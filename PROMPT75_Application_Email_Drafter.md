# PROMPT75: Application Email Drafter

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md before making changes.

## Purpose

When a job requires email application, draft a professional intro email using the candidate's profile and job requirements — ready to copy/paste. Removes friction and ensures professional presentation.

---

## What Already Exists (DO NOT recreate)

1. **Candidate profile:** `candidate_profiles.profile_json` with experience, skills
2. **Job data:** `jobs` with title, company, description
3. **Match reasons:** `matches.reasons` with matched/missing skills
4. **Anthropic SDK:** Configured

---

## What to Build

### Part 1: Email Drafter Service

**File to create:** `services/api/app/services/email_drafter.py`

```python
"""
Application Email Drafter

Generates professional application emails tailored to specific jobs.
"""

from anthropic import Anthropic
from sqlalchemy.orm import Session
from app.core.config import settings

client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
MODEL = "claude-3-haiku-20240307"


def draft_application_email(
    candidate_name: str,
    candidate_title: str,
    candidate_experience_years: int,
    top_skills: list[str],
    top_achievements: list[str],
    job_title: str,
    company: str,
    job_requirements: list[str],
    matched_skills: list[str],
) -> dict:
    """
    Draft a professional application email.
    
    Returns:
        {
            "subject": "Application for Senior Developer - [Your Name]",
            "greeting": "Dear Hiring Manager,",
            "body": "Full email body...",
            "closing": "Best regards,",
            "full_email": "Complete formatted email"
        }
    """
    
    prompt = f"""Write a professional job application email.

Candidate:
- Name: {candidate_name}
- Current/Recent Title: {candidate_title}
- Years of Experience: {candidate_experience_years}
- Top Skills: {', '.join(top_skills[:5])}
- Key Achievements: {'; '.join(top_achievements[:3])}

Job:
- Title: {job_title}
- Company: {company}
- Key Requirements: {', '.join(job_requirements[:5])}
- Candidate's Matching Skills: {', '.join(matched_skills[:5])}

Return JSON:
{{
    "subject": "Email subject line",
    "greeting": "Opening greeting",
    "body": "Email body - 2-3 short paragraphs",
    "closing": "Professional closing"
}}

Email Rules:
1. Subject: Include job title and imply experience (not just "Application")
2. Keep total length under 200 words
3. Paragraph 1: Express interest and 1 sentence on relevant background
4. Paragraph 2: 2-3 specific qualifications that match requirements (use their achievements)
5. Paragraph 3: Call to action (interview request) and availability
6. Tone: Confident but not arrogant, professional but not stiff
7. DO NOT use clichés: "I am excited", "I believe I would be a great fit"
8. DO include specific numbers/achievements from their background
9. End with clear next step

Return ONLY valid JSON."""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        result = json.loads(response.content[0].text)
        
        # Compose full email
        result["full_email"] = f"""Subject: {result['subject']}

{result['greeting']}

{result['body']}

{result['closing']}
{candidate_name}"""
        
        return result
        
    except Exception as e:
        return _generate_fallback_email(
            candidate_name, candidate_title, job_title, company, top_skills
        )


def _generate_fallback_email(
    name: str,
    title: str,
    job_title: str,
    company: str,
    skills: list[str],
) -> dict:
    """Fallback template-based email."""
    
    skills_str = ", ".join(skills[:3]) if skills else "relevant experience"
    
    subject = f"{job_title} Application - {name}"
    greeting = "Dear Hiring Manager,"
    body = f"""I am writing to apply for the {job_title} position at {company}.

With experience as a {title} and skills in {skills_str}, I am confident I can contribute to your team.

I would welcome the opportunity to discuss how my background aligns with your needs. I am available for an interview at your convenience."""
    closing = "Best regards,"
    
    return {
        "subject": subject,
        "greeting": greeting,
        "body": body,
        "closing": closing,
        "full_email": f"Subject: {subject}\n\n{greeting}\n\n{body}\n\n{closing}\n{name}",
    }


async def generate_email_for_match(
    match_id: int,
    user_id: int,
    db: Session,
) -> dict:
    """Generate application email for a specific match."""
    from app.models.match import Match
    from app.models.job import Job
    from app.models.candidate_profile import CandidateProfile
    
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
    
    # Extract achievements from experience bullets
    achievements = []
    for exp in experience[:3]:
        for bullet in exp.get("bullets", [])[:2]:
            if any(c.isdigit() for c in bullet):  # Has numbers = likely achievement
                achievements.append(bullet)
    
    # Calculate experience years
    exp_years = len(experience) * 2  # Rough estimate
    
    reasons = match.reasons or {}
    
    return draft_application_email(
        candidate_name=basics.get("name", ""),
        candidate_title=experience[0].get("title", "") if experience else "",
        candidate_experience_years=exp_years,
        top_skills=skills[:10],
        top_achievements=achievements[:3],
        job_title=job.title,
        company=job.company,
        job_requirements=reasons.get("job_requirements", [])[:5],
        matched_skills=reasons.get("matched_skills", []),
    )
```

