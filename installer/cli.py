"""
market — marketplace installer CLI.

Commands
────────
market install   [PLUGINS]...  --scope user|project  [--project-root PATH]
                 PLUGINS: plugin folder names (e.g. `roadmap`), `full` for everything,
                 or nothing for the MCP core only (memory plugin + Docker stack).
                 The MCP stack is always deployed.
market uninstall [PLUGINS]...  --scope user|project  [--project-root PATH]
market status
market doctor
market ingest    --repo-path PATH  (manual trigger, useful for first-time setup)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click
import httpx

_COMPOSE_FILE = Path(__file__).parents[1] / "market-mem" / "docker-compose.yml"
_ENV_FILE     = Path(__file__).parents[1] / "market-mem" / ".env"
_PLUGIN_ROOT  = Path(__file__).parents[1] / "plugins" / "memory"
_CERTS_DIR    = _COMPOSE_FILE.parent / "certs"

# Read by the plugin hooks (_lib.compose_file) — the native plugin install
# copies hooks under ~/.claude/plugins/, so they can't rely on repo-relative
# paths to find the Docker stack.
_COMPOSE_POINTER = Path.home() / ".config" / "market" / "compose_path"


def _write_compose_pointer() -> None:
    _COMPOSE_POINTER.parent.mkdir(parents=True, exist_ok=True)
    _COMPOSE_POINTER.write_text(str(_COMPOSE_FILE.resolve()) + "\n")


_SETTINGS_FILE = Path.home() / ".config" / "market" / "settings.json"
_LOOPBACK_SANS = ["127.0.0.1", "localhost", "::1"]


def _cert_sans() -> set[str]:
    """SANs already present in the installed server cert."""
    crt = _CERTS_DIR / "server.crt"
    if not crt.exists():
        return set()
    r = subprocess.run(
        ["openssl", "x509", "-in", str(crt), "-noout", "-ext", "subjectAltName"],
        capture_output=True, text=True,
    )
    sans: set[str] = set()
    for part in r.stdout.replace("\n", ",").split(","):
        part = part.strip()
        for prefix in ("DNS:", "IP Address:"):
            if part.startswith(prefix):
                sans.add(part[len(prefix):].strip())
    return sans


def _setup_tls(extra_hosts: list[str] | None = None) -> None:
    """Install a locally-trusted CA (mkcert) and generate the server cert.

    The MCP server serves https; mkcert's CA must be trusted so the Claude Code
    native client connects without warnings. `mkcert -install` may prompt for
    the macOS password — that's expected and only needed once per machine.

    *extra_hosts* are added as SANs so remote machines can verify the cert when
    the port is published off-loopback. The cert is regenerated whenever a
    requested SAN is missing from the existing one.
    """
    import shutil

    if shutil.which("mkcert") is None:
        click.echo("  ✗ mkcert not found — install it first:  brew install mkcert", err=True)
        click.echo("    (TLS setup skipped; the https server will start but the cert won't be trusted)", err=True)
        return

    # Install the local CA into the system trust store (idempotent).
    r = subprocess.run(["mkcert", "-install"], capture_output=True, text=True)
    if r.returncode != 0:
        click.echo("  ! mkcert -install needs your password; run it once manually:  mkcert -install", err=True)
    else:
        click.echo("  ✓ local CA trusted")

    wanted = _LOOPBACK_SANS + [h for h in (extra_hosts or []) if h not in _LOOPBACK_SANS]

    crt = _CERTS_DIR / "server.crt"
    key = _CERTS_DIR / "server.key"
    if crt.exists() and key.exists():
        missing = {h for h in wanted if h != "::1"} - _cert_sans()
        if not missing:
            click.echo("  ✓ server cert present")
            _export_ca()
            return
        click.echo(f"  → regenerating cert, missing SANs: {', '.join(sorted(missing))}")

    _CERTS_DIR.mkdir(parents=True, exist_ok=True)
    g = subprocess.run(
        ["mkcert", "-cert-file", str(crt), "-key-file", str(key), *wanted],
        capture_output=True, text=True,
    )
    if g.returncode == 0:
        click.echo(f"  ✓ server cert generated for: {', '.join(wanted)}")
        _export_ca()
    else:
        click.echo(f"  ✗ cert generation failed: {g.stderr.strip()}", err=True)


def _export_ca() -> None:
    """Copy the mkcert root CA to ~/.config/market/ca.pem.

    The hooks use httpx, which reads the certifi bundle and not the system
    trust store — so verifying a remote MCP server needs the CA as a file.
    This is also the file to copy onto remote machines."""
    r = subprocess.run(["mkcert", "-CAROOT"], capture_output=True, text=True)
    if r.returncode != 0:
        return
    root = Path(r.stdout.strip()) / "rootCA.pem"
    if not root.exists():
        return
    dest = Path.home() / ".config" / "market" / "ca.pem"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(root.read_bytes())
    click.echo(f"  ✓ CA exported to {dest}")


def _read_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def _set_env_var(key: str, value: str) -> None:
    """Upsert KEY=value in market-mem/.env, preserving comments and order."""
    lines = _ENV_FILE.read_text().splitlines() if _ENV_FILE.exists() else []
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    _ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ENV_FILE.write_text("\n".join(lines) + "\n")


def mem_token() -> str:
    """The shared secret, from env → .env file → settings.json."""
    return (
        os.getenv("MEM_TOKEN")
        or _read_env().get("MEM_TOKEN", "")
        or str(_load_settings().get("token") or "")
    )


def _load_settings() -> dict:
    try:
        import json
        return json.loads(_SETTINGS_FILE.read_text())
    except Exception:
        return {}


def _auth_headers() -> dict:
    tok = mem_token()
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def _ensure_token() -> str:
    """Generate the shared secret once and store it in both places it's read from:
    market-mem/.env (server side, via docker compose) and
    ~/.config/market/settings.json (client side, hooks + .mcp.json)."""
    import json
    import secrets

    tok = mem_token()
    if not tok:
        tok = secrets.token_hex(32)
        click.echo("  ✓ generated a new shared token")

    _set_env_var("MEM_TOKEN", tok)

    settings = _load_settings()
    if settings.get("token") != tok:
        settings["token"] = tok
        _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_FILE.write_text(json.dumps(settings, indent=2) + "\n")
        # Secret at rest — keep it out of other users' reach.
        _SETTINGS_FILE.chmod(0o600)
    click.echo(f"  ✓ token stored in {_ENV_FILE.name} and {_SETTINGS_FILE}")
    return tok


def _compose(*args, **kwargs):
    env_args = ["--env-file", str(_ENV_FILE)] if _ENV_FILE.exists() else []
    return subprocess.run(
        ["docker", "compose", "-f", str(_COMPOSE_FILE)] + env_args + list(args),
        **kwargs,
    )


def _mcp_url(path: str = "") -> str:
    env = _read_env()
    host = os.getenv("MEM_HOST") or env.get("MEM_HOST") or "127.0.0.1"
    port = os.getenv("MEM_PORT") or env.get("MEM_PORT") or "7333"
    return f"https://{host}:{port}{path}"


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------

@click.group()
def main():
    """market — memory marketplace installer for Claude Code."""


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

def _resolve_plugins(plugins: tuple[str, ...]) -> list[str]:
    """Resolve the plugin selection: names, `full`, or default (MCP core only).

    The memory plugin IS the MCP (hooks + .mcp.json) — it is always included,
    so the MCP is deployed by default whatever the selection.
    """
    from .targets.claude import available_plugins

    catalogue = available_plugins()
    if not plugins:
        selected = ["memory"]
    elif "full" in plugins:
        selected = list(catalogue)
    else:
        unknown = [p for p in plugins if p not in catalogue]
        if unknown:
            raise click.BadParameter(
                f"unknown plugin(s): {', '.join(unknown)} — available: {', '.join(catalogue)} (or `full`)"
            )
        selected = list(plugins)
    if "memory" not in selected:
        selected.insert(0, "memory")
    return selected


@main.command()
@click.argument("plugins", nargs=-1)
@click.option("--scope",  type=click.Choice(["user", "project"]), default="user", show_default=True)
@click.option("--project-root", default=None, help="Repo root for --scope project (defaults to cwd).")
@click.option("--expose", is_flag=True,
              help="Publish the MCP port on the network so other machines can reach it. "
                   "Requires token auth (generated automatically) and puts this machine's "
                   "LAN address in the TLS cert.")
@click.option("--bind", default=None, metavar="ADDR",
              help="Explicit publish address (advanced). Note that binding a single LAN IP "
                   "makes the port unreachable on 127.0.0.1, breaking this machine's own "
                   "hooks — prefer --expose.")
@click.option("--san", "sans", multiple=True, metavar="HOST",
              help="Extra hostname/IP to put in the TLS cert (repeatable).")
@click.option("--client-only", is_flag=True,
              help="Install against a remote MCP server: no Docker stack, no TLS setup. "
                   "Requires MEM_HOST and MEM_TOKEN in the environment.")
def install(plugins: tuple[str, ...], scope: str, project_root: str | None,
            expose: bool, bind: str | None, sans: tuple[str, ...], client_only: bool):
    """Install marketplace plugins (PLUGINS: names, `full`, or empty for MCP core only)."""
    project_root = project_root or os.getcwd()
    if client_only:
        _install_client_only(scope, project_root, _resolve_plugins(plugins))
        return
    selected = _resolve_plugins(plugins)
    click.echo(f"Plugins: {', '.join(selected)}")

    click.echo(f"Installing for Claude Code ({scope} scope)…")
    try:
        from .targets.claude import install as _install
        _install(scope, project_root if scope == "project" else None, selected)
        click.echo("  ✓ done")
    except Exception as e:
        click.echo(f"  ✗ {e}", err=True)
        sys.exit(1)

    # Tell the installed hooks where the Docker stack lives.
    _write_compose_pointer()

    # Bind address: loopback by default. Anything else exposes the server to
    # the network, so the server requires a token in that case (it refuses to
    # start otherwise) — generate one here either way.
    lan = _lan_address()
    if expose:
        # 0.0.0.0 rather than the LAN IP alone: the port must stay reachable on
        # 127.0.0.1, since this machine runs a Claude Code client too.
        _set_env_var("MEM_HOST", "0.0.0.0")
        click.echo(f"Publishing the MCP port on all interfaces (LAN address: {lan or 'unknown'})")
    elif bind:
        _set_env_var("MEM_HOST", bind)
        click.echo(f"Publishing the MCP port on {bind}")
        if bind not in _LOOPBACK_SANS + ["0.0.0.0"]:
            click.echo("  ! this machine's own hooks default to 127.0.0.1 and will no longer "
                       "reach the server; set MEM_HOST here too, or use --expose", err=True)

    click.echo("Setting up auth…")
    token = _ensure_token()

    # Set up TLS (mkcert CA + server cert) before starting the stack.
    click.echo("Setting up TLS (mkcert)…")
    extra = list(sans)
    if expose:
        extra += [h for h in (lan, _hostname()) if h]
    elif bind and bind != "0.0.0.0":
        extra.append(bind)
    _setup_tls(extra)

    # The MCP transport rejects Host headers it doesn't know (DNS-rebinding
    # protection), so the addresses remote clients dial must be declared too.
    if extra:
        _set_env_var("MEM_ALLOWED_HOSTS", ",".join(dict.fromkeys(extra)))

    # Publish the token to Claude Code, so .mcp.json and the hooks pick it up
    # without the user exporting anything by hand.
    _publish_env(scope, project_root, {"MEM_TOKEN": token})

    # Start Docker stack
    click.echo("Starting Docker stack…")
    r = _compose("up", "-d", "--remove-orphans", capture_output=True)
    if r.returncode != 0:
        click.echo("  ✗ docker compose up failed — run `market doctor` for details", err=True)
    else:
        click.echo("  ✓ stack up")

    click.echo("\nInstallation complete.  Restart Claude Code to activate hooks.")
    if expose or bind:
        _remote_setup_hint(lan or bind or "0.0.0.0")


def _publish_env(scope: str, project_root: str, env: dict[str, str]) -> None:
    """Make MEM_* visible to Claude Code (.mcp.json expansion + hooks).

    NODE_EXTRA_CA_CERTS goes along with it: the MCP client runs on Node, which
    ignores the system trust store, so the mkcert CA has to be pointed at
    explicitly or the TLS handshake fails."""
    from .targets.claude import _caroot, configure_env

    env = dict(env)
    ca = Path.home() / ".config" / "market" / "ca.pem"
    env.setdefault("NODE_EXTRA_CA_CERTS", str(ca) if ca.exists() else _caroot())
    try:
        configure_env(scope, project_root if scope == "project" else None, env)
        click.echo(f"  ✓ {', '.join(env)} published to Claude Code settings")
    except Exception as e:
        click.echo(f"  ! could not update Claude Code settings: {e}", err=True)
        click.echo("    Export these in your shell instead:", err=True)
        for k, v in env.items():
            click.echo(f"      export {k}={v}", err=True)


def _install_client_only(scope: str, project_root: str, selected: list[str]) -> None:
    """Install the plugins pointed at an MCP server running on another machine.

    Nothing is started locally: no Docker stack, no cert generation. The host
    and token come from the environment and are persisted to settings.json so
    the hooks find them in future shells."""
    import json

    host = os.getenv("MEM_HOST", "")
    token = os.getenv("MEM_TOKEN", "")
    ca = Path.home() / ".config" / "market" / "ca.pem"

    missing = [n for n, v in (("MEM_HOST", host), ("MEM_TOKEN", token)) if not v]
    if missing:
        click.echo(f"✗ --client-only needs {' and '.join(missing)} in the environment.", err=True)
        click.echo("  Get both from the server machine's `market install --expose` output.", err=True)
        sys.exit(1)
    if host in _LOOPBACK_SANS:
        click.echo(f"✗ MEM_HOST is {host} — that's this machine, not a remote server.", err=True)
        sys.exit(1)
    if not ca.exists():
        click.echo(f"! {ca} is missing — copy it from the server machine, otherwise the", err=True)
        click.echo("  hooks cannot verify the server's certificate and will fail.", err=True)

    click.echo(f"Client-only install against {host}:{os.getenv('MEM_PORT', '7333')}")
    try:
        from .targets.claude import install as _install
        _install(scope, project_root if scope == "project" else None, selected)
        click.echo("  ✓ plugins installed")
    except Exception as e:
        click.echo(f"  ✗ {e}", err=True)
        sys.exit(1)

    settings = _load_settings()
    settings["token"] = token
    settings["host"] = host
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_FILE.write_text(json.dumps(settings, indent=2) + "\n")
    _SETTINGS_FILE.chmod(0o600)
    click.echo(f"  ✓ server address and token saved to {_SETTINGS_FILE}")

    _publish_env(scope, project_root, {"MEM_HOST": host, "MEM_TOKEN": token})

    # Reachability check — a clear failure here beats a silent no-op at SessionStart.
    try:
        r = httpx.get(_mcp_url("/mcp-stats"), timeout=6,
                      verify=str(ca) if ca.exists() else True,
                      headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 200:
            click.echo("  ✓ server reachable and token accepted")
        elif r.status_code == 401:
            click.echo("  ✗ server reachable but token rejected", err=True)
        else:
            click.echo(f"  ✗ unexpected status {r.status_code}", err=True)
    except Exception as e:
        click.echo(f"  ✗ cannot reach the server: {e}", err=True)

    click.echo("\nInstallation complete.  Restart Claude Code to activate hooks.")
    click.echo("Note: code indexing stays on the server machine — code_search covers")
    click.echo("what the server can see. Memory and roadmap tools work fully from here.")


def _lan_address() -> str | None:
    """This machine's primary LAN IPv4, for the cert SANs and the setup hint."""
    import socket
    for iface in ("en0", "en1"):
        r = subprocess.run(["ipconfig", "getifaddr", iface], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    try:  # Linux / fallback: ask the routing table which source IP leaves the host
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 1))  # TEST-NET-1, never actually routed
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def _hostname() -> str | None:
    import socket
    try:
        return socket.gethostname()
    except Exception:
        return None


