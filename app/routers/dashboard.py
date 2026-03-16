from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_role
from app.models.attendance import Attendance, AttendanceStatus
from app.models.expense import ExpenseStatus
from app.models.ticket import TicketStatus
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.expense_repo import ExpenseRepository
from app.repositories.inventory_repo import InventoryRepository
from app.repositories.tender_repo import TenderRepository
from app.repositories.ticket_repo import TicketRepository

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/owner", dependencies=[Depends(require_role("owner"))])
def owner_dashboard(db: Session = Depends(get_db)):
    """
    Owner dashboard summary.

    Returns:
        open_tickets, overdue_amc, parts_in_field, pending_attendance_approvals,
        monthly_revenue, tenders_by_status, top_pending_expenses,
        today_attendance (with approver info), recent_tickets (with moderator/assignee info).

    - Accessible by: owner only.
    """
    from datetime import datetime, timezone
    from app.models.ticket import Ticket
    from app.models.user import User

    ticket_repo = TicketRepository(db)
    inv_repo = InventoryRepository(db)
    att_repo = AttendanceRepository(db)
    tender_repo = TenderRepository(db)
    expense_repo = ExpenseRepository(db)

    today = datetime.now(timezone.utc).date()

    # Overdue AMC
    from app.models.dg_set import DGSet
    overdue_amc = (
        db.query(DGSet)
        .filter(DGSet.next_service_date <= today, DGSet.is_deleted.is_(False))
        .count()
    )

    top_expenses = expense_repo.top_pending(5)

    # Today's attendance — include approver name + role
    today_attendance_records = att_repo.list_all_range(today, today, 0, 200)
    today_attendance = []
    for rec in today_attendance_records:
        user = db.get(User, rec.user_id)
        approver = db.get(User, rec.approved_by) if rec.approved_by else None
        today_attendance.append({
            "attendance_id": str(rec.id),
            "user_id": str(rec.user_id),
            "user_name": user.name if user else None,
            "user_role": user.role.value if user else None,
            "status": rec.status.value,
            "punch_in_time": rec.punch_in_time.isoformat() if rec.punch_in_time else None,
            "punch_out_time": rec.punch_out_time.isoformat() if rec.punch_out_time else None,
            "flag_reason": rec.flag_reason,
            "approved_by_id": str(rec.approved_by) if rec.approved_by else None,
            "approved_by_name": approver.name if approver else None,
            "approved_by_role": approver.role.value if approver else None,
            "approved_at": rec.approved_at.isoformat() if rec.approved_at else None,
        })

    # Recent tickets — include creator (moderator) + assigned technicians
    recent_tickets_raw = ticket_repo.list_all(skip=0, limit=10)
    recent_tickets = []
    for t in recent_tickets_raw:
        creator = db.get(User, t.created_by)
        technician_names = [tech.name for tech in (t.technicians or [])]
        recent_tickets.append({
            "ticket_id": str(t.id),
            "reference_no": t.reference_no,
            "status": t.status.value,
            "priority": t.priority.value,
            "reported_issue": t.reported_issue[:100],
            "created_by_id": str(t.created_by),
            "created_by_name": creator.name if creator else None,
            "created_by_role": creator.role.value if creator else None,
            "assigned_to": technician_names,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })

    return {
        "open_tickets": ticket_repo.count_open(),
        "overdue_amc": overdue_amc,
        "parts_in_field": inv_repo.count_in_field(),
        "pending_attendance_approvals": att_repo.count_pending(),
        "monthly_revenue": Decimal("0.00"),  # TODO: wire to invoice totals
        "tenders_by_status": tender_repo.count_by_status(),
        "top_pending_expenses": [
            {
                "id": str(e.id),
                "amount": str(e.amount),
                "submitted_by": str(e.submitted_by),
                "ticket_ref": str(e.ticket_id) if e.ticket_id else None,
            }
            for e in top_expenses
        ],
        "today_attendance": today_attendance,
        "recent_tickets": recent_tickets,
    }


@router.get("/moderator", dependencies=[Depends(require_role("owner", "moderator"))])
def moderator_dashboard(db: Session = Depends(get_db)):
    """
    Moderator dashboard summary.

    Returns:
        open_tickets, assigned_today, pending_attendance, low_stock_items.

    - Accessible by: moderator, owner.
    """
    from datetime import datetime, timezone
    from app.models.ticket import Ticket, TicketStatus

    ticket_repo = TicketRepository(db)
    inv_repo = InventoryRepository(db)
    att_repo = AttendanceRepository(db)

    today = datetime.now(timezone.utc).date()
    assigned_today = (
        db.query(Ticket)
        .filter(
            Ticket.status == TicketStatus.ASSIGNED,
            Ticket.is_deleted.is_(False),
        )
        .count()
    )

    low_stock = inv_repo.list_low_stock(db)

    return {
        "open_tickets": ticket_repo.count_open(),
        "assigned_today": assigned_today,
        "pending_attendance": att_repo.count_pending(),
        "low_stock_items": len(low_stock),
    }


@router.get("/staff")
def staff_dashboard(
    current_user=Depends(require_role("owner", "moderator", "staff")),
    db: Session = Depends(get_db),
):
    """
    Staff dashboard summary.

    Returns:
        my_open_tickets, today_attendance_status, pending_expense_approvals.

    - Accessible by: all roles.
    """
    from datetime import datetime, timezone
    from app.models.ticket import ticket_technicians
    from app.models.expense import ExpenseStatus

    today = datetime.now(timezone.utc).date()
    att_repo = AttendanceRepository(db)
    attendance = att_repo.get_today_record(current_user.id, today)

    expense_repo = ExpenseRepository(db)
    my_expenses = expense_repo.list_for_user(current_user.id)
    pending_expense_approvals = sum(
        1 for e in my_expenses if e.status == ExpenseStatus.SUBMITTED
    )

    from app.repositories.ticket_repo import TicketRepository
    ticket_repo = TicketRepository(db)
    my_tickets = ticket_repo.list_for_user(current_user.id, skip=0, limit=200)
    open_count = sum(1 for t in my_tickets if t.status not in ("COMPLETED", "INVOICED", "CANCELLED"))

    return {
        "my_open_tickets": open_count,
        "today_attendance_status": attendance.status.value if attendance else None,
        "pending_expense_approvals": pending_expense_approvals,
    }
