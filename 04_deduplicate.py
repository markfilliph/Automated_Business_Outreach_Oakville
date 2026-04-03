"""
STEP 4: DEDUPLICATE CANDIDATES

Removes duplicate entries using multi-layer deduplication:
  Layer 1: Exact google_place_id match (should be rare after Step 0)
  Layer 2: Exact phone number match
  Layer 3: Fuzzy business name matching (token_sort_ratio >= 85)
  Layer 4: Address proximity (same postal code + similar name)

When duplicates are found, the entry with the highest data completeness
is kept (most fields populated).

Input:  data/google_enriched.csv
Output: data/deduped_candidates.csv
"""

import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from config import (
    CHECKPOINT_GOOGLE,
    CHECKPOINT_DEDUPED,
    FUZZY_NAME_THRESHOLD,
)
from utils.fuzzy_match import are_duplicates, normalize_name


def data_completeness_score(row):
    """Score how complete a row's data is. Higher = more complete."""
    score = 0
    fields = ["company_name", "phone", "website", "address_raw",
              "postal_code", "google_rating", "review_count"]
    for f in fields:
        val = row.get(f)
        if pd.notna(val) and str(val).strip() not in ("", "nan", "None", "0", "0.0"):
            score += 1
    # Bonus for having a valid website
    if row.get("website_valid") == True or str(row.get("website_valid")).lower() == "true":
        score += 2
    return score


def dedup_by_place_id(df):
    """Layer 1: Remove exact place_id duplicates."""
    before = len(df)
    df = df.drop_duplicates(subset=["google_place_id"], keep="first").copy()
    removed = before - len(df)
    if removed > 0:
        print(f"  Layer 1 (place_id):    removed {removed} exact duplicates")
    return df


def dedup_by_phone(df):
    """Layer 2: Remove entries with identical phone numbers."""
    before = len(df)

    # Only consider non-empty phones
    has_phone = df["phone"].fillna("").str.strip().str.len() > 0
    phone_df = df[has_phone].copy()
    no_phone_df = df[~has_phone].copy()

    # For phone duplicates, keep the one with best data completeness
    phone_df["_completeness"] = phone_df.apply(data_completeness_score, axis=1)
    phone_df = phone_df.sort_values("_completeness", ascending=False)
    phone_df = phone_df.drop_duplicates(subset=["phone"], keep="first")
    phone_df.drop(columns=["_completeness"], inplace=True)

    df = pd.concat([phone_df, no_phone_df], ignore_index=True)
    removed = before - len(df)
    if removed > 0:
        print(f"  Layer 2 (phone):       removed {removed} phone duplicates")
    return df


def dedup_by_fuzzy_name(df):
    """Layer 3: Remove entries with similar business names."""
    before = len(df)

    # Add completeness score for tie-breaking
    df["_completeness"] = df.apply(data_completeness_score, axis=1)
    df = df.sort_values("_completeness", ascending=False).reset_index(drop=True)

    names = df["company_name"].tolist()
    to_remove = set()

    for i in range(len(names)):
        if i in to_remove:
            continue
        for j in range(i + 1, len(names)):
            if j in to_remove:
                continue
            is_dup, score = are_duplicates(names[i], names[j], FUZZY_NAME_THRESHOLD)
            if is_dup:
                # Also check if they share postal code or are close geographically
                same_area = False
                pc_i = str(df.iloc[i].get("postal_code", ""))[:3]
                pc_j = str(df.iloc[j].get("postal_code", ""))[:3]
                if pc_i and pc_j and pc_i == pc_j:
                    same_area = True

                # If names are very similar (95+), remove regardless of location
                # If moderately similar (85-94), only remove if same area
                if score >= 95 or same_area:
                    to_remove.add(j)  # j has lower completeness (sorted above)

    df = df.drop(index=list(to_remove)).reset_index(drop=True)
    df.drop(columns=["_completeness"], inplace=True, errors="ignore")

    removed = before - len(df)
    if removed > 0:
        print(f"  Layer 3 (fuzzy name): removed {removed} similar-name duplicates")
    return df


def main():
    print("=" * 60)
    print(" STEP 4: DEDUPLICATE CANDIDATES")
    print("=" * 60)

    df = pd.read_csv(CHECKPOINT_GOOGLE)
    print(f"  [INPUT] {len(df)} enriched candidates from {CHECKPOINT_GOOGLE}")
    print()

    # Apply dedup layers
    df = dedup_by_place_id(df)
    df = dedup_by_phone(df)
    df = dedup_by_fuzzy_name(df)

    print(f"\n  [OUTPUT] {len(df)} deduplicated candidates -> {CHECKPOINT_DEDUPED}")

    df.to_csv(CHECKPOINT_DEDUPED, index=False, encoding="utf-8")


if __name__ == "__main__":
    main()
