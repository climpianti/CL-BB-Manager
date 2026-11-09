"""Role-policy regression checks without importing Home Assistant."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import MappingProxyType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[1] / "custom_components/cl_bb_manager"
spec = importlib.util.spec_from_file_location("cl_bb_permissions_under_test", ROOT / "permissions.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def user(user_id="operator", *, admin=False, active=True):
    return SimpleNamespace(id=user_id, is_admin=admin, is_active=active)


def test_admin_always_authorized_when_active():
    assert module.user_role(user("admin", admin=True), {}) == "admin"
    assert module.user_role(user("admin", admin=True, active=False), {}) is None


def test_operator_needs_explicit_assignment_and_active_account():
    options = {"operator_user_ids": ["operator"]}
    assert module.user_role(user("operator"), options) == "operator"
    assert module.user_role(user("outsider"), options) is None
    assert module.user_role(user("operator", active=False), options) is None
    assert module.user_role(None, options) is None


def test_revocation_is_immediate_in_role_policy():
    options = {"operator_user_ids": ["operator"]}
    assert module.user_role(user("operator"), options) == "operator"
    options["operator_user_ids"] = []
    assert module.user_role(user("operator"), options) is None


def test_home_assistant_immutable_options_authorize_only_selected_active_users():
    backing = {"operator_user_ids": ["selected-user"]}
    options = MappingProxyType(backing)
    assert module.user_role(user("selected-user"), options) == "operator"
    assert module.user_role(user("other-user"), options) is None
    assert module.user_role(user("selected-user", active=False), options) is None
    backing["operator_user_ids"] = []
    assert module.user_role(user("selected-user"), options) is None


def test_malformed_allowlists_fail_closed():
    for malformed in (None, "operator", {"operator": True}, [None], [123]):
        options = {"operator_user_ids": malformed}
        assert module.user_role(user("operator"), options) is None
    options = {"operator_user_ids": ["operator", "operator", "second"]}
    assert module.operator_user_ids(options) == ("operator", "second")


def test_admin_only_handlers_remain_guarded_on_server():
    source = (ROOT / "api.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    commands = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "register_commands"
    )
    admin_only = {
        "add_gate", "update_gate", "remove_gate", "get_qr", "demo_check_pin",
    }
    operator_allowed = {
        "get_list", "add_booking", "revoke_booking", "demo_qr",
        "public_pilot_qr",
    }
    for handler in commands.body:
        if not isinstance(handler, ast.AsyncFunctionDef):
            continue
        names = {node.func.id: node for node in ast.walk(handler)
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)
                 and node.func.id == "_authorize"}
        if handler.name not in (admin_only | operator_allowed):
            continue
        assert "_authorize" in names, handler.name
        auth = names["_authorize"]
        gated = any(
            kw.arg == "admin_only"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in auth.keywords
        )
        assert gated == (handler.name in admin_only), handler.name


def test_role_loveless_panel_is_not_admin_only():
    source = (ROOT / "__init__.py").read_text(encoding="utf-8")
    assert 'sidebar_title="CL B&B Manager"' in source
    assert 'require_admin=False' in source
    assert 'role=user_role(connection.user, manager.entry.options)' in (ROOT / "api.py").read_text(encoding="utf-8")


def test_panel_does_not_hijack_ha_configure_button():
    panel = (ROOT / "__init__.py").read_text(encoding="utf-8")
    options = (ROOT / "config_flow.py").read_text(encoding="utf-8")
    assert "config_panel_domain=" not in panel
    assert "require_admin=False" in panel
    assert "async_get_options_flow" in options
    assert "operator_user_ids" in options or "OPTION_OPERATOR_USERS" in options

