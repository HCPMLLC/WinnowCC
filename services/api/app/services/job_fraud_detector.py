"""Fraud detection and duplicate detection for job postings."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.job_parsed_detail import JobParsedDetail

logger = logging.getLogger(__name__)

# Configurable thresholds
FRAUD_THRESHOLD = int(os.environ.get("FRAUD_THRESHOLD", "69"))
STALE_LAST_SEEN_DAYS = int(os.environ.get("STALE_LAST_SEEN_DAYS", "30"))
STALE_POSTED_DAYS = int(os.environ.get("STALE_POSTED_DAYS", "45"))


# ---------------------------------------------------------------------------
# Fraud signal definitions
# ---------------------------------------------------------------------------
# Each signal: (name, description, points, check_function_name)
FRAUD_SIGNALS: list[dict] = [
    {
        "code": "SCAM_PHRASE",
        "description": "Contains known scam phrases",
        "points": 20,
        "severity": "high",
    },
    {
        "code": "NO_COMPANY",
        "description": "Company name is missing or generic",
        "points": 15,
        "severity": "high",
    },
    {
        "code": "SHORT_DESCRIPTION",
        "description": "Description is extremely short (<100 chars)",
        "points": 15,
        "severity": "medium",
    },
    {
        "code": "SALARY_ANOMALY",
        "description": "Salary range is suspiciously high or low",
        "points": 10,
        "severity": "medium",
    },
    {
        "code": "NO_REQUIREMENTS",
        "description": "No skills or qualifications mentioned",
        "points": 10,
        "severity": "medium",
    },
    {
        "code": "URGENCY_LANGUAGE",
        "description": "Excessive urgency language (ASAP, immediately, etc.)",
        "points": 8,
        "severity": "low",
    },
    {
        "code": "PERSONAL_INFO_REQUEST",
        "description": "Requests personal/financial information upfront",
        "points": 20,
        "severity": "high",
    },
    {
        "code": "FEE_REQUIRED",
        "description": "Requires payment or fee from candidate",
        "points": 25,
        "severity": "high",
    },
    {
        "code": "VAGUE_TITLE",
        "description": "Job title is vague or generic",
        "points": 8,
        "severity": "low",
    },
    {
        "code": "EXCESSIVE_CAPS",
        "description": "Excessive use of ALL CAPS",
        "points": 5,
        "severity": "low",
    },
    {
        "code": "NO_LOCATION",
        "description": "No meaningful location provided",
        "points": 5,
        "severity": "low",
    },
    {
        "code": "CRYPTO_SCAM",
        "description": "Crypto/forex trading signals",
        "points": 15,
        "severity": "high",
    },
    {
        "code": "GMAIL_CONTACT",
        "description": "Uses free email provider for business contact",
        "points": 8,
        "severity": "medium",
    },
    {
        "code": "DUPLICATE_POSTING",
        "description": "Duplicate of another job posting",
        "points": 5,
        "severity": "low",
    },
]

_SCAM_PHRASES = [
    "make money fast",
    "earn from home",
    "no experience needed",
    "unlimited earning",
    "guaranteed income",
    "wire transfer",
    "money order",
    "western union",
    "be your own boss",
    "financial freedom",
    "mlm",
    "multi-level marketing",
    "pyramid",
    "network marketing opportunity",
]

_URGENCY_PHRASES = [
    "hiring immediately",
    "start today",
    "urgent hire",
    "asap",
    "immediate start",
    "start immediately",
    "hiring now",
    "apply today limited",
]

_PERSONAL_INFO_PHRASES = [
    "social security",
    "ssn",
    "bank account number",
    "credit card",
    "driver's license number",
    "send us your id",
    "copy of passport",
]

_FEE_PHRASES = [
    "registration fee",
    "application fee",
    "training fee",
    "upfront payment",
    "deposit required",
    "pay for training",
    "buy the kit",
    "purchase required",
    "investment required",
]

_CRYPTO_PHRASES = [
    "crypto trading",
    "forex trading",
    "bitcoin investment",
    "cryptocurrency opportunity",
    "nft opportunity",
    "decentralized finance opportunity",
]

_VAGUE_TITLES = [
    "opportunity",
    "position available",
    "job opening",
    "work from home",
    "make money",
    "earn cash",
    "team member",
    "representative",
]

_FREE_EMAIL_DOMAINS = [
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "aol.com",
    "mail.com",
    "protonmail.com",
]


class JobFraudDetector:
    """Fraud scoring and duplicate detection for job postings."""

    def evaluate(
        self, session: Session, job: Job, parsed: JobParsedDetail
    ) -> JobParsedDetail:
        """Run fraud scoring and duplicate detection on a parsed job.

        Updates the parsed record with fraud_score, red_flags,
        is_likely_fraudulent, and dedup info.
        """
        red_flags: list[dict] = []
        total_score = 0

        text_lower = (job.description_text or "").lower()
        title_lower = (job.title or "").lower()

        # 1. Scam phrases
        for phrase in _SCAM_PHRASES:
            if phrase in text_lower:
                total_score += 20
                red_flags.append(
                    {
                        "code": "SCAM_PHRASE",
                        "severity": "high",
                        "description": f"Contains scam phrase: '{phrase}'",
                        "points": 20,
                    }
                )
                break  # Count once

        # 2. No company
        company = (job.company or "").strip()
        if not company or company.lower() in (
            "n/a",
            "unknown",
            "confidential",
            "company",
        ):
            total_score += 15
            red_flags.append(
                {
                    "code": "NO_COMPANY",
                    "severity": "high",
                    "description": "Company name is missing or generic",
                    "points": 15,
                }
            )

        # 3. Short description
        if len(text_lower) < 100:
            total_score += 15
            red_flags.append(
                {
                    "code": "SHORT_DESCRIPTION",
                    "severity": "medium",
                    "description": f"Description is only {len(text_lower)} characters",
                    "points": 15,
                }
            )

        # 4. Salary anomaly
        if (
            parsed.parsed_salary_min is not None
            and parsed.salary_confidence == "parsed"
        ):
            if parsed.parsed_salary_min > 500_000:
                total_score += 10
                red_flags.append(
                    {
                        "code": "SALARY_ANOMALY",
                        "severity": "medium",
                        "description": (
                            f"Salary min ${parsed.parsed_salary_min:,}"
                            " is suspiciously high"
                        ),
                        "points": 10,
                    }
                )
            elif (
                parsed.parsed_salary_max is not None
                and parsed.parsed_salary_max < 15_000
            ):
                total_score += 10
                red_flags.append(
                    {
                        "code": "SALARY_ANOMALY",
                        "severity": "medium",
                        "description": (
                            f"Salary max ${parsed.parsed_salary_max:,}"
                            " is suspiciously low"
                        ),
                        "points": 10,
                    }
                )

        # 5. No requirements
        if (
            (not parsed.required_skills or len(parsed.required_skills) == 0)
            and (
                not parsed.required_certifications
                or len(parsed.required_certifications) == 0
            )
            and parsed.years_experience_min is None
        ):
            total_score += 10
            red_flags.append(
                {
                    "code": "NO_REQUIREMENTS",
                    "severity": "medium",
                    "description": (
                        "No skills, certifications, or experience requirements found"
                    ),
                    "points": 10,
                }
            )

        # 6. Urgency language
        for phrase in _URGENCY_PHRASES:
            if phrase in text_lower:
                total_score += 8
                red_flags.append(
                    {
                        "code": "URGENCY_LANGUAGE",
                        "severity": "low",
                        "description": f"Urgency phrase: '{phrase}'",
                        "points": 8,
                    }
                )
                break

        # 7. Personal info request
        for phrase in _PERSONAL_INFO_PHRASES:
            if phrase in text_lower:
                total_score += 20
                red_flags.append(
                    {
                        "code": "PERSONAL_INFO_REQUEST",
                        "severity": "high",
                        "description": f"Requests personal information: '{phrase}'",
                        "points": 20,
                    }
                )
                break

        # 8. Fee required
        for phrase in _FEE_PHRASES:
            if phrase in text_lower:
                total_score += 25
                red_flags.append(
                    {
                        "code": "FEE_REQUIRED",
                        "severity": "high",
                        "description": f"Requires fee: '{phrase}'",
                        "points": 25,
                    }
                )
                break

        # 9. Vague title
        if any(vt in title_lower for vt in _VAGUE_TITLES):
            total_score += 8
            red_flags.append(
                {
                    "code": "VAGUE_TITLE",
                    "severity": "low",
                    "description": "Job title is vague or generic",
                    "points": 8,
                }
            )

        # 10. Excessive caps
        if (
            job.title
            and sum(1 for c in job.title if c.isupper()) > len(job.title) * 0.6
        ):
            total_score += 5
            red_flags.append(
                {
                    "code": "EXCESSIVE_CAPS",
                    "severity": "low",
                    "description": "Excessive use of ALL CAPS in title",
                    "points": 5,
                }
            )

        # 11. No location
        if not job.location or job.location.strip().lower() in (
            "",
            "n/a",
            "unknown",
            "anywhere",
        ):
            if not job.remote_flag:
                total_score += 5
                red_flags.append(
                    {
                        "code": "NO_LOCATION",
                        "severity": "low",
                        "description": "No meaningful location provided",
                        "points": 5,
                    }
                )

        # 12. Crypto scam
        for phrase in _CRYPTO_PHRASES:
            if phrase in text_lower:
                total_score += 15
                red_flags.append(
                    {
                        "code": "CRYPTO_SCAM",
                        "severity": "high",
                        "description": f"Crypto/forex signal: '{phrase}'",
                        "points": 15,
                    }
                )
                break

        # 13. Free email for business
        for domain in _FREE_EMAIL_DOMAINS:
            if job.hiring_manager_email and domain in job.hiring_manager_email.lower():
                total_score += 8
                red_flags.append(
                    {
                        "code": "GMAIL_CONTACT",
                        "severity": "medium",
                        "description": f"Business contact uses free email: {domain}",
                        "points": 8,
                    }
                )
                break

        # 14. Duplicate detection
        dup_flag = self._check_duplicates(session, job, parsed)
        if dup_flag:
            total_score += 5
            red_flags.append(dup_flag)

        # Store results
        parsed.fraud_score = total_score
        parsed.red_flags = red_flags

        # <20 clean, 20-39 flags, 40-59 review, >=threshold fraud
        parsed.is_likely_fraudulent = total_score >= FRAUD_THRESHOLD

        # Set job is_active to false for fraudulent postings
        if parsed.is_likely_fraudulent:
            job.is_active = False

        session.flush()
        return parsed

    def _check_duplicates(
        self, session: Session, job: Job, parsed: JobParsedDetail
    ) -> dict | None:
        """Check for duplicate postings using 4 layers.

        Returns a red_flag dict if duplicate found, else None.
        """
        # Layer 1: Exact content_hash already handled in ingestion

        # Layer 2: Title + Company + Location fuzzy match
        similar_jobs = (
            session.execute(
                select(Job)
                .where(
                    and_(
                        Job.id != job.id,
                        Job.company == job.company,
                        Job.is_active.is_(True),
                    )
                )
                .limit(100)
            )
            .scalars()
            .all()
        )

        for other in similar_jobs:
            # Simple Levenshtein-like check: compare title words
            if self._title_fuzzy_match(job.title, other.title):
                if self._location_similar(job.location, other.location):
                    # This is likely a duplicate
                    self._assign_dedup_group(session, job, other)
                    parsed.is_duplicate_of_job_id = other.id
                    return {
                        "code": "DUPLICATE_POSTING",
                        "severity": "low",
                        "description": (
                            f"Similar to job #{other.id}:"
                            f" {other.title} at {other.company}"
                        ),
                        "points": 5,
                    }

        # Layer 3: Description Jaccard similarity >0.80 + same company
        for other in similar_jobs:
            if (
                self._description_similarity(
                    job.description_text or "", other.description_text or ""
                )
                > 0.80
            ):
                self._assign_dedup_group(session, job, other)
                parsed.is_duplicate_of_job_id = other.id
                return {
                    "code": "DUPLICATE_POSTING",
                    "severity": "low",
                    "description": f"Description very similar to job #{other.id}",
                    "points": 5,
                }

        # Layer 4 removed: same title+company within 14 days is now
        # handled at ingestion time via title_company_hash fingerprint.

        return None

    def _title_fuzzy_match(self, title1: str | None, title2: str | None) -> bool:
        """Simple fuzzy title comparison (Levenshtein distance <= 2 via word diff)."""
        if not title1 or not title2:
            return False
        words1 = set(title1.lower().split())
        words2 = set(title2.lower().split())
        if not words1 or not words2:
            return False
        # If titles differ by 2 or fewer words, consider them similar
        diff = (words1 - words2) | (words2 - words1)
        return len(diff) <= 2

    def _location_similar(self, loc1: str | None, loc2: str | None) -> bool:
        """Check if two locations are similar."""
        if not loc1 or not loc2:
            return True  # If either is missing, don't filter on location
        return loc1.lower().strip() == loc2.lower().strip()

    def _description_similarity(self, text1: str, text2: str) -> float:
        """Jaccard similarity of word sets."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0

    def _assign_dedup_group(self, session: Session, job: Job, canonical: Job) -> None:
        """Assign both jobs to the same dedup group."""
        if canonical.dedup_group_id:
            job.dedup_group_id = canonical.dedup_group_id
        else:
            group_id = str(uuid.uuid4())[:8]
            canonical.dedup_group_id = group_id
            job.dedup_group_id = group_id


