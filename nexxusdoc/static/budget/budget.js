/* Pagina Budget (master e owners): orcamento Inbound a partir de planilhas, com versoes, premissas editaveis
   (recalculo na hora pelo servidor), alertas e download no MODELO. Graficos em SVG proprio. */
(() => {
'use strict';
const S = {home: null, cur: null, data: null, tab: 'painel', draft: null, sim: null, simTimer: 0, filter: 'todos',
           open: new Set(['bunker', 'afrmm', 'despachante', 'sistemas', 'rodoviario']), cache: {}, cmp: {a: '', b: ''}, busy: false,
           view: (() => { try { return localStorage.getItem('nexus.budget.vista') || 'orcamento'; } catch { return 'orcamento'; } })()};
const root = () => document.getElementById('page-budget');
const E = s => (typeof esc === 'function' ? esc(s) : String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c])));
const nf = (v, d = 0) => (Number.isFinite(v) ? v : 0).toLocaleString('pt-BR', {minimumFractionDigits: d, maximumFractionDigits: d});
const mi = (v, d = 1) => `R$ ${nf(v / 1e6, d)} mi`;
const auto = v => { const a = Math.abs(v || 0); if (a < 0.5) return '–'; if (a >= 999500) return `R$ ${nf(v / 1e6, 2)} mi`; if (a >= 500) return `R$ ${nf(v / 1e3, 1)} mil`; return `R$ ${nf(v, 2)}`; };
const sig = (v, f) => (v > 0 ? '+' : v < 0 ? '-' : '') + f(Math.abs(v));
const pct = (v, d = 1) => `${nf((v || 0) * 100, d)}%`;
const spct = (v, d = 1) => sig(v || 0, x => pct(x, d));
const svgI = p => `<svg viewBox="0 0 24 24" aria-hidden="true">${p}</svg>`;
const IC = {
  up: svgI('<path d="M12 15V4m0 0-4 4m4-4 4 4"/><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>'),
  down: svgI('<path d="M12 4v11m0 0-4-4m4 4 4-4"/><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>'),
  file: svgI('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>'),
  chart: svgI('<path d="M4 20V10m6 10V4m6 16v-7m4 7H3"/>'),
  table: svgI('<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17M3.5 14.5h17M9.5 9.5v10"/>'),
  scale: svgI('<path d="M12 4v16M6 8h12M6 8l-3 6a3 3 0 0 0 6 0zm12 0-3 6a3 3 0 0 0 6 0z"/>'),
  sliders: svgI('<path d="M4 7h8m4 0h4M4 17h3m4 0h9M4 12h5m4 0h7"/><circle cx="14" cy="7" r="2"/><circle cx="9" cy="17" r="2"/><circle cx="11" cy="12" r="2"/>'),
  alert: svgI('<path d="M12 4 2.8 19.5h18.4z"/><path d="M12 10v4.5m0 2.5h.01"/>'),
  hist: svgI('<path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1L3.5 8.5"/><path d="M3.5 4v4.5H8M12 8v4.5l3 2"/>'),
  check: svgI('<path d="m5 12.5 4.5 4.5L19 7.5"/>'),
  info: svgI('<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5m0-8h.01"/>'),
  model: svgI('<rect x="4" y="3.5" width="16" height="17" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>'),
};
const SEV_IC = {Alta: IC.alert, 'Média': IC.info, Baixa: IC.info};
const res = () => (S.sim && S.sim.resultado) || (S.data && S.data.resultado);

/* ---------------- dados ---------------- */
async function loadHome(keepCur) {
  S.home = await api('/api/budget');
  const ids = S.home.versoes.map(v => v.id);
  let want = keepCur && ids.includes(S.cur) ? S.cur : null;
  if (!want) { try { want = localStorage.getItem('nexus.budget.versao'); } catch {} }
  if (!ids.includes(want)) want = ids[0] || null;
  if (want) await loadVersion(want, false); else { S.cur = null; S.data = null; }
}
async function loadVersion(id, draw = true) {
  S.cur = id; S.sim = null; S.draft = null;
  try { localStorage.setItem('nexus.budget.versao', id); } catch {}
  S.data = S.cache[id] || await api(`/api/budget/versoes/${id}`);
  S.cache[id] = S.data;
  S.draft = JSON.parse(JSON.stringify(S.data.params));
  if (draw) render();
}
const allowed = () => typeof state !== 'undefined' && ['master', 'owner'].includes(state.user?.role);
function lockedHtml() {
  return `<div class="bg-hero"><div><div class="eyebrow">ORÇAMENTO INBOUND · FISIA · LOGÍSTICA INTERNACIONAL</div><h1>Budget</h1>
    <p>Orçamento Inbound montado a partir da planilha, com cenários, alertas e o modelo oficial em Excel.</p></div></div>
    <div class="bg-empty bg-locked"><div><h2>${svgI('<rect x="5" y="11" width="14" height="9.5" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>')}Acesso restrito aos números</h2>
      <p>Os valores do orçamento, as premissas e as versões ficam disponíveis só para o administrador master e os owners das áreas. Se você precisa consultar ou ajustar o Budget, peça ao owner da sua área.</p></div>
      <div class="bg-locked-list"><div>${IC.chart}<span><b>Painel</b>custo total, H1 e H2, composição e comparação com o ano anterior</span></div>
        <div>${IC.sliders}<span><b>Premissas</b>câmbio, tarifas, volumes e reajustes, com recálculo na hora</span></div>
        <div>${IC.down}<span><b>Excel</b>planilha MODELO com gráficos e filtro Orçamento, Budget e Forecast</span></div></div></div>`;
}
async function open() {
  const r = root(); if (!r) return;
  if (!allowed()) { r.innerHTML = lockedHtml(); return; }
  if (!S.home) {
    r.innerHTML = '<div class="bg-loading">Carregando o Budget…</div>';
    try { await loadHome(); } catch (e) { r.innerHTML = `<div class="notice error"><div class="grow">${E(e.message)}</div></div>`; return; }
  }
  render();
}