def _remote_setup_hint(host: str) -> None:
    ca = Path.home() / ".config" / "market" / "ca.pem"
    click.echo("\n" + "─" * 62)
    click.echo("To connect another machine:")
    click.echo(f"  1. copy {ca}")
    click.echo("     to ~/.config/market/ca.pem on that machine")
    click.echo("  2. run there, with the same repo checked out:")
    click.echo(f"       MEM_HOST={host} MEM_TOKEN={mem_token()} \\")
    click.echo("         market install --client-only")
    click.echo("     No Docker needed on that side — the hooks skip the stack")
    click.echo("     startup and talk to this one.")
    click.echo("─" * 62)


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------

@main.command()
@click.argument("plugins", nargs=-1)
@click.option("--scope",  type=click.Choice(["user", "project"]), default="user", show_default=True)
@click.option("--project-root", default=None)
def uninstall(plugins: tuple[str, ...], scope: str, project_root: str | None):
    """Remove plugins (PLUGINS: names, or empty for everything — reads manifest, reversible)."""
    project_root = project_root or os.getcwd()
    selection = list(plugins) or None  # None = full uninstall

    click.echo(f"Uninstalling from Claude Code ({scope} scope)…")
    try:
        from .targets.claude import uninstall as _uninstall
        _uninstall(scope, project_root if scope == "project" else None, selection)
        click.echo("  ✓ done")
    except Exception as e:
        click.echo(f"  ✗ {e}", err=True)

    if selection is None:
        from .manifest import clear_manifest
        clear_manifest(scope, project_root if scope == "project" else None)
    click.echo("Done.  Docker stack left running (use `docker compose stop` to shut down).")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

