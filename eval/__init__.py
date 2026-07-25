"""
Watchstander evaluation harness.

Three pieces, per MIGRATION.md Phase 5.5 / the external-review follow-up:

- `scenarios.py` -- a fixed, hand-designed, checked-in suite of work-package
  scenarios and retrieval/reasoning queries. Not generated, not sampled --
  every scenario is a deliberate example of one behavior worth measuring,
  including the domain-correctness gaps the Fable/ChatGPT/Grok reviews
  already found (adjacency tolerance, is_over_side rationale mislabeling,
  the dead deck_level axis). Those gaps are scenarios *on purpose* -- the
  point of this harness is to turn "a reviewer noticed this by reading
  code" into "CI measures this on every run," not to hide them.

- `run_eval.py` -- a runner that exercises the real, non-mocked system
  (`deconfliction.find_all_conflicts`, `retrieval.cite_best_matching_case`,
  `reasoning.generate_safety_brief`'s deterministic fallback) against every
  scenario and produces a metrics dict. Zero API keys, zero network calls --
  same constraint as the rest of the test suite.

- `baseline.json` -- the metrics dict from the last intentional run,
  checked into git. `tests/test_eval_harness.py` re-runs the harness and
  asserts the live result matches this file byte-for-byte. A mismatch
  means something about the system's actual behavior changed -- for
  better or worse -- and the baseline must be consciously regenerated and
  reviewed as part of that change, not silently accepted.

This intentionally measures the current gaps as they exist as of the
2026-07-25 external review response. If a future change closes one of the
known gaps below, that will show up here as a metrics mismatch requiring
the baseline to be regenerated -- which is a feature, not friction: it's
the harness noticing the system got better and forcing that to be a
reviewed, visible event instead of a change nobody would otherwise measure.
"""
