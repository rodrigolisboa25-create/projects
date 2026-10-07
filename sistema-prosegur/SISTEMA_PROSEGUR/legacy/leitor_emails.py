import os
from imap_tools import MailBox, AND
from dotenv import load_dotenv

load_dotenv()

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
PASTA_DOWNLOADS = os.getenv("PASTA_DOWNLOADS", "downloads_temp")

def baixar_anexos_pdf_nao_lidos():
    """
    Conecta ao servidor IMAP, busca e-mails não lidos que contêm anexos,
    extrai os PDFs e salva na pasta temporária.
    Retorna uma lista de caminhos dos arquivos baixados.
    """
    if not EMAIL_HOST or not EMAIL_USER or not EMAIL_PASS:
        print("Erro: Credenciais de e-mail não configuradas no arquivo .env.")
        return []

    if not os.path.exists(PASTA_DOWNLOADS):
        os.makedirs(PASTA_DOWNLOADS)

    arquivos_baixados = []

    print(f"Conectando ao servidor: {EMAIL_HOST}...")
    try:
        with MailBox(EMAIL_HOST).login(EMAIL_USER, EMAIL_PASS) as mailbox:
            # Buscar apenas mensagens não lidas
            mensagens = mailbox.fetch(AND(seen=False))

            cont_mensagens = 0
            for msg in mensagens:
                cont_mensagens += 1
                for anexo in msg.attachments:
                    if anexo.filename.lower().endswith('.pdf'):
                        anexo_path = os.path.join(PASTA_DOWNLOADS, f"{msg.uid}_{anexo.filename}")
                        with open(anexo_path, 'wb') as f:
                            f.write(anexo.payload)
                        arquivos_baixados.append(anexo_path)
                        print(f"Baixado: {anexo.filename}")

            print(f"Processadas {cont_mensagens} mensagens não lidas.")
    except Exception as e:
        print(f"Erro ao conectar ou ler e-mails: {e}")

    return arquivos_baixados

if __name__ == "__main__":
    baixar_anexos_pdf_nao_lidos()
