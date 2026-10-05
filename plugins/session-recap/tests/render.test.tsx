// Le panneau et le bandeau se dessinent sur chaque surface, alimentés par les événements du moteur.
import { expect, mock, test } from 'claude-code/testing'

const SURFACES = ['terminal', 'desktop', 'vscode', 'mobile'] as const
const SCROLL = { offset: 0, bodyRows: 40 }

test('le panneau récap montre principal, limites, timeline et consommation', async ($, on) => {
  mock.clock(on)
  on('session.start', async ($, e) => e)
  on('turn.start', (async ($: unknown, e: unknown) => e) as never)
  on('session.measure', (async ($: unknown, e: unknown) => e) as never)
  on('command.register' as never, (async () => ({ value: { command: 'session-recap' } })) as never)
  on('settings.read' as never, (async () => ({ value: {} })) as never)
  on('session.model' as never, (async () => ({ value: 'claude-small-1-0' })) as never)
  on('agent.spawn', async () => ({ model: 'claude-mid-5-5', agentId: 'relais1' }))
  on('turn.step', async function* ($, e) {
    yield { kind: 'stop', stopReason: 'end_turn', usage: { input_tokens: 2, output_tokens: 138, cache_read_input_tokens: 0, cache_creation_input_tokens: 2548, model: 'claude-mid-5-5' } }
    return { turnId: e.turnId, index: e.index, answer: 'ok', toolUses: [] } as never
  })
  await $.session.start({ cwd: '/projet', surface: 'desktop', isInteractive: false })
  await $.turn.start({ text: 'Fais le travail', turnId: 't1' })
  await $.agent.spawn({
    tool_use_id: 'u1', prompt: 'go', description: 'relais', subagentType: 'relais', provider: 'model' as never,
    parentModel: 'claude-small-1-0', background: true, fork: false,
  })
  const stream = $.turn.step({ turnId: 't2', index: 0, model: 'claude-mid-5-5', effort: 'low', messageCount: 1, agentId: 'relais1' })
  for await (const _ of stream) { /* consommer */ }
  await $.session.measure({ context: { window: 200000 }, rateLimits: [{ kind: 'seven_day', percentUsed: 84, resetsAt: '2026-10-05T13:00:00.000Z' }], changed: ['rateLimits'] })

  for (const surface of SURFACES) {
    const ui = await $.ui.mount({
      plugin: 'session-recap', surface, component: 'Pane', requestId: 'session-recap',
      props: { title: 'Récap', isFocused: false, bodyColumns: 100, placement: 'dock', scroll: SCROLL, view: {} },
    })
    // compact par défaut : une ligne par limite et par agent, détails dans la carte au survol
    expect(await ui.find({ type: 'Text', text: /relais · mid-5-5 · low/ })).toBeDefined()
    // le bouton bascule vers le détail : timeline et consommation
    await ui.press({ key: 'toggle-view' })
    expect(await ui.find({ type: 'Text', text: /#1 Fais le travail/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /neuf relais · mid-5-5 · low · actif/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /relais\s+mid-5-5\s+low\s+2\s+138\s+0\s+2\.5k\s+1/ })).toBeDefined()
    await ui.press({ key: 'toggle-view' }) // l'état est partagé entre surfaces : retour au compact
    await ui.unmount()
  }
  for (const surface of ['terminal', 'desktop'] as const) {
    const band = await $.ui.mount({
      plugin: 'session-recap', surface, component: 'AbovePrompt',
      props: { hasSurvey: false, isWorking: false, maxRows: 5, bodyColumns: 120, scroll: SCROLL, view: {} },
    })
    // plan déclaré par l'orchestrateur : barre, phase, pourcentage, bande du sous-agent
    await $.tool.call({
      tool: 'mcp__session-recap__plan', tool_use_id: 'p1',
      title: 'Livraison', workflow: true,
      stages: [{ name: 'Lire', steps: ['canon', 'roadmap'] }, { name: 'Faire', steps: [{ name: 'code', agents: 2 }, 'tests'] }],
    } as never)
    await $.tool.call({ tool: 'mcp__session-recap__step', tool_use_id: 'p2', step: 'canon', status: 'done' } as never)
    const withPlan = await $.ui.mount({
      plugin: 'session-recap', surface, component: 'AbovePrompt',
      props: { hasSurvey: false, isWorking: false, maxRows: 5, bodyColumns: 120, scroll: SCROLL, view: {} },
    })
    expect(await withPlan.find({ type: 'Text', text: /25 % · 1\/4/ })).toBeDefined()
    expect(await withPlan.find({ type: 'Text', text: /mid-5-5 · low/ })).toBeDefined()
    await withPlan.unmount()
    await band.unmount()
  }
})
