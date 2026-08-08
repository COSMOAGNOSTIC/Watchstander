"""
Eval harness runner for Phase 2.

Loads the real corpus (NAVSEA 8010 Ch4/Ch11, OSHA 1915 Subpart B,
case_data/cases_v1.json) into a fresh in-memory VectorStore + BM25Index,
using the same deterministic hashed-bag-of-words embedding function
test_retrieval_integration.py already uses -- no live network, no real
sentence-transformers model, same constraint the rest of this package's
test suite runs under (see embedder.py's module docstring).

For each scenario in scenarios.py, runs the query through a vector-only
Retriever and a hybrid (vector + BM25) Retriever, and checks whether the
expected (source_id, section) is the top-1 result for each. Produces a
single JSON-serializable metrics dict, in the same checked-in-baseline
spirit as eval/ at the repo root.

Usage:
    python -m retrieval.eval.run_eval                  # human-readable report
    python -m retrieval.eval.run_eval --json            # raw metrics dict
    python -m retrieval.eval.run_eval --write-baseline  # overwrite baseline.json
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from unittest.mock import patch

from retrieval import ingest
from retrieval.bm25_index import BM25Index
from retrieval.embedder import Embedding
from retrieval.eval.scenarios import SCENARIOS
from retrieval.retriever import Retriever
from retrieval.vector_store import VectorStore

BASELINE_PATH = Path(__file__).parent / "baseline.json"
_WORD = re.compile(r"[a-z]+")
_DIMS = 64


def _hashed_bow_embed(text: str) -> Embedding:
    """Same deterministic, network-free embedding function
    test_retrieval_integration.py uses -- a real (if crude) bag-of-hashed-
    words vectorizer, not a no-op stub, so vector-only retrieval in this
    eval behaves like a real (if weak) embedding model, not a strawman it's
    trivially easy for hybrid to beat."""
    vector = [0.0] * _DIMS
    for word in _WORD.findall(text.lower()):
        bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % _DIMS
        vector[bucket] += 1.0
    norm = sum(v * v for v in vector) ** 0.5
    if norm:
        vector = [v / norm for v in vector]
    return Embedding(vector=vector, model_name="eval-hashed-bow")


def _embed_chunks(chunks):
    return [_hashed_bow_embed(c.text) for c in chunks]


def build_corpus() -> VectorStore:
    """Ingest the real corpus into a fresh in-memory VectorStore, reusing
    ingest.py's real ingestion functions with ingest.embed_chunks patched
    to the deterministic embedder above (in place of the real
    sentence-transformers model, which needs live network)."""
    store = VectorStore(collection_name="eval_corpus")
    with patch.object(ingest, "embed_chunks", _embed_chunks):
        ingest.ingest_text_source((ingest.SOURCES_DIR / "navsea_8010_ch4.txt").read_text(), "navsea_8010_ch4", store)
        ingest.ingest_text_source((ingest.SOURCES_DIR / "navsea_8010_ch11.txt").read_text(), "navsea_8010_ch11", store)
        ingest.ingest_osha_subpart(
            (ingest.SOURCES_DIR / "osha_1915_subpart_b.txt").read_text(), "osha_1915_subpart_b", store
        )
        ingest.ingest_cases(ingest.CASES_PATH, store)
    return store


def _run_scenarios(retriever: Retriever) -> list[dict]:
    results = []
    for scenario in SCENARIOS:
        top = retriever.retrieve(scenario.query, top_k=1)
        matched = bool(top) and top[0].source_id == scenario.expected_source_id and top[0].section == scenario.expected_section
        results.append(
            {
                "id": scenario.id,
                "query": scenario.query,
                "expected_source_id": scenario.expected_source_id,
                "expected_section": scenario.expected_section,
                "actual_source_id": top[0].source_id if top else None,
                "actual_section": top[0].section if top else None,
                "matched": matched,
            }
        )
    return results


def run() -> dict:
    store = build_corpus()
    bm25 = BM25Index.from_vector_store(store)

    vector_retriever = Retriever(vector_store=store, embed_fn=_hashed_bow_embed)
    hybrid_retriever = Retriever(vector_store=store, embed_fn=_hashed_bow_embed, bm25_index=bm25)

    vector_results = _run_scenarios(vector_retriever)
    hybrid_results = _run_scenarios(hybrid_retriever)

    vector_accuracy = sum(r["matched"] for r in vector_results) / len(vector_results)
    hybrid_accuracy = sum(r["matched"] for r in hybrid_results) / len(hybrid_results)

    return {
        "scenario_count": len(SCENARIOS),
        "vector_only_top1_accuracy": vector_accuracy,
        "hybrid_top1_accuracy": hybrid_accuracy,
        "hybrid_beats_vector_only": hybrid_accuracy > vector_accuracy,
        "vector_only_results": vector_results,
        "hybrid_results": hybrid_results,
    }


if __name__ == "__main__":
    metrics = run()
    if "--write-baseline" in sys.argv:
        BASELINE_PATH.write_text(json.dumps(metrics, indent=2) + "\n")
        print(f"Wrote baseline to {BASELINE_PATH}")
    elif "--json" in sys.argv:
        print(json.dumps(metrics, indent=2))
    else:
        print(f"Scenarios: {metrics['scenario_count']}")
        print(f"Vector-only top-1 accuracy: {metrics['vector_only_top1_accuracy']:.0%}")
        print(f"Hybrid     top-1 accuracy: {metrics['hybrid_top1_accuracy']:.0%}")
        print(f"Hybrid beats vector-only: {metrics['hybrid_beats_vector_only']}")
        for r in metrics["hybrid_results"]:
            mark = "PASS" if r["matched"] else "FAIL"
            print(f"  [{mark}] {r['id']}: expected {r['expected_source_id']}/{r['expected_section']}, got {r['actual_source_id']}/{r['actual_section']}")
