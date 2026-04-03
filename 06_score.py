"""
STEP 6: SCORE & RANK (Oakville: SDE-Calibrated)

Score components (100-point scale, 8 factors):
  - Years in business     (20%) - from Google data or owner enrichment
  - Review count          ( 8%) - Google Places (biased toward B2C, low weight)
  - Sector signal         (15%) - high-value sector keyword match
  - Employee count        (17%) - strong SDE proxy at this range
  - Data quality          (12%) - completeness of lead data
  - Website presence      ( 8%) - has working, validated website
  - Location bonus        ( 5%) - core Oakville postal codes
  - SDE fit signal        (15%) - NEW: estimates SDE and penalizes out-of-range

Key difference from prior projects: scoring explicitly models SDE fit using
industry margins and estimated revenue. A business clearly below $250K SDE
or above $500K SDE gets penalized, pushing in-range targets to the top.

Input:  data/owner_enriched.csv (or data/deduped_candidates.csv if step 05 skipped)
Output: data/scored_candidates.csv
"""

import pandas as pd
from datetime import datetime
import sys
import os

from utils.employee_estimator import estimate_employee_range

sys.path.insert(0, os.path.dirname(__file__))
from config import (
    CHECKPOINT_OWNER,
    CHECKPOINT_DEDUPED,
    CHECKPOINT_SCORED,
    WEIGHT_YEARS_IN_BUSINESS,
    WEIGHT_REVIEW_COUNT,
    WEIGHT_SECTOR_SIGNAL,
    WEIGHT_EMPLOYEE_COUNT,
    WEIGHT_DATA_QUALITY,
    WEIGHT_WEBSITE_PRESENCE,
    WEIGHT_LOCATION_BONUS,
    WEIGHT_SDE_FIT_SIGNAL,
    HIGH_VALUE_SECTOR_KEYWORDS,
    TARGET_SDE_LOW,
    TARGET_SDE_HIGH,
    UNVERIFIED_PENALTY,
    QUALIFICATION_THRESHOLD,
    REVIEW_THRESHOLDS,
    REVENUE_ESTIMATION,
    INDUSTRY_MARGINS,
    TARGET_POSTAL_PREFIXES,
    OWNER_ENRICHMENT_ENABLED,
)


# ── Revenue and SDE estimation ────────────────────────────────────────────────

def estimate_revenue(row):
    """Estimate revenue range from available signals.

    Returns (low, mid, high, confidence) tuple.
    Confidence is 0-100 indicating reliability of estimate.
    """
    signals = []
    confidence = 20  # Base confidence

    # Signal 1: Employee count (strongest proxy)
    emp = row.get("num_employees")
    if pd.notna(emp) and float(emp) > 0:
        emp = float(emp)
        rev_emp_low = emp * REVENUE_ESTIMATION["per_employee_low"]
        rev_emp_high = emp * REVENUE_ESTIMATION["per_employee_high"]
        rev_emp_mid = emp * REVENUE_ESTIMATION["per_employee_mid"]
        signals.append(("employees", rev_emp_low, rev_emp_mid, rev_emp_high))
        confidence += 25

    # Signal 2: Review count (weak proxy, better for B2C)
    reviews = row.get("review_count", 0)
    if pd.notna(reviews) and float(reviews) > 0:
        reviews = float(reviews)
        if reviews >= REVIEW_THRESHOLDS["excellent"]:
            rev_review_mid = 3_000_000
        elif reviews >= REVIEW_THRESHOLDS["good"]:
            rev_review_mid = 2_000_000
        elif reviews >= REVIEW_THRESHOLDS["moderate"]:
            rev_review_mid = 1_500_000
        elif reviews >= REVIEW_THRESHOLDS["low"]:
            rev_review_mid = 1_000_000
        else:
            rev_review_mid = 700_000
        margin = REVENUE_ESTIMATION["confidence_margin"]
        signals.append(("reviews",
                        rev_review_mid * (1 - margin),
                        rev_review_mid,
                        rev_review_mid * (1 + margin)))
        confidence += 10

    # Signal 3: Business age
    reg_date = row.get("registration_date") or row.get("established_date")
    if pd.notna(reg_date):
        try:
            reg = pd.to_datetime(reg_date)
            years = (datetime.now() - reg).days / 365.25
            if years >= 25:
                age_factor = 1.3
            elif years >= 15:
                age_factor = 1.1
            elif years >= 10:
                age_factor = 1.0
            else:
                age_factor = 0.8
            # Age modifies the base, not an independent signal
            confidence += 10
        except Exception:
            age_factor = 1.0
    else:
        age_factor = 1.0

    # Combine signals
    if signals:
        avg_low = sum(s[1] for s in signals) / len(signals) * age_factor
        avg_mid = sum(s[2] for s in signals) / len(signals) * age_factor
        avg_high = sum(s[3] for s in signals) / len(signals) * age_factor
    else:
        # No signals at all: use broad base range
        base = REVENUE_ESTIMATION["base_range"]
        avg_low = base[0]
        avg_mid = (base[0] + base[1]) / 2
        avg_high = base[1]

    return avg_low, avg_mid, avg_high, min(confidence, 85)


