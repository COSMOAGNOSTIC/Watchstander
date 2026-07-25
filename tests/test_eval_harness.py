"""
Regression gate for the evaluation harness (eval/).

This test re-runs the real, non-mocked eval harness (eval/run_eval.py
against eval/scenarios.py) and asserts the result matches the checked-in
eval/baseline.json exactly. A mismatch means the system's actual
behavior on a fixed, known scenario changed -- for better or worse -- and
is a signal to look at the diff, not a signal to blindly regenerate the
baseline.

This is deliberately distinct from tests/test_deconfliction.py and
tests/test_retrieval.py: those test individual functions in isolation
with ad hoc fixtures. This test exercises the same ~20 scenarios every
time, checked into git, so a change in scoring is visible as a diff on
eval/baseline.json in the PR that caused it -- exactly the "fixed
scenario suite + comparison against a checked-in baseline" pattern
called out in the 2026-07-25 external review response (see MIGRATION.md
Phase 5.5, ARCHITECTURE.md Section 7).

To intentionally update the baseline after a real, reviewed behavior
change:

    ANTHROPIC_API_KEY= python -m eval.run_eval --write-baseline

then diff eval/baseline.json in the commit and confirm every changed
scenario is an intentional, understood change -- not a silent
regression.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from eval.run_eval import BASELINE_PATH, run

# The known-gap and debatable scenarios that are *expected* to be
# domain-incorrect today (see eval/scenarios.py docstrings and
# ARCHITECTURE.md's Known Debt table). This list exists so that if one
# of these gaps gets fixed, this test fails loudly with a clear message
# instead of just silently passing -- closing a known gap is exactly the
# kind of change that should require a conscious baseline update.
EXPECTED_KNOWN_GAP_IDS = {
    "gap-adjacent-frames-not-touching",
    "gap-two-aloft-packages-stacked",
    "gap-simultaneous-confined-space-entries",
    "debatable-aloft-fall-protection-compliant-config",
}


@pytest.fixture(autouse=True)
def _no_api_key(monkeypatch):
    """
    The eval harness measures the deterministic-fallback reasoning path
    on purpose -- same zero-network-call constraint as the rest of the
    test suite. Strip any locally-set key so this test is reproducible
    in CI and on a laptop with a key in the environment alike.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_baseline_file_exists_and_is_valid_json():
    assert BASELINE_PATH.exists(), (
        "eval/baseline.json is missing. Generate it with "
        "`python -m eval.run_eval --write-baseline` and check it in."
    )
    json.loads(BASELINE_PATH.read_text())


def test_eval_harness_matches_checked_in_baseline():
    baseline = json.loads(BASELINE_PATH.read_text())
    live = run()

    assert live == baseline, (
        "The eval harness result no longer matches eval/baseline.json. "
        "This means a real behavior change happened in deconfliction.py, "
        "retrieval.py, or reasoning.py's fallback path. If this change was "
        "intentional and reviewed, regenerate the baseline with "
        "`python -m eval.run_eval --write-baseline` and check in the diff -- "
        "do not regenerate blindly without reading what changed."
    )


def test_all_conflict_scenarios_match_their_own_documented_expectation():
    """
    Every scenario's `expected_conflict` field is itself a claim about
    current behavior (see eval/scenarios.py). This checks the scenario
    authoring is internally consistent with the live code, independent
    of the baseline file -- a belt-and-suspenders check in case
    baseline.json itself ever drifts from scenarios.py without anyone
    updating the other.
    """
    live = run()
    mismatches = [s for s in live["conflict_scenarios"] if not s["matches_expected"]]
    assert not mismatches, f"Scenarios whose documented expectation no longer holds: {mismatches}"


def test_all_retrieval_scenarios_match_their_own_documented_expectation():
    live = run()
    mismatches = [s for s in live["retrieval_scenarios"] if not s["matches_expected"]]
    assert not mismatches, f"Retrieval scenarios that no longer resolve as documented: {mismatches}"


def test_known_gaps_are_exactly_the_documented_set():
    """
    If this fails because a gap ID is MISSING from the live results, a
    known domain gap just got fixed -- great news, update
    EXPECTED_KNOWN_GAP_IDS here and eval/baseline.json together, and
    consider updating ARCHITECTURE.md's Known Debt table too.

    If this fails because a NEW, undocumented gap ID showed up, a
    scenario that used to be domain-correct silently regressed -- that's
    a real bug to fix, not a baseline update.
    """
    live = run()
    live_gap_ids = {s["id"] for s in live["conflict_scenarios"] if not s["domain_correct"]}
    assert live_gap_ids == EXPECTED_KNOWN_GAP_IDS


def test_reasoning_check_runs_deterministic_fallback_and_is_grounded():
    live = run()
    check = live["reasoning_check"]
    assert check["source"] == "deterministic-fallback"
    assert check["provenance_tag_present"]
    assert check["executive_summary_non_empty"]
    assert check["precedent_context_non_empty"]
    assert check["recommended_action_non_empty"]
    assert check["references_conflict_rationale"]
