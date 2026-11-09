import io
import os
import hashlib
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import boto3
import fitz
import pytest
from botocore.response import StreamingBody
from botocore.stub import ANY, Stubber

from app.services import artifact_storage as store
from app.config import settings


def pdf_bytes():
    with fitz.open() as doc:
        doc.new_page().insert_text((40, 40), "Shared artifact sample")
        return doc.tobytes()


@pytest.fixture
def local(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ARTIFACT_BACKEND", "local")
    monkeypatch.setattr(settings, "ARTIFACT_LOCAL_ROOT", str(tmp_path / "artifacts"))
    return tmp_path


def test_local_reference_survives_new_storage_instance_and_materialization(local):
    content = pdf_bytes()
    reference = store.put_pdf(content, "original")
    assert reference.startswith("artifact://v1/original/")
    assert store.read_pdf(reference) == content
    with store.materialize_pdf(reference) as path:
        assert os.path.exists(path)
        with fitz.open(path) as doc:
            assert "Shared artifact sample" in doc[0].get_text()
    assert not os.path.exists(path)
    store.delete_pdf(reference)
    with pytest.raises(FileNotFoundError):
        store.read_pdf(reference)


def test_separate_worker_process_reads_uploaded_artifact(local):
    content = pdf_bytes()
    reference = store.put_pdf(content, "original")
    environment = {**os.environ, "ARTIFACT_BACKEND": "local", "ARTIFACT_LOCAL_ROOT": settings.ARTIFACT_LOCAL_ROOT}
    child = subprocess.run([sys.executable, "-c",
        "import sys, hashlib; from app.services.artifact_storage import read_pdf; print(hashlib.sha256(read_pdf(sys.argv[1])).hexdigest())",
        reference], cwd=str(store.BACKEND_ROOT), env=environment, capture_output=True, text=True, timeout=20)
    assert child.returncode == 0, child.stderr
    assert child.stdout.strip() == hashlib.sha256(content).hexdigest()


@pytest.mark.parametrize("reference", ["artifact://v1/../secret.pdf", "artifact://other/original/a.pdf", "artifact://v1/report/x.pdf", "artifact://v1/report/" + "a" * 32 + ".pdf/../../secret"])
def test_opaque_reference_cannot_escape_storage(local, reference):
    with pytest.raises(ValueError):
        store.read_pdf(reference)
    with pytest.raises(ValueError):
        store.delete_pdf(reference)


def test_legacy_read_requires_configured_root(local, monkeypatch):
    path = local / "old.pdf"
    path.write_bytes(pdf_bytes())
    with pytest.raises(ValueError):
        store.read_pdf(str(path))
    monkeypatch.setattr(settings, "ARTIFACT_LEGACY_ROOT", str(local))
    assert store.read_pdf(str(path)) == path.read_bytes()


def test_local_atomic_write_failure_exposes_no_final_pdf(local, monkeypatch):
    def fail(*args):
        raise OSError("Disk unavailable")
    monkeypatch.setattr(store.os, "replace", fail)
    with pytest.raises(OSError):
        store.put_pdf(pdf_bytes(), "report")
    assert list((local / "artifacts").rglob("*.pdf")) == []
    assert list((local / "artifacts").rglob(".pending-*")) == []


def test_pdf_extraction_and_annotation_use_shared_artifact(local):
    from app.services.source_verification.pdf_processor import extract_text_with_positions
    from app.services.source_verification.pdf_annotator import create_annotated_pdf
    original = store.put_pdf(pdf_bytes(), "original")
    assert "Shared artifact sample" in extract_text_with_positions(original)["full_text"]
    annotated = create_annotated_pdf(original, {}, [], [], [])
    assert annotated.startswith("artifact://v1/annotated/")
    assert store.read_pdf(annotated).startswith(b"%PDF-")


def test_s3_put_get_delete_use_private_bucket_without_public_acl(monkeypatch):
    monkeypatch.setattr(settings, "ARTIFACT_BACKEND", "s3")
    monkeypatch.setattr(settings, "ARTIFACT_S3_BUCKET", "test-private-artifacts")
    monkeypatch.setattr(settings, "ARTIFACT_S3_PREFIX", "test/v1")
    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test")
    monkeypatch.setattr(store, "_s3", lambda config=None: client)
    content = pdf_bytes()
    with Stubber(client) as stub:
        stub.add_response("put_object", {}, {"Bucket": "test-private-artifacts", "Key": ANY,
            "Body": content, "ContentType": "application/pdf", "CacheControl": "private, no-store"})
        reference = store.put_pdf(content, "report")
        key = "test/v1/" + store._key(reference)
        stub.add_response("get_object", {"Body": StreamingBody(io.BytesIO(content), len(content)), "ContentLength": len(content)},
                          {"Bucket": "test-private-artifacts", "Key": key})
        assert store.read_pdf(reference) == content
        stub.add_response("delete_object", {}, {"Bucket": "test-private-artifacts", "Key": key})
        store.delete_pdf(reference)
        stub.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=404,
                              expected_params={"Bucket": "test-private-artifacts", "Key": key})
        with pytest.raises(FileNotFoundError):
            store.read_pdf(reference)
        stub.assert_no_pending_responses()


