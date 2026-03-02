"""Weekly Job Market Digest — aggregation, LLM summary, and batch send.

Sends personalized weekly email digests to eligible candidates with new
matches, market trends, salary data, and a hidden-gem job recommendation.
Available to all tiers (free/starter/pro) as a retention driver.
"""

import logging
import os
from datetime import UTC, date, datetime, timedelta

import anthropic
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.job import Job
from app.models.match import Match
from app.models.user import User
from app.models.weekly_digest_log import WeeklyDigestLog
from app.services.email import send_weekly_digest_email

logger = logging.getLogger(__name__)

_HAIKU_MODEL = "claude-haiku-4-5-20251001"

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------


def _get_eligible_candidates(
    session: Session, week_start: date
) -> list[tuple[int, int, str, str | None]]:
    """Return (candidate.id, user.id, email, first_name) for eligible candidates.

    Eligible = consent_marketing True, alert_frequency is NULL or "weekly",
    and no digest log exists for this week_start.
    """
    already_sent = (
        select(WeeklyDigestLog.candidate_id)
        .where(WeeklyDigestLog.week_start == week_start)
        .subquery()
    )

    stmt = (
        select(
            Candidate.id,
            User.id,
            User.email,
            User.first_name,
        )
        .join(User, Candidate.user_id == User.id)
        .outerjoin(already_sent, Candidate.id == already_sent.c.candidate_id)
        .where(
            Candidate.consent_marketing == True,  # noqa: E712
            or_(
                Candidate.alert_frequency.is_(None),
                Candidate.alert_frequency == "weekly",
            ),
            already_sent.c.candidate_id.is_(None),  # not yet sent
        )
    )
    return list(session.execute(stmt).all())


# ---------------------------------------------------------------------------
# Data aggregation
# ---------------------------------------------------------------------------


def _aggregate_user_data(
    session: Session,
    user_id: int,
    week_start: date,
    week_end: date,
) -> dict:
    """Gather match and market data for a single candidate's digest."""
    week_start_dt = datetime(
        week_start.year, week_start.month, week_start.day, tzinfo=UTC
    )
    week_end_dt = datetime(
        week_end.year, week_end.month, week_end.day, 23, 59, 59,
        tzinfo=UTC,
    )

    # New matches this week
    new_matches = (
        session.execute(
            select(Match, Job)
            .join(Job, Match.job_id == Job.id)
            .where(
                Match.user_id == user_id,
                Match.created_at >= week_start_dt,
                Match.created_at <= week_end_dt,
            )
            .order_by(Match.match_score.desc())
        )
        .all()
    )

    new_match_count = len(new_matches)

    # Top 3 matches
    top_matches = []
    for match, job in new_matches[:3]:
        top_matches.append({
            "title": job.title,
            "company": job.company,
            "score": match.match_score,
            "location": job.location,
            "remote": job.remote_flag,
            "job_id": job.id,
        })

    # Hidden gem: score >= 60, not interacted with (application_status IS NULL),
    # created more than 3 days ago, not in this week's top matches
    top_job_ids = {m["job_id"] for m in top_matches}
    cutoff = datetime.now(UTC) - timedelta(days=3)
    gem_row = session.execute(
        select(Match, Job)
        .join(Job, Match.job_id == Job.id)
        .where(
            Match.user_id == user_id,
            Match.match_score >= 60,
            Match.application_status.is_(None),
            Match.created_at < cutoff,
            Match.job_id.notin_(top_job_ids) if top_job_ids else True,
        )
        .order_by(Match.match_score.desc())
        .limit(1)
    ).first()

    hidden_gem = None
    if gem_row:
        gem_match, gem_job = gem_row
        hidden_gem = {
            "title": gem_job.title,
            "company": gem_job.company,
            "score": gem_match.match_score,
            "location": gem_job.location,
            "remote": gem_job.remote_flag,
            "job_id": gem_job.id,
        }

    # Market stats: total active jobs, new this week, avg salary, remote %
    total_active = session.scalar(
        select(func.count()).select_from(Job).where(
            or_(Job.is_active == True, Job.is_active.is_(None))  # noqa: E712
        )
    ) or 0

    new_this_week = session.scalar(
        select(func.count()).select_from(Job).where(
            Job.ingested_at >= week_start_dt,
            Job.ingested_at <= week_end_dt,
        )
    ) or 0

    salary_row = session.execute(
        select(func.avg(Job.salary_min)).where(
            Job.salary_min.isnot(None),
            or_(Job.is_active == True, Job.is_active.is_(None)),  # noqa: E712
        )
    ).scalar() or 0

    remote_count = session.scalar(
        select(func.count()).select_from(Job).where(
            Job.remote_flag == True,  # noqa: E712
            or_(Job.is_active == True, Job.is_active.is_(None)),  # noqa: E712
        )
    ) or 0

    remote_pct = (remote_count / total_active * 100) if total_active else 0

    market_stats = {
        "total_active_jobs": total_active,
        "new_this_week": new_this_week,
        "avg_salary": float(salary_row),
        "remote_pct": round(remote_pct, 1),
    }

    return {
        "new_match_count": new_match_count,
        "top_matches": top_matches,
        "hidden_gem": hidden_gem,
        "market_stats": market_stats,
    }


