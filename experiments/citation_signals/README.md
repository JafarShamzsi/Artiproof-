# CITE-02: offline observed citation signals

Experiment only. Fictional identifiers, standard library, no application imports,
network, service or real-person records. No fraud verdict, confidence score,
blacklist or integrity ranking. Positive motifs are **not** evidence of intent or
real-world accuracy. Authorship does not establish who selected a reference.

## Internal fixture contract v1 (specified before implementation)

JSON object with exactly `version`, `window`, `authors`, `works`, `runs`,
`references`. Version is integer 1. All fields below are required; extra fields,
duplicate JSON keys, nonfinite numbers, dangling IDs and conflicting assertions
are errors. JSON numbers must be integers (decimal/exponent syntax is rejected,
including overflow such as `1e999`). Dates are bounded to 1900–2100.
IDs are opaque ASCII tokens (1–64 characters, letters/digits/_.:-).
No names. Identical repeated reference assertions are idempotent; other entity
IDs and per-work authorships must be unique.

* `window`: `start`, `end`, `as_of` strict YYYY-MM-DD. Publication-based window
  is **[start, end)**, with end <= as_of and at most 3660 days. As-of is inclusive
  at day precision, not a fabricated reference-event timestamp.
* `authors`: `id`, `status` (resolved/ambiguous/unknown), `resolution_version`
  (opaque token), `identifiers` (unique opaque tokens). A shared identifier across
  authors requires both to be ambiguous/unknown; resolved collisions are errors.
  Merge/split uncertainty must be marked ambiguous, not silently unified. This
  is a versioned assertion input, not an entity resolver or merge-history store.
* `works`: `id`, `kind` (research/review), `published` (`precision` = day/month/
  year/unknown, `value` = matching ISO date, YYYY-MM, YYYY or null), `authorships`
  (objects `author_id`, `assertion_id`, `resolution_version`). Versions must match
  the referenced author. Empty authorships mean unknown, not unauthored.
* `runs`: `id`, `provider`, `lineage`, `as_of`, `direction` (incoming/outgoing/both),
  `truncated` (boolean), `work_limit`, `reference_limit` (positive integers).
  Lineage identifies shared upstream data; mirrors are not independent votes.
  These are collection limits, **not** a claim of complete population coverage.
  This small contract defines `work_limit` as distinct endpoint works per run and
  `reference_limit` as distinct source-evidence IDs per run; contradictions reject.
* `references`: `id`, `citing`, `cited`, `run`, `source_evidence_id`, `observed_on`.
  Only explicit directed citing-work -> cited-work assertions create edges.
  Observed day <= run as_of <= analysis as_of. Self-work references and certainly
  impossible publication chronology are rejected. Coarse overlapping dates,
  unknown dates and uncertain observation/publication order abstain. The model
  assumes canonical published versions; preprint/version exceptions require a
  separately reviewed contract, not chronology guessing.

Date intervals wholly within the window are included; wholly outside excluded;
straddling boundaries abstain. For graph features both endpoint dates must permit
chronology, and both authorship lists must be nonempty and resolved. Unknown
identities/dates retain paper assertions but are excluded from author features.
Publication time is a window proxy, never claimed to be actual citation time.

Hard bounds: 1 MiB input; 64 authors, 128 works, 32 runs, 512 reference assertions,
8 authors/work, 8 identifiers/author; bounded three-author directed-cycle traversal
(at most 2 * choose(64, 3) = 83,328 oriented triples). At most 128 motifs are
emitted; further observations set `enumeration_truncated`. Each path uses a
matching of at most three author arcs to at most 512 paper pairs. No unbounded
community search or arbitrary path traversal. These are structural work bounds,
not a hard wall-clock timeout or a measured latency/memory guarantee.
The CLI reads at most the byte limit + 1, and rejects excessive nesting (>12).
No runtime/memory or database-performance claims without measurements.

## Feature semantics (proposed experiment-local, not an application API)

Each eligible unique work pair carries total mass 1, fractionally distributed
across its n*m ordered author pairs with exact rational arithmetic. Duplicate
providers never add mass. Self mass (same author) is separate from nonself mass
between authors sharing a fully dated, resolved coauthored work published by the
citing work's earliest possible date. That inventory is only observed coauthorship,
not a complete career history. Paper-level shared-author overlap counts once per
work pair and is not conflated with projected self mass.

Two-way author activity requires both ordered author edges with **distinct**
underlying work-pair witnesses. Three-author cycles require every directed edge,
with three distinct work-pair witnesses (a bounded matching, not silent all-pairs
inflation). Witnesses are ordered to match the corresponding author arcs.
The full projected masses remain descriptive, including overlapping authors;
`balanced_mass` is twice the smaller directional mass, while `two_way_mass` is
their sum. These are defined quantities, not calibrated anomaly statistics.
One consortium paper edge alone cannot establish reciprocal author activity or
a three-paper motif. Identical day dates are permitted; subday order is not inferred.
Cycles require observed work support;
they are not reciprocal paper pairs or misconduct rings. Concentration reports
outgoing fractional mass by recipient and the observed source denominator, not
a population fraction. Missing outgoing coverage cannot establish motif absence
or group closure. Temporal burst is unavailable: this contract has no actual
time-series/cohort baseline and does not substitute lifetime counts / career age.

