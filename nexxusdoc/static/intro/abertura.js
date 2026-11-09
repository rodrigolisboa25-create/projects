/* Abertura do NexxusDoc (antes do login), 08/11/2026: rede neural de dados em 3D, no estilo do video de referencia do
   usuario (Envato "3D animation of neural network"): piso de grade digital em perspectiva ate o horizonte aceso, linhas de
   luz que sobem do piso com losangos e rotulos (nuvem de palavras do NexxusDoc e indicadores), mapa-mundi pontilhado no
   fundo e particulas. A camera avanca devagar sobre a grade. No final o horizonte acende, uma onda percorre a rede e os
   fios saem dos losangos e ligam os pontos ate desenhar o quadro de login, que aparece no mesmo lugar.
   12 s, canvas 2D, deterministico: render(t) desenha o quadro do instante t. */
(() => {
'use strict';
const DUR = 12.0;
const C = {mint: [46, 230, 166], lime: [175, 208, 55], teal: [64, 214, 200], cyan: [90, 220, 235], white: [235, 255, 245]};
const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${Math.max(0, Math.min(1, a))})`;
const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const ease = t => 1 - Math.pow(1 - clamp(t), 3);
const easeIO = t => { t = clamp(t); return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
const seg = (t, a, b) => clamp((t - a) / (b - a));
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let x = Math.imul(seed ^ seed >>> 15, 1 | seed); x = x + Math.imul(x ^ x >>> 7, 61 | x) ^ x; return ((x ^ x >>> 14) >>> 0) / 4294967296; }; }
// mapa-mundi em grade de pontos (150 x 64), feito do mapa da apresentacao (Natural Earth, dominio publico)
const MAPA = 'AAAAAP///gAAAAAAAAAAAAAAAAAAAJ////AHwAAA4AAAAAAAAAAAAff4//+AAAA8B/gGAAAAAAAAAD+/4D/8AAABgP//hAAAAAAAAAH+38H/4AAYBD/////gAHAAAAf//+eH/gAD/r///////8PwAAB///8/H8eAH//////////34AAH///8cHgMAf/////////+B8AAf//8DgHAAB+/////////8B/AAD//4H4AAAA+////////pgAPAAB//+H4AAAY8///////8BwACAAB///f8AAA4////////8BwAEAAB///f+AAB9/////////ggAAAAD////8AAAf/////////wAAAAAB////OAAAf/////////gAAAAAD////gAAAP//+//////gAAAAAH///6AAAB/34e//////MAAAAAH///wAAAD8/7Of////8IAAAAAP///AAAADwF//f////cEAAAAAP//+AAAADwpv/f////2MAAAAAP//+AAAAB/gC//////m8AAAAAH//4AAAAD/wB//////xwAAAAAH//wAAAAH/////////wAAAAAAD/ogAAAAH/////////4AAAAAAC/AwAAAAf//+/f////wAAAAAAC+AAAAAA/////t////wAAAAAAAeBgAAAA////f+H///oAAAAAAAeIYAAAB/////+D/P+AAAAAAAAf4XAAAA////v8B8H0EAAAAAAAH4AAAAB////34B4H4EAAAAAAAA+AAAAB/////gA4B8EAAAAAAAAMAAAAB////8AA4B8AAAAAAAAAGP4AAA/////gA4BIDAAAAAAAAD/8AAAf////gAYBADAAAAAAAAAf/AAAP////AAAAgZAAAAAAAAAf/gAAAD///AAADw4AAAAAAAAA//wAAAB//+AAABx4AAAAAAAAB//4AAAB//4AAAAz2EAAAAAAAB//+AAAB//4AAAA52FgAAAAAAB///wAAA//wAAAAYGD4gAAAAAB///4AAAf/wAAAAOAA9AAAAAAA///4AAAf/wAAAABgA+AAAAAAAf//wAAAf/wAAAAAAACAAAAAAAf//wAAAf/wgAAAAAOQAAAAAAAP//gAAAf/xgAAAAB+YAAAAAAAH//gAAA//zAAAAAD/4AAAAAAAB//gAAAf/DAAAAAH/4AAAAAAAB//gAAAf/HAAAAA//8BAAAAAAB//AAAAP/HAAAAB//+AAAAAAAB/8AAAAP+CAAAAB//+AAAAAAAB/8AAAAP+AAAAAB//+AAAAAAAB/8AAAAH8AAAAAB//+AAAAAAAA/4AAAAD4AAAAAB//8AAAAAAAA/wAAAADwAAAAAB4f4AAAAAAAA/gAAAAAAAAAAAAAHwAgAAAAAA/gAAAAAAAAAAAAAHwAwAAAAAA/AAAAAAAAAAAAAAAAAgAAAAAA+AAAAAAAAAAAAAADACAAAAAAAeAAAAAAAAAAAAAAAAMAAAAAAAeAAAAAAAAAAAAAAAAQAAAAAAAeAAAAAAAAAAAAAAAAAAAAAAAAOAAAAAAAAAAAAAAAAAAAAAAAAHAAAAAAAAAAAAAAAAAAAAAAAADgAAAAAAAAAAAAAAAAAAA';
const MW = 150, MH = 64;
// nuvem de palavras: o que o NexxusDoc faz e o vocabulario de IA
const KEYWORDS = ['PROCEDIMENTOS', 'CONHECIMENTO', 'AUTOMAÇÃO', 'SAP · BIGQUERY', 'FLUXO AS IS', 'LOGÍSTICA INTERNACIONAL',
  'DOCUMENTOS', 'COMPLIANCE OEA', 'INTELIGÊNCIA ARTIFICIAL', 'PROCESSOS', 'REDE NEURAL', 'MACHINE LEARNING', 'DEEP LEARNING',
  'BIG DATA', 'LLM', 'DUIMP', 'KPI', 'INBOUND', 'PADRONIZAÇÃO', 'POP', 'CHAT NEXXUS', 'REF. DOCS', 'PGL', 'QUERY CONSOLE',
  'FISIA', 'CENTAURO', 'DESEMBARAÇO', 'MAPA DE AUTOMAÇÃO', 'REVISÃO', 'DADOS'];

let MODEL = null;
function build() {
  const R = rng(20261108);
  const bin = atob(MAPA), map = [];
  for (let i = 0; i < MW * MH; i++) if ((bin.charCodeAt(i >> 3) >> (7 - (i & 7))) & 1) map.push([i % MW, Math.floor(i / MW), R()]);
  const pillars = [];
  // palavras-chave: 10 colunas em 3 profundidades, alturas alternadas (vizinhas nunca na mesma altura), sempre na tela
  const TIERS = [{z: 8.5, x: 0, h: [2.75, 1.75]}, {z: 11.8, x: .77, h: [2.3, 3.4]}, {z: 15.2, x: 1.53, h: [4.7, 3.6]}];
  KEYWORDS.forEach((txt, i) => {
    const col = i % 10, T = TIERS[Math.floor(i / 10)];
    pillars.push({x: (col - 4.5) * 2.3 + T.x, z: T.z + (col % 3) * .6, h: T.h[col % 2] + (col % 3) * .2, t0: 1.5 + ((i * 7) % 30) * .18, kw: txt});
  });
  for (let i = 0; i < 190; i++) {
    const x = (R() * 2 - 1) * 19, z = 3 + R() * 40;
    pillars.push({x, z, h: .35 + Math.pow(R(), 1.4) * 5.2, t0: .7 + R() * 3.6, pct: (R() * 99.9).toFixed(2).replace('.', ',') + '%', lbl: R() < .55,
      pulse: R() < .35 ? R() * 3 : -1});
  }
  const stars = Array.from({length: 160}, () => ({x: R(), y: R() * .6, s: .5 + R() * 1.3, p: R() * 6.28}));
  const jitter = Array.from({length: 16}, () => [R() - .5, R() - .5]);
  MODEL = {map, pillars, stars, jitter};
}

/* quadro de login (alvo do final): na tela vem o retangulo real; no video, o tamanho padrao do quadro */
function cardRect(W, H, card) {
  if (card) return card;
  const w = Math.min(W * .36, 520 * W / 1600 * 1.05), h = w * .74;
  return {x: W / 2 - w / 2, y: H * .55 - h / 2, w, h};
}
function perimeter(r, rad, n) {           // n pontos igualmente espacados no contorno do retangulo arredondado
  const pts = [], L = 2 * (r.w + r.h - 4 * rad) + 2 * Math.PI * rad;
  const at = s => {
    let d = s * L; const seg2 = [r.w - 2 * rad, Math.PI * rad / 2, r.h - 2 * rad, Math.PI * rad / 2, r.w - 2 * rad, Math.PI * rad / 2, r.h - 2 * rad, Math.PI * rad / 2];
    const corner = (cx, cy, a0, k) => [cx + rad * Math.cos(a0 + k * Math.PI / 2), cy + rad * Math.sin(a0 + k * Math.PI / 2)];
    for (let i = 0; i < 8; i++) {
      if (d <= seg2[i] || i === 7) { const k = seg2[i] ? d / seg2[i] : 0;
        switch (i) {
          case 0: return [r.x + rad + k * (r.w - 2 * rad), r.y];
          case 1: return corner(r.x + r.w - rad, r.y + rad, -Math.PI / 2, k);
          case 2: return [r.x + r.w, r.y + rad + k * (r.h - 2 * rad)];
          case 3: return corner(r.x + r.w - rad, r.y + r.h - rad, 0, k);
          case 4: return [r.x + r.w - rad - k * (r.w - 2 * rad), r.y + r.h];
          case 5: return corner(r.x + rad, r.y + r.h - rad, Math.PI / 2, k);
          case 6: return [r.x, r.y + r.h - rad - k * (r.h - 2 * rad)];
          default: return corner(r.x + rad, r.y + rad, Math.PI, k);
        } }
      d -= seg2[i];
    }
    return [r.x, r.y];
  };
  for (let i = 0; i < n; i++) pts.push(at(i / n));
  return pts;
}

/* ---------- desenho do quadro no instante t ---------- */
function render(ctx, W, H, t, card) {
  if (!MODEL) build();
  const {map, pillars, stars, jitter} = MODEL;
  const u = W / 1600;
  const out = easeIO(seg(t, 11.3, DUR));            // saida: o login de verdade aparece no lugar do quadro desenhado
  const dim = (1 - .62 * easeIO(seg(t, 8.8, 9.8))) * (1 - out);   // a cena recua enquanto o quadro de login se forma
  const rc = cardRect(W, H, card);
  // camera: avanca devagar sobre a grade, com um leve giro (sensacao de 3D)
  const camZ = .42 * t, camX = .55 * Math.sin(t * .22), camY = 1.35, yaw = -.07 + .13 * easeIO(t / DUR);
  const F = W * .62, HY = H * .53, cyw = Math.cos(yaw), syw = Math.sin(yaw), FAR = 46;
  const view = (x, y, z) => { const dx = x - camX, dz = z - camZ; return [dx * cyw - dz * syw, y - camY, dx * syw + dz * cyw]; };
  const scr = ([rx, ry, rz]) => { const f = F / rz; return {X: W / 2 + rx * f, Y: HY - ry * f, f, z: rz}; };
  const proj = (x, y, z) => { const v = view(x, y, z); return v[2] > .25 ? scr(v) : null; };
  const fog = z => Math.pow(clamp(1 - z / FAR), 1.5);
  const line3 = (a, b) => {                          // segmento em 3D cortado no plano da camera
    let A = view(...a), B = view(...b); const n = .25;
    if (A[2] < n && B[2] < n) return null;
    if (A[2] < n) { const k = (n - A[2]) / (B[2] - A[2]); A = A.map((v, i) => v + (B[i] - v) * k); }
    if (B[2] < n) { const k = (n - B[2]) / (A[2] - B[2]); B = B.map((v, i) => v + (A[i] - v) * k); }
    return [scr(A), scr(B)];
  };

  ctx.save();
  ctx.clearRect(0, 0, W, H);
  // fundo: espaco escuro com bruma no horizonte
  ctx.globalAlpha = 1 - out;
  const bg = ctx.createLinearGradient(0, 0, 0, H);
  bg.addColorStop(0, '#060d0f'); bg.addColorStop(.45, '#0b1a1c'); bg.addColorStop(.56, '#10262a'); bg.addColorStop(1, '#070f11');
  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  const hz = proj(camX + 200 * syw, 0, camZ + 200 * cyw) || {X: W / 2};
  const haze = ctx.createRadialGradient(hz.X, HY, 0, hz.X, HY, W * .55);
  haze.addColorStop(0, 'rgba(40,150,150,.32)'); haze.addColorStop(.4, 'rgba(20,80,85,.12)'); haze.addColorStop(1, 'rgba(10,30,35,0)');
  ctx.fillStyle = haze; ctx.fillRect(0, 0, W, H);
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = 'lighter';
  stars.forEach(s => { const a = (.15 + .25 * (.5 + .5 * Math.sin(t * 1.6 + s.p))) * ease(seg(t, .1, 1.2)) * dim;
    ctx.fillStyle = rgba(C.cyan, a); ctx.fillRect(s.x * W - camX * 6 * u, s.y * HY, s.s * u * 1.4, s.s * u * 1.4); });
  // mapa-mundi pontilhado ao fundo (surge da esquerda para a direita)
  const mw = W * .62, mx0 = hz.X - mw / 2 - camX * 10 * u, my0 = H * .05, cw = mw / MW, ch = mw / 2.06 / MH, ds = Math.max(1.2, 2.1 * u);
  map.forEach(([i, j, r]) => { const a = .36 * ease(seg(t, .4 + i / MW * 1.6 + r * .3, 1.0 + i / MW * 1.6 + r * .3)) * (.7 + .3 * Math.sin(t * 2 + r * 9)) * dim;
    if (a > .005) { ctx.fillStyle = rgba(C.cyan, a); ctx.fillRect(mx0 + i * cw, my0 + j * ch, ds, ds); } });

  // piso de grade: nasce no horizonte e vem rolando ate a camera
  const gp = easeIO(seg(t, .15, 2.3)), zNear = camZ + .3, zFar = camZ + FAR, zShow = zFar - (zFar - zNear) * gp;
  const zw = t >= 8 ? zFar - (t - 8) / 1.7 * (zFar - zNear) : -99;    // onda que sai do horizonte e vem ate a camera
  const waveAt = z => (t >= 8 && t < 10.2) ? Math.exp(-(((z - zw) / 2.2) ** 2)) * (1 - seg(t, 9.6, 10.2)) : 0;
  ctx.lineCap = 'round';
  const z0 = Math.ceil(zShow), XS = 26;
  for (let k = z0; k <= zFar; k++) {                  // linhas transversais
    const s = line3([-XS, 0, k], [XS, 0, k]); if (!s) continue;
    const f = fog(k - camZ), w = waveAt(k);
    ctx.strokeStyle = rgba(w > .05 ? C.lime : C.teal, (.12 + .5 * f + .9 * w) * dim * ease(seg(zShow + 1.5, k, k - 1.5) + (gp >= 1 ? 1 : 0)));
    ctx.lineWidth = Math.max(.7, (.6 + 1.3 * f + 1.5 * w) * u); ctx.beginPath(); ctx.moveTo(s[0].X, s[0].Y); ctx.lineTo(s[1].X, s[1].Y); ctx.stroke();
  }
  for (let xi = -XS; xi <= XS; xi++) {               // linhas ate o horizonte, em trechos (a bruma apaga ao longe)
    const zA = Math.max(zShow, zNear), steps = 12;
    for (let s2 = 0; s2 < steps; s2++) {
      const za = zA + (zFar - zA) * (s2 / steps) ** 1.8, zb = zA + (zFar - zA) * ((s2 + 1) / steps) ** 1.8, zm = (za + zb) / 2;
      const s = line3([xi, 0, za], [xi, 0, zb]); if (!s) continue;
      const f = fog(zm - camZ), w = waveAt(zm);
      ctx.strokeStyle = rgba(w > .05 ? C.lime : C.teal, (.1 + .45 * f + .8 * w) * dim * (xi === 0 ? 1.4 : 1));
      ctx.lineWidth = Math.max(.7, (.6 + 1.2 * f + 1.2 * w) * u); ctx.beginPath(); ctx.moveTo(s[0].X, s[0].Y); ctx.lineTo(s[1].X, s[1].Y); ctx.stroke();
    }
  }
  for (let k = z0; k <= camZ + 16; k++) for (let xi = -14; xi <= 14; xi++) {   // nos da grade acesos
    const q = proj(xi, 0, k); if (!q || q.X < 0 || q.X > W || q.Y > H) continue;
    const a = (.35 + .6 * fog(k - camZ)) * dim * (.6 + .4 * Math.sin(t * 2 + xi * 1.7 + k)) * ease(seg(t, .6, 2.4)), w = waveAt(k);
    const r = Math.max(1, .045 * q.f * .5) * (1 + 1.5 * w);
    ctx.fillStyle = rgba(w > .1 ? C.white : C.mint, a + w); ctx.fillRect(q.X - r / 2, q.Y - r / 2, r, r);
  }

  // luz do horizonte: acende forte aos 8 s (o nucleo da rede), de onde nasce a ligacao final
  const ign = seg(t, 7.7, 8.5), flare = (.55 + .45 * Math.sin(t * 1.4)) * ease(seg(t, .2, 1.4)) + 1.7 * Math.sin(ign * Math.PI / 2) * (1 - seg(t, 9.4, 11));
  if (flare > 0) {
    const rr = (34 + 46 * ign) * u;
    const g = ctx.createRadialGradient(hz.X, HY, 0, hz.X, HY, rr * 3);
    g.addColorStop(0, rgba(C.white, .55 * flare * (1 - out))); g.addColorStop(.18, rgba(C.cyan, .25 * flare * (1 - out))); g.addColorStop(1, rgba(C.cyan, 0));
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(hz.X, HY, rr * 3, 0, 6.29); ctx.fill();
    const L = W * (.22 + .2 * ign), st = ctx.createLinearGradient(hz.X - L, 0, hz.X + L, 0);
    st.addColorStop(0, rgba(C.cyan, 0)); st.addColorStop(.5, rgba(C.white, .7 * Math.min(1, flare) * (1 - out))); st.addColorStop(1, rgba(C.cyan, 0));
    ctx.fillStyle = st; ctx.fillRect(hz.X - L, HY - 1.2 * u, L * 2, 2.4 * u);
  }

  // linhas de luz com losangos e rotulos (do fundo para a frente)
  const P = pillars.map(p => {
    const rise = ease(seg(t, p.t0, p.t0 + .9)); if (rise <= 0) return null;
    const base = proj(p.x, 0, p.z), top = proj(p.x, p.h * rise, p.z); if (!base || !top) return null;
    return {p, rise, base, top, f: fog(top.z), w: waveAt(p.z)};
  });
  const order = P.map((q, i) => i).filter(i => P[i]).sort((a, b) => P[b].top.z - P[a].top.z);
  const kwFont = Math.round(Math.max(10, 15 * u * 1.25)), labels = [];
  order.forEach(i => {
    const {p, rise, base, top, f, w} = P[i];
    if (top.X < -60 || top.X > W + 60) return;
    const a = (p.kw ? 1 : .35 + .65 * f) * dim;
    const lg = ctx.createLinearGradient(base.X, base.Y, top.X, top.Y);
    lg.addColorStop(0, rgba(C.cyan, 0)); lg.addColorStop(1, rgba(p.kw ? C.mint : C.cyan, (p.kw ? .75 : .5) * a));
    ctx.strokeStyle = lg; ctx.lineWidth = Math.max(.7, (p.kw ? 1.4 : 1) * u); ctx.beginPath(); ctx.moveTo(base.X, base.Y); ctx.lineTo(top.X, top.Y); ctx.stroke();
    if (p.pulse >= 0 && rise >= 1) {                 // dado subindo pela linha
      const ph = ((t * .7 + p.pulse) % 1.6) / 1.6;
      if (ph < 1) { const x = base.X + (top.X - base.X) * ph, y = base.Y + (top.Y - base.Y) * ph, r = Math.max(2, 3.2 * u * (.5 + f));
        const g = ctx.createRadialGradient(x, y, 0, x, y, r * 2.5); g.addColorStop(0, rgba(C.white, .9 * a)); g.addColorStop(1, rgba(C.mint, 0));
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r * 2.5, 0, 6.29); ctx.fill(); }
    }
    const up = proj(p.x, p.h * rise + 1.4, p.z);
    if (up) { const ug = ctx.createLinearGradient(top.X, top.Y, up.X, up.Y); ug.addColorStop(0, rgba(C.cyan, .22 * a)); ug.addColorStop(1, rgba(C.cyan, 0));
      ctx.strokeStyle = ug; ctx.beginPath(); ctx.moveTo(top.X, top.Y); ctx.lineTo(up.X, up.Y); ctx.stroke(); }
    // losango no topo
    const d = clamp(.075 * top.f, 1.8 * u, (p.kw ? 10 : 7) * u) * (p.kw ? 1.25 : 1), flash = w;
    const gl = ctx.createRadialGradient(top.X, top.Y, 0, top.X, top.Y, d * 4);
    gl.addColorStop(0, rgba(flash > .1 ? C.lime : C.mint, (.45 + .5 * flash) * a)); gl.addColorStop(1, rgba(C.mint, 0));
    ctx.fillStyle = gl; ctx.beginPath(); ctx.arc(top.X, top.Y, d * 4, 0, 6.29); ctx.fill();
    ctx.fillStyle = rgba(flash > .1 ? C.white : (p.kw ? C.white : C.mint), (.75 + .25 * flash) * a);
    ctx.beginPath(); ctx.moveTo(top.X, top.Y - d * 1.5); ctx.lineTo(top.X + d * .8, top.Y); ctx.lineTo(top.X, top.Y + d * 1.5); ctx.lineTo(top.X - d * .8, top.Y); ctx.closePath(); ctx.fill();
    const la = seg(rise, .75, 1);
    if (la > 0 && (p.kw || p.lbl) && top.z < 30) labels.push({p, X: top.X + d * 1.9, Y: top.Y, a: a * la, f, size: p.kw ? kwFont : clamp(.11 * top.f, 7 * u * 1.2, 12 * u * 1.2)});
  });
  // rotulos: os de palavra-chave nunca se sobrepoem (os mais proximos ficam no lugar)
  ctx.globalCompositeOperation = 'source-over';
  ctx.textBaseline = 'middle'; ctx.textAlign = 'left';
  const placed = [];
  labels.sort((A, B) => (B.p.kw ? 1 : 0) - (A.p.kw ? 1 : 0) || A.p.z - B.p.z).forEach(L => {
    const txt = L.p.kw ? L.p.kw.split('').join(' ') : L.p.pct;
    ctx.font = `${L.p.kw ? 700 : 600} ${Math.round(L.size)}px "Segoe UI", Inter, Arial, sans-serif`;
    const w = ctx.measureText(txt).width, pad = L.p.kw ? 16 * u : 0, box = {x: L.X - pad - 10 * u, y: L.Y - L.size * .7, w: w + 2 * pad + 10 * u, h: L.size * 1.4};
    if (L.p.kw) { for (let k = 0; k < 6 && placed.some(b => b.x < box.x + box.w && box.x < b.x + b.w && b.y < box.y + box.h && box.y < b.y + b.h); k++) { box.y += L.size * 1.5; } placed.push(box); }
    else if (placed.some(b => b.x < box.x + box.w && box.x < b.x + b.w && b.y < box.y + box.h && box.y < b.y + b.h)) return;
    const y = box.y + L.size * .7;
    if (L.p.kw) {
      ctx.shadowColor = rgba(C.mint, .85 * L.a); ctx.shadowBlur = 10 * u;
      ctx.fillStyle = rgba(C.white, .95 * L.a); ctx.fillText(txt, L.X, y); ctx.shadowBlur = 0;
      ctx.fillStyle = rgba(C.lime, L.a); ctx.fillRect(L.X, y + L.size * .78, 24 * u, 2 * u);
    } else { ctx.fillStyle = rgba(C.cyan, .7 * L.a); ctx.fillText(txt, L.X, y); }
  });
  ctx.textBaseline = 'alphabetic';
  ctx.globalCompositeOperation = 'lighter';

  /* ---------- final: fios saem dos losangos e ligam os pontos ate desenhar o quadro de login ---------- */
  const rad = Math.min(18 * u * 1.4, rc.h * .1), N = 32, pts = perimeter(rc, rad, N);
  if (t > 9.0) {
    const anchors = [0, 4, 8, 12, 16, 20, 24, 28], used = new Set();
    anchors.forEach((ai, j) => {
      const [axp, ayp] = pts[ai];
      let best = -1, bd = 1e18;
      // cada fio parte do losango mais proximo FORA do quadro (fio longo e visivel), de preferencia uma palavra-chave
      const m = 40 * u;
      P.forEach((q, i) => { if (!q || used.has(i) || q.rise < 1 || q.top.z > 26 || q.top.X < 0 || q.top.X > W || q.top.Y < 0 || q.top.Y > H) return;
        if (q.top.X > rc.x - m && q.top.X < rc.x + rc.w + m && q.top.Y > rc.y - m && q.top.Y < rc.y + rc.h + m) return;
        const d = ((q.top.X - axp) ** 2 + (q.top.Y - ayp) ** 2) * (q.p.kw ? .6 : 1); if (d < bd) { bd = d; best = i; } });
      if (best < 0) return; used.add(best);
      const s0 = 9.0 + j * .08, p = easeIO(seg(t, s0, s0 + 1.0)); if (p <= 0) return;
      const q = P[best].top, mx = (q.X + axp) / 2 + jitter[j][0] * 120 * u, my = (q.Y + ayp) / 2 + jitter[j][1] * 90 * u;
      const a = (1 - .65 * seg(t, 10.6, 11.4)) * (1 - out);
      const og = ctx.createRadialGradient(q.X, q.Y, 0, q.X, q.Y, 10 * u); og.addColorStop(0, rgba(C.white, .9 * a)); og.addColorStop(1, rgba(C.lime, 0));
      ctx.fillStyle = og; ctx.beginPath(); ctx.arc(q.X, q.Y, 10 * u, 0, 6.29); ctx.fill();
      ctx.strokeStyle = rgba(C.mint, .6 * a); ctx.lineWidth = 1.4 * u; ctx.beginPath(); ctx.moveTo(q.X, q.Y);
      let hx = q.X, hy = q.Y;
      for (let s = 1; s <= 24; s++) { const k = s / 24 * p, x = (1 - k) ** 2 * q.X + 2 * (1 - k) * k * mx + k * k * axp, y = (1 - k) ** 2 * q.Y + 2 * (1 - k) * k * my + k * k * ayp; ctx.lineTo(x, y); hx = x; hy = y; }
      ctx.stroke();
      if (p < 1) { const g = ctx.createRadialGradient(hx, hy, 0, hx, hy, 12 * u); g.addColorStop(0, rgba(C.white, a)); g.addColorStop(.4, rgba(C.lime, .6 * a)); g.addColorStop(1, rgba(C.lime, 0));
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(hx, hy, 12 * u, 0, 6.29); ctx.fill(); }
      if (p >= 1) { const g = ctx.createRadialGradient(axp, ayp, 0, axp, ayp, 10 * u); g.addColorStop(0, rgba(C.white, .9 * (1 - out))); g.addColorStop(1, rgba(C.lime, 0));
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(axp, ayp, 10 * u, 0, 6.29); ctx.fill(); }
    });
    // os pontos do contorno se ligam a partir de cada chegada, para os dois lados, ate fechar o quadro
    const closeP = seg(t, 9.9, 10.9);
    if (closeP > 0) {
      const reach = closeP * 2;
      ctx.strokeStyle = rgba(C.mint, .9 * (1 - out)); ctx.lineWidth = 1.8 * u;
      for (let i = 0; i < N; i++) {
        const fromA = i % 4, sgDone = clamp(reach - (fromA < 2 ? fromA : 3 - fromA)); if (sgDone <= 0) continue;
        const [x1, y1] = pts[i], [x2, y2] = pts[(i + 1) % N], fwd = fromA < 2;
        const sx = fwd ? x1 : x2, sy = fwd ? y1 : y2, ex = fwd ? x2 : x1, ey = fwd ? y2 : y1;
        ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(sx + (ex - sx) * sgDone, sy + (ey - sy) * sgDone); ctx.stroke();
        if (sgDone >= 1) { ctx.fillStyle = rgba(C.white, .8 * (1 - out)); ctx.beginPath(); ctx.arc(x1, y1, 1.8 * u, 0, 6.29); ctx.fill(); }
      }
    }
    // dentro do quadro: a rede desenha o titulo, o campo e o botao do login
    const inner = seg(t, 10.5, 11.3);
    if (inner > 0) {
      const rows = rc.rows && rc.rows.length ? rc.rows
        : [[.34, .13], [.55, .13], [.77, .14]].map(([ry, rh], j) => ({x: rc.x + rc.w * .1, y: rc.y + rc.h * ry - rc.h * rh / 2, w: rc.w * .8, h: rc.h * rh, btn: j === 2}));
      rows.forEach((row, j) => {
        const k = ease(seg(inner, j * .18, j * .18 + .6)); if (k <= 0) return;
        const ix = row.x, iw = row.w, y = row.y, h = row.h, isBtn = !!row.btn;
        ctx.strokeStyle = rgba(isBtn ? C.lime : C.mint, (isBtn ? .85 : .6) * (1 - out)); ctx.lineWidth = (isBtn ? 1.6 : 1.2) * u;
        ctx.beginPath(); ctx.moveTo(ix, y); ctx.lineTo(ix + iw * k, y); ctx.moveTo(ix, y + h); ctx.lineTo(ix + iw * k, y + h);
        if (k >= 1) { ctx.moveTo(ix, y); ctx.lineTo(ix, y + h); ctx.moveTo(ix + iw, y); ctx.lineTo(ix + iw, y + h); }
        ctx.stroke();
        if (isBtn && k >= 1) { ctx.fillStyle = rgba(C.lime, .18 * (1 - out)); ctx.fillRect(ix, y, iw, h); }
      });
      const glow = Math.sin(seg(t, 10.9, 11.9) * Math.PI) * (1 - out);
      if (glow > 0) { ctx.strokeStyle = rgba(C.lime, .35 * glow); ctx.lineWidth = 8 * u; ctx.strokeRect(rc.x, rc.y, rc.w, rc.h); }
    }
  }
  ctx.globalCompositeOperation = 'source-over';

  // titulo com reflexo de luz; sai antes do quadro de login se formar
  const tIn = ease(seg(t, 4.0, 5.1)) * (1 - ease(seg(t, 8.2, 9.0))), fs = Math.round(Math.min(W / 11, H / 7.5)), ty = H * .84 + (1 - ease(seg(t, 4.0, 5.1))) * 18;
  if (tIn > 0) {
    ctx.save(); ctx.globalAlpha = tIn * (1 - out); ctx.textAlign = 'center';
    ctx.font = `800 ${fs}px "Segoe UI", Inter, Arial, sans-serif`;
    const tw = ctx.measureText('NexxusDoc').width, tx = W / 2 - tw / 2;
    ctx.shadowColor = 'rgba(0,0,0,.9)'; ctx.shadowBlur = fs * .5; ctx.fillStyle = 'rgba(6,13,15,.5)'; ctx.fillText('NexxusDoc', W / 2, ty);
    ctx.shadowColor = rgba(C.mint, .75); ctx.shadowBlur = fs * .45;
    const grad = ctx.createLinearGradient(tx, 0, tx + tw, 0); grad.addColorStop(0, rgba(C.white, 1)); grad.addColorStop(.55, rgba(C.mint, 1)); grad.addColorStop(1, rgba(C.lime, 1));
    ctx.fillStyle = grad; ctx.fillText('NexxusDoc', W / 2, ty);
    ctx.shadowBlur = 0;
    const sw = seg(t, 4.6, 6.4);
    if (sw > 0 && sw < 1) {
      const sx = tx - tw * .3 + (tw * 1.6) * easeIO(sw), band = ctx.createLinearGradient(sx - fs * 1.2, 0, sx + fs * 1.2, 0);
      band.addColorStop(0, 'rgba(255,255,255,0)'); band.addColorStop(.5, 'rgba(255,255,255,.95)'); band.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.globalCompositeOperation = 'source-atop'; ctx.fillStyle = band; ctx.fillText('NexxusDoc', W / 2, ty);
      ctx.globalCompositeOperation = 'lighter';
      const k = Math.sin(sw * Math.PI), fy = ty - fs * .36, len = fs * 4.2;
      const streak = ctx.createLinearGradient(sx - len, 0, sx + len, 0);
      streak.addColorStop(0, 'rgba(120,255,210,0)'); streak.addColorStop(.5, `rgba(220,255,240,${.75 * k})`); streak.addColorStop(1, 'rgba(120,255,210,0)');
      ctx.fillStyle = streak; ctx.fillRect(sx - len, fy - 1.2, len * 2, 2.4);
      const coreG = ctx.createRadialGradient(sx, fy, 0, sx, fy, fs * .55);
      coreG.addColorStop(0, `rgba(255,255,255,${.8 * k})`); coreG.addColorStop(.3, `rgba(170,255,225,${.35 * k})`); coreG.addColorStop(1, 'rgba(120,255,210,0)');
      ctx.fillStyle = coreG; ctx.beginPath(); ctx.arc(sx, fy, fs * .55, 0, 6.29); ctx.fill();
      ctx.globalCompositeOperation = 'source-over';
    }
    ctx.globalAlpha = ease(seg(t, 4.8, 5.8)) * tIn * (1 - out);
    ctx.font = `600 ${Math.round(fs * .22)}px "Segoe UI", Inter, Arial, sans-serif`; ctx.fillStyle = rgba(C.white, .75);
    ctx.fillText('C E N T R A L I Z E D   P L A T F O R M   ·   C O E   I N B O U N D', W / 2, ty + fs * .52);
    ctx.restore();
  }
  ctx.restore();
}

/* ---------- uso na tela: toca uma vez e chama onEnd; getCard() da o retangulo real do quadro de login ---------- */
function play(canvas, onEnd, getCard) {
  if (!MODEL) build();
  const ctx = canvas.getContext('2d'); let start = null, done = false, raf = 0, dpr = 1;
  const fit = () => { dpr = Math.min(window.devicePixelRatio || 1, 2); canvas.width = innerWidth * dpr; canvas.height = innerHeight * dpr; };
  fit(); addEventListener('resize', fit);
  const finish = () => { if (done) return; done = true; cancelAnimationFrame(raf); removeEventListener('resize', fit); onEnd && onEnd(); };
  const frame = now => { if (start === null) start = now; const t = (now - start) / 1000;
    const r = getCard && getCard(), sc = o => ({x: o.x * dpr, y: o.y * dpr, w: o.w * dpr, h: o.h * dpr, btn: o.btn});
    const card = r && {...sc(r), rows: (r.rows || []).map(sc)};
    render(ctx, canvas.width, canvas.height, Math.min(t, DUR), card); if (t >= DUR) finish(); else raf = requestAnimationFrame(frame); };
  raf = requestAnimationFrame(frame);
  return finish;
}
/* ---------- fundo da tela de login (08/11/2026): o mesmo mapa-mundi fluorescente, cobrindo a tela inteira (o desfoque
   vem do CSS do canvas). Redesenha so quando a janela muda de tamanho. ---------- */
const fundos = new Set();
function drawFundo() { fundos.forEach(drawFundoEm); }
function drawFundoEm(cv) {
  if (!cv.isConnected || !cv.clientWidth) return;   // escondido: desenha quando a tela aparecer (fundo() de novo)
  if (!MODEL) build();
  const dpr = Math.min(window.devicePixelRatio || 1, 2), W = Math.max(1, Math.round(cv.clientWidth * dpr)), H = Math.max(1, Math.round(cv.clientHeight * dpr));
  if (cv.width !== W) cv.width = W; if (cv.height !== H) cv.height = H;
  const ctx = cv.getContext('2d'); ctx.clearRect(0, 0, W, H);
  // o mapa cobre a tela toda (como background-size: cover), centralizado
  const ar = 2.06, mw = Math.max(W, H * ar), mh = mw / ar, ox = (W - mw) / 2, oy = (H - mh) / 2, cw = mw / MW, ch = mh / MH;
  // pontos brancos levemente deslocados e entrelacados com os vizinhos (rede desenhando os continentes)
  const land = new Map(), jit = v => (v - .5) * .55;
  MODEL.map.forEach(([i, j, r]) => land.set(i * 1000 + j, [ox + (i + .5 + jit(r)) * cw, oy + (j + .5 + jit((r * 7.3) % 1)) * ch, r]));
  const wht = [235, 245, 242];
  ctx.lineWidth = Math.max(.6, cw * .07); ctx.strokeStyle = rgba(wht, .38); ctx.beginPath();
  land.forEach(([x, y, r], k) => {
    if (x < -cw * 2 || x > W + cw * 2 || y < -ch * 2 || y > H + ch * 2) return;
    const i = Math.floor(k / 1000), j = k % 1000;
    [[1, 0], [0, 1], [1, 1], [-1, 1]].forEach(([di, dj], n) => {
      if (n >= 2 && ((r * 10 + n) % 1) > .45) return;     // diagonais so em parte (trama irregular)
      const o = land.get((i + di) * 1000 + j + dj); if (!o) return;
      ctx.moveTo(x, y); ctx.lineTo(o[0], o[1]);
    });
  });
  ctx.stroke();
  ctx.fillStyle = rgba(wht, .85);
  land.forEach(([x, y, r]) => { if (x < -cw || x > W + cw || y < -ch || y > H + ch) return;
    ctx.beginPath(); ctx.arc(x, y, Math.max(1, cw * (.1 + .08 * r)), 0, 6.29); ctx.fill(); });
}
// usado no login e na tela de carregamento (canvas.login-map); cada um redesenha ao aparecer e ao mudar o tamanho da janela
function fundo(canvas) {
  if (!canvas) return;
  if (!fundos.size) addEventListener('resize', () => requestAnimationFrame(drawFundo));
  fundos.add(canvas);
  requestAnimationFrame(() => drawFundoEm(canvas));
}
window.nexusIntro = {play, render, DUR, fundo};
document.querySelectorAll('canvas.login-map').forEach(fundo);
})();
