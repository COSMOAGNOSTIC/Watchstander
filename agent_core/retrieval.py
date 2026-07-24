"""
Phase 3: local case retrieval, ranked instead of just category-matched.

Phase 1's `case_lookup.cite_case()` does a flat filter by hazard category
and returns whichever case happens to be first in the JSON file. That's
fine when a category has one case, but `fall_protection` already has
three (FALL-DETYENS-2024, STRUCK-DETYENS-2020, PATTERN-DETYENS-2015) and
MIGRATION.md Phase 4 targets 5-10 cases per category. "Always cite the
first one" stops being defensible once there's real choice to make.

This module ranks candidate cases by TF-IDF cosine similarity between the
flagged conflict's own text (description + conflict rationale) and each
case's summary/root-cause/subpart text, so the case actually cited is the
one whose facts overlap with what was flagged -- not just the oldest
entry in the file.

Why pure-Python TF-IDF instead of a vector store (per architecture
review, PASSDOWN.md Section 3 -- Watchstander is edge-first and must
keep running with zero network access): ChromaDB/FAISS + a
sentence-transformer embedding model would require downloading model
weights at runtime, which is exactly the kind of network dependency the
edge-resilience requirement rules out. At the case-corpus size this
project actually has -- low tens of documents even at Phase 4's target --
a hand-rolled TF-IDF index is a few dozen lines, needs no extra
dependency, no model download, and runs in well under a millisecond per
query. If the corpus grows into the hundreds this should be revisited
(see MIGRATION.md Phase 3 note); that's a problem for a future phase,
not this one.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache

from agent_core.case_lookup import _load_cases
from agent_core.state import HazardCategory

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _case_document(case: dict) -> str:
    """The fields worth matching a query against for a given case."""
    return " ".join(
        [
            case.get("summary", ""),
            case.get("root_cause", ""),
            case.get("hazard_category", ""),
            case.get("osha_subpart", ""),
        ]
    )


def _normalize(vec: dict[str, float]) -> dict[str, float]:
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return vec
    return {k: v / norm for k, v in vec.items()}


@lru_cache(maxsize=1)
def _build_index():
    """
    Builds a TF-IDF index over every case in case_data/cases_v1.json.
    Cached for process lifetime -- the case file doesn't change at
    runtime, only between deploys.
    """
    cases = _load_cases()
    documents = [_tokenize(_case_document(c)) for c in cases]

    doc_freq = Counter()
    for tokens in documents:
        doc_freq.update(set(tokens))

    n_docs = max(len(documents), 1)
    idf = {term: math.log((1 + n_docs) / (1 + freq)) + 1 for term, freq in doc_freq.items()}

    doc_vectors = []
    for tokens in documents:
        term_freq = Counter(tokens)
        vec = {term: count * idf.get(term, 0.0) for term, count in term_freq.items()}
        doc_vectors.append(_normalize(vec))

    return cases, doc_vectors, idf


def _vectorize_query(query: str, idf: dict[str, float]) -> dict[str, float]:
    term_freq = Counter(_tokenize(query))
    vec = {term: count * idf.get(term, 0.0) for term, count in term_freq.items() if term in idf}
    return _normalize(vec)


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def retrieve_best_case_for_hazards(
    query: str, hazards: list[HazardCategory | str]
) -> dict | None:
    """
    Ranks only the cases matching one of the given hazard categories by
    TF-IDF similarity to `query`, and returns the single best match (or
    None if no case is on file for any of those categories yet).

    With no usable query signal (empty string, or no query terms overlap
    the corpus vocabulary), falls back to the first sourced case for the
    hazard -- the same deterministic behavior as Phase 1's
    `case_lookup.cite_case()` -- rather than an arbitrary or unstable
    ranking.
    """
    cases, doc_vectors, idf = _build_index()
    hazard_values = {h.value if isinstance(h, HazardCategory) else h for h in hazards}

    candidates = [
        (case, doc_vec)
        for case, doc_vec in zip(cases, doc_vectors)
        if case["hazard_category"] in hazard_values
    ]
    if not candidates:
        return None

    query_vec = _vectorize_query(query, idf)
    if not query_vec:
        return candidates[0][0]

    best_case, _best_score = max(candidates, key=lambda pair: _cosine(query_vec, pair[1]))
    return best_case


def cite_best_matching_case(query: str, hazards: list[HazardCategory | str]) -> str | None:
    """
    Same citation format as `case_lookup.cite_case()`, but backed by
    similarity ranking instead of "first case in the file."
    """
    case = retrieve_best_case_for_hazards(query, hazards)
    if case is None:
        return None
    return (
        f"Precedent: {case['case_id']} ({case['shipyard']}) -- {case['summary']} "
        f"Root cause: {case['root_cause']} [{case['osha_subpart']}]"
    )
