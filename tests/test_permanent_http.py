"""Exercise persistent virtual QR portal against a mocked HA request lifecycle."""
import asyncio
from types import SimpleNamespace

from aiohttp import web
import pytest

import test_demo_http as base

permanent = base.load_module("permanent_http")
ORIGIN = "https://hotel.example.org"
HOST = "hotel.example.org"
GATE_TOKEN = "persistent-random-gate-label-0123456789"


def fixture():
    manager, hass, _ = base.make_fixture()
    manager.entry = SimpleNamespace(options={
        "permanent_pilot_enabled": True, "public_pilot_origin": ORIGIN,
    })
    manager.permanent_forms = {}
    manager.data["gates"][0]["token"] = GATE_TOKEN
    hass.config = SimpleNamespace(external_url=ORIGIN)
    return manager, hass


def request(hass, *, pin="12345678", origin=ORIGIN, host=HOST):
    r = base.FakeRequest(
        hass, pin=pin, host=host, peer="203.0.113.99", origin=origin,
    )
    r.content_length = 128
    return r


async def form_request(manager, hass, **kwargs):
    r = request(hass, **kwargs)
    response = await permanent.PermanentPilotView().get(r, GATE_TOKEN)
    assert response.status == 200
    r.csrf = next(iter(manager.permanent_forms))
    return r


def test_qr_survives_repeated_visits_and_only_virtual_script_runs():
    async def run():
        manager, hass = fixture()
        view = permanent.PermanentPilotView()
        r1 = await form_request(manager, hass)
        first = await view.post(r1, GATE_TOKEN)
        assert first.status == 200
        assert len(hass.calls) == 1
        assert hass.calls[0][:3] == (
            "script", "turn_on",
            {"entity_id": "script.cl_bb_demo_apri_camera_1"},
        )
        assert manager.data["access_history"][-1]["result"] == "authorized"
        assert manager.data["access_history"][-1]["property_id"] == manager.property_id
        assert (await view.post(r1, GATE_TOKEN)).status == 403
        assert len(hass.calls) == 1
        r2 = await form_request(manager, hass)
        second = await view.post(r2, GATE_TOKEN)
        assert second.status == 200
        assert len(hass.calls) == 2
    asyncio.run(run())


def test_qr_survives_home_assistant_restart_with_fresh_nonce():
    async def run():
        manager, hass = fixture()
        first = await form_request(manager, hass)
        manager.permanent_forms = {}  # Restart invalidates only forms.
        assert (await permanent.PermanentPilotView().post(first, GATE_TOKEN)).status == 403
        assert hass.calls == []
        again = await form_request(manager, hass)
        assert (await permanent.PermanentPilotView().post(again, GATE_TOKEN)).status == 200
    asyncio.run(run())


@pytest.mark.parametrize("mode", ["wrong", "revoked", "expired", "wrong_gate", "cross_property"])
def test_ineligible_booking_never_triggers_virtual_script(mode):
    async def run():
        manager, hass = fixture()
        booking = manager.data["bookings"][0]
        if mode == "revoked":
            booking["revoked"] = True
        elif mode == "expired":
            from datetime import datetime, timedelta, timezone
            booking["end"] = (
                datetime.now(timezone.utc) - timedelta(minutes=1)
            ).isoformat()
        elif mode == "wrong_gate":
            booking["gate_ids"] = ["other-gate"]
        elif mode == "cross_property":
            booking["property_id"] = "00000000-0000-4000-8000-000000000000"
        r = await form_request(manager, hass, pin="00000000" if mode == "wrong" else "12345678")
        response = await permanent.PermanentPilotView().post(r, GATE_TOKEN)
        assert response.status == 403
        assert hass.calls == []
        assert manager.data["access_history"][-1]["booking_id"] == ""
    asyncio.run(run())


def test_wrong_origin_and_disabled_portal_fail_closed():
    async def run():
        manager, hass = fixture()
        view = permanent.PermanentPilotView()
        r = await form_request(manager, hass, origin="https://evil.example.org")
        assert (await view.post(r, GATE_TOKEN)).status == 403
        manager.entry.options["permanent_pilot_enabled"] = False
        with pytest.raises(web.HTTPNotFound):
            await view.get(request(hass), GATE_TOKEN)
        manager.entry.options["permanent_pilot_enabled"] = True
        with pytest.raises(web.HTTPNotFound):
            await view.get(request(hass, host="evil.example.org"), GATE_TOKEN)
        manager.data["gates"][0]["token"] = "rotated-gate-token-98765432109876543210"
        with pytest.raises(web.HTTPNotFound):
            await view.get(request(hass), GATE_TOKEN)
        assert hass.calls == []
    asyncio.run(run())

