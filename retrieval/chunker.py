"""
Phase 1: real chunking.

Splits a source document's raw text into overlapping chunks sized for
embedding, using sentence boundaries (not a blind character-count cut) so a
chunk never ends mid-sentence. Also tags each chunk with the most specific
NAVSEA-style section number (e.g. "4.4.3") found in it, when the source uses
that numbering convention -- this is what citation_formatter turns into a
human-readable citation, so it has to be real, not decorative.

See MIGRATION.md Phase 1 for the definition of done this satisfies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Split on whitespace that follows sentence-ending punctuation and precedes
# a capital letter, digit, opening quote, or paren -- good enough for
# manual/regulatory prose (short abbreviations like "No." inside a sentence
# don't reliably break this, but this corpus doesn't lean on them).
_SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"(])')

# NAVSEA 8010-style section numbers: "4.4.3", "11.1.7", "4.4" -- always at
# the start of a paragraph, immediately followed by the section title. Only
# match at a line/chunk start (or right after a sentence boundary) so we
# don't pick up incidental numbers like "29 CFR Part 1915" mid-sentence.
_SECTION_NUMBER = re.compile(r'(?:^|\n)(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+[A-Z]')


@dataclass(frozen=True)
class Chunk:
    """A single chunk of source text, ready for embedding.

    `source_id` + `start_char`/`end_char` are what citation_formatter turns
    into a human-readable citation later in the pipeline -- load-bearing
    fields, not decorative ones. `section`, when present, is the most
    specific NAVSEA-style section number found inside this chunk's text
    (e.g. "4.4.3"); it is None for sources that don't use that numbering
    convention (e.g. case_data entries), and citation_formatter falls back
    to chunk_id-based provenance in that case.
    """

    text: str
    source_id: str  # e.g. "navsea_8010", "osha_cfr_1915"
    chunk_id: str  # source_id + deterministic index, e.g. "navsea_8010#003"
    start_char: int
    end_char: int
    section: str | None = None


def split_sentences(text: str) -> list[tuple[str, int, int]]:
    """Return (sentence_text, start_char, end_char) for every non-blank
    sentence in `text`, offsets relative to `text` itself. Public -- Phase 2's
    context compression (retrieval/compression.py) reuses this same
    sentence-boundary logic rather than re-implementing it, so a chunk's
    "sentences" mean the same thing everywhere in this package."""
    spans: list[tuple[int, int]] = []
    start = 0
    for m in _SENTENCE_BOUNDARY.finditer(text):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(text)))
    return [(text[s:e], s, e) for s, e in spans if text[s:e].strip()]


def _section_for(text: str) -> str | None:
    """Return the *last* section header found in `text` -- when a chunk
    contains more than one header (a short section followed by the start
    of the next), the last one is what's actually in force by the time the
    chunk ends, and is what should carry forward into the next chunk if it
    has no header of its own (see chunk_text)."""
    matches = _SECTION_NUMBER.findall(text)
    return matches[-1] if matches else None


def chunk_text(text: str, source_id: str, chunk_size: int = 800, overlap: int = 100) -> list[Chunk]:
    """Split `text` into overlapping, sentence-boundary-respecting `Chunk`s.

    Packs whole sentences into each chunk up to `chunk_size` characters (a
    single sentence longer than `chunk_size` still becomes its own chunk
    rather than being truncated -- losing content silently would be worse
    than one oversized chunk). Successive chunks overlap by walking back
    roughly `overlap` characters' worth of trailing sentences, so a fact
    split across a chunk boundary is still findable from either side.
    """
    if not text or not text.strip():
        return []

    sentences = split_sentences(text)
    n = len(sentences)
    chunks: list[Chunk] = []
    i = 0
    chunk_idx = 0
    # Carries the most recent section header seen so far across the whole
    # document -- a chunk that's a continuation of a section (comes after
    # its header sentence, not containing the header text itself) still
    # belongs to that section, not to no section at all. Without this, only
    # the chunk that happens to contain the literal "4.4.3 Limitations..."
    # header text gets tagged, and the very next chunk -- which is just as
    # much a part of 4.4.3 -- silently loses its citation.
    active_section: str | None = None

    while i < n:
        start_char = sentences[i][1]
        cur_len = 0
        j = i
        while j < n:
            sent_len = len(sentences[j][0])
            if cur_len and cur_len + sent_len > chunk_size:
                break
            cur_len += sent_len + 1
            j += 1
        # Always take at least one sentence, even if it alone exceeds
        # chunk_size -- never drop content to satisfy the size target.
        if j == i:
            j = i + 1

        end_char = sentences[j - 1][2]
        chunk_body = text[start_char:end_char].strip()
        found_section = _section_for(chunk_body)
        if found_section:
            active_section = found_section
        chunks.append(
            Chunk(
                text=chunk_body,
                source_id=source_id,
                chunk_id=f"{source_id}#{chunk_idx:03d}",
                start_char=start_char,
                end_char=end_char,
                section=active_section,
            )
        )
        chunk_idx += 1

        if j >= n:
            break

        # Walk back from the end of this chunk far enough to cover
        # `overlap` characters of trailing sentences, then resume there --
        # guaranteed to move forward by at least one sentence each pass.
        back_len = 0
        k = j - 1
        while k > i and back_len < overlap:
            back_len += len(sentences[k][0])
            k -= 1
        i = max(k + 1, i + 1)

    return chunks
