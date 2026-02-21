# PROMPT 43: Job Document Upload & Enhanced Fields

## Objective
Enhance employer job posting functionality by adding professional fields (Start Date, Close Date, Job ID, Job Category, Department, Certifications, Job Type), implementing Word document upload for automated job parsing, and creating automatic job archival after close dates.

---

## Context
Currently, employers manually fill out job forms. Many employers already have job descriptions in Word documents. This prompt adds:
1. **Enhanced job fields** for better categorization and tracking
2. **Document upload** capability for .docx job descriptions
3. **AI parsing** to extract job details from uploaded documents
4. **Auto-archival** for expired jobs

---

## Prerequisites
- ✅ PROMPT36 completed (employer backend)
- ✅ PROMPT38 completed (employer frontend)
- ✅ PROMPT9/10 completed (parsers exist) OR willingness to create job parser
- ✅ Backend can handle file uploads

---

## Implementation Steps

### PART 1: DATABASE SCHEMA UPDATES

**Step 1: Create Migration**

**Location:** Terminal

**Commands:**
```bash
cd services/api
alembic revision -m "add_enhanced_job_fields"
```

**Step 2: Implement Migration**

**Location:** `services/api/alembic/versions/XXXX_add_enhanced_job_fields.py`

**Code:**
```python
"""add_enhanced_job_fields

Revision ID: [GENERATED]
Revises: [PREVIOUS]
Create Date: [GENERATED]

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '[GENERATED]'
down_revision = '[PREVIOUS]'
branch_labels = None
depends_on = None


def upgrade():
    # Add new fields to employer_jobs table
    op.add_column('employer_jobs', sa.Column('job_id_external', sa.String(100), nullable=True, comment='External job ID/requisition number'))
    op.add_column('employer_jobs', sa.Column('start_date', sa.Date(), nullable=True, comment='Job start date'))
    op.add_column('employer_jobs', sa.Column('close_date', sa.Date(), nullable=True, comment='Application deadline'))
    op.add_column('employer_jobs', sa.Column('job_category', sa.String(100), nullable=True, comment='Job category (Engineering, Sales, etc.)'))
    op.add_column('employer_jobs', sa.Column('department', sa.String(100), nullable=True, comment='Department/team'))
    op.add_column('employer_jobs', sa.Column('certifications_required', JSONB, nullable=True, comment='Required certifications as JSON array'))
    op.add_column('employer_jobs', sa.Column('job_type', sa.String(50), nullable=True, comment='Type: permanent, contract, temporary, seasonal'))
    op.add_column('employer_jobs', sa.Column('archived', sa.Boolean(), server_default='false', nullable=False, comment='Job archived/expired'))
    op.add_column('employer_jobs', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True, comment='When job was archived'))
    op.add_column('employer_jobs', sa.Column('archived_reason', sa.String(50), nullable=True, comment='Why archived: expired, filled, cancelled'))
    
    # Add source document tracking
    op.add_column('employer_jobs', sa.Column('source_document_url', sa.String(500), nullable=True, comment='URL to original .docx if uploaded'))
    op.add_column('employer_jobs', sa.Column('parsed_from_document', sa.Boolean(), server_default='false', nullable=False, comment='Whether auto-parsed from upload'))
    op.add_column('employer_jobs', sa.Column('parsing_confidence', sa.Float(), nullable=True, comment='Parser confidence 0-1'))
    
    # Create index for archival queries
    op.create_index('idx_employer_jobs_archived', 'employer_jobs', ['archived'])
    op.create_index('idx_employer_jobs_close_date', 'employer_jobs', ['close_date'])
    op.create_index('idx_employer_jobs_job_category', 'employer_jobs', ['job_category'])


def downgrade():
    op.drop_index('idx_employer_jobs_job_category')
    op.drop_index('idx_employer_jobs_close_date')
    op.drop_index('idx_employer_jobs_archived')
    
    op.drop_column('employer_jobs', 'parsing_confidence')
    op.drop_column('employer_jobs', 'parsed_from_document')
    op.drop_column('employer_jobs', 'source_document_url')
    op.drop_column('employer_jobs', 'archived_reason')
    op.drop_column('employer_jobs', 'archived_at')
    op.drop_column('employer_jobs', 'archived')
    op.drop_column('employer_jobs', 'job_type')
    op.drop_column('employer_jobs', 'certifications_required')
    op.drop_column('employer_jobs', 'department')
    op.drop_column('employer_jobs', 'job_category')
    op.drop_column('employer_jobs', 'close_date')
    op.drop_column('employer_jobs', 'start_date')
    op.drop_column('employer_jobs', 'job_id_external')
```