@main.command()
@click.option("--repo-path", default=None, help="Check ingest status for a specific repo.")
def status(repo_path: str | None):
    """Show ingest status for the current project."""
    try:
        health = httpx.get(_mcp_url("/health"), timeout=3, verify=False, headers=_auth_headers()).json()
        click.echo(f"MCP server: {health.get('status', '?')}")
    except Exception:
        click.echo("MCP server: unreachable")
        return

    if repo_path:
        import hashlib, subprocess as sp
        try:
            url = sp.check_output(
                ["git", "-C", repo_path, "remote", "get-url", "origin"],
                stderr=sp.DEVNULL, text=True,
            ).strip()
        except Exception:
            url = str(Path(repo_path).resolve())
        gid = hashlib.sha256(url.encode()).hexdigest()[:16]
        try:
            s = httpx.get(_mcp_url(f"/status/{gid}"), timeout=3, verify=False, headers=_auth_headers()).json()
            click.echo(f"Ingest [{gid}]: {s.get('status', '?')}")
            for k in ("total", "embedded", "skipped", "errors"):
                if k in s:
                    click.echo(f"  {k}: {s[k]}")
            if "graph" in s and s["graph"]:
                g = s["graph"]
                click.echo(f"  graph.files:       {g.get('files', '?')}")
                click.echo(f"  graph.imports:     {g.get('imports', '?')}")
                click.echo(f"  graph.calls:       {g.get('calls_candidates', '?')}")
                click.echo(f"  graph.errors:      {g.get('errors', '?')}")
            # Also query live graph-status endpoint
            try:
                gs = httpx.get(_mcp_url(f"/graph-status/{gid}"), timeout=3, verify=False, headers=_auth_headers()).json()
                if "calls_edges" in gs:
                    click.echo(f"  graph edges:       calls={gs['calls_edges']} imports={gs['imports_edges']} files={gs['file_nodes']}")
            except Exception:
                pass
        except Exception:
            click.echo("Could not fetch ingest status.")


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------

