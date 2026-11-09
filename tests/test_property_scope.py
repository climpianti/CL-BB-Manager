"""Property isolation tests, independent from Home Assistant."""
import importlib.util
from pathlib import Path

import pytest

source = Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager/property_scope.py"
spec = importlib.util.spec_from_file_location("cl_bb_property_scope", source)
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)


def test_new_properties_have_distinct_ids():
    a = scope.new_property(" B&B Uno ")
    b = scope.new_property("B&B Due")
    assert a["name"] == "B&B Uno"
    assert a["id"] != b["id"]
    assert scope.require_property_id(a["id"]) == a["id"]


@pytest.mark.parametrize("invalid", [None, "", "default", "00000000-0000-0000-0000-000000000000", 42])
def test_invalid_property_ids_rejected(invalid):
    with pytest.raises(ValueError):
        scope.require_property_id(invalid)


def test_cross_property_gates_and_legacy_records_fail_closed():
    first = scope.new_property("Uno")["id"]
    second = scope.new_property("Due")["id"]
    gates = [
        {"id": "shared", "property_id": first},
        {"id": "private", "property_id": second},
        {"id": "legacy"},
    ]
    scope.assert_gate_scope(gates, ["shared"], first)
    with pytest.raises(ValueError):
        scope.assert_gate_scope(gates, ["private"], first)
    with pytest.raises(ValueError):
        scope.assert_gate_scope(gates, ["legacy"], first)
    assert not scope.belongs_to_property({"id": "legacy"}, first)


def test_duplicate_gate_ids_fail_closed():
    first = scope.new_property("Uno")["id"]
    gates = [{"id": "g", "property_id": first}, {"id": "g", "property_id": first}]
    with pytest.raises(ValueError):
        scope.assert_gate_scope(gates, ["g"], first)
    with pytest.raises(ValueError):
        scope.assert_gate_scope(gates[:1], ["g", "g"], first)
