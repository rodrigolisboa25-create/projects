/* Levantamento das reunioes de entendimento (12/11/2026). Tela so do master dentro de Automacao: seletor
   "Mapa de automacao | Levantamento das reunioes". Dados: GET /api/levantamento (um JSON por reuniao na pasta
   compartilhada); nova ata: POST /api/levantamento/ata (o agente organiza no mesmo formato). */
(() => {
  const PRIO = ['Ganho rápido', 'Estratégico', 'Melhoria pontual', 'Baixa prioridade'];
  const PCLS = {'Ganho rápido': 'p1', 'Estratégico': 'p2', 'Melhoria pontual': 'p3', 'Baixa prioridade': 'p4'};
  const S = {data: null, on: false, tab: 'oport', tema: '', f: {unit: '', prio: '', sit: '', q: ''}, open: new Set(), busy: false, err: ''};
  const E = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const br = d => { const [y, m, dd] = String(d || '').split('-'); return dd ? `${dd}/${m}/${y}` : String(d || ''); };
  const norm = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const toast = msg => { document.querySelector('.lv-toast')?.remove(); const t = document.createElement('div'); t.className = 'lv-toast'; t.textContent = msg; document.body.appendChild(t); setTimeout(() => t.remove(), 4200); };
  // Subpagina so do master (18/11/2026, pedido do usuario); o servidor tambem recusa os demais.
  const logged = () => typeof state !== 'undefined' && state.user?.role === 'master';
  const canEdit = () => !!S.data?.pode_editar;
  const I = {
    meet: '<path d="M4 6h16v10H8l-4 4z"/><path d="M8 10h8M8 13h5"/>',
    people: '<circle cx="9" cy="8" r="3"/><path d="M3 19c0-3 3-5 6-5s6 2 6 5"/><circle cx="17" cy="9" r="2.4"/><path d="M15.5 14.2c2.6.2 5 1.8 5 4.8"/>',
    bolt: '<path d="M13 3 5 14h6l-1 7 8-11h-6z"/>',
    star: '<path d="m12 3 2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.6 6.6 19.5l1.2-6L3.3 9.3l6.1-.7z"/>',
    wait: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    up: '<path d="M12 16V5m0 0-4 4m4-4 4 4M5 19h14"/>',
    down: '<path d="m6 9 6 6 6-6"/>',
    trash: '<path d="M5 7h14M10 7V5h4v2M7 7l1 12h8l1-12"/>',
    doc: '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M9.5 12h5M9.5 15.5h5"/>'
  };
  const ico = (k, cls = '') => `<svg class="lv-i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${I[k]}</svg>`;

  const opps = () => (S.data?.reunioes || []).flatMap(m => (m.oportunidades || []).map(o => ({...o, _m: m})));
  const meetingOf = id => (S.data?.reunioes || []).find(m => m.id === id);
  const oppById = id => opps().find(o => o.id === id);
  const waiting = o => /aguard|depende|avaliar junto|acompanhar|em andamento/i.test(o.situacao || '');

  function passes(o) {
    const f = S.f;
    if (f.unit && !(o.unidades || []).includes(f.unit)) return false;
    if (f.prio && o.prioridade !== f.prio) return false;
    if (f.sit === 'agir' && waiting(o)) return false;
    if (f.sit === 'espera' && !waiting(o)) return false;
    if (f.q) {
      const hay = norm([o.titulo, o.processo, o.hoje, o.dor, o.proposta, (o.dados_e_sistemas || []).join(' '), (o.citado_por || []).join(' ')].join(' '));
      if (!norm(f.q).split(/\s+/).filter(Boolean).every(w => hay.includes(w))) return false;
    }
    return true;
  }

  function unitTags(units) { return (units || []).map(u => `<span class="lv-u ${u === 'Fisia' ? 'fi' : 'ce'}">${E(u)}</span>`).join(''); }

  function tilesHtml() {
    const ms = S.data.reunioes || [], os = opps();
    const people = new Set(ms.flatMap(m => (m.participantes || []).map(p => p.nome)));
    const t = [['meet', 'Reuniões', ms.length, ms.length ? `${br(ms[0].data)} a ${br(ms[ms.length - 1].data)}` : '-'],
      ['people', 'Pessoas ouvidas', people.size, 'Fisia e Centauro'],
      ['bolt', 'Oportunidades', os.length, `${os.filter(o => (o.unidades || []).includes('Fisia')).length} Fisia · ${os.filter(o => (o.unidades || []).includes('Centauro')).length} Centauro`],
      ['star', 'Ganhos rápidos', os.filter(o => o.prioridade === 'Ganho rápido').length, 'impacto alto, esforço baixo ou médio'],
      ['wait', 'Dependem de terceiros', os.filter(waiting).length, 'PGL, Tec, DATI ou fechamento']];
    return `<div class="lv-tiles">${t.map(([i, k, v, h]) => `<div class="lv-tile">${ico(i)}<div><small>${k}</small><strong>${v}</strong><em>${E(h)}</em></div></div>`).join('')}</div>`;
  }

  function filtersHtml() {
    const f = S.f, sel = (id, label, opts, cur) => `<select id="${id}" class="${cur ? 'on' : ''}" aria-label="${label}"><option value="">${label}: todas</option>${opts.map(([v, t]) => `<option value="${E(v)}"${v === cur ? ' selected' : ''}>${E(t)}</option>`).join('')}</select>`;
    return `<div class="lv-filters"><input id="lv-q" type="search" placeholder="Buscar por processo, sistema, pessoa…" value="${E(f.q)}" aria-label="Buscar">
      ${sel('lv-unit', 'Unidade', [['Fisia', 'Fisia'], ['Centauro', 'Centauro']], f.unit)}
      ${S.tab === 'oport' ? sel('lv-prio', 'Prioridade', PRIO.map(p => [p, p]), f.prio) + sel('lv-sit', 'Situação', [['agir', 'Podemos começar'], ['espera', 'Dependem de terceiros']], f.sit) : ''}</div>`;
  }

  function field(label, body) { return body ? `<div class="lv-f"><b>${label}</b><div>${body}</div></div>` : ''; }

  function oppCard(o) {
    const open = S.open.has(o.id), m = o._m;
    const links = (o.tambem_em || []).map(id => { const x = oppById(id) || meetingOf(id); return x ? `<span class="lv-chip">${E(x.titulo)}${x._m ? ` · ${br(x._m.data)}` : x.data ? ` · ${br(x.data)}` : ''}</span>` : ''; }).join('');
    return `<article class="lv-op${open ? ' open' : ''}">
      <button type="button" class="lv-op-h" data-lv-op="${E(o.id)}" aria-expanded="${open}">
        <span class="lv-pr ${PCLS[o.prioridade] || 'p3'}">${E(o.prioridade)}</span>
        <span class="lv-op-t"><b>${E(o.titulo)}</b><small>${E(o.processo || '')}</small></span>
        <span class="lv-op-m">${unitTags(o.unidades)}<span class="lv-lv">Impacto <b>${E(o.impacto)}</b></span><span class="lv-lv">Esforço <b>${E(o.complexidade)}</b></span><span class="lv-sit${waiting(o) ? ' w' : ''}">${E(o.situacao)}</span></span>
        ${ico('down', 'lv-chev')}</button>
      ${open ? `<div class="lv-op-b">
        <div class="lv-grid">
          ${field('Como é hoje', E(o.hoje))}${field('O que dói', E(o.dor))}
          ${field('Proposta', E(o.proposta))}${field('Ganho esperado', E(o.ganho))}
        </div>
        <div class="lv-grid lv-grid3">
          ${field('Dados e sistemas', (o.dados_e_sistemas || []).map(d => `<span class="lv-chip">${E(d)}</span>`).join(''))}
          ${field('Próximo passo', E(o.proximo_passo))}
          ${field('Origem', `Reunião de ${br(m.data)} · ${E(m.titulo)}<br><span class="lv-mut">${E((o.citado_por || []).join(', '))}</span>`)}
        </div>
        ${links ? field('Também citado em', links) : ''}
      </div>` : ''}</article>`;
  }

  function oppsHtml() {
    const list = opps().filter(passes);
    if (!list.length) return '<p class="lv-empty">Nenhuma oportunidade com esses filtros.</p>';
    return PRIO.map(p => {
      const items = list.filter(o => o.prioridade === p);
      return items.length ? `<section class="lv-grp"><h4><span class="lv-pr ${PCLS[p]}">${p}</span><small>${items.length} ${items.length === 1 ? 'oportunidade' : 'oportunidades'}</small></h4>${items.map(oppCard).join('')}</section>` : '';
    }).join('');
  }

  function pointsHtml() {
    const f = S.f, words = norm(f.q).split(/\s+/).filter(Boolean);
    const all = (S.data.reunioes || []).flatMap(m => (m.pontos || []).map(p => ({...p, _m: m, _src: p})))
      .filter(p => (!f.unit || (p._m.unidades || []).includes(f.unit)) && (!words.length || words.every(w => norm(p.texto + ' ' + p.tema).includes(w))));
    if (!all.length) return '<p class="lv-empty">Nenhum ponto com esses filtros.</p>';
    // Temas numa coluna (com a contagem); a direita, so os pontos do tema escolhido, cada um em 2 linhas (clique abre).
    const temas = [...new Set(all.map(p => p.tema))].sort((a, b) => all.filter(p => p.tema === b).length - all.filter(p => p.tema === a).length || a.localeCompare(b));
    if (!temas.includes(S.tema)) S.tema = temas[0];
    const ps = all.filter(p => p.tema === S.tema);
    const units = [...new Set(ps.flatMap(p => p._m.unidades || []))];
    const dates = [...new Set(ps.map(p => br(p._m.data).slice(0, 5)))];
    return `<div class="lv-pt">
      <nav class="lv-pt-nav" aria-label="Temas">${temas.map(t => { const n = all.filter(p => p.tema === t).length; return `<button type="button" data-lv-tema="${E(t)}" class="${t === S.tema ? 'on' : ''}" aria-current="${t === S.tema}"><span>${E(t)}</span><b>${n}</b></button>`; }).join('')}</nav>
      <section class="lv-pt-main">
        <header><h4>${E(S.tema)}</h4><span>${ps.length} ${ps.length === 1 ? 'ponto' : 'pontos'} · reuniões de ${dates.join(', ')}${unitTags(units)}</span></header>
        <ol class="lv-pt-list">${ps.map(p => { const k = `p:${p._m.id}:${(p._m.pontos || []).indexOf(p._src)}`, open = S.open.has(k); return `<li class="${open ? 'open' : ''}"><button type="button" data-lv-pt="${E(k)}" aria-expanded="${open}"><p>${E(p.texto)}</p><span class="lv-src">${br(p._m.data)} · ${E((p._m.participantes || []).map(x => x.nome).join(', '))}${unitTags(p._m.unidades)}<em>${open ? 'Ver menos' : 'Ver tudo'}</em></span></button></li>`; }).join('')}</ol>
      </section></div>`;
  }

  function list(title, items) { return items?.length ? `<div class="lv-f"><b>${title}</b><ul class="lv-ul">${items.map(i => `<li>${E(i)}</li>`).join('')}</ul></div>` : ''; }

  function meetingsHtml() {
    const f = S.f, ms = (S.data.reunioes || []).filter(m => !f.unit || (m.unidades || []).includes(f.unit)).slice().reverse();
    if (!ms.length) return '<p class="lv-empty">Nenhuma reunião com esses filtros.</p>';
    return ms.map(m => {
      const open = S.open.has(m.id);
      return `<article class="lv-meet${open ? ' open' : ''}">
        <button type="button" class="lv-meet-h" data-lv-meet="${E(m.id)}" aria-expanded="${open}">
          <span class="lv-date"><b>${br(m.data).slice(0, 5)}</b><small>${String(m.data).slice(0, 4)}</small></span>
          <span class="lv-op-t"><b>${E(m.titulo)}</b><small>${E((m.participantes || []).map(p => `${p.nome} (${p.papel})`).join(' · '))}</small></span>
          <span class="lv-op-m">${unitTags(m.unidades)}<span class="lv-lv"><b>${(m.pontos || []).length}</b> ${(m.pontos || []).length === 1 ? 'ponto' : 'pontos'}</span><span class="lv-lv"><b>${(m.oportunidades || []).length}</b> ${(m.oportunidades || []).length === 1 ? 'oportunidade' : 'oportunidades'}</span>${m.origem === 'agente' ? '<span class="lv-sit">lida pelo agente</span>' : ''}</span>
          ${ico('down', 'lv-chev')}</button>
        ${open ? `<div class="lv-op-b">
          <p class="lv-res">${E(m.resumo)}</p>
          <div class="lv-f"><b>Principais pontos</b><ul class="lv-ul">${(m.pontos || []).map(p => `<li><span class="lv-tg">${E(p.tema)}</span>${E(p.texto)}</li>`).join('')}</ul></div>
          <div class="lv-grid lv-grid3">${list('Dores', m.dores)}${list('Decisões', m.decisoes)}${list('Próximos passos', m.proximos_passos)}</div>
          ${(m.oportunidades || []).length ? `<div class="lv-f"><b>Oportunidades desta reunião</b><div>${m.oportunidades.map(o => `<span class="lv-chip"><span class="lv-dot ${PCLS[o.prioridade] || 'p3'}"></span>${E(o.titulo)}</span>`).join('')}</div></div>` : ''}
          <div class="lv-foot"><span class="lv-mut">${E(m.fonte || '')}${m.adicionado_por ? ' · incluída por ' + E(m.adicionado_por) : ''}</span>${m.origem === 'agente' && canEdit() ? `<button type="button" class="lv-del" data-lv-del="${E(m.id)}">${ico('trash')}Excluir esta reunião</button>` : ''}</div>
        </div>` : ''}</article>`;
    }).join('');
  }

  function bodyHtml() {
    if (S.err) return `<p class="lv-empty">${E(S.err)}</p>`;
    if (!S.data) return '<p class="lv-empty">Carregando o levantamento…</p>';
    const tabs = [['oport', 'Oportunidades de automação', opps().length], ['pontos', 'Principais pontos', (S.data.reunioes || []).reduce((n, m) => n + (m.pontos || []).length, 0)], ['reunioes', 'Reuniões', (S.data.reunioes || []).length]];
    return `${tilesHtml()}
      <nav class="lv-tabs" role="tablist">${tabs.map(([k, t, n]) => `<button type="button" role="tab" aria-selected="${S.tab === k}" class="${S.tab === k ? 'on' : ''}" data-lv-tab="${k}">${t}<span>${n}</span></button>`).join('')}</nav>
      ${filtersHtml()}
      <div class="lv-body">${S.tab === 'oport' ? oppsHtml() : S.tab === 'pontos' ? pointsHtml() : meetingsHtml()}</div>`;
  }

  function render(keepFocus) {
    const root = document.getElementById('lv-root');
    if (!root) return;
    const act = document.activeElement, id = keepFocus && act?.id, pos = id && act.selectionStart;
    root.innerHTML = `<div class="lv-head"><div><h2>Levantamento das reuniões de entendimento</h2>
        <p>O que a equipe da Logística Internacional contou nas reuniões: rotinas, dores e oportunidades de automação. O agente do NexxusDoc usa como contexto.</p></div>
        ${canEdit() ? `<div class="lv-add"><label class="lv-btn${S.busy ? ' busy' : ''}">${ico('up')}<span>${S.busy ? 'Lendo a ata…' : 'Adicionar ata'}</span><input id="lv-file" type="file" accept=".docx,.pdf,.txt,.md" ${S.busy ? 'disabled' : ''} hidden></label><small>Anotações do Gemini (.docx, .pdf ou .txt). O agente organiza no mesmo formato.</small></div>` : ''}</div>
      ${S.busy ? `<div class="lv-prog"><div class="lv-bar"><i style="width:${S.pct || 3}%"></i></div><span>${Math.round(S.pct || 3)}%</span></div>` : ''}
      ${bodyHtml()}`;
    if (id) { const el = document.getElementById(id); if (el) { el.focus(); try { el.setSelectionRange(pos, pos); } catch {} } }
    // ponto que cabe em 2 linhas nao precisa de "Ver tudo"
    root.querySelectorAll('.lv-pt-list li:not(.open) p').forEach(p => { if (p.scrollHeight <= p.clientHeight + 2) p.closest('li').classList.add('short'); });
  }

  async function load() {
    S.err = '';
    try { S.data = await api('/api/levantamento'); } catch (e) { S.err = e.message; }
    render();
  }

  async function addFile(file) {
    if (!file || S.busy) return;
    S.busy = true; S.pct = 3; render();
    const t0 = Date.now(), timer = setInterval(() => { S.pct = Math.min(95, 95 * (1 - Math.exp(-(Date.now() - t0) / 40000))); const b = document.querySelector('#lv-root .lv-bar i'), s = document.querySelector('#lv-root .lv-prog span'); if (b) b.style.width = S.pct + '%'; if (s) s.textContent = Math.round(S.pct) + '%'; }, 400);
    try {
      const fd = new FormData(); fd.append('file', file);
      const m = await api('/api/levantamento/ata', {method: 'POST', body: fd});
      toast(`Ata incluída: ${m.titulo} (${(m.pontos || []).length} pontos, ${(m.oportunidades || []).length} oportunidades).`);
      S.tab = 'reunioes'; S.open.add(m.id);
      await load();
    } catch (e) { toast(e.message); }
    finally { clearInterval(timer); S.busy = false; render(); }
  }

  function setMode(on) {
    const page = document.getElementById('page-automation');
    if (!page) return;
    S.on = on && logged();
    page.classList.toggle('lv-on', S.on);
    document.querySelectorAll('#lv-switch button').forEach(b => b.setAttribute('aria-pressed', String((b.dataset.lvMode === 'lev') === S.on)));
    if (S.on && !S.data) load(); else if (S.on) render();
  }

  function mount() {
    const page = document.getElementById('page-automation');
    if (!page) return;
    const sw = document.getElementById('lv-switch');
    if (!logged()) { sw?.remove(); page.classList.remove('lv-on'); document.getElementById('lv-root')?.remove(); return; }
    if (!sw) {
      const head = page.querySelector('.pagehead');
      head.insertAdjacentHTML('afterend', `<div id="lv-switch" class="lv-switch" role="group" aria-label="Visão"><button type="button" data-lv-mode="mapa" aria-pressed="true">Mapa de automação</button><button type="button" data-lv-mode="lev" aria-pressed="false">${ico('meet')}Levantamento das reuniões</button></div><div id="lv-root"></div>`);
    }
    setMode(S.on);
  }

  document.addEventListener('click', e => {
    const b = e.target.closest('#lv-switch button,[data-lv-tab],[data-lv-op],[data-lv-meet],[data-lv-del],[data-lv-tema],[data-lv-pt]');
    if (!b) return;
    if (b.dataset.lvMode) { setMode(b.dataset.lvMode === 'lev'); return; }
    if (b.dataset.lvTema) { S.tema = b.dataset.lvTema; render(); return; }
    if (b.dataset.lvPt) { const k = b.dataset.lvPt; S.open.has(k) ? S.open.delete(k) : S.open.add(k); render(); return; }
    if (b.dataset.lvTab) { S.tab = b.dataset.lvTab; render(); return; }
    const k = b.dataset.lvOp || b.dataset.lvMeet;
    if (k) { S.open.has(k) ? S.open.delete(k) : S.open.add(k); render(); return; }
    if (b.dataset.lvDel) {
      const m = meetingOf(b.dataset.lvDel);
      if (!m || !confirm(`Excluir a reunião "${m.titulo}" (${br(m.data)}) do levantamento? Ela sai também do conhecimento do agente.`)) return;
      api(`/api/levantamento/${encodeURIComponent(m.id)}`, {method: 'DELETE'}).then(() => { toast('Reunião excluída do levantamento.'); load(); }).catch(err => toast(err.message));
    }
  });
  document.addEventListener('change', e => {
    const id = e.target.id;
    if (id === 'lv-file') { addFile(e.target.files[0]); e.target.value = ''; return; }
    const map = {'lv-unit': 'unit', 'lv-prio': 'prio', 'lv-sit': 'sit'};
    if (map[id]) { S.f[map[id]] = e.target.value; render(); }
  });
  document.addEventListener('input', e => { if (e.target.id === 'lv-q') { S.f.q = e.target.value; render(true); } });

  window.nexusLev = {mount, show: () => setMode(true), hide: () => setMode(false), reload: load, _estado: () => S};
})();
