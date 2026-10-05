# Mod récap de session — plan de reprise Claude Code

Oct 2, 2026 · @eddy HUMMEL — suivi dans la roadmap : `ROADMAP:SPEC:6`, `ROADMAP:MILESTONE:5`
(tâches `ROADMAP:TASK:26` à `ROADMAP:TASK:31`), canon `CANON:23`, `CANON:24`.

## Contexte et objectif

Objectif : voir, prompt après prompt, quels agents tournent, s'ils sont neufs, repris ou forkés, avec quel modèle et quel effort, et ce qu'ils consomment. Le panneau récap, toujours visible dans Claude Code Desktop, est l'interface de ce besoin.

Architecture actuelle : scribe (agent principal, Sonnet) → orchestrateur (sous-agent) → sous-agents de l'orchestrateur. Le scribe note roadmap et décisions ; l'orchestrateur agit et lui rend compte.

Problème constaté : avec Fable en scribe et en orchestrateur, la limite hebdomadaire a été consommée. Aujourd'hui, impossible de voir quel agent démarre la session, ni quel modèle et quel effort chaque sous-agent utilise réellement.

Le panneau doit afficher :

- l'agent de démarrage, son modèle et son effort ;
- une timeline par prompt : agents créés, repris (SendMessage) ou forkés, et ceux encore actifs ;
- les tokens (entrée, sortie, cache) par agent × modèle × effort ;
- la part consommée des limites 5 h et 7 jours, avec une prévision.

## Prérequis à collecter en début de session

Rien ne se code avant d'avoir ces cinq réponses : l'API des Mods est en early access et change d'une version à l'autre.

- [x] `claude --version` : noter la version exacte. Les Mods sont annoncés dans la 2.1.287 du 1er octobre 2026.
  - **2026-10-02 : installé 2.1.250** (`/opt/homebrew/bin/claude`) ; `npm view @anthropic-ai/claude-code version` → 2.1.287.
    Mis à jour le 2026-10-02 par `brew upgrade claude-code@latest` → **2.1.287**. Reste à vérifier que la session Desktop tourne bien sur cette version.
- [x] Vérifier si les function hooks demandent encore `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` dans cette version.
  - 2026-10-02, relevé dans le binaire 2.1.287 : la vraie barrière est le flag de déploiement serveur `tengu_plugin_hooks_modules` (défaut `true` côté client, **servi `off` pour ce compte**). `claude plugin test` répond : « hooks modules are turned off in this process: the rollout switch served off ». Poser `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` n'y change rien. Il existe un mécanisme d'override local non documenté, volontairement pas utilisé.
  - **Session Desktop** : l'app lance son propre binaire, `~/Library/Application Support/Claude/claude-code/2.1.284/`, et pas celui de Homebrew. Elle tourne donc en **2.1.284** (avec `--effort max --model claude-opus` passés par l'app), d'où la nécessité de mettre aussi l'app Desktop à jour.
  - Le CLI Homebrew n'est pas authentifié en headless (`claude -p` : « OAuth session expired ») : il faut lancer `claude` une fois dans un terminal et s'y connecter (`/login`).
- [x] Lancer `/plugin-types` et versionner les déclarations générées (`.claude/types/`).
  - 2026-10-02, après `/login` : le flag de déploiement est désormais **on** (`claude plugin test` cherche un module au lieu de refuser).
  - **`/plugin-types` n'existe pas en 2.1.287** (`claude -p "/plugin-types"` : commande inconnue). D'après le binaire, les déclarations sont écrites par le moteur lui-même quand il charge un plugin à module de hooks depuis un dossier de l'utilisateur : `tsconfig.json`, `.gitignore` et `types/{claude-code,claude-code-tools,claude-code-mcp}/index.d.ts`. La 2.1.287 embarque aussi deux plugins intégrés de référence, `plugin-authoring` (skill d'écriture de Mods) et `mods-guide`, ainsi que `claude plugin init <nom> --with hooks` pour l'échafaudage.
  - La session Desktop (2.1.284) ne liste pas `plugin-authoring` : ces étapes passent par le CLI 2.1.287.
  - **Fait 2026-10-02.** Échafaudage `claude plugin init session-recap --with hooks` (dans `~/.claude/skills/session-recap/`, **à retirer**, voir `ROADMAP:TASK:32`), puis ajout d'un module vide (`hooks/hooks.json` → `"modules": ["register.ts"]`, `export function register(on) {}`). Le moteur n'écrit les déclarations **que pour un plugin chargé par `--plugin-dir`** : `claude -p --plugin-dir <dossier> …` les a déposées dans `<plugin>/.claude-plugin/types/`. Copiées dans `.claude/types/{claude-code,claude-code-tools,claude-code-mcp}/index.d.ts` (2.1.287, 20 114 lignes).
