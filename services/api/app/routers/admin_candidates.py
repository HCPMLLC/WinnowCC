from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.candidate_trust import CandidateTrust
from app.models.job import Job
from app.models.job_run import JobRun
from app.models.match import Match
from app.models.resume_document import ResumeDocument
from app.models.tailored_resume import TailoredResume
from app.models.trust_audit_log import TrustAuditLog
from app.models.user import User
from app.routers.matches import (
    _deduplicate_matches,
    _latest_profile_version,
    _refresh_skill_analysis,
)
from app.schemas.matches import MatchResponse
from app.schemas.tailor import TailoredDocumentResponse
from app.services.auth import require_admin_user
from app.services.cascade_delete import cascade_delete_user
from app.services.location_utils import normalize_city, normalize_state
from app.services.storage import file_response_path, is_gcs_path


class AdminCandidateResponse(BaseModel):
    user_id: int
    full_name: str | None
    first_name: str | None
    last_name: str | None
    title: str | None
    city: str | None
    state: str | None
    location: str | None
    work_authorization: str | None
    years_experience: int | None
    email: str | None
    phone: str | None
    date_added: str | None
    date_modified: str | None
    trust_status: str | None
    match_count: int
    resume_document_id: int | None
    resume_filename: str | None


ALLOWED_ROLES = {"candidate", "employer", "recruiter", "both", "admin"}


class AdminUserRoleUpdate(BaseModel):
    role: str | None = None
    is_admin: bool | None = None


class AdminUserRoleResponse(BaseModel):
    user_id: int
    email: str
    role: str
    is_admin: bool


class DeleteCandidatesRequest(BaseModel):
    user_ids: list[int]


class DeleteCandidatesResponse(BaseModel):
    deleted_count: int
    message: str


class MergeCandidatesRequest(BaseModel):
    primary_user_id: int
    duplicate_user_ids: list[int]


class MergeCandidatesResponse(BaseModel):
    merged_count: int
    message: str


router = APIRouter(prefix="/api/admin/candidates", tags=["admin-candidates"])


