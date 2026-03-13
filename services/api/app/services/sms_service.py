import logging
import os
import random
import string
from datetime import datetime, timedelta

from telnyx import Telnyx

logger = logging.getLogger(__name__)

# Configure Telnyx client
_client = Telnyx(api_key=os.getenv("TELNYX_API_KEY"))
TELNYX_PHONE = (
    os.getenv("TELNYX_FROM_NUMBER", "").strip()
    or os.getenv("TELNYX_PHONE_NUMBER", "").strip()
    or None
)
OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", "10"))

# In-memory OTP store: { phone_number: { "code": "123456", "expires_at": datetime } }
# Note: For production, use Redis instead. This works fine for now.
_otp_store: dict = {}


def generate_otp() -> str:
    """Generate a random 6-digit code."""
    return "".join(random.choices(string.digits, k=6))


def send_otp(phone_number: str) -> bool:
    """
    Send an OTP code to the given phone number.
    Returns True if successful, False if failed.
    Phone number must be in format: +12105551234
    """
    code = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)

    # Store the code
    _otp_store[phone_number] = {"code": code, "expires_at": expires_at}

    try:
        _client.messages.send(
            from_=TELNYX_PHONE,
            to=phone_number,
            text=(
                f"Your Winnow verification code is: {code}. "
                f"It expires in {OTP_EXPIRY_MINUTES} minutes. "
                f"Do not share this code with anyone."
            ),
        )
        return True
    except Exception as e:
        print(f"[SMS ERROR] Failed to send OTP to {phone_number}: {e}")
        return False


def verify_otp(phone_number: str, code: str) -> bool:
    """
    Check if the code matches what we sent and hasn't expired.
    Returns True if valid, False if wrong or expired.
    """
    record = _otp_store.get(phone_number)

    if not record:
        return False  # Never sent a code to this number

    if datetime.utcnow() > record["expires_at"]:
        del _otp_store[phone_number]  # Clean up expired code
        return False  # Code expired

    if record["code"] != code:
        return False  # Wrong code

    # Code is correct! Clean it up so it can't be reused.
    del _otp_store[phone_number]
    return True


# ---------------------------------------------------------------------------
# Generic SMS send + 10DLC auto-response helpers
# ---------------------------------------------------------------------------


def send_sms(phone_number: str, message: str) -> bool:
    """Send an SMS message via Telnyx. Returns True on success."""
    if not TELNYX_PHONE:
        logger.error("TELNYX_FROM_NUMBER not set; skipping SMS to %s", phone_number)
        return False
    try:
        _client.messages.send(from_=TELNYX_PHONE, to=phone_number, text=message)
        return True
    except Exception as e:
        logger.error("Failed to send SMS to %s: %s", phone_number, e)
        return False


def send_opt_in_confirmation(phone_number: str) -> bool:
    """10DLC-required opt-in confirmation auto-response."""
    return send_sms(
        phone_number,
        "Winnow: Thanks for subscribing to job match alerts and application "
        "updates! Reply HELP for help. Message frequency may vary. Msg&data "
        "rates may apply. Consent is not a condition of purchase. Reply STOP "
        "to opt out.",
    )


def send_stop_confirmation(phone_number: str) -> bool:
    """10DLC-required STOP auto-response."""
    return send_sms(
        phone_number,
        "Winnow Job Alerts: You have been unsubscribed and will receive no "
        "further messages. Reply HELP for help.",
    )


def send_help_response(phone_number: str) -> bool:
    """10DLC-required HELP auto-response."""
    return send_sms(
        phone_number,
        "Winnow Job Alerts: For help, please reach out to us at "
        "support@winnowcc.ai. Reply STOP to opt out.",
    )
