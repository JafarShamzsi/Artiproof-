# ArtiProof: from MVP to dependable product

Assessment date: 24 October 2026.

## Executive assessment

ArtiProof is a substantial research-integrity MVP with useful application infrastructure. Its central weakness is that the authority of the output exceeds the strength of the evidence behind it. More dashboard features will not resolve that problem.

The next release should deliver one dependable workflow: a researcher or research-office reviewer submits a manuscript, inspects evidence-backed reference findings, records decisions, and exports a report with explicit coverage and limitations. This is a proposed product direction to validate with users, not an established market finding.

Retain the existing application and improve it incrementally. A framework rewrite or more elaborate landing page would have little effect on the most consequential problems identified here.

## Scope and confidence

This assessment traced frontend submission/authentication, API routes, source and researcher pipelines, scoring, bibliographic integrations, reports, quotas, team trials, deployment configuration, and CI. Findings below distinguish confirmed code behavior, deployment consequences, and product recommendations. Repository documentation describes intent; executable paths take precedence when they conflict.

No deployed instance, customer interviews, production configuration, live external APIs, billing account, or operational metrics were examined. Thus this is a code-grounded readiness assessment, not a penetration test, visual UX audit, market validation, or certification of production behavior.

Verification:

- Executed selected pure production functions by extracting their AST definitions, avoiding unavailable third-party imports. Saved outputs in `product-readiness-evidence-2026-10-24.json`. This verifies calculation behavior, not service wiring or full application execution.
- An empty source result with a claim-extraction failure warning returns score 100 and confidence 0.5.b
- Three authors each citing a target four times, with only incoming edges and no cycles, produce a potential ring with confidence 0.54.
- A researcher calculation with 20 publications but zero checked citations produces integrity 100, confidence 0.5, and “No significant integrity issues detected.”
- Replaying the fallback rating substring condition maps both “incorrect” and “not true” to true.
- `python -m pytest -q` could not start: pytest is absent from the available Python environment. `frontend/node_modules` is absent; no frontend build, unit suite, or browser suite was run. No dependencies were installed and no services started.

## What the codebase does

### Application architecture

| Area | Implementation | Role |
|---|---|---|
| Web application | Next.js App Router, React, Tailwind; NextAuth | Marketing, authentication, dashboard, submission/results, teams, settings, admin |
| API | FastAPI, Pydantic, async SQLAlchemy | Ownership, accounts, CRUD, orchestration, exports |
| Persistence | PostgreSQL and Alembic migrations | Users, sessions, organizations, analyses, findings, reports, audit and usage records |
| Background execution | Celery, Redis, beat | Analysis tasks, scheduled reports, cleanup |
| Language models | Provider factory plus Gemini compatibility wrapper | Extraction, verdicts, AI estimates, narratives and topic analysis |
| Academic data | Semantic Scholar, ORCID, CrossRef, OpenAlex, optional Scopus/Scholar | Identity, publications, citation relationships and retraction signals |
| Files | Local upload/report directories; PyMuPDF, WeasyPrint | Text positions, annotations, report PDFs |
| Operations | Request IDs, optional Sentry/OTel, LLM metrics, Celery run logs/DLQ, CI | Diagnostics and administration |

### Source-check flow

1. Browser submits a URL, text, or PDF to FastAPI. Authentication and a tier quota dependency gate creation.
2. API creates a `SourceCheck` and attempts to enqueue a Celery task. PDFs are written to local disk.
3. Browser obtains a stream ticket and opens SSE. That endpoint also executes the analysis, rather than simply observing the queued job.
4. Pipeline scrapes a URL, extracts PDF text/positions, or uses supplied text.
5. Claim extraction examines the first 15,000 characters and requests at most 15 claims. Fact-checking uses Google Fact Check matches and an LLM verdict. AI estimation examines up to 20 paragraphs, presenting only the first 500 characters of each to the model.
6. Citation analysis consumes links collected by the URL scraper, capped at 20 checks. It checks accessibility, retractions where a DOI can be extracted, and a domain-based credibility heuristic.
7. The pipeline traces some problematic claims, saves findings and an additive credibility score, and attempts PDF annotation.
8. Users can inspect findings, export, compare, rerun, or create share links.

### Researcher flow

The worker first runs a scraping orchestration layer which stores publications and citation/coauthor data. The academic analysis layer then resolves the researcher again and fetches publications through a separate helper path. It samples incoming citations, flags patterns, estimates topic relevance, computes adjusted metrics, and saves publication analyses. Reruns preserve scalar snapshots while replacing prior publication-analysis rows.