**Step 3: Run Migration**

**Commands:**
```bash
cd services/api
alembic upgrade head
```

---

### PART 2: BACKEND - JOB PARSER SERVICE

**Step 4: Create Job Parser**

**Location:** Create `services/api/app/services/job_parser.py`

**Code:**
```python
"""
Job document parser - extracts structured data from job description .docx files.
Uses similar patterns to resume parser but for job postings.
"""
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, date
from docx import Document
import anthropic
import os

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def parse_job_document(file_path: str) -> Dict[str, Any]:
    """
    Parse a job description Word document and extract structured data.
    
    Args:
        file_path: Path to .docx file
    
    Returns:
        Dictionary with extracted job fields
    """
    # Extract text from docx
    doc = Document(file_path)
    full_text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
    
    # Use Claude to parse the job description
    parsed_data = _parse_with_claude(full_text)
    
    # Post-process and validate
    processed = _post_process_job_data(parsed_data)
    
    return processed


def _parse_with_claude(text: str) -> Dict[str, Any]:
    """
    Use Claude to extract structured job information from text.
    """
    
    prompt = f"""You are a job posting parser. Extract structured information from this job description.

Job Description:
{text}

Extract the following fields and return ONLY valid JSON:

{{
  "title": "Job title",
  "job_id_external": "Job ID or requisition number if mentioned",
  "department": "Department or team",
  "job_category": "Category like Engineering, Sales, Marketing, Operations, Finance, HR, etc.",
  "location": "Job location",
  "remote_policy": "on-site, hybrid, or remote",
  "employment_type": "full-time, part-time, contract, or internship",
  "job_type": "permanent, contract, temporary, or seasonal",
  "start_date": "YYYY-MM-DD format if mentioned, null otherwise",
  "close_date": "YYYY-MM-DD format if mentioned, null otherwise",
  "description": "Full job description",
  "requirements": "Required qualifications and experience",
  "nice_to_haves": "Preferred qualifications",
  "certifications_required": ["List of required certifications"],
  "salary_min": null or integer,
  "salary_max": null or integer,
  "salary_currency": "USD" or other currency,
  "equity_offered": true or false,
  "application_email": "email@company.com if mentioned"
}}

Rules:
1. Extract ONLY information explicitly stated in the job description
2. Do not infer or make up information
3. Use null for missing fields
4. Normalize job_category to standard categories
5. Parse dates carefully - look for "Application deadline", "Close date", "Apply by", etc.
6. Return ONLY the JSON object, no other text
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": prompt
        }]
    )
    
    # Extract JSON from response
    response_text = message.content[0].text
    
    # Remove markdown code blocks if present
    response_text = response_text.strip()
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    if response_text.startswith("```"):
        response_text = response_text[3:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]
    
    import json
    try:
        parsed = json.loads(response_text.strip())
        return parsed
    except json.JSONDecodeError as e:
        print(f"Failed to parse Claude response: {e}")
        print(f"Response was: {response_text}")
        return {}


