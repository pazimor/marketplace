"""Repo-relative paths ↔ absolute paths on this server.

Chunks and file nodes are keyed by their **repo-relative** path, so the same
symbol gets the same node id whichever machine indexed it. Reading the source
back needs an absolute path, which is per-machine — this module owns that
mapping.

Two roots can provide a file, tried in order:

1. ``Project.repo_path`` — a working tree on this machine. Fresh: it reflects
   uncommitted edits.
2. ``Project.mirror_path`` — the server's own git clone (see ``mirror.py``).
   Only as fresh as the last push.

A project indexed from a remote machine has no working tree here and resolves
through the mirror alone.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from .db import get_graph


def _roots_uncached(group_id: str) -> tuple[str | None, str | None]:
    g = get_graph(group_id)
    res = g.query(
        "MATCH (p:Project {group_id: $gid}) RETURN p.repo_path, p.mirror_path LIMIT 1",
        {"gid": group_id},
    )
    if not res.result_set:
        return None, None
    repo, mirror = res.result_set[0]
    return repo, mirror


# Roots change only on ingest; a short cache keeps search from re-querying per hit.
@lru_cache(maxsize=64)
def _roots_cached(group_id: str) -> tuple[str | None, str | None]:
    return _roots_uncached(group_id)


def invalidate(group_id: str | None = None) -> None:
    """Drop cached roots — call after an ingest changes repo_path / mirror_path."""
    _roots_cached.cache_clear()


def rel_path(file_path: str, repo_path: str) -> str:
    """Repo-relative path with normalized forward slashes (fulltext-indexable)."""
    try:
        rel = os.path.relpath(file_path, repo_path)
    except ValueError:
        rel = file_path
    return rel.replace(os.sep, "/")


def resolve(group_id: str, path: str) -> str | None:
    """Absolute path of a stored (repo-relative) chunk path, or None.

    An absolute stored path is honoured as-is: graphs written before the
    rel_path migration still hold them, and re-ingest is what fixes those.
    """
    if not path:
        return None
    if os.path.isabs(path):
        return path if os.path.exists(path) else None

    repo, mirror = _roots_cached(group_id)
    for root in (repo, mirror):
        if not root:
            continue
        candidate = Path(root) / path
        if candidate.exists():
            return str(candidate)
    return None


def indexed_commit(group_id: str) -> str | None:
    """Commit the mirror was indexed at — None for a locally-indexed project."""
    g = get_graph(group_id)
    res = g.query(
        "MATCH (p:Project {group_id: $gid}) RETURN p.mirror_commit LIMIT 1",
        {"gid": group_id},
    )
    return res.result_set[0][0] if res.result_set else None
