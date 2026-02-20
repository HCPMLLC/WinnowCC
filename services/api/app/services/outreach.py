"""Outreach sequence engine — CRUD, enrollment, and scheduled email processing."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import resend
from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.outreach_enrollment import OutreachEnrollment
from app.models.outreach_sequence import OutreachSequence
from app.models.recruiter import RecruiterProfile
from app.models.recruiter_activity import RecruiterActivity
from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
from app.services.billing import (
    check_recruiter_feature,
    check_recruiter_monthly_limit,
    get_recruiter_limit,
    get_recruiter_tier,
    increment_recruiter_counter,
)

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM = os.getenv("RESEND_FROM_EMAIL", "Winnow <noreply@winnow.careers>").strip()


# ---------------------------------------------------------------------------
# Sequence CRUD
# ---------------------------------------------------------------------------


def create_sequence(
    session: Session,
    profile: RecruiterProfile,
    data,
) -> OutreachSequence:
    """Create a new outreach sequence."""
    if not check_recruiter_feature(profile, "outreach_sequences"):
        raise HTTPException(
            status_code=403,
            detail="Outreach sequences require a Team or Agency plan.",
        )

    tier = get_recruiter_tier(profile)
    max_active = get_recruiter_limit(tier, "active_sequences")
    active_count = session.execute(
        select(func.count(OutreachSequence.id)).where(
            OutreachSequence.recruiter_profile_id == profile.id,
            OutreachSequence.is_active == True,  # noqa: E712
        )
    ).scalar_one()
    if isinstance(max_active, int) and active_count >= max_active:
        raise HTTPException(
            status_code=429,
            detail=f"Active sequence limit reached ({max_active} on {tier} plan).",
        )

    seq = OutreachSequence(
        recruiter_profile_id=profile.id,
        recruiter_job_id=data.recruiter_job_id,
        name=data.name,
        description=data.description,
        steps=[s.model_dump() for s in data.steps],
    )
    session.add(seq)
    session.flush()
    return seq


def list_sequences(session: Session, profile: RecruiterProfile) -> list[dict]:
    """List all sequences for a recruiter with enrolled/sent counts."""
    enrolled_sub = (
        select(
            OutreachEnrollment.sequence_id,
            func.count(OutreachEnrollment.id).label("enrolled_count"),
            func.count(OutreachEnrollment.last_sent_at).label("sent_count"),
        )
        .where(OutreachEnrollment.recruiter_profile_id == profile.id)
        .group_by(OutreachEnrollment.sequence_id)
        .subquery()
    )

    stmt = (
        select(
            OutreachSequence,
            func.coalesce(enrolled_sub.c.enrolled_count, 0).label("enrolled_count"),
            func.coalesce(enrolled_sub.c.sent_count, 0).label("sent_count"),
        )
        .outerjoin(enrolled_sub, OutreachSequence.id == enrolled_sub.c.sequence_id)
        .where(OutreachSequence.recruiter_profile_id == profile.id)
        .order_by(OutreachSequence.created_at.desc())
    )

    results = []
    for row in session.execute(stmt).all():
        seq = row[0]
        results.append(
            {
                "id": seq.id,
                "recruiter_profile_id": seq.recruiter_profile_id,
                "recruiter_job_id": seq.recruiter_job_id,
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
    session: Session, profile: RecruiterProfile, sequence_id: int
) -> OutreachSequence:
    """Get a single sequence with ownership check."""
    seq = session.get(OutreachSequence, sequence_id)
    if seq is None or seq.recruiter_profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Sequence not found.")
    return seq


def update_sequence(
    session: Session,
    profile: RecruiterProfile,
    sequence_id: int,
    data,
) -> OutreachSequence:
    """Update a sequence. Block step changes if active enrollments exist."""
    seq = get_sequence(session, profile, sequence_id)

    if data.steps is not None:
        active_enrollments = session.execute(
            select(func.count(OutreachEnrollment.id)).where(
                OutreachEnrollment.sequence_id == seq.id,
                OutreachEnrollment.status == "active",
            )
        ).scalar_one()
        if active_enrollments > 0:
            raise HTTPException(
                status_code=409,
                detail="Cannot change steps while candidates are actively enrolled. Pause or unenroll them first.",
            )
        seq.steps = [s.model_dump() for s in data.steps]

    if data.name is not None:
        seq.name = data.name
    if data.description is not None:
        seq.description = data.description
    if data.recruiter_job_id is not None:
        seq.recruiter_job_id = data.recruiter_job_id
    if data.is_active is not None:
        seq.is_active = data.is_active

    session.flush()
    return seq


def delete_sequence(
    session: Session, profile: RecruiterProfile, sequence_id: int
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
    profile: RecruiterProfile,
    sequence_id: int,
    pipeline_candidate_ids: list[int],
) -> dict:
    """Enroll pipeline candidates in a sequence."""
    if not check_recruiter_feature(profile, "outreach_sequences"):
        raise HTTPException(
            status_code=403,
            detail="Outreach sequences require a Team or Agency plan.",
        )

    seq = get_sequence(session, profile, sequence_id)
    if not seq.is_active:
        raise HTTPException(status_code=400, detail="Sequence is paused.")
    if not seq.steps:
        raise HTTPException(status_code=400, detail="Sequence has no steps.")

    first_step = seq.steps[0]
    delay_days = first_step.get("delay_days", 0)
    now = datetime.now(timezone.utc)
    next_send = now + timedelta(days=delay_days)

    enrolled = 0
    skipped = 0
    no_email = 0

    for cid in pipeline_candidate_ids:
        candidate = session.get(RecruiterPipelineCandidate, cid)
        if candidate is None or candidate.recruiter_profile_id != profile.id:
            skipped += 1
            continue
        if not candidate.external_email:
            no_email += 1
            continue

        # Check monthly limit before each enrollment
        try:
            check_recruiter_monthly_limit(
                profile, "outreach_enrollments_used", "enrollments_per_month", session
            )
        except HTTPException:
            raise HTTPException(
                status_code=429,
                detail=f"Monthly enrollment limit reached. Enrolled {enrolled} of {len(pipeline_candidate_ids)} candidates.",
            )

        # Skip if already enrolled (unique constraint)
        existing = session.execute(
            select(OutreachEnrollment.id).where(
                OutreachEnrollment.sequence_id == seq.id,
                OutreachEnrollment.pipeline_candidate_id == cid,
            )
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue

        enrollment = OutreachEnrollment(
            sequence_id=seq.id,
            pipeline_candidate_id=cid,
            recruiter_profile_id=profile.id,
            current_step=0,
            status="active",
            next_send_at=next_send,
        )
        session.add(enrollment)
        increment_recruiter_counter(profile, "outreach_enrollments_used", session)
        enrolled += 1

    session.flush()
    return {"enrolled": enrolled, "skipped": skipped, "no_email": no_email}


def unenroll(
    session: Session,
    profile: RecruiterProfile,
    enrollment_ids: list[int],
) -> dict:
    """Unenroll candidates from their sequences."""
    unenrolled = 0
    for eid in enrollment_ids:
        enrollment = session.get(OutreachEnrollment, eid)
        if enrollment is None or enrollment.recruiter_profile_id != profile.id:
            continue
        if enrollment.status in ("active", "paused"):
            enrollment.status = "unenrolled"
            unenrolled += 1
    session.flush()
    return {"unenrolled": unenrolled}


def list_enrollments(
    session: Session,
    profile: RecruiterProfile,
    sequence_id: int,
    status_filter: str | None = None,
) -> list[dict]:
    """List enrollments for a sequence with candidate name/email resolved."""
    seq = get_sequence(session, profile, sequence_id)

    stmt = (
        select(OutreachEnrollment, RecruiterPipelineCandidate)
        .join(
            RecruiterPipelineCandidate,
            OutreachEnrollment.pipeline_candidate_id == RecruiterPipelineCandidate.id,
        )
        .where(OutreachEnrollment.sequence_id == seq.id)
    )
    if status_filter:
        stmt = stmt.where(OutreachEnrollment.status == status_filter)
    stmt = stmt.order_by(OutreachEnrollment.enrolled_at.desc())

    results = []
    for row in session.execute(stmt).all():
        enrollment = row[0]
        candidate = row[1]
        results.append(
            {
                "id": enrollment.id,
                "sequence_id": enrollment.sequence_id,
                "pipeline_candidate_id": enrollment.pipeline_candidate_id,
                "recruiter_profile_id": enrollment.recruiter_profile_id,
                "current_step": enrollment.current_step,
                "status": enrollment.status,
                "next_send_at": enrollment.next_send_at,
                "last_sent_at": enrollment.last_sent_at,
                "enrolled_at": enrollment.enrolled_at,
                "completed_at": enrollment.completed_at,
                "candidate_name": candidate.external_name,
                "candidate_email": candidate.external_email,
            }
        )
    return results


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------


def send_outreach_email(
    to: str, subject: str, body: str, recruiter_company: str
) -> bool:
    """Send an outreach email via Resend. Returns True on success."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set; skipping outreach email to %s", to)
        return False

    try:
        resend.api_key = RESEND_API_KEY
        resend.Emails.send(
            {
                "from": RESEND_FROM,
                "to": [to],
                "subject": subject,
                "html": (
                    f"<div>{body}</div>"
                    f'<p style="color:#999;font-size:12px;margin-top:24px;">'
                    f"Sent via {recruiter_company} on Winnow</p>"
                ),
            }
        )
        return True
    except Exception as e:
        logger.error("Failed to send outreach email to %s: %s", to, e)
        return False


