// Rejoue les événements relevés par la sonde de phase 1 (plan session-recap, 2026-10-02).
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

/** Session relevée : principal → relais (modèle intermédiaire) → feuille en inherit, plus une feuille directe. */
function probeSession() {
  let s = onSessionStart(emptyRecap(), { surface: null, agent: undefined, model: SMALL, at: 0 })
  s = onPrompt(s, { text: 'Utilise l outil Agent avec subagent_type relais', at: 1 })
  s = onStep(s, { model: SMALL, effort: undefined, at: 2 })
  s = onSpawn(s, { agentId: 'relais1', agent: 'relais', model: MID, fork: false, at: 3 })
  s = onStep(s, { agentId: 'relais1', model: MID, effort: 'medium', at: 4 })
  s = onUsage(s, { effort: undefined, usage: usage(SMALL, 10, 283, 22376, 10131) })
  s = onSpawn(s, { agentId: 'feuille1', agent: 'feuille', model: SMALL, fork: false, at: 5 })
  s = onSpawn(s, { agentId: 'feuille2', parentId: 'relais1', agent: 'feuille', model: MID, fork: false, at: 6 })
  s = onStep(s, { agentId: 'feuille2', model: MID, effort: 'medium', at: 7 })
  s = onUsage(s, { agentId: 'relais1', effort: 'medium', usage: usage(MID, 2, 138, 0, 2548) })
  s = onUsage(s, { agentId: 'feuille2', effort: 'medium', usage: usage(MID, 2, 8, 0, 1050) })
  s = onComplete(s, { agentId: 'feuille2', reason: 'answer', at: 8 })
  s = onComplete(s, { agentId: 'feuille1', reason: 'answer', at: 9 })
  s = onPrompt(s, { text: '<task-notification>\n<task-id>feuille1</task-id>', at: 10 })
  return s
}

describe('modèle du récap', () => {
  test('agent principal, arbre et instances', async () => {
    const s = probeSession()
    expect(s.runs[MAIN]?.agent).toBe('défaut')
    expect(s.runs[MAIN]?.model).toBe(SMALL)
    expect(s.runs.feuille2?.parentId).toBe('relais1')
    expect(s.runs.feuille1?.parentId).toBe(MAIN)
    expect(s.runs.feuille2?.status).toBe('done')
    expect(s.runs.relais1?.status).toBe('running')
    expect(s.timeline.map(t => t.kind)).toEqual(['nouvelle', 'nouvelle', 'nouvelle'])
  })

  test('les notifications de tâche ne comptent pas comme prompts', async () => {
    expect(probeSession().prompts).toHaveLength(1)
  })

  test('reprise par SendMessage : même agentId, sans spawn, sur le prompt suivant', async () => {
    let s = probeSession()
    s = onComplete(s, { agentId: 'relais1', reason: 'answer', at: 11 })
    s = onPrompt(s, { text: 'Envoie un message au relais', at: 12 })
    s = onStep(s, { agentId: 'relais1', model: SMALL, effort: undefined, at: 13 })
    const last = s.timeline[s.timeline.length - 1]
    expect(last).toEqual({ promptIndex: 2, agentId: 'relais1', kind: 'reprise', at: 13 })
    expect(s.runs.relais1?.resumes).toBe(1)
    expect(s.runs.relais1?.status).toBe('running')
  })

  test('fork', async () => {
    const s = onSpawn(probeSession(), { agentId: 'f', agent: 'general-purpose', model: SMALL, fork: true, at: 20 })
    expect(s.runs.f?.instance).toBe('fork')
  })

  test('consommation par agent × modèle × effort', async () => {
    const s = probeSession()
    const keys = Object.values(s.buckets).map(b => `${b.agent}|${shortModel(b.model)}|${b.effort}`)
    expect(keys).toEqual(['défaut|small-1-0|—', 'relais|mid-5-5|medium', 'feuille|mid-5-5|medium'])
    expect(totals(s).output).toBe(283 + 138 + 8)
    expect(weight(s.runs.relais1!.tokens)).toBe(2 + 138 + 2548)
  })

  test('limites et prévision', async () => {
    const reset = Date.parse('2026-10-02T07:00:00.000Z')
    const t0 = reset - 4 * 3600_000
    let s = onMeasure(emptyRecap(), { rateLimits: [{ kind: 'five_hour', percentUsed: 10, resetsAt: '2026-10-02T07:00:00.000Z' }], costUsd: 0.1, at: t0 })
    s = onMeasure(s, { rateLimits: [{ kind: 'five_hour', percentUsed: 30, resetsAt: '2026-10-02T07:00:00.000Z' }], at: t0 + 3600_000 })
    const f = forecast(s.limits.five_hour!)
    expect(f.atReset).toBe(90)
    expect(f.exhaustedAt).toBeNull()
    expect(s.costUsd).toBe(0.1)
  })

  test('alertes : limites, modèle inattendu, part du principal, une seule fois', async () => {
    let s = probeSession()
    s = onMeasure(s, { rateLimits: [{ kind: 'seven_day', percentUsed: 84, resetsAt: 'x' }], at: 30 })
    s = onStep(s, { agentId: 'relais1', model: SMALL, effort: undefined, at: 31 })
    s = onUsage(s, { effort: undefined, usage: usage(SMALL, 10, 200, 0, 10000) })
    const o = { ...DEFAULT_OPTIONS, mainShareLimit: 50 }
    const alerts = pendingAlerts(s, o)
    expect(alerts.map(a => a.key.split(':')[0])).toEqual(['limit', 'model', 'main-share'])
    expect(alerts[0]?.text).toContain('7 jours à 84 %')
    expect(pendingAlerts(markAlerted(s, alerts), o)).toEqual([])
  })

  test('options : défauts et valeurs fournies', async () => {
    expect(readOptions(undefined)).toEqual(DEFAULT_OPTIONS)
    expect(readOptions({ limitWarn: 70, modelMismatch: false }).limitWarn).toBe(70)
    expect(readOptions({ modelMismatch: false }).modelMismatch).toBe(false)
  })
})

