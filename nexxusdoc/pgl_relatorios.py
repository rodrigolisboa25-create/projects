"""Relatorios diarios da PGL (23/11/2026, pedido do usuario): os FUPs que a PGL manda por e-mail varias vezes ao dia.

O n8n (fluxo "NexxusDoc - Embarques", ramo "PGL") le no Gmail o anexo mais recente de cada relatorio e grava
nexxusdoc_pgl_relatorios.json na pasta do sistema (SO o n8n escreve; a 1a carga foi feita com este modulo). O arquivo
guarda a planilha inteira de cada relatorio (colunas e linhas como vieram, datas em AAAA-MM-DD) e, para a pagina
Embarques, um historico por processo (embarques.fup_registro) que vai crescendo: processo que sai do FUP continua la.
A mesma regra esta em JavaScript no fluxo (fup.js); os testes comparam as duas.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import embarques

# Relatorios automaticos da PGL (remetente admin@example.com). "assunto" = o que vem no e-mail.
RELATORIOS = {
    "fisia": {"titulo": "Follow Up · Fisia", "assunto": "Relatório de Follow Up - FISIA", "unidade": "Fisia",
              "descricao": "Processos da Fisia (INLINE, PROMO e AMOSTRAS) com o despachante PGL."},
    "zelus": {"titulo": "Follow Up · Fisia / Zelus", "assunto": "Relatório de Follow Up - Fisia / Zelus", "unidade": "Fisia",
              "descricao": "Processos da operação Zelus (Fisia) com o despachante PGL."},
    "sbf": {"titulo": "Follow Up · SBF (Centauro)", "assunto": "Relatório de Follow Up - SBF", "unidade": "Centauro",
            "descricao": "Processos da Centauro / SBF com o despachante PGL."},
}
# Colunas de data (pelo nome): o n8n le a data como numero de serie do Excel; sem a regra do nome, um numero comum
# (ex.: TOTAL 24602) viraria data.
DATA_COL = re.compile(r"^(DT |DATA|EMBARQUE NA ORIGEM|PREVISAO|CHEGADA|PRESENCA|REGISTRO DI|DESEMBARACO|INSPECAO|"
                      r"ENTREGA DA|ENTREGA DOC|NECESSIDADE|DATA_)", re.I)
MONEY_COL = re.compile(r"VALOR|CIF|FOB|FRETE", re.I)


def _texto(v: Any) -> Any:
    if isinstance(v, str):
        v = v.strip()
        return v or None
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def planilha(matriz: list[list[Any]]) -> tuple[list[str], list[list[Any]]]:
    """Linhas cruas da planilha -> (colunas, linhas). O cabecalho e a 1a linha com MODAL e PROCESSO (o FUP da SBF tem
    uma linha de titulo antes); linhas vazias saem; datas viram AAAA-MM-DD."""
    ini = next((i for i, r in enumerate(matriz[:15])
                if {"MODAL", "PROCESSO"} <= {str(c or "").strip().upper() for c in r}), None)
    if ini is None:
        raise ValueError("cabeçalho do FUP não encontrado (sem as colunas MODAL e PROCESSO)")
    cab = [str(c or "").strip() for c in matriz[ini]]
    while cab and not cab[-1]:
        cab.pop()
    datas = [bool(DATA_COL.match(c)) for c in cab]
    linhas = []
    for r in matriz[ini + 1:]:
        lin = []
        for j in range(len(cab)):
            v = r[j] if j < len(r) else None
            if datas[j] and v not in (None, ""):
                v = embarques.fup_data(v) or _texto(v)
            else:
                v = _texto(v)
            lin.append(v)
        if any(v not in (None, "") for v in lin):
            linhas.append(lin)
    return cab, linhas


def ler_xlsx(path: Path) -> tuple[list[str], list[list[Any]]]:
    import openpyxl
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return planilha([list(r) for r in book.worksheets[0].iter_rows(values_only=True)])
    finally:
        book.close()


def tipo_do_assunto(assunto: str) -> str:
    a = (assunto or "").upper()
    if "ZELUS" in a:
        return "zelus"
    if "FISIA" in a:
        return "fisia"
    return "sbf" if "SBF" in a else ""


def registros(colunas: list[str], linhas: list[list[Any]], fonte: str, visto: str) -> dict[str, dict[str, Any]]:
    """Linhas do FUP -> historico por processo da pagina Embarques (so Fisia e Zelus: a SBF e da Centauro)."""
    out: dict[str, dict[str, Any]] = {}
    for lin in linhas:
        par = embarques.fup_registro(dict(zip(colunas, lin)), fonte, visto)
        if par:
            out[par[0]] = par[1]
    return out


def montar_estado(anterior: dict[str, Any], novos: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """novos = {tipo: {msg, recebido_em, arquivo, colunas, linhas}}. Mesma regra do no 'PGL: montar' do n8n."""
    est = {**anterior}
    est.setdefault("relatorios", {})
    est.setdefault("processos", {})
    for tipo, rel in novos.items():
        meta = RELATORIOS[tipo]
        est["relatorios"][tipo] = {"titulo": meta["titulo"], "assunto": meta["assunto"], **rel}
        if tipo in ("fisia", "zelus"):
            est["processos"].update(registros(rel["colunas"], rel["linhas"], tipo, rel["recebido_em"]))
    est["versao"] = 1
    est["atualizado_em"] = datetime.now().astimezone().isoformat(timespec="seconds")
    return est


def sem_valores(colunas: list[str], linhas: list[list[Any]]) -> tuple[list[str], list[list[Any]]]:
    """Valores em R$/US$ so para master e owners (mesma regra da pagina Embarques)."""
    manter = [j for j, c in enumerate(colunas) if not MONEY_COL.search(c)]
    return [colunas[j] for j in manter], [[lin[j] if j < len(lin) else None for j in manter] for lin in linhas]