def _is_job_stale(job: Job, now: datetime) -> bool:
    """Check whether a job should be considered stale."""
    if job.application_deadline:
        deadline = job.application_deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        if now > deadline:
            return True
    if job.last_seen_at:
        return (now - job.last_seen_at).days > STALE_LAST_SEEN_DAYS
    if job.posted_at:
        posted = job.posted_at
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=UTC)
        return (now - posted).days > STALE_POSTED_DAYS
    return False


def check_stale_jobs(session: Session) -> int:
    """Mark jobs as stale if they haven't been seen recently.

    A job is stale if:
    - last_seen_at is more than STALE_LAST_SEEN_DAYS (default 30) days ago, OR
    - posted_at is more than STALE_POSTED_DAYS (default 45) days ago and no last_seen_at

    Checks both jobs with and without parsed details.
    Returns number of jobs marked stale.
    """
    now = datetime.now(UTC)
    stale_count = 0

    # Pass 1: Jobs that have a JobParsedDetail row
    stmt = (
        select(JobParsedDetail, Job)
        .join(Job, JobParsedDetail.job_id == Job.id)
        .where(Job.is_active.is_(True))
    )
    results = session.execute(stmt).all()

    for parsed, job in results:
        if _is_job_stale(job, now):
            parsed.is_stale = True
            job.is_active = False
            stale_count += 1

    # Pass 2: Active jobs without a JobParsedDetail row
    parsed_job_ids = select(JobParsedDetail.job_id)
    stmt2 = select(Job).where(
        Job.is_active.is_(True),
        Job.id.not_in(parsed_job_ids),
    )
    unparsed_jobs = session.execute(stmt2).scalars().all()

    for job in unparsed_jobs:
        if _is_job_stale(job, now):
            job.is_active = False
            stale_count += 1

    if stale_count > 0:
        session.flush()

    return stale_count