import { BRAILLE_TRACK, crabSvg, progressCells, progressSvg, duration, isScribe, stateHex, STATE_FADE_MS, onPlan, onPlanStep, onToolUse, planProgress, stripRuns, table } from '../hooks/recap'

test('agent principal : nommé, ou déduit du lancement de l\'orchestrateur', () => {
  let s = onSessionStart(emptyRecap(), { surface: 'desktop', agent: 'default', model: 'm', at: 0 })
  expect(s.runs[MAIN]!.agent).toBe('défaut')
  s = onSpawn(s, { agentId: 'o1', agent: 'orchestration:orchestrateur', model: 'm', fork: false, at: 1 })
  expect(s.runs[MAIN]!.agent).toBe('orchestration:scribe')
  expect(s.startInferred).toBe(true)
  expect(isScribe(s.runs[MAIN]!.agent)).toBe(true)
  s = onSessionStart(s, { surface: 'desktop', agent: undefined, model: 'm', at: 2 }) // rechargement
  expect(s.runs[MAIN]!.agent).toBe('orchestration:scribe')
  s = onSessionStart(s, { surface: 'desktop', agent: 'orchestration:scribe', model: 'm', at: 3 })
  expect(s.startInferred).toBe(false)
})

test('plan en étapes : progression et passage à l\'étape suivante', () => {
  let s = onPlan(emptyRecap(), { title: 't', steps: ['lire', 'coder', 'vérifier'], at: 0 })
  expect(planProgress(s.plan!)).toMatchObject({ done: 0, total: 3, percent: 0, index: 1 })
  s = onPlanStep(s, { step: 1, status: 'done', at: 1 })
  expect(planProgress(s.plan!)).toMatchObject({ done: 1, percent: 33, index: 2 })
  expect(planProgress(s.plan!).current!.name).toBe('coder')
  s = onPlanStep(s, { step: 'vérifier', status: 'done', at: 2 })
  expect(s.plan!.steps.map(x => x.status)).toEqual(['done', 'done', 'done'])
  expect(s.plan!.endedAt).toBe(2)
  expect(onPlanStep(s, { step: 9, status: 'done', at: 3 })).toBe(s)
})

