from __future__ import annotations

import threading

import torch
import transformers.pytorch_utils as _pt_utils

# `find_pruneable_heads_and_indices` was removed from transformers.pytorch_utils in 4.44+
# but jina-embeddings-v2-base-code's custom code still imports it from there.
if not hasattr(_pt_utils, "find_pruneable_heads_and_indices"):
    def _find_pruneable_heads_and_indices(heads, n_heads, head_size, already_pruned_heads):
        mask = torch.ones(n_heads, head_size)
        heads = set(heads) - already_pruned_heads
        for head in heads:
            head = head - sum(1 if h < head else 0 for h in already_pruned_heads)
            mask[head] = 0
        mask = mask.view(-1).contiguous().eq(1)
        index = torch.arange(len(mask))[mask].long()
        return heads, index

    _pt_utils.find_pruneable_heads_and_indices = _find_pruneable_heads_and_indices

from sentence_transformers import SentenceTransformer

from .config import config

_MODEL_CACHE_DIR = "/data/models"

_lock = threading.Lock()
_models: dict[str, SentenceTransformer] = {}


def _get_model(purpose: str) -> SentenceTransformer:
    with _lock:
        if purpose not in _models:
            model_id = config.CODE_EMBED_MODEL if purpose == "code" else config.MEMORY_EMBED_MODEL
            _models[purpose] = SentenceTransformer(
                model_id,
                cache_folder=_MODEL_CACHE_DIR,
                trust_remote_code=True,
            )
    return _models[purpose]


def embed(text: str, purpose: str = "code") -> list[float]:
    """Return a zero-padded MAX_DIM vector for *text*."""
    model = _get_model(purpose)
    vec: list[float] = model.encode(text, convert_to_numpy=True).tolist()
    pad = config.MAX_DIM - len(vec)
    if pad > 0:
        vec = vec + [0.0] * pad
    return vec[: config.MAX_DIM]


def embed_batch(texts: list[str], purpose: str = "code") -> list[list[float]]:
    """Embed a batch of texts in a single forward pass."""
    if not texts:
        return []
    model = _get_model(purpose)
    result = []
    for vec in model.encode(texts, convert_to_numpy=True, batch_size=32):
        v: list[float] = vec.tolist()
        pad = config.MAX_DIM - len(v)
        if pad > 0:
            v = v + [0.0] * pad
        result.append(v[: config.MAX_DIM])
    return result


def ensure_models() -> None:
    """Pre-warm both models (downloads from HuggingFace on first run)."""
    _get_model("code")
    _get_model("memory")
