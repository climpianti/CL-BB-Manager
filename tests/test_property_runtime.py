"""Regression checks for property ownership on new records and access paths.

The application-level assertions verify all active call sites until a full HA
integration harness is available in CI.
"""
from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager"
PKG = "_cl_bb_scope_runtime_test"
pkg = ModuleType(PKG)
pkg.__path__ = [str(ROOT)]
sys.modules.setdefault(PKG, pkg)
scope = importlib.import_module(PKG + ".property_scope")
migration = importlib.import_module(PKG + ".property_migration")
models = importlib.import_module(PKG + ".models")
security = importlib.import_module(PKG + ".security")


def test_schema_v2_repair_handles_unscoped_revoked_booking():
    prop = scope.new_property("Pilot")
    data = {
        "schema_version": 2,
        "properties": [prop],
        "gates": [{"id": "gate", "property_id": prop["id"]}],
        "bookings": [{"id": "revoked", "revoked": True, "gate_ids": ["gate"]}],
        "events": [{"event": "old", "property_id": prop["id"]}],
        "access_history": [],
    }
    upgraded = migration.migrate_legacy_data(data, prop["id"], "Pilot")
    assert data["schema_version"] == 2  # no mutation
    assert upgraded["schema_version"] == 3
    assert upgraded["bookings"][0]["property_id"] == prop["id"]
    assert migration.migrate_legacy_data(upgraded, prop["id"], "Pilot") == upgraded
    assert scope.active_property_id(upgraded) == prop["id"]


def test_migration_rejects_foreign_property_and_bogus_store():
    first, second = scope.new_property("A"), scope.new_property("B")
    with pytest.raises(ValueError):
        migration.migrate_legacy_data({
            "schema_version": 2,
            "properties": [first],
            "gates": [{"id": "x", "property_id": second["id"]}],
        }, first["id"], first["name"])
    for data in (
        {"schema_version": 3, "properties": [first, second]},
        {"schema_version": 3, "properties": []},
        {"schema_version": 2, "properties": [first]},
    ):
        with pytest.raises(ValueError):
            scope.active_property_id(data)


def test_candidate_booking_property_isolation_with_same_gate_id():
    first, second = scope.new_property("A"), scope.new_property("B")
    now = datetime.now(timezone.utc)
    start = (now - timedelta(minutes=5)).isoformat()
    end = (now + timedelta(minutes=5)).isoformat()
    allowed = models.make_booking("Camera", start, end, ["gate"], "12345678")
    foreign = models.make_booking("Camera", start, end, ["gate"], "87654321")
    unscoped = models.make_booking("Camera", start, end, ["gate"], "11112222")
    allowed["property_id"] = first["id"]
    foreign["property_id"] = second["id"]
    assert security.candidate_bookings(
        [allowed, foreign, unscoped], "gate", now, property_id=first["id"],
    ) == [allowed]
    assert security.candidate_bookings(
        [allowed, foreign, unscoped], "gate", now, property_id=second["id"],
    ) == [foreign]


def test_new_record_and_authorization_wiring():
    api = (ROOT / "api.py").read_text(encoding="utf-8")
    flow = (ROOT / "config_flow.py").read_text(encoding="utf-8")
    manager = (ROOT / "__init__.py").read_text(encoding="utf-8")
    demo = (ROOT / "demo_http.py").read_text(encoding="utf-8")
    public = (ROOT / "public_http.py").read_text(encoding="utf-8")
    guest = (ROOT / "guest.py").read_text(encoding="utf-8")
    assert 'gate["property_id"] = manager.property_id' in api
    assert 'booking["property_id"] = property_id' in api
    assert 'assert_gate_scope(manager.data["gates"], booking["gate_ids"], property_id)' in api
    assert 'gate["property_id"] = manager.property_id' in flow
    assert '"property_id": self.property_id' in manager
    assert 'def property_id(self)' in manager
    assert 'require_record_scope(record, property_id)' in manager
    for source in (api, demo, public, guest):
        assert "property_id=manager.property_id" in source
    for source in (demo, public, guest):
        assert "belongs_to_property" in source
