# PROMPT 60 — Telnyx SMS OTP: API Endpoints, Route Registration, and Testing

Read SPEC.md, ARCHITECTURE.md, and CLAUDE.md before making any changes.

## Purpose

Wire up the Telnyx SMS OTP system into the Winnow backend. This prompt assumes the following have already been completed manually:

- ✅ Telnyx account created at telnyx.com
- ✅ Phone number purchased in Telnyx portal
- ✅ Telnyx API key copied and saved
- ✅ `services/api/.env` updated with `TELNYX_API_KEY`, `TELNYX_PHONE_NUMBER`, and `OTP_EXPIRY_MINUTES`
- ✅ Telnyx library installed via `pip install telnyx --break-system-packages`
- ✅ `services/api/app/services/sms_service.py` created with `send_otp()` and `verify_otp()` functions

This prompt completes the remaining three steps: creating the API router, registering it with FastAPI, and verifying everything works end-to-end.

---

## Prerequisites

- ✅ FastAPI backend running at `services/api/`
- ✅ `services/api/app/services/sms_service.py` exists with `send_otp` and `verify_otp` functions
- ✅ `.env` file contains `TELNYX_API_KEY` and `TELNYX_PHONE_NUMBER`
- ✅ Existing `services/api/app/main.py` with `app.include_router(...)` pattern

---

## Step 1: Create the SMS OTP Router File

**What this does:** Creates the two API "buttons" that users will press — one to request a code, one to submit a code.

**File to create:**
```
services/api/app/routers/sms_otp.py
```

**How to create it in Cursor:**
1. In the left sidebar, navigate to `services/api/app/routers/`
2. Right-click the `routers` folder → click **"New File"**
3. Name it exactly: `sms_otp.py`
4. Paste the following code in its entirety — do not change anything:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, validator
import re
from app.services.sms_service import send_otp, verify_otp

router = APIRouter(prefix="/api/sms", tags=["SMS OTP"])


class SendOTPRequest(BaseModel):
    phone_number: str

    @validator("phone_number")
    def validate_phone(cls, v):
        # Must be in E.164 format: +1 followed by 10 digits (US numbers)
        if not re.match(r'^\+1\d{10}$', v):
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
            detail="Failed to send SMS. Please check your phone number and try again."
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
            detail="Invalid or expired verification code. Please request a new code."
        )
    return {"message": "Phone number verified successfully!", "verified": True}
```

5. Press **Ctrl+S** to save.

---

## Step 2: Register the Router in main.py

**What this does:** Tells the FastAPI application that the SMS OTP router exists. Without this step, the endpoints won't be reachable.

**File to edit:**
```
services/api/app/main.py
```

**How to do it in Cursor:**

1. In the left sidebar, click on `services/api/app/main.py` to open it.

2. **Find the imports section** — look near the top of the file for a group of lines that look like:
   ```python
   from app.routers import auth
   from app.routers import jobs
   # ... other routers ...
   ```

3. **Add this line** in that same group (exact position within the group doesn't matter):
   ```python
   from app.routers import sms_otp
   ```

4. **Scroll down** a bit until you find a group of lines that look like:
   ```python
   app.include_router(auth.router)
   app.include_router(jobs.router)
   # ... other include_router calls ...
   ```

5. **Add this line** in that same group:
   ```python
   app.include_router(sms_otp.router)
   ```

6. Press **Ctrl+S** to save.

---

## Step 3: Verify the sms_service.py File Exists and Is Correct

Before testing, confirm the service file from the manual setup step is complete.

**File to check:**
```
services/api/app/services/sms_service.py
```

Open it and confirm it contains these three functions:
- `generate_otp()` — creates a 6-digit code
- `send_otp(phone_number)` — sends the code via Telnyx
- `verify_otp(phone_number, code)` — checks if the code is valid

If the file does NOT exist or is empty, create it now with this full content:

```python
import os
import random
import string
from datetime import datetime, timedelta
import telnyx

