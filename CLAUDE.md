# CLAUDE.md

Guide pour Claude Code quand il travaille dans ce repo.

## Ce qu'est ce repo

Une **marketplace de plugins Claude Code** qui distribue un seul plugin, `roadmap`, sans
serveur. Tout ce qu'il produit est un fichier markdown dans le repo de l'utilisateur :
- `.claude/roadmap.md` : specs, milestones avec DoD, tâches à IDs stables, claims (skill `roadmap-tracker`)
- `.claude/canon/*.md` : attentes, conventions, tests, invariants, chaque entrée avec sa provenance `[USER:<nom>]` / `[MODEL]` (skill `canon-tracker`)
- l'agent `orchestrateur` (Fable) cadre la demande, délègue chaque tâche scopée en choisissant **modèle × effort**, vérifie au retour et capture l'implicite dans le canon

Ce repo applique lui-même son plugin : **lire `.claude/canon/*.md` et `.claude/roadmap.md` avant d'agir.**

## Arborescence

```
.claude-plugin/marketplace.json     # catalogue (un plugin : roadmap)
plugins/roadmap/
├── .claude-plugin/plugin.json      # version semver du plugin
├── agents/orchestrator.md          # orchestrateur (model: fable, hérite de l'effort de session)
├── agents/executant-{low,medium,high,xhigh,max}.md   # exécutants : ne diffèrent que par `effort`
└── skills/{roadmap-tracker,canon-tracker}/SKILL.md   # propriétaires des grammaires
docs/grammar.md                     # grammaire canon + roadmap en EBNF (décrit les SKILL.md, n'en décide pas)
scripts/validate.py                 # validateur stdlib : manifestes, frontmatter, canon, roadmap
scripts/tests/                      # tests du validateur (unittest)
.github/workflows/ci.yml            # CI : validate + smoke test d'installation du plugin
market-mem/                         # carcasse d'auth FastAPI conservée pour M4, sans fonctionnalité
CHANGELOG.md
```

## Commandes

```sh
python3 scripts/validate.py .                       # 0 erreur attendu ; --strict fait aussi échouer les WARN
python3 -m unittest discover -s scripts/tests -q    # tests du validateur
claude plugin validate . && claude plugin validate plugins/roadmap
cd market-mem/mcp && python -m pytest -q            # tests d'auth (pip install -r requirements.txt pytest httpx)
```

Smoke test d'installation, dans un HOME vierge : `claude plugin marketplace add ./` puis
`claude plugin install roadmap@marketplace` puis `claude plugin list --json`. Aucune
authentification n'est requise.

## Règles de travail

- **Versionner à chaque changement (`CANON:9`).** Modifier un skill ou un agent de
  `plugins/roadmap/` = augmenter `version` dans `plugins/roadmap/.claude-plugin/plugin.json`
  (patch : reformulation ; minor : nouveau comportement, agent ou skill ; major : grammaire
  canon/roadmap changée ou agent/skill retiré) **et** ajouter une entrée dans `CHANGELOG.md`.
  Un changement du catalogue augmente aussi `version` dans `.claude-plugin/marketplace.json`.
  Lancer `python3 scripts/validate.py .` avant de commiter.
- **Rester générique (`CANON:8`).** Aucun projet ni outil particulier (Unity, prefab…) dans
  les agents et skills distribués : ces détails vivent dans le canon du projet utilisateur.
- **Les grammaires appartiennent aux SKILL.md (`CANON:3`).** Si une règle de grammaire change,
  modifier le SKILL.md, puis `docs/grammar.md` et `scripts/validate.py` avec leurs tests.
- **Canon : on ne supprime rien.** Une entrée périmée est barrée `~~…~~` et suivie de
  `— obsolète AAAA-MM-JJ : <raison>`. Une entrée `[USER]` ne se déprécie que sur décision de
  l'utilisateur.
- **Agents de plugin** : `hooks`, `mcpServers` et `permissionMode` sont ignorés dans leur
  frontmatter. L'effort se fixe par `effort` dans le frontmatter (l'Agent tool ne le prend pas
  à l'appel), ou par `opts.effort` dans un workflow (`CANON:11`).
- Skills et agents en français, ton directif ; README en anglais (`CANON:1`).
- Aucune dépendance à GitHub ou à un service tiers dans les mécanismes du plugin (`CANON:5`) ;
  la CI GitHub Actions n'est que de l'outillage du repo.

## Décisions prises (ne pas rouvrir)

- Le fichier est le format ; un serveur n'est jamais qu'un transport optionnel (M4, tier équipe).
- Plus de code index, d'embeddings, de FalkorDB, de distiller ni d'installeur : l'installation
  passe par `/plugin install` natif, et la mémoire par la mémoire native de Claude Code.
