"""Loopback-only browser fixture using production handlers and fake HA devices."""
import asyncio
from pathlib import Path

from aiohttp import web
from pytest import MonkeyPatch

from test_pin_form_regression import setup_gate
from test_guest_i18n import physical


async def main():
    patch=MonkeyPatch();contexts={};commands=[]
    async def endpoint(request):
        token=request.match_info['token']
        if token not in contexts:
            door='strada' if token.startswith('strada-') else 'scala'
            manager,hass,gate,script=setup_gate(patch,door)
            gate['physical_token']=token
            contexts[token]=(manager,hass)
        manager,hass=contexts[token]
        # Each context is separate; only production request handlers run below.
        request.app['hass']=hass
        view=physical.PhysicalGuestView()
        response=await (view.get if request.method=='GET' else view.post)(request,token)
        commands[:] = [call for _,h in contexts.values() for call in h.calls]
        return response
    async def status(request):return web.json_response({'commands':len(commands)})
    async def logo(request):
        return web.FileResponse(Path(__file__).resolve().parents[1]/'custom_components/cl_bb_manager/frontend/cl-impianti-logo.svg')
    app=web.Application()
    app.router.add_route('GET','/api/cl_bb_manager/physical/{token}',endpoint)
    app.router.add_route('POST','/api/cl_bb_manager/physical/{token}',endpoint)
    app.router.add_get('/cl_bb_manager_static/cl-impianti-logo.svg',logo)
    app.router.add_get('/__test_status',status)
    runner=web.AppRunner(app,access_log=None);await runner.setup()
    site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
    print(site._server.sockets[0].getsockname()[1],flush=True)
    try:await asyncio.Event().wait()
    finally:await runner.cleanup();patch.undo()


if __name__=='__main__':asyncio.run(main())
