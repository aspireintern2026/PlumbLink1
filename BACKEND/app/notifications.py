import os
from flask import current_app
from email.message import EmailMessage
import smtplib


def _send_email(to_email: str, subject: str, body: str) -> bool:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "0") or 0)
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    if not smtp_host or not smtp_port:
        current_app.logger.debug("SMTP not configured; skipping email")
        return False

    msg = EmailMessage()
    msg["From"] = smtp_user or f"no-reply@{smtp_host}"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as s:
            if os.getenv("SMTP_STARTTLS", "true").lower() != "false":
                s.starttls()
            if smtp_user and smtp_pass:
                s.login(smtp_user, smtp_pass)
            s.send_message(msg)
        current_app.logger.info("Notification email sent to %s", to_email)
        return True
    except Exception as exc:
        current_app.logger.exception("Failed to send email: %s", exc)
        return False


def _send_sms_via_twilio(to_number: str, body: str) -> bool:
    try:
        from twilio.rest import Client
    except Exception:
        current_app.logger.debug("Twilio client not installed; skipping SMS")
        return False

    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    if not sid or not token or not from_number:
        current_app.logger.debug("Twilio not configured; skipping SMS")
        return False

    try:
        client = Client(sid, token)
        client.messages.create(body=body, from_=from_number, to=to_number)
        current_app.logger.info("SMS sent to %s", to_number)
        return True
    except Exception as exc:
        current_app.logger.exception("Failed to send SMS: %s", exc)
        return False


def notify_plumber_booking_assigned(supabase, plumber_id, booking):
    """Notify plumber (email/SMS) that a booking has been assigned.

    - `supabase` is expected to be the initialized client from
      `app.extensions`.
    - `plumber_id` is the user's id in `app_users` table.
    - `booking` is the booking record/dict.
    """
    if supabase is None:
        current_app.logger.debug(
            "Supabase client missing; cannot notify plumber"
        )
        return False

    try:
        resp = (
            supabase.table("app_users")
            .select("id, name, email, mobile")
            .eq("id", plumber_id)
            .single()
            .execute()
        )
        if hasattr(resp, "error") and resp.error:
            current_app.logger.warning(
                "Failed to fetch plumber %s: %s", plumber_id, resp.error
            )
            return False

        plumber = resp.data
        if not plumber:
            current_app.logger.warning(
                "No plumber record found for id %s", plumber_id
            )
            return False

        name = plumber.get("name") or "Plumber"
        mobile = plumber.get("mobile")
        email = plumber.get("email")

        short_desc = booking.get("issue") or "new booking"
        booking_id = booking.get("id") or "-"
        when = booking.get("preferred_time") or "soon"

        msg = (
            f"Hello {name},\n\n"
            f"A booking (ID: {booking_id}) for {short_desc} has been "
            f"assigned to you. Scheduled: {when}.\n\n"
            f"Please check your jobs list in the app.\n"
        )

        sent = False
        if mobile:
            sent = _send_sms_via_twilio(mobile, msg) or sent
        if email:
            sent = _send_email(
                email, f"New booking assigned (#{booking_id})", msg
            ) or sent

        if not sent:
            current_app.logger.info(
                "No notification channel succeeded for plumber %s; "
                "falling back to log",
                plumber_id,
            )
        return sent

    except Exception as exc:
        current_app.logger.exception("Error notifying plumber: %s", exc)
        return False
