# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions [semver](https://semver.org/lang/fr/).
Règle (`CANON:9`) : toute modification d'un skill ou d'un agent distribué incrémente la version
du plugin concerné (`plugins/<plugin>/.claude-plugin/plugin.json`) et ajoute une entrée ici ;
la version de `.claude-plugin/marketplace.json` suit à chaque changement du catalogue.

- **patch** — reformulation, correction de prompt sans changement de comportement attendu
- **minor** — nouveau comportement, nouvel agent / skill, nouvelle règle
- **major** — changement de grammaire des fichiers canon / roadmap, ou retrait d'un agent / skill

## [Unreleased]

### plugin `session-recap` 0.7.0 — marketplace 0.10.0 — Ajouté
- Affichage d'un vrai workflow (`workflow: true` seulement) : une section par phase, « n/m agents · phase: » puis les cartes des agents de la phase (le premier titre porte aussi spinner, pourcentage et durée) ; les agents prévus mais pas encore lancés apparaissent en emplacements « agent n — à venir ». Un agent lancé avant le plan est rattaché à la phase en cours. Hors workflow, rien ne change (cartes des agents actifs).

### plugin `roadmap` 0.6.0 — marketplace 0.9.0 — Modifié
- `scribe` n'est plus le point d'entrée (une session Claude Desktop ne peut pas démarrer avec lui, `CANON:27`). L'agent principal, le `scribe` et l'`orchestrateur` sont trois pairs égaux qui se parlent directement (`SendMessage`, messages courts par IDs et chemins). Le scribe tient canon et roadmap, ne relaie ni ne recopie rien (son contexte ne se remplit plus pour rien) ; l'orchestrateur rend compte à son appelant et envoie ses constats au scribe. Plus de réglage `--agent roadmap:scribe`.

### plugin `session-recap` 0.6.0 — marketplace 0.9.0 — Modifié
- Bandeau : le nom de l'agent (`✓ scribe` / `⚠ … pas le scribe`) et la ligne « titre (workflow) — étape » disparaissent ; la ligne d'identité ne garde que modèle · effort.
- Sous-agents en tableau de petites cartes (3 par ligne) : mascotte et tâche, puis modèle · effort · outil — durée.
- Transition de couleur : quand l'état du plan change (en cours, attend l'utilisateur, erreur, terminé), la barre, la vignette et le pourcentage fondent de l'ancienne couleur à la nouvelle en 0,9 s (`prevState` / `stateAt` dans le plan, `stateHex`) ; le tick reste actif pendant le fondu. Sur terminal, les cellules fondent aussi.
- Toutes les tailles : la barre occupe toute la largeur disponible (160 à 1600 px, au lieu de 420 max ; 10 à 80 colonnes sur terminal, au lieu de 24 max) et les cartes d'agents passent de 3 à 2 puis 1 par ligne quand la place manque.
- Mascotte sur deux lignes, une évolution par rang de modèle : crabe nu (haiku), reflet dans les yeux et accessoire doré dans les pinces (sonnet), couronne (opus), grande couronne à gemme + accessoire + étincelles (fable) ; inactive (terminée), elle passe en noir et blanc, accessoires compris ; émojis 🦐 🦀 🦞 🐉 sur terminal.
- Barre de progression : la vignette de phase passe au début de la piste et cache le départ du remplissage, qui en sort vers la droite ; correction d'une erreur de syntaxe laissée dans `progressSvg`.

### plugin `roadmap` 0.5.2 — marketplace 0.8.1 — Modifié
- `orchestrateur` : découpe le travail en étapes et, si le plugin `session-recap` est présent, les déclare et les fait avancer (§ 2 bis : phases et étapes, agents prévus par étape, `workflow: true`, états `input` / `error`, `description` de chaque agent délégué) ; sans lui, rien ne change.

