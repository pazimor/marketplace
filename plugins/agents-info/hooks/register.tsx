// Agents info Mod: observes without changing anything — each hook returns `next(e)` as is.
import { atom, read, update } from 'claude-code'
import type { Hook, Register } from 'claude-code'
import {
  INSTANCE_LABEL,
  MAIN,
  activeRuns,
  SPINNER,
  duration,
  isPlanLive,
  emptyRecap,
  formatTokens,
  markAlerted,
  onComplete,
  onMeasure,
  onPlan,
  onPlanStep,
  onPrompt,
  onSessionStart,
  onSpawn,
  onStep,
  onToolUse,
  onUsage,
  pendingAlerts,
  planProgress,
  progressCells,
  progressSvg,
  crabSvg,
  crabWidth,
  CRAB_HEIGHT,
  progressWidth,
  PROGRESS_HEIGHT,
  barWidth,
  isFading,
  workflowStages,
  stateHex,
  cardWidth,
  CARD_GAP,
  tierOf,
  mascotOf,
  MASCOT_EMOJI,
  agentDirs,
  agentFront,
  configDirOf,
  installPathsOf,
  onMascot,
  readOptions,
  shimmerBar,
  shortModel,
  stripRuns,
  totals,
  weight,
  workedMs,
  agentTree,
  agentKind,
  agentName,
  modelBuckets,
  forecast,
  limitLabel,
  limitLevel,
  limitSvg,
  limitCells,
  LIMIT_HEX,
  LIMIT_HEIGHT,
  usageSvg,
  usageCells,
  USAGE_HEX,
  columnsPx,
  localClock,
  toggleFold,
} from './recap'
import type { AgentRun, Limit, Mascot, Options, PaneSection, Tokens } from './recap'

const PANE = 'agents-info'
type Dollar = Parameters<Hook<'session.measure'>>[0]

const recap = atom({ plugin: 'agents-info', key: 'recap' } as const, emptyRecap())
const hidden = atom({ plugin: 'agents-info', key: 'hidden' } as const, false)
const tick = atom({ plugin: 'agents-info', key: 'tick' } as const, 0)
// Pane sections folded by the person (limits, agents, prompts, usage): shared by every surface, all open by default.
const folded = atom({ plugin: 'agents-info', key: 'folded' } as const, [] as string[])

// Mascot declared by each agent type (`mascot:` in its frontmatter), read once per session.
const mascots = new Map<string, Mascot | undefined>()
async function mascotFor($: Dollar, type: string): Promise<Mascot | undefined> {
  if (mascots.has(type)) return mascots.get(type)
  let found: Mascot | undefined
  try {
    const configDir = configDirOf($.plugin.root)
    const installed = configDir === undefined ? '' : await $.fs.read(`${configDir}/plugins/installed_plugins.json`).catch(() => '')
    const sessionRoot = await $.session.root().catch(() => undefined)
    const dirs = agentDirs(type, { pluginRoot: $.plugin.root, configDir, sessionRoot, installPaths: installPathsOf(installed) })
    let matched = false
    search: for (const { dir, name } of dirs) {
      const files = await $.fs.list(dir).catch(() => [])
      for (const f of files) {
        if (!f.name.endsWith('.md')) continue
        const front = agentFront(await $.fs.read(`${dir}/${f.name}`).catch(() => ''))
        if ((front.name ?? f.name.slice(0, -3)) === name) {
          found = front.mascot
          matched = true
          break search
        }
      }
    }
    // a plugin agent with no definition found: say so in the debug log rather than falling back silently
    if (!matched && type.includes(':')) $.ui.log(`agents-info: definition of ${type} not found, using the model mascot`, { to: 'debug' })
  } catch {
    // definition not found or unreadable: the trade of the model
  }
  mascots.set(type, found)
  return found
}

/** Raises the new alerts as toasts and marks them. */
async function raise($: Dollar, o: Options) {
  const s = await read($, recap)
  const alerts = pendingAlerts(s, o)
  if (alerts.length === 0) return
  await update($, recap, cur => markAlerted(cur, alerts))
  for (const a of alerts) $.ui.toast(`agents-info: ${a.text}`)
}

