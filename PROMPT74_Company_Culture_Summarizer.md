# PROMPT74: Company Culture Summarizer

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPT10_Job_Parser.md before making changes.

## Purpose

For each company in job matches, provide a 2-3 sentence AI-generated culture summary based on job description tone, benefits mentioned, and company info. Helps candidates self-select and makes Winnow feel more comprehensive.

---

## What Already Exists (DO NOT recreate)

1. **Job parser:** `services/api/app/services/job_parser.py` extracts job data
2. **Job parsed details:** `job_parsed_details` table with structured extraction
3. **Jobs table:** `jobs` with description_text, company, benefits info
4. **Anthropic SDK:** Configured

---

## What to Build

### Part 1: Culture Analyzer Service

**File to create:** `services/api/app/services/culture_analyzer.py`

```python
"""
Company Culture Analyzer

Analyzes job postings to infer company culture characteristics.
Caches results per company to avoid redundant analysis.
"""

from anthropic import Anthropic
from sqlalchemy.orm import Session
from app.core.config import settings

client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
MODEL = "claude-3-haiku-20240307"


def analyze_company_culture(
    company: str,
    job_description: str,
    job_title: str,
) -> dict:
    """
    Analyze job posting to infer company culture.
    
    Returns:
        {
            "summary": "2-3 sentence culture summary",
            "values": ["Innovation", "Work-Life Balance"],
            "work_style": "collaborative|autonomous|hierarchical|agile",
            "pace": "fast-paced|steady|flexible",
            "remote_culture": "remote-first|hybrid-friendly|office-centric",
            "growth_focus": "high|moderate|low",
            "signals": {
                "positive": ["Unlimited PTO", "Learning budget"],
                "neutral": ["Open office"],
                "watch_for": ["Fast-paced environment mentioned 3x"]
            }
        }
    """
    
    prompt = f"""Analyze this job posting to infer company culture.

Company: {company}
Job Title: {job_title}
Description (excerpt):
{job_description[:2500]}

Return JSON:
{{
    "summary": "2-3 sentence culture summary - be specific, not generic",
    "values": ["Value 1", "Value 2", "Value 3"],
    "work_style": "collaborative|autonomous|hierarchical|agile|startup",
    "pace": "fast-paced|steady|flexible",
    "remote_culture": "remote-first|hybrid-friendly|office-centric|unclear",
    "growth_focus": "high|moderate|low",
    "signals": {{
        "positive": ["Good sign 1", "Good sign 2"],
        "neutral": ["Neutral observation"],
        "watch_for": ["Potential concern if any"]
    }}
}}

Analysis Rules:
1. Look for tone: casual vs formal language
2. Look for values: what do they emphasize (innovation, stability, growth, teamwork)?
3. Look for benefits: what perks reveal about priorities
4. Look for red flags: "fast-paced" repeated, "wear many hats", unrealistic requirements
5. Be honest but balanced - don't be cynical
6. "watch_for" should only include genuine concerns, not nitpicks
7. If insufficient data, say so honestly

Return ONLY valid JSON."""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        return json.loads(response.content[0].text)
        
    except Exception as e:
        return _generate_fallback_culture(company, job_description)


def _generate_fallback_culture(company: str, description: str) -> dict:
    """Simple deterministic culture inference."""
    
    desc_lower = description.lower()
    
    # Detect work style signals
    work_style = "collaborative"
    if "autonomous" in desc_lower or "self-starter" in desc_lower:
        work_style = "autonomous"
    elif "agile" in desc_lower or "sprint" in desc_lower:
        work_style = "agile"
    
    # Detect pace
    pace = "steady"
    if "fast-paced" in desc_lower or "rapidly" in desc_lower:
        pace = "fast-paced"
    elif "flexible" in desc_lower:
        pace = "flexible"
    
    # Detect remote culture
    remote = "unclear"
    if "remote" in desc_lower and "first" in desc_lower:
        remote = "remote-first"
    elif "hybrid" in desc_lower:
        remote = "hybrid-friendly"
    elif "on-site" in desc_lower or "in-office" in desc_lower:
        remote = "office-centric"
    
    return {
        "summary": f"{company} appears to offer a {work_style} work environment with a {pace} pace.",
        "values": [],
        "work_style": work_style,
        "pace": pace,
        "remote_culture": remote,
        "growth_focus": "moderate",
        "signals": {
            "positive": [],
            "neutral": [],
            "watch_for": [],
        },
    }


def get_or_create_culture_summary(
    job_id: int,
    db: Session,
) -> dict:
    """
    Get cached culture summary or generate new one.
    Caches by company name to avoid redundant analysis.
    """
    from app.models.job import Job
    from app.models.job_parsed_details import JobParsedDetail
    
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return {"error": "Job not found"}
    
    # Check for cached culture in job_parsed_details
    parsed = db.query(JobParsedDetail).filter(
        JobParsedDetail.job_id == job_id
    ).first()
    
    if parsed and parsed.culture_summary:
        return parsed.culture_summary
    
    # Generate new analysis
    culture = analyze_company_culture(
        company=job.company or "Unknown Company",
        job_description=job.description_text or "",
        job_title=job.title or "",
    )
    
    # Cache in job_parsed_details
    if parsed:
        parsed.culture_summary = culture
    else:
        parsed = JobParsedDetail(
            job_id=job_id,
            culture_summary=culture,
        )
        db.add(parsed)
    
    db.commit()
    
    return culture
```