# ---------------------------------------------------------------------------
# Template variable resolution
# ---------------------------------------------------------------------------


def _resolve_template(
    text: str,
    candidate: RecruiterPipelineCandidate,
    seq: OutreachSequence,
    profile: RecruiterProfile,
) -> str:
    """Replace template variables in subject/body text."""
    replacements = {
        "{candidate_name}": candidate.external_name or "there",
        "{recruiter_name}": profile.company_name or "",
        "{recruiter_company}": profile.company_name or "",
    }

    # Job-specific variables from the linked recruiter job
    if seq.job:
        replacements["{job_title}"] = seq.job.title or ""
        replacements["{job_location}"] = seq.job.location or ""
    else:
        replacements["{job_title}"] = ""
        replacements["{job_location}"] = ""

    for key, val in replacements.items():
        text = text.replace(key, val)
    return text


# ---------------------------------------------------------------------------
# Scheduled processing
# ---------------------------------------------------------------------------


def process_due_outreach() -> dict:
    """Process all due outreach enrollments. Standalone — no request context."""
    from app.db.session import get_session_factory

    session = get_session_factory()()
    sent = 0
    errors = 0
    completed = 0

    try:
        now = datetime.now(timezone.utc)

        stmt = (
            select(OutreachEnrollment)
            .join(OutreachSequence, OutreachEnrollment.sequence_id == OutreachSequence.id)
            .where(
                and_(
                    OutreachEnrollment.status == "active",
                    OutreachEnrollment.next_send_at <= now,
                    OutreachSequence.is_active == True,  # noqa: E712
                )
            )
            .limit(100)
        )
        enrollments = list(session.execute(stmt).scalars().all())

        for enrollment in enrollments:
            try:
                seq = session.get(OutreachSequence, enrollment.sequence_id)
                candidate = session.get(
                    RecruiterPipelineCandidate, enrollment.pipeline_candidate_id
                )
                profile = session.get(
                    RecruiterProfile, enrollment.recruiter_profile_id
                )

                if not seq or not candidate or not profile:
                    enrollment.status = "bounced"
                    errors += 1
                    continue

                if not candidate.external_email:
                    enrollment.status = "bounced"
                    errors += 1
                    continue

                steps = seq.steps or []
                next_step_index = enrollment.current_step  # 0-based index
                if next_step_index >= len(steps):
                    enrollment.status = "completed"
                    enrollment.completed_at = now
                    completed += 1
                    continue

                step = steps[next_step_index]
                subject = _resolve_template(
                    step.get("subject", ""), candidate, seq, profile
                )
                body = _resolve_template(
                    step.get("body", ""), candidate, seq, profile
                )

                success = send_outreach_email(
                    to=candidate.external_email,
                    subject=subject,
                    body=body,
                    recruiter_company=profile.company_name or "A recruiter",
                )

                if success:
                    enrollment.current_step += 1
                    enrollment.last_sent_at = now

                    # Update pipeline candidate outreach tracking
                    candidate.outreach_count = (candidate.outreach_count or 0) + 1
                    candidate.last_outreach_at = now

                    # Auto-advance stage from sourced to contacted on first step
                    if next_step_index == 0 and candidate.stage == "sourced":
                        candidate.stage = "contacted"

                    # Check if all steps are done
                    if enrollment.current_step >= len(steps):
                        enrollment.status = "completed"
                        enrollment.completed_at = now
                        completed += 1
                    else:
                        # Compute next send time
                        next_step = steps[enrollment.current_step]
                        delay = next_step.get("delay_days", 1)
                        enrollment.next_send_at = now + timedelta(days=delay)

                    # Log activity
                    activity = RecruiterActivity(
                        recruiter_profile_id=profile.id,
                        pipeline_candidate_id=candidate.id,
                        recruiter_job_id=seq.recruiter_job_id,
                        activity_type="outreach_sent",
                        subject=f"Step {next_step_index + 1}: {subject[:200]}",
                        activity_metadata={
                            "sequence_id": seq.id,
                            "step_number": next_step_index + 1,
                            "enrollment_id": enrollment.id,
                        },
                    )
                    session.add(activity)
                    sent += 1
                else:
                    # Treat as bounced for permanent failures
                    enrollment.status = "bounced"
                    errors += 1

            except Exception as e:
                logger.error(
                    "Error processing enrollment %s: %s", enrollment.id, e
                )
                errors += 1

        session.commit()

    except Exception as e:
        logger.exception("process_due_outreach failed: %s", e)
        session.rollback()
    finally:
        session.close()

    return {"sent": sent, "errors": errors, "completed": completed}
