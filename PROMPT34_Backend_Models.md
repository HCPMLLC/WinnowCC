# PROMPT 34: Two-Sided Marketplace - Backend Models

## Objective
Implement SQLAlchemy ORM models for employer functionality, including employer profiles, job postings, candidate views, and saved candidates. Update existing User and CandidateProfile models to support the two-sided marketplace.

---

## Context
After creating the database schema in PROMPT33, we now need to create the Python models that will allow our FastAPI backend to interact with the new employer tables. These models define the structure and relationships between users, employers, candidates, and jobs.

---

## Prerequisites
- ✅ PROMPT33 completed (database migration run successfully)
- ✅ Database tables exist: `employer_profiles`, `employer_jobs`, `employer_candidate_views`, `employer_saved_candidates`
- ✅ `users` table has `role` column
- ✅ `candidate_profiles` has visibility columns

---

## Implementation Steps

### Step 1: Create Employer Models File

**Location:** Create new file `services/api/app/models/employer.py`

**Instructions:** Create this new file with the following content:

**Code:**
```python
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class EmployerProfile(Base):
    """
    Employer profile containing company information and subscription details.
    
    Relationships:
    - user: The User account (1:1)
    - jobs: Job postings created by this employer (1:many)
    - candidate_views: Candidates this employer has viewed (1:many)
    - saved_candidates: Candidates this employer has saved (1:many)
    """
    __tablename__ = "employer_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Company information
    company_name = Column(String(255), nullable=False)
    company_size = Column(String(50))  # '1-10', '11-50', '51-200', '201-500', '501-1000', '1000+'
    industry = Column(String(100))
    company_website = Column(String(500))
    company_description = Column(Text)
    company_logo_url = Column(String(500))
    billing_email = Column(String(255))
    
    # Subscription & billing
    subscription_tier = Column(String(50), nullable=False, default="free")  # 'free', 'starter', 'pro', 'enterprise'
    subscription_status = Column(String(50), default="active")  # 'active', 'cancelled', 'past_due'
    stripe_customer_id = Column(String(255))
    stripe_subscription_id = Column(String(255))
    trial_ends_at = Column(DateTime(timezone=True))
    current_period_start = Column(DateTime(timezone=True))
    current_period_end = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="employer_profile")
    jobs = relationship("EmployerJob", back_populates="employer", cascade="all, delete-orphan")
    candidate_views = relationship("EmployerCandidateView", back_populates="employer", cascade="all, delete-orphan")
    saved_candidates = relationship("EmployerSavedCandidate", back_populates="employer", cascade="all, delete-orphan")


class EmployerJob(Base):
    """
    Job posting created by an employer.
    
    Status workflow:
    - draft: Being created, not visible to candidates
    - active: Published and visible to candidates
    - paused: Temporarily hidden from candidates
    - closed: No longer accepting applications
    
    Relationships:
    - employer: The employer who posted this job (many:1)
    """
    __tablename__ = "employer_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employer_profiles.id", ondelete="CASCADE"), nullable=False)
    
    # Job details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    requirements = Column(Text)
    nice_to_haves = Column(Text)
    
    # Location & type
    location = Column(String(255))
    remote_policy = Column(String(50))  # 'on-site', 'hybrid', 'remote'
    employment_type = Column(String(50))  # 'full-time', 'part-time', 'contract', 'internship'
    
    # Compensation
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    salary_currency = Column(String(10), default="USD")
    equity_offered = Column(Boolean, default=False)
    
    # Status & application
    status = Column(String(50), nullable=False, default="draft")  # 'draft', 'active', 'paused', 'closed'
    application_url = Column(String(500))
    application_email = Column(String(255))
    
    # Dates
    posted_at = Column(DateTime(timezone=True))
    closes_at = Column(DateTime(timezone=True))
    
    # Analytics
    view_count = Column(Integer, default=0)
    application_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    employer = relationship("EmployerProfile", back_populates="jobs")


class EmployerCandidateView(Base):
    """
    Tracks when an employer views a candidate profile.
    
    Used for:
    - Enforcing subscription limits (e.g., free tier = 10 views/month)
    - Analytics (who's viewing candidate profiles)
    - Candidate insights (which employers are interested)
    
    Relationships:
    - employer: The employer who viewed (many:1)
    - candidate: The candidate who was viewed (many:1)
    """
    __tablename__ = "employer_candidate_views"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employer_profiles.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    viewed_at = Column(DateTime(timezone=True), server_default=func.now())
    source = Column(String(100))  # 'search', 'job_application', 'recommendation'
    
    # Relationships
    employer = relationship("EmployerProfile", back_populates="candidate_views")
    candidate = relationship("CandidateProfile")


class EmployerSavedCandidate(Base):
    """
    Employer's saved/favorited candidates.
    
    Allows employers to:
    - Mark interesting candidates for later review
    - Add private notes about candidates
    - Build a talent pipeline
    
    Relationships:
    - employer: The employer who saved (many:1)
    - candidate: The candidate who was saved (many:1)
    """
    __tablename__ = "employer_saved_candidates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employer_profiles.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    notes = Column(Text)
    saved_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    employer = relationship("EmployerProfile", back_populates="saved_candidates")
    candidate = relationship("CandidateProfile")
```

