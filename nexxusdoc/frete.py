"""Validação do frete internacional da Centauro (24/11/2026, pedido do usuário).

Mesmo cálculo da calculadora "Validação de frete.xlsx" da equipe (abas AS FCL, AS LCL, DMS FCL e DMS LCL) e dos POPs
"ID 01 - Procedimento Validação - Frete Internacional DMS" e "ID 02 - ... Asia Shipping":
  - a fatura (PDF anexado ao e-mail do agente) dá o processo, o HBL, a origem, a data de embarque, a taxa do dólar e cada
    cobrança;
  - o BID mais recente de cada agente (Sua Area › SeuProjeto › BID › Centauro › Agente de Cargas › Tarifário) dá a tarifa;
  - o FUP da PGL (relatório SBF) dá a cubagem, o peso e os contêineres (no lugar das planilhas Suporte PÓS e Follow Up).
Nada é estimado: cobrança sem tarifa no BID vira "verificar" com o motivo (ex.: LCL acima da última faixa = proposta spot).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

AGENTES = {"asia": "Asia Shipping", "dms": "DMS"}
IOF_PADRAO = 0.035
REPASSE_DMS = 0.10  # Valor fictício; configurar tarifa autorizada na implantação

# Parâmetros da calculadora (24/11/2026, pedido do usuário: configuráveis na tela, por agente). Os valores gravados ficam em
# frete/parametros.json na pasta do sistema; o que faltar usa o padrão abaixo. DMS: IOF e PIS/COFINS vazios = os do BID.
PADRAO = {
    "geral": {"tolerancia_cobranca": 0.50, "tolerancia_total": 1.00},
    "asia": {"iof": 0.035, "peso_max_lcl_t": 7.0, "min_wm": 0.0, "bid": "mais_recente"},
    "dms": {"iof": None, "repasse": None, "peso_max_lcl_t": 5.0, "min_wm": 1.0},
}
REGRAS_BID = {"mais_recente": "Sempre o BID mais recente", "vigencia": "O BID vigente na data de embarque"}
P = {k: dict(v) for k, v in PADRAO.items()}  # parâmetros em uso (validar() troca pelos gravados)


def parametros(gravados: dict | None = None) -> dict:
    """Padrão + o que foi gravado (só chaves conhecidas)."""
    out = {k: dict(v) for k, v in PADRAO.items()}
    for grupo, vals in (gravados or {}).items():
        if grupo in out and isinstance(vals, dict):
            for k, v in vals.items():
                if k in out[grupo]:
                    out[grupo][k] = v
    return out

# Código do porto (UN/LOCODE) → nome da linha no BID
PORTOS = {"CNSHA": "Shanghai", "CNNGB": "Ningbo", "CNXMN": "Xiamen", "CNSHK": "Shekou", "CNTXG": "Xingang", "CNTSN": "Xingang",
          "CNTJN": "Xingang", "CNNTG": "Nantong", "CNSZX": "Shenzhen", "TWTXG": "Taichung", "CNYTN": "Yantian",
          "PKKHI": "Karachi", "HKHKG": "Hong Kong", "TWKHH": "Kaohsiung", "CNTAO": "Qingdao"}

NOMES = {
    "frete": "Frete internacional", "efs": "Emergency Fuel Surcharge", "ebf": "Emergency Booking Fee", "pss": "Peak Season",
    "iof": "IOF", "telex": "BL Issue / Telex", "dbill": "Liberação do BL (DBILL)", "dthc": "THC / Capatazia",
    "dtsc": "Terminal Security (DTSC)", "isps": "ISPS", "ddpp": "Damage Protection (DDPP)", "ddoff": "Drop Off",
    "desc": "Desconsolidação", "blfee": "BL Fee", "impressao": "Impressão de BL", "liberacao": "Liberação de BL",
    "dhsf": "Destination Handling Service Fee",
}


# ---------------------------------------------------------------- utilidades
def sem_acento(s) -> str:
    return unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower().strip()


def num_br(s) -> float | None:
    """'1.949,05' → 1949.05; '1249,60' → 1249.6; '6,0361225' → 6.0361225."""
    if s is None:
        return None
    t = str(s).strip().replace(" ", "")
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def num_ponto(s) -> float | None:
    """Cubagem e peso da Asia vêm com ponto decimal ('22.930 M3', '4690.000 KG')."""
    try:
        return float(str(s).strip())
    except (TypeError, ValueError):
        return None


def data_br(s) -> str | None:
    m = re.match(r"(\d{2})/(\d{2})/(\d{2,4})", str(s or "").strip())
    if not m:
        return None
    d, mth, y = m.groups()
    y = int(y) + (2000 if len(y) == 2 else 0)
    try:
        return date(int(y), int(mth), int(d)).isoformat()
    except ValueError:
        return None


def tipo_cntr(s) -> str | None:
    """'40HC', "40' HIGH CUBE", '20DV', '40NOR', "40' DRY" → '20' | '40' | '40HC' | '40NOR'."""
    t = sem_acento(s).replace("'", "").replace(" ", "")
    if not t:
        return None
    if t.startswith("20"):
        return "20"
    if t.startswith("40"):
        if "hc" in t or "highcube" in t or "hq" in t:
            return "40HC"
        if "nor" in t or "rf" in t or "reefer" in t:
            return "40NOR"
        return "40"
    return None


# ---------------------------------------------------------------- faturas
def _linhas_valor(bloco: str, padrao: re.Pattern) -> list[dict]:
    """Cobranças: a linha que termina em 'MOEDA valor valor_em_reais'; as linhas seguintes sem valor completam a descrição."""
    out = []
    for ln in bloco.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        m = padrao.match(ln)
        if m:
            desc, moeda, v1, v2 = m.groups()
            out.append({"descricao": desc.strip(" -"), "moeda": moeda, "valor": num_br(v1), "brl": num_br(v2)})
        elif out:
            out[-1]["descricao"] = (out[-1]["descricao"] + " " + ln).strip()
    return out


def chave_cobranca(desc: str) -> str:
    d = sem_acento(desc)
    # IOF primeiro: a linha do IOF da Asia cita "(Freight Charges + Origin Charges ...)"
    regras = [("imposto sobre operacoes financeiras", "iof"), ("iof", "iof"), ("international freight", "frete"),
              ("emergency fuel", "efs"), ("emergency booking", "ebf"), ("peak season", "pss"), ("freight", "frete"),
              ("bl issue", "telex"), ("telex", "telex"), ("destination bill of lading release", "dbill"),
              ("destination terminal handling", "dthc"), ("capatazia", "dthc"), ("thc", "dthc"),
              ("destination terminal security", "dtsc"), ("isps", "isps"), ("damage protection", "ddpp"),
              ("drop off", "ddoff"), ("desconsolida", "desc"), ("impressao de bl", "impressao"), ("bl fee", "blfee"),
              ("liberacao de bl", "liberacao"), ("destination handling service", "dhsf")]
    for termo, k in regras:
        if termo in d:
            return k
    return "outra"


def ler_fatura(texto: str) -> dict | None:
    """Lê o texto do PDF da fatura (Asia Shipping: 'AR INV ….PDF'; DMS: 'ND_….pdf'). None se não for fatura conhecida."""
    t = texto or ""
    if "ASIA SHIPPING" in t.upper() and "TOTAL A PAGAR" in t.upper():
        return _ler_asia(t)
    if "DMS AGENC" in t.upper() and re.search(r"Total a pagar", t, re.I):
        return _ler_dms(t)
    return None


def _g(p, t, flags=0, f=lambda x: x.strip()):
    m = re.search(p, t, flags)
    return f(m.group(1)) if m else None


def _ler_asia(t: str) -> dict:
    ini = t.find("Taxas MOEDA")
    fim = t.upper().find("TOTAL A PAGAR")
    bloco = t[t.find("\n", ini) + 1:fim] if ini >= 0 else ""
    linhas = _linhas_valor(bloco, re.compile(r"^(.*?)\s*\b(USD|BRL|EUR)\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})$"))
    cont = []
    raw = _g(r"CONTAINER\(ES\):\s*(.+)", t) or ""
    for numero, tipo in re.findall(r"([A-Z]{4}\d{7})\s*-\s*([0-9]{2}\s*[A-Z]*)", raw):
        cont.append({"numero": numero, "tipo": tipo_cntr(tipo), "tipo_texto": tipo.strip()})
    pol = re.search(r"Embarque:\s*([A-Z]{5})\s*=\s*([^,\n]+)", t)
    fr = next((x for x in linhas if chave_cobranca(x["descricao"]) == "frete"), None)
    fd = sem_acento(fr["descricao"]) if fr else ""
    modal = "FCL" if re.search(r"/cn\b|container\(s\)\s*@|\b\d+\s*(20|40)(hc|dv|gp|nor|dry)?\s*@", fd) else ("LCL" if ("m3" in fd or "cubic" in fd or "kg" in fd) else None)
    return {
        "agente": "asia", "processo": _g(r"Processo:\s*(S\d+S)", t), "numero": _g(r"Demonstrativo:\s*(\S+)", t),
        "emissao": data_br(_g(r"Emiss[aã]o:\s*(\d{2}/\d{2}/\d{4})", t)), "vencimento": data_br(_g(r"Vencimento:\s*(\d{2}/\d{2}/\d{4})", t)),
        "hbl": _g(r"N[ºo°]\s*BL:\s*(\S+)", t), "mbl": _g(r"BL-Master:\s*(\S+)", t), "armador": _g(r"Armador:\s*(.+)", t),
        "exportador": _g(r"Exportador:\s*(.+)", t), "navio": _g(r"Navio:\s*(.+?)\s+Viagem", t),
        "pol": pol.group(1) if pol else None, "pol_nome": pol.group(2).strip() if pol else None,
        "etd": data_br(_g(r"Dt\.Embarque:\s*(\d{2}/\d{2}/\d{4})", t)), "eta": data_br(_g(r"Dt\.Chegada:\s*(\d{2}/\d{2}/\d{4})", t)),
        "cubagem": num_ponto(_g(r"Cubagem:\s*([\d.,]+)\s*M3", t)), "peso": num_ponto(_g(r"Peso:\s*([\d.,]+)\s*KG", t)),
        "ref_cliente": _g(r"Ref\. Cliente:\s*(\S+)", t), "conteineres": cont, "modal": modal,
        "linhas": linhas, "total": num_br(_g(r"TOTAL A PAGAR\s+([\d.]+,\d{2})", t, re.I)),
        "taxa": num_br(_g(r"TAXA DO DIA USD:\s*([\d.,]+)", t)),
    }


def _ler_dms(t: str) -> dict:
    ini = re.search(r"Descri[cç][aã]o\s+Moeda\s+Valor original\s+Valores", t)
    fim = re.search(r"Total a pagar", t, re.I)
    bloco = t[ini.end():fim.start()] if ini and fim else ""
    linhas = _linhas_valor(bloco, re.compile(r"^(.*?)\s+(USD|BRL|EUR)\s+([\d.]*\d,\d{2})\s+([\d.]*\d,\d{2})$"))
    return {
        "agente": "dms", "processo": _g(r"N/\s*Ref\.:\s*\n?\s*(\d+)", t) or _g(r"FATURA N[ºo°]\.?:\s*(\d+)", t),
        "numero": _g(r"FATURA N[ºo°]\.?:\s*(\d+)", t),
        "emissao": data_br(_g(r"Data de emiss[aã]o:\s*(\d{2}/\d{2}/\d{4})", t)),
        "vencimento": data_br(_g(r"Data de vencimento:\s*(\d{2}/\d{2}/\d{4})", t)),
        "hbl": _g(r"H/BL:\s*(\S+)", t), "mbl": _g(r"M/BL:\s*(\S+)", t), "armador": None,
        "exportador": _g(r"Exportador:\s*(.+)", t), "navio": None,
        "pol": _g(r"POL:\s*([A-Z]{5})", t), "pol_nome": None,
        "etd": data_br(_g(r"ETD:\s*(\d{2}/\d{2}/\d{2})", t)), "eta": data_br(_g(r"ETA:\s*(\d{2}/\d{2}/\d{2})", t)),
        "cubagem": None, "peso": None, "ref_cliente": _g(r"S/\s*Ref\.:\s*(.+)", t), "conteineres": [], "modal": None,
        "linhas": linhas, "total": num_br(_g(r"Total a pagar:\s*R\$\s*([\d.,]+)", t, re.I)),
        "taxa": num_br(_g(r"Moeda\s+Taxa\s*\n?\s*USD\s+([\d.,]+)", t)),
    }


# ---------------------------------------------------------------- BID (tarifário)
MESES_PT = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6, "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}
FIM_MES = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


def periodo_aba(nome: str, ano: int) -> tuple[str, str] | None:
    """Período de embarque no nome da aba da DMS: 'FCL (Embarques 24OUT x 13NOV)', 'LCL - SET a 23OUT', 'LCL (Embarques de
    24OUT_DEZ)', 'FCL (Embarques SET_OUT)', 'Preencher LCL - JUN_JUL_AGO', 'FCL (Prioridade de embarque JUN'."""
    n = sem_acento(nome).upper()
    if "OLD" in n or "HISTORICO" in n or re.search(r"20\d\d", n):
        return None
    toks = re.findall(r"(\d{1,2})?\s*(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)", n)
    if not toks:
        return None
    (d1, m1), (d2, m2) = toks[0], toks[-1]
    m1, m2 = MESES_PT[m1], MESES_PT[m2]
    ini = date(ano, m1, int(d1) if d1 else 1)
    fim = date(ano, m2, int(d2) if d2 else FIM_MES[m2])
    return ini.isoformat(), fim.isoformat()


def _val_moeda(v):
    """'BRL 1.616,00' → ('BRL', 1616.0); 'USD 20,00 / HBL' → ('USD', 20.0); 540 → ('BRL', 540.0)."""
    if isinstance(v, (int, float)):
        return "BRL", float(v)
    s = str(v or "")
    m = re.search(r"(USD|BRL|R\$)\s*([\d.]+,\d{2}|[\d.]+)", s)
    if not m:
        return None, None
    moeda = "BRL" if m.group(1) in ("BRL", "R$") else "USD"
    return moeda, num_br(m.group(2)) if "," in m.group(2) else float(m.group(2))


def _tabela(ws) -> dict | None:
    """Tabela de fretes por porto: acha a linha 'Load Port(s)', a linha de tamanhos/faixas (acima) e a de seções (acima)."""
    lp = None
    for r in range(1, 12):
        if sem_acento(ws.cell(r, 2).value) == "load port(s)":
            lp = r
            break
    if not lp:
        return None
    tam_r, sec_r = lp - 1, lp - 2
    colunas, secao = {}, None
    for c in range(4, 30):
        s = ws.cell(sec_r, c).value if sec_r >= 1 else None
        if s not in (None, ""):
            secao = sem_acento(s)
        tam = ws.cell(tam_r, c).value
        if tam in (None, "") or not secao:
            continue
        if any(x in secao for x in ("operations", "allocation", "comments")) or any(x in sem_acento(tam) for x in ("allocation", "frequency", "transit")):
            break
        colunas[c] = (secao, tam)
    portos = {}
    r = lp
    while r < lp + 40:
        nome = ws.cell(r, 3).value
        if nome in (None, ""):
            break
        linha = {}
        for c, (secao, tam) in colunas.items():
            v = ws.cell(r, c).value
            linha.setdefault(secao, {})[str(tam).strip()] = v if isinstance(v, (int, float)) else None
        # colunas soltas úteis (Overweight da Asia LCL)
        for c in range(4, 30):
            h = sem_acento(ws.cell(tam_r, c).value)
            if "overweight" in h:
                v = ws.cell(r, c).value
                linha["overweight"] = v if isinstance(v, (int, float)) else None
        portos[sem_acento(nome)] = linha
        r += 1
    return {"portos": portos}


def _faixas(linha: dict) -> list[tuple[float, float]]:
    """LCL: [(até m³, USD por W/M)] em ordem; aceita 'até 5m³', 'até 5m³ / 7 ton'."""
    out = []
    for secao, vals in linha.items():
        if secao == "overweight" or not isinstance(vals, dict):
            continue
        for tam, v in vals.items():
            m = re.search(r"ate\s*(\d+)", sem_acento(tam))
            if m and v is not None:
                out.append((float(m.group(1)), float(v)))
    return sorted(out)


def _secao(linha: dict, *termos) -> dict:
    for secao, vals in linha.items():
        if isinstance(vals, dict) and any(t in secao for t in termos):
            return {tipo_cntr(k) or k: v for k, v in vals.items()}
    return {}


def ler_bid_asia(caminho: Path) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(caminho, data_only=True, read_only=False)
    out = {"agente": "asia", "arquivo": caminho.name, "vigencia": None, "fcl": None, "lcl": None}
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{2})\s*a\s*(\d{2})\.(\d{2})\.(\d{2})", caminho.name)
    if m:
        d1, m1, y1, d2, m2, y2 = map(int, m.groups())
        out["vigencia"] = [date(2000 + y1, m1, d1).isoformat(), date(2000 + y2, m2, d2).isoformat()]
    for ws in wb.worksheets:
        n = sem_acento(ws.title)
        tab = _tabela(ws)
        if not tab:
            continue
        if "fcl" in n and out["fcl"] is None:
            tab["aba"] = ws.title
            tab["locais"] = _locais_asia_fcl(ws)
            out["fcl"] = tab
        elif "lcl" in n and out["lcl"] is None:
            tab["aba"] = ws.title
            tab["locais"] = _locais_asia_lcl(ws)
            out["lcl"] = tab
    return out