### Part 2: API Endpoint

**File to modify:** `services/api/app/routers/matches.py`

```python
from app.services.email_drafter import generate_email_for_match

@router.get("/api/matches/{match_id}/draft-email")
async def get_draft_email(
    match_id: int,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a draft application email for this job.
    """
    result = await generate_email_for_match(match_id, user.id, db)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.post("/api/matches/{match_id}/draft-email")
async def regenerate_draft_email(
    match_id: int,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Regenerate the draft email (fresh generation)."""
    return await generate_email_for_match(match_id, user.id, db)
```

### Part 3: Frontend - Email Draft Modal

**File to create:** `apps/web/app/components/matches/EmailDraftModal.tsx`

```tsx
'use client';

import { useState, useEffect } from 'react';

interface EmailDraft {
  subject: string;
  greeting: string;
  body: string;
  closing: string;
  full_email: string;
}

interface Props {
  matchId: number;
  jobTitle: string;
  company: string;
  onClose: () => void;
}

export default function EmailDraftModal({ matchId, jobTitle, company, onClose }: Props) {
  const [draft, setDraft] = useState<EmailDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetch(`/api/matches/${matchId}/draft-email`, { credentials: 'include' })
      .then(res => res.json())
      .then(setDraft)
      .finally(() => setLoading(false));
  }, [matchId]);

  const copyToClipboard = () => {
    if (draft) {
      navigator.clipboard.writeText(draft.full_email);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const regenerate = async () => {
    setLoading(true);
    const res = await fetch(`/api/matches/${matchId}/draft-email`, {
      method: 'POST',
      credentials: 'include',
    });
    const data = await res.json();
    setDraft(data);
    setLoading(false);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-xl font-semibold">📧 Draft Application Email</h2>
            <p className="text-sm text-gray-500">{jobTitle} at {company}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
        </div>

        {loading ? (
          <div className="space-y-3 animate-pulse">
            <div className="h-8 bg-gray-200 rounded w-2/3" />
            <div className="h-32 bg-gray-200 rounded" />
          </div>
        ) : draft ? (
          <>
            {/* Subject */}
            <div className="mb-4">
              <label className="text-xs font-medium text-gray-500">Subject</label>
              <div className="bg-gray-50 p-3 rounded border text-sm">
                {draft.subject}
              </div>
            </div>

            {/* Body */}
            <div className="mb-4">
              <label className="text-xs font-medium text-gray-500">Email</label>
              <div className="bg-gray-50 p-4 rounded border text-sm whitespace-pre-wrap font-mono">
                {draft.greeting}
                {'\n\n'}
                {draft.body}
                {'\n\n'}
                {draft.closing}
                {'\n'}[Your Name]
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={copyToClipboard}
                className={`flex-1 py-2 rounded-lg font-medium ${
                  copied 
                    ? 'bg-green-100 text-green-700' 
                    : 'bg-emerald-600 text-white hover:bg-emerald-700'
                }`}
              >
                {copied ? '✓ Copied!' : '📋 Copy to Clipboard'}
              </button>
              <button
                onClick={regenerate}
                className="px-4 py-2 border rounded-lg text-gray-600 hover:bg-gray-50"
              >
                🔄 Regenerate
              </button>
            </div>

            <p className="text-xs text-gray-400 mt-4 text-center">
              Review and personalize before sending. Add your contact info and signature.
            </p>
          </>
        ) : (
          <p className="text-red-600">Failed to generate email draft.</p>
        )}
      </div>
    </div>
  );
}
```

### Part 4: Add Button to Match Card

**File to modify:** Match card or job detail component

```tsx
const [showEmailDraft, setShowEmailDraft] = useState(false);

// In the match card actions:
<button
  onClick={() => setShowEmailDraft(true)}
  className="text-sm text-blue-600 hover:underline flex items-center gap-1"
>
  <span>📧</span>
  <span>Draft Intro Email</span>
</button>

{showEmailDraft && (
  <EmailDraftModal
    matchId={match.id}
    jobTitle={match.job.title}
    company={match.job.company}
    onClose={() => setShowEmailDraft(false)}
  />
)}
```

---

## Cost Analysis

| Scenario | Cost |
|----------|------|
| Per email draft (Haiku) | ~$0.008-0.012 |
| 50 drafts/day | ~$0.40-0.60/day |

---

## Summary Checklist

- [ ] Service: `email_drafter.py` with `draft_application_email()`
- [ ] Profile extraction: Uses candidate's actual achievements
- [ ] Personalization: Matches skills to job requirements
- [ ] API: `GET/POST /api/matches/{match_id}/draft-email`
- [ ] Frontend: `EmailDraftModal` component
- [ ] Copy to clipboard: One-click copying
- [ ] Regenerate: Option to get fresh draft
- [ ] Fallback: Template-based email when LLM unavailable
- [ ] Tests and linting complete

Return code changes only.
