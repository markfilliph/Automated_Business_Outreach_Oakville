"""
STEP 3: ENRICH WITH GOOGLE PLACES DETAILS (Cost-Optimized)

Fetches Place Details ONLY for the top candidates after a lightweight
pre-score. This avoids spending $0.017 per call on businesses that will
be filtered out anyway.

Strategy:
  1. Pre-score all filtered candidates using available data (name, types, reviews)
  2. Rank by pre-score
  3. Fetch Place Details for top N only (default: 200)
  4. Validate websites for enriched candidates

Input:  data/filtered_candidates.csv
Output: data/google_enriched.csv

Cost: ~$0.017 per Place Details call. 200 candidates = ~$3.40.
"""

import requests
import pandas as pd
import time
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from config import (
    GOOGLE_PLACES_API_KEY,
    CHECKPOINT_FILTERED,
    CHECKPOINT_GOOGLE,
    GOOGLE_DELAY_SECONDS,
    CACHE_ENABLED,
    WEBSITE_VALIDATION_ENABLED,
    WEBSITE_TIMEOUT_SECONDS,
    MAX_WEBSITE_CHECKS_PER_RUN,
    MAX_COST_USD_03,
    REQUIRE_CONFIRMATION,
    CHECKPOINT_EVERY_N_CALLS,
)
from utils.cache import cache_get, cache_set
from utils.website_validator import validate_website
from utils.employee_estimator import estimate_business_age

DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
CACHE_DIR = "data/cache/details"

# Maximum candidates to enrich with Place Details (cost control)
MAX_DETAILS_CANDIDATES = 200

# Fields to request from Place Details (controls billing)
DETAIL_FIELDS = [
    "name",
    "formatted_address",
    "formatted_phone_number",
    "international_phone_number",
    "website",
    "url",  # Google Maps URL
    "rating",
    "user_ratings_total",
    "types",
    "business_status",
    "opening_hours",
]


COST_PER_CALL_03 = 0.017  # Google Place Details rate


