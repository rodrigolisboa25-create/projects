/* Query Console (06/11/2026, pedido do usuario): tabelas do BigQuery que automatizam cada procedimento da area, pela
   ordem da importacao. Ambiente claro, so nesta pagina. Dados: /api/query-console (catalogo curado query_console.json
   + documentos do sistema ligados na hora).
   Ampliada em 12/11/2026 (pedido do usuario): abas Procedimentos, Perguntar (pergunta em portugues vira SQL pelo
   agente), Catalogo do BigQuery (1.234 tabelas), Processos x tabelas e Minhas consultas (prontas, salvas,
   compartilhadas, favoritas e historico). Gera consultas quem o master habilitou (Configuracoes › Acessos); nada de
   custo aparece na tela, para ninguem (pedido do usuario). So a Logistica Internacional. */
(() => {
'use strict';
const S = {data: null, sel: '', fase: '', sit: '', tab: {}, busy: false, cols: 'todas', busca: '', sim: null, result: {}, editing: false, edits: {},
           view: (() => { try { return localStorage.getItem('nexus.qc.aba') || 'proc'; } catch { return 'proc'; } })(),
           ws: {sql: (() => { try { return localStorage.getItem('nexus.qc.ws') || ''; } catch { return ''; } })(), titulo: '', origem: 'editor',
                pergunta: '', answer: null, asking: false, sim: null, result: null, saving: false},
           cat: {q: '', projeto: '', tipo: '', pagina: 1, data: null, sel: '', table: null, loading: false},
           pr: {data: null, q: '', so: '', unid: ''}, lib: null,
           // fases recolhidas na visao geral (preferencia desta pessoa neste navegador)
           closed: new Set((() => { try { return JSON.parse(localStorage.getItem('nexus.qc.recolhidas') || '[]'); } catch { return []; } })())};
const saveClosed = () => { try { localStorage.setItem('nexus.qc.recolhidas', JSON.stringify([...S.closed])); } catch {} };
const root = () => document.getElementById('page-query');
const E = s => (typeof esc === 'function' ? esc(s) : String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c])));
const nf = (v, d = 0) => Number(v || 0).toLocaleString('pt-BR', {minimumFractionDigits: d, maximumFractionDigits: d});
const big = n => n >= 1e9 ? `${nf(n / 1e9, 1)} bi` : n >= 1e6 ? `${nf(n / 1e6, 1)} mi` : n >= 1e3 ? `${nf(n / 1e3, 0)} mil` : nf(n);
const size = g => g >= 1000 ? `${nf(g / 1000, 1)} TB` : g >= 1 ? `${nf(g, 1)} GB` : `${nf(g * 1000, 0)} MB`;
const brd = iso => iso ? iso.slice(0, 10).split('-').reverse().join('/') : '';
const I = p => `<svg viewBox="0 0 24 24" aria-hidden="true">${p}</svg>`;
const IC = {
  db: I('<ellipse cx="12" cy="5.5" rx="7" ry="2.6"/><path d="M5 5.5v13c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6v-13"/><path d="M5 12c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6"/>'),
  table: I('<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17M3.5 14.5h17M9.5 9.5v10"/>'),
  check: I('<path d="m5 12.5 4.5 4.5L19 7.5"/>'),
  spark: I('<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6.3 6.3l2.8 2.8M14.9 14.9l2.8 2.8M6.3 17.7l2.8-2.8M14.9 9.1l2.8-2.8"/>'),
  minus: I('<path d="M6 12h12"/>'),
  doc: I('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>'),
  link: I('<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>'),
  arrow: I('<path d="M5 12h14M13 6l6 6-6 6"/>'),
  back: I('<path d="M19 12H5M11 6l-6 6 6 6"/>'),
  copy: I('<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>'),
  play: I('<path d="M7 5v14l11-7z"/>'),
  lock: I('<rect x="5" y="11" width="14" height="9.5" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>'),
  info: I('<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5m0-8h.01"/>'),
  warn: I('<path d="M12 4 2.8 19.5h18.4z"/><path d="M12 10v4.5m0 2.5h.01"/>'),
  clock: I('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'),
  rows: I('<path d="M4 6h16M4 12h16M4 18h16"/>'),
  cols: I('<path d="M6 4v16M12 4v16M18 4v16"/>'),
  part: I('<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>'),
  code: I('<path d="m8 8-4 4 4 4M16 8l4 4-4 4M13.5 5l-3 14"/>'),
  plug: I('<path d="M9 3v5M15 3v5M7 8h10v3a5 5 0 0 1-10 0zM12 16v5"/>'),
  layers: I('<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>'),
  target: I('<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r=".8"/>'),
  chevd: I('<path d="m6 9 6 6 6-6"/>'),
  chevu: I('<path d="m6 15 6-6 6 6"/>'),
};
const fase = id => (S.data.fases || []).find(f => f.id === id) || {nome: id, cor: '#6B7B72'};
const procs = () => S.data.procedimentos || [];
const proc = id => procs().find(p => p.id === id);
const shortT = id => { const t = S.data.tabelas[id]; return t ? t.caminho.split('.').pop().replace(/^sap_/, '').replace(/^example_table(fat|flt)_/, '').toUpperCase() : id; };
const toast = msg => { document.querySelector('.qc-toast')?.remove(); const t = document.createElement('div'); t.className = 'qc-toast'; t.textContent = msg; document.body.appendChild(t); setTimeout(() => t.remove(), 3200); };

async function open() {
  const r = root(); if (!r) return;
  if (!S.data) {
    r.innerHTML = '<div class="qc-loading">Carregando a Query Console…</div>';
    try { S.data = await api('/api/query-console'); } catch (e) { r.innerHTML = `<div class="notice error"><div class="grow">${E(e.message)}</div></div>`; return; }
  }
  render();
}

function filtered() {
  return procs().filter(p => (!S.fase || p.fase === S.fase) && (!S.sit || (S.sit === 'prio' ? p.prioridade : S.sit === 'ok' ? p.conferido
    : S.sit === 'doc' ? p.documentado : !p.documentado)));
}

/* ---------------- topo ---------------- */
function heroArt() {
  // A animacao (CSS transform) fica no g de dentro: no mesmo g ela apagaria o translate do SVG e empilharia os cartoes.
  const card = (x, y, cls, head, rows) => `<g transform="translate(${x} ${y})"><g class="float ${cls}">
    <rect width="150" height="${30 + rows * 17}" rx="12" fill="#fff" stroke="#CFE0C0"/>
    <rect width="150" height="26" rx="12" fill="${head}"/><rect y="14" width="150" height="12" fill="${head}"/>
    <circle cx="14" cy="13" r="4" fill="#fff" opacity=".9"/><rect x="24" y="10" width="64" height="6" rx="3" fill="#fff" opacity=".85"/>
    ${Array.from({length: rows}, (_, i) => `<rect x="12" y="${36 + i * 17}" width="${44 + (i * 23) % 40}" height="6" rx="3" fill="#D6E2CC"/>
      <rect x="${92 - (i % 2) * 6}" y="${36 + i * 17}" width="${40 + (i % 3) * 6}" height="6" rx="3" fill="${i % 2 ? '#E3ECF9' : '#EEF5DF'}"/>`).join('')}</g></g>`;
  return `<svg viewBox="0 0 360 190">
    <defs><linearGradient id="qcg" x1="0" x2="1"><stop offset="0" stop-color="#AFD037"/><stop offset="1" stop-color="#3B82F6"/></linearGradient></defs>
    <path d="M60 150 C 140 150, 150 70, 230 70" stroke="url(#qcg)" stroke-width="2.4" stroke-dasharray="5 6" fill="none"/>
    <path d="M150 170 C 210 170, 230 130, 290 128" stroke="url(#qcg)" stroke-width="2.4" stroke-dasharray="5 6" fill="none"/>
    ${card(0, 92, 'a', '#0B5B2B', 4)}${card(196, 0, 'b', '#2563EB', 5)}${card(120, 112, 'c', '#7CA21F', 3)}</svg>`;
}

function headHtml() {
  const d = S.data, all = procs(), tabs = Object.values(d.tabelas || {});
  const ok = tabs.filter(t => t.conferida).length, sap = tabs.filter(t => t.origem.startsWith('SAP')).length;
  const docd = all.filter(p => p.documentado).length;
  const pct = (a, b) => `${b ? Math.round(a / b * 100) : 0}%`;
  const prios = all.filter(p => p.prioridade).sort((a, b) => a.prioridade - b.prioridade);
  return `<section class="qc-hero"><div class="qc-hero-txt">
      <span class="qc-eyebrow">${IC.db}BIGQUERY · LOGÍSTICA INTERNACIONAL</span>
      <h1><span>Query Console</span></h1>
      <p>Tabelas do BigQuery que podem automatizar cada procedimento da área, consultas prontas e perguntas em português que viram SQL.</p>
      <div class="qc-chips"><span>${IC.clock}Levantamento de <b>${E(d.levantamento)}</b></span>${d.catalogo_total ? `<span>${IC.table}<b>${nf(d.catalogo_total)}</b> tabelas no catálogo</span>` : ''}
        <span class="qc-access${d.pode_gerar ? ' on' : ''}">${d.pode_gerar ? IC.play + 'Você gera consultas' : IC.lock + 'Leitura para todos · gerar consultas é liberado pelo administrador'}</span></div>
    </div><div class="qc-art">${heroArt()}</div></section>
    <div class="qc-stats">
      <div class="qc-stat"><div class="lab">PROCEDIMENTOS${IC.layers}</div><div class="big">${all.length}</div>
        <div class="sub">${docd} já têm documento no sistema; ${all.length - docd} ainda sem documento escrito</div>
        <div class="qc-bar"><i class="a" style="width:${pct(docd, all.length)}"></i><i class="b" style="width:${pct(all.length - docd, all.length)};opacity:.35"></i></div></div>
      <div class="qc-stat"><div class="lab">TABELAS DO BIGQUERY${IC.table}</div><div class="big">${tabs.length}</div>
        <div class="sub">${sap} do SAP S/4HANA · ${tabs.length - sap} da camada refined da Fisia</div>
        <div class="qc-bar"><i class="a" style="width:${pct(sap, tabs.length)}"></i><i class="c" style="width:${pct(tabs.length - sap, tabs.length)}"></i></div></div>
      <div class="qc-stat"><div class="lab">CONFERIDAS COM DADOS${IC.check}</div><div class="big">${ok}<small>de ${tabs.length}</small></div>
        <div class="sub">as demais têm a estrutura conferida; os dados, na primeira consulta</div>
        <div class="qc-bar"><i class="c" style="width:${pct(ok, tabs.length)}"></i></div></div>
      <div class="qc-stat"><div class="lab">POR ONDE COMEÇAR${IC.target}</div>
        <ul class="qc-prio">${prios.map(p => `<li><b>${p.prioridade}</b><button type="button" data-qproc="${E(p.id)}">${E(p.titulo)}</button></li>`).join('')}</ul></div>
    </div>`;
}
function journeyHtml() {
  const d = S.data, all = procs();
  const steps = [{id: '', nome: 'Todas as fases'}, ...d.fases].map((f, i) => {
    const ps = f.id ? all.filter(p => p.fase === f.id) : all, nt = new Set(ps.flatMap(p => p.tabelas.map(t => t.id))).size;
    return `<button type="button" class="qc-step${S.fase === f.id ? ' on' : ''}${f.id ? '' : ' all'}" data-qfase="${E(f.id)}"${f.cor ? ` style="--fc:${E(f.cor)}"` : ''}><span class="k">${i ? String(i).padStart(2, '0') : 'TODAS'}</span>
      <span class="t">${E(f.nome)}</span><span class="m"><span><b>${ps.length}</b> proc.</span><span><b>${nt}</b> tabelas</span></span></button>`;
  }).join('');
  return `<div class="qc-journey">${steps}</div>`;
}

function filterHtml() {
  const list = filtered(), d = S.data;
  const groups = d.fases.map(f => { const ps = list.filter(p => p.fase === f.id); return ps.length ? `<optgroup label="${E(f.nome)}">${ps.map(p =>
    `<option value="${E(p.id)}"${S.sel === p.id ? ' selected' : ''}>${E(p.titulo)}${p.prioridade ? ` · prioridade ${p.prioridade}` : ''}</option>`).join('')}</optgroup>` : ''; }).join('');
  const sit = [['', 'Todas'], ['prio', 'Prioridades para começar'], ['ok', 'Ligação conferida com dados'], ['doc', 'Com documento no sistema'], ['nodoc', 'Ainda sem documento']];
  return `<div class="qc-filter">
    <label class="qc-proc">Procedimento<select id="qc-proc" class="${S.sel ? 'on' : ''}"><option value="">Todos os procedimentos (${list.length})</option>${groups}</select></label>
    <label>Fase<select id="qc-fase" class="${S.fase ? 'on' : ''}"><option value="">Todas</option>${d.fases.map(f => `<option value="${E(f.id)}"${S.fase === f.id ? ' selected' : ''}>${E(f.nome)}</option>`).join('')}</select></label>
    <label>Situação<select id="qc-sit" class="${S.sit ? 'on' : ''}">${sit.map(([v, t]) => `<option value="${v}"${S.sit === v ? ' selected' : ''}>${t}</option>`).join('')}</select></label>
    <span class="grow"></span>
    ${S.sel || S.fase || S.sit ? `<button type="button" class="qc-btn" data-qreset>${IC.back}Ver todos</button>` : `<span class="qc-count">${list.length} procedimentos · ${Object.keys(d.tabelas).length} tabelas</span>`}
  </div>`;
}

