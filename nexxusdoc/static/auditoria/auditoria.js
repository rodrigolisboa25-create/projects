/* Pagina Auditoria (10/11/2026, pedido do usuario): espelho da planilha mestre de Controles Internos ("Arquivo Geral -
   gestora da area"): controles, recomendacoes da auditoria e solicitacoes de evidencia, mais o ciclo do ano
   (Interim / Roll Forward / Remediacao) e o ROTEIRO DE EVIDENCIAS de cada solicitacao, montado pelo agente da Auditoria
   no n8n a partir das pastas do Drive e da base de estudo. Nada e enviado a auditoria nem ao Connect.
   Dados: /api/auditoria (espelho do n8n de hora em hora, "Sincronizar agora" ou o retrato curado). Acesso: todos veem o
   icone; por enquanto so o master e a gerencia navegam (trava no servidor). */
(() => {
'use strict';
// 11/11/2026 (pedidos do usuario): aba Matriz de risco (probabilidade x impacto), Ciclo do ano como calendario com
// navegacao (ano e mes) mantendo a coluna dos controles, cards claros em gradiente (uma cor cada), aba selecionada em
// destaque, data da solicitacao na tabela e link direto em todo nome de pasta.
const TODAY = new Date();
const S = {data: null, tab: 'solicitacoes', busca: '', bu: '', proc: '', sit: '', open: null, plan: {}, watch: 0, sync: false,
           cal: {view: 'ano', ano: TODAY.getFullYear(), mes: TODAY.getMonth() + 1}, mx: {bu: '', sel: ''}};
const root = () => document.getElementById('page-audit');
const E = s => (typeof esc === 'function' ? esc(s) : String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c])));
const D = v => !v ? '-' : /^\d{4}-\d{2}-\d{2}$/.test(v) ? v.split('-').reverse().join('/') : v;
const DT = v => { if (!v) return '-'; const d = new Date(v); return isNaN(d) ? E(v) : d.toLocaleDateString('pt-BR') + ' ' + d.toLocaleTimeString('pt-BR', {hour: '2-digit', minute: '2-digit'}); };
const V = v => (v && String(v).trim()) ? E(v) : '-';
const norm = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const I = p => `<svg viewBox="0 0 24 24" aria-hidden="true">${p}</svg>`;
const IC = {
  shield: I('<path d="M12 3 5 6v5.5c0 4.2 2.9 7.9 7 9.5 4.1-1.6 7-5.3 7-9.5V6z"/><path d="m9 12 2.2 2.2L15.5 10"/>'),
  rec: I('<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.6 10.8c.7.6 1.1 1.4 1.1 2.2h5c0-.8.4-1.6 1.1-2.2A6 6 0 0 0 12 3z"/>'),
  inbox: I('<path d="M4 13.5 6.5 5h11l2.5 8.5V19a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19z"/><path d="M4 13.5h4.5l1.2 2.5h4.6l1.2-2.5H20"/>'),
  cycle: I('<path d="M20 11a8 8 0 0 0-14.3-4.9L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.3 4.9L20 16"/><path d="M20 20v-4h-4"/>'),
  check: I('<path d="m5 12.5 4.5 4.5L19 7.5"/>'),
  clock: I('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'),
  warn: I('<path d="M12 4 2.8 19.5h18.4z"/><path d="M12 10v4.5m0 2.5h.01"/>'),
  ext: I('<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v4.5a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6H10"/>'),
  x: I('<path d="M6 6l12 12M18 6 6 18"/>'),
  lock: I('<rect x="5" y="11" width="14" height="9.5" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>'),
  search: I('<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>'),
  link: I('<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>'),
  folder: I('<path d="M3.5 7.5A1.5 1.5 0 0 1 5 6h4l2 2h8a1.5 1.5 0 0 1 1.5 1.5v8A1.5 1.5 0 0 1 19 19H5a1.5 1.5 0 0 1-1.5-1.5z"/>'),
  ticket: I('<path d="M4 8a2 2 0 0 0 0 4v4h16v-4a2 2 0 0 1 0-4V4H4z" transform="translate(0 2)"/><path d="M14 6v12" stroke-dasharray="2 2"/>'),
  sync: I('<path d="M20 11a8 8 0 0 0-14.3-4.9L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.3 4.9L20 16"/><path d="M20 20v-4h-4"/>'),
  map: I('<path d="M4 6.5 9 4l6 2.5 5-2.5v13l-5 2.5-6-2.5-5 2.5z"/><path d="M9 4v15M15 6.5v13"/>'),
  mail: I('<rect x="3.5" y="5.5" width="17" height="13" rx="2"/><path d="m4 7 8 6 8-6"/>'),
  sap: I('<rect x="3.5" y="4.5" width="17" height="13" rx="2"/><path d="M8 21h8M12 17.5V21M7 9h10M7 13h6"/>'),
  new: I('<path d="M12 4v16M4 12h16"/>'),
  edit: I('<path d="m4 20 4-1 10.5-10.5a1.5 1.5 0 0 0 0-2.1l-.9-.9a1.5 1.5 0 0 0-2.1 0L5 16z"/>'),
  copy: I('<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>'),
  robot: I('<rect x="5" y="8" width="14" height="11" rx="2.5"/><path d="M12 4v4M9 13h.01M15 13h.01M9.5 16.5h5"/>'),
  grid: I('<rect x="3.5" y="3.5" width="17" height="17" rx="2"/><path d="M3.5 9.2h17M3.5 14.8h17M9.2 3.5v17M14.8 3.5v17"/>'),
  cal: I('<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>'),
  left: I('<path d="m14.5 6-6 6 6 6"/>'),
  right: I('<path d="m9.5 6 6 6-6 6"/>'),
  book: I('<path d="M5 4.5h10a3 3 0 0 1 3 3V20H8a3 3 0 0 1-3-3z"/><path d="M5 17a3 3 0 0 1 3-3h10"/>'),
};
const MONTHS = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
const MON = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
const WEEK = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S'];
const isoDay = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const TODAY_ISO = isoDay(TODAY);
const folderLink = (href, label) => href ? `<a class="au-ext au-folder-link" href="${E(href)}" target="_blank" rel="noopener">${IC.folder}${E(label)}</a>` : `<span class="au-folder">${IC.folder}${E(label)}</span>`;
const PHASE_CLASS = {'Interim': 'int', 'Roll Forward': 'rf', 'Remediação': 'rem', 'Interim e Roll Forward': 'int'};

const ctrls = () => S.data?.controles || [];
const recs = () => S.data?.recomendacoes || [];
const sols = () => S.data?.solicitacoes || [];
const ctrl = ref => ctrls().find(c => c.ref === ref);
const solKey = id => String(id || '').toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 24);

