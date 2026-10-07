import json
import logging
import os
import re
import sqlite3
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
LOGGER = logging.getLogger(__name__)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
INPUT_DIR = os.path.join(ROOT_DIR, 'Idocs_Prosegur')
DB_PATH = os.path.join(BASE_DIR, 'documentos.db')
CHECKLIST_EMAIL = os.path.join(INPUT_DIR, 'AUDITORIA_EMAIL.json')
RELATORIO_AUDITORIA = os.path.join(BASE_DIR, 'RELATORIO_AUDITORIA.txt')
OUTPUT_DIR = os.path.join(ROOT_DIR, 'PROSEGUR_PROCESS')

TOLERANCIA_VALOR = 0.01
TIPOS_NOTA = {'NFSE', 'CTE_OS'}
TIPOS_VALIDOS = {'NFSE', 'CTE_OS', 'BOL', 'DEM', 'UNKNOWN'}


def safe_float(value: Any) -> float:
    try:
        if value in (None, ''):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def money(value: float) -> str:
    return f'R$ {value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def sanitize_filename(value: Any) -> str:
    text = str(value or 'DESC').strip().upper()
    text = re.sub(r'[^A-Z0-9._-]+', '_', text)
    text = re.sub(r'_+', '_', text).strip('_')
    return text or 'DESC'


def periodo_atual() -> str:
    return datetime.now().strftime('%m-%Y')


def get_periodo(doc: Dict[str, Any]) -> str:
    for key in ('periodo', 'PERIODO'):
        value = str(doc.get(key) or '').strip()
        if re.fullmatch(r'\d{2}-\d{4}', value):
            return value
    return periodo_atual()


def normalizar_tipo_servico_nome_arquivo(tipo_servico: Any) -> str:
    texto = str(tipo_servico or '').strip().upper()
    texto = re.sub(r'\s+', ' ', texto)

    if texto == 'SERVICOS DE MANUSEIO, ARRUMACAO E CONTAGEM DE VALORES EM TESOURARIA':
        return 'CONTAGEM DE VALORES'

    if texto == 'SERVICOS MUNICIPAIS DE COLETA/ENTREGA VALORES A EMPRESAS':
        return 'TRANSPORTE DE VALORES'

    if 'MANUSEIO' in texto or 'CONTAGEM' in texto:
        return 'CONTAGEM DE VALORES'

    if 'COLETA/ENTREGA' in texto or 'TRANSPORTE' in texto:
        return 'TRANSPORTE DE VALORES'

    return 'SERVICO'


def get_subpasta_por_tipo(doc_type: str) -> str:
    if doc_type == 'BOL':
        return 'Boletos'
    if doc_type == 'DEM':
        return 'Demonstrativos'
    return 'Notas Fiscais'


def montar_nome_saida_esperado(doc: Dict[str, Any]) -> str:
    doc_type = normalizar_doc_type(doc.get('document_type'))
    tipo_servico = sanitize_filename(
        normalizar_tipo_servico_nome_arquivo(doc.get('tipo_servico'))
    )
    loja = sanitize_filename(doc.get('numero_loja') or 'DESC')
    fornecedor = sanitize_filename(doc.get('codigo_forn') or 'DESC')
    numero_doc = sanitize_filename(doc.get('numero_documento') or 'DESC')

    if doc_type == 'BOL':
        return f'{fornecedor}_{numero_doc}.PDF'

    return f'{tipo_servico}_{loja}_{fornecedor}_{numero_doc}.PDF'


def montar_caminho_relativo_saida(doc: Dict[str, Any]) -> str:
    doc_type = normalizar_doc_type(doc.get('document_type'))
    empresa = sanitize_filename(doc.get('empresa_nome'))
    periodo = get_periodo(doc)
    subpasta = get_subpasta_por_tipo(doc_type)
    nome_arquivo = montar_nome_saida_esperado(doc)
    return os.path.join(empresa, periodo, subpasta, nome_arquivo)


def listar_pdfs_saida() -> List[str]:
    encontrados: List[str] = []
    if not os.path.exists(OUTPUT_DIR):
        return encontrados

    for raiz, _, arquivos in os.walk(OUTPUT_DIR):
        for nome in arquivos:
            if nome.lower().endswith('.pdf'):
                caminho_abs = os.path.join(raiz, nome)
                caminho_rel = os.path.relpath(caminho_abs, OUTPUT_DIR)
                encontrados.append(caminho_rel)
    return sorted(encontrados)


def norm_relpath(path: str) -> str:
    return str(path or '').replace('\\', '/').upper().strip()


def is_boleto_output_path(relpath: str) -> bool:
    return '/BOLETOS/' in norm_relpath(relpath)


def extrair_numero_doc_do_nome_boleto(relpath: str) -> str:
    nome = os.path.basename(relpath)
    nome_sem_ext = os.path.splitext(nome)[0]
    partes = nome_sem_ext.split('_')
    if len(partes) >= 2:
        return partes[-1].strip().upper()
    return ''


