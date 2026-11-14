"""Very small location → country resolver for job locations (no network)."""

from __future__ import annotations

import re

COUNTRIES: dict[str, str] = {
    "india": "IN", "united states": "US", "usa": "US", "u.s.": "US", "us": "US", "united kingdom": "GB",
    "uk": "GB", "england": "GB", "scotland": "GB", "great britain": "GB", "switzerland": "CH", "australia": "AU",
    "new zealand": "NZ", "canada": "CA", "germany": "DE", "ireland": "IE", "netherlands": "NL", "france": "FR",
    "spain": "ES", "portugal": "PT", "italy": "IT", "sweden": "SE", "norway": "NO", "denmark": "DK",
    "finland": "FI", "poland": "PL", "austria": "AT", "belgium": "BE", "czech republic": "CZ", "czechia": "CZ",
    "romania": "RO", "estonia": "EE", "lithuania": "LT", "singapore": "SG", "japan": "JP", "south korea": "KR",
    "korea": "KR", "china": "CN", "hong kong": "HK", "taiwan": "TW", "united arab emirates": "AE", "uae": "AE",
    "israel": "IL", "brazil": "BR", "mexico": "MX", "argentina": "AR", "colombia": "CO", "chile": "CL",
    "philippines": "PH", "indonesia": "ID", "malaysia": "MY", "vietnam": "VN", "thailand": "TH",
    "south africa": "ZA", "nigeria": "NG", "kenya": "KE", "egypt": "EG", "saudi arabia": "SA", "luxembourg": "LU",
    "turkey": "TR", "greece": "GR", "hungary": "HU", "ukraine": "UA", "serbia": "RS", "bulgaria": "BG",
    "croatia": "HR",
}

CITIES: dict[str, str] = {
    # India
    "bengaluru": "IN", "bangalore": "IN", "hyderabad": "IN", "pune": "IN", "mumbai": "IN", "delhi": "IN",
    "new delhi": "IN", "gurgaon": "IN", "gurugram": "IN", "noida": "IN", "chennai": "IN", "kolkata": "IN",
    "ahmedabad": "IN", "jaipur": "IN", "chandigarh": "IN", "kochi": "IN", "indore": "IN",
    # US
    "san francisco": "US", "new york": "US", "nyc": "US", "seattle": "US", "austin": "US", "boston": "US",
    "chicago": "US", "los angeles": "US", "denver": "US", "atlanta": "US", "mountain view": "US",
    "palo alto": "US", "menlo park": "US", "sunnyvale": "US", "san jose": "US", "redmond": "US",
    "washington, dc": "US", "washington dc": "US", "miami": "US", "dallas": "US", "houston": "US",
    "san diego": "US", "portland": "US", "philadelphia": "US", "pittsburgh": "US", "salt lake city": "US",
    "hawthorne": "US", "bay area": "US", "brooklyn": "US", "phoenix": "US", "raleigh": "US",
    # UK / Europe
    "london": "GB", "manchester": "GB", "edinburgh": "GB", "cambridge, uk": "GB", "bristol": "GB",
    "zurich": "CH", "zürich": "CH", "geneva": "CH", "lausanne": "CH", "basel": "CH", "bern": "CH",
    "dublin": "IE", "berlin": "DE", "munich": "DE", "hamburg": "DE", "frankfurt": "DE", "amsterdam": "NL",
    "paris": "FR", "madrid": "ES", "barcelona": "ES", "lisbon": "PT", "stockholm": "SE", "copenhagen": "DK",
    "oslo": "NO", "helsinki": "FI", "warsaw": "PL", "krakow": "PL", "prague": "CZ", "vienna": "AT",
    "brussels": "BE", "milan": "IT", "tallinn": "EE",
    # APAC / others
    "sydney": "AU", "melbourne": "AU", "brisbane": "AU", "perth": "AU", "canberra": "AU",
    "auckland": "NZ", "wellington": "NZ", "christchurch": "NZ", "toronto": "CA", "vancouver": "CA",
    "montreal": "CA", "ottawa": "CA", "waterloo": "CA", "tokyo": "JP", "seoul": "KR", "dubai": "AE",
    "abu dhabi": "AE", "tel aviv": "IL", "sao paulo": "BR", "são paulo": "BR", "mexico city": "MX",
    "manila": "PH", "jakarta": "ID", "kuala lumpur": "MY", "johannesburg": "ZA", "cape town": "ZA",
}

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA",
    "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

REGIONS: dict[str, set[str]] = {
    "emea": {"GB", "IE", "DE", "NL", "FR", "ES", "PT", "IT", "SE", "NO", "DK", "FI", "PL", "CH", "AT", "BE",
             "AE", "IL", "ZA"},
    "europe": {"GB", "IE", "DE", "NL", "FR", "ES", "PT", "IT", "SE", "NO", "DK", "FI", "PL", "CH", "AT", "BE",
               "CZ", "EE", "RO", "LT"},
    "apac": {"IN", "SG", "AU", "NZ", "JP", "KR", "HK", "PH", "ID", "MY", "VN", "TH"},
    "asia": {"IN", "SG", "JP", "KR", "HK", "PH", "ID", "MY", "VN", "TH", "CN", "TW"},
    "north america": {"US", "CA"},
    "americas": {"US", "CA", "BR", "MX", "AR", "CO", "CL"},
    "latam": {"BR", "MX", "AR", "CO", "CL"},
}

_REMOTE = re.compile(r"\b(remote|anywhere|work from home|wfh|distributed)\b", re.I)
_SPLIT = re.compile(r"\s*(?:;|\||/| or |\n)\s*")


def countries_for(location: str) -> set[str]:
    """Best-effort set of ISO2 countries mentioned in a location string."""
    text = location.strip()
    if not text:
        return set()
    low = text.lower()
    found: set[str] = set()
    for name, code in COUNTRIES.items():
        if len(name) <= 3:
            if re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", low):
                found.add(code)
        elif name in low:
            found.add(code)
    for city, code in CITIES.items():
        if city in low:
            found.add(code)
    for region, codes in REGIONS.items():
        if re.search(rf"\b{re.escape(region)}\b", low):
            found |= codes
    # "Austin, TX" style
    for m in re.finditer(r",\s*([A-Z]{2})\b", text):
        if m.group(1) in US_STATES and m.group(1) != "IN":
            found.add("US")
    return found


def is_remote(location: str) -> bool:
    return bool(_REMOTE.search(location))


def split_locations(location: str) -> list[str]:
    return [p for p in _SPLIT.split(location) if p.strip()]
