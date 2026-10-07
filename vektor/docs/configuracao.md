# Configuração para uma nova implantação

## Propriedades do script

A versão pública lê os valores específicos do ambiente em **Configurações do projeto → Propriedades do script**.

| Propriedade | Finalidade |
| --- | --- |
| `BASE_CLARA_ID` | Base principal de transações do cartão corporativo |
| `VEKTOR_ACL_SPREADSHEET_ID` | Planilha de usuários, perfis e permissões |
| `VEKTOR_NUMERARIO_SS_ID` | Planilha de apoio do módulo Numerário |
| `VEKTOR_NUMERARIO_BRIDGE_FOLDER_ID` | Pasta usada pela ponte de extrações do Numerário |
| `VEKTOR_VERTEX_PROJECT_ID` | Projeto Google Cloud usado pelo Vertex AI |
| `VEKTOR_POLICY_HIST_SS_ID` | Histórico do assistente de política |
| `VEKTOR_METRICAS_SHEET_ID` | Base de métricas e uso |
| `VEKTOR_PASTA_TERMOS_ID` | Pasta de termos e documentos autorizados |
| `PROJECT_ID` | Projeto Google Cloud usado pelo núcleo analítico |
| `SPREADSHEET_ID_CLARA` | Base Clara usada por fluxos legados ou especializados |
| `SPREADSHEET_ID_CLARA_PEND` | Base histórica de pendências, quando aplicável |
| `VEKTOR_SAP_PROJECT_ID` | Projeto usado pela integração SAP |
| `VEKTOR_BR_HOLIDAY_CAL_ID` | Calendário de feriados considerado pelas regras |
| `VEKTOR_RPA_SS_ID` | Fila de solicitações da ponte RPA |
| `RPA_FOLDER_ID` | Pasta de intercâmbio da ponte RPA |
| `VEKTOR_AR_ID_PASTA_DRIVE` | Destino inicial dos documentos da Prosegur |
| `VEKTOR_AR_ID_PASTA_PROCESSADOS_RAIZ` | Raiz dos documentos já processados |
| `VEKTOR_AR_SISTEMA_PROSEGUR_FOLDER_ID` | Pasta de integração do sistema Prosegur |
| `VEKTOR_POWER_BI_EMBED_URL` | URL autorizada do relatório incorporado |
| `VEKTOR_NUM_V2_STORAGE_FOLDER_ID` | Persistência do Numerário V2 |
| `VEKTOR_NUM_V2_EMAIL_FROM` | Remetente autorizado do Numerário |
| `VEKTOR_NUM_V2_EMAIL_CC` | Cópia padrão do Numerário |
| `VEKTOR_NUM_V2_TEST_EMAIL` | Destinatário dos testes controlados |
| `VEKTOR_NUM_V2_DELETE_ALLOWED_EMAIL` | Conta autorizada para exclusões sensíveis |
| `VEKTOR_NUM_EMAIL_REPLY_QUEUE_FOLDER_ID` | Fila de respostas recebidas pelo módulo |
| `VEKTOR_POS_STORAGE_FOLDER_ID` | Persistência do módulo POS |
| `VEKTOR_POS_EMAIL_FROM` | Remetente autorizado do POS |
| `VEKTOR_POS_EMAIL_CC_DEFAULT` | Cópia padrão do POS |
| `VEKTOR_POS_BQ_BILLING_PROJECT_ID` | Projeto de faturamento das consultas BigQuery |
| `VEKTOR_POS_REGIONAL_SS_ID` | Base regional usada pelo POS |
| `VEKTOR_TP_WORKER_URL` | Endpoint do agente de Numerário |
| `VEKTOR_GUIA_FILE_ID` | Arquivo de orientação exibido pelo portal |

O código também utiliza propriedades próprias para tokens de APIs, chaves de workers e parâmetros de modelos. Revise as chamadas a `PropertiesService` antes da implantação e cadastre cada segredo diretamente no ambiente.

## Serviços avançados

Habilite no Apps Script os serviços com os mesmos símbolos usados pelo projeto:

- `BigQuery`
- `VertexAI`
- `Drive`
- `Gmail`
- `Sheets`

As APIs correspondentes também precisam estar habilitadas no projeto Google Cloud associado ao script.

## Bibliotecas

Adicione as bibliotecas `AutomationNum1` e `Maker_PDF` usando IDs e versões autorizados pela organização responsável pela nova implantação. O manifesto público contém marcadores no lugar dos IDs originais.

## Fontes e páginas externas

Substitua os marcadores de configuração usados para:

- domínios autorizados e grupos de acesso (`empresa.exemplo`, `marca.exemplo` e `subsidiaria.exemplo`);
- painel Power BI ou Looker Studio;
- imagem do assistente;
- catálogo de agentes;
- endpoint do worker de Numerário;
- links de documentação e treinamento;
- bases e pastas do Google Drive.

## Validação recomendada

1. Confirme que o manifesto pode ser salvo após informar as bibliotecas.
2. Valide login, sessão, empresa e perfis com contas de teste.
3. Teste cada módulo com bases sem dados reais.
4. Execute envios apenas para destinatários de teste.
5. Confirme permissões de Drive, Gmail, Sheets, BigQuery e Vertex AI.
6. Valide auditoria, deduplicação e retomada de jobs interrompidos.
7. Revise acionadores antes de ativar as rotinas programadas.
