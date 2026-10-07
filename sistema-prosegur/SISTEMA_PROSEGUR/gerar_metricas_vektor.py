import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict

import pandas as pd

SISTEMA_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SISTEMA_DIR, "documentos.db")
OUT_PATH = os.path.join(SISTEMA_DIR, "vektor_ar_metricas.json")


def safe_float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def periodo_atual() -> str:
    return datetime.now().strftime("%m-%Y")


def extrair_valor_analitico(doc: Dict[str, Any]) -> float:
    doc_type = str(doc.get("document_type") or "").strip().upper()

    # Mesmo criterio da aba Notas_e_CTEs do MASTER:
    # CTE_OS entra em "VALOR TOTAL DA PRESTACAO DO SERVICO"
    # NFSE entra em "VALOR DA NOTA (R$)".
    if doc_type in ("NFSE", "CTE_OS"):
        return safe_float(doc.get("valor_total_documento"))

    return 0.0


def agregar(rows):
    by_periodo_empresa = {}
    by_tipo = {}
    cards = {
        "total_docs": 0,
        "total_valor": 0.0,
        "empresas": {},
        "periodos": {}
    }

    for item in rows:
        periodo = item["periodo"] or "SEM_PERIODO"
        empresa = item["empresa"] or "DESCONHECIDA"
        tipo = item["document_type"] or "UNKNOWN"
        valor = safe_float(item["valor"])

        cards["total_docs"] += 1
        cards["total_valor"] += valor

        if empresa not in cards["empresas"]:
            cards["empresas"][empresa] = {"docs": 0, "valor": 0.0}
        cards["empresas"][empresa]["docs"] += 1
        cards["empresas"][empresa]["valor"] += valor

        if periodo not in cards["periodos"]:
            cards["periodos"][periodo] = {"docs": 0, "valor": 0.0}
        cards["periodos"][periodo]["docs"] += 1
        cards["periodos"][periodo]["valor"] += valor

        k = f"{periodo}__{empresa}"
        if k not in by_periodo_empresa:
            by_periodo_empresa[k] = {
                "periodo": periodo,
                "empresa": empresa,
                "docs": 0,
                "valor": 0.0
            }
        by_periodo_empresa[k]["docs"] += 1
        by_periodo_empresa[k]["valor"] += valor

        k2 = f"{periodo}__{empresa}__{tipo}"
        if k2 not in by_tipo:
            by_tipo[k2] = {
                "periodo": periodo,
                "empresa": empresa,
                "document_type": tipo,
                "docs": 0,
                "valor": 0.0
            }
        by_tipo[k2]["docs"] += 1
        by_tipo[k2]["valor"] += valor

    return {
        "cards": cards,
        "by_periodo_empresa": list(by_periodo_empresa.values()),
        "by_tipo": list(by_tipo.values())
    }


def main():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Banco não encontrado: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(
            """
            SELECT
                source_filename,
                raw_payload,
                document_type,
                periodo,
                empresa,
                numero_documento,
                updated_at,
                execution_id
            FROM documentos
            ORDER BY updated_at
            """,
            conn
        )
    finally:
        conn.close()

    if df.empty:
        current_period = periodo_atual()
        payload = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "execution_id": "",
            "current_period": current_period,
            "latest_execution": {
                "cards": {"total_docs": 0, "total_valor": 0.0, "empresas": {}, "periodos": {}},
                "by_periodo_empresa": [],
                "by_tipo": []
            },
            "current_period_base": {
                "cards": {"total_docs": 0, "total_valor": 0.0, "empresas": {}, "periodos": {}},
                "by_periodo_empresa": [],
                "by_tipo": []
            },
            "full_base": {
                "cards": {"total_docs": 0, "total_valor": 0.0, "empresas": {}, "periodos": {}},
                "by_periodo_empresa": [],
                "by_tipo": []
            }
        }
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"JSON vazio gerado em: {OUT_PATH}")
        return

    rows = []
    for _, row in df.iterrows():
        try:
            doc = json.loads(row["raw_payload"])
        except Exception:
            continue

        periodo = str(row.get("periodo") or doc.get("periodo") or "")
        empresa = str(row.get("empresa") or doc.get("empresa_nome") or "DESCONHECIDA").strip().upper()
        document_type = str(row.get("document_type") or doc.get("document_type") or "UNKNOWN").strip().upper()
        execution_id = str(row.get("execution_id") or "")
        valor = extrair_valor_analitico(doc)

        rows.append({
            "source_filename": str(row.get("source_filename") or ""),
            "periodo": periodo,
            "empresa": empresa,
            "document_type": document_type,
            "numero_documento": str(row.get("numero_documento") or ""),
            "updated_at": str(row.get("updated_at") or ""),
            "execution_id": execution_id,
            "valor": valor
        })

    exec_ids = [r["execution_id"] for r in rows if r["execution_id"]]
    latest_execution_id = exec_ids[-1] if exec_ids else ""

    current_period = periodo_atual()
    latest_rows = [r for r in rows if r["execution_id"] == latest_execution_id] if latest_execution_id else []
    current_period_rows = [r for r in rows if r["periodo"] == current_period]

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "execution_id": latest_execution_id,
        "current_period": current_period,
        "latest_execution": agregar(latest_rows),
        "current_period_base": agregar(current_period_rows),
        "full_base": agregar(rows)
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"JSON analítico gerado em: {OUT_PATH}")
    print(f"Última execution_id: {latest_execution_id}")
    print(f"Docs base completa: {payload['full_base']['cards']['total_docs']}")
    print(f"Valor base completa: {payload['full_base']['cards']['total_valor']:.2f}")


if __name__ == "__main__":
    main()
