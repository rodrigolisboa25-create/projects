/* Budget > MBR (18/11/2026): realizado de cada fechamento por operacao, com Budget, Forecast e Actual. Tudo vem das
   bases enviadas (bridges de custo e Ferramenta de Controle); o que a base nao traz aparece como "não consta na base". */
(() => {
'use strict';
const REV = '3';
const R = {data: null, op: 'fisia', per: 'mes', fx: 'real', det: 'custos', comp: '', el: null, intro: false, ult: {}, seq: 0};
const E = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const has = v => v !== null && v !== undefined;
const nf = (v, d = 0) => Number(v || 0).toLocaleString('pt-BR', {minimumFractionDigits: d, maximumFractionDigits: d});
const sg = v => v > 0 ? '+' : v < 0 ? '-' : '';
const brl = v => has(v) ? `${v < 0 ? '-' : ''}R$ ${nf(Math.abs(v))}` : '-';
const sbrl = v => has(v) ? `${sg(v)}R$ ${nf(Math.abs(v))}` : '-';
const pc = (a, b) => has(a) && has(b) && b ? `${sg(a / b - 1)}${nf(Math.abs(a / b - 1) * 100, 1)}%` : '-';
const cls = v => v > 0 ? 'rs-up' : v < 0 ? 'rs-down' : '';
const SEM = 'não consta na base';
const INFO = {budget: 'Orçamento: o plano e a meta oficial do ano. Não muda ao longo do ano.',
  forecast: 'Previsão: o que já aconteceu mais a nova projeção dos meses seguintes.',
  actual: 'Realizado: os números reais, depois do fechamento do mês.'};
const svg = p => `<svg viewBox="0 0 24 24" aria-hidden="true">${p}</svg>`;
const IC = {up: svg('<path d="M12 15V4m0 0-4 4m4-4 4 4"/><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>'), down: svg('<path d="M12 4v11m0 0-4-4m4 4 4-4"/><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>'),
  play: svg('<rect x="3" y="4.5" width="18" height="12.5" rx="2"/><path d="m10 8 4.5 2.7L10 13.5zM8 20.5h8"/>'), ok: svg('<path d="m5 12.5 4.5 4.5L19 7.5"/>'), at: svg('<path d="M12 4 2.8 19.5h18.4z"/><path d="M12 10v4.5m0 2.5h.01"/>')};
const MES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
const compNome = c => c ? `${MES[Number(c.slice(5)) - 1]}/${c.slice(0, 4)}` : '';
const opAtual = () => (R.data.operacoes.find(o => o.operacao === R.op) || R.data.operacoes[0]);
const perAtual = o => (o.periodos.find(p => p.chave === R.per) || o.periodos[0]);

async function load(comp) {
  R.data = await api(`/api/budget/resultados?comp=${encodeURIComponent(comp || R.comp || '')}`);
  R.comp = R.data.competencia;
}
async function mount(el) {
  R.el = el; el.innerHTML = '<div class="bg-loading">Carregando os resultados…</div>';
  R.intro = !!(window.nexusAnim && window.nexusAnim.takeIntro('mbr'));
  const seq = ++R.seq;
  try { await load(); if (seq === R.seq) draw(R.intro ? 'intro' : ''); } catch (e) { if (seq === R.seq) el.innerHTML = `<div class="notice error"><div class="grow">${E(e.message)}</div></div>`; }
}
const seg = (key, items) => `<div class="rs-seg" role="group">${items.map(([v, t]) => `<button type="button" data-set="${key}" data-v="${E(v)}" class="${R[key] === v ? 'on' : ''}">${E(t)}</button>`).join('')}</div>`;

function kpis(p) {
  const r = p.resumo, c = p.cambio || {}, db = r.actual - r.budget, df = has(r.forecast) ? (has(r.dif_forecast) ? r.dif_forecast : r.actual - r.forecast) : null;
  const box = (n, v, u, cpu, info, k) => `<div class="rs-kpi ${k || ''}"><small>${n}</small>${has(v) ? `<strong data-n="${v}" data-f="brl">${brl(v)}</strong><span>${nf(u)} units · CPU R$ ${nf(cpu, 2)}</span>` : `<strong class="nd">${SEM}</strong>`}<em>${info}</em></div>`;
  return `<div class="rs-kpis">${box('Budget', r.budget, r.units_budget, r.cpu_budget, INFO.budget)}${box('Forecast', r.forecast, r.units_forecast, r.cpu_forecast, INFO.forecast)}${box('Actual', r.actual, r.units_actual, r.cpu_actual, INFO.actual, 'act')}
    <div class="rs-kpi"><small>Actual vs Budget</small><strong class="${cls(db)}" data-n="${db}" data-f="sbrl">${sbrl(db)}</strong><span>${pc(r.actual, r.budget)} no custo</span><span>CPU ${pc(r.cpu_actual, r.cpu_budget)}</span></div>
    <div class="rs-kpi"><small>Actual vs Forecast</small>${has(df) ? `<strong class="${cls(df)}" data-n="${df}" data-f="sbrl">${sbrl(df)}</strong><span>${pc(r.actual, r.forecast)} no custo</span><span>CPU ${pc(r.cpu_actual, r.cpu_forecast)}</span>` : `<strong class="nd">${SEM}</strong>`}</div>
    <div class="rs-kpi"><small>Câmbio (USD)</small><strong${has(c.fx_actual) ? ` data-n="${c.fx_actual}" data-f="fx"` : ''}>${has(c.fx_actual) ? nf(c.fx_actual, 2) : '-'}</strong><span>Budget ${has(c.fx_budget) ? nf(c.fx_budget, 2) : '-'}</span><span>Efeito ${has(c.efeito_fx) ? sbrl(c.efeito_fx) : '-'}</span></div></div>`;
}
function waterfall(p) {
  const r = p.resumo, W = 1240, H = 330, T = 68, B = 44, L = 8;
  const it = [{t: 'BUDGET', v: r.budget, end: 1}, ...p.ponte.map(x => ({t: x.rotulo, v: (x.valor || 0) * 1e6})), {t: 'ACTUAL', v: r.actual, end: 1}];
  let acc = r.budget, top = r.budget;
  it.forEach(x => { if (!x.end) { x.a = acc; acc += x.v; x.b = acc; top = Math.max(top, x.a, x.b); } });
  const y = v => H - B - v / (top * 1.05) * (H - B - T), pw = (W - L * 2) / it.length, bw = pw * .6, d = top >= 1e6 ? 2 : 3;
  let s = `<defs><linearGradient id="wfU" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FF7A6E"/><stop offset="1" stop-color="#C9302C"/></linearGradient><linearGradient id="wfD" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5BE08A"/><stop offset="1" stop-color="#12A150"/></linearGradient><linearGradient id="wfE" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6FB1FF"/><stop offset="1" stop-color="#2459BC"/></linearGradient></defs><line x1="${L}" x2="${W - L}" y1="${y(0)}" y2="${y(0)}" stroke="rgba(255,255,255,.25)"/>`;
  it.forEach((x, i) => {
    const cx = L + pw * i + pw / 2, x0 = cx - bw / 2, up = !x.end && x.v > 0;
    const t0 = x.end ? y(x.v) : y(Math.max(x.a, x.b)), h = x.end ? y(0) - t0 : Math.max(3, Math.abs(y(x.a) - y(x.b)));
    const cor = x.end ? 'url(#wfE)' : up ? 'url(#wfU)' : 'url(#wfD)', tx = x.end ? nf(x.v / 1e6, d) : `${sg(x.v)}${nf(Math.abs(x.v) / 1e6, d)}`;
    s += `<rect x="${x0}" y="${t0}" width="${bw}" height="${h}" rx="3" fill="${cor}" class="gy" style="--i:${i}"/><text class="v fd" x="${cx}" y="${t0 - 8}" text-anchor="middle" style="--i:${i}${x.end ? '' : `;fill:${up ? '#ff8f87' : '#6fe39a'}`}">${tx}</text><text x="${cx}" y="${H - B + 20}" text-anchor="middle">${E(x.t)}</text>`;
    s += `<rect x="${L + pw * i}" y="0" width="${pw}" height="${H}" fill="transparent" data-bgtip="<b>${E(x.t)}</b><br>${x.end ? brl(x.v) : sbrl(x.v)}"/>`;
    if (i < it.length - 1) { const n = x.end ? x.v : x.b; s += `<line x1="${x0 + bw}" x2="${x0 + pw}" y1="${y(n)}" y2="${y(n)}" stroke="rgba(255,255,255,.25)" stroke-dasharray="3 4" class="fd" style="--i:${i}"/>`; }
  });
  // Traco que liga o Budget ao Actual, com a diferenca total no meio (como no MBR)
  const dt = r.actual - r.budget, xa = L + pw / 2, xb = L + pw * (it.length - 1) + pw / 2, xm = (xa + xb) / 2, yb = 16, gap = 62, corT = dt > 0 ? '#ff8f87' : '#6fe39a';
  s += `<g class="wf-br" fill="none" stroke="#dfe8e4" stroke-width="1.5"><path class="dr" pathLength="1" d="M${xa} ${y(r.budget) - 26}V${yb}H${xm - gap}M${xm + gap} ${yb}H${xb}V${y(r.actual) - 32}"/><path class="fd tarde" d="M${xb - 5} ${y(r.actual) - 33}h10l-5 8z" fill="#dfe8e4" stroke="none"/></g><text class="v fd tarde" x="${xm}" y="${yb + 5}" text-anchor="middle" style="font-size:15px;fill:${corT}">${sg(dt)}${nf(Math.abs(dt) / 1e6, 3)}MM</text>`;
  return `<section class="rs-sec" data-rv="bridge"><header><div><h3>Bridge: do Budget ao Actual (R$ milhões)</h3><p>Mostra cada fator que aumentou ou reduziu o custo. Preço a câmbio do Budget; a variação cambial aparece separada.</p></div>
    <div class="rs-leg"><span><i style="background:linear-gradient(180deg,#FF7A6E,#C9302C)"></i>Aumenta o custo</span><span><i style="background:linear-gradient(180deg,#5BE08A,#12A150)"></i>Reduz o custo</span></div></header><div class="rs-pad"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Bridge de custo">${s}</svg></div></section>`;
}
function grupos(p) {
  const b = R.fx === 'budget' && p.cambio_budget ? p.cambio_budget : p.real;
  const row = (x, t) => `<tr class="${t ? 't' : ''}"><td>${E(x.rotulo)}</td><td>${nf(x.cpu_budget, 2)}</td><td>${nf(x.cpu_actual, 2)}</td><td>${nf(x.budget)}</td><td>${nf(x.actual)}</td><td class="${cls(x.variacao)}">${sg(x.variacao)}${nf(Math.abs(x.variacao))}</td><td class="${cls(x.impacto_volume)}">${sg(x.impacto_volume)}${nf(Math.abs(x.impacto_volume))}</td><td class="${cls(x.impacto_preco)}">${sg(x.impacto_preco)}${nf(Math.abs(x.impacto_preco))}</td></tr>`;
  return `<section class="rs-sec"><header><div><h3>Abertura por grupo</h3><p>Impacto de volume e de preço em relação ao Budget (R$).</p></div>${seg('fx', [['real', 'Câmbio real'], ['budget', 'Câmbio do Budget']])}</header>
    <div class="rs-tb"><table><thead><tr><th>Grupo</th><th>CPU Budget</th><th>CPU Actual</th><th>Budget</th><th>Actual</th><th>Variação</th><th>Volume</th><th>Preço</th></tr></thead><tbody>${b.linhas.map(x => row(x)).join('')}${row(b.total, 1)}</tbody></table></div></section>`;
}
function detalhe(p) {
  const d = p.detalhe;
  if (!d) return `<section class="rs-sec"><header><div><h3>Detalhe por despesa</h3></div></header><div class="rs-empty">O detalhe por despesa deste período ${SEM}.</div></section>`;
  const dec = R.det === 'cpu' ? 3 : 0, cel = v => has(v) ? nf(v, dec) : '-';
  const dif = (a, b) => has(a) && has(b) ? `<td class="${cls(a - b)}">${sg(a - b)}${nf(Math.abs(a - b), dec)}</td><td class="${cls(a - b)}">${pc(a, b)}</td>` : '<td>-</td><td>-</td>';
  const rows = (d[R.det] || []).filter(x => has(x.budget) || has(x.actual)).map(x => `<tr class="${x.rotulo === 'Total' ? 't' : ''}"><td>${E(x.rotulo)}</td><td>${cel(x.budget)}</td><td>${cel(x.forecast)}</td><td>${cel(x.actual)}</td>${dif(x.actual, x.budget)}${dif(x.actual, x.forecast)}</tr>`).join('');
  return `<section class="rs-sec"><header><div><h3>Detalhe por despesa</h3><p>Budget, Forecast e Actual de cada linha.</p></div>${seg('det', [['custos', 'Custo (R$)'], ['cpu', 'CPU (R$)'], ['units', 'Units'], ['indicadores', 'Indicadores']])}</header>
    <div class="rs-tb"><table><thead><tr><th>Linha</th><th>Budget</th><th>Forecast</th><th>Actual</th><th>Actual vs Budget</th><th>%</th><th>Actual vs Forecast</th><th>%</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
}
function mensal(o) {
  const m = o.mensal; if (!m) return '';
  const W = 1240, H = 270, T = 26, B = 30, L = 44, c = m.custo, top = Math.max(...c.budget, ...c.forecast, ...c.actual) * 1.12;
  const pw = (W - L - 8) / 12, x = i => L + pw * i + pw / 2, y = v => H - B - v / top * (H - B - T), path = a => a.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join('');
  let s = `<defs><linearGradient id="wfM" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6FB1FF"/><stop offset="1" stop-color="#2459BC"/></linearGradient></defs>`, hit = '', rot = '';
  [0, .25, .5, .75, 1].forEach(f => { const v = top * f; s += `<line x1="${L}" x2="${W - 8}" y1="${y(v)}" y2="${y(v)}" stroke="rgba(255,255,255,.07)"/><text class="m" x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${nf(v / 1e6, 1)}</text>`; });
  m.rotulos.forEach((t, i) => { const v = c.actual[i], closed = i <= m.fechado;
    if (closed) s += `<rect x="${x(i) - pw * .28}" y="${y(v)}" width="${pw * .56}" height="${y(0) - y(v)}" rx="4" fill="url(#wfM)" class="gy" style="--i:${i}"/>`;
    if (closed) rot += `<g class="rs-pill fd" style="--i:${i}"><rect x="${x(i) - 23}" y="${y(0) - 34}" width="46" height="24" rx="12" fill="#173F96" stroke="rgba(255,255,255,.3)"/><text class="p" x="${x(i)}" y="${y(0) - 17.5}" text-anchor="middle">${nf(v / 1e6, 1)}</text></g>`;
    s += `<text x="${x(i)}" y="${H - 10}" text-anchor="middle">${t}</text>`;
    hit += `<rect x="${x(i) - pw / 2}" y="0" width="${pw}" height="${H}" fill="transparent" data-bgtip="<b>${t}</b><br>Budget ${brl(c.budget[i])}<br>Forecast ${brl(c.forecast[i])}<br>Actual ${closed ? brl(v) : '-'}"/>`; });
  s += `<path class="wp" d="${path(c.budget)}" fill="none" stroke="#E2B33C" stroke-width="2.5"/><path class="wp" d="${path(c.forecast)}" fill="none" stroke="#C9D6D0" stroke-width="2.2" stroke-dasharray="6 5"/>${rot}${hit}`;
  return `<section class="rs-sec" data-rv="mensal"><header><div><h3>Evolução mensal do custo (R$ milhões)</h3><p>Budget, Forecast e Actual de cada mês do ano.</p></div><div class="rs-leg"><span><i style="background:linear-gradient(180deg,#6FB1FF,#2459BC)"></i>Actual</span><span><i class="l" style="color:#E2B33C"></i>Budget</span><span><i class="d" style="color:#C9D6D0"></i>Forecast</span></div></header><div class="rs-pad"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Evolução mensal do custo">${s}</svg></div></section>`;
}
function proximo(o) {
  const f = o.proximo; if (!f) return '';
  const du = f.units_forecast - f.units_budget, dc = f.forecast - f.budget;
  return `<section class="rs-sec"><header><div><h3>Forecast de ${E(f.rotulo.toLowerCase())}</h3><p>Forecast comparado ao Budget do mês.</p></div></header><div class="rs-pad"><p class="rs-sum">Units: <b>${nf(f.units_forecast)}</b> no Forecast e ${nf(f.units_budget)} no Budget (<span class="${cls(du)}">${sg(du)}${nf(Math.abs(du))}</span>). Custo: <b>${brl(f.forecast)}</b> no Forecast e ${brl(f.budget)} no Budget (<span class="${cls(dc)}">${sbrl(dc)}</span>).</p></div>
    <div class="rs-tb" style="max-height:300px"><table><thead><tr><th>Despesa</th><th>Budget</th><th>Forecast</th><th>Diferença</th></tr></thead><tbody>${f.linhas.map(l => `<tr><td>${E(l.rotulo)}</td><td>${nf(l.budget)}</td><td>${nf(l.forecast)}</td><td class="${cls(l.forecast - l.budget)}">${sg(l.forecast - l.budget)}${nf(Math.abs(l.forecast - l.budget))}</td></tr>`).join('')}</tbody></table></div></section>`;
}
/* Comentarios, conferencia e arquivos: quadros recolhiveis na largura da pagina; a escolha fica guardada neste computador. */
const FOLD_KEY = 'nexus.res.quadros.abertos';
const abertos = (() => { try { return new Set(JSON.parse(localStorage.getItem(FOLD_KEY) || '[]')); } catch { return new Set(); } })();
const CHEV = svg('<path d="m6 9 6 6 6-6"/>');
function quadro(key, titulo, resumo, corpo, aviso) {
  const on = abertos.has(key);
  return `<section class="rs-sec rs-fold${on ? ' open' : ''}" data-fold="${key}"><h3 class="rs-fold-h"><button type="button" aria-expanded="${on}" aria-controls="rs-q-${key}"><span class="t">${titulo}</span><span class="s">${resumo}</span>${aviso ? `<span class="rs-badge">${IC.at}${aviso}</span>` : ''}<span class="c">${CHEV}</span></button></h3><div class="rs-fold-b" id="rs-q-${key}"${on ? '' : ' hidden'}>${corpo}</div></section>`;
}
function conferencia(o) {
  const c = o.conferencias || [], at = c.filter(x => !x.ok), ok = c.length - at.length;
  const corpo = `<div class="rs-pad rs-chk">${[...at, ...c.filter(x => x.ok)].map(x => `<div class="${x.ok ? 'ok' : 'at'}">${x.ok ? IC.ok : IC.at}<span>${E(x.nome)}${x.detalhe && !x.ok ? `<small>${E(x.detalhe)}</small>` : ''}</span></div>`).join('')}</div>`;
  return quadro('conf', 'Conferência das bases', `${ok} de ${c.length} conferências fecham`, corpo, at.length ? `${at.length} para atenção` : '');
}
function comentarios(o, p) {
  const lin = (R.data.comentarios || {})[`${o.operacao}|${R.comp}|${p.chave}`] || [], n = lin.length;
  const dst = (R.data.comentarios || {})[`${o.operacao}|${R.comp}|${p.chave}|destaques`] || [];
  const corpo = `<div class="rs-pad rs-com"><div class="rs-com-grid"><label>Comentários<textarea id="rs-com" maxlength="2400">${E(lin.join('\n'))}</textarea></label><label>Quadros de destaque na Bridge<textarea id="rs-dst" maxlength="760" placeholder="Bunker: Biocombustível e taxas de origem">${E(dst.join('\n'))}</textarea></label></div><footer><span id="rs-com-st">Uma frase por linha. Nos quadros, escreva o nome da barra, dois-pontos e o texto.</span><button class="secondary" type="button" id="rs-com-save">Salvar comentários</button></footer></div>`;
  return quadro('com', 'Comentários da apresentação', `${E(o.nome)} · ${E(p.rotulo)} · ${n ? `${n} ${n > 1 ? 'comentários' : 'comentário'}` : 'sem comentários'}`, corpo);
}
function arquivos() {
  const a = R.data.arquivos || [];
  const corpo = `<div class="rs-pad rs-files">${a.length ? a.map(f => `<div class="rs-file"><div><b title="${E(f.nome)}">${E(f.nome)}</b><small>${E(f.tipo_rotulo)}${f.operacoes.length ? ` · ${E(f.operacoes.join(', '))}` : ''}${f.competencia ? ` · ${E(compNome(f.competencia))}` : ''}${f.em_uso ? '' : ' · substituído'}</small></div><a href="/api/budget/resultados/arquivos/${f.id}" download>Baixar</a>${R.data.pode_excluir ? `<button type="button" data-del="${f.id}" data-nome="${E(f.nome)}">Excluir</button>` : ''}</div>`).join('') : '<small>Nenhum arquivo enviado.</small>'}</div>`;
  return quadro('arq', 'Arquivos enviados', `${a.length} ${a.length === 1 ? 'arquivo' : 'arquivos'} · vale o último de cada tipo, operação e mês`, corpo);
}
/* Animacao igual a do Painel: toda vez que entra na pagina, cada grafico ao aparecer na tela; ao trocar o periodo, rapida.
   Respeita Configuracoes > Meu perfil (window.nexusAnim). */
const FMT = {brl, sbrl, fx: v => nf(v, 2)};
let obsRv = null;
function conta(box, quick) {
  box.querySelectorAll('[data-n]').forEach((el, k) => {
    const to = Number(el.dataset.n), fmt = FMT[el.dataset.f], from = quick ? (R.ult[k] ?? to) : 0, final = el.textContent;
    R.ult[k] = to;
    if (from === to) return;
    const t0 = performance.now(), dur = quick ? 520 : 1100;
    const passo = now => { const p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 3); el.textContent = p < 1 ? fmt(from + (to - from) * e) : final; if (p < 1) requestAnimationFrame(passo); };
    el.textContent = fmt(from); requestAnimationFrame(passo);
  });
}
function anima(modo) {
  obsRv?.disconnect(); obsRv = null;
  const g = R.el.querySelector('.rs-kpis'), secs = [...R.el.querySelectorAll('[data-rv]')];
  if (!modo || !g || !window.nexusAnim?.enabled()) { g?.querySelectorAll('[data-n]').forEach((el, k) => { R.ult[k] = Number(el.dataset.n); }); return; }
  const quick = modo === 'quick';
  [g, ...secs].forEach(c => { c.classList.add('rv'); if (quick) c.classList.add('quick'); });
  requestAnimationFrame(() => g.classList.add('in'));
  conta(g, quick);
  if (quick || !('IntersectionObserver' in window)) { requestAnimationFrame(() => secs.forEach(c => c.classList.add('in'))); return; }
  obsRv = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); obsRv.unobserve(e.target); } }), {threshold: 0.25});
  secs.forEach(c => obsRv.observe(c));
}
function draw(modo = '') {
  const el = R.el, D = R.data;
  if (!D.operacoes.length) { el.innerHTML = `<div class="rs-sec"><div class="rs-empty"><p>Ainda não há resultados. Envie a bridge de custo ou a Ferramenta de Controle do mês.</p><button class="primary" type="button" id="rs-up">Enviar arquivos</button></div></div>`; el.querySelector('#rs-up').onclick = upload; return; }
  const o = opAtual(); R.op = o.operacao; const p = perAtual(o); R.per = p.chave;
  el.innerHTML = `<div class="rs-bar">${seg('per', o.periodos.map(x => [x.chave, x.rotulo]))}
      ${D.competencias.length > 1 ? `<select id="rs-comp" aria-label="Mês de fechamento">${D.competencias.map(c => `<option value="${c}"${c === R.comp ? ' selected' : ''}>${compNome(c)}</option>`).join('')}</select>` : ''}<span class="grow"></span>
      <button class="secondary" type="button" id="rs-deck">${IC.play}Apresentação</button><div class="rs-dd"><button class="secondary" type="button" id="rs-dl" aria-haspopup="menu" aria-expanded="false">${IC.down}Baixar apresentação</button><div class="rs-menu" id="rs-dl-menu" role="menu" hidden><a role="menuitem" href="/api/budget/resultados/apresentacao.pptx?comp=${encodeURIComponent(R.comp)}" download><b>PowerPoint</b><small>Arquivo .pptx editável</small></a><a role="menuitem" href="/api/budget/resultados/apresentacao.html?comp=${encodeURIComponent(R.comp)}" download><b>Página HTML</b><small>Abre no navegador, sem o sistema</small></a></div></div><a class="secondary" id="rs-base" title="Para mudar valores: altere a aba Editar valores e envie o arquivo em Enviar arquivos" href="/api/budget/resultados/base.xlsx?comp=${encodeURIComponent(R.comp)}" download>${IC.down}Baixar base (Excel)</a><button class="primary" type="button" id="rs-up">${IC.up}Enviar arquivos</button></div>
    ${kpis(p)}${waterfall(p)}${grupos(p)}${detalhe(p)}${mensal(o)}${proximo(o)}<div class="rs-quadros">${comentarios(o, p)}${conferencia(o)}${arquivos()}</div>`;
  el.querySelectorAll('[data-set]').forEach(b => b.onclick = () => { R[b.dataset.set] = b.dataset.v; draw(b.dataset.set === 'per' ? 'quick' : ''); });
  el.querySelectorAll('[data-fold] > .rs-fold-h button').forEach(b => b.onclick = () => {
    const s = b.closest('[data-fold]'), k = s.dataset.fold, on = !abertos.has(k);
    if (on) abertos.add(k); else abertos.delete(k);
    s.classList.toggle('open', on); b.setAttribute('aria-expanded', String(on)); s.querySelector('.rs-fold-b').hidden = !on;
    try { localStorage.setItem(FOLD_KEY, JSON.stringify([...abertos])); } catch {}
  });
  el.querySelector('#rs-comp')?.addEventListener('change', async e => { await load(e.target.value); draw('quick'); });
  el.querySelector('#rs-up').onclick = upload;
  const dl = el.querySelector('#rs-dl'), menu = el.querySelector('#rs-dl-menu'), abre = on => { menu.hidden = !on; dl.setAttribute('aria-expanded', String(on)); };
  dl.onclick = e => { e.stopPropagation(); abre(menu.hidden); };
  menu.onclick = () => abre(false);
  document.addEventListener('click', () => abre(false), {once: true});
  el.querySelector('#rs-deck').onclick = () => { const w = document.createElement('div'); w.className = 'rs-deck'; w.innerHTML = `<button type="button">Fechar</button><iframe title="Apresentação do MBR" src="/static/apresentacao/resultados.html?c=${REV}&comp=${encodeURIComponent(R.comp)}"></iframe>`; w.querySelector('button').onclick = () => w.remove(); document.body.appendChild(w); const f = w.querySelector('iframe'); f.onload = () => f.focus(); };
  el.querySelector('#rs-com-save').onclick = async () => { const st = el.querySelector('#rs-com-st'), linhas = el.querySelector('#rs-com').value.split('\n'), destaques = el.querySelector('#rs-dst').value.split('\n');
    try { await api('/api/budget/resultados/comentarios', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({operacao: o.operacao, competencia: R.comp, periodo: p.chave, linhas, destaques})}); (R.data.comentarios ||= {})[`${o.operacao}|${R.comp}|${p.chave}`] = linhas.map(x => x.trim()).filter(Boolean); R.data.comentarios[`${o.operacao}|${R.comp}|${p.chave}|destaques`] = destaques.map(x => x.trim()).filter(x => x.includes(':')); st.textContent = 'Comentários salvos.'; } catch (e) { st.textContent = e.message; } };
  el.querySelectorAll('[data-del]').forEach(b => b.onclick = async () => { if (!confirm(`Excluir "${b.dataset.nome}" do MBR?`)) return; try { await api(`/api/budget/resultados/arquivos/${b.dataset.del}`, {method: 'DELETE'}); await load(); draw(); } catch (e) { alert(e.message); } });
  anima(modo);
}
function upload() {
  const back = document.createElement('div'); back.className = 'bg-modal-back'; back.id = 'bg-modal';
  back.innerHTML = `<div class="bg-modal" role="dialog" aria-modal="true"><header><div><h2>Enviar arquivos de resultado</h2><p>Bridge de custo, Ferramenta de Controle e a base baixada daqui, depois de alterada, entram nos números. Nada é gravado antes de você confirmar.</p></div><button class="ghost" type="button" data-x>Fechar</button></header>
    <div class="body"><div class="bg-drop" id="rs-drop" tabindex="0" role="button">${IC.up}<b>Arraste os arquivos aqui</b><small>ou clique para escolher · até 5 arquivos de 20 MB · Excel, CSV, PDF, PowerPoint ou Word</small></div><input type="file" id="rs-file" multiple accept=".xlsx,.xlsm,.csv,.pdf,.pptx,.docx" hidden></div></div>`;
  document.body.appendChild(back);
  const close = () => back.remove(), drop = back.querySelector('#rs-drop'), inp = back.querySelector('#rs-file');
  back.querySelector('[data-x]').onclick = close; drop.onclick = () => inp.click();
  drop.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); inp.click(); } };
  drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); }; drop.ondragleave = () => drop.classList.remove('over');
  drop.ondrop = e => { e.preventDefault(); analyze([...e.dataTransfer.files]); }; inp.onchange = () => analyze([...inp.files]);
  async function analyze(files) {
    if (!files.length) return;
    const box = back.querySelector('.body'); box.innerHTML = '<div class="bg-loading">Lendo os arquivos e conferindo os números…</div>';
    const form = new FormData(); files.forEach(f => form.append('files', f, f.name));
    try { preview(await api('/api/budget/resultados/analisar', {method: 'POST', body: form})); } catch (e) { box.innerHTML = `<div class="notice error"><div class="grow">${E(e.message)}</div></div>`; }
  }
  function preview(pv) {
    const box = back.querySelector('.body');
    box.innerHTML = pv.arquivos.map((a, i) => `<div class="rs-up-item"><h4>${E(a.arquivo)}</h4>${a.reconhecido ? a.bases.map(b => { const at = b.conferencias.filter(c => !c.ok); return `<p>${E(b.tipo_rotulo)} · ${E(b.operacao)} · ${E(compNome(b.competencia))}${b.substitui ? ' · substitui o arquivo atual deste mês' : ''}</p>${b.alteracoes ? `<div class="rs-mud"><b>${b.total_alteracoes} ${b.total_alteracoes > 1 ? 'valores alterados' : 'valor alterado'}</b><ul>${b.alteracoes.map(x => `<li>${E(x)}</li>`).join('')}</ul>${b.efeitos.length ? `<b>O que muda na página</b><ul>${b.efeitos.map(x => `<li>${E(x)}</li>`).join('')}</ul>` : ''}${b.avisos.map(x => `<p class="rs-av">${E(x)}</p>`).join('')}</div>` : ''}<div class="rs-chk">${at.length ? at.map(c => `<div class="at">${IC.at}<span>${E(c.nome)}<small>${E(c.detalhe)}</small></span></div>`).join('') : `<div class="ok">${IC.ok}<span>Todas as ${b.conferencias.length} conferências fecham.</span></div>`}</div>`; }).join('') : `<p>${E(a.motivo)}</p>${a.pode_anexar ? `<label><input type="checkbox" data-anexo="${i}">Guardar como anexo, sem entrar nos números</label>` : ''}`}</div>`).join('') + '<div style="display:flex;justify-content:flex-end;gap:10px"><button class="secondary" type="button" data-c>Cancelar</button><button class="primary" type="button" data-ok>Confirmar envio</button></div>';
    box.querySelector('[data-c]').onclick = close;
    box.querySelector('[data-ok]').onclick = async e => { e.target.disabled = true; e.target.textContent = 'Gravando…';
      const anexos = [...box.querySelectorAll('[data-anexo]:checked')].map(c => pv.arquivos[Number(c.dataset.anexo)].arquivo);
      try { const r = await api('/api/budget/resultados/confirmar', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({token: pv.token, anexos})}); close(); await load(r.competencia || R.comp); draw(); }
      catch (err) { e.target.disabled = false; e.target.textContent = 'Confirmar envio'; alert(err.message); } };
  }
}
window.nexusBudgetRes = {mount};
})();
