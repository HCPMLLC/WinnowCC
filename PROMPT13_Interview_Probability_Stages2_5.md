# PROMPT12_Interview_Probability_Stages2_5.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and the existing openapi JSON files before making changes.

## Purpose

Complete the benchmark-based Interview Probability formula by implementing Stages 2–5. Stage 1 (Resume Score R_s) is already done. This prompt adds the Application Logistics Score (A_s), wires the existing Referral Multiplier (M_net), implements the Cover Letter Score (C_s), and combines everything into the full P_i formula. Preserve explainability and compliance — this is a heuristic estimate, not a guaranteed probability.

---

## Triggers — When to Use This Prompt

- Completing Stages 2–5 of the Interview Probability formula.
- Adding timing/platform scoring to matches.
- Wiring the cover letter score into match scoring.
- Computing the full P_i = [(0.70·R_s) + (0.20·C_s) + (0.10·A_s)] × M_net.
- Updating the frontend to display Interview Probability with explainability.

---

## The Formula

```
P_i = [(W_r · R_s) + (W_c · C_s) + (W_a · A_s)] × M_net
```

| Symbol | Name | Weight | Range | Source |
|--------|------|--------|-------|--------|
| R_s | Resume Score | W_r = 0.70 | 0–100 | Skill overlap + evidence strength + gap penalty |
| C_s | Cover Letter Score | W_c = 0.20 | 0–100 | Keyword alignment of cover letter with job |
| A_s | Application Logistics Score | W_a = 0.10 | 0–100 | Timing (days since posted) + platform |
| M_net | Referral Multiplier | — | 1.0 or 8.0 | 1.0 = cold apply, 8.0 = referred |
| P_i | Interview Probability | — | 0–100 (capped) | Combined output |

**Output capping:** The raw formula can exceed 100 when M_net = 8.0. Cap display value at 100. Store the raw value internally if useful for sorting, but never display > 100 to the user.

---

## What Already Exists (DO NOT recreate)

Read the codebase and OpenAPI specs carefully. These are already implemented:

1. **Stage 1 — R_s (Resume Score):** Computed and stored on Match. The `resume_score` field exists on the Match model and in `MatchResponse`. Computed in `services/api/app/services/matching.py`.

2. **Match model columns:** The Match model already has these columns (confirmed in OpenAPI `MatchResponse`):
   - `resume_score` (int, nullable) — R_s ✅
   - `cover_letter_score` (int, nullable) — C_s placeholder, currently null
   - `application_logistics_score` (int, nullable) — A_s placeholder, currently null
   - `referred` (boolean, default false) — M_net data ✅
   - `interview_probability` (int, nullable) — P_i placeholder, currently null
   - `interview_readiness_score` (int) — legacy field, keep for backward compatibility
   - `match_score` (int) — the overall match score, keep as-is
   - `application_status` (string, nullable) — tracking status

3. **Referral endpoint:** `PATCH /api/matches/{match_id}/referred` exists in `services/api/app/routers/matches.py`. Accepts `ReferralUpdateRequest` with `referred: bool`. Returns `ReferralUpdateResponse`.

4. **Match response schemas:** `services/api/app/schemas/matches.py` already includes all P_i component fields in the response.

5. **Scoring logic:** `services/api/app/services/matching.py` already computes R_s and stores it. This is the file where A_s, C_s, and P_i logic must be added.

6. **Job model:** `services/api/app/models/job.py` has `posted_at` (datetime), `source` (string), and other metadata needed for A_s.

7. **Tailored resumes table:** `services/api/app/models/tailored_resume.py` — if PROMPT11 (Tailored ATS Resume) is implemented, cover letters are stored here or in a related table. C_s scoring should check for cover letter existence per match/job.

**Since all DB columns already exist, NO Alembic migration is needed for this prompt.** The work is purely scoring logic + frontend.

---

## What to Build

### Stage 2: Application Logistics Score (A_s)

**File to modify:** `services/api/app/services/matching.py`

#### 2.1 Timing sub-score (0–100)

Compute how many days have elapsed since the job was posted. Earlier applications get higher scores.