// Situacao de cada item (rotulo + tipo): o tipo da a cor; rotulo e icone vao sempre juntos (nunca so a cor).
function recSit(r) {
  if (norm(r.status) === 'concluido') return {k: 'ok', t: 'Concluído'};
  const prazo = r.novo_deadline || r.deadline;
  if (prazo && prazo < S.data.hoje) return {k: 'late', t: 'Prazo vencido'};
  return {k: 'wait', t: r.status || 'Em aberto'};
}
function solSit(s) {
  if (norm(s.status_area) === 'concluido') return {k: 'ok', t: 'Concluído'};
  if (s.data_prevista && s.data_prevista < S.data.hoje) return {k: 'late', t: 'Atrasada'};
  return {k: 'wait', t: s.status_area || 'Em aberto'};
}
function ctrlSit(c) {
  if (norm(c.aprovacao_gerente) === 'aprovado') return {k: 'ok', t: 'Aprovado'};
  return {k: 'wait', t: 'Sem aprovação'};
}
const pill = s => `<span class="au-pill ${s.k}">${s.k === 'ok' ? IC.check : s.k === 'late' ? IC.warn : IC.clock}${E(s.t)}</span>`;
const bu = v => v ? `<span class="au-tag">${E(v)}</span>` : '-';
const person = v => (v && String(v).trim()) ? `<span class="au-person">${E(String(v).trim())}</span>` : '<span class="au-muted">-</span>';
const phaseTag = f => f && f.fase && f.fase !== 'A definir' ? `<span class="au-phase ${PHASE_CLASS[f.fase] || ''}">${E(f.fase)}${f.rotulo ? ` · ${E(f.rotulo)}` : ''}</span>` : '<span class="au-muted">-</span>';
const flag = s => s.novo ? `<span class="au-flag new">${IC.new}Nova</span>` : s.alterado ? `<span class="au-flag chg" title="Alterado: ${E((s.alterados || []).join(', '))}">${IC.edit}Alterada</span>` : '';
const planChip = st => !st ? '' : st.status === 'pronto' ? `<span class="au-plan ok">${IC.map}Roteiro pronto</span>`
  : st.status === 'gerando' ? `<span class="au-plan busy"><i></i>Montando roteiro…</span>`
  : st.status === 'desatualizado' ? `<span class="au-plan old">${IC.map}Roteiro desatualizado</span>`
  : st.status === 'erro' ? `<span class="au-plan err" title="${E(st.erro || '')}">${IC.warn}Roteiro com erro</span>` : '';
const ext = (href, label) => href ? `<a class="au-ext" href="${E(href)}" target="_blank" rel="noopener">${IC.ext}${E(label)}</a>` : '';
const toast = msg => { document.querySelector('.au-toast')?.remove(); const t = document.createElement('div'); t.className = 'au-toast'; t.textContent = msg; document.body.appendChild(t); setTimeout(() => t.remove(), 3600); };

// Acesso (10/11/2026): todos veem que a pagina existe; por enquanto so o master e a gestora da area navegam nela (trava no servidor).
const allowed = () => typeof state === 'undefined' || !state.user || state.user.auditoria !== false;
function locked(msg) {
  root().innerHTML = `<div class="au-locked" id="au-locked"><span class="au-lock">${IC.lock}</span><small>CONTROLES INTERNOS · LOGÍSTICA INTERNACIONAL</small>
    <h1>Auditoria</h1><p>${E(msg || 'Por enquanto esta página está liberada só para o administrador master e a gerência da área.')}</p>
    <p class="au-muted">Ela espelha a planilha de Controles Internos da área (controles, recomendações e solicitações de evidência) e monta o roteiro de evidências de cada solicitação. Se precisar do acesso, fale com o administrador do NexxusDoc.</p></div>`;
}
async function load() {
  S.data = await api('/api/auditoria');
  if (S.open) refreshOpen();
}
async function open() {
  const r = root(); if (!r) return;
  if (!allowed()) { S.data = null; locked(); return; }
  if (!S.data) {
    r.innerHTML = '<div class="au-loading">Carregando a Auditoria…</div>';
    try { await load(); } catch (e) { if (/liberada/.test(e.message)) locked(e.message); else r.innerHTML = `<div class="notice error"><div class="grow">${E(e.message)}</div></div>`; return; }
  }
  render();
  watch();
}
// Roteiros em montagem: confere a cada 4 s e refaz a lista quando terminam.
function watch() {
  clearInterval(S.watch);
  S.watch = setInterval(async () => {
    if (!S.data || root()?.classList.contains('hidden')) return;
    if (!sols().some(s => s.roteiro?.status === 'gerando')) return;
    try { await load(); refreshList(); } catch {}
  }, 4000);
}

function kpis() {
  const c = ctrls(), rc = recs(), sl = sols();
  const fisia = c.filter(x => x.bu === 'Fisia').length, cent = c.filter(x => x.bu === 'Centauro').length;
  const comRec = c.filter(x => x.possui_recomendacao).length;
  const recOk = rc.filter(x => recSit(x).k === 'ok').length;
  const solOk = sl.filter(x => solSit(x).k === 'ok').length, solLate = sl.filter(x => solSit(x).k === 'late').length;
  const solOpen = sl.length - solOk, novas = sl.filter(x => x.novo || x.alterado).length;
  const aprov = c.filter(x => ctrlSit(x).k === 'ok').length;
  const pct = (a, b) => b ? Math.round(a / b * 100) : 0;
  return `<div class="au-kpis" id="au-kpis">
    <div class="au-kpi k1"><small>Controles mapeados</small><strong>${c.length}</strong>
      <span>Fisia ${fisia} · Centauro ${cent}</span><div class="au-bar"><i style="width:100%"></i></div></div>
    <div class="au-kpi k2"><small>Aprovados pelo gerente</small><strong>${aprov}<em>de ${c.length}</em></strong>
      <span>${c.length - aprov ? `${c.length - aprov} sem aprovação e chamado` : 'todos aprovados'}</span>
      <div class="au-bar"><i style="width:${pct(aprov, c.length)}%"></i></div></div>
    <div class="au-kpi k3"><small>Recomendações</small><strong>${rc.length}<em>${comRec} controle${comRec === 1 ? '' : 's'}</em></strong>
      <span>${recOk} concluída${recOk === 1 ? '' : 's'} · ${rc.length - recOk} em aberto</span><div class="au-bar"><i style="width:${pct(recOk, rc.length)}%"></i></div></div>
    <div class="au-kpi k4${solOpen ? ' hot' : ''}"><small>Solicitações em aberto</small><strong>${solOpen}<em>de ${sl.length}</em></strong>
      <span>${solLate ? `${solLate} atrasada${solLate === 1 ? '' : 's'}` : solOpen ? 'dentro do prazo' : 'todas concluídas'}</span><div class="au-bar"><i style="width:${pct(solOk, sl.length)}%"></i></div></div>
    <div class="au-kpi k5${novas ? ' hot' : ''}"><small>Novidades da planilha</small><strong>${novas}</strong>
      <span>${novas ? 'novas ou alteradas em 14 dias' : 'nada novo nos últimos 14 dias'}</span><div class="au-bar"><i style="width:${novas ? 100 : 0}%"></i></div></div>
  </div>`;
}

// Itens da aba atual com os filtros aplicados.
function items() {
  const q = norm(S.busca);
  const list = S.tab === 'controles' ? ctrls() : S.tab === 'recomendacoes' ? recs() : sols();
  return list.filter(x => {
    if (S.bu && x.bu !== S.bu) return false;
    if (S.proc && x.processo !== S.proc) return false;
    if (S.sit) {
      let s;
      if (S.tab === 'controles') s = S.sit === 'rec' ? (x.possui_recomendacao ? 'rec' : '') : ctrlSit(x).k;
      else if (S.tab === 'recomendacoes') s = recSit(x).k;
      else s = S.sit === 'nova' ? (x.novo || x.alterado ? 'nova' : '') : S.sit === 'int' ? (x.fase?.fase === 'Interim' ? 'int' : '')
        : S.sit === 'rf' ? (x.fase?.fase === 'Roll Forward' ? 'rf' : '') : S.sit === 'plan' ? (x.roteiro?.status === 'pronto' ? 'plan' : '') : solSit(x).k;
      if (s !== S.sit) return false;
    }
    if (!q) return true;
    return norm(Object.values(x).filter(v => typeof v === 'string').join(' ')).includes(q);
  });
}

