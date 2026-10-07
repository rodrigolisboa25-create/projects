import os
import re
from datetime import datetime
from typing import Dict, List, Tuple, Any

import pandas as pd


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
OUTPUT_DIR = os.path.join(ROOT_DIR, 'PROSEGUR_PROCESS')

MASTER_PATH = os.path.join(OUTPUT_DIR, 'MASTER_Relatorio_Prosegur.xlsx')
OFICIAL_PATH = os.path.join(OUTPUT_DIR, 'Relatorio_prosegur_oficial.xlsx')


def periodo_atual() -> str:
    return datetime.now().strftime('%m-%Y')


def filtrar_periodo_master(df: pd.DataFrame) -> pd.DataFrame:
    if 'PERIODO' not in df.columns:
        return df.iloc[0:0].copy()
    return df[df['PERIODO'].astype(str).str.strip() == periodo_atual()].copy()


def filtrar_periodo_oficial(df: pd.DataFrame) -> pd.DataFrame:
    if {'MES_COMPETENCIA', 'ANO_COMPETENCIA'}.issubset(df.columns):
        mes_atual = datetime.now().month
        ano_atual = datetime.now().year
        mes = pd.to_numeric(df['MES_COMPETENCIA'], errors='coerce')
        ano = pd.to_numeric(df['ANO_COMPETENCIA'], errors='coerce')
        return df[(mes == mes_atual) & (ano == ano_atual)].copy()
    return df


