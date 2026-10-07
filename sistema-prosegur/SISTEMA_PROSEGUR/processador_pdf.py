import os
import re
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

import pandas as pd
import pdfplumber

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
LOGGER = logging.getLogger(__name__)


class DocumentType(str, Enum):
    BOL = 'BOL'
    CTE_OS = 'CTE_OS'
    DEM = 'DEM'
    NFSE = 'NFSE'
    UNKNOWN = 'UNKNOWN'


@dataclass
class Party:
    role: str
    name: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None


@dataclass
class Tax:
    tax_type: str
    amount: Optional[float] = 0.0


@dataclass
class DemItem:
    guia: Optional[str] = None
    coleta_entrega: Optional[str] = None
    chegada_saida: Optional[str] = None
    montante_total: Optional[float] = 0.0
    advalorem: Optional[float] = 0.0
    tempo_excedente: Optional[float] = 0.0
    malote_qtd: Optional[str] = None
    malote_valor: Optional[float] = 0.0
    custodia: Optional[float] = 0.0
    qtd_emb: Optional[str] = None
    valor_extra: Optional[float] = 0.0
    valor_a_faturar: Optional[float] = 0.0
    data: Optional[str] = None
    qtd_milheiro: Optional[str] = None
    valor: Optional[float] = 0.0
    repasse: Optional[float] = 0.0
    numero_loja: Optional[str] = None
    cliente_faturar: Optional[str] = None
    cliente_origem: Optional[str] = None
    modalidade: Optional[str] = None
    tipo_servico: Optional[str] = None
    page_number: Optional[int] = None
    total_a_faturar_pagina: Optional[float] = 0.0
    valor_nota_documento: Optional[float] = 0.0


@dataclass
class DocumentPayload:
    document_id: str
    source_filename: str
    document_type: str
    page_count: int
    numero_documento: Optional[str] = None
    agencia_beneficiario: Optional[str] = None
    nosso_numero: Optional[str] = None
    natureza_operacao: Optional[str] = None
    lote_fatura: Optional[str] = None
    codigo_barras: Optional[str] = None
    vencimento: Optional[str] = None
    data_emissao: Optional[str] = None
    competencia: Optional[str] = None
    valor_total_documento: Optional[float] = 0.0
    valor_fatura: Optional[float] = 0.0
    valor_liquido: Optional[float] = 0.0
    valor_a_receber: Optional[float] = 0.0
    valor_icms: Optional[float] = 0.0
    empresa_nome: str = 'Desconhecida'
    numero_loja: Optional[str] = None
    codigo_forn: Optional[str] = None
    tipo_servico: Optional[str] = None
    modalidade: Optional[str] = None
    cliente_faturar: Optional[str] = None
    cliente_origem: Optional[str] = None
    descricao_servico: Optional[str] = None
    raw_text: Optional[str] = None
    prestador: Optional[Party] = None
    tomador: Optional[Party] = None
    taxes: List[Tax] = field(default_factory=list)
    dem_items: List[DemItem] = field(default_factory=list)


# =========================================================
# HELPERS
# =========================================================

def clean_money(text: Optional[str]) -> float:
    if text is None:
        return 0.0
    value = str(text).strip()
    if not value:
        return 0.0
    value = value.replace('R$', '').replace(' ', '')
    if ',' in value and '.' in value:
        if value.rfind(',') > value.rfind('.'):
            value = value.replace('.', '').replace(',', '.')
        else:
            value = value.replace(',', '')
    elif ',' in value:
        value = value.replace('.', '').replace(',', '.')
    value = re.sub(r'[^0-9\.-]', '', value)
    try:
        return float(value)
    except Exception:
        return 0.0


def normalize_id(text: Optional[str]) -> str:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ''
    value = str(text).strip()
    if re.fullmatch(r'\d+\.0', value):
        value = value[:-2]
    if 'E+' in value.upper():
        try:
            value = f'{float(value):.0f}'
        except Exception:
            pass
    return re.sub(r'\D', '', value)


