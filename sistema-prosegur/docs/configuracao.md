# Configuração e implantação

## Dependências Python

As dependências estão em `SISTEMA_PROSEGUR/requirements.txt`:

- `pdfplumber` para leitura dos PDFs;
- `pandas` para tratamento tabular;
- `openpyxl` para relatórios Excel;
- `python-dotenv` para configuração local;
- bibliotecas Google para o fluxo de e-mail/API;
- `pypdf` para operações auxiliares com PDF.

Instalação:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r SISTEMA_PROSEGUR/requirements.txt
```

## Configuração local

Copie `.env.example` para `.env` e informe os valores somente no computador da implantação:

| Variável | Uso |
| --- | --- |
| `EMAIL_HOST` | Servidor IMAP, quando o leitor legado for utilizado |
| `EMAIL_USER` | Conta técnica de leitura |
| `EMAIL_PASS` | Senha ou segredo da conta, nunca no GitHub |
| `PASTA_DOWNLOADS` | Pasta local de entrada |
| `PASTA_FINAL` | Pasta de saída |

O pipeline atual usa caminhos relativos ao diretório do projeto. Ajuste `INPUT_DIR`, `OUTPUT_DIR`, `BASE_FORN_PATH`, `DB_PATH` e `TEMPLATE_DIR` em `main.py` quando a instalação usar outra topologia.

## Bases e templates

Forneça localmente:

- base de fornecedores;
- cadastro de lojas e empresas;
- centros de custo e regras de rateio;
- templates SAP por empresa;
- arquivos de referência necessários para enriquecimento.

Os nomes e campos variam entre organizações. O parser deve ser homologado com PDFs reais antes de gerar saídas oficiais.

## Apps Script

`Apps_Script_Prosegur_Novo.js` deve ser copiado para um projeto Apps Script separado. Configure:

- ID da pasta de destino no Drive;
- marcador de e-mail que representa a fila;
- arquivo de auditoria;
- conta que executará o Web App ou acionador;
- permissões Gmail e Drive;
- acionador de processamento.

Os identificadores da versão original foram substituídos por marcadores. Não coloque os IDs reais no repositório público.

## Empacotamento

O arquivo `Robo_Prosegur.spec` serve como referência para gerar um executável com PyInstaller. Antes de empacotar, revise caminhos absolutos, arquivos de template, banco, logs e permissões da conta executora.

## Checklist de homologação

- [ ] Python e dependências instalados.
- [ ] `.env` configurado fora do Git.
- [ ] Pastas de entrada e saída criadas.
- [ ] Bases e templates da nova empresa revisados.
- [ ] Um PDF de cada tipo processado com sucesso.
- [ ] Totais comparados manualmente.
- [ ] Auditoria sem divergências não explicadas.
- [ ] Reprocessamento de um documento conhecido não criou duplicata.
- [ ] Apps Script testado com conta e pasta de homologação.
- [ ] Acionadores instalados somente após a validação.
