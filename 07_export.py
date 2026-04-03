"""
STEP 7: EXPORT CSV (Hamilton Standard Format)

Reads scored_candidates.csv and exports a clean CSV matching the
Hamilton MVP's Burlington STANDARDIZED format (17 fields).

Hamilton Standard Fields (17):
  1.  business_name
  2.  address
  3.  city
  4.  postal_code
  5.  website
  6.  phone
  7.  owner_name
  8.  owner_confidence
  9.  owner_source
  10. industry
  11. category_standardized
  12. employee_range_estimate
  13. revenue_range_estimate
  14. sde_range_estimate
  15. age_range_estimate
  16. acquisition_fit_score
  17. important_notes

Input:  data/scored_candidates.csv
Output: data/top_100_for_review.csv
"""

import re
import sys
import os
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from utils.employee_estimator import estimate_employee_range
from config import (
    CHECKPOINT_SCORED,
    OUTPUT_FINAL,
    TARGET_FINAL_LEADS,
    QUALIFICATION_THRESHOLD,
    INDUSTRY_MARGINS,
    TARGET_SDE_LOW,
    TARGET_SDE_HIGH,
)


STANDARD_FIELDS = [
    "business_name",
    "address",
    "city",
    "postal_code",
    "website",
    "phone",
    "owner_name",
    "owner_confidence",
    "owner_source",
    "industry",
    "category_standardized",
    "employee_range_estimate",
    "revenue_range_estimate",
    "sde_range_estimate",
    "age_range_estimate",
    "acquisition_fit_score",
    "important_notes",
]


# ── Category classification ───────────────────────────────────────────────────

CATEGORY_RULES = [
    # Manufacturing (more specific first)
    (["machining", "cnc", "precision", "tool and die"], "Precision Manufacturing"),
    (["plastics", "injection", "mold"], "Plastics Manufacturing"),
    (["metal", "steel", "welding", "fabricat"], "Metal Fabrication"),
    (["wood", "millwork", "cabinet", "carpentry"], "Wood / Millwork"),
    (["printing", "print", "label", "packaging"], "Printing & Packaging"),
    (["food processing", "food manufacturing"], "Food Processing"),
    (["manufactur", "factory", "production", "assembly"], "Light Manufacturing"),
    # Construction and trades
    (["electrical", "electrician", "wiring"], "Electrical Contractor"),
    (["plumbing", "plumber"], "Plumbing Contractor"),
    (["hvac", "heating", "cooling", "air conditioning", "ventilation"], "HVAC / Mechanical"),
    (["roofing", "roofer", "siding"], "Roofing Contractor"),
    (["excavation", "grading", "concrete", "paving", "asphalt"], "Heavy Construction"),
    (["construction", "renovation", "general contractor", "builder"], "General Contractor"),
    (["demolition", "abatement"], "Demolition"),
    (["insulation", "drywall", "masonry", "framing"], "Specialty Trades"),
    (["fire protection", "sprinkler", "elevator"], "Building Systems"),
    # Transportation and logistics
    (["transport", "trucking", "freight", "shipping"], "Transportation / Logistics"),
    (["warehouse", "warehousing", "distribution", "3pl"], "Warehousing / Distribution"),
    (["courier", "delivery", "moving"], "Courier / Moving"),
    # Professional and technical
    (["engineering", "engineer"], "Engineering Services"),
    (["architecture", "architect"], "Architecture"),
    (["it service", "software", "managed service", "technology"], "IT / Technology Services"),
    (["consulting"], "Consulting / Professional Services"),
    (["surveying", "geotechnical"], "Surveying / Geotechnical"),
    (["testing", "laboratory", "inspection"], "Testing / Inspection"),
    (["staffing", "recruitment", "placement"], "Staffing / Recruitment"),
    # Wholesale and distribution
    (["wholesale", "distributor", "supply", "supplier"], "Wholesale / Distribution"),
    # Specialized services
    (["cleaning", "janitorial"], "Cleaning Services"),
    (["landscaping", "lawn", "property maintenance"], "Landscaping"),
    (["security", "guard", "alarm", "surveillance"], "Security Services"),
    (["pest control", "extermination"], "Pest Control"),
    (["auto body", "collision", "auto repair"], "Automotive Services"),
    (["towing"], "Towing / Recovery"),
    (["waste", "recycling", "disposal"], "Waste Management"),
    (["sign", "signage", "graphics"], "Signage / Display"),
    (["equipment", "rental", "leasing"], "Equipment Services"),
    # Healthcare
    (["dental", "dentist"], "Dental Practice"),
    (["physio", "rehabilitation"], "Physiotherapy / Rehab"),
    (["veterinary", "vet clinic", "animal"], "Veterinary Services"),
    (["chiropract"], "Chiropractic"),
    (["optom", "optical"], "Optometry"),
    (["medical clinic", "walk-in", "home care", "home health"], "Healthcare Services"),
    # Financial
    (["accounting", "accountant", "cpa", "bookkeep"], "Accounting / Financial"),
    (["insurance", "broker"], "Insurance Services"),
    (["property management", "real estate"], "Property Management"),
]


