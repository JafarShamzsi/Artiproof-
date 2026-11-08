"""Opt-in private S3 acceptance; only touches its UUID test prefix."""

import os
import uuid

import pytest

from app.config import settings
from app.services import artifact_storage as store

pytestmark = pytest.mark.integration


def test_separate_clients_retrieve_and_delete_private_pdf(monkeypatch):
    bucket = os.getenv("ARTIPROOF_TEST_S3_BUCKET")
    if not bucket:
        pytest.skip("Set ARTIPROOF_TEST_S3_BUCKET to a dedicated private test bucket")
    monkeypatch.setattr(settings, "ARTIFACT_BACKEND", "s3")
    monkeypatch.setattr(settings, "ARTIFACT_S3_BUCKET", bucket)
    monkeypatch.setattr(settings, "ARTIFACT_S3_ENDPOINT", os.getenv("ARTIPROOF_TEST_S3_ENDPOINT", ""))
    monkeypatch.setattr(settings, "ARTIFACT_S3_PREFIX", "artiproof-integration/" + uuid.uuid4().hex)
    content = b"%PDF-1.7\nIsolated integration storage payload\n%%EOF"
    reference = store.put_pdf(content, "original")
    try:
        # Each operation owns a fresh, closed SDK client; no local file cache.
        assert store.read_pdf(reference) == content
        store.delete_pdf(reference)
        with pytest.raises(FileNotFoundError):
            store.read_pdf(reference)
    finally:
        store.delete_pdf(reference)
