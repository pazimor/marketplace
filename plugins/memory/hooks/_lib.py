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
MEM_URL  = f"http://{MEM_HOST}:{MEM_PORT}"

DIRTY_MARKER_NAME   = ".mcp-memory/dirty"
SESSION_LOG_NAME    = ".mcp-memory/session.log"


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
        r = httpx.get(f"{MEM_URL}{path}", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def mcp_post(path: str, body: dict, timeout: float = 10.0) -> dict | None:
    try:
        r = httpx.post(f"{MEM_URL}{path}", json=body, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None
