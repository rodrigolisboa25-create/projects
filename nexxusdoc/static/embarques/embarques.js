/* Página Embarques (19/11/2026; revista em 23/11/2026 a pedido do usuário): processos da pasta Sua Area › Processos
   (INLINE, PROMO, AMOSTRAS e ZELUS), lidos pelo n8n (embarques.py no servidor). Lista com filtros, ficha do processo
   (documentos, comparativo faturas × proforma × BL, pré-conferência do Checklist ID 677) e relatórios para a gerência.
   Valores em US$ só para master e owners (o servidor nem envia). */
window.nexusEmb = (() => {
const F0 = {q: '', op: '', modal: '', ano: '', mes: '', armador: '', origem: '', fab: '', sit: '', pgl: '', resp: '', otr: ''};
// Downloads em Excel com carregamento visível (pedido do usuário em 25/11/2026: ao clicar, mostrar que está gerando)
async function baixar(el) {
  if (el.dataset.ocupado) return;
  const antes = el.innerHTML; el.dataset.ocupado = '1'; el.classList.add('em-busy');
  el.innerHTML = '<span class="em-spin" aria-hidden="true"></span>Gerando o Excel…';
  let fim = 'Excel baixado ✓';
  try {
    const r = await fetch(el.dataset.emdl, {credentials: 'same-origin'});
    if (!r.ok) { let m = ''; try { m = (await r.json()).detail || ''; } catch (e) {} throw new Error(m || 'Erro ' + r.status); }
    const blob = await r.blob(), cd = r.headers.get('content-disposition') || '';
    const m = /filename\*=UTF-8''([^;]+)/i.exec(cd) || /filename="?([^";]+)"?/i.exec(cd);
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = m ? decodeURIComponent(m[1]) : (el.dataset.nome || 'NexxusDoc.xlsx');
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
  } catch (e) { fim = 'Não foi possível gerar'; el.title = e.message; }
  el.innerHTML = fim; el.classList.remove('em-busy');
  setTimeout(() => { el.innerHTML = antes; delete el.dataset.ocupado; }, 2500);
}
document.addEventListener('click', e => { const el = e.target.closest && e.target.closest('[data-emdl]'); if (el) { e.preventDefault(); baixar(el); } });
// Faturas × OTR Nike (25/11/2026): o número de cada fatura da pasta tem de existir no OTR do BL e vice-versa
const OTRS = {ok: ['Conferido com o OTR', '#2E8B57', 'OTR ok'], aguardando: ['Aguardando número no OTR', '#C9962E', 'OTR: aguardando'],
              divergente: ['Divergente', '#B9533F', 'OTR: divergente'], verificar: ['Conferir PDF', '#C2410C', 'OTR: conferir PDF'], sem_otr: ['BL fora do OTR', '#97A39D', 'fora do OTR'],
              sem_tcci: ['Sem faturas na pasta', '#5B7C99', 'sem faturas']};
const otrSt = r => r.otr ? r.otr.s : '';
// Andamento na PGL (FUP que chega por e-mail; 23/11/2026): fase pelas datas do relatório
const PGLF = {transito: ['Em trânsito', '#2F7FB8'], no_brasil: ['Aguardando desembaraço', '#C9962E'], desembaracado: ['Aguardando entrega', '#7B61C9'],
              entregue: ['Entregue no CD', '#2E8B57'], sem: ['Sem FUP da PGL', '#97A39D']};
const pglFase = r => r.pgl ? r.pgl.fase : 'sem';
// Checklist documental (23/11/2026): completo, em parte, só identificação (BOL), em branco ou ainda não lido
const CK_ROT = {completo: 'preenchido', parcial: 'preenchido em parte', identificacao: 'só identificação (BOL), nenhum item conferido', branco: 'em branco', nao_lido: 'ainda não lido', sem_ok: 'nenhum item conferido'};
const ckEstado = ck => !ck ? '' : ck.estado || (ck.nao_lido ? 'nao_lido' : ck.preenchido ? 'completo' : 'sem_ok');
const primeiroNome = n => { const p = String(n || '').trim().split(/\s+/); return p.length > 1 ? p[0] + ' ' + p[p.length - 1] : p[0] || ''; };
const S = {data: null, rows: [], view: 'lista', f: {...F0}, shown: 100, loading: false, poll: 0, animDone: false};
const OPS = ['INLINE', 'PROMO', 'AMOSTRAS', 'ZELUS'];
// Operações em tons sóbrios (só nas etiquetas da tabela)
const OPC = {INLINE: '#2F5D8A', PROMO: '#8A6D3B', AMOSTRAS: '#3D7A5A', ZELUS: '#5E5A8C'};
const animOn = () => !window.nexusAnim || window.nexusAnim.enabled();
// Situação (23/11/2026, pedido do usuário: "Falta documento" e "Verificar" soavam fortes demais): cor pela gravidade;
// pré-conferência só a partir de 2025 (antes = "Antes de 2025")
const SIT = {ok: ['Conferido', '#2E8B57'], verificar: ['Divergência', '#B9533F'], checklist: ['Checklist pendente', '#C9962E'],
             incompleto: ['Em montagem', '#5B7C99'], sem_conferencia: ['Sem conferência', '#97A39D'], historico: ['Antes de 2025', '#B7C0BB']};
const faltaDe = r => { const d = r.falta || ((r.conferencia || []).find(c => c.item === 'Documentos na pasta' && c.status !== 'ok') || {}).detalhe || ''; return /^Falta:/.test(d) ? d.replace(/^Falta:\s*/, 'falta ').replace(/\.$/, '') : ''; };
const MES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
const DOC = {bl: 'BL', awb: 'HAWB', tcci: 'TCCI', ci: 'Fatura', proforma: 'Proforma', pl: 'PL', checklist: 'Checklist', nf: 'NF', fci: 'FCI'};
const DOC_ORDER = ['bl', 'awb', 'tcci', 'ci', 'proforma', 'pl', 'checklist', 'nf', 'fci'];
const E = s => esc(s == null ? '' : String(s));
const nf = (v, c = 0) => v == null || Number.isNaN(+v) ? '-' : (+v).toLocaleString('pt-BR', {minimumFractionDigits: c, maximumFractionDigits: c});
const usd = v => v == null ? '-' : 'US$ ' + nf(v, 2);
const mi = v => v == null ? '-' : v >= 1e6 ? 'US$ ' + nf(v / 1e6, 2) + ' mi' : v >= 1e3 ? 'US$ ' + nf(v / 1e3, 1) + ' mil' : usd(v);
const brd = v => v ? (/^\d{4}-\d{2}-\d{2}$/.test(v) ? v.split('-').reverse().join('/') : new Date(v).toLocaleDateString('pt-BR')) : '-';
const root = () => document.getElementById('page-embarques');

/* Ícones dos cards: desenhos coloridos próprios, no estilo de emoji (regra do sistema: nada de emoji do Windows) */
const ICON = {
  proc: '<svg viewBox="0 0 32 32"><path d="M16 3 4 9v14l12 6 12-6V9z" fill="#C8955A"/><path d="M16 3 4 9l12 6 12-6z" fill="#E2B57E"/><path d="M16 15v14l12-6V9z" fill="#A8743F"/><path d="m9.5 6.2 12 6v4.6l2.6-1.3v-4.6l-12-6z" fill="#F4DDB5"/></svg>',
  ok: '<svg viewBox="0 0 32 32"><rect x="3" y="3" width="26" height="26" rx="8" fill="#2E9D5B"/><rect x="3" y="3" width="26" height="13" rx="8" fill="#47B874" opacity=".55"/><path d="m9.5 16.5 4.5 4.5 9-10" fill="none" stroke="#fff" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  warn: '<svg viewBox="0 0 32 32"><circle cx="13.5" cy="13.5" r="9" fill="#FFF4D6" stroke="#D99A1E" stroke-width="3.2"/><path d="m20.2 20.2 7 7" stroke="#8C5A12" stroke-width="4.4" stroke-linecap="round"/><path d="M13.5 9v5.2M13.5 17.6v.4" stroke="#C47F0E" stroke-width="2.8" stroke-linecap="round"/></svg>',
  bad: '<svg viewBox="0 0 32 32"><path d="M7 3h12l7 7v18a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" fill="#F3F6F8" stroke="#8C9BA5" stroke-width="1.6"/><path d="M19 3v7h7" fill="#D9E0E5" stroke="#8C9BA5" stroke-width="1.6" stroke-linejoin="round"/><path d="M9.5 15h9M9.5 19h6" stroke="#B3BEC5" stroke-width="2" stroke-linecap="round"/><circle cx="23" cy="23" r="7" fill="#D2483A"/><path d="m20.3 20.3 5.4 5.4m0-5.4-5.4 5.4" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/></svg>',
  clip: '<svg viewBox="0 0 32 32"><rect x="6" y="5" width="20" height="24" rx="3" fill="#F3EBD9" stroke="#B9893A" stroke-width="1.6"/><rect x="11" y="2.5" width="10" height="5.5" rx="1.6" fill="#C9962E"/><path d="m10 14 2 2 3.5-3.6M10 21l2 2 3.5-3.6" fill="none" stroke="#2E9D5B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M18 14.5h5M18 21.5h5" stroke="#B9A57E" stroke-width="2" stroke-linecap="round"/></svg>',
  units: '<svg viewBox="0 0 32 32"><path d="M3 21.5c0-2 1-3.5 3-4l5.2-1.5 3-6.5c.4-.8 1.3-1 2-.5l2.8 2c1.6 1.1 3.5 2 5.5 2.4l2.6.5c1.7.3 2.9 1.8 2.9 3.5V23H3z" fill="#3B6FB6"/><path d="M3 23h26v2.2c0 .8-.7 1.5-1.5 1.5h-23C3.7 26.7 3 26 3 25.2z" fill="#F4F6F8" stroke="#B9C3CC" stroke-width="1"/><path d="m11 16.2 3.6 1.8 4.8-3.8" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"/><path d="m16.2 12 1.6 1.1m-.2-3 1.6 1.2" stroke="#C8D7EE" stroke-width="1.6" stroke-linecap="round"/></svg>',
  money: '<svg viewBox="0 0 32 32"><rect x="2.5" y="8" width="27" height="16" rx="3" fill="#3E9B63"/><rect x="5" y="10.5" width="22" height="11" rx="2" fill="none" stroke="#9AD6AE" stroke-width="1.2"/><circle cx="16" cy="16" r="4.4" fill="#E9F7EE"/><path d="M16 13.2v5.6m1.6-4.4c-.3-.6-.9-.9-1.6-.9-.9 0-1.6.5-1.6 1.2s.7 1 1.6 1.1c.9.2 1.6.5 1.6 1.2s-.7 1.2-1.6 1.2c-.7 0-1.3-.3-1.6-.9" fill="none" stroke="#2C7A4A" stroke-width="1.2" stroke-linecap="round"/></svg>',
};