```python
def _compute_timing_score(job_posted_at: datetime, evaluation_time: datetime = None) -> int:
    """
    Score based on how quickly the candidate sees/applies to the job.
    
    0-7 days:   100 (within first week — ideal)
    8-10 days:   80
    11-14 days:  60
    15-21 days:  40
    22-30 days:  20
    31+ days:     5 (stale but not zero)
    
    Returns: int 0–100
    """
    if evaluation_time is None:
        evaluation_time = datetime.utcnow()
    
    if job_posted_at is None:
        return 50  # Unknown posting date — use neutral default
    
    days_since_posted = (evaluation_time - job_posted_at).days
    
    if days_since_posted <= 7:
        return 100
    elif days_since_posted <= 10:
        return 80
    elif days_since_posted <= 14:
        return 60
    elif days_since_posted <= 21:
        return 40
    elif days_since_posted <= 30:
        return 20
    else:
        return 5
```

**If the user has marked "Applied" (application_status = "applied"):** If you later store an `applied_at` timestamp, use that instead of `evaluation_time`. For now, use the match computation time as a proxy.

#### 2.2 Platform sub-score (0–100)

Map the job's `source` field to a platform effectiveness score based on industry benchmarks.

```python
PLATFORM_SCORES = {
    "indeed": 90,
    "themuse": 75,
    "remotive": 80,
    "greenhouse": 85,       # Company career page via Greenhouse
    "lever": 85,            # Company career page via Lever
    "linkedin": 40,         # High volume, lower per-application success rate
    "ziprecruiter": 60,
    "glassdoor": 55,
    "company_career_page": 90,  # Direct application — highest signal
    "default": 50,
}

def _compute_platform_score(job_source: str | None) -> int:
    """Return platform effectiveness score based on job source."""
    if not job_source:
        return PLATFORM_SCORES["default"]
    return PLATFORM_SCORES.get(job_source.lower().strip(), PLATFORM_SCORES["default"])
```

#### 2.3 Combine into A_s

```python
def compute_application_logistics_score(
    job_posted_at: datetime | None,
    job_source: str | None,
    evaluation_time: datetime | None = None,
) -> int:
    """
    A_s = 0.6 × timing + 0.4 × platform
    Clamped to 0–100.
    """
    timing = _compute_timing_score(job_posted_at, evaluation_time)
    platform = _compute_platform_score(job_source)
    a_s = int(round(0.6 * timing + 0.4 * platform))
    return max(0, min(100, a_s))
```

#### 2.4 Store A_s on Match

In the match computation flow (where `resume_score` is already stored), also compute and store `application_logistics_score`:

```python
match.application_logistics_score = compute_application_logistics_score(
    job_posted_at=job.posted_at,
    job_source=job.source,
)
```

---

### Stage 3: Referral Multiplier (M_net)

**No new code needed for the data model.** The `referred` boolean column and `PATCH /api/matches/{match_id}/referred` endpoint already exist.

#### 3.1 M_net computation

In `matching.py`, when computing P_i:

```python
def _get_referral_multiplier(referred: bool) -> float:
    """M_net = 8.0 if referred, else 1.0."""
    return 8.0 if referred else 1.0
```

#### 3.2 Frontend — "I have a referral" toggle

**File to modify:** `apps/web/app/matches/page.tsx`

On each match card, add a small toggle or checkbox labeled "I have a referral for this job." When toggled:

1. Call `PATCH /api/matches/{match_id}/referred` with `{ "referred": true }` (or `false` to un-set).
2. After successful response, re-fetch or update the local match data to show the updated P_i.

Implementation suggestion — add a component similar to `ApplicationStatusSelect`:

**Create this new file in Cursor:**
```
apps/web/app/components/ReferralToggle.tsx
```

This component renders a small checkbox or toggle that calls the PATCH endpoint when changed.

---

### Stage 4: Cover Letter Score (C_s)

**File to modify:** `services/api/app/services/matching.py` (add scoring function)

C_s measures how well a cover letter (if one exists for this job) aligns with the job description's keywords.

#### 4.1 Check if a cover letter exists

When computing P_i for a match, check if the user has generated a tailored resume + cover letter for this job:

```python
# In the P_i computation function:
# Query tailored_resumes for this user_id + job_id
# If a cover_letter_url exists → compute C_s
# If no cover letter → C_s = 0
```

