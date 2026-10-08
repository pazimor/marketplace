// Replays the events recorded by the phase 1 probe (agents-info plan, 2026-10-02).
import { describe, expect, test } from 'claude-code/testing'
import {
  DEFAULT_OPTIONS,
  MAIN,
  emptyRecap,
  forecast,
  markAlerted,
  onComplete,
  onMeasure,
  onPrompt,
  onSessionStart,
  onSpawn,
  onStep,
  onUsage,
  pendingAlerts,
  readOptions,
  shortModel,
  totals,
  weight,
} from '../hooks/recap'

const SMALL = 'claude-small-1-0-20250101'
const MID = 'claude-mid-5-5'
const usage = (model: string, input: number, output: number, cacheRead = 0, cacheWrite = 0) => ({
  input_tokens: input,
  output_tokens: output,
  cache_read_input_tokens: cacheRead,
  cache_creation_input_tokens: cacheWrite,
  model,
})

/** Recorded session: main → relay (mid-tier model) → leaf on inherit, plus a direct leaf. */
function probeSession() {
  let s = onSessionStart(emptyRecap(), { surface: null, agent: undefined, model: SMALL, at: 0 })
  s = onPrompt(s, { text: 'Use the Agent tool with subagent_type relay', at: 1 })
  s = onStep(s, { model: SMALL, effort: undefined, at: 2 })
  s = onSpawn(s, { agentId: 'relay1', agent: 'relay', model: MID, fork: false, at: 3 })
  s = onStep(s, { agentId: 'relay1', model: MID, effort: 'medium', at: 4 })
  s = onUsage(s, { effort: undefined, usage: usage(SMALL, 10, 283, 22376, 10131) })
  s = onSpawn(s, { agentId: 'leaf1', agent: 'leaf', model: SMALL, fork: false, at: 5 })
  s = onSpawn(s, { agentId: 'leaf2', parentId: 'relay1', agent: 'leaf', model: MID, fork: false, at: 6 })
  s = onStep(s, { agentId: 'leaf2', model: MID, effort: 'medium', at: 7 })
  s = onUsage(s, { agentId: 'relay1', effort: 'medium', usage: usage(MID, 2, 138, 0, 2548) })
  s = onUsage(s, { agentId: 'leaf2', effort: 'medium', usage: usage(MID, 2, 8, 0, 1050) })
  s = onComplete(s, { agentId: 'leaf2', reason: 'answer', at: 8 })
  s = onComplete(s, { agentId: 'leaf1', reason: 'answer', at: 9 })
  s = onPrompt(s, { text: '<task-notification>\n<task-id>leaf1</task-id>', at: 10 })
  return s
}

