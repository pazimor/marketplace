# Invariants

- `CANON:5` [USER:eddy 2026-09-01] Aucune dépendance à GitHub (ni à un autre service tiers) dans les mécanismes du marketplace : on implémente les normes ouvertes (spec MCP, concurrence optimiste), « comme GitHub, jamais du GitHub ».
- ~~`CANON:6` [USER:eddy 2026-09-01] Rien du legacy (market-mem, plugin memory, installeur Docker) ne se démonte avant validation du nouveau workflow en usage réel (ROADMAP:TASK:8).~~
  — obsolète 2026-09-24 : décision utilisateur, le plugin memory n'est plus d'actualité et sort du repo sans attendre TASK:8 ; remplacé par `CANON:7`.
- ~~`CANON:7` [USER:eddy 2026-09-24] Le plugin memory est retiré du repo immédiatement (ROADMAP:TASK:10), sans attendre la validation de TASK:8 ; market-mem et l'installeur restent en place jusqu'à décision explicite (M4 prévoit de réutiliser la carcasse d'auth de market-mem).~~
  — obsolète 2026-09-24 : la décision explicite est venue, remplacé par `CANON:10`.
- `CANON:10` [USER:eddy 2026-09-24] Ménage du legacy sans attendre TASK:8 : l'installeur `market` (installer/, claude.py, pyproject.toml) et `.env.example` sortent du repo ; de market-mem on ne garde que la carcasse d'auth (FastAPI + bearer token + mkcert/--expose) réutilisée par M4, tout le reste (FalkorDB, embeddings, ingestion, graph builder) disparaît.
