"""Pure, explicit and repeatable migration from legacy single-property records.

Callers must create a backup of the original persisted store before saving a
migrated copy. This module never writes to Home Assistant storage.
"""
from __future__ import annotations

from copy import deepcopy

from .property_scope import require_property_id

SCHEMA_VERSION = 3
RECORD_COLLECTIONS = ("gates", "bookings", "events", "access_history")


def migrate_legacy_data(data: dict, property_id: str, property_name: str) -> dict:
    """Return a migrated copy; reject ambiguous or partially scoped records."""
    require_property_id(property_id)
    if not isinstance(property_name, str) or not 1 <= len(property_name.strip()) <= 80:
        raise ValueError("Nome struttura non valido.")
    if not isinstance(data, dict):
        raise ValueError("Archivio non valido.")
    current = data.get("schema_version", 1)
    if type(current) is not int or current not in (1, 2, SCHEMA_VERSION):
        raise ValueError("Versione archivio non supportata.")
    result = deepcopy(data)
    for collection in RECORD_COLLECTIONS:
        records = result.get(collection, [])
        if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
            raise ValueError("Collezione archivio non valida.")
        for record in records:
            existing = record.get("property_id")
            if existing is not None and existing != property_id:
                raise ValueError("Record associato a un'altra struttura.")
            record["property_id"] = property_id
        result[collection] = records
    properties = result.get("properties", [])
    if properties:
        if properties != [{"id": property_id, "name": property_name.strip()}]:
            raise ValueError("Catalogo strutture ambiguo.")
    result["properties"] = [{"id": property_id, "name": property_name.strip()}]
    result["schema_version"] = SCHEMA_VERSION
    return result
