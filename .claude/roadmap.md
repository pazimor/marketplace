# Roadmap

## Specs

- `ROADMAP:SPEC:1` **Pivot serverless — le marketplace ne distribue que des skills** [active]
  - Canon : décision commanditaire 2026-09-01. Le fichier markdown est le format, toujours ;
    un serveur n'est jamais qu'un transport optionnel. Le code-index est abandonné
    (ripgrep + modèles actuels suffisent) ; FalkorDB, embeddings et distiller disparaissent.
    La mémoire native Anthropic (auto-memory fichiers) couvre le besoin mémoire — aucune
    infra mémoire custom. Réf : `memory/decision_pivot_serverless_canon.md`.

- `ROADMAP:SPEC:2` **Couche canon avec provenance** [active]
  - Canon : des fichiers vivants à côté de la roadmap (attentes, conventions, instructions
    de test, invariants/états à ne pas casser). Chaque entrée porte sa source :
    `[USER:<nom>]` daté = dit ou validé par l'humain, intouchable par le modèle (conflit →
    signalé, jamais réécrit) ; `[MODEL]` = déduit en travaillant, déclassé d'office face à
    une entrée `[USER]`, promouvable uniquement sur confirmation explicite. La capture est
    un rituel automatique de l'orchestrateur à la clôture de chaque tâche : « qu'est-ce qui
    a été mis au point d'implicite pendant cette passe ? ». Lecture du canon obligatoire
    avant d'agir sur le code.

- `ROADMAP:SPEC:3` **Orchestration Fable → Opus** [active]
  - Canon : Fable ne code jamais — il reformule, questionne, cadre, découpe et délègue des
    tâches scopées à Opus ; il exécute le rituel de capture (SPEC:2) à chaque clôture.
    Formalisation du workflow actuel de l'utilisateur (aujourd'hui une ligne de CLAUDE.md)
    en skill packagé, versionné et distribué par le marketplace.

