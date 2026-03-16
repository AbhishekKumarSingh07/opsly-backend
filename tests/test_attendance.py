from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from tests.conftest import auth_headers_for


def test_punch_in_within_geofence(client: TestClient, staff_user, sample_ticket, test_db):
    """Staff punch-in within geofence (mocked) creates PENDING_APPROVAL record."""
    # Assign staff to ticket
    sample_ticket.technicians = [staff_user]
    from app.models.dg_set import DGSet
    from app.models.site import Site

    # Add a site with GPS to the ticket's DG set
    site = Site(name="Test Site", gps_lat=28.6139, gps_lng=77.2090)
    test_db.add(site)
    test_db.flush()

    dg = DGSet(site_id=site.id)
    test_db.add(dg)
    test_db.flush()

    sample_ticket.dg_set_id = dg.id
    test_db.commit()

    headers = auth_headers_for(staff_user)
    with patch("app.services.attendance_service.is_within_radius", return_value=True):
        resp = client.post(
            "/api/v1/attendance/punch-in",
            json={
                "gps_lat": 28.6139,
                "gps_lng": 77.2090,
                "selfie_url": "https://example.com/selfie.jpg",
                "liveness_score": 0.95,
                "ticket_id": str(sample_ticket.id),
            },
            headers=headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PENDING_APPROVAL"


def test_punch_in_outside_geofence_creates_flagged(client: TestClient, staff_user, sample_ticket, test_db):
    """Staff punch-in outside geofence creates FLAGGED record."""
    from app.models.dg_set import DGSet
    from app.models.site import Site

    site = Site(name="Test Site", gps_lat=28.6139, gps_lng=77.2090)
    test_db.add(site)
    test_db.flush()
    dg = DGSet(site_id=site.id)
    test_db.add(dg)
    test_db.flush()
    sample_ticket.dg_set_id = dg.id
    sample_ticket.technicians = [staff_user]
    test_db.commit()

    headers = auth_headers_for(staff_user)
    with patch("app.services.attendance_service.is_within_radius", return_value=False):
        with patch("app.services.notification_service.NotificationService.notify_flagged_attendance"):
            resp = client.post(
                "/api/v1/attendance/punch-in",
                json={
                    "gps_lat": 19.0760,
                    "gps_lng": 72.8777,
                    "selfie_url": "https://example.com/selfie.jpg",
                    "liveness_score": 0.9,
                    "ticket_id": str(sample_ticket.id),
                },
                headers=headers,
            )
    assert resp.status_code == 200
    assert resp.json()["status"] == "FLAGGED"


def test_self_approval_rejected(client: TestClient, staff_user, test_db):
    """A user cannot approve their own attendance record."""
    from app.models.attendance import Attendance, AttendanceStatus
    from datetime import datetime, timezone, date

    att = Attendance(
        user_id=staff_user.id,
        date=date.today(),
        punch_in_time=datetime.now(timezone.utc),
        status=AttendanceStatus.PENDING_APPROVAL,
    )
    test_db.add(att)
    test_db.commit()
    test_db.refresh(att)

    headers = auth_headers_for(staff_user)
    # Staff cannot access approve endpoint (moderator/owner only)
    resp = client.patch(
        f"/api/v1/attendance/{att.id}/approve",
        json={"notes": "self approve"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_duplicate_punch_in_rejected(client: TestClient, owner_user, test_db):
    """A second punch-in on the same day is rejected."""
    from app.models.attendance import Attendance, AttendanceStatus
    from datetime import datetime, timezone, date

    att = Attendance(
        user_id=owner_user.id,
        date=date.today(),
        punch_in_time=datetime.now(timezone.utc),
        status=AttendanceStatus.PENDING_APPROVAL,
    )
    test_db.add(att)
    test_db.commit()

    headers = auth_headers_for(owner_user)
    with patch("app.services.attendance_service.is_within_radius", return_value=True):
        resp = client.post(
            "/api/v1/attendance/punch-in",
            json={
                "gps_lat": 28.6139,
                "gps_lng": 77.2090,
                "selfie_url": "https://example.com/selfie2.jpg",
                "liveness_score": 0.9,
            },
            headers=headers,
        )
    assert resp.status_code == 409
