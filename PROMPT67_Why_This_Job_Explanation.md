# PROMPT67
: "Why This Job?" Quick Explanation

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPT15_Semantic_Search.md before making changes.

## Purpose

Add a human-readable, one-sentence explanation to every job match that tells the candidate exactly why Winnow surfaced this specific job for them. Instead of just showing "Match Score: 78", candidates see "Matched because of your Python + AWS experience and preference for remote work in fintech."

This builds trust in the matching algorithm, helps candidates prioritize their queue, and differentiates Winnow from competitors who hide their reasoning behind opaque scores.

---

## Triggers — When to Use This Prompt

- Adding explainable AI to job matching
- Improving match quality perception
- Building user trust in recommendations
- Product asks for "human-readable match reasons" or "why this job"

---

## What Already Exists (DO NOT recreate)

1. **Match computation:** `services/api/app/services/matching.py` — computes `match_score`, `interview_probability`, stores `reasons` JSON with `matched_skills`, `missing_skills`, `evidence_refs`
2. **Match response schema:** `services/api/app/schemas/matches.py` — `MatchResponse` with score fields
3. **Match API:** `services/api/app/routers/matches.py` — `GET /api/matches` returns list of matches
4. **Anthropic SDK:** Already installed, used in `tailor.py` and `sieve.py`
5. **Job data:** `jobs` table with title, company, location, salary, description
6. **Candidate profile:** `candidate_profiles` with skills, preferences, experience

---

## What to Build

### Part 1: Add match_explanation Field to Database

**File to modify:** Create Alembic migration

**Step 1:** Open PowerShell and navigate to the API directory:
```powershell
cd C:\Users\Ron\Winnow\services\api
```

**Step 2:** Create a new migration:
```powershell
.\.venv\Scripts\Activate.ps1
alembic revision --autogenerate -m "add_match_explanation_column"
```

**Step 3:** Open the generated migration file in `services/api/alembic/versions/` and verify it contains:
```python
def upgrade():
    op.add_column('matches', sa.Column('match_explanation', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('matches', 'match_explanation')
```

**Step 4:** Run the migration:
```powershell
alembic upgrade head
```

---

### Part 2: Update Match Model

**File to modify:** `services/api/app/models/match.py`

Add the new column to the SQLAlchemy model:

```python
# Add this column to the Match class
match_explanation = Column(Text, nullable=True)  # Human-readable explanation
```

---

### Part 3: Create Explanation Generator Service

**File to create:** `services/api/app/services/match_explainer.py`

