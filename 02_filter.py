"""
STEP 2: FILTER CANDIDATES (Oakville: Minimal Exclusions)

Applies 5 filtering gates in sequence:
  Gate 1: Geographic — must be in Oakville postal prefixes or lat/lng bounds
  Gate 2: Sector exclusion — law firms, immigration, retail, restaurants + non-business
  Gate 3: Chain/franchise — known chains and large corporations
  Gate 4: Subsidiary — subsidiaries of publicly traded / multinational parents
  Gate 5: Employee range — must be plausibly 5-200 employees (from Google signals)

NOTE: This pipeline uses MINIMAL exclusions. Most business types pass through.
The broker and human reviewer decide final fit. We cast a wide net here.

Input:  data/raw_candidates.csv
Output: data/filtered_candidates.csv
"""

import pandas as pd
import re
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from config import (
    CHECKPOINT_RAW,
    CHECKPOINT_FILTERED,
    EXCLUDED_SECTOR_KEYWORDS,
    TARGET_POSTAL_PREFIXES,
    GEO_BOUNDS,
    MIN_EMPLOYEES,
    MAX_EMPLOYEES,
    CHAIN_FILTER_ENABLED,
    SUBSIDIARY_FILTER_ENABLED,
)
from utils.chain_filter import is_chain_or_franchise
from utils.subsidiary_detector import is_subsidiary


_RESIDENTIAL_STREET_TYPES = [
    # Full names
    "crescent", "drive", "court", "terrace", "trail",
    "way", "lane", "circle", "place", "grove", "gardens", "heights",
    # Google Maps abbreviations
    "cres", "dr", "crt", "ct", "terr", "trl", "ln", "cir", "pl", "hts",
]
_COMMERCIAL_INDICATORS = [
    "industrial", "business park", "unit", "suite", "floor", "#",
]


def is_likely_residential(address):
    """Return True if address looks like a home address.

    Positive signal: contains a residential street type.
    Negative signal (commercial override): contains a unit/suite/industrial marker.
    """
    if not address or pd.isna(address):
        return False
    addr_lower = str(address).lower()
    has_residential = any(
        re.search(r'\b' + re.escape(st) + r'\b', addr_lower)
        for st in _RESIDENTIAL_STREET_TYPES
    )
    has_commercial = any(ind in addr_lower for ind in _COMMERCIAL_INDICATORS)
    return has_residential and not has_commercial


ADJACENT_MUNICIPALITY_PREFIXES = {
    # Burlington
    "L7L", "L7M", "L7N", "L7R", "L7S", "L7T",
    # Mississauga
    "L5J", "L5K", "L5L", "L5A", "L5B", "L5C", "L5G", "L5H",
}


def gate_geography(df):
    """Gate 1: Must be within Oakville geographic boundaries.

    Two-stage filter:
      Stage A: keep if address contains an Oakville postal prefix OR
               falls within lat/lng bounds.
      Stage B: hard-exclude any lead whose address contains a known
               adjacent-municipality prefix (Burlington, Mississauga),
               even if it slipped through Stage A via lat/lng overlap.
    """
    before = len(df)

    # Stage A: postal prefix OR lat/lng bounds
    has_postal = df["address_raw"].str.contains(
        "|".join(TARGET_POSTAL_PREFIXES), case=False, na=False
    )
    in_bounds = (
        (df["lat"] >= GEO_BOUNDS["south"]) &
        (df["lat"] <= GEO_BOUNDS["north"]) &
        (df["lng"] >= GEO_BOUNDS["west"]) &
        (df["lng"] <= GEO_BOUNDS["east"])
    )
    df = df[has_postal | in_bounds].copy()
    after_stage_a = len(df)

    # Stage B: hard-exclude known adjacent-municipality postal prefixes
    adjacent_pattern = "|".join(ADJACENT_MUNICIPALITY_PREFIXES)
    in_adjacent = df["address_raw"].str.contains(
        adjacent_pattern, case=False, na=False
    )
    n_adjacent = in_adjacent.sum()
    df = df[~in_adjacent].copy()

    after = len(df)
    print(f"  Gate 1 (Geography):  {before} -> {after}  (removed {before - after})"
          f"  [stage A: -{before - after_stage_a}, adjacent spill: -{n_adjacent}]")
    return df


