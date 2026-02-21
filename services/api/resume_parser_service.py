"""
Resume Parser Service for Winnow API
====================================

Service layer that integrates the intelligent resume parser with the Winnow API
"""

from pathlib import Path
from typing import Any

import docx2txt
import PyPDF2
from sqlalchemy.orm import Session

from resume_parser_agent import ParsedResume, ResumeParserAgent
from resume_parser_models import (
    Certification,
    Education,
    ExtractedSkill,
    JobExperience,
    JobSkillUsage,
    ParsedResumeDocument,
    QuantifiedAccomplishment,
    SkillCategoryEnum,
)


class ResumeParserService:
    """
    Service for parsing resumes and storing structured data
    Integrates with Winnow's existing resume_documents table
    """

    def __init__(self, db: Session):
        self.db = db
        self.parser = ResumeParserAgent()

    def parse_and_store(
        self, resume_document_id: int, user_id: int, file_path: str
    ) -> ParsedResumeDocument:
        """
        Parse a resume file and store all extracted data

        Args:
            resume_document_id: ID of existing resume_documents record
            user_id: User ID who owns the resume
            file_path: Path to the resume file (DOCX or PDF)

        Returns:
            ParsedResumeDocument object with all relationships loaded
        """
        # 1. Extract text from file
        resume_text = self._extract_text(file_path)

        # 2. Parse the resume
        file_metadata = {
            "filename": Path(file_path).name,
            "resume_document_id": resume_document_id,
        }
        parsed = self.parser.parse_resume(resume_text, file_metadata)

        # 3. Store in database
        db_record = self._store_parsed_resume(parsed, resume_document_id, user_id)

        # 4. Update candidate_profile with parsed data
        self._update_candidate_profile(user_id, parsed, db_record)

        return db_record

    def _extract_text(self, file_path: str) -> str:
        """Extract text from DOCX or PDF file"""
        file_path = Path(file_path)

        if file_path.suffix.lower() == ".docx":
            return docx2txt.process(str(file_path))
        elif file_path.suffix.lower() == ".pdf":
            return self._extract_pdf_text(file_path)
        else:
            # Try reading as plain text
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                return f.read()

    def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF file"""
        text = []
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page in pdf_reader.pages:
                text.append(page.extract_text())
        return "\n".join(text)

    def _store_parsed_resume(
        self, parsed: ParsedResume, resume_document_id: int, user_id: int
    ) -> ParsedResumeDocument:
        """Store parsed resume data in database"""

        # Create main record
        db_resume = ParsedResumeDocument(
            resume_document_id=resume_document_id,
            user_id=user_id,
            candidate_name=parsed.candidate_name,
            email=parsed.contact_info.get("email"),
            phone=parsed.contact_info.get("phone"),
            location=parsed.contact_info.get("location"),
            linkedin_url=parsed.contact_info.get("linkedin"),
            professional_summary=parsed.summary,
            parser_version="1.0",
            total_jobs_extracted=len(parsed.job_history),
            total_skills_extracted=len(parsed.all_skills_extracted),
            core_skills_count=len(parsed.core_skills),
        )
        self.db.add(db_resume)
        self.db.flush()  # Get ID

        # Store job experiences
        for idx, job in enumerate(parsed.job_history):
            db_job = JobExperience(
                parsed_resume_id=db_resume.id,
                company_name=job.company_name,
                job_title=job.job_title,
                start_date=job.start_date,
                end_date=job.end_date,
                location=job.location,
                duties=job.duties,
                environment_description=job.environment_description,
                technologies_used=job.technologies_used,
                position_order=idx,
            )
            self.db.add(db_job)
            self.db.flush()

            # Store accomplishments
            for acc in job.quantified_accomplishments:
                db_acc = QuantifiedAccomplishment(
                    job_experience_id=db_job.id,
                    description=acc.description,
                    metrics=acc.metrics,
                    impact_category=acc.impact_category,
                )
                self.db.add(db_acc)

            # Store job skill usage
            for skill in job.skills_used:
                db_job_skill = JobSkillUsage(
                    job_experience_id=db_job.id,
                    skill_name=skill["skill"],
                    skill_category=SkillCategoryEnum[skill["category"].upper()],
                    confidence_score=skill["confidence"],
                )
                self.db.add(db_job_skill)

        # Store all extracted skills
        for skill in parsed.all_skills_extracted:
            db_skill = ExtractedSkill(
                parsed_resume_id=db_resume.id,
                skill_name=skill["skill"],
                category=SkillCategoryEnum[skill["category"].upper()],
                confidence_score=skill["confidence"],
                extraction_source=skill["source"],
            )
            self.db.add(db_skill)

        # Store certifications
        for cert in parsed.certifications:
            db_cert = Certification(
                parsed_resume_id=db_resume.id, certification_name=cert
            )
            self.db.add(db_cert)

        # Store education
        for edu in parsed.education:
            db_edu = Education(
                parsed_resume_id=db_resume.id,
                degree=edu.get("degree"),
                field_of_study=edu.get("field"),
                institution=edu.get("institution"),
            )
            self.db.add(db_edu)

        self.db.commit()
        self.db.refresh(db_resume)

        return db_resume

    def _update_candidate_profile(
        self, user_id: int, parsed: ParsedResume, db_record: ParsedResumeDocument
    ) -> None:
        """
        Update candidate_profiles table with parsed data
        This creates a new version of the profile
        """
        from app.models import CandidateProfile  # Import from your models

        # Build profile_json from parsed data
        profile_json = {
            "basics": {
                "name": parsed.candidate_name,
                "email": parsed.contact_info.get("email"),
                "phone": parsed.contact_info.get("phone"),
                "location": parsed.contact_info.get("location"),
                "linkedin": parsed.contact_info.get("linkedin"),
            },
            "summary": parsed.summary,
            "experience": [
                {
                    "company": job.company_name,
                    "title": job.job_title,
                    "start_date": job.start_date,
                    "end_date": job.end_date,
                    "location": job.location,
                    "bullets": job.duties,
                    "accomplishments": [
                        {
                            "description": acc.description,
                            "metrics": acc.metrics,
                            "impact": acc.impact_category,
                        }
                        for acc in job.quantified_accomplishments
                    ],
                    "technologies": job.technologies_used,
                }
                for job in parsed.job_history
            ],
            "education": parsed.education,
            "certifications": parsed.certifications,
            "skills": {
                "core": [s["skill"] for s in parsed.core_skills],
                "technical": [
                    s["skill"]
                    for s in parsed.all_skills_extracted
                    if s["category"] == "technical"
                ],
                "environmental": [
                    s["skill"]
                    for s in parsed.all_skills_extracted
                    if s["category"] == "environmental"
                ],
                "soft": [
                    s["skill"]
                    for s in parsed.all_skills_extracted
                    if s["category"] == "soft"
                ],
            },
            "metadata": {
                "parsed_at": parsed.parsing_metadata.get("parsed_at"),
                "parser_version": "1.0",
                "resume_document_id": db_record.resume_document_id,
            },
        }

        # Get current profile version or start at 0
        current_profile = (
            self.db.query(CandidateProfile)
            .filter(CandidateProfile.user_id == user_id)
            .order_by(CandidateProfile.version.desc())
            .first()
        )

        new_version = (current_profile.version + 1) if current_profile else 1

        # Create new profile version
        new_profile = CandidateProfile(
            user_id=user_id, version=new_version, profile_json=profile_json
        )

        self.db.add(new_profile)
        self.db.commit()

    def get_parsed_resume(self, resume_document_id: int) -> ParsedResumeDocument | None:
        """Retrieve parsed resume data"""
        return (
            self.db.query(ParsedResumeDocument)
            .filter(ParsedResumeDocument.resume_document_id == resume_document_id)
            .first()
        )

    def get_core_skills(self, user_id: int) -> list[dict[str, Any]]:
        """Get core skills for a user"""
        parsed = (
            self.db.query(ParsedResumeDocument)
            .filter(ParsedResumeDocument.user_id == user_id)
            .order_by(ParsedResumeDocument.parsed_at.desc())
            .first()
        )

        if not parsed:
            return []

        core_skills = (
            self.db.query(ExtractedSkill)
            .filter(
                ExtractedSkill.parsed_resume_id == parsed.id,
                ExtractedSkill.category == SkillCategoryEnum.CORE,
            )
            .order_by(ExtractedSkill.confidence_score.desc())
            .all()
        )

        return [
            {
                "skill": s.skill_name,
                "confidence": s.confidence_score,
                "source": s.extraction_source,
            }
            for s in core_skills
        ]

    def get_job_history_summary(self, user_id: int) -> list[dict[str, Any]]:
        """Get formatted job history for a user"""
        parsed = (
            self.db.query(ParsedResumeDocument)
            .filter(ParsedResumeDocument.user_id == user_id)
            .order_by(ParsedResumeDocument.parsed_at.desc())
            .first()
        )

        if not parsed:
            return []

        jobs = (
            self.db.query(JobExperience)
            .filter(JobExperience.parsed_resume_id == parsed.id)
            .order_by(JobExperience.position_order)
            .all()
        )

        return [
            {
                "company": job.company_name,
                "title": job.job_title,
                "period": f"{job.start_date} - {job.end_date}"
                if job.start_date
                else None,
                "location": job.location,
                "key_accomplishments_count": len(job.accomplishments),
                "technologies": job.technologies_used,
            }
            for job in jobs
        ]

    def generate_skill_profile_for_matching(self, user_id: int) -> dict[str, Any]:
        """
        Generate a skill profile optimized for job matching
        Separates core expertise from environmental knowledge
        """
        parsed = (
            self.db.query(ParsedResumeDocument)
            .filter(ParsedResumeDocument.user_id == user_id)
            .order_by(ParsedResumeDocument.parsed_at.desc())
            .first()
        )

        if not parsed:
            return {}

        all_skills = (
            self.db.query(ExtractedSkill)
            .filter(ExtractedSkill.parsed_resume_id == parsed.id)
            .all()
        )

        # Categorize for matching
        core_skills = [s for s in all_skills if s.category == SkillCategoryEnum.CORE]
        technical_tools = [
            s for s in all_skills if s.category == SkillCategoryEnum.TECHNICAL
        ]
        industry_systems = [
            s for s in all_skills if s.category == SkillCategoryEnum.ENVIRONMENTAL
        ]

        return {
            "primary_expertise": {
                "skills": [
                    {
                        "name": s.skill_name,
                        "confidence": s.confidence_score,
                        "weight": 1.0,  # Full weight for matching
                    }
                    for s in core_skills
                ],
                "keywords": [s.skill_name.lower() for s in core_skills],
            },
            "technical_proficiency": {
                "tools": [s.skill_name for s in technical_tools],
                "weight": 0.5,  # Partial weight (nice-to-have)
            },
            "industry_exposure": {
                "systems": [s.skill_name for s in industry_systems],
                "weight": 0.3,  # Low weight (context only)
            },
            "matching_instructions": {
                "prioritize": "primary_expertise",
                "bonus_for": "technical_proficiency",
                "context_only": "industry_exposure",
            },
        }


# Example API endpoint integration
"""
# In services/api/app/routers/resume.py

from app.services.resume_parser_service import ResumeParserService

@router.post("/{resume_id}/parse-intelligent")
async def parse_resume_intelligent(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    '''
    Enhanced resume parsing with skill categorization
    '''
    # Get resume document
    resume_doc = db.query(ResumeDocument).filter(
        ResumeDocument.id == resume_id,
        ResumeDocument.user_id == current_user.id
    ).first()
    
    if not resume_doc:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Parse and store
    parser_service = ResumeParserService(db)
    parsed = parser_service.parse_and_store(
        resume_document_id=resume_id,
        user_id=current_user.id,
        file_path=resume_doc.path
    )
    
    return {
        "status": "success",
        "parsed_resume_id": parsed.id,
        "candidate_name": parsed.candidate_name,
        "total_jobs": parsed.total_jobs_extracted,
        "core_skills_count": parsed.core_skills_count,
        "total_skills": parsed.total_skills_extracted
    }

@router.get("/{resume_id}/skill-profile")
async def get_skill_profile(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    '''
    Get skill profile for matching (distinguishes core vs environmental)
    '''
    parser_service = ResumeParserService(db)
    skill_profile = parser_service.generate_skill_profile_for_matching(current_user.id)
    
    return skill_profile
"""
