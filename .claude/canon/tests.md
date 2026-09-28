# Tests

- `CANON:4` [MODEL 2026-09-01] Les manifestes se valident avec `python3 -c "import json; json.load(open(p))"` sur `.claude-plugin/marketplace.json` et chaque `plugins/*/.claude-plugin/plugin.json` — à faire après toute édition d'un manifeste.
- `CANON:12` [MODEL 2026-09-24] Validation du repo : `python3 scripts/validate.py .` (0 erreur ; `--strict` pour faire aussi échouer les WARN) puis `python3 -m unittest discover -s scripts/tests -q`. Le validateur prend une racine en argument et s'applique à tout projet utilisant le plugin.
- `CANON:13` [MODEL 2026-09-24] Le smoke test d'installation tourne sans authentification dans un HOME vierge : `claude plugin validate .`, `claude plugin marketplace add ./`, `claude plugin install roadmap@marketplace`, puis `claude plugin list --json` doit montrer `roadmap@marketplace` activé à la version de `plugin.json`.
- `CANON:14` [MODEL 2026-09-24] Carcasse d'auth de market-mem : `cd market-mem/mcp && python -m pytest -q` (dépendances : `pip install -r requirements.txt pytest httpx`), sans Docker.
