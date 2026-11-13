"""Gera bigquery_conhecimento.json: o conhecimento do BigQuery para o agente do Chat Nexxus (Consultas gerais).

12/11/2026, pedido do usuario: o agente nao sabia dizer que tabelas existem no BigQuery nem ligar as tabelas aos
processos. Fontes:
  - bigquery/catalogo_tabelas.json (catálogo privado autorizado, do projeto text_sql do usuario);
  - dicionario de colunas e regras de negocio do lake, lidos DIRETO do text_sql.zip (sem extrair; o .env do projeto
    nunca e lido);
  - query_console.json (procedimentos aprovados da área com as tabelas e colunas de cada um).
Uso: python tools/build_bigquery_conhecimento.py [caminho do text_sql.zip]
Depois: publicar (o arquivo esta em FILES do instalador).
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZIP = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads" / "text_sql.zip"
OUT = ROOT / "bigquery_conhecimento.json"
COLS_OUT = ROOT / "bigquery_colunas.json"     # todas as colunas, so para a ficha da tabela no Catalogo
SKIP_DATASETS = {"stage", "tech", "raw", "dpe_metadata"}     # tecnicos (regra do lake): nao usar para analise
MAX_COLS, MAX_DESC = 60, 90

# Supply only approved metadata in a local file kept outside public version control.
MANIFEST_PATH = ROOT / "tools" / "bigquery_manifest.private.json"
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.is_file() else {}
PROJETOS = MANIFEST.get("projetos", {})
TRANSACOES = MANIFEST.get("transacoes_sap", {})
FATOS_INBOUND = MANIFEST.get("fatos", [])
LIBRARY_PICK = MANIFEST.get("consultas_selecionadas", {})
LIBRARY_OUT = ROOT / "query_biblioteca.json"


def clean(text: object, limit: int = 0) -> str:
    text = " ".join(str(text or "").replace("—", "-").split())
    return text[:limit].rstrip() + "…" if limit and len(text) > limit else text


def main() -> None:
    catalog = json.loads((ROOT / "bigquery" / "catalogo_tabelas.json").read_text(encoding="utf-8"))
    qc = json.loads((ROOT / "query_console.json").read_text(encoding="utf-8"))
    dictionary: dict[str, dict] = {}
    with zipfile.ZipFile(ZIP) as package:
        for name in package.namelist():
            if name.startswith("text_sql/dados/dicionario/") and name.endswith(".json"):
                try:
                    item = json.loads(package.read(name).decode("utf-8"))
                    dictionary[item["id"]] = item
                except (ValueError, KeyError):
                    continue
        rules = package.read("text_sql/conhecimento/regras_negocio.md").decode("utf-8")
        library = json.loads(package.read("text_sql/dados/biblioteca_queries.json").decode("utf-8"))
    rules = rules.replace("—", "-")
    # Keep private business rules in the authorized external ZIP.
    # Publish generated output only after a separate disclosure review.
    picked = []
    for key, phase in LIBRARY_PICK.items():
        q = library.get(key)
        if not q:
            continue
        tags = q.get("tags")
        tags = tags if isinstance(tags, list) else re.findall(r"'([^']+)'", str(tags or ""))
        picked.append({"id": f"tsql-{key.replace('_', '-')}", "titulo": clean(q.get("titulo")), "fase": phase,
                       "descricao": clean(q.get("descricao"), 600), "sql": str(q.get("sql") or "").replace("—", "-").strip(),
                       "tags": tags, "origem": "Consulta pronta",
                       "observacao": "Confira os filtros e o período antes de usar."})
    # Consultas prontas da propria area (conferidas no BigQuery), mantidas a mao em tools/consultas_prontas_area.json.
    extra = ROOT / "tools" / "consultas_prontas_area.json"
    if extra.is_file():
        picked += json.loads(extra.read_text(encoding="utf-8")).get("consultas", [])
    LIBRARY_OUT.write_text(json.dumps({
        "observacao": "Consultas prontas da Query Console para a Logística Internacional (a partir do projeto "
                      "text_sql). Gerado por tools/build_bigquery_conhecimento.py; não editar à mão.",
        "gerado_em": date.today().isoformat(), "consultas": picked}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{LIBRARY_OUT.name}: {len(picked)} consultas")

    tables, sap_names, all_cols = [], [], {}
    for t in catalog:
        # tecnicas do lake: datasets de esteira, temp_* e tabelas sem nome de negocio (_sbc_<hash>, sem descricao)
        if t.get("dataset") in SKIP_DATASETS or str(t.get("tabela", "")).startswith(("temp_", "_")):
            continue
        d = dictionary.get(t["id"], {})
        cols = [c for c in d.get("colunas") or [] if not c.get("tecnica")]
        entry = {"id": t["id"], "desc": clean(t.get("descricao") or d.get("descricao_tabela"), 220)}
        if t.get("e_sap"):
            entry["sap"] = t.get("nome_sap")
            sap_names.append(t.get("nome_sap"))
        for key, src in (("linhas", d.get("linhas", t.get("linhas"))), ("gb", d.get("gb", t.get("gb"))),
                         ("particao", d.get("particionamento"))):
            if src not in (None, "", 0):
                entry[key] = src
        entry["n_colunas"] = len(d.get("colunas") or []) or t.get("colunas")
        entry["colunas"] = [[c["coluna"], c.get("tipo", ""), clean(c.get("descricao_gcp"), MAX_DESC)] for c in cols[:MAX_COLS]]
        tables.append(entry)
        # todas as colunas (13/11/2026): a ficha da tabela no Catalogo mostra todas; as tecnicas do lake vao marcadas (1)
        everything = d.get("colunas") or []
        all_cols[t["id"]] = [[c["coluna"], c.get("tipo", ""), clean(c.get("descricao_gcp"), 160), 1 if c.get("tecnica") else 0]
                             for c in everything]

    present = set(sap_names)
    transacoes = {k: [s for s in v if s in present] for k, v in TRANSACOES.items()}
    fases = {f["id"]: f["nome"] for f in qc.get("fases", [])}
    curated = qc.get("tabelas") or {}
    procedimentos = [{"titulo": p["titulo"], "fase": fases.get(p.get("fase"), p.get("fase")), "processo": p.get("processo", ""),
                      "unidades": p.get("unidades", []), "hoje": clean(p.get("hoje"), 400), "serve": clean(p.get("serve"), 300),
                      "tabelas": [{"tabela": (curated.get(x["id"]) or {}).get("caminho", x["id"]), "uso": x.get("uso", ""),
                                   "colunas": x.get("colunas", [])} for x in p.get("tabelas", [])],
                      "ligacao": p.get("ligacao", []), "fora_do_lake": p.get("fora", [])}
                     for p in qc.get("procedimentos", [])]
    tabelas_inbound = [{"tabela": t.get("caminho"), "nome": t.get("nome"), "descricao": clean(t.get("descricao"), 300),
                        "particao": t.get("particao"), "gb": t.get("gb"),
                        "colunas_principais": [[c["nome"], clean(c.get("descricao"), 80)] for c in t.get("colunas", [])[:25]]}
                       for t in curated.values()]
    counts: dict[str, int] = {}
    for t in tables:
        key = ".".join(t["id"].split(".")[:2])
        counts[key] = counts.get(key, 0) + 1
    out = {
        "observacao": "Gerado por tools/build_bigquery_conhecimento.py. Vai ao agente das Consultas gerais (Chat Nexxus) "
                      "quando a pergunta envolve BigQuery, tabelas ou dados. Não editar à mão: regerar.",
        "gerado_em": date.today().isoformat(),
        "resumo": {"total_tabelas": len(tables), "tabelas_sap": len(sap_names), "projeto_de_cobranca": MANIFEST.get("projeto_cobranca", "example-retail-project"),
                   "projetos": [{"projeto_dataset": k, "tabelas": n, "conteudo": PROJETOS.get(k, "")}
                                for k, n in sorted(counts.items())],
                   "tabelas_sap_no_lake": sorted(sap_names),
                   "nao_usar": "datasets stage, tech, raw e dpe_metadata e tabelas temp_* (técnicos do lake)"},
        "regras_lake": rules,
        "inbound": {"procedimentos": procedimentos, "tabelas": tabelas_inbound, "fora_do_lake": qc.get("sem_uso", []),
                    "fatos": FATOS_INBOUND},
        "transacoes_sap": transacoes,
        "tabelas": tables,
    }
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    assert "—" not in text
    OUT.write_text(text, encoding="utf-8")
    cols_text = json.dumps({"observacao": "Todas as colunas de cada tabela do catálogo: [nome, tipo, descrição, técnica do lake]. "
                                          "Gerado por tools/build_bigquery_conhecimento.py; não editar à mão.",
                            "gerado_em": date.today().isoformat(), "colunas": all_cols}, ensure_ascii=False, separators=(",", ":"))
    COLS_OUT.write_text(cols_text.replace("—", "-"), encoding="utf-8")
    print(f"{COLS_OUT.name}: {sum(len(v) for v in all_cols.values())} colunas de {len(all_cols)} tabelas, "
          f"{COLS_OUT.stat().st_size / 1048576:.1f} MB")
    print(f"{OUT.name}: {len(tables)} tabelas ({len(sap_names)} SAP), {len(procedimentos)} procedimentos, "
          f"{OUT.stat().st_size / 1048576:.1f} MB")


if __name__ == "__main__":
    main()
