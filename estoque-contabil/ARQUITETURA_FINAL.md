# Estoque Contábil — arquitetura final

## Objetivo e escopo

Plataforma Python/FastAPI para substituir o processamento pesado das planilhas, automatizar ZMM119 e MB59 no SAP GUI, enriquecer a posição com All Brazil e Mapping e entregar relatórios contábeis rastreáveis. Não usa Streamlit nem BigQuery.

A aplicação é executada em `http://127.0.0.1:8765` e instalada sob `%LOCALAPPDATA%\OpsContabil`. Depois da instalação, ela não depende da pasta do projeto no Drive de Operações Financeiras.

## Perfis e acesso

- O login aceita apenas contas `@gruposbf.com.br` e `@fisia.com.br` e vincula o e-mail informado à identidade corporativa do Windows.
- Todo perfil Usuário recebe obrigatoriamente **Visão e relatórios**.
- As demais páginas são liberadas individualmente em **Configurações > Acesso corporativo**.
- Para usar o chat, o perfil Usuário precisa da página **Optimus**. Para consultar diagnósticos, precisa da página **Health Center**.
- Administradores acessam todas as páginas e concentram SAP, Mapping, exclusão de competências, gestão e exclusão de acessos, geração de HTML e distribuição de atualizações. Ao excluir um usuário, o registro é removido e qualquer sessão existente perde acesso na próxima requisição autenticada.
- Administradores iniciais: `rodrigo.lisboa@gruposbf.com.br` e `gabriella.lalonso@gruposbf.com.br`.

## Distribuição dos dados compilados

O instalador ZIP incorpora uma fotografia transacional do DuckDB com todas as competências compiladas existentes no momento da publicação. Assim, um novo usuário autorizado enxerga imediatamente os mesmos relatórios, mesmo sem SAP, sem as planilhas-fonte e sem acesso ao Drive do projeto.

Ao atualizar uma máquina:

1. o código e as configurações são substituídos de forma atômica;
2. se o banco local já existir, cada competência do pacote é aplicada somente quando não existe na máquina ou quando a carga do pacote (última importação de ZMM119, MB59 ou All Brazil) é mais recente que a local; competências com carga local igual ou mais nova são mantidas;
3. usuários, vínculos de identidade, preferências, Mapping, auditoria e competências que existem apenas na máquina nunca são alterados;
4. antes de qualquer alteração o banco é copiado para `processed\ops_contabil.antes-da-atualizacao.duckdb`, e a troca das competências ocorre numa única transação;
5. uma cópia anterior da aplicação fica disponível para recuperação.

Sem banco local, a fotografia inteira é instalada como carga inicial.

## Ponte de dados pelo Drive compartilhado

Para que todas as máquinas vejam os mesmos dados sem reinstalar, as competências trafegam pela pasta do drive compartilhado **Estoque_Cont** (Google Drive para computador). O Drive é somente transporte: cada máquina continua dona do seu banco local.

- **Envio:** ao concluir uma atualização local (extração SAP, upload manual, recarga da Base de Estoque, reprocessamento de joins ou alteração de Mapping), a máquina exporta a competência em Parquet para `periodos\AAAA-MM\<versão>\` e só depois atualiza o ponteiro `periodos\AAAA-MM\atual.json` (horário da alteração, autor, máquina, linhas, tamanho e SHA-256 de cada arquivo). As três versões mais recentes de cada competência são mantidas. Sem acesso ao Drive, a competência fica pendente e o envio é refeito automaticamente.
- **Recebimento:** a cada 2 minutos, ao iniciar o sistema e no login, cada máquina aplica apenas as competências do Drive mais recentes que as suas e com todos os arquivos completos (tamanho e hash conferidos). Arquivos ainda sendo baixados pelo Google Drive fazem a máquina aguardar a próxima rodada. A aplicação usa a mesma trava das importações e uma transação por competência. As telas abertas se atualizam sozinhas.
- **Garantias:** nada é apagado localmente por ausência ou problema no Drive; a exclusão de competência é local e impede que a mesma versão volte pela ponte. Usuários, permissões, preferências, Mapping e auditoria não passam pela ponte — o controle de acesso continua exclusivamente local.
- **Conflitos:** competências diferentes atualizadas por pessoas diferentes não conflitam. Para a mesma competência vale a atualização mais recente; as anteriores permanecem no histórico de versões do Drive.
- **Contingência:** em Configurações é possível trocar a pasta (validada quanto a existência e gravação). A troca deixa `pasta_movida.json` na pasta anterior para que as demais máquinas passem a usar a nova. A pasta também pode ser definida por `OPS_BRIDGE_ROOT`.
- **Permissões recomendadas no Google Drive:** somente administradores com permissão de edição na pasta; demais usuários como leitores.

## Backup programado

Em Configurações, o administrador ativa o backup (diário, semanal ou mensal). Cada backup é uma exportação completa e consistente do DuckDB em Parquet, empacotada em `ops_contabil_backup_AAAAMMDD_HHMMSS_<COMPUTADOR>.zip` com o arquivo `COMO_RESTAURAR.txt`. Por padrão é gravado em `Estoque_Cont\backups\<nome do computador>` (ou em `%LOCALAPPDATA%\OpsContabil\backup` sem acesso ao Drive). **Cada novo backup substitui o anterior:** o arquivo novo é gravado, conferido (`verify_backup`: zip íntegro com `schema.sql`/`load.sql`) e só então `replace_previous_backups` apaga os backups anteriores deste computador na pasta; se a gravação ou a conferência falhar, o anterior permanece. Backups de outros computadores na mesma pasta nunca são apagados (o nome do arquivo identifica o computador). Quando o destino não é o próprio computador, uma cópia do backup mais recente também fica em `%LOCALAPPDATA%\OpsContabil\backup` (substituída da mesma forma), para que a perda da pasta do Drive não leve o backup junto. A antiga preferência de retenção em dias deixou de ser usada. As pastas de backup e da ponte são escolhidas pela janela nativa do Windows (`folder_picker.py`).

## Notificações do Windows

`notifications.py` envia somente notificações nativas do Windows (toast, Central de Notificações) a partir do servidor local, por isso funcionam com o navegador fechado. O app é registrado em `HKCU\Software\Classes\AppUserModelId\GrupoSBF.EstoqueContabil` (nome "Estoque Contábil", ícone `assets/estoque_contabil.png`, sem permissão de administrador) e cada aviso é mostrado por um PowerShell oculto (WinRT `ToastNotificationManager`), numa fila em segundo plano que nunca atrasa a tarefa.

Clique: o toast chama o protocolo `estoquecontabil:abrir?view=<página>&id=<n>` (registrado em `HKCU\Software\Classes\estoquecontabil`), que executa `assets/abrir_notificacao.vbs` → `abrir_notificacao.ps1` sem janela. O script lê a chave local `%LOCALAPPDATA%\OpsContabil\notificacoes\ativacao.json` (gerada pelo servidor a cada início; páginas da web não conseguem lê-la) e chama `POST /api/notifications/activate` (rota fora do login, protegida pela chave): o servidor marca a notificação como lida e manda as abas conectadas (eventos em tempo real `GET /api/notifications/stream`) irem para a página. Em seguida o script localiza, por UI Automation, a aba "Estoque Contábil" no Chrome/Edge e a traz para frente. Sem aba aberta, abre `http://127.0.0.1:8765/?origem=notificacao#<página>`; com o servidor parado, executa o inicializador `ABRIR_ESTOQUE_CONTABIL.ps1`. Uma aba aberta com `?origem=notificacao` enquanto outra já existe leva a existente para a página (BroadcastChannel) e se fecha.

