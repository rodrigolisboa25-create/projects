/* Página PGL › Relatórios da PGL (23/11/2026, pedido do usuário): os relatórios diários que a PGL manda por e-mail
   (FUP Fisia, Fisia / Zelus e SBF). O n8n lê o anexo no Gmail e grava nexxusdoc_pgl_relatorios.json; aqui a planilha
   inteira vira consulta online (busca, filtro por coluna, ordenação, colunas, Excel do que está na tela), com KPIs e
   gráficos que filtram a planilha ao clicar. Só consulta: o relatório é da PGL. */
window.nexusPglRel = (() => {
const S = {lista: null, tipo: '', dados: {}, cache: {}, root: null, f: null, anim: new Set(), sort: null, colsOff: {}, scrollTop: 0};
const E = s => esc(s == null ? '' : String(s));
const nf = (v, c = 0) => v == null || v === '' || Number.isNaN(+v) ? '-' : (+v).toLocaleString('pt-BR', {minimumFractionDigits: c, maximumFractionDigits: c});
const ISO = /^\d{4}-\d{2}-\d{2}$/;
const brd = v => ISO.test(v || '') ? v.slice(8, 10) + '/' + v.slice(5, 7) + '/' + v.slice(0, 4) : (v || '');
const fold = s => String(s == null ? '' : s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const hoje = () => new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10);
const dias = (a, b) => (Date.parse(b) - Date.parse(a)) / 864e5;
const addDias = (iso, n) => new Date(Date.parse(iso) + n * 864e5).toISOString().slice(0, 10);
const animOn = () => !window.nexusAnim || window.nexusAnim.enabled();
const RH = 30;  // altura da linha da planilha (px): a lista é desenhada só na parte visível
const LS = k => { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } };
const LSset = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* sem armazenamento: segue */ } };
// Fases do processo (pelas datas do próprio relatório; nada estimado)
const FASES = {
  transito: {l: 'Em trânsito', c: '#38bdf8', d: 'Embarcou e ainda não chegou ao Brasil'},
  no_brasil: {l: 'Aguardando desembaraço', c: '#f4b740', d: 'Chegou ao Brasil e ainda não foi desembaraçado'},
  desembaracado: {l: 'Aguardando entrega', c: '#a78bfa', d: 'Desembaraçado e ainda não entregue no CD'},
  entregue: {l: 'Entregue', c: '#3ee08f', d: 'Mercadoria entregue no CD'},
};
const CANAL = {VERDE: '#2fbf71', AMARELO: '#e8b429', VERMELHO: '#e5484d', CINZA: '#8a9aa3'};
const ICO = {
  box: '<svg viewBox="0 0 24 24"><path d="M12 2.8 3.5 7v10L12 21.2 20.5 17V7z"/><path d="M3.5 7 12 11.2 20.5 7M12 11.2v10"/></svg>',
  ship: '<svg viewBox="0 0 24 24"><path d="M3 15.5h18l-2.4 4.2H5.4z"/><path d="M6 15.5V10h12v5.5M9 10V6.5h6V10M12 3v3.5"/></svg>',
  port: '<svg viewBox="0 0 24 24"><path d="M4 20V9l8-5 8 5v11"/><path d="M9 20v-6h6v6M4 20h16"/></svg>',
  shield: '<svg viewBox="0 0 24 24"><path d="M12 3 4.5 6v5.5c0 4.5 3.2 8.2 7.5 9.5 4.3-1.3 7.5-5 7.5-9.5V6z"/><path d="m8.8 12 2.3 2.3 4.3-4.6"/></svg>',
  truck: '<svg viewBox="0 0 24 24"><path d="M2.5 6.5h11v9h-11zM13.5 9.5h4l3 3.2v2.8h-7z"/><circle cx="6.5" cy="17.5" r="1.8"/><circle cx="17" cy="17.5" r="1.8"/></svg>',
  ok: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m7.8 12.2 2.9 2.9 5.5-6"/></svg>',
  late: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5.2l3.2 2"/></svg>',
  red: '<svg viewBox="0 0 24 24"><path d="M12 3.5 21 19H3z"/><path d="M12 10v4M12 16.6v.4"/></svg>',
  clock: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5h4"/></svg>',
  search: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></svg>',
  cols: '<svg viewBox="0 0 24 24"><rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M9.2 4.5v15M14.8 4.5v15"/></svg>',
  xls: '<svg viewBox="0 0 24 24"><path d="M6 3.5h8l4 4v13H6z"/><path d="M14 3.5V8h4M9 12l4 5m0-5-4 5"/></svg>',
  clear: '<svg viewBox="0 0 24 24"><path d="M4 5h16l-6 7.5V19l-4-2v-4.5z"/><path d="m16.5 15.5 4 4m0-4-4 4"/></svg>',
  link: '<svg viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>',
  mail: '<svg viewBox="0 0 24 24"><rect x="3" y="5.5" width="18" height="13" rx="2"/><path d="m3.5 7 8.5 6 8.5-6"/></svg>',
};

