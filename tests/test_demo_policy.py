"""Unit tests for LAN-only QR sessions, without Home Assistant installed."""
import importlib.util
from pathlib import Path
import pytest

SOURCE = Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager/demo_policy.py"
spec = importlib.util.spec_from_file_location("cl_bb_demo_policy_test", SOURCE)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


@pytest.mark.parametrize("origin,expected", [
    ("http://192.168.1.100:8123", ("http://192.168.1.100:8123", "192.168.1.100:8123")),
    ("http://10.0.0.8:8123", ("http://10.0.0.8:8123", "10.0.0.8:8123")),
    ("https://homeassistant.local", ("https://homeassistant.local", "homeassistant.local")),
    ("http://ha.home.local:8123/", ("http://ha.home.local:8123", "ha.home.local:8123")),
])
def test_local_url_allowed(origin, expected):
    assert policy.validate_demo_origin(origin) == expected


@pytest.mark.parametrize("origin", [
    "https://climpianti.eu",
    "https://access.example.com",
    "http://8.8.8.8:8123",
    "http://127.0.0.1:8123",
    "http://localhost:8123",
    "http://172.32.0.1:8123",
    "http://user:pass@192.168.1.50:8123",
    "http://192.168.1.50:8123/path",
    "http://192.168.1.50:8123/?secret=1",
    "http://192.168.1.50:8123/#fragment",
    "ftp://192.168.1.50",
])
def test_public_or_unsafe_url_rejected(origin):
    with pytest.raises(ValueError):
        policy.validate_demo_origin(origin)


def test_qr_session_bound_to_local_host_and_expires():
    token, session = policy.make_demo_session(
        "demo-gate", "http://192.168.1.100:8123", now=1000
    )
    assert len(token) >= 40
    assert session["expires"] == 1600
    assert policy.valid_demo_session(session, "192.168.1.100:8123", "192.168.1.80", now=1300)
    assert not policy.valid_demo_session(session, "192.168.1.100:8123", "8.8.8.8", now=1300)
    assert not policy.valid_demo_session(session, "wrong.host:8123", "192.168.1.80", now=1300)
    assert not policy.valid_demo_session(session, "192.168.1.100:8123", "192.168.1.80", now=1600)


def test_no_public_peer_trust_based_on_forwarded_host():
    assert policy.is_lan_peer("192.168.2.51")
    assert policy.is_lan_peer("127.0.0.1")
    assert not policy.is_lan_peer("8.8.8.8")
    assert not policy.is_lan_peer(None)