Sino: `notification_log` (até 200, por máquina, fora do pacote do instalador) com `GET /api/notifications`, `POST /api/notifications/read`, `DELETE /api/notifications`; o aviso de conclusão de uma tarefa substitui o de início ainda não lido (mesma etiqueta). A versão intermediária com notificações pelo navegador (service worker) foi descartada; a tela remove o service worker antigo.

- Categorias: `sap` (início silencioso + conclusão/falha/cancelamento), `uploads` (upload de planilha, recarga e reprocessamento de joins), `optimus` (a tela do chat chama `POST /api/optimus/notify` só quando o usuário não está olhando o chat; erros da rota `/api/optimus/chat`, exceto 401/403, notificam no próprio servidor), `bridge` (competências recebidas pelo Drive), `backup` (backup programado e restauração), `connectivity` (agente sem conexão: VPN/n8n, abre o Health Center).
- Preferências por máquina em `system_settings.notification_preferences` (geral, por categoria e som), via `GET/PUT /api/notifications/preferences` e `POST /api/notifications/test`, acessíveis a qualquer perfil logado: Configurações > Notificações e link Preferências do sino. Não vão no pacote do instalador.
- Optimus: enquanto analisa, chama `window.top.setOptimusBusy(true)` e o item do menu mostra três pontinhos (escondidos com o menu recolhido); a conversa das últimas 8 h fica em `localStorage` (`ops_optimus_history:<e-mail>:<sessão>`).

## Perfis: páginas obrigatórias

`MANDATORY_USER_PAGES = ("overview", "docs")` em `auth.py`/`auth_windows.py`: todo perfil Usuário tem Visão e relatórios e Documentação. Configurações fica disponível a todos, mas o perfil Usuário vê só Interface e experiência (rotas `GET/PUT /api/preferences/interface`, apenas campos de interface) e Notificações; `/api/settings*` continua exclusivo de administradores (a tela esconde as demais seções com `body.role-user`).

**Menu lateral e página inicial.** Cada grupo do menu é um `<button class="group" aria-expanded aria-controls>` seguido de `.group-items > .group-inner` com os links; recolher usa `grid-template-rows` 1fr→0fr (animação desligada com `no-motion`) e `visibility:hidden` para tirar os links da navegação por teclado. O estado fica em `localStorage["opsNavGroupsCollapsed"]` (por navegador). Com `sidebar-collapsed` (ou largura ≤ 760 px) os grupos somem e todos os ícones aparecem. `activate(view)` com `push` reabre o grupo da página de destino. `applyUserAccess` esconde botão e lista do grupo sem páginas liberadas. `startSystem()` sempre ativa `overview` e normaliza o hash com `history.replaceState`; a única exceção é a aba aberta por clique em notificação (`?origem=notificacao`) sem outra aba do sistema aberta, que respeita o hash da notificação. `firstAllowedView()` devolve sempre `overview` (obrigatória para todos os perfis). **Ícone do sistema.** Três placas isométricas em azul-marinho com barras brancas de contorno fino constante (`vector-effect:non-scaling-stroke`, 0,8 px). Fontes em `assets/`: `estoque_contabil.svg` (sem fundo), `estoque_contabil.png` (128 px, ícone das notificações do Windows) e `estoque_contabil.ico` (16–256 px, cada tamanho desenhado nativamente). Sem fundo: SVG inline em `.logo.logo-mark` (menu 48 px, login 58 px), `img.loader-banner-icon` (58 px), capa do .docx/PDF. Com fundo quadrado (único lugar onde já havia fundo): favicon. O instalador (`installer_main.write_launcher`) copia o .ico para `%LOCALAPPDATA%\OpsContabil\estoque_contabil.ico`, fora da pasta `app` trocada nas atualizações, e grava `IconLocation` no atalho da área de trabalho.