function filters() {
  const procs = [...new Set([...ctrls(), ...recs(), ...sols()].map(x => x.processo).filter(Boolean))].sort();
  const sits = S.tab === 'controles' ? [['ok', 'Aprovados pelo gerente'], ['wait', 'Sem aprovação'], ['rec', 'Com recomendação']]
    : S.tab === 'recomendacoes' ? [['ok', 'Concluídas'], ['wait', 'Em aberto'], ['late', 'Prazo vencido']]
    : [['wait', 'Em aberto'], ['late', 'Atrasadas'], ['ok', 'Concluídas'], ['nova', 'Novas ou alteradas'], ['int', 'Interim'], ['rf', 'Roll Forward'], ['plan', 'Com roteiro pronto']];
  const opt = (v, t, cur) => `<option value="${E(v)}"${v === cur ? ' selected' : ''}>${E(t)}</option>`;
  return `<div class="au-filters" id="au-filters">
    <label class="au-search">${IC.search}<input id="au-q" type="search" placeholder="Buscar por controle, pessoa, texto…" value="${E(S.busca)}"></label>
    <select id="au-bu" class="${S.bu ? 'on' : ''}">${opt('', 'Todas as unidades', S.bu)}${opt('Fisia', 'Fisia', S.bu)}${opt('Centauro', 'Centauro', S.bu)}</select>
    <select id="au-proc" class="${S.proc ? 'on' : ''}">${opt('', 'Todos os processos', S.proc)}${procs.map(p => opt(p, p, S.proc)).join('')}</select>
    <select id="au-sit" class="${S.sit ? 'on' : ''}">${opt('', 'Todas as situações', S.sit)}${sits.map(([v, t]) => opt(v, t, S.sit)).join('')}</select>
    ${S.busca || S.bu || S.proc || S.sit ? '<button type="button" class="au-clear" id="au-clear">Limpar filtros</button>' : ''}
  </div>`;
}

function table() {
  const list = items();
  if (!list.length) return '<div class="au-empty">Nenhum item com esses filtros.</div>';
  if (S.tab === 'controles') return `<table class="au-table"><thead><tr><th>Ref.</th><th>Controle</th><th>Unidade</th><th>Frequência</th><th>Natureza</th>
    <th>Ponto focal</th><th>Recomendação</th><th>Aprovação do gerente</th><th>Chamado</th></tr></thead><tbody>${list.map(c => {
      const nr = recs().filter(r => r.controle === c.ref).length, ns = sols().filter(s => s.controle === c.ref).length;
      return `<tr data-au-open="c:${E(c.ref)}" tabindex="0"><td class="au-ref">${E(c.ref)}</td>
      <td class="au-name"><b>${E(c.nome)}</b><small>${E(c.processo)} · ${E(c.subprocesso)}${ns ? ` · ${ns} solicitaç${ns === 1 ? 'ão' : 'ões'}` : ''}</small></td>
      <td>${bu(c.bu)}</td><td>${V(c.frequencia)}</td><td>${V(c.natureza)}</td><td>${person(c.ponto_focal || c.ponto_focal_backup)}${!c.ponto_focal && c.ponto_focal_backup ? '<small class="au-muted">backup</small>' : ''}</td>
      <td>${c.possui_recomendacao ? `<span class="au-pill rec">${IC.rec}Sim${nr ? ` (${nr})` : ''}</span>` : '<span class="au-muted">Não</span>'}</td>
      <td>${pill(ctrlSit(c))}</td><td class="au-mono">${V(c.chamado)}</td></tr>`; }).join('')}</tbody></table>`;
  if (S.tab === 'recomendacoes') return `<table class="au-table"><thead><tr><th>Rec.</th><th>Recomendação</th><th>Controle</th><th>Unidade</th><th>Classificação</th>
    <th>Responsável</th><th>Apresentada em</th><th>Prazo</th><th>Situação</th></tr></thead><tbody>${list.map(r => `<tr data-au-open="r:${E(r.id)}" tabindex="0">
      <td class="au-ref">${E(r.id.replace('Rec#', ''))}</td><td class="au-name"><b>${E(r.objetivo)}</b><small>${E(r.processo)} · ${E(r.subprocesso)}</small></td>
      <td class="au-mono">${V(r.controle)}</td><td>${bu(r.bu)}</td><td>${V(r.classificacao)}</td><td>${person(r.responsavel)}</td>
      <td>${D(r.data_apresentacao)}</td><td>${D(r.novo_deadline || r.deadline)}</td><td>${pill(recSit(r))}</td></tr>`).join('')}</tbody></table>`;
  return `<table class="au-table"><thead><tr><th>Sol.</th><th>O que foi solicitado</th><th>Controle</th><th>Fase · período</th><th>Responsável</th>
    <th>Solicitada em</th><th>Entrega prevista</th><th>Controles Internos</th><th>Situação da área</th><th>Roteiro</th></tr></thead><tbody>${list.map(s => `<tr data-au-open="s:${E(s.id)}" tabindex="0" class="${s.novo || s.alterado ? 'au-hl' : ''}">
      <td class="au-ref">${E(s.id.replace('Sol#', ''))}${flag(s)}</td><td class="au-name"><span class="au-clamp">${E(s.solicitacao)}</span></td>
      <td class="au-mono">${V(s.controle)}</td><td>${phaseTag(s.fase)}<small class="au-muted">${s.fase?.tipo === 'amostra' ? 'amostra (seleção)' : 'base (população)'}</small></td>
      <td>${person(s.responsavel)}</td><td class="au-mono">${D(s.data_solicitacao)}</td><td class="au-mono">${D(s.data_prevista)}</td>
      <td>${s.status_ci ? `<span class="au-pill ${norm(s.status_ci) === 'aceito' ? 'ok' : 'wait'}">${norm(s.status_ci) === 'aceito' ? IC.check : IC.clock}${E(s.status_ci)}</span>` : '-'}</td>
      <td>${pill(solSit(s))}</td><td>${planChip(s.roteiro) || '<span class="au-muted">-</span>'}</td></tr>`).join('')}</tbody></table>`;
}

/* Aba Ciclo do ano (11/11/2026, pedido do usuario): calendario com navegacao (Ano e Mes, setas e Hoje), mantendo a
   coluna dos controles. Em cada linha: o periodo testado (faixa Interim, Roll Forward ou Remediacao), o pedido da
   auditoria (data da solicitacao) e a entrega prevista; clique abre a solicitacao. */
