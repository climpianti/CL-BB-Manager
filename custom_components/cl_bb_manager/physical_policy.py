"""Fail-closed policy for an isolated physical-door QR endpoint.

The existing printed permanent-demo QR is not upgraded into a door key.
Physical URLs, gate enablement and booking grants are independent, and the
release remains compile-time disabled until independently reviewed.
"""
from __future__ import annotations

import math
import secrets
import time

from .hardware_staging import read_candidate
from .models import booking_allows
from .property_scope import belongs_to_property

# Independent review/field acceptance is required before changing this flag.
# No config option, WebSocket call or stored record may override it.
PHYSICAL_RELEASE_ENABLED = False
PHYSICAL_OPEN_COOLDOWN_SECONDS = 12

# Explicitly reviewed actuator pairs for the single-property physical pilot.
# Fail closed for any script that is not paired with its expected Shelly relay.
# New installations require a separate, reviewed pairing/provisioning workflow.
PILOT_SCRIPT_RELAY = {
    "script.cl_bb_porta_strada_impulso_locale": "switch.porta_strada",
    "script.cl_bb_porta_scala_impulso_locale": "switch.porta_scale",
}


def physical_target(manager, gate: dict, hass, *, token: str | None = None):
    """Only return a real script when EVERY independent guard succeeds."""
    if not PHYSICAL_RELEASE_ENABLED:
        return None
    if manager.data.get("physical_access_enabled") is not True:
        return None
    if not belongs_to_property(gate, manager.property_id):
        return None
    if gate.get("enabled") is not True or gate.get("physical_enabled") is not True:
        return None
    if gate.get("action") != "script.turn_on":
        return None
    physical_token = gate.get("physical_token")
    if (
        not isinstance(physical_token, str)
        or not 40 <= len(physical_token) <= 100
    ):
        return None
    if token is not None and (
        not isinstance(token, str)
        or len(token) != len(physical_token)
        or not secrets.compare_digest(token, physical_token)
    ):
        return None
    # Deliberately separate from original demo entity and token.
    if physical_token == gate.get("token"):
        return None
    candidate = read_candidate(gate)
    if not candidate or candidate["entity_id"] == gate.get("entity_id"):
        return None
    if candidate["entity_id"].startswith("script.cl_bb_demo_"):
        return None
    script_id = candidate["entity_id"]
    relay_id = PILOT_SCRIPT_RELAY.get(script_id)
    if relay_id is None:
        return None
    entity = hass.states.get(script_id)
    relay = hass.states.get(relay_id)
    if (
        entity is None or getattr(entity, "state", None) != "off"
        or relay is None or getattr(relay, "state", None) != "off"
    ):
        return None
    return script_id


def approved_booking(booking: dict, gate_id: str, property_id: str) -> bool:
    """Existing virtual-only bookings NEVER gain physical rights implicitly."""
    return (
        isinstance(booking, dict)
        and belongs_to_property(booking, property_id)
        and isinstance(booking.get("physical_gate_ids"), list)
        and gate_id in booking["physical_gate_ids"]
        and booking_allows(booking, gate_id)
    )


def take_cooldown(data: dict, gate_id: str, *, now: float | None = None) -> bool:
    """Reserve a cooldown before issuing any physical service call.

    Call while holding manager.lock and persist the modified state before
    actuation. Even a timeout or uncertain outcome cannot immediately replay.
    """
    instant = time.time() if now is None else now
    if (type(instant) not in (int, float) or not math.isfinite(instant)):
        return False
    prior = data.setdefault("physical_last_action", {})
    if not isinstance(prior, dict):
        return False
    last = prior.get(gate_id)
    if last is not None and (
        type(last) not in (int, float)
        or not math.isfinite(last)
        or last > instant
        or instant - last < PHYSICAL_OPEN_COOLDOWN_SECONDS
    ):
        return False
    prior[gate_id] = instant
    return True
