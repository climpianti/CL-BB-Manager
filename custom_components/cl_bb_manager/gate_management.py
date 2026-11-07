"""Shared, side-effect-free guard for removing a configured gate.

Used by the admin WebSocket command and by Home Assistant integration options.
The guard must prevent invalidating active or future booking permissions.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .models import as_utc


def check_gate_removal(gate_id: str, bookings: list[dict], *, now: datetime | None = None) -> None:
    """Raise ValueError if any non-revoked, non-expired booking uses this gate."""
    instant = now if now is not None else datetime.now(timezone.utc)
    for booking in bookings:
        if (
            not booking.get("revoked", False)
            and gate_id in booking.get("gate_ids", ())
            and as_utc(booking["end"]) > instant
        ):
            raise ValueError("Revocare prima le prenotazioni future associate.")
