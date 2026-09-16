# market-mem

Stack Docker du plugin memory : FalkorDB (vecteurs + graphe) + serveur MCP (embedding intégré).

---

## Topologie

```
HÔTE (Claude Code + hooks)
   │  SSE → 127.0.0.1:<MEM_PORT>
   ▼
┌── réseau Docker interne « mem-net » ───────────────────────────────┐
│  mcp        ← serveur MCP + embedding + ingestion (seul service exposé) │
│  falkordb   ← vecteurs + graphe + full-text  (non publié)          │
└────────────────────────────────────────────────────────────────────┘
```

- FalkorDB : une instance, un graphe nommé par projet (`g_<group_id>`). Jamais publié.
- MCP exposé sur `127.0.0.1` par défaut. Voir « Accès depuis un autre poste » pour l'ouvrir.

---

## Authentification

Toute route sauf `/health` exige `Authorization: Bearer <MEM_TOKEN>`.

Le token est généré par `market install` et écrit à deux endroits :
- `market-mem/.env` — côté serveur, lu par docker compose ;
- `~/.config/market/settings.json` (mode 600) — côté client, lu par les hooks.

`market install` le publie aussi dans le bloc `env` de `~/.claude/settings.json`,
avec `NODE_EXTRA_CA_CERTS` : c'est ce qui permet à `.mcp.json` (`${MEM_TOKEN}`)
et aux hooks de fonctionner sans export manuel. Ces entrées sont enregistrées
comme patches réversibles et retirées à la désinstallation.

**Fail-closed** : si `MEM_HOST` n'est pas une adresse loopback et que `MEM_TOKEN`
est vide, le serveur refuse de démarrer.

---

## Accès depuis un autre poste

Sur la machine qui héberge le stack :

```bash
market install --expose
```

Ce que ça fait : bind sur `0.0.0.0` (le loopback reste servi, la machine hôte
est elle-même un client), génération du token, regénération du certificat mkcert
avec l'IP LAN et le hostname en SAN, export de la CA vers `~/.config/market/ca.pem`,
et renseignement de `MEM_ALLOWED_HOSTS`. La commande affiche ensuite la ligne à
lancer sur l'autre poste.

Sur le poste distant, avec le même repo cloné :

```bash
MEM_HOST=<ip-du-serveur> MEM_TOKEN=<token> market install --client-only
```

Copier au préalable `~/.config/market/ca.pem` depuis le serveur au même chemin —
httpx (hooks) et Node (client MCP) ignorent le trousseau système et ont besoin
de la CA sous forme de fichier.

### Le code depuis un poste distant

Les nœuds sont identifiés par leur chemin **relatif au repo**, jamais par un
chemin absolu : deux postes (ou un poste et le miroir serveur) qui indexent le
même repo convergent sur les mêmes nœuds au lieu de les dupliquer.

Le serveur ne pouvant pas lire les fichiers du poste distant, il indexe **son
propre clone** :

- `SessionStart` distant → `POST /ingest {group_id, git_url, ref}` → le serveur
  clone/fetch dans `/data/repos/<gid>` et indexe cet arbre.
- L'index reflète donc le dernier commit **poussé**. Il est stocké dans
  `Project.mirror_commit` et renvoyé par `code_search` et `code_fetch`
  (`indexed_commit`) — pour qu'un agent ne prenne jamais du code poussé pour
  l'état du worktree.
- `PostToolUse` distant envoie le **contenu** du fichier édité
  (`POST /reindex {group_id, rel_path, content}`, plafonné à 1 Mo) : les
  éditions non poussées rejoignent quand même l'index. Le graphe d'appels, lui,
  attend le prochain ingest miroir — sa résolution d'imports a besoin de
  l'arbre réel.
- Un chunk indexé dont le serveur ne peut pas lire la source fait renvoyer à
  `code_fetch` `source: null` + `reason: "source_unavailable"` avec le chemin et
  les lignes, pour que l'agent lise le fichier en local. Jamais d'erreur opaque.

Repo privé : monter une clé SSH en lecture seule dans le conteneur (voir le
volume commenté dans `docker-compose.yml`).

**Migration** : le passage aux chemins relatifs change tous les ids de nœuds. Le
premier ingest après mise à jour balaie l'ancien jeu (`invalidated`,
`deleted_pre_migration`, `files_purged` dans le retour de `/ingest`). Un seul
passage suffit.

---

## Variables d'environnement

Copie `.env.example` à la racine du repo et ajuste :

| Variable | Défaut | Note |
|---|---|---|
| `MEM_HOST` | `127.0.0.1` | Adresse de publication du port MCP. `0.0.0.0` pour ouvrir au réseau |
| `MEM_PORT` | `7333` | Port du serveur MCP |
| `MEM_TOKEN` | _(vide)_ | Secret partagé. Obligatoire dès que `MEM_HOST` n'est pas loopback |
| `MEM_ALLOWED_HOSTS` | _(vide)_ | Hôtes que les clients distants composent, séparés par des virgules, sans port. Le transport MCP rejette tout header `Host` inconnu (protection anti-DNS-rebinding) |
| `MEM_CA_BUNDLE` | `~/.config/market/ca.pem` | CA utilisée par les hooks pour vérifier le certificat d'un serveur distant |
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
   - `SessionStart` : parsing AST (tree-sitter) → chunks par fonction → embed via le serveur MCP → stocké dans FalkorDB.
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

Les modèles tournent **directement dans le conteneur `mcp`** (chargés via SentenceTransformers, cache persistant sur le volume `embed-models`) :
- code : `microsoft/graphcodebert-base` — 768d, RoBERTa entraîné sur code multilangage.
- memory : `nomic-ai/nomic-embed-text-v1.5` — 768d, Matryoshka, contexte long.

Index vectoriel à `MAX_DIM=2048` avec zero-padding. Changer de modèle = recompute (pas de recréation d'index sauf si la nouvelle dim dépasse 2048).