test('table aligne les colonnes', () => {
  expect(table([['a', 'x'], ['bbb', 'yy']], 1)).toEqual(['a     x', 'bbb  yy'])
})

test('plan à phases : état par intitulé conservé quand le plan est renvoyé, état du plan', () => {
  let s = onPlan(emptyRecap(), { title: 't', stages: [{ name: 'Lire', steps: ['a', 'b'] }, { name: 'Faire', steps: ['c'] }], at: 0 })
  expect(planProgress(s.plan!).stage).toBe('Lire')
  s = onPlanStep(s, { step: 'a', status: 'done', at: 5 })
  s = onPlan(s, { stages: [{ name: 'Lire', steps: ['a', 'b'] }, { name: 'Faire', steps: ['c', 'd'] }], at: 9 })
  expect(s.plan!.steps.map(x => x.status)).toEqual(['done', 'running', 'todo', 'todo'])
  expect(s.plan!.startedAt).toBe(0)
  s = onPlanStep(s, { state: 'input', note: 'attend une décision', at: 10 })
  expect(s.plan).toMatchObject({ state: 'input', note: 'attend une décision' })
  s = onPlanStep(s, { step: 'b', status: 'failed', at: 11 })
  expect(s.plan!.state).toBe('error')
})

test('bandes de sous-agents : actifs, en échec, ou finis depuis moins de 5 s', () => {
  let s = onSessionStart(emptyRecap(), { surface: 'desktop', agent: 'orchestration:scribe', model: 'm', at: 0 })
  s = onSpawn(s, { agentId: 'x1', agent: 'executant-low', model: 'm', fork: false, at: 1 })
  s = onToolUse(s, { agentId: 'x1', tool: 'Read' })
  expect(s.runs.x1!.tool).toBe('Read')
  expect(stripRuns(s, 2).map(r => r.id)).toEqual(['x1'])
  s = onComplete(s, { agentId: 'x1', reason: 'end_turn', at: 3000 })
  expect(stripRuns(s, 6000).map(r => r.id)).toEqual(['x1'])
  expect(stripRuns(s, 9000)).toEqual([])
  expect(duration(65_000)).toBe('1 min 05')
})

test('barre pondérée par les agents prévus : avance à chaque agent terminé, plafonnée avant la vérification', () => {
  let s = onSessionStart(emptyRecap(), { surface: 'desktop', agent: 'orchestration:scribe', model: 'm', at: 0 })
  s = onPlan(s, { isWorkflow: true, steps: [{ name: 'a', agents: 2 }, 'b'], at: 0 })
  s = onSpawn(s, { agentId: 'x1', agent: 'executant-low', model: 'm', fork: false, at: 1, task: 'lire le canon' })
  s = onSpawn(s, { agentId: 'x2', agent: 'executant-low', model: 'm', fork: false, at: 1 })
  expect(s.runs.x1!.task).toBe('lire le canon')
  expect(planProgress(s.plan!).percent).toBe(0)
  s = onComplete(s, { agentId: 'x1', reason: 'end_turn', at: 2 })
  expect(planProgress(s.plan!)).toMatchObject({ percent: 25, agentsDone: 1, agentsPlanned: 2 })
  s = onComplete(s, { agentId: 'x2', reason: 'end_turn', at: 3 })
  expect(planProgress(s.plan!).percent).toBe(45) // 0,9 / 2 étapes, la vérification reste à faire
  s = onPlanStep(s, { step: 'a', status: 'done', at: 4 })
  expect(planProgress(s.plan!).percent).toBe(50)
})

test('barre dessinée : SVG bien formé avec pastille de phase et éclat animé, cellules du terminal', () => {
  let s = onPlan(emptyRecap(), { title: 'L', stages: [{ name: 'Lire', steps: ['a', 'b'] }, { name: 'Faire', steps: ['c'] }], at: 0 })
  s = onPlanStep(s, { step: 'a', status: 'done', at: 5000 })
  const svg = progressSvg(s.plan!, 300, 9000)
  expect(svg.startsWith('<svg')).toBe(true)
  expect(svg).toContain('>Lire<')
  expect(svg).toContain('<animate')
  expect(svg).toContain('✓ a · 5s')
  const cells = progressCells(s.plan!, 20, 3)
  expect(cells.length).toBe(60)
  expect(cells[0]! >= 0x2800 && cells[0]! < 0x2900).toBe(true) // braille
  expect(cells[19 * 3]).toBe(BRAILLE_TRACK) // piste
})

