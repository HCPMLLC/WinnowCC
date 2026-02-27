"""Re-parse resume + parse jobs + recompute matches for Ronald Levi (user 9)."""

import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.resume_document import ResumeDocument

USER_ID = 9
DB_URL = os.getenv(
    "DB_URL",
    "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch",
)

engine = create_engine(DB_URL)

# ── Step 1: Re-parse resume ────────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 1: Re-parse resume for Ronald Levi (user 9)")
print("=" * 60)

with Session(engine) as session:
    resume = session.execute(
        select(ResumeDocument)
        .where(ResumeDocument.user_id == USER_ID)
        .order_by(ResumeDocument.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if resume is None:
        print("ERROR: No resume document found for user 9")
        sys.exit(1)

    print(f"Found resume: id={resume.id}, file={resume.filename}, path={resume.path}")

    from pathlib import Path

    from app.services.profile_parser import extract_text
    from app.services.resume_parse_job import (
        _enrich_new_profile,
        _get_latest_profile,
        _get_next_version,
        _merge_profiles,
        _parse_with_fallback,
        _sync_candidate_preferences,
    )
    from app.services.trust_scoring import evaluate_trust_for_resume

    text = extract_text(Path(resume.path))
    if not text.strip():
        print("ERROR: No text extracted from resume")
        sys.exit(1)
    print(f"Extracted {len(text)} characters from resume")

    parsed_json = _parse_with_fallback(text)
    print(
        f"Parsed {len(parsed_json.get('skills', []))} skills, "
        f"{len(parsed_json.get('experience', []))} experiences"
    )

    existing_profile = _get_latest_profile(session, USER_ID)
    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == USER_ID)
    ).scalar_one_or_none()

    if existing_profile:
        profile_json = _merge_profiles(existing_profile.profile_json, parsed_json)
        print(f"Merged with existing profile v{existing_profile.version}")
    else:
        profile_json = parsed_json
        _enrich_new_profile(profile_json)
        print("Created new profile (no existing)")

    _sync_candidate_preferences(profile_json, candidate)

    next_version = _get_next_version(session, USER_ID)
    profile = CandidateProfile(
        user_id=USER_ID,
        resume_document_id=resume.id,
        version=next_version,
        profile_json=profile_json,
    )
    session.add(profile)
    session.commit()

    evaluate_trust_for_resume(
        session, resume, profile_json=profile_json, action="recompute_after_parse"
    )

    print(f"Created profile version {next_version}")
    print(f"  Skills: {profile_json.get('skills', [])[:10]}...")
    prefs = profile_json.get("preferences", {})
    print(f"  Target titles: {prefs.get('target_titles', [])}")
    print(f"  Locations: {prefs.get('locations', [])}")

    profile_version = next_version

# ── Step 2: Parse all active jobs with JobParserService ─────────────────────
print("\n" + "=" * 60)
print("STEP 2: Parse jobs with JobParserService + FraudDetector")
print("=" * 60)

with Session(engine) as session:
    try:
        from app.models.job_parsed_detail import JobParsedDetail
        from app.services.job_fraud_detector import JobFraudDetector
        from app.services.job_parser import JobParserService

        jobs = (
            session.execute(select(Job).where(Job.is_active.is_not(False)))
            .scalars()
            .all()
        )
        print(f"Found {len(jobs)} active jobs to parse")

        parser = JobParserService()
        fraud_detector = JobFraudDetector()
        success = 0
        errors = 0

        for job in jobs:
            try:
                parsed = parser.parse(session, job)
                fraud_detector.evaluate(session, job, parsed)
                success += 1
            except Exception as e:
                logger.warning(f"Failed to parse job {job.id} ({job.title}): {e}")
                errors += 1

        session.commit()
        print(f"Parsed {success} jobs successfully, {errors} errors")

        # Show a few examples
        sample = session.execute(select(JobParsedDetail).limit(3)).scalars().all()
        for p in sample:
            print(
                f"  Job {p.job_id}: quality={p.posting_quality_score}, "
                f"fraud={p.fraud_score}, "
                f"skills={p.required_skills[:5] if p.required_skills else []}"
            )
    except Exception as e:
        logger.exception(f"Job parsing step failed: {e}")
        session.rollback()
        print(f"WARNING: Job parsing failed ({e}), continuing to matching...")

# ── Step 3: Recompute matches ──────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"STEP 3: Compute matches for user 9, profile v{profile_version}")
print("=" * 60)

with Session(engine) as session:
    from app.services.matching import compute_matches

    matches = compute_matches(session, user_id=USER_ID, profile_version=profile_version)
    print(f"Created {len(matches)} matches")

    if matches:
        print("\nTop 10 matches:")
        for i, m in enumerate(matches[:10], 1):
            job = session.get(Job, m.job_id)
            deep = m.reasons.get("deep_scoring", {})
            dims = deep.get("dimensions", {}) if deep else {}
            print(f"\n  {i}. {job.title} at {job.company}")
            print(f"     IPS: {m.interview_probability}  |  Match: {m.match_score}")
            if dims:
                print(
                    f"     Skills: {dims.get('skills', 'n/a')}  "
                    f"Exp: {dims.get('experience', 'n/a')}  "
                    f"Loc: {dims.get('location', 'n/a')}  "
                    f"Comp: {dims.get('compensation', 'n/a')}  "
                    f"Title: {dims.get('title', 'n/a')}"
                )
            skills = m.reasons.get("matched_skills", [])
            if skills:
                print(f"     Matched skills: {skills[:8]}")

print("\n" + "=" * 60)
print("DONE - Resume re-parsed, jobs parsed, matches recomputed")
print("=" * 60)
