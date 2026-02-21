# PROMPT 36: Two-Sided Marketplace - Backend Routes (API Endpoints)

## Objective
Implement FastAPI router with all employer-related API endpoints: profile management, job posting CRUD, candidate search, saved candidates, and analytics. Includes role-based authentication and subscription limit enforcement.

---

## Context
With the database schema (PROMPT33), models (PROMPT34), and schemas (PROMPT35) in place, we can now build the actual API endpoints that will be consumed by the frontend. This includes creating jobs, searching candidates, tracking views, and enforcing subscription limits.

---

## Prerequisites
- ✅ PROMPT33 completed (database schema)
- ✅ PROMPT34 completed (SQLAlchemy models)
- ✅ PROMPT35 completed (Pydantic schemas)
- ✅ Existing auth system (`get_current_user` dependency)

---

## Implementation Steps

### Step 1: Update Auth Dependencies

**Location:** `services/api/app/dependencies.py`

**Instructions:** Add role-based authentication functions.

**What to add:**

```python
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.employer import EmployerProfile
from app.models.candidate import CandidateProfile

# ... existing imports and get_current_user function ...


async def require_candidate(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Require user to have candidate role.
    
    Raises:
        HTTPException: 403 if user is not a candidate
    """
    if current_user.role not in ["candidate", "both"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate access required. Please create a candidate profile."
        )
    return current_user


async def require_employer(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Require user to have employer role.
    
    Raises:
        HTTPException: 403 if user is not an employer
    """
    if current_user.role not in ["employer", "both"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employer access required. Please create an employer profile."
        )
    return current_user


async def get_employer_profile(
    current_user: User = Depends(require_employer),
    db: Session = Depends(get_db)
) -> EmployerProfile:
    """
    Get the employer profile for the current user.
    
    Raises:
        HTTPException: 404 if employer profile not found
    """
    employer = db.query(EmployerProfile).filter(
        EmployerProfile.user_id == current_user.id
    ).first()
    
    if not employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employer profile not found. Please complete profile setup."
        )
    
    return employer


async def get_candidate_profile(
    current_user: User = Depends(require_candidate),
    db: Session = Depends(get_db)
) -> CandidateProfile:
    """
    Get the candidate profile for the current user.
    
    Raises:
        HTTPException: 404 if candidate profile not found
    """
    candidate = db.query(CandidateProfile).filter(
        CandidateProfile.user_id == current_user.id
    ).first()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate profile not found. Please complete profile setup."
        )
    
    return candidate
```

---

### Step 2: Create Employer Router

**Location:** Create new file `services/api/app/routers/employer.py`

**Instructions:** Create this large file with all employer endpoints.

**Code:**

