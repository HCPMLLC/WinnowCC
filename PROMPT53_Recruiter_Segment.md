# PROMPT53_Recruiter_Segment.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPTs 33–44 before making changes.

## Purpose

Build the **complete Recruiter segment** for Winnow — the third side of the three-sided marketplace. This prompt implements everything a professional recruiter or staffing agency needs: registration, onboarding, profile management, client management, candidate pipeline CRM, multi-channel outreach, team management, subscription billing, dashboard analytics, and the recruiter-specific landing page content. Recruiters are distinct from employers — they manage candidates across multiple clients and job orders simultaneously.

**Recruiter tiers:** Solo ($79/mo) · Team ($149/mo) · Agency ($299/mo)

**Competitive targets:** Bullhorn, Recruit CRM, CATSOne, Zoho Recruit

---

## Triggers — When to Use This Prompt

- Building the recruiter registration and onboarding flow.
- Creating the recruiter dashboard, CRM pipeline, or outreach features.
- Adding recruiter-specific billing tiers and feature gates.
- Implementing recruiter team management or client management.
- Wiring the recruiter audience toggle on the landing page.
- Product asks for "recruiter features," "staffing agency support," or "CRM pipeline."

---

## What Already Exists (DO NOT recreate — read the codebase first)

1. **User model with role field:** `services/api/app/models/` — `User.role` supports 'candidate', 'employer', 'both'. Needs extension to include 'recruiter'.
2. **Auth system:** `services/api/app/services/auth.py` — JWT cookie auth with `get_current_user`.
3. **Recruiter router (stub):** `services/api/app/routers/recruiter.py` — basic registration endpoint (may be minimal).
4. **Recruiter models (stubs):** `services/api/app/models/` — `recruiter_profiles` and `recruiter_team_members` tables may already exist from CLAUDE.md references. READ THEM FIRST.
5. **Employer patterns:** PROMPTs 33–43 established patterns for profile, jobs, billing, team management. Mirror these patterns for recruiters.
6. **Billing system:** `services/api/app/services/billing.py` — tiered enforcement with `CANDIDATE_PLAN_LIMITS`. Needs recruiter tier addition.
7. **Stripe integration:** `services/api/app/routers/billing.py` — checkout, webhooks, portal. Needs recruiter price IDs.
8. **Landing page audience toggle:** `apps/web/app/page.tsx` — has seeker/employer/recruiter sections. The recruiter section may have placeholder content.
9. **Distribution engine:** PROMPT44 built `board_connections`, `job_distributions`, `distribution_events` tables.
10. **Employer analytics:** `services/api/app/services/employer_analytics.py` — analytics patterns to reuse.
11. **Trust/compliance system:** Trust scoring, fraud detection, admin tools already exist.

---

## Implementation Order

**This prompt is divided into 10 Parts. Execute them in order:**

1. Part 1 — Database: Recruiter tables (Alembic migration)
2. Part 2 — Backend Models: SQLAlchemy models
3. Part 3 — Backend Schemas: Pydantic validation
4. Part 4 — Backend Services: Business logic
5. Part 5 — Backend Routes: API endpoints
6. Part 6 — Frontend: Auth & role routing updates
7. Part 7 — Frontend: Recruiter pages (onboarding, dashboard, CRM, clients, settings)
8. Part 8 — Recruiter Billing: Stripe tiers + feature gates
9. Part 9 — Landing Page: Recruiter audience content
10. Part 10 — Verification & Testing

---

# PART 1 — Database: Recruiter Tables

## Step 1.1 — Create Alembic Migration

Open a terminal in your project, navigate to the API folder, and run:

```powershell
cd services\api
alembic revision --autogenerate -m "add_recruiter_segment_tables"
```

This creates a new file inside:
```
services/api/alembic/versions/
```

Open that newly created file in Cursor and replace its contents with the migration below.

## Step 1.2 — Migration Content

The migration creates these tables. **Before writing, check if `recruiter_profiles` or `recruiter_team_members` already exist in the database.** If they do, only add the missing columns/tables.

### Table: `recruiter_profiles`

```python
op.create_table(
    'recruiter_profiles',
    sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
    sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),

    # Agency / firm info
    sa.Column('company_name', sa.String(255), nullable=True),
    sa.Column('company_website', sa.String(500), nullable=True),
    sa.Column('agency_type', sa.String(50), nullable=True),  # 'independent', 'boutique', 'staffing_agency', 'executive_search', 'rpо'
    sa.Column('specializations', sa.dialects.postgresql.JSONB, nullable=True),  # ['technology', 'healthcare', 'finance', ...]
    sa.Column('industries_served', sa.dialects.postgresql.JSONB, nullable=True),
    sa.Column('locations_served', sa.dialects.postgresql.JSONB, nullable=True),

    # Professional info
    sa.Column('years_recruiting', sa.Integer, nullable=True),
    sa.Column('certifications', sa.dialects.postgresql.JSONB, nullable=True),  # ['CIR', 'CDR', 'AIRS', ...]
    sa.Column('bio', sa.Text, nullable=True),
    sa.Column('linkedin_url', sa.String(500), nullable=True),
    sa.Column('phone', sa.String(50), nullable=True),

    # Subscription
    sa.Column('subscription_tier', sa.String(20), server_default='free'),  # 'free', 'solo', 'team', 'agency'
    sa.Column('stripe_customer_id', sa.String(255), nullable=True),
    sa.Column('stripe_subscription_id', sa.String(255), nullable=True),
    sa.Column('billing_email', sa.String(255), nullable=True),

    # Onboarding
    sa.Column('onboarding_completed', sa.Boolean, server_default='false'),
    sa.Column('onboarding_step', sa.Integer, server_default='0'),

    # Timestamps
    sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
)
```

### Table: `recruiter_team_members`

```python
op.create_table(
    'recruiter_team_members',
    sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
    sa.Column('recruiter_profile_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('recruiter_profiles.id', ondelete='CASCADE'), nullable=False),
    sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    sa.Column('role', sa.String(30), nullable=False),  # 'owner', 'recruiter', 'sourcer', 'coordinator', 'viewer'
    sa.Column('job_access', sa.dialects.postgresql.JSONB, nullable=True),  # null = all, or list of client_ids
    sa.Column('invited_at', sa.DateTime, server_default=sa.func.now()),
    sa.Column('accepted_at', sa.DateTime, nullable=True),
    sa.Column('is_active', sa.Boolean, server_default='true'),
    sa.UniqueConstraint('recruiter_profile_id', 'user_id', name='uq_recruiter_team_member'),
)
```

### Table: `recruiter_clients`

