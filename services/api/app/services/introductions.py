"""Introduction request service — consent-gated recruiter-to-candidate contact."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.candidate_profile import CandidateProfile
from app.models.introduction_request import IntroductionRequest
from app.models.recruiter import RecruiterProfile
from app.models.recruiter_job import RecruiterJob
from app.models.user import User
from app.services.billing import (
    check_recruiter_monthly_limit,
    increment_recruiter_counter,
)

logger = logging.getLogger(__name__)

INTRO_EXPIRY_DAYS = 7


def create_introduction_request(
    session: Session,
    recruiter_profile: RecruiterProfile,
    candidate_profile_id: int,
    message: str,
    recruiter_job_id: int | None = None,
) -> IntroductionRequest:
    """Create a new introduction request from recruiter to candidate.

    Validates:
    - Candidate exists and is open to introductions
    - No duplicate pending request
    - Recruiter monthly limit not exceeded
    - Job belongs to this recruiter (if provided)
    """
    # 1. Validate candidate
    cp = session.execute(
        select(CandidateProfile).where(CandidateProfile.id == candidate_profile_id)
    ).scalar_one_or_none()
    if cp is None:
        raise HTTPException(status_code=404, detail="Candidate profile not found.")
    if not cp.open_to_introductions:
        raise HTTPException(
            status_code=400,
            detail="This candidate is not currently accepting introduction requests.",
        )

    # Reject intro requests for recruiter-sourced candidates (LinkedIn, manual, uploaded)
    pj = cp.profile_json or {}
    if pj.get("sourced_by_user_id") or pj.get("source") == "linkedin_extension":
        raise HTTPException(
            status_code=400,
            detail="Introduction requests are only for candidates who registered on the platform.",
        )

    # 2. Check for existing pending request
    existing = session.execute(
        select(IntroductionRequest).where(
            IntroductionRequest.recruiter_profile_id == recruiter_profile.id,
            IntroductionRequest.candidate_profile_id == candidate_profile_id,
            IntroductionRequest.status == "pending",
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="You already have a pending introduction request for this candidate.",
        )

    # 3. Check monthly limit
    check_recruiter_monthly_limit(
        recruiter_profile,
        "intro_requests_used",
        "intro_requests_per_month",
        session,
    )

    # 4. Validate job ownership if provided
    if recruiter_job_id is not None:
        rj = session.execute(
            select(RecruiterJob).where(
                RecruiterJob.id == recruiter_job_id,
                RecruiterJob.recruiter_profile_id == recruiter_profile.id,
            )
        ).scalar_one_or_none()
        if rj is None:
            raise HTTPException(status_code=404, detail="Job not found.")

    # 5. Create request
    now = datetime.now(timezone.utc)
    intro = IntroductionRequest(
        recruiter_profile_id=recruiter_profile.id,
        candidate_profile_id=candidate_profile_id,
        recruiter_job_id=recruiter_job_id,
        message=message,
        status="pending",
        expires_at=now + timedelta(days=INTRO_EXPIRY_DAYS),
    )
    session.add(intro)

    # 6. Increment counter
    increment_recruiter_counter(recruiter_profile, "intro_requests_used", session)

    session.flush()

    # 7. Send notification email (non-blocking, best-effort)
    try:
        _send_intro_request_notification(session, cp, recruiter_profile, recruiter_job_id)
    except Exception:
        logger.exception("Failed to send introduction request email")

    return intro


def respond_to_introduction(
    session: Session,
    candidate_profile_ids: list[int] | int,
    request_id: int,
    action: str,
    response_message: str | None = None,
) -> IntroductionRequest:
    """Accept or decline an introduction request."""
    # Support both a single ID and a list for multi-version profiles
    if isinstance(candidate_profile_ids, int):
        candidate_profile_ids = [candidate_profile_ids]
    intro = session.execute(
        select(IntroductionRequest).where(
            IntroductionRequest.id == request_id,
            IntroductionRequest.candidate_profile_id.in_(candidate_profile_ids),
        )
    ).scalar_one_or_none()
    if intro is None:
        raise HTTPException(status_code=404, detail="Introduction request not found.")
    if intro.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot respond to a request with status '{intro.status}'.",
        )

    now = datetime.now(timezone.utc)

    if action == "accept":
        intro.status = "accepted"
        intro.responded_at = now
        intro.candidate_response_message = response_message
        session.flush()

        # Send acceptance email to recruiter with revealed candidate info
        try:
            _send_intro_accepted_notification(session, intro)
        except Exception:
            logger.exception("Failed to send introduction accepted email")

        # Log activity
        try:
            _log_activity(session, intro, "introduction_accepted")
        except Exception:
            logger.exception("Failed to log introduction activity")

    elif action == "decline":
        intro.status = "declined"
        intro.responded_at = now
        intro.candidate_response_message = response_message
        session.flush()
    else:
        raise HTTPException(status_code=400, detail="Action must be 'accept' or 'decline'.")

    return intro


def get_recruiter_introductions(
    session: Session,
    recruiter_profile_id: int,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List introduction requests sent by this recruiter, enriched with candidate info."""
    q = select(IntroductionRequest).where(
        IntroductionRequest.recruiter_profile_id == recruiter_profile_id,
    )
    if status_filter:
        q = q.where(IntroductionRequest.status == status_filter)
    q = q.order_by(IntroductionRequest.created_at.desc()).limit(limit).offset(offset)

    intros = session.execute(q).scalars().all()
    return [_enrich_for_recruiter(session, i) for i in intros]


