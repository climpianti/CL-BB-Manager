"""CL B&B Manager: local admin panel and booking management alpha.

This alpha never executes door opening services and exposes no public QR endpoint.
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
from .const import DOMAIN, MAX_EVENTS, PANEL_PATH, PANEL_RESOURCE, STORE_KEY
from .models import public_booking


class BBManager:
    """Single-instance booking store with serialized mutation and audit events."""

    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry
        self.store = Store(hass, 1, STORE_KEY)
        self.lock = asyncio.Lock()
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

    def summary(self):
        """Return a redacted and detached representation to the manager UI."""
        gates = [
            {key: gate[key] for key in (
                "id", "name", "entity_id", "action", "kind", "enabled"
            )}
            for gate in self.data["gates"]
        ]
        return {
            "structure": self.entry.data.get("structure_name", "B&B"),
            "gates": gates,
            "bookings": [public_booking(b) for b in self.data["bookings"]],
            "events": list(self.data["events"][-MAX_EVENTS:]),
            "guest_portal": "disabled",
            "hardware_control": "disabled",
        }


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up the integration, admin-only panel and API."""
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
        domain_data["routes_registered"] = True

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_PATH,
        webcomponent_name="cl-bb-manager-panel",
        module_url=PANEL_RESOURCE,
        sidebar_title="CL B&B Manager",
        sidebar_icon="mdi:bed",
        require_admin=True,
        config_panel_domain=DOMAIN,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload only the panel, retaining routes for safe reload in this process."""
    frontend.async_remove_panel(hass, PANEL_PATH, warn_if_unknown=False)
    hass.data.get(DOMAIN, {}).pop("manager", None)
    return True
