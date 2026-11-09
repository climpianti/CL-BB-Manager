"""Pure stable QR policy and short-lived browser forms."""
import importlib
from pathlib import Path
import sys
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager"
package = ModuleType("_cl_bb_permanent_policy_test")
package.__path__ = [str(ROOT)]
sys.modules[package.__name__] = package
policy = importlib.import_module(package.__name__ + ".permanent_policy")


def test_stable_https_url_remains_identical_across_calls():
    token = "random-opaque-public-label-0123456789-ABCDEFG"
    url = policy.permanent_url("https://hotel.example.org", token)
    assert url == policy.permanent_url("https://hotel.example.org", token)
    assert url.endswith("/permanent-demo/" + token)
    assert "pin" not in url
    assert "csrf" not in url


@pytest.mark.parametrize("url", ["http://hotel.example.org", "https://192.168.1.10", "https://hotel.example.org/path", "https://hotel.example.org:8123"])
def test_requires_https_dns_origin(url):
    with pytest.raises(ValueError):
        policy.permanent_url(url, "x" * 32)


def test_csrf_is_single_use_scoped_and_expires():
    forms = {}
    token = policy.issue_form(forms, "gate-a", now=100)
    assert token not in policy.permanent_url("https://hotel.example.org", "a" * 32)
    assert not policy.consume_form(forms, token, "gate-b", now=101)
    assert not policy.consume_form(forms, token, "gate-a", now=101)
    token = policy.issue_form(forms, "gate-a", now=200)
    assert policy.consume_form(forms, token, "gate-a", now=201)
    assert not policy.consume_form(forms, token, "gate-a", now=202)
    expired = policy.issue_form(forms, "gate-a", now=300)
    assert not policy.consume_form(forms, expired, "gate-a", now=901)


def test_bounded_forms_clean_expired_and_fail_closed():
    forms = {}
    for i in range(policy.MAX_FORMS):
        policy.issue_form(forms, str(i), now=100)
    with pytest.raises(ValueError):
        policy.issue_form(forms, "extra", now=101)
    policy.issue_form(forms, "fresh", now=800)
    assert len(forms) == 1
    assert next(iter(forms.values()))["gate_id"] == "fresh"
