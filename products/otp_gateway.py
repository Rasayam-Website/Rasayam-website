"""
OTP delivery gateway using Zavu API.
"""
import logging
from django.conf import settings
from zavudev import Zavudev

logger = logging.getLogger(__name__)

def send_otp(phone: str, otp: str) -> None:
    """
    Deliver the OTP to the user via Zavu.
    """
    logger.info("Sending OTP for %s via Zavu", phone)
    
    if not settings.ZAVU_API_KEY:
        logger.error("ZAVU_API_KEY is not set. Falling back to console.")
        print(f"[OTP] {phone} -> {otp}")
        return

    try:
        client = Zavudev(api_key=settings.ZAVU_API_KEY)
        client.messages.send(
            to=phone,
            text=f"Your Rasayam verification code is: {otp}. Valid for 10 minutes."
        )
        logger.info("OTP successfully sent to %s via Zavu", phone)
    except Exception as e:
        logger.error("Failed to send OTP to %s via Zavu: %s", phone, e)
        print(f"[OTP FALLBACK] {phone} -> {otp}")
