"""
Database Models for Intelligent Resume Parser
==============================================

SQLAlchemy models for storing parsed resume data with skill categorization
"""

import enum
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class SkillCategoryEnum(enum.Enum):
    """Skill categorization"""

    CORE = "core"
    TECHNICAL = "technical"
    ENVIRONMENTAL = "environmental"
    SOFT = "soft"


class ParsedResumeDocument(Base):
    """Main table for parsed resume data"""

    __tablename__ = "parsed_resume_documents"

    id = Column(Integer, primary_key=True)
    resume_document_id = Column(
        Integer, ForeignKey("resume_documents.id"), nullable=False, unique=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Candidate basic info
    candidate_name = Column(String(255))
    email = Column(String(255))
    phone = Column(String(50))
    location = Column(String(255))
    linkedin_url = Column(String(500))

    # Professional summary
    professional_summary = Column(Text)

    # Parsing metadata
    parsed_at = Column(DateTime, default=datetime.utcnow)
    parser_version = Column(String(20))
    total_jobs_extracted = Column(Integer, default=0)
    total_skills_extracted = Column(Integer, default=0)
    core_skills_count = Column(Integer, default=0)

    # Relationships
    job_experiences = relationship(
        "JobExperience", back_populates="resume", cascade="all, delete-orphan"
    )
    skills = relationship(
        "ExtractedSkill", back_populates="resume", cascade="all, delete-orphan"
    )
    certifications = relationship(
        "Certification", back_populates="resume", cascade="all, delete-orphan"
    )
    education_records = relationship(
        "Education", back_populates="resume", cascade="all, delete-orphan"
    )


class JobExperience(Base):
    """Individual job/position from resume"""

    __tablename__ = "job_experiences"

    id = Column(Integer, primary_key=True)
    parsed_resume_id = Column(
        Integer, ForeignKey("parsed_resume_documents.id"), nullable=False
    )

    # Job details
    company_name = Column(String(255), nullable=False)
    job_title = Column(String(255), nullable=False)
    start_date = Column(String(50))  # Flexible format: "January 2020", "2020", etc.
    end_date = Column(String(50))
    location = Column(String(255))

    # Responsibilities
    duties = Column(JSON)  # Array of duty strings

    # Environment/context
    environment_description = Column(Text)
    technologies_used = Column(JSON)  # Array of technology names

    # Order in resume (for maintaining sequence)
    position_order = Column(Integer, default=0)

    # Relationships
    resume = relationship("ParsedResumeDocument", back_populates="job_experiences")
    accomplishments = relationship(
        "QuantifiedAccomplishment", back_populates="job", cascade="all, delete-orphan"
    )
    job_skills = relationship(
        "JobSkillUsage", back_populates="job", cascade="all, delete-orphan"
    )


class QuantifiedAccomplishment(Base):
    """Measurable achievements from job experience"""

    __tablename__ = "quantified_accomplishments"

    id = Column(Integer, primary_key=True)
    job_experience_id = Column(
        Integer, ForeignKey("job_experiences.id"), nullable=False
    )

    # Achievement details
    description = Column(Text, nullable=False)
    metrics = Column(
        JSON
    )  # Array of extracted metrics (e.g., ["$294,000", "28,000/month"])
    impact_category = Column(
        String(50)
    )  # cost_savings, efficiency, quality, revenue_growth, delivery, other

    # Relationships
    job = relationship("JobExperience", back_populates="accomplishments")


class ExtractedSkill(Base):
    """All skills extracted from resume with categorization"""

    __tablename__ = "extracted_skills"

    id = Column(Integer, primary_key=True)
    parsed_resume_id = Column(
        Integer, ForeignKey("parsed_resume_documents.id"), nullable=False
    )

    # Skill details
    skill_name = Column(String(255), nullable=False)
    category = Column(SQLEnum(SkillCategoryEnum), nullable=False)
    confidence_score = Column(Float, default=0.5)  # 0.0 to 1.0
    extraction_source = Column(
        String(100)
    )  # explicit_skills_section, inferred_from_duties, inferred_from_title

    # Years of experience (can be calculated from job history)
    years_experience = Column(Float)

    # Relationships
    resume = relationship("ParsedResumeDocument", back_populates="skills")


class JobSkillUsage(Base):
    """Skills used in specific job (many-to-many relationship)"""

    __tablename__ = "job_skill_usage"

    id = Column(Integer, primary_key=True)
    job_experience_id = Column(
        Integer, ForeignKey("job_experiences.id"), nullable=False
    )
    skill_name = Column(String(255), nullable=False)
    skill_category = Column(SQLEnum(SkillCategoryEnum))
    confidence_score = Column(Float)

    # Relationships
    job = relationship("JobExperience", back_populates="job_skills")


class Certification(Base):
    """Professional certifications"""

    __tablename__ = "certifications"

    id = Column(Integer, primary_key=True)
    parsed_resume_id = Column(
        Integer, ForeignKey("parsed_resume_documents.id"), nullable=False
    )

    certification_name = Column(String(255), nullable=False)
    issuing_organization = Column(String(255))
    issue_date = Column(String(50))
    expiration_date = Column(String(50))
    credential_id = Column(String(100))

    # Relationships
    resume = relationship("ParsedResumeDocument", back_populates="certifications")


class Education(Base):
    """Educational background"""

    __tablename__ = "education_records"

    id = Column(Integer, primary_key=True)
    parsed_resume_id = Column(
        Integer, ForeignKey("parsed_resume_documents.id"), nullable=False
    )

    degree = Column(String(255))
    field_of_study = Column(String(255))
    institution = Column(String(255))
    graduation_date = Column(String(50))
    gpa = Column(String(20))

    # Relationships
    resume = relationship("ParsedResumeDocument", back_populates="education_records")


# Database schema SQL for reference
"""
-- Migration script to add parsed resume tables

CREATE TYPE skill_category AS ENUM ('core', 'technical', 'environmental', 'soft');

CREATE TABLE parsed_resume_documents (
    id SERIAL PRIMARY KEY,
    resume_document_id INTEGER NOT NULL UNIQUE
        REFERENCES resume_documents(id)
        ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    candidate_name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    location VARCHAR(255),
    linkedin_url VARCHAR(500),
    professional_summary TEXT,
    parsed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    parser_version VARCHAR(20),
    total_jobs_extracted INTEGER DEFAULT 0,
    total_skills_extracted INTEGER DEFAULT 0,
    core_skills_count INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_parsed_resume_user ON parsed_resume_documents(user_id);
CREATE INDEX idx_parsed_resume_doc ON parsed_resume_documents(resume_document_id);

CREATE TABLE job_experiences (
    id SERIAL PRIMARY KEY,
    parsed_resume_id INTEGER NOT NULL
        REFERENCES parsed_resume_documents(id)
        ON DELETE CASCADE,
    company_name VARCHAR(255) NOT NULL,
    job_title VARCHAR(255) NOT NULL,
    start_date VARCHAR(50),
    end_date VARCHAR(50),
    location VARCHAR(255),
    duties JSONB,
    environment_description TEXT,
    technologies_used JSONB,
    position_order INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_job_exp_resume ON job_experiences(parsed_resume_id);
CREATE INDEX idx_job_exp_company ON job_experiences(company_name);

CREATE TABLE quantified_accomplishments (
    id SERIAL PRIMARY KEY,
    job_experience_id INTEGER NOT NULL REFERENCES job_experiences(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    metrics JSONB,
    impact_category VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_accomplishment_job ON quantified_accomplishments(job_experience_id);
CREATE INDEX idx_accomplishment_category ON quantified_accomplishments(impact_category);

CREATE TABLE extracted_skills (
    id SERIAL PRIMARY KEY,
    parsed_resume_id INTEGER NOT NULL
        REFERENCES parsed_resume_documents(id)
        ON DELETE CASCADE,
    skill_name VARCHAR(255) NOT NULL,
    category skill_category NOT NULL,
    confidence_score FLOAT DEFAULT 0.5,
    extraction_source VARCHAR(100),
    years_experience FLOAT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_skill_resume ON extracted_skills(parsed_resume_id);
CREATE INDEX idx_skill_category ON extracted_skills(category);
CREATE INDEX idx_skill_name ON extracted_skills(skill_name);

CREATE TABLE job_skill_usage (
    id SERIAL PRIMARY KEY,
    job_experience_id INTEGER NOT NULL REFERENCES job_experiences(id) ON DELETE CASCADE,
    skill_name VARCHAR(255) NOT NULL,
    skill_category skill_category,
    confidence_score FLOAT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_job_skill_job ON job_skill_usage(job_experience_id);

CREATE TABLE certifications (
    id SERIAL PRIMARY KEY,
    parsed_resume_id INTEGER NOT NULL
        REFERENCES parsed_resume_documents(id)
        ON DELETE CASCADE,
    certification_name VARCHAR(255) NOT NULL,
    issuing_organization VARCHAR(255),
    issue_date VARCHAR(50),
    expiration_date VARCHAR(50),
    credential_id VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cert_resume ON certifications(parsed_resume_id);

CREATE TABLE education_records (
    id SERIAL PRIMARY KEY,
    parsed_resume_id INTEGER NOT NULL
        REFERENCES parsed_resume_documents(id)
        ON DELETE CASCADE,
    degree VARCHAR(255),
    field_of_study VARCHAR(255),
    institution VARCHAR(255),
    graduation_date VARCHAR(50),
    gpa VARCHAR(20),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_education_resume ON education_records(parsed_resume_id);
"""
