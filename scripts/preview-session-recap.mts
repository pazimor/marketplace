// Génère docs/session-recap-preview.html à partir du vrai code de la barre (progressSvg / progressCells).
// Usage : node --experimental-strip-types scripts/preview-session-recap.mts
import { writeFileSync } from 'node:fs'
import {
  emptyRecap, onSpawn, onStep, onComplete, workflowStages, onPlan, onPlanStep, planProgress, progressCells, progressSvg, crabSvg, tierOf, duration, barWidth, cardWidth, stateHex, STATE_FADE_MS, STATE_HEX,
} from '../plugins/session-recap/hooks/recap.ts'

const NOW = 95_000
const stages = [
  { name: 'Lire', steps: ['canon', 'roadmap'] },
  { name: 'Implémenter', steps: [{ name: 'code', agents: 3 }, 'tests'] },
  { name: 'Vérifier', steps: ['revue', 'rapport'] },
]
const names = ['canon', 'roadmap', 'code', 'tests', 'revue', 'rapport']

function scenario(done: number, state: 'running' | 'input' | 'error' | 'done', note = '') {
  let s = onPlan(emptyRecap(), { title: 'Livraison', isWorkflow: true, stages, at: 0 })
  for (let i = 0; i < done; i++) s = onPlanStep(s, { step: names[i]!, status: 'done', at: (i + 1) * 12_000 })
  if (state === 'input' || state === 'error') s = onPlanStep(s, { state, note, at: NOW })
  if (state === 'error') s = onPlanStep(s, { step: names[done]!, status: 'failed', at: NOW })
  return s.plan!
}

const strips = [
  ['🦀', 'haiku-4-5 · low', 'relever les sorties de tests', '(Bash)', '18s'],
  ['🦀', 'sonnet-5-5 · medium', 'implémenter le parseur de plan', '(Edit)', '42s'],
  ['🦀', 'opus-5-5 · high', 'revoir l’architecture du plan', '(Read)', '1 min 12'],
  ['🦀', 'fable-5-1 · xhigh', 'auditer la migration complète', '(Grep)', '2 min 31'],
  ['✓', 'sonnet-5-5 · medium', 'lire le canon', '', '1 min 05'],
  ['✓', 'fable-5-1 · xhigh', 'auditer le canon', '', '3 min 10'],
  ['✓', 'opus-5-5 · high', 'relire la roadmap', '', '2 min 02'],
  ['🦀', 'haiku-4-5 · low', 'écrire les tests du parseur', '(Write)', '12s'],
]

const COLOR = { running: STATE_HEX.running, input: STATE_HEX.input, error: STATE_HEX.error, done: STATE_HEX.done }
const cases = [
  { label: 'En cours (3/6) — carrés animés', plan: scenario(3, 'running'), strips: true },
  { label: 'Début (0/6)', plan: scenario(0, 'running'), strips: true },
  { label: 'Presque fini (5/6)', plan: scenario(5, 'running'), strips: false },
  { label: 'Attend l’utilisateur', plan: scenario(3, 'input', 'décision requise : supprimer ou garder l’ancien format ?'), strips: false },
  { label: 'Erreur', plan: scenario(3, 'error', 'les tests échouent'), strips: false },
  { label: 'Terminé', plan: scenario(6, 'done'), strips: false },
]

const band = (c: (typeof cases)[number]) => {
  const p = planProgress(c.plan)
  const live = c.plan.endedAt === undefined
  const spin = c.plan.state === 'input' ? '?' : c.plan.state === 'error' ? '✗' : c.plan.state === 'done' ? '✓' : '⠋'
  const agents = p.agentsPlanned > 0 ? ` · ${p.agentsDone}/${p.agentsPlanned} agents` : ''
  return `<section class="band">
  <h3>${c.label}</h3>
  <div class="row"><span class="dim">sonnet-5-5 · medium |</span>
    ${progressSvg(c.plan, 420, NOW, String(cases.indexOf(c)))}
    <span style="color:${COLOR[c.plan.state]}">${spin} ${p.percent} % · ${p.done}/${p.total}${agents} · ${duration((c.plan.endedAt ?? NOW) - c.plan.startedAt)}</span>
    <span class="dim close">✕</span></div>
  ${c.strips ? `<div class="grid">${strips.map(x => `<div class="card ${x[0] === '✓' ? 'dim' : ''}">${crabSvg({ body: x[0] === '✓' ? '#8a7f7a' : '#d97757', animated: x[0] !== '✓', tier: tierOf(x[1]), mono: x[0] === '✓' })}<div class="txt"><div class="t">${x[2]}</div><div class="dim">${x[1]}${x[3] ? ' ' + x[3] : ''} — ${x[4]}</div></div></div>`).join('')}</div>` : ''}
</section>`
}

