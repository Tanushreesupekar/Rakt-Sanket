"""SMTP delivery for donor outreach.

The pilot must run without an email provider, so SMTP is optional. When it is
not configured the campaign is still recorded and the API reports the round as
simulated. No new dependency is needed: this uses the standard library.
"""
from __future__ import annotations

import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr

from app import settings


@dataclass(frozen=True)
class OutboundEmail:
    to: str
    subject: str
    body: str


@dataclass
class EmailBatchResult:
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    error: str | None = None
    sent_recipients: list[str] = field(default_factory=list)
    failed_recipients: list[str] = field(default_factory=list)


def email_configured() -> bool:
    return bool(settings.SMTP_ENABLED and settings.SMTP_HOST and settings.SMTP_FROM)


def sender_address() -> str | None:
    return settings.SMTP_FROM if email_configured() else None


def _safe_error(error: BaseException) -> str:
    message = " ".join(str(error).split())
    return f"{type(error).__name__}: {message}"[:300] if message else type(error).__name__


def _open_connection() -> smtplib.SMTP:
    if settings.SMTP_USE_SSL:
        client: smtplib.SMTP = smtplib.SMTP_SSL(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=settings.SMTP_TIMEOUT_SECONDS,
        )
    else:
        client = smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=settings.SMTP_TIMEOUT_SECONDS,
        )
    client.ehlo()
    if settings.SMTP_USE_TLS:
        client.starttls()
        client.ehlo()
    if settings.SMTP_USERNAME:
        client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
    return client


def _message(email: OutboundEmail) -> EmailMessage:
    message = EmailMessage()
    message["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM))
    message["To"] = email.to
    message["Subject"] = email.subject
    message.set_content(email.body)
    return message


def send_emails(emails: list[OutboundEmail]) -> EmailBatchResult:
    """Send a batch over one SMTP connection and report each outcome."""
    result = EmailBatchResult()
    if not emails:
        return result
    if not email_configured():
        result.skipped = len(emails)
        result.error = "SMTP is not configured"
        return result

    try:
        client = _open_connection()
    except (smtplib.SMTPException, OSError, TimeoutError) as error:
        result.failed = len(emails)
        result.failed_recipients = [email.to for email in emails]
        result.error = _safe_error(error)
        return result

    try:
        for email in emails:
            try:
                client.send_message(_message(email))
                result.sent += 1
                result.sent_recipients.append(email.to)
            except (smtplib.SMTPException, OSError, ValueError) as error:
                result.failed += 1
                result.failed_recipients.append(email.to)
                result.error = _safe_error(error)
    finally:
        try:
            client.quit()
        except (smtplib.SMTPException, OSError):
            pass
    return result


def build_campaign_email(
    *,
    to: str,
    donor_name: str,
    blood_group: str,
    district: str,
    stage: int,
    cbsri: float,
) -> OutboundEmail:
    first_name = donor_name.replace(" (demo)", "").split()[0] if donor_name.strip() else "Donor"
    urgency = "Urgent blood donation request" if stage == 1 else "Blood donation request"
    subject = f"[RaktSanket] {urgency}: {blood_group} in {district}"
    body = (
        f"Hello {first_name},\n\n"
        f"RaktSanket has recorded a shortage risk for {blood_group} blood in {district} "
        f"(district CBSRI {cbsri:.1f}/100, outreach tier {stage}). If you are able to donate, "
        "please contact your nearest district blood bank.\n\n"
        "If you have donated recently or are currently unavailable, you can update your "
        "availability in the RaktSanket donor portal.\n\n"
        "You are receiving this email because you registered as a donor and consented to be "
        "contacted about blood donation. This request was prepared for operator-reviewed outreach.\n\n"
        "Thank you,\n"
        "RaktSanket\n"
    )
    return OutboundEmail(to=to, subject=subject, body=body)


def send_test_email(to_address: str) -> tuple[bool, str]:
    """Test SMTP connection and deliver a single diagnostic email."""
    if not email_configured():
        return False, "SMTP is not configured (set SMTP_HOST, SMTP_USERNAME, and SMTP_PASSWORD in backend/.env)"
    test_email = OutboundEmail(
        to=to_address,
        subject="[RaktSanket] SMTP Outreach Test Email",
        body=(
            "Hello,\n\n"
            "This is a test notification from the RaktSanket blood operations platform.\n"
            "Your SMTP configuration is active and working properly!\n\n"
            "When district admins trigger outreach rounds, eligible donors with active logins in "
            "that district will receive shortage activation emails automatically.\n\n"
            "Best regards,\n"
            "RaktSanket Operations Team\n"
        ),
    )
    result = send_emails([test_email])
    if result.sent > 0:
        return True, f"Test email successfully sent to {to_address}"
    return False, result.error or "Failed to deliver test email."