```python
"""
Match Explanation Generator

Generates human-readable, one-sentence explanations for why a job was matched
to a candidate. Uses Claude Haiku for cost-effective natural language generation.
"""

import json
from anthropic import Anthropic
from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.job import Job
from app.models.candidate_profile import CandidateProfile
from app.core.config import settings


# Initialize Anthropic client
client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

# Use Haiku for cost-effectiveness (~$0.001-0.003 per explanation)
MODEL = "claude-3-haiku-20240307"


def generate_match_explanation(
    match: Match,
    job: Job,
    profile: CandidateProfile,
    db: Session,
) -> str:
    """
    Generate a single-sentence explanation for why this job was matched to this candidate.
    
    Args:
        match: The Match object with reasons JSON
        job: The Job object
        profile: The CandidateProfile object
        db: Database session
    
    Returns:
        A human-readable explanation string (1-2 sentences max)
    """
    # Extract relevant data
    reasons = match.reasons or {}
    matched_skills = reasons.get("matched_skills", [])
    missing_skills = reasons.get("missing_skills", [])
    
    # Get profile preferences
    profile_json = profile.profile_json or {}
    preferences = profile_json.get("preferences", {})
    target_roles = preferences.get("roles", [])
    target_locations = preferences.get("locations", [])
    work_mode = preferences.get("work_mode", "")
    salary_min = preferences.get("salary_min")
    
    # Build context for LLM
    context = {
        "job_title": job.title,
        "company": job.company,
        "location": job.location,
        "remote": job.remote_flag,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "matched_skills": matched_skills[:5],  # Top 5 for brevity
        "missing_skills": missing_skills[:3],  # Top 3 gaps
        "match_score": match.match_score,
        "candidate_target_roles": target_roles[:3],
        "candidate_work_mode": work_mode,
        "candidate_salary_min": salary_min,
    }
    
    prompt = f"""Generate a single, friendly sentence explaining why this job was matched to this candidate.

Job: {context['job_title']} at {context['company']}
Location: {context['location']} {"(Remote)" if context['remote'] else ""}
Salary: ${context['salary_min'] or '?'}k - ${context['salary_max'] or '?'}k

Candidate's matched skills: {', '.join(context['matched_skills']) or 'general experience'}
Candidate's target roles: {', '.join(context['candidate_target_roles']) or 'not specified'}
Candidate's preferred work mode: {context['candidate_work_mode'] or 'flexible'}
Match score: {context['match_score']}%

Rules:
1. Write ONE sentence only (max 25 words)
2. Start with "Matched because..." or "Great fit because..."
3. Highlight the TOP 1-2 reasons (skills, location, remote, salary, role alignment)
4. Be specific and personal (use actual skill names, not generic phrases)
5. Sound encouraging, not robotic
6. Do NOT mention the score number

Examples of good explanations:
- "Matched because of your Python and AWS experience, plus this role offers the remote flexibility you prefer."
- "Great fit because your project management background aligns with this PM role at a fintech company you'd enjoy."
- "Matched because your React expertise and San Antonio location preference align perfectly with this opportunity."

Now generate the explanation:"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        
        explanation = response.content[0].text.strip()
        
        # Clean up any quotes or extra formatting
        explanation = explanation.strip('"').strip("'")
        
        # Ensure it doesn't exceed reasonable length
        if len(explanation) > 200:
            explanation = explanation[:197] + "..."
        
        return explanation
        
    except Exception as e:
        # Fallback to deterministic explanation if LLM fails
        return _generate_fallback_explanation(context)


def _generate_fallback_explanation(context: dict) -> str:
    """
    Generate a simple fallback explanation without LLM.
    Used when API calls fail or for cost savings in batch processing.
    """
    parts = []
    
    if context["matched_skills"]:
        skills_str = ", ".join(context["matched_skills"][:2])
        parts.append(f"your {skills_str} experience")
    
    if context["remote"] and context["candidate_work_mode"] in ["remote", "hybrid"]:
        parts.append("remote work option")
    
    if context["candidate_target_roles"]:
        for role in context["candidate_target_roles"]:
            if role.lower() in context["job_title"].lower():
                parts.append(f"alignment with your {role} goals")
                break
    
    if not parts:
        parts.append("your overall profile fit")
    
    return f"Matched because of {' and '.join(parts[:2])}."


async def generate_explanations_batch(
    match_ids: list[int],
    db: Session,
) -> dict[int, str]:
    """
    Generate explanations for multiple matches efficiently.
    
    For cost optimization, this function:
    1. Uses Haiku model
    2. Batches similar matches
    3. Falls back to deterministic for very low scores
    
    Args:
        match_ids: List of match IDs to generate explanations for
        db: Database session
    
    Returns:
        Dict mapping match_id to explanation string
    """
    from app.models.match import Match
    from app.models.job import Job
    from app.models.candidate_profile import CandidateProfile
    
    results = {}
    
    # Load all matches with related data
    matches = db.query(Match).filter(Match.id.in_(match_ids)).all()
    
    for match in matches:
        job = db.query(Job).filter(Job.id == match.job_id).first()
        profile = db.query(CandidateProfile).filter(
            CandidateProfile.user_id == match.user_id
        ).order_by(CandidateProfile.version.desc()).first()
        
        if not job or not profile:
            results[match.id] = "Matched based on your profile."
            continue
        
        # For very low scores, use fallback (save API costs)
        if match.match_score < 40:
            context = {
                "job_title": job.title,
                "company": job.company,
                "location": job.location,
                "remote": job.remote_flag,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "matched_skills": (match.reasons or {}).get("matched_skills", []),
                "missing_skills": (match.reasons or {}).get("missing_skills", []),
                "match_score": match.match_score,
                "candidate_target_roles": (profile.profile_json or {}).get("preferences", {}).get("roles", []),
                "candidate_work_mode": (profile.profile_json or {}).get("preferences", {}).get("work_mode", ""),
                "candidate_salary_min": (profile.profile_json or {}).get("preferences", {}).get("salary_min"),
            }
            results[match.id] = _generate_fallback_explanation(context)
        else:
            results[match.id] = generate_match_explanation(match, job, profile, db)
        
        # Update the match record
        match.match_explanation = results[match.id]
    
    db.commit()
    
    return results
```

---

### Part 4: Update Match Schema

**File to modify:** `services/api/app/schemas/matches.py`

Add the explanation field to the response schema:

```python
# Add to MatchResponse class
match_explanation: str | None = None  # Human-readable "why this job" explanation
```

---

### Part 5: Integrate into Match Computation

**File to modify:** `services/api/app/services/matching.py`

Add explanation generation after match score computation. Find the section where matches are created/updated and add:

```python
# After computing match_score and storing reasons:
from app.services.match_explainer import generate_match_explanation

# Generate explanation (for new matches or when score changes significantly)
if match.match_score >= 40:  # Only for meaningful matches
    match.match_explanation = generate_match_explanation(match, job, profile, db)
else:
    # Use simple fallback for low-score matches to save costs
    match.match_explanation = f"Partial match based on your {', '.join(matched_skills[:2]) if matched_skills else 'experience'}."
```

---

### Part 6: Update Match API Response

**File to modify:** `services/api/app/routers/matches.py`

