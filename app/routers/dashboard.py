from __future__ import annotations

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
    Owner dashboard summary — full business overview.

    Returns all KPIs needed for the owner dashboard:
    - Workforce: total employees, punched-in today, pending approvals
    - Tickets: open, closed (completed/invoiced), total
    - Inventory: total item types, total serialized items, items in field,
                 per-status breakdown (IN_STOCK, CHECKED_OUT, DAMAGED, CONSUMED)
    - Payroll: paid/pending count and amount for current month
    - Recent tickets + today attendance feed
    - Accessible by: owner only.
    """
    from datetime import datetime, timezone
    from sqlalchemy import func
    from app.models.ticket import Ticket, TicketStatus
    from app.models.user import User, UserRole
    from app.models.inventory import InventoryItem
    from app.models.payroll import SalaryRecord, SalaryStatus
    from app.models.dg_set import DGSet

    ticket_repo = TicketRepository(db)
    inv_repo = InventoryRepository(db)
    att_repo = AttendanceRepository(db)
    tender_repo = TenderRepository(db)
    expense_repo = ExpenseRepository(db)

    today = datetime.now(timezone.utc).date()

    # ── Workforce ──────────────────────────────────────────────────────────────
    total_employees = (
        db.query(func.count(User.id))
        .filter(User.is_active.is_(True), User.role != UserRole.owner)
        .scalar() or 0
    )

    # Punched in = has an attendance record today (any status except absent/rejected)
    punched_in_today = (
        db.query(func.count(Attendance.id))
        .filter(
            Attendance.date == today,
            Attendance.status.in_([
                AttendanceStatus.PENDING_APPROVAL,
                AttendanceStatus.FLAGGED,
                AttendanceStatus.APPROVED,
            ]),
        )
        .scalar() or 0
    )

    # ── Tickets ────────────────────────────────────────────────────────────────
    open_tickets = ticket_repo.count_open()
    closed_tickets = (
        db.query(func.count(Ticket.id))
        .filter(
            Ticket.status.in_([TicketStatus.COMPLETED, TicketStatus.INVOICED, TicketStatus.CANCELLED]),
            Ticket.is_deleted.is_(False),
        )
        .scalar() or 0
    )
    total_tickets = (
        db.query(func.count(Ticket.id))
        .filter(Ticket.is_deleted.is_(False))
        .scalar() or 0
    )

    # ── Inventory ──────────────────────────────────────────────────────────────
    # Total distinct part types and total quantity in stock
    total_item_types = (
        db.query(func.count(InventoryItem.id))
        .filter(InventoryItem.is_deleted.is_(False))
        .scalar() or 0
    )
    total_quantity = (
        db.query(func.coalesce(func.sum(InventoryItem.quantity), 0))
        .filter(InventoryItem.is_deleted.is_(False))
        .scalar() or 0
    )
    low_stock_count = inv_repo.count_filtered(
        category_id=None, search=None, low_stock_only=True
    )

    # ── Overdue AMC ────────────────────────────────────────────────────────────
    overdue_amc = (
        db.query(DGSet)
        .filter(DGSet.next_service_date <= today, DGSet.is_deleted.is_(False))
        .count()
    )

    # ── Payroll (current month) ─────────────────────────────────────────────────
    payroll_rows = (
        db.query(SalaryRecord.status, func.count(SalaryRecord.id), func.sum(SalaryRecord.net_payable))
        .filter(SalaryRecord.year == today.year, SalaryRecord.month == today.month)
        .group_by(SalaryRecord.status)
        .all()
    )
    payroll_summary = {}
    for row in payroll_rows:
        payroll_summary[row[0].value] = {
            "count": row[1],
            "total": float(row[2] or 0),
        }
    payroll_paid = payroll_summary.get("PAID", {"count": 0, "total": 0.0})
    payroll_pending = payroll_summary.get("PENDING", {"count": 0, "total": 0.0})

    # ── Today's attendance feed ────────────────────────────────────────────────
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
            "approved_by_name": approver.name if approver else None,
            "approved_at": rec.approved_at.isoformat() if rec.approved_at else None,
        })

    # ── Recent tickets ─────────────────────────────────────────────────────────
    recent_tickets_raw = ticket_repo.list_all(skip=0, limit=8)
    recent_tickets = []
    for t in recent_tickets_raw:
        creator = db.get(User, t.created_by)
        technician_names = [tech.name for tech in (t.technicians or [])]
        recent_tickets.append({
            "ticket_id": str(t.id),
            "reference_no": t.reference_no,
            "status": t.status.value,
            "priority": t.priority.value,
            "reported_issue": t.reported_issue[:80],
            "created_by_name": creator.name if creator else None,
            "assigned_to": technician_names,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })

    return {
        # Workforce
        "total_employees": total_employees,
        "punched_in_today": punched_in_today,
        "pending_attendance_approvals": att_repo.count_pending(),
        # Tickets
        "open_tickets": open_tickets,
        "closed_tickets": closed_tickets,
        "total_tickets": total_tickets,
        # Inventory
        "total_item_types": total_item_types,
        "total_quantity_in_stock": int(total_quantity),
        "low_stock_items": low_stock_count,
        # Overdue AMC
        "overdue_amc": overdue_amc,
        # Payroll (current month)
        "payroll_paid_count": payroll_paid["count"],
        "payroll_paid_total": payroll_paid["total"],
        "payroll_pending_count": payroll_pending["count"],
        "payroll_pending_total": payroll_pending["total"],
        # Feeds
        "tenders_by_status": tender_repo.count_by_status(),
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

    low_stock_count = inv_repo.count_filtered(
        category_id=None, search=None, low_stock_only=True
    )

    return {
        "open_tickets": ticket_repo.count_open(),
        "assigned_today": assigned_today,
        "pending_attendance": att_repo.count_pending(),
        "low_stock_items": low_stock_count,
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
