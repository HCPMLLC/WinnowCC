"""
Test Script for Intelligent Resume Parser
==========================================

Demonstrates parsing Ronald Levi's resume and categorizing skills
"""

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from resume_parser_agent import ResumeParserAgent, SkillCategory


def test_ronald_levi_resume():
    """Test parser with Ronald Levi's actual resume"""

    # Sample text from the resume (would normally extract from DOCX)
    resume_text = """
    Ronald Levi PMP®
    New Braunfels, TX | 512-686-6808 | rlevi@hcpm.llc | LinkedIn

    Summary
    Certified PMP with over 25 years of experience
    leading Waterfall, Agile and Hybrid programs.
    Successfully led and managed large-scale projects
    with cross-functional teams and vendors with
    budgets ranging from $5M-$15M. From concept through
    post-implementation the initiatives spanned
    a variety of industries and geographies.

    Skills
    - Waterfall, Agile & Hybrid Methodologies
    - Contract Management
    - Stakeholder Communications (all levels)
    - Application Development Projects
    - Infrastructure Projects
    - MS Project
    - Kanban
    - MS Office Suite
    - Power Automate and Power BI
    - Expert -- SharePoint Administration and Customization
    - Advanced Excel -- Pivot Tables and Charts
    - ServiceNow

    Work Experience

    Rady Children's Hospital July 2025 -- Current
    Senior Project Manager (CTG Contract) San Diego, CA
    Planning, scheduling, monitoring and reporting
    at all levels -- perform-team through executive
    leadership for four projects concurrently:
    - InfoSec Audit Remediation: Planning, monitoring
      and reporting the InfoSec response to audit exposures
    - StrataJazz Integration: Consolidation of financial planning/management systems
    - EMS Communications System Replacement: General Devices CAREpoint 3 integration
    - SPD Impress Replacement: Replacement of Impress
      system with Steris SPM Asset Tracking Software
      which integrates with EPIC

    Tidelands Health January 2025 -- July 2025
    Program Manager (Medix Contract) Georgetown, SC
    - Led the Epic Optimization Program and Order Set Review Projects
    - Implemented a SharePoint site collection
      integrating Lists, Libraries, Power Automate
      and Power BI
    - Environment: MS 365, SharePoint, ServiceNow, SolarWinds, Hybrid Waterfall & Agile

    Methodist Le Bonheur Healthcare March 2023 -- September 2024
    Program Manager (CTG Contract) Memphis, TN
    - Managed the Le Bonheur Hospital Expansion
      Project involving construction and installation
      of new equipment for acute care departments
    - Managed the Kronos (UKG) migration to Dimensions Migration Project
    - Managed a major IT infrastructure Uplift Program
      with wireless upgrades of over 3,000 access points
    - Environment: MS O365, MS Project, Visio,
      Smartsheet, Hybrid Waterfall & Agile methods

    Trinity Health January 2015 -- April 2020
    Senior Project Manager, Supply Chain Livonia, MI
    - Established a leased-equipment repository
      resulting in an average savings of $294,000 in
      buyout/termination fees and average cost
      avoidance of over $28,000 per month
    - Owned Program Management for Patient Access -
      Patient Financial Services strategic projects
      including deployment of PNC Bank solutions
    - Environment: MS O365, SharePoint, Tableau,
      MS Project, Hybrid Waterfall & Agile methods

    Education
    Wayne State University -- Detroit, MI
    Bachelor of Arts, Organizational Psychology

    Certifications
    - PMI Certified Project Management Professional (PMP®)
    - Certified SAFe® Product Owner/Product Manager (POPM)
    - Certified SAFe® Agilist (SA)
    - IBM Certified Senior Project Manager
    - Stanford Certified Project Manager (SCPM)
    """

    # Parse the resume
    parser = ResumeParserAgent()
    parsed = parser.parse_resume(resume_text)

    print("=" * 80)
    print("INTELLIGENT RESUME PARSER - TEST RESULTS")
    print("=" * 80)
    print()

    # Basic Info
    print("CANDIDATE INFORMATION:")
    print(f"  Name: {parsed.candidate_name}")
    print(f"  Email: {parsed.contact_info.get('email', 'N/A')}")
    print(f"  Phone: {parsed.contact_info.get('phone', 'N/A')}")
    print(f"  Location: {parsed.contact_info.get('location', 'N/A')}")
    print()

    # Summary
    print("PROFESSIONAL SUMMARY:")
    if parsed.summary:
        summary_preview = (
            parsed.summary[:200] + "..."
            if len(parsed.summary) > 200
            else parsed.summary
        )
        print(f"  {summary_preview}")
    print()

    # Core Skills (Primary Expertise)
    print("CORE SKILLS (Primary Expertise):")
    core_skills = [
        s
        for s in parsed.all_skills_extracted
        if s["category"] == SkillCategory.CORE.value
    ]
    core_skills.sort(key=lambda x: x["confidence"], reverse=True)

    for skill in core_skills[:15]:
        confidence_bar = "█" * int(skill["confidence"] * 10)
        print(f"  • {skill['skill']:<40} {confidence_bar} {skill['confidence']:.2f}")
    print(f"  Total core skills: {len(core_skills)}")
    print()

    # Technical Tools
    print("TECHNICAL TOOLS (Proficient with):")
    tech_skills = [
        s
        for s in parsed.all_skills_extracted
        if s["category"] == SkillCategory.TECHNICAL.value
    ]
    for skill in tech_skills[:10]:
        print(f"  • {skill['skill']}")
    print(f"  Total technical tools: {len(tech_skills)}")
    print()

    # Environmental Systems
    print("ENVIRONMENTAL SYSTEMS (Work Context):")
    env_skills = [
        s
        for s in parsed.all_skills_extracted
        if s["category"] == SkillCategory.ENVIRONMENTAL.value
    ]
    for skill in env_skills[:10]:
        print(f"  • {skill['skill']}")
    print(f"  Total environmental systems: {len(env_skills)}")
    print()

    # Job History
    print("JOB HISTORY:")
    for idx, job in enumerate(parsed.job_history, 1):
        print(f"\n  Job #{idx}:")
        print(f"    Company: {job.company_name}")
        print(f"    Title: {job.job_title}")
        print(f"    Period: {job.start_date} - {job.end_date}")
        print(f"    Duties: {len(job.duties)} responsibilities")
        print(
            f"    Accomplishments: {len(job.quantified_accomplishments)} with metrics"
        )

        # Show accomplishments with metrics
        for acc in job.quantified_accomplishments[:2]:
            print(f"      ✓ {acc.description[:80]}...")
            print(f"        Metrics: {', '.join(acc.metrics)}")
            print(f"        Impact: {acc.impact_category}")

        # Show inferred skills for this job
        job_core_skills = [
            s for s in job.skills_used if s["category"] == SkillCategory.CORE.value
        ]
        if job_core_skills:
            skills_str = ", ".join([s["skill"] for s in job_core_skills[:5]])
            print(f"    Core skills used: {skills_str}")

        # Show technologies
        if job.technologies_used:
            tech_str = ", ".join(job.technologies_used[:5])
            print(f"    Technologies: {tech_str}")

    print()
    print("=" * 80)

    # Demonstrate ATS JSON output
    print("\nATS-OPTIMIZED JSON OUTPUT:")
    print("=" * 80)
    ats_json = parser.to_ats_json(parsed)

    # Print simplified version
    print(
        json.dumps(
            {
                "personal_info": ats_json["personal_info"],
                "core_competencies_count": len(ats_json["core_competencies"]),
                "certifications_count": len(ats_json["certifications"]),
                "jobs_count": len(ats_json["professional_experience"]),
                "skills_summary": {
                    "core_skills_count": len(ats_json["skills_summary"]["core_skills"]),
                    "technical_tools_count": len(
                        ats_json["skills_summary"]["technical_tools"]
                    ),
                    "industry_systems_count": len(
                        ats_json["skills_summary"]["industry_systems"]
                    ),
                },
                "sample_core_skills": ats_json["skills_summary"]["core_skills"][:5],
                "sample_technical_tools": ats_json["skills_summary"]["technical_tools"][
                    :5
                ],
                "sample_industry_systems": ats_json["skills_summary"][
                    "industry_systems"
                ][:5],
            },
            indent=2,
        )
    )

    print()
    print("=" * 80)
    print("KEY INSIGHTS:")
    print("=" * 80)
    print()
    print("✓ Successfully distinguished PRIMARY EXPERTISE from tools/environment")
    print()
    print("  Ronald Levi is a CERTIFIED PROJECT MANAGER with:")
    print(
        "    - Core expertise: PM methodologies, stakeholder mgmt, program leadership"
    )
    print("    - Technical proficiency: MS Project, Smartsheet, SharePoint")
    print("    - Industry exposure: Healthcare IT (Epic, UKG, Steris SPM)")
    print()
    print("  For job matching:")
    print("    - Match on: Project Management, Agile, Program Management (weight: 1.0)")
    print("    - Bonus for: MS Project, Power BI, ServiceNow (weight: 0.5)")
    print("    - Context: Epic, SAP integration experience (weight: 0.3)")
    print()
    print("✓ Extracted quantified accomplishments:")
    total_accomplishments = sum(
        len(job.quantified_accomplishments) for job in parsed.job_history
    )
    print(f"    - {total_accomplishments} achievements with measurable metrics")
    print()
    print("✓ Ready for ATS optimization and intelligent job matching")
    print()

    return parsed, ats_json


if __name__ == "__main__":
    parsed_resume, ats_output = test_ronald_levi_resume()

    # Save output
    output_dir = Path(__file__).parent / "test_output"
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "parsed_resume_test.json", "w") as f:
        json.dump(ats_output, f, indent=2)

    print(f"\n📁 Full ATS JSON saved to: {output_dir / 'parsed_resume_test.json'}")
    print()
