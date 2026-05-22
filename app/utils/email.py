"""
Email utility — sends transactional emails.
Uses SMTP (configurable). In development, logs the email to console instead.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html_body: str) -> None:
    """Send an email. Falls back to console log if SMTP not configured."""
    if not settings.SMTP_HOST:
        # Dev mode — just log it
        logger.info(f"\n{'='*60}\nEMAIL TO: {to}\nSUBJECT: {subject}\nBODY:\n{html_body}\n{'='*60}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, to, msg.as_string())
        logger.info(f"Email sent to {to}: {subject}")
    except Exception:
        logger.exception(f"Failed to send email to {to}")
        raise


def send_verification_email(to: str, full_name: str, token: str) -> None:
    name = full_name or "there"
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    send_email(
        to=to,
        subject="Verify your TalkFiesta account",
        html_body=f"""
        <h2>Hi {name}!</h2>
        <p>Welcome to TalkFiesta. Please verify your email address:</p>
        <p><a href="{link}" style="background:#4F46E5;color:white;padding:12px 24px;
           border-radius:8px;text-decoration:none;">Verify Email</a></p>
        <p>This link expires in <strong>24 hours</strong>.</p>
        <p>If you didn't create an account, ignore this email.</p>
        """,
    )


def send_password_reset_email(to: str, full_name: str, token: str) -> None:
    name = full_name or "there"
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    send_email(
        to=to,
        subject="Reset your TalkFiesta password",
        html_body=f"""
        <h2>Hi {name}!</h2>
        <p>We received a request to reset your password.</p>
        <p><a href="{link}" style="background:#4F46E5;color:white;padding:12px 24px;
           border-radius:8px;text-decoration:none;">Reset Password</a></p>
        <p>This link expires in <strong>1 hour</strong>.</p>
        <p>If you didn't request this, ignore this email — your password won't change.</p>
        """,
    )
