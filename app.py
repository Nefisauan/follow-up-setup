import os
import logging
from datetime import datetime

from flask import Flask, request, jsonify, render_template, redirect, url_for
from dotenv import load_dotenv
from twilio.twiml.voice_response import VoiceResponse

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///leads.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

from models import db, Lead  # noqa: E402  (after app is created)

db.init_app(app)

from followup import init_scheduler, enroll_lead  # noqa: E402


# ── helpers ───────────────────────────────────────────────────────────────────

def _calendly() -> str:
    return os.environ.get("CALENDLY_LINK", "https://calendly.com/your-link")


def _missed_call_msg() -> str:
    return (
        "Hey, sorry we missed your call! "
        f"Click here to book a time with us: {_calendly()} "
        "We'll also follow up with you shortly."
    )


def _booking_confirmation_msg(name: str) -> str:
    first = name.split()[0] if name else "there"
    return f"Hi {first}! Your appointment is confirmed. We look forward to seeing you!"


def _get_or_create_lead(phone: str, name: str = "", service: str = "", source: str = "missed_call") -> Lead:
    phone = _normalise_phone(phone)
    lead = Lead.query.filter_by(phone=phone).first()
    if lead is None:
        lead = Lead(phone=phone, name=name, service=service, source=source)
        db.session.add(lead)
        db.session.commit()
        enroll_lead(app, lead.id, lead.created_at)
    return lead


def _normalise_phone(phone: str) -> str:
    """Keep only digits and leading +, ensure E.164-ish format."""
    digits = "".join(c for c in phone if c.isdigit() or c == "+")
    if not digits.startswith("+"):
        digits = "+1" + digits.lstrip("1")
    return digits


# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", calendly_link=_calendly())


@app.route("/submit-lead", methods=["POST"])
def submit_lead():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    service = request.form.get("service", "").strip()

    if not phone:
        return "Phone number is required.", 400

    from sms import send_sms

    lead = _get_or_create_lead(phone, name=name, service=service, source="landing_page")

    if not lead.followup_day1_sent:
        try:
            send_sms(
                phone,
                f"Hey {name.split()[0] if name else 'there'}! Thanks for reaching out. "
                f"Book a time here: {_calendly()} — we'll be in touch soon!",
            )
            lead.followup_day1_sent = True
            db.session.commit()
        except Exception:
            log.exception("Failed to send day-1 SMS to %s", phone)

    return render_template("thank_you.html", name=name)


# ── Twilio webhooks ───────────────────────────────────────────────────────────

@app.route("/webhook/call", methods=["POST"])
def webhook_call():
    """
    Twilio hits this URL for every inbound call.
    TwiML response: ring the owner; on no-answer, send the missed-call SMS.
    Configure your Twilio number's Voice webhook to POST here.
    """
    caller = request.form.get("From", "")
    call_status = request.form.get("CallStatus", "")

    log.info("Inbound call from %s — status: %s", caller, call_status)

    twiml = VoiceResponse()

    # Forward to your real number; adjust or remove as needed.
    forward_to = os.environ.get("FORWARD_TO_NUMBER", "")
    if forward_to:
        dial = twiml.dial(action="/webhook/call-status", timeout="20")
        dial.number(forward_to)
    else:
        # No forwarding — just play a message and hang up, triggering fallback.
        twiml.say("Please hold while we connect you.")
        twiml.hangup()

    return str(twiml), 200, {"Content-Type": "text/xml"}


@app.route("/webhook/call-status", methods=["POST"])
def webhook_call_status():
    """
    Twilio posts here after the <Dial> action completes.
    DialCallStatus == 'no-answer' | 'busy' | 'failed' means missed call.
    """
    caller = request.form.get("From", "")
    dial_status = request.form.get("DialCallStatus", "")

    log.info("Call status for %s: %s", caller, dial_status)

    if dial_status in ("no-answer", "busy", "failed", "canceled") and caller:
        from sms import send_sms

        lead = _get_or_create_lead(caller, source="missed_call")
        if not lead.followup_day1_sent:
            try:
                send_sms(caller, _missed_call_msg())
                lead.followup_day1_sent = True
                db.session.commit()
                log.info("Missed-call SMS sent to %s", caller)
            except Exception:
                log.exception("Failed to send missed-call SMS to %s", caller)

    twiml = VoiceResponse()
    return str(twiml), 200, {"Content-Type": "text/xml"}


@app.route("/webhook/booking", methods=["POST"])
def webhook_booking():
    """
    Calendly webhook — fires on invitee.created events.
    Set this URL in your Calendly webhook configuration.
    """
    data = request.get_json(silent=True) or {}
    event = data.get("event", "")

    if event != "invitee.created":
        return jsonify({"status": "ignored"}), 200

    payload = data.get("payload", {})
    invitee = payload.get("invitee", {})
    name = invitee.get("name", "")
    phone_raw = ""

    # Calendly puts custom questions in questions_and_answers
    for qa in payload.get("questions_and_answers", []):
        if "phone" in qa.get("question", "").lower():
            phone_raw = qa.get("answer", "")
            break

    if phone_raw:
        phone = _normalise_phone(phone_raw)
        from sms import send_sms

        lead = Lead.query.filter_by(phone=phone).first()
        if lead:
            lead.booked = True
            db.session.commit()

        try:
            send_sms(phone, _booking_confirmation_msg(name))
            log.info("Booking confirmation sent to %s", phone)
        except Exception:
            log.exception("Failed to send booking confirmation to %s", phone)

    return jsonify({"status": "ok"}), 200


# ── startup ───────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()

init_scheduler(app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
