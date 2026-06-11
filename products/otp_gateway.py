"""
OTP delivery gateway stub.

Swap out `send_otp` for a real SMS/email provider when ready.
Twilio example:
    from twilio.rest import Client
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(
        body=f"Your Rasayam code: {otp}",
        from_=settings.TWILIO_FROM_NUMBER,
        to=phone,
    )
"""
import logging

logger = logging.getLogger(__name__)


def send_otp(phone: str, otp: str) -> None:
    """
    Deliver the OTP to the user.
    Currently logs to console; replace the body with your SMS/email provider.
    """
    # ── REPLACE THIS BLOCK WITH YOUR GATEWAY ─────────────────────────────────
    logger.info("OTP for %s: %s", phone, otp)
    print(f"[OTP] {phone} → {otp}")
    # ─────────────────────────────────────────────────────────────────────────