```python
op.create_table(
    'recruiter_clients',
    sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
    sa.Column('recruiter_profile_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('recruiter_profiles.id', ondelete='CASCADE'), nullable=False),

    # Client company info
    sa.Column('company_name', sa.String(255), nullable=False),
    sa.Column('industry', sa.String(100), nullable=True),
    sa.Column('company_size', sa.String(50), nullable=True),
    sa.Column('website', sa.String(500), nullable=True),

    # Primary contact
    sa.Column('contact_name', sa.String(255), nullable=True),
    sa.Column('contact_email', sa.String(255), nullable=True),
    sa.Column('contact_phone', sa.String(50), nullable=True),
    sa.Column('contact_title', sa.String(255), nullable=True),

    # Contract details
    sa.Column('contract_type', sa.String(50), nullable=True),  # 'contingency', 'retained', 'rpo', 'contract_staffing'
    sa.Column('fee_percentage', sa.Numeric(5, 2), nullable=True),  # e.g., 20.00 for 20%
    sa.Column('flat_fee', sa.Numeric(10, 2), nullable=True),
    sa.Column('contract_start', sa.Date, nullable=True),
    sa.Column('contract_end', sa.Date, nullable=True),
    sa.Column('notes', sa.Text, nullable=True),

    # Status
    sa.Column('status', sa.String(30), server_default='active'),  # 'active', 'paused', 'completed', 'lost'

    sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
)
```

### Table: `recruiter_job_orders`

```python
op.create_table(
    'recruiter_job_orders',
    sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
    sa.Column('recruiter_profile_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('recruiter_profiles.id', ondelete='CASCADE'), nullable=False),
    sa.Column('client_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('recruiter_clients.id', ondelete='CASCADE'), nullable=False),
    sa.Column('assigned_to_user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),

    # Job details
    sa.Column('title', sa.String(255), nullable=False),
    sa.Column('description', sa.Text, nullable=True),
    sa.Column('requirements', sa.Text, nullable=True),
    sa.Column('location', sa.String(255), nullable=True),
    sa.Column('remote_policy', sa.String(30), nullable=True),
    sa.Column('employment_type', sa.String(30), nullable=True),
    sa.Column('salary_min', sa.Numeric(12, 2), nullable=True),
    sa.Column('salary_max', sa.Numeric(12, 2), nullable=True),
    sa.Column('salary_currency', sa.String(10), server_default='USD'),
    sa.Column('department', sa.String(100), nullable=True),

    # Pipeline tracking
    sa.Column('status', sa.String(30), server_default='open'),  # 'draft', 'open', 'on_hold', 'filled', 'cancelled'
    sa.Column('priority', sa.String(20), server_default='normal'),  # 'urgent', 'high', 'normal', 'low'
    sa.Column('target_start_date', sa.Date, nullable=True),
    sa.Column('positions_to_fill', sa.Integer, server_default='1'),
    sa.Column('positions_filled', sa.Integer, server_default='0'),

    # Fee info (inherited from client defaults, can override)
    sa.Column('fee_percentage', sa.Numeric(5, 2), nullable=True),
    sa.Column('flat_fee', sa.Numeric(10, 2), nullable=True),
    sa.Column('estimated_revenue', sa.Numeric(12, 2), nullable=True),

    sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
)
```

### Table: `recruiter_pipeline_candidates`

```python
op.create_table(
    'recruiter_pipeline_candidates',
    sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
    sa.Column('recruiter_profile_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('recruiter_profiles.id', ondelete='CASCADE'), nullable=False),
    sa.Column('job_order_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('recruiter_job_orders.id', ondelete='CASCADE'), nullable=True),
    sa.Column('candidate_profile_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('candidate_profiles.id', ondelete='SET NULL'), nullable=True),

    # For external candidates not on Winnow
    sa.Column('external_name', sa.String(255), nullable=True),
    sa.Column('external_email', sa.String(255), nullable=True),
    sa.Column('external_phone', sa.String(50), nullable=True),
    sa.Column('external_resume_url', sa.String(500), nullable=True),
    sa.Column('external_linkedin', sa.String(500), nullable=True),
    sa.Column('source', sa.String(100), nullable=True),  # 'winnow', 'linkedin', 'referral', 'job_board', 'internal_db'

    # Pipeline status
    sa.Column('stage', sa.String(50), server_default='sourced'),
    # 'sourced', 'contacted', 'screening', 'submitted_to_client', 'client_review',
    # 'interview_scheduled', 'interviewed', 'offer', 'placed', 'rejected', 'withdrawn'
    sa.Column('rating', sa.Integer, nullable=True),  # 1-5 stars
    sa.Column('tags', sa.dialects.postgresql.JSONB, nullable=True),
    sa.Column('notes', sa.Text, nullable=True),

    # Outreach tracking
    sa.Column('last_contacted_at', sa.DateTime, nullable=True),
    sa.Column('next_followup_at', sa.DateTime, nullable=True),
    sa.Column('outreach_count', sa.Integer, server_default='0'),

    # Match data (if Winnow candidate)
    sa.Column('match_score', sa.Numeric(5, 2), nullable=True),

    sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
)
```

### Table: `recruiter_activities`

```python
op.create_table(
    'recruiter_activities',
    sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
    sa.Column('recruiter_profile_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('recruiter_profiles.id', ondelete='CASCADE'), nullable=False),
    sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
    sa.Column('pipeline_candidate_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('recruiter_pipeline_candidates.id', ondelete='CASCADE'), nullable=True),
    sa.Column('job_order_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('recruiter_job_orders.id', ondelete='SET NULL'), nullable=True),
    sa.Column('client_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('recruiter_clients.id', ondelete='SET NULL'), nullable=True),

    sa.Column('activity_type', sa.String(50), nullable=False),
    # 'note', 'email_sent', 'email_received', 'call', 'meeting',
    # 'stage_change', 'linkedin_message', 'submission', 'interview_scheduled',
    # 'feedback_received', 'offer_extended', 'placement'
    sa.Column('subject', sa.String(500), nullable=True),
    sa.Column('body', sa.Text, nullable=True),
    sa.Column('metadata', sa.dialects.postgresql.JSONB, nullable=True),

    sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
)
```

### Indexes

```python
op.create_index('idx_recruiter_profiles_user_id', 'recruiter_profiles', ['user_id'])
op.create_index('idx_recruiter_clients_recruiter_id', 'recruiter_clients', ['recruiter_profile_id'])
op.create_index('idx_recruiter_clients_status', 'recruiter_clients', ['status'])
op.create_index('idx_recruiter_job_orders_recruiter_id', 'recruiter_job_orders', ['recruiter_profile_id'])
op.create_index('idx_recruiter_job_orders_client_id', 'recruiter_job_orders', ['client_id'])
op.create_index('idx_recruiter_job_orders_status', 'recruiter_job_orders', ['status'])
op.create_index('idx_recruiter_pipeline_recruiter_id', 'recruiter_pipeline_candidates', ['recruiter_profile_id'])
op.create_index('idx_recruiter_pipeline_job_order_id', 'recruiter_pipeline_candidates', ['job_order_id'])
op.create_index('idx_recruiter_pipeline_stage', 'recruiter_pipeline_candidates', ['stage'])
op.create_index('idx_recruiter_activities_recruiter_id', 'recruiter_activities', ['recruiter_profile_id'])
op.create_index('idx_recruiter_activities_created_at', 'recruiter_activities', ['created_at'])
```

### Modify `users` table

Add 'recruiter' to the role field's allowed values. If the `role` column uses a CHECK constraint, update it:

```python
# If role uses VARCHAR without CHECK, no change needed — just use 'recruiter' as a value.
# If role has a CHECK constraint, drop and recreate:
op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role")
op.execute("ALTER TABLE users ADD CONSTRAINT ck_users_role CHECK (role IN ('candidate', 'employer', 'recruiter', 'both', 'admin'))")
```

