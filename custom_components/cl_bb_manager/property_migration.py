"""Pure helpers for a future multi-property storage migration.

No Home Assistant runtime writes occur here. A caller must explicitly persist
the returned copy after validating and backing up its original store.
"""
from __future__ import annotations

from copy import deepcopy
from uuid import UUID, uuid5

PROPERTY_NAMESPACE = UUID("49d6d832-510b-4a46-966b-6226f5c1cbe3")
SCHEMA_VERSION = 2


def default_property_id(installation_id: str) -> str:
    """Derive a stable, non-secret property ID for a single installation."""
    if not isinstance(installation_id, str) or not installation_id.strip():
        raise ValueError("Installation ID must be a non-empty string.")
    return str(uuid5(PROPERTY_NAMESPACE, installation_id))


def preview_single_property_migration(
    stored: dict, *, installation_id: str, structure_name: str
) -> dict:
    """Return an isolated migrated copy; never mutate the existing store.

    This is a preparation utility, not an automatic production migration.
    """
    if not isinstance(stored, dict):
        raise ValueError("Store must be a mapping.")
    if not isinstance(structure_name, str) or not structure_name.strip():
        raise ValueError("Structure name is required.")
    if stored.get("schema_version") not in (None, 1):
        raise ValueError("Unsupported schema version.")
    for collection in ("gates", "bookings", "events", "access_history"):
        if not isinstance(stored.get(collection, []), list):
            raise ValueError(f"Invalid {collection} collection.")
    result = deepcopy(stored)
    property_id = default_property_id(installation_id)
    for collection in ("gates", "bookings", "events", "access_history"):
        for record in result.get(collection, []):
            if not isinstance(record, dict):
                raise ValueError(f"Invalid record in {collection}.")
            if "property_id" in record and record["property_id"] != property_id:
                raise ValueError("Conflicting property assignment.")
            record["property_id"] = property_id
    result["properties"] = [{"id": property_id, "name": structure_name.strip()}]
    result["schema_version"] = SCHEMA_VERSION
    return result
