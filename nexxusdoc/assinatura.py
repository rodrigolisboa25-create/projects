"""Assinatura das publicacoes do NexxusDoc (Ed25519, RFC 8032, so com a biblioteca padrao do Python).

O codigo fica na pasta compartilhada do Drive, que varias pessoas conseguem editar. Para que so o administrador
publique mudancas, cada publicacao tem um manifesto (publicacao.json: arquivos e SHA-256) assinado com a chave
privada que fica fora do Drive, na Area de Trabalho do administrador. As instalacoes so aplicam arquivos que
batem com um manifesto assinado por esta chave publica; qualquer alteracao feita direto no Drive e ignorada.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# Chave publica do administrador (a privada nunca vai para o Drive). Trocar a chave exige publicar este arquivo
# assinado com a chave antiga. Sem a chave antiga (perdida na troca de maquina de 03/11/2026, quando esta foi gerada),
# as instalacoes anteriores recusam a publicacao nova e so voltam a se atualizar rodando o instalador de novo.
PUBLIC_KEY_HEX = "1b3cd8ad4c0aef61edccbd117d062ddd3d4eb44243425c574a3d5f1ff043b28d"
MANIFEST = "publicacao.json"
SIGNATURE = "publicacao.sig"
# Chave publica do CADASTRO de acessos (05/11/2026), separada da de publicacao: so o computador do administrador master
# assina o access_control.json; alteracao feita direto no Drive nao bate com a assinatura e e ignorada.
CADASTRO_PUBLIC_KEY_HEX = "a9b85b785fdfe37927acb8703c9984a37ccc45a157270df4bfeb3e91f8a68549"

# --- Ed25519 (implementacao de referencia da RFC 8032, secao 6) -------------------------------------------
_p = 2 ** 255 - 19
_q = 2 ** 252 + 27742317777372353535851937790883648493
_d = -121665 * pow(121666, _p - 2, _p) % _p
_sqrt_m1 = pow(2, (_p - 1) // 4, _p)


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _sha512_modq(data: bytes) -> int:
    return int.from_bytes(_sha512(data), "little") % _q


def _add(P, Q):
    A, B = (P[1] - P[0]) * (Q[1] - Q[0]) % _p, (P[1] + P[0]) * (Q[1] + Q[0]) % _p
    C, D = 2 * P[3] * Q[3] * _d % _p, 2 * P[2] * Q[2] % _p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _p, G * H % _p, F * G % _p, E * H % _p)


def _mul(s: int, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _equal(P, Q) -> bool:
    return (P[0] * Q[2] - Q[0] * P[2]) % _p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % _p == 0


def _recover_x(y: int, sign: int):
    if y >= _p:
        return None
    x2 = (y * y - 1) * pow(_d * y * y + 1, _p - 2, _p) % _p
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_p + 3) // 8, _p)
    if (x * x - x2) % _p != 0:
        x = x * _sqrt_m1 % _p
    if (x * x - x2) % _p != 0:
        return None
    if (x & 1) != sign:
        x = _p - x
    return x


_gy = 4 * pow(5, _p - 2, _p) % _p
_gx = _recover_x(_gy, 0)
_G = (_gx, _gy, 1, _gx * _gy % _p)


def _compress(P) -> bytes:
    zinv = pow(P[2], _p - 2, _p)
    x, y = P[0] * zinv % _p, P[1] * zinv % _p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(data: bytes):
    if len(data) != 32:
        return None
    y = int.from_bytes(data, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _p)


def _expand(secret: bytes):
    h = _sha512(secret)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def public_key(secret: bytes) -> bytes:
    return _compress(_mul(_expand(secret)[0], _G))


def sign(secret: bytes, message: bytes) -> bytes:
    a, prefix = _expand(secret)
    A = _compress(_mul(a, _G))
    r = _sha512_modq(prefix + message)
    Rs = _compress(_mul(r, _G))
    s = (r + _sha512_modq(Rs + A + message) * a) % _q
    return Rs + int.to_bytes(s, 32, "little")


def verify(public: bytes, message: bytes, signature: bytes) -> bool:
    if len(public) != 32 or len(signature) != 64:
        return False
    A, R = _decompress(public), _decompress(signature[:32])
    if not A or not R:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _q:
        return False
    h = _sha512_modq(signature[:32] + public + message)
    return _equal(_mul(s, _G), _add(R, _mul(h, A)))


# --- Publicacao ---------------------------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def verified_manifest(folder: Path) -> dict | None:
    """Manifesto da pasta, somente se a assinatura for valida para a chave publica do administrador."""
    try:
        data = (folder / MANIFEST).read_bytes()
        signature = bytes.fromhex((folder / SIGNATURE).read_text(encoding="ascii").strip())
        if not verify(bytes.fromhex(PUBLIC_KEY_HEX), data, signature):
            return None
        manifest = json.loads(data.decode("utf-8"))
        return manifest if isinstance(manifest.get("arquivos"), dict) else None
    except (OSError, ValueError):
        return None


def mismatched_files(folder: Path, manifest: dict) -> list[str]:
    """Arquivos da pasta que nao conferem com o manifesto assinado (faltando ou alterados depois da publicacao)."""
    return [rel for rel, digest in manifest["arquivos"].items() if sha256_file(folder / rel) != digest]
