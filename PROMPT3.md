# Prompt 3 — Resume upload (MVP stub)

Read SPEC.md and ARCHITECTURE.md.

Implement in services/api:
- POST /api/resume/upload that accepts multipart file upload (PDF/DOCX)
- Save the file to a local folder for dev only, e.g. services/api/data/uploads
- Create a ResumeDocument table (id, user_id nullable for now, filename, path, created_at)
- Return JSON with resume_document_id and filename
- Add GET /api/resume/{id} that returns metadata only (not file content)
- Add Alembic migration for the ResumeDocument table

In apps/web:
- Add a simple Upload page with file picker that calls the upload endpoint
- Show upload success with returned id and filename

Rules:
- No auth yet; user_id nullable.
- Basic validation: allowed extensions (pdf, docx) and size limit.
- Keep it minimal and working on Windows.

Return code changes only.