```python
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from app.database import get_db
from app.dependencies import require_employer, get_employer_profile
from app.models.employer import (
    EmployerProfile,
    EmployerJob,
    EmployerCandidateView,
    EmployerSavedCandidate
)
from app.models.candidate import CandidateProfile
from app.models.user import User
from app.schemas.employer import (
    EmployerProfileCreate,
    EmployerProfileUpdate,
    EmployerProfileResponse,
    EmployerJobCreate,
    EmployerJobUpdate,
    EmployerJobResponse,
    CandidateSearchFilters,
    CandidateSearchResult,
    SaveCandidateRequest,
    SavedCandidateResponse,
    EmployerAnalyticsSummary,
    MessageResponse,
)

router = APIRouter(prefix="/api/employer", tags=["employer"])


# ============================================================================
# PROFILE MANAGEMENT
# ============================================================================

@router.post("/profile", response_model=EmployerProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_employer_profile(
    profile_data: EmployerProfileCreate,
    current_user: User = Depends(require_employer),
    db: Session = Depends(get_db)
):
    """
    Create employer profile for current user.
    
    Returns:
        Created employer profile with default free tier subscription
    
    Raises:
        400: If profile already exists
    """
    # Check if profile already exists
    existing = db.query(EmployerProfile).filter(
        EmployerProfile.user_id == current_user.id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employer profile already exists for this user"
        )
    
    # Create profile with free tier by default
    employer = EmployerProfile(
        user_id=current_user.id,
        **profile_data.model_dump()
    )
    db.add(employer)
    db.commit()
    db.refresh(employer)
    
    return employer


@router.get("/profile", response_model=EmployerProfileResponse)
async def get_my_employer_profile(
    employer: EmployerProfile = Depends(get_employer_profile)
):
    """
    Get current user's employer profile.
    
    Returns:
        Employer profile with subscription details
    """
    return employer


@router.patch("/profile", response_model=EmployerProfileResponse)
async def update_employer_profile(
    profile_data: EmployerProfileUpdate,
    employer: EmployerProfile = Depends(get_employer_profile),
    db: Session = Depends(get_db)
):
    """
    Update employer profile.
    
    Args:
        profile_data: Fields to update (all optional)
    
    Returns:
        Updated employer profile
    """
    update_data = profile_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(employer, field, value)
    
    db.commit()
    db.refresh(employer)
    
    return employer


# ============================================================================
# JOB MANAGEMENT
# ============================================================================

@router.post("/jobs", response_model=EmployerJobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: EmployerJobCreate,
    employer: EmployerProfile = Depends(get_employer_profile),
    db: Session = Depends(get_db)
):
    """
    Create a new job posting.
    
    Subscription limits:
    - Free: 1 active job
    - Starter: 5 active jobs
    - Pro: Unlimited
    - Enterprise: Unlimited
    
    Returns:
        Created job in 'draft' status
    
    Raises:
        403: If subscription limit reached
    """
    # Check subscription limits
    if employer.subscription_tier == "free":
        active_jobs_count = db.query(EmployerJob).filter(
            EmployerJob.employer_id == employer.id,
            EmployerJob.status.in_(["active", "draft"])
        ).count()
        
        if active_jobs_count >= 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Free tier allows only 1 active job. Please upgrade to post more jobs."
            )
    
    elif employer.subscription_tier == "starter":
        active_jobs_count = db.query(EmployerJob).filter(
            EmployerJob.employer_id == employer.id,
            EmployerJob.status.in_(["active", "draft"])
        ).count()
        
        if active_jobs_count >= 5:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Starter tier allows 5 active jobs. Please upgrade to Pro for unlimited jobs."
            )
    
    # Create job
    job = EmployerJob(
        employer_id=employer.id,
        **job_data.model_dump()
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    return job


@router.get("/jobs", response_model=List[EmployerJobResponse])
async def list_my_jobs(
    status_filter: Optional[str] = Query(None, description="Filter by status: draft, active, paused, closed"),
    employer: EmployerProfile = Depends(get_employer_profile),
    db: Session = Depends(get_db)
):
    """
    List all jobs posted by this employer.
    
    Args:
        status_filter: Optional filter by job status
    
    Returns:
        List of jobs ordered by creation date (newest first)
    """
    query = db.query(EmployerJob).filter(EmployerJob.employer_id == employer.id)
    
    if status_filter:
        if status_filter not in ["draft", "active", "paused", "closed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status filter. Must be: draft, active, paused, or closed"
            )
        query = query.filter(EmployerJob.status == status_filter)
    
    jobs = query.order_by(EmployerJob.created_at.desc()).all()
    return jobs


@router.get("/jobs/{job_id}", response_model=EmployerJobResponse)
async def get_job(
    job_id: UUID,
    employer: EmployerProfile = Depends(get_employer_profile),
    db: Session = Depends(get_db)
):
    """
    Get a specific job by ID.
    
    Returns:
        Job details
    
    Raises:
        404: If job not found or doesn't belong to employer
    """
    job = db.query(EmployerJob).filter(
        EmployerJob.id == job_id,
        EmployerJob.employer_id == employer.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return job


@router.patch("/jobs/{job_id}", response_model=EmployerJobResponse)
async def update_job(
    job_id: UUID,
    job_data: EmployerJobUpdate,
    employer: EmployerProfile = Depends(get_employer_profile),
    db: Session = Depends(get_db)
):
    """
    Update a job posting.
    
    Special behavior:
    - If status changes to 'active' and posted_at is null, sets posted_at to now
    - All fields are optional
    
    Returns:
        Updated job
    
    Raises:
        404: If job not found
    """
    job = db.query(EmployerJob).filter(
        EmployerJob.id == job_id,
        EmployerJob.employer_id == employer.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    update_data = job_data.model_dump(exclude_unset=True)
    
    # If publishing for the first time, set posted_at
    if update_data.get("status") == "active" and not job.posted_at:
        update_data["posted_at"] = datetime.utcnow()
    
    for field, value in update_data.items():
        setattr(job, field, value)
    
    db.commit()
    db.refresh(job)
    
    return job


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: UUID,
    employer: EmployerProfile = Depends(get_employer_profile),
    db: Session = Depends(get_db)
):
    """
    Delete a job posting.
    
    Note: This is a hard delete. Consider setting status to 'closed' instead.
    
    Raises:
        404: If job not found
    """
    job = db.query(EmployerJob).filter(
        EmployerJob.id == job_id,
        EmployerJob.employer_id == employer.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    db.delete(job)
    db.commit()
    
    return None


# ============================================================================
# CANDIDATE SEARCH
# ============================================================================

@router.post("/candidates/search", response_model=List[CandidateSearchResult])
async def search_candidates(
    filters: CandidateSearchFilters,
    limit: int = Query(20, le=100, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    employer: EmployerProfile = Depends(get_employer_profile),
    db: Session = Depends(get_db)
):
    """
    Search for candidates based on filters.
    
    Subscription limits on views (enforced when viewing full profile):
    - Free: 10 candidate views per month
    - Starter: 50 views per month
    - Pro: 200 views per month
    - Enterprise: Unlimited
    
    Note: Search itself doesn't count as a "view" - only viewing full profile does
    
    Returns:
        List of matching candidates (may be anonymized based on visibility settings)
    """
    # Build query - only show candidates who are open to opportunities
    query = db.query(CandidateProfile).filter(
        CandidateProfile.open_to_opportunities == True,
        CandidateProfile.profile_visibility.in_(["public", "anonymous"])
    )
    
    # Apply filters
    if filters.skills:
        # This is simplified - in production you'd want full-text search or vector search
        for skill in filters.skills:
            query = query.filter(
                CandidateProfile.profile_data["skills"].astext.ilike(f"%{skill}%")
            )
    
    if filters.experience_years_min is not None:
        query = query.filter(
            CandidateProfile.years_experience >= filters.experience_years_min
        )
    
    if filters.experience_years_max is not None:
        query = query.filter(
            CandidateProfile.years_experience <= filters.experience_years_max
        )
    
    if filters.locations:
        # Simple location matching - production would use geocoding
        location_filters = [
            CandidateProfile.profile_data["location"].astext.ilike(f"%{loc}%")
            for loc in filters.locations
        ]
        query = query.filter(or_(*location_filters))
    
    if filters.job_titles:
        # Match against job titles in experience
        title_filters = [
            CandidateProfile.profile_data["experience"].astext.ilike(f"%{title}%")
            for title in filters.job_titles
        ]
        query = query.filter(or_(*title_filters))
    
    # Execute query with pagination
    candidates = query.offset(offset).limit(limit).all()
    
    # Convert to response format
    results = []
    for candidate in candidates:
        # Extract top skills from profile_data
        skills = []
        if candidate.profile_data and "skills" in candidate.profile_data:
            skills = candidate.profile_data["skills"][:5]  # Top 5 skills
        
        # Anonymize if needed
        name = candidate.name
        if candidate.profile_visibility == "anonymous":
            name = f"Candidate {str(candidate.id)[:8]}"
        
        results.append(CandidateSearchResult(
            id=candidate.id,
            name=name,
            headline=candidate.profile_data.get("headline") if candidate.profile_data else None,
            location=candidate.profile_data.get("location") if candidate.profile_data else None,
            years_experience=candidate.years_experience,
            top_skills=skills,
            match_score=None,  # TODO: Implement matching algorithm in future
            profile_visibility=candidate.profile_visibility
        ))
    
    return results


@router.get("/candidates/{candidate_id}")
async def view_candidate_profile(
    candidate_id: UUID,
    employer: EmployerProfile = Depends(get_employer_profile),
    db: Session = Depends(get_db)
):
    """
    View detailed candidate profile.
    
    This counts as a "view" and is subject to subscription limits:
    - Free: 10 views/month
    - Starter: 50 views/month
    - Pro: 200 views/month
    - Enterprise: Unlimited
    
    Returns:
        Full or anonymized profile based on candidate's visibility settings
    
    Raises:
        403: If monthly view limit exceeded
        404: If candidate not found or not open to opportunities
    """
    # Check subscription limits
    if employer.subscription_tier in ["free", "starter", "pro"]:
        # Calculate views this month
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        views_this_month = db.query(EmployerCandidateView).filter(
            EmployerCandidateView.employer_id == employer.id,
            EmployerCandidateView.viewed_at >= month_start
        ).count()
        
        # Check limits
        limits = {
            "free": 10,
            "starter": 50,
            "pro": 200
        }
        
        if views_this_month >= limits[employer.subscription_tier]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{employer.subscription_tier.capitalize()} tier allows {limits[employer.subscription_tier]} candidate views per month. Please upgrade for more views."
            )
    
    # Get candidate
    candidate = db.query(CandidateProfile).filter(
        CandidateProfile.id == candidate_id,
        CandidateProfile.open_to_opportunities == True
    ).first()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found or not open to opportunities"
        )
    
    # Log the view
    view = EmployerCandidateView(
        employer_id=employer.id,
        candidate_id=candidate_id,
        source="search"
    )
    db.add(view)
    db.commit()
    
    # Return anonymized or full profile based on visibility
    if candidate.profile_visibility == "anonymous":
        return {
            "id": candidate.id,
            "name": f"Candidate {str(candidate.id)[:8]}",
            "headline": candidate.profile_data.get("headline") if candidate.profile_data else None,
            "years_experience": candidate.years_experience,
            "skills": candidate.profile_data.get("skills", []) if candidate.profile_data else [],
            "experience": candidate.profile_data.get("experience", []) if candidate.profile_data else [],
            "education": candidate.profile_data.get("education", []) if candidate.profile_data else [],
            "anonymized": True
        }
    
    # Full profile
    return {
        "id": candidate.id,
        "name": candidate.name,
        "profile_data": candidate.profile_data,
        "years_experience": candidate.years_experience,
        "anonymized": False
    }


# ============================================================================
# SAVED CANDIDATES
# ============================================================================

@router.post("/candidates/save", response_model=SavedCandidateResponse, status_code=status.HTTP_201_CREATED)
async def save_candidate(
    request: SaveCandidateRequest,
    employer: EmployerProfile = Depends(get_employer_profile),
    db: Session = Depends(get_db)
):
    """
    Save a candidate to favorites.
    
    Args:
        request: Candidate ID and optional notes
    
    Returns:
        Saved candidate with details
    
    Raises:
        400: If candidate already saved
        404: If candidate not found
    """
    # Check if already saved
    existing = db.query(EmployerSavedCandidate).filter(
        EmployerSavedCandidate.employer_id == employer.id,
        EmployerSavedCandidate.candidate_id == request.candidate_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Candidate already saved"
        )
    
    # Verify candidate exists
    candidate = db.query(CandidateProfile).filter(
        CandidateProfile.id == request.candidate_id
    ).first()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )
    
    # Save candidate
    saved = EmployerSavedCandidate(
        employer_id=employer.id,
        candidate_id=request.candidate_id,
        notes=request.notes
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    
    # Build response with candidate info
    skills = candidate.profile_data.get("skills", [])[:5] if candidate.profile_data else []
    
    return SavedCandidateResponse(
        id=saved.id,
        candidate_id=candidate.id,
        notes=saved.notes,
        saved_at=saved.saved_at,
        candidate=CandidateSearchResult(
            id=candidate.id,
            name=candidate.name if candidate.profile_visibility == "public" else f"Candidate {str(candidate.id)[:8]}",
            headline=candidate.profile_data.get("headline") if candidate.profile_data else None,
            location=candidate.profile_data.get("location") if candidate.profile_data else None,
            years_experience=candidate.years_experience,
            top_skills=skills,
            match_score=None,
            profile_visibility=candidate.profile_visibility
        )
    )


@router.get("/candidates/saved", response_model=List[SavedCandidateResponse])
async def list_saved_candidates(
    employer: EmployerProfile = Depends(get_employer_profile),
    db: Session = Depends(get_db)
):
    """
    List all saved candidates.
    
    Returns:
        List of saved candidates ordered by save date (newest first)
    """
    saved = db.query(EmployerSavedCandidate).filter(
        EmployerSavedCandidate.employer_id == employer.id
    ).order_by(EmployerSavedCandidate.saved_at.desc()).all()
    
    results = []
    for s in saved:
        candidate = s.candidate
        skills = candidate.profile_data.get("skills", [])[:5] if candidate.profile_data else []
        
        results.append(SavedCandidateResponse(
            id=s.id,
            candidate_id=candidate.id,
            notes=s.notes,
            saved_at=s.saved_at,
            candidate=CandidateSearchResult(
                id=candidate.id,
                name=candidate.name if candidate.profile_visibility == "public" else f"Candidate {str(candidate.id)[:8]}",
                headline=candidate.profile_data.get("headline") if candidate.profile_data else None,
                location=candidate.profile_data.get("location") if candidate.profile_data else None,
                years_experience=candidate.years_experience,
                top_skills=skills,
                match_score=None,
                profile_visibility=candidate.profile_visibility
            )
        ))
    
    return results


@router.delete("/candidates/saved/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_candidate(
    saved_id: UUID,
    employer: EmployerProfile = Depends(get_employer_profile),
    db: Session = Depends(get_db)
):
    """
    Remove a candidate from saved list.
    
    Raises:
        404: If saved candidate not found
    """
    saved = db.query(EmployerSavedCandidate).filter(
        EmployerSavedCandidate.id == saved_id,
        EmployerSavedCandidate.employer_id == employer.id
    ).first()
    
    if not saved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved candidate not found"
        )
    
    db.delete(saved)
    db.commit()
    
    return None


# ============================================================================
# ANALYTICS
# ============================================================================

@router.get("/analytics/summary", response_model=EmployerAnalyticsSummary)
async def get_analytics_summary(
    employer: EmployerProfile = Depends(get_employer_profile),
    db: Session = Depends(get_db)
):
    """
    Get analytics summary for employer dashboard.
    
    Returns:
        Summary statistics including job metrics, candidate views, and subscription info
    """
    # Count active jobs
    active_jobs = db.query(EmployerJob).filter(
        EmployerJob.employer_id == employer.id,
        EmployerJob.status == "active"
    ).count()
    
    # Total job views
    total_views = db.query(func.sum(EmployerJob.view_count)).filter(
        EmployerJob.employer_id == employer.id
    ).scalar() or 0
    
    # Total applications
    total_applications = db.query(func.sum(EmployerJob.application_count)).filter(
        EmployerJob.employer_id == employer.id
    ).scalar() or 0
    
    # Candidate views this month
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    candidate_views_this_month = db.query(EmployerCandidateView).filter(
        EmployerCandidateView.employer_id == employer.id,
        EmployerCandidateView.viewed_at >= month_start
    ).count()
    
    # Saved candidates
    saved_candidates = db.query(EmployerSavedCandidate).filter(
        EmployerSavedCandidate.employer_id == employer.id
    ).count()
    
    # Calculate view limit based on tier
    view_limits = {
        "free": 10,
        "starter": 50,
        "pro": 200,
        "enterprise": None  # Unlimited
    }
    
    return EmployerAnalyticsSummary(
        active_jobs=active_jobs,
        total_job_views=int(total_views),
        total_applications=int(total_applications),
        candidate_views_this_month=candidate_views_this_month,
        candidate_views_limit=view_limits.get(employer.subscription_tier),
        saved_candidates=saved_candidates,
        subscription_tier=employer.subscription_tier,
        subscription_status=employer.subscription_status
    )
```

