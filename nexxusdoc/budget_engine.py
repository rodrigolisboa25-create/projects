"""Budget Inbound (pagina Budget do NexxusDoc): motor de calculo, importacao de planilhas e exportacao no MODELO.

Referencia: "Nexxus · Modulo de Auditoria de Orcamento Inbound" (04/11/2026) e a planilha
Orcamento_Inbound_2027_Resumo_Executivo_MODELO.xlsx (budget_modelo.xlsx), que o usuario definiu como o modelo oficial.

- O calculo e DETERMINISTICO (secao 14.3 da especificacao): premissas -> tarifa vigente por mes -> volume, conteineres
  e processos -> custo de cada linha -> 13 rubricas -> total. Nada aqui passa por IA.
- Importa tres formatos: o MODELO (abas Premissas + Premissas Detalhadas + Calculo Mensal), a planilha FISIA de
  orcamento (abas Premissas + Orcamento AAAA, versoes de 2027) e, como previa, qualquer outra planilha (premissas
  achadas pelos rotulos em todas as abas). O que nao for achado fica com o valor de referencia e aparece na previa.
- Exporta sempre no MODELO: copia budget_modelo.xlsx e troca so as celulas de entrada direto no XML (assim graficos,
  formatos e formulas ficam intactos) e marca o arquivo para recalcular ao abrir no Excel.
"""
from __future__ import annotations

import copy
import io
import math
import re
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
MESES_LONGOS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
                "novembro", "dezembro"]


def norm(text: Any) -> str:
    plain = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.findall(r"[a-z0-9]+", plain))


def normx(text: Any) -> str:
    """norm() que guarda o sentido de > e < (CIF >1M e CIF <1M sao linhas diferentes)."""
    return norm(str(text or "").replace(">", " maior ").replace("<", " menor ").replace("→", " "))


def xl_round(x: float, digits: int = 0) -> float:
    """ARRED do Excel (metade para longe do zero)."""
    f = 10 ** digits
    return math.copysign(math.floor(abs(x) * f + 0.5) / f, x)


def xl_roundup(x: float) -> float:
    return math.copysign(math.ceil(abs(x) - 1e-12), x)


# ---------------------------------------------------------------------------
# Catalogo de premissas (secao 15.2). kind: int | pct | num | usd | brl
# ---------------------------------------------------------------------------
# Escalares (grupo, chave, rotulo, unidade, tipo, padrao, padroes de rotulo para importar)
ESCALARES: list[dict[str, Any]] = [
    {"g": "Principais", "k": "volume_total_units", "l": "Volume recebido", "u": "units no ano", "t": "int", "v": 16503483,
     "re": [r"^volume recebido", r"^volume total"]},
    {"g": "Principais", "k": "units_por_conteiner", "l": "Units por contêiner", "u": "units", "t": "int", "v": 10568,
     "re": [r"^units por conteiner"]},
    {"g": "Principais", "k": "pct_modal_aereo", "l": "Participação do modal aéreo", "u": "% das units", "t": "pct", "v": 0.0008,
     "re": [r"participacao do modal aereo", r"^share modal aereo"]},
    {"g": "Principais", "k": "cambio_usd_brl", "l": "Câmbio USD/BRL", "u": "R$ por US$", "t": "num", "v": 5.15,
     "re": [r"^cambio"]},
    {"g": "Principais", "k": "ipca", "l": "IPCA do ano", "u": "% ao ano", "t": "pct", "v": 0.0544, "re": [r"^ipca"]},
    {"g": "Principais", "k": "afrmm", "l": "AFRMM", "u": "% sobre frete, bunker e capatazia", "t": "pct", "v": 0.08,
     "re": [r"^afrmm"]},
    {"g": "Principais", "k": "seguro_apolice_usd_ano", "l": "Seguro internacional (apólice)", "u": "US$ por ano", "t": "usd",
     "v": 50029.13, "re": [r"^seguro internacional"]},
    {"g": "Percentuais", "k": "pct_conteineres_biocombustivel", "l": "% contêineres com biocombustível", "u": "%", "t": "pct",
     "v": 0.20, "re": [r"conteineres com biocombustivel"]},
    {"g": "Percentuais", "k": "pct_processos_cif_acima_1m", "l": "% processos com CIF acima de R$1M", "u": "%", "t": "pct",
     "v": 0.5025, "re": [r"processos com cif acima"]},
    {"g": "Percentuais", "k": "pct_processos_armazenagem_acima_10_dias", "l": "% processos com armazenagem acima de 10 dias",
     "u": "%", "t": "pct", "v": 0.59, "re": [r"armazenagem acima de 10"]},
    {"g": "Percentuais", "k": "pct_nf_acima_1m_rodoviario", "l": "% NFs acima de R$1M (frete rodoviário)", "u": "%", "t": "pct",
     "v": 0.91, "re": [r"nfs acima de r 1m"]},
    {"g": "Percentuais", "k": "pct_conteineres_escolta_armada", "l": "% contêineres com escolta armada", "u": "%", "t": "pct",
     "v": 0.11, "re": [r"conteineres com escolta"]},
    {"g": "Percentuais", "k": "pct_conteineres_estadia_veiculo", "l": "% contêineres com estadia de veículo", "u": "%", "t": "pct",
     "v": 0.03, "re": [r"conteineres com estadia"]},
    {"g": "Percentuais", "k": "pct_conteineres_pre_stacking", "l": "% contêineres com pré-stacking / depot", "u": "%", "t": "pct",
     "v": 0.02, "re": [r"conteineres com pre stacking"]},
    {"g": "Percentuais", "k": "pct_conteineres_horas_paradas", "l": "% contêineres com horas paradas", "u": "%", "t": "pct",
     "v": 0.06, "re": [r"conteineres com horas paradas"]},
    {"g": "Percentuais", "k": "units_por_processo_aereo", "l": "Units por processo aéreo", "u": "units", "t": "int", "v": 590,
     "re": [r"^units por processo aereo"]},
    {"g": "Percentuais", "k": "reajuste_in_house", "l": "Reajuste In-House", "u": "% (dissídio)", "t": "pct", "v": 0.05,
     "re": [r"reajuste adicional in house", r"reajuste.*in house"]},
]

# Tarifas (linha da aba Premissas Detalhadas no MODELO; mesma linha na aba Premissas da planilha FISIA)
# reajuste: ipca | inhouse | nenhum | fixo
TARIFAS: list[dict[str, Any]] = [
    {"k": "frete_maritimo_1", "row": 28, "l": "Frete marítimo – 1ª tarifa", "drv": "por contêiner", "m": "USD", "rj": "nenhum", "mes": 1, "v": 1223, "re": [r"frete maritimo 1"]},
    {"k": "frete_maritimo_2", "row": 29, "l": "Frete marítimo – 2ª tarifa", "drv": "por contêiner", "m": "USD", "rj": "nenhum", "mes": 7, "v": 1754, "re": [r"frete maritimo 2"]},
    {"k": "frete_aereo", "row": 30, "l": "Frete aéreo", "drv": "por unit aérea", "m": "BRL", "rj": "ipca", "mes": 1, "v": 35.70, "re": [r"^frete aereo"]},
    {"k": "bunker", "row": 31, "l": "Bunker", "drv": "por contêiner", "m": "USD", "rj": "nenhum", "mes": 1, "v": 1254, "re": [r"^bunker"]},
    {"k": "biocombustivel", "row": 32, "l": "Biocombustível", "drv": "por contêiner c/ bio", "m": "USD", "rj": "nenhum", "mes": 1, "v": 581, "re": [r"^biocombustivel"]},
    {"k": "capatazias", "row": 33, "l": "Capatazias", "drv": "por contêiner", "m": "BRL", "rj": "ipca", "mes": 1, "v": 988.05, "re": [r"^capatazia"]},
    {"k": "taxa_siscomex", "row": 34, "l": "Taxa Siscomex", "drv": "por unit", "m": "BRL", "rj": "nenhum", "mes": 1, "v": 0.0398, "re": [r"siscomex"]},
    {"k": "arm_cif_maior_ate10", "row": 35, "l": "Armazenagem – CIF >1M, até 10 dias", "drv": "por contêiner", "m": "BRL", "rj": "ipca", "mes": 5, "v": 3066.72, "re": [r"armazenagem cif maior 1m ate 10"]},
    {"k": "arm_cif_menor_ate10", "row": 36, "l": "Armazenagem – CIF <1M, até 10 dias", "drv": "por contêiner", "m": "BRL", "rj": "ipca", "mes": 5, "v": 2357.10, "re": [r"armazenagem cif menor 1m ate 10"]},
    {"k": "arm_cif_maior_acima10", "row": 37, "l": "Armazenagem – CIF >1M, acima de 10 dias", "drv": "por contêiner", "m": "BRL", "rj": "ipca", "mes": 5, "v": 0, "re": [r"armazenagem cif maior 1m acima de 10"]},
    {"k": "arm_cif_menor_acima10", "row": 38, "l": "Armazenagem – CIF <1M, acima de 10 dias", "drv": "por contêiner", "m": "BRL", "rj": "ipca", "mes": 5, "v": 0, "re": [r"armazenagem cif menor 1m acima de 10"]},
    {"k": "desembaraco", "row": 39, "l": "Desembaraço (DI/DUIMP)", "drv": "por processo", "m": "BRL", "rj": "ipca", "mes": 1, "v": 532.29, "re": [r"^desembaraco"]},
    {"k": "carta_protesto", "row": 40, "l": "Carta protesto", "drv": "fixo mensal", "m": "BRL", "rj": "ipca", "mes": 1, "v": 1154.85, "re": [r"^carta protesto"]},
    {"k": "licenca_ncm", "row": 41, "l": "Licença de Importação / NCM", "drv": "fixo mensal", "m": "BRL", "rj": "ipca", "mes": 1, "v": 9274.33, "re": [r"^licenca de importacao"]},
    {"k": "servico_dev", "row": 42, "l": "Serviço de desenvolvimento", "drv": "fixo mensal", "m": "BRL", "rj": "ipca", "mes": 2, "v": 593.75, "re": [r"^servico de desenvolvimento"]},
    {"k": "duimp_catalogo", "row": 43, "l": "DUIMP – catálogo de produto", "drv": "fixo mensal", "m": "BRL", "rj": "nenhum", "mes": 0, "v": 0, "re": [r"^duimp"]},
    {"k": "flowls", "row": 44, "l": "Flowls", "drv": "fixo mensal", "m": "BRL", "rj": "ipca", "mes": 1, "v": 15000, "re": [r"^flowls"]},
    {"k": "ttms", "row": 45, "l": "TTMS", "drv": "fixo mensal", "m": "BRL", "rj": "ipca", "mes": 1, "v": 5410, "re": [r"^ttms"]},
    {"k": "in_house", "row": 46, "l": "In-House (4 recursos)", "drv": "fixo mensal", "m": "BRL", "rj": "inhouse", "mes": 7, "v": 57123, "re": [r"^in house"]},
    {"k": "demurrage", "row": 47, "l": "Demurrage", "drv": "fixo mensal", "m": "BRL", "rj": "nenhum", "mes": 0, "v": 0, "re": [r"^demurrage"]},
    {"k": "multa", "row": 48, "l": "Multa", "drv": "por unit", "m": "BRL", "rj": "nenhum", "mes": 0, "v": 0, "re": [r"^multa"]},
    {"k": "rod_nf_maior", "row": 49, "l": "Frete Santos → Extrema – NF >1M", "drv": "por contêiner", "m": "BRL", "rj": "ipca", "mes": 2, "v": 6637.19, "re": [r"santos extrema nf maior 1m", r"frete santos extrema base"]},
    {"k": "rod_nf_menor", "row": 50, "l": "Frete Santos → Extrema – NF <1M", "drv": "por contêiner", "m": "BRL", "rj": "ipca", "mes": 2, "v": 6218.31, "re": [r"santos extrema nf menor 1m"]},
    {"k": "rod_aereo", "row": 51, "l": "Rodoviário aéreo GRU/VCP", "drv": "por processo aéreo", "m": "BRL", "rj": "ipca", "mes": 2, "v": 698.06, "re": [r"rodoviario aereo"]},
    {"k": "escolta", "row": 52, "l": "Escolta armada", "drv": "por evento", "m": "BRL", "rj": "ipca", "mes": 2, "v": 4608.98, "re": [r"^escolta armada$"]},
    {"k": "escolta_fixo", "row": 53, "l": "Escolta armada – fixo", "drv": "fixo mensal", "m": "BRL", "rj": "nenhum", "mes": 2, "v": 0, "re": [r"^escolta armada fixo"]},
    {"k": "trava", "row": 54, "l": "Trava Ciltronics (16 travas)", "drv": "fixo mensal", "m": "BRL", "rj": "ipca", "mes": 2, "v": 16704.71, "re": [r"^trava"]},
    {"k": "estadia", "row": 55, "l": "Estadia de veículo (12h)", "drv": "por evento", "m": "BRL", "rj": "ipca", "mes": 2, "v": 1824.86, "re": [r"^estadia"]},
    {"k": "pre_stacking", "row": 56, "l": "Pré-stacking / Depot", "drv": "por evento", "m": "BRL", "rj": "ipca", "mes": 2, "v": 1878.66, "re": [r"^pre stacking"]},
    {"k": "horas_paradas", "row": 57, "l": "Horas paradas (3h)", "drv": "por evento", "m": "BRL", "rj": "ipca", "mes": 2, "v": 327, "re": [r"^horas paradas"]},
    {"k": "ajudantes", "row": 58, "l": "Ajudantes (5)", "drv": "por mês de uso", "m": "BRL", "rj": "ipca", "mes": 2, "v": 120000, "re": [r"^ajudantes"]},
]
TARIFA_BY_KEY = {t["k"]: t for t in TARIFAS}
TARIFA_BY_ROW = {t["row"]: t for t in TARIFAS}
# Na aba Premissas do MODELO as tarifas estao na coluna C (linhas 11-16 e 30-56); mapa linha -> tarifa
MODELO_PREM_TARIFA = {11: "frete_maritimo_1", 12: "frete_maritimo_2", 13: "bunker", 15: "rod_nf_maior", 30: "frete_aereo",
                      31: "biocombustivel", 32: "capatazias", 33: "taxa_siscomex", 34: "arm_cif_maior_ate10",
                      35: "arm_cif_menor_ate10", 36: "arm_cif_maior_acima10", 37: "arm_cif_menor_acima10", 38: "desembaraco",
                      39: "carta_protesto", 40: "licenca_ncm", 41: "servico_dev", 42: "duimp_catalogo", 43: "flowls", 44: "ttms",
                      45: "in_house", 46: "demurrage", 47: "multa", 48: "rod_nf_menor", 49: "rod_aereo", 50: "escolta",
                      51: "escolta_fixo", 52: "trava", 53: "estadia", 54: "pre_stacking", 55: "horas_paradas", 56: "ajudantes"}
