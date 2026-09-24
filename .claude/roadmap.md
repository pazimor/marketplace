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

Règles :
- Le fichier est le format ; un serveur n'est qu'un transport (jamais l'inverse).
- Une entrée canon `[USER]` ne se réécrit pas ; le modèle signale les conflits.
- Rien du legacy (market-mem, plugin memory, installeur Docker) ne se démonte avant que le
  nouveau workflow soit validé en usage réel (TASK:8).

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

## M3 — Démantèlement du legacy (`ROADMAP:MILESTONE:3`, planned)

Retirer l'ancienne architecture une fois — et seulement une fois — le nouveau workflow
validé (TASK:8). Décision commanditaire 2026-09-01 : FalkorDB disparaît complètement.

DoD du milestone : le repo ne contient plus ni Docker, ni FalkorDB, ni embeddings, ni
distiller (`git grep -il falkordb` vide) ; l'installation marketplace ne requiert que
Claude Code ; CLAUDE.md décrit la nouvelle architecture et rien d'autre.

- [~] `ROADMAP:TASK:9` Retirer market-mem : serveur, docker-compose, ingestion, graph_builder, tests associés _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:8; claimed by claude)_ — périmètre CANON:10 : la carcasse d'auth reste pour M4
- [x] `ROADMAP:TASK:10` Retirer le plugin memory : hooks, prompts distiller, .mcp.json _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:8)_ — fait 2026-09-24 par anticipation sur décision utilisateur (CANON:7)
- [~] `ROADMAP:TASK:11` Simplifier l'installeur CLI (ou le retirer si l'installation plugin native suffit) _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:9, ROADMAP:TASK:10; claimed by claude)_ — décision 2026-09-24 : retiré (CANON:10)
- [~] `ROADMAP:TASK:12` Réécrire CLAUDE.md pour la nouvelle architecture + retro des mémoires obsolètes _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:9, ROADMAP:TASK:10, ROADMAP:TASK:11; claimed by claude)_

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

## Backlog (no milestone)

- [~] `ROADMAP:TASK:17` CI GitHub Actions : manifestes, frontmatter agents/skills, grammaire canon + roadmap, smoke test d'installation du plugin _(implements ROADMAP:SPEC:1, ROADMAP:SPEC:2; depends on ROADMAP:TASK:18; claimed by claude)_
- [~] `ROADMAP:TASK:18` Grammaire canon + roadmap écrite comme spec formelle (docs/) avec validateur exécutable _(implements ROADMAP:SPEC:2; claimed by claude)_
- [~] `ROADMAP:TASK:19` Orchestrateur générique (CANON:8) + choix de l'effort par tâche déléguée (CANON:11), agents Workflow compris _(implements ROADMAP:SPEC:3; claimed by claude)_
- [~] `ROADMAP:TASK:20` CHANGELOG.md + versionnage semver des plugins (CANON:9) _(implements ROADMAP:SPEC:1; claimed by claude)_
- [~] `ROADMAP:TASK:21` Traçabilité de TASK:8 : l'orchestrateur note ce qui a coincé après chaque session réelle _(implements ROADMAP:SPEC:3; claimed by claude)_

- [ ] `ROADMAP:TASK:16` [RÉFLEXION] Recherche full-text dans un gros canon d'entreprise (jamais d'embeddings — décision 2026-09-01) _(implements ROADMAP:SPEC:4)_
