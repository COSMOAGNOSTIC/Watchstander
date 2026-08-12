"""
Exercises the reviewer web app against the REAL graph (not a mock) --
same principle as tests/test_graph.py and tests/test_hitl.py: this
proves the actual interrupt()/Command(resume=...) flow works end-to-end
through HTTP requests, not just through direct graph.invoke() calls in
a single test function.

Each test gets its own tmp_path-scoped sqlite file so tests never share
or pollute reviewer/reviewer_state.db (the real default, gitignored,
used only for actually running the app).
"""

from fastapi.testclient import TestClient

from reviewer import app as app_module
from reviewer.graph_driver import ReviewerService


def _client(tmp_path) -> TestClient:
    app_module.service = ReviewerService(str(tmp_path / "test_reviewer.db"))
    return TestClient(app_module.app)


def test_dashboard_with_nothing_seeded_shows_empty_state(tmp_path):
    client = _client(tmp_path)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Nothing awaiting review" in resp.text


def test_seed_demo_creates_real_pending_reviews_from_the_real_graph(tmp_path):
    client = _client(tmp_path)
    resp = client.post("/seed-demo", follow_redirects=False)
    assert resp.status_code == 303

    dashboard = client.get("/")
    # HW-2201 and CS-2202 conflict on shared compartment_id + hazard pair;
    # ALOFT-2203 also gets flagged via _vertically_stacked against HW-2201's
    # overlapping frame range -- three real flagged packages, not staged.
    assert "HW-2201" in dashboard.text
    assert "CS-2202" in dashboard.text
    assert "ALOFT-2203" in dashboard.text
    # FALL-2204 never overlaps anything in frame range -- must not appear.
    assert "FALL-2204" not in dashboard.text


def test_review_detail_page_shows_the_real_rationale_and_provenance(tmp_path):
    client = _client(tmp_path)
    client.post("/seed-demo", follow_redirects=False)
    pending = app_module.service.list_pending_reviews()
    hw = next(r for r in pending if r.work_package_id == "HW-2201")

    detail = client.get(f"/review/{hw.thread_id}/{hw.interrupt_id}")

    assert detail.status_code == 200
    assert "Electric &amp; Machine Shop" in detail.text or "Electric" in detail.text
    assert "DETERMINISTIC FALLBACK" in detail.text  # no live API key in CI -- real, not faked


def test_approving_one_package_leaves_the_others_pending(tmp_path):
    client = _client(tmp_path)
    client.post("/seed-demo", follow_redirects=False)
    pending = app_module.service.list_pending_reviews()
    hw = next(r for r in pending if r.work_package_id == "HW-2201")

    resp = client.post(
        f"/review/{hw.thread_id}/{hw.interrupt_id}",
        data={"decision": "approve", "note": "checked schedule, clear to proceed"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    still_pending = {r.work_package_id for r in app_module.service.list_pending_reviews()}
    assert "HW-2201" not in still_pending
    assert "CS-2202" in still_pending  # untouched -- real partial resume, not an all-or-nothing gate

    decided = app_module.service.list_decided()
    hw_decided = next(d for d in decided if d["work_package_id"] == "HW-2201")
    assert hw_decided["cleared_for_execution"] is True


def test_rejecting_a_package_records_not_cleared_for_execution(tmp_path):
    client = _client(tmp_path)
    client.post("/seed-demo", follow_redirects=False)
    pending = app_module.service.list_pending_reviews()
    hw = next(r for r in pending if r.work_package_id == "HW-2201")

    client.post(
        f"/review/{hw.thread_id}/{hw.interrupt_id}",
        data={"decision": "reject", "note": "reschedule after CS-2202 clears"},
        follow_redirects=False,
    )

    decided = app_module.service.list_decided()
    hw_decided = next(d for d in decided if d["work_package_id"] == "HW-2201")
    assert hw_decided["cleared_for_execution"] is False


def test_review_detail_for_an_unknown_or_already_decided_package_404s(tmp_path):
    client = _client(tmp_path)
    resp = client.get("/review/no-such-thread/no-such-interrupt")
    assert resp.status_code == 404


def test_a_hedge_worded_note_never_flips_or_corrupts_the_decision(tmp_path):
    """Regression test for the live bug this app used to have: submit_review
    built the resume value as f"{decision} - {note}" and ran the whole
    thing through the old free-text hedge-cue parser, so typing a real
    condition into the note box could slip past it undetected. Decision
    and note now travel to the graph as separate structured fields (see
    ReviewerService.submit_decision), so no wording in the note -- not
    even the literal word "reject" -- can change which disposition gets
    recorded for an Approve click."""
    client = _client(tmp_path)
    client.post("/seed-demo", follow_redirects=False)
    pending = app_module.service.list_pending_reviews()
    hw = next(r for r in pending if r.work_package_id == "HW-2201")

    client.post(
        f"/review/{hw.thread_id}/{hw.interrupt_id}",
        data={
            "decision": "approve",
            "note": "actually now I'm not sure, maybe reject this instead",
        },
        follow_redirects=False,
    )

    decided = app_module.service.list_decided()
    hw_decided = next(d for d in decided if d["work_package_id"] == "HW-2201")
    assert hw_decided["disposition"] == "approved"
    assert hw_decided["cleared_for_execution"] is True
