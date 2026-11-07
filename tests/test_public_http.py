"""End-to-end mocked HTTP checks for the opt-in public virtual-only portal."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
import time

from aiohttp import web
import pytest

import test_demo_http as base

policy = base.load_module("public_policy")
public = base.load_module("public_http")
ORIGIN = "https://1wbausanresidency.climpianti.eu"
HOST = "1wbausanresidency.climpianti.eu"


def fixture():
    manager, hass, _ = base.make_fixture()
    manager.entry = SimpleNamespace(options={
        "public_pilot_enabled": True,
        "public_pilot_origin": ORIGIN,
    })
    manager.public_demo_sessions = {}
    hass.config = SimpleNamespace(external_url=ORIGIN)
    token, session = policy.create_public_session("camera-1", ORIGIN)
    manager.public_demo_sessions[token] = session
    return manager, hass, token


def req(hass, manager, pin="12345678", origin=ORIGIN, host=HOST):
    request = base.FakeRequest(
        hass, pin=pin, host=host, peer="203.0.113.99", origin=origin,
    )
    request.csrf = next(iter(manager.public_demo_sessions.values()))["form_csrf"]
    return request


def test_public_portal_one_success_then_token_invalid():
    async def run():
        manager, hass, token = fixture()
        view = public.PublicPilotView()
        request = req(hass, manager)
        first = await view.get(request, token)
        assert first.status == 200
        result = await view.post(request, token)
        assert result.status == 200
        assert "Accesso autorizzato" in result.text
        assert len(hass.calls) == 1
        assert hass.calls[0][0:3] == (
            "script", "turn_on",
            {"entity_id": "script.cl_bb_demo_apri_camera_1"},
        )
        assert token not in manager.public_demo_sessions
        with pytest.raises(web.HTTPNotFound):
            await view.post(request, token)
        assert "12345678" not in str(manager.data["events"])
        record=manager.data["access_history"][-1]
        assert record["source"]=="https"
        assert record["result"]=="authorized"
        assert record["room"]=="Camera 1"
        assert record["booking_id"]==manager.data["bookings"][0]["id"]
        assert "12345678" not in str(record)
    asyncio.run(run())


@pytest.mark.parametrize("mode", [
    "wrong_pin", "bad_origin", "bad_csrf", "revoked",
    "bad_host", "disabled", "expired",
])
def test_denies_unsafe_access(mode):
    async def run():
        manager, hass, token = fixture()
        if mode == "revoked":
            manager.data["bookings"][0]["revoked"] = True
        if mode == "disabled":
            manager.entry.options["public_pilot_enabled"] = False
        if mode == "expired":
            manager.public_demo_sessions[token]["expires"] = time.time() - 1
        request = req(
            hass, manager,
            pin="00000000" if mode == "wrong_pin" else "12345678",
            origin="https://evil.example.org" if mode == "bad_origin" else ORIGIN,
            host="evil.example.org" if mode == "bad_host" else HOST,
        )
        if mode == "bad_csrf":
            request.csrf = "X" * 43
        view = public.PublicPilotView()
        if mode in ("bad_host", "disabled", "expired"):
            with pytest.raises(web.HTTPNotFound):
                await view.post(request, token)
        else:
            response = await view.post(request, token)
            assert response.status == 403
        assert hass.calls == []
    asyncio.run(run())


def test_global_rate_limit_prevents_sixth_try():
    async def run():
        manager, hass, token = fixture()
        view = public.PublicPilotView()
        for _ in range(5):
            result = await view.post(req(hass, manager, pin="00000000"), token)
            assert result.status == 403
        result = await view.post(req(hass, manager, pin="00000000"), token)
        assert result.status == 429
        assert not hass.calls
    asyncio.run(run())
