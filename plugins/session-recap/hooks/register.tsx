// Mod récap de session : observe sans rien modifier — chaque hook rend `next(e)` tel quel.
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
  barWidth,
  isFading,
  workflowStages,
  stateHex,
  cardWidth,
  tierOf,
  TIER_EMOJI,
  readOptions,
  shimmerBar,
  shortModel,
  sortedBuckets,
  stripRuns,
  table,
  totals,
  weight,
} from './recap'
import type { AgentRun, Options } from './recap'

const PANE = 'session-recap'
type Dollar = Parameters<Hook<'session.measure'>>[0]

const recap = atom({ plugin: 'session-recap', key: 'recap' } as const, emptyRecap())
// Affichage du panneau : compact (défaut, détails au survol) ou détaillé (tout déplié).
const hidden = atom({ plugin: 'session-recap', key: 'hidden' } as const, false)
const tick = atom({ plugin: 'session-recap', key: 'tick' } as const, 0)
const view = atom({ plugin: 'session-recap', key: 'view' } as const, 'compact' as 'compact' | 'detail')

/** Lève en toast les alertes nouvelles et les marque. */
async function raise($: Dollar, o: Options) {
  const s = await read($, recap)
  const alerts = pendingAlerts(s, o)
  if (alerts.length === 0) return
  await update($, recap, cur => markAlerted(cur, alerts))
  for (const a of alerts) $.ui.toast(`récap : ${a.text}`)
}