---

### Step 2: Update User Model

**Location:** `services/api/app/models/user.py`

**Instructions:** Add the `role` field and employer relationship to the existing User model.

**What to change:**

1. **Add import** (if not already present):
```python
from sqlalchemy.orm import relationship
```

2. **Inside the `User` class, add these fields:**

```python
class User(Base):
    __tablename__ = "users"
    
    # ... existing fields (id, email, password_hash, etc.) ...
    
    # ADD THIS FIELD:
    role = Column(String(20), nullable=False, default="candidate")  # 'candidate', 'employer', 'both'
    
    # ... other existing fields ...
    
    # UPDATE RELATIONSHIPS SECTION:
    # The candidate_profile relationship should already exist, just add employer_profile:
    
    candidate_profile = relationship("CandidateProfile", back_populates="user", uselist=False)
    
    # ADD THIS LINE:
    employer_profile = relationship("EmployerProfile", back_populates="user", uselist=False)
```

**Complete User class should look like:**
```python
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # ADD THIS:
    role = Column(String(20), nullable=False, default="candidate")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    candidate_profile = relationship("CandidateProfile", back_populates="user", uselist=False)
    employer_profile = relationship("EmployerProfile", back_populates="user", uselist=False)  # ADD THIS
```

---

### Step 3: Update Candidate Model

**Location:** `services/api/app/models/candidate.py`

**Instructions:** Add visibility fields to the CandidateProfile model.

**What to change:**

Inside the `CandidateProfile` class, add these fields:

```python
class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    
    # ... existing fields (id, user_id, name, profile_data, etc.) ...
    
    # ADD THESE FIELDS:
    open_to_opportunities = Column(Boolean, default=True)
    profile_visibility = Column(String(50), default="public")  # 'public', 'anonymous', 'private'
    
    # ... rest of existing fields and relationships ...
```

**Field Meanings:**
- `open_to_opportunities`: If False, candidate won't appear in employer searches at all
- `profile_visibility`:
  - **'public'**: Name and full profile visible to employers
  - **'anonymous'**: Profile visible but name hidden (shows as "Candidate ABC123")
  - **'private'**: Not visible in searches (same as open_to_opportunities=False)

---

### Step 4: Update Models __init__.py

**Location:** `services/api/app/models/__init__.py`

**Instructions:** Export the new models so they can be imported elsewhere.

**What to add:**

```python
from app.models.user import User
from app.models.candidate import CandidateProfile
from app.models.employer import (
    EmployerProfile,
    EmployerJob,
    EmployerCandidateView,
    EmployerSavedCandidate
)

# Export all models
__all__ = [
    "User",
    "CandidateProfile",
    "EmployerProfile",
    "EmployerJob",
    "EmployerCandidateView",
    "EmployerSavedCandidate",
]
```

---

## Model Relationships Diagram

```
User
├─ role: 'candidate' | 'employer' | 'both'
├─ candidate_profile (1:1) ──> CandidateProfile
│                                ├─ open_to_opportunities: boolean
│                                ├─ profile_visibility: string
│                                ├─ (viewed by) EmployerCandidateView (1:many)
│                                └─ (saved by) EmployerSavedCandidate (1:many)
│
└─ employer_profile (1:1) ──> EmployerProfile
                                ├─ subscription_tier: string
                                ├─ subscription_status: string
                                ├─ jobs (1:many) ──> EmployerJob
                                ├─ candidate_views (1:many) ──> EmployerCandidateView
                                └─ saved_candidates (1:many) ──> EmployerSavedCandidate
```

---

## Verification & Testing

### Step 5: Test Model Import

**Location:** Terminal

**Commands:**
```bash
cd services/api

# Start Python shell
python3

# Test imports
>>> from app.models.employer import EmployerProfile, EmployerJob
>>> from app.models.user import User
>>> from app.models.candidate import CandidateProfile
>>> print("All models imported successfully!")
>>> exit()
```

**Expected Output:** No errors, models import cleanly.

---

### Step 6: Test Model Creation (Optional)

**Location:** Terminal/Python Shell

