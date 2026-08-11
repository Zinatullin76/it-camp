"""
models.py
=========
Pydantic contracts for the RBAC layer: the in-memory authorization
principal, API request/response models and admin-facing views.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Principal(BaseModel):
    """Authenticated identity resolved by the auth dependencies.

    All authorization is expressed as a set of permission codes; roles are
    only an implementation detail used to derive that set.
    """

    username: str
    full_name: str = ""
    roles: List[str] = []
    permissions: List[str] = []
    is_system: bool = False

    def has_permission(self, code: str) -> bool:
        return code in self.permissions


class UserView(BaseModel):
    id: int
    username: str
    full_name: str = ""
    is_active: bool = True
    roles: List[str] = []
    permissions: List[str] = []


class RoleView(BaseModel):
    code: str
    name: str
    description: str = ""
    permissions: List[str] = []


class PermissionView(BaseModel):
    code: str
    description: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserView


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str = ""
    role_codes: List[str] = []


class RoleAssign(BaseModel):
    role_codes: List[str] = []


class RoleCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    permission_codes: List[str] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class RolePermissions(BaseModel):
    permission_codes: List[str] = []