/* ---------- dados ---------- */
async function loadLista() {
  S.lista = await api('/api/pgl/relatorios');
  const salvo = LS('nexus.pgl.rel.tipo');
  const com = S.lista.relatorios.filter(r => r.linhas);
  S.tipo = S.tipo || (com.find(r => r.tipo === salvo) || com[0] || S.lista.relatorios[0]).tipo;
}
async function loadTipo(tipo) {
  if (!S.cache[tipo]) {
    const d = await api('/api/pgl/relatorios/' + encodeURIComponent(tipo));
    d.ci = Object.fromEntries(d.colunas.map((c, j) => [c, j]));
    d.datas = new Set(d.colunas.filter((c, j) => d.linhas.some(l => ISO.test(l[j] || ''))));
    d.rows = d.linhas.map((l, i) => derive(d, l, i));
    S.cache[tipo] = d;
  }
  S.dados = S.cache[tipo];
  S.f = S.f && S.f.tipo === tipo ? S.f : {tipo, q: '', fase: '', col: {}, chip: ''};
  S.colsOff = LS('nexus.pgl.rel.cols.' + tipo) || {};
  S.sort = null;
}
// Campos que os KPIs e os gráficos usam (pelo nome da coluna; coluna que faltar fica vazia)
function derive(d, l, i) {
  const g = c => (d.ci[c] === undefined ? null : l[d.ci[c]]);
  const r = {i, modal: g('MODAL') || '', proc: g('PROCESSO') || '', conh: g('CONHECIMENTO') || g('REF CLIENTE') || '',
    embarque: g('EMBARQUE NA ORIGEM'), prev_chegada: g('PREVISAO_CHEGADA'), chegada: g('CHEGADA MERCADORIA'), presenca: g('PRESENCA CARGA'),
    registro: g('REGISTRO DI'), desemb: g('DESEMBARACO'), prev_entrega: g('PREVISAO ENTR MERC_FAB'), entrega: g('ENTREGA DA MERC'),
    canal: String(g('CANAL') || '').toUpperCase(), status: g('STATUS') || '', armazem: g('ARMAZEM DESCARGA') || g('ARMAZEM ATRACACAO') || '',
    agente: g('AGENTE CARGA') || '', total: +g('TOTAL') || 0, cd: g('ARMAZEM DESCARGA TMS') || ''};
  r.fase = r.entrega ? 'entregue' : r.desemb ? 'desembaracado' : r.chegada ? 'no_brasil' : 'transito';
  const m = String(r.status).match(/^\s*(\d+)\s*(.*)$/);
  r.sn = m ? +m[1] : 99; r.sl = m ? m[2].replace(/\s+/g, ' ').trim() : String(r.status).trim();
  const h = hoje();
  r.atraso = !r.entrega && ((r.prev_entrega && r.prev_entrega < h) || (!r.chegada && r.prev_chegada && r.prev_chegada < h)) ? true : false;
  return r;
}

/* ---------- filtros ---------- */
const CHIPS = {
  '': 'Todos', transito: 'Em trânsito', no_brasil: 'Aguardando desembaraço', desembaracado: 'Aguardando entrega',
  entregue30: 'Entregues em 30 dias', atraso: 'Com previsão vencida', vermelho: 'Canal vermelho ou amarelo',
};
function passa(r, f, skipCol) {
  const h = hoje();
  if (f.chip) {
    if (FASES[f.chip] && r.fase !== f.chip) return false;
    if (f.chip === 'entregue30' && !(r.entrega && dias(r.entrega, h) <= 30)) return false;
    if (f.chip === 'atraso' && !r.atraso) return false;
    if (f.chip === 'vermelho' && !['VERMELHO', 'AMARELO'].includes(r.canal)) return false;
  }
  const lin = S.dados.linhas[r.i];
  if (f.q) { const hay = fold(lin.map(cell).join(' ')); if (!fold(f.q).split(/\s+/).filter(Boolean).every(w => hay.includes(w))) return false; }
  for (const [c, v] of Object.entries(f.col)) {
    if (!v || c === skipCol) continue;
    const j = S.dados.ci[c]; if (j === undefined) continue;
    if (v.startsWith('=')) { if (fold(cell(lin[j])) !== fold(v.slice(1))) return false; }
    else if (!fold(cell(lin[j])).includes(fold(v))) return false;
  }
  return true;
}
const cell = v => v == null ? '' : ISO.test(v) ? brd(v) : String(v);
function filtrados() {
  const rows = S.dados.rows.filter(r => passa(r, S.f));
  if (S.sort) {
    const j = S.dados.ci[S.sort.c], dir = S.sort.d;
    rows.sort((a, b) => {
      const x = S.dados.linhas[a.i][j], y = S.dados.linhas[b.i][j];
      if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
      return (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), 'pt-BR', {numeric: true})) * dir;
    });
  }
  return rows;
}
const nFiltros = () => (S.f.q ? 1 : 0) + (S.f.chip ? 1 : 0) + Object.values(S.f.col).filter(Boolean).length;

