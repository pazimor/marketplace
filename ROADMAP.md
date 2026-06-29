# Roadmap — Marketplace de Skills / Agents / Mémoire (style « ECC »)

> **v3 — révisée.** Un repository unique, façon marketplace Anthropic, qui distribue tes **skills**, tes **agents** et un **système de mémoire propriétaire** — install/désinstall côté *user* et *project* pour Claude Code **et** Codex, **tout en Docker**, isolé par projet, optimisé en tokens.
>
> **Décision structurante v3 :** la mémoire est **notre propre couche**, pas Graphiti branché en service. L'**ajout massif** en début de session = **embedder tout le codebase, zéro LLM, via Ollama local**. Graphiti reste une *inspiration* (modèle temporel, retrieval hybride sans LLM au query), réimplémentée en minimal — surtout parce que son extraction LLM-par-épisode rend un ajout massif impossible à coût maîtrisé.

---

## 0. Principes directeurs

1. **Token-utile only** : on ne charge en contexte que le nécessaire. Mémoire et RAG sont *pull* (via MCP), jamais *push* massif.
2. **Zéro LLM sur le chemin coûteux** : l'ingestion massive (codebase) est **100% embedding** (Ollama), aucun appel LLM. Le LLM (haiku) n'intervient que sur l'écriture épisodique incrémentale, et sur le delta uniquement.
3. **Isolation par projet** : un repo = un `group_id` = une base propre. Autre projet = base propre, zéro fuite.
4. **Tout containerisé, infra partagée** : **une seule** stack Docker de fond (FalkorDB + Ollama + serveur MCP), isolation **logique** par graphe nommé `group_id` — pas un conteneur par projet. Réseau Docker **interne** : Ollama n'est **jamais publié sur l'hôte** (voir §9).
5. **Convention over configuration** : conventions Anthropic (`.claude-plugin/`, `skills/`, `agents/`, `hooks/`).
6. **Séparation lecture / écriture** : lecture exposée au master ; écriture cachée, déléguée à haiku.
7. **Dérisquer avant d'élaborer** : le matching code↔mémoire instable est rendu *optionnel et non bloquant* en v1.

---

## 1. Architecture cible (vue d'ensemble)

```
┌─────────────────────────────────────────────────────────────┐
│  MARKETPLACE REPO  (le « ECC »-like)                         │
│  .claude-plugin/marketplace.json   ← catalogue              │
│  plugins/{memory, skills-pack, agents-pack}                 │
│  installer/   (CLI cross-target: claude + codex)            │
│  docker/      (compose data + Ollama partagé)               │
└─────────────────────────────────────────────────────────────┘
                          │ install
                          ▼
┌──────────────────────── PROJET A ───────────────────────────┐
│  Conversation AI-nimator                                     │
│                                                              │
│  Hook SessionStart ─► compose up (health/create)             │
│        └─► AJOUT MASSIF : embed TOUT le codebase             │
│            (AST → chunks → Ollama → FalkorDB)  [zéro LLM]     │
│                                                              │
│  Agent ─MCP(lecture)─► memory_search / code_search …         │
│  Hook Stop ─► haiku ─MCP(écriture)─► memory_add (delta only) │
│                                 │                            │
│   ┌─────────────────────────────┼──────────────────────┐    │
│   │ FalkorDB (vector + graph)   │  Ollama (PARTAGÉ)     │    │
│   │ group_id = projet_A         │  embeddings, local    │    │
│   │ • couche CODE (bulk embed)  │  zéro LLM à l'ingest  │    │
│   │ • couche ÉPISODIQUE (haiku) │                       │    │
│   └────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
   PROJET B = autre base / group_id ; MÊME conteneur Ollama
```

> Isolation : **une seule instance FalkorDB** héberge **un graphe par projet** (`group_id` = nom du graphe). **Ollama est stateless et partagé**, jamais rechargé par projet. Les deux + le serveur MCP vivent dans un **réseau Docker interne** ; seul l'endpoint MCP est exposé à Claude Code (sur `127.0.0.1`). Détails topologie : §9.

---

## 2. Point 1 — Système d'install (Claude + Codex, user & project)

### 2.1 Structure du marketplace (conventions Anthropic)