/* ---------------- visao geral ---------------- */
function pills(p, withFase) {
  const f = fase(p.fase);
  return `${withFase ? `<span class="qc-pill fase">${E(f.nome)}</span>` : ''}
    ${p.prioridade ? `<span class="qc-pill prio">${IC.target}Prioridade ${p.prioridade}</span>` : ''}
    ${p.conferido ? `<span class="qc-pill ok">${IC.check}Ligação conferida</span>` : ''}
    ${p.documentado ? `<span class="qc-pill doc">${IC.doc}${p.docs_sistema.length} no sistema</span>` : '<span class="qc-pill nodoc">Sem documento</span>'}
    ${(p.unidades || []).map(u => `<span class="qc-pill unit">${E(u)}</span>`).join('')}`;
}
function overviewHtml() {
  const list = filtered();
  if (!list.length) return '<div class="qc-empty" style="margin-top:16px">Nenhum procedimento com esse filtro.</div>';
  const shown = S.data.fases.filter(f => list.some(p => p.fase === f.id));
  const allClosed = shown.every(f => S.closed.has(f.id));
  return `<div class="qc-groups-bar"><button type="button" class="qc-btn" data-qtoggle-all="${allClosed ? 'abrir' : 'fechar'}">${allClosed ? IC.chevd + 'Expandir todas' : IC.chevu + 'Recolher todas'}</button></div>`
    + S.data.fases.map((f, i) => {
    const ps = list.filter(p => p.fase === f.id); if (!ps.length) return '';
    const closed = S.closed.has(f.id);
    return `<section class="qc-group${closed ? ' closed' : ''}"><button type="button" class="qc-group-h" data-qgroup="${E(f.id)}" aria-expanded="${!closed}">
        <span class="k">${String(i + 1).padStart(2, '0')}</span><h3>${E(f.nome)}</h3><small>${ps.length} procedimento(s)</small>
        <span class="tog">${closed ? 'Expandir' : 'Recolher'}${IC.chevd}</span></button>
      <div class="qc-grid">${ps.map(p => `<button type="button" class="qc-card" data-qproc="${E(p.id)}">
        <div class="top">${pills(p, false)}</div><h4>${E(p.titulo)}</h4><p>${E(p.serve)}</p>
        <div class="tabs">${p.tabelas.map(t => `<span class="qc-tt">${E(shortT(t.id))}</span>`).join('')}</div>
        <div class="foot">${IC.db}${p.gb_estimado != null ? `≈ ${size(p.gb_estimado)} por consulta` : 'leitura a medir'}<span class="go">Ver tabelas${IC.arrow}</span></div></button>`).join('')}</div></section>`;
  }).join('') + bottomHtml();
}
function bottomHtml() {
  const d = S.data, loose = d.a_mapear || [];
  // "Documentos novos a mapear" so aparece quando existe algum (pedido do usuario: sem quadro vazio).
  return `${loose.length ? `<div class="qc-box qc-loose"><h3>${IC.doc}Documentos novos a mapear (${loose.length})</h3><p>Entraram no sistema e ainda não se encaixam em nenhum procedimento desta página.</p>
      <div class="qc-docs">${loose.map(docRow).join('')}</div></div>` : ''}
    <div class="qc-box qc-nouse-box"><h3>${IC.minus}Sem uso no BigQuery hoje</h3><p>Dependem da PGL, do Siscomex ou de terceiros: entram quando a API da PGL (ou da Flowls) chegar ao BigQuery.</p>
      <div class="qc-nouse">${(d.sem_uso || []).map(s => `<div>${IC.info}<div><b>${E(s.titulo)}</b><span>${E(s.motivo)}</span></div></div>`).join('')}</div></div>`;
}
const docRow = d => `<${d.link ? `a href="${E(d.link)}" target="_blank" rel="noopener"` : 'div'} class="qc-doc"><span class="o${d.nexxus ? ' nx' : ''}">${E(d.origem)}</span><span>${E(d.titulo)}</span>${d.detalhe ? `<small>${E(d.detalhe)}</small>` : ''}</${d.link ? 'a' : 'div'}>`;

