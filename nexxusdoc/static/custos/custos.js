/* Página Custos (24/11/2026, pedido do usuário): custo de cada importação pelas MIROs de débito posterior da PGL
   (Sua Area › PGL S/4HANA › Layouts - MIRO de Déb. Post), ligado a Embarques (pasta, operação, modal) e ao FUP da PGL
   (CIF, datas, canal). Montagem do layout da MIRO no formato da PGL. Só master e owners (o servidor responde 403). */
window.nexusCustos = (() => {
const F0 = {q: '', ano: '', mes: '', op: '', modal: '', st: '', grupo: ''};
const S = {data: null, rows: [], view: 'lista', f: {...F0}, shown: 150, sort: {k: 'data_impostos', d: -1}, loading: false, locked: false,
           monta: null, montaRes: null, embs: null, animDone: false};
const ST = {completo: ['Impostos e despesas', '#3F8F4E'], so_impostos: ['Aguardando despesas', '#C9962E'],
            despesas_pendentes: ['Despesas pendentes', '#B9533F'], so_despesas: ['Só despesas', '#8a8f8c']};
const MODAL_COR = {'Marítimo': '#34679E', 'Aéreo': '#B8892C'};
const MES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
const E = s => esc(s == null ? '' : String(s));
const nf = (v, c = 0) => v == null || Number.isNaN(+v) ? '-' : (+v).toLocaleString('pt-BR', {minimumFractionDigits: c, maximumFractionDigits: c});
const brl = (v, c = 2) => v == null ? '-' : 'R$ ' + nf(v, c);
const curto = v => v == null ? '-' : Math.abs(v) >= 1e6 ? 'R$ ' + nf(v / 1e6, 2) + ' mi' : Math.abs(v) >= 1e3 ? 'R$ ' + nf(v / 1e3, 1) + ' mil' : brl(v);
const brd = v => v ? (/^\d{4}-\d{2}-\d{2}/.test(v) ? v.slice(0, 10).split('-').reverse().join('/') : new Date(v).toLocaleDateString('pt-BR')) : '-';
const J = (method, obj) => ({method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(obj)});
const root = () => document.getElementById('page-custos');
const animOn = () => !window.nexusAnim || window.nexusAnim.enabled();
const G = () => (S.data && S.data.grupos) || [];
const LOG = () => G().filter(g => g.k !== 'impostos');  // grupos do custo logístico (sem II e Siscomex)
const gcor = k => (G().find(g => g.k === k) || {}).cor || '#8a8f8c';
const gnome = k => (G().find(g => g.k === k) || {}).nome || k;

/* Ícones dos cards (desenho próprio, colorido) */
const ICON = {
  proc: '<svg viewBox="0 0 32 32"><path d="M16 3 4 9v14l12 6 12-6V9z" fill="#C8955A"/><path d="M16 3 4 9l12 6 12-6z" fill="#E2B57E"/><path d="M16 15v14l12-6V9z" fill="#A8743F"/></svg>',
  total: '<svg viewBox="0 0 32 32"><ellipse cx="16" cy="23" rx="10" ry="4" fill="#B9862C"/><rect x="6" y="15" width="20" height="8" fill="#D9A441"/><ellipse cx="16" cy="15" rx="10" ry="4" fill="#F2C861"/><rect x="6" y="9" width="20" height="6" fill="#D9A441"/><ellipse cx="16" cy="9" rx="10" ry="4" fill="#F7D97E"/><path d="M13 9h6" stroke="#B9862C" stroke-width="1.6" stroke-linecap="round"/></svg>',
  truck: '<svg viewBox="0 0 32 32"><rect x="2.5" y="9" width="17" height="12" rx="1.6" fill="#2a78d6"/><path d="M19.5 13h5.2l4.3 4.6V21h-9.5z" fill="#1c5cab"/><path d="M21.5 14.6h2.6l2.6 2.8h-5.2z" fill="#cde2fb"/><circle cx="8" cy="22.5" r="3" fill="#33393d"/><circle cx="24" cy="22.5" r="3" fill="#33393d"/><circle cx="8" cy="22.5" r="1.2" fill="#d6dade"/><circle cx="24" cy="22.5" r="1.2" fill="#d6dade"/></svg>',
  tax: '<svg viewBox="0 0 32 32"><path d="M7 3h13l6 6v18a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" fill="#FDF0E8" stroke="#C9592A" stroke-width="1.6"/><path d="M20 3v6h6" fill="#F6D2BE" stroke="#C9592A" stroke-width="1.6" stroke-linejoin="round"/><circle cx="12" cy="15" r="2" fill="#eb6834"/><circle cx="19" cy="22" r="2" fill="#eb6834"/><path d="m19.5 13.5-8 10" stroke="#C9592A" stroke-width="2" stroke-linecap="round"/></svg>',
  unit: '<svg viewBox="0 0 32 32"><path d="M5 12.5 16 6l11 6.5v11L16 30 5 23.5z" fill="#1baf7a"/><path d="M5 12.5 16 19l11-6.5L16 6z" fill="#5ccfa2"/><path d="M16 19v11" stroke="#0e7a53" stroke-width="1.4"/><circle cx="25" cy="7" r="5.5" fill="#fff" stroke="#0e7a53" stroke-width="1.6"/><path d="M25 4.2v5.6M23 5.6c.4-.6 1-.9 1.8-.9.9 0 1.6.5 1.6 1.2 0 1.6-3.4.8-3.4 2.5 0 .7.7 1.2 1.7 1.2.8 0 1.5-.3 1.8-.9" fill="none" stroke="#0e7a53" stroke-width="1.1" stroke-linecap="round"/></svg>',
  pct: '<svg viewBox="0 0 32 32"><circle cx="16" cy="16" r="12" fill="#EEF2FB" stroke="#6250d6" stroke-width="1.6"/><path d="M16 16V4a12 12 0 0 1 10.4 18z" fill="#6250d6"/><circle cx="16" cy="16" r="4.4" fill="#fff"/></svg>',
  alert: '<svg viewBox="0 0 32 32"><path d="M16 3.5 29.5 27h-27z" fill="#FDE8E8" stroke="#d03b3b" stroke-width="2" stroke-linejoin="round"/><path d="M16 12v7.5M16 23v.5" stroke="#b42f2f" stroke-width="3" stroke-linecap="round"/></svg>',
};
const LOCK = '<svg viewBox="0 0 24 24" class="cu-lockic"><rect x="5" y="11" width="14" height="9.5" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>';

async function load() {
  if (S.loading) return; S.loading = true;
  try { S.data = await api('/api/custos'); S.rows = S.data.processos || []; S.locked = false; }
  catch (e) {
    S.loading = false;
    // sem acesso aos valores das MIROs: a página abre na aba Frete internacional (de todos) e as outras ficam com cadeado
    if (e.status === 403) { S.locked = true; S.view = 'frete'; render(); return; }
    root().innerHTML = `<div class="cu-wrap"><div class="cu-empty">${E(e.message)}</div></div>`; return;
  }
  S.loading = false; render();
}
function lockedHtml() {
  return `<div class="cu-locked" id="cu-locked">${LOCK}<h2>Custos por processo</h2>
    <p>Esta aba mostra os valores das MIROs de cada importação: só o administrador e os owners das áreas têm acesso. A aba <b>Frete internacional</b> é aberta a todos.</p></div>`;
}
function open(chave) {
  if (!S.data && !S.locked) { root().innerHTML = '<div class="cu-wrap"><div class="cu-empty">Carregando…</div></div>'; load().then(() => { if (chave && S.data) ficha(chave); }); return; }
  if (S.locked) { render(); return; }
  render();
  if (chave) ficha(chave);
}

/* ---------- Filtros ---------- */
const match = (r, f, skip) => {
  const q = f.q.trim().toLowerCase();
  if (q) { const hay = [r.wfadim, r.ref, r.di, r.emb_nome, r.op, r.modal, r.armador, r.origem, r.colecao, r.cd].join(' ').toLowerCase(); if (!q.split(/\s+/).every(w => hay.includes(w))) return false; }
  if (skip !== 'ano' && f.ano && String(r.ano) !== f.ano) return false;
  if (skip !== 'mes' && f.mes && String(r.mes) !== f.mes) return false;
  if (skip !== 'op' && f.op && (r.op || 'Não identificada') !== f.op) return false;
  if (skip !== 'modal' && f.modal && (r.modal || 'Não identificado') !== f.modal) return false;
  if (skip !== 'st' && f.st && r.status !== f.st) return false;
  if (skip !== 'grupo' && f.grupo && !(r.grupos[f.grupo] > 0)) return false;
  return true;
};
const filtered = () => S.rows.filter(r => match(r, S.f));
function field(key, label, values, fmt = v => v) {
  const cnt = new Map();
  S.rows.filter(r => match(r, S.f, key)).forEach(r => values(r).forEach(v => cnt.set(v, (cnt.get(v) || 0) + 1)));
  const list = [...cnt.entries()].sort(key === 'ano' ? (a, b) => b[0] - a[0] : key === 'mes' ? (a, b) => a[0] - b[0] : (a, b) => b[1] - a[1]);
  const cur = S.f[key];
  return `<label class="cu-field${cur ? ' on' : ''}"><span>${E(label)}</span><select data-f="${key}" aria-label="${E(label)}"><option value="">Todos</option>${list.map(([v, n]) => `<option value="${E(v)}"${String(v) === cur ? ' selected' : ''}>${E(fmt(v))} (${nf(n)})</option>`).join('')}</select></label>`;
}
function filtersHtml() {
  const n = Object.values(S.f).filter(Boolean).length;
  return `<div class="cu-fpanel"><div class="cu-frow">
      <div class="cu-search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></svg><input type="search" id="cu-q" placeholder="Buscar WFADIM, BL/HAWB, DI, pasta, armador…" value="${E(S.f.q)}"></div>
      <span class="cu-fcount">${n ? `${n} filtro${n > 1 ? 's' : ''} ativo${n > 1 ? 's' : ''}` : 'Nenhum filtro'}</span>
      <button type="button" class="cu-btn ghost" id="cu-clear"${n ? '' : ' disabled'}>Limpar filtros</button></div>
    <div class="cu-fgrid">${field('ano', 'Ano', r => r.ano ? [r.ano] : [])}${field('mes', 'Mês', r => r.mes ? [r.mes] : [], v => MES[v - 1])}
      ${field('op', 'Operação', r => [r.op || 'Não identificada'])}${field('modal', 'Modal', r => [r.modal || 'Não identificado'])}
      ${field('st', 'Situação das MIROs', r => [r.status], v => (ST[v] || [v])[0])}${field('grupo', 'Com custo de', r => Object.keys(r.grupos).filter(g => r.grupos[g] > 0), gnome)}</div></div>`;
}

/* ---------- Cabeçalho, abas e números ---------- */
const TABS = [['lista', 'Processos'], ['rel', 'Relatórios'], ['montar', 'Montar layout'], ['frete', 'Frete internacional']];
const tabsHtml = () => `<nav class="cu-tabs" role="tablist">${TABS.map(([k, l]) => `<button type="button" role="tab" data-cuview="${k}" class="${S.view === k ? 'on' : ''}${S.locked && k !== 'frete' ? ' cu-tlock' : ''}" aria-selected="${S.view === k}">${l}${S.locked && k !== 'frete' ? LOCK : ''}</button>`).join('')}</nav>`;
function headHtml() {
  // Frete internacional (24/11/2026): faturas da Asia Shipping e da DMS conferidas pelo BID (static/frete/frete.js)
  if (S.view === 'frete') return `<div class="cu-head"><div><div class="eyebrow">COE INBOUND · CUSTOS DE IMPORTAÇÃO · CENTAURO</div><h1>Validação do frete internacional</h1>
      <p>As faturas da Asia Shipping e da DMS chegam por e-mail e o sistema confere cada cobrança com o BID mais recente, como a calculadora de validação de frete: frete por faixa ou contêiner, IOF, THC, desconsolidação e taxas locais. A cubagem, o peso e os contêineres vêm do FUP da PGL.</p></div>
    <div class="cu-actions"><button type="button" class="cu-btn" id="fr-graf"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 20V10M10 20V4M16 20v-7M21 20H3"/></svg>Gráficos</button><button type="button" class="cu-btn ghost" id="fr-par"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/></svg>Parâmetros</button><button type="button" class="cu-btn ghost" id="fr-xls">Exportar Excel</button></div></div>${tabsHtml()}`;
  if (S.locked) return `<div class="cu-head"><div><div class="eyebrow">COE INBOUND · CUSTOS DE IMPORTAÇÃO</div><h1>Custos por processo</h1></div></div>${tabsHtml()}`;
  const d = S.data, n8n = d.n8n || {};
  return `<div class="cu-head"><div><div class="eyebrow">COE INBOUND · CUSTOS DE IMPORTAÇÃO</div><h1>Custos por processo</h1>
      <p>O custo de cada importação da Fisia pelos layouts de MIRO de débito posterior que a PGL prepara e salva no Drive (o lançamento no SAP é do Grupo SBF): frete, II e Siscomex, porto, armazenagem, transporte e desembaraço. Cada processo é ligado à pasta em Embarques e ao FUP da PGL.</p>
      <div class="cu-when"><span>${nf(d.arquivos)} layouts de MIRO lidos (2025 em diante)</span><span>·</span>
        <span>${n8n.em ? `Última leitura pelo n8n em ${E(new Date(n8n.em).toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'}))}` : 'Leitura automática pelo n8n ainda não começou'}</span><span>·</span><span>${E(d.pasta)}</span></div></div>
    <div class="cu-actions"><button type="button" class="cu-btn" data-cuview="montar">Montar layout de MIRO</button><button type="button" class="cu-btn ghost" id="cu-xls">Exportar Excel</button></div></div>
    ${tabsHtml()}`;
}
function kpisHtml(rows) {
  const sum = (k, rs = rows) => rs.reduce((a, r) => a + (r[k] || 0), 0);
  const tot = sum('total'), logi = sum('logistico'), imp = sum('impostos');
  const comQ = rows.filter(r => r.qtd > 0), un = sum('qtd', comQ) ? sum('logistico', comQ) / sum('qtd', comQ) : null;
  const porModal = m => { const rs = comQ.filter(r => r.modal === m); const q = sum('qtd', rs); return q ? sum('logistico', rs) / q : null; };
  const comCif = rows.filter(r => r.cif > 0), pct = sum('cif', comCif) ? sum('logistico', comCif) / sum('cif', comCif) * 100 : null;
  const pend = rows.filter(r => r.status === 'despesas_pendentes' || r.status === 'so_impostos').length;
  const card = (ic, l, v, sub, attrs = '', cls = '') => `<div class="cu-kpi${cls}"${attrs}><small><span class="cu-ic">${ICON[ic]}</span>${l}</small><b>${v}</b><em>${sub}</em></div>`;
  return `<div class="cu-kpis">
    ${card('proc', 'Processos', nf(rows.length), `${nf(rows.filter(r => r.status === 'completo').length)} com impostos e despesas`)}
    ${card('total', 'Custo total', curto(tot), 'frete, impostos e despesas')}
    ${card('truck', 'Custo logístico', curto(logi), 'sem II e Siscomex')}
    ${card('tax', 'II e Siscomex', curto(imp), tot ? nf(imp / tot * 100, 1) + '% do custo total' : '-')}
    ${card('unit', 'Logístico por unidade', un == null ? '-' : brl(un), `marítimo ${porModal('Marítimo') == null ? '-' : brl(porModal('Marítimo'))} · aéreo ${porModal('Aéreo') == null ? '-' : brl(porModal('Aéreo'))}`)}
    ${card('pct', 'Logístico sobre o CIF', pct == null ? '-' : nf(pct, 2) + '%', `${nf(comCif.length)} processos com CIF no FUP`)}
    ${card('alert', 'Aguardando despesas', nf(pend), `${nf((S.data.sem_miro || []).length)} com DI e sem MIRO`, ' data-kst="pend" role="button" tabindex="0"', pend ? ' warn' : '')}
  </div>`;
}
/* Composição do custo logístico (barra única, cada grupo na sua cor; clique filtra) */
function compoHtml(rows) {
  const tot = {}; LOG().forEach(g => tot[g.k] = rows.reduce((a, r) => a + (r.grupos[g.k] || 0), 0));
  const soma = Object.values(tot).reduce((a, v) => a + v, 0);
  if (!soma) return '';
  const gs = LOG().filter(g => tot[g.k] >= 100);
  return `<div class="cu-compo"><div class="cu-compo-t"><b>Composição do custo logístico</b><small>${curto(soma)} · clique num grupo para filtrar</small></div>
    <div class="cu-compo-bar">${gs.map(g => `<i style="--c:${g.cor};flex:${tot[g.k] / soma}" title="${E(g.nome)}: ${brl(tot[g.k])} (${nf(tot[g.k] / soma * 100, 1)}%)" data-grupo="${g.k}"></i>`).join('')}</div>
    <div class="cu-legend">${gs.map(g => `<button type="button" data-grupo="${g.k}" class="${S.f.grupo === g.k ? 'on' : ''}"><i style="background:${g.cor}"></i>${E(g.nome)} <b>${nf(tot[g.k] / soma * 100, 1)}%</b><small>${curto(tot[g.k])}</small></button>`).join('')}</div></div>`;
}
const pill = st => `<span class="cu-pill" style="--c:${(ST[st] || ['', '#8a8f8c'])[1]}">${E((ST[st] || [st])[0])}</span>`;
const miniBar = r => { const t = r.logistico || 0; if (!t) return '<span class="cu-muted">-</span>'; return `<span class="cu-mini" title="${LOG().filter(g => r.grupos[g.k] > 0).map(g => `${g.nome}: ${brl(r.grupos[g.k])}`).join('\n')}">${LOG().filter(g => r.grupos[g.k] > 0).map(g => `<i style="background:${g.cor};flex:${r.grupos[g.k] / t}"></i>`).join('')}</span>`; };
const COLS = [
  ['wfadim', 'WFADIM'], ['ref', 'BL / HAWB'], ['op', 'Operação'], ['modal', 'Modal'], ['data_impostos', 'MIRO de impostos'],
  ['n_pedidos', 'Pedidos', 'n'], ['qtd', 'Unidades', 'n'], ['total', 'Custo total', 'n'], ['logistico', 'Logístico', 'n'],
  ['impostos', 'II e Siscomex', 'n'], ['logistico_un', 'Logístico / un.', 'n'], ['pct_cif', '% do CIF', 'n'], ['', 'Composição'], ['status', 'Situação'],
];
function tableHtml(rows) {
  const {k, d} = S.sort;
  const sorted = k ? [...rows].sort((a, b) => { const x = a[k], y = b[k]; if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1; return (x > y ? 1 : x < y ? -1 : 0) * d; }) : rows;
  const show = sorted.slice(0, S.shown);
  return `<div class="cu-table"><table><thead><tr>${COLS.map(([c, l, n]) => `<th class="${n || ''}${c ? ' sort' : ''}${c === k ? ' on' : ''}"${c ? ` data-sort="${c}"` : ''}>${l}${c === k ? (d > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr></thead><tbody>
    ${show.map(r => `<tr data-chave="${E(r.chave)}" tabindex="0"><td><b>${E(r.wfadim || '-')}</b>${r.reemitido ? '<small title="A PGL reemitiu o layout (-2, -3…); vale o de número maior">reemitido</small>' : ''}</td><td>${E(r.ref)}</td>
      <td>${r.op ? `<span class="cu-op">${E(r.op)}</span>` : '<span class="cu-muted">-</span>'}</td><td>${E(r.modal || '-')}</td><td>${brd(r.data_impostos || r.data)}</td>
      <td class="n">${nf(r.n_pedidos)}</td><td class="n">${nf(r.qtd)}</td><td class="n"><b>${brl(r.total)}</b></td><td class="n">${brl(r.logistico)}</td><td class="n">${brl(r.impostos)}</td>
      <td class="n">${r.logistico_un == null ? '-' : brl(r.logistico_un)}</td><td class="n">${r.pct_cif == null ? '-' : nf(r.pct_cif, 2) + '%'}</td><td>${miniBar(r)}</td><td>${pill(r.status)}</td></tr>`).join('')}
    </tbody></table></div>
    ${rows.length > S.shown ? `<div class="cu-more"><button type="button" class="cu-btn ghost" id="cu-more">Mostrar mais (${nf(Math.min(150, rows.length - S.shown))} de ${nf(rows.length - S.shown)} restantes)</button></div>` : ''}`;
}
function semMiroHtml() {
  const s = S.data.sem_miro || [];
  if (!s.length) return '';
  return `<details class="cu-sem"><summary><b>${nf(s.length)} processo(s) com DI registrada e sem nenhuma MIRO</b><small>pelo FUP da PGL; a PGL ainda não salvou o layout na pasta</small></summary>
    <div class="cu-table small"><table><thead><tr><th>WFADIM</th><th>BL / HAWB</th><th>Modal</th><th>Registro da DI</th><th>Desembaraço</th><th>Entrega</th><th></th></tr></thead><tbody>
    ${s.slice(0, 100).map(x => `<tr><td>${E(x.wfadim || '-')}</td><td>${E(x.conhecimento)}</td><td>${E(x.modal)}</td><td>${brd(x.registro_di)}</td><td>${brd(x.desembaraco)}</td><td>${brd(x.entrega)}</td><td><a href="#" data-montar-wf="${E(x.wfadim)}" data-montar-ref="${E(x.conhecimento)}">Montar</a></td></tr>`).join('')}
    </tbody></table></div></details>`;
}

/* ---------- Relatórios (gráficos SVG próprios) ---------- */
const ultMeses = (n) => { const out = []; const d = new Date(); d.setDate(1); for (let i = n - 1; i >= 0; i--) { const x = new Date(d.getFullYear(), d.getMonth() - i, 1); out.push(`${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}`); } return out; };
const ym = r => (r.data_impostos || r.data || '').slice(0, 7);
/* Custo logístico por mês (pedido do usuário: o tipo de custo de cada mês mais claro): barras do total do mês com o valor
   em cima e, nas mesmas colunas, uma tabela de calor com cada tipo de custo mês a mês (valor escrito na célula; a cor
   fica mais forte nos meses em que aquele tipo pesou mais). */
function chartMes(rows) {
  const meses = ultMeses(18);
  const por = meses.map(m => { const rs = rows.filter(r => ym(r) === m); const g = {}; LOG().forEach(x => g[x.k] = rs.reduce((a, r) => a + (r.grupos[x.k] || 0), 0)); return {m, g, n: rs.length, t: Object.values(g).reduce((a, v) => a + v, 0)}; });
  const tipos = LOG().filter(g => por.reduce((a, p) => a + p.g[g.k], 0) >= 1000);
  const geral = por.reduce((a, p) => a + p.t, 0);
  const mx = Math.max(1, ...por.map(p => p.t));
  // Valores reduzidos e com a moeda (pedido do usuário: número solto parecia quantidade)
  const mil = v => v >= 1e6 ? 'R$ ' + nf(v / 1e6, 2) + ' mi' : 'R$ ' + nf(v / 1e3, 0) + ' mil';
  const mi = v => 'R$ ' + nf(v / 1e6, 2) + ' mi';
  const lab = m => `${MES[+m.slice(5) - 1]}/${m.slice(2, 4)}`;
  const cols = `grid-template-columns:210px repeat(${meses.length},minmax(0,1fr)) 92px 58px`;
  // Cor de cada linha: do tom bem claro (mês de menor valor) ao tom cheio (maior); texto branco nas células escuras
  const cel = (cor, v, top) => { const f = top ? v / top : 0, a = .1 + .8 * f; return `background:${cor}${Math.round(a * 255).toString(16).padStart(2, '0')};color:${a > .55 ? '#fff' : '#16251c'}`; };
  return `<div class="cu-heat" style="${cols}">
    <div class="cu-hh"></div>${por.map((p, i) => `<div class="cu-hbar" style="--i:${i}" data-mes="${p.m}" role="button" tabindex="0" title="${lab(p.m)}: ${brl(p.t)} em ${nf(p.n)} processo(s). Clique para ver na lista."><b>${p.t ? mi(p.t) : '-'}</b><i style="height:${(p.t / mx * 100).toFixed(1)}%"></i></div>`).join('')}<div class="cu-hh"></div><div class="cu-hh"></div>
    <div class="cu-hh lbl">Tipo de custo</div>${por.map(p => `<div class="cu-hh" data-mes="${p.m}" role="button" tabindex="0">${lab(p.m)}</div>`).join('')}<div class="cu-hh n">18 meses</div><div class="cu-hh n">% do total</div>
    ${tipos.map((g, r) => { const top = Math.max(...por.map(p => p.g[g.k])); const tot = por.reduce((a, p) => a + p.g[g.k], 0);
      return `<div class="cu-hl"><i style="background:${g.cor}"></i>${E(g.nome)}</div>${por.map((p, i) => { const v = p.g[g.k]; return `<div class="cu-hc" style="${cel(g.cor, v, top)};--i:${i};--r:${r}" title="${E(g.nome)} · ${lab(p.m)}: ${brl(v)}">${v >= 500 ? mil(v) : v ? '< R$ 1 mil' : '-'}</div>`; }).join('')}<div class="cu-hc n">${mil(tot)}</div><div class="cu-hc n">${geral ? nf(tot / geral * 100, 1) + '%' : '-'}</div>`; }).join('')}
    <div class="cu-hl tot">Total do mês</div>${por.map((p, i) => `<div class="cu-hc tot" style="--i:${i};--r:${tipos.length}">${p.t ? mil(p.t) : '-'}</div>`).join('')}<div class="cu-hc tot n">${mil(geral)}</div><div class="cu-hc tot n">100%</div>
  </div><p class="cu-note">Valores em reais (mil = milhares; mi = milhões). Cada linha é um tipo de custo; quanto mais escura a célula, maior o valor daquele tipo no mês. Passe o mouse para ver o valor exato.</p>`;
}
/* Ícones dos modais (desenho próprio, na cor da linha de cada gráfico) */
const MODAL_IC = {
  'Marítimo': '<svg viewBox="0 0 32 32" class="cu-mic" aria-hidden="true"><path d="M13 5h6v4h-6z" fill="#8FA9C4"/><path d="M9 9h14v6H9z" fill="#DCE6F0" stroke="#34679E" stroke-width="1.2"/><path d="M11.5 11h2v2h-2zM15 11h2v2h-2zM18.5 11h2v2h-2z" fill="#34679E"/><path d="M4 15h24l-3.5 7h-17z" fill="#34679E"/><path d="M6 17h20" stroke="#fff" stroke-width="1" opacity=".6"/><path d="M3 25c2 0 2-1.4 4-1.4s2 1.4 4 1.4 2-1.4 4-1.4 2 1.4 4 1.4 2-1.4 4-1.4 2 1.4 4 1.4 2-1.4 3-1.4" fill="none" stroke="#7FA3C7" stroke-width="1.6" stroke-linecap="round"/></svg>',
  'Aéreo': '<svg viewBox="0 0 32 32" class="cu-mic" aria-hidden="true"><path d="M16 3c1.2 0 2 1.2 2 3v7l10 5.5v2.5l-10-3v6l3 2.2V28l-5-1.4-5 1.4v-1.8l3-2.2v-6l-10 3v-2.5L14 13V6c0-1.8.8-3 2-3z" fill="#B8892C"/><path d="M16 3c1.2 0 2 1.2 2 3v4h-4V6c0-1.8.8-3 2-3z" fill="#E3C47E"/><path d="M14 13 4 18.5v1L14 15zM18 13l10 5.5v1L18 15z" fill="#8E6A1F"/></svg>',
};
/* Um painel por modal, cada um na sua escala (o aéreo custa 10 a 20 vezes mais por unidade e achataria o marítimo) */
function chartUnit(rows) {
  const meses = ultMeses(18), W = 720, H = 240, pl = 58, pb = 30, pt = 14, step = (W - pl - 40) / (meses.length - 1);
  const painel = m => {
    const pts = meses.map(mm => { const rs = rows.filter(r => r.modal === m && ym(r) === mm && r.qtd > 0); const q = rs.reduce((a, r) => a + r.qtd, 0); return q ? rs.reduce((a, r) => a + r.logistico, 0) / q : null; });
    const vals = pts.filter(v => v != null);
    if (!vals.length) return `<div class="cu-pan"><b>${MODAL_IC[m]}${m}</b><p class="cu-muted">Sem processos com unidades no período.</p></div>`;
    const mx = Math.max(...vals) * 1.15, y = v => pt + (H - pt - pb) * (1 - v / mx), x = i => pl + 20 + i * step;
    let d = '', on = false; pts.forEach((v, i) => { if (v == null) { on = false; return; } d += `${on ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`; on = true; });
    const med = vals.reduce((a, v) => a + v, 0) / vals.length;
    return `<div class="cu-pan"><b>${MODAL_IC[m]}${m}<small>média dos meses ${brl(med)} por unidade</small></b><svg viewBox="0 0 ${W} ${H}" class="cu-svg" role="img" aria-label="Custo logístico por unidade, ${m}">
      ${[0, .25, .5, .75, 1].map(f => mx * f).map(t => `<line x1="${pl}" x2="${W - 10}" y1="${y(t)}" y2="${y(t)}" class="cu-grid"/><text x="${pl - 6}" y="${y(t) + 4}" text-anchor="end" class="cu-ax">${nf(t, 2)}</text>`).join('')}
      ${meses.map((mm, i) => i % 3 ? '' : `<text x="${x(i)}" y="${H - pb + 16}" text-anchor="middle" class="cu-ax">${MES[+mm.slice(5) - 1]}/${mm.slice(2, 4)}</text>`).join('')}
      <path d="${d}" pathLength="1" class="cu-line" fill="none" stroke="${MODAL_COR[m]}" stroke-width="2"/>${pts.map((v, i) => v == null ? '' : `<g class="cu-pt" style="--i:${i}"><circle cx="${x(i)}" cy="${y(v)}" r="3.5" fill="${MODAL_COR[m]}" stroke="#fff" stroke-width="1.5"><title>${m} · ${MES[+meses[i].slice(5) - 1]}/${meses[i].slice(0, 4)}: ${brl(v)} por unidade</title></circle><text x="${x(i)}" y="${(y(v) - 9).toFixed(1)}" text-anchor="middle" class="cu-lab">${nf(v, 2)}</text></g>`).join('')}</svg></div>`;
  };
  return `<div class="cu-pans">${painel('Marítimo')}${painel('Aéreo')}</div>`;
}
function chartOp(rows) {
  const ops = [...new Set(rows.map(r => r.op).filter(Boolean))];
  const linhas = ops.map(op => { const rs = rows.filter(r => r.op === op && r.qtd > 0); const q = rs.reduce((a, r) => a + r.qtd, 0); return {op, v: q ? rs.reduce((a, r) => a + r.logistico, 0) / q : 0, n: rs.length}; }).sort((a, b) => b.v - a.v);
  const mx = Math.max(1, ...linhas.map(l => l.v));
  return `<div class="cu-hbars">${linhas.map((l, n) => `<div class="cu-hb" data-op="${E(l.op)}" role="button" tabindex="0" title="Filtrar ${E(l.op)}"><span>${E(l.op)}</span><div><i style="--i:${n};width:${(l.v / mx * 100).toFixed(1)}%"></i></div><b>${brl(l.v)}</b><small>${nf(l.n)} proc.</small></div>`).join('')}</div>`;
}
function chartArmaz(rows) {
  const faixas = [[0, 5, 'até 5 dias'], [6, 10, '6 a 10 dias'], [11, 15, '11 a 15 dias'], [16, 25, '16 a 25 dias'], [26, 999, 'mais de 25 dias']];
  const linhas = faixas.map(([a, b, l]) => { const rs = rows.filter(r => r.dias_entrega != null && r.dias_entrega >= a && r.dias_entrega <= b); return {l, n: rs.length, v: rs.length ? rs.reduce((s, r) => s + (r.grupos.armazenagem || 0), 0) / rs.length : 0}; });
  const mx = Math.max(1, ...linhas.map(l => l.v));
  if (!linhas.some(l => l.n)) return '<p class="cu-muted">Sem datas de chegada e entrega no FUP para estes processos.</p>';
  return `<div class="cu-hbars">${linhas.map((l, n) => `<div class="cu-hb static"><span>${E(l.l)}</span><div><i style="--i:${n};width:${(l.v / mx * 100).toFixed(1)}%;background:linear-gradient(90deg,#0E7A6E,#14998A 60%,#6CC3B8)"></i></div><b>${brl(l.v, 0)}</b><small>${nf(l.n)} proc.</small></div>`).join('')}</div>
    <p class="cu-note">Média de armazenagem por processo, pelos dias entre a chegada e a entrega no CD (datas do FUP da PGL).</p>`;
}
function relHtml(rows) {
  return `${filtersHtml()}<div class="cu-charts${animOn() ? ' anim' : ''}">
    <section class="cu-card wide"><h3>Custo logístico por mês</h3><p class="cu-sub">Últimos 18 meses, pela data da MIRO de impostos. Clique num mês para ver os processos.</p>${chartMes(rows)}</section>
    <section class="cu-card wide"><h3>Custo logístico por unidade</h3><p class="cu-sub">Por modal, mês a mês (sem II e Siscomex).</p>${chartUnit(rows)}</section>
    <section class="cu-card"><h3>Logístico por unidade, por operação</h3><p class="cu-sub">Clique numa operação para filtrar.</p>${chartOp(rows)}</section>
    <section class="cu-card"><h3>Armazenagem × dias até a entrega</h3><p class="cu-sub">Quanto mais tempo no recinto, maior a armazenagem.</p>${chartArmaz(rows)}</section>
  </div>`;
}

/* ---------- Render ---------- */
function render() {
  const r0 = root(); if (!r0 || (!S.data && !S.locked)) return;
  const rows = filtered();
  let body = '';
  if (S.locked && S.view !== 'frete') body = lockedHtml();
  else if (S.view === 'lista') body = `${kpisHtml(rows)}${filtersHtml()}${compoHtml(rows)}${semMiroHtml()}${rows.length ? tableHtml(rows) : '<div class="cu-empty">Nenhum processo com estes filtros.</div>'}`;
  else if (S.view === 'rel') body = relHtml(rows);
  else if (S.view === 'frete') body = '<div id="fr-root"></div>';
  else body = montarHtml();
  r0.innerHTML = `<div class="cu-wrap${S.animDone || !animOn() ? '' : ' anim'}">${headHtml()}${body}</div>`;
  S.animDone = true;
  bind();
  if (S.view === 'frete' && window.nexusFrete) window.nexusFrete.mount(r0.querySelector('#fr-root'));
}
function bind() {
  const r0 = root();
  r0.querySelector('#cu-xls')?.addEventListener('click', exportar);
  r0.querySelector('#fr-xls')?.addEventListener('click', e => window.nexusFrete && window.nexusFrete.exportar(e.currentTarget));
  r0.querySelector('#fr-graf')?.addEventListener('click', () => window.nexusFrete && window.nexusFrete.graficos());
  r0.querySelector('#fr-par')?.addEventListener('click', () => window.nexusFrete && window.nexusFrete.parametros());
  r0.querySelectorAll('[data-cuview]').forEach(b => b.addEventListener('click', () => {
    S.view = b.dataset.cuview; render();
    if (S.view === 'montar' && !(S.monta && S.monta.procs)) window.scrollTo(0, 0);
  }));
  r0.querySelectorAll('select[data-f]').forEach(s => s.addEventListener('change', () => { S.f[s.dataset.f] = s.value; S.shown = 150; render(); }));
  const q = r0.querySelector('#cu-q');
  if (q) { let t; q.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => { S.f.q = q.value; S.shown = 150; const pos = q.selectionStart; render(); const n = root().querySelector('#cu-q'); n.focus(); n.setSelectionRange(pos, pos); }, 250); }); }
  r0.querySelector('#cu-clear')?.addEventListener('click', () => { S.f = {...F0}; render(); });
  r0.querySelectorAll('[data-grupo]').forEach(b => b.addEventListener('click', () => { S.f.grupo = S.f.grupo === b.dataset.grupo ? '' : b.dataset.grupo; render(); }));
  r0.querySelectorAll('[data-sort]').forEach(th => th.addEventListener('click', () => { const k = th.dataset.sort; S.sort = {k, d: S.sort.k === k ? -S.sort.d : -1}; render(); }));
  r0.querySelector('#cu-more')?.addEventListener('click', () => { S.shown += 150; render(); });
  r0.querySelectorAll('tr[data-chave]').forEach(tr => { const go = () => ficha(tr.dataset.chave); tr.addEventListener('click', go); tr.addEventListener('keydown', e => { if (e.key === 'Enter') go(); }); });
  r0.querySelector('[data-kst="pend"]')?.addEventListener('click', () => { S.f.st = S.f.st === 'despesas_pendentes' ? 'so_impostos' : 'despesas_pendentes'; if (!S.rows.some(r => r.status === S.f.st)) S.f.st = 'so_impostos'; S.view = 'lista'; render(); });
  r0.querySelectorAll('[data-mes]').forEach(b => b.addEventListener('click', () => { const [a, m] = b.dataset.mes.split('-'); S.f.ano = String(+a); S.f.mes = String(+m); S.view = 'lista'; render(); }));
  r0.querySelectorAll('[data-op]').forEach(b => b.addEventListener('click', () => { S.f.op = S.f.op === b.dataset.op ? '' : b.dataset.op; render(); }));
  r0.querySelectorAll('[data-montar-wf]').forEach(a => a.addEventListener('click', e => { e.preventDefault(); iniciarMontagem({wfadim: a.dataset.montarWf, ref: a.dataset.montarRef}); }));
  if (S.view === 'montar' && !S.locked) bindMontar();
}

/* Exportar Excel com retorno na tela (24/11/2026, pedido do usuário: o link não dizia se o download tinha começado) */
async function exportar() {
  const b = root().querySelector('#cu-xls'); if (!b || b.disabled) return;
  const volta = (t, ms) => setTimeout(() => { const x = root().querySelector('#cu-xls'); if (x) { x.disabled = false; x.className = 'cu-btn ghost'; x.textContent = 'Exportar Excel'; } }, ms);
  b.disabled = true; b.classList.add('busy'); b.innerHTML = '<i class="cu-spin"></i>Gerando o Excel…';
  try {
    const r = await fetch('/api/custos/excel', {credentials: 'same-origin'});
    if (!r.ok) { let d = ''; try { d = (await r.json()).detail; } catch {} throw new Error(typeof d === 'string' && d ? d : `Erro ${r.status} ao gerar o Excel.`); }
    const blob = await r.blob();
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'Custos_por_processo_COE_Inbound.xlsx';
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
    b.classList.remove('busy'); b.classList.add('done'); b.textContent = 'Excel baixado ✓'; volta('', 4000);
  } catch (e) {
    b.classList.remove('busy'); b.classList.add('fail'); b.textContent = 'Não foi possível exportar'; b.title = e.message; volta('', 5000);
  }
}

/* ---------- Ficha do processo ---------- */
async function ficha(chave) {
  closeFicha();
  const box = document.createElement('div'); box.className = 'cu-drawer-back'; box.id = 'cu-drawer';
  box.innerHTML = '<aside class="cu-drawer" role="dialog" aria-label="Custos do processo"><div class="cu-empty">Carregando…</div></aside>';
  document.body.appendChild(box);
  box.addEventListener('mousedown', e => { if (e.target === box) closeFicha(); });
  document.addEventListener('keydown', escClose, true);
  let d; try { d = await api('/api/custos/processo/' + encodeURIComponent(chave)); } catch (e) { box.querySelector('.cu-drawer').innerHTML = `<div class="cu-empty">${E(e.message)}</div>`; return; }
  const l = d.linha, f = d.fup || {};
  const fact = (k, v) => v != null && v !== '' ? `<div><small>${E(k)}</small><b>${E(v)}</b></div>` : '';
  const gs = (d.grupos || []).filter(g => l.grupos[g.k] > 0);
  const tot = l.total || 1;
  const datas = [['Embarque', f.embarque], ['Chegada', l.chegada], ['Registro da DI', l.registro_di], ['MIRO de impostos', l.data_impostos], ['Desembaraço', l.desembaraco], ['Entrega no CD', l.entrega], ['MIRO de despesas', l.data_despesas]].filter(x => x[1]);  // ordem das etapas (datas como vieram do FUP)
  const rat = d.rateio;
  box.querySelector('.cu-drawer').innerHTML = `<header><div><div class="eyebrow">${E(l.op || 'Processo')}${l.modal ? ' · ' + E(l.modal) : ''}</div><h2>${E(l.wfadim || l.ref)}</h2><div>${pill(l.status)}${l.reemitido ? ' <span class="cu-tag">layout reemitido pela PGL</span>' : ''}</div></div>
      <button class="cu-x" type="button" aria-label="Fechar">×</button></header>
    <div class="cu-sum">
      <div><small>Custo total</small><b>${brl(l.total)}</b></div><div><small>Custo logístico</small><b>${brl(l.logistico)}</b></div><div><small>II e Siscomex</small><b>${brl(l.impostos)}</b></div>
      <div><small>Logístico por unidade</small><b>${l.logistico_un == null ? '-' : brl(l.logistico_un)}</b></div><div><small>Logístico sobre o CIF</small><b>${l.pct_cif == null ? '-' : nf(l.pct_cif, 2) + '%'}</b></div><div><small>Logístico por kg</small><b>${l.logistico_kg == null ? '-' : brl(l.logistico_kg)}</b></div></div>
    <div class="cu-compo-bar big">${gs.map(g => `<i style="--c:${g.cor};flex:${l.grupos[g.k] / tot}" title="${E(g.nome)}: ${brl(l.grupos[g.k])}"></i>`).join('')}</div>
    <div class="cu-legend static">${gs.map(g => `<span><i style="background:${g.cor}"></i>${E(g.nome)} <b>${brl(l.grupos[g.k])}</b> <small>${nf(l.grupos[g.k] / tot * 100, 1)}%</small></span>`).join('')}</div>
    <div class="cu-facts">${fact('BL / HAWB', l.ref)}${fact('DI', l.di)}${fact('Pedidos (PO FISIA)', nf(l.n_pedidos))}${fact('Unidades', nf(l.qtd))}${fact('Peso bruto (kg)', l.peso ? nf(l.peso, 1) : '')}${fact('Contêineres', l.conteineres || '')}
      ${fact('Armador', l.armador)}${fact('Origem', l.origem)}${fact('Coleção', l.colecao)}${fact('Canal', l.canal)}${fact('CD', l.cd)}${fact('Valor CIF', l.cif ? brl(l.cif) : '')}</div>
    ${datas.length ? `<h3>Linha do tempo</h3><div class="cu-tl">${datas.map(([k, v]) => `<div class="${/MIRO/.test(k) ? 'miro' : ''}"><i></i><b>${E(k)}</b><span>${brd(v)}</span></div>`).join('')}</div>` : ''}
    <p class="cu-links">${l.emb_id ? `<a href="#" data-emb="${E(l.emb_id)}">Abrir em Embarques</a>` : '<span class="cu-muted">Pasta não encontrada em Embarques</span>'}
      <a href="#" data-montar="impostos">Montar MIRO de impostos</a><a href="#" data-montar="despesas">Montar MIRO de despesas</a></p>
    <h3>Rubricas · ${nf(d.rubricas.length)}</h3><div class="cu-table small"><table><thead><tr><th>Rubrica (Texto)</th><th>Descrição</th><th>Grupo</th><th>MIRO</th><th>Fornecedor</th><th>Vencimento</th><th class="n">Itens</th><th class="n">Valor</th></tr></thead><tbody>
      ${d.rubricas.map(r => `<tr><td><code>${E(r.codigo)}</code></td><td>${E(r.nome)}</td><td><span class="cu-dot" style="background:${gcor(r.grupo)}"></span>${E(gnome(r.grupo))}</td><td>${E(r.cabecalho || r.tipo)}</td><td>${E(r.fornecedor)}${r.fornecedor === '122546' ? ' <small>PGL</small>' : r.fornecedor === '150950' ? ' <small>II e 1% COFINS</small>' : r.fornecedor === '150951' ? ' <small>Siscomex</small>' : ''}</td><td>${brd(r.venc)}</td><td class="n">${nf(r.itens)}</td><td class="n"><b>${brl(r.total)}</b></td></tr>`).join('')}
      <tr class="tot"><td colspan="7">Total</td><td class="n"><b>${brl(l.total)}</b></td></tr></tbody></table></div>
    ${rat ? rateioHtml(rat) : ''}
    <h3>Por pedido · ${nf(d.pedidos.length)}</h3><div class="cu-table small"><table><thead><tr><th>PO FISIA</th><th class="n">Itens</th><th class="n">Unidades</th>${LOG().filter(g => l.grupos[g.k] > 0).map(g => `<th class="n">${E(g.nome)}</th>`).join('')}${l.impostos ? '<th class="n">II e Siscomex</th>' : ''}<th class="n">Total</th><th class="n">Por unidade</th></tr></thead><tbody>
      ${d.pedidos.map(p => `<tr><td>${E(p.po)}</td><td class="n">${nf(p.itens)}</td><td class="n">${nf(p.qtd)}</td>${LOG().filter(g => l.grupos[g.k] > 0).map(g => `<td class="n">${brl(p.grupos[g.k] || 0)}</td>`).join('')}${l.impostos ? `<td class="n">${brl(p.grupos.impostos || 0)}</td>` : ''}<td class="n"><b>${brl(p.total)}</b></td><td class="n">${p.qtd ? brl(p.total / p.qtd) : '-'}</td></tr>`).join('')}</tbody></table></div>
    ${d.itens && d.itens.length ? `<details class="cu-itens"><summary>Itens do pedido · ${nf(d.itens.length)} (valor de cada item nas MIROs)</summary><div class="cu-table small"><table><thead><tr><th>PO</th><th>Item</th><th class="n">Qtd.</th><th>Un.</th><th class="n">Logístico</th><th class="n">II e Siscomex</th><th class="n">Total</th><th class="n">Por unidade</th></tr></thead><tbody>
      ${d.itens.map(i => `<tr><td>${E(i.po)}</td><td>${E(i.item)}</td><td class="n">${nf(i.qtd)}</td><td>${E(i.unid)}</td><td class="n">${brl(i.total - (i.grupos.impostos || 0))}</td><td class="n">${brl(i.grupos.impostos || 0)}</td><td class="n"><b>${brl(i.total)}</b></td><td class="n">${i.custo_un == null ? '-' : brl(i.custo_un, 4)}</td></tr>`).join('')}</tbody></table></div></details>`
      : `<p class="cu-note">${d.pode_abrir ? 'Não foi possível ler os itens dos layouts agora.' : 'O valor de cada item aparece quando o Google Drive para computador está ligado neste computador.'}</p>`}
    <h3>Layouts de MIRO</h3><ul class="cu-files">${d.arquivos.map(a => `<li class="${a.vale ? '' : 'old'}"><span class="cu-tag">${E(a.tipo)}</span><div><b>${E(a.nome)}</b><small>${brd(a.data)} · versão ${nf(a.versao)}${a.vale ? ' · é a que vale' : ' · substituída pela reemissão'}</small></div>${a.drive_id ? `<a href="https://drive.google.com/file/d/${encodeURIComponent(a.drive_id)}/view" target="_blank" rel="noopener">Abrir</a>` : ''}</li>`).join('')}</ul>
    <p class="cu-foot">Fonte: Sua Area › PGL S/4HANA › Layouts - MIRO de Déb. Post. Fornecedor 122546 = PGL; 150950 = II e 1% de COFINS; 150951 = Taxa Siscomex e antidumping. PIS, COFINS e ICMS recuperáveis não entram nestas MIROs.</p>`;
  const dr = box.querySelector('.cu-drawer');
  dr.querySelector('.cu-x').addEventListener('click', closeFicha);
  dr.querySelector('[data-emb]')?.addEventListener('click', e => { e.preventDefault(); const id = e.currentTarget.dataset.emb; closeFicha(); showPage('embarques'); setTimeout(() => window.nexusEmb?.ficha?.(id), 150); });
  dr.querySelectorAll('[data-montar]').forEach(a => a.addEventListener('click', e => { e.preventDefault(); closeFicha(); iniciarMontagem({chave: l.chave, tipo: a.dataset.montar}); }));
}
function rateioHtml(rat) {
  if (!rat.rubricas.length) return rat.itens_sem_base.length ? `<p class="cu-note">Conferência do rateio: a planilha proforma do processo não tem os itens ${E(rat.itens_sem_base.slice(0, 5).join(', '))}${rat.itens_sem_base.length > 5 ? '…' : ''}.</p>` : '';
  return `<h3>Conferência do rateio da PGL</h3><p class="cu-sub">Cada rubrica refeita pelo critério da PGL com a planilha proforma do processo (peso bruto de cada item; Siscomex pelo valor). ${rat.ok ? '<b class="cu-ok">O rateio da PGL confere.</b>' : '<b class="cu-bad">Há itens com diferença.</b>'}</p>
    <div class="cu-table small"><table><thead><tr><th>Rubrica</th><th>Base</th><th class="n">Itens</th><th class="n">Com diferença</th><th class="n">Maior diferença</th></tr></thead><tbody>
    ${rat.rubricas.map(r => `<tr><td><code>${E(r.codigo)}</code> ${E(r.nome)}</td><td>${E(r.base)}</td><td class="n">${nf(r.itens)}</td><td class="n">${r.divergentes ? `<b class="cu-bad">${nf(r.divergentes)}</b>` : '0'}</td><td class="n">${brl(r.maior_diferenca)}</td></tr>`).join('')}</tbody></table></div>`;
}
function escClose(e) { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closeFicha(); } }
function closeFicha() { document.getElementById('cu-drawer')?.remove(); document.removeEventListener('keydown', escClose, true); }

/* ---------- Montar layout de MIRO (em lote) ----------
   24/11/2026, pedido do usuário: escolher um ou vários processos, preencher os valores numa grade (processo × rubrica) e
   gerar um CSV só com todos (um arquivo da PGL já junta duas MIROs assim). Cancelar a qualquer momento. */
const DEF_RUB = {impostos: ['PGTOFRETE', 'PGTOBUNKER', 'PGTOCAPATAZIAS', 'DEBITOII/1% Cof', 'DEBITOTX. SISC.'],
                 despesas: ['PGTOARMAZ', 'PGTOFRETEROD', 'PGTOAJDESCARGA', 'PGTODESEMB', 'PGTOCEMERCANTE', 'PGTOFLOWLS']};
const novaMonta = (tipo = 'despesas') => ({tipo, sel: [], procs: null, cols: [], cat: [], erro: '', erroGerar: '', carregando: 0, token: 0});
async function embIndex() {
  if (S.embs) return S.embs;
  try { const d = await api('/api/embarques'); S.embs = (d.processos || []).map(r => ({id: r.id, nome: r.nome, wfadim: r.wfadim || '', bol: r.bol || '', numero: r.numero || '', op: r.op, criada: (r.criada || '').slice(0, 10)})); }
  catch (e) { S.embs = []; }
  return S.embs;
}
const selKey = s => s.chave ? 'c:' + s.chave : s.emb_id ? 'e:' + s.emb_id : 'w:' + (s.wfadim || s.ref);
const naSel = k => (S.monta.sel || []).some(x => selKey(x) === k);
function alternar(item) {
  const m = S.monta, k = selKey(item), i = m.sel.findIndex(x => selKey(x) === k);
  if (i >= 0) m.sel.splice(i, 1); else m.sel.push(item);
  renderFixo();
}
// Redesenha sem perder a rolagem (24/11/2026, relato do usuário: ao escolher um processo mais abaixo, as listas voltavam
// para o topo): guarda a posição da página e de cada lista e devolve depois
function renderFixo() {
  const y = window.scrollY, listas = [...root().querySelectorAll('.cu-pick')].map(l => l.scrollTop);
  render();
  root().querySelectorAll('.cu-pick').forEach((l, i) => { if (listas[i] != null) l.scrollTop = listas[i]; });
  window.scrollTo(0, y);
}
function iniciarMontagem(o) {  // da ficha do processo: já entra selecionado e carregado
  S.view = 'montar'; S.montaRes = null; S.monta = novaMonta(o.tipo || 'despesas');
  const r = o.chave && S.rows.find(x => x.chave === o.chave);
  if (r) S.monta.sel.push({chave: r.chave, rotulo: r.wfadim || r.ref, sub: r.ref});
  else if (o.wfadim || o.ref) S.monta.sel.push({wfadim: o.wfadim, ref: o.ref, rotulo: o.wfadim || o.ref, sub: o.ref});
  render(); window.scrollTo(0, 0);
  if (S.monta.sel.length) carregar();
}
async function resolver(s) {  // item escolhido -> processo para a base (com MIRO: chave; sem: pasta em Embarques)
  if (s.chave) return {chave: s.chave};
  if (s.emb_id) return {emb_id: s.emb_id};
  const k = v => String(v || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  const c = S.rows.find(r => (s.wfadim && r.wfadim === s.wfadim) || (s.ref && k(r.ref) === k(s.ref)));
  if (c) return {chave: c.chave};
  const e = (await embIndex()).find(r => (s.wfadim && r.wfadim.toUpperCase() === String(s.wfadim).toUpperCase()) || (s.ref && (k(r.numero) === k(s.ref) || k(r.bol) === k(s.ref))));
  if (e) return {emb_id: e.id};
  throw new Error('não encontrado em Embarques (a pasta do processo ainda não existe em Sua Area › Processos)');
}
async function carregar() {
  const m = S.monta, tk = ++m.token;
  m.erro = ''; m.erroGerar = ''; S.montaRes = null;
  m.procs = m.sel.map(s => ({s, base: null, erro: '', vals: {}}));
  m.carregando = m.procs.length; render();
  const fila = [...m.procs];
  const trabalha = async () => {
    while (fila.length) {
      const p = fila.shift();
      try {
        const b = await api('/api/custos/layout/base', J('POST', {tipo: m.tipo, ...(await resolver(p.s))}));
        if (tk !== m.token) return;
        p.base = b; p.vals = {...(b.valores || {})};
        if (!m.cat.length) m.cat = b.catalogo || [];
      } catch (e) { if (tk !== m.token) return; p.erro = e.message; }
      m.carregando--; if (tk === m.token) render();
    }
  };
  await Promise.all([trabalha(), trabalha(), trabalha()]);
  if (tk !== m.token) return;
  const usadas = [...new Set(m.procs.flatMap(p => Object.keys(p.vals)))];
  m.cols = usadas.length ? [...DEF_RUB[m.tipo].filter(c => usadas.includes(c)), ...usadas.filter(c => !DEF_RUB[m.tipo].includes(c))] : DEF_RUB[m.tipo].slice();
  render();
}
function cancelar() { const t = S.monta.tipo; S.monta = novaMonta(t); S.montaRes = null; render(); window.scrollTo(0, 0); }
function sugestoes(q) {
  q = String(q || '').trim().toUpperCase();
  const fmt = r => ({chave: r.chave, rotulo: r.wfadim || r.ref, sub: `${r.ref} · ${r.op || ''} ${r.modal || ''} · já tem MIRO`});
  if (q.length < 3) return S.rows.slice(0, 8).map(fmt);
  const a = S.rows.filter(r => (r.wfadim + ' ' + r.ref + ' ' + r.emb_nome).toUpperCase().includes(q)).slice(0, 8).map(fmt);
  const b = (S.embs || []).filter(r => !S.rows.some(x => x.emb_id === r.id) && (r.nome + ' ' + r.wfadim + ' ' + r.bol).toUpperCase().includes(q)).slice(0, 8)
    .map(r => ({emb_id: r.id, rotulo: r.wfadim || r.nome, sub: `${r.nome} · ${r.op} · ainda sem MIRO`}));
  return [...a, ...b];
}
const rubNome = (c, cat) => { const x = (cat || []).find(y => y.codigo === c); return x ? x.nome : ''; };
// Valor em reais como a pessoa digita: "1.234,56", "1234,56", "R$ 1.500", "1.500" (milhar), "1500.5"
const numBR = s => {
  s = String(s || '').replace(/R\$|\s/gi, '').trim(); if (!s) return 0;
  if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.');
  else if (/^\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, '');
  const n = Number(s); return Number.isFinite(n) && n >= 0 ? n : NaN;
};

function montarHtml() {
  const m = S.monta || (S.monta = novaMonta());
  const tipoBtn = (k, l, s) => `<button type="button" data-mtipo="${k}" class="${m.tipo === k ? 'on' : ''}"><b>${l}</b><small>${s}</small></button>`;
  const ativo = !!m.procs;
  let html = `<div class="cu-mont"><section class="cu-card"><h3>1. Tipo de MIRO e processos<small>escolha um ou vários processos; todos saem num arquivo só</small></h3>
    <div class="cu-mrow"><div class="cu-mtipo">${tipoBtn('despesas', 'MIRO de despesas', 'na entrega: armazenagem, transporte, desembaraço e demais despesas da PGL')}${tipoBtn('impostos', 'MIRO de impostos', 'no registro da DI: frete internacional e taxas do agente, II e Siscomex')}</div>
      <div class="cu-search big"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></svg><input type="search" id="cu-mbusca" placeholder="Adicionar processo: WFADIM, BL ou HAWB" autocomplete="off"><div class="cu-sug" id="cu-sug"></div></div></div>
    <div class="cu-selbar"><b>${m.sel.length ? `${nf(m.sel.length)} processo(s) escolhido(s)` : 'Nenhum processo escolhido'}</b>
      <div class="cu-chips">${m.sel.map(s => `<span class="cu-chip">${E(s.rotulo)}${s.sub && s.sub !== s.rotulo ? `<small>${E(String(s.sub).split(' · ')[0])}</small>` : ''}<button type="button" data-unsel="${E(selKey(s))}" aria-label="Tirar ${E(s.rotulo)}">×</button></span>`).join('')}</div>
      <span class="cu-grow"></span>
      ${ativo ? '<button type="button" class="cu-btn ghost" id="cu-cancel">Cancelar montagem</button>' : `${m.sel.length ? '<button type="button" class="cu-btn ghost" id="cu-limpar">Limpar escolha</button>' : ''}<button type="button" class="cu-btn" id="cu-carregar"${m.sel.length ? '' : ' disabled'}>Montar com ${m.sel.length > 1 ? `os ${nf(m.sel.length)} processos` : 'o processo'}</button>`}</div>
    ${m.erro ? `<p class="cu-err">${E(m.erro)}</p>` : ''}</section>`;
  if (!ativo) return html + escolhaHtml() + '</div>';
  html += gradeHtml();
  if (S.montaRes) html += resultadoHtml();
  return html + '</div>';
}
/* Listas para escolher (vários de uma vez) */
function escolhaHtml() {
  const m = S.monta;
  const pendTodos = S.rows.filter(r => r.status === 'despesas_pendentes' || r.status === 'so_impostos');
  const sem = S.data.sem_miro || [];
  const recentes = S.rows.filter(r => r.status === 'completo').slice(0, 10);
  const item = o => { const on = naSel(selKey(o)); return `<li class="${on ? 'on' : ''}"><div><b>${E(o.rotulo)}</b><small>${E(o.sub)}</small></div><button type="button" class="cu-btn ghost sm" data-pick='${E(JSON.stringify(o))}'>${on ? 'Escolhido ✓' : 'Escolher'}</button></li>`; };
  const rowObj = r => ({chave: r.chave, rotulo: r.wfadim || r.ref, sub: `${r.ref} · ${r.op || ''} ${r.modal || ''}${r.entrega ? ' · entregue em ' + brd(r.entrega) : ''}`});
  const semObj = x => ({wfadim: x.wfadim, ref: x.conhecimento, rotulo: x.wfadim || x.conhecimento, sub: `${x.conhecimento} · DI registrada em ${brd(x.registro_di)}`});
  const bloco = (t, sub, objs, tipo) => `<section class="cu-card"><h3>${t}<small>${sub}</small></h3>
    ${objs.length ? `<button type="button" class="cu-link" data-pickall='${E(JSON.stringify(objs))}' data-ptipo="${tipo}">Escolher todos (${nf(objs.length)})</button><ul class="cu-pick">${objs.map(item).join('')}</ul>` : '<p class="cu-muted">Nenhum processo nessa situação.</p>'}</section>`;
  return `<div class="cu-esc">
    ${bloco('Aguardando a MIRO de despesas', 'com impostos e sem despesas', pendTodos.map(rowObj), 'despesas')}
    ${bloco('Com DI registrada e sem MIRO', 'pelo FUP da PGL', sem.map(semObj), 'impostos')}
    ${bloco('MIROs mais recentes', 'para conferir ou refazer', recentes.map(rowObj), '')}
  </div>`;
}
/* Grade: um processo por linha, uma rubrica por coluna */
function gradeHtml() {
  const m = S.monta, imp = m.tipo === 'impostos';
  const tot = p => m.cols.reduce((a, c) => a + (+p.vals[c] || 0), 0);
  const geral = m.procs.reduce((a, p) => a + (p.base ? tot(p) : 0), 0);
  const prontos = m.procs.filter(p => p.base).length;
  return `<section class="cu-card"><h3>2. Valores de cada processo<small>${m.carregando ? `buscando ${nf(m.carregando)} de ${nf(m.procs.length)}…` : `${nf(prontos)} de ${nf(m.procs.length)} prontos`}</small></h3>
    <p class="cu-sub">Um processo por linha e uma rubrica por coluna, em R$. Quando a PGL já salvou o layout do processo, os valores vêm preenchidos. Frete, taxas e despesas são repartidos pelo peso bruto de cada item; Siscomex pelo valor${imp ? '; II e antidumping seguem o valor de cada item da DI' : ''}.</p>
    <div class="cu-table grid"><table><thead><tr><th>Processo</th><th>Data da fatura</th><th>${imp ? 'DI' : 'Atribuição'}</th><th class="n">Itens</th>
      ${m.cols.map(c => `<th class="n rub"><span title="${E(rubNome(c, m.cat))}">${E(c)}</span><button type="button" data-delcol="${E(c)}" aria-label="Tirar ${E(c)}">×</button><small>${E(rubNome(c, m.cat))}</small></th>`).join('')}
      <th class="n">Total</th><th></th></tr></thead><tbody>
      ${m.procs.map((p, i) => {
        const nome = `<b>${E(p.s.rotulo)}</b><small>${E(p.base ? p.base.ref : String(p.s.sub || '').split(' · ')[0])}</small>`;
        if (p.erro) return `<tr class="bad"><td>${nome}</td><td colspan="${4 + m.cols.length}"><span class="cu-bad">${E(p.erro)}</span></td><td><button type="button" class="cu-icon" data-delrow="${i}" aria-label="Tirar">×</button></td></tr>`;
        if (!p.base) return `<tr><td>${nome}</td><td colspan="${4 + m.cols.length}"><span class="cu-load"><i></i>buscando…</span></td><td></td></tr>`;
        const b = p.base, semItens = !b.itens.length;
        return `<tr${semItens ? ' class="bad"' : ''}><td>${nome}</td><td><input type="date" data-pf="${i}|data" value="${E(b.data)}"></td>
          <td><input data-pf="${i}|${imp ? 'di' : 'atribuicao'}" value="${E(imp ? b.di : b.atribuicao)}" class="w"></td>
          <td class="n" title="${E(b.origem_itens || (b.avisos || []).join(' '))}">${semItens ? '<span class="cu-bad">sem itens</span>' : nf(b.itens.length)}</td>
          ${m.cols.map(c => `<td class="n"><input data-pv="${i}|${E(c)}" value="${p.vals[c] ? E(nf(p.vals[c], 2)) : ''}" placeholder="0,00" inputmode="decimal"></td>`).join('')}
          <td class="n"><b data-ptot="${i}">${brl(tot(p))}</b></td><td><button type="button" class="cu-icon" data-delrow="${i}" aria-label="Tirar">×</button></td></tr>`;
      }).join('')}
      <tr class="tot"><td colspan="${4 + m.cols.length}">Total do arquivo</td><td class="n"><b id="cu-gtot">${brl(geral)}</b></td><td></td></tr></tbody></table></div>
    ${m.procs.some(p => p.base && !p.base.itens.length) ? '<p class="cu-warn">Processo marcado como "sem itens": ainda não há a lista de itens dos pedidos (monte a planilha proforma em Embarques). Ele fica de fora do arquivo.</p>' : ''}
    <datalist id="cu-cat">${(m.cat || []).map(c => `<option value="${E(c.codigo)}">${E(c.nome)}</option>`).join('')}</datalist>
    ${m.erroGerar ? `<p class="cu-err" id="cu-merr">${E(m.erroGerar)}</p>` : ''}
    <div class="cu-mact"><input list="cu-cat" id="cu-newcol" placeholder="Outra rubrica (ex.: PGTODEMURRAGE)" class="cu-newcol"><button type="button" class="cu-btn ghost" id="cu-addcol">Adicionar rubrica</button>
      <span class="cu-grow"></span><button type="button" class="cu-btn ghost" id="cu-cancel2">Cancelar montagem</button><button type="button" class="cu-btn" id="cu-gerar"${m.carregando || !prontos ? ' disabled' : ''}>Gerar layout</button></div></section>`;
}
function resultadoHtml() {
  const res = S.montaRes;
  const cab = res.csv.split('\n')[0].split(';'), linhas = res.csv.trim().split('\n').slice(1).map(l => l.split(';'));
  const ver = [0, 3, 6, 9, 10, 13, 14, 15, 17, 18, 19, 22, 23, 24];
  return `<section class="cu-card ok"><h3>3. Layout pronto <small>${E(res.nome)}</small></h3>
    <div class="cu-table small"><table><thead><tr><th>Processo</th><th>BL / HAWB</th><th>Rubricas</th><th class="n">Linhas</th><th class="n">Valor</th></tr></thead><tbody>
      ${res.processos.map(p => `<tr><td>${E(p.wfadim || '-')}</td><td>${E(p.ref)}</td><td>${p.rubricas.map(r => `<code title="${E(r.nome)}: ${brl(r.total)} (${E(r.base)})">${E(r.codigo)}</code>`).join(' ')}</td><td class="n">${nf(p.linhas)}</td><td class="n">${brl(p.total)}</td></tr>`).join('')}
      <tr class="tot"><td colspan="3">Total do arquivo</td><td class="n">${nf(res.linhas)}</td><td class="n"><b>${brl(res.total)}</b></td></tr></tbody></table></div>
    ${res.erros.length ? `<div class="cu-errs"><b>Ficaram de fora (${nf(res.erros.length)}):</b><ul>${res.erros.map(e => `<li><b>${E(e.processo)}</b>: ${E(e.motivo)}</li>`).join('')}</ul></div>` : ''}
    <details class="cu-prev"><summary>Prévia das linhas (${nf(Math.min(linhas.length, 40))} de ${nf(linhas.length)})</summary><div class="cu-table small"><table><thead><tr>${ver.map(i => `<th>${E(cab[i])}</th>`).join('')}</tr></thead><tbody>${linhas.slice(0, 40).map(c => `<tr>${ver.map(i => `<td>${E(c[i])}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>
    <div class="cu-mact"><span class="cu-note">Mesmo formato dos layouts da PGL (ponto e vírgula, vírgula decimal). Nada é gravado no Drive: confira antes de lançar no SAP.</span><span class="cu-grow"></span><button type="button" class="cu-btn ghost" id="cu-nova">Nova montagem</button><button type="button" class="cu-btn" id="cu-baixar">Baixar CSV</button></div></section>`;
}
function bindMontar() {
  const r0 = root(), m = S.monta;
  r0.querySelectorAll('[data-mtipo]').forEach(b => b.addEventListener('click', () => { if (m.tipo === b.dataset.mtipo) return; m.tipo = b.dataset.mtipo; m.cols = []; m.cat = []; if (m.procs) carregar(); else render(); }));
  const bx = r0.querySelector('#cu-mbusca'), sug = r0.querySelector('#cu-sug');
  if (bx) {
    embIndex();
    const pinta = () => {
      const l = sugestoes(bx.value);
      sug.innerHTML = l.map((s, i) => `<button type="button" data-si="${i}"><b>${E(s.rotulo)}${naSel(selKey(s)) ? ' ✓' : ''}</b><small>${E(s.sub)}</small></button>`).join('');
      sug.classList.toggle('on', l.length > 0);
      sug.querySelectorAll('[data-si]').forEach(b => b.addEventListener('mousedown', e => { e.preventDefault(); const s = l[+b.dataset.si]; if (!naSel(selKey(s))) { m.sel.push(s); if (m.procs) { m.procs.push({s, base: null, erro: '', vals: {}}); carregarUm(m.procs[m.procs.length - 1]); } } render(); root().querySelector('#cu-mbusca')?.focus(); }));
    };
    bx.addEventListener('input', pinta);
    bx.addEventListener('click', pinta);
    bx.addEventListener('blur', () => setTimeout(() => sug.classList.remove('on'), 150));
  }
  r0.querySelectorAll('[data-pick]').forEach(b => b.addEventListener('click', () => alternar(JSON.parse(b.dataset.pick))));
  r0.querySelectorAll('[data-pickall]').forEach(b => b.addEventListener('click', () => {
    if (b.dataset.ptipo) m.tipo = b.dataset.ptipo;
    JSON.parse(b.dataset.pickall).forEach(o => { if (!naSel(selKey(o))) m.sel.push(o); }); renderFixo();
  }));
  r0.querySelectorAll('[data-unsel]').forEach(b => b.addEventListener('click', () => {
    const k = b.dataset.unsel; m.sel = m.sel.filter(x => selKey(x) !== k);
    if (m.procs) m.procs = m.procs.filter(p => selKey(p.s) !== k);
    if (m.procs && !m.procs.length) return cancelar();
    renderFixo();
  }));
  r0.querySelector('#cu-limpar')?.addEventListener('click', () => { m.sel = []; renderFixo(); });
  r0.querySelector('#cu-carregar')?.addEventListener('click', carregar);
  r0.querySelector('#cu-cancel')?.addEventListener('click', cancelar);
  r0.querySelector('#cu-cancel2')?.addEventListener('click', cancelar);
  r0.querySelector('#cu-nova')?.addEventListener('click', cancelar);
  if (!m.procs) return;
  const totais = () => {
    let g = 0;
    m.procs.forEach((p, i) => { if (!p.base) return; const t = m.cols.reduce((a, c) => a + (+p.vals[c] || 0), 0); g += t; const el = r0.querySelector(`[data-ptot="${i}"]`); if (el) el.textContent = brl(t); });
    const el = r0.querySelector('#cu-gtot'); if (el) el.textContent = brl(g);
  };
  r0.querySelectorAll('[data-pv]').forEach(inp => inp.addEventListener('input', () => {
    const [i, c] = inp.dataset.pv.split(/\|(.+)/); const v = numBR(inp.value);
    m.procs[+i].vals[c] = Number.isNaN(v) ? 0 : v; inp.classList.toggle('bad', Number.isNaN(v));
    inp.title = Number.isNaN(v) ? 'Valor não entendido: digite em reais, por exemplo 1.234,56' : ''; S.montaRes = null; totais();
  }));
  r0.querySelectorAll('[data-pf]').forEach(inp => inp.addEventListener('change', () => { const [i, f] = inp.dataset.pf.split('|'); m.procs[+i].base[f] = inp.value.trim(); S.montaRes = null; }));
  r0.querySelectorAll('[data-delcol]').forEach(b => b.addEventListener('click', () => { m.cols = m.cols.filter(c => c !== b.dataset.delcol); render(); }));
  r0.querySelectorAll('[data-delrow]').forEach(b => b.addEventListener('click', () => {
    const p = m.procs[+b.dataset.delrow]; m.procs.splice(+b.dataset.delrow, 1); m.sel = m.sel.filter(x => selKey(x) !== selKey(p.s));
    if (!m.procs.length) return cancelar(); render();
  }));
  const addCol = () => { const i = r0.querySelector('#cu-newcol'); const c = (i.value || '').trim(); if (!c) return; if (!m.cols.includes(c)) m.cols.push(c); render(); };
  r0.querySelector('#cu-addcol')?.addEventListener('click', addCol);
  r0.querySelector('#cu-newcol')?.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); addCol(); } });
  r0.querySelector('#cu-gerar')?.addEventListener('click', gerar);
  r0.querySelector('#cu-baixar')?.addEventListener('click', baixar);
}
async function carregarUm(p) {
  const m = S.monta, tk = m.token; m.carregando++; render();
  try { const b = await api('/api/custos/layout/base', J('POST', {tipo: m.tipo, ...(await resolver(p.s))})); if (tk !== m.token) return; p.base = b; p.vals = {...(b.valores || {})};
    Object.keys(p.vals).forEach(c => { if (!m.cols.includes(c)) m.cols.push(c); }); }
  catch (e) { if (tk !== m.token) return; p.erro = e.message; }
  m.carregando--; render();
}
async function gerar() {
  const m = S.monta;
  const processos = m.procs.filter(p => p.base).map(p => {
    const b = p.base, valores = {};
    m.cols.forEach(c => { if (+p.vals[c] > 0) valores[c] = +p.vals[c]; });
    return {ref: b.ref, wfadim: b.wfadim || '', di: b.di || '', data: b.data, atribuicao: b.atribuicao || '1', versao: b.versao || 1,
      itens: b.itens.map(i => ({po: i.po, item: i.item, qtd: i.qtd, unid: i.unid || 'CDA', peso: i.peso, valor: i.valor})), valores, manual: b.manual || {}};
  });
  if (!processos.some(p => Object.keys(p.valores).length)) { m.erroGerar = 'Preencha o valor de pelo menos uma rubrica em algum processo.'; render(); return; }
  m.erroGerar = '';
  const btn = root().querySelector('#cu-gerar'); if (btn) { btn.disabled = true; btn.textContent = 'Gerando…'; }
  try { S.montaRes = await api('/api/custos/layout', J('POST', {tipo: m.tipo, processos})); render(); root().querySelector('.cu-card.ok')?.scrollIntoView({block: 'start'}); }
  catch (e) { m.erroGerar = e.message; render(); root().querySelector('#cu-merr')?.scrollIntoView({block: 'center'}); }
}
function baixar() {
  const r = S.montaRes; if (!r) return;
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([r.csv], {type: 'text/csv'})); a.download = r.nome;
  document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}

// preload: tela de carregamento inicial (dados prontos antes do 1º clique; a página já fica desenhada, escondida)
return {open, ficha, preload: () => S.data || S.locked ? Promise.resolve() : load(), reload: () => { S.data = null; open(); }, montar: iniciarMontagem,
        aba: v => { S.view = v; if (S.data || S.locked) render(); }, view: () => S.view};
})();
