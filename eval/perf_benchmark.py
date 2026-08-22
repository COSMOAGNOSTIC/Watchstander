"""
Detection-latency benchmark for `deconfliction.find_all_conflicts`.

Watchstander's eval/ harness scores *correctness* against a fixed scenario
suite but never *speed*. This module answers how fast the deterministic
detection path actually runs, at a scale worth quoting.

Deliberately separate from eval/run_eval.py, not folded into it: `run()`'s
result is asserted for *exact* equality against the checked-in
eval/baseline.json (see tests/test_eval_harness.py) -- wall-clock timing
is inherently non-deterministic across machines and runs, so mixing it
into that dict would make the regression gate flaky by construction. This
script's output is meant to be read and quoted, not diffed byte-for-byte.

Synthetic data only, generated here with a fixed seed for reproducibility
-- not sourced case data (case_data/) and not the real-ship demo fixtures
(agent_core/demo_fixtures.py). Keeping this distinction explicit matches
the "two kinds of data sourcing" convention ARCHITECTURE.md's Section 4
already documents for case citations.

Usage:
    python -m eval.perf_benchmark                # human-readable report
    python -m eval.perf_benchmark --json          # machine-readable
"""

from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime, timedelta
from math import comb

from agent_core.deconfliction import find_all_conflicts
from agent_core.state import HazardCategory, SpatialCoordinates, WorkPackageState

_HAZARDS = list(HazardCategory)


def _synthetic_packages(n: int, seed: int = 42) -> list[WorkPackageState]:
    """
    Generates `n` synthetic work packages with a realistic mix of
    overlapping and non-overlapping frame ranges, schedules, and hazard
    categories, so the resulting conflict count is neither 0 nor n*(n-1)/2
    -- a benchmark that only ever hits the pipeline's fast-exit or its
    worst case wouldn't say much about real-world timing. Deterministic
    (fixed seed) so a benchmark run is reproducible, not a new dataset
    every invocation.
    """
    rng = random.Random(seed)
    base_time = datetime(2026, 9, 1, 0, 0)
    packages = []
    for i in range(n):
        frame_start = rng.randint(0, 200)
        start_offset_hours = rng.randint(0, 24 * 14)
        packages.append(
            WorkPackageState(
                work_package_id=f"SYN-{i:04d}",
                description="synthetic benchmark package",
                hazard_categories=[rng.choice(_HAZARDS)],
                spatial=SpatialCoordinates(
                    frame_start=frame_start,
                    frame_end=frame_start + rng.randint(2, 15),
                    compartment_id=f"COMPT-{rng.randint(0, 20)}",
                    is_aloft=rng.random() < 0.15,
                    is_over_side=rng.random() < 0.05,
                ),
                scheduled_start=base_time + timedelta(hours=start_offset_hours),
                scheduled_end=base_time + timedelta(hours=start_offset_hours + rng.randint(1, 8)),
            )
        )
    return packages


def run_benchmark(package_counts: list[int] = (10, 25, 50, 100, 200)) -> dict:
    """
    Times `find_all_conflicts` at each package count in `package_counts`.
    Returns a JSON-serializable dict; see `_print_report` for the
    human-readable form.
    """
    results = []
    for n in package_counts:
        packages = _synthetic_packages(n)
        start = time.perf_counter()
        find_all_conflicts(packages)
        elapsed = time.perf_counter() - start

        conflicts_found = sum(1 for wp in packages if wp.conflicts)
        pairwise_checks = comb(n, 2)

        results.append(
            {
                "package_count": n,
                "pairwise_checks": pairwise_checks,
                "packages_with_conflicts": conflicts_found,
                "elapsed_seconds": elapsed,
                "checks_per_second": pairwise_checks / elapsed if elapsed > 0 else None,
            }
        )
    return {"runs": results}


def _print_report(metrics: dict) -> None:
    print("Watchstander deterministic-detection benchmark")
    print("=" * 60)
    print(f"{'packages':>10}  {'pairwise checks':>16}  {'flagged':>8}  {'elapsed (s)':>12}  {'checks/sec':>12}")
    for r in metrics["runs"]:
        cps = f"{r['checks_per_second']:,.0f}" if r["checks_per_second"] else "n/a"
        print(
            f"{r['package_count']:>10}  {r['pairwise_checks']:>16,}  "
            f"{r['packages_with_conflicts']:>8}  {r['elapsed_seconds']:>12.4f}  {cps:>12}"
        )
    print()
    print(
        "Zero LLM calls, zero network access at any package count above -- "
        "detection is pure Python geometry/hazard-pair comparison (ADR-001)."
    )


if __name__ == "__main__":
    metrics = run_benchmark()
    if "--json" in sys.argv:
        print(json.dumps(metrics, indent=2))
    else:
        _print_report(metrics)