def clean_line(line: str) -> str:
    return re.sub(r'\s+', ' ', line).strip()


def compact_text(text: str) -> str:
    lines = [clean_line(line) for line in text.splitlines()]
    return '\n'.join(line for line in lines if line)


def get_match(patterns: List[str], text: str, group: int = 1, flags: int = re.IGNORECASE | re.MULTILINE | re.DOTALL) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match.group(group).strip()
    return None


def get_last_match(patterns: List[str], text: str, group: int = 1, flags: int = re.IGNORECASE | re.MULTILINE | re.DOTALL) -> Optional[str]:
    for pattern in patterns:
        matches = list(re.finditer(pattern, text, flags))
        if matches:
            return matches[-1].group(group).strip()
    return None


def add_tax_if_value(payload: DocumentPayload, tax_type: str, raw_value: Optional[str]) -> None:
    amount = clean_money(raw_value)
    if amount or raw_value == '0,00':
        payload.taxes.append(Tax(tax_type=tax_type, amount=amount))


def split_pages_text(file_path: str, passwords: List[str]) -> Tuple[List[str], str]:
    for password in passwords:
        try:
            with pdfplumber.open(file_path, password=password) as pdf:
                pages = [compact_text(page.extract_text() or '') for page in pdf.pages]
                full_text = '\n\n'.join(pages)
                if len(full_text.strip()) > 10:
                    return pages, full_text
        except Exception as exc:
            LOGGER.debug('Falha ao abrir %s com a senha fornecida: %s', file_path, exc)
    return [], ''


def detect_document_type(file_name: str, full_text: str) -> DocumentType:
    name_up = file_name.upper().strip()
    text_up = full_text.upper()

    # 1. Checagem por sufixo Prosegur (Mais confiável)
    if name_up.endswith('_DEM.PDF') or name_up.endswith('_DEM'):
        return DocumentType.DEM
    if name_up.endswith('_BOL.PDF') or name_up.endswith('_BOL'):
        return DocumentType.BOL
    if name_up.endswith('_NFE.PDF') or name_up.endswith('_NFE'):
        return DocumentType.NFSE
    if 'CTE-OS' in name_up or 'CTE_OS' in name_up:
        return DocumentType.CTE_OS

    # 2. Checagem por conteúdo (Fallback)
    if 'DEMONSTRATIVO DE FATURAMENTO' in text_up or 'APURAÇÃO:' in text_up:
        return DocumentType.DEM
    if 'FICHA DE COMPENSAÇÃO' in text_up or 'NOSSO NÚMERO' in text_up or 'AUTENTICAÇÃO MECÂNICA' in text_up:
        return DocumentType.BOL
    if 'DACTE OS' in text_up or 'CT-E OS' in text_up or 'CONHECIMENTO DE TRANSPORTE' in text_up:
        return DocumentType.CTE_OS
    if 'NOTA FISCAL DE SERVIÇO ELETRÔNICA' in text_up or 'NFS-E' in text_up or 'VALOR DOS SERVIÇOS' in text_up:
        return DocumentType.NFSE

    return DocumentType.UNKNOWN


def fallback_from_filename(payload: DocumentPayload, file_name: str) -> None:
    parts = file_name.split('_')
    if len(parts) >= 4 and not payload.numero_documento:
        payload.numero_documento = normalize_id(parts[3]) or parts[3]


def reconcile_numero_documento_com_nome(payload: DocumentPayload, file_name: str) -> None:
    parts = file_name.split('_')
    if len(parts) < 4:
        return

    numero_nome = normalize_id(parts[3])
    numero_atual = normalize_id(payload.numero_documento)

    if not numero_nome:
        return

    # Para BOL e DEM, o numero do nome original da Prosegur e mais confiavel.
    if payload.document_type in ('BOL', 'DEM'):
        if numero_atual != numero_nome:
            payload.numero_documento = numero_nome