**Optimus: rolagem no fim.** O chat roda em iframe dentro do painel; com o painel oculto o `#messages` não tem altura e a rolagem fica no início. Um `ResizeObserver` em `#messages` rola até o fim sempre que ele passa de oculto para visível.

**Paleta azul-marinho.** No fim do `<style>` do `dashboard.html` há blocos de sobreposição: tela de carregamento (`.system-loader`, `.loader-banner`, `.loader-pie` em `#0B2545`/`#9FC3EA`); páginas de OPERAÇÃO com as mesmas variáveis de Configurações (`--navy`, `--navy-soft`, `--navy-line`…) aplicadas via `:is([data-panel="sap"],[data-panel="all-brazil"],[data-panel="mapping"],[data-panel="governance"])` (bordas, faixa de título dos cards, botões primários, selos `:not(.warn)`, avisos, cabeçalhos do Mapping, painel `.jobs` e monitor de extração); Visão e relatórios com `.section` em `#EAF1FA` (o contorno `stroke` dos rótulos SVG acompanha o fundo). Evolução usa `<linearGradient id="trend-bar-gradient">` nas barras e linha azul `#2e86ab`; Variação usa degradê laranja (aumento) e vermelho (redução). O mapa de calor do Aging for Season usa `color-mix(in srgb,#f58634 X%,#fffaf5)` (8% a 54% conforme o valor), opaco para não misturar com o fundo azul do card. Como os relatórios HTML/PDF reproduzem o painel, herdam as cores sem código à parte.

**Division Description com variação.** `divisionChart(id, items, variance, previousPeriod)` desenha as colunas (`columnChart`) e chama `divisionVarianceLine`, que reserva uma faixa no topo do `.col-plot` (`.with-variance`, padding-top 92 px) e insere um SVG absoluto com a linha (`trend-qty`), pontos (`trend-dot`, vermelho se negativo) e rótulos de % (`trend-point-value quantity`), reaproveitando as animações da Evolução. As posições vêm das colunas medidas e são redesenhadas por `ResizeObserver` quando a largura muda. Os dados vêm de `summary.division_variance` (casados por rótulo). `fitSidebarWidth()` também considera o subtítulo do menu ("Inventory Mgmt", abreviado para não gerar rolagem; `.side{overflow-x:hidden}`); o topo mostra "Inventory Management / página".

**Risco de obsolescência.** `dashboard_summary()` devolve `division_aging = _fiscal_matrix(conn, period, "division_description", "aging_bucket")` (também enviado em `visuals` da apresentação executiva). `divisionAgingChart()` desenha barras empilhadas 100% por Division sobre o estoque recebido: a faixa `0) Futures` sai da barra e vira nota, as faixas ≥ `5)` (mais de 12 meses) somam o percentual de risco à direita, e o rodapé traz o total em R$. As linhas se distribuem na altura do card (`:has(>#chart-division-aging)` + `justify-content:space-evenly`); o Local de estoque usa a mesma técnica (`#chart-locations`, trilhos de 16 px), e a Origem do material tem trilhos de 18 px com espaçamento fixo. Substituiu o card "Variação por categoria" (`varianceChart` removido; `division_variance` continua alimentando a linha do Division Description, o Optimus e o relatório de contingência).

**Optimus importando planilhas já baixadas (contingência).** `sap_upload.find_sap_export_candidates()` lista os .xlsx dos últimos 45 dias (até 15, mais recentes) em Downloads, Área de Trabalho, Documentos, OneDrive, TEMP/TMP e `X:\TEMP|TMP`; `quick_identify_sap_export()` lê só o cabeçalho direto do XML (abas, primeiras linhas e os primeiros textos compartilhados) e aplica as mesmas regras de `identify_sap_export()` (posicional A:R da ZMM119, contrato `mb59_base`), com fallback para a leitura completa — 5 s em vez de ~100 s para 15 planilhas grandes. Ferramentas locais (somente admin): `find_sap_exports` e `import_sap_file`, que registra em `SAP_CONFIRMATIONS` uma pendência `parameters.kind="upload"`; `confirm_sap` desvia para `_start_agent_upload()`, que confere tamanho e data do arquivo, copia para `landing/uploads` e executa o mesmo `run_upload_job` do upload da página (o original não é tocado).

**Optimus proativo na falha de extração.** Ao fim de `run_sap_job` com FAILED/ACTION_REQUIRED, `offer_import_after_failure()` procura planilhas da mesma transação gravadas depois do início (−2 min), inclusive o destino oficial em `landing`, e grava uma oferta em `OPTIMUS_OFFERS` (12 h); a notificação da falha (mesma etiqueta) passa a abrir o Optimus. O chat (`optimus.html`) consulta `GET /api/optimus/proactive?session_id=` ao abrir e a cada 15 s; a oferta é entregue uma vez, vira a pendência da sessão (`origin="optimus_proactive"`, `offer_text`) e o "sim" segue o fluxo normal `confirm_sap`. Sem n8n novo: o nó "Detectar retorno local" já devolve ao agente tudo que não é PDF/Slides.

