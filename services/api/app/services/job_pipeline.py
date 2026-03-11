from __future__ import annotations

import logging

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.job_parsed_detail import JobParsedDetail
from app.services.embedding import (
    generate_embedding,
    prepare_job_text,
    prepare_profile_text,
)
from app.services.job_ingestion import ingest_jobs
from app.services.matching import compute_matches
from app.services.tailor import create_tailored_docs

logger = logging.getLogger(__name__)


def ingest_jobs_job(query: dict) -> int:
    session = get_session_factory()()
    try:
        return ingest_jobs(session, query)
    except Exception:
        session.rollback()
        logger.exception("ingest_jobs_job: failed for query %s", query)
        return 0
    finally:
        session.close()


def match_jobs_job(user_id: int, profile_version: int) -> int:
    if user_id is None:
        logger.warning("match_jobs_job: skipping — user_id is None")
        return 0
    session = get_session_factory()()
    try:
        matches = compute_matches(session, user_id, profile_version)
        return len(matches)
    except Exception:
        session.rollback()
        logger.exception(
            "match_jobs_job: failed for user=%s version=%s", user_id, profile_version
        )
        return 0
    finally:
        session.close()


def tailor_job(user_id: int, job_id: int, profile_version: int) -> int:
    session = get_session_factory()()
    try:
        tailored = create_tailored_docs(session, user_id, job_id, profile_version)
        return tailored.id
    except Exception:
        session.rollback()
        logger.exception(
            "tailor_job: failed for user=%s job=%s version=%s",
            user_id,
            job_id,
            profile_version,
        )
        return 0
    finally:
        session.close()


def embed_job(job_id: int) -> bool:
    """Generate and store embedding for a single job."""
    session = get_session_factory()()
    try:
        job = session.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
        if job is None:
            logger.warning("embed_job: job %s not found", job_id)
            return False
        text = prepare_job_text(job)
        job.embedding = generate_embedding(text)
        session.commit()
        logger.info("embed_job: embedded job %s", job_id)
        return True
    except Exception:
        session.rollback()
        logger.exception("embed_job: failed for job %s", job_id)
        return False
    finally:
        session.close()


def embed_profile(user_id: int, profile_version: int) -> bool:
    """Generate and store embedding for a candidate profile."""
    session = get_session_factory()()
    try:
        profile = session.execute(
            select(CandidateProfile).where(
                CandidateProfile.user_id == user_id,
                CandidateProfile.version == profile_version,
            )
        ).scalar_one_or_none()
        if profile is None:
            logger.warning(
                "embed_profile: profile not found for user=%s version=%s",
                user_id,
                profile_version,
            )
            return False
        text = prepare_profile_text(profile.profile_json)
        profile.embedding = generate_embedding(text)
        session.commit()
        logger.info(
            "embed_profile: embedded profile user=%s version=%s",
            user_id,
            profile_version,
        )
        return True
    except Exception:
        session.rollback()
        logger.exception(
            "embed_profile: failed for user=%s version=%s", user_id, profile_version
        )
        return False
    finally:
        session.close()


def embed_all_jobs() -> int:
    """Batch backfill embeddings for all jobs where embedding IS NULL."""
    session = get_session_factory()()
    try:
        jobs = (
            session.execute(select(Job).where(Job.embedding.is_(None))).scalars().all()
        )
        count = 0
        for job in jobs:
            try:
                text = prepare_job_text(job)
                job.embedding = generate_embedding(text)
                count += 1
                if count % 50 == 0:
                    session.commit()
                    logger.info("embed_all_jobs: embedded %s jobs so far", count)
            except Exception:
                logger.exception("embed_all_jobs: failed for job %s", job.id)
        session.commit()
        logger.info("embed_all_jobs: finished, embedded %s jobs total", count)
        return count
    except Exception:
        session.rollback()
        logger.exception("embed_all_jobs: batch failed")
        return 0
    finally:
        session.close()


def refresh_candidates_for_profile(user_id: int) -> None:
    """Placeholder for future candidate-refresh logic after profile update."""
    pass