def _locais_asia_fcl(ws) -> dict:
    """'TAXAS SANTOS': DDPP, DBILL, DTHC, DTSC, DDOFF, DISPS, NDESC, TELEX (valor e se é por CNTR ou BL)."""
    mapa = {"ddpp": "ddpp", "dbill": "dbill", "dthc": "dthc", "dtsc": "dtsc", "ddoff": "ddoff", "disps": "isps", "ndesc": "desc", "telex": "telex"}
    out = {}
    for r in range(20, 80):
        b = sem_acento(ws.cell(r, 2).value)
        if not b:
            continue
        cod = b.split(" ")[0]
        k = mapa.get(cod)
        if not k:
            continue
        moeda, v20 = _val_moeda(ws.cell(r, 3).value)
        _, v40 = _val_moeda(ws.cell(r, 4).value)
        por = "bl" if sem_acento(ws.cell(r, 5).value) in ("bl", "hbl") else "cntr"
        out[k] = {"moeda": moeda, "v20": v20, "v40": v40 if v40 is not None else v20, "por": por, "texto": str(ws.cell(r, 2).value).strip()}
    return out


def _locais_asia_lcl(ws) -> dict:
    """'TAXAS DESTINO - SANTOS': THC R$ 10 por W/M (mín. R$ 10), BL FEE 5, DESCONSOLIDAÇÃO 5, TELEX USD 20 por HBL."""
    out = {}
    for r in range(20, 80):
        b = sem_acento(ws.cell(r, 2).value)
        v = ws.cell(r, 3).value
        if not b or v in (None, ""):
            continue
        if b == "thc":
            moeda, val = _val_moeda(v)
            mn = re.search(r"min\w*\s*r\$\s*([\d.,]+)", sem_acento(v))
            out["dthc"] = {"moeda": moeda or "BRL", "por_wm": val, "minimo": num_br(mn.group(1)) if mn else val}
        elif b == "bl fee":
            out["dbill"] = {"moeda": "BRL", "valor": float(v) if isinstance(v, (int, float)) else _val_moeda(v)[1]}
        elif b.startswith("desconsolida"):
            out["desc"] = {"moeda": "BRL", "valor": float(v) if isinstance(v, (int, float)) else _val_moeda(v)[1]}
        elif b == "telex":
            moeda, val = _val_moeda(v)
            out["telex"] = {"moeda": moeda or "USD", "valor": val}
    return out


