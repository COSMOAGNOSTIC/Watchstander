"""
Evaluation harness runner.

Exercises the real, non-mocked pipeline -- agent_core.deconfliction,
agent_core.retrieval, agent_core.reasoning's deterministic fallback --
against the fixed scenario suite in eval/scenarios.py, and produces a
single JSON-serializable metrics dict.

No API keys, no network calls: ANTHROPIC_API_KEY is deliberately left
unset for the reasoning scenarios so generate_safety_brief() always takes
the deterministic-fallback path, same constraint the rest of the test
suite runs under.

Usage:
    python -m eval.run_eval                 # print a human-readable report
    python -m eval.run_eval --json          # print the raw metrics dict
    python -m eval.run_eval --write-baseline  # overwrite eval/baseline.json
"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

from agent_core.deconfliction import find_all_conflicts
from agent_core.reasoning import generate_safety_brief
from agent_core.retrieval import cite_best_matching_case
from eval.scenarios import CONFLICT_SCENARIOS, RETRIEVAL_SCENARIOS

BASELINE_PATH = Path(__file__).parent / "baseline.json"


def _run_conflict_scenarios() -> dict:
    results = []
    for scenario in CONFLICT_SCENARIOS:
        # Deep-copy so scenarios never leak mutated state into each other --
        # find_all_conflicts mutates .conflicts/.conflict_rationale in place.
        packages = copy.deepcopy(scenario.packages)
        find_all_conflicts(packages)
        by_id = {wp.work_package_id: wp for wp in packages}

        a_id, b_id = scenario.pair
        actual_conflict = b_id in by_id[a_id].conflicts

        entry = {
            "id": scenario.id,
            "category": scenario.category,
            "expected_conflict": scenario.expected_conflict,
            "actual_conflict": actual_conflict,
            "matches_expected": actual_conflict == scenario.expected_conflict,
            "domain_correct": scenario.correct,
        }

        if scenario.rationale_check is not None:
            rationale = by_id[a_id].conflict_rationale or ""
            entry["rationale_check_passed"] = scenario.rationale_check(rationale)

        if scenario.id == "tp-multi-conflict-single-package":
            entry["conflict_count_for_a"] = len(by_id[a_id].conflicts)
            entry["conflicts_with_third_package"] = "WP-14C" in by_id[a_id].conflicts

        results.append(entry)
    return {"scenarios": results}


def _run_retrieval_scenarios() -> dict:
    results = []
    for scenario in RETRIEVAL_SCENARIOS:
        citation = cite_best_matching_case(scenario.query, scenario.hazards)
        actual_case_id = (
            citation.removeprefix("Precedent: ").split(" (", 1)[0] if citation else None
        )
        results.append(
            {
                "id": scenario.id,
                "expected_case_id": scenario.expected_case_id,
                "actual_case_id": actual_case_id,
                "matches_expected": actual_case_id == scenario.expected_case_id,
            }
        )
    return {"scenarios": results}


def _run_reasoning_check() -> dict:
    """
    Confirms generate_safety_brief() takes the deterministic-fallback path
    with no API key configured, and that the resulting brief is grounded
    (non-empty, provenance-tagged, references the real conflict rationale).
    """
    assert "ANTHROPIC_API_KEY" not in os.environ, (
        "eval harness must run with no ANTHROPIC_API_KEY set so it measures the "
        "deterministic-fallback path -- same zero-network-call constraint as the "
        "rest of the test suite."
    )

    packages = copy.deepcopy(
        [s for s in CONFLICT_SCENARIOS if s.id == "tp-hotwork-confined-same-compartment"][0].packages
    )
    find_all_conflicts(packages)
    wp = next(p for p in packages if p.work_package_id == "WP-01A")
    brief = generate_safety_brief(wp)

    return {
        "source": brief.source,
        "is_deterministic_fallback": brief.source == "deterministic-fallback",
        "provenance_tag_present": "[SOURCE: DETERMINISTIC FALLBACK" in brief.executive_summary,
        "executive_summary_non_empty": bool(brief.executive_summary.strip()),
        "precedent_context_non_empty": bool(brief.precedent_context.strip()),
        "recommended_action_non_empty": bool(brief.recommended_action.strip()),
        "references_conflict_rationale": bool(wp.conflict_rationale)
        and (wp.conflict_rationale in brief.executive_summary),
    }


def run() -> dict:
    conflict_results = _run_conflict_scenarios()
    retrieval_results = _run_retrieval_scenarios()
    reasoning_result = _run_reasoning_check()

    total_conflict = len(conflict_results["scenarios"])
    matches = sum(1 for s in conflict_results["scenarios"] if s["matches_expected"])
    domain_correct = sum(1 for s in conflict_results["scenarios"] if s["domain_correct"])

    total_retrieval = len(retrieval_results["scenarios"])
    retrieval_matches = sum(1 for s in retrieval_results["scenarios"] if s["matches_expected"])

    summary = {
        "conflict_scenarios_total": total_conflict,
        "conflict_scenarios_behavior_matches_expected": matches,
        "conflict_scenarios_domain_correct": domain_correct,
        "conflict_scenarios_known_gaps": total_conflict - domain_correct,
        "retrieval_scenarios_total": total_retrieval,
        "retrieval_scenarios_matches_expected": retrieval_matches,
        "reasoning_deterministic_fallback_healthy": reasoning_result["is_deterministic_fallback"]
        and reasoning_result["provenance_tag_present"]
        and reasoning_result["executive_summary_non_empty"]
        and reasoning_result["precedent_context_non_empty"]
        and reasoning_result["recommended_action_non_empty"]
        and reasoning_result["references_conflict_rationale"],
    }

    return {
        "summary": summary,
        "conflict_scenarios": conflict_results["scenarios"],
        "retrieval_scenarios": retrieval_results["scenarios"],
        "reasoning_check": reasoning_result,
    }


def _print_report(metrics: dict) -> None:
    s = metrics["summary"]
    print("Watchstander evaluation harness")
    print("=" * 60)
    print(
        f"Conflict scenarios: {s['conflict_scenarios_behavior_matches_expected']}/"
        f"{s['conflict_scenarios_total']} match documented expected behavior"
    )
    print(
        f"  Domain-correct: {s['conflict_scenarios_domain_correct']}/{s['conflict_scenarios_total']}"
        f"  ({s['conflict_scenarios_known_gaps']} known gaps, documented on purpose)"
    )
    print(
        f"Retrieval scenarios: {s['retrieval_scenarios_matches_expected']}/"
        f"{s['retrieval_scenarios_total']} correct case selected"
    )
    print(f"Reasoning deterministic fallback healthy: {s['reasoning_deterministic_fallback_healthy']}")
    print()
    print("Known gaps (by design -- see ARCHITECTURE.md Known Debt):")
    for entry in metrics["conflict_scenarios"]:
        if not entry["domain_correct"]:
            print(f"  - {entry['id']}  (category={entry['category']})")

    unexpected = [e for e in metrics["conflict_scenarios"] if not e["matches_expected"]]
    unexpected += [e for e in metrics["retrieval_scenarios"] if not e["matches_expected"]]
    if unexpected:
        print()
        print("UNEXPECTED (behavior changed since scenarios were authored):")
        for entry in unexpected:
            print(f"  - {entry['id']}")


if __name__ == "__main__":
    metrics = run()
    if "--write-baseline" in sys.argv:
        BASELINE_PATH.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
        print(f"Wrote {BASELINE_PATH}")
    elif "--json" in sys.argv:
        print(json.dumps(metrics, indent=2, sort_keys=True))
    else:
        _print_report(metrics)
