# marketplace

Marketplace de skills, agents et mémoire pour Claude Code — style ECC.

Distribue le plugin **memory** : index de code (bulk, zéro LLM) + mémoire épisodique (haiku), propulsé par FalkorDB + Ollama en Docker local.

---

## Prérequis

- Python ≥ 3.11
- Docker Desktop (macOS / Windows) ou Docker Engine (Linux) avec `docker compose`
- Claude Code ≥ dernière version stable

---

## Installer le CLI `mem`

Le CLI s'installe depuis la racine du repo avec `pip` en mode éditable — pas besoin de publier sur PyPI.

```bash
# Depuis la racine du repo
pip install -e .
```

Vérifie :

```bash
mem --help
```

```
Usage: mem [OPTIONS] COMMAND [ARGS]...

  mem — memory marketplace installer for Claude Code.

Commands:
  install    Install the memory plugin for Claude Code and/or Codex.
  uninstall  Remove the memory plugin (reads manifest — reversible).
  status     Show ingest status for the current project.
  doctor     Run health checks on the entire stack.
  ingest     Manually trigger a full code ingest.
```

---

## Utilisation

### 1. Installer le plugin memory (une fois par machine)

```bash
# Portée user — hooks et MCP actifs dans tous tes projets Claude Code
mem install --target claude --scope user

# OU portée projet — actif uniquement dans le repo courant
mem install --target claude --scope project
```

L'install fait automatiquement :
- Copie les hooks dans `~/.claude/hooks/mem/` (ou `.claude/hooks/mem/`)
- Ajoute l'entrée MCP dans `~/.claude/.mcp.json`
- Merge les hooks dans `~/.claude/settings.json`
- Lance `docker compose up -d` (FalkorDB + Ollama + serveur MCP)
- Pull les modèles Ollama (`jina/jina-embeddings-v2-base-code` + `nomic-embed-text`)

**Redémarre Claude Code** après l'install pour activer les hooks.

---

### 2. Premier démarrage

Au prochain `SessionStart`, le hook lance automatiquement l'ingestion du repo en arrière-plan.  
Tu peux aussi la déclencher manuellement :

```bash
mem ingest --repo-path /chemin/vers/ton/repo
```

Surveille la progression :

```bash
mem status --repo-path /chemin/vers/ton/repo
```

---

### 3. Vérifier la stack

```bash
mem doctor
```

```
  ✓ Docker daemon
  ✓ docker compose  (Docker Compose version v2.x.x)
  ✓ docker-compose.yml present
  ✓ Stack running  (falkordb, ollama, mcp)
  ✓ MCP server /health  (ok)
```

---

### 4. Désinstaller

```bash
mem uninstall --target claude --scope user
```

Lit le manifeste et retire exactement ce qui a été posé — aucun `rm -rf` aveugle.

---

## Configuration

Copie `.env.example` en `.env` à la racine du repo et ajuste si besoin :

```bash
cp .env.example .env
```

| Variable | Défaut | Note |
|---|---|---|
| `MEM_HOST` | `127.0.0.1` | Adresse de bind du serveur MCP |
| `MEM_PORT` | `7333` | Port du serveur MCP |
| `REPOS_ROOT` | `/Users` | Chemin monté en read-only dans le conteneur MCP pour `code_fetch`. macOS : `/Users`. Linux : `/home` ou `/` |
| `CODE_EMBED_MODEL` | `jina/jina-embeddings-v2-base-code` | Modèle Ollama pour l'index code |
| `MEMORY_EMBED_MODEL` | `nomic-embed-text` | Modèle Ollama pour la mémoire épisodique |
| `MAX_DIM` | `2048` | Dimension de l'index vectoriel (fixe à la création) |

---

## Architecture en bref

```
SessionStart ──► docker compose up ──► ingest repo (AST → Ollama → FalkorDB)  [zéro LLM]
PostToolUse  ──► reindex fichier modifié (hash-gatée)
Stop         ──► gate dirty marker ──► haiku (Phase 2, stub pour l'instant)
SubagentStop ──► git diff → reindex fichiers touchés par le sub-agent
```

Les tools MCP exposés à Claude :

| Tool | Rôle |
|---|---|
| `code_search` | Recherche sémantique + lexicale dans le code |
| `code_fetch` | Lit la tranche exacte d'un symbole (path + lignes) |
| `memory_search` | Recherche dans la mémoire épisodique |
| `memory_query` | Lookup ciblé, filtrable par symbole ancré |
| `memory_immunize` | Protège un fait de la purge automatique |
| `memory_release` | Retire l'immunité |
| `memory_extend` | Repousse l'expiration de N jours |

---

## Roadmap

| Phase | Statut |
|---|---|
| 0 — Docker scaffold | ✅ |
| 1 — Ingestion code + RAG + MCP + installeur | ✅ |
| 2 — Mémoire épisodique (haiku au Stop) | 🔜 |
| 3 — Installer cross-target complet | 🔜 |
| 4 — Adaptateur Codex | 🔜 |
| 5 — Couplage code↔mémoire (data-driven) | 🔜 |