There are therefore two data-collection paths with overlapping responsibilities. The analysis does not simply consume one frozen, canonical dataset produced by scraping. This creates extra external calls and opportunities for disagreement.

### Foundations worth keeping

Authentication includes backend session checks, password reset, email verification, Google sign-in, and 2FA surfaces. Organization membership and role checks, soft deletion, score breakdowns, prompt hashes, coverage warnings, report sharing, telemetry, administrative tools, and CI already exist. These are useful foundations; this is not a blank-slate prototype.

## Prioritized findings

P0 means resolve before representing the affected capability as trustworthy in a real pilot. P1 means resolve before a broader paid launch. P2 means subsequent product development, subject to pilot evidence.

### P0 — Missing evidence can become a positive result

**Confirmed.** Source scoring starts at 100 and only subtracts findings. Empty failed steps therefore remove opportunities to subtract. `_calculate_confidence` returns 0.5 when no factors exist. `_save_results` sets completed even when preceding steps emitted failures. The researcher pipeline similarly substitutes empty graph/ring data after failures and can generate an integrity score of 100.

Evidence: `backend/app/services/source_verification/orchestrator.py:386`, `:469`, `:584`; `backend/app/services/academic_integrity/orchestrator.py`; `backend/app/services/academic_integrity/rating_adjuster.py:195`; saved calculation outputs.

**Impact:** a provider outage or incomplete analysis can look reassuring. A warning does not correct an authoritative headline score.

**Required change:** model step outcomes explicitly: succeeded, partial, unavailable, unsupported, failed. Separate evidence coverage from finding severity. Do not emit a positive overall conclusion when required evidence is absent. Persist terminal job errors and show them consistently on results, public links and exports.

**Acceptance:** provider outage, malformed output, zero citations and extraction failure yield unavailable/partial states; none can become a clean bill of health.

### P0 — Citation rings are inferred without ring evidence

**Confirmed and reproduced.** Graph construction creates edges from citing authors to the target. Ring detection groups frequent citers and calls their summed incoming counts “mutual citations.” It does not establish reciprocal relationships or cycles between members. “Suspicious pairs” similarly use one incoming edge weight.

Evidence: `backend/app/services/academic_integrity/citation_graph_builder.py`; `backend/app/services/academic_integrity/ring_detector.py:98`, `:112`; saved star-graph example.

**Impact:** an ordinary cluster of researchers citing related work can generate a misconduct-adjacent flag and lower a person's integrity score.

**Required change:** immediately label the existing output as citation concentration for exploration and stop scoring it as established ring behavior. A future ring engine needs directed citation evidence, time windows, coauthor relationships, discipline baselines, deduplication and expert validation. Even a graph cycle is a candidate pattern, not proof of misconduct.

**Acceptance:** the reproduced star graph is not a ring; each candidate pattern links to the specific observed papers and relationships.

### P0 — Product promises conflict with the implementation

**Confirmed discrepancies.** `frontend/src/components/landing/PricingSection.tsx` claims:

- Plagiarism detection, although no document similarity/corpus-comparison engine was located in the executed pipelines.
- Accuracy above 95% on benchmark sets, without a corresponding evaluation dataset or reproducible benchmark located in this review.
- No content storage after analysis, while original PDFs, text input, claims and paragraph text are persisted.
- Native LMS plugins and institution capabilities for which delivery implementations were not located.
- Pro includes 200 readings, while backend constants permit 100 source checks.
- Free excludes researcher analysis and PDF export, while backend quotas allow five researcher analyses and five reports monthly.

The hero and onboarding tour also promise five engines on one submission, but researcher analysis is a separate workflow. The methodology page's plagiarism qualification does not supply the missing implementation.

**Required change:** make a capability-and-entitlement matrix the source of truth for pricing, onboarding, API gates and sales copy. Remove unsupported accuracy and retention claims immediately. Verify security/deployment claims against operational evidence rather than inferring encryption guarantees from application code.

**Acceptance:** every public capability is demonstrable, every numerical quality claim links to an evaluation, and tier copy matches enforced entitlements.

### P0 — API and SSE can execute the same job concurrently

**Confirmed execution paths; concurrency consequences inferred.** Creation queues a Celery task, while the stream endpoint invokes `run_pipeline_streaming` for the same ID. It rejects completed checks but does not atomically claim pending work or reject processing checks. The orchestrator commits processing without acquiring an exclusive job claim.