def populate_recruiter_job_candidates(job_id: int) -> None:
    """Background job: compute and cache candidate matches for a recruiter job.

    Includes embedding backfill, auto-populate pipeline, and a 25-point
    match threshold.  Used by the SSE refresh endpoint, bulk refresh, and
    the daily scheduled refresh.
    """
    from sqlalchemy import delete as sa_delete

    from app.models.recruiter import RecruiterProfile
    from app.models.recruiter_job import RecruiterJob
    from app.models.recruiter_job_candidate import RecruiterJobCandidate
    from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
    from app.services.matching import find_top_candidates_for_recruiter_job

    session = get_session_factory()()
    try:
        job = session.get(RecruiterJob, job_id)
        if not job:
            logger.warning(
                "populate_recruiter_job_candidates: job %s not found", job_id
            )
            return
        rp = session.get(RecruiterProfile, job.recruiter_profile_id)
        if not rp:
            logger.warning(
                "populate_recruiter_job_candidates: recruiter profile %s not found",
                job.recruiter_profile_id,
            )
            return

        # Backfill embedding if missing
        if job.embedding is None:
            try:
                text = (
                    f"Job Title: {job.title}\n"
                    f"Company: {job.client_company_name or ''}\n"
                    f"Description: {(job.description or '')[:2000]}\n"
                    f"Requirements: {(job.requirements or '')[:1000]}\n"
                    f"Location: {job.location or ''}"
                )
                job.embedding = generate_embedding(text)
                session.commit()
            except Exception:
                logger.debug(
                    "populate_recruiter_job_candidates: "
                    "embedding backfill failed for job %s",
                    job_id,
                )

        results = find_top_candidates_for_recruiter_job(session, job, rp.user_id)

        # Delete old cached rows
        session.execute(
            sa_delete(RecruiterJobCandidate).where(
                RecruiterJobCandidate.recruiter_job_id == job_id
            )
        )

        inserted = 0
        for r in results:
            if r["match_score"] <= 25:
                continue
            session.add(
                RecruiterJobCandidate(
                    recruiter_job_id=job_id,
                    candidate_profile_id=r["id"],
                    match_score=r["match_score"],
                    matched_skills=r.get("matched_skills"),
                )
            )
            inserted += 1

        session.commit()

        # Auto-populate pipeline if recruiter setting is enabled
        pipeline_added = 0
        if rp.auto_populate_pipeline:
            try:
                cached = (
                    session.execute(
                        select(RecruiterJobCandidate).where(
                            RecruiterJobCandidate.recruiter_job_id == job_id
                        )
                    )
                    .scalars()
                    .all()
                )
                for rjc in cached:
                    exists = session.execute(
                        select(RecruiterPipelineCandidate.id).where(
                            RecruiterPipelineCandidate.recruiter_profile_id == rp.id,
                            RecruiterPipelineCandidate.candidate_profile_id
                            == rjc.candidate_profile_id,
                        )
                    ).scalar_one_or_none()
                    if not exists:
                        session.add(
                            RecruiterPipelineCandidate(
                                recruiter_profile_id=rp.id,
                                recruiter_job_id=job_id,
                                candidate_profile_id=rjc.candidate_profile_id,
                                source="auto-match",
                                stage="sourced",
                                match_score=rjc.match_score,
                            )
                        )
                        pipeline_added += 1
                if pipeline_added:
                    session.commit()
            except Exception:
                logger.warning(
                    "populate_recruiter_job_candidates: "
                    "pipeline auto-populate failed for job %s",
                    job_id,
                )

        logger.info(
            "populate_recruiter_job_candidates: job %s — "
            "%s cached, %s pipeline added",
            job_id,
            inserted,
            pipeline_added,
        )
    except Exception:
        session.rollback()
        logger.exception("populate_recruiter_job_candidates: failed for job %s", job_id)
    finally:
        session.close()


