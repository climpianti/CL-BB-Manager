"""Read-only risk checklist for staged real-door actuators.

This module must NEVER call Home Assistant services. A passing preflight
does not permit physical activation: independent review remains mandatory.
"""
from __future__ import annotations

from .hardware_staging import read_candidate
from .property_scope import belongs_to_property
from .security import demo_target_allowed


def hardware_preflight(gate: dict, property_id: str, hass, demo_scripts) -> dict:
    """Return redacted status and explicit blockers for the admin panel."""
    blockers = []
    if not belongs_to_property(gate, property_id):
        blockers.append("Varco non appartenente alla struttura.")
    if not demo_target_allowed(gate, demo_scripts):
        blockers.append("Il varco non è un varco virtuale abilitato.")
    staged = read_candidate(gate)
    if staged is None:
        blockers.append("Nessuno script reale predisposto.")
    else:
        entity = hass.states.get(staged["entity_id"])
        if entity is None or entity.state in ("unknown", "unavailable"):
            blockers.append("Script fisico non disponibile.")
    # Deliberate release gate: cannot be cleared by any client-supplied
    # parameter, stored candidate metadata, HTTP request or booking.
    blockers.append("Revisione indipendente di sicurezza HTTPS/PIN e collaudo end-to-end ancora necessari.")
    return {
        "gate_id": gate.get("id"),
        "name": gate.get("name"),
        "script_id": staged["entity_id"] if staged else None,
        "status": "blocked",
        "ready_for_physical_qr": False,
        "blockers": blockers,
    }
