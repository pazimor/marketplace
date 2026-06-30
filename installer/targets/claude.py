"""
Install / uninstall the memory plugin for Claude Code.

Canonical install path — drives the NATIVE plugin system (so the plugin shows
up under "Personal plugins") instead of hand-patching settings.json:

  1. register the local marketplace   (claude plugin marketplace add <repo>)
  2. install the memory plugin         (claude plugin install memory@marketplace)
     → hooks (hooks/hooks.json) and MCP (.mcp.json) are auto-discovered by Claude
  3. configure the Claude Desktop bridge (claude_desktop_config.json, mcp-remote)

No hooks are copied and settings.json is never touched, so install/uninstall is
fully reversible and idempotent — no duplicate hooks, no leftover MCP entries.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..manifest import record_json_patch, get_manifest

_REPO_ROOT       = Path(__file__).parents[2]
_MARKETPLACE     = "marketplace"            # marketplace.json "name"
_PLUGIN          = "memory"                 # plugin.json "name"
_PLUGIN_ID       = f"{_PLUGIN}@{_MARKETPLACE}"
_MCP_URL         = "https://127.0.0.1:7333/mcp/sse"
_DESKTOP_CONFIG  = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"


def _claude(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["claude", *args], capture_output=True, text=True)


def _caroot() -> str:
    r = subprocess.run(["mkcert", "-CAROOT"], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        return str(Path(r.stdout.strip()) / "rootCA.pem")
    return str(Path.home() / "Library" / "Application Support" / "mkcert" / "rootCA.pem")


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

def install(scope: str, project_root: str | None) -> None:
    # 1. Register the local marketplace (idempotent: update if already added).
    add = _claude("plugin", "marketplace", "add", str(_REPO_ROOT))
    if add.returncode != 0:
        upd = _claude("plugin", "marketplace", "update", _MARKETPLACE)
        if upd.returncode != 0:
            raise RuntimeError(
                f"marketplace add/update failed: {add.stderr.strip() or upd.stderr.strip()}"
            )

    # 2. Install the plugin (idempotent: reinstall to pick up manifest changes).
    if _is_installed():
        _claude("plugin", "uninstall", _PLUGIN_ID)
    inst = _claude("plugin", "install", _PLUGIN_ID)
    if inst.returncode != 0:
        raise RuntimeError(f"plugin install failed: {inst.stderr.strip()}")

    # 3. Configure the Claude Desktop bridge (local server → mcp-remote over TLS).
    _configure_desktop_bridge(scope, project_root)


def _is_installed() -> bool:
    r = _claude("plugin", "list")
    return _PLUGIN_ID in r.stdout


def _configure_desktop_bridge(scope: str, project_root: str | None) -> None:
    if not _DESKTOP_CONFIG.parent.exists():
        return  # Claude Desktop not installed on this machine — skip silently.

    data = json.loads(_DESKTOP_CONFIG.read_text()) if _DESKTOP_CONFIG.exists() else {}
    data.setdefault("mcpServers", {})
    entry = {
        "command": "npx",
        "args": ["mcp-remote", _MCP_URL],
        "env": {"NODE_EXTRA_CA_CERTS": _caroot()},
    }
    data["mcpServers"][_PLUGIN] = entry
    _DESKTOP_CONFIG.write_text(json.dumps(data, indent=2))
    record_json_patch(scope, str(_DESKTOP_CONFIG), ["mcpServers", _PLUGIN], entry, project_root)


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------

def uninstall(scope: str, project_root: str | None) -> None:
    if _is_installed():
        _claude("plugin", "uninstall", _PLUGIN_ID)
    _claude("plugin", "marketplace", "remove", _MARKETPLACE)

    # Remove recorded JSON patches (e.g. the Desktop bridge entry).
    manifest = get_manifest(scope, project_root)
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
