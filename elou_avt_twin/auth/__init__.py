"""
auth
====
Role-based access control (RBAC) for the ELOU-AVT training complex.

* storage: SQLite (same `sessions.db` as `persistence.session_store`);
* authentication: dependency-free (scrypt password hashes + HMAC-SHA256
  signed session tokens);
* authorization: route-level permission gates built on
  `require_permission("can_...")` — never on literal role checks.

Usage in api_server.py::

    from auth.deps import get_current_user, require_permission

    @app.post("/action", dependencies=[Depends(require_permission("send_commands"))])
    def action(...): ...
"""

from .models import (
    LoginRequest,
    LoginResponse,
    PermissionView,
    Principal,
    RoleAssign,
    RoleCreate,
    RolePermissions,
    RoleUpdate,
    RoleView,
    UserCreate,
    UserView,
)
from .security import create_token, hash_password, verify_password, verify_token
from .store import (
    ALL_PERMISSION_CODES,
    ALL_ROLE_CODES,
    AuthService,
    AuthStore,
    PERMISSIONS,
    ROLE_PERMISSIONS,
)
from .deps import AUTH_MODE, authenticate_websocket, get_current_user, require_permission

__all__ = [
    "AUTH_MODE",
    "ALL_PERMISSION_CODES",
    "ALL_ROLE_CODES",
    "AuthService",
    "AuthStore",
    "PERMISSIONS",
    "ROLE_PERMISSIONS",
    "LoginRequest",
    "LoginResponse",
    "PermissionView",
    "Principal",
    "RoleAssign",
    "RoleCreate",
    "RolePermissions",
    "RoleUpdate",
    "RoleView",
    "UserCreate",
    "UserView",
    "authenticate_websocket",
    "create_token",
    "get_current_user",
    "hash_password",
    "require_permission",
    "verify_password",
    "verify_token",
]
