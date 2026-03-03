# PROMPT70: Application Status Predictor

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md before making changes.

## Purpose

For applications submitted externally, estimate where the candidate likely stands based on job age, company hiring velocity, and match competitiveness. Reduces "black hole" anxiety — the #1 candidate complaint.

Example: "Based on this role being open 23 days, you're likely in late-stage review."

---

## What Already Exists (DO NOT recreate)

1. **Application tracking:** `matches.application_status` and `application_tracking` table
2. **Job data:** `jobs.posted_at`, company info
3. **Match data:** `match_score`, `created_at`
4. **Anthropic SDK:** Configured

---

## What to Build

### Part 1: Status Predictor Service

**File to create:** `services/api/app/services/status_predictor.py`

```python
"""
Application Status Predictor

Estimates where a candidate's application likely stands based on:
- Days since application
- Days job has been open
- Match score relative to role
- Historical patterns (when available)
"""

from datetime import datetime, timedelta
from anthropic import Anthropic
from sqlalchemy.orm import Session
from app.core.config import settings

client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
MODEL = "claude-3-haiku-20240307"


def predict_application_status(
    match_id: int,
    db: Session,
) -> dict:
    """
    Predict the likely status of an application.
    
    Returns:
        {
            "predicted_stage": "screening",  # submitted|screening|review|decision|closed
            "confidence": "medium",  # low|medium|high
            "days_since_applied": 5,
            "days_job_open": 18,
            "explanation": "Based on timing and your strong match...",
            "next_milestone": "Expect response within 1-2 weeks if moving forward",
            "tips": ["Follow up on LinkedIn if no response by day 14"]
        }
    """
    from app.models.match import Match
    from app.models.job import Job
    
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        return {"error": "Match not found"}
    
    job = db.query(Job).filter(Job.id == match.job_id).first()
    if not job:
        return {"error": "Job not found"}
    
    # Calculate timing
    now = datetime.utcnow()
    applied_at = match.updated_at  # When status changed to "applied"
    posted_at = job.posted_at or job.ingested_at
    
    days_since_applied = (now - applied_at).days if applied_at else 0
    days_job_open = (now - posted_at).days if posted_at else 0
    
    # Deterministic stage estimation
    stage_data = _estimate_stage(
        days_since_applied=days_since_applied,
        days_job_open=days_job_open,
        match_score=match.match_score or 0,
    )
    
    # Generate human-friendly explanation with LLM
    explanation = _generate_explanation(
        stage_data=stage_data,
        job_title=job.title,
        company=job.company,
        match_score=match.match_score or 0,
    )
    
    return {
        **stage_data,
        **explanation,
        "days_since_applied": days_since_applied,
        "days_job_open": days_job_open,
        "match_score": match.match_score,
    }


def _estimate_stage(
    days_since_applied: int,
    days_job_open: int,
    match_score: int,
) -> dict:
    """
    Deterministic stage estimation based on timing patterns.
    Based on industry averages from recruiting data.
    """
    
    # Stage definitions with typical timelines
    # submitted (0-3 days) → screening (3-10 days) → review (10-21 days) → decision (21+ days)
    
    if days_since_applied <= 3:
        stage = "submitted"
        confidence = "high"
        next_milestone = "Application enters screening queue within 3-5 business days"
    elif days_since_applied <= 10:
        stage = "screening"
        confidence = "medium"
        next_milestone = "Initial review typically completes within 2 weeks of application"
    elif days_since_applied <= 21:
        stage = "review"
        # Higher match scores more likely to still be in consideration
        confidence = "medium" if match_score >= 70 else "low"
        next_milestone = "Decision usually made within 3 weeks for active roles"
    else:
        # After 21 days, depends heavily on job age
        if days_job_open > 45:
            stage = "stale"
            confidence = "low"
            next_milestone = "Role may be on hold or filled — consider following up"
        else:
            stage = "decision"
            confidence = "low"
            next_milestone = "Final decisions typically within 4 weeks"
    
    # Adjust confidence based on match score
    if match_score >= 80:
        tips = ["Strong match — you're likely competitive for this role"]
    elif match_score >= 60:
        tips = ["Solid match — continue applying to similar roles while waiting"]
    else:
        tips = ["Consider strengthening your profile for better matches"]
    
    return {
        "predicted_stage": stage,
        "confidence": confidence,
        "next_milestone": next_milestone,
        "tips": tips,
    }


def _generate_explanation(
    stage_data: dict,
    job_title: str,
    company: str,
    match_score: int,
) -> dict:
    """Generate a friendly, encouraging explanation with LLM."""
    
    prompt = f"""Write a brief, encouraging status update for a job applicant.

Job: {job_title} at {company}
Match Score: {match_score}%
Predicted Stage: {stage_data['predicted_stage']}
Next Milestone: {stage_data['next_milestone']}

Return JSON:
{{"explanation": "2-3 sentence status update - honest but encouraging"}}

Rules:
1. Be realistic but not discouraging
2. If stage is "stale", gently suggest moving on while keeping hope
3. Mention their match score positively if >= 70
4. Keep it brief and actionable

Return ONLY JSON."""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        return json.loads(response.content[0].text)
    except:
        # Fallback
        stage_explanations = {
            "submitted": "Your application was recently submitted and is in the queue.",
            "screening": "Your application is likely being reviewed by the recruiting team.",
            "review": "If you're still in consideration, hiring managers are reviewing candidates.",
            "decision": "The team is likely in final decision-making stages.",
            "stale": "This role has been open a while — consider following up or exploring other options.",
        }
        return {
            "explanation": stage_explanations.get(
                stage_data['predicted_stage'],
                "Your application is being processed."
            )
        }
```

