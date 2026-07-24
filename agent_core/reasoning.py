"""
LLM reasoning / synthesis node.

Phase 2: takes a flagged conflict (deterministic output of deconfliction.py)
plus the grounded case citation (case_lookup.py) and produces a plain-
language SafetyBrief for the human reviewer at the HITL gate.

Hard rule (see MIGRATION.md Phase 2 / PASSDOWN.md team roles): the LLM
never decides whether a conflict exists -- that decision was already made
deterministically upstream in deconfliction.py. This node is pure
synthesis: turn real, already-verified data (conflict rationale + sourced
case) into a reviewer-facing narrative.

Grounding: the only facts available to the model are the ones explicitly
assembled in `_grounding_context()`. The system prompt instructs the model
to work only from those facts and never invent case IDs, shipyards, dates,
or outcomes. Whenever no live API key is configured -- which is always
true in CI -- `generate_safety_brief()` falls back to
`_deterministic_fallback()`, which builds the brief directly from that
same grounding context with no model call at all. That keeps
`python -m pytest -v` green with zero API keys and zero network calls in
the test suite, while still producing a real, case-grounded brief.
"""

from __future__ import annotations

import json
import os

from agent_core.case_lookup import cite_best_case
from agent_core.state import SafetyBrief, WorkPackageState

_SYSTEM_PROMPT = (
    "You are a shipyard safety synthesis assistant. You are given a "
    "deterministically-flagged work package conflict and, if available, a "
    "single sourced OSHA/DOL case citation. Respond with ONLY a JSON object "
    "with exactly these keys: executive_summary (2 sentences max, plain "
    "language, for a Safety Officer), precedent_context (plain-language "
    "summary of what happened in the cited case -- if no case is given, "
    "say so explicitly, do not invent one), and recommended_action (a "
    "concrete deconfliction step, e.g. reschedule / add a barrier / verify "
    "permit). Use ONLY the facts given below. Do not invent case IDs, "
    "shipyards, dates, or outcomes that are not present in the input."
)

_REQUIRED_LLM_KEYS = ("executive_summary", "precedent_context", "recommended_action")


def _grounding_context(wp: WorkPackageState) -> dict:
    """
    The complete, explicit set of facts this node is allowed to reason
    over. Nothing outside this dict reaches the model or the fallback --
    that's what makes both paths auditable.
    """
    return {
        "work_package_id": wp.work_package_id,
        "description": wp.description,
        "hazard_categories": list(wp.hazard_categories),
        "conflicts_with": list(wp.conflicts),
        "conflict_rationale": wp.conflict_rationale,
        "case_citation": cite_best_case(wp.hazard_categories),
    }


def _call_llm(context: dict) -> dict | None:
    """
    Attempts a live model call. Returns None -- which triggers the
    deterministic fallback -- if no API key is configured, the
    `anthropic` package isn't installed, or the model response isn't
    well-formed. This is the expected path in CI and for anyone running
    the repo without a key; it is never treated as an error.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None

    try:
        import anthropic
    except ImportError:
        return None

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(context)}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None

    if not all(key in parsed for key in _REQUIRED_LLM_KEYS):
        return None
    return {key: parsed[key] for key in _REQUIRED_LLM_KEYS}


def _deterministic_fallback(context: dict) -> dict:
    """
    Builds a SafetyBrief straight from the grounding context, with no
    model call. Every sentence is templated directly from real fields --
    nothing here can be a hallucination because nothing here is
    generated, it's assembled from data that was already verified
    upstream.
    """
    wp_id = context["work_package_id"]
    conflicts = ", ".join(context["conflicts_with"]) or "an overlapping work package"

    executive_summary = (
        f"{wp_id} was flagged for a spatial/temporal conflict with {conflicts}. "
        f"{context['conflict_rationale']}"
    )

    citation = context["case_citation"]
    precedent_context = citation or (
        "No sourced case on file yet for this hazard category "
        "(case_data expansion is tracked in MIGRATION.md Phase 4)."
    )

    recommended_action = (
        f"Do not run {wp_id} concurrently with {conflicts} in the affected "
        f"spatial envelope until a competent person confirms deconfliction "
        f"(e.g. reschedule one package, or add a physical/administrative "
        f"barrier) and the HITL reviewer signs off below."
    )

    return {
        "executive_summary": executive_summary,
        "precedent_context": precedent_context,
        "recommended_action": recommended_action,
    }


def generate_safety_brief(wp: WorkPackageState) -> SafetyBrief:
    context = _grounding_context(wp)

    llm_result = _call_llm(context)
    if llm_result is not None:
        return SafetyBrief(**llm_result, source="llm")

    fallback = _deterministic_fallback(context)
    return SafetyBrief(**fallback, source="deterministic-fallback")


def reasoning_node(state: dict) -> dict:
    """
    LangGraph node wrapper. Runs after deconfliction, before the HITL
    gate. Only synthesizes a brief for packages that were actually
    flagged -- clean packages pass through untouched.
    """
    packages = state["work_packages"]
    for wp in packages:
        if wp.conflicts:
            wp.safety_brief = generate_safety_brief(wp)
    return {"work_packages": packages}
