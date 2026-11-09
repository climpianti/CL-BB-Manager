"""Transactional, administrator-initiated commissioning; no relay ON commands."""
from __future__ import annotations

from copy import deepcopy
import secrets

from .models import make_gate
from .const import MAX_GATES
from .shelly_gate import async_configure, async_restore_profile, resolve_entity, available_relays


def relay_assigned(manager, relay):
    from .physical_policy import PILOT_SCRIPT_RELAY
    for other in manager.data["gates"]:
        binding = other.get("shelly_binding")
        candidate = other.get("hardware_candidate")
        if (other.get("entity_id") == relay.entity_id
            or (isinstance(binding, dict) and binding.get("unique_id") == relay.unique_id)
            or (isinstance(candidate, dict)
                and PILOT_SCRIPT_RELAY.get(candidate.get("entity_id")) == relay.entity_id)):
            return True
    return False


def available_gate_relays(manager):
    return [item for item in available_relays(manager.hass)
            if not relay_assigned(manager, resolve_entity(manager.hass, item["entity_id"]))]


async def async_add_shelly_gate(manager, *, name, entity_id, seconds=2, kind="private"):
    gate = make_gate(name, entity_id, "switch.turn_on", kind, enabled=False)
    async with manager.lock:
        relay = resolve_entity(manager.hass, entity_id)
        if len(manager.data["gates"]) >= MAX_GATES:
            raise ValueError("Numero massimo di varchi raggiunto.")
        if relay_assigned(manager, relay):
            raise ValueError("Questo relè è già associato a un varco.")
        binding, previous = await async_configure(manager.hass, entity_id, seconds)
        gate.update(property_id=manager.property_id, shelly_binding=binding,
                    physical_enabled=False, physical_token=secrets.token_urlsafe(36))
        previous_events = deepcopy(manager.data["events"])
        manager.data["gates"].append(gate)
        manager.audit("shelly_gate_configured", gate["id"])
        try:
            await manager.async_save()
        except Exception as exc:
            manager.data["gates"].remove(gate)
            manager.data["events"] = previous_events
            try:
                await async_restore_profile(manager.hass, binding, previous)
            except Exception:
                pass  # No gate was activated; never retry an uncertain write.
            raise ValueError("Salvataggio non riuscito: il varco non è stato attivato.") from exc
    return gate