# =========================================================
# PARSERS
# =========================================================

def parse_nfse(payload: DocumentPayload, text: str) -> None:
    payload.numero_documento = get_match([
        r'NOTA FISCAL DE SERVIÇO ELETRÔNICA Nº.*?\n.*?(\d+)\b',
        r'Nº NFE\s*\n?(\d+)',
    ], text)
    payload.data_emissao = get_match([r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})\s+BELO HORIZONTE'], text)
    payload.vencimento = get_match([r'Código Serviço:\s*\d+\s+Código CNAE:\s*\d+\s+Vencimento:\s*(\d{2}/\d{2}/\d{4})'], text)
    payload.competencia = get_match([r'SERVIÇO\(S\) PRESTADO\(S\) EM\s+(\d{2}/\d{4})'], text)
    payload.descricao_servico = get_match([
        r'DESCRIÇÃO DOS SERVIÇOS\s*(.*?)(?=DADOS ADICIONAIS|DADOS BANCÁRIOS|RETENÇÕES FEDERAIS|VALORES|$)'
    ], text)
    payload.lote_fatura = get_match([r'Lote:\s*([\d\.]+)'], text)

    # BLOCO VALORES
    m_valores = re.search(
        r'VALOR DOS SERVIÇOS \(R\$\).*?\nR\$\s*([\d\.,]+)\s+0\s+0\s+R\$\s*([\d\.,]+)\s+R\$\s*([\d\.,]+)',
        text,
        re.IGNORECASE | re.MULTILINE | re.DOTALL
    )
    if m_valores:
        payload.valor_fatura = clean_money(m_valores.group(1))

    # BLOCO ISS / VALOR LÍQUIDO / VALOR DA NOTA
    m_iss = re.search(
        r'ISS \(R\$\)\s+ISS RETIDO \(R\$\)\s+DESCONTO CONDICIONADO \(R\$\)\s+VALOR LIQUIDO \(R\$\)\s+VALOR DA NOTA \(R\$\)\s*\n'
        r'R\$\s*([\d\.,]+)\s+R\$\s*([\d\.,]+)\s+0\s+R\$\s*([\d\.,]+)\s+R\$\s*([\d\.,]+)',
        text,
        re.IGNORECASE | re.MULTILINE | re.DOTALL
    )
    if m_iss:
        add_tax_if_value(payload, 'ISS', m_iss.group(1))
        payload.valor_liquido = clean_money(m_iss.group(3))
        payload.valor_total_documento = clean_money(m_iss.group(4))
        payload.valor_a_receber = payload.valor_liquido

    # BLOCO RETENÇÕES FEDERAis
    m_ret = re.search(
        r'PIS \(R\$\)\s+COFINS \(R\$\)\s+IR \(R\$\)\s+CSLL \(R\$\)\s+INSS \(R\$\)\s+OUTRAS RETENÇÕES \(R\$\)\s*\n'
        r'R\$\s*([\d\.,]+)\s+R\$\s*([\d\.,]+)\s+R\$\s*([\d\.,]+)\s+R\$\s*([\d\.,]+)\s+R\$\s*([\d\.,]+)',
        text,
        re.IGNORECASE | re.MULTILINE | re.DOTALL
    )
    if m_ret:
        add_tax_if_value(payload, 'PIS', m_ret.group(1))
        add_tax_if_value(payload, 'COFINS', m_ret.group(2))
        add_tax_if_value(payload, 'IR', m_ret.group(3))
        add_tax_if_value(payload, 'CSLL', m_ret.group(4))
        add_tax_if_value(payload, 'INSS', m_ret.group(5))

    prestador_name = get_match([r'PRESTADOR DE SERVIÇOS\s*\nRazão Social CPF/CNPJ\s*\n([^\n]+?)\s+\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}'], text)
    prestador_cnpj = get_match([r'PRESTADOR DE SERVIÇOS.*?\n[^\n]+\s+(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})'], text)
    tomador_name = get_match([r'TOMADOR DE SERVIÇOS\s*\nRazão Social CPF/CNPJ\s*\n([^\n]+?)\s+\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}'], text)
    tomador_cnpj = get_match([r'TOMADOR DE SERVIÇOS.*?\n[^\n]+\s+(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})'], text)
    tomador_address = get_match([r'TOMADOR DE SERVIÇOS.*?\nEndereço:\s*([^\n]+)'], text)

    if prestador_name or prestador_cnpj:
        payload.prestador = Party(role='prestador', name=prestador_name, tax_id=normalize_id(prestador_cnpj))
    if tomador_name or tomador_cnpj:
        payload.tomador = Party(role='tomador', name=tomador_name, tax_id=normalize_id(tomador_cnpj), address=tomador_address)


