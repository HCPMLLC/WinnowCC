# PROMPT 35: Two-Sided Marketplace - Backend Schemas (Pydantic)

## Objective
Create Pydantic schemas for request/response validation of employer-related API endpoints. These schemas define the structure of data coming into and going out of the API, with validation rules and documentation.

---

## Context
After creating the SQLAlchemy models (PROMPT34), we need Pydantic schemas to:
- **Validate incoming data** (e.g., when creating a job posting)
- **Serialize outgoing data** (e.g., when returning employer profile)
- **Auto-generate API documentation** (OpenAPI/Swagger)
- **Ensure type safety** between frontend and backend

---

## Prerequisites
- ✅ PROMPT33 completed (database schema)
- ✅ PROMPT34 completed (SQLAlchemy models)
- ✅ Models can be imported: `from app.models.employer import EmployerProfile, EmployerJob`

---

## Implementation Steps

### Step 1: Create Employer Schemas File

**Location:** Create new file `services/api/app/schemas/employer.py`

**Instructions:** Create this new file with the following content:

**Code:**
```python
from pydantic import BaseModel, EmailStr, HttpUrl, Field, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ============================================================================
# EMPLOYER PROFILE SCHEMAS
# ============================================================================

class EmployerProfileBase(BaseModel):
    """Base schema for employer profile with common fields."""
    company_name: str = Field(..., min_length=1, max_length=255, description="Company name")
    company_size: Optional[str] = Field(None, description="Company size category: '1-10', '11-50', '51-200', '201-500', '501-1000', '1000+'")
    industry: Optional[str] = Field(None, max_length=100, description="Industry/sector")
    company_website: Optional[HttpUrl] = Field(None, description="Company website URL")
    company_description: Optional[str] = Field(None, description="Company description/about")
    company_logo_url: Optional[HttpUrl] = Field(None, description="Company logo image URL")
    billing_email: Optional[EmailStr] = Field(None, description="Billing contact email")
    
    @field_validator('company_size')
    @classmethod
    def validate_company_size(cls, v):
        """Validate company size is one of allowed values."""
        if v is not None:
            allowed = ['1-10', '11-50', '51-200', '201-500', '501-1000', '1000+']
            if v not in allowed:
                raise ValueError(f"company_size must be one of: {', '.join(allowed)}")
        return v


class EmployerProfileCreate(EmployerProfileBase):
    """Schema for creating a new employer profile."""
    pass


class EmployerProfileUpdate(BaseModel):
    """Schema for updating employer profile. All fields optional."""
    company_name: Optional[str] = Field(None, min_length=1, max_length=255)
    company_size: Optional[str] = None
    industry: Optional[str] = Field(None, max_length=100)
    company_website: Optional[HttpUrl] = None
    company_description: Optional[str] = None
    company_logo_url: Optional[HttpUrl] = None
    billing_email: Optional[EmailStr] = None
    
    @field_validator('company_size')
    @classmethod
    def validate_company_size(cls, v):
        """Validate company size is one of allowed values."""
        if v is not None:
            allowed = ['1-10', '11-50', '51-200', '201-500', '501-1000', '1000+']
            if v not in allowed:
                raise ValueError(f"company_size must be one of: {', '.join(allowed)}")
        return v


class EmployerProfileResponse(EmployerProfileBase):
    """Schema for employer profile response (what the API returns)."""
    id: UUID
    user_id: UUID
    subscription_tier: str
    subscription_status: str
    trial_ends_at: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True  # Allow ORM model conversion


# ============================================================================
# JOB POSTING SCHEMAS
# ============================================================================

class EmployerJobBase(BaseModel):
    """Base schema for job posting with common fields."""
    title: str = Field(..., min_length=1, max_length=255, description="Job title")
    description: str = Field(..., min_length=10, description="Job description (at least 10 chars)")
    requirements: Optional[str] = Field(None, description="Required qualifications")
    nice_to_haves: Optional[str] = Field(None, description="Preferred/nice-to-have qualifications")
    location: Optional[str] = Field(None, max_length=255, description="Job location")
    remote_policy: Optional[str] = Field(None, description="Remote work policy: 'on-site', 'hybrid', or 'remote'")
    employment_type: Optional[str] = Field(None, description="Employment type: 'full-time', 'part-time', 'contract', or 'internship'")
    salary_min: Optional[int] = Field(None, ge=0, description="Minimum salary (must be >= 0)")
    salary_max: Optional[int] = Field(None, ge=0, description="Maximum salary (must be >= 0)")
    salary_currency: str = Field(default="USD", max_length=10, description="Salary currency code")
    equity_offered: bool = Field(default=False, description="Whether equity is offered")
    application_url: Optional[HttpUrl] = Field(None, description="External application URL")
    application_email: Optional[EmailStr] = Field(None, description="Application email address")
    
    @field_validator('remote_policy')
    @classmethod
    def validate_remote_policy(cls, v):
        """Validate remote policy is one of allowed values."""
        if v is not None:
            allowed = ['on-site', 'hybrid', 'remote']
            if v not in allowed:
                raise ValueError(f"remote_policy must be one of: {', '.join(allowed)}")
        return v
    
    @field_validator('employment_type')
    @classmethod
    def validate_employment_type(cls, v):
        """Validate employment type is one of allowed values."""
        if v is not None:
            allowed = ['full-time', 'part-time', 'contract', 'internship']
            if v not in allowed:
                raise ValueError(f"employment_type must be one of: {', '.join(allowed)}")
        return v
    
    @field_validator('salary_max')
    @classmethod
    def validate_salary_range(cls, v, info):
        """Validate salary_max >= salary_min if both provided."""
        if v is not None and info.data.get('salary_min') is not None:
            if v < info.data['salary_min']:
                raise ValueError('salary_max must be greater than or equal to salary_min')
        return v


class EmployerJobCreate(EmployerJobBase):
    """Schema for creating a new job posting."""
    pass


class EmployerJobUpdate(BaseModel):
    """Schema for updating a job posting. All fields optional."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=10)
    requirements: Optional[str] = None
    nice_to_haves: Optional[str] = None
    location: Optional[str] = Field(None, max_length=255)
    remote_policy: Optional[str] = None
    employment_type: Optional[str] = None
    salary_min: Optional[int] = Field(None, ge=0)
    salary_max: Optional[int] = Field(None, ge=0)
    salary_currency: Optional[str] = Field(None, max_length=10)
    equity_offered: Optional[bool] = None
    application_url: Optional[HttpUrl] = None
    application_email: Optional[EmailStr] = None
    status: Optional[str] = Field(None, description="Job status: 'draft', 'active', 'paused', or 'closed'")
    closes_at: Optional[datetime] = Field(None, description="When job closes for applications")
    
    @field_validator('remote_policy')
    @classmethod
    def validate_remote_policy(cls, v):
        if v is not None:
            allowed = ['on-site', 'hybrid', 'remote']
            if v not in allowed:
                raise ValueError(f"remote_policy must be one of: {', '.join(allowed)}")
        return v
    
    @field_validator('employment_type')
    @classmethod
    def validate_employment_type(cls, v):
        if v is not None:
            allowed = ['full-time', 'part-time', 'contract', 'internship']
            if v not in allowed:
                raise ValueError(f"employment_type must be one of: {', '.join(allowed)}")
        return v
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        if v is not None:
            allowed = ['draft', 'active', 'paused', 'closed']
            if v not in allowed:
                raise ValueError(f"status must be one of: {', '.join(allowed)}")
        return v


class EmployerJobResponse(EmployerJobBase):
    """Schema for job posting response (what the API returns)."""
    id: UUID
    employer_id: UUID
    status: str
    posted_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None
    view_count: int
    application_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============================================================================
# CANDIDATE SEARCH SCHEMAS
# ============================================================================

class CandidateSearchFilters(BaseModel):
    """Filters for searching candidates."""
    skills: Optional[List[str]] = Field(None, description="Required skills (AND logic)")
    experience_years_min: Optional[int] = Field(None, ge=0, description="Minimum years of experience")
    experience_years_max: Optional[int] = Field(None, ge=0, description="Maximum years of experience")
    locations: Optional[List[str]] = Field(None, description="Acceptable locations")
    remote_only: Optional[bool] = Field(None, description="Only show candidates open to remote")
    job_titles: Optional[List[str]] = Field(None, description="Current or past job titles to match")
    
    @field_validator('experience_years_max')
    @classmethod
    def validate_experience_range(cls, v, info):
        """Validate max >= min if both provided."""
        if v is not None and info.data.get('experience_years_min') is not None:
            if v < info.data['experience_years_min']:
                raise ValueError('experience_years_max must be >= experience_years_min')
        return v


class CandidateSearchResult(BaseModel):
    """Single candidate in search results."""
    id: UUID
    name: str  # May be anonymized
    headline: Optional[str] = None
    location: Optional[str] = None
    years_experience: Optional[int] = None
    top_skills: List[str] = []
    match_score: Optional[float] = Field(None, ge=0, le=100, description="Match percentage (0-100)")
    profile_visibility: str  # 'public', 'anonymous', 'private'
    
    class Config:
        from_attributes = True


class CandidateSearchResponse(BaseModel):
    """Response for candidate search with pagination."""
    results: List[CandidateSearchResult]
    total: int
    page: int
    page_size: int
    has_more: bool


# ============================================================================
# SAVED CANDIDATES SCHEMAS
# ============================================================================

class SaveCandidateRequest(BaseModel):
    """Request to save a candidate."""
    candidate_id: UUID = Field(..., description="ID of candidate to save")
    notes: Optional[str] = Field(None, max_length=5000, description="Private notes about candidate")


class UpdateSavedCandidateNotes(BaseModel):
    """Request to update notes on saved candidate."""
    notes: Optional[str] = Field(None, max_length=5000)


class SavedCandidateResponse(BaseModel):
    """Response for saved candidate."""
    id: UUID
    candidate_id: UUID
    notes: Optional[str] = None
    saved_at: datetime
    candidate: CandidateSearchResult
    
    class Config:
        from_attributes = True


# ============================================================================
# ANALYTICS SCHEMAS
# ============================================================================

class EmployerAnalyticsSummary(BaseModel):
    """Summary analytics for employer dashboard."""
    active_jobs: int = Field(..., description="Number of active job postings")
    total_job_views: int = Field(..., description="Total views across all jobs")
    total_applications: int = Field(..., description="Total applications received")
    candidate_views_this_month: int = Field(..., description="Candidate profiles viewed this month")
    candidate_views_limit: Optional[int] = Field(None, description="Monthly limit based on subscription")
    saved_candidates: int = Field(..., description="Number of saved candidates")
    subscription_tier: str = Field(..., description="Current subscription tier")
    subscription_status: str = Field(..., description="Subscription status")


class JobAnalytics(BaseModel):
    """Analytics for a specific job."""
    job_id: UUID
    job_title: str
    status: str
    views: int
    applications: int
    views_last_7_days: int
    applications_last_7_days: int
    posted_at: Optional[datetime] = None
    days_active: Optional[int] = None


# ============================================================================
# SUBSCRIPTION SCHEMAS
# ============================================================================

class SubscriptionTierInfo(BaseModel):
    """Information about a subscription tier."""
    tier: str  # 'free', 'starter', 'pro', 'enterprise'
    name: str  # Display name
    price_monthly: Optional[int] = Field(None, description="Price in cents")
    features: dict = Field(default_factory=dict, description="Feature limits and capabilities")


class UpgradeSubscriptionRequest(BaseModel):
    """Request to upgrade subscription."""
    tier: str = Field(..., description="Target tier: 'starter', 'pro', or 'enterprise'")
    payment_method_id: Optional[str] = Field(None, description="Stripe payment method ID")
    
    @field_validator('tier')
    @classmethod
    def validate_tier(cls, v):
        allowed = ['starter', 'pro', 'enterprise']
        if v not in allowed:
            raise ValueError(f"tier must be one of: {', '.join(allowed)}")
        return v


# ============================================================================
# HELPER SCHEMAS
# ============================================================================

class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    detail: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response schema."""
    error: str
    detail: Optional[str] = None
    field: Optional[str] = None  # Field that caused validation error
```

