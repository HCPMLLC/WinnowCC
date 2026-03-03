# PROMPT76: Salary Negotiation Coach

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md before making changes.

## Purpose

When a candidate receives an offer, analyze it against market data, their experience, and job requirements to provide negotiation talking points and counter-offer suggestions. High-stakes moment where candidates desperately want help — natural Pro tier upsell.

---

## What Already Exists (DO NOT recreate)

1. **Match tracking:** `matches.application_status` with `offer` state
2. **Job salary data:** `jobs.salary_min`, `jobs.salary_max`
3. **Candidate profile:** Experience, skills, location
4. **Billing tiers:** Pro tier feature gating in `billing.py`
5. **Anthropic SDK:** Configured

---

## What to Build

### Part 1: Salary Coach Service

**File to create:** `services/api/app/services/salary_coach.py`

```python
"""
Salary Negotiation Coach

Analyzes job offers and provides personalized negotiation strategies.
Premium feature for Pro tier candidates.
"""

from anthropic import Anthropic
from sqlalchemy.orm import Session
from app.core.config import settings

client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
MODEL = "claude-sonnet-4-20250514"  # Sonnet for nuanced advice


def analyze_offer(
    offer_salary: int,
    offer_bonus: int | None,
    offer_equity: str | None,
    job_title: str,
    company: str,
    job_salary_min: int | None,
    job_salary_max: int | None,
    candidate_experience_years: int,
    candidate_current_salary: int | None,
    candidate_location: str,
    candidate_skills: list[str],
    matched_skills: list[str],
) -> dict:
    """
    Analyze a job offer and provide negotiation guidance.
    
    Returns:
        {
            "offer_assessment": {
                "overall": "below_market|at_market|above_market",
                "salary_position": "This offer is in the 40th percentile for...",
                "total_comp_analysis": "Including bonus, total comp is..."
            },
            "negotiation_strategy": {
                "approach": "standard_counter|strong_counter|accept_with_perks|accept",
                "reasoning": "Why this approach...",
                "risk_level": "low|medium|high"
            },
            "counter_offer": {
                "target_salary": 145000,
                "minimum_acceptable": 135000,
                "script": "Thank you for the offer. I'm excited about...",
                "justification_points": [
                    "My 8 years of experience in...",
                    "The market rate for this role is..."
                ]
            },
            "alternative_asks": [
                {
                    "item": "Signing bonus",
                    "suggested_amount": "$10,000",
                    "script": "If base salary flexibility is limited..."
                },
                {
                    "item": "Extra PTO",
                    "suggested_amount": "5 additional days",
                    "script": "I value work-life balance..."
                }
            ],
            "red_flags": ["Low equity for startup stage"],
            "positive_signals": ["Strong base for the role level"],
            "timeline_advice": "Ask for 3-5 business days to consider..."
        }
    """
    
    prompt = f"""You are an expert salary negotiation coach. Analyze this job offer and provide actionable negotiation guidance.

## Offer Details
- Job: {job_title} at {company}
- Offered Base Salary: ${offer_salary:,}
- Bonus: {f'${offer_bonus:,}' if offer_bonus else 'Not specified'}
- Equity: {offer_equity or 'Not specified'}
- Posted Salary Range: ${job_salary_min or '?'}k - ${job_salary_max or '?'}k

## Candidate Profile
- Years of Experience: {candidate_experience_years}
- Current/Last Salary: {f'${candidate_current_salary:,}' if candidate_current_salary else 'Not disclosed'}
- Location: {candidate_location}
- Key Skills: {', '.join(candidate_skills[:8])}
- Skills Matching This Role: {', '.join(matched_skills[:5])}

## Your Analysis

Return JSON:
{{
    "offer_assessment": {{
        "overall": "below_market|at_market|above_market",
        "salary_position": "Analysis of where this offer falls",
        "total_comp_analysis": "Full compensation picture"
    }},
    "negotiation_strategy": {{
        "approach": "standard_counter|strong_counter|accept_with_perks|accept",
        "reasoning": "Why this strategy",
        "risk_level": "low|medium|high"
    }},
    "counter_offer": {{
        "target_salary": number,
        "minimum_acceptable": number,
        "script": "Exact words to say/write",
        "justification_points": ["Point 1", "Point 2", "Point 3"]
    }},
    "alternative_asks": [
        {{
            "item": "What to ask for",
            "suggested_amount": "Specific amount",
            "script": "How to ask"
        }}
    ],
    "red_flags": ["Concern 1 if any"],
    "positive_signals": ["Good sign 1"],
    "timeline_advice": "How to handle timing"
}}

Rules:
1. Be realistic - don't suggest unreasonable counters
2. Consider the candidate's leverage (skills match, experience, market)
3. Counter target should be 10-20% above offer unless offer is already high
4. Always include alternative asks (bonus, PTO, remote, start date)
5. Scripts should be professional and confident, not aggressive
6. Include specific numbers, not ranges
7. If offer is already strong, say so - don't encourage unnecessary negotiation
8. Consider location-based salary adjustments

Return ONLY valid JSON."""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        return json.loads(response.content[0].text)
        
    except Exception as e:
        return _generate_fallback_analysis(
            offer_salary, job_salary_min, job_salary_max, candidate_experience_years
        )


def _generate_fallback_analysis(
    offer: int,
    job_min: int | None,
    job_max: int | None,
    experience: int,
) -> dict:
    """Fallback analysis without LLM."""
    
    # Simple assessment
    if job_max and offer >= job_max * 0.9:
        overall = "at_market"
        approach = "accept_with_perks"
    elif job_min and offer <= job_min * 1.1:
        overall = "below_market"
        approach = "strong_counter"
    else:
        overall = "at_market"
        approach = "standard_counter"
    
    target = int(offer * 1.15)
    minimum = int(offer * 1.07)
    
    return {
        "offer_assessment": {
            "overall": overall,
            "salary_position": "Based on the posted range, this offer appears reasonable.",
            "total_comp_analysis": "Consider the full package including benefits.",
        },
        "negotiation_strategy": {
            "approach": approach,
            "reasoning": "Standard negotiation is expected and won't jeopardize the offer.",
            "risk_level": "low",
        },
        "counter_offer": {
            "target_salary": target,
            "minimum_acceptable": minimum,
            "script": f"Thank you for the offer. I'm excited about the opportunity. Based on my experience and the market, I was hoping for a base salary closer to ${target:,}. Is there flexibility in the compensation?",
            "justification_points": [
                f"My {experience} years of experience",
                "Strong skills match for the role requirements",
                "Market rates for similar positions",
            ],
        },
        "alternative_asks": [
            {
                "item": "Signing bonus",
                "suggested_amount": "$5,000-10,000",
                "script": "If base salary flexibility is limited, would a signing bonus be possible?",
            },
            {
                "item": "Additional PTO",
                "suggested_amount": "5 extra days",
                "script": "I value work-life balance. Could we discuss additional PTO?",
            },
        ],
        "red_flags": [],
        "positive_signals": ["You received an offer - they want you!"],
        "timeline_advice": "Ask for 3-5 business days to review the full offer.",
    }


async def get_salary_coaching(
    match_id: int,
    offer_details: dict,
    user_id: int,
    db: Session,
) -> dict:
    """
    Get salary negotiation coaching for a specific offer.
    Requires Pro tier subscription.
    """
    from app.models.match import Match
    from app.models.job import Job
    from app.models.candidate_profile import CandidateProfile
    from app.models.candidate import Candidate
    from app.services.billing import check_feature_access
    
    # Check Pro tier access
    candidate = db.query(Candidate).filter(Candidate.user_id == user_id).first()
    if not check_feature_access(candidate, "salary_negotiation"):
        return {
            "error": "upgrade_required",
            "message": "Salary negotiation coaching is a Pro feature. Upgrade to unlock personalized negotiation strategies.",
        }
    
    match = db.query(Match).filter(
        Match.id == match_id,
        Match.user_id == user_id,
    ).first()
    
    if not match:
        return {"error": "Match not found"}
    
    job = db.query(Job).filter(Job.id == match.job_id).first()
    profile = db.query(CandidateProfile).filter(
        CandidateProfile.user_id == user_id
    ).order_by(CandidateProfile.version.desc()).first()
    
    if not job or not profile:
        return {"error": "Missing data"}
    
    profile_json = profile.profile_json or {}
    basics = profile_json.get("basics", {})
    experience = profile_json.get("experience", [])
    skills = profile_json.get("skills", [])
    preferences = profile_json.get("preferences", {})
    
    reasons = match.reasons or {}
    
    return analyze_offer(
        offer_salary=offer_details.get("salary", 0),
        offer_bonus=offer_details.get("bonus"),
        offer_equity=offer_details.get("equity"),
        job_title=job.title,
        company=job.company,
        job_salary_min=job.salary_min,
        job_salary_max=job.salary_max,
        candidate_experience_years=len(experience) * 2,
        candidate_current_salary=preferences.get("salary_current"),
        candidate_location=basics.get("location", ""),
        candidate_skills=skills[:15],
        matched_skills=reasons.get("matched_skills", []),
    )
```

