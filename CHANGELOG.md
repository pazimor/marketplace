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
- `orchestrateur` : élément « Fin de tour » dans le brief (l'agent délégué ne s'arrête pas pour demander, les ambiguïtés vont au rapport final).
- `orchestrateur` : `opus` couvre aussi audits et migrations longues, avec consigne d'explorer largement quand les sources ne sont pas nommées.

### Retiré
- Plugin `memory` (hooks, distiller, `.mcp.json`) — ROADMAP:TASK:10.

## plugin `roadmap` 0.2.0 — marketplace 0.3.0 — 2026-09-17

### Ajouté
- Agent `orchestrateur` (Fable cadre et délègue à Opus / Sonnet / Haiku) intégré au plugin `roadmap`.

## plugin `roadmap` 0.1.0 — 2026-09-06

### Ajouté
- Pivot serverless : skills `roadmap-tracker` et `canon-tracker`, roadmap du repo en dogfood.