### Part 2: API Endpoint

**File to modify:** `services/api/app/routers/matches.py`

```python
from app.services.status_predictor import predict_application_status

@router.get("/api/matches/{match_id}/status-prediction")
async def get_status_prediction(
    match_id: int,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get AI-predicted status for an application.
    Only available for matches with application_status = 'applied'.
    """
    # Verify ownership
    match = db.query(Match).filter(
        Match.id == match_id,
        Match.user_id == user.id,
    ).first()
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    if match.application_status != "applied":
        raise HTTPException(
            status_code=400,
            detail="Status prediction only available for submitted applications"
        )
    
    return predict_application_status(match_id, db)
```

### Part 3: Frontend - Status Prediction Card

**File to create:** `apps/web/app/components/matches/StatusPrediction.tsx`

```tsx
'use client';

import { useState, useEffect } from 'react';

interface Prediction {
  predicted_stage: 'submitted' | 'screening' | 'review' | 'decision' | 'stale';
  confidence: 'low' | 'medium' | 'high';
  days_since_applied: number;
  days_job_open: number;
  explanation: string;
  next_milestone: string;
  tips: string[];
}

const stageConfig = {
  submitted: { label: 'Submitted', color: 'bg-blue-500', icon: '📤' },
  screening: { label: 'Screening', color: 'bg-yellow-500', icon: '👀' },
  review: { label: 'In Review', color: 'bg-purple-500', icon: '📋' },
  decision: { label: 'Decision', color: 'bg-green-500', icon: '⚖️' },
  stale: { label: 'May Be Stale', color: 'bg-gray-400', icon: '⏰' },
};

export default function StatusPrediction({ matchId }: { matchId: number }) {
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/matches/${matchId}/status-prediction`, { credentials: 'include' })
      .then(res => res.ok ? res.json() : null)
      .then(setPrediction)
      .finally(() => setLoading(false));
  }, [matchId]);

  if (loading) return <div className="h-24 bg-gray-100 animate-pulse rounded-lg" />;
  if (!prediction) return null;

  const stage = stageConfig[prediction.predicted_stage];
  
  // Progress bar position
  const stageOrder = ['submitted', 'screening', 'review', 'decision'];
  const currentIndex = stageOrder.indexOf(prediction.predicted_stage);
  const progress = prediction.predicted_stage === 'stale' 
    ? 100 
    : ((currentIndex + 1) / stageOrder.length) * 100;

  return (
    <div className="bg-white border rounded-lg p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium text-gray-900">📊 Application Status Estimate</h3>
        <span className={`text-xs px-2 py-1 rounded-full ${
          prediction.confidence === 'high' ? 'bg-green-100 text-green-800' :
          prediction.confidence === 'medium' ? 'bg-yellow-100 text-yellow-800' :
          'bg-gray-100 text-gray-600'
        }`}>
          {prediction.confidence} confidence
        </span>
      </div>

      {/* Progress bar */}
      <div className="mb-4">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          {stageOrder.map((s, i) => (
            <span key={s} className={i <= currentIndex ? 'text-emerald-600 font-medium' : ''}>
              {stageConfig[s].icon}
            </span>
          ))}
        </div>
        <div className="h-2 bg-gray-200 rounded-full">
          <div 
            className={`h-2 rounded-full ${stage.color}`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Current stage */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-2xl">{stage.icon}</span>
        <div>
          <p className="font-medium">{stage.label}</p>
          <p className="text-sm text-gray-500">
            Day {prediction.days_since_applied} of your application
          </p>
        </div>
      </div>

      {/* Explanation */}
      <p className="text-sm text-gray-600 mb-3">{prediction.explanation}</p>

      {/* Next milestone */}
      <div className="text-sm bg-blue-50 text-blue-800 p-2 rounded">
        <strong>Next:</strong> {prediction.next_milestone}
      </div>

      {/* Tips */}
      {prediction.tips.length > 0 && (
        <div className="mt-3 text-xs text-gray-500">
          💡 {prediction.tips[0]}
        </div>
      )}
    </div>
  );
}
```

### Part 4: Add to Match Detail

**File to modify:** Match detail page or application tracking view

```tsx
{match.application_status === 'applied' && (
  <StatusPrediction matchId={match.id} />
)}
```

---

## Cost Analysis

| Scenario | Cost |
|----------|------|
| Per prediction (Haiku) | ~$0.003-0.005 |
| Deterministic only | $0.00 |
| 100 predictions/day | ~$0.30-0.50/day |

---

## Summary Checklist

- [ ] Service: `status_predictor.py` with `predict_application_status()`
- [ ] Deterministic: Stage estimation based on timing patterns
- [ ] LLM: Human-friendly explanation generation
- [ ] API: `GET /api/matches/{match_id}/status-prediction`
- [ ] Frontend: `StatusPrediction` component with progress bar
- [ ] Integration: Show on applied matches
- [ ] Confidence levels: Low/medium/high based on data quality
- [ ] Tips: Actionable suggestions for each stage
- [ ] Tests and linting complete

Return code changes only.
