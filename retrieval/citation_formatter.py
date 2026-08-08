"""
Phase 1: real citation formatting.

Turns a retrieval result's provenance into a human-readable citation string
-- e.g. "NAVSEA 8010 Manual (S0570-AC-CCM-010/8010), Sec. 4.4.3" rather than
a raw chunk_id. Kept as its own module because citation formatting is a
presentation concern, not a retrieval concern, and Phase 1's Definition of
Done explicitly requires "accurate citations" as a testable, separable
property.

`section` is optional because not every source uses NAVSEA-style section
numbering (case_data entries, for one) -- when it's missing, the citation
falls back to naming the source document and the chunk_id rather than
fabricating a section number that isn't there. An unknown source_id (not in
SOURCE_TITLES) is also handled without guessing at a title -- the raw
source_id is used verbatim so the citation stays traceable rather than
silently wrong.
"""

from __future__ import annotations

# Document titles for every source_id this pipeline ingests. Add an entry
# here whenever ingest.py gains a new source (see retrieval/ingest.py) --
# this registry, not chunk content, is what keeps a citation's document
# name accurate.
SOURCE_TITLES: dict[str, str] = {
    "navsea_8010": "NAVSEA 8010 Manual (S0570-AC-CCM-010/8010)",
    # Ingested per-chapter (see retrieval/ingest.py -- chunk_id numbering
    # restarts at #000 per source_id, so chapters can't share one source_id
    # without colliding) but cited as one document; the chapter distinction
    # lives in `section`, not the title.
    "navsea_8010_ch4": "NAVSEA 8010 Manual (S0570-AC-CCM-010/8010)",
    "navsea_8010_ch11": "NAVSEA 8010 Manual (S0570-AC-CCM-010/8010)",
    "cases_v1": "Watchstander Sourced Case File",
}


def format_citation(source_id: str, chunk_id: str, section: str | None = None) -> str:
    """Render a chunk's provenance as a human-readable citation."""
    title = SOURCE_TITLES.get(source_id, source_id)
    if section:
        return f"{title}, Sec. {section}"
    return f"{title} ({chunk_id})"
