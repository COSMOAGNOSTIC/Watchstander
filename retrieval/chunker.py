"""
Phase 0: skeleton.

Splits a source document's raw text into overlapping chunks sized for
embedding. Phase 1 wires this against the real Watchstander corpus (NAVSEA
8010 Manual, OSHA CFR excerpts, case_data); this phase only defines the data
model and the function boundary the rest of the pipeline is built against.

See MIGRATION.md Phase 1 for what "real logic" means here (sentence/
paragraph-aware splitting, not a blind character-count cut).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    """A single chunk of source text, ready for embedding.

    `source_id` + `start_char`/`end_char` are what citation_formatter turns
    into a human-readable citation later in the pipeline -- load-bearing
    fields, not decorative ones.
    """

    text: str
    source_id: str  # e.g. "navsea_8010", "osha_cfr_1915"
    chunk_id: str  # source_id + deterministic index, e.g. "navsea_8010#003"
    start_char: int
    end_char: int


def chunk_text(text: str, source_id: str, chunk_size: int = 800, overlap: int = 100) -> list[Chunk]:
    """Split `text` into overlapping `Chunk`s.

    Phase 0 skeleton -- real chunking logic lands in Phase 1. See
    MIGRATION.md.
    """
    raise NotImplementedError("chunk_text: real logic lands in Phase 1 -- see MIGRATION.md")