## Step 1.3 — Run the Migration

Open a terminal:

```powershell
cd services\api
alembic upgrade head
```

Verify no errors. If errors occur, check the migration file for typos.

---

# PART 2 — Backend Models

## Step 2.1 — Create Recruiter Models File

**File to create:** `services/api/app/models/recruiter.py`

Create this new file at the path above. It defines SQLAlchemy ORM models for all 6 recruiter tables.

```python
"""Recruiter segment models."""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, Text, DateTime, Date,
    Numeric, ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base  # adjust import to match your project's base


class RecruiterProfile(Base):
    __tablename__ = "recruiter_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)

    company_name = Column(String(255))
    company_website = Column(String(500))
    agency_type = Column(String(50))
    specializations = Column(JSONB)
    industries_served = Column(JSONB)
    locations_served = Column(JSONB)

    years_recruiting = Column(Integer)
    certifications = Column(JSONB)
    bio = Column(Text)
    linkedin_url = Column(String(500))
    phone = Column(String(50))

    subscription_tier = Column(String(20), default="free")
    stripe_customer_id = Column(String(255))
    stripe_subscription_id = Column(String(255))
    billing_email = Column(String(255))

    onboarding_completed = Column(Boolean, default=False)
    onboarding_step = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="recruiter_profile")
    team_members = relationship("RecruiterTeamMember", back_populates="recruiter_profile", cascade="all, delete-orphan")
    clients = relationship("RecruiterClient", back_populates="recruiter_profile", cascade="all, delete-orphan")
    job_orders = relationship("RecruiterJobOrder", back_populates="recruiter_profile", cascade="all, delete-orphan")
    pipeline_candidates = relationship("RecruiterPipelineCandidate", back_populates="recruiter_profile", cascade="all, delete-orphan")
    activities = relationship("RecruiterActivity", back_populates="recruiter_profile", cascade="all, delete-orphan")


class RecruiterTeamMember(Base):
    __tablename__ = "recruiter_team_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_profile_id = Column(UUID(as_uuid=True), ForeignKey("recruiter_profiles.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(30), nullable=False)
    job_access = Column(JSONB)
    invited_at = Column(DateTime, default=datetime.utcnow)
    accepted_at = Column(DateTime)
    is_active = Column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("recruiter_profile_id", "user_id", name="uq_recruiter_team_member"),)

    recruiter_profile = relationship("RecruiterProfile", back_populates="team_members")
    user = relationship("User")


class RecruiterClient(Base):
    __tablename__ = "recruiter_clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_profile_id = Column(UUID(as_uuid=True), ForeignKey("recruiter_profiles.id", ondelete="CASCADE"), nullable=False)

    company_name = Column(String(255), nullable=False)
    industry = Column(String(100))
    company_size = Column(String(50))
    website = Column(String(500))

    contact_name = Column(String(255))
    contact_email = Column(String(255))
    contact_phone = Column(String(50))
    contact_title = Column(String(255))

    contract_type = Column(String(50))
    fee_percentage = Column(Numeric(5, 2))
    flat_fee = Column(Numeric(10, 2))
    contract_start = Column(Date)
    contract_end = Column(Date)
    notes = Column(Text)

    status = Column(String(30), default="active")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    recruiter_profile = relationship("RecruiterProfile", back_populates="clients")
    job_orders = relationship("RecruiterJobOrder", back_populates="client", cascade="all, delete-orphan")


class RecruiterJobOrder(Base):
    __tablename__ = "recruiter_job_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_profile_id = Column(UUID(as_uuid=True), ForeignKey("recruiter_profiles.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(UUID(as_uuid=True), ForeignKey("recruiter_clients.id", ondelete="CASCADE"), nullable=False)
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    title = Column(String(255), nullable=False)
    description = Column(Text)
    requirements = Column(Text)
    location = Column(String(255))
    remote_policy = Column(String(30))
    employment_type = Column(String(30))
    salary_min = Column(Numeric(12, 2))
    salary_max = Column(Numeric(12, 2))
    salary_currency = Column(String(10), default="USD")
    department = Column(String(100))

    status = Column(String(30), default="open")
    priority = Column(String(20), default="normal")
    target_start_date = Column(Date)
    positions_to_fill = Column(Integer, default=1)
    positions_filled = Column(Integer, default=0)

    fee_percentage = Column(Numeric(5, 2))
    flat_fee = Column(Numeric(10, 2))
    estimated_revenue = Column(Numeric(12, 2))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    recruiter_profile = relationship("RecruiterProfile", back_populates="job_orders")
    client = relationship("RecruiterClient", back_populates="job_orders")
    pipeline_candidates = relationship("RecruiterPipelineCandidate", back_populates="job_order", cascade="all, delete-orphan")


class RecruiterPipelineCandidate(Base):
    __tablename__ = "recruiter_pipeline_candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_profile_id = Column(UUID(as_uuid=True), ForeignKey("recruiter_profiles.id", ondelete="CASCADE"), nullable=False)
    job_order_id = Column(UUID(as_uuid=True), ForeignKey("recruiter_job_orders.id", ondelete="CASCADE"), nullable=True)
    candidate_profile_id = Column(UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="SET NULL"), nullable=True)

    external_name = Column(String(255))
    external_email = Column(String(255))
    external_phone = Column(String(50))
    external_resume_url = Column(String(500))
    external_linkedin = Column(String(500))
    source = Column(String(100))

    stage = Column(String(50), default="sourced")
    rating = Column(Integer)
    tags = Column(JSONB)
    notes = Column(Text)

    last_contacted_at = Column(DateTime)
    next_followup_at = Column(DateTime)
    outreach_count = Column(Integer, default=0)

    match_score = Column(Numeric(5, 2))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    recruiter_profile = relationship("RecruiterProfile", back_populates="pipeline_candidates")
    job_order = relationship("RecruiterJobOrder", back_populates="pipeline_candidates")


class RecruiterActivity(Base):
    __tablename__ = "recruiter_activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_profile_id = Column(UUID(as_uuid=True), ForeignKey("recruiter_profiles.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    pipeline_candidate_id = Column(UUID(as_uuid=True), ForeignKey("recruiter_pipeline_candidates.id", ondelete="CASCADE"), nullable=True)
    job_order_id = Column(UUID(as_uuid=True), ForeignKey("recruiter_job_orders.id", ondelete="SET NULL"), nullable=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("recruiter_clients.id", ondelete="SET NULL"), nullable=True)

    activity_type = Column(String(50), nullable=False)
    subject = Column(String(500))
    body = Column(Text)
    metadata = Column(JSONB)

    created_at = Column(DateTime, default=datetime.utcnow)

    recruiter_profile = relationship("RecruiterProfile", back_populates="activities")
```

## Step 2.2 — Add Relationship to User Model

Open: `services/api/app/models/user.py` (or wherever the User model lives)

Add this relationship (if not already present):

```python
recruiter_profile = relationship("RecruiterProfile", back_populates="user", uselist=False)
```

## Step 2.3 — Export Models in __init__.py

Open: `services/api/app/models/__init__.py`

Add these imports:

