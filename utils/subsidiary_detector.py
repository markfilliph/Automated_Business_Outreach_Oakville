"""
Subsidiary detection for Oakville, Ontario.

Detects businesses that are subsidiaries or divisions of publicly traded
or multinational parent companies. These are not acquirable targets.

Three detection methods:
  1. Known subsidiary list (Oakville-specific large employers)
  2. Name pattern analysis (Holdings, International, etc.)
  3. Description/type pattern analysis
"""

import re
from typing import Tuple


# Known large company operations in Oakville area
KNOWN_SUBSIDIARIES = [
    # Automotive
    "ford motor company of canada",
    "ford of canada",

    # Aerospace and defense
    "collins aerospace",
    "utc aerospace",
    "raytheon",
    "l3harris",

    # Manufacturing multinationals
    "siemens",
    "general electric",
    "ipex",  # Aliaxis subsidiary
    "mancor",  # Part of larger group
    "procor",

    # Pharma and life sciences
    "pfizer",
    "johnson & johnson",
    "abbvie",
    "roche",
    "novartis",
    "astrazeneca",
    "merck",
    "sanofi",
    "bayer",
    "glaxosmithkline", "gsk",

    # Technology multinationals
    "ibm",
    "oracle",
    "sap",
    "microsoft",
    "google",
    "apple",
    "amazon",

    # Waste and environmental
    "waste connections",
    "waste management",
    "gfl environmental",
    "terrapure",

    # Financial services (large)
    "deloitte",
    "kpmg",
    "ernst & young", "ey",
    "pricewaterhousecoopers", "pwc",
    "grant thornton",
    "bdo canada",
    "manulife",
    "sun life",

    # Staffing (large multinationals)
    "randstad",
    "adecco",
    "manpower",
    "robert half",
    "hays",

    # Construction (large national)
    "pcl construction",
    "ellis don",
    "aecon",
    "ledcor",
    "pomerleau",
]


# Patterns in names that suggest large/corporate operations
SUBSIDIARY_NAME_PATTERNS = [
    r"\b(holdings)\b",
    r"\b(capital group|investment group)\b",
    r"\b(north america|americas|worldwide|global)\b",
    r"\b(canada division|canadian operations)\b",
]


def is_subsidiary(name: str, description: str = "") -> Tuple[bool, str]:
    """Check if a business is a subsidiary of a large corporation.

    Returns (is_subsidiary: bool, reason: str).
    """
    name_lower = name.lower().strip()
    combined = name_lower + " " + description.lower()

    # Method 1: Known subsidiary list (word-boundary to avoid "ey" matching "money")
    for sub in KNOWN_SUBSIDIARIES:
        pattern = r'\b' + re.escape(sub.lower()) + r'\b'
        if re.search(pattern, name_lower):
            return True, f"Known subsidiary/multinational: {sub}"

    # Method 2: Name patterns
    for pattern in SUBSIDIARY_NAME_PATTERNS:
        if re.search(pattern, name_lower, re.IGNORECASE):
            return True, f"Corporate pattern in name: {pattern}"

    # Method 3: Description patterns
    desc_patterns = [
        r"subsidiary of",
        r"division of",
        r"a member of",
        r"part of .+ group",
        r"owned by",
        r"a .+ company",
        r"publicly traded",
        r"nyse|nasdaq|tsx",
    ]
    for pattern in desc_patterns:
        if re.search(pattern, combined, re.IGNORECASE):
            return True, f"Subsidiary indicator in description"

    return False, ""
