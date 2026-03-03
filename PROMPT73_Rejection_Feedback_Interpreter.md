# PROMPT73: Rejection Feedback Interpreter

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md before making changes.

## Purpose

When employers provide rejection feedback (even generic), translate corporate-speak into actionable insights and emotional support. Turns "not the right fit" into growth opportunities.

Example: "They said 'not the right fit' which typically indicates a skills or experience gap. Based on your profile, consider highlighting your AWS experience more prominently."

---

## What Already Exists (DO NOT recreate)

1. **Application tracking:** `matches.application_status` with `rejected` state
2. **Candidate notifications:** PROMPT48 notification system
3. **Match data:** Profile, job, match reasons
4. **Anthropic SDK:** Configured

---

## What to Build

### Part 1: Feedback Interpreter Service

**File to create:** `services/api/app/services/rejection_interpreter.py`

```python
"""
Rejection Feedback Interpreter

Translates employer rejection feedback into actionable growth opportunities
while providing emotional support during a difficult moment.
"""

from anthropic import Anthropic
from sqlalchemy.orm import Session
from app.core.config import settings

client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
MODEL = "claude-3-haiku-20240307"


def interpret_rejection(
    rejection_reason: str | None,
    job_title: str,
    company: str,
    match_score: int,
    matched_skills: list[str],
    missing_skills: list[str],
) -> dict:
    """
    Interpret rejection feedback and provide supportive, actionable guidance.
    
    Returns:
        {
            "interpretation": "What this feedback typically means",
            "likely_reason": "skills_gap|experience_level|culture_fit|timing|competition",
            "emotional_support": "Encouraging message",
            "growth_opportunities": ["Specific action 1", "Specific action 2"],
            "silver_lining": "Positive takeaway from this experience",
            "next_steps": ["Continue applying to X", "Consider Y"]
        }
    """
    
    # Normalize empty/generic reasons
    reason = (rejection_reason or "").strip().lower()
    is_generic = not reason or reason in [
        "not the right fit",
        "moving forward with other candidates",
        "position has been filled",
        "decided to pursue other candidates",
        "not a match",
    ]
    
    prompt = f"""You are a compassionate career coach helping someone process a job rejection.

Rejection Context:
- Job: {job_title} at {company}
- Match Score: {match_score}%
- Employer Feedback: "{rejection_reason or 'No specific feedback provided'}"
- Candidate's Matched Skills: {', '.join(matched_skills[:5]) or 'Various'}
- Candidate's Skill Gaps: {', '.join(missing_skills[:3]) or 'None identified'}

Return JSON:
{{
    "interpretation": "1-2 sentences explaining what this feedback typically means in recruiting",
    "likely_reason": "skills_gap|experience_level|culture_fit|timing|competition|unknown",
    "emotional_support": "Warm, encouraging 1-2 sentences - acknowledge the disappointment, normalize it",
    "growth_opportunities": ["Specific actionable improvement 1", "Specific actionable improvement 2"],
    "silver_lining": "Something positive they can take from this experience",
    "next_steps": ["Concrete next action 1", "Concrete next action 2"]
}}

Rules:
1. Be warm and supportive - this is a hard moment
2. Don't be falsely positive - be honest but kind
3. If feedback is generic, acknowledge that most rejections have no real feedback
4. If their match score was high (70+), emphasize it was likely competition, not them
5. Growth opportunities should be specific to their gaps, not generic advice
6. Silver linings should be genuine, not toxic positivity
7. Next steps should be concrete and achievable this week

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
        return _generate_fallback_interpretation(
            rejection_reason, match_score, missing_skills
        )


def _generate_fallback_interpretation(
    rejection_reason: str | None,
    match_score: int,
    missing_skills: list[str],
) -> dict:
    """Fallback interpretation without LLM."""
    
    if match_score >= 70:
        likely_reason = "competition"
        interpretation = "With your strong match score, this was likely a highly competitive role with many qualified candidates."
    elif missing_skills:
        likely_reason = "skills_gap"
        interpretation = f"The role may have required stronger experience in {missing_skills[0] if missing_skills else 'certain areas'}."
    else:
        likely_reason = "unknown"
        interpretation = "Without specific feedback, it's hard to know the exact reason. This is normal — most rejections don't include detailed feedback."
    
    return {
        "interpretation": interpretation,
        "likely_reason": likely_reason,
        "emotional_support": "Rejection is a normal part of job searching and doesn't reflect your worth. Every successful job seeker has faced multiple rejections.",
        "growth_opportunities": [
            f"Consider upskilling in {missing_skills[0]}" if missing_skills else "Continue refining your profile",
            "Request informational interviews at similar companies",
        ],
        "silver_lining": "You gained interview experience and learned more about what you're looking for.",
        "next_steps": [
            "Apply to 2-3 similar roles this week",
            "Update your profile based on this experience",
        ],
    }


async def process_rejection_with_interpretation(
    match_id: int,
    rejection_reason: str | None,
    db: Session,
) -> dict:
    """
    Process a rejection and generate interpretation.
    Called when employer rejects a candidate or candidate marks as rejected.
    """
    from app.models.match import Match
    from app.models.job import Job
    
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        return {"error": "Match not found"}
    
    job = db.query(Job).filter(Job.id == match.job_id).first()
    if not job:
        return {"error": "Job not found"}
    
    reasons = match.reasons or {}
    
    interpretation = interpret_rejection(
        rejection_reason=rejection_reason,
        job_title=job.title,
        company=job.company,
        match_score=match.match_score or 0,
        matched_skills=reasons.get("matched_skills", []),
        missing_skills=reasons.get("missing_skills", []),
    )
    
    # Store interpretation in match
    if hasattr(match, 'rejection_interpretation'):
        match.rejection_interpretation = interpretation
        db.commit()
    
    return interpretation
```

