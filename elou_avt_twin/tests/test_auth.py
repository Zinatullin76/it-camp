import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi import HTTPException

import auth.deps as deps
from auth import (
    AuthService,
    AuthStore,
    PERMISSIONS,
    ROLE_PERMISSIONS,
    RoleCreate,
    RoleUpdate,
    UserCreate,
)
from auth.security import create_token, hash_password, verify_password, verify_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeHeaders:
    def __init__(self, authorization: str = ""):
        self._v = authorization

    def get(self, key: str, default=None):
        return self._v if key == "Authorization" else default


class _FakeRequest:
    def __init__(self, authorization: str = ""):
        self.headers = _FakeHeaders(authorization)


@pytest.fixture()
def svc(monkeypatch):
    store = AuthStore(":memory:")
    service = AuthService(store)
    monkeypatch.setattr(deps, "_auth_service", service)
    return service


# ---------------------------------------------------------------------------
# security: passwords
# ---------------------------------------------------------------------------

def test_password_hash_roundtrip():
    encoded = hash_password("secret-1")
    assert encoded.startswith("scrypt$")
    assert verify_password("secret-1", encoded)
    assert not verify_password("secret-2", encoded)
    assert not verify_password("secret-1", "sha256$garbage")


def test_password_hash_is_salted():
    assert hash_password("same") != hash_password("same")


# ---------------------------------------------------------------------------
# security: tokens
# ---------------------------------------------------------------------------

def test_token_roundtrip_and_tamper():
    token = create_token("secret", "operator", ttl_seconds=100)
    payload = verify_token("secret", token)
    assert payload["sub"] == "operator"
    assert verify_token("secret", token + "x") is None
    assert verify_token("other", token) is None


def test_token_expired():
    token = create_token("secret", "operator", ttl_seconds=-10)
    assert verify_token("secret", token) is None


# ---------------------------------------------------------------------------
# service: authentication & principals
# ---------------------------------------------------------------------------

def test_seed_accounts_and_permission_catalog(svc):
    assert svc.authenticate("admin", "admin") is not None
    assert svc.authenticate("operator", "operator") is not None
    assert svc.authenticate("field_operator", "field_operator") is not None
    assert svc.authenticate("unknown", "x") is None
    assert svc.authenticate("operator", "wrong") is None
    assert len(PERMISSIONS) == 40
    assert set(ROLE_PERMISSIONS) == {
        "administrator", "instructor", "operator", "field_operator",
    }


def test_admin_has_full_access(svc):
    principal = svc.principal_for("admin")
    assert set(principal.permissions) == set(PERMISSIONS)


def test_operator_permission_scope(svc):
    principal = svc.principal_for("operator")
    assert principal.has_permission("send_commands")
    assert principal.has_permission("run_simulation")
    assert principal.has_permission("view_scheme")
    assert not principal.has_permission("manage_users")
    assert not principal.has_permission("manage_twin")
    assert not principal.has_permission("view_field_operator_screen")


def test_field_operator_permission_scope(svc):
    principal = svc.principal_for("field_operator")
    assert principal.has_permission("view_field_operator_screen")
    assert principal.has_permission("view_profile")
    assert principal.has_permission("view_dashboard")
    # Полный кабинет консольного оператора…
    assert principal.has_permission("view_courses")
    assert principal.has_permission("view_competencies")
    assert principal.has_permission("view_history")
    assert principal.has_permission("take_exam")
    assert principal.has_permission("view_own_results")
    assert principal.has_permission("start_training")
    assert principal.has_permission("get_ai_recommendations")
    # …но без SCADA (мнемосхема, HMI, управление симуляцией).
    assert not principal.has_permission("view_scheme")
    assert not principal.has_permission("send_commands")
    assert not principal.has_permission("run_simulation")
    assert not principal.has_permission("manage_users")
    assert not principal.has_permission("manage_groups")
    assert not principal.has_permission("view_training_sessions")


def test_principal_from_token(svc):
    login = svc.authenticate("operator", "operator")
    principal = svc.principal_from_token(login.access_token)
    assert principal.username == "operator"
    assert principal.roles == ["operator"]


def test_principal_from_token_expired(svc):
    from auth import create_token
    old = create_token(svc._secret, "operator", ttl_seconds=-5)
    assert svc.principal_from_token(old) is None


def test_disabled_user_cannot_authenticate(svc):
    users = [u for u in svc.list_users() if u.username == "operator"]
    svc.set_user_active(users[0].id, False)
    assert svc.authenticate("operator", "operator") is None
    assert svc.principal_for("operator") is None


# ---------------------------------------------------------------------------
# service: user administration
# ---------------------------------------------------------------------------

def test_create_user_and_assign_roles(svc):
    user = svc.create_user(UserCreate(
        username="trainee", password="pass", full_name="Тест",
        role_codes=["operator"],
    ))
    assert user.roles == ["operator"]
    principal = svc.principal_for("trainee")
    assert principal.has_permission("send_commands")
    assert not principal.has_permission("manage_users")

    updated = svc.set_user_roles(user.id, ["administrator"])
    assert updated.roles == ["administrator"]
    assert svc.principal_for("trainee").has_permission("manage_users")


def test_create_duplicate_user_fails(svc):
    with pytest.raises(Exception):
        svc.create_user(UserCreate(username="admin", password="x"))