/* Bandeiras (desenho próprio, simplificado para 30×20) */
const FL = (b) => `<svg viewBox="0 0 30 20" class="em-flag" aria-hidden="true">${b}</svg>`;
const star = (cx, cy, r, c) => { let p = ''; for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? r * .42 : r; p += `${(cx + rr * Math.cos(a)).toFixed(2)},${(cy + rr * Math.sin(a)).toFixed(2)} `; } return `<polygon points="${p}" fill="${c}"/>`; };
const hs = (cs) => cs.map((c, i) => `<rect y="${20 / cs.length * i}" width="30" height="${20 / cs.length + .2}" fill="${c}"/>`).join('');
const vs = (cs) => cs.map((c, i) => `<rect x="${30 / cs.length * i}" width="${30 / cs.length + .2}" height="20" fill="${c}"/>`).join('');
const FLAGS = {
  'Vietnã': `<rect width="30" height="20" fill="#DA251D"/>${star(15, 10.4, 6, '#FFDD00')}`,
  'Indonésia': hs(['#CE1126', '#FFFFFF']),
  'China': `<rect width="30" height="20" fill="#DE2910"/>${star(6, 6, 3.6, '#FFDE00')}${star(11.5, 2.6, 1.1, '#FFDE00')}${star(13.2, 5, 1.1, '#FFDE00')}${star(13.2, 8.2, 1.1, '#FFDE00')}${star(11.5, 10.4, 1.1, '#FFDE00')}`,
  'Tailândia': `<rect width="30" height="20" fill="#A51931"/><rect y="3.33" width="30" height="13.33" fill="#F4F5F8"/><rect y="6.67" width="30" height="6.67" fill="#2D2A4A"/>`,
  'Índia': `${hs(['#FF9933', '#FFFFFF', '#138808'])}<circle cx="15" cy="10" r="2.4" fill="none" stroke="#000080" stroke-width=".9"/>`,
  'Camboja': `<rect width="30" height="20" fill="#032EA1"/><rect y="5" width="30" height="10" fill="#E00025"/><path d="M10.5 13.5h9v-1.5h-1v-2l-1-1.5-1 1.5v-2l-1.5-2-1.5 2v2l-1-1.5-1 1.5v2h-1z" fill="#fff"/>`,
  'Sri Lanka': `<rect width="30" height="20" fill="#FFBE29"/><rect x="1.2" y="1.2" width="3.6" height="17.6" fill="#00534E"/><rect x="4.8" y="1.2" width="3.6" height="17.6" fill="#EB7400"/><rect x="9.6" y="1.2" width="19.2" height="17.6" fill="#8D153A"/><path d="M14 13.5c1.5-3 4-4.5 6-4.5s3 1.5 4 3.5l-1.5.2c-.8-1.4-1.5-2-2.6-2-1.6 0-3.4 1.5-4.4 3z" fill="#FFBE29"/>`,
  'Paquistão': `<rect width="30" height="20" fill="#01411C"/><rect width="7.5" height="20" fill="#fff"/><circle cx="19.5" cy="10.5" r="5" fill="#fff"/><circle cx="20.8" cy="9.3" r="4.4" fill="#01411C"/>${star(22.6, 7.2, 1.8, '#fff')}`,
  'Turquia': `<rect width="30" height="20" fill="#E30A17"/><circle cx="11" cy="10" r="5" fill="#fff"/><circle cx="12.3" cy="10" r="4" fill="#E30A17"/>${star(17.4, 10, 2.3, '#fff')}`,
  'Geórgia': `<rect width="30" height="20" fill="#fff"/><rect x="13" width="4" height="20" fill="#E8112D"/><rect y="8" width="30" height="4" fill="#E8112D"/><path d="M6.5 2.5v4m-2-2h4M23.5 2.5v4m-2-2h4M6.5 13.5v4m-2-2h4M23.5 13.5v4m-2-2h4" stroke="#E8112D" stroke-width="1.3"/>`,
  'Malásia': `${[...Array(14)].map((_, i) => `<rect y="${i * 20 / 14}" width="30" height="${20 / 14 + .1}" fill="${i % 2 ? '#fff' : '#CC0001'}"/>`).join('')}<rect width="15" height="11.4" fill="#010066"/><circle cx="6" cy="5.7" r="3.6" fill="#FFCC00"/><circle cx="7.2" cy="5.7" r="3" fill="#010066"/>${star(11.4, 5.7, 2.4, '#FFCC00')}`,
  'Argentina': `${hs(['#74ACDF', '#FFFFFF', '#74ACDF'])}<circle cx="15" cy="10" r="1.8" fill="#F6B40E"/>`,
  'Jordânia': `${hs(['#000000', '#FFFFFF', '#007A3D'])}<path d="M0 0 13 10 0 20z" fill="#CE1126"/>${star(4.6, 10, 1.6, '#fff')}`,
  'Bósnia e Herzegovina': `<rect width="30" height="20" fill="#002395"/><path d="M8 0h14v20z" fill="#FECB00"/>${[0, 1, 2, 3, 4, 5].map(i => star(6.5 + i * 2.4, 1.6 + i * 3.4, 1, '#fff')).join('')}`,
  'Egito': `${hs(['#CE1126', '#FFFFFF', '#000000'])}<path d="M13.6 8h2.8l-.4 4h-2z" fill="#C09300"/>`,
  'Filipinas': `${hs(['#0038A8', '#CE1126'])}<path d="M0 0 13.5 10 0 20z" fill="#fff"/><circle cx="4.6" cy="10" r="2" fill="#FCD116"/>`,
  'Honduras': `${hs(['#0073CF', '#FFFFFF', '#0073CF'])}${star(15, 10, 1.2, '#0073CF')}${star(11.5, 8.6, 1, '#0073CF')}${star(11.5, 11.4, 1, '#0073CF')}${star(18.5, 8.6, 1, '#0073CF')}${star(18.5, 11.4, 1, '#0073CF')}`,
  'México': `${vs(['#006847', '#FFFFFF', '#CE1126'])}<circle cx="15" cy="10" r="2.4" fill="#8C6B2E" opacity=".85"/>`,
  'Taiwan': `<rect width="30" height="20" fill="#FE0000"/><rect width="15" height="10" fill="#000095"/><circle cx="7.5" cy="5" r="2.6" fill="#fff"/>`,
  'Itália': vs(['#009246', '#FFFFFF', '#CE2B37']),
  'Guatemala': `${vs(['#4997D0', '#FFFFFF', '#4997D0'])}<circle cx="15" cy="10" r="2.2" fill="none" stroke="#6C9A3D" stroke-width="1"/>`,
  'Singapura': `${hs(['#EF3340', '#FFFFFF'])}<circle cx="6.5" cy="5" r="3.4" fill="#fff"/><circle cx="8" cy="5" r="3.1" fill="#EF3340"/>${[[10.2, 3], [12.2, 4.4], [11.4, 6.8], [9, 6.8], [8.4, 4.4]].map(([x, y]) => star(x, y, .75, '#fff')).join('')}`,
  'El Salvador': `${hs(['#0F47AF', '#FFFFFF', '#0F47AF'])}<circle cx="15" cy="10" r="2.2" fill="none" stroke="#C9A227" stroke-width="1"/>`,
  'Coreia do Sul': `<rect width="30" height="20" fill="#fff"/><circle cx="15" cy="10" r="4.4" fill="#0047A0"/><path d="M10.6 10a4.4 4.4 0 0 1 8.8 0 2.2 2.2 0 0 1-4.4 0 2.2 2.2 0 0 0-4.4 0z" fill="#CD2E3A"/><path d="m5 4.5 3 -2m-2.4 3 3-2m-2.4 3 3-2M22 15.5l3 2m-3.6-1.2 3 2m-3.6-1.2 3 2M22 4.5l3 2m-3.6-1.2 3 2M5 15.5l3-2" stroke="#000" stroke-width=".9"/>`,
  'Bulgária': hs(['#FFFFFF', '#00966E', '#D62612']),
  'Brasil': `<rect width="30" height="20" fill="#009C3B"/><path d="M15 2.5 27 10 15 17.5 3 10z" fill="#FFDF00"/><circle cx="15" cy="10" r="4" fill="#002776"/>`,
  'Estados Unidos': `${[...Array(13)].map((_, i) => `<rect y="${i * 20 / 13}" width="30" height="${20 / 13 + .1}" fill="${i % 2 ? '#fff' : '#B22234'}"/>`).join('')}<rect width="12" height="10.8" fill="#3C3B6E"/>`,
  'Bangladesh': `<rect width="30" height="20" fill="#006A4E"/><circle cx="13.5" cy="10" r="5" fill="#F42A41"/>`,
  'Portugal': `<rect width="30" height="20" fill="#FF0000"/><rect width="12" height="20" fill="#006600"/><circle cx="12" cy="10" r="3.2" fill="#FFE900"/>`,
  'Japão': `<rect width="30" height="20" fill="#fff"/><circle cx="15" cy="10" r="5.6" fill="#BC002D"/>`,
};
const flag = c => FLAGS[c] ? FL(FLAGS[c]) : `<svg viewBox="0 0 30 20" class="em-flag" aria-hidden="true"><rect width="30" height="20" rx="2.5" fill="#E4EAE6" stroke="#0000001f"/><circle cx="15" cy="10" r="5.2" fill="none" stroke="#7C8C84" stroke-width="1.2"/><path d="M9.8 10h10.4M15 4.8c-2.6 3-2.6 7.4 0 10.4m0-10.4c2.6 3 2.6 7.4 0 10.4" fill="none" stroke="#7C8C84" stroke-width=".9"/></svg>`;

