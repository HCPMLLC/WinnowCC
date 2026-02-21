# PROMPT19_Implement_Data_Export.md

Read SPEC.md, ARCHITECTURE.md, and CLAUDE.md before making changes.

## Purpose

Implement data export and account deletion so users can download all their data and permanently delete their account. This is a **hard requirement** from SPEC §5 ("user can delete account and all data; export profile and generated resumes") and ARCHITECTURE §9 ("Users can delete account and all stored artifacts"). Required before public launch for GDPR-style compliance.

---

## Triggers — When to Use This Prompt

- Adding data export ("download my data") functionality.
- Adding account deletion ("delete my account") functionality.
- Implementing GDPR/privacy compliance features.
- Building a Settings or Account page for user self-service.

---

## What Already Exists (DO NOT recreate)

1. **Auth system:** `services/api/app/services/auth.py` — JWT cookies, `get_current_user` dependency. Cookie name: `rm_session`.
2. **User model:** `services/api/app/models/user.py` — `users` table (id, email, password_hash, onboarding_completed_at, is_admin, created_at, updated_at).
3. **Database models with user_id FK** (all in `services/api/app/models/`):
   - `candidate_profiles` — user_id FK, profile_json (JSONB), version, embedding
   - `candidate_trust` — user_id FK, trust_score, status, consent fields
   - `resume_documents` — user_id FK, original file path/URL, extracted_text
   - `matches` — user_id FK, job_id FK, scores, reasons JSON, semantic_similarity
   - `tailored_resumes` — user_id FK, job_id FK, docx_url, change_log JSON
   - `trust_audit_log` — user_id FK, action, details, timestamp
   - `application_tracking` — user_id FK, job_id FK, status, notes
4. **Job-parsed details:** `job_parsed_details` — NOT user-specific (shared job data, do NOT delete).
5. **Jobs table:** `jobs` — NOT user-specific (shared job postings, do NOT delete).
6. **File storage:** Resume files stored locally in `services/api/data/uploads/` (dev) or GCS bucket `winnow-resumes` (production). Tailored resume DOCX stored similarly.
7. **Queue/worker:** `services/api/app/services/queue.py` + `services/api/app/worker.py` — RQ-based background jobs.
8. **Main app:** `services/api/app/main.py` — FastAPI app with router registrations and CORS middleware.
9. **Frontend layout:** `apps/web/app/` — Next.js App Router with existing pages for dashboard, matches, profile, login.

---

## What to Build

### Part 1: Data Export Service

**File to create:** `services/api/app/services/data_export.py` (NEW)

This service collects all user data from every table and packages it into a ZIP file.

#### 1.1 What to include in the export

The export ZIP should contain:

```
winnow-export-{user_id}-{timestamp}/
├── profile.json              # Full candidate profile (latest version)
├── profile_history.json      # All profile versions
├── account.json              # User account info (email, created_at, onboarding status)
├── trust.json                # Trust score and consent status
├── matches.json              # All match records with scores and reasons
├── applications.json         # Application tracking history
├── tailored_resumes.json     # Tailored resume metadata + change logs
├── resumes/                  # Original uploaded resume files
│   ├── resume_1.pdf
│   └── resume_2.docx
└── tailored/                 # Generated tailored resume DOCX files
    ├── tailored_job_123.docx
    └── tailored_job_456.docx
```

#### 1.2 Export service implementation