def get_industry_label(row):
    """Extract industry label from available text fields."""
    text = (
        str(row.get("company_name", "")).lower() + " " +
        str(row.get("industry_description", "")).lower() + " " +
        str(row.get("google_types", "")).lower()
    )

    industry_map = [
        (["manufactur", "fabricat", "factory", "production"], "manufacturing"),
        (["plumbing", "hvac", "electrical", "roofing", "welding", "heating"], "trades"),
        (["construction", "renovation", "contractor", "builder"], "construction"),
        (["transport", "trucking", "freight", "logistics", "moving"], "transportation"),
        (["wholesale", "distributor", "distribution", "supply"], "wholesale"),
        (["cleaning", "janitorial"], "cleaning_services"),
        (["landscaping", "lawn", "property maintenance"], "landscaping"),
        (["it service", "software", "managed service", "technology"], "it_services"),
        (["engineering", "architect", "consulting"], "professional_services"),
        (["equipment", "rental", "leasing"], "equipment_rental"),
        (["printing", "print shop", "packaging"], "printing"),
        (["food processing", "food manufacturing"], "food_processing"),
        (["dental", "physio", "veterinar", "chiropract", "medical", "optom"], "healthcare_services"),
        (["accounting", "financial", "insurance", "bookkeep"], "financial_services"),
        (["staffing", "recruitment", "placement"], "staffing"),
    ]

    for keywords, label in industry_map:
        if any(kw in text for kw in keywords):
            return label
    return "general"


# ── Individual scoring functions ──────────────────────────────────────────────

def score_years_in_business(row):
    """Older businesses score higher. 30 years = 100 points."""
    reg_date = row.get("registration_date") or row.get("established_date")
    if pd.isna(reg_date) or reg_date is None:
        return 15.0  # Conservative default

    try:
        reg = pd.to_datetime(reg_date)
        years = (datetime.now() - reg).days / 365.25
        return min((years / 30.0) * 100, 100.0)
    except Exception:
        return 15.0


def score_review_count(row):
    """Granular review count thresholds. Low weight because B2C bias."""
    count = row.get("review_count", 0)
    if pd.isna(count):
        count = 0
    count = float(count)

    if count >= REVIEW_THRESHOLDS["excellent"]:
        return 100.0
    elif count >= REVIEW_THRESHOLDS["good"]:
        return 80.0
    elif count >= REVIEW_THRESHOLDS["moderate"]:
        return 60.0
    elif count >= REVIEW_THRESHOLDS["low"]:
        return 40.0
    elif count >= REVIEW_THRESHOLDS["very_low"]:
        return 25.0
    else:
        return 10.0  # No reviews: B2B companies often have zero


def score_sector_signal(row):
    """Score based on matching high-value sector keywords."""
    text = (
        str(row.get("company_name", "")).lower() + " " +
        str(row.get("industry_description", "")).lower() + " " +
        str(row.get("google_types", "")).lower()
    )

    matches = sum(1 for kw in HIGH_VALUE_SECTOR_KEYWORDS if kw.lower() in text)

    if matches >= 3:
        return 100.0
    elif matches == 2:
        return 80.0
    elif matches == 1:
        return 55.0
    else:
        return 20.0  # Not a known high-value sector, but still in scope


def score_employee_count(row):
    """Score employee count for SDE $250K-$500K sweet spot.

    Sweet spot is 15-50 employees for this SDE range.
    Below 10: likely too small. Above 75: might be too large / corporate.
    """
    emp = row.get("num_employees")
    if pd.isna(emp) or emp is None:
        return 30.0  # Unknown: moderate default

    emp = float(emp)
    if 15 <= emp <= 50:
        return 100.0   # Sweet spot
    elif 10 <= emp < 15:
        return 75.0
    elif 50 < emp <= 75:
        return 70.0
    elif 5 <= emp < 10:
        return 40.0
    elif 75 < emp <= 100:
        return 50.0
    elif 100 < emp <= 200:
        return 30.0
    else:
        return 10.0