## Run and replay

From the repository root, Python 3.12+ (no installation/dependencies required):

```text
python -B experiments/citation_signals/signals.py experiments/citation_signals/fixtures/reciprocal_authors.json
python -B -m unittest discover -s experiments/citation_signals -p test_signals.py -v
python -B experiments/citation_signals/synthetic.py --check
python -B -m tabnanny experiments/citation_signals
```

On the verified Windows host, replace `python` with
`& 'C:/Users/Axel/.local/bin/python3.12.exe'` in PowerShell.
The CLI emits JSON only on success (exit 0); invalid input emits a concise stderr
error, no stdout and exit 2. `synthetic.py` without `--check` regenerates only the
local `fixtures/` and `outputs/` directories. Do not feed it real-person records.

`outputs/` contains full deterministic results for 14 accepted fixtures and
expected error records for 2 rejected fixtures. All use explicit as-of
2024-02-01, fixture version 1 and algorithm version `citation-signals/1`.
`input_sha256` hashes compact sorted-key JSON after sorting contract assertion
sets and deduplicating identical reference IDs. It changes when provenance changes.
`features_sha256` hashes the deterministic feature object **preserving ordered
directional paths**; mirrors do not change it. It does not hash input metadata or
prove scientific validity, approval, code integrity or authenticity. Bind replay
to the reviewed Git head as well as both digests/version/window.

Excerpt of actual `outputs/reciprocal_authors.json` (full output includes evidence):

```json
{
  "counts": {
    "abstained_work_pairs": 0,
    "eligible_work_pairs": 2,
    "observed_work_pairs": 2,
    "outside_window_work_pairs": 0,
    "reference_assertions": 2
  },
  "fraud_verdict": "not_assessed",
  "temporal_burst": {
    "reason": "no_time_series_or_cohort_baseline",
    "status": "unavailable"
  }
}
```

Engineer explanation: A's later work cites B's earlier work; B's different later
work cites A's earlier work. This yields observed A->B and B->A author mass of 1
each, supported by two different paper pairs. **Neither paper pair is reversed.**
Trace each feature's work pairs through `paper_evidence.assertions` to source IDs
and runs, and through `work_assertions` to versioned authorship assertions. Mirrored
assertions are preserved with shared lineage; no assertion tally is a confidence
score. `projection_supporting_assertion_ids` identifies only the assertions whose
observation dates actually support the eligible projection; ambiguous earlier
observations remain in the ledger, not in that supporting set.
Concentration shares and self shares describe eligible observed mass only,
not unobserved, abstained or outside-window evidence. `counts` exposes those
exclusions; `population_denominator` and all absence claims remain null.

## Controls and limits demonstrated

| Fixture | Observable result, not a diagnosis |
| --- | --- |
| legitimate_high_self_citation | 3 eligible pairs; self mass 3, share 1; no misconduct assessment |
| legitimate_coauthor_team | 1 paper pair; self mass 1/2, separate nonself coauthor mass 1/2; no reciprocity |
| legitimate_small_field / artificial_directed_cycle | Identical 3-edge directed author cycle and identical outputs despite different scenario descriptions |
| reciprocal_authors | 2 pairs; two-way mass 2, balanced mass 2, no reciprocal paper pair |
| asymmetric_donor_recipient | 1 observed A->B mass, no two-way witness; absence not established |
| incomplete_incoming_only | Truncated incoming sample; population denominator, motif absence and group closure unavailable |
| duplicate_provider_mirror | 3 assertions, 2 work pairs, same features digest as unmirrored fixture |
| identity_collision_ambiguity / identity_split_ambiguity | Both paper pairs retained; both author projections abstain |
| legitimate_review_high_degree | 8 references; 8 equal 1/8 recipient shares, no burst assessment |
| missing_dates | 2 observed pairs; 1 eligible, 1 date abstention |
| window_boundaries | Start included, end excluded: 1 eligible pair, 1 outside |
| ambiguous_year_boundary | 1 year-precision boundary abstention, 1 outside; no guessed inclusion |
| invalid_future_observation / invalid_resolved_collision | Reject input with exit 2; no invented evidence |

Additional unit controls cover one-edge consortium false motifs, fractional mass
conservation, future coauthorship, coarse observation/chronology ambiguity, dangling
IDs, version conflicts, source reuse, impossible dates, empty evidence, strict
JSON, bounds, deterministic seeded permutations and input-change sensitivity.
No hypothesis test, field/cohort null model, career normalization, empirical
false-positive estimate, real-provider study or CIDRE implementation is provided.
The eight-reference review control is high-degree **relative to this tiny fixture**,
not a real-world large-degree benchmark. Motifs may still be ordinary small-field
or team behavior even when supported by multiple papers. No completeness claim
is inferred from a run reporting `truncated=false`.

