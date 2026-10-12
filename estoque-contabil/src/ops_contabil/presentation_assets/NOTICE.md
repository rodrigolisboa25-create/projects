# Componentes de terceiros

Os arquivos desta pasta (exceto este NOTICE) vêm do projeto **html-ppt-skill** — HTML PPT Studio
(https://github.com/lewislulu/html-ppt-skill), licença MIT, © 2026 lewis. Ver `LICENSE`.

Usados pelo gerador de apresentações do Optimus (`ops_contabil/presentations.py`), que embute estes
arquivos num único HTML autocontido (funciona offline):

- `base.css` — tokens e primitivas de layout (canvas 1920×1080, slides, kicker, títulos, grids, cards).
- `runtime.js` — navegação por teclado/toque, tela cheia (F), visão geral (O), modo apresentador (S).
- `animations.css` — animações de entrada (`data-anim`, `anim-stagger-list`).
- `fx-runtime.js` e `fx/*.js` — efeitos em canvas (`data-fx`); o gerador embute os módulos e esvazia a
  lista de carregamento dinâmico.
- `themes/*.css` — 10 temas (tokens de cor e tipografia).

Revisados antes da inclusão: não fazem chamadas de rede; usam apenas `localStorage` (layout do modo
apresentador), `BroadcastChannel`/`postMessage` (sincronia com a janela do apresentador) e `window.open`
(janela do apresentador, só ao pressionar S). `fonts.css` (Google Fonts) não foi incluído: as fontes caem
na pilha de fontes do sistema.