def get_candidate_introductions(
    session: Session,
    candidate_profile_ids: list[int] | int,
    status_filter: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List introduction requests received by this candidate, enriched with recruiter info."""
    if isinstance(candidate_profile_ids, int):
        candidate_profile_ids = [candidate_profile_ids]
    q = select(IntroductionRequest).where(
        IntroductionRequest.candidate_profile_id.in_(candidate_profile_ids),
    )
    if status_filter:
        q = q.where(IntroductionRequest.status == status_filter)
    q = q.order_by(IntroductionRequest.created_at.desc()).limit(limit)

    intros = session.execute(q).scalars().all()
    return [_enrich_for_candidate(session, i) for i in intros]


def get_candidate_pending_count(
    session: Session,
    candidate_profile_ids: list[int] | int,
) -> int:
    """Count pending introduction requests for badge display."""
    from sqlalchemy import func as sqlfunc

    if isinstance(candidate_profile_ids, int):
        candidate_profile_ids = [candidate_profile_ids]
    result = session.execute(
        select(sqlfunc.count(IntroductionRequest.id)).where(
            IntroductionRequest.candidate_profile_id.in_(candidate_profile_ids),
            IntroductionRequest.status == "pending",
        )
    ).scalar()
    return result or 0


def expire_stale_requests(session: Session) -> int:
    """Expire all pending requests past their expiration date. Returns count updated."""
    now = datetime.now(timezone.utc)
    result = session.execute(
        update(IntroductionRequest)
        .where(
            IntroductionRequest.status == "pending",
            IntroductionRequest.expires_at < now,
        )
        .values(status="expired")
    )
    session.flush()
    count = result.rowcount
    if count:
        logger.info("Expired %d stale introduction requests", count)
    return count


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _enrich_for_recruiter(session: Session, intro: IntroductionRequest) -> dict:
    """Build response dict for recruiter view (email only revealed on acceptance)."""
    from sqlalchemy import func as sqlfunc

    data = {
        "id": intro.id,
        "recruiter_profile_id": intro.recruiter_profile_id,
        "candidate_profile_id": intro.candidate_profile_id,
        "recruiter_job_id": intro.recruiter_job_id,
        "message": intro.message,
        "status": intro.status,
        "candidate_response_message": intro.candidate_response_message,
        "created_at": intro.created_at.isoformat() if intro.created_at else None,
        "responded_at": intro.responded_at.isoformat() if intro.responded_at else None,
        "expires_at": intro.expires_at.isoformat() if intro.expires_at else None,
    }

    # Load candidate profile — resolve to latest version
    cp = session.execute(
        select(CandidateProfile).where(CandidateProfile.id == intro.candidate_profile_id)
    ).scalar_one_or_none()
    if cp and cp.user_id:
        latest = session.execute(
            select(CandidateProfile)
            .where(CandidateProfile.user_id == cp.user_id)
            .order_by(CandidateProfile.version.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest:
            cp = latest
    if cp:
        pj = cp.profile_json or {}
        basics = pj.get("basics") or {}

        # Always show candidate name
        data["candidate_name"] = pj.get("name") or basics.get("name")

        # Derive headline from experience if not at top level
        headline = pj.get("headline") or (basics.get("target_titles") or [None])[0]
        if not headline:
            exp = pj.get("experience") or []
            if exp and isinstance(exp[0], dict):
                title = exp[0].get("title") or ""
                company = exp[0].get("company") or ""
                if title:
                    headline = f"{title} at {company}" if company else title
        data["candidate_headline"] = headline
        data["candidate_location"] = pj.get("location") or basics.get("location")

        # Only reveal email if accepted
        if intro.status == "accepted" and cp.user_id:
            user = session.execute(
                select(User).where(User.id == cp.user_id)
            ).scalar_one_or_none()
            if user:
                data["candidate_email"] = user.email

    # Job info
    if intro.recruiter_job_id:
        rj = session.execute(
            select(RecruiterJob).where(RecruiterJob.id == intro.recruiter_job_id)
        ).scalar_one_or_none()
        if rj:
            data["job_title"] = rj.title
            data["job_client"] = rj.client_company_name

    return data


def _enrich_for_candidate(session: Session, intro: IntroductionRequest) -> dict:
    """Build response dict for candidate view."""
    data = {
        "id": intro.id,
        "recruiter_profile_id": intro.recruiter_profile_id,
        "candidate_profile_id": intro.candidate_profile_id,
        "recruiter_job_id": intro.recruiter_job_id,
        "message": intro.message,
        "status": intro.status,
        "candidate_response_message": intro.candidate_response_message,
        "created_at": intro.created_at.isoformat() if intro.created_at else None,
        "responded_at": intro.responded_at.isoformat() if intro.responded_at else None,
        "expires_at": intro.expires_at.isoformat() if intro.expires_at else None,
    }

    # Recruiter company info
    rp = session.execute(
        select(RecruiterProfile).where(RecruiterProfile.id == intro.recruiter_profile_id)
    ).scalar_one_or_none()
    if rp:
        data["recruiter_company"] = rp.company_name

    # Job info
    if intro.recruiter_job_id:
        rj = session.execute(
            select(RecruiterJob).where(RecruiterJob.id == intro.recruiter_job_id)
        ).scalar_one_or_none()
        if rj:
            data["job_title"] = rj.title
            data["job_client"] = rj.client_company_name

    return data


def _send_intro_request_notification(
    session: Session,
    candidate_profile: CandidateProfile,
    recruiter_profile: RecruiterProfile,
    recruiter_job_id: int | None,
) -> None:
    """Send email to candidate about a new introduction request."""
    from app.services.email import send_introduction_request_email

    if not candidate_profile.user_id:
        return
    user = session.execute(
        select(User).where(User.id == candidate_profile.user_id)
    ).scalar_one_or_none()
    if not user or not user.email:
        return

    job_title = None
    if recruiter_job_id:
        rj = session.execute(
            select(RecruiterJob).where(RecruiterJob.id == recruiter_job_id)
        ).scalar_one_or_none()
        if rj:
            job_title = rj.title

    send_introduction_request_email(
        to_email=user.email,
        recruiter_company=recruiter_profile.company_name,
        job_title=job_title,
    )


def _send_intro_accepted_notification(
    session: Session,
    intro: IntroductionRequest,
) -> None:
    """Send email to recruiter when candidate accepts."""
    from app.services.email import send_introduction_accepted_email

    # Get recruiter's email
    rp = session.execute(
        select(RecruiterProfile).where(RecruiterProfile.id == intro.recruiter_profile_id)
    ).scalar_one_or_none()
    if not rp:
        return
    recruiter_user = session.execute(
        select(User).where(User.id == rp.user_id)
    ).scalar_one_or_none()
    if not recruiter_user or not recruiter_user.email:
        return

    # Get candidate info
    cp = session.execute(
        select(CandidateProfile).where(CandidateProfile.id == intro.candidate_profile_id)
    ).scalar_one_or_none()
    if not cp:
        return
    candidate_name = (cp.profile_json or {}).get("name") or "A candidate"
    candidate_email = None
    if cp.user_id:
        candidate_user = session.execute(
            select(User).where(User.id == cp.user_id)
        ).scalar_one_or_none()
        if candidate_user:
            candidate_email = candidate_user.email

    job_title = None
    if intro.recruiter_job_id:
        rj = session.execute(
            select(RecruiterJob).where(RecruiterJob.id == intro.recruiter_job_id)
        ).scalar_one_or_none()
        if rj:
            job_title = rj.title

    send_introduction_accepted_email(
        to_email=recruiter_user.email,
        candidate_name=candidate_name,
        candidate_email=candidate_email or "Not available",
        job_title=job_title,
    )


def _log_activity(
    session: Session,
    intro: IntroductionRequest,
    activity_type: str,
) -> None:
    """Log a RecruiterActivity for the introduction."""
    from app.models.recruiter_activity import RecruiterActivity

    activity = RecruiterActivity(
        recruiter_profile_id=intro.recruiter_profile_id,
        activity_type=activity_type,
        pipeline_candidate_id=None,
        recruiter_job_id=intro.recruiter_job_id,
        subject=f"Introduction {activity_type.split('_')[-1]}",
        body=f"Candidate profile #{intro.candidate_profile_id}",
        activity_metadata={"introduction_request_id": intro.id},
    )
    session.add(activity)
    session.flush()
