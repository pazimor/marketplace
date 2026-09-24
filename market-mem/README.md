# market-mem

Carcasse d'auth conservée de l'ancien serveur MCP mémoire (base graphe, embeddings,
ingestion : supprimés, cf. `CANON:10`). Base du serveur MCP de fichiers markdown
de M4 (`ROADMAP:SPEC:4`, `ROADMAP:TASK:13`) — aucune fonctionnalité métier ici.

Ce qui reste (`mcp/server/`) :
- app FastAPI, `GET /health` public ;
- middleware bearer : toute autre route exige `Authorization: Bearer <MEM_TOKEN>`
  (jamais en query string) ;
- garde de démarrage : refus de démarrer sans `MEM_TOKEN` si `MEM_BIND_ADDR`
  (= `MEM_HOST` côté compose) n'est pas loopback ;
- TLS si `TLS_CERT_FILE` + `TLS_KEY_FILE` existent ; `MEM_ALLOWED_HOSTS` pour le
  contrôle DNS-rebinding du futur transport MCP.

Certificat (la génération vivait dans l'installeur `market`, supprimé) :

```bash
mkcert -install
mkcert -cert-file certs/server.crt -key-file certs/server.key localhost 127.0.0.1 ::1 <ip-lan>
```

Tests (sans Docker) :

```bash
cd market-mem/mcp && pip install -r requirements.txt && python -m pytest -q
```
