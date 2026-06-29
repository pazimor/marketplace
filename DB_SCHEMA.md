# Schéma BDD — FalkorDB (mémoire + code, par projet)

> Cible : **FalkorDB** (Cypher, property graph + vector + full-text via RediSearch). Une base **isolée par projet**, contenant deux couches — **CODE** (ajout massif, embeddings propres) et **ÉPISODIQUE** (haiku, embeddings propres elle aussi) — avec horodatage pour purge et support **multi-modèles d'embedding + swap**.
>
> ⚠️ La syntaxe DDL ci-dessous suit la doc FalkorDB actuelle ; à reconfirmer contre la **version exacte** pinnée dans le `docker-compose`.

---

## 1. Isolation : un graphe FalkorDB par projet = le `group_id`

FalkorDB héberge plusieurs graphes indépendants dans la même instance. On mappe **1 projet = 1 graphe** :

```
nom du graphe  =  g_<hash(repo_path)>      ← c'est le group_id
```

- Ouvrir un autre repo → autre graphe → **base propre**, zéro fuite.
- « Repartir de zéro » sur un projet = `GRAPH.DELETE g_<hash>` (atomique).
- `group_id` est donc **implicite** (le graphe lui-même). On le duplique quand même en **propriété** sur chaque nœud comme garde-fou multi-tenant et pour les exports.

Dans chaque graphe, la séparation **mémoire | code** se fait par **label de nœud** (`:CodeChunk` vs `:MemoryEpisode`), pas par un sous-`group_id`. Ça permet à chacune d'avoir **son propre index vectoriel et son propre modèle**.

```
GRAPHE g_<hash>  (= group_id = 1 projet)
├── (:Project)            ← métadonnée singleton du graphe
├── (:EmbeddingModel)…    ← registre des modèles (purpose: code|memory)
├── (:CodeChunk)…         ← couche CODE   (vector index dédié, modèle code)
└── (:MemoryEpisode)…     ← couche ÉPISODIQUE (vector index dédié, modèle mémoire)
```

---

## 2. Nœuds

### 2.1 `(:Project)` — métadonnée du graphe (singleton)

| Propriété | Type | Rôle |
|---|---|---|
| `group_id` | string | hash(repo_path), = nom du graphe |
| `repo_path` | string | chemin du repo source |
| `schema_version` | int | version du schéma (migrations) |
| `created_at` | int (epoch ms) | création de la base |
| `last_full_scan_at` | int | dernier ajout massif complet |

### 2.2 `(:EmbeddingModel)` — registre des modèles (le cœur du multi-modèles + swap)

| Propriété | Type | Rôle |
|---|---|---|
| `id` | string | `name@version` (ex: `nomic-embed-text@1.5`) |
| `name` | string | modèle Ollama |
| `version` | string | version/tag |
| `purpose` | string | **`code`** ou **`memory`** |
| `dim` | int | dimension réelle des vecteurs (≤ MAX_DIM) |
| `metric` | string | `cosine` / `euclidean` |
| `active` | bool | modèle courant pour ce `purpose` |
| `created_at` | int | — |