**Test Script:**
```python
from app.database import SessionLocal
from app.models.user import User
from app.models.employer import EmployerProfile
from app.auth import get_password_hash

# Create session
db = SessionLocal()

# Create employer user
user = User(
    email="testemployer@example.com",
    password_hash=get_password_hash("testpassword"),
    role="employer"
)
db.add(user)
db.commit()
db.refresh(user)

# Create employer profile
employer = EmployerProfile(
    user_id=user.id,
    company_name="Test Company",
    company_size="11-50",
    industry="Technology",
    subscription_tier="free"
)
db.add(employer)
db.commit()

print(f"Created employer: {employer.company_name}")
print(f"User role: {user.role}")
print(f"Subscription tier: {employer.subscription_tier}")

# Cleanup
db.delete(employer)
db.delete(user)
db.commit()
db.close()

print("Test successful!")
```

---

## Key Model Features

### EmployerProfile
- **Subscription tiers**: free, starter, pro, enterprise
- **Billing integration**: Stripe customer and subscription IDs
- **Trial support**: `trial_ends_at` field
- **Cascading deletes**: Deleting profile deletes all jobs, views, saved candidates

### EmployerJob
- **Status workflow**: draft → active → paused/closed
- **Analytics**: Tracks views and applications
- **Flexible application**: Can use URL or email
- **Auto-timestamp**: `posted_at` set when status changes to 'active'

### EmployerCandidateView
- **Usage tracking**: Count views per month for subscription limits
- **Source tracking**: Know how employer found the candidate
- **No uniqueness constraint**: Can view same candidate multiple times (each view tracked)

### EmployerSavedCandidate
- **Unique constraint**: Can only save each candidate once
- **Private notes**: Employers can add notes only they see
- **Cascade delete**: Deleting employer removes all saved candidates

---

## Common Patterns & Best Practices

### 1. Using Relationships
```python
# Get all jobs for an employer
employer = db.query(EmployerProfile).first()
jobs = employer.jobs  # SQLAlchemy handles the join

# Get employer from a job
job = db.query(EmployerJob).first()
company_name = job.employer.company_name  # Automatic join
```

### 2. Counting with Limits
```python
# Check subscription limits
from datetime import datetime, timedelta

month_start = datetime.utcnow().replace(day=1, hour=0, minute=0)
views_this_month = db.query(EmployerCandidateView).filter(
    EmployerCandidateView.employer_id == employer.id,
    EmployerCandidateView.viewed_at >= month_start
).count()

if employer.subscription_tier == "free" and views_this_month >= 10:
    raise Exception("Free tier limit reached")
```

### 3. Eager Loading
```python
# Avoid N+1 queries
from sqlalchemy.orm import joinedload

employers = db.query(EmployerProfile).options(
    joinedload(EmployerProfile.jobs)
).all()
```

---

## Migration Compatibility

These models match the database schema created in PROMPT33. The table names, column names, and data types are identical:

| Model | Table | Matches Migration |
|-------|-------|-------------------|
| EmployerProfile | employer_profiles | ✅ |
| EmployerJob | employer_jobs | ✅ |
| EmployerCandidateView | employer_candidate_views | ✅ |
| EmployerSavedCandidate | employer_saved_candidates | ✅ |
| User.role | users.role | ✅ |
| CandidateProfile visibility | candidate_profiles columns | ✅ |

---

## Troubleshooting

### Import Error: "cannot import name 'EmployerProfile'"
**Cause:** File not created or in wrong location  
**Solution:** Verify `services/api/app/models/employer.py` exists

### Relationship Error: "No such column"
**Cause:** Migration not run or models don't match schema  
**Solution:** Run `alembic upgrade head` to ensure database is up to date

### Circular Import Error
**Cause:** Models importing each other incorrectly  
**Solution:** Use string references in relationships: `relationship("User")` instead of `relationship(User)`

### TypeError: "got an unexpected keyword argument"
**Cause:** Field name mismatch between model and database  
**Solution:** Check that column names in model match migration exactly

---

## Next Steps

After completing this prompt:

1. **PROMPT35:** Backend Schemas - Create Pydantic validation schemas
2. **PROMPT36:** Backend Routes - Implement employer API endpoints  
3. **PROMPT37:** Frontend Auth - Update authentication for roles
4. **PROMPT38:** Frontend Employer UI - Build employer dashboard

---

## Success Criteria

✅ File `services/api/app/models/employer.py` created with all 4 models  
✅ `User` model has `role` field and `employer_profile` relationship  
✅ `CandidateProfile` has visibility fields  
✅ Models can be imported without errors  
✅ Relationships are properly defined (back_populates)  
✅ Cascade deletes configured correctly  
✅ All models exported in `__init__.py`  

---

**Status:** Ready for implementation  
**Estimated Time:** 20-30 minutes  
**Dependencies:** PROMPT33 (database migration completed)  
**Next Prompt:** PROMPT35_Backend_Schemas.md
