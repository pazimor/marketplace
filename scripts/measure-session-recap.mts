// Génère docs/session-recap-measure.html : mesure la barre (progressSvg) contre l'image de référence.
// Usage : node --experimental-strip-types scripts/measure-session-recap.mts
// Puis ouvrir http://localhost:8765/session-recap-measure.html (serveur `recap-preview`) et lire #verdict / #out.
import { readFileSync, writeFileSync } from 'node:fs'
import { emptyRecap, onPlan, onPlanStep, progressSvg, PROGRESS_GEOMETRY } from '../plugins/session-recap/hooks/recap.ts'

const REF = JSON.parse(readFileSync(new URL('../docs/session-recap-reference.json', import.meta.url), 'utf8'))
const W = 400
// 5 étapes, 4 faites → 80 % ; la phase en cours est « Lire » (pastille courte)
let s = onPlan(emptyRecap(), { title: 'Mesure', stages: [{ name: 'Lire', steps: ['a', 'b', 'c', 'd', 'e'] }], at: 0 })
for (const n of ['a', 'b', 'c', 'd']) s = onPlanStep(s, { step: n, status: 'done', at: 1000 })
const svg = progressSvg(s.plan!, W, 5000, 'm')

const html = `<!doctype html><html><head><meta charset="utf-8"><title>Mesure barre session-recap</title>
<style>body{background:#202020;color:#ddd;font:12px ui-monospace,monospace;margin:16px}canvas,img{image-rendering:pixelated;display:block;margin:6px 0}
#verdict{font:600 14px system-ui;margin:8px 0}pre{white-space:pre-wrap}</style></head><body>
<div id="verdict">mesure en cours…</div>
<div>Référence (×4) puis rendu courant (×4), même fond :</div>
<img id="ref" src="session-recap-reference.png" width="${REF.size[0] * 4}">
<canvas id="cv"></canvas><canvas id="zoom"></canvas>
<pre id="out"></pre>
<script>
const REF=${JSON.stringify(REF)}, G=${JSON.stringify(PROGRESS_GEOMETRY)}, W=${W};
const SVG=${JSON.stringify(svg)};
const lum=c=>0.299*c[0]+0.587*c[1]+0.114*c[2];
const img=new Image();
img.onload=()=>{
  const H=img.naturalHeight||img.height;
  const cv=document.getElementById('cv'); cv.width=W; cv.height=H;
  const ctx=cv.getContext('2d',{willReadFrequently:true});
  ctx.fillStyle='rgb('+REF.bg.join(',')+')'; ctx.fillRect(0,0,W,H); ctx.drawImage(img,0,0,W,H);
  const d=ctx.getImageData(0,0,W,H).data;
  const at=(x,y)=>{const i=(y*W+x)*4;return [d[i],d[i+1],d[i+2]]};
  // bord gauche de la pastille : première colonne, au milieu de la hauteur, de la couleur unie de l'état (#8b5cf6 attendu)
  const midY=Math.floor(G.trackY+G.trackH/2);
  let badgeLeft=W; for(let x=0;x<W;x++){const c=at(x,midY); if(Math.abs(c[0]-139)<4&&Math.abs(c[1]-92)<4&&Math.abs(c[2]-246)<4){badgeLeft=x;break}}
  const x1=badgeLeft-1;
  const bins=REF.bins.length, out=[]; let eC=0,eG=0,eS=0,eK=0;
  const isCell=(x,y)=>((x-G.inset)%G.pitch+G.pitch)%G.pitch<G.cell && ((y-G.trackY-G.inset)%G.pitch+G.pitch)%G.pitch<G.cell;
  for(let b=0;b<bins;b++){
    const xa=Math.round(b*(x1+1)/bins), xb=Math.round((b+1)*(x1+1)/bins);
    const cell=[],gap=[];
    for(let x=xa;x<xb;x++)for(let y=G.trackY+1;y<G.trackY+G.trackH;y++)(isCell(x,y)?cell:gap).push(at(x,y));
    const mean=L=>L.length?[0,1,2].map(i=>L.reduce((a,c)=>a+c[i],0)/L.length):[0,0,0];
    const cl=cell.map(lum), mu=cl.reduce((a,v)=>a+v,0)/(cl.length||1);
    const sd=Math.sqrt(cl.reduce((a,v)=>a+(v-mu)**2,0)/(cl.length||1));
    const sorted=[...cl].sort((p,q)=>p-q), med=sorted[Math.floor(sorted.length/2)]||0;
    const sp=cl.filter(v=>v>med+14).length/(cl.length||1);
    const cm=mean(cell), gm=mean(gap), r=REF.bins[b];
    const dC=[0,1,2].reduce((a,i)=>a+Math.abs(cm[i]-r.cell[i]),0)/3, dG=[0,1,2].reduce((a,i)=>a+Math.abs(gm[i]-r.gap[i]),0)/3;
    eC+=dC;eG+=dG;eS+=Math.abs(sd-r.cellLumStd);eK+=Math.abs(sp-r.sparkleFrac);
    out.push({t:r.t,cell:cm.map(v=>+v.toFixed(1)),refCell:r.cell,dCell:+dC.toFixed(1),gap:gm.map(v=>+v.toFixed(1)),refGap:r.gap,dGap:+dG.toFixed(1),std:+sd.toFixed(1),refStd:r.cellLumStd,spark:+sp.toFixed(2),refSpark:r.sparkleFrac});
  }
  const score={cellErr:+(eC/bins).toFixed(2),gapErr:+(eG/bins).toFixed(2),stdErr:+(eS/bins).toFixed(2),sparkErr:+(eK/bins).toFixed(3),badgeLeft,fillSamples:x1+1};
  document.getElementById('verdict').textContent='RESULT '+JSON.stringify(score)+'  (objectif: cellErr<6, gapErr<5, stdErr<5, sparkErr<0.1 ; plus bas = plus proche)';
  document.getElementById('out').textContent=out.map(o=>JSON.stringify(o)).join('\\n');
  const z=document.getElementById('zoom'); z.width=W*4; z.height=H*4; const zc=z.getContext('2d'); zc.imageSmoothingEnabled=false; zc.drawImage(cv,0,0,W*4,H*4);
};
img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(SVG);
</script></body></html>`
writeFileSync(new URL('../docs/session-recap-measure.html', import.meta.url), html)
console.log('docs/session-recap-measure.html', html.length)
