"""Publica um pacote já conferido em Configurações › Instalador (pasta runtime/app/dist desta máquina).

Uso: python tools/manutencao/publicar_instalador.py <INSTALAR_ESTOQUE_CONTABIL_x.zip>
O pacote anterior fica guardado como INSTALAR_ESTOQUE_CONTABIL.previous.zip (para voltar, renomeie de volta).
A cópia é feita num arquivo temporário e conferida por hash antes de substituir (nunca fica um ZIP pela metade).
"""
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
zip_path = Path(sys.argv[1])
dist = Path(os.environ["LOCALAPPDATA"]) / "OpsContabil" / "runtime" / "app" / "dist"
target, previous = dist / "INSTALAR_ESTOQUE_CONTABIL.zip", dist / "INSTALAR_ESTOQUE_CONTABIL.previous.zip"
staging = dist / ".INSTALAR_ESTOQUE_CONTABIL.publishing.zip"
digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
with zipfile.ZipFile(zip_path) as archive:
    name = next(n for n in archive.namelist() if n.replace("\\", "/").strip("/") == "INSTALAR_ESTOQUE_CONTABIL.manifest.json")
    manifest = json.loads(archive.read(name).decode("utf-8-sig"))
dist.mkdir(parents=True, exist_ok=True)
shutil.copyfile(zip_path, staging)
assert hashlib.sha256(staging.read_bytes()).hexdigest() == digest, "cópia divergente"
if target.exists():
    os.replace(target, previous)
os.replace(staging, target)
manifest["archive_sha256"] = digest
manifest["archive_size"] = target.stat().st_size
(dist / "INSTALAR_ESTOQUE_CONTABIL.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print("publicado:", manifest["version"], digest, target.stat().st_size)
