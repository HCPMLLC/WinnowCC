# PROMPT14_Enhance_Parsers.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, PROMPT9_Resume_Parser.md, PROMPT10_Job_Parser.md, and the existing openapi JSON files before making changes.

## Purpose

Upgrade both the Resume Parser and the Job Parser to senior-recruiter-grade quality. This is a combined implementation prompt that integrates the design specifications from PROMPT9 (Resume Parser) and PROMPT10 (Job Parser) into the existing Winnow codebase. The current parsers are basic/v1 — this prompt transforms them into production-grade intelligence engines.

**Two parallel tracks, one prompt:**
- **Track A — Resume Parser Enhancement:** Upgrade `profile_parser.py` to use industry-aware disambiguation, XYZ-style bullet detection, duty vs. accomplishment separation, technology categorization, and the full PROMPT9 extraction schema.
- **Track B — Job Parser + Fraud Detector:** Create new `job_parser.py` and `job_fraud_detector.py` services, add the `job_parsed_details` table, wire into the ingestion pipeline, and upgrade match scoring to 6-dimension composite.

These two tracks can be implemented independently, but both feed into improved match quality.

---

## Triggers — When to Use This Prompt

- Upgrading resume parsing from basic regex/keyword extraction to recruiter-grade.
- Implementing deep job posting analysis with structured requirement extraction.
- Adding fraud and duplicate detection to job ingestion.
- Improving match quality beyond simple skill keyword overlap.
- Product asks for "better parsing," "recruiter-grade matching," or "deep extraction."

---

## What Already Exists (DO NOT recreate — read the codebase first)

### Resume parsing (Track A)

1. **Parser service:** `services/api/app/services/profile_parser.py` — current v1 parser. Extracts text from PDF (pypdf) and DOCX (python-docx), produces `profile_json` with basic fields (basics, experience, education, skills, preferences).
2. **Resume upload router:** `services/api/app/routers/resume.py` — `POST /api/resume/upload` and `POST /api/resume/{resume_id}/parse` (enqueues background parse job).
3. **Profile router:** `services/api/app/routers/profile.py` — `GET /api/profile`, `PUT /api/profile`, `GET /api/profile/completeness`.
4. **CandidateProfile model:** `services/api/app/models/candidate_profile.py` — `profile_json` (JSONB), `version` (int), `user_id`.
5. **Resume documents model:** `services/api/app/models/resume_document.py` — stores uploaded file path and metadata.
6. **Queue service:** `services/api/app/services/queue.py` — RQ wrapper for background jobs.

### Job parsing (Track B)

1. **Job model:** `services/api/app/models/job.py` — stores job postings with `title`, `company`, `description`, `requirements`, `location`, `salary_min/max`, `remote_ok`, `source`, `posted_at`, etc.
2. **Ingestion service:** The ingestion pipeline fetches jobs from sources (Remotive, The Muse, etc.) and stores them in the `jobs` table.
3. **Matching service:** `services/api/app/services/matching.py` — current skill-overlap matching logic producing `match_score`, `resume_score`, `interview_probability`, and `reasons` JSON.
4. **Match model:** `services/api/app/models/match.py` — `match_score`, `resume_score`, `interview_probability`, `reasons` (JSON), etc.

---

# TRACK A — RESUME PARSER ENHANCEMENT

## A1: Upgrade profile_json Schema

**File to modify:** `services/api/app/services/profile_parser.py`

The current v1 parser produces a basic `profile_json`. Upgrade to the full PROMPT9 schema. The enhanced `profile_json` stored in `candidate_profiles.profile_json` should contain:

```json
{
  "contact_information": {
    "full_name": "",
    "email": "",
    "phone": "",
    "linkedin_url": null,
    "github_url": null,
    "portfolio_url": null,
    "other_urls": [],
    "location": {
      "city": "",
      "state_province": "",
      "country": "",
      "willing_to_relocate": null,
      "remote_preference": null
    }
  },
  "professional_summary": "",
  "primary_industry": "",
  "primary_role_category": "",
  "years_of_experience": null,
  "work_experience": [
    {
      "job_title": "",
      "company_name": "",
      "company_industry": "",
      "employment_type": "",
      "location": { "city": "", "state_province": "", "country": "", "remote": false },
      "start_date": "",
      "end_date": "",
      "duties": [],
      "accomplishments": [],
      "technologies_used": [
        { "name": "", "category": "", "context": "" }
      ],
      "environments_supported": [],
      "domain_skills": [],
      "management_scope": {
        "direct_reports": null,
        "budget_managed": null,
        "team_size": null,
        "project_count": null
      }
    }
  ],
  "skills": {
    "technical_skills": [
      { "name": "", "category": "", "proficiency_indicator": "" }
    ],
    "methodologies": [],
    "soft_skills": [],
    "industry_knowledge": [],
    "languages_spoken": [
      { "language": "", "proficiency": "" }
    ],
    "certifications": [
      { "name": "", "issuing_body": "", "credential_id": "", "date_obtained": "", "expiration_date": "", "status": "" }
    ],
    "licenses": [
      { "name": "", "issuing_authority": "", "license_number": "", "status": "" }
    ]
  },
  "education": [
    {
      "institution": "",
      "degree_type": "",
      "field_of_study": "",
      "minor": "",
      "graduation_date": "",
      "gpa": null,
      "honors": "",
      "relevant_coursework": [],
      "thesis_or_capstone": ""
    }
  ],
  "additional_sections": {
    "publications": [],
    "patents": [],
    "awards": [],
    "volunteer_work": [],
    "professional_affiliations": [],
    "military_service": null,
    "security_clearance": null
  },
  "disambiguation_notes": [],
  "preferences": {
    "target_titles": [],
    "locations": [],
    "remote_ok": null,
    "job_type": null,
    "salary_min": null,
    "salary_max": null,
    "industries": []
  }
}
```