---

### Step 3: Register Employer Router

**Location:** `services/api/app/main.py`

**Instructions:** Add the employer router to the FastAPI application.

**What to change:**

Find where other routers are imported and included, then add:

```python
# At the top with other router imports
from app.routers import auth, candidate, employer  # Add 'employer' here

# In the app setup section where routers are included
app.include_router(auth.router)
app.include_router(candidate.router)
app.include_router(employer.router)  # ADD THIS LINE
```

---

## Testing the API

### Step 4: Start the Development Server

**Location:** Terminal

**Commands:**
```bash
# Make sure you're in services/api directory
cd services/api

# Start the server
uvicorn app.main:app --reload --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

---

### Step 5: Test Endpoints with OpenAPI Docs

**Location:** Web Browser

**URL:** `http://localhost:8000/docs`

**What you'll see:**
- Interactive API documentation (Swagger UI)
- All employer endpoints listed under "employer" tag
- Request/response schemas
- "Try it out" buttons to test endpoints

**Endpoints to test:**

1. **POST /api/employer/profile** - Create employer profile
2. **GET /api/employer/profile** - Get your profile
3. **POST /api/employer/jobs** - Create a job
4. **GET /api/employer/jobs** - List your jobs
5. **POST /api/employer/candidates/search** - Search candidates
6. **GET /api/employer/analytics/summary** - Get dashboard stats