```
mon-marketplace/
├── .claude-plugin/marketplace.json   # catalogue: name, owner, metadata, plugins[]
├── plugins/
│   ├── memory/
│   │   ├── .claude-plugin/plugin.json
│   │   ├── hooks/hooks.json          # SessionStart, PostToolUse, Stop…
│   │   ├── agents/                   # sub-agents (ex: l'inserteur haiku)
│   │   ├── skills/
│   │   └── .mcp.json                 # déclare notre MCP memory/code
│   ├── skills-pack/
│   └── agents-pack/
├── installer/
└── docker/
```

Règle : seul `plugin.json` dans `.claude-plugin/` ; `skills/`, `agents/`, `hooks/`, `commands/` à la racine du plugin. Install user via `/plugin marketplace add <owner>/<repo>` puis `/plugin install memory@mon-marketplace`.

### 2.2 Couche d'abstraction install — une source de vérité, deux adaptateurs

| Concept | Claude Code | Codex |
|---|---|---|
| Instructions agent | `CLAUDE.md` / plugin | `AGENTS.md` |
| Skills | `skills/*/SKILL.md` | mappé en prompt/outil |
| Sub-agents | `agents/*.md` | section dans `AGENTS.md` |
| Hooks | `hooks/hooks.json` (9 events) | wrapper/launcher maison |
| MCP | `.mcp.json` | `~/.codex/config.toml` (`[mcp_servers]`) |
| User-side | `~/.claude/` | `~/.codex/` |
| Project-side | `<repo>/.claude/` | `<repo>/.codex/` ou `AGENTS.md` |

**CLI** (`installer/`) :

```
mon-cli install   --target claude|codex|both  --scope user|project
mon-cli uninstall --target claude|codex|both  --scope user|project
mon-cli status
mon-cli doctor    # vérifie docker, Ollama joignable, MCP up, base présente
```

- Install = copie/symlink + **manifeste** (`.mon-cli/manifest.json` : fichiers posés + hash).
- Désinstall = lit le manifeste, retire *exactement* ce qui a été posé. Réversible, pas de `rm -rf` aveugle.
- `doctor` = la logique du hook `SessionStart`, en standalone.

> Séquencement : **Claude Code d'abord**, adaptateur Codex en Phase 4.

---

## 3. Point 2 — Système de mémoire (couche propriétaire)

> Conçue par nous. Inspirée de Graphiti pour deux idées seulement : **temporalité** (on invalide, on ne supprime pas) et **retrieval hybride sans LLM**. Tout le reste est à nous, en particulier l'**ingestion massive sans LLM**.

### 3.1 Le modèle de stockage : un store, deux couches

Une seule base FalkorDB par projet (`group_id`), contenant deux types d'enregistrements :

**Couche CODE — l'« ajout massif » (bulk, zéro LLM).**
- Au hook `SessionStart` : parsing AST (tree-sitter) → **chunking par fonction** (granularité actée ; une fonction/méthode = un nœud).
- Chaque chunk est **embeddé en masse par Ollama** (local, gratuit en tokens LLM) → vecteur **paddé à MAX_DIM** stocké dans FalkorDB.
- **Code stocké par référence, pas par copie** : on garde `path` + `[start_line, end_line]` (+ offsets bytes optionnels) ; `code_fetch` lit la tranche exacte à la demande → base légère, jamais désynchronisée du source.
- Métadonnées par enregistrement : `path`, `symbol`, `signature`, `lang`, `start_line`, `end_line`, `content_hash`, `emb_model`, `loc`.
- **Aucun appel LLM.** C'est la clé : un repo de 5 000 symboles = 5 000 embeddings locaux, pas 5 000 prompts.
- Mise à jour incrémentale au hook `PostToolUse:Write` : seuls les chunks **dont le hash change** sont ré-embeddés (debounce sur les rafales).

**Couche ÉPISODIQUE — la mémoire vécue (incrémentale, haiku).**
- Faits / décisions / conventions / bugs résolus / préférences, produits *pendant* la session.
- Écrits par **haiku** au hook `Stop` (delta only — voir 4.3). C'est le **seul** endroit où un LLM écrit, et il est petit + nourri au strict minimum.
- Mêmes métadonnées temporelles (`valid_from`, `invalid_at`) + un champ `anchor` **optionnel** (voir 3.3).

> Les deux couches partagent le **même index vectoriel** et le **même retrieval**. La couche CODE répond « où est ce que je cherche dans le code », la couche ÉPISODIQUE répond « qu'a-t-on appris ici ».

### 3.2 Retrieval — hybride, zéro LLM au query

