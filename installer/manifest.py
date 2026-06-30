"""
Install manifest — records what was installed so uninstall is clean and reversible.

Stored at: ~/.config/market/manifest.json (user scope)
           <repo>/.mcp-memory/manifest.json (project scope)
"""
from __future__ import annotations

import json
from pathlib import Path

_USER_MANIFEST = Path.home() / ".config" / "market" / "manifest.json"


def _project_manifest(project_root: str) -> Path:
    return Path(project_root) / ".mcp-memory" / "manifest.json"


def _load(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {"files": [], "json_patches": []}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def manifest_path(scope: str, project_root: str | None = None) -> Path:
    if scope == "user":
        return _USER_MANIFEST
    if project_root:
        return _project_manifest(project_root)
    raise ValueError("project scope requires project_root")


def record_file(scope: str, src: str, dst: str, project_root: str | None = None) -> None:
    mp = manifest_path(scope, project_root)
    data = _load(mp)
    entry = {"src": src, "dst": dst}
    if entry not in data["files"]:
        data["files"].append(entry)
    _save(mp, data)


def record_json_patch(
    scope: str, target_file: str, key_path: list[str], value,
    project_root: str | None = None,
) -> None:
    mp = manifest_path(scope, project_root)
    data = _load(mp)
    entry = {"target": target_file, "key_path": key_path, "value": value}
    if entry not in data["json_patches"]:
        data["json_patches"].append(entry)
    _save(mp, data)


def get_manifest(scope: str, project_root: str | None = None) -> dict:
    return _load(manifest_path(scope, project_root))


def clear_manifest(scope: str, project_root: str | None = None) -> None:
    mp = manifest_path(scope, project_root)
    if mp.exists():
        mp.unlink()
