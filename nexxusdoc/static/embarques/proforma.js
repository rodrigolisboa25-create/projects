/* Planilha proforma (página Embarques, 23/11/2026, pedido do usuário): planilha online por processo, montada pelo
   sistema (TCCIs da pasta + base da Ferramenta de Análise em DuckDB) ou trazida da proforma da pasta, editável como uma
   planilha comum: seleção com mouse/Shift+setas, Enter/Tab/F2, digitar já edita, Delete limpa, Ctrl+C/Ctrl+V (inclusive
   do Excel), Ctrl+Z/Ctrl+Y, botão direito para inserir/excluir linhas. Grava sozinho, em lote, logo depois de editar. */
window.nexusPf = (() => {
const P = {el: null, processos: [], meta: null, doc: null, pid: '', vis: [], sel: null, act: null, edit: null, queue: [], sending: false,
  undo: [], redo: [], q: '', soPend: false, poll: 0, status: '', erro: '', busy: '', pick: '', list: null};
const E = s => esc(s == null ? '' : String(s));
// O api() do sistema não põe o Content-Type: sem ele o servidor recusa o corpo (422)
const J = (method, obj) => ({method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(obj)});
const nf = (v, c = 0) => v == null || v === '' || Number.isNaN(+v) ? '' : (+v).toLocaleString('pt-BR', {minimumFractionDigits: c, maximumFractionDigits: c});
const COLS = () => P.meta.colunas;
const isNum = c => c.t === 'num';
const brDate = v => /^\d{4}-\d{2}-\d{2}$/.test(v || '') ? v.split('-').reverse().join('/') : (v || '');
const uid = () => [...crypto.getRandomValues(new Uint8Array(6))].map(b => b.toString(16).padStart(2, '0')).join('');
const OCOR = {tcci: '#3B6FB6', sap: '#5E5A8C', li: '#2E8B57', li_produto: '#7FAF95', otr: '#8A6D3B', bl: '#2F5D8A', rateio: '#9AA6A0', pasta: '#6F8790', manual: '#C9962E'};

function fmt(c, v) {
  if (c.t === 'num') return nf(v, c.d || 0);
  if (c.t === 'data') return brDate(v);
  return v == null ? '' : String(v);
}
function rawEdit(c, v) {
  if (v == null) return '';
  if (c.t === 'num') return String(v).replace('.', ',');
  if (c.t === 'data') return brDate(v);
  return String(v);
}
const total = ln => ln.c.qtd != null && ln.c.preco != null ? Math.round(ln.c.qtd * ln.c.preco * 100) / 100 : null;

async function mount(el, opts = {}) {
  P.el = el; P.processos = opts.processos || [];
  if (opts.pid) P.pid = opts.pid;
  el.innerHTML = '<div class="pf-empty">Carregando…</div>';
  try { P.meta = await api('/api/proformas'); } catch (e) { el.innerHTML = `<div class="pf-empty">${E(e.message)}</div>`; return; }
  if (P.pid) await abrir(P.pid); else render();
  clearInterval(P.poll);
  P.poll = setInterval(sync, 8000);
}

/* ---------- Telas ---------- */
function render() {
  if (!P.el) return;
  if (P.doc) return renderSheet();
  const m = P.meta, b = m.base;
  const proc = P.pid ? P.processos.find(r => r.id === P.pid) : null;
  const tem = new Set(m.proformas.map(x => x.pid));
  const sug = P.pick.trim().length >= 2 ? P.processos.filter(r => (r.nome + ' ' + (r.numero || '')).toLowerCase().includes(P.pick.trim().toLowerCase())).slice(0, 12) : [];
  P.el.innerHTML = `<div class="pf-wrap">
    <div class="pf-top">
      <div class="pf-picker"><label>Abrir ou montar a proforma de um processo</label>
        <div class="pf-search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></svg><input id="pf-pick" placeholder="Digite o BL, HAWB ou número do processo…" value="${E(P.pick)}" autocomplete="off"></div>
        ${sug.length ? `<ul class="pf-sug">${sug.map(r => `<li data-pid="${E(r.id)}"><b>${E(r.nome)}</b><span class="em-op" style="--c:${({INLINE: '#2F5D8A', PROMO: '#8A6D3B', AMOSTRAS: '#3D7A5A', ZELUS: '#5E5A8C'})[r.op] || '#777'}">${E(r.op)}</span><small>${E(r.grupo || '')} · ${E((r.criada || '').slice(0, 10).split('-').reverse().join('/'))} · ${r.faturas ? nf(r.faturas) + ' TCCI(s)' : 'sem TCCI lida'}</small>${tem.has(r.id) ? '<em>proforma salva</em>' : ''}</li>`).join('')}</ul>` : ''}
      </div>
      <div class="pf-base ${b.pronta ? 'ok' : 'warn'}"><b>Base da Ferramenta de Análise</b>
        <span>${b.pronta ? `${E(b.arquivo)} · ${nf((b.linhas || {}).LIs)} LIs, ${nf((b.linhas || {}).TCCI)} linhas de TCCI` : 'ainda não carregada'}${b.rodando ? ` · <i class="pf-spin"></i>${E(b.etapa || 'atualizando')}` : ''}${b.erro ? ` · ${E(b.erro)}` : ''}</span>
        ${b.nova_disponivel && !b.rodando ? `<small>Há uma cópia mais nova: ${E(b.atual)}</small>` : ''}
        <button type="button" class="pf-btn" id="pf-base"${b.rodando ? ' disabled' : ''}>${b.pronta ? 'Atualizar base' : 'Carregar base'}</button></div>
    </div>
    ${proc ? montarHtml(proc, tem.has(proc.id)) : ''}
    ${P.erro ? `<div class="pf-alert">${E(P.erro)}</div>` : ''}
    <div class="pf-card"><header><h3>Proformas no NexxusDoc</h3><span>${nf(m.proformas.length)} proforma(s)</span></header>
      ${m.proformas.length ? `<div class="pf-list"><table><thead><tr><th>Processo</th><th>Operação</th><th class="n">Linhas</th><th class="n">Unidades</th><th class="n">Pendências</th><th>Alterada em</th><th>Por</th><th></th></tr></thead><tbody>
        ${m.proformas.map(x => `<tr data-open="${E(x.pid)}"><td><b>${E(x.processo)}</b></td><td>${E(x.op)}</td><td class="n">${nf(x.linhas)}</td><td class="n">${nf(x.qtd)}</td><td class="n">${x.pendentes ? `<span class="pf-pend">${nf(x.pendentes)}</span>` : '<span class="pf-okt">ok</span>'}</td><td>${E(x.alterado_em ? new Date(x.alterado_em).toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'}) : '')}</td><td>${E(typeof personName === 'function' ? personName(x.alterado_por) : x.alterado_por)}</td><td><button type="button" class="pf-btn sm">Abrir</button></td></tr>`).join('')}</tbody></table></div>`
        : '<div class="pf-empty sm">Nenhuma proforma ainda. Procure o processo acima e clique em <b>Montar pelo sistema</b>.</div>'}</div>
  </div>`;
  const inp = P.el.querySelector('#pf-pick');
  inp.addEventListener('input', () => { P.pick = inp.value; render(); const n = P.el.querySelector('#pf-pick'); n.focus(); n.setSelectionRange(n.value.length, n.value.length); });
  P.el.querySelectorAll('.pf-sug li').forEach(li => li.addEventListener('mousedown', e => { e.preventDefault(); P.pick = ''; P.erro = ''; escolher(li.dataset.pid); }));
  P.el.querySelectorAll('[data-open]').forEach(tr => tr.addEventListener('click', () => abrir(tr.dataset.open)));
  P.el.querySelector('#pf-base')?.addEventListener('click', atualizarBase);
  P.el.querySelectorAll('[data-montar]').forEach(b => b.addEventListener('click', () => montar(b.dataset.montar)));
  P.el.querySelector('#pf-abrir-salva')?.addEventListener('click', () => abrir(P.pid));
}
function montarHtml(r, salva) {
  const temProf = (r.docs || []).includes('proforma');
  return `<div class="pf-card pf-mount"><header><h3>${E(r.nome)}</h3><span>${E(r.op)} · ${E(r.modal || '')} · ${r.faturas ? nf(r.faturas) + ' TCCI(s) lida(s)' : 'nenhuma TCCI lida ainda'}</span></header>
    ${salva ? `<p>Este processo já tem proforma no NexxusDoc.</p><div class="pf-acts"><button type="button" class="pf-btn primary" id="pf-abrir-salva">Abrir a proforma</button></div>` : `
    <p>O NexxusDoc monta a proforma pelas TCCIs da pasta e completa com a base da Ferramenta de Análise (abertura por tamanho, NCM, descrição, peso líquido e contêiner). O que nenhuma fonte trouxer fica em vermelho para preencher.</p>
    <div class="pf-acts"><button type="button" class="pf-btn primary" data-montar="sistema"${P.busy ? ' disabled' : ''}>${P.busy === 'sistema' ? '<i class="pf-spin"></i>Montando…' : 'Montar pelo sistema'}</button>
      ${temProf ? `<button type="button" class="pf-btn" data-montar="pasta"${P.busy ? ' disabled' : ''}>${P.busy === 'pasta' ? '<i class="pf-spin"></i>Trazendo…' : 'Trazer a proforma da pasta'}</button>` : ''}</div>`}</div>`;
}
async function atualizarBase() {
  try { P.meta.base = await api('/api/proformas/base', J('POST', {})); } catch (e) { toast(e.message); }
  render();
  const t = setInterval(async () => { try { const m = await api('/api/proformas'); P.meta = m; if (!m.base.rodando) { clearInterval(t); if (!P.doc) render(); toast(m.base.erro ? m.base.erro : 'Base da Ferramenta atualizada.'); } else if (!P.doc) render(); } catch (e) { clearInterval(t); } }, 3000);
}
function escolher(pid) {
  P.pid = pid;
  if (P.meta.proformas.some(x => x.pid === pid)) return abrir(pid);
  render();
}
async function montar(origem, refazer = false) {
  P.busy = origem; P.erro = ''; render();
  try {
    P.doc = await api('/api/proformas', J('POST', {pid: P.pid, origem, refazer}));
    P.meta = await api('/api/proformas');
    reset(); toast(origem === 'pasta' ? 'Proforma da pasta trazida para a planilha.' : 'Proforma montada pelo sistema.');
  } catch (e) { P.erro = e.message; }
  P.busy = ''; render();
}
async function abrir(pid) {
  P.pid = pid; P.erro = '';
  try { P.doc = await api('/api/proformas/' + pid); reset(); } catch (e) { P.doc = null; P.erro = e.message; }
  render();
}
function reset() { P.sel = {r1: 0, c1: 0, r2: 0, c2: 0}; P.act = {r: 0, c: 0}; P.undo = []; P.redo = []; P.queue = []; P.q = ''; P.soPend = false; P.status = 'salvo'; }
function fechar() { P.doc = null; P.pid = ''; P.erro = ''; P.edit = null; render(); }

/* ---------- Planilha ---------- */
function visiveis() {
  const q = P.q.trim().toLowerCase(), obr = P.meta.obrigatorias;
  P.vis = P.doc.linhas.filter(ln => (!q || COLS().some(c => fmt(c, c.k === 'total' ? total(ln) : ln.c[c.k]).toLowerCase().includes(q)))
    && (!P.soPend || obr.some(k => ln.c[k] == null || ln.c[k] === '')));
  return P.vis;
}
function cellHtml(ln, c, ri, ci) {
  const v = c.k === 'total' ? total(ln) : ln.c[c.k];
  const o = (ln.o || {})[c.k], vazia = v == null || v === '';
  const falta = vazia && P.meta.obrigatorias.includes(c.k);
  const cls = ['pf-c', isNum(c) ? 'n' : '', c.calc ? 'calc' : '', o === 'manual' ? 'man' : '', falta ? 'falta' : '', inSel(ri, ci) ? 'sel' : '', P.act && P.act.r === ri && P.act.c === ci ? 'act' : ''].filter(Boolean).join(' ');
  const tip = (falta ? 'Falta preencher' : o ? 'Origem: ' + (P.meta.origens[o] || o) : '') + (c.calc ? 'Calculado: Quantity × UNIT $' : '');
  return `<td class="${cls}" data-r="${ri}" data-c="${ci}"${tip ? ` title="${E(tip)}"` : ''}>${o && !c.calc && o !== 'manual' ? `<i class="pf-o" style="background:${OCOR[o] || '#999'}"></i>` : ''}${E(fmt(c, v))}</td>`;
}
const inSel = (r, c) => P.sel && r >= Math.min(P.sel.r1, P.sel.r2) && r <= Math.max(P.sel.r1, P.sel.r2) && c >= Math.min(P.sel.c1, P.sel.c2) && c <= Math.max(P.sel.c1, P.sel.c2);
function sums() {
  const s = {qtd: 0, peso_liq: 0, peso_bruto: 0, total: 0};
  P.vis.forEach(ln => { s.qtd += ln.c.qtd || 0; s.peso_liq += ln.c.peso_liq || 0; s.peso_bruto += ln.c.peso_bruto || 0; s.total += total(ln) || 0; });
  return s;
}
function renderSheet() {
  const d = P.doc, cab = d.cab || {}, n = d.numeros || {}, pend = d.pendencias || {total: 0, por_coluna: {}};
  const proc = P.processos.find(r => r.id === d.pid) || {};
  visiveis();
  const s = sums(), filtrado = P.vis.length !== d.linhas.length;
  const cmp = (a, b, tol) => a == null || b == null ? '' : Math.abs(a - b) <= (tol ? Math.max(a, b) * tol : .5) ? 'ok' : 'bad';
  const avisos = (d.montagem || {}).avisos || [];
  const COLW = COLS().map(c => `<col style="width:${c.w}px">`).join('');
  P.el.innerHTML = `<div class="pf-wrap pf-sheet-wrap">
    <div class="pf-head">
      <button type="button" class="pf-back" id="pf-back" title="Voltar à lista de proformas">‹</button>
      <div class="pf-title"><small>${E(d.op)} · ${E(d.modal || '')} · proforma</small><h2>${E(d.processo)}</h2></div>
      <div class="pf-cab">
        ${[['invoice', 'Invoice No'], ['exp', 'EXP No'], ['data', 'Inv Date'], ['bl', 'BL No']].map(([k, l]) => `<label><span>${l}</span><input data-cab="${k}" value="${E(cab[k] || '')}" maxlength="60"></label>`).join('')}
        <label><span>Modal</span><select data-cab="modal"><option value="VL"${cab.modal === 'VL' ? ' selected' : ''}>VL (marítimo)</option><option value="AF"${cab.modal === 'AF' ? ' selected' : ''}>AF (aéreo)</option></select></label>
      </div>
    </div>
    <div class="pf-kpis">
      <div><small>Linhas</small><b>${nf(n.linhas)}</b></div>
      <div><small>Unidades</small><b>${nf(n.qtd)}</b>${proc.qtd != null ? `<em class="${cmp(n.qtd, proc.qtd)}">faturas ${nf(proc.qtd)}</em>` : ''}</div>
      <div><small>Total US$</small><b>${nf(n.total, 2)}</b>${proc.valor_usd != null ? `<em class="${cmp(n.total, proc.valor_usd, .005)}">faturas ${nf(proc.valor_usd, 2)}</em>` : ''}</div>
      <div><small>Peso bruto (kg)</small><b>${nf(n.peso_bruto, 2)}</b>${proc.peso_bruto != null ? `<em class="${cmp(n.peso_bruto, proc.peso_bruto, .01)}">faturas ${nf(proc.peso_bruto, 2)}</em>` : ''}</div>
      <div><small>Peso líquido (kg)</small><b>${nf(n.peso_liq, 2)}</b></div>
      <div><small>TCCIs</small><b>${nf(n.tccis)}</b>${proc.faturas ? `<em class="${cmp(n.tccis, proc.faturas)}">na pasta ${nf(proc.faturas)}</em>` : ''}</div>
      <button type="button" class="pf-pendk ${pend.total ? 'bad' : 'ok'}${P.soPend ? ' on' : ''}" id="pf-pend" title="${E(Object.entries(pend.por_coluna).map(([k, v]) => `${(COLS().find(c => c.k === k) || {}).l}: ${v}`).join(' · ') || 'Nada a preencher')}"><small>Pendências</small><b>${nf(pend.total)}</b><em>${pend.total ? (P.soPend ? 'mostrando só elas' : 'clique para ver') : 'nada a preencher'}</em></button>
    </div>
    ${avisos.length ? `<div class="pf-avisos">${avisos.map(a => `<span>${E(a)}</span>`).join('')}</div>` : ''}
    <div class="pf-bar">
      <button type="button" class="pf-btn icon" id="pf-undo" title="Desfazer (Ctrl+Z)"${P.undo.length ? '' : ' disabled'}><svg viewBox="0 0 24 24"><path d="M9 7 4 12l5 5"/><path d="M4 12h10a6 6 0 0 1 0 12h-2"/></svg></button>
      <button type="button" class="pf-btn icon" id="pf-redo" title="Refazer (Ctrl+Y)"${P.redo.length ? '' : ' disabled'}><svg viewBox="0 0 24 24"><path d="m15 7 5 5-5 5"/><path d="M20 12H10a6 6 0 0 0 0 12h2"/></svg></button>
      <span class="pf-sep"></span>
      <button type="button" class="pf-btn" id="pf-ins"><svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>Inserir linha</button>
      <button type="button" class="pf-btn" id="pf-del"><svg viewBox="0 0 24 24"><path d="M5 7h14M10 7V5h4v2M7 7l1 12h8l1-12"/></svg>Excluir linha(s)</button>
      <span class="pf-sep"></span>
      <div class="pf-search sm"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></svg><input id="pf-q" placeholder="Filtrar a planilha…" value="${E(P.q)}"></div>
      ${filtrado || P.q || P.soPend ? '<button type="button" class="pf-btn" id="pf-limpar">Limpar filtro</button>' : ''}
      <span class="pf-fill"></span>
      <span class="pf-save ${P.status}" id="pf-save">${saveTxt()}</span>
      <a class="pf-btn" href="/api/proformas/${E(d.pid)}/excel" style="text-decoration:none"><svg viewBox="0 0 24 24"><path d="M12 4v11m-4-4 4 4 4-4M5 19h14"/></svg>Baixar Excel</a>
      <button type="button" class="pf-btn" id="pf-remontar" title="Monta de novo pelo sistema (a versão atual fica guardada)">Remontar</button>
      <button type="button" class="pf-btn danger" id="pf-excluir">Excluir</button>
    </div>
    <div class="pf-grid" id="pf-grid" tabindex="0">
      <table><colgroup><col style="width:46px">${COLW}</colgroup>
        <thead><tr><th class="rn">#</th>${COLS().map((c, ci) => `<th data-hc="${ci}" class="${isNum(c) ? 'n' : ''}${c.calc ? ' calc' : ''}" title="${E(c.l)}${(pend.por_coluna || {})[c.k] ? ` · ${pend.por_coluna[c.k]} em branco` : ''}">${E(c.l)}${(pend.por_coluna || {})[c.k] ? `<i class="pf-hp">${pend.por_coluna[c.k]}</i>` : ''}</th>`).join('')}</tr></thead>
        <tbody>${P.vis.length ? P.vis.map((ln, ri) => `<tr data-id="${ln.id}"><td class="rn${P.sel && ri >= Math.min(P.sel.r1, P.sel.r2) && ri <= Math.max(P.sel.r1, P.sel.r2) ? ' on' : ''}" data-rn="${ri}">${ri + 1}</td>${COLS().map((c, ci) => cellHtml(ln, c, ri, ci)).join('')}</tr>`).join('')
          : `<tr><td class="rn"></td><td colspan="${COLS().length}" class="pf-none">${d.linhas.length ? 'Nenhuma linha com esse filtro.' : 'Planilha vazia: clique em Inserir linha ou cole linhas do Excel (Ctrl+V).'}</td></tr>`}</tbody>
        <tfoot><tr><td class="rn">Σ</td>${COLS().map(c => `<td class="${isNum(c) ? 'n' : ''}">${['qtd', 'peso_liq', 'peso_bruto', 'total'].includes(c.k) ? E(nf(s[c.k], c.d || 0)) : c.k === 'po_fisia' ? `<b>${filtrado ? 'Filtrado' : 'Total'}</b>` : ''}</td>`).join('')}</tr></tfoot>
      </table>
    </div>
    <div class="pf-legend"><span><i class="pf-sw man"></i>Digitado na planilha</span><span><i class="pf-sw falta"></i>Falta preencher</span>${Object.entries(OCOR).filter(([k]) => k !== 'manual').map(([k, c]) => `<span><i class="pf-o" style="background:${c}"></i>${E(P.meta.origens[k] || k)}</span>`).join('')}<span class="pf-kb">Atalhos: setas · Shift+setas · Enter/F2 editar · Tab · Delete limpa · Ctrl+C/Ctrl+V · Ctrl+Z/Ctrl+Y · botão direito para linhas</span></div>
  </div>`;
  bindSheet();
}
function saveTxt() {
  return P.status === 'salvando' ? '<i class="pf-spin"></i>Salvando…' : P.status === 'erro' ? 'Não salvou: tentando de novo' : P.status === 'pendente' ? 'Alterações a salvar…'
    : `<svg viewBox="0 0 24 24"><path d="m5 12.5 4.5 4.5L19 7"/></svg>Salvo${P.doc && P.doc.alterado_em ? ' às ' + new Date(P.doc.alterado_em).toLocaleTimeString('pt-BR', {hour: '2-digit', minute: '2-digit'}) : ''}`;
}
function paintSel() {
  const g = P.el.querySelector('#pf-grid'); if (!g) return;
  g.querySelectorAll('td.sel,td.act').forEach(td => td.classList.remove('sel', 'act'));
  g.querySelectorAll('td.rn.on').forEach(td => td.classList.remove('on'));
  if (!P.sel) return;
  const r1 = Math.min(P.sel.r1, P.sel.r2), r2 = Math.max(P.sel.r1, P.sel.r2), c1 = Math.min(P.sel.c1, P.sel.c2), c2 = Math.max(P.sel.c1, P.sel.c2);
  const rows = g.querySelectorAll('tbody tr');
  for (let r = r1; r <= r2 && r < rows.length; r++) {
    const tds = rows[r].children; tds[0].classList.add('on');
    for (let c = c1; c <= c2; c++) tds[c + 1]?.classList.add('sel');
  }
  rows[P.act.r]?.children[P.act.c + 1]?.classList.add('act');
}
function scrollToAct() {
  const td = P.el.querySelector(`#pf-grid tbody tr:nth-child(${P.act.r + 1}) td:nth-child(${P.act.c + 2})`);
  const g = P.el.querySelector('#pf-grid'); if (!td || !g) return;
  const tr = td.getBoundingClientRect(), gr = g.getBoundingClientRect(), head = 34, foot = 32, left = 46;
  if (tr.top < gr.top + head) g.scrollTop -= gr.top + head - tr.top;
  if (tr.bottom > gr.bottom - foot) g.scrollTop += tr.bottom - gr.bottom + foot;
  if (tr.left < gr.left + left) g.scrollLeft -= gr.left + left - tr.left;
  if (tr.right > gr.right) g.scrollLeft += tr.right - gr.right + 14;
}
function updateRow(id) {
  const ri = P.vis.findIndex(l => l.id === id), tr = P.el.querySelector(`#pf-grid tr[data-id="${id}"]`);
  if (ri < 0 || !tr) return;
  const ln = P.vis[ri];
  tr.innerHTML = `<td class="rn" data-rn="${ri}">${ri + 1}</td>` + COLS().map((c, ci) => cellHtml(ln, c, ri, ci)).join('');
}
function refreshFoot() {
  const s = sums(), tf = P.el.querySelector('#pf-grid tfoot tr'); if (!tf) return;
  COLS().forEach((c, ci) => { if (['qtd', 'peso_liq', 'peso_bruto', 'total'].includes(c.k)) tf.children[ci + 1].textContent = nf(s[c.k], c.d || 0); });
}

/* ---------- Edição ---------- */
function startEdit(initial) {
  const c = COLS()[P.act.c], ln = P.vis[P.act.r];
  if (!ln || c.calc) { if (c && c.calc) toast('Total $ é calculado (Quantity × UNIT $).'); return; }
  const td = P.el.querySelector(`#pf-grid tbody tr:nth-child(${P.act.r + 1}) td:nth-child(${P.act.c + 2})`);
  if (!td) return;
  P.edit = {id: ln.id, k: c.k};
  td.classList.add('editing');
  td.innerHTML = `<input class="pf-in${isNum(c) ? ' n' : ''}" value="${E(initial != null ? initial : rawEdit(c, ln.c[c.k]))}">`;
  const inp = td.querySelector('input'); inp.focus();
  if (initial != null) inp.setSelectionRange(inp.value.length, inp.value.length); else inp.select();
  inp.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); commitEdit(inp.value); move(e.shiftKey ? -1 : 1, 0); }
    else if (e.key === 'Tab') { e.preventDefault(); commitEdit(inp.value); move(0, e.shiftKey ? -1 : 1); }
    else if (e.key === 'Escape') { e.preventDefault(); cancelEdit(); }
    else if ((e.key === 'ArrowUp' || e.key === 'ArrowDown') && initial != null) { e.preventDefault(); commitEdit(inp.value); move(e.key === 'ArrowUp' ? -1 : 1, 0); }
    e.stopPropagation();
  });
  inp.addEventListener('blur', () => { if (P.edit && P.edit.id === ln.id && P.edit.k === c.k) commitEdit(inp.value); });
}
function cancelEdit() { const e = P.edit; P.edit = null; if (P.stale) return adopt(P.doc); if (e) updateRow(e.id); paintSel(); P.el.querySelector('#pf-grid')?.focus(); }
function commitEdit(val) {
  const e = P.edit; P.edit = null; if (!e) return;
  if (P.stale) adopt(P.doc);  // chegou versão nova durante a edição: a tela passa a usar as linhas novas
  setCells([{id: e.id, k: e.k, v: val}]);
  P.el.querySelector('#pf-grid')?.focus({preventScroll: true});
}
function parseVal(k, v) {
  const c = COLS().find(x => x.k === k);
  v = v == null ? '' : String(v).trim();
  if (c.t === 'num') { if (!v) return null; let s = v.replace(/\s/g, ''); s = s.includes(',') && s.includes('.') ? (s.lastIndexOf(',') > s.lastIndexOf('.') ? s.replace(/\./g, '').replace(',', '.') : s.replace(/,/g, '')) : s.replace(',', '.'); const n = Number(s); return Number.isFinite(n) ? n : null; }
  if (c.t === 'data' && /^\d{2}\/\d{2}\/\d{4}$/.test(v)) { const [dd, mm, aa] = v.split('/'); return `${aa}-${mm}-${dd}`; }
  return v;
}
// Muda células (local na hora + fila para o servidor) e guarda o inverso para o Desfazer
function setCells(list, {hist = true} = {}) {
  const inv = [], ops = [];
  const byId = new Map(P.doc.linhas.map(l => [l.id, l]));
  list.forEach(({id, k, v}) => {
    const ln = byId.get(id), c = COLS().find(x => x.k === k);
    if (!ln || !c || c.calc) return;
    const nv = parseVal(k, v), ov = ln.c[k] ?? (c.t === 'num' ? null : '');
    if ((nv ?? '') === (ov ?? '')) return;
    inv.push({id, k, v: c.t === 'num' ? (ov == null ? '' : String(ov)) : c.t === 'data' ? brDate(ov) : ov});
    ln.c[k] = nv; ln.o = ln.o || {};
    if (nv == null || nv === '') delete ln.o[k]; else ln.o[k] = 'manual';
    ops.push({tipo: 'cel', linha: id, col: k, valor: nv, rev: ln.rev});
  });
  if (!ops.length) { list.forEach(x => updateRow(x.id)); paintSel(); return; }
  if (hist) { P.undo.push({tipo: 'cel', itens: inv}); P.redo = []; }
  [...new Set(list.map(x => x.id))].forEach(updateRow);
  paintSel(); refreshFoot(); push(ops); syncBar();
}
function insertRows(afterIdx, n, valores = [], {hist = true, ids = null, before = false} = {}) {
  const ref = P.vis[afterIdx], linhas = P.doc.linhas;
  let pos = ref ? linhas.indexOf(ref) + (before ? 0 : 1) : linhas.length;
  const novos = [];
  for (let i = 0; i < n; i++) {
    const vals = valores[i] || {}, id = ids ? ids[i] : uid(), ln = {id, rev: 1, c: {}, o: {}};
    COLS().forEach(c => { if (!c.calc) { const v = vals[c.k]; ln.c[c.k] = v == null || v === '' ? (c.t === 'num' ? null : '') : v; if (v != null && v !== '') ln.o[c.k] = 'manual'; } });
    novos.push(ln);
  }
  const apos = pos > 0 ? linhas[pos - 1].id : null;
  linhas.splice(pos, 0, ...novos);
  push([{tipo: 'ins', apos, inicio: pos === 0, n, ids: novos.map(l => l.id), valores: novos.map(l => {
    const o = {}; COLS().forEach(c => { if (!c.calc && l.c[c.k] != null && l.c[c.k] !== '') o[c.k] = l.c[c.k]; }); return o; })}]);
  if (hist) { P.undo.push({tipo: 'ins', ids: novos.map(l => l.id)}); P.redo = []; }
  renderSheet(); return novos;
}
function deleteRows(ids, {hist = true} = {}) {
  const linhas = P.doc.linhas, alvo = new Set(ids);
  const removidas = [];
  linhas.forEach((ln, i) => { if (alvo.has(ln.id)) removidas.push({ln: JSON.parse(JSON.stringify(ln)), apos: i > 0 ? linhas[i - 1].id : null}); });
  if (!removidas.length) return;
  P.doc.linhas = linhas.filter(ln => !alvo.has(ln.id));
  push([{tipo: 'del', ids: removidas.map(x => x.ln.id)}]);
  if (hist) { P.undo.push({tipo: 'del', itens: removidas}); P.redo = []; }
  const r = Math.min(P.act.r, Math.max(0, visiveis().length - 1)); P.act = {r, c: P.act.c}; P.sel = {r1: r, r2: r, c1: P.act.c, c2: P.act.c};
  renderSheet();
}
function restoreRows(itens) {
  // devolve linhas excluídas na posição de antes (mesmo id), uma a uma
  itens.forEach(({ln, apos}) => {
    const linhas = P.doc.linhas, i = apos ? linhas.findIndex(l => l.id === apos) + 1 : 0;
    linhas.splice(i, 0, ln);
    const vals = {}; COLS().forEach(c => { if (!c.calc && ln.c[c.k] != null && ln.c[c.k] !== '') vals[c.k] = ln.c[c.k]; });
    push([{tipo: 'ins', apos, inicio: !apos, n: 1, ids: [ln.id], valores: [vals]}]);
  });
}
function doUndo(redo = false) {
  const st = redo ? P.redo : P.undo, other = redo ? P.undo : P.redo;
  const a = st.pop(); if (!a) return;
  if (a.tipo === 'cel') {
    const atual = a.itens.map(({id, k}) => { const ln = P.doc.linhas.find(l => l.id === id), c = COLS().find(x => x.k === k); const v = ln ? ln.c[k] : ''; return {id, k, v: c.t === 'num' ? (v == null ? '' : String(v)) : c.t === 'data' ? brDate(v) : v}; });
    setCells(a.itens, {hist: false}); other.push({tipo: 'cel', itens: atual});
  } else if (a.tipo === 'ins') {
    const itens = []; P.doc.linhas.forEach((ln, i) => { if (a.ids.includes(ln.id)) itens.push({ln: JSON.parse(JSON.stringify(ln)), apos: i > 0 ? P.doc.linhas[i - 1].id : null}); });
    deleteRows(a.ids, {hist: false}); other.push({tipo: 'del', itens});
  } else if (a.tipo === 'del') {
    restoreRows(a.itens); other.push({tipo: 'ins', ids: a.itens.map(x => x.ln.id)}); renderSheet();
  }
  syncBar();
}
function syncBar() {
  const u = P.el.querySelector('#pf-undo'), r = P.el.querySelector('#pf-redo');
  if (u) u.disabled = !P.undo.length; if (r) r.disabled = !P.redo.length;
  const s = P.el.querySelector('#pf-save'); if (s) { s.className = 'pf-save ' + P.status; s.innerHTML = saveTxt(); }
}

