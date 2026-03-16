from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.user import UserRole
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.ticket_repo import TicketRepository
from app.services.attendance_service import AttendanceService
from app.services.expense_service import ExpenseService
from app.services.ticket_service import TicketService
from app.schemas.attendance import AttendancePunchInSchema
from app.schemas.ticket import TicketStatusUpdate
from app.schemas.expense import ExpenseCreate

router = APIRouter(prefix="/sync", tags=["Offline Sync"])


@router.post("/batch")
def batch_sync(
    body: dict,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Process an ordered list of offline actions submitted by a client after reconnecting.

    - Actions are processed sequentially in order.
    - Idempotency keys (client_uuid) prevent duplicate processing.
    - GPS-sensitive actions validate coordinates server-side.
    - Partial success is allowed — one failed action does not block subsequent ones.
    - The client's local_timestamp is stored for audit purposes ONLY.
    - Accessible by: all authenticated users (typically staff).

    Request body:
    {
      "actions": [
        {
          "client_uuid": "uuid4",
          "action_type": "UPDATE_TICKET_STATUS" | "UPLOAD_PHOTO" | "PUNCH_IN" | "LOG_EXPENSE",
          "payload": { ... },
          "local_timestamp": "ISO8601"
        }
      ]
    }
    """
    from app.utils.idempotency import check_idempotency_key, store_idempotency_key
    import json

    actions = body.get("actions", [])
    results = []

    for action in actions:
        client_uuid = action.get("client_uuid", "")
        action_type = action.get("action_type", "")
        payload = action.get("payload", {})

        idem_key = f"sync:{current_user.id}:{client_uuid}"
        cached = check_idempotency_key(idem_key)
        if cached:
            results.append({"client_uuid": client_uuid, "success": True, "error": None, "data": json.loads(cached)})
            continue

        try:
            data = _process_action(action_type, payload, current_user, db)
            store_idempotency_key(idem_key, json.dumps(data))
            results.append({"client_uuid": client_uuid, "success": True, "error": None, "data": data})
        except Exception as exc:
            results.append({
                "client_uuid": client_uuid,
                "success": False,
                "error": str(exc),
                "data": None,
            })

    return {"results": results}


def _process_action(action_type: str, payload: dict, user, db: Session) -> dict:
    """Dispatch a single sync action to the appropriate service."""
    if action_type == "PUNCH_IN":
        schema = AttendancePunchInSchema(**payload)
        service = AttendanceService(db)
        record = service.punch_in(user, schema)
        return {"attendance_id": str(record.id), "status": record.status.value}

    elif action_type == "UPDATE_TICKET_STATUS":
        from uuid import UUID
        ticket_id = UUID(payload["ticket_id"])
        schema = TicketStatusUpdate(**payload)
        service = TicketService(db)
        ticket = service.update_status(ticket_id, schema.new_status, user, schema.notes)
        return {"ticket_id": str(ticket.id), "status": ticket.status.value}

    elif action_type == "LOG_EXPENSE":
        schema = ExpenseCreate(**payload)
        service = ExpenseService(db)
        expense = service.create_expense(schema, user)
        return {"expense_id": str(expense.id), "amount": str(expense.amount)}

    elif action_type == "UPLOAD_PHOTO":
        # Photos should be uploaded via the /uploads/photo endpoint before sync
        # Here we just record the reference
        return {"message": "Photo references accepted", "s3_url": payload.get("s3_url")}

    else:
        raise BusinessRuleError("UNKNOWN_ACTION_TYPE", f"Unknown action type: {action_type}")
