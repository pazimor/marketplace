// Type contract of the agents-info plugin: the recap model and its state declared to the engine.

export type Instance = 'new' | 'resumed' | 'fork'
export type Status = 'running' | 'done' | 'failed'
export type Effort = string

export type Tokens = { input: number; output: number; cacheRead: number; cacheWrite: number }

export type AgentRun = {
  id: string // agentId, stable across resumes; MAIN for the main agent
  parentId: string | null // null = main agent
  agent: string // agent type (scribe, orchestrator, executor-low…)
  promptIndex: number // user prompt that launched this run
  instance: Instance
  spawnModel?: string // model resolved at launch (`agent.spawn` → result)
  model: string // last model seen on `turn.step`
  effort: Effort // last effort seen on `turn.step` ('—' when the model takes none)
  status: Status
  task?: string // description of the delegated task (`agent.spawn`)
  stepIndex?: number // plan step in progress at launch (index in `plan.steps`)
  tool?: string // last tool called by this agent (`tool.call`)
  mascot?: string // mascot read from the frontmatter of its definition (`mascot:`), absent = the model's trade
  resumes: number
  startedAt: number
  endedAt?: number
  activeSince?: number // start of the current stretch of work (launch or resume)
  activeMs?: number // worked time of the finished stretches: the waits between two resumes are not counted
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
  agents: number // agent calls planned for this step (0 = not specified)
  started: number // agents launched during the step
  finished: number // agents finished
}
export type PlanState = 'running' | 'input' | 'error' | 'done'
export type Plan = { title: string; isWorkflow: boolean; steps: PlanStep[]; state: PlanState; note: string; startedAt: number; endedAt?: number; prevState?: PlanState; stateAt?: number }

export type Recap = {
  surface: string | null
  startAgent: string
  plan: Plan | null // step plan declared by the orchestrator (mcp__agents-info__* tools)
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
    'agents-info': { recap: Recap; folded: string[]; tick: number; hidden: boolean }
  }
}
