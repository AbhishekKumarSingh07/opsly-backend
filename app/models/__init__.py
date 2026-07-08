from __future__ import annotations

# Make all models importable from app.models
from app.models.user import User, UserRole
from app.models.site import Site
from app.models.dg_set import DGSet
from app.models.ticket import Ticket, TicketStatus, TicketPriority, TicketStatusHistory, TicketPhoto, PhotoType
from app.models.attendance import Attendance, AttendanceStatus
from app.models.inventory import InventoryItem, InventoryCategory, InventoryDispatch
from app.models.tender import Tender, TenderStatus, TenderMilestone, TenderDocument
from app.models.expense import Expense, ExpenseStatus
from app.models.client import Client
from app.models.audit_log import AuditLog, AuditAction
from app.models.bulk_import import BulkImportLog, ImportType, ImportFormat, ImportStatus
from app.models.payroll import SalaryRecord, SalaryStatus, AdvancePayment

__all__ = [
    "User", "UserRole",
    "Site",
    "DGSet",
    "Ticket", "TicketStatus", "TicketPriority", "TicketStatusHistory", "TicketPhoto", "PhotoType",
    "Attendance", "AttendanceStatus",
    "InventoryItem", "InventoryCategory", "InventoryDispatch",
    "Tender", "TenderStatus", "TenderMilestone", "TenderDocument",
    "Expense", "ExpenseStatus",
    "Client",
    "AuditLog", "AuditAction",
    "SalaryRecord", "SalaryStatus", "AdvancePayment",
]