---

### Step 2: Update Schemas __init__.py

**Location:** `services/api/app/schemas/__init__.py`

**Instructions:** Export all new schemas for easy importing.

**What to add:**

```python
# Existing imports (if any)
from app.schemas.auth import *
from app.schemas.candidate import *

# ADD THESE:
from app.schemas.employer import (
    # Profile schemas
    EmployerProfileBase,
    EmployerProfileCreate,
    EmployerProfileUpdate,
    EmployerProfileResponse,
    
    # Job schemas
    EmployerJobBase,
    EmployerJobCreate,
    EmployerJobUpdate,
    EmployerJobResponse,
    
    # Search schemas
    CandidateSearchFilters,
    CandidateSearchResult,
    CandidateSearchResponse,
    
    # Saved candidates schemas
    SaveCandidateRequest,
    UpdateSavedCandidateNotes,
    SavedCandidateResponse,
    
    # Analytics schemas
    EmployerAnalyticsSummary,
    JobAnalytics,
    
    # Subscription schemas
    SubscriptionTierInfo,
    UpgradeSubscriptionRequest,
    
    # Helper schemas
    MessageResponse,
    ErrorResponse,
)

__all__ = [
    # ... existing exports ...
    
    # Employer schemas
    "EmployerProfileBase",
    "EmployerProfileCreate",
    "EmployerProfileUpdate",
    "EmployerProfileResponse",
    "EmployerJobBase",
    "EmployerJobCreate",
    "EmployerJobUpdate",
    "EmployerJobResponse",
    "CandidateSearchFilters",
    "CandidateSearchResult",
    "CandidateSearchResponse",
    "SaveCandidateRequest",
    "UpdateSavedCandidateNotes",
    "SavedCandidateResponse",
    "EmployerAnalyticsSummary",
    "JobAnalytics",
    "SubscriptionTierInfo",
    "UpgradeSubscriptionRequest",
    "MessageResponse",
    "ErrorResponse",
]
```