**Optimus proativo (vigia + agente).** `optimus_watch.py` só detecta fatos estruturados (sem texto pronto): `all_brazil_event`, `mapping_event`, `inventory_gap_event`, `closing_event`, `all_brazil_quality_event`, `variation_event`, `stuck_job_events`, `latest_period_event`/`documentation_event` (`silent_first`: só avisam quando mudam) e `health_events` (ignora `slides`, `permissions`, `n8n` e `sap` em atenção) com trechos de `documentation_matches()`. `new_events()` guarda chave→impressão digital em `system_settings.optimus_watch_seen` (não repete; resolvido sai da memória). No `app.py`, `optimus_watch_loop` (thread com `background_worker`) roda `optimus_watch_once()` a cada 5 min (`WATCH_INTERVAL_SECONDS`) ou após `optimus_watch_trigger()` (job concluído em `notify_job_result`, recálculo de Mapping), **somente se um administrador consultou `/api/optimus/proactive` nos últimos 90 s** (sistema aberto). Os eventos entram na fila `OPTIMUS_OFFERS` (`queue_optimus_event`, 12 h). A cada consulta do chat (15 s), `optimus_proactive` pega um evento, registra a pendência quando há ação (`origin="optimus_proactive"`, `proactive_event`; uma decisão pendente por vez) e chama `_optimus_chat(..., proactive_event=evento)`, que troca `[PERGUNTA_USUARIO]` por `[EVENTO_PROATIVO]` + `[INSTRUCAO_EVENTO_PROATIVO]`: **o próprio agente escreve o aviso**. Falha do n8n devolve o evento à fila. O chat notifica pelo Windows (`/api/optimus/notify` com `title="Optimus: aviso"`) só se o usuário estiver em outra página/janela. Antipoluição: impressão digital por fato + `optimus_watch["min_gap"]` (60 s) entre avisos do agente por sessão (`last_delivery`); itens `notified` (oferta de importação após falha SAP) e avisos do sistema não esperam.

**Optimus sem conexão (VPN/n8n).** `health_center.connectivity_indicators(url)` (também usado por `system_health`) roda só `_vpn_probe` + `_n8n_probe`. `connectivity_check()` (no `optimus_watch_loop`, a cada 2 min com administrador presente, e já no ciclo seguinte quando uma entrega ao n8n falha) usa `optimus_watch.connectivity_cause()`: há queda quando o n8n não está saudável; a causa apontada é a VPN se ela estiver em atenção/crítico, senão o n8n. Início da queda → `optimus_watch["outage"]={since, indicator}`, `notifier.notify("connectivity", ..., view="health", tag="connectivity")` e item `system=True` (`connectivity_lost`) na fila, entregue por `/api/optimus/proactive` sem n8n como `{"kind":"system","title":"Aviso do sistema · Health Center"}` com título/status/detalhes/como corrigir do indicador (texto do Health Center, não do agente). Durante a queda a resposta traz `offline:true`, nenhum evento do agente é enviado ao n8n e o chat mostra "Sem conexão (VPN / n8n)". Retorno → itens de queda pendentes viram `superseded` e `connectivity_restored` (`offline_since`, `restored_at`, `minutes_offline`, `cause`, `queued_warnings`) entra no início da fila para o agente escrever. VPN fora com n8n acessível: `health:network` vai para o agente normalmente (`new_events(..., scope=CONNECTIVITY_KEYS)` atualiza só essa chave).

**Ferramentas e ações do Optimus.** Consultas: `documentation_search`, `health_center`, `inventory_gaps`, `mapping_gaps`, `settings_overview` (admin). Ações (preparam pendência em `SAP_CONFIRMATIONS` com `parameters.kind`; executam em `_run_confirmed_action()` após `confirm_sap`/`confirm_action`, pelas mesmas funções dos endpoints): `reprocess_enrichment`→`start_inventory_enrichment`, `save_mapping_rule`→`create/update_mapping_row`, `sync_bridge_now`→`post_bridge_sync`, `backup_now`→`run_backup_now`, `save_user_access`/`disable_user_access`→`add_allowed_user`/`disable_allowed_user` (lista central), `set_notification_preferences`/`set_interface_preferences` (qualquer perfil; `SELF_SERVICE_ACTION_KINDS`). `set_backup_schedule`→grava `backup_enabled`/`backup_frequency` (a pasta não muda). Fora do Optimus por decisão do negócio: excluir competência, excluir usuário, restaurar backup, trocar a pasta do Drive e instalador.

**Responder a um aviso e não lidas.** `OptimusChatRequest.reply_to` (id do aviso): `_optimus_chat` coloca `replying_to_warning` no contexto e, se o aviso tem ação e não foi decidido (`mark_offer_resolved` marca na confirmação/cancelamento), restaura a pendência dele (`proactive_offer_id`). No `optimus.html`, cada aviso tem o botão "Responder a este aviso" (faixa `#reply-chip`; histórico guarda `offerId`/`replyTo`). Não lidas: o chat chama `top.registerOptimusMessage()` a cada mensagem nova do Optimus; o `dashboard.html` conta se a página Optimus não está ativa/visível (`#optimus-unread` no ícone do menu, `localStorage.opsOptimusUnread`) e `markOptimusRead()` zera ao abrir o Optimus e marca como lidas as notificações `optimus`/`agent` do sino.

