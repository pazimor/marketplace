#!/usr/bin/env python3
"""
SessionEnd hook — flush safety net.

If the dirty marker is still set (Stop hook was skipped / stalled),
call haiku here as a last resort, then stop the Docker stack.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import clear_dirty, clear_session_log, cwd_from_hook, group_id, is_dirty, read_stdin_json

COMPOSE_FILE = Path(__file__).parents[3] / "docker" / "docker-compose.yml"
ENV_FILE     = Path(__file__).parents[3] / "docker" / ".env"


def main() -> None:
    payload = read_stdin_json()
    repo    = cwd_from_hook(payload)

    if is_dirty(repo):
        # Guard: skip haiku if stop_hook_active (shouldn't happen here but be safe)
        if not os.getenv("stop_hook_active"):
            from _haiku import call_haiku
            transcript_path = payload.get("transcript_path", "")
            call_haiku(repo, transcript_path, group_id(repo))

        clear_dirty(repo)
        clear_session_log(repo)

    # Keep volumes alive — just stop the containers.
    env_args = ["--env-file", str(ENV_FILE)] if ENV_FILE.exists() else []
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE)] + env_args + ["stop"],
        check=False,
        capture_output=True,
    )

    sys.exit(0)


if __name__ == "__main__":
    main()
