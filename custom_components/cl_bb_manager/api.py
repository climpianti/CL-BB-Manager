"""Role-aware websocket API for CL B&B Manager.

The API intentionally contains NO service calls for opening gates in this alpha.
"""
from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components import websocket_api
import voluptuous as vol

from .const import DOMAIN, MAX_BOOKINGS, MAX_GATES
from .models import as_utc, generate_pin, make_booking, make_gate, pin_matches
from .gate_management import check_gate_removal
from .permissions import user_role
from .security import charge_attempt, demo_target_allowed, candidate_bookings


def _manager(hass):
    return hass.data.get(DOMAIN, {}).get("manager")


def _authorize(hass, connection, msg, *, admin_only=False):
    manager = _manager(hass)
    if manager is None:
        connection.send_error(msg["id"], "not_ready", "Gestore non configurato.")
        return None
    role = user_role(connection.user, manager.entry.options)
    if role is None or (admin_only and role != "admin"):
        connection.send_error(msg["id"], "unauthorized", "Utente non autorizzato.")
        return None
    return manager


def _summary(manager, connection):
    """Return a scoped snapshot based on the authenticated user, not client data."""
    return manager.summary(role=user_role(connection.user, manager.entry.options))


def _error(connection, msg, reason):
    connection.send_error(msg["id"], "invalid_request", str(reason))


def _validate_mapping(hass, data):
    gate = make_gate(
        data["name"], data["entity_id"], data["action"],
        data["kind"], enabled=bool(data.get("enabled", False))
    )
    if hass.states.get(gate["entity_id"]) is None:
        raise ValueError("Entità Home Assistant non trovata.")
    return gate


