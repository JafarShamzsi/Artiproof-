# Private PDF artifact storage

New uploaded, annotated and report PDFs use opaque references such as
`artifact://v1/original/<uuid>.pdf`. API and workers resolve the reference through
the same configured backend. Download routes still perform ownership or share
ticket checks before reading any bytes; bucket URLs and credentials are never
returned to clients.

## Local development and single-host deployments

`ARTIFACT_BACKEND=local` is the default. Files live under `backend/artifacts`, or
the absolute `ARTIFACT_LOCAL_ROOT`. Writes use a temporary file, fsync and atomic
rename. Compose mounts `/app/artifacts` in both API and worker services using
one named volume. All API instances need that same filesystem; independent
per-service volumes cannot share uploaded files.

## Separate-host deployments

Set these consistently on API, worker and cleanup processes:

```text
ARTIFACT_BACKEND=s3
ARTIFACT_S3_BUCKET=<private artifact bucket>
ARTIFACT_S3_REGION=<bucket region>
ARTIFACT_S3_PREFIX=artiproof/artifacts/v1
```

The optional `ARTIFACT_S3_ENDPOINT` supports a trusted S3-compatible endpoint.
Use HTTPS outside isolated local tests. Credentials use the SDK credential
chain: prefer a deployment role scoped to this bucket/prefix. Provision the
bucket separately with public access blocked, encryption and backup/versioning
policies appropriate to the retention requirements. The application does not
create buckets or grant public ACLs. Its role needs PutObject, GetObject,
DeleteObject and ListBucket restricted to this prefix. Never use account-wide
administrator credentials for the application.

PDF reads/writes are capped at 32 MiB and validate the PDF signature. S3 operations
use bounded connection/read timeouts and three total SDK attempts. Routes offload
blocking reads/writes to threads; worker PDF libraries consume stored bytes.
There is no persistent worker-side cache to lose during worker replacement.

## Existing files and migration

Legacy paths inside `backend/uploads` and `backend/reports` remain readable on
instances that can access those files. `ARTIFACT_LEGACY_ROOT` can explicitly allow
one additional trusted legacy root. Arbitrary filesystem paths are rejected.

Changing the backend or prefix does **not** migrate existing artifacts. Run the
migration command from `backend` on a host that can still read the source PDFs.
Back up the database and source files first. Stop API/report writers, workers,
beat/cleanup, drain queued/running analyses, and keep writers stopped until
verification completes. Use a direct PostgreSQL connection for this command;
transaction-pooling proxies do not preserve its session advisory lock.

Configure `ARTIFACT_*` environment variables for the **destination** store.
Source backend/root/bucket/region/prefix/endpoint overrides are supplied on the
planning command; source and destination share the SDK credential chain.
If legacy paths require an additional trusted root, set
`ARTIFACT_LEGACY_ROOT` before planning. A local-to-S3 example:

```sh
python -m app.cli.migrate_artifacts --manifest /secure/path/artifact-migration.json --source-backend local --source-root /old/backend/artifacts
```

This is a dry run: it inventories live and soft-deleted references, reads source
PDFs, hashes them, and writes the manifest. It does not copy PDFs or change DB
references. Existing destination artifacts are skipped when source and target
configuration match. Review the manifest and printed counts before applying.
The manifest includes private paths/bucket metadata; protect it with the backup.
It contains no SDK credentials or PDF content. Keep configuration unchanged
between planning and application.

```sh
python -m app.cli.migrate_artifacts --manifest /secure/path/artifact-migration.json --apply --maintenance-confirmed
```

Apply copies each unique source reference, verifies destination SHA-256, then
journals the copy before transactionally replacing every planned alias. Reruns
sharing an original PDF move together. If the source hash or a DB reference has
changed, the affected reference group is not committed. A dedicated connection
holds a PostgreSQL advisory lock across group commits, excluding another
migrator. The command checks the full reference inventory before marking the
manifest complete; it does not replace the requirement to stop application
writers.

After interruption, rerun the same apply command with the **same manifest**.
Previously verified copies are reused and rechecked. Already updated references
are accepted, while unrelated DB changes cause an explicit conflict. Do not
create a fresh plan partway through migration or start instances against a mixed
source/destination dataset. A failed copy before journaling can leave an orphan
object, handled later by cleanup. Source copies are never deleted by this command.

Before restarting cleanup, set `ARTIFACT_CLEANUP_HOLD_UNTIL` on cleanup/beat
processes to an ISO-8601 UTC timestamp covering the rollback window, or retain
source backups outside all cleanup roots. Until that timestamp, orphan cleanup
returns without listing or deleting files. Afterwards ordinary orphan retention
resumes. Without this hold, old source files become eligible for cleanup as soon
as their DB references have moved. Keep the DB backup, original files and manifest
until acceptance and rollback windows pass. Rolling back requires restoring
the consistent DB/source-store backup together; automatic rollback is not provided.

The database and object store do not share a transaction. A failed submission or
lost worker may leave an unreferenced object. Existing cleanup retains files
referenced by live or recoverable soft-deleted rows. After hard deletion, objects
older than the 24-hour orphan grace period become eligible for removal. S3
listing is paginated and deletion is capped at 1,000 candidates per sweep.
Large inventories still need operational timing/timeout acceptance tests and
retention/versioning policy verification.

## Evidence and remaining gates

Unit tests cover local atomic failure, temporary materialization cleanup,
separate-process reads, PDF extraction/annotation, authorized download, invalid
references, legacy roots, orphan age filtering and S3 request contracts. S3
contract tests use Botocore Stubber, not a live provider.

Migration transaction tests run against real PostgreSQL and isolated local source
and target stores. They cover dry-run immutability, hash verification, alias-group
rollback, resume, active-analysis refusal and concurrent-migrator exclusion. These
checks include an abrupt child-process exit after journaling, followed by resume
with the same copied object and automatic advisory-lock release. They do not
establish live S3 transfer or analysis-worker process-kill recovery.

For a dedicated, already provisioned private S3 test bucket, set
`ARTIPROOF_TEST_S3_BUCKET`, SDK credentials/role, and optionally
`ARTIPROOF_TEST_S3_ENDPOINT`, then run:

```sh
pytest -m integration tests/test_artifact_storage_integration.py
```

That test only writes/deletes its unique `artiproof-integration/<uuid>` prefix.
Actual provider, process restart, multi-instance upload/download and migration
acceptance remain release gates. The official Windows MinIO current and archived
binary URLs returned HTTP 410 during local setup on 2026-11-01; a native object
server was not started and live S3 validation has not been claimed.
