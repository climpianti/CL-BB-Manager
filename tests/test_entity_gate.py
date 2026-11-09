"""Generic brand-independent door commands, against fake HA only."""
import asyncio
from enum import IntFlag
from copy import deepcopy
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest
import test_shelly_gate as native

PKG = '_cl_bb_entity_test'
pkg = ModuleType(PKG);pkg.__path__=[str(native.ROOT)];sys.modules.setdefault(PKG,pkg)
driver=importlib.import_module(PKG+'.entity_gate')
setup=importlib.import_module(PKG+'.gate_setup')
policy=importlib.import_module(PKG+'.physical_policy')

YALE='lock.porta_d_ingresso_yale_linus_l2_3'
SWITCH='switch.rele_altra_marca'
CASES=[(YALE,'lock.unlock','locked',1), (YALE,'lock.open','unlocked',1),
       (SWITCH,'switch.turn_on','off',0), ('button.apri_porta','button.press','unknown',0),
       ('input_button.apri_porta','input_button.press','unknown',0),
       ('script.apri_porta','script.turn_on','off',0), ('cover.cancello','cover.open_cover','closed',1)]


class Services:
    def __init__(self,hass):
        self.hass=hass;self.calls=[];self.fail=None;self.ignore_off=False
        self.allowed={tuple(a.split('.')) for a in driver.ACTIONS}|{('switch','turn_off')}
    def has_service(self,domain,action):return (domain,action) in self.allowed
    async def async_call(self,domain,service,data,blocking):
        assert blocking is True and set(data)=={'entity_id'}
        self.calls.append((domain,service,dict(data)))
        if domain=='switch':
            state=self.hass.states[data['entity_id']]
            if service=='turn_on':state.state='on'
            elif not self.ignore_off:state.state='off'
        if service==self.fail:raise TimeoutError('Private device credential must not be displayed')


def fixture(monkeypatch):
    manager,hass,rpc,registry,*_=native.fixture(monkeypatch)
    registry.entities[native.ENTITY].id="native-registry"
    for i,(entity,action,state,features) in enumerate(CASES):
        if entity in hass.states:continue
        hass.states[entity]=SimpleNamespace(entity_id=entity,state=state,attributes={'friendly_name':entity,'supported_features':features})
        registry.entities[entity]=SimpleNamespace(id='registry-'+str(i),entity_id=entity,unique_id='identity-'+str(i),platform='other-brand',config_entry_id='entry-'+str(i),device_id='device-'+str(i),disabled_by=None)
    hass.services=Services(hass)
    monkeypatch.setattr(driver,'_registry',lambda h:registry)
    durations=[]
    async def delay(seconds):durations.append(seconds)
    monkeypatch.setattr(driver,'_delay',delay)
    return manager,hass,registry,durations


async def add(manager,entity=YALE,action='lock.unlock',**options):
    return await setup.async_add_entity_gate(manager,name='Ingresso',entity_id=entity,action=action,**options)


@pytest.mark.parametrize('entity,action,state,features',CASES)
def test_typed_entities_can_be_configured_armed_and_commanded_with_no_setup_actuation(monkeypatch,entity,action,state,features):
    async def run():
        manager,hass,registry,durations=fixture(monkeypatch)
        gate=await add(manager,entity,action)
        assert hass.services.calls==[] and not gate['enabled'] and not gate['physical_enabled']
        assert gate['physical_token']!=gate['token']
        gate.update(enabled=True,physical_enabled=True);manager.data['physical_access_enabled']=True
        assert policy.physical_target(manager,gate,hass,token=gate['physical_token'])==entity
        await driver.async_command(manager,gate,before_command=lambda:True)
        expected=[tuple(action.split('.'))]
        if entity==SWITCH:
            expected.append(('switch','turn_off'))
            assert durations==[2] and hass.states[entity].state=='off'
            assert manager.data['pending_entity_pulses']=={}
        assert [(d,s) for d,s,_ in hass.services.calls]==expected
        assert all(call[2]=={'entity_id':entity} for call in hass.services.calls)
    asyncio.run(run())


@pytest.mark.parametrize('failure',['unavailable','jammed','feature','service','code','disabled','wrong_domain','arbitrary_service'])
def test_invalid_lock_configuration_fails_before_any_command(monkeypatch,failure):
    manager,hass,registry,_=fixture(monkeypatch)
    action='lock.open';entity=YALE
    if failure in ('unavailable','jammed'):hass.states[YALE].state=failure
    if failure=='feature':hass.states[YALE].attributes['supported_features']=0
    if failure=='service':hass.services.allowed.remove(('lock','open'))
    if failure=='code':hass.states[YALE].attributes['code_format']='^.*$'
    if failure=='disabled':registry.entities[YALE].disabled_by='user'
    if failure=='wrong_domain':action='script.turn_on'
    if failure=='arbitrary_service':action='homeassistant.restart'
    with pytest.raises(ValueError):asyncio.run(add(manager,entity,action))
    assert not hass.services.calls and not manager.data['gates']


