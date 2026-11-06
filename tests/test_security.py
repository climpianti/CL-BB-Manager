"""Tests for persisted guest attempt limits and scoped demo authorization."""
import importlib.util
from pathlib import Path
import sys
import types
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager"
PACKAGE = "cl_bb_test_pkg"

if PACKAGE not in sys.modules:
    pkg = types.ModuleType(PACKAGE)
    pkg.__path__ = [str(ROOT)]
    sys.modules[PACKAGE] = pkg

for module in ("models", "security"):
    full = f"{PACKAGE}.{module}"
    if full not in sys.modules:
        spec = importlib.util.spec_from_file_location(full, ROOT / f"{module}.py")
        obj = importlib.util.module_from_spec(spec)
        sys.modules[full] = obj
        spec.loader.exec_module(obj)

from cl_bb_test_pkg.models import make_booking
from cl_bb_test_pkg.security import (
    charge_attempt, demo_target_allowed, candidate_bookings
)


def test_global_persisted_counter_survives_reuse():
    state = {"all": [], "gates": {}}
    for i in range(12):
        assert charge_attempt(state, "gate1", now=1000.0 + i * 4)
    assert not charge_attempt(state, "gate2", now=1050.0)
    snapshot = {"all": state["all"].copy(), "gates": dict(state["gates"])}
    assert not charge_attempt(snapshot, "gate2", now=1052.0)


def test_gate_limit_without_restricting_another_gate():
    state = {}
    for i in range(5):
        assert charge_attempt(state, "a", now=1000 + i)
    assert not charge_attempt(state, "a", now=1006)
    assert charge_attempt(state, "b", now=1006)


def test_limits_clear_after_window():
    state = {}
    for i in range(5):
        assert charge_attempt(state, "a", now=1000 + i)
    assert charge_attempt(state, "a", now=1100)


def test_invalid_history_fails_closed():
    import pytest

    with pytest.raises(ValueError):
        charge_attempt({"all": ["invalid"], "gates": {}}, "a", now=1000)


def test_demo_target_whitelist():
    scripts = frozenset({"script.demo_a"})
    good = {"enabled": True, "action": "script.turn_on", "entity_id": "script.demo_a"}
    assert demo_target_allowed(good, scripts)
    assert not demo_target_allowed({**good, "entity_id": "lock.front_door"}, scripts)
    assert not demo_target_allowed({**good, "enabled": False}, scripts)
    assert not demo_target_allowed({**good, "action": "lock.unlock"}, scripts)


def test_scoped_booking_expiration_and_revoke():
    now = datetime.now(timezone.utc)
    booking = make_booking(
        "Camera 1", (now - timedelta(hours=1)).isoformat(),
        (now + timedelta(hours=1)).isoformat(), ["camera1"], "12345678"
    )
    assert candidate_bookings([booking], "camera1", now) == [booking]
    assert candidate_bookings([booking], "camera2", now) == []
    assert candidate_bookings([booking], "camera1", now + timedelta(hours=2)) == []
    booking["revoked"] = True
    assert candidate_bookings([booking], "camera1", now) == []
