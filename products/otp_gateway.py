"""
OTP delivery gateway.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_otp(email: str, otp: str) -> bool:
    """
    Deliver the OTP to the user via Email.
    Returns True if sent successfully, False otherwise.
    """
    logger.info("Sending OTP for %s via Email", email)

    subject = "Your Rasayam Verification Code"
    message = f"Your Rasayam verification code is: {otp}\n\nThis code is valid for 5 minutes."
    from_email = settings.DEFAULT_FROM_EMAIL

    if settings.DEBUG:
        logger.info("DEBUG mode enabled. Printing OTP to console but STILL attempting send_mail if configured.")
        print(f"[OTP - EMAIL DEBUG] {email} -> {otp}")

    try:
        send_mail(
            subject,
            message,
            from_email,
            [email],
            fail_silently=False,
        )
        logger.info("OTP successfully sent to %s via Email", email)
        return True
    except Exception as e:
        logger.error("Failed to send OTP to %s via Email: %s", email, e)
        # If in debug mode and email fails (e.g. no SMTP setup yet), just return True so flow works.
        if settings.DEBUG:
            return True
        return False
