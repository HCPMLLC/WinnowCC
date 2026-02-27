import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, validator

from app.services.sms_service import send_otp, verify_otp

router = APIRouter(prefix="/api/sms", tags=["SMS OTP"])


class SendOTPRequest(BaseModel):
    phone_number: str

    @validator("phone_number")
    def validate_phone(cls, v):
        # Must be in E.164 format: +1 followed by 10 digits (US numbers)
        if not re.match(r"^\+1\d{10}$", v):
            raise ValueError("Phone must be in format +12105551234")
        return v


class VerifyOTPRequest(BaseModel):
    phone_number: str
    code: str


@router.post("/send-otp")
async def send_otp_endpoint(request: SendOTPRequest):
    """
    Send a 6-digit OTP verification code via SMS to the provided phone number.
    Rate limiting should be added before production use.
    """
    success = send_otp(request.phone_number)
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to send SMS. Please check your phone number and try again.",
        )
    return {"message": "Verification code sent successfully."}


@router.post("/verify-otp")
async def verify_otp_endpoint(request: VerifyOTPRequest):
    """
    Verify the 6-digit OTP code submitted by the user.
    Returns verified: true if correct and not expired.
    """
    is_valid = verify_otp(request.phone_number, request.code)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code. Please request a new code.",
        )
    return {"message": "Phone number verified successfully!", "verified": True}
