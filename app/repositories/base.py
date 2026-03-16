from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Generic CRUD base repository.
    Subclasses set `model` to the SQLAlchemy model class they manage.
    """

    model: type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, record_id: UUID | str) -> ModelT | None:
        """Fetch a single record by primary key."""
        return self.db.get(self.model, record_id)

    def list_all(self, skip: int = 0, limit: int = 100, **filters: Any) -> list[ModelT]:
        """Return a filtered, paginated list of records (excludes soft-deleted)."""
        q = self.db.query(self.model)
        if hasattr(self.model, "is_deleted"):
            q = q.filter(self.model.is_deleted.is_(False))
        for attr, val in filters.items():
            if val is not None and hasattr(self.model, attr):
                q = q.filter(getattr(self.model, attr) == val)
        return q.offset(skip).limit(limit).all()

    def count(self, **filters: Any) -> int:
        """Count records matching filters (excludes soft-deleted)."""
        q = self.db.query(self.model)
        if hasattr(self.model, "is_deleted"):
            q = q.filter(self.model.is_deleted.is_(False))
        for attr, val in filters.items():
            if val is not None and hasattr(self.model, attr):
                q = q.filter(getattr(self.model, attr) == val)
        return q.count()

    def create(self, obj: ModelT) -> ModelT:
        """Persist a new model instance."""
        self.db.add(obj)
        self.db.flush()
        self.db.refresh(obj)
        return obj

    def save(self, obj: ModelT) -> ModelT:
        """Flush pending changes for an existing object."""
        self.db.add(obj)
        self.db.flush()
        self.db.refresh(obj)
        return obj

    def soft_delete(self, obj: ModelT, deleted_by: UUID | None = None) -> ModelT:
        """Mark a record as deleted without removing from DB."""
        from datetime import datetime, timezone

        if hasattr(obj, "is_deleted"):
            obj.is_deleted = True  # type: ignore[attr-defined]
            obj.deleted_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]
            if deleted_by and hasattr(obj, "deleted_by"):
                obj.deleted_by = deleted_by  # type: ignore[attr-defined]
        return self.save(obj)