def test_old_artifact_inventory_excludes_recent_files(local):
    old = store.put_pdf(pdf_bytes(), "original")
    recent = store.put_pdf(pdf_bytes(), "report")
    path = local / "artifacts" / store._key(old)
    age = datetime.now(timezone.utc) - timedelta(days=2)
    os.utime(path, (age.timestamp(), age.timestamp()))
    candidates = store.old_artifacts(datetime.now(timezone.utc) - timedelta(days=1))
    assert candidates == [old]
    assert recent not in candidates
    assert store.old_artifacts(datetime.now(timezone.utc) - timedelta(days=1), referenced={old}) == []


def test_s3_orphan_listing_passes_referenced_first_page(monkeypatch):
    monkeypatch.setattr(settings, "ARTIFACT_BACKEND", "s3")
    monkeypatch.setattr(settings, "ARTIFACT_S3_BUCKET", "test-private-artifacts")
    monkeypatch.setattr(settings, "ARTIFACT_S3_PREFIX", "test/v1")
    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test")
    monkeypatch.setattr(store, "_s3", lambda config=None: client)
    old = datetime.now(timezone.utc) - timedelta(days=2)
    live_key, orphan_key = "original/" + "a" * 32 + ".pdf", "report/" + "b" * 32 + ".pdf"
    params = {"Bucket": "test-private-artifacts", "Prefix": "test/v1/", "MaxKeys": 1000}
    with Stubber(client) as stub:
        stub.add_response("list_objects_v2", {"IsTruncated": True, "NextContinuationToken": "second",
            "Contents": [{"Key": "test/v1/" + live_key, "LastModified": old}]}, params)
        stub.add_response("list_objects_v2", {"IsTruncated": False,
            "Contents": [{"Key": "test/v1/" + orphan_key, "LastModified": old}]},
            {**params, "ContinuationToken": "second"})
        candidates = store.old_artifacts(datetime.now(timezone.utc) - timedelta(days=1), limit=1,
            referenced={store.REFERENCE_PREFIX + live_key})
        assert candidates == [store.REFERENCE_PREFIX + orphan_key]
        stub.assert_no_pending_responses()


@pytest.mark.asyncio
async def test_authorized_pdf_download_reads_artifact_and_denies_other_users(local):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    from app.routers import source_check as router

    content = pdf_bytes()
    reference = store.put_pdf(content, "original")
    source = SimpleNamespace(id="source", user_id="owner", organization_id=None, original_pdf_path=reference)
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: source)))
    owner = SimpleNamespace(id="owner", role="researcher", tier="free", organization_id=None)
    response = await router.get_original_pdf("source", db, owner)
    assert response.body == content
    assert response.headers["cache-control"] == "private, no-store"
    stranger = SimpleNamespace(id="stranger", role="researcher", tier="free", organization_id=None)
    with pytest.raises(HTTPException) as error:
        await router.get_original_pdf("source", db, stranger)
    assert error.value.status_code == 403
