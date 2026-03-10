# Architecture: Prime/Sub Recruiter Relationships & Cross-Segment Trust

## Problem Statement

Government contracting recruitment operates in a chain: **Client (employer)** → **Prime Contractor (recruiter)** → **Subcontractor (recruiter)**. Subs source candidates and submit them to Primes. Primes collect submissions from multiple Subs, pick the best candidate, and submit to the Client.

Today, HCPM operates as a Sub. Contacts migrated from Recruit CRM include Primes and other Subs. Over time:
- A Prime contact may sign up as a Winnow Recruiter
- A Sub contact may sign up as a Winnow Recruiter
- A pipeline candidate may sign up as a Winnow Candidate
- A user may shift segments (Sub becomes Prime, recruiter becomes employer, etc.)

The system must support these transitions without breaking data isolation or trust boundaries.

---

## Real-World Relationship Chain

```
Client Company (Employer)
  e.g. Texas DIR, Alcoholic Beverage Commission
        │
        │ posts jobs, receives final candidate submissions
        ▼
Prime Contractor (Recruiter)
  e.g. Accenture Federal, CACI
        │
        │ manages job pipeline, collects candidates from Subs
        │ selects best candidate, submits to Client
        ▼
Subcontractor (Recruiter)
  e.g. HCPM
        │
        │ sources candidates, submits to Prime
        ▼
Candidates
  e.g. John Smith (Microbiologist)
```

**Key insight**: A Prime is a recruiter *to* the Client, but acts like an *employer* from the Sub's perspective. The same entity can be both, depending on which direction you look.

---

## What Already Exists

| Mechanism | Status | How It Works |
|-----------|--------|-------------|
| **RecruiterClient hierarchy** | Built | `parent_client_id` self-FK, tree view on clients page |
| **RecruiterJob to EmployerJob link** | Built | `employer_job_id` FK, auto-link by `job_id_external`, manual link endpoint |
| **CandidateSubmission** | Built | Cross-segment bridge: recruiter submits candidate to employer job |
| **RecruiterPipelineCandidate** | Built | Tracks both platform candidates (`candidate_profile_id`) and external candidates (`external_*` fields) |
| **User role = "both"** | Partial | Exists in DB, admin-only, no UI onboarding. Allows access to both employer + recruiter endpoints |
| **Trust system** | Built | Candidate-only (resume scoring), gates match visibility |
| **Notification system** | Built | `RecruiterNotification` model, notification endpoints |
| **Contact roles** | Built | JSONB contacts with roles: Purchaser, Hiring Manager, Prime Contractor, Subcontractor |

---

## Design Principles

### 1. Data ownership stays with the creator
- A recruiter's jobs, clients, and pipeline candidates belong to that recruiter
- No one else can see or modify them unless explicitly shared
- Cross-segment visibility happens only through defined bridge records (submissions, job links)

### 2. Contacts are not Accounts
- A contact in your CRM is just metadata (name, email, role)
- If that person signs up on Winnow, they get their own independent account
- The system can *notify* you and *suggest* a link, but never auto-merges data

### 3. Bridge records create controlled visibility
- `CandidateSubmission` = Sub shares a candidate with a Prime (or Prime shares with Client)
- `RecruiterJob.employer_job_id` = Recruiter's copy of a job links to the canonical employer posting
- Future: `RecruiterJob.upstream_recruiter_id` = Sub's job links to Prime's job (same pattern)

### 4. Roles are additive, not exclusive
- A user can be "both" (employer + recruiter) without losing data from either segment
- A Prime who is also a Winnow employer sees both dashboards
- Role transitions preserve all existing data

---

## Current Data Model

```
User (email, role: candidate|employer|recruiter|both|admin)
  |-- CandidateProfile (if candidate/both)
  |-- EmployerProfile (if employer/both)
  |     +-- EmployerJob (jobs posted as employer)
  +-- RecruiterProfile (if recruiter/both)
        |-- RecruiterClient (CRM companies, with parent/child hierarchy)
        |     +-- contacts[] (JSONB: name, email, phone, role)
        |-- RecruiterJob (jobs tracked by recruiter)
        |     |-- client_id -> RecruiterClient
        |     |-- employer_job_id -> EmployerJob (cross-segment link)
        |     +-- primary_contact (JSONB: name, email, role)
        |-- RecruiterPipelineCandidate
        |     +-- candidate_profile_id -> CandidateProfile (optional)
        +-- CandidateSubmission (bridge to employer jobs)
```

---

## Phased Buildout

### Phase 1: Client Detail Job Summary (immediate)
No model changes. Frontend + 1 new API endpoint.

- `GET /api/recruiter/clients/{id}/job-summary` returns jobs for this client + children, grouped by child client + status, and by primary contact + close date
- New section on client detail page with two tab views

### Phase 2: Contact-Account Recognition (near-term)
No model changes. Notification-only.

When a new user signs up whose email matches a contact in any `RecruiterClient.contacts`:
- Create a `RecruiterNotification` for the owning recruiter
- Log a `RecruiterActivity` on the matching client
- No auto-linking, no shared data. Just awareness.

Similarly for pipeline candidates who sign up.

### Phase 3: Prime-Sub Job Linking (future)
Model addition: Add `upstream_recruiter_job_id` to `RecruiterJob`.

Mirrors the existing `employer_job_id` pattern but for recruiter-to-recruiter. Requires a sharing/invitation mechanism.

### Phase 4: Role Transitions (future)
Self-service role upgrade UI. The existing "both" role and admin endpoint already support this at the data level.

---

## Trust Boundaries

| Scenario | What Happens | Trust Rule |
|----------|-------------|------------|
| Sub creates a job for a Prime's client | Sub owns the job. Prime can't see it. | Data stays with creator |
| Prime signs up on Winnow | Gets own account. Sub gets notified. | Contacts are not Accounts |
| Sub submits candidate to Prime | CandidateSubmission bridge created. Prime sees the submission. | Explicit sharing via bridge |
| Candidate in pipeline signs up | Candidate gets own account. Recruiter notified. No auto-link. | Consent required |
| User becomes "both" | Keeps all data. Sees both dashboards. | Roles are additive |
| RecruiterJob linked to EmployerJob | Recruiter can see employer company name. Employer sees submissions. | Bridge = controlled visibility |