# ---------------------------------------------------------------------------
# LLM summary
# ---------------------------------------------------------------------------


def _generate_summary(data: dict, first_name: str | None) -> str | None:
    """Generate a 3-paragraph friendly summary using Claude Haiku.

    Returns the summary text, or None if the LLM call fails.
    """
    name = first_name or "there"
    new_count = data["new_match_count"]
    top = data["top_matches"]
    gem = data["hidden_gem"]
    stats = data["market_stats"]

    top_desc = ", ".join(
        f"{m['title']} at {m['company']} ({m['score']}%)" for m in top
    ) or "no new top matches"

    gem_desc = (
        f"Hidden gem: {gem['title']} at {gem['company']} ({gem['score']}%)"
        if gem
        else "No hidden gem this week"
    )

    prompt = (
        f"Write a 3-paragraph friendly email summary for {name} about their "
        f"weekly job market digest. Keep it warm, concise, and encouraging.\n\n"
        f"Data:\n"
        f"- {new_count} new matches this week\n"
        f"- Top matches: {top_desc}\n"
        f"- {gem_desc}\n"
        f"- Market: {stats['total_active_jobs']:,} active jobs, "
        f"{stats['new_this_week']:,} new this week, "
        f"avg salary ${stats['avg_salary']:,.0f}, "
        f"{stats['remote_pct']:.0f}% remote\n\n"
        "Rules:\n"
        "- 3 short paragraphs, no headers or bullet points\n"
        "- First paragraph: greet and summarize matches\n"
        "- Second paragraph: highlight the hidden gem or market insight\n"
        "- Third paragraph: encouraging sign-off\n"
        "- Do NOT include links or calls to action (those are added separately)\n"
        "- Keep total under 150 words"
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        logger.exception("Failed to generate weekly digest summary")
        return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def send_weekly_digests() -> dict:
    """Main orchestrator: send weekly digests to all eligible candidates.

    Returns dict with sent/skipped/errors counts.
    """
    from app.db.session import get_session_factory

    session = get_session_factory()()
    try:
        # Calculate week boundaries (Monday–Sunday of the past week)
        today = date.today()
        # week_end = last Sunday (or today if Sunday)
        days_since_sunday = (today.weekday() + 1) % 7
        week_end = today - timedelta(days=days_since_sunday)
        week_start = week_end - timedelta(days=6)

        logger.info(
            "Weekly digest: processing week %s to %s", week_start, week_end
        )

        candidates = _get_eligible_candidates(session, week_start)
        logger.info("Weekly digest: %d eligible candidates", len(candidates))

        sent = 0
        skipped = 0
        errors = 0

        for candidate_id, user_id, email, first_name in candidates:
            try:
                data = _aggregate_user_data(session, user_id, week_start, week_end)

                # Skip if nothing to report
                if data["new_match_count"] == 0 and data["hidden_gem"] is None:
                    skipped += 1
                    continue

                # Generate LLM summary
                summary = _generate_summary(data, first_name)
                if summary is None:
                    logger.warning(
                        "Skipping digest for candidate %d: LLM summary failed",
                        candidate_id,
                    )
                    skipped += 1
                    continue

                # Send email
                email_id = send_weekly_digest_email(
                    to_email=email,
                    first_name=first_name,
                    summary_text=summary,
                    top_matches=data["top_matches"],
                    hidden_gem=data["hidden_gem"],
                    market_stats=data["market_stats"],
                    new_match_count=data["new_match_count"],
                )

                # Log to database
                log = WeeklyDigestLog(
                    candidate_id=candidate_id,
                    digest_json=data,
                    summary_text=summary,
                    hidden_gem_job_id=(
                        data["hidden_gem"]["job_id"] if data["hidden_gem"] else None
                    ),
                    email_id=email_id,
                    sent_at=datetime.now(UTC),
                    week_start=week_start,
                    week_end=week_end,
                )
                session.add(log)
                session.commit()
                sent += 1

            except Exception:
                logger.exception(
                    "Weekly digest failed for candidate %d", candidate_id
                )
                session.rollback()
                errors += 1

        logger.info(
            "Weekly digest complete: sent=%d skipped=%d errors=%d",
            sent,
            skipped,
            errors,
        )
        return {"sent": sent, "skipped": skipped, "errors": errors}

    except Exception as e:
        logger.exception("Weekly digest batch failed: %s", e)
        session.rollback()
        return {"sent": 0, "skipped": 0, "errors": 1, "error": str(e)}
    finally:
        session.close()
