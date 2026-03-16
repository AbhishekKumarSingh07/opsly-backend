from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

logger = logging.getLogger("opsly.amc_checker")

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"


def check_upcoming_amc_services(db: Session) -> None:
    """
    Daily AMC service checker (runs at 06:00 IST via APScheduler).

    Logic:
    1. Find all active DG sets.
    2. For each, calculate days until next service.
    3. If <= 7 days and no open ticket exists → auto-create HIGH priority ticket.
    4. If overdue (<=0 days) and no completed ticket → create CRITICAL ticket + escalate.
    """
    from app.models.dg_set import DGSet
    from app.models.ticket import Ticket, TicketPriority, TicketStatus, TicketStatusHistory
    from app.repositories.ticket_repo import TicketRepository
    from app.services.notification_service import NotificationService

    today = datetime.now(timezone.utc).date()
    ticket_repo = TicketRepository(db)

    dg_sets = db.query(DGSet).filter(DGSet.is_deleted.is_(False)).all()
    notification_service = NotificationService(db)

    for dg in dg_sets:
        if not dg.next_service_date:
            continue

        days_until = (dg.next_service_date - today).days

        if days_until <= 7:
            open_tickets = ticket_repo.list_open_for_dg_set(dg.id)
            if open_tickets:
                logger.debug("DG set %s already has an open ticket — skipping AMC auto-create", dg.id)
                continue

            priority = TicketPriority.CRITICAL if days_until <= 0 else TicketPriority.HIGH
            note = (
                f"AUTO: AMC Service Overdue by {abs(days_until)} day(s)"
                if days_until <= 0
                else f"AUTO: AMC Service Due in {days_until} day(s)"
            )

            import re
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            prefix = f"TKT-{date_str}-"
            from sqlalchemy import func
            count = (
                db.query(func.count(Ticket.id))
                .filter(Ticket.reference_no.like(f"{prefix}%"))
                .scalar()
                or 0
            )
            reference_no = f"{prefix}{(count + 1):04d}"

            ticket = Ticket(
                reference_no=reference_no,
                dg_set_id=dg.id,
                created_by=SYSTEM_USER_ID,
                status=TicketStatus.OPEN,
                priority=priority,
                reported_issue="AMC Scheduled Maintenance",
                notes=note,
            )
            db.add(ticket)
            db.flush()

            history = TicketStatusHistory(
                ticket_id=ticket.id,
                from_status=None,
                to_status=TicketStatus.OPEN.value,
                changed_by=SYSTEM_USER_ID,
                changed_at=datetime.now(timezone.utc),
                notes=note,
            )
            db.add(history)

            notification_service.notify_amc_due(str(dg.id), days_until)

            if days_until <= 0:
                notification_service.notify_escalation(
                    str(dg.id), f"AMC overdue by {abs(days_until)} day(s)"
                )

            logger.info(
                "Auto-created %s ticket %s for DG set %s (days_until=%d)",
                priority.value, reference_no, dg.id, days_until,
            )
