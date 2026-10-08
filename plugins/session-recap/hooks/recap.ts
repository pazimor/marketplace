// Modèle du récap de session : fonctions pures, sans `$`, testées seules.
// Les noms d'événements et de champs viennent des déclarations générées par le moteur
// (`.claude/types/claude-code/index.d.ts`, Claude Code 2.1.287) — aucun n'est inventé.

import type {
  AgentRun,
  Alert,
  Bucket,
  Effort,
  Forecast,
  Instance,
  Limit,
  Options,
  Plan,
  PlanState,
  PlanStep,
  Prompt,
  Recap,
  Status,
  TimelineEntry,
  Tokens,
  Usage,
} from '../types'

export type { AgentRun, Alert, Bucket, Effort, Forecast, Instance, Limit, Options, Plan, PlanState, PlanStep, Prompt, Recap, Status, TimelineEntry, Tokens, Usage }

export const MAIN = 'principal'


export const DEFAULT_OPTIONS: Options = {
  limitWarn: 80,
  limitCritical: 95,
  agentTokenLimit: 0,
  sessionTokenLimit: 0,
  mainShareLimit: 0,
  modelMismatch: true,
}

const MAX_PROMPTS = 50
const MAX_TIMELINE = 300
const MAX_RUNS = 200
const MAIN_SHARE_FLOOR = 20000
const TASK_NOTIFICATION = '<task-notification>'

export const zero = (): Tokens => ({ input: 0, output: 0, cacheRead: 0, cacheWrite: 0 })

export function emptyRecap(): Recap {
  return {
    surface: null,
    startAgent: 'défaut',
    startInferred: false,
    plan: null,
    runs: {},
    order: [],
    prompts: [],
    timeline: [],
    buckets: {},
    limits: {},
    costUsd: null,
    alerted: [],
  }
}

function currentPrompt(s: Recap): number {
  return s.prompts.length === 0 ? 0 : s.prompts[s.prompts.length - 1]!.index
}

function withRun(s: Recap, run: AgentRun): Recap {
  const isNew = s.runs[run.id] === undefined
  const order = isNew ? [...s.order, run.id].slice(-MAX_RUNS) : s.order
  const runs: Record<string, AgentRun> = {}
  for (const id of order) runs[id] = id === run.id ? run : s.runs[id]!
  return { ...s, runs, order }
}

function pushTimeline(s: Recap, entry: TimelineEntry): Recap {
  return { ...s, timeline: [...s.timeline, entry].slice(-MAX_TIMELINE) }
}

export function effortOf(effort: unknown): Effort {
  if (typeof effort === 'number') return `${effort} tok`
  if (typeof effort === 'string' && effort !== '') return effort
  return '—'
}

/** Réglage `agent` absent ou valant « default » : l'agent de départ n'est pas nommé. */
const PLACEHOLDER_AGENT = /^(default|défaut|)$/i
/** Le seul agent qui lance l'orchestrateur est le scribe : c'est ce qui permet de le déduire. */
const ORCHESTRATOR = /(^|:)orchestrateur$/
const SCRIBE = 'orchestration:scribe'

export const isScribe = (agent: string): boolean => /(^|:)scribe$/.test(agent)

export function onSessionStart(
  s: Recap,
  e: { surface: string | null; agent: string | undefined; model: string; at: number },
): Recap {
  const named = e.agent !== undefined && !PLACEHOLDER_AGENT.test(e.agent)
  const keep = !named && s.startInferred // un rechargement ne perd pas l'agent déduit
  const startAgent = named ? e.agent! : keep ? s.startAgent : 'défaut'
  const main: AgentRun = s.runs[MAIN] ?? {
    id: MAIN,
    parentId: null,
    agent: startAgent,
    promptIndex: 0,
    instance: 'nouvelle',
    model: e.model,
    effort: '—',
    status: 'running',
    resumes: 0,
    startedAt: e.at,
    tokens: zero(),
  }
  return withRun({ ...s, surface: e.surface, startAgent, startInferred: keep }, { ...main, agent: startAgent, model: e.model })
}

/** Un prompt utilisateur ; les notifications de tâches de fond n'en sont pas. */
export function onPrompt(s: Recap, e: { text: string; at: number }): Recap {
  if (e.text.startsWith(TASK_NOTIFICATION)) return s
  const index = currentPrompt(s) + 1
  const prompt = { index, text: e.text.replace(/\s+/g, ' ').slice(0, 80), at: e.at }
  return { ...s, prompts: [...s.prompts, prompt].slice(-MAX_PROMPTS) }
}

export function onSpawn(
  s: Recap,
  e: { agentId: string; parentId?: string; agent: string; model: string; fork: boolean; at: number; task?: string },
): Recap {
  const known = s.runs[e.agentId]
  const kind: Instance = known !== undefined ? 'reprise' : e.fork ? 'fork' : 'nouvelle'
  const promptIndex = currentPrompt(s)
  const run: AgentRun = {
    id: e.agentId,
    parentId: e.parentId ?? MAIN,
    agent: e.agent,
    promptIndex: known?.promptIndex ?? promptIndex,
    instance: known?.instance ?? kind,
    spawnModel: e.model,
    model: e.model,
    effort: known?.effort ?? '—',
    task: (e.task ?? '').replace(/\s+/g, ' ').trim().slice(0, 80) || known?.task,
    stepIndex: known?.stepIndex ?? runningStep(s),
    status: 'running',
    resumes: (known?.resumes ?? 0) + (known !== undefined ? 1 : 0),
    startedAt: known?.startedAt ?? e.at,
    tokens: known?.tokens ?? zero(),
    ...(known?.mascot !== undefined ? { mascot: known.mascot } : {}),
  }
  let withPlan = s
  if (known === undefined && run.stepIndex !== undefined) withPlan = bumpStep(s, run.stepIndex, 'started')
  const base = pushTimeline(withRun(withPlan, run), { promptIndex, agentId: e.agentId, kind, at: e.at })
  const main = base.runs[MAIN]
  if (
    main !== undefined &&
    PLACEHOLDER_AGENT.test(main.agent) &&
    run.parentId === MAIN &&
    ORCHESTRATOR.test(e.agent)
  ) {
    return withRun({ ...base, startAgent: SCRIBE, startInferred: true }, { ...main, agent: SCRIBE })
  }
  return base
}

/**
 * Un appel modèle d'un agent. Un agent inconnu (lancé avant le chargement du mod) est
 * créé ; un agent terminé qui reparle a été repris (SendMessage) : pas d'`agent.spawn`.
 */
export function onStep(
  s: Recap,
  e: { agentId?: string; model: string; effort: unknown; at: number },
): Recap {
  const id = e.agentId ?? MAIN
  const effort = effortOf(e.effort)
  const run = s.runs[id]
  const promptIndex = currentPrompt(s)
  if (run === undefined) {
    const created: AgentRun = {
      id,
      parentId: id === MAIN ? null : MAIN,
      agent: id === MAIN ? s.startAgent : 'inconnu',
      promptIndex,
      instance: 'reprise',
      model: e.model,
      effort,
      status: 'running',
      resumes: 0,
      startedAt: e.at,
      tokens: zero(),
    }
    const next = withRun(s, created)
    return id === MAIN ? next : pushTimeline(next, { promptIndex, agentId: id, kind: 'reprise', at: e.at })
  }
  const isResumed = id !== MAIN && run.status !== 'running'
  const updated: AgentRun = {
    ...run,
    model: e.model,
    effort,
    status: 'running',
    resumes: run.resumes + (isResumed ? 1 : 0),
    endedAt: isResumed ? undefined : run.endedAt,
  }
  const next = withRun(s, updated)
  return isResumed ? pushTimeline(next, { promptIndex, agentId: id, kind: 'reprise', at: e.at }) : next
}