Evidence: `backend/app/routers/source_check.py:124`, `:362`, `:397`; `backend/app/tasks/source_check_tasks.py`; source orchestrator start/save behavior.

**Impact:** duplicate model spend, duplicate findings, conflicting writes and unpredictable disconnect behavior. The browser connection becomes coupled to execution durability.

**Required change:** workers own execution; SSE/polling only observe persisted progress. Introduce an atomic claim/lease, idempotent result persistence, attempt IDs, explicit failure transitions, reconciliation of stranded jobs, and safe retry/cancel behavior. Use durable enqueue coordination so a committed submission cannot silently remain unqueued.

**Acceptance:** concurrent worker delivery and repeated browser connections produce one committed result set; closing a tab does not stop the job; retries do not duplicate charges or findings.

### P0 — Queued PDF work lacks shared durable storage

**Confirmed in supplied configuration.** API uploads and worker-generated reports use local paths. Compose supplies no upload/report volume shared by API and worker; Railway defines separate services without a shared file abstraction.

Evidence: `docker-compose.yml`; `backend/app/routers/source_check.py:160`; `backend/app/services/report_engine/pdf_generator.py`; both Railway configs.

**Impact:** the worker cannot read an API upload in the supplied Compose topology. API downloads likewise cannot assume access to files generated by another service. Replacement containers can lose locally generated files.

**Required change:** store immutable file objects through a shared storage interface, with access-controlled downloads, lifecycle policies, content checksums and retention. Persist object identifiers instead of process-local absolute paths. A shared persistent volume can support local development, but does not replace an explicit production storage design.

**Acceptance:** upload through one API instance, process in a separate worker, restart both, and download through another API instance successfully.

### P0 — Server-side fetching is insufficiently constrained

**Confirmed code gap; no exploit attempted.** Source submission accepts arbitrary input strings. The scraper fetches supplied URLs and follows redirects. Citation accessibility requests follow extracted links. The separate logo validator blocks literal private addresses but explicitly does not resolve DNS; report rendering uses the default WeasyPrint fetch mechanism.

Evidence: `backend/app/schemas/source_check.py:6`; `backend/app/services/source_verification/scraper.py`; `citation_analyzer.py`; `backend/app/utils/urls.py`; PDF generator.

**Impact:** server-side requests may reach unintended internal destinations or consume excessive resources. Deployment egress controls could mitigate this, but were not verified.

**Required change:** centralize outbound fetching with allowed schemes, connection-time address restrictions, redirect validation, time/byte budgets and controlled renderer resource loading. Bound uploads before reading them fully into memory, generate server-owned filenames, and enforce storage-path containment.

**Acceptance:** controlled tests reject private destinations through literals, DNS and redirects; oversized downloads/uploads stop within bounded resource use.

### P1 — Citation review is incomplete for the main manuscript input

**Confirmed.** `citations_from_scraper` starts empty and is populated only by URL scraping. PDF extraction returns text and positions, not parsed references. Raw text likewise has no reference extraction. Thus PDF/text submissions do not feed their bibliographies into this citation checker.

Evidence: source orchestrator `:168`, `:198`, `:273`; `pdf_processor.py`.

**Required change:** parse reference sections and in-text citation links, resolve DOI/title/author/year candidates, expose ambiguous matches for confirmation, and retain extracted reference text. Add OCR or a clear unsupported scanned-document state. Distinguish a reference not found from one not checked.

**Acceptance:** representative PDF and text manuscripts produce a reference inventory with verified matches, ambiguous matches and unresolved references, each with coverage counts.

### P1 — Fact-check output is not consistently grounded in retrieved evidence

**Confirmed.** When Google Fact Check has no match, the prompt asks the model to judge from its knowledge. It uses at most 500 characters of article context, and model source strings are accepted without fetching and validating supporting passages. Similar-claim matches are not a demonstrated entailment check. In the no-Gemini fallback, substring matching checks “correct” before “incorrect,” reversing that verdict; “not true” also matches true.

Evidence: `backend/app/services/source_verification/fact_checker.py`; saved substring replay.

**Required change:** separate retrieved evidence from model interpretation. Verify source existence, capture supporting passages and dates, and abstain when evidence is absent or does not address the exact claim. Replace substring rating interpretation with explicit normalized mappings and unknown outcomes. Define supported claim types; novel research findings may not have independently verifiable external answers.