**Backward compatibility:** Keep the `preferences` block at the top level (the profile editor depends on it). Map old field names: `basics.name` → `contact_information.full_name`, `experience[].bullets` → split into `duties[]` + `accomplishments[]`, `skills` (flat array) → `skills.technical_skills[]`.

When the profile editor (`PUT /api/profile`) writes to `profile_json`, it should continue to work — the enhanced parser adds new fields but does not remove existing ones.

---

## A2: Industry-Aware Disambiguation Engine

**File to create:** `services/api/app/services/resume_disambiguation.py` (NEW)

Implement the disambiguation logic from PROMPT9. This module is called by the parser after text extraction, before structured output.

### A2.1 Industry detection

```python
def detect_primary_industry(resume_text: str, employers: list[str], titles: list[str]) -> str:
    """
    Determine the candidate's primary industry from the overall resume context.
    Returns one of: "Information Technology", "Construction", "Healthcare",
    "Finance", "Manufacturing", "Government", "Energy/Utilities", "Education",
    "Legal", "Marketing", "Other"
    """
```

Analyze:
- Job titles (strongest signal)
- Employer names (if recognizable)
- Domain-specific terminology density (NEC/OSHA → construction, HIPAA → healthcare, SCADA → utilities, etc.)
- Certifications (PMP → management, CISSP → IT security, PE → engineering, CPA → finance)

### A2.2 Term classification

```python
# Classification hierarchy constants
ALWAYS_TECHNOLOGY = {"Tableau", "Jira", "Confluence", "ServiceNow", "Salesforce", "SAP", "Workday", "PeopleSoft"}
ALWAYS_METHODOLOGY = {"Agile", "Scrum", "Waterfall", "Kanban", "SAFe", "Lean", "Six Sigma", "ITIL", "TOGAF", "COBIT"}
ALWAYS_CLOUD = {"AWS", "Azure", "GCP"}
ALWAYS_CERTIFICATION = {"PMP", "CISSP", "CCNA", "CPA", "AWS Solutions Architect", "CompTIA Security+"}
ALWAYS_COMPLIANCE = {"HIPAA", "SOX", "GDPR", "PCI-DSS", "FERPA", "NERC CIP"}

def classify_term(
    term: str,
    context_words: list[str],
    industry: str,
    is_in_title: bool,
    is_after_employer_signal: bool,
    is_in_tech_line: bool,
) -> str:
    """
    Classify a term as: Technology, Company, Role, Methodology, Certification,
    Compliance, Domain_Skill, or Ambiguous.
    
    Apply the Term Classification Hierarchy from PROMPT9 in priority order.
    """
```

### A2.3 Technology categorization

```python
TECH_CATEGORIES = {
    "Python": "Programming Language", "JavaScript": "Programming Language", "TypeScript": "Programming Language",
    "Java": "Programming Language", "C#": "Programming Language", "Go": "Programming Language",
    "React": "Framework", "Angular": "Framework", "Django": "Framework", "Spring": "Framework",
    "PostgreSQL": "Database", "MySQL": "Database", "MongoDB": "Database", "Redis": "Database",
    "Docker": "Containerization", "Kubernetes": "Orchestration",
    "Jenkins": "CI/CD", "GitHub Actions": "CI/CD", "GitLab CI": "CI/CD",
    "Terraform": "DevOps Tool", "Ansible": "DevOps Tool",
    "Splunk": "Monitoring Tool", "Datadog": "Monitoring Tool", "PagerDuty": "Monitoring Tool",
    "Procore": "Collaboration Tool", "Bluebeam": "Collaboration Tool",
    "SAP": "ERP Platform", "Workday": "ERP Platform", "Oracle": "Database",
    "Power BI": "BI/Analytics Tool", "Tableau": "BI/Analytics Tool",
    # ... extend as needed
}

def categorize_technology(name: str) -> str:
    """Return the standardized category for a technology name."""
    return TECH_CATEGORIES.get(name, "Other")
```

---

## A3: Duty vs. Accomplishment Splitter

**File to modify:** `services/api/app/services/profile_parser.py`

Add logic to split experience bullets into duties and accomplishments.