## Why current application inputs are insufficient (read-only source audit)

Exact source baseline: `47fb9d79f3e5cbdf9062579f1d65b2e253f2486a`.
The acknowledged later main change is README-only; no app adapter is implemented.
These local-code primary sources were read, not imported/executed:

* [Graph builder, lines 51–89 and 135–161](../../backend/app/services/academic_integrity/citation_graph_builder.py):
  selects leading publications, samples incoming references, retains paper IDs
  and citing author IDs, and reports limits. Relationships lack full citing/cited
  dated authorship assertions and per-reference source/run/lineage/as-of evidence.
* [Pattern detector, lines 1–5, 91–127 and 163](../../backend/app/services/academic_integrity/ring_detector.py):
  explicitly cannot establish reciprocity/cycles/manipulation from incoming samples.
  Its lines 129–144 lifetime-count/age heuristic is **not** a temporal burst baseline;
  this experiment does not reuse it. That outside-scope limitation is reported,
  not fixed or relabeled as scientifically validated.
* [Models, lines 104–158](../../backend/app/models/researcher.py):
  scraped publication/citation/coauthor rows do not supply this experiment's
  versioned identity, precision, independent assertion lineage and coverage contract.
* [Orchestrator, lines 237–275 and 427–439](../../backend/app/services/academic_integrity/orchestrator.py):
  current analysis uses that incoming sample and persists truncated summary graph
  data, not a replayable complete directed evidence inventory.
* [Evidence regressions, lines 42–90](../../backend/tests/test_researcher_evidence.py):
  source-level tests explicitly preserve incoming concentration without ring penalties.

These are code-local observations, not claims of defects established against live
records. Provider totals alone cannot enter this contract as edges; unsupported
aggregate fields reject. A separately authorized collector/adapter would need
raw directed references, all endpoint authorship/date assertions, identity
resolution versions and explicit provider/run/coverage provenance first. Sibling
lane proposals are not an accepted shared API. No storage choice or database
query-performance claim is made here; in-memory fixture behavior says nothing
about PostgreSQL or graph-database performance.

## Human review and correction (required future integration, not implemented UI)

Signals describe observations only. Analyst disposition, evidence confidence and
adjudicated misconduct must remain separate records; none is generated here.
Any future case must include counterevidence (field conventions, review articles,
team/consortium overlap, career effects, collection gaps and identity disputes),
human review and an opportunity to correct identity/reference assertions and
appeal conclusions. Preserve prior input/evidence digests, identity versions,
reviewed code head and analyst actions in an audit trail; corrected evidence
requires a new replay and invalidates stale cases. This CLI only supplies local
replay artifacts, not an analyst workflow, append-only audit system or permission
to create public person rankings or autonomous blacklists.

## Verification evidence and handoff

Agent-Tag: CITE-02. Device-Tag: axel-windows. Refs issue #58 and manager claim
comment6720147055. Only `experiments/citation_signals/` is writable in this lane.

Actual local checks, 2026-11-08, Python 3.12.15:

* Full affected standalone `unittest` command above: **50 tests passed, no skips**.
  Includes CLI subprocess checks against all 16 published cases.
* Deterministic replay `synthetic.py --check`: **32 artifacts verified**.
* `tabnanny`: exit 0. All three Python sources compiled in memory: exit 0.
* Ruff unavailable (`No module named ruff`); no dependency installation attempted.
  No static type checker run. Tabnanny/syntax checks are not substitutes for Ruff.
* Initial RED: 9 tests, **6 assertion failures + 2 missing-output errors**;
  principal directed-paper assertion was `0 != 2` against the initial stub.
  Then all 9 passed. Additional RED: single-team/consortium controls produced
  **2 assertion failures**, corrected by distinct work-pair matching. Further RED:
  directional digest plus exponent-overflow controls produced **3 assertion
  failures**. A later assertion-level supporting-provenance guard produced
  **1 assertion failure** (`None != ['later']`), corrected before final GREEN.
  Final test suite has no failures.
* The generic `python` launcher became unavailable after initial RED (initially
  reported 3.14.9); all final checks use the explicit Python 3.12.15 path above.

No runtime/memory benchmark was performed. Test-run elapsed time is not an
algorithm or database benchmark. No application/backend/frontend/provider/browser/
database tests or builds were run; this task expressly excludes app execution and
infrastructure. Remote checks and independent exact-head review remain separate,
unverified acceptance gates. These synthetic checks establish implementation
behavior only, not scientific validity or production readiness.

Rollback is removal of this isolated experiment; no application/schema/data changes
exist to roll back. Freeze on draft publication and await independent exact-head
review; manager reconciles future contracts/integration and current CI. No merge,
self-approval, issue closure or deployment is authorized by this evidence.
