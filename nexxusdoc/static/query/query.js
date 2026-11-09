/* Query Console (06/11/2026, pedido do usuario): tabelas do BigQuery que automatizam cada procedimento da area, pela
   ordem da importacao. Todos veem o catalogo; so o master gera consultas. Ambiente claro, so nesta pagina.
   Dados: /api/query-console (catalogo curado query_console.json + documentos do sistema ligados na hora). */
(() => {
'use strict';
const S = {data: null, sel: '', fase: '', sit: '', tab: {}, busy: false, cols: 'todas', busca: '', sim: null, result: {}, editing: false, edits: {},
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
const shortT = id => { const t = S.data.tabelas[id]; return t ? t.caminho.split('.').pop().replace(/^sap_/, '').replace(/^finance_(fat|flt)_/, '').toUpperCase() : id; };
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
  const steps = [{id: '', nome: 'Todas as fases'}, ...d.fases].map((f, i) => {
    const ps = f.id ? all.filter(p => p.fase === f.id) : all, nt = new Set(ps.flatMap(p => p.tabelas.map(t => t.id))).size;
    return `<button type="button" class="qc-step${S.fase === f.id ? ' on' : ''}${f.id ? '' : ' all'}" data-qfase="${E(f.id)}"${f.cor ? ` style="--fc:${E(f.cor)}"` : ''}><span class="k">${i ? String(i).padStart(2, '0') : 'TODAS'}</span>
      <span class="t">${E(f.nome)}</span><span class="m"><span><b>${ps.length}</b> proc.</span><span><b>${nt}</b> tabelas</span></span></button>`;
  }).join('');
  return `<section class="qc-hero"><div class="qc-hero-txt">
      <span class="qc-eyebrow">${IC.db}BIGQUERY · LOGÍSTICA INTERNACIONAL</span>
      <h1><span>Query Console</span></h1>
      <p>Tabelas do BigQuery que podem automatizar cada procedimento da área.</p>
      <div class="qc-chips"><span>${IC.clock}Levantamento de <b>${E(d.levantamento)}</b></span><span>${IC.db}Cobrança em <b>${E(d.projeto_cobranca)}</b></span>
        <span class="qc-access${d.pode_gerar ? ' on' : ''}">${d.pode_gerar ? IC.play + 'Você gera consultas (master)' : IC.lock + 'Leitura para todos · só o master gera consultas'}</span></div>
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
    </div>
    <div class="qc-journey">${steps}</div>`;
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
    <div class="qc-meta"><span>${IC.layers}${E(t.origem)}</span><span>${IC.rows}<b>${big(t.linhas)}</b>&nbsp;linhas</span><span>${IC.db}<b>${size(t.gb)}</b></span>
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
      <span class="info">${IC.db}Leitura estimada <b>${p.gb_estimado != null ? '≈ ' + size(p.gb_estimado) : 'a medir'}</b> (consulta original) · cobrança em <b>${E(S.data.projeto_cobranca)}</b> · só leitura</span>
      <span class="grow"></span>
      ${pode ? `<button type="button" class="qc-btn${S.editing ? ' on' : ''}" data-qedit>${IC.code}${S.editing ? 'Concluir edição' : 'Editar consulta'}</button>` : ''}
      <button type="button" class="qc-btn" data-qcopy-sql>${IC.copy}Copiar SQL</button>
      ${pode ? `<button type="button" class="qc-btn primary" data-qrun>${IC.play}Gerar consulta</button>` : `<span class="qc-lockmsg">${IC.lock}Só o administrador master gera consultas</span><button type="button" class="qc-btn" disabled>${IC.lock}Gerar consulta</button>`}</div>
      ${pode && S.editing ? `<div class="qc-edit-hint">${IC.info}<span>Edite à vontade (incluir ou tirar colunas, filtros, período). <b>Clique numa coluna</b> da lista à direita ou da tabela acima para inserir o nome no cursor. Na simulação o sistema confere que é só leitura (SELECT) e só tabelas dos projetos de dados. A versão editada fica guardada neste navegador.</span></div>
        <textarea id="qc-sql-edit" class="qc-edit" spellcheck="false" aria-label="Editar a consulta">${E(curSql(p))}</textarea>`
        : `<pre class="qc-code">${sqlHtml(pode ? curSql(p) : p.sql)}</pre>`}
      <div class="qc-run" id="qc-run"></div></section>
    ${resultHtml(p)}`;
}

/* ---------------- gerar consulta (so o master): simula, confirma, executa ---------------- */
function resultHtml(p) {
  const r = S.result[p.id]; if (!r) return '';
  return `<section class="qc-full qc-result"><div class="qc-gridbar"><span class="qc-tbl-ico sm">${IC.rows}</span>
      <div><h3>Resultado da consulta</h3><small>${nf(r.total_linhas)} linha(s)${r.mostradas < r.total_linhas ? ` · mostrando as ${nf(r.mostradas)} primeiras` : ''} · ${size(r.gb_processados)} processados${r.cache ? ' (cache, sem custo)' : ''} · ${nf(r.segundos, 1)} s · projeto ${E(r.projeto)} · ${E(r.quando)}</small></div>
      <span class="grow" style="flex:1"></span>
      <button type="button" class="qc-btn" data-qcsv>${IC.copy}Baixar CSV</button><button type="button" class="qc-btn" data-qclose>Fechar</button></div>
    ${r.linhas.length ? `<div class="qc-gwrap"><table class="qc-grid-t"><thead><tr><th class="rn">#</th>${r.colunas.map(c => `<th>${E(c)}</th>`).join('')}</tr></thead>
      <tbody>${r.linhas.map((row, i) => `<tr><td class="rn">${i + 1}</td>${row.map(v => `<td>${E(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`
      : '<div class="qc-empty">A consulta não devolveu linhas no período.</div>'}</section>`;
}
async function runFlow(p) {
  const box = document.getElementById('qc-run'); if (!box) return;
  box.classList.add('on'); box.innerHTML = `${IC.clock}<span>Simulando a consulta no BigQuery (dry run, sem custo)…</span>`;
  try {
    const sql = curSql(p);
    const s = await postJson(`/api/query-console/${encodeURIComponent(p.id)}/simular`, {sql}); S.sim = {id: p.id, sql, ...s};
    const tabs = (s.tabelas || []).map(t => `<code>${E(t.split('.').pop())}</code>`).join(', ');
    box.innerHTML = s.acima_do_limite
      ? `${IC.warn}<span>A consulta leria <b>${size(s.gb)}</b>, acima do limite de ${s.limite_gb} GB da Query Console. Não foi executada.</span>`
      : `${IC.info}<span>${s.editada ? '<b>Consulta editada.</b> ' : ''}Vai ler <b>${size(s.gb)}</b>, cobrados no projeto <b>${E(s.projeto)}</b>${tabs ? ` · tabelas: ${tabs}` : ''}. Só leitura; até 500 linhas aparecem aqui. Confirma?</span>
         <span style="flex:1"></span><button type="button" class="qc-btn" data-qcancel>Cancelar</button><button type="button" class="qc-btn primary" data-qexec>${IC.play}Executar consulta</button>`;
  } catch (e) { box.innerHTML = `${IC.warn}<span>${E(e.message)}</span>`; }
}
async function execFlow(p) {
  const box = document.getElementById('qc-run'); if (!box || S.sim?.id !== p.id) return;
  const t0 = Date.now(), tick = setInterval(() => { const s = box.querySelector('[data-t]'); if (s) s.textContent = `${Math.round((Date.now() - t0) / 1000)} s`; }, 1000);
  box.innerHTML = `${IC.clock}<span>Executando no BigQuery… <b data-t>0 s</b></span>`;
  try {
    const r = await postJson(`/api/query-console/${encodeURIComponent(p.id)}/executar`, {confirmado: true, sql: S.sim.sql, bytes_simulados: S.sim.bytes});
    S.result[p.id] = {...r, quando: new Date().toLocaleString('pt-BR')}; S.sim = null; clearInterval(tick); render();
    document.querySelector('.qc-result')?.scrollIntoView({behavior: 'smooth', block: 'start'});
  } catch (e) { clearInterval(tick); box.innerHTML = `${IC.warn}<span>${E(e.message)}</span>`; }
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
  S.sim = null; const box = document.getElementById('qc-run'); if (box) { box.classList.remove('on'); box.innerHTML = ''; }
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

/* ---------------- tela ---------------- */
function render() {
  const r = root(); if (!r || !S.data) return;
  const p = S.sel && proc(S.sel);
  r.innerHTML = `<div class="qc${S.editing && p ? ' qc-editing' : ''}">${headHtml()}${filterHtml()}${p ? detailHtml(p) : overviewHtml()}</div>`;
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
  if (b.hasAttribute('data-qcancel')) { S.sim = null; const box = document.getElementById('qc-run'); box.classList.remove('on'); box.innerHTML = ''; return; }
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
window.nexusQuery = {open, reset: () => { S.data = null; }, _estado: () => S};
})();