```python
from app.models.recruiter import (
    RecruiterProfile,
    RecruiterTeamMember,
    RecruiterClient,
    RecruiterJobOrder,
    RecruiterPipelineCandidate,
    RecruiterActivity,
)
```

---

# PART 3 — Backend Schemas

## Step 3.1 — Create Pydantic Schemas

**File to create:** `services/api/app/schemas/recruiter.py`

```python
"""Pydantic schemas for the recruiter segment."""

from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


# --- Recruiter Profile ---

class RecruiterProfileCreate(BaseModel):
    company_name: Optional[str] = None
    company_website: Optional[str] = None
    agency_type: Optional[str] = None
    specializations: Optional[list[str]] = None
    industries_served: Optional[list[str]] = None
    locations_served: Optional[list[str]] = None
    years_recruiting: Optional[int] = None
    certifications: Optional[list[str]] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    billing_email: Optional[str] = None


class RecruiterProfileUpdate(BaseModel):
    company_name: Optional[str] = None
    company_website: Optional[str] = None
    agency_type: Optional[str] = None
    specializations: Optional[list[str]] = None
    industries_served: Optional[list[str]] = None
    locations_served: Optional[list[str]] = None
    years_recruiting: Optional[int] = None
    certifications: Optional[list[str]] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    billing_email: Optional[str] = None


class RecruiterProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    company_name: Optional[str] = None
    company_website: Optional[str] = None
    agency_type: Optional[str] = None
    specializations: Optional[list[str]] = None
    industries_served: Optional[list[str]] = None
    locations_served: Optional[list[str]] = None
    years_recruiting: Optional[int] = None
    certifications: Optional[list[str]] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    subscription_tier: str = "free"
    onboarding_completed: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Clients ---

class RecruiterClientCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    industry: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_title: Optional[str] = None
    contract_type: Optional[str] = None
    fee_percentage: Optional[float] = None
    flat_fee: Optional[float] = None
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("contract_type")
    @classmethod
    def validate_contract_type(cls, v):
        if v and v not in ("contingency", "retained", "rpo", "contract_staffing"):
            raise ValueError("Invalid contract_type")
        return v


class RecruiterClientUpdate(BaseModel):
    company_name: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_title: Optional[str] = None
    contract_type: Optional[str] = None
    fee_percentage: Optional[float] = None
    flat_fee: Optional[float] = None
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class RecruiterClientResponse(BaseModel):
    id: UUID
    company_name: str
    industry: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_title: Optional[str] = None
    contract_type: Optional[str] = None
    fee_percentage: Optional[float] = None
    flat_fee: Optional[float] = None
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None
    notes: Optional[str] = None
    status: str = "active"
    created_at: datetime
    job_order_count: Optional[int] = 0

    model_config = {"from_attributes": True}


# --- Job Orders ---

class RecruiterJobOrderCreate(BaseModel):
    client_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    requirements: Optional[str] = None
    location: Optional[str] = None
    remote_policy: Optional[str] = None
    employment_type: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: str = "USD"
    department: Optional[str] = None
    priority: str = "normal"
    target_start_date: Optional[date] = None
    positions_to_fill: int = 1
    fee_percentage: Optional[float] = None
    flat_fee: Optional[float] = None
    assigned_to_user_id: Optional[UUID] = None


class RecruiterJobOrderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    location: Optional[str] = None
    remote_policy: Optional[str] = None
    employment_type: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    department: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    target_start_date: Optional[date] = None
    positions_to_fill: Optional[int] = None
    positions_filled: Optional[int] = None
    fee_percentage: Optional[float] = None
    flat_fee: Optional[float] = None
    assigned_to_user_id: Optional[UUID] = None


class RecruiterJobOrderResponse(BaseModel):
    id: UUID
    client_id: UUID
    client_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    requirements: Optional[str] = None
    location: Optional[str] = None
    remote_policy: Optional[str] = None
    employment_type: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: str = "USD"
    department: Optional[str] = None
    status: str = "open"
    priority: str = "normal"
    target_start_date: Optional[date] = None
    positions_to_fill: int = 1
    positions_filled: int = 0
    fee_percentage: Optional[float] = None
    estimated_revenue: Optional[float] = None
    pipeline_count: Optional[int] = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Pipeline Candidates ---

class PipelineCandidateCreate(BaseModel):
    job_order_id: Optional[UUID] = None
    candidate_profile_id: Optional[UUID] = None
    external_name: Optional[str] = None
    external_email: Optional[str] = None
    external_phone: Optional[str] = None
    external_resume_url: Optional[str] = None
    external_linkedin: Optional[str] = None
    source: Optional[str] = None
    stage: str = "sourced"
    rating: Optional[int] = Field(None, ge=1, le=5)
    tags: Optional[list[str]] = None
    notes: Optional[str] = None


class PipelineCandidateUpdate(BaseModel):
    job_order_id: Optional[UUID] = None
    stage: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    tags: Optional[list[str]] = None
    notes: Optional[str] = None
    next_followup_at: Optional[datetime] = None


class PipelineCandidateResponse(BaseModel):
    id: UUID
    job_order_id: Optional[UUID] = None
    candidate_profile_id: Optional[UUID] = None
    external_name: Optional[str] = None
    external_email: Optional[str] = None
    source: Optional[str] = None
    stage: str
    rating: Optional[int] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = None
    match_score: Optional[float] = None
    last_contacted_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None
    outreach_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Activities ---

class RecruiterActivityCreate(BaseModel):
    pipeline_candidate_id: Optional[UUID] = None
    job_order_id: Optional[UUID] = None
    client_id: Optional[UUID] = None
    activity_type: str
    subject: Optional[str] = None
    body: Optional[str] = None
    metadata: Optional[dict] = None


class RecruiterActivityResponse(BaseModel):
    id: UUID
    activity_type: str
    subject: Optional[str] = None
    body: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Team ---

class RecruiterTeamInvite(BaseModel):
    email: str
    role: str = "recruiter"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in ("owner", "recruiter", "sourcer", "coordinator", "viewer"):
            raise ValueError("Invalid team role")
        return v


class RecruiterTeamMemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    role: str
    email: Optional[str] = None
    name: Optional[str] = None
    invited_at: datetime
    accepted_at: Optional[datetime] = None
    is_active: bool

    model_config = {"from_attributes": True}


# --- Dashboard ---

class RecruiterDashboardResponse(BaseModel):
    active_job_orders: int = 0
    total_pipeline_candidates: int = 0
    candidates_in_interview: int = 0
    placements_this_month: int = 0
    revenue_this_month: float = 0.0
    active_clients: int = 0
    upcoming_followups: int = 0
    subscription_tier: str = "free"
```

## Step 3.2 — Export Schemas

Open: `services/api/app/schemas/__init__.py`

Add:

```python
from app.schemas.recruiter import *
```

---

# PART 4 — Backend Services

## Step 4.1 — Create Recruiter Service

**File to create:** `services/api/app/services/recruiter_service.py`

This service handles all recruiter business logic: profile CRUD, client management, job orders, pipeline, activities, and dashboard aggregation.

