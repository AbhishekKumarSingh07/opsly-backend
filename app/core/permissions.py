from __future__ import annotations

"""
Centralised permission policy for Opsly.

Rules
-----
* Owner  → full CRUD access to everything.
* Moderator → can CREATE new records; cannot UPDATE or DELETE existing ones.
              Exception: moderators CAN approve/flag attendance for staff only.
* Staff  → limited to their own records (tickets, attendance, expenses).
* Client → read-only access to their own assets via the portal.

Usage
-----
    from app.core.permissions import PermissionPolicy
    policy = PermissionPolicy(current_user)
    policy.require_create()        # raises 403 if not allowed
    policy.require_update()        # raises 403 if not allowed
    policy.require_delete()        # raises 403 if not allowed
    policy.require_owner_only()    # raises 403 if not owner
    policy.can_approve_attendance(target_record)  # returns bool
"""

from app.models.user import User, UserRole
from app.core.exceptions import PermissionDeniedError


class PermissionPolicy:
    """Encapsulates all role-based permission decisions in one place."""

    def __init__(self, user: User) -> None:
        self.user = user

    # ─── Generic CRUD gates ──────────────────────────────────────────────────

    def require_create(self) -> None:
        """Owner and Moderator can create records."""
        if self.user.role not in (UserRole.owner, UserRole.moderator):
            raise PermissionDeniedError("Only owner or moderator can create records.")

    def require_update(self) -> None:
        """Only Owner can update existing records."""
        if self.user.role != UserRole.owner:
            raise PermissionDeniedError("Only owner can update existing records.")

    def require_delete(self) -> None:
        """Only Owner can delete (soft-delete) records."""
        if self.user.role != UserRole.owner:
            raise PermissionDeniedError("Only owner can delete records.")

    def require_owner_only(self) -> None:
        """Raise 403 if the current user is not the owner."""
        if self.user.role != UserRole.owner:
            raise PermissionDeniedError("This action is restricted to the owner.")

    # ─── User / staff management ─────────────────────────────────────────────

    def require_can_create_user(self, target_role: UserRole) -> None:
        """
        Owner can create any role.
        Moderator can only create staff accounts.
        """
        if self.user.role == UserRole.owner:
            return
        if self.user.role == UserRole.moderator:
            if target_role != UserRole.staff:
                raise PermissionDeniedError(
                    "Moderators can only create staff accounts."
                )
            return
        raise PermissionDeniedError("Insufficient permissions to create users.")

    def require_can_manage_user(self) -> None:
        """Only owner can edit/deactivate/reset-password for existing users."""
        if self.user.role != UserRole.owner:
            raise PermissionDeniedError(
                "Only the owner can edit or deactivate user accounts."
            )

    # ─── Attendance approval ─────────────────────────────────────────────────

    def require_can_approve_attendance(self, target_user: User) -> None:
        """
        Approval hierarchy:
        - Owner can approve anyone's attendance.
        - Moderator can approve staff attendance ONLY (not other moderators).
        - Nobody can approve their own attendance.
        """
        if self.user.id == target_user.id:
            raise PermissionDeniedError("Cannot self-approve attendance.")

        if self.user.role == UserRole.owner:
            return  # Owner approves everyone

        if self.user.role == UserRole.moderator:
            if target_user.role != UserRole.staff:
                raise PermissionDeniedError(
                    "Moderators can only approve staff attendance. "
                    "Moderator attendance must be approved by the owner."
                )
            return

        raise PermissionDeniedError("Insufficient permissions to approve attendance.")

    # ─── Bulk import ─────────────────────────────────────────────────────────

    def require_can_bulk_import(self) -> None:
        """Owner and Moderator can perform bulk imports."""
        if self.user.role not in (UserRole.owner, UserRole.moderator):
            raise PermissionDeniedError("Only owner or moderator can perform bulk imports.")
