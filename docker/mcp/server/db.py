from __future__ import annotations

from threading import Lock

from falkordb import FalkorDB, Graph

from .config import config

_client: FalkorDB | None = None
_lock = Lock()


def get_client() -> FalkorDB:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = FalkorDB(host=config.FALKORDB_HOST, port=config.FALKORDB_PORT)
    return _client


def get_graph(group_id: str) -> Graph:
    return get_client().select_graph(f"g_{group_id}")