### Part 2: API Endpoint

**File to modify:** `services/api/app/routers/matches.py`

```python
from app.services.rejection_interpreter import process_rejection_with_interpretation

@router.post("/api/matches/{match_id}/rejection-interpretation")
async def get_rejection_interpretation(
    match_id: int,
    rejection_reason: str | None = None,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get supportive interpretation of a job rejection.
    """
    match = db.query(Match).filter(
        Match.id == match_id,
        Match.user_id == user.id,
    ).first()
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    return await process_rejection_with_interpretation(match_id, rejection_reason, db)


@router.patch("/api/matches/{match_id}/status")
async def update_match_status(
    match_id: int,
    status: str,
    rejection_reason: str | None = None,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update application status. If rejected, include interpretation."""
    match = db.query(Match).filter(
        Match.id == match_id,
        Match.user_id == user.id,
    ).first()
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    match.application_status = status
    db.commit()
    
    response = {"status": status}
    
    # If rejected, generate interpretation
    if status == "rejected":
        interpretation = await process_rejection_with_interpretation(
            match_id, rejection_reason, db
        )
        response["interpretation"] = interpretation
    
    return response
```

### Part 3: Frontend - Rejection Support Modal

**File to create:** `apps/web/app/components/matches/RejectionSupport.tsx`

```tsx
'use client';

import { useState } from 'react';

interface Interpretation {
  interpretation: string;
  likely_reason: string;
  emotional_support: string;
  growth_opportunities: string[];
  silver_lining: string;
  next_steps: string[];
}

interface Props {
  matchId: number;
  jobTitle: string;
  company: string;
  onClose: () => void;
}

export default function RejectionSupport({ matchId, jobTitle, company, onClose }: Props) {
  const [reason, setReason] = useState('');
  const [interpretation, setInterpretation] = useState<Interpretation | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/matches/${matchId}/rejection-interpretation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ rejection_reason: reason }),
      });
      const data = await res.json();
      setInterpretation(data);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-lg w-full p-6 max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-semibold mb-2">
          Sorry to hear about {company}
        </h2>
        <p className="text-gray-600 text-sm mb-4">
          Rejection is tough. Let's process this together.
        </p>

        {!interpretation ? (
          <>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Did they give any feedback? (optional)
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder='e.g., "Moving forward with other candidates"'
              className="w-full border rounded-lg p-3 text-sm mb-4"
              rows={3}
            />
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="w-full bg-emerald-600 text-white py-2 rounded-lg hover:bg-emerald-700 disabled:opacity-50"
            >
              {loading ? 'Processing...' : 'Get Support & Insights'}
            </button>
          </>
        ) : (
          <div className="space-y-4">
            {/* Emotional Support */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <p className="text-blue-800">💙 {interpretation.emotional_support}</p>
            </div>

            {/* Interpretation */}
            <div>
              <h3 className="font-medium text-gray-900 mb-1">What This Means</h3>
              <p className="text-gray-600 text-sm">{interpretation.interpretation}</p>
            </div>

            {/* Growth Opportunities */}
            <div>
              <h3 className="font-medium text-gray-900 mb-1">Growth Opportunities</h3>
              <ul className="text-sm text-gray-600 space-y-1">
                {interpretation.growth_opportunities.map((opp, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-emerald-500">→</span>
                    {opp}
                  </li>
                ))}
              </ul>
            </div>

            {/* Silver Lining */}
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
              <p className="text-yellow-800 text-sm">
                ✨ <strong>Silver Lining:</strong> {interpretation.silver_lining}
              </p>
            </div>

            {/* Next Steps */}
            <div>
              <h3 className="font-medium text-gray-900 mb-1">Your Next Steps</h3>
              <ul className="text-sm space-y-2">
                {interpretation.next_steps.map((step, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <input type="checkbox" className="rounded" />
                    {step}
                  </li>
                ))}
              </ul>
            </div>

            <button
              onClick={onClose}
              className="w-full bg-gray-100 text-gray-700 py-2 rounded-lg hover:bg-gray-200"
            >
              Close & Move Forward
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
```

### Part 4: Trigger on Status Change

When user marks a match as "rejected", show the support modal:

```tsx
// In match card or tracking view
const [showRejectionSupport, setShowRejectionSupport] = useState(false);

const handleStatusChange = async (newStatus: string) => {
  if (newStatus === 'rejected') {
    setShowRejectionSupport(true);
  }
  // ... update status
};

{showRejectionSupport && (
  <RejectionSupport
    matchId={match.id}
    jobTitle={match.job.title}
    company={match.job.company}
    onClose={() => setShowRejectionSupport(false)}
  />
)}
```

---

## Cost Analysis

| Scenario | Cost |
|----------|------|
| Per interpretation (Haiku) | ~$0.005-0.008 |
| 50 rejections/day | ~$0.25-0.40/day |

---

## Summary Checklist

- [ ] Service: `rejection_interpreter.py` with `interpret_rejection()`
- [ ] API: `POST /api/matches/{match_id}/rejection-interpretation`
- [ ] Integration: Include interpretation when status changes to rejected
- [ ] Frontend: `RejectionSupport` modal component
- [ ] Emotional support: Warm, empathetic messaging
- [ ] Growth opportunities: Specific to candidate's gaps
- [ ] Next steps: Actionable items with checkboxes
- [ ] Fallback: Deterministic interpretation when LLM unavailable
- [ ] Tests and linting complete

Return code changes only.