- `ROADMAP:SPEC:4` **Tier équipe — serveur de fichiers MCP minimal (COMME GitHub, pas DU GitHub)** [active]
  - Canon : pour les équipes sans git (communication inter-services), un serveur MCP HTTP
    maison, bâti sur des normes ouvertes uniquement : auth bearer token conforme à la spec
    MCP (carcasse FastAPI + MEM_TOKEN/mkcert/--expose existants réutilisés), magasin de
    fichiers markdown par `group_id` avec historique versions+auteur+date, écriture
    conditionnelle par concurrence optimiste (version exigée → push périmé rejeté → rituel
    re-fetch/merge/re-push de l'orchestrateur). Résolution client : fichier du repo local
    s'il existe > fetch serveur, + force-fetch pour se réaligner. Aucune dépendance GitHub
    (décision commanditaire 2026-09-01).

- `ROADMAP:SPEC:5` **Plugin level design 3D — le goût, écrit** [active]
  - Canon : `CANON:15`, `CANON:16`. Un plugin `level-design` distinct de `roadmap` : skill
    `level-design-taste` (lecture du brief, 4 curseurs, tics de l'IA, pre-flight mesurable,
    références extérieur / intérieur / rendu / audits), skill `level-design-build` (procédure
    spec → passe idempotente → audit → captures → revue → livraison), agent
    `level-design-reviewer`. Source : le projet de jeu (reviewer, contrôle qualité LD,
    look bible, specs d'arène), rendu générique.

- `ROADMAP:SPEC:6` **Mod récap de session — voir qui tourne, sur quoi, pour combien** [active]
  - Canon : `CANON:23`, `CANON:24`. Un Mod Claude Code (plugin standard) qui affiche en
    permanence l'agent de démarrage, la timeline des agents par prompt (neufs, repris,
    forkés), le modèle résolu et l'effort de chacun, les tokens par agent × modèle × effort
    et les limites 5 h / 7 jours avec prévision. Lecture seule d'abord, alertes ensuite.
    Plan détaillé : `docs/plan-session-recap.md`.

Règles :
- Le fichier est le format ; un serveur n'est qu'un transport (jamais l'inverse).
- Une entrée canon `[USER]` ne se réécrit pas ; le modèle signale les conflits.
- ~~Rien du legacy (market-mem, plugin memory, installeur Docker) ne se démonte avant que le
  nouveau workflow soit validé en usage réel (TASK:8).~~ — levée 2026-09-24 sur décision
  utilisateur (CANON:7, CANON:10).

## M1 — Fondations fichiers (`ROADMAP:MILESTONE:1`, active)

Poser le tier solo complet : plugin roadmap finalisé, skill canon avec provenance, le tout
installable depuis le marketplace sans aucun serveur. Décision commanditaire 2026-09-01 :
c'est le socle, tout le reste s'appuie dessus.

DoD du milestone : sur un projet vierge, installer les plugins depuis le marketplace,
initialiser roadmap + canon, puis dérouler une tâche fictive de bout en bout (claim →
implémentation → clôture avec capture canon) sans qu'aucun conteneur ne tourne.

- [x] `ROADMAP:TASK:1` Initialiser roadmap.md du projet marketplace avec le plan du pivot + miroir repo _(implements ROADMAP:SPEC:1)_
- [x] `ROADMAP:TASK:2` Finaliser le plugin roadmap : plugin.json complet, entrée dans marketplace.json _(implements ROADMAP:SPEC:1)_
- [x] `ROADMAP:TASK:3` Skill canon-tracker : grammaire des fichiers canon avec provenance [USER]/[MODEL], emplacement repo + miroir _(implements ROADMAP:SPEC:2)_
- [x] `ROADMAP:TASK:4` Doc du tier solo : README refondu (installation, workflow fichiers, plus de Docker) _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:2, ROADMAP:TASK:3)_

## M2 — Orchestration Fable → Opus (`ROADMAP:MILESTONE:2`, planned)

Promouvoir la ligne de CLAUDE.md en skills d'orchestration distribuables, avec le rituel de
capture intégré — la réponse au problème « l'implicite disparaît » constaté sur le projet
de jeu vidéo.

DoD du milestone : depuis une session Fable sur le projet de jeu, une demande floue est
reformulée et cadrée, déléguée à Opus, implémentée ; la clôture écrit dans le canon au
moins une entrée [USER] et une [MODEL] correctement attribuées, et une session neuve
retrouve ces contraintes avant de coder.

- [x] `ROADMAP:TASK:5` Skill orchestrateur : Fable ne code pas — reformulation, questions, cadrage, délégation de tâches scopées _(implements ROADMAP:SPEC:3)_
- [x] `ROADMAP:TASK:6` Rituel de capture à la clôture : distinction [USER]/[MODEL], l'utilisateur prime, promotion sur confirmation _(implements ROADMAP:SPEC:2, ROADMAP:SPEC:3; depends on ROADMAP:TASK:3, ROADMAP:TASK:5)_
- [x] `ROADMAP:TASK:7` Gate de lecture : canon + roadmap chargés obligatoirement avant toute action de code _(implements ROADMAP:SPEC:2; depends on ROADMAP:TASK:3)_
- [ ] `ROADMAP:TASK:8` Valider le workflow complet en usage réel sur le projet de jeu et ajuster les skills _(implements ROADMAP:SPEC:3; depends on ROADMAP:TASK:5, ROADMAP:TASK:6, ROADMAP:TASK:7)_
- [x] `ROADMAP:TASK:35` Mesurer en session neuve le gain de `disallowedTools` (préfixe du premier appel d'un exécutant, avant/après) et vérifier que les agents livrés par un plugin le respectent _(implements ROADMAP:SPEC:3)_ — fait 2026-10-08 : relevé après redémarrage de l'app (exécutant ~45k contre ~60k avant, soit −25 % ; scribe ~49k, orchestrateur ~53k) ; agents livrés par un plugin respectant `disallowedTools` (`CANON:48` à `CANON:50`)
- [ ] `ROADMAP:TASK:36` Refaire le micro-benchmark de cadrage de `ROADMAP:TASK:24` avec la génération 5.5 du modèle le plus économe (le relevé de TASK:24 portait sur l'ancienne) _(implements ROADMAP:SPEC:3; depends on ROADMAP:TASK:24)_
- [ ] `ROADMAP:TASK:37` [RÉFLEXION] Évaluer un exécutant unique avec `effort` passé à l'appel (2.1.293+) à la place des cinq `executant-*` _(implements ROADMAP:SPEC:3)_

## M3 — Démantèlement du legacy (`ROADMAP:MILESTONE:3`, done)

Retirer l'ancienne architecture une fois — et seulement une fois — le nouveau workflow
validé (TASK:8). Décision commanditaire 2026-09-01 : FalkorDB disparaît complètement.

DoD du milestone : le repo ne contient plus ni Docker, ni FalkorDB, ni embeddings, ni
distiller (`git grep -il falkordb` vide) ; l'installation marketplace ne requiert que
Claude Code ; CLAUDE.md décrit la nouvelle architecture et rien d'autre.

- [x] `ROADMAP:TASK:9` Retirer market-mem : serveur, docker-compose, ingestion, graph_builder, tests associés _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:8)_ — fait 2026-09-24 : seule la carcasse d'auth reste (CANON:10), tests `cd market-mem/mcp && python -m pytest -q` verts
- [x] `ROADMAP:TASK:10` Retirer le plugin memory : hooks, prompts distiller, .mcp.json _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:8)_ — fait 2026-09-24 par anticipation sur décision utilisateur (CANON:7)
- [x] `ROADMAP:TASK:11` Simplifier l'installeur CLI (ou le retirer si l'installation plugin native suffit) _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:9, ROADMAP:TASK:10)_ — fait 2026-09-24 : retiré (CANON:10), l'installation passe par `/plugin install`
- [x] `ROADMAP:TASK:12` Réécrire CLAUDE.md pour la nouvelle architecture + retro des mémoires obsolètes _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:9, ROADMAP:TASK:10, ROADMAP:TASK:11)_ — fait 2026-09-24

