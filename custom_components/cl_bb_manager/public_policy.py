"""Strict policy for opt-in, short-lived, virtual-only HTTPS demo sessions.

This is NOT the permanent guest portal, and it grants no physical-access capability.
"""
from __future__ import annotations

import re
import secrets
import time
from urllib.parse import urlsplit

PUBLIC_DEMO_SECONDS = 600
MAX_PUBLIC_SESSIONS = 5
_DNS_NAME = re.compile(
    r"(?i)^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


def validate_public_origin(value: str) -> str:
    """Require a plain HTTPS DNS origin, no path, port, credentials, or query."""
    if not isinstance(value, str) or len(value) > 256:
        raise ValueError("Indicare un dominio pubblico HTTPS valido.")
    value = value.strip()
    try:
        part = urlsplit(value)
        port = part.port
    except ValueError as exc:
        raise ValueError("URL HTTPS non valido.") from exc
    host = part.hostname
    if (
        part.scheme != "https"
        or not host
        or not _DNS_NAME.fullmatch(host)
        or port is not None
        or part.username is not None
        or part.password is not None
        or part.path not in ("", "/")
        or part.query
        or part.fragment
        or part.netloc.lower() != host.lower()
    ):
        raise ValueError("Usare solo https://nome.dominio.tld senza percorso o porta.")
    return "https://" + host.lower()


def create_public_session(gate_id: str, origin: str, *, now: float | None = None):
    approved = validate_public_origin(origin)
    token = secrets.token_urlsafe(32)
    return token, {
        "gate_id": gate_id,
        "form_csrf": secrets.token_urlsafe(32),
        "origin": approved,
        "host": approved.removeprefix("https://"),
        "expires": (time.time() if now is None else now) + PUBLIC_DEMO_SECONDS,
    }


def valid_public_session(session: dict | None, host: str, configured_origin: str,
                         *, now: float | None = None) -> bool:
    """Fail closed if opt-in is missing, hostname changes, or session expires."""
    try:
        approved = validate_public_origin(configured_origin)
    except ValueError:
        return False
    current = time.time() if now is None else now
    return bool(
        isinstance(session, dict)
        and isinstance(session.get("expires"), (int, float))
        and current < session["expires"]
        and session.get("origin") == approved
        and session.get("host") == approved.removeprefix("https://")
        and host.lower() == session.get("host")
    )
