# Optimus — agente contábil via n8n

O **Optimus** é o agente conversacional do Estoque Contábil. Ele transforma perguntas sobre estoque, competência, aging, origem, lifecycle, centros, controles e documentação em respostas apoiadas por evidências da instalação local.

O modelo de linguagem é executado no workflow do **n8n**. O n8n faz a orquestração da conversa e conecta o modelo Gemini ao sistema; a aplicação local continua responsável por ler o DuckDB, aplicar as regras contábeis, validar permissões, executar consultas e controlar qualquer ação operacional. Essa separação permite trocar o modelo ou a instância do n8n sem mover a base contábil para fora da instalação.

## O que o Optimus resolve

- Explica os indicadores da competência selecionada e compara competências carregadas.
- Consulta valor fiscal, quantidade, PMM, aging, lifecycle, origem, divisão, local, centro e exceções de enriquecimento.
- Diferencia fato observado, alerta e recomendação, sempre informando a competência e o `run_id` quando existirem.
- Busca orientações no manual do sistema e na documentação técnica, inclusive para instalação, permissões, páginas e rotinas.
- Investiga lacunas da Base de Estoque, regras ausentes no Mapping, status de execução, status da MB59 e cobertura do All Brazil.
- Prepara PDF da Visão e relatórios e payload para apresentação executiva no Google Slides, sem inventar métricas ausentes.
- Acompanha eventos importantes e pode avisar administradores de forma proativa quando o sistema está aberto.

O agente não é um contabilizador e não substitui a validação humana. Ele não inventa saldo, material, centro, data, regra, causa ou valor que não estejam no contexto devolvido pelo sistema.

## Arquitetura da conversa

```mermaid
flowchart LR
    U[Usuário autenticado] --> UI[Página Optimus<br/>optimus.html]
    UI --> API[API local FastAPI<br/>/api/optimus/chat]
    API --> CTX[Contexto validado<br/>DuckDB + regras + manual]
    API --> N8N[Webhook Chat Trigger<br/>n8n]
    N8N --> VAL[Validar competência]
    VAL --> BRIDGE[GET /api/agent/context<br/>Bearer OPS_API_TOKEN]
    BRIDGE --> AG[Agente contábil]
    GEM[Google Gemini Chat Model] --> AG
    MEM[Memória da conversa<br/>janela de 8 mensagens] --> AG
    AG --> N8N
    N8N --> API
    API -->|resposta textual| UI
    AG -->|[[OPS_ACTION]]| API
    API --> TOOLS[Ferramentas locais<br/>consulta ou ação confirmável]
    TOOLS --> API
    API --> N8N
```

O fluxo completo é:

1. O usuário entra na página Optimus. A permissão `agent` precisa estar liberada; administradores têm acesso às páginas administrativas.
2. A interface envia a mensagem para `POST /api/optimus/chat`. A sessão, o usuário autenticado e a competência são mantidos no servidor local.
3. O backend monta o contexto da competência antes de chamar o n8n. Esse contexto inclui os KPIs, as competências disponíveis, o status da execução, os insights, o catálogo de campos, o Mapping, a origem e a cobertura do All Brazil, o índice do manual e as confirmações pendentes.
4. O backend chama o Chat Trigger do n8n com `action`, `sessionId`, `chatInput` e cabeçalhos de identificação da origem, usuário e competência.
5. O workflow valida a competência no formato `AAAA-MM`, consulta a rota local `/api/agent/context` e entrega o payload ao agente Gemini.
6. O agente responde usando somente o contexto validado e a memória curta da sessão. Quando precisa de informação adicional, solicita uma ferramenta local pelo marcador `[[OPS_ACTION]]`.
7. O backend interpreta o marcador, executa a consulta ou prepara uma ação local, devolve o resultado ao n8n e permite até quatro interações de ferramenta na mesma pergunta.
8. A resposta final volta para a interface. Se o usuário estiver em outra página, o sistema pode gerar uma notificação do Windows conforme as preferências locais.

## O que é enviado ao n8n

O n8n recebe a pergunta e o contexto necessário para respondê-la. O contexto é produzido localmente e contém, entre outros:

