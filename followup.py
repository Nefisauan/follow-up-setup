import os
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)

scheduler: BackgroundScheduler | None = None
_flask_app = None


def _calendly() -> str:
    return os.environ.get("CALENDLY_LINK", "https://calendly.com/your-link")


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
    return f"Last follow-up from us — whenever you're ready, we're here. {_calendly()}"


def _send_followup(lead_id: int, day: int) -> None:
    with _flask_app.app_context():
        from models import db, Lead
        from sms import send_sms

        lead = db.session.get(Lead, lead_id)
        if not lead or lead.booked:
            return

        sent_attr = f"followup_day{day}_sent"
        if getattr(lead, sent_attr):
            return

        if day == 2:
            msg = _msg_day2(lead.name or "")
        elif day == 4:
            msg = _msg_day4(lead.name or "")
        else:
            msg = _msg_day7()

        try:
            send_sms(lead.phone, msg)
            setattr(lead, sent_attr, True)
            db.session.commit()
            log.info("Day-%s follow-up sent to %s", day, lead.phone)
        except Exception:
            log.exception("Failed day-%s follow-up for lead %s", day, lead_id)


def init_scheduler(app) -> None:
    global scheduler, _flask_app
    _flask_app = app
    scheduler = BackgroundScheduler()
    scheduler.start()
    log.info("APScheduler started")


def enroll_lead(app, lead_id: int, created_at: datetime) -> None:
    if scheduler is None:
        raise RuntimeError("Scheduler not initialised")

    base = created_at
    for day, hours in [(2, 24), (4, 96), (7, 168)]:
        scheduler.add_job(
            _send_followup,
            "date",
            run_date=base + timedelta(hours=hours),
            args=[lead_id, day],
            id=f"day{day}_{lead_id}",
            replace_existing=True,
        )
    log.info("Enrolled lead %s in follow-up sequence", lead_id)
