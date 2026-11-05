/* NexxusDoc · Fluxo de importação: Fisia × Centauro (REF. DOCS).
 * Monta os slides com os dados de /api/refdocs (fluxos da apresentação da área, slides 10 e 15) e depois carrega o
 * motor do html-ppt-skill (runtime.js + fx-runtime.js). Clicar num processo devolve o id ao universo (postMessage). */
(async function(){
  'use strict';
  const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>Array.from(r.querySelectorAll(s));
  const esc=t=>String(t??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const deck=$('#deck');
  const send=msg=>{try{if(window.parent!==window)window.parent.postMessage(msg,location.origin)}catch(e){}};
  const Q=window.FLOW_REV?'?v='+window.FLOW_REV:'';  // mesma versão dos arquivos da página (já baixados na abertura do sistema)

  // Dados: aberta pelo REF. DOCS, vêm prontos da tela do universo (mensagem nexxus-flow-data, logo depois do aviso de
  // pronta); sem eles em 1,5 s, ou recarregada depois de "Editar dados", busca /api/refdocs. Na prévia autocontida vêm
  // embutidos na página. Tudo isso acontece enquanto a pessoa escolhe o idioma.
  const viaTela=new URLSearchParams(location.search).get('escolha')==='tela'&&window.parent!==window;
  let restarting=false;try{restarting=!!sessionStorage.getItem('nexus.flow.restart')}catch(e){}
  const fromParent=viaTela&&!restarting?new Promise(res=>{const tm=setTimeout(()=>res(null),1500);
    addEventListener('message',function onData(e){const m=e.data||{};
      if(e.origin!==location.origin||e.source!==window.parent||m.type!=='nexxus-flow-data')return;
      removeEventListener('message',onData);clearTimeout(tm);res(m.data&&m.data.flows?m.data:null)})}):Promise.resolve(null);
  const loaded=(async()=>{
    let data=window.__NEXXUS_DATA||await fromParent,map=window.__NEXXUS_MAP;
    if(!data){const r=await fetch('/api/refdocs',{credentials:'same-origin'});if(!r.ok)throw new Error('HTTP '+r.status);data=await r.json()}
    if(!map){const r=await fetch('mapa_mundo.json'+Q);map=r.ok?await r.json():null}
    return [data,map]})();
  loaded.catch(()=>{});

  /* ---------- idioma (português, inglês, espanhol): escolhido antes de a apresentação começar ---------- */
  const I18N=window.FLOW_I18N||{langs:['pt'],ui:{pt:{}},data:{}};
  let LANG='pt';
  const t=(k,v={})=>{const s=(I18N.ui[LANG]||{})[k]??(I18N.ui.pt||{})[k]??k;return typeof s==='function'?s(v):String(s).replace(/\{(\w+)\}/g,(m,x)=>v[x]??'')};
  // textos dos dados do fluxo (em português na base): tradução pela frase exata; o que não estiver no dicionário fica em português
  const d=x=>{if(LANG==='pt'||x==null||x==='')return x;const s=String(x).trim(),tab=I18N.data[LANG]||{};if(tab[s]!=null)return tab[s];
    const m=/^(\d+) dias$/.exec(s);return m?t('days',{n:Number(m[1])}):x};
  const dias=n=>t('days',{n:Number(n)||0});
  LANG=await new Promise(done=>{
    const ok=l=>I18N.langs.includes(l);
    let saved='pt',again='';
    try{saved=localStorage.getItem('nexus.flow.lang')||'pt'}catch(e){}
    try{again=sessionStorage.getItem('nexus.flow.restart')||'';sessionStorage.removeItem('nexus.flow.restart')}catch(e){}
    if(ok(again)){done(again);return}  // recarregada depois de "Editar dados": segue no mesmo idioma, sem perguntar de novo
    // Aberta pelo REF. DOCS: o idioma é escolhido na tela do universo (aparece já no clique) enquanto esta página carrega;
    // aqui só avisa que está pronta e espera a escolha. Aberta sozinha (ex.: prévia), mostra a própria tela de escolha.
    if(viaTela){
      $('#loading').hidden=true;
      addEventListener('message',function onStart(e){const m=e.data||{};
        if(e.origin!==location.origin||e.source!==window.parent||m.type!=='nexxus-flow-start'||!ok(m.lang))return;
        removeEventListener('message',onStart);done(m.lang)});
      send({type:'nexxus-flow-ready'});return}
    let cur=ok(saved)?saved:'pt';
    const T=k=>(I18N.ui[cur]||{})[k]??(I18N.ui.pt||{})[k]??k;
    const box=document.createElement('div');box.className='lang-pick';box.setAttribute('role','dialog');
    const render=()=>{document.documentElement.lang=T('locale');
      box.setAttribute('aria-label',T('pickTitle'));
      box.innerHTML=`<div class="lp-card">
        <svg class="lp-globe" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3.2 3.6 3.2 14.4 0 18M12 3c-3.2 3.6-3.2 14.4 0 18"/></svg>
        <div class="lp-kicker">${esc(T('pickKicker'))}</div><h1>${esc(T('pickTitle'))}</h1>
        <div class="lp-opts" role="radiogroup">${I18N.langs.map(l=>`<button type="button" role="radio" aria-checked="${l===cur}" class="lp-opt${l===cur?' on':''}" data-lang="${l}">
          <b class="lp-code">${l.toUpperCase()}</b><svg class="flag" viewBox="0 0 30 20" aria-hidden="true">${(I18N.flags||{})[l]||''}</svg><span><strong>${esc(I18N.ui[l].langName)}</strong><small>${esc(I18N.ui[l].langSub)}</small></span>
          <i class="lp-check"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg></i></button>`).join('')}</div>
        <p class="lp-lede">${esc(T('pickLede'))}</p>
        <div class="lp-actions"><button type="button" class="lp-back">${esc(T('pickBack'))}</button>
          <button type="button" class="lp-start">${esc(T('pickStart'))}<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button></div></div>`;
      box.querySelector('.lp-opt.on')?.focus()};
    const finish=()=>{removeEventListener('keydown',onKey,true);box.remove();
      try{localStorage.setItem('nexus.flow.lang',cur)}catch(e){}
      send({type:'nexxus-flow-lang',lang:cur});done(cur)};
    const move=k=>{const i=I18N.langs.indexOf(cur);cur=I18N.langs[(i+k+I18N.langs.length)%I18N.langs.length];render()};
    function onKey(e){
      if(e.key==='Escape'){e.preventDefault();send({type:'nexxus-flow-close'});return}
      if(['ArrowDown','ArrowRight'].includes(e.key)){e.preventDefault();move(1)}
      else if(['ArrowUp','ArrowLeft'].includes(e.key)){e.preventDefault();move(-1)}
      else if(/^[1-9]$/.test(e.key)&&I18N.langs[Number(e.key)-1]){cur=I18N.langs[Number(e.key)-1];render()}
      else if(e.key==='Enter'&&!e.target.closest?.('.lp-back')){e.preventDefault();finish()}}
    box.addEventListener('click',e=>{const o=e.target.closest('[data-lang]');if(o){cur=o.dataset.lang;render();return}
      if(e.target.closest('.lp-start'))finish();else if(e.target.closest('.lp-back'))send({type:'nexxus-flow-close'})});
    box.addEventListener('dblclick',e=>{if(e.target.closest('[data-lang]'))finish()});
    addEventListener('keydown',onKey,true);
    $('#loading').hidden=true;document.body.appendChild(box);render();
  });
  document.documentElement.lang=t('locale');document.title=t('docTitle');
  $('#loading').hidden=false;$('#loading').textContent=t('loading');

  const UNIT={Fisia:{c:'#ff8a3d'},Centauro:{c:'#e5484d'}};
  const PHASE=Object.fromEntries(Object.entries({sourcing:'#4cc9f0',pre:'#4cc9f0',embarque:'#7c9cff',navegacao:'#5b8cff',
    chegada:'#2ee6a6',desembaraco:'#b5dc3c',entrega:'#f4b740',pos:'#a9bdb7'}).map(([k,c])=>[k,[t('ph.'+k),c]]));
  const ST={nexxusdoc:['#c8ff4d',t('st.nexxusdoc')],manual:['#35e3c4',t('st.manual')],sem:['#7f97a0',t('st.sem')]};
  const ICON={
    pedido:'<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M9.5 11h6M9.5 14.5h6M9.5 18h4"/>',
    fabrica:'<path d="M3 21V10l5 3v-3l5 3v-3l5 3V4h3v17z"/><path d="M7 17h2M12 17h2M17 17h2"/>',
    consolidador:'<path d="M3 10 12 4l9 6v11H3z"/><path d="M7 21v-6h10v6M12 8v5m-2.2-2.2L12 13l2.2-2.2"/>',
    armazem:'<path d="M3 10 12 4l9 6v11H3z"/><rect x="8" y="13" width="8" height="8"/><path d="M8 16.5h8"/>',
    navio:'<path d="M3 14h18l-2.6 5H5.6z"/><path d="M6 14V9h12v5M9.5 9V5.5h5V9"/><path d="M2 22c1.7 0 1.7-1 3.4-1s1.7 1 3.4 1 1.7-1 3.4-1 1.7 1 3.4 1 1.7-1 3.4-1"/>',
    oceano:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3.2 3.6 3.2 14.4 0 18M12 3c-3.2 3.6-3.2 14.4 0 18"/>',
    porto:'<path d="M6 21V4h2l12 4H8M8 8v13M3 21h18M17 8v4"/><rect x="14.5" y="12" width="5" height="3.2"/>',
    aduana:'<path d="M12 3 4 6v6c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V6z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    sefaz:'<path d="M3 9 12 4l9 5M4 9h16M6 9v9M10 9v9M14 9v9M18 9v9M3 20h18"/>',
    caminhao:'<path d="M2 6h11v10H2zM13 9h4l3 3.5V16h-7"/><circle cx="6" cy="18" r="2"/><circle cx="16.5" cy="18" r="2"/>',
    cd:'<path d="M2 21V9l10-5 10 5v12"/><path d="M6 21v-8h12v8M6 17h12"/>',
    sap:'<ellipse cx="12" cy="5.5" rx="7" ry="2.5"/><path d="M5 5.5v6c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-6M5 11.5v6c0 1.4 3.1 2.5 7 2.5"/><path d="m15 18 2 2 4-4"/>',
    loja:'<path d="M4 10v11h16V10M3 10l2-6h14l2 6z"/><path d="M9 21v-6h6v6"/>',
    inspecao:'<path d="M9 4h6v3H9zM15 5.5h3V20H6V5.5h3"/><circle cx="12" cy="13" r="3"/><path d="m14.2 15.2 2.3 2.3"/>',
    carga:'<path d="M3 7.5 12 3l9 4.5v9L12 21l-9-4.5z"/><path d="M3 7.5 12 12l9-4.5M12 12v9"/>',
    conteiner:'<rect x="2" y="6" width="20" height="12" rx="1"/><path d="M6 6v12M10 6v12M14 6v12M18 6v12"/>'};
  const ic=(k,cls='ic')=>`<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICON[k]||ICON.carga}</svg>`;
  let DATA,MAP;
  try{[DATA,MAP]=await loaded}catch(e){$('#loading').textContent=t('loadError',{e:e.message});return}

  /* ---------- mapa do planeta (Natural Earth I, meridiano central 30° L; igual a tools/mapa_converter) ---------- */
  const PJ=MAP?.proj||{lon0:30,k:420,cx:1300,cy:640};
  const proj=(lon,lat)=>{const lam=((lon-PJ.lon0+540)%360-180)*Math.PI/180,phi=lat*Math.PI/180,p2=phi*phi,p4=p2*p2;
    return [PJ.cx+lam*(0.8707-0.131979*p2+p4*(-0.013791+p4*(0.003971*p2-0.001529*p4)))*PJ.k,
            PJ.cy-phi*(1.007226+p2*(0.015085+p4*(-0.044475+0.028874*p2-0.005916*p4)))*PJ.k]};
  const f1=v=>v.toFixed(1);
  // curva suave pelos pontos (Catmull-Rom → Bézier)
  const smooth=pts=>{const P=pts.map(p=>proj(p[0],p[1]));let d=`M${f1(P[0][0])},${f1(P[0][1])}`;
    for(let i=0;i<P.length-1;i++){const a=P[i-1]||P[i],b=P[i],c=P[i+1],e=P[i+2]||c;
      d+=` C${f1(b[0]+(c[0]-a[0])/6)},${f1(b[1]+(c[1]-a[1])/6)} ${f1(c[0]-(e[0]-b[0])/6)},${f1(c[1]-(e[1]-b[1])/6)} ${f1(c[0])},${f1(c[1])}`}
    return d};
  // enquadramento: a região [lon0..lon1 × lat0..lat1] cabe no retângulo da tela [x,y,w,h] (tela de 1920×1080)
  const fit=(lon0,lon1,lat0,lat1,[ax,ay,aw,ah])=>{const xs=[],ys=[];for(let i=0;i<=12;i++)for(let j=0;j<=12;j++){const[x,y]=proj(lon0+(lon1-lon0)*i/12,lat0+(lat1-lat0)*j/12);xs.push(x);ys.push(y)}
    const bx0=Math.min(...xs),bx1=Math.max(...xs),by0=Math.min(...ys),by1=Math.max(...ys),s=Math.max((bx1-bx0)/aw,(by1-by0)/ah);
    return [(bx0+bx1)/2-(ax+aw/2)*s,(by0+by1)/2-(ay+ah/2)*s,1920*s,1080*s]};
  // a faixa das etapas ocupa a parte de baixo: o mapa se enquadra acima dela
  const VIEW_WORLD=fit(-62,148,-41,44,[30,206,1370,544]),VIEW_BR=fit(-49.4,-43.6,-25.1,-21.4,[70,180,1300,560]);
  // posição na tela (1920×1080) com a câmera aproximada no Brasil: a camada do Brasil é desenhada em tamanho real
  const scr=(lon,lat)=>{const[x,y]=proj(lon,lat),s=VIEW_BR[2]/1920;return [(x-VIEW_BR[0])/s,(y-VIEW_BR[1])/s]};
  const smoothScr=pts=>{const P=pts.map(p=>scr(p[0],p[1]));let d=`M${f1(P[0][0])},${f1(P[0][1])}`;
    for(let i=0;i<P.length-1;i++){const a=P[i-1]||P[i],b=P[i],c=P[i+1],e=P[i+2]||c;
      d+=` C${f1(b[0]+(c[0]-a[0])/6)},${f1(b[1]+(c[1]-a[1])/6)} ${f1(c[0]-(e[0]-b[0])/6)},${f1(c[1]-(e[1]-b[1])/6)} ${f1(c[0])},${f1(c[1])}`}
    return d};
  // geografia das rotas (portos, rotas marítimas reais pelo Índico e Cabo da Boa Esperança, rodovia até os CDs)
  const SANTOS=[-46.33,-23.96],HUB=[104,1.2];
  const MAIN=[HUB,[98.5,4.2],[93,3.5],[80,-6],[62,-21],[42,-34.5],[22,-37.2],[8,-34],[-12,-29.5],[-32,-26.2],SANTOS];
  const CHINA={id:'156',n:t('geo.china'),port:t('geo.portsChina'),p:[121.8,30.6],feed:[[122.6,26.5],[118.5,21.2],[113.5,14],[108.5,7.5],[105.2,3.2],HUB]};
  const GEOMAP={
    Fisia:{title:t('geo.fisiaTitle'),origins:[
        {id:'704',n:t('geo.vietna'),port:'Ho Chi Minh',p:[106.9,10.4],feed:[[106.6,7.5],[105.2,3.6],HUB],lab:[16,8,'start']},
        {id:'360',n:t('geo.indonesia'),port:t('geo.jacarta'),p:[106.8,-6.1],feed:[[106.4,-3.8],[105,-.3],HUB],lab:[16,26,'start']},CHINA,
        {id:'764',n:t('geo.tailandia'),port:'Laem Chabang',p:[100.9,13.1],feed:[[101.8,9.6],[103.4,4.9],HUB],lab:[-16,-6,'end']},
        {id:'116',n:t('geo.camboja'),port:'Sihanoukville',p:[103.5,10.6],feed:[[104.1,6.3],HUB],lab:[-16,30,'end']}],
      hubName:t('geo.hubFisia'),
      land:[SANTOS,[-46.62,-23.55],[-46.56,-23.15],[-46.32,-22.85]],cds:[[d('CD Extrema'),[-46.32,-22.85]]],
      air:{pts:[[106.65,10.8],[58,30],[-46.47,-23.43]],label:t('geo.air')},
      legs:{cpt:'or',tt:'transito',des:'desembaraco',sefaz:'sefaz',road:'entrega'},sefazAt:[-46.32,-22.85],sefazName:'Sefaz MG'},
    Centauro:{title:t('geo.centauroTitle'),origins:[CHINA,
        {id:'586',n:t('geo.paquistao'),port:'Karachi',p:[66.9,24.8],feed:[[64.5,18],[60,5],[50,-16],[42,-34.5]],join:5},
        {id:'620',n:t('geo.portugal'),port:'Leixões',p:[-8.7,41.2],feed:[[-12.5,36],[-19,26],[-26,12],[-32,-4],[-39,-17],SANTOS],direct:true}],
      hubName:t('geo.hubCentauro'),
      land:[SANTOS,[-46.62,-23.55],[-46.56,-23.15],[-46.32,-22.85],[-46.52,-22.97],[-46.73,-23.1]],cds:[[d('CD Extrema'),[-46.32,-22.85]],[d('CD Jarinu'),[-46.73,-23.1]]],
      legs:{cpt:'estufagem',tt:'internacional',des:'desembaraco',sefaz:'sefaz',road:'nacional'},sefazAt:[-46.33,-23.96],sefazName:'SEFAZ'}};
  const GRAT=(()=>{let d='';for(let lon=-180;lon<=180;lon+=20){const pts=[];for(let lat=-80;lat<=80;lat+=5)pts.push(proj(lon,lat));if(Math.abs(((lon-PJ.lon0+540)%360)-180)<179)d+='M'+pts.map(p=>p.map(f1).join(',')).join('L')}
    for(let lat=-60;lat<=60;lat+=20){const pts=[];for(let lon=PJ.lon0-179;lon<=PJ.lon0+179;lon+=4)pts.push(proj(lon,lat));d+='M'+pts.map(p=>p.map(f1).join(',')).join('L')}return d})();
  const FL=DATA.flows||{},U=FL.units||{},units=Object.keys(U);
  if(!units.length){$('#loading').textContent=t('noFlows');return}
  const stars=DATA.stars||[];
  const tally=list=>{const t={nexxusdoc:0,manual:0,sem:0};list.forEach(s=>t[s.s]=(t[s.s]||0)+1);return t};
  const uniq=list=>{const seen=new Set();return list.filter(s=>!seen.has(s.id)&&seen.add(s.id))};
  const prazoTxt=p=>`${p.rotulo?p.rotulo+' · ':''}${dias(p.dias)}`;

  /* ---------- slides ---------- */
  const slides=[];
  const head=(kicker,title,lede='',extra='')=>`<div class="kicker" data-anim="fade-down">${kicker}</div><h2 class="title" data-anim="fade-up">${title}</h2>${lede?`<p class="lede" data-anim="fade-up">${lede}</p>`:''}${extra}`;
  const badge=u=>`<span class="unit-badge" style="--c:${UNIT[u]?.c||'#b5dc3c'}"><i></i>${esc(u)}</span>`;

  // 1. capa
  slides.push(`<section class="slide cover" data-k="cover" data-title="${esc(t('sl.cover'))}">
    <div class="cover-copy"><div class="kicker" data-anim="fade-down">REF. DOCS · ${esc(d(DATA.area||'Logística Internacional'))}</div>
      <h1 class="title glow-text" data-anim="rise-in">${t('cover.title')}</h1>
      <p class="lede" data-anim="fade-up">${t('cover.lede')}</p>
      <div class="cover-meta" data-anim="fade-up">${units.map(badge).join('')}</div></div>
    ${coverEmblem()}</section>`);

  // capa: os mesmos textos de antes (Sua Area, Fisia e Centauro com o lead time), parados; rotas pontilhadas
  // ligando cada unidade ao Sua Area e as linhas de um globo ao fundo
  function coverEmblem(){
    const cx=470,cy=430,pos=[[150,190],[800,690]],nodes=units.slice(0,2).map((u,i)=>({u,x:pos[i][0],y:pos[i][1]}));
    const globe=[...[0,1,2].map(i=>`<ellipse cx="${cx}" cy="${cy}" rx="${330-i*0}" ry="${[330,210,90][i]}"/>`),...[0,1].map(i=>`<ellipse cx="${cx}" cy="${cy}" rx="${[210,90][i]}" ry="330"/>`),`<circle cx="${cx}" cy="${cy}" r="330"/>`].join('');
    // a rota sai pela lateral do círculo da unidade (longe dos textos) e chega ao Sua Area
    const route=n=>{const up=n.y<cy,sx=n.x+(up?40:-40),ex=cx+(up?-80:80),ey=cy+(up?-80:80);
      return `<path class="ce-route" d="M${sx},${n.y} Q${up?ex+20:ex-20},${n.y} ${ex},${ey}"/>`};
    return `<svg class="cover-emblem" viewBox="0 0 940 860" aria-hidden="true">
      <defs><radialGradient id="ce-core" cx="50%" cy="45%" r="55%"><stop offset="0" stop-color="#f4ffd6"/><stop offset=".35" stop-color="#c8ff4d"/><stop offset="1" stop-color="#7fae36"/></radialGradient>
        <radialGradient id="ce-glow"><stop offset="0" stop-color="#b5dc3c" stop-opacity=".35"/><stop offset="1" stop-color="#b5dc3c" stop-opacity="0"/></radialGradient></defs>
      <g class="ce-globe">${globe}</g>
      ${nodes.map(route).join('')}
      <circle cx="${cx}" cy="${cy}" r="230" fill="url(#ce-glow)"/>
      <circle cx="${cx}" cy="${cy}" r="112" fill="url(#ce-core)" class="ce-core"/>
      <g transform="translate(${cx-26},${cy-58}) scale(2.2)" class="ce-ship">${ICON.navio}</g>
      <text x="${cx}" y="${cy+42}" class="ce-name">COE INBOUND</text>
      ${nodes.map(n=>{const c=UNIT[n.u]?.c||'#b5dc3c';return `<g class="ce-unit" style="--c:${c}"><circle cx="${n.x}" cy="${n.y}" r="58" class="ce-halo"/><circle cx="${n.x}" cy="${n.y}" r="30" class="ce-dot"/>
        <text x="${n.x}" y="${n.y-78}" class="ce-u">${esc(n.u.toUpperCase())}</text><text x="${n.x}" y="${n.y+96}" class="ce-lt">${esc(t('cover.lt',{n:U[n.u].lead_time||''}))}</text></g>`}).join('')}
    </svg>`;
  }

  // 2. lead time lado a lado (alinhado no início da consolidação)
  const DAY=10.5,ZERO=900;
  const ltRow=(u,top)=>{const f=U[u],segs=(f.prazos||[]).filter(p=>p.tipo==='segmento'),pre=(f.prazos||[]).filter(p=>p.tipo==='sourcing').reduce((a,p)=>a+p.dias,0);
    let i=0;const ghost=pre?`<div class="lt-seg ghost" style="--i:${i++};width:${pre*DAY}px"><b>${esc(t('lt.sourcing'))}</b><small>${esc(t('lt.beforeLt',{n:pre}))}</small></div>`
      :`<div class="lt-seg ghost" style="--i:${i++};width:${28*DAY}px"><b>${esc(t('lt.nikePre'))}</b><small>${esc(t('lt.outside'))}</small></div>`;
    const ghostW=pre?pre*DAY:28*DAY;
    return `<div class="lt-row" style="top:${top}px;--c:${UNIT[u].c}"><div class="lt-name">${badge(u)}<div class="num"><span class="cnt" data-to="${f.lead_time||0}">0</span><small>${esc(t('daysWord'))}</small></div></div>
      <div class="lt-bar" style="left:${ZERO-ghostW-4}px">${ghost}${segs.map(p=>`<div class="lt-seg" style="--i:${i++};width:${p.dias*DAY-4}px;--c:${p.rotulo==='TT'?'#5b8cff':p.rotulo==='CPT'?'#7c9cff':'#b5dc3c'}"><b>${esc(d(p.rotulo))}</b><small>${esc(dias(p.dias))}</small></div>`).join('')}</div></div>`};
  // "Tema: texto": o filtro olha o original em português; a tradução mantém o mesmo formato
  const diffs=(FL.differences||[]).filter(x=>!/^prazos/i.test(x)).slice(0,4).map(x=>{const s=d(x),k=s.indexOf(':');return `<div class="diff"><h4>${esc(k>0?s.slice(0,k):t('lt.diff'))}</h4><p>${esc(k>0?s.slice(k+1).trim():s)}</p></div>`}).join('');
  slides.push(`<section class="slide" data-k="lt" data-title="${esc(t('sl.lt'))}">${head(t('lt.kicker'),t('lt.title'),t('lt.lede'))}
    <div class="lt"><div class="lt-zero" style="left:${ZERO}px"><small>${esc(t('lt.zero'))}</small></div>${units.map((u,k)=>ltRow(u,20+k*190)).join('')}</div>
    <div class="diffs anim-stagger-list">${diffs}</div></section>`);

  // rota no mapa: trechos da viagem (dias vindos dos prazos da unidade, editáveis pelo master/owner)
  const LEG_ICON={cpt:'conteiner',tt:'navio',des:'aduana',sefaz:'sefaz',road:'caminhao'};
  // em que momento da viagem cada etapa acende (pré-embarque com as origens, embarque na consolidação…)
  const STEP_PHASE=s=>['pre','sourcing'].includes(s.fase)?'origins':s.fase==='embarque'?'cpt':s.fase==='navegacao'?'tt'
    :['chegada','desembaraco'].includes(s.fase)?(s.id==='sefaz'?'sefaz':'des'):s.fase==='entrega'?'road':'zout';
  const legsOf=u=>{const f=U[u],G=GEOMAP[u],pz=f.prazos||[],par=f.parceiros||{},stepName=id=>d((f.etapas||[]).find(s=>s.id===id)?.nome||'');
    const partner=re=>Object.entries(par).filter(([k])=>re.test(k)).flatMap(([,v])=>v).filter((x,i,a)=>a.indexOf(x)===i).join(', ');
    const etapa=ids=>pz.find(p=>p.tipo==='etapa'&&(ids.includes(p.de)||ids.includes(p.ate)));
    const days=p=>p?Number(p.dias)||0:0;
    return [
      {k:'cpt',n:t(u==='Fisia'?'leg.cptFisia':'leg.cptCentauro'),sub:partner(u==='Fisia'?/consolid/i:/agente/i),d:days(pz.find(p=>p.rotulo==='CPT')),stage:G.legs.cpt,tag:'CPT'},
      {k:'tt',n:t('leg.tt'),sub:partner(u==='Fisia'?/marít/i:/agente/i),d:days(pz.find(p=>p.rotulo==='TT')),stage:G.legs.tt,tag:'TT'},
      {k:'des',n:t('leg.des'),chip:t('leg.desChip'),sub:partner(/despach/i),d:days(etapa(['desembaraco'])),stage:G.legs.des,tag:''},
      {k:'sefaz',n:t('leg.sefaz',{s:G.sefazName}),sub:t('leg.icms'),d:days(etapa(['sefaz'])),stage:G.legs.sefaz,tag:''},
      // no cartão do mapa, inglês e espanhol usam um rótulo curto (o nome completo não cabe); o português fica como antes
      {k:'road',n:t('leg.road',{cds:G.cds.map(c=>c[0]).join(t('and')),list:G.cds.map(c=>c[0])}),chip:LANG==='pt'?'':t('leg.roadChip'),sub:partner(/rodovi/i),d:days(etapa(['entrega','nacional'])),stage:G.legs.road,tag:''}]
      .map(l=>({...l,stageName:stepName(l.stage)}))};
  const mapSlide=u=>{const G=GEOMAP[u],f=U[u],c=UNIT[u].c,legs=legsOf(u),orig=new Set(G.origins.map(o=>o.id));
    const sB=VIEW_BR[2]/1920; // escala do mapa aproximado no Brasil (tamanhos dos pinos)
    const lanes=[];if(G.origins.some(o=>!o.direct&&!o.join))lanes.push({k:'main',pts:MAIN});
    G.origins.forEach(o=>{if(o.join)lanes.push({k:'join',pts:[o.p,...o.feed,...MAIN.slice(o.join+1)]});if(o.direct)lanes.push({k:'direct',pts:[o.p,...o.feed]})});
    const feeds=G.origins.filter(o=>!o.direct).map(o=>({o,d:smooth([o.p,...(o.join?o.feed:o.feed)])}));
    const pre=(f.prazos||[]).filter(p=>p.tipo==='sourcing').reduce((a,p)=>a+(Number(p.dias)||0),0);
    const pin=(p,r,cls='')=>{const[x,y]=proj(p[0],p[1]);return `<circle class="${cls}" cx="${f1(x)}" cy="${f1(y)}" r="${r}"/>`};
    const txt=(p,dx,dy,t,cls,size)=>{const[x,y]=proj(p[0],p[1]);return `<text class="${cls}" x="${f1(x+dx)}" y="${f1(y+dy)}" font-size="${size}">${esc(t)}</text>`};
    const lab=(o,line)=>{const[dx,dy,an]=o.lab||[12,-12,'start'];return {dx,dy:dy+(line?20:0),an}};
    const otxt=(o,t,cls,size,line)=>{const[x,y]=proj(o.p[0],o.p[1]),L=lab(o,line);return `<text class="${cls}${L.an==='end'?' end':''}" x="${f1(x+L.dx)}" y="${f1(y+L.dy)}" font-size="${size}">${esc(t)}</text>`};
    // camada do Brasil (coordenadas de tela com a câmera aproximada)
    const sp=(p,r,cls)=>{const[x,y]=scr(p[0],p[1]);return `<circle class="${cls}" cx="${f1(x)}" cy="${f1(y)}" r="${r}"/>`};
    const st=(p,dx,dy,t,cls)=>{const[x,y]=scr(p[0],p[1]);return `<text class="${cls}" x="${f1(x+dx)}" y="${f1(y+dy)}">${esc(t)}</text>`};
    const brPins=[[SANTOS,t('geo.santosPort'),-16,6,'end'],...G.cds.map((c2,i)=>[c2[1],c2[0],u==='Centauro'&&i===1?-16:16,u==='Centauro'&&i===1?6:-12,u==='Centauro'&&i===1?'end':'start']),
      [[-46.63,-23.55],'São Paulo',-12,-10,'end city']];
    const ufLabels=[['SÃO PAULO',[-48.4,-22.35]],['MINAS GERAIS',[-45.5,-21.7]],['RIO DE JANEIRO',[-43.75,-22.62]]];
    // faixa das etapas: cada cartão acende quando a viagem chega na etapa dele
    const steps=f.etapas||[],sidx=Object.fromEntries(steps.map((s,i)=>[s.id,i])),pz=f.prazos||[];
    const inside=(p,q)=>p!==q&&sidx[p.de]<=sidx[q.de]&&sidx[p.ate]>=sidx[q.ate];
    const leafPz=pz.filter(p=>!pz.some(q=>inside(p,q)));
    const stepDays=id=>leafPz.filter(p=>p.de===id).map(p=>`${p.rotulo&&p.rotulo!=='Sourcing'?d(p.rotulo)+' ':''}${dias(p.dias)}`).join(' · ');
    const GRP=[['pre','sourcing'],['embarque','navegacao'],['chegada','desembaraco'],['entrega','pos']];
    const grpName=[t(steps.some(s=>s.fase==='sourcing')?'grp.sourcing':'grp.pre'),t('grp.embarque'),t('grp.chegada'),t(steps.some(s=>s.fase==='pos')?'grp.pos':'grp.entrega')];
    const spans=[];steps.forEach(s=>{const g=GRP.findIndex(x=>x.includes(s.fase));const last=spans[spans.length-1];if(last&&last.g===g)last.n++;else spans.push({g,n:1})});
    const strip=`<div class="rt-strip" style="--n:${steps.length}">
        <div class="rt-groups">${spans.map(sp2=>`<span style="grid-column:span ${sp2.n}">${esc(grpName[sp2.g]||'')}</span>`).join('')}</div>
        <div class="rt-steps"><div class="rt-track" style="background:linear-gradient(90deg,${steps.map(s=>(PHASE[s.fase]||PHASE.desembaraco)[1]+'33').join(',')})"><i class="rt-fill" style="background:linear-gradient(90deg,${steps.map(s=>(PHASE[s.fase]||PHASE.desembaraco)[1]).join(',')});"></i></div>${steps.map((s,i)=>{const sd=stepDays(s.id);return `<button type="button" class="rt-step" data-step="${esc(s.id)}" data-unit="${u}" data-ph="${STEP_PHASE(s)}" title="${esc(d(s.descricao))}" style="--c:${(PHASE[s.fase]||PHASE.desembaraco)[1]}"><span class="st-ic"><span class="halo"></span>${ic(s.icone,'')}</span><b>${esc(d(s.nome))}</b><small>${esc(d(s.responsavel||''))}</small>${sd?`<em>${esc(sd)}</em>`:''}</button>`}).join('')}</div></div>`;
    const chipAt={des:[SANTOS,30,30],sefaz:[u==='Fisia'?G.cds[0][1]:SANTOS,30,u==='Fisia'?-130:-112],road:[G.cds[G.cds.length-1][1],u==='Centauro'?-300:30,u==='Centauro'?30:24]};
    const brChips=legs.filter(l=>chipAt[l.k]).map(l=>{const[p,dx,dy]=chipAt[l.k],[x,y]=scr(p[0],p[1]);
      return `<g class="chip-br" data-k="${l.k}" transform="translate(${f1(x+dx)},${f1(y+dy)})"><rect width="270" height="64" rx="14"/><text x="18" y="26" class="cl">${esc(l.chip||l.n)}</text><text x="18" y="50" class="cd">${esc(dias(l.d))}${l.k==='road'&&u==='Centauro'?' · FCL 3 / LCL 5':''}</text></g>`}).join('');
    return `<section class="slide map-slide" data-k="${esc(u)}-route" data-title="${esc(t('sl.route',{u}))}" data-map="${u}" style="--c:${c}">
      <div class="map-ocean"></div>
      <svg class="map map-base" viewBox="${VIEW_WORLD.map(f1).join(' ')}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <path class="grat" d="${GRAT}"/>
        <g class="lands">${(MAP?.countries||[]).map(k=>`<path class="land${orig.has(k.id)?' orig':''}${k.id==='076'?' dest':''}" data-id="${k.id}" d="${k.d}"/>`).join('')}</g>
        <g class="ufs">${(MAP?.uf||[]).map(x=>`<path class="uf${['SP','MG','RJ'].includes(x.s)?' hot':''}" data-uf="${x.s}" d="${x.d}"/>`).join('')}</g></svg>
      <svg class="map map-top" viewBox="${VIEW_WORLD.map(f1).join(' ')}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <g class="orig-hl">${(MAP?.countries||[]).filter(k=>orig.has(k.id)).map(k=>`<path data-id="${k.id}" d="${k.d}"/>`).join('')}</g>
        <g class="routes">
          ${feeds.map((x,i)=>`<path class="rt feed" data-o="${i}" d="${x.d}"/>`).join('')}
          ${lanes.map((l,i)=>`<path class="rt sea-glow" d="${smooth(l.pts)}"/><path class="rt sea" data-lane="${i}" d="${smooth(l.pts)}"/>`).join('')}
          ${G.air?`<path class="rt air" d="${smooth(G.air.pts)}"/>`:''}</g>
        <g class="world-marks">
          ${G.origins.map((o,i)=>`<g class="orig-mark" data-o="${i}">${pin(o.p,22,'pulse')}${pin(o.p,5.5,'port')}${otxt(o,o.n,'cn',19,false)}${otxt(o,o.port,'pn',13,true)}</g>`).join('')}
          ${G.origins.some(o=>!o.direct&&!o.join)?`<g class="hub">${pin(HUB,6,'port hubp')}${txt(HUB,-12,26,G.hubName,'pn end',13)}</g>`:''}
          <g class="dest-mark">${pin(SANTOS,6,'port destp')}${txt(SANTOS,-14,4,'Santos','cn end',19)}</g>
          ${G.air?`<g class="air-mark">${txt(G.air.pts[1],0,-14,G.air.label,'pn mid air-l',14)}</g>`:''}</g>
        <g class="ships" data-lane="all">${lanes.map((l,i)=>`<g class="ship" data-lane="${i}"><circle r="15" class="halo-v"/><g transform="translate(-12,-12)" class="vic">${ICON.navio}</g></g>`).join('')}</g>
        ${G.air?`<g class="mover plane"><circle r="13" class="halo-v air-h"/><path class="vic-fill" d="M-11,0 L8,-1.6 L11,0 L8,1.6 Z M-2,-1 L2,-9 L4,-9 L3,-1 Z M-2,1 L2,9 L4,9 L3,1 Z M-10,-.8 L-8,-4.5 L-6.5,-4.5 L-7,-.8 Z M-10,.8 L-8,4.5 L-6.5,4.5 L-7,.8 Z"/></g>`:''}
      </svg>
      <svg class="br-layer" viewBox="0 0 1920 1080" aria-hidden="true">
        ${ufLabels.map(([n,p])=>{const[x,y]=scr(p[0],p[1]);return `<text class="uf-l" x="${f1(x)}" y="${f1(y)}">${n}</text>`}).join('')}
        <path class="road-glow" d="${smoothScr(G.land)}"/><path class="road" d="${smoothScr(G.land)}"/>
        ${brPins.map(([p,n,dx,dy,an])=>`${sp(p,an.includes('city')?4:7,'brp'+(an.includes('city')?' city':''))}${st(p,dx,dy,n,(an.includes('city')?'bt city ':'bt ')+an.split(' ')[0])}`).join('')}
        ${brChips}
        <g class="mover truck"><circle r="22" class="halo-v road-h"/><g transform="translate(-15,-15) scale(1.25)" class="vic">${ICON.caminhao}</g></g>
      </svg>
      <div class="map-head"><div class="kicker" data-anim="fade-down">${esc(t('map.kicker'))} · <b style="--k:${c}">${esc(u.toUpperCase())}</b></div>
        <h2 class="title" data-anim="fade-up">${badge(u)}&nbsp; ${esc(G.title)}</h2></div>
      <aside class="rt-panel">
        <div class="rt-day"><span>${esc(t('rt.day'))}</span><b class="rt-n">0</b><small>${t('rt.of',{n:f.lead_time||legs.reduce((a,l)=>a+l.d,0)})}</small></div>
        <div class="rt-origins"><h5>${esc(t('rt.origins'))}</h5>${G.origins.map((o,i)=>`<span data-o="${i}"><i></i>${esc(o.n)}</span>`).join('')}</div>
        <ol class="rt-legs">${legs.map(l=>`<li data-leg="${l.k}" data-step="${esc(l.stage)}" data-unit="${u}" title="${esc(t('rt.legTip',{s:l.stageName}))}"><span class="li-ic">${ic(LEG_ICON[l.k],'')}</span><div><b>${esc(l.n)}</b>${l.sub?`<small>${esc(l.sub)}</small>`:''}</div><em>${l.tag?l.tag+' · ':''}${esc(dias(l.d))}</em></li>`).join('')}</ol>
        <div class="rt-note">${esc(pre?t('rt.noteSourcing',{n:pre}):t('rt.noteNike'))}</div>
        <div class="rt-modes"><span class="m-sea"><i></i>${esc(t('rt.sea'))}</span><span class="m-road"><i></i>${esc(t('rt.road'))}</span>${G.air?`<span class="m-air"><i></i>${esc(t('rt.air'))}</span>`:''}</div>
        <button type="button" class="rt-replay"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12a8 8 0 1 0 2.4-5.7M4 4v4h4"/></svg>${esc(t('rt.replay'))}</button>
      </aside>${strip}</section>`};

  // 3-6. rota no mapa (com as etapas acendendo conforme a viagem) e fases em detalhe de cada unidade
  const GEO={};
  units.forEach(u=>{
    if(GEOMAP[u]&&MAP)slides.push(mapSlide(u));
    const f=U[u],steps=f.etapas||[],hasSourcing=steps.some(s=>s.fase==='sourcing');
    const idx=Object.fromEntries(steps.map((s,i)=>[s.id,i])),prazos=f.prazos||[],laneC=UNIT[u].c;

    // fases em detalhe
    const GROUPS=[{f:['sourcing','pre'],n:t(hasSourcing?'grp.sourcingShort':'grp.preShort'),c:'#4cc9f0'},{f:['embarque','navegacao'],n:t('grp.embarque'),c:'#7c9cff'},
      {f:['chegada','desembaraco'],n:t('grp.chegada'),c:'#b5dc3c'},{f:['entrega','pos'],n:t(steps.some(s=>s.fase==='pos')?'grp.pos':'grp.entrega'),c:'#f4b740'}];
    const pos=id=>idx[id]??-1;
    const contains=(p,q)=>p!==q&&pos(p.de)<=pos(q.de)&&pos(p.ate)>=pos(q.ate);
    const leaf=prazos.filter(p=>!prazos.some(q=>contains(p,q)));
    const partners=Object.entries(f.parceiros||{});
    const pgroup=k=>/consolid|marít|agente/i.test(k)?1:/despach|termina/i.test(k)?2:/rodovi/i.test(k)?3:-1;
    const cols=GROUPS.map((g,gi)=>{const list=steps.filter(s=>g.f.includes(s.fase));if(!list.length)return '';
      const mine=leaf.filter(p=>{const s=steps[pos(p.de)];return s&&g.f.includes(s.fase)}),days=mine.filter(p=>p.tipo!=='pos').reduce((a,p)=>a+p.dias,0),extra=mine.filter(p=>p.tipo==='pos');
      const who=[...new Set(list.map(s=>d(s.responsavel)).filter(Boolean))].join(' · ');
      const linked=uniq(list.flatMap(s=>s.stars)),tl=tally(linked),n=linked.length||1;
      const seen=new Set(),parts=partners.filter(([k])=>pgroup(k)===gi).flatMap(([k,v])=>v.filter(x=>!seen.has(x)&&seen.add(x)).map(x=>`<em title="${esc(d(k))}">${esc(x)}</em>`)).join('');
      return `<div class="pcol" style="--c:${g.c};--i:${gi}">${days?`<div class="days">${days}<small>${esc(t('daysWord'))}</small></div>`:''}<h3>${esc(g.n)}</h3><div class="who">${esc(who)}</div>
        <ol>${list.map(s=>`<li data-step="${esc(s.id)}" data-unit="${u}" title="${esc(t('ph.stepTip'))}"><span class="mini">${ic(s.icone,'')}</span><div><b>${esc(d(s.nome))}</b><span>${esc(d(s.descricao))}</span></div></li>`).join('')}</ol>
        ${extra.length?`<div class="cov">${esc(t('ph.afterCd',{list:extra.map(p=>`${d(p.rotulo)} ${dias(p.dias)}`).join(', ')}))}</div>`:''}${mine.some(p=>p.tipo==='sourcing')?`<div class="cov">${esc(t('ph.beforeLt'))}</div>`:''}
        <div class="partners">${parts}</div>
        <div class="cov">${esc(t('ph.coverage',{n:linked.length,d:tl.nexxusdoc+tl.manual}))}<div class="bar"><i style="width:${tl.nexxusdoc/n*100}%;background:#c8ff4d"></i><i style="width:${tl.manual/n*100}%;background:#35e3c4"></i></div></div></div>`}).join('');
    slides.push(`<section class="slide" data-k="${esc(u)}-phases" data-title="${esc(t('sl.phases',{u}))}">${head(`${esc(t('ph.kicker'))} · <b style="--k:${laneC}">${esc(u.toUpperCase())}</b>`,`${badge(u)}&nbsp; ${esc(t('ph.title'))}`)}
      <div class="phases">${cols}</div></section>`);
  });

  // 7. onde as operações se separam
  const cmp=FL.comparison||[];
  if(cmp.length&&U.Fisia&&U.Centauro){
    let i=0;const hot=/^\d+ dias$/;
    slides.push(`<section class="slide" data-k="cmp" data-title="${esc(t('sl.cmp'))}">${head(t('cmp.kicker'),t('cmp.title'),t('cmp.lede'))}
      <div class="cmp"><div class="h l">${badge('Fisia')}</div><div></div><div class="h r">${badge('Centauro')}</div>
      ${cmp.map(r=>`<div class="c l${hot.test(r.Fisia)?' hot':''}" style="--i:${i++}">${esc(d(r.Fisia))}</div><div class="t" style="--i:${i++}">${esc(d(r.tema))}</div><div class="c r${hot.test(r.Centauro)?' hot':''}" style="--i:${i++}">${esc(d(r.Centauro))}</div>`).join('')}</div></section>`);
  }

  // 8. documentação por unidade
  const dcard=u=>{const f=U[u],mine=stars.filter(s=>(s.u||[]).includes(u)),tl=tally(mine),pct=mine.length?Math.round((tl.nexxusdoc+tl.manual)/mine.length*100):0;
    const only=mine.filter(s=>s.u.length===1).length,C=2*Math.PI*80;
    const strip=(f.etapas||[]).map(s=>{const t2=tally(s.stars),n=s.stars.length,r=n?(t2.nexxusdoc+t2.manual)/n:0,h=!n?'#56666b':r>=.99?'#c8ff4d':r>0?'#35e3c4':'#e5484d';
      return `<button type="button" data-step="${esc(s.id)}" data-unit="${u}" style="--h:${h}" title="${esc(d(s.nome))}">${esc(d(s.nome))}<b>${n?`${t2.nexxusdoc+t2.manual}/${n}`:'-'}</b></button>`}).join('');
    return `<div class="dcard" style="--c:${UNIT[u].c}"><header><div class="ring"><svg viewBox="0 0 190 190"><circle class="trk" cx="95" cy="95" r="80"/><circle class="val" cx="95" cy="95" r="80" stroke="${UNIT[u].c}" stroke-dasharray="${C}" stroke-dashoffset="${C}" data-off="${C*(1-pct/100)}"/></svg><b>${pct}%<small>${esc(t('doc.pct'))}</small></b></div>
      <div><div style="margin-bottom:14px">${badge(u)}</div><div class="facts"><div><b>${mine.length}</b><span>${esc(t('doc.unitProcs'))}</span></div><div><b>${only}</b><span>${esc(t('doc.only',{u}))}</span></div><div><b>${tl.nexxusdoc}</b><span>${esc(t('doc.inNexxus'))}</span></div></div></div></header>
      <div class="strip">${strip}</div></div>`};
  slides.push(`<section class="slide" data-k="docs" data-title="${esc(t('sl.docs'))}">${head(t('doc.kicker'),t('doc.title'),t('doc.lede'))}
    <div class="docs-grid">${units.map(dcard).join('')}</div>
    <div class="legend-st"><span style="--m:#c8ff4d"><i></i>${esc(t('doc.full'))}</span><span style="--m:#35e3c4"><i></i>${esc(t('doc.part'))}</span><span style="--m:#e5484d"><i></i>${esc(t('doc.none'))}</span><span style="--m:#56666b"><i></i>${esc(t('doc.noProc'))}</span></div></section>`);

  // 9. encerramento
  slides.push(`<section class="slide closing" data-k="end" data-title="${esc(t('sl.end'))}"><div class="glows" aria-hidden="true"><i></i><i></i><i></i></div>
    <div class="kicker" data-anim="fade-down" style="position:relative">NexxusDoc · Chat Nexxus</div>
    <h1 class="title glow-text" data-anim="zoom-pop">${t('end.title')}</h1>
    <p class="lede" data-anim="fade-up">${esc(t('end.lede'))}</p>
    <div class="cta" data-anim="fade-up"><button type="button" data-close>${esc(t('end.back'))}</button><button type="button" class="alt" data-go="1">${esc(t('end.again'))}</button></div></section>`);

  /* ---------- moldura ---------- */
  // os slides são achados pela chave fixa (data-k), não pelo título, que muda com o idioma
  const firstOf=k=>slides.findIndex(s=>s.includes(`data-k="${k}"`))+1;
  const unitStart=u=>firstOf(`${u}-route`)||firstOf(`${u}-phases`);
  const JUMPS=[[t('nav.start'),1,''],...units.map(u=>[u,unitStart(u),UNIT[u].c]),[t('nav.cmp'),firstOf('cmp'),''],[t('nav.docs'),firstOf('docs'),'']].filter(j=>j[1]>0);
  $('#loading').remove();
  deck.insertAdjacentHTML('beforeend',slides.join('')+
    `<div class="deck-brand"><span class="badge">REF. DOCS</span><span>${esc(t('brand'))}</span><div class="jumps">${JUMPS.map(([n,k,c])=>`<button type="button" data-go="${k}"${c?` style="--c:${c}"`:''}>${c?'<i></i>':''}${esc(n)}</button>`).join('')}</div></div>
     <div class="deck-nav"><button type="button" data-nav="-1" aria-label="${esc(t('nav.prev'))}"><svg viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6"/></svg></button><span class="slide-number" data-current="1" data-total="${slides.length}"></span><button type="button" data-nav="1" aria-label="${esc(t('nav.next'))}"><svg viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></svg></button></div>
     <div class="deck-hint">${esc(t('nav.hint'))}</div>
     <aside class="drawer" id="drawer"><button class="drawer-x" type="button" aria-label="${esc(t('close'))}"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg></button><div id="drawer-body"></div></aside>`);

  // abre já na unidade escolhida no universo
  const want=new URLSearchParams(location.search).get('unidade');
  if(want&&U[want]&&!/^#\/\d+/.test(location.hash))history.replaceState(null,'','#/'+unitStart(want));

  /* ---------- interação ---------- */
  const drawer=$('#drawer');
  const openStep=(u,id)=>{const f=U[u],s=(f.etapas||[]).find(x=>x.id===id);if(!s)return;const ph=PHASE[s.fase]||PHASE.desembaraco;
    const pz=(f.prazos||[]).filter(p=>p.de===id||p.ate===id);
    $$('.node').forEach(n=>n.classList.toggle('sel',n.dataset.step===id&&n.dataset.unit===u));
    $('#drawer-body').innerHTML=`<div class="ph" style="--c:${ph[1]}">${esc(ph[0])} · ${esc(u)}</div><h3>${esc(d(s.nome))}</h3>
      <div class="chips"><span class="chip">${esc(d(s.responsavel)||'-')}</span>${pz.map(p=>`<span class="chip days" title="${esc(d(p.descricao)||'')}">${esc(prazoTxt(p))}</span>`).join('')}</div>
      <p>${esc(d(s.descricao))}</p><h4>${esc(t('dr.procs',{n:s.stars.length}))}</h4>
      ${s.stars.length?s.stars.map(st=>{const local=/^\/api\/documents\//.test(st.url||''),offline=local&&window.__NEXXUS_DATA;  // prévia fora do sistema
        const safeUrl=!offline&&/^(https:\/\/|\/api\/documents\/)/.test(st.url||'')?st.url:'';
        // com documento: abre o PDF do NexxusDoc ou o manual do Drive numa aba separada; sem documento: vai ao universo
        // o nome do processo é traduzido; o código e o título do documento ficam como estão (o documento é em português)
        return `<div class="proc" style="--m:${ST[st.s][0]}"><i></i><span>${esc(d(st.n))}<small>${ST[st.s][1]}${st.doc?' · '+esc(st.doc):''}${st.s==='manual'&&st.man?' · '+esc(st.man):''}</small></span>
          ${safeUrl?`<a class="proc-open" href="${esc(safeUrl)}" target="_blank" rel="noopener" title="${esc(t('dr.openTip'))}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>${esc(t('dr.open'))}</a>`
            :`<span class="proc-none">${esc(t(offline?'dr.offline':'dr.none'))}</span>`}
          <button type="button" class="proc-uni" data-star="${esc(st.id)}" title="${esc(t('dr.uniTip'))}"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="8.5"/></svg></button></div>`}).join('')
        +`<div class="hint">${esc(t('dr.hint'))}</div>`
        :`<p class="hint">${esc(t('dr.empty'))}</p>`}`;
    drawer.classList.add('open')};
  const closeDrawer=()=>{drawer.classList.remove('open');$$('.node.sel').forEach(n=>n.classList.remove('sel'))};
  const key=k=>document.dispatchEvent(new KeyboardEvent('keydown',{key:k,bubbles:true}));
  deck.addEventListener('click',e=>{
    if(e.target.closest('.cfg'))return;  // cliques do modal de edição são tratados por ele
    const step=e.target.closest('[data-step]');if(step){openStep(step.dataset.unit,step.dataset.step);return}
    const star=e.target.closest('[data-star]');if(star){send({type:'nexxus-flow-star',id:star.dataset.star});return}
    const go=e.target.closest('[data-go]');if(go){closeDrawer();location.hash='#/'+go.dataset.go;return}
    const nav=e.target.closest('[data-nav]');if(nav){closeDrawer();key(nav.dataset.nav==='1'?'ArrowRight':'ArrowLeft');return}
    if(e.target.closest('[data-close]')){send({type:'nexxus-flow-close'});return}
    if(e.target.closest('.drawer-x')||(!e.target.closest('.drawer')&&drawer.classList.contains('open')))closeDrawer()});
  addEventListener('keydown',e=>{if(e.key!=='Escape')return;if(drawer.classList.contains('open'))closeDrawer();else if(!$('.overview.open'))send({type:'nexxus-flow-close'})});

  /* ---------- edição dos dados (master e owner da área) ---------- */
  (window.__NEXXUS_FLOWS?Promise.resolve(window.__NEXXUS_FLOWS):fetch('/api/fluxos',{credentials:'same-origin'}).then(r=>r.ok?r.json():null)).then(info=>{
    if(!info||!info.can_edit)return;
    $('.deck-brand').insertAdjacentHTML('beforeend',`<button type="button" class="cfg-open" title="${esc(t('cfg.openTip'))}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/></svg>${esc(t('cfg.open'))}</button>`);
    $('.cfg-open').addEventListener('click',()=>openConfig(info));
  }).catch(()=>{});
  function openConfig(info){
    if($('.cfg'))return;
    const F=info.flows||{},UN=Object.keys(UNIT).filter(u=>F[u]);
    const inp=(path,v,cls='')=>`<input class="${cls}" data-p="${path}" value="${esc(v??'')}">`;
    const num=(path,v)=>`<input type="number" min="0" max="400" class="n" data-p="${path}" value="${esc(v??'')}">`;
    const area=(path,v,rows=2)=>`<textarea data-p="${path}" rows="${rows}">${esc(v??'')}</textarea>`;
    const lines=(path,list,rows=4)=>`<textarea data-p="${path}" data-lines rows="${rows}">${esc((list||[]).join('\n'))}</textarea>`;
    const unitTab=u=>{const f=F[u],names=Object.fromEntries((f.etapas||[]).map(s=>[s.id,s.nome]));
      // os campos guardam o texto de origem (em português); só os rótulos da tela seguem o idioma escolhido
      return `<div class="cfg-pane" data-pane="${u}"><h4>${esc(t('cfg.general'))}</h4><div class="cfg-grid g2">
          <label>${esc(t('cfg.unitDesc'))}${area(`${u}.descricao`,f.descricao)}</label><label>${esc(t('cfg.lead'))}${area(`${u}.responsabilidade`,f.responsabilidade)}</label>
          <label>${esc(t('cfg.ltTotal'))}${num(`${u}.lead_time_dias`,f.lead_time_dias)}</label><label>${esc(t('cfg.ltFormula'))}${inp(`${u}.lead_time_formula`,f.lead_time_formula)}</label></div>
        <h4>${esc(t('cfg.steps'))}</h4><table class="cfg-t"><thead><tr><th style="width:24%">${esc(t('cfg.step'))}</th><th style="width:18%">${esc(t('cfg.owner'))}</th><th>${esc(t('cfg.desc'))}</th></tr></thead><tbody>
          ${(f.etapas||[]).map(s=>`<tr><td>${inp(`${u}.etapas.${s.id}.nome`,s.nome)}</td><td>${inp(`${u}.etapas.${s.id}.responsavel`,s.responsavel)}</td><td>${area(`${u}.etapas.${s.id}.descricao`,s.descricao)}</td></tr>`).join('')}</tbody></table>
        <h4>${esc(t('cfg.deadlines'))}</h4><table class="cfg-t"><thead><tr><th style="width:12%">${esc(t('cfg.label'))}</th><th style="width:10%">${esc(t('cfg.days'))}</th><th style="width:26%">${esc(t('cfg.leg'))}</th><th>${esc(t('cfg.desc'))}</th></tr></thead><tbody>
          ${(f.prazos||[]).map((p,i)=>`<tr><td>${inp(`${u}.prazos.${i}.rotulo`,p.rotulo)}</td><td>${num(`${u}.prazos.${i}.dias`,p.dias)}</td><td class="ro">${esc(names[p.de]||p.de)}${p.ate!==p.de?` → ${esc(names[p.ate]||p.ate)}`:''}</td><td>${inp(`${u}.prazos.${i}.descricao`,p.descricao)}</td></tr>`).join('')}</tbody></table>
        <h4>${esc(t('cfg.partners'))} <small>${esc(t('cfg.partnersHint'))}</small></h4><div class="cfg-grid g2">
          ${Object.entries(f.parceiros||{}).map(([k,v])=>`<label>${esc(d(k))}<input data-p="${u}.parceiros.${esc(k)}" data-csv value="${esc((v||[]).join(', '))}"></label>`).join('')}</div>
        <h4>${esc(t('cfg.glossary'))} <small>${esc(t('cfg.glossaryHint'))}</small></h4>${lines(`${u}.glossario`,f.glossario,5)}</div>`};
    const cmpTab=`<div class="cfg-pane" data-pane="cmp"><h4>${esc(t('cmp.kicker'))}</h4><table class="cfg-t"><thead><tr><th style="width:22%">${esc(t('cfg.topic'))}</th><th>Fisia</th><th>Centauro</th></tr></thead><tbody>
        ${(F.comparativo||[]).map((r,i)=>`<tr><td>${inp(`comparativo.${i}.tema`,r.tema)}</td><td>${area(`comparativo.${i}.Fisia`,r.Fisia)}</td><td>${area(`comparativo.${i}.Centauro`,r.Centauro)}</td></tr>`).join('')}</tbody></table>
      <h4>${esc(t('cfg.diffs'))} <small>${esc(t('cfg.diffsHint'))}</small></h4>${lines('diferencas',F.diferencas,6)}
      <h4>${esc(t('cfg.notes'))} <small>${esc(t('cfg.notesHint'))}</small></h4>${area('observacao',F.observacao,3)}</div>`;
    const meta=info.custom?esc(t('cfg.editedBy',{who:info.updated_by||'-'})+(info.updated_at?t('cfg.editedAt',{when:new Date(info.updated_at).toLocaleString(t('locale'))}):'')):esc(t('cfg.default'));
    const source=t('cfg.source');
    deck.insertAdjacentHTML('beforeend',`<div class="cfg" role="dialog" aria-label="${esc(t('cfg.title'))}"><div class="cfg-box">
      <header><div><b>${esc(t('cfg.title'))}</b><small>${meta} · ${esc(t('cfg.agent'))}</small>${source?`<small class="cfg-src">${esc(source)}</small>`:''}</div>
        <button type="button" class="cfg-x" aria-label="${esc(t('close'))}"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg></button></header>
      <nav class="cfg-tabs">${UN.map((u,i)=>`<button type="button" data-tab="${u}" class="${i?'':'on'}" style="--c:${UNIT[u].c}"><i></i>${esc(u)}</button>`).join('')}<button type="button" data-tab="cmp">${esc(t('cfg.cmpTab'))}</button></nav>
      <div class="cfg-body">${UN.map(unitTab).join('')}${cmpTab}</div>
      <footer><span class="cfg-msg" id="cfg-msg"></span>${info.custom?`<button type="button" class="ghost" data-reset>${esc(t('cfg.reset'))}</button>`:''}<button type="button" class="ghost" data-cancel>${esc(t('cfg.cancel'))}</button><button type="button" class="save" data-save>${esc(t('cfg.save'))}</button></footer></div></div>`);
    const box=$('.cfg');
    const show=t=>{$$('.cfg-tabs button',box).forEach(b=>b.classList.toggle('on',b.dataset.tab===t));$$('.cfg-pane',box).forEach(p=>p.hidden=p.dataset.pane!==t)};
    show(UN[0]||'cmp');
    const shut=()=>box.remove();
    // Digitar no modal não pode virar comando de slide (setas, espaço, F, S…)
    box.addEventListener('keydown',e=>{e.stopPropagation();if(e.key==='Escape')shut()});
    const collect=()=>{const out={};$$('[data-p]',box).forEach(el=>{const path=el.dataset.p.split('.');let v=el.value;
        if(el.hasAttribute('data-lines'))v=v.split('\n').map(s=>s.trim()).filter(Boolean);else if(el.hasAttribute('data-csv'))v=v.split(',').map(s=>s.trim()).filter(Boolean);
        let o=out;path.forEach((k,i)=>{if(i===path.length-1){o[k]=v;return}const nextNum=/^\d+$/.test(path[i+1]);o[k]=o[k]||(nextNum&&k!=='etapas'?[]:{});o=o[k]})});
      // etapas vão por id (lista com id); prazos e comparativo por posição
      UN.forEach(u=>{if(out[u]?.etapas)out[u].etapas=Object.entries(out[u].etapas).map(([id,v])=>({id,...v}))});
      return out};
    const msg=t=>{$('#cfg-msg').textContent=t};
    const call=async(method,body)=>{if(window.__NEXXUS_FLOWS)throw new Error(t('cfg.preview'));const r=await fetch('/api/fluxos',{method,credentials:'same-origin',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
      if(!r.ok){let d='';try{d=(await r.json()).detail}catch(e){}throw new Error(d||'HTTP '+r.status)}return r.json()};
    box.addEventListener('click',async e=>{
      const tab=e.target.closest('[data-tab]');if(tab){show(tab.dataset.tab);return}
      if(e.target.closest('.cfg-x,[data-cancel]')){shut();return}
      const save=e.target.closest('[data-save]'),reset=e.target.closest('[data-reset]');if(!save&&!reset)return;
      if(reset&&!confirm(t('cfg.confirmReset')))return;
      $$('footer button',box).forEach(b=>b.disabled=true);msg(t(reset?'cfg.restoring':'cfg.saving'));
      try{await(reset?call('DELETE'):call('PUT',{flows:collect()}));send({type:'nexxus-flow-updated'});msg(t('cfg.saved'));
        try{sessionStorage.setItem('nexus.flow.restart',LANG)}catch(e){}  // recarrega já no idioma escolhido
        setTimeout(()=>location.reload(),500)}
      catch(err){msg(err.message);$$('footer button',box).forEach(b=>b.disabled=false)}});
  }

  /* ---------- animações próprias ---------- */
  const active=()=>$('.slide.is-active');
  // fundo: estrelas e nebulosas desenhadas uma vez só (sem animação contínua, para a troca de slides ficar leve)
  (function space(){const cv=$('#space'),ctx=cv.getContext('2d'),W=1920,H=1080;cv.width=W;cv.height=H;
    let seed=20261023;const rnd=()=>(seed=Math.imul(48271,seed)%2147483647)/2147483647;
    [[360,260,'#b5dc3c'],[1560,820,'#4cc9f0'],[1500,180,'#ff8a3d'],[300,900,'#e5484d']].forEach(([x,y,c])=>{const g=ctx.createRadialGradient(x,y,0,x,y,540);g.addColorStop(0,c+'22');g.addColorStop(1,c+'00');ctx.fillStyle=g;ctx.fillRect(x-540,y-540,1080,1080)});
    ctx.fillStyle='#dbe9ff';[[520,.6],[240,1],[90,1.6]].forEach(([n,s])=>{for(let i=0;i<n;i++){ctx.globalAlpha=rnd()*.6+.25;ctx.fillRect(rnd()*W,rnd()*H,s*(rnd()*.8+.6),s*(rnd()*.8+.6))}});
    ctx.globalAlpha=1})();


  // rota no mapa: origens acendem, navios saem de cada porto até Santos, a câmera aproxima do Brasil e o
  // caminhão leva a carga ao CD; o contador de dias acompanha cada trecho.
  const ease=x=>x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;
  function runMap(sl,u){
    const G=GEOMAP[u],legs=legsOf(u),svgs=$$('svg.map',sl),dayEl=$('.rt-n',sl);
    const feeds=$$('.rt.feed',sl),seas=$$('.rt.sea',sl),seaGlow=$$('.rt.sea-glow',sl),road=$('.br-layer .road',sl),roadGlow=$('.br-layer .road-glow',sl),air=$('.rt.air',sl);
    const ships=$$('.ship',sl),truck=$('.truck',sl),plane=$('.plane',sl),fill=$('.rt-fill',sl);
    // etapas da faixa: ordem dentro do momento da viagem em que acendem
    const cards=$$('.rt-step',sl),byPh={};cards.forEach(el=>{(byPh[el.dataset.ph]=byPh[el.dataset.ph]||[]).push(el)});
    const stripOrder=Object.entries(byPh).flatMap(([k,list])=>list.map((el,j)=>({el,k,j,n:list.length})));
    // rotas do mapa-múndi acompanham o zoom na espessura; a rodovia fica na camada do Brasil (tamanho de tela)
    const routes=[...feeds,...seas,...seaGlow,air].filter(Boolean),base=new Map([...routes,road,roadGlow].map(p=>[p,{L:p.getTotalLength(),w:parseFloat(getComputedStyle(p).strokeWidth)||2}]));
    const dash=(p,k)=>{const b=base.get(p);p.style.strokeDasharray=b.L;p.style.strokeDashoffset=b.L*(1-k)};
    let lastV='';
    const setView=v=>{const vb=v.map(f1).join(' ');if(vb===lastV)return;lastV=vb;svgs.forEach(s=>s.setAttribute('viewBox',vb));const s=v[2]/1920;routes.forEach(p=>{p.style.strokeWidth=base.get(p).w*s});sl.style.setProperty('--zs',s)};
    const lerpV=(a,b,k)=>a.map((x,i)=>x+(b[i]-x)*k);
    const at=(p,k)=>{const b=base.get(p),d=Math.max(0,Math.min(1,k))*b.L,q=p.getPointAtLength(d),r=p.getPointAtLength(Math.min(b.L,d+2));return [q.x,q.y,Math.atan2(r.y-q.y,r.x-q.x)*180/Math.PI]};
    const place=(g,p,k,scale=1,turn=false)=>{const[x,y,a]=at(p,k);g.setAttribute('transform',`translate(${f1(x)},${f1(y)}) scale(${scale})${turn?` rotate(${f1(a)})`:''}`)};
    const D={origins:.5+G.origins.length*.38,cpt:2.2,tt:5.2,zin:1.7,des:1.3,sefaz:1.3,road:2.4,zout:1.9};
    const order=['origins','cpt','tt','zin','des','sefaz','road','zout'],T={};let acc=.5;order.forEach(k=>{T[k]=[acc,acc+D[k]];acc+=D[k]});
    const cum={};let sum=0;legs.forEach(l=>{sum+=l.d;cum[l.k]=sum});const total=sum;
    let raf=0,t0=0;
    function reset(){lastV='';setView(VIEW_WORLD);sl.classList.remove('zoomed','done');[...routes,road,roadGlow].forEach(p=>dash(p,0));[...ships,truck,plane].filter(Boolean).forEach(g=>g.style.opacity=0);
      $$('.land.orig,.orig-hl path',sl).forEach(p=>p.classList.remove('lit'));cards.forEach(el=>el.classList.remove('on','done'));if(fill)fill.style.clipPath='inset(0 100% 0 0)';$$('.orig-mark,.rt-origins span,.chip-br',sl).forEach(e=>e.classList.remove('on'));$$('.rt-legs li',sl).forEach(li=>li.classList.remove('on','done'));dayEl.textContent='0'}
    function frame(now){
      if(!sl.classList.contains('is-active')){raf=0;return}
      raf=requestAnimationFrame(frame);const t=(now-t0)/1000,ph=k=>Math.max(0,Math.min(1,(t-T[k][0])/(T[k][1]-T[k][0])));
      // 1. países de origem, um a um
      G.origins.forEach((o,i)=>{if(t>T.origins[0]+i*.38){$$(`.land.orig[data-id="${o.id}"],.orig-hl path[data-id="${o.id}"]`,sl).forEach(p=>p.classList.add('lit'));$(`.orig-mark[data-o="${i}"]`,sl)?.classList.add('on');$(`.rt-origins span[data-o="${i}"]`,sl)?.classList.add('on')}});
      // 2. consolidação: rotas de alimentação até o transbordo
      feeds.forEach(p=>dash(p,ease(ph('cpt'))));
      // 3. navegação: navios de cada origem chegam juntos a Santos
      const k=ph('tt');seas.forEach((p,i)=>{dash(p,k);dash(seaGlow[i],k)});
      ships.forEach((g,i)=>{const show=t>=T.tt[0]&&t<T.zin[0]+.3;g.style.opacity=show?Math.min(1,(t-T.tt[0])*3):0;if(show)place(g,seas[i],k,VIEW_WORLD[2]/1920*1.1,false)});
      // 4. aproximação no Brasil, desembaraço, SEFAZ e caminhão até o(s) CD(s); 5. volta ao mapa todo
      const zi=ease(ph('zin')),zo=ease(ph('zout'));
      if(t<T.zout[0])setView(lerpV(VIEW_WORLD,VIEW_BR,zi));else setView(lerpV(VIEW_BR,VIEW_WORLD,zo));
      sl.classList.toggle('zoomed',t>=T.zin[0]+D.zin*.6&&t<T.zout[0]+D.zout*.3);
      $(`.chip-br[data-k="des"]`,sl).classList.toggle('on',t>=T.des[0]);$(`.chip-br[data-k="sefaz"]`,sl).classList.toggle('on',t>=T.sefaz[0]);$(`.chip-br[data-k="road"]`,sl).classList.toggle('on',t>=T.road[1]-.2);
      const kr=ease(ph('road'));dash(road,kr);dash(roadGlow,kr);
      if(truck){const show=t>=T.road[0]&&t<T.zout[0]+.2;truck.style.opacity=show?1:0;if(show)place(truck,road,kr)}
      if(air){const ka=ease(Math.max(0,Math.min(1,(t-T.zout[1])/2)));dash(air,ka);
        if(plane){const lp=t>T.zout[1]+2?((t-T.zout[1]-2)/7)%1:-1;plane.style.opacity=lp<0?0:lp<.08?lp/.08:lp>.92?(1-lp)/.08:1;if(lp>=0)place(plane,air,lp,VIEW_WORLD[2]/1920*1.15,true)}}
      // contador de dias e trechos
      const legOf={cpt:'cpt',tt:'tt',des:'des',sefaz:'sefaz',road:'road'};let day=0;
      legs.forEach((l,i)=>{const kk=ph(legOf[l.k]),prev=i?cum[legs[i-1].k]:0;if(kk>0)day=prev+(cum[l.k]-prev)*kk;
        const li=$(`.rt-legs li[data-leg="${l.k}"]`,sl);li.classList.toggle('on',kk>0&&kk<1);li.classList.toggle('done',kk>=1)});
      dayEl.textContent=Math.round(Math.min(total,day));
      // faixa das etapas: acende cada cartão quando a viagem chega nele; a linha de progresso acompanha
      let lit=0;stripOrder.forEach(({el,k,j,n})=>{const kk=ph(k),done=kk>=(j+1)/n-1e-6,on=!done&&kk>j/n;el.classList.toggle('done',done);el.classList.toggle('on',on);if(done)lit++;else if(on)lit+=.5});
      if(fill&&cards.length)fill.style.clipPath=`inset(0 ${f1(100-Math.min(100,lit/cards.length*100))}% 0 0)`;
      sl.classList.toggle('done',t>=T.zout[1]);
      if(t>T.zout[1]+.5&&!air){cancelAnimationFrame(raf);raf=0}  // sem animação contínua depois do fim (exceto o avião da Fisia)
    }
    return {start(){cancelAnimationFrame(raf);reset();t0=performance.now();raf=requestAnimationFrame(frame)}};
  }
  const MAPS={};
  deck.addEventListener('click',e=>{const b=e.target.closest('.rt-replay');if(b){const sl=b.closest('.slide');MAPS[sl.dataset.map]?.start()}});

  // ao entrar num slide: rota desenhada em sequência, navio e caminhão, contadores e anéis
  const RUN={};
  function enter(sl){
    if(sl.dataset.map){const m=sl.dataset.map;MAPS[m]=MAPS[m]||runMap(sl,m);MAPS[m].start()}
    const u=sl.dataset.journey;
    if(u&&GEO[u]){const G=GEO[u];
      // O caminho é traçado a velocidade constante, trecho a trecho; cada etapa acende quando a linha chega nela,
      // e os prazos e a faixa de baixo aparecem quando a linha alcança as etapas deles.
      const SPEED=1150,START=.45,draws=$$('.draw',sl),bases=$$('.base',sl),flows=$$('.flow',sl),arrive=[START];let t=START;
      draws.forEach((p,i)=>{const L=p.getTotalLength(),d=L/SPEED,start=t,pair=[p,bases[i]].filter(Boolean);t+=d;arrive.push(t);
        pair.forEach(el=>{el.style.transition='none';el.style.strokeDasharray=L;el.style.strokeDashoffset=L});
        if(flows[i]){flows[i].style.transition='none';flows[i].style.opacity=0}
        requestAnimationFrame(()=>requestAnimationFrame(()=>{pair.forEach(el=>{el.style.transition=`stroke-dashoffset ${d}s linear ${start}s`;el.style.strokeDashoffset=0});
          if(flows[i]){flows[i].style.transition=`opacity .5s ease ${start+d}s`;flows[i].style.opacity=''}}))});
      const restart=(el,delay)=>{el.style.animation='none';void el.getBoundingClientRect();el.style.animation='';el.style.animationDelay=delay+'s'};
      $$('.node',sl).forEach((n,i)=>restart(n,Math.max(0,arrive[i]-.18)));
      $$('.bracket',sl).forEach(b=>restart(b,(arrive[Number(b.dataset.ate)]||t)+.1));
      $$('.lane,.lane-svg',sl).forEach(l=>restart(l,arrive[Number(l.dataset.at)]||0));
      $$('.sea',sl).forEach(s=>restart(s,arrive[G.ship[0]]||0));
      $$('.journey-foot',sl).forEach(f=>restart(f,t+.2));
      const along=(range,dur,el)=>{if(!range||!el)return null;const ps=$$('.draw',sl).filter(p=>{const i=Number(p.dataset.seg);return i>=range[0]&&i<range[1]});
        const lens=ps.map(p=>p.getTotalLength()),total=lens.reduce((a,b)=>a+b,0);return {el,ps,lens,total,dur}};
      const movers=[along(G.ship,9,$(`#ship-${u}`,sl)),along(G.truck,5.5,$(`#truck-${u}`,sl))].filter(m=>m&&m.total);
      const t0=performance.now()+(t+.4)*1000;  // veículos só depois do caminho completo
      cancelAnimationFrame(RUN[u]);
      (function tick(now){if(!sl.classList.contains('is-active'))return;RUN[u]=requestAnimationFrame(tick);if(now<t0)return;
        movers.forEach(m=>{const p=((now-t0)/1000%m.dur)/m.dur;let d=p*m.total,k=0;while(k<m.lens.length-1&&d>m.lens[k]){d-=m.lens[k];k++}
          const pt=m.ps[k].getPointAtLength(Math.min(d,m.lens[k]));m.el.setAttribute('transform',`translate(${pt.x},${pt.y})`);m.el.classList.add('on');m.el.style.opacity=p<.06?p/.06:p>.94?(1-p)/.06:1})})(performance.now())}
    $$('.cnt',sl).forEach(el=>{const to=Number(el.dataset.to)||0,s=performance.now();(function step(n){const p=Math.min(1,(n-s)/1300),e=1-Math.pow(1-p,3);el.textContent=Math.round(to*e);if(p<1)requestAnimationFrame(step)})(s)});
    $$('.ring .val',sl).forEach(c=>{c.style.transition='none';c.style.strokeDashoffset=c.getAttribute('stroke-dasharray');requestAnimationFrame(()=>requestAnimationFrame(()=>{c.style.transition='';c.style.strokeDashoffset=c.dataset.off}))});
    const n=$$('.slide').indexOf(sl)+1;$$('.jumps button').forEach(b=>{const g=Number(b.dataset.go),next=JUMPS.map(j=>j[1]).filter(x=>x>g).sort((a,b)=>a-b)[0]||99;b.classList.toggle('on',n>=g&&n<next)});
    closeDrawer();
  }
  // só a passagem de inativo para ativo conta (as animações mexem em outras classes do próprio slide)
  $$('#deck > .slide').forEach(sl=>{let was=false;new MutationObserver(()=>{const now=sl.classList.contains('is-active');if(now&&!was)enter(sl);was=now})
    .observe(sl,{attributes:true,attributeFilter:['class']})});

  /* ---------- motor do html-ppt-skill ---------- */
  // na prévia autocontida os scripts vêm embutidos (<script type="text/plain" id="inl-…">)
  const load=src=>new Promise(r=>{const s=document.createElement('script'),inl=document.getElementById('inl-'+src.replace(/\W/g,'-'));
    if(inl){s.textContent=inl.textContent;document.body.appendChild(s);r();return}
    s.src=src+Q;s.onload=s.onerror=r;document.body.appendChild(s)});
  await load('runtime.js');await load('fx-runtime.js');
  const first=active();if(first)enter(first);
})();