# Configure Telnyx with your API key from .env
telnyx.api_key = os.getenv("TELNYX_API_KEY")
TELNYX_PHONE = os.getenv("TELNYX_PHONE_NUMBER")
OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", "10"))

# In-memory OTP store: { phone_number: { "code": "123456", "expires_at": datetime } }
# Note: For production with multiple server instances, replace with Redis.
_otp_store: dict = {}


def generate_otp() -> str:
    """Generate a random 6-digit numeric code."""
    return ''.join(random.choices(string.digits, k=6))


def send_otp(phone_number: str) -> bool:
    """
    Generate and send an OTP code to the given phone number via Telnyx SMS.
    Phone number must be in E.164 format: +12105551234
    Returns True if the SMS was sent successfully, False if it failed.
    """
    code = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)

    # Store the code before sending (in case Telnyx is slow)
    _otp_store[phone_number] = {
        "code": code,
        "expires_at": expires_at
    }

    try:
        telnyx.Message.create(
            from_=TELNYX_PHONE,
            to=phone_number,
            text=(
                f"Your Winnow verification code is: {code}. "
                f"It expires in {OTP_EXPIRY_MINUTES} minutes. "
                f"Do not share this code with anyone."
            )
        )
        return True
    except Exception as e:
        print(f"[SMS ERROR] Failed to send OTP to {phone_number}: {e}")
        # Clean up the stored code if sending failed
        _otp_store.pop(phone_number, None)
        return False


def verify_otp(phone_number: str, code: str) -> bool:
    """
    Verify that the submitted code matches what was sent and has not expired.
    Returns True if valid, False if wrong or expired.
    Deletes the code after a successful verification (one-time use).
    """
    record = _otp_store.get(phone_number)

    if not record:
        return False  # No code was ever sent to this number

    if datetime.utcnow() > record["expires_at"]:
        del _otp_store[phone_number]  # Clean up expired entry
        return False  # Code has expired

    if record["code"] != code:
        return False  # Wrong code entered

    # Code is correct — delete it so it cannot be reused
    del _otp_store[phone_number]
    return True