/* ---------- página ---------- */
async function mount(el) {
  S.root = el;
  if (!S.lista) el.innerHTML = '<div class="pr-wrap"><div class="pr-empty">Carregando os relatórios da PGL…</div></div>';
  try { await loadLista(); await loadTipo(S.tipo); }
  catch (e) { el.innerHTML = `<div class="pr-wrap"><div class="pr-empty"><b>Os relatórios da PGL ainda não estão disponíveis</b>${E(e.message)}</div></div>`; return; }
  render();
}
function render() {
  const el = S.root; if (!el || !S.dados) return;
  const d = S.dados, rows = S.dados.rows, vis = filtrados();
  const fmtW = v => v ? new Date(v).toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'}) : '-';
  const tabs = S.lista.relatorios.map(r => `<button type="button" class="pr-tab${r.tipo === S.tipo ? ' on' : ''}" data-tipo="${E(r.tipo)}"${r.linhas ? '' : ' disabled'}>
      <span class="pr-tab-ic">${ICO.mail}</span><span class="pr-tab-t"><b>${E(r.titulo)}</b><small>${r.linhas ? `${nf(r.linhas)} processos · recebido ${E(fmtW(r.recebido_em))}` : 'ainda não chegou'}</small></span>
      <span class="pr-unit u-${E(r.unidade.toLowerCase())}">${E(r.unidade)}</span></button>`).join('');
  const meta = S.lista.relatorios.find(r => r.tipo === S.tipo) || {};
  el.innerHTML = `<div class="pr-wrap">
    <div class="pr-hero">
      <div class="pr-hero-txt"><div class="pr-eyebrow"><i class="pr-live"></i>PGL · relatórios que chegam por e-mail</div>
        <h2>Relatórios diários da PGL</h2>
        <p>O follow-up que a PGL envia várias vezes ao dia, lido sozinho pelo n8n direto do e-mail. Consulte a planilha completa, filtre e exporte; os números e gráficos acompanham o filtro.</p></div>
      <div class="pr-hero-meta"><div><small>Relatório</small><b>${E(meta.assunto || '')}</b></div><div><small>Recebido</small><b>${E(fmtW(d.recebido_em))}</b></div><div><small>Arquivo</small><b class="mono">${E(d.arquivo || '-')}</b></div></div>
    </div>
    <div class="pr-tabs-box"><span class="pr-tabs-lbl">Escolha o relatório</span><div class="pr-tabs" role="tablist" aria-label="Relatórios">${tabs}</div></div>
    <div class="pr-kpis" id="pr-kpis">${kpis(vis)}</div>
    <div class="pr-grid" id="pr-charts">${charts(vis)}</div>
    <section class="pr-sheet-card">
      <header class="pr-sheet-head"><div><h3>Planilha do relatório</h3><span>${E(meta.titulo || '')} · como veio da PGL${d.colunas.length !== (meta.colunas || d.colunas.length) ? ' (colunas de valor só para gestores)' : ''}</span></div>
        <div class="pr-tools">
          <label class="pr-search">${ICO.search}<input type="search" id="pr-q" placeholder="Buscar em todas as colunas…" value="${E(S.f.q)}"></label>
          <button type="button" class="pr-btn" id="pr-cols">${ICO.cols}Colunas</button>
          <button type="button" class="pr-btn" id="pr-xls">${ICO.xls}Exportar Excel</button>
          <button type="button" class="pr-btn ghost" id="pr-clear"${nFiltros() ? '' : ' disabled'}>${ICO.clear}Limpar filtros</button>
        </div></header>
      <div class="pr-chips" id="pr-chips">${chipsHtml(rows)}</div>
      <div class="pr-sheet" id="pr-sheet"></div>
      <div class="pr-sheet-foot" id="pr-foot"></div>
    </section>
    <p class="pr-foot">Fonte: e-mail "${E(meta.assunto || '')}" (PGL Brasil). Leitura automática pelo n8n de hora em hora, de segunda a sexta, das 7h às 20h. Clique num número, numa barra ou numa fatia para filtrar a planilha.</p>
  </div>`;
  bind();
  sheet(vis);
  animar();
}
function refresh() {
  const vis = filtrados();
  S.root.querySelector('#pr-kpis').innerHTML = kpis(vis);
  S.root.querySelector('#pr-charts').innerHTML = charts(vis);
  S.root.querySelector('#pr-chips').innerHTML = chipsHtml(S.dados.rows);
  const cl = S.root.querySelector('#pr-clear'); if (cl) cl.disabled = !nFiltros();
  sheet(vis);
}

