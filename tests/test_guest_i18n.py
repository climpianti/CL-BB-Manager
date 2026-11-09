"""Guest language negotiation and actual GET/POST pages with fake actuators."""
import asyncio
from html import unescape

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

import test_demo_http as base
from test_pin_form_regression import FormParser, setup_gate, HOST, ORIGIN
import test_physical_path as fixture

locale=base.load_module('guest_i18n')
physical=fixture.physical_http
pytestmark=pytest.mark.filterwarnings('ignore:It is recommended to use web.AppKey instances for keys')


@pytest.mark.parametrize('header,expected',[
    (None,'it'),('','it'),('  ','it'),('en','en'),('it','it'),
    ('en-US,en;q=0.9,it;q=0.7','en'),('it-IT,it;q=0.9,en;q=0.8','it'),
    ('en;q=0.3,it;q=0.9','it'),('it;q=0.3,en;q=0.9','en'),
    ('fr-FR,fr;q=0.9,it;q=0.7,en;q=0.5','it'),('fr,de;q=0.9','en'),
    ('EN-gb;Q=0.8,IT;q=0.5','en'),('en;q=0,it;q=0.6','it'),
    ('it;q=0,en;q=0.6','en'),('it;q=0,en;q=0','en'),
    ('en;q=0.5,it;q=0.5','en'),('it;q=0.5,en;q=0.5','it'),
    ('it;q=nan,en','en'),('en;q=1.1,it','it'),('en;q=-1,it','it'),
    ('en;q=0.1234,it','it'),('it;q=.8,en','en'),('*','en'),
    ('it;q=0.8;anything=1,en','en'),('<script>alert(1)</script>','en'),
    ('en\r\nX-Header: x,it','it'),('a'*10000,'en'),
])
def test_browser_language_quality_regions_fallback_and_invalid_input(header,expected):
    assert locale.browser_language(header)==expected


def test_catalogues_have_identical_keys_and_nonempty_copy():
    assert set(locale.COPY)=={'it','en'}
    assert set(locale.COPY['it'])==set(locale.COPY['en'])
    assert all(isinstance(s,str) and s.strip() for messages in locale.COPY.values() for s in messages.values())


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('door',['strada','scala'])
@pytest.mark.parametrize('scenario',['success','invalid_code','session','origin','too_many','cooldown','unavailable','not_found','bad_request'])
def test_localised_physical_http_pages_keep_security_status_and_dispatch(monkeypatch,language,door,scenario):
    async def run():
        manager,hass,gate,script=setup_gate(monkeypatch,door)
        app=web.Application();app['hass']=hass;view=physical.PhysicalGuestView()
        async def endpoint(request):
            return await (view.get if request.method=='GET' else view.post)(request,request.match_info['token'])
        app.router.add_route('GET',view.url,endpoint);app.router.add_route('POST',view.url,endpoint)
        path='/api/cl_bb_manager/physical/'+fixture.TOKEN
        async with TestClient(TestServer(app)) as client:
            headers={'Host':HOST,'Accept-Language':language+'-'+('GB' if language=='en' else 'IT')}
            response=await client.get(path,headers=headers)
            assert response.status==200
            body=await response.text();parser=FormParser(body)
            assert '<html lang=\''+language+'\'>' in body
            assert locale.text(language,'prompt') in unescape(body)
            assert locale.text(language,'code_label') in unescape(body)
            assert gate['name'] in body  # User-configured names are not translated.
            assert response.headers['Content-Language']==language
            assert response.headers['Vary']=='Accept-Language'
            assert response.headers['Referrer-Policy']=='strict-origin'
            assert "script-src" not in response.headers['Content-Security-Policy']
            assert "default-src 'none'" in response.headers['Content-Security-Policy']
            assert '<script' not in body and hass.calls==[]
            payload={'pin':'12345678','form_csrf':parser.nonce}
            headers.update(Origin=ORIGIN,**{'Sec-Fetch-Site':'same-origin'})
            expected=403
            if scenario=='success':expected=200
            elif scenario=='invalid_code':payload['pin']='00000000'
            elif scenario=='session':manager.physical_forms.clear()
            elif scenario=='origin':headers['Origin']='https://foreign.example.org'
            elif scenario=='too_many':
                expected=429
                monkeypatch.setattr(physical,'charge_attempt',lambda *args:False)
            elif scenario=='cooldown':
                expected=429
                monkeypatch.setattr(physical,'take_cooldown',lambda *args:False)
            elif scenario=='unavailable':
                expected=503
                async def failed(*args,**kwargs):raise RuntimeError('private-device-secret')
                hass.services.async_call=failed
            elif scenario=='not_found':
                expected=404;gate['physical_enabled']=False
            elif scenario=='bad_request':
                expected=400;payload={'pin':'x'*300}
            response=await client.post(path,data=payload,headers=headers)
            body=await response.text()
            assert response.status==expected
            assert response.headers['Content-Language']==language
            assert 'no-store' in response.headers['Cache-Control']
            assert locale.text(language,scenario) in unescape(body)
            assert '<html lang=\''+language+'\'>' in body
            assert '12345678' not in body and fixture.TOKEN not in body and 'private-device-secret' not in body
            if scenario=='success':
                assert [call[2]['entity_id'] for call in hass.calls]==[script]
                assert locale.text(language,'success_title') in unescape(body)
                replay=await client.post(path,data=payload,headers=headers)
                assert replay.status==403 and len(hass.calls)==1
                assert locale.text(language,'session') in unescape(await replay.text())
            else:
                assert hass.calls==[]
                assert not FormParser(body).forms
                if scenario=='not_found':assert gate['name'] not in body
    asyncio.run(run())


def test_escaped_names_and_language_never_create_markup():
    response=base.demo_http._response('<img src=x onerror=alert(1)>',language='en',message_key='prompt',form_csrf='a'*43,physical=True)
    assert '<img src=x' not in response.text
    assert '&lt;img' in response.text
    assert 'Enter the access code' in response.text
    assert response.headers['Content-Language']=='en'
