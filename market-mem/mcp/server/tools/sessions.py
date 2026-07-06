"""
Processed-session ledger.

The SessionStart distiller (plugins/memory/hooks/_distill.py) turns past
session transcripts into episodic memory. This ledger records which session
ids have already been distilled, so a crash mid-distillation is replayed and
a completed transcript is never processed twice.

Stored in the project graph itself (:ProcessedSession) — durable across
container restarts and shared by all worktrees of the project.
"""
from __future__ import annotations

import time

from ..db import get_graph
from ..schema import ensure_schema

VALID_STATUSES = {"done", "skipped", "empty", "failed"}


def sessions_processed(group_id: str) -> dict:
    """All ledger entries for the project, most recent first."""
    ensure_schema(group_id)
    g = get_graph(group_id)
    res = g.query(
        """
        MATCH (s:ProcessedSession {group_id: $gid})
        RETURN s.id, s.status, s.processed_at, s.facts_written
        ORDER BY s.processed_at DESC
        """,
        {"gid": group_id},
    )
    entries = [
        {"session_id": r[0], "status": r[1], "processed_at": r[2], "facts_written": r[3]}
        for r in (res.result_set or [])
    ]
    return {"group_id": group_id, "sessions": entries,
            "ids": [e["session_id"] for e in entries]}


def session_mark_processed(
    group_id: str,
    session_id: str,
    status: str = "done",
    facts_written: int = 0,
) -> dict:
    if status not in VALID_STATUSES:
        return {"status": "error",
                "error": f"invalid status '{status}' (allowed: {sorted(VALID_STATUSES)})"}
    ensure_schema(group_id)
    g = get_graph(group_id)
    now = int(time.time() * 1000)
    g.query(
        """
        MERGE (s:ProcessedSession {id: $sid, group_id: $gid})
        SET s.status        = $status,
            s.processed_at  = $now,
            s.facts_written = $facts
        """,
        {"sid": session_id, "gid": group_id, "status": status,
         "now": now, "facts": facts_written},
    )
    return {"status": "ok", "session_id": session_id, "ledger_status": status}
