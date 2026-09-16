"""
Install / uninstall marketplace plugins for Claude Code.

Canonical install path — drives the NATIVE plugin system (so plugins show
up under "Personal plugins") instead of hand-patching settings.json:

  1. register the local marketplace   (claude plugin marketplace add <repo>)
  2. install the selected plugins      (claude plugin install <name>@marketplace)
     → hooks (hooks/hooks.json), skills (skills/*/SKILL.md) and MCP (.mcp.json)
       are auto-discovered by Claude Code
  3. configure the Claude Desktop bridge (claude_desktop_config.json, mcp-remote)

No hooks are copied and settings.json is never touched, so install/uninstall is
fully reversible and idempotent — no duplicate hooks, no leftover MCP entries.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from ..manifest import record_json_patch, get_manifest

_REPO_ROOT       = Path(__file__).parents[2]
_MARKETPLACE     = "marketplace"            # marketplace.json "name"
_MCP_URL         = "https://127.0.0.1:7333/mcp/sse"
_DESKTOP_CONFIG  = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
# Desktop bridge entry name — the shared MCP server, exposed by the memory plugin.
_BRIDGE_NAME     = "memory"


def available_plugins() -> list[str]:
    """Plugin names declared in .claude-plugin/marketplace.json."""
    catalogue = json.loads(
        (_REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text()
    )
    return [p["name"] for p in catalogue.get("plugins", [])]


def _claude(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["claude", *args], capture_output=True, text=True)


def _caroot() -> str:
    r = subprocess.run(["mkcert", "-CAROOT"], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        return str(Path(r.stdout.strip()) / "rootCA.pem")
    return str(Path.home() / "Library" / "Application Support" / "mkcert" / "rootCA.pem")


_MARKET_SETTINGS = Path.home() / ".config" / "market" / "settings.json"


def _mem_token() -> str:
    """Shared secret for the MCP server: MEM_TOKEN env, else installer settings.

    Mirrors hooks/_lib.mem_token() — the Desktop bridge needs the same token the
    server enforces, otherwise every bridge request is rejected with 401."""
    tok = os.getenv("MEM_TOKEN", "")
    if tok:
        return tok
    try:
        return str(json.loads(_MARKET_SETTINGS.read_text()).get("token") or "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

def install(scope: str, project_root: str | None, plugins: list[str] | None = None) -> None:
    plugins = plugins or ["memory"]

    # 1. Register the local marketplace (idempotent: update if already added).
    add = _claude("plugin", "marketplace", "add", str(_REPO_ROOT))
    if add.returncode != 0:
        upd = _claude("plugin", "marketplace", "update", _MARKETPLACE)
        if upd.returncode != 0:
            raise RuntimeError(
                f"marketplace add/update failed: {add.stderr.strip() or upd.stderr.strip()}"
            )

    # 2. Install each plugin (idempotent: reinstall to pick up manifest changes).
    installed = _installed_plugins()
    for name in plugins:
        plugin_id = f"{name}@{_MARKETPLACE}"
        if plugin_id in installed:
            _claude("plugin", "uninstall", plugin_id)
        inst = _claude("plugin", "install", plugin_id)
        if inst.returncode != 0:
            raise RuntimeError(f"plugin install failed ({name}): {inst.stderr.strip()}")

    # 3. Configure the Claude Desktop bridge (local server → mcp-remote over TLS).
    _configure_desktop_bridge(scope, project_root)


def _installed_plugins() -> str:
    r = _claude("plugin", "list")
    return r.stdout


_CC_SETTINGS = Path.home() / ".claude" / "settings.json"


def configure_env(scope: str, project_root: str | None, env: dict[str, str]) -> None:
    """Publish MEM_* into Claude Code's environment via settings.json `env`.

    The plugin's .mcp.json expands ${MEM_HOST} / ${MEM_TOKEN}, and the hooks read
    the same variables — but neither can reach into ~/.config/market. Without
    this, every session would need the variables exported by hand.

    Each key is recorded as a reversible JSON patch, so uninstall removes it and
    nothing is left behind; this is the same mechanism as the Desktop bridge.
    """
    if not env:
        return
    _CC_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(_CC_SETTINGS.read_text()) if _CC_SETTINGS.exists() else {}
    data.setdefault("env", {})
    for key, value in env.items():
        data["env"][key] = value
        record_json_patch(scope, str(_CC_SETTINGS), ["env", key], value, project_root)
    _CC_SETTINGS.write_text(json.dumps(data, indent=2))


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
    token = _mem_token()
    if token:
        # The server requires `Authorization: Bearer <token>` on /mcp/sse as
        # soon as MEM_TOKEN is set. mcp-remote interpolates ${VAR} from its
        # env inside --header values — the value must not contain a space at
        # the CLI level (Desktop's arg parsing splits on spaces), hence the
        # env-var indirection.
        entry["args"] += ["--header", "Authorization:${MEM_AUTH_HEADER}"]
        entry["env"]["MEM_AUTH_HEADER"] = f"Bearer {token}"
    data["mcpServers"][_BRIDGE_NAME] = entry
    _DESKTOP_CONFIG.write_text(json.dumps(data, indent=2))
    record_json_patch(scope, str(_DESKTOP_CONFIG), ["mcpServers", _BRIDGE_NAME], entry, project_root)


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------

def uninstall(scope: str, project_root: str | None, plugins: list[str] | None = None) -> None:
    names = plugins or available_plugins()
    installed = _installed_plugins()
    for name in names:
        plugin_id = f"{name}@{_MARKETPLACE}"
        if plugin_id in installed:
            _claude("plugin", "uninstall", plugin_id)
    # Drop the marketplace registration only on a full uninstall.
    if plugins is None:
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