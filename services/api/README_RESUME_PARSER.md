# Intelligent Resume Parser for Winnow

An advanced resume parsing agent that distinguishes between **core skills/expertise** and **environmental/technology-adjacent knowledge** for optimal job matching and ATS optimization.

## Overview

This parser is specifically designed for IT professionals (like Project Managers, Software Engineers, etc.) who use various tools and work in different technology environments, but whose **primary expertise** may be distinct from the technologies they happen to use.

### Example: Project Manager

**Core Skills (Primary Expertise):**
- Project Management
- Agile/Scrum/Waterfall methodologies
- Stakeholder management
- Risk management
- Budget planning

**Technical Tools (Used regularly):**
- MS Project
- Smartsheet
- JIRA
- PowerPoint
- SharePoint

**Environmental Systems (Work context):**
- Epic EHR
- SAP
- Salesforce
- AWS infrastructure

The parser understands that a PM is an expert in *project management*, proficient with *PM tools*, and has *exposure to* various industry systems—but the systems are not their primary skill.

## Key Features

1. **Skill Categorization**
   - `CORE`: Primary expertise and competencies
   - `TECHNICAL`: Tools and platforms used regularly
   - `ENVIRONMENTAL`: Systems in work environment (context)
   - `SOFT`: Communication, leadership, etc.

2. **Intelligent Inference**
   - Infers skills from job titles (e.g., "Project Manager" → stakeholder communication, risk mitigation)
   - Extracts quantified accomplishments with metrics
   - Distinguishes explicit mentions from contextual references

3. **Confidence Scoring**
   - Each skill gets a confidence score (0.0 to 1.0)
   - Based on: frequency of mention, job title alignment, explicit vs inferred

4. **ATS Optimization**
   - Structured output optimized for Applicant Tracking Systems
   - Separates achievements with quantified metrics
   - Maintains source traceability

## Database Schema

```
parsed_resume_documents
├── Basic info (name, contact, summary)
├── Parsing metadata
└── Relationships:
    ├── job_experiences
    │   ├── Company, title, dates, location
    │   ├── Duties (array)
    │   ├── quantified_accomplishments
    │   │   └── Description, metrics, impact category
    │   └── job_skill_usage
    │       └── Skills used in this specific job
    ├── extracted_skills
    │   ├── Skill name
    │   ├── Category (CORE/TECHNICAL/ENVIRONMENTAL/SOFT)
    │   ├── Confidence score
    │   └── Extraction source
    ├── certifications
    └── education_records
```

## Installation

### Prerequisites

```bash
pip install sqlalchemy psycopg2-binary PyPDF2 docx2txt python-dateutil
```

### Add to Winnow Project

1. Copy files to `services/api/app/`:
   ```
   services/api/app/
   ├── services/
   │   ├── resume_parser_agent.py
   │   └── resume_parser_service.py
   └── models/
       └── resume_parser_models.py
   ```

2. Run migration:
   ```bash
   cd services/api
   alembic revision --autogenerate -m "Add intelligent resume parser"
   alembic upgrade head
   ```

3. Update requirements.txt:
   ```
   PyPDF2>=3.0.0
   docx2txt>=0.8
   python-dateutil>=2.8.0
   ```

## Usage

### Basic Parsing

```python
from app.services.resume_parser_service import ResumeParserService

# Initialize service
parser_service = ResumeParserService(db_session)

# Parse a resume
parsed = parser_service.parse_and_store(
    resume_document_id=123,
    user_id=456,
    file_path="/path/to/resume.docx"
)

print(f"Extracted {parsed.total_jobs_extracted} jobs")
print(f"Found {parsed.core_skills_count} core skills")
```

### Get Skill Profile for Matching

```python
# Get categorized skills for job matching
skill_profile = parser_service.generate_skill_profile_for_matching(user_id=456)

# Output:
{
    "primary_expertise": {
        "skills": [
            {"name": "Project Management", "confidence": 0.95, "weight": 1.0},
            {"name": "Agile", "confidence": 0.90, "weight": 1.0}
        ],
        "keywords": ["project management", "agile", ...]
    },
    "technical_proficiency": {
        "tools": ["MS Project", "Smartsheet", "JIRA"],
        "weight": 0.5
    },
    "industry_exposure": {
        "systems": ["Epic", "SAP", "Salesforce"],
        "weight": 0.3
    }
}
```

### API Integration

Add to `services/api/app/routers/resume.py`:

```python
@router.post("/{resume_id}/parse-intelligent")
async def parse_resume_intelligent(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Enhanced resume parsing with skill categorization"""
    parser_service = ResumeParserService(db)
    parsed = parser_service.parse_and_store(
        resume_document_id=resume_id,
        user_id=current_user.id,
        file_path=resume_doc.path
    )
    
    return {
        "status": "success",
        "parsed_resume_id": parsed.id,
        "core_skills_count": parsed.core_skills_count,
        "total_skills": parsed.total_skills_extracted
    }

@router.get("/skill-profile")
async def get_skill_profile(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get skill profile for matching"""
    parser_service = ResumeParserService(db)
    return parser_service.generate_skill_profile_for_matching(current_user.id)
```

