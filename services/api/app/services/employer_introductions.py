"""Employer introduction request service.

Consent-gated employer-to-candidate contact.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate_profile import CandidateProfile
from app.models.employer import EmployerJob, EmployerProfile
from app.models.employer_introduction import EmployerIntroductionRequest
from app.models.user import User
from app.services.billing import (
    check_employer_monthly_limit,
    increment_employer_counter,
)

logger = logging.getLogger(__name__)

INTRO_EXPIRY_DAYS = 7


def create_employer_introduction(
    session: Session,
    employer_profile: EmployerProfile,
    candidate_profile_id: int,
    message: str,
    employer_job_id: int | None = None,
) -> EmployerIntroductionRequest:
    """Create a new introduction request from employer to candidate."""
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

    # 2. Check for existing pending request
    existing = session.execute(
        select(EmployerIntroductionRequest).where(
            EmployerIntroductionRequest.employer_profile_id == employer_profile.id,
            EmployerIntroductionRequest.candidate_profile_id == candidate_profile_id,
            EmployerIntroductionRequest.status == "pending",
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "You already have a pending introduction request for this candidate."
            ),
        )

    # 3. Check monthly limit
    check_employer_monthly_limit(
        employer_profile,
        "intro_requests_used",
        "intro_requests_per_month",
        session,
    )

    # 4. Validate job ownership if provided
    if employer_job_id is not None:
        ej = session.execute(
            select(EmployerJob).where(
                EmployerJob.id == employer_job_id,
                EmployerJob.employer_id == employer_profile.id,
            )
        ).scalar_one_or_none()
        if ej is None:
            raise HTTPException(status_code=404, detail="Job not found.")

    # 5. Create request
    now = datetime.now(UTC)
    intro = EmployerIntroductionRequest(
        employer_profile_id=employer_profile.id,
        candidate_profile_id=candidate_profile_id,
        employer_job_id=employer_job_id,
        message=message,
        status="pending",
        expires_at=now + timedelta(days=INTRO_EXPIRY_DAYS),
    )
    session.add(intro)

    # 6. Increment counter
    increment_employer_counter(employer_profile, "intro_requests_used", session)

    session.flush()

    # 7. Send notification email (non-blocking, best-effort)
    try:
        _send_intro_request_notification(session, cp, employer_profile, employer_job_id)
    except Exception:
        logger.exception("Failed to send employer introduction request email")

    return intro


def respond_to_employer_introduction(
    session: Session,
    candidate_profile_ids: list[int] | int,
    request_id: int,
    action: str,
    response_message: str | None = None,
) -> EmployerIntroductionRequest:
    """Accept or decline an employer introduction request."""
    if isinstance(candidate_profile_ids, int):
        candidate_profile_ids = [candidate_profile_ids]
    intro = session.execute(
        select(EmployerIntroductionRequest).where(
            EmployerIntroductionRequest.id == request_id,
            EmployerIntroductionRequest.candidate_profile_id.in_(candidate_profile_ids),
        )
    ).scalar_one_or_none()
    if intro is None:
        raise HTTPException(status_code=404, detail="Introduction request not found.")
    if intro.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot respond to a request with status '{intro.status}'.",
        )

    now = datetime.now(UTC)

    if action == "accept":
        intro.status = "accepted"
        intro.responded_at = now
        intro.candidate_response_message = response_message
        session.flush()

        # Send acceptance email to employer with revealed candidate info
        try:
            _send_intro_accepted_notification(session, intro)
        except Exception:
            logger.exception("Failed to send employer introduction accepted email")

    elif action == "decline":
        intro.status = "declined"
        intro.responded_at = now
        intro.candidate_response_message = response_message
        session.flush()
    else:
        raise HTTPException(
            status_code=400, detail="Action must be 'accept' or 'decline'."
        )

    return intro


def get_employer_introductions(
    session: Session,
    employer_profile_id: int,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List introduction requests sent by this employer.

    Enriched with candidate info.
    """
    q = select(EmployerIntroductionRequest).where(
        EmployerIntroductionRequest.employer_profile_id == employer_profile_id,
    )
    if status_filter:
        q = q.where(EmployerIntroductionRequest.status == status_filter)
    q = (
        q.order_by(EmployerIntroductionRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    intros = session.execute(q).scalars().all()
    return [_enrich_for_employer(session, i) for i in intros]


def get_employer_introduction_detail(
    session: Session,
    employer_profile_id: int,
    intro_id: int,
) -> dict:
    """Get a single introduction request detail."""
    intro = session.execute(
        select(EmployerIntroductionRequest).where(
            EmployerIntroductionRequest.id == intro_id,
            EmployerIntroductionRequest.employer_profile_id == employer_profile_id,
        )
    ).scalar_one_or_none()
    if intro is None:
        raise HTTPException(status_code=404, detail="Introduction request not found.")
    return _enrich_for_employer(session, intro)


def get_candidate_employer_introductions(
    session: Session,
    candidate_profile_ids: list[int] | int,
    status_filter: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List employer introduction requests received by a candidate."""
    if isinstance(candidate_profile_ids, int):
        candidate_profile_ids = [candidate_profile_ids]
    q = select(EmployerIntroductionRequest).where(
        EmployerIntroductionRequest.candidate_profile_id.in_(candidate_profile_ids),
    )
    if status_filter:
        q = q.where(EmployerIntroductionRequest.status == status_filter)
    q = q.order_by(EmployerIntroductionRequest.created_at.desc()).limit(limit)

    intros = session.execute(q).scalars().all()
    return [_enrich_for_candidate(session, i) for i in intros]


def get_candidate_employer_pending_count(
    session: Session,
    candidate_profile_ids: list[int] | int,
) -> int:
    """Count pending employer introduction requests for badge display."""
    from sqlalchemy import func as sqlfunc

    if isinstance(candidate_profile_ids, int):
        candidate_profile_ids = [candidate_profile_ids]
    result = session.execute(
        select(sqlfunc.count(EmployerIntroductionRequest.id)).where(
            EmployerIntroductionRequest.candidate_profile_id.in_(candidate_profile_ids),
            EmployerIntroductionRequest.status == "pending",
        )
    ).scalar()
    return result or 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _enrich_for_employer(session: Session, intro: EmployerIntroductionRequest) -> dict:
    """Build response dict for employer view (email only revealed on acceptance)."""
    data = {
        "id": intro.id,
        "employer_profile_id": intro.employer_profile_id,
        "candidate_profile_id": intro.candidate_profile_id,
        "employer_job_id": intro.employer_job_id,
        "message": intro.message,
        "status": intro.status,
        "candidate_response_message": intro.candidate_response_message,
        "created_at": intro.created_at.isoformat() if intro.created_at else None,
        "responded_at": intro.responded_at.isoformat() if intro.responded_at else None,
        "expires_at": intro.expires_at.isoformat() if intro.expires_at else None,
        "sender_type": "employer",
    }

    # Load candidate profile — resolve to latest version
    cp = session.execute(
        select(CandidateProfile).where(
            CandidateProfile.id == intro.candidate_profile_id
        )
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

        data["candidate_name"] = pj.get("name") or basics.get("name")

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
    if intro.employer_job_id:
        ej = session.execute(
            select(EmployerJob).where(EmployerJob.id == intro.employer_job_id)
        ).scalar_one_or_none()
        if ej:
            data["job_title"] = ej.title

    return data


def _enrich_for_candidate(session: Session, intro: EmployerIntroductionRequest) -> dict:
    """Build response dict for candidate view."""
    data = {
        "id": intro.id,
        "candidate_profile_id": intro.candidate_profile_id,
        "employer_job_id": intro.employer_job_id,
        "message": intro.message,
        "status": intro.status,
        "candidate_response_message": intro.candidate_response_message,
        "created_at": intro.created_at.isoformat() if intro.created_at else None,
        "responded_at": intro.responded_at.isoformat() if intro.responded_at else None,
        "expires_at": intro.expires_at.isoformat() if intro.expires_at else None,
        "sender_type": "employer",
    }

    # Employer company info
    ep = session.execute(
        select(EmployerProfile).where(EmployerProfile.id == intro.employer_profile_id)
    ).scalar_one_or_none()
    if ep:
        data["sender_company"] = ep.company_name

    # Job info
    if intro.employer_job_id:
        ej = session.execute(
            select(EmployerJob).where(EmployerJob.id == intro.employer_job_id)
        ).scalar_one_or_none()
        if ej:
            data["job_title"] = ej.title

    return data


def _send_intro_request_notification(
    session: Session,
    candidate_profile: CandidateProfile,
    employer_profile: EmployerProfile,
    employer_job_id: int | None,
) -> None:
    """Send email to candidate about a new employer introduction request."""
    from app.services.email import send_introduction_request_email

    if not candidate_profile.user_id:
        return
    user = session.execute(
        select(User).where(User.id == candidate_profile.user_id)
    ).scalar_one_or_none()
    if not user or not user.email:
        return

    job_title = None
    if employer_job_id:
        ej = session.execute(
            select(EmployerJob).where(EmployerJob.id == employer_job_id)
        ).scalar_one_or_none()
        if ej:
            job_title = ej.title

    send_introduction_request_email(
        to_email=user.email,
        recruiter_company=employer_profile.company_name,
        job_title=job_title,
    )


def _send_intro_accepted_notification(
    session: Session,
    intro: EmployerIntroductionRequest,
) -> None:
    """Send email to employer when candidate accepts."""
    from app.services.email import send_introduction_accepted_email

    # Get employer's email
    ep = session.execute(
        select(EmployerProfile).where(EmployerProfile.id == intro.employer_profile_id)
    ).scalar_one_or_none()
    if not ep:
        return
    employer_user = session.execute(
        select(User).where(User.id == ep.user_id)
    ).scalar_one_or_none()
    if not employer_user or not employer_user.email:
        return

    # Get candidate info
    cp = session.execute(
        select(CandidateProfile).where(
            CandidateProfile.id == intro.candidate_profile_id
        )
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
    if intro.employer_job_id:
        ej = session.execute(
            select(EmployerJob).where(EmployerJob.id == intro.employer_job_id)
        ).scalar_one_or_none()
        if ej:
            job_title = ej.title

    send_introduction_accepted_email(
        to_email=employer_user.email,
        candidate_name=candidate_name,
        candidate_email=candidate_email or "Not available",
        job_title=job_title,
    )