test('carrés fixes : 5 rangées, fondu statique gauche→droite, onde de couleur, aucune graduation, braille au terminal', () => {
  let s = onPlan(emptyRecap(), { title: 'L', stages: [{ name: 'Lire', steps: ['a', 'b'] }], at: 0 })
  s = onPlanStep(s, { step: 'a', status: 'done', at: 5000 })
  const svg = progressSvg(s.plan!, 300, 9000)
  expect(svg).toContain('attributeName="transform"')
  expect(svg).toContain('<mask') // fondu statique
  expect(svg).not.toContain('<pattern')
  expect(svg).not.toContain('<script')
  expect(svg).not.toMatch(/\son\w+=/)
  expect(svg.length).toBeLessThan(131072)
  // aucune graduation : seuls la piste, les cellules (2×2 au pas de 4, avec halo), les zones de survol et la pastille
  expect(svg).not.toMatch(/width="1" height="\d+" fill="#fff"/)
  expect(svg).not.toMatch(/width="3" height="\d+" rx="1.5"/)
  expect(svg.match(/<rect /g)!.length).toBe(1 + 1 + 1 + 1 + 2 + 1) // forme du remplissage, masque, masque des étincelles, piste, 2 zones de survol, pastille
  // cellules fixes de 2×2 au pas de 4, décalées de 1 px depuis la piste (y = 4) : 5 rangées
  const cells = [...svg.matchAll(/M(\d+) (\d+)h2v2h-2z/g)]
  expect(cells.length).toBeGreaterThan(0)
  expect(new Set(cells.map(m => m[2]))).toEqual(new Set(['5', '9', '13', '17', '21']))
  expect(cells.every(m => Number(m[1]) % 4 === 1)).toBe(true)
  // halo sous chaque cellule (tuile 4×4 + croix) : les entre-cellules sont teintés, pas noirs
  // tuiles fusionnées par séries de même niveau, posées sur un lit continu (sans jointure visible au zoom)
  const tileCols = [...svg.matchAll(/M(\d+) (\d+)h(\d+)v4h-\3z/g)].reduce((n, m) => n + Number(m[3]) / 4, 0)
  const crossN = [...svg.matchAll(/M(\d+) (\d+)h2v1h1v2h-1v1h-2v-1h-1v-2h1z/g)]
  expect(crossN.length).toBe(cells.length)
  expect(tileCols).toBeLessThanOrEqual(cells.length * 1.1) // les tuiles d'étincelles sont comptées deux fois (trou du lit + couche)
  expect(tileCols).toBeGreaterThan(cells.length / 2)
  expect(svg).toMatch(new RegExp(`<path d="M0 4h${(cells.length / 5) * 4}v20h-${(cells.length / 5) * 4}z[^"]*" fill-rule="evenodd" fill="#[0-9a-f]{6}" fill-opacity="0\\.\\d+"\\/>`))
  // étincelles rares : le tracé des cellules les plus claires (couleur unie, opacité pleine) en porte au plus 10 %
  const corePaths = [...svg.matchAll(/<path d="((?:M\d+ \d+h2v2h-2z)+)" fill="([^"]+)" fill-opacity="([\d.]+)"\/>/g)]
  const sparkPath = corePaths.find(m => m[3] === '1')
  expect(sparkPath).toBeDefined()
  expect(sparkPath![2]).not.toBe('#ffffff') // blanc teinté de la couleur d'état, pas un gris neutre
  expect(sparkPath![1].match(/z/g)!.length / cells.length).toBeLessThanOrEqual(0.1)
  expect(corePaths.length).toBeGreaterThanOrEqual(3) // bruit : plusieurs niveaux, pas seulement teinte / étincelle
  // le fondu s'arrête au bord gauche de la pastille
  const fade = svg.match(/id="f"[^>]*x2="(\d+)"/)
  expect(Number(fade![1])).toBeGreaterThan(0)
  // sens du fondu : minimum au début (gauche), plein contre la pastille (droite), jamais décroissant
  const ops = [...svg.match(/id="f"[^>]*>(.*?)<\/linearGradient>/)![1]!.matchAll(/stop-opacity="([\d.]+)"/g)].map(m => Number(m[1]))
  expect(ops.length).toBeGreaterThan(2)
  expect(ops.every((o, i) => i === 0 || o >= ops[i - 1]!)).toBe(true)
  expect(ops.at(-1)!).toBeGreaterThan(ops[0]! * 10)
  // la pastille (50 px) est au début de la piste et cache le départ du remplissage : à 50 % de 300 px
  // l'avant est à 25 + 275 / 2 ≈ 163, le fondu part du milieu de la pastille
  expect(svg).toContain('<clipPath id="c"><rect x="0" y="4" width="163" height="20" rx="10"/></clipPath>')
  expect(svg).toContain('<rect x="0" y="2" width="50" height="24" rx="12"')
  expect(svg).toMatch(/id="f"[^>]*x1="25"/)
  // étincelles : leur propre fondu, déjà visible au début, jamais en dessous du fondu commun
  const sOps = [...svg.match(/id="s"[^>]*>(.*?)<\/linearGradient>/)![1]!.matchAll(/stop-opacity="([\d.]+)"/g)].map(m => Number(m[1]))
  expect(sOps[0]!).toBeGreaterThanOrEqual(0.08)
  expect(sOps.every((o, i) => o >= ops[i]!)).toBe(true)
  expect(svg).toContain('mask="url(#k)"')
  // à 0 % la pastille de phase est déjà là, sans remplissage dessous
  const start = progressSvg(onPlan(emptyRecap(), { title: 'L', stages: [{ name: 'Lire', steps: ['a', 'b'] }], at: 0 }).plan!, 300, 0)
  expect(start).toContain('>Lire<')
  expect(start).toContain('<rect x="0" y="2" width="50"') // l'avant (25 px) reste sous la pastille
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
  // fondu du terminal : l'avant de la barre porte plus de points que l'arrière
  const dots = (w: number) => (w - 0x2800).toString(2).replace(/0/g, '').length
  const back = [0, 1, 2].reduce((n, i) => n + dots(f1[i * 3]!), 0)
  const front = [7, 8, 9].reduce((n, i) => n + dots(f1[i * 3]!), 0)
  expect(front).toBeGreaterThan(back)
})

