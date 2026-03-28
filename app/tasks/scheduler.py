from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("opsly.scheduler")

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    return _scheduler


def start_scheduler() -> None:
    """Register all cron jobs and start the background scheduler."""
    from app.tasks.amc_checker import check_upcoming_amc_services
    from app.tasks.inventory_reconciler import check_low_stock

    scheduler = get_scheduler()

    # AMC check — daily at 06:00 IST
    scheduler.add_job(
        _run_amc_check,
        trigger=CronTrigger(hour=6, minute=0, timezone="Asia/Kolkata"),
        id="amc_checker",
        replace_existing=True,
    )

    # Inventory reconciliation — daily at 02:00 IST
    scheduler.add_job(
        _run_inventory_reconciler,
        trigger=CronTrigger(hour=2, minute=0, timezone="Asia/Kolkata"),
        id="inventory_reconciler",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("APScheduler started with %d jobs", len(scheduler.get_jobs()))


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


def _run_amc_check() -> None:
    from app.db.base import SessionLocal
    from app.tasks.amc_checker import check_upcoming_amc_services
    db = SessionLocal()
    try:
        check_upcoming_amc_services(db)
        db.commit()
    except Exception as exc:
        logger.exception("AMC checker failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def _run_inventory_reconciler() -> None:
    from app.db.base import SessionLocal
    from app.tasks.inventory_reconciler import check_low_stock
    db = SessionLocal()
    try:
        check_low_stock(db)
        db.commit()
    except Exception as exc:
        logger.exception("Inventory reconciler failed: %s", exc)
        db.rollback()
    finally:
        db.close()
