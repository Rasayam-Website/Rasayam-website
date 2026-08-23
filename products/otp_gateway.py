"""
OTP delivery gateway — Zavu SMS integration.

Sends OTP codes via the Zavu messaging API (https://api.zavu.dev/v1/messages).
Falls back to console logging when ZAVU_API_KEY is not configured (local dev).

Configuration (set in .env or environment):
    ZAVU_API_KEY     – Bearer token for the Zavu API
    ZAVU_SENDER_ID   – Sender header value (defaults to the Rasayam sender ID)
    ZAVU_API_URL     – API endpoint (defaults to https://api.zavu.dev/v1/messages)
"""

import logging
import os

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Zavu configuration ───────────────────────────────────────────────────────
ZAVU_API_URL = os.getenv("ZAVU_API_URL", "https://api.zavu.dev/v1/messages")
ZAVU_API_KEY = os.getenv("ZAVU_API_KEY", "")
ZAVU_SENDER_ID = os.getenv("ZAVU_SENDER_ID", "kd76wwx3z18f1scm0bz6t8332s8c4dp9")

# Channel as specified by the integration requirements
ZAVU_CHANNEL = "sms"

# HTTP timeout in seconds — fail fast so the auth view doesn't hang
ZAVU_TIMEOUT = 10


def _send_via_zavu(phone: str, message: str) -> bool:
    """
    Send an SMS through the Zavu API.

    Returns True on success, False on any failure (network, auth, server error).
    Never raises — the caller decides how to handle failure.
    """
    headers = {
        "Authorization": f"Bearer {ZAVU_API_KEY}",
        "Content-Type": "application/json",
        "Zavu-Sender": ZAVU_SENDER_ID,
    }

    payload = {
        "to": phone,
        "text": message,
        "channel": ZAVU_CHANNEL,
    }

    try:
        response = requests.post(
            ZAVU_API_URL,
            json=payload,
            headers=headers,
            timeout=ZAVU_TIMEOUT,
        )

        if response.ok:
            data = response.json()
            msg_id = data.get("message", {}).get("id", "unknown")
            logger.info(
                "Zavu SMS sent successfully to %s (message_id=%s)", phone, msg_id
            )
            return True

        # Non-2xx response — log the details for debugging
        logger.error(
            "Zavu API error: HTTP %d — %s (phone=%s)",
            response.status_code,
            response.text[:500],
            phone,
        )
        return False

    except requests.exceptions.Timeout:
        logger.error("Zavu API timeout after %ds (phone=%s)", ZAVU_TIMEOUT, phone)
        return False

    except requests.exceptions.ConnectionError:
        logger.error("Zavu API connection failed (phone=%s)", phone)
        return False

    except requests.exceptions.RequestException as exc:
        logger.error("Zavu API unexpected error: %s (phone=%s)", exc, phone)
        return False


def send_otp(phone: str, otp: str) -> None:
    """
    Deliver a 6-digit OTP to the user via SMS.

    Production: sends via Zavu SMS gateway.
    Development (no API key): falls back to console logging so local
    testing works without external dependencies.
    """
    # ── Normalize to E.164 format (+91XXXXXXXXXX) ────────────────────────────
    # Users may enter numbers as "9876543210", "09876543210", "919876543210",
    # or "+919876543210". The Zavu API requires strict E.164 with the "+" prefix.
    phone = phone.strip().replace(" ", "").replace("-", "")
    if not phone.startswith("+"):
        # Remove leading 0 (domestic format)
        phone = phone.lstrip("0")
        # If it already starts with country code 91 and is 12 digits, just add +
        if phone.startswith("91") and len(phone) == 12:
            phone = f"+{phone}"
        else:
            # Default to India (+91) for 10-digit numbers
            phone = f"+91{phone}"

    message = f"Your verification code is {otp}. It expires in 5 minutes."

    # ── Guard: skip API call if no key is configured ─────────────────────────
    if not ZAVU_API_KEY:
        logger.warning(
            "ZAVU_API_KEY not set — OTP for %s printed to console only.", phone
        )
        print(f"[OTP] {phone} -> {otp}")
        return

    # ── Send via Zavu ────────────────────────────────────────────────────────
    success = _send_via_zavu(phone, message)

    if not success:
        # In DEBUG mode, allow the flow to continue so devs aren't blocked.
        # In production, log a critical alert — the OTP was generated but the
        # user never received it. Monitoring should catch this.
        if getattr(settings, "DEBUG", False):
            logger.warning(
                "Zavu delivery failed (DEBUG=True, continuing). OTP for %s: %s",
                phone,
                otp,
            )
            print(f"[OTP FALLBACK] {phone} -> {otp}")
        else:
            logger.critical(
                "Zavu SMS delivery FAILED in production for %s. "
                "User will not receive OTP. Investigate immediately.",
                phone,
            )
