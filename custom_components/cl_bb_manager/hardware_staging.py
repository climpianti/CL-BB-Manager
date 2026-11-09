"""Administrative staging for future physical gate integration.

Staging a script is only metadata. No public URL, booking, demo script, or
Home Assistant service call may use this candidate until an independently
reviewed hardware access path is implemented in a later release.
"""
from __future__ import annotations

import re

from .property_scope import require_record_scope

_SCRIPT = re.compile(r"^script\.[a-z0-9_]{1,240}$")
FIELD = "hardware_candidate"


def prepare_candidate(
    gate: dict, property_id: str, script_id: str, state,
    *, virtual_script_ids: frozenset[str] | set[str],
) -> dict:
    """Return strictly limited non-executable mapping metadata."""
    require_record_scope(gate, property_id)
    if not isinstance(gate.get("id"), str) or not gate["id"]:
        raise ValueError("Varco non valido.")
    if gate.get("action") != "script.turn_on":
        raise ValueError("Il varco richiede una mappatura tramite script.")
    if not isinstance(script_id, str) or not _SCRIPT.fullmatch(script_id):
        raise ValueError("Selezionare uno script Home Assistant valido.")
    if script_id == gate.get("entity_id") or script_id in virtual_script_ids:
        raise ValueError("Usare uno script reale separato da quelli demo.")
    if state is None or getattr(state, "state", None) in ("unknown", "unavailable"):
        raise ValueError("Script reale non disponibile in Home Assistant.")
    return {
        "entity_id": script_id,
        "action": "script.turn_on",
        "status": "pending_security_review",
    }


def clear_candidate(gate: dict, property_id: str) -> None:
    """Remove only the staged metadata; do not rotate the printed QR."""
    require_record_scope(gate, property_id)
    gate.pop(FIELD, None)


def read_candidate(gate: dict) -> dict | None:
    """Redact unsafe/unrecognized stored values from the panel."""
    candidate = gate.get(FIELD)
    if not isinstance(candidate, dict):
        return None
    if (
        candidate.get("status") != "pending_security_review"
        or candidate.get("action") != "script.turn_on"
        or not isinstance(candidate.get("entity_id"), str)
        or not _SCRIPT.fullmatch(candidate["entity_id"])
    ):
        return None
    return {
        "entity_id": candidate["entity_id"],
        "status": "pending_security_review",
    }
