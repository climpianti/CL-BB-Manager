"""Release-gate regression suite for HTTPS QR access, without touching real locks.

Uses the actual HTTP view code with an isolated Home Assistant fake. Every
service invocation is captured and must target only the virtual allowlist.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from aiohttp import web
import pytest

import test_permanent_http as permanent_test

view_module = permanent_test.permanent
ORIGIN = permanent_test.ORIGIN
TOKEN = permanent_test.GATE_TOKEN


def run(coro):
    return asyncio.run(coro)


def test_real_shelly_candidate_never_called_by_valid_printed_qr():
    async def exercise():
        manager, hass = permanent_test.fixture()
        gate = manager.data["gates"][0]
        gate["hardware_candidate"] = {
            "entity_id": "script.cl_bb_porta_scala_impulso_locale",
            "action": "script.turn_on",
            "status": "pending_security_review",
        }
        hass.states["script.cl_bb_porta_scala_impulso_locale"] = object()
        form = await permanent_test.form_request(manager, hass)
        result = await view_module.PermanentPilotView().post(form, TOKEN)
        assert result.status == 200
        assert [call[2]["entity_id"] for call in hass.calls] == [
            "script.cl_bb_demo_apri_camera_1"
        ]
        assert all("impulso_locale" not in str(call) for call in hass.calls)
    run(exercise())


def test_parallel_form_replay_runs_once_only():
    async def exercise():
        manager, hass = permanent_test.fixture()
        form = await permanent_test.form_request(manager, hass)
        view = view_module.PermanentPilotView()

        async def attempt():
            try:
                return (await view.post(form, TOKEN)).status
            except web.HTTPException as exc:
                return exc.status

        results = await asyncio.gather(attempt(), attempt())
        assert sorted(results) == [200, 403]
        assert len(hass.calls) == 1
    run(exercise())


def test_invalid_pin_consumes_nonce_preventing_later_valid_reuse():
    async def exercise():
        manager, hass = permanent_test.fixture()
        form = await permanent_test.form_request(
            manager, hass, pin="00000000"
        )
        view = view_module.PermanentPilotView()
        denied = await view.post(form, TOKEN)
        assert denied.status == 403
        form.pin = "12345678"
        with pytest.raises(web.HTTPForbidden):
            await view.post(form, TOKEN)
        assert hass.calls == []
    run(exercise())


@pytest.mark.parametrize("bad_origin,fetch_site", [
    ("https://attacker.example.org", "same-origin"),
    ("null", "same-origin"),
    ("http://hotel.example.org", "same-origin"),
    (ORIGIN, "cross-site"),
    (ORIGIN, "same-site"),
])
def test_wrong_origin_or_fetch_metadata_blocks_correct_pin(
    bad_origin, fetch_site
):
    async def exercise():
        manager, hass = permanent_test.fixture()
        form = await permanent_test.form_request(
            manager, hass, origin=bad_origin
        )
        form.headers["Sec-Fetch-Site"] = fetch_site
        with pytest.raises(web.HTTPForbidden):
            await view_module.PermanentPilotView().post(form, TOKEN)
        assert hass.calls == []
    run(exercise())


def test_missing_origin_with_one_time_csrf_works_on_mobile():
    async def exercise():
        manager, hass = permanent_test.fixture()
        form = await permanent_test.form_request(
            manager, hass, origin=False
        )
        form.headers["Sec-Fetch-Site"] = "same-origin"
        result = await view_module.PermanentPilotView().post(form, TOKEN)
        assert result.status == 200
        assert len(hass.calls) == 1
    run(exercise())


def test_csrf_missing_invalid_and_expired_are_all_denied():
    async def exercise():
        manager, hass = permanent_test.fixture()
        view = view_module.PermanentPilotView()
        for invalid in ("", "A" * 43):
            form = await permanent_test.form_request(manager, hass)
            form.csrf = invalid
            with pytest.raises(web.HTTPForbidden):
                await view.post(form, TOKEN)
        form = await permanent_test.form_request(manager, hass)
        manager.permanent_forms[form.csrf]["expires"] = 0
        with pytest.raises(web.HTTPForbidden):
            await view.post(form, TOKEN)
        assert hass.calls == []
    run(exercise())


def test_rate_limit_blocks_valid_pin_after_five_bad_attempts():
    async def exercise():
        manager, hass = permanent_test.fixture()
        view = view_module.PermanentPilotView()
        for _ in range(5):
            form = await permanent_test.form_request(
                manager, hass, pin="00000000"
            )
            assert (await view.post(form, TOKEN)).status == 403
        good_form = await permanent_test.form_request(manager, hass)
        result = await view.post(good_form, TOKEN)
        assert result.status == 429
        assert hass.calls == []
        assert manager.saves >= 6
    run(exercise())


@pytest.mark.parametrize("failure", [
    "revoked", "expired", "not_started", "wrong_gate", "cross_property",
])
def test_booking_unavailable_fails_closed(failure):
    async def exercise():
        manager, hass = permanent_test.fixture()
        booking = manager.data["bookings"][0]
        now = datetime.now(timezone.utc)
        if failure == "revoked":
            booking["revoked"] = True
        elif failure == "expired":
            booking["end"] = (now - timedelta(seconds=1)).isoformat()
        elif failure == "not_started":
            booking["start"] = (now + timedelta(days=1)).isoformat()
            booking["end"] = (now + timedelta(days=2)).isoformat()
        elif failure == "wrong_gate":
            booking["gate_ids"] = ["other-gate"]
        else:
            booking["property_id"] = "00000000-0000-4000-8000-000000000000"
        form = await permanent_test.form_request(manager, hass)
        result = await view_module.PermanentPilotView().post(form, TOKEN)
        assert result.status == 403
        assert hass.calls == []
    run(exercise())


def test_virtual_script_offline_fails_closed_without_real_actuation():
    async def exercise():
        manager, hass = permanent_test.fixture()
        hass.states.pop("script.cl_bb_demo_apri_camera_1")
        form = await permanent_test.form_request(manager, hass)
        with pytest.raises(web.HTTPServiceUnavailable):
            await view_module.PermanentPilotView().post(form, TOKEN)
        assert hass.calls == []
    run(exercise())


def test_explicit_command_exception_never_logs_authorized_access():
    async def exercise():
        manager, hass = permanent_test.fixture()
        async def fail(*args, **kwargs):
            raise RuntimeError("Simulated service failure")
        hass.services.async_call = fail
        form = await permanent_test.form_request(manager, hass)
        with pytest.raises(web.HTTPServiceUnavailable):
            await view_module.PermanentPilotView().post(form, TOKEN)
        assert not any(
            e.get("event") == "permanent_pilot_open"
            for e in manager.data["events"]
        )
        assert not any(
            e.get("result") == "authorized"
            for e in manager.data.get("access_history", [])
        )
    run(exercise())


def test_disabled_virtual_gate_blocks_qr():
    async def exercise():
        manager, hass = permanent_test.fixture()
        manager.data["gates"][0]["enabled"] = False
        with pytest.raises(web.HTTPNotFound):
            await view_module.PermanentPilotView().get(
                permanent_test.request(hass), TOKEN
            )
        assert hass.calls == []
    run(exercise())
