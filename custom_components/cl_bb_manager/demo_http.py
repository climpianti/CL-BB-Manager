"""Temporary LAN-only PIN + QR portal for virtual gate demonstrations.

No general guest portal is enabled. This route requires a 32-byte random
temporary session created by an authenticated HA administrator.
"""
from __future__ import annotations

from html import escape
import secrets

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import DOMAIN
from .demo_policy import is_lan_peer, valid_demo_session, valid_form_origin
from .guest import DEMO_SCRIPTS
from .models import pin_matches
from .security import candidate_bookings, charge_attempt, demo_target_allowed


def _response(gate_name: str, message: str = "", status: int = 200, *, form_csrf: str = "", complete: bool = False) -> web.Response:
    name = escape(gate_name, quote=True)
    info = escape(message, quote=True)
    document = (
        "<!doctype html><html lang='it'><head>"
        "<meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex,nofollow'>"
        "<meta name='referrer' content='no-referrer'>"
        "<title>CL B&B · Collaudo</title>"
        "<style>"
        "body{margin:0;font:16px system-ui,sans-serif;background:#edf3fa;"
        "color:#17365a;min-height:100svh;display:grid;place-items:center}"
        "main{background:white;padding:26px;border-radius:20px;"
        "box-shadow:0 12px 30px #17365a20;width:min(86vw,410px)}"
        "h1{font-size:25px;margin:12px 0}"
        "label{display:block;font-weight:600;margin:18px 0 6px}"
        "input,button{box-sizing:border-box;width:100%;border-radius:10px;"
        "font:inherit;padding:14px}"
        "input{border:1px solid #bfd2eb}"
        "button{border:0;background:#1857a5;color:#fff;margin-top:18px}"
        ".tag{color:#527ba9;font-size:13px;font-weight:700;letter-spacing:1px}"
        "</style></head><body><main>"
        "<div class='tag'>CL B&B MANAGER · DEMO LOCALE</div>"
        f"<h1>{name}</h1><p>{info}</p>"
        (
            "<p role='status'>✓ Comando virtuale inviato. Puoi chiudere questa pagina.</p>"
            if complete else (
                "<form method='post' autocomplete='off'>"
                f"<input type='hidden' name='form_csrf' value='{escape(form_csrf, quote=True)}'>"
                "<label for='pin'>PIN della prenotazione</label>"
                "<input id='pin' name='pin' type='password' inputmode='numeric'"
                " minlength='8' maxlength='8' pattern='[0-9]{8}'"
                " autocomplete='off' required>"
                "<button type='submit'>Simula apertura</button></form>"
            )
        )
        "<small>Sessione temporanea. Nessuna porta reale viene comandata.</small>"
        "</main></body></html>"
    )
    return web.Response(
        text=document, content_type="text/html", status=status,
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy":
                "default-src 'none'; style-src 'unsafe-inline';"
                " form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
        },
    )


def _session_and_gate(request, token: str):
    hass = request.app["hass"]
    manager = hass.data.get(DOMAIN, {}).get("manager")
    if manager is None or not is_lan_peer(request.remote):
        raise web.HTTPNotFound()
    session = manager.demo_sessions.get(token)
    if not valid_demo_session(session, request.host, request.remote):
        raise web.HTTPNotFound()
    gate = next(
        (g for g in manager.data["gates"] if g["id"] == session["gate_id"]),
        None,
    )
    if gate is None or not demo_target_allowed(gate, DEMO_SCRIPTS):
        raise web.HTTPNotFound()
    return hass, manager, session, gate