def extrair_fornecedor_do_nome_boleto(relpath: str) -> str:
    nome = os.path.basename(relpath)
    nome_sem_ext = os.path.splitext(nome)[0]
    partes = nome_sem_ext.split('_')
    if len(partes) >= 2:
        return partes[0].strip().upper()
    return ''


def is_nota_output_path(relpath: str) -> bool:
    return '/NOTAS FISCAIS/' in norm_relpath(relpath)


def extrair_numero_doc_do_nome_nota(relpath: str) -> str:
    nome = os.path.basename(relpath)
    nome_sem_ext = os.path.splitext(nome)[0]
    partes = nome_sem_ext.split('_')
    if len(partes) >= 4:
        return partes[-1].strip().upper()
    return ''


def diagnosticar_notas_ctes(db_docs: List[Dict[str, Any]], pdfs_saida: List[str]) -> Dict[str, Any]:
    notas_db = [
        doc for doc in db_docs
        if normalizar_doc_type(doc.get('document_type')) in {'NFSE', 'CTE_OS'}
    ]
    notas_saida = [p for p in pdfs_saida if is_nota_output_path(p)]

    notas_db_paths = {}
    for doc in notas_db:
        path_esperado = norm_relpath(montar_caminho_relativo_saida(doc))
        if path_esperado:
            notas_db_paths[path_esperado] = doc

    set_saida = {norm_relpath(p) for p in notas_saida}
    set_db = set(notas_db_paths.keys())

    faltando_na_saida = sorted(set_db - set_saida)
    sobrando_na_saida_paths = sorted(set_saida - set_db)

    idx_numero = defaultdict(list)
    for doc in notas_db:
        idx_numero[str(doc.get('numero_documento') or '').strip().upper()].append(doc)

    diagnosticos_sobrando = []
    for relpath in sobrando_na_saida_paths:
        numero_doc = extrair_numero_doc_do_nome_nota(relpath)
        matches_numero = idx_numero.get(numero_doc, [])

        motivo = 'SEM_CORRESPONDENCIA_NO_BANCO'
        detalhes = []

        if matches_numero:
            motivo = 'EXISTE_NO_BANCO_COM_OUTRO_PATH_OU_OUTRO_NOME'
            for doc in matches_numero:
                detalhes.append({
                    'source_filename': doc.get('source_filename'),
                    'numero_documento': doc.get('numero_documento'),
                    'lote_fatura': doc.get('lote_fatura'),
                    'document_type': doc.get('document_type'),
                    'path_esperado': norm_relpath(montar_caminho_relativo_saida(doc)),
                })

        diagnosticos_sobrando.append({
            'arquivo_saida': relpath,
            'numero_documento_saida': numero_doc,
            'motivo_suspeito': motivo,
            'matches_db': detalhes,
        })

    diagnosticos_db = []
    for doc in notas_db:
        diagnosticos_db.append({
            'source_filename': doc.get('source_filename'),
            'numero_documento': doc.get('numero_documento'),
            'lote_fatura': doc.get('lote_fatura'),
            'document_type': doc.get('document_type'),
            'path_esperado': norm_relpath(montar_caminho_relativo_saida(doc)),
        })

    return {
        'notas_db': diagnosticos_db,
        'notas_saida': [norm_relpath(p) for p in notas_saida],
        'faltando_na_saida': faltando_na_saida,
        'sobrando_na_saida': diagnosticos_sobrando,
    }


def diagnosticar_boletos(db_docs: List[Dict[str, Any]], pdfs_saida: List[str]) -> Dict[str, Any]:
    boletos_db = [doc for doc in db_docs if normalizar_doc_type(doc.get('document_type')) == 'BOL']
    boletos_saida = [p for p in pdfs_saida if is_boleto_output_path(p)]

    boletos_db_paths = {}
    for doc in boletos_db:
        path_esperado = norm_relpath(montar_caminho_relativo_saida(doc))
        if path_esperado:
            boletos_db_paths[path_esperado] = doc

    set_saida = {norm_relpath(p) for p in boletos_saida}
    set_db = set(boletos_db_paths.keys())

    faltando_na_saida = sorted(set_db - set_saida)
    sobrando_na_saida_paths = sorted(set_saida - set_db)

    idx_numero = defaultdict(list)
    for doc in boletos_db:
        idx_numero[str(doc.get('numero_documento') or '').strip().upper()].append(doc)

    diagnosticos_sobrando = []
    for relpath in sobrando_na_saida_paths:
        numero_doc = extrair_numero_doc_do_nome_boleto(relpath)
        fornecedor = extrair_fornecedor_do_nome_boleto(relpath)
        matches_numero = idx_numero.get(numero_doc, [])
        motivo = 'SEM_CORRESPONDENCIA_NO_BANCO'
        detalhes = []

        if matches_numero:
            motivo = 'EXISTE_NO_BANCO_COM_OUTRO_PATH_OU_OUTRO_NOME'
            for doc in matches_numero:
                detalhes.append({
                    'source_filename': doc.get('source_filename'),
                    'numero_documento': doc.get('numero_documento'),
                    'lote_fatura': doc.get('lote_fatura'),
                    'document_type': doc.get('document_type'),
                    'path_esperado': norm_relpath(montar_caminho_relativo_saida(doc)),
                })

        diagnosticos_sobrando.append({
            'arquivo_saida': relpath,
            'fornecedor_saida': fornecedor,
            'numero_documento_saida': numero_doc,
            'motivo_suspeito': motivo,
            'matches_db': detalhes,
        })

    diagnosticos_db = []
    for doc in boletos_db:
        diagnosticos_db.append({
            'source_filename': doc.get('source_filename'),
            'numero_documento': doc.get('numero_documento'),
            'lote_fatura': doc.get('lote_fatura'),
            'document_type': doc.get('document_type'),
            'path_esperado': norm_relpath(montar_caminho_relativo_saida(doc)),
        })

    return {
        'boletos_db': diagnosticos_db,
        'boletos_saida': [norm_relpath(p) for p in boletos_saida],
        'faltando_na_saida': faltando_na_saida,
        'sobrando_na_saida': diagnosticos_sobrando,
    }


