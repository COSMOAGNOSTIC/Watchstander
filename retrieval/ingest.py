"""
Phase 1: corpus ingestion.

Reads Watchstander source documents, chunks them, embeds them, and upserts
into a persistent Chroma collection so `retriever.retrieve()` has a real
index to query against. This is meant to be run by hand, not by the test
suite -- embedding for real requires sentence-transformers to download its
model on first use, which needs live network access this repo's automated
tests deliberately don't depend on (see embedder.py's module docstring).

Corpus, as of Phase 1 (see MIGRATION.md and ARCHITECTURE.md ADR-005):
  - navsea_8010_ch4 / navsea_8010_ch11: original manual text, Chapters 4 and
    11 (retrieval/sources/navsea_8010_ch4.txt, navsea_8010_ch11.txt) --
    separate source_ids per chapter (see ingest_all below for why), one
    document title in citations (citation_formatter.SOURCE_TITLES)
  - cases_v1: sourced incident cases (case_data/cases_v1.json), one chunk
    per case rather than sentence-chunked -- each case is already a short,
    self-contained unit and splitting one mid-case would separate the
    hazard from its root cause.

OSHA CFR 1915 excerpts are still an open item (MIGRATION.md Phase 1) -- not
sourced yet, deliberately not stubbed in here with placeholder text.

Run directly:

    python -m retrieval.ingest
"""

from __future__ import annotations

import json
from pathlib import Path

from retrieval.chunker import Chunk, chunk_text
from retrieval.embedder import embed_chunks
from retrieval.vector_store import VectorStore

SOURCES_DIR = Path(__file__).resolve().parent / "sources"
DEFAULT_PERSIST_DIR = str(Path(__file__).resolve().parent / ".chroma_store")
CASES_PATH = Path(__file__).resolve().parent.parent / "case_data" / "cases_v1.json"


def ingest_text_source(
    text: str, source_id: str, vector_store: VectorStore, chunk_size: int = 800, overlap: int = 100
) -> int:
    """Chunk, embed, and upsert one raw-text source document. Returns the
    number of chunks written."""
    chunks = chunk_text(text, source_id=source_id, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        return 0
    vector_store.upsert(chunks, embed_chunks(chunks))
    return len(chunks)


def _case_to_chunk(case: dict, index: int) -> Chunk:
    body = (
        f"{case['case_id']} ({case.get('shipyard', 'unknown shipyard')}, {case.get('date', 'undated')}): "
        f"{case.get('summary', '')} Root cause: {case.get('root_cause', '')}"
    )
    return Chunk(
        text=body,
        source_id="cases_v1",
        chunk_id=f"cases_v1#{index:03d}",
        start_char=0,
        end_char=len(body),
        section=case.get("case_id"),
    )


def ingest_cases(cases_path: Path, vector_store: VectorStore) -> int:
    """One chunk per sourced case -- see module docstring for why these
    aren't sentence-chunked like the manual text."""
    data = json.loads(cases_path.read_text())
    cases = data.get("cases", [])
    if not cases:
        return 0
    chunks = [_case_to_chunk(case, i) for i, case in enumerate(cases)]
    vector_store.upsert(chunks, embed_chunks(chunks))
    return len(chunks)


def ingest_all(persist_directory: str = DEFAULT_PERSIST_DIR) -> dict[str, int]:
    vector_store = VectorStore(persist_directory=persist_directory)
    counts = {
        # Distinct source_ids per chapter -- both chapters share a chunk_id
        # numbering scheme that restarts at #000, so reusing one source_id
        # for both would silently collide chunk_ids between chapters and
        # each upsert would overwrite the other's chunks in Chroma.
        # citation_formatter's SOURCE_TITLES maps both back to the same
        # human-readable document title.
        "navsea_8010_ch4": ingest_text_source(
            (SOURCES_DIR / "navsea_8010_ch4.txt").read_text(), "navsea_8010_ch4", vector_store
        ),
        "navsea_8010_ch11": ingest_text_source(
            (SOURCES_DIR / "navsea_8010_ch11.txt").read_text(), "navsea_8010_ch11", vector_store
        ),
        "cases_v1": ingest_cases(CASES_PATH, vector_store),
    }
    return counts


if __name__ == "__main__":
    written = ingest_all()
    total = sum(written.values())
    for source, count in written.items():
        print(f"  {source}: {count} chunks")
    print(f"Total: {total} chunks ingested into {DEFAULT_PERSIST_DIR}")
