"""Distribution API endpoints for multi-board job distribution."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.distribution import BoardConnection, JobDistribution
from app.models.employer import EmployerJob, EmployerProfile
from app.schemas.employer import (
    BoardConnectionCreate,
    BoardConnectionResponse,
    BoardConnectionUpdate,
    ConnectionTestResponse,
    DistributeJobRequest,
    JobDistributionResponse,
)
from app.services.auth import get_employer_profile
from app.services.billing import get_employer_limit, get_employer_tier
from app.services.board_adapters import get_adapter
from app.services.distribution import (
    distribute_job,
    remove_from_boards,
    sync_all_metrics,
)

router = APIRouter(prefix="/api/distribution", tags=["distribution"])


# ============================================================================
# BOARD CONNECTIONS
# ============================================================================


@router.get("/connections", response_model=list[BoardConnectionResponse])
def list_connections(
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
):
    """List employer's board connections."""
    stmt = (
        select(BoardConnection)
        .where(BoardConnection.employer_id == employer.id)
        .order_by(BoardConnection.created_at.desc())
    )
    return list(session.execute(stmt).scalars().all())


@router.post(
    "/connections",
    response_model=BoardConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_connection(
    data: BoardConnectionCreate,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
):
    """Add a new board connection."""
    # Check uniqueness
    existing = session.execute(
        select(BoardConnection).where(
            BoardConnection.employer_id == employer.id,
            BoardConnection.board_type == data.board_type,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Connection for '{data.board_type}' already exists",
        )

    conn = BoardConnection(
        employer_id=employer.id,
        board_type=data.board_type,
        board_name=data.board_name,
        api_key_encrypted=data.api_key,
        api_secret_encrypted=data.api_secret,
        feed_url=data.feed_url,
        config=data.config,
    )
    session.add(conn)
    session.commit()
    session.refresh(conn)
    return conn


@router.put("/connections/{connection_id}", response_model=BoardConnectionResponse)
def update_connection(
    connection_id: int,
    data: BoardConnectionUpdate,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
):
    """Update a board connection's settings."""
    conn = session.execute(
        select(BoardConnection).where(
            BoardConnection.id == connection_id,
            BoardConnection.employer_id == employer.id,
        )
    ).scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    update_data = data.model_dump(exclude_unset=True)
    # Map schema field names to model field names
    if "api_key" in update_data:
        conn.api_key_encrypted = update_data.pop("api_key")
    if "api_secret" in update_data:
        conn.api_secret_encrypted = update_data.pop("api_secret")
    for key, value in update_data.items():
        setattr(conn, key, value)

    session.commit()
    session.refresh(conn)
    return conn


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    connection_id: int,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
):
    """Remove a board connection."""
    conn = session.execute(
        select(BoardConnection).where(
            BoardConnection.id == connection_id,
            BoardConnection.employer_id == employer.id,
        )
    ).scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    session.delete(conn)
    session.commit()


@router.post("/connections/{connection_id}/test", response_model=ConnectionTestResponse)
def test_connection(
    connection_id: int,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
):
    """Test/validate a board connection's credentials."""
    conn = session.execute(
        select(BoardConnection).where(
            BoardConnection.id == connection_id,
            BoardConnection.employer_id == employer.id,
        )
    ).scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    adapter = get_adapter(conn.board_type)
    if not adapter:
        return ConnectionTestResponse(
            valid=False,
            message=f"No adapter available for board type '{conn.board_type}'",
        )

    try:
        valid = adapter.validate_credentials(conn)
        return ConnectionTestResponse(
            valid=valid,
            message=(
                "Credentials are valid" if valid else "Credentials invalid or missing"
            ),
        )
    except Exception as e:
        return ConnectionTestResponse(valid=False, message=str(e)[:500])


# ============================================================================
# JOB DISTRIBUTION
# ============================================================================


@router.post("/jobs/{job_id}/distribute")
def distribute_job_endpoint(
    job_id: int,
    body: DistributeJobRequest | None = None,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
):
    """Distribute a job to boards."""
    # Verify job belongs to employer
    job = session.execute(
        select(EmployerJob).where(
            EmployerJob.id == job_id,
            EmployerJob.employer_id == employer.id,
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "active":
        raise HTTPException(
            status_code=400, detail="Only active jobs can be distributed"
        )

    board_types = body.board_types if body else None

    # Enforce multi_board_distribution tier allowlist
    tier = get_employer_tier(employer)
    allowed_boards = get_employer_limit(tier, "multi_board_distribution")
    if allowed_boards != "all" and isinstance(allowed_boards, list):
        if board_types:
            disallowed = [b for b in board_types if b not in allowed_boards]
            if disallowed:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        f"{tier.capitalize()} tier only allows distribution to: "
                        f"{', '.join(allowed_boards)}. Upgrade to distribute to: "
                        f"{', '.join(disallowed)}."
                    ),
                )
        else:
            # Filter default distribution to allowed boards only
            board_types = allowed_boards

    results = distribute_job(job_id, board_types, session)
    return {"distributed": len(results), "results": results}


@router.post("/jobs/{job_id}/remove")
def remove_job_endpoint(
    job_id: int,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
):
    """Remove a job from all boards."""
    job = session.execute(
        select(EmployerJob).where(
            EmployerJob.id == job_id,
            EmployerJob.employer_id == employer.id,
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    results = remove_from_boards(job_id, session)
    return {"removed": len(results), "results": results}


@router.get("/jobs/{job_id}/status")
def get_distribution_status(
    job_id: int,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
):
    """Get distribution status across all boards for a job."""
    # Verify ownership
    job = session.execute(
        select(EmployerJob).where(
            EmployerJob.id == job_id,
            EmployerJob.employer_id == employer.id,
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    stmt = (
        select(JobDistribution)
        .where(JobDistribution.employer_job_id == job_id)
        .order_by(JobDistribution.created_at.desc())
    )
    distributions = list(session.execute(stmt).scalars().all())

    items = []
    for dist in distributions:
        conn = session.get(BoardConnection, dist.board_connection_id)
        items.append(
            JobDistributionResponse(
                id=dist.id,
                employer_job_id=dist.employer_job_id,
                board_connection_id=dist.board_connection_id,
                external_job_id=dist.external_job_id,
                status=dist.status,
                submitted_at=dist.submitted_at,
                live_at=dist.live_at,
                removed_at=dist.removed_at,
                error_message=dist.error_message,
                impressions=dist.impressions,
                clicks=dist.clicks,
                applications=dist.applications,
                cost_spent=float(dist.cost_spent),
                created_at=dist.created_at,
                updated_at=dist.updated_at,
                board_type=conn.board_type if conn else None,
                board_name=conn.board_name if conn else None,
            )
        )

    return {"job_id": job_id, "distributions": items}


# ============================================================================
# CONTENT OPTIMIZATION & VALIDATION (P46)
# ============================================================================


@router.post("/jobs/{job_id}/preview/{board_type}")
def preview_optimized_content(
    job_id: int,
    board_type: str,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
):
    """Preview optimized content for a specific board without posting."""
    from app.services.content_optimizer import optimize_for_board

    job = session.execute(
        select(EmployerJob).where(
            EmployerJob.id == job_id,
            EmployerJob.employer_id == employer.id,
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return optimize_for_board(job, board_type)


@router.get("/jobs/{job_id}/bias-scan")
def bias_scan(
    job_id: int,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
):
    """Get bias scan results for a job posting."""
    from app.services.job_bias_scanner import scan_job_for_bias

    # Gate by bias_detection tier feature
    tier = get_employer_tier(employer)
    bias_level = get_employer_limit(tier, "bias_detection")
    if not bias_level:
        raise HTTPException(
            status_code=403,
            detail="Bias detection requires Starter or Pro plan.",
        )

    job = session.execute(
        select(EmployerJob).where(
            EmployerJob.id == job_id,
            EmployerJob.employer_id == employer.id,
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return scan_job_for_bias(job)


@router.get("/jobs/{job_id}/validation")
def validate_job(
    job_id: int,
    board_type: str | None = None,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
):
    """Get validation results for a job posting."""
    from app.services.posting_validator import validate_posting

    job = session.execute(
        select(EmployerJob).where(
            EmployerJob.id == job_id,
            EmployerJob.employer_id == employer.id,
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return validate_posting(job, board_type)


@router.post("/sync-metrics")
def sync_metrics_endpoint(
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
):
    """Trigger metrics sync for all active distributions."""
    results = sync_all_metrics(employer.id, session)
    return {"synced": len(results), "results": results}
