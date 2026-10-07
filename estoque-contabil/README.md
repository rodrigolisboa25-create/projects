# Estoque Contábil

Plataforma Python para substituir o processamento de planilhas contábeis pesadas, automatizar extrações SAP e produzir saídas auditáveis. O Excel deixa de ser o motor de regras e passa a ser somente uma entrada legada ou um formato de entrega.

## Decisões desta fase

- Sem Streamlit.
- Sem BigQuery.
- Processamento local com Python, DuckDB e arquivos Parquet.
- Interface web local em FastAPI, aberta no navegador do usuário.
- Extração SAP GUI com sessão já autenticada; nenhuma senha fica no projeto.
- n8n atua como orquestrador e agente, mas não processa os arquivos pesados.
- Excel final é gerado a partir de modelo, com rastreabilidade por execução.

## Optimus: agente contábil via n8n

O **Optimus** é a camada de inteligência conversacional do projeto. Ele fica disponível na página própria do sistema e usa um workflow do n8n com Google Gemini para responder perguntas sobre as competências compiladas, sempre com contexto preparado pela API local.

O desenho separa responsabilidades: Python/FastAPI lê o DuckDB, aplica os contratos e regras de negócio, valida permissões e devolve agregados e evidências; o n8n orquestra a conversa e o modelo; a interface mostra a resposta e os avisos. O agente não recebe a base bruta inteira, não acessa credenciais SAP e não pode inventar números.

Além das consultas, o Optimus pesquisa o manual e a documentação do sistema, verifica lacunas e saúde da instalação, prepara PDFs e apresentações executivas e acompanha eventos proativos. Extrações SAP, importações, Mapping, backup, acessos e preferências sempre passam por resumo e confirmação explícita antes de qualquer execução.

O workflow importável, o contrato de contexto, as ferramentas, os avisos proativos, os limites de segurança e o passo a passo de configuração estão em [docs/optimus.md](docs/optimus.md).

## Início rápido

No primeiro acesso, um administrador baixa `INSTALAR_ESTOQUE_CONTABIL.zip` na página **Configurações** e envia o pacote ao novo usuário por um canal corporativo. O usuário extrai todo o ZIP e executa `INSTALAR_ESTOQUE_CONTABIL.bat`. A página Configurações somente existe depois que o sistema está instalado; portanto, ela é o ponto de distribuição e atualização, não o ponto de entrada de uma máquina vazia.

O pacote de aplicação e dados é versionado. O inicializador `.bat` evita depender de um executável próprio sem assinatura e:

1. localiza o Python 3.12/3.13 ou instala o Python 3.13 pelo `winget`;
2. cria o ambiente virtual em `%LOCALAPPDATA%\OpsContabil\runtime\.venv`;
3. instala as dependências e valida as importações essenciais;
4. publica de forma transacional a mesma versão de código embutida no ZIP;
5. instala, dentro de `%LOCALAPPDATA%\OpsContabil`, uma fotografia consistente das competências já compiladas, incluindo relatórios, Mapping e permissões, para que o primeiro acesso não dependa das planilhas-fonte nem do Drive;
6. em atualizações, preserva os vínculos locais de identidade e as preferências da interface, sem substituir dados operacionais que sejam mais novos que a fotografia embarcada;
7. cria o atalho **Estoque Contábil** na Área de Trabalho.

O código operacional fica em `%LOCALAPPDATA%\OpsContabil\runtime\app` e os dados compilados em `%LOCALAPPDATA%\OpsContabil\processed`, ambos dentro da árvore local da instalação e fora do Google Drive. Logs de instalação e inicialização ficam em `%LOCALAPPDATA%\OpsContabil\logs`. Depois da primeira instalação, o usuário abre o sistema pelo atalho da Área de Trabalho. Para atualizar, executa uma versão mais nova do mesmo pacote: o código é substituído, a fotografia mais recente é aplicada e dados operacionais locais mais novos não são apagados.

Nenhum usuário instalado precisa acessar a pasta deste projeto no Drive. A cópia local inclui código, configuração, cadastro de acessos, Mapping e todas as competências compiladas existentes no momento da publicação. Perfis `user` sempre recebem **Visão e relatórios**; para utilizar o chat ou o diagnóstico, precisam também das páginas **Optimus** e/ou **Health Center**. Perfis `admin` acessam todas as páginas, inclusive SAP, importações, exclusão de competências, HTML autônomo e Configurações. O HTML compartilhável é um arquivo independente: não usa n8n, Drive ou Apps Script. Para compartilhar, envie o próprio `.html`; endereços `file:///C:/...` existem apenas na máquina que abriu o arquivo.

Para uso administrativo diretamente neste projeto, `ABRIR_ESTOQUE_CONTABIL.bat` utiliza o código-fonte publicado em `src/` e apenas reutiliza o Python do runtime. Isso evita divergência entre arquivo-fonte e cópia local durante a manutenção.

Alternativa manual:

```powershell
$venv = "$env:LOCALAPPDATA\OpsContabil\runtime\.venv"
py -3.12 -m venv $venv
& "$venv\Scripts\python.exe" -m pip install --upgrade .
& "$venv\Scripts\python.exe" -m ops_contabil.runtime_entry doctor
& "$venv\Scripts\python.exe" -m uvicorn ops_contabil.dashboard_runtime:app --host 127.0.0.1 --port 8765
```

A interface abre em `http://127.0.0.1:8765`.

## Estrutura

- `config/`: fontes, caminhos, parâmetros SAP e regras.
- `src/ops_contabil/`: aplicação Python, API, pipeline e robôs.
- `n8n/workflows/`: fluxos importáveis do orquestrador e do agente.
- `ARQUITETURA_FINAL.md`: arquitetura e limites de homologação.
- `MAPEAMENTO_DADOS.md`: colunas, fórmulas e regras encontradas.
- `data/inbox/`: arquivos recebidos, separados por fonte e execução.
- `data/processed/`: Parquet e banco DuckDB.
- `data/output/`: Excel e relatórios publicados.
- `logs/`: logs técnicos e trilha de execução.

## Segurança

Não coloque credenciais no YAML, no `.env` ou nos VBS. O SAP GUI precisa estar aberto e autenticado. Credenciais do n8n devem ficar no cofre do próprio n8n. O agente recebe, por padrão, somente agregados e evidências limitadas retornadas pela API de leitura.

Leia [Arquitetura](ARQUITETURA_FINAL.md), [Mapeamento das bases](MAPEAMENTO_DADOS.md) e a [documentação do Optimus e da integração n8n](docs/optimus.md).