describe('recap model', () => {
  test('main agent, tree and instances', async () => {
    const s = probeSession()
    expect(s.runs[MAIN]?.agent).toBe('default')
    expect(s.runs[MAIN]?.model).toBe(SMALL)
    expect(s.runs.leaf2?.parentId).toBe('relay1')
    expect(s.runs.leaf1?.parentId).toBe(MAIN)
    expect(s.runs.leaf2?.status).toBe('done')
    expect(s.runs.relay1?.status).toBe('running')
    expect(s.timeline.map(t => t.kind)).toEqual(['new', 'new', 'new'])
  })

  test('task notifications do not count as prompts', async () => {
    expect(probeSession().prompts).toHaveLength(1)
  })

  test('resume via SendMessage: same agentId, no spawn, on the next prompt', async () => {
    let s = probeSession()
    s = onComplete(s, { agentId: 'relay1', reason: 'answer', at: 11 })
    s = onPrompt(s, { text: 'Send a message to the relay', at: 12 })
    s = onStep(s, { agentId: 'relay1', model: SMALL, effort: undefined, at: 13 })
    const last = s.timeline[s.timeline.length - 1]
    expect(last).toEqual({ promptIndex: 2, agentId: 'relay1', kind: 'resumed', at: 13 })
    expect(s.runs.relay1?.resumes).toBe(1)
    expect(s.runs.relay1?.status).toBe('running')
  })

  test('fork', async () => {
    const s = onSpawn(probeSession(), { agentId: 'f', agent: 'general-purpose', model: SMALL, fork: true, at: 20 })
    expect(s.runs.f?.instance).toBe('fork')
  })

  test('usage per agent × model × effort', async () => {
    const s = probeSession()
    const keys = Object.values(s.buckets).map(b => `${b.agent}|${shortModel(b.model)}|${b.effort}`)
    expect(keys).toEqual(['default|small-1-0|—', 'relay|mid-5-5|medium', 'leaf|mid-5-5|medium'])
    expect(totals(s).output).toBe(283 + 138 + 8)
    expect(weight(s.runs.relay1!.tokens)).toBe(2 + 138 + 2548)
  })

  test('limits and forecast', async () => {
    const reset = Date.parse('2026-10-02T07:00:00.000Z')
    const t0 = reset - 4 * 3600_000
    let s = onMeasure(emptyRecap(), { rateLimits: [{ kind: 'five_hour', percentUsed: 10, resetsAt: '2026-10-02T07:00:00.000Z' }], costUsd: 0.1, at: t0 })
    s = onMeasure(s, { rateLimits: [{ kind: 'five_hour', percentUsed: 30, resetsAt: '2026-10-02T07:00:00.000Z' }], at: t0 + 3600_000 })
    const f = forecast(s.limits.five_hour!)
    expect(f.atReset).toBe(90)
    expect(f.exhaustedAt).toBeNull()
    expect(s.costUsd).toBe(0.1)
  })

  test('alerts: limits, unexpected model, main share, raised once', async () => {
    let s = probeSession()
    s = onMeasure(s, { rateLimits: [{ kind: 'seven_day', percentUsed: 84, resetsAt: 'x' }], at: 30 })
    s = onStep(s, { agentId: 'relay1', model: SMALL, effort: undefined, at: 31 })
    s = onUsage(s, { effort: undefined, usage: usage(SMALL, 10, 200, 0, 10000) })
    const o = { ...DEFAULT_OPTIONS, mainShareLimit: 50 }
    const alerts = pendingAlerts(s, o)
    expect(alerts.map(a => a.key.split(':')[0])).toEqual(['limit', 'model', 'main-share'])
    expect(alerts[0]?.text).toContain('7 days at 84%')
    expect(pendingAlerts(markAlerted(s, alerts), o)).toEqual([])
  })

  test('options: defaults and provided values', async () => {
    expect(readOptions(undefined)).toEqual(DEFAULT_OPTIONS)
    expect(readOptions({ limitWarn: 70, modelMismatch: false }).limitWarn).toBe(70)
    expect(readOptions({ modelMismatch: false }).modelMismatch).toBe(false)
  })
})

import { BRAILLE_TRACK, crabSvg, mascotOf, agentFront, installPathsOf, agentDirs, configDirOf, onMascot, onSpawn as spawnRun, emptyRecap as fresh, MASCOT_EMOJI, progressCells, progressSvg, duration, stateHex, STATE_FADE_MS, onPlan, onPlanStep, onToolUse, planProgress, stripRuns, table, workedMs, agentTree, modelBuckets, limitSvg, limitGauge, limitLevel, LIMIT_HEX, usageSvg, USAGE_HEX } from '../hooks/recap'

test('main agent: named by the setting, never inferred from the agents it launches (three peers)', () => {
  let s = onSessionStart(emptyRecap(), { surface: 'desktop', agent: 'default', model: 'm', at: 0 })
  expect(s.runs[MAIN]!.agent).toBe('default')
  s = onSpawn(s, { agentId: 'o1', agent: 'orchestration:orchestrator', model: 'm', fork: false, at: 1 })
  expect(s.runs[MAIN]!.agent).toBe('default')
  // a state saved by an older version, where the main agent was inferred as the scribe, is reset on reload
  s = { ...s, startAgent: 'orchestration:scribe', runs: { ...s.runs, [MAIN]: { ...s.runs[MAIN]!, agent: 'orchestration:scribe' } } }
  s = onSessionStart(s, { surface: 'desktop', agent: undefined, model: 'm', at: 2 })
  expect(s.runs[MAIN]!.agent).toBe('default')
  s = onSessionStart(s, { surface: 'desktop', agent: 'orchestration:scribe', model: 'm', at: 3 })
  expect(s.runs[MAIN]!.agent).toBe('orchestration:scribe')
})

