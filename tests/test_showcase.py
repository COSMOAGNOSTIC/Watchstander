"""Session 12 showcase mockup: the page draws only from a snapshot of the real checks."""

import json

import pytest

from agent_core import daily_brief
from agent_core.carrier_demo import load_carrier_dataset
from showcase import build_mockup, export_snapshot


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_snapshot_matches_the_real_checks():
    snap = export_snapshot.snapshot()
    run = daily_brief.run_checks(load_carrier_dataset(), export_snapshot.AS_OF)
    status = {k: v.value for k, v in run.status_by_package().items()}
    rules = run.rules_by_package()
    assert {p["id"]: p["status"] for p in snap["packages"]} == status
    assert {p["id"]: {r["id"] for r in p["rules"]} for p in snap["packages"]} == rules
    assert snap["notional"] is True and "no LLM" in snap["generated_by"]
    for p in snap["packages"]:
        if p["suggestion"] and p["suggestion"]["available"]:
            assert run.shift_outcomes[p["id"]].suggestion.applied is False


def test_built_page_inlines_the_snapshot_and_nothing_else(tmp_path, monkeypatch):
    out = build_mockup.build()
    html = out.read_text()
    assert "__SNAPSHOT_JSON__" not in html
    start = html.index('<script type="application/json" id="snap">') + len('<script type="application/json" id="snap">')
    data = json.loads(html[start:html.index("</script>", start)])
    assert data == export_snapshot.snapshot()
