from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.utils.idempotency import add_to_blacklist, is_blacklisted


class AuthService:
    """Handles authentication business logic: login, token refresh, logout."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = UserRepository(db)

    def login(self, email: str, password: str, response: Response) -> dict:
        """
        Validate credentials, update last_login, set refresh cookie, return access token.
        Raises HTTP 401 if credentials are invalid.
        """
        user: User | None = self.repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Update last login timestamp (server-side)
        user.last_login = datetime.now(timezone.utc)
        self.db.flush()

        access_token = create_access_token({
            "sub": str(user.id),
            "role": user.role.value,
            "must_change_password": user.must_change_password,
        })
        refresh_token = create_refresh_token(user.id)

        # Set HttpOnly refresh token cookie.
        # secure=False so the cookie is accepted over plain HTTP on localhost /
        # Docker (http://localhost:8000). Set COOKIE_SECURE=true in production
        # when the API is served over HTTPS.
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite="lax",
            max_age=60 * 60 * 24 * 7,  # 7 days
        )

        return {"access_token": access_token, "token_type": "bearer"}

    def refresh(self, refresh_token: str, response: Response) -> dict:
        """
        Validate refresh token, blacklist old token, issue new tokens.
        Raises HTTP 401 if token is missing, expired, or blacklisted.
        """
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token missing",
            )

        if is_blacklisted(refresh_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )

        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        user_id: str | None = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        user = self.repo.get_by_id_active(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # Blacklist the old refresh token (TTL = remaining expiry)
        exp = payload.get("exp", 0)
        remaining = int(exp - datetime.now(timezone.utc).timestamp())
        if remaining > 0:
            add_to_blacklist(refresh_token, remaining)

        # Issue new tokens
        new_access = create_access_token({"sub": str(user.id), "role": user.role.value})
        new_refresh = create_refresh_token(user.id)

        response.set_cookie(
            key="refresh_token",
            value=new_refresh,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite="lax",
            max_age=60 * 60 * 24 * 7,
        )

        return {"access_token": new_access, "token_type": "bearer"}

    def logout(self, refresh_token: str, response: Response) -> None:
        """Blacklist the refresh token and clear the cookie."""
        if refresh_token:
            try:
                payload = decode_token(refresh_token)
                exp = payload.get("exp", 0)
                remaining = int(exp - datetime.now(timezone.utc).timestamp())
                if remaining > 0:
                    add_to_blacklist(refresh_token, remaining)
            except Exception:
                pass  # Token already invalid — still clear the cookie

        response.delete_cookie("refresh_token")