def parse_cte_os(payload: DocumentPayload, text: str) -> None:
    payload.numero_documento = get_match([
        r'Nº DOCUMENTO:\s*([\d\.]+)',
        r'MODELO SÉRIE NÚMERO FL DATA E HORA DE EMISSÃO\s+\d+\s+\d+\s+([\d\.]+)',
    ], text)
    payload.data_emissao = get_match([r'HORIZONTE, MG 67 1 [\d\.]+ 1/1 (\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})'], text)
    payload.natureza_operacao = get_match([
        r'NATUREZA DA OPERAÇÃO.*?\n\s*5353\s*-?([^\n]+?)(?:\s+ou em|$)',
        r'NATUREZA DA OPERAÇÃO\s+([^\n]+)'
    ], text)
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        upper = line.upper()
        if 'VALOR TOTAL DA PRESTAÇÃO DO SERVIÇO' in upper and idx + 1 < len(lines):
            payload.valor_total_documento = clean_money(lines[idx + 1])
        if 'VALOR A RECEBER' in upper and idx + 1 < len(lines):
            payload.valor_a_receber = clean_money(lines[idx + 1])
            payload.valor_liquido = payload.valor_a_receber
    payload.valor_icms = clean_money(get_match([r'Tributação Normal ICMS R\$\s*[\d\.,]+\s+[\d\.,]+\s+R\$\s*([\d\.,]+)'], text))
    payload.vencimento = get_match([r'VENCIMENTO:\s*(\d{2}/\d{2}/\d{4})'], text)
    payload.competencia = get_match([r'SERVICO\(S\) PRESTADO\(S\) EM\s+(\d{2}/\d{4})'], text)
    payload.lote_fatura = get_match([r'LOTE DE FATURA:\s*([\d\.]+)'], text)
    payload.tipo_servico = get_match([r'TIPO DO SERVIÇO\s*\n([^\n]+)'], text)

    prestador_name = 'PROSEGUR BRASIL S/A - TRANSPORTADORA DE VAL E SEGURANCA'
    prestador_cnpj = get_match([r'CNPJ:\s*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})'], text)
    tomador_name = get_match([r'TOMADOR/USUÁRIO DE SERVIÇO:.*?\n([^\n]+?)\s+[A-ZÁÉÍÓÚÇ ]+\s+\d{2}\.\d{3}-\d{3}'], text)
    tomador_cnpj = get_match([r'CNPJ/CPF:.*?\n(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})'], text)
    tomador_address = get_match([r'ENDEREÇO: UF: PAÍS:\s*\n([^\n]+)'], text)

    payload.prestador = Party(role='prestador', name=prestador_name, tax_id=normalize_id(prestador_cnpj))
    if tomador_name or tomador_cnpj:
        payload.tomador = Party(role='tomador', name=tomador_name, tax_id=normalize_id(tomador_cnpj), address=tomador_address)

    add_tax_if_value(payload, 'PIS', get_match([r'PIS:\s*([\d\.,]+)'], text))
    add_tax_if_value(payload, 'COFINS', get_match([r'COFINS:\s*([\d\.,]+)'], text))
    add_tax_if_value(payload, 'CSLL', get_match([r'CSLL:\s*([\d\.,]+)'], text))