```python
ACCOMPLISHMENT_SIGNALS = [
    r'\d+%',           # Percentages: "reduced by 40%"
    r'\$[\d,.]+[KMB]?', # Dollar amounts: "$4.2M", "$120K"
    r'\b\d+x\b',       # Multipliers: "3x improvement"
    r'saved\b', r'reduced\b', r'increased\b', r'improved\b', r'achieved\b',
    r'delivered\b', r'generated\b', r'grew\b', r'cut\b', r'eliminated\b',
    r'resulted in\b', r'led to\b', r'contributing to\b',
    r'awarded\b', r'recognized\b', r'promoted\b',
]

def classify_bullet(bullet: str) -> str:
    """
    Returns 'accomplishment' if the bullet contains measurable outcomes,
    metrics, or impact language. Otherwise returns 'duty'.
    """
    bullet_lower = bullet.lower()
    for pattern in ACCOMPLISHMENT_SIGNALS:
        if re.search(pattern, bullet_lower):
            return "accomplishment"
    return "duty"

def split_bullets(bullets: list[str]) -> tuple[list[str], list[str]]:
    """Split a list of bullets into (duties, accomplishments)."""
    duties = []
    accomplishments = []
    for bullet in bullets:
        if classify_bullet(bullet) == "accomplishment":
            accomplishments.append(bullet)
        else:
            duties.append(bullet)
    return duties, accomplishments
```

---

## A4: XYZ Bullet Detection

**File to modify:** `services/api/app/services/profile_parser.py`

Detect and tag "XYZ-style" bullets (Accomplished [X] as measured by [Y], by doing [Z]). These are the gold standard for resume bullets and feed into the resume_score (R_s) in the Interview Probability formula.

```python
def is_xyz_bullet(bullet: str) -> bool:
    """
    Detect XYZ-style bullets: Accomplished [X] as measured by [Y], by doing [Z].
    Returns True if the bullet contains all three elements:
    - X: An action/result verb (accomplished, led, delivered, etc.)
    - Y: A measurable metric (%, $, count, time)
    - Z: A method/approach (by doing, through, using, via)
    
    Also accepts partial XYZ: X+Y (action + metric) without explicit Z.
    """
    has_action = bool(re.search(
        r'\b(led|managed|delivered|built|designed|implemented|created|reduced|increased|improved|achieved|launched|drove|spearheaded|orchestrated)\b',
        bullet.lower()
    ))
    has_metric = bool(re.search(
        r'(\d+%|\$[\d,.]+[KMB]?|\b\d+\s*(users|clients|projects|team members|engineers|developers|reports|locations|sites)\b)',
        bullet
    ))
    has_method = bool(re.search(
        r'\b(by\s+(implementing|using|leveraging|creating|developing|introducing|establishing|building|designing))\b|\bthrough\b|\bvia\b|\busing\b',
        bullet.lower()
    ))
    
    # Full XYZ: all three. Partial XYZ: action + metric (still valuable).
    return (has_action and has_metric and has_method) or (has_action and has_metric)
```

Tag each bullet in the profile_json:

```json
{
  "accomplishments": [
    {
      "text": "Reduced deployment time by 40%, saving $120K annually, by implementing CI/CD with GitHub Actions",
      "is_xyz": true,
      "xyz_components": { "action": "Reduced", "metric": "40%, $120K", "method": "implementing CI/CD with GitHub Actions" }
    }
  ]
}
```

Or simpler approach — add an `xyz_bullet_count` field to each experience entry:
```json
{
  "company_name": "Acme Corp",
  "xyz_bullet_count": 3,
  "total_bullet_count": 7
}
```

---

## A5: Enhanced Parser Pipeline

**File to modify:** `services/api/app/services/profile_parser.py`

Update the main parse function to use the new modules:

```python
def parse_resume_enhanced(resume_text: str) -> dict:
    """
    Enhanced resume parsing pipeline.
    
    Step 1: Full scan — detect industry, role category, career trajectory
    Step 2: Anchor identification — lock in employer names and job titles
    Step 3: Contextual classification — disambiguate terms using industry context
    Step 4: Extraction — populate the full JSON schema
    Step 5: Validation — verify no misclassifications, logical dates, duty/accomplishment split
    Step 6: Output — return validated profile_json
    """
    # Step 1
    employers, titles = extract_anchors(resume_text)
    industry = detect_primary_industry(resume_text, employers, titles)
    role_category = detect_role_category(titles)
    
    # Step 2-3
    classified_terms = classify_all_terms(resume_text, industry, employers, titles)
    
    # Step 4
    profile = extract_structured_profile(resume_text, classified_terms, industry, role_category)
    
    # Step 5
    profile = validate_extraction(profile)
    
    return profile
```

**Important:** The enhanced parser should be backward-compatible. The `preferences` block structure must be preserved because the profile editor (`PUT /api/profile`) and completeness scorer (`compute_profile_completeness`) depend on it. Map old fields to new fields gracefully:
- Old `basics.name` → New `contact_information.full_name`
- Old `experience[].bullets` → New split into `duties[]` + `accomplishments[]`
- Old `skills` (flat string array) → New `skills.technical_skills[].name`
- Old `preferences` → Keep at same location

---

## A6: Two-Pass Validation (Optional but Recommended)

If the initial parse produces the profile_json, run a second validation pass that checks:

1. No company names accidentally listed as skills or technologies
2. No technologies that contradict the candidate's industry (e.g., "Kubernetes" for a construction worker with no IT background)
3. Dates are logical — no impossible overlaps unless concurrent roles are noted
4. Accomplishments are separated from duties (accomplishments have metrics)
5. `primary_industry` and `primary_role_category` are consistent with the resume body

Log any validation issues in `disambiguation_notes`.

---

# TRACK B — JOB PARSER + FRAUD DETECTOR

## B1: Job Parsed Details Table

**Migration to create:** `services/api/alembic/versions/xxxx_add_job_parsed_details.py`

