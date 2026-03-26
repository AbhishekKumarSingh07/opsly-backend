from __future__ import annotations
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user, get_db
from app.core.security import hash_password
from app.schemas.auth import LoginRequest, TokenResponse, RefreshResponse, ChangePasswordRequest
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Authenticate a user with email and password.

    Accepts **either**:
    - JSON body `{"email": "...", "password": "..."}` — used by the React app
    - OAuth2 form fields `username` / `password` — used by Swagger UI Authorize dialog
      (the OAuth2 spec uses `username`; we treat it as the email field)

    - Sets an HttpOnly `refresh_token` cookie (7 days).
    - Returns a short-lived JWT access token.
    """
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        email = body.get("email", "")
        password = body.get("password", "")
    else:
        form = await request.form()
        email = str(form.get("username") or form.get("email") or "")
        password = str(form.get("password") or "")

    service = AuthService(db)
    return service.login(email, password, response)


@router.post("/refresh", response_model=RefreshResponse)
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    """
    Issue a new access token using the HttpOnly refresh_token cookie.
    - Rotates the refresh token (old one is blacklisted in Redis).
    - Returns HTTP 401 if cookie is missing, expired, or blacklisted.
    """
    refresh_token_value = request.cookies.get("refresh_token", "")
    service = AuthService(db)
    return service.refresh(refresh_token_value, response)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """
    Logout the current user.
    - Blacklists the refresh token in Redis.
    - Clears the HttpOnly cookie.
    """
    refresh_token_value = request.cookies.get("refresh_token", "")
    service = AuthService(db)
    service.logout(refresh_token_value, response)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def me(current_user=Depends(get_current_user)):
    """
    Return the currently authenticated user's profile.
    - Accessible by all roles.
    """
    return current_user


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change the current user's own password.
    - Used on first login when must_change_password=True.
    - Clears the must_change_password flag after a successful change.
    """
    from app.repositories.user_repo import UserRepository
    from app.core.security import verify_password
    from fastapi import HTTPException, status

    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    repo = UserRepository(db)
    current_user.hashed_password = hash_password(payload.new_password)
    current_user.must_change_password = False
    repo.save(current_user)
    return {"message": "Password changed successfully."}