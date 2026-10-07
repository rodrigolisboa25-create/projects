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
| `VEKTOR_NUMERARIO_API_TOKEN` | Token da API usada pela ponte de Numerário |
| `VEKTOR_RPA_API_TOKEN` | Token da API usada pela ponte RPA |
| `VEKTOR_TP_WORKER_KEY` | Chave de autenticação do worker Tio Patinhas |
| `VEKTOR_EXTRA_OFF_DAYS` | Datas adicionais sem expediente consideradas nas agendas |
| `PEDRO_AI_PROVIDER` | Provedor usado pelo agente Pedro |
| `PEDRO_AI_ENDPOINT` | Endpoint do provedor de IA do POS |
| `PEDRO_AI_MODEL` | Modelo configurado para a análise |
| `PEDRO_AI_API_KEY` | Chave do provedor escolhido |
| `PEDRO_AI_PROJECT_ID` | Projeto Google Cloud, quando exigido pelo provedor |

O código também utiliza propriedades próprias para tokens de APIs, chaves de workers e parâmetros de modelos. Revise as chamadas a `PropertiesService` antes da implantação e cadastre cada segredo diretamente no ambiente.

### Referência das planilhas atuais

- `VEKTOR_METRICAS_SHEET_ID` deve apontar para [Vektor_Info_calibrate](https://docs.google.com/spreadsheets/d/18yAuYoAR33JOagqapxgwHh86F1WeD0mZcj9AIJym07k/edit?gid=1670513007#gid=1670513007) quando a implantação usar a mesma base compartilhada de métricas, custos, alertas e RPA.
- As propriedades do domínio Clara, como `BASE_CLARA_ID`, `SPREADSHEET_ID_CLARA`, `SPREADSHEET_ID_CLARA_PEND` e `VEKTOR_ACL_SPREADSHEET_ID`, devem apontar para [Capta_Clara](https://docs.google.com/spreadsheets/d/1_XW0IqbYjiCPpqtwdEi1xPxDlIP2MSkMrLGbeinLIeI/edit?gid=1277104230#gid=1277104230) ou para bases equivalentes criadas para o novo ambiente.

`Capta_Clara` é exclusiva do módulo Clara. Ao reutilizar outros módulos do Vektor, configure planilhas próprias para eles em vez de compartilhar essa base.

## Roteiro de implantação

### 1. Definir o escopo

Escolha quais módulos serão implantados. Essa decisão determina os serviços, escopos, fontes e acionadores necessários. Um ambiente que usa apenas Power BI e Governança Clara não precisa habilitar a mesma infraestrutura de um ambiente com Prosegur, POS e agentes de IA.

### 2. Criar os recursos de dados

- planilha de acesso e suas abas;
- bases operacionais dos módulos escolhidos;
- pastas do Drive para documentos e arquivos de estado;
- datasets e tabelas BigQuery;
- projeto Google Cloud para Vertex AI;
- caixas, marcadores e remetentes autorizados no Gmail.

### 3. Importar o código

Copie os 19 arquivos de `src/` para o projeto Apps Script. Preserve os nomes porque o backend usa `HtmlService.createTemplateFromFile()` e `createHtmlOutputFromFile()` para localizar páginas e fontes internas.

### 4. Ajustar o manifesto

Os campos `libraryId` são marcadores e precisam ser substituídos antes da implantação. Revise também:

- serviços avançados realmente utilizados;
- escopos OAuth;
- modo de execução do Web App;
- público autorizado;
- fuso horário.

### 5. Configurar acesso

Cadastre usuários, papéis, empresas, módulos e funções. Teste pelo menos um usuário de cada perfil e confirme que uma função não autorizada também é bloqueada no backend.

### 6. Configurar integrações

Preencha as propriedades do script, ajuste nomes de abas e tabelas, substitua domínios de exemplo e informe os endpoints externos.

### 7. Inicializar os módulos

Execute apenas as funções de setup dos módulos escolhidos. Elas podem criar arquivos, cabeçalhos, estruturas de armazenamento ou configurações iniciais.

### 8. Instalar acionadores

Ative individualmente os gatilhos de alertas, backups, relatórios e sincronizações. Registre quem instalou cada acionador e qual conta será usada na execução.

### 9. Homologar e publicar

Use dados e destinatários de teste. Valide consultas, gravações, deduplicação, retomada, auditoria e falhas simuladas antes de publicar para o público final.

## Serviços avançados

Habilite no Apps Script os serviços com os mesmos símbolos usados pelo projeto:

- `BigQuery`
- `VertexAI`
- `Drive`
- `Gmail`
- `Sheets`

As APIs correspondentes também precisam estar habilitadas no projeto Google Cloud associado ao script.

| Módulo | Serviços principais |
| --- | --- |
| Governança Clara | Sheets, BigQuery, Gmail e Drive |
| Assistente de Política | Vertex AI, Sheets e Drive |
| Numerário | Sheets, Drive e Gmail |
| AR / Prosegur | Gmail, Drive e Sheets |
| POS | Drive, Gmail, Sheets, BigQuery e IA configurada |
| Power BI | HTML Service e URL de incorporação autorizada |

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
8. Simule reprocessamento para confirmar as barreiras de duplicidade.
9. Verifique a expiração de sessão e o bloqueio de funções não autorizadas.
10. Registre responsáveis, rotina de backup e procedimento de recuperação.