### B1.1 New table: `job_parsed_details`

| Column | Type | Description |
|--------|------|-------------|
| id | int PK | Auto-increment |
| job_id | int FK jobs.id UNIQUE | One parsed record per job |
| normalized_title | string | Cleaned title (expanded abbreviations, standardized seniority) |
| seniority_level | string enum | entry, mid, senior, lead, principal, director, vp, c_level |
| employment_type | string enum | full_time, part_time, contract, freelance, internship |
| work_mode | string enum | onsite, remote, hybrid |
| parsed_location | jsonb | {city, state, country, region} |
| salary_min_parsed | int nullable | Extracted or inferred minimum salary |
| salary_max_parsed | int nullable | Extracted or inferred maximum salary |
| salary_currency | string nullable | USD, EUR, etc. |
| salary_type | string enum | annual, hourly, monthly, daily |
| compensation_confidence | string enum | explicit, inferred, unknown |
| benefits_mentioned | jsonb | Array of benefit keywords |
| required_skills | jsonb | Array of {skill, category, is_must_have, context_snippet} |
| preferred_skills | jsonb | Array of {skill, category, is_must_have: false, context_snippet} |
| required_certifications | jsonb | Array of {cert_name, normalized_name, required_or_preferred} |
| required_education | jsonb | {min_degree, field_of_study, equivalent_experience_ok} |
| required_years_experience | int nullable | Minimum years |
| preferred_years_experience | int nullable | Preferred years |
| required_clearance | string nullable | Security clearance if mentioned |
| tools_and_technologies | jsonb | Array of specific tools/platforms mentioned |
| company_industry | string nullable | Inferred industry |
| company_size_signal | string nullable | startup, smb, mid_market, enterprise |
| department | string nullable | Extracted department |
| reports_to | string nullable | Who this role reports to |
| team_size_signal | string nullable | Any team size clues |
| posting_quality_score | int 0–100 | Completeness/professionalism of posting |
| red_flags | jsonb | Array of {flag_code, severity, description} |
| is_likely_fraudulent | bool default false | Final fraud determination |
| is_duplicate_of_job_id | int nullable FK jobs.id | Points to canonical job |
| duplicate_confidence | float nullable | 0.0–1.0 |
| dedup_group_id | string nullable | UUID for duplicate clusters |
| raw_responsibilities | jsonb | Extracted responsibility strings |
| raw_qualifications | jsonb | Extracted qualification strings |
| created_at | timestamp | Auto |
| updated_at | timestamp | Auto |

### B1.2 Add columns to existing `jobs` table

| Column | Type | Description |
|--------|------|-------------|
| is_active | bool default true | Set false for fraud/expired |
| first_seen_at | timestamp nullable | First ingestion time |
| last_seen_at | timestamp nullable | Most recent ingestion time |

### B1.3 Steps in Cursor

1. Open a terminal in `services/api/`
2. Run:
   ```powershell
   cd services/api
   .\.venv\Scripts\Activate.ps1
   alembic revision --autogenerate -m "add job_parsed_details table and jobs columns"
   ```
3. Review the generated migration file in `services/api/alembic/versions/`
4. Run: `alembic upgrade head`

---

## B2: SQLAlchemy Model for job_parsed_details

**File to create:** `services/api/app/models/job_parsed_detail.py` (NEW)

```python
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base  # Use your existing base

class JobParsedDetail(Base):
    __tablename__ = "job_parsed_details"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), unique=True, nullable=False)
    normalized_title = Column(String, nullable=True)
    seniority_level = Column(String, nullable=True)
    employment_type = Column(String, nullable=True)
    work_mode = Column(String, nullable=True)
    parsed_location = Column(JSONB, nullable=True)
    salary_min_parsed = Column(Integer, nullable=True)
    salary_max_parsed = Column(Integer, nullable=True)
    salary_currency = Column(String, nullable=True)
    salary_type = Column(String, nullable=True)
    compensation_confidence = Column(String, nullable=True)
    benefits_mentioned = Column(JSONB, nullable=True)
    required_skills = Column(JSONB, nullable=True)
    preferred_skills = Column(JSONB, nullable=True)
    required_certifications = Column(JSONB, nullable=True)
    required_education = Column(JSONB, nullable=True)
    required_years_experience = Column(Integer, nullable=True)
    preferred_years_experience = Column(Integer, nullable=True)
    required_clearance = Column(String, nullable=True)
    tools_and_technologies = Column(JSONB, nullable=True)
    company_industry = Column(String, nullable=True)
    company_size_signal = Column(String, nullable=True)
    department = Column(String, nullable=True)
    reports_to = Column(String, nullable=True)
    team_size_signal = Column(String, nullable=True)
    posting_quality_score = Column(Integer, nullable=True)
    red_flags = Column(JSONB, nullable=True)
    is_likely_fraudulent = Column(Boolean, default=False)
    is_duplicate_of_job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    duplicate_confidence = Column(Float, nullable=True)
    dedup_group_id = Column(String, nullable=True)
    raw_responsibilities = Column(JSONB, nullable=True)
    raw_qualifications = Column(JSONB, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    job = relationship("Job", foreign_keys=[job_id], backref="parsed_details")
```

