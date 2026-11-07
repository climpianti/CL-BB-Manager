"""Config flow for CL B&B Manager."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN
from .public_policy import validate_public_origin


class CLBBManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create one local B&B manager instance."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return CLBBManagerOptionsFlow()

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


class CLBBManagerOptionsFlow(config_entries.OptionsFlow):
    """Require explicit administrator opt-in and a pinned HTTPS DNS origin."""

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            enabled = bool(user_input.get("public_pilot_enabled", False))
            origin = str(user_input.get("public_pilot_origin", "")).strip()
            origin = self.hass.config.external_url or origin
            if enabled:
                try:
                    origin = validate_public_origin(origin)
                except ValueError:
                    errors["base"] = "invalid_public_origin"
            if not errors:
                return self.async_create_entry(title="", data={
                    "public_pilot_enabled": enabled,
                    "public_pilot_origin": origin if enabled else "",
                })

        schema = vol.Schema({
            vol.Required(
                "public_pilot_enabled",
                default=self.config_entry.options.get("public_pilot_enabled", False)
            ): bool,
            vol.Optional(
                "public_pilot_origin",
                default=self.hass.config.external_url or self.config_entry.options.get("public_pilot_origin", "")
            ): str,
        })
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
