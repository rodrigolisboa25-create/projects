# Componentes de terceiros

Os arquivos `base.css`, `animations.css`, `runtime.js`, `fx-runtime.js` e `fx/*.js` vêm do projeto
**html-ppt-skill**: HTML PPT Studio (https://github.com/lewislulu/html-ppt-skill), licença MIT, © 2026 lewis.
Ver `LICENSE`. São as mesmas cópias revisadas usadas no Estoque Contábil.

Usados pela apresentação **Fluxo de importação: Fisia × Centauro** (`fluxo_importacao.html`), aberta pelo
botão "Fluxo de importação" do REF. DOCS. Alterações do NexxusDoc: `fx-runtime.js` carrega só os módulos
distribuídos (`_util`, `constellation`, `gradient-blob`). O tema (`tema-nexxusdoc.css`) e o roteiro
(`fluxo_importacao.html`/`.js`) são do NexxusDoc.

`mapa_mundo.json`: contornos dos países do **Natural Earth** (domínio público), via world-atlas 2.0.2 (1:110m; o Brasil
em 1:50m), e divisas dos estados do Brasil da **malha oficial do IBGE** (API de malhas v3), já projetados (Natural Earth I,
meridiano central 30° L) pelo conversor do NexxusDoc. Sem código de terceiros: só dados.

Revisados antes da inclusão: não fazem chamadas de rede externas; usam `localStorage` (layout do modo
apresentador), `BroadcastChannel`/`postMessage` (janela do apresentador, tecla S) e `window.open` (só com S).
A apresentação lê os dados de `/api/refdocs` do próprio NexxusDoc (mesma origem, sessão já aberta).