```python
"""
Data export service.
Collects all user data and packages it into a downloadable ZIP.
"""
import io
import json
import os
import zipfile
import logging
from datetime import datetime

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def export_user_data(user_id: int, db: Session) -> io.BytesIO:
    """
    Export all data for a user as a ZIP file in memory.
    
    Returns: BytesIO containing the ZIP file.
    """
    from app.models.user import User
    from app.models.candidate_profile import CandidateProfile
    from app.models.candidate_trust import CandidateTrust
    from app.models.resume_document import ResumeDocument
    from app.models.match import Match
    from app.models.tailored_resume import TailoredResume
    from app.models.trust_audit_log import TrustAuditLog
    # Import ApplicationTracking if it exists
    # from app.models.application_tracking import ApplicationTracking
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    folder_name = f"winnow-export-{user_id}-{timestamp}"
    
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        
        # ── 1. Account info ──
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            account_data = {
                "user_id": user.id,
                "email": user.email,
                "created_at": str(user.created_at) if user.created_at else None,
                "updated_at": str(user.updated_at) if user.updated_at else None,
                "onboarding_completed_at": str(user.onboarding_completed_at) if user.onboarding_completed_at else None,
                "is_admin": user.is_admin,
            }
            zf.writestr(
                f"{folder_name}/account.json",
                json.dumps(account_data, indent=2, default=str),
            )
        
        # ── 2. Candidate profiles (all versions) ──
        profiles = (
            db.query(CandidateProfile)
            .filter(CandidateProfile.user_id == user_id)
            .order_by(CandidateProfile.version.desc())
            .all()
        )
        if profiles:
            # Latest version
            latest = profiles[0]
            zf.writestr(
                f"{folder_name}/profile.json",
                json.dumps(latest.profile_json, indent=2, default=str),
            )
            # All versions
            history = []
            for p in profiles:
                history.append({
                    "version": p.version,
                    "profile_json": p.profile_json,
                    "created_at": str(p.created_at) if hasattr(p, "created_at") and p.created_at else None,
                    "updated_at": str(p.updated_at) if hasattr(p, "updated_at") and p.updated_at else None,
                })
            zf.writestr(
                f"{folder_name}/profile_history.json",
                json.dumps(history, indent=2, default=str),
            )
        
        # ── 3. Trust record ──
        trust = db.query(CandidateTrust).filter(CandidateTrust.user_id == user_id).first()
        if trust:
            trust_data = {
                "trust_score": trust.trust_score,
                "status": trust.status,
                "consent_resume_parse": getattr(trust, "consent_resume_parse", None),
                "consent_job_match": getattr(trust, "consent_job_match", None),
                "consent_ai_generation": getattr(trust, "consent_ai_generation", None),
                "updated_at": str(trust.updated_at) if hasattr(trust, "updated_at") and trust.updated_at else None,
            }
            zf.writestr(
                f"{folder_name}/trust.json",
                json.dumps(trust_data, indent=2, default=str),
            )
        
        # ── 4. Matches ──
        matches = db.query(Match).filter(Match.user_id == user_id).all()
        if matches:
            matches_data = []
            for m in matches:
                matches_data.append({
                    "match_id": m.id,
                    "job_id": m.job_id,
                    "profile_version": getattr(m, "profile_version", None),
                    "match_score": m.match_score,
                    "interview_readiness_score": getattr(m, "interview_readiness_score", None),
                    "offer_probability": getattr(m, "offer_probability", None),
                    "semantic_similarity": getattr(m, "semantic_similarity", None),
                    "reasons": m.reasons if hasattr(m, "reasons") else None,
                    "created_at": str(m.created_at) if hasattr(m, "created_at") and m.created_at else None,
                })
            zf.writestr(
                f"{folder_name}/matches.json",
                json.dumps(matches_data, indent=2, default=str),
            )
        
        # ── 5. Application tracking ──
        try:
            from app.models.application_tracking import ApplicationTracking
            apps = db.query(ApplicationTracking).filter(ApplicationTracking.user_id == user_id).all()
            if apps:
                apps_data = []
                for a in apps:
                    apps_data.append({
                        "job_id": a.job_id,
                        "status": a.status,
                        "notes": getattr(a, "notes", None),
                        "updated_at": str(a.updated_at) if hasattr(a, "updated_at") and a.updated_at else None,
                    })
                zf.writestr(
                    f"{folder_name}/applications.json",
                    json.dumps(apps_data, indent=2, default=str),
                )
        except ImportError:
            pass  # ApplicationTracking model may not exist yet
        
        # ── 6. Tailored resumes (metadata + files) ──
        tailored = db.query(TailoredResume).filter(TailoredResume.user_id == user_id).all()
        if tailored:
            tailored_data = []
            for t in tailored:
                tailored_data.append({
                    "tailored_resume_id": t.id,
                    "job_id": t.job_id,
                    "profile_version": getattr(t, "profile_version", None),
                    "docx_url": getattr(t, "docx_url", None),
                    "change_log": t.change_log if hasattr(t, "change_log") else None,
                    "created_at": str(t.created_at) if hasattr(t, "created_at") and t.created_at else None,
                })
                # Include the actual DOCX file if available locally
                docx_path = getattr(t, "docx_url", None)
                if docx_path and os.path.isfile(docx_path):
                    filename = os.path.basename(docx_path)
                    zf.write(docx_path, f"{folder_name}/tailored/{filename}")
            zf.writestr(
                f"{folder_name}/tailored_resumes.json",
                json.dumps(tailored_data, indent=2, default=str),
            )
        
        # ── 7. Resume documents (metadata + files) ──
        resumes = db.query(ResumeDocument).filter(ResumeDocument.user_id == user_id).all()
        if resumes:
            for r in resumes:
                file_path = getattr(r, "file_path", None) or getattr(r, "original_file_url", None)
                if file_path and os.path.isfile(file_path):
                    filename = os.path.basename(file_path)
                    zf.write(file_path, f"{folder_name}/resumes/{filename}")
        
        # ── 8. Trust audit log ──
        try:
            audit_logs = db.query(TrustAuditLog).filter(TrustAuditLog.user_id == user_id).all()
            if audit_logs:
                audit_data = []
                for log in audit_logs:
                    audit_data.append({
                        "action": log.action,
                        "details": getattr(log, "details", None),
                        "created_at": str(log.created_at) if hasattr(log, "created_at") and log.created_at else None,
                    })
                zf.writestr(
                    f"{folder_name}/audit_log.json",
                    json.dumps(audit_data, indent=2, default=str),
                )
        except Exception:
            pass  # TrustAuditLog may not exist
    
    zip_buffer.seek(0)
    return zip_buffer
```

