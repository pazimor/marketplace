# Expectations

- `CANON:9` [USER:pazimor 2026-09-28] The marketplace also distributes a `level-design` plugin: 3D level design skills modeled on taste-skill (reading the brief, dials, banned AI tells, measurable pre-flight), distilled from the game project (review agent, quality control and arena specs), plus the review agent.
- `CANON:13` [USER:pazimor 2026-10-02] The marketplace distributes an `agents-info` Mod: a permanent pane in Claude Code Desktop showing the startup agent, the timeline of agents per prompt (fresh, resumed, forked), the resolved model and effort of each, the tokens per agent × model × effort; it only observes, blocking nothing, before the alerts phase.
- `CANON:45` [USER:pazimor 2026-10-08] Clarifies `CANON:13`: the `/agents-info` pane has four sections, Limits, Agents, Prompts and Usage.
- `CANON:46` [USER:pazimor 2026-10-08] Clarifies `CANON:13`: the step plan (progress bar) is not in the pane; it stays in the band above the prompt only.
- `CANON:47` [USER:pazimor 2026-10-08] Clarifies `CANON:13`: each pane section folds on its title, which replaces the former compact / detail toggle; all sections are open by default.
- `CANON:48` [USER:pazimor 2026-10-08] Clarifies `CANON:13`: in the pane's agent tree, the main agent, the scribe and the orchestrator sit at the same top level whoever launched them; every other agent hangs under whoever launched it; the main agent is never inferred or renamed as the scribe (`CANON:17`).
- `CANON:49` [USER:pazimor 2026-10-08] Clarifies `CANON:13`: the duration shown for a resumed agent counts only its worked time, not the waits between two resumes, in the pane and in the band.
- `CANON:50` [USER:pazimor 2026-10-08] Clarifies `CANON:13`: each agent card carries its own usage bar.
- `CANON:51` [USER:pazimor 2026-10-08] Clarifies `CANON:13`: the last section, Usage, shows the session's global consumption: the totals, then one row per model × effort.
- `CANON:52` [USER:pazimor 2026-10-08] Clarifies `CANON:13`: the limit gauge is drawn in a solid color, with the forecast up to the reset hatched.
- `CANON:53` [USER:pazimor 2026-10-08] Clarifies `CANON:13`: in the terminal, the pane is drawn as text with mascot emoji and block bars, with no SVG.
- `CANON:60` [USER:pazimor 2026-10-15] Clarifies `CANON:13`: the `agents-info` figures are reachable without typing a command, ideally in the desktop app's session sidebar as soon as a Mod can draw there (`CANON:59`).
- `CANON:61` [USER:pazimor 2026-10-15] Planned cross-session stats of `agents-info`: the unit of comparison is a level built with the level designer (one session may build several; its name tells them apart, and the person draws the conclusions, the tool only surfaces the figures). Economy is measured by the share of the limits first (the orchestrator weighs on it), in dollars to speak to everyone, and in tokens.
- `CANON:67` [USER:pazimor 2026-10-19] Planned: the `agents-info` Mod shows the child sessions of a batch. It is a separate phase (`CANON:56`), started once the child sessions have landed.
