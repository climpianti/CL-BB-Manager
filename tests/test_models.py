"""Pure unit tests for the booking access rules."""
from datetime import datetime, timedelta, timezone
import pytest
from custom_components.cl_bb_manager.models import (
    generate_pin, seal_pin, pin_matches, make_booking, make_gate,
    booking_allows, public_booking
)


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
    with pytest.raises(ValueError):
        make_gate("Abusivo", "switch.foo", "switch.turn_on")


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


def test_naive_datetime_rejected():
    with pytest.raises(ValueError):
        make_booking("Camera 1", "2026-11-10T14:00:00",
                     "2026-11-11T10:00:00+01:00", ["a"], "12345678")
