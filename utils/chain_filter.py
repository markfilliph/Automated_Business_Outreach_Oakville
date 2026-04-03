"""
Chain, franchise, and large corporation filtering (Ontario-calibrated).

Three detection layers:
  1. Brand name match (chains/franchises across all sectors)
  2. Corporate pattern detection (multi-location, investor pages)
  3. URL patterns indicating large operations
"""

import re
from typing import Tuple


# ── Known chains and franchises (Ontario-calibrated, all sectors) ─────────────
KNOWN_CHAINS = [
    # National/international retail chains
    "walmart", "costco", "canadian tire", "home depot", "rona",
    "home hardware", "loblaws", "dollarama", "dollar tree",
    "staples", "best buy", "the source",
    "winners", "marshalls", "homesense",
    "ikea", "structube", "the brick",
    "leon's", "sleep country",

    # Ontario grocery and pharmacy
    "metro", "loblaws", "no frills", "food basics", "freshco",
    "shoppers drug mart", "rexall", "pharmasave",
    "sobeys", "farm boy", "whole foods",
    "longo's", "fortinos", "zehrs",

    # Restaurant and food chains
    "tim hortons", "mcdonald", "subway", "starbucks",
    "a&w", "harvey's", "wendy's", "burger king",
    "pizza hut", "domino", "papa john",
    "swiss chalet", "kelsey's", "east side mario",
    "boston pizza", "montana's", "the keg",
    "popeyes", "chick-fil-a", "five guys",
    "couche-tard", "circle k",
    "dunkin", "second cup",
    "pita pit", "mucho burrito",

    # Automotive chains
    "napa auto", "mr. lube", "jiffy lube", "midas", "speedy",
    "kal tire", "fountain tire", "canadian tire auto",
    "active green+ross", "ok tire",
    "toyota", "honda", "ford", "gm", "chrysler", "bmw", "mercedes",
    "hyundai", "kia", "volkswagen", "nissan", "mazda", "subaru",

    # Banks and financial institutions
    "td bank", "rbc", "bmo", "scotiabank", "cibc",
    "national bank", "hsbc", "tangerine",
    "sun life", "manulife", "great-west",

    # Telecom and utilities
    "bell canada", "rogers", "telus", "fido", "koodo",
    "virgin mobile", "freedom mobile",
    "enbridge", "hydro one", "oakville hydro",

    # Large corporations with Oakville presence
    "ford motor", "ford of canada",
    "siemens", "ge", "general electric",
    "utc aerospace", "collins aerospace",
    "halton healthcare",
    "sheridan college",

    # Construction/hardware franchise chains
    "reno-depot", "lowes", "ace hardware",

    # Service franchises
    "servicemaster", "molly maid", "merry maids",
    "cintas", "unifirst",
    "truly nolen", "orkin", "terminix",
    "u-haul", "budget truck",
    "hertz", "enterprise rent", "avis", "national car",
    "h&r block", "liberty tax",
    "kumon", "sylvan", "oxford learning",
    "anytime fitness", "goodlife", "planet fitness", "la fitness",

    # Real estate franchises
    "re/max", "royal lepage", "keller williams", "century 21",
    "coldwell banker", "sutton group",

    # Gas station chains
    "petro-canada", "esso", "shell", "mobil",
    "ultramar", "pioneer",

    # Plumbing / drain franchise chains
    "rooter-man", "roto-rooter", "mr. rooter", "drain rescue",

    # Hotel chains and franchises
    "7-eleven", "homewood suites", "hilton", "marriott",
    "holiday inn", "best western", "comfort inn", "hampton inn",

    # Waste / facilities management corporations
    "waste management", "bfi", "gfl environmental", "snap-on",

    # Major Canadian/international construction and engineering corporations
    # (these are NYSE/TSX-listed firms — never acquisition targets)
    "pcl constructors", "pcl construction", "ellisdon",
    "aecon", "graham construction", "bird construction", "ledcor",
    "stantec", "wsp", "snc-lavalin", "aecom", "jacobs engineering",
]


# Corporate indicators in business names or descriptions
CORPORATE_PATTERNS = [
    r"\b(inc|corp|ltd|llc|plc|gmbh|s\.a\.|n\.v\.)\b",  # Corporate suffixes
    r"\b(holdings|group of companies|international|global)\b",
    r"\b(division of|a subsidiary|a branch of|operated by)\b",
    r"\b(franchise|franchisee|licensed)\b",
]


def is_chain_or_franchise(name: str, types: str = "", website: str = "") -> Tuple[bool, str]:
    """Check if a business is a known chain, franchise, or large corporation.

    Returns (is_chain: bool, reason: str).
    """
    name_lower = name.lower().strip()
    types_lower = types.lower()
    combined = name_lower + " " + types_lower

    # Layer 1: Brand name match (word-boundary to avoid "ge" matching "agency")
    for chain in KNOWN_CHAINS:
        pattern = r'\b' + re.escape(chain.lower()) + r'\b'
        if re.search(pattern, name_lower):
            return True, f"Known chain: {chain}"

    # Layer 2: Corporate pattern detection
    for pattern in CORPORATE_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            # "franchise" or "franchisee" is a strong signal
            if "franchise" in combined or "franchisee" in combined:
                return True, "Franchise indicator in name/description"
            # "division of" or "subsidiary" is a strong signal
            if "division of" in combined or "subsidiary" in combined:
                return True, "Subsidiary/division indicator"

    # Layer 3: Multi-location indicators
    multi_location_patterns = [
        r"\b\d+\s*locations?\b",
        r"\bnationwide\b",
        r"\bacross canada\b",
        r"\bcoast to coast\b",
    ]
    for pattern in multi_location_patterns:
        if re.search(pattern, combined, re.IGNORECASE):
            return True, "Multi-location indicator"

    return False, ""
