"""Safety rules for stable printable virtual-only QR links.

The printed QR contains a persistent gate token, never a PIN or a form CSRF.
Every browser visit receives a separate, short-lived one-use form nonce.
"""
from __future__ import annotations

import secrets
import time

from .public_policy import validate_public_origin

FORM_SECONDS = 600
MAX_FORMS = 200


def permanent_url(origin: str, token: str) -> str:
    """Produce a canonical HTTPS URL with an opaque gate token."""
    validated = validate_public_origin(origin)
    if not isinstance(token, str) or len(token) < 20 or len(token) > 100:
        raise ValueError("Token varco non valido.")
    return validated + "/api/cl_bb_manager/permanent-demo/" + token


def issue_form(forms: dict, gate_id: str, *, now: float | None = None) -> str:
    """Issue a bounded, single-use CSRF proof without changing the QR token."""
    instant = time.time() if now is None else now
    if not isinstance(forms, dict):
        raise ValueError("Archivio moduli non valido.")
    expired = [key for key, item in forms.items() if (
        not isinstance(item, dict) or item.get("expires", 0) <= instant
    )]
    for key in expired:
        forms.pop(key, None)
    if len(forms) >= MAX_FORMS:
        raise ValueError("Troppe sessioni di accesso in attesa.")
    csrf = secrets.token_urlsafe(32)
    forms[csrf] = {"gate_id": gate_id, "expires": instant + FORM_SECONDS}
    return csrf


def consume_form(forms: dict, csrf: str, gate_id: str, *, now: float | None = None) -> bool:
    """Atomically consume a nonce within manager.lock, even if PIN fails."""
    if not isinstance(csrf, str) or len(csrf) < 32 or len(csrf) > 128:
        return False
    record = forms.pop(csrf, None)
    instant = time.time() if now is None else now
    return bool(
        isinstance(record, dict)
        and record.get("gate_id") == gate_id
        and isinstance(record.get("expires"), (int, float))
        and record["expires"] > instant
    )