**Also update:** `services/api/app/models/__init__.py` — import `JobParsedDetail`.
**Also update:** `services/api/app/models/job.py` — add `is_active`, `first_seen_at`, `last_seen_at` columns.

---

## B3: Shared Reference Data

**Create these three files:**

### B3.1 Skill Synonyms: `services/api/app/services/skill_synonyms.py` (NEW)

```python
SKILL_SYNONYMS = {
    "agile": {"scrum", "safe", "kanban"},
    "scrum": {"agile", "safe", "kanban"},
    "ms project": {"microsoft project"},
    "power bi": {"powerbi"},
    "sharepoint": {"sp", "spo", "sharepoint online"},
    "javascript": {"js", "typescript", "ts"},
    "python": {"python3"},
    "aws": {"amazon web services"},
    "gcp": {"google cloud", "google cloud platform"},
    "ci/cd": {"continuous integration", "continuous deployment", "jenkins", "github actions", "gitlab ci"},
    "sql": {"t-sql", "pl/sql", "mysql", "postgresql", "sql server"},
    "react": {"reactjs", "react.js"},
    "node": {"nodejs", "node.js"},
    "docker": {"containerization"},
    "kubernetes": {"k8s"},
}

def get_synonyms(skill: str) -> set[str]:
    """Return all synonyms for a skill (lowercase)."""
    skill_lower = skill.lower().strip()
    synonyms = {skill_lower}
    if skill_lower in SKILL_SYNONYMS:
        synonyms.update(SKILL_SYNONYMS[skill_lower])
    # Also check if this skill appears as a synonym of another
    for canonical, syns in SKILL_SYNONYMS.items():
        if skill_lower in syns:
            synonyms.add(canonical)
            synonyms.update(syns)
    return synonyms

def skills_match(skill_a: str, skill_b: str) -> bool:
    """Return True if two skills are the same or synonymous."""
    return skill_b.lower().strip() in get_synonyms(skill_a)
```

### B3.2 Salary Reference: `services/api/app/services/salary_reference.py` (NEW)

Embedded salary range data for common IT roles. Used when a job posting doesn't state compensation.

```python
SALARY_REFERENCE = {
    "software engineer": {"entry": (65000, 90000), "mid": (90000, 130000), "senior": (130000, 180000)},
    "project manager": {"entry": (55000, 75000), "mid": (75000, 110000), "senior": (110000, 150000)},
    "data analyst": {"entry": (50000, 70000), "mid": (70000, 100000), "senior": (100000, 135000)},
    "devops engineer": {"entry": (70000, 95000), "mid": (95000, 140000), "senior": (140000, 190000)},
    "product manager": {"entry": (70000, 95000), "mid": (95000, 140000), "senior": (140000, 190000)},
    "cybersecurity analyst": {"entry": (60000, 85000), "mid": (85000, 120000), "senior": (120000, 165000)},
    "database administrator": {"entry": (55000, 75000), "mid": (75000, 110000), "senior": (110000, 145000)},
    "cloud architect": {"entry": (90000, 120000), "mid": (120000, 160000), "senior": (160000, 220000)},
    "default": {"entry": (45000, 65000), "mid": (65000, 100000), "senior": (100000, 150000)},
}

def infer_salary_range(title: str, seniority: str = "mid") -> tuple[int, int]:
    """Return (min, max) salary estimate based on title and seniority."""
    title_lower = title.lower().strip()
    for key in SALARY_REFERENCE:
        if key in title_lower:
            return SALARY_REFERENCE[key].get(seniority, SALARY_REFERENCE[key]["mid"])
    return SALARY_REFERENCE["default"].get(seniority, SALARY_REFERENCE["default"]["mid"])
```

### B3.3 Industry Adjacency: `services/api/app/services/industry_map.py` (NEW)

```python
INDUSTRY_ADJACENCY = {
    "healthcare": {"health insurance", "pharmaceuticals", "biotech", "medical devices"},
    "banking": {"financial services", "insurance", "fintech", "investment management"},
    "government": {"defense", "aerospace", "public sector", "federal"},
    "technology": {"saas", "telecommunications", "software", "internet"},
    "energy": {"utilities", "oil and gas", "renewables", "power generation"},
    "manufacturing": {"automotive", "industrial", "consumer goods", "supply chain"},
    "construction": {"real estate", "architecture", "civil engineering", "infrastructure"},
    "education": {"edtech", "higher education", "k-12", "training"},
    "retail": {"ecommerce", "consumer goods", "hospitality", "food service"},
}

def are_industries_adjacent(industry_a: str, industry_b: str) -> bool:
    """Return True if two industries are the same or adjacent."""
    a_lower = industry_a.lower().strip()
    b_lower = industry_b.lower().strip()
    if a_lower == b_lower:
        return True
    for canonical, adjacents in INDUSTRY_ADJACENCY.items():
        all_in_group = {canonical} | adjacents
        if a_lower in all_in_group and b_lower in all_in_group:
            return True
    return False
```

---

## B4: Job Parser Service

**File to create:** `services/api/app/services/job_parser.py` (NEW)

Implement `JobParserService` with these extraction stages:

### B4.1 Title normalization
- Expand abbreviations: "Sr." → "Senior", "Jr." → "Junior", "Mgr" → "Manager", "Dev" → "Developer"
- Detect seniority: entry/mid/senior/lead/principal/director/vp/c_level
- Strip internal codes: "Job ID: 12345" or "Req #ABC123"

