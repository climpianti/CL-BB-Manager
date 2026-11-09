"""Typed Home Assistant door actuators; no arbitrary targets or guest services."""
from __future__ import annotations

import asyncio
from copy import deepcopy

from .shelly_gate import pulse_seconds

ACTIONS = {
    'lock.unlock': ('lock', 'Sblocca serratura'),
    'lock.open': ('lock', 'Apri scrocco'),
    'switch.turn_on': ('switch', 'Impulso relè'),
    'button.press': ('button', 'Premi pulsante'),
    'input_button.press': ('input_button', 'Premi pulsante aiutante'),
    'script.turn_on': ('script', 'Esegui script apriporta'),
    'cover.open_cover': ('cover', 'Apri cancello / portone'),
}
SWITCH_MODES = ('ha_pulse', 'device_pulse')
_delay = asyncio.sleep


def _registry(hass):
    from homeassistant.helpers import entity_registry as er
    return er.async_get(hass)


def _identity(record, entity_id):
    if record is None:
        return {'registered': False, 'entity_id': entity_id}
    return {'registered': True, 'registry_id': record.id,
            'unique_id': record.unique_id, 'platform': record.platform,
            'config_entry_id': record.config_entry_id, 'device_id': record.device_id}


def _check(hass, entity_id, action, *, require_idle=True):
    if action not in ACTIONS or not entity_id.startswith(ACTIONS[action][0] + '.'):
        raise ValueError('Entità e azione apriporta non corrispondenti.')
    state = hass.states.get(entity_id)
    attrs = getattr(state, 'attributes', {}) or {}
    domain, service = action.split('.')
    if state is None or state.state == 'unavailable':
        raise ValueError('Entità apriporta non disponibile.')
    if not hass.services.has_service(domain, service):
        raise ValueError('Azione non disponibile in Home Assistant.')
    if domain == 'switch' and not hass.services.has_service('switch', 'turn_off'):
        raise ValueError('Il relè non dispone del comando di spegnimento.')
    if domain == 'lock':
        if state.state not in ('locked', 'unlocked', 'open'):
            raise ValueError('Serratura non pronta o in movimento.')
        if attrs.get('code_format'):
            raise ValueError('La serratura richiede un codice dispositivo: usa uno script locale dedicato. Il codice della prenotazione non viene inoltrato alla serratura.')
    if action in ('lock.open', 'cover.open_cover'):
        features = attrs.get('supported_features', 0)
        if not isinstance(features, int) or isinstance(features, bool) or not features & 1:
            raise ValueError('Questa entità non supporta l’azione di apertura selezionata.')
    if domain == 'cover' and state.state not in ('open', 'closed'):
        raise ValueError('Cancello / portone non pronto o in movimento.')
    if domain == 'script' and state.state != 'off':
        raise ValueError('Lo script deve essere inattivo prima di procedere.')
    if domain == 'switch' and (state.state not in ('on', 'off') or (require_idle and state.state != 'off')):
        raise ValueError('Il relè deve essere OFF prima di procedere.')
    registry = _registry(hass)
    record = registry.async_get(entity_id)
    if record is not None and record.disabled_by is not None:
        raise ValueError('Entità disabilitata nel registro Home Assistant.')
    return record


def make_binding(hass, entity_id, action, *, switch_mode='ha_pulse', seconds=2,
                 confirm_device_pulse=False):
    record = _check(hass, entity_id, action)
    if switch_mode not in SWITCH_MODES:
        raise ValueError('Modalità impulso non valida.')
    binding = {'provider': 'ha_entity', 'configured': True, 'entity_id': entity_id,
               'action': action, 'identity': _identity(record, entity_id)}
    if action == 'switch.turn_on':
        if switch_mode == 'device_pulse' and confirm_device_pulse is not True:
            raise ValueError('Conferma lo spegnimento automatico già configurato sul dispositivo.')
        binding.update(switch_mode=switch_mode, pulse_seconds=pulse_seconds(seconds))
    return binding


def resolve_binding(hass, binding, *, require_idle=True):
    if not isinstance(binding, dict) or binding.get('provider') != 'ha_entity' or binding.get('configured') is not True:
        raise ValueError('Associazione apriporta non valida.')
    identity = binding.get('identity')
    if not isinstance(identity, dict):
        raise ValueError('Identità apriporta non valida.')
    entity_id = binding.get('entity_id')
    registry = _registry(hass)
    if identity.get('registered') is True:
        record = next((r for r in registry.entities.values() if r.id == identity.get('registry_id')), None)
        if record is None:
            raise ValueError('Entità associata rimossa dal registro.')
        entity_id = record.entity_id
    if not isinstance(entity_id, str):
        raise ValueError('Entità apriporta non valida.')
    record = _check(hass, entity_id, binding.get('action'), require_idle=require_idle)
    if _identity(record, entity_id) != identity:
        raise ValueError('Il dispositivo associato è cambiato: ripeti la configurazione del varco.')
    if binding['action'] == 'switch.turn_on':
        if binding.get('switch_mode') not in SWITCH_MODES:
            raise ValueError('Modalità impulso non valida.')
        pulse_seconds(binding.get('pulse_seconds'))
    return entity_id


