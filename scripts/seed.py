#!/usr/bin/env python
"""
Dev-only seed script.
Creates: 1 Owner, 1 Moderator, 1 Staff user.

Usage:
    python scripts/seed.py
"""
from __future__ import annotations

import os
import sys
import uuid

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.security import hash_password
from app.db.base import SessionLocal


def seed() -> None:
    db = SessionLocal()
    try:
        from app.models.user import User, UserRole

        # ── Users ─────────────────────────────────────────────────────────────
        users: list[tuple[str, str, str, str, UserRole]] = [
            ("Rahul Sharma", "owner@opsly.local", "9900000001", "owner@123",     UserRole.owner),
            ("Priya Mehta",  "mod@opsly.local",   "9900000002", "moderator@123", UserRole.moderator),
            ("Arjun Singh",  "staff@opsly.local", "9900000003", "staff@123",     UserRole.staff),
        ]

        results: list[tuple[str, str, str]] = []
        for name, email, phone, password, role in users:
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                results.append((role.value, email, "(already exists)"))
                continue

            user = User(
                id=uuid.uuid4(),
                name=name,
                email=email,
                phone=phone,
                role=role,
                hashed_password=hash_password(password),
                is_active=True,
                must_change_password=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            results.append((role.value, email, password))

        print("\n" + "=" * 55)
        print("  Opsly — Seed Complete")
        print("=" * 55)
        print(f"\n  {'Role':<12}  {'Email':<28}  {'Password'}")
        print(f"  {'-'*12}  {'-'*28}  {'-'*14}")
        for role, email, password in results:
            print(f"  {role:<12}  {email:<28}  {password}")
        print("=" * 55 + "\n")

    except Exception as exc:
        db.rollback()
        print(f"[ERROR] Seeding failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