async function load() {
  if (S.loading) return; S.loading = true;
  try { S.data = await api('/api/embarques'); S.rows = S.data.processos || []; }
  catch (e) { root().innerHTML = `<div class="em-wrap"><div class="em-empty">${E(e.message)}</div></div>`; S.loading = false; return; }
  S.loading = false; render();
  clearTimeout(S.poll);
  if (S.data.status && S.data.status.rodando) S.poll = setTimeout(() => { if (!root().classList.contains('hidden')) load(); }, 20000);
}
function open() { if (!S.data) { root().innerHTML = '<div class="em-wrap"><div class="em-empty">Carregando…</div></div>'; load(); } else render(); }

const match = (r, f, skip) => {
  const q = f.q.trim().toLowerCase();
  if (q) { const hay = [r.nome, r.numero, r.bol, r.grupo, r.wfadim, r.ref, r.obs, r.navio, r.armador, r.resp, (r.pgl || {}).di, ...(r.conteineres || []), ...(r.fabricantes || []), ...(r.origens || []), ...(r.temporadas || [])].join(' ').toLowerCase(); if (!q.split(/\s+/).every(w => hay.includes(w))) return false; }
  if (skip !== 'pgl' && f.pgl && pglFase(r) !== f.pgl) return false;
  if (skip !== 'resp' && f.resp && (r.resp || 'Não identificado') !== f.resp) return false;
  if (skip !== 'op' && f.op && r.op !== f.op) return false;
  if (skip !== 'modal' && f.modal && (r.modal || 'Não identificado') !== f.modal) return false;
  if (skip !== 'ano' && f.ano && String(r.ano) !== f.ano) return false;
  if (skip !== 'mes' && f.mes && String(r.mes) !== f.mes) return false;
  if (skip !== 'armador' && f.armador && (r.armador || 'Não identificado') !== f.armador) return false;
  if (skip !== 'origem' && f.origem && !(r.origens || []).includes(f.origem)) return false;
  if (skip !== 'fab' && f.fab && !(r.fabricantes || []).includes(f.fab)) return false;
  if (skip !== 'sit' && f.sit && r.situacao !== f.sit) return false;
  if (skip !== 'otr' && f.otr && otrSt(r) !== f.otr) return false;
  return true;
};
const filtered = () => S.rows.filter(r => match(r, S.f));
const activeCount = () => Object.entries(S.f).filter(([, v]) => v).length;

/* Filtro: rótulo em cima, lista com contagem de cada opção (aplicando os outros filtros) */
function field(key, label, values, fmt = v => v) {
  const cnt = new Map();
  S.rows.filter(r => match(r, S.f, key)).forEach(r => values(r).forEach(v => cnt.set(v, (cnt.get(v) || 0) + 1)));
  let list = [...cnt.entries()];
  list.sort(key === 'ano' || key === 'mes' ? (a, b) => (key === 'ano' ? b[0] - a[0] : a[0] - b[0]) : (a, b) => b[1] - a[1]);
  if (key === 'fab' || key === 'origem') list = list.slice(0, 300);
  const cur = S.f[key];
  return `<label class="em-field${cur ? ' on' : ''}"><span>${E(label)}</span><select data-f="${key}" aria-label="${E(label)}"><option value="">Todos</option>${list.map(([v, n]) => `<option value="${E(v)}"${String(v) === cur ? ' selected' : ''}>${E(fmt(v))} (${nf(n)})</option>`).join('')}</select></label>`;
}
function filtersHtml() {
  const n = activeCount();
  return `<div class="em-fpanel">
    <div class="em-frow">
      <div class="em-search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></svg><input type="search" id="em-q" placeholder="Buscar processo, contêiner, navio, fabricante, WFADIM…" value="${E(S.f.q)}"></div>
      <span class="em-fcount">${n ? `${n} filtro${n > 1 ? 's' : ''} ativo${n > 1 ? 's' : ''}` : 'Nenhum filtro'}</span>
      <button type="button" class="em-clear" id="em-clear"${n ? '' : ' disabled'}><svg viewBox="0 0 24 24"><path d="M4 5h16l-6 7.5V19l-4-2v-4.5z"/><path d="m16.5 15.5 4 4m0-4-4 4"/></svg>Limpar filtros</button>
    </div>
    <div class="em-fgrid">
      ${field('op', 'Operação', r => [r.op])}${field('modal', 'Modal', r => [r.modal || 'Não identificado'])}
      ${field('sit', 'Situação', r => [r.situacao], v => (SIT[v] || [v])[0])}${field('otr', 'Faturas × OTR Nike', r => r.otr ? [r.otr.s] : [], v => (OTRS[v] || [v])[0])}
      ${field('ano', 'Ano', r => r.ano ? [r.ano] : [])}${field('mes', 'Mês', r => r.mes ? [r.mes] : [], v => MES[v - 1])}
      ${field('armador', 'Armador', r => [r.armador || 'Não identificado'])}${field('origem', 'País de origem', r => r.origens || [])}
      ${field('fab', 'Fabricante', r => r.fabricantes || [])}
      ${field('pgl', 'Andamento na PGL', r => [pglFase(r)], v => (PGLF[v] || [v])[0])}${field('resp', 'Responsável pela pasta', r => [r.resp || 'Não identificado'])}
    </div></div>`;
}

function kpis(rows) {
  const n = rows.length, c = s => rows.filter(r => r.situacao === s).length;
  const qtd = rows.reduce((a, r) => a + (r.qtd || 0), 0), val = rows.reduce((a, r) => a + (r.valor_usd || 0), 0);
  const conf = rows.filter(r => !['sem_conferencia', 'historico'].includes(r.situacao)).length;
  const k = (ic, l, v, h, cls = '', tip = '') => `<div class="em-kpi ${cls}"${tip ? ` title="${E(tip)}"` : ''}><small><i class="em-ic">${ICON[ic]}</i>${l}</small><div class="em-kv"><b>${v}</b><em>${h}</em></div></div>`;
  return k('proc', 'Processos', nf(n), `${nf(new Set(rows.map(r => r.op)).size)} operação(ões) no recorte`) +
    k('ok', 'Conferidos', nf(c('ok')), conf ? `${nf(c('ok') / conf * 100, 0)}% dos conferidos (desde 2025)` : '-', 'ok') +
    k('warn', 'Divergências', nf(c('verificar')), 'quantidade, valor, peso, contêiner, NCM ou BL não bate', 'bad') +
    k('clip', 'Checklist pendente', nf(c('checklist')), 'tudo bate; falta concluir o checklist', 'warn',
      'Documentos e números conferem; o checklist documental ainda não tem todos os itens com OK.') +
    k('bad', 'Em montagem', nf(c('incompleto')), 'ainda falta BL/HAWB, fatura ou proforma', 'mont',
      'A pasta do embarque ainda não tem um dos documentos obrigatórios para o modal: BL (marítimo) ou HAWB (aéreo), faturas e proforma.') +
    k('warn', 'Faturas × OTR', nf(rows.filter(r => ['divergente', 'verificar'].includes(otrSt(r))).length), 'divergentes ou com PDF a conferir', 'bad',
      'Processos em que o número de alguma fatura não bate com o OTR da Nike, ou em que algum PDF de fatura não pôde ser lido e precisa ser conferido à mão.') +
    k('units', 'Unidades faturadas', nf(qtd), 'soma das faturas (TCCI)') +
    (S.data.valores ? k('money', 'Valor faturado', mi(val), 'soma das faturas, em US$') : '');
}

function render() {
  const r0 = root(); if (!r0 || !S.data) return;
  const st = S.data.status || {}, rows = filtered();
  const fmtW = v => v ? new Date(v).toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'}) : '';
  const n8n = S.data.n8n || {};
  const when = n8n.em ? `Leitura automática (n8n, de hora em hora): última em ${fmtW(n8n.em)}` : (S.data.gerado_em ? `Leitura da pasta: ${fmtW(S.data.gerado_em)}` : '');
  const prog = st.rodando ? `<span class="em-run"><i></i>Carga do histórico: ${nf(st.feitos || 0)} de ${nf(st.total || 0)} pastas (as mais novas já estão aqui)</span>` : '';
  r0.innerHTML = `<div class="em-wrap">
    <div class="em-head"><div><div class="eyebrow">${E((S.data.pasta || 'Sua Area › Processos').toUpperCase())}</div><h1>Embarques</h1>
      <p>Cada pasta de embarque com os documentos e a pré-conferência do Checklist ID 677. A equipe continua salvando na pasta como sempre; o NexxusDoc só lê.</p>
      <small class="em-when">${when ? E(when) : 'A pasta ainda não foi lida.'}${S.data.pgl_em ? ` · Andamento da PGL: FUP de ${E(fmtW(S.data.pgl_em))}` : ''} ${prog}</small>
      ${otrBar(S.data.otr)}</div>
      <div class="em-actions"><button type="button" class="em-dl" data-emdl="/api/embarques/otr/excel" data-nome="Faturas_x_OTR_Nike.xlsx" title="Conferência do número de cada fatura com o OTR Nike: resumo por processo e as ocorrências para cobrar a Nike">Faturas × OTR (Excel)</button><button type="button" class="em-dl" data-emdl="/api/embarques/excel" data-nome="Embarques.xlsx">Exportar Excel</button></div></div>
    ${S.rows.length ? `${S.view === 'proforma' ? '' : `<div class="em-kpis">${kpis(rows)}</div>`}
    <div class="em-tabs" role="tablist"><button type="button" data-v="lista" class="${S.view === 'lista' ? 'on' : ''}" role="tab">Processos</button><button type="button" data-v="rel" class="${S.view === 'rel' ? 'on' : ''}" role="tab">Relatórios</button><button type="button" data-v="proforma" class="${S.view === 'proforma' ? 'on' : ''}" role="tab">Planilha proforma</button></div>
    ${S.view === 'proforma' ? '<div id="pf-root"></div>' : `${filtersHtml()}
    <div id="em-body">${S.view === 'lista' ? listHtml(rows) : relHtml(rows)}</div>`}`
    : `<div class="em-empty"><b>A pasta ainda não foi lida</b>A leitura é automática, pelo n8n, de hora em hora; os processos aparecem aqui sozinhos.</div>`}
    </div>`;
  bind();
  const pf = r0.querySelector('#pf-root');
  if (pf && window.nexusPf) { window.nexusPf.mount(pf, {processos: S.rows, pid: S.pfPid || ''}); S.pfPid = ''; }
}

