"""
Install / uninstall the memory plugin for Claude Code.

What gets installed
───────────────────
user scope   → ~/.claude/hooks/market/*.py
               ~/.claude/.mcp.json   (memory server entry merged in)
               ~/.claude/settings.json  (hooks merged in)

project scope → <repo>/.claude/hooks/market/*.py
                <repo>/.mcp.json
                <repo>/.claude/settings.json
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..manifest import record_file, record_json_patch, get_manifest

_PLUGIN_ROOT = Path(__file__).parents[2] / "plugins" / "memory"
_HOOKS_SRC   = _PLUGIN_ROOT / "hooks"
_HOOK_SCRIPTS = [
    "session_start.py",
    "post_tool_use.py",
    "stop.py",
    "subagent_stop.py",
    "session_end.py",
    "_lib.py",
    "_haiku.py",
]

# MEM_HOOKS_DIR is set in the hook command so each script can locate _lib.py
_HOOK_EVENTS = {
    "SessionStart":  "session_start.py",
    "PostToolUse":   "post_tool_use.py",   # matcher: Write|Edit|MultiEdit
    "Stop":          "stop.py",
    "SubagentStop":  "subagent_stop.py",
}


def _claude_dir(scope: str, project_root: str | None) -> Path:
    if scope == "user":
        return Path.home() / ".claude"
    return Path(project_root) / ".claude"


def _hooks_dst(scope: str, project_root: str | None) -> Path:
    return _claude_dir(scope, project_root) / "hooks" / "market"


def install(scope: str, project_root: str | None) -> None:
    hooks_dst = _hooks_dst(scope, project_root)
    hooks_dst.mkdir(parents=True, exist_ok=True)

    # 1. Copy hook scripts
    for script in _HOOK_SCRIPTS:
        src = _HOOKS_SRC / script
        dst = hooks_dst / script
        shutil.copy2(src, dst)
        dst.chmod(0o755)
        record_file(scope, str(src), str(dst), project_root)

    # 2. Merge MCP server entry
    _merge_mcp(scope, project_root, hooks_dst)

    # 3. Merge hook commands into settings.json
    _merge_hooks(scope, project_root, hooks_dst)


def _merge_mcp(scope: str, project_root: str | None, hooks_dst: Path) -> None:
    if scope == "user":
        mcp_path = Path.home() / ".claude" / ".mcp.json"
    else:
        mcp_path = Path(project_root) / ".mcp.json"

    data = json.loads(mcp_path.read_text()) if mcp_path.exists() else {}
    data.setdefault("mcpServers", {})
    entry = {"transport": "sse", "url": "http://127.0.0.1:7333/mcp/sse"}
    data["mcpServers"]["memory"] = entry
    mcp_path.parent.mkdir(parents=True, exist_ok=True)
    mcp_path.write_text(json.dumps(data, indent=2))
    record_json_patch(scope, str(mcp_path), ["mcpServers", "memory"], entry, project_root)


def _merge_hooks(scope: str, project_root: str | None, hooks_dst: Path) -> None:
    if scope == "user":
        settings_path = Path.home() / ".claude" / "settings.json"
    else:
        settings_path = _claude_dir(scope, project_root) / "settings.json"

    data = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    data.setdefault("hooks", {})

    for event, script in _HOOK_EVENTS.items():
        cmd = f"MEM_HOOKS_DIR={hooks_dst} python3 {hooks_dst / script}"
        hook_entry: dict = {"type": "command", "command": cmd}

        if event == "PostToolUse":
            matcher_obj = {"matcher": "Write|Edit|MultiEdit", "hooks": [hook_entry]}
        else:
            matcher_obj = {"hooks": [hook_entry]}

        data["hooks"].setdefault(event, [])
        # Idempotent: don't add duplicates
        existing_cmds = [
            h.get("command", "")
            for obj in data["hooks"][event]
            for h in obj.get("hooks", [])
        ]
        if cmd not in existing_cmds:
            data["hooks"][event].append(matcher_obj)

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2))
    record_json_patch(scope, str(settings_path), ["hooks"], "mem_hooks", project_root)


def uninstall(scope: str, project_root: str | None) -> None:
    manifest = get_manifest(scope, project_root)

    # Remove copied files
    for entry in manifest.get("files", []):
        p = Path(entry["dst"])
        if p.exists():
            p.unlink()

    # Remove JSON patches
    for patch in manifest.get("json_patches", []):
        target = Path(patch["target"])
        if not target.exists():
            continue
        try:
            data = json.loads(target.read_text())
            _remove_key_path(data, patch["key_path"])
            target.write_text(json.dumps(data, indent=2))
        except Exception:
            pass


def _remove_key_path(obj: dict, key_path: list[str]) -> None:
    if len(key_path) == 1:
        obj.pop(key_path[0], None)
        return
    nxt = obj.get(key_path[0])
    if isinstance(nxt, dict):
        _remove_key_path(nxt, key_path[1:])