**Local "Não informado".** `dashboard_summary()` devolve `locations_unmapped` (centro, linhas e valor das linhas da competência com `location_group` vazio, ou seja, centro sem regra `group_key='location'` no Mapping). `locationChart(id, items, unmapped)` chama `locationNote()`, que acrescenta ao card a nota `.location-note` só quando existe a barra "Não informado"; ela também vai para o HTML/PDF do relatório.

**Ajuda dos gráficos.** `CHART_HELP` (id do gráfico → texto) cria um `button.chart-help` dentro do `h2` de cada card da Visão e um balão `.chart-help-pop` (fecha ao clicar fora, com Esc, ao trocar de página ou redimensionar). Não roda em modo relatório e `buildReportDocument()` remove botões, então não vai para HTML/PDF.

**Cards de KPI sem piscar.** `fitKpiValues()` guarda em `data-fit-digits` a forma medida (completa ou com 2/1/0 casas compactas) e, com o card oculto (`clientWidth===0`), mantém essa forma em vez de voltar ao valor completo; `setKpiValue()` já escreve na última forma medida. A largura do menu é `--side-w`: 226 px, ou o mínimo para o maior título de grupo caber em 1 linha (`fitSidebarWidth()`, recalculado ao carregar as fontes e no `resize`, cobre texto ampliado do Windows/zoom).

**Animações da Visão e relatórios só no carregamento.** Os cards usam `.chart-reveal`/`.kpi-reveal` com animações CSS pausadas até `.in-view`. Ocultar o painel (`display:none`) reinicia animações CSS, então, ao desativar o painel, todo card que já foi exibido recebe `.played` (`animation:none!important`); ao voltar, aparece pronto. `.played` só some ao recarregar a página (abrir, F5, novo login); cards ainda não vistos (abaixo da dobra) animam na primeira exibição.
- Os testes automáticos substituem o envio real (`tests/conftest.py`), sem notificações nem gravação no registro.

## Lista central de acessos

Até 02/10/2026 cada máquina tinha a própria lista de usuários (o antigo `shared_data/access/users.json` era gravado numa pasta local e nunca chegava às outras máquinas). Agora `access_sync.py` mantém uma lista central em `Estoque_Cont\acesso`:

- Cada máquina usada por administrador grava somente o próprio arquivo `acesso\alteracoes\<COMPUTADOR>.json` com a sua visão da lista; todas as máquinas leem todos os arquivos e, por e-mail, vale a alteração mais recente feita por um administrador (`allowed_users.access_changed_at/by`, UTC). O login altera `updated_at`, por isso a decisão não usa essa coluna; registros anteriores à funcionalidade entram como linha de base e perdem para qualquer alteração explícita. Exclusões são registradas como "excluído" (estado `access_state.tombstones`) e não são desfeitas por listas antigas.
- Sincronização: na inicialização, no login (antes de validar o usuário, até 8 s) e a cada ciclo da ponte (~2 min). Desativado/excluído perde a sessão no ciclo seguinte; novo usuário entra sem reinstalar.
- Administradores iniciais (`BOOTSTRAP_ADMINS`) nunca são desativados nem excluídos pela lista.
- Usuários comuns ficam bloqueados (401) se a máquina passar 7 dias sem consultar a lista (`verification`); administradores continuam entrando.
- Configurações > Acesso corporativo mostra todos os logins, quem alterou e quando, e a situação da lista; o Health Center tem o indicador "Controle de acessos" com o estado real.
- Integridade: só administradores devem ter edição no drive Estoque_Cont (usuários como Leitor). Bloquear o login não apaga os dados já existentes na máquina do usuário; para cortar dados novos, remova-o do drive Estoque_Cont.
- O estado `access_state` é por máquina e não vai no pacote do instalador.

## Página Documentação

Menu ADMINISTRAÇÃO > **Documentação** (página `docs` do catálogo: administradores sempre; usuários quando marcada em Configurações > Acesso corporativo). Exibe `Especificacao_Tecnico_Documental_Estoque_Contabil.docx` (raiz do projeto) convertido em PDF, com busca por palavras-chave (acentos/maiúsculas ignorados, todos os termos na mesma página, frase exata entre aspas), resultados com página, seção e trechos destacados, sumário clicável, abrir em nova aba e baixar.

- `tools/build_documentation.py` (Word via COM) trabalha numa cópia do .docx: recalcula o Sumário (texto fixo "Título<TAB>página"), exporta o PDF com marcadores e grava `knowledge/documentacao/{PDF, indice.json}` (versão, sumário, texto por página). Só reconverte quando o hash do .docx muda; `tools/build_installer.ps1` executa a conversão antes de empacotar.
- `documentation.py` serve a cópia mais recente entre a do pacote e a recebida pela ponte (`%LOCALAPPDATA%\OpsContabil\documentacao`); o ciclo da ponte publica uma versão mais nova em `Estoque_Cont\documentacao\<versão>` + `atual.json` (3 versões) e as demais máquinas a recebem conferindo tamanho e SHA-256, sem reinstalar.
- Rotas: `GET /api/docs/info`, `GET /api/docs/pdf[?download=true]`, `GET /api/docs/search?q=`.
- **Regra de manutenção:** toda alteração do sistema atualiza também a Especificação (.docx) e regenera o PDF.

## Manual do sistema para o Optimus

