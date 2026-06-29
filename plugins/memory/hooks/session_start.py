#!/usr/bin/env python3
"""
SessionStart hook.
1. Ensure the Docker stack is up (docker compose up -d).
2. Wait for the MCP server to be healthy.
3. Trigger bulk ingest in background (non-blocking).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import cwd_from_hook, group_id, mcp_get, mcp_post, read_stdin_json

COMPOSE_FILE = Path(__file__).parents[3] / "docker" / "docker-compose.yml"
MAX_WAIT_S   = 30
ENV_FILE     = Path(__file__).parents[3] / "docker" / ".env"


def main() -> None:
    payload  = read_stdin_json()
    repo     = cwd_from_hook(payload)
    gid      = group_id(repo)

    # 1. Start Docker stack
    env_args = ["--env-file", str(ENV_FILE)] if ENV_FILE.exists() else []
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE)] + env_args + ["up", "-d", "--remove-orphans"],
        check=False,
        capture_output=True,
    )

    # 2. Wait for health
    for _ in range(MAX_WAIT_S):
        resp = mcp_get("/health")
        if resp and resp.get("status") == "ok":
            break
        time.sleep(1.0)
    else:
        print("[mem] warning: MCP server not reachable after start", file=sys.stderr)
        return

    # 3. Trigger bulk ingest (non-blocking — server runs it in background)
    status = mcp_get(f"/status/{gid}")
    if status and status.get("status") not in ("running", "done"):
        mcp_post("/ingest", {"group_id": gid, "repo_path": repo})

    sys.exit(0)


if __name__ == "__main__":
    main()
