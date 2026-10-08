// Generates docs/agents-info-gallery.html (every state and size), the README band preview docs/agents-info-preview.{html,svg}
// and the README pane preview docs/agents-info-pane-preview.{html,svg} from the Mod's real drawing code (progressSvg,
// progressCells, crabSvg, limitSvg, usageSvg) and model (agentTree, workedMs, forecast…); only the layout is mocked.
// Usage: node --experimental-strip-types scripts/preview-agents-info.mts
import { writeFileSync } from 'node:fs'
import {
  emptyRecap, onSpawn, onStep, onComplete, workflowStages, onPlan, onPlanStep, planProgress, progressCells, progressSvg, crabSvg, tierOf, duration, barWidth, cardWidth, stateHex, STATE_FADE_MS, STATE_HEX,
  MAIN, onSessionStart, onPrompt, onUsage, onMeasure, onMascot, onToolUse, agentTree, modelBuckets, workedMs, forecast, limitLabel, limitLevel, limitSvg, usageSvg,
  LIMIT_HEX, USAGE_HEX, LIMIT_HEIGHT, DEFAULT_OPTIONS, INSTANCE_LABEL, formatTokens, weight, totals, shortModel, mascotOf,
} from '../plugins/agents-info/hooks/recap.ts'
import type { AgentRun, Limit, Recap } from '../plugins/agents-info/hooks/recap.ts'

const NOW = 95_000
const stages = [
  { name: 'Read', steps: ['canon', 'roadmap'] },
  { name: 'Implement', steps: [{ name: 'code', agents: 3 }, 'tests'] },
  { name: 'Verify', steps: ['review', 'report'] },
]
const names = ['canon', 'roadmap', 'code', 'tests', 'review', 'report']

function scenario(done: number, state: 'running' | 'input' | 'error' | 'done', note = '') {
  let s = onPlan(emptyRecap(), { title: 'Delivery', isWorkflow: true, stages, at: 0 })
  for (let i = 0; i < done; i++) s = onPlanStep(s, { step: names[i]!, status: 'done', at: (i + 1) * 12_000 })
  if (state === 'input' || state === 'error') s = onPlanStep(s, { state, note, at: NOW })
  if (state === 'error') s = onPlanStep(s, { step: names[done]!, status: 'failed', at: NOW })
  return s.plan!
}

const strips = [
  ['🦀', 'haiku-4-5 · low', 'collect the test outputs', '(Bash)', '18s'],
  ['🦀', 'sonnet-5-5 · medium', 'implement the plan parser', '(Edit)', '42s'],
  ['🦀', 'opus-5-5 · high', 'review the plan’s architecture', '(Read)', '1 min 12'],
  ['🦀', 'fable-5-1 · xhigh', 'audit the full migration', '(Grep)', '2 min 31'],
  ['✓', 'sonnet-5-5 · medium', 'read the canon', '', '1 min 05'],
  ['✓', 'fable-5-1 · xhigh', 'audit the canon', '', '3 min 10'],
  ['✓', 'opus-5-5 · high', 're-read the roadmap', '', '2 min 02'],
  ['🦀', 'haiku-4-5 · low', 'write the parser tests', '(Write)', '12s'],
]