> Invariant : **au plus un `active=true` par `purpose`**. La propriété vecteur est **toujours `emb`** (dimension d'index = MAX_DIM, padding zéro) → changer de modèle ne touche pas à l'index, il déclenche un recompute (voir §5).

### 2.3 `(:CodeChunk)` — couche CODE (ajout massif, zéro LLM)

| Propriété | Type | Rôle |
|---|---|---|
| `id` | string | `hash(path + symbol)` — stable |
| `group_id` | string | garde-fou |
| `path` | string | fichier |
| `symbol` | string | `module.classe.fonction` |
| `kind` | string | function / class / method / block |
| `lang` | string | python / ts / … |
| `signature` | string | signature |
| `start_line` | int | **référence** : 1ʳᵉ ligne dans `path` |
| `end_line` | int | **référence** : dernière ligne dans `path` |
| `start_byte` | int\|null | offset précis (optionnel, robuste au reformatage) |
| `end_byte` | int\|null | offset précis (optionnel) |
| `content_hash` | string | hash du slice — **gate de ré-embedding incrémental** |
| `emb` | vector<f32> | embedding (modèle `purpose=code`), **paddé à MAX_DIM** |
| `emb_model` | string | `id` du modèle ayant produit `emb` |
| `emb_dim` | int | dimension réelle (avant padding) |
| `loc` | int | lignes de code |
| `created_at` | int | — |
| `updated_at` | int | dernière modif du contenu |
| `indexed_at` | int | dernier embedding |
| `valid` | bool | soft-delete (fichier/symbole disparu) |

> **Code stocké par référence, pas par copie.** Le nœud ne contient pas le code brut : il pointe `path` + `[start_line, end_line]` (et offsets bytes optionnels). `code_fetch` lit la tranche exacte du fichier à la demande → base légère, jamais désynchronisée du source. `content_hash` (hash du slice) sert uniquement de gate de ré-embedding.

### 2.4 `(:MemoryEpisode)` — couche ÉPISODIQUE (haiku) — **avec ses propres embeddings**

| Propriété | Type | Rôle |
|---|---|---|
| `id` | string | uuid |
| `group_id` | string | garde-fou |
| `content` | string | le fait / la décision / la convention |
| `type` | string | fact / decision / convention / bug / preference |
| `emb` | vector<f32> | **embedding propre** (modèle `purpose=memory`), **paddé à MAX_DIM** → cherché via MCP comme le code |
| `emb_model` | string | `id` du modèle ayant produit `emb` |
| `emb_dim` | int | dimension réelle (avant padding) |
| `anchor` | string\|null | symbole de code lié — **optionnel** (porte ouverte couplage) |
| `source` | string | haiku / manual |
| `session_id` | string | tour/session d'origine |
| `valid_from` | int | début de validité |
| `invalid_at` | int\|null | **horodatage de péremption** (temporel) |
| `immune` | bool | **jamais purgé ni invalidé automatiquement** (réglable via MCP) |
| `created_at` | int | — |
| `last_accessed_at` | int | pour purge par désuétude |
| `access_count` | int | idem |

> Point clé demandé : la couche épisodique porte **`emb`** exactement comme `:CodeChunk`. Le MCP `memory_search` fait donc une recherche vectorielle identique à `code_search`, juste sur un autre label/index/modèle.

---

## 3. Relations (arêtes)

| Arête | Cardinalité | Statut |
|---|---|---|
| `(:MemoryEpisode)-[:ANCHORED_TO]->(:CodeChunk)` | 0..n | **optionnel** ; créée seulement si `anchor` renseigné. Non lue en v1, base de la propagation v2 |
| `(:CodeChunk)-[:CALLS]->(:CodeChunk)` | 0..n | **différé v2** : graphe d'appels best-effort |
| `(:CodeChunk)-[:IMPORTS]->(:CodeChunk)` | 0..n | différé v2 |

> En v1 on n'écrit que `ANCHORED_TO` (et seulement quand l'ancre existe). Le reste est réservé à la Phase 5 (couplage data-driven).

---

## 4. Index

FalkorDB : index **vectoriel** lié à `(Label, propriété)` avec **dimension fixe**. On fixe cette dimension à **`MAX_DIM = 2048`** (large marge : nos modèles sont à 768) pour les deux couches, et tout vecteur est **right-paddé de zéros jusqu'à MAX_DIM**. Le padding zéro **n'altère pas la similarité cosinus** (produit scalaire et normes inchangés) tant qu'on ne compare que des vecteurs du même modèle — ce qui est garanti (un seul modèle actif par couche, requête paddée à l'identique). Conséquence : **changer de modèle ne nécessite jamais de recréer l'index**, juste un recompute (voir §5).

