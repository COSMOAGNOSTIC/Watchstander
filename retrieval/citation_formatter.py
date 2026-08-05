"""
Phase 0: skeleton.

Turns a RetrievalResult's provenance into a human-readable citation string
-- e.g. "NAVSEA 8010 Manual, Ch. 4.4.3" rather than a raw chunk_id. Kept as
its own module because citation formatting is a presentation concern, not a
retrieval concern, and Phase 1's Definition of Done explicitly requires
"accurate citations" as a testable, separable property.
"""


def format_citation(source_id: str, chunk_id: str) -> str:
    """Render a chunk's provenance as a human-readable citation.

    Phase 0 skeleton -- Phase 1 wires this to real source metadata (document
    title, section/chapter, page where available). See MIGRATION.md.
    """
    raise NotImplementedError("format_citation: real logic lands in Phase 1 -- see MIGRATION.md")
