# Arquitetura do Vektor

## Visão geral

O Vektor é uma aplicação modular hospedada no Google Apps Script. `Code.gs` concentra o núcleo compartilhado e a página `index.html` fornece o portal principal. Os demais pares de arquivos `.gs` e `.html` implementam módulos especializados.

O frontend chama funções autorizadas do backend com `google.script.run`. O backend valida sessão e perfil antes de consultar bases, produzir análises ou executar uma ação transacional.

## Camadas

| Camada | Responsabilidade |
| --- | --- |
| Portal e navegação | Login, sessão, menu, páginas, componentes, gráficos e experiência conversacional |
| Controle de acesso | Lista de usuários, perfis, módulos autorizados e funções permitidas |
| Motor analítico | Normalização, filtros, consolidações, regras determinísticas, indicadores e priorizações |
| Automação | Alertas, e-mails, filas, gatilhos, integrações com RPA e rotinas programadas |
| Persistência | Google Sheets, arquivos JSON no Drive, propriedades do script e BigQuery |
| IA | Vertex AI/Gemini para respostas baseadas em contexto e análises assistidas |
| Observabilidade | Histórico, auditoria, status de jobs, métricas, custos e registros de execução |

## Módulos

### Núcleo e governança Clara

`Code.gs` e `index.html` formam o portal central. Esse conjunto implementa autenticação, seleção de empresa, perfis, catálogo de funções, análises financeiras, alertas, envio assistido de pendências, histórico e o assistente de política.

### Numerário

`numerario_index.html`, `vektor_numerario_email.gs` e `VektorNumerarioTioPatinhas.gs` tratam a operação de numerário. O módulo mantém dados e configurações, solicita extrações SAP, controla comunicações, produz relatórios, cria cópias de recuperação e conversa com um agente externo autorizado.

### Contas a Receber e Prosegur

`vektor_modulo_ar.gs`, `vektor_modulo_ar_htm.html`, `AR_Prosegur_V2.gs` e `AR_PROSEGUR_GMAIL_API.gs` implementam o painel de AR, a ponte com RPA e o processamento de anexos da Prosegur. O fluxo identifica mensagens elegíveis, grava PDFs sem duplicidade, atualiza auditoria e só então finaliza o estado da mensagem no Gmail.

### POS

`vektor_pos.gs` e `pos_index.html` reúnem cadastro de lojas, registros operacionais, importação SAP, comunicação por e-mail, relatórios e análises assistidas. A persistência usa arquivos controlados no Drive e fontes analíticas configuradas para a implantação.

### Power BI e agentes de IA

Os arquivos `vektor_modulo_powerbi*` encapsulam a exibição de um painel autorizado. Os arquivos `vektor_modulo_agentes_ia*` fornecem o catálogo de agentes e seus atalhos, sempre sujeitos às permissões do portal.

## Fluxo de uma operação

1. O usuário acessa o Web App e inicia uma sessão.
2. O backend identifica o perfil e os módulos permitidos.
3. A página solicita apenas as funções liberadas para aquele perfil.
4. O backend lê as fontes configuradas e aplica regras determinísticas.
5. O frontend exibe indicadores, tabelas, gráficos ou uma prévia da ação.
6. Ações transacionais exigem a etapa de confirmação prevista no fluxo.
7. O resultado é persistido com status e evidências para consulta posterior.

## Dependências externas

- Serviços avançados do Google: BigQuery, Vertex AI, Drive, Gmail e Sheets.
- APIs e escopos OAuth declarados em `appsscript.json`.
- Bibliotecas Apps Script: `AutomationNum1` e `Maker_PDF`.
- Bases, pastas, projetos Google Cloud, painéis e agentes configurados por ambiente.

As bibliotecas são dependências vinculadas ao projeto e não arquivos internos. O repositório não replica o código delas.
