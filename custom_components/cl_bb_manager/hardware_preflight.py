"""Read-only readiness report. Does not arm gates or send device commands."""
from .physical_policy import ready_actuator
from .property_scope import belongs_to_property


def hardware_preflight(gate, property_id, hass, demo_scripts=None):
    blockers = []
    if not belongs_to_property(gate, property_id):
        blockers.append("Varco non appartenente alla struttura.")
    target = ready_actuator(gate, hass) if not blockers else None
    if target is None:
        blockers.append("Dispositivo del varco non configurato, non disponibile o non spento.")
    return {"gate_id": gate.get("id"), "name": gate.get("name"),
            "script_id": target, "status": "ready" if not blockers else "blocked",
            "ready_for_physical_qr": not blockers, "blockers": blockers}