def backfill_recruiter_job_fields(job_id: int) -> bool:
    """Re-parse a recruiter job's stored text to extract missing required fields.

    Uses Claude Haiku to extract ``job_id_external`` (solicitation number)
    and ``close_date`` (application deadline) from the job's existing
    description + requirements text.  Only overwrites NULL fields.

    Returns True if at least one field was filled.
    """
    import json
    import os
    from datetime import UTC, datetime

    import anthropic

    from app.models.recruiter_job import RecruiterJob

    session = get_session_factory()()
    try:
        job = session.get(RecruiterJob, job_id)
        if not job:
            logger.warning("backfill_recruiter_job_fields: job %s not found", job_id)
            return False

        # Skip if both fields already present
        if job.job_id_external and job.closes_at:
            return False

        text = (
            f"Title: {job.title or ''}\n"
            f"Description: {(job.description or '')[:4000]}\n"
            f"Requirements: {(job.requirements or '')[:2000]}"
        ).strip()
        if len(text) < 20:
            return False

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("backfill_recruiter_job_fields: ANTHROPIC_API_KEY not set")
            return False

        client = anthropic.Anthropic(api_key=api_key, max_retries=2)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Extract ONLY these two fields from this job posting. "
                        "Return ONLY valid JSON.\n\n"
                        '{"job_id_external": "solicitation number / RFQ / '
                        'task order / req ID / posting number or null", '
                        '"close_date": "YYYY-MM-DD application deadline '
                        'or null"}\n\n'
                        "Rules:\n"
                        "- Search the ENTIRE text for any identifying number\n"
                        "- For close_date look for: deadline, closing date, "
                        "response date, due date, submit by\n"
                        "- Return null if not found — do NOT fabricate\n\n"
                        f"Job posting:\n{text}"
                    ),
                }
            ],
        )

        raw = response.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)
        updated = False

        if not job.job_id_external and data.get("job_id_external"):
            job.job_id_external = str(data["job_id_external"])[:100]
            updated = True

        if not job.closes_at and data.get("close_date"):
            try:
                d = datetime.strptime(data["close_date"], "%Y-%m-%d").date()
                job.closes_at = datetime(
                    d.year, d.month, d.day, tzinfo=UTC
                )
                updated = True
            except (ValueError, TypeError):
                pass

        if updated:
            session.commit()
            logger.info(
                "backfill_recruiter_job_fields: job %s — "
                "id_ext=%s closes_at=%s",
                job_id,
                job.job_id_external,
                job.closes_at,
            )

        return updated
    except Exception:
        session.rollback()
        logger.exception(
            "backfill_recruiter_job_fields: failed for job %s", job_id
        )
        return False
    finally:
        session.close()


def sync_employer_job_to_jobs(job_id: int) -> None:
    """Sync an employer job into the main jobs table as a proxy row.

    Creates or updates a Job with ``source='employer'`` so that
    ``compute_matches()`` picks it up for Starter+ candidates.
    """
    import hashlib

    from app.models.employer import EmployerJob, EmployerProfile

    session = get_session_factory()()
    try:
        ej = session.get(EmployerJob, job_id)
        if not ej:
            logger.warning(
                "sync_employer_job_to_jobs: EmployerJob %s not found", job_id
            )
            return

        ep = session.get(EmployerProfile, ej.employer_id)
        company = (ep.company_name if ep else None) or "Unknown"

        desc = (ej.description or "") + "\n" + (ej.requirements or "")
        content_hash = hashlib.sha256(desc.encode()).hexdigest()

        proxy = session.execute(
            select(Job).where(Job.employer_job_id == job_id)
        ).scalar_one_or_none()

        if proxy is None:
            proxy = Job(
                source="employer",
                source_job_id=f"employer_{job_id}",
                employer_job_id=job_id,
            )
            session.add(proxy)

        proxy.title = ej.title
        proxy.company = company
        proxy.location = ej.location or "Remote"
        proxy.remote_flag = (ej.remote_policy or "").lower() == "remote"
        proxy.salary_min = ej.salary_min
        proxy.salary_max = ej.salary_max
        proxy.currency = ej.salary_currency or "USD"
        proxy.description_text = desc.strip()
        proxy.content_hash = content_hash
        proxy.url = ej.application_url or ""
        proxy.posted_at = ej.posted_at or ej.created_at
        proxy.is_active = True

        # Generate embedding
        try:
            text = prepare_job_text(proxy)
            proxy.embedding = generate_embedding(text)
        except Exception:
            logger.warning("sync_employer_job_to_jobs: embedding failed for %s", job_id)

        session.commit()
        logger.info("sync_employer_job_to_jobs: synced employer job %s", job_id)
    except Exception:
        session.rollback()
        logger.exception("sync_employer_job_to_jobs: failed for %s", job_id)
    finally:
        session.close()


def deactivate_employer_job_proxy(job_id: int) -> None:
    """Mark the proxy Job row as inactive when an employer job is closed/archived."""
    session = get_session_factory()()
    try:
        proxy = session.execute(
            select(Job).where(Job.employer_job_id == job_id)
        ).scalar_one_or_none()
        if proxy:
            proxy.is_active = False
            session.commit()
            logger.info(
                "deactivate_employer_job_proxy: deactivated proxy for employer job %s",
                job_id,
            )
    except Exception:
        session.rollback()
        logger.exception("deactivate_employer_job_proxy: failed for %s", job_id)
    finally:
        session.close()


