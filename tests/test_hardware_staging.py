"""Safety regression tests for non-executable physical actuator staging."""
from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager"
PKG = "_cl_bb_hw_staging_test"
module = ModuleType(PKG)
module.__path__ = [str(ROOT)]
sys.modules[PKG] = module
staging = importlib.import_module(PKG + ".hardware_staging")
scope = importlib.import_module(PKG + ".property_scope")

PROPERTY_ID = scope.new_property("Test")["id"]
DEMO_SCRIPTS = frozenset({"script.cl_bb_demo_apri_portone"})


def gate():
    return {
        "id": "gate-scala",
        "property_id": PROPERTY_ID,
        "token": "permanent-token-not-modified-123456",
        "entity_id": "script.cl_bb_demo_apri_portone",
        "action": "script.turn_on",
        "enabled": True,
    }


def test_stage_and_clear_do_not_change_qr_token_or_virtual_mapping():
    item = gate()
    original = dict(item)
    candidate = staging.prepare_candidate(
        item, PROPERTY_ID,
        "script.cl_bb_porta_scala_impulso_locale",
        SimpleNamespace(state="off"),
        virtual_script_ids=DEMO_SCRIPTS,
    )
    item[staging.FIELD] = candidate
    assert candidate == {
        "entity_id": "script.cl_bb_porta_scala_impulso_locale",
        "action": "script.turn_on",
        "status": "pending_security_review",
    }
    assert staging.read_candidate(item) == {
        "entity_id": "script.cl_bb_porta_scala_impulso_locale",
        "status": "pending_security_review",
    }
    staging.clear_candidate(item, PROPERTY_ID)
    assert item == original


@pytest.mark.parametrize("script_id,state", [
    ("script.cl_bb_demo_apri_portone", "off"),
    ("script.unknown_hardware", "unavailable"),
    ("switch.porta_scale", "off"),
    ("script.other;switch.turn_on", "off"),
    ("script.other", None),
])
def test_rejects_unsafe_or_unavailable_staging(script_id, state):
    with pytest.raises(ValueError):
        staging.prepare_candidate(
            gate(), PROPERTY_ID, script_id,
            None if state is None else SimpleNamespace(state=state),
            virtual_script_ids=DEMO_SCRIPTS,
        )


def test_cross_property_rejected_and_bad_candidate_redacted():
    item = gate()
    other = scope.new_property("Other")["id"]
    with pytest.raises(ValueError):
        staging.prepare_candidate(
            item, other, "script.safe_real", SimpleNamespace(state="off"),
            virtual_script_ids=DEMO_SCRIPTS,
        )
    item[staging.FIELD] = {"entity_id": "switch.relay", "status": "pending_security_review", "action": "script.turn_on"}
    assert staging.read_candidate(item) is None


def test_non_executable_candidate_is_not_read_by_public_routes():
    portal = (ROOT / "permanent_http.py").read_text(encoding="utf-8")
    api = (ROOT / "api.py").read_text(encoding="utf-8")
    assert "hardware_candidate" not in portal
    assert 'demo_target_allowed(gate, DEMO_SCRIPTS)' in portal
    assert 'demo_target_allowed(current, DEMO_SCRIPTS)' in portal
    assert 'manager.entry.options.get("permanent_pilot_enabled", False)' in portal
    assert 'admin_only=True' in api.split('async def stage_hardware_gate', 1)[1].split('async def clear_hardware_gate',1)[0]
    assert 'admin_only=True' in api.split('async def clear_hardware_gate', 1)[1].split('async def permanent_pilot_qr',1)[0]
    assert 'gate[FIELD] = candidate' in api
    assert "gate[\"entity_id\"] = candidate" not in api
    assert '"hardware_control": "disabled"' in (ROOT / "__init__.py").read_text(encoding="utf-8")
