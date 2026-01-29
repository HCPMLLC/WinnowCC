# Prompt 4 — Resume parsing → Candidate Profile (v1: deterministic)

Read SPEC.md and ARCHITECTURE.md.

Implement v1 candidate profile extraction WITHOUT calling external LLMs yet.

Backend (services/api):
1) Add CandidateProfile table (id, user_id nullable, version int, profile_json jsonb, updated_at)
2) Add endpoints:
   - POST /api/resume/{resume_id}/parse  -> enqueue a parse job and return job info
   - GET /api/profile -> return latest CandidateProfile profile_json (or default structure)
   - PUT /api/profile -> update profile_json and increment version
3) Implement a background job (using your existing Redis queue setup) that:
   - Loads the uploaded resume from its saved path
   - Extracts text:
     - PDF via pypdf
     - DOCX via python-docx
   - Produces a structured profile_json with keys:
     - basics: { name, email, phone, location } (only if found in text)
     - experience: array of { company, title, start_date, end_date, bullets }
     - education: array of { school, degree, field, start_date, end_date }
     - skills: array of strings (keywords)
     - preferences: { target_titles, locations, remote_ok, job_type, salary_min, salary_max }
   - Saves CandidateProfile with versioning (new row per run) and associates it to resume_document_id (optional field if desired)

Rules:
- Do not guess demographics; only capture what is explicitly present.
- Keep it robust: if extraction fails, store an error status in job_runs and return helpful message.
- Add Alembic migration(s).
- Add basic unit tests for text extraction helpers if you can, but keep minimal.
- Ensure Windows compatibility.

Frontend (apps/web):
1) Create /profile page that:
   - Fetches GET /api/profile
   - Shows extracted experience and skills (read-only display)
   - Allows editing preferences fields and saving via PUT /api/profile
2) Update upload success UI to include a button "Build my profile" that calls POST /api/resume/{id}/parse and shows a simple status message (queued / done polling optional but not required)

Return code changes only.
