# 🧩 NexxusDoc

**Python · FastAPI · HTML/CSS/JavaScript · n8n · Gemini via endpoint compatível com OpenAI · Google Drive · PDF**

Aplicação local para Windows que transforma entrevistas guiadas em procedimentos operacionais (POPs). O agente de IA **NexxusDoc** conversa com quem executa o processo, coleta etapas, controles e evidências, ajuda a identificar lacunas e produz um documento para revisão humana. A aplicação administra versões, aprovações, consulta ao acervo e oportunidades de automação.

> Versão pública sanitizada. Credenciais, cadastros, documentos e referências corporativas reais não estão neste repositório. Integrações e bases específicas precisam ser configuradas para outra implantação.

## 📌 O problema

Procedimentos costumam ser descritos em conversas, planilhas e arquivos dispersos. Sem roteiro comum, ficam de fora exceções, responsáveis, evidências, controles, contingências e critérios de aprovação. Uma atualização também pode perder o vínculo com a versão anterior e seus materiais de apoio.

## ✅ A solução

1. A pessoa autenticada escolhe criar um procedimento ou revisar um documento existente.
2. O agente conduz uma entrevista, uma pergunta por vez, usando o questionário e o contexto da área.
3. A aplicação vincula anexos e links, extrai texto admitido e sinaliza duplicidades e documentos relacionados.
4. A prévia acompanha as respostas. O servidor bloqueia a geração quando faltam campos essenciais.
5. O sistema monta o PDF com sumário, etapas, papéis, riscos, evidências e referências.
6. O documento passa por revisão e aprovação; versões e decisões permanecem registradas.
7. O acervo sustenta consultas posteriores com indicação das fontes.
8. As entrevistas alimentam um mapa de oportunidades de automação por impacto e esforço.

```mermaid
flowchart TB
    U["Usuário no navegador"] --> A["FastAPI local"]
    A --> Q["Questionário e validações"]
    A --> N["Workflow n8n"]
    N <--> M["Modelo Gemini"]
    A --> D["Acervo sincronizado no Drive"]
    Q --> P["Prévia e PDF"]
    P --> R["Revisão e aprovação"]
    R --> D
    D --> A
```

## 🤖 NexxusDoc: agente de IA

O [workflow n8n](workflows/normas_procedimentos_n8n.json) usa um nó **AI Agent** e um nó **OpenAI Chat Model** apontado, na instalação original, para o modelo configurado como `gemini-3.6-flash` por um endpoint compatível. A cópia publicada não inclui a credencial nem o endpoint da organização. A seleção do modelo pertence à instância n8n; a API local controla a sessão, valida respostas e gera o documento.

O [prompt](workflows/system_message_nexxusdoc.md) orienta a entrevista; o [questionário](questionnaire.json) define campos e perguntas. A API prepara o contexto com referências, anexos e documentos relacionados. O modelo devolve a próxima pergunta ou síntese; o backend decide se há dados suficientes para gerar o PDF. A IA auxilia a redação e a consulta, mas o conteúdo exige revisão por pessoas autorizadas.

### Como a conversa funciona

```mermaid
sequenceDiagram
    participant P as Pessoa
    participant A as API local
    participant N as n8n
    participant I as Modelo de IA
    P->>A: Resposta ou anexo
    A->>A: Valida sessão e contexto
    A->>N: Pergunta e dados da rodada
    N->>I: Prompt e contexto
    I-->>N: Próxima pergunta ou síntese
    N-->>A: Resultado
    A-->>P: Conversa e prévia
```

O workflow usa uma retomada assíncrona: devolve rapidamente um endereço de resultado e a aplicação consulta até a resposta ficar pronta. Isso contorna o limite de duração do proxy da instalação original. A interface permite tentar novamente após falha sem perder a mensagem.

### O que ele faz

- Pergunta objetivo, escopo, gatilhos, entradas e saídas, passos, responsáveis, sistemas, regras e evidências.
- Investiga controles, exceções, contingências, riscos, indicadores e materiais de apoio.
- Ao revisar um POP existente, aproveita o texto recebido e pergunta o que falta para o novo padrão.
- Sugere documentos relacionados e avisa sobre outro procedimento do mesmo tema.
- Usa referências de mercado como ponto de partida para perguntas, sempre sujeitas à confirmação.
- Consulta o acervo com fontes e levanta esforço, frequência e volume para análise de automação.

## 🔄 Do rascunho ao documento vigente

