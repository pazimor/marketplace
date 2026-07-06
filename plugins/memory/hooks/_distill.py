#!/usr/bin/env python3
"""
Transcript distiller — turns PAST session transcripts into episodic memory.

Replaces the old Stop-hook haiku writer: transcripts are durable on disk, so
distilling them at the NEXT SessionStart is replayable and also captures
sessions that ended abnormally (crash, killed terminal).

Two-stage pipeline per transcript:
  Stage A  extractor (haiku)  — reads the condensed transcript, outputs
           candidate facts as strict JSON. No MCP access, no writes.
  Stage B  arbiter (sonnet)   — reads the candidates, memory_search's the
           existing graph, and decides ADD / MERGE / DISCARD via the memory
           MCP tools. This is where dedup and contradiction-resolution live.

Idempotence: the ledger (GET /sessions/{gid}, POST /sessions/processed) lives
in the project graph. 'failed' entries are retried on the next run; 'done',
'skipped' and 'empty' are final.

Invoked by session_start.py — detached in the background by default, inline
when MEM_DISTILL_SYNC=1 (or distill_sync=true in ~/.config/market/settings.json).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import INTERNAL_SESSION_ENV, group_id, mcp_get, mcp_post

EXTRACTOR_MODEL   = os.getenv("MEM_EXTRACTOR_MODEL", "claude-haiku-4-5-20251001")
ARBITER_MODEL     = os.getenv("MEM_ARBITER_MODEL", "claude-sonnet-5")
EXTRACTOR_TIMEOUT = 120   # seconds
ARBITER_TIMEOUT   = 300   # seconds

MAX_SESSIONS_PER_RUN = 3        # newest first; older unprocessed → 'skipped'
MAX_TRANSCRIPT_TURNS = 40
MAX_TURN_CHARS       = 1_500
MAX_TRANSCRIPT_CHARS = 24_000
MIN_TRANSCRIPT_BYTES = 2_000    # smaller than this → nothing happened

_PROMPTS_DIR = Path(__file__).parent / "prompts"

# Final ledger statuses — anything not listed here (i.e. 'failed') is retried.
_FINAL_STATUSES = {"done", "skipped", "empty"}


def _prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.md").read_text()


def condense_transcript(transcript_path: Path) -> str:
    """Flatten a session .jsonl into '[role]: text' turns, newest-truncated."""
    try:
        raw = transcript_path.read_text(errors="replace").splitlines()
    except Exception:
        return ""

    turns: list[str] = []
    for line in reversed(raw):
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if "message" in msg:
            msg = msg["message"]

        role    = msg.get("role") or msg.get("type", "")
        content = msg.get("content", "")
        if isinstance(content, list):
            parts = [b.get("text", "") for b in content
                     if isinstance(b, dict) and b.get("type") == "text"]
            content = " ".join(p for p in parts if p.strip())

        content = str(content).strip()
        if role in ("user", "human", "assistant") and content:
            turns.append(f"[{role}]: {content[:MAX_TURN_CHARS]}")
        if len(turns) >= MAX_TRANSCRIPT_TURNS:
            break

    text = "\n\n".join(reversed(turns))
    return text[-MAX_TRANSCRIPT_CHARS:] if len(text) > MAX_TRANSCRIPT_CHARS else text


def _run_agent(model: str, prompt: str, repo: str, timeout: int) -> str | None:
    """Headless `claude -p` subprocess. Returns stdout, or None on failure.
    INTERNAL_SESSION_ENV makes the subprocess's own hooks no-op (no recursion)."""
    try:
        result = subprocess.run(
            ["claude", "--model", model, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=repo,
            env={**os.environ, INTERNAL_SESSION_ENV: "1"},
        )
    except FileNotFoundError:
        print("[mem] 'claude' CLI not found — cannot distill", flush=True)
        return None
    except subprocess.TimeoutExpired:
        print(f"[mem] {model} timed out after {timeout}s", flush=True)
        return None
    except Exception as exc:
        print(f"[mem] {model} error: {exc}", flush=True)
        return None
    if result.returncode != 0:
        print(f"[mem] {model} exited {result.returncode}: {result.stderr[:200]}", flush=True)
        return None
    return result.stdout


def parse_candidates(raw: str) -> list[dict] | None:
    """Extract the JSON array from the extractor output. None = parse failure
    (retryable), [] = extractor legitimately found nothing."""
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start:end + 1])
    except Exception:
        return None
    if not isinstance(parsed, list):
        return None
    return [c for c in parsed if isinstance(c, dict) and c.get("content")]


