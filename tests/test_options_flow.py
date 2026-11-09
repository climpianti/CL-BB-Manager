"""Exercise the real options flow with minimal HA stubs (no HA runtime needed)."""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import voluptuous as vol

ROOT = Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager"
PACKAGE = "_cl_bb_options_test"
package = ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package


class BaseFlow:
    def __init_subclass__(cls, **kwargs):
        return super().__init_subclass__()

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_show_menu(self, **kwargs):
        return {"type": "menu", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    def async_abort(self, **kwargs):
        return {"type": "abort", **kwargs}


class DummySelector:
    def __init__(self, config):
        self.config = config

    def __call__(self, value):
        return value


class SelectorConfig:
    def __init__(self, **kwargs):
        self.options = kwargs


ha = ModuleType("homeassistant")
entries = ModuleType("homeassistant.config_entries")
entries.ConfigFlow = BaseFlow
entries.OptionsFlow = BaseFlow
helpers = ModuleType("homeassistant.helpers")
selector = ModuleType("homeassistant.helpers.selector")
selector.SelectSelector = DummySelector
selector.EntitySelector = DummySelector
selector.SelectSelectorConfig = SelectorConfig
selector.EntitySelectorConfig = SelectorConfig
selector.SelectOptionDict = lambda **kwargs: kwargs
selector.SelectSelectorMode = SimpleNamespace(DROPDOWN="dropdown")
helpers.selector = selector
ha.config_entries = entries
ha.helpers = helpers
for name, mod in (
    ("homeassistant", ha),
    ("homeassistant.config_entries", entries),
    ("homeassistant.helpers", helpers),
    ("homeassistant.helpers.selector", selector),
):
    sys.modules[name] = mod

for child in ("const", "models", "gate_management", "permissions", "public_policy", "config_flow"):
    spec = importlib.util.spec_from_file_location(
        PACKAGE + "." + child, ROOT / (child + ".py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

flow_module = sys.modules[PACKAGE + ".config_flow"]


class Store:
    property_id = "2bb950a2-a1c5-46ca-b192-9ad03b1f8ca5"

    def __init__(self):
        self.data = {"gates": [], "bookings": [], "events": []}
        self.lock = asyncio.Lock()
        self.saves = 0

    def audit(self, key, text):
        self.data["events"].append((key, text))

    async def async_save(self):
        self.saves += 1


def setup(options=None):
    manager = Store()
    users = [
        SimpleNamespace(id="worker-a", name="Operatore A", is_active=True,
                        is_admin=False, system_generated=False),
        SimpleNamespace(id="worker-b", name="Operatore B", is_active=True,
                        is_admin=False, system_generated=False),
        SimpleNamespace(id="admin", name="Admin", is_active=True,
                        is_admin=True, system_generated=False),
    ]
    async def get_users():
        return users

    hass = SimpleNamespace(
        auth=SimpleNamespace(async_get_users=get_users),
        config=SimpleNamespace(external_url="https://example.org"),
        data={"cl_bb_manager": {"manager": manager}},
        states=SimpleNamespace(get=lambda entity_id:
            SimpleNamespace(state="off") if entity_id.startswith("script.") else None),
    )
    flow = flow_module.CLBBManagerOptionsFlow()
    flow.hass = hass
    flow.config_entry = SimpleNamespace(options=options or {
        "public_pilot_enabled": True,
        "public_pilot_origin": "https://example.org",
        "operator_user_ids": ["worker-a"],
    })
    return flow, manager


def test_reopening_options_shows_saved_operator_and_name():
    async def go():
        flow, _ = setup()
        menu = await flow.async_step_init()
        assert menu["menu_options"] == ["access", "gates"]
        form = await flow.async_step_access()
        assert form["description_placeholders"]["current_operators"] == "Operatore A"
        schema = form["data_schema"].schema
        marked = next(k for k in schema if k.schema == "operator_user_ids")
        assert marked.default() == ["worker-a"]
    asyncio.run(go())


def test_saving_https_keeps_operator_list_and_reopening_restores_it():
    async def go():
        flow, _ = setup()
        saved = await flow.async_step_access({
            "public_pilot_enabled": True,
            "public_pilot_origin": "https://example.org",
            "operator_user_ids": ["worker-a", "worker-b"],
        })
        assert saved["type"] == "create_entry"
        assert saved["data"]["operator_user_ids"] == ["worker-a", "worker-b"]
        again, _ = setup(saved["data"])
        form = await again.async_step_access()
        assert "Operatore A" in form["description_placeholders"]["current_operators"]
        assert "Operatore B" in form["description_placeholders"]["current_operators"]
        marked = next(
            k for k in form["data_schema"].schema if k.schema == "operator_user_ids"
        )
        assert marked.default() == ["worker-a", "worker-b"]
    asyncio.run(go())


def test_explicitly_clearing_operator_list_is_saved():
    async def go():
        flow, _ = setup()
        saved = await flow.async_step_access({
            "public_pilot_enabled": True,
            "operator_user_ids": [],
        })
        assert saved["type"] == "create_entry"
        assert saved["data"]["operator_user_ids"] == []
    asyncio.run(go())


def test_add_gate_is_disabled_and_duplicate_rejected():
    async def go():
        flow, manager = setup()
        gate_values = {
            "name": "Cancello", "entity_id": "script.cancello",
            "action": "script.turn_on", "kind": "shared",
        }
        created = await flow.async_step_add_gate(gate_values)
        assert created["type"] == "create_entry"
        assert created["data"]["operator_user_ids"] == ["worker-a"]
        assert manager.saves == 1
        assert len(manager.data["gates"]) == 1
        assert manager.data["gates"][0]["enabled"] is False
        assert manager.data["gates"][0]["property_id"] == manager.property_id
        repeated = await flow.async_step_add_gate(gate_values)
        assert repeated["type"] == "form"
        assert repeated["errors"]["base"] == "invalid_gate"
        assert len(manager.data["gates"]) == 1
    asyncio.run(go())


def test_gate_deletion_requires_confirmation_and_respects_bookings():
    async def go():
        flow, manager = setup()
        await flow.async_step_add_gate({
            "name": "Cancello", "entity_id": "script.cancello",
            "action": "script.turn_on", "kind": "shared",
        })
        gate_id = manager.data["gates"][0]["id"]
        chosen = await flow.async_step_remove_gate({"gate_id": gate_id})
        assert chosen["step_id"] == "confirm_remove_gate"
        assert len(manager.data["gates"]) == 1
        not_confirmed = await flow.async_step_confirm_remove_gate({"confirm": False})
        assert not_confirmed["type"] == "form"
        assert len(manager.data["gates"]) == 1
        from datetime import datetime, timedelta, timezone
        manager.data["bookings"].append({
            "gate_ids": [gate_id], "revoked": False,
            "end": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        })
        blocked = await flow.async_step_confirm_remove_gate({"confirm": True})
        assert blocked["errors"]["base"] == "gate_has_bookings"
        assert len(manager.data["gates"]) == 1
        manager.data["bookings"][0]["revoked"] = True
        removed = await flow.async_step_confirm_remove_gate({"confirm": True})
        assert removed["type"] == "create_entry"
        assert manager.data["gates"] == []
        assert manager.saves == 2
    asyncio.run(go())


def test_nonexistent_gate_not_removed():
    async def go():
        flow, manager = setup()
        await flow.async_step_add_gate({
            "name": "Scala", "entity_id": "script.scala",
            "action": "script.turn_on", "kind": "shared",
        })
        result = await flow.async_step_remove_gate({"gate_id": "wrong-id"})
        assert result["errors"]["base"] == "invalid_gate"
        assert len(manager.data["gates"]) == 1
    asyncio.run(go())
