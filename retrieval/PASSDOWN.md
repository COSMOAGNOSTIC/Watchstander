# PASSDOWN — Grounding Retrieval Harness

Session-by-session log, newest entry on top. Answers "what's done, what's
next, what was decided but not built" so this can be picked back up cold.

---

## Session 8 — 2026-08-08 — Phase 2 build: hybrid retrieval, DoD met

**Status:** Phase 2 complete. Definition of Done ("hybrid retrieval
measurably beats vector-only on the eval set") met and verified by the
eval harness, not eyeballed: 82% vs. 73% top-1 accuracy. 127/127 tests
passing (106 → 127: +21 across `test_retrieval_bm25.py`,
`test_retrieval_compression.py`, `test_retrieval_eval_harness.py`, and
new hybrid-mode cases added to `test_retrieval_retriever.py`/
`test_retrieval_vector_store.py`).

**What happened:** Built all three Phase 2 pieces additively on top of
Phase 1's `Retriever` — passing no `bm25_index` still reproduces Phase 1
exactly, same tests, same assertions, still green:

- `bm25_index.py` — `BM25Index`, pure-Python `rank_bm25` (`BM25Okapi`)
  wrapper, built via `BM25Index.from_vector_store()` from a new
  `VectorStore.get_all()` method (Chroma stays the one place chunk data
  lives; BM25's index is a derived snapshot, not a second copy).
- `compression.py` — `compress()`, sentence-level term-overlap
  extraction (not LLM summarization — edge-first per ADR-003), reuses
  `chunker.split_sentences()` (renamed from private `_split_sentences`
  for this reuse).
- `retriever.py`'s hybrid path — vector + BM25 candidate pools fused
  via reciprocal rank fusion (RRF, `k=60`), each surviving result
  compressed before being returned.
- `retrieval/eval/` — new eval harness (`scenarios.py`: 11 hand-verified
  query -> expected-chunk pairs across all three corpus sources;
  `run_eval.py`: real ingestion + deterministic hashed-BOW embedder,
  no live network; checked-in `baseline.json`).

Two real bugs found via testing, both fixed the same session (full
writeup in `ARCHITECTURE.md` ADR-008, `AOSE.md`):

1. BM25's IDF degeneracy on tiny test fixtures (a term in 1 of 2 docs
   scores `idf = log(1) = 0` exactly) — not a bug in the code, a real
   property of the classic Okapi BM25 formula that only showed up
   because unit-test fixtures were smaller than any real corpus. Fixed
   by flooring every affected fixture at 3+ documents.
2. The RRF candidate pool pulled from each ranker before fusion was
   too narrow at small `top_k` (`pool_size = max(top_k*3, top_k)` → 3
   at `top_k=1`), causing a genuine BM25 top-pick that vector search
   didn't surface at all to lose a phantom RRF tie to a vector-only
   result — the tie-break silently always favored vector results due
   to dict/sort insertion order. Caught because the eval harness's
   first real run showed hybrid tying vector-only (73%/73%) instead of
   beating it, not because the bug looked wrong on inspection. Root-
   caused with a direct raw-score debugging script isolating the exact
   failing scenario (`case-firstmarine-explosion`), then fixed by
   flooring `pool_size` at 20. Re-ran the eval after the fix: 82% vs.
   73% — genuinely ahead.

**Not done, deliberately:** Two of the 11 eval scenarios
(`navsea-4.3.6-ammunition`, `navsea-11.2.2-smoke-boundary`) still fail
in both arms, for an unrelated, pre-existing reason: `chunker.py`
merges a short section into the same chunk as the following section,
and ADR-006's "last header wins" carry-forward tags that merged chunk
with the *later* section even when the query-relevant text is in the
*earlier* section's portion. Logged as known debt in `ARCHITECTURE.md`
§5 (not blocking this session's DoD — identical failure in both arms
means hybrid still measurably wins the comparison the DoD actually
asks for). Worth a `chunk_size` tuning pass or a smarter carry-forward
rule if it starts affecting real retrievals rather than just these two
eval scenarios.

Also added `rank_bm25` to `pyproject.toml`'s `retrieval` optional-
dependency group and re-verified the fresh-venv CI-equivalence check
(bare `pytest` after `pip install -e ".[dev,retrieval]"` into a clean
venv) — same gap ADR-006 already fixed once for `sentence-transformers`/
`chromadb`, caught proactively this time instead of after the fact.

**Next up:** Phase 2 is Watchstander's retrieval sub-project's last
currently-scoped phase (Phase 3/4/Databricks/certs items in
`MIGRATION.md` are separate, longer-horizon tracks). No immediate next
build step for `retrieval/` unless Donnie wants to revisit the two
known-debt chunking-granularity scenarios, expand corpus coverage
(other 1915 subparts `cases_v1.json` cites), or start one of the
longer-horizon Phase 3+ tracks.

---

## Session 7 — 2026-08-08 — Second corpus source: OSHA 1915 Subpart B

**Status:** Closes the "OSHA CFR 1915 excerpts" open item carried since
Session 5. 106/106 tests passing (101 → 106: +5 for OSHA ingestion,
parsing, and a real integration proof).

**What happened:** Scoped to 29 CFR 1915 Subpart B ("Confined and Enclosed
Spaces and Other Dangerous Atmospheres in Shipyard Employment," sections
1915.11–1915.16) rather than all of Part 1915 — chosen deliberately because
it fills a real gap: `agent_core/procedural_lookup.py` has zero governing-
procedure coverage for `confined_space` (NAVSEA 8010 is entirely
hot-work/fire), so this is the first corpus source in the project that
actually covers it. Logged as ADR-007 in `ARCHITECTURE.md`.

Sourced differently than the NAVSEA manual was: tried a summarizing fetch
tool against both osha.gov and eCFR first, and it produced paraphrased text
in both cases — not usable for a citation-grounded corpus, which needs the
actual regulatory language, not an AI's account of it. Switched to a live
Chrome browser session (already connected this session) and pulled each
section's raw DOM text directly from osha.gov's own per-section pages
(`osha.gov/laws-regs/regulations/standardnumber/1915/1915.11`, etc.) — full
verbatim text, GPO Source: e-CFR, public domain. Saved to
`retrieval/sources/osha_1915_subpart_b.txt` with explicit `=== SECTION
1915.NN ===` markers, since CFR section numbering doesn't fit `chunker.py`'s
existing NAVSEA-style header regex (extending that regex risked false
positives on incidental four-digit numbers elsewhere in the text — see
ADR-007 for the full reasoning). New `ingest.parse_osha_sections()` and
`ingest.ingest_osha_subpart()` handle the marker-based splitting and
section tagging; `citation_formatter.SOURCE_TITLES` gained an entry for
`osha_1915_subpart_b`. A new integration test
(`test_real_osha_1915_subpart_b_query_returns_the_correct_section_and_citation`)
proves the same Definition of Done this project already proved for NAVSEA
8010: a real query against the real ingested text returns the right
section (1915.12) and an accurate citation.

**Not done, deliberately:** Other 1915 subparts `case_data/cases_v1.json`
entries cite — D (welding/hot work), E (deck openings/edges), F, G
(rigging), H (lifting) — aren't in the corpus. Not blocking; worth
expanding if Phase 2's eval set wants broader hazard-category coverage.

**Next up:** Phase 2 — hybrid retrieval (BM25 + reranking + context
compression, small eval set). The corpus (NAVSEA 8010 Ch4/Ch11 + OSHA 1915
Subpart B + cases_v1) is now broad enough across hazard categories to make
a real eval set worth building.

---

## Session 6 — 2026-08-08 — Real model path verified on live hardware

**Status:** Phase 1's last open item closed. Everything in the "Definition
of Done" and "Not done, deliberately" sections of Session 5 below still
holds except the sandbox-network caveat, which is now resolved.

**What happened:** Ran `python -m retrieval.ingest` for real on Donnie's own
machine (normal internet access, unlike the build sandbox). `all-MiniLM-L6-v2`
downloaded from Hugging Face without issue, and the real corpus ingested
cleanly: 22 chunks from Chapter 4, 11 from Chapter 11, 7 from
`cases_v1.json` — 40 total, written to a persistent Chroma collection at
`retrieval/.chroma_store/` (gitignored, stays local, not committed).

Then, separately from ingestion, queried that live index through the real
`Retriever` with a query that appears nowhere in any test fixture — "how
many hot workers can a single fire watch supervise" — and got back the
correct chunk ("No more than four hot workers shall be attended by a single
fire watch") with the correct citation ("NAVSEA 8010 Manual
(S0570-AC-CCM-010/8010), Sec. 4.4.3"). Logged in `AOSE.md`'s new "Resolved
since Round 2" section: this is the same proof
`test_retrieval_integration.py` already established with an injected fake
embedder, now independently confirmed with the real model producing real
embeddings on real hardware — not a different result, a second, harder
confirmation of the same one.

**Next up:** Phase 2 — hybrid retrieval (BM25 + reranking + context
compression, small eval set). One real loose end left before that: OSHA CFR
1915 excerpts, the third planned Phase 1 corpus source, are still not
sourced (same PDF-extraction effort as ADR-005 describes for 8010, not yet
run against 29 CFR 1915).

---

## Session 5 — 2026-08-08 — Phase 1 build: local RAG proof

**Status:** Phase 1 complete. Definition of Done met and verified by test,
not eyeballed — see MIGRATION.md's Phase 1 section for the exact assertion.

**What happened:** Chapters 4 and 11's extracted text (sourced the same
session, via `pdfplumber` against the primary PDF Donnie uploaded directly —
see root PASSDOWN.md for that extraction's own story) landed in
`retrieval/sources/`. All five Phase 0 skeleton modules got real logic:

- `chunker.py` — sentence-boundary-respecting chunking with overlap, tags
  each chunk with the NAVSEA-style section number in force.
- `embedder.py` — wired to `sentence-transformers` (`all-MiniLM-L6-v2`),
  lazy-loaded and cached.
- `vector_store.py` — wired to Chroma, ephemeral in-memory by default,
  persistent when given a directory.
- `retriever.py` — real `retrieve()`, `embed_fn` injectable for tests.
- `citation_formatter.py` — real `format_citation()` with a `SOURCE_TITLES`
  registry.
- `ingest.py` — new module, wires the whole pipeline end-to-end for real
  corpus documents (8010 Ch4/Ch11 text + `case_data/cases_v1.json`, one
  chunk per case). Runnable by hand via `python -m retrieval.ingest`.

Two real bugs surfaced by the new tests, both fixed the same pass rather
than left open (see ARCHITECTURE.md ADR-006 for the full writeup):
section-citation not carrying forward into a chunk that continues a section
without repeating its header, and CI's install step not picking up the new
`retrieval` optional-dependency group (caught by actually installing into a
fresh venv and running bare `pytest`, not by trusting a local
`python -m pytest` pass — this repo already documents that exact gap once,
in root AOSE.md, over `eval/`; caught here before it repeated, not after).

sentence-transformers and chromadb are both real network/model dependencies
this sandbox couldn't reach Hugging Face to download a model through (403
from the proxy allowlist) — same class of block as the NAVSEA PDF fetch
earlier this session. Worked around the same way testing in this repo
always avoids live-network dependence: `embedder._load_model()` and the
real model path are never exercised by the test suite, which injects a
deterministic offline embedding function instead (a real, if crude,
hashed-bag-of-words vectorizer in `test_retrieval_integration.py` — word-
overlap-sensitive, not a no-op stub). The real model path is believed
correct by code review and by chromadb's own real (non-mocked) storage/
query logic being exercised directly, but has not been run end-to-end with
the real model inside this environment — that verification still needs to
happen on a machine with real network access (Donnie's, or CI) before it's
fully trusted, not just this session's code review.

**Not done, deliberately:** OSHA CFR 1915 excerpts — the third planned
Phase 1 corpus source — are not sourced. Same PDF-extraction effort as
ADR-005 describes for 8010 hasn't been run against 29 CFR 1915 yet. Doesn't
block Phase 1's DoD (met against the 8010 + cases_v1 corpus already
ingested) but the real corpus is smaller than originally scoped until this
lands.

**Next up:** Phase 2 — hybrid retrieval (BM25 + reranking + context
compression, small eval set). Before that, worth running
`python -m retrieval.ingest` for real on a machine with live network (to
actually download `all-MiniLM-L6-v2` and confirm the real model path works,
not just the injected-fake-embedder path the tests cover), and sourcing the
OSHA CFR 1915 excerpts to round out the Phase 1 corpus.

---

## Session 1 — 2026-08-04 — Phase 0 scaffold

**Status:** Phase 0 complete. Nothing before this session; this is the
project's first working session in Claude Code (prior session, elsewhere,
produced the placement/tooling decisions this session executed against —
see below).

