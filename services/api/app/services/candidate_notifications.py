"""Candidate notifications — status push notifications via email."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Status transition message templates
STATUS_MESSAGES: dict[str, dict] = {
    "screening": {
        "subject": "Your application is being reviewed",
        "body": (
            "Your application for {job_title} at {company} "
            "is being reviewed. We'll notify you of any updates."
        ),
    },
    "interviewing": {
        "subject": "Interview invitation from {company}",
        "body": (
            "Great news! {company} would like to interview you "
            "for {job_title}. Check your email for scheduling details."
        ),
    },
    "offer": {
        "subject": "Offer from {company}",
        "body": (
            "Congratulations! {company} has extended an offer "
            "for {job_title}. Log in to Winnow for details."
        ),
    },
    "rejected": {
        "subject": "Update on your application at {company}",
        "body": (
            "{company} has decided to move forward with other "
            "candidates for {job_title}. {feedback}"
        ),
    },
}


def notify_status_change(
    candidate_id: int,
    employer_job_id: int | None,
    new_status: str,
    job_title: str,
    company: str,
    feedback: str | None,
    session: Session,
) -> dict | None:
    """Send notification when application status changes.

    Creates a notification record and sends email via Resend.
    Returns the notification dict or None if no template matches.
    """
    template = STATUS_MESSAGES.get(new_status)
    if not template:
        return None

    feedback_text = feedback or ""
    subject = template["subject"].format(job_title=job_title, company=company)
    body = template["body"].format(
        job_title=job_title,
        company=company,
        feedback=feedback_text,
    )

    # Store notification record
    from app.models.candidate_notification import CandidateNotification

    notification = CandidateNotification(
        candidate_id=candidate_id,
        employer_job_id=employer_job_id,
        notification_type=f"status_{new_status}",
        subject=subject,
        body=body,
        sent_at=datetime.now(UTC),
    )
    session.add(notification)
    session.flush()

    # Send email (best-effort)
    _send_email(candidate_id, subject, body, session)

    return {
        "id": notification.id,
        "type": notification.notification_type,
        "subject": subject,
    }


def get_notifications(
    candidate_id: int,
    limit: int = 20,
    session: Session | None = None,
) -> list[dict]:
    """Get recent notifications for a candidate."""
    from app.models.candidate_notification import CandidateNotification

    if not session:
        return []

    stmt = (
        select(CandidateNotification)
        .where(CandidateNotification.candidate_id == candidate_id)
        .order_by(CandidateNotification.sent_at.desc())
        .limit(limit)
    )
    notifications = list(session.execute(stmt).scalars().all())

    return [
        {
            "id": n.id,
            "type": n.notification_type,
            "subject": n.subject,
            "body": n.body,
            "sent_at": n.sent_at.isoformat() if n.sent_at else None,
            "read_at": n.read_at.isoformat() if n.read_at else None,
        }
        for n in notifications
    ]


def mark_read(
    notification_id: int,
    candidate_id: int,
    session: Session,
) -> bool:
    """Mark a notification as read."""
    from app.models.candidate_notification import CandidateNotification

    stmt = select(CandidateNotification).where(
        CandidateNotification.id == notification_id,
        CandidateNotification.candidate_id == candidate_id,
    )
    notification = session.execute(stmt).scalar_one_or_none()
    if not notification:
        return False
    notification.read_at = datetime.now(UTC)
    return True


def get_rejection_recommendations(
    candidate_id: int,
    rejected_job_id: int,
    session: Session,
) -> list[dict]:
    """Find similar active jobs for a rejected candidate."""
    from app.models.job import Job
    from app.models.match import Match

    # Get top matches for the candidate that aren't this job
    stmt = (
        select(Match)
        .where(
            Match.candidate_id == candidate_id,
            Match.job_id != rejected_job_id,
        )
        .order_by(Match.match_score.desc())
        .limit(3)
    )
    matches = list(session.execute(stmt).scalars().all())

    recs = []
    for m in matches:
        job = session.get(Job, m.job_id)
        if job:
            recs.append(
                {
                    "job_id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "match_score": m.match_score,
                }
            )
    return recs


def _send_email(
    candidate_id: int,
    subject: str,
    body: str,
    session: Session,
) -> None:
    """Send email notification. Best-effort, no exception on failure."""
    try:
        from app.models.candidate import Candidate
        from app.models.user import User

        candidate = session.get(Candidate, candidate_id)
        if not candidate:
            return
        user = session.get(User, candidate.user_id)
        if not user or not user.email:
            return

        from app.services.email import send_email

        send_email(
            to=user.email,
            subject=subject,
            body=body,
        )
    except Exception as e:
        logger.warning(
            "Failed to send notification email to candidate %s: %s",
            candidate_id,
            e,
        )