---

### Step 6: Manual API Testing

**Location:** Terminal (using curl) or Postman

**Test Script:**

```bash
# 1. Login as employer (get token)
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "employer@test.com",
    "password": "testpass123"
  }'

# Save the token from response

# 2. Create employer profile
curl -X POST http://localhost:8000/api/employer/profile \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Test Company",
    "company_size": "11-50",
    "industry": "Technology"
  }'

# 3. Create a job
curl -X POST http://localhost:8000/api/employer/jobs \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Senior Software Engineer",
    "description": "Looking for an experienced backend engineer to join our team",
    "remote_policy": "remote",
    "employment_type": "full-time",
    "salary_min": 120000,
    "salary_max": 160000
  }'

# 4. Get analytics
curl -X GET http://localhost:8000/api/employer/analytics/summary \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

---

## API Endpoint Summary

### Profile Management
- `POST /api/employer/profile` - Create employer profile
- `GET /api/employer/profile` - Get own profile
- `PATCH /api/employer/profile` - Update profile

### Job Management
- `POST /api/employer/jobs` - Create job (respects tier limits)
- `GET /api/employer/jobs` - List all jobs (optional status filter)
- `GET /api/employer/jobs/{id}` - Get specific job
- `PATCH /api/employer/jobs/{id}` - Update job
- `DELETE /api/employer/jobs/{id}` - Delete job

### Candidate Search
- `POST /api/employer/candidates/search` - Search candidates (filters, pagination)
- `GET /api/employer/candidates/{id}` - View profile (counts as view, respects limits)

### Saved Candidates
- `POST /api/employer/candidates/save` - Save candidate
- `GET /api/employer/candidates/saved` - List saved candidates
- `DELETE /api/employer/candidates/saved/{id}` - Unsave candidate

### Analytics
- `GET /api/employer/analytics/summary` - Dashboard summary stats

---

## Subscription Limits Enforcement

The router enforces these limits:

### Free Tier
- ✅ 1 active job
- ✅ 10 candidate views per month
- ❌ No analytics (not implemented yet)

### Starter Tier ($99/mo)
- ✅ 5 active jobs
- ✅ 50 candidate views per month
- ✅ Analytics included

### Pro Tier ($299/mo)
- ✅ Unlimited active jobs
- ✅ 200 candidate views per month
- ✅ Full analytics

### Enterprise Tier (Custom)
- ✅ Unlimited everything

---

## Security Features

### Role-Based Access
- All endpoints require `require_employer` dependency
- Users with role 'candidate' get 403 Forbidden
- Users with role 'both' can access employer endpoints

### Authorization
- Employers can only access their own jobs
- Employers can only view their own saved candidates
- Employers can only see candidates who are open to opportunities

### Privacy Protection
- Respects candidate visibility settings
- Anonymizes names when visibility = 'anonymous'
- Doesn't expose private candidates in search

---

## Performance Considerations

### Indexes Used (from PROMPT33)
- `idx_employer_jobs_status` - Fast job filtering
- `idx_employer_jobs_employer_id` - Fast employer->jobs lookup
- `idx_employer_candidate_views_employer` - Fast view counting
- `idx_employer_saved_candidates_employer` - Fast saved candidate retrieval

### N+1 Query Prevention
Use `joinedload` for related data:

```python
from sqlalchemy.orm import joinedload

