"""
mem — marketplace installer CLI.

Commands
────────
mem install   --target claude|codex|both  --scope user|project  [--project-root PATH]
mem uninstall --target claude|codex|both  --scope user|project  [--project-root PATH]
mem status
mem doctor
mem ingest    --repo-path PATH  (manual trigger, useful for Codex or first-time setup)
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


def _compose(*args, **kwargs):
    env_args = ["--env-file", str(_ENV_FILE)] if _ENV_FILE.exists() else []
    return subprocess.run(
        ["docker", "compose", "-f", str(_COMPOSE_FILE)] + env_args + list(args),
        **kwargs,
    )


def _mcp_url(path: str = "") -> str:
    host = os.getenv("MEM_HOST", "127.0.0.1")
    port = os.getenv("MEM_PORT", "7333")
    return f"http://{host}:{port}{path}"


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------

@click.group()
def main():
    """mem — memory marketplace installer for Claude Code."""


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

@main.command()
@click.option("--target", type=click.Choice(["claude", "codex", "both"]), default="claude", show_default=True)
@click.option("--scope",  type=click.Choice(["user", "project"]),          default="user",   show_default=True)
@click.option("--project-root", default=None, help="Repo root for --scope project (defaults to cwd).")
def install(target: str, scope: str, project_root: str | None):
    """Install the memory plugin for Claude Code and/or Codex."""
    project_root = project_root or os.getcwd()
    targets = ["claude", "codex"] if target == "both" else [target]

    for t in targets:
        click.echo(f"Installing for {t} ({scope} scope)…")
        try:
            if t == "claude":
                from .targets.claude import install as _install
            else:
                from .targets.codex import install as _install
            _install(scope, project_root if scope == "project" else None)
            click.echo(f"  ✓ {t} done")
        except NotImplementedError as e:
            click.echo(f"  ✗ {e}", err=True)
        except Exception as e:
            click.echo(f"  ✗ {e}", err=True)
            sys.exit(1)

    # Start Docker stack
    click.echo("Starting Docker stack…")
    r = _compose("up", "-d", "--remove-orphans", capture_output=True)
    if r.returncode != 0:
        click.echo("  ✗ docker compose up failed — run `mem doctor` for details", err=True)
    else:
        click.echo("  ✓ stack up")

    click.echo("\nInstallation complete.  Restart Claude Code to activate hooks.")


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------

@main.command()
@click.option("--target", type=click.Choice(["claude", "codex", "both"]), default="claude", show_default=True)
@click.option("--scope",  type=click.Choice(["user", "project"]),          default="user",   show_default=True)
@click.option("--project-root", default=None)
def uninstall(target: str, scope: str, project_root: str | None):
    """Remove the memory plugin (reads manifest — reversible)."""
    project_root = project_root or os.getcwd()
    targets = ["claude", "codex"] if target == "both" else [target]

    for t in targets:
        click.echo(f"Uninstalling from {t} ({scope} scope)…")
        try:
            if t == "claude":
                from .targets.claude import uninstall as _uninstall
            else:
                from .targets.codex import uninstall as _uninstall
            _uninstall(scope, project_root if scope == "project" else None)
            click.echo(f"  ✓ {t} done")
        except NotImplementedError as e:
            click.echo(f"  ✗ {e}", err=True)
        except Exception as e:
            click.echo(f"  ✗ {e}", err=True)

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
    from .targets.claude import _hooks_dst  # noqa: just to confirm install

    try:
        health = httpx.get(_mcp_url("/health"), timeout=3).json()
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
            s = httpx.get(_mcp_url(f"/status/{gid}"), timeout=3).json()
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
                gs = httpx.get(_mcp_url(f"/graph-status/{gid}"), timeout=3).json()
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
    """Manually trigger a full code ingest (useful for first-time setup or Codex)."""
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
        )
        click.echo(r.json())
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