### B4.2 Employment type extraction
- Scan for "full-time", "part-time", "contract", "freelance", "internship", "temp-to-hire"
- Default to "full_time" if not stated

### B4.3 Location parsing
- Extract city, state, country from location string
- Detect "Remote", "Hybrid", "Onsite" from description
- Handle "multiple locations" and "anywhere in US"

### B4.4 Salary extraction
- Regex patterns for "$120K", "$120,000", "$120k-$150k", "$55/hr", "120,000–150,000 per year"
- If no salary stated: use `salary_reference.py` to infer range (set `compensation_confidence = "inferred"`)
- Extract benefits keywords: 401k, health, dental, equity, stock, PTO, unlimited PTO

### B4.5 Requirements extraction
- Split "Requirements" / "Qualifications" section into required vs. preferred
- Look for language signals: "must have", "required", "minimum" → `is_must_have = true`
- "preferred", "nice to have", "bonus", "ideally" → `is_must_have = false`
- Extract years of experience: "5+ years", "3-5 years experience"
- Extract education requirements: "Bachelor's degree required", "BS/MS in Computer Science"
- Extract certifications: "PMP preferred", "CISSP required"

### B4.6 Company intelligence
- Infer industry from company name and job description context
- Detect company size signals: "startup", "Fortune 500", "Series B", "small team"
- Extract department, reporting structure, team size

### B4.7 Posting quality score (0–100)
Score based on completeness:
- Has salary info: +15
- Has clear requirements section: +20
- Has company description: +10
- Has benefits listed: +10
- Description > 200 words: +15
- Has specific responsibilities: +15
- Has education requirement stated: +5
- Has location clearly stated: +10

---

## B5: Fraud & Duplicate Detector

**File to create:** `services/api/app/services/job_fraud_detector.py` (NEW)

### B5.1 Fraud scoring

Check for red flags and compute a fraud score:

```python
FRAUD_SIGNALS = [
    {"pattern": r"(wire transfer|western union|money order|bitcoin payment)", "flag": "payment_scam", "severity": "critical", "score": 40},
    {"pattern": r"(no experience needed|no experience required).*\$\d{3,}", "flag": "too_good", "severity": "high", "score": 25},
    {"pattern": r"(personal bank|social security|passport number|SSN)", "flag": "pii_harvest", "severity": "critical", "score": 40},
    {"pattern": r"(work from home|remote).*\$\d{4,}.*\b(week|daily)\b", "flag": "income_scam", "severity": "high", "score": 30},
    {"pattern": r"(gmail\.com|yahoo\.com|hotmail\.com).*@.*hiring", "flag": "personal_email", "severity": "medium", "score": 15},
]

def compute_fraud_score(job_description: str, company: str) -> tuple[int, list[dict]]:
    """
    Returns (fraud_score, red_flags_list).
    fraud_score >= 50 → is_likely_fraudulent = True
    """
```

Also flag:
- Description < 50 words (suspiciously vague)
- No company name
- Salary unreasonably high for the role level

### B5.2 Duplicate detection (4 layers)

Implement from PROMPT10:
- **Layer 1:** Exact URL or source_id match
- **Layer 2:** Normalized title + company (fuzzy, Levenshtein ≤ 2) + location match
- **Layer 3:** Description Jaccard similarity > 0.80 + same company
- **Layer 4:** Same company + same title + posted within 14 days

Assign `dedup_group_id` (UUID) to all jobs in a duplicate cluster. Earliest `first_seen_at` is the canonical record.

### B5.3 Staleness detection

- `first_seen_at` > 90 days AND `last_seen_at` > 30 days → `is_active = false`
- On each ingestion run, update `last_seen_at` for re-seen jobs

---

## B6: Enhanced Match Scoring — 6-Dimension Composite

**File to modify:** `services/api/app/services/matching.py`

When `job_parsed_details` exists for a job, use the 6-dimension deep scoring instead of the basic keyword overlap. Fall back to existing logic if no parsed details.

### B6.1 Composite formula

```python
DIMENSION_WEIGHTS = {
    "skills": 0.30,
    "experience": 0.25,
    "certifications": 0.10,
    "location": 0.15,
    "compensation": 0.10,
    "title": 0.10,
}

def compute_deep_match_score(profile_json: dict, parsed_details: JobParsedDetail) -> tuple[int, dict]:
    """
    Returns (composite_score 0-100, reasons_dict_with_per_dimension_breakdown).
    """
```

Each dimension scorer (0–100) per PROMPT10:
- **Skills (0.30):** Required skills match with synonym support, preferred skills at 50% weight
- **Experience (0.25):** Years fit + industry/domain match + responsibility alignment + budget/scope signals
- **Certifications (0.10):** Required cert match (default 80 if no certs required)
- **Location (0.15):** Remote/onsite/hybrid compatibility + geographic proximity
- **Compensation (0.10):** Salary range overlap between candidate preferences and job range
- **Title (0.10):** Title alignment (exact=100, related=60, stretch=40, unrelated=10)

Store per-dimension breakdown in `match.reasons` JSON:

