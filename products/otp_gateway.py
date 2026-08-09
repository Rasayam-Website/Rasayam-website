"""
OTP delivery gateway using Zavu API.
"""
import logging
from django.conf import settings
from zavudev import Zavudev

logger = logging.getLogger(__name__)

def send_otp(phone: str, otp: str) -> bool:
    """
    Deliver the OTP to the user via Zavu.
    Returns True if sent successfully, False otherwise.
    """
    # Normalize phone to E.164 (assume +91 for 10-digit India numbers)
    phone = phone.strip()
    if len(phone) == 10 and phone.isdigit():
        phone = f"+91{phone}"
    elif not phone.startswith('+'):
        phone = f"+{phone}"

    logger.info("Sending OTP for %s via Zavu", phone)

    if settings.DEBUG:
        logger.info("DEBUG mode enabled. Skipping real SMS.")
        print(f"[OTP - DEBUG] {phone} -> {otp}")
        return True
    
    if not settings.ZAVUDEV_API_KEY:
        logger.error("ZAVUDEV_API_KEY is not set. Failing OTP send.")
        return False

    try:
        client = Zavudev(api_key=settings.ZAVUDEV_API_KEY)
        client.messages.send(
            to=phone,
            text=f"Your Rasayam verification code is: {otp}. Valid for 10 minutes."
        )
        logger.info("OTP successfully sent to %s via Zavu", phone)
        return True
    except Exception as e:
        logger.error("Failed to send OTP to %s via Zavu: %s", phone, e)
        return False
