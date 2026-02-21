# PROMPT21_Security_Hardening.md

Read SPEC.md, ARCHITECTURE.md, and CLAUDE.md before making changes.

## Purpose

Harden the Winnow application for production launch. Per SPEC §5 (Hard Requirements): "PII protection — encryption in transit (TLS), encryption at rest for storage. No resume text in logs." Per ARCHITECTURE §3.2: "Never store raw resume text in logs. Principle of least privilege for service accounts." This prompt implements rate limiting, input sanitization, security headers, PII redaction, file upload hardening, dependency vulnerability scanning, and secrets management.

---

## Triggers — When to Use This Prompt

- Preparing the app for public launch / real user traffic.
- Addressing security review findings.
- Adding rate limiting, CSP headers, or input sanitization.
- Ensuring PII does not leak into logs.
- Running dependency vulnerability scans.

---

## What Already Exists (DO NOT recreate)

1. **Auth system:** `services/api/app/services/auth.py` — passlib[bcrypt] password hashing, python-jose JWT, HttpOnly cookie (`rm_session`), `Secure` + `SameSite` flags already adjust per environment (`IS_PRODUCTION`).
2. **CORS:** `services/api/app/main.py` — `CORSMiddleware` with `ALLOWED_ORIGINS` list, `allow_credentials=True`, production origin from `CORS_ORIGIN` env var.
3. **Admin auth:** Admin endpoints gated by `ADMIN_TOKEN` header/query param.
4. **TrustScore gate:** `services/api/app/services/trust_gate.py` — quarantines suspicious uploads.
5. **File upload:** `services/api/app/routers/resume.py` — accepts PDF/DOCX uploads.
6. **Deployment:** Cloud Run with HTTPS (TLS in transit), Cloud SQL with encryption at rest, GCS with default encryption.
7. **CI pipeline:** `.github/workflows/ci.yml` — lint + test on PR.

---

## What to Build

This prompt covers 8 security domains. Each is independent — implement them in order but each stands alone.

---

# PART 1 — RATE LIMITING

Prevent brute-force attacks on auth endpoints and abuse of expensive operations (LLM calls, resume parsing).

### 1.1 Install dependency

**File to modify:** `services/api/requirements.txt`

Add:
```
slowapi>=0.1.9
```

Then install:
```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
pip install slowapi
```

### 1.2 Configure rate limiter

**File to create:** `services/api/app/middleware/rate_limit.py` (NEW)

```python
"""
Rate limiting middleware using slowapi.
Limits are per IP address for unauthenticated endpoints
and per user ID for authenticated endpoints.
"""
import os
from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_key(request):
    """
    Use user ID from JWT cookie if authenticated, otherwise IP address.
    Falls back to IP for unauthenticated requests (login, signup, webhook).
    """
    # Try to extract user from cookie (don't fail if not present)
    cookie_name = os.environ.get("AUTH_COOKIE_NAME", "rm_session")
    token = request.cookies.get(cookie_name)
    if token:
        try:
            from app.services.auth import decode_jwt
            payload = decode_jwt(token)
            user_id = payload.get("sub") or payload.get("user_id")
            if user_id:
                return f"user:{user_id}"
        except Exception:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=_get_key)
```

### 1.3 Register the limiter in main.py

**File to modify:** `services/api/app/main.py`

Add these lines after the `app = FastAPI(...)` creation:

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.middleware.rate_limit import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

### 1.4 Apply rate limits to specific endpoints

Apply limits at the router level. The format is `"<count>/<period>"` — e.g., `"5/minute"` means 5 requests per minute.

**File to modify:** `services/api/app/routers/auth.py`

Add the `@limiter.limit()` decorator to auth endpoints:

```python
from app.middleware.rate_limit import limiter
from fastapi import Request

@router.post("/signup")
@limiter.limit("5/minute")
async def signup(request: Request, body: AuthRequest, db: Session = Depends(get_db)):
    # ... existing code
    pass

@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, body: AuthRequest, db: Session = Depends(get_db)):
    # ... existing code
    pass
```

**IMPORTANT:** The `request: Request` parameter MUST be the first parameter after `self` (if applicable) for slowapi to work. If your existing endpoints don't have `request: Request`, add it.