def parse_facts_written(raw: str) -> int:
    m = re.search(r"FACTS_WRITTEN:\s*(\d+)", raw)
    return int(m.group(1)) if m else 0


def distill_one(transcript: Path, repo: str, gid: str) -> tuple[str, int]:
    """Run the two-stage pipeline on one transcript. Returns (status, facts)."""
    if transcript.stat().st_size < MIN_TRANSCRIPT_BYTES:
        return "empty", 0

    condensed = condense_transcript(transcript)
    if not condensed.strip():
        return "empty", 0

    # Stage A — extractor (haiku), JSON out, no writes
    out = _run_agent(
        EXTRACTOR_MODEL,
        f"{_prompt('extractor')}\n\n--- SESSION TRANSCRIPT ---\n\n{condensed}",
        repo,
        EXTRACTOR_TIMEOUT,
    )
    if out is None:
        return "failed", 0
    candidates = parse_candidates(out)
    if candidates is None:
        return "failed", 0
    if not candidates:
        return "empty", 0

    # Stage B — arbiter (sonnet), decides via memory MCP tools
    out = _run_agent(
        ARBITER_MODEL,
        f"{_prompt('arbiter')}\n\n"
        f"group_id for all memory tool calls: {gid}\n\n"
        f"--- CANDIDATE FACTS ---\n\n{json.dumps(candidates, indent=2)}",
        repo,
        ARBITER_TIMEOUT,
    )
    if out is None:
        return "failed", 0
    return "done", parse_facts_written(out)


def pending_transcripts(transcript_dir: Path, gid: str, exclude: str) -> tuple[list[Path], list[Path]]:
    """(to_process, to_skip): unprocessed transcripts newest-first, capped at
    MAX_SESSIONS_PER_RUN; the overflow is marked 'skipped' (first-install
    backlog must not trigger an unbounded distillation storm)."""
    ledger = mcp_get(f"/sessions/{gid}") or {}
    final = {e["session_id"] for e in ledger.get("sessions", [])
             if e.get("status") in _FINAL_STATUSES}

    candidates = sorted(
        (p for p in transcript_dir.glob("*.jsonl")
         if p.stem != exclude and p.stem not in final),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[:MAX_SESSIONS_PER_RUN], candidates[MAX_SESSIONS_PER_RUN:]


def distill_all(repo: str, transcript_dir: str, exclude_session: str) -> int:
    tdir = Path(transcript_dir)
    if not tdir.is_dir():
        return 0
    gid = group_id(repo)

    if mcp_get("/health") is None:
        print("[mem] MCP server unreachable — distillation postponed", flush=True)
        return 0

    to_process, to_skip = pending_transcripts(tdir, gid, exclude_session)

    for t in to_skip:
        mcp_post("/sessions/processed",
                 {"group_id": gid, "session_id": t.stem, "status": "skipped"})

    total = 0
    for t in to_process:
        status, facts = distill_one(t, repo, gid)
        mcp_post("/sessions/processed",
                 {"group_id": gid, "session_id": t.stem,
                  "status": status, "facts_written": facts})
        print(f"[mem] distilled {t.stem}: {status} ({facts} facts)", flush=True)
        total += facts
    return total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--transcript-dir", required=True)
    ap.add_argument("--exclude-session", default="")
    args = ap.parse_args()
    distill_all(args.repo, args.transcript_dir, args.exclude_session)


if __name__ == "__main__":
    main()