def ler_bid_dms(caminho: Path) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(caminho, data_only=True, read_only=False)
    ano = _ano_dms(caminho.name)
    out = {"agente": "dms", "arquivo": caminho.name, "ano": ano, "fcl": [], "lcl": []}
    for ws in wb.worksheets:
        n = sem_acento(ws.title)
        modal = "fcl" if "fcl" in n else "lcl" if "lcl" in n else None
        per = periodo_aba(ws.title, ano) if modal else None
        if not modal or not per:
            continue
        tab = _tabela(ws)
        if not tab:
            continue
        tab.update({"aba": ws.title, "periodo": list(per), "oculta": ws.sheet_state != "visible"})
        tab["locais"] = _locais_dms_fcl(ws) if modal == "fcl" else _locais_dms_lcl(ws)
        tab["impostos"] = _impostos_dms(ws)
        out[modal].append(tab)
    return out


def _ano_dms(nome: str) -> int:
    m = re.search(r"(FCL_LCL|LCL|FCL)\s*(20\d\d)", nome)
    return int(m.group(2)) if m else date.today().year


def _impostos_dms(ws) -> dict:
    out = {"iof": IOF_PADRAO, "repasse": REPASSE_DMS}
    for r in range(20, 100):
        b = sem_acento(ws.cell(r, 2).value)
        v = ws.cell(r, 3).value
        if b == "iof" and isinstance(v, (int, float)):
            out["iof"] = float(v)
        elif b == "pis" and isinstance(v, (int, float)):
            out["repasse"] = float(v)
    return out


