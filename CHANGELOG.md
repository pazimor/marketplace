# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions [semver](https://semver.org/lang/fr/).
Règle (`CANON:9`) : toute modification d'un skill ou d'un agent distribué incrémente la version
du plugin concerné (`plugins/<plugin>/.claude-plugin/plugin.json`) et ajoute une entrée ici ;
la version de `.claude-plugin/marketplace.json` suit à chaque changement du catalogue.

- **patch** — reformulation, correction de prompt sans changement de comportement attendu
- **minor** — nouveau comportement, nouvel agent / skill, nouvelle règle
- **major** — changement de grammaire des fichiers canon / roadmap, ou retrait d'un agent / skill

## [Unreleased]

## plugin `roadmap` 0.3.0 — marketplace 0.4.0 — 2026-09-24

### Ajouté
- Agents `executant-low|medium|high|xhigh|max` : même contrat d'exécution de brief, seul l'`effort` diffère.
- `orchestrateur` : chaque délégation fixe `model` **et** effort (via `subagent_type` = exécutant), table par nature du travail, règles de redélégation.
- `orchestrateur` : section « Quand l'utilisateur demande un workflow » (opt-in explicite, `opts.model` + `opts.effort` sur chaque `agent()`, un workflow par étape à valider).
- `orchestrateur` : seconde question du rituel de capture, « qu'est-ce qui a coincé dans l'orchestration ? ».
- `orchestrateur` : élément « Fin de tour » dans le brief (l'agent délégué ne s'arrête pas pour demander, les ambiguïtés vont au rapport final).
- `orchestrateur` : `opus` couvre aussi audits et migrations longues, avec consigne d'explorer largement quand les sources ne sont pas nommées.

### Modifié
- `orchestrateur` rendu générique (`CANON:8`) : plus de mention Unity/prefab ; les spécificités du projet sont lues dans son canon.

### Outillage du repo
- `docs/grammar.md` (grammaire EBNF canon + roadmap), `scripts/validate.py` + tests, CI GitHub Actions (validation + smoke test d'installation).

### Retiré
- Plugin `memory` (hooks, distiller, `.mcp.json`) — ROADMAP:TASK:10.
- Installeur `market` (`installer/`, `claude.py`, `pyproject.toml`, `.env.example`) ; `market-mem` réduit à la carcasse d'auth pour M4 (`CANON:10`).

## plugin `roadmap` 0.2.0 — marketplace 0.3.0 — 2026-09-17

### Ajouté
- Agent `orchestrateur` (Fable cadre et délègue à Opus / Sonnet / Haiku) intégré au plugin `roadmap`.

## plugin `roadmap` 0.1.0 — 2026-09-06

### Ajouté
- Pivot serverless : skills `roadmap-tracker` et `canon-tracker`, roadmap du repo en dogfood.
