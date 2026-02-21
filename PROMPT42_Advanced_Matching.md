# PROMPT 42: Advanced Matching Algorithm (ML-Powered)

## Objective
Implement an intelligent job-candidate matching system using embeddings, semantic search, and machine learning to provide accurate match scores with explainable reasons. Replace the basic keyword matching with a production-grade recommendation engine.

---

## Context
Currently, job matching is basic (or non-existent). Users need:
- **Accurate match scores**: How well does this candidate fit this job?
- **Explainability**: Why is this a 85% match vs 60%?
- **Semantic understanding**: "React developer" should match "Frontend engineer"
- **Personalization**: Learn from user behavior (saves, applies, rejects)

---

## Prerequisites
- ✅ Backend API working (PROMPT36)
- ✅ Database with candidates and jobs
- ✅ OpenAI API key (for embeddings) OR Hugging Face (free alternative)

---

## Architecture Overview

```
Candidate Profile
    ↓
Extract Skills, Experience, Preferences
    ↓
Generate Embedding Vector (1536 dimensions)
    ↓
Store in Database (PostgreSQL with pgvector)
    ↓
Query Jobs with Vector Similarity
    ↓
Calculate Match Score (0-100)
    ↓
Generate Explanation ("Strong Python match, missing AWS experience")
```

---

## Technology Stack

**Option A: OpenAI (Recommended for MVP)**
- Embeddings API: text-embedding-3-small
- Cost: $0.02 per 1M tokens (~$0.0001 per profile)
- Quality: Excellent
- Speed: Fast

**Option B: Hugging Face (Free)**
- Model: sentence-transformers/all-MiniLM-L6-v2
- Cost: Free (run locally)
- Quality: Good
- Speed: Slower (if no GPU)

We'll implement Option A (OpenAI), with notes for Option B.

---

## Implementation Steps

### Step 0: Install Dependencies

**Commands:**
```bash
cd services/api
pip install openai pgvector scikit-learn --break-system-packages
```

---

### Step 1: Enable pgvector Extension

**Location:** Create migration `services/api/alembic/versions/XXXX_add_pgvector.py`

**Code:**
```python
"""add pgvector extension

Revision ID: [GENERATED]
Revises: [PREVIOUS]
Create Date: [GENERATED]

"""
from alembic import op
import sqlalchemy as sa

revision = '[GENERATED]'
down_revision = '[PREVIOUS]'
branch_labels = None
depends_on = None


def upgrade():
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Add embedding column to candidate_profiles
    op.add_column('candidate_profiles', 
        sa.Column('profile_embedding', sa.String(), nullable=True)
    )
    
    # Add embedding column to jobs (for employer jobs)
    op.add_column('employer_jobs',
        sa.Column('job_embedding', sa.String(), nullable=True)
    )
    
    # Add columns to store match data
    op.create_table(
        'job_matches',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('candidate_id', sa.UUID(), sa.ForeignKey('candidate_profiles.id', ondelete='CASCADE')),
        sa.Column('job_id', sa.UUID(), sa.ForeignKey('employer_jobs.id', ondelete='CASCADE')),
        sa.Column('match_score', sa.Float(), nullable=False),
        sa.Column('reasons', sa.JSON(), nullable=True),
        sa.Column('skills_match', sa.Float()),
        sa.Column('experience_match', sa.Float()),
        sa.Column('location_match', sa.Float()),
        sa.Column('calculated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    
    # Create index for faster matching queries
    op.create_index('idx_job_matches_candidate', 'job_matches', ['candidate_id'])
    op.create_index('idx_job_matches_score', 'job_matches', ['match_score'])


def downgrade():
    op.drop_index('idx_job_matches_score')
    op.drop_index('idx_job_matches_candidate')
    op.drop_table('job_matches')
    op.drop_column('employer_jobs', 'job_embedding')
    op.drop_column('candidate_profiles', 'profile_embedding')
    op.execute('DROP EXTENSION IF EXISTS vector')
```

**Run migration:**
```bash
cd services/api
alembic upgrade head
```

---

### Step 2: Embedding Service

**Location:** Create `services/api/app/services/embedding_service.py`