def _locais_dms_fcl(ws) -> list[dict]:
    """Três grupos de armadores, cada um com THC, BL FEE, ISPS, DROP OFF, IMPRESSÃO DE BL e DESCONSOLIDAÇÃO."""
    mapa = {"thc": "dthc", "bl fee": "blfee", "isps": "isps", "drop off": "ddoff", "impressao de bl": "impressao", "desconsolidacao": "desc"}
    grupos, atual = [], None
    for r in range(20, 100):
        b = sem_acento(ws.cell(r, 2).value)
        if b.startswith("armadores:"):
            atual = {"armadores": [x.strip().upper() for x in str(ws.cell(r, 2).value).split(":", 1)[1].split("|")], "taxas": {}}
            grupos.append(atual)
            continue
        if atual is None or not b.startswith("-"):
            continue
        nome = b.strip("- :").strip()
        k = mapa.get(nome)
        v = ws.cell(r, 3).value
        if k and isinstance(v, (int, float)):
            por = "bl" if "hbl" in sem_acento(ws.cell(r, 4).value) or "bl" == sem_acento(ws.cell(r, 4).value).split(" ")[-1] else "cntr"
            atual["taxas"][k] = {"moeda": "BRL", "valor": float(v), "por": por}
    return grupos


def _locais_dms_lcl(ws) -> dict:
    out = {}
    for r in range(20, 100):
        b = sem_acento(ws.cell(r, 2).value)
        if not b.startswith("*"):
            continue
        if "liberacao de bl" in b:
            out["liberacao"] = {"moeda": "BRL", "valor": 0.0 if "isento" in b else (num_br(re.search(r"([\d.]+,\d{2})", b).group(1)) if re.search(r"([\d.]+,\d{2})", b) else 0.0)}
        else:
            m = re.search(r"brl\s*([\d.]+,\d{2})", b)
            if not m:
                continue
            if "desconsolida" in b:
                out["desc"] = {"moeda": "BRL", "por_wm": num_br(m.group(1))}
            elif "thc" in b or "capatazia" in b:
                out["dthc"] = {"moeda": "BRL", "por_wm": num_br(m.group(1))}
    return out


def tarifario(pasta_bid: Path) -> dict:
    """BID mais recente de cada agente na pasta Tarifário (fora de 'Anteriores'): Asia Shipping/<ano>/ e DMS/<ano>/."""
    out = {"lido_em": datetime.now().isoformat(timespec="seconds"), "pasta": str(pasta_bid), "asia": None, "dms": None, "fontes": {}}
    for k, sub in (("asia", "Asia Shipping"), ("dms", "DMS")):
        base = pasta_bid / sub
        if not base.is_dir():
            continue
        anos = sorted([p for p in base.iterdir() if p.is_dir() and re.fullmatch(r"20\d\d", p.name)], key=lambda p: p.name)
        arqs = []
        for a in anos[-1:]:
            arqs += [f for f in a.glob("*.xlsx") if not f.name.startswith("~$")]
        if not arqs:
            continue
        mais = max(arqs, key=lambda f: f.stat().st_mtime)
        out["fontes"][k] = {"arquivo": mais.name, "caminho": str(mais), "mtime": mais.stat().st_mtime}
        try:
            out[k] = ler_bid_asia(mais) if k == "asia" else ler_bid_dms(mais)
        except Exception as erro:  # arquivo aberto/corrompido: mostra o motivo, não derruba a página
            out["fontes"][k]["erro"] = str(erro)
        if k == "asia":
            # para o parâmetro "BID vigente na data de embarque": todos os BIDs da Asia do ano (inclusive Anteriores)
            hist = []
            for f in arqs + [g for a in anos[-1:] for g in (a / "Anteriores").glob("*.xlsx") if not g.name.startswith("~$")]:
                try:
                    b = out["asia"] if f == mais and out.get("asia") else ler_bid_asia(f)
                except Exception:  # noqa: BLE001
                    continue
                if b.get("vigencia"):
                    hist.append(b)
            out["asia_hist"] = hist
    return out


