// The pane and the band are drawn on each surface, fed by the engine's events.
import { expect, mock, test } from 'claude-code/testing'

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
