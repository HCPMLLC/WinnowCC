from __future__ import annotations

from app.db.session import get_session_factory
from app.services.job_ingestion import ingest_jobs
from app.services.matching import compute_matches
from app.services.tailor import create_tailored_docs


def ingest_jobs_job(query: dict) -> int:
    session = get_session_factory()()
    try:
        return ingest_jobs(session, query)
    finally:
        session.close()


def match_jobs_job(user_id: int, profile_version: int) -> int:
    session = get_session_factory()()
    try:
        matches = compute_matches(session, user_id, profile_version)
        return len(matches)
    finally:
        session.close()


def tailor_job(user_id: int, job_id: int, profile_version: int) -> int:
    session = get_session_factory()()
    try:
        tailored = create_tailored_docs(session, user_id, job_id, profile_version)
        return tailored.id
    finally:
        session.close()
