"""
Real HITL reviewer web app.

The visualizer (visualizer/) shows *that* something is flagged and
waiting -- deliberately, per agent_core/events.py's broadcast policy, it
never shows *why* (full description, conflict rationale, synthesized
safety brief). This app is the other half: a local-only page where a
human sees the full brief -- including whether it came from a live LLM
call or the deterministic fallback (`safety_brief_provenance`) -- and a
real Approve / Reject form that resumes the actual LangGraph
`interrupt()`, not a simulated decision. See ARCHITECTURE.md ADR-024 for
why this is a separate, local-only channel rather than loosening
events.py's public broadcast policy.

Run: `uvicorn reviewer.app:app --reload` from the repo root (see
reviewer/README.md). No auth, no HTTPS, no multi-user support -- built
for one local reviewer working the queue on their own machine, the same
trust boundary the visualizer's undefended ws://localhost:8081 already
assumes. Not safe to expose beyond localhost as-is -- see Known Debt in
ARCHITECTURE.md.
"""

from __future__ import annotations

import html
import uuid

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from reviewer.graph_driver import ReviewerService

app = FastAPI(title="Watchstander HITL Reviewer")
service = ReviewerService()

_PAGE_STYLE = """
<style>
  body { background:#0a1420; color:#cfe6ff; font-family: -apple-system, Segoe UI, sans-serif;
         max-width: 900px; margin: 2rem auto; padding: 0 1rem; }
  h1, h2 { color: #7ec8ff; }
  a { color: #7ec8ff; }
  .card { background:#101f30; border:1px solid #244160; border-radius:8px;
          padding:1rem 1.25rem; margin-bottom:1rem; }
  .risk-critical, .risk-high { color:#ff8a8a; }
  .risk-moderate { color:#ffd27e; }
  .risk-low { color:#9adba8; }
  .provenance { display:inline-block; font-size:0.8rem; padding:0.15rem 0.5rem;
                border-radius:4px; background:#1c3350; color:#a9c8e6; margin-top:0.4rem; }
  .provenance.llm { background:#1c4a2f; color:#9adba8; }
  button { font-size:1rem; padding:0.5rem 1.25rem; border-radius:6px; border:none;
           cursor:pointer; margin-right:0.5rem; }
  .approve { background:#1c6b3a; color:white; }
  .reject { background:#7a1f1f; color:white; }
  textarea { width:100%; background:#0a1420; color:#cfe6ff; border:1px solid #244160;
             border-radius:6px; padding:0.5rem; margin:0.5rem 0; }
  .empty { color:#6e91b3; font-style:italic; }
  .decided { color:#6e91b3; font-size:0.9rem; }
</style>
"""


def _risk_class(risk_level: str) -> str:
    return f"risk-{risk_level.lower()}" if risk_level else ""


def _provenance_class(provenance: str | None) -> str:
    return "provenance llm" if provenance and "LLM SYNTHESIS" in provenance else "provenance"


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    pending = service.list_pending_reviews()
    decided = service.list_decided()

    if pending:
        cards = "\n".join(
            f"""<div class="card">
                <h2>{html.escape(r.work_package_id)}
                    <span class="{_risk_class(r.risk_level)}">[{html.escape(r.risk_level)}]</span></h2>
                <p>{html.escape(', '.join(r.hazard_categories))}</p>
                <span class="{_provenance_class(r.safety_brief_provenance)}">
                    {html.escape(r.safety_brief_provenance or 'no brief yet')}</span>
                <p><a href="/review/{html.escape(r.thread_id)}/{html.escape(r.interrupt_id)}">
                    Open full review &rarr;</a></p>
            </div>"""
            for r in pending
        )
    else:
        cards = '<p class="empty">Nothing awaiting review right now.</p>'

    if decided:
        decided_rows = "\n".join(
            f'<div class="decided">{html.escape(d["work_package_id"])} '
            f'&mdash; {html.escape(str(d["disposition"]))} '
            f'(cleared_for_execution={d["cleared_for_execution"]})</div>'
            for d in decided
        )
    else:
        decided_rows = '<p class="empty">Nothing decided yet.</p>'

    return f"""<!doctype html><html><head><title>Watchstander HITL Reviewer</title>{_PAGE_STYLE}</head>
    <body>
        <h1>Watchstander &mdash; Safety Review Queue</h1>
        <form method="post" action="/seed-demo">
            <button type="submit">Seed a real ACUSHNET demo run</button>
        </form>
        <h2>Awaiting review</h2>
        {cards}
        <h2>Recently decided</h2>
        {decided_rows}
    </body></html>"""


@app.post("/seed-demo")
def seed_demo() -> RedirectResponse:
    thread_id = f"reviewer-{uuid.uuid4().hex[:12]}"
    service.seed_demo(thread_id)
    return RedirectResponse(url="/", status_code=303)


@app.get("/review/{thread_id}/{interrupt_id}", response_class=HTMLResponse)
def review_detail(thread_id: str, interrupt_id: str) -> HTMLResponse:
    review = service.get_pending_review(thread_id, interrupt_id)
    if review is None:
        return HTMLResponse(
            f"""<!doctype html><html><head>{_PAGE_STYLE}</head><body>
            <p>No pending review found for this package &mdash; it may already have been decided.</p>
            <p><a href="/">&larr; back to queue</a></p></body></html>""",
            status_code=404,
        )

    brief_html = "<p class=\"empty\">No safety brief was synthesized for this package.</p>"
    if review.safety_brief:
        b = review.safety_brief
        brief_html = f"""
            <p><strong>Executive summary:</strong> {html.escape(b.get('executive_summary', ''))}</p>
            <p><strong>Precedent context:</strong> {html.escape(b.get('precedent_context', ''))}</p>
            <p><strong>Recommended action:</strong> {html.escape(b.get('recommended_action', ''))}</p>
        """

    return f"""<!doctype html><html><head><title>Review {html.escape(review.work_package_id)}</title>
    {_PAGE_STYLE}</head><body>
        <p><a href="/">&larr; back to queue</a></p>
        <h1>{html.escape(review.work_package_id)}
            <span class="{_risk_class(review.risk_level)}">[{html.escape(review.risk_level)}]</span></h1>
        <div class="card">
            <p><strong>Description:</strong> {html.escape(review.description)}</p>
            <p><strong>Hazard categories:</strong> {html.escape(', '.join(review.hazard_categories))}</p>
            <p><strong>Why it was flagged:</strong> {html.escape(review.conflict_rationale or '(no rationale recorded)')}</p>
            <span class="{_provenance_class(review.safety_brief_provenance)}">
                {html.escape(review.safety_brief_provenance or 'no brief yet')}</span>
            {brief_html}
        </div>
        <form method="post" action="/review/{html.escape(thread_id)}/{html.escape(interrupt_id)}">
            <label>Note (optional, appended to the decision record):</label>
            <textarea name="note" rows="2"></textarea>
            <button class="approve" type="submit" name="decision" value="approve">Approve</button>
            <button class="reject" type="submit" name="decision" value="reject">Reject</button>
        </form>
    </body></html>"""


@app.post("/review/{thread_id}/{interrupt_id}")
def submit_review(thread_id: str, interrupt_id: str, decision: str = Form(...), note: str = Form("")) -> RedirectResponse:
    decision_text = decision if not note.strip() else f"{decision} - {note.strip()}"
    service.submit_decision(thread_id, interrupt_id, decision_text)
    return RedirectResponse(url="/", status_code=303)
