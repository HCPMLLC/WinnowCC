from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobParsedDetail(Base):
    __tablename__ = "job_parsed_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Title / Role
    normalized_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seniority_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estimated_duration_months: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    # Location
    parsed_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parsed_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parsed_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    work_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    travel_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relocation_offered: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Compensation
    parsed_salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parsed_salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parsed_salary_currency: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )
    parsed_salary_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    salary_confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    benefits_mentioned: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Requirements
    required_skills: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    preferred_skills: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    required_certifications: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    required_education: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    years_experience_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    years_experience_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tools_and_technologies: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    raw_responsibilities: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    raw_qualifications: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Company Intelligence
    inferred_industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_size_signal: Mapped[str | None] = mapped_column(String(50), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reports_to: Mapped[str | None] = mapped_column(String(100), nullable=True)
    team_size: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Quality & Fraud
    posting_quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fraud_score: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    is_likely_fraudulent: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, default=False
    )
    red_flags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    culture_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Dedup
    is_duplicate_of_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_stale: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)

    # Meta
    parse_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parsed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
