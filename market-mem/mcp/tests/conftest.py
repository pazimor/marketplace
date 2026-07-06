"""Integration-test fixtures — run against a LIVE FalkorDB (inside the mcp
container or any env where server.config points at a reachable instance).

Every test gets a disposable `it_<hex>` graph, dropped afterwards, so the
suite never touches real project graphs.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.db import get_graph  # noqa: E402


@pytest.fixture()
def gid():
    group_id = f"it_{uuid.uuid4().hex[:12]}"
    yield group_id
    try:
        get_graph(group_id).delete()
    except Exception:
        pass
