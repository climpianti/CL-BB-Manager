"""Shared, side-effect-free guard for removing a configured gate.

Used by the admin WebSocket command and by Home Assistant integration options.
The guard must prevent invalidating active or future booking permissions.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .models import as_utc


def native_mapping_changed(hass, original: dict, candidate: dict) -> bool:
    """Accept a registry rename only when the stored native identity matches."""
    if "entity_binding" in original:
        from .entity_gate import resolve_binding
        entity_id = resolve_binding(hass, original["entity_binding"])
        action = original["entity_binding"]["action"]
    else:
        from .shelly_gate import resolve_binding
        entity_id = resolve_binding(hass, original["shelly_binding"]).entity_id
        action = "switch.turn_on"
    if candidate["entity_id"] != entity_id or candidate["action"] != action:
        raise ValueError("Il dispositivo configurato richiede una nuova procedura di associazione.")
    return original["kind"] != candidate["kind"]


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

