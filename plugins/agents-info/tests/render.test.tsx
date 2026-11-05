// The pane and the band are drawn on each surface, fed by the engine's events.
import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const SURFACES = ['terminal', 'desktop', 'vscode', 'mobile'] as const
const SCROLL = { offset: 0, bodyRows: 40 }

test('the pane shows limits, agents, prompts and usage, each section folds; the band shows the plan', async ($, on) => {
  mock.clock(on)
  on('session.start', async ($, e) => e)
  on('turn.start', (async ($: unknown, e: unknown) => e) as never)
  on('session.measure', (async ($: unknown, e: unknown) => e) as never)
  on('command.register' as never, (async () => ({ value: { command: 'agents-info' } })) as never)
  on('settings.read' as never, (async () => ({ value: {} })) as never)
  on('session.model' as never, (async () => ({ value: 'claude-small-1-0' })) as never)
  on('agent.spawn', async () => ({ model: 'claude-mid-5-5', agentId: 'relay1' }))
  on('turn.step', async function* ($, e) {
    yield { kind: 'stop', stopReason: 'end_turn', usage: { input_tokens: 2, output_tokens: 138, cache_read_input_tokens: 0, cache_creation_input_tokens: 2548, model: 'claude-mid-5-5' } }
    return { turnId: e.turnId, index: e.index, answer: 'ok', toolUses: [] } as never
  })
  await $.session.start({ cwd: '/projet', surface: 'desktop', isInteractive: false })
  await $.turn.start({ text: 'Do the work', turnId: 't1' })
  await $.agent.spawn({
    tool_use_id: 'u1', prompt: 'go', description: 'relay', subagentType: 'relay', provider: 'model' as never,
    parentModel: 'claude-small-1-0', background: true, fork: false,
  })
  const stream = $.turn.step({ turnId: 't2', index: 0, model: 'claude-mid-5-5', effort: 'low', messageCount: 1, agentId: 'relay1' })
  for await (const _ of stream) { /* consommer */ }
  await $.session.measure({ context: { window: 200000 }, rateLimits: [{ kind: 'seven_day', percentUsed: 84, resetsAt: '2026-10-05T13:00:00.000Z' }], changed: ['rateLimits'] })

  for (const surface of SURFACES) {
    const ui = await $.ui.mount({
      plugin: 'agents-info', surface, component: 'Pane', requestId: 'agents-info',
      props: { title: 'Agents info', isFocused: false, bodyColumns: 100, placement: 'dock', scroll: SCROLL, view: {} },
    })
    expect(await ui.find({ type: 'Text', text: /^Session$/ })).toBeDefined()
    // four foldable sections, all open by default, each with its summary
    for (const title of ['Limits', 'Agents', 'Prompts', 'Usage']) expect(await ui.find({ type: 'Button', text: new RegExp(`▾ ${title}`) })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /7 days 84%/ })).toBeDefined()
    expect(await ui.find({ key: 'lim-seven_day' })).toBeDefined()
    // agents: the main agent, never renamed, then the relay with its task, model and effort
    expect(await ui.find({ type: 'Text', text: /main agent/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /default · session/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /mid-5-5 · low/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /relay · #1/ })).toBeDefined()
    // prompts and the agents each one launched
    expect(await ui.find({ type: 'Text', text: /#1 Do the work/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /new relay/ })).toBeDefined()
    // usage per model × effort
    expect(await ui.find({ key: 'model-0' })).toBeDefined()
    if (surface === 'terminal') {
      expect(await ui.findAll({ type: 'Svg' })).toHaveLength(0)
      expect(await ui.find({ type: 'Text', text: /📦|🔨|🎓|🔮|◦/ })).toBeDefined() // mascot emoji
    } else {
      const alts = (await ui.findAll({ type: 'Svg' })).map(x => String(x.props.alt))
      expect(alts.some(a => /^7 days limit: 84% used/.test(a))).toBe(true)
      expect(alts.some(a => /^usage: /.test(a))).toBe(true)
    }
    // a press folds the section and keeps its summary; the state is shared between surfaces: unfold it again
    await ui.press({ key: 'fold-limits' })
    expect(await ui.find({ key: 'lim-seven_day' })).toBeUndefined()
    expect(await ui.find({ type: 'Button', text: /▸ Limits/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /7 days 84%/ })).toBeDefined()
    await ui.press({ key: 'fold-limits' })
    expect(await ui.find({ key: 'lim-seven_day' })).toBeDefined()
    await ui.unmount()
  }
  // a narrow pane (docked in a small window): the bars shrink to their floor, nothing is refused
  for (const surface of ['terminal', 'desktop'] as const) {
    const narrow = await $.ui.mount({
      plugin: 'agents-info', surface, component: 'Pane', requestId: 'agents-info',
      props: { title: 'Agents info', isFocused: false, bodyColumns: 40, placement: 'dock', scroll: SCROLL, view: {} },
    })
    expect(await narrow.find({ key: 'lim-seven_day' })).toBeDefined()
    expect(await narrow.find({ key: 'model-0' })).toBeDefined()
    expect(await narrow.find({ type: 'Text', text: /mid-5-5 · low/ })).toBeDefined()
    await narrow.unmount()
  }
  for (const surface of ['terminal', 'desktop'] as const) {
    const band = await $.ui.mount({
      plugin: 'agents-info', surface, component: 'AbovePrompt',
      props: { hasSurvey: false, isWorking: false, maxRows: 5, bodyColumns: 120, scroll: SCROLL, view: {} },
    })
    // plan declared by the orchestrator: bar, phase, percentage, sub-agent strip
    await $.tool.call({
      tool: 'mcp__agents-info__plan', tool_use_id: 'p1',
      title: 'Livraison', workflow: true,
      stages: [{ name: 'Read', steps: ['canon', 'roadmap'] }, { name: 'Do', steps: [{ name: 'code', agents: 2 }, 'tests'] }],
    } as never)
    await $.tool.call({ tool: 'mcp__agents-info__step', tool_use_id: 'p2', step: 'canon', status: 'done' } as never)
    const withPlan = await $.ui.mount({
      plugin: 'agents-info', surface, component: 'AbovePrompt',
      props: { hasSurvey: false, isWorking: false, maxRows: 5, bodyColumns: 120, scroll: SCROLL, view: {} },
    })
    expect(await withPlan.find({ type: 'Text', text: /25% · Read/ })).toBeDefined()
    expect(await withPlan.find({ type: 'Text', text: /mid-5-5 · low/ })).toBeDefined()
    // workflow: one section per phase, planned agents in "upcoming" slots
    expect(await withPlan.find({ type: 'Text', text: /0\/2 agents · Do/ })).toBeDefined()
    expect(await withPlan.find({ type: 'Text', text: /agent 1 — upcoming/ })).toBeDefined()
    await withPlan.unmount()
    await band.unmount()
  }
})

test('the pane of a session that has just started: every section open, each with its empty state', async ($, on) => {
  mock.clock(on)
  on('session.start', async ($, e) => e)
  on('command.register' as never, (async () => ({ value: { command: 'agents-info' } })) as never)
  on('settings.read' as never, (async () => ({ value: {} })) as never)
  on('session.model' as never, (async () => ({ value: 'claude-small-1-0' })) as never)
  await $.session.start({ cwd: '/projet', surface: 'desktop', isInteractive: false })
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({
      plugin: 'agents-info', surface, component: 'Pane', requestId: 'agents-info',
      props: { title: 'Agents info', isFocused: false, bodyColumns: 60, placement: 'dock', scroll: SCROLL, view: {} },
    })
    expect(await ui.find({ type: 'Text', text: /^Session$/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^no measure yet$/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /main agent/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /0 active \/ 0/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^no prompt$/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^no usage yet$/ })).toBeDefined()
    await ui.unmount()
  }
})

import { emptyRecap, onPrompt, onSessionStart, onSpawn, onUsage } from '../hooks/recap'

const PANE_PROPS = { title: 'Agents info', isFocused: false, bodyColumns: 100, placement: 'dock', scroll: SCROLL, view: {} } as const
const NOW = Date.parse('2026-10-15T09:00:00.000Z')

/** A session as the snapshot of its earlier process holds it. */
function savedRecap(prompt: string, task: string) {
  let s = onSessionStart(emptyRecap(), { surface: 'desktop', agent: undefined, model: 'claude-small-1-0', at: NOW - 2 * 3600_000 })
  s = onPrompt(s, { text: prompt, at: NOW - 2 * 3600_000 })
  s = onSpawn(s, { agentId: 'rev1', agent: 'level-design:level-design-reviewer', model: 'claude-mid-5-5', fork: false, at: NOW - 3600_000, task })
  return onUsage(s, { agentId: 'rev1', effort: 'high', usage: { input_tokens: 5, output_tokens: 900, cache_read_input_tokens: 0, cache_creation_input_tokens: 40000, model: 'claude-mid-5-5' } })
}

/** What the engine answers the Mod at the start of a session. */
function engine(on: On, sessionId: string) {
  on('session.start', async ($, e) => e)
  on('command.register' as never, (async () => ({ value: { command: 'agents-info' } })) as never)
  on('settings.read' as never, (async () => ({ value: {} })) as never)
  on('session.model' as never, (async () => ({ value: 'claude-small-1-0' })) as never)
  on('session.id' as never, (async () => ({ value: sessionId })) as never)
  on('session.usage' as never, (async () => ({
    value: { startedAt: NOW - 2 * 3600_000, context: { window: 200000 }, rateLimits: [{ kind: 'five_hour', percentUsed: 42, resetsAt: '2026-10-15T12:00:00.000Z' }], cost: { usd: 3.2 } },
  })) as never)
}

test('a process that restarted gets its recap back from the store, and the limits without waiting for a measurement', async ($, on) => {
  mock.clock(on, { now: NOW })
  mock.store(on, {
    'recap:s1': { savedAt: NOW - 600_000, recap: savedRecap('Build the cave level', 'review the cave') },
    'recap:s9': { savedAt: NOW - 60_000, recap: savedRecap('Work of another session', 'review the dunes') }, // a session beside this one
  })
  engine(on, 's1')
  await $.session.start({ cwd: '/projet', surface: null, isInteractive: false })
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'agents-info', surface, component: 'Pane', requestId: 'agents-info', props: PANE_PROPS })
    expect(await ui.find({ type: 'Text', text: /#1 Build the cave level/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /restored \d\d:\d\d/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /review the cave ✓/ })).toBeDefined() // it was running: the restart ended it
    expect(await ui.find({ type: 'Text', text: /Work of another session|review the dunes/ })).toBeUndefined()
    expect(await ui.find({ key: 'lim-five_hour' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /5 h 42%/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /no measure yet/ })).toBeUndefined()
    await ui.unmount()
  }
})

test('the recap is saved at the end of each main turn, under the session id', async ($, on) => {
  mock.clock(on, { now: NOW })
  const store = new Map<string, unknown>()
  on('store.get' as never, (async ($: unknown, e: { key: string }) => ({ value: store.get(e.key) })) as never)
  on('store.set' as never, (async ($: unknown, e: { key: string; value: unknown }) => (store.set(e.key, e.value), { value: undefined })) as never)
  on('store.keys' as never, (async () => ({ value: [...store.keys()] })) as never)
  engine(on, 's1')
  on('turn.start', (async ($: unknown, e: unknown) => e) as never)
  on('turn.complete', (async ($: unknown, e: { answer: string }) => ({ text: e.answer })) as never)
  await $.session.start({ cwd: '/projet', surface: null, isInteractive: false })
  await $.turn.start({ text: 'Build the cave level', turnId: 't1' })
  expect(store.has('recap:s1')).toBe(false)
  await $.turn.complete({ turnId: 't1', answer: 'done', durationMs: 10, isAborted: false, reason: 'answer' })
  const saved = store.get('recap:s1') as { savedAt: number; startedAt: number; recap: { prompts: { text: string }[] } }
  expect(saved.savedAt).toBe(NOW)
  expect(saved.startedAt).toBe(NOW - 2 * 3600_000)
  expect(saved.recap.prompts.map(p => p.text)).toEqual(['Build the cave level'])
})

test('the desktop app attaches after a non-interactive start: the pane opens then, once', async ($, on) => {
  mock.clock(on)
  engine(on, 's1')
  const opened: string[] = []
  on('ui.open' as never, (async ($: unknown, e: { id: string }) => (opened.push(e.id), { value: { isPlaced: true } })) as never)
  on('ui.panes' as never, (async () => ({ value: opened.map(id => ({ id, title: 'Agents info', isShown: true, isFocused: false, isPlaced: true, plugin: 'agents-info' })) })) as never)
  on('session.attach', (async ($: unknown, e: { clientId: string }) => ({ clientId: e.clientId })) as never)
  await $.session.start({ cwd: '/projet', surface: null, isInteractive: false })
  expect(opened).toEqual([])
  await $.session.attach({ surface: 'desktop', clientId: 'desktop:default' })
  expect(opened).toEqual(['agents-info'])
  await $.session.attach({ surface: 'mobile', clientId: 'mobile:phone' }) // already open: not opened again
  expect(opened).toEqual(['agents-info'])
})
