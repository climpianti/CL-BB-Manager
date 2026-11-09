"""Admin-only provisioning for future physical QR access.

This module intentionally cannot enable physical access. A separate reviewed
release is required to lift the compile-time and per-site kill switches.
"""
from __future__ import annotations

from io import BytesIO
import secrets

from homeassistant.components import websocket_api
import segno
import voluptuous as vol

from .const import DOMAIN
from .hardware_staging import read_candidate
from .physical_policy import PILOT_SCRIPT_RELAY, PHYSICAL_RELEASE_ENABLED
from .property_scope import require_record_scope
from .public_policy import validate_public_origin


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
            origin = validate_public_origin(
                hass.config.external_url
                or manager.entry.options.get("public_pilot_origin", "")
            )
            async with manager.lock:
                matches = [g for g in manager.data["gates"] if g.get("id") == msg["gate_id"]]
                if len(matches) != 1:
                    raise ValueError("Varco non disponibile.")
                gate = matches[0]
                require_record_scope(gate, manager.property_id)
                if gate.get("enabled") is not True:
                    raise ValueError("Varco disabilitato.")
                candidate = read_candidate(gate)
                if candidate is None or candidate["entity_id"] not in PILOT_SCRIPT_RELAY:
                    raise ValueError("Script Shelly non incluso nell'allowlist del pilota.")
                if gate.get("entity_id") == candidate["entity_id"]:
                    raise ValueError("I percorsi demo e fisici devono restare separati.")
                script = hass.states.get(candidate["entity_id"])
                relay = hass.states.get(PILOT_SCRIPT_RELAY[candidate["entity_id"]])
                if script is None or script.state != "off" or relay is None or relay.state != "off":
                    raise ValueError("Script o Shelly non pronto.")
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
                "message": "QR fisico preparato ma non abilitato: non stampare per gli ospiti.",
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
                if gate.get("physical_token") is None or gate.get("physical_enabled") is True:
                    raise ValueError("Preparare un QR fisico inattivo prima di concedere permessi.")
                if booking.get("revoked") is True or gate["id"] not in booking.get("gate_ids", []):
                    raise ValueError("Prenotazione revocata o non autorizzata per il varco.")
                from .models import booking_allows
                # Permissions must not be granted to a past/future booking outside its window.
                if not booking_allows(booking, gate["id"]):
                    raise ValueError("Prenotazione non attiva: grant non consentito.")
                granted = booking.get("physical_gate_ids", [])
                if not isinstance(granted, list):
                    raise ValueError("Autorizzazioni fisiche non valide.")
                booking["physical_gate_ids"] = sorted(set(granted) | {gate["id"]})
                manager.audit("physical_booking_grant_staged", booking["id"])
                await manager.async_save()
            connection.send_result(msg["id"], {
                "granted": True, "armed": False, "release_enabled": PHYSICAL_RELEASE_ENABLED,
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
                gate["physical_enabled"] = False
                gate.pop("physical_token", None)
            for booking in manager.data["bookings"]:
                booking.pop("physical_gate_ids", None)
            manager.physical_forms.clear()
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
        emergency_disable_physical,
    ):
        websocket_api.async_register_command(hass, handler)
