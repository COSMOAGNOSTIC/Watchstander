"""
Phase 0: skeleton.

Turns a Chunk (or a raw query string) into a vector embedding. Phase 1 wires
this to sentence-transformers. Kept as its own module (not inlined into
retriever.py) so swapping the embedding model/provider later -- a real
possibility once Phase 3's AWS SageMaker exposure happens -- touches one
file, not the whole pipeline.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Embedding:
    vector: list[float]
    model_name: str


def embed_text(text: str) -> Embedding:
    """Embed a single string of text.

    Phase 0 skeleton -- Phase 1 wires this to sentence-transformers
    (all-MiniLM-L6-v2 or similar). See MIGRATION.md.
    """
    raise NotImplementedError("embed_text: real logic lands in Phase 1 -- see MIGRATION.md")


def embed_chunks(chunks: list) -> list[Embedding]:
    """Embed a batch of chunks. Phase 0 skeleton -- see embed_text."""
    raise NotImplementedError("embed_chunks: real logic lands in Phase 1 -- see MIGRATION.md")
