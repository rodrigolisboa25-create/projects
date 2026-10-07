import os
from datetime import datetime, timedelta

def verificar_pdfs_ontem():
    # Caminho provável da pasta de Downloads no Windows
    caminho_downloads = os.path.join(os.path.expanduser('~'), 'Downloads')

    # Valida se a pasta existe
    if not os.path.exists(caminho_downloads):
        print(f"Não consegui encontrar a pasta de Downloads no caminho: {caminho_downloads}")
        return

    # Definir as datas (Hoje e Ontem)
    hoje = datetime.now()
    ontem_inicio = (hoje - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    ontem_fim = (hoje - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)

    print(f"Analisando PDFs na pasta: {caminho_downloads}")
    print(f"Buscando arquivos da data de ontem: de {ontem_inicio.strftime('%d/%m/%Y')} até as 23:59")
    print("-" * 50)

    encontrou_algum = False

    try:
        # Percorrer os arquivos da pasta
        for arquivo in os.listdir(caminho_downloads):
            if arquivo.lower().endswith('.pdf'):
                caminho_completo = os.path.join(caminho_downloads, arquivo)

                # Coleta o tempo de modificação do arquivo
                timestamp_modificacao = os.path.getmtime(caminho_completo)
                data_modificacao = datetime.fromtimestamp(timestamp_modificacao)

                # Verifica se a data de modificação ou criação cai no dia de ontem
                if ontem_inicio <= data_modificacao <= ontem_fim:
                    if not encontrou_algum:
                        print("✅ ENCONTRADOS (Modificados/Criados Ontem):")

                    encontrou_algum = True
                    print(f"  -> {arquivo}")
                    print(f"     Data exata: {data_modificacao.strftime('%d/%m/%Y %H:%M:%S')}")

        if not encontrou_algum:
            print("❌ Nenhum PDF de ontem foi encontrado na sua pasta de Downloads.")

    except PermissionError:
        print("Erro de permissão: Você não tem acesso de leitura na pasta de Downloads.")
    except Exception as e:
        print(f"Aconteceu um erro inesperado: {e}")

if __name__ == "__main__":
    verificar_pdfs_ontem()
