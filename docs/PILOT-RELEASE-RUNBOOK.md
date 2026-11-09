# Isolated pilot release and recovery — OPS-01

**Status: NO-GO / BLOCKED.** This document prepares a supervised pilot; it is
not deployment authorization. Reference issue #36. Baseline inspected:
`e1372a722b2f4e25ff38505238c62b93d0af49ad` (also `origin/main` when work began).
No production/cloud access, credential or `.env` reads, provider calls, shared
Compose invocation, migration edits or application deployment are part of this lane.

## Ownership and evidence boundary

- **OPS-01:** environment inventory, paired database/artifact backup, restore,
  recovery/rollback evidence and operating checklist.
- **DATA01:** record provenance, historical-result inventory, remediation and
  record-level acceptance. Recovering bytes does not establish valid provenance.
  OPS-01 must not rewrite records or declare DATA01's acceptance complete.
- **Manager:** choose release/candidate SHA, hosting and named operators; obtain
  independent review and current combined-tree checks; record explicit manual go/no-go.
- Hosting/security/support owners must be named before use. An unassigned owner,
  unknown topology, missing fixture or skipped check is **blocked**, not passed.

## Repository trace (definitions, not assumed deployed topology)

| Concern | Actual definition / implication |
|---|---|
| API image | `backend/Dockerfile`: Python 3.12, PDF system dependencies, Uvicorn `app.main:app`, image default port 8000. Image CMD does **not** run migrations. |
| Hosting API entrypoint | `backend/railway.toml`: `alembic upgrade head && uvicorn ... --port $PORT`; `/health` liveness. This is a proposed host definition, not evidence it is selected or deployed. |
| Worker entrypoint | `backend/railway-worker.toml`: `celery -A app.tasks.celery_app worker --beat --loglevel=info`. Same image/config/storage as API; no HTTP health listener. |
| Shared local topology | Root `docker-compose.yml` defines named shared DB/upload/report/artifact volumes, fixed container names and `.env` references. **Do not invoke it for this rehearsal**, including config commands that might resolve env files. |
| Frontend | `frontend/package.json`: Next 16.2; `next dev`, `next build`, `next start`. No hosting topology inferred. Assigned local frontend/backend ports are 3206/8206; no app servers are started here. |
| Migrations | `backend/alembic/env.py` loads app settings and executes migrations online. AST-only scan of `backend/alembic/versions/` finds one linear head: `0018_analysis_runs`. No advisory lock appears in this env definition, despite the Railway comment claiming one: owner must resolve serialization before multi-replica migration. Never use an app-settings import for offline preflight. |
| Durable execution | `backend/app/services/analysis_runs.py`, `backend/app/tasks/analysis_tasks.py`: DB-backed claims/events and reconciliation every 10 seconds. API/SSE liveness alone cannot prove queue progress. |
| Worker/beat | `backend/app/tasks/__init__.py`: hard/soft limits 300/240 seconds, task registration failures logged. Exactly one beat scheduler is required; extra worker replicas must not each run `--beat`. |
| Cleanup and schedules | `backend/app/tasks/cleanup.py`: daily cleanup, default 03:00 UTC. `scheduled_reports.py` removes the daily schedule; `routers/report_schedules.py` disables creation/execution pending durable tenant scope. Do not advertise scheduled delivery as ready. |
| Artifacts | `docs/artifact-storage.md` and `backend/app/services/artifact_storage.py`: local private artifact root or private S3 backend; legacy upload/report paths still matter. API, worker and cleanup require the same durable storage. Separate service disks are insufficient. |
| Health/monitoring | `backend/app/main.py`: `/health` is unconditional liveness, `/api/health` checks DB/Redis and returns 503 on degradation. `routers/health.py` deep probe contacts external providers: **do not call in this lane**. Sentry initialization is configuration-dependent, not proof of alert delivery. |
| Worker telemetry | `backend/app/tasks/observability.py`: best-effort run logs/DLQ, failures can be swallowed/debug-logged. Require independent worker/beat heartbeat and backlog alerts, not just these rows. |
| CI | `.github/workflows/ci.yml`: backend migrations/unit/required real integration with no skips; frontend types/lint/unit/webpack build/browser. Audit steps are advisory. A component green or unobserved workflow is not combined release acceptance. |

