"""Pure property-scoping primitives for the future multi-property data migration.

No stored records are changed by importing or calling these helpers.
"""
from __future__ import annotations

from uuid import UUID, uuid4


def new_property(name: str) -> dict:
    """Create a property with an immutable, opaque identifier."""
    if not isinstance(name, str):
        raise ValueError("Nome struttura non valido.")
    cleaned = name.strip()
    if not 1 <= len(cleaned) <= 80:
        raise ValueError("Nome struttura non valido.")
    return {"id": str(uuid4()), "name": cleaned}


def require_property_id(property_id: str) -> str:
    """Reject absent, malformed or noncanonical identifiers."""
    if not isinstance(property_id, str):
        raise ValueError("Identificativo struttura non valido.")
    try:
        parsed = UUID(property_id)
    except (ValueError, AttributeError) as err:
        raise ValueError("Identificativo struttura non valido.") from err
    if parsed.version != 4 or str(parsed) != property_id:
        raise ValueError("Identificativo struttura non valido.")
    return property_id


def belongs_to_property(record: dict, property_id: str) -> bool:
    """Fail closed for legacy/unscoped records until migration is explicit."""
    require_property_id(property_id)
    return (
        isinstance(record, dict)
        and record.get("property_id") == property_id
    )


def assert_gate_scope(
    gates: list[dict], gate_ids: list[str], property_id: str
) -> None:
    """Every requested gate must exist exactly once in the selected property."""
    require_property_id(property_id)
    if not gate_ids or len(gate_ids) != len(set(gate_ids)):
        raise ValueError("Selezionare varchi distinti.")
    if any(not isinstance(gate_id, str) or not gate_id for gate_id in gate_ids):
        raise ValueError("Identificativo varco non valido.")
    for gate_id in gate_ids:
        matches = [gate for gate in gates if isinstance(gate, dict) and gate.get("id") == gate_id]
        if len(matches) != 1 or not belongs_to_property(matches[0], property_id):
            raise ValueError("Varco non appartenente alla struttura.")


def active_property_id(data: dict) -> str:
    """Return the only configured property; reject ambiguous/corrupt stores."""
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 2:
        raise ValueError("Versione archivio strutture non valida.")
    properties = data.get("properties")
    if not isinstance(properties, list) or len(properties) != 1 or not isinstance(properties[0], dict):
        raise ValueError("Configurazione strutture ambigua.")
    record = properties[0]
    if not isinstance(record.get("name"), str) or not 1 <= len(record["name"].strip()) <= 80:
        raise ValueError("Nome struttura non valido.")
    return require_property_id(record.get("id"))


def require_record_scope(record: dict, property_id: str) -> dict:
    """Reject another property's records and unscoped legacy records."""
    if not belongs_to_property(record, property_id):
        raise ValueError("Record non appartenente alla struttura.")
    return record
