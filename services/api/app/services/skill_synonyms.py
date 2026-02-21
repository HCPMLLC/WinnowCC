"""Skill synonym mapping for intelligent matching.

Each group is a set of interchangeable skill names.  The first element
of each tuple is treated as the canonical form.
"""

from __future__ import annotations

SYNONYM_GROUPS: list[set[str]] = [
    # Agile family
    {"agile", "scrum", "safe", "kanban", "lean agile"},
    # Microsoft Project
    {"ms project", "microsoft project"},
    # JavaScript ecosystem
    {"javascript", "js", "ecmascript"},
    {"typescript", "ts"},
    # Python
    {"python", "python3", "python 3"},
    # AWS
    {"aws", "amazon web services"},
    # Azure
    {"azure", "microsoft azure"},
    # GCP
    {"gcp", "google cloud", "google cloud platform"},
    # React ecosystem
    {"react", "reactjs", "react.js"},
    # Node ecosystem
    {"node", "nodejs", "node.js"},
    # Vue
    {"vue", "vuejs", "vue.js"},
    # Angular
    {"angular", "angularjs"},
    # Next.js
    {"nextjs", "next.js"},
    # Databases
    {"postgres", "postgresql"},
    {"mongodb", "mongo"},
    {"mssql", "sql server", "microsoft sql server"},
    # Docker / K8s
    {"kubernetes", "k8s"},
    # CI/CD
    {"ci/cd", "cicd", "continuous integration", "continuous deployment"},
    # .NET
    {".net", "dotnet", "asp.net"},
    # C#
    {"c#", "csharp"},
    # C++
    {"c++", "cpp"},
    # Machine Learning
    {"machine learning", "ml"},
    {"artificial intelligence", "ai"},
    {"deep learning", "dl"},
    {"natural language processing", "nlp"},
    # DevOps
    {"devops", "dev ops"},
    {"site reliability", "sre"},
    {"infrastructure as code", "iac"},
    # PM tools
    {"jira", "atlassian jira"},
    {"confluence", "atlassian confluence"},
    # Business Intelligence
    {"business intelligence", "bi"},
    {"power bi", "powerbi", "microsoft power bi"},
    # Methodologies
    {"test driven development", "tdd"},
    {"behavior driven development", "bdd"},
    # Project management certifications
    {"pmp", "project management professional"},
    {"csm", "certified scrum master"},
    # Spring
    {"spring boot", "springboot"},
    # Golang
    {"go", "golang"},
    # Objective-C
    {"objective-c", "objc"},
    # Terraform
    {"terraform", "hashicorp terraform"},
]

# Build lookup: lowered skill → canonical (first element of its group)
_CANONICAL_MAP: dict[str, str] = {}
_GROUP_MAP: dict[str, int] = {}  # lowered skill → group index

for _idx, _group in enumerate(SYNONYM_GROUPS):
    _canonical = sorted(_group)[0]  # deterministic canonical
    # Use the longest form as canonical for readability
    _canonical = max(_group, key=len)
    for _skill in _group:
        _CANONICAL_MAP[_skill.lower()] = _canonical.lower()
        _GROUP_MAP[_skill.lower()] = _idx


def get_canonical(skill: str) -> str:
    """Return the canonical form of a skill, or the original if not mapped."""
    return _CANONICAL_MAP.get(skill.lower(), skill.lower())


def are_synonyms(a: str, b: str) -> bool:
    """Return True if a and b belong to the same synonym group."""
    a_lower, b_lower = a.lower(), b.lower()
    if a_lower == b_lower:
        return True
    a_group = _GROUP_MAP.get(a_lower)
    b_group = _GROUP_MAP.get(b_lower)
    if a_group is None or b_group is None:
        return False
    return a_group == b_group


def expand_skill(skill: str) -> set[str]:
    """Return all synonyms for a skill (including itself)."""
    idx = _GROUP_MAP.get(skill.lower())
    if idx is None:
        return {skill.lower()}
    return {s.lower() for s in SYNONYM_GROUPS[idx]}