---

## Schema Patterns Explained

### 1. Base, Create, Update, Response Pattern

This is a common Pydantic pattern:

```python
# Base: Shared fields
class JobBase(BaseModel):
    title: str
    description: str

# Create: What client sends to create
class JobCreate(JobBase):
    pass  # Inherits all from Base

# Update: All fields optional for PATCH
class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

# Response: What API returns (includes DB fields)
class JobResponse(JobBase):
    id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True  # Convert SQLAlchemy model
```

### 2. Field Validation

```python
# Simple validation
salary: int = Field(..., ge=0, le=1000000)

# Custom validator
@field_validator('email')
@classmethod
def validate_email(cls, v):
    if not v.endswith('@company.com'):
        raise ValueError('Must be company email')
    return v

# Cross-field validation
@field_validator('salary_max')
@classmethod
def validate_range(cls, v, info):
    if v < info.data['salary_min']:
        raise ValueError('Max must be >= min')
    return v
```

### 3. Nested Schemas

```python
class SavedCandidateResponse(BaseModel):
    id: UUID
    candidate: CandidateSearchResult  # Nested schema
```

---

## Validation Examples

### Valid Job Creation
```json
{
  "title": "Senior Software Engineer",
  "description": "We're looking for an experienced backend engineer...",
  "requirements": "5+ years Python, FastAPI experience",
  "location": "San Francisco, CA",
  "remote_policy": "hybrid",
  "employment_type": "full-time",
  "salary_min": 150000,
  "salary_max": 200000,
  "salary_currency": "USD",
  "equity_offered": true
}
```