function add(a: Tokens, u: Usage): Tokens {
  return {
    input: a.input + u.input_tokens,
    output: a.output + u.output_tokens,
    cacheRead: a.cacheRead + u.cache_read_input_tokens,
    cacheWrite: a.cacheWrite + u.cache_creation_input_tokens,
  }
}

/** L'usage d'un appel modèle (chunk `stop` de `turn.step`), attribué à agent × modèle × effort. */
export function onUsage(s: Recap, e: { agentId?: string; effort: unknown; usage: Usage }): Recap {
  const id = e.agentId ?? MAIN
  const run = s.runs[id]
  const agent = run?.agent ?? (id === MAIN ? s.startAgent : 'inconnu')
  const effort = effortOf(e.effort)
  const key = `${agent}\u0000${e.usage.model}\u0000${effort}`
  const bucket = s.buckets[key] ?? { agent, model: e.usage.model, effort, tokens: zero(), calls: 0 }
  const buckets = { ...s.buckets, [key]: { ...bucket, tokens: add(bucket.tokens, e.usage), calls: bucket.calls + 1 } }
  const next = { ...s, buckets }
  return run === undefined ? next : withRun(next, { ...run, tokens: add(run.tokens, e.usage) })
}

export function onComplete(s: Recap, e: { agentId?: string; reason: string; at: number }): Recap {
  const id = e.agentId ?? MAIN
  const run = s.runs[id]
  if (run === undefined || id === MAIN) return s
  const status: Status = e.reason === 'error' ? 'failed' : 'done'
  const base = run.status === 'running' && run.stepIndex !== undefined ? bumpStep(s, run.stepIndex, 'finished') : s
  return withRun(base, { ...run, status, endedAt: e.at })
}

export function onMeasure(
  s: Recap,
  e: { rateLimits: readonly { kind: string; percentUsed: number; resetsAt?: string }[]; costUsd?: number; at: number },
): Recap {
  const limits = { ...s.limits }
  for (const r of e.rateLimits) {
    const prev = limits[r.kind]
    const isNewWindow = prev === undefined || prev.resetsAt !== r.resetsAt || r.percentUsed < prev.percentUsed
    limits[r.kind] = {
      kind: r.kind,
      percentUsed: r.percentUsed,
      resetsAt: r.resetsAt,
      at: e.at,
      firstAt: isNewWindow ? e.at : prev.firstAt,
      firstPercent: isNewWindow ? r.percentUsed : prev.firstPercent,
    }
  }
  return { ...s, limits, costUsd: e.costUsd ?? s.costUsd }
}


/** Projection linéaire sur le rythme observé depuis le début de la session dans cette fenêtre. */
export function forecast(l: Limit): Forecast {
  const reset = l.resetsAt === undefined ? NaN : Date.parse(l.resetsAt)
  const elapsed = l.at - l.firstAt
  if (elapsed <= 0 || Number.isNaN(reset)) return { atReset: null, exhaustedAt: null }
  const rate = (l.percentUsed - l.firstPercent) / elapsed
  const atReset = Math.min(999, Math.round(l.percentUsed + rate * Math.max(0, reset - l.at)))
  const exhaustedAt = rate > 0 ? l.at + (100 - l.percentUsed) / rate : null
  return { atReset, exhaustedAt: exhaustedAt !== null && exhaustedAt < reset ? exhaustedAt : null }
}

/** Tokens qui pèsent sur les limites : la lecture du cache est comptée à part. */
export const weight = (t: Tokens): number => t.input + t.output + t.cacheWrite

export function totals(s: Recap): Tokens {
  return Object.values(s.buckets).reduce(
    (a, b) => ({
      input: a.input + b.tokens.input,
      output: a.output + b.tokens.output,
      cacheRead: a.cacheRead + b.tokens.cacheRead,
      cacheWrite: a.cacheWrite + b.tokens.cacheWrite,
    }),
    zero(),
  )
}


/** Les alertes à lever maintenant ; `alerted` garde celles déjà levées. */
export function pendingAlerts(s: Recap, o: Options): Alert[] {
  const out: Alert[] = []
  for (const l of Object.values(s.limits)) {
    for (const [level, threshold] of [['critique', o.limitCritical], ['alerte', o.limitWarn]] as const) {
      if (threshold > 0 && l.percentUsed >= threshold) {
        out.push({ key: `limit:${l.kind}:${threshold}:${l.resetsAt ?? ''}`, text: `${level} : limite ${limitLabel(l.kind)} à ${l.percentUsed} %` })
        break
      }
    }
  }
  for (const run of s.order.map(id => s.runs[id]!)) {
    if (o.agentTokenLimit > 0 && weight(run.tokens) >= o.agentTokenLimit) {
      out.push({ key: `agent:${run.id}`, text: `${run.agent} a dépassé ${formatTokens(o.agentTokenLimit)} tokens` })
    }
    if (o.modelMismatch && run.spawnModel !== undefined && run.model !== run.spawnModel) {
      out.push({
        key: `model:${run.id}:${run.model}`,
        text: `${run.agent} répond sur ${shortModel(run.model)} au lieu de ${shortModel(run.spawnModel)}`,
      })
    }
  }
  const total = weight(totals(s))
  if (o.sessionTokenLimit > 0 && total >= o.sessionTokenLimit) {
    out.push({ key: 'session', text: `la session a dépassé ${formatTokens(o.sessionTokenLimit)} tokens` })
  }
  const main = s.runs[MAIN]
  if (o.mainShareLimit > 0 && main !== undefined && total >= MAIN_SHARE_FLOOR) {
    const share = Math.round((100 * weight(main.tokens)) / total)
    if (share > o.mainShareLimit) {
      out.push({ key: 'main-share', text: `l'agent principal (${main.agent}) fait ${share} % des tokens de la session` })
    }
  }
  return out.filter(a => !s.alerted.includes(a.key))
}

export function markAlerted(s: Recap, alerts: readonly Alert[]): Recap {
  return alerts.length === 0 ? s : { ...s, alerted: [...s.alerted, ...alerts.map(a => a.key)].slice(-200) }
}

export function readOptions(raw: Readonly<Record<string, unknown>> | undefined): Options {
  const num = (k: keyof Options) => (typeof raw?.[k] === 'number' ? (raw[k] as number) : (DEFAULT_OPTIONS[k] as number))
  return {
    limitWarn: num('limitWarn'),
    limitCritical: num('limitCritical'),
    agentTokenLimit: num('agentTokenLimit'),
    sessionTokenLimit: num('sessionTokenLimit'),
    mainShareLimit: num('mainShareLimit'),
    modelMismatch: typeof raw?.modelMismatch === 'boolean' ? raw.modelMismatch : DEFAULT_OPTIONS.modelMismatch,
  }
}

// --- Affichage -------------------------------------------------------------------------------

/** `claude-xxx-5-5` → `xxx-5-5`, sans le suffixe de date d'un id complet. */
export function shortModel(id: string): string {
  return id.replace(/^claude-/, '').replace(/-\d{8}$/, '')
}