#### 1.3 GCS file retrieval (production)

In production, resume files and tailored DOCX files are stored in GCS, not locally. Add a helper to download them into the ZIP:

```python
def _download_gcs_file(gcs_url: str) -> bytes | None:
    """Download a file from GCS and return its bytes. Returns None on failure."""
    try:
        from google.cloud import storage
        # Parse bucket and blob name from URL
        # URL format: gs://bucket-name/path/to/file or https://storage.googleapis.com/bucket/path
        bucket_name = os.environ.get("GCS_BUCKET", "winnow-resumes")
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        # Extract blob name from URL
        blob_name = gcs_url.split(f"{bucket_name}/")[-1] if bucket_name in gcs_url else gcs_url
        blob = bucket.blob(blob_name)
        return blob.download_as_bytes()
    except Exception as e:
        logger.warning(f"Failed to download GCS file {gcs_url}: {e}")
        return None
```

Use `_download_gcs_file()` in the export when a file path starts with `gs://` or `https://storage.googleapis.com/`.

---

### Part 2: Account Deletion Service

**File to create:** `services/api/app/services/account_deletion.py` (NEW)

This service permanently deletes all user data across every table and removes stored files.

#### 2.1 Deletion order matters — foreign keys

Delete in reverse dependency order to avoid FK constraint violations. The correct order is:

1. `trust_audit_log` (FK → user_id)
2. `application_tracking` (FK → user_id, job_id)
3. `tailored_resumes` (FK → user_id, job_id) — also delete stored files
4. `matches` (FK → user_id, job_id)
5. `candidate_trust` (FK → user_id)
6. `candidate_profiles` (FK → user_id)
7. `resume_documents` (FK → user_id) — also delete stored files
8. `users` (the user record itself) — **delete last**

Do NOT delete from the `jobs` or `job_parsed_details` tables — those are shared data.

#### 2.2 Deletion service implementation