```json
{
  "skills": {"score": 82, "matched": [...], "missing": [...], "synonyms_used": [...]},
  "experience": {"score": 75, "years_fit": "exact", "industry_match": "adjacent"},
  "certifications": {"score": 100, "matched": ["PMP"], "missing": []},
  "location": {"score": 90, "mode_fit": "remote_match"},
  "compensation": {"score": 70, "overlap": "partial"},
  "title": {"score": 85, "alignment": "related_stretch"}
}
```

---

## B7: Wire Into Ingestion Pipeline

**File to modify:** `services/api/app/services/ingestion.py` (or equivalent)

After storing a job in the `jobs` table:
1. Run `JobParserService.parse(job)` → populate `job_parsed_details`
2. Run `JobFraudDetector.evaluate(job, parsed_details)` → set fraud flags + dedup
3. If `is_likely_fraudulent = true` → set `jobs.is_active = false`
4. If duplicate found → set `is_duplicate_of_job_id` and `dedup_group_id`

---

## B8: New API Endpoints

### B8.1 Admin reparse

**File to create:** `services/api/app/routers/admin_jobs.py` (NEW)

- `POST /api/admin/jobs/{job_id}/reparse` — re-run parser on one job (admin token required)
- `POST /api/admin/jobs/reparse-all` — enqueue RQ job to re-parse all active jobs (admin token required)

### B8.2 Parsed details

**File to create or modify:** `services/api/app/routers/jobs.py`

- `GET /api/jobs/{job_id}/parsed` — returns `job_parsed_details` for a job (auth required)

### B8.3 Register routers

**File to modify:** `services/api/app/main.py`

Import and register the new routers:
```python
from app.routers import admin_jobs, jobs
app.include_router(admin_jobs.router)
app.include_router(jobs.router)
```

---

## B9: Frontend — Match Detail Enhancement

**File to modify:** `apps/web/app/matches/page.tsx`

On each match card or in an expanded detail view, show the per-dimension breakdown when available:

- Skills match: "82/100 — 12 of 15 required skills matched"
- Experience: "75/100 — 8 years (meets 7+ requirement), adjacent industry"
- Certifications: "100/100 — PMP ✅"
- Location: "90/100 — Remote match"
- Compensation: "70/100 — Partial salary overlap ($130K–$180K vs. $120K–$150K)"
- Title: "85/100 — Related title match"

Also show job quality indicator (posting_quality_score) and any red flags.

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Resume parser (enhanced) | `services/api/app/services/profile_parser.py` | MODIFY — add enhanced pipeline |
| Resume disambiguation | `services/api/app/services/resume_disambiguation.py` | CREATE — industry detection, term classification |
| Job parser service | `services/api/app/services/job_parser.py` | CREATE — structured job extraction |
| Fraud detector | `services/api/app/services/job_fraud_detector.py` | CREATE — fraud scoring, dedup, staleness |
| Skill synonyms | `services/api/app/services/skill_synonyms.py` | CREATE — shared synonym table |
| Salary reference | `services/api/app/services/salary_reference.py` | CREATE — embedded salary data |
| Industry adjacency | `services/api/app/services/industry_map.py` | CREATE — industry group mapping |
| JobParsedDetail model | `services/api/app/models/job_parsed_detail.py` | CREATE — SQLAlchemy model |
| Job model (add columns) | `services/api/app/models/job.py` | MODIFY — add is_active, first/last_seen_at |
| Models __init__ | `services/api/app/models/__init__.py` | MODIFY — import JobParsedDetail |
| Matching service | `services/api/app/services/matching.py` | MODIFY — add 6-dimension composite scoring |
| Ingestion pipeline | `services/api/app/services/ingestion.py` (or equivalent) | MODIFY — call parser + fraud after storing jobs |
| Admin jobs router | `services/api/app/routers/admin_jobs.py` | CREATE — reparse endpoints |
| Jobs router | `services/api/app/routers/jobs.py` | CREATE or MODIFY — parsed details endpoint |
| Main app | `services/api/app/main.py` | MODIFY — register new routers |
| Job schemas | `services/api/app/schemas/jobs.py` | CREATE or MODIFY — response schemas for parsed details |
| Match schemas | `services/api/app/schemas/matches.py` | MODIFY — add per-dimension reasons |
| Queue / workers | `services/api/app/services/queue.py` | MODIFY — add reparse_all_jobs worker |
| Alembic migration | `services/api/alembic/versions/` | CREATE — job_parsed_details table + jobs columns |
| Matches page (frontend) | `apps/web/app/matches/page.tsx` | MODIFY — show per-dimension breakdown |
| Admin job quality page | `apps/web/app/admin/job-quality/page.tsx` | CREATE — fraud/quality review |
| Tests | `services/api/tests/` | CREATE — test_resume_disambiguation.py, test_job_parser.py, test_job_fraud_detector.py, test_deep_matching.py |

---

## Implementation Order (for a beginner following in Cursor)

This is a large prompt. Work through it in this exact sequence:

### Phase 1: Shared Reference Data (Steps 1–3)

1. **Step 1:** Create `services/api/app/services/skill_synonyms.py`
2. **Step 2:** Create `services/api/app/services/salary_reference.py`
3. **Step 3:** Create `services/api/app/services/industry_map.py`

### Phase 2: Resume Parser Enhancement — Track A (Steps 4–7)

