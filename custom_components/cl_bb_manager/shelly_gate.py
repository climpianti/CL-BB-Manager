"""Shelly door-pulse adapter using the authenticated, native HA connection.

No IPs, credentials, arbitrary RPC methods or service names come from a guest.
Setup configures timers but NEVER turns a relay on. Registry identity is checked
again on every use, so a renamed entity works and a replaced entity fails closed.
"""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
import math
import re

PROVIDER = "shelly_rpc"
SUPPORTED_MODELS = frozenset({"shelly1minigen3"})
_UNIQUE_ID = re.compile(r"^([0-9a-fA-F]{12})-switch:([0-7])$")
PROFILE_FIELDS = ("initial_state", "auto_on", "auto_off", "auto_off_delay")


def pulse_seconds(value) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not .5 <= value <= 5:
        raise ValueError("La durata dell'impulso deve essere tra 0,5 e 5 secondi.")
    return float(value)


def pulse_profile(seconds) -> dict:
    return {"initial_state": "off", "auto_on": False, "auto_off": True,
            "auto_off_delay": pulse_seconds(seconds)}


def profile_matches(config, seconds) -> bool:
    if not isinstance(config, Mapping):
        return False
    try:
        desired = pulse_profile(seconds)
        delay = config.get("auto_off_delay")
        return (
            config.get("initial_state") == desired["initial_state"]
            and config.get("auto_on") is False
            and config.get("auto_off") is True
            and type(delay) in (int, float) and math.isfinite(delay)
            and abs(delay - desired["auto_off_delay"]) < 1e-6
        )
    except ValueError:
        return False


def _registries(hass):
    # Lazy imports also keep pure policy tests independent of Home Assistant.
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    return er.async_get(hass), dr.async_get(hass)


