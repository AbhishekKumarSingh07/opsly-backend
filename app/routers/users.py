from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.exceptions import ConflictError, NotFoundError
from app.core.permissions import PermissionPolicy
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserCreate, UserPasswordReset, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=UserResponse)
def create_user(
    payload: UserCreate,
    current_user: User = Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Create a new platform user.

    Permission rules (enforced by PermissionPolicy):
    - Owner can create any role (owner / moderator / staff).
    - Moderator can only create staff accounts.

    Accessible by: owner, moderator.
    """
    policy = PermissionPolicy(current_user)
    policy.require_can_create_user(payload.role)

    repo = UserRepository(db)
    if repo.get_by_email(payload.email):
        raise ConflictError(f"Email '{payload.email}' is already registered.")

    user = User(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        role=payload.role,
        hashed_password=hash_password(payload.password),
        must_change_password=payload.must_change_password,
        created_by=current_user.id,
    )
    return repo.create(user)


@router.get("/", response_model=list[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    List all platform users.

    Accessible by: owner, moderator.
    """
    repo = UserRepository(db)
    return repo.list_all(skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: UUID,
    current_user: User = Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Fetch a single user profile by ID.

    Accessible by: owner, moderator.
    """
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise NotFoundError("User", str(user_id))
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    current_user: User = Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Update a user's profile (name, phone, active status).

    Only Owner can edit existing accounts — enforced via PermissionPolicy.
    Accessible by: owner.
    """
    PermissionPolicy(current_user).require_can_manage_user()

    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise NotFoundError("User", str(user_id))

    if payload.name is not None:
        user.name = payload.name
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.is_active is not None:
        user.is_active = payload.is_active
    return repo.save(user)


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: UUID,
    payload: UserPasswordReset,
    current_user: User = Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Reset a user's password (Owner only).

    Sets must_change_password=True so the user is prompted to change it on next login.
    Accessible by: owner.
    """
    PermissionPolicy(current_user).require_can_manage_user()

    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise NotFoundError("User", str(user_id))

    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = True
    repo.save(user)
    return {"message": "Password reset successfully. User must change it on next login."}