```python
"""
Account deletion service.
Permanently removes all user data from every table and deletes stored files.
"""
import os
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def delete_user_account(user_id: int, db: Session) -> dict:
    """
    Permanently delete all data for a user.
    
    Args:
        user_id: The user to delete.
        db: Database session.
    
    Returns:
        Summary dict with counts of deleted records per table.
    """
    from app.models.user import User
    from app.models.candidate_profile import CandidateProfile
    from app.models.candidate_trust import CandidateTrust
    from app.models.resume_document import ResumeDocument
    from app.models.match import Match
    from app.models.tailored_resume import TailoredResume
    from app.models.trust_audit_log import TrustAuditLog
    
    summary = {}
    
    # ── 1. Trust audit log ──
    try:
        count = db.query(TrustAuditLog).filter(TrustAuditLog.user_id == user_id).delete()
        summary["trust_audit_log"] = count
    except Exception as e:
        logger.warning(f"Could not delete trust_audit_log: {e}")
        summary["trust_audit_log"] = 0
    
    # ── 2. Application tracking ──
    try:
        from app.models.application_tracking import ApplicationTracking
        count = db.query(ApplicationTracking).filter(ApplicationTracking.user_id == user_id).delete()
        summary["application_tracking"] = count
    except Exception as e:
        logger.warning(f"Could not delete application_tracking: {e}")
        summary["application_tracking"] = 0
    
    # ── 3. Tailored resumes (delete files first, then DB records) ──
    tailored = db.query(TailoredResume).filter(TailoredResume.user_id == user_id).all()
    for t in tailored:
        _delete_stored_file(getattr(t, "docx_url", None))
        _delete_stored_file(getattr(t, "pdf_url", None))
    count = db.query(TailoredResume).filter(TailoredResume.user_id == user_id).delete()
    summary["tailored_resumes"] = count
    
    # ── 4. Matches ──
    count = db.query(Match).filter(Match.user_id == user_id).delete()
    summary["matches"] = count
    
    # ── 5. Candidate trust ──
    count = db.query(CandidateTrust).filter(CandidateTrust.user_id == user_id).delete()
    summary["candidate_trust"] = count
    
    # ── 6. Candidate profiles ──
    count = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).delete()
    summary["candidate_profiles"] = count
    
    # ── 7. Resume documents (delete files first, then DB records) ──
    resumes = db.query(ResumeDocument).filter(ResumeDocument.user_id == user_id).all()
    for r in resumes:
        file_path = getattr(r, "file_path", None) or getattr(r, "original_file_url", None)
        _delete_stored_file(file_path)
    count = db.query(ResumeDocument).filter(ResumeDocument.user_id == user_id).delete()
    summary["resume_documents"] = count
    
    # ── 8. User record (delete last) ──
    count = db.query(User).filter(User.id == user_id).delete()
    summary["users"] = count
    
    # Commit all deletions in one transaction
    db.commit()
    
    logger.info(f"Deleted account for user_id={user_id}: {summary}")
    return summary


def _delete_stored_file(file_path: str | None):
    """Delete a file from local storage or GCS."""
    if not file_path:
        return
    
    # Local file
    if os.path.isfile(file_path):
        try:
            os.remove(file_path)
            logger.info(f"Deleted local file: {file_path}")
        except OSError as e:
            logger.warning(f"Failed to delete local file {file_path}: {e}")
        return
    
    # GCS file
    if file_path.startswith("gs://") or "storage.googleapis.com" in file_path:
        try:
            from google.cloud import storage
            bucket_name = os.environ.get("GCS_BUCKET", "winnow-resumes")
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob_name = file_path.split(f"{bucket_name}/")[-1] if bucket_name in file_path else file_path
            blob = bucket.blob(blob_name)
            blob.delete()
            logger.info(f"Deleted GCS file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete GCS file {file_path}: {e}")
```

---

### Part 3: API Router

**File to create:** `services/api/app/routers/account.py` (NEW)