**What happened:**
- Confirmed with Donnie: proceed with Phase 0 now, using the
  aose-project-scaffold methodology (already decided pre-session, per the
  passdown this session started from).
- Inspected the existing Watchstander repo before scaffolding anything: it
  already has its own root-level MIGRATION.md/ARCHITECTURE.md/PASSDOWN.md/
  AOSE.md tracking the deconfliction agent project itself (currently Phase
  6, "Lock it in", in progress) — decided to give this sub-project its own
  scoped doc set inside `retrieval/` rather than injecting new phases into
  the root docs, per the scaffold skill's own guidance to split by
  component when a doc set would otherwise balloon or conflate two
  projects.
- Found and flagged a real architectural tension while writing the decision
  log: `agent_core/retrieval.py` explicitly rejected ChromaDB +
  sentence-transformers for the live graph because Watchstander is
  documented edge-first / zero-network. This project's Phase 1 plan is
  exactly that stack. Resolved for now (ADR-003, `retrieval/ARCHITECTURE.md`)
  as: fine as long as this stays a standalone harness never imported by
  `agent_core`; must be explicitly revisited if that ever changes. Not a
  blocker for Phase 0 or Phase 1, but worth knowing before Phase 1 starts,
  not after.
- Built the five Phase 0 modules (`chunker.py`, `embedder.py`,
  `vector_store.py`, `retriever.py`, `citation_formatter.py`) — real
  dataclasses for every data model, every function/method body a
  `NotImplementedError` pointing at Phase 1.