function listHtml(rows) {
  const money = S.data.valores, part = rows.slice(0, S.shown);
  const docs = r => DOC_ORDER.filter(d => (r.docs || []).includes(d)).map(d => `<span class="em-doc">${DOC[d]}</span>`).join('');
  const orig = r => (r.origens || []).length ? `<span class="em-orig">${flag(r.origens[0])}${E(r.origens[0])}${r.origens.length > 1 ? ` <small>+${r.origens.length - 1}</small>` : ''}</span>` : '-';
  const resp = r => r.resp ? `<small class="em-resp" title="${E(r.resp_certo ? 'Criou a pasta: ' + r.resp : 'Última alteração na pasta (renomeada ou movida depois de criada): ' + r.resp)}">${E(primeiroNome(r.resp))}${r.resp_certo ? '' : '*'}</small>` : '';
  const pgl = r => { if (!r.pgl) return '<span class="em-pgl sem" title="Processo fora do FUP da PGL">-</span>';
    const p = r.pgl, [l, c] = PGLF[p.fase], dt = p.entrega || (p.fase !== 'entregue' && p.prev_entrega) || '';
    const tip = [p.etapa && 'PGL: ' + p.etapa, p.chegada && 'Chegada ' + brd(p.chegada), p.canal && 'Canal ' + p.canal.toLowerCase(), p.desembaraco && 'Desembaraço ' + brd(p.desembaraco), p.entrega ? 'Entregue ' + brd(p.entrega) : p.prev_entrega && 'Previsão de entrega ' + brd(p.prev_entrega)].filter(Boolean).join(' · ');
    return `<span class="em-pgl" style="--c:${c}" title="${E(tip)}"><i></i>${E(l)}</span>${dt ? `<small>${p.entrega ? '' : 'prev. '}${brd(dt)}</small>` : ''}`; };
  return `<div class="em-table"><table><thead><tr><th>Processo</th><th>Operação</th><th>Criada · por</th><th>Armador · navio</th><th>Origem</th><th class="n">Faturas</th><th class="n">Unidades</th>${money ? '<th class="n">Valor</th>' : ''}<th>Documentos</th><th>Situação</th><th>Andamento PGL</th></tr></thead><tbody>
    ${part.map(r => {
      const sub = [r.bol && 'BOL ' + r.bol, r.grupo, r.wfadim, r.ref].filter(Boolean).join(' · ') + (r.outras_pastas && r.outras_pastas.length ? ` · +${r.outras_pastas.length} pasta(s)` : '');
      return `<tr data-id="${E(r.id)}" tabindex="0"><td class="em-name" title="${E(r.nome + (sub ? ' · ' + sub : ''))}"><b>${E(r.nome)}</b>${sub ? `<small>${E(sub)}</small>` : ''}</td>
      <td><span class="em-op" style="--c:${OPC[r.op]}">${E(r.op)}</span><small>${E(r.modal || '-')}</small></td><td>${brd((r.criada || '').slice(0, 10))}${resp(r)}</td>
      <td title="${E([r.armador, r.navio].filter(Boolean).join(' · '))}">${E(r.armador || '-')}${r.navio ? `<small>${E(r.navio)}</small>` : ''}</td><td title="${E((r.origens || []).join(', '))}">${orig(r)}</td>
      <td class="n">${r.faturas ? nf(r.faturas) : '-'}${r.otr ? `<small class="em-otr" style="--c:${(OTRS[r.otr.s] || ['', '#97A39D'])[1]}" title="${E(otrTip(r.otr))}"><i></i>${E((OTRS[r.otr.s] || ['', '', r.otr.s])[2])}</small>` : ''}</td><td class="n">${r.qtd != null ? nf(r.qtd) : '-'}</td>${money ? `<td class="n">${r.valor_usd != null ? usd(r.valor_usd) : '-'}</td>` : ''}
      <td><div class="em-docs">${docs(r)}</div></td><td>${pill(r.situacao)}${r.situacao === 'incompleto' && faltaDe(r) ? `<small class="em-falta">${E(faltaDe(r))}</small>` : ''}</td><td>${pgl(r)}</td></tr>`;
    }).join('')}</tbody></table></div>
    <div class="em-more">${nf(Math.min(S.shown, rows.length))} de ${nf(rows.length)} processos${rows.length > S.shown ? ' <button type="button" class="secondary" id="em-more">Mostrar mais</button>' : ''}</div>`;
}
const pill = s => { const [l, c] = SIT[s] || [s, '#97A39D']; return `<span class="em-pill" style="--c:${c}">${E(l)}</span>`; };
const otrTip = o => [`${(OTRS[o.s] || [o.s])[0]}`, `${o.p || 0} fatura(s) na pasta · ${o.o || 0} linha(s) no OTR`,
  o.x && `${o.x} com número diferente do OTR`, o.v && `${o.v} PDF(s) a conferir (não lidos)`, o.f && `${o.f} na pasta e fora do OTR`, o.n && `${o.n} do OTR sem PDF`, o.a && `${o.a} aguardando o número no OTR`,
  o.d && `${o.d} com quantidade ou peso diferente (aviso)`].filter(Boolean).join(' · ');
const dtBr = v => v ? new Date(v).toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'}) : '-';
// Guardrail (pedido do usuário): sempre dizer de quando é o OTR usado e se é o mais recente
function otrBar(s) {
  if (!s) return '';
  const ok = s.atualizado;
  return `<div class="em-otrbar ${ok ? 'ok' : 'warn'}" title="Pasta: ${E(s.pasta || '')}">
    <i>${ok ? '<svg viewBox="0 0 24 24"><path d="m5 12.5 4.5 4.5L19 7"/></svg>' : '<svg viewBox="0 0 24 24"><path d="M12 7v6M12 16.5v.5"/></svg>'}</i>
    <span><b>OTR Nike ${ok ? 'atualizado' : 'desatualizado'}</b>${s.arquivo ? ` · extração da Nike de ${E(dtBr(s.extraido_em))} · lido em ${E(dtBr(s.lido_em))}` : ''}${s.aviso ? ` · ${E(s.aviso.replace(/^OTR desatualizado: /, ''))}` : ''}</span></div>`;
}
/* Ficha: faturas da pasta × OTR Nike do BL (o número de cada fatura tem de estar no OTR, e cada fatura do OTR tem PDF) */
function otrHtml(c, s, id) {
  if (!c) return '';
  const [lab, cor] = OTRS[c.status] || [c.status, '#97A39D'];
  const lista = (t, xs, cols) => xs && xs.length ? `<div class="em-otr-l"><b>${E(t)} · ${nf(xs.length)}</b><div class="em-table small"><table><thead><tr>${cols.map(([, h]) => `<th>${E(h)}</th>`).join('')}</tr></thead><tbody>
    ${xs.slice(0, 120).map(x => `<tr>${cols.map(([k]) => `<td>${E(Array.isArray(x[k]) ? x[k].map(z => `${z[0]}: OTR ${nf(z[1], 1)} × fatura ${nf(z[2], 1)}`).join('; ') : (typeof x[k] === 'number' ? nf(x[k]) : x[k] || '-'))}</td>`).join('')}</tr>`).join('')}</tbody></table></div></div>` : '';
  const msg = {ok: 'Todos os números de fatura da pasta estão no OTR deste BL, e todas as faturas do OTR têm o PDF.',
    aguardando: 'Os PDFs batem pelo pedido e material, mas a Nike ainda não pôs o número dessas faturas no OTR. O sistema confere de novo com o OTR do dia seguinte.',
    divergente: 'Há número de fatura que não bate entre a pasta e o OTR. Veja no quadro abaixo o que cobrar da Nike ou arrumar na pasta.',
    verificar: 'Algum PDF de fatura não pôde ser lido (vazio, imagem ou outro modelo). Confira o PDF à mão: o quadro mostra o arquivo e a linha do OTR.',
    sem_otr: 'Este BL ainda não está no OTR da Nike (embarque muito recente) ou já saiu dele (processo antigo).',
    sem_tcci: 'O OTR tem este BL, mas nenhuma fatura foi lida na pasta (falta o zip das TCCIs).'}[c.status] || '';
  return `<h3>Faturas × OTR Nike</h3>
    <div class="em-otr-box" style="--c:${cor}"><span class="em-pill" style="--c:${cor}">${E(lab)}</span>
      ${c.pdfs != null ? `<span class="em-otr-n"><b>${nf(c.pdfs || 0)}</b> na pasta</span><span class="em-otr-n"><b>${nf(c.otr || 0)}</b> no OTR</span><span class="em-otr-n"><b>${nf(c.conferidas || 0)}</b> conferidas pelo número</span>` : ''}
      <p>${E(msg)}</p>${otrBar(s)}
      ${c.status !== 'sem_otr' ? `<a class="em-link em-otr-dl" href="#" data-emdl="/api/embarques/otr/excel?pid=${encodeURIComponent(id)}" data-nome="Faturas_x_OTR_processo.xlsx">Baixar a conferência deste processo (Excel)</a>` : ''}</div>
    ${c.quadro ? quadroOtr(c.quadro) : lista('Na pasta e fora do OTR', c.fora, [['fatura', 'Número da fatura'], ['po', 'Pedido Nike'], ['material', 'Material'], ['qtd', 'Qtd']])
      + lista('No OTR e sem PDF na pasta', c.sem_pdf, [['fatura', 'Número da fatura'], ['po', 'Pedido Nike'], ['linha', 'Linha'], ['material', 'Material'], ['qtd', 'Qtd']])
      + lista('Aguardando o número no OTR', c.aguardando, [['fatura', 'Número no PDF'], ['po', 'Pedido Nike'], ['linha', 'Linha'], ['material', 'Material']])}`;
}
/* Quadro PDF × OTR (pedido do usuário: mostrar "onde está de fato a verificação"): uma linha por fatura, o que está no
   PDF da pasta ao lado do que está no OTR; célula que não bate em destaque; filtro por resultado */
