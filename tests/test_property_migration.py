"""Regression coverage for the explicit legacy-store migration."""
import importlib
import sys
import types
from copy import deepcopy
from pathlib import Path

import pytest

# Load pure modules without importing the Home Assistant integration entrypoint.
package = types.ModuleType("cl_bb_manager_migration_test")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager")]
sys.modules.setdefault(package.__name__, package)
scope = importlib.import_module(package.__name__ + ".property_scope")
migration = importlib.import_module(package.__name__ + ".property_migration")


def test_migration_preserves_records_and_does_not_mutate_input():
    pid = scope.new_property("Covone")["id"]
    original = {
        "gates": [{"id": "gate", "token": "secret"}],
        "bookings": [{"id": "booking", "gate_ids": ["gate"], "pin_hash": "hash"}],
        "events": [{"event": "created"}],
        "access_history": [{"gate_id": "gate"}],
        "attempts": {"all": [1.0]},
    }
    before = deepcopy(original)
    result = migration.migrate_legacy_data(original, pid, "Covone")
    assert original == before
    assert result["schema_version"] == 3
    assert result["properties"] == [{"id": pid, "name": "Covone"}]
    for key in migration.RECORD_COLLECTIONS:
        assert all(record["property_id"] == pid for record in result[key])
    assert result["bookings"][0]["pin_hash"] == "hash"
    assert result["gates"][0]["token"] == "secret"
    assert result["attempts"] == before["attempts"]
    assert migration.migrate_legacy_data(result, pid, "Covone") == result


def test_rejects_cross_property_and_unsupported_versions():
    first = scope.new_property("Uno")["id"]
    second = scope.new_property("Due")["id"]
    with pytest.raises(ValueError):
        migration.migrate_legacy_data({"gates": [{"property_id": second}]}, first, "Uno")
    with pytest.raises(ValueError):
        migration.migrate_legacy_data({"schema_version": 999}, first, "Uno")
    with pytest.raises(ValueError):
        migration.migrate_legacy_data({"bookings": [None]}, first, "Uno")
    with pytest.raises(ValueError):
        migration.migrate_legacy_data({"schema_version": True}, first, "Uno")