### Invalid Job Creation (Errors)
```json
{
  "title": "",  // ❌ ERROR: min_length=1
  "description": "Short",  // ❌ ERROR: min_length=10
  "remote_policy": "sometimes",  // ❌ ERROR: not in allowed values
  "salary_min": 200000,
  "salary_max": 150000  // ❌ ERROR: max < min
}
```

---

## Testing Schemas

### Step 3: Test Schema Validation

**Location:** Terminal/Python Shell

**Test Script:**
```python
from app.schemas.employer import EmployerJobCreate, EmployerProfileCreate
from pydantic import ValidationError

# Test valid job creation
try:
    job = EmployerJobCreate(
        title="Software Engineer",
        description="Great opportunity to work with cutting-edge tech",
        remote_policy="remote",
        employment_type="full-time",
        salary_min=100000,
        salary_max=150000
    )
    print("✅ Valid job schema:", job.model_dump())
except ValidationError as e:
    print("❌ Validation error:", e)

# Test invalid job (salary range)
try:
    bad_job = EmployerJobCreate(
        title="Engineer",
        description="Test job posting",
        salary_min=150000,
        salary_max=100000  # Max < Min!
    )
except ValidationError as e:
    print("✅ Correctly caught error:", e.errors()[0]['msg'])

# Test valid profile
try:
    profile = EmployerProfileCreate(
        company_name="Acme Corp",
        company_size="51-200",
        industry="Technology"
    )
    print("✅ Valid profile schema:", profile.model_dump())
except ValidationError as e:
    print("❌ Validation error:", e)

print("\nAll schema tests passed!")
```