`src/ops_contabil/knowledge/manual_sistema.md` descreve cada página, botão, parâmetro, base, regra de cálculo, permissão e rotina; vai junto no instalador. `system_manual.py` escolhe as seções ligadas à pergunta (palavras-chave de cada seção) e o chat anexa até ~9 mil caracteres em `[MANUAL_DO_SISTEMA]` somente quando a pergunta é sobre o uso do sistema; perguntas sobre números não recebem o manual. O contexto sempre leva `system_manual_index` (títulos) e o Optimus pode pedir outras seções pela ferramenta local `system_manual` (`topics` e/ou `query`). **Ao alterar qualquer funcionalidade, atualize a seção correspondente do manual** (o teste `tests/test_optimus_manual.py` exige uma seção para cada página).

## Restauração a partir de um backup

Configurações > **Restaurar a partir de um backup** (somente administradores), módulo `backup_restore.py`:

1. **Conferir**: valida o .zip (integridade, `schema.sql`/`load.sql`, caminhos seguros, espaço em disco), importa-o num banco provisório `processed\.restauracao-<id>.duckdb` e compara, por competência, o backup com a máquina. O banco em uso não é alterado.
2. **Restaurar** (exige digitar `RESTAURAR`): acessos (`allowed_users`) e configurações desta máquina são levados para o banco restaurado; do backup vêm os dados. Com importações, envios ao Drive e backups travados, `db.database_maintenance()` bloqueia novas conexões, a troca espera até o arquivo ficar livre (abertura exclusiva do Windows) e o banco anterior é guardado como `ops_contabil.antes-da-restauracao-AAAAMMDD_HHMMSS.duckdb` (2 cópias). Se o banco continuar em uso por 60 s, nada é alterado.
3. Depois da troca, a ponte recebe do Drive o que lá estiver mais recente e reenvia o que o Drive não tiver; a publicação nunca sobrescreve uma versão mais nova no Drive.

Se a pasta do Drive se perder, as máquinas continuam com os dados completos: basta escolher uma nova pasta (contingência) e usar **Enviar competências desta máquina**. Os testes automatizados nunca acessam o Drive real (`tests/conftest.py` aponta a ponte para uma pasta inexistente).

## Fontes e ordem do processamento

1. **MB59 / Base GR** — deve ser extraída primeiro.
2. **ZMM119** — cria a posição bruta, restrita à empresa 7170.
3. **All Brazil** — seleciona somente o snapshot mais recente do mês cuja data seja menor ou igual à data-base.
4. **PASSO A PASSO** — procura cada campo por `CE & MAT` na MB59, depois na posição compilada anterior e, por último, no All Brazil somente por Material.
5. **Mapping e fórmulas** — calcula campos auxiliares, custos, aging, lifecycle, local e status.

Arquivos SAP ficam em `%LOCALAPPDATA%\OpsContabil\landing\<fonte>\AAAA-MM`. O banco compilado fica em `%LOCALAPPDATA%\OpsContabil\processed\ops_contabil.duckdb`.

Na exportação ALV, o robô seleciona XLSX, preenche os campos técnicos `DY_PATH` e `DY_FILENAME` com o destino oficial e pressiona explicitamente `wnd[1]/tbar[0]/btn[0]` (**Gerar**). O comando Enter não é usado nessa etapa porque, no dynpro **Gravar file**, ele apenas aceita a configuração sem criar o arquivo. `btn[11]` (**Substituir**) fica reservado ao fluxo de sobrescrita. Enquanto o popup nativo de segurança estiver visível, o comando Gerar não é repetido.

O destino efetivamente exibido em `DY_PATH`/`DY_FILENAME` é registrado antes e depois do preenchimento. Se o cliente SAP ignorar o destino solicitado e gravar em `C:\TEMP`, Downloads, Documentos, Desktop, `%TEMP%` ou outro diretório mostrado no próprio diálogo, o robô monitora esse local, copia o arquivo concluído e o normaliza automaticamente para o diretório oficial da competência. A cópia somente é aceita quando o ZIP interno do XLSX contém `[Content_Types].xml` e `xl/workbook.xml`; arquivos parciais durante `Transferring package` nunca são publicados.

Cada extração ativa reserva uma sessão SAP exclusiva. Se ZMM119 e MB59 forem solicitadas em paralelo, inclusive quando uma partir da página e outra do Optimus, o segundo job abre outra conexão/sessão SSO e nunca reutiliza a janela comandada pelo primeiro. A página **Extrações SAP** mantém os dois monitores visíveis, com progresso e mensagens independentes. O início de um job não apaga outro job ativo.

Os watchers dos diálogos SAP verificam formato, gravação e segurança em intervalos curtos. No dynpro **Gravar file**, o caminho e o nome são confirmados antes do clique; se o SAP mantiver a janela sem iniciar a transferência, o botão **Gerar** é tentado novamente de forma limitada em menos de um segundo. Quando a barra de status indicar `Transferring package`, o robô não repete o clique. Depois do Gerar, o prazo de validação acompanha o progresso real: é renovado sempre que o XLSX cresce no disco ou o status do SAP muda (por exemplo, `Download: 39 MB` → `40 MB`). A falha só ocorre após `sap_timeout_seconds` sem nenhum progresso (três vezes esse valor enquanto o SAP ainda reportar download), com teto absoluto de 45 minutos, e a mensagem informa o tempo total aguardado e o tempo sem progresso. Arquivos ainda em gravação nunca são copiados: a integridade do ZIP é verificada no próprio arquivo, lendo apenas o diretório central no fim, e a cópia para o destino oficial ocorre uma única vez, com o arquivo completo. Isso evita disputar o disco com o SAP e com o antivírus em máquinas mais lentas.