```python
"""Recruiter segment business logic."""

from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.recruiter import (
    RecruiterProfile, RecruiterClient, RecruiterJobOrder,
    RecruiterPipelineCandidate, RecruiterActivity, RecruiterTeamMember,
)
from app.models.user import User


# --- Profile ---

def get_or_create_profile(user_id: UUID, db: Session) -> RecruiterProfile:
    profile = db.query(RecruiterProfile).filter_by(user_id=user_id).first()
    if not profile:
        profile = RecruiterProfile(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def update_profile(user_id: UUID, data: dict, db: Session) -> RecruiterProfile:
    profile = get_or_create_profile(user_id, db)
    for key, value in data.items():
        if value is not None and hasattr(profile, key):
            setattr(profile, key, value)
    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    return profile


def complete_onboarding(user_id: UUID, db: Session) -> RecruiterProfile:
    profile = get_or_create_profile(user_id, db)
    profile.onboarding_completed = True
    db.commit()
    db.refresh(profile)
    return profile


# --- Clients ---

def create_client(recruiter_profile_id: UUID, data: dict, db: Session) -> RecruiterClient:
    client = RecruiterClient(recruiter_profile_id=recruiter_profile_id, **data)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def list_clients(recruiter_profile_id: UUID, status: str | None, db: Session) -> list[RecruiterClient]:
    q = db.query(RecruiterClient).filter_by(recruiter_profile_id=recruiter_profile_id)
    if status:
        q = q.filter_by(status=status)
    return q.order_by(RecruiterClient.company_name).all()


def update_client(client_id: UUID, recruiter_profile_id: UUID, data: dict, db: Session) -> RecruiterClient | None:
    client = db.query(RecruiterClient).filter_by(id=client_id, recruiter_profile_id=recruiter_profile_id).first()
    if not client:
        return None
    for key, value in data.items():
        if value is not None and hasattr(client, key):
            setattr(client, key, value)
    client.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(client)
    return client


def delete_client(client_id: UUID, recruiter_profile_id: UUID, db: Session) -> bool:
    client = db.query(RecruiterClient).filter_by(id=client_id, recruiter_profile_id=recruiter_profile_id).first()
    if not client:
        return False
    db.delete(client)
    db.commit()
    return True


# --- Job Orders ---

def create_job_order(recruiter_profile_id: UUID, data: dict, db: Session) -> RecruiterJobOrder:
    # Calculate estimated revenue if fee info provided
    if data.get("fee_percentage") and data.get("salary_max"):
        data["estimated_revenue"] = float(data["salary_max"]) * float(data["fee_percentage"]) / 100
    order = RecruiterJobOrder(recruiter_profile_id=recruiter_profile_id, **data)
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def list_job_orders(recruiter_profile_id: UUID, status: str | None, client_id: UUID | None, db: Session):
    q = db.query(RecruiterJobOrder).filter_by(recruiter_profile_id=recruiter_profile_id)
    if status:
        q = q.filter_by(status=status)
    if client_id:
        q = q.filter_by(client_id=client_id)
    return q.order_by(RecruiterJobOrder.created_at.desc()).all()


def update_job_order(order_id: UUID, recruiter_profile_id: UUID, data: dict, db: Session):
    order = db.query(RecruiterJobOrder).filter_by(id=order_id, recruiter_profile_id=recruiter_profile_id).first()
    if not order:
        return None
    for key, value in data.items():
        if value is not None and hasattr(order, key):
            setattr(order, key, value)
    order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(order)
    return order


# --- Pipeline ---

def add_to_pipeline(recruiter_profile_id: UUID, data: dict, db: Session) -> RecruiterPipelineCandidate:
    candidate = RecruiterPipelineCandidate(recruiter_profile_id=recruiter_profile_id, **data)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def list_pipeline(recruiter_profile_id: UUID, job_order_id: UUID | None, stage: str | None, db: Session):
    q = db.query(RecruiterPipelineCandidate).filter_by(recruiter_profile_id=recruiter_profile_id)
    if job_order_id:
        q = q.filter_by(job_order_id=job_order_id)
    if stage:
        q = q.filter_by(stage=stage)
    return q.order_by(RecruiterPipelineCandidate.created_at.desc()).all()


def update_pipeline_candidate(candidate_id: UUID, recruiter_profile_id: UUID, data: dict, db: Session):
    pc = db.query(RecruiterPipelineCandidate).filter_by(id=candidate_id, recruiter_profile_id=recruiter_profile_id).first()
    if not pc:
        return None
    old_stage = pc.stage
    for key, value in data.items():
        if value is not None and hasattr(pc, key):
            setattr(pc, key, value)
    pc.updated_at = datetime.utcnow()
    # Log stage change as activity
    if data.get("stage") and data["stage"] != old_stage:
        activity = RecruiterActivity(
            recruiter_profile_id=recruiter_profile_id,
            pipeline_candidate_id=candidate_id,
            job_order_id=pc.job_order_id,
            activity_type="stage_change",
            subject=f"Stage changed: {old_stage} → {data['stage']}",
            metadata={"old_stage": old_stage, "new_stage": data["stage"]},
        )
        db.add(activity)
    db.commit()
    db.refresh(pc)
    return pc


def delete_pipeline_candidate(candidate_id: UUID, recruiter_profile_id: UUID, db: Session) -> bool:
    pc = db.query(RecruiterPipelineCandidate).filter_by(id=candidate_id, recruiter_profile_id=recruiter_profile_id).first()
    if not pc:
        return False
    db.delete(pc)
    db.commit()
    return True


# --- Activities ---

def log_activity(recruiter_profile_id: UUID, data: dict, db: Session) -> RecruiterActivity:
    activity = RecruiterActivity(recruiter_profile_id=recruiter_profile_id, **data)
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def list_activities(recruiter_profile_id: UUID, limit: int, db: Session):
    return (
        db.query(RecruiterActivity)
        .filter_by(recruiter_profile_id=recruiter_profile_id)
        .order_by(RecruiterActivity.created_at.desc())
        .limit(limit)
        .all()
    )


# --- Dashboard ---

def get_dashboard_stats(recruiter_profile_id: UUID, db: Session) -> dict:
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    tomorrow = now + timedelta(days=1)

    active_orders = db.query(func.count(RecruiterJobOrder.id)).filter_by(
        recruiter_profile_id=recruiter_profile_id, status="open"
    ).scalar() or 0

    total_pipeline = db.query(func.count(RecruiterPipelineCandidate.id)).filter_by(
        recruiter_profile_id=recruiter_profile_id
    ).scalar() or 0

    in_interview = db.query(func.count(RecruiterPipelineCandidate.id)).filter(
        RecruiterPipelineCandidate.recruiter_profile_id == recruiter_profile_id,
        RecruiterPipelineCandidate.stage.in_(["interview_scheduled", "interviewed"])
    ).scalar() or 0

    placements = db.query(func.count(RecruiterPipelineCandidate.id)).filter(
        RecruiterPipelineCandidate.recruiter_profile_id == recruiter_profile_id,
        RecruiterPipelineCandidate.stage == "placed",
        RecruiterPipelineCandidate.updated_at >= month_start,
    ).scalar() or 0

    active_clients = db.query(func.count(RecruiterClient.id)).filter_by(
        recruiter_profile_id=recruiter_profile_id, status="active"
    ).scalar() or 0

    upcoming_followups = db.query(func.count(RecruiterPipelineCandidate.id)).filter(
        RecruiterPipelineCandidate.recruiter_profile_id == recruiter_profile_id,
        RecruiterPipelineCandidate.next_followup_at != None,
        RecruiterPipelineCandidate.next_followup_at <= tomorrow,
    ).scalar() or 0

    profile = db.query(RecruiterProfile).filter_by(id=recruiter_profile_id).first()

    return {
        "active_job_orders": active_orders,
        "total_pipeline_candidates": total_pipeline,
        "candidates_in_interview": in_interview,
        "placements_this_month": placements,
        "revenue_this_month": 0.0,  # TODO: calculate from placed candidates × fees
        "active_clients": active_clients,
        "upcoming_followups": upcoming_followups,
        "subscription_tier": profile.subscription_tier if profile else "free",
    }
```

