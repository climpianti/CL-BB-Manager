"""No PIN/token leakage; operator-visible logs are booking-scoped."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"custom_components/cl_bb_manager"
spec=importlib.util.spec_from_file_location("cl_bb_access_history",ROOT/"access_history.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_authorized_code_is_attributed_to_booking_not_claimed_person():
    now=datetime.now(timezone.utc)
    data={"access_history":[]}
    booking={"id":"booking-1","room":"Camera 2","guest_name":"Mario Rossi","pin_hash":"SECRET","pin_salt":"SECRET"}
    gate={"id":"gate-2","name":"Portone","token":"SECRET"}
    event=module.add_access_event(data,source="https",result="authorized",gate=gate,booking=booking,now=now)
    assert event["booking_id"]=="booking-1"
    assert event["room"]=="Camera 2"
    assert event["guest_name"]=="Mario Rossi"
    assert "pin" not in str(event).lower()
    assert "SECRET" not in str(event)
    assert "token" not in event
    assert module.public_access_history(data)==[event]


def test_denied_attempt_never_identifies_a_booking():
    data={}
    module.add_access_event(
        data,source="lan",result="denied",
        gate={"id":"gate-1","name":"Ingresso"},
        booking={"id":"secret","room":"Camera 1","guest_name":"Nome"},
    )
    entry=data["access_history"][0]
    assert entry["booking_id"]==""
    assert entry["room"]==""
    assert entry["guest_name"]==""


def test_old_entries_are_not_reported_and_limit_is_bounded():
    now=datetime.now(timezone.utc)
    data={"access_history":[{
        "at":(now-timedelta(days=100)).isoformat(),
        "result":"authorized","guest_name":"Old",
    }]}
    for _ in range(module.MAX_ACCESS_EVENTS+2):
        module.add_access_event(
            data,source="lan",result="denied",
            gate={"id":"1","name":"Ingresso"},now=now,
        )
    assert len(data["access_history"])==module.MAX_ACCESS_EVENTS
    assert all(x["guest_name"]!="Old" for x in module.public_access_history(data))


def test_does_not_expose_malformed_history():
    assert module.public_access_history({"access_history":"garbage"})==[]
    assert module.public_access_history({"access_history":[{"at":"NaN"}]})==[]
