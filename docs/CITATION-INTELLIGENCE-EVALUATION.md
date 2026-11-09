# Citation intelligence: evaluation and supervised case-review protocol

**CITE-03 · issue #58 · 2026-11-08 · proposal, not an approved scientific benchmark.**
Assigned source base: `47fb9d79f3e5cbdf9062579f1d65b2e253f2486a`.
The acknowledged README-only main advance does not change this source assessment.
This slice supplies methodology and fictional metric plumbing only. It collects no
profiles, changes no application detector/threshold/API, selects no graph store,
and authorizes no deployment, public ranking, blacklist or misconduct decision.
All future evaluation/acquisition gates below are **proposed**, manager-owned work.
No dependency on CITE-02's moving implementation or contract is introduced.

## 1. What is being measured—and what is not

Keep four distinct objects: **observed anomaly**, **evidence confidence** (identity,
date, provenance and coverage), **analyst disposition**, and **adjudicated outcome**.
A large count, community membership, reciprocal author citations, or a model's
confidence is not evidence of intent by itself. Authorship association does not
identify which coauthor selected a reference. A journal suppression or a retraction
for another reason cannot become an author-fraud label.

Current code, read-only at the assigned base:

- [`ring_detector.py`](../backend/app/services/academic_integrity/ring_detector.py#L1-L6)
  explicitly says sampled incoming relationships do not establish reciprocity,
  cycles or manipulation; legacy pair/ring arrays are empty (lines 149–164).
- [`citation_graph_builder.py`](../backend/app/services/academic_integrity/citation_graph_builder.py#L51-L104)
  selects leading publications and fetches bounded incoming samples, deduplicates
  citing/cited work pairs and author IDs, and returns sample coverage (146–161).
  This is not a complete directed author network or a conditional null model.
- [`orchestrator.py`](../backend/app/services/academic_integrity/orchestrator.py#L237-L277)
  calls the builder with 15 papers and then summarizes those observations.
  [`researcher.py`](../backend/app/models/researcher.py#L104-L158) has publication,
  citation and coauthor records; [`researcher_snapshot.py`](../backend/app/models/researcher_snapshot.py#L17-L42)
  preserves scalar/JSON analysis snapshots, not the complete immutable evaluation
  manifests proposed here.
- [`test_ring_detector.py`](../backend/tests/test_ring_detector.py#L119-L150) and
  [`test_researcher_evidence.py`](../backend/tests/test_researcher_evidence.py#L43-L104)
  protect concentration-not-ring, deduplication and missing-evidence semantics.
  These application tests were inspected, **not executed** in this offline task.

Out-of-scope limitation for manager: `ring_detector.py:129–147` uses lifetime count
divided by age relative to the current clock as “velocity”; it does not demonstrate
a time-series burst. Its field thresholds (14–24) are explicitly heuristic. Neither
is adopted as a validated cutoff here; no application fix is made.

## 2. Primary-literature conclusions and transfer limits

Sources [S1]–[S13] below were fetched as full articles/PDFs or official documentation,
with relevant methods, results and limitations inspected. The task-local
[source ledger](../experiments/citation_evaluation/sources.json) records anchors,
support and exclusions. Search leads/snippets are not evidence. Grounded-citations
tool discovery returned no available tool; the ledger is a local substitute, not
an externally verified citation service. This is a bounded review, not a systematic
survey or an exhaustive correction registry search.

### CIDRE: journal-level evidence, not researcher-fraud accuracy

Kojaku, Livan and Masuda [S1] construct annual directed **journal** networks from a
January 2020 MAG snapshot, counting citations to papers in the preceding two-year
JIF window. CIDRE compares weighted edges to a degree-corrected stochastic block
null model preserving incoming/outgoing strengths and block citation volumes in
expectation; filters edges with tail tests and Benjamini–Hochberg adjustment;
and iteratively retains donor **or** recipient roles. It is not just mutual pairs:
asymmetric donor-to-recipient groups can survive. Its clipping, time window,
minimum mass and thresholds are part of that method, not universal career rules.

The corrected Figure 2 caption reports **11 of 22 suspended journal groups** found
in the suspension year or before; the Results text separately describes 12 found
at least once under its overlap criterion. These are different statements, not
an overall accuracy/precision estimate. The comparator is a selected JCR suspension
list, not an exhaustively adjudicated population of researchers or all journals.
Additional detected groups are not automatically verified cartels; missing MAG
references/retracted papers can cause misses. The paper expressly rejects automated
decision-making as a substitute for expert judgment [S1, Results/Discussion].

The **2022 author correction [S2]** fixes Figure 2(a)'s yearly versus bi-yearly
x-axis labeling and missing panel (c) y-axis/JCR legend. It is a figure-presentation
correction, not author-level validation or a new accuracy experiment. Use the
corrected article and retain the correction relationship in the source manifest.

Important retrospective limit: [S1, Methods, Null model] fits journal blocks on
the **2000–2019 aggregate**, then computes annual expectations. An earlier-year
detection in that retrospective analysis is not, without replay, a prospective
prediction made using only knowledge available in that year. Our future protocol
must fit/update blocks using only information available at each cutoff.

Fister et al. [S3] offer a multilayer author/paper representation and simulated
RDF/SPARQL examples, in a **Perspective**, not a representative labeled author
validation study. We do not import its example threshold, its inference of intent
from coauthorship, or its probability language. A schematic result is not evidence
of real-world precision. CIDRE itself explains why ordinary field communities
would create false positives if treated as cartels [S1, Introduction].

### Direction, time and normalization

Karrer and Newman [S4, §§II–III] show why ordered directed null models must respect
vertex ordering as well as degree sequence. Their models allow multiedges and
are not uniform over all topologies; empirical agreement varies by property
[S4, §§III.2, V–VI]. They do not establish a misconduct detector. In our proposal:

1. Preserve directed **citing-work → cited-work** source assertions before author
   projection. Distinguish publication interval/precision, reference/version event,
   observed-at and ingested-at; an aggregate count's retrieval date is not the
   time of each citation. Do not forcibly erase apparent cycles caused by versions,
   corrections or imprecise dates; quarantine impossible well-dated assertions.
2. Compare simple in/out-degree or strength-conditioned baselines, then
   field/community/year/type/age-conditioned baselines. Fit fields/communities
   as-of, not from a full future graph. Small cohorts require partial pooling or
   abstention with sensitivity analysis, not invented robust field percentiles.
   A more complex null is a hypothesis to validate, not automatically a better one.
3. Keep an observed-sample denominator separate from the population denominator;
   a truncated incoming-only sample cannot supply outgoing citation opportunity.
   Provider absence, identity ambiguity and unknown dates are unavailable, not zero.

| Candidate observable | Required comparison and counterevidence | Failure/abstention condition |
| --- | --- | --- |
| Author reciprocity across different papers | In/out opportunity, topic/field/year/career cohort; separate self/coauthor paths; show underlying work pairs | Incoming-only or ambiguous author projection cannot establish two-way activity; paper-pair reciprocity is not author reciprocity |
| Donor/recipient concentration | Both directional denominators and size/block-conditioned expectation; compare asymmetric and symmetric groups [S1] | Missing donor references/recipient coverage means no normalized residual |
| Directed motifs/small groups | Prespecified motif family, degree/time/block nulls; expose all supporting edges and projection weights | Shared authorship or one duplicated source must not create multiple independent paths; community alone insufficient |
| Bursts/change points | Actual event/observation series, lag/coverage/type/cohort controls; compare method/guideline release and special-issue explanations | Lifetime total divided by age cannot establish a sudden burst; missing time series/baseline means unavailable |
| Self-citation/coauthor overlap | Report separately; field, paper type, consortium size and career-length sensitivity | High overlap/count is neither intent nor an adjudicated positive |

Projection rule must be frozen (e.g. fractional mass across unique authors versus
unique-pair counting) and compared in a sensitivity analysis. Same name is not
identity; same institution or collaborator is not misconduct. OpenAlex documents
both false merges and splits, changing IDs, and citation-based identity signals
[S10]. Preserve identifier/source/version/merge-split history and confidence;
abstain where identity remains unresolved. Because identity resolution can itself
use citations, validate it independently to avoid circularly manufacturing
reciprocity and calling that confirmation of the identity.

## 3. Prospective evaluation contract (not implemented by the metric CLI)

Pre-register target unit (case/group, not silently paper/author/journal), eligibility,
sampling frame, costs, dates, candidate budget, label definitions, feature/null
versions, test families and deployment population before inspecting holdout results.
Manager and domain reviewers must agree stopping/acceptance criteria; no numeric
scientific accuracy target or universal discipline/career cutoff is invented here.

### Time and entity leakage controls

- Train on observations available by **T0**, tune/calibrate on the subsequent
  **(T0,T1]** window, evaluate once on sealed **(T1,T2]** holdout. Dates and label
  maturation lag must be justified for the intended use, not chosen for favorable
  outcomes. A later notice can supply a later adjudicated outcome, but cannot be
  a prediction-time feature. A paper published before T0 but first discovered
  after T1 is not retroactively available at T0.
- Freeze identity/dedup/topic/community/baseline fitting, feature selection,
  calibration and threshold/budget policy on training/tuning only. No full-graph
  embeddings or future-connected community estimates in an earlier replay.
  Preserve an untouched prospective dataset after any holdout-guided revision.
- Separate **new-entity generalization** from **longitudinal monitoring**. For the
  former, hold out authors, connected case groups and closely linked communities
  as groups; quarantine cross-boundary work/case families or report their overlap.
  For the latter, recurring authors may be allowed but disclose dependence and
  disallow training on their future labels. Do not assert both designs at once.
- Canonicalize DOI/aliases/version families and underlying directed work pairs
  before split assignment. Mirrored provider records, repeated notices and
  multiple cases from one episode stay in the same fold. Provider-held-out
  evaluation must remove overlapping underlying works/assertions, not merely
  rename the source; report remaining overlap and provider coverage shifts.
- Audit split membership and knowledge cutoff with immutable manifests. Test
  deliberate duplicate injection, shifted observation dates and a future-label
  feature as leakage negative controls. Report exclusions, not only retained rows.

These are proposed controls informed by [S8, taxonomy §§2.4/3]: duplicate,
temporal, preprocessing, nonindependence and sampling leakage are distinct.
The source's broader survey is not a citation-fraud evaluation. This CLI does not
claim to implement split/identity/provider leakage detection.

### Outcome quality, blinding and positive-unlabeled data

Maintain the original multi-state label and evidence, never a bare “retracted” bit:

| Case state | Binary evaluation treatment |
| --- | --- |
| Confirmed citation manipulation under a documented competent process | Positive only for the specified case/unit/time and stated finding; preserve authority and notice/appeal status |
| Confirmed nonmanipulation within a sufficiently reviewed scope | Negative only for that scoped evaluation; not lifetime clearance |
| Retracted for another reason | Separate state; **unknown for citation manipulation**, not positive or negative merely due to retraction |
| Statistical anomaly / analyst concern | Candidate observation, binary unknown until independently resolved |
| Unknown/unreviewed/disputed/insufficient evidence | Unknown; neither negative nor an automatic false positive |

Crossref documents multiple notice types and reason vocabularies, and less complete
coverage for corrections/expressions of concern [S11]. Fetch and read the notice
and subsequent correction/reinstatement only in a separately authorized study;
absence from an index is not a negative label. Preserve competing notices.

Proposed adjudication: two independent domain experts initially blind to detector
score, threshold and queue rank; use randomized case order and matched random
controls. They inspect the same pinned paper references, context and coverage;
record label, confidence in evidence, scope, rationale and counterevidence
separately. Conflicts of interest require replacement. Preserve both votes, raw
agreement/confusion and disagreement reasons; a third reviewer resolves only
with documented rationale, otherwise retain disputed/unknown. Blinding may be
imperfect because public notices reveal status; record every unblinding.

Allow subject response, factual correction and appeal to a reviewer not responsible
for the first decision. Keep original and superseding decisions, timestamps,
evidence versions and access audit trail. Re-open affected cases after source or
identity corrections. Do not turn an analyst's queue disposition into a formal
misconduct determination. No autonomous blacklist or public real-person ranking.

LLM role is restricted to **source-linked evidence summarization and hypothesis
assistance**. Every factual statement must resolve to a retrieved source/version
and supporting passage inspected by a human; hypotheses are labeled as such and
counterevidence is retained. Never fabricate evidence, notices, quotes, references,
identity links or labels, and never let an LLM adjudicate misconduct or convert its
output into verified ground truth. Treat retrieved text as untrusted content, not
instructions; redact private notes under a separately approved data policy. LLM
confidence is not evidence confidence. This task makes no model/provider calls.

Known positives plus unreviewed candidates form **positive-unlabeled**, not
positive-negative, data. Elkan and Noto [S6, §2, Lemma 1] require positive examples
selected completely at random for their probability rescaling. Visibility and
investigation selection cannot simply be assumed random here. Thus no PU-derived
fraud probability or population recall/false-positive rate without validated
selection assumptions or a label-complete probability sample. Report descriptive
yield among fully adjudicated selected cases and missingness instead. If sampling
is enriched for positives, report design/weights and do not transport its precision
to the deployment base rate. The CLI deliberately implements no PU estimator.

## 4. Metrics, false positives, calibration and reviewer load

Predeclare the review budget **B**, tie policy and candidate eligibility. Report
precision@B only when all B selected cases have resolved binary outcomes; an
unresolved case consumes review time, not an invented negative. If there are fewer
than B candidates, report queue fill and refuse P@B rather than silently shrink B.
Also show known/unknown counts in the queue and all deferred candidates.

Report recall only in a label-complete evaluation frame, explicitly counting
positive abstentions as missed capture for end-to-end recall. Report abstention
coverage independently of conditional accuracy among decided cases. Stratify all
counts/coverage/yield by field, year/career stage, type (review/method/guideline),
consortium size, language/geography where lawful, provider and coverage/identity
confidence. Report low-support cohorts as insufficient, not ranks. Include
eligibility and extraction/matching failures in the coverage flow.

For complete labels, show TP/FP/TN/FN with the unit and abstained positives/negatives;
precision, false discovery **proportion** FP/(TP+FP), false positive rate FP/N,
and recall TP/P have different denominators. FDR is an **expectation** over repeated
testing, not merely one observed FP fraction [S5, §2.1]. The CLI returns an observed
proportion, never a guarantee that scientific FDR is controlled.

Multiplicity: register all edge/motif/cohort/window hypotheses and the family
size, including unsuccessful tests and parameter searches. [S1] uses BH; [S5,
Theorem 1] proves its stated guarantee under independence conditions. Network
edges, overlapping windows and learned communities are dependent and model-fitted
p-values need checking. Before claiming FDR control, require statistician-reviewed
valid null p-values and a dependence-appropriate procedure or validated null
simulation of the entire search. Do not reset the family to selected candidates
or treat a p/q-value as the probability an author committed misconduct.

Base rate matters [S7, PRC sections]. Algebraically,

`PPV = sensitivity × prevalence / (sensitivity × prevalence + FPR × (1 − prevalence))`.

**Illustration, not a prevalence estimate or benchmark:** hypothetical prevalence
1/1000, sensitivity 9/10 and FPR 1/100 yield PPV **10/121 ≈ 8.26%**. On a fictional
100,000-case population the expected counts would be 90 true alerts and 999 false
alerts. These are expected arithmetic counts, not measured outcomes. The rational
calculation is executable in `verify_math.py`. High specificity/accuracy alone
can still imply unacceptable reviewer load; a mostly-negative classifier can
look accurate while missing every positive (covered by the synthetic tests).

Separate model calibration from adjudication. [S9, §§2/4] defines empirical
calibration and uses held-out data; its image/text experiments do not validate a
citation detector. If future outputs are called probabilities, evaluate reliability
bins (with sample counts), Brier/log loss, subgroup/temporal calibration and
uncertainty on held-out adjudicated outcomes. Fit any recalibration on tuning
only; finite-sample calibration on one selected cohort is not an individual's
probability of fraud and does not establish intent. Current heuristic/evidence
confidence must not be relabeled calibrated probability. The CLI's [0,1] score
is **ranking priority**, not calibrated probability; calibration is not implemented.

Uncertainty: always show raw numerator/denominator. The CLI provides nominal
95% Wilson score intervals [S12, §3.1.1], **assuming independent binomial cases**;
these are illustrative plumbing, not network-valid scientific intervals. Zero
denominators are unavailable. For a future study, prespecify cluster resampling
at independent episode/community units and temporal blocks, with fixed seed,
resample count and interval method reviewed before results. Disclose too few
independent clusters, adjudication uncertainty, missing-label sensitivity and
selection bias rather than manufacture narrow intervals. More bootstraps do not
repair biased labels. No inferential method is implemented here beyond iid Wilson.

Reviewer load must include candidates/day, queue fill, unknowns, deferred cases,
duplicate episodes, time to inspect sources, median/p95 reviewer minutes, second
reviews, disagreements, appeals and time to correction. Measure these in a
separately approved study, not from CPU time. Compare a random budget baseline,
simple opportunity-conditioned baseline and each added feature under the same
budget/sampling frame; ablate identity/projection/coverage assumptions.

## 5. Counterexamples, monitoring and reproducibility gates

Require explicit legitimate controls: small coherent fields; a review with a long
bibliography; a method/software/guideline used by an entire community (also seen in
[S1]); consortia with many coauthors; a continuing research program with justified
self-citations; career-length/exposure changes; annual bibliographies; and changes
in provider indexing. Include asymmetric donor groups, reciprocal groups across
different papers, isolated degree-matched controls, identity merge/split collisions,
mirrored providers, missing dates, truncated incoming-only coverage and unseen
fields. Synthetic positives establish observability only, never intent or accuracy.

For each future run, freeze content-addressed input and split manifests, permitted
raw evidence/source revisions and license, canonicalization and identity map,
graph/projection generation, knowledge/event cutoffs, feature/null/model/code SHA,
configuration/threshold/budget/tie versions, label/adjudication revision, seed and
runtime/dependency versions. No wall-clock-dependent features in reproducible replay.
Hash canonical bytes and define their ordering; a digest establishes integrity of
those bytes, **not truth, consent, license or managerial approval**.

Monitor changes in coverage, unknown/abstention rates, label age, identity merges,
feature/null residual distributions, cohort mix, precision@fixed budget and reviewer
load. Agree alert budgets and suspension criteria with reviewers before use; no
performance thresholds are selected from current heuristics. A new provider/model
or material drift triggers shadow re-evaluation, not automatic score continuity.

Stale-source correction procedure: record the new source/notice and predecessor;
mark affected assertions, identities, labels and analysis outputs superseded;
propagate removals/reinstatements through canonical work edges, author projections,
cohorts/communities/nulls and cached case evidence; rebuild a new pinned generation;
re-evaluate and notify reviewers/appeal owners. Keep old runs auditable with visible
supersession, subject to approved privacy/license retention. A retrospective
corrected rerun is not the same as a historical knowledge-as-of replay. Any optional
graph/search store is a rebuildable projection proposal, not presumed infrastructure;
no database/query-performance claim follows from this offline metric implementation.

## 6. Bounded acquisition proposal—requires separate authorization

Do **not** run it now. Proposed first acquisition is a manager-approved,
work-level, licensed sample, not researcher profile crawling or bulk snapshots:

- At most **200 works, 2,000 directed reference assertions, 20 public notices,
  100 individual document requests, 50 MiB retained bytes and one hour**; whichever
  bound is reached first stops acquisition and marks coverage partial. These are
  provisional safety caps, not scientific sample-size justification or paid spend.
  Domain experts must justify a larger study's power/precision before approval.
- Approve an explicit DOI/work allowlist, fields/time windows and random/control
  sampling plan. Obtain a bounded metadata export from a licensed/public source
  such as OpenAlex's CC0 metadata [S10,S13], plus publisher-hosted notices with
  checked reuse terms [S11]. Source data licenses do not automatically license
  article full text, private notes or copied figures. Do not download full profiles,
  full database snapshots, paywalled content or private records.
- Verify license/terms, public source URL, provenance, observation time and version
  for each record; keep reference direction and document type. Obtain permission
  where uncertain, otherwise omit/abstain. No automated recursive expansion beyond
  the allowlist, paid APIs, credential access or cross-tenant private material.
- Store pseudonymous work/case keys for evaluation; restrict notice/person mapping
  to authorized reviewers with retention/appeal policy. Public metadata does not
  authorize public guilt labels. Publish only synthetic examples or separately
  cleared aggregates, never an investigatory real-person ranking.
- Go/no-go: manager/license/privacy review, expert adjudication capacity, immutable
  split/label plan, source completeness audit, and independent exact-head review.
  Retraction-only/enriched samples cannot establish population base rate or recall;
  even this sample needs explicit selection-bias limits. All incomplete labels stay
  unknown. No collection authorization is implied by this document or draft PR.

## 7. Delivered artifact and independent-review checklist

[`experiments/citation_evaluation/`](../experiments/citation_evaluation/) is stdlib,
standalone, bounded JSON input/output with fictional fixtures. See its README for
exact metric denominators, CLI failures, TDD evidence and actual checks. It does
not train a detector, build a graph, enforce temporal/entity splits, calibrate a
model, collect data or adjudicate a case. Future CITE-02 adapters are proposed only
and must be manager-owned after independent reviews of both exact heads.

- [ ] Reviewer checks source anchors/limitations, CIDRE correction and no
      journal-validation-to-author-fraud transposition.
- [ ] Reviewer reruns full standalone tests and math oracle at exact PR head;
      checks unknown, abstention, ties, zero denominators and resource limits.
- [ ] Manager reconciles proposed contracts/ownership and future acquisition gates;
      no application integration, independent approval or readiness assumed.
- [ ] Manager checks remote required CI/security results and integrated head later;
      local synthetic tests are not backend/PostgreSQL/browser/provider evidence.

## Sources (primary works / first-party documentation)

[S1]: https://www.nature.com/articles/s41598-021-93572-3
[S2]: https://www.nature.com/articles/s41598-022-19033-7
[S3]: https://www.frontiersin.org/journals/physics/articles/10.3389/fphy.2016.00049/full
[S4]: https://arxiv.org/html/0907.4346v1
[S5]: https://www.math.tau.ac.il/~ybenja/MyPapers/benjamini_hochberg1995.pdf
[S6]: https://cseweb.ucsd.edu/~elkan/posonly.pdf
[S7]: https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0118432
[S8]: https://arxiv.org/html/2207.07048v1
[S9]: https://arxiv.org/html/1706.04599v2
[S10]: https://help.openalex.org/data/authors/disambiguation
[S11]: https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/
[S12]: https://projecteuclid.org/journalArticle/Download?urlId=10.1214%2Fss%2F1009213286
[S13]: https://help.openalex.org/access/overview

- **[S1]** Kojaku, Livan & Masuda (2021), *Detecting anomalous citation groups in
  journal networks*, Scientific Reports 11:14524. doi:10.1038/s41598-021-93572-3.
  Results/Data, Figure 2, Discussion, Methods/Null model and Change history.
- **[S2]** Same authors (2022), author correction, Scientific Reports 12:14698.
  doi:10.1038/s41598-022-19033-7. Full correction text and original figure caption.
- **[S3]** Fister Jr., Fister & Perc (2016), *Toward the Discovery of Citation Cartels
  in Citation Networks*, Frontiers in Physics 4:49. doi:10.3389/fphy.2016.00049.
  Perspective, §§3–5; artificial examples and explicit real-world caution.
- **[S4]** Karrer & Newman (2009), *Random graph models for directed acyclic
  networks*, arXiv:0907.4346v1 / Phys. Rev. E 80:046110.
  §§II–III (ordering/ensemble), V–VI (empirical limitations).
- **[S5]** Benjamini & Hochberg (1995), *Controlling the False Discovery Rate:
  A Practical and Powerful Approach to Multiple Testing*, JRSS B 57:289–300.
  Author-hosted scanned full paper, pp.291–293, §§2.1/3.1 and Theorem 1.
- **[S6]** Elkan & Noto (2008), *Learning Classifiers from Only Positive and
  Unlabeled Data*, KDD '08, pp.213–220. doi:10.1145/1401890.1401920.
  Author-hosted full PDF; §2, Lemma 1 and §7; random-positive-selection assumption.
- **[S7]** Saito & Rehmsmeier (2015), *The Precision-Recall Plot Is More Informative
  than the ROC Plot When Evaluating Binary Classifiers on Imbalanced Datasets*,
  PLOS ONE 10:e0118432. doi:10.1371/journal.pone.0118432.
  Theoretical Background/PRC and Results; general metrics, not misconduct data.
- **[S8]** Kapoor & Narayanan (2022 preprint), *Leakage and the Reproducibility
  Crisis in ML-based Science*, arXiv:2207.07048v1, §§2.4/3 and own civil-war
  reanalysis. Version pinned; not a citation-detector empirical result.
- **[S9]** Guo et al. (2017), *On Calibration of Modern Neural Networks*,
  arXiv:1706.04599v2 (main text plus supplement), §§2/4–6.
  Image/document experiments and same-distribution assumption; no fraud calibration.
- **[S10]** OpenAlex, *Disambiguation*, first-party documentation, updated
  2026-10-27: signals, July 2023 upgrade, special IDs and known failure modes.
- **[S11]** Crossref, *Retraction Watch*, first-party documentation, updated
  2025-01-19: notice sources, update types and controlled reasons; not ground truth
  of citation manipulation.
- **[S12]** Brown, Cai & DasGupta (2001), *Interval Estimation for a Binomial
  Proportion*, Statistical Science 16:101–133. doi:10.1214/ss/1009213286.
  Full publisher PDF, §3.1.1 equation (4); binomial, not network dependence.
- **[S13]** OpenAlex, *Access overview*, first-party documentation, updated
  2026-11-03, CC0/data-versus-service distinction; no blanket full-text rights inferred.