def register_commands(hass):
    """Register commands once per Home Assistant process."""

    @websocket_api.websocket_command({"type": "cl_bb_manager/list"})
    @websocket_api.async_response
    async def get_list(hass, connection, msg):
        manager = _authorize(hass, connection, msg)
        if manager is not None:
            connection.send_result(msg["id"], _summary(manager, connection))

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/add_gate",
        vol.Required("name"): str,
        vol.Required("entity_id"): str,
        vol.Required("action"): vol.In(["script.turn_on", "button.press", "lock.unlock"]),
        vol.Required("kind"): vol.In(["shared", "private"]),
    })
    @websocket_api.async_response
    async def add_gate(hass, connection, msg):
        manager = _authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        try:
            gate = _validate_mapping(hass, msg)
            async with manager.lock:
                if len(manager.data["gates"]) >= MAX_GATES:
                    raise ValueError("Limite massimo di varchi raggiunto.")
                if any(g["entity_id"] == gate["entity_id"]
                       for g in manager.data["gates"]):
                    raise ValueError("Questa entità è già associata a un varco.")
                manager.data["gates"].append(gate)
                manager.audit("gate_added", gate["name"])
                await manager.async_save()
        except ValueError as err:
            _error(connection, msg, err)
            return
        connection.send_result(msg["id"], _summary(manager, connection))

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/update_gate",
        vol.Required("gate_id"): str,
        vol.Required("name"): str,
        vol.Required("entity_id"): str,
        vol.Required("action"): vol.In(["script.turn_on", "button.press", "lock.unlock"]),
        vol.Required("kind"): vol.In(["shared", "private"]),
        vol.Required("enabled"): bool,
    })
    @websocket_api.async_response
    async def update_gate(hass, connection, msg):
        manager = _authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        try:
            candidate = _validate_mapping(hass, msg)
            async with manager.lock:
                original = next(
                    (g for g in manager.data["gates"] if g["id"] == msg["gate_id"]),
                    None
                )
                if original is None:
                    raise ValueError("Varco inesistente.")
                if any(g["id"] != original["id"]
                       and g["entity_id"] == candidate["entity_id"]
                       for g in manager.data["gates"]):
                    raise ValueError("Entità già associata a un altro varco.")
                changed_mapping = (original["entity_id"] != candidate["entity_id"]
                                   or original["action"] != candidate["action"])
                original.update({
                    "name": candidate["name"],
                    "entity_id": candidate["entity_id"],
                    "action": candidate["action"],
                    "kind": candidate["kind"],
                    "enabled": False if changed_mapping else msg["enabled"],
                })
                manager.audit("gate_updated", original["name"])
                await manager.async_save()
        except ValueError as err:
            _error(connection, msg, err)
            return
        connection.send_result(msg["id"], _summary(manager, connection))

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/remove_gate",
        vol.Required("gate_id"): str,
    })
    @websocket_api.async_response
    async def remove_gate(hass, connection, msg):
        manager = _authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        try:
            async with manager.lock:
                gate = next(
                    (g for g in manager.data["gates"] if g["id"] == msg["gate_id"]),
                    None
                )
                if gate is None:
                    raise ValueError("Varco inesistente.")
                check_gate_removal(gate["id"], manager.data["bookings"])
                manager.data["gates"].remove(gate)
                manager.audit("gate_removed", gate["name"])
                await manager.async_save()
        except ValueError as err:
            _error(connection, msg, err)
            return
        connection.send_result(msg["id"], _summary(manager, connection))

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/add_booking",
        vol.Required("room"): str,
        vol.Optional("guest_name", default=""): str,
        vol.Required("start"): str,
        vol.Required("end"): str,
        vol.Required("gate_ids"): [str],
    })
    @websocket_api.async_response
    async def add_booking(hass, connection, msg):
        manager = _authorize(hass, connection, msg)
        if manager is None:
            return
        pin = generate_pin()
        try:
            # PBKDF2 hashing runs on the executor, not the Home Assistant loop.
            booking = await hass.async_add_executor_job(
                make_booking, msg["room"], msg["start"],
                msg["end"], msg["gate_ids"], pin, msg.get("guest_name", "")
            )
            if as_utc(booking["end"]) <= datetime.now(timezone.utc):
                raise ValueError("Check-out già trascorso.")
            async with manager.lock:
                selected = set(booking["gate_ids"])
                allowed = {g["id"] for g in manager.data["gates"] if g["enabled"]}
                if not selected.issubset(allowed):
                    raise ValueError("Uno o più varchi non sono abilitati.")
                if len(manager.data["bookings"]) >= MAX_BOOKINGS:
                    raise ValueError("Numero massimo di prenotazioni raggiunto.")
                manager.data["bookings"].append(booking)
                manager.audit("booking_added", booking["room"])
                await manager.async_save()
        except (ValueError, OverflowError) as err:
            _error(connection, msg, err)
            return
        # PIN is returned once to the authenticated administrator or selected operator.
        connection.send_result(msg["id"], {"pin_once": pin, "data": _summary(manager, connection)})

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/revoke_booking",
        vol.Required("booking_id"): str,
    })
    @websocket_api.async_response
    async def revoke_booking(hass, connection, msg):
        manager = _authorize(hass, connection, msg)
        if manager is None:
            return
        try:
            async with manager.lock:
                booking = next((b for b in manager.data["bookings"]
                                if b["id"] == msg["booking_id"]), None)
                if booking is None:
                    raise ValueError("Prenotazione inesistente.")
                booking["revoked"] = True
                manager.audit("booking_revoked", booking["room"])
                await manager.async_save()
        except ValueError as err:
            _error(connection, msg, err)
            return
        connection.send_result(msg["id"], _summary(manager, connection))

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/qr",
        vol.Required("gate_id"): str,
        vol.Required("base_url"): str,
    })
    @websocket_api.async_response
    async def get_qr(hass, connection, msg):
        manager = _authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        # Use an operator-provided HTTPS public URL. No internal tokens or
        # HA auth session credentials are embedded in the permanent QR.
        from urllib.parse import urlsplit
        from io import BytesIO
        import segno

        base = msg["base_url"].strip().rstrip("/")
        parts = urlsplit(base)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.query
            or parts.fragment
            or parts.path not in ("", "/")
            or len(base) > 255
        ):
            _error(connection, msg, "Inserisci un URL HTTPS pubblico valido, senza percorso.")
            return
        gate = next(
            (g for g in manager.data["gates"] if g["id"] == msg["gate_id"]),
            None,
        )
        if gate is None:
            _error(connection, msg, "Varco inesistente.")
            return
        if len(str(gate.get("token", ""))) < 20:
            _error(connection, msg, "Token QR non valido.")
            return
        target = f"{base}/api/cl_bb_manager/guest/{gate['token']}"
        buffer = BytesIO()
        segno.make_qr(target).save(buffer, kind="svg", scale=6, border=3)
        connection.send_result(msg["id"], {
            "svg": buffer.getvalue().decode("utf-8"),
            "url": target,
            "guest_portal": "disabled",
        })

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/demo_check_pin",
        vol.Required("gate_id"): str,
        vol.Required("pin"): str,
        vol.Optional("simulate_open", default=False): bool,
    })
    @websocket_api.async_response
    async def demo_check_pin(hass, connection, msg):
        """Admin-only test: check access and optionally actuate a virtual script.

        No unauthenticated guest access and NO physical door entities.
        """
        from .guest import DEMO_SCRIPTS

        manager = _authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        pin = msg["pin"]
        if not (len(pin) == 8 and pin.isascii() and pin.isdecimal()):
            _error(connection, msg, "Il PIN deve avere otto cifre.")
            return
        try:
            async with manager.lock:
                gate = next(
                    (g for g in manager.data["gates"] if g["id"] == msg["gate_id"]), None
                )
                if gate is None or not demo_target_allowed(gate, DEMO_SCRIPTS):
                    raise ValueError("Varco demo inesistente o non abilitato.")
                # Counter is persisted before attempting any PIN work.
                throttle = manager.data.setdefault("attempts", {"all": [], "gates": {}})
                if not charge_attempt(throttle, gate["id"]):
                    await manager.async_save()
                    raise ValueError("Limite di tentativi superato.")
                await manager.async_save()
                candidates = candidate_bookings(
                    manager.data["bookings"], gate["id"]
                )
                authorized = False
                for booking in candidates:
                    if await hass.async_add_executor_job(pin_matches, pin, booking):
                        authorized = True
                        break
                if not authorized:
                    manager.audit("demo_pin_denied", gate["id"])
                    await manager.async_save()
                    connection.send_result(msg["id"], {"allowed": False, "opened": False})
                    return
                if msg["simulate_open"]:
                    if hass.states.get(gate["entity_id"]) is None:
                        raise ValueError("Script virtuale non disponibile.")
                    # Trigger only the allowlisted, verified demo entity.
                    await hass.services.async_call(
                        "script", "turn_on",
                        {"entity_id": gate["entity_id"]}, blocking=True
                    )
                    manager.audit("demo_pin_opened", gate["id"])
                    await manager.async_save()
                connection.send_result(msg["id"], {
                    "allowed": True, "opened": bool(msg["simulate_open"])
                })
        except ValueError as err:
            _error(connection, msg, err)
        except Exception:
            connection.send_error(
                msg["id"], "demo_test_failed", "Verifica demo non riuscita."
            )

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/demo_qr",
        vol.Required("gate_id"): str,
        vol.Required("base_url"): str,
    })
    @websocket_api.async_response
    async def demo_qr(hass, connection, msg):
        """Create a single temporary LAN-only QR, for demo scripts only."""
        import time
        from io import BytesIO
        import segno
        from .demo_policy import (
            MAX_DEMO_SESSIONS, make_demo_session
        )
        from .guest import DEMO_SCRIPTS

        manager = _authorize(hass, connection, msg)
        if manager is None:
            return
        try:
            gate = next(
                (g for g in manager.data["gates"] if g["id"] == msg["gate_id"]),
                None
            )
            if gate is None or not demo_target_allowed(gate, DEMO_SCRIPTS):
                raise ValueError("Seleziona uno dei cinque varchi demo abilitati.")
            if hass.states.get(gate["entity_id"]) is None:
                raise ValueError("Script virtuale non disponibile.")
            # Protect session bookkeeping under the same manager lock.
            async with manager.lock:
                now = time.time()
                manager.demo_sessions = {
                    token: session
                    for token, session in manager.demo_sessions.items()
                    if session.get("expires", 0) > now
                }
                if len(manager.demo_sessions) >= MAX_DEMO_SESSIONS:
                    raise ValueError(
                        "Sono già attive cinque sessioni. Attendi la scadenza."
                    )
                token, session = make_demo_session(
                    gate["id"], msg["base_url"], now=now
                )
                url = (
                    session["origin"]
                    + "/api/cl_bb_manager/demo/"
                    + token
                )
                buffer = BytesIO()
                segno.make_qr(url).save(
                    buffer, kind="svg", scale=6, border=3
                )
                manager.demo_sessions[token] = session
            connection.send_result(msg["id"], {
                "svg": buffer.getvalue().decode("utf-8"),
                "url": url,
                "expires_seconds": 600,
                "guest_portal": "disabled",
            })
        except (ValueError, TypeError) as err:
            _error(connection, msg, err)


    @websocket_api.websocket_command({
        "type": "cl_bb_manager/public_pilot_qr",
        vol.Required("gate_id"): str,
    })
    @websocket_api.async_response
    async def public_pilot_qr(hass, connection, msg):
        """Admin-only one-use HTTPS QR for a verified, allowlisted virtual script."""
        import time
        from io import BytesIO
        import segno
        from .guest import DEMO_SCRIPTS
        from .public_policy import (
            MAX_PUBLIC_SESSIONS, create_public_session, validate_public_origin
        )

        manager = _authorize(hass, connection, msg)
        if manager is None:
            return
        try:
            if not manager.entry.options.get("public_pilot_enabled", False):
                raise ValueError("Abilitare prima il collaudo HTTPS nelle opzioni.")
            origin = validate_public_origin(
                hass.config.external_url or manager.entry.options.get("public_pilot_origin", "")
            )
            gate = next(
                (g for g in manager.data["gates"] if g["id"] == msg["gate_id"]),
                None,
            )
            if gate is None or not demo_target_allowed(gate, DEMO_SCRIPTS):
                raise ValueError("Varco virtuale non autorizzato.")
            if hass.states.get(gate["entity_id"]) is None:
                raise ValueError("Script virtuale non disponibile.")

            async with manager.lock:
                now = time.time()
                manager.public_demo_sessions = {
                    key: session
                    for key, session in manager.public_demo_sessions.items()
                    if session.get("expires", 0) > now
                }
                if len(manager.public_demo_sessions) >= MAX_PUBLIC_SESSIONS:
                    raise ValueError("Attendere: troppe sessioni HTTPS attive.")
                token, session = create_public_session(
                    gate["id"], origin, now=now
                )
                url = origin + "/api/cl_bb_manager/public-demo/" + token
                buffer = BytesIO()
                segno.make_qr(url).save(buffer, kind="svg", scale=6, border=3)
                manager.public_demo_sessions[token] = session
            connection.send_result(msg["id"], {
                "svg": buffer.getvalue().decode("utf-8"),
                "url": url,
                "expires_seconds": 600,
                "one_time": True,
            })
        except (ValueError, TypeError) as err:
            _error(connection, msg, err)

    for handler in (
        get_list, add_gate, update_gate, remove_gate, add_booking, revoke_booking, get_qr, demo_check_pin, demo_qr, public_pilot_qr
    ):
        websocket_api.async_register_command(hass, handler)