## Skill Categorization Logic

### Core Skills (Weight: 1.0 for matching)
- Explicitly listed in Skills section
- Mentioned in job titles
- Frequently referenced in duties
- Examples: "Project Management", "Agile", "System Architecture"

### Technical Tools (Weight: 0.5 for matching)
- Tools used to perform core work
- Examples: "MS Project", "JIRA", "GitHub", "Excel"

### Environmental Systems (Weight: 0.3 for matching)
- Industry/domain systems in work environment
- Not primary expertise but provides context
- Examples: "Epic EHR", "SAP", "Oracle Financials"

### Soft Skills (Weight: varies)
- Communication, leadership, analytical thinking
- Inferred from management titles and accomplishments

## Integration with Matching Engine

The parser output is designed to improve job matching:

```python
# In services/api/app/services/matching.py

def compute_match_score(candidate_profile, job_description):
    skill_profile = parser_service.generate_skill_profile_for_matching(user_id)
    
    # Primary match on core skills (full weight)
    core_match = calculate_overlap(
        skill_profile['primary_expertise']['keywords'],
        job_required_skills,
        weight=1.0
    )
    
    # Bonus for technical tool matches (partial weight)
    tools_match = calculate_overlap(
        skill_profile['technical_proficiency']['tools'],
        job_preferred_tools,
        weight=0.5
    )
    
    # Context only for environmental systems (low weight)
    env_context = calculate_overlap(
        skill_profile['industry_exposure']['systems'],
        job_environment,
        weight=0.3
    )
    
    return (core_match + tools_match + env_context) / total_weight
```

## Quantified Accomplishments

The parser extracts measurable achievements:

```python
accomplishments = [
    {
        "description": "Established leased-equipment repository resulting in average savings of $294,000",
        "metrics": ["$294,000"],
        "impact_category": "cost_savings"
    },
    {
        "description": "Managed infrastructure upgrade for over 3,000 wireless access points",
        "metrics": ["3,000"],
        "impact_category": "delivery"
    }
]
```

Impact categories:
- `cost_savings`: Budget reductions, efficiency gains
- `revenue_growth`: Sales, business expansion
- `efficiency`: Process improvements, automation
- `quality`: Defect reduction, accuracy improvements
- `delivery`: Successful project completions

## Customization

### Add Industry-Specific Skills

```python
# In resume_parser_agent.py

CORE_PM_SKILLS = {
    'project management', 'program management',
    # Add your industry skills:
    'compliance management', 'hipaa', 'sox'
}

INDUSTRY_SYSTEMS = {
    'epic', 'cerner', 'sap',
    # Add your industry systems:
    'workday', 'oracle fusion', 'azure devops'
}
```

### Adjust Confidence Thresholds

```python
# Higher threshold = more conservative (only very confident skills)
core_skills = [
    s for s in all_skills 
    if s['category'] == 'core' and s['confidence'] >= 0.8  # Raise from 0.7
]
```

## Testing

```python
# Test with your resume
from resume_parser_agent import ResumeParserAgent
import docx2txt

resume_text = docx2txt.process('path/to/resume.docx')
parser = ResumeParserAgent()
parsed = parser.parse_resume(resume_text)

print(f"Candidate: {parsed.candidate_name}")
print(f"\nCore Skills ({len(parsed.core_skills)}):")
for skill in parsed.core_skills[:10]:
    print(f"  - {skill['skill']} (confidence: {skill['confidence']:.2f})")

print(f"\nJobs ({len(parsed.job_history)}):")
for job in parsed.job_history:
    print(f"  - {job.job_title} at {job.company_name}")
    print(f"    Skills: {[s['skill'] for s in job.skills_used[:5]]}")
```

## Troubleshooting

### Common Issues

1. **Missing skills**: Check if skill is in predefined lists. Add custom skills to `CORE_PM_SKILLS` or adjust inference logic.

2. **Wrong categorization**: Review categorization logic in `_categorize_skill()`. Adjust keyword matches.

3. **Low confidence scores**: Increase score in `_calculate_skill_confidence()` if skill appears in title or multiple duties.

4. **PDF parsing issues**: Some PDFs have complex layouts. Use DOCX when possible for best results.

## Future Enhancements

- [ ] ML-based skill extraction (BERT/GPT for better inference)
- [ ] Years of experience calculation per skill
- [ ] Skill synonym matching (e.g., "PM" = "Project Management")
- [ ] Industry-specific skill taxonomies
- [ ] Resume quality scoring
- [ ] Automated skill gap analysis

## License

Proprietary - Part of Winnow platform

## Support

For issues or questions, contact the Winnow development team.
