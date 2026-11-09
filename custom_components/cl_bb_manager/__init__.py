"""CL B&B Manager: reservations, operator permissions and permanent door access."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .api import register_commands
from .access_history import public_access_history
from .physical_http import PhysicalGuestView
from .const import DOMAIN, MAX_EVENTS, PANEL_PATH, PANEL_RESOURCE, STORE_KEY
from .models import public_booking
from .qr_branding import branding_status
from .hardware_staging import read_candidate
from .property_migration import migrate_legacy_data, SCHEMA_VERSION
from .property_scope import active_property_id, new_property, require_property_id, require_record_scope


class BBManager:
    """Single-instance booking store with serialized mutation and audit events."""

    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry
        self.store = Store(hass, 1, STORE_KEY)
        self.lock = asyncio.Lock()
        # In-memory, expiring administrator-issued LAN QR sessions.
        # Deliberately not persisted across HA restarts.
        self.demo_sessions = {}
        self.public_demo_sessions = {}
        # Volatile, one-use browser form proofs; QR gate tokens stay persisted.
        self.permanent_forms = {}
        # Independent one-use forms for the physical guest endpoint.
        self.physical_forms = {}
        self.data = {"gates": [], "bookings": [], "events": [], "access_history": []}

    async def async_load(self):
        """Load persistent data after Home Assistant starts."""
        saved = await self.store.async_load()
        if saved is not None:
            self.data = saved
        # Single-property migration, also used to initialize an empty install.
        # The store is only written after a fully validated copy is prepared.
        if self.data.get("schema_version") != SCHEMA_VERSION:
            properties = self.data.get("properties", [])
            if properties:
                if not isinstance(properties, list) or len(properties) != 1:
                    raise ValueError("Archivio multi-struttura ambiguo.")
                property_id = require_property_id(properties[0]["id"])
            else:
                property_id = new_property(
                    self.entry.data.get("structure_name", "B&B")
                )["id"]
            migrated = migrate_legacy_data(
                self.data, property_id,
                self.entry.data.get("structure_name", "B&B"),
            )
            await self.store.async_save(migrated)
            self.data = migrated
        for key in ("gates", "bookings", "events", "access_history"):
            self.data.setdefault(key, [])
        # An already migrated v2 store is not rewritten implicitly.
        # Invalid ownership is rejected before exposing any access endpoint.
        property_id = self.property_id
        for key in ("gates", "bookings", "events", "access_history"):
            if not isinstance(self.data[key], list):
                raise ValueError("Archivio strutture corrotto.")
            for record in self.data[key]:
                require_record_scope(record, property_id)

    @property
    def property_id(self) -> str:
        """The trusted server-side property identifier."""
        return active_property_id(self.data)

    async def async_save(self):
        """Persist a completed mutation; call while holding lock."""
        await self.store.async_save(self.data)

    def audit(self, event: str, details: str = ""):
        """Record administrative events only; never PINs or login credentials."""
        self.data["events"].append({
            "at": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "details": details[:160],
            "property_id": self.property_id,
        })
        self.data["events"] = self.data["events"][-MAX_EVENTS:]

    def summary(self, role: str = "admin"):
        """Return minimal panel data with booking-scoped access history."""
        from .guest import DEMO_SCRIPTS

        property_id = self.property_id
        for key in ("gates", "bookings", "events", "access_history"):
            for record in self.data[key]:
                require_record_scope(record, property_id)
        is_admin = role == "admin"
        gates = []
        for gate in self.data["gates"]:
            item = {
                key: gate[key] for key in (
                    "id", "name", "kind", "enabled"
                )
            }
            item["demo_allowed"] = bool(
                gate.get("enabled")
                and gate.get("action") == "script.turn_on"
                and gate.get("entity_id") in DEMO_SCRIPTS
            )
            item["physical_qr_prepared"] = bool(gate.get("physical_token"))
            item["physical_enabled"] = gate.get("physical_enabled") is True
            item["provider"] = "shelly" if gate.get("shelly_binding") else "home_assistant" if gate.get("entity_binding") else "existing"
            if is_admin:
                item.update({
                    key: gate[key] for key in ("entity_id", "action")
                })
                item["hardware_candidate"] = read_candidate(gate)
                item["physical_qr_prepared"] = bool(gate.get("physical_token"))
                item["physical_enabled"] = gate.get("physical_enabled") is True
                if gate.get("shelly_binding"):
                    item["pulse_seconds"] = gate["shelly_binding"].get("pulse_seconds")
                    from .shelly_gate import resolve_binding
                    try:
                        item["entity_id"] = resolve_binding(self.hass, gate["shelly_binding"]).entity_id
                    except ValueError:
                        pass
                if gate.get("entity_binding"):
                    from .entity_gate import resolve_binding
                    try:
                        item["entity_id"] = resolve_binding(self.hass, gate["entity_binding"])
                    except ValueError:
                        pass
                    item["pulse_seconds"] = gate["entity_binding"].get("pulse_seconds")
                    item["switch_mode"] = gate["entity_binding"].get("switch_mode")
                    item["recovery_pending"] = gate["id"] in self.data.get("pending_entity_pulses", {})
            gates.append(item)
        return {
            **({"qr_branding": branding_status(self.data, preview=True)} if is_admin else {}),
            "structure": self.entry.data.get("structure_name", "B&B"),
            "gates": gates,
            "bookings": [public_booking(b) for b in self.data["bookings"]],
            "events": list(self.data["events"][-MAX_EVENTS:]) if is_admin else [],
            "access_history": public_access_history(self.data),
            "role": role,
            "public_origin": self.hass.config.external_url
                or self.entry.options.get("public_origin")
                or self.entry.options.get("public_pilot_origin", ""),
            "public_access_enabled": self.entry.options.get("public_access_enabled", True),
            "guest_portal": "disabled",
            "public_pilot": "enabled" if self.entry.options.get("public_pilot_enabled", False) else "disabled",
            "permanent_pilot": "enabled" if self.entry.options.get("permanent_pilot_enabled", False) else "disabled",
            "hardware_control": "enabled" if (self.data.get("physical_access_enabled") is True and any(g.get("physical_enabled") is True for g in self.data["gates"])) else "disabled",
        }


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up the integration, restricted panel and permission-checked API."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    manager = BBManager(hass, entry)
    await manager.async_load()
    domain_data["manager"] = manager
    # Recover interrupted generic relay pulses using OFF only. Unavailable or
    # replaced devices keep a pending marker and cannot receive a fresh ON.
    from .entity_gate import async_recover_on_lifecycle
    async with manager.lock:
        await async_recover_on_lifecycle(manager)

    if not domain_data.get("routes_registered"):
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                "/cl_bb_manager_static",
                str(Path(__file__).parent / "frontend"),
                False,
            )
        ])
        register_commands(hass)
        # Old test-only URLs are intentionally no longer published. Existing
        # physical URLs retain the same path and stored credentials.
        hass.http.register_view(PhysicalGuestView())
        domain_data["routes_registered"] = True

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_PATH,
        webcomponent_name="cl-bb-manager-panel",
        module_url=PANEL_RESOURCE,
        # Standalone installation: also reachable without CL Control Core.
        # Each WS handler enforces the current operator/admin ACL server-side.
        sidebar_title="CL B&B Manager",
        sidebar_icon="mdi:bed",
        require_admin=False,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload only the panel, retaining routes for safe reload in this process."""
    frontend.async_remove_panel(hass, PANEL_PATH, warn_if_unknown=False)
    manager = hass.data.get(DOMAIN, {}).pop("manager", None)
    if manager is not None:
        async with manager.lock:
            from .entity_gate import async_recover_on_lifecycle
            await async_recover_on_lifecycle(manager)
    return True

