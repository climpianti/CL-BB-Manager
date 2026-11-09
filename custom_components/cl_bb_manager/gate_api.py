"""Operator access status and administrator-only Shelly setup endpoints."""
from homeassistant.components import websocket_api
import voluptuous as vol

from .gate_setup import (async_add_shelly_gate, available_gate_relays,
                         async_add_entity_gate, available_gate_entities)
from .permissions import user_role
from .entity_gate import ACTIONS


def register_gate_setup_commands(hass, authorize, summary, manager_of, send_error):
    @websocket_api.websocket_command({"type": "cl_bb_manager/access_status"})
    @websocket_api.async_response
    async def access_status(hass, connection, msg):
        manager = manager_of(hass)
        role = user_role(connection.user, manager.entry.options) if manager else None
        connection.send_result(msg["id"], {"authorized": role is not None, "role": role})

    @websocket_api.websocket_command({"type": "cl_bb_manager/shelly_relays"})
    @websocket_api.async_response
    async def shelly_relays(hass, connection, msg):
        manager = authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        connection.send_result(msg["id"], {"relays": available_gate_relays(manager)})

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/add_shelly_gate",
        vol.Required("name"): str, vol.Required("entity_id"): str,
        vol.Required("pulse_seconds"): vol.Any(int, float),
        vol.Required("kind"): vol.In(["private", "shared"]),
        vol.Required("confirm"): vol.Equal(True),
    })
    @websocket_api.async_response
    async def add_shelly_gate(hass, connection, msg):
        manager = authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        try:
            await async_add_shelly_gate(manager, name=msg["name"], entity_id=msg["entity_id"],
                                       seconds=msg["pulse_seconds"], kind=msg["kind"])
        except (ValueError, TypeError, KeyError) as exc:
            send_error(connection, msg, exc)
            return
        connection.send_result(msg["id"], summary(manager, connection))

    @websocket_api.websocket_command({"type": "cl_bb_manager/door_entities"})
    @websocket_api.async_response
    async def door_entities(hass, connection, msg):
        manager = authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        connection.send_result(msg["id"], {"entities": available_gate_entities(manager)})

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/add_entity_gate",
        vol.Required("name"): str, vol.Required("entity_id"): str,
        vol.Required("action"): vol.In(list(ACTIONS)),
        vol.Required("kind"): vol.In(["private", "shared"]),
        vol.Optional("switch_mode", default="ha_pulse"): vol.In(["ha_pulse", "device_pulse"]),
        vol.Optional("pulse_seconds", default=2): vol.Any(int, float),
        vol.Optional("confirm_device_pulse", default=False): bool,
        vol.Required("confirm"): vol.Equal(True),
    })
    @websocket_api.async_response
    async def add_entity_gate(hass, connection, msg):
        manager = authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        try:
            await async_add_entity_gate(manager, name=msg["name"], entity_id=msg["entity_id"],
                action=msg["action"], kind=msg["kind"], switch_mode=msg.get("switch_mode", "ha_pulse"),
                seconds=msg.get("pulse_seconds", 2), confirm_device_pulse=msg.get("confirm_device_pulse", False))
        except (ValueError, TypeError, KeyError) as exc:
            send_error(connection, msg, exc)
            return
        connection.send_result(msg["id"], summary(manager, connection))

    @websocket_api.websocket_command({
        "type": "cl_bb_manager/recover_entity_gate",
        vol.Required("gate_id"): str,
        vol.Required("confirm"): vol.Equal(True),
    })
    @websocket_api.async_response
    async def recover_entity_gate(hass, connection, msg):
        manager = authorize(hass, connection, msg, admin_only=True)
        if manager is None:
            return
        from .entity_gate import async_reset_pending
        async with manager.lock:
            await async_reset_pending(manager, msg["gate_id"])
        connection.send_result(msg["id"], summary(manager, connection))

    for handler in (access_status, shelly_relays, add_shelly_gate, door_entities, add_entity_gate, recover_entity_gate):
        websocket_api.async_register_command(hass, handler)
