"""Config flow for CL B&B Manager."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import DOMAIN
from .permissions import MAX_OPERATORS, OPTION_OPERATOR_USERS, operator_user_ids
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
        # Only active, human, non-admin Home Assistant accounts are eligible.
        # Administrators retain access automatically and need no assignment.
        users = await self.hass.auth.async_get_users()
        eligible = {
            str(user.id): str(getattr(user, "name", "") or user.id)
            for user in users
            if bool(getattr(user, "is_active", False))
            and not bool(getattr(user, "is_admin", False))
            and not bool(getattr(user, "system_generated", False))
        }
        errors = {}
        if user_input is not None:
            selected = user_input.get(OPTION_OPERATOR_USERS, [])
            if (
                not isinstance(selected, list)
                or len(selected) > MAX_OPERATORS
                or len(selected) != len(set(selected))
                or any(user_id not in eligible for user_id in selected)
            ):
                errors["base"] = "invalid_operator_users"
            enabled = bool(user_input.get("public_pilot_enabled", False))
            origin = str(user_input.get("public_pilot_origin", "")).strip()
            origin = self.hass.config.external_url or origin
            if enabled:
                try:
                    origin = validate_public_origin(origin)
                except ValueError:
                    errors["base"] = "invalid_public_origin"
            if not errors:
                # Keep any future options managed by other features.
                updated = dict(self.config_entry.options)
                updated.update({
                    "public_pilot_enabled": enabled,
                    "public_pilot_origin": origin if enabled else "",
                    OPTION_OPERATOR_USERS: selected,
                })
                return self.async_create_entry(title="", data=updated)

        schema = vol.Schema({
            vol.Required(
                "public_pilot_enabled",
                default=self.config_entry.options.get("public_pilot_enabled", False)
            ): bool,
            vol.Optional(
                "public_pilot_origin",
                default=self.hass.config.external_url or self.config_entry.options.get("public_pilot_origin", "")
            ): str,
            vol.Optional(
                OPTION_OPERATOR_USERS,
                default=[user_id for user_id in operator_user_ids(self.config_entry.options) if user_id in eligible],
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=user_id, label=name)
                        for user_id, name in sorted(eligible.items(), key=lambda item: item[1].casefold())
                    ],
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
