"""Gate deletion guard reused by panel and HA options flow."""
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager"
package = ModuleType("_cl_bb_gate_test")
package.__path__ = [str(ROOT)]
sys.modules[package.__name__] = package
for component in ("models", "gate_management"):
    spec = importlib.util.spec_from_file_location(
        package.__name__ + "." + component, ROOT / (component + ".py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

guard = sys.modules[package.__name__ + ".gate_management"].check_gate_removal


def booking(gate_ids, *, revoked=False, days=2):
    return {
        "gate_ids": gate_ids,
        "revoked": revoked,
        "end": (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(),
    }


def test_gate_with_future_active_booking_is_not_removable():
    with pytest.raises(ValueError, match="Revocare"):
        guard("gate-a", [booking(["gate-a", "gate-b"])])


def test_revoked_or_expired_bookings_do_not_block_removal():
    guard("gate-a", [booking(["gate-a"], revoked=True)])
    guard("gate-a", [booking(["gate-a"], days=-1)])
    guard("gate-a", [booking(["gate-b"])])


def test_guard_does_not_mutate_booking_records():
    records = [booking(["gate-a"], revoked=True)]
    before = [dict(records[0])]
    guard("gate-a", records)
    assert records == before


def test_both_admin_entry_points_reuse_the_same_guard():
    api = (ROOT / "api.py").read_text(encoding="utf-8")
    flow = (ROOT / "config_flow.py").read_text(encoding="utf-8")
    assert 'check_gate_removal(gate["id"], manager.data["bookings"])' in api
    assert 'check_gate_removal(gate_id, manager.data["bookings"])' in flow
    assert 'self._gate_id_to_remove = gate_id' in flow
    assert 'user_input.get("confirm") is True' in flow


def test_operator_options_reopen_with_saved_selection():
    source = (ROOT / "config_flow.py").read_text(encoding="utf-8")
    assert 'operator_user_ids(self.config_entry.options)' in source
    assert 'OPTION_OPERATOR_USERS, default=list(previous)' in source
    assert '"current_operators": names' in source
    assert 'OPTION_OPERATOR_USERS: selected' in source


def test_gate_created_disabled_and_options_kept_unchanged():
    source = (ROOT / "config_flow.py").read_text(encoding="utf-8")
    assert 'user_input["action"], user_input["kind"], enabled=False' in source
    assert 'self.hass.states.get(gate["entity_id"]) is None' in source
    assert 'return self.async_create_entry(' in source
    assert 'data=self._unchanged_options()' in source



def test_edit_gate_options_wiring_and_safety_guards():
    source = (ROOT / "config_flow.py").read_text(encoding="utf-8")
    assert '"edit_gate"' in source
    assert "async def async_step_edit_gate" in source
    assert "async def async_step_edit_gate_details" in source
    assert 'check_gate_removal(gate_id, manager.data["bookings"])' in source
    assert 'current["enabled"] = False' in source
    assert 'current["token"] = candidate["token"]' in source
    assert 'manager.demo_sessions.clear()' in source
    assert 'manager.public_demo_sessions.clear()' in source
    assert 'manager.audit("gate_updated", current["name"])' in source
    assert 'self.hass.states.get(candidate["entity_id"]) is None' in source
    assert 'current[key] = candidate[key]' in source


def test_edit_options_preserves_operator_options():
    source = (ROOT / "config_flow.py").read_text(encoding="utf-8")
    assert 'data=self._unchanged_options()' in source
    assert 'OPTION_OPERATOR_USERS, default=list(previous)' in source
    for path in (
        ROOT / "strings.json",
        ROOT / "translations" / "it.json",
    ):
        import json
        options = json.loads(path.read_text(encoding="utf-8"))["options"]["step"]
        assert "edit_gate" in options["gates"]["menu_options"]
        assert "edit_gate_details" in options
        assert "operator_user_ids" in options["access"]["data"]
