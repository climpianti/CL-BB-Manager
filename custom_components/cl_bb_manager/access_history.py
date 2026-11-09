"""Privacy-limited access history for CL B&B Manager virtual-only pilots.

A successful code verification identifies the *booking* used, not the person
physically entering a PIN. Never store the PIN, QR URL or temporary session.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .property_scope import require_property_id

MAX_ACCESS_EVENTS = 1000
ACCESS_HISTORY_DAYS = 90
ACCESS_SOURCES = frozenset({"lan", "https", "legacy"})
ACCESS_RESULTS = frozenset({"authorized", "denied"})


def add_access_event(
    data: dict[str, Any],
    *,
    source: str,
    result: str,
    gate: dict[str, Any],
    booking: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Append a sanitized, bounded audit entry after a verification attempt."""
    if source not in ACCESS_SOURCES or result not in ACCESS_RESULTS:
        raise ValueError("Invalid access event category")
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("Access event time must include a timezone")
    stamp = instant.astimezone(timezone.utc)
    property_id = require_property_id(gate.get("property_id"))
    if booking is not None and booking.get("property_id") != property_id:
        raise ValueError("Prenotazione di un altra struttura.")
    matched = booking if result == "authorized" and booking else {}
    entry = {
        "at": stamp.isoformat(),
        "property_id": property_id,
        "source": source,
        "result": result,
        "gate_id": str(gate.get("id", ""))[:128],
        "gate_name": str(gate.get("name", ""))[:80],
        "booking_id": str(matched.get("id", ""))[:128],
        "room": str(matched.get("room", ""))[:80],
        "guest_name": str(matched.get("guest_name", ""))[:80],
    }
    existing = data.get("access_history", [])
    if not isinstance(existing, list):
        existing = []
    cutoff = stamp - timedelta(days=ACCESS_HISTORY_DAYS)
    retained = []
    for candidate in existing[-MAX_ACCESS_EVENTS:]:
        if not isinstance(candidate, dict):
            continue
        try:
            event_time = datetime.fromisoformat(str(candidate.get("at", "")))
            if event_time.tzinfo and event_time.astimezone(timezone.utc) >= cutoff:
                retained.append(candidate)
        except (TypeError, ValueError):
            continue
    data["access_history"] = (retained + [entry])[-MAX_ACCESS_EVENTS:]
    return entry


def public_access_history(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only the strictly enumerated fields for authorized B&B users."""
    values = data.get("access_history", [])
    if not isinstance(values, list):
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=ACCESS_HISTORY_DAYS)
    allowed = (
        "at", "property_id", "source", "result", "gate_id", "gate_name",
        "booking_id", "room", "guest_name",
    )
    output = []
    for item in values[-MAX_ACCESS_EVENTS:]:
        if not isinstance(item, dict):
            continue
        try:
            at = datetime.fromisoformat(str(item.get("at", "")))
        except (TypeError, ValueError):
            continue
        if at.tzinfo is None or at.astimezone(timezone.utc) < cutoff:
            continue
        output.append({key: str(item.get(key, "")) for key in allowed})
    return output