# ---------------------------------------------------------------- base do embarque (FUP da PGL)
def base_embarque(fat: dict, fup: dict | None) -> dict:
    """Cubagem, peso e contêineres: do FUP da PGL (como a calculadora, que puxava do Suporte PÓS); sem FUP, os da fatura."""
    f = fup or {}
    cub_fup, peso_fup = f.get("cubagem"), f.get("peso")
    cub = cub_fup if cub_fup else fat.get("cubagem")
    peso = peso_fup if peso_fup else fat.get("peso")
    cont = conteineres_fup(f.get("volume")) or {}
    if not cont and fat.get("conteineres"):
        for c in fat["conteineres"]:
            if c.get("tipo"):
                cont[c["tipo"]] = cont.get(c["tipo"], 0) + 1
    confere = []
    if cub_fup and fat.get("cubagem"):
        confere.append({"campo": "Cubagem (m³)", "fatura": fat["cubagem"], "fup": cub_fup, "ok": abs(cub_fup - fat["cubagem"]) <= max(0.01, cub_fup * 0.005)})
    if peso_fup and fat.get("peso"):
        confere.append({"campo": "Peso bruto (kg)", "fatura": fat["peso"], "fup": peso_fup, "ok": abs(peso_fup - fat["peso"]) <= max(1, peso_fup * 0.005)})
    if f.get("etd") and fat.get("etd") and f["etd"][:10] != fat["etd"]:
        confere.append({"campo": "Embarque", "fatura": fat["etd"], "fup": f["etd"][:10], "ok": False})
    return {"cubagem": cub, "peso": peso, "conteineres": cont, "fonte": "FUP da PGL" if (cub_fup or peso_fup) else "fatura",
            "wm": max(cub or 0, (peso or 0) / 1000) or None, "confere": confere}


def conteineres_fup(volume) -> dict:
    """"2 CNTR 40' HIGH CUBE,1 CNTR 20' DRY" → {'40HC': 2, '20': 1}."""
    out = {}
    for n, tipo in re.findall(r"(\d+)\s*CNTR\s*([^,]+)", str(volume or ""), re.I):
        t = tipo_cntr(tipo)
        if t:
            out[t] = out.get(t, 0) + int(n)
    return out


# ---------------------------------------------------------------- validação
def _linha(k, cobrado, esperado_moeda, esperado_valor, taxa, regra, status=None):
    esp_brl = None if esperado_valor is None else round(esperado_valor * (taxa if esperado_moeda == "USD" else 1), 2)
    cob_brl = sum((c["brl"] or 0) for c in cobrado) if cobrado else None
    dif = None if esp_brl is None or cob_brl is None else round(cob_brl - esp_brl, 2)
    if status is None:
        if not cobrado:
            status = "nao_cobrado" if esp_brl else "ok"
        elif esp_brl is None:
            status = "sem_tarifa"
        else:
            status = "ok" if abs(dif) <= max(P["geral"]["tolerancia_cobranca"], abs(esp_brl) * 0.003) else "divergente"
    return {"chave": k, "nome": NOMES.get(k, k), "cobrado": [{"descricao": c["descricao"], "moeda": c["moeda"], "valor": c["valor"], "brl": c["brl"]} for c in cobrado],
            "cobrado_brl": cob_brl, "esperado_moeda": esperado_moeda, "esperado_valor": None if esperado_valor is None else round(esperado_valor, 4),
            "esperado_brl": esp_brl, "dif": dif, "regra": regra, "status": status}


def _porto(fat: dict, portos: dict) -> tuple[str | None, dict | None]:
    nome = PORTOS.get(fat.get("pol") or "") or (fat.get("pol_nome") or "")
    k = sem_acento(nome)
    if k in portos:
        return nome, portos[k]
    for p, linha in portos.items():
        if k and (p.startswith(k) or k.startswith(p)):
            return nome, linha
    return nome or None, None


def validar(fat: dict, tar: dict, fup: dict | None = None, params: dict | None = None) -> dict:
    """Confere cada cobrança da fatura contra o BID. Situação: conferida | divergente | verificar."""
    global P
    P = parametros(params)
    taxa = fat.get("taxa") or 0
    base = base_embarque(fat, fup)
    motivos, avisos = [], []
    por_chave = {}
    for i, c in enumerate(fat.get("linhas", [])):
        k = chave_cobranca(c["descricao"])
        por_chave.setdefault(k if k != "outra" else f"outra{i}", []).append(c)  # cada taxa fora do BID numa linha
    modal = fat.get("modal")
    if not modal:
        # a DMS não escreve FCL/LCL na fatura (e a Asia às vezes não deixa claro): o FUP da PGL só tem contêiner no FCL
        modal = "FCL" if conteineres_fup((fup or {}).get("volume")) else "LCL"
    res = {"modal": modal, "base": base, "tarifa": None, "linhas": []}
    if not taxa:
        motivos.append("A fatura não traz a taxa do dólar.")
    bid = (tar or {}).get(fat.get("agente"))
    if not bid:
        motivos.append(f"O BID da {AGENTES.get(fat.get('agente'), fat.get('agente'))} não foi encontrado na pasta Tarifário.")
        return _fecha(res, fat, motivos, avisos)
    tab = None
    if fat["agente"] == "asia":
        etd = fat.get("etd")
        if P["asia"].get("bid") == "vigencia" and etd:
            # parâmetro: o BID cuja vigência cobre a data de embarque (o que começou por último); sem nenhum, o mais recente
            cobre = [b for b in tar.get("asia_hist") or [] if b.get("vigencia") and b["vigencia"][0] <= etd <= b["vigencia"][1]]
            if cobre:
                bid = max(cobre, key=lambda b: b["vigencia"][0])
            else:
                avisos.append(f"Nenhum BID da Asia cobre o embarque em {_br(etd)}: conferido com o BID mais recente.")
        tab = bid.get("fcl" if modal == "FCL" else "lcl")
        vig = bid.get("vigencia")
        if P["asia"].get("bid") != "vigencia" and vig and etd and not (vig[0] <= etd <= vig[1]):
            avisos.append(f"Embarque em {_br(etd)}, fora da vigência do BID ({_br(vig[0])} a {_br(vig[1])}): conferido com o BID mais recente, como manda o parâmetro.")
        if tab:
            res["tarifa"] = {"arquivo": bid["arquivo"], "aba": tab.get("aba"), "periodo": vig}
    else:
        abas = bid.get("fcl" if modal == "FCL" else "lcl") or []
        etd = fat.get("etd") or (fup or {}).get("etd", "")[:10]
        cand = [a for a in abas if etd and a["periodo"][0] <= etd <= a["periodo"][1]]
        if cand:
            tab = max(cand, key=lambda a: a["periodo"][0])  # período mais específico (o que começou por último)
        elif abas:
            tab = max(abas, key=lambda a: a["periodo"][0])
            avisos.append(f"Nenhuma aba do BID cobre o embarque em {_br(etd) if etd else 'data não informada'}; usada a aba mais recente ({tab['aba']}).")
        if tab:
            res["tarifa"] = {"arquivo": bid["arquivo"], "aba": tab["aba"], "periodo": tab["periodo"]}
    if not tab:
        motivos.append(f"O BID não tem a tabela {modal or ''} deste agente.")
        return _fecha(res, fat, motivos, avisos)
    porto, linha = _porto(fat, tab["portos"])
    res["tarifa"]["porto"] = porto
    if not linha:
        motivos.append(f"A origem {fat.get('pol') or '-'} ({porto or 'sem nome'}) não está no BID.")
    calc = (_asia_lcl if (fat["agente"], modal) == ("asia", "LCL") else _asia_fcl if fat["agente"] == "asia" else
            _dms_lcl if modal == "LCL" else _dms_fcl)
    calc(res, fat, tab, linha or {}, base, por_chave, taxa, motivos, avisos)
    # cobranças que o BID não prevê
    usadas = {ln["chave"] for ln in res["linhas"]}
    for k, cs in por_chave.items():
        if k not in usadas:
            st = "indevida" if k == "dhsf" else "nao_prevista"
            ln = _linha(k, cs, None, None, taxa, "Taxa cobrada indevidamente: não faz parte do BID (planilha TAXA INDEVIDA da equipe)." if k == "dhsf" else "Cobrança que o BID não prevê.", st)
            if k.startswith("outra"):
                ln["nome"] = re.split(r"\s+-\s+|\s+@", cs[0]["descricao"])[0][:60]
            res["linhas"].append(ln)
    for c in base["confere"]:
        if not c["ok"]:
            avisos.append(f"{c['campo']} da fatura ({_fmt(c['fatura'])}) diferente do FUP da PGL ({_fmt(c['fup'])}).")
    return _fecha(res, fat, motivos, avisos)


