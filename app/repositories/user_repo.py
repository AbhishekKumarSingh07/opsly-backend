from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_by_email(self, email: str) -> User | None:
        """Fetch an active user by email address."""
        return (
            self.db.query(User)
            .filter(User.email == email, User.is_active.is_(True))
            .first()
        )

    def get_by_id_active(self, user_id) -> User | None:
        """Fetch an active user by primary key."""
        return (
            self.db.query(User)
            .filter(User.id == user_id, User.is_active.is_(True))
            .first()
        )

    def list_by_role(self, role: str) -> list[User]:
        """Return all active users with a given role."""
        return (
            self.db.query(User)
            .filter(User.role == role, User.is_active.is_(True))
            .all()
        )