def _model(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _mac(value):
    return re.sub(r"[^a-f0-9]", "", str(value).lower())


@dataclass(frozen=True)
class ResolvedRelay:
    entity_id: str
    unique_id: str
    device_id: str
    config_entry_id: str
    channel: int
    model: str
    rpc: object


def resolve_entity(hass, entity_id: str) -> ResolvedRelay:
    registry, devices = _registries(hass)
    record = registry.async_get(entity_id)
    if (record is None or record.platform != "shelly"
        or not entity_id.startswith("switch.") or record.disabled_by is not None):
        raise ValueError("Seleziona un relè dell'integrazione Shelly ufficiale.")
    match = _UNIQUE_ID.fullmatch(record.unique_id or "")
    device = devices.async_get(record.device_id) if record.device_id else None
    entry = hass.config_entries.async_get_entry(record.config_entry_id)
    if (not match or device is None or entry is None or entry.domain != "shelly"
        or _model(device.model) not in SUPPORTED_MODELS):
        raise ValueError("Modello non supportato: seleziona uno Shelly 1 Mini Gen3.")
    coordinator = getattr(getattr(entry, "runtime_data", None), "rpc", None)
    rpc = getattr(coordinator, "device", None)
    state = hass.states.get(entity_id)
    if (rpc is None or not getattr(coordinator, "connected", False)
        or state is None or state.state != "off"
        or not callable(getattr(rpc, "call_rpc", None))
        or _mac(getattr(rpc, "mac", "")) != match[1].lower()
        or _mac(entry.unique_id) != match[1].lower()):
        raise ValueError("Shelly non pronto: controlla connessione, identità e uscita OFF.")
    return ResolvedRelay(entity_id, record.unique_id, record.device_id,
                         record.config_entry_id, int(match[2]), device.model, rpc)


def binding_from_relay(relay: ResolvedRelay, seconds) -> dict:
    return {"provider": PROVIDER, "unique_id": relay.unique_id,
            "device_id": relay.device_id, "config_entry_id": relay.config_entry_id,
            "channel": relay.channel, "model": relay.model,
            "pulse_seconds": pulse_seconds(seconds), "configured": True}


def resolve_binding(hass, binding: dict) -> ResolvedRelay:
    if not isinstance(binding, dict) or binding.get("provider") != PROVIDER:
        raise ValueError("Associazione Shelly non valida.")
    if binding.get("configured") is not True:
        raise ValueError("Configurazione Shelly incompleta.")
    pulse_seconds(binding.get("pulse_seconds"))
    registry, _ = _registries(hass)
    unique_id = binding.get("unique_id")
    if not isinstance(unique_id, str) or not _UNIQUE_ID.fullmatch(unique_id):
        raise ValueError("Identità Shelly non valida.")
    entity_id = registry.async_get_entity_id("switch", "shelly", unique_id)
    if entity_id is None:
        raise ValueError("Il relè associato non esiste più.")
    relay = resolve_entity(hass, entity_id)
    if any(binding.get(key) != getattr(relay, key) for key in
           ("unique_id", "device_id", "config_entry_id", "channel", "model")):
        raise ValueError("Il dispositivo associato è cambiato: configura nuovamente il varco.")
    return relay


async def _rpc(relay: ResolvedRelay, method: str, params: dict):
    try:
        async with asyncio.timeout(8):
            result = await relay.rpc.call_rpc(method, params)
    except Exception as exc:
        # Native exceptions may contain network addresses or authentication data.
        raise ValueError("Comunicazione Shelly non riuscita. Nessun tentativo automatico.") from exc
    if not isinstance(result, Mapping):
        raise ValueError("Risposta Shelly non valida.")
    return result


async def _off(relay):
    status = await _rpc(relay, "Switch.GetStatus", {"id": relay.channel})
    if status.get("id") != relay.channel or status.get("output") is not False:
        raise ValueError("L'uscita Shelly deve essere OFF prima di procedere.")


async def async_configure(hass, entity_id: str, seconds) -> tuple[dict, dict]:
    """Read, configure and verify only the door-pulse settings; never open."""
    desired = pulse_profile(seconds)
    relay = resolve_entity(hass, entity_id)
    await _off(relay)
    before = await _rpc(relay, "Switch.GetConfig", {"id": relay.channel})
    if before.get("id") != relay.channel or any(k not in before for k in PROFILE_FIELDS):
        raise ValueError("Il firmware non espone le impostazioni richieste.")
    if not profile_matches(before, seconds):
        latest = resolve_entity(hass, entity_id)
        if latest != relay:
            raise ValueError("Associazione Shelly cambiata durante la configurazione.")
        result = await _rpc(relay, "Switch.SetConfig", {"id": relay.channel, "config": desired})
        if result.get("restart_required") is True:
            raise ValueError("Il dispositivo richiede un riavvio: completa la verifica prima di aggiungere il varco.")
    after = await _rpc(relay, "Switch.GetConfig", {"id": relay.channel})
    if after.get("id") != relay.channel or not profile_matches(after, seconds):
        raise ValueError("Impostazioni Shelly non confermate: il varco resta inattivo.")
    await _off(relay)
    binding = binding_from_relay(relay, seconds)
    return binding, {k: before[k] for k in PROFILE_FIELDS}


async def async_validate(hass, binding: dict) -> ResolvedRelay:
    relay = resolve_binding(hass, binding)
    config = await _rpc(relay, "Switch.GetConfig", {"id": relay.channel})
    if config.get("id") != relay.channel or not profile_matches(config, binding["pulse_seconds"]):
        raise ValueError("Impostazioni Shelly cambiate: ripeti la configurazione del varco.")
    await _off(relay)
    if resolve_binding(hass, binding) != relay:
        raise ValueError("Associazione Shelly cambiata durante la verifica.")
    return relay


async def async_pulse(hass, binding: dict, *, before_command=None) -> None:
    """Exactly one ON request, with a device-local timer. Never retry on timeout."""
    relay = await async_validate(hass, binding)
    if before_command is not None and before_command() is not True:
        raise ValueError("Autorizzazione non più valida. Nessun comando inviato.")
    await _rpc(relay, "Switch.Set", {"id": relay.channel, "on": True,
                                    "toggle_after": pulse_seconds(binding["pulse_seconds"]),
                                    "tag": "cl_bb_manager"})


async def async_restore_profile(hass, binding, previous) -> None:
    """Rollback a failed storage transaction, only if our exact profile remains."""
    relay = await async_validate(hass, binding)
    await _rpc(relay, "Switch.SetConfig", {"id": relay.channel, "config": previous})


def available_relays(hass) -> list[dict]:
    registry, _ = _registries(hass)
    result = []
    for entry in registry.entities.values():
        if entry.platform != "shelly" or not entry.entity_id.startswith("switch."):
            continue
        try:
            relay = resolve_entity(hass, entry.entity_id)
        except ValueError:
            continue
        result.append({"entity_id": relay.entity_id, "name": entry.name or
                       entry.original_name or relay.entity_id, "model": relay.model})
    return sorted(result, key=lambda item: item["name"].casefold())
