"""CL B&B Manager: installation-safe alpha foundation.

Public PIN/QR endpoints and door triggers are deliberately NOT exposed yet.
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORE_KEY


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Initialize isolated local data for a future reservation backend."""
    store = Store(hass, 1, STORE_KEY)
    data = await store.async_load()
    if data is None:
        data = {"gates": [], "bookings": [], "events": []}
        await store.async_save(data)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "store": store,
        "data": data,
        "structure_name": entry.data["structure_name"],
    }
    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload the isolated instance without changing other HA entities."""
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True
