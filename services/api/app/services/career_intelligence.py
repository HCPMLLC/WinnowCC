"""Career Intelligence Engine — AI-powered recruiter/employer tools.

Capabilities:
1. generate_candidate_brief  — AI candidate summary for recruiters
2. compute_market_position   — percentile ranking among applicants
3. salary_intelligence       — role/location salary percentiles
4. predict_time_to_fill      — hiring timeline estimate
5. predict_career_trajectory  — 6/12-month career path prediction
6. notify_employer_high_match — auto-brief on high IPS matches
"""

import json
import logging
import math
import os
import re
import statistics
from datetime import UTC, datetime, timedelta

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate_profile import CandidateProfile
from app.models.career_intelligence import (
    CareerTrajectory,
    MarketIntel,
    RecruiterCandidateBrief,
    TimeFillPrediction,
)
from app.models.employer import EmployerJob
from app.models.job import Job
from app.models.match import Match

logger = logging.getLogger(__name__)


def _infer_seniority(title: str) -> str:
    """Infer seniority level from a job/role title."""
    t = title.lower()
    if any(w in t for w in ("junior", "jr.", "jr ", "entry", "associate")):
        return "junior"
    if any(w in t for w in ("senior", "sr.", "sr ", "lead", "principal", "staff")):
        return "senior"
    if any(w in t for w in ("manager", "director", "vp", "head of")):
        return "manager"
    return "mid"