- Added `tests/test_retrieval_*.py` (five files) — assert the data models
  are real and the boundaries exist/raise as documented. Deliberately not
  vacuous: each test either constructs a real dataclass and checks its
  fields, or asserts the documented `NotImplementedError`.
- Fixed `pyproject.toml` `packages.find` to include `retrieval*` proactively
  — the repo's own history (root MIGRATION.md Phase 6) shows exactly this
  omission happening with `eval/` and going undetected locally while CI
  stayed red. No reason to repeat that here.
- Wrote `retrieval/README.md`, `MIGRATION.md`, `ARCHITECTURE.md` (this
  file's sibling), and this file.
- Added a short pointer section to the repo-root `README.md` so the
  sub-project doesn't go undiscoverable.

**What's decided but not built:** Everything in MIGRATION.md Phase 1 onward
— corpus ingestion, real chunking, sentence-transformers embedding, Chroma
storage, real retrieval, real citation formatting, hybrid retrieval,
SageMaker exposure, Databricks exposure, certs.

**Open questions for next session:**
- NAVSEA 8010 source text: chunk from the already-structured
  `case_data/navsea_8010_psns_v2014.json`, or pull the manual's original
  text fresh? (ARCHITECTURE.md §5)
- `pyproject.toml`'s `retrieval` optional-dependency group
  (`sentence-transformers`, `chromadb`) still needs adding — deliberately
  not added this session since nothing uses them yet.

---

## Session 2 — 2026-08-04 — Phase 0 AOSE round

**Status:** Phase 0 AOSE Round 1 complete (see `AOSE.md`). Phase 0 fully
closed as of this session — this entry was never added at the time, which
left this file's "Next up" line stale (still describing the AOSE round as a
future step) even though `AOSE.md` itself was current. Backfilled 2026-08-08
alongside Session 3 below, once the staleness was caught.

