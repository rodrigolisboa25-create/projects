from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb


def money(value: float | int | None) -> str:
    value = float(value or 0)
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main() -> int:
    period = sys.argv[1] if len(sys.argv) > 1 else "2026-08"
    db = Path(os.path.expandvars(r"%LOCALAPPDATA%/OpsContabil/processed/ops_contabil.duckdb"))
    if not db.is_file():
        print(f"Banco não encontrado: {db}")
        return 2

    con = duckdb.connect(str(db), read_only=True)
    try:
        exists = con.execute(
            "select count(*) from information_schema.tables where lower(table_name)='inventory_rows'"
        ).fetchone()[0]
        if not exists:
            print("Tabela inventory_rows não encontrada.")
            return 3

        def metric(where: str, params=None):
            params = [period, *(params or [])]
            row = con.execute(
                f"""select count(*) as rows,
                           count(distinct material) as materials,
                           coalesce(sum(fiscal_total_amount),0) as fiscal
                    from inventory_rows
                    where period=? and ({where})""",
                params,
            ).fetchone()
            return int(row[0]), int(row[1]), float(row[2] or 0)

        total = metric("true")
        companies = con.execute(
            """select coalesce(company,'<vazio>'), count(*), coalesce(sum(fiscal_total_amount),0)
               from inventory_rows where period=? group by 1 order by 2 desc""",
            [period],
        ).fetchall()

        pending_clause = """(
            division_description is null or trim(coalesce(division_description,''))='' or
            material_origin is null or trim(coalesce(material_origin,''))='' or
            lifecycle is null or trim(coalesce(lifecycle,''))='' or
            lifecycle_description is null or trim(coalesce(lifecycle_description,''))='' or
            product_offer_end_date is null or
            aging_days is null or
            aging_bucket is null or trim(coalesce(aging_bucket,''))='' or
            season is null or trim(coalesce(season,''))='' or
            year is null or
            season_year is null or trim(coalesce(season_year,''))=''
        )"""
        no_ab = """(
            division_description is null and material_origin is null and
            lifecycle is null and lifecycle_description is null
        )"""
        partial_ab = """(
            not (division_description is null and material_origin is null and lifecycle is null and lifecycle_description is null)
            and (
                division_description is null or trim(coalesce(division_description,''))='' or
                material_origin is null or trim(coalesce(material_origin,''))='' or
                lifecycle is null or trim(coalesce(lifecycle,''))='' or
                lifecycle_description is null or trim(coalesce(lifecycle_description,''))=''
            )
        )"""

        metrics = [
            ("Pendência atual do botão", pending_clause),
            ("Sem nenhum atributo All Brazil", no_ab),
            ("All Brazil parcial/incompleto", partial_ab),
            ("Sem Product Offer End Dt", "product_offer_end_date is null"),
            ("Sem Days", "aging_days is null"),
            ("Sem AGING", "aging_bucket is null or trim(coalesce(aging_bucket,''))=''"),
            ("Sem Season", "season is null or trim(coalesce(season,''))=''"),
            ("Sem Year", "year is null"),
            ("Sem Season/Coleção", "season_year is null or trim(coalesce(season_year,''))=''"),
        ]

        print(f"\nDIAGNÓSTICO DE PENDÊNCIAS - {period}")
        print("=" * 78)
        print(f"Total da base: {total[0]:,} linhas | {total[1]:,} materiais | {money(total[2])}")
        print("\nEMPRESAS NA BASE")
        for company, rows, fiscal in companies:
            print(f"  {company}: {int(rows):,} linhas | {money(fiscal)}")

        print("\nQUEBRA DAS PENDÊNCIAS")
        for label, clause in metrics:
            rows, materials, fiscal = metric(clause)
            pct = (100 * rows / total[0]) if total[0] else 0
            print(f"  {label}: {rows:,} linhas ({pct:.2f}%) | {materials:,} materiais | {money(fiscal)}")

        print("\nSTATUS DAS FONTES")
        try:
            row = con.execute(
                """select snapshot_date, source_path, inventory_keys, matched_keys, coverage_pct,
                          duplicate_keys, conflict_keys, imported_at
                   from all_brazil_imports where period=? order by imported_at desc limit 1""",
                [period],
            ).fetchone()
            if row:
                print(
                    "  All Brazil: "
                    f"snapshot={row[0]} | cobertura={row[4]}% | chaves posição={row[2]:,} | "
                    f"casadas={row[3]:,} | duplicadas={row[5]:,} | conflitos={row[6]:,} | fonte={row[1]}"
                )
            else:
                print("  All Brazil: sem registro de enriquecimento.")
        except Exception as exc:
            print(f"  All Brazil: não foi possível consultar ({exc}).")

        try:
            row = con.execute(
                """select source_path, source_rows, lookup_rows, imported_at
                   from mb59_imports where period=? order by imported_at desc limit 1""",
                [period],
            ).fetchone()
            if row:
                print(
                    f"  MB59: linhas fonte={row[1]:,} | chaves CE & MAT={row[2]:,} | "
                    f"importada em={row[3]} | fonte={row[0]}"
                )
            else:
                print("  MB59: sem registro de importação.")
        except Exception as exc:
            print(f"  MB59: não foi possível consultar ({exc}).")

        print("\nAMOSTRA: MATERIAIS SEM NENHUM ATRIBUTO ALL BRAZIL")
        rows = con.execute(
            f"""select material, plant, material_description, fiscal_total_amount
                 from inventory_rows where period=? and {no_ab}
                 order by abs(coalesce(fiscal_total_amount,0)) desc nulls last limit 20""",
            [period],
        ).fetchall()
        for material, plant, description, fiscal in rows:
            print(f"  {material} | centro {plant} | {money(fiscal)} | {description or ''}")

        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