/* ---------- KPIs ---------- */
function kpis(rows) {
  const h = hoje(), c = f => rows.filter(f).length;
  const ent = rows.filter(r => r.entrega && r.embarque && dias(r.entrega, h) <= 90 && dias(r.embarque, r.entrega) >= 0);
  const lt = ent.length ? ent.reduce((a, r) => a + dias(r.embarque, r.entrega), 0) / ent.length : null;
  const cn = rows.filter(r => r.canal), red = c(r => ['VERMELHO', 'AMARELO'].includes(r.canal));
  const k = (chip, ic, cor, label, v, sub, tip) => `<button type="button" class="pr-kpi${chip && S.f.chip === chip ? ' on' : ''}" data-chip="${chip}" style="--c:${cor}" title="${E(tip || '')}">
    <span class="ic">${ICO[ic]}</span><small>${label}</small><b data-n="${v == null ? '' : v}">${v == null ? '-' : nf(v)}</b><em>${sub}</em></button>`;
  return k('', 'box', '#e8f5ee', 'Processos no relatório', rows.length, `${nf(rows.reduce((a, r) => a + r.total, 0))} unidades`) +
    k('transito', 'ship', FASES.transito.c, 'Em trânsito', c(r => r.fase === 'transito'), 'embarcou, ainda não chegou', FASES.transito.d) +
    k('no_brasil', 'port', FASES.no_brasil.c, 'Aguardando desembaraço', c(r => r.fase === 'no_brasil'), 'já no Brasil', FASES.no_brasil.d) +
    k('desembaracado', 'truck', FASES.desembaracado.c, 'Aguardando entrega', c(r => r.fase === 'desembaracado'), 'falta entregar no CD', FASES.desembaracado.d) +
    k('entregue30', 'ok', FASES.entregue.c, 'Entregues em 30 dias', c(r => r.entrega && dias(r.entrega, h) <= 30), `${nf(c(r => r.fase === 'entregue'))} no relatório`) +
    k('atraso', 'late', '#ff8a5c', 'Previsão vencida', c(r => r.atraso), 'previsão já passou', 'Sem entrega e com a previsão de entrega (ou de chegada, se ainda não chegou) anterior a hoje') +
    k('vermelho', 'red', CANAL.VERMELHO, 'Canal vermelho ou amarelo', red, cn.length ? `${nf(red / cn.length * 100, 1)}% das DIs` : 'sem DI registrada') +
    `<div class="pr-kpi lead" title="Média, nos processos entregues nos últimos 90 dias, entre o embarque na origem e a entrega no CD"><span class="ic">${ICO.clock}</span><small>Embarque até a entrega</small><b>${lt == null ? '-' : nf(lt, 1)}<i> dias</i></b><em>média de 90 dias (${nf(ent.length)})</em></div>`;
}
function chipsHtml(rows) {
  const n = k => k === '' ? rows.length : rows.filter(r => FASES[k] ? r.fase === k : k === 'atraso' ? r.atraso : k === 'vermelho' ? ['VERMELHO', 'AMARELO'].includes(r.canal) : (r.entrega && dias(r.entrega, hoje()) <= 30)).length;
  return Object.entries(CHIPS).map(([k, l]) => `<button type="button" class="pr-chip${S.f.chip === k ? ' on' : ''}" data-chip="${k}"${FASES[k] ? ` style="--c:${FASES[k].c}"` : ''}>${E(l)}<b>${nf(n(k))}</b></button>`).join('') +
    Object.entries(S.f.col).filter(([, v]) => v).map(([c, v]) => `<span class="pr-colf">${E(c)}: <b>${E(v.replace(/^=/, ''))}</b><button type="button" data-unf="${E(c)}" aria-label="Tirar filtro">×</button></span>`).join('');
}