def score_data_quality(row):
    """Score based on data completeness."""
    score = 0.0
    max_score = 100.0

    fields_and_weights = [
        ("company_name", 15),
        ("address_raw", 10),
        ("phone", 15),
        ("website", 15),
        ("google_rating", 10),
        ("review_count", 5),
        ("owner_name", 20),
        ("num_employees", 10),
    ]

    for field, weight in fields_and_weights:
        val = row.get(field)
        if pd.notna(val) and str(val).strip() not in ("", "nan", "None", "N/A", "Not found"):
            score += weight

    return min(score, max_score)


def score_website_presence(row):
    """Score based on having a working website."""
    website = row.get("website")
    if pd.isna(website) or str(website).strip() in ("", "nan", "None"):
        return 0.0

    website_valid = row.get("website_valid")
    if pd.notna(website_valid) and str(website_valid).lower() == "true":
        return 100.0
    elif pd.notna(website_valid) and str(website_valid).lower() == "false":
        return 10.0  # Has website but it's broken
    else:
        return 60.0  # Has website, not validated yet


def score_location_bonus(row):
    """Bonus for core Oakville postal codes."""
    address = str(row.get("address_raw", "")).upper()
    postal = str(row.get("postal_code", "")).upper()

    # Check for core Oakville prefixes
    for prefix in TARGET_POSTAL_PREFIXES:
        if prefix in address or prefix in postal:
            return 100.0
    return 50.0  # In bounds but postal not confirmed


def score_sde_fit(row, industry):
    """NEW: Score how well estimated SDE fits the $250K-$500K target.

    This is the key differentiator from prior projects. We estimate SDE
    and score based on how close it falls to the target range.
    """
    rev_low, rev_mid, rev_high, confidence = estimate_revenue(row)
    margin = INDUSTRY_MARGINS.get(industry, INDUSTRY_MARGINS["default"])

    sde_low = rev_low * margin
    sde_mid = rev_mid * margin
    sde_high = rev_high * margin

    # Perfect fit: SDE range overlaps with target
    if sde_low <= TARGET_SDE_HIGH and sde_high >= TARGET_SDE_LOW:
        # How much of the estimate overlaps with target?
        overlap_low = max(sde_low, TARGET_SDE_LOW)
        overlap_high = min(sde_high, TARGET_SDE_HIGH)
        overlap_width = overlap_high - overlap_low
        target_width = TARGET_SDE_HIGH - TARGET_SDE_LOW
        overlap_ratio = overlap_width / target_width

        base_score = 50 + (overlap_ratio * 50)  # 50-100 based on overlap

        # Confidence adjustment
        conf_factor = confidence / 100.0
        return base_score * (0.5 + 0.5 * conf_factor)

    # SDE range is below target (too small)
    elif sde_high < TARGET_SDE_LOW:
        gap = TARGET_SDE_LOW - sde_high
        gap_ratio = gap / TARGET_SDE_LOW
        return max(10.0, 40.0 * (1 - gap_ratio))

    # SDE range is above target (too large)
    elif sde_low > TARGET_SDE_HIGH:
        gap = sde_low - TARGET_SDE_HIGH
        gap_ratio = gap / TARGET_SDE_HIGH
        return max(10.0, 35.0 * (1 - gap_ratio))

    return 30.0  # Fallback


def compute_total_score(row, industry):
    """Compute weighted total score from all 8 factors."""
    assert abs((WEIGHT_YEARS_IN_BUSINESS + WEIGHT_REVIEW_COUNT + WEIGHT_SECTOR_SIGNAL +
                WEIGHT_EMPLOYEE_COUNT + WEIGHT_DATA_QUALITY + WEIGHT_WEBSITE_PRESENCE +
                WEIGHT_LOCATION_BONUS + WEIGHT_SDE_FIT_SIGNAL) - 1.0) < 0.001, \
        "Scoring weights in config.py must sum to 1.0"
    s_years = score_years_in_business(row)
    s_reviews = score_review_count(row)
    s_sector = score_sector_signal(row)
    s_employees = score_employee_count(row)
    s_quality = score_data_quality(row)
    s_website = score_website_presence(row)
    s_location = score_location_bonus(row)
    s_sde = score_sde_fit(row, industry)

    total = (
        s_years * WEIGHT_YEARS_IN_BUSINESS +
        s_reviews * WEIGHT_REVIEW_COUNT +
        s_sector * WEIGHT_SECTOR_SIGNAL +
        s_employees * WEIGHT_EMPLOYEE_COUNT +
        s_quality * WEIGHT_DATA_QUALITY +
        s_website * WEIGHT_WEBSITE_PRESENCE +
        s_location * WEIGHT_LOCATION_BONUS +
        s_sde * WEIGHT_SDE_FIT_SIGNAL
    )

    return {
        "score_years": round(s_years, 1),
        "score_reviews": round(s_reviews, 1),
        "score_sector": round(s_sector, 1),
        "score_employees": round(s_employees, 1),
        "score_quality": round(s_quality, 1),
        "score_website": round(s_website, 1),
        "score_location": round(s_location, 1),
        "score_sde_fit": round(s_sde, 1),
        "total_score": round(total, 1),
        "industry_label": industry,
    }


