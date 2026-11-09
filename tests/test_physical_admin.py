"""Exercise admin-only dormant physical QR controls with fake HA.

No physical script is invoked by this test: provisioning and emergency
disable are storage-only operations. The HTTP kill switch stays False.
"""
from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace

import test_permanent_http as fixture
import test_demo_http as base

from test_physical_path import physical_policy

ws = types.ModuleType("homeassistant.components.websocket_api")
ws.websocket_command = lambda schema: (lambda fn: fn)
ws.async_response = lambda fn: fn
registered = {}
ws.async_register_command = lambda hass, handler: registered.__setitem__(handler.__name__, handler)
sys.modules["homeassistant.components.websocket_api"] = ws
# segno is a runtime dependency but absent from the lightweight model CI.
segno = types.ModuleType("segno")
class FakeQR:
    def save(self, buffer, **kwargs):
        buffer.write(b"<svg/>")
segno.make_qr = lambda url: FakeQR()
sys.modules.setdefault("segno", segno)
# The import is independent from real Home Assistant.
physical_admin = base.load_module("physical_admin")


class Connection:
    def __init__(self):
        self.results = []
        self.errors = []

    def send_result(self, id, result):
        self.results.append((id, result))

    def send_error(self, id, code, description):
        self.errors.append((id, code, description))


def run(coro):
    return asyncio.run(coro)


def setup():
    manager, hass = fixture.fixture()
    gate = manager.data["gates"][0]
    gate["hardware_candidate"] = {
        "entity_id": "script.cl_bb_porta_scala_impulso_locale",
        "action": "script.turn_on",
        "status": "pending_security_review",
    }
    manager.physical_forms = {}
    hass.states["script.cl_bb_porta_scala_impulso_locale"] = SimpleNamespace(state="off")
    hass.states["switch.porta_scale"] = SimpleNamespace(state="off")
    manager.audit = lambda event, detail="": manager.data["events"].append(
        {"event": event, "details": detail}
    )
    registered.clear()
    physical_admin.register_physical_admin_commands(
        hass,
        lambda h, conn, msg, admin_only=False: manager if admin_only else None,
        lambda mgr, conn: None,
        lambda conn, msg, error: conn.send_error(msg["id"], "invalid_request", str(error)),
    )
    return manager, hass


def test_prepare_creates_distinct_dormant_token_then_emergency_revokes():
    async def check():
        manager, hass = setup()
        conn = Connection()
        gate = manager.data["gates"][0]
        original_demo_token = gate["token"]
        cmd = {"id": 1, "gate_id": gate["id"], "confirm": True}
        await registered["prepare_physical_qr"](hass, conn, cmd)
        assert not conn.errors
        result = conn.results[-1][1]
        assert result["armed"] is False
        assert result["release_enabled"] is True
        assert result["url"].endswith(gate["physical_token"])
        assert gate["physical_token"] != original_demo_token
        assert gate["physical_enabled"] is False
        assert physical_policy.PHYSICAL_RELEASE_ENABLED is True
        assert hass.calls == []

        # Stage a narrowly-scoped explicit booking authorization.
        booking = manager.data["bookings"][0]
        await registered["grant_physical_booking"](
            hass, conn, {"id": 2, "booking_id": booking["id"], "gate_id": gate["id"], "confirm": True}
        )
        assert gate["id"] in booking["physical_gate_ids"]
        assert hass.calls == []

        await registered["emergency_disable_physical"](
            hass, conn, {"id": 3, "confirm": True}
        )
        assert conn.results[-1][1]["disabled"] is True
        assert gate.get("physical_token") is None
        assert gate["physical_enabled"] is False
        assert manager.data["physical_access_enabled"] is False
        assert gate["id"] not in booking.get("physical_gate_ids", [])
        assert gate["token"] == original_demo_token
        assert hass.calls == []
    run(check())


def test_repreparing_changes_token_and_does_not_enable_hardware():
    async def check():
        manager, hass = setup()
        conn = Connection()
        gate = manager.data["gates"][0]
        msg = {"id": 1, "gate_id": gate["id"], "confirm": True}
        await registered["prepare_physical_qr"](hass, conn, msg)
        first = gate["physical_token"]
        await registered["prepare_physical_qr"](hass, conn, msg)
        assert gate["physical_token"] != first
        assert not gate["physical_enabled"]
        assert hass.calls == []
    run(check())


