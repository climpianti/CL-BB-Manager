"""Permanent guest access with per-booking permissions and replay protection."""
from __future__ import annotations

import secrets
from functools import wraps

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import DOMAIN
from .guest_i18n import browser_language, text as guest_text
from .access_history import add_access_event
from .demo_http import _response, _security_rejection
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
            hass.config.external_url or manager.entry.options.get("public_origin")
            or manager.entry.options.get("public_pilot_origin", "")
        )
    except ValueError as exc:
        raise web.HTTPNotFound() from exc
    if request.host.lower() != origin.removeprefix("https://"):
        raise web.HTTPNotFound()
    if manager.entry.options.get("public_access_enabled", True) is not True:
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


def _localized_errors(handler):
    """Localise expected HTTP errors while retaining exception type and status."""
    @wraps(handler)
    async def wrapped(self, request, token):
        try:
            return await handler(self, request, token)
        except (web.HTTPBadRequest, web.HTTPNotFound, web.HTTPServiceUnavailable) as exc:
            language = browser_language(request.headers.get("Accept-Language"))
            key = {400: "bad_request", 404: "not_found", 503: "unavailable"}[exc.status]
            response = _response(guest_text(language, "generic_gate"), status=exc.status,
                                 physical=True, language=language, message_key=key)
            exc.text = response.text
            exc.headers.update(response.headers)
            exc.headers.pop("Content-Length", None)
            raise
    return wrapped


class PhysicalGuestView(HomeAssistantView):
    """Guest endpoint; no HA user credentials are accepted as a booking PIN."""

    url = "/api/cl_bb_manager/physical/{token}"
    name = "api:cl_bb_manager:physical"
    requires_auth = False

    @_localized_errors
    async def get(self, request, token):
        language = browser_language(request.headers.get("Accept-Language"))
        _, manager, _, gate = _context(request, token)
        async with manager.lock:
            if physical_target(manager, gate, manager.hass, token=token) is None:
                raise web.HTTPNotFound()
            try:
                csrf = issue_form(manager.physical_forms, gate["id"])
            except ValueError as exc:
                raise web.HTTPServiceUnavailable() from exc
        return _response(
            gate["name"], message_key="prompt", language=language,
            form_csrf=csrf, physical=True,
        )

    @_localized_errors
    async def post(self, request, token):
        language = browser_language(request.headers.get("Accept-Language"))
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
            return _security_rejection(
                gate["name"], route="physical", reason="origin", physical=True, language=language,
            )

        async with manager.lock:
            # Verify the same gate, token, authorization and script at call time.
            if not consume_form(manager.physical_forms, csrf, gate["id"]):
                return _security_rejection(
                    gate["name"], route="physical", reason="csrf", physical=True, language=language,
                )
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
                return _response(gate["name"], status=429, physical=True, language=language, message_key="too_many")

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
                add_access_event(manager.data, source="https", result="denied", gate=gate)
                await manager.async_save()
                return _response(gate["name"], status=403, physical=True, language=language, message_key="invalid_code")

            if not take_cooldown(manager.data, gate["id"]):
                return _response(gate["name"], status=429, physical=True, language=language, message_key="cooldown")
            # Persist the safety reservation before any potentially uncertain
            # switch operation. No retry on timeout.
            manager.audit("physical_attempt", gate["id"])
            try:
                await manager.async_save()
            except Exception as exc:
                raise web.HTTPServiceUnavailable() from exc
            try:
                def still_authorized():
                    # Native profile reads can take seconds: expiry or a config
                    # reload during those awaits must cancel the opening.
                    return (
                        hass.data.get(DOMAIN, {}).get("manager") is manager
                        and manager.entry.options.get("public_access_enabled", True) is True
                        and approved_booking(matched, gate["id"], manager.property_id)
                        and physical_target(manager, gate, hass, token=token) is not None
                    )
                if "entity_binding" in gate:
                    from .entity_gate import async_command
                    await async_command(manager, gate, before_command=still_authorized)
                elif "shelly_binding" in gate:
                    from .shelly_gate import async_pulse
                    await async_pulse(hass, gate["shelly_binding"], before_command=still_authorized)
                else:
                    if not still_authorized():
                        raise ValueError("Autorizzazione scaduta durante la verifica.")
                    await hass.services.async_call(
                        "script", "turn_on", {"entity_id": script_id}, blocking=True,
                    )
            except Exception as exc:
                manager.audit("physical_service_failed", gate["id"])
                await manager.async_save()
                raise web.HTTPServiceUnavailable() from exc
            manager.audit("physical_command_sent", gate["id"])
            add_access_event(
                manager.data, source="https", result="authorized",
                gate=gate, booking=matched,
            )
            await manager.async_save()
        # HA service completion does not prove that an actual door unlocked.
        return _response(
            gate["name"],
            message_key="success", language=language,
            complete=True, physical=True,
        )