/* ---------- gráficos ---------- */
function card(t, sub, body, cls = '') { return `<section class="pr-card ${cls}"><header><h3>${t}</h3><span>${sub}</span></header>${body}</section>`; }
function charts(rows) {
  if (!rows.length) return card('Sem processos no filtro', 'Limpe os filtros para ver os gráficos', '<div class="pr-none">Nada para mostrar.</div>', 'wide');
  return card('Onde estão os processos', 'Situação informada pela PGL (coluna STATUS), na ordem das etapas · clique para filtrar', pipeline(rows), 'wide') +
    card('Tempo médio em cada etapa', 'Processos entregues nos últimos 120 dias, em dias, por modal', etapas(rows)) +
    card('Entregas no CD por semana', 'Últimas 10 semanas e previsão das próximas 2', semanas(rows)) +
    card('Canal de parametrização', 'DIs registradas · clique para filtrar', donut(rows)) +
    card('Próximas entregas previstas', 'Sem entrega e com previsão nos próximos 7 dias', proximas(rows)) +
    card('Por armazém de descarga', 'Processos ainda não entregues · clique para filtrar', barras(rows.filter(r => r.fase !== 'entregue'), r => r.armazem, S.dados.ci['ARMAZEM DESCARGA'] !== undefined ? 'ARMAZEM DESCARGA' : 'ARMAZEM ATRACACAO')) +
    terceiro(rows.filter(r => r.fase !== 'entregue'));
}
// 3º gráfico da linha: a 1ª coluna com dados entre agente de carga, transportadora e armazém de atracação (o FUP da SBF
// vem sem o agente de carga)
function terceiro(rows) {
  const ops = [['AGENTE CARGA', 'Por agente de carga'], ['TRANSPORTADORA', 'Por transportadora'], ['ARMAZEM ATRACACAO', 'Por armazém de atracação'],
               ['NAVIO', 'Por navio'], ['MODAL', 'Por modal']];
  const d = S.dados, nv = c => d.ci[c] === undefined ? 0 : new Set(rows.map(r => d.linhas[r.i][d.ci[c]]).filter(Boolean)).size;
  const [col, tit] = ops.find(([c]) => nv(c) > 1) || ops.find(([c]) => nv(c) > 0) || ops[0];
  return card(tit, 'Processos ainda não entregues · clique para filtrar', barras(rows, r => d.ci[col] === undefined ? '' : d.linhas[r.i][d.ci[col]], col));
}
function pipeline(rows) {
  const m = new Map();
  rows.forEach(r => { const k = r.sn + '|' + r.sl; const o = m.get(k) || {n: r.sn, l: r.sl, v: 0, fase: r.fase, raw: r.status}; o.v++; m.set(k, o); });
  const it = [...m.values()].sort((a, b) => a.n - b.n), max = Math.max(...it.map(i => i.v), 1);
  return `<div class="pr-pipe">${it.map((i, k) => `<button type="button" class="pr-pipe-i" data-colf="STATUS" data-v="${E(i.raw)}" style="--k:${k};--c:${(FASES[i.fase] || FASES.transito).c}" title="${E(i.l)}: ${nf(i.v)} processo(s) · clique para filtrar">
    <span class="n">${i.n < 99 ? String(i.n).padStart(2, '0') : '-'}</span><span class="l">${E(i.l || 'Sem situação')}</span>
    <span class="b"><i style="width:${Math.max(2, i.v / max * 100).toFixed(1)}%"></i></span><b>${nf(i.v)}</b></button>`).join('')}</div>
    <div class="pr-legend">${Object.values(FASES).map(f => `<span><i style="background:${f.c}"></i>${f.l}</span>`).join('')}</div>`;
}
function etapas(rows) {
  const h = hoje();
  const segs = [['Trânsito internacional', 'embarque', 'chegada', '#38bdf8'], ['Chegada até o registro da DI', 'chegada', 'registro', '#f4b740'],
                ['Registro até o desembaraço', 'registro', 'desemb', '#e98bd0'], ['Desembaraço até a entrega no CD', 'desemb', 'entrega', '#3ee08f']];
  const modais = [...new Set(rows.map(r => r.modal).filter(Boolean))].sort();
  const linhas = modais.map(mo => {
    const rs = rows.filter(r => r.modal === mo && r.entrega && dias(r.entrega, h) <= 120);
    const med = segs.map(([, a, b]) => { const v = rs.filter(r => r[a] && r[b] && dias(r[a], r[b]) >= 0).map(r => dias(r[a], r[b])); return v.length ? v.reduce((x, y) => x + y, 0) / v.length : 0; });
    return {mo, n: rs.length, med, tot: med.reduce((x, y) => x + y, 0)};
  }).filter(x => x.n);
  if (!linhas.length) return '<div class="pr-none">Sem processos entregues nos últimos 120 dias.</div>';
  const max = Math.max(...linhas.map(x => x.tot), 1);
  return `<div class="pr-steps">${linhas.map((x, k) => `<div class="pr-step"><div class="t"><b>${E(x.mo.charAt(0) + x.mo.slice(1).toLowerCase())}</b><small>${nf(x.n)} entregues · ${nf(x.tot, 1)} dias no total</small></div>
      <div class="bar">${x.med.map((v, j) => v ? `<i style="--k:${k * 4 + j};width:${(v / max * 100).toFixed(2)}%;background:${segs[j][3]}" title="${E(segs[j][0])}: ${nf(v, 1)} dias">${v / max > .07 ? nf(v, 1) : ''}</i>` : '').join('')}</div></div>`).join('')}</div>
    <div class="pr-legend">${segs.map(s => `<span><i style="background:${s[3]}"></i>${s[0]}</span>`).join('')}</div>`;
}
function semanas(rows) {
  const h = hoje(), seg = iso => { const d = new Date(iso + 'T12:00:00Z'); const w = (d.getUTCDay() + 6) % 7; return addDias(iso, -w); };
  const ini = seg(h), ks = []; for (let i = -9; i <= 2; i++) ks.push(addDias(ini, i * 7));
  const real = new Map(), prev = new Map();
  rows.forEach(r => { if (r.entrega) { const k = seg(r.entrega); real.set(k, (real.get(k) || 0) + 1); } else if (r.prev_entrega && r.prev_entrega >= addDias(ini, 0)) { const k = seg(r.prev_entrega); prev.set(k, (prev.get(k) || 0) + 1); } });
  const val = k => k < ini ? (real.get(k) || 0) : (real.get(k) || 0) + (prev.get(k) || 0);
  const max = Math.max(...ks.map(val), 1);
  return `<div class="pr-cols">${ks.map((k, i) => { const fut = k > ini, cur = k === ini, r = real.get(k) || 0, p = k >= ini ? (prev.get(k) || 0) : 0;
    return `<div class="pr-col${cur ? ' cur' : ''}" title="Semana de ${brd(k)}: ${nf(r)} entregue(s)${p ? `, ${nf(p)} prevista(s)` : ''}"><b>${nf(r + p)}</b>
      <div class="bars"><i class="p" style="--k:${i};height:${(p / max * 100).toFixed(1)}%"></i><i class="r" style="--k:${i};height:${(r / max * 100).toFixed(1)}%"></i></div>
      <small>${brd(k).slice(0, 5)}${cur ? '<em>esta</em>' : fut ? '<em>prev.</em>' : ''}</small></div>`; }).join('')}</div>
    <div class="pr-legend"><span><i style="background:#3ee08f"></i>Entregues</span><span><i class="hatch"></i>Previstas (sem entrega ainda)</span></div>`;
}
function donut(rows) {
  const m = new Map(); rows.forEach(r => { if (r.canal) m.set(r.canal, (m.get(r.canal) || 0) + 1); });
  const it = [...m.entries()].sort((a, b) => b[1] - a[1]);
  if (!it.length) return '<div class="pr-none">Nenhuma DI registrada no filtro.</div>';
  const tot = it.reduce((a, [, v]) => a + v, 0), R = 64, C = 2 * Math.PI * R; let acc = 0;
  const segs = it.map(([k, v], i) => { const len = Math.max(0, v / tot * C - (it.length > 1 ? 3 : 0)), off = -acc; acc += v / tot * C;
    return `<circle class="pr-seg" data-colf="CANAL" data-v="=${E(k)}" cx="90" cy="90" r="${R}" fill="none" stroke="${CANAL[k] || '#8a9aa3'}" stroke-width="26" stroke-dasharray="${len.toFixed(2)} ${(C - len).toFixed(2)}" stroke-dashoffset="${off.toFixed(2)}" transform="rotate(-90 90 90)" style="--k:${i};--len:${len.toFixed(2)}"><title>${E(k)}: ${nf(v)} (${nf(v / tot * 100, 1)}%)</title></circle>`; }).join('');
  return `<div class="pr-donut"><svg viewBox="0 0 180 180" role="img" aria-label="Canal de parametrização"><circle cx="90" cy="90" r="${R}" fill="none" stroke="#ffffff14" stroke-width="26"/>${segs}
    <text x="90" y="88" text-anchor="middle" class="dv">${nf(tot)}</text><text x="90" y="106" text-anchor="middle" class="dl">DIs</text></svg>
    <ul>${it.map(([k, v]) => `<li data-colf="CANAL" data-v="=${E(k)}"><i style="background:${CANAL[k] || '#8a9aa3'}"></i><span>${E(k.charAt(0) + k.slice(1).toLowerCase())}</span><b>${nf(v)}</b><small>${nf(v / tot * 100, 1)}%</small></li>`).join('')}</ul></div>`;
}
function proximas(rows) {
  const h = hoje(), ate = addDias(h, 7);
  const it = rows.filter(r => !r.entrega && r.prev_entrega && r.prev_entrega >= h && r.prev_entrega <= ate).sort((a, b) => a.prev_entrega.localeCompare(b.prev_entrega));
  if (!it.length) return '<div class="pr-none">Nenhuma entrega prevista para os próximos 7 dias.</div>';
  return `<ul class="pr-next">${it.slice(0, 9).map(r => `<li data-colf="${S.dados.ci.CONHECIMENTO !== undefined ? 'CONHECIMENTO' : 'PROCESSO'}" data-v="=${E(S.dados.ci.CONHECIMENTO !== undefined ? r.conh : r.proc)}">
      <span class="d"><b>${brd(r.prev_entrega).slice(0, 5)}</b><small>${['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'][new Date(r.prev_entrega + 'T12:00:00Z').getUTCDay()]}</small></span>
      <span class="t"><b>${E(r.conh || r.proc)}</b><small>${E([r.modal && r.modal.charAt(0) + r.modal.slice(1).toLowerCase(), r.cd, r.sl].filter(Boolean).join(' · '))}</small></span>
      <span class="q">${r.total ? nf(r.total) + ' un.' : ''}</span></li>`).join('')}</ul>${it.length > 9 ? `<p class="pr-more">+ ${nf(it.length - 9)} outra(s) prevista(s) na semana</p>` : ''}`;
}
function barras(rows, fn, col) {
  const m = new Map(); rows.forEach(r => { const v = fn(r); if (v) m.set(v, (m.get(v) || 0) + 1); });
  const it = [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
  if (!it.length) return '<div class="pr-none">Sem dados no filtro.</div>';
  const max = it[0][1];
  return `<div class="pr-hbars">${it.map(([l, v], k) => `<button type="button" class="pr-hb" data-colf="${E(col)}" data-v="=${E(l)}" style="--k:${k}" title="${E(l)}: ${nf(v)}">
    <span class="l">${E(l)}</span><span class="b"><i style="width:${Math.max(2, v / max * 100).toFixed(1)}%"></i></span><b>${nf(v)}</b></button>`).join('')}</div>`;
}
function animar() {
  if (!animOn() || S.anim.has(S.tipo)) return;
  S.anim.add(S.tipo);
  const r0 = S.root.querySelector('.pr-wrap'); r0.classList.add('pr-anim');
  r0.querySelectorAll('.pr-kpi b[data-n]').forEach(b => { const n = +b.dataset.n; if (!n) return; const t0 = performance.now();
    const tick = t => { const p = Math.min(1, (t - t0) / 900); b.textContent = nf(Math.round(n * (1 - Math.pow(1 - p, 3)))); if (p < 1) requestAnimationFrame(tick); }; requestAnimationFrame(tick); });
  setTimeout(() => r0.classList.remove('pr-anim'), 1800);
}

/* ---------- planilha (desenha só as linhas visíveis) ---------- */
function largura(c, j) {
  const amostra = S.dados.linhas.slice(0, 400).map(l => cell(l[j]).length);
  const t = Math.max(c.length * .82, ...amostra.sort((a, b) => b - a).slice(5, 6), 4);
  return Math.round(Math.min(300, Math.max(78, t * 7.6 + 26)));
}
function sheet(vis) {
  const box = S.root.querySelector('#pr-sheet'); if (!box) return;
  const d = S.dados, cols = d.colunas.map((c, j) => ({c, j})).filter(x => !S.colsOff[x.c]);
  d.w = d.w || {}; cols.forEach(x => { if (!d.w[x.c]) d.w[x.c] = largura(x.c, x.j); });
  const fixas = cols.slice(0, 2).map(x => x.c);  // MODAL e PROCESSO (ou as 2 primeiras visíveis) ficam presas à esquerda
  let left = 46; const pos = {}; fixas.forEach(c => { pos[c] = left; left += d.w[c]; });
  const tw = 46 + cols.reduce((a, x) => a + d.w[x.c], 0);
  const th = cols.map(x => { const s = S.sort && S.sort.c === x.c ? (S.sort.d > 0 ? ' ▲' : ' ▼') : '';
    return `<div class="th${pos[x.c] != null ? ' fix' : ''}" style="width:${d.w[x.c]}px${pos[x.c] != null ? `;left:${pos[x.c]}px` : ''}" data-sort="${E(x.c)}" title="Ordenar por ${E(x.c)}">${E(x.c)}<span>${s}</span></div>`; }).join('');
  const tf = cols.map(x => `<div class="tf${pos[x.c] != null ? ' fix' : ''}" style="width:${d.w[x.c]}px${pos[x.c] != null ? `;left:${pos[x.c]}px` : ''}"><input data-f="${E(x.c)}" value="${E((S.f.col[x.c] || '').replace(/^=/, ''))}" placeholder="filtrar" aria-label="Filtrar ${E(x.c)}"></div>`).join('');
  box.innerHTML = `<div class="pr-scroll" id="pr-scroll"><div class="pr-table" style="width:${tw}px">
    <div class="pr-hrow"><div class="th rn fix" style="left:0">#</div>${th}</div>
    <div class="pr-frow"><div class="tf rn fix" style="left:0">${ICO.search}</div>${tf}</div>
    <div class="pr-body" style="height:${vis.length * RH}px"></div></div>
    ${vis.length ? '' : '<div class="pr-none in">Nenhum processo com esses filtros.</div>'}</div>`;
  const sc = box.querySelector('#pr-scroll'), body = box.querySelector('.pr-body');
  const draw = () => {
    const top = Math.max(0, Math.floor((sc.scrollTop - 64) / RH) - 12), fim = Math.min(vis.length, top + Math.ceil(sc.clientHeight / RH) + 26);
    let h = '';
    for (let k = top; k < fim; k++) {
      const r = vis[k], lin = d.linhas[r.i], pid = (d.embarques || [])[r.i];
      h += `<div class="pr-row${k % 2 ? ' z' : ''}" style="top:${k * RH}px"><div class="td rn fix" style="left:0">${r.i + 1}</div>${cols.map(x => {
        const v = lin[x.j], fx = pos[x.c] != null ? ` fix" style="width:${d.w[x.c]}px;left:${pos[x.c]}px` : `" style="width:${d.w[x.c]}px`;
        return `<div class="td${typeof v === 'number' ? ' n' : ''}${fx}" title="${E(cell(v))}">${fmt(x.c, v, pid, r)}</div>`; }).join('')}</div>`;
    }
    body.innerHTML = h;
  };
  // O navegador já entrega a rolagem uma vez por quadro: desenha na hora (sem esperar o próximo quadro, que pode atrasar)
  let ultimo = -1;
  sc.addEventListener('scroll', () => { S.scrollTop = sc.scrollTop; const k = Math.floor(sc.scrollTop / RH); if (k !== ultimo) { ultimo = k; draw(); } }, {passive: true});
  sc.scrollTop = Math.min(S.scrollTop, Math.max(0, vis.length * RH - 200));
  draw();
  S.vis = vis;
  const foot = S.root.querySelector('#pr-foot');
  foot.innerHTML = `<span><b>${nf(vis.length)}</b> de ${nf(d.linhas.length)} processos · ${nf(cols.length)} de ${nf(d.colunas.length)} colunas</span><span>Clique no título da coluna para ordenar; digite na linha "filtrar" para filtrar a coluna.</span>`;
  box.querySelectorAll('[data-sort]').forEach(h => h.addEventListener('click', () => {
    const c = h.dataset.sort; S.sort = !S.sort || S.sort.c !== c ? {c, d: 1} : S.sort.d > 0 ? {c, d: -1} : null; sheet(filtrados()); }));
  let t;
  box.querySelectorAll('input[data-f]').forEach(inp => inp.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => {
    S.f.col[inp.dataset.f] = inp.value.trim(); S.scrollTop = 0; refreshKeep(inp.dataset.f); }, 260); }));
  box.querySelector('.pr-body').addEventListener('click', e => { const a = e.target.closest('[data-emb]'); if (!a) return; e.preventDefault();
    if (typeof showPage === 'function') showPage('embarques'); setTimeout(() => window.nexusEmb && window.nexusEmb.ficha(a.dataset.emb), 60); });
}
// Filtro digitado na planilha: refaz tudo e devolve o cursor ao mesmo campo
function refreshKeep(col) {
  refresh();
  const inp = S.root.querySelector(`input[data-f="${CSS.escape(col)}"]`); if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
}
function fmt(c, v, pid, r) {
  if (v == null || v === '') return '';
  if (c === 'STATUS') return `<span class="pr-st" style="--c:${FASES[r.fase].c}">${E(v)}</span>`;
  if (c === 'CANAL') return `<span class="pr-cn"><i style="background:${CANAL[String(v).toUpperCase()] || '#8a9aa3'}"></i>${E(v)}</span>`;
  if ((c === 'CONHECIMENTO' || c === 'REF CLIENTE') && pid) return `<a href="#" class="pr-emb" data-emb="${E(pid)}" title="Abrir a ficha deste processo na página Embarques">${E(v)}${ICO.link}</a>`;
  if (typeof v === 'number') return /VALOR|CIF|FOB|PESO|CUBAGEM|MEDIA|KG/i.test(c) ? nf(v, Number.isInteger(v) ? 0 : 2) : /KM|TOTAL|VESTUARIO|CALCADO|EQUIPAMENTO/i.test(c) ? nf(v) : E(v);
  return E(cell(v));
}

