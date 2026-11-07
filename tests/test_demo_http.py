"""Exercise the actual demo HTTP handler against isolated HA/AioHTTP mocks."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import time
import types

import pytest
from aiohttp import web

ROOT = Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager"
PKG = "cl_bb_http_test_pkg"

package = types.ModuleType(PKG)
package.__path__ = [str(ROOT)]
sys.modules[PKG] = package

# A lightweight mock Home Assistant HTTP superclass, not a real HA instance.
ha = types.ModuleType("homeassistant")
components = types.ModuleType("homeassistant.components")
http = types.ModuleType("homeassistant.components.http")
http.HomeAssistantView = type("HomeAssistantView", (), {})
sys.modules.setdefault("homeassistant", ha)
sys.modules.setdefault("homeassistant.components", components)
sys.modules.setdefault("homeassistant.components.http", http)

guest_stub = types.ModuleType(PKG + ".guest")
guest_stub.DEMO_SCRIPTS = frozenset({"script.cl_bb_demo_apri_camera_1"})
sys.modules[PKG + ".guest"] = guest_stub


def load_module(name):
    spec = importlib.util.spec_from_file_location(
        PKG + "." + name, ROOT / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[PKG + "." + name] = module
    spec.loader.exec_module(module)
    return module


const = load_module("const")
models = load_module("models")
policy = load_module("demo_policy")
security = load_module("security")
demo_http = load_module("demo_http")


class DemoManager:
    def __init__(self, booking):
        self.lock = asyncio.Lock()
        self.demo_sessions = {}
        self.data = {
            "gates": [{
                "id": "camera-1",
                "name": "Camera 1",
                "enabled": True,
                "entity_id": "script.cl_bb_demo_apri_camera_1",
                "action": "script.turn_on",
                "kind": "private",
            }],
            "bookings": [booking],
            "events": [],
        }
        self.saves = 0

    async def async_save(self):
        self.saves += 1

    def audit(self, event, detail):
        self.data["events"].append({"event": event, "details": detail})


class FakeHass:
    def __init__(self, manager):
        self.data = {const.DOMAIN: {"manager": manager}}
        self.states = {"script.cl_bb_demo_apri_camera_1": object()}
        self.calls = []
        self.services = self

    async def async_add_executor_job(self, func, *args):
        return await asyncio.to_thread(func, *args)

    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append((domain, service, data, blocking))


class FakeRequest:
    def __init__(self, hass, pin=None, peer="192.168.1.56",
                 host="192.168.1.100:8123", origin=None, csrf_override=None, fetch_site=None):
        self.app = {"hass": hass}
        self.remote = peer
        self.host = host
        self.scheme = "http"
        self.headers = (
            {} if origin is False
            else {"Origin": "http://192.168.1.100:8123" if origin is None else origin}
        )
        if fetch_site is not None:
            self.headers["Sec-Fetch-Site"] = fetch_site
        manager = hass.data[const.DOMAIN]["manager"]
        session = next(iter(manager.demo_sessions.values()))
        self.csrf = session["form_csrf"] if csrf_override is None else csrf_override
        self.content_length = 12
        self.content_type = "application/x-www-form-urlencoded"
        self.pin = pin

    async def post(self):
        return {"pin": self.pin, "form_csrf": self.csrf}


def make_fixture(pin="12345678", gate_ids=None, revoked=False):
    now = datetime.now(timezone.utc)
    booking = models.make_booking(
        "Camera 1",
        (now - timedelta(hours=1)).isoformat(),
        (now + timedelta(hours=2)).isoformat(),
        ["camera-1"] if gate_ids is None else gate_ids,
        pin,
    )
    booking["revoked"] = revoked
    manager = DemoManager(booking)
    token, session = policy.make_demo_session(
        "camera-1", "http://192.168.1.100:8123", now=time.time()
    )
    manager.demo_sessions[token] = session
    hass = FakeHass(manager)
    return manager, hass, token


def test_valid_pin_simulates_only_allowlisted_virtual_script():
    async def run():
        manager, hass, token = make_fixture()
        request = FakeRequest(hass, pin="12345678")
        response = await demo_http.DemoPortalView().get(request, token)
        assert response.status == 200
        assert "Camera 1" in response.text
        result = await demo_http.DemoPortalView().post(request, token)
        assert result.status == 200
        assert "Richiesta completata" in result.text
        assert "name='pin'" not in result.text
        assert len(hass.calls) == 1
        assert hass.calls[0][0:3] == (
            "script", "turn_on",
            {"entity_id": "script.cl_bb_demo_apri_camera_1"}
        )
        assert manager.saves >= 2
        assert "12345678" not in str(manager.data["events"])
    asyncio.run(run())


@pytest.mark.parametrize("mode", ["wrong", "revoked", "expired", "other_gate"])
def test_denies_ineligible_guest_without_opening(mode):
    async def run():
        manager, hass, token = make_fixture(
            revoked=(mode == "revoked"),
            gate_ids=["camera-2"] if mode == "other_gate" else None,
        )
        if mode == "expired":
            manager.data["bookings"][0]["end"] = (
                datetime.now(timezone.utc) - timedelta(hours=1)
            ).isoformat()
        pin = "00000000" if mode == "wrong" else "12345678"
        result = await demo_http.DemoPortalView().post(
            FakeRequest(hass, pin=pin), token
        )
        assert result.status == 403
        assert not hass.calls
    asyncio.run(run())


def test_session_expiration_and_public_peer_are_denied():
    async def run():
        manager, hass, token = make_fixture()
        manager.demo_sessions[token]["expires"] = time.time() - 1
        with pytest.raises(web.HTTPNotFound):
            await demo_http.DemoPortalView().get(FakeRequest(hass), token)
        manager.demo_sessions[token]["expires"] = time.time() + 60
        with pytest.raises(web.HTTPNotFound):
            await demo_http.DemoPortalView().get(
                FakeRequest(hass, peer="8.8.8.8"), token
            )
        with pytest.raises(web.HTTPNotFound):
            await demo_http.DemoPortalView().get(
                FakeRequest(hass, host="example.com"), token
            )
    asyncio.run(run())


def test_wrong_origin_rejected_before_pin_check():
    async def run():
        _, hass, token = make_fixture()
        rejected = await demo_http.DemoPortalView().post(
            FakeRequest(hass, pin="12345678", origin="http://evil.example"), token
        )
        assert rejected.status == 403
        assert "Richiesta non autorizzata" in rejected.text
        assert not hass.calls
    asyncio.run(run())


def test_rate_limit_prevents_sixth_attempt():
    async def run():
        manager, hass, token = make_fixture()
        portal = demo_http.DemoPortalView()
        for _ in range(5):
            result = await portal.post(FakeRequest(hass, pin="00000000"), token)
            assert result.status == 403
        result = await portal.post(FakeRequest(hass, pin="00000000"), token)
        assert result.status == 429
        assert not hass.calls
    asyncio.run(run())

def test_mobile_browser_without_origin_can_submit_form_with_csrf():
    async def run():
        manager, hass, token = make_fixture()
        request = FakeRequest(hass, pin="12345678", origin=False)
        result = await demo_http.DemoPortalView().post(request, token)
        assert result.status == 200
        assert len(hass.calls) == 1
    asyncio.run(run())


def test_originless_form_without_csrf_is_blocked():
    async def run():
        manager, hass, token = make_fixture()
        request = FakeRequest(
            hass, pin="12345678", origin=False, csrf_override="incorrect",
        )
        result = await demo_http.DemoPortalView().post(request, token)
        assert result.status == 403
        assert "Sessione non valida" in result.text
        assert not hass.calls
    asyncio.run(run())


def test_cross_site_origin_with_correct_csrf_is_still_blocked():
    async def run():
        manager, hass, token = make_fixture()
        request = FakeRequest(hass, pin="12345678", origin="https://other.example")
        result = await demo_http.DemoPortalView().post(request, token)
        assert result.status == 403
        assert "Richiesta non autorizzata" in result.text
        assert not hass.calls
    asyncio.run(run())

def test_opaque_android_origin_with_csrf_is_accepted_on_lan():
    async def run():
        _, hass, token = make_fixture()
        result = await demo_http.DemoPortalView().post(
            FakeRequest(
                hass, pin="12345678", origin="null",
                fetch_site="same-origin"
            ), token
        )
        assert result.status == 200
        assert len(hass.calls) == 1
    asyncio.run(run())


def test_reported_origin_mismatch_with_browser_same_origin_and_csrf_is_accepted():
    async def run():
        _, hass, token = make_fixture()
        result = await demo_http.DemoPortalView().post(
            FakeRequest(
                hass, pin="12345678", origin="http://192.168.1.100",
                fetch_site="same-origin"
            ), token
        )
        assert result.status == 200
        assert len(hass.calls) == 1
    asyncio.run(run())


def test_explicit_cross_site_fetch_metadata_blocks_even_with_valid_csrf():
    async def run():
        _, hass, token = make_fixture()
        result = await demo_http.DemoPortalView().post(
            FakeRequest(
                hass, pin="12345678", origin="http://192.168.1.100:8123",
                fetch_site="cross-site"
            ), token
        )
        assert result.status == 403
        assert "Richiesta non autorizzata" in result.text
        assert not hass.calls
    asyncio.run(run())


def test_csrf_is_required_even_for_android_opaque_origin():
    async def run():
        _, hass, token = make_fixture()
        result = await demo_http.DemoPortalView().post(
            FakeRequest(
                hass, pin="12345678", origin="null",
                fetch_site="same-origin", csrf_override="bad-token"
            ), token
        )
        assert result.status == 403
        assert "Sessione non valida" in result.text
        assert not hass.calls
    asyncio.run(run())
