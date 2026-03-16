from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.db.base import Base


def _get_model_state(instance) -> dict[str, Any]:
    """Serialize an ORM model instance to a plain dict of column values."""
    result: dict[str, Any] = {}
    mapper = inspect(instance.__class__)
    for col in mapper.columns:
        val = getattr(instance, col.key, None)
        if isinstance(val, uuid.UUID):
            val = str(val)
        elif isinstance(val, datetime):
            val = val.isoformat()
        result[col.key] = val
    return result


_AUDITED_TABLES = {"tickets", "inventory_items", "attendance", "tenders"}


def _write_audit_log(
    session: Session,
    table_name: str,
    record_id: uuid.UUID | str,
    action: str,
    old_value: dict | None,
    new_value: dict | None,
) -> None:
    """Insert a row into audit_log within the same session."""
    from app.models.audit_log import AuditLog  # lazy import to avoid circular deps

    actor_id: uuid.UUID | None = getattr(session, "_audit_actor_id", None)
    ip_address: str | None = getattr(session, "_audit_ip_address", None)

    log = AuditLog(
        table_name=table_name,
        record_id=str(record_id),
        action=action,
        old_value=old_value,
        new_value=new_value,
        actor_id=actor_id,
        ip_address=ip_address,
        timestamp=datetime.now(timezone.utc),
    )
    session.add(log)


def register_audit_listeners() -> None:
    """
    Register SQLAlchemy after_flush event to auto-write audit log entries
    for critical tables: tickets, inventory_items, attendance, tenders.
    """

    @event.listens_for(Session, "after_bulk_delete")
    def _prevent_bulk_delete(delete_context):  # type: ignore[misc]
        table = delete_context.primary_table.name
        if table in _AUDITED_TABLES:
            raise RuntimeError(
                f"Bulk DELETE on audited table '{table}' is not allowed. Use soft delete."
            )

    @event.listens_for(Session, "before_flush")
    def _capture_audit(session: Session, flush_context, instances):  # type: ignore[misc]
        for instance in session.new:
            table = getattr(instance, "__tablename__", None)
            if table in _AUDITED_TABLES:
                record_id = getattr(instance, "id", None)
                new_val = _get_model_state(instance)
                _write_audit_log(session, table, record_id, "CREATE", None, new_val)

        for instance in session.dirty:
            if not session.is_modified(instance):
                continue
            table = getattr(instance, "__tablename__", None)
            if table in _AUDITED_TABLES:
                record_id = getattr(instance, "id", None)
                # Capture old values from identity map history
                old_val: dict[str, Any] = {}
                mapper = inspect(instance.__class__)
                for attr in mapper.attrs:
                    hist = attr.load_history()  # type: ignore[attr-defined]
                    if hist.deleted:
                        old_val[attr.key] = hist.deleted[0]  # type: ignore[index]
                new_val = _get_model_state(instance)
                _write_audit_log(session, table, record_id, "UPDATE", old_val, new_val)