const phaseCls = f => f?.fase === 'Remediação' ? 'rem' : f?.fase === 'Roll Forward' ? 'rf' : 'int';
const ymd = v => /^\d{4}-\d{2}-\d{2}$/.test(v || '') ? v.split('-').map(Number) : null;
function calEvents(ref, test) {
  const out = [];
  for (const s of sols().filter(x => x.controle === ref)) {
    const a = ymd(s.data_solicitacao), b = ymd(s.data_prevista);
    if (a && test(a)) out.push({k: 'ped', d: a, s, t: `Pedido da auditoria · ${s.id} em ${D(s.data_solicitacao)}`});
    if (b && test(b)) out.push({k: solSit(s).k === 'late' ? 'prz late' : 'prz', d: b, s, t: `Entrega prevista · ${s.id} em ${D(s.data_prevista)}${solSit(s).k === 'ok' ? ' (concluída)' : ''}`});
  }
  return out;
}
const marker = e => `<button type="button" class="au-mk ${e.k}" data-au-open="s:${E(e.s.id)}" title="${E(e.t)}">${e.k.startsWith('ped') ? 'P' : 'E'}<b>${e.d[2]}</b></button>`;
function calendar() {
  const cal = S.cal, c = S.data.ciclo || {};
  const refs = [...new Map(ctrls().map(x => [x.ref, x])).values()];
  const year = cal.ano, label = cal.view === 'ano' ? String(year) : `${MONTHS[cal.mes - 1]} de ${year}`;
  const bar = `<div class="au-cal-bar">
      <div class="au-cal-nav"><button type="button" class="au-icon-btn" data-au-cal="prev" title="Anterior">${IC.left}</button><b>${E(label)}</b>
        <button type="button" class="au-icon-btn" data-au-cal="next" title="Próximo">${IC.right}</button><button type="button" class="au-icon-btn" data-au-cal="hoje">Hoje</button></div>
      <div class="au-seg"><button type="button" data-au-cal="ano" class="${cal.view === 'ano' ? 'on' : ''}">Ano</button><button type="button" data-au-cal="mes" class="${cal.view === 'mes' ? 'on' : ''}">Mês</button></div>
      <div class="au-cal-legend"><span><i class="int"></i>Interim</span><span><i class="rf"></i>Roll Forward</span><span><i class="rem"></i>Remediação</span>
        <span><em class="au-mk ped">P</em>Pedido da auditoria</span><span><em class="au-mk prz">E</em>Entrega prevista</span><span><em class="au-mk prz late">E</em>Atrasada</span></div></div>
    <p class="au-cal-rule">${E(c.regra || '')}</p>`;
  const ctrlCell = ctl => `<td class="au-cal-ctrl"><button type="button" class="au-cal-ref" data-au-open="c:${E(ctl.ref)}"><b>${E(ctl.ref)}</b><small>${E(ctl.nome)}</small></button>${bu(ctl.bu)}</td>`;
  const tested = (ref, y, m) => sols().filter(s => s.controle === ref && s.fase?.ano === y && (s.fase?.meses || []).includes(m));
  let grid, events = [];
  if (cal.view === 'ano') {
    const curM = TODAY.getFullYear() === year ? TODAY.getMonth() + 1 : 0;
    grid = `<table class="au-cal"><thead><tr><th rowspan="2" class="au-cal-ctrl">Controle</th>
        <th colspan="6" class="au-cal-sem int">Interim · desenho e efetividade · jan a jun</th><th colspan="6" class="au-cal-sem rf">Roll Forward · jul a dez</th></tr>
      <tr>${MON.map((m, i) => `<th class="au-cal-m${curM === i + 1 ? ' now' : ''}"><button type="button" data-au-cal-mes="${i + 1}" title="Ver ${MONTHS[i]} de ${year}">${m}</button></th>`).join('')}</tr></thead>
      <tbody>${refs.map(ctl => `<tr>${ctrlCell(ctl)}${MON.map((_, i) => {
        const m = i + 1, here = tested(ctl.ref, year, m);
        const evs = calEvents(ctl.ref, d => d[0] === year && d[1] === m); events.push(...evs);
        const cls = here.length ? `band ${phaseCls(here[0].fase)}` : '';
        const chips = here.filter(s => s.fase.meses[0] === m).map(s => `<button type="button" class="au-cal-chip" data-au-open="s:${E(s.id)}" title="${E(s.fase.fase)} · ${E(s.fase.rotulo)}">${E(s.id)} · ${s.fase.tipo === 'amostra' ? 'amostra' : 'base'}</button>`).join('');
        return `<td class="au-cal-c ${cls}${curM === m ? ' now' : ''}">${chips}${evs.length ? `<div class="au-mks">${evs.map(marker).join('')}</div>` : ''}</td>`;
      }).join('')}</tr>`).join('')}</tbody></table>`;
  } else {
    const days = new Date(year, cal.mes, 0).getDate(), cols = Array.from({length: days}, (_, i) => i + 1);
    const wd = d => new Date(year, cal.mes - 1, d).getDay();
    const isToday = d => TODAY.getFullYear() === year && TODAY.getMonth() + 1 === cal.mes && TODAY.getDate() === d;
    const sem = cal.mes <= 6 ? 'int' : 'rf';
    grid = `<table class="au-cal au-cal-days"><thead><tr><th rowspan="2" class="au-cal-ctrl">Controle</th>
        <th colspan="${days}" class="au-cal-sem ${sem}">${sem === 'int' ? 'Interim · desenho e efetividade' : 'Roll Forward'} · ${MONTHS[cal.mes - 1]}</th></tr>
      <tr>${cols.map(d => `<th class="au-cal-d${[0, 6].includes(wd(d)) ? ' wkd' : ''}${isToday(d) ? ' now' : ''}"><b>${d}</b><small>${WEEK[wd(d)]}</small></th>`).join('')}</tr></thead>
      <tbody>${refs.map(ctl => {
        const here = tested(ctl.ref, year, cal.mes);
        const evs = calEvents(ctl.ref, d => d[0] === year && d[1] === cal.mes); events.push(...evs);
        const band = here.length ? `band ${phaseCls(here[0].fase)}` : '';
        return `<tr>${ctrlCell(ctl)}${cols.map(d => {
          const mine = evs.filter(e => e.d[2] === d);
          return `<td class="au-cal-c ${band}${[0, 6].includes(wd(d)) ? ' wkd' : ''}${isToday(d) ? ' now' : ''}">${d === 1 && here.length ? here.map(s => `<button type="button" class="au-cal-chip" data-au-open="s:${E(s.id)}">${E(s.id)}</button>`).join('') : ''}${mine.map(marker).join('')}</td>`;
        }).join('')}</tr>`;
      }).join('')}</tbody></table>`;
  }
  events.sort((a, b) => (a.d[0] - b.d[0]) || (a.d[1] - b.d[1]) || (a.d[2] - b.d[2]));
  const hints = (c.controles || []).filter(r => r.roll_forward_dica).map(r => `<div class="au-hint">${IC.folder}<b>${E(r.ref)}</b> ${E(r.roll_forward_dica.texto)}: ${folderLink(r.roll_forward_dica.link, r.roll_forward_dica.nome)}</div>`).join('');
  return `<div class="au-cycle">${bar}<div class="au-cal-wrap">${grid}</div>
    <div class="au-cal-list"><h4>${cal.view === 'ano' ? `Eventos de ${year}` : `Eventos de ${MONTHS[cal.mes - 1].toLowerCase()} de ${year}`}</h4>
      ${events.length ? `<ul>${events.map(e => `<li><button type="button" data-au-open="s:${E(e.s.id)}"><span class="au-mono">${String(e.d[2]).padStart(2, '0')}/${String(e.d[1]).padStart(2, '0')}</span><em class="au-mk ${e.k}">${e.k.startsWith('ped') ? 'P' : 'E'}</em>${E(e.k.startsWith('ped') ? 'Pedido da auditoria' : 'Entrega prevista')} · <b>${E(e.s.id)}</b> · ${E(e.s.controle)}${pill(solSit(e.s))}</button></li>`).join('')}</ul>`
        : `<p class="au-muted">Nenhum pedido ou entrega neste período. ${cal.view === 'mes' ? 'Use as setas para navegar ou volte para a visão do ano.' : ''}</p>`}
      ${hints}</div></div>`;
}

/* Aba Matriz de risco (11/11/2026, pedidos do usuario): um risco por controle da planilha; nota = probabilidade x
   impacto (1 a 5) CALCULADA PELO SISTEMA com todas as bases (planilha, base de estudo e roteiros do agente), sem
   classificacao manual. Selecionar um risco (lista ou mapa) acende a celula dele no mapa e mostra cada ponto da nota. */
