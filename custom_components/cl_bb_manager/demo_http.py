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
from .access_history import add_access_event
from .demo_policy import is_lan_peer, valid_demo_session, valid_form_origin
from .guest import DEMO_SCRIPTS
from .models import pin_matches
from .security import candidate_bookings, charge_attempt, demo_target_allowed


def _response(gate_name: str, message: str = "", status: int = 200, *, form_csrf: str = "", complete: bool = False) -> web.Response:
    """CL Control BlueTech Glass access screen; all dynamic text is HTML-escaped."""
    name = escape(gate_name, quote=True)
    info = escape(message, quote=True)
    if complete:
        form_html = (
            "<div class='result' role='status' aria-live='polite'>"
            "<span class='result-icon' aria-hidden='true'>✓</span>"
            "<strong>Richiesta completata</strong>"
            "<p>Operazione virtuale eseguita correttamente.</p></div>"
        )
    else:
        form_html = (
            "<form method='post' autocomplete='off'>"
            f"<input type='hidden' name='form_csrf' value='{escape(form_csrf, quote=True)}'>"
            "<label for='pin'>Codice di accesso</label>"
            "<input id='pin' name='pin' type='password' inputmode='numeric'"
            " minlength='8' maxlength='8' pattern='[0-9]{8}'"
            " autocomplete='off' placeholder='••••••••' required>"
            "<button type='submit'>Continua <span aria-hidden='true'>→</span></button>"
            "</form>"
        )
    document = (
        "<!doctype html><html lang='it'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex,nofollow'>"
        "<meta name='referrer' content='no-referrer'>"
        "<meta name='theme-color' content='#061324'>"
        "<title>CL Control · Accesso</title>"
        "<style>"
        "*{box-sizing:border-box}"
        ":root{color-scheme:dark;font-family:Inter,'Segoe UI',system-ui,-apple-system,sans-serif}"
        "body{margin:0;min-height:100svh;display:grid;place-items:center;padding:22px 14px;"
        "background:radial-gradient(ellipse at 88% 10%,#15658b70,transparent 46%),"
        "radial-gradient(ellipse at 0% 95%,#124c7470,transparent 55%),"
        "linear-gradient(145deg,#061324,#0a233c 70%,#061324);color:#f4f9ff}"
        ".wrap{width:min(100%,465px)}"
        "main{background:linear-gradient(145deg,#16405fdc,#09233ce8);"
        "border:1px solid #63a8c65c;border-radius:24px;padding:clamp(25px,5vw,39px);"
        "box-shadow:0 22px 65px #0008;backdrop-filter:blur(18px)}"
        ".brand{display:flex;align-items:center;gap:12px;padding-bottom:22px;"
        "border-bottom:1px solid #7aaac53f}"
        ""
        ""
        ""
        ".brand-logo{width:68px;height:61px;display:block;object-fit:contain;flex-shrink:0}"".brand-copy{display:grid;gap:2px}.brand-copy strong{font-size:15px;letter-spacing:.13em}"
        ".brand-copy small{font-size:11px;letter-spacing:.11em;color:#8ad9ff}"
        ".eyebrow{margin:26px 0 8px;font-size:11px;letter-spacing:.13em;"
        "font-weight:750;color:#67cfff;text-transform:uppercase}"
        "h1{font-size:clamp(26px,6vw,34px);letter-spacing:-.04em;"
        "line-height:1.18;margin:0 0 13px;overflow-wrap:anywhere}"
        ".description{color:#c2d9e9;font-size:15px;line-height:1.6;margin:0 0 25px}"
        "form{display:grid;gap:12px}"
        "label{font-size:13px;color:#d9ebf7;font-weight:690}"
        "input{width:100%;height:57px;border:1px solid #5b9dc2;"
        "border-radius:13px;background:#061b30c9;color:#fff;padding:12px 16px;"
        "font-size:23px;font-weight:700;line-height:1.3;font-family:inherit;letter-spacing:.22em;text-align:center}"
        "input::placeholder{color:#729bb4}input:focus-visible,button:focus-visible{outline:2px solid #19baff;outline-offset:3px}"
        "button{border:1px solid #5ed8ff7d;border-radius:13px;"
        "background:linear-gradient(120deg,#1bb5ed,#1379b6);color:white;"
        "font-size:16px;font-weight:700;line-height:1.4;font-family:inherit;padding:16px 20px;cursor:pointer;"
        "display:flex;align-items:center;justify-content:space-between;gap:14px;"
        "box-shadow:0 9px 25px #19baff35}"
        "button:hover{background:linear-gradient(120deg,#36c8fb,#158bca)}"
        ".result{display:grid;justify-items:center;text-align:center;gap:10px;"
        "background:#32e39412;border:1px solid #32e39465;border-radius:17px;padding:24px}"
        ".result-icon{display:grid;place-items:center;width:49px;height:49px;border-radius:50%;"
        "background:#32e39425;color:#70fac0;font-size:29px;font-weight:700}"
        ".result strong{font-size:21px}.result p{margin:0;color:#c8e8da;font-size:14px}"
        ".security{display:flex;gap:10px;align-items:center;margin-top:26px;"
        "padding-top:19px;border-top:1px solid #7aaac53f;color:#9cbcd0;font-size:12px}"
        ".dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#32e394;"
        "box-shadow:0 0 12px #32e39477;flex-shrink:0}"
        ".disclaimer{text-align:center;color:#a0b7c8;font-size:12px;line-height:1.5;"
        "margin:18px 12px 0}"
        "@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}"
        "</style></head><body>"
        "<div class='wrap'><main>"
        "<div class='brand'><img class='brand-logo' src='/cl_bb_manager_static/cl-impianti-logo.svg?v=0.5.0-alpha.4' alt='CL Impianti'><span class='brand-copy'>"
        "<strong>CL CONTROL</strong><small>HOSPITALITY · ACCESSI</small></span></div>"
        "<p class='eyebrow'>Accesso alla struttura</p>"
        f"<h1>{name}</h1><p class='description'>{info}</p>"
        f"{form_html}"
        "<div class='security'><span class='dot' aria-hidden='true'></span>"
        "Codice protetto · Sessione temporanea</div>"
        "</main><p class='disclaimer'>Ambiente pilota: nessuna porta fisica viene comandata.</p>"
        "</div></body></html>"
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
                " img-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
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
            gate["name"], "Inserisci il codice di accesso ricevuto per continuare.",
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
                gate["name"], "Sessione non valida. Apri nuovamente il QR.",
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
                gate["name"], "Richiesta non autorizzata. Apri nuovamente il QR.",
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
                add_access_event(manager.data, source="lan", result="denied", gate=gate)
                await manager.async_save()
                return _response(gate["name"], "Codice non valido o scaduto.", 403, form_csrf=session["form_csrf"])

            try:
                candidates = candidate_bookings(manager.data["bookings"], gate["id"])
            except ValueError as exc:
                raise web.HTTPServiceUnavailable() from exc

            matched_booking = None
            for booking in candidates:
                if await hass.async_add_executor_job(pin_matches, pin, booking):
                    matched_booking = booking
                    break
            if matched_booking is None:
                manager.audit("demo_qr_denied", gate["id"])
                add_access_event(manager.data, source="lan", result="denied", gate=gate)
                await manager.async_save()
                return _response(gate["name"], "Codice non valido o scaduto.", 403, form_csrf=session["form_csrf"])

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
            add_access_event(
                manager.data, source="lan", result="authorized",
                gate=gate, booking=matched_booking,
            )
            await manager.async_save()

        return _response(gate["name"], "Accesso autorizzato.", complete=True)
