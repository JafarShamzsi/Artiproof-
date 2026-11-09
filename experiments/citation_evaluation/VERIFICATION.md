# CITE-03 verification evidence

2026-11-08 · Agent-Tag `CITE-03` · Device-Tag `axel-windows` · issue #58.
Assigned source base/parent `47fb9d79f3e5cbdf9062579f1d65b2e253f2486a`;
manager acknowledged README-only main advance to
`58ddbd0c9f2a60a06b2f28622b4f84620dc61ab0`. No rebase or main merge.
Exact final head and publication-time base are recorded in the draft PR, avoiding
a self-referential commit hash in this committed file.

## Environment and commands actually executed

Existing CPython **3.14.9**, Windows. No installation or infrastructure startup.
All tests are stdlib synthetic unit/CLI fixture tests, not live/provider/browser
or application integration. In commands below `$py` denotes the existing binary:

```powershell
$py = 'C:/Users/Axel/AppData/Local/hermes/tools/python-3.14.9+20261021-win32-x64/python.exe'
& $py -B -m unittest discover -s experiments/citation_evaluation -v
& $py -B experiments/citation_evaluation/verify_math.py
Get-Content experiments/citation_evaluation/fixtures/complete.json -Raw | & $py -B experiments/citation_evaluation/evaluate.py --require-metric precision_at_budget
Get-Content experiments/citation_evaluation/fixtures/incomplete.json -Raw | & $py -B experiments/citation_evaluation/evaluate.py
```

- Full final unit/CLI run before this evidence file: **24 tests passed** in
  **2.787 seconds** (unittest's observed suite duration, not a performance benchmark).
  Includes 216 exhaustive label/decision combinations inside one property-style
  test, 5000-row bound, repeated fixture replay and actual child-process CLI tests.
  No skips. A final rerun and staged checks are reported with the PR head.
- Both fixture CLI commands exited 0 with bounded JSON. Complete fixture:
  TP=2, FP=1, TN=1, FN=1; P@3=2/3; recall=1/2; conditional accuracy=3/5;
  decision coverage=5/6; one positive abstention. Incomplete fixture emits `null`
  for every metric; selected unknown stays unknown. Child-process test proves
  `--require-metric recall` on incomplete data exits 2 with no stdout report.
- Math command exited 0: `Fraction` references P@3=2/3, recall=1/2,
  conditional accuracy=3/5, coverage=5/6; hypothetical PPV=10/121 and expected
  true/false alerts 90/999 on a hypothetical 100,000 cases. Independent 40-digit
  Decimal Wilson(2,3) agrees with evaluator floats within test tolerance.
- Syntax/import-scope/JSON/source consistency check actually passed: all **3**
  Python files compile from source without pycache; AST imports restricted to
  `sys.stdlib_module_names` plus the two local experiment modules; **3** JSON files
  parse; **13** source IDs are unique and equal protocol definitions, each ledger
  URL appears in the protocol. This is a bounded static check, not a type checker.
- `ruff` was not available through installed command discovery. No lint/type
  package was installed. Python compilation and import-scope assertions are the
  static evidence; full Ruff/mypy/other type-checker execution is **unverified**.
- `git diff --check` passed on tracked content during work; final **staged**
  whitespace/path check is required because new files were initially untracked.

## Observed TDD RED → GREEN (not reconstructed passing claims)

1. Wrote 17 tests with a stub `evaluate()` returning `{}`. Ran
   `python -B -m unittest discover -s experiments/citation_evaluation -v`:
   **exit 1**, 17 tests, **27 failures / 15 errors** including subtests. Assertions
   included `ValueError not raised` and invalid CLI input incorrectly exiting 0.
2. Implemented validation/counting/CLI; pinned executable full run:
   **17 passed**, 1.020 seconds.
3. Added exhaustive conservation/interval and fixture controls. Full run:
   **exit 1**, 20 tests, **1 assertion failure / 1 missing-fixture error**.
   Investigation showed Wilson(0,3)'s computed lower endpoint was
   `5.551115123125783e-17`, incorrectly excluding the point estimate zero.
   Fixed exact 0/all-success boundaries and added the fixed fictional fixture:
   **20 passed**, 0.879 seconds. No test expectation was loosened.
4. Added math-reference and abstained-label count tests against missing outputs:
   first two key errors; clarified assertions with `.get()` then reran focused
   tests and observed **2 assertion failures** (`None != '2/3'`, `None != 1`).
   Implemented separate rational/Decimal reference and abstention label counts:
   **22 passed**, 0.970 seconds; actual math output inspected.
5. Added invalid-UTF8 and fixed-fixture replay checks; full suite:
   **24 passed**, 2.787 seconds.

The initial post-implementation `python` PATH alias failed with “Python was not
found”; rerun used the absolute existing executable. `pdftotext` PATH discovery
also varied; the full PDF extraction used the existing explicit binary. PowerShell
`Get-FileHash` discovery failed; stdlib `hashlib` successfully verified the three
downloaded primary PDFs instead. These tooling failures are not passing checks.

## Literature evidence and limits

13 primary works/first-party documentation entries with source anchors and
claim exclusions in `sources.json`; CIDRE and its linked 2022 correction both read.
The BH PDF is a scanned paper: text extraction returned no text; all 13 pages
were rendered/read, including definition on p.291 and theorem on p.293. PU and
binomial-interval PDFs were extracted/read. SHA-256s of the downloaded PDFs are
recorded in the ledger; they identify retrieved bytes, not correctness or approval.
Other entries identify inspected full HTML and pinned paper/page versions; HTML
bytes were not all archived/hash-pinned. Candidate search/URL failures or unrelated
results were discarded, never used as evidence. Only the ledger's inspected
sources support published claims. This is not an exhaustive systematic review or
an exhaustive correction search; CIDRE's original page explicitly links its
correction. No grounded-citations tool was available through discovery.

Source files were inspected at the assigned base and current main README read.
Application tests, manifests and CI were read only. No backend unit suite,
PostgreSQL integration, frontend lint/types/build, browser, provider, deployed
acceptance or dataset acquisition ran; no application files were changed.
Shared CI is unchanged and does not automatically prove this explicit standalone
test command ran. Remote checks are manager-reviewed separately at exact head.

## Outstanding acceptance / handoff

- Independent scientific/statistical and exact-head code review **pending**.
- Split/leakage controls, identity matching, graph/null models, calibration,
  clustered uncertainty, case adjudication/appeals, reviewer-load measurement,
  representative labels and licensed acquisition are **protocol proposals**, not
  implemented or empirically established.
- The CLI trusts caller-declared completeness and versions; fictional ID syntax
  is not proof inputs are synthetic. No network/privacy/OS sandbox claim.
- No author-fraud accuracy, field/career threshold, production readiness, graph DB
  benchmark, independent approval, integration, merge, deployment or issue closure.
- Risk/rollback: isolated new files only; do not integrate before review. If later
  accepted and withdrawal needed, manager can revert the task commit; no schema,
  persisted data or service rollback is involved. Next dependency is manager
  reconciliation and independent review, not another implementation lane's API.