const RISK_CLS = n => !n ? '' : n >= 16 ? 'crit' : n >= 10 ? 'alto' : n >= 5 ? 'mod' : 'baixo';
const RISK_NAME = {crit: 'Crítico', alto: 'Alto', mod: 'Moderado', baixo: 'Baixo'};
const riskPill = r => r.nota ? `<span class="au-risk ${RISK_CLS(r.nota)}">${r.nota} ${RISK_NAME[RISK_CLS(r.nota)]}</span>` : '<span class="au-risk none">-</span>';
const risks = () => S.data?.riscos || [];
function matrix() {
  const m = S.data.matriz || {}, P = m.probabilidade || [], IM = m.impacto || [], how = m.metodo || {};
  const list = risks().filter(r => !S.mx.bu || r.bu === S.mx.bu)
    .sort((a, b) => (b.nota || 0) - (a.nota || 0) || a.codigo.localeCompare(b.codigo));
  let sel = list.find(r => r.chave === S.mx.sel);
  if (!sel) { sel = list[0]; S.mx.sel = sel?.chave || ''; }
  const heat = [5, 4, 3, 2, 1].map(p => `<div class="au-hm-row"><div class="au-hm-lbl"><b>${p}</b>${E(P[p - 1] || '')}</div>${[1, 2, 3, 4, 5].map(i => {
      const n = p * i, here = list.filter(r => r.p === p && r.i === i), on = sel && sel.p === p && sel.i === i;
      return `<div class="au-hm-cell ${RISK_CLS(n)}${on ? ' sel' : ''}"><span>${n}</span><div>${here.map(r => `<button type="button" class="au-hm-chip${r.chave === S.mx.sel ? ' on' : ''}" data-au-risk="${E(r.chave)}" title="${E(r.codigo)} · ${E(r.evento)}">${E(r.codigo)}</button>`).join('')}</div></div>`;
    }).join('')}</div>`).join('');
  const factors = (arr, total, label) => `<div class="au-mx-calc"><div class="au-mx-calc-head"><b>${label}</b><span class="au-mx-total">${total}</span></div>
    <ul>${(arr || []).map(f => {
      // impacto: a maior consequencia vale o nivel (=5), as outras so aparecem (sem somar) e 2+ naturezas somam +1
      const tag = f.tipo === 'maior' ? `= ${f.pontos}` : f.tipo === 'tambem' ? `${f.pontos}` : f.pontos ? `+${f.pontos}` : '0';
      return `<li class="${f.tipo === 'tambem' || !f.pontos ? 'zero' : ''}"><em>${tag}</em><span>${E(f.motivo)}<small>${E(f.fonte)}</small></span></li>`;
    }).join('')}</ul></div>`;
  return `<div class="au-mx">
    <div class="au-mx-head"><div><h2>Matriz de risco</h2><p>Riscos dos ${ctrls().length} controles da planilha de Auditoria, com a nota calculada pelo sistema</p></div>
      <div class="au-mx-tools"><span class="au-mx-tag">Classificação automática</span>
        <select id="au-mx-bu"><option value="">Todas as unidades</option><option value="Fisia"${S.mx.bu === 'Fisia' ? ' selected' : ''}>Fisia</option><option value="Centauro"${S.mx.bu === 'Centauro' ? ' selected' : ''}>Centauro</option></select></div></div>
    <div class="au-mx-grid">
      <div class="au-mx-box"><div class="au-mx-boxhead"><h3>Mapa de calor</h3><span>Nota = probabilidade × impacto</span></div>
        <div class="au-hm"><div class="au-hm-axis-y">PROBABILIDADE ↑</div>${heat}
          <div class="au-hm-row au-hm-x"><div class="au-hm-lbl"></div>${IM.map((t, k) => `<div><b>${k + 1}</b> ${E(t)}</div>`).join('')}</div>
          <div class="au-hm-axis-x">IMPACTO →</div></div>
        <div class="au-hm-legend"><span><i class="baixo"></i>Baixo 1 a 4</span><span><i class="mod"></i>Moderado 5 a 9</span><span><i class="alto"></i>Alto 10 a 15</span><span><i class="crit"></i>Crítico 16 a 25</span></div></div>
      <div class="au-mx-box"><div class="au-mx-boxhead"><h3>Riscos da planilha</h3><span>${list.length} riscos · maior nota primeiro</span></div>
        <div class="au-mx-tablewrap"><table class="au-mx-table"><thead><tr><th>Risco</th><th>Evento / controle</th><th>P × I</th><th>Classificação</th></tr></thead><tbody>
        ${list.map(r => `<tr class="${r.chave === S.mx.sel ? 'on' : ''}" data-au-risk="${E(r.chave)}" tabindex="0"><td class="au-ref">${E(r.codigo)}<small>${E(r.controle)}</small></td>
          <td><b>${E(r.evento)}</b><small>${E(r.bu)} · ${E(r.tema)}${r.recomendacoes_abertas.length ? ` · ${E(r.recomendacoes_abertas.join(', '))} em aberto` : ''}</small></td>
          <td class="au-mono">${r.p} × ${r.i}</td><td>${riskPill(r)}</td></tr>`).join('')}</tbody></table></div></div></div>
    ${sel ? `<div class="au-mx-sel" id="au-mx-sel">
      <div class="au-mx-box"><div class="au-mx-boxhead"><h3>${E(sel.codigo)} · risco selecionado</h3>${riskPill(sel)}</div>
        <b class="au-mx-ev">${E(sel.evento)}</b><small class="au-muted">Controle ${E(sel.controle)} · ${E(sel.nome_controle)} · ${E(sel.bu)}</small>
        <div class="au-text au-mx-desc">${E(sel.descricao)}</div>
        <button type="button" class="au-link" data-au-open="c:${E(sel.controle)}"><b>${E(sel.controle)}</b><span>Abrir o controle</span></button></div>
      <div class="au-mx-box"><div class="au-mx-boxhead"><h3>Como o sistema chegou na nota</h3><span class="au-mono">${sel.p} × ${sel.i} = <b>${sel.nota}</b></span></div>
        ${factors(sel.fatores_p, `${sel.p} · ${E(P[sel.p - 1] || '')}`, 'Probabilidade')}
        ${factors(sel.fatores_i, `${sel.i} · ${E(IM[sel.i - 1] || '')}`, 'Impacto')}</div>
      <div class="au-mx-box au-mx-how"><h3>Regras do cálculo</h3><p><b>Probabilidade.</b> ${E(how.probabilidade || '')}</p>
        <p><b>Impacto.</b> ${E(how.impacto || '')}</p><p class="au-muted">${E(how.fontes || '')}</p></div></div>` : ''}
    <p class="au-foot">${E(m.regra || '')}</p></div>`;
}
function bindMatrix() {
  document.getElementById('au-mx-bu')?.addEventListener('change', e => { S.mx.bu = e.target.value; S.mx.sel = ''; refreshList(); });
}

function mirror() {
  const m = S.data.espelho || {}, f = S.data.fonte || {};
  const auto = m.automatico_lido_em ? `${m.automatico_ativo ? 'ativo' : 'parado'}, última leitura ${DT(m.automatico_lido_em)}` : 'ainda sem leitura (importe o fluxo no n8n)';
  const cls = f.tipo === 'espelho' && (m.automatico_ativo || f.origem === 'manual') ? 'ok' : 'warn';
  const when = f.tipo === 'espelho' ? `espelho ${f.origem === 'manual' ? 'manual' : 'automático'} de ${DT(f.lido_em)}` : `retrato de ${D(f.lido_em)} (até o primeiro espelho)`;
  return `<div class="au-source ${cls}">${f.tipo === 'espelho' ? IC.check : IC.warn}<div><small>Planilha mestre espelhada</small><b>${E(f.titulo || 'Arquivo Geral')}</b>
      <span>${when} · leitura de hora em hora: ${auto}</span></div>
    ${ext(f.url || S.data.pastas?.planilha?.link, 'Abrir planilha')}
    <button type="button" class="secondary au-sync" id="au-sync"${S.sync ? ' disabled' : ''}>${IC.sync}${S.sync ? 'Lendo a planilha…' : 'Sincronizar agora'}</button></div>`;
}

