"""Migration backup and rollback tests without Home Assistant."""
import importlib
import sys
import types
from copy import deepcopy
from pathlib import Path

import pytest

package = types.ModuleType("cl_bb_manager_backup_test")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager")]
sys.modules.setdefault(package.__name__, package)
scope = importlib.import_module(package.__name__ + ".property_scope")
backup = importlib.import_module(package.__name__ + ".property_backup")


def test_prepare_migration_and_rollback_preserve_secrets():
    pid = scope.new_property("Covone")["id"]
    original = {"gates": [{"id": "g", "token": "secret"}],
                "bookings": [{"id": "b", "pin_hash": "hash", "pin_salt": "salt"}]}
    before = deepcopy(original)
    snapshot, migrated = backup.prepare_migration(original, pid, "Covone")
    assert original == before
    assert migrated["bookings"][0]["property_id"] == pid
    assert backup.restore_snapshot(snapshot) == before
    migrated["bookings"][0]["pin_hash"] = "changed"
    assert backup.restore_snapshot(snapshot)["bookings"][0]["pin_hash"] == "hash"


def test_tampered_backup_rejected():
    snapshot = backup.make_snapshot({"gates": [{"token": "secret"}]})
    snapshot["data"]["gates"][0]["token"] = "changed"
    with pytest.raises(ValueError):
        backup.restore_snapshot(snapshot)


def test_invalid_archive_and_non_json_data_rejected():
    with pytest.raises(ValueError):
        backup.make_snapshot([])
    with pytest.raises((ValueError, TypeError)):
        backup.make_snapshot({"not_json": {1, 2}})
    with pytest.raises(ValueError):
        backup.restore_snapshot({"format": "wrong", "sha256": "bad", "data": {}})


def test_failed_migration_does_not_mutate_original():
    pid = scope.new_property("Covone")["id"]
    original = {"schema_version": 99, "gates": [{"token": "secret"}]}
    before = deepcopy(original)
    with pytest.raises(ValueError):
        backup.prepare_migration(original, pid, "Covone")
    assert original == before