const COLOR = { running: STATE_HEX.running, input: STATE_HEX.input, error: STATE_HEX.error, done: STATE_HEX.done }
const cases = [
  { label: 'Running (3/6) — animated squares', plan: scenario(3, 'running'), strips: true },
  { label: 'Start (0/6)', plan: scenario(0, 'running'), strips: true },
  { label: 'Almost done (5/6)', plan: scenario(5, 'running'), strips: false },
  { label: 'Waiting for user', plan: scenario(3, 'input', 'decision needed: remove or keep the old format?'), strips: false },
  { label: 'Error', plan: scenario(3, 'error', 'the tests are failing'), strips: false },
  { label: 'Done', plan: scenario(6, 'done'), strips: false },
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
    <span style="color:${COLOR[c.plan.state]}">${spin} ${p.percent}% · ${p.done}/${p.total}${agents} · ${duration((c.plan.endedAt ?? NOW) - c.plan.startedAt)}</span>
    <span class="dim close">✕</span></div>
  ${c.strips ? `<div class="grid">${strips.map(x => `<div class="card ${x[0] === '✓' ? 'dim' : ''}">${crabSvg({ body: x[0] === '✓' ? '#8a7f7a' : '#d97757', animated: x[0] !== '✓', tier: tierOf(x[1]), mono: x[0] === '✓' })}<div class="txt"><div class="t">${x[2]}</div><div class="dim">${x[1]}${x[3] ? ' ' + x[3] : ''} — ${x[4]}</div></div></div>`).join('')}</div>` : ''}
</section>`
}

// All sizes: same plan, band rendered at 40, 80, 120 and 200 columns (bar and card widths computed as in the Mod)
// the main agent's label, on the same line as the bar (as in the Mod)
const BAND_LABEL = 'opus-5-5 · high | '
const sizeSections = [40, 80, 120, 200].map(cols => {
  const plan = scenario(3, 'running')
  const w = Math.round(cols * 7.2)
  const cw = cardWidth(cols)
  const per = cw === '100%' ? 100 : cw === '50%' ? 50 : 33.33
  const bar = barWidth(cols, BAND_LABEL.length + 3)
  return `<section class="band" style="width:${w}px;max-width:100%"><h3>${cols} columns — bar ${bar} px, cards ${cw}</h3>
  <div class="row" style="justify-content:center;gap:6px"><span class="dim">${BAND_LABEL}</span>${progressSvg(plan, bar, NOW, 's' + cols)}<span class="dim">✕</span></div>
  <div class="grid">${strips.slice(0, 4).map(x => `<div class="card" style="width:calc(${per}% - 4px)">${crabSvg({ body: '#d97757', animated: true, tier: tierOf(x[1]) })}<div class="txt"><div class="t">${x[2]}</div><div class="dim">${x[1]} — ${x[4]}</div></div></div>`).join('')}</div></section>`
})
const sizes = sizeSections.join('\n')

// Transition: the state changes at T0; the bar is rendered at 0, 25, 50, 75 and 100% of the fade
const T0 = 60_000
const shift = (from: 'running' | 'input', to: 'input' | 'error' | 'done') => {
  let r = { ...emptyRecap(), plan: scenario(3, from) }
  if (to === 'done') for (const n of names.slice(3)) r = onPlanStep(r, { step: n, status: 'done', at: T0 })
  else r = onPlanStep(r, { state: to, note: '', at: T0 })
  return r.plan!
}
const fades = [['Running → Waiting for user', 'running', 'input'], ['Waiting for user → Error', 'input', 'error'], ['Running → Done', 'running', 'done']] as const
const transitions = fades.map(([label, from, to]) => {
  const rows = [0, 0.25, 0.5, 0.75, 1].map(f => {
    const p = shift(from, to)
    const t = T0 + f * STATE_FADE_MS
    return `<div class="row" style="margin:4px 0"><span class="dim" style="width:48px">${Math.round(f * 100)}%</span>${progressSvg(p, 360, t, 't' + label.length + f * 100)}<span style="color:${stateHex(p, t)}">■ ${stateHex(p, t)}</span></div>`
  }).join('')
  return `<section class="band"><h3>${label}</h3>${rows}</section>`
}).join('\n')

// Workflow: one section per phase, agents launched first, then upcoming slots
const workflowHtml = (() => {
  let r = onPlan(emptyRecap(), {
    title: 'Delivery', isWorkflow: true, at: 0,
    stages: [
      { name: 'information gathering', steps: [{ name: 'reading', agents: 3 }, { name: 'research', agents: 2 }] },
      { name: 'feature development', steps: [{ name: 'code', agents: 3 }] },
      { name: 'tests', steps: [{ name: 'tests', agents: 2 }] },
    ],
  })
  const M = ['claude-haiku-4-5', 'claude-sonnet-5-5', 'claude-opus-5-5']
  const spawn = (id: string, model: string, task: string, effort: string, at: number) => {
    r = onSpawn(r, { agentId: id, agent: 'orchestration:executor', model, fork: false, at, task })
    r = onStep(r, { agentId: id, model, effort, at })
  }
  for (const [i, t] of ['read the canon', 'read the roadmap', 'read CLAUDE.md'].entries()) {
    spawn('l' + i, M[i % 2]!, t, i % 2 ? 'medium' : 'low', 1000 * (i + 1))
    r = onComplete(r, { agentId: 'l' + i, reason: 'answer', at: 4000 + i * 1000 })
  }
  r = onPlanStep(r, { step: 'lecture', status: 'done', at: 8000 })
  spawn('r0', M[2]!, 'find the uses of the progress bar', 'high', 9000)
  r = onComplete(r, { agentId: 'r0', reason: 'answer', at: 40_000 })
  spawn('r1', M[1]!, 'compare the existing renders', 'medium', 41_000)
  const stages = workflowStages(r)
  const p = planProgress(r.plan!)
  return `<section class="band"><h3>Real workflow — phases, agents launched and upcoming</h3>
  <div class="row" style="justify-content:center">${progressSvg(r.plan!, 420, NOW, 'wf')}</div>
  ${stages.map((st, i) => {
    const head = (st.planned > 0 ? st.done + '/' + st.planned + ' agents · ' : '') + st.name
    const cards = st.runs.map(x => {
      const done = x.status === 'done'
      return `<div class="card ${done ? 'dim' : ''}">${crabSvg({ body: '#d97757', animated: !done, tier: tierOf(x.model), mono: done })}<div class="txt"><div class="t">${x.task ?? x.agent}</div><div class="dim">${x.model.replace('claude-', '')} · ${x.effort} — ${duration((x.endedAt ?? NOW) - x.startedAt)}</div></div></div>`
    }).join('')
    const ph = Array.from({ length: st.placeholders }, (_, k) => `<div class="card dim">${crabSvg({ mono: true })}<div class="txt"><div class="t">agent ${st.runs.length + k + 1} — upcoming</div><div class="dim">waiting</div></div></div>`).join('')
    const first = i === 0 ? `<span style="color:${COLOR.running}">⠋ ${p.percent}% · ${head} · 1 min 35:</span>` : `<span class="${st.status === 'todo' ? 'dim' : ''}">${head}:</span>`
    return `<div style="margin-top:10px">${first}<div class="grid">${cards}${ph}</div></div>`
  }).join('')}
  </section>`
})()

// Terminal: Raster = colored cells, replayed frame by frame.
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

// --- The /agents-info pane -----------------------------------------------------------------------
// A session: the main agent, the scribe (resumed), the orchestrator and two executors under it, two limit windows.
const paneRecap = (() => {
  const T0 = Date.parse('2026-10-08T10:00:00Z')
  const at = (min: number) => T0 + min * 60_000
  const M = { haiku: 'claude-haiku-5-5', sonnet: 'claude-sonnet-5-5', opus: 'claude-opus-5-5' }
  const u = (model: string, input: number, output: number, cacheRead: number, cacheWrite: number) => ({
    input_tokens: input, output_tokens: output, cache_read_input_tokens: cacheRead, cache_creation_input_tokens: cacheWrite, model,
  })
  let r: Recap = onSessionStart(emptyRecap(), { surface: 'desktop', agent: undefined, model: M.opus, at: at(0) })
  r = onStep(r, { model: M.opus, effort: 'high', at: at(0) })
  r = onUsage(r, { effort: 'high', usage: u(M.opus, 1200, 9800, 820_000, 64_000) })
  r = onPrompt(r, { text: 'Redo the /agents-info pane on the model of the band SVG', at: at(1) })
  r = onSpawn(r, { agentId: 'sc', agent: 'orchestration:scribe', model: M.haiku, fork: false, at: at(2), task: 'read the canon and the roadmap' })
  r = onMascot(r, { agentId: 'sc', mascot: 'scribe' })
  r = onStep(r, { agentId: 'sc', model: M.haiku, effort: 'xhigh', at: at(2) })
  r = onUsage(r, { agentId: 'sc', effort: 'xhigh', usage: u(M.haiku, 900, 3100, 140_000, 49_000) })
  r = onComplete(r, { agentId: 'sc', reason: 'answer', at: at(4) })
  r = onPrompt(r, { text: 'Go, implement it with tests', at: at(10) })
  r = onSpawn(r, { agentId: 'or', agent: 'orchestration:orchestrator', model: M.opus, fork: false, at: at(17), task: 'deliver the pane redesign' })
  r = onMascot(r, { agentId: 'or', mascot: 'chef' })
  r = onStep(r, { agentId: 'or', model: M.opus, effort: 'high', at: at(17) })
  r = onUsage(r, { agentId: 'or', effort: 'high', usage: u(M.opus, 2100, 7400, 310_000, 53_000) })
  r = onSpawn(r, { agentId: 'e1', parentId: 'or', agent: 'orchestration:executor-medium', model: M.sonnet, fork: false, at: at(80), task: 'implement the pane layout' })
  r = onStep(r, { agentId: 'e1', model: M.sonnet, effort: 'medium', at: at(80) })
  r = onUsage(r, { agentId: 'e1', effort: 'medium', usage: u(M.sonnet, 1500, 12_400, 260_000, 45_000) })
  r = onToolUse(r, { agentId: 'e1', tool: 'Edit' })
  r = onSpawn(r, { agentId: 'e2', parentId: 'or', agent: 'orchestration:executor-low', model: M.haiku, fork: false, at: at(93), task: 'write the render tests' })
  r = onStep(r, { agentId: 'e2', model: M.haiku, effort: 'low', at: at(93) })
  r = onUsage(r, { agentId: 'e2', effort: 'low', usage: u(M.haiku, 400, 2200, 41_000, 45_000) })
  r = onToolUse(r, { agentId: 'e2', tool: 'Write' })
  r = onSpawn(r, { agentId: 'sc', agent: 'orchestration:scribe', model: M.haiku, fork: false, at: at(94), task: 'note the gauge decision' })
  r = onStep(r, { agentId: 'sc', model: M.haiku, effort: 'xhigh', at: at(94) })
  r = onUsage(r, { agentId: 'sc', effort: 'xhigh', usage: u(M.haiku, 300, 800, 49_000, 2_000) })
  r = onComplete(r, { agentId: 'sc', reason: 'answer', at: at(95) })
  const reset5h = '2026-10-08T13:00:00Z'
  const reset7d = '2026-10-10T08:00:00Z'
  r = onMeasure(r, { rateLimits: [{ kind: 'five_hour', percentUsed: 41, resetsAt: reset5h }, { kind: 'seven_day', percentUsed: 79, resetsAt: reset7d }], costUsd: 3.42, at: at(5) })
  r = onMeasure(r, { rateLimits: [{ kind: 'five_hour', percentUsed: 63, resetsAt: reset5h }, { kind: 'seven_day', percentUsed: 84, resetsAt: reset7d }], costUsd: 3.42, at: at(95) })
  return { recap: r, now: at(95) }
})()

const escText = (t: string) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
// fixed UTC times, so that the preview does not depend on the machine that generates it
const clock = (ms: number) => new Date(ms).toISOString().slice(11, 16)
const dayClock = (ms: number) => `${new Date(ms).toISOString().slice(5, 10)} ${clock(ms)}`
const shortAgent = (agent: string) => agent.replace(/^orchestration:/, '')
const PANE_CSS = `.pane{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;box-sizing:border-box;font-size:13px}
.pane .hd{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.pane h4{font:600 11px system-ui,sans-serif;text-transform:uppercase;letter-spacing:.06em;color:var(--dim);margin:12px 0 6px;border-top:1px solid var(--line);padding-top:10px}
.pane h4 .tw{display:inline-block;width:14px;color:var(--fg)}.pane h4 .sum{text-transform:none;letter-spacing:0;font-weight:400}
.pane .txt{min-width:0;overflow:hidden;flex:1}.pane .txt>div{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pane .sm{font-size:11px}
.lim{display:flex;align-items:center;gap:8px}.lim .lk{width:52px;color:var(--dim);font-size:12px}.lim .pc{width:34px;text-align:right;font-weight:600}
.lsub{font-size:11px;margin:0 0 6px 60px}
.acard{display:flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:8px;padding:4px 8px;margin-bottom:5px;font-size:12px}
.acard.off{opacity:.62}.acard.main{border-color:#55556a}.acard .bar{margin-top:3px}
.acard .side{color:var(--dim);font-size:11px;text-align:right;white-space:nowrap;padding-left:6px}.branch{color:var(--dim);margin-right:-4px}
.prow{display:flex;gap:8px;font-size:12px}.prow .pi{color:var(--dim)}.prow .pt{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chips{display:flex;flex-wrap:wrap;gap:4px;margin:3px 0 8px 22px}
.chip{display:inline-flex;align-items:center;gap:4px;border:1px solid var(--line);border-radius:10px;padding:0 7px 0 4px;font-size:11px}
.chip.resumed{border-style:dashed}.chip.fork{border-color:#8b5cf6}
.urow{display:flex;align-items:center;gap:8px;font-size:12px;margin-bottom:4px}.urow .un{flex:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.urow .uv{margin-left:auto;white-space:nowrap}
.legend{font-size:11px;margin:2px 0 8px}.legend i{display:inline-block;width:8px;height:8px;border-radius:2px;margin:0 3px 0 8px}.legend i:first-child{margin-left:0}`

/** The pane at `cols` columns, every section open: the layout register.tsx draws, mocked in HTML around the Mod's own drawings. */
function paneHtml(cols: number, uid: string): string {
  const { recap: r, now } = paneRecap
  const W = Math.round(cols * 7.2)
  const inner = W - 30
  const main = r.runs[MAIN]!
  const all = totals(r)
  const total = weight(all)
  const runs = Object.values(r.runs)
  const active = runs.filter(x => x.id !== MAIN && x.status === 'running').length
  const section = (name: string, summary: string, body: string) =>
    `<h4><span class="tw">▾</span>${name}<span class="dim sum"> · ${summary}</span></h4>${body}`
  // limits
  const limits = Object.values(r.limits).map((l: Limit, i) => {
    const f = forecast(l)
    const reset = l.resetsAt === undefined ? NaN : Date.parse(l.resetsAt)
    const tail = f.exhaustedAt !== null
      ? `<span style="color:${LIMIT_HEX.critical}">full ≈ ${clock(f.exhaustedAt)}</span>`
      : f.atReset !== null ? `→ ${f.atReset}% at reset` : ''
    return `<div class="lim"><span class="lk">${limitLabel(l.kind)}</span>${limitSvg(l, inner - 104, DEFAULT_OPTIONS, `${uid}l${i}`)}<span class="pc" style="color:${LIMIT_HEX[limitLevel(l.percentUsed, DEFAULT_OPTIONS)]}">${l.percentUsed}%</span></div>
<div class="lsub dim">resets ${l.kind === 'five_hour' ? clock(reset) : dayClock(reset)}${tail ? ` · ${tail}` : ''}</div>`
  }).join('')
  // agents: three peers at level 0, a usage bar on each card scaled against the heaviest agent
  const maxAgent = Math.max(...runs.map(x => weight(x.tokens)))
  const kind = (x: AgentRun) =>
    x.id === MAIN ? `${x.agent} · session` : `${shortAgent(x.agent)}${x.resumes > 0 ? ` · ${INSTANCE_LABEL.resumed} ×${x.resumes + 1}` : x.instance !== 'new' ? ` · ${INSTANCE_LABEL[x.instance]}` : ''} · #${x.promptIndex}`
  const agents = agentTree(r).map(({ run: x, depth }, i) => {
    const off = x.status !== 'running'
    const crab = crabSvg({ body: x.status === 'failed' ? '#ef4444' : off ? '#8a7f7a' : '#d97757', animated: !off, mascot: mascotOf(x), mono: off })
    const mark = x.status === 'failed' ? ' ✗' : off ? ' ✓' : ''
    const tool = x.tool !== undefined && !off ? ` (${x.tool})` : ''
    const barW = inner - depth * 18 - 190
    return `<div class="acard${off ? ' off' : ''}${x.id === MAIN ? ' main' : ''}" style="margin-left:${depth * 18}px">${depth > 0 ? '<span class="branch">└</span>' : ''}${crab}
<div class="txt"><div>${escText(x.id === MAIN ? 'main agent' : (x.task ?? x.agent))}${mark}</div><div class="dim">${shortModel(x.model)} · ${x.effort}${tool}</div><div class="dim sm">${escText(kind(x))}</div>
<div class="bar">${usageSvg(x.tokens, barW, maxAgent, { height: 6, uid: `${uid}a${i}` })}</div></div>
<div class="side"><div>${duration(workedMs(x, now))}</div><div>${formatTokens(weight(x.tokens))} · ${Math.round((100 * weight(x.tokens)) / total)}%</div></div></div>`
  }).join('')
  // prompts: one chip per agent launched or resumed
  const prompts = r.prompts.slice(-3).map(p => {
    const chips = r.timeline.filter(t => t.promptIndex === p.index).map(t => {
      const x = r.runs[t.agentId]!
      return `<span class="chip ${t.kind}">${crabSvg({ height: 14, mascot: mascotOf(x), mono: x.status !== 'running' })}${INSTANCE_LABEL[t.kind]} ${shortAgent(x.agent)}</span>`
    }).join('')
    return `<div class="prow"><span class="pi">#${p.index}</span><span class="pt">${escText(p.text)}</span><span class="dim">${clock(p.at)}</span></div><div class="chips">${chips || '<span class="dim">main agent only</span>'}</div>`
  }).join('')
  // usage: the session as a whole, then per model × effort
  const legend = (['cacheWrite', 'output', 'input'] as const)
    .map(k => `<i style="background:${USAGE_HEX[k]}"></i>${k === 'cacheWrite' ? 'cache written' : k} ${formatTokens(all[k])}`).join(' ')
  const models = modelBuckets(r)
  const maxModel = Math.max(...models.map(b => weight(b.tokens)))
  const usage = `<div class="urow">${usageSvg(all, inner - 90, total, { height: 10, uid: `${uid}t` })}<span class="uv"><b>${formatTokens(total)}</b> tok</span></div>
<div class="legend dim">${legend} · cache read ${formatTokens(all.cacheRead)} not counted${r.costUsd !== null ? ` · $${r.costUsd.toFixed(2)}` : ''}</div>
${models.map((b, i) => `<div class="urow">${crabSvg({ height: 18, mascot: mascotOf({ model: b.model }) })}<span class="un" style="width:${cols < 80 ? 130 : 170}px">${shortModel(b.model)}<span class="dim"> · ${b.effort}</span></span>${usageSvg(b.tokens, inner - (cols < 80 ? 130 : 170) - 120, maxModel, { height: 8, uid: `${uid}m${i}` })}<span class="uv">${formatTokens(weight(b.tokens))} <span class="dim">${Math.round((100 * weight(b.tokens)) / total)}%</span></span></div>`).join('')}`
  return `<section class="pane" style="width:${W}px">
<div class="hd"><b>Session</b><span class="dim">${formatTokens(total)} tok${r.costUsd !== null ? ` · $${r.costUsd.toFixed(2)}` : ''} · ${duration(workedMs(main, now))}</span></div>
${section('Limits', Object.values(r.limits).map(l => `${limitLabel(l.kind)} ${l.percentUsed}%`).join(' · '), limits)}
${section('Agents', `${active} active / ${runs.length - 1}`, agents)}
${section('Prompts', `${r.prompts.length} prompt(s)`, prompts)}
${section('Usage', `${formatTokens(total)} tok`, usage)}
</section>`
}

const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>agents-info progress bar preview</title>
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
${PANE_CSS}
</style></head><body><main>
<button id="theme">light / dark theme</button><button id="zoom" style="margin-right:6px">zoom ×1</button>
<h1>Progress bar — agents-info</h1>
<p class="lead">Rendered by <code>progressSvg</code> and <code>progressCells</code> (the Mod's code, not a mock-up). Hover over the dots and the badge: tooltips show the name and duration.</p>
<h2>Desktop — animated SVG (SMIL)</h2>
${cases.map(band).join('\n')}
<h2>All sizes — width of the bar and the cards</h2>
${sizes}
<h2>Workflow</h2>
${workflowHtml}
<h2>Color transition (0.9 s fade)</h2>
${transitions}
<h2>/agents-info pane — docked (56 columns) and wide (100 columns)</h2>
<div class="row" style="align-items:flex-start;gap:16px">${paneHtml(56, 'g56')}${paneHtml(100, 'g100')}</div>
<h2>Terminal — Raster (colored cells, frame by frame)</h2>
<div class="term" id="term">${frames[0]}</div>
</main>
<script>
const F=${JSON.stringify(frames)};let i=0;const t=document.getElementById('term');
setInterval(()=>{i=(i+1)%F.length;t.innerHTML=F[i]},300);
const z=document.getElementById('zoom');let zi=1;z.onclick=()=>{zi=zi%3+1;document.querySelector('main').style.zoom=zi;z.textContent='zoom ×'+zi};
const r=document.documentElement;document.getElementById('theme').onclick=()=>{r.dataset.theme=r.dataset.theme==='light'?'dark':'light'};
</script></body></html>`
// README preview: the band above the prompt at 80 columns, on a dark background — progress bar and mascots
// drawn by the Mod's code (progressSvg, crabSvg). Written as HTML, and as an SVG image (HTML in a
// foreignObject) because GitHub shows an SVG image in a README but never an HTML file.
const PREVIEW_COLS = 80
const PREVIEW_W = 608 // band (576 px = 80 columns) + 2 × 16 px of margin
const PREVIEW_H = 212 // measured in a browser (208 px): bump it if the band grows
const previewBand = (() => {
  const plan = scenario(3, 'running')
  const p = planProgress(plan)
  const per = cardWidth(PREVIEW_COLS) === '100%' ? 100 : cardWidth(PREVIEW_COLS) === '50%' ? 50 : 33.33
  return `<section class="band" style="width:${Math.round(PREVIEW_COLS * 7.2)}px">
  <div class="row" style="justify-content:center;gap:6px"><span class="dim">${BAND_LABEL}</span>${progressSvg(plan, barWidth(PREVIEW_COLS, BAND_LABEL.length + 3), NOW, 'readme')}<span class="dim">✕</span></div>
  <div style="text-align:center;color:${COLOR.running}">⠋ ${p.percent}% · ${p.done}/${p.total} · ${p.agentsDone}/${p.agentsPlanned} agents · ${duration(NOW - plan.startedAt)}</div>
  <div class="grid">${strips.slice(0, 4).map(x => `<div class="card" style="width:calc(${per}% - 3px)">${crabSvg({ body: '#d97757', animated: true, tier: tierOf(x[1]) })}<div class="txt"><div class="t">${x[2]}</div><div class="dim">${x[1]} ${x[3]} — ${x[4]}</div></div></div>`).join('')}</div>
</section>`
})()
const previewCss = `.page{--bg:#16161c;--fg:#e6e6ee;--dim:#8a8a9a;--card:#1e1e27;--line:#33333f;--ok:#16a34a;box-sizing:border-box;width:${PREVIEW_W}px;padding:16px;background:var(--bg);color:var(--fg);font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
${html.match(/\.band\{[^}]*\}[\s\S]*?\.card \.txt\{[^}]*\}/)![0]}
.band{margin:0;box-sizing:border-box}svg{display:block}.card .txt>div{overflow:hidden;text-overflow:ellipsis}`
const preview = `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>agents-info preview</title>
<style>body{margin:0;display:inline-block}${previewCss}</style></head><body><div class="page">${previewBand}</div></body></html>`
const previewSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="${PREVIEW_W}" height="${PREVIEW_H}" viewBox="0 0 ${PREVIEW_W} ${PREVIEW_H}">
<foreignObject x="0" y="0" width="${PREVIEW_W}" height="${PREVIEW_H}"><div xmlns="http://www.w3.org/1999/xhtml" class="page" style="height:${PREVIEW_H}px">
<style><![CDATA[${previewCss}]]></style>${previewBand}</div></foreignObject></svg>`
// README preview of the /agents-info pane: wide (100 columns), every section open, same SVG-in-foreignObject trick.
const PANE_COLS = 100
const PANE_W = Math.round(PANE_COLS * 7.2) + 32
const PANE_H = 922 // measured in a browser (.page height): bump it if the pane grows
const paneCss = `.page{--bg:#16161c;--fg:#e6e6ee;--dim:#8a8a9a;--card:#1e1e27;--line:#33333f;box-sizing:border-box;width:${PANE_W}px;padding:16px;background:var(--bg);color:var(--fg);font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
.dim{color:var(--dim)}svg{display:block;flex:none}b{font-weight:700}
${PANE_CSS}`
const paneBody = paneHtml(PANE_COLS, 'readme')
const panePreview = `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>agents-info pane preview</title>
<style>body{margin:0;display:inline-block}${paneCss}</style></head><body><div class="page">${paneBody}</div></body></html>`
const panePreviewSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="${PANE_W}" height="${PANE_H}" viewBox="0 0 ${PANE_W} ${PANE_H}">
<foreignObject x="0" y="0" width="${PANE_W}" height="${PANE_H}"><div xmlns="http://www.w3.org/1999/xhtml" class="page" style="height:${PANE_H}px">
<style><![CDATA[${paneCss}]]></style>${paneBody}</div></foreignObject></svg>`
writeFileSync(new URL('../docs/agents-info-pane-preview.html', import.meta.url), panePreview)
writeFileSync(new URL('../docs/agents-info-pane-preview.svg', import.meta.url), panePreviewSvg)
writeFileSync(new URL('../docs/agents-info-preview.html', import.meta.url), preview)
writeFileSync(new URL('../docs/agents-info-preview.svg', import.meta.url), previewSvg)
writeFileSync(new URL('../docs/agents-info-gallery.html', import.meta.url), html)
console.log('docs/agents-info-gallery.html', html.length)