class DemoPortalView(HomeAssistantView):
    """Unauthenticated but short-lived and LAN-only testing route."""

    url = "/api/cl_bb_manager/demo/{token}"
    name = "api:cl_bb_manager:demo"
    requires_auth = False

    async def get(self, request, token):
        _, _, session, gate = _session_and_gate(request, token)
        return _response(
            gate["name"], "Inserisci un PIN valido per provare il varco virtuale.",
            form_csrf=session["form_csrf"],
        )

    async def post(self, request, token):
        hass, manager, session, gate = _session_and_gate(request, token)
        if (
            request.content_length is None
            or request.content_length > 256
            or request.content_type != "application/x-www-form-urlencoded"
        ):
            raise web.HTTPBadRequest()
        try:
            form = await request.post()
            pin = str(form.get("pin", ""))
            supplied_csrf = str(form.get("form_csrf", ""))
        except (ValueError, web.HTTPException) as exc:
            raise web.HTTPBadRequest() from exc

        # Do not trust an Origin-less POST merely because it has the QR token.
        # The form secret must be the one rendered on that session's GET.
        expected_csrf = session.get("form_csrf", "")
        if (
            not isinstance(expected_csrf, str)
            or len(expected_csrf) < 32
            or not secrets.compare_digest(supplied_csrf, expected_csrf)
        ):
            return _response(
                gate["name"], "Sessione del modulo non valida. Riapri il QR.",
                403, form_csrf=expected_csrf if isinstance(expected_csrf, str) else "",
            )

        supplied_origin = request.headers.get("Origin")
        fetch_site = request.headers.get("Sec-Fetch-Site")
        if not valid_form_origin(
            supplied_origin, fetch_site, session["origin"]
        ):
            # Audit only a rejection category, never the PIN, QR URL or token.
            async with manager.lock:
                manager.audit("demo_qr_origin_rejected", gate["id"])
                await manager.async_save()
            return _response(
                gate["name"], "Origine non autorizzata. Riapri il QR sulla LAN.",
                403, form_csrf=session["form_csrf"],
            )

        async with manager.lock:
            # Fail closed if a session expires or the gate is modified while
            # the form is submitted.
            if not valid_demo_session(session, request.host, request.remote):
                raise web.HTTPNotFound()
            current_gate = next(
                (g for g in manager.data["gates"] if g["id"] == gate["id"]),
                None,
            )
            if current_gate is None or not demo_target_allowed(
                current_gate, DEMO_SCRIPTS
            ):
                raise web.HTTPNotFound()

            throttle = manager.data.setdefault("attempts", {"all": [], "gates": {}})
            try:
                allowed = charge_attempt(throttle, gate["id"])
                await manager.async_save()
            except (TypeError, ValueError) as exc:
                raise web.HTTPServiceUnavailable() from exc
            if not allowed:
                return _response(gate["name"], "Troppi tentativi. Riprova più tardi.", 429, form_csrf=session["form_csrf"])

            if not (len(pin) == 8 and pin.isascii() and pin.isdecimal()):
                manager.audit("demo_qr_denied", gate["id"])
                await manager.async_save()
                return _response(gate["name"], "PIN non valido o scaduto.", 403, form_csrf=session["form_csrf"])

            try:
                candidates = candidate_bookings(manager.data["bookings"], gate["id"])
            except ValueError as exc:
                raise web.HTTPServiceUnavailable() from exc

            verified = False
            for booking in candidates:
                if await hass.async_add_executor_job(pin_matches, pin, booking):
                    verified = True
                    break
            if not verified:
                manager.audit("demo_qr_denied", gate["id"])
                await manager.async_save()
                return _response(gate["name"], "PIN non valido o scaduto.", 403, form_csrf=session["form_csrf"])

            if hass.states.get(gate["entity_id"]) is None:
                raise web.HTTPServiceUnavailable()
            try:
                await hass.services.async_call(
                    "script", "turn_on",
                    {"entity_id": gate["entity_id"]},
                    blocking=True,
                )
            except Exception as exc:
                raise web.HTTPServiceUnavailable() from exc
            manager.audit("demo_qr_open", gate["id"])
            await manager.async_save()

        return _response(gate["name"], "Apertura virtuale inviata correttamente.", complete=True)
