"""Source-level invariants for stable QR management exposed by HA."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager"


def test_permanent_qr_restricted_to_admin_and_virtual_gates():
    api = (ROOT / "api.py").read_text(encoding="utf-8")
    assert '"type": "cl_bb_manager/permanent_pilot_qr"' in api
    assert '"type": "cl_bb_manager/rotate_permanent_qr"' in api
    for method in ("async def permanent_pilot_qr", "async def rotate_permanent_qr"):
        block = api.split(method, 1)[1].split("    @websocket_api.websocket_command", 1)[0]
        assert "admin_only=True" in block
    assert 'permanent_url(origin, gate["token"])' in api
    assert "demo_target_allowed(gate, DEMO_SCRIPTS)" in api
    assert 'manager.permanent_forms.clear()' in api
    assert 'manager.demo_sessions.clear()' in api
    assert 'manager.public_demo_sessions.clear()' in api


def test_permanent_route_opt_in_and_virtual_only():
    server = (ROOT / "permanent_http.py").read_text(encoding="utf-8")
    store = (ROOT / "__init__.py").read_text(encoding="utf-8")
    opts = (ROOT / "config_flow.py").read_text(encoding="utf-8")
    panel = (ROOT / "frontend/panel.js").read_text(encoding="utf-8")
    assert 'permanent_pilot_enabled", False' in server
    assert 'demo_target_allowed(current, DEMO_SCRIPTS)' in server
    assert '"script", "turn_on"' in server
    assert 'property_id=manager.property_id' in server
    assert 'manager.permanent_forms = {}' not in store
    assert 'self.permanent_forms = {}' in store
    assert 'hass.http.register_view(PermanentPilotView())' in store
    assert '"permanent_pilot_enabled"' in opts
    assert 'default=self.config_entry.options.get("permanent_pilot_enabled", False)' in opts
    assert 'permanent_pilot_qr' in panel
    assert 'rotate_permanent_qr' in panel
    assert 'download="CL-BB-QR-' not in panel  # generated via DOM property, never HTML injection
    assert 'download.download="CL-BB-QR-"' in panel