## Step 4.2 — Create Recruiter Billing Constants

Open: `services/api/app/services/billing.py`

Add the recruiter plan limits alongside the existing `CANDIDATE_PLAN_LIMITS`:

```python
RECRUITER_PLAN_LIMITS = {
    "free": {
        "active_job_orders": 3,
        "pipeline_candidates": 25,
        "clients": 2,
        "team_members": 0,
        "activities_per_day": 20,
        "candidate_search": False,
        "bulk_outreach": False,
        "analytics": False,
        "data_export": False,
    },
    "solo": {
        "active_job_orders": 25,
        "pipeline_candidates": 500,
        "clients": 15,
        "team_members": 0,
        "activities_per_day": -1,  # unlimited
        "candidate_search": True,
        "bulk_outreach": False,
        "analytics": True,
        "data_export": True,
    },
    "team": {
        "active_job_orders": 100,
        "pipeline_candidates": 2000,
        "clients": 50,
        "team_members": 10,
        "activities_per_day": -1,
        "candidate_search": True,
        "bulk_outreach": True,
        "analytics": True,
        "data_export": True,
    },
    "agency": {
        "active_job_orders": -1,  # unlimited
        "pipeline_candidates": -1,
        "clients": -1,
        "team_members": -1,
        "activities_per_day": -1,
        "candidate_search": True,
        "bulk_outreach": True,
        "analytics": True,
        "data_export": True,
        "api_access": True,
        "white_label": True,
    },
}
```

---

# PART 5 — Backend Routes

## Step 5.1 — Create Recruiter Router

**File to create (or heavily modify):** `services/api/app/routers/recruiter.py`

If this file already exists with a basic stub, replace its contents entirely. If it doesn't exist, create it.

The router should define these endpoints:

```
# Profile
POST   /api/recruiter/register          — create profile + set user role
GET    /api/recruiter/profile            — get current recruiter profile
PUT    /api/recruiter/profile            — update profile
POST   /api/recruiter/onboarding/complete — mark onboarding done

# Dashboard
GET    /api/recruiter/dashboard          — dashboard stats

# Clients
GET    /api/recruiter/clients            — list clients (query: ?status=active)
POST   /api/recruiter/clients            — create client
GET    /api/recruiter/clients/{id}       — get client detail
PUT    /api/recruiter/clients/{id}       — update client
DELETE /api/recruiter/clients/{id}       — delete client

# Job Orders
GET    /api/recruiter/job-orders         — list job orders (query: ?status=open&client_id=...)
POST   /api/recruiter/job-orders         — create job order
GET    /api/recruiter/job-orders/{id}    — get job order detail
PUT    /api/recruiter/job-orders/{id}    — update job order
DELETE /api/recruiter/job-orders/{id}    — delete job order

# Pipeline
GET    /api/recruiter/pipeline           — list pipeline candidates (query: ?job_order_id=...&stage=...)
POST   /api/recruiter/pipeline           — add candidate to pipeline
PUT    /api/recruiter/pipeline/{id}      — update pipeline candidate (stage change, notes, rating)
DELETE /api/recruiter/pipeline/{id}      — remove from pipeline

# Activities
GET    /api/recruiter/activities         — list recent activities (query: ?limit=50)
POST   /api/recruiter/activities         — log activity

# Team (Team/Agency tiers only)
GET    /api/recruiter/team               — list team members
POST   /api/recruiter/team/invite        — invite team member
DELETE /api/recruiter/team/{id}          — remove team member
```

All endpoints should:
- Use `get_current_user` for authentication
- Verify the user has role 'recruiter'
- Verify `recruiter_profile_id` matches the current user (multi-tenant security)
- Return proper HTTP status codes (201 for creation, 404 for not found, 403 for forbidden)

## Step 5.2 — Register Router in main.py

Open: `services/api/app/main.py`

Add:

```python
from app.routers import recruiter
app.include_router(recruiter.router, prefix="/api/recruiter", tags=["recruiter"])
```

---

# PART 6 — Frontend: Auth & Role Routing

## Step 6.1 — Update Auth Context for Recruiter Role

Open: `apps/web/app/` — find the auth context or hook (likely in `context/AuthContext.tsx` or `hooks/useAuth.ts` or similar).

Ensure the user object includes the `role` field and that routing logic recognizes `'recruiter'` as a valid role.

## Step 6.2 — Add Recruiter Route Guard

The recruiter pages need a role check. Create or update a route guard:

**File to create:** `apps/web/app/recruiter/layout.tsx`

```tsx
"use client";

import { useAuth } from "@/hooks/useAuth"; // adjust import path
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function RecruiterLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
    // If user exists but no recruiter profile, redirect to onboarding
    if (!loading && user && user.role !== "recruiter") {
      router.push("/dashboard");
    }
  }, [user, loading, router]);

  if (loading) return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  if (!user) return null;

  return <>{children}</>;
}
```

---

# PART 7 — Frontend: Recruiter Pages

## Overview of pages to create

All recruiter pages go inside: `apps/web/app/recruiter/`

```
apps/web/app/recruiter/
├── layout.tsx              (Part 6 above — route guard + sidebar)
├── onboarding/
│   └── page.tsx            (Step 7.1)
├── dashboard/
│   └── page.tsx            (Step 7.2)
├── clients/
│   ├── page.tsx            (Step 7.3 — client list)
│   └── [id]/
│       └── page.tsx        (Step 7.4 — client detail)
├── job-orders/
│   ├── page.tsx            (Step 7.5 — job order list)
│   └── [id]/
│       └── page.tsx        (Step 7.6 — job order detail with pipeline)
├── pipeline/
│   └── page.tsx            (Step 7.7 — full pipeline Kanban view)
├── settings/
│   └── page.tsx            (Step 7.8 — profile, billing, team)
└── components/
    ├── RecruiterSidebar.tsx (Step 7.9)
    ├── PipelineKanban.tsx   (Step 7.10)
    └── ActivityFeed.tsx     (Step 7.11)
```

## Step 7.1 — Recruiter Onboarding Page

**File to create:** `apps/web/app/recruiter/onboarding/page.tsx`

Multi-step onboarding form:
1. **Step 1 — About You:** Company name, agency type (dropdown: Independent, Boutique, Staffing Agency, Executive Search, RPO), years recruiting, bio
2. **Step 2 — Specializations:** Multi-select for industries served, locations served, specializations (tech, healthcare, finance, etc.)
3. **Step 3 — First Client:** Optional — add first client company name, contract type, fee %
4. **Step 4 — Complete:** Welcome message, link to dashboard