---

## Schema Usage in Routes (Preview)

Here's how these schemas will be used in PROMPT36:

```python
from fastapi import APIRouter, Depends
from app.schemas.employer import EmployerJobCreate, EmployerJobResponse

router = APIRouter()

@router.post("/jobs", response_model=EmployerJobResponse)
async def create_job(
    job_data: EmployerJobCreate,  # Auto-validates input
    db: Session = Depends(get_db)
):
    # job_data is guaranteed valid here
    job = EmployerJob(**job_data.model_dump())
    db.add(job)
    db.commit()
    
    # Auto-serializes to EmployerJobResponse
    return job
```

---

## Auto-Generated API Documentation

These schemas automatically generate OpenAPI documentation at `/docs`:

**Example generated docs:**

```
POST /api/employer/jobs
Request Body (EmployerJobCreate):
  - title: string (required, min: 1, max: 255)
  - description: string (required, min: 10)
  - remote_policy: string (enum: on-site, hybrid, remote)
  - salary_min: integer (>= 0)
  - salary_max: integer (>= 0, must be >= salary_min)
  
Response (EmployerJobResponse):
  - id: UUID
  - employer_id: UUID
  - status: string
  - created_at: datetime
  ... (all fields)
```

---

## Subscription Tier Feature Definitions

The schemas reference subscription tiers. Here are the planned features:

```python
SUBSCRIPTION_TIERS = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "features": {
            "active_jobs": 1,
            "candidate_views_per_month": 10,
            "job_analytics": False,
            "priority_support": False
        }
    },
    "starter": {
        "name": "Starter",
        "price_monthly": 9900,  # $99.00
        "features": {
            "active_jobs": 5,
            "candidate_views_per_month": 50,
            "job_analytics": True,
            "priority_support": False
        }
    },
    "pro": {
        "name": "Professional",
        "price_monthly": 29900,  # $299.00
        "features": {
            "active_jobs": -1,  # Unlimited
            "candidate_views_per_month": 200,
            "job_analytics": True,
            "priority_support": True,
            "ats_integration": True
        }
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": None,  # Custom pricing
        "features": {
            "active_jobs": -1,
            "candidate_views_per_month": -1,  # Unlimited
            "job_analytics": True,
            "priority_support": True,
            "ats_integration": True,
            "dedicated_account_manager": True,
            "sla": True
        }
    }
}
```

This will be implemented in a later prompt for subscription management.

---

## Troubleshooting

### ValidationError on Import
**Cause:** Pydantic validation running on schema definition  
**Solution:** Check for typos in Field definitions, ensure validators are properly decorated

### "from_attributes not recognized"
**Cause:** Old Pydantic version (v1)  
**Solution:** Upgrade to Pydantic v2: `pip install "pydantic>=2.0" --break-system-packages`

### Circular Import Between Schemas
**Cause:** Two schemas importing each other  
**Solution:** Use forward references: `candidate: "CandidateSearchResult"`

### Field Validation Not Running
**Cause:** Using validator instead of field_validator (Pydantic v2)  
**Solution:** Use `@field_validator('field_name')` decorator

---

## Next Steps

After completing this prompt:

1. **PROMPT36:** Backend Routes - Implement employer API endpoints (uses these schemas)
2. **PROMPT37:** Frontend Auth - Update authentication for role-based access
3. **PROMPT38:** Frontend Employer UI - Build employer dashboard

---

## Success Criteria

✅ File `services/api/app/schemas/employer.py` created  
✅ All schema classes defined with proper validation  
✅ Validators work correctly (test with invalid data)  
✅ Schemas can be imported: `from app.schemas.employer import *`  
✅ All schemas exported in `__init__.py`  
✅ Field descriptions added for auto-docs  
✅ Nested schemas work (SavedCandidateResponse)  

---

**Status:** Ready for implementation  
**Estimated Time:** 30-45 minutes  
**Dependencies:** PROMPT34 (models created)  
**Next Prompt:** PROMPT36_Backend_Routes.md
