# Durable analysis execution

Migration `0018_analysis_runs` introduces a durable run and ordered progress
events. API submission commits the resource, run, current-run pointer and initial
event in one PostgreSQL transaction. The Redis broker delivers run IDs; its
availability does not decide whether the submission exists.

Workers atomically claim queued runs. Duplicate delivery cannot claim a running
or terminal run. Each business commit locks the resource and checks its current
run, owner token and unexpired lease before flushing changes. Leases last 360
seconds, longer than the configured 300-second Celery hard limit. Provider calls
may repeat after a crash; this does not promise exactly-once external requests
or exactly-once provider charges.

SSE endpoints authorize the resource, then replay committed events. Connecting,
reconnecting or disconnecting never starts or cancels analysis. `Last-Event-ID`
resumes replay. Polling the existing resource GET endpoint also works.

The submission screens open the result on completion, failure, stream error or
ticket failure. Result pages refresh every three seconds while pending or
processing, including after reload or an in-place researcher rerun. Requests
are serial, cancelled on navigation, and stop at terminal status. Temporary
network/server failures retain the last result and show an automatic retry
notice. HTTP 401/403/404 stops retries and asks the user to check access. An
initial page-load failure still offers the existing manual retry control.
Researcher history/graph and source PDF positions refresh on settlement.

Wire events use `event: message` so browser `EventSource.onmessage` receives
them. JSON payloads carry `step` (queued, resolving, complete, error, etc.),
`status`, `detail`, `progress` and `run_id`; replayable rows carry an SSE `id`.
Completed and failed runs can be replayed. A terminal snapshot is also sent when
the supplied cursor is already at the last saved event. HTTP integration tests
exercise ticket issuance, both real stream routes, serialized messages, cursor
replay and invalid-cursor rejection without executing a run.

## Required processes

Run PostgreSQL, Redis, the API, workers and one beat scheduler. For a single
development worker, the existing combined command remains supported:

```sh
celery -A app.tasks.celery_app worker --beat --loglevel=info
```

With multiple workers, run beat separately once. Every ten seconds it submits
`analysis.reconcile_and_dispatch`. The dispatcher publishes committed queued
runs, retries unavailable delivery, and recovers expired running attempts.
Successful publication remains eligible for redelivery after 30 seconds until
claimed. A broker failure defers delivery for 15 seconds. Three expired attempts
exhaust a run. Already committed completed/failed resource results are finalized
without reanalysis. Researcher retries retain the prior revision captured at
submission and rebuild collector artifacts for each attempt.

No worker means queued work stays queued. No beat means recovery and durable
delivery retries stop. Monitor oldest queued age, expired leases, failed runs and
beat availability. Run events are internal progress, not an immutable audit log.

## Upgrade

1. Stop new submissions and drain/stop old API and worker processes, including
   open old SSE handlers. Old code does not honor ownership fencing.
2. Back up the database and apply `alembic upgrade head`.
3. Start the updated API, workers and one beat scheduler together.
4. Submit a controlled text check and confirm terminal status without opening
   its stream. Verify reconnect/replay and the worker/beat logs.

Existing results are preserved. Legacy pending/processing resources without a
run are not silently queued by GET: streaming returns 409 and requires an
explicit rerun. Review stranded legacy jobs during deployment. Do not downgrade
while new processes are writing run records.

Compose now mounts the same named upload/report volumes in API and worker
containers. Those volumes survive container replacement on that Docker host.
Their cross-container/restart behavior has not been exercised locally because
Docker requires unavailable host virtualization. Separate-host deployments such
as Railway must configure the private S3 artifact backend or genuinely shared
filesystem. See [artifact storage](artifact-storage.md) for configuration, legacy
migration and remaining live-provider acceptance tests. Independent per-service
disks do not satisfy this requirement.

## Verification

Default `pytest` runs unit tests. For a dedicated, migrated PostgreSQL test DB:

```sh
ARTIPROOF_INTEGRATION_DATABASE_URL=postgresql+asyncpg://... pytest -m integration tests/test_analysis_runs_integration.py
```

The fixtures create UUID-owned data and clean up only that data. The tests
exercise transaction rollback, concurrent claims, active-run conflicts, stale
write rejection, unavailable broker delivery, terminal-result recovery, ordered
replay, researcher revision persistence, exhausted-attempt cleanup and missing
terminal-event failure handling.

Set `ARTIPROOF_INTEGRATION_REDIS_URL` as well to enable the real Celery/Redis
delivery test. CI supplies PostgreSQL 16 and Redis 7. That test uses a unique
queue and a short local input that fails before calling external providers.
Local evidence covers PostgreSQL plus forcibly killed child workers. For source
checks, death before result commit requeues one replacement and commits one
finding; death after result commit finalizes without recomputing. For researcher
runs, death during collection or after failed-result persistence retains exactly
one original revision and clears stale current metrics. Tests accelerate lease
expiry in the DB and use controlled pipeline data, not real external providers.
These processes call the durable coordinator directly; the real Redis/Celery
delivery test remains skipped locally. Real broker failure/redelivery, full host
restart, real-provider and live object-storage acceptance remain release gates.

Chromium acceptance on 2026-11-01 used the real local Next frontend, API routes,
JWT ownership checks, PostgreSQL and durable coordinator with controlled pipeline
results and suppressed broker publication. Both submissions displayed real SSE
progress. Source completion and researcher failure navigated to their results.
Premature HTTP stream EOF for both kinds opened still-running results, which
then refreshed to completion. Researcher polling recovered after a browser
network outage; an in-place rerun refreshed to failure. A mocked source ticket
503 still opened the real pending result and later displayed failure. Database
audit found six runs, each with one attempt and one terminal event. Mobile
running source/researcher results had no horizontal overflow at 390px.

This was local browser acceptance, not provider or Redis delivery acceptance.
Only fault injection and analysis outputs were controlled; submissions, tickets
(except the explicit 503 case), result reads and progress events used the API.
Screenshots and local harness evidence are under ignored `output/playwright/`.
The six refresh regression tests cover terminal stopping, transient recovery,
access failures, non-overlapping requests and cancellation of stale responses.
