"""
Episodic memory writer — spawns a headless Claude Code agent (haiku) to extract facts.

The agent has access to the memory MCP server and calls memory_add directly.
No Anthropic SDK needed on the host — uses the claude CLI.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

HAIKU_MODEL          = "claude-haiku-4-5-20251001"
MAX_TRANSCRIPT_TURNS = 8
MAX_DELTA_CHARS      = 10_000
AGENT_TIMEOUT        = 60   # seconds

_INSTRUCTIONS = """\
You are a memory extraction agent for a software development project.

Analyse the conversation delta provided below and call memory_add for each fact
worth remembering long-term.

Rules:
- Only write facts with LASTING relevance: architectural decisions, naming conventions,
  discovered bugs and their root causes, technical constraints, user preferences.
- Do NOT write: step-by-step narration of what was done, generic programming advice,
  temporary debug steps, or facts obvious from reading the code.
- Each call to memory_add must be self-contained — readable months later with no context.
- Be concise: 1–2 sentences per fact.
- For anchor: provide the most relevant code symbol (module.func or module.Class.method)
  only when the fact is tightly bound to that symbol. Omit (empty string) otherwise.
- If nothing is worth remembering, call memory_add zero times — that is perfectly fine.\
"""


def _read_transcript(transcript_path: str) -> str:
    if not transcript_path:
        return ""
    try:
        raw = Path(transcript_path).read_text(errors="replace").splitlines()
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
            parts: list[str] = []
            for block in content:
                if not isinstance(block, dict):
                    parts.append(str(block))
                elif block.get("type") == "text":
                    parts.append(block.get("text", ""))
            content = " ".join(p for p in parts if p.strip())

        content = str(content).strip()
        if role in ("user", "human", "assistant") and content:
            turns.append(f"[{role}]: {content[:1500]}")
        if len(turns) >= MAX_TRANSCRIPT_TURNS:
            break

    return "\n\n".join(reversed(turns))


def _read_session_log(repo_path: str) -> str:
    log_file = Path(repo_path) / ".mcp-memory" / "session.log"
    if not log_file.exists():
        return ""
    try:
        entries: list[str] = []
        for line in log_file.read_text(errors="replace").splitlines()[-30:]:
            try:
                e = json.loads(line)
                entries.append(f"  {e.get('tool','?')}  {e.get('path','?')}")
            except Exception:
                pass
        return ("Files modified this session:\n" + "\n".join(entries)) if entries else ""
    except Exception:
        return ""


def call_haiku(repo_path: str, transcript_path: str, group_id: str) -> int:
    """
    Spawn a headless haiku agent that reads the delta and calls memory_add via MCP.
    Returns 1 if the agent ran, 0 if skipped or failed.
    """
    transcript_text = _read_transcript(transcript_path)
    session_log     = _read_session_log(repo_path)

    delta = "\n\n---\n\n".join(filter(None, [session_log, transcript_text]))
    if not delta.strip():
        return 0

    if len(delta) > MAX_DELTA_CHARS:
        delta = delta[-MAX_DELTA_CHARS:]

    prompt = (
        f"{_INSTRUCTIONS}\n\n"
        f"group_id for all memory_add calls: {group_id}\n\n"
        "--- SESSION DELTA ---\n\n"
        f"{delta}"
    )

    try:
        result = subprocess.run(
            ["claude", "--model", HAIKU_MODEL, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=AGENT_TIMEOUT,
            cwd=repo_path,
        )
    except FileNotFoundError:
        print("[mem] 'claude' CLI not found — skipping episodic memory write", flush=True)
        return 0
    except subprocess.TimeoutExpired:
        print("[mem] haiku agent timed out", flush=True)
        return 0
    except Exception as exc:
        print(f"[mem] haiku agent error: {exc}", flush=True)
        return 0

    if result.returncode != 0:
        print(f"[mem] haiku agent exited {result.returncode}: {result.stderr[:200]}", flush=True)
        return 0

    print("[mem] haiku agent done", flush=True)
    return 1
