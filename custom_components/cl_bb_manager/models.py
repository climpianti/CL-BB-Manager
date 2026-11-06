"""Pure-data security and reservation helpers, independent of Home Assistant."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from uuid import uuid4

PIN_DIGITS = 8
PIN_ITERATIONS = 200_000
ALLOWED_ACTIONS = {
    "script.turn_on": "script",
    "button.press": "button",
    "lock.unlock": "lock",
}


def as_utc(value: str) -> datetime:
    """Parse a timezone-aware ISO-8601 instant."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Indicare un orario con fuso orario.")
    return dt.astimezone(timezone.utc)


def generate_pin() -> str:
    """Create a PIN using a cryptographically secure generator."""
    return f"{secrets.randbelow(10 ** PIN_DIGITS):0{PIN_DIGITS}d}"


def seal_pin(pin: str) -> dict[str, str]:
    """Hash a PIN using salted PBKDF2, never store it in plaintext."""
    if not (pin.isascii() and pin.isdecimal() and len(pin) == PIN_DIGITS):
        raise ValueError("Il PIN deve essere numerico di otto cifre.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", pin.encode("ascii"), salt, PIN_ITERATIONS
    )
    return {"pin_salt": salt.hex(), "pin_hash": digest.hex()}


def pin_matches(pin: str, booking: dict) -> bool:
    """Constant-time digest comparison for a reservation PIN."""
    if not (pin.isascii() and pin.isdecimal() and len(pin) == PIN_DIGITS):
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("ascii"),
        bytes.fromhex(booking["pin_salt"]),
        PIN_ITERATIONS,
    )
    return hmac.compare_digest(digest, bytes.fromhex(booking["pin_hash"]))


def make_gate(
    name: str,
    entity_id: str,
    action: str,
    kind: str = "private",
    enabled: bool = False,
) -> dict:
    """Validate and create an explicitly mapped Home Assistant gate."""
    name = name.strip()
    if not (1 <= len(name) <= 80):
        raise ValueError("Il nome del varco deve avere 1-80 caratteri.")
    if action not in ALLOWED_ACTIONS:
        raise ValueError("Azione non ammessa: utilizzare script, button o lock.")
    if not entity_id.startswith(ALLOWED_ACTIONS[action] + "."):
        raise ValueError("L'entità non corrisponde all'azione.")
    if kind not in ("shared", "private"):
        raise ValueError("Tipologia varco non valida.")
    return {
        "id": str(uuid4()),
        "name": name,
        "entity_id": entity_id,
        "action": action,
        "kind": kind,
        "enabled": enabled,
        "token": secrets.token_urlsafe(24),
    }


def make_booking(
    room: str, start: str, end: str, gate_ids: list[str], pin: str
) -> dict:
    """Validate reservation window, allowed gates and PIN."""
    if not room or len(room) > 80:
        raise ValueError("Camera non valida.")
    starts, ends = as_utc(start), as_utc(end)
    if starts >= ends:
        raise ValueError("Il check-out deve seguire il check-in.")
    if not gate_ids or len(gate_ids) != len(set(gate_ids)):
        raise ValueError("Selezionare varchi distinti.")
    if (ends - starts).days > 90:
        raise ValueError("Per la demo, durata massima 90 giorni.")
    return {
        "id": str(uuid4()),
        "room": room.strip(),
        "start": starts.isoformat(),
        "end": ends.isoformat(),
        "gate_ids": gate_ids,
        "revoked": False,
        **seal_pin(pin),
    }


def booking_allows(booking: dict, gate_id: str, now: datetime | None = None) -> bool:
    """Server-side ACL; an enabled gate is also required at call time."""
    current = now or datetime.now(timezone.utc)
    return (
        not booking["revoked"]
        and gate_id in booking["gate_ids"]
        and as_utc(booking["start"]) <= current < as_utc(booking["end"])
    )


def public_booking(booking: dict) -> dict:
    """Remove all credential fields before returning to the manager."""
    return {k: v for k, v in booking.items() if k not in ("pin_salt", "pin_hash")}
