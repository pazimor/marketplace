"""
Auth skeleton — FastAPI app, port 7333. Base for the M4 markdown MCP server.

Endpoints
─────────
GET  /health           liveness probe (public)
"""
from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import bind_is_loopback, config, ssl_kwargs

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    _assert_auth_configured()
    yield


app = FastAPI(title="market-mem", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Auth — shared bearer token
# ---------------------------------------------------------------------------
#
# Every route except the liveness probe requires `Authorization: Bearer <token>`
# when MEM_TOKEN is set.  The token is never accepted from a query string: URLs
# land in proxy logs and shell history.
#
# When the port is published off-loopback (MEM_HOST != 127.0.0.1), a token is
# mandatory — the server refuses to start without one rather than silently
# exposing its routes to the whole network.

_PUBLIC_PATHS = {"/health"}


def _assert_auth_configured() -> None:
    if config.MEM_TOKEN:
        log.info("auth: bearer token required (bind=%s)", config.MEM_BIND_ADDR)
        return
    if bind_is_loopback():
        log.warning("auth: no MEM_TOKEN set — allowed because the port is loopback-only")
        return
    raise RuntimeError(
        f"refusing to start: the port is published on {config.MEM_BIND_ADDR!r} "
        "but MEM_TOKEN is empty. Set MEM_TOKEN "
        "(e.g. `openssl rand -hex 32`) or set MEM_HOST=127.0.0.1."
    )


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    return value.strip() if scheme.lower() == "bearer" else ""


@app.middleware("http")
async def _require_token(request: Request, call_next):
    if config.MEM_TOKEN and request.url.path not in _PUBLIC_PATHS:
        if not hmac.compare_digest(_bearer(request), config.MEM_TOKEN):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    # TLS (mkcert) when TLS_CERT_FILE + TLS_KEY_FILE point at existing files;
    # plain http otherwise.
    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=config.SERVER_PORT,
        log_level="info",
        **ssl_kwargs(),
    )
