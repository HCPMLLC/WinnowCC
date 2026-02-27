"""
Intelligent Resume Parser Agent for Winnow
==========================================

This agent parses resumes to extract structured data while distinguishing between:
1. Core skills/expertise (primary competencies)
2. Environmental/technology-adjacent knowledge (tools/systems used)

Key Features:
- Extracts job history with quantified accomplishments
- Infers skills from duties and job titles
- Categorizes skills as "core" vs "environmental"
- Optimizes output for Applicant Tracking Systems (ATS)
- Supports multiple input formats (DOCX, PDF, TXT)
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class SkillCategory(Enum):
    """Categorize skills by their relationship to the candidate's expertise"""

    CORE = "core"  # Primary expertise (e.g., Project Management, Agile, Waterfall)
    TECHNICAL = "technical"  # Technical tools/platforms used regularly
    ENVIRONMENTAL = "environmental"  # Systems/tech in work environment
    SOFT = "soft"  # Communication, leadership, etc.


@dataclass
class QuantifiedAccomplishment:
    """Represents a measurable achievement"""

    description: str
    metrics: list[str]  # e.g., ["$294,000 savings", "28,000 per month cost avoidance"]
    impact_category: str  # e.g., "cost_savings", "efficiency", "quality"


@dataclass
class JobExperience:
    """Structured representation of a job position"""

    company_name: str
    job_title: str
    start_date: str | None
    end_date: str | None
    location: str | None
    duties: list[str]
    quantified_accomplishments: list[QuantifiedAccomplishment]
    skills_used: list[
        dict[str, Any]
    ]  # {skill: str, category: SkillCategory, confidence: float}
    technologies_used: list[str]
    environment_description: str | None


@dataclass
class ParsedResume:
    """Complete parsed resume structure"""

    candidate_name: str
    contact_info: dict[str, str]
    summary: str | None
    core_skills: list[dict[str, Any]]  # Primary expertise areas
    certifications: list[str]
    education: list[dict[str, str]]
    job_history: list[JobExperience]
    all_skills_extracted: list[dict[str, Any]]  # All skills with categorization
    parsing_metadata: dict[str, Any]