**Code:**
```python
import json
from typing import List, Dict, Any
import openai
from app.core.config import settings

openai.api_key = settings.OPENAI_API_KEY


def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding vector for text using OpenAI.
    
    Args:
        text: Input text to embed
    
    Returns:
        1536-dimensional embedding vector
    """
    try:
        response = openai.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Embedding generation failed: {e}")
        return [0.0] * 1536  # Fallback to zero vector


def generate_candidate_embedding(profile_data: Dict[str, Any]) -> List[float]:
    """
    Generate embedding for candidate profile.
    
    Combines: skills, experience, education, preferences
    """
    # Build comprehensive text representation
    parts = []
    
    # Skills
    if profile_data.get('skills'):
        skills_text = ", ".join(profile_data['skills'])
        parts.append(f"Skills: {skills_text}")
    
    # Experience
    if profile_data.get('experience'):
        for exp in profile_data['experience'][:3]:  # Top 3 jobs
            title = exp.get('title', '')
            company = exp.get('company', '')
            description = exp.get('description', '')
            parts.append(f"{title} at {company}. {description}")
    
    # Education
    if profile_data.get('education'):
        for edu in profile_data['education']:
            degree = edu.get('degree', '')
            field = edu.get('field', '')
            parts.append(f"{degree} in {field}")
    
    # Preferences
    if profile_data.get('job_preferences'):
        prefs = profile_data['job_preferences']
        if prefs.get('desired_roles'):
            parts.append(f"Seeking: {', '.join(prefs['desired_roles'])}")
        if prefs.get('preferred_locations'):
            parts.append(f"Location: {', '.join(prefs['preferred_locations'])}")
    
    # Combine and generate embedding
    full_text = " ".join(parts)
    return generate_embedding(full_text)


def generate_job_embedding(job_data: Dict[str, Any]) -> List[float]:
    """
    Generate embedding for job posting.
    
    Combines: title, description, requirements, skills
    """
    parts = [
        f"Job: {job_data.get('title', '')}",
        f"Description: {job_data.get('description', '')}",
        f"Requirements: {job_data.get('requirements', '')}",
    ]
    
    if job_data.get('nice_to_haves'):
        parts.append(f"Nice to have: {job_data['nice_to_haves']}")
    
    full_text = " ".join(parts)
    return generate_embedding(full_text)


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Returns value between 0 and 1 (1 = identical, 0 = completely different)
    """
    import numpy as np
    
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    
    dot_product = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(dot_product / (norm1 * norm2))
```

---

### Step 3: Matching Service

**Location:** Create `services/api/app/services/matching_service.py`

