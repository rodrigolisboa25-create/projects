# Dados e artefatos fora do GitHub

O diretório original contém dados de operação e artefatos gerados ao longo das competências. Eles não foram copiados para o repositório.

## Itens excluídos

| Item | Motivo |
| --- | --- |
| `.env` | Contém credenciais e caminhos locais |
| `documentos.db` | Banco com histórico de documentos processados |
| `Idocs_Prosegur/` | PDFs recebidos e anexos reais |
| `PROSEGUR_PROCESS/` | Relatórios, planilhas e documentos de produção |
| `Processados/` | Documentos já tratados, organizados por competência |
| `Bases de informações.xlsx` | Cadastros, fornecedores, lojas e regras operacionais |
| `Base_Forn.xlsx` | Base auxiliar de fornecedores |
| `Planilha_SAP_*.xlsx` | Templates com estrutura e possível conteúdo operacional |
| `processamento.log` | Histórico detalhado de execução |
| `RELATORIO_AUDITORIA.txt` | Evidências e valores de uma execução real |
| `vektor_ar_metricas.json` | Métricas de produção |
| `dist/` e `build/` | Binários gerados e dependências empacotadas |
| `__pycache__/` | Cache local do Python |

Para usar o projeto, crie esses recursos na nova implantação a partir dos contratos descritos em [Arquitetura](arquitetura.md) e [Configuração](configuracao.md).