MODELO_PREM_ESCALAR = {6: "volume_total_units", 7: "units_por_conteiner", 8: "pct_modal_aereo", 9: "cambio_usd_brl", 10: "ipca",
                       14: "afrmm", 16: "seguro_apolice_usd_ano", 20: "pct_conteineres_biocombustivel",
                       21: "pct_processos_cif_acima_1m", 22: "pct_processos_armazenagem_acima_10_dias",
                       23: "pct_nf_acima_1m_rodoviario", 24: "pct_conteineres_escolta_armada",
                       25: "pct_conteineres_estadia_veiculo", 26: "pct_conteineres_pre_stacking",
                       27: "pct_conteineres_horas_paradas", 28: "units_por_processo_aereo", 29: "reajuste_in_house"}
CURVA_PADRAO = [1559723, 936905, 1172760, 1459059, 1247703, 1710052, 1787466, 1426489, 1529181, 1503043, 1116546, 1060770]

# Rubricas (13) na ordem da aba de calculo; budget/forecast do ano anterior por rubrica
RUBRICAS: list[dict[str, Any]] = [
    {"k": "frete_maritimo", "l": "Frete marítimo", "re": r"^frete maritimo", "b": 13841520, "f": 10324324.8},
    {"k": "frete_aereo", "l": "Frete aéreo", "re": r"^frete aereo", "b": 413197.16, "f": 2530202.14},
    {"k": "bunker", "l": "Bunker + biocombustível", "re": r"^bunker", "b": 6896052.97, "f": 8735872.16},
    {"k": "capatazias", "l": "Capatazias", "re": r"^capatazia", "b": 1430414.10, "f": 1312622.01},
    {"k": "afrmm", "l": "Marinha Mercante (AFRMM) + Siscomex", "re": r"marinha mercante|afrmm", "b": 2313832.77, "f": 1991396.20},
    {"k": "armazenagem", "l": "Armazenagem", "re": r"^armazenagem", "b": 4109984.12, "f": 5063589.57},
    {"k": "despachante", "l": "Despachante aduaneiro", "re": r"^despachante", "b": 810767.15, "f": 811867.17},
    {"k": "sistemas", "l": "Sistemas & desenvolvimento", "re": r"^sistemas", "b": 404938.31, "f": 364036.63},
    {"k": "in_house", "l": "Equipe In-House", "re": r"in house", "b": 653709.47, "f": 671756.71},
    {"k": "demurrage", "l": "Demurrage", "re": r"^demurrage", "b": 36972, "f": 23099.15},
    {"k": "multa", "l": "Multa", "re": r"^multa", "b": 0, "f": 0},
    {"k": "rodoviario", "l": "Frete rodoviário (total)", "re": r"^frete rodoviario", "b": 11370173.56, "f": 10618384.92},
    {"k": "seguro", "l": "Seguro internacional (apólice em USD)", "re": r"^seguro", "b": 316310.94, "f": 305115.41},
]
RUBRICA_BY_KEY = {r["k"]: r for r in RUBRICAS}
VOLUME_ANTERIOR = {"b": 14810556, "f": 14876089}
# Budget e Forecast do ano anterior MES A MES (Ferramenta de Controle 2026, fechamento de agosto, aba Outlook): por
# rubrica, mais o frete Santos-Extrema (para o rodoviario aparecer dividido em 2), units e conteineres. A soma de cada
# rubrica bate com o anual do Comparativo; se o anual for alterado, o mensal daquela rubrica deixa de valer (n/d).
try:
    ANTERIOR_MENSAL_PADRAO = __import__("json").loads((Path(__file__).resolve().parent / "budget_anterior_padrao.json")
                                                     .read_text(encoding="utf-8"))
except (OSError, ValueError):
    ANTERIOR_MENSAL_PADRAO = {"budget": {}, "forecast": {}}


def default_params(ano: int = 2027) -> dict[str, Any]:
    """Premissas da versao aprovada de 04/11/2026 (MODELO)."""
    return {
        "ano": ano,
        "escalares": {e["k"]: e["v"] for e in ESCALARES},
        "tarifas": {t["k"]: {"base": t["v"], "moeda": t["m"], "reajuste": t["rj"], "pct": 0.0, "mes": t["mes"]} for t in TARIFAS},
        "curva": list(CURVA_PADRAO),
        "ajudantes_uso": [1] * 12,
        "base_volume": 1,
        "anterior": {r["k"]: {"budget": r["b"], "forecast": r["f"]} for r in RUBRICAS},
        "volume_anterior": dict(VOLUME_ANTERIOR),
        "anterior_mensal": copy.deepcopy(ANTERIOR_MENSAL_PADRAO),
    }


