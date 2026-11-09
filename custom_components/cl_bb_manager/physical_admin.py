"""Admin-only persistent physical QR provisioning and emergency stop.

Staging a QR never arms hardware. Site and gate arming require separate explicit
administrator confirmation and can be disabled at any time.
"""
from __future__ import annotations

from io import BytesIO
from copy import deepcopy
import secrets

from homeassistant.components import websocket_api
import voluptuous as vol

from .const import DOMAIN
from .hardware_staging import read_candidate
from .physical_policy import PILOT_SCRIPT_RELAY, PHYSICAL_RELEASE_ENABLED, ready_actuator
from .property_scope import require_record_scope
from .public_policy import validate_public_origin


def invalidate_gate_physical_credentials(manager, gate_id: str) -> None:
    """Revoke physical QR and grants on mapping change, under manager.lock."""
    gate = next((g for g in manager.data["gates"] if g.get("id") == gate_id), None)
    if gate is not None:
        gate["physical_enabled"] = False
        gate.pop("physical_token", None)
    for booking in manager.data["bookings"]:
        ids = booking.get("physical_gate_ids")
        if isinstance(ids, list):
            booking["physical_gate_ids"] = [g for g in ids if g != gate_id]
    manager.physical_forms.clear()


def register_physical_admin_commands(hass, authorize, summary, send_error):
    """Register admin-only preparation, revocation and safety operations."""

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/prepare_physical_qr",
        vol.Required("gate_id"): str,
        vol.Required("confirm"): vol.Equal(True),
    })
    @websocket_api.async_response
    async def prepare_physical_qr(hass, connection, msg):
        """Mint a distinct, dormant URL; never arm its actuator."""
        manager = authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        try:
            import segno
            origin = validate_public_origin(
                hass.config.external_url or manager.entry.options.get("public_origin")
                or manager.entry.options.get("public_pilot_origin", "")
            )
            async with manager.lock:
                matches = [g for g in manager.data["gates"] if g.get("id") == msg["gate_id"]]
                if len(matches) != 1:
                    raise ValueError("Varco non disponibile.")
                gate = matches[0]
                require_record_scope(gate, manager.property_id)
                if gate.get("enabled") is not True and not any(key in gate for key in ("shelly_binding", "entity_binding")):
                    raise ValueError("Varco disabilitato.")
                if ready_actuator(gate, hass) is None:
                    raise ValueError("Dispositivo del varco non pronto.")
                token = secrets.token_urlsafe(36)
                while token == gate.get("token") or token == gate.get("physical_token"):
                    token = secrets.token_urlsafe(36)
                gate["physical_token"] = token
                gate["physical_enabled"] = False
                manager.physical_forms.clear()
                manager.audit("physical_qr_prepared_dormant", gate["id"])
                await manager.async_save()
                name = gate["name"]
            url = origin + "/api/cl_bb_manager/physical/" + token
            buffer = BytesIO()
            segno.make_qr(url).save(buffer, kind="svg", scale=8, border=4)
            connection.send_result(msg["id"], {
                "gate_id": msg["gate_id"],
                "name": name,
                "svg": buffer.getvalue().decode("utf-8"),
                "url": url,
                "armed": False,
                "release_enabled": PHYSICAL_RELEASE_ENABLED,
                "message": "Nuovo QR preparato. Il varco resta disattivato fino all'abilitazione.",
            })
        except (ValueError, TypeError) as err:
            send_error(connection, msg, err)

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/grant_physical_booking",
        vol.Required("booking_id"): str,
        vol.Required("gate_id"): str,
        vol.Required("confirm"): vol.Equal(True),
    })
    @websocket_api.async_response
    async def grant_physical_booking(hass, connection, msg):
        """Stage explicit guest permission, with no implicit hardware arming."""
        manager = authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        try:
            async with manager.lock:
                gates = [g for g in manager.data["gates"] if g.get("id") == msg["gate_id"]]
                bookings = [b for b in manager.data["bookings"] if b.get("id") == msg["booking_id"]]
                if len(gates) != 1 or len(bookings) != 1:
                    raise ValueError("Varco o prenotazione non disponibile.")
                gate, booking = gates[0], bookings[0]
                require_record_scope(gate, manager.property_id)
                require_record_scope(booking, manager.property_id)
                if gate.get("physical_token") is None:
                    raise ValueError("Preparare prima un QR fisico per il varco.")
                if booking.get("revoked") is True or gate["id"] not in booking.get("gate_ids", []):
                    raise ValueError("Prenotazione revocata o non autorizzata per il varco.")
                from datetime import datetime, timezone
                from .models import as_utc
                # Future bookings can be pre-authorized, but never expired ones.
                if as_utc(booking["end"]) <= datetime.now(timezone.utc):
                    raise ValueError("Prenotazione già terminata.")
                granted = booking.get("physical_gate_ids", [])
                if not isinstance(granted, list):
                    raise ValueError("Autorizzazioni fisiche non valide.")
                booking["physical_gate_ids"] = sorted(set(granted) | {gate["id"]})
                manager.audit("physical_booking_grant_staged", booking["id"])
                await manager.async_save()
            connection.send_result(msg["id"], {
                "granted": True, "armed": bool(manager.data.get("physical_access_enabled") and gate.get("physical_enabled")), "release_enabled": PHYSICAL_RELEASE_ENABLED,
                "booking_id": msg["booking_id"], "gate_id": msg["gate_id"],
            })
        except (ValueError, TypeError, KeyError) as err:
            send_error(connection, msg, err)

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/revoke_physical_booking",
        vol.Required("booking_id"): str,
        vol.Required("gate_id"): str,
        vol.Required("confirm"): vol.Equal(True),
    })
    @websocket_api.async_response
    async def revoke_physical_booking(hass, connection, msg):
        manager = authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        try:
            async with manager.lock:
                matches = [b for b in manager.data["bookings"] if b.get("id") == msg["booking_id"]]
                if len(matches) != 1:
                    raise ValueError("Prenotazione non disponibile.")
                booking = matches[0]
                require_record_scope(booking, manager.property_id)
                current = booking.get("physical_gate_ids", [])
                if not isinstance(current, list):
                    raise ValueError("Autorizzazioni fisiche non valide.")
                booking["physical_gate_ids"] = [g for g in current if g != msg["gate_id"]]
                manager.physical_forms.clear()
                manager.audit("physical_booking_revoked", booking["id"])
                await manager.async_save()
            connection.send_result(msg["id"], {"revoked": True})
        except (ValueError, TypeError) as err:
            send_error(connection, msg, err)

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/arm_physical_gate",
        vol.Required("gate_id"): str,
        vol.Required("confirm"): vol.Equal(True),
        vol.Optional("confirm_wiring", default=False): bool,
    })
    @websocket_api.async_response
    async def arm_physical_gate(hass, connection, msg):
        """Persistent arming: no expiration. PIN and booking checks remain per use."""
        manager = authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        try:
            from .physical_policy import physical_target
            async with manager.lock:
                gates = [g for g in manager.data["gates"] if g.get("id") == msg["gate_id"]]
                if len(gates) != 1:
                    raise ValueError("Varco non trovato.")
                gate = gates[0]
                require_record_scope(gate, manager.property_id)
                if not PHYSICAL_RELEASE_ENABLED:
                    raise ValueError("La release non consente l'accesso fisico.")
                if not isinstance(gate.get("physical_token"), str):
                    raise ValueError("Preparare il nuovo QR fisico prima dell'attivazione.")
                if ready_actuator(gate, hass) is None:
                    raise ValueError("Dispositivo del varco non pronto.")
                previous_gate = deepcopy(gate)
                had_global = "physical_access_enabled" in manager.data
                previous_global = manager.data.get("physical_access_enabled", False)
                previous_events = deepcopy(manager.data["events"])
                if any(key in gate for key in ("shelly_binding", "entity_binding")):
                    if msg.get("confirm_wiring") is not True:
                        raise ValueError("Conferma la verifica del collegamento e della durata dell'impulso.")
                    if "shelly_binding" in gate:
                        from .shelly_gate import async_validate
                        await async_validate(hass, gate["shelly_binding"])
                    else:
                        from .entity_gate import resolve_binding
                        resolve_binding(hass, gate["entity_binding"])
                        if gate['id'] in manager.data.get('pending_entity_pulses', {}):
                            raise ValueError('Ripristina il precedente impulso prima di abilitare il varco.')
                    # No test booking is needed to commission a new installation.
                    # Every opening still needs its own currently eligible booking.
                    gate["enabled"] = True
                else:
                    from .physical_policy import approved_booking
                    if gate.get("enabled") is not True or not any(
                        approved_booking(b, gate["id"], manager.property_id)
                        for b in manager.data["bookings"]
                    ):
                        raise ValueError("Manca una prenotazione attiva con permesso fisico esplicito.")
                manager.data["physical_access_enabled"] = True
                gate["physical_enabled"] = True
                manager.audit("physical_gate_armed_permanent", gate["id"])
                try:
                    await manager.async_save()
                except Exception as exc:
                    gate.clear()
                    gate.update(previous_gate)
                    if had_global:
                        manager.data["physical_access_enabled"] = previous_global
                    else:
                        manager.data.pop("physical_access_enabled", None)
                    manager.data["events"] = previous_events
                    manager.physical_forms.clear()
                    raise ValueError("Salvataggio non riuscito: abilitazione non completata.") from exc
            connection.send_result(msg["id"], {
                "armed": True, "gate_id": msg["gate_id"],
                "persistent": True,
                "message": "QR fisico attivo senza scadenza; PIN e prenotazione rimangono obbligatori.",
            })
        except (ValueError, TypeError, KeyError) as err:
            send_error(connection, msg, err)

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/physical_qr",
        vol.Required("gate_id"): str,
    })
    @websocket_api.async_response
    async def physical_qr(hass, connection, msg):
        """Read the existing printable QR; never rotate credentials or arm."""
        manager = authorize(hass, connection, msg)
        if manager is None:
            return
        try:
            import segno
            origin = validate_public_origin(hass.config.external_url
                or manager.entry.options.get("public_origin")
                or manager.entry.options.get("public_pilot_origin", ""))
            gates = [g for g in manager.data["gates"] if g.get("id") == msg["gate_id"]]
            if len(gates) != 1:
                raise ValueError("Varco non disponibile.")
            gate = require_record_scope(gates[0], manager.property_id)
            token = gate.get("physical_token")
            if not isinstance(token, str) or not 40 <= len(token) <= 100:
                raise ValueError("QR non ancora predisposto per questo varco.")
            target = origin + "/api/cl_bb_manager/physical/" + token
            buffer = BytesIO()
            segno.make_qr(target).save(buffer, kind="svg", scale=8, border=4)
            connection.send_result(msg["id"], {
                "gate_id": gate["id"], "name": gate["name"],
                "url": target, "svg": buffer.getvalue().decode(),
                "armed": gate.get("physical_enabled") is True,
            })
        except (ValueError, TypeError, KeyError) as err:
            send_error(connection, msg, err)

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/disarm_physical_gate",
        vol.Required("gate_id"): str,
        vol.Required("confirm"): vol.Equal(True),
    })
    @websocket_api.async_response
    async def disarm_physical_gate(hass, connection, msg):
        """Disable one physical gate without rotating a printed QR."""
        manager = authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        try:
            async with manager.lock:
                gates = [g for g in manager.data["gates"] if g.get("id") == msg["gate_id"]]
                if len(gates) != 1:
                    raise ValueError("Varco non disponibile.")
                gate = gates[0]
                require_record_scope(gate, manager.property_id)
                gate["physical_enabled"] = False
                manager.physical_forms.clear()
                manager.audit("physical_gate_disarmed", gate["id"])
                await manager.async_save()
            connection.send_result(msg["id"], {"disarmed": True, "gate_id": msg["gate_id"]})
        except (ValueError, TypeError) as err:
            send_error(connection, msg, err)

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/emergency_disable_physical",
        vol.Required("confirm"): vol.Equal(True),
    })
    @websocket_api.async_response
    async def emergency_disable_physical(hass, connection, msg):
        """Immediately disable all physical rights and invalidate all URLs."""
        manager = authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        async with manager.lock:
            manager.data["physical_access_enabled"] = False
            for gate in manager.data["gates"]:
                invalidate_gate_physical_credentials(manager, gate["id"])
            manager.audit("physical_emergency_disabled")
            await manager.async_save()
        connection.send_result(msg["id"], {
            "disabled": True,
            "physical_qr_enabled": False,
            "all_physical_tokens_revoked": True,
            "existing_virtual_qr_unchanged": True,
        })

    for handler in (
        prepare_physical_qr,
        grant_physical_booking,
        revoke_physical_booking,
        arm_physical_gate,
        disarm_physical_gate,
        emergency_disable_physical,
        physical_qr,
    ):
        websocket_api.async_register_command(hass, handler)

