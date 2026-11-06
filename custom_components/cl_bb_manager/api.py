"""Admin-only websocket API for dynamic gates and reservations.

The API intentionally contains NO service calls for opening gates in this alpha.
"""
from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components import websocket_api
import voluptuous as vol

from .const import DOMAIN, MAX_BOOKINGS, MAX_GATES
from .models import as_utc, generate_pin, make_booking, make_gate


def _manager(hass):
    return hass.data.get(DOMAIN, {}).get("manager")


def _authorize(hass, connection, msg):
    if connection.user is None or not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Solo amministratori.")
        return None
    manager = _manager(hass)
    if manager is None:
        connection.send_error(msg["id"], "not_ready", "Gestore non configurato.")
    return manager


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
            connection.send_result(msg["id"], manager.summary())

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/add_gate",
        vol.Required("name"): str,
        vol.Required("entity_id"): str,
        vol.Required("action"): vol.In(["script.turn_on", "button.press", "lock.unlock"]),
        vol.Required("kind"): vol.In(["shared", "private"]),
    })
    @websocket_api.async_response
    async def add_gate(hass, connection, msg):
        manager = _authorize(hass, connection, msg)
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
        connection.send_result(msg["id"], manager.summary())

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
        manager = _authorize(hass, connection, msg)
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
        connection.send_result(msg["id"], manager.summary())

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/remove_gate",
        vol.Required("gate_id"): str,
    })
    @websocket_api.async_response
    async def remove_gate(hass, connection, msg):
        manager = _authorize(hass, connection, msg)
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
                now = datetime.now(timezone.utc)
                if any(not b["revoked"]
                       and gate["id"] in b["gate_ids"]
                       and as_utc(b["end"]) > now
                       for b in manager.data["bookings"]):
                    raise ValueError("Revocare prima le prenotazioni future associate.")
                manager.data["gates"].remove(gate)
                manager.audit("gate_removed", gate["name"])
                await manager.async_save()
        except ValueError as err:
            _error(connection, msg, err)
            return
        connection.send_result(msg["id"], manager.summary())

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/add_booking",
        vol.Required("room"): str,
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
                msg["end"], msg["gate_ids"], pin
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
        # PIN sent only to this authenticated admin in the creation response.
        connection.send_result(msg["id"], {"pin_once": pin, "data": manager.summary()})

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
        connection.send_result(msg["id"], manager.summary())

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/qr",
        vol.Required("gate_id"): str,
        vol.Required("base_url"): str,
    })
    @websocket_api.async_response
    async def get_qr(hass, connection, msg):
        manager = _authorize(hass, connection, msg)
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

    for handler in (
        get_list, add_gate, update_gate, remove_gate, add_booking, revoke_booking, get_qr
    ):
        websocket_api.async_register_command(hass, handler)
