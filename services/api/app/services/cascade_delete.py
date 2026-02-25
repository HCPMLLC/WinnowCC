"""Cascade-delete a user and all associated data."""

from datetime import datetime, timezone

from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import Session

from app.services.storage import delete_file as delete_stored_file

from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.candidate_trust import CandidateTrust
from app.models.job_run import JobRun
from app.models.match import Match
from app.models.resume_document import ResumeDocument
from app.models.tailored_resume import TailoredResume
from app.models.trust_audit_log import TrustAuditLog
from app.models.user import User


def _delete_employer_data(session: Session, user_id: int) -> None:
    """Delete all employer-related data for a user (raw SQL for safety)."""
    # Find employer profile ID for this user
    row = session.execute(
        text("SELECT id FROM employer_profiles WHERE user_id = :uid"),
        {"uid": user_id},
    ).first()
    if row is None:
        return
    ep_id = row[0]

    # Collect employer_job IDs
    job_ids = [
        r[0]
        for r in session.execute(
            text("SELECT id FROM employer_jobs WHERE employer_id = :eid"),
            {"eid": ep_id},
        ).all()
    ]

    if job_ids:
        # Great-grandchildren: distribution_events -> job_distributions
        session.execute(
            text(
                "DELETE FROM distribution_events "
                "WHERE distribution_id IN ("
                "  SELECT id FROM job_distributions WHERE employer_job_id = ANY(:jids)"
                ")"
            ),
            {"jids": job_ids},
        )
        # Grandchildren of employer_jobs
        for tbl in [
            "job_distributions",
            "employer_job_candidates",
            "interview_feedback",
            "employer_introduction_requests",
        ]:
            session.execute(
                text(f"DELETE FROM {tbl} WHERE employer_job_id = ANY(:jids)"),
                {"jids": job_ids},
            )

    # Direct children of employer_profiles
    for tbl in [
        "employer_jobs",
        "employer_team_members",
        "employer_candidate_views",
        "employer_saved_candidates",
        "employer_compliance_log",
        "talent_pipeline",
    ]:
        session.execute(
            text(f"DELETE FROM {tbl} WHERE employer_id = :eid"),
            {"eid": ep_id},
        )

    # Board connections (need to clean distributions first, already done above)
    session.execute(
        text("DELETE FROM board_connections WHERE employer_id = :eid"),
        {"eid": ep_id},
    )

    # Employer profile itself
    session.execute(
        text("DELETE FROM employer_profiles WHERE id = :eid"),
        {"eid": ep_id},
    )


def _delete_recruiter_data(session: Session, user_id: int) -> None:
    """Delete all recruiter-related data for a user (raw SQL for safety)."""
    row = session.execute(
        text("SELECT id FROM recruiter_profiles WHERE user_id = :uid"),
        {"uid": user_id},
    ).first()
    if row is None:
        return
    rp_id = row[0]

    # Collect recruiter_job IDs
    job_ids = [
        r[0]
        for r in session.execute(
            text("SELECT id FROM recruiter_jobs WHERE recruiter_profile_id = :rid"),
            {"rid": rp_id},
        ).all()
    ]

    if job_ids:
        # Grandchildren of recruiter_jobs
        session.execute(
            text(
                "DELETE FROM recruiter_job_candidates "
                "WHERE recruiter_job_id = ANY(:jids)"
            ),
            {"jids": job_ids},
        )

    # Outreach enrollments (FK to sequences, pipeline_candidates, and recruiter_profiles)
    session.execute(
        text("DELETE FROM outreach_enrollments WHERE recruiter_profile_id = :rid"),
        {"rid": rp_id},
    )

    # Outreach sequences
    session.execute(
        text("DELETE FROM outreach_sequences WHERE recruiter_profile_id = :rid"),
        {"rid": rp_id},
    )

    # Recruiter activities
    session.execute(
        text("DELETE FROM recruiter_activities WHERE recruiter_profile_id = :rid"),
        {"rid": rp_id},
    )

    # Pipeline candidates
    session.execute(
        text(
            "DELETE FROM recruiter_pipeline_candidates "
            "WHERE recruiter_profile_id = :rid"
        ),
        {"rid": rp_id},
    )

    # Introduction requests
    session.execute(
        text("DELETE FROM introduction_requests WHERE recruiter_profile_id = :rid"),
        {"rid": rp_id},
    )

    # Recruiter jobs
    session.execute(
        text("DELETE FROM recruiter_jobs WHERE recruiter_profile_id = :rid"),
        {"rid": rp_id},
    )

    # Recruiter clients
    session.execute(
        text("DELETE FROM recruiter_clients WHERE recruiter_profile_id = :rid"),
        {"rid": rp_id},
    )

    # Team members
    session.execute(
        text("DELETE FROM recruiter_team_members WHERE recruiter_profile_id = :rid"),
        {"rid": rp_id},
    )

    # Recruiter profile itself
    session.execute(
        text("DELETE FROM recruiter_profiles WHERE id = :rid"),
        {"rid": rp_id},
    )


