import os
import re
import json
import uuid
import pandas as pd
import pdfplumber
from dataclasses import dataclass, field, asdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, List, Optional, Tuple

# =========================================================
# CONFIG / ENUMS
# =========================================================

class DocumentType(str, Enum):
    BOL = "BOL"
    CTE_OS = "CTE_OS"
    DEM = "DEM"
    NFSE = "NFSE"
    UNKNOWN = "UNKNOWN"

@dataclass
class Party:
    role: str
    name: Optional[str] = None
    tax_id: Optional[str] = None

@dataclass
class Tax:
    tax_type: str
    base_amount: Optional[str] = None
    rate: Optional[str] = None
    amount: Optional[str] = None

@dataclass
class DemItem:
    item_seq: int
    source_page: int
    guia: Optional[str] = None
    valor_a_faturar: Optional[str] = None

@dataclass
class DocumentPayload:
    document_id: str
    source_filename: str
    document_type: str
    page_count: int
    status_extraction: str = "OK"
    numero_documento: Optional[str] = None
    data_emissao: Optional[str] = None
    competencia: Optional[str] = None
    data_vencimento: Optional[str] = None
    valor_total_documento: Optional[str] = None
    chave_documento: Optional[str] = None
    raw_text: Optional[str] = None

    # Campos Específicos Adicionados para o Ecossistema Prosegur
    empresa_nome: str = "Desconhecida"
    numero_loja: Optional[str] = None
    codigo_forn: Optional[str] = None
    tipo_servico: Optional[str] = None
    codigo_barras: Optional[str] = None

    parties: List[Party] = field(default_factory=list)
    taxes: List[Tax] = field(default_factory=list)
    dem_items: List[DemItem] = field(default_factory=list)

# =========================================================
# HELPERS DE EXTRAÇÃO E NORMALIZAÇÃO
# =========================================================

def br_money_to_decimal_str(text: Optional[str]) -> Optional[str]:
    if not text: return None
    s = str(text).strip().replace("R$", "").replace(".", "").replace(",", ".")
    try: return str(Decimal(s))
    except: return None

def br_date_to_iso(text: Optional[str]) -> Optional[str]:
    if not text: return None
    text = text.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d/%m/%Y %H:%M"):
        try: return datetime.strptime(text, fmt).isoformat(sep=" ")
        except ValueError: continue
    return text

def normalize_cnpj_cpf(text: Optional[str]) -> Optional[str]:
    if not text: return None
    return re.sub(r"\D", "", text)

def first_match(patterns: List[str], text: str) -> Optional[str]:
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if m: return m.group(1).strip()
    return None

# =========================================================
# BASES DE REFERÊNCIA (PROSEGUR)
# =========================================================

def carregar_bases_referencia():
    # Agora buscamos na pasta raiz (ajuste se mover o xlsx)
    caminho_base = "Base_Forn.xlsx"
    map_lojas, map_empresas, map_fornecedores = {}, {}, {}
    if not os.path.exists(caminho_base): return map_lojas, map_empresas, map_fornecedores
    try:
        df_lojas = pd.read_excel(caminho_base, sheet_name='cnpj lojas')
        for _, row in df_lojas.iterrows():
            c = normalize_cnpj_cpf(str(row['CNPJ']))
            map_lojas[c] = str(row['LOJA']).strip()
            map_empresas[c] = 'SBF' if str(row['EMPRESA']).strip() == '7010' else 'FISIA'
        df_forn = pd.read_excel(caminho_base, sheet_name='forns prosegur')
        for _, row in df_forn.iterrows():
            c = normalize_cnpj_cpf(str(row['CNPJ']))
            map_fornecedores[c] = str(row['CÓDIGO']).strip()
    except: pass
    return map_lojas, map_empresas, map_fornecedores

LOJAS_REF, EMPRESAS_REF, FORNS_REF = carregar_bases_referencia()

# =========================================================
# PARSERS ROBUSTOS (CONFORME TEMPLATE)
# =========================================================

def parse_bol(payload: DocumentPayload, text: str):
    payload.numero_documento = first_match([r"Número do documento\s+([0-9A-Za-z/\.\-]+)", r"\b(01-IC-\d+)\b"], text)
    payload.data_vencimento = br_date_to_iso(first_match([r"Vencimento\s+(\d{2}/\d{2}/\d{4})"], text))
    payload.valor_total_documento = br_money_to_decimal_str(first_match([r"Valor Fatura:\s*([\d\.,]+)", r"Valor do Documento.*?\n.*?([\d\.,]+)"], text))
    payload.codigo_barras = first_match([r"(\d{5}\.\d{5}\s+\d{5}\.\d{6}\s+\d{5}\.\d{6}\s+\d\s+\d{14})"], text)

