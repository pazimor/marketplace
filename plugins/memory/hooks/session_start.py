#!/usr/bin/env python3
"""
SessionStart hook.
1. Ensure the Docker stack is up (docker compose up -d).
2. Wait for the MCP server to be healthy.
3. Trigger bulk ingest in background (non-blocking).
4. Distill past session transcripts into episodic memory (extractor haiku →
   arbiter sonnet, see _distill.py). Detached background process by default;
   inline (blocking) when MEM_DISTILL_SYNC=1 or distill_sync=true in
   ~/.config/market/settings.json.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (
    compose_file, cwd_from_hook, distill_sync_enabled, group_id, ingest_allowed,
    is_internal_session, mcp_get, mcp_post, read_stdin_json,
)

MAX_WAIT_S = 30

CLAUDE_MD_START = "<!-- market-mem:start -->"
CLAUDE_MD_END = "<!-- market-mem:end -->"


def claude_md_block(gid: str) -> str:
    return "\n".join([
        CLAUDE_MD_START,
        "## Memory graph (managed by market-mem — do not edit this block)",
        f"This project's graph id: `group_id = \"{gid}\"` — pass it to every memory MCP tool.",
        f"- Conceptual code question (\"where is X handled?\") → `code_search(group_id=\"{gid}\", query=…)` BEFORE Grep/Read.",
        f"- Architecture decision, refactor, or reopening a past choice → `memory_search(group_id=\"{gid}\", query=…)` before acting.",
        "- Empty results are cheap and expected — call speculatively.",
        CLAUDE_MD_END,
    ])


def ensure_claude_md_block(repo: str, gid: str) -> None:
    """Keep a marker-fenced usage block (group_id + trigger rules) in the
    project's CLAUDE.md. Idempotent; never creates the file, never touches
    anything outside the markers. Best-effort."""
    try:
        path = Path(repo) / "CLAUDE.md"
        if not path.is_file():
            return
        text = path.read_text()
        block = claude_md_block(gid)
        if CLAUDE_MD_START in text and CLAUDE_MD_END in text:
            head, rest = text.split(CLAUDE_MD_START, 1)
            _, tail = rest.split(CLAUDE_MD_END, 1)
            new = head + block + tail
        else:
            new = text.rstrip("\n") + "\n\n" + block + "\n"
        if new != text:
            path.write_text(new)
    except Exception as exc:
        print(f"[mem] CLAUDE.md block skipped: {exc}", file=sys.stderr)

# No-op for the headless distiller subprocesses' own SessionStart (see _distill.py).
if is_internal_session():
    sys.exit(0)


def launch_distiller(payload: dict, repo: str) -> None:
    """Distill past transcripts. The transcript dir is derived from the current
    session's transcript_path (same directory holds the whole project history)."""
    transcript_path = payload.get("transcript_path", "")
    if not transcript_path:
        return
    tdir = Path(transcript_path).parent
    if not tdir.is_dir():
        return
    current_sid = payload.get("session_id") or Path(transcript_path).stem

    if distill_sync_enabled():
        from _distill import distill_all
        distill_all(repo, str(tdir), current_sid)
        return

    log_file = Path(repo) / ".mcp-memory" / "distill.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a") as log:
        subprocess.Popen(
            [
                sys.executable, str(Path(__file__).parent / "_distill.py"),
                "--repo", repo,
                "--transcript-dir", str(tdir),
                "--exclude-session", current_sid,
            ],
            stdout=log,
            stderr=log,
            start_new_session=True,   # detached — survives the hook exiting
        )


def main() -> None:
    payload  = read_stdin_json()
    repo     = cwd_from_hook(payload)
    gid      = group_id(repo)

    ensure_claude_md_block(repo, gid)

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
    else:
        status = mcp_get(f"/status/{gid}")
        if status and status.get("status") not in ("running", "done"):
            mcp_post("/ingest", {"group_id": gid, "repo_path": repo})

    # 4. Distill past session transcripts (background unless MEM_DISTILL_SYNC=1)
    launch_distiller(payload, repo)

    sys.exit(0)


if __name__ == "__main__":
    main()