- competência selecionada e lista de todas as competências carregadas;
- quantidade de linhas, materiais, quantidade total, valor fiscal, PMM e variações;
- `run_id`, status, horários e mensagem da última execução;
- insights contábeis com severidade, descrição, valor e evidência;
- catálogo de campos da Base de Estoque e regras de negócio;
- status da MB59, origem do snapshot do All Brazil, cobertura, duplicidades e conflitos;
- grupos e regras do Mapping;
- índice do manual e trechos selecionados para perguntas sobre o funcionamento do sistema;
- confirmação pendente de uma extração, importação ou ação preparada;
- orientação explícita de que a resposta deve dizer “Não localizado” quando não houver evidência.

O n8n não recebe senha do SAP, credenciais do banco, arquivos brutos, PDFs ou a base inteira para o modelo. O endpoint local retorna agregados, evidências limitadas e resultados pontuais das ferramentas autorizadas.

## Workflow n8n publicado no projeto

O workflow principal está em [`n8n/workflows/ops_contabil_agent_gemini.json`](../n8n/workflows/ops_contabil_agent_gemini.json). Ele contém estes nós:

| Nó | Responsabilidade |
| --- | --- |
| **Chat Trigger** | Recebe a conversa e mantém o `sessionId`. |
| **Validar competência** | Exige uma competência `AAAA-MM` e separa pergunta, período e sessão. |
| **Contexto Ops Contábil** | Consulta a API local com `OPS_API_BASE_URL` e `OPS_API_TOKEN`. |
| **Agente contábil** | Aplica as regras de resposta, cita evidências e solicita ferramentas quando necessário. |
| **Google Gemini Chat Model** | Modelo de linguagem configurado pela credencial corporativa do n8n. |
| **Memória da conversa** | Mantém uma janela curta de oito mensagens por sessão. |

O arquivo `ops_contabil_agent_compacto.json` é uma alternativa mínima para homologação com outro modelo compatível. Para o uso principal, a versão Gemini é a referência.

## Consultas e ferramentas locais

O agente pode pedir consultas sem alterar dados:

- `inventory_search`: pesquisa materiais e linhas da competência com filtros e ordenação;
- `runs` e `sap_status`: consulta execuções e jobs recentes;
- `mb59_status`: mostra a situação da base GR;
- `all_brazil_source`, `all_brazil_enrichment_status`, `all_brazil_catalog` e `all_brazil_search`: consulta fonte, cobertura e registros do All Brazil;
- `mappings` e `mapping_gaps`: lê regras e identifica centros sem cobertura;
- `inventory_gaps`: encontra campos de enriquecimento sem preenchimento;
- `documentation_search` e `system_manual`: busca a documentação técnica e o manual operacional;
- `health_center`: verifica API, banco, dados, ponte, VPN, n8n/Optimus e demais indicadores;
- `settings_overview`: lê configurações administrativas quando o usuário é administrador;
- `report_pdf`: prepara um PDF autenticado com os mesmos gráficos da Visão e relatórios;
- `executive_presentation`: prepara o payload factual para o fluxo n8n criar uma apresentação executiva.

As ferramentas consultivas não alteram a base. O payload de PDF e apresentação é produzido pelo backend e é a única fonte autorizada para o artefato; o agente não deve estimar ou completar indicadores.

## Ações com confirmação explícita

Quando uma solicitação pode alterar dados, iniciar processamento ou mudar configuração, o Optimus primeiro apresenta um resumo e guarda uma pendência. Nada é executado na primeira mensagem. Somente uma confirmação semântica explícita do usuário usa `confirm_sap`.

Podem exigir confirmação:

- executar ZMM119 ou MB59;
- importar uma planilha SAP já baixada;
- reprocessar os joins de All Brazil, PASSO A PASSO e Mapping;
- incluir ou alterar uma regra de Mapping;
- sincronizar a ponte do Drive;
- gerar um backup ou alterar o agendamento;
- cadastrar ou desativar um acesso corporativo;
- alterar preferências de notificação ou interface do próprio computador.

