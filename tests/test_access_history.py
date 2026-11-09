"""No PIN/token leakage; operator-visible logs are booking-scoped."""
import importlib.util
import sys
from types import ModuleType
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"custom_components/cl_bb_manager"
package=ModuleType("cl_bb_access_history_test")
package.__path__=[str(ROOT)]
sys.modules[package.__name__]=package
spec=importlib.util.spec_from_file_location(package.__name__+".access_history",ROOT/"access_history.py")
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)
PROPERTY_ID="2bb950a2-a1c5-46ca-b192-9ad03b1f8ca5"


def test_authorized_code_is_attributed_to_booking_not_claimed_person():
    now=datetime.now(timezone.utc)
    data={"access_history":[]}
    booking={"id":"booking-1","property_id":PROPERTY_ID,"room":"Camera 2","guest_name":"Mario Rossi","pin_hash":"SECRET","pin_salt":"SECRET"}
    gate={"id":"gate-2","property_id":PROPERTY_ID,"name":"Portone","token":"SECRET"}
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
        gate={"id":"gate-1","property_id":PROPERTY_ID,"name":"Ingresso"},
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
            gate={"id":"1","property_id":PROPERTY_ID,"name":"Ingresso"},now=now,
        )
    assert len(data["access_history"])==module.MAX_ACCESS_EVENTS
    assert all(x["guest_name"]!="Old" for x in module.public_access_history(data))


def test_does_not_expose_malformed_history():
    assert module.public_access_history({"access_history":"garbage"})==[]
    assert module.public_access_history({"access_history":[{"at":"NaN"}]})==[]