```

Press **Ctrl+S** to save.

---

## Step 4: Start the Backend and Verify No Errors

**Where to do this:** In the Cursor Terminal (the black panel at the bottom). To open it: click **Terminal** in the top menu → **New Terminal**.

**Run these commands one at a time**, pressing Enter after each:

```bash
cd services/api
```

```bash
uvicorn app.main:app --reload --port 8000
```

**What to look for:** The terminal should show something like:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**If you see any red error text**, stop here and read the error carefully. Common issues:
- `ModuleNotFoundError: No module named 'telnyx'` → Run `pip install telnyx --break-system-packages` then try again
- `ImportError: cannot import name 'send_otp'` → The `sms_service.py` file is missing or has a typo — re-check Step 3
- `KeyError: TELNYX_API_KEY` → The `.env` file is missing the key — re-check your `.env` file

---

## Step 5: Test Using the Swagger UI (Interactive Docs)

**Where to do this:** In your web browser.

**Step 5.1** — Open your browser and go to:
```
http://localhost:8000/docs
```

You will see a page with a list of all API endpoints. This is called Swagger UI — think of it as a control panel for your API.

**Step 5.2** — Scroll down until you see a section labeled **"SMS OTP"**. You should see two entries:
- `POST /api/sms/send-otp`
- `POST /api/sms/verify-otp`

If you do NOT see this section, go back and re-check that you added both lines in Step 2 (the import and the include_router).

**Step 5.3 — Test Send OTP:**

1. Click on `POST /api/sms/send-otp` to expand it
2. Click the **"Try it out"** button (top right of that section)
3. In the box that appears, replace the example text with your own phone number:
   ```json
   {
     "phone_number": "+12105551234"
   }
   ```
   *(Use your actual phone number in +1XXXXXXXXXX format)*
4. Click the blue **"Execute"** button
5. Scroll down — you should see `"message": "Verification code sent successfully."`
6. **Check your phone** — you should receive a text message from your Telnyx number within 30 seconds

**Step 5.4 — Test Verify OTP:**

1. Click on `POST /api/sms/verify-otp` to expand it
2. Click **"Try it out"**
3. Enter your phone number and the 6-digit code you received:
   ```json
   {
     "phone_number": "+12105551234",
     "code": "123456"
   }
   ```
4. Click **"Execute"**
5. You should see: `"verified": true`

**Step 5.5 — Test Expired/Wrong Code:**

1. Try submitting the same code again (it should already be deleted after successful use)
2. You should see a `400` error: `"Invalid or expired verification code"`
3. This confirms the one-time-use behavior is working correctly ✅

---

## Step 6: Test Edge Cases

Still in Swagger UI — test these scenarios to make sure error handling works:

**Test 1 — Wrong phone format:**
Send to `POST /api/sms/send-otp` with:
```json
{ "phone_number": "2105551234" }
```
Expected result: `422 Unprocessable Entity` — "Phone must be in format +12105551234"

**Test 2 — Wrong code:**
1. Send a real OTP to your phone
2. Submit `/verify-otp` with the correct phone number but code `"000000"`
3. Expected result: `400` error — "Invalid or expired verification code"

**Test 3 — Nonexistent phone number:**
Submit `/verify-otp` with a phone number you never sent a code to:
```json
{ "phone_number": "+19999999999", "code": "123456" }
```
Expected result: `400` error ✅

---

## Step 7: Lint and Format the New Files

**In the Cursor Terminal:**

```bash
cd services/api
python -m ruff check app/routers/sms_otp.py
python -m ruff check app/services/sms_service.py
python -m ruff format app/routers/sms_otp.py
python -m ruff format app/services/sms_service.py
```

If ruff is not installed:
```bash
pip install ruff --break-system-packages
```

Fix any errors ruff reports before continuing.

---

## Summary Checklist

Before marking this prompt complete, verify each item:

- [ ] `services/api/app/services/sms_service.py` exists with `generate_otp`, `send_otp`, and `verify_otp` functions
- [ ] `services/api/app/routers/sms_otp.py` created with `POST /api/sms/send-otp` and `POST /api/sms/verify-otp`
- [ ] `services/api/app/main.py` updated with both the import and `app.include_router(sms_otp.router)`
- [ ] Backend starts with no errors (`uvicorn app.main:app --reload --port 8000`)
- [ ] Swagger UI at `http://localhost:8000/docs` shows the **"SMS OTP"** section
- [ ] `POST /api/sms/send-otp` successfully sends a real text message to your phone
- [ ] `POST /api/sms/verify-otp` returns `"verified": true` with the correct code
- [ ] Submitting a wrong or expired code returns a `400` error
- [ ] Submitting a phone number in wrong format returns a `422` error
- [ ] Files pass ruff lint check

---

## Files Created or Modified in This Prompt

| Action | File Path |
|--------|-----------|
| Created | `services/api/app/routers/sms_otp.py` |
| Created (if missing) | `services/api/app/services/sms_service.py` |
| Modified | `services/api/app/main.py` (2 lines added) |

---

## Notes for Future Development

- The current OTP store uses **in-memory Python dictionary** (`_otp_store`). This is fine for local development and single-server deployment. When you scale to multiple servers (Google Cloud Run with multiple instances), replace it with a **Redis cache** so all instances share the same OTP store.
- Consider adding **rate limiting** to `POST /api/sms/send-otp` before going to production (e.g., max 3 requests per phone number per 10 minutes) to prevent abuse and Telnyx bill inflation.
- Telnyx charges per SMS sent (approximately $0.004–$0.007 per message). Monitor usage in the Telnyx portal under **Billing → Usage**.

---

**PROMPT60_Telnyx_SMS_OTP v1.0**
Last updated: 2026-02-27