export function formatTokens(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`
  return String(n)
}

export function limitLabel(kind: string): string {
  if (kind === 'five_hour') return '5 h'
  if (kind === 'seven_day') return '7 jours'
  return kind.replace(/_/g, ' ')
}

export function bar(percent: number, width = 20): string {
  const filled = Math.max(0, Math.min(width, Math.round((percent / 100) * width)))
  return '█'.repeat(filled) + '░'.repeat(width - filled)
}

export const INSTANCE_LABEL: Record<Instance, string> = { nouvelle: 'neuf', reprise: 'repris', fork: 'forké' }

export function sortedBuckets(s: Recap): Bucket[] {
  return Object.values(s.buckets).sort((a, b) => weight(b.tokens) - weight(a.tokens))
}

export function activeRuns(s: Recap): AgentRun[] {
  return s.order.map(id => s.runs[id]!).filter(r => r.id !== MAIN && r.status === 'running')
}

/** Les enfants d'un agent, dans l'ordre de lancement. */
export function childrenOf(s: Recap, id: string): AgentRun[] {
  return s.order.map(i => s.runs[i]!).filter(r => r.parentId === id)
}


/** Étape du plan en cours (index), pour rattacher les agents qui se lancent. */
function runningStep(s: Recap): number | undefined {
  const i = s.plan?.steps.findIndex(x => x.status === 'running') ?? -1
  return i >= 0 ? i : undefined
}

function bumpStep(s: Recap, index: number, key: 'started' | 'finished'): Recap {
  const plan = s.plan
  if (plan === null || plan.steps[index] === undefined) return s
  const steps = plan.steps.map((x, i) => (i === index ? { ...x, [key]: x[key] + 1 } : x))
  return { ...s, plan: { ...plan, steps } }
}

// --- Plan en étapes (déclaré par l'orchestrateur) ---------------------------------------------

const MAX_STEPS = 40
const STRIP_FOLD_MS = 5000

type StepInput = string | { name: string; agents?: number }
type StageInput = { name: string; steps: readonly StepInput[] }

const stepName = (x: StepInput): string => (typeof x === 'string' ? x : String(x.name))
const stepAgents = (x: StepInput): number =>
  typeof x === 'string' || !Number.isFinite(Number(x.agents)) ? 0 : Math.max(0, Math.min(50, Math.floor(Number(x.agents))))

/**
 * Un plan renvoyé en cours de route garde l'état des étapes déjà terminées (par intitulé).
 * `agents` par étape = appels d'agents prévus (un workflow en connaît le nombre) : la barre
 * avance alors à chaque agent terminé, pas seulement à chaque étape.
 */
export function onPlan(
  s: Recap,
  e: { title?: string; steps?: readonly StepInput[]; stages?: readonly StageInput[]; isWorkflow?: boolean; at: number },
): Recap {
  const flat: { input: StepInput; stage: string }[] = []
  for (const st of e.stages ?? []) for (const n of st.steps) flat.push({ input: n, stage: String(st.name) })
  for (const n of e.steps ?? []) flat.push({ input: n, stage: '' })
  const old = new Map((s.plan?.steps ?? []).map(x => [x.name.toLowerCase(), x]))
  const steps: PlanStep[] = flat
    .map(x => ({ name: stepName(x.input).trim().slice(0, 80), stage: x.stage.trim().slice(0, 40), agents: stepAgents(x.input) }))
    .filter(x => x.name !== '')
    .slice(0, MAX_STEPS)
    .map(x => {
      const prev = old.get(x.name.toLowerCase())
      return prev?.status === 'done'
        ? { ...x, status: 'done' as const, doneAt: prev.doneAt, started: prev.started, finished: prev.finished }
        : { ...x, status: 'todo' as const, started: 0, finished: 0 }
    })
  if (steps.length === 0) return { ...s, plan: null }
  const first = steps.findIndex(x => x.status !== 'done')
  if (first >= 0) steps[first] = { ...steps[first]!, status: 'running' }
  const done = first < 0
  return {
    ...s,
    plan: {
      title: (e.title ?? s.plan?.title ?? '').slice(0, 60),
      isWorkflow: e.isWorkflow ?? s.plan?.isWorkflow ?? false,
      steps,
      state: done ? 'done' : 'running',
      note: '',
      startedAt: s.plan?.startedAt ?? e.at,
      endedAt: done ? e.at : undefined,
      ...stateShift(s.plan, done ? 'done' : 'running', e.at),
    },
  }
}

/** Durée du fondu d'une couleur d'état à l'autre. */
export const STATE_FADE_MS = 900
/** Champs de transition quand l'état change (rien si l'état est inchangé : le fondu en cours continue). */
function stateShift(plan: Plan | null | undefined, state: PlanState, at: number): { prevState?: PlanState; stateAt?: number } {
  if (plan === null || plan === undefined) return {}
  if (plan.state === state) return { prevState: plan.prevState, stateAt: plan.stateAt }
  return { prevState: plan.state, stateAt: at }
}
/** Le fondu de couleur est-il en cours ? */
export const isFading = (plan: Plan | null, now: number): boolean => plan?.stateAt !== undefined && now - plan.stateAt < STATE_FADE_MS
/** Couleur de l'état, en fondu depuis la précédente pendant `STATE_FADE_MS` après un changement. */
export function stateHex(plan: Plan, now?: number): string {
  const to = STATE_HEX[plan.state]
  if (now === undefined || plan.prevState === undefined || plan.stateAt === undefined) return to
  const t = Math.min(1, Math.max(0, (now - plan.stateAt) / STATE_FADE_MS))
  const ease = t * t * (3 - 2 * t)
  return mix(STATE_HEX[plan.prevState], to, ease)
}

/** `step` : numéro (à partir de 1) ou nom. `done` passe à l'étape suivante, qui devient en cours. */
export function onPlanStep(
  s: Recap,
  e: { step?: number | string; status?: 'running' | 'done' | 'failed'; state?: PlanState; note?: string; at: number },
): Recap {
  const plan = s.plan
  if (plan === null) return s
  let steps = plan.steps
  if (e.step !== undefined && e.status !== undefined) {
    const idx =
      typeof e.step === 'number'
        ? e.step - 1
        : plan.steps.findIndex(x => x.name.toLowerCase() === String(e.step).trim().toLowerCase())
    if (!Number.isInteger(idx) || idx < 0 || idx >= plan.steps.length) return s
    const status = e.status
    steps = plan.steps.map((x, i) =>
      i === idx ? { ...x, status, doneAt: status === 'done' ? e.at : x.doneAt } : x,
    )
    if (status === 'done') {
      for (let i = 0; i < idx; i++) {
        if (steps[i]!.status !== 'failed' && steps[i]!.status !== 'done') steps[i] = { ...steps[i]!, status: 'done', doneAt: e.at }
      }
      const next = steps[idx + 1]
      if (next !== undefined && next.status === 'todo') steps[idx + 1] = { ...next, status: 'running' }
    }
  }
  const finished = steps.every(x => x.status === 'done')
  const failed = steps.some(x => x.status === 'failed')
  const state: PlanState = finished ? 'done' : (e.state ?? (failed ? 'error' : e.status === 'done' || e.status === 'running' ? 'running' : plan.state))
  return {
    ...s,
    plan: {
      ...plan,
      steps,
      state,
      note: (e.note ?? (e.state !== undefined || e.step !== undefined ? '' : plan.note)).slice(0, 120),
      endedAt: finished ? (plan.endedAt ?? e.at) : undefined,
      ...stateShift(plan, state, e.at),
    },
  }
}

export function planProgress(plan: Plan): {
  done: number
  total: number
  percent: number
  current: PlanStep | undefined
  index: number
  stage: string
  agentsDone: number
  agentsPlanned: number
} {
  const total = plan.steps.length
  const done = plan.steps.filter(x => x.status === 'done').length
  const index = plan.steps.findIndex(x => x.status === 'running' || x.status === 'failed')
  const current = index >= 0 ? plan.steps[index] : undefined
  // Étape en cours avec des agents prévus : fraction d'agents terminés, plafonnée à 90 % (reste la vérification).
  const fraction = (x: PlanStep): number =>
    x.status === 'done' ? 1 : x.status === 'running' && x.agents > 0 ? Math.min(0.9, x.finished / x.agents) : 0
  const sum = plan.steps.reduce((n, x) => n + fraction(x), 0)
  return {
    done,
    total,
    percent: total === 0 ? 0 : Math.round((sum / total) * 100),
    current,
    index: index + 1,
    stage: current?.stage ?? '',
    agentsDone: plan.steps.reduce((n, x) => n + x.finished, 0),
    agentsPlanned: plan.steps.reduce((n, x) => n + x.agents, 0),
  }
}

export type WorkflowStage = {
  name: string
  planned: number // agents prévus (somme des étapes)
  runs: AgentRun[] // agents déjà lancés dans cette phase, du plus ancien au plus récent
  placeholders: number // agents prévus pas encore lancés
  done: number // agents terminés
  status: PlanStep['status']
}
/** Phases d'un workflow (étapes consécutives de même phase) avec leurs agents, lancés ou à venir. */
export function workflowStages(s: Recap): WorkflowStage[] {
  const plan = s.plan
  if (plan === null || !plan.isWorkflow) return []
  const groups: { name: string; idx: number[] }[] = []
  plan.steps.forEach((x, i) => {
    const last = groups[groups.length - 1]
    if (last !== undefined && last.name === x.stage) last.idx.push(i)
    else groups.push({ name: x.stage, idx: [i] })
  })
  const running = groups.findIndex(g => g.idx.some(i => plan.steps[i]!.status === 'running'))
  const fallback = running >= 0 ? running : groups.length - 1
  return groups.map(g => {
    const steps = g.idx.map(i => plan.steps[i]!)
    // un agent lancé avant le plan (sans étape) est rattaché à la phase en cours
    const runs = s.order
      .map(id => s.runs[id]!)
      .filter(r => r.id !== MAIN && (r.stepIndex !== undefined ? g.idx.includes(r.stepIndex) : groups.indexOf(g) === fallback))
    const planned = steps.reduce((n, x) => n + x.agents, 0)
    return {
      name: g.name !== '' ? g.name : plan.title,
      planned,
      runs,
      placeholders: Math.max(0, planned - runs.length),
      done: steps.reduce((n, x) => n + x.finished, 0),
      status: steps.every(x => x.status === 'done') ? 'done' : steps.some(x => x.status === 'failed') ? 'failed' : steps.some(x => x.status === 'running') ? 'running' : 'todo',
    }
  })
}

export const isPlanLive = (s: Recap): boolean => s.plan !== null && s.plan.endedAt === undefined

/** Dernier outil appelé par un agent (`tool.call` porte l'agentId ; absent = agent principal). */
export function onToolUse(s: Recap, e: { agentId?: string; tool: string }): Recap {
  const id = e.agentId ?? MAIN
  const run = s.runs[id]
  if (run === undefined || run.tool === e.tool) return s
  return withRun(s, { ...run, tool: e.tool.replace(/^mcp__/, '') })
}

/** Sous-agents à montrer sous la barre : actifs, en échec, ou finis depuis moins de 5 s. */
export function stripRuns(s: Recap, now: number): AgentRun[] {
  return s.order
    .map(id => s.runs[id]!)
    .filter(
      r =>
        r.id !== MAIN &&
        (r.status === 'running' || r.status === 'failed' || (r.endedAt !== undefined && now - r.endedAt < STRIP_FOLD_MS)),
    )
}

/** `42s`, `1 min 05`, `1 h 02`. */
export function duration(ms: number): string {
  const sec = Math.max(0, Math.floor(ms / 1000))
  if (sec < 60) return `${sec}s`
  const m = Math.floor(sec / 60)
  if (m < 60) return `${m} min ${String(sec % 60).padStart(2, '0')}`
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')}`
}

