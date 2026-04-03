"""
STEP 5: ENRICH OWNER DATA (Ontario: Alternative Sources)

Unlike Quebec (REQ), Ontario does not have a freely scrapable enterprise
registry. This step uses alternative sources:

  1. OpenCorporates API (free tier: 500/month)
  2. [Future: LinkedIn Sales Navigator API]
  3. [Future: Dun & Bradstreet API]

If OWNER_ENRICHMENT_ENABLED is False, this step simply copies the input
file to the output path, preserving pipeline flow.

Input:  data/deduped_candidates.csv
Output: data/owner_enriched.csv
"""

import pandas as pd
import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from config import (
    CHECKPOINT_DEDUPED,
    CHECKPOINT_OWNER,
    CHECKPOINT_SCORED,
    OWNER_ENRICHMENT_ENABLED,
    OPENCORPORATES_API_TOKEN,
    GOOGLE_DELAY_SECONDS,
)
from utils.owner_enrichment import enrich_owner


def main():
    print("=" * 60)
    print(" STEP 5: ENRICH OWNER DATA (Ontario Alternative Sources)")
    print("=" * 60)

    df = pd.read_csv(CHECKPOINT_DEDUPED)
    print(f"  [INPUT] {len(df)} deduped candidates from {CHECKPOINT_DEDUPED}")

    # Filter to top 100 scored leads if scored file exists
    if os.path.exists(CHECKPOINT_SCORED):
        scored_names = pd.read_csv(CHECKPOINT_SCORED)["company_name"].head(100).tolist()
        df = df[df["company_name"].isin(scored_names)].reset_index(drop=True)
        print(f"  [FILTER] Limited to top 100 scored leads ({len(df)} matched in deduped)")

    # Ensure string columns aren't inferred as float64 (happens when all values are NaN)
    for col in ("owner_name", "owner_confidence", "owner_source"):
        if col in df.columns:
            df[col] = df[col].astype(object)

    if not OWNER_ENRICHMENT_ENABLED:
        print(f"\n  Owner enrichment DISABLED. Copying input to output.")
        df.to_csv(CHECKPOINT_OWNER, index=False, encoding="utf-8")
        print(f"  [OUTPUT] {len(df)} candidates -> {CHECKPOINT_OWNER}")
        return

    api_token = OPENCORPORATES_API_TOKEN if OPENCORPORATES_API_TOKEN else None
    if not api_token:
        print(f"  [WARN] No OPENCORPORATES_API_TOKEN set. Using unauthenticated requests (lower rate limit).")

    print(f"\n  Enriching owner data for {len(df)} candidates...")
    enriched = 0
    failed = 0
    skipped = 0

    for idx, row in df.iterrows():
        company_name = str(row.get("company_name", "")).strip()
        if not company_name:
            skipped += 1
            continue

        # Skip if owner already found (from manual import or prior run)
        existing_owner = str(row.get("owner_name", "")).strip()
        if existing_owner and existing_owner not in ("", "nan", "None", "Not found", "N/A"):
            skipped += 1
            continue

        result = enrich_owner(
            company_name,
            city=str(row.get("city", "Oakville")),
            province="ON",
            website=str(row.get("website", "")) if row.get("website") else None,
            api_token=api_token,
        )

        df.at[idx, "owner_name"] = result["owner_name"]
        df.at[idx, "owner_confidence"] = result["owner_confidence"]
        df.at[idx, "owner_source"] = result["owner_source"]

        if result["owner_name"] and result["owner_name"] != "Not found":
            enriched += 1
        else:
            failed += 1

        # Progress
        processed = enriched + failed
        if processed % 25 == 0 and processed > 0:
            print(f"    Progress: {processed}/{len(df) - skipped} "
                  f"(found: {enriched}, not found: {failed})")

        # Rate limiting
        time.sleep(GOOGLE_DELAY_SECONDS * 2)  # Slower for OpenCorporates

    print(f"\n  Owner enrichment complete:")
    print(f"    Found:      {enriched}")
    print(f"    Not found:  {failed}")
    print(f"    Skipped:    {skipped}")
    print(f"    Hit rate:   {enriched/(enriched+failed)*100:.0f}%" if (enriched + failed) > 0 else "    Hit rate:   N/A")

    # Save
    df.to_csv(CHECKPOINT_OWNER, index=False, encoding="utf-8")
    print(f"\n  [OUTPUT] {len(df)} candidates -> {CHECKPOINT_OWNER}")


if __name__ == "__main__":
    main()
