import json

import pytest

from app.cli import migrate_artifacts as migration
from app.config import settings


def test_initial_manifest_cannot_clobber_reviewed_plan(tmp_path):
    path = tmp_path / "migration.json"
    migration.save_manifest(path, {"reviewed": "first"}, create=True)
    with pytest.raises(FileExistsError):
        migration.save_manifest(path, {"reviewed": "second"}, create=True)
    assert json.loads(path.read_text()) == {"reviewed": "first"}
    migration.save_manifest(path, {"journal": "updated"})
    assert json.loads(path.read_text()) == {"journal": "updated"}
    assert list(tmp_path.glob(".artifact-migration-*")) == []


def test_manifest_destination_mismatch_fails_before_copy():
    manifest = {"version": 1, "target_config": {}, "source_config": {}, "inventory": [], "groups": []}
    with pytest.raises(ValueError, match="destination configuration mismatch"):
        migration.validate_manifest(manifest, settings)
