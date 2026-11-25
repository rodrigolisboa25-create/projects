/* Visão geral › Rede global de embarques (25/11/2026, pedido do usuário: "globo terrestre, impactante, com os países,
   quantitativo e valor dos embarques, com animação de sobreposição piscando"). Dados da página Embarques
   (/api/visao/globo: país de origem × mês × operação × modal; valor em US$ para todos os usuários). Globo em WebGL pelo
   globe.gl (Three.js, MIT, em static/globo/vendor), países do world-atlas 110m (Natural Earth). Brasil em destaque como
   destino: marítimo chega ao Porto de Santos; o aéreo vai ao Brasil, sem aeroporto (varia; pedido do usuário).
   Entrada em sequência (globo, países, arcos, números), câmera na Ásia e Europa, pausa quando a página não está
   visível; segue a preferência de animações (Configurações › Meu perfil). Clique no globo pelo ponto do mouse
   (toGlobeCoords + país que contém o ponto): funciona em qualquer lugar do globo; Brasil abre o detalhe dos embarques. */
window.nexusGlobo = (() => {
// país (como em Embarques) → [lat, lng, id do world-atlas (ISO numérico)]
const PAIS = {
  'Vietnã': [14.5, 107.8, '704'], 'Indonésia': [-3.2, 115.5, '360'], 'China': [31.5, 112.5, '156'], 'Tailândia': [15.4, 101.0, '764'],
  'Índia': [21.5, 78.9, '356'], 'Camboja': [12.6, 104.9, '116'], 'Sri Lanka': [7.9, 80.8, '144'], 'Paquistão': [29.9, 69.4, '586'],
  'Turquia': [39.0, 35.2, '792'], 'Geórgia': [42.2, 43.5, '268'], 'Argentina': [-34.0, -64.0, '032'], 'Malásia': [4.0, 102.0, '458'],
  'Jordânia': [30.9, 36.4, '400'], 'Bósnia e Herzegovina': [44.0, 17.8, '070'], 'Egito': [26.6, 30.0, '818'], 'Filipinas': [12.5, 122.5, '608'],
  'Honduras': [14.9, -86.6, '340'], 'Taiwan': [23.7, 121.0, '158'], 'México': [23.4, -102.4, '484'], 'Guatemala': [15.6, -90.3, '320'],
  'Itália': [42.6, 12.8, '380'], 'Singapura': [1.35, 103.8, ''], 'El Salvador': [13.7, -88.9, '222'], 'Coreia do Sul': [36.3, 127.9, '410'],
  'Bulgária': [42.7, 25.3, '100'], 'Estados Unidos': [39.5, -98.5, '840'], 'Bangladesh': [23.8, 90.3, '050'], 'Portugal': [39.6, -8.1, '620'],
  'Japão': [36.5, 138.5, '392'],
};
const BRASIL = {id: '076', lat: -12.5, lng: -51.5};
// Distância ESTIMADA por processo (pedido do usuário: "km viajados"): marítimo = rota por mar do porto principal do país
// até Santos (Ásia pelo Cabo da Boa Esperança, Mediterrâneo por Gibraltar, Pacífico da América pelo Panamá), em km;
// aéreo = linha reta (círculo máximo) do país até São Paulo. Não há o dado real nas fontes (só a Zelus traz km no FUP).
const KM_MAR = {'China': 20400, 'Vietnã': 16900, 'Indonésia': 15400, 'Tailândia': 17200, 'Índia': 13900, 'Camboja': 17000,
  'Sri Lanka': 13150, 'Paquistão': 14600, 'Turquia': 11700, 'Geórgia': 12800, 'Argentina': 1850, 'Malásia': 15400, 'Jordânia': 12600,
  'Bósnia e Herzegovina': 10700, 'Egito': 10900, 'Filipinas': 19000, 'Honduras': 9100, 'Taiwan': 19800, 'México': 9600,
  'Guatemala': 9100, 'Itália': 9600, 'Singapura': 15700, 'El Salvador': 9100, 'Coreia do Sul': 21300, 'Bulgária': 11850,
  'Estados Unidos': 9250, 'Bangladesh': 15400, 'Portugal': 8000, 'Japão': 21850};
const SP = [-23.5, -46.6];
function kmAr(lat, lng) {
  const r = Math.PI / 180, [a, b] = SP, h = Math.sin((a - lat) * r / 2) ** 2 + Math.cos(lat * r) * Math.cos(a * r) * Math.sin((b - lng) * r / 2) ** 2;
  return Math.round(2 * 6371 * Math.asin(Math.sqrt(h)));
}
const kmDe = (pais, modal) => !PAIS[pais] ? 0 : modal === 'Aéreo' ? kmAr(PAIS[pais][0], PAIS[pais][1]) : (KM_MAR[pais] || 0);
// vista padrão: Ásia e Europa, onde estão quase todas as origens (pedido do usuário); a câmera balança em volta dela
const HOME = {lat: 24, lng: 76, altitude: 2.25};
const DEST = {Marítimo: {lat: -23.96, lng: -46.30, nome: 'Porto de Santos'}, 'Aéreo': {lat: -22.6, lng: -47.2, nome: 'Brasil'}};
// Embarques: andamento na PGL e situação da conferência (mesmos nomes e cores da página Embarques)
const FASE = {transito: ['Em trânsito', '#2F7FB8'], no_brasil: ['Aguardando desembaraço', '#C9962E'], desembaracado: ['Aguardando entrega', '#7B61C9'],
              entregue: ['Entregue no CD', '#2E8B57'], sem: ['Sem FUP da PGL', '#97A39D']};
const SIT = {ok: ['Conferido', '#2E8B57'], checklist: ['Checklist pendente', '#C9962E'], verificar: ['Divergência', '#B9533F'],
             incompleto: ['Em montagem', '#5B7C99'], sem_conferencia: ['Sem conferência', '#97A39D'], historico: ['Antes de 2025', '#B7C0BB']};
const COR = {mar: '#4cc9f0', aer: '#f4b740', lime: '#b5dc3c', hi: '#e2ff7a', baixo: '#4a8f3c'};
const OPS = ['INLINE', 'AMOSTRAS', 'PROMO', 'ZELUS'];
const S = {data: null, el: null, g: null, feats: null, f: {per: '12m', un: '', op: '', modal: ''}, agg: null, sel: null, hover: null,
           flash: null, started: false, running: false, loop: 0, sway: true, swayT: 0, idleAt: 0, ro: null, pulse: 0, span: {}};

const E = s => (window.esc ? esc(s == null ? '' : String(s)) : String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'})[c]));
const animOn = () => !window.nexusAnim || window.nexusAnim.enabled();
const nf = (v, c = 0) => v == null || Number.isNaN(+v) ? '-' : (+v).toLocaleString('pt-BR', {minimumFractionDigits: c, maximumFractionDigits: c});
const usd = v => v == null ? '-' : v >= 1e9 ? `US$ ${nf(v / 1e9, 2)} bi` : v >= 1e6 ? `US$ ${nf(v / 1e6, 1)} mi` : v >= 1e3 ? `US$ ${nf(v / 1e3, 0)} mil` : `US$ ${nf(v, 0)}`;
const curto = v => v >= 1e6 ? `${nf(v / 1e6, 1)} mi` : v >= 1e3 ? `${nf(v / 1e3, 0)} mil` : nf(v);
const flag = p => (window.nexusEmb && nexusEmb.flag) ? nexusEmb.flag(p) : '';
const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
const mix = (a, b, t, al = 1) => { const x = hex(a), y = hex(b); return `rgba(${x.map((v, i) => Math.round(v + (y[i] - v) * t)).join(',')},${al})`; };
const brd = s => s ? String(s).slice(0, 10).split('-').reverse().join('/') : '-';
const MES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

async function preload() { if (!S.data) S.data = await api('/api/visao/globo'); }

// ------------------------------------------------------------------ dados do período
function ymAgo(n) { const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - n); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`; }
function anos() { return [...new Set((S.data.totais || []).map(t => t[1].slice(0, 4)))].sort().reverse().slice(0, 3); }
// meses futuros ficam de fora (o FUP às vezes traz data de embarque prevista)
function noPer(ym) { const p = S.f.per; return ym <= ymAgo(0) && (p === 'tudo' ? true : p === '12m' ? ym >= ymAgo(11) : ym.startsWith(p)); }
const passa = (ym, op, modal, un) => noPer(ym) && (!S.f.op || op === S.f.op) && (!S.f.modal || modal === S.f.modal) && (!S.f.un || un === S.f.un);
// linha da rota: [país, mês, operação, modal, tipo, situação, fase PGL, unidade, processos, valor, unidades, peso,
// contêineres, dias trânsito (soma, qtd), desembaraço, entrega, total]
const novoAcc = pais => ({pais, n: 0, v: 0, q: 0, mar: 0, aer: 0, peso: 0, cntr: 0, cx: 0, km: 0, ops: {}, sit: {}, fase: {}, tipo: {}, un: {}, mes: {}, ult: ''});
// [.., contêineres (12), dias de cada etapa (13-20, sem uso na tela desde que a média agregada saiu), caixas (21)]
function acumula(a, l) {
  const [pais, ym, op, modal, tipo, sit, fase, un, n, v, q, peso, cntr] = l;
  a.cx += l[21] || 0;
  a.n += n; a.v += v || 0; a.q += q || 0; if (modal === 'Aéreo') a.aer += n; else a.mar += n;
  if (pais) a.km += n * kmDe(pais, modal);
  a.peso += peso || 0; a.cntr += cntr || 0;
  for (const [o, k] of [[a.ops, op], [a.sit, sit], [a.fase, fase], [a.tipo, tipo], [a.un, un], [a.mes, ym]]) o[k] = (o[k] || 0) + n;
  if (ym > a.ult) a.ult = ym;
}
function agregar() {
  const paises = {}, tot = {...novoAcc('Brasil'), temV: true};
  for (const l of S.data.totais || []) if (passa(l[1], l[2], l[3], l[7])) acumula(tot, l);
  for (const l of S.data.paises || []) {
    if (!PAIS[l[0]] || !passa(l[1], l[2], l[3], l[7])) continue;
    acumula(paises[l[0]] || (paises[l[0]] = novoAcc(l[0])), l);
    tot.km += l[8] * kmDe(l[0], l[3]);  // os totais não têm país: a distância vem das linhas por país
  }
  tot.temV = tot.v > 0;  // valores em US$ para TODOS os usuários no globo (pedido do usuário, 25/11/2026)
  const lista = Object.values(paises).sort((a, b) => b.n - a.n);
  const max = lista.length ? lista[0].n : 1, soma = lista.reduce((s, x) => s + x.n, 0);
  lista.forEach((p, i) => { p.rank = i + 1; p.t = Math.sqrt(p.n / max); p.share = soma ? p.n / soma : 0; });
  S.agg = {tot, lista, by: paises, max};
}
// próximas chegadas (previsão do FUP da PGL) do país ou, no Brasil, de todos, respeitando operação, modal e unidade
const chegadas = pais => (S.data.a_chegar || []).filter(c => (pais === 'Brasil' || c.pais === pais) && (!S.f.op || c.op === S.f.op)
  && (!S.f.modal || c.modal === S.f.modal) && (!S.f.un || c.un === S.f.un));

// ------------------------------------------------------------------ montagem
function perLabel() { return S.f.per === '12m' ? 'nos últimos 12 meses' : S.f.per === 'tudo' ? 'desde 2022' : `em ${S.f.per}`; }
function shell() {
  // filtros em listas suspensas (pedido do usuário: ocupam menos espaço); o que sai do padrão fica com borda lima
  const padrao = {per: '12m', un: '', op: '', modal: ''};
  const lista = (k, rot, opts) => `<label class="gl-fg"><small>${rot}</small><select data-k="${k}" class="${S.f[k] !== padrao[k] ? 'on' : ''}">${opts.map(([v, t]) =>
    `<option value="${E(v)}"${S.f[k] === v ? ' selected' : ''}>${E(t)}</option>`).join('')}</select></label>`;
  // topo (título + filtros numa linha), corpo (cards à esquerda e ranking à direita, alinhados) e faixa embaixo: em fluxo,
  // para nada cobrir o título em tela menor
  S.el.innerHTML = `<div class="gl-stars"></div><div class="gl-stage" id="gl-stage"></div><div class="gl-vig"></div>
    <header class="gl-top">
      <div class="gl-tt"><span class="gl-live"><i></i>Rede global de embarques</span></div>
      <div class="gl-filters">
        ${lista('per', 'Período', [['12m', 'Últimos 12 meses'], ...anos().map(a => [a, a]), ['tudo', 'Tudo (desde 2022)']])}
        ${lista('un', 'Unidade', [['', 'Todas'], ['Fisia', 'Fisia'], ['Centauro', 'Centauro']])}
        ${lista('op', 'Operação', [['', 'Todas'], ...OPS.map(o => [o, o.charAt(0) + o.slice(1).toLowerCase()])])}
        ${lista('modal', 'Modal', [['', 'Todos'], ['Marítimo', 'Marítimo'], ['Aéreo', 'Aéreo']])}
      </div>
    </header>
    <div class="gl-body">
      <aside class="gl-left"><div class="gl-kpis" id="gl-kpis"></div></aside>
      <div class="gl-mid"><div class="gl-legend"><span><i class="ln mar"></i>Marítimo → Porto de Santos</span><span><i class="ln aer"></i>Aéreo → Brasil</span>
        <span class="gl-ramp">menos <b></b> mais processos</span><span class="gl-hint">arraste para girar · clique num país</span></div></div>
      <aside class="gl-right"><div class="gl-rk-h"><b>Países de origem</b><small id="gl-rk-sub"></small></div><ol class="gl-rank" id="gl-rank"></ol></aside>
      <section class="gl-detail" id="gl-detail" hidden></section>
    </div>
    <footer class="gl-ticker"><span class="gl-tk-h"><i></i>Últimas pastas de processo</span><div class="gl-tk-win"><div class="gl-tk-run" id="gl-tk"></div></div></footer>`;
  S.el.addEventListener('click', onClick);
  S.el.addEventListener('change', e => {
    const s = e.target.closest('select[data-k]'); if (!s) return;
    S.f[s.dataset.k] = s.value; s.classList.toggle('on', s.value !== padrao[s.dataset.k]); refresh(true);
  });
}
function onClick(e) {
  const ch = e.target.closest('[data-ch]');
  if (ch) {  // abre/fecha a linha do tempo do processo, sem refazer a animação do quadro
    S.chOpen = S.chOpen === ch.dataset.ch ? null : ch.dataset.ch;
    const box = document.getElementById('gl-detail'), top = box.scrollTop;
    detalhe(box, S.sel === 'Brasil' ? S.agg.tot : S.agg.by[S.sel], S.sel === 'Brasil'); box.scrollTop = top;
    return;
  }
  const r = e.target.closest('[data-pais]');
  if (r) { select(r.dataset.pais, !!r.closest('#gl-rank')); return; }
  if (e.target.closest('[data-gl-close]')) { select(null); return; }
  const emb = e.target.closest('[data-gl-emb]');
  if (emb && window.nexusEmb) { nexusEmb.filtrar(emb.dataset.glEmb ? {origem: emb.dataset.glEmb} : {}); if (typeof showPage === 'function') showPage('embarques'); }
}

// ------------------------------------------------------------------ painéis
function countUp(el, to, fmt, ms = 1400) {
  if (!animOn()) { el.textContent = fmt(to); return; }
  const from = +(el.dataset.v || 0), t0 = performance.now(); el.dataset.v = to;
  const step = t => { const k = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - k, 3); el.textContent = fmt(from + (to - from) * e); if (k < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}
// ícones desenhados dos cards (regra do sistema: nada de emoji), à esquerda do título
const ico = d => `<svg class="gl-ki" viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
const KPI_ICON = {
  n: ico('<path d="M7 3h7l4 4v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>'),
  p: ico('<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.6 2.6 3.8 5.6 3.8 9s-1.2 6.4-3.8 9c-2.6-2.6-3.8-5.6-3.8-9S9.4 5.6 12 3z"/>'),
  k: ico('<circle cx="5.5" cy="18" r="2.2"/><circle cx="18.5" cy="6" r="2.2"/><path d="M7.5 17c4-1 2-6 6-7.5 1.6-.6 2.6-1.4 3.4-2.6" stroke-dasharray="2.4 2.2"/>'),
  w: ico('<path d="M8.5 8.5a3.5 3.5 0 1 1 7 0"/><path d="M6.5 8.5h11l2 11.5h-15z"/><path d="M10 14.5h4"/>'),
  q: ico('<path d="M9 3.5 6 5 3 8l2.5 3L7 10v10.5h10V10l1.5 1L21 8l-3-3-3-1.5c-.5 1.4-1.6 2.2-3 2.2s-2.5-.8-3-2.2z"/>'),
  c: ico('<path d="M12 3 4 7v10l8 4 8-4V7z"/><path d="m4 7 8 4 8-4M12 11v10"/>'),
  cn: ico('<rect x="2.5" y="6.5" width="19" height="11" rx="1"/><path d="M6.5 9v6M10 9v6M14 9v6M17.5 9v6"/>'),
};
function kpis() {
  const {tot, lista} = S.agg, box = document.getElementById('gl-kpis');
  // cards (25/11/2026: sai o valor das faturas; entram a distância estimada e o peso total)
  const kmFmt = v => v >= 1e6 ? `${nf(v / 1e6, 1)} mi km` : `${nf(v)} km`;
  const cards = [['n', 'Processos', tot.n, v => nf(v), `${nf(tot.mar)} marítimos · ${nf(tot.aer)} aéreos`],
                 ['p', 'Países de origem', lista.length, v => nf(v), lista[0] ? `${lista[0].pais} lidera com ${nf(lista[0].share * 100, 0)}%` : '-'],
                 ['k', 'Distância percorrida', tot.km, kmFmt, tot.km ? `estimada · ≈ ${nf(tot.km / 40075, 0)} voltas ao mundo` : 'sem país de origem no filtro'],
                 ['w', 'Peso bruto', tot.peso / 1000, v => `${nf(v)} t`, tot.cntr ? `em ${nf(tot.cntr)} contêineres e cargas aéreas` : 'faturas e FUP da PGL'],
                 ['cn', 'Contêineres', tot.cntr, v => nf(v), tot.mar ? `cntrs · ${nf(tot.cntr / Math.max(1, (tot.tipo.FCL || 0)), 1)} por processo FCL` : 'cntrs dos processos marítimos'],
                 ['q', 'Units', tot.q, curto, tot.n ? `${nf(tot.q / tot.n, 0)} por processo · faturas (TCCI)` : 'faturas (TCCI)'],
                 ['c', 'Caixas', tot.cx, curto, tot.cx ? `${nf(tot.q / tot.cx, 1)} units por caixa` : 'volumes das faturas']];
  if (!box.dataset.ok) {
    box.innerHTML = cards.map(([k, t]) => `<div class="gl-kpi" data-kk="${k}" tabindex="0" aria-label="${E(t)}: ver o detalhamento"><small>${KPI_ICON[k] || ''}${E(t)}</small><strong data-v="0">0</strong><em></em></div>`).join('');
    box.dataset.ok = '1';
    // passar o mouse (ou focar pelo teclado) abre o painel de análise do card; sair dele e do painel fecha
    box.querySelectorAll('.gl-kpi').forEach(c => {
      const abre = () => { clearTimeout(S.pnT); S.pnT = setTimeout(() => abrePainel(c.dataset.kk), S.pn ? 60 : 180); };
      c.addEventListener('mouseenter', abre); c.addEventListener('focus', abre);
      c.addEventListener('mouseleave', fechaPainelDepois); c.addEventListener('blur', fechaPainelDepois);
    });
  }
  cards.forEach(([k, , v, fmt, sub]) => { const c = box.querySelector(`[data-kk="${k}"]`); if (!c) return; countUp(c.querySelector('strong'), v, fmt); c.querySelector('em').textContent = sub; });
}
function ranking() {
  const {lista, tot} = S.agg;
  document.getElementById('gl-rk-sub').textContent = `${nf(lista.length)} ${lista.length === 1 ? 'país' : 'países'} · ${perLabel()}`;
  const ol = document.getElementById('gl-rank');
  // todos os países de origem do filtro (a lista rola), não só os 10 primeiros
  ol.innerHTML = lista.map(p => `<li data-pais="${E(p.pais)}" class="${S.sel === p.pais ? 'on' : ''}" title="Ver ${E(p.pais)} no globo">
      <span class="gl-rk-n">${p.rank}</span><span class="gl-flag">${flag(p.pais)}</span>
      <span class="gl-rk-x"><b>${E(p.pais)}</b><i><u style="--w:${Math.max(3, p.n / S.agg.max * 100)}%"></u></i></span>
      <span class="gl-rk-v"><b>${nf(p.n)}</b><small>${tot.temV ? usd(p.v) : nf(p.share * 100, 1) + '%'}</small></span></li>`).join('')
    || `<li class="gl-rk-empty">${S.f.un === 'Centauro' ? 'O relatório da PGL da Centauro não traz o país de origem: os números da Centauro ficam no Brasil (clique nele no globo).' : 'Nenhum processo neste filtro.'}</li>`;
  if (animOn()) { ol.classList.remove('grow'); void ol.offsetWidth; ol.classList.add('grow'); }
}
function ticker() {
  const it = (S.data.ultimos || []).map(u => `<span class="gl-tk-i"><span class="gl-flag">${flag(u.pais)}</span><b>${E(u.nome)}</b>${E(u.pais)} · ${E(u.op)} · ${E(u.modal || '-')} · ${brd(u.criada)}</span>`).join('');
  document.getElementById('gl-tk').innerHTML = it + it;  // duas vezes: a faixa corre sem emenda
}
// barras de distribuição (operação, andamento, situação)
const barras = (obj, nomes, total) => Object.entries(obj).filter(([, n]) => n).sort((a, b) => b[1] - a[1]).map(([k, n]) => {
  const [rot, cor] = nomes ? (nomes[k] || [k || 'Não informado', '#97A39D']) : [k, ''];
  return `<div class="gl-op"><span title="${E(rot)}">${E(rot)}</span><i><u style="--w:${n / total * 100}%${cor ? `;background:${cor}` : ''}"></u></i><b>${nf(n)}</b></div>`;
}).join('');
// Brasil: o destino de tudo, com o detalhamento dos embarques no filtro escolhido
// paleta sóbria dos painéis (pedido do usuário: "roxo com laranja e azul parece escola de samba"): tons do sistema
const PAL = {a: '#b5dc3c', b: '#6f9a5c', c: '#c3cfca', d: '#5b6863'};
const UNC = {Fisia: ['Fisia', PAL.a], Centauro: ['Centauro', PAL.c]};
// nomes curtos (pedido do usuário: não cortar na barra)
const TIPO = {FCL: ['FCL', PAL.a], LCL: ['LCL', PAL.b], 'Aéreo': ['Aéreo', PAL.c], '': ['Não ident.', PAL.d]};
// Linha do tempo de UM processo (pedido do usuário: a média agregada não fazia sentido): embarque, chegada (prevista),
// registro da DI, desembaraço e entrega no CD, com as datas do FUP da PGL; feito = verde, previsto = tracejado
const diasAte = d => Math.round((new Date(d + 'T00:00:00') - new Date(new Date().toDateString())) / 864e5);
function linhaProcesso(c) {
  const d = c.datas || {};
  const passos = [['Embarque', d.embarque, null], ['Chegada', d.chegada, d.prev_chegada], ['Registro da DI', d.registro_di, null],
                  ['Desembaraço', d.desembaraco, null], ['Entrega no CD', d.entrega, d.prev_entrega]];
  const prox = diasAte(c.prev);
  return `<div class="gl-pt">
    <div class="gl-pt-h"><span>${prox <= 0 ? 'Chegada prevista para hoje' : `Chega em <b>${prox} ${prox === 1 ? 'dia' : 'dias'}</b>`}</span>${c.etapa ? `<span class="gl-pt-e">${E(c.etapa)}</span>` : ''}</div>
    <ol class="gl-pt-l">${passos.map(([rot, feito, prev]) => `<li class="${feito ? 'ok' : prev ? 'prev' : ''}"><i></i><b>${E(rot)}</b><small>${feito ? brd(feito) : prev ? `previsto ${brd(prev)}` : '-'}</small></li>`).join('')}</ol>
    <div class="gl-pt-f">${[c.wfadim, c.navio && `Navio ${c.navio}`, c.tipo, c.cntr && `${c.cntr} ${c.cntr === 1 ? 'contêiner' : 'contêineres'}`, c.op, c.un].filter(Boolean).map(E).join(' · ')}</div></div>`;
}
// Detalhe (país de origem ou Brasil): números, tipo de embarque, próximas chegadas (clique = linha do tempo do processo),
// mês a mês, unidade, situação da conferência e operação
function detalhe(box, x, br) {
  const tot = S.agg.tot;
  const meses = Object.keys(x.mes).sort().slice(-12), maxM = Math.max(1, ...meses.map(m => x.mes[m]));
  // barras em pixels (a altura em % não era aplicada e todas ficavam iguais), com o número em cima de cada uma
  const evol = meses.map(m => `<span class="gl-ev" title="${MES[+m.slice(5) - 1]}/${m.slice(0, 4)}: ${nf(x.mes[m])} processos"><b>${nf(x.mes[m])}</b><u style="height:${Math.max(3, Math.round(x.mes[m] / maxM * 62))}px"></u><small>${MES[+m.slice(5) - 1]}${m.slice(5) === '01' || m === meses[0] ? `<br>${m.slice(2, 4)}` : ''}</small></span>`).join('');
  const prox = chegadas(br ? 'Brasil' : x.pais);
  const em30 = prox.filter(c => c.prev <= new Date(Date.now() + 30 * 864e5).toISOString().slice(0, 10)).length;
  const lista = prox.slice(0, 30).map((c, i) => { const k = c.nome + '|' + c.prev, on = S.chOpen === k;
    return `<li class="${on ? 'on' : ''}"><button type="button" class="gl-ch-b" data-ch="${E(k)}" aria-expanded="${on}"><span class="gl-ch-d">${brd(c.prev)}</span><b>${E(c.nome)}</b><span class="gl-ch-t" style="--c:${(TIPO[c.tipo] || TIPO[''])[1]}">${E(c.tipo || '-')}${c.cntr ? ` · ${c.cntr} cntr` : ''}</span><span class="gl-ch-o">${c.pais ? E(c.pais) : 'origem não identificada'} · ${E(c.un)}</span></button>${on ? linhaProcesso(c) : ''}</li>`; }).join('');
  const top = br ? S.agg.lista.slice(0, 5).map(p => `<li data-pais="${E(p.pais)}"><span class="gl-flag">${flag(p.pais)}</span><b>${E(p.pais)}</b><span>${nf(p.n)}</span></li>`).join('') : '';
  const temSit = Object.keys(x.sit).some(k => k);
  box.innerHTML = `<button type="button" class="gl-x" data-gl-close aria-label="Fechar">×</button>
    <div class="gl-d-h"><span class="gl-flag big">${flag(br ? 'Brasil' : x.pais)}</span><div><small>${br ? 'Destino' : `Origem · ${x.rank}º`} · ${perLabel()}</small><h3>${E(br ? 'Brasil' : x.pais)}</h3></div></div>
    <div class="gl-d-k wrap"><div><strong>${nf(x.n)}</strong><small>processos</small></div>${tot.temV ? `<div><strong>${usd(x.v)}</strong><small>valor das faturas</small></div>` : ''}
      <div><strong>${nf(x.cntr)}</strong><small>contêineres</small></div><div><strong>${curto(x.q)}</strong><small>unidades</small></div>
      <div><strong>${nf(x.peso / 1000, 0)} t</strong><small>peso bruto</small></div>
      <div><strong>${x.km >= 1e6 ? `${nf(x.km / 1e6, 1)} mi` : nf(x.km)} km</strong><small>distância (estimada)</small></div>
      ${br ? `<div><strong>${nf(S.agg.lista.length)}</strong><small>países de origem</small></div>` : `<div><strong>${nf(x.share * 100, 1)}%</strong><small>das origens</small></div>`}</div>
    <div class="gl-d-sec"><small>Tipo de embarque</small>${barras(x.tipo, TIPO, x.n)}</div>
    <div class="gl-d-sec"><small>Próximas chegadas · ${nf(prox.length)} previstas${prox.length ? `, ${nf(em30)} nos próximos 30 dias` : ''}${prox.length ? ' · clique para ver a linha do tempo' : ''}</small>${lista ? `<ul class="gl-ch">${lista}</ul>${prox.length > 30 ? `<div class="gl-none">Mostrando as 30 primeiras.</div>` : ''}` : '<div class="gl-none">Nenhuma chegada prevista no FUP da PGL.</div>'}</div>
    <div class="gl-d-sec"><small>Processos por mês</small><div class="gl-evol">${evol}</div></div>
    ${Object.keys(x.un).length > 1 ? `<div class="gl-d-sec"><small>Por unidade</small>${barras(x.un, UNC, x.n)}</div>` : ''}
    ${temSit ? `<div class="gl-d-sec"><small>Situação da conferência</small>${barras(Object.fromEntries(Object.entries(x.sit).filter(([k]) => k)), SIT, x.n)}</div>` : ''}
    ${Object.keys(x.ops).some(k => k) ? `<div class="gl-d-sec"><small>Por operação</small>${barras(Object.fromEntries(Object.entries(x.ops).filter(([k]) => k)), null, x.n)}</div>` : ''}
    ${top ? `<div class="gl-d-sec"><small>Principais origens</small><ol class="gl-top5">${top}</ol></div>` : ''}
    <div class="gl-d-f"><span>${br ? 'Embarques + FUP da PGL' : `Último processo: ${x.ult ? `${MES[+x.ult.slice(5) - 1]}/${x.ult.slice(0, 4)}` : '-'}`}</span><button type="button" class="gl-btn" data-gl-emb="${br ? '' : E(x.pais)}">${br ? 'Abrir Embarques →' : 'Ver processos em Embarques →'}</button></div>`;
}
function detail() {
  const box = document.getElementById('gl-detail');
  const br = S.sel === 'Brasil', x = br ? S.agg.tot : S.sel && S.agg.by[S.sel];
  if (!x) { box.hidden = true; return; }
  detalhe(box, x, br);
  box.hidden = false; box.classList.remove('in'); void box.offsetWidth; box.classList.add('in');
}

// ------------------------------------------------------------------ painel de análise de cada card (ao passar o mouse)
// Pedido do usuário (25/11/2026): detalhamento por mês, trimestre, semestre e ano, "ultraimpactante". Usa os mesmos
// dados do globo com os filtros de unidade, operação e modal (o período é o eixo do painel).
// CO₂ (estimado, fatores médios do GLEC Framework): marítimo 0,016 e aéreo 0,60 kg de CO₂ por tonelada-km, sobre o
// peso bruto e a distância da rota padrão. Trecho rodoviário: referência real da PGL (FUP da Zelus): Santos → CD
// Extrema 432 km e 516,6 kg de CO₂ por viagem; aeroporto → CD Louveira 96 km e 72,2 kg (aplicado aos processos Fisia).
const CO2F = {mar: .016, aer: .60};
const RODO = {Marítimo: [432, 516.63, 'Porto de Santos → CD Extrema'], 'Aéreo': [96, 72.16, 'Aeroporto → CD Louveira']};
const GRANS = [['mes', 'Mês'], ['tri', 'Trimestre'], ['sem', 'Semestre'], ['ano', 'Ano']];
const QTD_GRAN = {mes: 12, tri: 8, sem: 6, ano: 5};
const passaSemPer = (ym, op, modal, un) => ym <= ymAgo(0) && (!S.f.op || op === S.f.op) && (!S.f.modal || modal === S.f.modal) && (!S.f.un || un === S.f.un);
function balde(ym, g) {
  const y = ym.slice(0, 4), m = +ym.slice(5);
  return g === 'mes' ? ym : g === 'tri' ? `${y}-T${Math.ceil(m / 3)}` : g === 'sem' ? `${y}-S${m <= 6 ? 1 : 2}` : y;
}
function rotBalde(k, g) {
  if (g === 'mes') return `${MES[+k.slice(5) - 1]}/${k.slice(2, 4)}`;
  if (g === 'ano') return k;
  return `${k.slice(5)}/${k.slice(2, 4)}`;  // "T3/26", "S2/26"
}
function serie(g) {
  const B = {}, novo = () => ({n: 0, mar: 0, aer: 0, peso: 0, cntr: 0, q: 0, cx: 0, km: 0, kmMar: 0, kmAer: 0, co2Mar: 0, co2Aer: 0, rodoKm: 0, rodoCo2: 0,
    un: {}, ops: {}, opsCx: {}, opsQ: {}, tipo: {}, tipoPeso: {}, tipoCx: {}, paises: {}, paisQ: {}, paisPeso: {},
    vF: 0, pesoF: 0, tipoVF: {}, tipoPesoF: {}, unCntr: {}, tipoCntr: {}, paisCntr: {}, opsCntr: {}});
  const add = (o, k, v) => { o[k] = (o[k] || 0) + v; };
  for (const l of S.data.totais || []) {
    const [, ym, op, modal, tipo, , , un, n, v, q, peso, cntr] = l, cx = l[21] || 0;
    if (!passaSemPer(ym, op, modal, un)) continue;
    const b = B[balde(ym, g)] || (B[balde(ym, g)] = novo());
    b.n += n; b.peso += peso || 0; b.cntr += cntr || 0; b.q += q || 0; b.cx += cx;
    // valor por peso (US$/kg): só Fisia, que tem valor das faturas; a Centauro tem peso sem valor e diluiria a média
    if (un === 'Fisia' && v != null && peso) { b.vF += v; b.pesoF += peso; add(b.tipoVF, tipo, v); add(b.tipoPesoF, tipo, peso); }
    if (op) { add(b.opsCx, op, cx); add(b.opsQ, op, q || 0); add(b.opsCntr, op, cntr || 0); } add(b.tipoCx, tipo, cx);
    add(b.unCntr, un, cntr || 0); add(b.tipoCntr, tipo, cntr || 0);
    if (modal === 'Aéreo') b.aer += n; else b.mar += n;
    add(b.un, un, n); if (op) add(b.ops, op, n); add(b.tipo, tipo, n); add(b.tipoPeso, tipo, peso || 0);
    if (un === 'Fisia' && RODO[modal]) { b.rodoKm += n * RODO[modal][0]; b.rodoCo2 += n * RODO[modal][1]; }
  }
  for (const [pais, ym, op, modal, , , , un, n, , q, peso, cntr] of S.data.paises || []) {
    if (!PAIS[pais] || !passaSemPer(ym, op, modal, un)) continue;
    const b = B[balde(ym, g)] || (B[balde(ym, g)] = novo()), km = kmDe(pais, modal), aer = modal === 'Aéreo';
    b.km += n * km; if (aer) b.kmAer += n * km; else b.kmMar += n * km;
    const co2 = (peso || 0) / 1000 * km * (aer ? CO2F.aer : CO2F.mar);
    if (aer) b.co2Aer += co2; else b.co2Mar += co2;
    add(b.paises, pais, n); add(b.paisQ, pais, q || 0); add(b.paisPeso, pais, peso || 0); add(b.paisCntr, pais, cntr || 0);
  }
  const chaves = Object.keys(B).sort().slice(-QTD_GRAN[g]);
  // mês: só o nome ("dez"), com o ano na primeira coluna e em janeiro (rótulos curtos não se encostam)
  return chaves.map((k, i) => ({k, g, rot: g === 'mes' ? MES[+k.slice(5) - 1] + (i === 0 || k.endsWith('-01') ? `/${k.slice(2, 4)}` : '') : rotBalde(k, g), ...B[k]}));
}
// colunas empilhadas em HTML (texto sempre nítido, mesmo com dois gráficos lado a lado), com o total em cima de cada
// coluna, a dica de cada parte e a última coluna (período atual) em destaque
function colunas(dados, partes, fmt) {
  const tot = d => partes.reduce((s, [k]) => s + (d[k] || 0), 0), max = Math.max(1, ...dados.map(tot)), H = 150;
  return `<div class="gl-cols" style="--n:${dados.length}">${dados.map((d, i) => {
    const ult = i === dados.length - 1;
    const segs = partes.slice().reverse().map(([k, cor, rot]) => { const hh = (d[k] || 0) / max * H;
      return hh > 0 ? `<u style="height:${hh.toFixed(1)}px;background:${cor}" title="${E(d.rot)} · ${E(rot)}: ${fmt(d[k] || 0)}"></u>` : ''; }).join('');
    return `<div class="gl-col${ult ? ' ult' : ''}" style="--d:${i * 45}ms"><b>${fmt(tot(d))}</b><span class="gl-stk">${segs}</span><small>${E(d.rot)}</small></div>`;
  }).join('')}</div>
  <div class="gl-var" style="--n:${dados.length}" title="Variação de cada período em relação ao anterior">${dados.map((d, i) => {
    // linha de variação: quanto cada período subiu ou caiu em relação ao anterior
    const v = i ? delta(tot(d), tot(dados[i - 1])) : null, parcial = i === dados.length - 1 && d.k && d.k === balde(ymAgo(0), d.g || 'mes');
    return `<span class="${v == null ? '' : v >= 0 ? 'up' : 'down'}"${parcial ? ' title="Período atual, ainda em andamento"' : ''}>${v == null ? 'vs. ant.' : `${v >= 0 ? '+' : '−'}${nf(Math.abs(v), Math.abs(v) < 10 ? 1 : 0)}%${parcial ? '*' : ''}`}</span>`;
  }).join('')}</div>`;
}
const delta = (a, b) => b ? (a - b) / b * 100 : null;
const dTxt = v => v == null ? '<span class="gl-dl">sem comparação</span>' : `<span class="gl-dl ${v >= 0 ? 'up' : 'down'}">${v >= 0 ? '▲' : '▼'} ${nf(Math.abs(v), 1)}%</span>`;
const legenda = partes => `<div class="gl-pl">${partes.map(([, cor, rot]) => `<span><i style="background:${cor}"></i>${E(rot)}</span>`).join('')}</div>`;
const lista5 = (obj, fmt, n = 6) => { const xs = Object.entries(obj).filter(([k, v]) => k && v).sort((a, b) => b[1] - a[1]).slice(0, n), mx = xs.length ? xs[0][1] : 1;
  return xs.map(([k, v]) => `<div class="gl-pr"><span class="gl-flag">${PAIS[k] ? flag(k) : ''}</span><b>${E(k)}</b><i><u style="--w:${v / mx * 100}%"></u></i><em>${fmt(v)}</em></div>`).join('') || '<div class="gl-none">Sem dados.</div>'; };
const tK = v => v >= 1e6 ? `${nf(v / 1e6, 1)} mi` : v >= 1e3 ? `${nf(v / 1e3, 0)} mil` : nf(v);
const tCO2 = kg => kg >= 1e6 ? `${nf(kg / 1e6, 1)} mil t` : `${nf(kg / 1e3, 0)} t`;
// conteúdo de cada painel
function painel(k, g) {
  // o período atual ainda não fechou: marcado como parcial (a comparação com o anterior não é queda real)
  const s = serie(g), u = s[s.length - 1] || {}, a = s[s.length - 2] || null,
    per = u.k ? rotBalde(u.k, g) + (u.k === balde(ymAgo(0), g) ? ' (parcial)' : '') : '-', lblG = GRANS.find(x => x[0] === g)[1].toLowerCase();
  const hero = cards => `<div class="gl-ph">${cards.map(([rot, val, sub]) => `<div><small>${rot}</small><strong>${val}</strong>${sub || ''}</div>`).join('')}</div>`;
  const sec = (t, html) => `<div class="gl-ps"><h5>${t}</h5>${html}</div>`;
  if (k === 'n') {
    const partes = [['mar', PAL.a, 'Marítimo'], ['aer', PAL.c, 'Aéreo']];
    return hero([[`Processos · ${per}`, nf(u.n), dTxt(delta(u.n, a && a.n))], ['Média por ' + lblG, nf(s.reduce((t, x) => t + x.n, 0) / (s.length || 1)), ''],
      ['Marítimo × aéreo', `${nf(u.mar)} · ${nf(u.aer)}`, `<span class="gl-dl">${u.n ? nf(u.mar / u.n * 100, 0) : 0}% marítimo</span>`]])
      + `<div class="gl-pc">${legenda(partes)}${colunas(s, partes, v => nf(v))}</div>`
      + `<div class="gl-p2">${sec(`Por unidade · ${per}`, barras(u.un || {}, UNC, u.n || 1))}${sec(`Tipo de embarque · ${per}`, barras(u.tipo || {}, TIPO, u.n || 1))}${sec(`Por operação · ${per}`, barras(u.ops || {}, null, u.n || 1))}</div>`;
  }
  if (k === 'p') {
    const ativos = x => Object.keys(x.paises || {}).length, novos = a ? Object.keys(u.paises || {}).filter(p => !(a.paises || {})[p]) : [];
    const top3 = Object.values(u.paises || {}).sort((x, y) => y - x).slice(0, 3).reduce((t, v) => t + v, 0), totP = Object.values(u.paises || {}).reduce((t, v) => t + v, 0);
    const ser = s.map(x => ({...x, at: ativos(x)}));
    return hero([[`Países ativos · ${per}`, nf(ativos(u)), dTxt(delta(ativos(u), a && ativos(a)))], ['Concentração (top 3)', `${totP ? nf(top3 / totP * 100, 0) : 0}%`, '<span class="gl-dl">dos processos</span>'],
      ['Novos no período', nf(novos.length), novos.length ? `<span class="gl-dl up">${novos.slice(0, 3).map(E).join(', ')}</span>` : '<span class="gl-dl">nenhum</span>']])
      + `<div class="gl-pc">${colunas(ser, [['at', '#d8ff6a', 'Países']], v => nf(v))}</div>`
      + `<div class="gl-p2">${sec(`Principais origens · ${per}`, lista5(u.paises || {}, v => `${nf(v)} proc.`, 8))}${sec(`Unidades por país · ${per}`, lista5(u.paisQ || {}, tK, 8))}</div>`;
  }
  if (k === 'k') {
    const co2 = x => (x.co2Mar || 0) + (x.co2Aer || 0) + (x.rodoCo2 || 0), co2u = co2(u);
    const partes = [['kmMar', PAL.a, 'Rota marítima'], ['kmAer', PAL.c, 'Rota aérea']];
    const pc = [['co2Mar', PAL.a, 'Marítimo'], ['co2Aer', PAL.c, 'Aéreo'], ['rodoCo2', PAL.b, 'Rodoviário']];
    return hero([[`Distância · ${per}`, `${tK(u.km)} km`, dTxt(delta(u.km, a && a.km))], [`CO₂ estimado · ${per}`, tCO2(co2u), dTxt(delta(co2u, a && co2(a)))],
      ['Equivale a', `${nf(co2u / 22, 0)} árvores`, '<span class="gl-dl">absorvendo CO₂ por um ano</span>'], ['Voltas ao mundo', nf(u.km / 40075, 0), `<span class="gl-dl">${nf(u.km / 384400, 1)}× a distância da Terra à Lua</span>`]])
      + `<div class="gl-p2 c2"><div class="gl-pc">${legenda(partes)}${colunas(s, partes, tK)}</div><div class="gl-pc">${legenda(pc)}${colunas(s, pc, tCO2)}</div></div>`
      + `<div class="gl-p3">${[['Rota marítima', u.kmMar, u.co2Mar, PAL.a, 'porto de origem → Santos'], ['Rota aérea', u.kmAer, u.co2Aer, PAL.c, 'aeroporto de origem → São Paulo'],
        ['Trecho rodoviário', u.rodoKm, u.rodoCo2, PAL.b, 'Santos → CD Extrema (432 km) · aeroporto → CD Louveira (96 km)']].map(([t, km, c, cor, sub]) =>
        `<div class="gl-pk" style="--c:${cor}"><small>${t}</small><strong>${tK(km || 0)} km</strong><em>${tCO2(c || 0)} de CO₂</em><span>${sub}</span></div>`).join('')}</div>
      <div class="gl-pn">Estimativas: rota padrão por país e fatores médios do GLEC Framework (navio 0,016 e avião 0,60 kg de CO₂ por tonelada-km, sobre o peso bruto). Trecho rodoviário pela referência da PGL no relatório da Zelus. Uma árvore absorve cerca de 22 kg de CO₂ por ano.</div>`;
  }
  if (k === 'w') {
    const partes = [['FCL', PAL.a, 'FCL'], ['LCL', PAL.b, 'LCL'], ['Aéreo', PAL.c, 'Aéreo'], ['', PAL.d, 'Não identificado']];
    const ser = s.map(x => ({...x, ...Object.fromEntries(partes.map(([t]) => [t, (x.tipoPeso[t] || 0) / 1000]))}));
    // peso por contêiner: todo o peso marítimo ÷ contêineres (o FCL sozinho deixava de fora os processos ainda sem FUP)
    const pesoMar = ((u.peso || 0) - ((u.tipoPeso || {})['Aéreo'] || 0)) / 1000;
    // valor por peso (US$/kg), para todos os usuários (pedido do usuário) e só com a Fisia
    const temV = true, vkg = x => x && x.pesoF ? x.vF / x.pesoF : null, uv = vkg(u), av = vkg(a);
    const fv = v => `US$ ${nf(v, 2)}`;
    const serV = s.map(x => ({...x, vkg: vkg(x) || 0}));
    const porTipo = Object.fromEntries(Object.entries(u.tipoPesoF || {}).filter(([t, p]) => p > 0).map(([t, p]) => [t, (u.tipoVF[t] || 0) / p]));
    const listaTipo = Object.entries(porTipo).sort((x, y) => y[1] - x[1]).map(([t, v]) => { const mx = Math.max(...Object.values(porTipo));
      return `<div class="gl-op"><span>${E((TIPO[t] || [t || 'Não ident.'])[0])}</span><i><u style="--w:${v / mx * 100}%;background:${(TIPO[t] || ['', PAL.d])[1]}"></u></i><b>${fv(v)}</b></div>`; }).join('');
    return hero([[`Peso bruto · ${per}`, `${nf(u.peso / 1000)} t`, dTxt(delta(u.peso, a && a.peso))], ['Média por processo', `${u.n ? nf(u.peso / 1000 / u.n, 1) : 0} t`, ''],
      ['Por contêiner', u.cntr ? `${nf(pesoMar / u.cntr, 1)} t` : '-', `<span class="gl-dl">${nf(u.cntr || 0)} contêineres · peso marítimo</span>`],
      ...(temV ? [[`Valor por kg · ${per}`, uv == null ? '-' : fv(uv), dTxt(uv != null && av != null ? delta(uv, av) : null)]] : [])])
      + `<div class="gl-pc">${legenda(partes)}${colunas(ser, partes, v => `${tK(v)} t`)}</div>`
      + (temV ? `<div class="gl-pc"><div class="gl-pl"><span><i style="background:${PAL.a}"></i>Valor das faturas por kg de peso bruto (US$/kg) · Fisia</span></div>${colunas(serV, [['vkg', PAL.a, 'US$/kg']], fv)}</div>` : '')
      + `<div class="gl-p2">${sec(`Peso por tipo · ${per}`, barras(Object.fromEntries(Object.entries(u.tipoPeso || {}).map(([t, v]) => [t, Math.round(v / 1000)])), TIPO, Math.max(1, u.peso / 1000)))}${temV ? sec(`US$/kg por tipo · ${per}`, listaTipo || '<div class="gl-none">Sem dados.</div>') : ''}${sec(`Origens mais pesadas · ${per}`, lista5(u.paisPeso || {}, v => `${nf(v / 1000)} t`, 8))}</div>`
      + (temV ? '<div class="gl-pn">Valor por kg = valor das faturas (US$) ÷ peso bruto, só dos processos da Fisia (a Centauro não tem o valor das faturas no sistema).</div>' : '');
  }
  // units (peças) e caixas: colunas empilhadas por operação (dado real de cada operação)
  const opsC = {INLINE: PAL.a, AMOSTRAS: PAL.b, PROMO: PAL.c, ZELUS: PAL.d};
  const partes = OPS.map(o => [o, opsC[o], o.charAt(0) + o.slice(1).toLowerCase()]);
  const nomesOp = Object.fromEntries(OPS.map(o => [o, [o.charAt(0) + o.slice(1).toLowerCase(), opsC[o]]]));
  if (k === 'cn') {  // contêineres (cntrs): por período, por tipo de embarque, origem e unidade
    const partes = [['FCL', PAL.a, 'FCL'], ['LCL', PAL.b, 'LCL'], ['', PAL.d, 'Não identificado']];
    const ser = s.map(x => ({...x, ...Object.fromEntries(partes.map(([t]) => [t, x.tipoCntr[t] || 0]))}));
    const pesoMar = ((u.peso || 0) - ((u.tipoPeso || {})['Aéreo'] || 0)) / 1000;
    return hero([[`Contêineres · ${per}`, nf(u.cntr || 0), dTxt(delta(u.cntr, a && a.cntr))], ['Média por ' + lblG, nf(s.reduce((t, x) => t + x.cntr, 0) / (s.length || 1), 0), ''],
      ['Peso por contêiner', u.cntr ? `${nf(pesoMar / u.cntr, 1)} t` : '-', '<span class="gl-dl">peso marítimo ÷ cntrs</span>'],
      ['Units por contêiner', u.cntr ? tK(u.q / u.cntr) : '-', '']])
      + `<div class="gl-pc">${legenda(partes)}${colunas(ser, partes, v => nf(v))}</div>`
      + `<div class="gl-p2">${sec(`Contêineres por origem · ${per}`, lista5(u.paisCntr || {}, v => `${nf(v)} cntrs`, 8))}${sec(`Por unidade · ${per}`, barras(u.unCntr || {}, UNC, Math.max(1, u.cntr)))}${sec(`Por operação · ${per}`, barras(u.opsCntr || {}, nomesOp, Math.max(1, u.cntr)))}</div>`
      + '<div class="gl-pn">Contêineres pelo FUP da PGL (coluna VOLUME) ou, sem ele, pelos contêineres do BL.</div>';
  }
  if (k === 'c') {
    const ser = s.map(x => ({...x, ...Object.fromEntries(OPS.map(o => [o, x.opsCx[o] || 0]))}));
    return hero([[`Caixas · ${per}`, tK(u.cx), dTxt(delta(u.cx, a && a.cx))], ['Units por caixa', u.cx ? nf(u.q / u.cx, 1) : '-', ''],
      ['Caixas por processo', u.n ? nf(u.cx / u.n, 0) : '-', `<span class="gl-dl">${u.cntr ? `${nf(u.cx / u.cntr, 0)} por contêiner` : ''}</span>`]])
      + `<div class="gl-pc">${legenda(partes)}${colunas(ser, partes, tK)}</div>`
      + `<div class="gl-p2">${sec(`Caixas por tipo de embarque · ${per}`, barras(u.tipoCx || {}, TIPO, Math.max(1, u.cx)))}${sec(`Caixas por operação · ${per}`, barras(u.opsCx || {}, nomesOp, Math.max(1, u.cx)))}</div>`;
  }
  const ser = s.map(x => ({...x, ...Object.fromEntries(OPS.map(o => [o, x.opsQ[o] || 0]))}));
  return hero([[`Units · ${per}`, tK(u.q), dTxt(delta(u.q, a && a.q))], ['Média por processo', u.n ? nf(u.q / u.n, 0) : '-', '<span class="gl-dl">units por processo</span>'],
    ['Média por ' + lblG, tK(s.reduce((t, x) => t + x.q, 0) / (s.length || 1)), '']])
    + `<div class="gl-pc">${legenda(partes)}${colunas(ser, partes, tK)}</div>`
    + `<div class="gl-p2">${sec(`Países com mais units · ${per}`, lista5(u.paisQ || {}, tK, 8))}${sec(`Units por operação · ${per}`, barras(u.opsQ || {}, nomesOp, Math.max(1, u.q)))}</div>`;
}
const TIT = {n: 'Processos', p: 'Países de origem', k: 'Distância percorrida e CO₂', w: 'Peso bruto', cn: 'Contêineres', q: 'Units', c: 'Caixas'};
function abrePainel(k) {
  clearTimeout(S.pnT);
  let box = document.getElementById('gl-pop');
  if (!box) { box = document.createElement('section'); box.id = 'gl-pop'; box.className = 'gl-pop'; S.el.querySelector('.gl-body').appendChild(box);
    box.addEventListener('mouseenter', () => clearTimeout(S.pnT)); box.addEventListener('mouseleave', fechaPainelDepois);
    box.addEventListener('click', e => { const b = e.target.closest('[data-gran]'); if (b) { S.gran = b.dataset.gran; desenhaPainel(true); } }); }
  const novo = S.pn !== k; S.pn = k;
  S.el.querySelectorAll('.gl-kpi').forEach(c => c.classList.toggle('on', c.dataset.kk === k));
  desenhaPainel(novo);
}
function desenhaPainel(anima) {
  const box = document.getElementById('gl-pop'), k = S.pn, g = S.gran || 'mes';
  if (!box || !k) return;
  const filtros = [S.f.un, S.f.op && S.f.op.charAt(0) + S.f.op.slice(1).toLowerCase(), S.f.modal].filter(Boolean).join(' · ') || 'todas as unidades, operações e modais';
  box.innerHTML = `<header><div><span class="gl-pi">${KPI_ICON[k]}</span><div><h4>${TIT[k]}</h4><small>${E(filtros)}</small></div></div>
    <div class="gl-pt-g" role="tablist">${GRANS.map(([v, t]) => `<button type="button" role="tab" data-gran="${v}" class="${v === g ? 'on' : ''}">${t}</button>`).join('')}</div></header>
    <div class="gl-pb">${painel(k, g)}</div>`;
  box.hidden = false;
  if (anima && animOn()) { box.classList.remove('in'); void box.offsetWidth; box.classList.add('in'); }
  box.classList.toggle('anim', animOn());
}
function fechaPainelDepois() {
  clearTimeout(S.pnT);
  S.pnT = setTimeout(() => { const box = document.getElementById('gl-pop'); if (box) box.hidden = true; S.pn = null;
    S.el.querySelectorAll('.gl-kpi.on').forEach(c => c.classList.remove('on')); }, 280);
}

// ------------------------------------------------------------------ globo
function capColor(f) {
  if (f.id === BRASIL.id) return 'rgba(166,214,58,.74)';  // liso e com cor fixa; o reflexo vem do material próprio (materialBrasil)
  const p = S.agg.by[f.properties.pais];
  if (!p) return 'rgba(0,0,0,0)';
  const fl = S.flash && S.flash.pais === p.pais ? Math.max(0, 1 - (performance.now() - S.flash.t) / 1100) : 0;
  const on = S.sel === p.pais || S.hover === p.pais;
  const k = .5 + .5 * Math.sin(S.pulse + p.rank * .9);  // cada país pisca no seu ritmo
  const base = mix(COR.baixo, COR.hi, p.t, .45 + .35 * p.t + .12 * k);
  return fl > 0 || on ? mix('#e2ff7a', '#ffffff', Math.max(fl, on ? .45 : 0), .92) : base;
}
function polyAlt(f) {
  if (!S.started) return .004;  // montado na pré-carga rente ao globo; na entrada os países sobem
  if (f.id === BRASIL.id) return .018;
  const p = S.agg.by[f.properties.pais]; if (!p) return .004;
  return .008 + .045 * p.t + (S.sel === p.pais ? .02 : 0);
}
function tip(f) {
  if (f.id === BRASIL.id) return `<div class="gl-tip"><span class="gl-flag">${flag('Brasil')}</span><b>Brasil · destino</b><small>${nf(S.agg.tot.n)} processos ${perLabel()}</small></div>`;
  const p = S.agg.by[f.properties.pais]; if (!p) return '';
  return `<div class="gl-tip"><span class="gl-flag">${flag(p.pais)}</span><b>${E(p.pais)}</b><small>${nf(p.n)} processos · ${nf(p.share * 100, 1)}%${S.agg.tot.temV ? ' · ' + usd(p.v) : ''}</small></div>`;
}
function arcs() {
  const out = [], {lista, max} = S.agg;
  for (const p of lista) {
    const [lat, lng] = PAIS[p.pais];
    for (const [modal, n] of [['Marítimo', p.mar], ['Aéreo', p.aer]]) {
      if (!n) continue;
      const d = DEST[modal];
      out.push({pais: p.pais, modal, n, startLat: lat, startLng: lng, endLat: d.lat, endLng: d.lng,
        stroke: .18 + 1.15 * Math.sqrt(n / max), time: 2600 + (p.rank * 337) % 1800, gap: (p.rank * .173) % 1,
        color: modal === 'Aéreo' ? ['rgba(244,183,64,.08)', 'rgba(244,183,64,.95)'] : ['rgba(76,201,240,.08)', 'rgba(120,225,255,.95)']});
    }
  }
  return out;
}
function rings() {
  const out = S.agg.lista.slice(0, 14).map(p => ({lat: PAIS[p.pais][0], lng: PAIS[p.pais][1], r: 1.6 + 4.2 * p.t, per: 1500 + (p.rank * 211) % 900, c: '216,255,106'}));
  out.push({lat: DEST['Marítimo'].lat, lng: DEST['Marítimo'].lng, r: 7, per: 1300, c: '76,201,240'});
  out.push({lat: DEST['Aéreo'].lat, lng: DEST['Aéreo'].lng, r: 5, per: 1700, c: '244,183,64'});
  return out;
}
// etiquetas: todos os países de origem (os 6 maiores com bandeira e números; os demais compactos) e o Brasil.
// Quando duas se sobrepõem na tela, fica a do país com mais processos (declutter)
function pins() {
  const out = S.agg.lista.map(p => ({kind: p.rank <= 6 ? 'o' : 'm', pais: p.pais, lat: PAIS[p.pais][0], lng: PAIS[p.pais][1], p}));
  out.push({kind: 'br', pais: 'Brasil', lat: BRASIL.lat, lng: BRASIL.lng});
  return out;
}
function pinEl(d) {
  const el = document.createElement('div');
  el.className = 'gl-pin ' + d.kind;
  el.dataset.pais = d.pais;
  el.dataset.rank = d.kind === 'br' ? 0 : d.p.rank;
  // a biblioteca centraliza o elemento no ponto (estilo próprio); o deslocamento para a ponta tocar o país fica no interno
  el.innerHTML = `<div class="gl-pin-in">${d.kind === 'br'
    ? `<span class="gl-pin-box"><span class="gl-flag">${flag('Brasil')}</span><span><b>Brasil</b><small>destino · ${nf(S.agg.tot.n)} processos</small></span></span><i class="gl-pin-stem"></i>`
    : d.kind === 'o'
    ? `<span class="gl-pin-box"><span class="gl-flag">${flag(d.pais)}</span><span><b>${E(d.pais)}</b><small>${nf(d.p.n)} · ${nf(d.p.share * 100, 0)}%</small></span></span><i class="gl-pin-stem"></i>`
    : `<span class="gl-pin-box"><i class="gl-pin-dot"></i><b>${E(d.pais)}</b><small>${nf(d.p.n)}</small></span>`}</div>`;
  el.addEventListener('pointerup', ev => ev.stopPropagation());  // o clique na etiqueta não vira clique no globo
  el.addEventListener('click', ev => { ev.stopPropagation(); select(d.pais); });
  return el;
}
// Etiquetas sem sobreposição: cada uma tenta a posição padrão e depois acima, abaixo, à direita e à esquerda do país
// (um ponto marca o país); só some se não couber em lugar nenhum. Também desvia dos painéis.
const ov = (a, b) => !(a.right + 3 < b.left || a.left - 3 > b.right || a.bottom + 2 < b.top || a.top - 2 > b.bottom);
function declutter() {
  const card = S.el.getBoundingClientRect();
  const els = [...S.el.querySelectorAll('.gl-pin')];
  const pri = el => el.dataset.pais === S.sel ? -1 : +el.dataset.rank;
  els.sort((a, b) => pri(a) - pri(b));
  const placed = [...S.el.querySelectorAll('.gl-top>*, .gl-left>*, .gl-right, .gl-ticker, .gl-detail:not([hidden])')].map(e => e.getBoundingClientRect());
  for (const el of els) {
    if (el.dataset.vis === '0') { el.classList.add('hid'); continue; }
    const o = el.getBoundingClientRect(), inner = el.firstElementChild;
    if (!o.width || !inner) continue;
    const ax = o.left + o.width / 2, ay = o.top + o.height / 2, w = o.width, h = o.height;
    const cands = el.classList.contains('m')
      ? [[0, 0, 'c'], [0, -h - 2, 'up'], [0, h + 2, 'dn'], [w / 2 + 8, 0, 'rt'], [-(w / 2 + 8), 0, 'lf'], [0, -2 * h - 4, 'up'], [0, 2 * h + 4, 'dn'], [w / 2 + 8, -h - 2, 'rt'], [-(w / 2 + 8), -h - 2, 'lf']]
      : [[0, -h / 2 - 2, 'up'], [0, h / 2 + 6, 'dn'], [w / 2 + 10, 0, 'rt'], [-(w / 2 + 10), 0, 'lf'], [w / 2 + 10, -h / 2, 'rt'], [-(w / 2 + 10), -h / 2, 'lf'], [0, -h - 8, 'up']];
    let ok = null;
    for (const [dx, dy, pos] of cands) {
      const r = {left: ax + dx - w / 2, right: ax + dx + w / 2, top: ay + dy - h / 2, bottom: ay + dy + h / 2};
      if (r.left < card.left + 4 || r.right > card.right - 4 || r.top < card.top + 4 || r.bottom > card.bottom - 4) continue;
      if (!placed.some(p => ov(r, p))) { ok = [dx, dy, pos, r]; break; }
    }
    if (ok) {
      inner.style.transform = `translate(${ok[0]}px,${ok[1]}px)`; el.dataset.pos = ok[2];
      el.classList.remove('hid'); placed.push(ok[3]);
    } else el.classList.add('hid');
  }
}

// clique no globo pelo ponto do mouse: acha o país que contém o ponto (sem depender do 3D nem da posição do globo)
function inRing(x, y, ring) {
  let ins = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) ins = !ins;
  }
  return ins;
}
function inFeat(f, lng, lat) {
  const g = f.geometry || {}, polys = g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : [];
  return polys.some(p => inRing(lng, lat, p[0]) && !p.slice(1).some(hole => inRing(lng, lat, hole)));
}
function paisNoPonto(lat, lng) {
  for (const f of S.feats) {
    const n = f.properties.pais;
    if (n && (n === 'Brasil' || S.agg.by[n]) && inFeat(f, lng, lat)) return n;
  }
  let best = null, bd = 3.5;  // país pequeno (Singapura) ou clique na borda: a origem mais próxima até ~3,5°
  for (const p of S.agg.lista) {
    const [a, b] = PAIS[p.pais], d = Math.hypot(a - lat, (b - lng) * Math.cos(lat * Math.PI / 180));
    if (d < bd) { bd = d; best = p.pais; }
  }
  return best;
}
function cliqueNoGlobo(stage) {
  let down = null;
  stage.addEventListener('pointerdown', e => { down = {x: e.clientX, y: e.clientY, t: performance.now()}; });
  stage.addEventListener('pointerup', e => {
    if (!down || e.target.closest('.gl-pin')) return;
    const moveu = Math.hypot(e.clientX - down.x, e.clientY - down.y) > 6 || performance.now() - down.t > 700;
    down = null;
    if (moveu || !S.g || !S.agg) return;  // arrastar gira o globo; só o clique escolhe
    const r = stage.getBoundingClientRect(), c = S.g.toGlobeCoords(e.clientX - r.left, e.clientY - r.top);
    if (!c) return;
    const pais = paisNoPonto(c.lat, c.lng);
    if (pais) select(pais);
  });
}
// tamanho de cada país (graus) para o zoom: país pequeno aproxima mais, país grande menos
function spanDe(pais) {
  if (S.span[pais] != null) return S.span[pais];
  const f = S.feats.find(x => x.properties.pais === pais);
  let a = [90, -90, 180, -180];
  const walk = c => { if (typeof c[0] === 'number') { a = [Math.min(a[0], c[1]), Math.max(a[1], c[1]), Math.min(a[2], c[0]), Math.max(a[3], c[0])]; } else c.forEach(walk); };
  if (f) walk(f.geometry.coordinates);
  const lat = PAIS[pais] ? PAIS[pais][0] : BRASIL.lat;
  return (S.span[pais] = f ? Math.max(a[1] - a[0], (a[3] - a[2]) * Math.cos(lat * Math.PI / 180)) : 2);
}

async function initGlobe() {
  const stage = document.getElementById('gl-stage');
  if (typeof Globe === 'undefined' || typeof topojson === 'undefined') { stage.innerHTML = '<div class="gl-empty">Não foi possível carregar o globo neste navegador.</div>'; return; }
  const topo = await fetch('/static/globo/vendor/countries-110m.json?v=1').then(r => r.json());
  const porId = Object.fromEntries(Object.entries(PAIS).filter(([, v]) => v[2]).map(([k, v]) => [v[2], k]));
  S.feats = topojson.feature(topo, topo.objects.countries).features.filter(f => f.properties.name !== 'Antarctica');
  S.feats.forEach(f => { f.properties.pais = porId[f.id] || (f.id === BRASIL.id ? 'Brasil' : ''); });
  const g = S.g = new Globe(stage, {animateIn: false});
  // oceano e fundo em azul-petróleo; o lima do sistema fica nos dados (origens, Brasil, números)
  g.backgroundColor('rgba(0,0,0,0)').showAtmosphere(true).atmosphereColor('#5fb8e8').atmosphereAltitude(.17)
    .width(S.el.clientWidth).height(S.el.clientHeight);
  const mat = g.globeMaterial();
  mat.color.set('#0b2638'); if (mat.emissive) mat.emissive.set('#06141f'); mat.emissiveIntensity = 1; mat.shininess = 18;
  if (mat.specular) mat.specular.set('#1f4560');
  g.hexPolygonsData(S.feats).hexPolygonResolution(3).hexPolygonMargin(.38).hexPolygonUseDots(true).hexPolygonAltitude(.003)
    .hexPolygonColor(f => f.id === BRASIL.id ? 'rgba(0,0,0,0)' : 'rgba(176,206,224,.36)');  // Brasil liso (sem os pontinhos do mapa)
  g.polygonsTransitionDuration(animOn() ? 900 : 0)
    .polygonCapColor(capColor).polygonSideColor(() => 'rgba(181,220,60,.10)').polygonStrokeColor(f => f.id === BRASIL.id ? '#e2ff7a' : 'rgba(216,255,106,.55)')
    .polygonAltitude(polyAlt).polygonLabel(tip)
    .onPolygonHover(f => { S.hover = f && f.properties.pais ? f.properties.pais : null; stage.style.cursor = S.hover ? 'pointer' : 'grab'; });
  cliqueNoGlobo(stage);
  g.arcStartLat('startLat').arcStartLng('startLng').arcEndLat('endLat').arcEndLng('endLng').arcColor('color').arcStroke('stroke')
    .arcAltitudeAutoScale(.42).arcDashLength(.42).arcDashGap(.9).arcDashInitialGap('gap').arcDashAnimateTime('time').arcsTransitionDuration(animOn() ? 1200 : 0)
    .arcLabel(d => `<div class="gl-tip"><b>${E(d.pais)} → ${E(DEST[d.modal].nome)}</b><small>${nf(d.n)} processos ${d.modal === 'Aéreo' ? 'aéreos' : 'marítimos'}</small></div>`);
  g.ringLat('lat').ringLng('lng').ringMaxRadius('r').ringPropagationSpeed(2.2).ringRepeatPeriod('per')
    .ringColor(d => t => `rgba(${d.c},${Math.max(0, 1 - t) * .85})`);
  g.htmlElementsData([]).htmlLat('lat').htmlLng('lng').htmlAltitude(d => d.kind === 'br' ? .03 : .06).htmlElement(pinEl);
  if (g.htmlElementVisibilityModifier) g.htmlElementVisibilityModifier((el, vis) => { el.dataset.vis = vis ? '1' : '0'; });
  const ctl = g.controls();
  ctl.enableZoom = false; ctl.autoRotate = false; ctl.enableDamping = true; ctl.dampingFactor = .08; ctl.rotateSpeed = .55;
  ctl.addEventListener('start', () => { S.sway = false; S.idleAt = 0; paraIntro(); });
  ctl.addEventListener('end', () => { S.idleAt = performance.now(); });
  g.pointOfView(animOn() ? {lat: -14, lng: -52, altitude: 5.2} : HOME, 0);  // a entrada começa no Brasil (pedido do usuário)
  S.ro = new ResizeObserver(() => { if (S.g) S.g.width(S.el.clientWidth).height(S.el.clientHeight); });
  S.ro.observe(S.el);
  g.pauseAnimation();
}
// Reflexo sobre o Brasil (25/11/2026; o usuário recusou o pisca do país inteiro e depois a grade de pontos: "tem que
// ficar com a esfera lisa"): o Brasil fica liso, com material próprio, e a placa de vídeo desenha uma faixa de luz que
// atravessa o país na diagonal (nordeste → sudoeste) em ~5 s. A cada quadro só muda um número (uTempo): custo quase zero.
// O material é do mesmo tipo do padrão dos países (pego de um país já montado), com o trecho do reflexo injetado no shader.
function materialBrasil() {
  if (S.brMat !== undefined) return S.brMat;
  let base = null;
  S.g.scene().traverse(o => { if (!base && o.__globeObjType === 'polygon' && o.__defaultCapMaterial) base = o.__defaultCapMaterial; });
  if (!base) return null;  // os países ainda estão sendo montados
  const m = base.clone();
  m.color.set('#a6d63a'); m.transparent = true; m.opacity = .74; m.depthWrite = true;
  S.brU = {value: 0};
  m.onBeforeCompile = sh => {
    sh.uniforms.uTempo = S.brU;
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vPosBr;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvPosBr = position;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vPosBr;\nuniform float uTempo;')
      .replace('#include <dithering_fragment>', `#include <dithering_fragment>
        vec3 pBr = normalize(vPosBr);
        float latBr = 90.0 - degrees(acos(clamp(pBr.y, -1.0, 1.0)));
        float lngBr = 90.0 - degrees(atan(pBr.z, pBr.x));
        if (lngBr > 180.0) lngBr -= 360.0;
        float dBr = (5.0 - latBr) / 39.0 * 0.55 + (-34.0 - lngBr) / 40.0 * 0.45;
        float faseBr = fract(uTempo / 5.2) * 1.5 - 0.25;
        float kBr = exp(-pow((dBr - faseBr) / 0.075, 2.0));
        gl_FragColor.rgb += vec3(0.52, 0.58, 0.40) * kBr;
        gl_FragColor.a = min(1.0, gl_FragColor.a + 0.2 * kBr);`);
  };
  m.customProgramCacheKey = () => 'nexxus-brasil-reflexo';
  S.brMat = m;
  S.g.polygonCapMaterial(f => f.id === BRASIL.id ? S.brMat : null);
  return m;
}
function dados(anim) {
  const g = S.g; if (!g) return;
  g.polygonsData(S.feats.filter(f => f.id === BRASIL.id || S.agg.by[f.properties.pais])).polygonAltitude(polyAlt);
  g.arcsData([]); g.ringsData([]); g.htmlElementsData([]);
  const show = () => { g.arcsData(arcs()); g.ringsData(rings()); g.htmlElementsData(pins()); };
  if (anim && animOn()) setTimeout(show, 700); else show();
}

// sequência de entrada: globo chega de longe, países acendem, arcos saem para o Brasil, números sobem
function intro() {
  S.started = true; agregar(); kpis(); ranking(); ticker();
  const g = S.g; if (!g) return;
  dados(true);
  // entrada (pedido do usuário): aproxima do Brasil, onde chegam as mercadorias, e depois viaja até a Ásia e a Europa,
  // onde estão as origens; mexer no globo ou escolher um país interrompe a viagem
  if (animOn()) {
    S.sway = false;
    g.pointOfView({lat: -16, lng: -50, altitude: 2.05}, 2400);
    S.introT = [setTimeout(() => g.pointOfView(HOME, 3800), 4300),
                setTimeout(() => { S.sway = true; S.swayT = performance.now(); S.introT = null; }, 8700)];
  } else g.pointOfView(HOME, 0);
  S.el.classList.add('gl-on');
}
function refresh(anim) {
  agregar(); kpis(); ranking();
  if (S.pn) desenhaPainel(false);
  if (S.sel && S.sel !== 'Brasil' && !S.agg.by[S.sel]) S.sel = null;
  detail(); dados(anim);
}
function paraIntro() { if (S.introT) { S.introT.forEach(clearTimeout); S.introT = null; } }
// toggle: só o ranking desfaz a escolha clicando de novo; no globo e nas etiquetas o clique sempre abre o país
function select(pais, toggle = false) {
  paraIntro();
  S.sel = pais && !(toggle && S.sel === pais) ? pais : null;
  S.chOpen = null;
  ranking(); detail();
  if (!S.g) return;
  if (S.sel) {
    const br = S.sel === 'Brasil', [lat, lng] = br ? [-15, -52] : PAIS[S.sel]; S.sway = false; S.idleAt = 0;
    // zoom pelo tamanho do país, com o país um pouco à esquerda (o quadro de detalhe fica à direita)
    const alt = Math.min(1.9, Math.max(.75, .5 + spanDe(S.sel) / 34));
    S.g.pointOfView({lat, lng: lng + alt * 12, altitude: alt}, animOn() ? 1600 : 0);
    S.flash = {pais: S.sel, t: performance.now()};
  } else {
    S.g.pointOfView(HOME, animOn() ? 1400 : 0);
    setTimeout(() => { if (!S.sel) { S.sway = true; S.swayT = performance.now(); } }, 1500);
  }
  S.g.polygonAltitude(polyAlt);
  S.g.arcsData(arcs().filter(a => !S.sel || S.sel === 'Brasil' || a.pais === S.sel));  // país escolhido: só a rota dele até o Brasil
}

// laço leve: piscar (10 por segundo), balanço da câmera e pausa quando a Visão geral não aparece
// o globo para (render e animações) quando a página não aparece e também quando a tela de atualização, a de sistema
// encerrado ou a de carregamento estão por cima: a página fica livre para a atualização terminar (25/11/2026: o reflexo
// pesado deixou a aba presa em "Atualizando o NexxusDoc")
function visivel() {
  const boot = document.getElementById('boot-loader');
  if (document.getElementById('update-screen') || document.getElementById('offline-screen')) return false;
  if (S.naTela === false) return false;  // rolou a página e o globo saiu da vista: não desenha (IntersectionObserver)
  return S.el && S.el.isConnected && S.el.offsetParent !== null && !document.hidden && (!boot || boot.classList.contains('hidden'));
}
function tick() {
  const v = visivel();
  if (!v) { if (S.running && S.g) { S.g.pauseAnimation(); S.running = false; } return; }
  if (!S.running && S.g) { S.g.resumeAnimation(); S.running = true; }
  if (!S.started) { intro(); return; }
  if (!S.g) return;
  S.tk = (S.tk || 0) + 1;
  if (S.tk % 3 === 0) declutter();  // mede a tela a cada 0,3 s (não a cada passo)
  const now = performance.now();
  if (animOn()) {
    S.pulse += .32;
    if (!S.sel && S.agg.lista.length && (!S.flash || now - S.flash.t > 1600)) {  // um país por vez "acende"
      const top = S.agg.lista.slice(0, 10), i = S.flash ? (top.findIndex(p => p.pais === S.flash.pais) + 1) % top.length : 0;
      S.flash = {pais: top[i].pais, t: now};
      S.el.querySelectorAll('.gl-pin').forEach(el => el.classList.toggle('flash', el.dataset.pais === top[i].pais));
      S.el.querySelectorAll('#gl-rank li').forEach(el => el.classList.toggle('flash', el.dataset.pais === top[i].pais));
    }
    S.g.polygonCapColor(f => capColor(f));
    if (S.brMat === undefined) materialBrasil();  // reflexo do Brasil: montado uma vez; o tempo anda no swayFrame
    if (!S.sway && !S.sel && S.idleAt && now - S.idleAt > 9000) { S.sway = true; S.swayT = now; S.idleAt = 0; }
  }
}
// balanço da câmera no ritmo da tela: devagar entre a Ásia e o Brasil (os dois lados da rota); para ao arrastar
function swayFrame(now) {
  requestAnimationFrame(swayFrame);
  if (S.brU && S.running) S.brU.value = now / 1000;  // anda o reflexo do Brasil (só um número para a placa de vídeo)
  if (!S.g || !S.running || !S.sway || S.sel || !animOn()) return;
  const pv = S.g.pointOfView(), alvo = HOME.lng + 24 * Math.sin((now - S.swayT) / 9000);
  S.g.pointOfView({lat: pv.lat + (HOME.lat - pv.lat) * .01, lng: pv.lng + (alvo - pv.lng) * .015, altitude: pv.altitude + (HOME.altitude - pv.altitude) * .01}, 0);
}

async function mount(el) {
  if (!el || S.el === el) return;
  S.el = el;
  if (!S.data) { try { await preload(); } catch (e) { el.innerHTML = `<div class="gl-empty">${E(e.message)}</div>`; return; } }
  shell();
  try {
    await initGlobe();
    if (S.g) {  // pré-carga: países e pontos do mapa já montados (a entrada só anima)
      agregar(); S.g.polygonsData(S.feats.filter(f => f.id === BRASIL.id || S.agg.by[f.properties.pais])).polygonAltitude(polyAlt);
      S.g.resumeAnimation(); await new Promise(r => setTimeout(r, 400)); if (!visivel()) S.g.pauseAnimation(); else S.running = true;
    }
  } catch (e) { document.getElementById('gl-stage').innerHTML = `<div class="gl-empty">Globo indisponível: ${E(e.message)}</div>`; }
  clearInterval(S.loop); S.loop = setInterval(tick, 100);
  // fora da vista (página rolada) o globo não desenha nem anima
  try { new IntersectionObserver(es => { S.naTela = es[es.length - 1].isIntersecting; }, {threshold: 0}).observe(el); } catch (e) { /* sem suporte: segue */ }
  requestAnimationFrame(swayFrame);
}
return {preload, mount, select, _estado: () => S};
})();
