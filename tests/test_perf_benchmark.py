from eval.perf_benchmark import _synthetic_packages, run_benchmark


def test_synthetic_packages_are_valid_and_deterministic():
    a = _synthetic_packages(20, seed=1)
    b = _synthetic_packages(20, seed=1)
    assert len(a) == 20
    assert [wp.work_package_id for wp in a] == [wp.work_package_id for wp in b]
    assert [wp.scheduled_start for wp in a] == [wp.scheduled_start for wp in b]


def test_run_benchmark_returns_sane_shape_for_small_counts():
    """
    Deliberately not asserting on elapsed_seconds' value -- timing is
    environment-dependent by nature, this only checks the shape and
    internal consistency of the result (pairwise_checks matches n choose 2,
    elapsed is non-negative, flagged count never exceeds package count).
    """
    metrics = run_benchmark(package_counts=[5, 10])
    assert len(metrics["runs"]) == 2
    for run in metrics["runs"]:
        n = run["package_count"]
        assert run["pairwise_checks"] == n * (n - 1) // 2
        assert run["elapsed_seconds"] >= 0
        assert 0 <= run["packages_with_conflicts"] <= n
