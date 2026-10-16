"""Links "Abrir no Drive" das pastas a partir do Google Drive para computador (DriveFS), sem API do Google.

O DriveFS guarda localmente um banco SQLite com os metadados das pastas sincronizadas
(%LOCALAPPDATA%/Google/DriveFS/<conta>/mirror_metadata_sqlite.db): a tabela ``items`` tem o ID da pasta na nuvem
(coluna ``id``) e o nome (``local_title``), e ``stable_parents`` liga cada item à pasta de cima. Com isso o link
https://drive.google.com/drive/folders/<id> de um mês novo do All Brazil sai sozinho, sem ninguém cadastrar.

Só leitura (``mode=ro``), com tempo limite curto e cache; qualquer falha (DriveFS ausente, banco mudou de formato)
devolve vazio e a página usa os links conhecidos ou a pasta principal.
"""

from __future__ import annotations

import glob
import os
import sqlite3
import threading
import time

_CACHE: dict[str, tuple[float, dict[tuple[str, str], str]]] = {}
_LOCK = threading.Lock()
CACHE_SECONDS = 600


def _databases() -> list[str]:
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "DriveFS")
    return glob.glob(os.path.join(base, "*", "mirror_metadata_sqlite.db"))


def month_folder_ids(root_title: str) -> dict[tuple[str, str], str]:
    """{(pasta do ano, pasta do mês): ID na nuvem} das pastas <root_title>/<ano>/<mês> conhecidas pelo DriveFS."""
    with _LOCK:
        cached = _CACHE.get(root_title)
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]
    found: dict[tuple[str, str], str] = {}
    for database in _databases():
        try:
            connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=3)
            try:
                rows = connection.execute(
                    """select y.local_title, m.local_title, m.id
                         from items m
                         join stable_parents pm on pm.item_stable_id = m.stable_id
                         join items y on y.stable_id = pm.parent_stable_id
                         join stable_parents py on py.item_stable_id = y.stable_id
                         join items r on r.stable_id = py.parent_stable_id
                        where m.is_folder = 1 and y.is_folder = 1 and not m.trashed and r.local_title = ?""",
                    [root_title],
                ).fetchall()
            finally:
                connection.close()
        except sqlite3.Error:
            continue
        for year_title, month_title, cloud_id in rows:
            if year_title and month_title and cloud_id:
                found[(str(year_title), str(month_title))] = str(cloud_id)
    with _LOCK:
        _CACHE[root_title] = (time.monotonic(), found)
    return found


def folder_url(cloud_id: str) -> str:
    return f"https://drive.google.com/drive/folders/{cloud_id}"