On submit, call `POST /api/recruiter/register` then `PUT /api/recruiter/profile` then `POST /api/recruiter/onboarding/complete`.

Style: Match the existing candidate/employer onboarding style. Dark theme, clean forms, progress indicator.

## Step 7.2 — Recruiter Dashboard

**File to create:** `apps/web/app/recruiter/dashboard/page.tsx`

Fetch data from `GET /api/recruiter/dashboard`.

Layout:
- **Stats cards row:** Active Job Orders, Pipeline Candidates, In Interview, Placements This Month, Active Clients, Revenue This Month
- **Upcoming Follow-ups panel:** List of pipeline candidates with `next_followup_at` in next 48 hours
- **Recent Activity feed:** Last 10 activities from `GET /api/recruiter/activities?limit=10`
- **Quick Actions:** "Add Client", "Create Job Order", "Add Candidate to Pipeline" buttons

## Step 7.3 — Client List Page

**File to create:** `apps/web/app/recruiter/clients/page.tsx`

- Fetch from `GET /api/recruiter/clients`
- Table/card view: company name, industry, contract type, fee %, # active job orders, status
- Filter by status (active/paused/completed/lost)
- "Add Client" button → opens modal or navigates to create form
- Click row → navigates to `/recruiter/clients/[id]`

## Step 7.4 — Client Detail Page

**File to create:** `apps/web/app/recruiter/clients/[id]/page.tsx`

- Client profile info (editable)
- Tab: "Job Orders" — list of job orders for this client
- Tab: "Activities" — activity log filtered by this client
- "Create Job Order" button

## Step 7.5 — Job Orders List Page

**File to create:** `apps/web/app/recruiter/job-orders/page.tsx`

- Fetch from `GET /api/recruiter/job-orders`
- Table: title, client name, status, priority, salary range, pipeline count, created date
- Filter by status (open/on_hold/filled/cancelled) and client
- "Create Job Order" button
- Click row → navigates to `/recruiter/job-orders/[id]`

## Step 7.6 — Job Order Detail Page

**File to create:** `apps/web/app/recruiter/job-orders/[id]/page.tsx`

- Job order details (editable)
- **Pipeline section:** Kanban board showing candidates in this job order's pipeline
  - Columns: Sourced → Contacted → Screening → Submitted → Client Review → Interview → Offer → Placed
  - Each card: name, source, rating (stars), last contacted
  - Drag-and-drop between columns to change stage
- "Add Candidate" button → modal to add Winnow candidate or external candidate
- Activity feed for this job order

## Step 7.7 — Full Pipeline View

**File to create:** `apps/web/app/recruiter/pipeline/page.tsx`

- Cross-job-order Kanban showing ALL pipeline candidates
- Filter by: job order, client, stage, source, tags
- Search by name/email
- Bulk actions: tag, move stage, export

## Step 7.8 — Settings Page

**File to create:** `apps/web/app/recruiter/settings/page.tsx`

- **Profile section:** Edit recruiter profile fields
- **Billing section:** Current tier badge, usage stats, upgrade button
  - Free → Solo ($79/mo), Team ($149/mo), Agency ($299/mo)
  - Usage bars: X/Y job orders, X/Y pipeline candidates, X/Y clients
  - "Manage Billing" button → Stripe portal
- **Team section** (Team/Agency tiers only): List team members, invite new, remove
- **Danger zone:** Delete account

## Step 7.9 — Recruiter Sidebar Component

**File to create:** `apps/web/app/recruiter/components/RecruiterSidebar.tsx`

Sidebar navigation for all recruiter pages:
- Dashboard (icon: LayoutDashboard)
- Clients (icon: Building2)
- Job Orders (icon: Briefcase)
- Pipeline (icon: Users)
- Settings (icon: Settings)

Include: tier badge, user name, notification count for upcoming follow-ups.

Update `layout.tsx` to include the sidebar alongside the main content.

## Step 7.10 — Pipeline Kanban Component

**File to create:** `apps/web/app/recruiter/components/PipelineKanban.tsx`

Reusable Kanban board:
- Accepts: list of pipeline candidates, stage configuration
- Renders columns with drag-and-drop (use HTML5 drag API or a library like `@hello-pangea/dnd`)
- Each card shows: candidate name, source badge, rating stars, days in stage
- On drop: calls `PUT /api/recruiter/pipeline/{id}` with new stage

## Step 7.11 — Activity Feed Component

**File to create:** `apps/web/app/recruiter/components/ActivityFeed.tsx`

Reusable activity feed timeline:
- Accepts: list of activities
- Renders: icon per activity type, timestamp, subject, body preview
- Expandable items for full body text

---

# PART 8 — Recruiter Billing

## Step 8.1 — Add Stripe Price IDs to .env

Add these to `services/api/.env`:

```
STRIPE_PRICE_RECRUITER_SOLO_MO=price_placeholder_recruiter_solo
STRIPE_PRICE_RECRUITER_TEAM_MO=price_placeholder_recruiter_team
STRIPE_PRICE_RECRUITER_AGENCY_MO=price_placeholder_recruiter_agency
```

## Step 8.2 — Add Recruiter Checkout Endpoint

Open: `services/api/app/routers/billing.py`

Add a new endpoint or extend the existing checkout to handle recruiter tiers:

```python
@router.post("/api/billing/recruiter/checkout")
async def recruiter_checkout(
    tier: str,  # 'solo', 'team', 'agency'
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Map tier to Stripe price ID
    price_map = {
        "solo": os.getenv("STRIPE_PRICE_RECRUITER_SOLO_MO"),
        "team": os.getenv("STRIPE_PRICE_RECRUITER_TEAM_MO"),
        "agency": os.getenv("STRIPE_PRICE_RECRUITER_AGENCY_MO"),
    }
    # Create Stripe checkout session, return URL
    # On webhook success, update recruiter_profiles.subscription_tier
```

## Step 8.3 — Update Webhook Handler

Open: `services/api/app/routers/billing.py` (or wherever the Stripe webhook lives)

In the `checkout.session.completed` handler, detect recruiter subscriptions and update `recruiter_profiles.subscription_tier`.

---

# PART 9 — Landing Page: Recruiter Audience Content

## Step 9.1 — Update Recruiter Tab Content

Open: `apps/web/app/page.tsx`

Find the audience toggle section (seeker/employer/recruiter tabs). The recruiter tab likely has placeholder content. Replace with:

**Hero:**
- Headline: "Stop Juggling Spreadsheets. Start Placing Candidates."
- Subheadline: "Winnow replaces Bullhorn, Recruit CRM, and spreadsheet chaos with an AI-powered recruiting platform that manages clients, pipelines, and placements from one dashboard."
- CTA: "Start Free Trial" → /recruiter/onboarding

