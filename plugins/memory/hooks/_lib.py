"""Shared utilities for all hook scripts."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

# Optional user settings (e.g. {"distill_sync": true, "host": …, "token": …}).
# Read early: the server address and secret live here on machines that talk to
# an MCP server running elsewhere (`market install --client-only`).
SETTINGS_FILE = Path.home() / ".config" / "market" / "settings.json"


def market_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except Exception:
        return {}


MEM_HOST = os.getenv("MEM_HOST") or str(market_settings().get("host") or "") or "127.0.0.1"
MEM_PORT = os.getenv("MEM_PORT", "7333")
MEM_URL  = f"https://{MEM_HOST}:{MEM_PORT}"

LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def mem_is_remote() -> bool:
    """True when the MCP server runs on another machine — it then has no access
    to this machine's filesystem, so path-based operations must be skipped."""
    return MEM_HOST not in LOOPBACK


def mem_verify():
    """TLS verification policy for the MCP connection.

    Loopback: the mkcert cert is locally trusted but httpx uses the certifi
    bundle, not the system keychain — verification would fail for no security
    gain, since there is no MITM risk on 127.0.0.1.

    Remote host: verification is mandatory. httpx still can't see the system
    trust store, so it needs the mkcert CA explicitly — MEM_CA_BUNDLE, else
    ~/.config/market/ca.pem, else the default bundle (works if the server has
    a publicly-trusted cert).
    """
    if MEM_HOST in LOOPBACK:
        return False
    ca = os.getenv("MEM_CA_BUNDLE") or str(Path.home() / ".config" / "market" / "ca.pem")
    return ca if Path(ca).exists() else True


MEM_VERIFY = mem_verify()

SESSION_LOG_NAME    = ".mcp-memory/session.log"

# Set on the env of the headless `claude -p` subprocesses spawned by the
# distiller (extractor + arbiter). Their own hook invocations
# (SessionStart/PostToolUse/SessionEnd/SubagentStop) must no-op, otherwise
# each SessionStart would spawn another distiller (infinite loop / token burn).
INTERNAL_SESSION_ENV = "MEM_HOOK_INTERNAL"


def is_internal_session() -> bool:
    return os.getenv(INTERNAL_SESSION_ENV) == "1"


# Written by `market install` — survives the native plugin install, where this
# file is copied under ~/.claude/plugins/ and repo-relative paths break.
COMPOSE_POINTER = Path.home() / ".config" / "market" / "compose_path"


def mem_token() -> str:
    """Shared secret for the MCP server: MEM_TOKEN env, else settings.json.

    Empty when the server runs unauthenticated (loopback-only setups)."""
    return os.getenv("MEM_TOKEN") or str(market_settings().get("token") or "")


def mem_headers() -> dict:
    tok = mem_token()
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def distill_sync_enabled() -> bool:
    """Distillation runs detached in the background by default; MEM_DISTILL_SYNC=1
    (or distill_sync=true in ~/.config/market/settings.json) makes SessionStart
    block until the past transcripts are distilled."""
    env = os.getenv("MEM_DISTILL_SYNC")
    if env is not None:
        return env == "1"
    return bool(market_settings().get("distill_sync"))


def compose_file() -> Path | None:
    """Locate market-mem/docker-compose.yml: env var → installer pointer → repo-relative fallback."""
    env = os.getenv("MEM_COMPOSE_FILE")
    if env and Path(env).exists():
        return Path(env)
    try:
        if COMPOSE_POINTER.exists():
            p = Path(COMPOSE_POINTER.read_text().strip())
            if p.exists():
                return p
    except Exception:
        pass
    fallback = Path(__file__).parents[3] / "market-mem" / "docker-compose.yml"
    return fallback if fallback.exists() else None


def read_stdin_json() -> dict:
    try:
        return json.loads(sys.stdin.read())
    except Exception:
        return {}


def cwd_from_hook(payload: dict) -> str:
    return payload.get("cwd") or os.getcwd()


def group_id(repo_path: str) -> str:
    key: str | None = None
    try:
        out = subprocess.check_output(
            ["git", "-C", repo_path, "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if out:
            key = out
    except Exception:
        pass
    if not key:
        key = str(Path(repo_path).resolve())
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def git_remote_url(repo_path: str) -> str:
    """origin's URL — what a remote server needs to clone this repo itself."""
    try:
        return subprocess.check_output(
            ["git", "-C", repo_path, "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return ""


def current_branch(repo_path: str) -> str:
    """Checked-out branch, empty on a detached HEAD (the server then uses the
    remote's default branch)."""
    try:
        branch = subprocess.check_output(
            ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
        return "" if branch == "HEAD" else branch
    except Exception:
        return ""


# Mirrors MAX_REINDEX_BYTES on the server — don't ship what it will refuse.
MAX_REINDEX_BYTES = 1_000_000


def reindex_payload(gid: str, repo: str, file_path: str) -> dict | None:
    """Body for a content-carrying /reindex, or None when it can't be built.

    Used against a remote server: it cannot open *file_path*, so the file's
    text travels with the request, keyed by its repo-relative path."""
    try:
        p = Path(file_path)
        if p.is_dir():
            return None
        rel = os.path.relpath(str(p), repo).replace(os.sep, "/")
        if rel.startswith(".."):
            return None  # outside the repo — not ours to index
        if p.stat().st_size > MAX_REINDEX_BYTES:
            return None
        return {"group_id": gid, "rel_path": rel,
                "content": p.read_text(errors="replace")}
    except OSError:
        return None


def ingest_allowed(repo_path: str) -> tuple[bool, str]:
    """
    Guard bulk ingest against unbounded / non-project trees.

    Bulk ingest walks the whole tree over the Docker virtiofs share; pointing it
    at a home directory or filesystem root floods Docker Desktop's file-sharing
    service ("fs injecting event blocked for 60s") and crash-loops the VM.
    We only ingest a real git work tree, and never the home dir / root.
    """
    try:
        resolved = Path(repo_path).resolve()
    except Exception:
        return False, f"cannot resolve path: {repo_path!r}"

    if resolved == Path.home():
        return False, "refusing to ingest the home directory"
    if resolved == Path(resolved.anchor):
        return False, "refusing to ingest the filesystem root"

    try:
        inside = subprocess.check_output(
            ["git", "-C", str(resolved), "rev-parse", "--is-inside-work-tree"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return False, f"not a git work tree: {resolved}"
    if inside != "true":
        return False, f"not a git work tree: {resolved}"

    return True, ""


def session_log_path(repo_path: str) -> Path:
    return Path(repo_path) / SESSION_LOG_NAME


def append_session_log(repo_path: str, entry: dict) -> None:
    log_file = session_log_path(repo_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def clear_session_log(repo_path: str) -> None:
    session_log_path(repo_path).unlink(missing_ok=True)


def mcp_get(path: str, timeout: float = 5.0) -> dict | None:
    try:
        r = httpx.get(f"{MEM_URL}{path}", timeout=timeout, verify=MEM_VERIFY,
                      headers=mem_headers())
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def mcp_post(path: str, body: dict, timeout: float = 10.0) -> dict | None:
    try:
        r = httpx.post(f"{MEM_URL}{path}", json=body, timeout=timeout, verify=MEM_VERIFY,
                       headers=mem_headers())
        r.raise_for_status()
        return r.json()
    except Exception:
        return None
