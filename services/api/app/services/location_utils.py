"""Shared city/state normalization utilities."""

# State name → 2-letter abbreviation lookup
_STATE_ABBREVIATIONS: dict[str, str] = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "district of columbia": "DC",
}

# Reverse lookup: abbreviation (lowercase) → uppercase abbreviation
_VALID_ABBREVS: set[str] = {v for v in _STATE_ABBREVIATIONS.values()}


def normalize_city(city: str | None) -> str:
    """Normalize city name to Title Case.

    Examples: "new york" → "New York", "SAN FRANCISCO" → "San Francisco"
    Returns empty string for falsy input.
    """
    if not city:
        return ""
    return city.strip().title()


def normalize_state(state: str | None) -> str:
    """Convert state name or abbreviation to 2-char uppercase abbreviation.

    Examples: "california" → "CA", "ca" → "CA", "NY" → "NY"
    Returns empty string if not a valid US state or falsy input.
    """
    if not state:
        return ""
    state = state.strip()
    if len(state) == 2:
        upper = state.upper()
        if upper in _VALID_ABBREVS:
            return upper
        return ""
    return _STATE_ABBREVIATIONS.get(state.lower(), "")