# Load employer with jobs in one query
employer = db.query(EmployerProfile).options(
    joinedload(EmployerProfile.jobs)
).filter(EmployerProfile.id == employer_id).first()
```

---

## Future Enhancements (Not in this prompt)

1. **Job Matching Algorithm**: Calculate match scores for candidates
2. **Email Notifications**: Notify candidates when saved/viewed
3. **Advanced Search**: Full-text search, vector embeddings
4. **Messaging**: Direct messaging between employers and candidates
5. **Interview Scheduling**: Built-in calendar integration
6. **ATS Integration**: Export candidates to external ATS
7. **Webhooks**: Notify external systems of events

---

## Troubleshooting

### 403 Forbidden on all endpoints
**Cause:** User role is 'candidate', not 'employer'  
**Solution:** Check user.role in database, should be 'employer' or 'both'

### 404 Employer profile not found
**Cause:** Profile not created yet  
**Solution:** Call POST /api/employer/profile first

### Subscription limit errors
**Cause:** Actually hitting the limit  
**Solution:** Test with higher tier or upgrade in database

### Search returns empty results
**Cause:** No candidates have `open_to_opportunities=true`  
**Solution:** Set this flag on some test candidates

### Views not counting
**Cause:** Not calling the view endpoint, just search  
**Solution:** Search doesn't count as view, only GET /candidates/{id} does

---

## Next Steps

After completing this prompt:

1. **PROMPT37:** Frontend Auth - Update authentication for role selection
2. **PROMPT38:** Frontend Employer UI - Build employer dashboard, job posting, candidate search pages
3. **PROMPT39:** Subscription & Billing - Stripe integration (future)

---

## Success Criteria

✅ File `services/api/app/routers/employer.py` created  
✅ All 14+ endpoints implemented  
✅ Role-based auth dependencies work  
✅ Subscription limits enforced  
✅ Router registered in `main.py`  
✅ Server starts without errors  
✅ OpenAPI docs show all endpoints at /docs  
✅ Can create employer profile via API  
✅ Can create and list jobs  
✅ Can search candidates  
✅ Analytics endpoint returns data  

---

**Status:** Ready for implementation  
**Estimated Time:** 1-2 hours  
**Dependencies:** PROMPT33, 34, 35 completed  
**Next Prompt:** PROMPT37_Frontend_Auth.md
