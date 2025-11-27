from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# SQLAlchemy instance (initialized in app)
db = SQLAlchemy()


class Expert(db.Model):
    __tablename__ = "expert"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    specialty = db.Column(db.String(120))
    email = db.Column(db.String(120), nullable=False)
    meeting_provider = db.Column(db.String(20), default="zoom")  # "zoom" | "google"


class Availability(db.Model):
    __tablename__ = "availability"
    id = db.Column(db.Integer, primary_key=True)
    expert_id = db.Column(db.Integer, db.ForeignKey("expert.id"), nullable=False)
    start_utc = db.Column(db.DateTime, nullable=False)
    end_utc = db.Column(db.DateTime, nullable=False)
    is_booked = db.Column(db.Boolean, default=False, nullable=False)


class Booking(db.Model):
    __tablename__ = "booking"
    id = db.Column(db.Integer, primary_key=True)
    expert_id = db.Column(db.Integer, db.ForeignKey("expert.id"), nullable=False)
    farmer_name = db.Column(db.String(120), nullable=False)
    farmer_email = db.Column(db.String(120), nullable=False)
    slot_start_utc = db.Column(db.DateTime, nullable=False)
    slot_end_utc = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)  # pending, paid, confirmed, cancelled
    razorpay_order_id = db.Column(db.String(100))
    razorpay_payment_id = db.Column(db.String(100))
    meeting_link = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    commission_code = db.Column(db.String(64))


class QRScan(db.Model):
    __tablename__ = "qr_scan"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    result = db.Column(db.String(20), nullable=False)  # genuine | warning
    farmer_name = db.Column(db.String(120))
    farmer_email = db.Column(db.String(120))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