export const register: Register = (on, options) => {
  const o = readOptions(options)
  const autoOpen = options?.autoOpen !== false
  const compactBand = options?.compactBand !== false

  on('session.start', async ($, e, next) => {
    // `/recap` est une commande intégrée : le récap s'ouvre par `/session-recap`. Un refus
    // d'enregistrement ne doit pas priver la session du reste du hook.
    await $.command
      .register({ name: 'session-recap', description: 'Récap de session : agents, modèles, efforts, tokens, limites' })
      .catch(() => undefined)
    const settings = await $.settings.read()
    const agent = typeof settings.agent === 'string' ? settings.agent : undefined
    const model = await $.session.model()
    const at = await $.clock.now()
    await update($, recap, s => onSessionStart(s, { surface: e.surface, agent, model, at }))
    // Outils du plan en étapes : l'orchestrateur les appelle pour que le bandeau montre l'avancement.
    await $.command.register({ name: 'progress', description: 'Masque ou montre les barres de progression' }).catch(() => undefined)
    await $.command.register({ name: 'progress-clear', description: 'Efface le plan en cours' }).catch(() => undefined)
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
          "Déclare (ou redéclare) le plan en étapes du travail en cours : barre de progression au-dessus du prompt, avec les sous-agents dessous. À appeler une fois avant de déléguer ; renvoyé en cours de route, les étapes déjà terminées gardent leur état (par intitulé). Donne soit `stages` (phases avec leurs étapes), soit `steps`. Une étape peut être `{ name, agents }` : `agents` = nombre d'appels d'agents prévus, la barre avance alors à chaque agent terminé (indispensable pour un workflow, dont `workflow: true` marque le plan). N'a aucun effet sur le projet.",
        inputSchema: {
          type: 'object',
          properties: {
            title: { type: 'string', description: 'Intitulé court du plan' },
            workflow: { type: 'boolean', description: 'Le plan suit un workflow : un ensemble d’agents dont le nombre est connu' },
            stages: {
              type: 'array',
              description: 'Phases, dans l’ordre',
              items: {
                type: 'object',
                properties: { name: { type: 'string' }, steps: { type: 'array', items: stepSchema } },
                required: ['name', 'steps'],
              },
            },
            steps: { type: 'array', items: stepSchema, description: 'Étapes sans phase' },
          },
        },
      })
      .catch(() => undefined)
    await $.tool
      .register({
        name: 'step',
        description:
          "Fait avancer le plan : `step` (numéro à partir de 1, ou nom) + `status` (`done` termine et passe à la suivante, `failed`, `running`). `state` signale l'état du plan : `input` (attend l'utilisateur), `error`, `running`; `note` une ligne d'explication. N'a aucun effet sur le projet.",
        inputSchema: {
          type: 'object',
          properties: {
            step: { type: ['integer', 'string'], description: "Numéro de l'étape (à partir de 1) ou son nom" },
            status: { type: 'string', enum: ['running', 'done', 'failed'] },
            state: { type: 'string', enum: ['running', 'input', 'error'] },
            note: { type: 'string' },
          },
        },
      })
      .catch(() => undefined)
    // Le bandeau s'anime (et les horloges avancent) tant qu'un plan ou un sous-agent est actif.
    void $.clock.every(250, async () => {
      const cur = await read($, recap)
      if (isPlanLive(cur) || isFading(cur.plan, await $.clock.now()) || Object.values(cur.runs).some(r => r.id !== MAIN && r.status === 'running'))
        await update($, tick, n => n + 1)
    })
    if (e.isInteractive && autoOpen) void $.ui.open({ id: PANE, title: 'Récap' })
    return next(e)
  })

  on('tool.call', { tool: 'mcp__session-recap__plan' }, async ($, e) => {
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
    return { result: `Plan enregistré : ${total} étape(s).` }
  })

  on('tool.call', { tool: 'mcp__session-recap__step' }, async ($, e) => {
    const at = await $.clock.now()
    const status = e.status === 'done' || e.status === 'failed' || e.status === 'running' ? e.status : undefined
    const step = typeof e.step === 'number' || typeof e.step === 'string' ? e.step : undefined
    const state = e.state === 'input' || e.state === 'error' || e.state === 'running' ? e.state : undefined
    const note = typeof e.note === 'string' ? e.note : undefined
    const before = await read($, recap)
    await update($, recap, s => onPlanStep(s, { step, status, state, note, at }))
    const after = await read($, recap)
    if (before.plan === null) return { result: "Aucun plan déclaré : appelle d'abord `plan`." }
    if (step !== undefined && after.plan === before.plan)
      return { result: `Étape inconnue. Étapes : ${before.plan.steps.map((x, i) => `${i + 1}. ${x.name}`).join(' ; ')}` }
    return { result: 'Plan mis à jour.' }
  })

  // Dernier outil de chaque agent, pour les bandes sous la barre. Ne modifie rien.
  on('tool.call', async ($, e, next) => {
    await update($, recap, s => onToolUse(s, { agentId: e.agentId, tool: e.tool }))
    return next(e)
  })

  on('command.run', { command: 'progress' }, async $ => {
    await update($, hidden, h => !h)
    return { text: (await read($, hidden)) ? 'Barres masquées.' : 'Barres affichées.' }
  })

  on('command.run', { command: 'progress-clear' }, async $ => {
    await update($, recap, s => ({ ...s, plan: null }))
    return { text: 'Plan effacé.' }
  })

  on('command.run', { command: 'session-recap' }, async $ => {
    await $.ui.open({ id: PANE, title: 'Récap', focus: true })
    return { text: 'Panneau récap ouvert.' }
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

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const s = await read($, recap)
    const mode = await read($, view)
    const main = s.runs[MAIN]
    const all = totals(s)
    const toggle = (
      <Button
        key="toggle-view"
        hotkey="d"
        dimColor
        onPress={() => update($, view, v => (v === 'compact' ? 'detail' : 'compact'))}
      >
        {mode === 'compact' ? 'détail' : 'compact'}
      </Button>
    )
    const card = (lines: string[]) => (
      <Box position="absolute" top={1} left={2} display="none" hover={{ display: 'flex' }}
        flexDirection="column" borderStyle="round" paddingX={1}>
        {lines.map((l, i) => (
          <Text key={`c-${i}`} wrap="truncate-end">{l}</Text>
        ))}
      </Box>
    )
    const header = (
      <Box>
        <Text bold wrap="truncate-end">
          {main === undefined ? 'Session non démarrée' : `${main.agent} · ${shortModel(main.model)} · ${main.effort}`}
        </Text>
        <Text dimColor> · {formatTokens(weight(all))}{s.costUsd !== null ? ` · ${s.costUsd.toFixed(2)} $` : ''} </Text>
        {toggle}
      </Box>
    )
    const agentCard = (r: AgentRun) =>
      card([
        `${r.agent} (${INSTANCE_LABEL[r.instance]}${r.resumes > 0 ? ` ×${r.resumes + 1}` : ''}) · prompt #${r.promptIndex}`,
        `${shortModel(r.model)} · effort ${r.effort} · ${r.status}`,
        `entrée ${formatTokens(r.tokens.input)} · sortie ${formatTokens(r.tokens.output)}`,
        `cache lu ${formatTokens(r.tokens.cacheRead)} · écrit ${formatTokens(r.tokens.cacheWrite)}`,
      ])
    const runs = Object.values(s.runs)

    if (mode === 'compact') {
      return (
        <Box flexDirection="column">
          {header}
          {runs.map(r => (
            <Box key={`run-${r.id}`}>
              <Text dimColor={r.status !== 'running'} wrap="truncate-end">
                {r.status === 'running' ? '● ' : r.status === 'failed' ? '✗ ' : '○ '}
                {r.agent} · {shortModel(r.model)} · {r.effort}
              </Text>
              {agentCard(r)}
            </Box>
          ))}
        </Box>
      )
    }

    // Détail : la timeline se réduit à une ligne par prompt (3 derniers), le reste au survol.
    const recent = s.prompts.slice(-3)
    const rows = [
      ['agent', 'modèle', 'effort', 'entrée', 'sortie', 'c. lu', 'c. écrit', 'appels'],
      ...sortedBuckets(s).map(b => [
        b.agent,
        shortModel(b.model),
        b.effort,
        formatTokens(b.tokens.input),
        formatTokens(b.tokens.output),
        formatTokens(b.tokens.cacheRead),
        formatTokens(b.tokens.cacheWrite),
        String(b.calls),
      ]),
    ]
    const lines = table(rows, 3)
    return (
      <Box flexDirection="column">
        {header}

        <Box flexDirection="column" marginTop={1}>
          <Text bold>Prompts</Text>
          {recent.length === 0 && <Text dimColor>aucun prompt</Text>}
          {recent.map(p => {
            const entries = s.timeline.filter(t => t.promptIndex === p.index)
            return (
              <Box key={`prompt-${p.index}`}>
                <Text wrap="truncate-end">
                  #{p.index} {p.text} <Text dimColor>· {entries.length} agent(s)</Text>
                </Text>
                {entries.length > 0 &&
                  card(
                    entries.map(t => {
                      const r = s.runs[t.agentId]
                      return `${INSTANCE_LABEL[t.kind]} ${r?.agent ?? t.agentId} · ${r !== undefined ? shortModel(r.model) : '?'} · ${r?.effort ?? '—'}${r?.status === 'running' ? ' · actif' : ''}`
                    }),
                  )}
              </Box>
            )
          })}
        </Box>

        <Box flexDirection="column" marginTop={1}>
          <Text bold>Agents</Text>
          {runs.map(r => (
            <Box key={`run-${r.id}`}>
              <Text dimColor={r.status !== 'running'} wrap="truncate-end">
                {r.status === 'running' ? '● ' : r.status === 'failed' ? '✗ ' : '○ '}
                {r.agent} · {shortModel(r.model)} · {r.effort} · {INSTANCE_LABEL[r.instance]}
                {r.resumes > 0 ? ` ×${r.resumes + 1}` : ''} · {formatTokens(weight(r.tokens))}
              </Text>
              {agentCard(r)}
            </Box>
          ))}
        </Box>

        <Box flexDirection="column" marginTop={1}>
          <Text bold>Consommation</Text>
          {lines.slice(0, 1).map(l => (
            <Text key="th" bold dimColor wrap="truncate-end">{l}</Text>
          ))}
          {lines.slice(1).map((l, i) => (
            <Text key={`tr-${i}`} wrap="truncate-end">{l}</Text>
          ))}
          {lines.length > 1 && (
            <Text bold wrap="truncate-end">
              total {formatTokens(weight(all))} (entrée + sortie + cache écrit)
            </Text>
          )}
        </Box>
      </Box>
    )
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const s = await read($, recap)
    const frame = await read($, tick)
    const isHidden = await read($, hidden)
    const main = s.runs[MAIN]
    if (!compactBand || e.props.hasSurvey || main === undefined) return next(e)
    const els = $.ui.resolve(e) as Record<string, any> // la table d'éléments dépend de la surface
    const { Box, Text, Button } = els
    const now = await $.clock.now()
    const active = activeRuns(s)
    const plan = s.plan
    const prog = plan !== null ? planProgress(plan) : null
    const width = Math.max(10, Math.min(80, e.props.bodyColumns - 16))
    const isTerminal = e.surface === 'terminal'
    const strips = stripRuns(s, now)
    const stateColor = { running: 'magenta', input: 'yellow', error: 'red', done: 'green' } as const
    const mark = (st: string) => (st === 'done' ? '✓' : st === 'failed' ? '✗' : st === 'running' ? '●' : '○')

    const live = plan !== null && plan.endedAt === undefined
    const color = plan === null ? undefined : isTerminal ? stateColor[plan.state] : stateHex(plan, now) // desktop : le texte suit le fondu
    const elapsed = plan !== null ? duration((plan.endedAt ?? now) - plan.startedAt) : ''
    const spin =
      plan === null ? '' : live && plan.state === 'running' ? SPINNER[frame % SPINNER.length]! : plan.state === 'input' ? '?' : plan.state === 'error' ? '✗' : '✓'

    const identity = (
      <Box key="identity" flexDirection="column" alignItems="center" justifyContent="center">
        <Text dimColor wrap="truncate-end">
          {shortModel(main.model)} · {main.effort}
          {plan === null || isHidden ? '' : ' | '}
        </Text>
        {plan !== null && prog !== null && !isHidden && isTerminal && (
          <Text color={color} wrap="truncate-end">
            {spin} {prog.stage !== '' && live ? `[${prog.stage}] ` : ''}
          </Text>
        )}
        {plan !== null && prog !== null && !isHidden && (
          <Box key="plan-progress-row" flexDirection="column" alignItems="center" justifyContent="center" width="100%">
            {isTerminal ? (
              <els.Raster
                key="plan-bar"
                columns={width}
                rows={1}
                cells={new Uint8Array(progressCells(plan, width, frame, now).buffer).toBase64()}
              />
            ) : (
              <Box key="plan-bar-container" display="flex" justifyContent="center" width="100%">
                <els.Svg
                  source={progressSvg(plan, barWidth(e.props.bodyColumns), now)}
                  alt={`${plan.title || 'plan'} : ${prog.percent} %`}
                  isInteractive
                />
              </Box>
            )}
            {!plan.isWorkflow && (
              <Text color={color} wrap="truncate-end">
                {isTerminal ? ' ' : `${spin} `}
                {prog.percent} % · {prog.done}/{prog.total}
                {prog.agentsPlanned > 0 ? ` · ${prog.agentsDone}/${prog.agentsPlanned} agents` : ''} · {elapsed}{' '}
              </Text>
            )}
          </Box>
        )}
        {plan !== null && !isHidden && (
          <Button key="plan-close" dimColor plain onPress={() => update($, recap, cur => ({ ...cur, plan: null }))}>
            ✕
          </Button>
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
        <Box key={`strip-${r.id}`} width={cardWidth(e.props.bodyColumns)} borderStyle="round" paddingX={1}>
          <Box>
            {isTerminal ? (
              <Text color={tint} dimColor={r.status === 'done'}>{TIER_EMOJI[tierOf(r.model)]} </Text>
            ) : (
              <els.Svg
                key={`crab-${r.id}`}
                source={crabSvg({ body: crabBody, animated: r.status === 'running', tier: tierOf(r.model), mono: r.status === 'done' })}
                alt={`agent ${tierOf(r.model)}`}
                isInteractive
              />
            )}
            <Box flexDirection="column" paddingLeft={1}>
              <Text color={tint} dimColor={r.status === 'done'} wrap="truncate-end">{r.task ?? r.agent}</Text>
              <Text dimColor wrap="truncate-end">
                {shortModel(r.model)} · {r.effort}
                {r.tool !== undefined && r.status === 'running' ? ` (${r.tool})` : ''} — {duration((r.endedAt ?? now) - r.startedAt)}
              </Text>
            </Box>
          </Box>
        </Box>
      )
    }
    // emplacement d'un agent prévu par le workflow et pas encore lancé
    const placeholder = (key: string, n: number) => (
      <Box key={key} width={cardWidth(e.props.bodyColumns)} borderStyle="round" paddingX={1}>
        {isTerminal ? (
          <Text dimColor>◌ </Text>
        ) : (
          <els.Svg source={crabSvg({ mono: true })} alt="agent à venir" isInteractive />
        )}
        <Box flexDirection="column" paddingLeft={1}>
          <Text dimColor wrap="truncate-end">agent {n} — à venir</Text>
          <Text dimColor wrap="truncate-end">en attente</Text>
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
                    {isTerminal ? ' ' : `${spin} `}{prog?.percent} % · {head} · {elapsed}:
                  </Text>
                ) : (
                  <Text color={sc} dimColor={st.status === 'todo'} wrap="truncate-end">{head}:</Text>
                )}
                <Box key={`grid-${i}`} flexDirection="row" flexWrap="wrap" width="100%">
                  {st.runs.map(card)}
                  {Array.from({ length: st.placeholders }, (_, k) => placeholder(`ph-${i}-${k}`, st.runs.length + k + 1))}
                </Box>
              </Box>
            )
          })}
        {!showWorkflow && strips.length > 0 && (
          <Box key="agent-grid" flexDirection="row" flexWrap="wrap" width="100%">
            {strips.map(card)}
          </Box>
        )}
      </Box>
    )
  })
}
