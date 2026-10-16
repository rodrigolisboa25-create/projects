"""Confere um pacote do instalador antes de publicar: código igual ao projeto e base (seed) completa.

Uso: python tools/manutencao/verificar_instalador.py <INSTALAR_ESTOQUE_CONTABIL_x.zip>
Confere:
  1. cada arquivo de src/ e config/ do projeto está no ZIP com o mesmo conteúdo (hash) — nada faltando ou velho;
  2. INSTALAR_ESTOQUE_CONTABIL.bat e installer_main.py iguais aos de installer/;
  3. a base que vai junto (payload/seed/ops_contabil.duckdb) tem as competências, a base mestre e as entradas da MB59.
Sai com código 1 se algo estiver errado (não publique esse pacote).
"""
import hashlib
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
zip_path = Path(sys.argv[1])
project = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parents[2]
skip = lambda p: "__pycache__" in p.parts or ".egg-info" in str(p) or p.suffix == ".pyc" or ".bak" in p.name  # noqa: E731

with zipfile.ZipFile(zip_path) as archive:
    inside = {n: hashlib.sha256(archive.read(n)).hexdigest() for n in archive.namelist() if not n.endswith("/")}
missing, different = [], []
for folder in ("src", "config"):
    for file in (project / folder).rglob("*"):
        if file.is_file() and not skip(file):
            key = "payload/" + file.relative_to(project).as_posix()
            if key not in inside:
                missing.append(key)
            elif inside[key] != hashlib.sha256(file.read_bytes()).hexdigest():
                different.append(key)
for name in ("INSTALAR_ESTOQUE_CONTABIL.bat", "installer_main.py"):
    if inside.get(name) != hashlib.sha256((project / "installer" / name).read_bytes()).hexdigest():
        different.append(name)
print(f"arquivos no ZIP: {len(inside)}")
print(f"faltando: {missing or 'nenhum'}")
print(f"diferentes: {different or 'nenhum'}")

import duckdb  # noqa: E402 - só depois de conferir os arquivos

temporary = tempfile.mkdtemp(prefix="seedchk-")
problems = len(missing) + len(different)
try:
    with zipfile.ZipFile(zip_path) as archive:
        archive.extract("payload/seed/ops_contabil.duckdb", temporary)
    connection = duckdb.connect(os.path.join(temporary, "payload", "seed", "ops_contabil.duckdb"), read_only=True)
    tables = {row[0] for row in connection.execute("select table_name from information_schema.tables").fetchall()}
    for table in ("inventory_rows", "master_base_rows", "mb59_material_entries"):
        if table not in tables:
            print(f"AUSENTE na base: {table}")
            problems += 1
    print("competências:", connection.execute(
        "select period, count(*), round(sum(fiscal_total_amount),2) from inventory_rows group by 1 order by 1").fetchall())
    print("<2022 por competência:", connection.execute(
        "select period, round(sum(fiscal_total_amount),2) from inventory_rows where historical_year_bucket='<2022' group by 1 order by 1").fetchall())
    connection.close()
finally:
    shutil.rmtree(temporary, ignore_errors=True)
print("RESULTADO:", "OK" if not problems else f"{problems} problema(s) — não publique")
sys.exit(1 if problems else 0)