def populate_job_candidates(job_id: int) -> None:
    """Background job: compute and cache candidate matches for an employer job."""
    from sqlalchemy import delete as sa_delete

    from app.models.employer import EmployerJob
    from app.models.employer_job_candidate import EmployerJobCandidate
    from app.services.matching import find_top_candidates_for_employer_job

    session = get_session_factory()()
    try:
        job = session.get(EmployerJob, job_id)
        if not job:
            logger.warning("populate_job_candidates: EmployerJob %s not found", job_id)
            return

        results = find_top_candidates_for_employer_job(session, job)

        session.execute(
            sa_delete(EmployerJobCandidate).where(
                EmployerJobCandidate.employer_job_id == job_id
            )
        )

        inserted = 0
        for r in results:
            if r["match_score"] <= 50:
                continue
            session.add(
                EmployerJobCandidate(
                    employer_job_id=job_id,
                    candidate_profile_id=r["id"],
                    match_score=r["match_score"],
                    matched_skills=r.get("matched_skills"),
                )
            )
            inserted += 1

        session.commit()
        logger.info(
            "populate_job_candidates: employer job %s — %s candidates cached",
            job_id,
            inserted,
        )
    except Exception:
        session.rollback()
        logger.exception("populate_job_candidates: failed for employer job %s", job_id)
    finally:
        session.close()


def sync_recruiter_job_to_jobs(job_id: int) -> None:
    """Sync a recruiter job into the main jobs table as a proxy row.

    Creates or updates a Job with ``source='recruiter'`` so that
    ``compute_matches()`` picks it up for Pro candidates.
    """
    import hashlib

    from app.models.recruiter import RecruiterProfile
    from app.models.recruiter_job import RecruiterJob

    session = get_session_factory()()
    try:
        rj = session.get(RecruiterJob, job_id)
        if not rj:
            logger.warning(
                "sync_recruiter_job_to_jobs: RecruiterJob %s not found", job_id
            )
            return

        rp = session.get(RecruiterProfile, rj.recruiter_profile_id)
        company = (
            rj.client_company_name or (rp.company_name if rp else None) or "Unknown"
        )

        desc = (rj.description or "") + "\n" + (rj.requirements or "")
        content_hash = hashlib.sha256(desc.encode()).hexdigest()

        proxy = session.execute(
            select(Job).where(Job.recruiter_job_id == job_id)
        ).scalar_one_or_none()

        if proxy is None:
            proxy = Job(
                source="recruiter",
                source_job_id=f"recruiter_{job_id}",
                recruiter_job_id=job_id,
            )
            session.add(proxy)

        proxy.title = rj.title
        proxy.company = company
        proxy.location = rj.location or "Remote"
        proxy.remote_flag = (rj.remote_policy or "").lower() == "remote"
        proxy.salary_min = rj.salary_min
        proxy.salary_max = rj.salary_max
        proxy.currency = rj.salary_currency or "USD"
        proxy.description_text = desc.strip()
        proxy.content_hash = content_hash
        proxy.url = rj.application_url or ""
        proxy.posted_at = rj.posted_at or rj.created_at
        proxy.is_active = True

        # Generate embedding
        try:
            text = prepare_job_text(proxy)
            proxy.embedding = generate_embedding(text)
        except Exception:
            logger.warning(
                "sync_recruiter_job_to_jobs: embedding failed for %s", job_id
            )

        session.commit()
        logger.info("sync_recruiter_job_to_jobs: synced recruiter job %s", job_id)
    except Exception:
        session.rollback()
        logger.exception("sync_recruiter_job_to_jobs: failed for %s", job_id)
    finally:
        session.close()


def deactivate_recruiter_job_proxy(job_id: int) -> None:
    """Mark the proxy Job row as inactive when a recruiter job is closed."""
    session = get_session_factory()()
    try:
        proxy = session.execute(
            select(Job).where(Job.recruiter_job_id == job_id)
        ).scalar_one_or_none()
        if proxy:
            proxy.is_active = False
            session.commit()
            logger.info(
                "deactivate_recruiter_job_proxy: deactivated proxy for recruiter job"
                " %s",
                job_id,
            )
    except Exception:
        session.rollback()
        logger.exception("deactivate_recruiter_job_proxy: failed for %s", job_id)
    finally:
        session.close()