**What happened:** Ran Round 1 of the adversarial-review loop against the
Phase 0 skeleton — packaging (verified the `packages.find` fix under a
fresh install + CI-equivalent bare `pytest` invocation, not just locally),
the `retrieval`/`agent_core.retrieval` naming collision (grepped for and
ruled out any existing bare `import retrieval`), and a general pass over
every stubbed function/dataclass for anything that could be wrong at a
skeleton stage. One real fix made (`Retriever.__init__` gained a type hint
on `vector_store`); one risk logged as accepted, not fixed (a *future* bare
`import retrieval` inside `agent_core` would silently resolve to the wrong
package — low severity, fails loud). Full writeup in `AOSE.md`.

**Next up:** Phase 1 — local RAG proof.

---

## Session 3 — 2026-08-08 — Independent re-verification of the Phase 0 AOSE round, doc staleness fixed

**Status:** Phase 0 confirmed still closed. No new code changes — this
session was a documentation-integrity check, not a build session.

**What happened:** Before starting Phase 1, re-ran Round 1's three testable
claims independently rather than trusting the write-up at face value (same
principle root `AOSE.md` already states: re-reading a prior finding isn't
verification, re-running it is). All three held with no drift: 78/78 tests
pass from a genuinely fresh venv + editable install + bare `pytest`
console-script invocation; no bare `import retrieval` exists anywhere in the
repo and `retrieval`/`agent_core.retrieval` still resolve to two distinct
files; `Retriever.__init__`'s type hint from Round 1's fix is still present.
Logged as its own dated entry in `AOSE.md` rather than silently folded into
Round 1.