```mermaid
stateDiagram-v2
    [*] --> Entrevista
    Entrevista --> Previa: respostas
    Previa --> Entrevista: campos pendentes
    Previa --> Rascunho: validação
    Rascunho --> Aprovacao: enviar
    Aprovacao --> Ajustes: solicitar
    Ajustes --> Rascunho: nova versão
    Aprovacao --> Vigente: aprovar
    Vigente --> Rascunho: revisar
```

O aprovador deve ser um owner ou administrador ativo. O modo obrigatório ou opcional é configurável. O histórico registra comentários, versões e decisões. O texto redigido pelo modelo não se torna vigente sem o fluxo aplicável.

## 🧩 Principais recursos

- Interface local com Visão geral, Chat Nexxus, Documentos e Configurações.
- Identificação pelo e-mail corporativo vinculado ao UPN do Windows, com perfis master, owner e usuário.
- Anexos de documentos, planilhas e imagens, com limites e extração de texto.
- Prévia durante a entrevista e validação de campos essenciais.
- PDF com capa, sumário navegável, links, histórico e documentos relacionados.
- Revisão de POPs existentes, consulta assistida e alerta de duplicidade.
- Aprovação com segregação de papéis, retorno para ajustes e auditoria.
- Mapa de automação com exportação para Excel.
- Instalador por usuário, atualização assinada, backup de cadastro, diagnóstico de VPN e sincronização.

## 🛠️ Componentes

| Arquivo | Responsabilidade |
| --- | --- |
| [`app.py`](app.py) | API, sessões, entrevistas, documentos, PDF, acervo e aprovação. |
| [`static/`](static/) | Interface e módulos de fluxo, orçamento e apresentação. |
| [`budget_engine.py`](budget_engine.py) | Motor de orçamento e importação/exportação. |
| [`questionnaire.json`](questionnaire.json) | Roteiro estruturado de perguntas. |
| [`workflows/`](workflows/) | Workflow n8n, prompt e instruções. |
| [`instalador_nexus.py`](instalador_nexus.py) e [`nexus_launcher.pyw`](nexus_launcher.pyw) | Instalação, atualização e inicialização. |
| [`assinatura.py`](assinatura.py) | Verificação de publicações e cadastro assinados. |
| [`modelos_referencias_por_area.json`](modelos_referencias_por_area.json) | Modelos de referência iniciais. |

## 📁 Estrutura

```text
nexxusdoc/
├── app.py                       # servidor e regras
├── budget_engine.py             # orçamento
├── assinatura.py                # verificação de assinaturas
├── instalador_nexus.py          # instalação e atualização
├── nexus_launcher.pyw           # inicialização
├── questionnaire.json           # entrevista
├── modelos_referencias_por_area.json
├── static/                      # interface e recursos visuais
├── workflows/                   # agente e prompt
├── tools/                       # utilitário de documentação
├── docs/                        # arquitetura e segurança
├── .env.example                 # parâmetros de exemplo
└── requirements.txt
```

## 🚀 Adaptação e instalação

1. Em Windows, crie um ambiente Python compatível com [`requirements.txt`](requirements.txt).
2. Copie `.env.example` para `.env` e configure a pasta compartilhada, e-mail master, segredo de sessão e URL n8n.
3. Importe o workflow no n8n e configure suas próprias credenciais de modelo, Gmail, Drive e BigQuery conforme os nós usados.
4. Configure o identificador da pasta sincronizada no instalador e a ponte do Drive quando necessários.
5. Providencie cadastros e bases curadas específicos em ambiente restrito; eles foram excluídos desta cópia.

**A cópia pública não é um pacote de produção pronto.** Caminhos, IDs, projeto de dados e endereços foram substituídos por exemplos. Sua implantação precisa preencher esses parâmetros e validar permissões.

## 🔐 Segurança

A pasta original no Drive não foi alterada. Chaves privadas, assinaturas, usuários, entrevistas, logs, backups, PDFs e conhecimento corporativo real foram excluídos. E-mails, URLs internas, IDs e projetos de dados foram substituídos na cópia publicada. A autenticação pelo UPN pressupõe um Windows gerenciado e requer avaliação na implantação.

Leia [arquitetura da IA](docs/ia-e-fluxos.md) e [escopo da versão pública](docs/seguranca.md).

Desenvolvido por [Rodrigo Lisboa](https://github.com/rodrigolisboa25-create).