@router.get("", response_model=list[AdminCandidateResponse])
def get_all_candidates(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> list[AdminCandidateResponse]:
    """
    Get all candidates with their latest profile data.
    Sorted by last name ascending.
    """
    # Subquery to get latest profile version for each user
    latest_version_subq = (
        select(
            CandidateProfile.user_id,
            func.max(CandidateProfile.version).label("max_version"),
        )
        .where(CandidateProfile.user_id.isnot(None))
        .group_by(CandidateProfile.user_id)
        .subquery()
    )

    # Get latest profiles joined with users
    stmt = (
        select(CandidateProfile, User)
        .join(
            latest_version_subq,
            (CandidateProfile.user_id == latest_version_subq.c.user_id)
            & (CandidateProfile.version == latest_version_subq.c.max_version),
        )
        .join(User, CandidateProfile.user_id == User.id)
    )

    results = session.execute(stmt).all()

    # Get match counts for all users in a single query
    match_count_rows = session.execute(
        select(Match.user_id, func.count(Match.id))
        .group_by(Match.user_id)
    ).all()
    match_count_map: dict[int, int] = {uid: cnt for uid, cnt in match_count_rows}

    # Get trust statuses and resume info for all users
    trust_map: dict[int, str] = {}
    resume_map: dict[int, tuple[int, str]] = {}  # user_id -> (doc_id, filename)
    for _profile, user in results:
        # Look up resume by user_id (resumes are linked directly via user_id)
        resume_stmt = (
            select(ResumeDocument)
            .where(ResumeDocument.user_id == user.id)
            .order_by(ResumeDocument.created_at.desc())
            .limit(1)
        )
        resume_doc = session.execute(resume_stmt).scalar_one_or_none()
        if resume_doc:
            resume_map[user.id] = (resume_doc.id, resume_doc.filename)
            # Get trust status for this resume document
            trust_stmt = select(CandidateTrust).where(
                CandidateTrust.resume_document_id == resume_doc.id
            )
            trust = session.execute(trust_stmt).scalar_one_or_none()
            if trust:
                trust_map[user.id] = trust.status

    candidates = []
    for profile, user in results:
        profile_json = profile.profile_json or {}
        basics = profile_json.get("basics", {})
        experience = profile_json.get("experience", [])

        # Get name fields — support both "basics" nested and flat structures
        first_name = basics.get("first_name")
        last_name = basics.get("last_name")
        full_name = basics.get("name") or profile_json.get("name")
        if not first_name and full_name:
            # Parse first/last from full name (strip credentials after comma)
            clean = full_name.split(",")[0].strip()
            name_parts = clean.split()
            if name_parts:
                first_name = name_parts[0]
                last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else None
        if not full_name:
            full_name = (
                f"{first_name or ''} {last_name or ''}".strip() or None
            )

        # Get title from most recent experience, or from headline
        title = None
        if experience and len(experience) > 0:
            title = experience[0].get("title")
        if not title:
            title = basics.get("headline") or profile_json.get("headline")

        # Parse location into city and state — support both structures
        location = (
            basics.get("location")
            or profile_json.get("location")
            or ""
        )
        city = None
        state = None
        if location:
            parts = [p.strip() for p in location.split(",")]
            if len(parts) >= 2:
                city = normalize_city(parts[0])
                state = normalize_state(parts[1]) or parts[1]
            elif len(parts) == 1:
                city = normalize_city(parts[0])

        # Get resume info
        resume_info = resume_map.get(user.id)
        resume_doc_id = resume_info[0] if resume_info else None
        resume_filename = resume_info[1] if resume_info else None

        candidates.append(
            AdminCandidateResponse(
                user_id=user.id,
                full_name=full_name,
                first_name=first_name,
                last_name=last_name,
                title=title,
                city=city,
                state=state,
                location=location,
                work_authorization=basics.get("work_authorization"),
                years_experience=(
                    basics.get("total_years_experience")
                    or profile_json.get("total_years_experience")
                ),
                email=(
                    basics.get("email")
                    or (profile_json.get("contact_info") or {}).get("email")
                    or user.email
                ),
                phone=(
                    basics.get("phone")
                    or (profile_json.get("contact_info") or {}).get("phone")
                ),
                date_added=user.created_at.isoformat() if user.created_at else None,
                date_modified=profile.updated_at.isoformat()
                if profile.updated_at
                else None,
                trust_status=trust_map.get(user.id),
                match_count=match_count_map.get(user.id, 0),
                resume_document_id=resume_doc_id,
                resume_filename=resume_filename,
            )
        )

    # Sort by last name (case-insensitive), then first name
    candidates.sort(
        key=lambda c: (
            (c.last_name or "").lower(),
            (c.first_name or "").lower(),
        )
    )

    return candidates


@router.post("/delete", response_model=DeleteCandidatesResponse)
def delete_candidates(
    payload: DeleteCandidatesRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> DeleteCandidatesResponse:
    """
    Delete one or more candidates and all their associated data.
    """
    if not payload.user_ids:
        raise HTTPException(status_code=400, detail="No user IDs provided.")

    deleted_count = 0
    for user_id in payload.user_ids:
        if cascade_delete_user(session, user_id):
            deleted_count += 1

    session.commit()

    return DeleteCandidatesResponse(
        deleted_count=deleted_count,
        message=f"Successfully deleted {deleted_count} candidate(s).",
    )


@router.post("/merge", response_model=MergeCandidatesResponse)
def merge_candidates(
    payload: MergeCandidatesRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> MergeCandidatesResponse:
    """
    Merge duplicate candidates into a primary candidate.
    Keeps the primary user and transfers data from duplicates before deleting them.
    """
    if not payload.duplicate_user_ids:
        raise HTTPException(status_code=400, detail="No duplicate user IDs provided.")

    primary_user = session.get(User, payload.primary_user_id)
    if primary_user is None:
        raise HTTPException(status_code=404, detail="Primary user not found.")

    merged_count = 0
    for dup_user_id in payload.duplicate_user_ids:
        if dup_user_id == payload.primary_user_id:
            continue  # Skip if same as primary

        dup_user = session.get(User, dup_user_id)
        if dup_user is None:
            continue

        # Transfer tailored resumes to primary user
        session.execute(
            select(TailoredResume).where(TailoredResume.user_id == dup_user_id)
        )
        for tr in (
            session.execute(
                select(TailoredResume).where(TailoredResume.user_id == dup_user_id)
            )
            .scalars()
            .all()
        ):
            tr.user_id = payload.primary_user_id

        # Transfer matches to primary user
        for match in (
            session.execute(select(Match).where(Match.user_id == dup_user_id))
            .scalars()
            .all()
        ):
            match.user_id = payload.primary_user_id

        # Handle resume documents and their related data
        resume_docs = (
            session.execute(
                select(ResumeDocument).where(ResumeDocument.user_id == dup_user_id)
            )
            .scalars()
            .all()
        )
        for doc in resume_docs:
            # Transfer job runs to primary user's context
            session.execute(delete(JobRun).where(JobRun.resume_document_id == doc.id))
            # Handle trust records
            trust = session.execute(
                select(CandidateTrust).where(
                    CandidateTrust.resume_document_id == doc.id
                )
            ).scalar_one_or_none()
            if trust:
                # Delete audit log entries first
                session.execute(
                    delete(TrustAuditLog).where(TrustAuditLog.trust_id == trust.id)
                )
                # Delete trust record
                session.execute(
                    delete(CandidateTrust).where(CandidateTrust.id == trust.id)
                )
            # Transfer resume document to primary user
            doc.user_id = payload.primary_user_id

        # Transfer candidate profiles to primary user
        for profile in (
            session.execute(
                select(CandidateProfile).where(CandidateProfile.user_id == dup_user_id)
            )
            .scalars()
            .all()
        ):
            profile.user_id = payload.primary_user_id

        # Delete candidate (onboarding data) for duplicate user
        session.execute(delete(Candidate).where(Candidate.user_id == dup_user_id))

        # Delete duplicate user
        session.delete(dup_user)
        merged_count += 1

    session.commit()

    return MergeCandidatesResponse(
        merged_count=merged_count,
        message=f"Successfully merged {merged_count} duplicate(s) into primary user.",
    )


@router.patch("/{user_id}/role", response_model=AdminUserRoleResponse)
def update_user_role(
    user_id: int,
    payload: AdminUserRoleUpdate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> AdminUserRoleResponse:
    """Update a user's role and/or admin flag (admin only)."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    if payload.role is not None:
        if payload.role not in ALLOWED_ROLES:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid role. Must be one of: {', '.join(sorted(ALLOWED_ROLES))}",
            )
        user.role = payload.role

    if payload.is_admin is not None:
        user.is_admin = payload.is_admin

    session.commit()
    session.refresh(user)

    return AdminUserRoleResponse(
        user_id=user.id,
        email=user.email,
        role=user.role,
        is_admin=user.is_admin,
    )


def _cleanup_temp(path: Path, stored_path: str) -> None:
    """Remove temp file only if it was downloaded from GCS."""
    if is_gcs_path(stored_path):
        path.unlink(missing_ok=True)


@router.get("/resume/{resume_id}")
def get_resume_file(
    resume_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> FileResponse:
    """
    Download/view a candidate's resume file (admin only).
    """
    resume = session.get(ResumeDocument, resume_id)
    if resume is None or not resume.path:
        raise HTTPException(status_code=404, detail="Resume not found.")

    try:
        suffix = Path(resume.path).suffix if not is_gcs_path(resume.path) else Path(resume.filename).suffix
        local_path = file_response_path(resume.path, suffix=suffix)
    except Exception:
        raise HTTPException(status_code=404, detail="Resume file not found.")

    if not local_path.exists():
        raise HTTPException(status_code=404, detail="Resume file not found on disk.")

    extension = local_path.suffix.lower()
    media_type = (
        "application/pdf"
        if extension == ".pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    background_tasks.add_task(_cleanup_temp, local_path, resume.path)
    return FileResponse(
        path=local_path,
        filename=resume.filename,
        media_type=media_type,
    )


# --- Dynamic /{user_id}/... routes (must come after static-prefix routes) ---


@router.get("/{user_id}/matches", response_model=list[MatchResponse])
def get_candidate_matches(
    user_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> list[MatchResponse]:
    """Get all deduplicated matches for a candidate (admin only)."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    stmt = (
        select(Match, Job)
        .join(Job, Match.job_id == Job.id)
        .where(
            Match.user_id == user_id,
            Job.is_active.is_not(False),
        )
        .order_by(
            Match.interview_probability.desc().nulls_last(),
            Match.match_score.desc(),
        )
    )
    rows = session.execute(stmt).all()

    jobs_by_id = {job.id: job for _, job in rows}

    profile_version = _latest_profile_version(session, user_id)
    profile = session.execute(
        select(CandidateProfile).where(
            CandidateProfile.user_id == user_id,
            CandidateProfile.version == profile_version,
        )
    ).scalar_one_or_none()
    profile_json = profile.profile_json if profile else {}

    deduplicated = _deduplicate_matches(rows)
    return _refresh_skill_analysis(deduplicated, profile_json, jobs_by_id)


@router.get("/{user_id}/documents", response_model=list[TailoredDocumentResponse])
def get_candidate_documents(
    user_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> list[TailoredDocumentResponse]:
    """Get all tailored documents for a candidate (admin only)."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    matched_job_ids = set(
        session.execute(select(Match.job_id).where(Match.user_id == user_id))
        .scalars()
        .all()
    )

    stmt = (
        select(TailoredResume, Job)
        .join(Job, TailoredResume.job_id == Job.id)
        .where(TailoredResume.user_id == user_id)
        .order_by(TailoredResume.created_at.desc())
    )
    results = session.execute(stmt).all()

    documents = []
    for tailored, job in results:
        has_active_match = job.id in matched_job_ids
        documents.append(
            TailoredDocumentResponse(
                id=tailored.id,
                job_id=job.id,
                job_title=job.title,
                company=job.company,
                resume_url=(
                    f"/api/admin/candidates/{user_id}/documents/{tailored.id}/resume"
                ),
                cover_letter_url=(
                    f"/api/admin/candidates/{user_id}"
                    f"/documents/{tailored.id}/cover-letter"
                ),
                created_at=tailored.created_at,
                has_active_match=has_active_match,
            )
        )
    return documents


@router.get("/{user_id}/documents/{doc_id}/resume")
def download_candidate_resume(
    user_id: int,
    doc_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> FileResponse:
    """Download a tailored resume for a candidate (admin only)."""
    tailored = session.get(TailoredResume, doc_id)
    if tailored is None or tailored.user_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found.")
    if not tailored.docx_url:
        raise HTTPException(status_code=404, detail="File not found.")
    try:
        path = file_response_path(tailored.docx_url, suffix=".docx")
    except Exception:
        raise HTTPException(status_code=404, detail="File not found.")
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk.")
    background_tasks.add_task(_cleanup_temp, path, tailored.docx_url)
    return FileResponse(path, filename=path.name)


@router.get("/{user_id}/documents/{doc_id}/cover-letter")
def download_candidate_cover_letter(
    user_id: int,
    doc_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> FileResponse:
    """Download a tailored cover letter for a candidate (admin only)."""
    tailored = session.get(TailoredResume, doc_id)
    if tailored is None or tailored.user_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found.")
    if not tailored.cover_letter_url:
        raise HTTPException(status_code=404, detail="File not found.")
    try:
        path = file_response_path(tailored.cover_letter_url, suffix=".docx")
    except Exception:
        raise HTTPException(status_code=404, detail="File not found.")
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk.")
    background_tasks.add_task(_cleanup_temp, path, tailored.cover_letter_url)
    return FileResponse(path, filename=path.name)
