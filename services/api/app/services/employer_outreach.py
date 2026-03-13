"""Employer outreach sequence engine — CRUD, enrollment, and scheduled processing."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta

import resend
from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.candidate_profile import CandidateProfile
from app.models.employer import EmployerJob, EmployerProfile
from app.models.employer_outreach import (
    EmployerOutreachEnrollment,
    EmployerOutreachSequence,
)
from app.models.user import User
from app.services.billing import (
    check_employer_feature,
    check_employer_monthly_limit,
    get_employer_limit,
    get_employer_tier,
    increment_employer_counter,
)

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM = os.getenv("RESEND_FROM_EMAIL", "Winnow <noreply@winnow.careers>").strip()


# ---------------------------------------------------------------------------
# Sequence CRUD
# ---------------------------------------------------------------------------


def create_sequence(
    session: Session,
    profile: EmployerProfile,
    data,
) -> EmployerOutreachSequence:
    """Create a new employer outreach sequence."""
    if not check_employer_feature(profile, "outreach_sequences"):
        raise HTTPException(
            status_code=403,
            detail="Outreach sequences require a Pro or Enterprise plan.",
        )

    tier = get_employer_tier(profile)
    max_active = get_employer_limit(tier, "active_outreach_sequences")
    active_count = session.execute(
        select(func.count(EmployerOutreachSequence.id)).where(
            EmployerOutreachSequence.employer_profile_id == profile.id,
            EmployerOutreachSequence.is_active == True,  # noqa: E712
        )
    ).scalar_one()
    if isinstance(max_active, int) and active_count >= max_active:
        raise HTTPException(
            status_code=429,
            detail=f"Active sequence limit reached ({max_active} on {tier} plan).",
        )

    seq = EmployerOutreachSequence(
        employer_profile_id=profile.id,
        employer_job_id=data.employer_job_id,
        name=data.name,
        description=data.description,
        steps=[s.model_dump() for s in data.steps],
    )
    session.add(seq)
    session.flush()
    return seq


def list_sequences(session: Session, profile: EmployerProfile) -> list[dict]:
    """List all sequences for an employer with enrolled/sent counts."""
    enrolled_sub = (
        select(
            EmployerOutreachEnrollment.sequence_id,
            func.count(EmployerOutreachEnrollment.id).label("enrolled_count"),
            func.count(EmployerOutreachEnrollment.last_sent_at).label("sent_count"),
        )
        .where(EmployerOutreachEnrollment.employer_profile_id == profile.id)
        .group_by(EmployerOutreachEnrollment.sequence_id)
        .subquery()
    )

    stmt = (
        select(
            EmployerOutreachSequence,
            func.coalesce(enrolled_sub.c.enrolled_count, 0).label("enrolled_count"),
            func.coalesce(enrolled_sub.c.sent_count, 0).label("sent_count"),
        )
        .outerjoin(
            enrolled_sub,
            EmployerOutreachSequence.id == enrolled_sub.c.sequence_id,
        )
        .where(EmployerOutreachSequence.employer_profile_id == profile.id)
        .order_by(EmployerOutreachSequence.created_at.desc())
    )

    results = []
    for row in session.execute(stmt).all():
        seq = row[0]
        results.append(
            {
                "id": seq.id,
                "employer_profile_id": seq.employer_profile_id,
                "employer_job_id": seq.employer_job_id,
                "name": seq.name,
                "description": seq.description,
                "is_active": seq.is_active,
                "steps": seq.steps or [],
                "enrolled_count": row[1],
                "sent_count": row[2],
                "created_at": seq.created_at,
                "updated_at": seq.updated_at,
            }
        )
    return results


def get_sequence(
    session: Session, profile: EmployerProfile, sequence_id: int
) -> EmployerOutreachSequence:
    """Get a single sequence with ownership check."""
    seq = session.get(EmployerOutreachSequence, sequence_id)
    if seq is None or seq.employer_profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Sequence not found.")
    return seq


def update_sequence(
    session: Session,
    profile: EmployerProfile,
    sequence_id: int,
    data,
) -> EmployerOutreachSequence:
    """Update a sequence. Block step changes if active enrollments exist."""
    seq = get_sequence(session, profile, sequence_id)

    if data.steps is not None:
        active_enrollments = session.execute(
            select(func.count(EmployerOutreachEnrollment.id)).where(
                EmployerOutreachEnrollment.sequence_id == seq.id,
                EmployerOutreachEnrollment.status == "active",
            )
        ).scalar_one()
        if active_enrollments > 0:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Cannot change steps while candidates are actively enrolled. "
                    "Pause or unenroll them first."
                ),
            )
        seq.steps = [s.model_dump() for s in data.steps]

    if data.name is not None:
        seq.name = data.name
    if data.description is not None:
        seq.description = data.description
    if data.employer_job_id is not None:
        seq.employer_job_id = data.employer_job_id
    if data.is_active is not None:
        seq.is_active = data.is_active

    session.flush()
    return seq


def delete_sequence(
    session: Session, profile: EmployerProfile, sequence_id: int
) -> None:
    """Delete a sequence (cascades enrollments)."""
    seq = get_sequence(session, profile, sequence_id)
    session.delete(seq)
    session.flush()


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------


def enroll_candidates(
    session: Session,
    profile: EmployerProfile,
    sequence_id: int,
    candidate_profile_ids: list[int],
) -> dict:
    """Enroll candidate profiles in a sequence."""
    if not check_employer_feature(profile, "outreach_sequences"):
        raise HTTPException(
            status_code=403,
            detail="Outreach sequences require a Pro or Enterprise plan.",
        )

    seq = get_sequence(session, profile, sequence_id)
    if not seq.is_active:
        raise HTTPException(status_code=400, detail="Sequence is paused.")
    if not seq.steps:
        raise HTTPException(status_code=400, detail="Sequence has no steps.")

    first_step = seq.steps[0]
    delay_days = first_step.get("delay_days", 0)
    now = datetime.now(UTC)
    next_send = now + timedelta(days=delay_days)

    enrolled = 0
    skipped = 0

    for cid in candidate_profile_ids:
        profile_obj = session.get(CandidateProfile, cid)
        if profile_obj is None:
            skipped += 1
            continue

        # Check monthly limit before each enrollment
        try:
            check_employer_monthly_limit(
                profile,
                "outreach_enrollments_used",
                "outreach_enrollments_per_month",
                session,
            )
        except HTTPException:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Monthly enrollment limit reached. "
                    f"Enrolled {enrolled} of {len(candidate_profile_ids)} candidates."
                ),
            ) from None

        # Skip if already enrolled (unique constraint)
        existing = session.execute(
            select(EmployerOutreachEnrollment.id).where(
                EmployerOutreachEnrollment.sequence_id == seq.id,
                EmployerOutreachEnrollment.candidate_profile_id == cid,
            )
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue

        enrollment = EmployerOutreachEnrollment(
            sequence_id=seq.id,
            candidate_profile_id=cid,
            employer_profile_id=profile.id,
            current_step=0,
            status="active",
            next_send_at=next_send,
        )
        session.add(enrollment)
        increment_employer_counter(profile, "outreach_enrollments_used", session)
        enrolled += 1

    session.flush()
    return {"enrolled": enrolled, "skipped": skipped}


def unenroll(
    session: Session,
    profile: EmployerProfile,
    enrollment_ids: list[int],
) -> dict:
    """Unenroll candidates from their sequences."""
    unenrolled = 0
    for eid in enrollment_ids:
        enrollment = session.get(EmployerOutreachEnrollment, eid)
        if enrollment is None or enrollment.employer_profile_id != profile.id:
            continue
        if enrollment.status in ("active", "paused"):
            enrollment.status = "unenrolled"
            unenrolled += 1
    session.flush()
    return {"unenrolled": unenrolled}


def list_enrollments(
    session: Session,
    profile: EmployerProfile,
    sequence_id: int,
    status_filter: str | None = None,
) -> list[dict]:
    """List enrollments for a sequence with candidate info resolved."""
    seq = get_sequence(session, profile, sequence_id)

    stmt = (
        select(EmployerOutreachEnrollment, CandidateProfile)
        .join(
            CandidateProfile,
            EmployerOutreachEnrollment.candidate_profile_id == CandidateProfile.id,
        )
        .where(EmployerOutreachEnrollment.sequence_id == seq.id)
    )
    if status_filter:
        stmt = stmt.where(EmployerOutreachEnrollment.status == status_filter)
    stmt = stmt.order_by(EmployerOutreachEnrollment.enrolled_at.desc())

    results = []
    for row in session.execute(stmt).all():
        enrollment = row[0]
        candidate = row[1]
        pj = candidate.profile_json or {}
        basics = pj.get("basics", {})
        name = basics.get("name") or f"Candidate {candidate.id}"

        # Resolve email via user
        email = None
        if candidate.user_id:
            user = session.get(User, candidate.user_id)
            if user:
                email = user.email

        results.append(
            {
                "id": enrollment.id,
                "sequence_id": enrollment.sequence_id,
                "candidate_profile_id": enrollment.candidate_profile_id,
                "employer_profile_id": enrollment.employer_profile_id,
                "current_step": enrollment.current_step,
                "status": enrollment.status,
                "next_send_at": enrollment.next_send_at,
                "last_sent_at": enrollment.last_sent_at,
                "enrolled_at": enrollment.enrolled_at,
                "completed_at": enrollment.completed_at,
                "applied_at": enrollment.applied_at,
                "candidate_name": name,
                "candidate_email": email,
            }
        )
    return results


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------


def _build_unsubscribe_url(enrollment_id: int, token: str) -> str:
    base = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    return f"{base}/api/employer-outreach/{enrollment_id}/unsubscribe/{token}"


def send_employer_outreach_email(
    to: str,
    subject: str,
    body: str,
    company_name: str,
    enrollment_id: int | None = None,
    unsubscribe_token: str | None = None,
) -> bool:
    """Send an employer outreach email via Resend. Returns True on success."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set; skipping outreach email to %s", to)
        return False

    unsub_html = ""
    headers: dict[str, str] = {}
    if enrollment_id and unsubscribe_token:
        unsub_url = _build_unsubscribe_url(enrollment_id, unsubscribe_token)
        unsub_html = (
            f'<p style="color:#999;font-size:11px;margin-top:16px;">'
            f'<a href="{unsub_url}" style="color:#999;">'
            f"Unsubscribe from this sequence</a></p>"
        )
        headers["List-Unsubscribe"] = f"<{unsub_url}>"
        headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    try:
        resend.api_key = RESEND_API_KEY
        payload: dict = {
            "from": RESEND_FROM,
            "to": [to],
            "subject": subject,
            "html": (
                f"<div>{body}</div>"
                f'<p style="color:#999;font-size:12px;margin-top:24px;">'
                f"Sent via {company_name} on Winnow</p>"
                f"{unsub_html}"
            ),
        }
        if headers:
            payload["headers"] = headers
        resend.Emails.send(payload)
        return True
    except Exception as e:
        logger.error("Failed to send employer outreach email to %s: %s", to, e)
        return False


