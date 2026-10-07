import os
import shutil
import sqlite3
import json
from datetime import datetime
import pandas as pd
from dataclasses import asdict
from processador_pdf import analisar_pdf_extrair_dados, DocumentPayload

# --- CONFIGURAÇÃO DE CAMINHOS ABSOLUTOS ---
ROOT_DIR = r"g:\Drives compartilhados\OPERAÇÕES FINANCEIRAS\Antigravity"
SYSTEM_DIR = os.path.join(ROOT_DIR, "SISTEMA_PROSEGUR")
INPUT_DIR = os.path.join(ROOT_DIR, "Idocs_Prosegur")
OUTPUT_DIR = os.path.join(ROOT_DIR, "PROSEGUR_GRAVITY")
DB_PATH = os.path.join(SYSTEM_DIR, "documentos.db")
LOG_FILE = os.path.join(SYSTEM_DIR, "processamento.log")

def logar(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(msg)

# --- BANCO DE DADOS ---
def inicializar_db():
    if not os.path.exists(SYSTEM_DIR): os.makedirs(SYSTEM_DIR)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documentos (
            document_id TEXT PRIMARY KEY,
            source_filename TEXT,
            document_type TEXT,
            numero_documento TEXT,
            empresa_nome TEXT,
            numero_loja TEXT,
            codigo_forn TEXT,
            valor_total TEXT,
            data_emissao TEXT,
            data_vencimento TEXT,
            codigo_barras TEXT,
            tipo_servico TEXT,
            raw_payload TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def salvar_no_db(payload: DocumentPayload):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO documentos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        payload.document_id, payload.source_filename, payload.document_type,
        payload.numero_documento, payload.empresa_nome, payload.numero_loja,
        payload.codigo_forn, payload.valor_total_documento, payload.data_emissao,
        payload.data_vencimento, payload.codigo_barras, payload.tipo_servico,
        json.dumps(asdict(payload), default=str), datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()

# --- CONSOLIDAÇÃO EXCEL ---
def gerar_excels():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM documentos", conn)
    conn.close()
    if df.empty: return

    # 1. Excel Mensal (Mês Atual)
    mes_atual = datetime.now().strftime("%m-%Y")
    caminho_mensal = os.path.join(OUTPUT_DIR, mes_atual, f"Consolidado_Prosegur_{mes_atual}.xlsx")
    os.makedirs(os.path.dirname(caminho_mensal), exist_ok=True)
    df.to_excel(caminho_mensal, index=False)

    # 2. Excel MASTER (Histórico Completo)
    caminho_master = os.path.join(OUTPUT_DIR, "MASTER_Consolidado_Prosegur.xlsx")
    df.to_excel(caminho_master, index=False)
    logar(f"Excels atualizados: Mensal ({mes_atual}) e MASTER.")

# --- ORQUESTRAÇÃO ---
def executar_pipeline():
    logar("=== INICIANDO SISTEMA PROSEGUR ROBUSTO ===")
    inicializar_db()

    if not os.path.exists(INPUT_DIR): os.makedirs(INPUT_DIR)
    arquivos = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith('.pdf')]

    if not arquivos:
        logar("Nenhum arquivo na pasta de entrada.")
        return

    for f_name in arquivos:
        c_origem = os.path.join(INPUT_DIR, f_name)
        try:
            payload = analisar_pdf_extrair_dados(c_origem, f_name)
            salvar_no_db(payload)

            # Caminho de Destino Hierárquico
            mes_ano = datetime.now().strftime("%m-%Y")
            tipo_pasta = "Boletos" if payload.document_type == "BOL" else ("Demonstrativos" if payload.document_type == "DEM" else "Notas Fiscais")
            dest_dir = os.path.join(OUTPUT_DIR, mes_ano, payload.empresa_nome, tipo_pasta)
            os.makedirs(dest_dir, exist_ok=True)

            # Nome padronizado
            forn = payload.codigo_forn or "DESC"
            nota = payload.numero_documento or "DESC"
            novo_nome = f"{payload.document_type}_{forn}_{nota}.pdf".upper()
            c_destino = os.path.join(dest_dir, novo_nome)

            # Segurança: Copia -> Verifica -> Deleta
            shutil.copy2(c_origem, c_destino)
            if os.path.exists(c_destino):
                os.remove(c_origem)
                logar(f"   [OK] {f_name} -> {novo_nome}")
        except Exception as e:
            logar(f"   [ERRO] Falha ao processar {f_name}: {e}")

    gerar_excels()
    logar("=== PROCESSAMENTO FINALIZADO ===")

if __name__ == "__main__": executar_pipeline()