test('worked time: the waits between two resumes are not counted, on both resume paths', () => {
  let s = onSessionStart(emptyRecap(), { surface: 'desktop', agent: undefined, model: 'm', at: 0 })
  s = onSpawn(s, { agentId: 'a', agent: 'orchestration:scribe', model: 'm', fork: false, at: 0 })
  s = onComplete(s, { agentId: 'a', reason: 'answer', at: 2000 })
  expect(workedMs(s.runs.a!, 9000)).toBe(2000)
  s = onSpawn(s, { agentId: 'a', agent: 'orchestration:scribe', model: 'm', fork: false, at: 10_000 }) // resumed by a spawn
  expect(workedMs(s.runs.a!, 10_500)).toBe(2500)
  s = onComplete(s, { agentId: 'a', reason: 'answer', at: 11_000 })
  s = onComplete(s, { agentId: 'a', reason: 'answer', at: 12_000 }) // a second completion adds nothing
  expect(workedMs(s.runs.a!, 50_000)).toBe(3000)
  s = onStep(s, { agentId: 'a', model: 'm', effort: 'low', at: 20_000 }) // resumed by SendMessage
  expect(workedMs(s.runs.a!, 20_500)).toBe(3500)
  expect(workedMs(s.runs[MAIN]!, 20_500)).toBe(20_500)
  // a run saved before the field existed keeps its span
  const old = { ...s.runs.a!, activeMs: undefined, activeSince: undefined, startedAt: 0, endedAt: 4000, status: 'done' as const }
  expect(workedMs(old, 9000)).toBe(4000)
})

test('pane tree: the main agent and its peers at level 0, the others under whoever launched them', () => {
  let s = onSessionStart(emptyRecap(), { surface: 'desktop', agent: undefined, model: 'm', at: 0 })
  s = onSpawn(s, { agentId: 'x', agent: 'Explore', model: 'm', fork: false, at: 1 })
  s = onSpawn(s, { agentId: 'sc', agent: 'orchestration:scribe', model: 'm', fork: false, at: 2 })
  s = onSpawn(s, { agentId: 'or', agent: 'orchestration:orchestrator', model: 'm', fork: false, at: 3 })
  s = onSpawn(s, { agentId: 'e1', parentId: 'or', agent: 'orchestration:executor-low', model: 'm', fork: false, at: 4 })
  s = onSpawn(s, { agentId: 'e2', parentId: 'e1', agent: 'general-purpose', model: 'm', fork: false, at: 5 })
  s = onSpawn(s, { agentId: 'lost', parentId: 'gone', agent: 'general-purpose', model: 'm', fork: false, at: 6 })
  s = onSpawn(s, { agentId: 'sc2', parentId: 'or', agent: 'orchestration:scribe', model: 'm', fork: false, at: 7 }) // a peer launched by a peer
  expect(agentTree(s).map(x => `${x.run.id}:${x.depth}`)).toEqual(['main:0', 'x:1', 'sc:0', 'or:0', 'e1:1', 'e2:2', 'sc2:0', 'lost:0'])
})

test('usage per model × effort: all agents together, heaviest first', () => {
  const s = probeSession()
  const rows = modelBuckets(s).map(b => `${shortModel(b.model)}|${b.effort}|${weight(b.tokens)}|${b.calls}`)
  expect(rows).toEqual([`small-1-0|—|${10 + 283 + 10131}|1`, `mid-5-5|medium|${2 + 138 + 2548 + 2 + 8 + 1050}|2`])
})