def test_local_timer_confirmation_and_single_device_pulse(monkeypatch):
    async def run():
        manager,hass,registry,durations=fixture(monkeypatch)
        with pytest.raises(ValueError):await add(manager,SWITCH,'switch.turn_on',switch_mode='device_pulse')
        gate=await add(manager,SWITCH,'switch.turn_on',switch_mode='device_pulse',confirm_device_pulse=True)
        await driver.async_command(manager,gate,before_command=lambda:True)
        assert [(d,s) for d,s,_ in hass.services.calls]==[('switch','turn_on')]
        assert durations==[] and 'pending_entity_pulses' not in manager.data
    asyncio.run(run())


def test_entity_rename_preserves_binding_but_replacement_fails_closed(monkeypatch):
    manager,hass,registry,_=fixture(monkeypatch)
    gate=asyncio.run(add(manager));token=gate['physical_token']
    renamed='lock.ingresso_rinominato';record=registry.entities.pop(YALE);record.entity_id=renamed
    registry.entities[renamed]=record;hass.states[renamed]=hass.states.pop(YALE)
    assert driver.resolve_binding(hass,gate['entity_binding'])==renamed
    assert gate['physical_token']==token
    record.unique_id='replacement'
    with pytest.raises(ValueError):driver.resolve_binding(hass,gate['entity_binding'])
    assert hass.services.calls==[]


def test_duplicate_entity_and_storage_failure_do_not_create_second_gate(monkeypatch):
    async def run():
        manager,hass,registry,_=fixture(monkeypatch)
        gate=await add(manager)
        with pytest.raises(ValueError):await add(manager)
        assert len(manager.data['gates'])==1
        manager.fail_save=True
        with pytest.raises(ValueError):await add(manager,'button.apri_porta','button.press')
        assert manager.data['gates']==[gate] and hass.services.calls==[]
    asyncio.run(run())


def test_timeout_never_retries_on_but_still_sends_off(monkeypatch):
    async def run():
        manager,hass,registry,_=fixture(monkeypatch);gate=await add(manager,SWITCH,'switch.turn_on')
        hass.services.fail='turn_on'
        with pytest.raises(ValueError,match='Nessun nuovo tentativo') as error:await driver.async_command(manager,gate,before_command=lambda:True)
        assert 'credential' not in str(error.value)
        assert [s for d,s,data in hass.services.calls]==['turn_on','turn_off']
        assert manager.data['pending_entity_pulses']=={}
    asyncio.run(run())


def test_unconfirmed_off_persists_recovery_and_never_reopens_on_reload(monkeypatch):
    async def run():
        manager,hass,registry,_=fixture(monkeypatch);gate=await add(manager,SWITCH,'switch.turn_on')
        hass.services.ignore_off=True
        with pytest.raises(ValueError,match='Spegnimento'):await driver.async_command(manager,gate,before_command=lambda:True)
        assert gate['id'] in manager.saved['pending_entity_pulses']
        manager.data=deepcopy(manager.saved);hass.services.ignore_off=False;hass.services.calls=[]
        await driver.async_reset_pending(manager)
        assert [s for d,s,data in hass.services.calls]==['turn_off']
        assert manager.data['pending_entity_pulses']=={} and hass.states[SWITCH].state=='off'
    asyncio.run(run())


def test_recovery_never_controls_a_replaced_entity(monkeypatch):
    async def run():
        manager,hass,registry,_=fixture(monkeypatch);gate=await add(manager,SWITCH,'switch.turn_on')
        manager.data['pending_entity_pulses']={gate['id']:deepcopy(gate['entity_binding'])}
        registry.entities[SWITCH].unique_id='different'
        await driver.async_reset_pending(manager)
        assert manager.data['pending_entity_pulses'] and hass.services.calls==[]
    asyncio.run(run())


def test_booking_expiry_and_failed_precommand_save_never_energize_relay(monkeypatch):
    async def run():
        manager,hass,registry,_=fixture(monkeypatch);gate=await add(manager,SWITCH,'switch.turn_on')
        with pytest.raises(ValueError):await driver.async_command(manager,gate,before_command=lambda:False)
        manager.fail_save=True
        with pytest.raises(ValueError):await driver.async_command(manager,gate,before_command=lambda:True)
        assert not hass.services.calls and not manager.data.get('pending_entity_pulses')
    asyncio.run(run())


def test_cancelled_request_deenergizes_relay_and_clears_recovery(monkeypatch):
    async def run():
        manager,hass,registry,_=fixture(monkeypatch);gate=await add(manager,SWITCH,'switch.turn_on')
        waiting=asyncio.Event()
        async def block(seconds):waiting.set();await asyncio.Future()
        monkeypatch.setattr(driver,'_delay',block)
        task=asyncio.create_task(driver.async_command(manager,gate,before_command=lambda:True))
        await asyncio.wait_for(waiting.wait(),1);task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert [s for d,s,data in hass.services.calls]==['turn_on','turn_off']
        assert not manager.data['pending_entity_pulses']
    asyncio.run(run())


def test_home_assistant_intflag_features_support_open_without_accepting_boolean(monkeypatch):
    class LockFeature(IntFlag):
        OPEN=1
    manager,hass,registry,_=fixture(monkeypatch)
    hass.states[YALE].attributes['supported_features']=LockFeature.OPEN
    gate=asyncio.run(add(manager,YALE,'lock.open'))
    assert driver.resolve_binding(hass,gate['entity_binding'])==YALE
    hass.states[YALE].attributes['supported_features']=True
    with pytest.raises(ValueError):driver.resolve_binding(hass,gate['entity_binding'])
