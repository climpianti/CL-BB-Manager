"""Real provisioning/controller code against native-HA-shaped registry/RPC fakes."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import importlib
from pathlib import Path
import sys
from types import MappingProxyType, ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/cl_bb_manager'
PKG = '_cl_bb_shelly_test'
pkg = ModuleType(PKG); pkg.__path__ = [str(ROOT)]; sys.modules.setdefault(PKG, pkg)
driver = importlib.import_module(PKG + '.shelly_gate')
setup = importlib.import_module(PKG + '.gate_setup')
models = importlib.import_module(PKG + '.models')
scope = importlib.import_module(PKG + '.property_scope')
policy = importlib.import_module(PKG + '.physical_policy')

MAC = 'AABBCCDDEEFF'
ENTITY = 'switch.another_hotel_entrance'
UNIQUE = MAC + '-switch:0'


class NativeRpc:
    mac = MAC
    def __init__(self):
        self.config = dict(id=0, initial_state='restore_last', auto_on=False,
                           auto_off=False, auto_off_delay=60, in_mode='momentary')
        self.output = False
        self.calls = []
        self.fail_method = None
        self.ignore_config = False

    async def call_rpc(self, method, params):
        self.calls.append((method, deepcopy(params)))
        if self.fail_method == method:
            raise TimeoutError('private network detail must not reach the UI')
        if method == 'Switch.GetStatus':
            return {'id': 0, 'output': self.output}
        if method == 'Switch.GetConfig':
            return deepcopy(self.config)
        if method == 'Switch.SetConfig':
            if not self.ignore_config:
                self.config.update(params['config'])
            return {'restart_required': False}
        if method == 'Switch.Set':
            self.output = params['on']
            return {'was_on': False}
        raise AssertionError('Unexpected RPC: ' + method)


class Registry:
    def __init__(self):
        self.entities = {ENTITY: SimpleNamespace(entity_id=ENTITY, platform='shelly',
            unique_id=UNIQUE, config_entry_id='native-shelly', device_id='device',
            disabled_by=None, name='Another hotel entrance', original_name=None)}

    def async_get(self, entity):
        return self.entities.get(entity)

    def async_get_entity_id(self, domain, platform, unique_id):
        return next((e.entity_id for e in self.entities.values()
                     if e.platform == platform and e.unique_id == unique_id), None)


class Manager:
    def __init__(self, hass):
        self.hass = hass
        self.property_id = scope.new_property('An entirely different property')['id']
        self.data = {'gates': [], 'bookings': [], 'events': [], 'access_history': []}
        self.lock = asyncio.Lock()
        self.physical_forms = {}
        self.entry = SimpleNamespace(options=MappingProxyType({'public_access_enabled': True}))
        self.saved = None
        self.fail_save = False

    async def async_save(self):
        if self.fail_save:
            raise OSError('Storage is unavailable')
        self.saved = deepcopy(self.data)

    def audit(self, event, details=''):
        self.data['events'].append({'event': event, 'details': details,
            'property_id': self.property_id, 'at': datetime.now(timezone.utc).isoformat()})


def fixture(monkeypatch):
    rpc = NativeRpc(); registry = Registry()
    device = SimpleNamespace(model='Shelly 1 Mini Gen3')
    entry = SimpleNamespace(domain='shelly', unique_id=MAC,
        runtime_data=SimpleNamespace(rpc=SimpleNamespace(connected=True, device=rpc)))
    hass = SimpleNamespace(states={ENTITY: SimpleNamespace(state='off')},
        config_entries=SimpleNamespace(async_get_entry=lambda id: entry if id=='native-shelly' else None),
        config=SimpleNamespace(external_url='https://newhotel.example.org'))
    devices = SimpleNamespace(async_get=lambda id: device if id == 'device' else None)
    monkeypatch.setattr(driver, '_registries', lambda h: (registry, devices))
    manager = Manager(hass)
    hass.data = {'cl_bb_manager': {'manager': manager}}
    return manager, hass, rpc, registry, device, entry


def run(coro):
    return asyncio.run(coro)


def provision(manager):
    return setup.async_add_shelly_gate(manager, name='Entrance', entity_id=ENTITY,
                                      seconds=2, kind='shared')


def test_add_gate_configures_and_reads_back_profile_without_opening(monkeypatch):
    manager, hass, rpc, *_ = fixture(monkeypatch)
    gate = run(provision(manager))
    assert rpc.config['auto_off'] is True
    assert rpc.config['auto_off_delay'] == 2
    assert rpc.config['initial_state'] == 'off'
    assert rpc.config['in_mode'] == 'momentary'  # Local input behavior is preserved.
    assert not any(method == 'Switch.Set' for method, _ in rpc.calls)
    assert gate['enabled'] is False and gate['physical_enabled'] is False
    assert len(gate['physical_token']) >= 40
    assert gate['physical_token'] != gate['token']
    assert gate['property_id'] == manager.property_id
    assert 'hardware_candidate' not in gate
    assert gate['shelly_binding']['unique_id'] == UNIQUE
    assert manager.saved['gates'][0]['physical_token'] == gate['physical_token']
    assert 'password' not in str(gate) and 'host' not in str(gate)


def test_configured_gate_uses_one_local_timed_pulse_and_no_script(monkeypatch):
    manager, hass, rpc, *_ = fixture(monkeypatch)
    gate = run(provision(manager))
    gate.update(enabled=True, physical_enabled=True)
    manager.data['physical_access_enabled'] = True
    assert policy.physical_target(manager, gate, hass, token=gate['physical_token']) == ENTITY
    run(driver.async_pulse(hass, gate['shelly_binding']))
    commands = [params for method, params in rpc.calls if method == 'Switch.Set']
    assert commands == [{'id': 0, 'on': True, 'toggle_after': 2.0, 'tag': 'cl_bb_manager'}]


def test_entity_rename_keeps_stable_mapping_and_entity_replacement_fails(monkeypatch):
    manager, hass, rpc, registry, *_ = fixture(monkeypatch)
    gate = run(provision(manager))
    record = registry.entities.pop(ENTITY); record.entity_id='switch.renamed'
    registry.entities[record.entity_id]=record
    hass.states['switch.renamed']=hass.states.pop(ENTITY)
    assert driver.resolve_binding(hass, gate['shelly_binding']).entity_id == 'switch.renamed'
    record.unique_id = '112233445566-switch:0'
    with pytest.raises(ValueError):
        run(driver.async_pulse(hass, gate['shelly_binding']))
    assert not any(method == 'Switch.Set' for method, _ in rpc.calls)


@pytest.mark.parametrize('failure', ['model','platform','disabled','identity','offline','on'])
def test_non_supported_or_uncertain_device_is_never_configured(monkeypatch, failure):
    manager, hass, rpc, registry, device, entry = fixture(monkeypatch)
    if failure=='model':device.model='Unrelated relay'
    if failure=='platform':registry.entities[ENTITY].platform='mqtt'
    if failure=='disabled':registry.entities[ENTITY].disabled_by='user'
    if failure=='identity':rpc.mac='001122334455'
    if failure=='offline':entry.runtime_data.rpc.connected=False
    if failure=='on':rpc.output=True
    with pytest.raises(ValueError):run(provision(manager))
    assert manager.data['gates']==[]
    assert not any(method in ('Switch.Set','Switch.SetConfig') for method,_ in rpc.calls)


@pytest.mark.parametrize('value', [True,False,0,.1,6,float('nan'),float('inf'),'2'])
def test_invalid_pulse_duration_never_writes(monkeypatch, value):
    manager, _, rpc, *_ = fixture(monkeypatch)
    with pytest.raises(ValueError):run(setup.async_add_shelly_gate(manager,
        name='Entrance',entity_id=ENTITY,seconds=value))
    assert rpc.calls==[]


def test_configuration_readback_failure_never_creates_active_gate(monkeypatch):
    manager, _, rpc, *_ = fixture(monkeypatch);rpc.ignore_config=True
    with pytest.raises(ValueError, match='non confermate'):run(provision(manager))
    assert manager.data['gates']==[]
    assert not any(method=='Switch.Set' for method,_ in rpc.calls)


def test_storage_failure_rolls_back_config_and_never_leaves_a_gate(monkeypatch):
    manager, _, rpc, *_ = fixture(monkeypatch)
    before=deepcopy(rpc.config);manager.fail_save=True
    with pytest.raises(ValueError,match='Salvataggio'):run(provision(manager))
    assert rpc.config==before
    assert manager.data['gates']==[]
    assert not any(method=='Switch.Set' for method,_ in rpc.calls)


def test_duplicate_channel_does_not_reconfigure_or_rotate_credentials(monkeypatch):
    manager, _, rpc, *_ = fixture(monkeypatch)
    gate=run(provision(manager));before=deepcopy(gate);calls=len(rpc.calls)
    with pytest.raises(ValueError,match='già associato'):run(provision(manager))
    assert gate==before and len(rpc.calls)==calls


def test_changed_hardware_timer_blocks_opening(monkeypatch):
    manager, hass, rpc, *_ = fixture(monkeypatch)
    gate=run(provision(manager));rpc.config['auto_off']=False
    with pytest.raises(ValueError,match='cambiate'):run(driver.async_pulse(hass,gate['shelly_binding']))
    assert not any(method=='Switch.Set' for method,_ in rpc.calls)


def test_uncertain_on_request_is_not_retried_and_error_has_no_network_detail(monkeypatch):
    manager, hass, rpc, *_ = fixture(monkeypatch)
    gate=run(provision(manager));rpc.fail_method='Switch.Set'
    with pytest.raises(ValueError) as exc:run(driver.async_pulse(hass,gate['shelly_binding']))
    assert 'private network' not in str(exc.value)
    assert sum(method=='Switch.Set' for method,_ in rpc.calls)==1


def test_booking_guard_is_evaluated_after_profile_reads_and_before_command(monkeypatch):
    manager,hass,rpc,*_=fixture(monkeypatch)
    gate=run(provision(manager));before=len(rpc.calls)
    checks=[]
    def expired():
        checks.append(len(rpc.calls))
        return False
    with pytest.raises(ValueError,match='Autorizzazione'):
        run(driver.async_pulse(hass,gate['shelly_binding'],before_command=expired))
    assert checks and checks[0]>before
    assert not any(method=='Switch.Set' for method,_ in rpc.calls)