def normalizar_doc_type(doc_type: Any) -> str:
    value = str(doc_type or '').strip().upper()
    return value if value in TIPOS_VALIDOS else 'UNKNOWN'


def get_lote_id(source_filename: str) -> str:
    parts = str(source_filename or '').split('_')
    if len(parts) >= 4:
        return f'{parts[0]}_{parts[3]}'
    return f'ARQUIVO_SEM_LOTE::{source_filename}'


def ler_manifesto_email() -> Tuple[Dict[str, Any], List[str]]:
    avisos: List[str] = []
    if not os.path.exists(CHECKLIST_EMAIL):
        avisos.append('Checklist AUDITORIA_EMAIL.json não encontrado em Idocs_Prosegur.')
        return {}, avisos

    try:
        with open(CHECKLIST_EMAIL, 'r', encoding='utf-8') as file:
            manifesto = json.load(file)
    except Exception as exc:
        avisos.append(f'Falha ao ler AUDITORIA_EMAIL.json: {exc}')
        return {}, avisos

    # Aceita tanto a nomenclatura antiga quanto a nova.
    manifesto_padronizado = {
        'total_threads': manifesto.get('total_threads_lote', manifesto.get('total_threads_encontradas', 0)),
        'total_emails_vistos': manifesto.get('total_emails_vistos', 0),
        'total_arquivos_salvos': manifesto.get('total_arquivos_salvos', 0),
        'total_arquivos_ignorados': manifesto.get('total_arquivos_ignorados', 0),
        'detalhes': manifesto.get('detalhes', []),
    }
    return manifesto_padronizado, avisos


def carregar_docs_db() -> List[Dict[str, Any]]:
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f'Banco de dados não encontrado: {DB_PATH}')

    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            '''
            SELECT source_filename, raw_payload, periodo, execution_id
            FROM documentos
            ORDER BY source_filename
            '''
        ).fetchall()
    finally:
        conn.close()

    docs: List[Dict[str, Any]] = []
    for source_filename, raw_payload, periodo, execution_id in rows:
        try:
            doc = json.loads(raw_payload)
            if 'source_filename' not in doc:
                doc['source_filename'] = source_filename
            doc['periodo'] = str(periodo or doc.get('periodo') or '').strip() or periodo_atual()
            if 'execution_id' not in doc:
                doc['execution_id'] = execution_id
            docs.append(doc)
        except Exception as exc:
            docs.append({
                'source_filename': source_filename,
                'document_type': 'UNKNOWN',
                'periodo': str(periodo or '').strip() or periodo_atual(),
                'execution_id': execution_id,
                'erro_parse_payload': str(exc),
            })
    return docs


def listar_pdfs_entrada() -> List[str]:
    if not os.path.exists(INPUT_DIR):
        return []
    return sorted([name for name in os.listdir(INPUT_DIR) if name.lower().endswith('.pdf')])


def extrair_valores_lote(nf_doc: Dict[str, Any], bol_doc: Dict[str, Any], dem_doc: Dict[str, Any]) -> Tuple[float, float, float]:
    val_nf = safe_float(nf_doc.get('valor_total_documento'))
    val_bol = safe_float(bol_doc.get('valor_total_documento') or bol_doc.get('valor_fatura'))
    val_dem = safe_float(dem_doc.get('valor_fatura') or dem_doc.get('valor_total_documento'))
    return val_nf, val_bol, val_dem