/** Barre animée : un éclat parcourt la partie remplie (`frame` = compteur de ticks). */
export function shimmerBar(percent: number, width: number, frame: number, isLive: boolean): string {
  const filled = Math.max(0, Math.min(width, Math.round((percent / 100) * width)))
  const cells: string[] = []
  const spot = filled > 0 ? frame % filled : -1
  for (let i = 0; i < width; i++) {
    if (i >= filled) cells.push('░')
    else cells.push(isLive && (i === spot || i === spot - 1) ? '▓' : '█')
  }
  return cells.join('')
}

export const SPINNER = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

/** Tableau aligné : colonnes séparées par deux espaces, nombres à droite. */
export function table(rows: readonly (readonly string[])[], rightFrom = 1): string[] {
  const w: number[] = []
  for (const r of rows) r.forEach((c, i) => (w[i] = Math.max(w[i] ?? 0, c.length)))
  return rows.map(r => r.map((c, i) => (i >= rightFrom ? c.padStart(w[i]!) : c.padEnd(w[i]!))).join('  '))
}


// --- Barre dessinée (desktop : SVG ; terminal : cellules colorées) ----------------------------

export const STATE_HEX = { running: '#8b5cf6', input: '#f59e0b', error: '#ef4444', done: '#22c55e' } as const

const esc = (t: string): string => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

// Treillis façon grille de contributions : cellules de 2×2 px au pas de 4, 5 rangées, marge de 1 px.
// Chaque cellule porte un halo doux sur sa tuile de 4×4 (bords à ~½, coins à ~¼ de son intensité) :
// les entre-cellules sont teintés et le damier se lit presque continu.
const SQ = 2 // côté d'une cellule, en px
const GAP = 2
const ROWS = 5
const INSET = 1 // décalage des cellules depuis le bord haut et le bord gauche de la piste
const TRACK_Y = 4
const TRACK_H = 20
const BADGE_H = 24
const EDGE = 0.54 // intensité des bords du halo, relative au cœur de la cellule
const CORNER = 0.27 // intensité des coins du halo
/** Profil d'alpha du cœur d'une cellule moyenne (t : 0 au début, 1 contre la pastille) : croissant de gauche à droite. */
const FADE: [number, number][] = [
  [0, 0.012],
  [0.06, 0.02],
  [0.14, 0.037],
  [0.2, 0.05],
  [0.3, 0.085],
  [0.38, 0.115],
  [0.45, 0.18],
  [0.53, 0.23],
  [0.69, 0.38],
  [0.78, 0.41],
  [1, 0.43],
]
/** Niveaux de bruit (multiplicateurs d'intensité) ; le dernier est l'étincelle, plus blanche. */
const NOISE = [0.85, 1, 1.35, 1.65]
const SPARK = NOISE.length - 1
/** Alpha ajouté aux étincelles (nul contre la pastille, où le fondu suffit) : elles restent lisibles dans la partie estompée du début. */
const SPARK_MIN = 0.09
const NCOLS = 37 // période de la table, première pour ne pas laisser voir la répétition
/** Table fixe 5 × 37 des niveaux (graine figée) : ~8 % d'étincelles, réparties sur toute la longueur, jamais deux voisines (diagonales comprises). */
const NOISE_TABLE: number[][] = (() => {
  let seed = 324 // choisie pour que chaque fenêtre de 4 colonnes porte au moins une étincelle
  const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff), (seed >> 8) / 0x7fffff)
  const rows: number[][] = []
  for (let row = 0; row < ROWS; row++) {
    const line: number[] = []
    for (let c = 0; c < NCOLS; c++) {
      const r = rnd()
      let v = r < 0.12 ? 0 : r < 0.55 ? 1 : r < 0.93 ? 2 : SPARK
      const near = [line[c - 1], rows[row - 1]?.[c - 1], rows[row - 1]?.[c], rows[row - 1]?.[(c + 1) % NCOLS], c === NCOLS - 1 ? line[0] : -1]
      if (v === SPARK && near.includes(SPARK)) v = 2
      line.push(v)
    }
    rows.push(line)
  }
  return rows
})()
// Intensités fixes du terminal (progressCells) : une période de 14 colonnes, 6 intensités.
const COLS = 14
const LEVELS = [0.3, 0.45, 0.6, 0.75, 0.9, 1]
/** Intensités fixes (graine figée), sans deux voisins égaux horizontalement ni verticalement. */
const PATTERN: number[][] = (() => {
  let seed = 7
  const rows: number[][] = []
  for (let row = 0; row < ROWS; row++) {
    const line: number[] = []
    for (let c = 0; c < COLS; c++) {
      let v = 0
      do {
        seed = (seed * 1103515245 + 12345) & 0x7fffffff
        v = (seed >> 16) % LEVELS.length
      } while (v === line[c - 1] || v === rows[row - 1]?.[c] || (c === COLS - 1 && v === line[0]))
      line.push(v)
    }
    rows.push(line)
  }
  return rows
})()
const level = (c: number, row: number): number => LEVELS[PATTERN[row % ROWS]![((c % COLS) + COLS) % COLS]!]!
/** Largeur en px d'une colonne de texte, pour convertir `bodyColumns` en pixels. */
const COL_PX = 7
/** Largeur de la barre : toute la ligne disponible (moins une marge), de 160 px à 1600 px. */
export const barWidth = (bodyColumns: number): number => Math.min(1600, Math.max(160, Math.floor((bodyColumns - 4) * COL_PX)))
/** Hauteur en px de la barre SVG (la pastille dépasse la piste). */
export const PROGRESS_HEIGHT = TRACK_H + TRACK_Y * 2
/** Largeur en px de la barre SVG pour une largeur demandée. */
export const progressWidth = (width: number): number => Math.max(120, Math.floor(width))
/**
 * Style de la racine des SVG du bureau, fond transparent. Les SVG sont dessinés en image, jamais en cadre isolé
 * (`isInteractive`) : le cadre, recréé à chaque rendu du bandeau, flashait en blanc et relançait les animations.
 */
