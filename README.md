# Revenue Pro Systems — Missed Call Text-Back & Lead Follow-Up

Automated SMS follow-up system built with Python + Flask + Twilio + APScheduler.

---

## Features

| Feature | Detail |
|---|---|
| Missed call SMS | Fires within seconds of a missed call via Twilio |
| Landing page | `/` — captures name, phone, service needed |
| 7-day follow-up | Day 1 / 2 / 4 / 7 SMS sequence via APScheduler |
| Booking confirmation | Calendly webhook sends an instant confirmation text |
| SQLite storage | All leads + follow-up status persisted locally |

---

## Local Setup

```bash
# 1. Clone and enter the project
cd revenueprosystems

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Open .env and fill in your Twilio + Calendly values

# 5. Run
python app.py
```

The app starts on http://localhost:5000.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TWILIO_ACCOUNT_SID` | Yes | Found in Twilio Console dashboard |
| `TWILIO_AUTH_TOKEN` | Yes | Found in Twilio Console dashboard |
| `TWILIO_PHONE_NUMBER` | Yes | Your Twilio number (E.164: +15550000000) |
| `CALENDLY_LINK` | Yes | Your Calendly booking URL |
| `FORWARD_TO_NUMBER` | No | Your real cell — Twilio forwards calls here before firing the missed-call SMS |
| `SECRET_KEY` | Yes | Random string for Flask sessions |
| `DATABASE_URL` | No | Defaults to SQLite. Set to Postgres URL on Railway/Render |

---

## Twilio Configuration

### 1. Missed-Call Webhook

In the [Twilio Console](https://console.twilio.com) → Phone Numbers → your number:

- **Voice & Fax → A call comes in:**
  - Method: `HTTP POST`
  - URL: `https://your-app-domain.com/webhook/call`

This TwiML response optionally forwards the call to `FORWARD_TO_NUMBER`. When the call isn't answered, Twilio posts to `/webhook/call-status`, which sends the missed-call SMS.

### 2. No Forwarding (simpler)

If you don't want call forwarding, leave `FORWARD_TO_NUMBER` blank. Set the Twilio webhook to hit `/webhook/call-status` directly with **CallStatus** = `no-answer`. You can do this by setting:

- **Voice & Fax → A call comes in:** `https://your-app.com/webhook/call`
- The TwiML at that route will redirect to `/webhook/call-status` automatically.

---

## Calendly Webhook

1. Go to [Calendly Developer Settings](https://calendly.com/integrations/api_webhooks)
2. Create a new webhook subscription:
   - Event: `invitee.created`
   - URL: `https://your-app-domain.com/webhook/booking`
3. Make sure your Calendly event type has a **Phone Number** question so we can match the booking to a lead and send the confirmation SMS.

---

## Deploy to Railway

1. Push this folder to a GitHub repo.
2. Create a new Railway project → **Deploy from GitHub repo**.
3. Add all environment variables in Railway's **Variables** tab.
4. Railway auto-detects the `Procfile` and deploys with gunicorn.
5. Copy the Railway domain (e.g. `https://revenuepro-production.up.railway.app`) and paste it into your Twilio and Calendly webhook URLs.

## Deploy to Render

1. Push to GitHub.
2. New Render **Web Service** → connect repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app --workers 1 --threads 4 --bind 0.0.0.0:$PORT`
5. Add env vars in Render's **Environment** tab.

---

## Folder Structure

```
revenueprosystems/
├── app.py            # Flask app + all routes
├── models.py         # SQLAlchemy Lead model
├── sms.py            # Twilio SMS helper
├── followup.py       # APScheduler follow-up sequence
├── templates/
│   ├── index.html    # Landing page
│   └── thank_you.html
├── static/
│   └── style.css
├── requirements.txt
├── Procfile
├── .env.example
└── README.md
```

---

## Follow-Up Sequence

| Trigger | Message |
|---|---|
| Day 1 (immediate) | Missed-call SMS or landing page confirmation with Calendly link |
| Day 2 (24 h later) | "Did you get a chance to book?" |
| Day 4 (96 h later) | "Still here if you need us. Here's our booking link." |
| Day 7 (168 h later) | "Last follow-up from us — whenever you're ready, we're here." |

Leads who book via Calendly have their sequence halted automatically (`booked = True`).
