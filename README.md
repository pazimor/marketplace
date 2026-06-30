# marketplace

Marketplace de skills, agents et mémoire pour Claude Code.

Installe le plugin **memory** : index de code sémantique (zéro LLM) + mémoire épisodique par session, propulsé par FalkorDB + TEI en Docker local.

---

## Prérequis

- Python ≥ 3.11
- Docker Desktop (macOS / Windows) ou Docker Engine (Linux) avec `docker compose`
- Claude Code ≥ dernière version stable

---

## Installer le CLI `mem`

```bash
pip install -e .
mem --help
```

---

## Commandes

```bash
# Installer le plugin (une fois par machine)
mem install --target claude --scope user

# Vérifier que tout tourne
mem doctor

# Voir l'état d'ingestion du repo courant
mem status

# Déclencher une ingestion manuelle
mem ingest --repo-path /chemin/vers/ton/repo

# Désinstaller (réversible, lit le manifeste)
mem uninstall --target claude --scope user
```

> Redémarre Claude Code après `install` pour activer les hooks.

---

## Configuration

```bash
cp .env.example .env
```

Voir [`market-mem/README.md`](market-mem/README.md) pour le détail des variables et de l'architecture.
