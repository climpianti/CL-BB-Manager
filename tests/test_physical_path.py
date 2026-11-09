"""Isolated future hardware QR checks against fake Home Assistant only.

The release kill switch is NEVER enabled in runtime code or deployed tests.
Any hypothetical unlocked-path tests use in-process monkeypatching and mocks.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from aiohttp import web
import pytest

import test_permanent_http as fixture
import test_demo_http as base

physical_policy = base.load_module("physical_policy")
physical_http = base.load_module("physical_http")
TOKEN = "P" * 48
VIRTUAL = "script.cl_bb_demo_apri_camera_1"
REAL = "script.cl_bb_porta_scala_impulso_locale"


def setup(monkeypatch, *, physical_grant=True, online=True):
    manager, hass = fixture.fixture()
    manager.hass = hass
    manager.physical_forms = {}
    gate = manager.data["gates"][0]
    gate["physical_token"] = TOKEN
    gate["physical_enabled"] = True
    gate["hardware_candidate"] = {
        "entity_id": REAL,
        "action": "script.turn_on",
        "status": "pending_security_review",
    }
    manager.data["physical_access_enabled"] = True
    if physical_grant:
        manager.data["bookings"][0]["physical_gate_ids"] = [gate["id"]]
    hass.states[REAL] = SimpleNamespace(state="off")
    hass.states["switch.porta_scale"] = SimpleNamespace(
        state="off" if online else "unavailable"
    )
    monkeypatch.setattr(physical_policy, "PHYSICAL_RELEASE_ENABLED", True)
    monkeypatch.setattr(physical_http, "PHYSICAL_RELEASE_ENABLED", True)
    return manager, hass


async def form(manager, hass, *, pin="12345678", token=TOKEN):
    req = fixture.request(hass, pin=pin)
    response = await physical_http.PhysicalGuestView().get(req, token)
    assert response.status == 200
    req.csrf = next(iter(manager.physical_forms))
    return req


def test_release_is_compile_time_disabled():
    source = (base.ROOT / "physical_policy.py").read_text(encoding="utf-8")
    assert "PHYSICAL_RELEASE_ENABLED = False" in source
    assert physical_policy.PHYSICAL_RELEASE_ENABLED is False
    assert physical_http.PHYSICAL_RELEASE_ENABLED is False


def test_unreleased_endpoint_is_closed_without_touching_shelly():
    async def check():
        manager, hass = fixture.fixture()
        with pytest.raises(web.HTTPNotFound):
            await physical_http.PhysicalGuestView().get(
                fixture.request(hass), TOKEN
            )
        assert hass.calls == []
    asyncio.run(check())


def test_hypothetical_enabled_flow_requires_separate_booking_grant(monkeypatch):
    async def check():
        manager, hass = setup(monkeypatch, physical_grant=False)
        request = await form(manager, hass)
        result = await physical_http.PhysicalGuestView().post(request, TOKEN)
        assert result.status == 403
        assert hass.calls == []
    asyncio.run(check())


def test_hypothetical_authorized_flow_is_once_only_with_cooldown(monkeypatch):
    async def check():
        manager, hass = setup(monkeypatch)
        request = await form(manager, hass)
        result = await physical_http.PhysicalGuestView().post(request, TOKEN)
        assert result.status == 200
        assert "non conferma" in result.text
        assert [call[2]["entity_id"] for call in hass.calls] == [REAL]
        with pytest.raises(web.HTTPForbidden):
            await physical_http.PhysicalGuestView().post(request, TOKEN)
        request2 = await form(manager, hass)
        held = await physical_http.PhysicalGuestView().post(request2, TOKEN)
        assert held.status == 429
        assert len(hass.calls) == 1
    asyncio.run(check())


def test_old_permanent_qr_token_never_acts_as_physical_token(monkeypatch):
    async def check():
        manager, hass = setup(monkeypatch)
        old_token = manager.data["gates"][0]["token"]
        with pytest.raises(web.HTTPNotFound):
            await physical_http.PhysicalGuestView().get(
                fixture.request(hass), old_token
            )
        assert hass.calls == []
    asyncio.run(check())


@pytest.mark.parametrize("failure", ["unavailable", "not_armed", "gate_disabled", "script_replaced"])
def test_hypothetical_hardware_errors_fail_closed(monkeypatch, failure):
    async def check():
        manager, hass = setup(monkeypatch)
        gate = manager.data["gates"][0]
        if failure == "unavailable":
            hass.states[REAL].state = "unavailable"
        elif failure == "not_armed":
            manager.data["physical_access_enabled"] = False
        elif failure == "gate_disabled":
            gate["physical_enabled"] = False
        else:
            gate["hardware_candidate"]["entity_id"] = VIRTUAL
        with pytest.raises(web.HTTPNotFound):
            await physical_http.PhysicalGuestView().get(
                fixture.request(hass), TOKEN
            )
        assert hass.calls == []
    asyncio.run(check())


def test_invalid_physical_pin_never_reaches_real_script(monkeypatch):
    async def check():
        manager, hass = setup(monkeypatch)
        request = await form(manager, hass, pin="00000000")
        result = await physical_http.PhysicalGuestView().post(request, TOKEN)
        assert result.status == 403
        assert hass.calls == []
    asyncio.run(check())


def test_cross_site_request_rejected_before_hardware(monkeypatch):
    async def check():
        manager, hass = setup(monkeypatch)
        request = await form(manager, hass)
        request.headers["Origin"] = "https://evil.example.org"
        with pytest.raises(web.HTTPForbidden):
            await physical_http.PhysicalGuestView().post(request, TOKEN)
        assert hass.calls == []
    asyncio.run(check())


def test_physical_policy_without_monkeypatch_never_reports_real_target():
    manager, hass = fixture.fixture()
    manager.hass = hass
    gate = manager.data["gates"][0]
    gate["physical_enabled"] = True
    gate["physical_token"] = TOKEN
    gate["hardware_candidate"] = {
        "entity_id": REAL, "status": "pending_security_review",
        "action": "script.turn_on",
    }
    manager.data["physical_access_enabled"] = True
    hass.states[REAL] = SimpleNamespace(state="off")
    hass.states["switch.porta_scale"] = SimpleNamespace(state="off")
    assert physical_policy.physical_target(manager, gate, hass, token=TOKEN) is None


def test_unknown_real_script_is_not_approved_even_if_available(monkeypatch):
    manager, hass = setup(monkeypatch)
    candidate = manager.data["gates"][0]["hardware_candidate"]
    candidate["entity_id"] = "script.unknown_open_door"
    hass.states["script.unknown_open_door"] = SimpleNamespace(state="off")
    assert physical_policy.physical_target(
        manager, manager.data["gates"][0], hass, token=TOKEN
    ) is None


def test_expected_shelly_relay_must_be_off_and_present(monkeypatch):
    manager, hass = setup(monkeypatch)
    gate = manager.data["gates"][0]
    assert physical_policy.physical_target(manager, gate, hass, token=TOKEN) == REAL
    for bad_state in ("unavailable", "unknown", "on"):
        hass.states["switch.porta_scale"].state = bad_state
        assert physical_policy.physical_target(manager, gate, hass, token=TOKEN) is None
    hass.states.pop("switch.porta_scale")
    assert physical_policy.physical_target(manager, gate, hass, token=TOKEN) is None


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), True])
def test_cooldown_rejects_invalid_clock(bad):
    data = {}
    assert physical_policy.take_cooldown(data, "gate", now=bad) is False


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), True])
def test_cooldown_rejects_corrupt_saved_timestamp(bad):
    data = {"physical_last_action": {"gate": bad}}
    assert physical_policy.take_cooldown(data, "gate", now=5000) is False
