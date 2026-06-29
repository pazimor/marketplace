from __future__ import annotations

import httpx

from .config import config

_BASE = f"http://{config.OLLAMA_HOST}:{config.OLLAMA_PORT}"


def embed(text: str, purpose: str = "code") -> list[float]:
    """Return a zero-padded MAX_DIM vector for *text*.

    Uses /api/embed (Ollama >= 0.4) with fallback to /api/embeddings (legacy).
    """
    model = config.CODE_EMBED_MODEL if purpose == "code" else config.MEMORY_EMBED_MODEL

    # Try new endpoint first (Ollama >= 0.4)
    resp = httpx.post(
        f"{_BASE}/api/embed",
        json={"model": model, "input": text},
        timeout=60.0,
    )

    if resp.status_code == 404:
        # Fallback: old endpoint
        resp = httpx.post(
            f"{_BASE}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=60.0,
        )
        resp.raise_for_status()
        vec: list[float] = resp.json()["embedding"]
    else:
        resp.raise_for_status()
        # New API returns {"embeddings": [[...]]}
        vec = resp.json()["embeddings"][0]

    pad = config.MAX_DIM - len(vec)
    if pad > 0:
        vec = vec + [0.0] * pad
    return vec[: config.MAX_DIM]


def pull_model(model: str) -> None:
    """Pull an Ollama model if not already present (blocking)."""
    httpx.post(f"{_BASE}/api/pull", json={"name": model, "stream": False}, timeout=600.0).raise_for_status()


def ensure_models() -> None:
    pull_model(config.CODE_EMBED_MODEL)
    pull_model(config.MEMORY_EMBED_MODEL)
