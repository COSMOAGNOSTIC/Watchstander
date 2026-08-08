"""
Regression guard for Phase 2's actual Definition of Done (MIGRATION.md):
"Hybrid retrieval measurably beats vector-only on the eval set."

Re-runs the real eval harness (same corpus, same scenarios, same
deterministic hashed-BOW embedder -- no live network/model) and asserts
against the checked-in baseline.json, so a future change that quietly
regresses hybrid back to a tie (or worse) fails CI instead of just
looking fine in a manual `python -m retrieval.eval.run_eval` run.
"""

import json
from pathlib import Path

from retrieval.eval.run_eval import BASELINE_PATH, run


def test_hybrid_measurably_beats_vector_only_on_the_eval_set():
    """The literal Phase 2 Definition of Done -- not a tie, not close,
    strictly greater."""
    metrics = run()
    assert metrics["hybrid_beats_vector_only"] is True
    assert metrics["hybrid_top1_accuracy"] > metrics["vector_only_top1_accuracy"]


def test_eval_results_match_the_checked_in_baseline():
    """Catches silent regressions/improvements in either direction --
    if retrieval behavior changes, the baseline should be regenerated
    deliberately (--write-baseline), not drift unnoticed."""
    assert Path(BASELINE_PATH).exists(), "baseline.json missing -- run with --write-baseline first"
    baseline = json.loads(Path(BASELINE_PATH).read_text())
    metrics = run()

    assert metrics["vector_only_top1_accuracy"] == baseline["vector_only_top1_accuracy"]
    assert metrics["hybrid_top1_accuracy"] == baseline["hybrid_top1_accuracy"]
    assert metrics["hybrid_results"] == baseline["hybrid_results"]
    assert metrics["vector_only_results"] == baseline["vector_only_results"]