// Toutes les tailles : même plan, bandeau rendu pour 40, 80, 120 et 200 colonnes (largeur de la barre et des cartes calculées comme dans le Mod)
const sizeSections = [40, 80, 120, 200].map(cols => {
  const plan = scenario(3, 'running')
  const w = Math.round(cols * 7.2)
  const cw = cardWidth(cols)
  const per = cw === '100%' ? 100 : cw === '50%' ? 50 : 33.33
  return `<section class="band" style="width:${w}px;max-width:100%"><h3>${cols} colonnes — barre ${barWidth(cols)} px, cartes ${cw}</h3>
  <div class="row" style="justify-content:center">${progressSvg(plan, barWidth(cols), NOW, 's' + cols)}</div>
  <div class="grid">${strips.slice(0, 4).map(x => `<div class="card" style="width:calc(${per}% - 4px)">${crabSvg({ body: '#d97757', animated: true, tier: tierOf(x[1]) })}<div class="txt"><div class="t">${x[2]}</div><div class="dim">${x[1]} — ${x[4]}</div></div></div>`).join('')}</div></section>`
})
const sizes = sizeSections.join('\n')

// Transition : l'état change à T0 ; la barre est rendue à 0, 25, 50, 75 et 100 % du fondu
const T0 = 60_000
const shift = (from: 'running' | 'input', to: 'input' | 'error' | 'done') => {
  let r = { ...emptyRecap(), plan: scenario(3, from) }
  if (to === 'done') for (const n of names.slice(3)) r = onPlanStep(r, { step: n, status: 'done', at: T0 })
  else r = onPlanStep(r, { state: to, note: '', at: T0 })
  return r.plan!
}
const fades = [['En cours → Attend l’utilisateur', 'running', 'input'], ['Attend l’utilisateur → Erreur', 'input', 'error'], ['En cours → Terminé', 'running', 'done']] as const
const transitions = fades.map(([label, from, to]) => {
  const rows = [0, 0.25, 0.5, 0.75, 1].map(f => {
    const p = shift(from, to)
    const t = T0 + f * STATE_FADE_MS
    return `<div class="row" style="margin:4px 0"><span class="dim" style="width:48px">${Math.round(f * 100)} %</span>${progressSvg(p, 360, t, 't' + label.length + f * 100)}<span style="color:${stateHex(p, t)}">■ ${stateHex(p, t)}</span></div>`
  }).join('')
  return `<section class="band"><h3>${label}</h3>${rows}</section>`
}).join('\n')

// Workflow : une section par phase, agents lancés puis emplacements « à venir »
const workflowHtml = (() => {
  let r = onPlan(emptyRecap(), {
    title: 'Livraison', isWorkflow: true, at: 0,
    stages: [
      { name: 'acquisition d’informations', steps: [{ name: 'lecture', agents: 3 }, { name: 'recherche', agents: 2 }] },
      { name: 'développement de features', steps: [{ name: 'code', agents: 3 }] },
      { name: 'tests', steps: [{ name: 'tests', agents: 2 }] },
    ],
  })
  const M = ['claude-haiku-4-5', 'claude-sonnet-5-5', 'claude-opus-5-5']
  const spawn = (id: string, model: string, task: string, effort: string, at: number) => {
    r = onSpawn(r, { agentId: id, agent: 'orchestration:executant', model, fork: false, at, task })
    r = onStep(r, { agentId: id, model, effort, at })
  }
  for (const [i, t] of ['lire le canon', 'lire la roadmap', 'lire le CLAUDE.md'].entries()) {
    spawn('l' + i, M[i % 2]!, t, i % 2 ? 'medium' : 'low', 1000 * (i + 1))
    r = onComplete(r, { agentId: 'l' + i, reason: 'answer', at: 4000 + i * 1000 })
  }
  r = onPlanStep(r, { step: 'lecture', status: 'done', at: 8000 })
  spawn('r0', M[2]!, 'chercher les usages de la barre', 'high', 9000)
  r = onComplete(r, { agentId: 'r0', reason: 'answer', at: 40_000 })
  spawn('r1', M[1]!, 'comparer les rendus existants', 'medium', 41_000)
  const stages = workflowStages(r)
  const p = planProgress(r.plan!)
  return `<section class="band"><h3>Workflow réel — phases, agents lancés et à venir</h3>
  <div class="row" style="justify-content:center">${progressSvg(r.plan!, 420, NOW, 'wf')}</div>
  ${stages.map((st, i) => {
    const head = (st.planned > 0 ? st.done + '/' + st.planned + ' agents · ' : '') + st.name
    const cards = st.runs.map(x => {
      const done = x.status === 'done'
      return `<div class="card ${done ? 'dim' : ''}">${crabSvg({ body: '#d97757', animated: !done, tier: tierOf(x.model), mono: done })}<div class="txt"><div class="t">${x.task ?? x.agent}</div><div class="dim">${x.model.replace('claude-', '')} · ${x.effort} — ${duration((x.endedAt ?? NOW) - x.startedAt)}</div></div></div>`
    }).join('')
    const ph = Array.from({ length: st.placeholders }, (_, k) => `<div class="card dim">${crabSvg({ mono: true })}<div class="txt"><div class="t">agent ${st.runs.length + k + 1} — à venir</div><div class="dim">en attente</div></div></div>`).join('')
    const first = i === 0 ? `<span style="color:${COLOR.running}">⠋ ${p.percent} % · ${head} · 1 min 35:</span>` : `<span class="${st.status === 'todo' ? 'dim' : ''}">${head}:</span>`
    return `<div style="margin-top:10px">${first}<div class="grid">${cards}${ph}</div></div>`
  }).join('')}
  </section>`
})()