def parse_bol(payload: DocumentPayload, text: str) -> None:
    payload.vencimento = get_match([r'Vencimento\s*\n(\d{2}/\d{2}/\d{4})', r'\b(\d{2}/\d{2}/\d{4})\b'], text)
    payload.data_emissao = get_match([r'Data do documento.*?\n(\d{2}/\d{2}/\d{4})', r'Data Processamento\s*\nPAGAVEL.*?(\d{2}/\d{2}/\d{4})'], text)
    payload.agencia_beneficiario = get_match([r'\b(\d{4}\s*/\s*\d{6}-\d)\b'], text)
    payload.nosso_numero = get_match([r'\b(\d{2}/\d{10}-\d)\b'], text)
    payload.codigo_barras = get_match([r'(\d{5}\.\d{5}\s+\d{5}\.\d{6}\s+\d{5}\.\d{6}\s+\d\s+\d{14})'], text)
    payload.lote_fatura = get_match([r'Lote Fatura:\s*([\d\.]+)'], text)
    payload.valor_liquido = clean_money(get_match([r'Valor Líquido\s*:?\s*([\d\.,]+)'], text))
    payload.valor_fatura = clean_money(get_match([r'VALOR FATURA:\s*([\d\.,]+)'], text))
    payload.valor_total_documento = payload.valor_fatura or clean_money(get_match([r'\(=\) Valor do Documento\s*\n.*?([\d\.,]+)'], text))
    payload.numero_documento = get_match([r'Número do documento\s+Espécie.*?\n\d{2}/\d{2}/\d{4}\s+([^\s]+)', r'\b(01-IC-\d+)\b'], text)

    prestador_name = 'PROSEGUR BRASIL S/A - TRANSPORTADORA DE VAL E SEGURANCA'
    prestador_cnpj = get_match([
        r'Nome do Beneficiário/CPF/CNPJ\s*\nPROSEGUR BRASIL S/A[^\n]*-CNPJ:(\d{14}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})',
        r'PROSEGUR BRASIL S/A[^\n]*-CNPJ:(\d{14}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})'
    ], text)
    tomador_name = get_match([r'Pagador:\s*([^\n]+?)\s+CPF/CNPJ:'], text)
    tomador_cnpj = get_match([r'Pagador:\s*[^\n]+?\s+CPF/CNPJ:\s*(\d{14})'], text)
    tomador_address = get_match([r'Pagador:\s*[^\n]+\n([^\n]+)'], text)

    payload.prestador = Party(role='prestador', name=prestador_name, tax_id=normalize_id(prestador_cnpj))
    if tomador_name or tomador_cnpj:
        payload.tomador = Party(role='tomador', name=tomador_name, tax_id=normalize_id(tomador_cnpj), address=tomador_address)

    add_tax_if_value(payload, 'IRRF', get_match([r'\(-\) IRRF:?\s*([\d\.,]+)'], text))
    add_tax_if_value(payload, 'ISSQN', get_match([r'\(-\) ISSQN:?\s*([\d\.,]+)'], text))
    add_tax_if_value(payload, 'INSS', get_match([r'\(-\) INSS:?\s*([\d\.,]+)'], text))
    add_tax_if_value(payload, 'PIS/COF/CSLL', get_match([r'\(-\) PIS/COF/CSLL\s*([\d\.,]+)'], text))


def _parse_dem_table_line_new(line: str) -> Optional[dict]:
    compact = line.replace(' ', '')
    match = re.match(
        r'^(?P<data>\d{2}/\d{2}/\d{4})(?:[A-Z0-9:]+)?(?P<qtd_milheiro>\d+[\.,]\d+)'
        r'(?P<valor>\d+[\.,]\d+)(?P<repasse>\d+[\.,]\d+)(?P<valor_a_faturar>\d+[\.,]\d+)$',
        compact,
    )
    if not match:
        return None
    return match.groupdict()


