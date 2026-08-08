"""
Phase 2: context compression.

Given a chunk's full text and the query that retrieved it, returns just the
most query-relevant sentence(s) from within it rather than the whole chunk
-- less for a downstream consumer (or a reviewer reading the citation) to
read through, without needing an LLM call to summarize (Watchstander's
live graph is edge-first/zero-network by design -- see
ARCHITECTURE.md ADR-003 -- and this is a teaching harness for exactly that
kind of real-but-lightweight RAG technique).

Real term-overlap scoring against each sentence, not a blind head/tail
truncation -- a chunk's most query-relevant sentence isn't always its
first one (see test_compress_prefers_the_relevant_sentence_over_the_first_one).
"""

from __future__ import annotations

import re

from retrieval.chunker import split_sentences

_WORD = re.compile(r"[a-z0-9]+")


def _terms(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def compress(text: str, query: str, max_sentences: int = 2) -> str:
    """Return up to `max_sentences` sentences from `text`, the ones sharing
    the most vocabulary with `query`, in their original order. Falls back
    to the full text unchanged when there's nothing to gain from
    compressing: the text is already short enough, the query has no usable
    vocabulary, or no sentence shares any vocabulary with the query at all
    (compression should never make an answer harder to verify by cutting a
    snippet that turns out to be unrelated to what was actually asked)."""
    sentences = [s for s, _, _ in split_sentences(text)]
    if len(sentences) <= max_sentences:
        return text

    query_terms = _terms(query)
    if not query_terms:
        return text

    scores = [len(query_terms & _terms(s)) for s in sentences]
    if all(score == 0 for score in scores):
        return text

    top_indices = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)[:max_sentences]
    keep_indices = sorted(top_indices)  # restore original reading order
    return " ".join(sentences[i] for i in keep_indices)
