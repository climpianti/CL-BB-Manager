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
        generic = other.get("entity_binding", {}).get("identity", {})
        candidate = other.get("hardware_candidate")
        if (other.get("entity_id") == relay.entity_id
            or (generic.get("platform") == "shelly" and generic.get("unique_id") == relay.unique_id)
            or (isinstance(binding, dict) and binding.get("unique_id") == relay.unique_id)
            or (isinstance(candidate, dict)
                and PILOT_SCRIPT_RELAY.get(candidate.get("entity_id")) == relay.entity_id)):
            return True
    for binding in manager.data.get('pending_entity_pulses', {}).values():
        if binding.get('identity', {}).get('platform') == 'shelly' and binding.get('identity', {}).get('unique_id') == relay.unique_id:
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


def entity_assigned(manager, entity_id, binding):
    from .physical_policy import PILOT_SCRIPT_RELAY
    identity = binding['identity']
    for gate in manager.data['gates']:
        other = gate.get('entity_binding', {})
        native = gate.get('shelly_binding', {})
        candidate = gate.get('hardware_candidate', {})
        if (gate.get('entity_id') == entity_id
            or (identity.get('registered') and identity == other.get('identity'))
            or (identity.get('platform') == 'shelly' and identity.get('unique_id') and identity.get('unique_id') == native.get('unique_id'))
            or PILOT_SCRIPT_RELAY.get(candidate.get('entity_id')) == entity_id):
            return True
    for pending in manager.data.get('pending_entity_pulses', {}).values():
        if pending.get('identity') == identity or pending.get('entity_id') == entity_id:
            return True
    return False


def available_gate_entities(manager):
    from .entity_gate import available_entities, make_binding
    result = []
    for item in available_entities(manager.hass):
        binding = make_binding(manager.hass, item['entity_id'], item['actions'][0]['action'])
        if not entity_assigned(manager, item['entity_id'], binding):
            result.append(item)
    return result


async def async_add_entity_gate(manager, *, name, entity_id, action, kind='private',
                                switch_mode='ha_pulse', seconds=2, confirm_device_pulse=False):
    from .entity_gate import make_binding
    gate = make_gate(name, entity_id, action, kind, enabled=False)
    async with manager.lock:
        if len(manager.data['gates']) >= MAX_GATES:
            raise ValueError('Numero massimo di varchi raggiunto.')
        binding = make_binding(manager.hass, entity_id, action, switch_mode=switch_mode,
                               seconds=seconds, confirm_device_pulse=confirm_device_pulse)
        if entity_assigned(manager, entity_id, binding):
            raise ValueError('Entità già associata a un varco.')
        gate.update(property_id=manager.property_id, entity_binding=binding,
                    physical_enabled=False, physical_token=secrets.token_urlsafe(36))
        events = deepcopy(manager.data['events'])
        manager.data['gates'].append(gate)
        manager.audit('entity_gate_configured', gate['id'])
        try:
            await manager.async_save()
        except Exception as exc:
            manager.data['gates'].remove(gate)
            manager.data['events'] = events
            raise ValueError('Salvataggio non riuscito: varco non configurato.') from exc
    return gate
