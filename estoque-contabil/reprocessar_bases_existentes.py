from __future__ import annotations

import calendar
import json
import sys
from datetime import date
from pathlib import Path

from ops_contabil.db import connect
from ops_contabil.inventory import import_zmm119_xlsx
from ops_contabil.mappings import apply_mapping_rules
from ops_contabil.mb59 import enrich_inventory_pass_step, import_mb59_xlsx
from ops_contabil.settings import load_settings
from ops_contabil.sources.all_brazil import enrich_inventory_from_all_brazil


def _latest_xlsx(folder: Path) -> Path:
    files = sorted(
        (path for path in folder.glob("*.xlsx") if not path.name.startswith("~$")),
        key=lambda path: path.stat().st_mtime,
    )
    if not files:
        raise FileNotFoundError(f"Nenhum XLSX encontrado em {folder}")
    return files[-1]


def _progress(period: str, stage: str):
    last_bucket = -1

    def report(fraction: float, message: str) -> None:
        nonlocal last_bucket
        bucket = int(max(0.0, min(1.0, fraction)) * 20)
        if bucket != last_bucket:
            last_bucket = bucket
            print(f"[{period}] {stage} {bucket * 5:>3}% - {message}", flush=True)

    return report


def process_period(period: str) -> dict[str, object]:
    settings = load_settings()
    year, month = map(int, period.split("-"))
    as_of = date(year, month, calendar.monthrange(year, month)[1])
    mb59_path = _latest_xlsx(settings.path("landing") / "mb59" / period)
    zmm119_path = _latest_xlsx(settings.path("landing") / "zmm119" / period)

    print(f"[{period}] Importando MB59 existente: {mb59_path.name}", flush=True)
    mb59 = import_mb59_xlsx(settings, period, mb59_path)
    print(f"[{period}] Importando ZMM119 existente: {zmm119_path.name}", flush=True)
    inventory = import_zmm119_xlsx(
        settings,
        period,
        zmm119_path,
        progress_callback=_progress(period, "ZMM119"),
    )
    all_brazil = enrich_inventory_from_all_brazil(
        settings,
        period,
        as_of,
        progress_callback=_progress(period, "All Brazil"),
    )
    pass_step = enrich_inventory_pass_step(
        settings,
        period,
        as_of,
        progress_callback=_progress(period, "PASSO A PASSO"),
    )
    apply_mapping_rules(settings, period, as_of)

    with connect(settings.path("database")) as connection:
        audit = connection.execute(
            """select count(*) as rows,
                      count(distinct center_material_key) as keys,
                      count(*) filter (where product_offer_end_date is null) as missing_offer,
                      count(*) filter (where season is null or trim(season)='') as missing_season,
                      count(*) filter (where year is null) as missing_year,
                      count(*) filter (where season_year is null or trim(season_year)='') as missing_season_year,
                      count(*) filter (where company<>'7170' or company is null) as invalid_company
                 from inventory_rows where period=?""",
            [period],
        ).fetchone()

    return {
        "period": period,
        "zmm119": inventory,
        "mb59": mb59,
        "all_brazil": all_brazil,
        "pass_step": pass_step,
        "audit": {
            "rows": int(audit[0]),
            "keys": int(audit[1]),
            "missing_product_offer_end_date": int(audit[2]),
            "missing_season": int(audit[3]),
            "missing_year": int(audit[4]),
            "missing_season_year": int(audit[5]),
            "invalid_company_rows": int(audit[6]),
        },
    }


def main() -> None:
    periods = sys.argv[1:] or ["2026-07", "2026-08"]
    results = [process_period(period) for period in periods]
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
