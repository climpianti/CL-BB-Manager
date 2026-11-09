"""Pure unit tests for the booking access rules."""
from datetime import datetime, timedelta, timezone
import pytest
import importlib.util
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager/models.py"
spec = importlib.util.spec_from_file_location("cl_bb_models", source)
models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(models)
generate_pin, seal_pin, pin_matches = models.generate_pin, models.seal_pin, models.pin_matches
make_booking, make_gate = models.make_booking, models.make_gate
booking_allows, public_booking = models.booking_allows, models.public_booking


def test_pin_security():
    pin = generate_pin()
    assert len(pin) == 8 and pin.isascii() and pin.isdecimal()
    digest = seal_pin(pin)
    assert pin not in repr(digest)
    assert pin_matches(pin, digest)
    assert not pin_matches("abcdefgh", digest)


def test_gate_map():
    gate = make_gate("Camera 1", "script.cl_bb_demo_apri_camera_1", "script.turn_on")
    assert gate["enabled"] is False
    relay = make_gate("Porta", "switch.foo", "switch.turn_on")
    assert relay["enabled"] is False
    assert "shelly_binding" not in relay  # Metadata alone grants no physical capability.
    with pytest.raises(ValueError):
        make_gate("Abusivo", "switch.foo", "switch.toggle")


def test_booking_access_and_revoke():
    now = datetime.now(timezone.utc)
    booking = make_booking(
        "Camera 1", now.isoformat(),
        (now + timedelta(days=1)).isoformat(), ["gate1"], "12345678"
    )
    assert booking_allows(booking, "gate1", now + timedelta(hours=1))
    assert not booking_allows(booking, "gate2", now + timedelta(hours=1))
    assert not booking_allows(booking, "gate1", now + timedelta(days=2))
    booking["revoked"] = True
    assert not booking_allows(booking, "gate1", now + timedelta(hours=1))
    assert "pin_hash" not in public_booking(booking)
    named=make_booking(
        "Camera 2", now.isoformat(),
        (now + timedelta(days=1)).isoformat(), ["gate1"], "87654321",
        "Ospite prova",
    )
    assert public_booking(named)["guest_name"]=="Ospite prova"


def test_naive_datetime_rejected():
    with pytest.raises(ValueError):
        make_booking("Camera 1", "2026-11-10T14:00:00",
                     "2026-11-11T10:00:00+01:00", ["a"], "12345678")