def clean_params(p: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Valida e normaliza as premissas (secao 15.1 item 5). Devolve (premissas, erros)."""
    out, errors = default_params(int(p.get("ano") or 2027)), []
    try:
        out["ano"] = max(2000, min(2100, int(p.get("ano") or out["ano"])))
    except (TypeError, ValueError):
        errors.append("Ano inválido.")
    for e in ESCALARES:
        raw = (p.get("escalares") or {}).get(e["k"], e["v"])
        try:
            v = float(raw)
        except (TypeError, ValueError):
            errors.append(f"{e['l']}: valor inválido.")
            continue
        if e["t"] == "pct" and not 0 <= v <= 1:
            errors.append(f"{e['l']}: use um percentual entre 0% e 100%.")
        elif e["t"] == "int" and (v <= 0 or abs(v - round(v)) > 1e-9):
            errors.append(f"{e['l']}: use um número inteiro maior que zero.")
        elif e["k"] == "cambio_usd_brl" and v <= 0:
            errors.append("Câmbio: use um valor maior que zero.")
        elif v < 0:
            errors.append(f"{e['l']}: não pode ser negativo.")
        out["escalares"][e["k"]] = int(round(v)) if e["t"] == "int" else v
    for t in TARIFAS:
        raw = (p.get("tarifas") or {}).get(t["k"]) or {}
        cur = out["tarifas"][t["k"]]
        try:
            base = float(raw.get("base", cur["base"]))
            pct = float(raw.get("pct", 0) or 0)
            mes = int(raw.get("mes", cur["mes"]))
        except (TypeError, ValueError):
            errors.append(f"{t['l']}: valor inválido.")
            continue
        if base < 0:
            errors.append(f"{t['l']}: a tarifa não pode ser negativa.")
        moeda = "USD" if str(raw.get("moeda", cur["moeda"])).upper() == "USD" else "BRL"
        reaj = raw.get("reajuste", cur["reajuste"])
        if reaj not in {"ipca", "inhouse", "nenhum", "fixo"}:
            reaj = cur["reajuste"]
        if not 0 <= mes <= 12:
            errors.append(f"{t['l']}: mês de início entre 1 e 12.")
        if reaj == "fixo" and not -0.5 <= pct <= 1:
            errors.append(f"{t['l']}: reajuste fixo entre -50% e 100%.")
        cur.update(base=base, moeda=moeda, reajuste=reaj, pct=pct if reaj == "fixo" else 0.0, mes=max(0, min(12, mes)))
    curva = p.get("curva") or out["curva"]
    try:
        curva = [max(0.0, float(x)) for x in list(curva)[:12]]
    except (TypeError, ValueError):
        curva = out["curva"]
        errors.append("Curva de recebimento inválida.")
    if len(curva) != 12 or sum(curva) <= 0:
        errors.append("A curva de recebimento precisa de 12 meses com soma maior que zero.")
    else:
        out["curva"] = curva
    uso = p.get("ajudantes_uso") or out["ajudantes_uso"]
    out["ajudantes_uso"] = [1 if str(x) not in {"0", "False", "false", ""} and x else 0 for x in list(uso)[:12]] + [0] * (12 - len(list(uso)[:12]))
    out["base_volume"] = 2 if str(p.get("base_volume")) == "2" else 1
    for r in RUBRICAS:
        raw = (p.get("anterior") or {}).get(r["k"]) or {}
        for key in ("budget", "forecast"):
            try:
                out["anterior"][r["k"]][key] = float(raw.get(key, out["anterior"][r["k"]][key]) or 0)
            except (TypeError, ValueError):
                errors.append(f"{r['l']}: valor de {key} inválido.")
    am = p.get("anterior_mensal")
    if isinstance(am, dict):
        limpo: dict[str, Any] = {"fonte": str(am.get("fonte") or "")[:200]}
        for cen in ("budget", "forecast"):
            limpo[cen] = {}
            for k, arr in (am.get(cen) or {}).items():
                if (k in RUBRICA_BY_KEY or k == "rod_santos") and isinstance(arr, list) and len(arr) == 12:
                    try:
                        limpo[cen][k] = [float(x or 0) for x in arr]
                    except (TypeError, ValueError):
                        pass
            for vk in (f"units_{cen}", f"cntr_{cen}"):
                arr = am.get(vk)
                if isinstance(arr, list) and len(arr) == 12:
                    try:
                        limpo[vk] = [float(x or 0) for x in arr]
                    except (TypeError, ValueError):
                        pass
        out["anterior_mensal"] = limpo
    va = p.get("volume_anterior") or {}
    for key, short in (("budget", "b"), ("forecast", "f")):
        try:
            out["volume_anterior"][short] = float(va.get(short, va.get(key, out["volume_anterior"][short])) or 0)
        except (TypeError, ValueError):
            pass
    return out, errors


# ---------------------------------------------------------------------------
# Motor de calculo (secao 14.3)
# ---------------------------------------------------------------------------
def tarifa_vigente(p: dict[str, Any], k: str, m: int) -> float:
    """Tarifa da linha k no mes m (1-12): base x (1+reajuste a partir do mes de inicio) x cambio (se USD)."""
    t = p["tarifas"][k]
    fx = p["escalares"]["cambio_usd_brl"] if t["moeda"] == "USD" else 1.0
    pct = {"ipca": p["escalares"]["ipca"], "inhouse": p["escalares"]["reajuste_in_house"], "fixo": t.get("pct", 0.0)}.get(t["reajuste"], 0.0)
    return t["base"] * (1 + pct) * fx if m >= t["mes"] else t["base"] * fx


def seguro_mensal(p: dict[str, Any]) -> float:
    return p["escalares"]["seguro_apolice_usd_ano"] / 12 * p["escalares"]["cambio_usd_brl"]


def calcular(params: dict[str, Any]) -> dict[str, Any]:
    p, _ = clean_params(params)
    e = p["escalares"]
    curva = p["curva"]
    soma = sum(curva) or 1
    dist = [c / soma for c in curva]
    units = [curva[i] if p["base_volume"] == 2 else e["volume_total_units"] * dist[i] for i in range(12)]
    aer = [u * e["pct_modal_aereo"] for u in units]
    mar = [u - a for u, a in zip(units, aer)]
    cntr = [xl_round(x / e["units_por_conteiner"]) for x in mar]
    proc = [xl_roundup(a / e["units_por_processo_aereo"]) for a in aer]
    T = lambda k, m: tarifa_vigente(p, k, m)  # noqa: E731
    det: dict[str, list[float]] = {k: [0.0] * 12 for k in (
        "frete_maritimo", "frete_aereo", "bunker", "biocombustivel", "capatazias", "afrmm", "siscomex", "armazenagem",
        "desembaraco", "carta_protesto", "licenca_ncm", "servico_dev", "duimp", "flowls", "ttms", "in_house", "demurrage",
        "multa", "rod_santos", "rod_aereo", "escolta", "trava", "estadia", "pre_stacking", "horas_paradas", "ajudantes", "seguro")}
    pc, p10, pnf = e["pct_processos_cif_acima_1m"], e["pct_processos_armazenagem_acima_10_dias"], e["pct_nf_acima_1m_rodoviario"]
    mes2 = p["tarifas"]["frete_maritimo_2"]["mes"]
    for i in range(12):
        m = i + 1
        c = cntr[i]
        det["frete_maritimo"][i] = c * (T("frete_maritimo_2", m) if m >= mes2 else T("frete_maritimo_1", m))
        det["frete_aereo"][i] = aer[i] * T("frete_aereo", m)
        det["bunker"][i] = c * T("bunker", m)
        det["biocombustivel"][i] = c * e["pct_conteineres_biocombustivel"] * T("biocombustivel", m)
        det["capatazias"][i] = c * T("capatazias", m)
        det["afrmm"][i] = (det["frete_maritimo"][i] + det["bunker"][i] + det["capatazias"][i]) * e["afrmm"]
        det["siscomex"][i] = units[i] * T("taxa_siscomex", m)
        det["armazenagem"][i] = c * (pc * p10 * T("arm_cif_maior_acima10", m) + pc * (1 - p10) * T("arm_cif_maior_ate10", m)
                                     + (1 - pc) * p10 * T("arm_cif_menor_acima10", m) + (1 - pc) * (1 - p10) * T("arm_cif_menor_ate10", m))
        det["desembaraco"][i] = (c + proc[i]) * T("desembaraco", m)
        det["carta_protesto"][i] = T("carta_protesto", m)
        det["licenca_ncm"][i] = T("licenca_ncm", m)
        det["servico_dev"][i] = T("servico_dev", m)
        det["duimp"][i] = T("duimp_catalogo", m)
        det["flowls"][i] = T("flowls", m)
        det["ttms"][i] = T("ttms", m)
        det["in_house"][i] = T("in_house", m)
        det["demurrage"][i] = T("demurrage", m)
        det["multa"][i] = units[i] * T("multa", m)
        det["rod_santos"][i] = c * (pnf * T("rod_nf_maior", m) + (1 - pnf) * T("rod_nf_menor", m))
        det["rod_aereo"][i] = proc[i] * T("rod_aereo", m)
        det["escolta"][i] = c * e["pct_conteineres_escolta_armada"] * T("escolta", m) + T("escolta_fixo", m)
        det["trava"][i] = T("trava", m)
        det["estadia"][i] = c * e["pct_conteineres_estadia_veiculo"] * T("estadia", m)
        det["pre_stacking"][i] = c * e["pct_conteineres_pre_stacking"] * T("pre_stacking", m)
        det["horas_paradas"][i] = c * e["pct_conteineres_horas_paradas"] * T("horas_paradas", m)
        det["ajudantes"][i] = p["ajudantes_uso"][i] * T("ajudantes", m)
        det["seguro"][i] = seguro_mensal(p)
    soma_linhas = lambda *ks: [sum(det[k][i] for k in ks) for i in range(12)]  # noqa: E731
    rub = {
        "frete_maritimo": det["frete_maritimo"], "frete_aereo": det["frete_aereo"],
        "bunker": soma_linhas("bunker", "biocombustivel"), "capatazias": det["capatazias"],
        "afrmm": soma_linhas("afrmm", "siscomex"), "armazenagem": det["armazenagem"],
        "despachante": soma_linhas("desembaraco", "carta_protesto"),
        "sistemas": soma_linhas("licenca_ncm", "servico_dev", "duimp", "flowls", "ttms"), "in_house": det["in_house"],
        "demurrage": det["demurrage"], "multa": det["multa"],
        "rodoviario": soma_linhas("rod_santos", "rod_aereo", "escolta", "trava", "estadia", "pre_stacking", "horas_paradas", "ajudantes"),
        "seguro": det["seguro"],
    }
    total = [sum(rub[k][i] for k in rub) for i in range(12)]
    return montar_resultado(p, units, cntr, proc, aer, det, rub, total)


DETALHE_ROTULOS = {
    "bunker": [("bunker", "Bunker"), ("biocombustivel", "Biocombustível")],
    "afrmm": [("afrmm", "AFRMM"), ("siscomex", "Taxa Siscomex")],
    "despachante": [("desembaraco", "Desembaraço (contêineres + processos aéreos)"), ("carta_protesto", "Carta protesto")],
    "sistemas": [("licenca_ncm", "Licença de Importação / NCM"), ("servico_dev", "Serviço de desenvolvimento"),
                 ("duimp", "DUIMP"), ("flowls", "Flowls"), ("ttms", "TTMS")],
    "rodoviario": [("rod_santos", "Santos – Extrema"), ("ajudantes", "Ajudantes"), ("escolta", "Escolta armada"),
                   ("trava", "Trava Ciltronics"), ("estadia", "Estadia de veículo"), ("pre_stacking", "Pré-stacking / Depot"),
                   ("horas_paradas", "Horas paradas"), ("rod_aereo", "Aéreo GRU/VCP")],
}


def _fmt_mi(v: float, casas: int = 1) -> str:
    return f"{v / 1e6:,.{casas}f}".replace(",", "#").replace(".", ",").replace("#", ".")


def _br(v: float, casas: int = 2) -> str:
    return f"{v:,.{casas}f}".replace(",", "#").replace(".", ",").replace("#", ".")


def montar_resultado(p, units, cntr, proc, aer, det, rub, total) -> dict[str, Any]:
    ano = p["ano"]
    e = p["escalares"]
    tot = sum(total)
    h1 = sum(total[:6])
    soma = lambda v: sum(v)  # noqa: E731
    # Linhas do Resumo Mensal: rubricas com o rodoviario dividido em 2 (secao 13.2); demurrage/multa so se tiverem valor
    linhas = []
    for r in RUBRICAS:
        if r["k"] == "rodoviario":
            santos = det["rod_santos"]
            adic = [rub["rodoviario"][i] - santos[i] for i in range(12)]
            linhas.append({"k": "rod_santos", "l": "Rodoviário – frete Santos/Extrema", "v": santos})
            linhas.append({"k": "rod_adicionais", "l": "Rodoviário – ajudantes, escolta e adicionais", "v": adic})
        elif r["k"] in {"demurrage", "multa"} and abs(soma(rub[r["k"]])) < 0.5:
            continue
        else:
            nome = {"in_house": "Equipe In-House", "despachante": "Despachante aduaneiro"}.get(r["k"], r["l"])
            linhas.append({"k": r["k"], "l": nome, "v": rub[r["k"]]})
    for ln in linhas:
        ln["total"] = soma(ln["v"])
        ln["h1"] = soma(ln["v"][:6])
        ln["h2"] = ln["total"] - ln["h1"]
        ln["pct"] = ln["total"] / tot if tot else 0
    linhas.sort(key=lambda x: -x["total"])
    # Rubricas abertas (secao 5.4): nivel 0 + detalhes (nivel 1)
    abertas = []
    for r in RUBRICAS:
        v = rub[r["k"]]
        t = soma(v)
        item = {"k": r["k"], "l": r["l"], "v": v, "total": t, "h1": soma(v[:6]), "pct": t / tot if tot else 0, "det": []}
        for dk, dl in DETALHE_ROTULOS.get(r["k"], []):
            dv = det[dk]
            dt = soma(dv)
            item["det"].append({"k": dk, "l": dl, "v": dv, "total": dt, "h1": soma(dv[:6]), "pct": dt / tot if tot else 0,
                                "pct_rubrica": dt / t if t else 0})
        abertas.append(item)
    units_tot, cntr_tot = soma(units), soma(cntr)
    # Comparativo com o ano anterior (nivel rubrica)
    comp = []
    for r in RUBRICAS:
        v27 = soma(rub[r["k"]])
        b, f = p["anterior"][r["k"]]["budget"], p["anterior"][r["k"]]["forecast"]
        comp.append({"k": r["k"], "l": r["l"], "atual": v27, "budget": b, "forecast": f, "var_f": v27 - f,
                     "var_f_pct": v27 / f - 1 if f else 0, "var_b": v27 - b, "var_b_pct": v27 / b - 1 if b else 0,
                     "explica": _explica(r["k"], p, rub, det)})
    comp.sort(key=lambda x: -x["atual"])
    tb, tf = sum(c["budget"] for c in comp), sum(c["forecast"] for c in comp)
    vb, vf = p["volume_anterior"]["b"], p["volume_anterior"]["f"]
    cpu = tot / units_tot if units_tot else 0
    cpu_b, cpu_f = (tb / vb if vb else 0), (tf / vf if vf else 0)
    seg_ano = soma(det["seguro"])
    kpi = {"total": tot, "h1": h1, "h2": tot - h1, "pct_h1": h1 / tot if tot else 0, "units": units_tot, "conteineres": cntr_tot,
           "processos_aereos": soma(proc), "custo_unit": cpu, "custo_cntr": tot / cntr_tot if cntr_tot else 0,
           "budget_anterior": tb, "forecast_anterior": tf, "var_forecast": tot - tf, "var_forecast_pct": tot / tf - 1 if tf else 0,
           "var_budget": tot - tb, "var_budget_pct": tot / tb - 1 if tb else 0, "custo_unit_budget": cpu_b,
           "custo_unit_forecast": cpu_f, "var_cpu_forecast_pct": cpu / cpu_f - 1 if cpu_f else 0,
           "seguro_brl_ano": seg_ano, "seguro_usd_ano": e["seguro_apolice_usd_ano"], "volume_budget": vb, "volume_forecast": vf}
    mensal = {"rotulos": [f"{m}/{str(ano)[2:]}" for m in MESES], "total": total, "units": units, "conteineres": cntr,
              "processos_aereos": proc, "units_aereo": aer,
              "custo_unit": [total[i] / units[i] if units[i] else 0 for i in range(12)],
              "custo_cntr": [total[i] / cntr[i] if cntr[i] else 0 for i in range(12)]}
    graficos = _graficos(p, linhas, comp, kpi, mensal)
    cenarios = {"budget": _cenario_anterior(p, "budget", linhas), "forecast": _cenario_anterior(p, "forecast", linhas)}
    return {"ano": ano, "kpi": kpi, "linhas": linhas, "rubricas": abertas, "comparativo": comp, "mensal": mensal, "cenarios": cenarios,
            "graficos": graficos, "tarifas_vigentes": {t["k"]: [tarifa_vigente(p, t["k"], m) for m in range(1, 13)] for t in TARIFAS},
            "seguro_mensal_brl": seguro_mensal(p)}


def _cenario_anterior(p: dict[str, Any], cen: str, linhas: list[dict[str, Any]]) -> dict[str, Any]:
    """Budget ou Forecast do ano anterior mes a mes, nas mesmas linhas do Resumo Mensal (rodoviario dividido em 2).
    Linha sem mensal valido (soma diferente do anual) fica com v=None: a tela mostra so o anual."""
    am = (p.get("anterior_mensal") or {}).get(cen) or {}
    anual = {k: p["anterior"][k][cen] for k in RUBRICA_BY_KEY}
    ok = {k: isinstance(am.get(k), list) and abs(sum(am[k]) - anual[k]) <= 1.0 for k in RUBRICA_BY_KEY}
    tot_anual = sum(anual.values())
    out = []
    keys = [ln["k"] for ln in linhas] + [k for k in ("demurrage", "multa") if k not in {ln["k"] for ln in linhas} and abs(anual[k]) >= 0.5]
    nomes = {ln["k"]: ln["l"] for ln in linhas}
    for k in keys:
        if k in {"rod_santos", "rod_adicionais"}:
            base_ok = ok["rodoviario"] and isinstance(am.get("rod_santos"), list)
            santos = am.get("rod_santos") if base_ok else None
            if k == "rod_santos":
                v = santos
                total = sum(santos) if santos else None
            else:
                v = [am["rodoviario"][i] - santos[i] for i in range(12)] if base_ok else None
                total = sum(v) if v else None
            if total is None and k == "rod_santos":
                total = None
        else:
            v = am[k] if ok.get(k) else None
            total = anual.get(k)
        nome = nomes.get(k) or RUBRICA_BY_KEY[k]["l"]
        out.append({"k": k, "l": nome, "v": v, "total": total if total is not None else (anual["rodoviario"] if k == "rod_santos" and not v else None),
                    "h1": sum(v[:6]) if v else None})
    # rodoviario sem mensal: uma linha so com o anual (nao rateia)
    if not (ok["rodoviario"] and isinstance(am.get("rod_santos"), list)):
        out = [x for x in out if x["k"] not in {"rod_santos", "rod_adicionais"}]
        out.append({"k": "rodoviario", "l": "Frete rodoviário (total)", "v": None, "total": anual["rodoviario"], "h1": None})
    for x in out:
        x["pct"] = (x["total"] / tot_anual) if (x["total"] is not None and tot_anual) else None
    todos = all(ok.values())
    total = [sum(am[k][i] for k in RUBRICA_BY_KEY) for i in range(12)] if todos else None
    units = am.get(f"units_{cen}") if isinstance(p.get("anterior_mensal"), dict) else None
    units = (p["anterior_mensal"].get(f"units_{cen}") if isinstance(p.get("anterior_mensal"), dict) else None)
    vol_anual = p["volume_anterior"]["b" if cen == "budget" else "f"]
    if not (isinstance(units, list) and abs(sum(units) - vol_anual) <= 1.0):
        units = None
    cntr = p["anterior_mensal"].get(f"cntr_{cen}") if isinstance(p.get("anterior_mensal"), dict) else None
    return {"linhas": out, "total": total, "total_anual": tot_anual, "h1": sum(total[:6]) if total else None,
            "units": units, "units_anual": vol_anual, "conteineres": cntr if isinstance(cntr, list) else None,
            "custo_unit": [total[i] / units[i] if (total and units and units[i]) else 0 for i in range(12)] if (total and units) else None,
            "mensal_completo": todos}


def _explica(k: str, p: dict[str, Any], rub: dict[str, list[float]], det: dict[str, list[float]]) -> str:
    e, t = p["escalares"], p["tarifas"]
    mes2 = t["frete_maritimo_2"]["mes"]
    aj = sum(det["ajudantes"])
    textos = {
        "frete_maritimo": f"2ª tarifa marítima (USD {_br(t['frete_maritimo_2']['base'], 0)}/cntr) vale a partir de {MESES[max(1, min(12, mes2)) - 1].lower()}/{str(p['ano'])[2:]}.",
        "bunker": f"Bunker de USD {_br(t['bunker']['base'], 0)}/cntr; {_br(e['pct_conteineres_biocombustivel'] * 100, 0)}% dos contêineres com biocombustível.",
        "rodoviario": f"Mais contêineres, reajuste pelo IPCA e ajudantes (R$ {_fmt_mi(aj)} mi/ano).",
        "afrmm": f"AFRMM ({_br(e['afrmm'] * 100, 0)}%) acompanha o frete e o bunker.",
        "armazenagem": ("Faixa acima de 10 dias sem tarifa (pendente)." if t["arm_cif_maior_acima10"]["base"] == 0
                        or t["arm_cif_menor_acima10"]["base"] == 0 else "Inclui a faixa acima de 10 dias."),
        "capatazias": "Mais contêineres e tarifa reajustada pelo IPCA.",
        "despachante": "Acompanha o número de processos.",
        "in_house": f"Dissídio de {_br(e['reajuste_in_house'] * 100, 0)}% a partir de {MESES[max(1, min(12, t['in_house']['mes'])) - 1].lower()}/{str(p['ano'])[2:]}.",
        "frete_aereo": f"Modal aéreo com {_br(e['pct_modal_aereo'] * 100, 2)}% das units.",
        "sistemas": "Contratos fixos com reajuste.",
        "seguro": f"Apólice de USD {_br(e['seguro_apolice_usd_ano'])}/ano × câmbio R$ {_br(e['cambio_usd_brl'])} = R$ {_br(sum(rub['seguro']) / 1000, 1)} mil/ano.",
        "demurrage": "Sem provisão." if sum(rub["demurrage"]) == 0 else "Provisão mensal fixa.",
        "multa": "Sem previsão." if sum(rub["multa"]) == 0 else "Provisão por unit.",
    }
    return textos.get(k, "")


def _graficos(p, linhas, comp, kpi, mensal) -> dict[str, Any]:
    tot = kpi["total"] or 1
    h1, h2 = kpi["h1"], kpi["h2"]
    t2 = p["tarifas"]["frete_maritimo_2"]
    mes2 = max(1, min(12, t2["mes"]))
    by = {ln["k"]: ln for ln in linhas}
    top3 = sum(by.get(k, {}).get("total", 0) for k in ("frete_maritimo", "bunker", "rod_santos"))
    # Variacao vs forecast: rubricas com |var| >= R$ 200 mil e o resto em "Demais (N)"
    grandes = [c for c in comp if abs(c["var_f"]) >= 200000]
    pequenas = [c for c in comp if abs(c["var_f"]) < 200000]
    variacao = [{"l": c["l"], "v": c["var_f"]} for c in grandes]
    if pequenas:
        variacao.append({"l": f"Demais ({len(pequenas)} rubricas)", "v": sum(c["var_f"] for c in pequenas)})
    variacao.sort(key=lambda x: -x["v"])
    curto = {"rodoviario": "Rodoviário", "frete_maritimo": "Marítimo", "bunker": "Bunker", "afrmm": "AFRMM",
             "armazenagem": "Armazenagem", "capatazias": "Capatazias", "despachante": "Despachante", "in_house": "In-House",
             "frete_aereo": "Aéreo", "sistemas": "Sistemas", "seguro": "Seguro", "demurrage": "Demurrage", "multa": "Multa"}
    top5 = comp[:5]
    resto = comp[5:]
    comparacao = [{"l": curto[c["k"]], "atual": c["atual"], "budget": c["budget"], "forecast": c["forecast"]} for c in top5]
    if resto:
        comparacao.append({"l": "Demais", "atual": sum(c["atual"] for c in resto), "budget": sum(c["budget"] for c in resto),
                           "forecast": sum(c["forecast"] for c in resto)})
    difs = sorted(comparacao, key=lambda c: c["atual"] - c["forecast"])
    altas = [c for c in reversed(difs) if c["atual"] - c["forecast"] > 0][:2]
    queda = difs[0] if difs and difs[0]["atual"] - difs[0]["forecast"] < 0 else None
    alta_txt = " e ".join([altas[0]["l"]] + [a["l"].lower() for a in altas[1:]]) if altas else "Nenhuma rubrica"
    ref_cpu = kpi["custo_unit_budget"]
    cpu_h1 = h1 / sum(mensal["units"][:6]) if sum(mensal["units"][:6]) else 0
    cpu_h2 = h2 / sum(mensal["units"][6:]) if sum(mensal["units"][6:]) else 0
    sinal = lambda v: "+" if v >= 0 else "-"  # noqa: E731
    return {
        "mensal": {"titulo": f"Custo mensal {p['ano']}",
                   "sub": (f"H2 custa {_br(abs(h2 / h1 - 1) * 100 if h1 else 0, 0)}% {'mais' if h2 >= h1 else 'menos'} que H1: a 2ª tarifa de "
                           f"frete marítimo (USD {_br(t2['base'], 0)}/cntr) vale de {MESES_LONGOS[mes2 - 1]} a dezembro")},
        "composicao": {"titulo": f"Onde está o custo de {p['ano']}",
                       "sub": f"Marítimo, bunker e Santos/Extrema somam {_br(top3 / tot * 100, 0)}% do total",
                       "itens": [{"l": ln["l"].replace(" (apólice em USD)", ""), "v": ln["total"], "pct": ln["pct"],
                                  "usd": kpi["seguro_usd_ano"] if ln["k"] == "seguro" else None} for ln in linhas]},
        "variacao": {"titulo": f"{p['ano']} × Forecast {p['ano'] - 1}: {sinal(kpi['var_forecast'])}R$ {_fmt_mi(abs(kpi['var_forecast']))} mi "
                               f"({sinal(kpi['var_forecast_pct'])}{_br(abs(kpi['var_forecast_pct']) * 100, 0)}%)",
                     "sub": "O que sobe e o que cai, por rubrica", "itens": variacao},
        "comparacao": {"titulo": f"{p['ano']} × {p['ano'] - 1} por rubrica",
                       "sub": f"{alta_txt} {'puxam' if len(altas) > 1 else 'puxa'} a alta" + (f"; {queda['l'].lower()} cai" if queda else ""),
                       "itens": comparacao},
        "custo_unit": {"titulo": "Custo por unit mês a mês",
                       "sub": f"Média {p['ano']} de R$ {_br(kpi['custo_unit'])}; {'sobe' if cpu_h2 > cpu_h1 else 'cai'} no H2",
                       "ref": ref_cpu, "ref_rotulo": f"Média Budget {p['ano'] - 1} (R$ {_br(ref_cpu)})"},
    }


# ---------------------------------------------------------------------------
# Referencias de mercado (secao 7) e alertas de premissa
# ---------------------------------------------------------------------------
BENCHMARKS_PADRAO = {
    "fx": {"v": 5.22, "rotulo": "Focus/BCB 19/10/2026: câmbio fim de 2027 R$ 5,22",
           "url": "https://www.infomoney.com.br/economia/boletim-focus-projecoes-19102026/"},
    "ipca": {"v": 0.0432, "rotulo": "Focus/BCB 19/10/2026: IPCA 2027 4,32%",
             "url": "https://www.infomoney.com.br/economia/boletim-focus-projecoes-19102026/"},
    "inctl": {"v": 0.0684, "rotulo": "NTC&Logística: INCT-L +6,84% em 12 meses até set/26",
              "url": "https://www.portalntc.org.br/relatorio-mensal-do-indice-nacional-de-custos-do-transporte-inctf-e-inctl-setembro-26/"},
    "afrmm": {"v": 0.08, "rotulo": "Lei 10.893/2004, art. 6º: 8% no longo curso",
              "url": "https://www.planalto.gov.br/CCiVil_03/_Ato2004-2006/2004/Lei/L10.893.htm"},
    "siscomex_limite": {"v": 1500, "rotulo": "Limite de plausibilidade: R$ 1.500 por DI (Portaria ME 4.131/2021: R$ 115,67/DI + adições)",
                        "url": "https://www.aasp.org.br/?p=33557"},
}


def alertas_premissas(p: dict[str, Any], res: dict[str, Any], bench: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Alertas sobre as premissas da versao (valem para qualquer origem)."""
    b = {**BENCHMARKS_PADRAO, **(bench or {})}
    e, t = p["escalares"], p["tarifas"]
    out = []

    def add(sev, cod, titulo, detalhe, acao, impacto=None, onde="Premissas"):
        out.append({"sev": sev, "cod": cod, "onde": onde, "titulo": titulo, "detalhe": detalhe, "acao": acao, "impacto": impacto})

    zer = [TARIFA_BY_KEY[k]["l"] for k in ("arm_cif_maior_acima10", "arm_cif_menor_acima10") if t[k]["base"] == 0]
    if zer:
        arm = sum(next(r for r in res["rubricas"] if r["k"] == "armazenagem")["v"])
        p10 = e["pct_processos_armazenagem_acima_10_dias"]
        piso = arm / (1 - p10) - arm if p10 < 1 else None
        add("Alta", "R04", "Armazenagem acima de 10 dias sem tarifa",
            f"{'; '.join(zer)} está(ão) zerada(s), mas {_br(p10 * 100, 0)}% dos processos ficam mais de 10 dias.",
            "Informar a tarifa do terminal para a faixa acima de 10 dias.", piso)
    for k in ("demurrage", "multa"):
        if t[k]["base"] == 0:
            add("Baixa", "R05", f"Sem provisão: {TARIFA_BY_KEY[k]['l']}", "Orçamento zero para um custo que costuma ocorrer.",
                "Provisionar pela média histórica ou criar um cenário de estresse.")
    fx = b["fx"]["v"]
    if e["cambio_usd_brl"] < fx - 0.02:
        usd = sum(sum(r["v"]) for r in res["rubricas"] if r["k"] in {"frete_maritimo", "bunker"})
        add("Média", "M01", "Câmbio abaixo do mercado", f"Premissa R$ {_br(e['cambio_usd_brl'])} × {b['fx']['rotulo']}.",
            "Usar a mediana Focus mais recente ou um cenário de estresse. O impacto é para cada +R$ 0,10, já com AFRMM.",
            usd / e["cambio_usd_brl"] * 0.1 * (1 + e["afrmm"]))
    if abs(e["afrmm"] - b["afrmm"]["v"]) > 1e-9:
        add("Alta", "M02", "AFRMM diferente da lei", f"Premissa {_br(e['afrmm'] * 100)}% × 8% no longo curso.", "Ajustar para 8%.")
    rod = [t[k] for k in ("rod_nf_maior", "rod_nf_menor", "rod_aereo", "escolta", "estadia", "pre_stacking", "horas_paradas")]
    reaj = [e["ipca"] if x["reajuste"] == "ipca" else x.get("pct", 0) if x["reajuste"] == "fixo" else 0 for x in rod]
    media = sum(reaj) / len(reaj)
    if media < b["inctl"]["v"] - 1e-9:
        sub = sum(sum(r["v"]) for r in res["rubricas"] if r["k"] == "rodoviario")
        add("Média", "M03", "Reajuste rodoviário abaixo do custo do setor",
            f"Média aplicada {_br(media * 100)}% × {b['inctl']['rotulo']}.",
            "Usar o INCT-L ou um cenário de recomposição para o rodoviário (impacto aproximado).",
            sub * 0.85 * (b["inctl"]["v"] - media) / (1 + media) * 11 / 12)
    procs = res["kpi"]["conteineres"] + res["kpi"]["processos_aereos"]
    if procs:
        por_di = tarifa_vigente(p, "taxa_siscomex", 12) * res["kpi"]["units"] / procs
        if por_di > b["siscomex_limite"]["v"]:
            add("Alta", "M04", "Siscomex implausível por DI", f"Equivale a R$ {_br(por_di, 0)} por DI/processo.",
                "Revisar a tarifa por unit da taxa Siscomex.")
    if t["bunker"]["base"] > t["frete_maritimo_1"]["base"]:
        add("Média", "R25", "Bunker maior que o frete base",
            f"Bunker USD {_br(t['bunker']['base'], 0)}/cntr × 1ª tarifa de frete USD {_br(t['frete_maritimo_1']['base'], 0)}/cntr.",
            "Confirmar se o frete é all-in (risco de dupla contagem).")
    if p["base_volume"] == 1 and abs(sum(p["curva"]) - e["volume_total_units"]) > 0.5:
        add("Média", "R15", "Volume total diferente da curva de recebimento",
            f"Volume informado {_br(e['volume_total_units'], 0)} × soma da curva {_br(sum(p['curva']), 0)} units. "
            "O cálculo usa o volume total distribuído pela curva.", "Definir uma fonte única de volume.")
    ordem = {"Alta": 0, "Média": 1, "Baixa": 2}
    out.sort(key=lambda a: (ordem[a["sev"]], -abs(a["impacto"] or 0)))
    return out


# ---------------------------------------------------------------------------
# Importacao de planilhas
# ---------------------------------------------------------------------------
def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and math.isfinite(v):
        return float(v)
    return None


def _cell_ref(ws, row: int, col: int) -> str:
    from openpyxl.utils import get_column_letter
    return f"{ws.title}!{get_column_letter(col)}{row}"


def importar(conteudo: bytes, nome_arquivo: str, base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Le a planilha e devolve a previa: formato, premissas achadas (com a celula de origem), o que ficou com o valor
    de referencia, os alertas de auditoria da propria planilha e o total que ela informa (para conferir o calculo)."""
    from openpyxl import load_workbook
    wf = load_workbook(io.BytesIO(conteudo), data_only=False)
    wv = load_workbook(io.BytesIO(conteudo), data_only=True)
    nomes = wf.sheetnames
    base_p = copy.deepcopy(base) if base else default_params()
    if {"Premissas", "Premissas Detalhadas", "Cálculo Mensal"} <= set(nomes):
        out = _importar_modelo(wf, wv, base_p)
    elif any(norm(n).startswith("premissas") for n in nomes) and any(re.match(r"^orcamento \d{4}", norm(n)) for n in nomes):
        out = _importar_fisia(wf, wv, base_p)
    else:
        out = _importar_generico(wf, wv, base_p)
    p, erros = clean_params(out["params"])
    out["params"] = p
    out["erros_validacao"] = erros
    res = calcular(p)
    out["resultado_kpi"] = res["kpi"]
    total_planilha = out.get("total_planilha")
    if total_planilha:
        dif = res["kpi"]["total"] - total_planilha
        out["reproducao"] = {"total_planilha": total_planilha, "total_calculado": res["kpi"]["total"], "diferenca": dif,
                             "ok": abs(dif) <= max(1.0, abs(total_planilha) * 0.001)}
        if not out["reproducao"]["ok"]:
            out["alertas"].append({"sev": "Média", "cod": "C01", "onde": "Cálculo",
                                   "titulo": "O cálculo no modelo difere do total da planilha",
                                   "detalhe": f"Planilha R$ {_br(total_planilha, 0)} × modelo R$ {_br(res['kpi']['total'], 0)} "
                                              f"(diferença R$ {_br(dif, 0)}). Diferenças vêm de fórmulas da planilha que não seguem o "
                                              "modelo (valores colados, linhas sem rótulo) ou de premissas não encontradas.",
                                   "acao": "Conferir os alertas acima e as premissas marcadas como 'valor de referência'.",
                                   "impacto": dif})
    out["alertas"] += alertas_premissas(p, res)
    ordem = {"Alta": 0, "Média": 1, "Baixa": 2}
    out["alertas"].sort(key=lambda a: (ordem.get(a["sev"], 3), -abs(a.get("impacto") or 0)))
    return out


def _resultado_vazio(formato: str, base_p: dict[str, Any]) -> dict[str, Any]:
    return {"formato": formato, "params": base_p, "origem": {}, "nao_encontrados": [], "alertas": [], "total_planilha": None,
            "abas": []}


def _origem(out, chave, ws, row, col, valor, obs=""):
    out["origem"][chave] = {"celula": _cell_ref(ws, row, col), "valor": valor, **({"obs": obs} if obs else {})}


def _importar_modelo(wf, wv, base_p) -> dict[str, Any]:
    out = _resultado_vazio("modelo", base_p)
    p = out["params"]
    P, Pv = wf["Premissas"], wv["Premissas"]
    for r, k in MODELO_PREM_ESCALAR.items():
        v = _num(Pv.cell(r, 3).value)
        if v is not None:
            p["escalares"][k] = v
            _origem(out, k, P, r, 3, v)
        else:
            out["nao_encontrados"].append(k)
    for r, k in MODELO_PREM_TARIFA.items():
        v = _num(Pv.cell(r, 3).value)
        if v is not None:
            p["tarifas"][k]["base"] = v
            _origem(out, "tarifa:" + k, P, r, 3, v)
        else:
            out["nao_encontrados"].append("tarifa:" + k)
    curva = [_num(Pv.cell(r, 3).value) for r in range(65, 77)]
    if all(c is not None for c in curva):
        p["curva"] = curva
        out["origem"]["curva"] = {"celula": "Premissas!C65:C76", "valor": sum(curva)}
    D, Dv = wf["Premissas Detalhadas"], wv["Premissas Detalhadas"]
    for t in TARIFAS:
        _atributos_tarifa(p, t["k"], D, Dv, t["row"], 5, 6, 7, ipca_cell="C13", inhouse_cell="C14")
    bv = _num(Dv["C8"].value)
    p["base_volume"] = 2 if bv == 2 else 1
    C, Cv = wf["Cálculo Mensal"], wv["Cálculo Mensal"]
    uso = [_num(Cv.cell(18, c).value) for c in range(3, 15)]
    if all(u is not None for u in uso):
        p["ajudantes_uso"] = [1 if u else 0 for u in uso]
    total = _num(Cv["O62"].value)
    out["total_planilha"] = total
    _anterior_comparativo(wf, wv, p, out)
    _anterior_mensal_modelo(Cv, p, out)
    return out


def _anterior_mensal_modelo(Cv, p, out) -> None:
    """Le o bloco Budget/Forecast mes a mes da aba Calculo Mensal (MODELO com filtro no Resumo Mensal)."""
    if not str(Cv.cell(BLOCO_BUDGET, 2).value or "").strip():
        return
    am: dict[str, Any] = {"fonte": "Planilha MODELO (aba Cálculo Mensal, bloco do ano anterior)", "budget": {}, "forecast": {}}
    for base, cen in ((BLOCO_BUDGET, "budget"), (BLOCO_FORECAST, "forecast")):
        linhas = {}
        for r in range(base, base + 13):
            keys = _linha_por_rotulo(Cv.cell(r, 2).value)
            if keys:
                linhas[tuple(keys)] = [(_num(Cv.cell(r, c).value) or 0.0) for c in range(3, 15)]
        if not any(sum(v) for v in linhas.values()):
            return
        for keys, v in linhas.items():
            if keys == ("rod_santos",) or keys == ("rod_adicionais",):
                continue
            am[cen][keys[0]] = v
            if keys == ("demurrage", "multa"):
                am[cen]["multa"] = [0.0] * 12
        santos, adic = linhas.get(("rod_santos",)), linhas.get(("rod_adicionais",))
        if santos and adic:
            am[cen]["rod_santos"] = santos
            am[cen]["rodoviario"] = [santos[i] + adic[i] for i in range(12)]
    for r, key in ((102, "units_budget"), (103, "cntr_budget"), (104, "units_forecast"), (105, "cntr_forecast")):
        am[key] = [(_num(Cv.cell(r, c).value) or 0.0) for c in range(3, 15)]
    p["anterior_mensal"] = am
    out["origem"]["anterior_mensal"] = {"celula": "Cálculo Mensal!C72:N105", "valor": sum(sum(v) for v in am["budget"].values() if v)}


def _atributos_tarifa(p, k, ws, wsv, row, c_moeda, c_reaj, c_mes, ipca_cell="", inhouse_cell="", ipca_val=None, inhouse_val=None,
                      out=None):
    moeda = str(wsv.cell(row, c_moeda).value or "").strip().upper()
    if moeda in {"USD", "BRL"}:
        p["tarifas"][k]["moeda"] = moeda
    f = ws.cell(row, c_reaj).value
    v = _num(wsv.cell(row, c_reaj).value)
    reaj, pct = None, 0.0
    if isinstance(f, str) and f.startswith("="):
        ref = f.replace("$", "")
        if ipca_cell and ipca_cell in ref:
            reaj = "ipca"
        elif inhouse_cell and inhouse_cell in ref:
            reaj = "inhouse"
    if reaj is None and v is not None:
        if v == 0:
            reaj = "nenhum"
        elif ipca_val is not None and abs(v - ipca_val) < 1e-9:
            reaj = "ipca"
            if out is not None:
                out.setdefault("_ipca_digitado", []).append(_cell_ref(ws, row, c_reaj))
        elif inhouse_val is not None and abs(v - inhouse_val) < 1e-9:
            reaj = "inhouse"
        else:
            reaj, pct = "fixo", v
    if reaj:
        p["tarifas"][k]["reajuste"] = reaj
        p["tarifas"][k]["pct"] = pct
    mes = _num(wsv.cell(row, c_mes).value)
    if mes is not None:
        p["tarifas"][k]["mes"] = int(mes)


def _anterior_comparativo(wf, wv, p, out):
    if "Comparativo 2026" not in wf.sheetnames and not any(n.startswith("Comparativo") for n in wf.sheetnames):
        return
    nome = next(n for n in wf.sheetnames if n.startswith("Comparativo"))
    Cv = wv[nome]
    for r in range(6, 40):
        lab = norm(Cv.cell(r, 2).value)
        if not lab:
            continue
        if lab.startswith("volume"):
            for col, key in ((4, "b"), (5, "f")):
                v = _num(Cv.cell(r, col).value)
                if v is not None:
                    p["volume_anterior"][key] = v
            continue
        rub = next((x for x in RUBRICAS if re.search(x["re"], lab)), None)
        if rub:
            for col, key in ((4, "budget"), (5, "forecast")):
                v = _num(Cv.cell(r, col).value)
                if v is not None:
                    p["anterior"][rub["k"]][key] = v
            out["origem"]["anterior:" + rub["k"]] = {"celula": f"{nome}!D{r}:E{r}", "valor": p["anterior"][rub["k"]]["forecast"]}


def _find_label(ws, wsv, padroes: list[str], col_label: int | None = None, max_row: int = 200):
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, max_row)):
        for c in row:
            if col_label and c.column != col_label:
                continue
            if isinstance(c.value, str) and any(re.search(pt, norm(c.value)) for pt in padroes):
                return c.row, c.column
    return None


def _importar_fisia(wf, wv, base_p) -> dict[str, Any]:
    """Planilha de orcamento FISIA (Premissas com tabela de tarifas + Orcamento AAAA + Resumo), com auditoria."""
    out = _resultado_vazio("fisia", base_p)
    p = out["params"]
    nP = next(n for n in wf.sheetnames if norm(n).startswith("premissas"))
    nO = next(n for n in wf.sheetnames if re.match(r"^orcamento \d{4}", norm(n)))
    nR = next((n for n in wf.sheetnames if norm(n).startswith("resumo")), None)
    P, Pv, O, Ov = wf[nP], wv[nP], wf[nO], wv[nO]
    p["ano"] = int(re.search(r"\d{4}", nO).group(0))
    alertas = out["alertas"]

    def add(sev, cod, onde, titulo, detalhe, acao, impacto=None):
        alertas.append({"sev": sev, "cod": cod, "onde": onde, "titulo": titulo, "detalhe": detalhe, "acao": acao, "impacto": impacto})

    # Escalares (rotulo na coluna B, valor na C)
    ipca_ref = inhouse_ref = ""
    for e in ESCALARES:
        if e["k"] == "seguro_apolice_usd_ano":
            continue
        pos = _find_label(P, Pv, e["re"], col_label=2, max_row=27)
        v = _num(Pv.cell(pos[0], 3).value) if pos else None
        if v is None:
            out["nao_encontrados"].append(e["k"])
            continue
        p["escalares"][e["k"]] = v
        _origem(out, e["k"], P, pos[0], 3, v)
        if e["k"] == "ipca":
            ipca_ref = f"C{pos[0]}"
        if e["k"] == "reajuste_in_house":
            inhouse_ref = f"C{pos[0]}"
    # Tabela de tarifas
    head = _find_label(P, Pv, [r"tarifa .*reajuste"], max_row=80)
    linhas_tab = []
    if head:
        hr = head[0]
        cols = {}
        for c in range(1, P.max_column + 1):
            h = norm(P.cell(hr, c).value)
            if h.startswith("driver"):
                cols["drv"] = c
            elif h.startswith("base"):
                cols["base"] = c
            elif h.startswith("moeda"):
                cols["moeda"] = c
            elif h.startswith("reajuste") and "partir" not in h:
                cols["reaj"] = c
            elif "partir do m" in h:
                cols["mes"] = c
            elif re.search(r"tarifa .*reajuste", h):
                cols["eff"] = c
            elif "fonte" in h or "coment" in h:
                cols["com"] = c
        r = hr + 1
        while r <= P.max_row:
            lab = P.cell(r, 2).value
            if isinstance(lab, str) and re.match(r"^\d+\.\s", lab.strip()):
                break
            base = _num(Pv.cell(r, cols.get("base", 4)).value)
            if base is not None or Pv.cell(r, cols.get("drv", 3)).value is not None:
                linhas_tab.append({"r": r, "label": (lab or "").strip() if isinstance(lab, str) else "", "base": base})
            r += 1
        ipca_val, ih_val = p["escalares"]["ipca"], p["escalares"]["reajuste_in_house"]
        usados = set()
        por_posicao = len(linhas_tab) >= len(TARIFAS)
        for i, ln in enumerate(linhas_tab):
            nl = normx(ln["label"])
            tk = None
            if nl:
                for t in TARIFAS:
                    if t["k"] in usados:
                        continue
                    pads = t["re"] or [re.escape(normx(t["l"]))]
                    if any(re.search(pt, nl) for pt in pads) or normx(t["l"]) == nl:
                        tk = t["k"]
                        break
                if tk is None:
                    tk = _tarifa_por_rotulo(nl, usados)
            if tk is None and por_posicao and i < len(TARIFAS) and TARIFAS[i]["k"] not in usados:
                tk = TARIFAS[i]["k"]   # linha sem rotulo: posicao igual a do modelo
            if tk is None:
                if re.search(r"seguro", nl):
                    ln["seguro"] = True
                    _seguro_fisia(P, Pv, ln["r"], cols, p, out)
                continue
            usados.add(tk)
            if ln["base"] is not None:
                p["tarifas"][tk]["base"] = ln["base"]
                _origem(out, "tarifa:" + tk, P, ln["r"], cols.get("base", 4), ln["base"],
                        "" if ln["label"] else "linha sem rótulo, ligada pela posição")
            _atributos_tarifa(p, tk, P, Pv, ln["r"], cols.get("moeda", 5), cols.get("reaj", 6), cols.get("mes", 7),
                              ipca_cell=ipca_ref, inhouse_cell=inhouse_ref, ipca_val=ipca_val, inhouse_val=ih_val, out=out)
            _auditar_tarifa(P, Pv, ln, cols, p, tk, add, nP)
        if not any(ln.get("seguro") for ln in linhas_tab):
            out["nao_encontrados"].append("seguro_apolice_usd_ano")
        for t in TARIFAS:
            if t["k"] not in usados:
                out["nao_encontrados"].append("tarifa:" + t["k"])
    if out.get("_ipca_digitado"):
        cel = out.pop("_ipca_digitado")
        add("Média", "R06", nP, f"IPCA digitado em {len(cel)} linha(s) em vez de link",
            f"Células {', '.join(c.split('!')[1] for c in cel)}. Se o IPCA mudar, elas não acompanham.",
            "No sistema essas tarifas já foram ligadas ao IPCA das premissas.")
    # Curva de recebimento
    rec = _find_label(P, Pv, [r"recebimento mensal"], col_label=2, max_row=P.max_row)
    if rec:
        tc = next((c for c in range(2, P.max_column + 1) if norm(P.cell(rec[0], c).value) == "total"), None)
        curva = []
        for r in range(rec[0] + 1, rec[0] + 13):
            curva.append(_num(Pv.cell(r, tc).value) if tc else None)
        if tc and all(c is not None for c in curva):
            p["curva"] = curva
            out["origem"]["curva"] = {"celula": f"{nP}!{_cell_ref(P, rec[0] + 1, tc).split('!')[1]}:…", "valor": sum(curva)}
    # Orcamento: ajudantes, total e auditoria de somas
    _auditar_orcamento(O, Ov, nO, p, out, add)
    if nR:
        _anterior_resumo(wf[nR], wv[nR], p, out, nR)
    return out


def _tarifa_por_rotulo(nl: str, usados: set[str]) -> str | None:
    regras = [(r"frete maritimo.*(2|jul)", "frete_maritimo_2"), (r"frete maritimo", "frete_maritimo_1"),
              (r"cif maior.*ate 10", "arm_cif_maior_ate10"), (r"cif menor.*ate 10", "arm_cif_menor_ate10"),
              (r"cif maior.*acima", "arm_cif_maior_acima10"), (r"cif menor.*acima", "arm_cif_menor_acima10"),
              (r"santos.*nf maior|nf acima", "rod_nf_maior"), (r"santos.*nf menor|nf abaixo", "rod_nf_menor"),
              (r"santos|extrema", "rod_nf_maior")]
    for pt, k in regras:
        if k not in usados and re.search(pt, nl):
            return k
    return None


def _seguro_fisia(P, Pv, r, cols, p, out):
    base = _num(Pv.cell(r, cols.get("base", 4)).value)
    moeda = str(Pv.cell(r, cols.get("moeda", 5)).value or "BRL").upper()
    if base is None:
        return
    if moeda == "USD":
        p["escalares"]["seguro_apolice_usd_ano"] = base * 12
        _origem(out, "seguro_apolice_usd_ano", P, r, cols.get("base", 4), base * 12, "base mensal × 12")
    else:
        usd = base * 12 / (p["escalares"]["cambio_usd_brl"] or 1)
        p["escalares"]["seguro_apolice_usd_ano"] = usd
        _origem(out, "seguro_apolice_usd_ano", P, r, cols.get("base", 4), usd,
                f"planilha em reais (R$ {_br(base * 12)}/ano), convertido para US$ pelo câmbio")


def _auditar_tarifa(P, Pv, ln, cols, p, tk, add, nP):
    from openpyxl.utils import get_column_letter as L
    r = ln["r"]
    t = p["tarifas"][tk]
    fx = p["escalares"]["cambio_usd_brl"] if t["moeda"] == "USD" else 1
    pct = {"ipca": p["escalares"]["ipca"], "inhouse": p["escalares"]["reajuste_in_house"], "fixo": t["pct"]}.get(t["reajuste"], 0)
    if "eff" in cols:
        f = P.cell(r, cols["eff"]).value
        v = _num(Pv.cell(r, cols["eff"]).value)
        esp = (t["base"] or 0) * (1 + pct) * fx
        if v is not None and not (isinstance(f, str) and f.startswith("=")):
            if abs(v - esp) > max(1e-6, abs(esp) * 1e-6):
                add("Alta", "R01", f"{nP}!{L(cols['eff'])}{r}", f"Tarifa com reajuste colada como número: {ln['label'] or TARIFA_BY_KEY[tk]['l']}",
                    f"Vale {_br(v, 4)}, mas base × (1+reajuste) × câmbio daria {_br(esp, 4)}.",
                    "No sistema vale a regra do modelo (base × reajuste × câmbio).")
            else:
                add("Baixa", "R02", f"{nP}!{L(cols['eff'])}{r}", f"Tarifa sem fórmula: {ln['label'] or TARIFA_BY_KEY[tk]['l']}",
                    "Hoje o número bate, mas não acompanha mudanças.", "No sistema a tarifa é sempre calculada.")
    if not ln["label"] and ln["base"] is not None:
        add("Alta", "R03", f"{nP}!B{r}", f"Linha de tarifa sem rótulo (linha {r})",
            f"Ligada pela posição a '{TARIFA_BY_KEY[tk]['l']}'. Base = {_br(ln['base'] or 0)}.", "Nomear a linha na planilha de origem.")


def _auditar_orcamento(O, Ov, nO, p, out, add):
    hdr, mcols = None, []
    mre = re.compile(r"^(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)[a-z]*/?\s*\d{2,4}$", re.I)
    for r in range(1, min(O.max_row, 40) + 1):
        cs = [c for c in range(1, O.max_column + 1) if isinstance(Ov.cell(r, c).value, str) and mre.match(Ov.cell(r, c).value.strip())]
        if len(cs) >= 12:
            hdr, mcols = r, cs[:12]
            break
    if not hdr:
        add("Média", "R00", nO, "Linha dos meses não encontrada", "Não achei a linha com os 12 meses.", "Conferir a aba de orçamento.")
        return
    lc = mcols[0] - 1
    tcol = next((c for c in range(mcols[11] + 1, O.max_column + 1) if norm(Ov.cell(hdr, c).value).startswith("total")), None)
    rows = [(r, str(Ov.cell(r, lc).value).strip()) for r in range(hdr + 1, O.max_row + 1)
            if isinstance(Ov.cell(r, lc).value, str) and Ov.cell(r, lc).value.strip()]
    serie = lambda r: [(_num(Ov.cell(r, c).value) or 0.0) for c in mcols]  # noqa: E731
    from openpyxl.utils import get_column_letter as L
    if not any(isinstance(O.cell(r, mcols[0]).value, str) and str(O.cell(r, mcols[0]).value).startswith("=")
               and _num(Ov.cell(r, mcols[0]).value) is not None for r, _ in rows):
        add("Alta", "R00", nO, "Planilha sem valores calculados", "As fórmulas não têm valor salvo.", "Abra no Excel, salve e envie de novo.")
    for r, lab in rows:
        if re.search(r"ajudantes.*uso", norm(lab)):
            p["ajudantes_uso"] = [1 if x else 0 for x in serie(r)]
            out["origem"]["ajudantes_uso"] = {"celula": f"{nO}!{L(mcols[0])}{r}:{L(mcols[11])}{r}", "valor": sum(serie(r))}
        if re.match(r"^custo total", norm(lab)):
            out["total_planilha"] = sum(serie(r))
    # Subtotais (SUM das linhas logo abaixo) e linhas digitadas no meio de formulas
    subs = []
    for r, lab in rows:
        f = O.cell(r, mcols[0]).value
        m = re.match(r"^=SUM\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)$", str(f or "").replace("$", ""), re.I)
        if m and int(m.group(2)) > r:
            subs.append((r, lab, int(m.group(2)), int(m.group(4))))
    for r, lab, a, b in subs:
        for c in mcols:
            v = _num(Ov.cell(r, c).value)
            s = sum((_num(Ov.cell(x, c).value) or 0) for x in range(a, b + 1))
            if v is not None and abs(v - s) > 1:
                add("Alta", "R08", f"{nO}!{L(c)}{r}", f"Subtotal não bate com as linhas abaixo: {lab}",
                    f"Subtotal R$ {_br(v, 0)}; soma das linhas {a}–{b} = R$ {_br(s, 0)}.", "Corrigir o intervalo do SUM.", v - s)
                break
    for r, lab in rows:
        cells = [(c, O.cell(r, c).value) for c in mcols]
        com_f = [c for c, f in cells if isinstance(f, str) and f.startswith("=")]
        fixos = [c for c, f in cells if not (isinstance(f, str) and f.startswith("=")) and _num(Ov.cell(r, c).value) is not None]
        if len(com_f) >= 6 and fixos:
            add("Média", "R13", f"{nO}!" + ", ".join(f"{L(c)}{r}" for c in fixos), f"Valor digitado numa linha de fórmulas: {lab}",
                f"{len(fixos)} mês(es) com número fixo enquanto os outros usam fórmula.",
                "No sistema a linha é sempre calculada pelo modelo.")
        if tcol and not re.search(r"por unit|por cont|mes n|distribui", norm(lab)):
            t = _num(Ov.cell(r, tcol).value)
            if t is not None:
                s = sum(serie(r))
                if abs(t - s) > max(1, abs(s) * 1e-9):
                    add("Alta", "R11", f"{nO}!{L(tcol)}{r}", f"Total anual diferente da soma dos meses: {lab}",
                        f"Total {_br(t)}; soma dos meses {_br(s)}.", "Revisar o total da linha.", t - s)
    dist = next((r for r, lab in rows if "distribuicao mensal" in norm(lab)), None)
    if dist:
        s = sum(serie(dist))
        if abs(s - 1) > 1e-6:
            add("Alta", "R12", f"{nO}!linha {dist}", "Distribuição mensal não soma 100%", f"Soma = {_br(s * 100, 4)}%.",
                "Ajustar a curva de recebimento.")


def _anterior_resumo(R, Rv, p, out, nR):
    rh = _find_label(R, Rv, [r"^rubrica$"], col_label=2, max_row=60)
    if not rh:
        return
    cb = cf = None
    for c in range(2, R.max_column + 1):
        h = norm(Rv.cell(rh[0], c).value)
        if h.startswith("budget"):
            cb = cb or c
        elif h.startswith("forecast"):
            cf = cf or c
    if not cb or not cf:
        return
    for r in range(rh[0] + 1, rh[0] + 40):
        lab = norm(Rv.cell(r, 2).value)
        if not lab:
            continue
        if lab.startswith("total"):
            continue
        if lab.startswith("volume"):
            for c, k in ((cb, "b"), (cf, "f")):
                v = _num(Rv.cell(r, c).value)
                if v is not None:
                    p["volume_anterior"][k] = v
            continue
        rub = next((x for x in RUBRICAS if re.search(x["re"], lab)), None)
        if rub and "anterior:" + rub["k"] not in out["origem"]:
            b, f = _num(Rv.cell(r, cb).value), _num(Rv.cell(r, cf).value)
            if b is not None:
                p["anterior"][rub["k"]]["budget"] = b
            if f is not None:
                p["anterior"][rub["k"]]["forecast"] = f
            out["origem"]["anterior:" + rub["k"]] = {"celula": f"{nR}!linha {r}", "valor": f}


def _importar_generico(wf, wv, base_p) -> dict[str, Any]:
    """Previa para planilhas fora do modelo: procura o rotulo de cada premissa em todas as abas e pega o numero mais
    proximo a direita. O que nao for achado fica com o valor de referencia (modelo ou ultima versao)."""
    out = _resultado_vazio("generico", base_p)
    p = out["params"]
    alvos = [("e", e["k"], e["re"]) for e in ESCALARES] + [("t", t["k"], t["re"] or [re.escape(norm(t["l"]))]) for t in TARIFAS]
    for tipo, k, pads in alvos:
        achou = False
        for ws in wf.worksheets:
            wsv = wv[ws.title]
            pos = _find_label(ws, wsv, pads, max_row=300)
            if not pos:
                continue
            for c in range(pos[1] + 1, min(ws.max_column, pos[1] + 8) + 1):
                v = _num(wsv.cell(pos[0], c).value)
                if v is not None:
                    if tipo == "e":
                        p["escalares"][k] = v
                        _origem(out, k, ws, pos[0], c, v)
                    else:
                        p["tarifas"][k]["base"] = v
                        _origem(out, "tarifa:" + k, ws, pos[0], c, v)
                    achou = True
                    break
            if achou:
                break
        if not achou:
            out["nao_encontrados"].append(k if tipo == "e" else "tarifa:" + k)
    out["alertas"].append({"sev": "Média", "cod": "G01", "onde": "Planilha", "titulo": "Planilha fora do modelo",
                           "detalhe": f"{len(out['origem'])} premissa(s) reconhecida(s) pelos rótulos; "
                                      f"{len(out['nao_encontrados'])} ficaram com o valor de referência.",
                           "acao": "Conferir a prévia antes de confirmar. Moeda, reajuste e mês de início das tarifas vêm do modelo.",
                           "impacto": None})
    return out


def rotulo_premissa(chave: str) -> str:
    if chave.startswith("tarifa:"):
        return TARIFA_BY_KEY[chave[7:]]["l"]
    if chave.startswith("anterior:"):
        return f"Budget/Forecast anterior: {RUBRICA_BY_KEY[chave[9:]]['l']}"
    e = next((x for x in ESCALARES if x["k"] == chave), None)
    return e["l"] if e else {"curva": "Curva de recebimento", "ajudantes_uso": "Ajudantes: meses com uso",
                             "anterior_mensal": "Budget e Forecast do ano anterior mês a mês"}.get(chave, chave)


# ---------------------------------------------------------------------------
# Exportacao no MODELO (troca de celulas direto no XML: graficos e formatos ficam intactos)
# ---------------------------------------------------------------------------
def _sheet_paths(z: zipfile.ZipFile) -> dict[str, str]:
    wb = z.read("xl/workbook.xml").decode("utf-8")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    rid = {m.group(1): m.group(2) for m in re.finditer(r'<Relationship[^>]*Id="([^"]+)"[^>]*Target="([^"]+)"', rels)}
    rid.update({m.group(2): m.group(1) for m in re.finditer(r'<Relationship[^>]*Target="([^"]+)"[^>]*Id="([^"]+)"', rels)})
    out = {}
    for m in re.finditer(r'<sheet [^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wb):
        target = rid[m.group(2)].lstrip("/")
        out[_xml_unescape(m.group(1))] = target if target.startswith("xl/") else "xl/" + target
    return out


def _xml_unescape(s: str) -> str:
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&")


def _fmt_num(v: float) -> str:
    return repr(float(v)) if not float(v).is_integer() else str(int(v))


def _set_cell(xml: str, ref: str, value: Any = None, formula: str | None = None) -> str:
    """Troca o conteudo da celula ref no XML da aba (numero, texto ou formula), mantendo o estilo."""
    pat = re.compile(r'<c r="' + ref + r'"([^>]*?)(/>|>(.*?)</c>)', re.S)
    m = pat.search(xml)
    attrs = re.sub(r'\s+t="[^"]*"', "", m.group(1)) if m else ""
    if formula is not None:
        new = f'<c r="{ref}"{attrs}><f>{escape(formula.lstrip("="))}</f></c>'
    elif isinstance(value, str):
        new = f'<c r="{ref}"{attrs} t="inlineStr"><is><t>{escape(value)}</t></is></c>'
    else:
        new = f'<c r="{ref}"{attrs}><v>{_fmt_num(value)}</v></c>'
    if m:
        return xml[:m.start()] + new + xml[m.end():]
    # celula inexistente: insere na linha (ordem das colunas)
    rown = int(re.sub(r"[A-Z]+", "", ref))
    rm = re.search(r'<row r="' + str(rown) + r'"[^>]*?(/>|>(.*?)</row>)', xml, re.S)
    if not rm:
        raise ValueError(f"linha {rown} não existe no modelo")
    if rm.group(1) == "/>":
        row_xml = rm.group(0)[:-2] + ">" + new + "</row>"
        return xml[:rm.start()] + row_xml + xml[rm.end():]
    inner = rm.group(2)
    col = re.sub(r"\d+", "", ref)

    def colnum(c):
        n = 0
        for ch in c:
            n = n * 26 + ord(ch) - 64
        return n
    pos = len(inner)
    for cm in re.finditer(r'<c r="([A-Z]+)\d+"', inner):
        if colnum(cm.group(1)) > colnum(col):
            pos = cm.start()
            break
    inner2 = inner[:pos] + new + inner[pos:]
    start = rm.start(2)
    return xml[:start] + inner2 + xml[start + len(inner):]


def exportar_modelo(params: dict[str, Any], modelo: Path, subtitulo: str = "") -> bytes:
    """Gera a planilha MODELO com as premissas da versao. O Excel recalcula tudo ao abrir."""
    p, _ = clean_params(params)
    e, t = p["escalares"], p["tarifas"]
    src = zipfile.ZipFile(str(modelo))
    paths = _sheet_paths(src)
    xml = {name: src.read(path).decode("utf-8") for name, path in paths.items()
           if name in {"Premissas", "Premissas Detalhadas", "Cálculo Mensal", "Comparativo 2026", "Painel"}}
    P = xml["Premissas"]
    for r, k in MODELO_PREM_ESCALAR.items():
        P = _set_cell(P, f"C{r}", e[k])
    for r, k in MODELO_PREM_TARIFA.items():
        P = _set_cell(P, f"C{r}", t[k]["base"])
    for i, v in enumerate(p["curva"]):
        P = _set_cell(P, f"C{65 + i}", v)
    xml["Premissas"] = P
    D = xml["Premissas Detalhadas"]
    D = _set_cell(D, "C8", p["base_volume"])
    for tt in TARIFAS:
        r = tt["row"]
        cur = t[tt["k"]]
        D = _set_cell(D, f"E{r}", cur["moeda"])
        if cur["reajuste"] == "ipca":
            D = _set_cell(D, f"F{r}", formula="'Premissas Detalhadas'!$C$13")
        elif cur["reajuste"] == "inhouse":
            D = _set_cell(D, f"F{r}", formula="'Premissas Detalhadas'!$C$14")
        else:
            D = _set_cell(D, f"F{r}", cur["pct"] if cur["reajuste"] == "fixo" else 0)
        D = _set_cell(D, f"G{r}", cur["mes"])
    xml["Premissas Detalhadas"] = D
    C = xml["Cálculo Mensal"]
    for i, u in enumerate(p["ajudantes_uso"]):
        C = _set_cell(C, f"{'CDEFGHIJKLMN'[i]}18", u)
    if "FiltroResumo" in src.read("xl/workbook.xml").decode("utf-8"):
        C = _bloco_anterior(src, C, p)
        xml["Resumo Mensal"] = _set_cell(src.read(paths["Resumo Mensal"]).decode("utf-8"), "C4", f"Orçamento {p['ano']}")
    xml["Cálculo Mensal"] = C
    # Comparativo: budget/forecast do ano anterior pela rubrica escrita na coluna B do modelo
    xml["Comparativo 2026"] = _comparativo_xml(src, xml["Comparativo 2026"], p)
    if subtitulo:
        xml["Painel"] = _set_cell(xml["Painel"], "B3", subtitulo)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for item in src.infolist():
            name = item.filename
            if name == "xl/calcChain.xml":
                continue
            data = src.read(name)
            sheet = next((s for s, pth in paths.items() if pth == name and s in xml), None)
            if sheet:
                data = xml[sheet].encode("utf-8")
            elif name == "xl/workbook.xml":
                w = data.decode("utf-8")
                if "<calcPr" in w:
                    w = re.sub(r"<calcPr([^>]*?)/>", lambda mm: "<calcPr" + re.sub(r'\s+fullCalcOnLoad="[^"]*"', "", mm.group(1))
                               + ' fullCalcOnLoad="1"/>', w)
                else:
                    w = w.replace("</workbook>", '<calcPr fullCalcOnLoad="1"/></workbook>')
                data = w.encode("utf-8")
            elif name == "[Content_Types].xml":
                data = data.decode("utf-8").replace(
                    '<Override PartName="/xl/calcChain.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.calcChain+xml"/>',
                    "").encode("utf-8")
            elif name == "xl/_rels/workbook.xml.rels":
                data = re.sub(r'<Relationship[^>]*Target="calcChain.xml"[^>]*/>', "", data.decode("utf-8")).encode("utf-8")
            out.writestr(item, data)
    return buf.getvalue()


MES_COLS = "CDEFGHIJKLMN"
# Bloco do ano anterior na aba Calculo Mensal do MODELO (filtro Orcamento/Budget/Forecast da aba Resumo Mensal):
# linhas 72-84 = Budget e 88-100 = Forecast, na ordem das linhas do Resumo Mensal (rotulo na coluna B);
# 102/103 = volume e conteineres do Budget; 104/105 = do Forecast; C70:E70 = textos das opcoes do filtro.
BLOCO_BUDGET, BLOCO_FORECAST = 72, 88


def _linha_por_rotulo(rotulo: str) -> list[str]:
    n = norm(rotulo)
    regras = [(r"santos extrema", ["rod_santos"]), (r"ajudantes escolta|adicionais", ["rod_adicionais"]),
              (r"^frete maritimo", ["frete_maritimo"]), (r"^bunker", ["bunker"]), (r"marinha mercante|afrmm", ["afrmm"]),
              (r"^armazenagem", ["armazenagem"]), (r"^capatazia", ["capatazias"]), (r"^despachante", ["despachante"]),
              (r"in house", ["in_house"]), (r"^frete aereo", ["frete_aereo"]), (r"^sistemas", ["sistemas"]),
              (r"^seguro", ["seguro"]), (r"demurrage", ["demurrage", "multa"])]
    return next((keys for pt, keys in regras if re.search(pt, n)), [])


def _serie_anterior(p: dict[str, Any], cen: str, keys: list[str]) -> list[float]:
    am = (p.get("anterior_mensal") or {}).get(cen) or {}
    total = [0.0] * 12
    for k in keys:
        if k == "rod_adicionais":
            rod, santos = am.get("rodoviario"), am.get("rod_santos")
            arr = [rod[i] - santos[i] for i in range(12)] if rod and santos else None
        else:
            arr = am.get(k)
        if arr:
            total = [total[i] + arr[i] for i in range(12)]
    return total


def _bloco_anterior(z: zipfile.ZipFile, C: str, p: dict[str, Any]) -> str:
    ss = _shared_strings(z)
    ano = p["ano"]
    C = _set_cell(C, "C70", f"Orçamento {ano}")
    C = _set_cell(C, "D70", f"Budget {ano - 1}")
    C = _set_cell(C, "E70", f"Forecast {ano - 1}")
    for base, cen in ((BLOCO_BUDGET, "budget"), (BLOCO_FORECAST, "forecast")):
        for r in range(base, base + 13):
            keys = _linha_por_rotulo(_texto_celula(C, f"B{r}", ss))
            serie = _serie_anterior(p, cen, keys) if keys else [0.0] * 12
            for i, v in enumerate(serie):
                C = _set_cell(C, f"{MES_COLS[i]}{r}", round(v, 6))
    am = p.get("anterior_mensal") or {}
    for r, key in ((102, "units_budget"), (103, "cntr_budget"), (104, "units_forecast"), (105, "cntr_forecast")):
        arr = am.get(key) or [0.0] * 12
        for i, v in enumerate(arr):
            C = _set_cell(C, f"{MES_COLS[i]}{r}", round(float(v), 6))
    return C


def _texto_celula(xml: str, ref: str, ss: list[str]) -> str:
    m = re.search(r'<c r="' + ref + r'"([^>]*?)(?:/>|>(.*?)</c>)', xml, re.S)
    if not m or not m.group(2):
        return ""
    if 't="s"' in m.group(1):
        v = re.search(r"<v>(\d+)</v>", m.group(2))
        return _xml_unescape(ss[int(v.group(1))]) if v else ""
    return _xml_unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", m.group(2), re.S)))


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    try:
        xml = z.read("xl/sharedStrings.xml").decode("utf-8")
    except KeyError:
        return []
    return ["".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S)) for si in re.findall(r"<si>(.*?)</si>", xml, re.S)]


def _comparativo_xml(z: zipfile.ZipFile, K: str, p: dict[str, Any]) -> str:
    ss = _shared_strings(z)
    for m in list(re.finditer(r'<c r="B(\d+)"([^>]*?)>(.*?)</c>', K, re.S)):
        row, attrs, inner = int(m.group(1)), m.group(2), m.group(3)
        if 't="s"' in attrs:
            vm = re.search(r"<v>(\d+)</v>", inner)
            texto = _xml_unescape(ss[int(vm.group(1))]) if vm else ""
        else:
            texto = _xml_unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", inner, re.S)))
        lab = norm(texto)
        if not lab or row < 6:
            continue
        if lab.startswith("volume"):
            K = _set_cell(K, f"D{row}", p["volume_anterior"]["b"])
            K = _set_cell(K, f"E{row}", p["volume_anterior"]["f"])
            continue
        rub = next((x for x in RUBRICAS if re.search(x["re"], lab)), None)
        if rub and not lab.startswith("custo"):
            K = _set_cell(K, f"D{row}", p["anterior"][rub["k"]]["budget"])
            K = _set_cell(K, f"E{row}", p["anterior"][rub["k"]]["forecast"])
    return K


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")