const OTRR = {numero: ['Número diferente', '#C2453A'], outro_bl: ['No OTR em outro BL', '#C2453A'], fora: ['Na pasta e fora do OTR', '#C2453A'],
  sem_pdf: ['No OTR sem PDF', '#C2453A'], pdf_nao_lido: ['PDF não lido: conferir', '#C2410C'], nao_lido: ['Número não lido no PDF', '#C2410C'],
  pdf_nome: ['PDF sem texto: conferir', '#C2410C'], pdf_extra: ['PDF não reconhecido', '#B7791F'], aviso: ['Aviso', '#B7791F'], pelo_numero: ['Confere pelo número', '#2E8B57'],
  aguardando: ['Aguardando número no OTR', '#B7791F'], ok: ['Confere', '#2E8B57']};
function quadroOtr(q) {
  if (!q.length) return '';
  const cnt = {}; q.forEach(x => { cnt[x.r] = (cnt[x.r] || 0) + 1; });
  const num = (v, d) => v == null ? '<span class="em-otr-vz">-</span>' : nf(v, d);
  const difQ = x => x.q_pdf != null && x.q_otr != null && Math.abs(x.q_pdf - x.q_otr) > .5;
  const difP = x => x.p_pdf && x.p_otr && Math.abs(x.p_pdf - x.p_otr) > Math.max(.5, .005 * x.p_otr);
  const numF = (v, bad) => v ? `<b class="${bad ? 'bad' : ''}">${E(v)}</b>` : `<span class="em-otr-vz ${bad ? 'bad' : ''}">${bad === 'falta' ? 'não está' : 'vazio'}</span>`;
  return `<div class="em-otr-q"><div class="em-otr-qh"><b>Conferência PDF × OTR · ${nf(q.length)} linha(s)</b>
      <span class="em-otr-fs"><button type="button" class="on" data-otrf="">Todas</button>${Object.keys(OTRR).filter(k => cnt[k]).map(k => `<button type="button" data-otrf="${k}" style="--c:${OTRR[k][1]}"><i></i>${E(OTRR[k][0])} <small>${nf(cnt[k])}</small></button>`).join('')}</span></div>
    <div class="em-table small em-otr-tab"><table><thead>
      <tr><th rowspan="2">Resultado</th><th colspan="2" class="grp">Número da fatura</th><th rowspan="2">Pedido Nike</th><th rowspan="2">Linha</th><th rowspan="2">Material</th><th colspan="2" class="grp">Quantidade</th><th colspan="2" class="grp">Peso bruto (kg)</th></tr>
      <tr><th>No PDF (pasta)</th><th>No OTR</th><th class="n">PDF</th><th class="n">OTR</th><th class="n">PDF</th><th class="n">OTR</th></tr></thead><tbody>
      ${q.map(x => { const [l, c] = OTRR[x.r]; const dq = difQ(x), dp = difP(x);
        return `<tr data-r="${x.r}"><td class="em-otr-res"><span class="em-otr-r" style="--c:${c}"><i></i>${E(l)}</span>${x.obs ? `<small>${E(x.obs)}</small>` : ''}</td>
          <td>${numF(x.pdf, x.r === 'sem_pdf' ? 'falta' : x.r === 'numero' || x.r === 'nao_lido' ? 'bad' : '')}</td><td>${numF(x.otr, x.r === 'fora' ? 'falta' : x.r === 'numero' || x.r === 'outro_bl' || x.r === 'aguardando' || (x.r === 'sem_pdf' && !x.otr) ? 'bad' : '')}</td>
          <td>${E(x.po || '-')}</td><td>${E(x.linha || '-')}</td><td>${E(x.material || '-')}</td>
          <td class="n${dq ? ' bad' : ''}">${num(x.q_pdf)}</td><td class="n${dq ? ' bad' : ''}">${num(x.q_otr)}</td>
          <td class="n${dp ? ' bad' : ''}">${num(x.p_pdf, 1)}</td><td class="n${dp ? ' bad' : ''}">${num(x.p_otr, 1)}</td></tr>`; }).join('')}
    </tbody></table></div>
    <p class="em-otr-leg">O sistema procura o número de cada PDF da pasta no OTR deste BL (histórico de todos os OTRs desde jan/2026). Sem o número no OTR, liga pelo pedido e material (aguardando). PDF que o sistema não conseguiu ler nunca passa como conferido. Quantidade e peso diferentes são só aviso.</p></div>`;
}

