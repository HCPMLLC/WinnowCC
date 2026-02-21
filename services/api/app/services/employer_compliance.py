"""Employer compliance — audit logging, OFCCP reports, EEO summaries."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employer import EmployerJob

logger = logging.getLogger(__name__)


def log_compliance_event(
    employer_id: int,
    event_type: str,
    event_data: dict,
    job_id: int | None = None,
    user_id: int | None = None,
    ip_address: str | None = None,
    session: Session | None = None,
) -> None:
    """Log an auditable compliance event."""
    if not session:
        return

    from app.models.employer_compliance_log import EmployerComplianceLog

    log_entry = EmployerComplianceLog(
        employer_id=employer_id,
        employer_job_id=job_id,
        event_type=event_type,
        event_data=event_data,
        user_id=user_id,
        ip_address=ip_address,
    )
    session.add(log_entry)
    session.flush()


def get_compliance_log(
    employer_id: int,
    job_id: int | None = None,
    event_type: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    session: Session | None = None,
) -> list[dict]:
    """Retrieve compliance audit log entries."""
    from app.models.employer_compliance_log import EmployerComplianceLog

    if not session:
        return []

    stmt = (
        select(EmployerComplianceLog)
        .where(EmployerComplianceLog.employer_id == employer_id)
        .order_by(EmployerComplianceLog.created_at.desc())
    )

    if job_id:
        stmt = stmt.where(EmployerComplianceLog.employer_job_id == job_id)
    if event_type:
        stmt = stmt.where(EmployerComplianceLog.event_type == event_type)
    if start_date:
        stmt = stmt.where(EmployerComplianceLog.created_at >= start_date)
    if end_date:
        stmt = stmt.where(EmployerComplianceLog.created_at <= end_date)

    stmt = stmt.offset(offset).limit(limit)
    entries = list(session.execute(stmt).scalars().all())

    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "event_data": e.event_data,
            "employer_job_id": e.employer_job_id,
            "user_id": e.user_id,
            "created_at": (e.created_at.isoformat() if e.created_at else None),
        }
        for e in entries
    ]


def generate_ofccp_report(
    employer_id: int,
    start_date: datetime | None,
    end_date: datetime | None,
    session: Session,
) -> dict:
    """Generate OFCCP-ready audit report.

    Includes all job postings, distribution history, and candidate flow.
    """
    from app.models.distribution import JobDistribution

    # All jobs in date range
    job_stmt = select(EmployerJob).where(EmployerJob.employer_id == employer_id)
    if start_date:
        job_stmt = job_stmt.where(EmployerJob.created_at >= start_date)
    if end_date:
        job_stmt = job_stmt.where(EmployerJob.created_at <= end_date)
    jobs = list(session.execute(job_stmt).scalars().all())

    job_records = []
    for job in jobs:
        # Get distribution info
        dist_stmt = select(JobDistribution).where(
            JobDistribution.employer_job_id == job.id
        )
        distributions = list(session.execute(dist_stmt).scalars().all())

        job_records.append(
            {
                "job_id": job.id,
                "title": job.title,
                "status": job.status,
                "posted_at": (job.posted_at.isoformat() if job.posted_at else None),
                "closed_at": (
                    job.closed_at.isoformat()
                    if hasattr(job, "closed_at") and job.closed_at
                    else None
                ),
                "boards_distributed": [
                    {
                        "board_id": d.board_connection_id,
                        "status": d.status,
                        "submitted_at": (
                            d.submitted_at.isoformat() if d.submitted_at else None
                        ),
                    }
                    for d in distributions
                ],
                "applications": sum(d.applications or 0 for d in distributions),
            }
        )

    return {
        "employer_id": employer_id,
        "report_type": "ofccp",
        "generated_at": datetime.now(UTC).isoformat(),
        "date_range": {
            "start": start_date.isoformat() if start_date else None,
            "end": end_date.isoformat() if end_date else None,
        },
        "total_jobs": len(job_records),
        "jobs": job_records,
    }


def get_posting_compliance_status(
    employer_job_id: int,
    session: Session,
) -> dict:
    """Check a specific job's compliance status."""
    from app.services.job_bias_scanner import scan_job_for_bias
    from app.services.posting_validator import validate_posting

    job = session.get(EmployerJob, employer_job_id)
    if not job:
        return {"error": "Job not found"}

    validation = validate_posting(job)
    bias_scan = scan_job_for_bias(job)

    # Check posting duration
    posted_days = None
    if job.posted_at:
        posted_days = (datetime.now(UTC) - job.posted_at).days

    return {
        "job_id": employer_job_id,
        "validation": validation,
        "bias_scan": {
            "score": bias_scan["bias_score"],
            "flag_count": len(bias_scan["flags"]),
        },
        "posted_days": posted_days,
        "has_eeo": any(
            c["name"] == "eeo_statement" and c["status"] == "pass"
            for c in validation["checks"]
        ),
        "has_salary": bool(job.salary_min or job.salary_max),
    }


def check_government_compliance(
    employer_job_id: int,
    session: Session,
) -> dict:
    """Government-specific compliance checks (P51)."""
    job = session.get(EmployerJob, employer_job_id)
    if not job:
        return {"error": "Job not found"}

    checks = []

    # Veterans' preference (VEVRAA)
    desc = (job.description or "").lower()
    has_vevraa = "veteran" in desc or "vevraa" in desc
    checks.append(
        {
            "name": "vevraa",
            "status": "pass" if has_vevraa else "warn",
            "message": (
                "Veterans' preference language included"
                if has_vevraa
                else "Consider adding veterans' preference statement"
            ),
        }
    )

    # Section 503
    has_503 = "section 503" in desc or "disability" in desc
    checks.append(
        {
            "name": "section_503",
            "status": "pass" if has_503 else "warn",
            "message": (
                "Section 503 disability language included"
                if has_503
                else "Consider adding Section 503 compliance language"
            ),
        }
    )

    # Merit system principles
    has_merit = "merit" in desc
    checks.append(
        {
            "name": "merit_system",
            "status": "pass" if has_merit else "info",
            "message": (
                "Merit system language present"
                if has_merit
                else "Government positions should reference merit system principles"
            ),
        }
    )

    return {
        "job_id": employer_job_id,
        "government_checks": checks,
    }