def gate_sector_exclusion(df):
    """Gate 2: Exclude hard-excluded sectors (law, immigration, retail, restaurant)."""
    before = len(df)

    # Build a combined text field for matching
    df["_match_text"] = (
        df["company_name"].fillna("").str.lower() + " " +
        df.get("industry_description", pd.Series([""] * len(df))).fillna("").str.lower() + " " +
        df["google_types"].fillna("").str.lower() + " " +
        df["address_raw"].fillna("").str.lower()
    )

    mask = pd.Series([False] * len(df), index=df.index)
    for keyword in EXCLUDED_SECTOR_KEYWORDS:
        kw_lower = keyword.lower().strip()
        if kw_lower:
            mask = mask | df["_match_text"].str.contains(kw_lower, na=False, regex=False)

    df = df[~mask].copy()
    df.drop(columns=["_match_text"], inplace=True, errors="ignore")

    after = len(df)
    print(f"  Gate 2 (Sector):     {before} -> {after}  (removed {before - after})")
    return df


def gate_chains(df):
    """Gate 3: Exclude known chains, franchises, and large corporations."""
    if not CHAIN_FILTER_ENABLED:
        print(f"  Gate 3 (Chains):     DISABLED")
        return df

    before = len(df)
    keep_mask = []

    for _, row in df.iterrows():
        name = str(row.get("company_name", ""))
        types = str(row.get("google_types", ""))
        is_chain, _ = is_chain_or_franchise(name, types)
        keep_mask.append(not is_chain)

    df = df[keep_mask].copy()
    after = len(df)
    print(f"  Gate 3 (Chains):     {before} -> {after}  (removed {before - after})")
    return df


def gate_subsidiaries(df):
    """Gate 4: Exclude subsidiaries of publicly traded / multinational parents."""
    if not SUBSIDIARY_FILTER_ENABLED:
        print(f"  Gate 4 (Subsidiary): DISABLED")
        return df

    before = len(df)
    keep_mask = []

    for _, row in df.iterrows():
        name = str(row.get("company_name", ""))
        desc = str(row.get("industry_description", ""))
        is_sub, _ = is_subsidiary(name, desc)
        keep_mask.append(not is_sub)

    df = df[keep_mask].copy()
    after = len(df)
    print(f"  Gate 4 (Subsidiary): {before} -> {after}  (removed {before - after})")
    return df


def gate_employee_signal(df):
    """Gate 5: Rough employee count signal from Google data.

    At $250K-$500K SDE, businesses typically have 10-75 employees.
    We use review_count and google_types as very rough proxies.
    Businesses with 0 reviews and no indicators are kept (we don't
    want to filter out B2B companies that simply lack online presence).
    We only remove businesses with strong signals of being too small
    (e.g., single-person operations) or too large (corporate offices).
    """
    before = len(df)

    # Remove entries that are clearly individual practitioners
    # (Google types like 'lawyer', 'doctor' are already excluded in Gate 2)
    solo_indicators = [
        "notary_public", "insurance_agency",
        "travel_agency", "real_estate_agency",
    ]

    # Only flag if review count is very low (suggesting micro-operation)
    # AND the type strongly suggests solo practice
    mask_too_small = pd.Series([False] * len(df), index=df.index)
    for indicator in solo_indicators:
        type_match = df["google_types"].str.contains(indicator, case=False, na=False)
        low_reviews = df["review_count"].fillna(0).astype(float) < 3
        mask_too_small = mask_too_small | (type_match & low_reviews)

    df = df[~mask_too_small].copy()
    after = len(df)
    print(f"  Gate 5 (Employees):  {before} -> {after}  (removed {before - after})")
    return df


def main():
    print("=" * 60)
    print(" STEP 2: FILTER CANDIDATES (Oakville Minimal Exclusions)")
    print("=" * 60)

    df = pd.read_csv(CHECKPOINT_RAW)
    print(f"  [INPUT] {len(df)} raw candidates from {CHECKPOINT_RAW}")
    print()

    # Apply gates in sequence
    df = gate_geography(df)
    df = gate_sector_exclusion(df)
    df = gate_chains(df)
    df = gate_subsidiaries(df)
    df = gate_employee_signal(df)

    # Annotate residential addresses (non-blocking — does not filter)
    df["residential_flag"] = df["address_raw"].apply(is_likely_residential)
    residential_count = df["residential_flag"].sum()
    print(f"  Residential flag:    {residential_count} addresses flagged as likely home-based")

    print()
    print(f"  [OUTPUT] {len(df)} filtered candidates -> {CHECKPOINT_FILTERED}")

    os.makedirs(os.path.dirname(CHECKPOINT_FILTERED), exist_ok=True)
    df.to_csv(CHECKPOINT_FILTERED, index=False, encoding="utf-8")

    # Category summary
    print(f"\n  Google type summary (top 10 after filtering):")
    type_counts = {}
    for types_str in df["google_types"]:
        if pd.notna(types_str):
            for t in str(types_str).split(","):
                t = t.strip()
                if t:
                    type_counts[t] = type_counts.get(t, 0) + 1
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    {t:35s} {c:>4}")


if __name__ == "__main__":
    main()