/* ---------- Gravação (em lote, logo depois de editar) ---------- */
let flushT = 0;
function push(ops) { P.queue.push(...ops); P.status = 'pendente'; syncBar(); clearTimeout(flushT); flushT = setTimeout(flush, 450); }
async function flush() {
  if (P.sending || !P.queue.length || !P.doc) return;
  const ops = P.queue.splice(0), pid = P.doc.pid;
  P.sending = true; P.status = 'salvando'; syncBar();
  try {
    const d = await api('/api/proformas/' + pid, J('PATCH', {ops}));
    if (!P.doc || P.doc.pid !== pid) return;
    adopt(d);
    if ((d.conflitos || []).length) toast(`${d.conflitos.length} linha(s) tinham sido alteradas por outra pessoa na mesma célula: ficou o valor dela.`);
    P.status = P.queue.length ? 'pendente' : 'salvo';
  } catch (e) {
    P.queue.unshift(...ops); P.status = 'erro'; setTimeout(flush, 4000);
  } finally { P.sending = false; syncBar(); if (P.queue.length) { clearTimeout(flushT); flushT = setTimeout(flush, 300); } }
}
// Versão do servidor + o que ainda está na fila (aplicado por cima, para a tela não "voltar" o que a pessoa digitou)
function adopt(d) {
  const edit = P.edit;
  P.doc = d;
  P.queue.forEach(op => {
    if (op.tipo === 'cel') { const ln = d.linhas.find(l => l.id === op.linha); if (ln) { ln.c[op.col] = op.valor; (ln.o = ln.o || {})[op.col] = 'manual'; } }
  });
  if (edit) { P.stale = true; return syncBar(); }  // não redesenha no meio de uma edição (redesenha ao terminar)
  P.stale = false;
  const top = P.el.querySelector('#pf-grid')?.scrollTop || 0, left = P.el.querySelector('#pf-grid')?.scrollLeft || 0;
  renderSheet();
  const g = P.el.querySelector('#pf-grid'); if (g) { g.scrollTop = top; g.scrollLeft = left; }
}
async function sync() {
  if (!P.doc || P.queue.length || P.sending || P.edit || document.hidden || !P.el || !P.el.isConnected) return;
  try { const d = await api(`/api/proformas/${P.doc.pid}?desde=${P.doc.versao}`); if (!d.igual && !P.queue.length && !P.edit) adopt(d); } catch (e) { /* sem rede: tenta de novo */ }
}

