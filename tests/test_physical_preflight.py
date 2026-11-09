"""No-physical-actuation regressions and hardened HTTPS origin tests."""
from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager"
PKG = "_cl_bb_physical_preflight_test"
pkg = ModuleType(PKG)
pkg.__path__ = [str(ROOT)]
sys.modules.setdefault(PKG, pkg)
policy = importlib.import_module(PKG + ".public_policy")
scope = importlib.import_module(PKG + ".property_scope")
preflight = importlib.import_module(PKG + ".hardware_preflight")


@pytest.mark.parametrize("origin,fetch_site,expected", [
    ("https://hotel.example.org", "same-origin", True),
    (None, "same-origin", True),
    (None, None, True),
    (None, "cross-site", False),
    (None, "same-site", False),
    ("null", "same-origin", False),
    ("https://evil.example.org", "same-origin", False),
    ("http://hotel.example.org", "same-origin", False),
    ("https://hotel.example.org", "cross-site", False),
    ("https://hotel.example.org", "same-site", False),
    ("https://hotel.example.org:443", "same-origin", False),
])
def test_strict_public_post_origin(origin, fetch_site, expected):
    assert policy.valid_https_form_origin(
        origin, fetch_site, "https://hotel.example.org"
    ) is expected


def test_preflight_reports_readiness_without_arming_or_mutating():
    property_id = scope.new_property("Pilot")["id"]
    gate = {
        "id": "gate1", "name": "Scala", "property_id": property_id,
        "enabled": True, "action": "script.turn_on",
        "entity_id": "script.cl_bb_demo_apri_portone",
        "hardware_candidate": {
            "entity_id": "script.cl_bb_porta_scala_impulso_locale",
            "action": "script.turn_on",
            "status": "pending_security_review",
        },
    }
    class StateLookup:
        def get(self, entity_id):
            return SimpleNamespace(state="off")
    hass = SimpleNamespace(states=StateLookup())
    report = preflight.hardware_preflight(
        gate, property_id, hass, frozenset({"script.cl_bb_demo_apri_portone"})
    )
    assert report["status"] == "ready"
    assert report["ready_for_physical_qr"] is True
    assert report["script_id"] == "script.cl_bb_porta_scala_impulso_locale"
    assert report["blockers"] == []
    # No mutating side effects; existing QR mapping remains virtual.
    assert gate["entity_id"] == "script.cl_bb_demo_apri_portone"


def test_live_post_paths_use_only_strict_policy_and_demo_scripts():
    for file in ("permanent_http.py", "public_http.py"):
        s = (ROOT / file).read_text(encoding="utf-8")
        assert "valid_https_form_origin(" in s
        assert "valid_form_origin(" not in s
        assert "hardware_candidate" not in s
        assert "demo_target_allowed(" in s
    api = (ROOT / "api.py").read_text(encoding="utf-8")
    block = api.split("async def hardware_preflight_report", 1)[1].split(
        "async def permanent_pilot_qr", 1
    )[0]
    assert 'admin_only=True' in block
    assert "services.async_call" not in block

