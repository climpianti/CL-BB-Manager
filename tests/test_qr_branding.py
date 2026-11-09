"""Logo upload, persistence and real machine decoding, without live QR tokens."""
import asyncio
import base64
from contextlib import contextmanager
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
import pytest
import zxingcpp

import test_demo_http as base
import test_shelly_gate as native

branding=base.load_module('qr_branding')


def image_bytes(fmt='PNG',size=(360,180),style='normal'):
    image=Image.new('RGBA',size,(255,255,255,0))
    draw=ImageDraw.Draw(image)
    if style=='black':draw.rectangle((0,0,*size),fill='black')
    elif style=='white':draw.rectangle((0,0,*size),fill='white')
    else:
        draw.rounded_rectangle((0,0,size[0]-1,size[1]-1),radius=12,fill='#07578b')
        draw.text((size[0]//2,size[1]//2),'CL',fill='white',font=ImageFont.load_default(size=max(1,size[1]//2)),anchor='mm')
    if fmt=='JPEG':image=image.convert('RGB')
    output=BytesIO();image.save(output,format=fmt);return output.getvalue()


def test_normalize_converts_supported_raster_formats_and_preserves_aspect():
    for fmt in ('PNG','JPEG','WEBP'):
        logo=branding.normalize_logo(image_bytes(fmt))
        raw=base64.b64decode(logo['png_base64'])
        image=Image.open(BytesIO(raw))
        assert image.format=='PNG' and image.size==(256,128)
        assert len(raw)<=branding.MAX_LOGO_BYTES and image.mode=='RGBA'


def test_metadata_is_removed_and_transparency_is_retained():
    image=Image.new('RGBA',(120,80),(0,0,0,0))
    meta=PngImagePlugin.PngInfo();meta.add_text('secret','customer private note')
    output=BytesIO();image.save(output,format='PNG',pnginfo=meta)
    logo=branding.normalize_logo(output.getvalue())
    clean=Image.open(BytesIO(base64.b64decode(logo['png_base64'])))
    assert clean.info=={} and clean.getpixel((0,0))[3]==0


@pytest.mark.parametrize('raw',[b'',b'not an image',b'<svg><script>alert(1)</script></svg>',b'x'*(1024*1024+1)])
def test_invalid_oversize_and_active_formats_are_rejected(raw):
    with pytest.raises(ValueError):branding.normalize_logo(raw)


def test_large_dimensions_and_animation_are_rejected():
    with pytest.raises(ValueError):branding.normalize_logo(image_bytes(size=(2049,2)))
    output=BytesIO()
    Image.new('RGB',(10,10),'red').save(output,format='PNG',save_all=True,append_images=[Image.new('RGB',(10,10),'blue')])
    with pytest.raises(ValueError):branding.normalize_logo(output.getvalue())


@pytest.mark.parametrize('host',['hotel.example.org','1wbausanresidency.climpianti.eu','a'*63+'.'+'b'*63+'.example.org'])
@pytest.mark.parametrize('length',[40,48,100])
@pytest.mark.parametrize('style',['normal','black','white'])
def test_branded_exports_decode_exact_original_payload_and_protect_function_modules(host,length,style):
    url='https://'+host+'/api/cl_bb_manager/physical/'+'x'*length
    logo=branding.normalize_logo(image_bytes(style=style))
    result=branding.render_qr(url,{'enabled':True,'logo':logo})
    image=Image.open(BytesIO(base64.b64decode(result['png_base64'])))
    decoded=zxingcpp.read_barcode(image)
    assert decoded is not None and decoded.text==url
    assert result['logo_applied'] is True
    qr,box=branding._qr_and_box(url,True)
    start,side=box;assert qr.error=='H' and side/len(qr.matrix)<=.18
    from segno import consts
    modules=list(qr.matrix_iter(border=0,verbose=True))
    assert all(modules[y][x] in (consts.TYPE_DATA_DARK,consts.TYPE_DATA_LIGHT)
               for y in range(start,start+side) for x in range(start,start+side))
    svg=ET.fromstring(result['svg']);embedded=svg.find('{'+branding.SVG_NS+'}image')
    assert embedded is not None
    assert embedded.get('href')=='data:image/png;base64,'+logo['png_base64']
    assert embedded.get('x')==str((branding.BORDER+start+1)*branding.SCALE)
    assert len(svg.findall('{'+branding.SVG_NS+'}rect'))==1
    assert '<script' not in result['svg']
    # Quiet zone is completely opaque white, including all corners.
    rgb=image.convert('RGB');assert all(rgb.getpixel(p)==(255,255,255) for p in [(0,0),(rgb.width-1,0),(0,rgb.height-1),(rgb.width-1,rgb.height-1)])


def test_no_logo_or_disabled_logo_exports_plain_self_contained_qr():
    url='https://hotel.example.org/api/cl_bb_manager/physical/'+'x'*48
    for settings in (None,{'enabled':False,'logo':branding.normalize_logo(image_bytes())}):
        result=branding.render_qr(url,settings)
        assert result['logo_applied'] is False
        assert 'data:image/png' not in result['svg']
        assert zxingcpp.read_barcode(Image.open(BytesIO(base64.b64decode(result['png_base64'])))).text==url


def test_corrupt_saved_logo_fails_without_returning_broken_artwork():
    with pytest.raises(ValueError):branding.render_qr('https://hotel.example.org',{'enabled':True,'logo':{'png_base64':'bad%data'}})


def test_native_upload_consumed_and_cleanup_runs_on_success_and_failure(monkeypatch,tmp_path):
    file=tmp_path/'upload';events=[]
    @contextmanager
    def process(hass,file_id):
        assert file_id=='native-upload-id'
        try:yield file
        finally:events.append('cleaned');file.unlink()
    module=ModuleType('homeassistant.components.file_upload');module.process_uploaded_file=process
    monkeypatch.setitem(sys.modules,module.__name__,module)
    for raw,valid in [(image_bytes(),True),(b'bad',False)]:
        file.write_bytes(raw)
        if valid:assert branding.consume_upload(object(),'native-upload-id')['png_base64']
        else:
            with pytest.raises(ValueError):branding.consume_upload(object(),'native-upload-id')
        assert not file.exists()
    assert events==['cleaned','cleaned']


def test_branding_changes_preserve_gates_tokens_grants_and_restore_on_save_error(monkeypatch):
    async def run():
        manager,hass,rpc,*_=native.fixture(monkeypatch)
        manager.data['gates']=[{'id':'door','physical_token':'unchanged','physical_enabled':True}]
        manager.data['bookings']=[{'physical_gate_ids':['door']}]
        original=deepcopy(manager.data)
        logo=branding.normalize_logo(image_bytes())
        monkeypatch.setattr(branding,'consume_upload',lambda *args:logo)
        async def executor(fn,*args):return fn(*args)
        hass.async_add_executor_job=executor
        await branding.async_update_branding(manager,enabled=True,file_id='upload')
        assert branding.branding_status(manager.data)['enabled']
        assert manager.data['gates']==original['gates'] and manager.data['bookings']==original['bookings']
        before=deepcopy(manager.data);manager.fail_save=True
        with pytest.raises(ValueError):await branding.async_update_branding(manager,enabled=False,remove_logo=True)
        assert manager.data==before
        manager.fail_save=False
        await branding.async_update_branding(manager,enabled=False)
        assert not branding.branding_status(manager.data)['enabled'] and branding.branding_status(manager.data)['has_logo']
        await branding.async_update_branding(manager,enabled=True)
        assert branding.branding_status(manager.data)['enabled']
        await branding.async_update_branding(manager,enabled=True,remove_logo=True)
        assert branding.branding_status(manager.data)=={'has_logo':False,'enabled':False}
        assert manager.data['gates']==original['gates'] and manager.data['bookings']==original['bookings']
        assert rpc.calls==[]  # Branding never touches the native device connection.
    asyncio.run(run())


def test_longest_dns_name_with_large_physical_token_still_decodes_with_logo():
    host='.'.join(['a'*63,'b'*63,'c'*63,'d'*61])
    assert len(host)==253
    url='https://'+host+'/api/cl_bb_manager/physical/'+'x'*100
    result=branding.render_qr(url,{'enabled':True,'logo':branding.normalize_logo(image_bytes())})
    assert zxingcpp.read_barcode(Image.open(BytesIO(base64.b64decode(result['png_base64'])))).text==url