test('limit gauge: solid fill in the level color, hatched forecast, one tick per threshold, text twin', () => {
  const reset = Date.parse('2026-10-02T07:00:00.000Z')
  let s = onMeasure(emptyRecap(), { rateLimits: [{ kind: 'five_hour', percentUsed: 40, resetsAt: '2026-10-02T07:00:00.000Z' }], at: reset - 4 * 3600_000 })
  s = onMeasure(s, { rateLimits: [{ kind: 'five_hour', percentUsed: 60, resetsAt: '2026-10-02T07:00:00.000Z' }], at: reset - 3 * 3600_000 })
  const l = s.limits.five_hour! // 60% now, 120% projected at the reset
  const o = { limitWarn: 80, limitCritical: 95 }
  expect(limitLevel(60, o)).toBe('ok')
  expect(limitLevel(84, o)).toBe('warn')
  expect(limitLevel(95, o)).toBe('critical')
  const svg = limitSvg(l, 200, o, 'g1')
  expect(svg).toMatch(/^<svg [^>]*width="200" height="16"/)
  expect(svg).toContain(`<rect width="120" height="16" fill="${LIMIT_HEX.ok}"/>`) // 60% of 200, solid
  expect(svg).toContain(`<rect x="120" width="80" height="16" fill="url(#lhg1)"/>`) // hatched up to 100%
  expect(svg).toContain(`fill="${LIMIT_HEX.critical}" fill-opacity="0.5"`) // the forecast reaches the critical level
  expect(svg.match(/<rect x="\d+" y="0" width="2"/g)).toHaveLength(2)
  expect(svg).not.toContain('<animate')
  expect(limitGauge(l, 10)).toBe('██████▒▒▒▒')
  expect(limitGauge({ ...l, at: l.firstAt }, 10)).toBe('██████░░░░') // no rate yet: no forecast
})

