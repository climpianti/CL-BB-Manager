"""Regression checks for non-destructive multi-property migration preview."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager/property_migration.py"
spec = importlib.util.spec_from_file_location("cl_bb_property_migration", path)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def test_preview_keeps_legacy_data_and_credentials_unchanged():
    legacy = {
        "gates": [{"id": "g1", "token": "existing-token"}],
        "bookings": [{"id": "b1", "gate_ids": ["g1"], "pin_hash": "hash", "pin_salt": "salt"}],
        "events": [{"event": "booking_added"}],
        "access_history": [],
        "attempts": {"all": [1], "gates": {}},
    }
    original = deepcopy(legacy)
    result = migration.preview_single_property_migration(
        legacy, installation_id="ha-instance-1", structure_name="B&B Demo"
    )
    assert legacy == original
    assert result["schema_version"] == 2
    prop_id = result["properties"][0]["id"]
    assert all(record["property_id"] == prop_id for key in ("gates", "bookings", "events")
               for record in result[key])
    assert result["gates"][0]["token"] == "existing-token"
    assert result["bookings"][0]["pin_hash"] == "hash"
    assert result["attempts"] == original["attempts"]
    assert prop_id == migration.default_property_id("ha-instance-1")
    assert prop_id != migration.default_property_id("ha-instance-2")


@pytest.mark.parametrize("stored", [
    {"gates": "not-a-list"},
    {"bookings": [None]},
    {"schema_version": 3},
    {"gates": [{"property_id": "other-property"}]},
])
def test_preview_rejects_invalid_or_conflicting_stores(stored):
    with pytest.raises(ValueError):
        migration.preview_single_property_migration(
            stored, installation_id="ha-instance-1", structure_name="B&B Demo"
        )


def test_preview_requires_identity_and_name():
    with pytest.raises(ValueError):
        migration.default_property_id("")
    with pytest.raises(ValueError):
        migration.preview_single_property_migration({}, installation_id="ha-1", structure_name=" ")
