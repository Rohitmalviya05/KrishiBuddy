import os
from datetime import datetime, timedelta, timezone
from backend.models import db, Booking, Expert


def send_email(to_email: str, subject: str, body_html: str):
    # TODO: integrate SendGrid/SMTP. This is a stub.
    print(f"[EMAIL] To: {to_email} | Subject: {subject}")


def enqueue_confirm_email(booking_id: int):
    booking = Booking.query.get(booking_id)
    expert = Expert.query.get(booking.expert_id)
    if not booking or not expert:
        return
    send_email(
        booking.farmer_email,
        "Consultation booked",
        f"Your booking with {expert.name} is confirmed for {booking.slot_start_utc} UTC.",
    )
    send_email(
        expert.email,
        "New consultation booked",
        f"You have a new booking with {booking.farmer_name} at {booking.slot_start_utc} UTC.",
    )


def schedule_meeting_job(booking_id: int):
    # TODO: integrate APScheduler or your task queue
    print(f"[SCHEDULE] Meeting link generation scheduled for booking {booking_id}")


def create_and_send_meeting_link(booking_id: int):
    booking = Booking.query.get(booking_id)
    expert = Expert.query.get(booking.expert_id)
    if not booking or not expert:
        return
    link = create_zoom_meeting(expert, booking) if expert.meeting_provider == "zoom" else create_google_meet(expert, booking)
    booking.meeting_link = link
    booking.status = "confirmed"
    db.session.commit()
    send_email(booking.farmer_email, "Meeting link", f"Join link: {link}")
    send_email(expert.email, "Meeting link", f"Join link: {link}")


def create_zoom_meeting(expert: Expert, booking: Booking) -> str:
    # TODO: integrate Zoom Server-to-Server OAuth and create a meeting
    return "https://zoom.us/j/placeholder"


def create_google_meet(expert: Expert, booking: Booking) -> str:
    # TODO: integrate Google Calendar API to create Meet link
    return "https://meet.google.com/placeholder"
