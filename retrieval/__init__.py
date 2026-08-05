"""
Grounding Retrieval Harness -- RAG skills-building project.

Applies semantic search + citation grounding to the Watchstander regulatory
corpus (NAVSEA 8010 Manual, OSHA CFR excerpts, case_data). Built to close
specific platform gaps (RAG mechanics, vector DBs, AWS SageMaker, Databricks)
surfaced by an actual job posting -- see PASSDOWN.md for the full context.

This package is deliberately separate from `agent_core/` -- it is not wired
into the live deconfliction graph and does not inherit agent_core's
zero-network edge-resilience constraint. See ARCHITECTURE.md ADR-003 for why,
and what would need to be revisited before that could change.

Not to be confused with `agent_core/retrieval.py`, an unrelated pure-Python
TF-IDF case-lookup module that already exists elsewhere in this repo, for a
different purpose (ranking OSHA/DOL case precedents for the live safety
agent's reasoning step). This package does not use, wrap, or modify that
module.

See MIGRATION.md for the phased build plan and ARCHITECTURE.md for the
current state of the system and why it's shaped this way.
"""
