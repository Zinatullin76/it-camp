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
    assert svc.authenticate("unknown", "x") is None
    assert svc.authenticate("operator", "wrong") is None
    assert len(PERMISSIONS) == 27
    assert set(ROLE_PERMISSIONS) == {
        "administrator", "instructor", "operator",
    }


def test_admin_has_full_access(svc):
    principal = svc.principal_for("admin")
    assert set(principal.permissions) == set(PERMISSIONS)


def test_operator_permission_scope(svc):
    principal = svc.principal_for("operator")
    assert principal.has_permission("send_commands")
    assert principal.has_permission("run_simulation")
    assert not principal.has_permission("manage_users")
    assert not principal.has_permission("manage_twin")


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
