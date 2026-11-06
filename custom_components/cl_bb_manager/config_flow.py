"""Config flow for CL B&B Manager."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN


class CLBBManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create one local B&B manager instance."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Register an instance through the Home Assistant UI."""
        await self.async_set_unique_id("cl_bb_manager_instance")
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(
                title=user_input["structure_name"], data=user_input
            )
        schema = vol.Schema(
            {vol.Required("structure_name", default="Struttura Demo"): str}
        )
        return self.async_show_form(step_id="user", data_schema=schema)