def _extract_json(text: str) -> str:
    """Extract JSON from LLM responses.

    Handles code fences, XML tags, or preamble.
    """
    text = text.strip()
    # Strip XML-like thinking tags (e.g. <thinking>...</thinking>, <antThinking>...)
    text = re.sub(r"<[\w-]+>.*?</[\w-]+>", "", text, flags=re.DOTALL).strip()
    # Try to find a ```json ... ``` code block anywhere in the text
    m = re.search(r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Try to find raw JSON object
    m = re.search(r"(\{.*\})", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text


MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


# ---------------------------------------------------------------------------
# 1. Candidate brief
# ---------------------------------------------------------------------------
def generate_candidate_brief(
    candidate_profile_id: int,
    employer_job_id: int | None,
    brief_type: str,
    user_id: int | None,
    db: Session,
) -> dict:
    """Generate an AI candidate brief for a recruiter.

    brief_type: "general" | "job_specific" | "submittal"
      - general: 1-paragraph elevator pitch + structured summary (no job context)
      - job_specific: Matches candidate against a job with fit rationale and gaps
      - submittal: Client-ready document formatted for email/PDF
    """
    profile = db.execute(
        select(CandidateProfile).where(CandidateProfile.id == candidate_profile_id)
    ).scalar_one_or_none()
    if not profile:
        raise ValueError("Candidate profile not found")

    profile_data = profile.profile_json or {}

    job_context = ""
    match_context = ""
    employer_job_exists = False
    if employer_job_id:
        # Try recruiter_jobs first, then employer_jobs, then regular jobs
        from app.models.recruiter_job import RecruiterJob

        rec_job = db.execute(
            select(RecruiterJob).where(RecruiterJob.id == employer_job_id)
        ).scalar_one_or_none()
        if rec_job:
            job_context = (
                f"\n\nJob context:\nTitle: {rec_job.title}\n"
                f"Client: {rec_job.client_company_name or 'N/A'}\n"
                f"Description: {(rec_job.description or '')[:1000]}\n"
                f"Requirements: {rec_job.requirements or 'N/A'}\n"
                f"Location: {rec_job.location or 'N/A'}\n"
                f"Salary range: "
                f"{rec_job.salary_min or 'N/A'}-"
                f"{rec_job.salary_max or 'N/A'}\n"
                f"Remote: {rec_job.remote_policy or 'N/A'}"
            )
        else:
            ej = db.execute(
                select(EmployerJob).where(EmployerJob.id == employer_job_id)
            ).scalar_one_or_none()
            if ej:
                employer_job_exists = True
                job_context = (
                    f"\n\nJob context:\nTitle: {ej.title}\n"
                    f"Description: {(ej.description or '')[:1000]}\n"
                    f"Requirements: {ej.requirements or 'N/A'}\n"
                    f"Salary range: {ej.salary_min or 'N/A'}-{ej.salary_max or 'N/A'}\n"
                    f"Remote: {ej.remote_policy or 'N/A'}"
                )
            else:
                rj = db.execute(
                    select(Job).where(Job.id == employer_job_id)
                ).scalar_one_or_none()
                if rj:
                    job_context = (
                        f"\n\nJob context:\nTitle: {rj.title}\n"
                        f"Company: {rj.company or 'N/A'}\n"
                        f"Description: {(rj.description_text or '')[:1000]}\n"
                        f"Location: {rj.location or 'N/A'}\n"
                        f"Salary range: "
                        f"{rj.salary_min or 'N/A'}"
                        f"-{rj.salary_max or 'N/A'}"
                    )
        # Look up existing match for context
        # (Match uses user_id, not candidate_profile_id)
        if profile.user_id:
            match = db.execute(
                select(Match).where(
                    Match.user_id == profile.user_id,
                    Match.job_id == employer_job_id,
                )
            ).scalar_one_or_none()
            if match:
                match_context = (
                    f"\n\nExisting match score: {match.match_score}\n"
                    f"Match details: "
                    f"{json.dumps(match.reasons or {}, default=str)}"
                )

    type_instructions = {
        "general": (
            "Generate a GENERAL brief: 2-3 sentence elevator pitch plus structured "
            "summary. No job-specific analysis needed. Set fit_rationale to null."
        ),
        "job_specific": (
            "Generate a JOB-SPECIFIC brief: Match candidate against the provided job. "
            "Include detailed fit rationale, skill alignment with evidence, gap "
            "analysis, and why they should (or shouldn't) be interviewed."
        ),
        "submittal": (
            "Generate a SUBMITTAL brief: Client-ready document formatted for "
            "email/PDF. Include everything from a job-specific brief plus a polished "
            "full_text section that a recruiter can copy-paste into a client email."
        ),
    }

    system_prompt = (
        "You are a senior recruiting analyst. Generate a structured candidate brief. "
        "NEVER fabricate — every claim must come from the candidate data provided. "
        "Never invent credentials, dates, employers, or skills. "
        "Return valid JSON with these exact keys:\n"
        '  "elevator_pitch": "2-3 sentence punchy summary",\n'
        '  "headline": "Senior Backend Engineer | 8 YoE | Python/Go | Fintech",\n'
        '  "strengths": ["Evidence-backed strength 1", "..."],\n'
        '  "concerns": ["Honest gap 1", "..."],\n'
        '  "fit_rationale": "Why they fit THIS job '
        "(null for general). "
        'Use \\n\\n between paragraphs for readability.",\n'
        '  "skills_alignment": {\n'
        '    "matched": [{"skill": "Python", "evidence": "Led team building APIs"}],\n'
        '    "missing": [{"skill": "Kubernetes", "severity": "nice_to_have"}]\n'
        "  },\n"
        '  "compensation_note": "Salary alignment commentary or null",\n'
        '  "availability": "Notice period or availability info, or null",\n'
        '  "fit_score": 0-100 integer rating overall '
        "fitness (90-100 Exceptional, 75-89 Strong, "
        "60-74 Moderate, 40-59 Weak, 0-39 Poor),\n"
        '  "recommended_action": "Interview immediately / Consider / Pass",\n'
        '  "full_text": "Complete formatted brief for copy/paste"'
    )

    user_msg = (
        f"{type_instructions.get(brief_type, type_instructions['general'])}\n\n"
        f"Candidate profile:\n{json.dumps(profile_data, default=str)}"
        f"{job_context}{match_context}"
    )

    client = _get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw_text = _extract_json(response.content[0].text)
    try:
        brief_json = json.loads(raw_text)
    except json.JSONDecodeError:
        # LLM response may be truncated — try to salvage by closing braces
        salvaged = raw_text.rstrip()
        open_braces = salvaged.count("{") - salvaged.count("}")
        open_brackets = salvaged.count("[") - salvaged.count("]")
        salvaged += "]" * max(0, open_brackets) + "}" * max(0, open_braces)
        try:
            brief_json = json.loads(salvaged)
        except json.JSONDecodeError:
            brief_json = {"full_text": raw_text}

    full_text = brief_json.get("full_text", raw_text)

    record = RecruiterCandidateBrief(
        candidate_profile_id=candidate_profile_id,
        employer_job_id=employer_job_id if employer_job_exists else None,
        generated_by_user_id=user_id,
        brief_type=brief_type,
        brief_json=brief_json,
        brief_text=full_text,
        model_used=MODEL,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {"id": record.id, "brief_type": brief_type, **brief_json}


# ---------------------------------------------------------------------------
# 2. Market position
# ---------------------------------------------------------------------------
def compute_market_position(
    candidate_profile_id: int,
    employer_job_id: int,
    db: Session,
) -> dict:
    """Compute candidate's percentile position among all matches for a job."""
    matches = db.execute(
        select(Match.user_id, Match.match_score)
        .where(Match.job_id == employer_job_id)
        .order_by(Match.match_score.desc())
    ).all()

    if not matches:
        return {
            "percentile": None,
            "total_candidates": 0,
            "message": "No matches found for this job",
        }

    # Resolve candidate_profile_id to user_id for lookup
    from app.models.candidate_profile import CandidateProfile

    profile_row = db.execute(
        select(CandidateProfile.user_id).where(
            CandidateProfile.id == candidate_profile_id
        )
    ).first()
    target_user_id = profile_row.user_id if profile_row else None

    scores = [m.match_score for m in matches if m.match_score is not None]
    candidate_match = next((m for m in matches if m.user_id == target_user_id), None)

    if not candidate_match or candidate_match.match_score is None:
        return {
            "percentile": None,
            "total_candidates": len(scores),
            "message": "Candidate has not been matched to this job",
        }

    candidate_score = candidate_match.match_score
    below = sum(1 for s in scores if s < candidate_score)
    percentile = round((below / len(scores)) * 100, 1) if scores else 0

    return {
        "percentile": percentile,
        "candidate_score": float(candidate_score),
        "total_candidates": len(scores),
        "rank": sorted(scores, reverse=True).index(candidate_score) + 1,
        "avg_score": round(statistics.mean(scores), 2) if scores else None,
        "top_score": max(scores) if scores else None,
    }


# ---------------------------------------------------------------------------
# 3. Salary intelligence
# ---------------------------------------------------------------------------
def salary_intelligence(
    role_title: str,
    location: str | None,
    db: Session,
) -> dict:
    """Compute salary percentiles for a role/location from jobs data."""
    scope_key = f"{role_title.lower()}|{(location or 'remote').lower()}"

    # Check cache
    cached = db.execute(
        select(MarketIntel).where(
            MarketIntel.scope_type == "salary",
            MarketIntel.scope_key == scope_key,
            MarketIntel.expires_at > datetime.now(UTC),
        )
    ).scalar_one_or_none()

    if cached:
        return cached.data_json

    # Query jobs with salary data
    query = select(Job.salary_min, Job.salary_max).where(
        Job.title.ilike(f"%{role_title}%"),
        Job.salary_min.isnot(None),
    )
    if location:
        query = query.where(Job.location.ilike(f"%{location}%"))

    rows = db.execute(query).all()

    # Tier 2: parsed salary from job descriptions
    if not rows:
        from app.models.job_parsed_detail import JobParsedDetail

        pd_query = (
            select(
                JobParsedDetail.parsed_salary_min,
                JobParsedDetail.parsed_salary_max,
            )
            .join(Job, Job.id == JobParsedDetail.job_id)
            .where(
                Job.title.ilike(f"%{role_title}%"),
                JobParsedDetail.parsed_salary_min.isnot(None),
            )
        )
        if location:
            pd_query = pd_query.where(Job.location.ilike(f"%{location}%"))
        pd_rows = db.execute(pd_query).all()
        if pd_rows:
            rows = [
                type(
                    "R",
                    (),
                    {
                        "salary_min": r.parsed_salary_min,
                        "salary_max": r.parsed_salary_max or r.parsed_salary_min,
                    },
                )()
                for r in pd_rows
            ]

    if rows:
        # Use midpoint of salary ranges
        salaries = sorted(
            [(r.salary_min + (r.salary_max or r.salary_min)) / 2 for r in rows]
        )
        n = len(salaries)

        def percentile(pct: int) -> int:
            idx = int(n * pct / 100)
            return int(salaries[min(idx, n - 1)])

        result = {
            "role": role_title,
            "location": location,
            "sample_size": n,
            "currency": "USD",
            "p10": percentile(10),
            "p25": percentile(25),
            "p50": percentile(50),
            "p75": percentile(75),
            "p90": percentile(90),
        }

        # Cache with 7-day expiry
        intel = MarketIntel(
            scope_type="salary",
            scope_key=scope_key,
            data_json=result,
            sample_size=n,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db.merge(intel)
        db.commit()

        return result

    # Tier 3: Reference table fallback
    from app.services.salary_reference import estimate_salary

    seniority = _infer_seniority(role_title)
    ref = estimate_salary(role_title, seniority)
    if ref:
        lo, hi = ref[0], ref[1]
        span = hi - lo
        result = {
            "role": role_title,
            "location": location,
            "sample_size": 0,
            "source": "reference",
            "currency": ref[2],
            "p10": lo,
            "p25": int(lo + span * 0.25),
            "p50": int(lo + span * 0.50),
            "p75": int(lo + span * 0.75),
            "p90": hi,
        }

        # Cache with shorter 3-day expiry for reference data
        intel = MarketIntel(
            scope_type="salary",
            scope_key=scope_key,
            data_json=result,
            sample_size=0,
            expires_at=datetime.now(UTC) + timedelta(days=3),
        )
        db.merge(intel)
        db.commit()

        return result

    # Tier 4: LLM estimate (Claude Haiku — fast, cheap, sufficient for salary)
    try:
        client = _get_client()
        llm_response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=(
                "You are a salary data analyst. Given a job title, seniority level, "
                "and optional location, estimate the annual salary range in USD. "
                'Return JSON only: {"min": <int>, "max": <int>, "currency": "USD", '
                '"confidence": "low"|"medium"|"high"}'
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Role: {role_title}, Seniority: {seniority}, "
                        f"Location: {location or 'US National'}"
                    ),
                }
            ],
        )
        llm_raw = _extract_json(llm_response.content[0].text)
        llm_data = json.loads(llm_raw)
        lo = int(llm_data["min"])
        hi = int(llm_data["max"])
        span = hi - lo
        result = {
            "role": role_title,
            "location": location,
            "sample_size": 0,
            "source": "ai_estimate",
            "currency": llm_data.get("currency", "USD"),
            "confidence": llm_data.get("confidence", "low"),
            "p10": lo,
            "p25": int(lo + span * 0.25),
            "p50": int(lo + span * 0.50),
            "p75": int(lo + span * 0.75),
            "p90": hi,
        }

        # Cache with 1-day expiry (shorter — AI estimates are less stable)
        intel = MarketIntel(
            scope_type="salary",
            scope_key=scope_key,
            data_json=result,
            sample_size=0,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        db.merge(intel)
        db.commit()

        return result
    except Exception:
        logger.warning("LLM salary estimate failed for '%s'", role_title, exc_info=True)

    return {
        "role": role_title,
        "location": location,
        "sample_size": 0,
        "message": "Insufficient salary data for this query",
    }


# ---------------------------------------------------------------------------
# 4. Time-to-fill prediction (hybrid: empirical stats + LLM adjustment)
# ---------------------------------------------------------------------------

_HAIKU_MODEL = "claude-haiku-4-5-20251001"

_TTF_LLM_SYSTEM = """\
You are a hiring‐analytics expert. Given a job posting, estimate how its \
specific attributes will affect time-to-fill RELATIVE to the statistical \
median for similar roles.

Return ONLY valid JSON (no markdown, no commentary):
{
  "adjustment_factor": <float 0.70 to 1.50>,
  "reasoning": "<1-2 sentence summary>",
  "signals": [
    {"signal": "<keyword>", "impact": "<e.g. +15%>", "detail": "<brief>"}
  ]
}

Signals to look for:
- urgency language ("ASAP", "backfill", "immediate") → faster (factor < 1)
- niche/rare skill combinations → slower (factor > 1)
- security clearance, visa sponsorship → slower
- strong employer brand or "FAANG-tier" → faster
- location constraints (rural, no remote option) → slower
- excessive mandatory requirements (10+) → slower
- competitive compensation explicitly stated → faster
- contract/temp vs permanent → faster for short-term

Be conservative: most jobs should be 0.90–1.15. Only use extremes for \
truly unusual postings."""


def _llm_ttf_adjustment(
    title: str,
    description: str,
    segment_median: int,
    employment_type: str,
    employer_job_id: int,
    db: Session,
) -> dict:
    """Call Claude Haiku to analyse the job posting for TTF adjustment signals.

    Returns ``{"adjustment_factor": float, "reasoning": str, "signals": list}``.
    Falls back to ``{"adjustment_factor": 1.0}`` on any failure.
    """
    neutral = {
        "adjustment_factor": 1.0,
        "reasoning": "LLM analysis unavailable",
        "signals": [],
    }

    if not os.getenv("ANTHROPIC_API_KEY"):
        return neutral

    # Check cache (keyed by employer_job_id, 1-day TTL)
    cache_key = f"ej_{employer_job_id}"
    cached = db.execute(
        select(MarketIntel).where(
            MarketIntel.scope_type == "ttf_llm",
            MarketIntel.scope_key == cache_key,
            MarketIntel.expires_at > datetime.now(UTC),
        )
    ).scalar_one_or_none()
    if cached:
        return cached.data_json

    # Truncate description to stay within token budget
    desc_truncated = (description or "")[:3000]
    user_msg = (
        f"Job title: {title}\n"
        f"Employment type: {employment_type}\n"
        f"Statistical median for similar roles: {segment_median} days\n\n"
        f"Job description:\n{desc_truncated}"
    )

    try:
        client = _get_client()
        resp = client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=256,
            temperature=0.0,
            system=_TTF_LLM_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = _extract_json(resp.content[0].text)
        result = json.loads(raw)

        # Clamp factor to safe range
        factor = max(0.70, min(1.50, float(result.get("adjustment_factor", 1.0))))
        result["adjustment_factor"] = factor
    except Exception:
        logger.warning(
            "LLM TTF adjustment failed for job %d",
            employer_job_id,
            exc_info=True,
        )
        return neutral

    # Cache result
    try:
        mi = MarketIntel(
            scope_type="ttf_llm",
            scope_key=cache_key,
            data_json=result,
            sample_size=1,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        db.merge(mi)
        db.flush()
    except Exception:
        logger.warning("Failed to cache LLM TTF adjustment", exc_info=True)

    return result


def _compute_confidence(sample_size: int) -> float:
    """Compute prediction confidence from sample size (logarithmic curve)."""
    if sample_size < _MIN_SEGMENT_SAMPLE:
        return 0.40
    return min(0.90, 0.40 + 0.50 * (1.0 - 1.0 / math.sqrt(sample_size)))


_MIN_SEGMENT_SAMPLE = 20


def predict_time_to_fill(
    employer_job_id: int | None = None,
    db: Session | None = None,
    *,
    recruiter_job_id: int | None = None,
) -> dict:
    """Predict days to fill a job.

    Accepts either ``employer_job_id`` or ``recruiter_job_id`` (not both).

    Hybrid approach:
    1. Statistical base — segment-based empirical medians from scraped jobs.
    2. LLM adjustment — Claude analyses job description for niche signals.
    3. Heuristic fallback — if no historical data exists at all.
    """
    from app.services.market_intelligence import compute_ttf_segment_stats

    if not employer_job_id and not recruiter_job_id:
        raise ValueError("Provide employer_job_id or recruiter_job_id")

    # --- Load job record (employer or recruiter) ---
    if recruiter_job_id:
        from app.models.recruiter_job import RecruiterJob

        job = db.execute(
            select(RecruiterJob).where(RecruiterJob.id == recruiter_job_id)
        ).scalar_one_or_none()
        if not job:
            raise ValueError("Recruiter job not found")
        job_source = "recruiter"
        # Use linked employer_job_id if available for the prediction record
        ej_id = getattr(job, "employer_job_id", None)
    else:
        job = db.execute(
            select(EmployerJob).where(EmployerJob.id == employer_job_id)
        ).scalar_one_or_none()
        if not job:
            raise ValueError("Job not found")
        job_source = "employer"
        ej_id = employer_job_id

    employment_type = (job.employment_type or "full-time").lower()
    title = job.title or ""

    # Try to get richer features from linked scraped job's parsed details
    seniority = None
    work_mode = None
    industry = None

    # Check for linked scraped job (employer jobs or recruiter jobs)
    linked_ej_id = (
        employer_job_id
        if job_source == "employer"
        else getattr(job, "employer_job_id", None)
    )
    if linked_ej_id:
        linked = db.execute(
            select(Job).where(Job.employer_job_id == linked_ej_id)
        ).scalar_one_or_none()
        if linked:
            from app.models.job_parsed_detail import JobParsedDetail

            jpd = db.execute(
                select(JobParsedDetail).where(JobParsedDetail.job_id == linked.id)
            ).scalar_one_or_none()
            if jpd:
                seniority = jpd.seniority_level
                work_mode = jpd.work_mode
                industry = jpd.inferred_industry

    # Infer seniority from title if not available from parsed details
    if not seniority:
        seniority = _infer_seniority(title)

    # Infer work_mode from remote_policy if not available
    if not work_mode and job.remote_policy:
        rp = job.remote_policy.lower()
        if "remote" in rp:
            work_mode = "remote"
        elif "hybrid" in rp:
            work_mode = "hybrid"
        else:
            work_mode = "onsite"

    # Unique key for LLM cache (works for both job types)
    llm_cache_id = ej_id or -(recruiter_job_id or 0)

    # --- Step 1: Statistical base ---
    segment = compute_ttf_segment_stats(
        employment_type=employment_type,
        seniority_level=seniority,
        work_mode=work_mode,
        industry=industry,
        session=db,
    )

    if segment:
        base_days = segment["median_days"]
        confidence = _compute_confidence(segment["sample_size"])
        method = "hybrid"

        # --- Step 2: LLM adjustment ---
        description = getattr(job, "description", "") or ""
        llm = _llm_ttf_adjustment(
            title=title,
            description=description,
            segment_median=base_days,
            employment_type=employment_type,
            employer_job_id=llm_cache_id,
            db=db,
        )
        adjustment = llm.get("adjustment_factor", 1.0)
        predicted_days = max(3, round(base_days * adjustment))

        factors = {
            "method": method,
            "statistical_base": {
                "tier": segment["tier_used"],
                "sample_size": segment["sample_size"],
                "median_days": segment["median_days"],
                "p25_days": segment["p25_days"],
                "p75_days": segment["p75_days"],
            },
            "llm_adjustment": {
                "factor": adjustment,
                "reasoning": llm.get("reasoning", ""),
                "signals": llm.get("signals", []),
            },
            "segment_key": (f"{employment_type}|{seniority}|{work_mode}|{industry}"),
        }
    else:
        # --- Step 3: Heuristic fallback ---
        base_days = {
            "full-time": 42,
            "contract": 21,
            "part-time": 28,
            "internship": 14,
        }.get(employment_type, 42)

        if job.remote_policy and "remote" in job.remote_policy.lower():
            base_days = int(base_days * 0.85)
        t = title.lower()
        if any(w in t for w in ("senior", "lead", "principal", "director")):
            base_days = int(base_days * 1.25)
        elif any(w in t for w in ("junior", "entry", "intern")):
            base_days = int(base_days * 0.75)

        predicted_days = base_days
        confidence = 0.40
        method = "heuristic_fallback"
        factors = {
            "method": method,
            "note": "Insufficient historical data for segment matching",
        }

    # Track recruiter_job_id in factors when no employer_job_id FK
    if recruiter_job_id:
        factors["recruiter_job_id"] = recruiter_job_id

    prediction = TimeFillPrediction(
        employer_job_id=ej_id or 0,
        predicted_days=predicted_days,
        confidence=confidence,
        factors_json=factors,
    )
    # Only persist if we have a valid employer_job_id FK
    if ej_id:
        db.add(prediction)
        db.commit()
        db.refresh(prediction)
        pred_id = prediction.id
    else:
        # Recruiter job without employer link — don't persist
        # (avoids FK constraint on employer_jobs.id)
        pred_id = None

    result = {
        "predicted_days": predicted_days,
        "confidence": round(float(confidence), 2),
        "factors": factors,
    }
    if pred_id:
        result["id"] = pred_id
    if employer_job_id:
        result["employer_job_id"] = employer_job_id
    if recruiter_job_id:
        result["recruiter_job_id"] = recruiter_job_id
    return result


# ---------------------------------------------------------------------------
# 5. Career trajectory
# ---------------------------------------------------------------------------
def predict_career_trajectory(
    candidate_profile_id: int,
    db: Session,
) -> dict:
    """Use AI to predict career trajectory from profile data."""
    profile = db.execute(
        select(CandidateProfile).where(CandidateProfile.id == candidate_profile_id)
    ).scalar_one_or_none()
    if not profile:
        raise ValueError("Candidate profile not found")

    profile_data = profile.profile_json or {}

    system_prompt = (
        "You are a career strategy advisor. Analyze the candidate's career history "
        "and predict likely trajectories. Return valid JSON with keys: "
        "current_level, trajectory_6mo (object with role, salary_range_min, "
        "salary_range_max, likelihood), trajectory_12mo (same structure), "
        "key_growth_areas (array), recommended_skills (array), "
        "career_velocity (string: accelerating/steady/plateauing)."
    )

    client = _get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": (
                    "Candidate profile:\n" + json.dumps(profile_data, default=str)
                ),
            }
        ],
    )

    raw = _extract_json(response.content[0].text)
    try:
        trajectory_json = json.loads(raw)
    except json.JSONDecodeError:
        trajectory_json = {"raw_prediction": raw}

    # Backfill missing salary ranges from reference table
    for key in ("trajectory_6mo", "trajectory_12mo"):
        step = trajectory_json.get(key)
        if not step or not isinstance(step, dict):
            continue
        if step.get("salary_range_min") and step.get("salary_range_max"):
            continue  # AI provided salary — keep it
        role = step.get("role", "")
        if role:
            from app.services.salary_reference import estimate_salary

            seniority = _infer_seniority(role)
            ref = estimate_salary(role, seniority)
            if ref:
                step["salary_range_min"] = ref[0]
                step["salary_range_max"] = ref[1]
                step["salary_source"] = "reference"

    record = CareerTrajectory(
        candidate_profile_id=candidate_profile_id,
        trajectory_json=trajectory_json,
        model_used=MODEL,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {"id": record.id, **trajectory_json}


# ---------------------------------------------------------------------------
# 6. High-match notification
# ---------------------------------------------------------------------------
def notify_employer_high_match(
    employer_job_id: int,
    candidate_profile_id: int,
    match_score: float,
    db: Session,
) -> dict | None:
    """Auto-generate brief + notification when IPS >= 80."""
    if match_score < 80:
        return None

    try:
        brief = generate_candidate_brief(
            candidate_profile_id=candidate_profile_id,
            employer_job_id=employer_job_id,
            brief_type="job_specific",
            user_id=None,
            db=db,
        )
    except Exception:
        logger.exception("Failed to generate high-match brief")
        return None

    logger.info(
        "High-match notification: job=%d candidate=%d score=%.1f",
        employer_job_id,
        candidate_profile_id,
        match_score,
    )

    return {
        "employer_job_id": employer_job_id,
        "candidate_profile_id": candidate_profile_id,
        "match_score": match_score,
        "brief_id": brief.get("id"),
    }