test('usage bar: cache written, output, input stacked against the heaviest, cache read left out', () => {
  const svg = usageSvg({ input: 10, output: 30, cacheRead: 999, cacheWrite: 60 }, 200, 200, { uid: 'u1' })
  expect(svg).toContain(`<rect x="0" width="60" height="8" fill="${USAGE_HEX.cacheWrite}"/>`)
  expect(svg).toContain(`<rect x="60" width="30" height="8" fill="${USAGE_HEX.output}"/>`)
  expect(svg).toContain(`<rect x="90" width="10" height="8" fill="${USAGE_HEX.input}"/>`)
  expect(svg).toContain('<clipPath id="ucu1"><rect width="100"')
  expect(usageSvg({ input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, 50, 0)).toContain('<rect width="0"')
})

test('step plan: progress and moving on to the next step', () => {
  let s = onPlan(emptyRecap(), { title: 't', steps: ['read', 'code', 'verify'], at: 0 })
  expect(planProgress(s.plan!)).toMatchObject({ done: 0, total: 3, percent: 0, index: 1 })
  s = onPlanStep(s, { step: 1, status: 'done', at: 1 })
  expect(planProgress(s.plan!)).toMatchObject({ done: 1, percent: 33, index: 2 })
  expect(planProgress(s.plan!).current!.name).toBe('code')
  s = onPlanStep(s, { step: 'verify', status: 'done', at: 2 })
  expect(s.plan!.steps.map(x => x.status)).toEqual(['done', 'done', 'done'])
  expect(s.plan!.endedAt).toBe(2)
  expect(onPlanStep(s, { step: 9, status: 'done', at: 3 })).toBe(s)
})

test('table aligns the columns', () => {
  expect(table([['a', 'x'], ['bbb', 'yy']], 1)).toEqual(['a     x', 'bbb  yy'])
})

test('phase plan: state kept by name when the plan is sent back, plan state', () => {
  let s = onPlan(emptyRecap(), { title: 't', stages: [{ name: 'Read', steps: ['a', 'b'] }, { name: 'Do', steps: ['c'] }], at: 0 })
  expect(planProgress(s.plan!).stage).toBe('Read')
  s = onPlanStep(s, { step: 'a', status: 'done', at: 5 })
  s = onPlan(s, { stages: [{ name: 'Read', steps: ['a', 'b'] }, { name: 'Do', steps: ['c', 'd'] }], at: 9 })
  expect(s.plan!.steps.map(x => x.status)).toEqual(['done', 'running', 'todo', 'todo'])
  expect(s.plan!.startedAt).toBe(0)
  s = onPlanStep(s, { state: 'input', note: 'waiting for a decision', at: 10 })
  expect(s.plan).toMatchObject({ state: 'input', note: 'waiting for a decision' })
  s = onPlanStep(s, { step: 'b', status: 'failed', at: 11 })
  expect(s.plan!.state).toBe('error')
})

test('sub-agent strips: active, failed, or finished less than 5 s ago', () => {
  let s = onSessionStart(emptyRecap(), { surface: 'desktop', agent: 'orchestration:scribe', model: 'm', at: 0 })
  s = onSpawn(s, { agentId: 'x1', agent: 'executor-low', model: 'm', fork: false, at: 1 })
  s = onToolUse(s, { agentId: 'x1', tool: 'Read' })
  expect(s.runs.x1!.tool).toBe('Read')
  expect(stripRuns(s, 2).map(r => r.id)).toEqual(['x1'])
  s = onComplete(s, { agentId: 'x1', reason: 'end_turn', at: 3000 })
  expect(stripRuns(s, 6000).map(r => r.id)).toEqual(['x1'])
  expect(stripRuns(s, 9000)).toEqual([])
  expect(duration(65_000)).toBe('1 min 05')
})

test('bar weighted by planned agents: advances at each finished agent, capped before the verification', () => {
  let s = onSessionStart(emptyRecap(), { surface: 'desktop', agent: 'orchestration:scribe', model: 'm', at: 0 })
  s = onPlan(s, { isWorkflow: true, steps: [{ name: 'a', agents: 2 }, 'b'], at: 0 })
  s = onSpawn(s, { agentId: 'x1', agent: 'executor-low', model: 'm', fork: false, at: 1, task: 'read the canon' })
  s = onSpawn(s, { agentId: 'x2', agent: 'executor-low', model: 'm', fork: false, at: 1 })
  expect(s.runs.x1!.task).toBe('read the canon')
  expect(planProgress(s.plan!).percent).toBe(0)
  s = onComplete(s, { agentId: 'x1', reason: 'end_turn', at: 2 })
  expect(planProgress(s.plan!)).toMatchObject({ percent: 25, agentsDone: 1, agentsPlanned: 2 })
  s = onComplete(s, { agentId: 'x2', reason: 'end_turn', at: 3 })
  expect(planProgress(s.plan!).percent).toBe(45) // 0.9 / 2 steps, the verification is still to do
  s = onPlanStep(s, { step: 'a', status: 'done', at: 4 })
  expect(planProgress(s.plan!).percent).toBe(50)
})

test('drawn bar: well-formed SVG with phase badge and animated glint, terminal cells', () => {
  let s = onPlan(emptyRecap(), { title: 'L', stages: [{ name: 'Read', steps: ['a', 'b'] }, { name: 'Do', steps: ['c'] }], at: 0 })
  s = onPlanStep(s, { step: 'a', status: 'done', at: 5000 })
  const svg = progressSvg(s.plan!, 300, 9000)
  expect(svg.startsWith('<svg')).toBe(true)
  expect(svg).toContain('>Read<')
  expect(svg).toContain('<animate')
  expect(svg).toContain('✓ a · 5s')
  const cells = progressCells(s.plan!, 20, 3)
  expect(cells.length).toBe(60)
  expect(cells[0]! >= 0x2800 && cells[0]! < 0x2900).toBe(true) // braille
  expect(cells[19 * 3]).toBe(BRAILLE_TRACK) // track
})

test('fixed squares: 5 rows, static left-to-right fade, color wave, no tick marks, braille in the terminal', () => {
  let s = onPlan(emptyRecap(), { title: 'L', stages: [{ name: 'Read', steps: ['a', 'b'] }], at: 0 })
  s = onPlanStep(s, { step: 'a', status: 'done', at: 5000 })
  const svg = progressSvg(s.plan!, 300, 9000)
  expect(svg).toContain('attributeName="transform"')
  expect(svg).toContain('<mask') // static fade
  expect(svg).not.toContain('<pattern')
  expect(svg).not.toContain('<script')
  expect(svg).not.toMatch(/\son\w+=/)
  expect(svg.length).toBeLessThan(131072)
  // no tick marks: only the track, the cells (2×2 on a 4 px pitch, with halo), the hover zones and the badge
  expect(svg).not.toMatch(/width="1" height="\d+" fill="#fff"/)
  expect(svg).not.toMatch(/width="3" height="\d+" rx="1.5"/)
  expect(svg.match(/<rect /g)!.length).toBe(1 + 1 + 1 + 1 + 2 + 1) // fill shape, mask, spark mask, track, 2 hover zones, badge
  // fixed 2×2 cells on a 4 px pitch, offset 1 px from the track (y = 4): 5 rows
  const cells = [...svg.matchAll(/M(\d+) (\d+)h2v2h-2z/g)]
  expect(cells.length).toBeGreaterThan(0)
  expect(new Set(cells.map(m => m[2]))).toEqual(new Set(['5', '9', '13', '17', '21']))
  expect(cells.every(m => Number(m[1]) % 4 === 1)).toBe(true)
  // halo under each cell (4×4 tile + cross): the gaps between cells are tinted, not black
  // tiles merged in runs of the same level, laid on a continuous bed (no visible seam when zoomed)
  const tileCols = [...svg.matchAll(/M(\d+) (\d+)h(\d+)v4h-\3z/g)].reduce((n, m) => n + Number(m[3]) / 4, 0)
  const crossN = [...svg.matchAll(/M(\d+) (\d+)h2v1h1v2h-1v1h-2v-1h-1v-2h1z/g)]
  expect(crossN.length).toBe(cells.length)
  expect(tileCols).toBeLessThanOrEqual(cells.length * 1.1) // spark tiles are counted twice (hole in the bed + layer)
  expect(tileCols).toBeGreaterThan(cells.length / 2)
  expect(svg).toMatch(new RegExp(`<path d="M0 4h${(cells.length / 5) * 4}v20h-${(cells.length / 5) * 4}z[^"]*" fill-rule="evenodd" fill="#[0-9a-f]{6}" fill-opacity="0\\.\\d+"\\/>`))
  // sparks are rare: the path of the lightest cells (solid color, full opacity) holds at most 10%
  const corePaths = [...svg.matchAll(/<path d="((?:M\d+ \d+h2v2h-2z)+)" fill="([^"]+)" fill-opacity="([\d.]+)"\/>/g)]
  const sparkPath = corePaths.find(m => m[3] === '1')
  expect(sparkPath).toBeDefined()
  expect(sparkPath![2]).not.toBe('#ffffff') // white tinted with the state color, not a neutral grey
  expect(sparkPath![1].match(/z/g)!.length / cells.length).toBeLessThanOrEqual(0.1)
  expect(corePaths.length).toBeGreaterThanOrEqual(3) // noise: several levels, not only tint / spark
  // the fade stops at the badge's left edge
  const fade = svg.match(/id="f"[^>]*x2="(\d+)"/)
  expect(Number(fade![1])).toBeGreaterThan(0)
  // fade direction: minimum at the start (left), full against the badge (right), never decreasing
  const ops = [...svg.match(/id="f"[^>]*>(.*?)<\/linearGradient>/)![1]!.matchAll(/stop-opacity="([\d.]+)"/g)].map(m => Number(m[1]))
  expect(ops.length).toBeGreaterThan(2)
  expect(ops.every((o, i) => i === 0 || o >= ops[i - 1]!)).toBe(true)
  expect(ops.at(-1)!).toBeGreaterThan(ops[0]! * 10)
  // the badge (50 px) is at the start of the track and hides the start of the fill: at 50% of 300 px
  // the front is at 25 + 275 / 2 ≈ 163, the fade starts from the middle of the badge
  expect(svg).toContain('<clipPath id="c"><rect x="0" y="4" width="163" height="20" rx="10"/></clipPath>')
  expect(svg).toContain('<rect x="0" y="2" width="50" height="24" rx="12"')
  expect(svg).toMatch(/id="f"[^>]*x1="25"/)
  // sparks: their own fade, already visible at the start, never below the common fade
  const sOps = [...svg.match(/id="s"[^>]*>(.*?)<\/linearGradient>/)![1]!.matchAll(/stop-opacity="([\d.]+)"/g)].map(m => Number(m[1]))
  expect(sOps[0]!).toBeGreaterThanOrEqual(0.08)
  expect(sOps.every((o, i) => o >= ops[i]!)).toBe(true)
  expect(svg).toContain('mask="url(#k)"')
  // at 0% the phase badge is already there, with no fill under it
  const start = progressSvg(onPlan(emptyRecap(), { title: 'L', stages: [{ name: 'Read', steps: ['a', 'b'] }], at: 0 }).plan!, 300, 0)
  expect(start).toContain('>Read<')
  expect(start).toContain('<rect x="0" y="2" width="50"') // the front (25 px) stays under the badge
  const waiting = onPlanStep(s, { state: 'input', note: 'x', at: 6000 })
  expect(progressSvg(waiting.plan!, 300, 9000)).not.toContain('<animateTransform')
  const f1 = progressCells(s.plan!, 20, 0)
  const f2 = progressCells(s.plan!, 20, 1)
  const braille = (w: number) => w >= 0x2800 && w < 0x2900
  expect(braille(f1[0]!)).toBe(true)
  expect(f1[19 * 3]).toBe(BRAILLE_TRACK)
  expect(f1[2]).toBe(0x01000000)
  let moved = false
  for (let i = 0; i < 10; i++) if (f1[i * 3] !== f2[i * 3]) moved = true
  expect(moved).toBe(true)
  // terminal fade: the front of the bar carries more dots than the back
  const dots = (w: number) => (w - 0x2800).toString(2).replace(/0/g, '').length
  const back = [0, 1, 2].reduce((n, i) => n + dots(f1[i * 3]!), 0)
  const front = [7, 8, 9].reduce((n, i) => n + dots(f1[i * 3]!), 0)
  expect(front).toBeGreaterThan(back)
})

test('desktop: SVG source identical from one tick to the next (the isolated frame reloads otherwise), transparent background', () => {
  let s = onPlan(emptyRecap(), { title: 'L', stages: [{ name: 'Read', steps: ['a', 'b'] }], at: 0 })
  s = onPlanStep(s, { step: 'a', status: 'done', at: 5000 })
  expect(progressSvg(s.plan!, 300, 9000)).toBe(progressSvg(s.plan!, 300, 9250))
  expect(progressSvg(s.plan!, 300, 9000)).toBe(progressSvg(s.plan!, 300, 61000))
  expect(progressSvg(s.plan!, 300, 9000)).toContain('color-scheme:light dark')
  expect(crabSvg()).toContain('color-scheme:light dark')
  // state fade: CSS animation, same source during the whole fade, removed afterwards
  const w = onPlanStep(s, { state: 'input', note: 'x', at: 10000 })
  const during = progressSvg(w.plan!, 300, 10000)
  expect(during).toContain('@keyframes')
  expect(progressSvg(w.plan!, 300, 10000 + STATE_FADE_MS / 2)).toBe(during)
  expect(progressSvg(w.plan!, 300, 10000 + STATE_FADE_MS)).not.toContain('@keyframes')
})

test('mascot: pixel-art SVG, animated only when requested', () => {
  expect(crabSvg()).toContain('viewBox')
  expect(crabSvg()).not.toContain('animateTransform')
  expect(crabSvg({ animated: true })).toContain('animateTransform')
  expect(crabSvg({ body: '#ef4444' })).toContain('#ef4444')
})

test('mascot: one outfit per named mascot, the model trade by default, grey once inactive', () => {
  const costume = { haiku: '#2f7de1', sonnet: '#d83a3a', opus: '#26262b', fable: '#6d4ac7' } as const
  for (const [tier, hex] of Object.entries(costume)) {
    expect(crabSvg({ tier: tier as keyof typeof costume })).toContain(hex)
    expect(crabSvg()).not.toContain(hex)
  }
  expect(crabSvg({ tier: 'haiku', animated: true })).toContain('dur="0.35s"')
  expect(crabSvg({ tier: 'opus', animated: true })).toContain('dur="0.7s"')
  // a named mascot takes precedence over the model
  expect(crabSvg({ tier: 'opus', mascot: 'scribe' })).toContain('#6b4a2b')
  expect(crabSvg({ tier: 'opus', mascot: 'scribe' })).not.toContain(costume.opus)
  expect(crabSvg({ tier: 'haiku', mascot: 'chef' })).toContain('#f08bb0')
  expect(crabSvg({ tier: 'sonnet', mascot: 'artist' })).toContain('#c0392b')
  expect(crabSvg({ tier: 'sonnet', mascot: 'inspector' })).toContain('#8a6a3f')
  expect(MASCOT_EMOJI.inspector).toBe('🔍')
  expect(crabSvg({ mascot: 'courier' })).toBe(crabSvg({ tier: 'haiku' }))
  expect(mascotOf({ model: 'claude-sonnet-5-5' })).toBe('artisan')
  expect(mascotOf({ model: 'claude-sonnet-5-5', mascot: 'chef' })).toBe('chef')
  expect(mascotOf({ model: 'claude-opus-5-5', mascot: 'unicorn' })).toBe('scholar')
  expect(MASCOT_EMOJI.artist).toBe('🎨')
  const fills = [crabSvg({ mascot: 'chef', mono: true }), crabSvg({ mascot: 'scribe', mono: true }), crabSvg({ mascot: 'artist', mono: true }), crabSvg({ mascot: 'inspector', mono: true }), crabSvg({ tier: 'fable', mono: true })]
    .flatMap(svg => [...svg.matchAll(/fill="#(..)(..)(..)"/g)])
  expect(fills.length).toBeGreaterThan(0)
  for (const [, r, g, b] of fills) expect(r === g && g === b).toBe(true)
})

test('declared mascot: read from the definition frontmatter, kept on resume', () => {
  expect(agentFront('---\nname: orchestrator\ndescription: >-\n  x\nmodel: haiku\nmascot: chef # for the band\n---\nBody\nmascot: artist\n'))
    .toEqual({ name: 'orchestrator', mascot: 'chef' })
  expect(agentFront('---\nname: x\nmascot: "scribe"\n---\n')).toEqual({ name: 'x', mascot: 'scribe' })
  expect(agentFront('---\nname: x\nmascot: unicorn\n---\n')).toEqual({ name: 'x', mascot: undefined })
  expect(agentFront('no frontmatter')).toEqual({})
  const installed = JSON.stringify({ version: 2, plugins: { 'orchestration@marketplace': [{ scope: 'user', installPath: '/h/.claude/plugins/cache/marketplace/orchestration/0.9.0' }] } })
  expect(installPathsOf(installed)).toEqual({ orchestration: '/h/.claude/plugins/cache/marketplace/orchestration/0.9.0' })
  expect(installPathsOf('not json')).toEqual({})
  const root = '/h/.claude/plugins/cache/marketplace/agents-info/0.8.0'
  expect(configDirOf(root)).toBe('/h/.claude')
  expect(configDirOf('/repo/plugins/agents-info')).toBeUndefined()
  expect(agentDirs('orchestration:scribe', { pluginRoot: '/repo/plugins/agents-info', installPaths: installPathsOf(installed) })).toEqual([
    { dir: '/h/.claude/plugins/cache/marketplace/orchestration/0.9.0/agents', name: 'scribe' },
    { dir: '/repo/plugins/orchestration/agents', name: 'scribe' },
  ])
  expect(agentDirs('relecteur', { pluginRoot: root, configDir: '/h/.claude', sessionRoot: '/p' })).toEqual([
    { dir: '/p/.claude/agents', name: 'relecteur' },
    { dir: '/h/.claude/agents', name: 'relecteur' },
  ])
  let s = spawnRun(fresh(), { agentId: 'a1', agent: 'orchestration:scribe', model: 'claude-haiku-5-5', fork: false, at: 1 })
  s = onMascot(s, { agentId: 'a1', mascot: 'scribe' })
  expect(mascotOf(s.runs['a1']!)).toBe('scribe')
  s = spawnRun(s, { agentId: 'a1', agent: 'orchestration:scribe', model: 'claude-haiku-5-5', fork: false, at: 2 })
  expect(s.runs['a1']!.mascot).toBe('scribe')
  expect(onMascot(s, { agentId: 'unknown', mascot: 'chef' })).toBe(s)
})

test('state change: the color fades from the old one to the new one', () => {
  let s = onPlan(emptyRecap(), { title: 'L', stages: [{ name: 'Read', steps: ['a', 'b'] }], at: 0 })
  expect(stateHex(s.plan!, 5)).toBe('#8b5cf6') // no transition before a change
  s = onPlanStep(s, { state: 'input', note: 'x', at: 1000 })
  expect(s.plan!.prevState).toBe('running')
  expect(stateHex(s.plan!, 1000)).toBe('#8b5cf6') // start: the old color
  const mid = stateHex(s.plan!, 1000 + STATE_FADE_MS / 2)
  expect(mid).not.toBe('#8b5cf6')
  expect(mid).not.toBe('#f59e0b')
  expect(stateHex(s.plan!, 1000 + STATE_FADE_MS)).toBe('#f59e0b') // end: the new one
  const same = onPlanStep(s, { note: 'y', at: 1200 }) // same state: the fade in progress is not restarted
  expect(same.plan!.stateAt).toBe(1000)
})