def classify_category(text):
    """Classify a business into a standardized category based on keywords."""
    text_lower = text.lower()
    for keywords, category in CATEGORY_RULES:
        if any(re.search(r'\b' + re.escape(kw), text_lower) for kw in keywords):
            return category
    return "General Business"


def format_revenue_range(low, high):
    """Format revenue range: '$1.8M-$3.1M' or '$500K-$900K'."""
    def fmt(val):
        if val >= 1_000_000:
            return f"${val/1_000_000:.1f}M"
        elif val >= 1000:
            return f"${val/1000:.0f}K"
        else:
            return f"${val:.0f}"
    return f"{fmt(low)}-{fmt(high)}"


def format_sde_range(sde_low, sde_high):
    """Format SDE range."""
    def fmt(val):
        if val >= 1_000_000:
            return f"${val/1_000_000:.1f}M"
        elif val >= 1000:
            return f"${val/1000:.0f}K"
        else:
            return f"${val:.0f}"
    return f"{fmt(sde_low)}-{fmt(sde_high)}"


def format_age_range(row):
    """Format business age from available date fields, falling back to review-count estimate."""
    reg_date = row.get("registration_date") or row.get("established_date")
    if pd.notna(reg_date) and reg_date is not None:
        try:
            reg = pd.to_datetime(reg_date)
            years = (datetime.now() - reg).days / 365.25
            if years >= 30:
                return "30+ years"
            elif years >= 20:
                return "20-30 years"
            elif years >= 15:
                return "15-20 years"
            elif years >= 10:
                return "10-15 years"
            elif years >= 5:
                return "5-10 years"
            elif years >= 2:
                return "2-5 years"
            else:
                return "<2 years"
        except Exception:
            pass

    # Fallback: estimated_years from review count proxy
    est = row.get("estimated_years")
    if est is not None and pd.notna(est):
        try:
            y = float(est)
            if y >= 15:
                return "15+ years (est.)"
            elif y >= 10:
                return "10-15 years (est.)"
            elif y >= 5:
                return "5-10 years (est.)"
            elif y >= 2:
                return "2-5 years (est.)"
            else:
                return "<2 years (est.)"
        except (ValueError, TypeError):
            pass

    return "Unknown"


def format_employee_range(emp_count):
    """Format employee count into a range."""
    if pd.isna(emp_count) or emp_count is None:
        return "Unknown"

    try:
        emp = int(float(emp_count))
        if emp <= 5:
            return "1-5"
        elif emp <= 10:
            return "5-10"
        elif emp <= 20:
            return "10-20"
        elif emp <= 35:
            return "15-35"
        elif emp <= 50:
            return "25-50"
        elif emp <= 75:
            return "50-75"
        elif emp <= 100:
            return "75-100"
        elif emp <= 200:
            return "100-200"
        else:
            return f"{emp}+"
    except Exception:
        return "Unknown"


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


