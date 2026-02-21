"""
Database Models for Intelligent Resume Parser
==============================================

SQLAlchemy models for storing parsed resume data with skill categorization
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SkillCategoryEnum(str, enum.Enum):
    """Skill categorization"""

    CORE = "core"
    TECHNICAL = "technical"
    ENVIRONMENTAL = "environmental"
    SOFT = "soft"


class ParsedResumeDocument(Base):
    """Main table for parsed resume data"""

    __tablename__ = "parsed_resume_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("resume_documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Candidate basic info
    candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Professional summary
    professional_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Parsing metadata
    parsed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    parser_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    total_jobs_extracted: Mapped[int] = mapped_column(Integer, default=0)
    total_skills_extracted: Mapped[int] = mapped_column(Integer, default=0)
    core_skills_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    job_experiences: Mapped[list["JobExperience"]] = relationship(
        "JobExperience", back_populates="resume", cascade="all, delete-orphan"
    )
    skills: Mapped[list["ExtractedSkill"]] = relationship(
        "ExtractedSkill", back_populates="resume", cascade="all, delete-orphan"
    )
    certifications: Mapped[list["ParsedCertification"]] = relationship(
        "ParsedCertification", back_populates="resume", cascade="all, delete-orphan"
    )
    education_records: Mapped[list["ParsedEducation"]] = relationship(
        "ParsedEducation", back_populates="resume", cascade="all, delete-orphan"
    )


class JobExperience(Base):
    """Individual job/position from resume"""

    __tablename__ = "job_experiences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parsed_resume_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("parsed_resume_documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Job details
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Responsibilities
    duties: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Environment/context
    environment_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    technologies_used: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Order in resume (for maintaining sequence)
    position_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    resume: Mapped["ParsedResumeDocument"] = relationship(
        "ParsedResumeDocument", back_populates="job_experiences"
    )
    accomplishments: Mapped[list["QuantifiedAccomplishment"]] = relationship(
        "QuantifiedAccomplishment", back_populates="job", cascade="all, delete-orphan"
    )
    job_skills: Mapped[list["JobSkillUsage"]] = relationship(
        "JobSkillUsage", back_populates="job", cascade="all, delete-orphan"
    )


class QuantifiedAccomplishment(Base):
    """Measurable achievements from job experience"""

    __tablename__ = "quantified_accomplishments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_experience_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("job_experiences.id", ondelete="CASCADE"), nullable=False
    )

    # Achievement details
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    impact_category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    job: Mapped["JobExperience"] = relationship(
        "JobExperience", back_populates="accomplishments"
    )


class ExtractedSkill(Base):
    """All skills extracted from resume with categorization"""

    __tablename__ = "extracted_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parsed_resume_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("parsed_resume_documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Skill details
    skill_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # core, technical, environmental, soft
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5)
    extraction_source: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Years of experience (can be calculated from job history)
    years_experience: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    resume: Mapped["ParsedResumeDocument"] = relationship(
        "ParsedResumeDocument", back_populates="skills"
    )


class JobSkillUsage(Base):
    """Skills used in specific job (many-to-many relationship)"""

    __tablename__ = "job_skill_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_experience_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("job_experiences.id", ondelete="CASCADE"), nullable=False
    )
    skill_name: Mapped[str] = mapped_column(String(255), nullable=False)
    skill_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    job: Mapped["JobExperience"] = relationship(
        "JobExperience", back_populates="job_skills"
    )


class ParsedCertification(Base):
    """Professional certifications"""

    __tablename__ = "parsed_certifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parsed_resume_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("parsed_resume_documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    certification_name: Mapped[str] = mapped_column(String(255), nullable=False)
    issuing_organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issue_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expiration_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    credential_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    resume: Mapped["ParsedResumeDocument"] = relationship(
        "ParsedResumeDocument", back_populates="certifications"
    )


class ParsedEducation(Base):
    """Educational background"""

    __tablename__ = "parsed_education"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parsed_resume_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("parsed_resume_documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    degree: Mapped[str | None] = mapped_column(String(255), nullable=True)
    field_of_study: Mapped[str | None] = mapped_column(String(255), nullable=True)
    institution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    graduation_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gpa: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relationships
    resume: Mapped["ParsedResumeDocument"] = relationship(
        "ParsedResumeDocument", back_populates="education_records"
    )
