"""Opt-in HTTPS pilot portal: PIN + one-time QR for allowlisted virtual scripts only.

The permanent guest portal remains disabled. Public sessions expire in 10 minutes
and are destroyed on HA restart. Administrator issues each session individually.
"""
from __future__ import annotations

import secrets

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import DOMAIN
from .demo_http import _response
from .demo_policy import valid_form_origin
from .guest import DEMO_SCRIPTS
from .models import pin_matches
from .public_policy import valid_public_session
from .security import charge_attempt, candidate_bookings, demo_target_allowed


def _context(request, token):
    hass = request.app["hass"]
    manager = hass.data.get(DOMAIN, {}).get("manager")
    if manager is None or not manager.entry.options.get("public_pilot_enabled", False):
        raise web.HTTPNotFound()
    session = manager.public_demo_sessions.get(token)
    origin = hass.config.external_url or manager.entry.options.get("public_pilot_origin", "")
    if not valid_public_session(session, request.host, origin):
        raise web.HTTPNotFound()
    gate = next(
        (g for g in manager.data["gates"] if g["id"] == session["gate_id"]),
        None,
    )
    if not gate or not demo_target_allowed(gate, DEMO_SCRIPTS):
        raise web.HTTPNotFound()
    return hass, manager, session, gate


class PublicPilotView(HomeAssistantView):
    """Public HTTPS route which operates *only* approved virtual demo scripts."""

    url = "/api/cl_bb_manager/public-demo/{token}"
    name = "api:cl_bb_manager:public_demo"
    requires_auth = False

    async def get(self, request, token):
        _, _, session, gate = _context(request, token)
        return _response(
            gate["name"], "Prova virtuale. Inserisci il PIN temporaneo.",
            form_csrf=session["form_csrf"],
        )

    async def post(self, request, token):
        hass, manager, session, gate = _context(request, token)
        if (
            request.content_length is None
            or request.content_length > 256
            or request.content_type != "application/x-www-form-urlencoded"
        ):
            raise web.HTTPBadRequest()
        try:
            form = await request.post()
            pin = str(form.get("pin", ""))
            csrf = str(form.get("form_csrf", ""))
        except (ValueError, web.HTTPException) as exc:
            raise web.HTTPBadRequest() from exc

        expected = session.get("form_csrf", "")
        if (
            not isinstance(expected, str)
            or len(expected) < 32
            or not secrets.compare_digest(csrf, expected)
        ):
            return _response(gate["name"], "Sessione non valida. Riapri il QR.", 403)

        if not valid_form_origin(
            request.headers.get("Origin"),
            request.headers.get("Sec-Fetch-Site"),
            session["origin"],
        ):
            return _response(gate["name"], "Origine non autorizzata.", 403)

        async with manager.lock:
            # Check again under the lock (concurrent submissions and revocations).
            if not valid_public_session(
                session, request.host,
                hass.config.external_url or manager.entry.options.get("public_pilot_origin", ""),
            ) or manager.public_demo_sessions.get(token) is not session:
                raise web.HTTPNotFound()
            current = next(
                (g for g in manager.data["gates"] if g["id"] == gate["id"]),
                None,
            )
            if not current or not demo_target_allowed(current, DEMO_SCRIPTS):
                raise web.HTTPNotFound()

            throttle = manager.data.setdefault(
                "attempts", {"all": [], "gates": {}}
            )
            try:
                allowed = charge_attempt(throttle, gate["id"])
                await manager.async_save()
            except (TypeError, ValueError) as exc:
                raise web.HTTPServiceUnavailable() from exc
            if not allowed:
                return _response(gate["name"], "Troppi tentativi.", 429)

            if not (len(pin) == 8 and pin.isascii() and pin.isdecimal()):
                manager.audit("public_pilot_denied", gate["id"])
                await manager.async_save()
                return _response(gate["name"], "PIN non valido o scaduto.", 403)
            try:
                bookings = candidate_bookings(
                    manager.data["bookings"], gate["id"]
                )
            except ValueError as exc:
                raise web.HTTPServiceUnavailable() from exc

            authorized = False
            for booking in bookings:
                if await hass.async_add_executor_job(pin_matches, pin, booking):
                    authorized = True
                    break
            if not authorized:
                manager.audit("public_pilot_denied", gate["id"])
                await manager.async_save()
                return _response(gate["name"], "PIN non valido o scaduto.", 403)

            if hass.states.get(gate["entity_id"]) is None:
                raise web.HTTPServiceUnavailable()
            try:
                await hass.services.async_call(
                    "script", "turn_on", {"entity_id": gate["entity_id"]},
                    blocking=True,
                )
            except Exception as exc:
                raise web.HTTPServiceUnavailable() from exc
            # Single-use after *successful* command: no second opening.
            manager.public_demo_sessions.pop(token, None)
            manager.audit("public_pilot_open", gate["id"])
            await manager.async_save()
        return _response(
            gate["name"], "Apertura virtuale inviata correttamente.",
            complete=True,
        )