/* ---------- Teclado, mouse, área de transferência ---------- */
function move(dr, dc, extend = false) {
  const nr = Math.max(0, Math.min(P.vis.length - 1, P.act.r + dr)), nc = Math.max(0, Math.min(COLS().length - 1, P.act.c + dc));
  P.act = {r: nr, c: nc};
  if (extend) { P.sel.r2 = nr; P.sel.c2 = nc; } else P.sel = {r1: nr, c1: nc, r2: nr, c2: nc};
  paintSel(); scrollToAct();
}
function selRange() { return {r1: Math.min(P.sel.r1, P.sel.r2), r2: Math.max(P.sel.r1, P.sel.r2), c1: Math.min(P.sel.c1, P.sel.c2), c2: Math.max(P.sel.c1, P.sel.c2)}; }
function copySel() {
  const s = selRange(), out = [];
  for (let r = s.r1; r <= s.r2; r++) { const ln = P.vis[r]; if (!ln) continue; const row = []; for (let c = s.c1; c <= s.c2; c++) { const col = COLS()[c]; row.push(fmt(col, col.k === 'total' ? total(ln) : ln.c[col.k]).replace(/\t|\n/g, ' ')); } out.push(row.join('\t')); }
  return out.join('\r\n');
}
function pasteText(text) {
  const rows = text.replace(/\r/g, '').split('\n'); if (rows.length > 1 && rows[rows.length - 1] === '') rows.pop();
  const grid = rows.map(r => r.split('\t'));
  if (!grid.length) return;
  const s = selRange();
  // um valor só e várias células selecionadas: repete em todas
  if (grid.length === 1 && grid[0].length === 1 && (s.r2 > s.r1 || s.c2 > s.c1)) {
    const list = []; for (let r = s.r1; r <= s.r2; r++) for (let c = s.c1; c <= s.c2; c++) { const col = COLS()[c]; if (!col.calc && P.vis[r]) list.push({id: P.vis[r].id, k: col.k, v: grid[0][0]}); }
    return setCells(list);
  }
  const falta = s.r1 + grid.length - P.vis.length;
  if (falta > 0) {
    if (P.q || P.soPend) { toast('Tire o filtro para colar mais linhas do que as visíveis.'); return; }
    const vals = grid.slice(grid.length - falta).map(cells => { const o = {}; cells.forEach((v, j) => { const col = COLS()[s.c1 + j]; if (col && !col.calc && v !== '') o[col.k] = parseVal(col.k, v); }); return o; });
    const list = [];
    grid.slice(0, grid.length - falta).forEach((cells, i) => cells.forEach((v, j) => { const col = COLS()[s.c1 + j]; if (col && !col.calc) list.push({id: P.vis[s.r1 + i].id, k: col.k, v}); }));
    if (list.length) setCells(list);
    insertRows(P.vis.length - 1, falta, vals);
    toast(`${grid.length} linha(s) coladas (${falta} nova(s)).`); return;
  }
  const list = [];
  grid.forEach((cells, i) => cells.forEach((v, j) => { const col = COLS()[s.c1 + j], ln = P.vis[s.r1 + i]; if (col && !col.calc && ln) list.push({id: ln.id, k: col.k, v}); }));
  setCells(list);
  P.sel = {r1: s.r1, c1: s.c1, r2: s.r1 + grid.length - 1, c2: Math.min(COLS().length - 1, s.c1 + Math.max(...grid.map(g => g.length)) - 1)}; paintSel();
}
function clearSel() {
  const s = selRange(), list = [];
  for (let r = s.r1; r <= s.r2; r++) for (let c = s.c1; c <= s.c2; c++) { const col = COLS()[c]; if (!col.calc && P.vis[r]) list.push({id: P.vis[r].id, k: col.k, v: ''}); }
  setCells(list);
}
function selRowIds() { const s = selRange(); return P.vis.slice(s.r1, s.r2 + 1).map(l => l.id); }
function menu(x, y) {
  closeMenu();
  const s = selRange(), n = s.r2 - s.r1 + 1;
  const m = document.createElement('div'); m.className = 'pf-menu'; m.id = 'pf-menu';
  m.innerHTML = `<button data-a="acima">Inserir linha acima</button><button data-a="abaixo">Inserir linha abaixo</button><button data-a="dup">Duplicar ${n > 1 ? n + ' linhas' : 'linha'}</button><hr>
    <button data-a="copiar">Copiar <kbd>Ctrl+C</kbd></button><button data-a="limpar">Limpar células <kbd>Delete</kbd></button><hr><button data-a="excluir" class="danger">Excluir ${n > 1 ? n + ' linhas' : 'linha'}</button>`;
  document.body.appendChild(m);
  const r = m.getBoundingClientRect(); m.style.left = Math.min(x, innerWidth - r.width - 8) + 'px'; m.style.top = Math.min(y, innerHeight - r.height - 8) + 'px';
  m.addEventListener('mousedown', e => e.stopPropagation());
  m.querySelectorAll('button').forEach(b => b.addEventListener('click', async () => {
    closeMenu();
    const a = b.dataset.a;
    if (a === 'acima') insertRows(s.r1, 1, [], {before: true});
    else if (a === 'abaixo') insertRows(s.r2, 1);
    else if (a === 'dup') { const vals = P.vis.slice(s.r1, s.r2 + 1).map(l => { const o = {}; COLS().forEach(c => { if (!c.calc && l.c[c.k] != null && l.c[c.k] !== '') o[c.k] = l.c[c.k]; }); return o; }); insertRows(s.r2, vals.length, vals); }
    else if (a === 'copiar') { try { await navigator.clipboard.writeText(copySel()); toast('Copiado.'); } catch (e) { toast('Use Ctrl+C para copiar.'); } }
    else if (a === 'limpar') clearSel();
    else if (a === 'excluir') deleteRows(selRowIds());
  }));
  setTimeout(() => document.addEventListener('mousedown', closeMenu, {once: true}), 0);
}
function closeMenu() { document.getElementById('pf-menu')?.remove(); }