### Part 2: Update Billing Tier Config

**File to modify:** `services/api/app/services/billing.py`

Add `salary_negotiation` to Pro tier features:

```python
CANDIDATE_PLAN_LIMITS = {
    "free": {
        # ... existing ...
        "salary_negotiation": False,
    },
    "starter": {
        # ... existing ...
        "salary_negotiation": False,
    },
    "pro": {
        # ... existing ...
        "salary_negotiation": True,
    },
}
```

### Part 3: API Endpoint

**File to modify:** `services/api/app/routers/matches.py`

```python
from app.services.salary_coach import get_salary_coaching
from pydantic import BaseModel

class OfferDetails(BaseModel):
    salary: int
    bonus: int | None = None
    equity: str | None = None

@router.post("/api/matches/{match_id}/salary-coaching")
async def get_salary_negotiation_coaching(
    match_id: int,
    offer: OfferDetails,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get AI-powered salary negotiation coaching for a job offer.
    Pro tier feature.
    """
    result = await get_salary_coaching(
        match_id=match_id,
        offer_details=offer.dict(),
        user_id=user.id,
        db=db,
    )
    
    if result.get("error") == "upgrade_required":
        raise HTTPException(
            status_code=402,
            detail=result["message"],
        )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result
```

### Part 4: Frontend - Salary Coach Modal

