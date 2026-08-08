"""
Fixed scenario suite for the Phase 2 eval harness (see run_eval.py).

Each scenario is a real query against real, ingested corpus text, with the
correct (source_id, section) hand-verified against the actual source files
in retrieval/sources/ and case_data/cases_v1.json -- not invented section
numbers. Spans all three corpus sources so the eval reflects real
cross-corpus retrieval, not one document in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    query: str
    expected_source_id: str
    expected_section: str | None


SCENARIOS: list[Scenario] = [
    # NAVSEA 8010 Chapter 4 -- Hot Work and Fire Watch
    Scenario(
        id="navsea-4.4.3-fire-watch-capacity",
        query="how many hot workers can a single fire watch supervise",
        expected_source_id="navsea_8010_ch4",
        expected_section="4.4.3",
    ),
    Scenario(
        id="navsea-4.2.1-written-notice",
        query="written notice required before hot work begins",
        expected_source_id="navsea_8010_ch4",
        expected_section="4.2.1",
    ),
    Scenario(
        id="navsea-4.3.6-ammunition",
        query="hot work operations near ammunition or explosives",
        expected_source_id="navsea_8010_ch4",
        expected_section="4.3.6",
    ),
    # NAVSEA 8010 Chapter 11 -- Fire and Smoke Boundaries
    Scenario(
        id="navsea-11.1.6-boundary-record",
        query="record of boundary openings and access cuts",
        expected_source_id="navsea_8010_ch11",
        expected_section="11.1.6",
    ),
    Scenario(
        id="navsea-11.1.7-carrier-hangar",
        query="hangar division door travel paths on carrier type ships",
        expected_source_id="navsea_8010_ch11",
        expected_section="11.1.7",
    ),
    Scenario(
        id="navsea-11.2.2-smoke-boundary",
        query="what is a smoke boundary set during a fire",
        expected_source_id="navsea_8010_ch11",
        expected_section="11.2.2",
    ),
    # OSHA 29 CFR 1915 Subpart B -- Confined and Enclosed Spaces
    Scenario(
        id="osha-1915.12-oxygen-threshold",
        query="an employee may not enter a space where oxygen content by volume is below 19.5 percent",
        expected_source_id="osha_1915_subpart_b",
        expected_section="1915.12",
    ),
    Scenario(
        id="osha-1915.14-marine-chemist",
        query="hot work certified safe by a marine chemist or coast guard authorized person",
        expected_source_id="osha_1915_subpart_b",
        expected_section="1915.14",
    ),
    Scenario(
        id="osha-1915.16-warning-labels",
        query="warning signs and labels must be understood by all employees",
        expected_source_id="osha_1915_subpart_b",
        expected_section="1915.16",
    ),
    # case_data/cases_v1.json -- sourced incident cases
    Scenario(
        id="case-stjohns-confined-space",
        query="welder entered a space without atmospheric testing for oxygen deficiency",
        expected_source_id="cases_v1",
        expected_section="CS-2023-STJOHNS",
    ),
    Scenario(
        id="case-firstmarine-explosion",
        query="explosion from flammable gases during welding cutting operations",
        expected_source_id="cases_v1",
        expected_section="HW-FIRSTMARINE",
    ),
]
