# Data Protection Hardening

## Fixes Implemented

- [x] **Fix 1**: Add `GCS_BUCKET=winnow-resumes-prod` to deploy workflow (API + Worker)
- [x] **Fix 2**: Fix `cascade_delete.py` to use `storage.delete_file` instead of `Path.unlink()`
- [x] **Fix 3**: Add destructive migration safety guard in `alembic/env.py`
- [x] **Fix 4**: Add FK constraint on `candidate_profiles.resume_document_id` with migration
- [x] **Fix 5**: Add soft-delete (`deleted_at`) to `ResumeDocument` with filtering across 16+ query sites
- [ ] **Fix 6**: Run `gsutil versioning set on gs://winnow-resumes-prod` after deployment (ops task)

## Files Modified

### Fix 1
- `.github/workflows/deploy.yml` — Added `GCS_BUCKET=winnow-resumes-prod` to both API (line 58) and Worker (line 123) deploy steps

### Fix 2
- `services/api/app/services/cascade_delete.py` — Replaced `from pathlib import Path` with `from app.services.storage import delete_file`, updated file deletion for tailored resumes and resume documents

### Fix 3
- `services/api/alembic/env.py` — Added `_guard_destructive_migrations()` that blocks `DROP SCHEMA`, `DROP TABLE`, `TRUNCATE` when database has production data. Override with `ALEMBIC_ALLOW_DESTRUCTIVE=1`.

### Fix 4
- `services/api/app/models/candidate_profile.py` — Added `ForeignKey("resume_documents.id", ondelete="SET NULL")`
- `services/api/alembic/versions/20260225_02_add_fk_resume_document_id.py` — New migration: clean orphans + add FK

### Fix 5
- `services/api/app/models/resume_document.py` — Added `deleted_at` column + `active()` classmethod
- `services/api/alembic/versions/20260225_03_add_soft_delete_resume_documents.py` — New migration: add column + partial index
- `services/api/app/services/cascade_delete.py` — Changed hard-delete to soft-delete (SET deleted_at)
- `services/api/app/routers/resume.py` — 4 query sites filtered
- `services/api/app/routers/account.py` — 1 query site filtered
- `services/api/app/routers/admin_candidates.py` — 5 query sites filtered
- `services/api/app/routers/admin_trust.py` — 1 query site filtered (outerjoin condition)
- `services/api/app/routers/admin_support.py` — 5 query sites filtered (includes join conditions)
- `services/api/app/services/data_export.py` — 1 query site filtered
- `services/api/app/services/trust_scoring.py` — 3 query sites filtered
- `services/api/app/services/sieve_chat.py` — 1 query site filtered
- `services/api/app/services/recruiter_llm_reparse.py` — 1 post-fetch check
- `services/api/app/services/resume_parse_job.py` — 1 post-fetch check

---

# MFA OTP Verification — Mobile App

## Summary

Added MFA (OTP verification) support to the Expo mobile app. Previously, MFA-enabled accounts (employers, recruiters, "both" roles) could not log in on mobile — the app threw a generic error. Now the app presents a 6-digit OTP verification screen matching the web app's existing flow.

## Implementation

- [x] Extend `AuthContextType` with `verifyOtp`, `resendOtp`, `mfaPendingEmail`, `cancelMfa`
- [x] Modify `login()` to return `{ requiresMfa: boolean }` instead of throwing on MFA
- [x] Add MFA state (`mfaPendingEmail`, `mfaPendingPassword`) and callbacks to root layout
- [x] Register `verify-otp` screen in auth stack layout
- [x] Update login screen to navigate to OTP screen when MFA required
- [x] Create `verify-otp.tsx` screen (6-digit input, verify, resend, back to sign in)

## Files Modified

| File | Change |
|------|--------|
| `apps/mobile/lib/auth.ts` | Extended `AuthContextType` interface with MFA methods and fields |
| `apps/mobile/app/_layout.tsx` | Added MFA state, `verifyOtp`/`resendOtp`/`cancelMfa` callbacks, updated provider |
| `apps/mobile/app/(auth)/_layout.tsx` | Registered `verify-otp` screen in auth stack |
| `apps/mobile/app/(auth)/login.tsx` | Added `useRouter`, check `login()` return for MFA navigation |
| `apps/mobile/app/(auth)/verify-otp.tsx` | **New file** — OTP verification screen |

## Test Results (2026-02-25)

| Test | Result |
|------|--------|
| Metro bundle — root layout (701 modules) | Pass |
| Metro bundle — login screen (630 modules) | Pass |
| Metro bundle — verify-otp screen (672 modules) | Pass |
| MFA login (`rlevi@hcpm.llc`) returns `requires_mfa: true` | Pass |
| verify-otp with wrong code → 401 "Invalid code." | Pass |
| resend-otp → 200 `{"status":"sent"}` | Pass |
| resend-otp with wrong password → 401 "Invalid email or password." | Pass |
| TypeScript `tsc --noEmit` — no new errors (4 pre-existing unrelated) | Pass |

## Commit

- `5cf4b4c` — Add MFA OTP verification flow to mobile app
