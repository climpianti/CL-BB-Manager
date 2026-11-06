"""Pure testable security policy for CL B&B demo guest access.

Every accepted attempt is charged to persisted state BEFORE PIN verification.
Global and gate limits do not trust HTTP headers or the client's IP address.
"""
from __future__ import annotations

import math
import time

GLOBAL_PER_MINUTE = 12
GLOBAL_PER_DAY = 120
GATE_PER_MINUTE = 5
GATE_PER_HOUR = 25
MAX_ACTIVE_CANDIDATES = 20
DAY_SECONDS = 86400


def _recent(values: list, now: float, seconds: int) -> list[float]:
    """Discard old timestamps; invalid persisted state MUST fail closed."""
    if not isinstance(values, list) or len(values) > 2000:
        raise ValueError("Invalid persisted attempt history")
    if any(
        not isinstance(t, (int, float))
        or not math.isfinite(t)
        or t > now + 60
        for t in values
    ):
        raise ValueError("Invalid persisted attempt timestamp")
    return [float(t) for t in values if now - seconds < t <= now + 60]


def charge_attempt(state: dict, gate_id: str, now: float | None = None) -> bool:
    """Update a stored throttle, returning False when limits are exhausted.

    This is intended to run within the manager's async lock. The caller
    MUST persist the modified state before expensive password verification
    or a simulated door action. Limits survive an HA restart.
    """
    instant = time.time() if now is None else float(now)
    if not math.isfinite(instant) or not isinstance(state, dict):
        raise ValueError("Invalid attempt state")
    all_items = _recent(state.get("all", []), instant, DAY_SECONDS)
    gates = state.get("gates", {})
    if not isinstance(gates, dict):
        raise ValueError("Invalid gate attempt state")
    gate_items = _recent(gates.get(gate_id, []), instant, 3600)

    if (
        sum(t > instant - 60 for t in all_items) >= GLOBAL_PER_MINUTE
        or len(all_items) >= GLOBAL_PER_DAY
        or sum(t > instant - 60 for t in gate_items) >= GATE_PER_MINUTE
        or len(gate_items) >= GATE_PER_HOUR
    ):
        return False

    # Do not modify persisted state until the checks all pass.
    state["all"] = all_items + [instant]
    gates = {
        key: _recent(val, instant, 3600)
        for key, val in gates.items()
        if isinstance(key, str) and len(key) <= 100
    }
    gates[gate_id] = gate_items + [instant]
    state["gates"] = {key: val for key, val in gates.items() if val}
    return True


def demo_target_allowed(gate: dict, allowlisted: set[str] | frozenset[str]) -> bool:
    """Ensure a gate is enabled and mapped ONLY to an approved demo script."""
    return (
        gate.get("enabled") is True
        and gate.get("action") == "script.turn_on"
        and gate.get("entity_id") in allowlisted
    )


def candidate_bookings(bookings: list[dict], gate_id: str, now=None):
    """Return bounded authorized candidates; fail closed under excess load."""
    from .models import booking_allows

    candidates = []
    for booking in bookings:
        if booking_allows(booking, gate_id, now):
            candidates.append(booking)
            if len(candidates) > MAX_ACTIVE_CANDIDATES:
                raise ValueError("Too many active candidates for demo")
    return candidates
