"""
Phase 1: real embedding, wired to sentence-transformers.

Turns a Chunk (or a raw query string) into a vector embedding using
all-MiniLM-L6-v2, loaded lazily and cached at module scope so repeated
calls (e.g. one per chunk during ingestion) don't reload the model each
time. `sentence-transformers` is an optional dependency (the `retrieval`
extra in pyproject.toml) -- importing this module never requires it; only
calling `embed_text`/`embed_chunks` does, so callers that inject their own
`embed_fn` (as tests and Retriever both can) never pay that cost.

Real model download requires live network access (first run only, then
cached locally) -- this module is never exercised with the real model
inside this repo's test suite, which injects a deterministic offline
embed_fn instead. See tests/test_retrieval_integration.py. This mirrors the
repo's existing pattern (agent_core/reasoning.py's ANTHROPIC_API_KEY-gated
deterministic fallback): the real path exists and is meant to run for real,
just not automatically under CI.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from retrieval.chunker import Chunk

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"


@dataclass(frozen=True)
class Embedding:
    vector: list[float]
    model_name: str


@lru_cache(maxsize=4)
def _load_model(model_name: str):
    """Import sentence-transformers lazily -- keeps it an optional
    dependency for anything that doesn't actually need to embed."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def embed_text(text: str, model_name: str = DEFAULT_MODEL_NAME) -> Embedding:
    """Embed a single string of text."""
    model = _load_model(model_name)
    vector = model.encode(text, normalize_embeddings=True).tolist()
    return Embedding(vector=vector, model_name=model_name)


def embed_chunks(chunks: list["Chunk"], model_name: str = DEFAULT_MODEL_NAME) -> list[Embedding]:
    """Embed a batch of chunks in one model call -- meaningfully faster than
    calling embed_text per chunk during ingestion."""
    if not chunks:
        return []
    model = _load_model(model_name)
    vectors = model.encode([c.text for c in chunks], normalize_embeddings=True)
    return [Embedding(vector=v.tolist(), model_name=model_name) for v in vectors]
