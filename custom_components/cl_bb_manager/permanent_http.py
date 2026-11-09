"""Optional stable QR guest form, restricted to allowlisted virtual scripts.

Printing a link never grants an access right. A booking PIN, gate scope, time
window, CSRF proof and persisted rate limit are checked on every submission.
"""
from __future__ import annotations

import secrets

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .access_history import add_access_event
from .const import DOMAIN
from .demo_http import _response
from .demo_policy import valid_form_origin
from .guest import DEMO_SCRIPTS
from .models import pin_matches
from .permanent_policy import consume_form, issue_form
from .property_scope import belongs_to_property
from .public_policy import validate_public_origin
from .security import candidate_bookings, charge_attempt, demo_target_allowed


def _context(request, token: str):
    hass = request.app["hass"]
    manager = hass.data.get(DOMAIN, {}).get("manager")
    if manager is None or not manager.entry.options.get("permanent_pilot_enabled", False):
        raise web.HTTPNotFound()
    if not isinstance(token, str) or not 20 <= len(token) <= 100:
        raise web.HTTPNotFound()
    try:
        origin = validate_public_origin(
            hass.config.external_url or manager.entry.options.get("public_pilot_origin", "")
        )
    except ValueError as exc:
        raise web.HTTPNotFound() from exc
    if request.host.lower() != origin.removeprefix("https://"):
        raise web.HTTPNotFound()
    matches = [
        gate for gate in manager.data["gates"]
        if isinstance(gate, dict)
        and isinstance(gate.get("token"), str)
        and secrets.compare_digest(gate["token"], token)
    ]
    if len(matches) != 1:
        raise web.HTTPNotFound()
    gate = matches[0]
    if not belongs_to_property(gate, manager.property_id) or not demo_target_allowed(gate, DEMO_SCRIPTS):
        raise web.HTTPNotFound()
    return hass, manager, origin, gate


class PermanentPilotView(HomeAssistantView):
    """Stable URL, short-lived form nonces, and virtual-only access."""

    url = "/api/cl_bb_manager/permanent-demo/{token}"
    name = "api:cl_bb_manager:permanent_demo"
    requires_auth = False

    async def get(self, request, token):
        _, manager, _, gate = _context(request, token)
        async with manager.lock:
            # Recheck a gate that could have been revoked between lookups.
            current = next(
                (g for g in manager.data["gates"] if g["id"] == gate["id"]), None
            )
            if current is not gate or not demo_target_allowed(current, DEMO_SCRIPTS):
                raise web.HTTPNotFound()
            try:
                csrf = issue_form(manager.permanent_forms, gate["id"])
            except ValueError as exc:
                raise web.HTTPServiceUnavailable() from exc
        return _response(
            gate["name"], "Inserisci il PIN valido della prenotazione. Il QR resta fisso.",
            form_csrf=csrf,
        )

    async def post(self, request, token):
        hass, manager, origin, gate = _context(request, token)
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

        if not valid_form_origin(
            request.headers.get("Origin"),
            request.headers.get("Sec-Fetch-Site"),
            origin,
        ):
            raise web.HTTPForbidden()

        async with manager.lock:
            # A nonce never authorizes a second POST, even after an incorrect PIN.
            if not consume_form(manager.permanent_forms, csrf, gate["id"]):
                raise web.HTTPForbidden()
            current = next(
                (g for g in manager.data["gates"] if g["id"] == gate["id"]), None
            )
            if (
                current is not gate
                or not isinstance(current.get("token"), str)
                or not secrets.compare_digest(current["token"], token)
                or not manager.entry.options.get("permanent_pilot_enabled", False)
                or not belongs_to_property(current, manager.property_id)
                or not demo_target_allowed(current, DEMO_SCRIPTS)
            ):
                raise web.HTTPNotFound()
            throttle = manager.data.setdefault(
                "attempts", {"all": [], "gates": {}}
            )
            try:
                permitted = charge_attempt(throttle, gate["id"])
                await manager.async_save()
            except (TypeError, ValueError) as exc:
                raise web.HTTPServiceUnavailable() from exc
            if not permitted:
                return _response(gate["name"], "Troppi tentativi. Riprova più tardi.", 429)
            matched = None
            if len(pin) == 8 and pin.isascii() and pin.isdecimal():
                try:
                    candidates = candidate_bookings(
                        manager.data["bookings"], gate["id"],
                        property_id=manager.property_id,
                    )
                except ValueError as exc:
                    raise web.HTTPServiceUnavailable() from exc
                for booking in candidates:
                    if await hass.async_add_executor_job(pin_matches, pin, booking):
                        matched = booking
                        break
            if matched is None:
                manager.audit("permanent_pilot_denied", gate["id"])
                add_access_event(
                    manager.data, source="https", result="denied", gate=gate,
                )
                await manager.async_save()
                return _response(
                    gate["name"], "Codice non valido, scaduto o revocato.", 403
                )
            if hass.states.get(gate["entity_id"]) is None:
                raise web.HTTPServiceUnavailable()
            try:
                await hass.services.async_call(
                    "script", "turn_on", {"entity_id": gate["entity_id"]},
                    blocking=True,
                )
            except Exception as exc:
                raise web.HTTPServiceUnavailable() from exc
            manager.audit("permanent_pilot_open", gate["id"])
            add_access_event(
                manager.data, source="https", result="authorized",
                gate=gate, booking=matched,
            )
            await manager.async_save()
        return _response(gate["name"], "Accesso virtuale autorizzato.", complete=True)