```cypher
-- VECTORIEL : couche code — dimension = MAX_DIM (padding zéro)
CREATE VECTOR INDEX FOR (c:CodeChunk) ON (c.emb)
  OPTIONS {dimension: 2048, similarityFunction: 'cosine'};

-- VECTORIEL : couche mémoire — même MAX_DIM
CREATE VECTOR INDEX FOR (m:MemoryEpisode) ON (m.emb)
  OPTIONS {dimension: 2048, similarityFunction: 'cosine'};

-- FULL-TEXT (lexical, pour identifiants exacts → retrieval hybride)
CALL db.idx.fulltext.createNodeIndex('CodeChunk', 'symbol', 'signature', 'content');
CALL db.idx.fulltext.createNodeIndex('MemoryEpisode', 'content');

-- RANGE (horodatage = purge efficace + filtre temporel)
CREATE INDEX FOR (m:MemoryEpisode) ON (m.invalid_at);
CREATE INDEX FOR (m:MemoryEpisode) ON (m.created_at);
CREATE INDEX FOR (m:MemoryEpisode) ON (m.last_accessed_at);
CREATE INDEX FOR (c:CodeChunk)     ON (c.updated_at);

-- EXACT (déduplication / upsert)
CREATE INDEX FOR (c:CodeChunk)     ON (c.id);
CREATE INDEX FOR (c:CodeChunk)     ON (c.content_hash);
CREATE INDEX FOR (m:MemoryEpisode) ON (m.id);
```

**Recherche (exemple, zéro LLM) :**
```cypher
-- côté mémoire (identique côté code en remplaçant le label/index)
CALL db.idx.vector.queryNodes('MemoryEpisode', 'emb', 10, vecf32($q))
YIELD node, score
WHERE node.valid_from <= timestamp()
  AND (node.invalid_at IS NULL OR node.invalid_at > timestamp())
RETURN node.content, score
ORDER BY score;
```

---

## 5. Multi-modèles & changement d'embedding

### 5.1 Deux modèles simultanés (code ≠ mémoire) — natif
Index par label + dimension fixée à MAX_DIM → il suffit de **deux entrées** dans `:EmbeddingModel` :

```cypher
CREATE (:EmbeddingModel {id:'jina-code-v2@1.0', name:'jina-embeddings-v2-base-code',
        version:'1.0', purpose:'code',   dim:768,  metric:'cosine', active:true});
CREATE (:EmbeddingModel {id:'nomic-text@1.5',   name:'nomic-embed-text',
        version:'1.5', purpose:'memory', dim:768,  metric:'cosine', active:true});
```

L'ingestion lit le modèle `active` du `purpose` voulu, embed, **right-pad à MAX_DIM**, écrit `emb` + `emb_model` + `emb_dim`.

### 5.2 Changer de modèle (recompute, pas de re-création d'index)
Puisque l'index est dimensionné à **MAX_DIM** et que le padding zéro préserve le cosinus, on **ne touche jamais à l'index**. Le swap = un simple recompute :

1. Enregistrer le nouveau modèle (`active=false`) ; sa `dim` doit être **≤ MAX_DIM** (sinon augmenter MAX_DIM = seul cas de re-création d'index).
2. Bascule du flag : `active=false` sur l'ancien, `active=true` sur le nouveau (atomique).
3. **Routine de recompute** (déclenchée au `SessionStart`, voir §5.3) : tous les nœuds dont `emb_model ≠` modèle actif sont ré-embeddés par Ollama, paddés à MAX_DIM, `SET emb`, `emb_model`, `emb_dim`. Zéro LLM, c'est de l'embedding.

> Le recompute est progressif et idempotent : tant qu'un nœud n'est pas migré, son `emb_model` trahit l'ancien modèle ; on peut donc reprendre une migration interrompue sans état externe.

### 5.3 Routine de cohérence au démarrage (`SessionStart`)
Avant d'ouvrir le service, un check déterministe (zéro LLM hors ré-embed) :

1. Lire le modèle `active` par `purpose`.
2. `MATCH (n) WHERE n.emb_model <> $active_id RETURN count(n)` → s'il y en a, lancer le recompute (batch Ollama) sur ces nœuds uniquement.
3. Vérifier que `MAX_DIM` de l'index ≥ `dim` du modèle actif ; sinon alerter (il faut augmenter MAX_DIM et recréer l'index — unique cas lourd).
4. Reprendre/poursuivre l'ajout massif manquant.

→ « changement d'embedding ⇒ recompute » est ainsi **automatique** et **reprenable**.

---

## 6. Horodatage & purge

Tout nœud porte `created_at`. La mémoire ajoute `valid_from`, `invalid_at`, `last_accessed_at`, `access_count`, `immune`.