test('mascotte : SVG pixel-art, animée seulement si demandé', () => {
  expect(crabSvg()).toContain('viewBox')
  expect(crabSvg()).not.toContain('animateTransform')
  expect(crabSvg({ animated: true })).toContain('animateTransform')
  expect(crabSvg({ body: '#ef4444' })).toContain('#ef4444')
})

test('changement d\u2019état : la couleur fond de l\u2019ancienne à la nouvelle', () => {
  let s = onPlan(emptyRecap(), { title: 'L', stages: [{ name: 'Lire', steps: ['a', 'b'] }], at: 0 })
  expect(stateHex(s.plan!, 5)).toBe('#8b5cf6') // pas de transition avant un changement
  s = onPlanStep(s, { state: 'input', note: 'x', at: 1000 })
  expect(s.plan!.prevState).toBe('running')
  expect(stateHex(s.plan!, 1000)).toBe('#8b5cf6') // début : l\u2019ancienne couleur
  const mid = stateHex(s.plan!, 1000 + STATE_FADE_MS / 2)
  expect(mid).not.toBe('#8b5cf6')
  expect(mid).not.toBe('#f59e0b')
  expect(stateHex(s.plan!, 1000 + STATE_FADE_MS)).toBe('#f59e0b') // fin : la nouvelle
  const same = onPlanStep(s, { note: 'y', at: 1200 }) // même état : le fondu en cours n\u2019est pas relancé
  expect(same.plan!.stateAt).toBe(1000)
})
