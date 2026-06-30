# marketplace

Marketplace de skills, agents et mémoire pour Claude Code.

---

## Prérequis

- Python ≥ 3.11
- Docker Desktop (macOS / Windows) ou Docker Engine (Linux) avec `docker compose`
- Claude Code

---

## Installer le CLI `mem`

```bash
pip install -e .
market --help
```

---

## Commandes

```bash
# Installer le plugin (une fois par machine)
market install --target `claude` --scope user

# Vérifier que tout tourne
market doctor

# Voir l'état d'ingestion du repo courant
market status

# Déclencher une ingestion manuelle
market ingest --repo-path /chemin/vers/ton/repo

# Désinstaller (réversible, lit le manifeste)
market uninstall --target `claude` --scope user
```

> Redémarre Claude Code après `install` pour activer les hooks.

---

## Configuration

```bash
cp .env.example .env
```

Installe le plugin **memory** : index de code sémantique (zéro LLM) + mémoire épisodique par session, propulsé par FalkorDB en Docker local.

Voir [`market-mem/README.md`](market-mem/README.md) pour le détail des variables et de l'architecture.