function render() {
  const r = root(); if (!r || !S.data) return;
  const p = S.data.pastas || {};
  r.innerHTML = `<div class="au-hero" id="au-hero">
      <div><div class="eyebrow">${IC.shield}CONTROLES INTERNOS · LOGÍSTICA INTERNACIONAL</div>
        <h1>Auditoria</h1>
        <p>Espelho da planilha de Controles Internos: controles avaliados pela Auditoria Interna, recomendações e solicitações de evidência, com o roteiro de onde achar cada evidência. Gerência: <b>${E(S.data.gerencia || '-')}</b>.</p>
        <div class="au-links">${folderLink(p.gerencia?.link, 'Pasta da gerência')}${folderLink(p.evidencias_2026?.link, p.evidencias_2026?.nome || 'Evidências 2026')}${ext(p.programacao_importados?.link, 'Programação Importados')}${S.data.ipe?.pdf ? `<a class="au-ext" href="${E(S.data.ipe.pdf)}" target="_blank" rel="noopener" title="${E(S.data.ipe.resumo || '')}">${IC.book}Orientações de IPE</a>` : ''}</div></div>
      ${mirror()}
    </div>
    ${kpis()}
    ${tabs()}
    ${['ciclo', 'matriz'].includes(S.tab) ? '' : filters()}
    <div class="au-panel${['ciclo', 'matriz'].includes(S.tab) ? ' au-panel-free' : ''}" id="au-list">${content()}</div>
    <p class="au-foot">${E((S.data.fonte || {}).observacao || 'A planilha mestre é a fonte; o NexxusDoc só lê. Nada é enviado à auditoria nem ao Connect.')}</p>
    <div class="au-drawer-wrap hidden" id="au-drawer-wrap"><div class="au-drawer" id="au-drawer" role="dialog" aria-modal="true"></div></div>`;
  bind();
  if (S.tab === 'matriz') bindMatrix();
  if (S.open) drawer(S.open, true);
}
const content = () => S.tab === 'ciclo' ? calendar() : S.tab === 'matriz' ? matrix() : table();
function tabs() {
  const openRecs = recs().filter(x => recSit(x).k !== 'ok').length, openSols = sols().filter(x => solSit(x).k !== 'ok').length;
  const critical = risks().filter(x => x.nota >= 16).length;
  const tab = (k, icon, label, n, badge) => `<button type="button" data-au-tab="${k}" class="${S.tab === k ? 'on' : ''}">${icon}${label}${n != null ? `<span class="au-count">${n}</span>` : ''}${badge ? `<span class="au-badge" title="${E(badge.t)}">${badge.n}</span>` : ''}</button>`;
  return `<div class="au-tabs" id="au-tabs" role="tablist">
      ${tab('solicitacoes', IC.inbox, 'Solicitações de evidência', sols().length, openSols ? {n: openSols, t: `${openSols} em aberto`} : null)}
      ${tab('ciclo', IC.cal, 'Ciclo do ano', null)}
      ${tab('controles', IC.shield, 'Controles', ctrls().length)}
      ${tab('recomendacoes', IC.rec, 'Recomendações', recs().length, openRecs ? {n: openRecs, t: `${openRecs} em aberto`} : null)}
      ${tab('matriz', IC.grid, 'Matriz de risco', null, critical ? {n: critical, t: `${critical} risco${critical === 1 ? '' : 's'} crítico${critical === 1 ? '' : 's'}`} : null)}
    </div>`;
}
function bindTabs() {
  root().querySelectorAll('[data-au-tab]').forEach(b => b.addEventListener('click', () => { S.tab = b.dataset.auTab; S.sit = ''; render(); }));
}

function refreshList() {
  const list = document.getElementById('au-list'); if (list) { list.innerHTML = content(); if (S.tab === 'matriz') bindMatrix(); }
  const k = document.getElementById('au-kpis'); if (k) k.outerHTML = kpis();
  const tb = document.getElementById('au-tabs'); if (tb) { tb.outerHTML = tabs(); bindTabs(); }
  const src = document.querySelector('#au-hero .au-source'); if (src) { src.outerHTML = mirror(); bindSync(); }
  const fl = document.getElementById('au-filters');
  if (fl && !['ciclo', 'matriz'].includes(S.tab)) { const pos = document.getElementById('au-q')?.selectionStart; fl.outerHTML = filters(); bindFilters(); const q = document.getElementById('au-q'); if (q && S._typing) { q.focus(); q.setSelectionRange(pos, pos); } }
  if (S.open) refreshOpen();
}
function refreshOpen() {
  const wrap = document.getElementById('au-drawer-wrap');
  if (wrap && !wrap.classList.contains('hidden')) drawer(S.open, true);
}

function bindFilters() {
  const q = document.getElementById('au-q');
  q?.addEventListener('input', () => { S.busca = q.value; S._typing = true; refreshList(); S._typing = false; });
  [['au-bu', 'bu'], ['au-proc', 'proc'], ['au-sit', 'sit']].forEach(([id, k]) => document.getElementById(id)?.addEventListener('change', e => { S[k] = e.target.value; refreshList(); }));
  document.getElementById('au-clear')?.addEventListener('click', () => { S.busca = S.bu = S.proc = S.sit = ''; refreshList(); });
}
function bindSync() {
  document.getElementById('au-sync')?.addEventListener('click', async () => {
    if (S.sync) return;
    S.sync = true; refreshList();
    try {
      const r = await postJson('/api/auditoria/sincronizar', {});
      await load();
      toast(`Planilha lida: ${r.solicitacoes} solicitações e ${r.controles} controles.`);
    } catch (e) { toast(e.message); }
    S.sync = false; refreshList();
  });
}
function bind() {
  const r = root();
  bindTabs(); bindFilters(); bindSync();
  if (r.dataset.auBound) return;  // a raiz nao muda entre redesenhos: liga clique e teclado uma vez so
  r.dataset.auBound = '1';
  r.addEventListener('click', onClick);
  r.addEventListener('keydown', e => {
    if (!(e.key === 'Enter' || e.key === ' ')) return;
    if (e.target.matches('tr[data-au-open]')) { e.preventDefault(); drawer(e.target.dataset.auOpen); }
    else if (e.target.matches('tr[data-au-risk]')) { e.preventDefault(); pickRisk(e.target.dataset.auRisk); }
  });
}
// Selecionar um risco (lista ou mapa): a celula dele acende no mapa e o detalhe do calculo aparece embaixo.
function pickRisk(key) {
  S.mx.sel = key; refreshList();
  const cell = document.querySelector('#page-audit .au-hm-cell.sel');  // se o mapa estiver fora da vista, mostra a celula
  if (cell) { const r = cell.getBoundingClientRect(); if (r.top < 70 || r.bottom > innerHeight) cell.scrollIntoView({block: 'center', behavior: 'smooth'}); }
}
function calNav(action) {
  const c = S.cal;
  if (action === 'ano' || action === 'mes') c.view = action;
  else if (action === 'hoje') { c.ano = TODAY.getFullYear(); c.mes = TODAY.getMonth() + 1; }
  else {
    const step = action === 'next' ? 1 : -1;
    if (c.view === 'ano') c.ano += step;
    else { c.mes += step; if (c.mes > 12) { c.mes = 1; c.ano++; } if (c.mes < 1) { c.mes = 12; c.ano--; } }
  }
  refreshList();
}
function onClick(e) {
  const o = e.target.closest('[data-au-open]');
  if (o) { e.stopPropagation(); drawer(o.dataset.auOpen); return; }
  const cn = e.target.closest('[data-au-cal]');
  if (cn) { calNav(cn.dataset.auCal); return; }
  const cm = e.target.closest('[data-au-cal-mes]');
  if (cm) { S.cal.mes = Number(cm.dataset.auCalMes); S.cal.view = 'mes'; refreshList(); return; }
  const rk = e.target.closest('[data-au-risk]');
  if (rk) { pickRisk(rk.dataset.auRisk); return; }
  const g = e.target.closest('[data-au-plan]');
  if (g) { generate(g.dataset.auPlan, g.dataset.auRefazer === '1'); return; }
  const cp = e.target.closest('[data-au-copy]');
  if (cp) { copyPlan(cp.dataset.auCopy); return; }
  if (e.target.closest('[data-au-close]') || e.target.id === 'au-drawer-wrap') close();
}
document.addEventListener('keydown', e => { if (e.key === 'Escape' && S.open && !document.getElementById('au-drawer-wrap')?.classList.contains('hidden')) close(); });

const sec = (t, body, cls = '') => body ? `<section class="au-sec ${cls}"><h3>${t}</h3>${body}</section>` : '';
const txt = v => (v && String(v).trim()) ? `<div class="au-text">${E(String(v).trim())}</div>` : '';
const facts = rows => `<dl class="au-facts">${rows.filter(Boolean).map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl>`;