def compose_notes(row, category):
    """Compose the important_notes field."""
    notes_parts = []

    # Residential address flag (prepended so broker sees it immediately)
    address = row.get("address_raw", "") or row.get("address", "")
    if is_likely_residential(address):
        notes_parts.append("FLAG: Residential address (likely home-based)")

    # Category tag
    notes_parts.append(f"Category: {category}")

    # SDE fit assessment with confidence signal
    sde_low = row.get("estimated_sde_low", 0)
    sde_high = row.get("estimated_sde_high", 0)
    rev_conf = row.get("revenue_confidence", 0)
    if pd.notna(sde_low) and float(sde_low) > 0:
        if float(sde_low) <= TARGET_SDE_HIGH and float(sde_high) >= TARGET_SDE_LOW:
            notes_parts.append("SDE estimate overlaps target range")
        elif float(sde_high) < TARGET_SDE_LOW:
            notes_parts.append("REVIEW: SDE estimate below target range")
        elif float(sde_low) > TARGET_SDE_HIGH:
            notes_parts.append("REVIEW: SDE estimate above target range")

    # Confidence signal (Gemini catch: broker needs to know estimate quality)
    if pd.notna(rev_conf):
        conf = float(rev_conf)
        if conf >= 60:
            notes_parts.append("Estimate confidence: HIGH (multiple data signals)")
        elif conf >= 40:
            notes_parts.append("Estimate confidence: MODERATE (limited signals)")
        else:
            notes_parts.append("Estimate confidence: LOW (verify revenue manually)")

    # Qualification status
    score = row.get("total_score", 0)
    if float(score) >= 70:
        notes_parts.append("High acquisition fit; priority follow-up")
    elif float(score) >= 55:
        notes_parts.append("Good acquisition fit; worth investigating")
    elif float(score) >= QUALIFICATION_THRESHOLD:
        notes_parts.append("Moderate fit; review recommended")
    else:
        notes_parts.append("Below threshold; manual review needed")

    # Revenue confidence
    rev_conf = row.get("revenue_confidence", 0)
    if pd.notna(rev_conf) and float(rev_conf) >= 50:
        notes_parts.append("Reasonable revenue confidence")

    # Verification status
    if row.get("website_valid") == True or str(row.get("website_valid")).lower() == "true":
        notes_parts.append("Website verified")

    return " | ".join(notes_parts)



def _get_employee_range(row):
    """Return employee range string, using estimator when num_employees is missing."""
    emp = row.get("num_employees")
    if pd.notna(emp) and str(emp).strip() not in ("", "nan", "None", "0"):
        return format_employee_range(emp)
    # Fall back to estimator range string
    result = estimate_employee_range(row)
    if result:
        return result["employee_range"]
    return "Unknown"


def transform_row(row):
    """Transform a scored pipeline row into Hamilton standard format."""
    # Build text for classification
    desc_text = (
        str(row.get("company_name", "")) + " " +
        str(row.get("industry_description", "")) + " " +
        str(row.get("google_types", ""))
    )
    industry_label = str(row.get("industry_label", "general"))
    category = classify_category(desc_text)

    # Revenue range
    rev_low = float(row.get("estimated_revenue_low", 0)) if pd.notna(row.get("estimated_revenue_low")) else 0
    rev_high = float(row.get("estimated_revenue_high", 0)) if pd.notna(row.get("estimated_revenue_high")) else 0
    revenue_range = format_revenue_range(rev_low, rev_high) if rev_low > 0 else "Unknown"

    # SDE range
    sde_low = float(row.get("estimated_sde_low", 0)) if pd.notna(row.get("estimated_sde_low")) else 0
    sde_high = float(row.get("estimated_sde_high", 0)) if pd.notna(row.get("estimated_sde_high")) else 0
    sde_range = format_sde_range(sde_low, sde_high) if sde_low > 0 else "Unknown"

    # Owner info
    owner_name = row.get("owner_name", "")
    if pd.isna(owner_name) or str(owner_name).strip() in ("", "nan", "None", "N/A"):
        owner_name = "Not found"
        owner_confidence = "none"
        owner_source = "Owner not found; manual research required"
    else:
        owner_name = str(owner_name).strip()
        owner_confidence = str(row.get("owner_confidence", "medium"))
        _src = row.get("owner_source")
        owner_source = str(_src).strip() if pd.notna(_src) and str(_src).strip() not in ("", "nan", "None") else "Alternative source"

    # Address
    address = str(row.get("address_raw", "")) if pd.notna(row.get("address_raw")) else ""
    city = str(row.get("city", "Oakville")) if pd.notna(row.get("city")) else "Oakville"
    postal = str(row.get("postal_code", "")) if pd.notna(row.get("postal_code")) else ""

    return {
        "business_name": str(row.get("company_name", "")),
        "address": address,
        "city": city,
        "postal_code": postal,
        "website": re.sub(r"[?&]utm_[^#]*", "", str(row.get("website", ""))).rstrip("?&") if pd.notna(row.get("website")) else "",
        "phone": str(row.get("phone", "")) if pd.notna(row.get("phone")) else "",
        "owner_name": owner_name,
        "owner_confidence": owner_confidence,
        "owner_source": owner_source,
        "industry": industry_label,
        "category_standardized": category,
        "employee_range_estimate": _get_employee_range(row),
        "revenue_range_estimate": revenue_range,
        "sde_range_estimate": sde_range,
        "age_range_estimate": format_age_range(row),
        "acquisition_fit_score": int(round(float(row.get("total_score", 0)))),
        "important_notes": compose_notes(row, category),
    }