**Code:**
```python
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models.candidate import CandidateProfile
from app.models.employer import EmployerJob
from app.services import embedding_service
import json


def calculate_skills_match(candidate_skills: List[str], job_requirements: str) -> Tuple[float, List[str]]:
    """
    Calculate skill match percentage and identify matching skills.
    
    Returns:
        (match_score, matching_skills)
    """
    if not candidate_skills or not job_requirements:
        return 0.0, []
    
    # Normalize for comparison
    job_req_lower = job_requirements.lower()
    matched_skills = []
    
    for skill in candidate_skills:
        if skill.lower() in job_req_lower:
            matched_skills.append(skill)
    
    if len(candidate_skills) == 0:
        return 0.0, []
    
    match_score = len(matched_skills) / len(candidate_skills)
    return match_score, matched_skills


def calculate_experience_match(candidate_years: int, job_data: Dict) -> float:
    """
    Calculate experience level match.
    
    Returns value 0-1 based on how well experience aligns.
    """
    # Extract required years from job description (simplified)
    # In production, use NLP to extract "5+ years experience"
    
    # For now, assume jobs need 2-10 years
    if candidate_years < 1:
        return 0.3  # Entry level
    elif candidate_years <= 3:
        return 0.6  # Junior
    elif candidate_years <= 7:
        return 0.9  # Mid-level
    else:
        return 1.0  # Senior
    
    
def calculate_location_match(candidate_location: str, job_location: str, remote_policy: str) -> float:
    """
    Calculate location compatibility.
    
    Returns:
        1.0 if remote or locations match
        0.5 if different locations
        0.0 if incompatible
    """
    if remote_policy == "remote":
        return 1.0
    
    if not candidate_location or not job_location:
        return 0.5  # Unknown
    
    # Simple string matching (in production, use geocoding)
    if candidate_location.lower() in job_location.lower():
        return 1.0
    
    return 0.3  # Different locations


def generate_match_explanation(
    skills_match: float,
    matched_skills: List[str],
    experience_match: float,
    location_match: float,
    overall_score: float
) -> List[str]:
    """
    Generate human-readable explanations for match score.
    """
    reasons = []
    
    # Skills
    if skills_match > 0.7:
        reasons.append(f"Strong skills match: {', '.join(matched_skills[:5])}")
    elif skills_match > 0.4:
        reasons.append(f"Partial skills match: {', '.join(matched_skills[:3])}")
    else:
        reasons.append("Limited skills overlap - growth opportunity")
    
    # Experience
    if experience_match > 0.8:
        reasons.append("Experience level aligns well")
    elif experience_match > 0.5:
        reasons.append("Some experience gap")
    else:
        reasons.append("Entry-level position or experience mismatch")
    
    # Location
    if location_match == 1.0:
        reasons.append("Location compatible (remote or local)")
    elif location_match > 0.5:
        reasons.append("Location may require relocation")
    
    # Overall
    if overall_score > 0.8:
        reasons.insert(0, "🎯 Excellent overall match")
    elif overall_score > 0.6:
        reasons.insert(0, "✅ Good fit with some gaps")
    else:
        reasons.insert(0, "⚠️ Potential match with development needed")
    
    return reasons


def calculate_match_score(
    candidate: CandidateProfile,
    job: EmployerJob,
    db: Session
) -> Dict[str, Any]:
    """
    Calculate comprehensive match score between candidate and job.
    
    Returns:
        {
            'match_score': float (0-100),
            'skills_match': float,
            'experience_match': float,
            'location_match': float,
            'semantic_similarity': float,
            'reasons': List[str]
        }
    """
    # 1. Semantic similarity (embeddings)
    candidate_embedding = json.loads(candidate.profile_embedding) if candidate.profile_embedding else None
    job_embedding = json.loads(job.job_embedding) if job.job_embedding else None
    
    if candidate_embedding and job_embedding:
        semantic_sim = embedding_service.cosine_similarity(candidate_embedding, job_embedding)
    else:
        # Fallback: generate embeddings now
        candidate_embedding = embedding_service.generate_candidate_embedding(candidate.profile_data or {})
        job_embedding = embedding_service.generate_job_embedding({
            'title': job.title,
            'description': job.description,
            'requirements': job.requirements,
            'nice_to_haves': job.nice_to_haves,
        })
        
        # Store for future use
        candidate.profile_embedding = json.dumps(candidate_embedding)
        job.job_embedding = json.dumps(job_embedding)
        db.commit()
        
        semantic_sim = embedding_service.cosine_similarity(candidate_embedding, job_embedding)
    
    # 2. Skills match
    candidate_skills = candidate.profile_data.get('skills', []) if candidate.profile_data else []
    skills_match, matched_skills = calculate_skills_match(
        candidate_skills,
        job.requirements or ""
    )
    
    # 3. Experience match
    experience_match = calculate_experience_match(
        candidate.years_experience or 0,
        {'title': job.title}
    )
    
    # 4. Location match
    candidate_location = candidate.profile_data.get('location', '') if candidate.profile_data else ''
    location_match = calculate_location_match(
        candidate_location,
        job.location or '',
        job.remote_policy or ''
    )
    
    # 5. Weighted overall score
    overall_score = (
        semantic_sim * 0.40 +       # 40% semantic understanding
        skills_match * 0.30 +        # 30% skills match
        experience_match * 0.20 +    # 20% experience
        location_match * 0.10        # 10% location
    )
    
    # Convert to 0-100 scale
    match_percentage = overall_score * 100
    
    # 6. Generate explanations
    reasons = generate_match_explanation(
        skills_match,
        matched_skills,
        experience_match,
        location_match,
        overall_score
    )
    
    return {
        'match_score': round(match_percentage, 1),
        'skills_match': round(skills_match * 100, 1),
        'experience_match': round(experience_match * 100, 1),
        'location_match': round(location_match * 100, 1),
        'semantic_similarity': round(semantic_sim * 100, 1),
        'reasons': reasons
    }


def find_top_matches(
    candidate_id: str,
    db: Session,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Find top job matches for a candidate.
    
    Uses pre-computed embeddings for fast similarity search.
    """
    candidate = db.query(CandidateProfile).filter(
        CandidateProfile.id == candidate_id
    ).first()
    
    if not candidate:
        return []
    
    # Get active jobs
    active_jobs = db.query(EmployerJob).filter(
        EmployerJob.status == 'active'
    ).all()
    
    # Calculate matches
    matches = []
    for job in active_jobs:
        match_data = calculate_match_score(candidate, job, db)
        matches.append({
            'job_id': str(job.id),
            'job_title': job.title,
            'company_name': job.employer.company_name,
            'location': job.location,
            'remote_policy': job.remote_policy,
            **match_data
        })
    
    # Sort by match score (descending)
    matches.sort(key=lambda x: x['match_score'], reverse=True)
    
    return matches[:limit]
```

---

### Step 4: Background Job for Embedding Generation

