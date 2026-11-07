"""CL B&B Manager: admin panel and isolated short-lived LAN QR test sessions.

The permanent guest portal is disabled. Only five demo virtual scripts can run.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .api import register_commands
from .guest import GuestView
from .demo_http import DemoPortalView
from .public_http import PublicPilotView
from .const import DOMAIN, MAX_EVENTS, PANEL_PATH, PANEL_RESOURCE, STORE_KEY
from .models import public_booking


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
        self.data = {"gates": [], "bookings": [], "events": []}

    async def async_load(self):
        """Load persistent data after Home Assistant starts."""
        saved = await self.store.async_load()
        if saved is not None:
            self.data = saved
        for key in ("gates", "bookings", "events"):
            self.data.setdefault(key, [])

    async def async_save(self):
        """Persist a completed mutation; call while holding lock."""
        await self.store.async_save(self.data)

    def audit(self, event: str, details: str = ""):
        """Record administrative events only; never PINs or login credentials."""
        self.data["events"].append({
            "at": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "details": details[:160],
        })
        self.data["events"] = self.data["events"][-MAX_EVENTS:]

    def summary(self, role: str = "admin"):
        """Return minimal panel data; operators do not receive HA mappings or audit."""
        from .guest import DEMO_SCRIPTS

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
            if is_admin:
                item.update({
                    key: gate[key] for key in ("entity_id", "action")
                })
            gates.append(item)
        return {
            "structure": self.entry.data.get("structure_name", "B&B"),
            "gates": gates,
            "bookings": [public_booking(b) for b in self.data["bookings"]],
            "events": list(self.data["events"][-MAX_EVENTS:]) if is_admin else [],
            "role": role,
            "guest_portal": "disabled",
            "public_pilot": "enabled" if self.entry.options.get("public_pilot_enabled", False) else "disabled",
            "hardware_control": "disabled",
        }


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up the integration, restricted panel and permission-checked API."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    manager = BBManager(hass, entry)
    await manager.async_load()
    domain_data["manager"] = manager

    if not domain_data.get("routes_registered"):
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                "/cl_bb_manager_static",
                str(Path(__file__).parent / "frontend"),
                False,
            )
        ])
        register_commands(hass)
        hass.http.register_view(GuestView())
        hass.http.register_view(DemoPortalView())
        hass.http.register_view(PublicPilotView())
        domain_data["routes_registered"] = True

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_PATH,
        webcomponent_name="cl-bb-manager-panel",
        module_url=PANEL_RESOURCE,
        # Avoid advertising a panel that should only be reached by Core's
        # per-user shortcut. All WebSocket actions enforce the operator ACL.
        sidebar_title=None,
        sidebar_icon="mdi:bed",
        require_admin=False,
        config_panel_domain=DOMAIN,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload only the panel, retaining routes for safe reload in this process."""
    frontend.async_remove_panel(hass, PANEL_PATH, warn_if_unknown=False)
    hass.data.get(DOMAIN, {}).pop("manager", None)
    return True