Related operational detail: [analysis execution](analysis-execution.md),
[artifact storage](artifact-storage.md), [CI runbook](CI-RUNBOOK.md).
Historical logs describe earlier tests, not fresh OPS-01 verification.

## Safe offline commands

Use Python 3.12+ with standard library only. No installs are required. Commands
run from this worktree, never from another lane. The approved existing scratch
Python may be used read-only (it is Python 3.14.9 here):

```powershell
$py = 'C:/Users/Axel/AppData/Local/hermes/cache/scratch/artiproof-audit-venv/Scripts/python.exe'
& $py -B -m unittest discover -s backend/tests -p test_pilot_rehearsal_safety.py -v
& $py -B scripts/pilot_rehearsal/rehearse.py preflight
$LASTEXITCODE # 2 means BLOCKED; tool wrappers may render all nonzero exits as 1
```

Preflight parses revision constants without importing application code or
executing migrations. It bind-probes only 127.0.0.1 ports **3206, 8206, 55446,
56446**, then closes each probe; it does not contact existing listeners. A free
probe is only a point-in-time result, never permission to terminate another owner.
Preflight always leaves release/recovery BLOCKED because it does not recover data.

If a reviewed native PostgreSQL installation is available, this **optional local
synthetic command** can be used; substitute an actual reviewed binary directory:

```powershell
& $py -B scripts/pilot_rehearsal/rehearse.py rehearse --pg-bin '<reviewed-native-PG-bin>' --confirm-synthetic-only
```

The CLI accepts no arbitrary endpoint, existing database, artifact source or
restore target. It creates a unique `ops01-*` child under
`C:/Users/Axel/AppData/Local/hermes/cache/scratch/ops-01/`, refuses existing run
paths, rechecks assigned ports immediately before starting, and uses a new native
cluster listening **only on 127.0.0.1:55446**. Synthetic role
`ops01_synthetic` and exact databases `ops01_synthetic_source`,
`ops01_synthetic_restore`, `ops01_synthetic_rollback` are not application accounts.
Loopback trust authentication is synthetic-only; other local users could access
this short-lived fixture, so never load real data. Child processes receive an
allowlisted OS environment and nonexistent explicit PG pass/service files, not
inherited application/provider/cloud/PG credentials. No root Compose, Docker,
Redis, network provider or app server is used.

The rehearsal seeds a tiny synthetic table and PDF-signature byte fixture, writes
a custom-format `pg_dump` plus artifact/hash manifest, simulates a bad release,
restores into **two new databases** (recovery and rollback), checks rows/artifact
references/SHA-256 and the backed-up migration marker, and stops only its unique
cluster via `pg_ctl -D <owned cluster>`. It never drops databases, overwrites an
existing target, or deletes the retained cluster/backups/evidence. Stop failure
blocks the result: inspect retained logs and have the lane owner stop only that
exact cluster, never a global PostgreSQL process. Do not restart global services.

**Limits:** a synthetic `alembic_version` marker is deliberately not an applied
application schema. This fixture tests backup mechanics only; it cannot establish
full application migration compatibility, real PDF rendering, live object storage,
Redis redelivery, host restart, record provenance or a deployed rollback. Mocked
unit lifecycle tests are command-contract tests, **not** real recovery evidence.
Even a successful optional run reports release BLOCKED and
`TESTED_SYNTHETIC_ONLY`, never production readiness. A failed/missing tool reports
BLOCKED and exits nonzero. Review `evidence.json`, `commands.json`, backup manifest
and logs; preserve them for the handoff. No automatic cleanup exists.

## Required stage plan — not executed hosting commands

All items below require a separately authorized, owner-approved stage environment.
No credentials, project names, buckets, endpoints or live topology are assumed.
**Do not run these steps against hosting under this assignment.**

