# CITE-03 synthetic metric plumbing

**Not a scientific accuracy benchmark or a misconduct detector.** All cases and
scores in the two fixtures are invented. No network, application/settings imports,
profiles, model calls, graph traversal or third-party dependencies. Future CITE-02
adapters require separate manager ownership and review; no moving sibling import.
The [evaluation protocol](../../docs/CITATION-INTELLIGENCE-EVALUATION.md) proposes
the scientific/human-review work this program does **not** implement.

## Run (Python 3.12+ stdlib; no installation)

From the repository root, Bash:

```bash
python -B -m unittest discover -s experiments/citation_evaluation -v
python -B experiments/citation_evaluation/evaluate.py < experiments/citation_evaluation/fixtures/complete.json
python -B experiments/citation_evaluation/evaluate.py --require-metric recall < experiments/citation_evaluation/fixtures/incomplete.json
python -B experiments/citation_evaluation/verify_math.py
```

The third command intentionally exits **2**, emits a bounded JSON error on stderr
and **no stdout report**. The default emits all metrics with `null` plus a reason
for each unavailable metric; it does not fabricate zero. `--require-metric` can
be repeated to fail the whole request if any requested metric is unavailable.
Valid reports exit 0. Standard `--help`/argument errors use argparse's text UI.

PowerShell does not support `<` stdin redirection; use:

```powershell
Get-Content experiments/citation_evaluation/fixtures/complete.json -Raw | python -B experiments/citation_evaluation/evaluate.py
```

On the delivery host the `python`/`pdftotext` PATH aliases varied between tool
invocations. Actual verification used the existing pinned Python executable:
`C:/Users/Axel/AppData/Local/hermes/tools/python-3.14.9+20261021-win32-x64/python.exe`.
An earlier post-implementation `python` invocation failed with “Python was not
found”; it is not counted as a test pass. No installer/environment changes made.

## Strict versioned input

`fixtures/complete.json` defines every required field. Extra or missing fields at
either object level fail. Root fields:

- `schema_version`: exactly `cite-eval-v1`; `synthetic_only`: exactly `true`.
- `as_of`: valid `YYYY-MM-DD`, supplied by fixture, never the running clock.
- `model_version`, `config_version`, `label_version`, `evidence_version`: 1–64
  ASCII tokens (`[A-Za-z0-9][A-Za-z0-9._-]*`). These bind declared identifiers;
  the CLI does not verify that external files/models actually exist or match them.
- `labels_complete`: strict boolean, asserting outcome completeness **within the
  supplied evaluation frame**, not representativeness of any real population.
  `true` plus any binary-unknown state is rejected as inconsistent.
- `review_budget`: strict integer 1–5000; booleans are not integers here.
- `rows`: at most 5000 rows with exactly `id`, `label`, `score`, `decision`.

IDs are unique `fictional-` strings followed by 1–54 lowercase ASCII letters,
digits or hyphens. Prefix checks are a fixture guard, **not a privacy detector**;
never pass real data disguised with a fictional ID. Labels:

| Label | Binary treatment |
| --- | --- |
| `confirmed_manipulation` | Positive (fictional assertion only) |
| `confirmed_nonmanipulation` | Negative within this fictional scope, not clearance |
| `other_retraction`, `anomaly`, `unknown` | Binary unknown, never negative |

`decision` is supplied `review`, `dismiss` or `abstain`, never inferred from a
threshold. Decided rows require a finite numeric `score` in [0,1]. It is **review
priority**, not a fraud probability. Abstentions require `score: null` and cannot
be ranked into the review queue. No threshold selection or detector training.

UTF-8 stdin is read to at most **1,048,577 bytes** and rejected above 1,048,576.
A string/escape-aware pre-scan rejects nesting deeper than 8 before recursive JSON
decoding. Duplicate JSON keys, NaN/Infinity (including overflowing exponents),
wrong types, invalid dates, unknown fields, duplicate case IDs and excess rows
fail. Output is JSON with finite numbers, bounded to 1 MiB, with no raw-input echo
in validation errors. No files/URLs are opened by the CLI. Complexity is bounded
by input bytes plus O(n log n) sorting and O(n) counting/output, n≤5000; no graph
nodes/edges/traversals exist. This is **not** an OS memory or hard wall-clock
sandbox: a pipe waiting for EOF or slow stdout can block; callers must impose their
own process/IO timeout (tests use 10 seconds), and use closed fixture files only.

## Metric semantics (deliberately explicit)

Let `review` be predicted positive and `dismiss` predicted negative. Abstention is
neither. `known_decided_confusion` counts only rows with a binary-known label and
a nonabstained decision. It is always descriptive and **not population confusion**
when unknowns or abstentions exist. Coverage reports total, decided, abstained,
binary-known and each original label count; decision coverage = decided/total
(`null` for empty). Accuracy is never replaced with decision coverage.

All metrics except descriptive queue P@B require `labels_complete: true`; this
conservative policy refuses even all-known rows if frame completeness is denied.