**Stratégie actée : rétention 30 j + grâce 30 j, avec items `immune` exemptés** (« on se laisse le luxe d'avoir des problèmes » : 30 j pour voir venir un souci avant l'invalidation, 30 j de plus avant la suppression définitive).

```cypher
-- 1) INVALIDER (soft) les faits non-immuns plus vieux que 30 j
WITH timestamp() - 30*24*3600*1000 AS cutoff
MATCH (m:MemoryEpisode)
WHERE m.immune = false AND m.invalid_at IS NULL AND m.created_at < cutoff
SET m.invalid_at = timestamp();

-- 2) PURGER (hard) après 30 j de grâce supplémentaires
WITH timestamp() - 30*24*3600*1000 AS grace
MATCH (m:MemoryEpisode)
WHERE m.immune = false AND m.invalid_at IS NOT NULL AND m.invalid_at < grace
DETACH DELETE m;

-- 3) CODE : retirer les chunks orphelins (fichier/symbole disparu au dernier scan)
MATCH (c:CodeChunk) WHERE c.valid = false AND c.updated_at < $last_full_scan_at
DETACH DELETE c;
```

- **`immune = true`** : ni invalidé ni purgé, jamais. Réglable à la volée via le MCP (`memory_immunize` / `memory_release`, voir §6.1).
- **Invalidation ≠ suppression** : un fait invalidé n'est plus retourné par le retrieval (filtre temporel §4) mais reste auditable pendant les 30 j de grâce → fenêtre pour annuler.
- **Filet total = 60 j** entre création et suppression d'un fait non protégé.
- Exécution : tâche planifiée ou hook `SessionStart`/`SessionEnd`. Le **range index** sur `invalid_at`/`created_at` rend ces requêtes efficaces.

### 6.1 Contrôle d'immunité via MCP

| Tool | Effet |
|---|---|
| `memory_immunize(id)` | `SET m.immune = true` — fige le fait, hors de toute purge |
| `memory_release(id)` | `SET m.immune = false` — le fait redevient soumis à la rétention |
| `memory_extend(id, days)` | repousse l'échéance (`created_at`/`invalid_at`) sans immuniser |

> Ces tools sont des **écritures sûres et explicites** : exposables au master (geste délibéré de protection), contrairement à `memory_add` qui reste réservé à haiku.

---

## 7. Récapitulatif des décisions de schéma

1. **1 projet = 1 graphe FalkorDB** = `group_id` ; `group_id` aussi en propriété (garde-fou). ✅
2. **Deux labels** `:CodeChunk` / `:MemoryEpisode` → index vectoriels séparés → **modèles distincts par couche**. ✅
3. **La couche épisodique a son `emb`** → `memory_search` = même mécanique vectorielle que `code_search`. ✅
4. **Index à MAX_DIM + padding zéro** → 2 modèles natifs, et **changer de modèle = recompute** (jamais de re-création d'index). ✅
5. **Code par référence** `path[start_line, end_line]` (+ bytes optionnels) → `code_fetch` lit la tranche ; base légère, jamais désynchro. ✅
6. **Rétention 30 j + grâce 30 j** ; **`immune`** exempte totalement ; contrôle via MCP (`memory_immunize`/`release`/`extend`). ✅
7. **`ANCHORED_TO` optionnel** ; graphe d'appels (`CALLS`/`IMPORTS`) **différé v2**. ✅

### Décisions complémentaires actées
- `MAX_DIM = 2048` (marge confortable ; modèles à 768). ✅
- Modèle **code** : `jina-embeddings-v2-base-code` (161M, 768d, 30 langages, contexte 8192). ✅
- Modèle **mémoire** : `nomic-embed-text` (~137M, 768d). ✅
- Chunking code : **par fonction**. ✅
- Pré-traitement code avant embed : retirer le **bruit** (headers de licence, code commenté mort, séparateurs décoratifs) mais **conserver les docstrings** (jina-v2-base-code est entraîné sur des paires docstring↔code → la doc est un signal, pas du flou).

---

### Sources
- [FalkorDB — Vector Index](https://docs.falkordb.com/cypher/indexing/vector-index.html)
- [FalkorDB — Indexing (range, full-text)](https://docs.falkordb.com/cypher/indexing.html)
- [FalkorDB — Cypher Language](https://docs.falkordb.com/cypher/)
