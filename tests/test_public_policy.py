"""Public HTTPS pilot policy must never accept LAN origins or arbitrary ports."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

FILE = Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager/public_policy.py"
spec = importlib.util.spec_from_file_location("cl_bb_public_policy_test", FILE)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


@pytest.mark.parametrize("candidate", [
    "https://1wbausanresidency.climpianti.eu",
    "https://TEST.example.org/",
])
def test_explicit_https_dns_is_allowed(candidate):
    assert policy.validate_public_origin(candidate).startswith("https://")


@pytest.mark.parametrize("candidate", [
    "http://1wbausanresidency.climpianti.eu",
    "http://192.168.110.103:8123",
    "https://127.0.0.1",
    "https://localhost",
    "https://example.org:8123",
    "https://example.org/path",
    "https://example.org?q=hello",
    "https://user:pass@example.org",
    "https://example.org@evil.net/",
    "javascript:alert(1)",
    "",
])
def test_public_policy_rejects_noncanonical_or_insecure_urls(candidate):
    with pytest.raises(ValueError):
        policy.validate_public_origin(candidate)


def test_bound_host_and_ten_minute_expiry():
    origin = "https://1wbausanresidency.climpianti.eu"
    token, session = policy.create_public_session("gate-1", origin, now=1000)
    assert len(token) > 40
    assert len(session["form_csrf"]) > 40
    assert session["expires"] == 1600
    assert policy.valid_public_session(session, "1wbausanresidency.climpianti.eu", origin, now=1300)
    assert not policy.valid_public_session(session, "evil.example.org", origin, now=1300)
    assert not policy.valid_public_session(session, "1wbausanresidency.climpianti.eu", "https://other.example.org", now=1300)
    assert not policy.valid_public_session(session, "1wbausanresidency.climpianti.eu", origin, now=1600)
    assert not policy.valid_public_session(None, "1wbausanresidency.climpianti.eu", origin, now=1300)
