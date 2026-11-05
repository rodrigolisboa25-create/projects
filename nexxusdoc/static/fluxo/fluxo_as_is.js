/* Fluxo As Is do NexxusDoc (03/11/2026).
   Fluxograma do processo montado pelo agente a partir do procedimento (só POPs criados ou revisados no NexxusDoc):
   raias por papel, etapas, decisões, retornos (retrabalho) e pontos de melhoria. Abre sozinho depois de gerar ou
   revisar um POP e pelo botão "Fluxo As Is" em Documentos. Uso: window.nexusFlow.open(id, {fresh:true}). */
window.nexusFlow=(()=>{
'use strict';
const TASK_W=224,TASK_H=112,GATE=60,EVENT=46,COLW=272,ROWH=216,LEFT=0,PADX=34,LANE_MIN=1,HEADW=156;
const LANE_TYPES={
  interno:{label:'Equipe interna',c:'#1f7a45',s:'#eaf4ec',icon:'<circle cx="12" cy="8" r="3.5"/><path d="M5 20c.8-3.6 3.6-5.5 7-5.5s6.2 1.9 7 5.5"/>'},
  terceiro:{label:'Prestador terceirizado',c:'#b86e00',s:'#fff3df',icon:'<path d="M3 21h18M5 21V9l7-4 7 4v12M9 21v-5h6v5"/>'},
  sistema:{label:'Sistema ou robô',c:'#4c55c9',s:'#eef0ff',icon:'<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>'},
  externo:{label:'Externo',c:'#5e6b73',s:'#eef1f3',icon:'<circle cx="12" cy="12" r="8"/><path d="M4 12h16M12 4c2.5 2.6 2.5 13.4 0 16M12 4c-2.5 2.6-2.5 13.4 0 16"/>'}};
const CATS={
  automacao:{label:'Automação',c:'#1f8f55',icon:'<path d="M13 3 5 14h6l-1 7 8-11h-6z"/>'},
  desperdicio:{label:'Desperdício Lean',c:'#c77700',icon:'<circle cx="12" cy="12" r="8"/><path d="M8.5 12h7"/>'},
  risco:{label:'Risco',c:'#d64545',icon:'<path d="M12 4 3 19h18z"/><path d="M12 10v4M12 16.6v.4"/>'},
  controle:{label:'Controle',c:'#2f6fd6',icon:'<path d="M12 3 5 6v5.5c0 4.2 3 7.8 7 8.5 4-.7 7-4.3 7-8.5V6z"/><path d="m9 12 2 2 4-4"/>'},
  gargalo:{label:'Gargalo',c:'#8a4fd1',icon:'<path d="M4 5h16l-6 7v6l-4 2v-8z"/>'},
  padronizacao:{label:'Padronização',c:'#0e8c9a',icon:'<path d="M10 6h10M10 12h10M10 18h10"/><path d="m3.5 6 1.2 1.2L7 5M3.5 12l1.2 1.2L7 11M3.5 18l1.2 1.2L7 17"/>'}};
const WASTES={espera:'Espera',defeitos:'Defeitos e retrabalho',processamento_extra:'Processamento extra',movimentacao:'Movimentação',
  transporte:'Transporte',estoque:'Estoque',superproducao:'Superprodução',talento:'Talento não utilizado'};
const LEVEL={alto:'Alto',medio:'Médio',baixo:'Baixo'};
const PRIO=[['Ganho rápido','p0'],['Estratégico','p1'],['Melhoria pontual','p2'],['Baixa prioridade','p3']];
const I={
  flow:'<rect x="3" y="3.5" width="7" height="5.5" rx="1.6"/><rect x="14" y="15" width="7" height="5.5" rx="1.6"/><path d="M6.5 9v3.2a2.3 2.3 0 0 0 2.3 2.3H14"/><circle cx="17.5" cy="6.3" r="2.6"/><path d="M10 6.3h4.9"/>',
  close:'<path d="M6 6l12 12M18 6 6 18"/>',bulb:'<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.7.6 1.1 1.3 1.1 2.2h5c0-.9.4-1.6 1.1-2.2A6 6 0 0 0 12 3z"/>',
  download:'<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',redo:'<path d="M20 12a8 8 0 1 1-2.4-5.7M20 4v5h-5"/>',
  grid:'<rect x="4" y="4" width="6.5" height="6.5" rx="1.4"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.4"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.4"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.4"/>',
  plus:'<path d="M12 6v12M6 12h12"/>',minus:'<path d="M6 12h12"/>',fit:'<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
  hand:'<path d="M8 13V6.5a1.5 1.5 0 0 1 3 0V12M11 11V5a1.5 1.5 0 0 1 3 0v6M14 11V6.5a1.5 1.5 0 0 1 3 0V14a6 6 0 0 1-6 6h-.6a5 5 0 0 1-4-2l-2.5-3.4a1.5 1.5 0 0 1 2.3-1.9L8 14"/>',
  clock:'<circle cx="12" cy="12" r="8"/><path d="M12 8v4l2.8 1.8"/>',building:'<path d="M3 21h18M5 21V9l7-4 7 4v12M9 21v-5h6v5"/>',
  monitor:'<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',stack:'<rect x="4" y="4" width="16" height="16" rx="2.5"/><path d="M12 8.5v7M8.5 12h7"/>',
  task:'<rect x="4" y="5" width="16" height="14" rx="3"/><path d="M8 10h8M8 14h5"/>',doc:'<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5M10 13h6M10 17h6"/>',
  rule:'<path d="M12 4v16M7 20h10M5 8h14M7 8l-3 6a3 3 0 0 0 6 0zM17 8l-3 6a3 3 0 0 0 6 0z"/>',shield:CATS.controle.icon,
  inp:'<path d="M3 12h11M10 8l4 4-4 4M15 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4"/>',out:'<path d="M10 12h11M17 8l4 4-4 4M9 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4"/>',
  sys:'<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',how:'<path d="M4 6h16M4 12h10M4 18h7"/>',
  left:'<path d="m15 6-6 6 6 6"/>',right:'<path d="m9 6 6 6-6 6"/>',img:'<rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="9" cy="10" r="2"/><path d="m4 18 5-5 4 4 3-3 4 4"/>',
  bpmn:'<rect x="3" y="8" width="7" height="8" rx="1.5"/><path d="M10 12h4"/><path d="m17 8 4 4-4 4-4-4z"/>',pdf:'<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/><path d="M9.5 16.5v-4h1.3a1.3 1.3 0 0 1 0 2.6H9.5M14 12.5v4"/>',
  move:'<path d="M12 3v18M3 12h18M12 3l-3 3M12 3l3 3M12 21l-3-3M12 21l3-3M3 12l3-3M3 12l3 3M21 12l-3-3M21 12l-3 3"/>',
  branch:'<path d="M12 5v6M12 11l-5 6M12 11l5 6"/>',edit:'<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',play:'<path d="M9 6.5v11l9-5.5z"/>',stop:'<rect x="6" y="6" width="12" height="12" rx="2"/>'};
const svg=(p,cls='')=>`<svg viewBox="0 0 24 24" class="${cls}" aria-hidden="true">${p}</svg>`;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const cap=(el,e)=>{try{el.setPointerCapture(e.pointerId)}catch{}};
const STATIC=/[?&]estatico=1/.test(location.search);
const reduce=()=>STATIC||window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

async function req(url,options={}){
  let r;
  try{r=await fetch(url,{credentials:'same-origin',...options})}
  catch{throw Error('O servidor local do NexxusDoc não está respondendo. Abra o NexxusDoc de novo pelo atalho.')}
  let data=null;try{data=await r.json()}catch{}
  if(!r.ok){const d=data?.detail;throw Error(typeof d==='string'?d:(d?.message||`Erro ${r.status} no servidor local.`))}
  return data;
}
const send=(url,method,body)=>req(url,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});

/* Estado */
const S={id:null,data:null,flow:null,geo:null,custom:{},k:1,tx:0,ty:0,sel:null,focus:null,laneFocus:null,showImp:true,
  impOpen:false,catOff:new Set(),poll:0,timer:0,fresh:false,root:null,dirty:0,keyHandler:null,openSeq:0};

function priority(m){
  if(m.impacto==='alto')return m.esforco==='alto'?1:0;
  return m.esforco==='baixo'?2:3;
}
const sizeOf=n=>n.tipo==='decisao'?{w:GATE,h:GATE}:(n.tipo==='inicio'||n.tipo==='fim')?{w:EVENT,h:EVENT}:{w:TASK_W,h:TASK_H};

/* Layout: camada (coluna) pelo caminho mais longo, ignorando os retornos; raia pela linha; empilha na mesma célula. */
function layout(flow){
  const nodes=flow.etapas,edges=flow.ligacoes,index=new Map(nodes.map((n,i)=>[n.id,i]));
  const out=new Map(nodes.map(n=>[n.id,[]]));edges.forEach(e=>out.get(e.de)?.push(e));
  const back=new Set(),mark=new Map();
  const start=nodes.find(n=>n.tipo==='inicio')||nodes[0];
  const visit=id=>{mark.set(id,1);for(const e of out.get(id)||[]){const m=mark.get(e.para);if(m===1)back.add(e);else if(!m)visit(e.para)}mark.set(id,2)};
  [start,...nodes].forEach(n=>{if(!mark.get(n.id))visit(n.id)});
  const rank=new Map(nodes.map(n=>[n.id,0])),indeg=new Map(nodes.map(n=>[n.id,0]));
  edges.forEach(e=>{if(!back.has(e))indeg.set(e.para,indeg.get(e.para)+1)});
  const queue=nodes.filter(n=>!indeg.get(n.id)).map(n=>n.id);
  while(queue.length){const id=queue.shift();for(const e of out.get(id)){if(back.has(e))continue;
    rank.set(e.para,Math.max(rank.get(e.para),rank.get(id)+1));indeg.set(e.para,indeg.get(e.para)-1);if(!indeg.get(e.para))queue.push(e.para)}}
  const lanes=flow.raias.length?flow.raias:[{id:'_',nome:'Processo',tipo:'interno'}];
  const laneIx=new Map(lanes.map((l,i)=>[l.id,i]));
  const slot=new Map(),used=new Map();
  nodes.slice().sort((a,b)=>rank.get(a.id)-rank.get(b.id)||index.get(a.id)-index.get(b.id)).forEach(n=>{
    const key=`${laneIx.get(n.raia)??0}|${rank.get(n.id)}`,s=used.get(key)||0;used.set(key,s+1);slot.set(n.id,s)});
  let y=0;const laneBox=lanes.map((l,i)=>{const rows=Math.max(LANE_MIN,...nodes.filter(n=>(laneIx.get(n.raia)??0)===i).map(n=>slot.get(n.id)+1));
    const box={...l,y,h:rows*ROWH};y+=box.h;return box});
  const maxRank=Math.max(0,...rank.values());
  // Vão entre colunas sob medida: a ligação com rótulo que sai de uma etapa ganha espaço para o texto caber entre os
  // cards (as saídas da decisão já têm folga dentro da coluna dela).
  const kindOf=new Map(nodes.map(n=>[n.id,n.tipo])),extra=new Map();
  edges.forEach(e=>{if(!e.rotulo||back.has(e)||kindOf.get(e.de)==='decisao')return;
    const r=rank.get(e.de),need=labelWidth(e.rotulo)+44-(COLW-TASK_W);
    if(need>0)extra.set(r,Math.max(extra.get(r)||0,need))});
  const colX=[];let acc=LEFT+PADX;
  for(let r=0;r<=maxRank;r++){colX[r]=acc+COLW/2;acc+=COLW+(extra.get(r)||0)}
  const auto=new Map(nodes.map(n=>{const lb=laneBox[laneIx.get(n.raia)??0];
    return [n.id,{x:colX[rank.get(n.id)],y:lb.y+slot.get(n.id)*ROWH+ROWH/2}]}));
  // Numeração das etapas na ordem do fluxo (sem eventos e decisões).
  const seq=nodes.filter(n=>!['inicio','fim','decisao'].includes(n.tipo)).sort((a,b)=>rank.get(a.id)-rank.get(b.id)||index.get(a.id)-index.get(b.id));
  const num=new Map(seq.map((n,i)=>[n.id,i+1]));
  const order=nodes.slice().sort((a,b)=>rank.get(a.id)-rank.get(b.id)||(laneIx.get(a.raia)??0)-(laneIx.get(b.raia)??0)||index.get(a.id)-index.get(b.id));
  return {auto,back,rank,laneBox,laneIx,num,order,width:acc+PADX,height:y};
}
let measureCtx=null;
function labelWidth(text){
  measureCtx??=document.createElement('canvas').getContext('2d');measureCtx.font='600 11.5px "Segoe UI", Arial, sans-serif';
  return Math.ceil(measureCtx.measureText(String(text||'')).width)+20;
}
// Saídas de uma decisão: cada uma por um lado do losango (a mais alinhada pela direita, as de cima por cima, as de
// baixo por baixo), para as linhas e os rótulos Sim/Não nunca saírem juntos.
// Escolhe, entre os lados livres, o primeiro (na ordem de preferência) cujo traçado não atravessa nenhuma etapa.
function decisionSides(id){
  S.sides??=new Map();if(S.sides.has(id))return S.sides.get(id);
  const a=box(S.byId.get(id)),sides=new Map(),used=new Set();
  const outs=S.flow.ligacoes.filter(e=>e.de===id&&!S.geo.back.has(e)&&box(S.byId.get(e.para)).l>=a.r-4)
    .map(e=>({e,dy:box(S.byId.get(e.para)).y-a.y})).sort((p,q)=>Math.abs(p.dy)-Math.abs(q.dy));
  for(const {e,dy} of outs){const pref=Math.abs(dy)<2?['r','b','t']:dy<0?['t','r','b']:['b','r','t'];
    const free=pref.filter(s=>!used.has(s));
    const side=free.find(s=>forward(e,s).ok)||free[0]||pref[0];used.add(side);sides.set(e,side)}
  sides.used=used;S.sides.set(id,sides);return sides;
}
function pos(id){return S.custom[id]?{x:S.custom[id][0],y:S.custom[id][1]}:S.geo.auto.get(id)}
function box(n){const p=pos(n.id),s=sizeOf(n);return {x:p.x,y:p.y,w:s.w,h:s.h,l:p.x-s.w/2,r:p.x+s.w/2,t:p.y-s.h/2,b:p.y+s.h/2,kind:n.tipo}}
function obstacle(n){const b=box(n);
  if(n.tipo==='decisao')return [b,{l:b.x-158,r:b.x-30,t:b.t-48,b:b.t+12}];
  if(n.tipo==='inicio'||n.tipo==='fim')return [b,{l:b.x-85,r:b.x+85,t:b.b+2,b:b.b+40}];
  return [b]}

/* Ligações ortogonais que evitam atravessar as etapas. */
function hits(points,skip){
  // A origem e o destino não contam como obstáculo, mas o texto do destino (pergunta da decisão, nome do evento) conta:
  // a linha que chega não pode passar por cima dele.
  const obs=S.flow.etapas.flatMap(n=>!skip.includes(n.id)?obstacle(n):n.id===skip[1]?obstacle(n).slice(1):[]);
  for(let i=1;i<points.length;i++){const [x1,y1]=points[i-1],[x2,y2]=points[i];
    const l=Math.min(x1,x2),r=Math.max(x1,x2),t=Math.min(y1,y2),b=Math.max(y1,y2);
    for(const o of obs)if(r>o.l-6&&l<o.r+6&&b>o.t-6&&t<o.b+6)return true}
  return false}
// Traçado de ida por um lado ('r' direita, 't' cima, 'b' baixo); ok = não atravessa nenhuma etapa.
function forward(e,side){
  const a=box(S.byId.get(e.de)),c=box(S.byId.get(e.para)),skip=[e.de,e.para];
  const sx=a.kind==='decisao'?a.x+GATE/2:a.r,sy=a.y,ex=c.kind==='decisao'?c.x-GATE/2:c.l,ey=c.y;
  const pick=list=>{const good=list.find(p=>!hits(p,skip));return {pts:good||list[list.length-1],ok:!!good}};
  if(side!=='r'){
    // Saída por cima ou por baixo do losango: sobe/desce até a linha do destino ou corre no corredor entre as linhas,
    // por fora de todos os cards da linha da decisão (não rente à borda deles).
    const vy=side==='t'?a.t:a.b,half=TASK_H/2;
    const yc=side==='t'?Math.min(a.y-half,c.t)-28:Math.max(a.y+half,c.b)+28;
    const opts=[];
    if(side==='t'?ey<a.t-8:ey>a.b+8)opts.push([[a.x,vy],[a.x,ey],[ex,ey]]);
    opts.push([[a.x,vy],[a.x,yc],[ex-24,yc],[ex-24,ey],[ex,ey]]);
    return pick(opts);
  }
  const cands=[];
  if(Math.abs(sy-ey)<1.5)cands.push([[sx,sy],[ex,ey]]);
  for(const mx of [ex-24,(sx+ex)/2,sx+24])if(mx>sx+8&&mx<ex-8)cands.push([[sx,sy],[mx,sy],[mx,ey],[ex,ey]]);
  for(const yc of [Math.min(a.t,c.t)-26,Math.max(a.b,c.b)+26])cands.push([[sx,sy],[sx+20,sy],[sx+20,yc],[ex-20,yc],[ex-20,ey],[ex,ey]]);
  // Decisão de destino em outra linha: pode entrar pelo topo (vindo de cima) ou pela base (vindo de baixo), quando a
  // pergunta ocupa o vão à esquerda do losango e esse lado não é usado por uma saída dela.
  if(c.kind==='decisao'&&Math.abs(sy-ey)>=1.5){const used=decisionSides(e.para).used,top=sy<ey;
    if(!used.has(top?'t':'b'))cands.push([[sx,sy],[c.x,sy],[c.x,top?c.t:c.b]])}
  const good=cands.find(p=>!hits(p,skip));
  return {pts:good||(Math.abs(sy-ey)<1.5?cands[0]:cands[1]||cands[0]),ok:!!good};
}
function route(e,backIx){
  const byId=S.byId,a=box(byId.get(e.de)),c=box(byId.get(e.para)),skip=[e.de,e.para];
  const isBack=S.geo.back.has(e)||c.l<a.r-4;
  if(!isBack)return forward(e,a.kind==='decisao'?decisionSides(e.de).get(e)||'r':'r').pts;
  // Retorno (retrabalho): sai por cima ou por baixo da etapa, corre no corredor entre as linhas e entra na etapa
  // refeita por baixo/cima; se bater em alguma etapa, entra pela esquerda, pelo corredor entre as colunas.
  const off=8*(backIx%4);
  let up=c.y<a.y-2,down=c.y>a.y+2;
  const sx=a.x+(a.kind==='tarefa'||a.kind==='espera'||a.kind==='subprocesso'?20:0)+off;
  let ey=up?c.b:down?c.t:c.b,sy=up?a.t:a.b,yc=up?a.t-22-off:Math.max(a.b,down?a.b:c.b)+24+off;
  if(a.kind==='decisao'){
    // Decisão: o retorno sai pelo lado oposto às outras saídas (os rótulos não se sobrepõem) e passa por fora.
    const used=decisionSides(e.de).used;
    const below=used.has('b')&&!used.has('t')||used.has('b')&&used.has('t')&&c.y<a.y;
    if(below){sy=a.t;yc=Math.min(a.t-22,c.t-24)-off;ey=c.t}else{sy=a.b;yc=Math.max(a.b+22,c.b+24)+off;ey=c.b}
  }
  const xs=c.kind==='decisao'?[c.x]:[c.x-20-off,c.l+18,c.r-18];
  const cands=xs.map(tx=>[[sx,sy],[sx,yc],[tx,yc],[tx,ey]]);
  const gx=c.l-22-off;cands.push([[sx,sy],[sx,yc],[gx,yc],[gx,c.y],[c.kind==='decisao'?c.x-GATE/2:c.l,c.y]]);
  return cands.find(p=>!hits(p,skip))||cands[0];
}
function pathD(pts){
  const p=pts.filter((q,i)=>!i||q[0]!==pts[i-1][0]||q[1]!==pts[i-1][1]);
  let d=`M${p[0][0]},${p[0][1]}`;
  for(let i=1;i<p.length-1;i++){const [x0,y0]=p[i-1],[x1,y1]=p[i],[x2,y2]=p[i+1];
    const r=Math.min(11,Math.hypot(x1-x0,y1-y0)/2,Math.hypot(x2-x1,y2-y1)/2);
    d+=` L${x1-Math.sign(x1-x0)*r},${y1-Math.sign(y1-y0)*r} Q${x1},${y1} ${x1+Math.sign(x2-x1)*r},${y1+Math.sign(y2-y1)*r}`}
  const z=p[p.length-1];return d+` L${z[0]},${z[1]}`}
function plen(pts){let s=0;for(let i=1;i<pts.length;i++)s+=Math.hypot(pts[i][0]-pts[i-1][0],pts[i][1]-pts[i-1][1]);return Math.ceil(s)}
// Rótulo da ligação: na saída da decisão, logo depois do losango; nas demais, no primeiro trecho horizontal onde o
// texto cabe (o vão logo depois da etapa de origem), e não colado na etapa de destino.
function labelAt(pts,fromDecision,width=60){
  if(fromDecision){const [x1,y1]=pts[0],[x2,y2]=pts[1],d=Math.hypot(x2-x1,y2-y1)||1,horiz=Math.abs(y2-y1)<1;
    const t=Math.min(horiz?width/2+10:26,d/2);return [x1+(x2-x1)/d*t,y1+(y2-y1)/d*t]}
  const seg=[];for(let i=1;i<pts.length;i++){const [x1,y1]=pts[i-1],[x2,y2]=pts[i];seg.push({i,len:Math.hypot(x2-x1,y2-y1),horiz:Math.abs(y2-y1)<1})}
  const pick=seg.find(s=>s.horiz&&s.len>=width+8)||seg.filter(s=>s.horiz).sort((p,q)=>q.len-p.len)[0]||seg.sort((p,q)=>q.len-p.len)[0];
  return [(pts[pick.i][0]+pts[pick.i-1][0])/2,(pts[pick.i][1]+pts[pick.i-1][1])/2]}

/* Montagem do modal */
function ensureRoot(){
  if(S.root)return S.root;
  const root=document.createElement('div');root.className='fx-root';root.hidden=true;
  root.innerHTML=`<div class="fx-backdrop"></div><div class="fx-dialog" role="dialog" aria-modal="true" aria-label="Fluxo As Is do processo">
    <header class="fx-head"><div class="fx-mark">${svg(I.flow)}</div><div class="fx-titles"><div class="fx-kicker">Fluxo As Is <span class="fx-code" id="fx-code" hidden></span></div>
      <h2 class="fx-title" id="fx-title">Carregando…</h2><div class="fx-sub" id="fx-sub"></div></div>
      <div class="fx-stats" id="fx-stats"></div>
      <div class="fx-actions" id="fx-actions"><button class="fx-btn on" type="button" id="fx-imp-btn" title="Pontos de melhoria do processo">${svg(I.bulb)}<span class="fx-lbl">Melhorias</span><span class="fx-count" id="fx-imp-n">0</span></button>
        <div class="fx-menu"><button class="fx-btn" type="button" id="fx-dl-btn" aria-haspopup="menu" aria-expanded="false">${svg(I.download)}<span class="fx-lbl">Baixar</span></button>
          <div class="fx-menu-list" id="fx-dl-menu" role="menu" hidden>
            <button type="button" role="menuitem" data-dl="png">${svg(I.img)}<span><b>Imagem (PNG)</b><small>Para e-mail, apresentação ou o Drive</small></span></button>
            <button type="button" role="menuitem" data-dl="bpmn">${svg(I.bpmn)}<span><b>BPMN 2.0 (.bpmn)</b><small>Abre no Bizagi, no Visio e em outras ferramentas de processos</small></span></button>
            <button type="button" role="menuitem" data-dl="pdf">${svg(I.pdf)}<span><b>Procedimento (PDF)</b><small>O documento de onde o fluxo veio</small></span></button></div></div>
        <button class="fx-icon boxed" type="button" id="fx-move" hidden aria-pressed="false" title="Mover etapas: liga e desliga o modo de arrastar as etapas (fora dele, arrastar move a tela)" aria-label="Mover etapas">${svg(I.move)}</button>
        <button class="fx-icon boxed" type="button" id="fx-reset" hidden title="Reorganizar: voltar à arrumação automática das etapas" aria-label="Reorganizar">${svg(I.grid)}</button>
        <button class="fx-icon boxed" type="button" id="fx-redo" hidden title="Refazer: montar o fluxo de novo a partir do documento" aria-label="Refazer o fluxo">${svg(I.redo)}</button>
        <button class="fx-icon" type="button" id="fx-close" aria-label="Fechar">${svg(I.close)}</button></div></header>
    <div class="fx-body" id="fx-body"><div class="fx-view" id="fx-view"><div class="fx-world" id="fx-world"></div></div><div class="fx-heads" id="fx-heads"></div>
      <div class="fx-legend" id="fx-legend"></div>
      <div class="fx-dock"><canvas class="fx-mini" id="fx-mini" width="424" height="240" aria-label="Mapa do fluxo"></canvas>
        <div class="fx-zoom"><button class="fx-icon" type="button" id="fx-zout" aria-label="Afastar">${svg(I.minus)}</button><span id="fx-zl">100%</span>
        <button class="fx-icon" type="button" id="fx-zin" aria-label="Aproximar">${svg(I.plus)}</button><button class="fx-icon" type="button" id="fx-zfit" aria-label="Ver o fluxo inteiro">${svg(I.fit)}</button></div></div>
      <div class="fx-hint" id="fx-hint"></div>
      <aside class="fx-panel left" id="fx-imp" aria-label="Pontos de melhoria"></aside>
      <aside class="fx-panel right" id="fx-det" aria-label="Detalhes da etapa"></aside>
      <div class="fx-build" id="fx-build" hidden></div></div></div>`;
  document.body.appendChild(root);S.root=root;
  const $=id=>root.querySelector('#'+id);
  root.querySelector('.fx-backdrop').addEventListener('click',close);
  $('fx-close').addEventListener('click',close);
  $('fx-imp-btn').addEventListener('click',()=>toggleImp());
  $('fx-dl-btn').addEventListener('click',e=>{e.stopPropagation();const m=$('fx-dl-menu');m.hidden=!m.hidden;$('fx-dl-btn').setAttribute('aria-expanded',String(!m.hidden))});
  root.addEventListener('click',e=>{if(!e.target.closest('.fx-menu'))$('fx-dl-menu').hidden=true});
  $('fx-dl-menu').addEventListener('click',e=>{const b=e.target.closest('[data-dl]');if(!b)return;$('fx-dl-menu').hidden=true;
    if(b.dataset.dl==='png')exportPng();else if(b.dataset.dl==='bpmn')exportBpmn();else window.open(S.data.documento.pdf_url,'_blank','noopener')});
  $('fx-reset').addEventListener('click',resetLayout);
  $('fx-move').addEventListener('click',()=>toggleArrange());
  $('fx-redo').addEventListener('click',redo);
  $('fx-zin').addEventListener('click',()=>zoomBy(1.2));$('fx-zout').addEventListener('click',()=>zoomBy(1/1.2));$('fx-zfit').addEventListener('click',()=>fit(true));
  bindView();bindMini();
  window.addEventListener('resize',()=>{if(!root.hidden&&S.flow){applyView();drawMini()}});
  return root;
}
const R=id=>S.root.querySelector('#'+id);

async function open(id,opts={}){
  ensureRoot();const seq=++S.openSeq;
  Object.assign(S,{id,data:null,flow:null,geo:null,custom:{},sel:null,focus:null,laneFocus:null,impOpen:false,fresh:!!opts.fresh,
    arrange:false,pan:null,nodeDrag:null});
  S.catOff.clear();clearTimeout(S.poll);
  S.root.hidden=false;document.documentElement.style.overflow='hidden';
  R('fx-title').textContent='Carregando…';R('fx-sub').textContent='';R('fx-stats').innerHTML='';R('fx-code').hidden=true;
  R('fx-world').innerHTML='';R('fx-heads').innerHTML='';R('fx-det').classList.remove('open');R('fx-imp').classList.remove('open');
  R('fx-actions').style.visibility='hidden';R('fx-legend').hidden=true;
  S.keyHandler=e=>{if(e.key!=='Escape')return;e.stopPropagation();e.preventDefault();
    if(!R('fx-dl-menu').hidden){R('fx-dl-menu').hidden=true;return}
    if(S.focus){setFocus(null);return}if(R('fx-det').classList.contains('open')){select(null);return}
    if(S.impOpen){toggleImp(false);return}close()};
  document.addEventListener('keydown',S.keyHandler,true);
  building({decorrido:0,esperado:50});
  try{
    let data=await req(`/api/documents/${encodeURIComponent(id)}/fluxo`);if(seq!==S.openSeq)return;
    if(data.status==='ausente'||data.status==='desatualizado'||data.status==='erro'){
      await send(`/api/documents/${encodeURIComponent(id)}/fluxo/gerar`,'POST',{});data={...data,status:'gerando',decorrido:0}}
    handle(data,seq);
  }catch(err){showError(err.message,seq)}
}
function handle(data,seq){
  if(seq!==S.openSeq||S.root.hidden)return;
  S.data=data;header(data);
  if(data.status==='gerando'){S.wasBuilding=true;building(data);S.poll=setTimeout(()=>poll(seq),1500);return}
  if(data.status==='erro'){showError(data.erro||'Não foi possível montar o fluxo.',seq);return}
  if(data.fluxo){
    render(data);
    // Acabou de ficar pronto: avisa a página (o botão em Documentos ganha o check verde).
    if(S.wasBuilding&&data.status==='pronto'){S.wasBuilding=false;window.dispatchEvent(new CustomEvent('nexus-flow-pronto',{detail:{id:S.id}}))}
  }
}
async function poll(seq){
  try{handle(await req(`/api/documents/${encodeURIComponent(S.id)}/fluxo`),seq)}
  catch(err){showError(err.message,seq)}
}
function close(){
  if(!S.root||S.root.hidden)return;
  S.openSeq++;clearTimeout(S.poll);clearInterval(S.timer);
  if(S.dirty){clearTimeout(S.dirty);S.dirty=0;saveLayout()}
  S.root.hidden=true;document.documentElement.style.overflow='';
  document.removeEventListener('keydown',S.keyHandler,true);
}

/* Cabeçalho e números */
function header(data){
  const d=data.documento||{},f=data.fluxo;
  R('fx-title').textContent=f?.titulo||d.processo||d.titulo||'Fluxo As Is';
  R('fx-code').textContent=d.codigo||'';R('fx-code').hidden=!d.codigo;
  const when=data.gerado_em?new Date(data.gerado_em).toLocaleDateString('pt-BR'):'';
  R('fx-sub').textContent=[d.area,(d.unidades||[]).join(' e '),d.versao?`versão ${d.versao}`:'',d.status_label,
    when?`fluxo montado em ${when}${data.gerado_por?' por '+data.gerado_por:''}`:''].filter(Boolean).join(' · ');
  if(!f){R('fx-stats').innerHTML='';return}
  const tasks=f.etapas.filter(n=>!['inicio','fim','decisao'].includes(n.tipo));
  const systems=new Set(f.etapas.flatMap(n=>n.sistemas||[]).map(s=>s.toLowerCase()));
  const manual=tasks.filter(n=>n.manual).length,h=data.automacao?.horas_mes;
  const stat=(v,l,hot)=>`<div class="fx-stat${hot?' hot':''}"><b>${esc(v)}</b><small>${esc(l)}</small></div>`;
  // Ordem de importância: em telas menores somem os últimos.
  R('fx-stats').innerHTML=stat(tasks.length,'etapas')+stat(f.etapas.filter(n=>n.tipo==='decisao').length,'decisões')+stat(f.raias.length,'papéis')
    +stat(f.melhorias.length,'pontos de melhoria',true)+(tasks.length?stat(`${Math.round(manual/tasks.length*100)}%`,'feito à mão'):'')
    +(typeof h==='number'&&h>0?stat(`${Math.round(h)} h`,'por mês hoje'):'')+stat(systems.size,'sistemas');
}

/* Montando (agente trabalhando) e erro */
function ghost(){
  const r=(x,y,w=150,h=70)=>`<rect class="g" x="${x}" y="${y}" width="${w}" height="${h}" rx="14"/>`;
  return `<svg class="fx-ghost" viewBox="0 0 1400 700" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
    <path d="M60 175H1340M60 350H1340M60 525H1340" style="stroke:#e4eadf;stroke-dasharray:none;animation:none"/>
    ${r(120,90)}${r(340,90)}${r(560,265)}${r(800,265)}${r(800,440)}${r(1040,90)}${r(1040,440)}
    <path d="M270 125H340M490 125H520V300H560M710 300H800M950 300H990V125H1040M875 335V440M950 475H1040"/></svg>`}
function building(data){
  const el=R('fx-build');el.hidden=false;R('fx-legend').hidden=true;
  const steps=['Lendo o procedimento','Identificando papéis e raias','Desenhando etapas e decisões','Ligando as etapas e os retornos','Apontando os pontos de melhoria'];
  if(!el.querySelector('.fx-steps')){
    el.innerHTML=`${ghost()}<div class="fx-build-card"><div class="fx-mark">${svg(I.flow)}</div><h3>Montando o fluxo As Is</h3>
      <p>O NexxusDoc está lendo o procedimento e desenhando o processo como ele é feito hoje, com quem faz cada etapa, as decisões, os retornos e onde dá para melhorar.</p>
      <ol class="fx-steps">${steps.map(s=>`<li><i></i>${esc(s)}</li>`).join('')}</ol><div class="fx-bar"><i style="width:3%"></i></div>
      <small>Leva cerca de um minuto. Pode fechar esta janela: o fluxo continua sendo montado e fica no botão Fluxo As Is, em Documentos.</small>
      <small class="fx-retry" hidden></small></div>`;
  }
  const retry=el.querySelector('.fx-retry');
  if(retry){retry.hidden=!(data.tentativa>1);retry.textContent=data.tentativa>1?`O servidor do agente oscilou: o NexxusDoc está tentando de novo sozinho (tentativa ${data.tentativa} de ${data.tentativas||3}).`:''}
  const started=Date.now()-(data.decorrido||0)*1000,expected=(data.esperado||50)*1000;
  clearInterval(S.timer);
  const tick=()=>{const p=(Date.now()-started)/expected,stage=p<.12?0:p<.3?1:p<.58?2:p<.8?3:4;
    el.querySelectorAll('.fx-steps li').forEach((li,i)=>{li.className=i<stage?'done':i===stage?'on':''});
    el.querySelector('.fx-bar i').style.width=`${Math.min(94,4+p*90)}%`};
  tick();S.timer=setInterval(tick,500);
}
function showError(message,seq){
  if(seq!==undefined&&seq!==S.openSeq)return;
  clearInterval(S.timer);const el=R('fx-build');el.hidden=false;
  el.innerHTML=`${ghost()}<div class="fx-build-card"><div class="fx-mark">${svg(I.flow)}</div><h3>Não deu para montar o fluxo agora</h3>
    <div class="fx-err">${esc(message)}</div><div class="fx-row"><button class="fx-btn" type="button" data-x="close">Fechar</button>
    <button class="fx-btn primary" type="button" data-x="retry">${svg(I.redo)}Tentar novamente</button></div></div>`;
  el.querySelector('[data-x=close]').addEventListener('click',close);
  el.querySelector('[data-x=retry]').addEventListener('click',async()=>{
    el.innerHTML='';const s=++S.openSeq;building({decorrido:0,esperado:S.data?.esperado||50});
    try{await send(`/api/documents/${encodeURIComponent(S.id)}/fluxo/gerar`,'POST',{refazer:S.data?.status==='pronto'});S.poll=setTimeout(()=>poll(s),1500)}
    catch(err){showError(err.message,s)}});
}

/* Desenho */
function render(data){
  clearInterval(S.timer);R('fx-build').hidden=true;R('fx-build').innerHTML='';
  const f=data.fluxo;S.flow=f;S.byId=new Map(f.etapas.map(n=>[n.id,n]));
  S.geo=layout(f);
  // Arrumação manual: deslocamento em relação ao lugar automático (acompanha mudanças no desenho automático).
  S.custom=Object.fromEntries(Object.entries(data.layout||{}).filter(([k,v])=>S.byId.has(k)&&Array.isArray(v)&&v.length===2)
    .map(([k,[dx,dy]])=>{const a=S.geo.auto.get(k);return [k,[a.x+dx,a.y+dy]]}));
  S.impBy=new Map(f.etapas.map(n=>[n.id,[]]));f.melhorias.forEach(m=>m.etapas.forEach(id=>S.impBy.get(id)?.push(m)));
  R('fx-actions').style.visibility='';R('fx-imp-n').textContent=f.melhorias.length;
  R('fx-imp-btn').classList.toggle('on',S.showImp);
  R('fx-reset').hidden=!(data.pode_gerenciar&&Object.keys(S.custom).length);R('fx-redo').hidden=!data.pode_gerenciar;
  R('fx-move').hidden=!data.pode_gerenciar;toggleArrange(false);
  R('fx-heads').innerHTML='';  // raias do fluxo novo (refazer pode mudar os nomes)
  const world=R('fx-world');
  world.classList.toggle('fx-anim',!reduce());S.root.classList.toggle('fx-static',STATIC);
  world.innerHTML=`<div class="fx-lanes" id="fx-lanes"></div><svg class="fx-edges" id="fx-edges"><defs>
      ${['n','h','b'].map((k,i)=>`<marker id="fx-ar-${k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0 0L10 5L0 10z" fill="${['#8a9a8f','#1f7a45','#c77700'][i]}"/></marker>`).join('')}</defs><g id="fx-paths"></g></svg>
    <div class="fx-labels" id="fx-labels"></div><div class="fx-nodes" id="fx-nodes"></div>`;
  drawLanes();drawNodes();drawEdges();legend();
  S.root.classList.toggle('fx-hide-imp',!S.showImp);
  fit(false);
  if(S.fresh){S.fresh=false;toast()}
  if(!reduce())setTimeout(()=>world.classList.remove('fx-anim'),2600+S.geo.rank.size*70);
}
function worldSize(){
  let w=S.geo.width,h=S.geo.height;
  for(const n of S.flow.etapas){const b=box(n);w=Math.max(w,b.r+PADX+40);h=Math.max(h,b.b+40)}
  return {w,h}}
function drawLanes(){
  const {w,h}=worldSize();
  R('fx-lanes').innerHTML=S.geo.laneBox.map((l,i)=>`<div class="fx-lane" style="top:${l.y}px;height:${i===S.geo.laneBox.length-1?Math.max(l.h,h-l.y):l.h}px;width:${w}px"></div>`).join('');
  const world=R('fx-world');world.style.width=w+'px';world.style.height=h+'px';
  const edges=R('fx-edges');edges.setAttribute('width',w);edges.setAttribute('height',h);
}
function laneOf(n){return S.geo.laneBox[S.geo.laneIx.get(n.raia)??0]}
function nodeHtml(n){
  const p=pos(n.id),s=sizeOf(n),r=S.geo.rank.get(n.id)||0,imps=S.impBy.get(n.id)||[];
  const high=imps.some(m=>m.impacto==='alto')?' imp-high':'';
  const style=`left:${p.x-s.w/2}px;top:${p.y-s.h/2}px;width:${s.w}px;height:${s.h}px;--r:${r}`;
  if(n.tipo==='inicio'||n.tipo==='fim')return `<div class="fx-node fx-event${n.tipo==='fim'?' end':''}" data-id="${esc(n.id)}" style="${style}" tabindex="0" role="button" aria-label="${esc((n.tipo==='inicio'?'Início: ':'Fim: ')+n.titulo)}">
    <div class="fx-dot">${svg(n.tipo==='inicio'?I.play:I.stop)}</div><div class="fx-event-label">${esc(n.titulo)}</div></div>`;
  if(n.tipo==='decisao')return `<div class="fx-node fx-gate" data-id="${esc(n.id)}" style="${style}" tabindex="0" role="button" aria-label="${esc('Decisão: '+n.titulo)}">
    <div class="fx-dia">${svg(I.branch)}</div><div class="fx-gate-label">${esc(n.titulo)}</div></div>`;
  const lane=S.flow.raias.find(l=>l.id===n.raia)||{},third=n.terceiro||lane.tipo==='terceiro';
  const kind=n.tipo==='espera'?[I.clock,'Espera']:n.tipo==='subprocesso'?[I.stack,'Subprocesso']:lane.tipo==='sistema'?[I.monitor,'Automática']
    :third?[I.building,'Executada pelo terceiro']:n.manual?[I.hand,'Manual']:[I.task,'Tarefa'];
  const cats=[...new Set(imps.map(m=>m.categoria))].slice(0,3);
  const chips=[...(n.transacoes||[]).map(t=>`<span class="fx-chip sap">SAP · ${esc(t)}</span>`),
    ...(n.sistemas||[]).filter(s=>!(n.transacoes||[]).length||!/^sap/i.test(s)).map(s=>`<span class="fx-chip">${esc(s)}</span>`)];
  return `<div class="fx-node" data-id="${esc(n.id)}" style="${style}"><div class="fx-ring"></div>
    <div class="fx-task${third?' third':''}${n.tipo==='espera'?' wait':''}" tabindex="0" role="button" aria-label="${esc(`Etapa ${S.geo.num.get(n.id)}: ${n.titulo}`)}" style="height:100%">
    <div class="fx-n-top"><span class="fx-n-num">${String(S.geo.num.get(n.id)||'').padStart(2,'0')}</span><span class="fx-n-kind">${svg(kind[0])}${esc(kind[1])}</span>
    <span class="fx-n-flags">${cats.map(c=>`<span class="fx-flag" style="background:${CATS[c].c}" title="${esc(CATS[c].label)}">${svg(CATS[c].icon)}</span>`).join('')}</span></div>
    <div class="fx-n-title">${esc(n.titulo)}</div><div class="fx-n-chips">${chips.slice(0,2).join('')}${chips.length>2?`<span class="fx-chip more">+${chips.length-2}</span>`:''}</div>
    ${n.tipo==='subprocesso'?'<span class="fx-sub-mark"></span>':''}</div></div>`.replace('class="fx-node"',`class="fx-node${high}"`);
}
function drawNodes(){
  R('fx-nodes').innerHTML=S.flow.etapas.map(nodeHtml).join('');
  R('fx-nodes').querySelectorAll('.fx-node').forEach(bindNode);
  paintState();
}
function drawEdges(){
  const paths=[],labels=[];let backIx=0;
  S.edgeEls=[];S.sides=new Map();  // lados das decisões recalculados (as etapas podem ter sido arrastadas)
  S.flow.ligacoes.forEach((e,i)=>{
    const isBack=S.geo.back.has(e)||box(S.byId.get(e.para)).l<box(S.byId.get(e.de)).r-4;
    const pts=route(e,isBack?backIx++:0),d=pathD(pts),r=S.geo.rank.get(e.de)||0;
    paths.push(`<path data-i="${i}" class="${isBack?'back':''}" d="${d}" style="--len:${plen(pts)};--r:${r}" marker-end="url(#fx-ar-${isBack?'b':'n'})"/>`);
    if(e.rotulo){const [x,y]=labelAt(pts,!isBack&&S.byId.get(e.de).tipo==='decisao',labelWidth(e.rotulo));
      labels.push(`<div class="fx-elabel${isBack?' back':''}" data-i="${i}" style="left:${x}px;top:${y}px;--r:${r}">${esc(e.rotulo)}</div>`)}
  });
  R('fx-paths').innerHTML=paths.join('');R('fx-labels').innerHTML=labels.join('');
  paintState();
}
function paintState(){
  if(!S.flow)return;
  const focusIds=S.focus?new Set(S.focus.etapas):null,lane=S.laneFocus,hover=S.hover;
  R('fx-nodes').querySelectorAll('.fx-node').forEach(el=>{const n=S.byId.get(el.dataset.id);
    const dim=(focusIds&&!focusIds.has(n.id))||(lane&&n.raia!==lane);
    el.classList.toggle('dim',!!dim);el.classList.toggle('sel',S.sel===n.id);el.classList.toggle('focus',!!focusIds?.has(n.id))});
  R('fx-paths')?.querySelectorAll('path').forEach(p=>{const e=S.flow.ligacoes[+p.dataset.i];
    const on=hover&&(e.de===hover||e.para===hover)||S.sel&&(e.de===S.sel||e.para===S.sel);
    const dim=(focusIds&&!(focusIds.has(e.de)&&focusIds.has(e.para)))||(lane&&!(S.byId.get(e.de).raia===lane||S.byId.get(e.para).raia===lane));
    p.classList.toggle('hl',!!on);p.classList.toggle('dim',!!dim&&!on);
    p.setAttribute('marker-end',`url(#fx-ar-${on?'h':p.classList.contains('back')?'b':'n'})`)});
  R('fx-labels')?.querySelectorAll('.fx-elabel').forEach(l=>{const e=S.flow.ligacoes[+l.dataset.i];
    l.classList.toggle('dim',!!((focusIds&&!(focusIds.has(e.de)&&focusIds.has(e.para)))||(lane&&!(S.byId.get(e.de).raia===lane||S.byId.get(e.para).raia===lane))))});
  R('fx-heads').querySelectorAll('.fx-head-lane').forEach(h=>h.classList.toggle('on',h.dataset.lane===lane));
}
function drawHeads(){
  R('fx-heads').innerHTML=S.geo.laneBox.map(l=>{const t=LANE_TYPES[l.tipo]||LANE_TYPES.interno;
    return `<div class="fx-head-lane" data-lane="${esc(l.id)}" title="${esc(l.nome)} (${esc(t.label)}). Clique para destacar só esta raia.">
      <div class="fx-head-in"><span class="fx-head-ic" style="background:${t.s};color:${t.c}">${svg(t.icon)}</span><b>${esc(l.nome)}</b><i style="color:${t.c}">${esc(t.label)}</i></div></div>`}).join('');
  R('fx-heads').querySelectorAll('.fx-head-lane').forEach(h=>h.addEventListener('click',()=>{S.laneFocus=S.laneFocus===h.dataset.lane?null:h.dataset.lane;paintState()}));
  placeHeads();paintState();
}
// Só reposiciona as cabeças das raias (chamado a cada quadro do arrasto, sem reconstruir nada).
function placeHeads(){
  const heads=R('fx-heads').children;
  if(heads.length!==S.geo.laneBox.length){drawHeads();return}
  S.geo.laneBox.forEach((l,i)=>{const h=heads[i];h.style.top=`${S.ty+l.y*S.k}px`;h.style.height=`${l.h*S.k}px`;h.classList.toggle('tight',l.h*S.k<130)});
}
function legend(){
  const el=R('fx-legend');el.hidden=false;
  const item=(g,l)=>`<span><svg viewBox="0 0 22 16" aria-hidden="true">${g}</svg>${esc(l)}</span>`;
  el.innerHTML=item('<circle cx="11" cy="8" r="6" fill="#f1f7dc" stroke="#1f7a45" stroke-width="1.6"/>','Início')
    +item('<rect x="2" y="2" width="18" height="12" rx="3.5" fill="#fff" stroke="#b9c6b1"/>','Etapa')
    +item('<path d="M11 1.5 17.5 8 11 14.5 4.5 8z" fill="#fffdf3" stroke="#d6b85e" stroke-width="1.4"/>','Decisão')
    +item('<circle cx="11" cy="8" r="5.5" fill="#fff" stroke="#003d18" stroke-width="3"/>','Fim')
    +item('<path d="M1 8h17" stroke="#8a9a8f" stroke-width="1.7"/><path d="m16 5 4 3-4 3z" fill="#8a9a8f"/>','Sequência')
    +item('<path d="M1 8h17" stroke="#c77700" stroke-width="1.7" stroke-dasharray="4 3"/><path d="m16 5 4 3-4 3z" fill="#c77700"/>','Retorno ou retrabalho')
    +item('<rect x="2" y="2" width="18" height="12" rx="3.5" fill="#fffcf6" stroke="#e3c48f" stroke-dasharray="3 2"/>','Espera')
    +Object.values(CATS).map(c=>`<span><span class="fx-flag" style="background:${c.c};width:16px;height:16px">${svg(c.icon)}</span>${esc(c.label)}</span>`).join('');
}
function toast(){
  const t=document.createElement('div');t.className='fx-toast';
  t.innerHTML=`<div class="fx-mark">${svg(I.flow)}</div><div><b>Documento pronto.</b> Este é o fluxo As Is do processo, montado a partir do procedimento: confira as etapas, os retornos e os ${S.flow.melhorias.length} pontos de melhoria.</div><button class="fx-icon" type="button" aria-label="Fechar aviso">${svg(I.close)}</button>`;
  R('fx-body').appendChild(t);const go=()=>t.remove();t.querySelector('button').addEventListener('click',go);setTimeout(go,9000);
}

/* Navegação: arrastar, zoom, minimapa */
// Leve: move o desenho na hora; raias e minimapa no máximo uma vez por quadro (o arrasto não engasga).
function applyView(){
  R('fx-world').style.transform=`translate(${S.tx}px,${S.ty}px) scale(${S.k})`;
  R('fx-zl').textContent=`${Math.round(S.k*100)}%`;
  if(!S.geo||S.frame)return;
  S.frame=requestAnimationFrame(()=>{S.frame=0;if(S.geo){placeHeads();drawMini()}});
}
function fit(animate){
  const v=R('fx-view').getBoundingClientRect(),{w,h}=worldSize();
  // Abre legível (78% no mínimo), começando pelo início do processo; o minimapa e "ver tudo" mostram o resto.
  const k=clamp(Math.min((v.width-HEADW-70)/w,(v.height-150)/h),0.3,1.05),kk=Math.max(k,animate?k:0.78);
  S.k=kk;
  S.tx=w*kk<v.width-HEADW-50?HEADW+(v.width-HEADW-w*kk)/2:HEADW+8;
  S.ty=h*kk<v.height-130?Math.max(56,(v.height-110-h*kk)/2+40):56;
  if(animate&&!reduce()){const world=R('fx-world');world.style.transition='transform .35s ease';setTimeout(()=>world.style.transition='',380)}
  applyView();
}
function zoomBy(f,cx,cy){
  const v=R('fx-view').getBoundingClientRect();cx??=v.width/2;cy??=v.height/2;
  const k=clamp(S.k*f,0.25,2);S.tx=cx-(cx-S.tx)*(k/S.k);S.ty=cy-(cy-S.ty)*(k/S.k);S.k=k;applyView();
}
function center(ids){
  const bs=ids.map(id=>box(S.byId.get(id)));if(!bs.length)return;
  const l=Math.min(...bs.map(b=>b.l)),r=Math.max(...bs.map(b=>b.r)),t=Math.min(...bs.map(b=>b.t)),b=Math.max(...bs.map(b=>b.b));
  const v=R('fx-view').getBoundingClientRect(),padL=S.impOpen?HEADW+430:HEADW+30,padR=R('fx-det').classList.contains('open')?420:60;
  const k=clamp(Math.min((v.width-padL-padR)/(r-l+80),(v.height-170)/(b-t+80),1),0.45,1);
  S.k=k;S.tx=padL+(v.width-padL-padR)/2-(l+r)/2*k;S.ty=60+(v.height-130)/2-(t+b)/2*k;
  if(!reduce()){const world=R('fx-world');world.style.transition='transform .4s ease';setTimeout(()=>world.style.transition='',430)}
  applyView();
}
// A etapa escolhida não fica escondida atrás dos painéis laterais.
function reveal(id){
  const b=box(S.byId.get(id)),v=R('fx-view').getBoundingClientRect();
  const right=v.width-(R('fx-det').classList.contains('open')?425:40),left=HEADW+(S.impOpen?430:20);
  const sl=S.tx+b.l*S.k,sr=S.tx+b.r*S.k,dx=sr>right?right-sr-24:sl<left?left-sl+24:0;
  if(!dx)return;S.tx+=dx;
  if(!reduce()){const world=R('fx-world');world.style.transition='transform .35s ease';setTimeout(()=>world.style.transition='',380)}
  applyView();
}
/* Arrasto: a tela anda ao arrastar em qualquer lugar (fundo ou card). Etapa só se move no modo "Mover etapas"
   (quem pode reorganizar). Movimento e soltura ouvidos na janela inteira: soltar fora do fluxo não deixa nada preso. */
function startPan(e,nodeId){
  S.pan={x:e.clientX,y:e.clientY,tx:S.tx,ty:S.ty,moved:false,node:nodeId||null};
  R('fx-world').style.transition='';
  dragging(true);
}
// Durante qualquer arrasto: nada de seleção de texto (e a que já existia é desfeita).
function dragging(on){
  S.root?.classList.toggle('fx-dragging',on);
  if(on)try{window.getSelection()?.removeAllRanges()}catch{}
}
function onPointerMove(e){
  const p=S.pan,d=S.nodeDrag;
  if(p){const dx=e.clientX-p.x,dy=e.clientY-p.y;
    if(!p.moved){if(Math.hypot(dx,dy)<4)return;p.moved=true;R('fx-view').classList.add('panning');S.hover=null}
    S.tx=p.tx+dx;S.ty=p.ty+dy;applyView();return}
  if(d){if(!d.moved&&Math.hypot(e.clientX-d.x,e.clientY-d.y)<8)return;  // clique com a mão tremendo não move a etapa
    d.moved=true;const n=S.byId.get(d.id),lane=laneOf(n),s=sizeOf(n);
    const x=Math.max(s.w/2+12,d.px+(e.clientX-d.x)/S.k);
    const y=clamp(d.py+(e.clientY-d.y)/S.k,lane.y+s.h/2+(n.tipo==='decisao'?44:8),lane.y+lane.h-s.h/2-(n.tipo==='inicio'||n.tipo==='fim'?40:8));
    S.custom[d.id]=[Math.round(x),Math.round(y)];
    d.el.style.left=`${x-s.w/2}px`;d.el.style.top=`${y-s.h/2}px`;d.el.style.animation='none';
    if(!S.edgeFrame)S.edgeFrame=requestAnimationFrame(()=>{S.edgeFrame=0;drawEdges()})}
}
function onPointerUp(){
  const p=S.pan,d=S.nodeDrag;S.pan=null;S.nodeDrag=null;
  if(!p&&!d)return;
  dragging(false);
  if(S.root)R('fx-view').classList.remove('panning');
  if(p&&!p.moved){
    if(p.node)select(p.node);
    else if(S.focus)setFocus(null);else if(S.laneFocus){S.laneFocus=null;paintState()}else select(null);
  }
  if(d){if(d.moved){drawLanes();drawEdges();drawMini();R('fx-reset').hidden=false;clearTimeout(S.dirty);S.dirty=setTimeout(()=>{S.dirty=0;saveLayout()},700)}
    else select(d.id)}
}
function bindView(){
  const view=R('fx-view');
  view.addEventListener('pointerdown',e=>{if(e.button!==0||e.target.closest('.fx-node'))return;e.preventDefault();startPan(e)});
  window.addEventListener('pointermove',onPointerMove);
  window.addEventListener('pointerup',onPointerUp);window.addEventListener('pointercancel',onPointerUp);window.addEventListener('blur',onPointerUp);
  view.addEventListener('dragstart',e=>e.preventDefault());
  view.addEventListener('selectstart',e=>e.preventDefault());
  view.addEventListener('wheel',e=>{e.preventDefault();const r=view.getBoundingClientRect();zoomBy(Math.exp(-e.deltaY*0.0015),e.clientX-r.left,e.clientY-r.top)},{passive:false});
}
function toggleArrange(force){
  S.arrange=force??!S.arrange;
  S.root.classList.toggle('fx-arranging',S.arrange);R('fx-move').classList.toggle('on',S.arrange);
  R('fx-move').setAttribute('aria-pressed',String(S.arrange));
  R('fx-hint').textContent=S.arrange?'Mover etapas: arraste uma etapa para outro lugar da raia · clique de novo no botão para voltar a navegar'
    :'Role para aproximar · arraste para navegar · clique numa etapa para ver como é feita';
}
function bindNode(el){
  const id=el.dataset.id;
  el.addEventListener('pointerenter',()=>{if(S.pan||S.nodeDrag)return;S.hover=id;paintState()});
  el.addEventListener('pointerleave',()=>{if(S.hover===id&&!S.pan){S.hover=null;paintState()}});
  el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(id)}});
  el.addEventListener('dblclick',()=>{if(S.data.pode_gerenciar){select(id);editStep(id)}});
  el.addEventListener('pointerdown',e=>{if(e.button!==0)return;e.stopPropagation();e.preventDefault();
    if(S.arrange&&S.data.pode_gerenciar){const p=pos(id);S.nodeDrag={id,el,x:e.clientX,y:e.clientY,px:p.x,py:p.y,moved:false};dragging(true)}
    else startPan(e,id)});
}
async function saveLayout(){
  const offsets=Object.fromEntries(Object.entries(S.custom).map(([k,[x,y]])=>{const a=S.geo.auto.get(k);return [k,[x-a.x,y-a.y]]}));
  try{await send(`/api/documents/${encodeURIComponent(S.id)}/fluxo/layout`,'PUT',{posicoes:offsets,relativo:true})}catch{}
}
async function resetLayout(){
  S.custom={};R('fx-reset').hidden=true;drawLanes();drawNodes();drawEdges();fit(true);
  try{await send(`/api/documents/${encodeURIComponent(S.id)}/fluxo/layout`,'PUT',{posicoes:{},relativo:true})}catch{}
}
async function redo(){
  if(!confirm('Montar o fluxo de novo a partir do documento?\n\nO agente lê o procedimento outra vez. A arrumação manual e as correções feitas nos quadros são perdidas.'))return;
  const seq=++S.openSeq;R('fx-det').classList.remove('open');toggleImp(false);
  R('fx-build').innerHTML='';building({decorrido:0,esperado:S.data?.esperado||50});
  try{await send(`/api/documents/${encodeURIComponent(S.id)}/fluxo/gerar`,'POST',{refazer:true});S.poll=setTimeout(()=>poll(seq),1500)}
  catch(err){showError(err.message,seq)}
}
function bindMini(){
  const c=R('fx-mini');let down=false;
  const go=e=>{const m=S.mini;if(!m)return;const r=c.getBoundingClientRect(),x=(e.clientX-r.left)*(c.width/r.width),y=(e.clientY-r.top)*(c.height/r.height);
    const wx=(x-m.ox)/m.s,wy=(y-m.oy)/m.s,v=R('fx-view').getBoundingClientRect();S.tx=v.width/2-wx*S.k;S.ty=v.height/2-wy*S.k;applyView()};
  c.addEventListener('pointerdown',e=>{down=true;cap(c,e);go(e)});
  c.addEventListener('pointermove',e=>{if(down)go(e)});c.addEventListener('pointerup',()=>{down=false});
}
function drawMini(){
  const c=R('fx-mini'),g=c.getContext('2d');if(!S.flow)return;
  const {w,h}=worldSize(),s=Math.min((c.width-20)/w,(c.height-20)/h),ox=(c.width-w*s)/2,oy=(c.height-h*s)/2;S.mini={s,ox,oy};
  g.clearRect(0,0,c.width,c.height);
  S.geo.laneBox.forEach((l,i)=>{g.fillStyle=i%2?'#f6f8f2':'#ffffff';g.fillRect(ox,oy+l.y*s,w*s,l.h*s);g.strokeStyle='#e2e8dd';g.strokeRect(ox,oy+l.y*s,w*s,l.h*s)});
  for(const n of S.flow.etapas){const b=box(n);
    g.fillStyle=n.tipo==='decisao'?'#d6b85e':n.tipo==='inicio'?'#1f7a45':n.tipo==='fim'?'#003d18':(S.impBy.get(n.id)||[]).length&&S.showImp?'#afd037':'#9fb0a4';
    g.fillRect(ox+b.l*s,oy+b.t*s,Math.max(3,b.w*s),Math.max(3,b.h*s))}
  const v=R('fx-view').getBoundingClientRect();
  g.strokeStyle='#1f7a45';g.lineWidth=2;g.strokeRect(ox+(-S.tx/S.k)*s,oy+(-S.ty/S.k)*s,(v.width/S.k)*s,(v.height/S.k)*s);
}