const SVG_ROOT_STYLE = 'color-scheme:light dark;background:transparent'
/** Largeur d'une carte d'agent selon la place : 1, 2 ou 3 par ligne. */
export const cardWidth = (bodyColumns: number): '100%' | '50%' | '33%' => (bodyColumns < 64 ? '100%' : bodyColumns < 104 ? '50%' : '33%')
/** Écart entre deux cartes d'agent, en cellules : une colonne à droite de chaque carte, une rangée entre deux lignes de cartes. */
export const CARD_GAP = 1
/** Géométrie de la barre, lue par scripts/measure-session-recap.mts : à garder synchrone avec progressSvg. */
export const PROGRESS_GEOMETRY = { cell: SQ, pitch: SQ + GAP, rows: ROWS, trackY: TRACK_Y, trackH: TRACK_H, inset: INSET } as const

/**
 * Barre SVG : piste en pilule, remplissage en treillis fixe de 5 rangées de cellules 2×2 posées sur un lit
 * teinté, dans une version claire de la couleur d'état. Un fondu statique va du minimum à gauche (début)
 * au plein à droite (contre la pastille), quelques cellules fixes étincellent ; tant que le plan tourne, une
 * onde de couleurs plus ou moins claires naît contre la pastille et recule vers la gauche (SMIL), en
 * s'estompant avec le fondu. Les cellules ne bougent jamais, seule la couleur bouge.
 * Aucune graduation. Une zone par étape avec `<title>` (infobulle, seulement là où le SVG est interactif). La pastille de phase
 * est unie, collée à l'avant du remplissage, qui s'arrête net à son bord gauche (rien dessous ni dans ses coins).
 * `uid` suffixe les ids quand plusieurs barres partagent un même document (page de test).
 */
