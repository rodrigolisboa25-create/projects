from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

from .db import connect

SESSION_COOKIE = "ops_contabil_session"
CSRF_COOKIE = "ops_contabil_csrf"
BOOTSTRAP_ADMINS = (
    "rodrigo.lisboa@gruposbf.com.br",
    "gabriella.lalonso@gruposbf.com.br",
)
PAGE_CATALOG = (
    ("overview", "Visão e relatórios"),
    ("inventory", "Base de estoque"),
    ("sap", "Extrações SAP"),
    ("all-brazil", "Bases All Brazil"),
    ("mapping", "Mapping"),
    ("governance", "Controles e auditoria"),
    ("health", "Health Center"),
    ("agent", "Optimus"),
    ("docs", "Documentação"),
)
PAGE_KEYS = frozenset(key for key, _ in PAGE_CATALOG)
# Obrigatórias para o perfil Usuário. Configurações também fica disponível a todos,
# mas só com Interface e experiência e Notificações (fora do catálogo de páginas).
MANDATORY_USER_PAGES = ("overview", "docs")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@([^\s@]+)$")


def _auth_config(settings: Any) -> dict[str, Any]:
    path = settings.root / "config" / "auth.yaml"
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError:
        loaded = {}
    return loaded if isinstance(loaded, dict) else {}


def allowed_domains(settings: Any) -> frozenset[str]:
    configured = _auth_config(settings).get("allowed_domains", ["gruposbf.com.br", "fisia.com.br"])
    return frozenset(str(item).strip().lower().lstrip("@") for item in configured if str(item).strip())


def session_hours(settings: Any) -> int:
    raw = os.getenv("OPS_SESSION_HOURS", str(_auth_config(settings).get("session_hours", 12)))
    try:
        return max(1, min(168, int(raw)))
    except ValueError:
        return 12


def normalize_corporate_email(settings: Any, email: str) -> str:
    normalized = email.strip().lower()
    match = EMAIL_PATTERN.fullmatch(normalized)
    if not match or match.group(1) not in allowed_domains(settings):
        raise ValueError("Use um e-mail corporativo @gruposbf.com.br ou @fisia.com.br.")
    return normalized


def ensure_auth_schema(settings: Any) -> None:
    with connect(settings.path("database")) as connection:
        for email in BOOTSTRAP_ADMINS:
            connection.execute(
                """insert into allowed_users(email, is_active, role, allowed_pages, updated_at)
                   values (?, true, 'admin', '[]', current_timestamp)
                   on conflict(email) do update set
                     is_active=true,
                     role='admin',
                     allowed_pages='[]',
                     updated_at=excluded.updated_at""",
                [email],
            )


def sanitize_role_pages(role: str, pages: list[str] | None) -> tuple[str, list[str]]:
    normalized_role = role.strip().lower()
    if normalized_role not in {"admin", "user"}:
        raise ValueError("Perfil inválido. Use Administrador ou Usuário.")
    selected = {str(page).strip() for page in (pages or []) if str(page).strip() in PAGE_KEYS}
    if normalized_role == "user":
        selected.update(MANDATORY_USER_PAGES)
    normalized_pages = [key for key, _label in PAGE_CATALOG if key in selected]
    return normalized_role, ([] if normalized_role == "admin" else normalized_pages)


def windows_corporate_email(settings: Any) -> str:
    if os.name != "nt":
        raise RuntimeError("A verificação sem OAuth exige uma sessão corporativa do Windows.")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            ["whoami", "/upn"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("Não foi possível consultar a identidade corporativa do Windows.") from exc
    if completed.returncode != 0:
        raise RuntimeError("O Windows não encontrou um UPN corporativo para este usuário.")
    try:
        return normalize_corporate_email(settings, completed.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("Entre no Windows com sua conta corporativa @gruposbf.com.br ou @fisia.com.br.") from exc


def authorize_windows_user(settings: Any, entered_email: str) -> tuple[dict[str, Any], str]:
    requested_email = normalize_corporate_email(settings, entered_email)
    verified_email = windows_corporate_email(settings)
    if requested_email != verified_email:
        raise PermissionError(
            f"O e-mail informado não corresponde à conta corporativa conectada ao Windows ({verified_email})."
        )
    identity_subject = f"windows:{verified_email}"
    with connect(settings.path("database")) as connection:
        row = connection.execute(
            "select email, is_active, role, allowed_pages, identity_subject from allowed_users where email=?",
            [verified_email],
        ).fetchone()
        if row is None or not bool(row[1]):
            raise PermissionError("Seu e-mail corporativo ainda não foi liberado por um administrador.")
        if row[4] and row[4] != identity_subject:
            raise PermissionError("Esta liberação está vinculada a outra identidade corporativa.")
        connection.execute(
            "update allowed_users set identity_subject=?, last_login_at=current_timestamp, updated_at=current_timestamp where email=?",
            [identity_subject, verified_email],
        )
    return _user_payload(row[0], row[2], row[3], ""), identity_subject


def _secret_path(settings: Any) -> Path:
    base = settings.path("processed").parent
    base.mkdir(parents=True, exist_ok=True)
    return base / "auth_session.key"


def _session_secret(settings: Any) -> bytes:
    path = _secret_path(settings)
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip().encode("utf-8")


def create_session_token(settings: Any, email: str, subject: str) -> str:
    payload = {
        "email": email,
        "sub": subject,
        "exp": int(time.time()) + session_hours(settings) * 3600,
        "nonce": secrets.token_hex(8),
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=")
    signature = hmac.new(_session_secret(settings), body, hashlib.sha256).digest()
    return body.decode() + "." + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()


def read_session_token(settings: Any, token: str | None) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    body_text, signature_text = token.split(".", 1)
    body = body_text.encode()
    try:
        supplied = base64.urlsafe_b64decode(signature_text + "=" * (-len(signature_text) % 4))
        expected = hmac.new(_session_secret(settings), body, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body_text + "=" * (-len(body_text) % 4)))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) <= int(time.time()):
        return None
    return payload


def current_user(settings: Any, token: str | None) -> dict[str, Any] | None:
    session = read_session_token(settings, token)
    if session is None:
        return None
    with connect(settings.path("database")) as connection:
        row = connection.execute(
            "select email, is_active, role, allowed_pages, identity_subject from allowed_users where email=?",
            [str(session.get("email", "")).lower()],
        ).fetchone()
    if row is None or not bool(row[1]) or not row[4] or row[4] != session.get("sub"):
        return None
    return _user_payload(row[0], row[2], row[3], "")


def _user_payload(email: str, role: str | None, pages_json: str | None, name: str) -> dict[str, Any]:
    normalized_role = "admin" if role == "admin" else "user"
    if normalized_role == "admin":
        pages = [key for key, _label in PAGE_CATALOG]
    else:
        try:
            stored = json.loads(pages_json or "[]")
        except (json.JSONDecodeError, TypeError):
            stored = []
        selected = {str(page) for page in stored if str(page) in PAGE_KEYS}
        selected.update(MANDATORY_USER_PAGES)
        pages = [key for key, _label in PAGE_CATALOG if key in selected]
    return {"email": email, "name": name, "role": normalized_role, "pages": pages}


def page_catalog() -> list[dict[str, str]]:
    return [{"key": key, "label": label} for key, label in PAGE_CATALOG]


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)
