"""Server-side git mirrors.

A client whose files this server cannot read (another machine) still gets code
RAG: instead of walking a path that only exists on the client, the server keeps
its own clone of the repo and indexes that.

The trade-off is explicit and must stay visible to callers: a mirror only knows
what has been **pushed**. Every read path therefore reports the commit the index
was built from (``Project.mirror_commit``), so an agent can tell whether it is
looking at current work or at the last push.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

MIRROR_ROOT = Path(os.getenv("MIRROR_ROOT", "/data/repos"))

# Transports we are willing to fetch over. `ext::` and `file::` are excluded on
# purpose: ext:: runs an arbitrary command, and file:: would expose the server's
# own filesystem to whoever can call /ingest.
_ALLOWED_SCHEMES = ("https://", "ssh://", "git@")

_GIT_TIMEOUT = 900  # 15 min — a first clone of a large repo is slow, not hung


class MirrorError(RuntimeError):
    pass


def _git(*args: str, cwd: Path | None = None) -> str:
    r = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, timeout=_GIT_TIMEOUT,
        # Never let git stop for credentials: a prompt would hang the request
        # until the timeout instead of failing with something actionable.
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true"},
    )
    if r.returncode != 0:
        raise MirrorError((r.stderr or r.stdout).strip() or f"git {args[0]} failed")
    return r.stdout.strip()


def _check_url(git_url: str) -> None:
    if not git_url or not git_url.startswith(_ALLOWED_SCHEMES):
        raise MirrorError(
            f"unsupported git URL {git_url!r} — expected one of {_ALLOWED_SCHEMES}"
        )


def _check_ref(ref: str) -> None:
    # The ref lands on a git command line; keep it to plain ref characters so a
    # crafted value cannot turn into an option or a second argument.
    if not re.fullmatch(r"[A-Za-z0-9._/-]{1,255}", ref) or ref.startswith("-"):
        raise MirrorError(f"invalid ref {ref!r}")


def mirror_path(group_id: str) -> Path:
    return MIRROR_ROOT / group_id


def sync(group_id: str, git_url: str, ref: str = "") -> tuple[str, str]:
    """Clone or update the mirror for *group_id*. Returns (path, commit).

    *ref* defaults to the remote's default branch. The working tree is reset
    hard: the mirror is a disposable projection of the remote, never a place
    where work happens.
    """
    _check_url(git_url)
    if ref:
        _check_ref(ref)

    path = mirror_path(group_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not (path / ".git").is_dir():
        log.info("mirror: cloning %s → %s", git_url, path)
        _git("clone", "--quiet", git_url, str(path))
    else:
        # Point at the requested URL in case the remote moved.
        _git("remote", "set-url", "origin", git_url, cwd=path)
        _git("fetch", "--quiet", "--prune", "origin", cwd=path)

    target = ref or _default_branch(path)
    # Prefer the remote-tracking ref: the local branch may lag behind the fetch.
    for candidate in (f"origin/{target}", target):
        try:
            _git("checkout", "--quiet", "--force", "--detach", candidate, cwd=path)
            break
        except MirrorError:
            continue
    else:
        raise MirrorError(f"ref {target!r} not found in {git_url}")

    _git("clean", "-qfdx", cwd=path)
    commit = _git("rev-parse", "HEAD", cwd=path)
    log.info("mirror: %s at %s (%s)", group_id, commit[:12], target)
    return str(path), commit


def _default_branch(path: Path) -> str:
    """The remote's HEAD branch, falling back to the usual suspects."""
    try:
        # e.g. "refs/remotes/origin/main" → "main"
        out = _git("symbolic-ref", "refs/remotes/origin/HEAD", cwd=path)
        return out.rsplit("/", 1)[-1]
    except MirrorError:
        pass
    for name in ("main", "master"):
        try:
            _git("rev-parse", "--verify", f"origin/{name}", cwd=path)
            return name
        except MirrorError:
            continue
    raise MirrorError("cannot determine the default branch")


def head_commit(group_id: str) -> str | None:
    """Current commit of an existing mirror, or None."""
    path = mirror_path(group_id)
    if not (path / ".git").is_dir():
        return None
    try:
        return _git("rev-parse", "HEAD", cwd=path)
    except MirrorError:
        return None