- **Sémantique** : kNN vectoriel (embedding de la requête via Ollama vs vecteurs stockés).
- **Lexical** : full-text / mots-clés (FalkorDB/RediSearch) pour les identifiants exacts.
- **Fusion** : score combiné (ex. RRF). Aucun LLM dans la boucle de recherche → latence basse, coût nul.
- Filtrage temporel : on n'expose que les enregistrements `valid` à la date courante.

### 3.3 Ancrage code↔mémoire : métadonnée **optionnelle** (porte ouverte, pas d'obligation)

- À l'écriture épisodique, haiku **peut** renseigner `anchor` = symbole(s) concerné(s) (`auth.service.login`), **seulement s'il est confiant**. Sinon, champ vide, rien ne casse.
- **En v1, `anchor` n'est lu par aucune propagation** : on l'accumule + on **mesure** son taux/cohérence.
- **En v2 (feature, pas obligation)** : si l'ancrage est jugé fiable, on construit la propagation (descendants/ascendants, `impact_of`) **par-dessus les ancres déjà collectées** — FalkorDB gère déjà le graphe, donc **zéro migration**.

> Conséquence : tout le système v1 marche **sans dépendre de la qualité du matching haiku**. Le matching est un *bonus mesurable*, pas un *point de défaillance*.

### 3.4 Pourquoi pas Graphiti tel quel (rappel de la décision)

Graphiti appelle un LLM **par épisode** à l'insertion (extraction entités/relations). Un ajout massif du codebase y serait lent et coûteux — l'inverse de l'objectif. Notre couche fait l'ingestion massive en **pur embedding Ollama**, et réserve le LLM (haiku) à l'écriture épisodique fine. On garde de Graphiti l'idée temporelle et le retrieval sans-LLM, pas son pipeline d'insertion.

---

## 4. Questions ouvertes — état des décisions

### 4.1 Stack BDD : **FalkorDB**, actée
Un seul conteneur (Redis-module léger) faisant **vector ET graph + full-text** → pas de techno en plus le jour où on active le graphe. Isolation par `group_id`, latence sub-10ms. En v1 on exploite **vector + full-text** ; le graph reste dispo sans migration pour la v2.

