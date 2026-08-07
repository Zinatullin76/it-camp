"""
deps.py
=======
FastAPI dependencies enforcing RBAC on every protected route.

Authorization model:
* a route declares `dependencies=[Depends(require_permission("can_x"))]`;
* `get_current_user` resolves the caller from the `Authorization: Bearer`
  header into a `Principal` carrying a set of permission codes;
* `require_permission` is a 403 gate — checks happen against permissions,
  never against a literal role.

`ELOU_AUTH_MODE` controls enforcement:
* "disabled" (default, dev): requests without a token act as a system
  principal with every permission, so the legacy demo UI and the existing
  test-suite keep working unchanged;
* "enabled": a valid Bearer token is required (401) and permission checks
  apply (403).
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from .models import Principal
from .store import ALL_PERMISSION_CODES, AuthService, AuthStore

AUTH_MODE = os.environ.get("ELOU_AUTH_MODE", "disabled").lower()

_system_principal = Principal(
    username="system",
    full_name="System (ELOU_AUTH_MODE=disabled)",
    roles=["administrator"],
    permissions=list(ALL_PERMISSION_CODES),
    is_system=True,
)

_auth_store = AuthStore()
_auth_service = AuthService(_auth_store)


def get_auth_service() -> AuthService:
    return _auth_service


def get_current_user(request: Request) -> Principal:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
        principal = _auth_service.principal_from_token(token)
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return principal
    if AUTH_MODE == "disabled":
        return _system_principal
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_permission(code: str):
    """Return a dependency that allows only callers holding `code`."""

    def dependency(current_user: Principal = Depends(get_current_user)) -> Principal:
        if not current_user.has_permission(code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {code}",
            )
        return current_user

    return dependency


def authenticate_websocket(token: str) -> Optional[Principal]:
    """Resolve a WebSocket caller from the `token` query parameter."""
    principal = _auth_service.principal_from_token(token) if token else None
    if AUTH_MODE == "disabled":
        return _system_principal
    if principal is None:
        return None
    return principal