function bindSheet() {
  const g = P.el.querySelector('#pf-grid');
  P.el.querySelector('#pf-back').addEventListener('click', async () => { await flush(); fechar(); });
  P.el.querySelectorAll('[data-cab]').forEach(inp => inp.addEventListener('change', () => { P.doc.cab[inp.dataset.cab] = inp.value; push([{tipo: 'cab', campo: inp.dataset.cab, valor: inp.value}]); }));
  P.el.querySelector('#pf-undo').addEventListener('click', () => doUndo());
  P.el.querySelector('#pf-redo').addEventListener('click', () => doUndo(true));
  P.el.querySelector('#pf-ins').addEventListener('click', () => { const r = P.vis.length ? selRange().r2 : -1; insertRows(r, 1); move(1, 0); });
  P.el.querySelector('#pf-del').addEventListener('click', () => { if (!P.vis.length) return; const ids = selRowIds(); if (ids.length > 1 && !confirm(`Excluir ${ids.length} linhas?`)) return; deleteRows(ids); });
  P.el.querySelector('#pf-pend').addEventListener('click', () => { P.soPend = !P.soPend; P.act = {r: 0, c: 0}; P.sel = {r1: 0, c1: 0, r2: 0, c2: 0}; renderSheet(); });
  P.el.querySelector('#pf-limpar')?.addEventListener('click', () => { P.q = ''; P.soPend = false; renderSheet(); });
  const q = P.el.querySelector('#pf-q'); let t = 0;
  q.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => { P.q = q.value; P.act = {r: 0, c: 0}; P.sel = {r1: 0, c1: 0, r2: 0, c2: 0}; renderSheet(); const n = P.el.querySelector('#pf-q'); n.focus(); n.setSelectionRange(n.value.length, n.value.length); }, 250); });
  P.el.querySelector('#pf-remontar').addEventListener('click', async () => { if (!confirm('Montar de novo pelo sistema? As alterações feitas na planilha serão substituídas (a versão atual fica guardada no histórico).')) return; await flush(); await montar('sistema', true); });
  P.el.querySelector('#pf-excluir').addEventListener('click', async () => { if (!confirm('Excluir esta proforma do NexxusDoc? (os arquivos da pasta não mudam)')) return; try { await api('/api/proformas/' + P.doc.pid, {method: 'DELETE'}); P.meta = await api('/api/proformas'); toast('Proforma excluída.'); fechar(); } catch (e) { toast(e.message); } });
  let drag = false;
  g.addEventListener('mousedown', e => {
    if (e.button === 2) { const td = e.target.closest('td[data-r]'); if (td && !inSel(+td.dataset.r, +td.dataset.c)) { P.act = {r: +td.dataset.r, c: +td.dataset.c}; P.sel = {r1: P.act.r, c1: P.act.c, r2: P.act.r, c2: P.act.c}; paintSel(); } return; }
    const rn = e.target.closest('td[data-rn]');
    if (rn) { const r = +rn.dataset.rn; if (e.shiftKey) P.sel.r2 = r; else { P.sel = {r1: r, r2: r, c1: 0, c2: COLS().length - 1}; P.act = {r, c: 0}; } P.sel.c1 = 0; P.sel.c2 = COLS().length - 1; paintSel(); drag = 'row'; g.focus({preventScroll: true}); e.preventDefault(); return; }
    const hc = e.target.closest('th[data-hc]');
    if (hc) { const c = +hc.dataset.hc; P.sel = {r1: 0, r2: Math.max(0, P.vis.length - 1), c1: c, c2: c}; P.act = {r: 0, c}; paintSel(); g.focus({preventScroll: true}); return; }
    const td = e.target.closest('td[data-r]'); if (!td || td.classList.contains('editing')) return;
    const r = +td.dataset.r, c = +td.dataset.c;
    if (e.shiftKey && P.sel) { P.sel.r2 = r; P.sel.c2 = c; } else { P.act = {r, c}; P.sel = {r1: r, c1: c, r2: r, c2: c}; }
    paintSel(); drag = 'cell'; g.focus({preventScroll: true}); e.preventDefault();
  });
  g.addEventListener('mouseover', e => {
    if (!drag) return;
    if (drag === 'row') { const rn = e.target.closest('td[data-rn]') || e.target.closest('tr')?.querySelector('td[data-rn]'); if (rn) { P.sel.r2 = +rn.dataset.rn; paintSel(); } return; }
    const td = e.target.closest('td[data-r]'); if (td) { P.sel.r2 = +td.dataset.r; P.sel.c2 = +td.dataset.c; paintSel(); }
  });
  P.endDrag = () => { drag = false; };
  g.addEventListener('dblclick', e => { const td = e.target.closest('td[data-r]'); if (td) { P.act = {r: +td.dataset.r, c: +td.dataset.c}; startEdit(); } });
  g.addEventListener('contextmenu', e => { if (e.target.closest('td[data-r],td[data-rn]')) { e.preventDefault(); menu(e.clientX, e.clientY); } });
  g.addEventListener('keydown', e => {
    if (P.edit || !P.vis.length) return;
    const k = e.key, ctrl = e.ctrlKey || e.metaKey;
    if (ctrl && k.toLowerCase() === 'z') { e.preventDefault(); doUndo(e.shiftKey); return; }
    if (ctrl && k.toLowerCase() === 'y') { e.preventDefault(); doUndo(true); return; }
    if (ctrl && k.toLowerCase() === 'a') { e.preventDefault(); P.sel = {r1: 0, c1: 0, r2: P.vis.length - 1, c2: COLS().length - 1}; paintSel(); return; }
    if (ctrl && (k.toLowerCase() === 'c' || k.toLowerCase() === 'v' || k.toLowerCase() === 'x')) return;  // eventos copy/paste abaixo
    const map = {ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1]};
    if (map[k]) { e.preventDefault(); const [dr, dc] = map[k]; if (ctrl) move(dr ? (dr < 0 ? -P.vis.length : P.vis.length) : 0, dc ? (dc < 0 ? -99 : 99) : 0, e.shiftKey); else move(dr, dc, e.shiftKey); return; }
    if (k === 'Tab') { e.preventDefault(); move(0, e.shiftKey ? -1 : 1); return; }
    if (k === 'Enter' || k === 'F2') { e.preventDefault(); startEdit(); return; }
    if (k === 'Home') { e.preventDefault(); move(ctrl ? -P.vis.length : 0, -99); return; }
    if (k === 'End') { e.preventDefault(); move(ctrl ? P.vis.length : 0, 99); return; }
    if (k === 'PageDown' || k === 'PageUp') { e.preventDefault(); move(k === 'PageDown' ? 20 : -20, 0, e.shiftKey); return; }
    if (k === 'Delete' || k === 'Backspace') { e.preventDefault(); clearSel(); return; }
    if (k.length === 1 && !ctrl && !e.altKey) { e.preventDefault(); startEdit(k); }
  });
  g.addEventListener('copy', e => { if (P.edit) return; e.preventDefault(); e.clipboardData.setData('text/plain', copySel()); });
  g.addEventListener('cut', e => { if (P.edit) return; e.preventDefault(); e.clipboardData.setData('text/plain', copySel()); clearSel(); });
  g.addEventListener('paste', e => {
    if (P.edit) return; e.preventDefault();
    const text = e.clipboardData.getData('text/plain'); if (!text) return;
    if (!P.vis.length) { const rows = text.replace(/\r/g, '').split('\n').filter(Boolean).map(r => r.split('\t')); insertRows(-1, rows.length, rows.map(cells => { const o = {}; cells.forEach((v, j) => { const col = COLS()[j]; if (col && !col.calc && v !== '') o[col.k] = parseVal(col.k, v); }); return o; })); return; }
    pasteText(text);
  });
  if (!P.edit) g.focus({preventScroll: true});
}
function open(pid) { P.pid = pid; P.doc = null; }
window.addEventListener('mouseup', () => P.endDrag && P.endDrag());
return {mount, open, flush, _estado: () => P};
})();
