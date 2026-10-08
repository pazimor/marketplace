# Delegation benchmarks — the method

How to re-run the benchmarks that chose the model and effort of the `orchestration` agents.
Only the method lives here. The original benchmarks and their measurements of 2026-10-08 are in
the history: `git show 5630742:bench/README.md` (and `git show 5630742:bench/<file>` for each file).

Costs are API-price equivalents, input side only: transcripts undercount output tokens, and how a
subscription's quota is weighted is not public.

## Reading a run

Each subagent's transcript is `~/.claude/projects/<project>/<session>/subagents/agent-*.jsonl`:

- resolved model: `message.model`; resolved effort: `effort` and `perTurnEffort` (since 2.1.293);
- usage: per `requestId`, keep the maximum (a request is logged several times as it streams);
- input cost = (input + cache writes + cache reads) × the model's price for each kind.

Launch the agents being compared in a single message, so they start from the same state. A brief
that starts with `sleep` must run in the background: the session's Bash tool refuses a foreground
`sleep`.

## Executors — same brief, hidden suite

Several `orchestration:executor-*` receive the same brief, each in its own folder, with the model
passed at call time. Their code is then graded by a suite they never see.

Brief, in this order:

1. **Context** — what the benchmark is; start with `sleep 20` to leave time to watch the launch.
2. **Canon referenced** — usually none: the work happens outside the repo.
3. **Scope** — one folder per executor (`<FOLDER>/`), the files to create.
4. **Specification** — numbered rules, with the edge cases spelled out (separators, rounding,
   forms that are valid only alone, what raises).
5. **Success criterion** — the command the executor runs itself (its own tests).
6. **Forbidden** — nothing outside the folder, standard library only, no commit, no agent.
7. **Expected report** — paths, summary, criterion output verbatim, ambiguous points.
8. **End of turn** — nobody answers along the way: decide, and list the ambiguities.

Hidden suite: a standalone script, run with `python3 -I <suite> <folder>`, that imports the
executor's module from its folder and checks a table of valid inputs (expected value and type)
and a list of invalid inputs (expected exception), then prints `passed/total` and each failure.
Write a reference implementation that passes every case before launching anything.

| Agent | Resolved model | Effort | Hidden suite | Duration | Input cost |
|---|---|---|---|---|---|

A task specified too completely tells the models apart on cost only. To compare quality, leave
one rule implicit, or ask for something the criterion cannot see.

## Scribe — a typical pass in a sandbox

The scribe receives one message with a series of points to record, in a sandbox: a copy of
`.claude/canon/`, `CLAUDE.md` and `scripts/validate.py` taken at a fixed commit, kept under git to
read the diff. The message names the sandbox path (`<PROJECT>`) and forbids writing elsewhere.

Points to include:

- a user decision, quoted verbatim (expected: a `[USER]` entry);
- a finding from another agent (expected: a `[MODEL]` entry in the right theme file);
- a decision that replaces an existing entry (expected: the old one struck with
  `— obsolete YYYY-MM-DD: <reason>`, the new one as `[USER]`, details as a separate `[MODEL]`);
- two traps: a proposal to deprecate a `[USER]` entry, and a suggestion that breaks a `[USER]`
  convention (expected: nothing changed, both raised as questions);
- a question whose answer is a canon ID.

Checklist: one line per expected outcome, plus `python3 scripts/validate.py .` at 0 errors in the
sandbox and nothing written outside it (compare file fingerprints of the real canon before/after).

| Run | Critical points | Deviation | Input cost | Requests > 100k tokens |
|---|---|---|---|---|

Count the requests over 100k prompt tokens: past that threshold, the most economical model bills
more per token (`CANON:27`).