def calcular_totais_equivalentes_master(db_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    totais: Dict[str, Any] = {
        'notas_ctes_qtd_docs': 0,
        'boletos_qtd_docs': 0,
        'dem_qtd_docs': 0,
        'notas_total_prestacao': 0.0,
        'notas_total_nota': 0.0,
        'boletos_total_documento': 0.0,
        'dem_total_valor_nota': 0.0,
        'trace': []
    }

    for doc in db_docs:
        doc_type = normalizar_doc_type(doc.get('document_type'))
        source_filename = doc.get('source_filename')
        numero_documento = doc.get('numero_documento')
        lote_fatura = doc.get('lote_fatura')

        if doc_type == 'NFSE':
            valor = safe_float(doc.get('valor_total_documento'))
            totais['notas_ctes_qtd_docs'] += 1
            totais['notas_total_nota'] += valor
            totais['trace'].append({'tipo': 'NFSE', 'arquivo': source_filename, 'numero_documento': numero_documento, 'lote_fatura': lote_fatura, 'campo_master': 'VALOR DA NOTA (R$)', 'valor': valor})

        elif doc_type == 'CTE_OS':
            valor = safe_float(doc.get('valor_total_documento'))
            totais['notas_ctes_qtd_docs'] += 1
            totais['notas_total_prestacao'] += valor
            totais['trace'].append({'tipo': 'CTE_OS', 'arquivo': source_filename, 'numero_documento': numero_documento, 'lote_fatura': lote_fatura, 'campo_master': 'VALOR TOTAL DA PRESTAÇÃO DO SERVIÇO', 'valor': valor})

        elif doc_type == 'BOL':
            valor = safe_float(doc.get('valor_total_documento'))
            totais['boletos_qtd_docs'] += 1
            totais['boletos_total_documento'] += valor
            totais['trace'].append({'tipo': 'BOL', 'arquivo': source_filename, 'numero_documento': numero_documento, 'lote_fatura': lote_fatura, 'campo_master': 'Valor do Documento', 'valor': valor})

        elif doc_type == 'DEM':
            valor = safe_float(doc.get('valor_fatura'))
            totais['dem_qtd_docs'] += 1
            totais['dem_total_valor_nota'] += valor
            totais['trace'].append({'tipo': 'DEM', 'arquivo': source_filename, 'numero_documento': numero_documento, 'lote_fatura': lote_fatura, 'campo_master': 'Valor da Nota', 'valor': valor})

    return totais


def executar_auditoria(execution_id_atual: str | None = None) -> int:
    periodo_processamento = periodo_atual()
    print('\n' + '=' * 72)
    print('AGENTE DE AUDITORIA PROSEGUR - VALIDAÇÃO FINAL')
    print('=' * 72)

    erros_criticos = 0
    linhas_relatorio: List[str] = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    linhas_relatorio.append(f'RELATÓRIO DE AUDITORIA PROSEGUR | {timestamp}')
    linhas_relatorio.append('=' * 72)
    linhas_relatorio.append(f'BASE_DIR: {BASE_DIR}')
    linhas_relatorio.append(f'INPUT_DIR: {INPUT_DIR}')
    linhas_relatorio.append(f'DB_PATH: {DB_PATH}')
    linhas_relatorio.append(f'PERIODO_ANALISADO: {periodo_processamento}')
    linhas_relatorio.append('')

    manifesto, avisos_manifesto = ler_manifesto_email()
    for aviso in avisos_manifesto:
        print(f' [AVISO] {aviso}')
        linhas_relatorio.append(f'[AVISO] {aviso}')

    if manifesto:
        print(f" -> [E-MAIL] Threads encontradas:        {manifesto.get('total_threads', 0)}")
        print(f" -> [E-MAIL] E-mails vistos:             {manifesto.get('total_emails_vistos', 0)}")
        print(f" -> [E-MAIL] PDFs salvos no Drive:       {manifesto.get('total_arquivos_salvos', 0)}")
        print(f" -> [E-MAIL] Duplicidades ignoradas:     {manifesto.get('total_arquivos_ignorados', 0)}")
        linhas_relatorio.append(f"[E-MAIL] Threads encontradas: {manifesto.get('total_threads', 0)}")
        linhas_relatorio.append(f"[E-MAIL] E-mails vistos: {manifesto.get('total_emails_vistos', 0)}")
        linhas_relatorio.append(f"[E-MAIL] PDFs salvos no Drive: {manifesto.get('total_arquivos_salvos', 0)}")
        linhas_relatorio.append(f"[E-MAIL] Duplicidades ignoradas: {manifesto.get('total_arquivos_ignorados', 0)}")
        linhas_relatorio.append('')

    try:
        db_docs_todos = carregar_docs_db()
        db_docs = [doc for doc in db_docs_todos if get_periodo(doc) == periodo_processamento]
    except Exception as exc:
        print(f' [ERRO] {exc}')
        with open(RELATORIO_AUDITORIA, 'w', encoding='utf-8') as file:
            file.write(f'ERRO AO ABRIR BANCO: {exc}\n')
        return 1

    docs_ultima_leva = []
    if execution_id_atual:
        docs_ultima_leva = [
            doc for doc in db_docs
            if str(doc.get('execution_id') or '').strip() == execution_id_atual
        ]

    totais_ultima_leva = calcular_totais_equivalentes_master(docs_ultima_leva)
    totais_base_completa = calcular_totais_equivalentes_master(db_docs)

    pdfs_entrada = listar_pdfs_entrada()
    total_db = len(db_docs)
    print(f' -> [DB] Documentos processados no banco ({periodo_processamento}): {total_db}')
    linhas_relatorio.append(f'[DB] Documentos processados no banco ({periodo_processamento}): {total_db}')

    # Totais equivalentes ao MASTER
    total_cte_nf_ultima = (
        totais_ultima_leva['notas_total_prestacao'] +
        totais_ultima_leva['notas_total_nota']
    )

    total_cte_nf_base = (
        totais_base_completa['notas_total_prestacao'] +
        totais_base_completa['notas_total_nota']
    )

    print('')
    print(' -> Totais equivalentes ao MASTER | ÚLTIMA LEVA PROCESSADA...')
    print(
        f"    Notas_e_CTEs | qtd_docs: {totais_ultima_leva['notas_ctes_qtd_docs']} | "
        f"Valor Total de NFe e CTE: {money(total_cte_nf_ultima)}"
    )
    print(
        f"    Boletos      | qtd_docs: {totais_ultima_leva['boletos_qtd_docs']} | "
        f"Valor do Documento: {money(totais_ultima_leva['boletos_total_documento'])}"
    )
    print(
        f"    Demonstrativos | qtd_docs: {totais_ultima_leva['dem_qtd_docs']} | "
        f"Valor da Nota: {money(totais_ultima_leva['dem_total_valor_nota'])}"
    )

    print('')
    print(' -> Totais equivalentes ao MASTER | BASE COMPLETA...')
    print(
        f"    Notas_e_CTEs | qtd_docs: {totais_base_completa['notas_ctes_qtd_docs']} | "
        f"Valor Total de NFe e CTE: {money(total_cte_nf_base)}"
    )
    print(
        f"    Boletos      | qtd_docs: {totais_base_completa['boletos_qtd_docs']} | "
        f"Valor do Documento: {money(totais_base_completa['boletos_total_documento'])}"
    )
    print(
        f"    Demonstrativos | qtd_docs: {totais_base_completa['dem_qtd_docs']} | "
        f"Valor da Nota: {money(totais_base_completa['dem_total_valor_nota'])}"
    )

    linhas_relatorio.append('')
    linhas_relatorio.append('[INFO] Totais equivalentes ao MASTER | ÚLTIMA LEVA PROCESSADA:')
    linhas_relatorio.append(
        f"[TOTAL][ULTIMA_LEVA] Notas_e_CTEs | qtd_docs={totais_ultima_leva['notas_ctes_qtd_docs']} | "
        f"Valor Total de NFe e CTE={money(total_cte_nf_ultima)}"
    )
    linhas_relatorio.append(
        f"[TOTAL][ULTIMA_LEVA] Boletos | qtd_docs={totais_ultima_leva['boletos_qtd_docs']} | "
        f"Valor do Documento={money(totais_ultima_leva['boletos_total_documento'])}"
    )
    linhas_relatorio.append(
        f"[TOTAL][ULTIMA_LEVA] Demonstrativos | qtd_docs={totais_ultima_leva['dem_qtd_docs']} | "
        f"Valor da Nota={money(totais_ultima_leva['dem_total_valor_nota'])}"
    )

    linhas_relatorio.append('')
    linhas_relatorio.append('[INFO] Totais equivalentes ao MASTER | BASE COMPLETA:')
    linhas_relatorio.append(
        f"[TOTAL][BASE_COMPLETA] Notas_e_CTEs | qtd_docs={totais_base_completa['notas_ctes_qtd_docs']} | "
        f"Valor Total de NFe e CTE={money(total_cte_nf_base)}"
    )
    linhas_relatorio.append(
        f"[TOTAL][BASE_COMPLETA] Boletos | qtd_docs={totais_base_completa['boletos_qtd_docs']} | "
        f"Valor do Documento={money(totais_base_completa['boletos_total_documento'])}"
    )
    linhas_relatorio.append(
        f"[TOTAL][BASE_COMPLETA] Demonstrativos | qtd_docs={totais_base_completa['dem_qtd_docs']} | "
        f"Valor da Nota={money(totais_base_completa['dem_total_valor_nota'])}"
    )

    linhas_relatorio.append('')
    linhas_relatorio.append('[TRACE] Composição dos totais equivalentes ao MASTER:')
    for item in totais_base_completa['trace']:
        linhas_relatorio.append(
            f" - tipo={item['tipo']} | arquivo={item['arquivo']} | "
            f"doc={item['numero_documento']} | lote={item['lote_fatura']} | "
            f"campo={item['campo_master']} | valor={money(item['valor'])}"
        )



    if manifesto:
        total_salvos = int(manifesto.get('total_arquivos_salvos', 0) or 0)
        if total_salvos != total_db:
            erros_criticos += 1
            msg = f'Divergência entre PDFs salvos pelo Apps Script ({total_salvos}) e documentos no banco ({total_db}).'
            print(f' [!] {msg}')
            linhas_relatorio.append(f'[ALERTA] {msg}')

    # -------------------------
    # COMPARAÇÃO BANCO x PASTAS FINAIS
    # -------------------------
    pdfs_saida = [
        path for path in listar_pdfs_saida()
        if f'/{periodo_processamento}/' in norm_relpath(path)
    ]

    esperados_saida = []
    for doc in db_docs:
        doc_type = normalizar_doc_type(doc.get('document_type'))
        if doc_type in {'NFSE', 'CTE_OS', 'BOL', 'DEM'}:
            esperados_saida.append(montar_caminho_relativo_saida(doc))

    set_esperados = set(esperados_saida)
    set_saida = set(pdfs_saida)

    faltando_na_saida = sorted(set_esperados - set_saida)
    sobrando_na_saida = sorted(set_saida - set_esperados)

    print(f' -> [SAÍDA] PDFs físicos nas pastas finais: {len(pdfs_saida)}')
    print(f' -> [SAÍDA] PDFs esperados a partir do banco: {len(esperados_saida)}')
    linhas_relatorio.append(f'[SAÍDA] PDFs físicos nas pastas finais: {len(pdfs_saida)}')
    linhas_relatorio.append(f'[SAÍDA] PDFs esperados a partir do banco: {len(esperados_saida)}')

    if len(pdfs_saida) != len(esperados_saida):
        erros_criticos += 1
        msg = f'Divergência entre PDFs nas pastas finais ({len(pdfs_saida)}) e PDFs válidos no banco ({len(esperados_saida)}).'
        print(f' [!] {msg}')
        linhas_relatorio.append(f'[ALERTA] {msg}')

    if faltando_na_saida:
        erros_criticos += len(faltando_na_saida)
        print('\n -> PDFs esperados no banco, mas ausentes nas pastas finais:')
        linhas_relatorio.append('')
        linhas_relatorio.append('[ALERTA] PDFs esperados no banco, mas ausentes nas pastas finais:')
        for nome in faltando_na_saida:
            print(f'    - {nome}')
            linhas_relatorio.append(f' - {nome}')

    if sobrando_na_saida:
        erros_criticos += len(sobrando_na_saida)
        print('\n -> PDFs existentes nas pastas finais, mas sem correspondência no banco:')
        linhas_relatorio.append('')
        linhas_relatorio.append('[ALERTA] PDFs existentes nas pastas finais, mas sem correspondência no banco:')
        for nome in sobrando_na_saida:
            print(f'    - {nome}')
            linhas_relatorio.append(f' - {nome}')

    # -------------------------
    # RASTREIO DETALHADO DE BOLETOS
    # -------------------------
    diag_boletos = diagnosticar_boletos(db_docs, pdfs_saida)

    print('')
    print(' -> Rastreio detalhado de boletos...')
    print(f"    Boletos no banco: {len(diag_boletos['boletos_db'])}")
    print(f"    Boletos nas pastas finais: {len(diag_boletos['boletos_saida'])}")

    linhas_relatorio.append('')
    linhas_relatorio.append('[TRACE] RASTREIO DETALHADO DE BOLETOS')
    linhas_relatorio.append(f"[TRACE] Boletos no banco: {len(diag_boletos['boletos_db'])}")
    linhas_relatorio.append(f"[TRACE] Boletos nas pastas finais: {len(diag_boletos['boletos_saida'])}")

    for item in diag_boletos['boletos_db']:
        linhas_relatorio.append(
            '[TRACE][DB][BOL] '
            f"src={item['source_filename']} | "
            f"doc={item['numero_documento']} | "
            f"lote={item['lote_fatura']} | "
            f"type={item['document_type']} | "
            f"path={item['path_esperado']}"
        )

    for relpath in diag_boletos['boletos_saida']:
        linhas_relatorio.append(f'[TRACE][SAIDA][BOL] {relpath}')

    if diag_boletos['faltando_na_saida']:
        linhas_relatorio.append('')
        linhas_relatorio.append('[ALERTA] Boletos que estão no banco, mas não estão fisicamente na saída:')
        for path in diag_boletos['faltando_na_saida']:
            linhas_relatorio.append(f' - {path}')

    if diag_boletos['sobrando_na_saida']:
        linhas_relatorio.append('')
        linhas_relatorio.append('[ALERTA] Boletos que estão fisicamente na saída, mas não batem com o banco:')
        for item in diag_boletos['sobrando_na_saida']:
            linhas_relatorio.append(
                f" - arquivo_saida={item['arquivo_saida']} | "
                f"doc_saida={item['numero_documento_saida']} | "
                f"fornecedor_saida={item['fornecedor_saida']} | "
                f"motivo={item['motivo_suspeito']}"
            )
            for match in item['matches_db']:
                linhas_relatorio.append(
                    f"   -> match_db: src={match['source_filename']} | "
                    f"doc={match['numero_documento']} | "
                    f"lote={match['lote_fatura']} | "
                    f"type={match['document_type']} | "
                    f"path={match['path_esperado']}"
                )

    diag_notas = diagnosticar_notas_ctes(db_docs, pdfs_saida)

    print('')
    print(' -> Rastreio detalhado de notas/CTEs...')
    print(f"    Notas/CTEs no banco: {len(diag_notas['notas_db'])}")
    print(f"    Notas/CTEs nas pastas finais: {len(diag_notas['notas_saida'])}")

    linhas_relatorio.append('')
    linhas_relatorio.append('[TRACE] RASTREIO DETALHADO DE NOTAS/CTEs')
    linhas_relatorio.append(f"[TRACE] Notas/CTEs no banco: {len(diag_notas['notas_db'])}")
    linhas_relatorio.append(f"[TRACE] Notas/CTEs nas pastas finais: {len(diag_notas['notas_saida'])}")

    for item in diag_notas['notas_db']:
        linhas_relatorio.append(
            '[TRACE][DB][NOTA] '
            f"src={item['source_filename']} | "
            f"doc={item['numero_documento']} | "
            f"lote={item['lote_fatura']} | "
            f"type={item['document_type']} | "
            f"path={item['path_esperado']}"
        )

    for relpath in diag_notas['notas_saida']:
        linhas_relatorio.append(f'[TRACE][SAIDA][NOTA] {relpath}')

    if diag_notas['faltando_na_saida']:
        linhas_relatorio.append('')
        linhas_relatorio.append('[ALERTA] Notas/CTEs que estao no banco, mas nao estao fisicamente na saida:')
        for path in diag_notas['faltando_na_saida']:
            linhas_relatorio.append(f' - {path}')

    if diag_notas['sobrando_na_saida']:
        linhas_relatorio.append('')
        linhas_relatorio.append('[ALERTA] Notas/CTEs que estao fisicamente na saida, mas nao batem com o banco:')
        for item in diag_notas['sobrando_na_saida']:
            linhas_relatorio.append(
                f" - arquivo_saida={item['arquivo_saida']} | "
                f"doc_saida={item['numero_documento_saida']} | "
                f"motivo={item['motivo_suspeito']}"
            )
            for match in item['matches_db']:
                linhas_relatorio.append(
                    f"   -> match_db: src={match['source_filename']} | "
                    f"doc={match['numero_documento']} | "
                    f"lote={match['lote_fatura']} | "
                    f"type={match['document_type']} | "
                    f"path={match['path_esperado']}"
                )

    counts = defaultdict(int)
    lotes: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    unknown_docs: List[str] = []
    duplicate_keys: Dict[Tuple[str, str, str, str], List[str]] = defaultdict(list)

    for doc in db_docs:
        source_filename = str(doc.get('source_filename') or '')
        doc_type = normalizar_doc_type(doc.get('document_type'))
        counts[doc_type] += 1
        lote_id = get_lote_id(source_filename)
        lotes[lote_id][doc_type].append(doc)

        if doc_type == 'UNKNOWN':
            unknown_docs.append(source_filename)

        dup_key = (
            doc_type,
            str(doc.get('numero_documento') or '').strip(),
            str(doc.get('lote_fatura') or '').strip(),
            f"{safe_float(doc.get('valor_total_documento') or doc.get('valor_fatura')):.2f}",
        )
        duplicate_keys[dup_key].append(source_filename)

    print(f" -> [DB] NFSE: {counts['NFSE']} | CTE_OS: {counts['CTE_OS']} | BOL: {counts['BOL']} | DEM: {counts['DEM']} | UNKNOWN: {counts['UNKNOWN']}")
    linhas_relatorio.append(
        f"[DB] NFSE={counts['NFSE']} | CTE_OS={counts['CTE_OS']} | BOL={counts['BOL']} | DEM={counts['DEM']} | UNKNOWN={counts['UNKNOWN']}"
    )
    linhas_relatorio.append('')

    total_notas = counts['NFSE'] + counts['CTE_OS']
    total_boletos = counts['BOL']
    if total_notas != total_boletos:
        erros_criticos += 1
        msg = f'Quantidade global divergente: Notas/CTEs={total_notas} vs Boletos={total_boletos}.'
        print(f' [!] {msg}')
        linhas_relatorio.append(f'[ALERTA] {msg}')

    if unknown_docs:
        erros_criticos += len(unknown_docs)
        print('\n -> Arquivos classificados como UNKNOWN:')
        linhas_relatorio.append('')
        linhas_relatorio.append('[ALERTA] Arquivos classificados como UNKNOWN:')
        for name in unknown_docs:
            print(f'    - {name}')
            linhas_relatorio.append(f' - {name}')

    if pdfs_entrada:
        print('\n -> PDFs ainda presentes em Idocs_Prosegur:')
        linhas_relatorio.append('')
        linhas_relatorio.append('[INFO] PDFs ainda presentes em Idocs_Prosegur:')
        for name in pdfs_entrada:
            print(f'    - {name}')
            linhas_relatorio.append(f' - {name}')

    # Duplicidade lógica
    duplicidades_logicas = []
    for dup_key, arquivos in duplicate_keys.items():
        doc_type, numero_documento, lote_fatura, valor = dup_key
        if len(arquivos) > 1 and numero_documento:
            duplicidades_logicas.append((dup_key, arquivos))

    if duplicidades_logicas:
        erros_criticos += len(duplicidades_logicas)
        print('\n -> Possíveis duplicidades lógicas detectadas:')
        linhas_relatorio.append('')
        linhas_relatorio.append('[ALERTA] Possíveis duplicidades lógicas detectadas:')
        for dup_key, arquivos in duplicidades_logicas:
            doc_type, numero_documento, lote_fatura, valor = dup_key
            msg = f'{doc_type} | doc={numero_documento} | lote={lote_fatura or "SEM_LOTE"} | valor={valor} | arquivos={arquivos}'
            print(f'    - {msg}')
            linhas_relatorio.append(f' - {msg}')

    print('\n -> Verificando trios por lote e simetria de valores...')
    linhas_relatorio.append('')
    linhas_relatorio.append('[INFO] Verificação por lote:')

    lotes_incompletos = 0
    lotes_divergentes = 0

    for lote_id in sorted(lotes.keys()):
        docs_por_tipo = lotes[lote_id]
        notas = docs_por_tipo.get('NFSE', []) + docs_por_tipo.get('CTE_OS', [])
        boletos = docs_por_tipo.get('BOL', [])
        dems = docs_por_tipo.get('DEM', [])
        unknowns = docs_por_tipo.get('UNKNOWN', [])

        if len(notas) != 1 or len(boletos) != 1 or len(dems) != 1:
            lotes_incompletos += 1
            erros_criticos += 1
            msg = (
                f'Lote {lote_id} incompleto/duplicado | '
                f'Notas={len(notas)} {[d.get("source_filename") for d in notas]} | '
                f'Boletos={len(boletos)} {[d.get("source_filename") for d in boletos]} | '
                f'DEM={len(dems)} {[d.get("source_filename") for d in dems]} | '
                f'UNKNOWN={len(unknowns)} {[d.get("source_filename") for d in unknowns]}'
            )
            print(f' [!] {msg}')
            linhas_relatorio.append(f'[ALERTA] {msg}')
            continue

        nf = notas[0]
        bol = boletos[0]
        dem = dems[0]
        val_nf, val_bol, val_dem = extrair_valores_lote(nf, bol, dem)

        diff_nf_bol = round(abs(val_nf - val_bol), 2)
        diff_nf_dem = round(abs(val_nf - val_dem), 2)

        if diff_nf_bol > TOLERANCIA_VALOR or diff_nf_dem > TOLERANCIA_VALOR:
            lotes_divergentes += 1
            erros_criticos += 1
            msg = (
                f'Lote {lote_id} com divergência | '
                f'Nota/CTe={money(val_nf)} ({nf.get("source_filename")}) | '
                f'Boleto={money(val_bol)} ({bol.get("source_filename")}) | '
                f'DEM={money(val_dem)} ({dem.get("source_filename")})'
            )
            print(f' [!] {msg}')
            linhas_relatorio.append(f'[ALERTA] {msg}')

    linhas_relatorio.append('')
    linhas_relatorio.append(f'[RESUMO] Lotes analisados: {len(lotes)}')
    linhas_relatorio.append(f'[RESUMO] Lotes incompletos/duplicados: {lotes_incompletos}')
    linhas_relatorio.append(f'[RESUMO] Lotes com divergência de valores: {lotes_divergentes}')
    linhas_relatorio.append(f'[RESUMO] UNKNOWN no banco: {len(unknown_docs)}')
    linhas_relatorio.append(f'[RESUMO] PDFs ainda em Idocs_Prosegur: {len(pdfs_entrada)}')
    linhas_relatorio.append(f'[RESUMO] PDFs físicos na saída: {len(pdfs_saida)}')
    linhas_relatorio.append(f'[RESUMO] PDFs esperados via banco: {len(esperados_saida)}')
    linhas_relatorio.append(f'[RESUMO] Faltando na saída: {len(faltando_na_saida)}')
    linhas_relatorio.append(f'[RESUMO] Sobrando na saída: {len(sobrando_na_saida)}')
    linhas_relatorio.append(f'[RESUMO] Erros críticos: {erros_criticos}')

    os.makedirs(os.path.dirname(RELATORIO_AUDITORIA), exist_ok=True)
    with open(RELATORIO_AUDITORIA, 'w', encoding='utf-8') as file:
        file.write('\n'.join(linhas_relatorio) + '\n')

    print('\n' + '-' * 72)
    print(f' LOTES ANALISADOS: {len(lotes)}')
    print(f' LOTES INCOMPLETOS/DUPLICADOS: {lotes_incompletos}')
    print(f' LOTES COM DIVERGÊNCIA DE VALORES: {lotes_divergentes}')
    print(f' UNKNOWN NO BANCO: {len(unknown_docs)}')
    print(f' PDFs AINDA EM IDOCS_PROSEGUR: {len(pdfs_entrada)}')
    print(f' PDFs FÍSICOS NA SAÍDA: {len(pdfs_saida)}')
    print(f' PDFs ESPERADOS VIA BANCO: {len(esperados_saida)}')
    print(f' FALTANDO NA SAÍDA: {len(faltando_na_saida)}')
    print(f' SOBRANDO NA SAÍDA: {len(sobrando_na_saida)}')
    if erros_criticos == 0:
        print(' STATUS DA AUDITORIA: [OK] Nenhuma divergência encontrada.')
    else:
        print(f' STATUS DA AUDITORIA: [ALERTA] {erros_criticos} divergências detectadas!')
    print('=' * 72 + '\n')
    print(f'Relatório salvo em: {RELATORIO_AUDITORIA}')


    return erros_criticos


if __name__ == '__main__':
    erros = executar_auditoria()
    if erros > 0:
        print(f'\nATENÇÃO: Foram encontrados {erros} pontos de auditoria.')
    else:
        print('\nSucesso: Nenhuma inconsistência encontrada.')
