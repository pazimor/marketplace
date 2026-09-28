"""Unit tests for the auth skeleton — no Docker, no network."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import main  # noqa: E402
from server.config import allowed_hosts, bind_is_loopback, config, ssl_kwargs  # noqa: E402

TOKEN = "s3cret"


@pytest.fixture()
def cfg(monkeypatch):
    """Reset auth config to a known state; tests override what they need."""
    monkeypatch.setattr(config, "MEM_TOKEN", "")
    monkeypatch.setattr(config, "MEM_BIND_ADDR", "127.0.0.1")
    monkeypatch.setattr(config, "MEM_ALLOWED_HOSTS", "")
    monkeypatch.setattr(config, "TLS_CERT_FILE", "")
    monkeypatch.setattr(config, "TLS_KEY_FILE", "")
    return monkeypatch


def client() -> TestClient:
    return TestClient(main.app)


# --- startup guard ---------------------------------------------------------

@pytest.mark.parametrize("addr", ["127.0.0.1", "localhost", "::1", "[::1]"])
def test_loopback_without_token_starts(cfg, addr):
    cfg.setattr(config, "MEM_BIND_ADDR", addr)
    assert bind_is_loopback()
    main._assert_auth_configured()


@pytest.mark.parametrize("addr", ["0.0.0.0", "192.168.1.10"])
def test_exposed_without_token_refuses(cfg, addr):
    cfg.setattr(config, "MEM_BIND_ADDR", addr)
    with pytest.raises(RuntimeError, match="refusing to start"):
        main._assert_auth_configured()


def test_exposed_with_token_starts(cfg):
    cfg.setattr(config, "MEM_BIND_ADDR", "0.0.0.0")
    cfg.setattr(config, "MEM_TOKEN", TOKEN)
    main._assert_auth_configured()


def test_lifespan_runs_the_guard(cfg):
    cfg.setattr(config, "MEM_BIND_ADDR", "0.0.0.0")
    with pytest.raises(RuntimeError, match="refusing to start"):
        with client():
            pass


# --- bearer middleware -----------------------------------------------------

def test_no_token_configured_everything_open(cfg):
    with client() as c:
        assert c.get("/health").status_code == 200
        # Unknown route reaches routing (404), not the auth gate.
        assert c.get("/anything").status_code == 404


def test_health_is_public(cfg):
    cfg.setattr(config, "MEM_TOKEN", TOKEN)
    with client() as c:
        r = c.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": "Bearer wrong"},
    {"Authorization": f"Basic {TOKEN}"},
    {"Authorization": TOKEN},
    {"Authorization": "Bearer "},
])
def test_protected_route_rejects(cfg, headers):
    cfg.setattr(config, "MEM_TOKEN", TOKEN)
    with client() as c:
        r = c.get("/anything", headers=headers)
    assert r.status_code == 401
    assert r.json() == {"error": "unauthorized"}


def test_token_in_query_string_rejected(cfg):
    cfg.setattr(config, "MEM_TOKEN", TOKEN)
    with client() as c:
        assert c.get(f"/anything?token={TOKEN}").status_code == 401


@pytest.mark.parametrize("value", [f"Bearer {TOKEN}", f"bearer {TOKEN}", f"Bearer  {TOKEN} "])
def test_protected_route_accepts_valid_bearer(cfg, value):
    cfg.setattr(config, "MEM_TOKEN", TOKEN)
    with client() as c:
        # Past the gate: routing answers 404 for a route that doesn't exist.
        assert c.get("/anything", headers={"Authorization": value}).status_code == 404


# --- config helpers --------------------------------------------------------

def test_allowed_hosts(cfg):
    cfg.setattr(config, "MEM_ALLOWED_HOSTS", " 192.168.1.10 , box.lan,")
    hosts = allowed_hosts()
    for h in ("127.0.0.1", "localhost", "[::1]", "192.168.1.10", "box.lan"):
        assert h in hosts and f"{h}:*" in hosts
    assert "" not in hosts


def test_ssl_kwargs(cfg, tmp_path):
    assert ssl_kwargs() == {}
    crt, key = tmp_path / "server.crt", tmp_path / "server.key"
    cfg.setattr(config, "TLS_CERT_FILE", str(crt))
    cfg.setattr(config, "TLS_KEY_FILE", str(key))
    assert ssl_kwargs() == {}  # configured but missing on disk → plain http
    crt.write_text("x")
    key.write_text("x")
    assert ssl_kwargs() == {"ssl_certfile": str(crt), "ssl_keyfile": str(key)}
