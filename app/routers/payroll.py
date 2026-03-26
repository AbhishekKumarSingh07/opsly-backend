from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, require_role
from app.schemas.payroll import (
    AdvancePaymentCreate,
    AdvancePaymentResponse,
    SalaryRecordCreate,
    SalaryRecordResponse,
    SalaryRecordUpdate,
    StaffPayrollSummary,
)
from app.services.payroll_service import PayrollService

router = APIRouter(prefix="/payroll", tags=["Payroll"])


# ─── Payroll Summary ──────────────────────────────────────────────────────────

@router.get(
    "/summary",
    response_model=list[StaffPayrollSummary],
    dependencies=[Depends(require_role("owner"))],
)
def get_payroll_summary(db: Session = Depends(get_db)):
    """
    Return a combined payroll snapshot (salary + advances) for every
    staff and moderator.

    Accessible by: owner only.
    """
    service = PayrollService(db)
    return service.get_payroll_summary()


# ─── Salary Records ───────────────────────────────────────────────────────────

@router.post(
    "/salary",
    response_model=SalaryRecordResponse,
    status_code=201,
)
def create_salary_record(
    payload: SalaryRecordCreate,
    current_user=Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    """
    Create a monthly salary record for a staff/moderator user.

    - Raises 409 if a record for that user/year/month already exists.
    - net_payable is auto-computed as gross_salary − advance_deducted.
    - Accessible by: owner only.
    """
    service = PayrollService(db)
    record = service.create_salary_record(current_user, payload)
    return SalaryRecordResponse.from_orm_with_relations(record)


@router.patch("/salary/{salary_id}", response_model=SalaryRecordResponse)
def update_salary_record(
    salary_id: UUID,
    payload: SalaryRecordUpdate,
    current_user=Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    """
    Update a salary record's status, notes, or paid_at timestamp.

    Accessible by: owner only.
    """
    service = PayrollService(db)
    record = service.update_salary_record(current_user, salary_id, payload)
    return SalaryRecordResponse.from_orm_with_relations(record)


@router.get(
    "/salary/user/{user_id}",
    response_model=list[SalaryRecordResponse],
    dependencies=[Depends(require_role("owner"))],
)
def list_salary_records_for_user(
    user_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Return all salary records for a specific user.

    Accessible by: owner only.
    """
    service = PayrollService(db)
    records = service.list_salary_records_for_user(user_id)
    return [SalaryRecordResponse.from_orm_with_relations(r) for r in records]


@router.get(
    "/salary",
    response_model=list[SalaryRecordResponse],
    dependencies=[Depends(require_role("owner"))],
)
def list_all_salary_records(
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """
    List all salary records across all users.

    Accessible by: owner only.
    """
    service = PayrollService(db)
    records = service.list_all_salary_records(skip=skip, limit=limit)
    return [SalaryRecordResponse.from_orm_with_relations(r) for r in records]


# ─── Advance Payments ─────────────────────────────────────────────────────────

@router.post(
    "/advance",
    response_model=AdvancePaymentResponse,
    status_code=201,
)
def create_advance_payment(
    payload: AdvancePaymentCreate,
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Record a cash advance given to a staff or moderator.

    - Owner can give advances to staff and moderators.
    - Moderator can only give advances to staff.
    - Accessible by: owner, moderator.
    """
    service = PayrollService(db)
    advance = service.create_advance_payment(current_user, payload)
    return AdvancePaymentResponse.from_orm_with_relations(advance)


@router.get(
    "/advance/user/{user_id}",
    response_model=list[AdvancePaymentResponse],
    dependencies=[Depends(require_role("owner", "moderator"))],
)
def list_advances_for_user(
    user_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Return all advance payments for a specific user.

    Accessible by: owner, moderator.
    """
    service = PayrollService(db)
    advances = service.list_advances_for_user(user_id)
    return [AdvancePaymentResponse.from_orm_with_relations(a) for a in advances]


@router.get(
    "/advance",
    response_model=list[AdvancePaymentResponse],
    dependencies=[Depends(require_role("owner"))],
)
def list_all_advances(
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """
    List all advance payments across all users.

    Accessible by: owner only.
    """
    service = PayrollService(db)
    advances = service.list_all_advances(skip=skip, limit=limit)
    return [AdvancePaymentResponse.from_orm_with_relations(a) for a in advances]