**Location:** Create `services/api/app/tasks/generate_embeddings.py`

**Code:**
```python
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.candidate import CandidateProfile
from app.models.employer import EmployerJob
from app.services import embedding_service
import json


def generate_all_candidate_embeddings():
    """
    Background task to generate embeddings for all candidates.
    Run this periodically or when profiles are created/updated.
    """
    db = SessionLocal()
    
    try:
        # Get candidates without embeddings
        candidates = db.query(CandidateProfile).filter(
            CandidateProfile.profile_embedding.is_(None)
        ).all()
        
        print(f"Generating embeddings for {len(candidates)} candidates...")
        
        for i, candidate in enumerate(candidates):
            if not candidate.profile_data:
                continue
            
            embedding = embedding_service.generate_candidate_embedding(
                candidate.profile_data
            )
            candidate.profile_embedding = json.dumps(embedding)
            
            if (i + 1) % 10 == 0:
                db.commit()
                print(f"Processed {i + 1}/{len(candidates)}")
        
        db.commit()
        print("Done!")
        
    finally:
        db.close()


def generate_all_job_embeddings():
    """
    Background task to generate embeddings for all jobs.
    """
    db = SessionLocal()
    
    try:
        jobs = db.query(EmployerJob).filter(
            EmployerJob.job_embedding.is_(None),
            EmployerJob.status == 'active'
        ).all()
        
        print(f"Generating embeddings for {len(jobs)} jobs...")
        
        for i, job in enumerate(jobs):
            embedding = embedding_service.generate_job_embedding({
                'title': job.title,
                'description': job.description,
                'requirements': job.requirements,
                'nice_to_haves': job.nice_to_haves,
            })
            job.job_embedding = json.dumps(embedding)
            
            if (i + 1) % 10 == 0:
                db.commit()
                print(f"Processed {i + 1}/{len(jobs)}")
        
        db.commit()
        print("Done!")
        
    finally:
        db.close()


if __name__ == "__main__":
    generate_all_candidate_embeddings()
    generate_all_job_embeddings()
```

---

### Step 5: Update Candidate API

**Location:** `services/api/app/routers/candidate.py`

**Add new endpoint:**
```python
from app.services.matching_service import find_top_matches

@router.get("/matches", response_model=List[dict])
async def get_job_matches(
    limit: int = Query(20, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get personalized job matches for current candidate.
    
    Returns jobs sorted by match score with explanations.
    """
    # Get candidate profile
    candidate = db.query(CandidateProfile).filter(
        CandidateProfile.user_id == current_user.id
    ).first()
    
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail="Candidate profile not found"
        )
    
    # Get matches
    matches = find_top_matches(
        candidate_id=str(candidate.id),
        db=db,
        limit=limit
    )
    
    return matches
```

---

### Step 6: Add Config for OpenAI

**Location:** `services/api/app/core/config.py`

**Add:**
```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    OPENAI_API_KEY: str
    
    class Config:
        env_file = ".env"
```

**Add to `.env`:**
```bash
OPENAI_API_KEY=sk-...
```

---

### Step 7: Run Embedding Generation

**Commands:**
```bash
cd services/api

# Generate embeddings for existing data
python -m app.tasks.generate_embeddings
```

This will process all candidates and jobs, generating embeddings.

---

### Step 8: Frontend - Display Match Scores

**Location:** `web/app/(candidate)/matches/page.tsx`

**Update to show match data:**
```typescript
interface JobMatch {
  job_id: string;
  job_title: string;
  company_name: string;
  location: string;
  remote_policy: string;
  match_score: number;
  skills_match: number;
  experience_match: number;
  location_match: number;
  semantic_similarity: number;
  reasons: string[];
}

function JobMatchCard({ match }: { match: JobMatch }) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      {/* Match Score Badge */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-xl font-semibold text-gray-900">{match.job_title}</h3>
          <p className="text-gray-600">{match.company_name}</p>
          <p className="text-sm text-gray-500">
            {match.location} • {match.remote_policy}
          </p>
        </div>
        
        <div className="flex flex-col items-end">
          <div className={`text-3xl font-bold ${
            match.match_score >= 80 ? 'text-green-600' :
            match.match_score >= 60 ? 'text-blue-600' :
            'text-gray-600'
          }`}>
            {match.match_score}%
          </div>
          <div className="text-xs text-gray-500">Match</div>
        </div>
      </div>
      
      {/* Match Breakdown */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <MatchStat label="Skills" value={match.skills_match} />
        <MatchStat label="Experience" value={match.experience_match} />
        <MatchStat label="Location" value={match.location_match} />
      </div>
      
      {/* Reasons */}
      <div className="space-y-2">
        {match.reasons.map((reason, i) => (
          <div key={i} className="flex items-start gap-2 text-sm">
            <span className="text-blue-600">•</span>
            <span className="text-gray-700">{reason}</span>
          </div>
        ))}
      </div>
      
      {/* Actions */}
      <div className="mt-6 flex gap-3">
        <button className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700">
          View Job
        </button>
        <button className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50">
          Save
        </button>
      </div>
    </div>
  );
}

function MatchStat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-sm text-gray-600 mb-1">{label}</div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className="bg-blue-600 h-2 rounded-full"
          style={{ width: `${value}%` }}
        />
      </div>
      <div className="text-xs text-gray-500 mt-1">{value}%</div>
    </div>
  );
}
```