Como contingência ao robô, a página **Extrações SAP** permite carregar manualmente a planilha exportada da ZMM119 ou da MB59 (exclusivo de administradores). No envio, o sistema identifica pela estrutura de colunas de qual transação é o arquivo e recusa na hora uma planilha trocada (MB59 no quadro da ZMM119 e vice-versa) ou que não seja de nenhuma das duas. Em seguida valida o conteúdo antes de alterar qualquer dado: contrato A:R e ao menos um registro da empresa 7170 na ZMM119; layout da Base GR, ao menos um movimento e lançamentos da competência escolhida na MB59. O arquivo validado substitui o destino oficial em `landing` (o anterior é preservado como `.anterior.xlsx` e restaurado se a importação falhar) e segue exatamente a mesma importação e os mesmos enriquecimentos da extração automática, acompanhado no monitor de execuções com a etiqueta Upload.

As conexões ao DuckDB são abertas por várias threads do mesmo processo (jobs de importação e requisições da interface). A abertura é serializada e, se o arquivo estiver momentaneamente preso pelo checkpoint de outra conexão que está fechando, a tentativa é repetida por até 15 segundos antes de falhar.

As exportações podem ocorrer simultaneamente; a importação e os enriquecimentos no DuckDB passam por uma trava única. Assim, MB59 e ZMM119 não gravam joins, Mapping ou `inventory_rows` ao mesmo tempo. A ordem em que os arquivos terminarem é aceita: se a MB59 entrar depois da ZMM119, ela reaplica o PASSO A PASSO; se entrar antes, a ZMM119 já a encontra durante sua consolidação.

## Contratos de colunas

- **ZMM119:** contrato posicional fixo A:R, com 18 colunas. Os cabeçalhos são usados como trava contra mudança de layout; alteração de ordem ou quantidade bloqueia a importação.
- **MB59 e All Brazil:** resolução por nomes normalizados e aliases definidos em `config/schemas.yaml`; a ordem física pode mudar.
- Campo obrigatório ausente ou duplicado bloqueia apenas a importação daquela fonte antes de alterar a competência.
- Cada importação registra caminho, hash SHA-256, aba, linha de cabeçalho, quantidade de linhas, fingerprint do schema e horário.

## All Brazil e consistência

O relacionamento tenta primeiro o Material completo. Somente quando ele não existe, usa o Estilo-Cor de 10 caracteres. Centro nunca participa dessa chave.

Chaves repetidas são contabilizadas. Quando as repetições possuem os mesmos valores nos campos relevantes, a carga segue e o controle aparece como consistente com ressalva. Quando há divergência, somente os campos conflitantes ficam vazios e o conflito é registrado; atualmente isso **não bloqueia toda a publicação**. A página Controles e auditoria mostra os números reais da competência, em vez de estados fixos.

## Mapping

Os quatro conjuntos editáveis correspondem à antiga aba Mapping: aging, planta/local, lifecycle e status da operação.

Qualquer inclusão, alteração ou exclusão:

1. lista todas as competências existentes em `inventory_rows`;
2. limpa os valores derivados de Mapping (`operation_status`, `location_group`, `lifecycle` e `aging_bucket`);
3. reaplica as regras atuais em todas as competências;
4. devolve à interface a quantidade de competências e linhas recalculadas.

Os campos-fonte vindos de SAP, MB59 e All Brazil não são alterados pelo editor de Mapping.

## Relatórios e HTML compartilhável

Todas as consultas e visuais usam a competência selecionada. A navegação reaproveita dados pré-carregados e não recarrega cada página sem necessidade.

O botão **Share Link**, exclusivo de administradores, gera um arquivo `.html` autônomo. O arquivo não usa n8n, Google Drive, Apps Script, servidor local, CDN ou qualquer recurso externo. Depois da geração, o sistema oferece o painel nativo de compartilhamento de arquivos quando suportado pelo Windows/navegador e mantém a opção de download. O arquivo deve ser anexado diretamente no Slack ou em outro canal e aberto no navegador pelo destinatário. Um endereço `file:///C:/...` identifica apenas a cópia local e nunca deve ser enviado como link. Não é produzido um falso link público: sem hospedagem externa, o artefato compartilhável é o próprio arquivo.

O PDF continua sendo gerado localmente pelo Microsoft Edge em modo headless e entregue por uma rota autenticada de download. Quando o Optimus solicita esse artefato, o backend gera, valida e coloca o PDF em cache antes de devolver o botão ao chat. O clique exibe progresso, confere status HTTP, MIME e tamanho antes de salvar; uma resposta JSON de erro nunca é baixada como se fosse PDF. A correção pertence ao backend e à interface local; o roteamento PDF do workflow n8n não precisa ser alterado.

**Mesmos gráficos do dashboard.** O HTML do Share Link e o PDF (Visão e relatórios e Optimus) não têm mais um layout próprio: `reporting.render_dashboard_report()` abre o Edge headless com porta de depuração (CDP via `websockets`), injeta o cookie de sessão do usuário solicitante (`identity_subject` de `allowed_users`), fixa a largura em 1440 px e navega para `/?modo=relatorio&competencia=AAAA-MM#overview`. Nesse modo o `dashboard.html` esconde menu/topo, desliga animações e notificações, carrega só a Visão e relatórios e sinaliza `window.__reportReady`. Em seguida `buildReportDocument()` clona o painel com os SVGs já desenhados, troca seletores por texto, remove botões e itens de administrador e embute o CSS, gerando um HTML autônomo (sem scripts nem links para o servidor). O PDF é impresso a partir desse HTML com `Page.printToPDF` em A4 paisagem (escala 0,74, cards sem quebra). O PDF em cache vale só se for mais novo que o DuckDB **e** que o `dashboard.html`; a gravação usa arquivo `.parcial.pdf` + `os.replace`. Falhas (sem Edge, sem sessão, tempo esgotado de 120 s) caem no relatório simplificado `report_html()`. Como a página renderizada chama o próprio servidor, a ação local do Optimus roda em `run_in_threadpool` para não travar o loop assíncrono. Nenhuma mudança no n8n: o nó "Resposta PDF" continua só repassando `download_url`.

