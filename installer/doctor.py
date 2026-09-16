"""
`market doctor` — health checks for the memory plugin stack.
Checks: Docker, compose file, stack running, MCP reachable, FalkorDB/Ollama (via MCP).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import httpx

COMPOSE_FILE = Path(__file__).parents[1] / "market-mem" / "docker-compose.yml"


class Check:
    def __init__(self, name: str):
        self.name    = name
        self.ok      = False
        self.detail  = ""

    def __repr__(self):
        icon = "✓" if self.ok else "✗"
        msg  = f"  {icon} {self.name}"
        if self.detail:
            msg += f"  ({self.detail})"
        return msg


def run_checks(mcp_host: str = "127.0.0.1", mcp_port: int = 7333) -> list[Check]:
    checks = []

    def add(name: str, fn) -> Check:
        c = Check(name)
        try:
            ok, detail = fn()
            c.ok, c.detail = ok, detail
        except Exception as e:
            c.detail = str(e)
        checks.append(c)
        return c

    # Docker daemon
    def _docker():
        r = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
        return r.returncode == 0, ""
    c = add("Docker daemon", _docker)

    if not c.ok:
        return checks

    # docker compose available
    def _compose():
        ok = shutil.which("docker") is not None
        r = subprocess.run(["docker", "compose", "version"], capture_output=True, timeout=5)
        return r.returncode == 0, r.stdout.decode().strip()
    add("docker compose", _compose)

    # Compose file exists
    def _file():
        return COMPOSE_FILE.exists(), str(COMPOSE_FILE)
    add("docker-compose.yml present", _file)

    # Stack running
    def _stack():
        r = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "ps", "--services", "--filter", "status=running"],
            capture_output=True, text=True, timeout=10,
        )
        running = r.stdout.strip().splitlines()
        expected = {"falkordb", "mcp"}
        missing  = expected - set(running)
        if missing:
            return False, f"not running: {', '.join(missing)}"
        return True, "falkordb, mcp"
    add("Stack running", _stack)

    # MCP reachable
    def _mcp():
        r = httpx.get(f"https://{mcp_host}:{mcp_port}/health", timeout=5, verify=False)
        return r.status_code == 200, r.json().get("status", "")
    c_mcp = add("MCP server /health", _mcp)

    if not c_mcp.ok:
        return checks

    # Auth — /health is public, /mcp-stats is not. A 401 here means the token
    # the client would send doesn't match the one the server was started with.
    def _auth():
        from .cli import _auth_headers, mem_token
        r = httpx.get(f"https://{mcp_host}:{mcp_port}/mcp-stats", timeout=5,
                      verify=False, headers=_auth_headers())
        if r.status_code == 401:
            return False, ("token rejected — server and client disagree; "
                           "re-run `market install` and restart the stack")
        if r.status_code != 200:
            return False, f"unexpected status {r.status_code}"
        if not mem_token():
            loopback = mcp_host in ("127.0.0.1", "localhost", "::1")
            return loopback, ("no token (loopback-only, ok)" if loopback
                              else "NO TOKEN and reachable off-host")
        return True, "bearer token accepted"
    add("MCP auth", _auth)

    # Phase 5B: report available tree-sitter language parsers
    def _lang_coverage():
        supported = []
        missing   = []
        _tiers = {
            "tree_sitter_rust":    ("rs",    "Tier 1"),
            "tree_sitter_java":    ("java",  "Tier 1"),
            "tree_sitter_c":       ("c",     "Tier 1"),
            "tree_sitter_cpp":     ("cpp",   "Tier 1"),
            "tree_sitter_c_sharp": ("cs",    "Tier 1"),
            "tree_sitter_ruby":    ("rb",    "Tier 2"),
            "tree_sitter_php":     ("php",   "Tier 2"),
            "tree_sitter_kotlin":  ("kt",    "Tier 2"),
            "tree_sitter_swift":   ("swift", "Tier 2"),
            "tree_sitter_scala":   ("scala", "Tier 2"),
            "tree_sitter_bash":    ("sh",    "Tier 3"),
            "tree_sitter_lua":     ("lua",   "Tier 3"),
            "tree_sitter_haskell": ("hs",    "Tier 3"),
            "tree_sitter_elixir":  ("ex",    "Tier 3"),
        }
        import importlib
        for mod, (ext, tier) in _tiers.items():
            try:
                importlib.import_module(mod)
                supported.append(f".{ext}({tier})")
            except ImportError:
                missing.append(f".{ext}({tier})")
        detail = f"{len(supported)} installed"
        if missing:
            detail += f"; missing: {', '.join(missing)}"
        return len(missing) == 0, detail
    add("Language parsers (Phase 5B)", _lang_coverage)

    return checks