def parse_board_job_skills(job_id: int) -> bool:
    """Use a cheap LLM call to extract skills for a job with few taxonomy matches.

    Only called for jobs where regex+taxonomy parsing found < 3 skills.
    Uses Claude Haiku for minimal cost (~$0.001/job).
    """
    import json
    import os

    import anthropic

    session = get_session_factory()()
    try:
        job = session.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
        if job is None:
            logger.warning("parse_board_job_skills: job %s not found", job_id)
            return False

        parsed = session.execute(
            select(JobParsedDetail).where(JobParsedDetail.job_id == job_id)
        ).scalar_one_or_none()
        if parsed is None:
            logger.warning("parse_board_job_skills: no parsed detail for job %s", job_id)
            return False

        # Skip if already has enough skills
        existing_skills = (parsed.required_skills or []) + (parsed.preferred_skills or [])
        if len(existing_skills) >= 6:
            return True

        description = (job.description_text or "")[:3000]  # Cap to limit tokens
        if not description.strip():
            return False

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("parse_board_job_skills: ANTHROPIC_API_KEY not set")
            return False

        client = anthropic.Anthropic(api_key=api_key, max_retries=2)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Extract the required and preferred technical skills from this "
                        "job posting. Return ONLY a JSON object with two arrays:\n"
                        '{"required_skills": [...], "preferred_skills": [...]}\n\n'
                        "Rules:\n"
                        "- Include programming languages, frameworks, tools, platforms\n"
                        "- Use canonical names (e.g., 'JavaScript' not 'JS')\n"
                        "- Do NOT include soft skills or vague terms\n"
                        "- Max 15 skills per category\n\n"
                        f"Job posting:\n{description}"
                    ),
                }
            ],
        )

        text = response.content[0].text.strip()
        # Extract JSON from response (handle markdown code blocks)
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        data = json.loads(text)
        from app.services.skill_taxonomy import normalize_skills

        req = normalize_skills(
            [s for s in data.get("required_skills", []) if isinstance(s, str)][:15]
        )
        pref = normalize_skills(
            [s for s in data.get("preferred_skills", []) if isinstance(s, str)][:15]
        )

        if req or pref:
            parsed.required_skills = req
            parsed.preferred_skills = pref
            session.commit()
            logger.info(
                "parse_board_job_skills: job %s — %d required, %d preferred skills",
                job_id, len(req), len(pref),
            )
        return True
    except Exception:
        session.rollback()
        logger.exception("parse_board_job_skills: failed for job %s", job_id)
        return False
    finally:
        session.close()


def backfill_board_job_parsing() -> dict:
    """Backfill regex+taxonomy parsing for all board jobs missing JobParsedDetail.

    Returns stats on how many jobs were parsed and how many need LLM enrichment.
    """
    from app.services.job_parser import JobParserService
    from app.services.queue import get_queue

    session = get_session_factory()()
    try:
        # Find board jobs without parsed details
        parsed_job_ids = select(JobParsedDetail.job_id)
        jobs = session.execute(
            select(Job).where(
                Job.source.not_in(["employer", "recruiter"]),
                Job.id.not_in(parsed_job_ids),
                Job.is_active.is_not(False),
            )
        ).scalars().all()

        parser = JobParserService()
        parsed_count = 0
        low_skill_count = 0
        q = get_queue()

        for job in jobs:
            try:
                detail = parser.parse(session, job)
                parsed_count += 1

                # Queue LLM enrichment if taxonomy found < 3 skills
                total_skills = len(detail.required_skills or []) + len(
                    detail.preferred_skills or []
                )
                if total_skills < 6:
                    try:
                        q.enqueue(
                            "app.services.job_pipeline.parse_board_job_skills",
                            job.id,
                        )
                        low_skill_count += 1
                    except Exception:
                        pass

                if parsed_count % 50 == 0:
                    session.commit()
                    logger.info(
                        "backfill_board_job_parsing: %d jobs parsed so far",
                        parsed_count,
                    )
            except Exception:
                logger.debug(
                    "backfill_board_job_parsing: failed for job %s",
                    job.id,
                    exc_info=True,
                )

        session.commit()
        logger.info(
            "backfill_board_job_parsing: done — %d parsed, %d queued for LLM",
            parsed_count,
            low_skill_count,
        )
        return {
            "total_missing": len(jobs),
            "parsed": parsed_count,
            "queued_for_llm": low_skill_count,
        }
    except Exception:
        session.rollback()
        logger.exception("backfill_board_job_parsing: failed")
        return {"error": "backfill failed"}
    finally:
        session.close()
