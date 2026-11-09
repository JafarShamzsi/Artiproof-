"""Plan/apply/resume artifact migration while application writers are stopped.

No original object is deleted. A durable manifest records each verified copy
before any DB reference changes, making interruption/resume safe.
"""

import argparse
import asyncio
import hashlib
import json
import os
import tempfile
from pathlib import Path

import sqlalchemy as sa

from app.config import settings
from app.models.analysis_run import AnalysisRun
from app.models.report import Report
from app.models.source_check import SourceCheck
from app.services import artifact_storage as storage

FIELDS = {
    "source_check": (SourceCheck, ("original_pdf_path", "annotated_pdf_path")),
    "report": (Report, ("pdf_path",)),
}
CONFIG_FIELDS = (
    "ARTIFACT_BACKEND", "ARTIFACT_LOCAL_ROOT", "ARTIFACT_LEGACY_ROOT",
    "ARTIFACT_S3_BUCKET", "ARTIFACT_S3_REGION", "ARTIFACT_S3_ENDPOINT", "ARTIFACT_S3_PREFIX",
)


def describe(config):
    return {field: getattr(config, field) for field in CONFIG_FIELDS}


def digest(content):
    return hashlib.sha256(content).hexdigest()


def save_manifest(path: Path, manifest: dict, *, create=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".artifact-migration-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(manifest, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if create:
            # Atomic no-clobber publication for the first reviewed plan.
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


async def assert_quiescent(db):
    active = await db.scalar(sa.select(AnalysisRun.id).where(
        AnalysisRun.status.in_(("queued", "running")),
    ).limit(1))
    if active:
        raise RuntimeError("Drain queued/running analysis runs before storage migration")


async def inventory(db):
    records = []
    for kind, (model, fields) in FIELDS.items():
        rows = (await db.execute(sa.select(model.id, *(getattr(model, f) for f in fields))
                                 .order_by(model.id))).all()
        for row in rows:
            for field, reference in zip(fields, row[1:]):
                if reference:
                    records.append({"kind": kind, "id": row[0], "field": field, "reference": reference})
    return records


async def plan(sessions, source_config, target_config):
    async with sessions() as db:
        await assert_quiescent(db)
        records = await inventory(db)
    groups = {}
    same_store = describe(source_config) == describe(target_config)
    for record in records:
        reference = record["reference"]
        if same_store and reference.startswith(storage.REFERENCE_PREFIX):
            continue
        if reference not in groups:
            content = await asyncio.to_thread(storage.read_pdf, reference, config=source_config)
            category = {"original_pdf_path": "original", "annotated_pdf_path": "annotated", "pdf_path": "report"}[record["field"]]
            groups[reference] = {"source": reference, "category": category,
                "sha256": digest(content), "bytes": len(content), "records": [], "target": None}
        groups[reference]["records"].append({k: record[k] for k in ("kind", "id", "field")})
    return {"version": 1, "source_config": describe(source_config), "target_config": describe(target_config),
            "groups": list(groups.values()), "inventory": records, "complete": False}


def validate_manifest(manifest, target_config):
    if manifest.get("version") != 1 or manifest.get("target_config") != describe(target_config):
        raise ValueError("Manifest version or destination configuration mismatch")
    groups = manifest.get("groups")
    if not isinstance(groups, list) or not isinstance(manifest.get("source_config"), dict) or not isinstance(manifest.get("inventory"), list):
        raise ValueError("Invalid migration manifest")
    seen = set()
    for group in groups:
        if group.get("category") not in {"original", "annotated", "report"}:
            raise ValueError("Invalid manifest category")
        checksum = group.get("sha256", "")
        if len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
            raise ValueError("Invalid manifest checksum")
        if not group.get("records"):
            raise ValueError("Manifest group has no references")
        if group.get("target"):
            storage._key(group["target"])
        for record in group["records"]:
            kind, field = record.get("kind"), record.get("field")
            if kind not in FIELDS or field not in FIELDS[kind][1] or not isinstance(record.get("id"), str):
                raise ValueError("Invalid manifest record")
            identity = (kind, record["id"], field)
            if identity in seen:
                raise ValueError("Duplicate manifest record")
            seen.add(identity)


async def apply_manifest(sessions, manifest, path, target_config):
    validate_manifest(manifest, target_config)
    # Dedicated physical connection: business-session commits must not return
    # the advisory-lock connection to a pool or release it under NullPool.
    async with sessions.kw["bind"].connect() as connection:
        locked = await connection.scalar(sa.text("SELECT pg_try_advisory_lock(834910207)"))
        await connection.commit()
        if not locked:
            raise RuntimeError("Another artifact migration is running")
        try:
            await _apply_locked(sessions, manifest, path, target_config)
        finally:
            await connection.execute(sa.text("SELECT pg_advisory_unlock(834910207)"))
            await connection.commit()


async def _apply_locked(sessions, manifest, path, target_config):
    source_config = settings.model_copy(update=manifest["source_config"])
    async with sessions() as db:
        try:
            await assert_quiescent(db)
            for group in manifest["groups"]:
                if not group.get("target"):
                    content = await asyncio.to_thread(storage.read_pdf, group["source"], config=source_config)
                    if digest(content) != group["sha256"] or len(content) != group["bytes"]:
                        raise RuntimeError("Source content changed since migration plan")
                    target = await asyncio.to_thread(storage.put_pdf, content, group["category"], config=target_config)
                    verified = await asyncio.to_thread(storage.read_pdf, target, config=target_config)
                    if digest(verified) != group["sha256"]:
                        raise RuntimeError("Destination verification failed; DB references unchanged")
                    group["target"] = target
                    await asyncio.to_thread(save_manifest, path, manifest)
                else:
                    verified = await asyncio.to_thread(storage.read_pdf, group["target"], config=target_config)
                    if digest(verified) != group["sha256"]:
                        raise RuntimeError("Previously copied destination failed verification")
                # Stable lock ordering, including aliases shared by reruns.
                for record in sorted(group["records"], key=lambda r: (r["kind"], r["id"], r["field"])):
                    model = FIELDS[record["kind"]][0]
                    row = (await db.execute(sa.select(model).where(model.id == record["id"]).with_for_update())).scalar_one_or_none()
                    if row is None or getattr(row, record["field"]) not in {group["source"], group["target"]}:
                        raise RuntimeError("Database reference changed since plan; group rolled back")
                    setattr(row, record["field"], group["target"])
                await db.commit()
            replacements = {group["source"]: group["target"] for group in manifest["groups"]}
            expected = [{**record, "reference": replacements.get(record["reference"], record["reference"])}
                        for record in manifest["inventory"]]
            if await inventory(db) != expected:
                raise RuntimeError("Artifact inventory changed during migration; keep maintenance mode and investigate")
            manifest["complete"] = True
            await asyncio.to_thread(save_manifest, path, manifest)
        except BaseException:
            await db.rollback()
            raise


async def main_async(args):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    path = Path(args.manifest).resolve()
    try:
        if args.apply:
            if not args.maintenance_confirmed:
                raise ValueError("--apply requires --maintenance-confirmed after stopping all writers/cleanup")
            manifest = json.loads(path.read_text(encoding="utf-8"))
            await apply_manifest(sessions, manifest, path, settings)
        else:
            if path.exists():
                raise ValueError("Manifest already exists; resume with --apply or choose a new path")
            source = settings.model_copy(update={"ARTIFACT_BACKEND": args.source_backend,
                "ARTIFACT_LOCAL_ROOT": args.source_root or settings.ARTIFACT_LOCAL_ROOT,
                "ARTIFACT_S3_BUCKET": args.source_bucket or settings.ARTIFACT_S3_BUCKET,
                "ARTIFACT_S3_REGION": args.source_region or settings.ARTIFACT_S3_REGION,
                "ARTIFACT_S3_PREFIX": args.source_prefix if args.source_prefix is not None else settings.ARTIFACT_S3_PREFIX,
                "ARTIFACT_S3_ENDPOINT": args.source_endpoint if args.source_endpoint is not None else settings.ARTIFACT_S3_ENDPOINT})
            manifest = await plan(sessions, source, settings)
            await asyncio.to_thread(save_manifest, path, manifest, create=True)
        print(json.dumps({"groups": len(manifest["groups"]), "references": sum(len(g["records"]) for g in manifest["groups"]),
                          "bytes": sum(g["bytes"] for g in manifest["groups"]), "complete": manifest["complete"]}))
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--maintenance-confirmed", action="store_true")
    parser.add_argument("--source-backend", choices=("local", "s3"), default="local")
    parser.add_argument("--source-root")
    parser.add_argument("--source-bucket")
    parser.add_argument("--source-region")
    parser.add_argument("--source-prefix")
    parser.add_argument("--source-endpoint")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
