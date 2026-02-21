"""Industry adjacency map for intelligent matching.

Used to determine if a candidate's industry experience is transferable
to a job's industry.
"""

from __future__ import annotations

ADJACENCY: dict[str, set[str]] = {
    "technology": {"saas", "telecom", "fintech", "edtech", "healthtech", "e-commerce"},
    "saas": {"technology", "fintech", "edtech", "e-commerce"},
    "telecom": {"technology", "media"},
    "fintech": {"technology", "saas", "banking", "financial services"},
    "banking": {"financial services", "insurance", "fintech"},
    "financial services": {"banking", "insurance", "fintech", "consulting"},
    "insurance": {"financial services", "banking", "healthcare"},
    "healthcare": {"health insurance", "pharmaceuticals", "biotech", "healthtech"},
    "health insurance": {"healthcare", "insurance"},
    "pharmaceuticals": {"healthcare", "biotech"},
    "biotech": {"healthcare", "pharmaceuticals"},
    "healthtech": {"healthcare", "technology"},
    "government": {"defense", "aerospace", "public sector"},
    "defense": {"government", "aerospace"},
    "aerospace": {"defense", "government", "manufacturing"},
    "public sector": {"government", "nonprofit"},
    "manufacturing": {"aerospace", "automotive", "industrial"},
    "automotive": {"manufacturing", "industrial"},
    "industrial": {"manufacturing", "automotive", "energy"},
    "energy": {"oil and gas", "utilities", "industrial"},
    "oil and gas": {"energy", "utilities"},
    "utilities": {"energy", "oil and gas"},
    "consulting": {"financial services", "professional services"},
    "professional services": {"consulting", "legal"},
    "legal": {"professional services"},
    "media": {"entertainment", "telecom", "advertising"},
    "entertainment": {"media", "gaming"},
    "gaming": {"entertainment", "technology"},
    "advertising": {"media", "marketing"},
    "marketing": {"advertising", "e-commerce"},
    "retail": {"e-commerce", "consumer goods"},
    "e-commerce": {"retail", "technology", "saas"},
    "consumer goods": {"retail"},
    "education": {"edtech", "nonprofit"},
    "edtech": {"education", "technology", "saas"},
    "nonprofit": {"education", "public sector"},
    "real estate": {"construction", "property management"},
    "construction": {"real estate", "manufacturing"},
    "property management": {"real estate"},
}

# Keywords used to infer industry from job text
_INDUSTRY_KEYWORDS: dict[str, list[str]] = {
    "technology": ["software", "saas", "tech company", "platform"],
    "healthcare": ["hospital", "clinical", "patient", "medical", "healthcare"],
    "banking": ["bank", "banking", "financial institution"],
    "financial services": ["fintech", "investment", "wealth management", "trading"],
    "insurance": ["insurance", "underwriting", "actuarial"],
    "pharmaceuticals": ["pharmaceutical", "pharma", "drug development"],
    "government": ["government", "federal", "state agency", "public sector"],
    "defense": ["defense", "military", "dod", "clearance"],
    "aerospace": ["aerospace", "aviation", "satellite", "space"],
    "manufacturing": ["manufacturing", "factory", "production", "assembly"],
    "retail": ["retail", "store", "merchandise", "consumer"],
    "e-commerce": ["e-commerce", "ecommerce", "online retail", "marketplace"],
    "energy": ["energy", "renewable", "solar", "wind"],
    "oil and gas": ["oil", "gas", "petroleum", "refinery", "upstream"],
    "consulting": ["consulting", "advisory", "consultant"],
    "education": ["university", "school", "education", "academic"],
    "media": ["media", "news", "publishing", "broadcast"],
    "advertising": ["advertising", "ad tech", "agency"],
    "real estate": ["real estate", "property", "realty"],
    "construction": ["construction", "building", "contractor"],
    "telecom": ["telecom", "telecommunications", "wireless"],
    "automotive": ["automotive", "vehicle", "car"],
}


def are_adjacent(a: str, b: str) -> bool:
    """Return True if industries a and b are the same or adjacent."""
    a_lower, b_lower = a.lower(), b.lower()
    if a_lower == b_lower:
        return True
    adjacent = ADJACENCY.get(a_lower, set())
    return b_lower in adjacent


def infer_industry(text: str, company: str) -> str | None:
    """Infer industry from job description text and company name.

    Returns the best-matching industry or None.
    """
    combined = f"{text} {company}".lower()
    best_industry = None
    best_count = 0

    for industry, keywords in _INDUSTRY_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in combined)
        if count > best_count:
            best_count = count
            best_industry = industry

    return best_industry if best_count > 0 else None
