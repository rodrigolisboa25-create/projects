from ops_contabil.db import connect
from ops_contabil.mb59 import mb59_status
from ops_contabil.settings import load_settings


settings = load_settings()
with connect(settings.path("database")) as connection:
    final = connection.execute(
        """select period,
                  count(*),
                  count(distinct center_material_key),
                  count(*) filter (where product_offer_end_date is null),
                  count(*) filter (where season is null or trim(season)=''),
                  count(*) filter (where year is null),
                  count(*) filter (where season_year is null or trim(season_year)=''),
                  count(*) filter (where company<>'7170' or company is null)
             from inventory_rows
            where period in ('2026-07','2026-08')
            group by period order by period"""
    ).fetchall()
    all_brazil = connection.execute(
        """select period,inventory_keys,matched_keys,coverage_pct,conflict_keys
             from all_brazil_imports
            where period in ('2026-07','2026-08')
            order by period"""
    ).fetchall()

print("FINAL", final)
print("ALL_BRAZIL", all_brazil)
print("MB59", mb59_status(settings, "2026-08"))