/* ---------------- tela ---------------- */
function render() {
  const r = root(); if (!r) return;
  if (!S.home.versoes.length) { r.innerHTML = emptyHtml(); bindEmpty(); return; }
  const v = S.data.versao, ano = S.data.params.ano;
  const opts = S.home.versoes.map(x => `<option value="${x.id}"${x.id === S.cur ? ' selected' : ''}>${E(x.ciclo)} · ${E(x.nome)} · ${new Date(x.criado_em).toLocaleDateString('pt-BR')}</option>`).join('');
  const al = S.data.alertas || [], altas = al.filter(a => a.sev === 'Alta').length;
  r.innerHTML = `
  <div class="bg-hero">
    <div><div class="eyebrow">ORÇAMENTO INBOUND · FISIA · LOGÍSTICA INTERNACIONAL</div>
      <h1>Budget ${E(ano)}</h1>
      <p><b>${E(v.nome)}</b> · ${E(v.ciclo)} · ${originLabel(v)} por ${E(v.criado_por_nome || v.criado_por)} em ${new Date(v.criado_em).toLocaleString('pt-BR')}</p></div>
    <div class="bg-actions">
      <select id="bg-version" aria-label="Versão do orçamento">${opts}</select>
      <a class="secondary" href="/api/budget/versoes/${S.cur}/excel" download title="Baixar a planilha MODELO com as premissas desta versão (abre e recalcula no Excel)">${IC.down}Baixar Excel</a>
      <button class="primary" type="button" id="bg-upload">${IC.up}Enviar planilha</button>
    </div>
  </div>
  <div id="bg-kpis">${kpisHtml()}</div>
  <nav class="bg-tabs" role="tablist">
    ${tab('painel', IC.chart, 'Painel')}${tab('mensal', IC.table, 'Resumo mensal')}${tab('comparativo', IC.scale, `Comparativo ${ano - 1}`)}
    ${tab('premissas', IC.sliders, 'Premissas')}${tab('alertas', IC.alert, `Alertas <span class="bg-count${altas ? '' : ' zero'}">${al.length}</span>`)}
    ${tab('historico', IC.hist, 'Histórico de versões')}
  </nav>
  <div id="bg-body"></div>`;
  r.querySelector('#bg-version').onchange = e => loadVersion(e.target.value);
  r.querySelector('#bg-upload').onclick = () => uploadModal();
  r.querySelectorAll('[data-bgtab]').forEach(b => b.onclick = () => { S.tab = b.dataset.bgtab; render(); });
  body();
}
const tab = (k, ic, label) => `<button type="button" role="tab" data-bgtab="${k}" class="${S.tab === k ? 'on' : ''}">${ic}${label}</button>`;
function originLabel(v) {
  return {upload: v.formato === 'modelo' ? 'Planilha MODELO enviada' : v.formato === 'generico' ? 'Planilha fora do modelo enviada' : 'Planilha FISIA enviada',
          edicao: 'Premissas ajustadas no sistema', modelo: 'Modelo aprovado carregado'}[v.origem] || 'Versão';
}
function kpisHtml() {
  const k = res().kpi, ano = S.data.params.ano, simTag = S.sim ? ' <span class="bg-chip edicao">simulação</span>' : '';
  const d = (v, f, inv) => `<span class="bg-delta ${v > 0 ? 'up' : v < 0 ? 'down' : ''}">${v > 0 ? '▲' : v < 0 ? '▼' : ''} ${f}</span>`;
  return `<div class="bg-kpis">
    <div class="bg-kpi main"><small>Custo total ${ano}${simTag}</small><strong>${mi(k.total)}</strong>${d(k.var_forecast_pct, `${spct(k.var_forecast_pct)} vs Forecast ${ano - 1}`)}</div>
    <div class="bg-kpi"><small>1º semestre (H1)</small><strong>${mi(k.h1)}</strong><span>${pct(k.pct_h1, 0)} do ano · jan–jun</span><div class="bg-split"><i style="width:${(k.pct_h1 * 100).toFixed(1)}%"></i></div></div>
    <div class="bg-kpi"><small>2º semestre (H2)</small><strong>${mi(k.h2)}</strong><span>${pct(1 - k.pct_h1, 0)} do ano · jul–dez</span></div>
    <div class="bg-kpi"><small>vs Forecast ${ano - 1}</small><strong>${sig(k.var_forecast, x => mi(x))}</strong><span>Fcst ${String(ano - 1).slice(2)}: ${mi(k.forecast_anterior)}</span></div>
    <div class="bg-kpi"><small>Custo por unit</small><strong>R$ ${nf(k.custo_unit, 2)}</strong>${d(k.var_cpu_forecast_pct, `${spct(k.var_cpu_forecast_pct)} vs Fcst ${String(ano - 1).slice(2)}`)}</div>
    <div class="bg-kpi"><small>Contêineres</small><strong>${nf(k.conteineres)}</strong><span>${nf(k.units / 1e6, 1)} mi units · R$ ${nf(k.custo_cntr)} por contêiner</span></div>
  </div>`;
}
function body() {
  const b = document.getElementById('bg-body');
  b.innerHTML = {painel: painelHtml, mensal: mensalHtml, comparativo: compHtml, premissas: premHtml, alertas: alertHtml, historico: histHtml}[S.tab]();
  ({premissas: bindPrem, mensal: bindMensal, alertas: bindAlert, historico: bindHist})[S.tab]?.();
}