@main.command()
def doctor():
    """Run health checks on the entire stack."""
    from .doctor import run_checks
    checks = run_checks(
        mcp_host=os.getenv("MEM_HOST", "127.0.0.1"),
        mcp_port=int(os.getenv("MEM_PORT", "7333")),
    )
    for c in checks:
        click.echo(repr(c))
    if all(c.ok for c in checks):
        click.echo("\nAll checks passed.")
    else:
        click.echo("\nSome checks failed.  See above.", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# ingest  (manual trigger)
# ---------------------------------------------------------------------------

@main.command()
@click.option("--repo-path", default=None, help="Path to the repository to ingest (default: cwd).")
def ingest(repo_path: str | None):
    """Manually trigger a full code ingest (useful for first-time setup)."""
    import hashlib, subprocess as sp

    repo_path = repo_path or os.getcwd()
    try:
        url = sp.check_output(
            ["git", "-C", repo_path, "remote", "get-url", "origin"],
            stderr=sp.DEVNULL, text=True,
        ).strip()
    except Exception:
        url = str(Path(repo_path).resolve())
    gid = hashlib.sha256(url.encode()).hexdigest()[:16]

    click.echo(f"Triggering ingest for {repo_path} (group_id={gid})…")
    try:
        r = httpx.post(
            _mcp_url("/ingest"),
            json={"group_id": gid, "repo_path": repo_path},
            timeout=10,
            verify=False,
            headers=_auth_headers(),
        )
        click.echo(r.json())
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