#### 4.2 C_s scoring logic

If a cover letter exists (from PROMPT11 tailored resume generation), score it:

```python
def compute_cover_letter_score(
    cover_letter_text: str | None,
    job_description: str,
    job_requirements: str | None = None,
) -> int:
    """
    Score cover letter alignment with job description.
    
    Components:
    - Keyword overlap: what % of job keywords appear in the cover letter (0–60 points)
    - Length/structure: is it a proper length? (0–20 points)
    - Specificity: does it mention the company and role by name? (0–20 points)
    
    Returns: int 0–100
    """
    if not cover_letter_text or not cover_letter_text.strip():
        return 0
    
    cl_lower = cover_letter_text.lower()
    job_text = (job_description + " " + (job_requirements or "")).lower()
    
    # 1) Keyword overlap (0–60 points)
    # Extract meaningful words from job description (3+ chars, not stopwords)
    job_keywords = _extract_keywords(job_text)
    if job_keywords:
        matched = sum(1 for kw in job_keywords if kw in cl_lower)
        keyword_ratio = matched / len(job_keywords)
        keyword_score = int(round(keyword_ratio * 60))
    else:
        keyword_score = 30  # Neutral if can't extract keywords
    
    # 2) Length/structure (0–20 points)
    word_count = len(cover_letter_text.split())
    if 150 <= word_count <= 400:
        length_score = 20  # Ideal length
    elif 100 <= word_count < 150 or 400 < word_count <= 600:
        length_score = 12  # Acceptable
    else:
        length_score = 5   # Too short or too long
    
    # 3) Specificity (0–20 points)
    specificity_score = 0
    # Check if company name is mentioned
    # Check if role title is mentioned
    # (Company and role can be passed as params or extracted from job data)
    # For now, check for common patterns
    if any(phrase in cl_lower for phrase in ["dear hiring", "dear ", "to whom"]):
        specificity_score += 5
    if word_count > 50:  # Has substantive content
        specificity_score += 5
    # Bonus for paragraphs (indicates structure)
    paragraph_count = cover_letter_text.count("\n\n") + 1
    if 3 <= paragraph_count <= 5:
        specificity_score += 10
    elif paragraph_count >= 2:
        specificity_score += 5
    
    c_s = keyword_score + length_score + specificity_score
    return max(0, min(100, c_s))
```

#### 4.3 Helper — keyword extraction

```python
import re

STOPWORDS = {"the", "and", "for", "with", "that", "this", "from", "have", "will", 
             "are", "our", "you", "your", "can", "all", "been", "has", "was", "were",
             "but", "not", "they", "their", "than", "its", "who", "also", "into",
             "more", "other", "some", "such", "about", "would", "which", "when"}

def _extract_keywords(text: str, min_length: int = 3) -> list[str]:
    """Extract meaningful keywords from text, excluding stopwords."""
    words = re.findall(r'[a-z]+', text.lower())
    return list(set(w for w in words if len(w) >= min_length and w not in STOPWORDS))
```

#### 4.4 When to compute and store C_s

There are two trigger points:

**A) When P_i is computed (match refresh):** Check if a tailored resume with a cover letter exists for this user+job. If yes, load the cover letter text and compute C_s. Store on `match.cover_letter_score`.

**B) When a cover letter is generated (PROMPT11 tailor pipeline):** After generating the cover letter DOCX, immediately compute C_s and store it on the Match record for that user+job. This ensures C_s is available instantly without waiting for a match refresh.

Add to the tailor worker (if PROMPT11 is implemented):
```python
# After cover letter generation:
match = get_match_for_user_job(user_id, job_id, db)
if match:
    match.cover_letter_score = compute_cover_letter_score(
        cover_letter_text=cover_letter_content,
        job_description=job.description,
        job_requirements=job.requirements,
    )
    db.commit()
```

If PROMPT11 is NOT yet implemented, C_s defaults to 0 for all matches. The formula still works — it just weights R_s more heavily in practice.

---

### Stage 5: Combine into P_i and Expose

**File to modify:** `services/api/app/services/matching.py`

#### 5.1 The P_i computation function