## M4 — Tier équipe (`ROADMAP:MILESTONE:4`, planned)

Le serveur de fichiers MCP minimal pour les équipes sans git — construit sur le socle
propre, en réutilisant la plomberie d'auth de market-mem conservée à cet effet.

DoD du milestone : deux clients sans git partagent canon + roadmap via le serveur ; une
écriture concurrente basée sur une version périmée est rejetée puis résolue par le rituel
re-fetch/merge/re-push ; l'auth bearer token est conforme à la spec MCP ; le tier solo
fonctionne toujours strictement sans serveur.

- [ ] `ROADMAP:TASK:13` Serveur MCP fichiers minimal : carcasse FastAPI + auth réutilisées, magasin markdown par group_id, historique versions+auteur+date _(implements ROADMAP:SPEC:4; depends on ROADMAP:TASK:12)_
- [ ] `ROADMAP:TASK:14` Écriture conditionnelle (concurrence optimiste) côté serveur + rituel re-fetch/merge/re-push côté skill _(implements ROADMAP:SPEC:4; depends on ROADMAP:TASK:13)_
- [ ] `ROADMAP:TASK:15` Résolution client (repo local > serveur, force-fetch) + provenance multi-auteurs [USER:<nom>] _(implements ROADMAP:SPEC:2, ROADMAP:SPEC:4; depends on ROADMAP:TASK:13, ROADMAP:TASK:14)_

## M5 — Mod récap de session (`ROADMAP:MILESTONE:5`, active)

Rendre visible la consommation par agent après la limite hebdomadaire mangée par
l'héritage de modèle. Chaque phase du plan ne démarre qu'après validation de la précédente
par l'utilisateur ; les changements de config sont montrés avant d'être appliqués.