### P1 — AI likelihood is presented more precisely than its implementation supports

**Confirmed implementation.** A model estimates probability from style; the fallback uses sentence regularity, transitions and contractions. Results are averaged per paragraph, not by document coverage or word count. Leading samples and 500-character snippets are used. AI estimates subtract from credibility despite measuring a different concept from factual correctness.

Evidence: `ai_detector.py`; source orchestrator `_calculate_credibility` and `_save_results`.

**Required change:** keep authorship-style signals separate from factual/referential findings. Do not treat generated probabilities as calibrated confidence. Evaluate representative human, AI-assisted, edited and translated writing by language and discipline before making accuracy claims. The present heuristic can remain an explicitly labeled experiment, with no adverse decision authority.

### P1 — Researcher identity, sampling and adjusted metrics need redesign

**Confirmed.** Name lookup takes the first search match. ORCID lookup obtains a name then searches Semantic Scholar, potentially attaching the supplied ORCID to a different same-name author. The analysis fetches up to 100 publications, checks 15 highly cited papers and up to 50 incoming citations each; it does not paginate those analysis helper calls. Incoming counts from a biased sample are extrapolated to total citation counts. Suspicious author counts can overlap on coauthored citing papers. Adjusted h-index is computed by multiplying h-index by a citation ratio, rather than recomputing from per-paper eligible citations. Field-specific detector thresholds also differ from fixed thresholds in the rating adjuster.

Evidence: `academic_integrity/scholar_scraper.py:35`, `:72`, `:114`, `:159`; academic orchestrator; graph builder; `rating_adjuster.py:66`, `:82`.

**Required change:** introduce identity candidates and confirmation, verify identifier mappings, preserve dataset scope and sampling bias, deduplicate citing works, and separate provider-specific totals. Either recompute h-index from a sufficiently complete per-paper dataset or label an estimate accurately. Do not present a sampled ratio adjustment as an exact corrected metric.

### P1 — Streaming UI does not match emitted event types

**Confirmed code mismatch; not browser-tested.** Source and researcher forms listen with `EventSource.onmessage`. The source server emits named events such as `started`, `fact_checking` and `complete`, which are not delivered to the default message listener. The source form consequently cannot rely on its handler for progress and completion; its error path redirects on stream closure.

Evidence: `frontend/src/app/(dashboard)/check/page.tsx:119`; corresponding researcher page `:137`; source router event generator.

**Required change:** use one documented event contract and subscribe correctly, preferably against observer-only progress endpoints. Add a full submission-to-result browser test, including reconnect and completion while the tab is closed.

### P1 — Billing and quota behavior do not yet form a commercial lifecycle

**Confirmed.** Billing webhook uses stub processor events and a generic signature format. Self-serve checkout is explicitly unfinished. Trial expiry is stored and displayed, but no enforcement reference was located beyond creation/model/schema/UI. Quotas count non-deleted resource rows, so deleting a check can restore allowance; researcher reruns are not naturally represented by resource creation counts. Quota checks are non-atomic by design. Team quotas are unlimited in constants. A known billing event with an unmatched user returns 202 after rollback, without durable deferred processing; redelivery cannot be assumed from a successful HTTP status.

Evidence: `billing_webhook.py`; `utils/quota.py:73`; constants; organizations router; frontend settings billing section; repository-wide trial-expiry search.

**Required change:** select a commercial model and implement subscription/trial states, durable billing reconciliation and provider-specific event handling. Maintain an append-only usage ledger for attempts/reservations, consumption and refunds, independent of deletion. Define seat-level versus pooled budgets and bounded trial spend. An assisted paid pilot can use explicit invoicing and operator-managed entitlement states before self-serve billing is ready.

### P1 — Authentication and provider abstractions are only partly integrated

- Backend refresh/logout routes exist, but the shared frontend API client signs out on 401 and no call to backend refresh/logout was located in that client or NextAuth integration. Standard sidebar logout invokes NextAuth sign-out. Finish backend session revocation on logout and expiry/refresh behavior end to end.
- Model factory supports alternative providers, but analysis engines still gate execution on `GEMINI_API_KEY`. A deployment configured only for another provider can skip extraction/detection. Saved analysis metadata hardcodes Google/model settings even when the factory can serve another provider. Citation alternatives directly instantiate Gemini outside the central client.
- Analysis preferences such as `check_citations` and `trace_misinfo_origins` are defined and editable but no pipeline consumption was located. Completion/low-score notification preferences similarly need an execution audit; scheduled-report email preference handling does exist.