4. **Step 4:** Create `services/api/app/services/resume_disambiguation.py` with industry detection + term classification
5. **Step 5:** Open `services/api/app/services/profile_parser.py`. Add `classify_bullet`, `split_bullets`, `is_xyz_bullet` functions.
6. **Step 6:** In the same file, update the main parse function to use the enhanced pipeline (A5). Output the upgraded `profile_json` schema.
7. **Step 7:** Test resume parsing:
   ```powershell
   cd services/api
   .\.venv\Scripts\Activate.ps1
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   Upload a resume → parse → verify the new profile_json has duties/accomplishments split, technology categorization, and industry detection.

### Phase 3: Job Parser — Track B Data Model (Steps 8–10)

8. **Step 8:** Create `services/api/app/models/job_parsed_detail.py` (the SQLAlchemy model)
9. **Step 9:** Update `services/api/app/models/__init__.py` to import it. Update `services/api/app/models/job.py` to add `is_active`, `first_seen_at`, `last_seen_at`.
10. **Step 10:** Create and run the Alembic migration:
    ```powershell
    cd services/api
    .\.venv\Scripts\Activate.ps1
    alembic revision --autogenerate -m "add job_parsed_details table and jobs columns"
    alembic upgrade head
    ```

### Phase 4: Job Parser + Fraud Detector (Steps 11–13)

11. **Step 11:** Create `services/api/app/services/job_parser.py` with `JobParserService` class
12. **Step 12:** Create `services/api/app/services/job_fraud_detector.py` with fraud scoring + duplicate detection
13. **Step 13:** Test both services manually against a few job records in the database.

### Phase 5: Integration + API (Steps 14–17)

14. **Step 14:** Modify the ingestion pipeline to call parser + fraud detector after storing jobs.
15. **Step 15:** Create `services/api/app/routers/admin_jobs.py` (reparse endpoints) and `services/api/app/routers/jobs.py` (parsed details endpoint).
16. **Step 16:** Register new routers in `services/api/app/main.py`.
17. **Step 17:** Add schemas in `services/api/app/schemas/jobs.py`.

### Phase 6: Enhanced Matching (Step 18)

18. **Step 18:** Modify `services/api/app/services/matching.py` to add 6-dimension composite scoring. Keep existing logic as fallback when no `job_parsed_details` exists.

### Phase 7: Frontend (Steps 19–20)

19. **Step 19:** Update `apps/web/app/matches/page.tsx` to show per-dimension breakdown.
20. **Step 20:** Create `apps/web/app/admin/job-quality/page.tsx` for admin fraud/quality review.

### Phase 8: Tests + Lint (Steps 21–22)

21. **Step 21:** Create test files:
    - `services/api/tests/test_resume_disambiguation.py`
    - `services/api/tests/test_job_parser.py`
    - `services/api/tests/test_job_fraud_detector.py`
    - `services/api/tests/test_deep_matching.py`
22. **Step 22:** Lint and format:
    ```powershell
    cd services/api
    python -m ruff check .
    python -m ruff format .
    cd apps/web
    npm run lint
    ```

---

## Non-Goals (Do NOT implement in this prompt)

- External API calls for company verification (Crunchbase, LinkedIn API, etc.)
- ML/AI-based fraud detection (keep it deterministic and rule-based)
- Real-time salary data from external APIs (use embedded reference data)
- LLM-assisted parsing (PROMPT4 was deterministic; LLM-based parsing can be a future enhancement)
- Automated job application on behalf of the user
- Scraping any website that prohibits it
- Changes to the profile editor frontend (keep backward-compatible)

---

## Summary Checklist

### Track A — Resume Parser
- [ ] Disambiguation engine: `resume_disambiguation.py` with industry detection + term classification
- [ ] Duty vs. accomplishment splitter with regex signals
- [ ] XYZ-style bullet detection and tagging
- [ ] Enhanced `profile_json` schema with categorized technologies, domain skills, management scope
- [ ] Backward-compatible with existing profile editor and completeness scorer
- [ ] Two-pass validation with `disambiguation_notes`

### Track B — Job Parser + Fraud
- [ ] Alembic migration: `job_parsed_details` table + new `jobs` columns
- [ ] SQLAlchemy model: `JobParsedDetail`
- [ ] `JobParserService`: title normalization, type extraction, location parsing, salary extraction/inference, requirements extraction, company intelligence, quality scoring
- [ ] `JobFraudDetector`: fraud scoring (regex signals), duplicate detection (4 layers), staleness detection
- [ ] Shared reference data: skill synonyms, salary reference, industry adjacency map
- [ ] Integration: parser + fraud detector called during ingestion pipeline
- [ ] API: admin reparse endpoints, job parsed details endpoint
- [ ] Routers registered in main.py

### Enhanced Matching
- [ ] 6-dimension composite scoring (skills 0.30, experience 0.25, certs 0.10, location 0.15, compensation 0.10, title 0.10)
- [ ] Per-dimension breakdown stored in `match.reasons` JSON
- [ ] Fallback to existing keyword matching when no `job_parsed_details`
- [ ] Exclude fraudulent/inactive jobs from candidate-facing results

### Frontend
- [ ] Match cards show per-dimension score breakdown
- [ ] Job quality indicator visible
- [ ] Admin job quality review page

### Tests
- [ ] Unit tests for disambiguation, job parser, fraud detector, deep matching

Return code changes only.
