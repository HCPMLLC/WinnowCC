"""Career Intelligence router.

AI-powered recruiter/employer tools + LinkedIn sourcing (v2).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate_profile import CandidateProfile
from app.models.user import User
from app.services.auth import get_current_user, require_employer
from app.services.career_intelligence import (
    compute_market_position,
    generate_candidate_brief,
    predict_career_trajectory,
    predict_time_to_fill,
    salary_intelligence,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/career-intelligence",
    tags=["career-intelligence"],
)


# ---------------------------------------------------------------------------
# Brief generation
# ---------------------------------------------------------------------------
@router.post("/brief/{candidate_profile_id}")
def create_brief(
    candidate_profile_id: int,
    job_id: int | None = Query(None),
    brief_type: str = Query("general"),
    user: User = Depends(require_employer),
    db: Session = Depends(get_session),
):
    """Generate an AI candidate brief for a recruiter."""
    if brief_type not in ("general", "job_specific", "submittal"):
        raise HTTPException(
            status_code=400,
            detail="brief_type must be general, job_specific, or submittal",
        )
    try:
        return generate_candidate_brief(
            candidate_profile_id=candidate_profile_id,
            employer_job_id=job_id,
            brief_type=brief_type,
            user_id=user.id,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("Brief generation failed for profile %s", candidate_profile_id)
        msg = str(e)
        if "credit balance" in msg or "billing" in msg.lower():
            raise HTTPException(status_code=503, detail="AI service temporarily unavailable. Please try again later.") from e
        raise HTTPException(status_code=500, detail="Failed to generate brief. Please try again.") from e


# ---------------------------------------------------------------------------
# Market position
# ---------------------------------------------------------------------------
@router.get("/market-position/{candidate_profile_id}/{job_id}")
def get_market_position(
    candidate_profile_id: int,
    job_id: int,
    user: User = Depends(require_employer),
    db: Session = Depends(get_session),
):
    """Get candidate's percentile ranking among all matches for a job."""
    return compute_market_position(candidate_profile_id, job_id, db)


# ---------------------------------------------------------------------------
# Salary intelligence
# ---------------------------------------------------------------------------
@router.get("/salary")
def get_salary_intel(
    role: str = Query(..., min_length=2),
    location: str | None = Query(None),
    user: User = Depends(require_employer),
    db: Session = Depends(get_session),
):
    """Get salary percentiles for a role and location."""
    return salary_intelligence(role, location, db)


