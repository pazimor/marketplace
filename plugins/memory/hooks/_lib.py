"""Shared utilities for all hook scripts."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

MEM_HOST = os.getenv("MEM_HOST", "127.0.0.1")
MEM_PORT = os.getenv("MEM_PORT", "7333")
MEM_URL  = f"https://{MEM_HOST}:{MEM_PORT}"
# Loopback-only connection with a locally-trusted (mkcert) cert. httpx uses the
# certifi bundle, not the macOS keychain, so skip verification — no MITM risk on
# 127.0.0.1.
MEM_VERIFY = False

DIRTY_MARKER_NAME   = ".mcp-memory/dirty"
SESSION_LOG_NAME    = ".mcp-memory/session.log"

# Set on the env of the headless `claude -p` haiku subprocess. Its own hook
# invocations (SessionStart/PostToolUse/Stop/SessionEnd/SubagentStop) must
# no-op, otherwise its Stop/SessionEnd would see the still-dirty marker and
# recursively spawn another haiku subprocess (infinite loop / token burn).
INTERNAL_SESSION_ENV = "MEM_HOOK_INTERNAL"


def is_internal_session() -> bool:
    return os.getenv(INTERNAL_SESSION_ENV) == "1"


# Written by `market install` — survives the native plugin install, where this
# file is copied under ~/.claude/plugins/ and repo-relative paths break.
COMPOSE_POINTER = Path.home() / ".config" / "market" / "compose_path"


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


def dirty_marker(repo_path: str) -> Path:
    return Path(repo_path) / DIRTY_MARKER_NAME


def mark_dirty(repo_path: str) -> None:
    m = dirty_marker(repo_path)
    m.parent.mkdir(parents=True, exist_ok=True)
    m.touch()


def is_dirty(repo_path: str) -> bool:
    return dirty_marker(repo_path).exists()


def clear_dirty(repo_path: str) -> None:
    dirty_marker(repo_path).unlink(missing_ok=True)


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
        r = httpx.get(f"{MEM_URL}{path}", timeout=timeout, verify=MEM_VERIFY)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def mcp_post(path: str, body: dict, timeout: float = 10.0) -> dict | None:
    try:
        r = httpx.post(f"{MEM_URL}{path}", json=body, timeout=timeout, verify=MEM_VERIFY)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None