```python
# Weights (recruiter-aligned benchmarks)
W_R = 0.70  # Resume
W_C = 0.20  # Cover Letter
W_A = 0.10  # Application Logistics

def compute_interview_probability(
    resume_score: int | None,
    cover_letter_score: int | None,
    application_logistics_score: int | None,
    referred: bool,
) -> int:
    """
    P_i = [(W_r · R_s) + (W_c · C_s) + (W_a · A_s)] × M_net
    
    Defaults: R_s=0, C_s=0, A_s=50 if not available.
    Capped at 100 for display.
    
    Returns: int 0–100
    """
    r_s = resume_score if resume_score is not None else 0
    c_s = cover_letter_score if cover_letter_score is not None else 0
    a_s = application_logistics_score if application_logistics_score is not None else 50
    m_net = 8.0 if referred else 1.0
    
    raw_pi = (W_R * r_s + W_C * c_s + W_A * a_s) * m_net
    
    # Cap at 100 for display
    capped_pi = int(round(min(100.0, raw_pi)))
    return max(0, capped_pi)
```

#### 5.2 Wire into the match computation pipeline

Find the place in `matching.py` where `resume_score` is computed and `match_score` / `interview_readiness_score` are stored. After those existing computations, add:

```python
# Compute A_s
match.application_logistics_score = compute_application_logistics_score(
    job_posted_at=job.posted_at,
    job_source=job.source,
)

# C_s: check if a cover letter exists for this user+job
# (If not yet implemented, this will be None → defaults to 0)
# cover_letter_score is already on the match if computed by tailor pipeline

# Compute full P_i
match.interview_probability = compute_interview_probability(
    resume_score=match.resume_score,
    cover_letter_score=match.cover_letter_score,
    application_logistics_score=match.application_logistics_score,
    referred=match.referred or False,
)

# Backward compatibility: also update interview_readiness_score
match.interview_readiness_score = match.interview_probability
```

#### 5.3 Recompute P_i when referral changes

In `services/api/app/routers/matches.py`, find the `PATCH /api/matches/{match_id}/referred` handler. After updating `match.referred`, recompute P_i:

```python
# After: match.referred = payload.referred
match.interview_probability = compute_interview_probability(
    resume_score=match.resume_score,
    cover_letter_score=match.cover_letter_score,
    application_logistics_score=match.application_logistics_score,
    referred=match.referred,
)
match.interview_readiness_score = match.interview_probability
db.commit()
```

Import `compute_interview_probability` from `services/api/app/services/matching.py`.

---

### Part 6: Frontend — Display Interview Probability with Explainability

**File to modify:** `apps/web/app/matches/page.tsx`

#### 6.1 Replace or update the score display

On each match card, currently displaying `interview_readiness_score`. Change to display `interview_probability` as the primary score.

Label: **"Interview Probability"** (or keep "Interview Readiness" if preferred)
Tooltip: "A benchmark-based estimate of interview likelihood. Not a guarantee."

#### 6.2 Score breakdown (expandable)

Add an expandable "How we score" or "Score breakdown" section on each match card (or on a detail view):

```
Interview Probability: 72 / 100
  ├─ Resume Score (R_s): 85 × 0.70 = 59.5
  ├─ Cover Letter (C_s): 0 × 0.20 = 0.0  ← "Generate a cover letter to boost this"
  ├─ Timing + Platform (A_s): 80 × 0.10 = 8.0
  ├─ Subtotal: 67.5
  └─ Referral (M_net): ×1.0 (cold apply)  ← "Have a referral? Toggle above to apply 8x multiplier"
     = 67.5 → capped at 68
```

Show each component:
- `resume_score` from `match.resume_score`
- `cover_letter_score` from `match.cover_letter_score` (show "—" or "Generate cover letter" CTA if null/0)
- `application_logistics_score` from `match.application_logistics_score`
- `referred` from `match.referred` (show "×1.0 (cold apply)" or "×8.0 (referred!)")
- `interview_probability` from `match.interview_probability`

#### 6.3 Color coding

- P_i ≥ 75: green (strong candidate)
- P_i 50–74: amber (competitive)
- P_i 25–49: orange (stretch)
- P_i < 25: red (significant gaps)

