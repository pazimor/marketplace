# market-mem

Stack Docker du plugin memory : TEI (embeddings) + FalkorDB (vecteurs + graphe) + serveur MCP.

---

## Topologie

```
HÔTE (Claude Code + hooks)
   │  SSE → 127.0.0.1:<MEM_PORT>
   ▼
┌── réseau Docker interne « mem-net » ───────────────────────────────┐
│  mcp        ← serveur MCP + ingestion   (seul service exposé)      │
│  falkordb   ← vecteurs + graphe + full-text  (non publié)          │
│  tei-code   ← embeddings code (TEI, non publié)                    │
│  tei-memory ← embeddings mémoire (TEI, non publié)                 │
└────────────────────────────────────────────────────────────────────┘
```

- FalkorDB : une instance, un graphe nommé par projet (`g_<group_id>`).
- MCP exposé **uniquement** sur `127.0.0.1` (jamais `0.0.0.0`).

---

## Variables d'environnement

Copie `.env.example` à la racine du repo et ajuste :

| Variable | Défaut | Note |
|---|---|---|
| `MEM_HOST` | `127.0.0.1` | Adresse de bind du serveur MCP |
| `MEM_PORT` | `7333` | Port du serveur MCP |
| `REPOS_ROOT` | `/Users` | Chemin monté en read-only dans le conteneur MCP pour `code_fetch`. macOS : `/Users`. Linux : `/home` ou `/` |
| `CODE_EMBED_MODEL` | `microsoft/graphcodebert-base` | Modèle HuggingFace pour l'index code |
| `MEMORY_EMBED_MODEL` | `nomic-ai/nomic-embed-text-v1.5` | Modèle HuggingFace pour la mémoire épisodique |
| `MAX_DIM` | `2048` | Dimension de l'index vectoriel (fixe à la création du graphe) |

---

## Démarrage manuel

```bash
# Depuis la racine du repo
docker compose -f market-mem/docker-compose.yml up -d

# Arrêt (volumes conservés)
docker compose -f market-mem/docker-compose.yml stop
```

---

## Architecture mémoire — deux couches dans FalkorDB

### Couche code (bulk, zéro LLM)

- [HOOKS]
   - `SessionStart` : parsing AST (tree-sitter) → chunks par fonction → embed via TEI → stocké dans FalkorDB.
   - `PostToolUse(Write/Edit)` : reindex incrémental des symboles dont le hash change.
- Stockage **par référence** : `path + [start_line, end_line]`, jamais de copie du code.
- `content_hash` gate le ré-embed : seuls les symboles modifiés sont recalculés.


### Couche épisodique (haiku, delta only)

- [HOOKS]
   - `Stop` : si la session est marquée "dirty", haiku reçoit le delta et écrit les faits via `memory_add`.
   - `SubagentStop` : **pas de haiku** — uniquement reconcile code-RAG (git diff → upsert).
- Rétention : 30 j d'invalidation + 30 j de grâce (60 j au total). Items `immune` exemptés.

### Retrieval hybride (zéro LLM au query)

Sémantique + lexical (full-text FalkorDB/RediSearch) → score fusionné (RRF). Filtrage temporel sur `valid`.

---

## Tools MCP exposés

| Tool | Couche | Rôle |
|---|---|---|
| `code_search` | Code | Recherche sémantique + lexicale |
| `code_fetch` | Code | Lit la tranche exacte d'un symbole |
| `memory_search` | Épisodique | Recherche hybride dans la mémoire |
| `memory_query` | Épisodique | Lookup ciblé, filtrable par symbole ancré |
| `memory_immunize` | Épisodique | Protège un fait de la purge |
| `memory_release` | Épisodique | Retire l'immunité |
| `memory_extend` | Épisodique | Repousse l'expiration de N jours |

### Tools cachés (haiku / debug uniquement)

| Tool | Couche | Rôle |
|---|---|---|
| `memory_add` | Épisodique | ajout de memoire 
| `memory_delete` | Épisodique | suppression de memoir 
| `code_add` | Code | ajout de node code 
| `code_edit` | Code | edit une node de code
| `code_delete` | Code | delete de node code 

---

## Call graph (Phase 5B)

Arêtes `CALLS` et `IMPORTS` entre `:CodeChunk`, construites depuis l'AST (tree-sitter).

| Tier | Langages | CALLS | IMPORTS |
|---|---|---|---|
| 1 — Full | Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, C# | ✅ | ✅ |
| 2 — Partial | Ruby, PHP, Kotlin, Swift, Scala | best-effort | ✅ |
| 3 — Import only | Bash, Lua, Haskell, Elixir, Dart, R | ❌ | ✅ |

Tools associés : `impact_of(symbol, depth)`, `callers_of(symbol, depth)`, `imports_of(file)`.

---

## Identité projet (`group_id`)

`hash(git remote URL)` en priorité, fallback `hash(repo_path)` si pas de remote.  
Un `group_id` = un graphe nommé dans FalkorDB = isolation totale entre projets.

---

## Modèles d'embedding

Les modèles tournent via **TEI (Text Embeddings Inference)** dans deux conteneurs séparés :
- code : `microsoft/graphcodebert-base` — 768d, RoBERTa entraîné sur code multilangage.
- memory : `nomic-ai/nomic-embed-text-v1.5` — 768d, Matryoshka, contexte long.

Index vectoriel à `MAX_DIM=2048` avec zero-padding. Changer de modèle = recompute (pas de recréation d'index sauf si la nouvelle dim dépasse 2048).