def cascade_delete_user(session: Session, user_id: int) -> bool:
    """Delete a user and all associated data. Returns True if user existed."""
    user = session.get(User, user_id)
    if user is None:
        return False

    # 0. MJASS tables (raw SQL — no ORM models)
    session.execute(
        text(
            "DELETE FROM mjass_application_events "
            "WHERE draft_id IN ("
            "  SELECT id FROM mjass_application_drafts WHERE user_id = :uid"
            ")"
        ),
        {"uid": user_id},
    )
    session.execute(
        text("DELETE FROM mjass_application_drafts WHERE user_id = :uid"),
        {"uid": user_id},
    )

    # 1. Onboarding v1 tables (raw SQL, no ORM models)
    session.execute(text("DELETE FROM consents WHERE user_id = :uid"), {"uid": user_id})
    session.execute(
        text("DELETE FROM candidate_preferences_v1 WHERE user_id = :uid"),
        {"uid": user_id},
    )
    session.execute(
        text("DELETE FROM onboarding_state WHERE user_id = :uid"),
        {"uid": user_id},
    )

    # 2. Tailored resumes — delete physical files first, then DB rows
    tailored = (
        session.execute(select(TailoredResume).where(TailoredResume.user_id == user_id))
        .scalars()
        .all()
    )
    for tr in tailored:
        for url_field in [tr.docx_url, tr.cover_letter_url]:
            if url_field:
                delete_stored_file(url_field)
    session.execute(delete(TailoredResume).where(TailoredResume.user_id == user_id))

    # 3. Matches
    session.execute(delete(Match).where(Match.user_id == user_id))

    # 4. Resume-related data
    resume_docs = (
        session.execute(select(ResumeDocument).where(ResumeDocument.user_id == user_id))
        .scalars()
        .all()
    )
    for doc in resume_docs:
        # Parsed resume documents (children cascade via FK)
        session.execute(
            text("DELETE FROM parsed_resume_documents WHERE resume_document_id = :did"),
            {"did": doc.id},
        )
        # Job runs
        session.execute(delete(JobRun).where(JobRun.resume_document_id == doc.id))
        # Trust audit log + trust record
        trust = session.execute(
            select(CandidateTrust).where(CandidateTrust.resume_document_id == doc.id)
        ).scalar_one_or_none()
        if trust:
            session.execute(
                delete(TrustAuditLog).where(TrustAuditLog.trust_id == trust.id)
            )
            session.execute(delete(CandidateTrust).where(CandidateTrust.id == trust.id))

    # 5. Candidate profiles
    session.execute(delete(CandidateProfile).where(CandidateProfile.user_id == user_id))

    # 6. Resume documents — soft-delete (physical files retained for recovery)
    session.execute(
        update(ResumeDocument)
        .where(ResumeDocument.user_id == user_id)
        .where(ResumeDocument.deleted_at.is_(None))
        .values(deleted_at=datetime.now(timezone.utc))
    )

    # 7. Candidate (onboarding data)
    session.execute(delete(Candidate).where(Candidate.user_id == user_id))

    # 8. Employer data (all employer tables + children)
    _delete_employer_data(session, user_id)

    # 9. Recruiter data (all recruiter tables + children)
    _delete_recruiter_data(session, user_id)

    # 10. Shared multi-segment tables
    session.execute(
        text("DELETE FROM sieve_conversations WHERE user_id = :uid"),
        {"uid": user_id},
    )
    session.execute(
        text("DELETE FROM daily_usage_counters WHERE user_id = :uid"),
        {"uid": user_id},
    )

    # 11. User
    session.delete(user)

    return True