/* ---------- Relatórios ---------- */
// Barras horizontais: um tom só (verde do sistema) em gradiente; rótulo com bandeira quando é país
function bars(items, opts = {}) {
  if (!items.length) return '<div class="em-none">Sem dados no recorte.</div>';
  const max = Math.max(...items.map(i => i.v)) || 1, fmt = opts.fmt || nf, tot = items.reduce((a, i) => a + i.v, 0);
  return `<div class="em-hbars${opts.cls ? ' ' + opts.cls : ''}">${items.map((i, k) => `<div class="em-hb" title="${E(i.l)}: ${E(fmt(i.v))}" style="--k:${k}">
    <span class="l">${opts.flags ? flag(i.l) : ''}<span>${E(i.l)}</span></span>
    <span class="b"><i style="width:${Math.max(1.5, i.v / max * 100).toFixed(1)}%;${i.c ? `--c1:${i.c[0]};--c2:${i.c[1]}` : ''}"></i></span>
    <span class="v">${E(fmt(i.v))}${opts.pct && tot ? `<small>${nf(i.v / tot * 100, 0)}%</small>` : ''}</span></div>`).join('')}</div>`;
}
// Mapa de calor: operação × mês, com o número em cada célula (intensidade pelo maior mês da própria operação)
// Número curto para caber no quadrado ("1,2 mi", "845 mil"); o valor completo fica na dica
const short = v => { const a = Math.abs(v); return a >= 1e6 ? nf(v / 1e6, a >= 1e7 ? 0 : 1) + ' mi' : a >= 1e4 ? nf(v / 1e3, 0) + ' mil' : a >= 1e3 ? nf(v / 1e3, 1) + ' mil' : nf(v); };
const HEAT = {n: ['Processos', r => 1, v => nf(v)], qtd: ['Unidades', r => r.qtd || 0, short], valor: ['Valor (US$)', r => r.valor_usd || 0, short]};
function heatmap(rows) {
  const mode = HEAT[S.heat] && (S.heat !== 'valor' || S.data.valores) ? S.heat : 'n', [, pick, fmt] = HEAT[mode];
  const full = v => mode === 'valor' ? usd(v) : nf(v);
  const by = new Map();
  rows.forEach(r => { if (!r.ano) return; const k = r.ano * 100 + r.mes; const o = by.get(k) || {}; o[r.op] = (o[r.op] || 0) + pick(r); by.set(k, o); });
  let keys = [...by.keys()].sort((a, b) => a - b);
  if (!keys.length) return '<div class="em-none">Sem dados no recorte.</div>';
  // meses seguidos (mês sem processo aparece com 0), últimos 18
  const all = []; for (let k = keys[0]; k <= keys[keys.length - 1]; k = (k % 100 === 12 ? (Math.floor(k / 100) + 1) * 100 + 1 : k + 1)) all.push(k);
  keys = all.slice(-18);
  const ops = OPS.filter(o => rows.some(r => r.op === o));
  const val = (k, o) => (by.get(k) || {})[o] || 0;
  const tot = k => ops.reduce((a, o) => a + val(k, o), 0);
  const mix = (t) => { const a = [238, 245, 234], b = [31, 90, 51]; return `rgb(${a.map((x, i) => Math.round(x + (b[i] - x) * t)).join(',')})`; };
  const cell = (v, max, k, o, key) => { const t = max ? Math.sqrt(v / max) : 0; return `<td class="hc${v ? ' click' : ''}" data-op="${o}" data-ym="${key}" style="--k:${k};background:${v ? mix(.12 + t * .88) : '#F7FAF5'};color:${t > .55 ? '#fff' : '#16251c'}" title="${o} · ${MES[key % 100 - 1]}/${Math.floor(key / 100)}: ${full(v)}${v ? ' · clique para ver os processos' : ''}">${v ? fmt(v) : ''}</td>`; };
  const years = []; keys.forEach((k, i) => { const y = Math.floor(k / 100); if (!years.length || years[years.length - 1][0] !== y) years.push([y, 1]); else years[years.length - 1][1]++; });
  let i = 0;
  const avgFmt = v => mode === 'n' ? nf(v, 1) : fmt(v);
  const seg = Object.entries(HEAT).filter(([k]) => k !== 'valor' || S.data.valores).map(([k, [l]]) => `<button type="button" data-heat="${k}" class="${k === mode ? 'on' : ''}">${l}</button>`).join('');
  return `<div class="em-heat-bar"><div class="em-seg-btns" role="group" aria-label="O que mostrar">${seg}</div><span>Clique num quadrado para ver os processos daquele mês</span></div>
    <div class="em-heat"><table>
    <thead><tr><th></th>${years.map(([y, n]) => `<th colspan="${n}" class="yr">${y}</th>`).join('')}<th></th></tr>
    <tr><th></th>${keys.map(k => `<th>${MES[k % 100 - 1]}</th>`).join('')}<th class="avg">Média/mês</th></tr></thead>
    <tbody>${ops.map(o => { const max = Math.max(...keys.map(k => val(k, o))); const avg = keys.reduce((a, k) => a + val(k, o), 0) / keys.length;
      return `<tr><th><span class="em-op" style="--c:${OPC[o]}">${o}</span></th>${keys.map(k => cell(val(k, o), max, i++, o, k)).join('')}<td class="avg" title="${full(avg)}">${avgFmt(avg)}</td></tr>`; }).join('')}
    <tr class="tot"><th>Total</th>${keys.map(k => `<td title="${full(tot(k))}">${fmt(tot(k))}</td>`).join('')}<td class="avg">${avgFmt(keys.reduce((a, k) => a + tot(k), 0) / keys.length)}</td></tr></tbody></table></div>
    <div class="em-heat-leg"><span>menos</span><i style="background:linear-gradient(90deg,${mix(.12)},${mix(1)})"></i><span>mais ${mode === 'n' ? 'processos' : mode === 'qtd' ? 'unidades' : 'valor'} no mês (em cada operação)</span></div>`;
}
/* Etapas do embarque até a entrega no CD, por operação (barra empilhada; datas do FUP da PGL) */
function etapasPgl(rows) {
  const SEG = [['Trânsito internacional', 'embarque', 'chegada', '#5B9BD5'], ['Chegada até o registro da DI', 'chegada', 'registro_di', '#C9962E'],
               ['Registro até o desembaraço', 'registro_di', 'desembaraco', '#B07CC6'], ['Desembaraço até a entrega', 'desembaraco', 'entrega', '#2E8B57']];
  const d = (a, b) => (Date.parse(b) - Date.parse(a)) / 864e5;
  const ls = OPS.map(o => {
    const rs = rows.filter(r => r.op === o && r.pgl && r.pgl.entrega);
    const med = SEG.map(([, a, b]) => { const v = rs.filter(r => r.pgl[a] && r.pgl[b]).map(r => d(r.pgl[a], r.pgl[b])).filter(x => x >= 0 && x < 300); return v.length ? v.reduce((x, y) => x + y, 0) / v.length : 0; });
    return {o, n: rs.length, med, tot: med.reduce((x, y) => x + y, 0)};
  }).filter(x => x.n);
  if (!ls.length) return '<div class="em-none">Sem processos entregues no recorte.</div>';
  const max = Math.max(...ls.map(x => x.tot), 1);
  return `<div class="em-etapas">${ls.map((x, k) => `<div class="em-et"><div class="t"><span class="em-op" style="--c:${OPC[x.o]}">${x.o}</span><small>${nf(x.n)} entregues · <b>${nf(x.tot, 1)} dias</b> do embarque à entrega</small></div>
      <div class="bar">${x.med.map((v, j) => v ? `<i style="--k:${k * 4 + j};width:${(v / max * 100).toFixed(2)}%;background:${SEG[j][3]}" title="${E(SEG[j][0])}: ${nf(v, 1)} dias">${v / max > .08 ? nf(v, 1) : ''}</i>` : '').join('')}</div></div>`).join('')}</div>
    <div class="em-legend">${SEG.map(s => `<span><i style="background:${s[3]}"></i>${s[0]}</span>`).join('')}</div>`;
}
/* Rosca (para poucos itens: ocupa a altura do card, total no centro, legenda com quantidade e percentual) */
const PAL = ['#2F5D8A', '#3D7A5A', '#8A6D3B', '#5E5A8C', '#97A39D'];
function donut(items, center) {
  items = items.filter(i => i.v > 0);
  if (!items.length) return '<div class="em-none">Sem dados no recorte.</div>';
  const tot = items.reduce((a, i) => a + i.v, 0), R = 70, C = 2 * Math.PI * R, gap = items.length > 1 ? 3 : 0;
  let acc = 0;
  const segs = items.map((i, k) => {
    const len = Math.max(0, i.v / tot * C - gap), off = -acc; acc += i.v / tot * C;
    return `<circle class="em-seg" cx="100" cy="100" r="${R}" fill="none" stroke="${i.c || PAL[k % PAL.length]}" stroke-width="30" stroke-dasharray="${len.toFixed(2)} ${(C - len).toFixed(2)}" stroke-dashoffset="${off.toFixed(2)}" style="--k:${k};--len:${len.toFixed(2)}" transform="rotate(-90 100 100)"><title>${E(i.l)}: ${nf(i.v)} (${nf(i.v / tot * 100, 1)}%)</title></circle>`;
  }).join('');
  return `<div class="em-donut"><svg viewBox="0 0 200 200" role="img" aria-label="${E(center)}"><circle cx="100" cy="100" r="${R}" fill="none" stroke="#ffffffa6" stroke-width="30"/>${segs}
    <text x="100" y="96" text-anchor="middle" class="dv">${nf(tot)}</text><text x="100" y="116" text-anchor="middle" class="dl">${E(center)}</text></svg>
    <ul>${items.map((i, k) => `<li><i style="background:${i.c || PAL[k % PAL.length]}"></i><span>${E(i.l)}</span><b>${nf(i.v)}</b><small>${nf(i.v / tot * 100, 1)}%</small></li>`).join('')}</ul></div>`;
}
function count(rows, fn, top = 10) {
  const m = new Map(); rows.forEach(r => fn(r).forEach(v => m.set(v, (m.get(v) || 0) + 1)));
  return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, top).map(([l, v]) => ({l, v}));
}
function relHtml(rows) {
  const money = S.data.valores;
  const sitByOp = OPS.map(o => { const rs = rows.filter(r => r.op === o); return {o, n: rs.length, parts: Object.keys(SIT).map(s => [s, rs.filter(r => r.situacao === s).length])}; }).filter(x => x.n);
  const issues = count(rows, r => (r.conf || []).filter(c => c[1] === 'verificar').map(c => c[0] === 'Documentos na pasta' ? 'Documento ainda não salvo na pasta' : c[0]));
  const card = (t, sub, body, cls = '') => `<section class="em-card ${cls}"><header><h3>${t}</h3><span>${sub}</span></header>${body}</section>`;
  const AMB = ['#E7C27A', '#B07D1E'];
  let html = card('Processos por mês', 'Pastas de embarque criadas em cada mês, por operação (últimos 18 meses); unidades e valor pelas faturas', heatmap(rows), 'wide');
  html += card('Situação da conferência por operação', 'Checklist ID 677: BL × faturas × proforma',
    sitByOp.length ? `<div class="em-stack">${sitByOp.map(x => `<div class="em-st"><span class="l"><span class="em-op" style="--c:${OPC[x.o]}">${x.o}</span><small>${nf(x.n)}</small></span><span class="b">${x.parts.map(([s, v]) => { const p = v / x.n * 100; return v ? `<i style="width:${p.toFixed(2)}%;--c:${SIT[s][1]}" title="${SIT[s][0]}: ${nf(v)} (${nf(p, 0)}%)">${p >= 8 ? `${nf(p, 0)}%` : ''}</i>` : ''; }).join('')}</span></div>`).join('')}</div>
      <div class="em-legend">${Object.values(SIT).map(([l, c]) => `<span><i style="background:${c}"></i>${l}</span>`).join('')}</div>` : '<div class="em-none">Sem dados.</div>');
  // Andamento na PGL (FUP por e-mail) e tempo do embarque até a entrega no CD, por operação
  html += card('Andamento na PGL', 'Pelo FUP diário da PGL (datas do relatório)',
    donut(Object.entries(PGLF).map(([k, [l, c]]) => ({l, c, v: rows.filter(r => pglFase(r) === k).length})), 'processos'));
  html += card('Do embarque à entrega no CD', 'Média em dias de cada etapa, processos entregues (FUP da PGL)', etapasPgl(rows));
  // Lado a lado os de altura parecida (pedido do usuário: nada de espaço vazio embaixo de um gráfico)
  html += card('Por armador', 'Marítimo, pelo BL', donut(count(rows.filter(r => r.modal === 'Marítimo'), r => [r.armador || 'Não identificado'])
    .map(i => i.l === 'Não identificado' ? {...i, c: '#B5BFBA'} : i), 'processos marítimos'));
  html += card('O que mais aparece para verificar', 'Itens da conferência que não bateram', bars(issues.map(i => ({...i, c: AMB}))));
  const noCk = rows.filter(r => r.op === 'INLINE' && r.modal === 'Marítimo' && (r.criada || '') >= '2025-06-06');
  html += card('Checklist documental (INLINE marítimo desde 06/2025)', 'Arquivo do checklist na pasta do embarque',
    donut([{l: 'Preenchido', v: noCk.filter(r => ckEstado(r.checklist) === 'completo').length, c: '#2E8B57'},
           {l: 'Preenchido em parte', v: noCk.filter(r => ckEstado(r.checklist) === 'parcial').length, c: '#7FB069'},
           {l: 'Só identificação (BOL), nenhum item conferido', v: noCk.filter(r => ['identificacao', 'sem_ok'].includes(ckEstado(r.checklist))).length, c: '#C9962E'},
           {l: 'Na pasta, em branco ou não lido', v: noCk.filter(r => ['branco', 'nao_lido'].includes(ckEstado(r.checklist))).length, c: '#D9B36A'},
           {l: 'Sem checklist', v: noCk.filter(r => !r.checklist).length, c: '#B9533F'}], 'processos'));
  html += card('Por país de origem', 'Pelas faturas (TCCI)', bars(count(rows, r => r.origens || []), {flags: true, pct: true, cls: 'flags'}), 'em-card-geo');
  html += card('Fabricantes com mais processos', 'Pelas faturas e proformas', bars(count(rows, r => r.fabricantes || [], 10)));
  if (money) {
    const byM = new Map(); rows.forEach(r => { if (r.ano && r.valor_usd) { const k = r.ano * 100 + r.mes; byM.set(k, (byM.get(k) || 0) + r.valor_usd); } });
    const ks = [...byM.keys()].sort((a, b) => a - b).slice(-12);
    html += card('Valor faturado por mês (US$)', 'Soma das faturas Nike (TCCI) dos processos criados no mês, últimos 12 meses', bars(ks.map(k => ({l: `${MES[k % 100 - 1]}/${String(k).slice(2, 4)}`, v: byM.get(k)})), {fmt: mi}));
    const fr = rows.filter(r => r.frete_usd_cntr), byF = new Map();
    fr.forEach(r => { const k = r.ano * 100 + r.mes; const a = byF.get(k) || [0, 0]; a[0] += r.frete_usd_cntr; a[1]++; byF.set(k, a); });
    const kf = [...byF.keys()].sort((a, b) => a - b).slice(-12);
    html += card('Frete marítimo médio por contêiner (US$)', `Basic Ocean Freight dos BLs da Maersk (${nf(fr.length)} BLs com o frete no documento)`, bars(kf.map(k => ({l: `${MES[k % 100 - 1]}/${String(k).slice(2, 4)}`, v: byF.get(k)[0] / byF.get(k)[1]})), {fmt: v => usd(v)}));
  }
  return `<div class="em-grid">${html}</div>`;
}