## Optimus

O Optimus usa Gemini por meio do workflow n8n para consultas e apresentações. O n8n não participa da geração do HTML compartilhável.

O backend distingue timeout, falha de conexão, HTTP do n8n, sessão, permissão e indisponibilidade do servidor local. A interface não afirma mais que toda falha é VPN. O diagnóstico de rede e VPN fica no Health Center.

O fluxo completo do agente, o contrato de contexto, os nós do workflow, as ferramentas locais, as confirmações, os avisos proativos e a configuração reutilizável do n8n estão descritos em [docs/optimus.md](docs/optimus.md).

## Health Center

Página de Inteligência com semáforos independentes e verificáveis para:

- SAP GUI e resultado da última execução;
- VPN/rede corporativa pela presença de conexão ou adaptador VPN ativo no Windows, incluindo GlobalProtect/PANGP/Palo Alto e demais clientes corporativos conhecidos, seguida do teste de rede; acesso comum à internet não prova VPN. O padrão pode ser ampliado por `OPS_VPN_ADAPTER_PATTERN` sem alterar o código;
- webhook n8n/Optimus por requisição HTTP independente, considerando online somente resposta de sucesso ou redirecionamento; HTTP 4xx/5xx nunca aparece verde;
- pasta All Brazil do Google Drive para computador;
- template/rota do Google Slides, explicitando que a credencial só é provada numa geração de ponta a ponta;
- DuckDB e quantidade de linhas da competência;
- presença de ZMM119, MB59 e All Brazil;
- sessão, perfil e permissões do usuário.

Cada semáforo abre um diagnóstico com evidência, orientação de correção e contato `transformacao_digital@gruposbf.com.br`. O percentual é calculado a partir dos estados reais; um componente que não pode ser comprovado integralmente aparece como atenção, e não como sucesso artificial. Indicadores em atenção ou críticos usam a mesma cor do alerta no semáforo e uma animação fina percorrendo o contorno do card; indicadores verdes permanecem estáticos.

O texto **Última verificação** mostra somente data e hora. A competência não é exibida nesse carimbo porque o Health Center representa a saúde global da instalação; quando algum diagnóstico usa dados de uma competência como evidência, isso permanece restrito ao detalhe técnico do indicador correspondente.

Enquanto o Health Center estiver aberto e visível, os diagnósticos são renovados automaticamente a cada 15 segundos. Após o GlobalProtect concluir a conexão, o farol normalmente muda no ciclo seguinte, considerando também o tempo da sonda de rede; o botão **Atualizar** permite uma verificação imediata.

## Instalador e atualização

O artefato publicado no projeto usa nome versionado, como `dist\INSTALAR_ESTOQUE_CONTABIL_2026.09.25.16.zip`; a cópia disponibilizada pela aplicação usa o nome estável `INSTALAR_ESTOQUE_CONTABIL.zip`. Depois de extrair, o usuário executa `INSTALAR_ESTOQUE_CONTABIL.bat`. O pacote usa o Python oficial ou o instala via Windows Package Manager, cria o ambiente isolado, instala dependências e grava o runtime local.

O instalador trata o banco DuckDB como dado do usuário, separado do runtime. Se o banco não existir, instala a fotografia embarcada; se já existir, retorna `kept_local_database` e não o abre para escrita. Migrações de estrutura continuam sendo aditivas na inicialização da aplicação, sem recriar as tabelas nem apagar linhas existentes.

O atalho da Área de Trabalho chama diretamente o `powershell.exe` nativo do Windows e executa o inicializador em `%LOCALAPPDATA%`, sem depender do Windows Script Host. A pasta Desktop é resolvida pela Known Folder oficial do Windows, inclusive quando redirecionada por OneDrive ou política corporativa, garantindo que o atalho visível seja substituído. Um VBS mínimo em ASCII puro e sem BOM é mantido apenas para compatibilidade, mas não participa do caminho normal. Essa arquitetura elimina o erro `800A0408 / Caractere inválido` observado em imagens corporativas cujo Windows Script Host rejeita arquivos VBS com BOM UTF-8.

O ZIP e o script BAT reduzem o alerta associado a executáveis PyInstaller sem assinatura, mas o SmartScreen pode continuar mostrando aviso de origem/reputação em arquivos novos. Sem assinatura digital corporativa não é tecnicamente possível garantir a eliminação desse aviso em todas as máquinas.

## Homologação

- Reconciliar duas competências fechadas com o Excel legado.
- Validar totais, cobertura, ordem MB59 → anterior → All Brazil e empresa 7170.
- Testar SAP GUI em cada perfil de máquina homologado.
- Testar o instalador em uma máquina sem acesso ao Drive do projeto.
- Validar Optimus e Slides de ponta a ponta no n8n.
- Validar o HTML autônomo em um computador sem o Estoque Contábil instalado.
