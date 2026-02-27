import os
import random
import string
from datetime import datetime, timedelta

import telnyx

# Configure Telnyx with your API key
telnyx.api_key = os.getenv("TELNYX_API_KEY")
TELNYX_PHONE = os.getenv("TELNYX_PHONE_NUMBER")
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
        telnyx.Message.create(
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