def _frete_lcl(res, fat, linha, base, por_chave, taxa, motivos, avisos, minimo_wm=0.0):
    wm = base["wm"]
    faixas = _faixas(linha)
    if not wm:
        motivos.append("Sem cubagem e peso (nem no FUP da PGL, nem na fatura) para calcular o frete LCL.")
        res["linhas"].append(_linha("frete", por_chave.get("frete", []), "USD", None, taxa, "Frete LCL por W/M", "sem_tarifa"))
        return None
    wm_calc = max(wm, minimo_wm)
    faixa = next(((ate, v) for ate, v in faixas if wm <= ate), None)
    if not faixa:
        ult = faixas[-1][0] if faixas else 0
        cob = " ".join(c["descricao"] for c in por_chave.get("frete", []))
        m = re.findall(r"@\s*USD\s*([\d.,]+)\s*/\s*(?:M3|Cubic)", cob, re.I) or re.findall(r"@\s*USD\s*([\d.,]+)\s*/M3", cob, re.I)
        tarifa = f" A fatura cobra USD {m[-1]} por m³." if m else ""
        res["resumo"] = f"Spot: {_fmt(wm)} W/M, acima da última faixa do BID ({_fmt(ult)} m³)" + (f"; cobrado USD {m[-1]}/m³" if m else "")
        motivos.append(f"Carga de {_fmt(wm)} W/M, acima da última faixa do BID (até {_fmt(ult)} m³): o frete é negociado à parte (proposta spot).{tarifa} Conferir com a proposta da equipe que negocia o frete.")
        res["linhas"].append(_linha("frete", por_chave.get("frete", []), "USD", None, taxa, f"Fora das faixas do BID (até {_fmt(ult)} m³)", "sem_tarifa"))
        return None
    ate, v = faixa
    res["tarifa"]["faixa"] = f"até {_fmt(ate)} m³: USD {_fmt(v)} por W/M"
    usd = round(v * wm_calc, 2)
    res["linhas"].append(_linha("frete", por_chave.get("frete", []), "USD", usd, taxa, f"USD {_fmt(v)} × {_fmt(wm_calc)} W/M (faixa até {_fmt(ate)} m³)"))
    return usd


def _iof(res, por_chave, base_usd, taxa, pct, regra_base):
    if base_usd is None and por_chave.get("frete"):
        # frete sem tarifa no BID (spot): o IOF ainda é conferido sobre o frete que a fatura cobra
        base_usd = round(sum(c["valor"] or 0 for c in por_chave["frete"] if c["moeda"] == "USD"), 2) or None
        regra_base = "o frete cobrado (spot)"
    if base_usd is None:
        res["linhas"].append(_linha("iof", por_chave.get("iof", []), "USD", None, taxa, "IOF sobre o frete", "sem_tarifa"))
        return
    res["linhas"].append(_linha("iof", por_chave.get("iof", []), "USD", round(base_usd * pct, 2), taxa, f"{_fmt(pct * 100)}% sobre {regra_base} (USD {_fmt(base_usd)})"))


def _asia_lcl(res, fat, tab, linha, base, por_chave, taxa, motivos, avisos):
    loc = tab.get("locais") or {}
    wm = base["wm"]
    lim = float(P["asia"]["peso_max_lcl_t"] or 0)
    if lim and (base.get("peso") or 0) > lim * 1000:
        avisos.append(f"Peso de {_fmt(base['peso'])} kg acima de {_fmt(lim)} t: o BID prevê adicional de overweight (USD {_fmt(linha.get('overweight'))} por W/M).")
    usd = _frete_lcl(res, fat, linha, base, por_chave, taxa, motivos, avisos, minimo_wm=float(P["asia"]["min_wm"] or 0))
    _iof(res, por_chave, usd, taxa, float(P["asia"]["iof"]), "o frete")
    thc = loc.get("dthc") or {"por_wm": 10.0, "minimo": 10.0}
    if wm:
        res["linhas"].append(_linha("dthc", por_chave.get("dthc", []), "BRL", max(thc["minimo"] or 0, thc["por_wm"] * wm), taxa, f"R$ {_fmt(thc['por_wm'])} por W/M (mínimo R$ {_fmt(thc['minimo'])})"))
    for k, rot in (("dbill", "BL FEE"), ("desc", "Desconsolidação"), ("telex", "Telex por HBL")):
        x = loc.get(k)
        if x:
            res["linhas"].append(_linha(k, por_chave.get(k, []), x["moeda"], x["valor"], taxa, f"{rot}: {x['moeda']} {_fmt(x['valor'])}"))