def _parse_dem_table_line_old(line: str) -> Optional[dict]:
    match = re.match(
        r'^(?P<guia>\d{6,})\s*(?P<coleta_entrega>[A-Z]{3}\s*\d{2}/\d{2}/\d{2}-\d{2}/\d{2}/\d{2})\s+'
        r'(?P<chegada_saida>\d{2}:\d{2}\s*/\s*\d{2}:\d{2})\s+'
        r'(?P<montante_total>[\d\.,]+)\s+'
        r'(?P<advalorem>[\d\.,]+)\s+'
        r'(?P<tempo_excedente>[\d\.,]+)\s+'
        r'(?P<malote_qtd>\d+)\s+'
        r'(?P<malote_valor>[\d\.,]+)\s+'
        r'(?P<custodia>[\d\.,]+)\s+'
        r'(?P<qtd_emb>\d+)\s+'
        r'(?P<valor_extra>[\d\.,]+)\s+'
        r'(?P<valor_a_faturar>[\d\.,]+)$',
        line,
    )
    if not match:
        return None
    data = match.groupdict()
    data['coleta_entrega'] = re.sub(r'([A-Z]{3})(\d{2}/\d{2}/\d{2})', r'\1 \2', data['coleta_entrega'])
    data['coleta_entrega'] = data['coleta_entrega'].replace('-', ' - ')
    return data