#### 6.4 Compliance copy

Add a small disclaimer near the score:
> "Benchmark-based estimate. Not a guarantee of interview outcome."

Use `text-xs text-gray-400` styling — visible but not prominent.

#### 6.5 Referral toggle

Add the referral toggle component (from Stage 3.2) on each match card. When toggled, the P_i should visually update (re-fetch match data or compute locally for instant feedback).

---

### Part 7: Create the ReferralToggle Component

**Create this new file:**
```
apps/web/app/components/ReferralToggle.tsx
```

```tsx
"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

interface Props {
  matchId: number;
  referred: boolean;
  onReferralChange?: (newReferred: boolean) => void;
}

export default function ReferralToggle({ matchId, referred, onReferralChange }: Props) {
  const [isReferred, setIsReferred] = useState(referred);
  const [saving, setSaving] = useState(false);

  const handleToggle = async () => {
    const newValue = !isReferred;
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/matches/${matchId}/referred`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ referred: newValue }),
      });
      if (res.ok) {
        setIsReferred(newValue);
        onReferralChange?.(newValue);
      }
    } catch (err) {
      console.error("Error updating referral:", err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <label className="flex items-center gap-2 cursor-pointer text-sm">
      <input
        type="checkbox"
        checked={isReferred}
        onChange={handleToggle}
        disabled={saving}
        className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
      />
      <span className={isReferred ? "text-purple-700 font-medium" : "text-gray-500"}>
        {isReferred ? "🤝 Referred (8× boost)" : "I have a referral"}
      </span>
      {saving && <span className="text-xs text-gray-400">Saving...</span>}
    </label>
  );
}
```

Import and use in `apps/web/app/matches/page.tsx`:
```tsx
import ReferralToggle from "../components/ReferralToggle";

// Inside each match card:
<ReferralToggle
  matchId={match.id}
  referred={match.referred || false}
  onReferralChange={() => refetchMatches()}
/>
```

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Scoring logic (A_s, C_s, P_i) | `services/api/app/services/matching.py` | MODIFY — add scoring functions |
| Referral PATCH handler | `services/api/app/routers/matches.py` | MODIFY — recompute P_i after referral change |
| Match model | `services/api/app/models/match.py` | READ ONLY — all columns already exist |
| Match schemas | `services/api/app/schemas/matches.py` | READ ONLY — all fields already in response |
| Job model | `services/api/app/models/job.py` | READ ONLY — has posted_at, source |
| Tailor service (C_s hook) | `services/api/app/services/tailor.py` | MODIFY — compute C_s after cover letter generation |
| ReferralToggle component | `apps/web/app/components/ReferralToggle.tsx` | CREATE |
| Matches page | `apps/web/app/matches/page.tsx` | MODIFY — add P_i display, breakdown, referral toggle |

---

## Implementation Order (for a beginner following in Cursor)

### Step 1: Add A_s scoring functions to matching.py

1. Open `services/api/app/services/matching.py` in Cursor.
2. Add the three functions: `_compute_timing_score`, `_compute_platform_score`, `compute_application_logistics_score`.
3. Add the `PLATFORM_SCORES` dictionary and `STOPWORDS` set.
4. Save the file.

### Step 2: Add C_s scoring function to matching.py

1. In the same file, add `_extract_keywords` helper and `compute_cover_letter_score`.
2. Save the file.

### Step 3: Add the P_i combination function

1. In the same file, add `W_R`, `W_C`, `W_A` constants and `compute_interview_probability`.
2. Save the file.

### Step 4: Wire A_s and P_i into the match computation pipeline

1. Find the existing code where `resume_score` is computed (search for `resume_score` in `matching.py`).
2. Below that, add the A_s computation and P_i computation.
3. Set `match.interview_readiness_score = match.interview_probability` for backward compatibility.
4. Save the file.

### Step 5: Recompute P_i on referral change

1. Open `services/api/app/routers/matches.py` in Cursor.
2. Find the `PATCH .../referred` handler function.
3. After `match.referred = payload.referred`, import and call `compute_interview_probability`.
4. Update `match.interview_probability` and `match.interview_readiness_score`.
5. Save the file.

### Step 6: Test backend

1. Start infra: `cd infra && docker compose up -d`
2. Start API: `cd services/api && .\.venv\Scripts\Activate.ps1 && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
3. Open `http://127.0.0.1:8000/docs`
4. Run `POST /api/matches/refresh` to recompute matches.
5. Call `GET /api/matches` — verify each match now has `application_logistics_score` and `interview_probability` populated.
6. Call `PATCH /api/matches/{id}/referred` with `{"referred": true}` — verify `interview_probability` increases.