**File to modify:** `services/api/app/routers/tailor.py`

```python
from app.middleware.rate_limit import limiter
from fastapi import Request

@router.post("/{job_id}")
@limiter.limit("10/minute")
async def generate_tailored_resume(request: Request, job_id: int, ...):
    # ... existing code
    pass
```

**File to modify:** `services/api/app/routers/resume.py`

```python
from app.middleware.rate_limit import limiter
from fastapi import Request

@router.post("/upload")
@limiter.limit("10/minute")
async def upload_resume(request: Request, ...):
    # ... existing code
    pass
```

### 1.5 Rate limit summary

| Endpoint | Limit | Reason |
|----------|-------|--------|
| `POST /api/auth/signup` | 5/minute | Prevent spam account creation |
| `POST /api/auth/login` | 10/minute | Prevent brute-force password guessing |
| `POST /api/resume/upload` | 10/minute | Prevent upload spam |
| `POST /api/tailor/{job_id}` | 10/minute | Expensive LLM call |
| `POST /api/matches/refresh` | 5/minute | Expensive match computation |
| `GET /api/account/export` | 3/minute | Expensive ZIP generation |
| `POST /api/account/delete` | 2/minute | Irreversible action |
| `POST /api/billing/webhook` | 100/minute | Stripe sends bursts |
| All other endpoints | No explicit limit | Default is unlimited |

---

# PART 2 — SECURITY HEADERS MIDDLEWARE

Add standard security response headers to every API response.

**File to create:** `services/api/app/middleware/security_headers.py` (NEW)

```python
"""
Security headers middleware.
Adds standard security headers to every response.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Enable XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy — don't leak URLs
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy — restrict browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), interest-cohort=()"
        )

        # Strict Transport Security (only in production over HTTPS)
        # Cloud Run always terminates TLS, so this is safe
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Cache control for API responses — no caching of user data
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, private"
            )
            response.headers["Pragma"] = "no-cache"

        return response
```

**File to modify:** `services/api/app/main.py`

Register the middleware (order matters — add BEFORE CORSMiddleware so headers are applied after CORS):

```python
from app.middleware.security_headers import SecurityHeadersMiddleware

# Add AFTER app creation, BEFORE CORS middleware registration
app.add_middleware(SecurityHeadersMiddleware)
```

### 2.1 Next.js Security Headers

**File to modify:** `apps/web/next.config.js` (or `next.config.mjs`)

Add security headers for the frontend:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',  // Already exists from PROMPT16

  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-XSS-Protection', value: '1; mode=block' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://js.stripe.com",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com",
              "img-src 'self' data: blob: https:",
              "connect-src 'self' " + (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000') + " https://api.stripe.com",
              "frame-src https://js.stripe.com https://hooks.stripe.com",
              "object-src 'none'",
              "base-uri 'self'",
              "form-action 'self'",
            ].join('; '),
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=(), payment=(self)',
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=31536000; includeSubDomains',
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
```

---

# PART 3 — PII LOG REDACTION

Per SPEC §5: "No resume text in logs." Ensure no PII (email, phone, resume content, profile JSON) appears in application logs.

### 3.1 Create a PII-safe log filter

**File to create:** `services/api/app/middleware/log_filter.py` (NEW)

```python
"""
PII redaction filter for Python logging.
Strips or masks sensitive data from log messages before they are emitted.
"""
import logging
import re