def _post_process_job_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean and validate parsed job data.
    """
    # Normalize job category
    category_mapping = {
        "engineering": "Engineering",
        "software": "Engineering",
        "tech": "Engineering",
        "it": "Engineering",
        "sales": "Sales",
        "marketing": "Marketing",
        "design": "Design",
        "product": "Product",
        "operations": "Operations",
        "finance": "Finance",
        "hr": "Human Resources",
        "customer": "Customer Success",
        "support": "Customer Support",
    }
    
    if data.get("job_category"):
        category_lower = data["job_category"].lower()
        for key, value in category_mapping.items():
            if key in category_lower:
                data["job_category"] = value
                break
    
    # Parse dates if they're strings
    for date_field in ["start_date", "close_date"]:
        if data.get(date_field) and isinstance(data[date_field], str):
            try:
                # Try to parse YYYY-MM-DD format
                data[date_field] = datetime.strptime(data[date_field], "%Y-%m-%d").date()
            except ValueError:
                data[date_field] = None
    
    # Ensure certifications is a list
    if data.get("certifications_required") and not isinstance(data["certifications_required"], list):
        data["certifications_required"] = [data["certifications_required"]]
    
    # Calculate parsing confidence based on completeness
    required_fields = ["title", "description"]
    optional_fields = ["requirements", "location", "job_category", "department"]
    
    filled_required = sum(1 for f in required_fields if data.get(f))
    filled_optional = sum(1 for f in optional_fields if data.get(f))
    
    confidence = (filled_required / len(required_fields) * 0.7) + (filled_optional / len(optional_fields) * 0.3)
    data["parsing_confidence"] = round(confidence, 2)
    
    return data


def extract_text_from_docx(file_path: str) -> str:
    """
    Extract plain text from a .docx file.
    """
    doc = Document(file_path)
    return "\n".join([paragraph.text for paragraph in doc.paragraphs])
```

---

### PART 3: BACKEND - UPDATE SCHEMAS

**Step 5: Update Job Schemas**

**Location:** `services/api/app/schemas/employer.py`

**What to add:**

```python
from datetime import date
from typing import List, Optional

# Update EmployerJobBase
class EmployerJobBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=10)
    requirements: Optional[str] = None
    nice_to_haves: Optional[str] = None
    
    # Location & type (existing)
    location: Optional[str] = None
    remote_policy: Optional[str] = None
    employment_type: Optional[str] = None
    
    # NEW FIELDS
    job_id_external: Optional[str] = Field(None, max_length=100, description="External job ID/requisition number")
    start_date: Optional[date] = Field(None, description="Job start date")
    close_date: Optional[date] = Field(None, description="Application deadline")
    job_category: Optional[str] = Field(None, max_length=100, description="Job category")
    department: Optional[str] = Field(None, max_length=100, description="Department/team")
    certifications_required: Optional[List[str]] = Field(None, description="Required certifications")
    job_type: Optional[str] = Field(None, description="Job type: permanent, contract, temporary, seasonal")
    
    # Compensation (existing)
    salary_min: Optional[int] = Field(None, ge=0)
    salary_max: Optional[int] = Field(None, ge=0)
    salary_currency: str = "USD"
    equity_offered: bool = False
    application_email: Optional[str] = None
    
    @field_validator('job_type')
    @classmethod
    def validate_job_type(cls, v):
        if v is not None:
            allowed = ['permanent', 'contract', 'temporary', 'seasonal']
            if v not in allowed:
                raise ValueError(f"job_type must be one of: {', '.join(allowed)}")
        return v
    
    @field_validator('job_category')
    @classmethod
    def validate_job_category(cls, v):
        if v is not None:
            allowed = [
                'Engineering', 'Sales', 'Marketing', 'Design', 'Product',
                'Operations', 'Finance', 'Human Resources', 'Customer Success',
                'Customer Support', 'Data Science', 'Legal', 'Executive', 'Other'
            ]
            if v not in allowed:
                # Allow it but warn
                pass
        return v


# Update EmployerJobResponse
class EmployerJobResponse(EmployerJobBase):
    id: UUID
    employer_id: UUID
    status: str
    posted_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None
    view_count: int
    application_count: int
    
    # NEW FIELDS
    archived: bool = False
    archived_at: Optional[datetime] = None
    archived_reason: Optional[str] = None
    parsed_from_document: bool = False
    parsing_confidence: Optional[float] = None
    
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# NEW: Schema for document upload
class JobDocumentUploadResponse(BaseModel):
    job_id: UUID
    parsed_data: Dict[str, Any]
    confidence: float
    message: str
```

---

### PART 4: BACKEND - UPDATE ROUTES

**Step 6: Add Document Upload Endpoint**

**Location:** `services/api/app/routers/employer.py`

**What to add:**

```python
from fastapi import UploadFile, File
from app.services.job_parser import parse_job_document
import tempfile
import os
from pathlib import Path

# ... existing imports ...


@router.post("/jobs/upload-document", response_model=JobDocumentUploadResponse)
async def upload_job_document(
    file: UploadFile = File(...),
    employer: EmployerProfile = Depends(get_employer_profile),
    db: Session = Depends(get_db)
):
    """
    Upload a job description Word document and auto-create job posting.
    
    Accepts .docx files, parses them using AI, and creates a job draft.
    Returns the created job ID and parsed data for review.
    """
    # Validate file type
    if not file.filename.endswith('.docx'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .docx files are supported"
        )
    
    # Check file size (max 10MB)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 10MB"
        )
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp_file:
        tmp_file.write(contents)
        tmp_path = tmp_file.name
    
    try:
        # Parse the document
        parsed_data = parse_job_document(tmp_path)
        
        if not parsed_data.get('title'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract job title from document"
            )
        
        # Create job from parsed data
        job = EmployerJob(
            employer_id=employer.id,
            title=parsed_data.get('title'),
            description=parsed_data.get('description', ''),
            requirements=parsed_data.get('requirements'),
            nice_to_haves=parsed_data.get('nice_to_haves'),
            location=parsed_data.get('location'),
            remote_policy=parsed_data.get('remote_policy'),
            employment_type=parsed_data.get('employment_type'),
            job_id_external=parsed_data.get('job_id_external'),
            start_date=parsed_data.get('start_date'),
            close_date=parsed_data.get('close_date'),
            job_category=parsed_data.get('job_category'),
            department=parsed_data.get('department'),
            certifications_required=parsed_data.get('certifications_required'),
            job_type=parsed_data.get('job_type'),
            salary_min=parsed_data.get('salary_min'),
            salary_max=parsed_data.get('salary_max'),
            salary_currency=parsed_data.get('salary_currency', 'USD'),
            equity_offered=parsed_data.get('equity_offered', False),
            application_email=parsed_data.get('application_email'),
            parsed_from_document=True,
            parsing_confidence=parsed_data.get('parsing_confidence', 0.0),
            status='draft'  # Always create as draft for review
        )
        
        db.add(job)
        db.commit()
        db.refresh(job)
        
        return JobDocumentUploadResponse(
            job_id=job.id,
            parsed_data=parsed_data,
            confidence=parsed_data.get('parsing_confidence', 0.0),
            message=f"Job draft created from document. Please review and publish."
        )
        
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/jobs/{job_id}/archive")
async def archive_job(
    job_id: UUID,
    reason: Optional[str] = Query(None, description="Reason: expired, filled, cancelled"),
    employer: EmployerProfile = Depends(get_employer_profile),
    db: Session = Depends(get_db)
):
    """
    Archive a job posting.
    
    Archived jobs are hidden from candidate searches but remain in employer's history.
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
    
    if job.archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job is already archived"
        )
    
    job.archived = True
    job.archived_at = datetime.utcnow()
    job.archived_reason = reason or 'manual'
    job.status = 'closed'
    
    db.commit()
    db.refresh(job)
    
    return {
        "message": "Job archived successfully",
        "job_id": str(job.id),
        "archived_at": job.archived_at
    }


