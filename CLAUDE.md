# CLAUDE.md

Guide pour Claude Code quand il travaille dans ce repo.

## Ce qu'est ce repo

Une **marketplace de plugins Claude Code** qui distribue trois plugins sans serveur : `orchestration`
(ci-dessous), `level-design` (goût et méthode de level design 3D, `CANON:15`) et
`session-recap` (Mod de récap de session en function hooks, `CANON:23`).
`orchestration` ne produit que des fichiers markdown dans le repo de l'utilisateur :
- `.claude/roadmap.md` : specs, milestones avec DoD, tâches à IDs stables, claims (skill `roadmap-tracker`)
- `.claude/canon/*.md` : attentes, conventions, tests, invariants, chaque entrée avec sa provenance `[USER:<nom>]` / `[MODEL]` (skill `canon-tracker`)
- les agents `scribe`, `orchestrateur` et l'agent principal (« default ») sont trois pairs égaux qui se parlent directement (`CANON:27`) : le scribe tient canon + roadmap ; celui qui a cadré la demande avec l'utilisateur confie un dossier de cadrage à l'agent `orchestrateur`, qui délègue chaque tâche scopée en choisissant **l'effort**, vérifie au retour et rend compte ; le scribe capture l'implicite dans le canon

Ce repo applique lui-même son plugin : **lire `.claude/canon/*.md` et `.claude/roadmap.md` avant d'agir.**

## Arborescence

```
.claude-plugin/marketplace.json     # catalogue (orchestration, level-design, session-recap)
plugins/orchestration/
├── .claude-plugin/plugin.json      # version semver du plugin
├── agents/scribe.md                # scribe : pair, tient canon + roadmap, ne code pas, ne relaie rien
├── agents/orchestrator.md          # orchestrateur : pair, délègue, vérifie, rend compte à l'appelant
├── agents/executant-{low,medium,high,xhigh,max}.md   # exécutants : ne diffèrent que par `effort`
└── skills/{roadmap-tracker,canon-tracker}/SKILL.md   # propriétaires des grammaires
plugins/level-design/
├── .claude-plugin/plugin.json      # version semver du plugin
├── agents/level-design-reviewer.md # juge sur captures (lecture seule)
└── skills/{level-design-taste,level-design-build}/  # SKILL.md + references/
plugins/session-recap/              # Mod (function hooks, API en early access, `CANON:24`)
├── .claude-plugin/plugin.json      # version, options (`userConfig`), contrat `types`
├── hooks/{hooks.json,register.tsx,recap.ts}   # module de hooks + modèle pur
├── types/index.d.ts                # état déclaré au moteur (PluginState)
└── tests/                          # `claude plugin test plugins/session-recap`
.claude/types/                      # déclarations du moteur (2.1.287), régénérées à chaque version
docs/plan-session-recap.md          # plan et constats du Mod (prérequis, phases, hypothèses)
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
claude plugin validate . && claude plugin validate plugins/orchestration
claude plugin validate plugins/session-recap && claude plugin test plugins/session-recap
cd market-mem/mcp && python -m pytest -q            # tests d'auth (pip install -r requirements.txt pytest httpx)
```

Smoke test d'installation, dans un HOME vierge : `claude plugin marketplace add ./` puis
`claude plugin install orchestration@marketplace` puis `claude plugin list --json`. Aucune
authentification n'est requise.

## Règles de travail

- **Versionner à chaque changement (`CANON:9`).** Modifier un skill ou un agent de
  `plugins/orchestration/` = augmenter `version` dans `plugins/orchestration/.claude-plugin/plugin.json`
  (patch : reformulation ; minor : nouveau comportement, agent ou skill ; major : grammaire
  canon/roadmap changée ou agent/skill retiré) **et** ajouter une entrée dans `CHANGELOG.md`.
  Un changement du catalogue augmente aussi `version` dans `.claude-plugin/marketplace.json`.
  Lancer `python3 scripts/validate.py .` avant de commiter.
- **Modèles (`CANON:30`).** Les agents d'`orchestration` n'ont pas de `model` : scribe et
  orchestrateur héritent du modèle de la session, l'orchestrateur passe celui de chaque exécutant à l'appel. Un modèle ne se nomme que sur la ligne `model:` du frontmatter
  d'un agent — jamais dans le texte des agents, skills, manifestes, README ou ce fichier
  (`validate.py` le refuse).
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
