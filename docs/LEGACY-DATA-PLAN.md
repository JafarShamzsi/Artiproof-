# Legacy metadata inventory and reversible remediation design

**[DATA-01] / axel-windows — draft, references #32.** Source baseline:
`e1372a722b2f4e25ff38505238c62b93d0af49ad` (main). Retain existing data;
do not replace it with a fresh database to claim legacy acceptance.

## Authority and evidence boundary

This change implements **offline synthetic metadata classification only**.
No historical inventory, customer-content read, database connection, backup,
restore, quarantine, token revocation, record mutation or deployment was performed.
The findings below describe source behavior, **not evidence that a production
record exists or was exposed**. No approval for real-environment access or writes
is implied. Every action below is a proposal requiring separate authorization.

Related acceptance remains open in #19 / #25 and historical PRs #23 / #27 / #29.
Their new-enrollment/report-scope protections are not legacy repair evidence.
The pilot readiness plan must link #32's eventual approved inventory, recoverable
backup, independently reviewed mappings, and recipient/resource authorization
evidence before pilot release. Manager owns that cross-lane plan update; this lane
does not edit it. OPS-01 (#36, `docs/PILOT-RELEASE-RUNBOOK.md`) owns environment
recovery rehearsal, not record remediation logic.

## Source provenance trace

Paths are relative to `backend/`; inspect the exact release tree again before a
future authorized audit. Model comments alone are not authoritative.

| Source | Observed behavior / inventory consequence |
| --- | --- |
| `alembic/versions/0012_org_id_on_owned_resources.py:43-73` | Adds nullable org FKs to source checks, researcher profiles and reports. Actual SQL copies every matching non-null `users.organization_id`; unlike the docstring's tier wording, SQL has no tier, resource-creation-time or consent filter. A stamped org is not original ownership proof. |
| `alembic/versions/0013_organization_members.py:100-133` | Inserts memberships for non-deleted users with an org pointer (no tier filter); promotes the smallest member user ID per org. `joined_at` default is insertion time, not consent time; null inviter/admin role is not consent evidence. |
| `app/models/organization_member.py`, `organization_invite.py`, `organization_audit_log.py`; `app/services/team_invites.py:71-112` | Current acceptance requires active, email-verified authenticated recipient, persisted live invite and explicit acceptance, then membership/pointer/accepted timestamp and bound audit actions. Invite `status=accepted`, inviter presence, joined time, current membership or email-domain matching alone cannot establish historical recipient authorization. Do not export invite tokens, email, or raw audit payload. |
| `app/models/source_check.py`, `researcher.py`, `researcher_snapshot.py` | Resource user/org and lifecycle timestamps must be inventoried separately from current user org. Original/annotated PDFs, clones sharing references, snapshots and child results remain dependent records; their text is outside scope. |
| `app/models/report.py:21-67`; `app/routers/reports.py:_derived_scope`, `_require_report_input_scope`, `generate_report` | Reports have scalar and JSON-array resource references, own stored scope, cached PDF and annotations. Current generation derives common input scope and regeneration rejects drift/missing inputs. That does not prove old report scope, original input set or cached PDF branding. Inventory every scalar and array reference, not just the first. |
| `app/routers/reports.py:_share_link_alive`, shared JSON/download routes, `_serve_report_pdf`; `alembic/versions/0010_report_share_expiry.py` | Public report bearer access and cached PDF access require separate review from authenticated resource checks. 0010 backfills expiry from creation +90 days; current helper treats null expiry as alive. An expired link does not prove it was never accessed. A cached PDF can outlive the provenance assumptions used to create it. |
| `app/models/source_check.py:49-51`; `app/routers/source_check.py:issue_share_token`, `revoke_share_token`, `get_shared_source_check` | Source sharing is a separate optional bearer token with no expiry column, distinct from report sharing. Record token presence/state only; never export tokens, hashes usable as correlators, share URLs or content. |
| `app/models/report_schedule.py`; `app/tasks/scheduled_reports.py:run_due_schedules`, `schedule_beat` | Model lacks durable original scope/input provenance. Current task raises before DB work and beat removes unsafe sweep. Keep disabled; do not infer historical summary inputs from today's user/org or latest activity. |
| `app/utils/ownership.py:is_owner_or_org_admin` | Current direct-owner or same-org-admin authorization is not historical provenance. Model membership docstring's broader member-read wording is not the helper's implemented rule. |
| `app/services/artifact_storage.py`; `app/cli/migrate_artifacts.py`; `app/tasks/cleanup.py` | Artifact references may be shared and cleanup/migration can affect rollback. Existing artifact-copy migration is not an ownership/consent remediation tool. Preserve alias groups, soft-deleted/recoverable references and cleanup holds. |

The baseline has a linear migration chain through `0018_analysis_runs` (file
`0018_durable_analysis_runs.py`). This lane adds/changes no migration and runs none.
Synthetic upgrade-shaped cases model 0012/0013 effects; they are **not executed
Alembic upgrades or PostgreSQL integrity/isolation tests**.

## Future privacy-minimal inventory (blocked on separate read approval)

Manager/data owner must approve exact environment, snapshot identifier, metadata
columns, purpose, retention period, operators and secured evidence location first.
Use an independently reviewed read-only extractor on an approved snapshot, not
this synthetic tool. No production export is accepted by this CLI. Reconcile
paginated counts, exclusions, FK/array edges and missing evidence explicitly.

Required restricted inventory fields (not all belong in synthetic classifier):

| Group | Minimum fields and review rules |
| --- | --- |
| Snapshot | Inventory schema/tool/release SHA, migration head, snapshot/backup ID, extraction cutoff UTC, table counts including soft-deleted rows, pagination completeness, unavailable fields, reviewer and approval IDs. |
| Record identity | Restricted opaque record mapping, kind/table, owner reference, stored org (including explicit null), creation/update/deletion timestamps, lifecycle status and version/precondition fingerprint. Public handoffs contain aggregates and opaque review references only. |
| Provenance | Candidate original owner/scope, contemporaneous creation evidence reference and timestamp, migration exposure/window or uncertainty, contradictory evidence and confidence category. Keep **unknown** distinct from proven personal/null. Current org is diagnostic only; never ownership evidence or a default mapping. |
| Membership/consent | Org/recipient/invite/audit opaque references, historical role, invited/joined/accepted/revoked timestamps, authenticated recipient binding, exact org/role/action and policy scope at acceptance, transaction/event correlation, known legacy origin and missing/contradictory evidence. Do not infer consent from a successful registration or current pointer. |
| Derived resources | All scalar and array input references with kinds, cardinality, missing/deleted inputs, historical scopes and creation-time authorization evidence; report template/type, cached-renderer/version/branding provenance where available; schedule origin and original scope/input set if provable. Unknown summary inputs stay unknown. |
| Artifacts | Presence/type, restricted opaque artifact alias/version, parent/clone/shared-reference edges, size/checksum and backup-manifest reference in secured OPS evidence, storage backend category, recoverability/hold state. No raw filesystem/object paths, PDFs or body fetches in this lane. |
| Shares | Token **presence only**, resource kind/reference, expiry/revocation state and timestamps, authorization/recipient evidence availability, distribution/access evidence availability and redacted incident-review reference. No token, token digest, URL, IP, recipient address or raw access log export. |
| Remediation | Proposed classification/action/reason, evidence gaps, restricted before/after mapping, affected dependencies, expected row counts, artifact/share disposition, approvals, rollback mapping, verification results and journal status. |

Exclude customer names, email addresses, document titles/text, source URLs,
researcher/publication text, annotations, narratives, claims, raw JSON payloads,
credentials and bearer tokens. Metadata remains sensitive: minimize and restrict
the real inventory, including IDs/timestamps/hashes, even when content is absent.

## Synthetic classifier contract

From `backend/`, with a local Python interpreter (stdlib only):

```text
python -B -m unittest tests.test_legacy_data_audit -v
python -B -m tools.legacy_data_audit --synthetic-input tests/fixtures/legacy_data_audit/upgrade.json
```

The tool imports no application/config/database/storage code, consults no env
configuration, and has no SQL, network, apply, output-file or production mode.
It reads only the explicitly named synthetic `.json` file and prints proposals.
Do not supply a real export, even with names removed. `synthetic: true` is a
required declaration, **not an automated guarantee that input is synthetic**.
UNC/device/URL prefixes are rejected lexically before filesystem probes, with
both separator spellings normalized (including mixed `/\` prefixes). File
symlinks are rejected before reading. Operators must use
local fixtures; this is not an OS sandbox capable of detecting mapped network
drives, every ancestor mount or maliciously relabeled real metadata.

Input is an exact object `{schema_version: 1, synthetic: true, records: [...]}`.
One to 1,000 records; JSON input at most 1 MiB. Duplicate JSON keys, unknown keys,
non-finite constants, invalid enums/types/aliases and duplicate record IDs fail
closed. CLI errors are static and never repeat arguments, paths or input values.
Direct API callers must also supply only synthetic metadata.

Each record must contain exactly these fields (see the checked-in fixture):

| Field | Accepted values |
| --- | --- |
| `id` | Synthetic alias `syn-1` through `syn-999999`, unique within input. |
| `kind` | `membership`, `source_check`, `researcher_profile`, `report`, `schedule`. |
| `stored_scope`, `historical_scope`, `current_user_org` | Synthetic alias or null. `current_user_org` is deliberately ignored by classification. Null historical scope means personal **only if** creation evidence is declared. |
| `scope_evidence` | `unknown`, `creation_record`. This is a fixture assertion, not independently validated proof. |
| `origin` | `unknown`, `native`, `migration_0012`, `migration_0013`. Backfill origin remains ambiguous even if other assertions match; independently approved later remediation must establish new evidence. |
| `consent`, `consent_audit_bound` | `unknown` / `recipient_accepted`, and strict boolean. Membership needs both accepted and bound evidence; these fixture flags cannot certify actual consent. |
| `inputs` | Unique synthetic input aliases, at most 25, only on reports. Missing/deleted/non-base-resource inputs, nested reports and cycles fail closed as quarantine proposals. |
| `artifact` | `none`, `original_pdf`, `annotated_pdf`, `cached_pdf`, `unknown`. One summarized category per synthetic row; not a complete artifact inventory/alias model. |
| `share` | `none`, `active`, `expired`, `revoked`, `expiry_unknown`. States are fixture assertions, not computed from a live clock or token inspection. |
| `deleted` | Strict boolean. Deleted records remain held, never resurrected. |

Output contains only input **ordinals**, fixed reason/action enums and fixed
status flags. It never echoes aliases, scopes or arbitrary strings. It is a
review aid, not an executable mapping or authorization result:

- `quarantine_proposed`: ambiguous/backfilled/contradictory provenance, missing
  consent, missing/drifted report inputs, unknown artifact provenance, active or
  expiry-unknown bearer share, deleted record, or schedule without durable origin.
- `consistent_metadata_review_only`: supplied synthetic assertions agree;
  **not cleared, safe to release, verified consent or approved ownership**.
- Every result requires manual review. Artifact presence proposes a preservation
  hold review; any share presence proposes disable/disposition review, even if
  expired/revoked. No restamping/deletion occurs. Report ambiguity propagates
  from all declared base inputs; incomplete inventory cannot be detected from
  omitted-but-otherwise-valid fixture assertions.

The six-record upgrade fixture expects five quarantine proposals (legacy member,
0012 source plus bearer share, conflicting researcher, conflicting cached report,
scope-free schedule) and one review-only personal source unaffected by current
org. Tests cover mixed personal/org inputs, absent/deleted/self/membership inputs,
recipient binding, strict metadata rejection, deterministic non-mutating output
and CLI boundaries. They do not prove actual database authorization, completeness,
chronology, recipient identity, migration execution or production prevalence.

## Proposed remediation, never silent restamping/deletion

1. **Preserve and contain:** after separate approval, apply a reviewed reversible
   deny overlay/quarantine to ambiguous memberships/resources and dependent
   reports, authenticated exports, public JSON/PDF shares and artifacts. This
   baseline has no general quarantine model; designing/testing its schema and
   enforcement is a future security/data implementation scope, not performed here.
   Do not substitute soft deletion, nulling orgs, changing owner IDs, removing the
   last admin, or moving rows to a new employer as a shortcut. If quarantine
   enforcement is unavailable, affected surfaces/cohort remain blocked.
2. **Membership:** obtain authenticated recipient re-consent to the exact org,
   role and resource-sharing scope, with verified recipient identity and durable
   audit binding. Membership re-consent does not retroactively authorize old
   resources or shares. Declined/unreachable recipients remain quarantined;
   authorized removal, last-admin recovery and notification require explicit
   manager/security/legal decisions. Do not email anyone in this offline run.
3. **Record mapping:** reviewer compares contemporaneous evidence, not current
   pointers. Record each proposed old owner/scope -> explicit new owner/scope
   (including deliberate personal/null) with evidence, confidence, alternatives
   and rollback. No evidence means **no mapping**, continued quarantine. Preserve
   the original stored values in a secured immutable journal, not public output.
4. **Reports/artifacts:** include all derived inputs, shared artifact aliases,
   clones, snapshots and soft-deleted recoverable records. Retain old PDF versions
   under restricted backup/hold. After scope and recipient/resource authorization
   are independently established, regenerate into a new private artifact/version;
   verify before publishing a new reference. Do not overwrite an old cached PDF
   or regenerate an inputless summary from current-org history. Unknown schedules
   remain disabled until a separately reviewed durable scope implementation.
5. **Shares:** review source and report bearer links independently. Restrict or
   revoke old shares after approval; newly authorized sharing uses new tokens and
   recipient/resource checks. Do not copy old bearer tokens into evidence, and
   do not silently reactivate them during rollback. Already downloaded external
   copies cannot be recalled; manager/privacy owner decides incident handling
   based on separately approved evidence, not an assumption of exposure.

### Reversible mapping/journal specification (future tool, not executable here)

Require immutable plan ID/digest, snapshot+release+schema IDs, record/edge aliases,
exact before/after values, expected row versions/fingerprints and counts, evidence
references, explicit operation and inverse, dependencies/alias groups, artifact
version manifests, quarantine/share policies, approver IDs/time, and rollback
deadline/hold ID. A secured lookup binds aliases to actual keys; never publish it.

An independently reviewed executor must compare preconditions immediately before
each transaction, stop on any drift/missing edge/count mismatch, journal intent
before changes and outcome afterwards, and enforce actor/resource authorization.
Use conditional updates, idempotency keys and transactional group boundaries;
no broad `UPDATE ... FROM users`, wildcard deletes, inferred default owner/org,
or cross-database assumptions. Resuming must reverify committed state and retained
artifacts; failure leaves quarantine intact. Define and test crash boundaries
between DB journals and object versions before obtaining write approval.

Rollback reverses only verified journaled mappings with matching postconditions,
restores original artifact references/versions and validates counts/edges. Drift
halts rollback for manual review; never overwrite intervening legitimate changes.
Keep deny overlays and unsafe old shares disabled until explicit safe-release
approval. Restoring compromised authorization is **not** successful rollback.
Retention/deletion of preserved versions is a later approved lifecycle decision.

## Backup/restore prerequisites and manual gates

| Gate | Required evidence / responsible owner |
| --- | --- |
| G0 — read scope | Manager + data/privacy owner approve environment, snapshot, metadata fields, operator, purpose, retention and access isolation. Historical audit is blocked until then. |
| G1 — recovery | OPS-01 supplies coherent DB snapshot **and** versioned artifact backup, migration heads, counts/checksums/alias manifest, isolated restore logs, RPO/RTO observations and rollback/hold window. Verify restored DB references resolve to retained artifact versions, including soft-deleted/shared refs; no cleanup worker may destroy them. Rehearsal must not bind live shares or send emails/tasks. Synthetic rehearsal is not production backup verification. |
| G2 — dry-run inventory | Separately approved read-only extractor produces reconciled inventory and exact before/after diff; prove zero source writes, complete pagination, missing provenance counts, no content/token output, no deletion/restamping, and a reviewed hold/deny list. Distinguish unavailable from zero. |
| G3 — independent plan review | Manager, security reviewer, data/privacy owner and OPS review exact release/tool/plan digests, per-record mappings, dependency graph, re-consent evidence, recipient/resource authorization matrix, rollback, crash/retry tests and restored-snapshot rehearsal. DATA cannot self-approve. |
| G4 — write authorization | Separate explicit environment/time/cohort/write approval, named operator/approver, maintenance/worker/cleanup hold, fresh backup verification and monitored abort thresholds. No approval implied by issue, merge, CI or draft PR. |
| G5 — release/rollback decision | Execute only reviewed bounded batches; compare exact counts/edges/hash manifests and authorization denials/positive controls for owner, prior/new-org admin, recipient and public JSON/PDF. Manager decides go/no-go or rollback; preserve quarantine on uncertainty. OPS verifies environment recovery; DATA verifies record mappings. |

No G0-G5 production evidence has been gathered by this lane. Real PostgreSQL
authorization/mapping/crash acceptance, actual backup recoverability, customer
re-consent, live object storage, incident assessment and pilot release remain
blocked on their respective owners and separate approvals. No merge/deploy.

The existing `ARTIFACT_CLEANUP_HOLD_UNTIL` guards orphan-file removal, **not**
`hard_delete_expired_soft_deletes`. OPS must explicitly prevent both DB hard
deletion and artifact cleanup for the entire approved rollback window; setting
only the artifact hold is insufficient.

## Local verification record

Initial interpreter used read-only with `-B`:
`C:/Users/Axel/AppData/Local/hermes/cache/scratch/artiproof-audit-venv/Scripts/python.exe`.
Final tests use an own scratch venv at
`C:/Users/Axel/AppData/Local/hermes/cache/scratch/data-01/venv/` (Python 3.14.9).
Only Ruff 0.14.3 was installed there; the shared interpreter was not changed.
Stdlib `unittest` avoids loading repository pytest `conftest.py`, whose autouse
rate-limiter fixture imports application configuration. No dependencies or env
files are needed by this tool. Other backend tests are not local evidence here.

- Initial regression run: missing new module (one import error; not a behavior test).
- Against validation + review-only scaffold: **21 tests, 15 failures** including
  subtests, reproducing the specified conservative-classification requirements.
- After classification implementation: **21 tests passed**, no skips. This is
  synthetic fixture/unit/CLI evidence only, not historical or service evidence.
- Expanded boundary regression: **27 tests, 3 failing UNC/URL subtests** before
  adding pre-filesystem path rejection; **27 passed, zero skips** afterwards.
- `python -B -m ruff check --no-cache tools/legacy_data_audit tests/test_legacy_data_audit.py`:
  passed. No shared/global dependency installation or cache mutation.
- Explicit fixture CLI: five quarantine proposals and one review-only result;
  no aliases/content/tokens in stdout, `production_audit_performed: false`.

Frontend/types/build and unrelated backend/service suites were not run locally:
only new stdlib offline tooling, synthetic fixtures/tests and this doc changed.
Hosted results, if observed, are separate component evidence, not legacy audit,
deployment, full privacy-lifecycle or production clearance.

Scratch evidence directory:
`C:/Users/Axel/AppData/Local/hermes/cache/scratch/data-01/`.
Final exact SHA, expanded tests/checks and remote CI observations are recorded in
the draft PR / #32 handoff; no blanket green or release-readiness claim is made.

### Independent-review correction

PR38 comment 6694721583 blocked the original head: raw-prefix matching missed
Windows mixed-separator UNC paths. The successor first reproduced **10 failing
subtests across 29 tests** with all reachable filesystem entrypoints and socket
creation forbidden. A lexical-only separator normalization now rejects UNC and
device prefixes before path construction/probes. The 40-spelling matrix covers
all four slash/backslash prefix pairs, UNC and extended/device forms, and both
tail separators; six mocked local-path controls and the actual local fixture CLI
remain accepted. No reviewer probe script was executed or edited, no UNC path was
actually probed, and no network/authentication effect is claimed. Classifier
policy is unchanged. Fresh independent review of the exact successor is required.
Initial successor CI failed this test before argument handling: Python 3.12/Linux
argparse invoked gettext, which attempted a local locale-file stat forbidden by
the regression. The test now supplies a pure identity message translator only;
all filesystem/network prohibitions remain active. That failed CI is not passing
evidence, and final-successor results are recorded separately in the PR handoff.