def money(value: float) -> str:
    return f'R$ {value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def safe_float(value: Any) -> float:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return 0.0
        if value == '':
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def normalize_doc_number(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    s = str(value).strip()
    if re.fullmatch(r'\d+\.0', s):
        s = s[:-2]
    return re.sub(r'\D', '', s)


def normalize_empresa_oficial(value: Any) -> str:
    s = str(value or '').upper()

    if 'FISIA' in s:
        return 'FISIA'

    return 'SBF'


def normalize_empresa_master(value: Any) -> str:
    s = str(value or '').upper().strip()
    if 'FISIA' in s:
        return 'FISIA'
    return 'SBF'


def ler_base_oficial(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f'Arquivo oficial não encontrado: {path}')

    df = pd.read_excel(path, sheet_name='Notas Fiscais')
    df = df.copy()

    # Garante nomes consistentes
    df.columns = [str(col).strip() for col in df.columns]
    df = filtrar_periodo_oficial(df)

    col_segmento = 'DESCRICAO_SEGMENTO'
    col_empresa = 'RAZAO_SOCIAL'
    col_nf = 'NUMERO_NF'
    col_valor = 'VALOR_NOTA_FISCAL'

    colunas_obrigatorias = [col_segmento, col_empresa, col_nf, col_valor]
    faltantes = [c for c in colunas_obrigatorias if c not in df.columns]
    if faltantes:
        raise ValueError(
            f'Colunas obrigatórias não encontradas na aba "Notas Fiscais": {faltantes}'
        )

    df[col_segmento] = df[col_segmento].astype(str).str.strip().str.upper()

    df = df[
        df[col_segmento].isin([
            'TRANSPORTE DE VALORES',
            'TESOURARIA'
        ])
    ].copy()

    df['EMPRESA_NORM'] = df[col_empresa].apply(normalize_empresa_oficial)
    df['NOTA_NORM'] = df[col_nf].apply(normalize_doc_number)
    df['TIPO_NF_NORM'] = df[col_segmento].apply(
        lambda x: 'CTE' if str(x).strip().upper() == 'TRANSPORTE DE VALORES' else 'NF'
    )
    df['VALOR_NORM'] = pd.to_numeric(df[col_valor], errors='coerce').fillna(0)

    df = df[df['NOTA_NORM'] != ''].copy()

    return df[['EMPRESA_NORM', 'NOTA_NORM', 'TIPO_NF_NORM', 'VALOR_NORM']]

def ler_master_notas(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f'MASTER não encontrado: {path}')

    df = pd.read_excel(path, sheet_name='Notas_e_CTEs')
    df = df.copy()
    df = filtrar_periodo_master(df)

    df['EMPRESA_NORM'] = df['EMPRESA'].apply(normalize_empresa_master)

    def extrair_nota(row):
        if str(row.get('TIPO_DOC') or '').upper().strip() == 'NFSE':
            return normalize_doc_number(row.get('Nº Nota Fiscal Eletrônica'))
        return normalize_doc_number(row.get('Nº DOCUMENTO'))

    df['NOTA_NORM'] = df.apply(extrair_nota, axis=1)

    def extrair_tipo(row):
        return 'NF' if str(row.get('TIPO_DOC') or '').upper().strip() == 'NFSE' else 'CTE'

    df['TIPO_NF_NORM'] = df.apply(extrair_tipo, axis=1)

    df['VALOR_TOTAL_NOTA'] = (
        pd.to_numeric(df.get('VALOR TOTAL DA PRESTAÇÃO DO SERVIÇO', 0), errors='coerce').fillna(0)
        + pd.to_numeric(df.get('VALOR DA NOTA (R$)', 0), errors='coerce').fillna(0)
    )

    df = df[df['NOTA_NORM'] != ''].copy()

    return df[['EMPRESA_NORM', 'NOTA_NORM', 'TIPO_NF_NORM', 'VALOR_TOTAL_NOTA', 'LOJA', 'TIPO_DOC']]


def ler_master_boletos(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name='Boletos')
    df = df.copy()
    df = filtrar_periodo_master(df)

    df['EMPRESA_NORM'] = df['EMPRESA'].apply(normalize_empresa_master)

    def extrair_nota_boleto(value):
        s = str(value or '').strip().upper()
        # exemplos: 01-IC-21245 / 01-FB-2183
        m = re.search(r'(\d+)$', s)
        return m.group(1) if m else normalize_doc_number(s)

    df['NOTA_NORM'] = df['Nº DOCUMENTO'].apply(extrair_nota_boleto)
    df['VALOR_DOC_NORM'] = pd.to_numeric(df['Valor do Documento'], errors='coerce').fillna(0)

    df = df[df['NOTA_NORM'] != ''].copy()

    return df[['EMPRESA_NORM', 'NOTA_NORM', 'VALOR_DOC_NORM']]


def ler_master_demonstrativos(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name='Demonstrativos')
    df = df.copy()
    df = filtrar_periodo_master(df)

    df['EMPRESA_NORM'] = df['EMPRESA'].apply(normalize_empresa_master)
    df['NOTA_NORM'] = df['Nota Fiscal'].apply(normalize_doc_number)
    df['VALOR_NOTA_NORM'] = pd.to_numeric(df['Valor da Nota'], errors='coerce').fillna(0)

    # 1 nota por documento: soma única por NOTA/EMPRESA
    agg = (
        df.groupby(['EMPRESA_NORM', 'NOTA_NORM'], dropna=False, as_index=False)
          .agg({'VALOR_NOTA_NORM': 'sum'})
    )

    agg = agg[agg['NOTA_NORM'] != ''].copy()
    return agg


def resumo_por_empresa(df_oficial: pd.DataFrame, df_master_notas: pd.DataFrame,
                       df_bol: pd.DataFrame, df_dem: pd.DataFrame) -> List[str]:
    linhas: List[str] = []

    empresas = sorted(set(df_oficial['EMPRESA_NORM'].unique()) | set(df_master_notas['EMPRESA_NORM'].unique()))

    for emp in empresas:
        of_emp = df_oficial[df_oficial['EMPRESA_NORM'] == emp]
        mn_emp = df_master_notas[df_master_notas['EMPRESA_NORM'] == emp]
        mb_emp = df_bol[df_bol['EMPRESA_NORM'] == emp]
        md_emp = df_dem[df_dem['EMPRESA_NORM'] == emp]

        linhas.append(f'EMPRESA: {emp}')
        linhas.append(
            f'  Oficial | notas={len(of_emp)} | valor={money(of_emp["VALOR_NORM"].sum())}'
        )
        linhas.append(
            f'  MASTER Notas_e_CTEs | notas={len(mn_emp)} | valor={money(mn_emp["VALOR_TOTAL_NOTA"].sum())}'
        )
        linhas.append(
            f'  MASTER Boletos | notas únicas={mb_emp["NOTA_NORM"].nunique()} | valor={money(mb_emp["VALOR_DOC_NORM"].sum())}'
        )
        linhas.append(
            f'  MASTER Demonstrativos | notas únicas={md_emp["NOTA_NORM"].nunique()} | valor={money(md_emp["VALOR_NOTA_NORM"].sum())}'
        )
        linhas.append('')

    return linhas


def divergencias_notas(df_oficial: pd.DataFrame, df_master_notas: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    chaves_of = set(zip(df_oficial['EMPRESA_NORM'], df_oficial['NOTA_NORM']))
    chaves_mn = set(zip(df_master_notas['EMPRESA_NORM'], df_master_notas['NOTA_NORM']))

    faltando = chaves_of - chaves_mn
    sobrando = chaves_mn - chaves_of
    comuns = chaves_of & chaves_mn

    df_faltando = df_oficial[df_oficial.apply(lambda r: (r['EMPRESA_NORM'], r['NOTA_NORM']) in faltando, axis=1)].copy()
    df_sobrando = df_master_notas[df_master_notas.apply(lambda r: (r['EMPRESA_NORM'], r['NOTA_NORM']) in sobrando, axis=1)].copy()

    merged = pd.merge(
        df_oficial,
        df_master_notas,
        on=['EMPRESA_NORM', 'NOTA_NORM'],
        suffixes=('_OFICIAL', '_MASTER')
    )
    merged['DIF_VALOR'] = (merged['VALOR_NORM'] - merged['VALOR_TOTAL_NOTA']).round(2)
    df_valor_div = merged[merged['DIF_VALOR'].abs() > 0.01].copy()

    return df_faltando, df_sobrando, df_valor_div


def cruzar_notas_faltantes_com_boletos_e_dem(df_faltando: pd.DataFrame, df_bol: pd.DataFrame, df_dem: pd.DataFrame) -> pd.DataFrame:
    falt = df_faltando.copy()
    if falt.empty:
        falt['EXISTE_BOLETO_MASTER'] = []
        falt['EXISTE_DEM_MASTER'] = []
        return falt

    bol_set = set(zip(df_bol['EMPRESA_NORM'], df_bol['NOTA_NORM']))
    dem_set = set(zip(df_dem['EMPRESA_NORM'], df_dem['NOTA_NORM']))

    falt['EXISTE_BOLETO_MASTER'] = falt.apply(
        lambda r: (r['EMPRESA_NORM'], r['NOTA_NORM']) in bol_set,
        axis=1
    )
    falt['EXISTE_DEM_MASTER'] = falt.apply(
        lambda r: (r['EMPRESA_NORM'], r['NOTA_NORM']) in dem_set,
        axis=1
    )
    return falt


def analisar() -> str:
    df_oficial = ler_base_oficial(OFICIAL_PATH)
    df_master_notas = ler_master_notas(MASTER_PATH)
    df_master_bol = ler_master_boletos(MASTER_PATH)
    df_master_dem = ler_master_demonstrativos(MASTER_PATH)

    df_faltando, df_sobrando, df_valor_div = divergencias_notas(df_oficial, df_master_notas)
    df_faltando_cruzado = cruzar_notas_faltantes_com_boletos_e_dem(df_faltando, df_master_bol, df_master_dem)

    linhas: List[str] = []
    linhas.append(f'ANALISE BASE PROSEGUR | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    linhas.append('=' * 90)
    linhas.append(f'Periodo analisado: {periodo_atual()}')
    linhas.append(f'Arquivo oficial: {OFICIAL_PATH}')
    linhas.append(f'Arquivo master:  {MASTER_PATH}')
    linhas.append('')

    linhas.append('RESUMO GERAL')
    linhas.append(f'  Oficial - notas: {len(df_oficial)} | valor: {money(df_oficial["VALOR_NORM"].sum())}')
    linhas.append(f'  MASTER Notas_e_CTEs - notas: {len(df_master_notas)} | valor: {money(df_master_notas["VALOR_TOTAL_NOTA"].sum())}')
    linhas.append(f'  MASTER Boletos - notas únicas: {df_master_bol["NOTA_NORM"].nunique()} | valor: {money(df_master_bol["VALOR_DOC_NORM"].sum())}')
    linhas.append(f'  MASTER Demonstrativos - notas únicas: {df_master_dem["NOTA_NORM"].nunique()} | valor: {money(df_master_dem["VALOR_NOTA_NORM"].sum())}')
    linhas.append('')

    linhas.append('RESUMO POR EMPRESA')
    linhas.extend(resumo_por_empresa(df_oficial, df_master_notas, df_master_bol, df_master_dem))

    linhas.append('NOTAS OFICIAIS QUE NÃO ESTÃO EM Notas_e_CTEs')
    if df_faltando_cruzado.empty:
        linhas.append('  Nenhuma.')
    else:
        for _, row in df_faltando_cruzado.sort_values(['EMPRESA_NORM', 'NOTA_NORM']).iterrows():
         linhas.append(
            f"  {row['EMPRESA_NORM']} | nota={row['NOTA_NORM']} | tipo={row['TIPO_NF_NORM']} | "
            f"valor={money(row['VALOR_NORM'])} | "
            f"boleto_master={'SIM' if row['EXISTE_BOLETO_MASTER'] else 'NAO'} | "
            f"dem_master={'SIM' if row['EXISTE_DEM_MASTER'] else 'NAO'}"
        )

    linhas.append('')

    linhas.append('NOTAS QUE ESTÃO A MAIS EM Notas_e_CTEs')
    if df_sobrando.empty:
        linhas.append('  Nenhuma.')
    else:
        for _, row in df_sobrando.sort_values(['EMPRESA_NORM', 'NOTA_NORM']).iterrows():
            linhas.append(
                f"  {row['EMPRESA_NORM']} | nota={row['NOTA_NORM']} | tipo_master={row['TIPO_NF_NORM']} | "
                f"valor_master={money(row['VALOR_TOTAL_NOTA'])} | loja={row['LOJA']}"
            )
    linhas.append('')

    linhas.append('NOTAS COM DIVERGÊNCIA DE VALOR')
    if df_valor_div.empty:
        linhas.append('  Nenhuma.')
    else:
        for _, row in df_valor_div.sort_values(['EMPRESA_NORM', 'NOTA_NORM']).iterrows():
            linhas.append(
                f"  {row['EMPRESA_NORM']} | nota={row['NOTA_NORM']} | "
                f"valor_oficial={money(row['VALOR_NORM'])} | valor_master={money(row['VALOR_TOTAL_NOTA'])} | "
                f"dif={money(row['DIF_VALOR'])}"
            )
    linhas.append('')

    return '\n'.join(linhas) + '\n'


if __name__ == '__main__':
    conteudo = analisar()

    print('\n' + '=' * 100)
    print('ANALISE BASE PROSEGUR')
    print('=' * 100)
    print(conteudo)
    print('=' * 100)
