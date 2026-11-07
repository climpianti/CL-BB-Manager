"""Central, fail-closed user policy for the CL B&B Manager operator role.

Only Home Assistant administrators can configure mappings and integration options.
Explicitly selected active users can manage reservations, PINs and temporary QR.
"""
from __future__ import annotations

from typing import Any

OPTION_OPERATOR_USERS = "operator_user_ids"
MAX_OPERATORS = 20


def operator_user_ids(options: Any) -> tuple[str, ...]:
    """Read valid IDs from an integration options mapping; ignore malformed data."""
    if not isinstance(options, dict):
        return ()
    raw = options.get(OPTION_OPERATOR_USERS, [])
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(dict.fromkeys(
        value for value in raw
        if isinstance(value, str) and 0 < len(value) <= 128
    ))[:MAX_OPERATORS]


def user_role(user: Any, options: Any) -> str | None:
    """Return 'admin'/'operator' for active allowed HA users, otherwise None."""
    if user is None or not bool(getattr(user, "is_active", False)):
        return None
    if bool(getattr(user, "is_admin", False)):
        return "admin"
    user_id = str(getattr(user, "id", "") or "")
    if user_id and user_id in operator_user_ids(options):
        return "operator"
    return None