/* Detalhe da etapa */
function select(id){
  S.sel=id;paintState();const panel=R('fx-det');
  if(!id){panel.classList.remove('open');return}
  const n=S.byId.get(id),lane=S.flow.raias.find(l=>l.id===n.raia)||{},t=LANE_TYPES[lane.tipo]||LANE_TYPES.interno;
  const kind={inicio:'Início do processo',fim:'Fim do processo',decisao:'Decisão',espera:'Espera',subprocesso:'Subprocesso'}[n.tipo]||'Etapa';
  const num=S.geo.num.get(id),imps=S.impBy.get(id)||[];
  const sec=(icon,title,body)=>body?`<div class="fx-sec"><h4>${svg(icon)}${esc(title)}</h4>${body}</div>`:'';
  const list=a=>(a||[]).length?`<ul>${a.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'';
  const p=v=>v?`<p>${esc(v)}</p>`:'';
  const out=S.flow.ligacoes.filter(e=>e.de===id).map(e=>`<li><b>${esc(e.rotulo||'Segue para')}</b>: ${esc(S.byId.get(e.para).titulo)}</li>`);
  const inc=S.flow.ligacoes.filter(e=>e.para===id).map(e=>`<li>${esc(S.byId.get(e.de).titulo)}${e.rotulo?` (${esc(e.rotulo)})`:''}</li>`);
  const facts=[n.passo&&['Passo no documento',n.passo],n.tempo&&['Tempo ou prazo',n.tempo],
    !['inicio','fim','decisao'].includes(n.tipo)&&['Execução',n.terceiro||lane.tipo==='terceiro'?'Pelo prestador':lane.tipo==='sistema'?'Automática':n.manual?'Manual':'Pela equipe']].filter(Boolean);
  const order=S.geo.order.map(x=>x.id),at=order.indexOf(id);
  panel.innerHTML=`<div class="fx-p-head"><div class="grow"><div class="fx-p-kicker">${esc(kind)}${num?` ${String(num).padStart(2,'0')}`:''}</div><h3 class="fx-p-title">${esc(n.titulo)}</h3>
      <span class="fx-lane-tag" style="background:${t.s};color:${t.c}">${svg(t.icon)}${esc(lane.nome||'')}</span></div>
      <button class="fx-icon" type="button" data-x="close" aria-label="Fechar detalhes">${svg(I.close)}</button></div>
    <div class="fx-p-body">
      ${facts.length?`<div class="fx-sec"><div class="fx-facts">${facts.map(([a,b])=>`<div class="fx-fact"><small>${esc(a)}</small><b>${esc(b)}</b></div>`).join('')}</div></div>`:''}
      ${sec(I.how,'Como é feito',p(n.descricao))}
      ${sec(I.sys,'Sistemas e transações',(n.sistemas||[]).length||(n.transacoes||[]).length?`<div class="fx-chips">${(n.transacoes||[]).map(x=>`<span class="fx-chip sap">SAP · ${esc(x)}</span>`).join('')}${(n.sistemas||[]).filter(s=>!(n.transacoes||[]).length||!/^sap$/i.test(s.trim())).map(x=>`<span class="fx-chip">${esc(x)}</span>`).join('')}</div>`:'')}
      ${sec(I.inp,'Entradas',list(n.entradas))}${sec(I.out,'Saídas',list(n.saidas))}
      ${sec(I.rule,'Regra aplicada',p(n.regra))}${sec(I.shield,'Controle',p(n.controle))}${sec(I.doc,'Evidência',p(n.evidencia))}
      ${sec(I.left,'Vem de',inc.length?`<ul>${inc.join('')}</ul>`:'')}${sec(I.right,'Depois',out.length?`<ul>${out.join('')}</ul>`:'')}
      ${sec(I.bulb,`Pontos de melhoria nesta etapa (${imps.length})`,imps.length?imps.map(impCard).join(''):'<p class="fx-empty">Nenhum ponto de melhoria apontado aqui.</p>')}
      ${n.editado?`<p class="fx-edited">${svg(I.edit)}Corrigido no fluxo por ${esc(n.editado.nome||n.editado.por)} em ${esc(new Date(n.editado.em).toLocaleDateString('pt-BR'))}</p>`:''}
    </div>
    <div class="fx-p-foot"><button class="fx-btn" type="button" data-x="prev"${at<=0?' disabled':''} title="Etapa anterior">${svg(I.left)}<span class="fx-lbl2">Anterior</span></button>
      ${S.data.pode_gerenciar?`<button class="fx-btn" type="button" data-x="edit" title="Corrigir as informações deste quadro">${svg(I.edit)}Editar</button>`:''}
      <button class="fx-btn" type="button" data-x="next"${at>=order.length-1?' disabled':''} title="Próxima etapa"><span class="fx-lbl2">Próxima</span>${svg(I.right)}</button></div>`;
  panel.classList.add('open');reveal(id);
  panel.querySelector('[data-x=close]').addEventListener('click',()=>select(null));
  panel.querySelector('[data-x=edit]')?.addEventListener('click',()=>editStep(id));
  panel.querySelector('[data-x=prev]').addEventListener('click',()=>{const k=order[at-1];if(k){select(k);center([k])}});
  panel.querySelector('[data-x=next]').addEventListener('click',()=>{const k=order[at+1];if(k){select(k);center([k])}});
  panel.querySelectorAll('[data-imp]').forEach(b=>b.addEventListener('click',()=>setFocus(S.flow.melhorias.find(m=>m.id===b.dataset.imp))));
}

/* Edição de um quadro pela própria tela (sem o agente): autor, owner da área ou master. */
function editStep(id){
  const n=S.byId.get(id),panel=R('fx-det'),task=!['inicio','fim','decisao'].includes(n.tipo);
  const kind={inicio:'o início',fim:'o fim',decisao:'a decisão'}[n.tipo]||'a etapa';
  const lines=a=>esc((a||[]).join('\n')),comma=a=>esc((a||[]).join(', '));
  const lanes=S.flow.raias.map(l=>`<option value="${esc(l.id)}"${l.id===n.raia?' selected':''}>${esc(l.nome)}</option>`).join('');
  panel.innerHTML=`<div class="fx-p-head"><div class="grow"><div class="fx-p-kicker">Editar ${esc(kind)}</div><h3 class="fx-p-title">${esc(n.titulo)}</h3></div>
      <button class="fx-icon" type="button" data-x="cancel" aria-label="Cancelar edição">${svg(I.close)}</button></div>
    <form class="fx-p-body fx-form" id="fx-edit" novalidate>
      <label>${n.tipo==='decisao'?'Pergunta da decisão':'Título'}<input name="titulo" maxlength="90" value="${esc(n.titulo)}" required></label>
      <label>Quem faz (raia)<select name="raia">${lanes}</select></label>
      <label>Como é feito<textarea name="descricao" rows="4" maxlength="600">${esc(n.descricao)}</textarea></label>
      ${task?`<div class="fx-2"><label>Sistemas<input name="sistemas" value="${comma(n.sistemas)}" placeholder="Separe por vírgula"></label>
        <label>Transações SAP<input name="transacoes" value="${comma(n.transacoes)}" placeholder="Ex.: MIRO, ME23N"></label></div>
        <div class="fx-2"><label>Entradas<textarea name="entradas" rows="3" placeholder="Uma por linha">${lines(n.entradas)}</textarea></label>
        <label>Saídas<textarea name="saidas" rows="3" placeholder="Uma por linha">${lines(n.saidas)}</textarea></label></div>
        <label>Regra aplicada<textarea name="regra" rows="2" maxlength="320">${esc(n.regra)}</textarea></label>
        <label>Controle<input name="controle" maxlength="240" value="${esc(n.controle)}"></label>
        <label>Evidência<input name="evidencia" maxlength="240" value="${esc(n.evidencia)}"></label>
        <label>Tempo ou prazo<input name="tempo" maxlength="120" value="${esc(n.tempo)}"></label>
        <div class="fx-checks"><label><input type="checkbox" name="manual"${n.manual?' checked':''}>Feita à mão</label><label><input type="checkbox" name="terceiro"${n.terceiro?' checked':''}>Executada pelo terceiro</label></div>`:''}
      <p class="fx-note">A correção vale para este fluxo e fica registrada com o seu nome. Se a informação também estiver errada no procedimento, corrija o documento em Documentos › Editar: a nova versão remonta o fluxo a partir dele.</p>
      <p class="fx-err" id="fx-edit-err" hidden></p>
    </form>
    <div class="fx-p-foot"><button class="fx-btn" type="button" data-x="cancel">Cancelar</button><button class="fx-btn primary" type="submit" form="fx-edit" data-x="save">Salvar</button></div>`;
  panel.classList.add('open');
  const form=panel.querySelector('#fx-edit');form.elements.titulo.focus();
  panel.querySelectorAll('[data-x=cancel]').forEach(b=>b.addEventListener('click',()=>select(id)));
  form.addEventListener('submit',async e=>{
    e.preventDefault();const f=form.elements,err=panel.querySelector('#fx-edit-err'),btn=panel.querySelector('[data-x=save]');
    const split=(v,re)=>String(v||'').split(re).map(s=>s.trim()).filter(Boolean);
    if(!f.titulo.value.trim()){err.textContent='Informe o título.';err.hidden=false;f.titulo.focus();return}
    const body={titulo:f.titulo.value,raia:f.raia.value,descricao:f.descricao.value};
    if(task)Object.assign(body,{sistemas:split(f.sistemas.value,/[,;\n]/),transacoes:split(f.transacoes.value,/[,;\s]+/),
      entradas:split(f.entradas.value,/\n/),saidas:split(f.saidas.value,/\n/),regra:f.regra.value,controle:f.controle.value,
      evidencia:f.evidencia.value,tempo:f.tempo.value,manual:f.manual.checked,terceiro:f.terceiro.checked});
    btn.disabled=true;btn.textContent='Salvando…';err.hidden=true;
    try{
      const res=await send(`/api/documents/${encodeURIComponent(S.id)}/fluxo/etapas/${encodeURIComponent(id)}`,'PUT',body);
      const i=S.flow.etapas.findIndex(x=>x.id===id);S.flow.etapas[i]=res.etapa;S.byId.set(id,res.etapa);
      S.geo=layout(S.flow);drawLanes();drawNodes();drawEdges();header(S.data);applyView();select(id);
    }catch(x){err.textContent=x.message;err.hidden=false;btn.disabled=false;btn.textContent='Salvar'}
  });
}

/* Pontos de melhoria */
function impCard(m){
  const c=CATS[m.categoria]||CATS.padronizacao,[pl,pc]=PRIO[priority(m)];
  const steps=m.etapas.map(id=>S.byId.get(id)).filter(Boolean).map(n=>S.geo.num.get(n.id)?String(S.geo.num.get(n.id)).padStart(2,'0'):n.titulo);
  return `<div class="fx-imp${S.focus?.id===m.id?' on':''}" data-imp="${esc(m.id)}" role="button" tabindex="0">
    <div class="fx-imp-top"><span class="fx-imp-cat" style="color:${c.c}"><span class="fx-flag" style="background:${c.c}">${svg(c.icon)}</span>${esc(c.label)}${m.desperdicio?`: ${esc(WASTES[m.desperdicio]||m.desperdicio)}`:''}</span><span class="fx-prio ${pc}">${pl}</span></div>
    <h5>${esc(m.titulo)}</h5>${m.descricao?`<p>${esc(m.descricao)}</p>`:''}${m.ganho?`<div class="fx-imp-gain">${esc(m.ganho)}</div>`:''}
    <div class="fx-imp-meta"><span>Impacto <b>${LEVEL[m.impacto]||m.impacto}</b></span><span>Esforço <b>${LEVEL[m.esforco]||m.esforco}</b></span>${steps.length?`<span>Etapas <b>${esc(steps.join(', '))}</b></span>`:'<span>Processo inteiro</span>'}</div></div>`;
}
function toggleImp(force){
  S.impOpen=force??!S.impOpen;const panel=R('fx-imp');
  if(S.impOpen){S.showImp=true;S.root.classList.remove('fx-hide-imp');renderImp()}
  panel.classList.toggle('open',S.impOpen);R('fx-imp-btn').classList.toggle('on',S.impOpen||S.showImp);
}
function renderImp(){
  const panel=R('fx-imp'),all=S.flow.melhorias.slice().sort((a,b)=>priority(a)-priority(b));
  const counts={};all.forEach(m=>counts[m.categoria]=(counts[m.categoria]||0)+1);
  const list=all.filter(m=>!S.catOff.has(m.categoria));
  const quick=all.filter(m=>priority(m)===0).length,auto=counts.automacao||0;
  panel.innerHTML=`<div class="fx-p-head"><div class="grow"><div class="fx-p-kicker">Do As Is para o To Be</div><h3 class="fx-p-title">Pontos de melhoria</h3></div>
      <button class="fx-icon" type="button" data-x="close" aria-label="Fechar">${svg(I.close)}</button></div>
    <div class="fx-p-body">${S.flow.resumo?`<div class="fx-summary">${esc(S.flow.resumo)}</div>`:''}
      <div class="fx-sec"><div class="fx-facts"><div class="fx-fact"><small>Ganhos rápidos</small><b>${quick} de ${all.length}</b></div><div class="fx-fact"><small>Automação</small><b>${auto} oportunidade(s)</b></div></div></div>
      <div class="fx-sec"><div class="fx-catbar">${Object.entries(counts).map(([k,n])=>`<button type="button" data-cat="${k}" class="${S.catOff.has(k)?'off':''}" aria-pressed="${!S.catOff.has(k)}"><span class="fx-flag" style="background:${CATS[k].c}">${svg(CATS[k].icon)}</span>${esc(CATS[k].label)} (${n})</button>`).join('')}</div>
      ${list.length?list.map(impCard).join(''):'<p class="fx-empty">Nenhum ponto nesta seleção.</p>'}</div></div>`;
  panel.querySelector('[data-x=close]').addEventListener('click',()=>toggleImp(false));
  panel.querySelectorAll('[data-cat]').forEach(b=>b.addEventListener('click',()=>{const k=b.dataset.cat;S.catOff.has(k)?S.catOff.delete(k):S.catOff.add(k);renderImp()}));
  panel.querySelectorAll('[data-imp]').forEach(b=>{const go=()=>setFocus(S.flow.melhorias.find(m=>m.id===b.dataset.imp));
    b.addEventListener('click',go);b.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();go()}})});
}
function setFocus(m){
  S.focus=m&&m.etapas.length?m:null;R('fx-body').querySelector('.fx-focusbar')?.remove();
  if(S.focus){const bar=document.createElement('div');bar.className='fx-focusbar';
    bar.innerHTML=`<span>Etapas ligadas a</span><b>${esc(m.titulo)}</b><button type="button">Mostrar tudo</button>`;
    bar.querySelector('button').addEventListener('click',()=>setFocus(null));R('fx-body').appendChild(bar);center(m.etapas)}
  paintState();if(S.impOpen)renderImp();if(S.sel)select(S.sel);
}

/* Exportação: PNG (desenho próprio em SVG) e BPMN 2.0 com posições, raias e documentação de cada etapa. */
function fileBase(){const d=S.data.documento||{};return `Fluxo As Is - ${(d.codigo?d.codigo+' ':'')}${S.flow.titulo||d.processo||'processo'}`.replace(/[\\/:*?"<>|]+/g,' ').trim()}
function download(name,blob){const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.appendChild(a);a.click();
  setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},1000)}
function wrap(ctx,text,width,max){const words=String(text||'').split(/\s+/),lines=[];let line='';
  for(const w of words){const t=line?line+' '+w:w;if(ctx.measureText(t).width>width&&line){lines.push(line);line=w}else line=t}
  if(line)lines.push(line);if(lines.length>max){lines.length=max;lines[max-1]=lines[max-1].replace(/\s*\S*$/,'')+'…'}return lines}
async function exportPng(){
  const {w,h}=worldSize(),top=96,W=Math.ceil(w+HEADW+40),H=Math.ceil(h+top+30),x0=20+HEADW,y0=top;
  const meas=document.createElement('canvas').getContext('2d');
  const tx=(x,y,lines,size,weight,color,anchor='start',lh=1.3)=>lines.map((l,i)=>`<text x="${x}" y="${y+i*size*lh}" font-size="${size}" font-weight="${weight}" fill="${color}" text-anchor="${anchor}">${esc(l)}</text>`).join('');
  let out=`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" font-family="Segoe UI, Arial, sans-serif"><rect width="100%" height="100%" fill="#f4f6f0"/>
    <defs>${['n','b'].map((k,i)=>`<marker id="m${k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L10 5L0 10z" fill="${['#8a9a8f','#c77700'][i]}"/></marker>`).join('')}</defs>
    <text x="24" y="38" font-size="12" font-weight="700" fill="#1f7a45" letter-spacing="1">FLUXO AS IS${S.data.documento?.codigo?' · '+esc(S.data.documento.codigo):''}</text>
    <text x="24" y="64" font-size="22" font-weight="700" fill="#003d18">${esc(S.flow.titulo||S.data.documento?.processo||'')}</text>
    <text x="24" y="84" font-size="12" fill="#7d8b81">${esc(R('fx-sub').textContent)}</text><g transform="translate(${x0},${y0})">`;
  S.geo.laneBox.forEach((l,i)=>{const t=LANE_TYPES[l.tipo]||LANE_TYPES.interno;
    meas.font='700 12.5px Segoe UI';const ls=wrap(meas,l.nome,HEADW-28,3);
    out+=`<rect x="0" y="${l.y}" width="${w}" height="${l.h}" fill="${i%2?'#f8faf4':'#ffffff'}" stroke="#e2e8dd"/><rect x="${-HEADW}" y="${l.y}" width="${HEADW}" height="${l.h}" fill="#ffffff" stroke="#e2e8dd"/>
      ${tx(-HEADW+14,l.y+22,ls,12.5,700,'#17231b')}${tx(-HEADW+14,l.y+28+ls.length*16,[t.label],11,600,t.c)}`});
  let backIx=0;
  S.flow.ligacoes.forEach(e=>{const isBack=S.geo.back.has(e)||box(S.byId.get(e.para)).l<box(S.byId.get(e.de)).r-4,pts=route(e,isBack?backIx++:0);
    out+=`<path d="${pathD(pts)}" fill="none" stroke="${isBack?'#c77700':'#8a9a8f'}" stroke-width="1.7"${isBack?' stroke-dasharray="6 5"':''} marker-end="url(#m${isBack?'b':'n'})"/>`;
    if(e.rotulo){const [x,y]=labelAt(pts,!isBack&&S.byId.get(e.de).tipo==='decisao',labelWidth(e.rotulo));meas.font='600 11.5px Segoe UI';const tw=meas.measureText(e.rotulo).width+16;
      out+=`<rect x="${x-tw/2}" y="${y-10}" width="${tw}" height="20" rx="10" fill="#fff" stroke="${isBack?'#f0d29f':'#cfd8c8'}"/>${tx(x,y+4,[e.rotulo],11.5,600,isBack?'#9a5c00':'#4e5e53','middle')}`}});
  for(const n of S.flow.etapas){const b=box(n);
    if(n.tipo==='inicio'||n.tipo==='fim'){meas.font='700 12.5px Segoe UI';
      out+=`<circle cx="${b.x}" cy="${b.y}" r="${EVENT/2-1}" fill="${n.tipo==='inicio'?'#f1f7dc':'#fff'}" stroke="${n.tipo==='inicio'?'#1f7a45':'#003d18'}" stroke-width="${n.tipo==='inicio'?2:4}"/>${tx(b.x,b.b+20,wrap(meas,n.titulo,165,2),12.5,700,'#003d18','middle')}`;continue}
    if(n.tipo==='decisao'){meas.font='700 12px Segoe UI';const ls=wrap(meas,n.titulo,126,3);
      out+=`<path d="M${b.x} ${b.t+2}L${b.r-2} ${b.y}L${b.x} ${b.b-2}L${b.l+2} ${b.y}z" fill="#fffdf3" stroke="#d6b85e" stroke-width="1.6"/><path d="M${b.x} ${b.y-8}v6M${b.x} ${b.y-2}l-5 7M${b.x} ${b.y-2}l5 7" stroke="#9a7a12" stroke-width="2" fill="none" stroke-linecap="round"/>`
        +tx(b.x-30,b.t+12-(ls.length-1)*15,ls,12,700,'#6f5a10','end');continue}
    const lane=S.flow.raias.find(l=>l.id===n.raia)||{},third=n.terceiro||lane.tipo==='terceiro',imps=S.impBy.get(n.id)||[];
    meas.font='700 14px Segoe UI';const ls=wrap(meas,n.titulo,b.w-24,2);
    out+=`<rect x="${b.l}" y="${b.t}" width="${b.w}" height="${b.h}" rx="14" fill="${third||n.tipo==='espera'?'#fffcf6':'#fff'}" stroke="${n.tipo==='espera'?'#e3c48f':'#dfe6d9'}"${n.tipo==='espera'?' stroke-dasharray="5 4"':''}/>
      <rect x="${b.l+12}" y="${b.t+10}" width="26" height="22" rx="7" fill="#003d18"/>${tx(b.l+25,b.t+25.5,[String(S.geo.num.get(n.id)||'').padStart(2,'0')],11.5,700,'#fff','middle')}
      ${tx(b.l+46,b.t+25.5,[n.tipo==='espera'?'Espera':third?'Executada pelo terceiro':n.manual?'Manual':'Tarefa'],11,600,'#7d8b81')}
      ${tx(b.l+12,b.t+52,ls,14,700,'#17231b')}`;
    [...new Set(imps.map(m=>m.categoria))].slice(0,3).forEach((c,i)=>{out+=`<circle cx="${b.r-18-i*24}" cy="${b.t+21}" r="9" fill="${CATS[c].c}"/>`});
    const chips=[...(n.transacoes||[]).map(t=>'SAP · '+t),...(n.sistemas||[]).filter(s=>!(n.transacoes||[]).length||!/^sap/i.test(s))].slice(0,2);
    let cx=b.l+12;meas.font='600 11px Segoe UI';
    chips.forEach(cp=>{const cw=Math.min(140,meas.measureText(cp).width+14);if(cx+cw>b.r-10)return;
      out+=`<rect x="${cx}" y="${b.b-28}" width="${cw}" height="18" rx="6" fill="#f9fbf6" stroke="#e2e8dd"/>${tx(cx+7,b.b-15,[cp],11,600,'#4e5e53')}`;cx+=cw+5})}
  out+='</g></svg>';
  const img=new Image(),scale=2;
  img.onload=()=>{const c=document.createElement('canvas');c.width=W*scale;c.height=H*scale;const g=c.getContext('2d');g.scale(scale,scale);g.drawImage(img,0,0);
    c.toBlob(b=>download(fileBase()+'.png',b),'image/png')};
  img.onerror=()=>alert('Não foi possível gerar a imagem do fluxo.');
  img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(out);
}
function exportBpmn(){
  const x=v=>esc(v),sc=0.62,ox=40,oy=40,{w}=worldSize();
  const lanes=S.geo.laneBox,nodes=S.flow.etapas,edges=S.flow.ligacoes;
  const tag=n=>({inicio:'startEvent',fim:'endEvent',decisao:'exclusiveGateway',subprocesso:'subProcess',espera:'intermediateCatchEvent'}[n.tipo]
    ||((S.flow.raias.find(l=>l.id===n.raia)||{}).tipo==='sistema'?'serviceTask':n.manual?'manualTask':'userTask'));
  const docOf=n=>{const imps=(S.impBy.get(n.id)||[]).map(m=>`Melhoria (${(CATS[m.categoria]||{}).label||m.categoria}): ${m.titulo}. ${m.descricao}`);
    return [n.descricao,(n.transacoes||[]).length?'Transações SAP: '+n.transacoes.join(', '):'',(n.sistemas||[]).length?'Sistemas: '+n.sistemas.join(', '):'',
      n.regra?'Regra: '+n.regra:'',n.controle?'Controle: '+n.controle:'',n.evidencia?'Evidência: '+n.evidencia:'',n.tempo?'Tempo: '+n.tempo:'',...imps].filter(Boolean).join('\n')};
  const nid=n=>'N_'+n.id.replace(/[^A-Za-z0-9_]/g,'_'),fid=i=>'F_'+(i+1),lid=l=>'L_'+l.id.replace(/[^A-Za-z0-9_]/g,'_');
  const bpmnSize=n=>n.tipo==='decisao'?[50,50]:(n.tipo==='inicio'||n.tipo==='fim'||n.tipo==='espera')?[36,36]:[150,80];
  let proc='',di='';
  proc+=`<bpmn:laneSet id="LaneSet_1">${lanes.map(l=>`<bpmn:lane id="${lid(l)}" name="${x(l.nome)}">${nodes.filter(n=>n.raia===l.id).map(n=>`<bpmn:flowNodeRef>${nid(n)}</bpmn:flowNodeRef>`).join('')}</bpmn:lane>`).join('')}</bpmn:laneSet>`;
  nodes.forEach(n=>{const t=tag(n),doc=docOf(n);
    const ins=edges.map((e,i)=>e.para===n.id?`<bpmn:incoming>${fid(i)}</bpmn:incoming>`:'').join(''),outs=edges.map((e,i)=>e.de===n.id?`<bpmn:outgoing>${fid(i)}</bpmn:outgoing>`:'').join('');
    proc+=`<bpmn:${t} id="${nid(n)}" name="${x(n.titulo)}">${doc?`<bpmn:documentation>${x(doc)}</bpmn:documentation>`:''}${ins}${outs}${n.tipo==='espera'?'<bpmn:timerEventDefinition/>':''}</bpmn:${t}>`;
    const p=pos(n.id),[bw,bh]=bpmnSize(n);
    di+=`<bpmndi:BPMNShape id="${nid(n)}_di" bpmnElement="${nid(n)}"${n.tipo==='subprocesso'?' isExpanded="false"':''}><dc:Bounds x="${Math.round(ox+p.x*sc-bw/2)}" y="${Math.round(oy+p.y*sc-bh/2)}" width="${bw}" height="${bh}"/></bpmndi:BPMNShape>`});
  edges.forEach((e,i)=>{proc+=`<bpmn:sequenceFlow id="${fid(i)}" sourceRef="${nid(S.byId.get(e.de))}" targetRef="${nid(S.byId.get(e.para))}"${e.rotulo?` name="${x(e.rotulo)}"`:''}/>`;
    const a=pos(e.de),b=pos(e.para),[aw]=bpmnSize(S.byId.get(e.de)),[bw]=bpmnSize(S.byId.get(e.para));
    const p1=[ox+a.x*sc+aw/2,oy+a.y*sc],p2=[ox+b.x*sc-bw/2,oy+b.y*sc];
    const mid=p2[0]>p1[0]+10?[[p1[0]+(p2[0]-p1[0])/2,p1[1]],[p1[0]+(p2[0]-p1[0])/2,p2[1]]]:[[p1[0]+20,p1[1]],[p1[0]+20,p1[1]+60],[p2[0]-20,p1[1]+60],[p2[0]-20,p2[1]]];
    di+=`<bpmndi:BPMNEdge id="${fid(i)}_di" bpmnElement="${fid(i)}">${[p1,...mid,p2].map(q=>`<di:waypoint x="${Math.round(q[0])}" y="${Math.round(q[1])}"/>`).join('')}</bpmndi:BPMNEdge>`});
  const H=S.geo.height*sc;
  di=`<bpmndi:BPMNShape id="Pool_1_di" bpmnElement="Pool_1" isHorizontal="true"><dc:Bounds x="${ox-30}" y="${oy}" width="${Math.round(w*sc+30)}" height="${Math.round(H)}"/></bpmndi:BPMNShape>`
    +lanes.map(l=>`<bpmndi:BPMNShape id="${lid(l)}_di" bpmnElement="${lid(l)}" isHorizontal="true"><dc:Bounds x="${ox}" y="${Math.round(oy+l.y*sc)}" width="${Math.round(w*sc)}" height="${Math.round(l.h*sc)}"/></bpmndi:BPMNShape>`).join('')+di;
  const name=S.flow.titulo||S.data.documento?.processo||'Processo';
  const xml=`<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id="Definitions_NexxusDoc" targetNamespace="http://example.com/nexxusdoc" exporter="NexxusDoc" exporterVersion="1">
<bpmn:collaboration id="Collab_1"><bpmn:participant id="Pool_1" name="${x(name)}" processRef="Process_1"/></bpmn:collaboration>
<bpmn:process id="Process_1" name="${x(name)}" isExecutable="false"><bpmn:documentation>${x([S.data.documento?.codigo,S.flow.resumo].filter(Boolean).join(' · '))}</bpmn:documentation>${proc}</bpmn:process>
<bpmndi:BPMNDiagram id="Diagram_1"><bpmndi:BPMNPlane id="Plane_1" bpmnElement="Collab_1">${di}</bpmndi:BPMNPlane></bpmndi:BPMNDiagram>
</bpmn:definitions>`;
  download(fileBase()+'.bpmn',new Blob([xml],{type:'application/xml'}));
}

return {open,close,_estado:()=>S};  // _estado: leitura para os testes automáticos de sobreposição
})();