Ensure the `match_explanation` field is included in API responses. In the endpoint that returns matches:

```python
# In the GET /api/matches endpoint, ensure explanation is included
# It should be automatic if MatchResponse schema is updated and model has the field

# For matches without explanations (legacy data), generate on-the-fly:
for match in matches:
    if not match.match_explanation and match.match_score >= 40:
        # Lazy generation for legacy matches
        match.match_explanation = generate_match_explanation(match, job, profile, db)
        db.commit()
```

---

### Part 7: Update Frontend Match Card

**File to modify:** `apps/web/app/components/matches/MatchCard.tsx` (or similar)

Add the explanation display to match cards:

```tsx
// Add after the match score display
{match.match_explanation && (
  <p className="text-sm text-gray-600 mt-2 italic">
    {match.match_explanation}
  </p>
)}
```

**Styling suggestions:**
- Use a slightly smaller font than the main content
- Italic or a distinct color (e.g., `text-emerald-700`) to make it feel like a helpful note
- Position below the score or job title
- Add a small lightbulb or sparkle icon (✨) before the text for visual interest

---

### Part 8: Add Worker Job for Backfill

**File to modify:** `services/api/app/worker.py` (or create new task)

Add a worker job to backfill explanations for existing matches:

```python
from rq import Queue
from app.services.match_explainer import generate_explanations_batch

def backfill_match_explanations(batch_size: int = 100):
    """
    Backfill explanations for existing matches that don't have them.
    Run this as a one-time migration task.
    """
    from app.database import SessionLocal
    from app.models.match import Match
    
    db = SessionLocal()
    try:
        # Find matches without explanations, score >= 40
        matches = db.query(Match).filter(
            Match.match_explanation.is_(None),
            Match.match_score >= 40
        ).limit(batch_size).all()
        
        if not matches:
            print("No matches to backfill.")
            return
        
        match_ids = [m.id for m in matches]
        generate_explanations_batch(match_ids, db)
        
        print(f"Generated explanations for {len(match_ids)} matches.")
        
    finally:
        db.close()
```

---

## Testing

### Step 1: Test the explanation generator directly

```python
# In Python shell or test file
from app.services.match_explainer import generate_match_explanation, _generate_fallback_explanation

# Test fallback
context = {
    "job_title": "Senior Python Developer",
    "company": "TechCorp",
    "location": "Austin, TX",
    "remote": True,
    "salary_min": 120,
    "salary_max": 160,
    "matched_skills": ["Python", "AWS", "PostgreSQL"],
    "missing_skills": ["Kubernetes"],
    "match_score": 82,
    "candidate_target_roles": ["Python Developer", "Backend Engineer"],
    "candidate_work_mode": "remote",
    "candidate_salary_min": 110,
}

fallback = _generate_fallback_explanation(context)
print(f"Fallback: {fallback}")
# Expected: "Matched because of your Python, AWS experience and remote work option."
```

### Step 2: Test API endpoint

```bash
# Get matches and verify explanation is included
curl -X GET "http://localhost:8000/api/matches" \
  -H "Cookie: rm_session=YOUR_SESSION" | jq '.matches[0].match_explanation'
```

### Step 3: Test frontend display

1. Log in as a candidate with matches
2. Navigate to `/matches`
3. Verify each match card shows the explanation below the score
4. Verify the explanation is specific (mentions actual skills, not generic text)

---

## Lint and Format

```powershell
cd services/api
python -m ruff check .
python -m ruff format .

cd ../apps/web
npm run lint
```

---

## Cost Analysis

| Scenario | Cost |
|----------|------|
| Per explanation (Haiku) | ~$0.001-0.003 |
| 100 new matches/day | ~$0.10-0.30/day |
| 10,000 match backfill | ~$10-30 (one-time) |
| Monthly (1000 active users) | ~$3-10/month |

**Cost Optimization:**
- Use fallback for matches with score < 40
- Cache explanations (don't regenerate unless score changes)
- Batch process during off-peak hours

---

## Non-Goals (Do NOT implement in this prompt)

- Multi-sentence explanations (keep it to ONE sentence)
- Explanation editing by users
- A/B testing different explanation styles
- Explanation in multiple languages (future enhancement)
- Real-time explanation regeneration on every page load

---

## Summary Checklist

- [ ] Alembic migration: `match_explanation` column added to `matches` table
- [ ] SQLAlchemy model: `Match.match_explanation` field added
- [ ] Service: `match_explainer.py` with `generate_match_explanation()` and batch function
- [ ] Schema: `MatchResponse.match_explanation` field added
- [ ] Integration: Explanation generated during match computation
- [ ] API: Explanation included in `GET /api/matches` response
- [ ] Frontend: Match card displays explanation
- [ ] Worker: Backfill job for existing matches
- [ ] Fallback: Deterministic explanation when LLM unavailable
- [ ] Tests: Explanation generator tested
- [ ] Linted and formatted

Return code changes only.
