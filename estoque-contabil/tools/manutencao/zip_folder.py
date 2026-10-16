"""Compacta uma pasta num ZIP, tolerando bloqueios temporários do antivírus arquivo a arquivo, e confere o resultado.

Uso: python tools/manutencao/zip_folder.py <pasta_origem> <arquivo.zip>
Motivo: o Compress-Archive do PowerShell falha quando o antivírus segura por alguns segundos um arquivo recém-copiado.
"""
import sys
import time
import zipfile
from pathlib import Path

source, target = Path(sys.argv[1]), Path(sys.argv[2])
files = sorted(p for p in source.rglob("*") if p.is_file())
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in files:
        for attempt in range(30):
            try:
                archive.write(path, path.relative_to(source).as_posix())
                break
            except PermissionError:
                if attempt == 29:
                    raise
                time.sleep(1)
with zipfile.ZipFile(target) as archive:
    bad = archive.testzip()
    if bad or len(archive.namelist()) != len(files):
        sys.exit(f"ZIP inválido: {bad or 'contagem divergente'}")
print(f"ZIP ok: {len(files)} arquivos")