### 4.2 Le graphe de couplage : **différé en v2**
Pas de graphe code↔mémoire en v1 (matching trop instable pour le faire porter à haiku, et extraction du graphe d'appels seulement *best-effort* à cause de DI/callbacks/dispatch dynamique). On conserve la **donnée** (ancres optionnelles) pour le construire plus tard, mesures à l'appui. Niveaux : **v1 vector seul** → **v2 arêtes sur ancres fiables** → **v3 graphe riche** (si justifié).

### 4.3 Token strategy : **master = lecture, haiku = écriture**, actée
- Master n'a que les tools de **lecture** ; l'écriture est **cachée**.
- Hook `Stop`/`SubagentStop` → haiku reçoit **seulement le delta** (dernier tour + diff), pas l'historique.
- L'ingestion massive ne consomme **aucun** token LLM (embedding pur).

### 4.4 Embeddings : **Ollama local, conteneur partagé**, actée
- Un seul Ollama (stateless) partagé entre projets ; seule la base est isolée.
- Sert **deux usages** : bulk codebase (massif) + embedding des requêtes au query.
- **Modèles retenus** (locaux, petits, batch rapide) :
  - **code** : `jina-embeddings-v2-base-code` — 161M params, 768d, **30 langages** (Python/JS/Java/PHP/Go/Ruby en tête), contexte 8192, ~307 Mo. Répond à « pas trop gros » + « multi-lang ».
  - **mémoire** : `nomic-embed-text` — ~137M, 768d, contexte long.
  - Les deux à 768d, très en-dessous de MAX_DIM.
- **Pré-traitement code avant embed** : retirer le **bruit** (headers de licence, code commenté mort, séparateurs décoratifs) → moins de flou, comme tu le souhaites. **Mais garder les docstrings** : jina-v2-base-code est entraîné sur des paires *docstring↔code*, donc la doc est un **signal de matching**, pas du bruit. Strip ciblé, pas strip total.
- **Index à `MAX_DIM = 2048` + padding zéro** : index dimensionné une fois à 2048 ; tout vecteur est right-paddé. Le padding zéro **n'altère pas le cosinus** (un seul modèle actif par couche). Donc **changer de modèle = recompute** (ré-embed Ollama, zéro LLM), jamais de re-création d'index — sauf si une future dim dépasse 2048. Une **routine au `SessionStart`** détecte les nœuds au mauvais modèle et les recalcule (reprenable).

---

## 5. Spécification MCP & Hooks

### 5.1 Tools MCP

**Toujours exposés (lecture, master) :**
- `memory_search(query, group_id, k)` — couche épisodique, hybride sémantique+lexical.
- `memory_query(query|symbol, group_id)` — variante ciblée (faits liés à un sujet/symbole).
- `code_search(query, group_id, k)` — couche code, hybride.
- `code_fetch(node_id | path:symbol)` — code exact d'un symbole.
- *(expandable, v2)* `impact_of(symbol)` — ascendants impactés *(actif quand le graphe arrive)*.

**Contrôle d'immunité (écritures sûres, exposables au master) :**
- `memory_immunize(id)` — `immune=true`, le fait n'est jamais purgé ni invalidé.
- `memory_release(id)` — `immune=false`, le fait redevient soumis à la rétention.
- `memory_extend(id, days)` — repousse l'échéance sans immuniser.

**Cachés par défaut (écriture, haiku/debug) :**
- `memory_add(content, group_id, anchor?, valid_from)` — `anchor` **optionnel**.
- `memory_delete(id | policy)` — voir rétention.
- `code_add` / `code_edit` / `code_delete` — réindexation d'un symbole.

**Rétention actée : 30 j + grâce 30 j, items `immune` exemptés.** Au-delà de 30 j, un fait non-immun est **invalidé** (`invalid_at`, sort du retrieval mais reste auditable) ; 30 j de grâce plus tard, il est **supprimé**. Soit 60 j de filet pour réagir, et l'immunité (`memory_immunize`) met un fait hors d'atteinte. « On se laisse le luxe d'avoir des problèmes. »

### 5.2 Hooks

| Event | Action |
|---|---|
| `SessionStart` | `docker compose up` (health, création si absent) + Ollama joignable → **routine de cohérence embedding** (recompute des nœuds au mauvais modèle, reprenable) → **AJOUT MASSIF** : si la couche code est absente/périmée pour ce `group_id`, embed tout le codebase (zéro LLM) |
| `PostToolUse` (Write/Edit) | (a) ré-embed les symboles du fichier **dont le hash a changé** (AST diff → upsert) ; (b) **marque la session « sale »** (étage 1 du gate, voir 5.3) |
| `Stop` (master) | **gate déterministe** (étage 2) : si la session est « sale », summon haiku sur le delta → `memory_add` ; sinon **sort sans rien faire** |
| `SubagentStop` | **PAS de haiku** (l'orchestrateur ne décide rien à partir de la sortie du sub-agent). **Uniquement un reconcile code-RAG** : ré-indexer les fichiers modifiés pendant le run du sub-agent (zéro LLM) — nécessaire car `PostToolUse` ne se déclenche **pas** pour les écritures d'un sub-agent ([issue #34692](https://github.com/anthropics/claude-code/issues/34692)) |
| `SessionEnd` | flush de secours (si « sale » et non vidé) puis `docker compose stop` (garder le volume) |

> **Pourquoi ce découpage :** `Stop` porte la mémoire épisodique (décisions du master). `SubagentStop` ne sert qu'à **rattraper les écritures de code** qu'un sub-agent codeur a faites et que `PostToolUse` a manquées.

### 5.2.1 Reconcile code-RAG sur `SubagentStop` (déterministe, zéro LLM)
1. Déterminer les fichiers touchés pendant le run : `git status --porcelain` / `git diff --name-only` (fallback : scan mtime depuis le début du run du sub-agent).
2. Pour chaque fichier : re-parse AST → upsert des **seuls symboles dont le `content_hash` change** (même logique que `PostToolUse`).
3. Idempotent et hash-gated → relancer ne coûte rien si rien n'a bougé. Couvre aussi le cas où `Stop` du master re-scanne par sécurité.

### 5.3 Gate déterministe à deux étages (ne jamais appeler haiku pour rien)

`Stop` se déclenche **une fois par tour** (pas entre les tools — ça c'est `PostToolUse`), mais **même sur un tour sans activité mémorable**. Pour ne pas brûler un appel haiku à chaque tour de discussion, on intercale un gate **100% déterministe, zéro LLM** :

**Étage 1 — marquage (dans `PostToolUse:Write/Edit`).**
- Dès qu'un fichier est modifié, le hook écrit un marqueur de session : `touch .mon-cli/dirty` (ou append d'une ligne `{tool, path, hash, ts}` dans `.mon-cli/session.log`).
- Coût : nul. C'est juste un drapeau « il s'est passé quelque chose ».

**Étage 2 — décision (dans `Stop` du master uniquement).**
- Un petit script bash/python lit le marqueur **avant** tout appel LLM :
  - pas de marqueur / session « propre » → `exit 0` immédiat, **haiku n'est pas appelé** ;
  - session « sale » → on summon haiku sur le **delta uniquement** (lignes du `session.log` + dernier tour), puis on **efface le marqueur** (`rm .mon-cli/dirty`).
- Optionnel : un seuil (ex. n'appeler haiku qu'au-delà de N modifications, ou debounce de T secondes) pour regrouper plusieurs petits tours en une seule insertion.

**Garde-fous :**
- `Stop` n'est pas garanti (cas de stall mid-turn, [issue #29881](https://github.com/anthropics/claude-code/issues/29881)) → le **flush au `SessionEnd`** rattrape un marqueur resté « sale ».
- Respecter `stop_hook_active` pour éviter toute boucle si le hook relance l'agent.

> Résultat : haiku ne tourne **que** sur les tours ayant réellement produit du code/des décisions. Les tours de pure discussion ne coûtent rien.

---

## 6. Roadmap par phases

### Phase 0 — Socle Docker (½–1 sem.)
- Scaffolder le repo (marketplace.json, layout plugins).
- `docker-compose` partagé : **FalkorDB + Ollama + serveur MCP** sur un **réseau interne**, Ollama **non publié**, MCP exposé sur `127.0.0.1` uniquement (voir §9). Pull des 2 modèles dans le volume Ollama du conteneur.
- Cibler **Claude Code** d'abord.
- *Livrable* : `docker compose up` lève la stack, MCP joignable depuis l'hôte, Ollama + FalkorDB joignables **uniquement** depuis le réseau interne.

### Phase 1 — Ajout massif + RAG Code + MCP lecture (1–2 sem.)
- Pipeline d'ingestion : AST (tree-sitter) → chunks → **embed bulk Ollama** → FalkorDB (zéro LLM).
- Retrieval hybride (vector + full-text).
- MCP : `code_search`, `code_fetch`, `memory_search`.
- Hook `SessionStart` (boot + ajout massif) + `PostToolUse` (ré-embed hash-gated).
- *Livrable* : au démarrage, tout le code est mémorisé et interrogeable sémantiquement. **Utilisable au quotidien dès ici.**

### Phase 2 — Couche épisodique + écriture haiku (1–2 sem.)
- Schéma temporel (`valid_from`/`invalid_at`), `memory_add` avec `anchor` **optionnel**.
- Hook `Stop` → haiku inserteur (delta only).
- Invalidation temporelle + pin.
- Instrumenter le **taux d'ancrage** (pour décider la v2 sur des chiffres).
- *Livrable* : la mémoire vécue se remplit seule, sans coûter au master.

### Phase 3 — Installer cross-target + désinstall (1–2 sem.)
- CLI `install/uninstall/status/doctor`, manifeste, user+project (Claude).
- *Livrable* : install/désinstall propre et réversible.

### Phase 4 — Adaptateur Codex + packaging marketplace (1 sem.)
- Adaptateur `AGENTS.md` / `~/.codex/config.toml` ; publication du marketplace.
- *Livrable* : `both` fonctionnel, repo publiable.

### Phase 5 (optionnelle, data-driven) — Couplage code↔mémoire
- **Pré-requis : taux d'ancrage Phase 2 jugé fiable.**
- Arêtes sur ancres → `memory_query(depth)`, `impact_of`.
- *Livrable* : propagation descendants/ascendants. Sinon on ne la construit pas.

### Phase 5B — Call graph statique (Code↔Code)

> **Prérequis :** Phases 0–3 terminées. Indépendante de Phase 5 (les arêtes Code↔Code ne dépendent pas de la qualité des ancres mémoire).

**Objectif :** enrichir FalkorDB avec des arêtes structurelles entre `:CodeChunk`, pour permettre un traversal d'impact (`impact_of`) et du contexte de navigation ("qui appelle cette fonction ?", "d'où vient ce symbole ?").

#### Arêtes modélisées

| Type | Direction | Exemple |
|---|---|---|
| `CALLS` | `:CodeChunk` → `:CodeChunk` | `auth.login` appelle `db.query` |
| `IMPORTS` | `:CodeChunk` (ou fichier) → `:CodeChunk` | `routes/auth.py` importe `services/user.py` |

Arêtes **non retenues** : `REFERENCES` (trop de bruit), `INHERITS`/`IMPLEMENTS` (v3 si besoin, data-driven).

**Politique de résolution :** certitude uniquement — une arête n'est créée que si la cible est résolue avec certitude depuis l'AST (appel direct sur nom connu, import explicite). Appels dynamiques, DI, callbacks, dispatch via string → ignorés, jamais stockés. Pas de score de confiance : une arête est vraie ou absente.

#### Couverture langages

Extraction basée sur **tree-sitter** (même parser que l'ingestion bulk). Cible : maximum de langages.

| Tier | Langages | Niveau CALLS | Niveau IMPORTS |
|---|---|---|---|
| 1 — Full | Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, C# | ✅ résolution directe | ✅ |
| 2 — Partial | Ruby, PHP, Kotlin, Swift, Scala | ✅ best-effort static | ✅ |
| 3 — Import only | Bash, Lua, Haskell, Elixir, Dart, R | ❌ (dynamisme trop élevé) | ✅ si syntaxe explicite |

Un fichier dans un langage non supporté = ignoré pour la construction du graphe (ses nœuds `:CodeChunk` existent, ils n'ont juste pas d'arêtes).

#### Construction et mise à jour

- **SessionStart** : construction du call graph **en parallèle** de l'embed bulk (même pipeline, même `content_hash`-gating). Les arêtes sont idempotentes : `MERGE` FalkorDB, pas d'INSERT en double.
- **PostToolUse (Write/Edit)** : après ré-embed du fichier modifié, recalcul incrémental des arêtes sortantes *de ce fichier uniquement* (+ suppression des arêtes devenues invalides).
- **Jamais re-construit en entier** sauf `mem reindex --graph` explicite.

#### MCP tools activés

- `impact_of(symbol, group_id, depth=3)` — traversal FalkorDB jusqu'à `depth` niveaux via arêtes `CALLS`+`IMPORTS`, retourne la liste des symboles impactés avec leur distance. `depth` configurable par appel (défaut 3, max 10).
- `callers_of(symbol, group_id, depth=1)` — inverse : qui appelle ce symbole ? (depth=1 par défaut, plus pertinent pour la navigation).
- `imports_of(file, group_id)` — dépendances directes d'un fichier.

#### Risques spécifiques

- **Résolution cross-fichier** : un appel `foo()` dans un fichier Python peut venir de 3 imports différents. On résout via les `IMPORTS` déjà indexés (lookup dans le graphe) ; si ambigu → pas d'arête.
- **Arêtes fantômes** : si un symbole est supprimé, ses arêtes sortantes restent. Solution : au `PostToolUse`, on retire toutes les arêtes dont la source est le chunk retraité avant de ré-insérer.
- **Monorepos** : un `import utils` peut cibler plusieurs packages. On résout en priorité dans le même `group_id` ; si toujours ambigu → pas d'arête.
- **Performance** : sur un repo de 10k fonctions, le graphe peut avoir ~50k–200k arêtes. FalkorDB gère ça nativement, mais le traversal `depth=10` sur un graphe dense peut être lent → cap à `depth=10` côté MCP, et index sur `(source_id, type)`.

*Livrable* : `impact_of` et `callers_of` fonctionnels, couverture Tier 1 complète, Tier 2 best-effort. `mem doctor` indique les langages du repo et leur niveau de support graph.

### Phase 6 — Durcissement
- Isolation stricte `group_id`, tests de fuite inter-projets.
- Métriques tokens, bench latence retrieval, bench modèle d'embedding code, bench temps d'ajout massif.

---

## 7. Risques & vigilance

- **Temps de l'ajout massif** : sur gros repo en CPU, embedder tout peut être long → batch + parallélisme, cache persistant par hash (ne ré-embed que le diff entre sessions), barre de progression dans le hook.
- **Embedding code** : modèle texte générique matche mal le code → benchmark obligatoire, modèle code-aware probable.
- **Ré-indexation à l'écriture** : strictement conditionnée au hash, debounce sur rafales de `Write`.
- **Source de vérité = l'AST** ; le graphe (v2+) en est *dérivé*. Arêtes fantômes possibles si un symbole est supprimé entre deux sessions → le `PostToolUse` doit purger les arêtes du chunk retraité avant ré-insertion.
- **Call graph incomplet par design (Phase 5B)** : les arêtes manquantes (dispatch dynamique, DI) ne sont pas des bugs, c'est la politique. Ne pas tenter de les inférer sans données de profilage.
- **Isolation Docker** : volume/réseau déterministe par `group_id` (`mem_<hash_repo>`) ; Ollama explicitement *hors* de cette isolation.
- **Sur-ingénierie** : Phases 0–2 utilisables seules = la protection. Ne pas démarrer la Phase 5 sans chiffres.

---

## 8. Décisions actées (v3)

1. Mémoire : **couche propriétaire**, Graphiti = inspiration seulement (temporalité + retrieval sans-LLM). ✅
2. Ajout massif au `SessionStart` : **embed tout le codebase, zéro LLM, Ollama local**. ✅
3. Stack : **FalkorDB** (vector + full-text en v1, graph dispo pour v2). ✅
4. Embeddings : **Ollama local, conteneur partagé**, modèle à benchmarker (code-aware). ✅
5. Écriture épisodique : **haiku via hook, delta only** ; master en lecture seule. ✅
5b. Déclenchement haiku : **gate déterministe à 2 étages** (marqueur en `PostToolUse` → décision en `Stop`, zéro LLM si rien à mémoriser) + flush `SessionEnd`. ✅
6. Ancrage code↔mémoire : **métadonnée optionnelle**, propagation **différée** (Phase 5, data-driven). ✅
7. Target initial : **Claude Code**, Codex en Phase 4. ✅
8. Rétention : **30 j + grâce 30 j**, items **`immune`** exemptés, contrôle MCP (`memory_immunize`/`release`/`extend`). ✅
9. Index vectoriel : **MAX_DIM = 2048 + padding zéro** → multi-modèles natif, **changement de modèle = recompute** au `SessionStart`. ✅
10. Code stocké **par référence** `path[start_line, end_line]` ; `code_fetch` lit la tranche. ✅
11. Modèles : **code** `jina-embeddings-v2-base-code` (161M, 768d, 30 langages) ; **mémoire** `nomic-embed-text` (768d). ✅
12. Chunking code : **par fonction**. Pré-traitement : strip du bruit, **conserver les docstrings**. ✅
13. `SubagentStop` : **pas de mémoire/haiku** ; sert **uniquement** au reconcile code-RAG (les écritures sub-agent échappent à `PostToolUse`). ✅

> Détail schéma complet : voir **`DB_SCHEMA.md`**.

### Reste à trancher
- Stocker le `content` du code en cache vs référence pure (déjà tranché côté référence, cache optionnel à évaluer).
- Politique de `git` vs scan mtime pour le reconcile `SubagentStop` selon les repos non-git.

---

## 9. Topologie de déploiement & angles morts (à cadrer dès l'implémentation)

> Section ajoutée après audit. L'agent d'implémentation **doit lire ceci en premier** : ce sont les points non couverts par les sections « heureuses » et qui le feraient deviner de travers.

### 9.1 Topologie Docker & réseau (RÉSOLU)

```
HÔTE (Claude Code + hooks)                    ton Ollama perso (port 11434) ← INTOUCHÉ
   │  stdio/SSE vers 127.0.0.1:<port_mcp>
   ▼
┌── réseau Docker interne « mem_net » (pas d'exposition hôte sauf MCP) ──┐
│  mcp        ← serveur MCP+ingestion ; SEUL service exposé (127.0.0.1)  │
│  falkordb   ← 1 instance, 1 graphe par projet ; NON publié            │
│  ollama     ← partagé, modèles dans son volume ; NON publié           │
└────────────────────────────────────────────────────────────────────────┘
```

- **Ollama Docker non publié** (`expose:` interne, pas `ports:`) → aucune collision avec ton Ollama hôte (11434), et inaccessible hors réseau Docker, comme demandé.
- Conséquence directe : **tout ce qui appelle Ollama doit être dans `mem_net`**. Donc le **serveur MCP tourne en conteneur** (pas en process hôte), joint `ollama` et `falkordb` par leur nom de service.
- **Les hooks (sur l'hôte) ne parlent jamais à Ollama/FalkorDB en direct** : ils appellent le service `mcp` (endpoint `127.0.0.1`) ou déclenchent l'ingestion via `docker compose exec`. 
- MCP exposé **uniquement** sur `127.0.0.1:<port>` (jamais `0.0.0.0`).
- Modèles d'embedding : `ollama pull` **dans le volume du conteneur** (séparés de tes modèles hôte → isolation propre, au prix d'un téléchargement dédié).
- *Alternative écartée* (notée pour mémoire) : réutiliser l'Ollama hôte via `host.docker.internal` — rejetée, tu veux l'isolation réseau Docker.

### 9.2 Serveur MCP — runtime & transport (à fixer en Phase 1)
- **Conteneurisé**, sur `mem_net`. Transport recommandé : **SSE/HTTP** sur `127.0.0.1:<port>` (déclaré dans `.mcp.json`). Stateless : prend `group_id` en paramètre, route vers le bon graphe.
- Langage libre (Node ou Python) ; doit embarquer client FalkorDB + client Ollama + parsing tree-sitter.

### 9.3 Ajout massif : NON bloquant (à implémenter Phase 1)
- Le `SessionStart` lance le bulk embed **en tâche de fond** et marque l'état `warming`. Les `*_search` renvoient un résultat partiel + drapeau « index en cours » jusqu'à `ready`.
- Sinon : première ouverture d'un gros repo = session **gelée** plusieurs minutes. À éviter absolument.
- Cache persistant par `content_hash` entre sessions → seules les sessions suivantes sont quasi-instantanées.

### 9.4 Périmètre d'ingestion (à définir Phase 1)
- Respecter `.gitignore` ; exclure `node_modules/`, `vendor/`, `dist/`, `build/`, `.git/`, binaires, lockfiles, fichiers > N Mo.
- Limiter aux langages dont la **grammaire tree-sitter** est installée ; logger les fichiers ignorés.

### 9.5 Invocation de haiku depuis un hook (à fixer Phase 2)
- Le hook `Stop` est un script ; pour « summon haiku » il appelle l'**API Anthropic** (clé via variable d'env) ou le **CLI headless**. Définir : gestion de la clé, timeout, budget max par appel, comportement si offline (skip + flush différé).

### 9.6 Parité Codex — honnêteté (impacte Phase 4)
- Toute l'**automatisation** repose sur les **hooks Claude Code** (9 events). **Codex n'a pas ce modèle d'événements.**
- En v1, Codex obtient **les tools MCP** (read/write) + une **ingestion manuelle/CLI** (`mon-cli ingest`), mais **pas** l'automatisation par hooks (ajout massif auto, haiku au Stop, reindex au Write).
- Donc « both » = **Claude Code first (full), Codex en MCP-only** au début. À assumer dans la com'.

### 9.7 Identité projet / `group_id` (DÉCISION à confirmer)
- `hash(repo_path)` casse si le repo est déplacé/cloné ailleurs (→ mémoire « perdue », nouveau graphe).
- **Reco** : `hash(git remote URL)` en priorité, **fallback** `hash(repo_path)` si pas de remote. À confirmer.

### 9.8 Concurrence multi-session même repo
- Deux conversations sur le même repo partagent le graphe → **upserts idempotents hash-gated** (déjà le cas) + **lock léger** sur l'ajout massif (éviter deux bulks simultanés). Verrou par clé Redis dans FalkorDB.

### 9.9 Détails à ne pas oublier
- Les tools de **lecture MCP** doivent bumper `last_accessed_at` / `access_count` (sinon purge par désuétude inopérante).
- **Dédup mémoire** : avant `memory_add`, haiku vérifie la proximité sémantique (seuil cosinus) pour ne pas empiler des quasi-doublons.
- **Secrets** (clé API, port MCP) hors du repo : `.env` git-ignoré, jamais dans le manifeste d'install.

---

### Sources
- [Create plugins — Claude Code Docs](https://code.claude.com/docs/en/plugins)
- [anthropics/claude-plugins-official — marketplace.json](https://github.com/anthropics/claude-plugins-official/blob/main/.claude-plugin/marketplace.json)
- [Claude Code Plugins Complete Guide (skills, hooks, agents, MCP)](https://hidekazu-konishi.com/entry/claude_code_plugins_complete_guide.html)
- [Everything Claude Code (ECC) — repo](https://github.com/affaan-m/ECC)
- [Graphiti: Knowledge graph memory — Neo4j](https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/) *(inspiration : modèle temporel, retrieval hybride)*
- [Graphiti + FalkorDB](https://www.falkordb.com/blog/graphiti-falkordb-multi-agent-performance/)
- [Ollama embedding models](https://ollama.com/blog/embedding-models)
- [nomic-embed-text — Ollama](https://ollama.com/library/nomic-embed-text)