def test_offline_shelly_blocks_token_provisioning():
    async def check():
        manager, hass = setup()
        hass.states["switch.porta_scale"].state = "unavailable"
        conn = Connection()
        gate = manager.data["gates"][0]
        await registered["prepare_physical_qr"](
            hass, conn, {"id": 1, "gate_id": gate["id"], "confirm": True}
        )
        assert conn.errors and not conn.results
        assert gate.get("physical_token") is None
        assert hass.calls == []
    run(check())


def test_non_admin_is_denied_before_provisioning():
    async def check():
        manager, hass = setup()
        physical_admin.register_physical_admin_commands(
            hass,
            lambda h, conn, msg, admin_only=False: None,
            lambda mgr, conn: None,
            lambda conn, msg, error: None,
        )
        conn = Connection()
        gate = manager.data["gates"][0]
        await registered["prepare_physical_qr"](
            hass, conn, {"id": 1, "gate_id": gate["id"], "confirm": True}
        )
        assert gate.get("physical_token") is None
        assert hass.calls == []
    run(check())


def test_gate_mapping_invalidation_revokes_physical_grants_only():
    manager, hass = setup()
    gate = manager.data["gates"][0]
    booking = manager.data["bookings"][0]
    gate["physical_token"] = "x" * 48
    gate["physical_enabled"] = True
    booking["physical_gate_ids"] = [gate["id"]]
    physical_admin.invalidate_gate_physical_credentials(manager, gate["id"])
    assert "physical_token" not in gate
    assert gate["physical_enabled"] is False
    assert booking["physical_gate_ids"] == []
    assert booking["gate_ids"] == [gate["id"]]
    assert hass.calls == []


def test_explicit_arm_is_persistent_then_per_gate_disarm_and_emergency():
    async def check():
        manager, hass = setup()
        gate = manager.data["gates"][0]
        booking = manager.data["bookings"][0]
        conn = Connection()
        arm = {"id": 5, "gate_id": gate["id"], "confirm": True}
        # No QR = no arming.
        await registered["arm_physical_gate"](hass, conn, arm)
        assert conn.errors and not conn.results
        conn.errors.clear()
        await registered["prepare_physical_qr"](
            hass, conn, {"id": 1, "gate_id": gate["id"], "confirm": True}
        )
        prepared_token = gate["physical_token"]
        # No explicit booking grant = no arming.
        await registered["arm_physical_gate"](hass, conn, arm)
        assert conn.errors
        conn.errors.clear()
        await registered["grant_physical_booking"](
            hass, conn, {"id": 2, "booking_id": booking["id"], "gate_id": gate["id"], "confirm": True}
        )
        await registered["arm_physical_gate"](hass, conn, arm)
        assert not conn.errors
        assert manager.data["physical_access_enabled"] is True
        assert gate["physical_enabled"] is True
        assert conn.results[-1][1]["persistent"] is True
        assert physical_policy.physical_target(manager, gate, hass, token=prepared_token) == "script.cl_bb_porta_scala_impulso_locale"
        # Disarming does not expire or rotate the printed QR.
        await registered["disarm_physical_gate"](hass, conn, arm)
        assert gate["physical_enabled"] is False
        assert gate["physical_token"] == prepared_token
        assert physical_policy.physical_target(manager, gate, hass, token=prepared_token) is None
        await registered["arm_physical_gate"](hass, conn, arm)
        assert gate["physical_enabled"] is True
        await registered["emergency_disable_physical"](hass, conn, {"id": 9, "confirm": True})
        assert manager.data["physical_access_enabled"] is False
        assert "physical_token" not in gate
        assert booking.get("physical_gate_ids") == []
        assert hass.calls == []
    run(check())


def test_relay_unavailable_prevents_arming():
    async def check():
        manager, hass = setup()
        gate = manager.data["gates"][0]
        booking = manager.data["bookings"][0]
        conn = Connection()
        await registered["prepare_physical_qr"](
            hass, conn, {"id": 1, "gate_id": gate["id"], "confirm": True}
        )
        await registered["grant_physical_booking"](
            hass, conn, {"id": 2, "booking_id": booking["id"], "gate_id": gate["id"], "confirm": True}
        )
        hass.states["switch.porta_scale"].state = "unavailable"
        await registered["arm_physical_gate"](
            hass, conn, {"id": 3, "gate_id": gate["id"], "confirm": True}
        )
        assert conn.errors
        assert gate["physical_enabled"] is False
        assert hass.calls == []
    run(check())
