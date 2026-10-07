import os

# VARREDURA TOTAL - SEM FILTROS
start_dir = r"g:\Drives compartilhados\OPERAÇÕES FINANCEIRAS"
print(f"LUPA ATIVADA! Buscando em absolutely TUDO dentro de: {start_dir}")

encontrados = []
try:
    for root, dirs, files in os.walk(start_dir):
        for file in files:
            if file.lower().endswith(".pdf"):
                full_path = os.path.join(root, file)
                # Vamos focar nos arquivos da Prosegur (que começam com números longos)
                if any(char.isdigit() for char in file[:5]):
                    encontrados.append(full_path)
except Exception as e:
    print(f"Erro durante a varredura: {e}")

if encontrados:
    print(f"\nACHAMOS! Total de {len(encontrados)} arquivos PDF encontrados:\n")
    for path in encontrados:
        print(path)
else:
    print("\nERRO CRÍTICO: Nenhum PDF encontrado no Drive. Verifique a Lixeira do Drive na Web.")