def main():
    print("=" * 60)
    print(" STEP 6: SCORE & RANK (Oakville SDE-Calibrated)")
    print("=" * 60)

    # Try owner-enriched first, fall back to deduped
    input_file = CHECKPOINT_OWNER if os.path.exists(CHECKPOINT_OWNER) else CHECKPOINT_DEDUPED
    df = pd.read_csv(input_file)
    print(f"  [INPUT] {len(df)} candidates from {input_file}")

    # Fill missing employee counts using heuristic estimator
    if "employee_source" not in df.columns:
        df["employee_source"] = ""
    filled = 0
    for idx, row in df.iterrows():
        emp = row.get("num_employees")
        if pd.isna(emp) or str(emp).strip() in ("", "nan", "None", "0"):
            result = estimate_employee_range(row)
            if result:
                df.at[idx, "num_employees"] = result["employee_midpoint"]
                df.at[idx, "employee_source"] = result["employee_source"]
                filled += 1
    print(f"\n  Employee estimation: filled {filled}/{len(df)} missing values")

    # Score each candidate
    print(f"\n  Scoring {len(df)} candidates (8 factors, SDE-calibrated)...")
    score_rows = []
    for _, row in df.iterrows():
        industry = get_industry_label(row)
        scores = compute_total_score(row, industry)
        score_rows.append(scores)

    # Merge scores back into DataFrame
    scores_df = pd.DataFrame(score_rows)
    df = pd.concat([df.reset_index(drop=True), scores_df.reset_index(drop=True)], axis=1)

    # Add revenue and SDE estimates
    rev_data = []
    for _, row in df.iterrows():
        rev_low, rev_mid, rev_high, confidence = estimate_revenue(row)
        industry = row.get("industry_label", "general")
        margin = INDUSTRY_MARGINS.get(industry, INDUSTRY_MARGINS["default"])
        rev_data.append({
            "estimated_revenue_low": round(rev_low),
            "estimated_revenue_mid": round(rev_mid),
            "estimated_revenue_high": round(rev_high),
            "revenue_confidence": confidence,
            "estimated_sde_low": round(rev_low * margin),
            "estimated_sde_mid": round(rev_mid * margin),
            "estimated_sde_high": round(rev_high * margin),
        })
    rev_df = pd.DataFrame(rev_data)
    df = pd.concat([df.reset_index(drop=True), rev_df.reset_index(drop=True)], axis=1)

    # Sort by total score descending
    df = df.sort_values("total_score", ascending=False).reset_index(drop=True)

    # Summary
    qualified = df[df["total_score"] >= QUALIFICATION_THRESHOLD]
    print(f"\n  Scoring complete:")
    print(f"    Total scored:    {len(df)}")
    print(f"    Qualified (>={QUALIFICATION_THRESHOLD}): {len(qualified)}")
    print(f"    Score range:     {df['total_score'].min():.0f} to {df['total_score'].max():.0f}")
    print(f"    Mean score:      {df['total_score'].mean():.1f}")

    # Industry breakdown
    print(f"\n  Industry breakdown:")
    for ind, count in df["industry_label"].value_counts().head(10).items():
        avg = df[df["industry_label"] == ind]["total_score"].mean()
        print(f"    {ind:30s} {count:>4} leads  (avg score: {avg:.0f})")

    # SDE fit distribution
    print(f"\n  SDE fit signal distribution:")
    sde_scores = df["score_sde_fit"]
    print(f"    Excellent (80+):   {len(sde_scores[sde_scores >= 80])}")
    print(f"    Good (60-79):      {len(sde_scores[(sde_scores >= 60) & (sde_scores < 80)])}")
    print(f"    Fair (40-59):      {len(sde_scores[(sde_scores >= 40) & (sde_scores < 60)])}")
    print(f"    Weak (<40):        {len(sde_scores[sde_scores < 40])}")

    # Save
    df.to_csv(CHECKPOINT_SCORED, index=False, encoding="utf-8")
    print(f"\n  [OUTPUT] {len(df)} scored candidates -> {CHECKPOINT_SCORED}")


if __name__ == "__main__":
    main()