export function progressSvg(plan: Plan, width: number, now: number, uid = ''): string {
  const p = planProgress(plan)
  const pitch = SQ + GAP
  const H = PROGRESS_HEIGHT // 28, la pastille (24 px) dépasse la piste
  const R = TRACK_H / 2 // arrondi de la piste et du remplissage : pilule
  const W = progressWidth(width)
  const live = plan.endedAt === undefined && plan.state === 'running'
  // couleurs finales dans le balisage ; le fondu d'état est une animation CSS posée tant qu'il dure, pour que
  // la source reste identique d'un tic à l'autre (le cadre isolé du bureau se recharge à chaque changement de source)
  const hex = STATE_HEX[plan.state]
  const fading = plan.prevState !== undefined && plan.prevState !== plan.state && isFading(plan, now)
  const prevHex = plan.prevState !== undefined ? STATE_HEX[plan.prevState] : hex
  const n = plan.steps.length
  // pastille : calculée d'abord, le fondu s'arrête à son bord gauche
  const label = p.stage.length > 12 ? `${p.stage.slice(0, 11)}…` : p.stage
  // affichée dès qu'une phase est en cours, même à 0 % (elle couvre alors le début de la piste)
  const hasBadge = p.stage !== ''
  const pw = hasBadge ? Math.ceil(label.length * 7 + 22) : 0
  const ph = BADGE_H
  // la vignette est au début de la piste et cache le départ du remplissage : à 0 % l'avant est au milieu de la vignette
  const px = 0
  const half = pw / 2
  const fillW = Math.round(half + ((W - half) * p.percent) / 100)
  // le remplissage s'arrête net au bord gauche de la pastille (x = px) : rien ne passe dessous, donc aucune
  // cellule n'apparaît dans les arrondis de ses coins (on y voit la piste, comme autour du reste de la pastille)
  const cy = TRACK_Y + TRACK_H / 2
  const clipW = fillW
  const fadeStart = hasBadge ? half : 0
  const fadeEnd = Math.max(fadeStart + 1, fillW)
  // cellules fixes regroupées par niveau de bruit, chacune en trois couches (tuile 4×4, croix, cœur 2×2)
  // dont les opacités composées donnent coins / bords / cœur dans les proportions CORNER / EDGE / 1 ;
  // les tuiles reposent sur un lit continu (le niveau le plus faible) et sont fusionnées par séries
  // de même niveau, pour qu'aucune jointure ne se voie à fort zoom
  const cols = Math.ceil(clipW / pitch) + NCOLS
  const tiles = NOISE.map(() => ['', '', ''])
  for (let row = 0; row < ROWS; row++) {
    const y = TRACK_Y + row * pitch
    for (let c = 0; c < cols; c++) {
      const x = c * pitch
      const k = NOISE_TABLE[row]![c % NCOLS]!
      const t = tiles[k]!
      let run = 1
      while (c + run < cols && NOISE_TABLE[row]![(c + run) % NCOLS] === k) run++
      t[0] += `M${x} ${y}h${pitch * run}v4h-${pitch * run}z`
      for (let j = 0; j < run; j++) {
        const xj = x + j * pitch
        t[1] += `M${xj + 1} ${y}h2v1h1v2h-1v1h-2v-1h-1v-2h1z`
        t[2] += `M${xj + INSET} ${y + INSET}h${SQ}v${SQ}h-${SQ}z`
      }
      c += run - 1
    }
  }
  const light = mix(hex, '#ffffff', 0.55)
  const sparkHex = mix(hex, '#ffffff', 0.7)
  const paint = light
  const top = NOISE[SPARK]!
  const meanNoise = NOISE_TABLE.flat().reduce((m, v) => m + NOISE[v]!, 0) / (ROWS * NCOLS)
  const op = (v: number) => +v.toFixed(3)
  const bedA = (CORNER * NOISE[0]!) / top // lit continu : la tuile du niveau le plus faible
  const layers = (k: number, fill: string) => {
    const [sq, plus, core] = tiles[k]!
    if (!core) return ''
    const cc = NOISE[k]! / top
    const sA = CORNER * cc
    const extra = k === 0 && fill === paint ? 0 : 1 - (1 - sA) / (1 - (fill === paint ? bedA : 0))
    const pA = 1 - (1 - EDGE * cc) / (1 - sA)
    const qA = 1 - (1 - cc) / (1 - EDGE * cc)
    return (
      (extra > 0 ? `<path d="${sq}" fill="${fill}" fill-opacity="${op(extra)}"/>` : '') +
      `<path d="${plus}" fill="${fill}" fill-opacity="${op(pA)}"/>` +
      `<path d="${core}" fill="${fill}" fill-opacity="${op(qA)}"/>`
    )
  }
  const bedPath = `M0 ${TRACK_Y}h${cols * pitch}v${TRACK_H}h-${cols * pitch}z`
  const tilesSpark = tiles[SPARK]![0]
  // le lit ne passe pas sous les étincelles (elles ont leur propre couleur et leur propre fondu)
  const cellPaths =
    `<path d="${bedPath}${tilesSpark ? ` ${tilesSpark}` : ''}" fill-rule="evenodd" fill="${paint}" fill-opacity="${op(bedA)}"/>` +
    NOISE.map((_, k) => (k === SPARK ? '' : layers(k, paint))).join('')
  const sparkPaths = layers(SPARK, sparkHex)
  const stops = FADE.map(([t, a]) => `<stop offset="${t}" stop-color="#fff" stop-opacity="${op((a * top) / meanNoise)}"/>`).join('')
  const sparkStops = FADE.map(
    ([t, a]) => `<stop offset="${t}" stop-color="#fff" stop-opacity="${op(Math.min(1, (a * top) / meanNoise + SPARK_MIN * Math.min(1, Math.max(0, (0.85 - t) / 0.3))))}"/>`,
  ).join('')
  // forme du remplissage : pilule à gauche, bord droit droit contre la pastille (calotte seule si très court)
  const fillShape = `<rect x="0" y="${TRACK_Y}" width="${clipW}" height="${TRACK_H}" rx="${R}"/>`
  const parts: string[] = []
  parts.push(`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="${SVG_ROOT_STYLE}">`)
  if (fading) {
    const fade = (name: string, from: string, to: string) =>
      `@keyframes ${name}${uid}{from{fill:${from}}}[fill="${to}"]{animation:${name}${uid} ${STATE_FADE_MS}ms ease-in-out both}`
    // la pastille (hex) et les cellules (light, sparkHex) ont des teintes distinctes : un sélecteur par teinte
    parts.push(`<style>${fade('h', prevHex, hex)}${fade('l', mix(prevHex, '#ffffff', 0.55), light)}${fade('s', mix(prevHex, '#ffffff', 0.7), sparkHex)}</style>`)
  }
  parts.push(
    `<defs><clipPath id="c${uid}">${fillShape}</clipPath>` +
      // fondu statique : minimum à gauche (début), plein à droite contre la pastille ; l'onde y naît et s'estompe en reculant
      `<linearGradient id="f${uid}" gradientUnits="userSpaceOnUse" x1="${fadeStart}" y1="0" x2="${fadeEnd}" y2="0">${stops}</linearGradient>` +
      `<mask id="m${uid}"><rect x="0" y="0" width="${Math.max(1, Math.ceil(clipW))}" height="${H}" fill="url(#f${uid})"/></mask>` +
      (sparkPaths
        ? `<linearGradient id="s${uid}" gradientUnits="userSpaceOnUse" x1="${fadeStart}" y1="0" x2="${fadeEnd}" y2="0">${sparkStops}</linearGradient>` +
          `<mask id="k${uid}"><rect x="0" y="0" width="${Math.max(1, Math.ceil(clipW))}" height="${H}" fill="url(#s${uid})"/></mask>`
        : '') +
      `</defs>`,
  )
  // piste gris neutre légèrement chaud : sur un fond de carte bleuté, elle ne refroidit pas le début du remplissage
  parts.push(`<rect x="0" y="${TRACK_Y}" width="${W}" height="${TRACK_H}" rx="${R}" fill="#8a8a87" fill-opacity="0.2"/>`)
  // la translation déplace le treillis vers la gauche pour donner l'impression que les cellules changent de couleur
  const values = Array.from({ length: NCOLS + 1 }, (_, i) => `${-i * pitch} 0`).join('; ')
  // immobile hors `running` (attente, erreur, terminé)
  const anim = live ? `<animateTransform attributeName="transform" type="translate" values="${values}" dur="4s" repeatCount="indefinite" calcMode="discrete"/>` : ''
  if (clipW > 0) parts.push(`<g clip-path="url(#c${uid})"><g mask="url(#m${uid})"><g>${anim}${cellPaths}</g></g>${sparkPaths ? `<g mask="url(#k${uid})"><g>${anim}${sparkPaths}</g></g>` : ''}</g>`)
  plan.steps.forEach((x, i) => {
    const x0 = Math.round((i / n) * W)
    const x1 = Math.round(((i + 1) / n) * W)
    const t =
      x.status === 'done'
        ? `✓ ${x.name}${x.doneAt !== undefined ? ` · ${duration(x.doneAt - plan.startedAt)}` : ''}`
        : `${x.status === 'running' ? '● ' : ''}${x.name}`
    parts.push(`<rect x="${x0}" y="0" width="${x1 - x0}" height="${H}" fill="#0000"><title>${esc(t)}</title></rect>`)
  })
  if (hasBadge) {
    const py = (H - ph) / 2
    const [br, bg, bb] = rgb(hex)
    const textColor = br * 0.299 + bg * 0.587 + bb * 0.114 > 130 ? '#16161a' : '#ffffff'
    parts.push(
      `<rect x="${px}" y="${py}" width="${pw}" height="${ph}" rx="${ph / 2}" fill="${hex}"/>` +
        `<text x="${px + pw / 2}" y="${py + ph / 2 + 4.2}" font-size="12" font-weight="700" fill="${textColor}" text-anchor="middle" font-family="system-ui,sans-serif">${esc(label)}<title>${esc(plan.endedAt !== undefined ? `${plan.title || 'plan'} · ${duration(plan.endedAt - plan.startedAt)}` : plan.title || 'plan')}</title></text>`,
    )
  }
  parts.push('</svg>')
  return parts.join('')
}

const lerp = (a: number, b: number, t: number): number => Math.round(a + (b - a) * t)
/** Mélange `hex` vers `target` (0 = hex, 1 = target), en `#rrggbb`. */
function mix(hex: string, target: string, t: number): string {
  const a = rgb(hex)
  const b = rgb(target)
  return `#${[0, 1, 2].map(i => lerp(a[i]!, b[i]!, t).toString(16).padStart(2, '0')).join('')}`
}
const rgb = (hex: string): [number, number, number] => [
  parseInt(hex.slice(1, 3), 16),
  parseInt(hex.slice(3, 5), 16),
  parseInt(hex.slice(5, 7), 16),
]

// Braille : un caractère = 2 colonnes × 4 rangées de points ; bits par (colonne, rangée).
const BRAILLE_BITS = [
  [0x01, 0x02, 0x04, 0x40],
  [0x08, 0x10, 0x20, 0x80],
] as const
export const BRAILLE_TRACK = 0x2800 + 0xc0 // ⣀ : la piste, deux points en bas

/**
 * Cellules du terminal pour `Raster` : mots `[point de code, avant-plan, arrière-plan]`, u32
 * petit-boutiste. Chaque cellule est un caractère braille : une grille de points d'intensités
 * variables qui reculent d'une demi-cellule par image et s'estompent vers l'arrière.
 */
export function progressCells(plan: Plan, columns: number, frame: number, now?: number): Uint32Array {
  const p = planProgress(plan)
  const filled = Math.round((columns * p.percent) / 100)
  const live = plan.endedAt === undefined && plan.state === 'running'
  const [r, g, b] = rgb(stateHex(plan, now))
  const shift = live ? frame : 0
  const words = new Uint32Array(columns * 3)
  for (let i = 0; i < columns; i++) {
    let ch = BRAILLE_TRACK
    let fg = 0x555566
    if (i < filled) {
      const fade = filled <= 1 ? 1 : 0.12 + 0.88 * (i / (filled - 1)) // 0,12 à l'arrière → 1 à l'avant
      let bits = 0
      for (let sc = 0; sc < 2; sc++) {
        for (let row = 0; row < 4; row++) {
          const norm = (level(2 * i + sc + shift, row) - LEVELS[0]!) / (1 - LEVELS[0]!) // 0 → 1
          if (norm <= fade) bits |= BRAILLE_BITS[sc]![row]!
        }
      }
      ch = 0x2800 + (bits === 0 ? 0x40 : bits)
      const c = (v: number) => lerp(0x30, v, 0.35 + 0.65 * fade)
      fg = (c(r) << 16) | (c(g) << 8) | c(b)
    }
    words[i * 3] = ch
    words[i * 3 + 1] = fg
    words[i * 3 + 2] = 0x01000000
  }
  return words
}