**Features (recruiter-specific):**
1. **Client & Job Order Management** — Organize clients, contracts, fee structures, and job orders in one place
2. **AI-Powered Pipeline CRM** — Track candidates from sourcing to placement with Kanban boards and automated stage tracking
3. **Smart Candidate Matching** — Winnow's 6-dimension matching engine finds candidates who actually fit the job order
4. **Activity Logging & Follow-ups** — Never miss a follow-up with automated reminders and full activity history
5. **Team Collaboration** — Assign job orders, share pipelines, and coordinate with your team (Team/Agency tiers)
6. **Revenue Tracking** — Track fees, estimated revenue, and placements per client

**Pricing (recruiter-specific):**

| Feature | Free | Solo $79/mo | Team $149/mo | Agency $299/mo |
|---------|------|-------------|--------------|----------------|
| Job Orders | 3 | 25 | 100 | Unlimited |
| Pipeline Candidates | 25 | 500 | 2,000 | Unlimited |
| Clients | 2 | 15 | 50 | Unlimited |
| Team Members | — | — | 10 | Unlimited |
| Candidate Search | — | ✓ | ✓ | ✓ |
| Bulk Outreach | — | — | ✓ | ✓ |
| Analytics | — | ✓ | ✓ | ✓ |
| API Access | — | — | — | ✓ |

**Competitive Comparison (recruiter-specific):**
Compare Winnow vs. Bullhorn, Recruit CRM, CATSOne, Zoho Recruit on: pricing transparency, AI matching, pipeline management, ease of setup, reporting.

---

# PART 10 — Verification & Testing

## Step 10.1 — Run the Migration

```powershell
cd services\api
alembic upgrade head
```

Verify: No errors. All 6 tables created.

## Step 10.2 — Start Backend

```powershell
cd services\api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Check: `http://127.0.0.1:8000/docs` — verify all `/api/recruiter/*` endpoints appear.

## Step 10.3 — Test API Endpoints

Using the Swagger UI or curl:

1. Register as recruiter: `POST /api/recruiter/register` with a valid auth cookie
2. Get profile: `GET /api/recruiter/profile`
3. Create client: `POST /api/recruiter/clients` with `{"company_name": "Acme Corp"}`
4. Create job order: `POST /api/recruiter/job-orders` with `{"client_id": "...", "title": "Senior Engineer"}`
5. Add to pipeline: `POST /api/recruiter/pipeline` with `{"job_order_id": "...", "external_name": "Jane Doe", "source": "linkedin"}`
6. Update stage: `PUT /api/recruiter/pipeline/{id}` with `{"stage": "contacted"}`
7. Get dashboard: `GET /api/recruiter/dashboard`

## Step 10.4 — Start Frontend

```powershell
cd apps\web
npm run dev
```

## Step 10.5 — Verify Frontend Pages

1. Go to `http://localhost:3000` → click "Recruiters" audience tab → verify hero, features, pricing
2. Click "Start Free Trial" → verify redirect to `/recruiter/onboarding`
3. Complete onboarding → verify redirect to `/recruiter/dashboard`
4. Navigate to: `/recruiter/clients`, `/recruiter/job-orders`, `/recruiter/pipeline`, `/recruiter/settings`
5. Create a client, create a job order, add a pipeline candidate, change stage
6. Verify sidebar navigation highlights active page
7. Verify dashboard stats update after creating data

---

## Data Model Relationships

```
User (role: 'recruiter')
  └─> RecruiterProfile (1:1)
        ├─> RecruiterTeamMember (1:many)
        ├─> RecruiterClient (1:many)
        │     └─> RecruiterJobOrder (1:many)
        │           └─> RecruiterPipelineCandidate (1:many)
        ├─> RecruiterPipelineCandidate (1:many — cross-job-order view)
        └─> RecruiterActivity (1:many — full audit trail)
```

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Migration | `services/api/alembic/versions/xxx_add_recruiter_segment_tables.py` | CREATE |
| Models | `services/api/app/models/recruiter.py` | CREATE |
| Models init | `services/api/app/models/__init__.py` | MODIFY — add imports |
| User model | `services/api/app/models/user.py` | MODIFY — add relationship |
| Schemas | `services/api/app/schemas/recruiter.py` | CREATE |
| Schemas init | `services/api/app/schemas/__init__.py` | MODIFY — add imports |
| Service | `services/api/app/services/recruiter_service.py` | CREATE |
| Billing constants | `services/api/app/services/billing.py` | MODIFY — add RECRUITER_PLAN_LIMITS |
| Router | `services/api/app/routers/recruiter.py` | CREATE or REPLACE |
| Main | `services/api/app/main.py` | MODIFY — register router |
| Env | `services/api/.env` | MODIFY — add Stripe price IDs |
| Recruiter layout | `apps/web/app/recruiter/layout.tsx` | CREATE |
| Onboarding page | `apps/web/app/recruiter/onboarding/page.tsx` | CREATE |
| Dashboard page | `apps/web/app/recruiter/dashboard/page.tsx` | CREATE |
| Clients page | `apps/web/app/recruiter/clients/page.tsx` | CREATE |
| Client detail | `apps/web/app/recruiter/clients/[id]/page.tsx` | CREATE |
| Job orders page | `apps/web/app/recruiter/job-orders/page.tsx` | CREATE |
| Job order detail | `apps/web/app/recruiter/job-orders/[id]/page.tsx` | CREATE |
| Pipeline page | `apps/web/app/recruiter/pipeline/page.tsx` | CREATE |
| Settings page | `apps/web/app/recruiter/settings/page.tsx` | CREATE |
| Sidebar component | `apps/web/app/recruiter/components/RecruiterSidebar.tsx` | CREATE |
| Kanban component | `apps/web/app/recruiter/components/PipelineKanban.tsx` | CREATE |
| Activity feed | `apps/web/app/recruiter/components/ActivityFeed.tsx` | CREATE |
| Landing page | `apps/web/app/page.tsx` | MODIFY — recruiter tab content |
| Billing router | `services/api/app/routers/billing.py` | MODIFY — add recruiter checkout |

---

## Success Criteria

✅ All 6 recruiter database tables created and migrated
✅ SQLAlchemy models with proper relationships and cascades
✅ Pydantic schemas with validation for all CRUD operations
✅ Service layer with full business logic (profile, clients, job orders, pipeline, activities, dashboard)
✅ 20+ API endpoints registered and working at `/api/recruiter/*`
✅ Recruiter billing tiers (free/solo/team/agency) with feature gates
✅ Stripe checkout and webhook handling for recruiter subscriptions
✅ Frontend onboarding flow (4-step)
✅ Dashboard with stats cards, follow-ups, and activity feed
✅ Client management with CRUD and contract tracking
✅ Job order management with status, priority, and fee tracking
✅ Pipeline CRM with Kanban drag-and-drop and stage tracking
✅ Activity logging with full audit trail
✅ Team management for Team/Agency tiers
✅ Settings page with profile, billing, and team sections
✅ Landing page recruiter tab with hero, features, pricing, and competitive comparison
✅ All data scoped to recruiter (multi-tenant security — no cross-recruiter data leaks)
✅ Sidebar navigation with active page highlighting

---

**Status:** Ready for implementation
**Estimated Time:** 4–6 hours (experienced developer) / 8–12 hours (following step-by-step)
**Dependencies:** PROMPTs 33–43 (employer segment patterns), PROMPT44 (strategic plan)
**Next Prompt:** PROMPT54 (Market Intelligence & Compensation Benchmarking)