/* ---------- eventos ---------- */
function bind() {
  const r0 = S.root;
  r0.querySelectorAll('.pr-tab[data-tipo]').forEach(b => b.addEventListener('click', async () => {
    if (b.dataset.tipo === S.tipo) return; S.tipo = b.dataset.tipo; LSset('nexus.pgl.rel.tipo', S.tipo); S.scrollTop = 0;
    b.classList.add('loading');
    try { await loadTipo(S.tipo); } catch (e) { toast(e.message); return; }
    render();
  }));
  r0.querySelector('#pr-chips').addEventListener('click', e => {
    const u = e.target.closest('[data-unf]'); if (u) { delete S.f.col[u.dataset.unf]; S.scrollTop = 0; refresh(); return; }
    const c = e.target.closest('[data-chip]'); if (c) { S.f.chip = S.f.chip === c.dataset.chip ? '' : c.dataset.chip; S.scrollTop = 0; refresh(); }
  });
  r0.querySelector('#pr-kpis').addEventListener('click', e => { const c = e.target.closest('[data-chip]'); if (!c) return;
    S.f.chip = S.f.chip === c.dataset.chip ? '' : c.dataset.chip; S.scrollTop = 0; refresh(); r0.querySelector('.pr-sheet-card').scrollIntoView({behavior: 'smooth', block: 'start'}); });
  let t;
  const q = r0.querySelector('#pr-q');
  q.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => { S.f.q = q.value; S.scrollTop = 0; refresh(); const n = S.root.querySelector('#pr-q'); n.focus(); }, 260); });
  r0.querySelector('#pr-clear').addEventListener('click', () => { S.f = {tipo: S.tipo, q: '', fase: '', col: {}, chip: ''}; S.sort = null; S.scrollTop = 0; render(); });
  r0.querySelector('#pr-cols').addEventListener('click', e => colsMenu(e.currentTarget));
  r0.querySelector('#pr-xls').addEventListener('click', exportar);
  r0.querySelector('#pr-charts').addEventListener('click', onChart);  // o quadro fica; só o conteúdo é refeito
}
// Clique num gráfico = filtro exato daquela coluna (clicar de novo desfaz)
function onChart(e) {
  const b = e.target.closest('[data-colf]'); if (!b) return;
  const c = b.dataset.colf, v = b.dataset.v.startsWith('=') ? b.dataset.v : '=' + b.dataset.v;
  S.f.col[c] = S.f.col[c] === v ? '' : v;
  S.scrollTop = 0; refresh();
}
function colsMenu(btn) {
  document.getElementById('pr-colmenu')?.remove();
  const m = document.createElement('div'); m.id = 'pr-colmenu'; m.className = 'pr-colmenu'; m.setAttribute('role', 'dialog');
  m.innerHTML = `<header><b>Colunas visíveis</b><button type="button" data-all="1">Todas</button><button type="button" data-all="0">Só as principais</button></header>
    <div class="lst">${S.dados.colunas.map(c => `<label><input type="checkbox" data-c="${E(c)}"${S.colsOff[c] ? '' : ' checked'}><span>${E(c)}</span></label>`).join('')}</div>`;
  document.body.appendChild(m);
  const r = btn.getBoundingClientRect(); m.style.top = (r.bottom + window.scrollY + 6) + 'px'; m.style.left = Math.max(12, r.right + window.scrollX - 320) + 'px';
  const PRINC = ['MODAL', 'PROCESSO', 'AGENTE CARGA', 'REF CLIENTE', 'CONHECIMENTO', 'TOTAL', 'EMBARQUE NA ORIGEM', 'PREVISAO_CHEGADA', 'CHEGADA MERCADORIA',
    'PRESENCA CARGA', 'REGISTRO DI', 'NR_DI', 'CANAL', 'DESEMBARACO', 'PREVISAO ENTR MERC_FAB', 'ENTREGA DA MERC', 'STATUS', 'ARMAZEM DESCARGA', 'ARMAZEM DESCARGA TMS'];
  const salvar = () => { LSset('nexus.pgl.rel.cols.' + S.tipo, S.colsOff); sheet(filtrados()); };
  m.addEventListener('change', e => { const c = e.target.dataset.c; if (!c) return; if (e.target.checked) delete S.colsOff[c]; else S.colsOff[c] = 1; salvar(); });
  m.querySelectorAll('[data-all]').forEach(b => b.addEventListener('click', () => {
    S.colsOff = b.dataset.all === '1' ? {} : Object.fromEntries(S.dados.colunas.filter(c => !PRINC.includes(c)).map(c => [c, 1]));
    m.querySelectorAll('input[data-c]').forEach(i => { i.checked = !S.colsOff[i.dataset.c]; }); salvar(); }));
  const fora = e => { if (!m.contains(e.target) && e.target !== btn) { m.remove(); document.removeEventListener('mousedown', fora, true); } };
  setTimeout(() => document.addEventListener('mousedown', fora, true), 0);
}
async function exportar(e) {
  const btn = e.currentTarget; btn.disabled = true;
  try {
    const cols = S.dados.colunas.filter(c => !S.colsOff[c]);
    const res = await fetch('/api/pgl/relatorios/' + encodeURIComponent(S.tipo) + '/excel', {method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({linhas: (S.vis || []).map(r => r.i), colunas: cols})});
    if (!res.ok) { let m = 'Erro ' + res.status; try { m = (await res.json()).detail || m; } catch (x) { /* resposta sem JSON */ } throw new Error(m); }
    const blob = await res.blob(), a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = (res.headers.get('Content-Disposition') || '').match(/filename="([^"]+)"/)?.[1] || 'PGL.xlsx';
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  } catch (err) { toast(err.message); }
  finally { btn.disabled = false; }
}
return {mount, _estado: () => S};
})();
