"""Base de estoque: a legenda "Origem do PASSO A PASSO" filtra a grade (e o Excel), em qualquer campo ou num só."""

from __future__ import annotations

from ops_contabil.db import connect
from ops_contabil.inventory import list_inventory
from test_optimus_import import env  # noqa: F401 - fixture reaproveitada
from test_overview_filters import seed


def test_origin_filter_by_any_field_or_one_field(env) -> None:  # noqa: F811
    settings, database, *_ = env
    seed(database)  # 2026-09: source_row 3, 4, 5 e 6
    with connect(database) as connection:
        connection.execute("""create table if not exists pass_step_sources (period varchar not null, source_row bigint not null,
                              product_offer_end_date varchar, season varchar, year varchar)""")
        for row, pod, season, year in [(3, "MB59", "MB59", "Mês anterior (2026-08)"), (4, "Mês anterior (2026-08)", "All Brazil", "All Brazil"),
                                       (5, "Manual (ana, 01/10)", "Não localizado", "MB59"), (6, "MB59", "MB59", "MB59")]:
            connection.execute("insert into pass_step_sources values ('2026-09', ?, ?, ?, ?)", [row, pod, season, year])

    def rows(origin, field=None):
        return sorted(r["source_row"] for r in list_inventory(settings, "2026-09", 1, 50, "", "source_row", "asc",
                                                              origin=origin, origin_field=field)["rows"])

    assert rows(None) == [3, 4, 5, 6]
    assert rows("prev") == [3, 4]  # qualquer um dos três campos
    assert rows("prev", "year") == [3]
    assert rows("ab", "season") == [4] and rows("manual") == [5] and rows("none") == [5]
    assert rows("mb59", "product_offer_end_date") == [3, 6]
    totals = list_inventory(settings, "2026-09", 1, 50, "", "source_row", "asc", origin="mb59", origin_field="year")["totals"]
    assert totals["fiscal_total_amount"] == 70.0  # Σ segue o filtro (linhas 5 e 6: 60 + 10)
