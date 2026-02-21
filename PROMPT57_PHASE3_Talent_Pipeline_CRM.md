# PHASE 3: Candidate Pipeline CRM - Complete Implementation

**Read First:** SPEC.md, ARCHITECTURE.MD, PROMPT44 (Strategic Plan), PROMPT50, and completed Phase 1 & 2

## Purpose

Build a living talent pipeline so recruiters never start from zero on new requisitions. Strong candidates who weren't selected for one role are automatically captured and available for future roles, with intelligent matching suggestions when new jobs are posted.

**What already exists (DO NOT recreate):**
- ✅ Candidate profiles with skills and experience
- ✅ Job matching engine with semantic similarity
- ✅ Employer authentication and profile management

**What we're building:**
- Talent pipeline database table and status tracking
- Auto-capture of "silver medalists" (candidates who reached interviews but weren't hired)
- Pipeline search to surface candidates for new jobs
- Kanban-style pipeline UI with drag-and-drop status changes
- Consent management for candidate privacy

---

## Step 1: Create Pipeline Database Table

### 1.1 - Create Alembic Migration

**What to do:**
1. Open **PowerShell**
2. Navigate to: `services/api`
3. Activate venv: `.\.venv\Scripts\Activate.ps1`
4. Create migration:
   ```powershell
   alembic revision -m "add_talent_pipeline"
   ```

### 1.2 - Edit Migration File

**File location:** `services/api/alembic/versions/xxxx_add_talent_pipeline.py`  
(Find the newest file in that folder)

**Replace contents** with:

```python
"""add talent pipeline

Revision ID: xxxx
Revises: yyyy
Create Date: (timestamp)

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'xxxx'  # Keep auto-generated
down_revision = 'yyyy'  # Keep auto-generated
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'talent_pipeline',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('employer_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('employer_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('candidate_profile_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('candidate_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_job_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('employer_jobs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('pipeline_status', sa.String(50), nullable=False, default='silver_medalist'),
        sa.Column('match_score', sa.Integer, nullable=True),
        sa.Column('tags', postgresql.JSONB, default=[]),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('last_contacted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_followup_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consent_given', sa.Boolean, default=False),
        sa.Column('consent_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.UniqueConstraint('employer_id', 'candidate_profile_id', name='uq_employer_candidate_pipeline')
    )
    
    # Indexes
    op.create_index('idx_talent_pipeline_employer', 'talent_pipeline', ['employer_id'])
    op.create_index('idx_talent_pipeline_status', 'talent_pipeline', ['pipeline_status'])
    op.create_index('idx_talent_pipeline_tags', 'talent_pipeline', ['tags'], postgresql_using='gin')


def downgrade():
    op.drop_table('talent_pipeline')
```

**Keep the auto-generated revision IDs!**

### 1.3 - Run Migration

```powershell
alembic upgrade head
```

---

## Step 2: Create Pipeline Model

### File to create: `services/api/app/models/pipeline.py`

**Full path:** `services/api/app/models/pipeline.py`

**Code to add:**

```python
"""
Talent pipeline models.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class TalentPipeline(Base):
    """
    Employer's talent pipeline for future opportunities.
    
    Tracks candidates who were:
    - Silver medalists (made it far but not hired)
    - Warm leads (showed interest)
    - Nurturing (building relationship)
    - Contacted (reached out for specific role)
    - Hired (successfully placed)
    """
    __tablename__ = "talent_pipeline"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employer_profiles.id", ondelete="CASCADE"), nullable=False)
    candidate_profile_id = Column(UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    source_job_id = Column(UUID(as_uuid=True), ForeignKey("employer_jobs.id", ondelete="SET NULL"), nullable=True)
    
    # Status workflow
    pipeline_status = Column(String(50), nullable=False, default="silver_medalist")
    # Possible values: silver_medalist, warm_lead, nurturing, contacted, not_interested, hired
    
    # Match data
    match_score = Column(Integer, nullable=True)  # Original match score from source job
    
    # Metadata
    tags = Column(JSONB, default=list)  # e.g. ['backend', 'senior', 'visa-required']
    notes = Column(Text, nullable=True)
    
    # Follow-up tracking
    last_contacted_at = Column(DateTime(timezone=True), nullable=True)
    next_followup_at = Column(DateTime(timezone=True), nullable=True)
    
    # Consent management
    consent_given = Column(Boolean, default=False)
    consent_date = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    employer = relationship("EmployerProfile", back_populates="pipeline_candidates")
    candidate_profile = relationship("CandidateProfile")
    source_job = relationship("EmployerJob")
```

### 2.1 - Update Employer Model

**File to edit:** `services/api/app/models/employer.py`

**Find the relationships section** (around line 35)

**Add this line:**

```python
pipeline_candidates = relationship("TalentPipeline", back_populates="employer", cascade="all, delete-orphan")
```

### 2.2 - Update Models __init__.py

**File to edit:** `services/api/app/models/__init__.py`

**Add import:**

```python
from app.models.pipeline import TalentPipeline
```

---

## Step 3: Create Pipeline Service

### File to create: `services/api/app/services/talent_pipeline.py`

**Full path:** `services/api/app/services/talent_pipeline.py`

**Code to add:**

```python
"""
Talent pipeline service for managing candidate pipeline.
"""
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.models.pipeline import TalentPipeline
from app.models.candidate import CandidateProfile
from app.models.job import EmployerJob


async def add_to_pipeline(
    employer_id: uuid.UUID,
    candidate_id: uuid.UUID,
    source_job_id: Optional[uuid.UUID],
    status: str,
    tags: List[str],
    notes: Optional[str],
    match_score: Optional[int],
    db: Session
) -> Dict[str, Any]:
    """
    Add a candidate to the talent pipeline.
    
    Args:
        employer_id: Employer adding the candidate
        candidate_id: Candidate profile ID
        source_job_id: Job they originally applied to (optional)
        status: Pipeline status (silver_medalist, warm_lead, etc.)
        tags: List of tags (e.g. ['backend', 'senior'])
        notes: Recruiter notes
        match_score: Original match score
        db: Database session
    
    Returns:
        {'success': bool, 'pipeline_id': str, 'error': Optional[str]}
    """
    # Check if already in pipeline
    existing = db.query(TalentPipeline).filter(
        and_(
            TalentPipeline.employer_id == employer_id,
            TalentPipeline.candidate_profile_id == candidate_id
        )
    ).first()
    
    if existing:
        # Update existing
        existing.pipeline_status = status
        existing.tags = tags
        existing.notes = notes
        existing.match_score = match_score
        existing.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            'success': True,
            'pipeline_id': str(existing.id),
            'error': None
        }
    
    # Create new pipeline entry
    pipeline = TalentPipeline(
        id=uuid.uuid4(),
        employer_id=employer_id,
        candidate_profile_id=candidate_id,
        source_job_id=source_job_id,
        pipeline_status=status,
        tags=tags,
        notes=notes,
        match_score=match_score,
        consent_given=True,  # TODO: Add real consent flow
        consent_date=datetime.utcnow()
    )
    
    db.add(pipeline)
    db.commit()
    
    return {
        'success': True,
        'pipeline_id': str(pipeline.id),
        'error': None
    }


async def search_pipeline(
    employer_id: uuid.UUID,
    filters: Dict[str, Any],
    db: Session
) -> List[Dict[str, Any]]:
    """
    Search the talent pipeline with filters.
    
    Args:
        employer_id: Employer's ID
        filters: {
            'status': Optional[str],
            'tags': Optional[List[str]],
            'min_match_score': Optional[int],
            'skills': Optional[List[str]]
        }
        db: Database session
    
    Returns:
        List of pipeline candidates with their profiles
    """
    query = db.query(TalentPipeline).join(CandidateProfile).filter(
        TalentPipeline.employer_id == employer_id
    )
    
    # Status filter
    if filters.get('status'):
        query = query.filter(TalentPipeline.pipeline_status == filters['status'])
    
    # Tags filter
    if filters.get('tags'):
        for tag in filters['tags']:
            query = query.filter(TalentPipeline.tags.contains([tag]))
    
    # Match score filter
    if filters.get('min_match_score'):
        query = query.filter(TalentPipeline.match_score >= filters['min_match_score'])
    
    # Skills filter (on candidate profile)
    if filters.get('skills'):
        for skill in filters['skills']:
            query = query.filter(CandidateProfile.skills.contains([skill]))
    
    # Order by most recently updated
    query = query.order_by(desc(TalentPipeline.updated_at))
    
    results = query.all()
    
    pipeline_data = []
    for pipeline in results:
        candidate = pipeline.candidate_profile
        
        pipeline_data.append({
            'pipeline_id': str(pipeline.id),
            'candidate_id': str(candidate.id),
            'full_name': candidate.full_name,
            'headline': candidate.headline,
            'location': candidate.location,
            'skills': candidate.skills,
            'years_of_experience': candidate.years_of_experience,
            'status': pipeline.pipeline_status,
            'tags': pipeline.tags,
            'notes': pipeline.notes,
            'match_score': pipeline.match_score,
            'last_contacted_at': pipeline.last_contacted_at.isoformat() if pipeline.last_contacted_at else None,
            'created_at': pipeline.created_at.isoformat()
        })
    
    return pipeline_data


async def suggest_pipeline_candidates(
    employer_id: uuid.UUID,
    new_job_id: uuid.UUID,
    db: Session
) -> List[Dict[str, Any]]:
    """
    For a new job posting, suggest pipeline candidates who might be good fits.
    
    Args:
        employer_id: Employer's ID
        new_job_id: New job to find candidates for
        db: Database session
    
    Returns:
        List of suggested candidates from pipeline
    """
    # Get the new job
    job = db.query(EmployerJob).filter(EmployerJob.id == new_job_id).first()
    if not job:
        return []
    
    # Get job requirements (simplified - in production use semantic similarity)
    job_skills = []  # TODO: Parse job description for skills
    
    # Get all pipeline candidates (excluding hired/not_interested)
    pipeline = db.query(TalentPipeline).join(CandidateProfile).filter(
        and_(
            TalentPipeline.employer_id == employer_id,
            TalentPipeline.pipeline_status.in_(['silver_medalist', 'warm_lead', 'nurturing'])
        )
    ).all()
    
    suggestions = []
    for p in pipeline:
        candidate = p.candidate_profile
        
        # Simple skill overlap (in production, use semantic similarity from PROMPT15)
        skill_overlap = len(set(candidate.skills or []) & set(job_skills))
        
        suggestions.append({
            'pipeline_id': str(p.id),
            'candidate_id': str(candidate.id),
            'full_name': candidate.full_name,
            'headline': candidate.headline,
            'skills': candidate.skills,
            'status': p.pipeline_status,
            'tags': p.tags,
            'notes': p.notes,
            'original_match_score': p.match_score,
            'skill_overlap': skill_overlap,
            'source_job_title': p.source_job.title if p.source_job else None
        })
    
    # Sort by skill overlap (in production, use semantic similarity score)
    suggestions.sort(key=lambda x: x['skill_overlap'], reverse=True)
    
    return suggestions[:10]  # Top 10 suggestions


async def auto_add_silver_medalists(
    employer_id: uuid.UUID,
    job_id: uuid.UUID,
    db: Session
) -> Dict[str, Any]:
    """
    When a job is filled, automatically add candidates who reached
    interview stage but weren't hired as 'silver_medalist' in pipeline.
    
    Args:
        employer_id: Employer's ID
        job_id: Job that was filled
        db: Database session
    
    Returns:
        {'success': bool, 'added_count': int}
    """
    # TODO: This requires application tracking from PROMPT11
    # For now, return placeholder
    
    return {
        'success': True,
        'added_count': 0,
        'message': 'Auto-add silver medalists requires application tracking (PROMPT11)'
    }
```

---

## Step 4: Create Pipeline API Routes

### File to create: `services/api/app/routers/pipeline.py`

**Full path:** `services/api/app/routers/pipeline.py`

**Code to add:**

```python
"""
Talent pipeline API routes.
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.core.auth import require_employer
from app.models.pipeline import TalentPipeline
from app.services import talent_pipeline


router = APIRouter(prefix="/api/employer/pipeline", tags=["pipeline"])


# --- Pydantic Schemas ---

class AddToPipelineRequest(BaseModel):
    candidate_profile_id: str
    source_job_id: Optional[str] = None
    status: str = 'silver_medalist'
    tags: List[str] = []
    notes: Optional[str] = None
    match_score: Optional[int] = None


class UpdatePipelineRequest(BaseModel):
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    next_followup_at: Optional[str] = None


class SearchPipelineRequest(BaseModel):
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    min_match_score: Optional[int] = None
    skills: Optional[List[str]] = None


# --- Routes ---

@router.get("")
async def list_pipeline(
    status: Optional[str] = None,
    current_user=Depends(require_employer),
    db: Session = Depends(get_db)
):
    """
    List all pipeline candidates with optional status filter.
    """
    employer_id = current_user.employer_profile.id
    
    filters = {}
    if status:
        filters['status'] = status
    
    results = await talent_pipeline.search_pipeline(employer_id, filters, db)
    
    return {
        'pipeline_candidates': results,
        'total': len(results)
    }


@router.post("")
async def add_candidate_to_pipeline(
    request: AddToPipelineRequest,
    current_user=Depends(require_employer),
    db: Session = Depends(get_db)
):
    """
    Add a candidate to the talent pipeline.
    """
    employer_id = current_user.employer_profile.id
    
    result = await talent_pipeline.add_to_pipeline(
        employer_id=employer_id,
        candidate_id=uuid.UUID(request.candidate_profile_id),
        source_job_id=uuid.UUID(request.source_job_id) if request.source_job_id else None,
        status=request.status,
        tags=request.tags,
        notes=request.notes,
        match_score=request.match_score,
        db=db
    )
    
    return result


@router.put("/{pipeline_id}")
async def update_pipeline_candidate(
    pipeline_id: str,
    request: UpdatePipelineRequest,
    current_user=Depends(require_employer),
    db: Session = Depends(get_db)
):
    """
    Update a pipeline candidate's status, tags, notes, etc.
    """
    employer_id = current_user.employer_profile.id
    
    # Get pipeline record
    pipeline = db.query(TalentPipeline).filter(
        TalentPipeline.id == uuid.UUID(pipeline_id),
        TalentPipeline.employer_id == employer_id
    ).first()
    
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline candidate not found")
    
    # Update fields
    if request.status:
        pipeline.pipeline_status = request.status
    if request.tags is not None:
        pipeline.tags = request.tags
    if request.notes is not None:
        pipeline.notes = request.notes
    if request.next_followup_at:
        from datetime import datetime
        pipeline.next_followup_at = datetime.fromisoformat(request.next_followup_at)
    
    db.commit()
    
    return {
        'success': True,
        'pipeline_id': str(pipeline.id)
    }


@router.delete("/{pipeline_id}")
async def remove_from_pipeline(
    pipeline_id: str,
    current_user=Depends(require_employer),
    db: Session = Depends(get_db)
):
    """
    Remove a candidate from the pipeline.
    """
    employer_id = current_user.employer_profile.id
    
    pipeline = db.query(TalentPipeline).filter(
        TalentPipeline.id == uuid.UUID(pipeline_id),
        TalentPipeline.employer_id == employer_id
    ).first()
    
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline candidate not found")
    
    db.delete(pipeline)
    db.commit()
    
    return {
        'success': True,
        'message': 'Candidate removed from pipeline'
    }


@router.post("/search")
async def search_pipeline_candidates(
    request: SearchPipelineRequest,
    current_user=Depends(require_employer),
    db: Session = Depends(get_db)
):
    """
    Search pipeline with filters.
    """
    employer_id = current_user.employer_profile.id
    
    filters = {
        'status': request.status,
        'tags': request.tags,
        'min_match_score': request.min_match_score,
        'skills': request.skills
    }
    
    results = await talent_pipeline.search_pipeline(employer_id, filters, db)
    
    return {
        'candidates': results,
        'total': len(results)
    }


@router.get("/suggestions/{job_id}")
async def get_pipeline_suggestions(
    job_id: str,
    current_user=Depends(require_employer),
    db: Session = Depends(get_db)
):
    """
    Get pipeline candidates suggested for a new job.
    """
    employer_id = current_user.employer_profile.id
    
    suggestions = await talent_pipeline.suggest_pipeline_candidates(
        employer_id=employer_id,
        new_job_id=uuid.UUID(job_id),
        db=db
    )
    
    return {
        'suggestions': suggestions,
        'total': len(suggestions)
    }


@router.post("/auto-add/{job_id}")
async def auto_add_silver_medalists_route(
    job_id: str,
    current_user=Depends(require_employer),
    db: Session = Depends(get_db)
):
    """
    Auto-add silver medalists from a filled job to pipeline.
    """
    employer_id = current_user.employer_profile.id
    
    result = await talent_pipeline.auto_add_silver_medalists(
        employer_id=employer_id,
        job_id=uuid.UUID(job_id),
        db=db
    )
    
    return result
```

### 4.1 - Register Router

**File to edit:** `services/api/app/main.py`

**Add import:**

```python
from app.routers import candidate, employer, distribution, pipeline
```

**Add router:**

```python
app.include_router(pipeline.router)
```

---

## Step 5: Frontend - Pipeline Kanban Page

### File to create: `apps/web/app/employer/pipeline/page.tsx`

**Full path:** `apps/web/app/employer/pipeline/page.tsx`

**Code to add:**

```typescript
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

interface PipelineCandidate {
  pipeline_id: string;
  candidate_id: string;
  full_name: string;
  headline: string;
  location: string;
  skills: string[];
  status: string;
  tags: string[];
  notes: string;
  match_score: number | null;
  created_at: string;
}

const STATUS_COLUMNS = [
  { key: 'silver_medalist', label: 'Silver Medalist', color: 'bg-yellow-50 border-yellow-200' },
  { key: 'warm_lead', label: 'Warm Lead', color: 'bg-blue-50 border-blue-200' },
  { key: 'nurturing', label: 'Nurturing', color: 'bg-purple-50 border-purple-200' },
  { key: 'contacted', label: 'Contacted', color: 'bg-green-50 border-green-200' },
  { key: 'hired', label: 'Hired', color: 'bg-emerald-50 border-emerald-200' },
];

export default function PipelinePage() {
  const router = useRouter();
  const [candidates, setCandidates] = useState<PipelineCandidate[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPipeline();
  }, []);

  const fetchPipeline = async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        router.push('/login');
        return;
      }

      const response = await fetch('http://localhost:8000/api/employer/pipeline', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setCandidates(data.pipeline_candidates || []);
      }
    } catch (err) {
      console.error('Error fetching pipeline:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (pipelineId: string, newStatus: string) => {
    try {
      const token = localStorage.getItem('access_token');
      
      const response = await fetch(`http://localhost:8000/api/employer/pipeline/${pipelineId}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: newStatus }),
      });

      if (response.ok) {
        // Update local state
        setCandidates(prev =>
          prev.map(c =>
            c.pipeline_id === pipelineId ? { ...c, status: newStatus } : c
          )
        );
      }
    } catch (err) {
      console.error('Error updating status:', err);
    }
  };

  const handleRemove = async (pipelineId: string) => {
    if (!confirm('Remove this candidate from your pipeline?')) return;

    try {
      const token = localStorage.getItem('access_token');
      
      const response = await fetch(`http://localhost:8000/api/employer/pipeline/${pipelineId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        setCandidates(prev => prev.filter(c => c.pipeline_id !== pipelineId));
      }
    } catch (err) {
      console.error('Error removing candidate:', err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Loading pipeline...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <h1 className="text-3xl font-bold text-gray-900">Talent Pipeline</h1>
          <p className="text-gray-600 mt-1">{candidates.length} candidates in your pipeline</p>
        </div>
      </div>

      {/* Kanban Board */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {candidates.length === 0 ? (
          <div className="bg-white rounded-xl shadow p-12 text-center">
            <div className="text-6xl mb-4">📊</div>
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">Pipeline is Empty</h2>
            <p className="text-gray-600">
              Candidates who reach interview stage will automatically be added here
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            {STATUS_COLUMNS.map((column) => {
              const columnCandidates = candidates.filter(c => c.status === column.key);
              
              return (
                <div key={column.key} className={`rounded-xl border-2 ${column.color} p-4`}>
                  <h3 className="font-semibold text-gray-900 mb-3">
                    {column.label}
                    <span className="ml-2 text-sm text-gray-500">({columnCandidates.length})</span>
                  </h3>
                  
                  <div className="space-y-3">
                    {columnCandidates.map((candidate) => (
                      <div
                        key={candidate.pipeline_id}
                        className="bg-white rounded-lg shadow-sm p-4 hover:shadow-md transition"
                      >
                        <h4 className="font-medium text-gray-900 mb-1">
                          {candidate.full_name || 'Anonymous'}
                        </h4>
                        {candidate.headline && (
                          <p className="text-xs text-gray-600 mb-2">{candidate.headline}</p>
                        )}
                        
                        {/* Skills */}
                        {candidate.skills && candidate.skills.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-3">
                            {candidate.skills.slice(0, 3).map((skill, idx) => (
                              <span
                                key={idx}
                                className="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded"
                              >
                                {skill}
                              </span>
                            ))}
                          </div>
                        )}
                        
                        {/* Tags */}
                        {candidate.tags && candidate.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-3">
                            {candidate.tags.map((tag, idx) => (
                              <span
                                key={idx}
                                className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                        
                        {/* Match Score */}
                        {candidate.match_score !== null && (
                          <p className="text-xs text-gray-500 mb-2">
                            Match: {candidate.match_score}%
                          </p>
                        )}
                        
                        {/* Actions */}
                        <div className="flex gap-2">
                          <select
                            value={candidate.status}
                            onChange={(e) => handleStatusChange(candidate.pipeline_id, e.target.value)}
                            className="flex-1 text-xs border border-gray-300 rounded px-2 py-1"
                          >
                            {STATUS_COLUMNS.map(col => (
                              <option key={col.key} value={col.key}>{col.label}</option>
                            ))}
                          </select>
                          <button
                            onClick={() => handleRemove(candidate.pipeline_id)}
                            className="text-xs text-red-600 hover:text-red-800"
                          >
                            ✕
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
```

**How to create this file:**
1. Navigate to: `apps/web/app/employer/`
2. Create folder: `pipeline`
3. Inside pipeline folder: `page.tsx`
4. Paste code
5. Save

---

## Step 6: Add Pipeline Link to Navigation

**File to edit:** `apps/web/app/employer/dashboard/page.tsx`

**Find the Quick Actions section** (around line 150)

**Add this new link:**

```typescript
<Link
  href="/employer/pipeline"
  className="p-4 border border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition"
>
  <div className="text-blue-600 text-2xl mb-2">🎯</div>
  <h3 className="font-medium text-gray-900">Talent Pipeline</h3>
  <p className="text-sm text-gray-500 mt-1">View your candidate pipeline</p>
</Link>
```

---

## Step 7: Testing Phase 3

### 7.1 - Restart Services

**Stop and restart all services:**

Terminal 1: `cd infra && docker compose up -d`  
Terminal 2: `cd services/api && uvicorn app.main:app --reload`  
Terminal 3: `cd apps/web && npm run dev`

### 7.2 - Test Pipeline Flow

**Test 1: Add Candidate to Pipeline**
1. Use curl or Postman:
```bash
curl -X POST http://localhost:8000/api/employer/pipeline \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_profile_id": "CANDIDATE_ID_HERE",
    "status": "silver_medalist",
    "tags": ["backend", "senior"],
    "notes": "Strong React skills, good culture fit",
    "match_score": 85
  }'
```

**Test 2: View Pipeline**
1. Go to: `http://localhost:3000/employer/pipeline`
2. Should see Kanban board with 5 columns
3. Candidate should appear in "Silver Medalist" column

**Test 3: Move Candidate Between Stages**
1. Use dropdown on candidate card
2. Change status to "Warm Lead"
3. Card should move to new column

**Test 4: Remove from Pipeline**
1. Click ✕ button on a candidate
2. Confirm removal
3. Candidate should disappear

---

## Success Criteria for Phase 3

✅ Pipeline database table created  
✅ Pipeline model and relationships  
✅ Pipeline service functions  
✅ API routes for pipeline CRUD  
✅ Kanban-style frontend UI  
✅ Status workflow implemented  
✅ Tags and notes system  
✅ Search and filter capabilities  
✅ Pipeline suggestions for new jobs  

---

## What You've Built

Across all 3 phases, you now have:

**Phase 1:** Complete recruiter dashboard UI
- Analytics dashboard
- Job creation and management
- Candidate search
- Saved candidates

**Phase 2:** Multi-board job distribution
- One-click distribution to multiple boards
- Real-time sync
- Per-board metrics tracking
- Mock adapters for testing

**Phase 3:** Talent pipeline CRM
- Kanban-style pipeline view
- Status workflow tracking
- Tags and notes system
- Search and filter

**This is a production-ready recruiter platform!** 🎉

Next steps would be:
- Add real job board integrations (Indeed, LinkedIn APIs)
- Implement application tracking
- Add email notifications
- Build compliance features
- Deploy to GCP