/* ---------- Ficha do processo ---------- */
async function ficha(id) {
  closeFicha();
  const box = document.createElement('div'); box.className = 'em-drawer-back'; box.id = 'em-drawer';
  box.innerHTML = '<aside class="em-drawer" role="dialog" aria-label="Ficha do embarque"><div class="em-empty">Carregando…</div></aside>';
  document.body.appendChild(box);
  box.addEventListener('mousedown', e => { if (e.target === box) closeFicha(); });
  document.addEventListener('keydown', escClose, true);
  let d; try { d = await api('/api/embarques/' + encodeURIComponent(id)); } catch (e) { box.querySelector('.em-drawer').innerHTML = `<div class="em-empty">${E(e.message)}</div>`; return; }
  const r = d.resumo, money = d.valores;
  const fat = d.arquivos.flatMap(f => ((f.dados || {}).faturas || []));
  const uniq = [...new Map(fat.map(x => [x.fatura || Math.random(), x])).values()];
  const bl = (d.arquivos.find(f => f.tipo === 'bl' && f.dados) || {}).dados;
  const prof = (d.arquivos.filter(f => f.tipo === 'proforma' && (f.dados || {}).lida).sort((a, b) => (a.mod || '').localeCompare(b.mod || '')).pop() || {}).dados;
  const fact = (l, v) => v != null && v !== '' && !(Array.isArray(v) && !v.length) ? `<div><small>${E(l)}</small><b>${E(Array.isArray(v) ? v.join(', ') : v)}</b></div>` : '';
  const stIcon = s => s === 'ok' ? '<svg viewBox="0 0 24 24"><path d="m5 12.5 4.5 4.5L19 7"/></svg>' : '<svg viewBox="0 0 24 24"><path d="M12 7v6M12 16.5v.5"/></svg>';
  box.querySelector('.em-drawer').innerHTML = `<header><div><div class="eyebrow">${E(r.op)}${r.grupo ? ' · ' + E(r.grupo) : ''}</div><h2>${E(r.nome)}</h2><div>${pill(r.situacao)}</div></div>
      <button class="em-x" type="button" aria-label="Fechar">×</button></header>
    <div class="em-facts">${fact(r.modal === 'Aéreo' ? 'HAWB completo' : 'BOL (BL completo)', r.bol)}${fact('Modal', r.modal)}${fact('Pasta criada em', brd((r.criada || '').slice(0, 10)))}${r.resp ? fact(r.resp_certo ? 'Criada por' : 'Última alteração na pasta', r.resp) : ''}${fact('Armador', r.armador)}${fact('Navio', r.navio)}${fact('Embarque (BL)', r.embarque ? brd(r.embarque) : '')}
      ${fact('Porto de embarque', r.porto_embarque)}${fact('Porto de descarga', r.porto_descarga)}${fact('Contêineres', r.conteineres)}${fact('Origem', r.origens)}${fact('Temporadas', r.temporadas)}
      ${money ? fact('Frete por contêiner (BL)', r.frete_usd_cntr != null ? usd(r.frete_usd_cntr) : '') + fact('Fossil Fuel Fee por contêiner', r.bunker_usd_cntr != null ? usd(r.bunker_usd_cntr) : '') : ''}
      ${fact(r.wfadim_fup ? 'WFADIM (do FUP da PGL)' : 'WFADIM', r.wfadim)}${fact('Ref. FISIA', r.ref)}${fact('Observação na pasta', r.obs)}${r.checklist ? fact('Checklist', `ID ${r.checklist.id || '-'}${r.checklist.revisado ? ' · ' + r.checklist.revisado : ''} · ${CK_ROT[ckEstado(r.checklist)] || ''}${r.checklist.itens_total ? ` (${r.checklist.itens_ok || 0} de ${r.checklist.itens_total} com OK)` : ''}`) : ''}</div>
    ${linhaPgl(d.pgl, money, r)}
    ${otrHtml(d.otr, d.otr_status, id)}
    ${custoHtml(d.custo)}
    ${compare(r, uniq, prof, bl, money)}
    <h3>Pré-conferência</h3><ul class="em-checks">${(r.conferencia || []).map(c => `<li class="${c.status}"><span class="ic">${stIcon(c.status)}</span><div><b>${E(c.item === 'Documentos na pasta' && c.status !== 'ok' ? 'Documentos ainda não salvos na pasta' : c.item)}</b><small>${E(c.detalhe)}</small></div></li>`).join('') || (r.situacao === 'historico' ? '<li>Processo anterior a 2025: a pré-conferência vale para os processos de 2025 em diante.</li>' : '<li>Sem documentos lidos para conferir.</li>')}</ul>
    ${r.fabricantes && r.fabricantes.length ? `<h3>Fabricantes</h3><p class="em-p">${E(r.fabricantes.join(' · '))}</p>` : ''}
    <h3>Documentos na pasta</h3><ul class="em-files">${d.arquivos.map(f => `<li><span class="em-doc">${E(DOC[f.tipo] || 'Outro')}</span><div><b>${E(f.rel)}</b><small>${nf(f.tam / 1024, 0)} KB · ${brd(f.mod)}${f.tipo_lido ? ' · reconhecido pelo conteúdo' : ''}${f.erro ? ' · ' + E(f.erro) : ''}${(f.dados || {}).faturas ? ' · ' + nf(f.dados.faturas.length) + ' fatura(s) lida(s)' : ''}${(f.dados || {}).itens_ok != null ? ' · ' + nf(f.dados.itens_ok) + ' item(ns) com OK' : ''}</small></div>${f.drive_id ? `<a href="https://drive.google.com/file/d/${encodeURIComponent(f.drive_id)}/view" target="_blank" rel="noopener">Abrir</a>` : d.pode_abrir ? `<a href="/api/embarques/${E(id)}/arquivo?rel=${encodeURIComponent(f.rel)}" target="_blank" rel="noopener">Abrir</a>` : ''}</li>`).join('')}</ul>
    <p class="em-p em-links">${d.pasta_drive ? `<a class="em-link" href="https://drive.google.com/drive/folders/${encodeURIComponent(d.pasta_drive)}" target="_blank" rel="noopener">Abrir a pasta no Drive</a>` : ''}<a class="em-link" href="#" data-pf="${E(id)}">Planilha proforma deste processo</a></p>
    ${uniq.length ? `<h3>Faturas (TCCI) · ${nf(uniq.length)}</h3><div class="em-table small"><table><thead><tr><th>Fatura</th><th>Data</th><th>PO</th><th>Material</th><th class="n">Qtd</th>${money ? '<th class="n">Valor</th>' : ''}<th class="n">Peso bruto</th><th>Fabricante</th></tr></thead><tbody>
      ${uniq.slice(0, 200).map(x => `<tr><td>${E(x.fatura)}</td><td>${brd(x.data)}</td><td>${E(x.po || x.po_cliente)}</td><td>${E(x.material)}</td><td class="n">${nf(x.quantidade)}</td>${money ? `<td class="n">${usd(x.valor)}</td>` : ''}<td class="n">${nf(x.peso_bruto, 1)}</td><td>${E(x.fabricante)}</td></tr>`).join('')}</tbody></table></div>` : ''}
    ${r.outras_pastas && r.outras_pastas.length ? `<h3>O mesmo processo em outra pasta</h3><ul class="em-files">${r.outras_pastas.map(o => `<li><div><b>${E(o.nome)}</b><small>${E(o.grupo)}</small></div><a href="#" data-other="${E(o.id)}">Ver</a></li>`).join('')}</ul>` : ''}
    <p class="em-foot">Lido em ${E(d.lido_em ? new Date(d.lido_em).toLocaleString('pt-BR') : '-')}${d.origem === 'n8n' ? ' pelo n8n' : ''} · pasta Sua Area › Processos › ${E(d.rel)}</p>`;
  const dr = box.querySelector('.em-drawer');
  dr.querySelector('.em-x').addEventListener('click', closeFicha);
  dr.querySelectorAll('[data-other]').forEach(a => a.addEventListener('click', e => { e.preventDefault(); ficha(a.dataset.other); }));
  dr.querySelectorAll('[data-otrf]').forEach(b => b.addEventListener('click', () => {  // filtro do quadro PDF × OTR
    const f = b.dataset.otrf; dr.querySelectorAll('[data-otrf]').forEach(x => x.classList.toggle('on', x === b));
    dr.querySelectorAll('.em-otr-tab tr[data-r]').forEach(tr => { tr.hidden = !!f && tr.dataset.r !== f; });
  }));
  dr.querySelector('[data-custo]')?.addEventListener('click', e => { e.preventDefault(); const k = e.currentTarget.dataset.custo; closeFicha(); showPage('custos'); window.nexusCustos?.open(k); });
  dr.querySelector('[data-pf]')?.addEventListener('click', e => { e.preventDefault(); closeFicha(); S.pfPid = id; S.view = 'proforma'; render(); window.scrollTo(0, 0); });
}
/* Custo do processo pelas MIROs da PGL (página Custos; só para quem vê valores) */
function custoHtml(c) {
  if (!c) return '';
  const brl = v => v == null ? '-' : 'R$ ' + nf(v, 2);
  return `<h3>Custo do processo (MIROs da PGL)</h3><div class="em-facts em-facts-pgl"><div><small>Custo total</small><b>${brl(c.total)}</b></div><div><small>Custo logístico</small><b>${brl(c.logistico)}</b></div><div><small>II e Siscomex</small><b>${brl(c.impostos)}</b></div>
    <div><small>Por unidade</small><b>${c.custo_un == null ? '-' : brl(c.custo_un)}</b></div><div><small>Logístico sobre o CIF</small><b>${c.pct_cif == null ? '-' : nf(c.pct_cif, 2) + '%'}</b></div><div><small>Detalhe</small><b><a href="#" class="em-link" data-custo="${E(c.chave)}">Ver na página Custos</a></b></div></div>`;
}
/* Andamento na PGL: linha do tempo do FUP (datas do relatório da PGL; nada estimado) */
function linhaPgl(p, money, r) {
  if (!p) {
    // O motivo depende da data do processo: novo (a PGL ainda não incluiu), antigo (antes de 2025) ou fora do relatório
    const cri = (r && r.criada || '').slice(0, 10), fup = (S.data && S.data.pgl_em || '').slice(0, 10), hoje = new Date().toISOString().slice(0, 10);
    const novo = cri && (Date.parse(hoje) - Date.parse(cri)) / 864e5 <= 20;
    const txt = novo ? `Ainda não está no FUP da PGL${fup ? ' de ' + brd(fup) : ''}: o processo foi aberto em ${brd(cri)} e a PGL o inclui no relatório quando abre o despacho. A data aparece aqui sozinha na próxima leitura do FUP.`
      : cri && cri < '2025-01-01' ? 'Processo anterior a 2025: os relatórios diários da PGL trazem os embarques de 2025 em diante.'
      : `Não está no FUP da PGL${fup ? ' de ' + brd(fup) : ''}. Pode ser um processo que a PGL não despachou ou que saiu do relatório antes de o NexxusDoc começar a guardar o histórico (23/11/2026).`;
    return `<h3>Andamento na PGL</h3><p class="em-p em-muted">${E(txt)}</p>`;
  }
  const passos = [['Embarque na origem', p.embarque], ['Previsão de chegada', !p.chegada && p.prev_chegada, 'prev'], ['Chegada ao Brasil', p.chegada],
    ['Presença de carga', p.presenca], ['Registro da DI', p.registro_di, '', [p.di && 'DI ' + p.di, p.canal && 'canal ' + p.canal.toLowerCase()].filter(Boolean).join(' · ')],
    ['Inspeção de madeira', p.insp_madeira], ['Desembaraço', p.desembaraco], ['Documento de transporte', p.entrega_doc],
    ['Previsão de entrega', !p.entrega && p.prev_entrega, 'prev'], ['Entrega no CD', p.entrega, '', p.cd || '']].filter(x => x[1]);
  const h = new Date().toISOString().slice(0, 10);
  const fatos = [['Situação na PGL', p.status], ['Agente de carga', p.agente], ['Transportadora', p.transportadora], ['Armazém / recinto', p.recinto || p.armazem],
    ['NF (DANFE)', p.danfe], ['ICMS pago em', p.icms_pago && brd(p.icms_pago)], ['WFADIM', p.wfadim], ...(money && p.cif != null ? [['Valor CIF', 'R$ ' + nf(p.cif, 2)]] : [])];
  return `<h3>Andamento na PGL</h3><div class="em-tl">${passos.map(([l, d, k, x]) => `<div class="em-tl-i${k === 'prev' ? ' prev' + (d < h ? ' late' : '') : ' done'}"><i></i><b>${E(l)}</b><span>${brd(d)}${k === 'prev' && d < h ? ' · vencida' : ''}</span>${x ? `<small>${E(x)}</small>` : ''}</div>`).join('')}</div>
    <div class="em-facts em-facts-pgl">${fatos.filter(f => f[1]).map(([l, v]) => `<div><small>${E(l)}</small><b>${E(v)}</b></div>`).join('')}</div>
    <p class="em-foot">FUP da PGL recebido em ${E(p.visto ? new Date(p.visto).toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'}) : '-')} · relatório completo em PGL › Relatórios da PGL</p>`;
}
/* Comparativo dos documentos: o que cada um traz, lado a lado (nada estimado; vazio quando o documento não traz) */
function compare(r, uniq, prof, bl, money) {
  if (!uniq.length && !prof && !bl) return '';
  const sum = k => uniq.length && uniq.some(x => x[k] != null) ? uniq.reduce((a, x) => a + (x[k] || 0), 0) : null;
  const rows = [
    ['Unidades', sum('quantidade'), prof ? prof.quantidade : null, null, 0, 0],
    ...(money ? [['Valor (US$)', sum('valor'), prof ? prof.valor : null, null, 2, .005]] : []),
    ['Peso bruto (kg)', sum('peso_bruto'), prof ? prof.peso_bruto : null, bl ? bl.peso_bruto : null, 1, .01],
    ['Peso líquido (kg)', sum('peso_liquido'), prof ? prof.peso_liquido : null, null, 1, null],  // proforma = peso da LI: só mostra
    ['Caixas', sum('caixas'), null, bl ? bl.caixas : null, 0, 0],
    ['CBM', null, null, bl ? bl.cbm : null, 2, 0],
  ];
  const ok = (vals, tol) => { const v = vals.filter(x => x != null && x !== 0); if (v.length < 2 || tol === null) return ''; const mx = Math.max(...v), mn = Math.min(...v); return (tol ? (mx - mn) / mx <= tol : Math.abs(mx - mn) < .5) ? 'ok' : 'bad'; };
  const list = (a) => a && a.length ? E(a.join(', ')) : '-';
  const tcciProf = prof && prof.tcci ? prof.tcci.length : null;
  return `<h3>Faturas × proforma × BL</h3><div class="em-cmp"><table><thead><tr><th></th><th>Faturas (TCCI)</th><th>Proforma</th><th>${r.modal === 'Aéreo' ? 'HAWB' : 'BL'}</th><th></th></tr></thead><tbody>
    ${rows.filter(x => x[1] != null || x[2] != null || x[3] != null).map(([l, a, b, c, dec, tol]) => { const s = ok([a, b, c], tol); return `<tr><th>${l}</th><td>${a != null ? nf(a, dec) : '-'}</td><td>${b != null ? nf(b, dec) : '-'}</td><td>${c != null ? nf(c, dec) : '-'}</td><td class="st">${s ? `<span class="em-dot ${s}" title="${s === 'ok' ? 'Bate' : 'Não bate'}"></span>` : ''}</td></tr>`; }).join('')}
    <tr><th>Faturas</th><td>${nf(uniq.length)} lida(s)</td><td>${tcciProf != null ? nf(tcciProf) + ' citada(s)' : '-'}</td><td>-</td><td class="st">${tcciProf != null && uniq.length ? `<span class="em-dot ${tcciProf === uniq.length ? 'ok' : 'bad'}"></span>` : ''}</td></tr>
    <tr><th>Contêiner</th><td>-</td><td>${list(prof && prof.conteineres)}</td><td>${list(bl && bl.conteineres)}</td><td></td></tr>
    <tr><th>NCM</th><td>-</td><td>${list(prof && prof.ncm)}</td><td>${list(bl && bl.ncm)}</td><td></td></tr>
    ${prof ? `<tr><th>Linhas da proforma</th><td>-</td><td>${nf(prof.linhas)}${prof.alt_preco || prof.alt_qtd ? ` · ${nf(prof.alt_preco || 0)} com preço alterado, ${nf(prof.alt_qtd || 0)} com quantidade alterada` : ''}</td><td>-</td><td></td></tr>` : ''}
    </tbody></table></div>`;
}
function escClose(e) { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closeFicha(); } }
function closeFicha() { document.getElementById('em-drawer')?.remove(); document.removeEventListener('keydown', escClose, true); }