// --- Mascotte (SVG pixel-art) -----------------------------------------------------------------

/** Hauteur par défaut et largeur en px de la mascotte (grille 13 × 12,5). */
export const CRAB_HEIGHT = 30
export const crabWidth = (h = CRAB_HEIGHT): number => Math.round((h * 13) / 12.5)

export type Tier = 'haiku' | 'sonnet' | 'opus' | 'fable'
/** Rang d'un modèle d'après son identifiant ; inconnu : le plus simple. */
export function tierOf(id: string): Tier {
  const m = /haiku|sonnet|opus|fable/i.exec(id)
  return (m?.[0].toLowerCase() as Tier | undefined) ?? 'haiku'
}

/**
 * Mascottes nommées. Un agent choisit la sienne par le champ `mascot` de son frontmatter (à côté de `model` et
 * `effort`, que Claude Code ignore) ; sans champ, il porte le métier de son modèle.
 */
export const MASCOTS = ['scribe', 'chef', 'artiste', 'inspecteur', 'coursier', 'artisan', 'savant', 'mage', 'nu'] as const
export type Mascot = (typeof MASCOTS)[number]
const TIER_MASCOT: Record<Tier, Mascot> = { haiku: 'coursier', sonnet: 'artisan', opus: 'savant', fable: 'mage' }
/** Un émoji par mascotte pour le terminal. */
export const MASCOT_EMOJI: Record<Mascot, string> = {
  scribe: '📜', chef: '🧠', artiste: '🎨', inspecteur: '🔍', coursier: '📦', artisan: '🔨', savant: '🎓', mage: '🔮', nu: '◦',
}
export const isMascot = (v: unknown): v is Mascot => typeof v === 'string' && (MASCOTS as readonly string[]).includes(v)
/** La mascotte d'un agent : celle de sa définition, sinon le métier de son modèle. */
export function mascotOf(r: { mascot?: string; model: string }): Mascot {
  return isMascot(r.mascot) ? r.mascot : TIER_MASCOT[tierOf(r.model)]
}

/** `name` et `mascot` du frontmatter d'une définition d'agent (fichier `.md`), sans dépendre d'un parseur YAML. */
export function agentFront(text: string): { name?: string; mascot?: Mascot } {
  const m = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text)
  if (m === null) return {}
  const field = (k: string) => new RegExp(`^${k}:[ \\t]*["']?([^"'#\\r\\n]*?)["']?[ \\t]*(?:#.*)?$`, 'm').exec(m[1]!)?.[1]
  const name = field('name') || undefined
  const mascot = field('mascot')
  return { name, mascot: isMascot(mascot) ? mascot : undefined }
}

/** `installPath` de chaque plugin installé, par nom de plugin, lu dans `plugins/installed_plugins.json`. */
export function installPathsOf(json: string): Record<string, string> {
  const out: Record<string, string> = {}
  try {
    const plugins = (JSON.parse(json) as { plugins?: Record<string, unknown> }).plugins ?? {}
    for (const [key, v] of Object.entries(plugins)) {
      const entries = (Array.isArray(v) ? v : [v]) as { installPath?: unknown }[]
      const path = entries.find(x => typeof x?.installPath === 'string')?.installPath
      if (typeof path === 'string') out[key.split('@')[0]!] ??= path
    }
  } catch {
    // fichier absent ou d'un autre format : on se replie sur les autres emplacements
  }
  return out
}

/**
 * Dossiers où chercher la définition d'un type d'agent, et le `name` à y trouver. `plugin:nom` : le dossier
 * `agents/` du plugin installé, puis celui d'un plugin voisin du mod (repo de marketplace, `--plugin-dir`) ;
 * `nom` seul : les agents du projet, puis ceux de l'utilisateur. Les types intégrés n'ont pas de fichier.
 */
export function agentDirs(
  type: string,
  ctx: { pluginRoot: string; configDir?: string; sessionRoot?: string; installPaths?: Record<string, string> },
): { dir: string; name: string }[] {
  const cut = type.indexOf(':')
  if (cut > 0) {
    const plugin = type.slice(0, cut)
    const name = type.slice(cut + 1)
    const dirs = [ctx.installPaths?.[plugin], `${ctx.pluginRoot.replace(/\/+$/, '').replace(/\/[^/]+$/, '')}/${plugin}`]
    return dirs.filter((d): d is string => d !== undefined).map(d => ({ dir: `${d}/agents`, name }))
  }
  return [ctx.sessionRoot && `${ctx.sessionRoot}/.claude/agents`, ctx.configDir && `${ctx.configDir}/agents`]
    .filter((d): d is string => typeof d === 'string' && d !== '')
    .map(dir => ({ dir, name: type }))
}

/** Le dossier de configuration de Claude Code d'après le dossier d'un plugin installé (`…/plugins/cache/…`). */
export function configDirOf(pluginRoot: string): string | undefined {
  const at = pluginRoot.indexOf('/plugins/cache/')
  return at > 0 ? pluginRoot.slice(0, at) : undefined
}

/** Enregistre la mascotte lue dans la définition d'un agent. */
export function onMascot(s: Recap, e: { agentId: string; mascot: Mascot }): Recap {
  const run = s.runs[e.agentId]
  return run === undefined || run.mascot === e.mascot ? s : withRun(s, { ...run, mascot: e.mascot })
}

/** Gris de même luminance : la mascotte d'un agent inactif, accessoires compris. */
function grey(hex: string): string {
  const n = parseInt(hex.slice(1), 16)
  const l = Math.round(0.3 * (n >> 16) + 0.59 * ((n >> 8) & 255) + 0.11 * (n & 255))
  const v = l.toString(16).padStart(2, '0')
  return `#${v}${v}${v}`
}

/**
 * Mascotte de Claude Code en pixel-art, grille 13 × 12 (affichée sur deux lignes) : corps, bras, yeux, quatre
 * pattes en bas, habillée selon `mascot` — scribe : capuche, plume et parchemin ; chef : toque à insigne cerveau,
 * veste blanche à manches, foulard, cuillère en bois ; artiste : béret, palette, pinceau, taches de peinture ;
 * inspecteur : casquette de détective, loupe, pipe qui fume (pour un agent de test ou de débogage) ;
 * coursier : casquette, colis, pas pressé ; artisan : bandana, ceinture à outils, marteau ; savant : mortier,
 * lunettes, nœud papillon, diplôme ; mage : chapeau étoilé, bâton à gemme, étincelles. Sans `mascot`, le métier
 * du modèle `tier` ; sans l'un ni l'autre, la mascotte nue (emplacement à venir).
 */
