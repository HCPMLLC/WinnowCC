# Prompt — TrustScore v1 + Quarantine Gate (MVP, pre-auth)

Read the current codebase carefully before making changes.
This project already has:
- resume upload
- background parsing jobs (RQ + Redis)
- versioned candidate profiles
- a profile UI

Your task is to implement an explainable, deterministic **TrustScore v1** system
that flags potentially fraudulent or low-confidence candidates and quarantines
them from marketplace actions.

There is NO login/auth yet. Key everything to the **latest resume/profile**.

Return code changes only.

---

## Goals

1. Assign a trust_score (0–100) to each candidate
2. Derive a trust_status:
   - allowed
   - soft_quarantine
   - hard_quarantine
3. Persist trust data and an audit log
4. Show a quarantine banner ONLY to the candidate
5. Provide admin-only visibility + override
6. Gate future “marketplace” actions (stub endpoint)

Never accuse the user of fraud. Messaging must be neutral:
“Verification required before matching.”

---

## Data Model (services/api)

### 1) candidate_trust table (Alembic migration required)

Keyed by **resume_document_id** (unique).

Fields:
- id (PK)
- resume_document_id (FK, unique)
- score (int, 0–100)
- status (enum: allowed | soft_quarantine | hard_quarantine)
- reasons (jsonb array of objects)
- user_message (text)
- internal_notes (text, admin-only)
- updated_at (timestamp)

### 2) trust_audit_log table (append-only)

Fields:
- id (PK)
- trust_id (FK)
- actor_type (enum: system | candidate | admin)
- action (string)
- prev_status
- new_status
- created_at
- metadata (jsonb)

---

## TrustScore v1 Algorithm (deterministic)

Score is additive from capped buckets.

### A) Identity & completeness (0–25)
Using extracted profile_json fields:
- name present (+6)
- email present (+6)
- location present (+6)
- work history present (+7)

Red flags:
- missing name OR no work history (+10)

### B) Resume plausibility (0–20)
- parse succeeded (+5)
- at least 1 job entry (+5)
- no overlapping date ranges (+5)
- no extreme keyword repetition (+5)

Red flags:
- overlapping employment dates (+10–15)
- keyword stuffing heuristic (+10)

### C) Online presence evidence (0–25)
(candidate-provided only; no scraping)
- LinkedIn URL present (+10)
- GitHub / portfolio URL present (+5)
- both present (+10)

Red flags:
- malformed URLs (+5–10)

### D) Abuse & duplication signals (0–30)
- compute sha256 of uploaded resume file
- if same sha256 appears on multiple resume_documents:
  +20–30 (severity increases with count)
- unusually frequent uploads from same profile (+10)

---

## Thresholds

- score < 30 → allowed
- 30–59 → soft_quarantine
- ≥ 60 → hard_quarantine

Set:
- trust_status
- user_message explaining next steps
- reasons[] with {code, severity, message}

---

## Integration Points

### 1) Resume upload
- Compute sha256 of file
- Store sha256 on resume_documents
- Create or update candidate_trust
- Log audit entry (system, action="initial_evaluation")

### 2) After parse job completes
- Recompute TrustScore using parsed profile_json
- Update candidate_trust
- Log audit entry (system, action="recompute_after_parse")

---

## API Endpoints

### Candidate-facing
- GET /api/trust/me
  - returns trust_status, score, user_message
  - resolves to latest resume/profile only

- POST /api/trust/me/request-review
  - creates audit log entry
  - does not change status

### Admin-only (protect with X-Admin-Token == ADMIN_TOKEN env var)
- GET /api/admin/trust/queue
  - list all non-allowed trust records
- POST /api/admin/trust/{trust_id}/set
  - set status, internal_notes
  - append audit log

---

## Gating

Add dependency:
`require_allowed_trust()`

Create stub endpoint:
- POST /api/match/run

Behavior:
- If trust_status != allowed → HTTP 403
- Message: “Account verification required before matching.”

Do NOT block:
- resume upload
- profile view/edit
- trust endpoints

---

## Frontend (apps/web)

### Candidate UI
- On /profile page:
  - fetch GET /api/trust/me
  - if quarantined, show banner:
    “Your account requires verification before job matching.”
  - show “Request review” button

### Admin UI (minimal)
- /admin/trust page
- fetch trust queue using admin token
- allow status change

Trust data must NEVER appear in public endpoints.

---

## Non-goals (do NOT implement)
- Login / authentication
- Payment / subscription
- External verification APIs
- Background checks

---

## Implementation notes
- Keep scoring explainable and deterministic
- All trust changes must be auditable
- Code should be readable and modular
- Add Alembic migrations
- Update README if new env vars are added

Return code changes only.
