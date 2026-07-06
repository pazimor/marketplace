"""
Unit tests for the transcript distiller — fully offline.

The `claude` CLI is replaced by a stub shell script prepended to PATH, and the
MCP server by monkeypatched _lib.mcp_get / mcp_post. No Docker, no tokens:
this is the mocked e2e of the extractor → arbiter pipeline.
"""
from __future__ import annotations

import json
import os
import stat
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _distill
import _lib


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _write_transcript(path: Path, turns: list[tuple[str, str]], pad: bool = True) -> None:
    lines = [json.dumps({"message": {"role": r, "content": c}}) for r, c in turns]
    if pad:  # clear the MIN_TRANSCRIPT_BYTES gate
        lines += [json.dumps({"type": "system", "content": "x" * 200})] * 20
    path.write_text("\n".join(lines))


@pytest.fixture()
def fake_claude(tmp_path, monkeypatch):
    """Stub `claude` binary: extractor prompts get a JSON candidate list,
    arbiter prompts (recognised by 'CANDIDATE FACTS') get a FACTS_WRITTEN line.
    Every invocation is appended to calls.log."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls_log = tmp_path / "calls.log"
    calls_log.touch()
    script = bin_dir / "claude"
    script.write_text(f"""#!/bin/sh
echo "$2" >> "{calls_log}"
case "$4" in
  *"CANDIDATE FACTS"*)
    echo "arbitrated."
    echo "FACTS_WRITTEN: 2"
    ;;
  *)
    echo '[{{"content": "the API uses cursor pagination", "kind": "episodic", "type": "fact", "anchor": ""}}]'
    ;;
esac
""")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    return calls_log


@pytest.fixture()
def fake_mcp(monkeypatch):
    """In-memory MCP: healthy server, ledger recorded via /sessions/processed."""
    state = {"ledger": [], "posts": []}

    def _get(path, timeout=5.0):
        if path == "/health":
            return {"status": "ok"}
        if path.startswith("/sessions/"):
            return {"sessions": state["ledger"],
                    "ids": [e["session_id"] for e in state["ledger"]]}
        return None

    def _post(path, body, timeout=10.0):
        state["posts"].append((path, body))
        if path == "/sessions/processed":
            state["ledger"].append(body)
        return {"status": "ok"}

    monkeypatch.setattr(_distill, "mcp_get", _get)
    monkeypatch.setattr(_distill, "mcp_post", _post)
    return state


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_condense_transcript(tmp_path):
    t = tmp_path / "s1.jsonl"
    _write_transcript(t, [("user", "fix the login bug"),
                          ("assistant", "found it: the token was expired")], pad=False)
    out = _distill.condense_transcript(t)
    assert "[user]: fix the login bug" in out
    assert "[assistant]: found it: the token was expired" in out


def test_parse_candidates():
    ok = _distill.parse_candidates('noise before [{"content": "a fact"}] after')
    assert ok == [{"content": "a fact"}]
    assert _distill.parse_candidates("[]") == []
    assert _distill.parse_candidates("no json here") is None
    assert _distill.parse_candidates('{"content": "not a list"}') is None
    # entries without content are dropped
    assert _distill.parse_candidates('[{"kind": "episodic"}]') == []


def test_parse_facts_written():
    assert _distill.parse_facts_written("blah\nFACTS_WRITTEN: 3\n") == 3
    assert _distill.parse_facts_written("no counter") == 0


def test_pending_transcripts_filters_and_caps(tmp_path, fake_mcp):
    for i in range(6):
        t = tmp_path / f"s{i}.jsonl"
        t.write_text("x")
        os.utime(t, (time.time() - i, time.time() - i))  # s0 newest
    fake_mcp["ledger"].append({"session_id": "s1", "status": "done"})
    fake_mcp["ledger"].append({"session_id": "s2", "status": "failed"})  # retryable

    todo, skip = _distill.pending_transcripts(tmp_path, "gid", exclude="s0")
    # s0 excluded (current session), s1 final; s2 retried; newest-first cap at 3
    assert [p.stem for p in todo] == ["s2", "s3", "s4"]
    assert [p.stem for p in skip] == ["s5"]


# ---------------------------------------------------------------------------
# Mocked e2e
# ---------------------------------------------------------------------------

def test_distill_all_end_to_end(tmp_path, fake_claude, fake_mcp):
    tdir = tmp_path / "transcripts"
    tdir.mkdir()
    _write_transcript(tdir / "old-session.jsonl",
                      [("user", "always run ruff before committing"),
                       ("assistant", "noted, running ruff")])

    total = _distill.distill_all(str(tmp_path), str(tdir), exclude_session="current")

    assert total == 2  # FACTS_WRITTEN by the stub arbiter
    # exactly two invocations: extractor then arbiter
    calls = fake_claude.read_text().splitlines()
    assert calls == [_distill.EXTRACTOR_MODEL, _distill.ARBITER_MODEL]

    ledger = {e["session_id"]: e for e in fake_mcp["ledger"]}
    assert ledger["old-session"]["status"] == "done"
    assert ledger["old-session"]["facts_written"] == 2

    # idempotence: a second run finds nothing to do
    fake_claude.write_text("")
    assert _distill.distill_all(str(tmp_path), str(tdir), "current") == 0
    assert fake_claude.read_text() == ""


def test_distill_all_empty_transcript(tmp_path, fake_claude, fake_mcp):
    tdir = tmp_path / "transcripts"
    tdir.mkdir()
    (tdir / "tiny.jsonl").write_text("{}")  # under MIN_TRANSCRIPT_BYTES

    assert _distill.distill_all(str(tmp_path), str(tdir), "current") == 0
    ledger = {e["session_id"]: e for e in fake_mcp["ledger"]}
    assert ledger["tiny"]["status"] == "empty"
    assert fake_claude.read_text() == ""  # no LLM call at all


def test_distill_postponed_when_server_down(tmp_path, monkeypatch):
    monkeypatch.setattr(_distill, "mcp_get", lambda *a, **k: None)
    tdir = tmp_path / "transcripts"
    tdir.mkdir()
    (tdir / "s.jsonl").write_text("x" * 5000)
    assert _distill.distill_all(str(tmp_path), str(tdir), "current") == 0


# ---------------------------------------------------------------------------
# Sync-mode flag
# ---------------------------------------------------------------------------

def test_distill_sync_flag(monkeypatch):
    monkeypatch.delenv("MEM_DISTILL_SYNC", raising=False)
    monkeypatch.setattr(_lib, "market_settings", lambda: {})
    assert _lib.distill_sync_enabled() is False

    monkeypatch.setattr(_lib, "market_settings", lambda: {"distill_sync": True})
    assert _lib.distill_sync_enabled() is True

    # env var wins over settings.json, in both directions
    monkeypatch.setenv("MEM_DISTILL_SYNC", "0")
    assert _lib.distill_sync_enabled() is False
    monkeypatch.setenv("MEM_DISTILL_SYNC", "1")
    monkeypatch.setattr(_lib, "market_settings", lambda: {})
    assert _lib.distill_sync_enabled() is True