def fetch_place_details(place_id):
    """Fetch Place Details for a single place_id.

    Returns (result, was_cached):
      - result:     dict of place details, or None on failure.
      - was_cached: True if served from cache (costs $0).
    """
    cache_key = {"place_id": place_id}
    cached = cache_get("details", cache_key, CACHE_DIR)
    if cached is not None:
        return cached, True

    params = {
        "place_id": place_id,
        "fields": ",".join(DETAIL_FIELDS),
        "key": GOOGLE_PLACES_API_KEY,
    }

    try:
        resp = requests.get(DETAILS_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") == "OK":
            result = data.get("result", {})
            cache_set("details", cache_key, result, CACHE_DIR)
            return result, False
        else:
            return None, False
    except requests.RequestException as e:
        print(f"    [ERROR] Details fetch failed for {place_id}: {e}")
        return None, False


def enrich_row(row, details):
    """Merge Place Details into a candidate row."""
    if not details:
        return row

    # Update/add fields from details
    row["phone"] = details.get("formatted_phone_number", row.get("phone", ""))
    row["website"] = details.get("website", row.get("website", ""))
    row["google_rating"] = details.get("rating", row.get("google_rating"))
    row["review_count"] = details.get("user_ratings_total", row.get("review_count", 0))

    # Estimate business age from review count proxy
    age_est = estimate_business_age(row["review_count"])
    if age_est is not None:
        row["estimated_years"] = age_est["estimated_years"]

    new_types = details.get("types", [])
    if new_types:
        row["google_types"] = ",".join(new_types)
    row["business_status"] = details.get("business_status", row.get("business_status", ""))

    # Extract structured address
    formatted = details.get("formatted_address", "")
    if formatted:
        row["address_raw"] = formatted

    # Opening hours as activity signal
    hours = details.get("opening_hours", {})
    if hours:
        row["has_opening_hours"] = True
        row["is_open_now"] = hours.get("open_now", None)
    else:
        row["has_opening_hours"] = False

    return row


def pre_score(row):
    """Lightweight pre-score using only data available from Step 0.

    Purpose: rank candidates so we only pay for Place Details on the
    most promising ones. NOT the final score (that's Step 06).

    IMPORTANT: B2B companies (manufacturing, wholesale, logistics) often
    have zero reviews and generic Google types. The pre-score must NOT
    penalize them for lack of consumer-facing signals. A machining shop
    with 0 reviews may be a $4M revenue target.
    """
    score = 0

    # Review count (rough size proxy, but B2C-biased)
    reviews = row.get("review_count", 0)
    if pd.notna(reviews):
        reviews = float(reviews)
        if reviews >= 50:
            score += 20
        elif reviews >= 15:
            score += 15
        elif reviews >= 5:
            score += 10
        elif reviews >= 1:
            score += 5

    # Google rating (established businesses tend to have 4.0+)
    rating = row.get("google_rating")
    if pd.notna(rating):
        score += 8

    # Google types that suggest a real operating business
    types = str(row.get("google_types", "")).lower()
    high_signal_types = [
        "general_contractor", "electrician", "plumber",
        "moving_company", "storage", "car_repair",
        "accounting", "insurance_agency",
        "physiotherapist", "dentist", "veterinary_care",
        # B2B types that Google sometimes assigns
        "point_of_interest", "establishment",
    ]
    for t in high_signal_types:
        if t in types:
            score += 10
            break

    # Name signals: corporate suffixes
    name = str(row.get("company_name", "")).lower()
    biz_signals = ["inc", "ltd", "corp", "group", "services", "solutions",
                   "systems", "associates", "partners", "company"]
    for sig in biz_signals:
        if sig in name:
            score += 10
            break

    # B2B / INDUSTRIAL KEYWORD BOOST
    # This is the critical fix for B2B bias. Manufacturing, wholesale,
    # logistics, and construction companies often have zero consumer
    # signals but are the highest-value acquisition targets. Give them
    # a floor score based on name keywords alone.
    b2b_keywords = [
        "manufactur", "industrial", "fabricat", "machine", "metal",
        "steel", "plastic", "wood", "mill", "tool",
        "wholesale", "distribut", "supply", "logistics", "freight",
        "warehouse", "transport", "trucking", "moving",
        "construct", "contractor", "excavat", "concrete", "paving",
        "electric", "plumb", "hvac", "heating", "mechanical",
        "roofing", "insulation", "demolition",
        "engineer", "consult", "staffing", "recruit",
        "cleaning", "janitorial", "maintenance", "landscap",
        "security", "waste", "recycl", "equipment", "rental",
        "printing", "packaging", "sign", "graphic",
        "auto body", "collision", "towing",
    ]
    b2b_match = sum(1 for kw in b2b_keywords if kw in name)
    if b2b_match >= 2:
        score += 25  # Strong B2B signal
    elif b2b_match == 1:
        score += 15  # Moderate B2B signal

    return score


def main():
    print("=" * 60)
    print(" STEP 3: ENRICH WITH GOOGLE PLACES DETAILS (Cost-Optimized)")
    print("=" * 60)

    df = pd.read_csv(CHECKPOINT_FILTERED)
    print(f"  [INPUT] {len(df)} filtered candidates from {CHECKPOINT_FILTERED}")

    # Ensure string columns aren't inferred as float64 (happens when all values are NaN)
    for col in ("phone", "website", "address", "google_types", "owner_name",
                "owner_source", "industry", "category_standardized"):
        if col in df.columns:
            df[col] = df[col].astype(object)

    # Pre-score to select top candidates for enrichment
    print(f"\n  Pre-scoring {len(df)} candidates for enrichment priority...")
    df["_pre_score"] = df.apply(pre_score, axis=1)
    df = df.sort_values("_pre_score", ascending=False).reset_index(drop=True)

    enrich_count = min(len(df), MAX_DETAILS_CANDIDATES)
    print(f"  Will enrich top {enrich_count} of {len(df)} candidates")
    print(f"  Estimated cost: ${enrich_count * 0.017:.2f}")

    # ── Pre-flight cost estimate ───────────────────────────────────────────────
    worst_case_cost = enrich_count * COST_PER_CALL_03
    print(f"\n  ── Pre-flight Cost Estimate ──────────────────────────────")
    print(f"  Candidates to enrich: {enrich_count}")
    print(f"  Worst case cost:      ${worst_case_cost:.2f}  "
          f"(cached calls cost $0 — likely less)")
    print(f"  Hard cap:             ${MAX_COST_USD_03:.2f}  "
          f"(aborts if live calls exceed this)")
    print(f"  To abort mid-run:     create a file named STOP in project root")

    if REQUIRE_CONFIRMATION:
        print(f"\n  Proceed with live API calls? [y/N]: ", end="", flush=True)
        answer = input().strip().lower()
        if answer not in ("y", "yes"):
            print("  Aborted by user.")
            import sys; sys.exit(0)

    # Fetch details for top candidates only
    print(f"\n  Fetching Place Details...")
    live_calls = 0
    enriched_count = 0

    for idx in range(enrich_count):
        # --- STOP file check ---
        if os.path.exists("STOP"):
            print(f"\n  [STOP] STOP file detected at candidate {idx+1}. Saving progress and halting.")
            break

        # --- Hard cost cap check ---
        if live_calls * COST_PER_CALL_03 >= MAX_COST_USD_03:
            print(f"\n  [COST CAP] Reached ${MAX_COST_USD_03:.2f} limit "
                  f"({live_calls} live calls). Stopping enrichment.")
            break

        row = df.iloc[idx]
        place_id = row.get("google_place_id", "")
        if not place_id or pd.isna(place_id):
            continue

        details, was_cached = fetch_place_details(place_id)
        if not was_cached:
            live_calls += 1

        if details:
            for key, val in enrich_row(row.to_dict(), details).items():
                df.at[idx, key] = val
            enriched_count += 1

        if (idx + 1) % 50 == 0:
            cost_so_far = live_calls * COST_PER_CALL_03
            print(f"    Progress: {idx+1}/{enrich_count} processed, "
                  f"{live_calls} live calls (${cost_so_far:.2f}), "
                  f"{enriched_count} enriched")

        # --- Periodic checkpoint save ---
        if live_calls > 0 and live_calls % CHECKPOINT_EVERY_N_CALLS == 0:
            df.to_csv(CHECKPOINT_GOOGLE.replace(".csv", "_partial.csv"),
                      index=False, encoding="utf-8")
            print(f"    [CHECKPOINT] {enriched_count} enriched saved (partial)")

        time.sleep(GOOGLE_DELAY_SECONDS)

    print(f"  Details enrichment complete: {enriched_count}/{enrich_count} enriched")
    print(f"  Live API calls: {live_calls}, cost: ${live_calls * COST_PER_CALL_03:.2f}")

    # Website validation (only for enriched candidates, free but slow)
    if WEBSITE_VALIDATION_ENABLED:
        validate_count = min(enrich_count, MAX_WEBSITE_CHECKS_PER_RUN)
        print(f"\n  Validating websites (top {validate_count} candidates)...")
        websites_checked = 0
        websites_valid = 0

        if "website_valid" not in df.columns:
            df["website_valid"] = pd.array([None] * len(df), dtype=object)
        else:
            df["website_valid"] = df["website_valid"].astype(object)

        for idx in range(validate_count):
            website = df.iloc[idx].get("website", "")
            if not website or pd.isna(website) or str(website).strip() in ("", "nan"):
                continue

            is_valid, final_url, status = validate_website(str(website),
                                                           timeout=WEBSITE_TIMEOUT_SECONDS)
            df.at[idx, "website_valid"] = is_valid
            if is_valid and final_url:
                df.at[idx, "website"] = final_url
            websites_checked += 1
            if is_valid:
                websites_valid += 1

            if websites_checked % 50 == 0:
                print(f"    Checked {websites_checked}: {websites_valid} valid")

        print(f"  Website validation: {websites_valid}/{websites_checked} valid")

    # Clean up temp columns
    df.drop(columns=["_pre_score"], inplace=True, errors="ignore")

    # Summary
    has_phone = len(df[df["phone"].fillna("").str.len() > 0])
    has_website = len(df[df["website"].fillna("").str.len() > 0])
    has_rating = len(df[df["google_rating"].notna()])

    print(f"\n  Enrichment summary:")
    print(f"    Phone numbers:  {has_phone}/{len(df)}")
    print(f"    Websites:       {has_website}/{len(df)}")
    print(f"    Google ratings: {has_rating}/{len(df)}")

    total_cost = live_calls * COST_PER_CALL_03
    print(f"\n  Total API cost (live calls only): ${total_cost:.2f}  "
          f"(hard cap was ${MAX_COST_USD_03:.2f})")

    # Save
    df.to_csv(CHECKPOINT_GOOGLE, index=False, encoding="utf-8")
    print(f"\n  [OUTPUT] {len(df)} candidates -> {CHECKPOINT_GOOGLE}")
    print(f"  ({enrich_count} enriched with Place Details, {len(df) - enrich_count} basic data only)")


if __name__ == "__main__":
    main()