/* ---------------- detalhe ---------------- */
function vary(v, i) {
  const s = String(v ?? '');
  if (!i || !s) return s;
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) { const d = new Date(s.slice(0, 10) + 'T12:00'); d.setDate(d.getDate() + i * 3); return d.toISOString().slice(0, 10) + s.slice(10); }
  if (/^\d{1,3}(\.\d{3})*(,\d+)?$/.test(s) && (s.includes('.') || s.includes(','))) {
    const dec = (s.split(',')[1] || '').length, n = Number(s.replace(/\./g, '').replace(',', '.')) * [1, .83, 1.21, .66, 1.08, .74][i % 6];
    return n.toLocaleString('pt-BR', {minimumFractionDigits: dec, maximumFractionDigits: dec});
  }
  const m = s.match(/^(.*?)(\d{5,})$/); if (m) { const n = String(BigInt(m[2]) + BigInt(i * 7)).padStart(m[2].length, '0'); return m[1] + n; }
  return s;
}
function tableHtml(p, use) {
  const t = S.data.tabelas[use.id]; if (!t) return '';
  const used = new Set(use.colunas), [proj, ds, name] = t.caminho.split('.');
  return `<div class="qc-tbl"><div class="qc-tbl-top"><span class="qc-tbl-ico">${IC.table}</span><div><h3>${E(t.nome)}</h3><p>${E(t.descricao)}</p></div></div>
    <div class="qc-path"><code class="mono">${E(proj)}.${E(ds)}.<b>${E(name)}</b></code><button type="button" data-qcopy="${E(t.caminho)}">${IC.copy}Copiar</button></div>
    <div class="qc-meta"><span>${IC.layers}${E(t.origem)}</span><span>${IC.rows}<b>${big(t.linhas)}</b>&nbsp;linhas</span>${t.gb != null ? `<span>${IC.db}<b>${size(t.gb)}</b></span>` : ''}
      <span>${IC.cols}<b>${t.total_colunas}</b>&nbsp;colunas</span>${t.particao ? `<span>${IC.part}Partição: <b class="mono">${E(t.particao)}</b></span>` : ''}
      <span>${IC.clock}Atualizada em ${brd(t.atualizada_em)}</span>
      ${t.conferida ? `<span class="good">${IC.check}Conferida com dados</span>` : `<span class="todo">${IC.info}A conferir com dados</span>`}</div>
    <div class="qc-use">${IC.target}<div><b>Neste procedimento:</b> ${E(use.uso)}</div></div>
    <div class="qc-h"><h4>Colunas da tabela (${t.total_colunas})</h4><small>role para ver todas · em verde, as ${used.size} usadas neste procedimento</small></div>
    <div class="qc-cols scroll">${colsListHtml(t, used)}</div></div>`;
}
// Todas as colunas, numa lista com rolagem vertical: as usadas primeiro (destacadas), depois as demais na ordem do BigQuery.
function colsListHtml(t, used) {
  const info = Object.fromEntries(t.colunas.map(c => [c.nome, c]));
  const all = t.todas_colunas || t.colunas.map(c => [c.nome, c.tipo]);
  const row = ([n, ty]) => `<tr class="${used.has(n) ? 'used' : ''}"><td class="c" data-qcol="${E(n)}">${E(n)}</td><td><span class="qc-type">${E(ty)}</span></td><td>${E(info[n]?.descricao || '')}</td></tr>`;
  const first = all.filter(([n]) => used.has(n)), rest = all.filter(([n]) => !used.has(n));
  return `<table><thead><tr><th>Coluna</th><th>Tipo</th><th>O que é</th></tr></thead><tbody>${first.map(row).join('')}
    ${rest.length ? `<tr class="sep"><td colspan="3">Demais colunas (${rest.length})</td></tr>` : ''}${rest.map(row).join('')}</tbody></table>`;
}
// Tabela completa do BigQuery na largura inteira da pagina (pedido do usuario: pegar a tabela toda, com rolagem horizontal).
function fullTableHtml(p, use) {
  const t = S.data.tabelas[use.id]; if (!t) return '';
  const used = new Set(use.colunas);
  return `<section class="qc-full"><div class="qc-gridbar"><span class="qc-tbl-ico sm">${IC.table}</span>
      <div><h3>Tabela no BigQuery · <span class="mono">${E(t.caminho.split('.').pop())}</span></h3><small>${E(t.nome)} · ${t.total_colunas} colunas, na ordem do BigQuery</small></div>
      <div class="qc-seg" role="group" aria-label="Colunas"><button type="button" data-qcols="todas" class="${S.cols === 'todas' ? 'on' : ''}">Todas as colunas (${t.total_colunas})</button>
        <button type="button" data-qcols="usadas" class="${S.cols === 'usadas' ? 'on' : ''}">Usadas aqui (${used.size})</button></div>
      <label class="qc-search">${I('<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>')}<input type="search" id="qc-busca" placeholder="Buscar coluna" value="${E(S.busca)}" aria-label="Buscar coluna"></label></div>
    <div class="qc-gwrap" id="qc-gwrap">${gridHtml(t, used)}</div>
    <div class="qc-note">${IC.info}Role para os lados para ver todas as colunas. Em verde, as usadas neste procedimento. Valores ilustrativos (não são dados reais) nas colunas principais; as demais ficam em branco no exemplo.</div></section>`;
}
function gridHtml(t, used) {
  const info = Object.fromEntries(t.colunas.map(c => [c.nome, c]));
  const q = S.busca.trim().toLowerCase();
  const cols = (t.todas_colunas || t.colunas.map(c => [c.nome, c.tipo])).filter(([n]) => (S.cols !== 'usadas' || used.has(n))
    && (!q || n.toLowerCase().includes(q) || (info[n]?.descricao || '').toLowerCase().includes(q)));
  if (!cols.length) return '<div class="qc-empty" style="margin:10px">Nenhuma coluna com esse nome.</div>';
  const cls = n => used.has(n) ? ' class="used"' : '';
  return `<table class="qc-grid-t"><thead><tr><th class="rn">#</th>${cols.map(([n, ty]) => `<th${cls(n)} data-qcol="${E(n)}">${E(n)}<small>${E(ty)}</small></th>`).join('')}</tr></thead>
    <tbody><tr class="desc"><td class="rn">O QUE É</td>${cols.map(([n]) => `<td${cls(n)}>${E(info[n]?.descricao || '')}</td>`).join('')}</tr>
    ${[0, 1, 2, 3, 4, 5].map(i => `<tr><td class="rn">${i + 1}</td>${cols.map(([n]) => info[n] ? `<td${cls(n)}>${E(vary(info[n].exemplo, i))}</td>` : `<td class="e${used.has(n) ? ' used' : ''}"></td>`).join('')}</tr>`).join('')}</tbody></table>`;
}
function sqlHtml(sql) {
  const KW = /\b(SELECT|FROM|WHERE|JOIN|LEFT|INNER|ON|AND|OR|NOT|IN|AS|GROUP|BY|ORDER|HAVING|WITH|DISTINCT|IS|NULL|DESC|ASC|CASE|WHEN|THEN|ELSE|END|LIMIT|USING|INTERVAL|DAY|IGNORE|NULLS|UNNEST)\b/g;
  const FN = /\b(SUM|COUNT|COUNTIF|MIN|MAX|IF|IFNULL|CAST|SAFE|PARSE_DATE|FORMAT_DATE|DATE_SUB|DATE_DIFF|TIMESTAMP_SUB|CURRENT_DATE|CURRENT_TIMESTAMP|LTRIM|SPLIT|OFFSET|ARRAY_AGG|ARRAY_LENGTH|STRING_AGG|STARTS_WITH|UPPER|REPLACE|CONCAT|ABS|DATE|NUMERIC)\b(?=\s*\()/g;
  const tok = /(`[^`]*`)|('[^']*')|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][\w]*)|([^`'\w]+)/g;
  return sql.split('\n').map(line => {
    let out = '', m;
    tok.lastIndex = 0;
    while ((m = tok.exec(line))) {
      if (m[1]) out += `<span class="t">${E(m[1])}</span>`;
      else if (m[2]) out += `<span class="s">${E(m[2])}</span>`;
      else if (m[3]) out += `<span class="num">${E(m[3])}</span>`;
      else if (m[4]) { const w = m[4]; KW.lastIndex = 0; FN.lastIndex = 0;
        out += /^(SELECT|FROM|WHERE|JOIN|LEFT|INNER|ON|AND|OR|NOT|IN|AS|GROUP|BY|ORDER|HAVING|WITH|DISTINCT|IS|NULL|DESC|ASC|CASE|WHEN|THEN|ELSE|END|LIMIT|USING|INTERVAL|DAY|IGNORE|NULLS|UNNEST)$/.test(w) ? `<span class="k">${w}</span>`
          : /^(SUM|COUNT|COUNTIF|MIN|MAX|IF|IFNULL|CAST|SAFE|PARSE_DATE|FORMAT_DATE|DATE_SUB|DATE_DIFF|TIMESTAMP_SUB|CURRENT_DATE|CURRENT_TIMESTAMP|LTRIM|SPLIT|OFFSET|ARRAY_AGG|ARRAY_LENGTH|STRING_AGG|STARTS_WITH|UPPER|REPLACE|CONCAT|ABS|DATE|NUMERIC|STRING|BigNumeric)$/.test(w) ? `<span class="f">${w}</span>` : E(w); }
      else out += E(m[5]);
    }
    return `<span class="ln">${out || ' '}</span>`;
  }).join('');
}
function detailHtml(p) {
  const f = fase(p.fase), tab = S.tab[p.id] || p.tabelas[0].id, use = p.tabelas.find(t => t.id === tab) || p.tabelas[0];
  const li = (cls, ic, items) => `<ul class="qc-list ${cls}">${items.map(x => `<li><i>${ic}</i><span>${E(x)}</span></li>`).join('')}</ul>`;
  const chain = (p.ligacao || []).map((x, i) => `${i ? IC.arrow : ''}<span>${E(x)}</span>`).join('');
  const docs = p.docs_sistema.length ? `<div class="qc-docs">${p.docs_sistema.map(docRow).join('')}</div>`
    : `<div class="qc-empty">Ainda sem documento escrito${p.processo ? ` (processo do inventário: <b>${E(p.processo)}</b>)` : ''}. Quando o procedimento entrar no NexxusDoc, aparece aqui sozinho.</div>`;
  const pode = S.data.pode_gerar;
  return `<div class="qc-detail"><article class="qc-desc">
      <div class="qc-crumb"><button type="button" class="qc-back" data-qreset>${IC.back}Todos os procedimentos</button></div>
      <h2>${E(p.titulo)}</h2><div class="qc-tags">${pills(p, true)}</div>
      <div class="qc-sec qc-serve"><h4>${IC.target}Para que serve</h4><p>${E(p.serve)}</p></div>
      <div class="qc-sec"><h4>${IC.clock}Como é feito hoje</h4><p>${E(p.hoje)}</p></div>
      <div class="qc-sec qc-two"><div><h4>${IC.check}O que cobre</h4>${li('cover', IC.check, p.cobre)}</div><div><h4>${IC.spark}O que facilita</h4>${li('easy', IC.spark, p.facilita)}</div></div>
      ${p.fora.length ? `<div class="qc-sec"><h4>${IC.minus}O que continua fora</h4>${li('out', IC.minus, p.fora)}</div>` : ''}
      <div class="qc-sec"><h4>${IC.link}Como as tabelas se ligam</h4><div class="qc-chain">${chain}</div></div>
      <div class="qc-sec"><h4>${IC.doc}Documentos no sistema</h4>${docs}</div>
    </article>
    <section class="qc-console"><div class="qc-con-head"><h3>${IC.db}Tabelas no BigQuery · ${p.tabelas.length}</h3></div>
      <div class="qc-tabs" role="tablist">${p.tabelas.map(t => `<button type="button" role="tab" class="qc-tab${t.id === use.id ? ' on' : ''}" data-qtab="${E(t.id)}" title="${E(t.uso)}"><i></i><span class="mono">${E(shortT(t.id))}</span></button>`).join('')}</div>
      ${tableHtml(p, use)}</section></div>
    ${fullTableHtml(p, use)}
    <section class="qc-sql"><div class="qc-sql-head"><h3>${IC.code}Consulta sugerida</h3><span id="qc-sql-state" class="qc-sql-state">${pode ? (curSql(p), editState(p.id in S.edits)) : ''}</span>
      <span class="info">${IC.db}Leitura estimada <b>${p.gb_estimado != null ? '≈ ' + size(p.gb_estimado) : 'a medir'}</b> (consulta original) · só leitura</span>
      <span class="grow"></span>
      ${pode ? `<button type="button" class="qc-btn${S.editing ? ' on' : ''}" data-qedit>${IC.code}${S.editing ? 'Concluir edição' : 'Editar consulta'}</button>` : ''}
      <button type="button" class="qc-btn" data-qcopy-sql>${IC.copy}Copiar SQL</button>
      ${pode ? `<button type="button" class="qc-btn" data-qto-ws title="Levar esta consulta para a aba Perguntar, para ajustar com o agente, salvar ou executar">${IC.arrow}Abrir no editor</button>
        <button type="button" class="qc-btn primary" data-qrun>${IC.play}Gerar consulta</button>` : `<span class="qc-lockmsg">${IC.lock}Gerar consultas é liberado pelo administrador (Configurações › Acessos)</span><button type="button" class="qc-btn" disabled>${IC.lock}Gerar consulta</button>`}</div>
      ${pode && S.editing ? `<div class="qc-edit-hint">${IC.info}<span>Edite à vontade (incluir ou tirar colunas, filtros, período). <b>Clique numa coluna</b> da lista à direita ou da tabela acima para inserir o nome no cursor. Na simulação o sistema confere que é só leitura (SELECT) e só tabelas dos projetos de dados. A versão editada fica guardada neste navegador.</span></div>
        <textarea id="qc-sql-edit" class="qc-edit" spellcheck="false" aria-label="Editar a consulta">${E(curSql(p))}</textarea>`
        : `<pre class="qc-code">${sqlHtml(pode ? curSql(p) : p.sql)}</pre>`}
      <div class="qc-run${S.procRun[p.id] ? ' on' : ''}" id="qc-run">${runBoxHtml(S.procRun[p.id], PROC_ATTRS)}</div></section>
    ${resultHtml(p)}`;
}

/* ---------------- gerar consulta (so o master): simula, confirma, executa ---------------- */
// Executando (13/11/2026, pedido do usuario): no lugar onde a tabela vai aparecer, um circulo girando com o tempo.
function loadingHtml(run) {
  return `<section class="qc-full qc-result qc-running" aria-live="polite" aria-busy="true"><div class="qc-gridbar"><span class="qc-tbl-ico sm">${IC.rows}</span>
      <div><h3>Resultado da consulta</h3><small>Executando no BigQuery… <b data-tl>${Math.round((Date.now() - run.t0) / 1000)} s</b></small></div></div>
    <div class="qc-loadbox"><span class="qc-spin" role="progressbar" aria-label="Executando a consulta"><i></i></span><b>Gerando a tabela…</b>
      <small>O resultado aparece aqui assim que o BigQuery terminar. Pode trocar de aba ou de página: a consulta continua.</small></div></section>`;
}
function resultHtml(p) {
  if (S.procRun[p.id]?.fase === 'exec') return loadingHtml(S.procRun[p.id]);
  const r = S.result[p.id]; if (!r) return '';
  return `<section class="qc-full qc-result"><div class="qc-gridbar"><span class="qc-tbl-ico sm">${IC.rows}</span>
      <div><h3>Resultado da consulta</h3><small>${nf(r.total_linhas)} linha(s)${r.mostradas < r.total_linhas ? ` · mostrando as ${nf(r.mostradas)} primeiras` : ''}${r.gb_processados != null ? ` · ${size(r.gb_processados)} processados` : ''} · ${nf(r.segundos, 1)} s · ${E(r.quando)}</small></div>
      <span class="grow" style="flex:1"></span>
      <button type="button" class="qc-btn" data-qxlsx>${IC.table}Baixar Excel</button><button type="button" class="qc-btn" data-qcsv>${IC.copy}Baixar CSV</button><button type="button" class="qc-btn" data-qclose>Fechar</button></div>
    ${r.linhas.length ? `<div class="qc-gwrap"><table class="qc-grid-t"><thead><tr><th class="rn">#</th>${r.colunas.map(c => `<th>${E(c)}</th>`).join('')}</tr></thead>
      <tbody>${r.linhas.map((row, i) => `<tr><td class="rn">${i + 1}</td>${row.map(v => `<td>${E(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`
      : '<div class="qc-empty">A consulta não devolveu linhas no período.</div>'}</section>`;
}
/* Andamento de gerar/executar guardado no estado (13/11/2026, pedido do usuario): trocar de aba ou de pagina nao para
   a consulta nem perde o andamento; ao voltar, o quadro mostra onde ela esta. Quando fica pronta e a pessoa nao esta
   olhando, vai um aviso do Windows (categoria "consulta"). */
S.procRun = {};
function runBoxHtml(r, attrs) {
  if (!r) return '';
  if (r.fase === 'conf') return `${IC.clock}<span>Conferindo a consulta no BigQuery…</span>`;
  if (r.fase === 'exec') return `${IC.clock}<span>Executando no BigQuery… <b data-t>${Math.round((Date.now() - r.t0) / 1000)} s</b></span>`;
  if (r.fase === 'pronto') return `${IC.info}<span>${r.editada ? '<b>Consulta editada.</b> ' : ''}Vai ler <b>${size(r.gb)}</b>${r.tabs ? ` · tabelas: ${r.tabs}` : ''}. Só leitura; até 500 linhas aparecem aqui. Confirma?</span>
    <span style="flex:1"></span><button type="button" class="qc-btn" ${attrs.cancel}>Cancelar</button><button type="button" class="qc-btn primary" ${attrs.exec}>${IC.play}Executar consulta</button>`;
  return `${IC.warn}<span>${E(r.msg)}</span>`;
}
function paintRun(id, r, attrs) {
  const box = document.getElementById(id); if (!box) return;
  box.className = 'qc-run' + (r ? ' on' : ''); box.innerHTML = runBoxHtml(r, attrs);
  const tl = document.querySelector('#page-query .qc-running [data-tl]');
  if (tl && r?.t0) tl.textContent = `${Math.round((Date.now() - r.t0) / 1000)} s`;
}
const PROC_ATTRS = {cancel: 'data-qcancel', exec: 'data-qexec'}, WS_ATTRS = {cancel: 'data-qws-cancel', exec: 'data-qws-exec'};
const paintProc = id => { paintNav(); if (S.view === 'proc' && S.sel === id) paintRun('qc-run', S.procRun[id], PROC_ATTRS); };
const paintWs = () => { paintNav(); if (S.view === 'perguntar') paintRun('qc-ws-run', S.ws.run, WS_ATTRS); };
function notifyDone(titulo, texto, view, sel) {
  const page = document.getElementById('page-query');
  const watching = !document.hidden && document.hasFocus() && page && !page.classList.contains('hidden') && S.view === view && (!sel || S.sel === sel);
  if (watching) return;
  postJson('/api/notificacoes/enviar', {categoria: 'consulta', titulo, texto: String(texto || '').slice(0, 300), pagina: 'query:' + view}).catch(() => {});
}
async function runFlow(p) {
  S.procRun[p.id] = {fase: 'conf'}; paintProc(p.id);
  try {
    const sql = curSql(p);
    const s = await postJson(`/api/query-console/${encodeURIComponent(p.id)}/simular`, {sql}); S.sim = {id: p.id, sql, ...s};
    S.procRun[p.id] = {fase: 'pronto', gb: s.gb, editada: s.editada, tabs: (s.tabelas || []).map(t => `<code>${E(t.split('.').pop())}</code>`).join(', ')};
  } catch (e) { S.procRun[p.id] = {fase: 'erro', msg: e.message}; }
  paintProc(p.id);
}
async function execFlow(p) {
  if (S.sim?.id !== p.id) return;
  S.procRun[p.id] = {fase: 'exec', t0: Date.now()}; paintProc(p.id);
  const here = () => S.view === 'proc' && S.sel === p.id;
  if (here()) { render(); document.querySelector('#page-query .qc-running')?.scrollIntoView({behavior: 'smooth', block: 'center'}); }
  const tick = setInterval(() => paintProc(p.id), 1000), sql = S.sim.sql;
  try {
    const r = await postJson(`/api/query-console/${encodeURIComponent(p.id)}/executar`, {confirmado: true, sql});
    S.result[p.id] = {...r, quando: new Date().toLocaleString('pt-BR')}; S.sim = null; delete S.procRun[p.id]; clearInterval(tick);
    if (S.view === 'proc' && S.sel === p.id) { render(); document.querySelector('.qc-result')?.scrollIntoView({behavior: 'smooth', block: 'start'}); }
    notifyDone('Resultado da consulta pronto', `${p.titulo}: ${nf(r.total_linhas)} linha(s).`, 'proc', p.id);
  } catch (e) {
    clearInterval(tick); S.procRun[p.id] = {fase: 'erro', msg: e.message}; if (here()) render(); else paintProc(p.id);
    notifyDone('Consulta não executada', `${p.titulo}: ${e.message}`, 'proc', p.id);
  }
}
function downloadCsv(p) {
  const r = S.result[p.id]; if (!r) return;
  const q = v => /[;"\n]/.test(v) ? `"${String(v).replace(/"/g, '""')}"` : v;
  const csv = '﻿' + [r.colunas, ...r.linhas].map(row => row.map(q).join(';')).join('\r\n');
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], {type: 'text/csv;charset=utf-8'}));
  a.download = `query_console_${p.id}_${new Date().toISOString().slice(0, 10)}.csv`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

/* ---------------- edicao da consulta (so o master) ----------------
   A versao editada fica so neste navegador, por procedimento; o servidor confere tudo de novo na simulacao. */
const editKey = id => `nexus.qc.sql.${id}`;
function curSql(p) {
  if (!(p.id in S.edits)) { try { const v = localStorage.getItem(editKey(p.id)); if (v) S.edits[p.id] = v; } catch {} }
  return S.edits[p.id] ?? p.sql;
}
function setEdit(p, text) {
  const edited = text.trim() !== p.sql.trim();
  if (edited) S.edits[p.id] = text; else delete S.edits[p.id];
  try { edited ? localStorage.setItem(editKey(p.id), text) : localStorage.removeItem(editKey(p.id)); } catch {}
  S.sim = null; if (S.procRun[p.id]?.fase !== 'exec') { delete S.procRun[p.id]; paintRun('qc-run', null, PROC_ATTRS); }
  const st = document.getElementById('qc-sql-state'); if (st) st.innerHTML = editState(edited);
}
const editState = edited => edited ? `<span class="qc-pill prio">${IC.code}Editada por você</span><button type="button" class="qc-btn sm" data-qrestore>${IC.back}Restaurar original</button>` : '';
function insertColumn(name) {
  const ta = document.getElementById('qc-sql-edit'); if (!ta) return;
  const a = ta.selectionStart ?? ta.value.length, b = ta.selectionEnd ?? a;
  ta.value = ta.value.slice(0, a) + name + ta.value.slice(b);
  ta.focus(); ta.selectionStart = ta.selectionEnd = a + name.length;
  setEdit(proc(S.sel), ta.value); toast(`Coluna ${name} inserida na consulta.`);
}

/* ---------------- abas (12/11/2026) ---------------- */
const VIEWS = [['proc', 'Procedimentos', IC.layers], ['perguntar', 'Perguntar', IC.spark], ['catalogo', 'Catálogo do BigQuery', IC.db],
               ['processos', 'Processos × tabelas', IC.link], ['biblioteca', 'Minhas consultas', IC.doc]];
function navHtml() {
  return `<nav class="qc-nav" role="tablist" aria-label="Seções da Query Console">${VIEWS.map(([id, t, ic]) =>
    `<button type="button" role="tab" class="qc-navb${S.view === id ? ' on' : ''}" data-qview="${id}" aria-selected="${S.view === id}">${ic}<span>${t}</span>${busyView(id) ? '<i class="qc-busy" title="Consulta em andamento"></i>' : ''}</button>`).join('')}</nav>`;
}
// pontinho pulsando na aba enquanto ha consulta montando ou executando nela (13/11/2026)
function busyView(id) {
  if (id === 'perguntar') return Boolean(S.ws.asking || ['conf', 'exec'].includes(S.ws.run?.fase));
  if (id === 'proc') return Object.values(S.procRun || {}).some(r => ['conf', 'exec'].includes(r?.fase));
  return false;
}
function paintNav() { const n = root()?.querySelector('.qc-nav'); if (n) n.outerHTML = navHtml(); }
function setView(v) { S.view = v; try { localStorage.setItem('nexus.qc.aba', v); } catch {} render(); }
const SEARCH = I('<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>');
const shortId = id => String(id || '').split('.').pop().replace(/^sap_/, '');
const projOf = id => String(id || '').split('.')[0];
async function download(url, body, name) {
  try {
    const r = await fetch(url, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    if (!r.ok) { let m = 'Não consegui gerar o arquivo.'; try { m = (await r.json()).detail || m; } catch {} toast(m); return; }
    const a = document.createElement('a'); a.href = URL.createObjectURL(await r.blob()); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 3000);
  } catch { toast('Não consegui gerar o arquivo.'); }
}
const xlsxName = t => `Query_Console_${(t || 'consulta').normalize('NFD').replace(/[^\w ]+/g, '').trim().replace(/\s+/g, '_').slice(0, 50) || 'consulta'}_${new Date().toISOString().slice(0, 10)}.xlsx`;
function resultTable(r, attrs) {
  return `<section class="qc-full qc-result"><div class="qc-gridbar"><span class="qc-tbl-ico sm">${IC.rows}</span>
      <div><h3>Resultado da consulta</h3><small>${nf(r.total_linhas)} linha(s)${r.mostradas < r.total_linhas ? ` · mostrando as ${nf(r.mostradas)} primeiras` : ''}${r.gb_processados != null ? ` · ${size(r.gb_processados)} processados` : ''} · ${nf(r.segundos, 1)} s · ${E(r.quando)}</small></div>
      <span class="grow" style="flex:1"></span>
      <button type="button" class="qc-btn" ${attrs.xlsx}>${IC.table}Baixar Excel</button><button type="button" class="qc-btn" ${attrs.csv}>${IC.copy}Baixar CSV</button><button type="button" class="qc-btn" ${attrs.close}>Fechar</button></div>
    ${r.linhas.length ? `<div class="qc-gwrap"><table class="qc-grid-t"><thead><tr><th class="rn">#</th>${r.colunas.map(c => `<th>${E(c)}</th>`).join('')}</tr></thead>
      <tbody>${r.linhas.map((row, i) => `<tr><td class="rn">${i + 1}</td>${row.map(v => `<td>${E(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`
      : '<div class="qc-empty">A consulta não devolveu linhas.</div>'}</section>`;
}
function csvOf(r, name) {
  const q = v => /[;"\n]/.test(v) ? `"${String(v).replace(/"/g, '""')}"` : v;
  const csv = '﻿' + [r.colunas, ...r.linhas].map(row => row.map(q).join(';')).join('\r\n');
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], {type: 'text/csv;charset=utf-8'}));
  a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

/* ---- SQL organizado (13/11/2026, pedido do usuario: o agente devolvia a consulta numa linha so) ----
   Uma clausula por linha, uma coluna do SELECT por linha, AND/OR dos filtros alinhados e subconsultas recuadas. So
   mexe em espacos: textos entre aspas, nomes entre crases e comentarios ficam iguais. SQL que ja tem quebras de linha
   suficientes fica como veio. */
function formatSql(sql) {
  const s = String(sql || '').trim();
  if (!s || (s.match(/\n/g) || []).length >= Math.max(3, s.length / 140)) return s;
  const toks = s.match(/'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"|`[^`]*`|--[^\n]*|\s+|[(),]|[^\s(),'"`]+/g) || [];
  const CLAUSES = ['SELECT', 'FROM', 'WHERE', 'GROUP', 'ORDER', 'HAVING', 'QUALIFY', 'LIMIT', 'UNION', 'WINDOW', 'WITH'];
  const JOINERS = ['LEFT', 'RIGHT', 'INNER', 'FULL', 'CROSS'];
  const stack = [], clauses = [];
  let out = '', clause = '', afterSelect = false, between = false;
  const level = () => stack.filter(x => x === 'q').length;
  const nl = (extra = 0) => { out = out.replace(/[ \t]+$/, ''); if (!out.endsWith('\n')) out += '\n'; out += '  '.repeat(level() + extra); };
  const next = i => { let j = i + 1; while (j < toks.length && /^\s+$/.test(toks[j])) j++; return toks[j] || ''; };
  for (let i = 0; i < toks.length; i++) {
    const t = toks[i];
    if (/^\s+$/.test(t)) { if (out && !/[\s(]$/.test(out)) out += ' '; continue; }
    const U = t.toUpperCase(), inF = stack[stack.length - 1] === 'f';
    if (t.startsWith('--')) { out += t; nl(); continue; }
    if (t === '(') {
      const q = /^(SELECT|WITH)$/i.test(next(i));
      stack.push(q ? 'q' : 'f'); if (q) clauses.push(clause);
      out += '('; continue;
    }
    if (t === ')') {
      const k = stack.pop();
      if (k === 'q') { clause = clauses.pop() || ''; nl(); }
      out = out.replace(/ $/, '') + ')'; continue;
    }
    if (t === ',') {
      out = out.replace(/ $/, '') + ',';
      if (!inF && ['SELECT', 'GROUP', 'ORDER'].includes(clause)) nl(1);
      else if (!inF && clause === 'WITH') nl();
      continue;
    }
    if (afterSelect && U !== 'DISTINCT' && U !== 'AS' && U !== 'STRUCT') { afterSelect = false; nl(1); out += t; continue; }
    if (!inF && CLAUSES.includes(U)) {
      if (out.trim() && !out.endsWith('(')) nl(); else if (out.endsWith('(')) nl();
      out += t; clause = U; afterSelect = U === 'SELECT'; between = false; continue;
    }
    if (!inF && JOINERS.includes(U)) { nl(); out += t; clause = 'JOIN'; continue; }
    if (!inF && U === 'JOIN') { if (!/\b(LEFT|RIGHT|INNER|FULL|CROSS|OUTER)\s*$/i.test(out)) nl(); out += t; clause = 'JOIN'; continue; }
    if (U === 'BETWEEN') between = true;
    if (!inF && (U === 'AND' || U === 'OR') && ['WHERE', 'JOIN', 'QUALIFY', 'HAVING'].includes(clause)) {
      if (between && U === 'AND') { between = false; out += t; continue; }
      nl(1); out += t; continue;
    }
    out += t;
  }
  return out.replace(/[ \t]+\n/g, '\n').trim();
}

/* ---- Perguntar: pergunta em portugues -> SQL pelo agente; editor; executar; salvar ---- */
const EXAMPLES = ['Pedidos Nike da Fisia com quantidade em aberto por mês de remessa',
  'Notas fiscais de entrada recebidas no CD da Fisia nos últimos 15 dias, com o pedido',
  'MIROs lançadas nos últimos 30 dias por usuário e empresa',
  'Taxa do dólar (USD) para real nos últimos 30 dias'];
const saveWs = () => { try { localStorage.setItem('nexus.qc.ws', S.ws.sql); } catch {} };
function answerHtml(a) {
  const list = (t, xs, cls) => xs && xs.length ? `<div class="qc-ans-sec ${cls || ''}"><h4>${t}</h4><ul>${xs.map(x => `<li>${E(x)}</li>`).join('')}</ul></div>` : '';
  if (!a.sql) return `<div class="qc-answer warn">${IC.warn}<div><b>Sem consulta para esta pergunta.</b><p>${E(a.explicacao || 'O NexxusDoc não encontrou tabelas no BigQuery que respondam a esta pergunta.')}</p>${list('Depende de dados fora do BigQuery', a.fora_do_lake, 'out')}</div></div>`;
  // Tabela vazia ou parada (13/11/2026, pedido do usuario): o aviso vem ANTES; a consulta so vai ao editor se pedir.
  const alerts = a.alertas_tabelas || [];
  const alertBox = alerts.length ? `<div class="qc-answer warn qc-alert">${IC.warn}<div><b>${S.ws.pendente ? 'Atenção antes de gerar: a consulta usa tabela sem dados atualizados' : 'Atenção: a consulta usa tabela sem dados atualizados'}</b>
      <ul>${alerts.map(x => `<li>${E(x.texto)}</li>`).join('')}</ul>
      ${S.ws.pendente ? `<p>A consulta pode voltar vazia ou com dados antigos. Peça de outro jeito (ex.: "use as tabelas de origem do SAP") ou veja a consulta mesmo assim.</p>
      <div class="row"><button type="button" class="qc-btn" data-qalert-ok>${IC.code}Ver a consulta mesmo assim</button></div>` : ''}</div></div>` : '';
  return `${alertBox}<div class="qc-answer">${a.conferida ? `<span class="qc-pill ok">${IC.check}Conferida no BigQuery</span>` : `<span class="qc-pill nodoc">${IC.info}Não conferida${a.aviso ? ': ' + E(a.aviso) : ''}</span>`}
    <h3>${E(a.titulo || 'Consulta montada')}</h3><p>${E(a.explicacao)}</p>
    ${(a.tabelas || []).length ? `<div class="qc-ans-tabs">${a.tabelas.map(t => `<button type="button" class="qc-tt" data-qcat-open="${E(t)}" title="Ver a tabela no catálogo">${E(shortId(t))}</button>`).join('')}</div>` : ''}
    <div class="qc-ans-cols">${list('Premissas', a.premissas)}${list('Fora do BigQuery', a.fora_do_lake, 'out')}</div></div>`;
}
function saveFormHtml() {
  const w = S.ws, mine = w.editId && (S.lib?.minhas || []).find(q => q.id === w.editId);
  return `<div class="qc-save"><label>Título<input id="qc-save-t" maxlength="160" value="${E(w.titulo || '')}"></label>
    <label>Descrição (opcional)<textarea id="qc-save-d" rows="2" maxlength="1200">${E(w.descricao || '')}</textarea></label>
    <label class="chk"><input type="checkbox" id="qc-save-c"${w.compartilhada ? ' checked' : ''}> Compartilhar com a equipe (quem tem acesso à Query Console vê em Minhas consultas)</label>
    ${mine ? `<label class="chk"><input type="checkbox" id="qc-save-r" checked> Atualizar a consulta salva “${E(mine.titulo)}” (desmarque para salvar como nova)</label>` : ''}
    <div class="row"><button type="button" class="qc-btn" data-qsave-cancel>Cancelar</button><button type="button" class="qc-btn primary" data-qsave-ok>${IC.check}Salvar</button></div></div>`;
}
function wsHtml() {
  const pode = S.data.pode_gerar, w = S.ws, has = Boolean(w.sql.trim());
  const ask = `<section class="qc-box qc-ask"><h3>${IC.spark}Pergunte em português</h3>
    <p>Descreva o que quer ver. O NexxusDoc escolhe as tabelas do BigQuery, monta a consulta e confere antes de mostrar. Depois é só gerar.</p>
    ${pode ? `<div class="qc-ask-row"><textarea id="qc-ask-q" rows="3" maxlength="1500" placeholder="Ex.: pedidos Nike da Fisia com quantidade em aberto por mês de remessa da coleção atual">${E(w.pergunta)}</textarea>
      <div class="qc-ask-btns"><button type="button" class="qc-btn primary" data-qask${w.asking ? ' disabled' : ''}>${IC.spark}${w.asking ? 'Montando…' : 'Montar consulta'}</button>
      ${has ? `<button type="button" class="qc-btn" data-qask-adjust${w.asking ? ' disabled' : ''} title="Usa o texto acima para ajustar a consulta que está no editor">${IC.code}Ajustar a do editor</button>` : ''}</div></div>
      ${w.asking ? '<div class="qc-askprog" role="progressbar" aria-label="Montando a consulta"><div class="qc-askbar"><i></i></div><small class="qc-askpct">0%</small></div>' : ''}
      <div class="qc-examples"><small>Exemplos:</small>${EXAMPLES.map(x => `<button type="button" class="qc-ex" data-qex="${E(x)}">${E(x)}</button>`).join('')}</div>`
    : `<div class="qc-lockmsg">${IC.lock}Perguntar e gerar consultas é liberado pelo administrador (Configurações › Acessos). Você pode ver as consultas prontas, os processos e o catálogo.</div>`}
    ${w.asking ? `<div class="qc-run on">${IC.clock}<span>O NexxusDoc está montando a consulta… <b data-qt>0 s</b></span></div>` : ''}
    ${w.answer && !w.asking ? answerHtml(w.answer) : ''}</section>`;
  const editor = `<section class="qc-sql qc-ws"><div class="qc-sql-head"><h3>${IC.code}Editor de consulta</h3>
      <input id="qc-ws-title" class="qc-ws-title" maxlength="160" placeholder="Título (para salvar e para o Excel)" value="${E(w.titulo)}"${pode ? '' : ' disabled'}>
      <span class="grow"></span>
      <button type="button" class="qc-btn" data-qws-copy${has ? '' : ' disabled'}>${IC.copy}Copiar</button>
      ${pode ? `<button type="button" class="qc-btn" data-qws-save${has ? '' : ' disabled'}>${IC.doc}Salvar</button>
      <button type="button" class="qc-btn" data-qws-clear${has ? '' : ' disabled'}>Limpar</button>
      <button type="button" class="qc-btn primary" data-qws-run${has ? '' : ' disabled'}>${IC.play}Gerar consulta</button>` : ''}</div>
    ${w.saving ? saveFormHtml() : ''}
    <textarea id="qc-ws-sql" class="qc-edit" spellcheck="false" aria-label="Consulta SQL" placeholder="${pode ? 'A consulta montada aparece aqui. Você também pode escrever ou colar um SQL (só leitura: SELECT).' : 'Abra uma consulta pronta em Minhas consultas para ver o SQL.'}"${pode ? '' : ' readonly'}>${E(w.sql)}</textarea>
    <div class="qc-run${w.run ? ' on' : ''}" id="qc-ws-run">${runBoxHtml(w.run, WS_ATTRS)}</div></section>`;
  return `<div class="qc-ws-wrap">${ask}${editor}${w.run?.fase === 'exec' ? loadingHtml(w.run) : w.result ? resultTable(w.result, {xlsx: 'data-qws-xlsx', csv: 'data-qws-csv', close: 'data-qws-rclose'}) : ''}</div>`;
}
async function ask(adjust) {
  const q = (document.getElementById('qc-ask-q')?.value || '').trim();
  if (q.length < 5) { toast('Escreva a pergunta (pelo menos algumas palavras).'); return; }
  S.ws.pergunta = q; S.ws.asking = true; S.ws.answer = null;
  // Consulta NOVA (13/11/2026, pedido do usuario): o editor e o resultado anteriores saem na hora, para nao parecer
  // que a consulta ja esta pronta. "Ajustar a do editor" mantem a consulta (ela e o ponto de partida).
  if (!adjust) { Object.assign(S.ws, {sql: '', titulo: '', result: null, sim: null, saving: false, editId: '', origem: 'pergunta'}); saveWs(); }
  render();
  // Barra de progresso (13/11/2026, pedido do usuario): avanca rapido no comeco e devagar depois, sem passar de 95%
  // enquanto espera; chega a 100% quando a resposta chega.
  const t0 = Date.now(), pct = () => Math.min(95, Math.round(95 * (1 - Math.exp(-(Date.now() - t0) / 16000))));
  const paint = p => { const b = document.querySelector('.qc-askbar i'), l = document.querySelector('.qc-askpct');
    if (b) b.style.width = p + '%'; if (l) l.textContent = p + '%';
    const s = document.querySelector('[data-qt]'); if (s) s.textContent = `${Math.round((Date.now() - t0) / 1000)} s`; };
  const tick = setInterval(() => paint(pct()), 250);
  try {
    const a = await postJson('/api/query-console/perguntar', {pergunta: q, sql_atual: adjust ? S.ws.sql : ''});
    if (a.sql) a.sql = formatSql(a.sql);
    S.ws.answer = a; S.ws.pendente = '';
    if (a.sql && (a.alertas_tabelas || []).length) { S.ws.pendente = a.sql; S.ws.titulo = a.titulo || q.slice(0, 120); S.ws.origem = 'pergunta'; S.ws.result = null; S.ws.sim = null; S.ws.editId = ''; }
    else if (a.sql) { S.ws.sql = a.sql; S.ws.titulo = a.titulo || q.slice(0, 120); S.ws.origem = 'pergunta'; S.ws.result = null; S.ws.sim = null; S.ws.editId = ''; saveWs(); }
  } catch (e) { S.ws.answer = {sql: '', explicacao: e.message}; }
  clearInterval(tick); paint(100); await new Promise(r => setTimeout(r, 350));
  S.ws.asking = false; render();
  const a = S.ws.answer || {};
  if (a.sql && S.ws.pendente) notifyDone('Consulta montada com aviso', `${S.ws.titulo || 'Consulta'}: usa tabela vazia ou sem atualização. Veja o aviso na Query Console › Perguntar.`, 'perguntar');
  else if (a.sql) notifyDone('Consulta montada', `${S.ws.titulo || 'Consulta'}: pronta no editor da Query Console › Perguntar.`, 'perguntar');
  else notifyDone('Consulta não montada', a.explicacao || 'O NexxusDoc não conseguiu montar a consulta.', 'perguntar');
}
async function wsRun() {
  S.ws.run = {fase: 'conf'}; paintWs();
  try {
    const sql = S.ws.sql;
    const s = await postJson('/api/query-console/consulta/simular', {sql}); S.ws.sim = {sql, ...s};
    S.ws.run = {fase: 'pronto', gb: s.gb, tabs: (s.tabelas || []).map(t => `<code>${E(shortId(t))}</code>`).join(', ')};
  } catch (e) { S.ws.run = {fase: 'erro', msg: e.message}; }
  paintWs();
}
async function wsExec() {
  if (!S.ws.sim) return;
  S.ws.run = {fase: 'exec', t0: Date.now()}; paintWs();
  if (S.view === 'perguntar') { render(); document.querySelector('#page-query .qc-running')?.scrollIntoView({behavior: 'smooth', block: 'center'}); }
  const tick = setInterval(paintWs, 1000), titulo = S.ws.titulo || 'Consulta';
  try {
    const r = await postJson('/api/query-console/consulta/executar', {confirmado: true, sql: S.ws.sim.sql, titulo, origem: S.ws.origem || 'editor'});
    S.ws.result = {...r, quando: new Date().toLocaleString('pt-BR')}; S.ws.sim = null; S.ws.run = null; S.lib = null; clearInterval(tick);
    if (S.view === 'perguntar') { render(); document.querySelector('.qc-ws-wrap .qc-result')?.scrollIntoView({behavior: 'smooth', block: 'start'}); }
    notifyDone('Resultado da consulta pronto', `${titulo}: ${nf(r.total_linhas)} linha(s). Abra a Query Console › Perguntar.`, 'perguntar');
  } catch (e) {
    clearInterval(tick); S.ws.run = {fase: 'erro', msg: e.message}; if (S.view === 'perguntar') render(); else paintWs();
    notifyDone('Consulta não executada', `${titulo}: ${e.message}`, 'perguntar');
  }
}
async function saveQuery() {
  const t = (document.getElementById('qc-save-t')?.value || '').trim(), d = (document.getElementById('qc-save-d')?.value || '').trim();
  const share = Boolean(document.getElementById('qc-save-c')?.checked), replace = Boolean(document.getElementById('qc-save-r')?.checked);
  if (t.length < 3) { toast('Dê um título para a consulta.'); return; }
  const body = {titulo: t, descricao: d, sql: S.ws.sql, compartilhada: share, origem: S.ws.origem || 'editor'};
  try {
    const saved = replace && S.ws.editId ? await api(`/api/query-console/biblioteca/${encodeURIComponent(S.ws.editId)}`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})
      : await postJson('/api/query-console/biblioteca', body);
    Object.assign(S.ws, {saving: false, titulo: saved.titulo, editId: saved.id, descricao: saved.descricao, compartilhada: saved.compartilhada});
    S.lib = null; render(); toast(share ? 'Consulta salva e compartilhada com a equipe.' : 'Consulta salva em Minhas consultas.');
  } catch (e) { toast(e.message); }
}
function toWorkspace(sql, titulo, origem, extra) {
  Object.assign(S.ws, {sql, titulo: titulo || '', origem: origem || 'editor', answer: null, sim: null, result: null, saving: false, editId: '', descricao: '', compartilhada: false}, extra || {});
  saveWs(); setView('perguntar'); window.scrollTo({top: root().querySelector('.qc-nav').offsetTop - 80, behavior: 'smooth'});
}

/* ---- Catalogo do BigQuery (todas as tabelas), agrupado por projeto (13/11/2026, pedido do usuario) ---- */
// As tabelas do SAP formam um grupo proprio; o resto do dataset trusted (cargas e APIs de outros sistemas) fica em
// "Outras tabelas do Grupo SBF".
const CAT_GROUPS = [
  ['sap', 'SAP S/4HANA', 'Tabelas do SAP que chegam ao lake · example-sap-project · trusted'],
  ['example-brand-project.refined', 'Fisia / Nike Brasil', 'Pedidos Nike, recebimento no CD e vendas · example-brand-project · refined'],
  ['example-sap-project.refined', 'Visões corporativas do Grupo SBF', 'Frete, estoque e outras visões · example-sap-project · refined'],
  ['example-sap-project.trusted', 'Outras tabelas do Grupo SBF', 'Cargas e integrações de outros sistemas · example-sap-project · trusted'],
  ['example-retail-project.refined', 'Centauro', 'Vendas, clientes, produtos e logística · example-retail-project · refined']];
const CAT_STEP = 12;
const lsSet = k => { try { return new Set(JSON.parse(localStorage.getItem(k) || '[]')); } catch { return new Set(); } };
const lsSave = (k, set) => { try { localStorage.setItem(k, JSON.stringify([...set])); } catch {} };
S.cat.closed = lsSet('nexus.qc.cat.fechados'); S.cat.closedQ = new Set(); S.cat.show = {};
function catGroups(items) {
  const by = {};
  for (const t of items) { const k = t.sap ? 'sap' : t.id.split('.').slice(0, 2).join('.'); (by[k] = by[k] || []).push(t); }
  // sem busca, cada grupo em ordem alfabetica do nome curto (com busca, a ordem de relevancia do servidor)
  if (!S.cat.q.trim()) for (const k in by) by[k].sort((a, b) => shortId(a.id).localeCompare(shortId(b.id)));
  const known = CAT_GROUPS.map(g => g[0]);
  return [...CAT_GROUPS, ...Object.keys(by).filter(k => !known.includes(k)).map(k => [k, k, ''])]
    .filter(([k]) => by[k]).map(([k, nome, sub]) => ({k, nome, sub, items: by[k]}));
}
// Tabela vazia (0 linhas) ou parada (sem atualizacao ha mais de 30 dias), pela conferencia do catalogo (13/11/2026)
const brD = d => d ? d.split('-').reverse().join('/') : '';
const sitPill = s => !s ? '' : s.situacao === 'vazia'
  ? `<span class="qc-pill sit" title="0 linhas no BigQuery${s.atualizada ? '; última atualização em ' + brD(s.atualizada) : ''}">vazia</span>`
  : `<span class="qc-pill sit" title="Sem atualização desde ${brD(s.atualizada)}">parada desde ${brD(s.atualizada)}</span>`;
const sitBanner = s => !s ? '' : `<div class="qc-answer warn qc-alert">${IC.warn}<div><b>${s.situacao === 'vazia' ? 'Tabela vazia no BigQuery' : 'Tabela sem atualização'}</b><p>${s.situacao === 'vazia' ? `Não tem nenhuma linha${s.atualizada ? ` e não é atualizada desde ${brD(s.atualizada)}` : ''}: uma consulta nela volta vazia.` : `Não é atualizada desde ${brD(s.atualizada)}: os dados mais recentes não estão nela.`}</p></div></div>`;
const catRow = t => `<button type="button" class="qc-catr${S.cat.sel === t.id ? ' on' : ''}" data-qcat-sel="${E(t.id)}">
  <span class="l1"><b class="tn">${E(shortId(t.id))}</b>${t.sap ? `<span class="qc-pill prio">SAP · ${E(t.sap)}</span>` : ''}${t.nova ? '<span class="qc-pill new">nova</span>' : ''}${sitPill(t.situacao)}
    <span class="m">${t.situacao?.situacao === 'vazia' ? '0 linhas · ' : t.linhas ? `${big(t.linhas)} linhas · ` : ''}${nf(t.n_colunas || 0)} colunas${t.particao ? ` · <span class="mono">${E(t.particao)}</span>` : ''}</span></span>
  <span class="d">${E(t.desc || 'Sem descrição no BigQuery.')}</span></button>`;
function catListHtml() {
  const c = S.cat, d = c.data;
  if (!d) return '<div class="qc-loading">Carregando o catálogo…</div>';
  if (!d.itens.length) return '<div class="qc-empty">Nenhuma tabela com esse filtro. Tente outra palavra (o nome da tabela do SAP, uma coluna ou o assunto).</div>';
  const searching = Boolean(c.q.trim());
  return catGroups(d.itens).map(g => {
    const closed = (searching ? c.closedQ : c.closed).has(g.k), n = c.show[g.k] || CAT_STEP, rest = g.items.length - n;
    return `<section class="qc-catg${closed ? ' closed' : ''}"><button type="button" class="qc-catg-h" data-qcat-group="${E(g.k)}" aria-expanded="${!closed}">
        <span class="t"><b>${E(g.nome)}</b><small>${E(g.sub)}</small></span><span class="qc-pill">${nf(g.items.length)} tabela(s)</span>
        <span class="tog">${closed ? 'Expandir' : 'Recolher'}${IC.chevd}</span></button>
      ${closed ? '' : `<div class="qc-catg-l">${g.items.slice(0, n).map(catRow).join('')}
        ${rest > 0 ? `<button type="button" class="qc-btn sm qc-more" data-qcat-more="${E(g.k)}">${IC.chevd}Mostrar mais ${nf(Math.min(rest, 40))} de ${nf(rest)}</button>` : ''}</div>`}</section>`;
  }).join('');
}
function catHtml() {
  const c = S.cat, d = c.data;
  const projs = d?.projetos || [];
  return `<div class="qc-filter qc-catbar"><label class="qc-search big">${SEARCH}<input type="search" id="qc-cat-q" placeholder="Buscar tabela, coluna ou assunto (ex.: pedido, NCM, ekko, embarque, ASN)" value="${E(c.q)}" aria-label="Buscar no catálogo"></label>
      <label>Projeto<select id="qc-cat-proj" class="${c.projeto ? 'on' : ''}"><option value="">Todos</option>${projs.map(p => `<option value="${E(p.id)}"${c.projeto === p.id ? ' selected' : ''}>${E(p.id)} (${nf(p.tabelas)})</option>`).join('')}</select></label>
      <label>Tipo<select id="qc-cat-tipo" class="${c.tipo ? 'on' : ''}"><option value="">Todas</option><option value="sap"${c.tipo === 'sap' ? ' selected' : ''}>Só tabelas do SAP</option><option value="outras"${c.tipo === 'outras' ? ' selected' : ''}>Fora do SAP</option></select></label>
      <span class="grow"></span><span class="qc-count">${d ? `${nf(d.total)} tabela(s)` : 'Carregando…'}</span></div>
    <div class="qc-catgrid"><div class="qc-catlist">${catListHtml()}</div>
      <aside class="qc-catdet">${catDetailHtml()}</aside></div>`;
}
// Atualizacao semanal do catalogo (13/11/2026): toda segunda-feira pelo computador do administrador; ele tambem pode
// atualizar na hora.
function catUpdateHtml() {
  const d = S.cat.data || {}, u = d.atualizacao;
  const when = u ? new Date(u.quando).toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'}) : '';
  return `<div class="qc-catupd">${IC.clock}<span>${u ? `Tabelas conferidas no BigQuery em <b>${E(when)}</b>${u.novas ? ` · <b>${nf(u.novas)}</b> nova(s) (marcadas na lista)` : ' · nenhuma tabela nova'}${u.removidas ? ` · ${nf(u.removidas)} saíram do BigQuery` : ''}.` : 'O catálogo é conferido com o BigQuery toda segunda-feira.'}</span>
    ${d.pode_atualizar ? `<button type="button" class="qc-btn sm" data-qcat-refresh${d.atualizando || S.cat.refreshing ? ' disabled' : ''}>${IC.spark}${d.atualizando || S.cat.refreshing ? 'Conferindo…' : 'Atualizar agora'}</button>` : ''}</div>`;
}
function catDetailHtml() {
  const t = S.cat.table;
  if (!t) {
    const groups = S.cat.data ? catGroups(S.cat.data.itens) : [];
    return `<div class="qc-catintro"><span class="qc-tbl-ico">${IC.db}</span><h3>Catálogo do BigQuery</h3>
      <p>As tabelas estão agrupadas por projeto. Clique numa tabela para ver as colunas, em que procedimento da área e em quais transações SAP ela aparece e montar uma consulta.</p>
      ${groups.length ? `<ul>${groups.map(g => `<li><b>${E(g.nome)}</b><span>${nf(g.items.length)} tabela(s)</span></li>`).join('')}</ul>` : ''}
      <small>${IC.info}Busque pelo nome da tabela do SAP (ex.: ekko, j_1bnfdoc), por uma coluna ou pelo assunto (pedido, NCM, embarque).</small>
      ${catUpdateHtml()}</div>`;
  }
  const [proj, ds, name] = t.id.split('.');
  return `<div class="qc-tbl"><div class="qc-tbl-top"><span class="qc-tbl-ico">${IC.table}</span><div><h3 class="tn">${E(shortId(t.id))}</h3><p>${E(t.desc || 'Sem descrição no BigQuery.')}</p></div></div>
    <div class="qc-path"><code class="mono">${E(proj)}.${E(ds)}.<b>${E(name)}</b></code><button type="button" data-qcopy="${E(t.id)}">${IC.copy}Copiar</button></div>
    ${sitBanner(t.situacao)}
    <div class="qc-meta">${t.sap ? `<span>${IC.layers}SAP · <b>${E(t.sap)}</b></span>` : `<span>${IC.layers}${E(proj)}</span>`}${t.situacao?.situacao === 'vazia' ? `<span>${IC.rows}<b>0</b>&nbsp;linhas</span>` : t.linhas ? `<span>${IC.rows}<b>${big(t.linhas)}</b>&nbsp;linhas</span>` : ''}
      <span>${IC.cols}<b>${nf(t.n_colunas || 0)}</b>&nbsp;colunas</span>${t.particao ? `<span>${IC.part}Partição: <b class="mono">${E(t.particao)}</b></span>` : ''}</div>
    ${(t.procedimentos || []).length || (t.transacoes || []).length ? `<div class="qc-use">${IC.target}<div><b>Na área:</b> ${(t.procedimentos || []).map(p => `<button type="button" class="qc-link" data-qproc-go="${E(p.id)}">${E(p.titulo)}</button>`).join(', ')}${(t.procedimentos || []).length && (t.transacoes || []).length ? ' · ' : ''}${(t.transacoes || []).length ? `transações ${t.transacoes.map(x => `<code>${E(x)}</code>`).join(' ')}` : ''}</div></div>` : ''}
    ${S.data.pode_gerar ? `<div class="qc-cat-actions"><button type="button" class="qc-btn primary" data-qcat-new>${IC.code}Nova consulta com esta tabela</button></div>` : ''}
    ${catColsHtml(t)}</div>`;
}
// Todas as colunas da tabela (13/11/2026, pedido do usuario): as de negocio primeiro, as tecnicas do lake no fim e
// marcadas; busca por nome ou descricao (so a lista e redesenhada).
function catColsHtml(t) {
  const all = (t.colunas_todas || []).length ? t.colunas_todas : (t.colunas || []).map(c => [...c, 0]);
  const tech = all.filter(c => c[3]).length;
  return `<div class="qc-h"><h4>Colunas (${nf(all.length)})</h4><small>${tech ? `${nf(all.length - tech)} de negócio e ${nf(tech)} técnicas do lake (no fim)` : 'todas de negócio'}</small>
      <label class="qc-search sm">${SEARCH}<input type="search" id="qc-cat-colq" placeholder="Buscar coluna" value="${E(S.cat.colq || '')}" aria-label="Buscar coluna"></label></div>
    <div class="qc-cols scroll" id="qc-cat-cols">${catColsRows(all)}</div>`;
}
function catColsRows(all) {
  const q = (S.cat.colq || '').trim().toLowerCase();
  const rows = [...all.filter(c => !c[3]), ...all.filter(c => c[3])].filter(c => !q || c[0].toLowerCase().includes(q) || String(c[2] || '').toLowerCase().includes(q));
  if (!rows.length) return '<div class="qc-empty" style="margin:10px">Nenhuma coluna com esse nome.</div>';
  return `<table><thead><tr><th>Coluna</th><th>Tipo</th><th>O que é</th></tr></thead><tbody>${rows.map(([n, ty, d, tec]) =>
    `<tr${tec ? ' class="tech"' : ''}><td class="c">${E(n)}</td><td><span class="qc-type">${E(ty)}</span></td><td>${E(d)}${tec ? ' <span class="qc-pill">técnica do lake</span>' : ''}</td></tr>`).join('')}</tbody></table>`;
}
let catTimer = 0, catReq = 0;
// So vale a resposta do pedido mais recente (filtro trocado durante o carregamento nao volta com o resultado antigo).
async function loadCat() {
  const c = S.cat, my = ++catReq; c.loading = true;
  try {
    const qs = new URLSearchParams({q: c.q, projeto: c.projeto, tipo: c.tipo, todos: '1'});
    const d = await api('/api/query-console/catalogo?' + qs);
    if (my !== catReq) return;
    c.data = d;
  } catch (e) { if (my !== catReq) return; c.data = {total: 0, por_pagina: 30, itens: [], projetos: []}; toast(e.message); }
  c.loading = false; if (S.view === 'catalogo') render();
}
async function openTable(id, go) {
  S.cat.sel = id; S.cat.colq = '';
  try { S.cat.table = await api('/api/query-console/tabela?id=' + encodeURIComponent(id)); } catch (e) { toast(e.message); return; }
  if (go) { S.cat.q = shortId(id); S.cat.pagina = 1; S.cat.data = null; S.view = 'catalogo'; try { localStorage.setItem('nexus.qc.aba', 'catalogo'); } catch {} }
  const keep = !go && root().querySelector('.qc-catlist')?.scrollTop;
  render();
  if (go) window.scrollTo({top: root().querySelector('.qc-nav').offsetTop - 80, behavior: 'smooth'});
  else if (keep) { const l = root().querySelector('.qc-catlist'); if (l) l.scrollTop = keep; }
}
function tableTemplate(t) {
  const cols = (t.colunas || []).slice(0, 12).map(c => c[0]);
  const part = t.particao, partType = ((t.colunas || []).find(c => c[0] === part) || [])[1] || '';
  const where = !part ? '' : part === 'kafka_arrival_timestamp' || /TIMESTAMP/.test(partType)
    ? `\nWHERE ${part} >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)`
    : /^DATE$/.test(partType) ? `\nWHERE ${part} >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)`
    : `\nWHERE CAST(${part} AS DATE) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)`;
  return `SELECT\n  ${(cols.length ? cols : ['*']).join(',\n  ')}\nFROM \`${t.id}\`${where}\nLIMIT 100`;
}

/* ---- Processos da area x tabelas ---- */
async function loadPr() {
  try { S.pr.data = await api('/api/query-console/processos'); } catch (e) { S.pr.data = {processos: [], total: 0, com_tabelas: 0}; toast(e.message); }
  if (S.view === 'processos') render();
}
function prFiltered() {
  const q = S.pr.q.trim().toLowerCase();
  return (S.pr.data?.processos || []).filter(p => (!S.pr.unid || (p.unidades || []).includes(S.pr.unid))
    && (!S.pr.so || (S.pr.so === 'com' ? p.tabelas.length : !p.tabelas.length))
    && (!q || [p.nome, ...(p.transacoes || []), ...p.tabelas.map(t => t.curta)].join(' ').toLowerCase().includes(q)));
}
// Agrupados pela fase macro do processo (13/11/2026, pedido do usuario): as mesmas fases do universo do REF. DOCS.
S.pr.closed = lsSet('nexus.qc.pr.fechadas'); S.pr.closedQ = new Set();
function prCardsHtml() {
  const list = prFiltered();
  if (!S.pr.data) return '<div class="qc-loading">Carregando os processos…</div>';
  if (!list.length) return '<div class="qc-empty">Nenhum processo com esse filtro.</div>';
  const fases = S.pr.data.fases || [], searching = Boolean(S.pr.q.trim());
  return fases.map((f, i) => {
    const ps = list.filter(p => p.fase === f.id); if (!ps.length) return '';
    const closed = (searching ? S.pr.closedQ : S.pr.closed).has(f.id), com = ps.filter(p => p.tabelas.length).length;
    return `<section class="qc-group qc-prg${closed ? ' closed' : ''}" style="--fc:${E(f.cor)}"><button type="button" class="qc-group-h" data-qpr-group="${E(f.id)}" aria-expanded="${!closed}">
        <span class="k">${String(i + 1).padStart(2, '0')}</span><i class="dot"></i><h3>${E(f.nome)}</h3><small>${ps.length} processo(s) · ${com} com tabelas</small>
        <span class="tog">${closed ? 'Expandir' : 'Recolher'}${IC.chevd}</span></button>
      ${closed ? '' : prGridHtml(ps)}</section>`;
  }).join('');
}
function prGridHtml(list) {
  return `<div class="qc-prgrid">${list.map(p => `<article class="qc-pr${p.tabelas.length ? '' : ' none'}">
      <div class="top"><span class="qc-pill ${p.origem.includes('NexxusDoc') ? 'ok' : 'fase'}">${E(p.origem)}</span>${(p.unidades || []).map(u => `<span class="qc-pill unit">${E(u)}</span>`).join('')}</div>
      <h4>${E(p.nome)}</h4>
      ${(p.transacoes || []).length || (p.outras_transacoes || []).length ? `<div class="qc-pr-l"><small>Transações SAP</small><div>${[...(p.transacoes || []), ...(p.outras_transacoes || [])].map(x => `<code>${E(x)}</code>`).join(' ')}</div></div>` : ''}
      ${p.tabelas.length ? `<div class="qc-pr-l"><small>Tabelas no BigQuery</small><div>${p.tabelas.map(t => `<button type="button" class="qc-tt" data-qcat-open="${E(t.id)}" title="${E(t.motivo)}">${E(t.curta)}</button>`).join('')}</div></div>`
        : `<div class="qc-pr-l"><small>Tabelas no BigQuery</small><div class="qc-pr-none">Nenhuma tabela ligada${(p.fora_do_lake || []).length ? '' : ': pergunte na aba Perguntar'}</div></div>`}
      ${(p.procedimentos || []).length ? `<div class="qc-pr-l"><small>Consulta pronta</small><div>${p.procedimentos.map(x => `<button type="button" class="qc-link" data-qproc-go="${E(x.id)}">${E(x.titulo)}</button>`).join(', ')}</div></div>` : ''}
      ${(p.fora_do_lake || []).length ? `<div class="qc-pr-out">${IC.info}<span>Também depende de dados fora do BigQuery: ${E(p.fora_do_lake.join(', '))}</span></div>` : ''}
    </article>`).join('')}</div>`;
}
function prHtml() {
  const d = S.pr.data, units = [...new Set((d?.processos || []).flatMap(p => p.unidades || []))].sort();
  return `<div class="qc-filter qc-prbar"><label class="qc-search big">${SEARCH}<input type="search" id="qc-pr-q" placeholder="Buscar processo, transação ou tabela" value="${E(S.pr.q)}" aria-label="Buscar processo"></label>
      <label>Unidade<select id="qc-pr-unid" class="${S.pr.unid ? 'on' : ''}"><option value="">Todas</option>${units.map(u => `<option${S.pr.unid === u ? ' selected' : ''}>${E(u)}</option>`).join('')}</select></label>
      <label>Mostrar<select id="qc-pr-so" class="${S.pr.so ? 'on' : ''}"><option value="">Todos os processos</option><option value="com"${S.pr.so === 'com' ? ' selected' : ''}>Com tabelas no BigQuery</option><option value="sem"${S.pr.so === 'sem' ? ' selected' : ''}>Sem tabelas no BigQuery</option></select></label>
      <span class="grow"></span><span class="qc-count">${d ? `${nf(d.com_tabelas)} de ${nf(d.total)} processos com tabelas` : ''}</span></div>
    ${d?.observacao ? `<div class="qc-note qc-pr-note">${IC.info}${E(d.observacao)}</div>` : ''}
    <div id="qc-pr-list">${prCardsHtml()}</div>`;
}

/* ---- Minhas consultas: prontas, salvas, compartilhadas, favoritas e historico ---- */
S.libClosed = lsSet('nexus.qc.lib.fechadas');
async function loadLib() {
  try { S.lib = await api('/api/query-console/biblioteca'); } catch (e) { S.lib = {prontas: [], minhas: [], compartilhadas: [], historico: [], favoritos: []}; toast(e.message); }
  if (S.view === 'biblioteca') render();
}
const isFav = id => (S.lib?.favoritos || []).includes(id);
function libItem(q, kind) {
  const fav = isFav(q.favId), pode = S.data.pode_gerar;
  const when = q.atualizado_em || q.quando ? new Date(q.atualizado_em || q.quando).toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'}) : '';
  const meta = kind === 'hist' ? `${when} · ${nf(q.linhas || 0)} linha(s)` : kind === 'proc' ? `${E(fase(q.fase).nome)} · consulta do procedimento`
    : kind === 'pronta' ? `${E(fase(q.fase).nome)} · consulta pronta` : `${kind === 'minha' ? (q.compartilhada ? 'compartilhada com a equipe' : 'só você vê') : 'de ' + E(q.autor_nome || q.autor)} · ${when}`;
  return `<div class="qc-libi"><div class="t"><b>${E(q.titulo)}</b><small>${meta}</small>${q.descricao || q.serve ? `<p>${E(q.descricao || q.serve)}</p>` : ''}</div>
    <div class="a">${kind !== 'hist' ? `<button type="button" class="qc-star${fav ? ' on' : ''}" data-qfav="${E(q.favId)}" title="${fav ? 'Tirar das favoritas' : 'Marcar como favorita'}" aria-pressed="${fav}">${I('<path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>')}</button>` : ''}
      ${kind === 'proc' ? `<button type="button" class="qc-btn sm" data-qproc-go="${E(q.id)}">Ver procedimento</button>` : ''}
      <button type="button" class="qc-btn sm${pode ? ' primary' : ''}" data-qlib-open="${E(kind + ':' + q.id)}">${IC.code}${pode ? 'Abrir no editor' : 'Ver SQL'}</button>
      ${kind === 'minha' ? `<button type="button" class="qc-btn sm" data-qlib-share="${E(q.id)}">${q.compartilhada ? 'Deixar só comigo' : 'Compartilhar'}</button><button type="button" class="qc-btn sm" data-qlib-del="${E(q.id)}">Excluir</button>` : ''}
      ${kind === 'comp' && S.lib.master ? `<button type="button" class="qc-btn sm" data-qlib-del="${E(q.id)}">Excluir</button>` : ''}</div></div>`;
}
function libHtml() {
  const L = S.lib; if (!L) return '<div class="qc-loading">Carregando as consultas…</div>';
  const pronta = (L.prontas || []).map(q => ({...q, favId: q.id})), proc = procs().map(p => ({...p, favId: 'proc:' + p.id}));
  const minhas = (L.minhas || []).map(q => ({...q, favId: q.id})), comp = (L.compartilhadas || []).map(q => ({...q, favId: q.id}));
  // Consultas da equipe (13/11/2026, pedido do usuario): TODAS as compartilhadas, as das outras pessoas e as suas, da mais nova
  // para a mais antiga. As suas continuam tambem em Minhas consultas (ali se compartilha e se exclui).
  const when = q => String(q.atualizado_em || q.criado_em || '');
  const team = [...minhas.filter(q => q.compartilhada).map(q => [q, 'minha']), ...comp.map(q => [q, 'comp'])].sort((a, b) => when(b[0]).localeCompare(when(a[0])));
  const favs = [...pronta.map(q => [q, 'pronta']), ...proc.map(q => [q, 'proc']), ...minhas.map(q => [q, 'minha']), ...comp.map(q => [q, 'comp'])].filter(([q]) => isFav(q.favId));
  // secoes recolhiveis (13/11/2026, pedido do usuario); a escolha fica guardada no navegador
  const sec = (key, title, sub, inner, n) => { const closed = S.libClosed.has(key);
    return `<section class="qc-box qc-lib${closed ? ' closed' : ''}"><button type="button" class="qc-lib-h" data-qlib-toggle="${key}" aria-expanded="${!closed}"><h3>${title}${n != null ? ` <span class="n">${n}</span>` : ''}</h3><span class="tog">${closed ? 'Expandir' : 'Recolher'}${IC.chevd}</span></button>${closed ? '' : `${sub ? `<p>${sub}</p>` : ''}<div class="qc-libl">${inner}</div>`}</section>`; };
  return `${favs.length ? sec('fav', `${I('<path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>')}Favoritas`, '', favs.map(([q, k]) => libItem(q, k)).join(''), favs.length) : ''}
    ${sec('minhas', `${IC.doc}Minhas consultas`, L.pode_salvar ? 'As que você salvou no editor da aba Perguntar. Só você vê, a não ser que compartilhe.' : '', minhas.length ? minhas.map(q => libItem(q, 'minha')).join('') : `<div class="qc-empty">${L.pode_salvar ? 'Nenhuma consulta salva ainda. Monte ou ajuste uma consulta na aba Perguntar e clique em Salvar.' : 'Salvar consultas é para quem o administrador liberou.'}</div>`, minhas.length)}
    ${sec('equipe', `${IC.link}Consultas da equipe`, 'Todas as consultas que as pessoas compartilharam, inclusive as suas. Para compartilhar uma sua, use o botão Compartilhar em Minhas consultas.',
      team.length ? team.map(([q, k]) => libItem(q, k)).join('') : '<div class="qc-empty">Nenhuma consulta compartilhada ainda.</div>', team.length)}
    ${sec('prontas', `${IC.check}Consultas prontas da área`, 'Prontas para usar; confira o período antes de gerar.', pronta.map(q => libItem(q, 'pronta')).join('') || '<div class="qc-empty">Nenhuma consulta pronta nesta versão.</div>', pronta.length)}
    ${sec('procs', `${IC.layers}Consultas dos procedimentos`, 'A consulta de cada procedimento da aba Procedimentos.', proc.map(q => libItem(q, 'proc')).join(''), proc.length)}
    ${L.pode_salvar ? sec('hist', `${IC.clock}Histórico`, 'Suas últimas execuções (até 60).', (L.historico || []).length ? (L.historico || []).map(q => libItem(q, 'hist')).join('') + `<div class="qc-lib-foot"><button type="button" class="qc-btn sm" data-qhist-clear>Limpar histórico</button></div>` : '<div class="qc-empty">Nenhuma consulta executada ainda.</div>', (L.historico || []).length) : ''}`;
}
function libFind(key) {
  const [kind, id] = [key.slice(0, key.indexOf(':')), key.slice(key.indexOf(':') + 1)], L = S.lib || {};
  const list = kind === 'pronta' ? L.prontas : kind === 'minha' ? L.minhas : kind === 'comp' ? L.compartilhadas : kind === 'hist' ? L.historico : procs();
  return [kind, (list || []).find(q => q.id === id)];
}

/* ---------------- tela ---------------- */
function render() {
  const r = root(); if (!r || !S.data) return;
  if (!VIEWS.some(v => v[0] === S.view)) S.view = 'proc';
  const p = S.view === 'proc' && S.sel && proc(S.sel);
  const hero = headHtml(), cut = hero.indexOf('<div class="qc-stats">');
  const body = navHtml() + (S.view === 'proc' ? hero.slice(cut) + journeyHtml() + filterHtml() + (p ? detailHtml(p) : overviewHtml())
    : S.view === 'perguntar' ? wsHtml() : S.view === 'catalogo' ? catHtml() : S.view === 'processos' ? prHtml() : libHtml());
  // o campo em que a pessoa esta digitando continua com o foco e o cursor depois de redesenhar
  const act = document.activeElement, fid = act && act.id && r.contains(act) ? act.id : '';
  const caret = fid && 'selectionStart' in act ? [act.selectionStart, act.selectionEnd] : null;
  r.innerHTML = `<div class="qc${S.editing && p ? ' qc-editing' : ''}">${hero.slice(0, cut)}${body}</div>`;
  if (fid) { const el = document.getElementById(fid); if (el) { el.focus({preventScroll: true}); if (caret) try { el.setSelectionRange(...caret); } catch {} } }
  if (S.view === 'catalogo' && !S.cat.data && !S.cat.loading) loadCat();
  if (S.view === 'processos' && !S.pr.data) loadPr();
  if (S.view === 'biblioteca' && !S.lib) loadLib();
}
document.addEventListener('change', e => {
  if (!e.target.closest('#page-query')) return;
  if (e.target.id === 'qc-proc') { S.sel = e.target.value; render(); window.scrollTo({top: root().querySelector('.qc-filter').offsetTop - 80, behavior: 'smooth'}); }
  if (e.target.id === 'qc-fase') { S.fase = e.target.value; if (S.sel && proc(S.sel)?.fase !== S.fase && S.fase) S.sel = ''; render(); }
  if (e.target.id === 'qc-sit') { S.sit = e.target.value; S.sel = ''; render(); }
});
document.addEventListener('click', e => {
  const r = root(); if (!r || !e.target.closest('#page-query')) return;
  if (S.editing && e.target.closest('[data-qcol]')) { insertColumn(e.target.closest('[data-qcol]').dataset.qcol); return; }
  const b = e.target.closest('[data-qproc],[data-qfase],[data-qreset],[data-qtab],[data-qcopy],[data-qcopy-sql],[data-qrun],[data-qcols],[data-qgroup],[data-qtoggle-all],[data-qexec],[data-qcancel],[data-qcsv],[data-qclose],[data-qedit],[data-qrestore]'); if (!b) return;
  if (b.hasAttribute('data-qedit')) { S.editing = !S.editing; render(); document.querySelector('.qc-sql')?.scrollIntoView({behavior: 'smooth', block: 'center'}); return; }
  if (b.hasAttribute('data-qrestore')) { const p = proc(S.sel); setEdit(p, p.sql); render(); toast('Consulta original restaurada.'); return; }
  if (b.hasAttribute('data-qexec')) { execFlow(proc(S.sel)); return; }
  if (b.hasAttribute('data-qcancel')) { S.sim = null; delete S.procRun[S.sel]; paintRun('qc-run', null, PROC_ATTRS); return; }
  if (b.hasAttribute('data-qcsv')) { downloadCsv(proc(S.sel)); return; }
  if (b.hasAttribute('data-qclose')) { delete S.result[S.sel]; render(); return; }
  if (b.dataset.qcols) { S.cols = b.dataset.qcols; render(); return; }
  if (b.dataset.qgroup) {   // recolhe ou expande so a fase clicada, sem redesenhar a pagina
    const id = b.dataset.qgroup, sec = b.closest('.qc-group'), closed = !S.closed.has(id);
    closed ? S.closed.add(id) : S.closed.delete(id); saveClosed();
    sec.classList.toggle('closed', closed); b.setAttribute('aria-expanded', !closed);
    b.querySelector('.tog').innerHTML = (closed ? 'Expandir' : 'Recolher') + IC.chevd;
    return;
  }
  if (b.dataset.qtoggleAll) {
    if (b.dataset.qtoggleAll === 'fechar') S.data.fases.forEach(f => S.closed.add(f.id)); else S.closed.clear();
    saveClosed(); render(); return;
  }
  if (b.dataset.qproc) { S.sel = b.dataset.qproc; render(); window.scrollTo({top: r.querySelector('.qc-filter').offsetTop - 80, behavior: 'smooth'}); }
  else if (b.dataset.qfase !== undefined) { S.fase = b.dataset.qfase; S.sel = ''; render(); }
  else if (b.hasAttribute('data-qreset')) { S.sel = ''; S.fase = ''; S.sit = ''; render(); }
  else if (b.dataset.qtab) { S.tab[S.sel] = b.dataset.qtab; render(); }
  else if (b.dataset.qcopy) { navigator.clipboard?.writeText(b.dataset.qcopy).then(() => toast('Caminho da tabela copiado.')); }
  else if (b.hasAttribute('data-qcopy-sql')) { navigator.clipboard?.writeText(curSql(proc(S.sel))).then(() => toast('Consulta copiada.')); }
  else if (b.hasAttribute('data-qrun')) { runFlow(proc(S.sel)); }
});
// Busca de coluna: refaz só a grade (o campo mantém o foco).
document.addEventListener('input', e => {
  if (e.target.id === 'qc-sql-edit') { setEdit(proc(S.sel), e.target.value); return; }
  if (e.target.id !== 'qc-busca') return;
  S.busca = e.target.value;
  const p = proc(S.sel), use = p && (p.tabelas.find(t => t.id === (S.tab[p.id] || p.tabelas[0].id)) || p.tabelas[0]);
  if (use) document.getElementById('qc-gwrap').innerHTML = gridHtml(S.data.tabelas[use.id], new Set(use.colunas));
});
/* ---------------- abas novas: cliques e campos (12/11/2026) ---------------- */
document.addEventListener('click', async e => {
  if (!e.target.closest('#page-query')) return;
  const b = e.target.closest('[data-qview],[data-qto-ws],[data-qxlsx],[data-qask],[data-qask-adjust],[data-qex],[data-qws-run],[data-qws-exec],[data-qws-cancel],[data-qws-copy],[data-qws-clear],[data-qws-save],[data-qsave-ok],[data-qsave-cancel],[data-qws-xlsx],[data-qws-csv],[data-qws-rclose],[data-qcat-sel],[data-qcat-open],[data-qcat-page],[data-qcat-new],[data-qproc-go],[data-qfav],[data-qlib-open],[data-qlib-share],[data-qlib-del],[data-qhist-clear],[data-qcat-group],[data-qcat-more],[data-qpr-group],[data-qlib-toggle],[data-qalert-ok]');
  if (!b || b.disabled) return;
  const d = b.dataset;
  if (d.qview) { setView(d.qview); return; }
  if (b.hasAttribute('data-qalert-ok')) { S.ws.sql = S.ws.pendente || S.ws.sql; S.ws.pendente = ''; saveWs(); render(); return; }
  // grupos recolhiveis do Catalogo, de Processos x tabelas e de Minhas consultas (13/11/2026)
  const toggle = (set, key, store) => { set.has(key) ? set.delete(key) : set.add(key); lsSave(store, set); render(); };
  // durante a busca os grupos tambem recolhem (escolha so desta busca; a proxima busca abre tudo de novo)
  if (d.qcatGroup) { if (S.cat.q.trim()) { const s = S.cat.closedQ; s.has(d.qcatGroup) ? s.delete(d.qcatGroup) : s.add(d.qcatGroup); render(); } else toggle(S.cat.closed, d.qcatGroup, 'nexus.qc.cat.fechados'); return; }
  if (d.qcatMore) { S.cat.show[d.qcatMore] = (S.cat.show[d.qcatMore] || CAT_STEP) + 40; render(); return; }
  if (b.hasAttribute('data-qcat-refresh')) {
    S.cat.refreshing = true; render(); toast('Conferindo as tabelas no BigQuery (só metadados)…');
    try { const r = await postJson('/api/query-console/catalogo/atualizar', {});
      toast(r.feito ? `Catálogo conferido: ${r.novas} tabela(s) nova(s), ${r.removidas} removida(s).` : (r.motivo || 'Não foi possível atualizar agora.'));
    } catch (err) { toast(err.message); }
    S.cat.refreshing = false; S.cat.data = null; render(); return;
  }
  if (d.qprGroup) { if (S.pr.q.trim()) { const s = S.pr.closedQ; s.has(d.qprGroup) ? s.delete(d.qprGroup) : s.add(d.qprGroup); const box = document.getElementById('qc-pr-list'); if (box) box.innerHTML = prCardsHtml(); } else toggle(S.pr.closed, d.qprGroup, 'nexus.qc.pr.fechadas'); return; }
  if (d.qlibToggle) { toggle(S.libClosed, d.qlibToggle, 'nexus.qc.lib.fechadas'); return; }
  if (b.hasAttribute('data-qto-ws')) { const p = proc(S.sel); toWorkspace(curSql(p), p.titulo, 'editor'); return; }
  if (b.hasAttribute('data-qxlsx')) { const p = proc(S.sel), r = S.result[S.sel]; if (r) download('/api/query-console/excel', {titulo: p.titulo, colunas: r.colunas, linhas: r.linhas, sql: curSql(p)}, xlsxName(p.titulo)); return; }
  if (b.hasAttribute('data-qask')) { ask(false); return; }
  if (b.hasAttribute('data-qask-adjust')) { ask(true); return; }
  if (d.qex) { const ta = document.getElementById('qc-ask-q'); if (ta) { ta.value = d.qex; S.ws.pergunta = d.qex; ta.focus(); } return; }
  if (b.hasAttribute('data-qws-run')) { wsRun(); return; }
  if (b.hasAttribute('data-qws-exec')) { wsExec(); return; }
  if (b.hasAttribute('data-qws-cancel')) { S.ws.sim = null; S.ws.run = null; paintRun('qc-ws-run', null, WS_ATTRS); return; }
  if (b.hasAttribute('data-qws-copy')) { navigator.clipboard?.writeText(S.ws.sql).then(() => toast('Consulta copiada.')); return; }
  if (b.hasAttribute('data-qws-clear')) { Object.assign(S.ws, {sql: '', titulo: '', answer: null, sim: null, result: null, saving: false, editId: ''}); saveWs(); render(); return; }
  if (b.hasAttribute('data-qws-save')) { if (!S.lib) await loadLib(); S.ws.saving = true; render(); document.getElementById('qc-save-t')?.focus(); return; }
  if (b.hasAttribute('data-qsave-cancel')) { S.ws.saving = false; render(); return; }
  if (b.hasAttribute('data-qsave-ok')) { saveQuery(); return; }
  if (b.hasAttribute('data-qws-xlsx')) { const r = S.ws.result; if (r) download('/api/query-console/excel', {titulo: S.ws.titulo || 'Consulta', colunas: r.colunas, linhas: r.linhas, sql: S.ws.sql}, xlsxName(S.ws.titulo)); return; }
  if (b.hasAttribute('data-qws-csv')) { if (S.ws.result) csvOf(S.ws.result, `query_console_${new Date().toISOString().slice(0, 10)}.csv`); return; }
  if (b.hasAttribute('data-qws-rclose')) { S.ws.result = null; render(); return; }
  if (d.qcatSel) { openTable(d.qcatSel, false); return; }
  if (d.qcatOpen) { openTable(d.qcatOpen, true); return; }
  if (d.qcatPage) { S.cat.pagina = Math.max(1, Number(d.qcatPage)); S.cat.data = null; render(); return; }
  if (b.hasAttribute('data-qcat-new')) { const t = S.cat.table; if (t) toWorkspace(tableTemplate(t), shortId(t.id), 'catalogo'); return; }
  if (d.qprocGo) { S.sel = d.qprocGo; S.fase = ''; S.sit = ''; setView('proc'); window.scrollTo({top: root().querySelector('.qc-filter')?.offsetTop - 80 || 0, behavior: 'smooth'}); return; }
  if (d.qfav) {
    const on = !isFav(d.qfav);
    try { const r = await postJson('/api/query-console/favoritos', {id: d.qfav, favorito: on}); S.lib.favoritos = r.favoritos; render(); } catch (err) { toast(err.message); }
    return;
  }
  if (d.qlibOpen) {
    const [kind, q] = libFind(d.qlibOpen); if (!q) return;
    const sql = kind === 'proc' ? curSql(q) : q.sql;
    toWorkspace(sql, q.titulo, kind === 'hist' ? 'historico' : 'biblioteca',
      kind === 'minha' ? {editId: q.id, descricao: q.descricao || '', compartilhada: Boolean(q.compartilhada)} : {});
    return;
  }
  if (d.qlibShare) {
    const q = (S.lib.minhas || []).find(x => x.id === d.qlibShare); if (!q) return;
    try { await api(`/api/query-console/biblioteca/${encodeURIComponent(q.id)}`, {method: 'PUT', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({titulo: q.titulo, descricao: q.descricao || '', sql: q.sql, compartilhada: !q.compartilhada, origem: q.origem || 'editor'})});
      toast(q.compartilhada ? 'Agora só você vê esta consulta.' : 'Consulta compartilhada com a equipe.'); S.lib = null; loadLib(); } catch (err) { toast(err.message); }
    return;
  }
  if (d.qlibDel) {
    if (!confirm('Excluir esta consulta salva? Esta ação não pode ser desfeita.')) return;
    try { await api(`/api/query-console/biblioteca/${encodeURIComponent(d.qlibDel)}`, {method: 'DELETE'}); toast('Consulta excluída.'); S.lib = null; loadLib(); } catch (err) { toast(err.message); }
    return;
  }
  if (b.hasAttribute('data-qhist-clear')) {
    if (!confirm('Limpar o histórico das suas consultas?')) return;
    try { await api('/api/query-console/historico', {method: 'DELETE'}); S.lib = null; loadLib(); } catch (err) { toast(err.message); }
  }
});
document.addEventListener('change', e => {
  if (!e.target.closest('#page-query')) return;
  const id = e.target.id;
  if (id === 'qc-cat-proj' || id === 'qc-cat-tipo') { S.cat[id === 'qc-cat-proj' ? 'projeto' : 'tipo'] = e.target.value; S.cat.pagina = 1; S.cat.data = null; render(); loadCat(); }
  if (id === 'qc-pr-unid' || id === 'qc-pr-so') { S.pr[id === 'qc-pr-unid' ? 'unid' : 'so'] = e.target.value; render(); }
});
document.addEventListener('input', e => {
  if (!e.target.closest?.('#page-query')) return;
  const id = e.target.id;
  if (id === 'qc-ws-sql') { S.ws.sql = e.target.value; S.ws.sim = null; if (S.ws.run?.fase !== 'exec') S.ws.run = null; saveWs(); const box = document.getElementById('qc-ws-run'); if (box) { box.classList.remove('on'); box.innerHTML = ''; }
    const has = Boolean(S.ws.sql.trim()); document.querySelectorAll('[data-qws-run],[data-qws-save],[data-qws-copy],[data-qws-clear]').forEach(x => { x.disabled = !has; }); }
  if (id === 'qc-ws-title') S.ws.titulo = e.target.value;
  if (id === 'qc-ask-q') S.ws.pergunta = e.target.value;
  if (id === 'qc-cat-colq') { S.cat.colq = e.target.value; const box = document.getElementById('qc-cat-cols'), t = S.cat.table;
    if (box && t) box.innerHTML = catColsRows((t.colunas_todas || []).length ? t.colunas_todas : (t.colunas || []).map(c => [...c, 0])); return; }
  if (id === 'qc-cat-q') { S.cat.q = e.target.value; S.cat.closedQ = new Set(); clearTimeout(catTimer); catTimer = setTimeout(() => { S.cat.pagina = 1; loadCat(); }, 350); }
  if (id === 'qc-pr-q') { S.pr.q = e.target.value; S.pr.closedQ = new Set(); const box = document.getElementById('qc-pr-list'); if (box) box.innerHTML = prCardsHtml(); }
});
// Enter na pergunta monta a consulta (Shift+Enter quebra a linha)
document.addEventListener('keydown', e => {
  if (e.target.id === 'qc-ask-q' && e.key === 'Enter' && !e.shiftKey && !S.ws.asking) { e.preventDefault(); ask(false); }
});
window.nexusQuery = {open, preload: async () => { if (!S.data) S.data = await api('/api/query-console'); }, reset: () => { S.data = null; S.lib = null; S.pr.data = null; S.cat.data = null; }, view: setView, _estado: () => S};
})();