export const register: Register = (on, options) => {
  const o = readOptions(options)
  const autoOpen = options?.autoOpen !== false
  const compactBand = options?.compactBand !== false

  on('session.start', async ($, e, next) => {
    // `/recap` is a built-in command: the recap opens with `/agents-info`. A refused registration
    // must not deprive the session of the rest of the hook.
    await $.command
      .register({ name: 'agents-info', description: 'Agents info: agents, models, efforts, tokens, limits' })
      .catch(() => undefined)
    const settings = await $.settings.read()
    const agent = typeof settings.agent === 'string' ? settings.agent : undefined
    const model = await $.session.model()
    const at = await $.clock.now()
    await update($, recap, s => onSessionStart(s, { surface: e.surface, agent, model, at }))
    // Step plan tools: the orchestrator calls them so the band shows progress.
    await $.command.register({ name: 'progress', description: 'Hide or show the progress bars' }).catch(() => undefined)
    await $.command.register({ name: 'progress-clear', description: 'Clear the current plan' }).catch(() => undefined)
    const stepSchema = {
      anyOf: [
        { type: 'string' },
        { type: 'object', properties: { name: { type: 'string' }, agents: { type: 'integer' } }, required: ['name'] },
      ],
    }
    await $.tool
      .register({
        name: 'plan',
        description:
          "Declares (or re-declares) the step plan of the work in progress: progress bar above the prompt, with the sub-agents below. Call it once before delegating; when sent back mid-way, the steps already finished keep their state (matched by name). Gives either `stages` (phases with their steps) or `steps`. A step can be `{ name, agents }`: `agents` = number of agent calls planned, the bar then advances at each finished agent (essential for a workflow, whose `workflow: true` marks the plan). It has no effect on the project.",
        inputSchema: {
          type: 'object',
          properties: {
            title: { type: 'string', description: 'Short title of the plan' },
            workflow: { type: 'boolean', description: 'The plan follows a workflow: a set of agents whose number is known' },
            stages: {
              type: 'array',
              description: 'Phases, in order',
              items: {
                type: 'object',
                properties: { name: { type: 'string' }, steps: { type: 'array', items: stepSchema } },
                required: ['name', 'steps'],
              },
            },
            steps: { type: 'array', items: stepSchema, description: 'Steps without a phase' },
          },
        },
      })
      .catch(() => undefined)
    await $.tool
      .register({
        name: 'step',
        description:
          "Advances the plan: `step` (number starting at 1, or name) + `status` (`done` completes it and moves on to the next one, `failed`, `running`). `state` signals the state of the plan: `input` (waits for the user), `error`, `running`; `note` a one-line explanation. It has no effect on the project.",
        inputSchema: {
          type: 'object',
          properties: {
            step: { type: ['integer', 'string'], description: "Step number (starting at 1) or its name" },
            status: { type: 'string', enum: ['running', 'done', 'failed'] },
            state: { type: 'string', enum: ['running', 'input', 'error'] },
            note: { type: 'string' },
          },
        },
      })
      .catch(() => undefined)
    // The band animates (and the clocks advance) as long as a plan or a sub-agent is active. Outside the terminal,
    // the SVGs animate on their own: the tick only serves the clocks, once per second.
    void $.clock.every(e.surface === 'terminal' ? 250 : 1000, async () => {
      const cur = await read($, recap)
      if (isPlanLive(cur) || isFading(cur.plan, await $.clock.now()) || Object.values(cur.runs).some(r => r.id !== MAIN && r.status === 'running'))
        await update($, tick, n => n + 1)
    })
    if (e.isInteractive && autoOpen) void $.ui.open({ id: PANE, title: 'Agents info' })
    return next(e)
  })

  on('tool.call', { tool: 'mcp__agents-info__plan' }, async ($, e) => {
    const at = await $.clock.now()
    const parse = (v: unknown): (string | { name: string; agents?: number })[] =>
      Array.isArray(v)
        ? v.map(x =>
            typeof x === 'object' && x !== null
              ? { name: String((x as { name?: unknown }).name ?? ''), agents: Number((x as { agents?: unknown }).agents) }
              : String(x),
          )
        : []
    const stages = Array.isArray(e.stages)
      ? (e.stages as { name?: unknown; steps?: unknown }[]).map(x => ({ name: String(x.name ?? ''), steps: parse(x.steps) }))
      : []
    const steps = parse(e.steps)
    const isWorkflow = typeof e.workflow === 'boolean' ? e.workflow : undefined
    await update($, recap, s =>
      onPlan(s, { title: typeof e.title === 'string' ? e.title : undefined, steps, stages, isWorkflow, at }),
    )
    const total = steps.length + stages.reduce((n, x) => n + x.steps.length, 0)
    return { result: `Plan saved: ${total} step(s).` }
  })

  on('tool.call', { tool: 'mcp__agents-info__step' }, async ($, e) => {
    const at = await $.clock.now()
    const status = e.status === 'done' || e.status === 'failed' || e.status === 'running' ? e.status : undefined
    const step = typeof e.step === 'number' || typeof e.step === 'string' ? e.step : undefined
    const state = e.state === 'input' || e.state === 'error' || e.state === 'running' ? e.state : undefined
    const note = typeof e.note === 'string' ? e.note : undefined
    const before = await read($, recap)
    await update($, recap, s => onPlanStep(s, { step, status, state, note, at }))
    const after = await read($, recap)
    if (before.plan === null) return { result: "No plan declared: call `plan` first." }
    if (step !== undefined && after.plan === before.plan)
      return { result: `Unknown step. Steps: ${before.plan.steps.map((x, i) => `${i + 1}. ${x.name}`).join('; ')}` }
    return { result: 'Plan updated.' }
  })

  // Last tool of each agent, for the strips under the bar. Changes nothing.
  on('tool.call', async ($, e, next) => {
    await update($, recap, s => onToolUse(s, { agentId: e.agentId, tool: e.tool }))
    return next(e)
  })

  on('command.run', { command: 'progress' }, async $ => {
    await update($, hidden, h => !h)
    return { text: (await read($, hidden)) ? 'Bars hidden.' : 'Bars shown.' }
  })

  on('command.run', { command: 'progress-clear' }, async $ => {
    await update($, recap, s => ({ ...s, plan: null }))
    return { text: 'Plan cleared.' }
  })

  on('command.run', { command: 'agents-info' }, async $ => {
    await $.ui.open({ id: PANE, title: 'Agents info', focus: true })
    return { text: 'Agents info pane opened.' }
  })

  on('turn.start', async ($, e, next) => {
    const at = await $.clock.now()
    await update($, recap, s => onPrompt(s, { text: e.text, at }))
    return next(e)
  })

  on('agent.spawn', async ($, e, next) => {
    const r = await next(e)
    if (r.deny === undefined && r.agentId !== undefined) {
      const at = await $.clock.now()
      const agentId = r.agentId
      const agent = e.subagentType || e.name || 'general-purpose'
      await update($, recap, s =>
        onSpawn(s, { agentId, parentId: e.parentAgentId, agent, model: r.model, fork: e.fork, at, task: e.description }),
      )
      const mascot = await mascotFor($, agent)
      if (mascot !== undefined) await update($, recap, s => onMascot(s, { agentId, mascot }))
    }
    return r
  })

  on('turn.step', async function* ($, e, next) {
    const at = await $.clock.now()
    await update($, recap, s => onStep(s, { agentId: e.agentId, model: e.model, effort: e.effort, at }))
    const stream = next(e)
    while (true) {
      const step = await stream.next()
      if (step.done) {
        await raise($, o)
        return step.value
      }
      const chunk = step.value
      if (chunk.kind === 'stop' && chunk.usage !== null) {
        const usage = chunk.usage
        await update($, recap, s => onUsage(s, { agentId: e.agentId, effort: e.effort, usage }))
      }
      yield chunk
    }
  })

  on('turn.complete', async ($, e, next) => {
    const at = await $.clock.now()
    await update($, recap, s => onComplete(s, { agentId: e.agentId, reason: e.reason, at }))
    return next(e)
  })

  on('session.measure', async ($, e, next) => {
    const at = await $.clock.now()
    await update($, recap, s => onMeasure(s, { rateLimits: e.rateLimits, costUsd: e.cost?.usd, at }))
    await raise($, o)
    return next(e)
  })

  // The pane: limits, agents (the main agent and its peers at the top level), prompts, usage — each section folds.
  // Remote surfaces draw the gauges, mascots and bars as Svg; the terminal draws text, emoji and block bars.
  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const els = $.ui.resolve(e) as Record<string, any> // the element table depends on the surface
    const { Box, Text, Button } = els
    const isText = e.surface === 'terminal'
    const s = await read($, recap)
    const closed = await read($, folded)
    await read($, tick) // the clocks of the running agents advance with the band's tick
    const now = await $.clock.now()
    const cols = e.props.bodyColumns
    const all = totals(s)
    const total = weight(all)
    const main = s.runs[MAIN]
    const subs = Object.values(s.runs).filter(r => r.id !== MAIN)
    const active = subs.filter(r => r.status === 'running').length
    const limits = Object.values(s.limits)
    const share = (t: Tokens) => (total > 0 ? Math.round((100 * weight(t)) / total) : 0)
    const cost = s.costUsd !== null ? ` · $${s.costUsd.toFixed(2)}` : ''

    const section = (id: PaneSection, title: string, summary: string, body: () => unknown) => {
      const open = !closed.includes(id)
      return (
        <Box key={`sec-${id}`} flexDirection="column" marginTop={1}>
          <Box key={`sec-head-${id}`} flexDirection="row">
            <Button key={`fold-${id}`} plain onPress={() => update($, folded, f => toggleFold(f, id))}>
              {`${open ? '▾' : '▸'} ${title}`}
            </Button>
            <Text dimColor wrap="truncate-end"> · {summary}</Text>
          </Box>
          {open && body()}
        </Box>
      )
    }
    // terminal bars: one colored run of cells per part
    const usageText = (t: Tokens, width: number, max: number, key: string) => {
      const c = usageCells(t, width, max)
      return [
        <Text key={`${key}-w`} color={USAGE_HEX.cacheWrite}>{'█'.repeat(c.cacheWrite)}</Text>,
        <Text key={`${key}-o`} color={USAGE_HEX.output}>{'█'.repeat(c.output)}</Text>,
        <Text key={`${key}-i`} color={USAGE_HEX.input}>{'█'.repeat(c.input)}</Text>,
        <Text key={`${key}-f`} dimColor>{'░'.repeat(c.free)}</Text>,
      ]
    }

    const header = (
      <Box key="pane-head" flexDirection="row" justifyContent="space-between">
        <Text bold>{main === undefined ? 'Session not started' : 'Session'}</Text>
        <Text dimColor wrap="truncate-end">
          {formatTokens(total)} tok{cost}{main !== undefined ? ` · ${duration(workedMs(main, now))}` : ''}
        </Text>
      </Box>
    )

    // --- Limits: one gauge per window, forecast to the reset, alert thresholds of the options
    const limitRow = (l: Limit) => {
      const f = forecast(l)
      const level = limitLevel(l.percentUsed, o)
      const label = limitLabel(l.kind)
      const reset = l.resetsAt === undefined ? NaN : Date.parse(l.resetsAt)
      const isLong = l.kind !== 'five_hour'
      const tail =
        f.exhaustedAt !== null ? `full ≈ ${localClock(f.exhaustedAt, isLong)}` : f.atReset !== null ? `→ ${f.atReset}% at reset` : ''
      const tailColor = f.exhaustedAt !== null ? LIMIT_HEX.critical : undefined
      const resets = Number.isNaN(reset) ? '' : `resets ${localClock(reset, isLong)}`
      if (isText) {
        const c = limitCells(l, Math.max(10, Math.min(40, cols - 34)))
        return (
          <Box key={`lim-${l.kind}`} flexDirection="row">
            <Text wrap="truncate-end">
              {label.padEnd(7)}
              <Text color={LIMIT_HEX[level]}>{'█'.repeat(c.used)}</Text>
              <Text color={LIMIT_HEX[limitLevel(f.atReset ?? 0, o)]}>{'▒'.repeat(c.projected)}</Text>
              <Text dimColor>{'░'.repeat(c.free)}</Text>
              <Text color={LIMIT_HEX[level]} bold> {String(l.percentUsed).padStart(3)}%</Text>
              <Text color={tailColor} dimColor={tailColor === undefined}> {tail || resets}</Text>
            </Text>
          </Box>
        )
      }
      const px = columnsPx(cols - 14)
      return (
        <Box key={`lim-${l.kind}`} flexDirection="column">
          <Box key={`lim-row-${l.kind}`} flexDirection="row" alignItems="center">
            <Text dimColor>{label.padEnd(7)}</Text>
            <els.Svg
              key={`lim-svg-${l.kind}`}
              source={limitSvg(l, px, o)}
              width={px}
              height={LIMIT_HEIGHT}
              alt={`${label} limit: ${l.percentUsed}% used${f.atReset !== null ? `, ${f.atReset}% forecast at the reset` : ''}`}
            />
            <Text color={LIMIT_HEX[level]} bold> {l.percentUsed}%</Text>
          </Box>
          <Text dimColor wrap="truncate-end">
            {'       '}{resets}{resets !== '' && tail !== '' ? ' · ' : ''}<Text color={tailColor}>{tail}</Text>
          </Text>
        </Box>
      )
    }

    // --- Agents: a card each, usage bar scaled against the heaviest agent, numbers on hover
    const maxAgent = Math.max(1, ...Object.values(s.runs).map(r => weight(r.tokens)))
    const detail = (r: AgentRun) => (
      <Box position="absolute" top={1} left={2} display="none" hover={{ display: 'flex' }}
        flexDirection="column" borderStyle="round" paddingX={1}>
        <Text key="d-1" wrap="truncate-end">input {formatTokens(r.tokens.input)} · output {formatTokens(r.tokens.output)}</Text>
        <Text key="d-2" wrap="truncate-end">cache read {formatTokens(r.tokens.cacheRead)} · written {formatTokens(r.tokens.cacheWrite)}</Text>
      </Box>
    )
    const agentCard = (r: AgentRun, depth: number) => {
      const off = r.status !== 'running'
      const mark = r.status === 'failed' ? ' ✗' : off ? ' ✓' : ''
      const title = r.id === MAIN ? 'main agent' : (r.task ?? r.agent)
      const meta = `${shortModel(r.model)} · ${r.effort}${r.tool !== undefined && !off ? ` (${r.tool})` : ''}`
      const side = `${duration(workedMs(r, now))} · ${formatTokens(weight(r.tokens))}`
      const mascot = mascotOf(r)
      if (isText) {
        const lead = depth === 0 ? '' : `${'  '.repeat(depth - 1)}└ `
        return (
          <Box key={`run-${r.id}`} flexDirection="column">
            <Box key={`run-a-${r.id}`} flexDirection="row" justifyContent="space-between">
              <Text color={r.status === 'failed' ? 'red' : undefined} dimColor={r.status === 'done'} wrap="truncate-end">
                {lead}{MASCOT_EMOJI[mascot]} {title}{mark}
              </Text>
              <Box key={`run-as-${r.id}`} flexShrink={0}><Text dimColor> {side}</Text></Box>
            </Box>
            <Box key={`run-b-${r.id}`} flexDirection="row" justifyContent="space-between">
              <Text dimColor wrap="truncate-end">{' '.repeat(lead.length + 3)}{meta} · {agentKind(r)}</Text>
              <Box key={`run-bs-${r.id}`} flexShrink={0}>
                <Text> {usageText(r.tokens, 10, maxAgent, `bar-${r.id}`)}<Text dimColor> {String(share(r.tokens)).padStart(2)}%</Text></Text>
              </Box>
            </Box>
            {detail(r)}
          </Box>
        )
      }
      const barPx = columnsPx(cols - depth * 2 - 26)
      const crabBody = r.status === 'failed' ? '#ef4444' : off ? '#8a7f7a' : '#d97757'
      return (
        <Box key={`run-${r.id}`} flexDirection="row" alignItems="center" marginLeft={depth * 2} borderStyle="round" paddingX={1}>
          {depth > 0 && <Text dimColor>└ </Text>}
          <els.Svg key={`crab-${r.id}`} source={crabSvg({ body: crabBody, animated: !off, mascot, mono: off })}
            alt={`${mascot} mascot`} width={crabWidth()} height={CRAB_HEIGHT} />
          <Box key={`run-txt-${r.id}`} flexDirection="column" paddingLeft={1} flexGrow={1} flexShrink={1}>
            <Text color={r.status === 'failed' ? 'red' : undefined} dimColor={r.status === 'done'} wrap="truncate-end">{title}{mark}</Text>
            <Text dimColor wrap="truncate-end">{meta}</Text>
            <Text dimColor wrap="truncate-end">{agentKind(r)}</Text>
            <els.Svg key={`use-${r.id}`} source={usageSvg(r.tokens, barPx, maxAgent, { height: 6 })} width={barPx} height={6}
              alt={`usage: ${formatTokens(weight(r.tokens))} tokens, ${share(r.tokens)}% of the session`} />
          </Box>
          <Box key={`run-side-${r.id}`} flexDirection="column" alignItems="flex-end" flexShrink={0} paddingLeft={1}>
            <Text dimColor>{duration(workedMs(r, now))}</Text>
            <Text dimColor>{formatTokens(weight(r.tokens))} · {share(r.tokens)}%</Text>
          </Box>
          {detail(r)}
        </Box>
      )
    }

    // --- Prompts: the last ones, each with the agents it launched or resumed
    const prompts = s.prompts.slice(-5)
    const promptRow = (p: (typeof prompts)[number]) => {
      const entries = s.timeline.filter(t => t.promptIndex === p.index)
      const head = (
        <Box key={`prompt-head-${p.index}`} flexDirection="row" justifyContent="space-between">
          <Text wrap="truncate-end">#{p.index} {p.text}</Text>
          <Box key={`prompt-at-${p.index}`} flexShrink={0}><Text dimColor> {localClock(p.at)}</Text></Box>
        </Box>
      )
      if (isText || entries.length === 0) {
        return (
          <Box key={`prompt-${p.index}`} flexDirection="column">
            {head}
            <Text dimColor wrap="wrap">
              {'   '}{entries.length === 0 ? 'main agent only' : entries.map(t => `${INSTANCE_LABEL[t.kind]} ${agentName(s.runs[t.agentId]?.agent ?? t.agentId)}`).join(' · ')}
            </Text>
          </Box>
        )
      }
      return (
        <Box key={`prompt-${p.index}`} flexDirection="column">
          {head}
          <Box key={`chips-${p.index}`} flexDirection="row" flexWrap="wrap" gap={1} marginLeft={3}>
            {entries.map((t, i) => {
              const r = s.runs[t.agentId]
              return (
                <Box key={`chip-${p.index}-${i}`} flexDirection="row" alignItems="center" borderStyle="round" paddingX={1}>
                  {r !== undefined && (
                    <els.Svg key={`chip-crab-${p.index}-${i}`} source={crabSvg({ height: 14, mascot: mascotOf(r), mono: r.status !== 'running' })}
                      alt={`${mascotOf(r)} mascot`} width={crabWidth(14)} height={14} />
                  )}
                  <Text dimColor={t.kind !== 'new'}> {INSTANCE_LABEL[t.kind]} {agentName(r?.agent ?? t.agentId)}</Text>
                </Box>
              )
            })}
          </Box>
        </Box>
      )
    }

    // --- Usage: the session as a whole, then per model × effort
    const models = modelBuckets(s)
    const maxModel = Math.max(1, ...models.map(b => weight(b.tokens)))
    const usage = () => {
      if (total === 0) return <Text key="usage-none" dimColor>no usage yet</Text>
      const legend = (
        <Text key="usage-legend" wrap="truncate-end">
          <Text color={USAGE_HEX.cacheWrite}>■</Text><Text dimColor> cache written {formatTokens(all.cacheWrite)}  </Text>
          <Text color={USAGE_HEX.output}>■</Text><Text dimColor> output {formatTokens(all.output)}  </Text>
          <Text color={USAGE_HEX.input}>■</Text><Text dimColor> input {formatTokens(all.input)} · cache read {formatTokens(all.cacheRead)} not counted</Text>
        </Text>
      )
      const name = (b: (typeof models)[number]) => `${shortModel(b.model)} · ${b.effort}`
      const nameCols = Math.min(24, Math.max(14, ...models.map(b => name(b).length + 1)))
      if (isText) {
        const w = Math.max(10, Math.min(48, cols - nameCols - 16))
        return [
          <Box key="usage-total" flexDirection="row">
            <Text>{'total'.padEnd(nameCols)}{usageText(all, w, total, 'total')}<Text bold> {formatTokens(total).padStart(6)}</Text></Text>
          </Box>,
          legend,
          ...models.map((b, i) => (
            <Box key={`model-${i}`} flexDirection="row">
              <Text wrap="truncate-end">
                {name(b).padEnd(nameCols)}{usageText(b.tokens, w, maxModel, `model-${i}`)}
                {' '}{formatTokens(weight(b.tokens)).padStart(6)}<Text dimColor> {String(share(b.tokens)).padStart(2)}%</Text>
              </Text>
            </Box>
          )),
        ]
      }
      const totalPx = columnsPx(cols - 14)
      const modelPx = columnsPx(cols - nameCols - 18)
      return [
        <Box key="usage-total" flexDirection="row" alignItems="center">
          <els.Svg key="usage-total-svg" source={usageSvg(all, totalPx, total, { height: 10 })} width={totalPx} height={10}
            alt={`session usage: ${formatTokens(total)} tokens`} />
          <Text bold> {formatTokens(total)} tok</Text>
        </Box>,
        legend,
        ...models.map((b, i) => (
          <Box key={`model-${i}`} flexDirection="row" alignItems="center">
            <els.Svg key={`model-crab-${i}`} source={crabSvg({ height: 18, mascot: mascotOf({ model: b.model }) })}
              alt={`${mascotOf({ model: b.model })} mascot`} width={crabWidth(18)} height={18} />
            <Box key={`model-name-${i}`} width={nameCols} paddingLeft={1}>
              <Text wrap="truncate-end">{shortModel(b.model)}<Text dimColor> · {b.effort}</Text></Text>
            </Box>
            <els.Svg key={`model-svg-${i}`} source={usageSvg(b.tokens, modelPx, maxModel, { height: 8 })} width={modelPx} height={8}
              alt={`${name(b)}: ${formatTokens(weight(b.tokens))} tokens`} />
            <Text> {formatTokens(weight(b.tokens))}<Text dimColor> {share(b.tokens)}%</Text></Text>
          </Box>
        )),
      ]
    }

    return (
      <Box flexDirection="column">
        {header}
        {section('limits', 'Limits', limits.length === 0 ? 'no measure yet' : limits.map(l => `${limitLabel(l.kind)} ${l.percentUsed}%`).join(' · '), () =>
          limits.length === 0 ? <Text key="limits-none" dimColor>no measure yet</Text> : limits.map(limitRow),
        )}
        {section('agents', 'Agents', `${active} active / ${subs.length}`, () => agentTree(s).map(x => agentCard(x.run, x.depth)))}
        {section('prompts', 'Prompts', `${s.prompts.length} prompt(s)`, () =>
          prompts.length === 0 ? <Text key="prompts-none" dimColor>no prompt</Text> : prompts.map(promptRow),
        )}
        {section('usage', 'Usage', `${formatTokens(total)} tok${cost}`, usage)}
      </Box>
    )
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const s = await read($, recap)
    const frame = await read($, tick)
    const isHidden = await read($, hidden)
    const main = s.runs[MAIN]
    if (!compactBand || e.props.hasSurvey || main === undefined) return next(e)
    const els = $.ui.resolve(e) as Record<string, any> // the element table depends on the surface
    const { Box, Text, Button } = els
    const now = await $.clock.now()
    const active = activeRuns(s)
    const plan = s.plan
    const prog = plan !== null ? planProgress(plan) : null
    const isTerminal = e.surface === 'terminal'
    const strips = stripRuns(s, now)
    const stateColor = { running: 'magenta', input: 'yellow', error: 'red', done: 'green' } as const
    const mark = (st: string) => (st === 'done' ? '✓' : st === 'failed' ? '✗' : st === 'running' ? '●' : '○')

    const live = plan !== null && plan.endedAt === undefined
    const color = plan === null ? undefined : isTerminal ? stateColor[plan.state] : stateHex(plan, now) // desktop: the text follows the fade
    const elapsed = plan !== null ? duration((plan.endedAt ?? now) - plan.startedAt) : ''
    const spin =
      plan === null ? '' : live && plan.state === 'running' ? (isTerminal ? SPINNER[frame % SPINNER.length]! : '●') : plan.state === 'input' ? '?' : plan.state === 'error' ? '✗' : '✓'

    // model · effort, then the bar on the same line: the bar gives up the columns of the label, the lead and the ✕
    const showBar = plan !== null && prog !== null && !isHidden
    const label = `${shortModel(main.model)} · ${main.effort}${showBar ? ' | ' : ''}`
    const lead = showBar && isTerminal ? `${spin} ${prog.stage !== '' && live ? `[${prog.stage}] ` : ''}` : ''
    const reserved = label.length + lead.length + 3
    const barColumns = Math.max(10, Math.min(80, e.props.bodyColumns - 4 - reserved))
    const barPx = barWidth(e.props.bodyColumns, reserved)
    const identity = (
      <Box key="identity" flexDirection="column" alignItems="center" justifyContent="center">
        <Box key="identity-row" flexDirection="row" alignItems="center" justifyContent="center" width="100%">
          <Text dimColor wrap="truncate-end">{label}</Text>
          {lead !== '' && <Text color={color} wrap="truncate-end">{lead}</Text>}
          {showBar &&
            (isTerminal ? (
              <els.Raster
                key="plan-bar"
                columns={barColumns}
                rows={1}
                cells={new Uint8Array(progressCells(plan, barColumns, frame, now).buffer).toBase64()}
              />
            ) : (
              <els.Svg
                key="plan-bar-svg"
                source={progressSvg(plan, barPx, now)}
                width={progressWidth(barPx)}
                height={PROGRESS_HEIGHT}
                alt={`${plan.title || 'plan'}: ${prog.percent}%`}
              />
            ))}
          {showBar && (
            <Button key="plan-close" dimColor plain onPress={() => update($, recap, cur => ({ ...cur, plan: null }))}>
              {' ✕'}
            </Button>
          )}
        </Box>
        {showBar && !plan.isWorkflow && (
          <Text color={color} wrap="truncate-end">
            {isTerminal ? ' ' : `${spin} `}
            {prog.percent}% · {prog.done}/{prog.total}
            {prog.agentsPlanned > 0 ? ` · ${prog.agentsDone}/${prog.agentsPlanned} agents` : ''} · {elapsed}{' '}
          </Text>
        )}
        {plan !== null && !isHidden && (
          <Box position="absolute" bottom={1} left={2} display="none" hover={{ display: 'flex' }}
            flexDirection="column" borderStyle="round" paddingX={1}>
            {plan.isWorkflow && <Text dimColor>workflow</Text>}
            {plan.steps.map((x, i) => (
              <Text key={`st-${i}`} dimColor={x.status === 'todo'} color={x.status === 'failed' ? 'red' : undefined} wrap="truncate-end">
                {mark(x.status)} {x.stage !== '' ? `${x.stage} · ` : ''}{x.name}
                {x.agents > 0 ? ` · ${x.finished}/${x.agents} agents` : ''}
                {x.doneAt !== undefined ? ` · ${duration(x.doneAt - plan.startedAt)}` : ''}
              </Text>
            ))}
          </Box>
        )}
      </Box>
    )
    const card = (r: (typeof strips)[number]) => {
      const crabBody = r.status === 'failed' ? '#ef4444' : r.status === 'done' ? '#8a7f7a' : '#d97757'
      const tint = r.status === 'failed' ? 'red' : undefined
      return (
        <Box key={`strip-${r.id}`} width={cardWidth(e.props.bodyColumns)} paddingRight={CARD_GAP}>
          <Box key={`strip-body-${r.id}`} borderStyle="round" paddingX={1} flexGrow={1}>
            {isTerminal ? (
              <Text color={tint} dimColor={r.status === 'done'}>{MASCOT_EMOJI[mascotOf(r)]} </Text>
            ) : (
              <els.Svg
                key={`crab-${r.id}`}
                source={crabSvg({ body: crabBody, animated: r.status === 'running', mascot: mascotOf(r), mono: r.status === 'done' })}
                alt={`agent ${mascotOf(r)}`}
                width={crabWidth()}
                height={CRAB_HEIGHT}
              />
            )}
            <Box flexDirection="column" paddingLeft={1}>
              <Text color={tint} dimColor={r.status === 'done'} wrap="truncate-end">{r.task ?? r.agent}</Text>
              <Text dimColor wrap="truncate-end">
                {shortModel(r.model)} · {r.effort}
                {r.tool !== undefined && r.status === 'running' ? ` (${r.tool})` : ''} — {duration(workedMs(r, now))}
              </Text>
            </Box>
          </Box>
        </Box>
      )
    }
    // slot for an agent planned by the workflow and not launched yet
    const placeholder = (key: string, n: number) => (
      <Box key={key} width={cardWidth(e.props.bodyColumns)} paddingRight={CARD_GAP}>
        <Box key={`${key}-body`} borderStyle="round" paddingX={1} flexGrow={1}>
          {isTerminal ? (
            <Text dimColor>◌ </Text>
          ) : (
            <els.Svg key={`${key}-crab`} source={crabSvg({ mono: true })} alt="upcoming agent" width={crabWidth()} height={CRAB_HEIGHT} />
          )}
          <Box flexDirection="column" paddingLeft={1}>
            <Text dimColor wrap="truncate-end">agent {n} — upcoming</Text>
            <Text dimColor wrap="truncate-end">waiting</Text>
          </Box>
        </Box>
      </Box>
    )
    const stages = workflowStages(s)
    const showWorkflow = plan !== null && plan.isWorkflow && stages.length > 0

    if (isHidden || (plan === null && strips.length === 0)) return <Box key="band" flexDirection="column">{identity}</Box>

    return (
      <Box key="band" flexDirection="column">
        {identity}
        {showWorkflow &&
          stages.map((st, i) => {
            const head = `${st.planned > 0 ? `${st.done}/${st.planned} agents · ` : ''}${st.name}`
            const sc = st.status === 'failed' ? 'red' : st.status === 'running' ? color : undefined
            return (
              <Box key={`stage-${i}`} flexDirection="column" width="100%">
                {i === 0 ? (
                  <Text color={color} wrap="truncate-end">
                    {isTerminal ? ' ' : `${spin} `}{prog?.percent}% · {head} · {elapsed}:
                  </Text>
                ) : (
                  <Text color={sc} dimColor={st.status === 'todo'} wrap="truncate-end">{head}:</Text>
                )}
                <Box key={`grid-${i}`} flexDirection="row" flexWrap="wrap" rowGap={CARD_GAP} width="100%">
                  {st.runs.map(card)}
                  {Array.from({ length: st.placeholders }, (_, k) => placeholder(`ph-${i}-${k}`, st.runs.length + k + 1))}
                </Box>
              </Box>
            )
          })}
        {!showWorkflow && strips.length > 0 && (
          <Box key="agent-grid" flexDirection="row" flexWrap="wrap" rowGap={CARD_GAP} width="100%">
            {strips.map(card)}
          </Box>
        )}
      </Box>
    )
  })
}
