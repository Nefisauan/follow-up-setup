from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Lead(db.Model):
    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    phone = db.Column(db.String(20), nullable=False, unique=True)
    service = db.Column(db.String(200))
    source = db.Column(db.String(50))  # 'missed_call' | 'landing_page'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Follow-up tracking (day index: 1, 2, 4, 7)
    followup_day1_sent = db.Column(db.Boolean, default=False)
    followup_day2_sent = db.Column(db.Boolean, default=False)
    followup_day4_sent = db.Column(db.Boolean, default=False)
    followup_day7_sent = db.Column(db.Boolean, default=False)
    booked = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Lead {self.phone}>"