**File to create:** `apps/web/app/components/matches/SalaryCoachModal.tsx`

```tsx
'use client';

import { useState } from 'react';

interface CounterOffer {
  target_salary: number;
  minimum_acceptable: number;
  script: string;
  justification_points: string[];
}

interface AlternativeAsk {
  item: string;
  suggested_amount: string;
  script: string;
}

interface CoachingResult {
  offer_assessment: {
    overall: string;
    salary_position: string;
    total_comp_analysis: string;
  };
  negotiation_strategy: {
    approach: string;
    reasoning: string;
    risk_level: string;
  };
  counter_offer: CounterOffer;
  alternative_asks: AlternativeAsk[];
  red_flags: string[];
  positive_signals: string[];
  timeline_advice: string;
}

interface Props {
  matchId: number;
  jobTitle: string;
  company: string;
  onClose: () => void;
}

export default function SalaryCoachModal({ matchId, jobTitle, company, onClose }: Props) {
  const [step, setStep] = useState<'input' | 'loading' | 'result'>('input');
  const [salary, setSalary] = useState('');
  const [bonus, setBonus] = useState('');
  const [equity, setEquity] = useState('');
  const [result, setResult] = useState<CoachingResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setStep('loading');
    setError(null);
    
    try {
      const res = await fetch(`/api/matches/${matchId}/salary-coaching`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          salary: parseInt(salary.replace(/,/g, '')),
          bonus: bonus ? parseInt(bonus.replace(/,/g, '')) : null,
          equity: equity || null,
        }),
      });
      
      if (res.status === 402) {
        setError('upgrade');
        setStep('input');
        return;
      }
      
      const data = await res.json();
      setResult(data);
      setStep('result');
    } catch (e) {
      setError('Failed to analyze offer');
      setStep('input');
    }
  };

  const formatCurrency = (n: number) => `$${n.toLocaleString()}`;

  const assessmentColors = {
    below_market: 'bg-red-100 text-red-800',
    at_market: 'bg-yellow-100 text-yellow-800',
    above_market: 'bg-green-100 text-green-800',
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-xl font-semibold">💰 Salary Negotiation Coach</h2>
            <p className="text-sm text-gray-500">{jobTitle} at {company}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
        </div>

        {error === 'upgrade' && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
            <p className="text-amber-800 font-medium">Pro Feature</p>
            <p className="text-amber-700 text-sm">
              Salary negotiation coaching is available on the Pro plan.
            </p>
            <a href="/settings/billing" className="text-amber-800 underline text-sm">
              Upgrade to Pro →
            </a>
          </div>
        )}

        {step === 'input' && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Offered Base Salary *
              </label>
              <input
                type="text"
                value={salary}
                onChange={(e) => setSalary(e.target.value)}
                placeholder="120,000"
                className="w-full border rounded-lg p-3"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Bonus (optional)
                </label>
                <input
                  type="text"
                  value={bonus}
                  onChange={(e) => setBonus(e.target.value)}
                  placeholder="15,000"
                  className="w-full border rounded-lg p-3"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Equity (optional)
                </label>
                <input
                  type="text"
                  value={equity}
                  onChange={(e) => setEquity(e.target.value)}
                  placeholder="0.1% or 10,000 RSUs"
                  className="w-full border rounded-lg p-3"
                />
              </div>
            </div>
            <button
              onClick={handleSubmit}
              disabled={!salary}
              className="w-full bg-emerald-600 text-white py-3 rounded-lg font-medium hover:bg-emerald-700 disabled:opacity-50"
            >
              Analyze My Offer
            </button>
          </div>
        )}

        {step === 'loading' && (
          <div className="text-center py-12">
            <div className="animate-spin h-12 w-12 border-4 border-emerald-600 border-t-transparent rounded-full mx-auto mb-4" />
            <p className="text-gray-600">Analyzing your offer...</p>
          </div>
        )}

        {step === 'result' && result && (
          <div className="space-y-6">
            {/* Assessment */}
            <div className={`p-4 rounded-lg ${assessmentColors[result.offer_assessment.overall]}`}>
              <p className="font-medium capitalize">{result.offer_assessment.overall.replace('_', ' ')}</p>
              <p className="text-sm mt-1">{result.offer_assessment.salary_position}</p>
            </div>

            {/* Strategy */}
            <div>
              <h3 className="font-medium mb-2">Recommended Strategy</h3>
              <p className="text-gray-600">{result.negotiation_strategy.reasoning}</p>
              <span className={`inline-block mt-2 text-xs px-2 py-1 rounded-full ${
                result.negotiation_strategy.risk_level === 'low' ? 'bg-green-100 text-green-700' :
                result.negotiation_strategy.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                'bg-red-100 text-red-700'
              }`}>
                {result.negotiation_strategy.risk_level} risk
              </span>
            </div>

            {/* Counter Offer */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h3 className="font-medium text-blue-900 mb-2">💬 Your Counter Script</h3>
              <p className="text-blue-800 text-sm italic">"{result.counter_offer.script}"</p>
              <div className="mt-3 flex gap-4 text-sm">
                <div>
                  <p className="text-blue-600">Target</p>
                  <p className="font-bold text-blue-900">{formatCurrency(result.counter_offer.target_salary)}</p>
                </div>
                <div>
                  <p className="text-blue-600">Minimum</p>
                  <p className="font-bold text-blue-900">{formatCurrency(result.counter_offer.minimum_acceptable)}</p>
                </div>
              </div>
            </div>

            {/* Justification Points */}
            <div>
              <h3 className="font-medium mb-2">Your Justification Points</h3>
              <ul className="space-y-1 text-sm text-gray-600">
                {result.counter_offer.justification_points.map((p, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-emerald-500">✓</span> {p}
                  </li>
                ))}
              </ul>
            </div>

            {/* Alternative Asks */}
            <div>
              <h3 className="font-medium mb-2">If Salary Is Fixed, Ask For:</h3>
              <div className="space-y-2">
                {result.alternative_asks.map((ask, i) => (
                  <div key={i} className="bg-gray-50 p-3 rounded-lg text-sm">
                    <p className="font-medium">{ask.item}: {ask.suggested_amount}</p>
                    <p className="text-gray-600 text-xs mt-1">"{ask.script}"</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Timeline */}
            <div className="bg-gray-100 p-3 rounded-lg text-sm">
              <p className="font-medium">⏰ Timing</p>
              <p className="text-gray-600">{result.timeline_advice}</p>
            </div>

            <button
              onClick={onClose}
              className="w-full bg-gray-100 text-gray-700 py-2 rounded-lg hover:bg-gray-200"
            >
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
```

### Part 5: Trigger on Offer Status

When application status changes to "offer":

```tsx
{match.application_status === 'offer' && (
  <button
    onClick={() => setShowSalaryCoach(true)}
    className="bg-emerald-600 text-white px-4 py-2 rounded-lg"
  >
    💰 Get Negotiation Help
  </button>
)}
```

---

## Cost Analysis

| Scenario | Cost |
|----------|------|
| Per coaching session (Sonnet) | ~$0.03-0.05 |
| Pro tier revenue | $29/month |
| Break-even | ~600 sessions/user (well beyond usage) |

---

## Summary Checklist

- [ ] Service: `salary_coach.py` with `analyze_offer()`
- [ ] Billing: `salary_negotiation` feature gated to Pro tier
- [ ] API: `POST /api/matches/{match_id}/salary-coaching`
- [ ] Input: Salary, bonus, equity fields
- [ ] Analysis: Market position, strategy, risk level
- [ ] Counter script: Exact words to say
- [ ] Justifications: Specific talking points
- [ ] Alternatives: Other things to negotiate
- [ ] Frontend: `SalaryCoachModal` component
- [ ] Upgrade prompt: For non-Pro users
- [ ] Tests and linting complete

Return code changes only.
