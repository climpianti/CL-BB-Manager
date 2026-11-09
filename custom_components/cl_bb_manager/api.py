"""Role-aware websocket API for CL B&B Manager.

Device setup is admin-only. Opening requires the separate physical PIN endpoint.
"""
from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components import websocket_api
import voluptuous as vol

from .const import DOMAIN, MAX_BOOKINGS, MAX_GATES
from .models import as_utc, generate_pin, make_booking, make_gate, pin_matches
from .gate_management import check_gate_removal, native_mapping_changed
from .physical_admin import invalidate_gate_physical_credentials
from .permissions import user_role
from .property_scope import assert_gate_scope, require_record_scope
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
        vol.Required("action"): vol.In(["script.turn_on", "button.press", "lock.unlock", "lock.open", "switch.turn_on", "cover.open_cover", "input_button.press"]),
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
                gate["property_id"] = manager.property_id
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
        vol.Required("action"): vol.In(["script.turn_on", "button.press", "lock.unlock", "lock.open", "switch.turn_on", "cover.open_cover", "input_button.press"]),
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
                require_record_scope(original, manager.property_id)
                if any(g["id"] != original["id"]
                       and g["entity_id"] == candidate["entity_id"]
                       for g in manager.data["gates"]):
                    raise ValueError("Entità già associata a un altro varco.")
                sensitive_change = any(
                    original[key] != candidate[key]
                    for key in ("entity_id", "action", "kind")
                )
                if "shelly_binding" in original or "entity_binding" in original:
                    sensitive_change = native_mapping_changed(hass, original, candidate)
                if sensitive_change:
                    # Keep active/future bookings bound to the same gate mapping.
                    check_gate_removal(original["id"], manager.data["bookings"])
                original.update({
                    "name": candidate["name"],
                    "entity_id": candidate["entity_id"],
                    "action": candidate["action"],
                    "kind": candidate["kind"],
                    "enabled": False if sensitive_change else msg["enabled"],
                })
                if sensitive_change:
                    # Mapping changes require deliberate re-enabling and revoke old QR sessions.
                    invalidate_gate_physical_credentials(manager, original["id"])
                    original["token"] = candidate["token"]
                    manager.demo_sessions.clear()
                    manager.public_demo_sessions.clear()
                    manager.permanent_forms.clear()
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
                require_record_scope(gate, manager.property_id)
                check_gate_removal(gate["id"], manager.data["bookings"])
                manager.permanent_forms.clear()
                invalidate_gate_physical_credentials(manager, gate["id"])
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
                property_id = manager.property_id
                assert_gate_scope(manager.data["gates"], booking["gate_ids"], property_id)
                selected = set(booking["gate_ids"])
                allowed = {g["id"] for g in manager.data["gates"] if g["enabled"] and g.get("property_id") == property_id}
                if not selected.issubset(allowed):
                    raise ValueError("Uno o più varchi non sono abilitati.")
                if len(manager.data["bookings"]) >= MAX_BOOKINGS:
                    raise ValueError("Numero massimo di prenotazioni raggiunto.")
                booking["property_id"] = property_id
                # Explicit selection when creating a booking defines its physical ACL.
                # Existing reservations keep their grants unchanged during upgrade.
                booking["physical_gate_ids"] = [
                    gate["id"] for gate in manager.data["gates"]
                    if gate["id"] in selected and gate.get("physical_token")
                    and (gate.get("shelly_binding") or gate.get("entity_binding") or gate.get("hardware_candidate"))
                ]
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
                require_record_scope(booking, manager.property_id)
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
        try:
            require_record_scope(gate, manager.property_id)
        except ValueError as err:
            _error(connection, msg, err)
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
                require_record_scope(gate, manager.property_id)
                # Counter is persisted before attempting any PIN work.
                throttle = manager.data.setdefault("attempts", {"all": [], "gates": {}})
                if not charge_attempt(throttle, gate["id"]):
                    await manager.async_save()
                    raise ValueError("Limite di tentativi superato.")
                await manager.async_save()
                candidates = candidate_bookings(
                    manager.data["bookings"], gate["id"], property_id=manager.property_id
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
            require_record_scope(gate, manager.property_id)
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
            require_record_scope(gate, manager.property_id)
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


    @websocket_api.websocket_command({
        "type": "cl_bb_manager/stage_hardware_gate",
        vol.Required("gate_id"): str,
        vol.Required("script_id"): str,
    })
    @websocket_api.async_response
    async def stage_hardware_gate(hass, connection, msg):
        """Admin-only metadata: never sends a device command or changes QR rights."""
        from .guest import DEMO_SCRIPTS
        from .hardware_staging import FIELD, prepare_candidate

        manager = _authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        try:
            async with manager.lock:
                matching = [
                    gate for gate in manager.data["gates"]
                    if gate.get("id") == msg["gate_id"]
                ]
                if len(matching) != 1:
                    raise ValueError("Varco non disponibile.")
                gate = matching[0]
                if not demo_target_allowed(gate, DEMO_SCRIPTS):
                    raise ValueError("Associazione solo a un varco demo verificato.")
                candidate = prepare_candidate(
                    gate, manager.property_id, msg["script_id"],
                    hass.states.get(msg["script_id"]),
                    virtual_script_ids=DEMO_SCRIPTS,
                )
                if any(
                    other.get("id") != gate["id"]
                    and isinstance(other.get(FIELD), dict)
                    and other[FIELD].get("entity_id") == candidate["entity_id"]
                    for other in manager.data["gates"]
                ):
                    raise ValueError("Script già proposto per un altro varco.")
                invalidate_gate_physical_credentials(manager, gate["id"])
                gate[FIELD] = candidate
                manager.audit("hardware_candidate_staged", gate["id"])
                await manager.async_save()
            connection.send_result(msg["id"], _summary(manager, connection))
        except (ValueError, TypeError) as err:
            _error(connection, msg, err)

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/clear_hardware_gate",
        vol.Required("gate_id"): str,
    })
    @websocket_api.async_response
    async def clear_hardware_gate(hass, connection, msg):
        """Remove a hardware candidate; QR token and booking ACL stay untouched."""
        from .hardware_staging import clear_candidate

        manager = _authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        try:
            async with manager.lock:
                matching = [
                    gate for gate in manager.data["gates"]
                    if gate.get("id") == msg["gate_id"]
                ]
                if len(matching) != 1:
                    raise ValueError("Varco non disponibile.")
                invalidate_gate_physical_credentials(manager, matching[0]["id"])
                clear_candidate(matching[0], manager.property_id)
                manager.audit("hardware_candidate_cleared", msg["gate_id"])
                await manager.async_save()
            connection.send_result(msg["id"], _summary(manager, connection))
        except (ValueError, TypeError) as err:
            _error(connection, msg, err)

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/hardware_preflight",
    })
    @websocket_api.async_response
    async def hardware_preflight_report(hass, connection, msg):
        """Admin-only readiness report; never opens or arms a physical gate."""
        from .guest import DEMO_SCRIPTS
        from .hardware_preflight import hardware_preflight

        manager = _authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        async with manager.lock:
            report = [
                hardware_preflight(gate, manager.property_id, hass, DEMO_SCRIPTS)
                for gate in manager.data["gates"]
                if gate.get("hardware_candidate") is not None
            ]
        physical_on = manager.data.get("physical_access_enabled") is True
        armed_gates = [
            gate["id"] for gate in manager.data["gates"]
            if gate.get("physical_enabled") is True and physical_on
        ]
        connection.send_result(msg["id"], {
            "hardware_control": "enabled" if armed_gates else "disabled",
            "physical_qr_enabled": bool(armed_gates),
            "armed_gate_ids": armed_gates,
            "gates": report,
        })

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/permanent_pilot_qr",
        vol.Required("gate_id"): str,
    })
    @websocket_api.async_response
    async def permanent_pilot_qr(hass, connection, msg):
        """Return a repeatable, printable QR; does not grant any access."""
        from io import BytesIO
        import segno
        from .guest import DEMO_SCRIPTS
        from .permanent_policy import permanent_url
        from .public_policy import validate_public_origin

        manager = _authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        try:
            if not manager.entry.options.get("permanent_pilot_enabled", False):
                raise ValueError("Abilitare prima il QR fisso virtuale nelle opzioni.")
            origin = validate_public_origin(
                hass.config.external_url
                or manager.entry.options.get("public_pilot_origin", "")
            )
            async with manager.lock:
                gates = [g for g in manager.data["gates"] if g.get("id") == msg["gate_id"]]
                if len(gates) != 1:
                    raise ValueError("Varco non disponibile.")
                gate = gates[0]
                require_record_scope(gate, manager.property_id)
                if not demo_target_allowed(gate, DEMO_SCRIPTS):
                    raise ValueError("Solo i varchi virtuali abilitati possono usare QR fissi.")
                url = permanent_url(origin, gate["token"])
            buffer = BytesIO()
            segno.make_qr(url).save(buffer, kind="svg", scale=8, border=4)
            connection.send_result(msg["id"], {
                "svg": buffer.getvalue().decode("utf-8"),
                "url": url,
                "permanent": True,
                "printable": True,
                "hardware_control": "disabled",
            })
        except (ValueError, TypeError) as err:
            _error(connection, msg, err)

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/rotate_permanent_qr",
        vol.Required("gate_id"): str,
        vol.Required("confirm"): vol.Equal(True),
    })
    @websocket_api.async_response
    async def rotate_permanent_qr(hass, connection, msg):
        """Revoke a printed QR without editing a gate or changing bookings."""
        import secrets

        manager = _authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        try:
            async with manager.lock:
                gates = [g for g in manager.data["gates"] if g.get("id") == msg["gate_id"]]
                if len(gates) != 1:
                    raise ValueError("Varco non disponibile.")
                gate = gates[0]
                require_record_scope(gate, manager.property_id)
                old_token = gate.get("token")
                replacement = secrets.token_urlsafe(32)
                while replacement == old_token:
                    replacement = secrets.token_urlsafe(32)
                gate["token"] = replacement
                manager.permanent_forms.clear()
                manager.demo_sessions.clear()
                manager.public_demo_sessions.clear()
                manager.audit("permanent_qr_rotated", gate["id"])
                await manager.async_save()
            connection.send_result(msg["id"], {
                "rotated": True,
                "gate_id": msg["gate_id"],
                "message": "Vecchio QR revocato. Stampare e sostituire il nuovo QR.",
            })
        except (ValueError, TypeError) as err:
            _error(connection, msg, err)

    from .physical_admin import register_physical_admin_commands
    register_physical_admin_commands(hass, _authorize, _summary, _error)
    from .gate_api import register_gate_setup_commands
    register_gate_setup_commands(hass, _authorize, _summary, _manager, _error)

    for handler in (
        get_list, update_gate, remove_gate, add_booking, revoke_booking,
        hardware_preflight_report
    ):
        websocket_api.async_register_command(hass, handler)

