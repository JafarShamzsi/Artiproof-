"""Private PDF artifacts shared by API and workers through stable references.

Blocking storage calls belong in a thread when called from an async route.
New references contain only a validated opaque key, never a public URL or a
client-supplied filesystem path. Legacy paths are read-only compatibility.
"""

import os
import re
import tempfile
import uuid
from contextlib import contextmanager, closing
from pathlib import Path

from app.config import settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_PREFIX = "artifact://v1/"
KEY_PATTERN = re.compile(r"(?:original|annotated|report)/[a-f0-9]{32}\.pdf\Z")
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024


def _key(reference: str) -> str:
    if not reference.startswith(REFERENCE_PREFIX):
        raise ValueError("Not an artifact reference")
    key = reference[len(REFERENCE_PREFIX):]
    if not KEY_PATTERN.fullmatch(key):
        raise ValueError("Invalid artifact reference")
    return key


def _root(config=None) -> Path:
    config = config or settings
    return Path(config.ARTIFACT_LOCAL_ROOT or BACKEND_ROOT / "artifacts").resolve()


def _legacy(reference: str, config=None) -> Path:
    config = config or settings
    path = Path(reference).resolve()
    roots = [BACKEND_ROOT / "uploads", BACKEND_ROOT / "reports"]
    if config.ARTIFACT_LEGACY_ROOT:
        roots.append(Path(config.ARTIFACT_LEGACY_ROOT).resolve())
    if not any(path.is_relative_to(root.resolve()) for root in roots):
        raise ValueError("Legacy artifact path outside configured storage roots")
    return path


def _s3(config=None):
    config = config or settings
    import boto3
    from botocore.config import Config

    if not config.ARTIFACT_S3_BUCKET:
        raise ValueError("ARTIFACT_S3_BUCKET is required")
    return boto3.client("s3", region_name=config.ARTIFACT_S3_REGION,
        endpoint_url=config.ARTIFACT_S3_ENDPOINT or None,
        config=Config(connect_timeout=5, read_timeout=15,
                      retries={"mode": "standard", "total_max_attempts": 3}))


def _object_key(key: str, config=None) -> str:
    config = config or settings
    prefix = config.ARTIFACT_S3_PREFIX.strip("/")
    if prefix and any(segment in {".", "..", ""} for segment in prefix.split("/")):
        raise ValueError("Invalid artifact object prefix")
    return f"{prefix}/{key}" if prefix else key


def put_pdf(content: bytes, category: str, *, config=None) -> str:
    config = config or settings
    if category not in {"original", "annotated", "report"}:
        raise ValueError("Unsupported artifact category")
    if not content.startswith(b"%PDF-") or len(content) > MAX_ARTIFACT_BYTES:
        raise ValueError("Artifact must be a PDF within the size limit")
    key = f"{category}/{uuid.uuid4().hex}.pdf"
    if config.ARTIFACT_BACKEND == "s3":
        with closing(_s3(config)) as client:
            client.put_object(Bucket=config.ARTIFACT_S3_BUCKET, Key=_object_key(key, config),
                Body=content, ContentType="application/pdf", CacheControl="private, no-store")
    elif config.ARTIFACT_BACKEND == "local":
        path = _root(config) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        # A crash never exposes partially written content under the final key.
        handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    else:
        raise ValueError("Unknown artifact backend")
    return REFERENCE_PREFIX + key


def read_pdf(reference: str, *, config=None) -> bytes:
    config = config or settings
    if not reference.startswith(REFERENCE_PREFIX):
        path = _legacy(reference, config)
        with path.open("rb") as stream:
            content = stream.read(MAX_ARTIFACT_BYTES + 1)
    else:
        key = _key(reference)
        if config.ARTIFACT_BACKEND == "s3":
            from botocore.exceptions import ClientError
            with closing(_s3(config)) as client:
                try:
                    result = client.get_object(Bucket=config.ARTIFACT_S3_BUCKET, Key=_object_key(key, config))
                except ClientError as exc:
                    if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
                        raise FileNotFoundError("Artifact not found") from exc
                    raise
                with result["Body"] as stream:
                    if result.get("ContentLength", 0) > MAX_ARTIFACT_BYTES:
                        raise ValueError("Artifact exceeds size limit")
                    content = stream.read(MAX_ARTIFACT_BYTES + 1)
        elif config.ARTIFACT_BACKEND == "local":
            with (_root(config) / key).open("rb") as stream:
                content = stream.read(MAX_ARTIFACT_BYTES + 1)
        else:
            raise ValueError("Unknown artifact backend")
    if len(content) > MAX_ARTIFACT_BYTES or not content.startswith(b"%PDF-"):
        raise ValueError("Invalid stored PDF artifact")
    return content


def delete_pdf(reference: str) -> None:
    if not reference.startswith(REFERENCE_PREFIX):
        _legacy(reference).unlink(missing_ok=True)
        return
    key = _key(reference)
    if settings.ARTIFACT_BACKEND == "s3":
        with closing(_s3()) as client:
            client.delete_object(Bucket=settings.ARTIFACT_S3_BUCKET, Key=_object_key(key))
    elif settings.ARTIFACT_BACKEND == "local":
        (_root() / key).unlink(missing_ok=True)
    else:
        raise ValueError("Unknown artifact backend")


def old_artifacts(before, limit: int = 1000, referenced: set[str] | None = None) -> list[str]:
    """Bounded orphan candidates; caller must check every DB reference first."""
    result = []
    referenced = referenced or set()
    if settings.ARTIFACT_BACKEND == "local":
        root = _root()
        for category in ("original", "annotated", "report"):
            for path in (root / category).glob("*.pdf"):
                key = path.relative_to(root).as_posix()
                if KEY_PATTERN.fullmatch(key) and REFERENCE_PREFIX + key not in referenced and path.stat().st_mtime < before.timestamp():
                    result.append(REFERENCE_PREFIX + key)
                    if len(result) >= limit:
                        return result
    elif settings.ARTIFACT_BACKEND == "s3":
        prefix = settings.ARTIFACT_S3_PREFIX.strip("/")
        prefix = prefix + "/" if prefix else ""
        with closing(_s3()) as client:
            pages = client.get_paginator("list_objects_v2").paginate(
                Bucket=settings.ARTIFACT_S3_BUCKET, Prefix=prefix, PaginationConfig={"PageSize": 1000})
            for page in pages:
                for item in page.get("Contents", []):
                    key = item["Key"][len(prefix):]
                    reference = REFERENCE_PREFIX + key
                    if KEY_PATTERN.fullmatch(key) and reference not in referenced and item["LastModified"] < before:
                        result.append(reference)
                        if len(result) >= limit:
                            return result
    else:
        raise ValueError("Unknown artifact backend")
    return result


@contextmanager
def materialize_pdf(reference: str):
    """Give path-based PDF libraries a private, short-lived local copy."""
    content = read_pdf(reference)
    with tempfile.TemporaryDirectory(prefix="artiproof-pdf-") as directory:
        path = Path(directory) / "document.pdf"
        path.write_bytes(content)
        yield str(path)