async function generate(key, refazer) {
  try {
    await postJson(`/api/auditoria/roteiro/${key}`, {refazer});
    await load(); refreshList();
  } catch (e) { toast(e.message); }
}
async function fetchPlan(key) {
  try { S.plan[key] = await api(`/api/auditoria/roteiro/${key}`); } catch (e) { S.plan[key] = {status: 'erro', erro: e.message}; }
  refreshOpen();
}
function planText(key) {
  const p = S.plan[key]?.roteiro; if (!p) return '';
  const lines = [`ROTEIRO DE EVIDÊNCIAS · ${S.plan[key].solicitacao}`, p.resumo, `Fase: ${p.fase} · ${p.tipo} · ${p.periodo_testado}`, ''];
  for (const it of p.itens) {
    lines.push(`${it.n}) ${it.evidencia}`);
    for (const o of it.onde) lines.push(`   - ${o.fonte}: ${o.local}${o.link ? ' ' + o.link : ''}${o.como ? ' | ' + o.como : ''}`);
    if (it.busca_email) lines.push(`   Busca no Gmail: ${it.busca_email}`);
    if (it.transacao) lines.push(`   SAP: ${it.transacao} ${it.parametros || ''}`.trim());
    if (it.precedente?.nome) lines.push(`   Precedente: ${it.precedente.nome}${it.precedente.link ? ' ' + it.precedente.link : ''}`);
    if (it.criterio) lines.push(`   Conferir: ${it.criterio}`);
    lines.push('');
  }
  if (p.passos?.length) lines.push('PASSOS', ...p.passos.map((x, i) => `${i + 1}. ${x}`), '');
  if (p.pendencias?.length) lines.push('PENDÊNCIAS', ...p.pendencias.map(x => `- ${x}`), '');
  if (p.alertas?.length) lines.push('ALERTAS', ...p.alertas.map(x => `- ${x}`));
  return lines.join('\n');
}
async function copyPlan(key) {
  try { await navigator.clipboard.writeText(planText(key)); toast('Roteiro copiado.'); } catch { toast('Não foi possível copiar.'); }
}

function planHtml(s) {
  const st = s.roteiro || {}, key = st.chave || solKey(s.id), cached = S.plan[key];
  const ipe = S.data?.ipe?.pdf ? `<a class="au-ext" href="${E(S.data.ipe.pdf)}" target="_blank" rel="noopener">${IC.book}Orientações de IPE</a>` : '';
  const head = (label, extra = '') => `<div class="au-plan-head"><span class="au-plan-title">${IC.map}${label}</span>${extra || ipe}</div>`;
  if (st.status === 'gerando') return head('Roteiro de evidências') + `<div class="au-plan-busy"><i></i>O agente está lendo as pastas do Drive e montando o roteiro (cerca de 1 minuto)…</div>`;
  if (st.status === 'sem_roteiro' || st.status === 'erro') {
    return head('Roteiro de evidências') + `<div class="au-plan-empty">${st.status === 'erro' ? `<div class="au-note">${IC.warn}${E(st.erro || 'Falha ao montar o roteiro.')}</div>` : '<p>Ainda sem roteiro para esta solicitação.</p>'}
      <button type="button" class="primary au-gen" data-au-plan="${E(key)}" data-au-refazer="1">${IC.robot}Montar roteiro com o agente</button></div>`;
  }
  if (!cached || cached.chave !== key && cached.status !== 'erro') { fetchPlan(key); return head('Roteiro de evidências') + '<div class="au-plan-busy"><i></i>Carregando o roteiro…</div>'; }
  if (cached.status === 'erro' && !cached.roteiro) return head('Roteiro de evidências') + `<div class="au-note">${IC.warn}${E(cached.erro || '')}</div>`;
  const p = cached.roteiro; if (!p) return head('Roteiro de evidências') + '<div class="au-plan-busy"><i></i>Carregando o roteiro…</div>';
  const diff = {facil: ['ok', 'fácil'], media: ['wait', 'média'], dificil: ['late', 'difícil']};
  const actions = `<div class="au-plan-actions">${st.status === 'desatualizado' ? `<span class="au-plan old">${IC.warn}A solicitação mudou na planilha depois deste roteiro</span>` : ''}
      <button type="button" class="au-icon-btn" data-au-copy="${E(key)}" title="Copiar o roteiro como texto">${IC.copy}Copiar</button>
      <button type="button" class="au-icon-btn" data-au-plan="${E(key)}" data-au-refazer="1" title="Montar de novo com o agente">${IC.sync}Refazer</button></div>`;
  return head('Roteiro de evidências', actions) + `
    <div class="au-plan-meta">${p.fase ? `<span class="au-phase ${PHASE_CLASS[p.fase] || ''}">${E(p.fase)}</span>` : ''}${p.tipo ? `<span class="au-tag">${E(p.tipo)}</span>` : ''}${p.periodo_testado ? `<span class="au-tag">${E(p.periodo_testado)}</span>` : ''}
      ${p.confianca ? `<span class="au-tag">confiança ${E(p.confianca)}</span>` : ''}<span class="au-muted">gerado em ${DT(cached.gerado_em)}${cached.acervo_total ? ` · ${cached.acervo_total} arquivos lidos no Drive` : ''}</span></div>
    ${p.resumo ? `<div class="au-text au-plan-sum">${E(p.resumo)}</div>` : ''}
    <ol class="au-items">${p.itens.map(it => `<li><div class="au-item-head"><b>${E(it.n)}</b><span>${E(it.evidencia)}</span>${it.dificuldade && diff[it.dificuldade] ? `<span class="au-pill ${diff[it.dificuldade][0]}">${E(diff[it.dificuldade][1])}</span>` : ''}</div>
      ${it.onde.length ? `<ul class="au-where">${it.onde.map(o => `<li>${o.fonte === 'Gmail' ? IC.mail : o.fonte === 'SAP' ? IC.sap : IC.folder}<div><b>${E(o.fonte || 'Onde')}</b> ${o.link ? `<a class="au-ext" href="${E(o.link)}" target="_blank" rel="noopener">${E(o.local || 'abrir')}${IC.ext}</a>` : E(o.local)}${o.como ? `<small>${E(o.como)}</small>` : ''}</div></li>`).join('')}</ul>` : ''}
      ${it.busca_email ? `<div class="au-kv">${IC.mail}<b>Busca no Gmail</b><code>${E(it.busca_email)}</code></div>` : ''}
      ${it.transacao ? `<div class="au-kv">${IC.sap}<b>${E(it.transacao)}</b><span>${E(it.parametros || '')}</span></div>` : ''}
      ${it.precedente?.nome ? `<div class="au-kv">${IC.link}<b>Precedente</b><span>${E(it.precedente.nome)} ${ext(it.precedente.link, 'abrir')}</span></div>` : ''}
      ${it.criterio ? `<div class="au-kv crit">${IC.check}<b>Conferir</b><span>${E(it.criterio)}</span></div>` : ''}
      ${it.responsavel ? `<div class="au-kv">${IC.search}<b>Com quem</b><span>${E(it.responsavel)}</span></div>` : ''}</li>`).join('')}</ol>
    ${p.passos?.length ? `<h4>Passo a passo</h4><ol class="au-steps">${p.passos.map(x => `<li>${E(x)}</li>`).join('')}</ol>` : ''}
    ${p.pendencias?.length ? `<h4>Pendências</h4><ul class="au-list warn">${p.pendencias.map(x => `<li>${IC.clock}${E(x)}</li>`).join('')}</ul>` : ''}
    ${p.alertas?.length ? `<h4>Alertas</h4><ul class="au-list late">${p.alertas.map(x => `<li>${IC.warn}${E(x)}</li>`).join('')}</ul>` : ''}`;
}

