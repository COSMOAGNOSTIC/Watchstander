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

## Resolved since Round 2

- **The real `sentence-transformers` model path — closed 2026-08-08, same
  day as Round 2, on Donnie's own machine (live network, not this
  sandbox).** `python -m retrieval.ingest` ran for real: downloaded
  `all-MiniLM-L6-v2` from Hugging Face, chunked and embedded the real
  corpus (22 + 11 + 7 = 40 chunks), wrote a persistent Chroma collection to
  `retrieval/.chroma_store/`. Then, separately, queried that live index
  with a genuinely novel query never used in any test fixture — "how many
  hot workers can a single fire watch supervise" — through the real
  `Retriever` against the real persisted store. Returned the correct chunk
  (containing "No more than four hot workers shall be attended by a single
  fire watch") with the correct citation ("NAVSEA 8010 Manual
  (S0570-AC-CCM-010/8010), Sec. 4.4.3"). This is the same proof
  `test_retrieval_integration.py` already established with a fake
  embedder, now independently confirmed with the real model producing real
  embeddings — the fake-embedder tests were verifying the pipeline's
  wiring correctly; they weren't standing in for something that turned out
  to behave differently for real.

**Round 3 (2026-08-08, adding OSHA 1915 Subpart B, ADR-007).** One real
methodology catch during sourcing, one real test-design trap caught before
it shipped:

- **Assumed a fetch tool's output was verbatim; checked, found it wasn't.**
  A summarizing fetch tool was tried first against both osha.gov and eCFR
  pages. It returned confident-looking, well-formatted regulatory
  language — but comparing it against the actual page content (via a live
  browser session's raw-DOM text extraction, not a summarizing tool)
  showed it had paraphrased and condensed multiple subsections ("Additional
  definitions cover Marine Chemist, IDLH, oxygen-deficient/enriched
  atmospheres..." rather than the actual definitions). For a citation-
  grounded corpus this is exactly the failure mode that matters: text that
  reads as authoritative but isn't the primary source verbatim. Caught
  before any of it entered the corpus, not after — switched sourcing
  method entirely rather than lightly editing the summarized output.
- **Test-design trap, same shape as an earlier one this project already
  documents (root AOSE.md's fire-watch capacity test, and this file's own
  history):** the first draft of the OSHA integration test used a
  semantically-natural query ("what oxygen percentage is required before
  entering a confined space"). Against the real hashed-bag-of-words fake
  embedder, that query retrieved a *different* chunk within the correct
  section (1915.12) than the one the assertion expected — not a bug in
  `ingest_osha_subpart` or `chunker.py`, just a query that didn't share
  enough vocabulary with the target chunk for a crude word-overlap
  embedder to prefer it over a neighboring chunk in the same section.
  Caught by actually running the test rather than assuming a plausible-
  sounding query would work, then fixed by using a query built from the
  target chunk's own vocabulary (same technique the NAVSEA integration
  tests already use).

**Outcome:** no code defects found this round — `ingest_osha_subpart()`,
`parse_osha_sections()`, and the `SOURCE_TITLES` addition were correct on
first real-corpus test. Both catches were sourcing/test-design discipline,
not implementation bugs, which is itself a difference worth naming: not
every AOSE round finds a bug, and that's fine as long as the round was
real (comparing against actual page content, actually running the test)
rather than skipped because "this part is simple."

**Round 4 (2026-08-08, Phase 2 hybrid retrieval, ADR-008).** Two real
findings, both caught by actually running things rather than trusting
code review — the eval harness itself is what this round's own
mechanism relied on, which is worth naming as a methodology point: the
harness wasn't just Phase 2's deliverable, it was also the thing that
caught Phase 2's own bug.

- **Assumed BM25 test fixtures needed the same rigor as any other
  fixture; found a real mathematical property that broke naive small
  fixtures.** `test_retrieval_bm25.py`'s first draft used 2-document
  toy corpora, matching the existing style of other small unit-test
  fixtures in this repo. Four tests failed with 0 or negative scores.
  Diagnosed directly (not guessed) with a Python one-liner comparing a
  2-doc vs. 3-doc `BM25Okapi` corpus on the identical query — the 2-doc
  case returned `[0., 0.]`, the 3-doc case returned real differentiating
  scores. Root cause: Okapi BM25's IDF term is `log((N-df+0.5)/(df+0.5))`;
  for a term in exactly 1 of 2 documents that's `log(1) = 0` exactly,
  and negative at N=1. Not a `bm25_index.py` bug — a real, well-known
  property of the formula that this repo's existing small-fixture
  convention happened to walk straight into. Fixed by flooring every
  affected fixture (`test_retrieval_bm25.py`, `test_retrieval_retriever.py`'s
  hybrid-mode tests) at 3+ documents via a shared `_FILLER_DOCS`/
  `_filler_chunks()` helper, with the reasoning documented inline so a
  future small-fixture addition doesn't walk into the same trap blind.
- **Assumed the eval harness's first real run would just confirm the
  design; it caught a genuine bug instead.** `python -m retrieval.eval.run_eval`
  against the real 11-scenario set returned hybrid tying vector-only
  (73%/73%, 8/11 each) — failing Phase 2's literal Definition of Done
  ("hybrid retrieval *measurably beats* vector-only"), not a subtle
  near-miss. Root-caused with a targeted debugging script isolating the
  one flipped scenario (`case-firstmarine-explosion`): BM25's raw
  ranking put the correct chunk (`cases_v1/HW-FIRSTMARINE`) clearly
  first (score 17.189, next-best 9.483), but at the eval harness's real
  `top_k=1` call, `retriever.py`'s candidate pool per ranker
  (`pool_size = max(top_k*3, top_k)`) was only 3 — narrow enough that
  the correct chunk, which vector search didn't surface at all within
  that narrow pool, and a vector-only chunk that also didn't appear in
  BM25's pool, computed *identical* RRF scores (`1/(60+0+1)` each,
  since both were rank-0 in exactly one ranking). The tie was then
  broken silently by dict/sort insertion order — `vector_results` is
  fused before `bm25_results` in the function call, so ties always
  favored vector regardless of which candidate was actually more
  relevant. Fixed by flooring `pool_size` at 20 regardless of `top_k`.
  Re-ran the eval after the fix: 82%/73%, genuinely ahead, confirmed by
  the harness itself rather than assumed from the code change alone.

**Outcome:** two real findings, both fixed same-session, both caught
by executing (a debugging script against real `BM25Okapi` output, the
eval harness's own real run) rather than by inspection. `compression.py`
and `VectorStore.get_all()` had no defects found this round — their
test suites (5 and 2 new tests respectively) passed clean on first real
run.

## Where the discipline is still open

- Other 1915 subparts `case_data/cases_v1.json` cites (D, E, F, G, H) are
  not in the corpus — Subpart B was scoped in deliberately for the
  confined_space coverage gap it closes (ADR-007), not because the rest
  isn't relevant. Worth revisiting once Phase 2's eval set defines what
  hazard-category coverage it actually needs.
- Two eval scenarios (`navsea-4.3.6-ammunition`, `navsea-11.2.2-smoke-
  boundary`) fail identically under both vector-only and hybrid
  retrieval, due to a `chunker.py`/ADR-006 chunking-granularity
  limitation unrelated to Phase 2 (a short section's content lands in a
  chunk tagged with the *following* section's header). Doesn't block
  Phase 2's DoD (both arms fail identically, so the comparison the DoD
  asks for still holds), but is a real limitation worth a future round
  if it starts affecting real retrievals rather than just these two
  scenarios — see ARCHITECTURE.md §5.
