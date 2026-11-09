"""Tests for the orphan-file cleanup task.

The earlier implementation deleted any file in `uploads/`/`reports/` whose
mtime was older than 24 h, which silently nuked live PDFs. These tests pin
the new contract: files referenced by a `SourceCheck`/`Report` row are
preserved regardless of age; only truly orphaned files are removed.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("naive", [False, True])
async def test_migration_cleanup_hold_preserves_all_orphans(monkeypatch, naive):
    from app.config import settings
    from app.tasks import cleanup

    hold = datetime.now(timezone.utc) + timedelta(hours=1)
    monkeypatch.setattr(settings, "ARTIFACT_CLEANUP_HOLD_UNTIL", hold.replace(tzinfo=None) if naive else hold)
    db = AsyncMock()
    assert await cleanup.remove_orphan_files(db) == 0
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_referenced_files_are_not_deleted(tmp_path, monkeypatch):
    from app.tasks import cleanup

    # Point the cleanup helper at an isolated upload root.
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    monkeypatch.setattr(cleanup, "UPLOAD_DIRS", [upload_root])

    referenced_file = upload_root / "live.pdf"
    referenced_file.write_bytes(b"%PDF-1.4 referenced")

    orphan_file = upload_root / "orphan.pdf"
    orphan_file.write_bytes(b"%PDF-1.4 orphan")

    # Backdate both files so the age guard passes.
    old_mtime = time.time() - (cleanup.ORPHAN_FILE_GRACE_HOURS + 1) * 3600
    os.utime(referenced_file, (old_mtime, old_mtime))
    os.utime(orphan_file, (old_mtime, old_mtime))

    # Stub the DB session: SourceCheck query returns the live file path,
    # Report query returns nothing.
    referenced_path = cleanup._normalize_path(str(referenced_file))

    class _Result:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    db = AsyncMock()
    db.execute.side_effect = [
        _Result([(referenced_path, None)]),  # SourceCheck (orig, annotated)
        _Result([]),                          # Report.pdf_path
    ]

    removed = await cleanup.remove_orphan_files(db)

    assert removed == 1
    assert referenced_file.exists(), "Referenced live PDF should NOT be deleted"
    assert not orphan_file.exists(), "Truly orphan PDF should be removed"


@pytest.mark.asyncio
async def test_recent_orphans_are_preserved(tmp_path, monkeypatch):
    """Files inside the grace window survive even if they're not referenced."""
    from app.tasks import cleanup

    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    monkeypatch.setattr(cleanup, "UPLOAD_DIRS", [upload_root])

    fresh = upload_root / "fresh.pdf"
    fresh.write_bytes(b"%PDF-1.4")
    # Default mtime is now, well within the 24h grace.

    db = AsyncMock()

    class _Result:
        def all(self):
            return []

    db.execute.return_value = _Result()

    removed = await cleanup.remove_orphan_files(db)
    assert removed == 0
    assert fresh.exists()
