from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import create_access_token, verify_password, decode_token
from app.models.client import Client

router = APIRouter(prefix="/portal", tags=["Client Portal"])


class PortalLoginRequest(BaseModel):
    client_id: UUID
    password: str


class PortalTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _get_portal_client(token: str, db: Session) -> Client:
    """Validate a portal JWT and return the corresponding Client."""
    payload = decode_token(token)
    if payload.get("role") != "client":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client token required")
    client_id = payload.get("sub")
    client = db.get(Client, client_id)
    if not client or client.is_deleted or not client.portal_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Portal access denied")
    return client


@router.post("/login", response_model=PortalTokenResponse)
def portal_login(payload: PortalLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate a client for portal access.

    - Uses portal_password_hash stored on the Client record.
    - Returns a JWT with role='client'.
    - Accessible by: external clients.
    """
    client = db.get(Client, payload.client_id)
    if not client or not client.portal_password_hash or not client.portal_enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(payload.password, client.portal_password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": str(client.id), "role": "client"})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/assets")
def portal_assets(
    authorization: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Return DG sets belonging to the authenticated client.

    - Enforces client_id filter — clients can only see their own assets.
    - Accessible by: authenticated clients.
    """
    from fastapi.security.utils import get_authorization_scheme_param
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    _, token = get_authorization_scheme_param(authorization)
    client = _get_portal_client(token, db)

    from app.models.dg_set import DGSet
    from app.models.site import Site
    dg_sets = (
        db.query(DGSet)
        .join(Site, DGSet.site_id == Site.id)
        .filter(Site.client_id == client.id, DGSet.is_deleted.is_(False))
        .all()
    )
    return [
        {
            "id": str(dg.id),
            "make": dg.make,
            "model": dg.model,
            "capacity_kva": dg.capacity_kva,
            "serial_no": dg.serial_no,
            "last_service_date": str(dg.last_service_date) if dg.last_service_date else None,
            "next_service_date": str(dg.next_service_date) if dg.next_service_date else None,
        }
        for dg in dg_sets
    ]


@router.get("/assets/{dg_set_id}/tickets")
def portal_asset_tickets(
    dg_set_id: UUID,
    authorization: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Return recent completed tickets for a specific DG set owned by the client.

    - Accessible by: authenticated clients.
    """
    from fastapi.security.utils import get_authorization_scheme_param
    from app.models.ticket import Ticket, TicketStatus
    from app.models.dg_set import DGSet
    from app.models.site import Site

    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    _, token = get_authorization_scheme_param(authorization)
    client = _get_portal_client(token, db)

    # Verify this DG set belongs to the client
    dg = (
        db.query(DGSet)
        .join(Site, DGSet.site_id == Site.id)
        .filter(DGSet.id == dg_set_id, Site.client_id == client.id)
        .first()
    )
    if not dg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    tickets = (
        db.query(Ticket)
        .filter(
            Ticket.dg_set_id == dg_set_id,
            Ticket.status == TicketStatus.COMPLETED,
            Ticket.is_deleted.is_(False),
        )
        .order_by(Ticket.completed_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": str(t.id),
            "reference_no": t.reference_no,
            "reported_issue": t.reported_issue,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }
        for t in tickets
    ]


@router.get("/service-reports/{ticket_id}")
def portal_service_report(
    ticket_id: UUID,
    authorization: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Return a service report for a completed ticket.

    - Only tickets belonging to the client's assets are accessible.
    - In production: generate and return a signed S3 PDF URL.
    - Accessible by: authenticated clients.
    """
    from fastapi.security.utils import get_authorization_scheme_param
    from app.models.ticket import Ticket, TicketStatus
    from app.models.dg_set import DGSet
    from app.models.site import Site

    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    _, token = get_authorization_scheme_param(authorization)
    client = _get_portal_client(token, db)

    ticket = (
        db.query(Ticket)
        .join(DGSet, Ticket.dg_set_id == DGSet.id)
        .join(Site, DGSet.site_id == Site.id)
        .filter(
            Ticket.id == ticket_id,
            Site.client_id == client.id,
            Ticket.is_deleted.is_(False),
        )
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service report not found")

    # TODO: generate and return signed S3 PDF URL
    return {
        "ticket_id": str(ticket.id),
        "reference_no": ticket.reference_no,
        "reported_issue": ticket.reported_issue,
        "completed_at": ticket.completed_at.isoformat() if ticket.completed_at else None,
        "report_url": None,  # Placeholder for PDF generation
    }