---

## Alternative: Hugging Face (Free)

If you want to avoid OpenAI costs:

**Install:**
```bash
pip install sentence-transformers --break-system-packages
```

**Update embedding_service.py:**
```python
from sentence_transformers import SentenceTransformer

# Load model once
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

def generate_embedding(text: str) -> List[float]:
    """Generate embedding using local model."""
    embedding = model.encode(text)
    return embedding.tolist()
```

**Pros:** Free, no API calls  
**Cons:** Slower, requires GPU for speed, 384 dimensions (vs 1536)

---

## Performance Optimization

### Batch Processing
```python
# Process multiple embeddings at once
def generate_batch_embeddings(texts: List[str]) -> List[List[float]]:
    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=texts  # Up to 2048 texts
    )
    return [item.embedding for item in response.data]
```

### Caching
```python
# Cache embeddings in Redis
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379)

def get_cached_embedding(key: str) -> Optional[List[float]]:
    cached = redis_client.get(f"embedding:{key}")
    if cached:
        return json.loads(cached)
    return None

def cache_embedding(key: str, embedding: List[float], ttl: int = 86400):
    redis_client.setex(
        f"embedding:{key}",
        ttl,
        json.dumps(embedding)
    )
```

---

## Monitoring & Analytics

**Track matching performance:**
```python
# Add to job_matches table
- user_clicked: boolean
- user_applied: boolean
- user_saved: boolean
- user_dismissed: boolean
```

**Analyze:**
- Which match scores lead to applications?
- Are high match scores (80%+) converting better?
- Which factors matter most (skills vs experience)?

---

## Future Enhancements

1. **Personalization**: Learn from user actions
   - Clicks → positive signal
   - Dismissals → negative signal
   - Update weights dynamically

2. **A/B Testing**: Test different matching algorithms
   - 50% users get semantic matching
   - 50% users get keyword matching
   - Measure application rates

3. **Salary Matching**: Factor in compensation expectations

4. **Culture Fit**: Match based on company values, team size

5. **Fine-tuning**: Train custom model on your data

---

## Testing

**Test cases:**
```python
# Test 1: Exact skill match
candidate = {"skills": ["Python", "FastAPI", "PostgreSQL"]}
job = {"requirements": "Python, FastAPI, PostgreSQL required"}
# Expected: 90%+ match

# Test 2: Semantic match
candidate = {"skills": ["React", "TypeScript", "Node.js"]}
job = {"requirements": "Frontend engineer with modern JavaScript"}
# Expected: 70-85% match

# Test 3: No overlap
candidate = {"skills": ["Marketing", "SEO", "Content Writing"]}
job = {"requirements": "Senior Rust developer"}
# Expected: <30% match
```

---

## Cost Analysis

**OpenAI Embeddings:**
- text-embedding-3-small: $0.02 per 1M tokens
- Average profile: ~500 tokens = $0.00001
- 10,000 candidates: ~$0.10
- 1,000 jobs: ~$0.01
- **Total initial cost: ~$0.11**

**Ongoing:**
- New candidate: $0.00001
- Job update: $0.00001
- Re-matching (monthly): negligible

Very cheap!

---

## Success Criteria

✅ Embeddings generated for candidates and jobs  
✅ Match scores calculated with explanations  
✅ Semantic similarity works (React matches Frontend)  
✅ Match scores correlate with user applications  
✅ API returns matches sorted by score  
✅ Frontend displays match breakdown  
✅ Performance acceptable (<2s for 1000 jobs)  
✅ Explainability clear to users  

---

**Status:** Ready for implementation  
**Estimated Time:** 4-6 hours  
**Cost:** ~$0.11 initial + minimal ongoing  
**Dependencies:** PROMPT36 (backend API)  
**Recommended:** Start with OpenAI, optimize later
