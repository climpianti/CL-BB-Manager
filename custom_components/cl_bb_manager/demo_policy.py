"""Pure helpers for isolated LAN-only CL B&B QR demo sessions."""
from __future__ import annotations

import ipaddress
import re
import secrets
import time
from urllib.parse import urlsplit

DEMO_DURATION_SECONDS = 600
MAX_DEMO_SESSIONS = 5
_PRIVATE_NETS = tuple(ipaddress.ip_network(net) for net in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
))
_MDNS = re.compile(r"(?i)^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*\.local$")


def is_lan_name(host: str | None) -> bool:
    """Allow explicit RFC1918 addresses or mDNS .local names, never public DNS."""
    if not host:
        return False
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return bool(_MDNS.fullmatch(host))
    return isinstance(addr, ipaddress.IPv4Address) and any(
        addr in network for network in _PRIVATE_NETS
    )


def is_lan_peer(peer: str | None) -> bool:
    """Accept direct LAN peers; HA's local proxy may use loopback."""
    if not peer:
        return False
    try:
        addr = ipaddress.ip_address(peer)
    except ValueError:
        return False
    return addr.is_loopback or is_lan_name(peer)


def validate_demo_origin(url: str) -> tuple[str, str]:
    """Return normalized origin and Host, or reject public/ambiguous URLs."""
    if not isinstance(url, str) or len(url) > 256:
        raise ValueError("Indicare un URL locale valido.")
    trimmed = url.strip().rstrip("/")
    try:
        p = urlsplit(trimmed)
        port = p.port
    except ValueError as err:
        raise ValueError("Porta URL non valida.") from err
    if (
        p.scheme not in ("http", "https")
        or not is_lan_name(p.hostname)
        or p.username is not None or p.password is not None
        or p.path or p.query or p.fragment
        or port == 0
    ):
        raise ValueError(
            "Usa solo un indirizzo LAN privato o *.local, senza percorso."
        )
    hostname = p.hostname.lower()
    host = hostname + (f":{port}" if port else "")
    return f"{p.scheme}://{host}", host


def make_demo_session(gate_id: str, origin: str, now: float | None = None) -> tuple[str, dict]:
    """Issue a nonpersistent, unguessable 10-minute test link."""
    validated, host = validate_demo_origin(origin)
    token = secrets.token_urlsafe(32)
    return token, {
        "gate_id": gate_id,
        "form_csrf": secrets.token_urlsafe(32),
        "origin": validated,
        "host": host,
        "expires": (time.time() if now is None else now) + DEMO_DURATION_SECONDS,
    }


def valid_demo_session(session: dict | None, host: str, peer: str, now: float | None = None) -> bool:
    """Session must be unexpired and accessed via the bound LAN hostname."""
    current = time.time() if now is None else now
    return bool(
        isinstance(session, dict)
        and isinstance(session.get("expires"), (int, float))
        and current < session["expires"]
        and host.lower() == session.get("host")
        and is_lan_peer(peer)
    )
