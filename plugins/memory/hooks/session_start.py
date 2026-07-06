#!/usr/bin/env python3
"""
SessionStart hook.
1. Ensure the Docker stack is up (docker compose up -d).
2. Wait for the MCP server to be healthy.
3. Trigger bulk ingest in background (non-blocking).
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (
    compose_file, cwd_from_hook, group_id, ingest_allowed, is_internal_session,
    mcp_get, mcp_post, read_stdin_json,
)

MAX_WAIT_S = 30

# No-op for the headless haiku subprocess's own SessionStart (see stop.py).
if is_internal_session():
    sys.exit(0)


def main() -> None:
    payload  = read_stdin_json()
    repo     = cwd_from_hook(payload)
    gid      = group_id(repo)

    # 1. Start Docker stack (skipped when the compose file can't be located —
    # the stack may already be running, so still try the health check below)
    cf = compose_file()
    if cf is not None:
        env_file = cf.parent / ".env"
        env_args = ["--env-file", str(env_file)] if env_file.exists() else []
        subprocess.run(
            ["docker", "compose", "-f", str(cf)] + env_args + ["up", "-d", "--remove-orphans"],
            check=False,
            capture_output=True,
        )
    else:
        print("[mem] warning: docker-compose.yml not found (run `market install`)", file=sys.stderr)

    # 2. Wait for health
    for _ in range(MAX_WAIT_S):
        resp = mcp_get("/health")
        if resp and resp.get("status") == "ok":
            break
        time.sleep(1.0)
    else:
        print("[mem] warning: MCP server not reachable after start", file=sys.stderr)
        return

    # 3. Trigger bulk ingest (non-blocking — server runs it in background).
    # Guard: never ingest an unbounded tree (home dir / non-repo) — walking it
    # over virtiofs floods Docker's fs service and crash-loops the VM.
    ok, why = ingest_allowed(repo)
    if not ok:
        print(f"[mem] skipping bulk ingest — {why}", file=sys.stderr)
        return
    status = mcp_get(f"/status/{gid}")
    if status and status.get("status") not in ("running", "done"):
        mcp_post("/ingest", {"group_id": gid, "repo_path": repo})

    sys.exit(0)


if __name__ == "__main__":
    main()
