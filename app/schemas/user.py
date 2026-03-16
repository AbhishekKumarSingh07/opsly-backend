from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.user import UserRole


class UserCreate(BaseModel):
    """Request body for creating a new user."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    email: EmailStr
    phone: str | None = None
    role: UserRole = UserRole.staff
    password: str
    # When True, user will be prompted to change password on first login.
    # Defaults to True so bulk-imported / admin-created accounts must reset.
    must_change_password: bool = True


class UserUpdate(BaseModel):
    """Request body for updating a user's profile (owner only)."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = None
    phone: str | None = None
    is_active: bool | None = None


class UserPasswordReset(BaseModel):
    """Request body for resetting a user's password (owner only)."""

    model_config = ConfigDict(from_attributes=True)

    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


class UserResponse(BaseModel):
    """Public user profile returned in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    phone: str | None
    role: UserRole
    is_active: bool
    must_change_password: bool
    last_login: datetime | None
    created_at: datetime
    created_by: UUID | None