// Terminal : Raster = cellules colorées, rejouées image par image.
const running = scenario(3, 'running')
const COLS = 24
const frames: string[] = []
for (let f = 0; f < 48; f++) {
  const w = progressCells(running, COLS, f)
  let html = ''
  for (let i = 0; i < COLS; i++) {
    const ch = String.fromCodePoint(w[i * 3]!)
    const fg = w[i * 3 + 1]!.toString(16).padStart(6, '0')
    html += `<span style="color:#${fg}">${ch}</span>`
  }
  frames.push(html)
}

const html = `<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aperçu barre session-recap</title>
<style>
:root{--bg:#16161c;--fg:#e6e6ee;--dim:#8a8a9a;--card:#1e1e27;--line:#33333f;--ok:#4ade80}
:root[data-theme=light]{--bg:#f6f6f9;--fg:#1c1c24;--dim:#6b6b7a;--card:#fff;--line:#d8d8e2;--ok:#16a34a}
body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;padding:24px 16px 48px}
main{max-width:860px;margin:0 auto}
h1{font:600 16px system-ui,sans-serif;margin:0 0 4px}
p.lead{color:var(--dim);margin:0 0 20px;font-family:system-ui,sans-serif}
h2{font:600 12px system-ui,sans-serif;text-transform:uppercase;letter-spacing:.06em;color:var(--dim);margin:28px 0 10px}
.band{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:0 0 12px}
.band h3{margin:0 0 8px;font:600 12px system-ui,sans-serif;color:var(--dim)}
.row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.dim{color:var(--dim)} .ok{color:var(--ok)} .close{cursor:pointer;margin-left:auto}
.term{background:#0d0d12;color:#ddd;border-radius:8px;padding:10px 14px;display:inline-block;font-size:15px;letter-spacing:0}
button{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px 10px;font:12px system-ui,sans-serif;cursor:pointer;float:right}
svg{display:block}
.grid{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.card{width:calc(33.33% - 4px);box-sizing:border-box;border:1px solid var(--line);border-radius:8px;padding:4px 8px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;font-size:12px}.card{display:flex;align-items:center;gap:8px}.card .txt{min-width:0;overflow:hidden;text-overflow:ellipsis}
</style></head><body><main>
<button id="theme">thème clair / sombre</button><button id="zoom" style="margin-right:6px">zoom ×1</button>
<h1>Barre de progression — session-recap</h1>
<p class="lead">Rendu généré par <code>progressSvg</code> et <code>progressCells</code> (le code du Mod, pas une maquette). Survole les points et la pastille : infobulles nom + durée.</p>
<h2>Desktop — Svg animé (SMIL)</h2>
${cases.map(band).join('\n')}
<h2>Toutes les tailles — largeur de la barre et des cartes</h2>
${sizes}
<h2>Workflow</h2>
${workflowHtml}
<h2>Transition de couleur (fondu de 0,9 s)</h2>
${transitions}
<h2>Terminal — Raster (cellules colorées, image par image)</h2>
<div class="term" id="term">${frames[0]}</div>
</main>
<script>
const F=${JSON.stringify(frames)};let i=0;const t=document.getElementById('term');
setInterval(()=>{i=(i+1)%F.length;t.innerHTML=F[i]},300);
const z=document.getElementById('zoom');let zi=1;z.onclick=()=>{zi=zi%3+1;document.querySelector('main').style.zoom=zi;z.textContent='zoom ×'+zi};
const r=document.documentElement;document.getElementById('theme').onclick=()=>{r.dataset.theme=r.dataset.theme==='light'?'dark':'light'};
</script></body></html>`
// Capture pour le README : le seul bandeau à 80 colonnes, sur fond sombre
const shot = `<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Capture session-recap</title>
<style>:root{--bg:#16161c;--fg:#e6e6ee;--dim:#8a8a9a;--card:#1e1e27;--line:#33333f}
body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;padding:20px;display:inline-block}
${html.match(/\.band\{[^}]*\}[\s\S]*?\.card \.txt\{[^}]*\}/)![0]}
.band{margin:0}svg{display:block}</style></head><body>${sizeSections[1]}</body></html>`
writeFileSync(new URL('../docs/session-recap-screenshot.html', import.meta.url), shot)
writeFileSync(new URL('../docs/session-recap-preview.html', import.meta.url), html)
console.log('docs/session-recap-preview.html', html.length)