```python
"""
Account management endpoints: data export and account deletion.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/export")
async def export_data(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Export all user data as a ZIP file download.
    
    Returns a ZIP containing: profile JSON (all versions), account info,
    trust status, match history, application tracking, uploaded resume files,
    and generated tailored resume DOCX files.
    """
    from app.services.data_export import export_user_data
    
    zip_buffer = export_user_data(user.id, db)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=winnow-export-{user.id}.zip"
        },
    )


@router.post("/delete")
async def delete_account(
    confirmation: dict,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Permanently delete user account and all associated data.
    
    Requires confirmation body: { "confirm": "DELETE MY ACCOUNT" }
    
    This action is IRREVERSIBLE. All data including uploaded resumes,
    generated tailored resumes, match history, profile, and tracking
    data will be permanently deleted.
    """
    from app.services.account_deletion import delete_user_account
    from app.services.auth import clear_auth_cookie
    from fastapi.responses import JSONResponse
    
    # Require explicit confirmation string
    confirm_text = confirmation.get("confirm", "")
    if confirm_text != "DELETE MY ACCOUNT":
        raise HTTPException(
            status_code=400,
            detail="To delete your account, send: {\"confirm\": \"DELETE MY ACCOUNT\"}"
        )
    
    # Perform deletion
    summary = delete_user_account(user.id, db)
    
    # Clear auth cookie and return success
    response = JSONResponse(
        content={
            "status": "deleted",
            "message": "Your account and all associated data have been permanently deleted.",
            "summary": summary,
        }
    )
    clear_auth_cookie(response)
    
    return response


@router.get("/export/preview")
async def export_preview(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Preview what data will be included in the export.
    Returns counts of records per category without generating the ZIP.
    """
    from app.models.candidate_profile import CandidateProfile
    from app.models.candidate_trust import CandidateTrust
    from app.models.resume_document import ResumeDocument
    from app.models.match import Match
    from app.models.tailored_resume import TailoredResume
    
    preview = {
        "profile_versions": db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).count(),
        "resume_documents": db.query(ResumeDocument).filter(ResumeDocument.user_id == user.id).count(),
        "matches": db.query(Match).filter(Match.user_id == user.id).count(),
        "tailored_resumes": db.query(TailoredResume).filter(TailoredResume.user_id == user.id).count(),
        "has_trust_record": db.query(CandidateTrust).filter(CandidateTrust.user_id == user.id).count() > 0,
    }
    
    # Application tracking (if model exists)
    try:
        from app.models.application_tracking import ApplicationTracking
        preview["applications"] = db.query(ApplicationTracking).filter(ApplicationTracking.user_id == user.id).count()
    except ImportError:
        preview["applications"] = 0
    
    return preview
```

---

### Part 4: Register the Router

**File to modify:** `services/api/app/main.py`

Add the import and registration for the new account router:

```python
from app.routers import account

# In the router registration section (near the other app.include_router calls):
app.include_router(account.router)
```

---

### Part 5: Request/Response Schemas

**File to create:** `services/api/app/schemas/account.py` (NEW)

```python
"""Pydantic schemas for account management endpoints."""
from pydantic import BaseModel


class DeleteAccountRequest(BaseModel):
    confirm: str  # Must be "DELETE MY ACCOUNT"


class ExportPreviewResponse(BaseModel):
    profile_versions: int
    resume_documents: int
    matches: int
    tailored_resumes: int
    applications: int
    has_trust_record: bool


class DeleteAccountResponse(BaseModel):
    status: str
    message: str
    summary: dict
```

Optionally, update the router to use these schemas for request/response typing. The basic `dict` approach in Part 3 works fine for MVP, but typed schemas improve OpenAPI docs.

---

### Part 6: Frontend — Settings Page

**File to create:** `apps/web/app/settings/page.tsx` (NEW)

Create a Settings page with two sections: "Export My Data" and "Delete My Account".