| Metric | Numerator / denominator | Semantics |
| --- | --- | --- |
| `selective_accuracy` | (TP+TN) / decided | Accuracy conditional on a nonabstained decision; always report coverage beside it |
| `precision` | TP / (TP+FP) | Yield of **all** review candidates, not just budget-selected cases |
| `false_discovery_proportion` | FP / (TP+FP) | Observed fraction, not statistical FDR control |
| `recall` | TP / all supplied positives | End-to-end candidate capture; positive abstentions count as missed capture, not negative predictions in the confusion table; **not recall@B** |
| `false_positive_rate` | FP / all supplied negatives | End-to-end false-review fraction; negative abstentions stay in denominator, so inspect coverage |
| `precision_at_budget` | positives in selected queue / B | Select top B **review** candidates by descending score then ascending ASCII ID; exact equality ties, no epsilon or random selection |

P@B remains a valid **descriptive selected-case yield** when the rest of the frame
has incomplete labels **only if all B selected labels are binary known**. It is
not an estimate of population precision/recall or proof the selection was unbiased.
Unknown selected labels or an unfilled budget refuse a value. No silent skipping of
unknowns or shrinking B; output selected IDs, unknown selected, unfilled slots,
candidate count and deferred candidates. Reasons have deterministic precedence:
`labels_incomplete` for gated cohort metrics; P@B uses `budget_unfilled` before
`selected_labels_unknown`; otherwise denominator zero gives `zero_denominator`.
Numerators/denominators accompanying unavailable metrics are diagnostic partial
counts, **not a valid ratio to compute downstream**.

Valid ratios include nominal `wilson95_iid` intervals with z=1.959963984540054,
Wilson score formula in [S12](../../docs/CITATION-INTELLIGENCE-EVALUATION.md#sources-primary-works--first-party-documentation), §3.1.1 equation (4).
Zero/all-success endpoints are clamped exactly to 0/1 to avoid floating-point
cancellation. These assume iid binomial cases and do not account for dependent
networks, case selection or imperfect adjudication. Do not use these fixture
intervals as scientific evidence. Unknown/zero-denominator ratios have no interval.

## Determinism and mathematical oracle

No randomness is used (seed not applicable); fixture as-of date is 2026-11-08.
SHA-256 hashes validated input serialized by stdlib `json.dumps`, sorted keys,
compact separators, UTF-8, rows sorted by ID. Row permutation and object-key order
do not change the digest or report. Numeric spelling normalized by JSON decoding;
integer 1 versus float 1.0 is **not** promised hash-equivalent. This is a Python
encoding contract, not RFC 8785 or a cross-language canonicalization claim.
All declared versions, labels, decisions, scores and budget are bound. A hash
establishes byte integrity, not scientific truth, license, approval or identity.
The reviewed code is pinned separately by the PR head SHA, not included magically
in `input_sha256`. Freeze input, code and runtime versions together.

The fixed complete fixture yields (verified using tools, not mental arithmetic):

- Known-decided confusion: TP=2, FP=1, TN=1, FN=1; one positive abstention.
- Precision and P@3 = 2/3; recall = 2/4 = 1/2 (includes that abstention).
- Selective accuracy = 3/5; coverage = 5/6; FDP=1/3; FPR=1/2.
- Precision's iid Wilson interval ≈ [0.20765960080204775, 0.93850805527960376].
- Input digest: `a7bf2c51d8bbd85b1eb8c24caa8e148f2d07fa81730ceb5e12c31ae66e480b7a`.

The incomplete fixture produces no metric values: one of the selected two labels
is unknown. An unresolved retraction and an abstained anomaly remain separate
unknown states. The counts are fictional and have no scientific interpretation.

`verify_math.py` independently uses `Fraction` and 40-digit `Decimal` calculations
for fixture ratios, Wilson(2,3), and the base-rate illustration: sensitivity 9/10,
FPR 1/100, prevalence 1/1000 give PPV=10/121. These are hypothetical inputs,
not estimated prevalence or measured detector performance.

## Verification record and limits

Initial TDD: stub `evaluate()` returned `{}`; full 17-test run actually failed
(27 failures / 15 errors including subtests), including `ValueError not raised`
and CLI success-on-invalid assertions. After implementation, 17 tests passed.
Expanded exhaustive control then exposed Wilson(0,3)'s rounded lower endpoint
above zero, and a missing fixture; fixed exact boundary handling and added the
fixture, then 20 tests passed. Later math/abstention tests and final results are
recorded in `VERIFICATION.md` and the exact-head draft PR.

Tests cover synthetic confusion/P@B, deterministic tie/permutation invariance,
version/label digest sensitivity, empty/all-unknown/all-abstain/zero denominators,
unknown not negative, unfilled queue, 99%-accurate all-negative failure control,
216 exhaustive three-case label/decision combinations, maximum row bound, malformed
JSON/duplicate keys/NaN/overflow/depth/bytes and strict types/IDs. These tests
establish metric behavior only. No dataset, adjudication, model, calibration,
temporal/provider leakage pipeline, performance benchmark or reviewer timing was
scientifically validated. Source papers are not ingested as case data.

No backend/frontend/database/browser/provider/app build tests are run: no such
code is changed and importing application settings/services is outside this task.
Shared CI is unchanged and may not discover this standalone suite automatically;
reviewers must run the explicit command. No production readiness or CI pass assumed.