- [x] Lister dans les déclarations : l'événement de démarrage (`session.start`, qui reçoit une `surface`), le spawn et la fin d'un sous-agent, la réponse modèle avec son usage, l'accès au niveau d'effort.

  | Besoin | Événement (`.claude/types/claude-code/index.d.ts`) | Champs utiles |
  | --- | --- | --- |
  | Démarrage | `session.start` | `cwd`, `surface: 'terminal' \| 'desktop' \| 'mobile' \| 'vscode' \| null`, `isInteractive` (pas de nom d'agent ni de modèle) |
  | Prompt utilisateur | `turn.start` | `text`, `turnId` |
  | Spawn d'un sous-agent | `agent.spawn` | entrée : `subagentType`, `name?`, `model?` (demandé), `parentModel`, `parentAgentId?`, `fork`, `background`, `tool_use_id` ; résultat : `model` (**résolu**), `agentId?` |
  | Modèle + effort par appel | `turn.step` | `turnId`, `index`, `model`, `effort?` (`low…max` ou budget), `agentId?` (absent = agent principal) |
  | Fin de tour + usage | `turn.complete` | `turnId`, `agentId?`, `durationMs`, `usage?: TurnUsage` (`input_tokens`, cache, sortie… + `model`) |
  | Limites et coût | `session.measure` | `rateLimits: { kind, percentUsed, resetsAt? }[]`, `cost?: { usd }`, `context`, `changed` |
  | Fin de session | `session.end` | `reason`, `sessionId`, `resume` |

  Pas d'événement dédié à la fin d'un sous-agent ni à la reprise par SendMessage : la fin se lit sur `turn.complete` avec `agentId`, la reprise sur un `agentId` déjà connu qui revient sans nouvel `agent.spawn` (à confirmer en phase 1).
- [~] Lister les surfaces UI disponibles (`ui.open`, panneaux, boutons) et vérifier lesquelles sont rendues dans Desktop.
  - Déclarées sur `$.ui` : `open`, `close`, `panes`, `mount`, `blit`, `invalidate`, `status`, `toast`, `notice`, `log`, `ask`, `focus`, `scroll`, `copy`, `input`, `select`, `press`, `resolve` ; événements `ui.render`, `ui.press`, `ui.input`, etc. `RenderSurface` inclut `'desktop'`.
  - **Reste à vérifier** (phase 3) : le rendu réel dans Desktop, qui tourne encore en 2.1.284.

## Phase 0 — Audit de config et garde-fous (sans code)

Cette phase arrête l'hémorragie avant même que le panneau existe. Elle se fait en une demi-heure.

Audit en lecture seule du 2026-10-02 :

| Réglage | Où | Valeur constatée |
| --- | --- | --- |
| Modèle de session | `~/.claude/settings.json` `model` | `opus[1m]` |
| Agent de démarrage | `agent` (user / projet) | **absent** → la session démarre sur l'agent par défaut, pas sur `scribe` |
| Effort de session | `effortLevel` | `xhigh` |
| Effort de session (env) | `env.CLAUDE_CODE_EFFORT_LEVEL` | `medium` — contredit `effortLevel` |
| Plafond d'effort | `maxEffortLevel` | absent |
| Règles deny | user + `.claude/settings.local.json` | aucune |
| `model:` des agents du plugin `roadmap` | frontmatter | explicite sur les 7 agents (`CANON:22`) |

- [x] Ajouter un `model:` explicite dans le frontmatter de chaque agent. Un sous-agent en `inherit` prend le modèle de la conversation principale, donc celui du scribe. — déjà fait (`CANON:22`, plugin roadmap 0.5.0).
- [x] Vérifier que l'orchestrateur est appelé comme agent nommé, pas en fork. Le mode fork est actif par défaut et un fork hérite de toute la conversation du scribe.
  - 2026-10-02, sonde : `agent.spawn` porte `fork: false` pour un appel nommé par `subagent_type` ; le Mod affiche « forké » le cas échéant.
  - 2026-10-02, lecture statique : `scribe.md:73` appelle l'orchestrateur par l'Agent tool avec `subagent_type` nommé, donc pas en fork. À confirmer à l'exécution en phase 1.
- [x] Ajouter une règle deny sur les spawns coûteux, par exemple `Agent(model:fable)`. Les règles deny/ask matchent les paramètres d'outil.
  - 2026-10-02 : `permissions.deny: ["Agent(model:fable)"]` dans `~/.claude/settings.json` (sauvegarde `settings.json.bak-2026-10-02`).
- [x] Plafonner l'effort avec le setting `maxEffortLevel`.
  - 2026-10-02 : `maxEffortLevel: xhigh`, relevé ensuite à `max` par l'utilisateur ; `effortLevel: xhigh` retiré, l'effort de session reste `CLAUDE_CODE_EFFORT_LEVEL=medium`.
  - Agent de démarrage : `"agent": "roadmap:scribe"` non posé, le plugin `roadmap@marketplace` est installé (scope projet) mais désactivé.
- [ ] **(à faire par l'utilisateur)** Prendre une mesure de référence sur une session type : `/usage` (répartition par sous-agent) et `/cost` (répartition par modèle).

## Phase 1 — Sonde avec hooks classiques

**Fait 2026-10-02**, avec le module de hooks de la sonde (`~/.claude/skills/session-recap/`) plutôt que des hooks classiques : les déclarations donnaient déjà les événements. Sessions headless `claude -p --plugin-dir <sonde> --agents …` : principal (petit modèle) → `relais` (modèle intermédiaire, `effort: low`) → `feuille` (`inherit`), plus une `feuille` directe ; second prompt par `--resume` + SendMessage. Fichiers dans le scratchpad de la session.

But : savoir quels champs le moteur expose réellement, avant d'écrire le Mod. Livrable : un tableau des champs disponibles par événement.

1. Créer un hook qui écrit son stdin dans un fichier horodaté, par exemple `cat > /tmp/hooks/$(date +%s%N)-$EVENT.json`.
2. Le brancher sur `SessionStart`, `SubagentStart` et `SubagentStop`.
3. Lancer une session test : scribe → orchestrateur → deux sous-agents avec des modèles et efforts différents. Enchaîner deux prompts (recherche avec questions, puis réponses) et comparer les agent\_id d'un prompt à l'autre.
4. Remplir le tableau ci-dessous à partir des fichiers obtenus.

| Événement | Nom d'agent | Agent parent | Modèle | Effort (`effort.level`) | Usage tokens |
| --- | --- | --- | --- | --- | --- |
| SessionStart → `session.start` | — | — | non (`$.session.model()`) | non | non |
| SubagentStart → `agent.spawn` | `subagentType`, `name?` | `parentAgentId?` | demandé `model?`, parent `parentModel`, **résolu** dans le résultat | non | non |
| (appel modèle) → `turn.step` + chunk `stop` | via `agentId` | via `agentId` | `model` | `effort` (`low…max`, absent si le modèle n'en prend pas) | `usage` par appel : entrée, sortie, cache lu, cache écrit, `model` |
| SubagentStop → `turn.complete` | via `agentId` | — | `usage.model` | non | `usage` du tour (somme des appels) |
| (limites) → `session.measure` | — | — | — | — | `rateLimits` (`five_hour`, `seven_day`), `cost.usd` |

Constats :
- **Effort : `CLAUDE_CODE_EFFORT_LEVEL` écrase tout.** Avec la variable (`medium`, posée dans `env` de `~/.claude/settings.json`, donc héritée par tous les processus lancés sous Claude Code), la session en `--effort high` et `executant-low` (`effort: low`) tournent tous deux en `medium`. Sans la variable : session `high`, `executant-low` en `low`. Le choix d'effort de l'orchestrateur est donc annulé tant que la variable est posée.
- Le résultat d'`agent.spawn` donne le modèle **résolu** ; une `feuille` en `inherit` lancée par le `relais` prend le modèle du relais (parent immédiat), pas celui de la session.
- Les tâches de fond reviennent comme des tours `turn.start` dont le texte commence par `<task-notification>` : ce ne sont pas des prompts.
- Reprise par SendMessage : même `agentId`, aucun `agent.spawn`, nouveaux `turn.step`. Biais du test : le `relais` repris a tourné sur le modèle de la session, mais `--agents` n'avait pas été repassé à la reprise ; à revérifier avec un agent de plugin.
- Avec `--setting-sources project,local`, le flag de déploiement des Mods est servi `off` : les Mods dépendent des réglages utilisateur (compte).

Ce qui manque dans les hooks devra venir des déclarations du Mod ou des transcripts JSONL locaux.

Contrôle croisé dans `~/.claude/projects/{projet}/{session}/subagents/agent-{id}.jsonl` : un nouveau fichier par prompt signifie une nouvelle instance ; le même fichier qui grossit signifie une reprise via SendMessage.

## Phase 2 — Mod v0 en lecture seule

Le Mod observe et affiche, il ne bloque ni ne modifie rien. Point de départ : le mod communautaire limit-watch, qui affiche déjà les limites 5 h et 7 jours, une prévision et un panneau `/limits`. Relire son source avant de le forker.

Modèle de données, un enregistrement par agent lancé :

```ts
type AgentRun = {
  id: string                // agentId, stable entre reprises
  parentId: string | null   // null = agent principal (scribe)
  agent: string             // scribe, orchestrateur, ...
  promptIndex: number       // prompt utilisateur qui a déclenché ce run
  instance: 'nouvelle' | 'reprise' | 'fork'
  model: string             // modèle résolu, pas celui du frontmatter
  effort: string            // effort.level au moment du spawn
  status: 'running' | 'waiting-permission' | 'done' | 'failed'
  startedAt: number
  endedAt?: number
  tokens: { input: number; output: number; cacheRead: number; cacheWrite: number }
}
```

Étapes :

1. Au démarrage de session : créer l'enregistrement de l'agent principal.
2. À chaque spawn ou reprise de sous-agent (SendMessage vers un agentId) : créer ou rouvrir l'enregistrement, rattaché à son parent et au prompt en cours.
3. À chaque réponse modèle : ajouter l'usage à l'agent en cours.
4. Agréger par clé `agent × model × effort` pour le récap.
5. Commande `/recap` qui ouvre un panneau, sur le modèle du mod `diff` : badge de l'agent principal, timeline prompt par prompt (agents neufs, repris, forkés), arbre des agents, table de consommation, jauges 5 h / 7 jours.
6. Tests avec `claude plugin test`, en mockant les événements relevés en phase 1.

**Fait 2026-10-02** : `plugins/session-recap/` (`hooks/register.tsx` + `hooks/recap.ts`, contrat `types/index.d.ts`). Écarts au plan :
- la commande est **`/session-recap`** : `/recap` est une commande intégrée de la 2.1.287 (refus constaté en session réelle) ;
- `status` ne connaît pas `waiting-permission` (aucun événement observé pour l'attente de permission) ;
- l'agent de démarrage vient du réglage `agent` (`$.settings.read()`), sinon « défaut » ;
- l'usage se compte par appel modèle (chunk `stop` de `turn.step`), pas par `turn.complete`, pour ne rien compter deux fois.
Tests : 9/9 (`claude plugin test plugins/session-recap`), dont le rendu sur terminal, desktop, vscode et mobile. Session réelle : tous les hooks réglés sans erreur, toast « limite 7 jours à 84 % ».

## Phase 3 — Rendu dans Claude Code Desktop

Le risque principal du projet est ici : rien ne garantit encore que Desktop rend un panneau de Mod comme le terminal.

- [~] Lire la `surface` reçue au démarrage de session et logger sa valeur dans Desktop. — le Mod l'affiche en tête du panneau ; `null` en headless. À lire dans Desktop une fois l'app en 2.1.287.
- [ ] Tester l'ouverture du panneau `/session-recap` dans Desktop (l'app embarque 2.1.284 : à refaire après sa mise à jour). Si possible, le détacher dans sa propre fenêtre pour qu'il reste visible.
- [x] Si le panneau ne s'affiche pas : repli sur un indicateur compact (ligne sous le prompt, comme limit-watch) plus une ligne de transcript à chaque spawn. — bandeau `AbovePrompt` (terminal et desktop) livré d'office, option `compactBand` ; pas de ligne de transcript.
- [ ] (non nécessaire à ce stade) Dernier repli : les hooks classiques de la phase 1 renvoient un `systemMessage` à chaque spawn.

## Phase 4 — Alertes et seuils

Une fois le récap fiable, le Mod prévient avant que la semaine soit mangée, pas après.

- [x] Alerte à 80 % et 95 % des limites 5 h et 7 jours, avec la limite hebdomadaire Fable suivie à part. — toute fenêtre que `session.measure` rapporte est suivie ; aucune fenêtre par modèle n'a été observée (seulement `five_hour`, `seven_day`).
- [x] Seuil de tokens par agent et par session, configurable dans les options du plugin.
- [x] Alerte quand un sous-agent tourne sur un modèle différent de celui attendu, par exemple un `inherit` qui tombe sur le modèle du scribe. — « attendu » = modèle résolu au lancement ; le frontmatter de l'agent n'est pas exposé au Mod.
- [x] Alerte quand le scribe dépasse une part fixée de la consommation totale de la session.

## Phase 5 — Packaging dans la marketplace

Un Mod reste un plugin standard : il s'ajoute à la marketplace comme les autres.

- [x] Choisir : plugin séparé (`session-recap`) ou intégré au plugin orchestrateur. Séparé est plus simple à désactiver si l'API casse.
- [x] Arborescence : `.claude-plugin/plugin.json`, `hooks/hooks.json` qui pointe vers `register.tsx`, `tests/`, `types/`.
- [x] Ajouter l'entrée dans `marketplace.json`, avec la version de Claude Code testée dans la description.
- [x] Exposer les seuils de la phase 4 comme options du plugin (`claude plugin configure`).
- [x] Installer depuis la marketplace : `claude plugin install session-recap@marketplace`. — smoke test dans un HOME vierge : installé et activé en 0.1.0.

## Hypothèses à vérifier

Chacune de ces questions peut changer le plan ; les trancher pendant les phases 0 et 1.

- Un sous-agent de l'orchestrateur en `inherit` hérite-t-il du modèle du scribe ou de celui de l'orchestrateur ?
  - 2026-10-02 : de son parent immédiat (l'orchestrateur), constaté sur `relais` → `feuille`.
- Les sessions lancées par Desktop ont-elles l'outil SendMessage ? Sans lui, aucune reprise : chaque prompt recrée un orchestrateur neuf.
  - 2026-10-02 : oui, une session Desktop 2.1.250 liste `SendMessage` parmi ses outils (différés).
- Quand le scribe reprend-il l'orchestrateur plutôt que d'en lancer un neuf ? Écrire la règle dans son prompt d'agent une fois les données de la timeline disponibles.
  - Ouvert : la timeline du Mod le montrera sur de vraies sessions (`ROADMAP:TASK:25`).
- Le frontmatter d'agent accepte-t-il un champ d'effort, ou l'effort ne se règle-t-il qu'au niveau session ?
  - 2026-10-02 : le frontmatter accepte `effort` (`CANON:11`) ; les `executant-*` l'utilisent déjà. Reste à vérifier que l'effort résolu est bien celui-là (phase 1).
- Le scribe est-il vraiment l'agent de démarrage ?
  - 2026-10-02 : non, aucun réglage `agent` n'est posé ; la session démarre sur l'agent par défaut en `opus[1m]` (voir audit phase 0).
- Desktop rend-il les panneaux de Mod (`ui.open`) ?
  - Ouvert : le test de montage valide l'arbre sur la table d'éléments desktop, pas la peinture ; à vérifier dans l'app en 2.1.287.
- Les function hooks sont-ils encore derrière un flag en 2.1.287 ?
  - 2026-10-02 : oui, mais c'est un flag de déploiement côté serveur (`tengu_plugin_hooks_modules`), pas une variable d'environnement ; il est passé à on pour ce compte après `/login`.
- Le source de limit-watch est-il sain et compatible avec la version installée ?
  - Non utilisé : les limites viennent directement de `session.measure`, aucun code tiers n'a été repris.

Sources :

- [Changelog Claude Code](https://code.claude.com/docs/en/changelog)
- [What's new Claude Code](https://code.claude.com/docs/en/whats-new)
- [README des Mods (anthropics/claude-code)](https://github.com/anthropics/claude-code/blob/main/mods/README.md)
- [claude-code-mods, dont limit-watch](https://github.com/KilimcininKorOglu/claude-code-mods)
- [Sous-agents dans le SDK](https://code.claude.com/docs/en/agent-sdk/subagents)
- [Reprise des sous-agents via SendMessage (guide tiers)](https://claudefa.st/blog/guide/agents/persistent-subagents)

## Prompt de démarrage pour Claude Code

```markdown
On reprend le plan dans docs/plan-session-recap.md : un Mod Claude Code qui affiche un récap de session permanent (agent principal, arbre des sous-agents, modèle résolu, effort, tokens par agent × modèle × effort, limites 5 h / 7 jours).

Contraintes :
- L'API des Mods est en early access. N'invente aucun nom d'événement : base-toi uniquement sur les déclarations générées par /plugin-types.
- Commence par la section « Prérequis », puis la phase 0. Montre-moi les changements de config avant de les appliquer.
- Ne passe à la phase suivante qu'après validation de la précédente.
- Coche les tâches du plan au fur et à mesure et note les réponses aux hypothèses dans le fichier.
```
