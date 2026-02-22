"""Data export service — collects all user data into a downloadable ZIP."""

from __future__ import annotations

import io
import json
import logging
import os
import zipfile
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.candidate_trust import CandidateTrust
from app.models.match import Match
from app.models.resume_document import ResumeDocument
from app.models.tailored_resume import TailoredResume
from app.models.trust_audit_log import TrustAuditLog
from app.models.usage_counter import UsageCounter
from app.models.user import User
from app.services.storage import download_as_bytes

logger = logging.getLogger(__name__)


def _json_default(obj: object) -> str:
    """Fallback serialiser for datetime and other non-JSON types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def _dump(data: object) -> str:
    return json.dumps(data, indent=2, default=_json_default)


def _add_file_to_zip(
    zf: zipfile.ZipFile,
    folder: str,
    archive_path: str,
    source_path: str,
) -> None:
    """Add a file to the ZIP from local disk or GCS."""
    if not source_path:
        return
    data = download_as_bytes(source_path)
    if data:
        zf.writestr(f"{folder}/{archive_path}", data)


def export_user_data(user_id: int, db: Session) -> io.BytesIO:
    """Export all data for a user as an in-memory ZIP file."""
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    folder = f"winnow-export-{user_id}-{ts}"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Account info
        user = db.get(User, user_id)
        if user:
            zf.writestr(
                f"{folder}/account.json",
                _dump(
                    {
                        "user_id": user.id,
                        "email": user.email,
                        "created_at": user.created_at,
                        "updated_at": user.updated_at,
                        "onboarding_completed_at": user.onboarding_completed_at,
                        "is_admin": user.is_admin,
                    }
                ),
            )

        # 2. Candidate (onboarding data)
        cand = db.execute(
            select(Candidate).where(Candidate.user_id == user_id)
        ).scalar_one_or_none()
        if cand:
            zf.writestr(
                f"{folder}/candidate.json",
                _dump(
                    {
                        "first_name": cand.first_name,
                        "last_name": cand.last_name,
                        "phone": cand.phone,
                        "location_city": cand.location_city,
                        "state": cand.state,
                        "country": cand.country,
                        "work_authorization": cand.work_authorization,
                        "years_experience": cand.years_experience,
                        "desired_job_types": cand.desired_job_types,
                        "desired_locations": cand.desired_locations,
                        "desired_salary_min": cand.desired_salary_min,
                        "desired_salary_max": cand.desired_salary_max,
                        "remote_preference": cand.remote_preference,
                        "plan_tier": cand.plan_tier,
                        "created_at": cand.created_at,
                        "updated_at": cand.updated_at,
                    }
                ),
            )

        # 3. Candidate profiles (all versions)
        profiles = (
            db.execute(
                select(CandidateProfile)
                .where(CandidateProfile.user_id == user_id)
                .order_by(CandidateProfile.version.desc())
            )
            .scalars()
            .all()
        )
        if profiles:
            zf.writestr(
                f"{folder}/profile.json",
                _dump(profiles[0].profile_json),
            )
            history = [
                {
                    "version": p.version,
                    "profile_json": p.profile_json,
                    "updated_at": p.updated_at,
                }
                for p in profiles
            ]
            zf.writestr(f"{folder}/profile_history.json", _dump(history))

        # 4. Trust records (via resume_documents)
        resume_docs = (
            db.execute(select(ResumeDocument).where(ResumeDocument.user_id == user_id))
            .scalars()
            .all()
        )
        trust_records = []
        audit_records = []
        for doc in resume_docs:
            trust = db.execute(
                select(CandidateTrust).where(
                    CandidateTrust.resume_document_id == doc.id
                )
            ).scalar_one_or_none()
            if trust:
                trust_records.append(
                    {
                        "resume_document_id": doc.id,
                        "score": trust.score,
                        "status": trust.status,
                        "reasons": trust.reasons,
                        "user_message": trust.user_message,
                        "updated_at": trust.updated_at,
                    }
                )
                audits = (
                    db.execute(
                        select(TrustAuditLog).where(TrustAuditLog.trust_id == trust.id)
                    )
                    .scalars()
                    .all()
                )
                for a in audits:
                    audit_records.append(
                        {
                            "action": a.action,
                            "actor_type": a.actor_type,
                            "prev_status": a.prev_status,
                            "new_status": a.new_status,
                            "details": a.details,
                            "created_at": a.created_at,
                        }
                    )
        if trust_records:
            zf.writestr(f"{folder}/trust.json", _dump(trust_records))
        if audit_records:
            zf.writestr(f"{folder}/audit_log.json", _dump(audit_records))

        # 5. Matches
        matches = (
            db.execute(select(Match).where(Match.user_id == user_id)).scalars().all()
        )
        if matches:
            zf.writestr(
                f"{folder}/matches.json",
                _dump(
                    [
                        {
                            "match_id": m.id,
                            "job_id": m.job_id,
                            "profile_version": m.profile_version,
                            "match_score": m.match_score,
                            "interview_readiness_score": m.interview_readiness_score,
                            "offer_probability": m.offer_probability,
                            "interview_probability": m.interview_probability,
                            "semantic_similarity": m.semantic_similarity,
                            "application_status": m.application_status,
                            "notes": m.notes,
                            "reasons": m.reasons,
                            "created_at": m.created_at,
                        }
                        for m in matches
                    ]
                ),
            )

        # 6. Tailored resumes (metadata + files)
        tailored = (
            db.execute(select(TailoredResume).where(TailoredResume.user_id == user_id))
            .scalars()
            .all()
        )
        if tailored:
            zf.writestr(
                f"{folder}/tailored_resumes.json",
                _dump(
                    [
                        {
                            "id": t.id,
                            "job_id": t.job_id,
                            "profile_version": t.profile_version,
                            "docx_url": t.docx_url,
                            "cover_letter_url": t.cover_letter_url,
                            "change_log": t.change_log,
                            "created_at": t.created_at,
                        }
                        for t in tailored
                    ]
                ),
            )
            for t in tailored:
                if t.docx_url:
                    fname = os.path.basename(t.docx_url)
                    _add_file_to_zip(zf, folder, f"tailored/{fname}", t.docx_url)
                if t.cover_letter_url:
                    fname = os.path.basename(t.cover_letter_url)
                    _add_file_to_zip(
                        zf, folder, f"tailored/{fname}", t.cover_letter_url
                    )

        # 7. Resume documents (metadata + files)
        if resume_docs:
            for r in resume_docs:
                if r.path:
                    _add_file_to_zip(zf, folder, f"resumes/{r.filename}", r.path)

        # 8. Usage counters
        counters = (
            db.execute(select(UsageCounter).where(UsageCounter.user_id == user_id))
            .scalars()
            .all()
        )
        if counters:
            zf.writestr(
                f"{folder}/usage.json",
                _dump(
                    [
                        {
                            "period_start": str(c.period_start),
                            "match_refreshes": c.match_refreshes,
                            "tailor_requests": c.tailor_requests,
                        }
                        for c in counters
                    ]
                ),
            )

    buf.seek(0)
    return buf
