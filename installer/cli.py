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


def _setup_tls() -> None:
    """Install a locally-trusted CA (mkcert) and generate the server cert.

    The MCP server serves https; mkcert's CA must be trusted so the Claude Code
    native client connects without warnings. `mkcert -install` may prompt for
    the macOS password — that's expected and only needed once per machine.
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

    # Generate the server cert if missing.
    crt = _CERTS_DIR / "server.crt"
    key = _CERTS_DIR / "server.key"
    if crt.exists() and key.exists():
        click.echo("  ✓ server cert present")
        return
    _CERTS_DIR.mkdir(parents=True, exist_ok=True)
    g = subprocess.run(
        ["mkcert", "-cert-file", str(crt), "-key-file", str(key),
         "127.0.0.1", "localhost", "::1"],
        capture_output=True, text=True,
    )
    if g.returncode == 0:
        click.echo("  ✓ server cert generated")
    else:
        click.echo(f"  ✗ cert generation failed: {g.stderr.strip()}", err=True)


def _compose(*args, **kwargs):
    env_args = ["--env-file", str(_ENV_FILE)] if _ENV_FILE.exists() else []
    return subprocess.run(
        ["docker", "compose", "-f", str(_COMPOSE_FILE)] + env_args + list(args),
        **kwargs,
    )


def _mcp_url(path: str = "") -> str:
    host = os.getenv("MEM_HOST", "127.0.0.1")
    port = os.getenv("MEM_PORT", "7333")
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
def install(plugins: tuple[str, ...], scope: str, project_root: str | None):
    """Install marketplace plugins (PLUGINS: names, `full`, or empty for MCP core only)."""
    project_root = project_root or os.getcwd()
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

    # Set up local TLS (mkcert CA + server cert) before starting the stack.
    click.echo("Setting up TLS (mkcert)…")
    _setup_tls()

    # Start Docker stack
    click.echo("Starting Docker stack…")
    r = _compose("up", "-d", "--remove-orphans", capture_output=True)
    if r.returncode != 0:
        click.echo("  ✗ docker compose up failed — run `market doctor` for details", err=True)
    else:
        click.echo("  ✓ stack up")

    click.echo("\nInstallation complete.  Restart Claude Code to activate hooks.")


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
        health = httpx.get(_mcp_url("/health"), timeout=3, verify=False).json()
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
            s = httpx.get(_mcp_url(f"/status/{gid}"), timeout=3, verify=False).json()
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
                gs = httpx.get(_mcp_url(f"/graph-status/{gid}"), timeout=3, verify=False).json()
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
        )
        click.echo(r.json())
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