def test_role_listing(svc):
    roles = {r.code: r for r in svc.list_roles()}
    assert "administrator" in roles
    assert set(roles["operator"].permissions) == set(ROLE_PERMISSIONS["operator"])


# ---------------------------------------------------------------------------
# service: role administration (CRUD)
# ---------------------------------------------------------------------------

def test_create_role_with_permissions(svc):
    role = svc.create_role(RoleCreate(
        code="shift_supervisor",
        name="Начальник смены",
        description="Наблюдение и статистика",
        permission_codes=["view_statistics", "view_operator_actions", "unknown_perm"],
    ))
    assert role.code == "shift_supervisor"
    assert role.name == "Начальник смены"
    assert role.permissions == ["view_operator_actions", "view_statistics"]
    # неизвестное право отфильтровано


def test_create_duplicate_role_fails(svc):
    with pytest.raises(ValueError):
        svc.create_role(RoleCreate(code="operator", name="Дубль"))


def test_create_role_invalid_code_fails(svc):
    with pytest.raises(ValueError):
        svc.create_role(RoleCreate(code="плохой код", name="x"))


def test_update_role_name_and_description(svc):
    svc.create_role(RoleCreate(code="auditor", name="Аудитор"))
    updated = svc.update_role("auditor", RoleUpdate(name="Аудитор ИБ", description="Просмотр логов"))
    assert updated.name == "Аудитор ИБ"
    assert updated.description == "Просмотр логов"


def test_update_missing_role_fails(svc):
    with pytest.raises(KeyError):
        svc.update_role("nope", RoleUpdate(name="x"))


def test_set_role_permissions(svc):
    svc.create_role(RoleCreate(code="viewer", name="Наблюдатель"))
    role = svc.set_role_permissions("viewer", ["view_logs", "view_statistics"])
    assert set(role.permissions) == {"view_logs", "view_statistics"}
    role = svc.set_role_permissions("viewer", [])
    assert role.permissions == []


def test_custom_role_is_not_wiped_by_catalog(svc):
    svc.create_role(RoleCreate(code="auditor", name="Аудитор", permission_codes=["view_logs"]))
    svc.list_roles()  # list_roles() вызывает ensure_catalog()
    roles = {r.code for r in svc.list_roles()}
    assert "auditor" in roles


def test_assign_custom_role_to_user(svc):
    svc.create_role(RoleCreate(code="auditor", name="Аудитор", permission_codes=["view_logs"]))
    user = svc.create_user(UserCreate(
        username="revizor", password="pass", role_codes=["auditor"],
    ))
    assert user.roles == ["auditor"]
    principal = svc.principal_for("revizor")
    assert principal.has_permission("view_logs")
    assert not principal.has_permission("manage_users")


def test_delete_custom_role(svc):
    svc.create_role(RoleCreate(code="temp_role", name="Временная"))
    user = svc.create_user(UserCreate(username="temp_user", password="pass", role_codes=["temp_role"]))
    svc.delete_role("temp_role")
    roles = {r.code for r in svc.list_roles()}
    assert "temp_role" not in roles
    # каскад: роль слетела с пользователя
    assert svc.principal_for("temp_user").roles == []


def test_delete_missing_role_fails(svc):
    with pytest.raises(KeyError):
        svc.delete_role("nope")


def test_delete_builtin_role_forbidden(svc):
    with pytest.raises(ValueError):
        svc.delete_role("administrator")


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

def test_get_current_user_with_token(svc):
    login = svc.authenticate("operator", "operator")
    principal = deps.get_current_user(_FakeRequest("Bearer " + login.access_token))
    assert principal.username == "operator"
    assert principal.has_permission("send_commands")
    assert not principal.has_permission("manage_users")


def test_get_current_user_bad_token_401(svc):
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(_FakeRequest("Bearer not-a-token"))
    assert e.value.status_code == 401


def test_fallback_system_in_disabled_mode(svc):
    principal = deps.get_current_user(_FakeRequest(""))
    assert principal.is_system
    assert principal.has_permission("manage_users")
    assert principal.has_permission("grade_exam")


def test_enabled_mode_requires_token(svc, monkeypatch):
    monkeypatch.setattr(deps, "AUTH_MODE", "enabled")
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(_FakeRequest(""))
    assert e.value.status_code == 401


def test_enabled_mode_valid_token_passes(svc, monkeypatch):
    monkeypatch.setattr(deps, "AUTH_MODE", "enabled")
    login = svc.authenticate("admin", "admin")
    principal = deps.get_current_user(_FakeRequest("Bearer " + login.access_token))
    assert principal.username == "admin"


def test_require_permission_allows(svc):
    gate = deps.require_permission("manage_users")
    admin = svc.principal_for("admin")
    assert gate(current_user=admin).username == "admin"


def test_require_permission_forbids_403(svc):
    gate = deps.require_permission("manage_users")
    operator = svc.principal_for("operator")
    with pytest.raises(HTTPException) as e:
        gate(current_user=operator)
    assert e.value.status_code == 403


def test_require_permission_system_in_disabled_mode(svc):
    gate = deps.require_permission("grade_exam")
    assert gate(current_user=deps.get_current_user(_FakeRequest(""))).is_system