def _asia_fcl(res, fat, tab, linha, base, por_chave, taxa, motivos, avisos):
    cont = base["conteineres"]
    if not cont:
        motivos.append("Não foi possível saber os contêineres (nem no FUP da PGL, nem na fatura).")
        return
    fr, efs, pss = _secao(linha, "freight"), _secao(linha, "emergency"), _secao(linha, "peak")
    usd = 0.0
    partes = []
    for t, q in cont.items():
        v = fr.get(t) if fr.get(t) else (fr.get("40") if t == "40HC" else None)
        if not v:
            motivos.append(f"O BID não tem frete para contêiner {t} saindo de {res['tarifa'].get('porto')}.")
            continue
        usd += v * q
        partes.append(f"{q} × {t} USD {_fmt(v)}")
    frete_usd = round(usd, 2) if partes else None
    res["linhas"].append(_linha("frete", por_chave.get("frete", []), "USD", frete_usd, taxa, " + ".join(partes) or "Frete por contêiner"))
    extra = 0.0
    if efs:
        v_efs = sum((efs.get(t) or efs.get("40HC") or 0) * q for t, q in cont.items())
        if v_efs:
            extra += v_efs
            res["linhas"].append(_linha("efs", por_chave.get("efs", []), "USD", v_efs, taxa, "Emergency Fuel Surcharge do BID, por contêiner"))
    if pss:
        v_pss = sum((pss.get("CTNR") or next(iter(pss.values()), 0) or 0) * q for q in cont.values())
        if v_pss:
            extra += v_pss
            res["linhas"].append(_linha("pss", por_chave.get("pss", []), "USD", v_pss, taxa, "Peak Season do BID, por contêiner"))
    _iof(res, por_chave, None if frete_usd is None else frete_usd + extra, taxa, float(P["asia"]["iof"]), "frete e adicionais")
    if frete_usd is not None and por_chave.get("frete"):
        cob = sum(c["valor"] or 0 for c in por_chave["frete"])
        if abs(cob - frete_usd) > 1:
            avisos.append(f"Frete cobrado USD {_fmt(cob)} × BID USD {_fmt(frete_usd)}: se foi embarque spot, conferir com a proposta aprovada.")
    n = sum(cont.values())
    for k, x in (tab.get("locais") or {}).items():
        if x["por"] == "bl":
            v = x["v20"]
            regra = f"{x['moeda']} {_fmt(v)} por BL"
        else:
            v = sum((x["v20"] if t == "20" else x["v40"]) * q for t, q in cont.items())
            regra = f"{x['moeda']} {_fmt(x['v20'])} (20') / {_fmt(x['v40'])} (40') por contêiner × {n}"
        res["linhas"].append(_linha(k, por_chave.get(k, []), x["moeda"], v, taxa, regra))


def _dms_lcl(res, fat, tab, linha, base, por_chave, taxa, motivos, avisos):
    loc, imp = tab.get("locais") or {}, _impostos_dms_p(tab)
    if not base["wm"]:
        # sem FUP: a capatazia (R$ por W/M) mostra a W/M que a DMS usou
        cap = sum(c["brl"] or 0 for c in por_chave.get("dthc", []))
        pw = (loc.get("dthc") or {}).get("por_wm")
        if cap and pw:
            base["wm"] = round(cap / pw, 3)
            base["fonte"] = "capatazia da fatura"
            avisos.append("Processo sem cubagem no FUP da PGL: a W/M foi tirada da capatazia da fatura.")
    lim = float(P["dms"]["peso_max_lcl_t"] or 0)
    if lim and (base.get("peso") or 0) >= lim * 1000:
        avisos.append(f"Carga LCL com {_fmt(lim)} t ou mais: pela proposta da DMS pode haver adicional de overweight.")
    wm = base["wm"]
    usd = _frete_lcl(res, fat, linha, base, por_chave, taxa, motivos, avisos)
    _iof(res, por_chave, usd, taxa, imp.get("iof", IOF_PADRAO), "o frete")
    wmc = max(wm or 0, float(P["dms"]["min_wm"] or 0))  # mínimo de W/M das taxas locais (parâmetro; a calculadora usa 1)
    if wm and loc.get("dthc"):
        res["linhas"].append(_linha("dthc", por_chave.get("dthc", []), "BRL", loc["dthc"]["por_wm"] * wmc, taxa, f"Capatazia R$ {_fmt(loc['dthc']['por_wm'])} por W/M × {_fmt(wmc)}"))
    if wm and loc.get("desc"):
        rep = imp.get("repasse", REPASSE_DMS)
        v = loc["desc"]["por_wm"] * wmc * (1 + rep)
        res["linhas"].append(_linha("desc", por_chave.get("desc", []), "BRL", v, taxa, f"R$ {_fmt(loc['desc']['por_wm'])} por W/M × {_fmt(wmc)} + {_fmt(rep * 100)}% de PIS/COFINS repassado"))
    if loc.get("liberacao") is not None:
        res["linhas"].append(_linha("liberacao", por_chave.get("liberacao", []) + por_chave.get("blfee", []), "BRL", loc["liberacao"]["valor"], taxa, "Liberação de BL: isenta no BID"))


