"""Collaborative hiring workspace router (P53)."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services.auth import get_current_user

router = APIRouter(
    prefix="/api/employer",
    tags=["hiring-workspace"],
)
logger = logging.getLogger(__name__)


def _require_employer(user=Depends(get_current_user)):
    if user.role not in ("employer", "both", "admin"):
        raise HTTPException(403, "Employer role required")
    return user


def _get_employer_id(user, db: Session) -> int:
    from app.models.employer import EmployerProfile

    profile = (
        db.query(EmployerProfile).filter(EmployerProfile.user_id == user.id).first()
    )
    if not profile:
        raise HTTPException(404, "Employer profile not found")
    return profile.id


class FeedbackRequest(BaseModel):
    candidate_profile_id: int
    interview_type: str = "phone_screen"
    rating: int | None = None
    recommendation: str | None = None
    strengths: str | None = None
    concerns: str | None = None
    notes: str | None = None


class TeamInviteRequest(BaseModel):
    user_id: int
    role: str = "viewer"
    job_access: list[int] | None = None


@router.get("/jobs/{job_id}/workspace")
def get_workspace(
    job_id: int,
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Full workspace view: candidates, feedback, status."""
    from app.models.employer import EmployerJob
    from app.models.employer_team import InterviewFeedback

    employer_id = _get_employer_id(user, db)
    job = db.get(EmployerJob, job_id)
    if not job or job.employer_id != employer_id:
        raise HTTPException(404, "Job not found")

    # Get all feedback for this job
    stmt = select(InterviewFeedback).where(InterviewFeedback.employer_job_id == job_id)
    feedback = list(db.execute(stmt).scalars().all())

    feedback_list = [
        {
            "id": f.id,
            "candidate_profile_id": f.candidate_profile_id,
            "interviewer_user_id": f.interviewer_user_id,
            "interview_type": f.interview_type,
            "rating": f.rating,
            "recommendation": f.recommendation,
            "strengths": f.strengths,
            "concerns": f.concerns,
            "notes": f.notes,
            "submitted_at": (f.submitted_at.isoformat() if f.submitted_at else None),
        }
        for f in feedback
    ]

    return {
        "job_id": job_id,
        "title": job.title,
        "status": job.status,
        "feedback": feedback_list,
    }


@router.post("/jobs/{job_id}/feedback")
def submit_feedback(
    job_id: int,
    body: FeedbackRequest,
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Submit interview feedback for a candidate."""
    from app.models.employer import EmployerJob
    from app.models.employer_team import InterviewFeedback

    employer_id = _get_employer_id(user, db)
    job = db.get(EmployerJob, job_id)
    if not job or job.employer_id != employer_id:
        raise HTTPException(404, "Job not found")

    feedback = InterviewFeedback(
        employer_job_id=job_id,
        candidate_profile_id=body.candidate_profile_id,
        interviewer_user_id=user.id,
        interview_type=body.interview_type,
        rating=body.rating,
        recommendation=body.recommendation,
        strengths=body.strengths,
        concerns=body.concerns,
        notes=body.notes,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return {
        "id": feedback.id,
        "status": "submitted",
    }


@router.get("/jobs/{job_id}/scorecard")
def get_scorecard(
    job_id: int,
    candidate_profile_id: int | None = None,
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Aggregated interview scorecard per candidate."""
    from app.models.employer import EmployerJob
    from app.models.employer_team import InterviewFeedback

    employer_id = _get_employer_id(user, db)
    job = db.get(EmployerJob, job_id)
    if not job or job.employer_id != employer_id:
        raise HTTPException(404, "Job not found")

    stmt = select(InterviewFeedback).where(InterviewFeedback.employer_job_id == job_id)
    if candidate_profile_id:
        stmt = stmt.where(
            InterviewFeedback.candidate_profile_id == candidate_profile_id
        )

    feedback = list(db.execute(stmt).scalars().all())

    # Group by candidate
    by_candidate: dict[int, list] = {}
    for f in feedback:
        cid = f.candidate_profile_id
        if cid not in by_candidate:
            by_candidate[cid] = []
        by_candidate[cid].append(
            {
                "interviewer_id": f.interviewer_user_id,
                "type": f.interview_type,
                "rating": f.rating,
                "recommendation": f.recommendation,
            }
        )

    scorecards = []
    for cid, reviews in by_candidate.items():
        ratings = [r["rating"] for r in reviews if r["rating"]]
        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None
        scorecards.append(
            {
                "candidate_profile_id": cid,
                "total_reviews": len(reviews),
                "avg_rating": avg_rating,
                "reviews": reviews,
            }
        )

    return {"job_id": job_id, "scorecards": scorecards}


@router.post("/team/invite")
def invite_team_member(
    body: TeamInviteRequest,
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Invite a team member to the hiring workspace."""
    from app.models.employer_team import EmployerTeamMember

    employer_id = _get_employer_id(user, db)

    member = EmployerTeamMember(
        employer_id=employer_id,
        user_id=body.user_id,
        role=body.role,
        job_access=body.job_access,
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    return {"id": member.id, "status": "invited"}


@router.get("/team")
def list_team_members(
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """List all team members for the employer."""
    from app.models.employer_team import EmployerTeamMember

    employer_id = _get_employer_id(user, db)
    stmt = select(EmployerTeamMember).where(
        EmployerTeamMember.employer_id == employer_id
    )
    members = list(db.execute(stmt).scalars().all())

    return [
        {
            "id": m.id,
            "user_id": m.user_id,
            "role": m.role,
            "job_access": m.job_access,
            "invited_at": (m.invited_at.isoformat() if m.invited_at else None),
            "accepted_at": (m.accepted_at.isoformat() if m.accepted_at else None),
        }
        for m in members
    ]


class TeamMemberUpdate(BaseModel):
    role: str | None = None
    job_access: list[int] | None = None


_ALLOWED_TEAM_ROLES = ("viewer", "reviewer", "editor", "admin")


@router.patch("/team/{member_id}")
def update_team_member(
    member_id: int,
    body: TeamMemberUpdate,
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Update a team member's role or job access."""
    from app.models.employer_team import EmployerTeamMember

    employer_id = _get_employer_id(user, db)
    member = db.execute(
        select(EmployerTeamMember).where(
            EmployerTeamMember.id == member_id,
            EmployerTeamMember.employer_id == employer_id,
        )
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(404, "Team member not found")

    if body.role is not None:
        if body.role not in _ALLOWED_TEAM_ROLES:
            raise HTTPException(
                400,
                f"Invalid role. Must be one of: {', '.join(_ALLOWED_TEAM_ROLES)}",
            )
        member.role = body.role
    if body.job_access is not None:
        member.job_access = body.job_access

    db.commit()
    db.refresh(member)

    return {
        "id": member.id,
        "user_id": member.user_id,
        "role": member.role,
        "job_access": member.job_access,
        "invited_at": (member.invited_at.isoformat() if member.invited_at else None),
        "accepted_at": (member.accepted_at.isoformat() if member.accepted_at else None),
    }


@router.delete("/team/{member_id}", status_code=204)
def remove_team_member(
    member_id: int,
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Remove a team member from the hiring workspace."""
    from app.models.employer_team import EmployerTeamMember

    employer_id = _get_employer_id(user, db)
    member = db.execute(
        select(EmployerTeamMember).where(
            EmployerTeamMember.id == member_id,
            EmployerTeamMember.employer_id == employer_id,
        )
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(404, "Team member not found")

    db.delete(member)
    db.commit()