# ---------------------------------------------------------------------------
# Time-to-fill
# ---------------------------------------------------------------------------
@router.get("/time-to-fill/{job_id}")
def get_time_to_fill(
    job_id: int,
    user: User = Depends(require_employer),
    db: Session = Depends(get_session),
):
    """Predict time-to-fill for an employer job."""
    try:
        return predict_time_to_fill(job_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Career trajectory
# ---------------------------------------------------------------------------
@router.get("/trajectory/{candidate_profile_id}")
def get_trajectory(
    candidate_profile_id: int,
    user: User = Depends(require_employer),
    db: Session = Depends(get_session),
):
    """Predict career trajectory for a candidate."""
    try:
        return predict_career_trajectory(candidate_profile_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------------------------------------------------------------------------
# LinkedIn sourcing endpoint (Chrome extension)
# ---------------------------------------------------------------------------
class LinkedInProfilePayload(BaseModel):
    name: str
    headline: str | None = None
    location: str | None = None
    linkedin_url: str
    photo_url: str | None = None
    current_company: str | None = None
    experience: list[dict] | None = None
    education: list[dict] | None = None
    skills: list[str | dict] | None = None  # str (legacy) or {name, endorsements}
    tag_job_id: int | None = None
    about: str | None = None
    certifications: list[dict] | None = None
    volunteer: list[dict] | None = None
    publications: list[dict] | None = None
    projects: list[dict] | None = None
    contact_info: dict | None = None
    open_to_work: bool | None = None
    recommendations_count: int | None = None


def _require_sourcing_role(user: User = Depends(get_current_user)) -> User:
    """Allow employer, recruiter, or admin to source candidates."""
    if user.role not in ("employer", "recruiter", "both", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Employer or recruiter access required.",
        )
    return user


def _estimate_years_experience(experience: list[dict]) -> int | None:
    """Estimate total years from experience date_range fields."""
    import re
    from datetime import datetime as _dt

    total_months = 0
    month_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    for entry in experience:
        dr = (entry.get("date_range") or "").lower()
        if not dr:
            continue
        # Match patterns like "Oct 2013 - Present" or "Mar 2005 - Jun 2008"
        parts = re.split(r"\s*[-–—]\s*", dr)
        if len(parts) < 2:
            continue

        def parse_month_year(text: str):
            text = text.strip()
            if "present" in text:
                now = _dt.now()
                return now.year, now.month
            m = re.search(
                r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{4})",
                text,
            )
            if m:
                return int(m.group(2)), month_map.get(m.group(1)[:3], 1)
            # Just a year
            ym = re.search(r"(\d{4})", text)
            if ym:
                return int(ym.group(1)), 1
            return None, None

        y1, m1 = parse_month_year(parts[0])
        y2, m2 = parse_month_year(parts[-1])
        if y1 and y2:
            months = (y2 - y1) * 12 + (m2 - m1)
            if 0 < months < 600:  # sanity: up to 50 years
                total_months += months

    return round(total_months / 12) if total_months > 0 else None


@router.post("/source/linkedin")
def source_from_linkedin(
    payload: LinkedInProfilePayload,
    user: User = Depends(_require_sourcing_role),
    db: Session = Depends(get_session),
):
    """Import a candidate profile from LinkedIn via Chrome extension.

    De-duplicates by LinkedIn URL. Creates or updates CandidateProfile.
    """
    try:
        return _source_from_linkedin_impl(payload, user, db)
    except HTTPException:
        raise
    except Exception:
        logger.exception("LinkedIn source failed for %s", payload.linkedin_url)
        raise HTTPException(
            status_code=500, detail="Failed to save LinkedIn profile."
        )


def _source_from_linkedin_impl(
    payload: LinkedInProfilePayload,
    user: User,
    db: Session,
):
    # Normalize LinkedIn URL (strip trailing slash for consistent matching)
    linkedin_url = payload.linkedin_url.rstrip("/")

    # Check for existing profile by LinkedIn URL (try both with and without trailing /)
    # Use .first() instead of .scalar_one_or_none() to avoid MultipleResultsFound
    existing = db.execute(
        select(CandidateProfile).where(
            CandidateProfile.profile_json["linkedin_url"].astext.in_(
                [linkedin_url, linkedin_url + "/"]
            )
        )
    ).scalars().first()

    # Parse name into first/last
    name_parts = (payload.name or "").split(",")[0].strip().split()
    first_name = name_parts[0] if name_parts else None
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else None

    # Parse location into city/state
    location = payload.location or ""
    city, state = None, None
    if location:
        loc_parts = [p.strip() for p in location.split(",")]
        if len(loc_parts) >= 2:
            city = loc_parts[0]
            state = loc_parts[1]
        elif len(loc_parts) == 1:
            city = loc_parts[0]

    # Estimate total years from experience date ranges
    total_years = _estimate_years_experience(payload.experience or [])

    # Extract contact info
    contact = payload.contact_info or {}

    # Normalize skills to list of strings for consistency
    skill_list = []
    for s in (payload.skills or []):
        if isinstance(s, dict):
            skill_list.append(s.get("name", str(s)))
        else:
            skill_list.append(str(s))

    # Build profile in the standard "basics" structure used by the rest of the app
    profile_data = {
        "basics": {
            "name": payload.name,
            "first_name": first_name,
            "last_name": last_name,
            "email": contact.get("email"),
            "phone": contact.get("phone"),
            "location": location,
            "headline": payload.headline,
            "work_authorization": None,
            "total_years_experience": total_years,
        },
        "experience": payload.experience or [],
        "education": payload.education or [],
        "skills": skill_list,
        "certifications": payload.certifications or [],
        "volunteer": payload.volunteer or [],
        "publications": payload.publications or [],
        "projects": payload.projects or [],
        "about": payload.about,
        "linkedin_url": linkedin_url,
        "photo_url": payload.photo_url,
        "current_company": payload.current_company,
        "open_to_work": payload.open_to_work,
        "recommendations_count": payload.recommendations_count,
        "contact_info": payload.contact_info,
        "source": "linkedin_extension",
        "sourced_by_user_id": user.id,
    }

    if existing:
        # Update existing profile
        merged = {**(existing.profile_json or {}), **profile_data}
        existing.profile_json = merged
        db.commit()
        return {
            "candidate_profile_id": existing.id,
            "status": "updated",
            "message": "Existing profile updated with latest LinkedIn data",
        }

    # Create new profile (linked to a placeholder user)
    # Extract slug from URL: ".../in/jacewoody" → "jacewoody"
    slug = linkedin_url.split("/")[-1] or linkedin_url.split("/")[-2] or "unknown"
    placeholder_email = f"linkedin-{slug}@sourced.winnow"

    # Check if placeholder user already exists (from a previous failed attempt)
    existing_user = db.execute(
        select(User).where(User.email == placeholder_email)
    ).scalar_one_or_none()

    if existing_user:
        target_user = existing_user
    else:
        target_user = User(
            email=placeholder_email,
            password_hash="",
            role="candidate",
        )
        db.add(target_user)
        db.flush()

    new_profile = CandidateProfile(
        user_id=target_user.id,
        version=1,
        profile_json=profile_data,
    )
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)

    return {
        "candidate_profile_id": new_profile.id,
        "status": "created",
        "message": "New candidate profile created from LinkedIn",
    }