def main():
    print("=" * 60)
    print(" STEP 7: EXPORT CSV (Hamilton Standard Format)")
    print("=" * 60)

    df = pd.read_csv(CHECKPOINT_SCORED)
    print(f"  [INPUT] {len(df)} scored candidates from {CHECKPOINT_SCORED}")

    # Take top N by score, then hard-filter SDE out-of-range leads
    top = df.head(TARGET_FINAL_LEADS).copy()
    print(f"  [SELECT] Top {len(top)} candidates (target: {TARGET_FINAL_LEADS})")

    # Hard SDE filter — remove leads whose ENTIRE range is outside target
    below_mask = top["estimated_sde_high"].fillna(0).astype(float) < TARGET_SDE_LOW
    above_mask = top["estimated_sde_low"].fillna(float("inf")).astype(float) > TARGET_SDE_HIGH
    n_below = below_mask.sum()
    n_above = above_mask.sum()

    if n_below or n_above:
        print(f"\n  SDE hard filter:")
        print(f"    Removed (entire range below ${TARGET_SDE_LOW:,.0f}): {n_below}")
        print(f"    Removed (entire range above ${TARGET_SDE_HIGH:,.0f}): {n_above}")
        top = top[~below_mask & ~above_mask].copy()

        # Backfill from remaining scored candidates not already in top
        shortfall = TARGET_FINAL_LEADS - len(top)
        if shortfall > 0:
            already_in = top.index
            pool = df.drop(index=already_in.intersection(df.index), errors="ignore")
            # Apply same SDE filter to pool
            pool_below = pool["estimated_sde_high"].fillna(0).astype(float) < TARGET_SDE_LOW
            pool_above = pool["estimated_sde_low"].fillna(float("inf")).astype(float) > TARGET_SDE_HIGH
            pool = pool[~pool_below & ~pool_above]
            # Exclude rows already in top by position
            pool = pool[~pool.index.isin(already_in)]
            backfill = pool.head(shortfall)
            top = pd.concat([top, backfill], ignore_index=True)
            print(f"    Backfilled {len(backfill)} replacement leads from scored pool")
            if len(backfill) < shortfall:
                print(f"  [WARN] Only {len(top)} in-range leads available (target was {TARGET_FINAL_LEADS})")
        print(f"    Final count after SDE filter: {len(top)}")
    else:
        print(f"  SDE hard filter: all {len(top)} leads within range — no removals")

    # Transform each row
    print(f"\n  Transforming to Hamilton standard 17-field format...")
    leads = []
    for _, row in top.iterrows():
        leads.append(transform_row(row))

    output_df = pd.DataFrame(leads, columns=STANDARD_FIELDS)

    # Summary stats
    categories = output_df["category_standardized"].value_counts()
    print(f"\n  Category breakdown:")
    for cat, count in categories.head(10).items():
        print(f"    {cat:35s} {count:>3}")
    if len(categories) > 10:
        print(f"    ... and {len(categories) - 10} more categories")

    owner_found = len(output_df[output_df["owner_name"] != "Not found"])
    print(f"\n  Owner/officer found: {owner_found}/{len(output_df)} ({owner_found/len(output_df)*100:.0f}%)")

    scores = output_df["acquisition_fit_score"]
    print(f"  Score range: {scores.min()} to {scores.max()} (mean: {scores.mean():.0f})")

    # Save
    output_df.to_csv(OUTPUT_FINAL, index=False, encoding="utf-8")
    print(f"\n  [OUTPUT] {len(output_df)} leads saved -> {OUTPUT_FINAL}")
    print(f"  [OUTPUT] Fields: {len(STANDARD_FIELDS)} (Hamilton standard)")

    # Verify field order
    print(f"\n  Field order verification:")
    for i, field in enumerate(STANDARD_FIELDS, 1):
        print(f"    {i:>2}. {field}")


if __name__ == "__main__":
    main()