### Step 7: Create the ReferralToggle component

1. Create: `apps/web/app/components/ReferralToggle.tsx`
2. Paste the component code from Part 7.
3. Save the file.

### Step 8: Update the matches page

1. Open `apps/web/app/matches/page.tsx` in Cursor.
2. Import `ReferralToggle`.
3. Replace or supplement the `interview_readiness_score` display with `interview_probability`.
4. Add the score breakdown expandable section.
5. Add the `ReferralToggle` to each match card.
6. Add color coding based on P_i value.
7. Add the compliance disclaimer.
8. Save the file.

### Step 9: Test end-to-end

1. Start all services (or use `.\start-dev.ps1`).
2. Open `http://localhost:3000/matches`.
3. Verify:
   - [ ] Each match shows "Interview Probability: XX" with the new score
   - [ ] Score breakdown shows R_s, C_s, A_s, and M_net
   - [ ] C_s shows "0" or "Generate cover letter" CTA when no cover letter exists
   - [ ] Referral toggle works — checking it triggers PATCH and score visually updates
   - [ ] Unchecking referral drops the score back down
   - [ ] Colors match the thresholds (green ≥75, amber 50–74, orange 25–49, red <25)
   - [ ] Compliance disclaimer is visible near the score
   - [ ] `interview_readiness_score` still works for backward compatibility

### Step 10: Lint and format

```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
python -m ruff check .
python -m ruff format .

cd apps/web
npm run lint
```

---

## Compliance and Positioning

- **SPEC.md says:** "Interview Readiness Score (heuristic, explainable; not a guaranteed probability)" and lists "No guaranteed interview probability claims" in non-goals.
- **UI copy:** Use "Interview Probability" or "Interview Readiness" with tooltip: "Based on resume fit, cover letter, application timing, and referral — a benchmark-based estimate, not a guarantee."
- **Legal:** Do not claim a literal probability of getting an interview. Position as an index informed by recruiter benchmarks.

---

## Non-Goals (Do NOT implement in this prompt)

- New database columns or migrations — all columns already exist.
- Cover letter generation — that's PROMPT11 (Tailored ATS Resume). C_s simply scores it if it exists.
- Changes to the match_score algorithm — only P_i is modified here.
- ML-based scoring models — keep it deterministic and explainable.
- Mobile (Expo) display — future Month 5 task.

---

## Summary Checklist

- [ ] Stage 2: `compute_application_logistics_score` added to `matching.py` (timing + platform)
- [ ] Stage 2: A_s stored on `match.application_logistics_score` during match computation
- [ ] Stage 3: `_get_referral_multiplier` returns 1.0 or 8.0 based on `match.referred`
- [ ] Stage 3: `ReferralToggle.tsx` created and used in matches page
- [ ] Stage 4: `compute_cover_letter_score` added to `matching.py` (keyword overlap + structure)
- [ ] Stage 4: C_s stored on `match.cover_letter_score` (via tailor pipeline or match refresh)
- [ ] Stage 5: `compute_interview_probability` combines all components with weights 0.70/0.20/0.10 × M_net
- [ ] Stage 5: P_i stored on `match.interview_probability`, capped at 100
- [ ] Stage 5: `interview_readiness_score` set from P_i for backward compatibility
- [ ] Stage 5: P_i recomputed when referral is toggled (PATCH handler updated)
- [ ] Frontend: Interview Probability displayed as primary score with color coding
- [ ] Frontend: Score breakdown shows R_s, C_s, A_s, M_net with explanations
- [ ] Frontend: Referral toggle on each match card
- [ ] Frontend: Compliance disclaimer visible
- [ ] Linted and formatted

Return code changes only.
