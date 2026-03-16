from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


class LoginRequest(BaseModel):
    """Credentials for login."""

    email: str   # plain str — login accepts any format, validated by DB lookup
    password: str


class TokenResponse(BaseModel):
    """JWT access token response."""

    access_token: str
    token_type: str = "bearer"


class RefreshResponse(BaseModel):
    """New access token after refresh."""

    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    """Request body for changing own password (used on first-login reset)."""

    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters.")
        return v
