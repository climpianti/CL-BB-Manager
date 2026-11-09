"""CL B&B Manager guest QR portal, DEMO-only and opt-in.

Requires demo_guest_portal=True in options; alpha 0.3 provides NO options UI.
Do not enable until public endpoint security and proxy tests are complete.
"""
from __future__ import annotations

from html import escape
from io import BytesIO
import secrets

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import DOMAIN
from .access_history import add_access_event
from .models import pin_matches
from .property_scope import belongs_to_property
from .security import charge_attempt, demo_target_allowed, candidate_bookings

# No real actuator entities. These are ONLY the demo script IDs.
DEMO_SCRIPTS = frozenset({
    "script.cl_bb_demo_apri_cancello",
    "script.cl_bb_demo_apri_portone",
    "script.cl_bb_demo_apri_camera_1",
    "script.cl_bb_demo_apri_camera_2",
    "script.cl_bb_demo_apri_camera_3",
})

def manager_of(request):
    return request.app["hass"].data.get(DOMAIN, {}).get("manager")


def find_gate(manager, token):
    if not manager or not manager.entry.options.get("demo_guest_portal", False):
        raise web.HTTPNotFound()
    if len(token) > 100:
        raise web.HTTPNotFound()
    gate = next((g for g in manager.data["gates"]
                 if secrets.compare_digest(str(g["token"]), token)), None)
    if not gate or not belongs_to_property(gate, manager.property_id) or not demo_target_allowed(gate, DEMO_SCRIPTS):
        raise web.HTTPNotFound()
    return gate


def page(name, message, status=200):
    html = (
        "<!doctype html><html lang='it'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex,nofollow'>"
        "<title>CL B&B Access</title><style>"
        "body{font:16px system-ui;background:#edf3fa;color:#18304f;"
        "display:grid;place-items:center;min-height:90vh}"
        "main{background:white;border-radius:18px;padding:30px;width:min(85vw,400px)}"
        "input,button{box-sizing:border-box;width:100%;padding:14px;margin-top:12px}"
        "</style><main><small>CL B&B Access · demo</small>"
        f"<h1>{escape(name)}</h1><p>{escape(message)}</p>"
        "<form method='post'><label>PIN temporaneo"
        "<input name='pin' type='password' inputmode='numeric' "
        "pattern='[0-9]{8}' minlength='8' maxlength='8' required></label>"
        "<button type='submit'>Apri varco demo</button></form></main></html>"
    )
    return web.Response(
        text=html, status=status, content_type="text/html",
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy":
                "default-src 'none'; style-src 'unsafe-inline';"
                " form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
        },
    )


class GuestView(HomeAssistantView):
    url = "/api/cl_bb_manager/guest/{token}"
    name = "api:cl_bb_manager:guest"
    requires_auth = False

    async def get(self, request, token):
        gate = find_gate(manager_of(request), token)
        return page(gate["name"], "Inserisci il PIN della tua prenotazione.")

    async def post(self, request, token):
        manager = manager_of(request)
        gate = find_gate(manager, token)
        # Reject cross-origin requests, including missing/null Origin.
        if request.headers.get("Origin") != f"{request.scheme}://{request.host}":
            raise web.HTTPForbidden()
        if request.content_length is None or request.content_length > 256:
            raise web.HTTPRequestEntityTooLarge(
                max_size=256, actual_size=request.content_length or 0
            )
        try:
            form = await request.post()
        except Exception as exc:
            raise web.HTTPBadRequest() from exc
        pin = str(form.get("pin", ""))
        hass = request.app["hass"]

        # Check all candidate bookings under a lock, then trigger only an
        # allowlisted, existing virtual script. Do not expose arbitrary services.
        async with manager.lock:
            # Persist a failed or successful attempt BEFORE hashing or opening.
            throttle = manager.data.setdefault("attempts", {"all": [], "gates": {}})
            try:
                allowed_attempt = charge_attempt(throttle, gate["id"])
                await manager.async_save()
            except (ValueError, TypeError):
                raise web.HTTPServiceUnavailable()
            if not allowed_attempt:
                return page(gate["name"], "Troppi tentativi. Riprova più tardi.", 429)
            current = next(
                (g for g in manager.data["gates"] if g["id"] == gate["id"]), None
            )
            if (
                not manager.entry.options.get("demo_guest_portal", False)
                or not current
                or not belongs_to_property(current, manager.property_id)
                or not demo_target_allowed(current, DEMO_SCRIPTS)
                or current["entity_id"] != gate["entity_id"]
            ):
                raise web.HTTPForbidden()
            if not (len(pin) == 8 and pin.isascii() and pin.isdecimal()):
                return page(gate["name"], "Codice non valido o scaduto.", 403)
            try:
                candidates = candidate_bookings(manager.data["bookings"], gate["id"], property_id=manager.property_id)
            except ValueError:
                raise web.HTTPServiceUnavailable()
            matched_booking = None
            for booking in candidates:
                if await hass.async_add_executor_job(pin_matches, pin, booking):
                    matched_booking = booking
                    break
            if matched_booking is None:
                manager.audit("guest_denied", gate["id"])
                add_access_event(manager.data, source="legacy", result="denied", gate=gate)
                await manager.async_save()
                return page(gate["name"], "Codice non valido o scaduto.", 403)
            if hass.states.get(gate["entity_id"]) is None:
                raise web.HTTPServiceUnavailable()
            try:
                await hass.services.async_call(
                    "script", "turn_on", {"entity_id": gate["entity_id"]},
                    blocking=True,
                )
            except Exception as exc:
                raise web.HTTPServiceUnavailable() from exc
            manager.audit("guest_demo_open", gate["id"])
            add_access_event(
                manager.data, source="legacy", result="authorized",
                gate=gate, booking=matched_booking,
            )
            await manager.async_save()
        return page(gate["name"], "Apertura simulata inviata.")


class AdminQRView(HomeAssistantView):
    url = "/api/cl_bb_manager/qr/{gate_id}"
    name = "api:cl_bb_manager:qr"
    requires_auth = True

    async def get(self, request, gate_id):
        if not request["hass_user"].is_admin:
            raise web.HTTPForbidden()
        manager = manager_of(request)
        if not manager:
            raise web.HTTPNotFound()
        gate = next((g for g in manager.data["gates"] if g["id"] == gate_id), None)
        if not gate:
            raise web.HTTPNotFound()
        import segno

        url = f"{request.scheme}://{request.host}/api/cl_bb_manager/guest/{gate['token']}"
        buffer = BytesIO()
        segno.make_qr(url).save(buffer, kind="svg", scale=6, border=3)
        return web.Response(
            body=buffer.getvalue(), content_type="image/svg+xml",
            headers={"Cache-Control": "no-store",
                     "X-Content-Type-Options": "nosniff",
                     "Content-Security-Policy": "default-src 'none'"},
        )