Evidence: `frontend/src/lib/auth.ts`; `frontend/src/lib/api.ts`; dashboard layout; `services/llm/factory.py`; claim/AI engines; source orchestrator `:568`; constants and settings schemas.

**Required change:** make one backend capability/configuration contract authoritative, record the actual provider per operation, and wire or remove controls that currently do not change behavior.

### P1 — Reproducibility and human review stop short of a usable evidence record

**Confirmed foundations, incomplete workflow.** Prompt hashes and formula versions exist, but do not alone preserve the input data, external responses or exact decision environment. Source URL checks retain the URL and extracted findings, not a complete immutable retrieval snapshot. Researcher snapshots preserve metrics but reruns delete prior publication-analysis rows. Teams provide membership/activity/audit functions, but no dedicated finding-review, disposition, reviewer assignment, comment, appeal or case state model was located.

**Required change:** define Submission, AnalysisRun, EvidenceSnapshot, Finding, ReviewDecision and ReportVersion as separate concepts. Preserve who reviewed what evidence and why. Support confirmed/dismissed/unresolved findings with reasons and an audit trail. Generate versioned reports from frozen run/review state; revoke or expire public access independently. Source-check share links currently have revocation but no expiry field, unlike report shares.

### P1 — Tests establish many local behaviors, not the complete product contract

**Confirmed.** CI includes lint/type checks, backend unit tests, frontend unit tests, migration application and Playwright smoke tests. This is useful. However, default pytest explicitly excludes integration tests; CI uses that default and has no Redis service. Browser coverage is mostly landing/auth/team surfaces, not the full PDF/worker/result journey. Vulnerability audits are non-blocking. No benchmark harness establishing real detection quality was located.

**Required change:** gate releases on realistic application journeys with Postgres, Redis and a separate worker, plus deterministic external-provider fixtures. Run integration-marked tests explicitly, exercise migration upgrades from an existing database, test cross-org access, retry/concurrency and file survival. Separate correctness evaluation from unit tests: a test reproducing an arbitrary score does not validate its scientific meaning.

### P2 — Maintainability and operational proof

Several pages combine extensive fetching, state and UI (notably settings); frontend API types mirror backend schemas manually. Scoring and tier claims live in multiple places. These make inconsistent behavior easier to introduce. Split modules along stable product boundaries after the critical workflow is defined, and generate/validate API contracts.

Operational tooling exists, so the next work is proving recovery: database/object-store backup restoration, stranded-job reconciliation, provider-outage behavior, alert ownership, support runbooks and budget limits. No production readiness conclusion can be drawn from optional telemetry configuration alone. Run beat separately from horizontally scaled workers to avoid multiplying schedule dispatchers.

Scheduled reporting also needs a product contract: it currently aggregates at most 20 recent checks and includes non-completed records in the query, converting missing scores to zero. Label the window/sample honestly, aggregate completed comparable results only, and represent no activity as no data rather than score zero.

## Product gaps beyond code defects

### Choose the buyer and recurring decision

The repository addresses students, researchers, research offices, committees and institutions, plus both journalism-style fact-checking and academic bibliometrics. These users have different evidence standards, budgets and review workflows. A broad menu does not establish product-market fit.

Recommended initial hypothesis: research-office staff or journal editors reviewing manuscript references before deeper review. Their useful output is a prioritized evidence queue and completed review report. Validate that hypothesis with actual buyers before committing to institution-wide misconduct screening.

Interview a small set of design partners around a recent real submission: what triggered review, which tools they used, how long it took, who could decide, what evidence was needed, and what happened next. Test a real manuscript/report walkthrough rather than asking whether they like an AI platform.

### Complete the review loop

Current emphasis is submit → score → export. A professional workflow needs submit → verify identity/input → inspect coverage → review evidence → resolve ambiguity → record decision → export/share a versioned record → revisit when evidence changes. Team membership alone does not provide that loop.

### Make uncertainty actionable

“Not checked,” “no match,” “provider unavailable,” “paywalled,” “metadata conflict,” “retraction notice found,” and “reviewer dismissed” are distinct states. Boolean accessibility/retraction fields collapse too many of these. A failed HEAD request is not proof a paper is invalid, and absent retraction data is not proof it is unretracted.

### Match regional positioning with actual coverage