def parse_dem(payload: DocumentPayload, pages: List[str], full_text: str) -> None:
    payload.numero_documento = get_match([
        r'Nota Fiscal\s*:?\s*(\d+)',
        r'OS\s*:?\s*(\d+)',
    ], full_text)
    payload.data_emissao = get_match([
        r'DEMONSTRATIVO DE FATURAMENTO Data:\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})',
        r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})',
    ], full_text)
    payload.competencia = get_match([r'COMPETÊNCIA:\s*(\d{2}/\d{4})', r'Competência\s*:\s*(\d{2}/\d{4})'], full_text)
    payload.tipo_servico = get_match([r'Tipo de Serviço\s*:?\s*([^\n]+?)(?=\s+Ponto Envolvido|$)'], full_text)
    payload.modalidade = get_match([r'Modalidade\s*:?\s*([^\n]+?)(?=\s+Estrutura|\s+Nota Fiscal|$)'], full_text)
    payload.cliente_faturar = get_match([r'Cliente Faturar:\s*([^\n]+?)(?=\s+(?:Cliente Centro Custo|onto Centro Custo|Ponto Centro Custo)|$)'], full_text)
    payload.cliente_origem = get_match([r'Cliente Origem\s*:?\s*([^\n]+?)(?=\s+Município|$)'], full_text)
    payload.lote_fatura = get_match([r'Lote de Fatura:\s*([\d\.]+)'], full_text)
    payload.valor_fatura = clean_money(get_last_match([
        r'Valor da Nota:?\s*R\$\s*([\d\.,]+)',
        r'Valor da Nota\s*([\d\.,]+)',
        r'Valor Original\s*([\d\.,]+)',
    ], full_text))

    # Para DEM multi-loja, o valor do documento deve ser o consolidado final da nota.
    payload.valor_total_documento = payload.valor_fatura

    doc_store_candidates: List[str] = []

    for page_number, page_text in enumerate(pages, start=1):
        page_store = normalize_id(get_match([
            r'Cod Único cliente:\s*([A-Z]{0,3}\d+)',
            r'Loja\s*:?\s*(\d+)'
        ], page_text))
        page_cliente_faturar = get_match([r'Cliente Faturar:\s*([^\n]+?)(?=\s+(?:Cliente Centro Custo|onto Centro Custo|Ponto Centro Custo)|$)'], page_text) or payload.cliente_faturar
        page_cliente_origem = get_match([r'Cliente Origem\s*:?\s*([^\n]+?)(?=\s+Município|$)'], page_text) or payload.cliente_origem
        page_tipo_servico = get_match([r'Tipo de Serviço\s*:?\s*([^\n]+?)(?=\s+Ponto Envolvido|$)'], page_text) or payload.tipo_servico
        page_modalidade = get_match([r'Modalidade\s*:?\s*([^\n]+?)(?=\s+Estrutura|\s+Nota Fiscal|$)'], page_text) or payload.modalidade

        page_total_a_faturar = clean_money(get_last_match([
            r'Total a Faturar:?\s*([\d\.,]+)',
            r'Valor a Faturar:?\s*([\d\.,]+)',
        ], page_text))

        if page_store:
            doc_store_candidates.append(page_store)

        for raw_line in page_text.splitlines():
            line = clean_line(raw_line)
            if not line or line.startswith('Data Guia') or line == 'Faturar':
                continue

            item_new = _parse_dem_table_line_new(line)
            if item_new:
                payload.dem_items.append(DemItem(
                    data=item_new['data'],
                    qtd_milheiro=item_new['qtd_milheiro'],
                    valor=clean_money(item_new['valor']),
                    repasse=clean_money(item_new['repasse']),
                    valor_a_faturar=clean_money(item_new['valor_a_faturar']),
                    numero_loja=page_store or None,
                    cliente_faturar=page_cliente_faturar,
                    cliente_origem=page_cliente_origem,
                    modalidade=page_modalidade,
                    tipo_servico=page_tipo_servico,
                    page_number=page_number,
                    total_a_faturar_pagina=page_total_a_faturar,
                    valor_nota_documento=payload.valor_fatura,
                ))
                continue

            item_old = _parse_dem_table_line_old(line)
            if item_old:
                payload.dem_items.append(DemItem(
                    guia=item_old['guia'],
                    coleta_entrega=item_old['coleta_entrega'],
                    chegada_saida=item_old['chegada_saida'],
                    montante_total=clean_money(item_old['montante_total']),
                    advalorem=clean_money(item_old['advalorem']),
                    tempo_excedente=clean_money(item_old['tempo_excedente']),
                    malote_qtd=item_old['malote_qtd'],
                    malote_valor=clean_money(item_old['malote_valor']),
                    custodia=clean_money(item_old['custodia']),
                    qtd_emb=item_old['qtd_emb'],
                    valor_extra=clean_money(item_old['valor_extra']),
                    valor_a_faturar=clean_money(item_old['valor_a_faturar']),
                    numero_loja=page_store or None,
                    cliente_faturar=page_cliente_faturar,
                    cliente_origem=page_cliente_origem,
                    modalidade=page_modalidade,
                    tipo_servico=page_tipo_servico,
                    page_number=page_number,
                    total_a_faturar_pagina=page_total_a_faturar,
                    valor_nota_documento=payload.valor_fatura,
                ))

    unique_stores = [store for store in dict.fromkeys(doc_store_candidates) if store]
    if len(unique_stores) == 1:
        payload.numero_loja = unique_stores[0]
    elif len(unique_stores) > 1:
        payload.numero_loja = 'MULTI'


# =========================================================
# BASES AUXILIARES
# =========================================================

