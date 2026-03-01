"""Stage rule engine for automated pipeline advancement."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recruiter_activity import RecruiterActivity
from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
from app.models.stage_rule import StageRule

logger = logging.getLogger(__name__)


def evaluate_rules(
    session: Session,
    pipeline_candidate: RecruiterPipelineCandidate,
) -> list[str]:
    """Evaluate all active rules for a candidate, auto-advance if matched.

    Returns list of stage transitions applied (e.g. ["sourced→qualified"]).
    """
    profile_id = pipeline_candidate.recruiter_profile_id
    job_id = pipeline_candidate.recruiter_job_id

    stmt = select(StageRule).where(
        StageRule.recruiter_profile_id == profile_id,
        StageRule.is_active.is_(True),
        StageRule.from_stage == pipeline_candidate.stage,
    )
    rules = session.execute(stmt).scalars().all()

    transitions: list[str] = []
    for rule in rules:
        # Skip job-specific rules that don't match
        if rule.recruiter_job_id and rule.recruiter_job_id != job_id:
            continue

        if _check_condition(rule, pipeline_candidate):
            old = pipeline_candidate.stage
            pipeline_candidate.stage = rule.to_stage
            transitions.append(f"{old}→{rule.to_stage}")

            # Log the auto-advancement
            activity = RecruiterActivity(
                recruiter_profile_id=profile_id,
                pipeline_candidate_id=pipeline_candidate.id,
                recruiter_job_id=job_id,
                activity_type="stage_change",
                subject=f"Auto-advanced: {old} → {rule.to_stage}",
                activity_metadata={
                    "old_stage": old,
                    "new_stage": rule.to_stage,
                    "auto_rule_id": rule.id,
                },
            )
            session.add(activity)
            break  # One transition per evaluation

    return transitions


def _check_condition(
    rule: StageRule,
    pc: RecruiterPipelineCandidate,
) -> bool:
    """Check if a rule's condition is met for the given candidate."""
    ct = rule.condition_type
    val = rule.condition_value

    if ct == "match_score_above":
        threshold = float(val)
        return (pc.match_score or 0) >= threshold

    if ct == "rating_above":
        threshold = int(val)
        return (pc.rating or 0) >= threshold

    if ct == "days_in_stage":
        max_days = int(val)
        if not pc.updated_at and not pc.created_at:
            return False
        last_change = pc.updated_at or pc.created_at
        days = (datetime.now(UTC) - last_change).days
        return days >= max_days

    if ct == "tag_present":
        tags = pc.tags or []
        return val in tags

    return False


def apply_rules_to_batch(
    session: Session,
    recruiter_profile_id: int,
) -> int:
    """Process all pipeline candidates against all active rules.

    Returns count of candidates advanced.
    """
    candidates = (
        session.execute(
            select(RecruiterPipelineCandidate).where(
                RecruiterPipelineCandidate.recruiter_profile_id == recruiter_profile_id,
                RecruiterPipelineCandidate.stage.notin_(["hired", "rejected"]),
            )
        )
        .scalars()
        .all()
    )

    advanced = 0
    for pc in candidates:
        transitions = evaluate_rules(session, pc)
        if transitions:
            advanced += 1

    if advanced:
        session.flush()

    return advanced


def create_rule(
    session: Session,
    recruiter_profile_id: int,
    data: dict,
) -> StageRule:
    """Create a new stage rule."""
    rule = StageRule(recruiter_profile_id=recruiter_profile_id, **data)
    session.add(rule)
    session.flush()
    return rule


def list_rules(
    session: Session,
    recruiter_profile_id: int,
) -> list[StageRule]:
    """List all rules for a recruiter."""
    return list(
        session.execute(
            select(StageRule)
            .where(StageRule.recruiter_profile_id == recruiter_profile_id)
            .order_by(StageRule.created_at.desc())
        )
        .scalars()
        .all()
    )


def update_rule(
    session: Session,
    recruiter_profile_id: int,
    rule_id: int,
    data: dict,
) -> StageRule | None:
    """Update a stage rule."""
    rule = session.execute(
        select(StageRule).where(
            StageRule.id == rule_id,
            StageRule.recruiter_profile_id == recruiter_profile_id,
        )
    ).scalar_one_or_none()
    if rule is None:
        return None
    for field, value in data.items():
        setattr(rule, field, value)
    session.flush()
    return rule


def delete_rule(
    session: Session,
    recruiter_profile_id: int,
    rule_id: int,
) -> bool:
    """Delete a stage rule. Returns True if found and deleted."""
    rule = session.execute(
        select(StageRule).where(
            StageRule.id == rule_id,
            StageRule.recruiter_profile_id == recruiter_profile_id,
        )
    ).scalar_one_or_none()
    if rule is None:
        return False
    session.delete(rule)
    session.flush()
    return True
