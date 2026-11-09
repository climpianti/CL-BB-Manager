"""Isolated physical QR endpoint; hard-disabled in this release.

Unlike the virtual permanent pilot, this path requires an independent token,
an explicit physical grant on the booking, a per-gate hardware enable flag,
and global hardware enablement. No public QR is issued for this route.
"""
from __future__ import annotations

import secrets

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import DOMAIN
from .demo_http import _response
from .models import pin_matches
from .permanent_policy import consume_form, issue_form
from .physical_policy import (
    PHYSICAL_RELEASE_ENABLED, approved_booking, physical_target, take_cooldown,
)
from .public_policy import valid_https_form_origin, validate_public_origin
from .security import candidate_bookings, charge_attempt


def _context(request, token: str):
    if not PHYSICAL_RELEASE_ENABLED:
        raise web.HTTPNotFound()
    hass = request.app["hass"]
    manager = hass.data.get(DOMAIN, {}).get("manager")
    if manager is None:
        raise web.HTTPNotFound()
    try:
        origin = validate_public_origin(
            hass.config.external_url or manager.entry.options.get("public_pilot_origin", "")
        )
    except ValueError as exc:
        raise web.HTTPNotFound() from exc
    if request.host.lower() != origin.removeprefix("https://"):
        raise web.HTTPNotFound()
    if not isinstance(token, str) or not 40 <= len(token) <= 100:
        raise web.HTTPNotFound()
    matches = [
        gate for gate in manager.data["gates"]
        if isinstance(gate, dict)
        and isinstance(gate.get("physical_token"), str)
        and secrets.compare_digest(token, gate["physical_token"])
    ]
    if len(matches) != 1 or physical_target(manager, matches[0], hass, token=token) is None:
        raise web.HTTPNotFound()
    return hass, manager, origin, matches[0]


class PhysicalGuestView(HomeAssistantView):
    """Future physical QR route, unreachable while release kill switch is off."""

    url = "/api/cl_bb_manager/physical/{token}"
    name = "api:cl_bb_manager:physical"
    requires_auth = False

    async def get(self, request, token):
        _, manager, _, gate = _context(request, token)
        async with manager.lock:
            if physical_target(manager, gate, manager.hass, token=token) is None:
                raise web.HTTPNotFound()
            try:
                csrf = issue_form(manager.physical_forms, gate["id"])
            except ValueError as exc:
                raise web.HTTPServiceUnavailable() from exc
        return _response(
            gate["name"], "Inserisci il PIN della prenotazione autorizzata.",
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
        if not valid_https_form_origin(
            request.headers.get("Origin"),
            request.headers.get("Sec-Fetch-Site"), origin,
        ):
            raise web.HTTPForbidden()

        async with manager.lock:
            # Verify the same gate, token, authorization and script at call time.
            if not consume_form(manager.physical_forms, csrf, gate["id"]):
                raise web.HTTPForbidden()
            script_id = physical_target(manager, gate, hass, token=token)
            if script_id is None:
                raise web.HTTPNotFound()

            throttle = manager.data.setdefault("attempts", {"all": [], "gates": {}})
            try:
                permitted = charge_attempt(throttle, gate["id"])
                await manager.async_save()
            except (ValueError, TypeError) as exc:
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
                    if (
                        approved_booking(booking, gate["id"], manager.property_id)
                        and await hass.async_add_executor_job(pin_matches, pin, booking)
                    ):
                        matched = booking
                        break
            if matched is None:
                manager.audit("physical_denied", gate["id"])
                await manager.async_save()
                return _response(gate["name"], "Codice non valido o non autorizzato.", 403)

            if not take_cooldown(manager.data, gate["id"]):
                return _response(gate["name"], "Attendere prima di riprovare.", 429)
            # Persist the safety reservation before any potentially uncertain
            # switch operation. No retry on timeout.
            manager.audit("physical_attempt", gate["id"])
            try:
                await manager.async_save()
            except Exception as exc:
                raise web.HTTPServiceUnavailable() from exc
            try:
                await hass.services.async_call(
                    "script", "turn_on", {"entity_id": script_id}, blocking=True,
                )
            except Exception as exc:
                manager.audit("physical_service_failed", gate["id"])
                await manager.async_save()
                raise web.HTTPServiceUnavailable() from exc
            manager.audit("physical_command_sent", gate["id"])
            await manager.async_save()
        # HA service completion does not prove that an actual door unlocked.
        return _response(
            gate["name"],
            "Comando inviato. Verifica l'apertura della porta.",
            complete=False,
        )
