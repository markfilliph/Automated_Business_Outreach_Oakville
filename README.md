# Oakville Acquisition Lead Generation MVP

Business acquisition lead generation pipeline targeting companies with **SDE (Seller's Discretionary Earnings) of CAD $250K to $500K** in Oakville, Ontario.

## Target Profile

| Parameter | Value |
|---|---|
| SDE Range | CAD $250,000 to $500,000 per year |
| Implied Revenue | ~$1.25M to $8.3M (varies by industry) |
| Location | Oakville, ON (postal: L6H, L6J, L6K, L6L, L6M) |
| Employees | Typically 10 to 75 |
| Business Age | 10+ years preferred |
| End Use | Broker-ready leads for cold outreach |

## Excluded Sectors

Only five hard exclusions: **law firms**, **immigration consultants**, **convenience stores**, **retail stores**, and **restaurants/food service**. Plus standard non-business types (churches, schools, hospitals, government, non-profits).

All other business types are in scope, including healthcare practices, accounting firms, IT services, and other professional services that hit the SDE target.

## Pipeline

```
python 00_acquire_leads.py   -> data/raw_candidates.csv       (keyword search + industrial zone mini-grid)
python 01_ingest.py          -> data/raw_candidates.csv       (normalize/merge)
python 02_filter.py          -> data/filtered_candidates.csv  (5 gates)
python 03_enrich_google.py   -> data/google_enriched.csv      (Place Details for top 200 + websites)
python 04_deduplicate.py     -> data/deduped_candidates.csv   (fuzzy matching)
python 05_enrich_owner.py    -> data/owner_enriched.csv       (OpenCorporates + alternatives)
python 06_score.py           -> data/scored_candidates.csv    (8-factor SDE-calibrated scoring)
python 07_export.py          -> data/top_100_for_review.csv   (Hamilton standard 17-field CSV)
python 08_export_excel.py    -> data/Oakville_Acquisition_Leads.xlsx
python 09_review_queue.py    -> human review CLI
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your GOOGLE_PLACES_API_KEY
# Optionally add OPENCORPORATES_API_TOKEN for owner enrichment
```

## Output Format

17-field Hamilton Standard format (identical to Hamilton and Vaudreuil pipelines):

1. business_name
2. address
3. city
4. postal_code
5. website
6. phone
7. owner_name
8. owner_confidence
9. owner_source
10. industry
11. category_standardized
12. employee_range_estimate
13. revenue_range_estimate
14. sde_range_estimate
15. age_range_estimate
16. acquisition_fit_score
17. important_notes

## Architecture

Hybrid design: Vaudreuil v3.1 sequential script structure with select Hamilton features.

**From Vaudreuil:** synchronous Python, Pandas DataFrames, CSV checkpoints, file-based JSON cache, numbered pipeline scripts, no database, no async.

**From Hamilton:** chain/franchise filtering, subsidiary detection, website validation, structured scoring with configurable weights, formatted Excel export.

**New for Oakville:** SDE-fit scoring factor, industry-specific margin calculations, OpenCorporates owner enrichment, wider funnel with minimal exclusions, cost-optimized acquisition (keyword-first with targeted industrial zone mini-grid instead of full geographic sweep), pre-scored Place Details enrichment (top 200 only), B2B keyword boost to protect industrial firms from consumer-biased scoring, estimate confidence tagging (HIGH/MODERATE/LOW) in broker output.

## Estimated API Costs (Optimized)

| Step | API | Estimated Cost |
|---|---|---|
| 00 (Acquire) | Google Text/Nearby Search | $3 to $7 |
| 03 (Enrich) | Google Place Details (top 200 only) | $3 to $4 |
| 05 (Owner) | OpenCorporates | Free (500/month) |
| **Total** | | **$6 to $11 per run** |

Cost optimization: keyword-first acquisition with targeted mini-grid on industrial zones (not full Oakville sweep). Place Details limited to pre-scored top 200 candidates. Full grid available as fallback if needed.

## License

MIT