/* ---------------- graficos ---------------- */
function niceStep(v) { if (v <= 0) return 1; const p = Math.pow(10, Math.floor(Math.log10(v))); const n = v / p; return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p; }
function niceMax(v, n = 4) { const st = niceStep(v / n); return Math.ceil(v / st) * st; }
function ticks(max, n = 4) { const st = niceStep(max / n), out = []; for (let v = 0; v <= max + st / 2; v += st) out.push(v); return out; }
const tickTxt = (v, st) => nf(v, st % 1 ? (st % 0.5 ? 2 : 1) : 0);
const tipAttr = html => ` data-bgtip="${E(html)}"`;
function chartMonthly(r) {
  const W = 1000, H = 270, L = 54, B = 30, T = 26, vals = r.mensal.total, max = niceMax(Math.max(...vals) * 1.1);
  const pw = (W - L - 10) / 12, bw = pw * 0.62, y = v => H - B - (v / max) * (H - B - T), tk = ticks(max), st = (tk[1] || max) / 1e6;
  let g = '';
  tk.forEach(v => { const yy = y(v); g += `<line x1="${L}" x2="${W - 10}" y1="${yy}" y2="${yy}" stroke="var(--bg-grid)"/><text x="${L - 8}" y="${yy + 4}" text-anchor="end" class="mut">${tickTxt(v / 1e6, st)} mi</text>`; });
  vals.forEach((v, i) => {
    const x = L + i * pw + (pw - bw) / 2, yy = y(v), h = H - B - yy, col = i < 6 ? 'var(--bg-h1)' : 'var(--bg-h2)';
    const tip = `<b>${r.mensal.rotulos[i]} · ${i < 6 ? 'H1' : 'H2'}</b><br>Custo ${auto(v)}<br>${nf(r.mensal.conteineres[i])} contêineres · ${nf(r.mensal.units[i] / 1e6, 2)} mi units<small>Custo por unit R$ ${nf(r.mensal.custo_unit[i], 2)}</small>`;
    g += `<path class="mk" d="M${x},${H - B} V${yy + 4} Q${x},${yy} ${x + 4},${yy} H${x + bw - 4} Q${x + bw},${yy} ${x + bw},${yy + 4} V${H - B} Z" fill="${col}"/>`;
    g += `<text x="${x + bw / 2}" y="${yy - 7}" text-anchor="middle" class="lbl">${nf(v / 1e6, 1)} mi</text>`;
    g += `<text x="${x + bw / 2}" y="${H - 10}" text-anchor="middle">${r.mensal.rotulos[i].split('/')[0]}</text>`;
    g += `<rect class="hit" x="${L + i * pw}" y="${T - 10}" width="${pw}" height="${H - B - T + 10}"${tipAttr(tip)}/>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Custo mensal">${g}<line x1="${L}" x2="${W - 10}" y1="${H - B}" y2="${H - B}" stroke="#4a5a5e"/></svg>`;
}
function chartComposition(r) {
  const it = r.graficos.composicao.itens, W = 560, rh = 27, H = it.length * rh + 8, LW = 250, max = Math.max(...it.map(i => i.v)) * 1.32;
  let g = '';
  it.forEach((d, i) => {
    const yy = 4 + i * rh, w = Math.max(2, (d.v / max) * (W - LW - 8)), lab = d.usd ? `${auto(d.v)} (US$ ${nf(d.usd / 1e3, 0)} mil)` : auto(d.v);
    g += `<text x="${LW - 10}" y="${yy + 16}" text-anchor="end">${E(d.l)} <tspan class="mut">(${nf(d.pct * 100, d.pct < 0.01 ? 1 : 0)}%)</tspan></text>`;
    g += `<rect class="mk" x="${LW}" y="${yy + 4}" width="${w}" height="${rh - 9}" rx="4" fill="var(--bg-bar)"/>`;
    g += `<text x="${LW + w + 7}" y="${yy + 16}" class="lbl">${lab}</text>`;
    g += `<rect class="hit" x="0" y="${yy}" width="${W}" height="${rh}"${tipAttr(`<b>${E(d.l)}</b><br>${auto(d.v)} no ano · ${pct(d.pct)} do total`)}/>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Composição do custo">${g}</svg>`;
}
function chartVariation(r) {
  const it = r.graficos.variacao.itens, W = 560, rh = 34, H = it.length * rh + 10, LW = 230, ext = Math.max(...it.map(i => Math.abs(i.v))) * 1.45 || 1;
  const pos = Math.max(0, ...it.map(i => i.v)), neg = Math.max(0, ...it.map(i => -i.v)), span = W - LW - 10, lab = 92;
  const sc = (span - (neg ? lab : 8) - (pos ? lab : 8)) / ((pos + neg) || 1), z = LW + (neg ? lab : 8) + neg * sc;
  let g = `<line x1="${z}" x2="${z}" y1="0" y2="${H}" stroke="#4a5a5e"/>`;
  it.forEach((d, i) => {
    const yy = 5 + i * rh, w = Math.abs(d.v) * sc, x = d.v >= 0 ? z : z - w, col = d.v >= 0 ? 'var(--bg-up)' : 'var(--bg-down)';
    const lab = sig(d.v, v => v >= 999500 ? mi(v) : `R$ ${nf(v / 1e3, 0)} mil`);
    g += `<text x="${LW - 10}" y="${yy + 19}" text-anchor="end">${E(d.l)}</text>`;
    g += `<rect class="mk" x="${x}" y="${yy + 6}" width="${Math.max(2, w)}" height="${rh - 12}" rx="4" fill="${col}"/>`;
    g += `<text x="${d.v >= 0 ? x + w + 6 : x - 6}" y="${yy + 19}" text-anchor="${d.v >= 0 ? 'start' : 'end'}" class="lbl">${lab}</text>`;
    g += `<rect class="hit" x="0" y="${yy}" width="${W}" height="${rh}"${tipAttr(`<b>${E(d.l)}</b><br>${lab} vs Forecast anterior`)}/>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Variação por rubrica">${g}</svg>`;
}
function chartCompare(r) {
  const it = r.graficos.comparacao.itens, W = 560, H = 290, L = 36, B = 28, T = 22, max = niceMax(Math.max(...it.flatMap(i => [i.atual, i.budget, i.forecast])) / 1e6 * 1.1);
  const pw = (W - L - 6) / it.length, bw = pw * 0.22, y = v => H - B - (v / max) * (H - B - T), tk = ticks(max), st = tk[1] || max;
  let g = '';
  tk.forEach(v => { const yy = y(v); g += `<line x1="${L}" x2="${W - 6}" y1="${yy}" y2="${yy}" stroke="var(--bg-grid)"/><text x="${L - 6}" y="${yy + 4}" text-anchor="end" class="mut">${tickTxt(v, st)}</text>`; });
  it.forEach((d, i) => {
    const x0 = L + i * pw + pw * 0.14;
    [['atual', 'var(--bg-c27)'], ['budget', 'var(--bg-cb)'], ['forecast', 'var(--bg-cf)']].forEach(([k, c], j) => {
      const v = d[k] / 1e6, x = x0 + j * (bw + 3), yy = y(v);
      g += `<path class="mk" d="M${x},${H - B} V${yy + 3} Q${x},${yy} ${x + 3},${yy} H${x + bw - 3} Q${x + bw},${yy} ${x + bw},${yy + 3} V${H - B} Z" fill="${c}"/>`;
      if (k === 'atual') g += `<text x="${x + bw / 2}" y="${yy - 6}" text-anchor="middle" class="lbl">${nf(v, 1)}</text>`;
    });
    g += `<text x="${x0 + bw * 1.5 + 3}" y="${H - 9}" text-anchor="middle">${E(d.l)}</text>`;
    g += `<rect class="hit" x="${L + i * pw}" y="${T}" width="${pw}" height="${H - B - T}"${tipAttr(`<b>${E(d.l)}</b><br>Orçamento ${mi(d.atual)}<br>Budget anterior ${mi(d.budget)}<br>Forecast anterior ${mi(d.forecast)}`)}/>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Comparação com o ano anterior">${g}<line x1="${L}" x2="${W - 6}" y1="${H - B}" y2="${H - B}" stroke="#4a5a5e"/></svg>`;
}
function chartUnit(r) {
  const v = r.mensal.custo_unit, ref = r.graficos.custo_unit.ref, W = 560, H = 290, L = 44, B = 28, T = 24;
  let lo = Math.min(...v, ref), hi = Math.max(...v, ref); const st0 = niceStep(((hi - lo) * 1.4 || 0.4) / 4); lo = Math.floor((lo - st0 * 0.4) / st0) * st0; hi = Math.ceil((hi + st0 * 0.4) / st0) * st0;
  const pw = (W - L - 16) / 11, x = i => L + 8 + i * pw, y = val => H - B - (val - lo) / (hi - lo) * (H - B - T);
  let g = '';
  for (let val = lo; val <= hi + st0 / 2; val += st0) { const yy = y(val); g += `<line x1="${L}" x2="${W - 6}" y1="${yy}" y2="${yy}" stroke="var(--bg-grid)"/><text x="${L - 6}" y="${yy + 4}" text-anchor="end" class="mut">${nf(val, 2)}</text>`; }
  g += `<line x1="${L}" x2="${W - 6}" y1="${y(ref)}" y2="${y(ref)}" stroke="#8C9DA4" stroke-width="1.5" stroke-dasharray="6 5"/>`;
  g += `<path d="${v.map((val, i) => `${i ? 'L' : 'M'}${x(i)},${y(val)}`).join(' ')}" fill="none" stroke="var(--bg-bar)" stroke-width="2.5" stroke-linejoin="round"/>`;
  v.forEach((val, i) => {
    g += `<circle class="mk" cx="${x(i)}" cy="${y(val)}" r="4.5" fill="var(--bg-bar)" stroke="var(--bg-card)" stroke-width="2"/>`;
    const up = i === 0 ? val >= v[1] : val >= v[i - 1];   // sobe = rotulo acima; desce = abaixo (todos os pontos com rotulo)
    g += `<text x="${x(i)}" y="${y(val) + (up ? -11 : 19)}" text-anchor="middle" class="lbl">${nf(val, 2)}</text>`;
    g += `<text x="${x(i)}" y="${H - 9}" text-anchor="middle">${r.mensal.rotulos[i].split('/')[0]}</text>`;
    g += `<rect class="hit" x="${x(i) - pw / 2}" y="${T}" width="${pw}" height="${H - B - T}"${tipAttr(`<b>${r.mensal.rotulos[i]}</b><br>Custo por unit R$ ${nf(val, 2)}<small>Referência ${E(r.graficos.custo_unit.ref_rotulo)}</small>`)}/>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Custo por unit">${g}</svg>`;
}
function painelHtml() {
  const r = res(), g = r.graficos, ano = r.ano;
  const lg = items => `<div class="bg-legend">${items.map(([c, l, cls]) => `<span><i class="${cls || ''}" style="${cls ? '' : `background:${c}`}"></i>${l}</span>`).join('')}</div>`;
  return `<div class="bg-grid">
    <section class="bg-chart wide"><div class="bg-chart-head"><div><h3>${E(g.mensal.titulo)} (R$ milhões)</h3><p class="sub">${E(g.mensal.sub)}</p></div>${lg([['var(--bg-h1)', 'H1 (jan–jun)'], ['var(--bg-h2)', 'H2 (jul–dez)']])}</div>${chartMonthly(r)}</section>
    <section class="bg-chart"><h3>${E(g.composicao.titulo)}</h3><p class="sub">${E(g.composicao.sub)}</p>${chartComposition(r)}</section>
    <section class="bg-chart"><div class="bg-chart-head"><div><h3>${E(g.variacao.titulo)}</h3><p class="sub">${E(g.variacao.sub)}</p></div>${lg([['var(--bg-up)', 'Aumento de custo'], ['var(--bg-down)', 'Redução de custo']])}</div>${chartVariation(r)}</section>
    <section class="bg-chart"><div class="bg-chart-head"><div><h3>${E(g.comparacao.titulo)} (R$ milhões)</h3><p class="sub">${E(g.comparacao.sub)}</p></div></div>
      ${lg([['var(--bg-c27)', `Orçamento ${ano}`], ['var(--bg-cb)', `Budget ${ano - 1}`], ['var(--bg-cf)', `Forecast ${ano - 1}`]])}${chartCompare(r)}</section>
    <section class="bg-chart"><div class="bg-chart-head"><div><h3>${E(g.custo_unit.titulo)} (R$)</h3><p class="sub">${E(g.custo_unit.sub)}</p></div></div>
      ${lg([['var(--bg-bar)', `Custo por unit ${ano}`], ['', E(g.custo_unit.ref_rotulo), 'dash']])}${chartUnit(r)}</section>
  </div>`;
}

/* ---------------- resumo mensal (rubricas abertas nas linhas de detalhe) ---------------- */
function viewBar() {
  const a = res().ano, b = (k, l) => `<button type="button" data-view="${k}" class="${S.view === k ? 'on' : ''}">${l}</button>`;
  return `<div class="bg-filter bg-view" role="group" aria-label="Linhas exibidas">${b('orcamento', `Orçamento ${a}`)}${b('budget', `Budget ${a - 1}`)}${b('forecast', `Forecast ${a - 1}`)}</div>`;
}
function mensalHtml() {
  S.view = S.view || 'orcamento';
  return viewBar() + (S.view === 'orcamento' ? mensalOrcHtml() : mensalCenHtml(S.view));
}
function mensalCenHtml(cen) {
  const r = res(), c = r.cenarios[cen], a = r.ano - 1, nome = cen === 'budget' ? `Budget ${a}` : `Forecast ${a}`;
  const head = r.mensal.rotulos.map(x => `<th>${E(x.replace(String(r.ano).slice(2), String(a).slice(2)))}</th>`).join('');
  const nd = '<td class="mut">n/d</td>'.repeat(12);
  let rows = c.linhas.map(x => `<tr><td>${E(x.l)}</td>${x.v ? x.v.map(v => `<td>${auto(v)}</td>`).join('') : nd}
      <td class="h">${x.v ? auto(x.h1) : 'n/d'}</td><td class="h2">${x.v ? auto(x.total - x.h1) : 'n/d'}</td><td><b>${x.total == null ? 'n/d' : auto(x.total)}</b></td><td>${x.pct == null ? '' : pct(x.pct)}</td></tr>`).join('');
  rows += `<tr class="tot"><td>Custo total</td>${c.total ? c.total.map(v => `<td>${auto(v)}</td>`).join('') : nd}<td>${c.h1 == null ? 'n/d' : auto(c.h1)}</td><td>${c.h1 == null ? 'n/d' : auto(c.total_anual - c.h1)}</td><td>${auto(c.total_anual)}</td><td>100%</td></tr>`;
  const sum = v => v.reduce((x, y) => x + y, 0);
  const ind = (l, v, f, tot) => `<tr><td>${l}</td>${v ? v.map(x => `<td>${f(x)}</td>`).join('') : nd}<td class="h">${v ? f(tot ? tot[0] : sum(v.slice(0, 6))) : 'n/d'}</td><td class="h2">${v ? f(tot ? tot[1] : sum(v.slice(6))) : 'n/d'}</td><td><b>${v ? f(tot ? tot[2] : sum(v)) : (l.startsWith('Volume') ? f(c.units_anual) : 'n/d')}</b></td><td></td></tr>`;
  rows += `<tr class="sec"><td>Indicadores</td><td colspan="16"></td></tr>`;
  rows += ind('Volume recebido (units)', c.units, x => nf(x / 1e6, 2) + ' mi');
  rows += ind('Contêineres', c.conteineres, x => nf(x));
  if (c.units && c.total) { const u1 = sum(c.units.slice(0, 6)); rows += ind('Custo por unit (R$)', c.custo_unit, x => nf(x, 2), [c.h1 / u1, (c.total_anual - c.h1) / (c.units_anual - u1), c.total_anual / c.units_anual]); }
  return `<div class="bg-table clean"><table><thead><tr><th>${E(nome)} · linha de custo</th>${head}<th>H1</th><th>H2</th><th>Total ${a}</th><th>% do total</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="bg-foot">${E(nome)} mês a mês: ${E((S.data.params.anterior_mensal || {}).fonte || 'Ferramenta de Controle do ano anterior')}. O total anual é o do Comparativo; "n/d" aparece quando o anual da rubrica foi alterado e o mês a mês deixou de conferir.
    O rodoviário aparece dividido em frete Santos/Extrema e adicionais (ajudantes, escolta, travas, estadias, Santos-Louveira e outros).</p>`;
}
function mensalOrcHtml() {
  const r = res(), m = r.mensal, k = r.kpi, head = m.rotulos.map(x => `<th>${E(x)}</th>`).join('');
  const cells = (v, cls = '') => v.map((x, i) => `<td class="${i < 6 ? '' : ''}${cls}">${auto(x)}</td>`).join('');
  let rows = '';
  r.rubricas.filter(x => Math.abs(x.total) >= 0.5 || x.det.length).forEach(x => {
    const has = x.det.length > 1, op = S.open.has(x.k);
    rows += `<tr><td>${has ? `<button class="tog" type="button" data-tog="${x.k}" aria-expanded="${op}">${op ? '−' : '+'}</button>` : ''}${E(x.l)}</td>${cells(x.v)}
      <td class="h">${auto(x.h1)}</td><td class="h2">${auto(x.total - x.h1)}</td><td><b>${auto(x.total)}</b></td><td>${pct(x.pct)}</td><td>${has ? '100%' : ''}</td></tr>`;
    if (has && op) x.det.forEach(d => { rows += `<tr class="det"><td>${E(d.l)}</td>${cells(d.v)}<td class="h">${auto(d.h1)}</td><td class="h2">${auto(d.total - d.h1)}</td><td>${auto(d.total)}</td><td>${pct(d.pct)}</td><td>${pct(d.pct_rubrica)}</td></tr>`; });
  });
  rows += `<tr class="tot"><td>Custo total</td>${cells(m.total)}<td>${auto(k.h1)}</td><td>${auto(k.h2)}</td><td>${auto(k.total)}</td><td>100%</td><td></td></tr>`;
  const sum = v => v.reduce((a, b) => a + b, 0), h1 = v => sum(v.slice(0, 6));
  const ind = (l, v, f, tot) => `<tr><td>${l}</td>${v.map(x => `<td>${f(x)}</td>`).join('')}<td class="h">${f(tot ? tot[0] : h1(v))}</td><td class="h2">${f(tot ? tot[1] : sum(v) - h1(v))}</td><td><b>${f(tot ? tot[2] : sum(v))}</b></td><td></td><td></td></tr>`;
  const u = m.units, uh1 = h1(u), cn = m.conteineres, ch1 = h1(cn);
  rows += `<tr class="sec"><td>Indicadores</td><td colspan="17"></td></tr>`;
  rows += ind('Volume recebido (units)', u, x => nf(x / 1e6, 2) + ' mi');
  rows += ind('Contêineres', cn, x => nf(x));
  rows += ind('Processos aéreos', m.processos_aereos, x => nf(x));
  rows += ind('Custo por unit (R$)', m.custo_unit, x => nf(x, 2), [k.h1 / uh1, k.h2 / (k.units - uh1), k.custo_unit]);
  rows += ind('Custo por contêiner (R$)', m.custo_cntr, x => nf(x), [k.h1 / ch1, k.h2 / (k.conteineres - ch1), k.custo_cntr]);
  rows += ind('Seguro internacional (US$)', Array(12).fill(k.seguro_usd_ano / 12), x => 'US$ ' + nf(x, 2));
  return `<div class="bg-table clean"><table><thead><tr><th>Rubrica / linha de custo</th>${head}<th>H1</th><th>H2</th><th>Total ${r.ano}</th><th>% do total</th><th>% da rubrica</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="bg-foot">Valores: "mil" = milhares (R$ 925,9 mil = R$ 925.900) e "mi" = milhões (R$ 1,20 mi = R$ 1.200.000). Rubricas compostas abrem nas linhas de detalhe (sinal + / −); o total soma só as rubricas, nunca as linhas de detalhe.
    Seguro: apólice de US$ ${nf(k.seguro_usd_ano, 2)}/ano convertida pelo câmbio = ${auto(k.seguro_brl_ano)}/ano.</p>`;
}
function bindMensal() {
  document.querySelectorAll('[data-tog]').forEach(b => b.onclick = () => { const k = b.dataset.tog; S.open.has(k) ? S.open.delete(k) : S.open.add(k); body(); });
  document.querySelectorAll('[data-view]').forEach(b => b.onclick = () => { S.view = b.dataset.view; try { localStorage.setItem('nexus.budget.vista', S.view); } catch {} body(); });
}

/* ---------------- comparativo ---------------- */
function compHtml() {
  const r = res(), k = r.kpi, a = r.ano;
  const vc = v => `<span class="${v > 0.5 ? 'pos' : v < -0.5 ? 'neg' : ''}">${Math.abs(v) < 0.5 ? '–' : sig(v, auto)}</span>`;
  const pc = (v, base) => base ? `<span class="${v > 0 ? 'pos' : v < 0 ? 'neg' : ''}">${spct(v, 0)}</span>` : '–';
  const rows = r.comparativo.map(c => `<tr><td>${E(c.l)}</td><td><b>${auto(c.atual)}</b></td><td>${auto(c.budget)}</td><td>${auto(c.forecast)}</td>
    <td class="h">${vc(c.var_f)}</td><td class="h">${pc(c.var_f_pct, c.forecast)}</td><td>${vc(c.var_b)}</td><td>${pc(c.var_b_pct, c.budget)}</td><td class="note">${E(c.explica)}</td></tr>`).join('');
  return `<div class="bg-table"><table><thead><tr><th>Rubrica</th><th>Orçamento ${a}</th><th>Budget ${a - 1}</th><th>Forecast ${a - 1}</th><th>Var. vs Forecast</th><th>%</th><th>Var. vs Budget</th><th>%</th><th style="text-align:left">O que explica</th></tr></thead><tbody>${rows}
    <tr class="tot"><td>Custo total</td><td>${auto(k.total)}</td><td>${auto(k.budget_anterior)}</td><td>${auto(k.forecast_anterior)}</td><td>${sig(k.var_forecast, auto)}</td><td>${spct(k.var_forecast_pct)}</td><td>${sig(k.var_budget, auto)}</td><td>${spct(k.var_budget_pct)}</td><td></td></tr>
    <tr><td>Volume (units)</td><td>${nf(k.units)}</td><td>${nf(k.volume_budget)}</td><td>${nf(k.volume_forecast)}</td><td>${sig(k.units - k.volume_forecast, nf)}</td><td>${pc(k.units / k.volume_forecast - 1, k.volume_forecast)}</td><td>${sig(k.units - k.volume_budget, nf)}</td><td>${pc(k.units / k.volume_budget - 1, k.volume_budget)}</td><td></td></tr>
    <tr><td>Custo por unit (R$)</td><td>${nf(k.custo_unit, 3)}</td><td>${nf(k.custo_unit_budget, 3)}</td><td>${nf(k.custo_unit_forecast, 3)}</td><td>${sig(k.custo_unit - k.custo_unit_forecast, x => nf(x, 3))}</td><td>${pc(k.var_cpu_forecast_pct, 1)}</td><td>${sig(k.custo_unit - k.custo_unit_budget, x => nf(x, 3))}</td><td>${pc(k.custo_unit / k.custo_unit_budget - 1, k.custo_unit_budget)}</td><td></td></tr>
  </tbody></table></div>
  <p class="bg-foot">Vermelho = custo maior no ${a}; azul = menor. Budget e Forecast ${a - 1} existem só por rubrica (o rodoviário aparece no total). Os valores do ano anterior podem ser ajustados em Premissas.</p>`;
}

/* ---------------- premissas (editaveis, recalculo na hora) ---------------- */
const CAT = () => S.home.catalogo;
const isPct = e => e.t === 'pct';
const showVal = (e, v) => isPct(e) ? nf(v * 100, 2) : e.t === 'int' ? nf(v) : nf(v, e.t === 'num' ? 2 : 2);
const parseNum = s => { s = String(s).trim().replace(/\s|R\$|US\$|%/g, ''); if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.'); const n = Number(s); return Number.isFinite(n) ? n : NaN; };
function premHtml() {
  const p = S.draft, o = S.data.params, c = CAT(), ano = p.ano;
  const field = e => `<div class="bg-field"><label for="bgp-${e.k}">${E(e.l)} <small>· ${E(e.u)}</small></label>
    <input id="bgp-${e.k}" data-p="e.${e.k}" inputmode="decimal" value="${showVal(e, p.escalares[e.k])}" class="${p.escalares[e.k] !== o.escalares[e.k] ? 'chg' : ''}">
    ${e.k === 'seguro_apolice_usd_ano' ? `<span class="hint">= ${auto(res().kpi.seguro_brl_ano)}/ano no câmbio da premissa</span>` : ''}</div>`;
  const grp = g => c.escalares.filter(e => e.g === g).map(field).join('');
  const eff = res().tarifas_vigentes;
  const trow = t => { const d = p.tarifas[t.k], od = o.tarifas[t.k], ch = f => d[f] !== od[f] ? ' chg' : '';
    return `<div class="bg-trow"><div class="lab"><b>${E(t.l)}</b><small>${E(t.drv)}</small></div>
      <input data-p="t.${t.k}.base" inputmode="decimal" value="${nf(d.base, d.base < 1 && d.base > 0 ? 4 : 2)}" class="${ch('base')}" aria-label="Base de ${E(t.l)}">
      <select data-p="t.${t.k}.moeda" class="${ch('moeda')}" aria-label="Moeda"><option${d.moeda === 'BRL' ? ' selected' : ''}>BRL</option><option${d.moeda === 'USD' ? ' selected' : ''}>USD</option></select>
      <select data-p="t.${t.k}.mes" class="${ch('mes')}" aria-label="Reajuste a partir do mês">${[0, ...Array.from({length: 12}, (_, i) => i + 1)].map(m => `<option value="${m}"${+d.mes === m ? ' selected' : ''}>${m ? c.meses[m - 1] : 'Todos'}</option>`).join('')}</select>
      <div class="pctbox"><select data-p="t.${t.k}.reajuste" class="${ch('reajuste')}" aria-label="Tipo de reajuste">${[['ipca', 'IPCA'], ['inhouse', 'Dissídio In-House'], ['nenhum', 'Sem reajuste'], ['fixo', '% fixo']].map(([v, l]) => `<option value="${v}"${d.reajuste === v ? ' selected' : ''}>${l}</option>`).join('')}</select></div>
      <input data-p="t.${t.k}.pct" inputmode="decimal" value="${nf((d.pct || 0) * 100, 2)}" ${d.reajuste === 'fixo' ? '' : 'disabled'} class="${ch('pct')}" aria-label="% fixo">
      <div class="eff" title="Tarifa usada em dezembro, em reais">R$ ${nf(eff[t.k][11], eff[t.k][11] < 1 ? 4 : 2)}</div></div>`; };
  const curva = p.curva.map((v, i) => `<div><div class="bar${i > 5 ? ' h2' : ''}"><i style="height:${(v / Math.max(...p.curva) * 100).toFixed(1)}%"></i></div><small>${c.meses[i]}</small>
      <input data-p="c.${i}" inputmode="numeric" value="${nf(v)}" class="${v !== o.curva[i] ? 'chg' : ''}" aria-label="Recebimento de ${c.meses[i]}">
      <label class="uso"><input type="checkbox" data-p="u.${i}"${p.ajudantes_uso[i] ? ' checked' : ''}> ajud.</label></div>`).join('');
  const ant = c.rubricas.map(rb => `<div class="bg-trow" style="grid-template-columns:minmax(220px,1.6fr) 180px 180px"><div class="lab"><b>${E(rb.l)}</b></div>
      <input data-p="a.${rb.k}.budget" inputmode="decimal" value="${nf(p.anterior[rb.k].budget, 2)}" class="${p.anterior[rb.k].budget !== o.anterior[rb.k].budget ? 'chg' : ''}" aria-label="Budget">
      <input data-p="a.${rb.k}.forecast" inputmode="decimal" value="${nf(p.anterior[rb.k].forecast, 2)}" class="${p.anterior[rb.k].forecast !== o.anterior[rb.k].forecast ? 'chg' : ''}" aria-label="Forecast"></div>`).join('');
  return `<div id="bg-simbar" class="bg-simbar hidden"></div>
  <section class="bg-sec"><header><h3>Premissas principais</h3><span>Mude um valor e o orçamento é recalculado na hora. Para guardar, salve como nova versão (a atual fica no histórico).</span></header>
    <div class="bg-fields"><div class="bg-field"><label for="bgp-ano">Ano do orçamento</label><input id="bgp-ano" data-p="ano" inputmode="numeric" value="${ano}"></div>${grp('Principais')}</div></section>
  <section class="bg-sec"><header><h3>Percentuais operacionais</h3><span>Participação de contêineres e processos em cada situação.</span></header><div class="bg-fields">${grp('Percentuais')}</div></section>
  <section class="bg-sec"><header><h3>Tarifas</h3><span>Tarifa vigente no mês = base × (1 + reajuste a partir do mês de início) × câmbio (se USD).</span></header>
    <div class="bg-trow head"><div>Tarifa</div><div>Base</div><div>Moeda</div><div>Reajuste a partir de</div><div>Tipo de reajuste</div><div>% fixo</div><div style="text-align:right">Vigente em dez</div></div>
    ${CAT().tarifas.map(trow).join('')}</section>
  <section class="bg-sec"><header><h3>Curva de recebimento (units por mês) e meses com ajudantes</h3><span>Total da curva: ${nf(p.curva.reduce((a, b) => a + b, 0))} units. O volume total é distribuído por esta curva.</span></header><div class="bg-curve">${curva}</div></section>
  <section class="bg-sec"><header><h3>Ano anterior (Budget e Forecast ${ano - 1})</h3><span>Referências históricas para o comparativo; não entram no cálculo de ${ano}.</span></header>
    <div class="bg-trow head" style="grid-template-columns:minmax(220px,1.6fr) 180px 180px"><div>Rubrica</div><div>Budget ${ano - 1}</div><div>Forecast ${ano - 1}</div></div>${ant}
    <div class="bg-trow" style="grid-template-columns:minmax(220px,1.6fr) 180px 180px"><div class="lab"><b>Volume (units)</b></div>
      <input data-p="v.b" inputmode="numeric" value="${nf(p.volume_anterior.b)}"><input data-p="v.f" inputmode="numeric" value="${nf(p.volume_anterior.f)}"></div></section>`;
}
function setPath(path, raw, el) {
  const p = S.draft, [kind, a, b] = path.split('.');
  if (kind === 'u') { p.ajudantes_uso[+a] = el.checked ? 1 : 0; return true; }
  if (kind === 't' && (b === 'moeda' || b === 'reajuste')) { p.tarifas[a][b] = raw; if (b === 'reajuste') { const pc = el.closest('.bg-trow').querySelector(`[data-p="t.${a}.pct"]`); pc.disabled = raw !== 'fixo'; } return true; }
  if (kind === 't' && b === 'mes') { p.tarifas[a].mes = +raw; return true; }
  const n = parseNum(raw); if (!Number.isFinite(n)) return false;
  if (kind === 'ano') p.ano = Math.round(n);
  else if (kind === 'e') { const e = CAT().escalares.find(x => x.k === a); p.escalares[a] = isPct(e) ? n / 100 : n; }
  else if (kind === 't') p.tarifas[a][b] = b === 'pct' ? n / 100 : n;
  else if (kind === 'c') p.curva[+a] = n;
  else if (kind === 'a') p.anterior[a][b] = n;
  else if (kind === 'v') p.volume_anterior[a] = n;
  return true;
}
function changedCount() {
  const a = JSON.stringify(S.data.params), b = JSON.stringify(S.draft);
  if (a === b) return 0;
  let n = 0; const o = S.data.params, p = S.draft;
  for (const k in p.escalares) if (p.escalares[k] !== o.escalares[k]) n++;
  for (const k in p.tarifas) for (const f of ['base', 'moeda', 'reajuste', 'pct', 'mes']) if (p.tarifas[k][f] !== o.tarifas[k][f]) n++;
  p.curva.forEach((v, i) => { if (v !== o.curva[i]) n++; }); p.ajudantes_uso.forEach((v, i) => { if (v !== o.ajudantes_uso[i]) n++; });
  for (const k in p.anterior) for (const f of ['budget', 'forecast']) if (p.anterior[k][f] !== o.anterior[k][f]) n++;
  if (p.ano !== o.ano) n++; if (p.volume_anterior.b !== o.volume_anterior.b) n++; if (p.volume_anterior.f !== o.volume_anterior.f) n++;
  return n || 1;
}
function bindPrem() {
  const b = document.getElementById('bg-body');
  const onChange = e => {
    const el = e.target.closest('[data-p]'); if (!el) return;
    const ok = setPath(el.dataset.p, el.type === 'checkbox' ? el.checked : el.value, el);
    el.classList.toggle('chg', ok); if (!ok) return;
    clearTimeout(S.simTimer); S.simTimer = setTimeout(simulate, 350);
  };
  b.addEventListener('input', onChange); b.addEventListener('change', onChange);
  simbar();
}
async function simulate() {
  const n = changedCount();
  if (!n) { S.sim = null; refreshTop(); simbar(); return; }
  try { S.sim = await postJson('/api/budget/simular', {params: S.draft}); } catch (e) { S.sim = {erros: [e.message]}; }
  refreshTop(); simbar();
  const eff = S.sim && S.sim.resultado && S.sim.resultado.tarifas_vigentes;
  if (eff) document.querySelectorAll('.bg-trow').forEach(row => { const inp = row.querySelector('[data-p$=".base"]'); if (!inp) return; const k = inp.dataset.p.split('.')[1]; const cell = row.querySelector('.eff'); if (cell && eff[k]) cell.textContent = `R$ ${nf(eff[k][11], eff[k][11] < 1 ? 4 : 2)}`; });
}
function refreshTop() { const k = document.getElementById('bg-kpis'); if (k && res()) k.innerHTML = kpisHtml(); }
function simbar() {
  const bar = document.getElementById('bg-simbar'); if (!bar) return;
  const n = changedCount(); bar.classList.toggle('hidden', !n); if (!n) { bar.innerHTML = ''; return; }
  const errs = (S.sim && S.sim.erros) || [];
  const a = S.data.resultado.kpi.total, b = S.sim && S.sim.resultado ? S.sim.resultado.kpi.total : a, d = b - a;
  bar.innerHTML = `<div class="grow">${errs.length ? `<span class="bg-bad">${E(errs.join(' · '))}</span>` : `Total: ${mi(a, 2)} → <b>${mi(b, 2)}</b> <span class="bg-delta ${d > 0 ? 'up' : 'down'}">(${sig(d, x => mi(x, 2))})</span> · ${n} premissa(s) alterada(s)`}</div>
    <input id="bg-newname" placeholder="Nome da nova versão (ex.: Câmbio 5,40)" maxlength="80" aria-label="Nome da nova versão">
    <button class="secondary" type="button" id="bg-discard">Descartar</button><button class="primary" type="button" id="bg-save"${errs.length ? ' disabled' : ''}>${IC.check}Salvar como nova versão</button>`;
  bar.querySelector('#bg-discard').onclick = () => { S.draft = JSON.parse(JSON.stringify(S.data.params)); S.sim = null; render(); };
  bar.querySelector('#bg-save').onclick = async () => {
    const btn = bar.querySelector('#bg-save'); btn.disabled = true; btn.textContent = 'Salvando…';
    try { const r = await postJson('/api/budget/versoes', {base: S.cur, nome: bar.querySelector('#bg-newname').value, params: S.draft});
      S.cur = r.id; await loadHome(true); S.tab = 'historico'; render(); }
    catch (e) { btn.disabled = false; btn.textContent = 'Salvar como nova versão'; alert(e.message); }
  };
}

/* ---------------- alertas ---------------- */
function alertHtml() {
  const al = S.data.alertas || [], f = S.filter, list = f === 'todos' ? al : al.filter(a => a.sev === f);
  const cnt = s => al.filter(a => a.sev === s).length;
  const fb = (k, l) => `<button type="button" data-flt="${k}" class="${f === k ? 'on' : ''}">${l}</button>`;
  return `<div class="bg-filter">${fb('todos', `Todos (${al.length})`)}${fb('Alta', `Alta (${cnt('Alta')})`)}${fb('Média', `Média (${cnt('Média')})`)}${fb('Baixa', `Baixa (${cnt('Baixa')})`)}</div>
    <div class="bg-alerts">${list.length ? list.map(a => `<article class="bg-alert"><span class="bg-sev ${a.sev}">${SEV_IC[a.sev] || ''}${a.sev}</span>
      <div><h4>${E(a.titulo)}</h4><p>${E(a.detalhe || '')}</p>${a.acao ? `<p class="act">Ação: ${E(a.acao)}</p>` : ''}<div class="where">${E(a.cod)} · ${E(a.onde || '')}</div></div>
      <div class="imp">${a.impacto != null && Math.abs(a.impacto) >= 1 ? `${sig(a.impacto, auto)}<small>impacto estimado/ano</small>` : ''}</div></article>`).join('')
      : '<div class="empty"><b>Nenhum alerta</b>As premissas desta versão passaram em todas as verificações.</div>'}</div>
    <p class="bg-foot">Alta = muda o total ou a lógica do modelo; Média = risco relevante ou inconsistência; Baixa = qualidade ou provisão. Os alertas da planilha de origem (somas, valores colados, linhas sem rótulo) ficam registrados na versão importada.</p>`;
}
function bindAlert() { document.querySelectorAll('[data-flt]').forEach(b => b.onclick = () => { S.filter = b.dataset.flt; body(); }); }

/* ---------------- historico e comparacao ---------------- */
function histHtml() {
  const vs = S.home.versoes, master = S.home.pode_excluir;
  if (!S.cmp.a || !vs.some(v => v.id === S.cmp.a)) S.cmp.a = S.cur;
  if (!S.cmp.b || !vs.some(v => v.id === S.cmp.b)) S.cmp.b = (vs.find(v => v.id !== S.cmp.a) || {}).id || '';
  const opt = sel => vs.map(v => `<option value="${v.id}"${v.id === sel ? ' selected' : ''}>${E(v.ciclo)} · ${E(v.nome)}</option>`).join('');
  const chip = v => `<span class="bg-chip ${v.origem === 'edicao' ? 'edicao' : v.formato === 'generico' ? 'generico' : ''}">${v.origem === 'edicao' ? 'Ajuste no sistema' : v.origem === 'modelo' ? 'Modelo aprovado' : v.formato === 'modelo' ? 'Planilha MODELO' : v.formato === 'generico' ? 'Fora do modelo' : 'Planilha FISIA'}</span>`;
  const rows = vs.map((v, i) => { const prev = vs[i + 1], d = prev ? v.resumo.total - prev.resumo.total : null, al = v.alertas || {};
    return `<tr class="${v.id === S.cur ? 'cur' : ''}"><td><b>${E(v.nome)}</b><br><small style="color:var(--muted);font-weight:400">${E(v.ciclo)}${v.arquivo ? ' · ' + E(v.arquivo) : ''}</small></td>
      <td style="text-align:left">${chip(v)}${v.mudancas ? ` <small style="color:var(--muted)">${v.mudancas} alteração(ões)</small>` : ''}</td>
      <td style="text-align:left">${E(v.criado_por_nome || v.criado_por)}<br><small style="color:var(--muted)">${new Date(v.criado_em).toLocaleString('pt-BR')}</small></td>
      <td><b>${mi(v.resumo.total, 2)}</b></td><td>${d == null ? '–' : `<span class="${d > 0 ? 'pos' : d < 0 ? 'neg' : ''}">${sig(d, x => mi(x, 2))}</span>`}</td>
      <td>${al['Alta'] || 0} · ${al['Média'] || 0} · ${al['Baixa'] || 0}</td>
      <td><div class="acts"><button class="secondary" type="button" data-openv="${v.id}">Abrir</button><a class="secondary" href="/api/budget/versoes/${v.id}/excel" download>Excel</a>
        ${v.arquivo ? `<a class="secondary" href="/api/budget/versoes/${v.id}/original" download>Original</a>` : ''}${master ? `<button class="danger-btn" type="button" data-delv="${v.id}" data-name="${E(v.nome)}">Excluir</button>` : ''}</div></td></tr>`; }).join('');
  return `<div class="bg-table bg-hist" style="max-height:none;margin-bottom:16px"><table><thead><tr><th>Versão</th><th style="text-align:left">Origem</th><th style="text-align:left">Enviada por</th><th>Custo total</th><th>vs versão anterior</th><th>Alertas (A · M · B)</th><th>Ações</th></tr></thead><tbody>${rows}</tbody></table></div>
    <section class="bg-sec"><header><h3>Comparar versões</h3><span>Diferença por rubrica entre duas versões.</span></header>
      <div style="padding:14px 16px"><div class="bg-compare">Versão A <select id="bg-cmp-a">${opt(S.cmp.a)}</select> × versão B <select id="bg-cmp-b">${opt(S.cmp.b)}</select></div><div id="bg-cmp-out" class="bg-loading" style="padding:20px 0">Calculando…</div></div></section>`;
}
function bindHist() {
  document.querySelectorAll('[data-openv]').forEach(b => b.onclick = async () => { await loadVersion(b.dataset.openv, false); S.tab = 'painel'; render(); });
  document.querySelectorAll('[data-delv]').forEach(b => b.onclick = async () => {
    if (!confirm(`Excluir a versão "${b.dataset.name}"? Ela sai do histórico (o arquivo fica guardado em budget/excluidas).`)) return;
    try { await api(`/api/budget/versoes/${b.dataset.delv}`, {method: 'DELETE'}); delete S.cache[b.dataset.delv]; await loadHome(true); render(); } catch (e) { alert(e.message); }
  });
  const go = () => { S.cmp.a = document.getElementById('bg-cmp-a').value; S.cmp.b = document.getElementById('bg-cmp-b').value; compare(); };
  document.getElementById('bg-cmp-a').onchange = go; document.getElementById('bg-cmp-b').onchange = go; compare();
}
async function compare() {
  const out = document.getElementById('bg-cmp-out'); if (!out) return;
  if (!S.cmp.b) { out.innerHTML = 'Envie ou salve outra versão para comparar.'; return; }
  const [A, B] = await Promise.all([S.cmp.a, S.cmp.b].map(async id => S.cache[id] || (S.cache[id] = await api(`/api/budget/versoes/${id}`))));
  const ra = Object.fromEntries(A.resultado.rubricas.map(r => [r.k, r])), rb = Object.fromEntries(B.resultado.rubricas.map(r => [r.k, r]));
  const rows = A.resultado.rubricas.map(r => { const a = r.total, b = (rb[r.k] || {}).total || 0, d = a - b;
    return `<tr><td>${E(r.l)}</td><td>${auto(a)}</td><td>${auto(b)}</td><td><span class="${d > 0.5 ? 'pos' : d < -0.5 ? 'neg' : ''}">${Math.abs(d) < 0.5 ? '–' : sig(d, auto)}</span></td><td>${b ? spct(a / b - 1) : '–'}</td>
      <td>${auto(r.h1 - ((rb[r.k] || {}).h1 || 0))}</td></tr>`; }).join('');
  const ka = A.resultado.kpi, kb = B.resultado.kpi, d = ka.total - kb.total;
  out.className = '';
  out.innerHTML = `<div class="bg-table" style="max-height:none"><table><thead><tr><th>Rubrica</th><th>Versão A</th><th>Versão B</th><th>A − B</th><th>%</th><th>Diferença no H1</th></tr></thead><tbody>${rows}
    <tr class="tot"><td>Custo total</td><td>${auto(ka.total)}</td><td>${auto(kb.total)}</td><td>${sig(d, auto)}</td><td>${kb.total ? spct(ka.total / kb.total - 1) : '–'}</td><td>${sig(ka.h1 - kb.h1, auto)}</td></tr></tbody></table></div>
    ${(A.versao.id && A.mudancas.length && (S.home.versoes.find(v => v.id === A.versao.id) || {})) ? `<p class="bg-foot">Premissas alteradas na versão A em relação à versão de origem: ${A.mudancas.slice(0, 12).map(m => `${E(m.rotulo)} (${E(fmtAny(m.de))} → ${E(fmtAny(m.para))})`).join('; ')}${A.mudancas.length > 12 ? '…' : ''}</p>` : ''}`;
}
const fmtAny = v => typeof v === 'number' ? (Math.abs(v) < 1 && v !== 0 ? nf(v * 100, 2) + '%' : nf(v, 2)) : String(v ?? '');

/* ---------------- vazio e upload ---------------- */
function emptyHtml() {
  return `<div class="bg-hero"><div><div class="eyebrow">ORÇAMENTO INBOUND · FISIA · LOGÍSTICA INTERNACIONAL</div><h1>Budget</h1>
    <p>Orçamento Inbound montado a partir da planilha, com premissas editáveis, alertas e download no modelo oficial.</p></div></div>
    <div class="bg-empty"><div><h2>Comece o orçamento</h2>
      <p>Envie a planilha de orçamento (o MODELO do NexxusDoc, a planilha FISIA com Premissas e Orçamento, ou outra planilha: o sistema reconhece as premissas pelos rótulos e mostra uma prévia antes de gravar). Também dá para começar pelo modelo aprovado em 04/11/2026.</p>
      <div class="row">${S.home.modelo_disponivel ? `<button class="secondary" type="button" id="bg-from-model">${IC.model}Começar pelo modelo aprovado</button>` : ''}</div>
      <p class="bg-foot" style="margin-top:14px">Cada envio vira uma versão no histórico, com o arquivo original guardado. Mudou uma premissa? O total é recalculado na hora e a mudança vira uma nova versão.</p></div>
      <div class="bg-drop" id="bg-drop" tabindex="0" role="button">${IC.up}<b>Arraste a planilha aqui</b><small>ou clique para escolher · .xlsx ou .xlsm · até 20 MB</small></div></div>
    <input type="file" id="bg-file" accept=".xlsx,.xlsm" hidden>`;
}
function bindEmpty() {
  const btn = document.getElementById('bg-from-model');
  if (btn) btn.onclick = async () => { btn.disabled = true; btn.textContent = 'Carregando o modelo…';
    try { const r = await postJson('/api/budget/modelo-padrao', {}); S.cur = r.id; await loadHome(true); render(); } catch (e) { btn.disabled = false; alert(e.message); } };
  bindDrop(document.getElementById('bg-drop'), document.getElementById('bg-file'), f => uploadModal(f));
}
function bindDrop(drop, input, onFile) {
  drop.onclick = () => input.click(); drop.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } };
  input.onchange = () => { if (input.files[0]) onFile(input.files[0]); input.value = ''; };
  drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); }; drop.ondragleave = () => drop.classList.remove('over');
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove('over'); const f = e.dataTransfer.files[0]; if (f) onFile(f); };
}
function modal(html) {
  closeModal();
  const back = document.createElement('div'); back.className = 'bg-modal-back'; back.id = 'bg-modal';
  back.innerHTML = `<div class="bg-modal" role="dialog" aria-modal="true">${html}</div>`;
  back.addEventListener('click', e => { if (e.target === back && !S.busy) closeModal(); });
  document.body.appendChild(back); return back;
}
function closeModal() { document.getElementById('bg-modal')?.remove(); }
function uploadModal(file) {
  const back = modal(`<header><div><h2>Enviar planilha de orçamento</h2><p>O NexxusDoc lê as premissas, confere a planilha e mostra uma prévia. Nada é gravado antes de você confirmar.</p></div>
      <button class="ghost" type="button" data-close>Fechar</button></header>
    <div class="body"><div class="bg-drop" id="bg-drop2" tabindex="0" role="button">${IC.up}<b>Arraste a planilha aqui</b><small>ou clique para escolher · .xlsx ou .xlsm · até 20 MB</small></div><input type="file" id="bg-file2" accept=".xlsx,.xlsm" hidden></div>`);
  back.querySelector('[data-close]').onclick = closeModal;
  bindDrop(back.querySelector('#bg-drop2'), back.querySelector('#bg-file2'), analyze);
  if (file) analyze(file);
}
async function analyze(file) {
  S.busy = true;
  const box = document.querySelector('#bg-modal .body');
  box.innerHTML = `<div class="bg-loading">Lendo <b>${E(file.name)}</b> e conferindo as premissas…</div>`;
  const form = new FormData(); form.append('file', file, file.name);
  try { const pv = await api('/api/budget/analisar', {method: 'POST', body: form}); S.busy = false; preview(pv); }
  catch (e) { S.busy = false; box.innerHTML = `<div class="notice error"><div class="grow">${E(e.message)}</div></div>`; }
}
const paramValue = (p, key) => {
  if (key.startsWith('tarifa:')) return p.tarifas[key.slice(7)].base;
  if (key.startsWith('anterior:')) return p.anterior[key.slice(9)].forecast;
  if (key === 'curva') return p.curva.reduce((a, b) => a + b, 0);
  if (key === 'ajudantes_uso') return p.ajudantes_uso.reduce((a, b) => a + b, 0);
  return p.escalares[key];
};
function preview(pv) {
  const k = pv.kpi, rep = pv.reproducao, ciclos = S.home.ciclos || [];
  const al = pv.alertas || [], altas = al.filter(a => a.sev === 'Alta');
  const md = document.querySelector('#bg-modal .bg-modal');
  md.innerHTML = `<header><div><h2>Prévia: ${E(pv.arquivo)}</h2><p>${E(pv.formato_rotulo)} · ano ${E(pv.ano)} · premissas não encontradas usam a ${E(pv.base)}</p></div><button class="ghost" type="button" data-close>Fechar</button></header>
  <div class="body">
    <div class="bg-mini">
      <div><small>Custo total no modelo</small><b>${mi(k.total, 2)}</b><span>H1 ${mi(k.h1)} · H2 ${mi(k.h2)}</span></div>
      <div><small>Total da planilha</small><b>${rep ? mi(rep.total_planilha, 2) : '–'}</b><span class="${rep ? (rep.ok ? 'bg-ok' : 'bg-bad') : ''}">${rep ? (rep.ok ? 'Igual ao cálculo do modelo' : `Diferença de ${sig(rep.diferenca, x => mi(x, 2))}: veja os alertas`) : 'A planilha não informa o total'}</span></div>
      <div><small>Premissas reconhecidas</small><b>${pv.origem.length}</b><span>${pv.faltam.length ? `${pv.faltam.length} com valor de referência` : 'todas encontradas na planilha'}</span></div>
      <div><small>Alertas</small><b>${al.length}</b><span>${altas.length} de gravidade alta</span></div>
    </div>
    ${pv.erros.length ? `<div class="notice error"><div class="grow">${E(pv.erros.join(' · '))}</div></div>` : ''}
    ${pv.faltam.length ? `<section class="bg-sec" style="margin:0"><header><h3>Premissas com valor de referência</h3><span>Não achadas na planilha. Dá para ajustar depois em Premissas (vira nova versão).</span></header>
      <div class="bg-map" style="border:0;border-radius:0"><table><thead><tr><th>Premissa</th><th>Valor usado</th></tr></thead><tbody>${pv.faltam.map(f => `<tr><td>${E(f.rotulo)}</td><td class="n">${nf(paramValue(pv.params, f.chave), 4)}</td></tr>`).join('')}</tbody></table></div></section>` : ''}
    ${al.length ? `<section class="bg-sec" style="margin:0"><header><h3>Alertas da planilha</h3><span>Os principais; a lista completa fica na aba Alertas da versão.</span></header>
      <div style="padding:10px 14px;display:grid;gap:8px">${al.slice(0, 6).map(a => `<div style="display:flex;gap:10px;align-items:flex-start"><span class="bg-sev ${a.sev}">${a.sev}</span><div style="font-size:12.5px;color:#dfe8e4"><b>${E(a.titulo)}</b> <span style="color:var(--muted)">${E(a.onde || '')}</span><br><span style="color:#b9c8c3">${E(a.detalhe || '')}</span></div></div>`).join('')}</div></section>` : ''}
    <details class="bg-sec" style="margin:0"><summary style="padding:12px 16px;cursor:pointer;color:#dfe8e4;font-weight:700">Premissas reconhecidas na planilha (${pv.origem.length}) · de qual célula veio cada uma</summary>
      <div class="bg-map" style="border:0;border-radius:0"><table><thead><tr><th>Premissa</th><th>Célula de origem</th><th>Valor</th></tr></thead><tbody>${pv.origem.map(o => `<tr><td>${E(o.rotulo)}${o.obs ? ` <small style="color:var(--muted)">(${E(o.obs)})</small>` : ''}</td><td>${E(o.celula)}</td><td class="n">${nf(o.valor, 4)}</td></tr>`).join('')}</tbody></table></div></details>
    <div class="bg-two"><div class="bg-field"><label for="bg-ciclo">Ciclo do orçamento</label><input id="bg-ciclo" list="bg-ciclos" value="${E(pv.ciclo_sugerido)}" maxlength="80"><datalist id="bg-ciclos">${ciclos.map(c => `<option value="${E(c)}">`).join('')}</datalist></div>
      <div class="bg-field"><label for="bg-vname">Nome da versão</label><input id="bg-vname" value="${E(pv.arquivo.replace(/\.(xlsx|xlsm)$/i, ''))}" maxlength="80"></div></div>
  </div>
  <footer><span class="grow">O arquivo original fica guardado com a versão, para baixar depois.</span><button class="secondary" type="button" data-close>Cancelar</button>
    <button class="primary" type="button" id="bg-confirm"${pv.erros.length ? ' disabled' : ''}>${IC.check}Criar versão</button></footer>`;
  md.querySelectorAll('[data-close]').forEach(b => b.onclick = closeModal);
  md.querySelector('#bg-confirm').onclick = async () => {
    const b = md.querySelector('#bg-confirm'); b.disabled = true; b.textContent = 'Gravando…'; S.busy = true;
    try { const r = await postJson('/api/budget/confirmar', {token: pv.token, ciclo: md.querySelector('#bg-ciclo').value, nome: md.querySelector('#bg-vname').value});
      S.busy = false; closeModal(); S.cur = r.id; S.tab = 'painel'; await loadHome(true); render(); }
    catch (e) { S.busy = false; b.disabled = false; b.textContent = 'Criar versão'; alert(e.message); }
  };
}

/* ---------------- dica (tooltip) ---------------- */
let tip;
document.addEventListener('mousemove', e => {
  const t = e.target.closest && e.target.closest('#page-budget [data-bgtip]');
  if (!t) { if (tip) tip.style.display = 'none'; return; }
  if (!tip) { tip = document.createElement('div'); tip.className = 'bg-tip'; document.body.appendChild(tip); }
  tip.innerHTML = t.dataset.bgtip; tip.style.display = 'block';
  const w = tip.offsetWidth, h = tip.offsetHeight;
  tip.style.left = Math.min(window.innerWidth - w - 10, e.clientX + 14) + 'px';
  tip.style.top = Math.max(10, e.clientY - h - 12) + 'px';
});

window.nexusBudget = {open, upload: f => uploadModal(f), reset: () => { S.home = null; S.cache = {}; }};
})();
