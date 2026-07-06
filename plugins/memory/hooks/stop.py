#!/usr/bin/env python3
"""
Stop hook — two-stage gate before calling haiku.

Stage 1: dirty marker present?  → no marker = nothing to remember, exit 0.
Stage 2: call haiku on the session delta to write episodic memory.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (
    clear_dirty, clear_session_log, cwd_from_hook, group_id, is_dirty,
    is_internal_session, read_stdin_json,
)

# Prevent infinite loop: the headless haiku subprocess spawned below is itself
# a Claude Code session in this repo, so its own Stop hook must no-op.
if is_internal_session():
    sys.exit(0)


def main() -> None:
    payload = read_stdin_json()
    repo    = cwd_from_hook(payload)

    # Prevent infinite loop if this hook itself triggers a Stop event
    # (stop_hook_active is a field of the hook stdin payload, not an env var).
    if payload.get("stop_hook_active"):
        sys.exit(0)

    if not is_dirty(repo):
        sys.exit(0)

    # Clear the dirty marker before spawning haiku (not the session log, which
    # haiku still needs to read): haiku runs a full nested Claude Code session,
    # and if its own Stop hook ran before this cleared, it would still see
    # dirty=true and recursively spawn another haiku call.
    clear_dirty(repo)

    from _haiku import call_haiku
    transcript_path = payload.get("transcript_path", "")
    call_haiku(repo, transcript_path, group_id(repo))

    clear_session_log(repo)
    sys.exit(0)


if __name__ == "__main__":
    main()
