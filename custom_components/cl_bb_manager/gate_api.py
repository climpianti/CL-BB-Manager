"""Operator access status and administrator-only Shelly setup endpoints."""
from homeassistant.components import websocket_api
import voluptuous as vol

from .gate_setup import async_add_shelly_gate, available_gate_relays
from .permissions import user_role


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

    for handler in (access_status, shelly_relays, add_shelly_gate):
        websocket_api.async_register_command(hass, handler)