def parse_cte_os(payload: DocumentPayload, text: str):
    payload.numero_documento = first_match([r"Nº DOCUMENTO:.*?SÉRIE:.*?\n.*?CT-E OS\s+([\d\.]+)"], text)
    payload.data_emissao = br_date_to_iso(first_match([r"DATA E HORA DE EMISSÃO\s+.*?\s+(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})"], text))
    payload.valor_total_documento = br_money_to_decimal_str(first_match([r"VALOR TOTAL DA PRESTAÇÃO.*?R\$\s*([\d\.,]+)"], text))

def parse_dem(payload: DocumentPayload, text: str):
    payload.competencia = first_match([r"COMPETÊNCIA:\s*([0-9/]+)"], text)
    payload.data_emissao = br_date_to_iso(first_match([r"Data:\s*(\d{2}/\d{2}/\d{4})"], text))
    payload.valor_total_documento = br_money_to_decimal_str(first_match([r"Total a Faturar\s+([\d\.,]+)", r"Valor da Nota\s+([\d\.,]+)"], text))
    # Identificação especial para DEM Prosegur
    if 'ce' in text.lower(): payload.empresa_nome = 'SBF'
    else: payload.empresa_nome = 'Fisia'

def parse_nfse(payload: DocumentPayload, text: str):
    payload.numero_documento = first_match([r"Nº NFE\s+(\d+)", r"NOTA FISCAL DE SERVIÇO ELETRÔNICA Nº.*?\n.*?(\d+)"], text)
    payload.data_emissao = br_date_to_iso(first_match([r"Data e Hora de Emissão.*?(\d{2}/\d{2}/\d{4})"], text))
    payload.valor_total_documento = br_money_to_decimal_str(first_match([r"VALOR DA NOTA.*?R\$\s*([\d\.,]+)"], text))

# =========================================================
# ORQUESTRADOR CENTRAL
# =========================================================

def analisar_pdf_extrair_dados(caminho_arquivo, nome_arquivo) -> DocumentPayload:
    texto_total = ""
    pages_count = 0
    senhas = ["", "06347", "59546"]

    # Tratamento de Senhas
    for s in senhas:
        try:
            with pdfplumber.open(caminho_arquivo, password=s) as pdf:
                pages_count = len(pdf.pages)
                for p in pdf.pages:
                    t = p.extract_text()
                    if t: texto_total += t + "\n"
                if len(texto_total.strip()) > 10: break
        except: continue

    # Detecção de Tipo
    doc_type = DocumentType.UNKNOWN
    upper_name = nome_arquivo.upper()
    if "_BOL" in upper_name: doc_type = DocumentType.BOL
    elif "_DEM" in upper_name: doc_type = DocumentType.DEM
    elif "_NFE" in upper_name: doc_type = DocumentType.NFSE
    elif "_CTE" in upper_name: doc_type = DocumentType.CTE_OS

    payload = DocumentPayload(
        document_id=str(uuid.uuid4()),
        source_filename=nome_arquivo,
        document_type=doc_type.value,
        page_count=pages_count,
        raw_text=texto_total
    )

    # Execução do Parser Específico
    if doc_type == DocumentType.BOL: parse_bol(payload, texto_total)
    elif doc_type == DocumentType.DEM: parse_dem(payload, texto_total)
    elif doc_type == DocumentType.NFSE: parse_nfse(payload, texto_total)
    elif doc_type == DocumentType.CTE_OS: parse_cte_os(payload, texto_total)

    # Enriquecimento com Dados de Empresa/Loja/Fornecedor via CNPJ
    cnpjs = re.findall(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", texto_total)
    for c in cnpjs:
        cleanc = normalize_cnpj_cpf(c)
        if cleanc in LOJAS_REF:
            payload.numero_loja = LOJAS_REF[cleanc]
            payload.empresa_nome = EMPRESAS_REF[cleanc]
        if cleanc in FORNS_REF:
            payload.codigo_forn = FORNS_REF[cleanc]

    # Identificação de Tipo de Serviço (Prosegur)
    t_up = texto_total.upper()
    if 'MANUSEIO' in t_up or 'CONTAGEM' in t_up: payload.tipo_servico = 'CONTAGEM DE VALORES'
    elif 'COLETA' in t_up or 'TRANSPORTE' in t_up: payload.tipo_servico = 'TRANSPORTE DE VALORES'

    return payload
