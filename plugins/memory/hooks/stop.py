#!/usr/bin/env python3
"""
Stop hook — two-stage gate before calling haiku.

Stage 1: dirty marker present?  → no marker = nothing to remember, exit 0.
Stage 2: call haiku on the session delta to write episodic memory.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import clear_dirty, clear_session_log, cwd_from_hook, group_id, is_dirty, read_stdin_json

# Prevent infinite loop if this hook itself triggers a Stop event
if os.getenv("stop_hook_active"):
    sys.exit(0)


def main() -> None:
    payload = read_stdin_json()
    repo    = cwd_from_hook(payload)

    if not is_dirty(repo):
        sys.exit(0)

    from _haiku import call_haiku
    transcript_path = payload.get("transcript_path", "")
    call_haiku(repo, transcript_path, group_id(repo))

    clear_dirty(repo)
    clear_session_log(repo)
    sys.exit(0)


if __name__ == "__main__":
    main()