# ---------------------------------------------------------------------------
# Template variable resolution
# ---------------------------------------------------------------------------


def _resolve_template(
    text: str,
    candidate_name: str,
    company_name: str,
    job: EmployerJob | None,
    career_page_url: str | None = None,
) -> str:
    """Replace template variables in subject/body text."""
    replacements = {
        "{candidate_name}": candidate_name or "there",
        "{company_name}": company_name or "",
    }

    if job:
        replacements["{job_title}"] = job.title or ""
        replacements["{job_location}"] = job.location or ""
    else:
        replacements["{job_title}"] = ""
        replacements["{job_location}"] = ""

    if career_page_url:
        replacements["{career_page_url}"] = career_page_url
    else:
        replacements["{career_page_url}"] = ""

    replacements["{form_links}"] = ""  # Populated separately when action=send_forms

    for key, val in replacements.items():
        text = text.replace(key, val)
    return text


# ---------------------------------------------------------------------------
# Scheduled processing
# ---------------------------------------------------------------------------


def process_due_employer_outreach() -> dict:
    """Process due employer outreach enrollments. No request context."""
    from app.db.session import get_session_factory

    session = get_session_factory()()
    sent = 0
    errors = 0
    completed = 0

    try:
        now = datetime.now(UTC)

        stmt = (
            select(EmployerOutreachEnrollment)
            .join(
                EmployerOutreachSequence,
                EmployerOutreachEnrollment.sequence_id
                == EmployerOutreachSequence.id,
            )
            .where(
                and_(
                    EmployerOutreachEnrollment.status == "active",
                    EmployerOutreachEnrollment.next_send_at <= now,
                    EmployerOutreachSequence.is_active == True,  # noqa: E712
                )
            )
            .limit(100)
        )
        enrollments = list(session.execute(stmt).scalars().all())

        for enrollment in enrollments:
            try:
                seq = session.get(
                    EmployerOutreachSequence, enrollment.sequence_id
                )
                candidate = session.get(
                    CandidateProfile, enrollment.candidate_profile_id
                )
                profile = session.get(
                    EmployerProfile, enrollment.employer_profile_id
                )

                if not seq or not candidate or not profile:
                    enrollment.status = "bounced"
                    errors += 1
                    continue

                # Resolve candidate email via user
                email = None
                if candidate.user_id:
                    user = session.get(User, candidate.user_id)
                    if user:
                        email = user.email

                if not email:
                    enrollment.status = "bounced"
                    errors += 1
                    continue

                steps = seq.steps or []
                next_step_index = enrollment.current_step
                if next_step_index >= len(steps):
                    enrollment.status = "completed"
                    enrollment.completed_at = now
                    completed += 1
                    continue

                step = steps[next_step_index]

                # Resolve candidate name
                pj = candidate.profile_json or {}
                basics = pj.get("basics", {})
                cand_name = basics.get("name") or "there"

                # Resolve linked job for template vars
                job = None
                if seq.employer_job_id:
                    job = session.get(EmployerJob, seq.employer_job_id)

                subject = _resolve_template(
                    step.get("subject", ""),
                    cand_name,
                    profile.company_name,
                    job,
                )
                body = _resolve_template(
                    step.get("body", ""),
                    cand_name,
                    profile.company_name,
                    job,
                )

                success = send_employer_outreach_email(
                    to=email,
                    subject=subject,
                    body=body,
                    company_name=profile.company_name or "An employer",
                    enrollment_id=enrollment.id,
                    unsubscribe_token=enrollment.unsubscribe_token,
                )

                if success:
                    enrollment.current_step += 1
                    enrollment.last_sent_at = now

                    # Check if all steps are done
                    if enrollment.current_step >= len(steps):
                        enrollment.status = "completed"
                        enrollment.completed_at = now
                        completed += 1
                    else:
                        next_step = steps[enrollment.current_step]
                        delay = next_step.get("delay_days", 1)
                        enrollment.next_send_at = now + timedelta(days=delay)

                    sent += 1
                else:
                    enrollment.status = "bounced"
                    errors += 1

            except Exception as e:
                logger.error(
                    "Error processing employer enrollment %s: %s",
                    enrollment.id,
                    e,
                )
                errors += 1

        session.commit()

    except Exception as e:
        logger.exception("process_due_employer_outreach failed: %s", e)
        session.rollback()
    finally:
        session.close()

    return {"sent": sent, "errors": errors, "completed": completed}
