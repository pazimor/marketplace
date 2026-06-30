"""
Codex install target (Phase 4).

Codex has no hooks model — install = MCP server entry in config + AGENTS.md snippet.
Manual ingest via `market ingest` is required (no automatic SessionStart hook).

Config location: ~/.codex/config.toml  (user scope)
                 <repo>/.codex/config.toml  (project scope — if Codex supports it)

AGENTS.md: prepended/updated in <repo>/AGENTS.md (project scope)
           or skipped for user scope (no meaningful location).
"""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from ..manifest import record_file, record_json_patch, get_manifest

_MCP_SERVER_URL  = "http://127.0.0.1:7333/mcp/sse"
_MCP_SERVER_NAME = "memory"

_AGENTS_MD_SECTION = """\
<!-- market-plugin:start -->
## Memory & Code Search (market plugin)

This project uses a local memory MCP server.  Use these tools before starting work:

| Tool | Description |
|---|---|
| `code_search(query, group_id, k)` | Semantic search over indexed codebase |
| `code_fetch(group_id, path, symbol)` | Fetch exact source of a function |
| `memory_search(query, group_id)` | Search past decisions and facts |
| `memory_query(query, group_id, symbol)` | Facts anchored to a code symbol |
| `impact_of(symbol, group_id, depth)` | Symbols affected by changes to symbol |
| `callers_of(symbol, group_id, depth)` | Who calls this symbol? |
| `imports_of(file, group_id)` | Files imported by a file |

**group_id**: run `market status --repo-path .` to get your project's group_id.

**First-time setup**: run `market ingest --repo-path .` to index the codebase.
(Claude Code users: this happens automatically at session start.)
<!-- market-plugin:end -->
"""


# ---------------------------------------------------------------------------
# TOML helpers (stdlib tomllib is read-only — we write manually)
# ---------------------------------------------------------------------------

def _read_toml(path: Path) -> dict:
    if path.exists():
        with path.open("rb") as f:
            return tomllib.load(f)
    return {}


def _toml_set_mcp_entry(path: Path, server_name: str, url: str) -> None:
    """Add or replace [mcp_servers.<server_name>] section in a TOML file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = path.read_text(encoding="utf-8") if path.exists() else ""

    # Remove any existing block for this server (between matching headers)
    pattern = re.compile(
        rf"\[mcp_servers\.{re.escape(server_name)}\][^\[]*",
        re.DOTALL,
    )
    cleaned = pattern.sub("", existing).rstrip()

    new_block = (
        f'\n[mcp_servers.{server_name}]\n'
        f'transport = "sse"\n'
        f'url = "{url}"\n'
    )
    path.write_text(cleaned + new_block, encoding="utf-8")


def _toml_remove_mcp_entry(path: Path, server_name: str) -> None:
    if not path.exists():
        return
    existing = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"\[mcp_servers\.{re.escape(server_name)}\][^\[]*",
        re.DOTALL,
    )
    cleaned = pattern.sub("", existing).rstrip()
    path.write_text(cleaned + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# AGENTS.md helpers
# ---------------------------------------------------------------------------

_AGENTS_START = "<!-- market-plugin:start -->"
_AGENTS_END   = "<!-- market-plugin:end -->"


def _upsert_agents_md(agents_path: Path) -> None:
    """Insert or replace the market-plugin section in AGENTS.md."""
    agents_path.parent.mkdir(parents=True, exist_ok=True)
    existing = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""

    if _AGENTS_START in existing:
        # Replace existing section
        pattern = re.compile(
            re.escape(_AGENTS_START) + r".*?" + re.escape(_AGENTS_END),
            re.DOTALL,
        )
        new_content = pattern.sub(_AGENTS_MD_SECTION.strip(), existing)
    else:
        # Prepend
        new_content = _AGENTS_MD_SECTION + "\n" + existing

    agents_path.write_text(new_content, encoding="utf-8")


def _remove_agents_md_section(agents_path: Path) -> None:
    if not agents_path.exists():
        return
    content = agents_path.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(_AGENTS_START) + r".*?" + re.escape(_AGENTS_END) + r"\n?",
        re.DOTALL,
    )
    cleaned = pattern.sub("", content)
    agents_path.write_text(cleaned, encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _config_path(scope: str, project_root: str | None) -> Path:
    if scope == "user":
        return Path.home() / ".codex" / "config.toml"
    return Path(project_root) / ".codex" / "config.toml"


def install(scope: str, project_root: str | None) -> None:
    config_path = _config_path(scope, project_root)
    _toml_set_mcp_entry(config_path, _MCP_SERVER_NAME, _MCP_SERVER_URL)
    record_json_patch(
        scope,
        str(config_path),
        ["mcp_servers", _MCP_SERVER_NAME],
        {"transport": "sse", "url": _MCP_SERVER_URL},
        project_root,
    )

    # AGENTS.md only makes sense at project scope
    if scope == "project" and project_root:
        agents_path = Path(project_root) / "AGENTS.md"
        _upsert_agents_md(agents_path)
        record_file(scope, str(agents_path), str(agents_path), project_root)


def uninstall(scope: str, project_root: str | None) -> None:
    config_path = _config_path(scope, project_root)
    _toml_remove_mcp_entry(config_path, _MCP_SERVER_NAME)

    if scope == "project" and project_root:
        agents_path = Path(project_root) / "AGENTS.md"
        _remove_agents_md_section(agents_path)