1. **Freeze candidate:** record exact app/image SHA/digest, previous known-good
   image, dependency/PDF runtime versions and independent review. Verify required
   checks on the exact combined candidate, not only this documentation branch.
2. **Choose isolation:** named environment owner documents API/frontend/worker/
   singleton beat/DB/Redis/artifact topology, private ingress/storage/egress,
   synthetic test namespaces and access policy. Explicitly disallow default/shared
   databases. Native test tooling above is not a host configuration template.
3. **Quiesce:** stop submissions; drain durable runs; stop API writers, workers,
   beat, scheduled/cleanup jobs and old SSE executors. Record queued/running/
   expired jobs and active processes; no unapproved task retries/provider calls.
   Redis is delivery infrastructure, not the only recoverable record of intent.
4. **Paired recovery point:** while writers remain stopped, back up PostgreSQL
   schema/data/roles/extensions requirements and **all referenced artifacts**,
   including legacy upload/report roots and soft-deleted recoverable references.
   For object storage require private versioned snapshots/version IDs or a verified
   complete inventory/copy; a bucket name or public URL is not a backup. Record
   snapshot time, app SHA, DB head, reference inventory, checksums, encrypted backup
   location/access owner, retention, restore prerequisites and approved RPO/RTO.
   Verify dump readability AND a real restore; file existence is insufficient.
5. **Migration verification:** in a newly provisioned approved stage DB, compare
   repository `alembic heads`, DB `alembic current` and `alembic_version`; require
   one reviewed head and resolve unexpected branches/drift. Apply reviewed
   `alembic upgrade head` only after recoverable paired backups and explicit
   migration-owner approval. Check actual schema/data compatibility. Serialize
   migrations explicitly; do not rely on the unimplemented lock comment.
6. **Restore and rollback rehearsal:** restore paired DB/artifacts to new isolated
   targets, verify every expected reference/hash/count and sample authorized
   downloads using synthetic accounts. Verify app revision compatibility and
   recovery within approved RPO/RTO. Simulate failure and switch to a separately
   restored previous image + compatible DB/artifact pair with writers stopped.
   Prefer new-target restore over destructive in-place changes; no blind
   `alembic downgrade`, object deletion or old-image-only rollback. Account for
   accepted writes since the snapshot; owner approves their recovery/loss budget.
   Obtain DATA01's separate provenance/remediation signoff on the restored data.
7. **Cleanup hold:** backups outside cleanup roots; keep source objects/manifest
   for rollback. In `backend/app/tasks/cleanup.py`, periodic cleanup runs
   `hard_delete_expired_soft_deletes` **before** `remove_orphan_files`.
   `ARTIFACT_CLEANUP_HOLD_UNTIL` guards only orphan-file removal; DB hard deletion
   has no hold guard. Require **both DB hard-delete dispatch/execution and artifact
   cleanup to remain held throughout the rollback window**, including stage
   startup/restart. The operator must separately document and prove (a) how DB
   hard-delete dispatch and execution are prevented, including already queued or
   running cleanup, and (b) the effective artifact hold and its expiry on every
   cleanup process. No existing DB-hold flag or operational enforcement is claimed
   here; absent either proof, keep cleanup stopped and the gate **BLOCKED**.
   Re-enable either deletion path only after rollback-window closure and explicit
   owner acceptance. Retention/privacy and restore access are explicit decisions,
   not defaults. Do not delete preexisting resources.
8. **Start controlled stage:** compatible API/workers, one beat, correct shared
   artifact store and dedicated queues. Starting/restarting workers or beat must
   not resume cleanup prematurely: reverify both holds and separate operator proofs
   from step 7 before startup and after restart; otherwise keep cleanup stopped
   and stage acceptance **BLOCKED**. Confirm DB/Redis readiness, task
   registration, reconciliation, ownership fencing, no-SSE terminal completion,
   reconnect/replay and authorized artifact retrieval after process replacement.
   Prove real Redis and host-restart recovery separately. Deep provider checks
   need separate approval; routine tests must not incur model calls.
