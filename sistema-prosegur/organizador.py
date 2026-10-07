import os
import shutil

ROOT = r"g:\Drives compartilhados\OPERAÇÕES FINANCEIRAS\Antigravity"
SYSTEM = os.path.join(ROOT, "SISTEMA_PROSEGUR")
LEGACY = os.path.join(SYSTEM, "ARQUIVOS_ANTIGOS")

def organizar():
    if not os.path.exists(SYSTEM): os.makedirs(SYSTEM)
    if not os.path.exists(LEGACY): os.makedirs(LEGACY)

    # 1. Arquivos para Mover para a Raiz do Sistema (Bases e Config)
    bases_e_config = [
        "Base_Forn.xlsx", "requirements.txt", ".env", "Apps_Script_Prosegur.js"
    ]

    # 2. Arquivos para Mover para Backup/Legacy (Ferramentas antigas e redundantes)
    redundantes = [
        "leitor_emails.py", "leitor_prosegur.py", "main.py", "processador_pdf.py",
        "verificador_pdf.py", "onde_estao.py", "Bases de informações_PROCV.xlsx",
        "Bases_Forn.xlsx", "Extracao_Final" # Pasta antiga
    ]

    print("Iniciando organização...")

    for f in bases_e_config:
        src = os.path.join(ROOT, f)
        if os.path.exists(src):
            try:
                # Se for arquivo, move. Se for pasta, move árvore.
                shutil.move(src, os.path.join(SYSTEM, f))
                print(f"Movido para SISTEMA: {f}")
            except Exception as e: print(f"Erro ao mover {f}: {e}")

    for f in redundantes:
        src = os.path.join(ROOT, f)
        if os.path.exists(src):
            try:
                # Se for arquivo, move para LEGACY.
                shutil.move(src, os.path.join(LEGACY, f))
                print(f"Movido para LEGACY: {f}")
            except Exception as e: print(f"Erro ao mover {f}: {e}")

    print("Organização básica concluída.")

if __name__ == "__main__":
    organizar()
