"""Compute a stable group_id for a repository path."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


def compute(repo_path: str) -> str:
    """
    Primary key: SHA-256 of the git remote 'origin' URL (stable across clones).
    Fallback: SHA-256 of the resolved absolute path.
    Returns the first 16 hex chars.
    """
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