def available_entities(hass):
    states = hass.states.values() if isinstance(hass.states, dict) else hass.states.async_all()
    result = []
    for state in states:
        entity_id = getattr(state, 'entity_id', '')
        actions = []
        for action, (domain, label) in ACTIONS.items():
            if entity_id.startswith(domain + '.'):
                try:
                    _check(hass, entity_id, action)
                except (ValueError, TypeError):
                    continue
                actions.append({'action': action, 'label': label})
        if actions:
            attrs = getattr(state, 'attributes', {}) or {}
            result.append({'entity_id': entity_id, 'name': attrs.get('friendly_name', entity_id), 'actions': actions})
    return sorted(result, key=lambda e: e['name'].casefold())


async def _service(hass, domain, service, entity_id):
    try:
        async with asyncio.timeout(10):
            await hass.services.async_call(domain, service, {'entity_id': entity_id}, blocking=True)
    except Exception as exc:
        raise ValueError('Comando Home Assistant non confermato. Nessun nuovo tentativo automatico di apertura.') from exc


async def async_reset_pending(manager, key=None):
    """Send only OFF for persisted interrupted pulses; never send an ON on reload."""
    pending = manager.data.get('pending_entity_pulses', {})
    if not isinstance(pending, dict):
        raise ValueError('Registro impulsi non valido.')
    for pulse_key, binding in list(pending.items()):
        if key is not None and key != pulse_key:
            continue
        try:
            if binding.get('action') != 'switch.turn_on' or binding.get('switch_mode') != 'ha_pulse':
                raise ValueError('Impulso pendente non valido.')
            entity_id = resolve_binding(manager.hass, binding, require_idle=False)
            await _service(manager.hass, 'switch', 'turn_off', entity_id)
            if manager.hass.states.get(entity_id).state != 'off':
                raise ValueError('Spegnimento non confermato dallo stato del relè.')
            del pending[pulse_key]
            await manager.async_save()
        except Exception:
            # Keep the persisted recovery intent and block this actuator.
            pending[pulse_key] = binding
    return key is None or key not in pending


async def async_command(manager, gate, *, before_command):
    binding = gate['entity_binding'];hass = manager.hass
    if gate['id'] in manager.data.get('pending_entity_pulses', {}):
        await async_reset_pending(manager, gate['id'])
        if gate['id'] in manager.data.get('pending_entity_pulses', {}):
            raise ValueError('Impulso precedente da ripristinare: varco bloccato.')
        # Require a fresh request after restoring a previous uncertain pulse.
        raise ValueError('Impulso precedente ripristinato. Ripeti la richiesta di accesso.')
    entity_id = resolve_binding(hass, binding)
    if before_command() is not True:
        raise ValueError('Autorizzazione non più valida.')
    domain, service = binding['action'].split('.')
    if binding['action'] != 'switch.turn_on' or binding['switch_mode'] == 'device_pulse':
        await _service(hass, domain, service, entity_id)
        return
    # Write recovery intent before energizing a generic relay. A hardware timer
    # remains preferable: HA cannot de-energize it during an HA/network outage.
    pending = manager.data.setdefault('pending_entity_pulses', {})
    pending[gate['id']] = deepcopy(binding)
    try:
        await manager.async_save()
    except Exception as exc:
        pending.pop(gate['id'], None)
        raise ValueError('Impulso non avviato: salvataggio non riuscito.') from exc
    try:
        if before_command() is not True:
            raise ValueError('Autorizzazione non più valida.')
        await _service(hass, domain, service, entity_id)
        await _delay(binding['pulse_seconds'])
    finally:
        # Cleanup also runs on timeout/cancellation. Never retry ON.
        await async_reset_pending(manager, gate['id'])
        if gate['id'] in pending:
            raise ValueError('Spegnimento non confermato: varco bloccato per ripristino.')


async def async_recover_on_lifecycle(manager):
    """Bound startup/unload work; unprocessed intents remain blocked for admin recovery."""
    try:
        async with asyncio.timeout(12):
            await async_reset_pending(manager)
    except TimeoutError:
        pass
