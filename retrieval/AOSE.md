# AOSE — Grounding Retrieval Harness

Adversarial-review discipline for `retrieval/`, applied at every phase
boundary. See the repo-root [AOSE.md](../AOSE.md) for the full methodology
write-up; this file is the record of real rounds run against this
sub-project specifically, not a re-explanation of the practice.

## The loop

```
BUILD → TRY TO BREAK IT → ASSUME USER ERROR / CLEVER MISUSE / MALICIOUS USE →
ASSUME COMPONENT FAILURE → ASSUME ENVIRONMENT CHANGES →
GET INDEPENDENT CRITIQUE → FIX HIGHEST-RISK PROBLEMS →
ADD REGRESSION TESTS → REPEAT
```

## Rounds

**Round 1 (2026-08-04, Phase 0 boundary).** Phase 0 has no real logic yet
(every function/method body is a documented `NotImplementedError`), so this
round focused on the things that *can* still be wrong at a skeleton stage:
packaging, naming collisions, and whether the "imports cleanly" DoD claim
actually holds outside the one shell session that built it.

- **Verified, not assumed, that the `packages.find` fix works.** Root
  MIGRATION.md Phase 6 documents `eval/` passing locally while CI stayed red
  because local runs used `python -m pytest` (cwd on `sys.path`) and CI
  doesn't. Re-ran `pip install -e ".[dev]"` fresh and invoked the bare
  `pytest` console script directly (not `python -m pytest`) — 78/78 passed,
  no regressions to the existing suite. Also imported every `retrieval.*`
  submodule from an unrelated working directory (`/tmp`) to confirm the
  editable install, not an accidental cwd-on-path effect, is what makes it
  resolve.
