"""
Resume disambiguation engine.

Industry-aware classification for resume terms, technology categorization,
and role category detection. Called by the enhanced parser pipeline after
text extraction, before structured output.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Classification hierarchy constants
# ---------------------------------------------------------------------------

ALWAYS_TECHNOLOGY = {
    "tableau",
    "jira",
    "confluence",
    "servicenow",
    "salesforce",
    "sap",
    "workday",
    "peoplesoft",
    "dynamics 365",
    "netsuite",
    "hubspot",
    "zendesk",
    "slack",
    "trello",
    "asana",
    "monday.com",
    "smartsheet",
}

ALWAYS_METHODOLOGY = {
    "agile",
    "scrum",
    "waterfall",
    "kanban",
    "safe",
    "lean",
    "six sigma",
    "itil",
    "togaf",
    "cobit",
    "prince2",
    "dmaic",
    "kaizen",
    "tpm",
    "devops",
    "ci/cd",
    "tdd",
    "bdd",
    "pair programming",
}

ALWAYS_CLOUD = {"aws", "azure", "gcp", "google cloud", "amazon web services"}

ALWAYS_CERTIFICATION = {
    "pmp",
    "cissp",
    "ccna",
    "cpa",
    "aws solutions architect",
    "comptia security+",
    "csm",
    "psm",
    "capm",
    "prince2",
    "itil v4",
    "ceh",
    "oscp",
    "ccnp",
    "cisa",
    "cism",
    "aws certified",
    "google cloud certified",
    "azure certified",
    "comptia a+",
    "comptia network+",
    "six sigma green belt",
    "six sigma black belt",
}

ALWAYS_COMPLIANCE = {
    "hipaa",
    "sox",
    "gdpr",
    "pci-dss",
    "pci dss",
    "ferpa",
    "nerc cip",
    "ccpa",
    "soc2",
    "soc 2",
    "iso 27001",
    "nist",
    "fedramp",
    "itar",
    "fisma",
    "glba",
    "coppa",
}

# ---------------------------------------------------------------------------
# Industry detection
# ---------------------------------------------------------------------------

# (keyword, weight) tuples per industry
INDUSTRY_KEYWORDS: dict[str, list[tuple[str, int]]] = {
    "Information Technology": [
        ("software", 3),
        ("saas", 4),
        ("developer", 3),
        ("devops", 4),
        ("api", 2),
        ("frontend", 3),
        ("backend", 3),
        ("fullstack", 4),
        ("cloud", 2),
        ("microservices", 4),
        ("kubernetes", 4),
        ("docker", 3),
        ("python", 2),
        ("javascript", 2),
        ("react", 3),
        ("machine learning", 4),
        ("data science", 4),
        ("algorithm", 3),
        ("database", 2),
        ("sql", 2),
        ("agile", 2),
        ("sprint", 2),
        ("ci/cd", 3),
        ("deployment", 2),
        ("aws", 3),
        ("azure", 3),
        ("cybersecurity", 4),
        ("infosec", 4),
        ("penetration test", 4),
        ("sre", 4),
        ("site reliability", 4),
        ("linux", 2),
        ("git", 2),
    ],
    "Construction": [
        ("construction", 5),
        ("osha", 4),
        ("nec", 3),
        ("conduit", 3),
        ("blueprints", 3),
        ("general contractor", 5),
        ("subcontractor", 4),
        ("building code", 4),
        ("jobsite", 4),
        ("excavation", 4),
        ("concrete", 3),
        ("structural", 3),
        ("masonry", 4),
        ("hvac", 3),
        ("plumbing", 3),
        ("electrical wiring", 4),
        ("procore", 4),
        ("bluebeam", 4),
        ("autocad", 2),
        ("surveying", 3),
        ("punch list", 4),
        ("change order", 4),
        ("superintendent", 4),
    ],
    "Healthcare": [
        ("hipaa", 4),
        ("patient", 3),
        ("clinical", 3),
        ("ehr", 4),
        ("nursing", 5),
        ("diagnosis", 3),
        ("medical", 3),
        ("hospital", 4),
        ("physician", 4),
        ("pharmacy", 4),
        ("hl7", 4),
        ("fhir", 4),
        ("epic", 3),
        ("cerner", 4),
        ("healthcare", 4),
        ("surgical", 4),
        ("radiology", 4),
        ("pathology", 4),
        ("triage", 4),
        ("rehabilitation", 3),
        ("occupational therapy", 4),
    ],
    "Finance": [
        ("financial", 3),
        ("banking", 4),
        ("investment", 3),
        ("trading", 4),
        ("portfolio", 3),
        ("risk management", 3),
        ("compliance", 2),
        ("audit", 3),
        ("sox", 3),
        ("gaap", 4),
        ("ifrs", 4),
        ("cpa", 4),
        ("accounting", 4),
        ("tax", 3),
        ("revenue", 2),
        ("fintech", 4),
        ("underwriting", 4),
        ("actuarial", 4),
        ("treasury", 3),
        ("derivatives", 4),
        ("hedge fund", 4),
        ("private equity", 4),
    ],
    "Manufacturing": [
        ("manufacturing", 5),
        ("assembly", 3),
        ("production line", 4),
        ("lean manufacturing", 4),
        ("quality control", 3),
        ("iso 9001", 4),
        ("supply chain", 3),
        ("warehouse", 3),
        ("inventory", 2),
        ("logistics", 2),
        ("procurement", 3),
        ("six sigma", 2),
        ("kaizen", 3),
        ("erp", 2),
        ("mrp", 4),
        ("cnc", 4),
        ("cad", 2),
        ("tooling", 3),
        ("injection molding", 4),
        ("fabrication", 3),
    ],
    "Government": [
        ("government", 4),
        ("federal", 4),
        ("dod", 4),
        ("clearance", 3),
        ("public sector", 4),
        ("agency", 2),
        ("classified", 3),
        ("fedramp", 4),
        ("fisma", 4),
        ("nist", 3),
        ("itar", 4),
        ("defense", 3),
        ("military", 3),
        ("va ", 3),
        ("gsa", 4),
        ("acquisition", 2),
        ("far", 3),
        ("contracting officer", 4),
    ],
    "Energy/Utilities": [
        ("energy", 3),
        ("utilities", 4),
        ("power plant", 4),
        ("grid", 3),
        ("scada", 4),
        ("nerc", 4),
        ("renewable", 3),
        ("solar", 3),
        ("wind energy", 4),
        ("oil and gas", 4),
        ("pipeline", 3),
        ("refinery", 4),
        ("drilling", 3),
        ("upstream", 3),
        ("downstream", 3),
        ("substation", 4),
        ("transformer", 3),
        ("transmission", 2),
        ("distribution", 2),
    ],
    "Education": [
        ("education", 3),
        ("curriculum", 4),
        ("teaching", 3),
        ("professor", 4),
        ("university", 3),
        ("k-12", 4),
        ("edtech", 4),
        ("lms", 3),
        ("instructional design", 4),
        ("student", 2),
        ("academic", 3),
        ("research", 2),
        ("ferpa", 4),
        ("dean", 4),
        ("faculty", 3),
        ("pedagogy", 4),
        ("accreditation", 3),
    ],
    "Legal": [
        ("legal", 4),
        ("attorney", 5),
        ("lawyer", 5),
        ("litigation", 4),
        ("paralegal", 4),
        ("contract", 2),
        ("intellectual property", 4),
        ("patent", 3),
        ("trademark", 4),
        ("compliance", 2),
        ("regulatory", 3),
        ("arbitration", 4),
        ("mediation", 4),
        ("discovery", 3),
        ("deposition", 4),
        ("statute", 4),
    ],
    "Marketing": [
        ("marketing", 4),
        ("branding", 3),
        ("seo", 4),
        ("sem", 4),
        ("campaign", 3),
        ("advertising", 3),
        ("social media", 3),
        ("content strategy", 4),
        ("copywriting", 4),
        ("crm", 2),
        ("hubspot", 3),
        ("analytics", 2),
        ("conversion", 3),
        ("lead generation", 3),
        ("brand awareness", 4),
        ("ppc", 4),
        ("email marketing", 3),
        ("market research", 3),
    ],
}

# Certification -> industry mapping
CERT_INDUSTRY: dict[str, str] = {
    "pmp": "Management",
    "capm": "Management",
    "prince2": "Management",
    "cissp": "Information Technology",
    "ceh": "Information Technology",
    "oscp": "Information Technology",
    "ccna": "Information Technology",
    "ccnp": "Information Technology",
    "comptia security+": "Information Technology",
    "comptia a+": "Information Technology",
    "comptia network+": "Information Technology",
    "aws solutions architect": "Information Technology",
    "aws certified": "Information Technology",
    "pe": "Engineering",
    "cpa": "Finance",
    "cfa": "Finance",
    "cisa": "Finance",
    "rn": "Healthcare",
    "lpn": "Healthcare",
    "cna": "Healthcare",
    "osha 30": "Construction",
    "osha 10": "Construction",
}

# Title patterns -> role category
ROLE_CATEGORY_PATTERNS: list[tuple[str, str]] = [
    (r"project\s*manager", "Project Management"),
    (r"program\s*manager", "Program Management"),
    (r"product\s*manager", "Product Management"),
    (r"product\s*owner", "Product Management"),
    (r"scrum\s*master", "Agile/Scrum"),
    (r"software\s*(engineer|developer)", "Software Engineering"),
    (r"web\s*developer", "Software Engineering"),
    (r"full\s*stack", "Software Engineering"),
    (r"front\s*end|frontend", "Software Engineering"),
    (r"back\s*end|backend", "Software Engineering"),
    (r"mobile\s*(developer|engineer)", "Software Engineering"),
    (r"data\s*(scientist|analyst|engineer)", "Data/Analytics"),
    (r"business\s*(analyst|intelligence)", "Data/Analytics"),
    (r"devops|sre|site\s*reliability", "DevOps/SRE"),
    (r"cloud\s*(engineer|architect)", "Cloud/Infrastructure"),
    (r"system\s*(admin|engineer)", "Infrastructure"),
    (r"network\s*(engineer|admin)", "Infrastructure"),
    (r"security\s*(engineer|analyst)", "Cybersecurity"),
    (r"information\s*security", "Cybersecurity"),
    (r"(nurse|rn\b|lpn\b)", "Nursing"),
    (r"physician|doctor|md\b", "Medicine"),
    (r"accountant|cpa\b", "Accounting"),
    (r"financial\s*analyst", "Finance"),
    (r"marketing\s*(manager|director|specialist)", "Marketing"),
    (r"sales\s*(manager|director|representative)", "Sales"),
    (r"human\s*resources|hr\s*(manager|director|generalist)", "Human Resources"),
    (r"designer|ux|ui\b", "Design"),
    (r"qa\s*(engineer|analyst)|quality\s*assurance", "Quality Assurance"),
    (r"technical\s*writer", "Technical Writing"),
    (r"teacher|instructor|professor", "Education"),
    (r"attorney|lawyer|paralegal", "Legal"),
    (r"superintendent|foreman", "Construction Management"),
    (r"(chief|cto|cfo|cio|coo|ceo)", "Executive"),
    (r"(vp|vice\s*president|director)", "Senior Leadership"),
]

# ---------------------------------------------------------------------------
# Technology categorization
# ---------------------------------------------------------------------------

TECH_CATEGORIES: dict[str, str] = {
    # Programming languages
    "python": "Programming Language",
    "javascript": "Programming Language",
    "typescript": "Programming Language",
    "java": "Programming Language",
    "c#": "Programming Language",
    "c++": "Programming Language",
    "go": "Programming Language",
    "golang": "Programming Language",
    "rust": "Programming Language",
    "ruby": "Programming Language",
    "php": "Programming Language",
    "swift": "Programming Language",
    "kotlin": "Programming Language",
    "scala": "Programming Language",
    "r": "Programming Language",
    "matlab": "Programming Language",
    "sql": "Programming Language",
    "perl": "Programming Language",
    "bash": "Programming Language",
    "powershell": "Programming Language",
    # Frameworks
    "react": "Framework",
    "angular": "Framework",
    "vue": "Framework",
    "django": "Framework",
    "flask": "Framework",
    "fastapi": "Framework",
    "spring": "Framework",
    "spring boot": "Framework",
    ".net": "Framework",
    "asp.net": "Framework",
    "express": "Framework",
    "nextjs": "Framework",
    "next.js": "Framework",
    "rails": "Framework",
    "ruby on rails": "Framework",
    "laravel": "Framework",
    "node.js": "Framework",
    "nodejs": "Framework",
    # Databases
    "postgresql": "Database",
    "postgres": "Database",
    "mysql": "Database",
    "mongodb": "Database",
    "redis": "Database",
    "elasticsearch": "Database",
    "oracle": "Database",
    "sql server": "Database",
    "mssql": "Database",
    "dynamodb": "Database",
    "cassandra": "Database",
    "sqlite": "Database",
    "mariadb": "Database",
    "firebase": "Database",
    "neo4j": "Database",
    "couchdb": "Database",
    # Cloud platforms
    "aws": "Cloud Platform",
    "azure": "Cloud Platform",
    "gcp": "Cloud Platform",
    "google cloud": "Cloud Platform",
    "amazon web services": "Cloud Platform",
    "heroku": "Cloud Platform",
    "digitalocean": "Cloud Platform",
    # Containerization/orchestration
    "docker": "Containerization",
    "kubernetes": "Orchestration",
    "k8s": "Orchestration",
    "openshift": "Orchestration",
    "helm": "Orchestration",
    # CI/CD
    "jenkins": "CI/CD",
    "github actions": "CI/CD",
    "gitlab ci": "CI/CD",
    "circleci": "CI/CD",
    "travis ci": "CI/CD",
    "azure devops": "CI/CD",
    "bamboo": "CI/CD",
    "teamcity": "CI/CD",
    # DevOps tools
    "terraform": "DevOps Tool",
    "ansible": "DevOps Tool",
    "puppet": "DevOps Tool",
    "chef": "DevOps Tool",
    "cloudformation": "DevOps Tool",
    "vagrant": "DevOps Tool",
    # Monitoring
    "splunk": "Monitoring Tool",
    "datadog": "Monitoring Tool",
    "pagerduty": "Monitoring Tool",
    "grafana": "Monitoring Tool",
    "prometheus": "Monitoring Tool",
    "new relic": "Monitoring Tool",
    "nagios": "Monitoring Tool",
    "elk stack": "Monitoring Tool",
    # BI/Analytics
    "power bi": "BI/Analytics Tool",
    "tableau": "BI/Analytics Tool",
    "looker": "BI/Analytics Tool",
    "qlik": "BI/Analytics Tool",
    "metabase": "BI/Analytics Tool",
    # Collaboration/project tools
    "jira": "Collaboration Tool",
    "confluence": "Collaboration Tool",
    "trello": "Collaboration Tool",
    "asana": "Collaboration Tool",
    "monday.com": "Collaboration Tool",
    "smartsheet": "Collaboration Tool",
    "slack": "Collaboration Tool",
    "microsoft teams": "Collaboration Tool",
    "procore": "Collaboration Tool",
    "bluebeam": "Collaboration Tool",
    # ERP platforms
    "sap": "ERP Platform",
    "workday": "ERP Platform",
    "netsuite": "ERP Platform",
    "peoplesoft": "ERP Platform",
    "dynamics 365": "ERP Platform",
    # CRM
    "salesforce": "CRM Platform",
    "hubspot": "CRM Platform",
    "servicenow": "CRM Platform",
    "zendesk": "CRM Platform",
    # Design
    "figma": "Design Tool",
    "sketch": "Design Tool",
    "adobe xd": "Design Tool",
    "photoshop": "Design Tool",
    "illustrator": "Design Tool",
    "invision": "Design Tool",
    # Version control
    "git": "Version Control",
    "github": "Version Control",
    "gitlab": "Version Control",
    "bitbucket": "Version Control",
    "svn": "Version Control",
    # Testing
    "selenium": "Testing Tool",
    "cypress": "Testing Tool",
    "jest": "Testing Tool",
    "pytest": "Testing Tool",
    "junit": "Testing Tool",
    "postman": "Testing Tool",
    # CAD/engineering
    "autocad": "CAD/Engineering Tool",
    "solidworks": "CAD/Engineering Tool",
    "revit": "CAD/Engineering Tool",
    "catia": "CAD/Engineering Tool",
    # Data/ML
    "tensorflow": "ML/AI Framework",
    "pytorch": "ML/AI Framework",
    "scikit-learn": "ML/AI Framework",
    "pandas": "Data Library",
    "numpy": "Data Library",
    "spark": "Data Processing",
    "hadoop": "Data Processing",
    "kafka": "Message Queue",
    "rabbitmq": "Message Queue",
    # Healthcare
    "epic": "Healthcare System",
    "cerner": "Healthcare System",
}


def detect_primary_industry(
    resume_text: str, employers: list[str], titles: list[str]
) -> str:
    """
    Determine the candidate's primary industry from the overall resume context.

    Returns one of: "Information Technology", "Construction", "Healthcare",
    "Finance", "Manufacturing", "Government", "Energy/Utilities", "Education",
    "Legal", "Marketing", "Other"

    Algorithm:
    1. Score each industry by weighted keyword density in resume_text
    2. Bonus points for title keywords matching industry
    3. Bonus for certifications matching CERT_INDUSTRY
    4. Return highest scoring industry; "Other" if no score > threshold
    """
    text_lower = resume_text.lower()
    scores: dict[str, float] = {}

    # Phase 1: keyword density scoring
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        total = 0.0
        for keyword, weight in keywords:
            # Count occurrences (capped at 3 to avoid over-counting)
            count = min(3, len(re.findall(re.escape(keyword), text_lower)))
            total += count * weight
        scores[industry] = total

    # Phase 2: title signal bonus (strongest signal)
    titles_combined = " ".join(titles).lower()
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        for keyword, weight in keywords:
            if keyword in titles_combined:
                scores[industry] = scores.get(industry, 0) + weight * 2

    # Phase 3: certification signal
    for cert, industry in CERT_INDUSTRY.items():
        if cert.lower() in text_lower:
            # Map cert industry to our canonical names
            for canonical in INDUSTRY_KEYWORDS:
                if canonical.lower().startswith(industry.lower()[:4]):
                    scores[canonical] = scores.get(canonical, 0) + 8
                    break

    # Return highest scoring industry if above threshold
    if not scores:
        return "Other"

    best_industry = max(scores, key=lambda k: scores[k])
    if scores[best_industry] < 8:
        return "Other"

    return best_industry


def detect_role_category(titles: list[str]) -> str:
    """
    Determine the candidate's primary role category from job titles.

    Uses majority voting across all titles against ROLE_CATEGORY_PATTERNS.
    Returns "General" if no pattern matches.
    """
    if not titles:
        return "General"

    votes: dict[str, int] = {}

    for title in titles:
        title_lower = title.lower()
        for pattern, category in ROLE_CATEGORY_PATTERNS:
            if re.search(pattern, title_lower):
                votes[category] = votes.get(category, 0) + 1
                break  # One vote per title

    if not votes:
        return "General"

    return max(votes, key=lambda k: votes[k])


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

    Applies the classification hierarchy in priority order.
    """
    term_lower = term.lower().strip()

    # Priority 1: positional context
    if is_in_title:
        return "Role"
    if is_after_employer_signal:
        return "Company"
    if is_in_tech_line:
        return "Technology"

    # Priority 2: always-* constant sets
    if term_lower in ALWAYS_COMPLIANCE:
        return "Compliance"
    if term_lower in ALWAYS_CERTIFICATION:
        return "Certification"
    if term_lower in ALWAYS_METHODOLOGY:
        return "Methodology"
    if term_lower in ALWAYS_TECHNOLOGY or term_lower in ALWAYS_CLOUD:
        return "Technology"
    if term_lower in TECH_CATEGORIES:
        return "Technology"

    # Priority 3: industry-specific domain skills
    industry_domain_skills: dict[str, set[str]] = {
        "Construction": {
            "estimating",
            "takeoff",
            "scheduling",
            "rfi",
            "submittal",
            "punch list",
            "change order",
            "safety",
            "leed",
        },
        "Healthcare": {
            "charting",
            "triage",
            "patient care",
            "medication administration",
            "vital signs",
            "discharge planning",
            "case management",
        },
        "Finance": {
            "underwriting",
            "credit analysis",
            "portfolio management",
            "risk assessment",
            "valuation",
            "due diligence",
        },
    }

    for ind, skills in industry_domain_skills.items():
        if industry.lower().startswith(ind.lower()[:4]) and term_lower in skills:
            return "Domain_Skill"

    return "Ambiguous"


def categorize_technology(name: str) -> str:
    """Return the standardized category for a technology name."""
    return TECH_CATEGORIES.get(name.lower().strip(), "Other")


def infer_company_industry(company_name: str, duties: list[str]) -> str | None:
    """
    Infer the industry of a specific company from its name and role duties.

    Uses keyword scoring against INDUSTRY_KEYWORDS, limited to the company
    context (name + duties) rather than the full resume.
    """
    text = (company_name + " " + " ".join(duties)).lower()

    scores: dict[str, float] = {}
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        total = 0.0
        for keyword, weight in keywords:
            if keyword in text:
                total += weight
        if total > 0:
            scores[industry] = total

    if not scores:
        return None

    best = max(scores, key=lambda k: scores[k])
    if scores[best] < 5:
        return None

    return best