@router.post("/jobs/{job_id}/unarchive")
async def unarchive_job(
    job_id: UUID,
    employer: EmployerProfile = Depends(get_employer_profile),
    db: Session = Depends(get_db)
):
    """
    Unarchive a job posting.
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
    
    if not job.archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job is not archived"
        )
    
    job.archived = False
    job.archived_at = None
    job.archived_reason = None
    job.status = 'draft'  # Return to draft for review
    
    db.commit()
    db.refresh(job)
    
    return {
        "message": "Job unarchived successfully",
        "job_id": str(job.id)
    }
```

---

### PART 5: BACKEND - AUTO-ARCHIVAL TASK

**Step 7: Create Background Job for Auto-Archival**

**Location:** Create `services/api/app/tasks/archive_expired_jobs.py`

**Code:**
```python
"""
Background task to automatically archive jobs past their close date.
Run this daily via cron or scheduler.
"""
from datetime import date, datetime
from sqlalchemy import and_
from app.database import SessionLocal
from app.models.employer import EmployerJob


def archive_expired_jobs():
    """
    Archive all jobs where close_date has passed and job is still active.
    """
    db = SessionLocal()
    
    try:
        today = date.today()
        
        # Find jobs past close date that aren't archived
        expired_jobs = db.query(EmployerJob).filter(
            and_(
                EmployerJob.close_date < today,
                EmployerJob.archived == False,
                EmployerJob.status.in_(['active', 'paused'])
            )
        ).all()
        
        archived_count = 0
        
        for job in expired_jobs:
            job.archived = True
            job.archived_at = datetime.utcnow()
            job.archived_reason = 'expired'
            job.status = 'closed'
            archived_count += 1
        
        if archived_count > 0:
            db.commit()
            print(f"✅ Archived {archived_count} expired jobs")
        else:
            print("ℹ️  No expired jobs to archive")
        
        return archived_count
        
    except Exception as e:
        print(f"❌ Error archiving jobs: {e}")
        db.rollback()
        return 0
        
    finally:
        db.close()


if __name__ == "__main__":
    archive_expired_jobs()
```

**Step 8: Add to Scheduler**

**Location:** `services/api/app/main.py` (or wherever you run background tasks)

**What to add:**

```python
from apscheduler.schedulers.background import BackgroundScheduler
from app.tasks.archive_expired_jobs import archive_expired_jobs

# At startup
scheduler = BackgroundScheduler()
scheduler.add_job(
    archive_expired_jobs,
    'cron',
    hour=2,  # Run at 2 AM daily
    minute=0
)
scheduler.start()
```

Or run manually via cron:
```bash
# Add to crontab
0 2 * * * cd /path/to/services/api && python -m app.tasks.archive_expired_jobs
```

---

### PART 6: FRONTEND - UPDATE JOB FORM

**Step 9: Update Create Job Form**

**Location:** `web/app/employer/jobs/new/page.tsx`

**What to add:**

```typescript
const [formData, setFormData] = useState({
  // Existing fields
  title: '',
  description: '',
  requirements: '',
  nice_to_haves: '',
  location: '',
  remote_policy: '',
  employment_type: '',
  salary_min: '',
  salary_max: '',
  salary_currency: 'USD',
  equity_offered: false,
  application_email: '',
  
  // NEW FIELDS
  job_id_external: '',
  start_date: '',
  close_date: '',
  job_category: '',
  department: '',
  certifications_required: [] as string[],
  job_type: '',
});

const [certInput, setCertInput] = useState('');

// Add certification
function addCertification() {
  if (certInput.trim()) {
    setFormData({
      ...formData,
      certifications_required: [...formData.certifications_required, certInput.trim()]
    });
    setCertInput('');
  }
}

// Remove certification
function removeCertification(index: number) {
  setFormData({
    ...formData,
    certifications_required: formData.certifications_required.filter((_, i) => i !== index)
  });
}

// Add to JSX (after existing fields):

{/* Job ID */}
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">
    Job ID / Requisition Number
  </label>
  <input
    type="text"
    value={formData.job_id_external}
    onChange={(e) => setFormData({ ...formData, job_id_external: e.target.value })}
    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
    placeholder="REQ-2024-123"
  />
</div>

{/* Job Category */}
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">
    Job Category
  </label>
  <select
    value={formData.job_category}
    onChange={(e) => setFormData({ ...formData, job_category: e.target.value })}
    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
  >
    <option value="">Select category...</option>
    <option value="Engineering">Engineering</option>
    <option value="Sales">Sales</option>
    <option value="Marketing">Marketing</option>
    <option value="Design">Design</option>
    <option value="Product">Product</option>
    <option value="Operations">Operations</option>
    <option value="Finance">Finance</option>
    <option value="Human Resources">Human Resources</option>
    <option value="Customer Success">Customer Success</option>
    <option value="Customer Support">Customer Support</option>
    <option value="Data Science">Data Science</option>
    <option value="Legal">Legal</option>
    <option value="Executive">Executive</option>
    <option value="Other">Other</option>
  </select>
</div>

{/* Department */}
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">
    Department
  </label>
  <input
    type="text"
    value={formData.department}
    onChange={(e) => setFormData({ ...formData, department: e.target.value })}
    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
    placeholder="Engineering, Sales, etc."
  />
</div>

{/* Job Type */}
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">
    Job Type
  </label>
  <select
    value={formData.job_type}
    onChange={(e) => setFormData({ ...formData, job_type: e.target.value })}
    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
  >
    <option value="">Select type...</option>
    <option value="permanent">Permanent</option>
    <option value="contract">Contract</option>
    <option value="temporary">Temporary</option>
    <option value="seasonal">Seasonal</option>
  </select>
</div>

{/* Start Date */}
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">
    Start Date
  </label>
  <input
    type="date"
    value={formData.start_date}
    onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
  />
</div>

{/* Close Date */}
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">
    Application Deadline
  </label>
  <input
    type="date"
    value={formData.close_date}
    onChange={(e) => setFormData({ ...formData, close_date: e.target.value })}
    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
  />
</div>

{/* Certifications */}
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">
    Required Certifications
  </label>
  <div className="flex gap-2 mb-2">
    <input
      type="text"
      value={certInput}
      onChange={(e) => setCertInput(e.target.value)}
      onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addCertification())}
      className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
      placeholder="e.g., PMP, AWS Solutions Architect"
    />
    <button
      type="button"
      onClick={addCertification}
      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
    >
      Add
    </button>
  </div>
  {formData.certifications_required.length > 0 && (
    <div className="flex flex-wrap gap-2">
      {formData.certifications_required.map((cert, index) => (
        <span
          key={index}
          className="inline-flex items-center gap-1 px-3 py-1 bg-gray-100 rounded-full text-sm"
        >
          {cert}
          <button
            type="button"
            onClick={() => removeCertification(index)}
            className="text-gray-500 hover:text-red-600"
          >
            ×
          </button>
        </span>
      ))}
    </div>
  )}
</div>
```

---

### PART 7: FRONTEND - DOCUMENT UPLOAD COMPONENT

**Step 10: Create Upload Component**

**Location:** Create `web/components/JobDocumentUpload.tsx`

**Code:**
```typescript
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function JobDocumentUpload() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState('');

  async function handleUpload() {
    if (!file) return;

    setIsUploading(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('file', file);

      const token = localStorage.getItem('accessToken');
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/employer/jobs/upload-document`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        }
      );

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Upload failed');
      }

      const data = await res.json();
      
      // Show success and redirect to job edit page
      alert(
        `Job parsed successfully! Confidence: ${(data.confidence * 100).toFixed(0)}%\n` +
        `Please review the job details and publish.`
      );
      
      router.push(`/employer/jobs/${data.job_id}`);
      
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Upload Job Description Document
      </h3>
      
      <p className="text-sm text-gray-600 mb-4">
        Upload a .docx file containing your job description. We'll automatically
        extract the details using AI.
      </p>

      <div className="space-y-4">
        {/* File input */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Choose Document (.docx only)
          </label>
          <input
            type="file"
            accept=".docx"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="block w-full text-sm text-gray-500
              file:mr-4 file:py-2 file:px-4
              file:rounded-md file:border-0
              file:text-sm file:font-semibold
              file:bg-blue-50 file:text-blue-700
              hover:file:bg-blue-100"
          />
        </div>

        {/* Upload button */}
        <button
          onClick={handleUpload}
          disabled={!file || isUploading}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isUploading ? 'Parsing document...' : 'Upload & Parse'}
        </button>

        {/* Error message */}
        {error && (
          <div className="text-red-600 text-sm bg-red-50 border border-red-200 rounded-md p-3">
            {error}
          </div>
        )}

        {/* Info */}
        <div className="text-xs text-gray-500">
          <p className="font-medium mb-1">Supported formats:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>.docx files up to 10MB</li>
            <li>Standard job description format</li>
            <li>Extracts: title, description, requirements, dates, etc.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
```

**Step 11: Add Upload Option to Jobs Page**

**Location:** `web/app/employer/jobs/new/page.tsx`

**What to add at the top:**

```typescript
import JobDocumentUpload from '@/components/JobDocumentUpload';
import { useState } from 'react';

export default function CreateJobPage() {
  const [uploadMode, setUploadMode] = useState<'manual' | 'upload'>('manual');

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Create Job Posting</h1>
        <p className="text-gray-600 mt-1">Fill in the details or upload a document</p>
      </div>

      {/* Mode Toggle */}
      <div className="mb-6 flex gap-4">
        <button
          onClick={() => setUploadMode('manual')}
          className={`flex-1 py-3 px-4 rounded-lg font-medium transition-colors ${
            uploadMode === 'manual'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          📝 Manual Entry
        </button>
        <button
          onClick={() => setUploadMode('upload')}
          className={`flex-1 py-3 px-4 rounded-lg font-medium transition-colors ${
            uploadMode === 'upload'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          📄 Upload Document
        </button>
      </div>

      {/* Conditional rendering */}
      {uploadMode === 'upload' ? (
        <JobDocumentUpload />
      ) : (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-8 space-y-6">
          {/* Existing form fields... */}
        </form>
      )}
    </div>
  );
}
```

---

### PART 8: FRONTEND - ARCHIVED JOBS VIEW

**Step 12: Add Archived Jobs Tab**

**Location:** `web/app/employer/jobs/page.tsx`

**What to add:**

```typescript
const [viewMode, setViewMode] = useState<'active' | 'archived'>('active');
const [archivedJobs, setArchivedJobs] = useState<Job[]>([]);

// Fetch archived jobs
async function fetchArchivedJobs() {
  const token = localStorage.getItem('accessToken');
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/api/employer/jobs?archived=true`,
    {
      headers: { Authorization: `Bearer ${token}` },
    }
  );
  if (res.ok) {
    const data = await res.json();
    setArchivedJobs(data);
  }
}

// Add tabs to UI
<div className="mb-6 border-b border-gray-200">
  <nav className="-mb-px flex gap-8">
    <button
      onClick={() => setViewMode('active')}
      className={`py-4 px-1 border-b-2 font-medium text-sm ${
        viewMode === 'active'
          ? 'border-blue-600 text-blue-600'
          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
      }`}
    >
      Active Jobs ({jobs.length})
    </button>
    <button
      onClick={() => {
        setViewMode('archived');
        fetchArchivedJobs();
      }}
      className={`py-4 px-1 border-b-2 font-medium text-sm ${
        viewMode === 'archived'
          ? 'border-blue-600 text-blue-600'
          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
      }`}
    >
      Archived ({archivedJobs.length})
    </button>
  </nav>
</div>

{/* Show appropriate list */}
{viewMode === 'active' ? (
  <div className="space-y-4">
    {jobs.map((job) => (
      <JobCard key={job.id} job={job} />
    ))}
  </div>
) : (
  <div className="space-y-4">
    {archivedJobs.map((job) => (
      <ArchivedJobCard key={job.id} job={job} onUnarchive={fetchArchivedJobs} />
    ))}
  </div>
)}
```

---

## Testing Checklist

After implementation:

✅ Database migration runs successfully  
✅ Can create job with new fields (dates, category, department, etc.)  
✅ Can upload .docx file to create job  
✅ Parser extracts title, description, requirements correctly  
✅ Parser extracts dates in correct format  
✅ Parser extracts certifications as array  
✅ Job created as draft for review  
✅ Can manually archive a job  
✅ Can unarchive a job  
✅ Auto-archival task runs and archives expired jobs  
✅ Archived jobs don't appear in active list  
✅ Archived jobs visible in "Archived" tab  
✅ Job detail page shows all new fields  
✅ Certifications display as tags  

---

## Success Criteria

✅ All new fields added to database and forms  
✅ Document upload accepts .docx files  
✅ AI parser extracts job data with >70% accuracy  
✅ Jobs can be manually archived  
✅ Jobs auto-archive after close_date  
✅ Archived jobs hidden from candidate searches  
✅ Employer can view/unarchive archived jobs  
✅ Upload flow creates draft job for review  
✅ All fields validate correctly  

---

**Status:** Ready for implementation  
**Estimated Time:** 4-6 hours  
**Dependencies:** PROMPT36, 38 (employer backend/frontend)  
**Required:** Anthropic API key for job parsing  

---

## Notes

- **Parser accuracy:** Depends on document format quality
- **File storage:** Currently using temp files; consider adding permanent storage (S3) later
- **Parsing cost:** ~$0.001 per job document (very cheap)
- **Auto-archival:** Run daily at 2 AM or via cron
- **Close date:** Jobs auto-archive the day AFTER close_date
- **Certifications:** Stored as JSON array for flexibility
