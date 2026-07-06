"""
graph_overview — one call for the agent to orient itself in the project graph.
bootstrap — payload injected by the SessionStart hook (~1-2k tokens):
backlog state + most relevant memories + graph stats.
"""
from __future__ import annotations

import time

from ..db import get_graph
from ..schema import ensure_schema
from .roadmap import backlog_get

_LABELS = ["CodeChunk", "MemoryEpisode", "FileNode", "Spec", "Milestone", "Task"]


def graph_overview(group_id: str) -> dict:
    """Node counts by type, latest memory additions, active milestones,
    claimed tasks — everything needed to orient in one call."""
    ensure_schema(group_id)
    g = get_graph(group_id)
    now = int(time.time() * 1000)

    counts: dict[str, int] = {}
    for label in _LABELS:
        try:
            counts[label] = g.query(f"MATCH (n:{label}) RETURN count(n)").result_set[0][0]
        except Exception:
            counts[label] = 0

    recent = g.query(
        """
        MATCH (m:MemoryEpisode)
        WHERE m.valid_from <= $now AND (m.invalid_at IS NULL OR m.invalid_at > $now)
        RETURN m.id, m.type, m.content, m.created_at
        ORDER BY m.created_at DESC LIMIT 5
        """,
        {"now": now},
    )
    recent_memories = [
        {"id": r[0], "type": r[1],
         "content": (r[2] or "")[:300], "created_at": r[3]}
        for r in recent.result_set
    ]

    milestones = g.query(
        """
        MATCH (m:Milestone) WHERE m.status = 'active'
        OPTIONAL MATCH (t:Task)-[:PART_OF]->(m)
        RETURN m.id, m.title,
               count(t), count(CASE WHEN t.status = 'done' THEN 1 END)
        ORDER BY m.id
        """
    )
    active_milestones = [
        {"id": r[0], "title": r[1], "tasks": r[2], "done": r[3]}
        for r in milestones.result_set
    ]

    claimed = g.query(
        """
        MATCH (t:Task) WHERE t.claimed_by IS NOT NULL
        RETURN t.id, t.title, t.status, t.claimed_by, t.claimed_worktree
        ORDER BY t.id
        """
    )
    claimed_tasks = [
        {"id": r[0], "title": r[1], "status": r[2],
         "claimed_by": r[3], "worktree": r[4]}
        for r in claimed.result_set
    ]

    return {
        "group_id": group_id,
        "nodes": counts,
        "recent_memories": recent_memories,
        "active_milestones": active_milestones,
        "claimed_tasks": claimed_tasks,
    }


def bootstrap(group_id: str) -> dict:
    """Session bootstrap payload: backlog + recent memories + stats.
    Deterministic — no embedding call, safe on a cold server."""
    from .stats import stats_get

    overview = graph_overview(group_id)
    backlog = backlog_get(group_id, include_done=False)
    try:
        token_stats = stats_get(group_id)
    except Exception:
        token_stats = None
    return {
        "overview": overview,
        "backlog": backlog,
        "token_stats": token_stats,
    }
