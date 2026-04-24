"""
APScheduler-based follow-up sequence.

Schedule:
  Day 1  — immediate (sent inline, not via scheduler)
  Day 2  — 24 h after lead creation
  Day 4  — 96 h after lead creation
  Day 7  — 168 h after lead creation
"""

import os
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

log = logging.getLogger(__name__)

scheduler: BackgroundScheduler | None = None


def _calendly() -> str:
    return os.environ.get("CALENDLY_LINK", "https://calendly.com/your-link")


# ── message templates ─────────────────────────────────────────────────────────

def _msg_day2(name: str) -> str:
    first = name.split()[0] if name else "there"
    return (
        f"Hey {first}, did you get a chance to book with us? "
        f"We'd love to help! {_calendly()}"
    )


def _msg_day4(name: str) -> str:
    first = name.split()[0] if name else "there"
    return (
        f"Hey {first}, still here if you need us. "
        f"Here's our booking link: {_calendly()}"
    )


def _msg_day7() -> str:
    return (
        "Last follow-up from us — whenever you're ready, we're here. "
        f"{_calendly()}"
    )


# ── job functions (run inside app context) ────────────────────────────────────

def _send_day2(app, lead_id: int) -> None:
    with app.app_context():
        from models import db, Lead
        from sms import send_sms

        lead = db.session.get(Lead, lead_id)
        if not lead or lead.followup_day2_sent or lead.booked:
            return
        try:
            send_sms(lead.phone, _msg_day2(lead.name or ""))
            lead.followup_day2_sent = True
            db.session.commit()
            log.info("Day-2 follow-up sent to %s", lead.phone)
        except Exception:
            log.exception("Failed day-2 follow-up for lead %s", lead_id)


def _send_day4(app, lead_id: int) -> None:
    with app.app_context():
        from models import db, Lead
        from sms import send_sms

        lead = db.session.get(Lead, lead_id)
        if not lead or lead.followup_day4_sent or lead.booked:
            return
        try:
            send_sms(lead.phone, _msg_day4(lead.name or ""))
            lead.followup_day4_sent = True
            db.session.commit()
            log.info("Day-4 follow-up sent to %s", lead.phone)
        except Exception:
            log.exception("Failed day-4 follow-up for lead %s", lead_id)


def _send_day7(app, lead_id: int) -> None:
    with app.app_context():
        from models import db, Lead
        from sms import send_sms

        lead = db.session.get(Lead, lead_id)
        if not lead or lead.followup_day7_sent or lead.booked:
            return
        try:
            send_sms(lead.phone, _msg_day7())
            lead.followup_day7_sent = True
            db.session.commit()
            log.info("Day-7 follow-up sent to %s", lead.phone)
        except Exception:
            log.exception("Failed day-7 follow-up for lead %s", lead_id)


# ── public API ────────────────────────────────────────────────────────────────

def init_scheduler(app) -> None:
    global scheduler
    db_url = app.config["SQLALCHEMY_DATABASE_URI"]
    jobstores = {"default": SQLAlchemyJobStore(url=db_url)}
    scheduler = BackgroundScheduler(jobstores=jobstores)
    scheduler.start()
    log.info("APScheduler started")


def enroll_lead(app, lead_id: int, created_at: datetime) -> None:
    """Schedule the Day 2/4/7 follow-up jobs for a new lead."""
    if scheduler is None:
        raise RuntimeError("Scheduler not initialised — call init_scheduler() first")

    base = created_at

    scheduler.add_job(
        _send_day2,
        "date",
        run_date=base + timedelta(hours=24),
        args=[app, lead_id],
        id=f"day2_{lead_id}",
        replace_existing=True,
    )
    scheduler.add_job(
        _send_day4,
        "date",
        run_date=base + timedelta(hours=96),
        args=[app, lead_id],
        id=f"day4_{lead_id}",
        replace_existing=True,
    )
    scheduler.add_job(
        _send_day7,
        "date",
        run_date=base + timedelta(hours=168),
        args=[app, lead_id],
        id=f"day7_{lead_id}",
        replace_existing=True,
    )
    log.info("Enrolled lead %s in 3-step follow-up sequence", lead_id)