English-only UI is a documented choice. The more urgent research question is whether identifier resolution, source coverage and extracted references work on the Azerbaijani, Russian and English materials intended customers actually submit. Measure that before allocating translation work. Language coverage claims should follow evidence.

### Define the business unit and operating cost

Decide whether customers buy checks, manuscripts, reviewer seats, or institution budgets. Measure provider spend, processing time and human review time per successfully completed review. Deletion-independent metering and retry/refund rules must follow this choice. Telemetry is already present, but real gross margin and willingness to pay were not available for this assessment.

## Recommended target product boundary

Keep one application and database, with clear module responsibilities:

1. **Submission and storage:** validated inputs, object identifiers, identity confirmation, retention policy.
2. **Durable analysis execution:** run/attempt state, leases, persisted step progress, budgets and cancellation.
3. **Evidence adapters:** normalized provider results, timestamps, snapshots, explicit failure states.
4. **Findings:** evidence-linked observations with coverage and method versions; no automatic accusation.
5. **Review workspace:** assignments, comments, dispositions and decision history.
6. **Reports:** immutable exports of a chosen analysis/review version, controlled sharing.
7. **Commercial access:** subscription/trial state, entitlements and usage ledger.

This does not require microservices. The existing FastAPI/service structure can implement these boundaries, with the worker performing long-running execution.

## Staged delivery plan

| Stage | Work | Exit condition |
|---|---|---|
| 0: Honest pilot boundary | Correct public claims/tiers; disable or relabel unsupported conclusions; introduce unavailable results | No incomplete run claims clearance; all marketed pilot capabilities demonstrable |
| 1: Dependable execution | Worker-only execution, atomic claiming, event contract, durable storage, fetch restrictions, terminal failures | PDF journey passes across separate API/worker processes, retries, disconnects and restarts |
| 2: Reliable reference review | PDF/text references, metadata matching, retraction evidence, tri-state availability, immutable snapshots | Expert-reviewed representative corpus meets predeclared matching/coverage/false-positive criteria |
| 3: Professional workflow | Review decisions, assignments, report versions, privacy/retention controls, bounded trial/commercial lifecycle | A design partner completes real reviews and can explain and retrieve every reported finding |
| 4: Expand on evidence | Validated graph analytics, carefully scoped claim verification, integrations, localization | Pilot demand and evaluation results justify each added capability |

These are dependency stages, not time estimates. Staffing, provider access, evaluation data and pilot feedback determine duration.

## Release gates and metrics

- **Truthfulness:** all public capability, retention, pricing and quality claims checked against a demo and evidence record.
- **Execution:** one effective committed result per run; no silent permanently processing jobs; bounded retry cost; recovery demonstrated after worker/API restart.
- **Evidence quality:** a labeled corpus with held-out evaluation; precision/recall or matching accuracy by finding type; coverage and unknown rate; false-positive review for each supported language/discipline.
- **Review utility:** time to first useful finding, completed review rate, time to resolution, reviewer acceptance/dismissal rates and repeat weekly use. Dismissal alone is not ground truth; adjudicate disputed examples.
- **Privacy/access:** cross-user and cross-org tests, explicit retention behavior, deletion/export checks, share revocation/expiry, verified restoration and file lifecycle.
- **Economics:** cost per completed review, retry/provider waste, bounded free/trial consumption, paid-pilot conversion and actual support load.
- **Operations:** named alert/support ownership, actionable dependency health, queue-age monitoring and documented recovery drills.

Set numerical quality targets with design partners before running the held-out evaluation. Do not invent a universal accuracy percentage or declare success from unit-test count.

## Immediate backlog order

1. Correct retention/accuracy/plagiarism claims and tier inconsistencies.
2. Replace reassuring scores for missing evidence with unavailable/partial outcomes.
3. Relabel frequent-citer detection and remove unsupported misconduct implications.
4. Make workers the only execution owners; fix event delivery and duplicate execution.
5. Introduce shared durable file storage and constrain outbound fetches.
6. Deliver PDF/text reference extraction and evidence-backed reference results.
7. Add realistic integration journeys and a human-labeled evaluation corpus.
8. Build finding dispositions and versioned reviewer reports with pilot users.
9. Finish usage/trial/billing lifecycle and end-to-end session handling.
10. Expand features only after repeat usage and evaluated quality justify them.

The defining transition is from generating impressive results to helping a specific reviewer complete a repeatable decision with evidence they can inspect and defend.