- **Checked the naming collision flagged in ARCHITECTURE.md §3 for real, not
  just in prose.** Grepped the
  whole repo for any existing bare `import retrieval` that could now
  silently resolve to the wrong module. Found none — every existing
  reference to the old TF-IDF module already uses the fully-qualified
  `agent_core.retrieval`. Also confirmed at runtime that `import retrieval`
  and `import agent_core.retrieval` resolve to two distinct files with no
  interference. Residual risk: a *future* contributor inside `agent_core`
  writing a bare `import retrieval` intending the local module would get
  the new top-level package instead — assessed as low-severity because it
  fails loud (`AttributeError` on the first call, since the two modules'
  APIs don't overlap), not silently. Logged as accepted risk, not fixed —
  renaming either module is out of scope for Phase 0 and the passdown
  already settled the directory name.
- **Found and fixed a real (if minor) inconsistency:** `Retriever.__init__`
  took an untyped `vector_store=None` parameter while every other file in
  this project (and the wider codebase's style) type-hints constructor
  params. Fixed to `vector_store: VectorStore | None = None`. Re-ran the
  affected tests after the fix to confirm nothing broke.
- **Tried the "inexperienced/expert user" angles the loop calls for** against
  a skeleton with no real logic: constructing every dataclass with its
  documented fields (passes), calling every stubbed function/method with
  valid-looking arguments (raises the documented `NotImplementedError`, not
  some other, less legible error). No fail-open or silently-wrong-answer
  cases exist yet, because nothing yet returns an answer — that's the actual
  point of leaving Phase 0 as stubs rather than fake-plausible logic.
- **Component/environment failure angles:** not yet applicable — Phase 0 has
  no network calls, no file I/O, no external services. Revisit at the Phase
  1 boundary, where all three become real (corpus files, an embedding
  model, a Chroma store).

**Outcome:** one real fix (retriever.py type hint), one accepted risk
(future bare-`import retrieval` inside `agent_core` — low severity, fails
loud), one verified-not-assumed claim (packages.find fix genuinely holds
under a fresh install + CI-equivalent invocation). No regression tests added
this round beyond what Phase 0 already required, since nothing found was a
behavioral bug — Phase 1 is where behavior (and therefore behavioral
regression tests) starts existing.

**Independent re-verification (2026-08-08, Phase 0 boundary, before starting
Phase 1).** PASSDOWN.md's "Next up" line still read as if the Phase 0 AOSE
round hadn't happened yet, even though Round 1 above is dated four days
earlier — a doc-freshness gap, not a code gap, but per this project's own
rule ("verifying a fix by re-running it the same way you always have isn't
verification, it's repetition" — root AOSE.md), Round 1's three testable
claims were re-run independently rather than taken on faith from the prior
entry:

- Re-ran the exact CI-equivalent check from a genuinely fresh virtualenv
  (`python -m venv`, `pip install -e .`, bare `pytest` console script, not
  `python -m pytest`): 78/78 passed. Matches Round 1's result exactly, no
  drift.
- Re-grepped the whole repo for any bare `import retrieval` and re-confirmed
  at runtime, from a fresh venv, that `retrieval` and `agent_core.retrieval`
  resolve to two distinct files (`retrieval/__init__.py` vs.
  `agent_core/retrieval.py`). Still none found; still distinct.
- Confirmed `Retriever.__init__`'s `vector_store` parameter still carries
  the `VectorStore | None` type hint from Round 1's fix — not reverted by
  any commit since.

No new findings. Phase 0 is genuinely closed, not just documented as closed.
Fixed the actual bug this check surfaced: PASSDOWN.md's stale "Next up" line
(see that file's latest entry) — it described the AOSE round as a future
step rather than a past one.

**Round 2 (2026-08-08, Phase 1 boundary).** Phase 1 has real logic and real
failure modes for the first time — this round covers what the Phase 0 note
above flagged as revisit-later territory: empty corpus, a chunk losing its
provenance, and CI silently exercising a different dependency set than
local runs.

- **Found and fixed a real citation-accuracy bug via the integration test
  itself, not a separate adversarial pass.** `chunker.chunk_text()`'s first
  cut at section-tagging only looked at a chunk's own text for a header —
  a continuation chunk (falls after the header sentence, same section, no
  header text of its own) silently got `section: None`. Caught by
  `test_retrieval_integration.py`'s real-Chapter-4 query: right chunk
  retrieved, wrong (missing) citation. This is exactly the "component
  failure" angle the loop calls for, just surfaced by a correctness test
  rather than a deliberately adversarial one — fixed by carrying the last
  seen section number forward across chunks (ARCHITECTURE.md ADR-006),
  with a dedicated regression test
  (`test_chunk_text_carries_section_forward_into_continuation_chunks`) so
  this can't silently regress.
- **Assumed environment change, checked it, found it real.** This
  sandbox's network allowlist blocks Hugging Face model downloads (403,
  same failure class as the NAVSEA PDF fetch earlier this session) — the
  real `sentence-transformers` model path cannot be exercised here at all.
  Rather than skip testing embedder.py, verified its *own* logic (batching,
  normalization, caching) against an injected fake model with the same
  `.encode()` interface real models expose — see
  `test_retrieval_embedder.py`. The real model path is unverified inside
  this environment specifically; flagged below as still open, not silently
  assumed to work.
- **Verified CI would actually pass, not just local `pytest -v`.**
  `pyproject.toml` gained a `retrieval` optional-dependency group this
  phase; before pushing, installed into a genuinely fresh venv with only
  `.[dev]` (mirroring the *old* CI config) and confirmed 13 tests failed on
  `ModuleNotFoundError: chromadb` — reproducing, not assuming, the exact gap
  root AOSE.md already documents once for `eval/`. Fixed
  `.github/workflows/tests.yml` to install `.[dev,retrieval]`, then
  re-verified clean: 101/101 under a fresh venv + bare `pytest`.
- **Malicious/clever-misuse angle:** `VectorStore.upsert()` with
  mismatched `chunks`/`embeddings` lengths now raises `ValueError` instead
  of silently zipping to the shorter list and dropping data — covered by
  `test_upsert_mismatched_lengths_raises`. `Retriever.retrieve()` on a
  blank/whitespace-only query returns `[]` without calling the embedder at
  all, rather than embedding empty text and returning a plausible-looking
  but meaningless top-k — covered by
  `test_retriever_retrieve_on_blank_query_returns_empty_list_without_embedding`.
- **Component failure angle:** `VectorStore.query()` against an empty
  collection returns `[]` rather than erroring or returning garbage —
  Chroma raises on `n_results` greater than the collection's count, which
  the fix clamps to `min(top_k, collection.count())` before querying.
  Covered by `test_query_on_empty_store_returns_empty_list`.

**Outcome:** two real fixes with regression tests (section carry-forward,
CI install gap), three defensive behaviors added and tested proactively
(mismatched-length upsert, blank-query short-circuit, empty-collection
query) rather than waiting for them to fail in the wild first. One item
moved to "still open" below rather than closed, because it genuinely isn't
verified yet.

## Accepted, not open

- Bare `import retrieval` inside `agent_core` resolving to the wrong package
  if ever written — see Round 1. Revisit only if it actually happens; not
  worth a rename or an import-linter rule for a risk that fails loud on
  first use.
- `chunker.py`'s overlap is opportunistic, not guaranteed at every chunk
  boundary (a single-sentence chunk has nothing earlier of its own to back
  into) — see ARCHITECTURE.md §5. No text is ever lost; this is a "some
  chunk boundaries don't get the double-coverage overlap exists for"
  limitation, not a correctness bug, and fixing it properly needs a real
  design pass (letting overlap reach into a *previous* chunk), not a quick
  patch under this round.

## Where the discipline is still open

- **The real `sentence-transformers` model path has not been run
  end-to-end inside this environment** — this sandbox's network allowlist
  blocks the Hugging Face download `all-MiniLM-L6-v2` needs on first use.
  `embedder.py`'s own logic is tested against an injected fake model (see
  Round 2 above), and `retrieval/ingest.py` is believed correct by code
  review, but "the real model actually downloads and produces sane
  embeddings that retrieve the right chunks for genuinely novel queries" is
  unverified until someone runs `python -m retrieval.ingest` for real, on a
  machine with live network access. Next real round should close this
  specifically, not just re-confirm the fake-model tests still pass.
- OSHA CFR 1915 excerpts are still not sourced (see PASSDOWN.md Session 5,
  ARCHITECTURE.md §5) — not an AOSE finding, just a scope gap worth
  tracking here too since Phase 2's eval set will want a corpus that
  actually includes it.