export function crabSvg(o: { height?: number; body?: string; eye?: string; animated?: boolean; tier?: Tier; mascot?: Mascot; mono?: boolean } = {}): string {
  const h = o.height ?? CRAB_HEIGHT
  const mono = o.mono === true // inactif : noir et blanc, accessoires compris
  const c = (hex: string) => (mono ? grey(hex) : hex)
  const body = mono ? '#9a9a9a' : (o.body ?? '#d97757')
  const eye = c(o.eye ?? '#1b1b1f')
  const OY = 5 // le corps occupe les rangées 5 à 11, chapeaux et objets les rangées 0 à 6
  const px = (x: number, y: number, w = 1, hh = 1, fill = body) => `<rect x="${x}" y="${y}" width="${w}" height="${hh}" fill="${fill}"/>`
  const parts = [
    px(2, OY, 9, 5), // corps
    px(0, OY + 2, 2, 2), // bras gauche
    px(11, OY + 2, 2, 2), // bras droit
    px(3, OY + 5, 1, 2),
    px(5, OY + 5, 1, 2),
    px(7, OY + 5, 1, 2),
    px(9, OY + 5, 1, 2), // pattes
  ]
  const eyes = () => parts.push(px(4, OY + 1, 1, 2, eye), px(8, OY + 1, 1, 2, eye))
  const white = c('#f4f4f4')
  const gold = c('#f5c542')
  const red = c('#d83a3a')
  const wood = c('#8b5a2b')
  const design: Mascot = o.mascot ?? (o.tier !== undefined ? TIER_MASCOT[o.tier] : 'nu')
  switch (design) {
    case 'scribe': {
      // capuche de copiste, plume dans la pince droite, parchemin roulé dans la pince gauche
      const hood = c('#6b4a2b')
      parts.push(px(4, 2, 5, 1, hood), px(3, 3, 7, 1, hood), px(2, 4, 9, 1, c('#8a6240')))
      parts.push(px(12, 0, 1, 1, white), px(11, 1, 2, 2, white), px(12, 1, 1, 2, c('#cfcfcf')), px(11, 3, 1, 1, white), px(11, 4, 1, 2, c('#3a3a3a')), px(11, 6, 1, 1, c('#2b4fc7')))
      const roll = c('#c9a86a')
      parts.push(px(0, 2, 2, 4, c('#f3e3b5')), px(0, 1, 2, 1, roll), px(0, 6, 2, 1, roll), px(0, 3, 1, 1, c('#6b4a2b')), px(1, 4, 1, 1, c('#6b4a2b')))
      eyes()
      break
    }
    case 'chef': {
      // le chef de la brigade : toque à insigne cerveau, veste blanche à manches et foulard rouge en pointe, cuillère en bois levée
      const toque = c('#f7f7f7')
      parts.push(px(4, 0, 5, 1, toque), px(3, 1, 7, 1, toque), px(4, 2, 5, 2, toque), px(3, 4, 7, 1, c('#dcdcdc')))
      parts.push(px(5, 2, 3, 2, c('#f08bb0')), px(6, 2, 1, 2, c('#c9567f')))
      parts.push(px(2, OY + 3, 9, 2, toque), px(0, OY + 2, 2, 2, toque), px(11, OY + 2, 2, 2, toque)) // veste et manches
      parts.push(px(5, OY + 3, 3, 1, red), px(6, OY + 4, 1, 1, red), px(4, OY + 4, 1, 1, c('#bdbdbd')), px(8, OY + 4, 1, 1, c('#bdbdbd'))) // foulard, boutons
      parts.push(px(11, 0, 2, 2, c('#b07a43')), px(12, 2, 1, 5, wood))
      eyes()
      break
    }
    case 'artiste': {
      // béret rouge de travers, palette dans la pince gauche, pinceau trempé dans la droite, taches de peinture
      const beret = c('#c0392b')
      parts.push(px(8, 2, 1, 1, beret), px(3, 3, 7, 1, beret), px(2, 4, 7, 1, beret))
      parts.push(px(0, 3, 2, 3, c('#c8a26b')), px(0, 3, 1, 1, c('#e74c3c')), px(1, 4, 1, 1, c('#2f7de1')), px(0, 5, 1, 1, c('#f5c542')))
      parts.push(px(12, 0, 1, 1, c('#2f7de1')), px(12, 1, 1, 1, c('#9aa3ad')), px(12, 2, 1, 5, c('#26262b')))
      parts.push(px(3, OY + 4, 1, 1, c('#2f7de1')), px(9, OY + 3, 1, 1, c('#f5c542')))
      eyes()
      break
    }
    case 'inspecteur': {
      // casquette de détective en tweed et son nœud, loupe dans la pince droite, pipe qui fume dans la gauche
      const tweed = c('#8a6a3f')
      const check = c('#6b5130')
      parts.push(px(6, 1, 1, 1, check), px(4, 2, 5, 1, tweed), px(3, 3, 7, 1, tweed), px(2, 4, 9, 1, tweed))
      parts.push(px(5, 2, 1, 1, check), px(7, 2, 1, 1, check), px(4, 3, 1, 1, check), px(6, 3, 1, 1, check), px(8, 3, 1, 1, check), px(3, 4, 1, 1, check), px(9, 4, 1, 1, check))
      const rim = c('#26262b')
      parts.push(px(11, 0, 2, 1, rim), px(11, 1, 2, 2, c('#cfe8ff')), px(11, 3, 2, 1, rim), px(12, 4, 1, 3, wood))
      parts.push(px(0, 4, 1, 2, c('#5a3a1a')), px(1, 6, 1, 1, c('#3a2a1a')), px(0, 2, 1, 1, c('#bdbdbd')), px(1, 1, 1, 1, c('#d9d9d9')))
      eyes()
      break
    }
    case 'coursier': {
      // le coursier : casquette de face (calotte, logo, visière), colis dans la pince droite
      const cap = c('#2f7de1')
      parts.push(px(4, 2, 5, 1, cap), px(3, 3, 7, 1, cap), px(6, 3, 1, 1, white), px(1, 4, 11, 1, c('#1f5fb3')))
      parts.push(px(11, 5, 2, 2, c('#c08a4a')), px(11, 5, 1, 2, c('#e8c48a')))
      eyes()
      break
    }
    case 'artisan': {
      // l'artisan : bandana à pois, ceinture à outils et sa boucle, marteau dans la pince droite
      parts.push(px(2, 4, 9, 1, red), px(4, 4, 1, 1, white), px(8, 4, 1, 1, white))
      parts.push(px(2, OY + 4, 9, 1, c('#7a4a2a')), px(6, OY + 4, 1, 1, gold), px(3, OY + 4, 1, 1, c('#9aa3ad')), px(9, OY + 4, 1, 1, c('#9aa3ad')))
      parts.push(px(10, 2, 3, 1, c('#9aa3ad')), px(12, 3, 1, 4, wood))
      eyes()
      break
    }
    case 'savant': {
      // le savant : mortier et gland doré, lunettes, nœud papillon, diplôme dans la pince droite
      const ink = c('#26262b')
      parts.push(px(3, 2, 7, 1, ink), px(1, 3, 11, 1, ink), px(4, 4, 5, 1, ink), px(10, 4, 1, 1, gold))
      const lens = c('#cfe8ff')
      parts.push(px(3, OY + 1, 3, 2, lens), px(7, OY + 1, 3, 2, lens), px(6, OY + 1, 1, 1, ink), px(3, OY + 2, 3, 1, c('#8fb8e0')), px(7, OY + 2, 3, 1, c('#8fb8e0')))
      eyes()
      parts.push(px(5, OY + 4, 1, 1, red), px(7, OY + 4, 1, 1, red), px(6, OY + 4, 1, 1, c('#8b1e1e')))
      parts.push(px(11, 4, 2, 3, c('#f3ead2')), px(11, 5, 2, 1, red))
      break
    }
    case 'mage': {
      // le mage : chapeau pointu étoilé, bâton à gemme dans la pince droite, étincelles
      const hat = c('#6d4ac7')
      parts.push(px(7, 0, 1, 1, hat), px(6, 1, 2, 1, hat), px(5, 2, 3, 1, hat), px(4, 3, 5, 1, hat), px(2, 4, 9, 1, c('#4d2f9e')), px(6, 3, 1, 1, gold))
      parts.push(px(12, 2, 1, 5, wood), px(11, 0, 2, 2, c('#8b5cf6')), px(12, 0, 1, 1, c('#c4b5fd')))
      parts.push(px(9, 0, 1, 1, white), px(3, 1, 1, 1, white))
      eyes()
      break
    }
    default:
      eyes()
  }
  const bob = o.animated
    ? `<animateTransform attributeName="transform" type="translate" values="0 0;0 -0.5;0 0" dur="${design === 'coursier' ? '0.35s' : '0.7s'}" repeatCount="indefinite"/>`
    : ''
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${crabWidth(h)}" height="${h}" style="${SVG_ROOT_STYLE}" viewBox="0 -0.5 13 12.5" shape-rendering="crispEdges"><g>${bob}${parts.join('')}</g></svg>`
}
