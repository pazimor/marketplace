// Contrat de types du plugin session-recap : le modèle du récap et son état déclaré au moteur.

export type Instance = 'nouvelle' | 'reprise' | 'fork'
export type Status = 'running' | 'done' | 'failed'
export type Effort = string

export type Tokens = { input: number; output: number; cacheRead: number; cacheWrite: number }

export type AgentRun = {
  id: string // agentId, stable entre reprises ; MAIN pour l'agent principal
  parentId: string | null // null = agent principal
  agent: string // type d'agent (scribe, orchestrateur, executant-low…)
  promptIndex: number // prompt utilisateur qui a lancé ce run
  instance: Instance
  spawnModel?: string // modèle résolu au lancement (`agent.spawn` → résultat)
  model: string // dernier modèle vu sur `turn.step`
  effort: Effort // dernier effort vu sur `turn.step` ('—' quand le modèle n'en prend pas)
  status: Status
  task?: string // description de la tâche confiée (`agent.spawn`)
  stepIndex?: number // étape du plan en cours au lancement (index dans `plan.steps`)
  tool?: string // dernier outil appelé par cet agent (`tool.call`)
  mascot?: string // mascotte lue dans le frontmatter de sa définition (`mascot:`), absente = métier du modèle
  resumes: number
  startedAt: number
  endedAt?: number
  tokens: Tokens
}

export type TimelineEntry = { promptIndex: number; agentId: string; kind: Instance; at: number }
export type Prompt = { index: number; text: string; at: number }
export type Bucket = { agent: string; model: string; effort: Effort; tokens: Tokens; calls: number }
export type Limit = {
  kind: string
  percentUsed: number
  resetsAt?: string
  at: number
  firstAt: number
  firstPercent: number
}

export type PlanStep = {
  name: string
  stage: string
  status: 'todo' | 'running' | 'done' | 'failed'
  doneAt?: number
  agents: number // appels d'agents prévus pour cette étape (0 = non précisé)
  started: number // agents lancés pendant l'étape
  finished: number // agents terminés
}
export type PlanState = 'running' | 'input' | 'error' | 'done'
export type Plan = { title: string; isWorkflow: boolean; steps: PlanStep[]; state: PlanState; note: string; startedAt: number; endedAt?: number; prevState?: PlanState; stateAt?: number }

export type Recap = {
  surface: string | null
  startAgent: string
  startInferred: boolean // vrai quand l'agent principal est déduit (réglage absent) et non lu
  plan: Plan | null // plan en étapes déclaré par l'orchestrateur (outils mcp__session-recap__*)
  runs: Record<string, AgentRun>
  order: string[]
  prompts: Prompt[]
  timeline: TimelineEntry[]
  buckets: Record<string, Bucket>
  limits: Record<string, Limit>
  costUsd: number | null
  alerted: string[]
}

export type Options = {
  limitWarn: number
  limitCritical: number
  agentTokenLimit: number
  sessionTokenLimit: number
  mainShareLimit: number
  modelMismatch: boolean
}

export type Usage = {
  input_tokens: number
  output_tokens: number
  cache_read_input_tokens: number
  cache_creation_input_tokens: number
  model: string
}

export type Alert = { key: string; text: string }
export type Forecast = { atReset: number | null; exhaustedAt: number | null }

declare module 'claude-code' {
  interface PluginState {
    'session-recap': { recap: Recap; view: 'compact' | 'detail'; tick: number; hidden: boolean }
  }
}