# Patterns to redact
PII_PATTERNS = [
    # Email addresses
    (re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'), '[EMAIL_REDACTED]'),
    # Phone numbers (US and international)
    (re.compile(r'(\+?1?[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'), '[PHONE_REDACTED]'),
    # SSN
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[SSN_REDACTED]'),
    # JWT tokens (long base64 strings)
    (re.compile(r'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}'), '[JWT_REDACTED]'),
    # API keys (common patterns)
    (re.compile(r'sk[-_](?:test|live)[-_][A-Za-z0-9]{20,}'), '[STRIPE_KEY_REDACTED]'),
    (re.compile(r'sk-ant-[A-Za-z0-9_-]{20,}'), '[ANTHROPIC_KEY_REDACTED]'),
    (re.compile(r'pa-[A-Za-z0-9_-]{20,}'), '[VOYAGE_KEY_REDACTED]'),
    (re.compile(r'whsec_[A-Za-z0-9]{20,}'), '[WEBHOOK_SECRET_REDACTED]'),
]

# Fields to redact entirely when they appear as keys in log messages
SENSITIVE_FIELD_NAMES = {
    'password', 'password_hash', 'token', 'secret', 'api_key',
    'extracted_text', 'resume_text', 'profile_json', 'description_text',
    'cover_letter_text', 'change_log',
}


class PIIRedactionFilter(logging.Filter):
    """Logging filter that redacts PII from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in PII_PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        
        # Also redact args if they're strings
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: '[REDACTED]' if k.lower() in SENSITIVE_FIELD_NAMES else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._redact_value(a) for a in record.args
                )
        
        return True
    
    def _redact_value(self, value):
        if isinstance(value, str):
            for pattern, replacement in PII_PATTERNS:
                value = pattern.sub(replacement, value)
        return value


def configure_safe_logging():
    """
    Configure Python logging with PII redaction.
    Call this once at application startup.
    """
    pii_filter = PIIRedactionFilter()
    
    # Apply to root logger so ALL log messages are filtered
    root_logger = logging.getLogger()
    root_logger.addFilter(pii_filter)
    
    # Also apply to uvicorn's access logger
    for name in ('uvicorn', 'uvicorn.access', 'uvicorn.error'):
        logger = logging.getLogger(name)
        logger.addFilter(pii_filter)
```

### 3.2 Initialize PII-safe logging at startup

**File to modify:** `services/api/app/main.py`

Add near the top, before any logging calls:

```python
from app.middleware.log_filter import configure_safe_logging
configure_safe_logging()
```

### 3.3 Audit existing code for PII leaks

Search the codebase for any `logger.info`, `logger.debug`, `logger.warning`, or `print` statements that might include PII. Common offenders:

- `services/api/app/services/profile_parser.py` — may log `extracted_text`
- `services/api/app/services/tailor.py` — may log LLM prompts containing resume content
- `services/api/app/services/matching.py` — may log job descriptions or profile data
- `services/api/app/routers/auth.py` — may log email addresses

For each, replace direct PII logging with safe alternatives:

```python
# BAD — logs PII
logger.info(f"Parsing resume for user {user.email}, text: {extracted_text[:200]}")

# GOOD — no PII
logger.info(f"Parsing resume for user_id={user.id}, text_length={len(extracted_text)}")
```

```python
# BAD — logs profile JSON
logger.info(f"Profile updated: {profile.profile_json}")

# GOOD — no PII
logger.info(f"Profile updated for user_id={user_id}, version={profile.version}")
```

---

# PART 4 — INPUT SANITIZATION

Validate and sanitize all user inputs to prevent injection attacks.

### 4.1 Email validation

**File to modify:** `services/api/app/routers/auth.py`

Add email validation in signup and login:

```python
import re

EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)

def _validate_email(email: str) -> str:
    """Validate and normalize email."""
    email = email.strip().lower()
    if not EMAIL_REGEX.match(email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    if len(email) > 255:
        raise HTTPException(status_code=400, detail="Email too long")
    return email
```

Call `_validate_email(body.email)` at the start of `signup` and `login` handlers.

### 4.2 Password strength requirements

**File to modify:** `services/api/app/routers/auth.py`

Add minimum password requirements on signup:

```python
def _validate_password(password: str):
    """Enforce minimum password requirements."""
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if len(password) > 128:
        raise HTTPException(status_code=400, detail="Password too long")
    if password.isdigit():
        raise HTTPException(status_code=400, detail="Password cannot be all numbers")
    if password.isalpha():
        raise HTTPException(status_code=400, detail="Password must include at least one number or special character")
```

Call `_validate_password(body.password)` at the start of the `signup` handler.

### 4.3 General string sanitization helper

**File to create:** `services/api/app/middleware/sanitize.py` (NEW)

```python
"""
Input sanitization utilities.
Strip dangerous characters, enforce length limits, and prevent injection.
"""
import re
import html


def sanitize_text(value: str, max_length: int = 10000) -> str:
    """
    Sanitize a text input:
    - Strip leading/trailing whitespace
    - HTML-encode special characters
    - Enforce max length
    - Remove null bytes
    """
    if not isinstance(value, str):
        return value
    
    value = value.strip()
    value = value.replace('\x00', '')  # Remove null bytes
    value = html.escape(value)
    
    if len(value) > max_length:
        value = value[:max_length]
    
    return value


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename:
    - Remove path separators
    - Remove special characters except dots, hyphens, underscores
    - Enforce max length
    """
    if not filename:
        return "unnamed"
    
    # Remove path separators
    filename = filename.replace('/', '').replace('\\', '')
    
    # Keep only safe characters
    filename = re.sub(r'[^\w.\-]', '_', filename)
    
    # Prevent directory traversal
    filename = filename.lstrip('.')
    
    if len(filename) > 255:
        filename = filename[:255]
    
    return filename or "unnamed"
```

### 4.4 Apply filename sanitization to resume upload

**File to modify:** `services/api/app/routers/resume.py`

In the upload handler, sanitize the filename before saving:

```python
from app.middleware.sanitize import sanitize_filename

@router.post("/upload")
async def upload_resume(file: UploadFile, ...):
    safe_filename = sanitize_filename(file.filename)
    # Use safe_filename instead of file.filename when saving
    # ... rest of existing upload logic
```

---

# PART 5 — FILE UPLOAD HARDENING

Strengthen file upload validation beyond the basic extension check.

### 5.1 Create upload validator

**File to create:** `services/api/app/middleware/upload_validator.py` (NEW)

```python
"""
File upload validation.
Validates file size, extension, MIME type, and magic bytes.
"""
import logging
from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)

