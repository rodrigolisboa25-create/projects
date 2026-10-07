import os.path
import base64
import pdfplumber
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Escopos que o script terá. Apenas leitura (modify para marcar como lido se no futuro quiser).
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

REMETENTE_ALVO = "usuario01@empresa.exemplo"


def ler_pdf(caminho_arquivo):
    """
    Função para ler o texto do documento PDF usando pdfplumber.
    """
    try:
        print(f"\n  -> Lendo conteúdo de {os.path.basename(caminho_arquivo)}...")
        texto_extraido = ""
        with pdfplumber.open(caminho_arquivo) as pdf:
            for pagina in pdf.pages:
                texto_pagina = pagina.extract_text()
                if texto_pagina:
                    texto_extraido += texto_pagina + "\n"

        linhas = texto_extraido.strip().split('\n')
        if linhas:
            print("     [Prévia do conteúdo extraído]:")
            for linha in linhas[:5]:
                print(f"       {linha}")
            if len(linhas) > 5:
                print("       (...)")
        else:
            print("     [O PDF parece ser uma imagem ou está vazio]")

    except Exception as e:
        print(f"  -> Erro ao ler PDF {caminho_arquivo}: {e}")

def obter_servico_gmail():
    """Autentica o usuário e retorna a instância do serviço do Gmail API."""
    creds = None
    # O arquivo token.json armazena os tokens de acesso e atualização do usuário,
    # criados automaticamente na primeira vez.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # Se não houver credenciais válidas, pede login ao usuário abrindo o navegador.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Atualizando o token de acesso...")
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("ERRO: O arquivo 'credentials.json' não foi encontrado na pasta atual.")
                print("Por favor, siga os passos no Google Cloud Platform para gerá-lo e o coloque aqui.")
                return None

            print("Abrindo o navegador para você autorizar o aplicativo...")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Salva a credencial p não precisar logar de novo
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Constrói o serviço
    service = build('gmail', 'v1', credentials=creds)
    return service

def ler_emails_api_gmail():
    servico = obter_servico_gmail()
    if servico is None:
        return

    destino_pdf = os.path.join(os.getcwd(), 'PDFs_Prosegur')
    if not os.path.exists(destino_pdf):
        os.makedirs(destino_pdf)

    print(f"Buscando e-mails do remetente (pode demorar alguns segundos): {REMETENTE_ALVO}...")
    try:
        # Busca no Gmail usando a sintaxe padrão de pesquisa
        alvo_busca = f"from:{REMETENTE_ALVO} has:attachment filename:pdf"
        resultados = servico.users().messages().list(userId='me', q=alvo_busca, maxResults=10).execute()
        mensagens = resultados.get('messages', [])

        if not mensagens:
            print("Nenhum e-mail da Prosegur com anexo PDF foi encontrado.")
            return

        print(f"{len(mensagens)} e-mail(s) recente(s) da Prosegur contendo PDF encontrado(s).")

        for msg_miniatura in mensagens:
            msg_id = msg_miniatura['id']
            msg_completa = servico.users().messages().get(userId='me', id=msg_id).execute()

            # Puxando cabeçalhos (Assunto e Data)
            payload = msg_completa.get('payload', {})
            headers = payload.get('headers', [])

            assunto = "(Sem Assunto)"
            data = ""
            for header in headers:
                if header['name'].lower() == 'subject':
                    assunto = header['value']
                if header['name'].lower() == 'date':
                    data = header['value']

            print(f"\n[Data: {data}] \nAssunto: {assunto}")

            # Buscar as partes (anexos)
            parts = payload.get('parts', [])
            for part in parts:
                if part['filename'] and part['filename'].lower().endswith('.pdf'):
                    # O arquivo base64 pode estar direto aqui ou precisar de um fetch extra no body_id
                    body = part['body']
                    data_base64 = None

                    if 'data' in body:
                        data_base64 = body['data']
                    elif 'attachmentId' in body:
                        # Precisamos buscar o base64 desse attachment ID específico
                        att_id = body['attachmentId']
                        att_obj = servico.users().messages().attachments().get(
                            userId='me', messageId=msg_id, id=att_id).execute()
                        data_base64 = att_obj['data']

                    if data_base64:
                        # Google API usa base64url, que usamos '-' em vez de '+' etc
                        file_data = base64.urlsafe_b64decode(data_base64.encode('UTF-8'))

                        nome_arquivo = part['filename']
                        caminho_arquivo = os.path.join(destino_pdf, nome_arquivo)

                        print(f"  -- Baixando anexo: {nome_arquivo}")
                        with open(caminho_arquivo, 'wb') as f:
                            f.write(file_data)

                        # Ler o PDF processado
                        ler_pdf(caminho_arquivo)

        print("\nProcessamento concluído.")

    except Exception as error:
        print(f'Ocorreu um erro: {error}')

if __name__ == '__main__':
    ler_emails_api_gmail()
