#!/usr/bin/env python3
"""
PreToolUse hook — fires before Read.

The code RAG (code_search / code_fetch) only accrues token savings when the
master actually calls those MCP tools. In practice the master defaults to raw
Read on source files and never touches the RAG, so token_stats.json stays flat.

This hook nudges — at the exact moment the master is about to Read a *code*
file — to prefer code_search first. Non-blocking (the Read still proceeds via
`permissionDecision: allow`); the reminder rides along as additionalContext.

Throttled to once per session (marker keyed by session_id) so a long editing
session isn't spammed. Deterministic, no network call, no LLM.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import cwd_from_hook, is_internal_session, read_stdin_json

# No-op for the headless haiku subprocess (it does its own reconcile, and must
# never be steered away from Read — see _distill.py).
if is_internal_session():
    sys.exit(0)

# Source files where a semantic code_search / code_fetch genuinely beats a raw
# Read. Config / prose / data files are intentionally excluded — Read is right
# for those and a nudge would be noise.
CODE_SUFFIXES = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".go", ".rs", ".java", ".kt", ".kts", ".scala", ".c", ".h",
    ".cc", ".cpp", ".hpp", ".cxx", ".cs", ".rb", ".php", ".swift",
    ".m", ".mm", ".lua", ".dart", ".ex", ".exs", ".erl", ".clj",
    ".hs", ".ml", ".sh", ".bash", ".zsh", ".sql", ".vue", ".svelte",
}

NUDGE_MARKER_NAME = ".mcp-memory/nudge"

REMINDER = (
    "Code RAG available: prefer `code_search` (semantic, ~10-20x fewer tokens "
    "than a full Read) to locate the relevant chunk, then `code_fetch` on that "
    "chunk. Fall back to Read only when the chunk is insufficient (e.g. you need "
    "the exact surrounding text to Edit). This also feeds the code-RAG token stats."
)


def _already_nudged(repo: str, session_id: str) -> bool:
    """True if this session was already nudged. Records the session on first call."""
    marker = Path(repo) / NUDGE_MARKER_NAME
    try:
        if marker.exists() and marker.read_text().strip() == session_id:
            return True
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(session_id)
    except Exception:
        # Best-effort throttle: if the marker can't be read/written, fall back to
        # nudging (better a redundant reminder than silently never nudging).
        return False
    return False


def _emit_reminder() -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "additionalContext": REMINDER,
        }
    }))


def main() -> None:
    payload = read_stdin_json()
    if payload.get("tool_name") != "Read":
        sys.exit(0)

    fp = (payload.get("tool_input") or {}).get("file_path") or ""
    if not fp or Path(fp).suffix.lower() not in CODE_SUFFIXES:
        sys.exit(0)

    repo = cwd_from_hook(payload)
    session_id = payload.get("session_id") or ""
    if _already_nudged(repo, session_id):
        sys.exit(0)

    _emit_reminder()
    sys.exit(0)


if __name__ == "__main__":
    main()