def carregar_bases() -> Tuple[dict, dict, dict]:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    candidate_paths = [
        os.path.join(current_dir, 'Base_Forn.xlsx'),
        os.path.join(parent_dir, 'Base_Forn.xlsx'),
    ]
    base_path = next((path for path in candidate_paths if os.path.exists(path)), None)

    mapa_lojas = {}
    mapa_empresas = {}
    mapa_fornecedores = {}

    if not base_path:
        LOGGER.warning('Base_Forn.xlsx não encontrada. O enriquecimento por CNPJ ficará incompleto.')
        return mapa_lojas, mapa_empresas, mapa_fornecedores

    try:
        df_lojas = pd.read_excel(base_path, sheet_name='cnpj lojas')
        for _, row in df_lojas.iterrows():
            cnpj = normalize_id(row.get('CNPJ')).zfill(14)
            loja = normalize_id(row.get('LOJA'))
            empresa = str(row.get('EMPRESA', '')).strip()
            if cnpj:
                mapa_lojas[cnpj] = loja
                mapa_empresas[cnpj] = 'SBF' if empresa == '7010' else 'FISIA'
    except Exception as exc:
        LOGGER.exception('Erro ao ler a aba cnpj lojas da Base_Forn.xlsx: %s', exc)

    try:
        df_forn = pd.read_excel(base_path, sheet_name='forns prosegur')
        for _, row in df_forn.iterrows():
            cnpj = normalize_id(row.get('CNPJ')).zfill(14)
            codigo = normalize_id(row.get('CÓDIGO'))
            if cnpj:
                mapa_fornecedores[cnpj] = codigo
    except Exception as exc:
        LOGGER.exception('Erro ao ler a aba forns prosegur da Base_Forn.xlsx: %s', exc)

    return mapa_lojas, mapa_empresas, mapa_fornecedores


MAP_L, MAP_E, MAP_F = carregar_bases()


def enrich_by_cnpj(payload: DocumentPayload, text: str) -> None:
    found_cnpjs = re.findall(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14}', text)
    for cnpj in found_cnpjs:
        normalized = normalize_id(cnpj).zfill(14)
        if normalized in MAP_L and not payload.numero_loja:
            payload.numero_loja = MAP_L[normalized]
            payload.empresa_nome = MAP_E.get(normalized, payload.empresa_nome)
        if normalized in MAP_F and not payload.codigo_forn:
            payload.codigo_forn = MAP_F[normalized]

    if payload.prestador and payload.prestador.tax_id and not payload.codigo_forn:
        payload.codigo_forn = MAP_F.get(payload.prestador.tax_id.zfill(14), payload.codigo_forn)

    if payload.empresa_nome == 'Desconhecida':
        upper_text = text.upper()
        if 'FISIA' in upper_text:
            payload.empresa_nome = 'FISIA'
        elif 'CENTAURO' in upper_text or 'GRUPO SBF' in upper_text or 'SBF' in upper_text:
            payload.empresa_nome = 'SBF'


# =========================================================
# ENTRYPOINT
# =========================================================

def analisar_pdf_extrair_dados(caminho: str, nome: str) -> DocumentPayload:
    pages, texto = split_pages_text(caminho, ['', '06347', '59546'])
    tipo = detect_document_type(nome, texto)

    payload = DocumentPayload(
        document_id=str(uuid.uuid4()),
        source_filename=nome,
        document_type=tipo.value,
        page_count=len(pages),
        raw_text=texto,
    )

    if tipo == DocumentType.BOL:
        parse_bol(payload, texto)
    elif tipo == DocumentType.DEM:
        parse_dem(payload, pages, texto)
    elif tipo == DocumentType.NFSE:
        parse_nfse(payload, texto)
    elif tipo == DocumentType.CTE_OS:
        parse_cte_os(payload, texto)
    else:
        LOGGER.warning('Tipo de documento não identificado para %s', nome)

    fallback_from_filename(payload, nome)
    reconcile_numero_documento_com_nome(payload, nome)
    enrich_by_cnpj(payload, texto)

    if not payload.tipo_servico:
        upper_text = texto.upper()
        if 'MANUSEIO' in upper_text or 'CONTAGEM' in upper_text or 'TESOURARIA' in upper_text:
            payload.tipo_servico = 'CONTAGEM DE VALORES'
        elif 'TRANSPORTE' in upper_text or 'COLETA/ENTREGA' in upper_text or 'COLETA' in upper_text:
            payload.tipo_servico = 'TRANSPORTE DE VALORES'
        else:
            payload.tipo_servico = 'SERVICO'

    return payload
