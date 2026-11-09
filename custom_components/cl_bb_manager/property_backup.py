"""Pure migration snapshot and rollback validation.

No file or Home Assistant storage writes happen here. The caller must keep
snapshots in a protected location before committing a migrated store.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

SNAPSHOT_FORMAT = "cl_bb_manager.migration_snapshot.v1"


def _serialize(data: dict) -> bytes:
    if not isinstance(data, dict):
        raise ValueError("Archivio non valido.")
    return json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def make_snapshot(data: dict) -> dict:
    """Create an immutable-by-convention, integrity-protected data snapshot."""
    encoded = _serialize(data)
    return {
        "format": SNAPSHOT_FORMAT,
        "sha256": sha256(encoded).hexdigest(),
        "data": deepcopy(data),
    }


def restore_snapshot(snapshot: dict) -> dict:
    """Return a fresh copy only if snapshot integrity checks succeed."""
    if not isinstance(snapshot, dict) or set(snapshot) != {"format", "sha256", "data"}:
        raise ValueError("Snapshot non valido.")
    if snapshot["format"] != SNAPSHOT_FORMAT:
        raise ValueError("Formato snapshot non supportato.")
    encoded = _serialize(snapshot["data"])
    if sha256(encoded).hexdigest() != snapshot["sha256"]:
        raise ValueError("Integrita snapshot non valida.")
    return deepcopy(snapshot["data"])


def prepare_migration(data: dict, property_id: str, property_name: str) -> tuple[dict, dict]:
    """Return (original snapshot, migrated data) without mutating storage."""
    from .property_migration import migrate_legacy_data

    snapshot = make_snapshot(data)
    migrated = migrate_legacy_data(data, property_id, property_name)
    restore_snapshot(snapshot)
    return snapshot, migrated