def _dms_fcl(res, fat, tab, linha, base, por_chave, taxa, motivos, avisos):
    cont, imp = base["conteineres"], _impostos_dms_p(tab)
    if not cont:
        motivos.append("O FUP da PGL não tem os contêineres deste processo.")
        return
    fr, ebf = _secao(linha, "freight"), _secao(linha, "emergency")
    usd, partes = 0.0, []
    for t, q in cont.items():
        v = fr.get(t)
        if not isinstance(v, (int, float)):
            motivos.append(f"O BID não tem frete para contêiner {t} saindo de {res['tarifa'].get('porto')}.")
            continue
        usd += v * q
        partes.append(f"{q} × {t} USD {_fmt(v)}")
    frete_usd = round(usd, 2) if partes else None
    res["linhas"].append(_linha("frete", por_chave.get("frete", []), "USD", frete_usd, taxa, " + ".join(partes) or "Frete por contêiner"))
    extra = 0.0
    v_ebf = sum((ebf.get(t) or 0) * q for t, q in cont.items() if isinstance(ebf.get(t), (int, float)))
    if v_ebf:
        extra = v_ebf
        res["linhas"].append(_linha("ebf", por_chave.get("ebf", []), "USD", v_ebf, taxa, "Emergency Booking Fee do BID, por contêiner"))
    _iof(res, por_chave, None if frete_usd is None else frete_usd + extra, taxa, imp.get("iof", IOF_PADRAO), "frete e adicionais")
    # taxas locais: a DMS cobra pelo grupo do armador; a fatura não diz o armador, então vale o grupo que bate
    n = sum(cont.values())
    grupos = tab.get("locais") or []
    melhor = None
    for g in grupos:
        linhas = []
        for k, x in g["taxas"].items():
            v = x["valor"] * (1 if x["por"] == "bl" else n)
            regra = f"R$ {_fmt(x['valor'])} por {'BL' if x['por'] == 'bl' else 'contêiner'}" + ("" if x["por"] == "bl" else f" × {n}")
            if k == "desc":
                v *= 1 + imp.get("repasse", REPASSE_DMS)
                regra += f" + {_fmt(imp.get('repasse', REPASSE_DMS) * 100)}% de PIS/COFINS"
            linhas.append(_linha(k, por_chave.get(k, []), "BRL", v, taxa, regra))
        erro = sum(abs(ln["dif"] or 0) for ln in linhas if ln["cobrado"])
        if melhor is None or erro < melhor[0]:
            melhor = (erro, g, linhas)
    if melhor:
        res["linhas"] += melhor[2]
        res["tarifa"]["grupo_armador"] = " | ".join(melhor[1]["armadores"])


def _impostos_dms_p(tab) -> dict:
    """IOF e PIS/COFINS da DMS: o parâmetro, quando preenchido; senão, o que está no BID."""
    imp = dict(tab.get("impostos") or {})
    for k in ("iof", "repasse"):
        if P["dms"].get(k) is not None:
            imp[k] = float(P["dms"][k])
    return imp


def _fecha(res, fat, motivos, avisos) -> dict:
    total = fat.get("total")
    linhas = res["linhas"]
    calc = None
    if linhas and all(ln["esperado_brl"] is not None or ln["status"] in ("nao_prevista", "indevida") for ln in linhas if ln["status"] != "ok" or ln["esperado_brl"] is not None):
        calc = round(sum(ln["esperado_brl"] or 0 for ln in linhas), 2)
    soma_fat = round(sum(c["brl"] or 0 for c in fat.get("linhas", [])), 2)
    tol_total = float(P["geral"]["tolerancia_total"])
    if total is not None and abs(soma_fat - total) > tol_total:
        avisos.append(f"A soma das cobranças (R$ {_fmt(soma_fat)}) não fecha com o total da fatura (R$ {_fmt(total)}).")
    divs = [ln for ln in linhas if ln["status"] in ("divergente", "nao_prevista", "indevida")]
    sem = [ln for ln in linhas if ln["status"] == "sem_tarifa"]
    falt = [ln for ln in linhas if ln["status"] == "nao_cobrado"]
    for ln in divs:
        if ln["status"] == "divergente":
            motivos.append(f"{ln['nome']}: cobrado R$ {_fmt(ln['cobrado_brl'])}, pelo BID R$ {_fmt(ln['esperado_brl'])} (diferença R$ {_fmt(ln['dif'])}).")
        elif ln["status"] == "indevida":
            motivos.append(f"{ln['nome']} cobrada (R$ {_fmt(ln['cobrado_brl'])}): taxa indevida, fora do BID.")
        else:
            motivos.append(f"{ln['cobrado'][0]['descricao'][:70]} (R$ {_fmt(ln['cobrado_brl'])}) não está prevista no BID.")
    for ln in falt:
        avisos.append(f"{ln['nome']} prevista no BID (R$ {_fmt(ln['esperado_brl'])}) e não cobrada na fatura.")
    if sem or any("spot" in m or "não está no BID" in m or "não tem" in m or "Sem cubagem" in m or "não foi encontrado" in m or "taxa do dólar" in m or "contêineres" in m for m in motivos):
        situacao = "verificar"
    elif divs:
        situacao = "divergente"
    else:
        situacao = "conferida"
    if situacao == "conferida" and calc is not None and total is not None and abs(calc - total) > tol_total + 0.02 * len(linhas):
        situacao = "divergente"
        motivos.append(f"Total da fatura R$ {_fmt(total)} × total pelo BID R$ {_fmt(calc)}.")
    frete = next((ln for ln in linhas if ln["chave"] == "frete"), None)
    # resumo de uma linha para a lista
    if situacao == "conferida":
        res["resumo"] = "Todas as cobranças conferem com o BID."
    elif situacao == "divergente" and divs:
        maior = max(divs, key=lambda ln: abs(ln["dif"] if ln["dif"] is not None else (ln["cobrado_brl"] or 0)))
        val = maior["dif"] if maior["dif"] is not None else maior["cobrado_brl"]
        res["resumo"] = (f"{maior['nome']}: R$ {_fmt(val)} {'acima' if (val or 0) > 0 else 'abaixo'} do BID"
                         + (f" (e mais {len(divs) - 1} cobrança{'s' if len(divs) > 2 else ''})" if len(divs) > 1 else ""))
    elif not res.get("resumo"):
        res["resumo"] = motivos[0] if motivos else ""
    res.update({"situacao": situacao, "motivos": motivos, "avisos": avisos, "total_fatura": total, "total_bid": calc,
                "diferenca": None if calc is None or total is None else round(total - calc, 2),
                "frete_usd": sum(c["valor"] or 0 for c in (frete or {}).get("cobrado", [])) or None,
                "frete_brl": (frete or {}).get("cobrado_brl")})
    return res


def _br(iso) -> str:
    return "-" if not iso else "/".join(reversed(str(iso)[:10].split("-")))


def _fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, (int, float)):
        s = f"{v:,.2f}" if abs(v - round(v)) > 0.0001 or abs(v) < 100 else f"{v:,.0f}"
        if abs(v) < 100 and abs(v - round(v, 2)) > 0.0001:
            s = f"{v:,.3f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    return str(v)