### Part 2: Database Column

**Migration:** Add `culture_summary` JSON column to `job_parsed_details`:

```python
# In Alembic migration
def upgrade():
    op.add_column('job_parsed_details', 
        sa.Column('culture_summary', sa.JSON(), nullable=True))

def downgrade():
    op.drop_column('job_parsed_details', 'culture_summary')
```

### Part 3: API Endpoint

**File to modify:** `services/api/app/routers/jobs.py`

```python
from app.services.culture_analyzer import get_or_create_culture_summary

@router.get("/api/jobs/{job_id}/culture")
async def get_job_culture(
    job_id: int,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get AI-analyzed company culture summary for a job."""
    return get_or_create_culture_summary(job_id, db)
```

### Part 4: Include in Match Response

**File to modify:** `services/api/app/routers/matches.py`

Option A: Include culture in match detail endpoint:
```python
@router.get("/api/matches/{match_id}")
async def get_match_detail(...):
    # ... existing code ...
    
    # Add culture if available
    culture = get_or_create_culture_summary(match.job_id, db)
    response["culture"] = culture
    
    return response
```

Option B: Separate endpoint, frontend fetches when needed (recommended for performance).

### Part 5: Frontend - Culture Card

**File to create:** `apps/web/app/components/jobs/CultureSummary.tsx`

```tsx
'use client';

import { useState, useEffect } from 'react';

interface Culture {
  summary: string;
  values: string[];
  work_style: string;
  pace: string;
  remote_culture: string;
  growth_focus: string;
  signals: {
    positive: string[];
    neutral: string[];
    watch_for: string[];
  };
}

export default function CultureSummary({ jobId }: { jobId: number }) {
  const [culture, setCulture] = useState<Culture | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    fetch(`/api/jobs/${jobId}/culture`, { credentials: 'include' })
      .then(res => res.json())
      .then(setCulture)
      .finally(() => setLoading(false));
  }, [jobId]);

  if (loading) return <div className="h-20 bg-gray-100 animate-pulse rounded-lg" />;
  if (!culture) return null;

  const styleColors = {
    collaborative: 'bg-blue-100 text-blue-800',
    autonomous: 'bg-purple-100 text-purple-800',
    agile: 'bg-green-100 text-green-800',
    hierarchical: 'bg-gray-100 text-gray-800',
    startup: 'bg-orange-100 text-orange-800',
  };

  return (
    <div className="bg-white border rounded-lg p-4 shadow-sm">
      <div 
        className="cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-gray-900">🏢 Company Culture</h3>
          <span className="text-gray-400">{expanded ? '▲' : '▼'}</span>
        </div>
        <p className="text-sm text-gray-600 mt-1">{culture.summary}</p>
      </div>

      {expanded && (
        <div className="mt-4 pt-4 border-t space-y-3">
          {/* Tags */}
          <div className="flex flex-wrap gap-2">
            <span className={`text-xs px-2 py-1 rounded-full ${styleColors[culture.work_style] || 'bg-gray-100'}`}>
              {culture.work_style}
            </span>
            <span className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-700">
              {culture.pace}
            </span>
            <span className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-700">
              {culture.remote_culture}
            </span>
          </div>

          {/* Values */}
          {culture.values.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">Values</p>
              <div className="flex flex-wrap gap-1">
                {culture.values.map((v, i) => (
                  <span key={i} className="text-xs bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded">
                    {v}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Positive Signals */}
          {culture.signals.positive.length > 0 && (
            <div>
              <p className="text-xs font-medium text-green-600 mb-1">✓ Good Signs</p>
              <ul className="text-xs text-gray-600 space-y-0.5">
                {culture.signals.positive.map((s, i) => (
                  <li key={i}>• {s}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Watch For */}
          {culture.signals.watch_for.length > 0 && (
            <div>
              <p className="text-xs font-medium text-amber-600 mb-1">⚠ Consider</p>
              <ul className="text-xs text-gray-600 space-y-0.5">
                {culture.signals.watch_for.map((s, i) => (
                  <li key={i}>• {s}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

### Part 6: Add to Job/Match Detail

```tsx
// In match detail or job view
<CultureSummary jobId={job.id} />
```

---

## Cost Analysis

| Scenario | Cost |
|----------|------|
| Per analysis (Haiku) | ~$0.003-0.005 |
| Cached retrieval | $0.00 |
| 100 new companies/day | ~$0.30-0.50/day |

**Optimization:** Cache by company name, not job ID — many jobs share companies.

---

## Summary Checklist

- [ ] Service: `culture_analyzer.py` with `analyze_company_culture()`
- [ ] Database: `culture_summary` JSON column in `job_parsed_details`
- [ ] Caching: By company to avoid redundant analysis
- [ ] API: `GET /api/jobs/{job_id}/culture`
- [ ] Frontend: `CultureSummary` component with expandable details
- [ ] Signals: Positive, neutral, and "watch for" indicators
- [ ] Fallback: Deterministic analysis when LLM unavailable
- [ ] Integration: Add to job detail and match views
- [ ] Tests and linting complete

Return code changes only.
