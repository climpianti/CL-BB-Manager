"""CL B&B Manager HA UI configuration and guarded administrative options."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import DOMAIN, MAX_GATES
from .gate_management import check_gate_removal, native_mapping_changed
from .property_scope import require_record_scope
from .models import make_gate
from .permissions import MAX_OPERATORS, OPTION_OPERATOR_USERS, operator_user_ids
from .public_policy import validate_public_origin


class CLBBManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create one local B&B manager instance."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return CLBBManagerOptionsFlow()

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id("cl_bb_manager_instance")
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(
                title=user_input["structure_name"], data=user_input
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("structure_name", default="Nuova struttura"): str
            }),
        )


class CLBBManagerOptionsFlow(config_entries.OptionsFlow):
    """Administrative menu for HTTPS/operators and persisted gate mappings."""

    def _manager(self):
        return self.hass.data.get(DOMAIN, {}).get("manager")

    def _unchanged_options(self):
        """Gate edits are saved in Manager's own Store, not in entry options."""
        return dict(self.config_entry.options)

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init", menu_options=["access", "gates"]
        )

    async def async_step_access(self, user_input=None):
        """Persist operator selection without changing existing gates or grants."""
        users = await self.hass.auth.async_get_users()
        eligible = {
            str(user.id): str(getattr(user, "name", "") or user.id)
            for user in users
            if bool(getattr(user, "is_active", False))
            and not bool(getattr(user, "is_admin", False))
            and not bool(getattr(user, "system_generated", False))
        }
        previous = [uid for uid in operator_user_ids(self.config_entry.options) if uid in eligible]
        errors = {}
        if user_input is not None:
            selected = user_input.get(OPTION_OPERATOR_USERS, [])
            if (not isinstance(selected, list) or len(selected) > MAX_OPERATORS
                or len(selected) != len(set(selected))
                or any(not isinstance(uid, str) or uid not in eligible for uid in selected)):
                errors["base"] = "invalid_operator_users"
            enabled = user_input.get("public_access_enabled", True) is True
            origin = self.hass.config.external_url or str(user_input.get("public_origin", "")).strip()
            if enabled:
                try:
                    origin = validate_public_origin(origin)
                except ValueError:
                    errors["base"] = "invalid_public_origin"
            if not errors:
                updated = self._unchanged_options()
                updated.update(public_access_enabled=enabled, public_origin=origin,
                               **{OPTION_OPERATOR_USERS: selected})
                return self.async_create_entry(title="", data=updated)
        origin = self.hass.config.external_url or self.config_entry.options.get("public_origin") or self.config_entry.options.get("public_pilot_origin", "")
        return self.async_show_form(
            step_id="access", errors=errors,
            description_placeholders={"current_operators": ", ".join(eligible[uid] for uid in previous) or "Nessuno"},
            data_schema=vol.Schema({
                vol.Required("public_access_enabled", default=self.config_entry.options.get("public_access_enabled", True)): bool,
                vol.Optional("public_origin", default=origin): str,
                vol.Required(OPTION_OPERATOR_USERS, default=list(previous)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=[
                        selector.SelectOptionDict(value=uid, label=name)
                        for uid, name in sorted(eligible.items(), key=lambda item: item[1].casefold())
                    ], multiple=True, mode=selector.SelectSelectorMode.DROPDOWN)),
            }),
        )

    async def async_step_gates(self, user_input=None):
        """Gate management lives behind the HA integration options cog."""
        if self._manager() is None:
            return self.async_abort(reason="not_ready")
        return self.async_show_menu(
            step_id="gates", menu_options=["add_gate", "edit_gate", "remove_gate"]
        )

    async def async_step_add_gate(self, user_input=None):
        return self.async_show_menu(step_id="add_gate", menu_options=["add_entity_gate", "add_shelly_gate"])

    async def async_step_add_entity_gate(self, user_input=None):
        from .gate_setup import async_add_entity_gate
        from .entity_gate import ACTIONS
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="not_ready")
        errors = {}
        if user_input is not None:
            try:
                if user_input.get("confirm") is not True:
                    raise ValueError("Conferma l'associazione del varco.")
                await async_add_entity_gate(manager, name=user_input["name"], entity_id=user_input["entity_id"],
                    action=user_input["action"], kind=user_input["kind"], seconds=user_input.get("pulse_seconds", 2),
                    switch_mode=user_input.get("switch_mode", "ha_pulse"),
                    confirm_device_pulse=user_input.get("confirm_device_pulse", False))
            except (KeyError, TypeError, ValueError):
                errors["base"] = "invalid_gate"
            else:
                return self.async_create_entry(title="", data=self._unchanged_options())
        return self.async_show_form(step_id="add_entity_gate", errors=errors, data_schema=vol.Schema({
            vol.Required("name"): str,
            vol.Required("entity_id"): selector.EntitySelector(selector.EntitySelectorConfig(domain=list(dict.fromkeys(domain for domain, label in ACTIONS.values())))),
            vol.Required("action", default="lock.unlock"): selector.SelectSelector(selector.SelectSelectorConfig(
                options=[selector.SelectOptionDict(value=action, label=label) for action, (domain, label) in ACTIONS.items()],
                mode=selector.SelectSelectorMode.DROPDOWN)),
            vol.Required("kind", default="private"): vol.In(["private", "shared"]),
            vol.Required("switch_mode", default="ha_pulse"): selector.SelectSelector(selector.SelectSelectorConfig(
                options=[selector.SelectOptionDict(value="ha_pulse", label="Impulso gestito da Home Assistant"),
                         selector.SelectOptionDict(value="device_pulse", label="Timer locale già configurato nel dispositivo")],
                mode=selector.SelectSelectorMode.DROPDOWN)),
            vol.Required("pulse_seconds", default=2): vol.All(vol.Coerce(float), vol.Range(min=.5, max=5)),
            vol.Optional("confirm_device_pulse", default=False): bool,
            vol.Required("confirm", default=False): bool,
        }))

    async def async_step_add_shelly_gate(self, user_input=None):
        """Configure a native Shelly relay and prepare its QR without opening it."""
        from .gate_setup import async_add_shelly_gate, available_gate_relays
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="not_ready")
        errors = {}
        if user_input is not None:
            try:
                if user_input.get("confirm") is not True:
                    raise ValueError("Conferma la configurazione del relè.")
                await async_add_shelly_gate(manager, name=user_input["name"],
                    entity_id=user_input["entity_id"], seconds=user_input["pulse_seconds"],
                    kind=user_input["kind"])
            except (KeyError, TypeError, ValueError):
                errors["base"] = "invalid_gate"
            else:
                return self.async_create_entry(title="", data=self._unchanged_options())
        relays = available_gate_relays(manager)
        if not relays:
            return self.async_abort(reason="no_shelly")
        return self.async_show_form(
            step_id="add_shelly_gate", errors=errors,
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("entity_id"): selector.SelectSelector(selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value=r["entity_id"], label=r["name"] + " · " + r["model"]) for r in relays],
                    multiple=False, mode=selector.SelectSelectorMode.DROPDOWN)),
                vol.Required("pulse_seconds", default=2): vol.All(vol.Coerce(float), vol.Range(min=.5, max=5)),
                vol.Required("kind", default="private"): vol.In(["shared", "private"]),
                vol.Required("confirm", default=False): bool,
            }),
        )

    async def async_step_edit_gate(self, user_input=None):
        """Select an existing gate; do not change it until the next form is saved."""
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="not_ready")
        async with manager.lock:
            gates = list(manager.data["gates"])
        if not gates:
            return self.async_abort(reason="no_gates")
        errors = {}
        if user_input is not None:
            gate_id = user_input.get("gate_id", "")
            if any(gate["id"] == gate_id for gate in gates):
                self._gate_id_to_edit = gate_id
                return await self.async_step_edit_gate_details()
            errors["base"] = "invalid_gate"

        return self.async_show_form(
            step_id="edit_gate",
            data_schema=vol.Schema({
                vol.Required("gate_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=gate["id"],
                                label=gate["name"] + " · " + gate["entity_id"],
                            )
                            for gate in gates
                        ],
                        multiple=False,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }),
            errors=errors,
        )

    async def async_step_edit_gate_details(self, user_input=None):
        """Edit a gate while preserving bookings and avoiding actuator changes."""
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="not_ready")
        gate_id = getattr(self, "_gate_id_to_edit", None)
        if not gate_id:
            return self.async_abort(reason="invalid_gate")
        errors = {}
        async with manager.lock:
            gate = next(
                (item for item in manager.data["gates"] if item["id"] == gate_id),
                None,
            )
            if gate is None:
                return self.async_abort(reason="invalid_gate")
            defaults = {
                key: gate[key] for key in ("name", "entity_id", "action", "kind")
            }
            if "entity_binding" in gate:
                from .entity_gate import resolve_binding
                try:
                    defaults["entity_id"] = resolve_binding(self.hass, gate["entity_binding"])
                except ValueError:
                    pass
            if "shelly_binding" in gate:
                from .shelly_gate import resolve_binding
                try:
                    defaults["entity_id"] = resolve_binding(self.hass, gate["shelly_binding"]).entity_id
                except ValueError:
                    pass  # Show saved data; an unavailable device cannot be reassigned here.

        if user_input is not None:
            try:
                candidate = make_gate(
                    user_input["name"], user_input["entity_id"],
                    user_input["action"], user_input["kind"], enabled=False,
                )
                if self.hass.states.get(candidate["entity_id"]) is None:
                    raise ValueError("Entità Home Assistant non trovata.")
                async with manager.lock:
                    current = next(
                        (item for item in manager.data["gates"] if item["id"] == gate_id),
                        None,
                    )
                    if current is None:
                        return self.async_abort(reason="invalid_gate")
                    require_record_scope(current, manager.property_id)
                    if any(
                        item["id"] != gate_id
                        and item["entity_id"] == candidate["entity_id"]
                        for item in manager.data["gates"]
                    ):
                        raise ValueError("Entità già associata a un altro varco.")
                    sensitive_change = any(
                        current[key] != candidate[key]
                        for key in ("entity_id", "action", "kind")
                    )
                    if "shelly_binding" in current or "entity_binding" in current:
                        sensitive_change = native_mapping_changed(self.hass, current, candidate)
                    if sensitive_change:
                        # Do not silently change any active booking's door rights.
                        check_gate_removal(gate_id, manager.data["bookings"])
                    for key in ("name", "entity_id", "action", "kind"):
                        current[key] = candidate[key]
                    if sensitive_change:
                        # Require deliberate re-enabling and invalidate old QR links.
                        from .physical_admin import invalidate_gate_physical_credentials
                        invalidate_gate_physical_credentials(manager, current["id"])
                        current["enabled"] = False
                        current["token"] = candidate["token"]
                        manager.demo_sessions.clear()
                        manager.public_demo_sessions.clear()
                        manager.permanent_forms.clear()
                    manager.audit("gate_updated", current["name"])
                    await manager.async_save()
            except (KeyError, TypeError, ValueError) as err:
                errors["base"] = (
                    "gate_has_bookings" if "Revocare" in str(err)
                    else "invalid_gate"
                )
            else:
                return self.async_create_entry(
                    title="", data=self._unchanged_options()
                )

        return self.async_show_form(
            step_id="edit_gate_details",
            data_schema=vol.Schema({
                vol.Required("name", default=defaults["name"]): str,
                vol.Required(
                    "entity_id", default=defaults["entity_id"]
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["script", "button", "lock", "switch", "input_button", "cover"], multiple=False
                    )
                ),
                vol.Required(
                    "action", default=defaults["action"]
                ): vol.In(["script.turn_on", "button.press", "lock.unlock", "lock.open", "switch.turn_on", "cover.open_cover", "input_button.press"]),
                vol.Required("kind", default=defaults["kind"]): vol.In(
                    ["shared", "private"]
                ),
            }),
            errors=errors,
            description_placeholders={"gate_name": defaults["name"]},
        )

    async def async_step_remove_gate(self, user_input=None):
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="not_ready")
        async with manager.lock:
            gates = list(manager.data["gates"])
        if not gates:
            return self.async_abort(reason="no_gates")
        errors = {}
        if user_input is not None:
            gate_id = user_input.get("gate_id", "")
            if any(gate["id"] == gate_id for gate in gates):
                self._gate_id_to_remove = gate_id
                return await self.async_step_confirm_remove_gate()
            errors["base"] = "invalid_gate"

        return self.async_show_form(
            step_id="remove_gate",
            data_schema=vol.Schema({
                vol.Required("gate_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=gate["id"],
                                label=gate["name"] + " · " + gate["entity_id"],
                            )
                            for gate in gates
                        ],
                        multiple=False,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }),
            errors=errors,
        )

    async def async_step_confirm_remove_gate(self, user_input=None):
        """Require a second explicit confirmation and revalidate inside lock."""
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="not_ready")
        gate_id = getattr(self, "_gate_id_to_remove", None)
        if not gate_id:
            return self.async_abort(reason="invalid_gate")
        errors = {}
        async with manager.lock:
            gate = next(
                (item for item in manager.data["gates"] if item["id"] == gate_id),
                None,
            )
            if gate is None:
                return self.async_abort(reason="invalid_gate")
            require_record_scope(gate, manager.property_id)
            name = gate["name"]
            if user_input is not None and user_input.get("confirm") is True:
                try:
                    check_gate_removal(gate_id, manager.data["bookings"])
                except (ValueError, KeyError, TypeError):
                    errors["base"] = "gate_has_bookings"
                else:
                    manager.data["gates"].remove(gate)
                    manager.audit("gate_removed", name)
                    await manager.async_save()
                    return self.async_create_entry(
                        title="", data=self._unchanged_options()
                    )
        return self.async_show_form(
            step_id="confirm_remove_gate",
            data_schema=vol.Schema({
                vol.Required("confirm", default=False): bool,
            }),
            errors=errors,
            description_placeholders={"gate_name": name},
        )