### plugin `session-recap` 0.5.9 — marketplace 0.8.10 — Modifié / Ajouté
- Les limites quittent le panneau et le bandeau (déjà dans l'app) ; les alertes en toast restent.
- Agent de départ : « default » n'est plus affiché tel quel ; quand le réglage ne le nomme pas, il est déduit du lancement de l'orchestrateur (`roadmap:scribe`, marqué « déduit »). Le bandeau le certifie (`✓ scribe`) ou avertit (`⚠ … pas le scribe`).
- Vue détaillée plus compacte : 3 derniers prompts sur une ligne (agents au survol) et tableau de consommation aligné avec total.
- Plan en étapes, sur le modèle de `plan-progress` : outils `mcp__session-recap__plan` (phases et étapes, renvoyable en cours de route sans perdre les étapes terminées) et `step` (étape, état `input` / `error`, note). Le bandeau montre une ligne par plan : spinner, titre, phase, barre animée, pourcentage, étapes faites, durée, étape en cours, bouton ✕ ; le survol liste les étapes avec leur durée. Quatre états colorés (en cours, attend l'utilisateur, erreur, terminé).
- Bandes de sous-agents sous la barre : agent, modèle · effort, outil en cours, horloge ; repliées 5 s après la fin, les échecs restent.
- La barre de progression remplace le compteur d'agents sur la ligne d'identité. Elle est pondérée par les agents prévus (`agents` par étape, `workflow: true` pour un workflow) : chaque agent lancé pendant une étape lui est rattaché et la barre avance à chaque agent terminé, plafonnée à 90 % d'une étape jusqu'à sa vérification. Compteur `n/m agents` à côté.
- Barre dessinée au lieu de caractères : sur desktop, VS Code et mobile, un `Svg` interactif (piste arrondie, dégradé de l'état, éclat animé, capsule à chaque frontière de phase, un point par étape avec infobulle nom + durée, pastille de la phase en cours) ; sur terminal, un `Raster` de cellules colorées avec dégradé et éclat.
- Barre en pilule remplie de petits carrés sur 5 rangées (façon grille de contributions), fixes. Fondu statique du minimum à gauche (début) au plein à droite (contre la pastille, ou au bout de la barre terminée) ; par-dessus, des couleurs plus ou moins claires naissent contre la pastille et reculent vers la gauche (0,9 s) en s'estompant à travers ce fondu tant que le plan tourne. Aucune graduation. Couleur de l'état, immobile hors `running`. Pastille de phase unie (couleur de l'état, 23 px, texte 12 px) collée à l'avant du remplissage ; le remplissage est concentrique à la pastille (il s'arrête 2 px avant son bord droit, même centre d'arrondi) et n'est pas dessiné quand il tient sous elle, donc jamais visible autour. Pastille affichée dès 0 % ; fondu minimal à 30 % pour que les carrés du début restent lisibles ; texte foncé sur les couleurs claires (seuil de luminance 130).
- Terminal : la barre est faite de caractères braille (points d'intensités variables qui reculent d'une demi-cellule par tick, fondu de l'arrière vers l'avant, piste ⣀) ; le tick passe à 250 ms.
- Mascotte de Claude Code en SVG pixel-art (`crabSvg`) devant chaque ligne d'agent : orange animée quand l'agent tourne, grisée une fois fini, rouge en échec ; 🦀 sur terminal.
- Bandes de sous-agents : `⎿ 🦀 modèle · effort — tâche (outil) — durée` ; la tâche est la `description` donnée à l'agent.
- Commandes `/progress` (masque / montre les barres) et `/progress-clear`.
- Non repris de `plan-progress` : sons, barre en pixels, plans parallèles (un seul plan à la fois), sauvegarde entre sessions, relances du modèle.

### plugin `session-recap` 0.2.0 — marketplace 0.8.0 — Modifié
- Panneau compact par défaut : une ligne par limite et par agent ; le détail (prompt, tokens entrée / sortie / cache, prévision de la limite) apparaît dans une carte au survol. Le bouton `détail` / `compact` (touche `d`) bascule vers l'ancien affichage complet (timeline, consommation).
- Bandeau : le survol déplie une carte avec les agents actifs et les limites.

### plugin `session-recap` 0.1.0 — marketplace 0.7.0 — Ajouté
- Nouveau plugin `session-recap` (`CANON:23`) : un Mod en function hooks (Claude Code 2.1.287, API en early access, `CANON:24`), en lecture seule. Il bâtit à partir de `session.start`, `turn.start`, `agent.spawn`, `turn.step` (et son chunk `stop`), `turn.complete` et `session.measure` un récap par agent : agent de démarrage, timeline par prompt (neuf, repris, forké, actif), modèle résolu, effort appliqué, tokens par agent × modèle × effort, limites 5 h / 7 jours avec prévision linéaire.
- Panneau `/session-recap` (`/recap` est une commande intégrée) et bandeau d'une ligne au-dessus du prompt ; options `autoOpen`, `compactBand`.
- Alertes en toast (phase 4) : seuils de limites (80 / 95 %), budget de tokens par agent et par session, modèle inattendu (un agent qui répond sur un autre modèle que celui résolu à son lancement), part de l'agent principal. Toutes réglables par `userConfig`.
- Tests `claude plugin test plugins/session-recap` : modèle rejoué avec les événements relevés par la sonde, rendu du panneau et du bandeau sur les surfaces terminal, desktop, vscode et mobile.
- Déclarations du moteur versionnées dans `.claude/types/` ; plan et constats dans `docs/plan-session-recap.md`.

### plugin `roadmap` 0.5.0 — marketplace 0.6.0 — Ajouté / Modifié
- Nouvel agent `scribe`, point d'entrée (`CANON:22`). Il est le seul à parler à l'utilisateur : il reformule, propose des approches, pose les questions et tient canon et roadmap au fil de l'eau. Il confie ensuite un dossier de cadrage validé à l'orchestrateur, puis fait le rituel de capture. Il doit être l'agent principal de la session (`claude --agent roadmap:scribe`).
- `orchestrateur` : il reçoit le dossier du scribe, découpe, délègue (effort par exécutant), écrit le workflow s'il est demandé et vérifie. Il rend au scribe un rapport avec les sorties des critères, les questions et les constats à capturer. Il n'écrit plus ni canon ni roadmap et ne parle plus à l'utilisateur.
- Chaque agent fixe son modèle dans son frontmatter (`scribe`, `orchestrateur`, `executant-*`), qui est le seul endroit où un modèle est nommé. Plus aucun `inherit`, qui prenait la gamme la plus coûteuse (`ROADMAP:TASK:24`). L'orchestrateur ne passe jamais `model` à l'appel.
- `orchestrateur` : un advisor (`/advisor`) configuré par l'utilisateur corrige d'office les exécutants sur un modèle plus petit.
- `canon-tracker` : le rituel de capture est exécuté par le scribe.
- `scripts/validate.py` : trois nouvelles règles, `frontmatter.model-forbidden` (gamme interdite), `frontmatter.model-missing` (WARN, agent de plugin sans modèle explicite) et `plugin.model-mention` (modèle nommé hors de la ligne `model:` d'un agent). Tests associés.

### plugin `level-design` 0.1.1 — Modifié
- `level-design-build` : plus aucun commit, le working tree revient à l'humain (`CANON:17`) ; « selon cette colonne » corrigé.
- Plus aucune distance absolue dans le plugin (`CANON:21`). Les valeurs s'expriment en modules et cellules du kit, en multiples du gabarit joueur mesuré, en secondes de course ou en proportions (du fog, du premier plan). La marche des plateaux se mesure sous la hauteur de pas du contrôleur. Au passage, la contradiction 1 lampe / 40 m² contre 1 lampe par pas de couloir disparaît.

### plugin `roadmap` 0.4.0 — marketplace 0.5.1 — Modifié
- `orchestrateur` : ne nomme plus aucun modèle (`CANON:20`). Il choisit seulement l'effort (l'exécutant) et ne passe plus `model` à l'appel, ni `opts.model` dans un workflow, sauf si le canon ou l'utilisateur en fixe un. Il tourne lui-même en `model: inherit`. Après un échec de compréhension, il signale le besoin d'un modèle plus capable au lieu de le choisir. Une typo corrigée au passage.
- `executant-*` : la description dit que le modèle est laissé au harness.
- `roadmap-tracker` : l'étape « Contexte mémoire » renvoie à la gate de lecture de `canon-tracker` (`.claude/canon/`) au lieu des anciens fichiers mémoire ; retrait de la mention `_memory_migration/` (installeur retiré, `CANON:10`).
- `canon-tracker` : retrait d'une insistance redondante dans le rituel de capture.
- `roadmap-tracker` : « canon » réservé à `.claude/canon/` dans la prose (« La spec fait foi », « Spec d'abord ») ; le champ `- Canon :` de la grammaire est inchangé.

## plugin `level-design` 0.1.0 — marketplace 0.5.0 — 2026-09-28

### Ajouté
- Plugin `level-design` (`CANON:15`), générique au sens de `CANON:8` (`CANON:16`) :
  - skill `level-design-taste` : lecture du niveau en une ligne, curseurs OUVERTURE / DENSITE / RELIEF / NATURE avec presets, deux grammaires de placement, directives, tics de l'IA bannis, vocabulaire, protocole de nouvelle version, pre-flight mesurable ; références `exterieur.md`, `interieur.md`, `rendu.md`, `audits.md` ;
  - skill `level-design-build` : procédure cadrage → recettes mesurées → spec → questions → passe idempotente → jeu → jugement → livraison ; références `spec.md` (gabarit), `recettes.md`, `pieges.md`, `extensions.md` ;
  - **extensions du projet** : `.claude/level-design/index.md` (grammaire dans `extensions.md`) déclare le contexte, les attentes, les références par type de scène, les specs et recettes existantes, la checklist, les précisions par étape et les pièges du projet ; lu par les deux skills et le reviewer, il prime sur le plugin (le canon `[USER]` prime sur lui). Une nouvelle version reprend sa spec, une recette mesurée se réutilise ;
  - agent `level-design-reviewer` (opus, lecture seule, skill `level-design-taste` préchargé) : rapport classé par gravité à partir de captures et du canon du projet.

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
