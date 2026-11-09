"""Fresh-install and real WS/HTTP workflows with HA-shaped fakes, no devices."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
from types import MappingProxyType, ModuleType, SimpleNamespace

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

import test_shelly_gate as native
from test_pin_form_regression import FormParser

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/cl_bb_manager'


class Store:
    def __init__(self,hass,*args):self.hass=hass
    async def async_load(self):return deepcopy(getattr(self.hass,'persisted',None))
    async def async_save(self,data):self.hass.persisted=deepcopy(data)


class Connection:
    def __init__(self,user_id='installer',admin=True,active=True):
        self.user=SimpleNamespace(id=user_id,is_admin=admin,is_active=active)
        self.result=None;self.errors=[]
    def send_result(self,id,result):self.result=result
    def send_error(self,id,code,message):self.errors.append((code,message))


def harness(monkeypatch):
    registered={};panels=[]
    ws=ModuleType('homeassistant.components.websocket_api')
    ws.websocket_command=lambda schema:lambda fn:fn
    ws.async_response=lambda fn:fn
    ws.async_register_command=lambda h,fn:registered.__setitem__(fn.__name__,fn)
    frontend=ModuleType('homeassistant.components.frontend')
    frontend.async_remove_panel=lambda *a,**kw:None
    panel=ModuleType('homeassistant.components.panel_custom')
    async def register_panel(hass,**kwargs):panels.append(kwargs)
    panel.async_register_panel=register_panel
    http=ModuleType('homeassistant.components.http')
    http.HomeAssistantView=type('HomeAssistantView',(),{})
    http.StaticPathConfig=lambda *args:args
    core=ModuleType('homeassistant.core');core.HomeAssistant=object
    storage=ModuleType('homeassistant.helpers.storage');storage.Store=Store
    components=ModuleType('homeassistant.components')
    components.websocket_api=ws;components.frontend=frontend;components.panel_custom=panel
    monkeypatch.setitem(sys.modules,'homeassistant.components',components)
    for mod in (ws,frontend,panel,http,core,storage):monkeypatch.setitem(sys.modules,mod.__name__,mod)
    package='_cl_bb_product_runtime'
    for key in list(sys.modules):
        if key==package or key.startswith(package+'.'):monkeypatch.delitem(sys.modules,key)
    spec=importlib.util.spec_from_file_location(package,ROOT/'__init__.py',submodule_search_locations=[str(ROOT)])
    module=importlib.util.module_from_spec(spec);monkeypatch.setitem(sys.modules,package,module);spec.loader.exec_module(module)
    _,hass,rpc,registry,device,shelly_entry=native.fixture(monkeypatch)
    hass.data={};hass.persisted=None
    views=[]
    async def static_paths(paths):pass
    hass.http=SimpleNamespace(register_view=views.append,async_register_static_paths=static_paths)
    async def executor(func,*args):return func(*args)
    hass.async_add_executor_job=executor
    hass.config=SimpleNamespace(external_url='https://newhotel.example.org')
    async def forbidden_service(*args,**kwargs):raise AssertionError('Manual HA scripts must not be needed')
    hass.services=SimpleNamespace(async_call=forbidden_service)
    # The native adapter imported inside this package sees the same HA registry.
    product_driver=importlib.import_module(package+'.shelly_gate')
    monkeypatch.setattr(product_driver,'_registries',lambda h:(registry,SimpleNamespace(async_get=lambda id:device if id=='device' else None)))
    entry=SimpleNamespace(data=MappingProxyType({'structure_name':'A newly installed property'}),
                          options=MappingProxyType({'operator_user_ids':['selected-operator']}))
    return module,hass,entry,registered,views,panels,rpc,registry


async def call(handlers,handler_name,hass,connection,**data):
    connection.result=None;connection.errors=[]
    await handlers[handler_name](hass,connection,{'id':1,**data})
    return connection.result


@pytest.mark.filterwarnings('ignore:It is recommended to use web.AppKey instances for keys')
def test_empty_install_setup_booking_physical_http_and_restart(monkeypatch):
    async def run():
        module,hass,entry,handlers,views,panels,rpc,registry=harness(monkeypatch)
        assert await module.async_setup_entry(hass,entry) is True
        manager=hass.data['cl_bb_manager']['manager']
        assert manager.data['gates']==[]
        assert manager.data['bookings']==[]
        assert len(manager.data['properties'])==1
        assert panels[-1]['require_admin'] is False
        assert panels[-1]['sidebar_title']=='CL B&B Manager'
        assert [view.url for view in views]==['/api/cl_bb_manager/physical/{token}']
        assert not any(name in handlers for name in ('demo_qr','public_pilot_qr','permanent_pilot_qr','demo_check_pin','add_gate'))
        admin=Connection();operator=Connection('selected-operator',False)
        outsider=Connection('not-selected',False)
        await call(handlers,'get_list',hass,outsider)
        assert outsider.errors[0][0]=='unauthorized'
        await call(handlers,'get_list',hass,operator)
        assert operator.result['role']=='operator'
        await call(handlers,'shelly_relays',hass,operator)
        assert operator.errors[0][0]=='unauthorized'
        await call(handlers,'add_shelly_gate',hass,operator,name='Entrance',entity_id=native.ENTITY,pulse_seconds=2,kind='shared',confirm=True)
        assert operator.errors[0][0]=='unauthorized' and rpc.calls==[]
        await call(handlers,'add_shelly_gate',hass,admin,name='Entrance',entity_id=native.ENTITY,pulse_seconds=2,kind='shared',confirm=True)
        assert not admin.errors
        gate=manager.data['gates'][0];token=gate['physical_token']
        assert not gate['enabled'] and not gate['physical_enabled']
        assert not any(method=='Switch.Set' for method,_ in rpc.calls)
        # Reading/printing an already prepared QR never rotates it or arms.
        await call(handlers,'physical_qr',hass,operator,gate_id=gate['id'])
        assert not operator.errors and operator.result['url'].endswith(token)
        assert gate['physical_token']==token and not gate['physical_enabled']
        await call(handlers,'arm_physical_gate',hass,admin,gate_id=gate['id'],confirm=True,confirm_wiring=False)
        assert admin.errors and not gate['physical_enabled']
        await call(handlers,'arm_physical_gate',hass,admin,gate_id=gate['id'],confirm=True,confirm_wiring=True)
        assert not admin.errors and gate['physical_enabled']
        assert manager.data['bookings']==[]  # No trial booking needed for setup.
        now=datetime.now(timezone.utc)
        await call(handlers,'add_booking',hass,operator,room='Room A',guest_name='Guest',
                   start=(now-timedelta(minutes=1)).isoformat(),end=(now+timedelta(days=1)).isoformat(),gate_ids=[gate['id']])
        assert not operator.errors
        generated_pin=operator.result['pin_once']
        booking=manager.data['bookings'][0]
        assert booking['physical_gate_ids']==[gate['id']]
        assert generated_pin not in str(manager.data)
        await call(handlers,'get_list',hass,operator)
        assert 'entity_id' not in operator.result['gates'][0]
        assert 'hardware_candidate' not in operator.result['gates'][0]
        assert operator.result['events']==[]
        view=views[0];app=web.Application();app['hass']=hass
        async def endpoint(request):
            return await (view.get if request.method=='GET' else view.post)(request,request.match_info['token'])
        app.router.add_route('GET',view.url,endpoint);app.router.add_route('POST',view.url,endpoint)
        path='/api/cl_bb_manager/physical/'+token
        async with TestClient(TestServer(app)) as client:
            headers={'Host':'newhotel.example.org'}
            first=await client.get(path,headers=headers)
            assert first.status==200 and first.headers['Referrer-Policy']=='strict-origin'
            page=await first.text();csrf=FormParser(page).nonce
            assert not any(text in page.lower() for text in ('demo','pilota','temporaneo','virtuale'))
            payload={'pin':generated_pin,'form_csrf':csrf}
            headers.update(Origin='https://newhotel.example.org',**{'Sec-Fetch-Site':'same-origin'})
            response=await client.post(path,data=payload,headers=headers)
            assert response.status==200
            replay=await client.post(path,data=payload,headers=headers)
            assert replay.status==403
            assert sum(method=='Switch.Set' for method,_ in rpc.calls)==1
        # A reload/restored store keeps QR and grants; never sends an ON.
        rpc.output=False
        before=deepcopy(manager.data)
        await module.async_unload_entry(hass,entry)
        await module.async_setup_entry(hass,entry)
        restored=hass.data['cl_bb_manager']['manager']
        assert restored.data==before
        assert restored.data['gates'][0]['physical_token']==token
        assert sum(method=='Switch.Set' for method,_ in rpc.calls)==1
    asyncio.run(run())


def test_live_operator_revocation_inactive_user_and_immutable_options(monkeypatch):
    async def run():
        module,hass,entry,handlers,*_=harness(monkeypatch)
        await module.async_setup_entry(hass,entry)
        selected=Connection('selected-operator',False)
        await call(handlers,'get_list',hass,selected)
        assert not selected.errors and selected.result['role']=='operator'
        entry.options=MappingProxyType({'operator_user_ids':[]})
        await call(handlers,'get_list',hass,selected)
        assert selected.errors[0][0]=='unauthorized'
        entry.options=MappingProxyType({'operator_user_ids':['selected-operator']})
        selected.user.is_active=False
        await call(handlers,'get_list',hass,selected)
        assert selected.errors[0][0]=='unauthorized'
        await call(handlers,'access_status',hass,selected)
        assert selected.result=={'authorized':False,'role':None}
    asyncio.run(run())


def test_native_rename_keeps_qr_booking_grants_and_blocks_replacement(monkeypatch):
    async def run():
        module,hass,entry,handlers,views,panels,rpc,registry=harness(monkeypatch)
        await module.async_setup_entry(hass,entry)
        manager=hass.data['cl_bb_manager']['manager'];admin=Connection()
        await call(handlers,'add_shelly_gate',hass,admin,name='Entrance',entity_id=native.ENTITY,pulse_seconds=2,kind='shared',confirm=True)
        gate=manager.data['gates'][0];token=gate['physical_token']
        await call(handlers,'arm_physical_gate',hass,admin,gate_id=gate['id'],confirm=True,confirm_wiring=True)
        now=datetime.now(timezone.utc)
        await call(handlers,'add_booking',hass,admin,room='A',guest_name='',start=now.isoformat(),end=(now+timedelta(days=1)).isoformat(),gate_ids=[gate['id']])
        grants=deepcopy(manager.data['bookings'][0]['physical_gate_ids'])
        renamed='switch.renamed_entrance'
        record=registry.entities.pop(native.ENTITY);record.entity_id=renamed
        registry.entities[renamed]=record;hass.states[renamed]=hass.states.pop(native.ENTITY)
        await call(handlers,'get_list',hass,admin)
        assert admin.result['gates'][0]['entity_id']==renamed
        await call(handlers,'update_gate',hass,admin,gate_id=gate['id'],name='Renamed entrance',entity_id=renamed,action='switch.turn_on',kind='shared',enabled=True)
        assert not admin.errors and gate['entity_id']==renamed
        assert gate['physical_token']==token and gate['physical_enabled']
        assert manager.data['bookings'][0]['physical_gate_ids']==grants
        # A different state/registry identity is never accepted as a harmless rename.
        hass.states['switch.unrelated']=SimpleNamespace(state='off')
        await call(handlers,'update_gate',hass,admin,gate_id=gate['id'],name='Replacement',entity_id='switch.unrelated',action='switch.turn_on',kind='shared',enabled=True)
        assert admin.errors and gate['entity_id']==renamed
        assert gate['physical_token']==token
        assert not any(method=='Switch.Set' for method,_ in rpc.calls)
    asyncio.run(run())


def test_failed_arm_save_stays_disabled_and_revoked_native_qr_can_be_reprepared(monkeypatch):
    async def run():
        module,hass,entry,handlers,views,panels,rpc,registry=harness(monkeypatch)
        await module.async_setup_entry(hass,entry)
        manager=hass.data['cl_bb_manager']['manager'];admin=Connection()
        await call(handlers,'add_shelly_gate',hass,admin,name='Entrance',entity_id=native.ENTITY,pulse_seconds=2,kind='shared',confirm=True)
        gate=manager.data['gates'][0];before=deepcopy(manager.data)
        saved=manager.async_save
        async def fail():raise OSError('Storage unavailable')
        manager.async_save=fail
        await call(handlers,'arm_physical_gate',hass,admin,gate_id=gate['id'],confirm=True,confirm_wiring=True)
        assert admin.errors and manager.data==before
        assert not gate['physical_enabled'] and not gate['enabled']
        manager.async_save=saved
        await call(handlers,'emergency_disable_physical',hass,admin,confirm=True)
        assert 'physical_token' not in gate
        await call(handlers,'prepare_physical_qr',hass,admin,gate_id=gate['id'],confirm=True)
        assert not admin.errors and 'physical_token' in gate
        assert not gate['physical_enabled'] and not gate['enabled']
        assert not any(method=='Switch.Set' for method,_ in rpc.calls)
    asyncio.run(run())