9. **Observability:** table below must have owners, approved thresholds and
   synthetic alert-delivery evidence before cohort access. Telemetry rows or
   Sentry config alone are insufficient.
10. **Manual decision:** manager records all gate evidence, DATA01 acceptance,
    named on-call/support owner and explicit GO/NO-GO with exact SHA/time/cohort.
    No automation here issues GO or starts a deployment.

## Operating gates and owner decisions

| Gate | Required evidence / owner decision (currently pending) |
|---|---|
| Recovery | Environment/recovery owner; paired restore and rollback on actual approved stage stack; agreed RPO/RTO and timed drill; DB/schema/reference/hash verification; off-host backup access and retention. |
| Worker/beat | Operations owner; independent heartbeat/scheduler count; oldest queued age, expired leases, retries, failures/DLQ and terminal events; alert if recovery stalls. Approve numeric thresholds and test routing/acknowledgment. |
| Service health | Operations owner; liveness distinct from readiness; synthetic 503/dependency outage alarm, API error rate/latency and artifact failure alarms. External-provider probes must not become restart gates. |
| Storage/DB | Storage owner; capacity, backup age/failure, restore failure, inaccessible/missing artifact, checksum drift and cleanup-hold expiry alerts. Audit private access without logging content/secrets. |
| Cohort/cost | Manager/product owner must enter numeric max organizations/users, concurrent/queued jobs, upload size/rate, daily provider budget and kill-switch/pause criteria. Until specified, **no cohort admitted**. Do not infer limits from UI copy. |
| Support | Named primary/backup, staffed coverage hours, contact/escalation path, acknowledgment targets and incident/rollback decision owner. Communicate uncertainty, availability and retention policy to the cohort. |
| Data | DATA01 supplies record provenance/remediation acceptance and remaining exclusions. Environment restore success cannot substitute for this. |
| Security/review | Manager/security owner; exact combined-tree backend/frontend checks and independent review; known advisory scanner results disposition; no self-approval. |

## Fresh OPS-01 evidence and exclusions

- Regression-first: safety test import failed before implementation existed
  (`FileNotFoundError` for `scripts/pilot_rehearsal/rehearse.py`); this was an
  expected red baseline, not a service failure.
- Initial offline preflight: static head `0018_analysis_runs`; assigned ports all
  free at probe time. `postgres_tools: []`; recovery and release **BLOCKED**.
- Native `initdb`, `pg_ctl`, `pg_dump`, `pg_restore` were not available on PATH;
  no reviewed native bin was found in checked standard installation locations.
  No PostgreSQL tools downloaded/installed, no Docker daemon contacted, no recovery
  claimed. Ruff 0.14.4 alone was installed in an OPS-01-owned scratch venv for
  changed-file lint; the existing shared scratch Python environment was not modified.
- Fresh safety suite: **16 passed, no skips**, exit 0, using the unittest command
  above. Changed-file Ruff 0.14.4 `check scripts/pilot_rehearsal
  backend/tests/test_pilot_rehearsal_safety.py` passed; `git diff --check` passed.
  Preflight and unconfirmed `rehearse` each returned **2 (BLOCKED)** as designed.
  Exact head SHA and hosted check state are recorded in the draft PR/handoff.
  Unit mocks must not be counted as a local PostgreSQL restore. Frontend/backend
  runtime suites were not rerun locally; runtime code was not changed.
- **Outstanding:** real DB+artifact recovery, application migration/rollback,
  approved stage hosting/storage/Redis/host-restart acceptance, alert delivery,
  cohort/support decisions, DATA01 provenance and manager manual go/no-go.

Next scope needed: manager supplies a reviewed native PostgreSQL binary path for
the optional synthetic drill, or assigns a separately authorized isolated stage
rehearsal to the environment owner. No recovery gate can be closed from this
preflight alone. OPS-01 does not request or need live credentials for this work.