#### 6.1 Page layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  ⚙️ Account Settings                                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  📦 Export My Data                                                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Download a ZIP file containing all your Winnow data:      │    │
│  │  • Profile (all versions)                                   │    │
│  │  • Uploaded resumes                                         │    │
│  │  • Generated tailored resumes                               │    │
│  │  • Match history and scores                                 │    │
│  │  • Application tracking history                             │    │
│  │  • Trust and consent records                                │    │
│  │                                                             │    │
│  │  Your data: 3 profile versions, 2 resumes, 47 matches,     │    │
│  │  5 tailored resumes, 12 applications                        │    │
│  │                                                             │    │
│  │  [ Download My Data ]                                       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ──────────────────────────────────────────────────────────────     │
│                                                                     │
│  🗑️ Delete My Account                                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  ⚠️ This action is permanent and cannot be undone.          │    │
│  │                                                             │    │
│  │  Deleting your account will permanently remove:             │    │
│  │  • Your profile and all versions                            │    │
│  │  • All uploaded resume files                                │    │
│  │  • All generated tailored resumes                           │    │
│  │  • Your match history and scores                            │    │
│  │  • Application tracking data                                │    │
│  │  • Your login credentials                                   │    │
│  │                                                             │    │
│  │  We recommend downloading your data first.                  │    │
│  │                                                             │    │
│  │  Type "DELETE MY ACCOUNT" to confirm:                       │    │
│  │  ┌─────────────────────────────────┐                        │    │
│  │  │                                 │                        │    │
│  │  └─────────────────────────────────┘                        │    │
│  │                                                             │    │
│  │  [ Delete My Account ]  (red, disabled until text matches)  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### 6.2 Component behavior

**Export section:**
1. On page load, call `GET /api/account/export/preview` to show data counts.
2. When "Download My Data" is clicked, call `GET /api/account/export` — this triggers a file download (the response is a ZIP).
3. Show a loading spinner while the ZIP is being generated.
4. On success, browser downloads the file automatically.

**Delete section:**
1. Show a warning with a red border or red background.
2. Require the user to type `DELETE MY ACCOUNT` exactly into a text input.
3. The "Delete My Account" button is **disabled** until the input matches exactly.
4. When clicked, show a final confirmation dialog: "Are you absolutely sure? This cannot be undone."
5. If confirmed, call `POST /api/account/delete` with body `{ "confirm": "DELETE MY ACCOUNT" }`.
6. On success (200), clear local state and redirect to the landing page (`/`).
7. On error, show the error message.

#### 6.3 API calls from the frontend

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL;

// Preview export (page load)
const previewResponse = await fetch(`${API_BASE}/api/account/export/preview`, {
  credentials: "include",
});
const preview = await previewResponse.json();

// Download export
const exportResponse = await fetch(`${API_BASE}/api/account/export`, {
  credentials: "include",
});
const blob = await exportResponse.blob();
const url = window.URL.createObjectURL(blob);
const a = document.createElement("a");
a.href = url;
a.download = "winnow-export.zip";
document.body.appendChild(a);
a.click();
a.remove();
window.URL.revokeObjectURL(url);

// Delete account
const deleteResponse = await fetch(`${API_BASE}/api/account/delete`, {
  method: "POST",
  credentials: "include",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ confirm: "DELETE MY ACCOUNT" }),
});
if (deleteResponse.ok) {
  // Redirect to landing page
  window.location.href = "/";
}
```

---

### Part 7: Add Navigation Link to Settings

**File to modify:** The main navigation component (likely `apps/web/app/components/Navbar.tsx` or the dashboard layout `apps/web/app/dashboard/layout.tsx` or sidebar).

Add a "Settings" link that navigates to `/settings`. Place it in the user menu, profile dropdown, or sidebar — wherever the existing navigation links live.

Look for the existing navigation structure and add:

```tsx
<Link href="/settings">⚙️ Settings</Link>
```

Or if there's a user dropdown/menu:

```tsx
<DropdownItem>
  <Link href="/settings">Account Settings</Link>
</DropdownItem>
```

---

### Part 8: Tests

**File to create:** `services/api/tests/test_account.py` (NEW)

```python
"""Tests for data export and account deletion."""


def test_export_preview_authenticated(auth_client):
    client, user = auth_client
    response = client.get("/api/account/export/preview")
    assert response.status_code == 200
    data = response.json()
    assert "profile_versions" in data
    assert "resume_documents" in data
    assert "matches" in data
    assert "tailored_resumes" in data
    assert "applications" in data