function bind() {
  const r0 = root();
  r0.querySelectorAll('[data-v]').forEach(b => b.addEventListener('click', () => { S.view = b.dataset.v; render(); }));
  // Gráficos animados só na PRIMEIRA vez que a pessoa abre os Relatórios (pedido do usuário; filtro não anima de novo)
  const cards = [...r0.querySelectorAll('.em-card')];
  if (cards.length && !S.animDone) {
    S.animDone = true;
    if (animOn() && 'IntersectionObserver' in window) {
      const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('em-anim'); io.unobserve(e.target); } }), {threshold: .15});
      cards.forEach(c => { c.classList.add('em-wait'); io.observe(c); });
    }
  }
  r0.querySelectorAll('[data-heat]').forEach(b => b.addEventListener('click', () => { S.heat = b.dataset.heat; render(); }));
  // Quadrado do mapa de calor: abre a lista com a operação, o ano e o mês daquele quadrado
  r0.querySelectorAll('.em-heat td.hc.click').forEach(td => td.addEventListener('click', () => {
    const ym = +td.dataset.ym;
    S.f = {...S.f, op: td.dataset.op, ano: String(Math.floor(ym / 100)), mes: String(ym % 100)}; S.view = 'lista'; S.shown = 100; render();
    root().querySelector('.em-table')?.scrollIntoView({behavior: 'smooth', block: 'start'});
  }));
  r0.querySelectorAll('[data-f]').forEach(s => s.addEventListener('change', () => { S.f[s.dataset.f] = s.value; S.shown = 100; render(); }));
  const q = r0.querySelector('#em-q'); let t = 0;
  q?.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => { S.f.q = q.value; S.shown = 100; render(); const n = root().querySelector('#em-q'); n.focus(); n.setSelectionRange(n.value.length, n.value.length); }, 250); });
  r0.querySelector('#em-clear')?.addEventListener('click', () => { S.f = {...F0}; S.shown = 100; render(); });
  r0.querySelector('#em-more')?.addEventListener('click', () => { S.shown += 200; render(); });
  r0.querySelectorAll('tr[data-id]').forEach(tr => { tr.addEventListener('click', () => ficha(tr.dataset.id)); tr.addEventListener('keydown', e => { if (e.key === 'Enter') ficha(tr.dataset.id); }); });
}
// filtrar: abre a lista já filtrada (ex.: país clicado no globo da Visão geral)
const filtrar = f => { S.f = {...F0, ...f}; S.view = 'lista'; S.shown = 100; };
return {open, load, ficha, flag, filtrar, _estado: () => S};  // flag: bandeiras desenhadas, também no globo da Visão geral
})();