While doing this, caught and fixed the actual bug this check surfaced: this
file's "Next up" line (previously at the end of Session 1) still described
the Phase 0 AOSE round as a future step, even though `AOSE.md` showed it
completed four days earlier. Backfilled the missing Session 2 entry above
so the record matches what actually happened, and moved "Next up" here,
where it's current.

**Next up:** Phase 1 — local RAG proof (see MIGRATION.md for scope: corpus
ingestion, real chunking, sentence-transformers embedding, Chroma storage,
real retrieval, real citation formatting). Open questions from Session 1
(NAVSEA 8010 source text choice; `retrieval` optional-dependency group)
still need a decision before or during Phase 1 — neither resolved by this
session.

---

## Session 4 — 2026-08-08 — NAVSEA 8010 source decision

**Status:** One of Session 1's two open questions resolved. The
`retrieval` optional-dependency group (`sentence-transformers`, `chromadb`)
remains open — deliberately, still not needed until Phase 1 actually starts
wiring code against them.

**What happened:** Donnie decided the NAVSEA 8010 chunking source: pull the
original manual text (Chapters 4 and 11) fresh, rather than chunk the
already-extracted `case_data/navsea_8010_psns_v2014.json` summaries. Framed
explicitly as choosing the harder path on purpose — the extraction-and-
wiring work is itself the point of this sub-project, and doing it now, on a
small corpus, while the stakes are low, beats deferring it. Logged as
ADR-005 in `ARCHITECTURE.md` §4, with the reasoning and scope (Chapters 4
and 11 specifically, not the full manual) captured there rather than just in
chat. `MIGRATION.md`'s Phase 1 checklist and `ARCHITECTURE.md` §1's corpus
description updated to match. No code written this session — Chapters 4/11
still need to actually be sourced/extracted from the PDF before Phase 1's
ingestion step can start.

**Next up:** Phase 1 — local RAG proof. Immediate next action, before any
chunking/embedding code: source and extract the actual text of NAVSEA 8010
Chapters 4 and 11 from the primary PDF (confirmed public domain, NAVSEA's
own FOIA reading room — see ADR-005 for the citation). The `retrieval`
optional-dependency group still needs adding to `pyproject.toml` once
`sentence-transformers`/`chromadb` are actually used.
