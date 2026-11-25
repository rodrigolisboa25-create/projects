/* Custos › Frete internacional (24/11/2026, pedido do usuário): faturas da Asia Shipping e da DMS (Centauro) conferidas
   pelo BID mais recente com a regra da calculadora "Validação de frete.xlsx". O n8n lê os e-mails das faturas; o "ok" desta
   tela fica só no sistema: nenhum e-mail é respondido. Usa o visual da página Custos (classes cu-*). */
window.nexusFrete = (() => {
const F0 = {q: '', agente: '', modal: '', st: ''};
const S = {data: null, f: {...F0}, el: null, loading: false, sort: {k: 'recebido_em', d: -1}};
const ST = {conferida: ['Conferida pelo BID', '#3F8F4E'], divergente: ['Divergente', '#B9533F'], verificar: ['Verificar (fora do BID)', '#C9962E'],
            ok_sistema: ['Ok dado no sistema', '#2F7F8C'], aprovada: ['Aprovada por e-mail', '#1E6B3A'], devolvida: ['Devolvida ao agente', '#7C6CB0'],
            sem_arquivo: ['PDF não encontrado', '#8a8f8c']};
const LN = {ok: ['Confere', '#3F8F4E'], divergente: ['Divergente', '#B9533F'], sem_tarifa: ['Sem tarifa no BID', '#C9962E'],
            nao_cobrado: ['Prevista e não cobrada', '#8a8f8c'], nao_prevista: ['Fora do BID', '#B9533F'], indevida: ['Taxa indevida', '#B9533F']};
const E = s => esc(s == null ? '' : String(s));
const nf = (v, c = 2) => v == null || Number.isNaN(+v) ? '-' : (+v).toLocaleString('pt-BR', {minimumFractionDigits: c, maximumFractionDigits: c});
const brl = v => v == null ? '-' : 'R$ ' + nf(v);
const brd = v => v ? String(v).slice(0, 10).split('-').reverse().join('/') : '-';
const pill = st => `<span class="cu-pill" style="--c:${(ST[st] || ['', '#8a8f8c'])[1]}">${E((ST[st] || [st])[0])}</span>`;
const J = (method, obj) => ({method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(obj)});
const ICON = {
  doc: '<svg viewBox="0 0 32 32"><path d="M8 3h11l6 6v19a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 7 28V4.5A1.5 1.5 0 0 1 8.5 3z" fill="#EAF1FB" stroke="#2a5d9c" stroke-width="1.6"/><path d="M19 3v6h6" fill="#cfe0f5" stroke="#2a5d9c" stroke-width="1.6" stroke-linejoin="round"/><path d="M11 15h10M11 19h10M11 23h6" stroke="#2a5d9c" stroke-width="1.6" stroke-linecap="round"/></svg>',
  ok: '<svg viewBox="0 0 32 32"><circle cx="16" cy="16" r="12.5" fill="#E3F3E6" stroke="#2f7d45" stroke-width="1.8"/><path d="m10.5 16.5 4 4 7.5-9" fill="none" stroke="#2f7d45" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  div: '<svg viewBox="0 0 32 32"><circle cx="16" cy="16" r="12.5" fill="#FBE7E3" stroke="#b9533f" stroke-width="1.8"/><path d="M11.5 11.5l9 9M20.5 11.5l-9 9" stroke="#b9533f" stroke-width="2.6" stroke-linecap="round"/></svg>',
  ver: '<svg viewBox="0 0 32 32"><path d="M16 3.5 29.5 27h-27z" fill="#FBF1DC" stroke="#b5841f" stroke-width="1.8" stroke-linejoin="round"/><path d="M16 12v7.5M16 23v.4" stroke="#8f6610" stroke-width="2.8" stroke-linecap="round"/></svg>',
  aprov: '<svg viewBox="0 0 32 32"><rect x="4" y="7" width="24" height="18" rx="2.5" fill="#E8F2E3" stroke="#1e6b3a" stroke-width="1.6"/><path d="m5 9 11 8 11-8" fill="none" stroke="#1e6b3a" stroke-width="1.6"/><circle cx="24" cy="23" r="6" fill="#1e6b3a"/><path d="m21.4 23 1.8 1.8 3.4-3.8" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  open: '<svg viewBox="0 0 32 32"><ellipse cx="16" cy="22" rx="11" ry="4.2" fill="#B9862C"/><rect x="5" y="13" width="22" height="9" fill="#D9A441"/><ellipse cx="16" cy="13" rx="11" ry="4.2" fill="#F2C861"/><path d="M13 13h6" stroke="#B9862C" stroke-width="1.6" stroke-linecap="round"/></svg>',
};

async function load(force) {
  if (S.loading) return;
  S.loading = true;
  try { S.data = await api('/api/frete' + (force ? '?_=' + Date.now() : '')); }
  catch (e) { S.loading = false; if (S.el) S.el.innerHTML = `<div class="cu-empty">${E(e.message)}</div>`; return; }
  S.loading = false;
  if (S.el && S.el.isConnected) render();
}
// preload: dados prontos na tela de carregamento (regra do sistema: nenhuma página carrega no clique)
function preload() { return S.data ? Promise.resolve() : load(); }
// ao entrar na aba: desenha na hora com o que já veio e busca de novo em segundo plano (o n8n pode ter lido e-mails novos)
function mount(el) { S.el = el; S.animar = true; if (S.data) { render(); load(true); return; } else { el.innerHTML = '<div class="cu-empty">Carregando…</div>'; load(); } }
// Aba aberta por muito tempo (25/11/2026: o n8n leu as aprovações às 9h e a tela aberta desde antes não mostrava): confere
// a cada 2 min e ao voltar para a janela; só redesenha se algo mudou e ninguém está com fatura, quadro ou campo em uso.
async function refresh() {
  const el = S.el;
  if (S.loading || !el || !el.isConnected || !el.offsetParent || document.hidden) return;
  let novo;
  try { novo = await api('/api/frete?_=' + Date.now()); } catch (e) { return; }
  if (JSON.stringify(novo) === JSON.stringify(S.data) && !S.pend) return;
  S.data = novo;
  const ocupado = document.querySelector('.fr-gmodal, .fr-drawer') || (document.activeElement && el.contains(document.activeElement)
    && /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName));
  if (!ocupado && el.isConnected) { S.pend = false; S.animar = false; render(); } else S.pend = true;
}
setInterval(refresh, 120000);
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
document.addEventListener('focusout', () => setTimeout(() => {
  if (S.pend && S.el && S.el.isConnected && !document.querySelector('.fr-gmodal, .fr-drawer')
      && !(document.activeElement && S.el.contains(document.activeElement))) { S.pend = false; S.animar = false; render(); }
}, 0));

const rows = () => (S.data && S.data.faturas) || [];
const match = (r, f, skip) => {
  const q = f.q.trim().toLowerCase();
  if (q && !q.split(/\s+/).every(w => [r.hbl, r.processo, r.wfadim, r.exportador, r.porto, r.agente_nome, r.numero].join(' ').toLowerCase().includes(w))) return false;
  if (skip !== 'agente' && f.agente && r.agente_nome !== f.agente) return false;
  if (skip !== 'modal' && f.modal && (r.modal || '-') !== f.modal) return false;
  if (skip !== 'st' && f.st && r.status !== f.st) return false;
  return true;
};
const filtered = () => rows().filter(r => match(r, S.f));
function field(key, label, val, fmt = v => v) {
  const cnt = new Map();
  rows().filter(r => match(r, S.f, key)).forEach(r => { const v = val(r); cnt.set(v, (cnt.get(v) || 0) + 1); });
  return `<label class="cu-field${S.f[key] ? ' on' : ''}"><span>${E(label)}</span><select data-ff="${key}"><option value="">Todos</option>${[...cnt.entries()].sort((a, b) => b[1] - a[1]).map(([v, n]) => `<option value="${E(v)}"${v === S.f[key] ? ' selected' : ''}>${E(fmt(v))} (${n})</option>`).join('')}</select></label>`;
}

function bidHtml() {
  const t = S.data.tarifario || {}, n8n = S.data.n8n || {};
  const asia = t.asia ? `<b>Asia Shipping</b><span>${E(t.asia.arquivo)}</span><small>vigência ${brd((t.asia.vigencia || [])[0])} a ${brd((t.asia.vigencia || [])[1])}</small>` : '<b>Asia Shipping</b><span class="cu-muted">BID não encontrado</span>';
  const dms = t.dms ? `<b>DMS</b><span>${E(t.dms.arquivo)}</span><small>${(t.dms.abas || []).map(a => `${E(a.modal)} ${brd(a.periodo[0])} a ${brd(a.periodo[1])}`).join(' · ')}</small>` : '<b>DMS</b><span class="cu-muted">BID não encontrado</span>';
  return `<div class="fr-bid"><div class="fr-bid-t">BID em uso <small>${E(S.data.pasta_bid)}${S.data.tarifario_copia ? ' · cópia guardada no sistema (a pasta do BID não está neste computador)' : ''}</small></div>
    <div class="fr-bid-g"><div>${asia}</div><div>${dms}</div>
    <div><b>Leitura dos e-mails</b><span>${n8n.em ? 'pelo n8n em ' + E(new Date(n8n.em).toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'})) : 'ainda não começou'}</span><small>a cada 3 horas (7h às 19h), de segunda a sexta. Nenhum e-mail é respondido.</small></div></div></div>`;
}
function kpisHtml(rs) {
  const sum = (xs, k) => xs.reduce((a, r) => a + (r[k] || 0), 0);
  const by = st => rs.filter(r => r.status === st);
  const aprov = rs.filter(r => r.status === 'aprovada' || r.status === 'ok_sistema');
  const aberto = rs.filter(r => !['aprovada', 'ok_sistema', 'devolvida'].includes(r.status));
  const card = (ic, l, v, sub, st, cls = '') => `<div class="cu-kpi fr-kpi${cls}${S.f.st === st && st ? ' sel' : ''}"${st ? ` data-kst="${st}" role="button" tabindex="0"` : ''}><small><span class="cu-ic">${ICON[ic]}</span>${l}</small><b>${v}</b><em>${sub}</em></div>`;
  return `<div class="cu-kpis fr-kpis">
    ${card('doc', 'Faturas recebidas', rs.length, brl(sum(rs, 'total_fatura')))}
    ${card('ok', 'Conferidas pelo BID', by('conferida').length, 'prontas para o ok', 'conferida')}
    ${card('div', 'Divergentes', by('divergente').length, brl(sum(by('divergente'), 'diferenca')) + ' acima do BID', 'divergente', by('divergente').length ? ' warn' : '')}
    ${card('ver', 'Verificar (fora do BID)', by('verificar').length, 'proposta spot ou sem tarifa', 'verificar')}
    ${card('aprov', 'Aprovadas', aprov.length, `${by('aprovada').length} por e-mail · ${by('ok_sistema').length} no sistema`)}
    ${card('open', 'Em aberto', aberto.length, brl(sum(aberto, 'total_fatura')))}</div>`;
}
const COLS = [['recebido_em', 'Recebida'], ['agente_nome', 'Agente'], ['hbl', 'HBL'], ['wfadim', 'WFADIM'], ['modal', 'Modal'], ['porto', 'Origem'],
  ['etd', 'Embarque'], ['total_fatura', 'Fatura', 'n'], ['total_bid', 'Pelo BID', 'n'], ['diferenca', 'Diferença', 'n'], ['status', 'Situação'], ['', 'Motivo']];
function tableHtml(rs) {
  const {k, d} = S.sort;
  const s = [...rs].sort((a, b) => { const x = a[k], y = b[k]; if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1; return (x > y ? 1 : x < y ? -1 : 0) * d; });
  return `<div class="cu-table fr-table"><table><thead><tr>${COLS.map(([c, l, n]) => `<th class="${n || ''}${c ? ' sort' : ''}${c === k ? ' on' : ''}"${c ? ` data-fsort="${c}"` : ''}>${l}${c === k ? (d > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr></thead><tbody>
    ${s.map(r => `<tr data-fid="${E(r.id)}" tabindex="0"><td>${brd(r.recebido_em)}</td><td>${E(r.agente_nome)}</td><td><b>${E(r.hbl || '-')}</b></td><td>${E(r.wfadim || '-')}</td>
      <td>${E(r.modal || '-')}</td><td>${E(r.porto || r.pol || '-')}</td><td>${brd(r.etd)}</td><td class="n"><b>${brl(r.total_fatura)}</b></td><td class="n">${brl(r.total_bid)}</td>
      <td class="n${r.diferenca && Math.abs(r.diferenca) > 1 ? ' fr-dif' : ''}">${r.diferenca == null ? '-' : brl(r.diferenca)}</td><td>${pill(r.status)}</td>
      <td class="fr-mot" title="${E((r.motivos || []).join('\n'))}">${E(r.status === 'aprovada' ? `aprovada por ${personName(r.aprovacao.por)} em ${brd(r.aprovacao.em)}` : r.status === 'ok_sistema' ? `ok de ${personName(r.conferencia.por)} em ${brd(r.conferencia.em)}` : r.status === 'devolvida' ? `devolvida por ${personName(r.conferencia.por)}: ${r.conferencia.nota || ''}` : r.resumo || (r.motivos || [])[0] || '')}</td></tr>`).join('')}
    </tbody></table></div>`;
}
/* ---------- Gráficos (pedido do usuário: quantidade e valor por situação etc., no estilo de Custos, com animação) ---------- */
const curto = v => v == null ? '-' : Math.abs(v) >= 1e6 ? 'R$ ' + nf(v / 1e6, 2) + ' mi' : Math.abs(v) >= 1e3 ? 'R$ ' + nf(v / 1e3, 1) + ' mil' : brl(v);
const ORDEM = ['conferida', 'divergente', 'verificar', 'aprovada', 'ok_sistema', 'devolvida', 'sem_arquivo'];
/* Painel de gráficos (pedido do usuário: fora do meio da tela, abre num botão; gráficos com borda, eixos, linhas de grade
   e rótulos de dados, com animação). Usa as linhas com os filtros da tela. */
const sumV = xs => xs.reduce((a, r) => a + (r.total_fatura || 0), 0);
const gid = c => 'frg' + c.replace('#', '');
const gradDefs = cores => `<defs>${[...new Set(cores)].map(c => `<linearGradient id="${gid(c)}" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="${c}"/><stop offset=".65" stop-color="${c}" stop-opacity=".85"/><stop offset="1" stop-color="${c}" stop-opacity=".6"/></linearGradient><linearGradient id="${gid(c)}v" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="${c}"/><stop offset="1" stop-color="${c}" stop-opacity=".62"/></linearGradient>`).join('')}</defs>`;
const ticks = (mx, n = 4) => { const p = Math.pow(10, Math.floor(Math.log10(mx / n || 1))); const passo = [1, 2, 2.5, 5, 10].map(k => k * p).find(s => s * n >= mx) || mx / n; return Array.from({length: n + 1}, (_, i) => i * passo); };
const eixo = v => v >= 1e6 ? nf(v / 1e6, 1) + ' mi' : v >= 1e3 ? nf(v / 1e3, 0) + ' mil' : nf(v, 0);
function donut(itens, centro, sub, attr = 'kst', col = 'Situação') {
  const R = 74, C = 2 * Math.PI * R, tot = itens.reduce((a, x) => a + x.n, 0) || 1;
  let acc = 0;
  const segs = itens.map((x, i) => { const len = x.n / tot * C, s = `<circle class="fr-seg" style="--i:${i}" cx="100" cy="100" r="${R}" fill="none" stroke="${x.cor}" stroke-width="30" stroke-dasharray="${Math.max(len - 2, 0.5).toFixed(2)} ${C.toFixed(2)}" stroke-dashoffset="${(-acc).toFixed(2)}" transform="rotate(-90 100 100)" data-${attr}="${x.k}"><title>${E(x.nome)}: ${x.n} (${nf(x.n / tot * 100, 0)}%) · ${brl(x.v)}</title></circle>`; acc += len; return s; }).join('');
  return `<div class="fr-dn"><svg viewBox="0 0 200 200" class="fr-svg fr-dsvg" role="img" aria-label="Faturas por situação"><circle cx="100" cy="100" r="${R}" fill="none" stroke="#eef2ec" stroke-width="30"/>${segs}
      <text x="100" y="96" text-anchor="middle" class="fr-dc" style="font-size:${String(centro).length > 6 ? 17 : 30}px">${E(centro)}</text><text x="100" y="117" text-anchor="middle" class="fr-ds">${sub}</text></svg>
    <table class="fr-dleg"><thead><tr><th>${col}</th><th class="n">Faturas</th><th class="n">%</th><th class="n">Valor</th></tr></thead><tbody>${itens.map(x => `<tr data-${attr}="${x.k}" role="button" tabindex="0"><td><i style="background:${x.cor}"></i>${E(x.nome)}</td><td class="n"><b>${x.n}</b></td><td class="n">${nf(x.n / tot * 100, 0)}%</td><td class="n">${curto(x.v)}</td></tr>`).join('')}</tbody></table></div>`;
}
function barrasH(itens, opt = {}) {
  // itens: {nome, sub, v, cor, attrs}
  const W = opt.W || 620, L = 150, RT = 92, rowH = 36, top = 8, H = top + itens.length * rowH + 26, mx = Math.max(1, ...itens.map(x => Math.abs(x.v)));
  const tk = ticks(mx), mxT = tk[tk.length - 1] || 1, x = v => L + (W - L - RT) * Math.abs(v) / mxT;
  return `<svg viewBox="0 0 ${W} ${H}" class="fr-svg" role="img" aria-label="${E(opt.rotulo || '')}">${gradDefs(itens.map(i => i.cor))}
    ${tk.map(t => `<line x1="${x(t)}" x2="${x(t)}" y1="${top - 2}" y2="${H - 22}" class="fr-grid"/><text x="${x(t)}" y="${H - 8}" text-anchor="middle" class="fr-ax">${eixo(t)}</text>`).join('')}
    <line x1="${L}" x2="${L}" y1="${top - 2}" y2="${H - 22}" class="fr-axl"/>
    ${itens.map((it, i) => { const y = top + i * rowH, w = Math.max(x(it.v) - L, 2);
      return `<g class="fr-row" ${it.attrs || ''}><text x="${L - 10}" y="${y + 15}" text-anchor="end" class="fr-lb">${E(it.nome)}</text>${it.sub ? `<text x="${L - 10}" y="${y + 28}" text-anchor="end" class="fr-sb">${E(it.sub)}</text>` : ''}
        <rect class="fr-bar" style="--i:${i}" x="${L}" y="${y + 6}" width="${w.toFixed(1)}" height="20" rx="3" fill="url(#${gid(it.cor)})"><title>${E(it.nome)}: ${E(opt.fmt ? opt.fmt(it.v) : brl(it.v))}</title></rect>
        <text x="${L + w + 8}" y="${y + 21}" class="fr-val" style="--i:${i}">${E(opt.fmt ? opt.fmt(it.v) : curto(it.v))}</text></g>`; }).join('')}</svg>`;
}
function empilhado(ags, sts, rs) {
  const W = 620, L = 150, RT = 92, rowH = 52, top = 8, H = top + ags.length * rowH + 26;
  const tots = ags.map(a => sumV(rs.filter(r => r.agente_nome === a))), mx = Math.max(1, ...tots);
  const tk = ticks(mx), mxT = tk[tk.length - 1] || 1, sx = v => (W - L - RT) * v / mxT;
  return `<svg viewBox="0 0 ${W} ${H}" class="fr-svg" role="img" aria-label="Valor por agente e situação">
    ${tk.map(t => `<line x1="${L + sx(t)}" x2="${L + sx(t)}" y1="${top - 2}" y2="${H - 22}" class="fr-grid"/><text x="${L + sx(t)}" y="${H - 8}" text-anchor="middle" class="fr-ax">${eixo(t)}</text>`).join('')}
    <line x1="${L}" x2="${L}" y1="${top - 2}" y2="${H - 22}" class="fr-axl"/>
    ${ags.map((a, i) => { const y = top + i * rowH, xs = rs.filter(r => r.agente_nome === a); let acc = L;
      const segs = sts.map(s => { const ys = xs.filter(r => r.status === s), v = sumV(ys); if (!v) return ''; const w = sx(v), g = `<rect class="fr-bar" style="--i:${i}" x="${acc.toFixed(1)}" y="${y + 8}" width="${Math.max(w - 1.5, 1).toFixed(1)}" height="28" fill="${ST[s][1]}" data-kst="${s}" data-ag="${E(a)}"><title>${E(a)} · ${E(ST[s][0])}: ${ys.length} fatura(s), ${brl(v)}</title></rect>${w > 26 ? `<text x="${(acc + w / 2).toFixed(1)}" y="${y + 27}" text-anchor="middle" class="fr-in">${ys.length}</text>` : ''}`; acc += w; return g; }).join('');
      return `<text x="${L - 10}" y="${y + 21}" text-anchor="end" class="fr-lb">${E(a)}</text><text x="${L - 10}" y="${y + 35}" text-anchor="end" class="fr-sb">${xs.length} fatura${xs.length > 1 ? 's' : ''}</text>${segs}
        <text x="${acc + 8}" y="${y + 27}" class="fr-val" style="--i:${i}">${curto(tots[i])}</text>`; }).join('')}</svg>
    <div class="fr-leg2">${sts.map(s => `<span><i style="background:${ST[s][1]}"></i>${E(ST[s][0])}</span>`).join('')}<em>número dentro da barra = faturas</em></div>`;
}
function colunas(ks, sem) {
  const W = 620, H = 270, L = 58, B = 46, T = 22, R = 10, mx = Math.max(1, ...ks.map(k => sumV(sem[k])));
  const tk = ticks(mx), mxT = tk[tk.length - 1] || 1, y = v => T + (H - T - B) * (1 - v / mxT), cw = (W - L - R) / ks.length;
  return `<svg viewBox="0 0 ${W} ${H}" class="fr-svg" role="img" aria-label="Faturas recebidas por semana">${gradDefs(['#2F5D8A'])}
    ${tk.map(t => `<line x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}" class="fr-grid"/><text x="${L - 8}" y="${y(t) + 4}" text-anchor="end" class="fr-ax">${eixo(t)}</text>`).join('')}
    <line x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}" class="fr-axl"/>
    ${ks.map((k, i) => { const v = sumV(sem[k]), x = L + i * cw + cw * 0.22, w = cw * 0.56;
      return `<rect class="fr-col" style="--i:${i}" x="${x.toFixed(1)}" y="${y(v).toFixed(1)}" width="${w.toFixed(1)}" height="${(y(0) - y(v)).toFixed(1)}" rx="3" fill="url(#${gid('#2F5D8A')}v)"><title>Semana de ${brd(k)}: ${brl(v)} em ${sem[k].length} fatura(s)</title></rect>
        <text x="${(x + w / 2).toFixed(1)}" y="${(y(v) - 7).toFixed(1)}" text-anchor="middle" class="fr-val" style="--i:${i}">${curto(v)}</text>
        <text x="${(x + w / 2).toFixed(1)}" y="${H - B + 17}" text-anchor="middle" class="fr-lb">${brd(k).slice(0, 5)}</text><text x="${(x + w / 2).toFixed(1)}" y="${H - B + 32}" text-anchor="middle" class="fr-sb">${sem[k].length} fatura${sem[k].length > 1 ? 's' : ''}</text>`; }).join('')}</svg>`;
}
function graficosHtml(rs) {
  const sts = ORDEM.filter(s => rs.some(r => r.status === s));
  const porSt = sts.map(s => { const xs = rs.filter(r => r.status === s); return {k: s, nome: ST[s][0], cor: ST[s][1], n: xs.length, v: sumV(xs)}; });
  const ags = [...new Set(rs.map(r => r.agente_nome))];
  // LCL × FCL (pedido do usuário): quantidade e valor por modal, separado por agente; LCL em azul, FCL em terracota
  const COR_MOD = {'LCL|Asia Shipping': '#2F5D8A', 'LCL|DMS': '#7FA3C7', 'FCL|Asia Shipping': '#B0603F', 'FCL|DMS': '#D99A74'};
  const porModal = ['LCL', 'FCL'].flatMap(m => ags.map(a => { const xs = rs.filter(r => (r.modal || 'LCL') === m && r.agente_nome === a);
    return xs.length ? {k: `${m}|${a}`, nome: `${m} · ${a}`, cor: COR_MOD[`${m}|${a}`] || '#8a8f8c', n: xs.length, v: sumV(xs)} : null; })).filter(Boolean);
  const seg = iso => { const d = new Date(String(iso).slice(0, 10) + 'T12:00:00'); d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); return d.toISOString().slice(0, 10); };
  const sem = {};
  rs.filter(r => r.recebido_em).forEach(r => { const k = seg(r.recebido_em); (sem[k] = sem[k] || []).push(r); });
  const ks = Object.keys(sem).sort().slice(-12);
  const dif = rs.filter(r => r.diferenca != null && Math.abs(r.diferenca) > 0.5).sort((a, b) => Math.abs(b.diferenca) - Math.abs(a.diferenca)).slice(0, 8);
  const comBid = rs.filter(r => r.total_bid != null);
  const card = (titulo, sub, corpo, cls = '') => `<section class="fr-gc${cls}"><header><h3>${titulo}</h3><small>${sub}</small></header>${corpo}</section>`;
  return `<div class="fr-gk"><div><small>Faturas</small><b>${rs.length}</b></div><div><small>Valor faturado</small><b>${brl(sumV(rs))}</b></div>
      <div><small>Conferível pelo BID</small><b>${comBid.length} de ${rs.length}</b></div><div><small>Diferença total sobre o BID</small><b>${brl(comBid.reduce((a, r) => a + (r.diferenca || 0), 0))}</b></div></div>
    <div class="fr-gg">
    ${card('Faturas por situação', 'quantidade e valor · clique para filtrar a lista', donut(porSt, String(rs.length), rs.length === 1 ? 'fatura' : 'faturas'))}
    ${card('LCL × FCL', 'quantidade e valor por modal e agente · clique para filtrar', donut(porModal, curto(sumV(rs)), 'faturado', 'kmod', 'Modal · agente'))}
    ${card('Valor por situação', 'soma do total das faturas · clique para filtrar', barrasH(porSt.map(p => ({nome: p.nome, sub: `${p.n} fatura${p.n > 1 ? 's' : ''}`, v: p.v, cor: p.cor, attrs: `data-kst="${p.k}" role="button"`})), {rotulo: 'Valor por situação'}))}
    ${card('Valor por agente', 'dividido pela situação · clique num trecho para filtrar', empilhado(ags, sts, rs))}
    ${card('Faturas recebidas por semana', 'valor total por semana do e-mail', ks.length ? colunas(ks, sem) : '<p class="cu-muted">Sem faturas.</p>')}
    ${card('Maiores diferenças em relação ao BID', 'cobrado menos o BID · clique para abrir a fatura', dif.length ? barrasH(dif.map(r => ({nome: r.hbl, sub: r.agente_nome, v: r.diferenca, cor: r.diferenca > 0 ? '#B9533F' : '#3F7FB0', attrs: `data-fid="${E(r.id)}" role="button"`})), {fmt: brl, rotulo: 'Diferenças'}) : '<p class="cu-muted fr-nodif">Nenhuma fatura com diferença em relação ao BID.</p>')}
    </div>`;
}
function graficos() {
  if (!S.data) return;
  document.getElementById('fr-gmodal')?.remove();
  const rs = filtered(), n = Object.values(S.f).filter(Boolean).length;
  const box = document.createElement('div'); box.className = 'fr-gback'; box.id = 'fr-gmodal';
  box.innerHTML = `<div class="fr-gmodal${animOn() ? ' anim' : ''}" role="dialog" aria-label="Gráficos da validação de frete"><header class="fr-gh"><div><div class="eyebrow">Frete internacional · Asia Shipping e DMS</div>
      <h2>Gráficos da validação de frete</h2><p>${n ? `Com os filtros da tela (${n} ativo${n > 1 ? 's' : ''}).` : 'Todas as faturas recebidas.'}</p></div><button class="cu-x" type="button" aria-label="Fechar">×</button></header>
    ${rs.length ? graficosHtml(rs) : '<div class="cu-empty">Nenhuma fatura com estes filtros.</div>'}</div>`;
  document.body.appendChild(box);
  const fecha = () => { box.remove(); document.removeEventListener('keydown', esc1, true); };
  const esc1 = e => { if (e.key === 'Escape') { e.stopPropagation(); fecha(); } };
  document.addEventListener('keydown', esc1, true);
  box.addEventListener('mousedown', e => { if (e.target === box) fecha(); });
  box.querySelector('.cu-x').addEventListener('click', fecha);
  box.querySelectorAll('[data-kst]').forEach(b => b.addEventListener('click', () => { S.f.st = b.dataset.kst; if (b.dataset.ag) S.f.agente = b.dataset.ag; fecha(); render(); }));
  box.querySelectorAll('[data-fid]').forEach(b => b.addEventListener('click', () => { fecha(); ficha(b.dataset.fid); }));
  box.querySelectorAll('[data-kmod]').forEach(b => b.addEventListener('click', () => { const [m, a] = b.dataset.kmod.split('|'); S.f.modal = m; S.f.agente = a; fecha(); render(); }));
}
const animOn = () => !window.nexusAnim || window.nexusAnim.enabled();
function render() {
  if (!S.el || !S.data) return;
  const rs = filtered(), n = Object.values(S.f).filter(Boolean).length;
  const erros = Object.entries(S.data.erros_bid || {});
  S.el.innerHTML = `${bidHtml()}${erros.length ? `<div class="fr-alert">Não foi possível ler o BID: ${erros.map(([k, v]) => `${E(k)} (${E(v)})`).join('; ')}.</div>` : ''}${kpisHtml(rows())}
    <div class="cu-fpanel"><div class="cu-frow"><div class="cu-search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></svg><input type="search" id="fr-q" placeholder="Buscar HBL, processo, WFADIM, exportador…" value="${E(S.f.q)}"></div>
      <span class="cu-fcount">${n ? `${n} filtro${n > 1 ? 's' : ''} ativo${n > 1 ? 's' : ''}` : 'Nenhum filtro'}</span><button type="button" class="cu-btn ghost" id="fr-clear"${n ? '' : ' disabled'}>Limpar filtros</button></div>
      <div class="cu-fgrid fr-fgrid">${field('agente', 'Agente', r => r.agente_nome)}${field('modal', 'Modal', r => r.modal || '-')}${field('st', 'Situação', r => r.status, v => (ST[v] || [v])[0])}</div></div>
    ${rs.length ? tableHtml(rs) : '<div class="cu-empty">Nenhuma fatura com estes filtros.</div>'}
    <p class="cu-note">Conferida = todas as cobranças batem com o BID (tolerância de R$ 0,50 por cobrança, arredondamento do agente). Verificar = carga acima da última faixa do BID ou taxa sem tarifa: conferir com a proposta da equipe que negocia o frete.</p>`;
  S.animar = false;  // anima ao entrar na aba; filtrar não anima de novo
  bind();
}
function bind() {
  const r0 = S.el;
  r0.querySelectorAll('select[data-ff]').forEach(s => s.addEventListener('change', () => { S.f[s.dataset.ff] = s.value; render(); }));
  const q = r0.querySelector('#fr-q');
  if (q) { let t; q.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => { S.f.q = q.value; const p = q.selectionStart; render(); const n = S.el.querySelector('#fr-q'); n.focus(); n.setSelectionRange(p, p); }, 250); }); }
  r0.querySelector('#fr-clear')?.addEventListener('click', () => { S.f = {...F0}; render(); });
  r0.querySelectorAll('[data-kst]').forEach(b => b.addEventListener('click', () => {
    S.f.st = S.f.st === b.dataset.kst ? '' : b.dataset.kst;
    if (b.dataset.ag) S.f.agente = S.f.st ? b.dataset.ag : '';
    render();
  }));
  r0.querySelectorAll('.cu-hb[data-fid]').forEach(b => b.addEventListener('click', () => ficha(b.dataset.fid)));
  r0.querySelectorAll('[data-fsort]').forEach(th => th.addEventListener('click', () => { const k = th.dataset.fsort; S.sort = {k, d: S.sort.k === k ? -S.sort.d : -1}; render(); }));
  r0.querySelectorAll('tr[data-fid]').forEach(tr => { const go = () => ficha(tr.dataset.fid); tr.addEventListener('click', go); tr.addEventListener('keydown', e => { if (e.key === 'Enter') go(); }); });
}

/* ---------- Ficha da fatura ---------- */
function fechar() { document.getElementById('fr-drawer')?.remove(); document.removeEventListener('keydown', escFecha, true); }
function escFecha(e) { if (e.key === 'Escape') { e.stopPropagation(); fechar(); } }
async function ficha(fid) {
  fechar();
  const box = document.createElement('div'); box.className = 'cu-drawer-back'; box.id = 'fr-drawer';
  box.innerHTML = '<aside class="cu-drawer fr-drawer" role="dialog" aria-label="Fatura de frete internacional"><div class="cu-empty">Carregando…</div></aside>';
  document.body.appendChild(box);
  box.addEventListener('mousedown', e => { if (e.target === box) fechar(); });
  document.addEventListener('keydown', escFecha, true);
  let d; try { d = await api('/api/frete/fatura/' + encodeURIComponent(fid)); } catch (e) { box.querySelector('aside').innerHTML = `<div class="cu-empty">${E(e.message)}</div>`; return; }
  const l = d.linha, v = d.validacao || {}, b = v.base || {}, t = v.tarifa || {}, f = d.fup || {};
  const kv = (k, x, cls = '') => x != null && x !== '' ? `<div class="fr-kv ${cls}"><dt>${E(k)}</dt><dd title="${E(x)}">${E(x)}</dd></div>` : '';
  // Busca a fatura pelo HBL no Gmail da pessoa (conta principal do navegador). Testado pelo usuário em 24/11/2026:
  // "?authuser=<e-mail>" perde a busca no redirecionamento e "/mail/u/<e-mail>/" dá erro 404 na conta do Grupo SBF.
  const gmail = `https://mail.google.com/mail/u/0/#search/${encodeURIComponent(d.busca || '')}`;
  const cont = Object.entries(b.conteineres || {}).map(([k, n]) => `${n} × ${k}`).join(', ');
  const linhas = (v.linhas || []).map(ln => `<tr class="fr-l-${ln.status}"><td><b>${E(ln.nome)}</b>${ln.cobrado.length ? `<small>${E(ln.cobrado.map(c => c.descricao).join(' / ').slice(0, 140))}</small>` : ''}</td>
      <td class="n">${ln.cobrado.length ? ln.cobrado.map(c => `${E(c.moeda)} ${nf(c.valor)}`).join('<br>') : '-'}</td><td class="n"><b>${brl(ln.cobrado_brl)}</b></td>
      <td class="n">${ln.esperado_brl == null ? '-' : brl(ln.esperado_brl)}</td><td class="n${ln.dif && Math.abs(ln.dif) > 0.5 ? ' fr-dif' : ''}">${ln.dif == null ? '-' : brl(ln.dif)}</td>
      <td class="fr-regra">${E(ln.regra)}</td><td><span class="cu-pill" style="--c:${(LN[ln.status] || ['', '#8a8f8c'])[1]}">${E((LN[ln.status] || [ln.status])[0])}</span></td></tr>`).join('');
  const conf = l.conferencia, aprov = l.aprovacao;
  const acoes = aprov ? `<div class="fr-done">${ICON.aprov}<div><b>Aprovada por e-mail</b> por ${E(personName(aprov.por))} em ${brd(aprov.em)}<small>“${E(aprov.trecho || '')}”</small></div></div>`
    : conf ? `<div class="fr-done${conf.acao === 'devolver' ? ' dev' : ''}">${conf.acao === 'ok' ? ICON.ok : ICON.div}<div><b>${conf.acao === 'ok' ? 'Ok dado no sistema' : 'Devolvida ao agente'}</b> por ${E(personName(conf.por))} em ${brd(conf.em)}${conf.nota ? `<small>${E(conf.nota)}</small>` : ''}</div><button type="button" class="cu-btn ghost" data-facao="desfazer">Desfazer</button></div>`
    : `<div class="fr-act"><label for="fr-nota">Observação ${l.situacao === 'conferida' ? '(opcional)' : '(obrigatória para dar o ok fora do BID e para devolver)'}</label>
        <textarea id="fr-nota" rows="2" maxlength="600" placeholder="${l.situacao === 'conferida' ? 'Ex.: conferido com a calculadora' : 'Ex.: proposta spot aprovada pela equipe de frete em 20/10'}"></textarea>
        <div class="fr-act-b"><button type="button" class="cu-btn" data-facao="ok">${ICON.ok}Dar ok no sistema</button><button type="button" class="cu-btn ghost" data-facao="devolver" title="Marca a fatura como devolvida ao agente, com o motivo. O e-mail ao agente continua sendo feito por você.">Registrar devolução ao agente</button>
        <span class="cu-muted">O ok e a devolução ficam registrados só no NexxusDoc, com o seu nome. Nenhum e-mail é enviado ao agente.</span></div><div class="fr-msg" id="fr-msg" role="status"></div></div>`;
  box.querySelector('aside').innerHTML = `<header><div><div class="eyebrow">${E(l.agente_nome)} · ${E(l.modal || '-')}${l.porto ? ' · ' + E(l.porto) : ''}</div><h2>HBL ${E(l.hbl || '-')}</h2><div>${pill(l.status)}${l.wfadim ? ` <span class="cu-tag">${E(l.wfadim)}</span>` : ''}</div></div><button class="cu-x" type="button" aria-label="Fechar">×</button></header>
    <div class="cu-sum fr-sum"><div><small>Total da fatura</small><b>${brl(l.total_fatura)}</b></div><div><small>Total pelo BID</small><b>${brl(l.total_bid)}</b></div>
      <div><small>Diferença</small><b class="${l.diferenca && Math.abs(l.diferenca) > 1 ? 'fr-dif' : ''}">${l.diferenca == null ? '-' : brl(l.diferenca)}</b></div>
      <div><small>Frete internacional</small><b>${l.frete_usd ? 'USD ' + nf(l.frete_usd) : '-'}</b></div><div><small>Taxa do dólar da fatura</small><b>${l.taxa ? nf(l.taxa, 4) : '-'}</b></div>
      <div><small>Vencimento</small><b>${brd(l.vencimento)}</b></div></div>
    ${(v.motivos || []).length ? `<div class="fr-box red">${(v.motivos || []).map(m => `<p>${E(m)}</p>`).join('')}</div>` : '<div class="fr-box green"><p>Todas as cobranças conferem com o BID.</p></div>'}
    ${(v.avisos || []).length ? `<div class="fr-box gray">${v.avisos.map(m => `<p>${E(m)}</p>`).join('')}</div>` : ''}
    <div class="fr-links"><a class="cu-btn ghost" href="/api/frete/fatura/${encodeURIComponent(l.id)}/pdf" target="_blank" rel="noopener">${ICON.doc}Abrir a fatura (PDF)</a>
      <a class="cu-btn ghost" href="${E(gmail)}" target="_blank" rel="noopener" title="Abre a busca no seu próprio Gmail. O e-mail aparece se você estava em cópia na fatura do agente.">Procurar o e-mail no meu Gmail</a></div>
    ${acoes}
    <h3>Cobranças da fatura × BID</h3>
    <div class="cu-table small fr-ltab"><table><thead><tr><th>Cobrança</th><th class="n">Na fatura</th><th class="n">Cobrado (R$)</th><th class="n">Pelo BID (R$)</th><th class="n">Diferença</th><th>Regra do BID</th><th>Situação</th></tr></thead><tbody>${linhas}
      <tr class="tot"><td>Total</td><td></td><td class="n">${brl(l.total_fatura)}</td><td class="n">${brl(l.total_bid)}</td><td class="n">${l.diferenca == null ? '-' : brl(l.diferenca)}</td><td colspan="2"></td></tr></tbody></table></div>
    <div class="fr-det">
      <section class="fr-dcard"><h4>${ICON.doc}BID usado</h4><dl>${kv('Arquivo', t.arquivo, 'fr-arq')}${kv('Aba', t.aba)}${kv('Período / vigência', t.periodo ? brd(t.periodo[0]) + ' a ' + brd(t.periodo[1]) : '')}${kv('Porto de origem', t.porto)}${kv('Faixa LCL', t.faixa)}${kv('Grupo de armadores', t.grupo_armador)}</dl></section>
      <section class="fr-dcard"><h4>${ICON.open}Base do embarque <small>${E(b.fonte || '')}</small></h4><dl>${kv('Cubagem', b.cubagem == null ? '' : nf(b.cubagem, 3) + ' m³')}${kv('Peso bruto', b.peso == null ? '' : nf(b.peso, 1) + ' kg')}${kv('W/M usado', b.wm == null ? '' : nf(b.wm, 3))}${kv('Contêineres', cont)}
        ${(b.confere || []).map(c => `<div class="fr-kv fr-cmp"><dt>${E(c.campo)}<small>fatura × FUP da PGL</small></dt><dd><span>${E(typeof c.fatura === 'number' ? nf(c.fatura, /peso/i.test(c.campo) ? 1 : 3) : brd(c.fatura))} × ${E(typeof c.fup === 'number' ? nf(c.fup, /peso/i.test(c.campo) ? 1 : 3) : brd(c.fup))}</span><span class="cu-pill" style="--c:${c.ok ? '#3F8F4E' : '#C9962E'}">${c.ok ? 'Igual' : 'Diferente'}</span></dd></div>`).join('')}</dl></section>
      <section class="fr-dcard"><h4>${ICON.aprov}Processo</h4><dl>${kv('Processo do agente', l.processo)}${kv('WFADIM', l.wfadim)}${kv('Exportador', l.exportador)}${kv('Armador', l.armador)}${kv('Embarque', l.etd ? brd(l.etd) : '')}${kv('Chegada prevista', l.eta ? brd(l.eta) : '')}${kv('Registro da DI', f.registro_di ? brd(f.registro_di) : '')}${kv('Situação no FUP', f.status)}${kv('E-mail recebido', l.recebido_em ? brd(l.recebido_em) : '')}</dl></section></div>`;
  box.querySelector('.cu-x').addEventListener('click', fechar);
  box.querySelectorAll('[data-facao]').forEach(btn => btn.addEventListener('click', async () => {
    const acao = btn.dataset.facao, nota = (box.querySelector('#fr-nota') || {}).value || '';
    const msg = box.querySelector('#fr-msg');
    btn.disabled = true;
    try {
      await api('/api/frete/fatura/' + encodeURIComponent(fid) + '/conferencia', J('POST', {acao, nota}));
      await load(true); ficha(fid);
    } catch (e) { btn.disabled = false; if (msg) { msg.textContent = e.message; msg.className = 'fr-msg err'; } }
  }));
}

/* ---------- Parâmetros da calculadora (pedido do usuário: configuráveis, por agente) ---------- */
const num = s => { const t = String(s == null ? '' : s).trim().replace(/\s/g, ''); if (!t) return null; const v = Number(t.includes(',') ? t.replace(/\./g, '').replace(',', '.') : t); return Number.isFinite(v) ? v : NaN; };
const CAMPOS = [
  ['geral', 'Geral', [['tolerancia_cobranca', 'Tolerância por cobrança', 'R$', 1, 'Diferença aceita entre a fatura e o BID em cada cobrança (arredondamento do agente).'],
                      ['tolerancia_total', 'Tolerância no total da fatura', 'R$', 1, 'Diferença aceita entre a soma das cobranças e o total a pagar.']]],
  ['asia', 'Asia Shipping', [['iof', 'IOF', '%', 100, 'Percentual sobre o frete internacional (e adicionais) em dólar.'],
                             ['peso_max_lcl_t', 'Peso máximo do LCL', 't', 1, 'Acima disso o BID prevê adicional de overweight: a fatura ganha um aviso.'],
                             ['min_wm', 'Mínimo de W/M no frete LCL', 'W/M', 1, '0 = sem mínimo (a cobrança é pela W/M da carga).'],
                             ['bid', 'Qual BID usar', '', 0, 'Mais recente: o arquivo mais novo da pasta. Vigente: o BID cuja vigência cobre a data de embarque (inclui a pasta Anteriores).']]],
  ['dms', 'DMS', [['iof', 'IOF', '%', 100, 'Vazio = o percentual do próprio BID da DMS.'],
                  ['repasse', 'PIS/COFINS sobre a desconsolidação', '%', 100, 'Vazio = o percentual do próprio BID da DMS (14,25%).'],
                  ['peso_max_lcl_t', 'Peso máximo do LCL', 't', 1, 'Acima disso a proposta da DMS pode ter overweight: a fatura ganha um aviso.'],
                  ['min_wm', 'Mínimo de W/M nas taxas locais', 'W/M', 1, 'Capatazia e desconsolidação cobram no mínimo esta W/M (a calculadora usa 1).']]],
];
async function parametrosModal() {
  document.getElementById('fr-pmodal')?.remove();
  let d; try { d = await api('/api/frete/parametros'); } catch (e) { alert(e.message); return; }
  const pode = d.pode_editar, v = d.valores;
  const valor = (g, k, mult) => { const x = v[g][k]; return x == null ? '' : mult === 100 ? nf(x * 100, 2).replace(/,00$/, '') : nf(x, 2).replace(/,00$/, ''); };
  const campo = (g, [k, rot, un, mult, dica]) => k === 'bid'
    ? `<label class="fr-pf wide"><span>${E(rot)}</span><select data-pg="${g}" data-pk="${k}"${pode ? '' : ' disabled'}>${Object.entries(d.regras_bid).map(([a, b]) => `<option value="${a}"${v[g][k] === a ? ' selected' : ''}>${E(b)}${a === d.padrao[g][k] ? ' (padrão)' : ''}</option>`).join('')}</select><small>${E(dica)}</small></label>`
    : `<label class="fr-pf"><span>${E(rot)}</span><div class="fr-pin"><input type="text" inputmode="decimal" data-pg="${g}" data-pk="${k}" data-mult="${mult}" value="${valor(g, k, mult)}" placeholder="${d.padrao[g][k] == null ? 'do BID' : ''}"${pode ? '' : ' disabled'}><em>${E(un)}</em></div><small>${E(dica)} Padrão: ${d.padrao[g][k] == null ? 'o do BID' : (mult === 100 ? nf(d.padrao[g][k] * 100, 2).replace(/,00$/, '') : nf(d.padrao[g][k], 2).replace(/,00$/, '')) + ' ' + un}.</small></label>`;
  const hist = (d.historico || []).slice().reverse().slice(0, 5);
  // histórico legível: "Asia Shipping › IOF: 3,5% → 4%"
  const rotulo = campo => { const [g, k] = campo.split('.'); const grp = CAMPOS.find(c => c[0] === g) || [g, g, []]; const c = grp[2].find(x => x[0] === k);
    return {nome: `${grp[1]} › ${c ? c[1] : k}`, fmt: x => x == null ? 'do BID' : k === 'bid' ? (d.regras_bid[x] || x) : `${c && c[3] === 100 ? nf(x * 100, 2).replace(/,00$/, '') : nf(x, 2).replace(/,00$/, '')} ${c ? c[2] : ''}`.trim()}; };
  const mudTxt = m => { const r = rotulo(m.campo); return `${r.nome}: ${r.fmt(m.de)} → ${r.fmt(m.para)}`; };
  const box = document.createElement('div'); box.className = 'fr-gback'; box.id = 'fr-pmodal';
  box.innerHTML = `<div class="fr-gmodal fr-pmodal" role="dialog" aria-label="Parâmetros da calculadora"><header class="fr-gh"><div><div class="eyebrow">Frete internacional · calculadora</div>
      <h2>Parâmetros da validação</h2><p>${pode ? 'As tarifas vêm do BID; aqui ficam as regras que não estão nele. A mudança vale para todas as faturas na hora.' : 'Só o administrador, os owners e quem o administrador liberar em Configurações › Acessos alteram estes valores.'}</p></div><button class="cu-x" type="button" aria-label="Fechar">×</button></header>
    <div class="fr-pgrid">${CAMPOS.map(([g, t, cs]) => `<section class="fr-dcard"><h4>${E(t)}</h4><div class="fr-pbody">${cs.map(c => campo(g, c)).join('')}</div></section>`).join('')}</div>
    <div class="fr-pfoot"><div class="fr-phist">${d.alterado_em ? `Última alteração: ${E(personName(d.alterado_por))} em ${brd(d.alterado_em)}` : 'Valores padrão (nunca alterados).'}
      ${hist.length ? `<ul>${hist.map(h => `<li>${brd(h.em)} · ${E(personName(h.por))}: ${h.mudancas.map(m => E(mudTxt(m))).join('; ')}</li>`).join('')}</ul>` : ''}</div>
      ${pode ? '<div class="fr-pbtn"><button type="button" class="cu-btn ghost" id="fr-ppad">Restaurar padrão</button><button type="button" class="cu-btn" id="fr-psal">Salvar parâmetros</button></div>' : ''}</div>
    <div class="fr-msg" id="fr-pmsg" role="status"></div></div>`;
  document.body.appendChild(box);
  const fecha = () => { box.remove(); document.removeEventListener('keydown', escP, true); };
  const escP = e => { if (e.key === 'Escape') { e.stopPropagation(); fecha(); } };
  document.addEventListener('keydown', escP, true);
  box.addEventListener('mousedown', e => { if (e.target === box) fecha(); });
  box.querySelector('.cu-x').addEventListener('click', fecha);
  box.querySelector('#fr-ppad')?.addEventListener('click', () => {
    box.querySelectorAll('[data-pk]').forEach(el => { const p = d.padrao[el.dataset.pg][el.dataset.pk];
      if (el.tagName === 'SELECT') el.value = p; else el.value = p == null ? '' : (Number(el.dataset.mult) === 100 ? nf(p * 100, 2) : nf(p, 2)).replace(/,00$/, ''); });
  });
  box.querySelector('#fr-psal')?.addEventListener('click', async e => {
    const msg = box.querySelector('#fr-pmsg'), valores = {geral: {}, asia: {}, dms: {}};
    for (const el of box.querySelectorAll('[data-pk]')) {
      if (el.tagName === 'SELECT') { valores[el.dataset.pg][el.dataset.pk] = el.value; continue; }
      const n = num(el.value);
      if (Number.isNaN(n)) { msg.textContent = 'Valor inválido: ' + el.closest('label').querySelector('span').textContent; msg.className = 'fr-msg err'; el.focus(); return; }
      valores[el.dataset.pg][el.dataset.pk] = n == null ? null : Number(el.dataset.mult) === 100 ? n / 100 : n;
    }
    e.currentTarget.disabled = true;
    try {
      const r = await api('/api/frete/parametros', J('PUT', {valores}));
      msg.textContent = r.mudancas ? `Parâmetros salvos (${r.mudancas} alteração${r.mudancas > 1 ? 'ões' : ''}). As faturas foram recalculadas.` : 'Nada mudou.'; msg.className = 'fr-msg ok';
      await load(true);
      setTimeout(fecha, 1200);
    } catch (err) { e.currentTarget.disabled = false; msg.textContent = err.message; msg.className = 'fr-msg err'; }
  });
}

/* Excel com retorno na tela (mesmo padrão do Exportar Excel de Custos) */
async function exportar(b) {
  if (!b || b.disabled) return;
  const volta = ms => setTimeout(() => { b.disabled = false; b.className = 'cu-btn ghost'; b.textContent = 'Exportar Excel'; }, ms);
  b.disabled = true; b.classList.add('busy'); b.innerHTML = '<i class="cu-spin"></i>Gerando o Excel…';
  try {
    const r = await fetch('/api/frete/excel', {credentials: 'same-origin'});
    if (!r.ok) throw new Error(`Erro ${r.status} ao gerar o Excel.`);
    const blob = await r.blob(), a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'Validacao_frete_internacional.xlsx'; document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
    b.classList.remove('busy'); b.classList.add('done'); b.textContent = 'Excel baixado ✓'; volta(4000);
  } catch (e) { b.classList.remove('busy'); b.classList.add('fail'); b.textContent = 'Não foi possível exportar'; b.title = e.message; volta(5000); }
}
return {mount, preload, ficha, exportar, graficos, parametros: parametrosModal, reload: () => load(true)};
})();