Usuários comuns não executam extrações, importações nem ações administrativas. O Optimus não exclui competência ou usuário, não restaura backup, não troca a pasta do Drive e não instala o sistema; nesses casos ele orienta o caminho correto nas páginas administrativas.

## Avisos proativos

O vigia local do Optimus detecta fatos estruturados; a mensagem em linguagem natural é escrita pelo próprio agente no n8n. Isso mantém a evidência no sistema e evita que o texto do alerta seja criado a partir de suposição.

Os gatilhos incluem:

- falha ou ação necessária em uma extração SAP;
- planilha ZMM119 ou MB59 salva pelo SAP e disponível para importação contingencial;
- lacunas de enriquecimento na Base de Estoque;
- centros sem regra de Mapping;
- variações e eventos de fechamento relevantes;
- mudança na qualidade ou cobertura do All Brazil;
- jobs travados ou competência/documentação atualizada;
- queda ou retorno da VPN e do n8n.

O vigia roda enquanto um administrador está com o sistema aberto: após cargas, extrações ou mudanças de Mapping, em ciclos de cinco minutos para fatos de negócio e de dois minutos para conectividade. Os eventos são deduplicados, ficam disponíveis por até 12 horas e respeitam um intervalo mínimo entre avisos. A oferta de importar uma planilha só é executada depois de “sim”; o arquivo original não é movido nem apagado.

Quando o n8n está indisponível, o próprio Health Center informa a causa técnica. Ao retornar a conexão, o Optimus informa o tempo de indisponibilidade, a causa identificada e entrega os avisos pendentes.

## Configuração do n8n

Consulte [`n8n/PUBLICAR_AGENTE_GEMINI.md`](../n8n/PUBLICAR_AGENTE_GEMINI.md) para o procedimento completo. Em resumo:

1. Importe `ops_contabil_agent_gemini.json` na instância n8n corporativa.
2. Selecione a credencial Gemini aprovada e o modelo disponível para ela.
3. Configure `OPS_API_BASE_URL` para uma URL pela qual o n8n alcance a API local e `OPS_API_TOKEN` com o mesmo token da instalação.
4. Restrinja `allowedOrigins` à origem do sistema e publique o workflow.
5. Configure `N8N_CHAT_URL` na máquina do Estoque Contábil com a URL de produção do Chat Trigger.
6. Abra o Health Center e valide os indicadores **VPN / rede** e **n8n / Optimus**.
7. Faça um teste com uma pergunta que contenha uma competência existente, por exemplo: “Na competência 2026-08, qual foi o valor fiscal e o PMM?”.

Em uma implantação corporativa, a API deve ser exposta somente em rede protegida, com HTTPS e autenticação. Não publique a porta `127.0.0.1` diretamente na internet e não coloque o token ou a credencial Gemini no repositório.

## Diagnóstico rápido

| Sintoma | Verificação |
| --- | --- |
| “URL do Optimus não configurada” | Conferir `N8N_CHAT_URL` no ambiente da instalação. |
| Chat sem conexão | Verificar VPN / rede e o indicador n8n / Optimus no Health Center. |
| HTTP 401 ou 403 no contexto | Conferir `OPS_API_TOKEN`, origem permitida e autenticação da API local. |
| Competência recusada | Informar o período no formato `AAAA-MM` e confirmar que existe em Base de Estoque. |
| Resposta sem número | Verificar se a competência tem execução concluída e evidência disponível; o agente não deve preencher lacunas. |
| PDF ou Slides não gerados | Conferir o Health Center, a credencial Google e executar a ação novamente pelo chat após a conexão voltar. |

## Arquivos de referência

- [Workflow Gemini](../n8n/workflows/ops_contabil_agent_gemini.json)
- [Publicação do agente](../n8n/PUBLICAR_AGENTE_GEMINI.md)
- [Artefatos de relatório](../n8n/ARTIFATOS_RELATORIO.md)
- [Página do chat](../src/ops_contabil/web/templates/optimus.html)
- [Manual operacional incorporado ao contexto](../src/ops_contabil/knowledge/manual_sistema.md)
- [Vigia de eventos proativos](../src/ops_contabil/optimus_watch.py)
- [API e ferramentas locais](../src/ops_contabil/web/app.py)