DoD du milestone : dans Claude Code Desktop, une session scribe → orchestrateur →
exécutants affiche (panneau ou repli compact) l'agent de démarrage, chaque agent par prompt
avec instance, modèle résolu, effort et tokens, et les jauges 5 h / 7 jours ; le Mod
s'installe depuis le marketplace avec la version de Claude Code testée dans sa description.

- [x] `ROADMAP:TASK:26` Prérequis : Claude Code ≥ 2.1.287, flag des function hooks, `/plugin-types` versionné, événements et surfaces UI relevés dans les déclarations _(implements ROADMAP:SPEC:6)_ — fait 2026-10-02 : 2.1.287, flag de déploiement serveur (pas de variable), déclarations dans `.claude/types/` (générées via `--plugin-dir`, `/plugin-types` n'existe pas), événements et `$.ui` relevés ; rendu Desktop reporté à `ROADMAP:TASK:33`
- [ ] `ROADMAP:TASK:27` Phase 0 : audit de config et garde-fous (orchestrateur nommé et non forké, deny sur les spawns coûteux, `maxEffortLevel`, mesure de référence `/usage` + `/cost`) _(implements ROADMAP:SPEC:6)_ — reste la mesure de référence (utilisateur) — `CLAUDE_CODE_EFFORT_LEVEL` retirée des réglages utilisateur le 2026-10-07 (re-vérification par version : `CANON:31`)
- [x] `ROADMAP:TASK:28` Phase 1 : sonde par hooks classiques, tableau des champs exposés par événement, contrôle croisé par les transcripts _(implements ROADMAP:SPEC:6; depends on ROADMAP:TASK:26, ROADMAP:TASK:27)_ — fait 2026-10-02 : tableau et constats dans `docs/plan-session-recap.md` (effort écrasé par `CLAUDE_CODE_EFFORT_LEVEL`, `inherit` = parent immédiat, reprise sans `agent.spawn`)
- [x] `ROADMAP:TASK:29` Phase 2 + 3 : Mod v0 en lecture seule (`/recap`) et rendu dans Desktop, avec replis _(implements ROADMAP:SPEC:6; depends on ROADMAP:TASK:28)_ — fait 2026-10-02 : `plugins/session-recap/` 0.1.0, commande `/session-recap` (`/recap` est intégrée), bandeau compact, 9 tests verts, session réelle sans erreur
- [x] `ROADMAP:TASK:30` Phase 4 : alertes de limites, seuils par agent, modèle inattendu, part du scribe _(implements ROADMAP:SPEC:6; depends on ROADMAP:TASK:29)_ — fait 2026-10-02 : toasts, seuils en `userConfig`
- [x] `ROADMAP:TASK:31` Phase 5 : packaging dans le marketplace, options du plugin, installation _(implements ROADMAP:SPEC:6; depends on ROADMAP:TASK:29)_ — fait 2026-10-02 : entrée catalogue, marketplace 0.7.0, CHANGELOG, README, CLAUDE.md, smoke test d'installation en HOME vierge
- [x] `ROADMAP:TASK:32` Retirer la sonde `~/.claude/skills/session-recap/` (échafaudage créé le 2026-10-02 pour générer `.claude/types/`) dès que le vrai plugin vit dans le repo _(implements ROADMAP:SPEC:6; depends on ROADMAP:TASK:29)_ — fait 2026-10-02 : supprimée (elle occupait `/session-recap` dans les sessions Desktop)
- [ ] `ROADMAP:TASK:33` Vérifier le rendu du panneau `/session-recap` et du bandeau dans Claude Code Desktop une fois l'app en 2.1.287 (elle embarque 2.1.284) ; relever la `surface` _(implements ROADMAP:SPEC:6; depends on ROADMAP:TASK:29)_
- [x] `ROADMAP:TASK:34` Tester en session réelle le correctif 0.7.2 du bandeau sur le bureau (SVG en image sans `isInteractive`, tic à 1 s hors terminal) : plus de flash blanc ni d'animation relancée, carte d'un exécutant visible pendant qu'il tourne _(implements ROADMAP:SPEC:6; depends on ROADMAP:TASK:29)_ — fait 2026-10-08 : testé en session réelle avec `session-recap` 0.8.0 ; plus de flash, cartes visibles pendant que les agents tournent ; validé par eddy
- [x] `ROADMAP:TASK:38` Mascottes déclarées en frontmatter (`mascot:`) ; scribe, chef, artiste, inspecteur, et une mascotte par gamme de modèle ; espacement entre les cartes ; validé visuellement par eddy le 2026-10-08 _(implements ROADMAP:SPEC:6)_ — canon : `CANON:42` à `CANON:47`

## Backlog (no milestone)

- [x] `ROADMAP:TASK:17` CI GitHub Actions : manifestes, frontmatter agents/skills, grammaire canon + roadmap, smoke test d'installation du plugin _(implements ROADMAP:SPEC:1, ROADMAP:SPEC:2; depends on ROADMAP:TASK:18)_ — fait 2026-09-24 : `.github/workflows/ci.yml`
- [x] `ROADMAP:TASK:18` Grammaire canon + roadmap écrite comme spec formelle (docs/) avec validateur exécutable _(implements ROADMAP:SPEC:2)_ — fait 2026-09-24 : `docs/grammar.md`, `scripts/validate.py`
- [x] `ROADMAP:TASK:19` Orchestrateur générique (CANON:8) + choix de l'effort par tâche déléguée (CANON:11), agents Workflow compris _(implements ROADMAP:SPEC:3)_ — fait 2026-09-24 : agents `executant-*`, plugin 0.3.0
- [x] `ROADMAP:TASK:20` CHANGELOG.md + versionnage semver des plugins (CANON:9) _(implements ROADMAP:SPEC:1)_ — fait 2026-09-24
- [x] `ROADMAP:TASK:21` Traçabilité de TASK:8 : l'orchestrateur note ce qui a coincé après chaque session réelle _(implements ROADMAP:SPEC:3)_ — fait 2026-09-24 : seconde question du rituel de capture

- [ ] `ROADMAP:TASK:16` [RÉFLEXION] Recherche full-text dans un gros canon d'entreprise (jamais d'embeddings — décision 2026-09-01) _(implements ROADMAP:SPEC:4)_
- [x] `ROADMAP:TASK:22` Plugin `level-design` 0.1.0 : skills level-design-taste et level-design-build, agent level-design-reviewer _(implements ROADMAP:SPEC:5)_ — fait 2026-09-28
- [ ] `ROADMAP:TASK:23` Valider le plugin `level-design` en usage réel sur le projet de jeu (prochaine map ou salle) et ajuster les skills _(implements ROADMAP:SPEC:5; depends on ROADMAP:TASK:22)_
- [x] `ROADMAP:TASK:24` faire des tests de detection des taches et sous entandues avec diferents models pour pouvoir set l'orchestrateur sur un model en particuler ... si pas specifier ou inerit ... prend fable et Crame tout les tokens opus peut repartir le travaille mais sonnet ou haiku devra demander a un opus de faire le travaille de "get" de contexte a sa place -> a regarder _(implements ROADMAP:SPEC:3)_ — fait 2026-10-01 : micro-benchmark de cadrage (4 demandes pièges ; le petit modèle ≈ 50 %, le modèle intermédiaire ≈ 96 %, le plus capable 100 %), décision `CANON:22` : scribe + orchestrateur + exécutants à modèle fixé dans leur fichier, advisor, plugin 0.5.0
- [ ] `ROADMAP:TASK:25` Valider en usage réel la chaîne scribe → orchestrateur → exécutants : imbrication de sous-agents sur deux niveaux, Workflow lancé depuis un sous-agent, advisor actif sur les exécutants, coût comparé à l'ancien `inherit` _(implements ROADMAP:SPEC:3; depends on ROADMAP:TASK:24)_