def test_export_preview_unauthenticated(client):
    response = client.get("/api/account/export/preview")
    assert response.status_code == 401


def test_export_data_returns_zip(auth_client):
    client, user = auth_client
    response = client.get("/api/account/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "winnow-export" in response.headers.get("content-disposition", "")


def test_export_data_unauthenticated(client):
    response = client.get("/api/account/export")
    assert response.status_code == 401


def test_delete_account_requires_confirmation(auth_client):
    client, user = auth_client
    # Missing confirmation
    response = client.post("/api/account/delete", json={"confirm": "wrong"})
    assert response.status_code == 400


def test_delete_account_wrong_confirmation(auth_client):
    client, user = auth_client
    response = client.post("/api/account/delete", json={"confirm": "delete"})
    assert response.status_code == 400


def test_delete_account_success(auth_client, db_session):
    client, user = auth_client
    user_id = user.id
    
    # Delete account
    response = client.post(
        "/api/account/delete",
        json={"confirm": "DELETE MY ACCOUNT"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "deleted"
    assert "summary" in data
    
    # Verify user is gone
    from app.models.user import User
    assert db_session.query(User).filter(User.id == user_id).first() is None


def test_delete_account_unauthenticated(client):
    response = client.post(
        "/api/account/delete",
        json={"confirm": "DELETE MY ACCOUNT"}
    )
    assert response.status_code == 401


def test_delete_cascades_all_data(auth_client, db_session):
    """Verify that deletion removes data from all related tables."""
    client, user = auth_client
    user_id = user.id
    
    # Create some test data first
    from tests.helpers import create_test_profile, create_test_job, create_test_match
    create_test_profile(db_session, user_id)
    job = create_test_job(db_session)
    create_test_match(db_session, user_id, job.id)
    
    # Delete account
    response = client.post(
        "/api/account/delete",
        json={"confirm": "DELETE MY ACCOUNT"}
    )
    assert response.status_code == 200
    
    # Verify all related data is gone
    from app.models.candidate_profile import CandidateProfile
    from app.models.match import Match
    assert db_session.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).count() == 0
    assert db_session.query(Match).filter(Match.user_id == user_id).count() == 0
```

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Data export service | `services/api/app/services/data_export.py` | CREATE |
| Account deletion service | `services/api/app/services/account_deletion.py` | CREATE |
| Account router | `services/api/app/routers/account.py` | CREATE |
| Account schemas | `services/api/app/schemas/account.py` | CREATE |
| Main app (register router) | `services/api/app/main.py` | MODIFY — add `app.include_router(account.router)` |
| Settings page | `apps/web/app/settings/page.tsx` | CREATE |
| Navigation (add Settings link) | `apps/web/app/components/` or layout file | MODIFY — add link to `/settings` |
| Tests | `services/api/tests/test_account.py` | CREATE |

---

## Implementation Order (for a beginner following in Cursor)

### Phase 1: Backend Services (Steps 1–4)

1. **Step 1:** Create `services/api/app/services/data_export.py` — copy the implementation from Part 1. This is the export logic.
2. **Step 2:** Create `services/api/app/services/account_deletion.py` — copy the implementation from Part 2. This is the cascade-delete logic.
3. **Step 3:** Create `services/api/app/routers/account.py` — copy the implementation from Part 3. This has the three endpoints.
4. **Step 4:** Open `services/api/app/main.py`. Find the section where other routers are imported and registered. Add:
   ```python
   from app.routers import account
   app.include_router(account.router)
   ```

### Phase 2: Test Backend (Steps 5–7)

5. **Step 5:** Start the API locally:
   ```powershell
   cd services/api
   .\.venv\Scripts\Activate.ps1
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
6. **Step 6:** Test the export preview in your browser or with curl:
   ```powershell
   # First log in via the web UI to get a session cookie, then:
   curl -b "rm_session=YOUR_TOKEN" http://localhost:8000/api/account/export/preview
   ```
7. **Step 7:** Test the export download:
   ```powershell
   curl -b "rm_session=YOUR_TOKEN" http://localhost:8000/api/account/export -o export.zip
   # Unzip and verify the contents
   ```

### Phase 3: Frontend (Steps 8–10)

8. **Step 8:** Create `apps/web/app/settings/page.tsx` with the two-section layout (Export + Delete). Wire up the API calls from Part 6.
9. **Step 9:** Add a "Settings" navigation link (Part 7). Find the existing nav component and add the link.
10. **Step 10:** Test the frontend:
    - Navigate to `/settings`
    - Verify the export preview loads with correct counts
    - Click "Download My Data" — ZIP should download
    - Open the ZIP — verify it contains profile.json, matches.json, etc.
    - Type "DELETE MY ACCOUNT" — button should enable
    - (Test deletion with a throwaway test account, not your main account)

### Phase 4: Tests (Step 11)

11. **Step 11:** Create `services/api/tests/test_account.py`. Run tests:
    ```powershell
    cd services/api
    .\.venv\Scripts\Activate.ps1
    python -m pytest tests/test_account.py -v
    ```

### Phase 5: Lint (Step 12)

12. **Step 12:** Lint and format:
    ```powershell
    cd services/api
    python -m ruff check .
    python -m ruff format .
    cd ../../apps/web
    npm run lint
    ```

---

## Security Considerations

- **Export:** Only exports data for the currently authenticated user. No admin can export another user's data via this endpoint (admin tools are separate).
- **Deletion:** Requires exact confirmation string `"DELETE MY ACCOUNT"` to prevent accidental clicks. The auth cookie is cleared immediately after deletion.
- **Timing:** Export is synchronous (the ZIP is generated in-memory during the request). For users with very large datasets (hundreds of tailored resumes), consider making this async with a background job that generates the ZIP and sends a download link. For MVP, synchronous is fine.
- **File deletion:** Files are deleted from local storage and GCS. If a file fails to delete, the DB records are still removed and the failure is logged (best-effort file cleanup).
- **No soft delete:** Per SPEC §5, this is a permanent, hard delete. There is no "undo" and no trash/archive period. The user is warned clearly.
- **Audit:** The deletion itself is logged before the audit log is deleted. Consider logging the deletion event to an external service (e.g., structured logging to Cloud Logging) for compliance purposes, since the in-DB audit log is deleted with the account.

---

## Non-Goals (Do NOT implement in this prompt)

- Admin ability to delete other users' accounts (separate admin feature)
- Soft delete / account deactivation (SPEC requires permanent delete)
- Scheduled/delayed deletion (e.g., "delete in 30 days") — future consideration
- Email notification before deletion (future)
- Data portability to other platforms (beyond ZIP export)
- Right to rectification endpoint (users already have PUT /api/profile)

---

## Summary Checklist

- [ ] Data export service: `data_export.py` created with full ZIP generation
- [ ] Export includes: account info, profile (all versions), trust, matches, applications, tailored resumes, audit log
- [ ] Export includes: actual resume files (PDF/DOCX from local or GCS)
- [ ] Export includes: actual tailored resume DOCX files
- [ ] Account deletion service: `account_deletion.py` with correct FK deletion order
- [ ] Deletion removes: all 8 tables in correct order (audit → tracking → tailored → matches → trust → profiles → resumes → user)
- [ ] Deletion removes: stored files from local storage and GCS
- [ ] API router: `GET /api/account/export` returns ZIP download
- [ ] API router: `GET /api/account/export/preview` returns record counts
- [ ] API router: `POST /api/account/delete` with confirmation guard
- [ ] Router registered in `main.py`
- [ ] Frontend: Settings page at `/settings` with Export and Delete sections
- [ ] Frontend: Export shows preview counts + download button
- [ ] Frontend: Delete requires typing "DELETE MY ACCOUNT" + confirmation dialog
- [ ] Frontend: After deletion, cookie cleared + redirect to landing page
- [ ] Navigation: Settings link added to nav/sidebar/menu
- [ ] Tests: export preview, export download, delete confirmation guard, delete success, delete cascade, unauthenticated guards
- [ ] Linted and formatted

Return code changes only.
