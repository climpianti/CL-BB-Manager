"""Real aiohttp GET/POST lifecycle; all HA state and actuators are in-memory fakes."""
import asyncio
from html.parser import HTMLParser
from types import SimpleNamespace
import time

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

import test_demo_http as base
import test_permanent_http as permanent_fixture
import test_physical_path as physical_fixture

physical = physical_fixture.physical_http
ORIGIN = permanent_fixture.ORIGIN
HOST = permanent_fixture.HOST
# The production handler uses HA's existing app["hass"] contract.
pytestmark = pytest.mark.filterwarnings("ignore:It is recommended to use web.AppKey instances for keys")


class FormParser(HTMLParser):
    def __init__(self, document):
        super().__init__()
        self.nonce = ""
        self.forms = []
        self.links = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") == "form_csrf":
            self.nonce = attrs.get("value", "")
        if tag == "form":
            self.forms.append(attrs)
        if tag == "a":
            self.links.append(attrs)


def setup_gate(monkeypatch, door):
    manager, hass = physical_fixture.setup(monkeypatch)
    gate = manager.data["gates"][0]
    gate["name"] = "Porta " + door.title()
    script = "script.cl_bb_porta_" + door + "_impulso_locale"
    relay = "switch.porta_strada" if door == "strada" else "switch.porta_scale"
    gate["hardware_candidate"]["entity_id"] = script
    hass.states[script] = SimpleNamespace(state="off")
    hass.states[relay] = SimpleNamespace(state="off")
    return manager, hass, gate, script


async def lifecycle(monkeypatch, door, scenario):
    manager, hass, gate, script = setup_gate(monkeypatch, door)
    app = web.Application()
    app["hass"] = hass
    view = physical.PhysicalGuestView()

    async def endpoint(request):
        handler = view.get if request.method == "GET" else view.post
        return await handler(request, request.match_info["token"])

    app.router.add_route("GET", view.url, endpoint)
    app.router.add_route("POST", view.url, endpoint)
    path = "/api/cl_bb_manager/physical/" + physical_fixture.TOKEN
    async with TestClient(TestServer(app)) as client:
        first = await client.get(path, headers={"Host": HOST})
        assert first.status == 200
        document = await first.text()
        parsed = FormParser(document)
        assert len(parsed.nonce) >= 32
        assert parsed.forms[0].get("action", "") == ""
        assert "permanent-demo" not in document
        assert "no-store" in first.headers["Cache-Control"]
        assert not first.cookies  # No HA login/session cookie authorizes this route.

        if scenario == "render_policy":
            assert first.headers["Referrer-Policy"] == "strict-origin"
            assert "<meta name='referrer' content='strict-origin'>" in document
            assert hass.calls == []
            return

        headers = {"Host": HOST, "Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"}
        payload = {"pin": "12345678", "form_csrf": parsed.nonce}
        if scenario == "null_origin":
            headers["Origin"] = "null"
        elif scenario == "foreign_origin":
            headers["Origin"] = "https://untrusted.example.org"
        elif scenario == "same_site":
            headers["Sec-Fetch-Site"] = "same-site"
        elif scenario == "cross_site":
            headers["Sec-Fetch-Site"] = "cross-site"
        elif scenario == "no_origin":
            headers.pop("Origin")
        elif scenario == "missing_csrf":
            payload.pop("form_csrf")
        elif scenario == "expired_csrf":
            manager.physical_forms[parsed.nonce]["expires"] = time.time() - 1
        elif scenario == "restart":
            manager.physical_forms.clear()
        elif scenario == "wrong_gate_csrf":
            manager.physical_forms[parsed.nonce]["gate_id"] = "another-gate"
        elif scenario == "wrong_pin_retry":
            payload["pin"] = "00000000"
        elif scenario == "no_booking_grant":
            manager.data["bookings"][0]["physical_gate_ids"] = []
        elif scenario == "revoked":
            manager.data["bookings"][0]["revoked"] = True
        elif scenario == "cross_property":
            manager.data["bookings"][0]["property_id"] = "00000000-0000-4000-8000-000000000000"
        elif scenario == "disarmed_after_get":
            gate["physical_enabled"] = False

        response = await client.post(path, headers=headers, data=payload)
        text = await response.text()
        assert "12345678" not in text
        assert physical_fixture.TOKEN not in text
        if scenario in ("success", "no_origin"):
            assert response.status == 200
            assert [call[2]["entity_id"] for call in hass.calls] == [script]
            # Replaying the exact HTTP body may not dispatch a second command.
            replay = await client.post(path, headers=headers, data=payload)
            assert replay.status == 403
            assert len(hass.calls) == 1
            assert "Sessione" in await replay.text()
        elif scenario == "disarmed_after_get":
            assert response.status == 404
            assert hass.calls == []
        else:
            assert response.status == 403
            assert hass.calls == []
            error = FormParser(text)
            assert not error.forms  # Never offer a form with an empty/consumed nonce.
            assert any(link.get("href") == "" for link in error.links)
            if scenario == "wrong_pin_retry":
                # The retry link reloads this same physical URL via GET.
                fresh = await client.get(path, headers={"Host": HOST})
                fresh_nonce = FormParser(await fresh.text()).nonce
                assert fresh_nonce and fresh_nonce != parsed.nonce
                payload.update(pin="12345678", form_csrf=fresh_nonce)
                success = await client.post(path, headers=headers, data=payload)
                assert success.status == 200
                assert [call[2]["entity_id"] for call in hass.calls] == [script]


@pytest.mark.parametrize("door", ["strada", "scala"])
@pytest.mark.parametrize("scenario", [
    "render_policy", "success", "no_origin", "null_origin", "foreign_origin",
    "same_site", "cross_site", "missing_csrf", "expired_csrf", "restart",
    "wrong_gate_csrf", "wrong_pin_retry", "no_booking_grant", "revoked",
    "cross_property", "disarmed_after_get",
])
def test_physical_http_lifecycle(monkeypatch, door, scenario):
    asyncio.run(lifecycle(monkeypatch, door, scenario))


@pytest.mark.parametrize("door", ["strada", "scala"])
def test_physical_token_never_enters_virtual_route(monkeypatch, door):
    async def run():
        _, hass, gate, _ = setup_gate(monkeypatch, door)
        request = permanent_fixture.request(hass)
        with pytest.raises(web.HTTPNotFound):
            await permanent_fixture.permanent.PermanentPilotView().get(
                request, physical_fixture.TOKEN,
            )
        # Conversely, a demo token is never accepted by the physical route.
        with pytest.raises(web.HTTPNotFound):
            await physical.PhysicalGuestView().get(request, gate["token"])
        assert hass.calls == []
    asyncio.run(run())


def test_response_never_renders_empty_csrf_form():
    response = base.demo_http._response("Porta Strada", "Riprova", 403, physical=True)
    parsed = FormParser(response.text)
    assert not parsed.forms
    assert any(link.get("href") == "" for link in parsed.links)


def test_security_log_never_contains_request_secrets(monkeypatch, caplog):
    asyncio.run(lifecycle(monkeypatch, "scala", "null_origin"))
    assert "route=physical reason=origin" in caplog.text
    assert "12345678" not in caplog.text
    assert physical_fixture.TOKEN not in caplog.text