# Maximum file size: 10 MB
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Allowed file types with their MIME types and magic bytes
ALLOWED_TYPES = {
    ".pdf": {
        "mime_types": ["application/pdf"],
        "magic_bytes": [b"%PDF"],
    },
    ".docx": {
        "mime_types": [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/octet-stream",  # Some clients send this
        ],
        "magic_bytes": [b"PK\x03\x04"],  # DOCX is a ZIP file
    },
}


async def validate_upload(file: UploadFile) -> bytes:
    """
    Validate an uploaded file and return its contents.
    
    Checks:
    1. File extension is allowed (.pdf or .docx)
    2. MIME type matches expected type for the extension
    3. File size is under the limit
    4. Magic bytes match expected file format
    
    Returns: The file contents as bytes.
    Raises: HTTPException if validation fails.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    # 1. Check extension
    filename_lower = file.filename.lower()
    ext = None
    for allowed_ext in ALLOWED_TYPES:
        if filename_lower.endswith(allowed_ext):
            ext = allowed_ext
            break
    
    if not ext:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Accepted: {', '.join(ALLOWED_TYPES.keys())}"
        )
    
    # 2. Check MIME type
    allowed = ALLOWED_TYPES[ext]
    if file.content_type and file.content_type not in allowed["mime_types"]:
        logger.warning(
            f"MIME type mismatch: expected one of {allowed['mime_types']}, "
            f"got {file.content_type} for extension {ext}"
        )
        # Log but don't block — some browsers send incorrect MIME types
    
    # 3. Read file and check size
    contents = await file.read()
    await file.seek(0)  # Reset for downstream consumers
    
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB"
        )
    
    # 4. Check magic bytes
    magic_match = False
    for magic in allowed["magic_bytes"]:
        if contents[:len(magic)] == magic:
            magic_match = True
            break
    
    if not magic_match:
        raise HTTPException(
            status_code=400,
            detail="File content does not match its extension. The file may be corrupted."
        )
    
    return contents
```

### 5.2 Apply to resume upload

**File to modify:** `services/api/app/routers/resume.py`

Replace the existing file validation (if any) with the hardened validator:

```python
from app.middleware.upload_validator import validate_upload

@router.post("/upload")
async def upload_resume(file: UploadFile, ...):
    # Validate file before processing
    contents = await validate_upload(file)
    
    # ... rest of existing upload logic, using contents instead of re-reading
```

---

# PART 6 — DEPENDENCY VULNERABILITY SCANNING

Add automated scanning for known vulnerabilities in Python and JavaScript dependencies.

### 6.1 Python: pip-audit

**File to modify:** `services/api/requirements-dev.txt`

Add:
```
pip-audit>=2.7.0
```

### 6.2 Create a scan script

**File to create:** `services/api/scripts/security-scan.ps1` (NEW)

```powershell
# Security scan script for Python dependencies
Write-Host "=== Running pip-audit (Python dependency vulnerability scan) ===" -ForegroundColor Cyan
pip-audit --strict --desc

Write-Host ""
Write-Host "=== Running Ruff security checks ===" -ForegroundColor Cyan
python -m ruff check . --select S  # S = Bandit security rules

Write-Host ""
Write-Host "=== Scan complete ===" -ForegroundColor Green
```

### 6.3 JavaScript: npm audit

**File to create:** `apps/web/scripts/security-scan.ps1` (NEW)

```powershell
# Security scan script for JavaScript dependencies
Write-Host "=== Running npm audit ===" -ForegroundColor Cyan
npm audit --production

Write-Host ""
Write-Host "=== Scan complete ===" -ForegroundColor Green
```

### 6.4 Add to CI pipeline

**File to modify:** `.github/workflows/ci.yml`

Add a new job for security scanning:

```yaml
  security-scan:
    name: Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Install Python dependencies
        run: |
          cd services/api
          pip install -r requirements.txt -r requirements-dev.txt
      
      - name: Run pip-audit
        run: |
          cd services/api
          pip-audit --strict --desc
        continue-on-error: true  # Don't block CI, but report findings
      
      - name: Run npm audit
        run: |
          cd apps/web
          npm ci
          npm audit --production --audit-level=high
        continue-on-error: true  # Don't block CI, but report findings
```

---

# PART 7 — AUTH HARDENING

Strengthen existing auth beyond the current implementation.

### 7.1 Password hashing cost factor

**File to modify:** `services/api/app/services/auth.py`

Ensure bcrypt rounds are set appropriately:

```python
from passlib.context import CryptContext

# Use 12 rounds (default is 12, but be explicit)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
```

### 7.2 JWT expiry and validation hardening

**File to modify:** `services/api/app/services/auth.py`

Ensure the JWT includes audience and issuer claims:

```python
def create_jwt(user_id: int, email: str) -> str:
    """Create a JWT with proper security claims."""
    expires = datetime.utcnow() + timedelta(
        days=int(os.environ.get("AUTH_TOKEN_EXPIRES_DAYS", "7"))
    )
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expires,
        "iat": datetime.utcnow(),
        "iss": "winnow-api",
        "aud": "winnow-web",
    }
    return jwt.encode(
        payload,
        os.environ.get("AUTH_SECRET", ""),
        algorithm="HS256",
    )


def decode_jwt(token: str) -> dict:
    """Decode and validate a JWT with all claims."""
    return jwt.decode(
        token,
        os.environ.get("AUTH_SECRET", ""),
        algorithms=["HS256"],
        audience="winnow-web",
        issuer="winnow-api",
    )
```

### 7.3 Timing-safe auth error messages

**File to modify:** `services/api/app/routers/auth.py`

Use identical error messages for "user not found" and "wrong password" to prevent user enumeration:

```python
@router.post("/login")
async def login(...):
    user = db.query(User).filter(User.email == email).first()
    
    # Same error message for both cases — prevents user enumeration
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # ... rest of login logic
```

### 7.4 AUTH_SECRET validation at startup

**File to modify:** `services/api/app/main.py`

Add a startup check that the auth secret is strong enough for production:

```python
import os

@app.on_event("startup")
async def _validate_security_config():
    """Validate critical security configuration on startup."""
    auth_secret = os.environ.get("AUTH_SECRET", "")
    env = os.environ.get("ENV", "dev")
    
    if env != "dev":
        # In production, require a strong secret
        if len(auth_secret) < 32:
            raise RuntimeError(
                "AUTH_SECRET must be at least 32 characters in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if auth_secret in ("dev-secret-change-me", "secret", "changeme"):
            raise RuntimeError("AUTH_SECRET is using a default value. Set a real secret.")
```

---

# PART 8 — PRODUCTION ENVIRONMENT CHECKLIST ENDPOINT

Add a hidden endpoint that reports the security posture of the running instance (admin-only).

**File to create:** `services/api/app/routers/security_check.py` (NEW)

```python
"""
Security posture check endpoint (admin-only).
Reports on security configuration of the running instance.
"""
import os
import logging

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/security", tags=["admin-security"])


@router.get("/check")
async def security_check(
    admin_token: str = Query(..., alias="admin_token"),
):
    """
    Check the security posture of the running instance.
    Admin-only. Returns a report of security configuration.
    """
    expected_token = os.environ.get("ADMIN_TOKEN", "")
    if admin_token != expected_token:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    env = os.environ.get("ENV", "dev")
    auth_secret = os.environ.get("AUTH_SECRET", "")
    
    checks = []
    all_pass = True
    
    # 1. AUTH_SECRET strength
    if len(auth_secret) >= 32 and auth_secret not in ("dev-secret-change-me",):
        checks.append({"check": "AUTH_SECRET strength", "status": "PASS"})
    else:
        checks.append({"check": "AUTH_SECRET strength", "status": "FAIL", "detail": "Secret too short or default value"})
        all_pass = False
    
    # 2. Environment mode
    if env != "dev":
        checks.append({"check": "Production mode", "status": "PASS", "detail": f"ENV={env}"})
    else:
        checks.append({"check": "Production mode", "status": "WARN", "detail": "Running in dev mode"})
    
    # 3. CORS origin
    cors_origin = os.environ.get("CORS_ORIGIN", "")
    if cors_origin and "localhost" not in cors_origin:
        checks.append({"check": "CORS origin", "status": "PASS", "detail": cors_origin})
    else:
        checks.append({"check": "CORS origin", "status": "WARN", "detail": "CORS origin not set or is localhost"})
    
    # 4. Stripe keys (live mode)
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if stripe_key.startswith("sk_live_"):
        checks.append({"check": "Stripe live mode", "status": "PASS"})
    elif stripe_key.startswith("sk_test_"):
        checks.append({"check": "Stripe live mode", "status": "WARN", "detail": "Using test mode keys"})
    else:
        checks.append({"check": "Stripe live mode", "status": "SKIP", "detail": "No Stripe key configured"})
    
    # 5. Database encryption (Cloud SQL always encrypts at rest)
    db_url = os.environ.get("DB_URL", "")
    if "cloudsql" in db_url or "cloud" in db_url:
        checks.append({"check": "Database encryption at rest", "status": "PASS", "detail": "Cloud SQL (encrypted by default)"})
    else:
        checks.append({"check": "Database encryption at rest", "status": "WARN", "detail": "Local database — no encryption at rest"})
    
    # 6. GCS bucket configured
    gcs_bucket = os.environ.get("GCS_BUCKET", "")
    if gcs_bucket:
        checks.append({"check": "GCS bucket", "status": "PASS", "detail": gcs_bucket})
    else:
        checks.append({"check": "GCS bucket", "status": "WARN", "detail": "Using local file storage"})
    
    return {
        "environment": env,
        "all_pass": all_pass,
        "checks": checks,
    }
```

**File to modify:** `services/api/app/main.py`

Register the router:

```python
from app.routers import security_check

app.include_router(security_check.router)
```

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Rate limiter config | `services/api/app/middleware/rate_limit.py` | CREATE |
| Security headers middleware | `services/api/app/middleware/security_headers.py` | CREATE |
| PII log redaction filter | `services/api/app/middleware/log_filter.py` | CREATE |
| Input sanitization utils | `services/api/app/middleware/sanitize.py` | CREATE |
| Upload validator | `services/api/app/middleware/upload_validator.py` | CREATE |
| Security check endpoint | `services/api/app/routers/security_check.py` | CREATE |
| Middleware __init__ | `services/api/app/middleware/__init__.py` | CREATE (empty) |
| Main app (register all) | `services/api/app/main.py` | MODIFY — add middleware + routers |
| Auth router (rate limits + validation) | `services/api/app/routers/auth.py` | MODIFY |
| Auth service (JWT hardening) | `services/api/app/services/auth.py` | MODIFY |
| Resume router (upload hardening) | `services/api/app/routers/resume.py` | MODIFY |
| Tailor router (rate limit) | `services/api/app/routers/tailor.py` | MODIFY |
| Next.js config (CSP headers) | `apps/web/next.config.js` | MODIFY |
| Requirements.txt | `services/api/requirements.txt` | MODIFY — add `slowapi` |
| Requirements-dev.txt | `services/api/requirements-dev.txt` | MODIFY — add `pip-audit` |
| Python scan script | `services/api/scripts/security-scan.ps1` | CREATE |
| JS scan script | `apps/web/scripts/security-scan.ps1` | CREATE |
| CI workflow (security job) | `.github/workflows/ci.yml` | MODIFY — add security-scan job |

---

## Implementation Order (for a beginner following in Cursor)

### Phase 1: Dependencies (Steps 1–2)

1. **Step 1:** Add `slowapi>=0.1.9` to `services/api/requirements.txt`. Install:
   ```powershell
   cd services/api
   .\.venv\Scripts\Activate.ps1
   pip install slowapi
   ```
2. **Step 2:** Add `pip-audit>=2.7.0` to `services/api/requirements-dev.txt`. Install:
   ```powershell
   pip install pip-audit
   ```

### Phase 2: Middleware Directory (Step 3)

3. **Step 3:** Create the middleware directory and its files:
   ```powershell
   mkdir services/api/app/middleware
   ```
   Create these files inside `services/api/app/middleware/`:
   - `__init__.py` (empty file)
   - `rate_limit.py` (Part 1.2)
   - `security_headers.py` (Part 2)
   - `log_filter.py` (Part 3.1)
   - `sanitize.py` (Part 4.3)
   - `upload_validator.py` (Part 5.1)

### Phase 3: Register in Main App (Step 4)

4. **Step 4:** Open `services/api/app/main.py`. Add all registrations:
   - Import and call `configure_safe_logging()` (Part 3.2)
   - Add `SecurityHeadersMiddleware` (Part 2)
   - Register rate limiter state + exception handler (Part 1.3)
   - Add auth secret validation on startup (Part 7.4)
   - Register `security_check.router` (Part 8)

### Phase 4: Harden Existing Routers (Steps 5–9)

5. **Step 5:** Open `services/api/app/routers/auth.py`. Add:
   - `@limiter.limit()` decorators on signup and login (Part 1.4)
   - `_validate_email()` function (Part 4.1)
   - `_validate_password()` function (Part 4.2)
   - Timing-safe error messages on login (Part 7.3)
6. **Step 6:** Open `services/api/app/services/auth.py`. Add:
   - Explicit bcrypt rounds (Part 7.1)
   - JWT `iss` and `aud` claims in `create_jwt` and `decode_jwt` (Part 7.2)
7. **Step 7:** Open `services/api/app/routers/resume.py`. Add:
   - Rate limit decorator (Part 1.4)
   - `validate_upload()` call (Part 5.2)
   - `sanitize_filename()` call (Part 4.4)
8. **Step 8:** Open `services/api/app/routers/tailor.py`. Add rate limit decorator (Part 1.4).
9. **Step 9:** Audit all `logger.info/debug/warning` calls in `services/api/app/services/` for PII leaks (Part 3.3). Replace any that log email, phone, resume text, or profile JSON.

### Phase 5: Frontend Headers (Step 10)

10. **Step 10:** Open `apps/web/next.config.js`. Add the `headers()` function with CSP and security headers (Part 2.1).

### Phase 6: Scan Scripts + CI (Steps 11–12)

11. **Step 11:** Create scan scripts:
    - `services/api/scripts/security-scan.ps1` (Part 6.2)
    - `apps/web/scripts/security-scan.ps1` (Part 6.3)
12. **Step 12:** Open `.github/workflows/ci.yml`. Add the `security-scan` job (Part 6.4).

### Phase 7: Test + Verify (Steps 13–16)

13. **Step 13:** Start the API locally:
    ```powershell
    cd services/api
    .\.venv\Scripts\Activate.ps1
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ```
14. **Step 14:** Test rate limiting — hit `POST /api/auth/login` more than 10 times in a minute. You should get a `429 Too Many Requests` response.
15. **Step 15:** Test security headers — make any API request and inspect the response headers. You should see `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, etc.
16. **Step 16:** Test upload validation — try uploading a `.txt` file renamed to `.pdf`. You should get a `400` error about magic bytes not matching.

### Phase 8: Run Scans + Lint (Steps 17–18)

17. **Step 17:** Run the security scans:
    ```powershell
    cd services/api
    .\.venv\Scripts\Activate.ps1
    pip-audit --strict --desc
    python -m ruff check . --select S
    
    cd ../../apps/web
    npm audit --production
    ```
18. **Step 18:** Lint and format:
    ```powershell
    cd services/api
    python -m ruff check .
    python -m ruff format .
    cd ../../apps/web
    npm run lint
    ```

---

## Non-Goals (Do NOT implement in this prompt)

- WAF / Cloud Armor (future — use if traffic grows)
- DDoS protection (Cloud Run has built-in basic protection)
- Penetration testing (should be done by a security professional)
- SOC 2 / HIPAA compliance documentation
- Database-level column encryption (Cloud SQL encrypts at rest by default)
- IP allowlisting for admin endpoints (future)
- Two-factor authentication (future)
- OAuth2 / social login hardening (not yet implemented)
- Session revocation / token blocklist (JWT is stateless — accept current trade-off)

---

## Summary Checklist

### Rate Limiting
- [ ] `slowapi` installed and configured
- [ ] Rate limiter registered in `main.py`
- [ ] Auth endpoints limited: signup (5/min), login (10/min)
- [ ] Expensive endpoints limited: upload (10/min), tailor (10/min), export (3/min)
- [ ] Webhook endpoint has generous limit (100/min)
- [ ] 429 responses returned when limits are exceeded

### Security Headers
- [ ] API middleware: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy, HSTS, Cache-Control
- [ ] Next.js headers: CSP (script-src, style-src, connect-src, frame-src for Stripe), HSTS, X-Frame-Options

### PII Log Redaction
- [ ] `PIIRedactionFilter` applied to root logger
- [ ] Email, phone, SSN, JWT, API keys redacted from log messages
- [ ] Sensitive field names (`extracted_text`, `profile_json`, etc.) redacted from dict args
- [ ] Manual audit of existing `logger.*` calls — no PII in log messages
- [ ] Uvicorn access/error loggers filtered

### Input Sanitization
- [ ] Email validation on signup/login (regex, length, normalize to lowercase)
- [ ] Password strength check on signup (8+ chars, not all-numeric, not all-alpha)
- [ ] Filename sanitization on upload (no path separators, no special chars)
- [ ] General `sanitize_text()` utility available for other inputs

### File Upload Hardening
- [ ] Extension whitelist (.pdf, .docx only)
- [ ] MIME type check (log mismatch, don't block — browsers are unreliable)
- [ ] File size limit (10 MB max)
- [ ] Magic bytes validation (PDF starts with `%PDF`, DOCX starts with `PK`)
- [ ] Empty file rejection

### Dependency Scanning
- [ ] `pip-audit` installed as dev dependency
- [ ] `security-scan.ps1` scripts for Python and JavaScript
- [ ] CI job runs `pip-audit` and `npm audit` on every push
- [ ] Ruff security rules (`--select S`) included in scan

### Auth Hardening
- [ ] Bcrypt rounds explicitly set to 12
- [ ] JWT includes `iss`, `aud`, `iat` claims
- [ ] JWT validation checks `iss` and `aud`
- [ ] Login error messages are identical for "user not found" and "wrong password"
- [ ] AUTH_SECRET validated at startup in production (min 32 chars, no defaults)

### Security Check Endpoint
- [ ] `GET /api/admin/security/check` reports security posture
- [ ] Checks: AUTH_SECRET strength, environment mode, CORS, Stripe mode, DB encryption, GCS bucket
- [ ] Admin-only (requires admin_token)

Return code changes only.