class ResumeParserAgent:
    """
    Intelligent agent that parses resumes and distinguishes core skills
    from environmental/adjacent technologies
    """

    # Core PM/IT skills that indicate primary expertise
    CORE_PM_SKILLS = {
        "project management",
        "program management",
        "portfolio management",
        "agile",
        "scrum",
        "kanban",
        "waterfall",
        "hybrid methodologies",
        "pmp",
        "safe",
        "pmbok",
        "prince2",
        "stakeholder management",
        "vendor management",
        "contract management",
        "risk management",
        "change management",
        "resource management",
        "budget management",
        "cost control",
        "schedule management",
        "requirements gathering",
        "scope management",
        "quality management",
        "process improvement",
        "strategic planning",
        "business analysis",
    }

    # Tools that PMs use but are not core PM expertise
    PM_TOOLS = {
        "ms project",
        "microsoft project",
        "smartsheet",
        "jira",
        "confluence",
        "asana",
        "monday.com",
        "trello",
        "basecamp",
        "wrike",
        "ms office",
        "microsoft office",
        "office 365",
        "ms 365",
        "m365",
        "excel",
        "powerpoint",
        "word",
        "visio",
        "outlook",
        "power automate",
        "power bi",
        "power apps",
        "sharepoint",
        "teams",
        "onedrive",
        "onenote",
        "tableau",
        "servicenow",
        "solarwinds",
    }

    # Industry/domain systems (environmental, not core PM skills)
    INDUSTRY_SYSTEMS = {
        "epic",
        "cerner",
        "meditech",
        "allscripts",
        "sap",
        "oracle",
        "workday",
        "peoplesoft",
        "lawson",
        "kronos",
        "ukg",
        "salesforce",
        "dynamics",
        "netsuite",
        "erp",
        "ehr",
        "emr",
        "rightfax",
        "steris",
        "general devices",
        "carepoint",
        "strata",
        "stratajazz",
        "greenhouse",
        "lever",
        "webex",
        "zoom",
        "cisco",
        "citrix",
        "vmware",
    }

    # Metrics/quantification patterns
    METRIC_PATTERNS = [
        r"\$[\d,]+(?:\.\d+)?[KMB]?",  # Dollar amounts
        r"[\d,]+(?:\.\d+)?%",  # Percentages
        r"[\d,]+\+?\s*(?:users|people|sites|locations|projects|hours|days|weeks|months)",
        r"over\s+\$?[\d,]+",
        r"reduced.*by\s+[\d,]+%?",
        r"increased.*by\s+[\d,]+%?",
        r"saved.*\$[\d,]+",
        r"[\d,]+x\s+(?:faster|improvement|increase)",
    ]

    # Job title indicators
    MANAGEMENT_TITLES = {
        "project manager",
        "program manager",
        "portfolio manager",
        "senior project manager",
        "lead project manager",
        "director",
        "pmo",
        "scrum master",
        "product owner",
        "business analyst",
    }

    def __init__(self):
        self.metric_regex = re.compile("|".join(self.METRIC_PATTERNS), re.IGNORECASE)

    def parse_resume(
        self, resume_text: str, file_metadata: dict | None = None
    ) -> ParsedResume:
        """
        Main parsing method - orchestrates all parsing steps

        Args:
            resume_text: Extracted text from resume document
            file_metadata: Optional metadata about the source file

        Returns:
            ParsedResume object with all structured data
        """
        # Extract basic info
        candidate_name = self._extract_name(resume_text)
        contact_info = self._extract_contact_info(resume_text)
        summary = self._extract_summary(resume_text)

        # Extract certifications and education
        certifications = self._extract_certifications(resume_text)
        education = self._extract_education(resume_text)

        # Extract job history (most complex part)
        job_history = self._extract_job_history(resume_text)

        # Extract and categorize ALL skills
        all_skills = self._extract_and_categorize_skills(resume_text, job_history)

        # Identify core skills (high-confidence primary expertise)
        core_skills = [
            s
            for s in all_skills
            if s["category"] == SkillCategory.CORE.value and s["confidence"] >= 0.7
        ]

        return ParsedResume(
            candidate_name=candidate_name,
            contact_info=contact_info,
            summary=summary,
            core_skills=core_skills,
            certifications=certifications,
            education=education,
            job_history=job_history,
            all_skills_extracted=all_skills,
            parsing_metadata={
                "parsed_at": datetime.utcnow().isoformat(),
                "source_file": file_metadata.get("filename") if file_metadata else None,
                "total_jobs": len(job_history),
                "total_skills": len(all_skills),
                "core_skills_count": len(core_skills),
            },
        )

    def _extract_name(self, text: str) -> str:
        """Extract candidate name from resume"""
        # Usually first line or after contact info
        lines = text.strip().split("\n")
        for line in lines[:5]:
            line = line.strip()
            # Name is typically 2-4 words, title case, not all caps
            if (
                2 <= len(line.split()) <= 4
                and line[0].isupper()
                and not line.isupper()
                and "@" not in line
                and "http" not in line.lower()
            ):
                return line
        return "Name Not Found"

    def _extract_contact_info(self, text: str) -> dict[str, str]:
        """Extract email, phone, LinkedIn, location"""
        contact = {}

        # Email
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        if email_match:
            contact["email"] = email_match.group()

        # Phone (various formats)
        phone_match = re.search(
            r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text
        )
        if phone_match:
            contact["phone"] = phone_match.group()

        # LinkedIn
        linkedin_match = re.search(r"linkedin\.com/in/[\w-]+", text, re.IGNORECASE)
        if linkedin_match:
            contact["linkedin"] = f"https://{linkedin_match.group()}"

        # Location (look for City, State pattern)
        location_match = re.search(
            r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*([A-Z]{2})", text
        )
        if location_match:
            contact["location"] = (
                f"{location_match.group(1)}, {location_match.group(2)}"
            )

        return contact

    def _extract_summary(self, text: str) -> str | None:
        """Extract professional summary/objective"""
        # Look for Summary, Profile, or Objective section
        summary_pattern = (
            r"(?:Summary|Profile|Objective)[:\n]+"
            r"(.*?)(?:\n\n|Skills|Experience|Education)"
        )
        match = re.search(summary_pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def _extract_certifications(self, text: str) -> list[str]:
        """Extract certifications"""
        certs = []

        # Common cert patterns
        cert_patterns = [
            r"PMP®?",
            r"SAFe®?\s+\w+",
            r"Certified\s+[\w\s]+",
            r"SCPM",
            r"Agile\s+Certified",
            r"\b[A-Z]{2,5}\b(?:\s*®)?",  # Acronym certs
        ]

        # Look in Certifications section
        cert_section = re.search(
            r"Certifications?[:\n]+(.*?)(?:\n\n|\Z)", text, re.IGNORECASE | re.DOTALL
        )
        if cert_section:
            cert_text = cert_section.group(1)
            for pattern in cert_patterns:
                matches = re.findall(pattern, cert_text)
                certs.extend(matches)

        return list(set(certs))  # Remove duplicates

    def _extract_education(self, text: str) -> list[dict[str, str]]:
        """Extract education history"""
        education = []

        edu_section = re.search(
            r"Education[:\n]+(.*?)(?:\n\n|Certifications|Skills|\Z)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if edu_section:
            edu_text = edu_section.group(1)

            # Look for degree and institution
            degree_patterns = [
                r"(Bachelor|Master|PhD|Associate)(?:\'s)?\s+of\s+([\w\s]+)",
                r"(B\.?[AS]\.?|M\.?[AS]\.?|MBA|PhD)\s+(?:in\s+)?([\w\s]+)",
            ]

            for pattern in degree_patterns:
                matches = re.finditer(pattern, edu_text, re.IGNORECASE)
                for match in matches:
                    degree_info = {
                        "degree": match.group(0),
                        "field": match.group(2) if len(match.groups()) > 1 else "",
                    }

                    # Try to find institution nearby
                    context = edu_text[max(0, match.start() - 100) : match.end() + 100]
                    institution = re.search(
                        r"(?:University|College|Institute)[^,\n]*",
                        context,
                        re.IGNORECASE,
                    )
                    if institution:
                        degree_info["institution"] = institution.group()

                    education.append(degree_info)

        return education

    def _extract_job_history(self, text: str) -> list[JobExperience]:
        """
        Extract job history with duties and accomplishments
        This is the most complex parsing task
        """
        jobs = []

        # Find Work Experience section
        work_section = re.search(
            r"(?:Work\s+Experience|Experience|Professional\s+Experience|Employment\s+History)[:\n]+(.*?)(?:Education|Certifications|\Z)",
            text,
            re.IGNORECASE | re.DOTALL,
        )

        if not work_section:
            return jobs

        work_text = work_section.group(1)

        # Split into job blocks (company + dates usually start a new job)
        # Pattern: Company Name  Dates or Company Name \n Title
        job_blocks = re.split(
            r"\n(?=[A-Z][^\n]{10,80}(?:\s{2,}|\n)(?:January|February|March|April|May|June|July|August|September|October|November|December|\d{4}))",
            work_text,
        )

        for block in job_blocks:
            if len(block.strip()) < 50:  # Skip small fragments
                continue

            job = self._parse_job_block(block)
            if job:
                jobs.append(job)

        return jobs

    def _parse_job_block(self, block: str) -> JobExperience | None:
        """Parse a single job entry"""
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if len(lines) < 2:
            return None

        # First line is usually company and dates
        first_line = lines[0]

        # Extract company name (before dates)
        company_match = re.match(r"(.*?)(?:\s{2,}|$)", first_line)
        company_name = company_match.group(1).strip() if company_match else first_line

        # Extract dates
        _months = (
            r"January|February|March|April|May|June|"
            r"July|August|September|October|November|"
            r"December|Jan|Feb|Mar|Apr|May|Jun|Jul|"
            r"Aug|Sep|Oct|Nov|Dec"
        )
        date_pattern = (
            rf"({_months})?\s*(\d{{4}})\s*[-–—]\s*"
            rf"((?:{_months})?\s*\d{{4}}|Current|Present)"
        )
        date_match = re.search(date_pattern, first_line, re.IGNORECASE)

        start_date = None
        end_date = None
        if date_match:
            start_date = f"{date_match.group(1) or ''} {date_match.group(2)}".strip()
            end_date = date_match.group(3)

        # Second line is usually job title
        job_title = lines[1] if len(lines) > 1 else "Position Not Specified"

        # Location might be on third line or in first line
        location = None
        location_match = re.search(r",\s*([A-Z]{2})\s*$", first_line)
        if location_match:
            location = location_match.group(1)
        elif len(lines) > 2:
            location_match = re.search(
                r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*([A-Z]{2})", lines[2]
            )
            if location_match:
                location = f"{location_match.group(1)}, {location_match.group(2)}"

        # Rest is duties and accomplishments
        content = "\n".join(lines[2:] if len(lines) > 2 else lines[1:])

        # Extract bullet points (duties)
        duties = self._extract_bullets(content)

        # Extract quantified accomplishments
        accomplishments = self._extract_accomplishments(content)

        # Infer skills from job title and duties
        skills_used = self._infer_job_skills(job_title, duties)

        # Extract technologies/systems mentioned
        technologies = self._extract_technologies(content)

        # Create environment description
        environment_desc = self._extract_environment(content)

        return JobExperience(
            company_name=company_name,
            job_title=job_title,
            start_date=start_date,
            end_date=end_date,
            location=location,
            duties=duties,
            quantified_accomplishments=accomplishments,
            skills_used=skills_used,
            technologies_used=technologies,
            environment_description=environment_desc,
        )

    def _extract_bullets(self, text: str) -> list[str]:
        """Extract bullet points from job description"""
        bullets = []

        # Look for lines starting with bullet chars or dashes
        bullet_pattern = r"^[\s]*[•\-–—*]\s*(.+)$"
        for line in text.split("\n"):
            match = re.match(bullet_pattern, line, re.MULTILINE)
            if match:
                bullets.append(match.group(1).strip())

        return bullets

    def _extract_accomplishments(self, text: str) -> list[QuantifiedAccomplishment]:
        """Extract accomplishments with quantified metrics"""
        accomplishments = []

        # Find sentences with metrics
        sentences = re.split(r"[.!]\s+", text)
        for sentence in sentences:
            metrics = self.metric_regex.findall(sentence)
            if metrics:
                # Categorize impact
                impact_category = self._categorize_impact(sentence)

                accomplishments.append(
                    QuantifiedAccomplishment(
                        description=sentence.strip(),
                        metrics=metrics,
                        impact_category=impact_category,
                    )
                )

        return accomplishments

    def _categorize_impact(self, text: str) -> str:
        """Categorize the type of impact/accomplishment"""
        text_lower = text.lower()

        if any(
            word in text_lower
            for word in ["saved", "savings", "cost", "budget", "reduced cost"]
        ):
            return "cost_savings"
        elif any(
            word in text_lower
            for word in ["efficiency", "faster", "streamlined", "automated"]
        ):
            return "efficiency"
        elif any(
            word in text_lower for word in ["quality", "accuracy", "defects", "errors"]
        ):
            return "quality"
        elif any(
            word in text_lower for word in ["revenue", "sales", "growth", "increased"]
        ):
            return "revenue_growth"
        elif any(
            word in text_lower
            for word in ["delivered", "completed", "launched", "implemented"]
        ):
            return "delivery"
        else:
            return "other"

    def _infer_job_skills(
        self, job_title: str, duties: list[str]
    ) -> list[dict[str, Any]]:
        """
        Infer skills from job title and duties
        This is where we distinguish core vs environmental skills
        """
        skills = []
        text = f"{job_title} {' '.join(duties)}".lower()

        # Check for core PM skills
        for skill in self.CORE_PM_SKILLS:
            if skill in text:
                confidence = self._calculate_skill_confidence(skill, job_title, duties)
                skills.append(
                    {
                        "skill": skill.title(),
                        "category": SkillCategory.CORE.value,
                        "confidence": confidence,
                        "source": "inferred_from_duties",
                    }
                )

        # Check for PM tools (technical but not core)
        for tool in self.PM_TOOLS:
            if tool in text:
                skills.append(
                    {
                        "skill": tool.title(),
                        "category": SkillCategory.TECHNICAL.value,
                        # High confidence for explicit mentions
                        "confidence": 0.9,
                        "source": "explicit_mention",
                    }
                )

        # Infer universal PM skills based on title
        title_lower = job_title.lower()
        if any(t in title_lower for t in self.MANAGEMENT_TITLES):
            # Add implicit skills that all PMs have
            implicit_skills = [
                "Stakeholder Communication",
                "Team Leadership",
                "Risk Mitigation",
                "Schedule Planning",
                "Budget Tracking",
            ]
            for implicit in implicit_skills:
                if not any(s["skill"].lower() == implicit.lower() for s in skills):
                    skills.append(
                        {
                            "skill": implicit,
                            "category": SkillCategory.CORE.value,
                            "confidence": 0.8,
                            "source": "inferred_from_title",
                        }
                    )

        return skills

    def _calculate_skill_confidence(
        self, skill: str, job_title: str, duties: list[str]
    ) -> float:
        """
        Calculate confidence score for inferred skill
        Higher score = more certain this is a core competency
        """
        confidence = 0.5  # Base

        # Boost if in job title
        if skill in job_title.lower():
            confidence += 0.3

        # Boost based on frequency in duties
        mentions = sum(1 for duty in duties if skill in duty.lower())
        confidence += min(0.2, mentions * 0.05)

        return min(1.0, confidence)

    def _extract_technologies(self, text: str) -> list[str]:
        """Extract technologies/systems mentioned (environmental)"""
        technologies = []
        text_lower = text.lower()

        for system in self.INDUSTRY_SYSTEMS:
            if system in text_lower:
                technologies.append(
                    system.upper() if len(system) <= 4 else system.title()
                )

        # Also look for "Environment:" sections
        env_match = re.search(r"Environment:?\s*([^\n]+)", text, re.IGNORECASE)
        if env_match:
            env_text = env_match.group(1)
            # Split on commas and clean up
            tech_list = [t.strip() for t in re.split(r"[,;]", env_text)]
            technologies.extend(tech_list)

        return list(set(technologies))  # Remove duplicates

    def _extract_environment(self, text: str) -> str | None:
        """Extract environment/context description"""
        env_match = re.search(r"Environment:?\s*([^\n]+)", text, re.IGNORECASE)
        if env_match:
            return env_match.group(1).strip()
        return None

    def _extract_and_categorize_skills(
        self, text: str, job_history: list[JobExperience]
    ) -> list[dict[str, Any]]:
        """
        Extract ALL skills and categorize them
        Combines explicit skill section + inferred from jobs
        """
        all_skills = []

        # 1. Extract from explicit Skills section
        skills_section = re.search(
            r"(?:Skills|Core\s+Competencies|Technical\s+Skills)[:\n]+(.*?)(?:\n\n|Work\s+Experience|Education|\Z)",
            text,
            re.IGNORECASE | re.DOTALL,
        )

        if skills_section:
            skills_text = skills_section.group(1)
            explicit_skills = self._parse_skills_section(skills_text)
            all_skills.extend(explicit_skills)

        # 2. Add skills inferred from jobs
        for job in job_history:
            for skill in job.skills_used:
                # Check if already exists
                existing = next(
                    (
                        s
                        for s in all_skills
                        if s["skill"].lower() == skill["skill"].lower()
                    ),
                    None,
                )
                if existing:
                    # Update confidence (take max)
                    existing["confidence"] = max(
                        existing["confidence"], skill["confidence"]
                    )
                else:
                    all_skills.append(skill)

        # 3. Deduplicate and sort by confidence
        all_skills = sorted(all_skills, key=lambda x: x["confidence"], reverse=True)

        return all_skills

    def _parse_skills_section(self, skills_text: str) -> list[dict[str, Any]]:
        """Parse skills from explicit skills section"""
        skills = []

        # Skills might be bullet points or comma-separated
        skill_items = []

        # Try bullet format first
        bullets = re.findall(r"^[\s]*[•\-–—*]\s*(.+)$", skills_text, re.MULTILINE)
        if bullets:
            skill_items = bullets
        else:
            # Try comma/newline separated
            skill_items = [
                s.strip() for s in re.split(r"[,\n]", skills_text) if s.strip()
            ]

        for item in skill_items:
            # Categorize each skill
            category = self._categorize_skill(item)

            skills.append(
                {
                    "skill": item.strip(),
                    "category": category.value,
                    "confidence": 0.95,  # High confidence for explicitly listed
                    "source": "explicit_skills_section",
                }
            )

        return skills

    def _categorize_skill(self, skill: str) -> SkillCategory:
        """Categorize a single skill"""
        skill_lower = skill.lower()

        # Check against known categories
        if any(core in skill_lower for core in self.CORE_PM_SKILLS):
            return SkillCategory.CORE
        elif any(tool in skill_lower for tool in self.PM_TOOLS):
            return SkillCategory.TECHNICAL
        elif any(sys in skill_lower for sys in self.INDUSTRY_SYSTEMS):
            return SkillCategory.ENVIRONMENTAL

        # Soft skills keywords
        soft_keywords = [
            "communication",
            "leadership",
            "collaboration",
            "teamwork",
            "analytical",
            "problem solving",
            "critical thinking",
        ]
        if any(soft in skill_lower for soft in soft_keywords):
            return SkillCategory.SOFT

        # Default to technical
        return SkillCategory.TECHNICAL

    def to_ats_json(self, parsed_resume: ParsedResume) -> dict:
        """
        Convert parsed resume to ATS-optimized JSON format
        """
        return {
            "personal_info": {
                "name": parsed_resume.candidate_name,
                **parsed_resume.contact_info,
            },
            "professional_summary": parsed_resume.summary,
            "core_competencies": [
                {
                    "skill": s["skill"],
                    "proficiency_level": "expert"
                    if s["confidence"] > 0.9
                    else "advanced",
                    "years_experience": None,  # Could be inferred from job history
                }
                for s in parsed_resume.core_skills
            ],
            "certifications": parsed_resume.certifications,
            "education": parsed_resume.education,
            "professional_experience": [
                {
                    "company": job.company_name,
                    "title": job.job_title,
                    "start_date": job.start_date,
                    "end_date": job.end_date,
                    "location": job.location,
                    "key_responsibilities": job.duties,
                    "achievements": [
                        {
                            "description": acc.description,
                            "metrics": acc.metrics,
                            "impact_type": acc.impact_category,
                        }
                        for acc in job.quantified_accomplishments
                    ],
                    "skills_utilized": [
                        s["skill"]
                        for s in job.skills_used
                        if s["category"]
                        in [SkillCategory.CORE.value, SkillCategory.TECHNICAL.value]
                    ],
                    "technologies_environment": job.technologies_used,
                }
                for job in parsed_resume.job_history
            ],
            "skills_summary": {
                "core_skills": [
                    s["skill"]
                    for s in parsed_resume.all_skills_extracted
                    if s["category"] == SkillCategory.CORE.value
                ],
                "technical_tools": [
                    s["skill"]
                    for s in parsed_resume.all_skills_extracted
                    if s["category"] == SkillCategory.TECHNICAL.value
                ],
                "industry_systems": [
                    s["skill"]
                    for s in parsed_resume.all_skills_extracted
                    if s["category"] == SkillCategory.ENVIRONMENTAL.value
                ],
                "soft_skills": [
                    s["skill"]
                    for s in parsed_resume.all_skills_extracted
                    if s["category"] == SkillCategory.SOFT.value
                ],
            },
            "parsing_metadata": parsed_resume.parsing_metadata,
        }


def main():
    """Example usage"""
    # Read the example resume
    try:
        import docx2txt

        resume_text = docx2txt.process(
            "/mnt/project/Resume_of_Ronald_Levi_PMP_CSS2025.docx"
        )
    except Exception:
        # Fallback: use a sample text
        resume_text = """
        Ronald Levi PMP
        New Braunfels, TX | 512-686-6808 | rlevi@hcpm.llc
        
        Summary
        Certified PMP with over 25 years of experience
        leading Waterfall, Agile and Hybrid programs.
        
        Skills
        - Project Management
        - Agile & Scrum
        - MS Project
        - Stakeholder Communications
        
        Work Experience
        Rady Children's Hospital  July 2025 -- Current
        Senior Project Manager (CTG Contract)  San Diego, CA
        - Planning, scheduling, monitoring and reporting for four projects concurrently
        - Led InfoSec Audit Remediation project
        - Managed EPIC integration projects
        
        Environment: MS 365, SharePoint, ServiceNow
        """

    # Parse the resume
    parser = ResumeParserAgent()
    parsed = parser.parse_resume(resume_text)

    # Convert to ATS format
    ats_json = parser.to_ats_json(parsed)

    # Print results
    print(json.dumps(ats_json, indent=2))

    return parsed, ats_json


if __name__ == "__main__":
    main()