function drawer(key, silent) {
  const wrap = document.getElementById('au-drawer-wrap'), box = document.getElementById('au-drawer'); if (!wrap || !box) return;
  const [kind, id] = [key.slice(0, 1), key.slice(2)];
  let html = '';
  if (kind === 'c') {
    const c = ctrl(id); if (!c) return;
    const rl = recs().filter(r => r.controle === c.ref), sl = sols().filter(s => s.controle === c.ref);
    html = `<header><div><small>Controle ${E(c.ref)} · ${E(c.processo)}</small><h2>${E(c.nome)}</h2>
        <div class="au-tags">${bu(c.bu)}<span class="au-tag">${V(c.frequencia)}</span><span class="au-tag">${V(c.natureza)}</span>${pill(ctrlSit(c))}${c.chamado ? `<span class="au-tag mono">${IC.ticket}${E(c.chamado)}</span>` : ''}</div></div>
        <button type="button" class="au-x" data-au-close aria-label="Fechar">${IC.x}</button></header>
      <div class="au-body">
        ${c.versoes > 1 ? `<div class="au-note">${IC.warn}Este controle aparece ${c.versoes} vezes na planilha; aqui está a versão mais recente.</div>` : ''}
        ${c.pastas?.length ? sec('Pastas no Drive', `<div class="au-tags">${c.pastas.map(f => folderLink(f.link, f.nome)).join('')}</div>`) : ''}
        ${sec('Risco', txt(c.risco))}${sec('Objetivo do controle', txt(c.objetivo))}
        ${sec('Descrição da atividade de controle', txt(c.descricao))}${sec('Evidências', txt(c.evidencias))}
        ${sec('Responsáveis', facts([['Ponto focal', person(c.ponto_focal)], ['Backup', person(c.ponto_focal_backup)], ['Gerente responsável', person(c.gerente)], ['N2', person(c.n2)], ['N3', person(c.n3)]]))}
        ${sec(`Recomendações da auditoria (${rl.length})`, rl.map(r => `<button type="button" class="au-link" data-au-open="r:${E(r.id)}"><b>${E(r.id)}</b><span>${E(r.objetivo)}</span>${pill(recSit(r))}</button>`).join(''))}
        ${sec(`Solicitações de evidência (${sl.length})`, sl.map(s => `<button type="button" class="au-link" data-au-open="s:${E(s.id)}"><b>${E(s.id)}</b><span>${E(s.solicitacao.split('\n')[0])}</span>${phaseTag(s.fase)}${pill(solSit(s))}</button>`).join(''))}
      </div>`;
  } else if (kind === 'r') {
    const r = recs().find(x => x.id === id); if (!r) return;
    const c = ctrl(r.controle);
    html = `<header><div><small>${E(r.id)} · ${E(r.classificacao || 'Recomendação')}</small><h2>${E(r.objetivo)}</h2>
        <div class="au-tags">${bu(r.bu)}${pill(recSit(r))}${r.links?.pasta ? ext(r.links.pasta, 'Pasta no Drive') : ''}</div></div>
        <button type="button" class="au-x" data-au-close aria-label="Fechar">${IC.x}</button></header>
      <div class="au-body">
        ${sec('Recomendação', txt(r.recomendacao))}${sec('Risco que deu origem', txt(r.risco))}${sec('Situação identificada pela auditoria', txt(r.comentario_origem))}
        ${sec('Plano de ação da área', txt(r.plano_acao) || '<div class="au-muted">Ainda não apresentado.</div>')}
        ${sec('Prazos e responsáveis', facts([['Responsável pelo plano', person(r.responsavel) + (r.email ? `<small class="au-muted">${E(r.email)}</small>` : '')], ['Apresentada em', D(r.data_apresentacao)],
          ['Prazo', D(r.deadline)], r.novo_deadline ? ['Novo prazo', D(r.novo_deadline)] : null, ['Concluída em', D(r.data_conclusao)], r.observacao ? ['Observação', E(r.observacao)] : null,
          r.links?.pasta ? ['Pasta da recomendação', folderLink(r.links.pasta, r.id)] : null,
          ['Gerente responsável', person(r.gerente)], ['N2', person(r.n2)], ['N3', person(r.n3)]]))}
        ${c ? sec('Controle relacionado', `<button type="button" class="au-link" data-au-open="c:${E(c.ref)}"><b>${E(c.ref)}</b><span>${E(c.nome)}</span>${pill(ctrlSit(c))}</button>`) : ''}
      </div>`;
  } else {
    const s = sols().find(x => x.id === id); if (!s) return;
    const c = ctrl(s.controle), l = s.links || {};
    html = `<header><div><small>${E(s.id)} · controle ${E(s.controle)}${s.novo ? ' · nova na planilha' : s.alterado ? ' · alterada na planilha' : ''}</small><h2>${c ? E(c.nome) : 'Solicitação de evidência'}</h2>
        <div class="au-tags">${bu(s.bu)}${phaseTag(s.fase)}<span class="au-tag">${s.fase?.tipo === 'amostra' ? 'amostra (seleção)' : 'base (população)'}</span>${pill(solSit(s))}${l.pasta ? ext(l.pasta, 'Pasta de evidências') : ''}${l.selecao ? ext(l.selecao, 'Seleção da auditoria') : ''}</div></div>
        <button type="button" class="au-x" data-au-close aria-label="Fechar">${IC.x}</button></header>
      <div class="au-body">
        ${s.alterado && s.alterados?.length ? `<div class="au-note">${IC.edit}Alterado na planilha: ${E(s.alterados.join(', '))}.</div>` : ''}
        ${sec('O que foi solicitado', txt(s.solicitacao))}
        <section class="au-sec au-plan-sec">${planHtml(s)}</section>
        ${sec('Andamento', facts([['Período', l.selecao && s.periodo ? `<a class="au-ext" href="${E(l.selecao)}" target="_blank" rel="noopener">${IC.ext}${E(s.periodo)}</a>` : V(s.periodo)],
          ['Solicitada em', D(s.data_solicitacao)], ['Entrega prevista', D(s.data_prevista)], ['Controles Internos', V(s.status_ci)],
          ['Situação da área', V(s.status_area)], ['Pasta de evidências', s.pasta_evidencias || l.pasta ? folderLink(l.pasta, s.pasta_evidencias || 'Abrir a pasta') : '-'],
          c?.pastas?.length ? ['Pasta do controle no Drive', c.pastas.map(f => folderLink(f.link, f.nome)).join(' ')] : null,
          s.notificacao ? ['Notificação', E(s.notificacao)] : null]))}
        ${sec('Observações', txt(s.observacoes))}
        ${sec('Contatos', facts([['Responsável', person(s.responsavel) + (s.email_responsavel ? `<small class="au-muted">${E(s.email_responsavel)}</small>` : '')],
          ['Gestor', person(s.gestor) + (s.email_gestor ? `<small class="au-muted">${E(s.email_gestor)}</small>` : '')], s.email_backup ? ['Backup', `<small class="au-muted">${E(s.email_backup)}</small>`] : null]))}
        ${c ? sec('Controle relacionado', `<button type="button" class="au-link" data-au-open="c:${E(c.ref)}"><b>${E(c.ref)}</b><span>${E(c.nome)}</span>${pill(ctrlSit(c))}</button>`) : ''}
      </div>`;
  }
  const same = S.open === key;
  S.open = key;
  const top = same ? box.scrollTop : 0;
  box.innerHTML = html;
  box.scrollTop = top;
  wrap.classList.remove('hidden');
  requestAnimationFrame(() => wrap.classList.add('show'));
  if (!silent) box.querySelector('.au-x')?.focus({preventScroll: true});
}
function close() {
  const wrap = document.getElementById('au-drawer-wrap'); S.open = null;
  if (!wrap) return;
  wrap.classList.remove('show');
  setTimeout(() => { if (!S.open) wrap.classList.add('hidden'); }, 220);
}

// Usado pelo tour: abre a primeira solicitacao e fecha ao sair.
window.nexusAudit = {open, drawer: k => drawer(k || `s:${sols()[0]?.id || ''}`), close, tab: t => { S.tab = t; S.sit = ''; render(); },
  ready: () => Boolean(S.data) || Boolean(document.getElementById('au-locked')), allowed, reload: () => load().then(refreshList)};
})();
