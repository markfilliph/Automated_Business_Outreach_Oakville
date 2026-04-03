# Oakville Acquisition MVP v1 — Build Rules

## What this is
A script pipeline to generate 100 scored acquisition leads targeting businesses
with SDE (Seller's Discretionary Earnings) between CAD $250K and $500K in
Oakville, Ontario. It runs once or twice. It is NOT a SaaS product.

## Target Profile
- **SDE Range:** CAD $250,000 to $500,000 per year
- **Implied Revenue Range:** ~$1.25M to $8.3M (varies by industry margin)
- **Location:** Oakville, Ontario (postal prefixes L6H, L6J, L6K, L6L, L6M)
- **Employee Range:** Typically 10 to 75 employees
- **Business Age:** 10+ years preferred (succession/retirement signal)
- **End Use:** Broker-ready leads for cold outreach to off-market owners

## Sector Scope
- **INCLUDE:** Virtually everything that is an "operating business"
- **EXCLUDE (hard):** Law firms, immigration consultants, convenience stores,
  retail stores, restaurants/bars/food service
- **EXCLUDE (standard):** Churches, schools, daycares, hospitals,
  government offices, non-profits, charities
- **EXCLUDE:** Known chains, franchises, large corporations, subsidiaries
  of publicly traded or multinational parent companies

NOTE: Unlike Vaudreuil v3 which excluded all practices/personal services,
this pipeline uses MINIMAL exclusions. Accounting firms, medical clinics,
engineering consultancies, IT firms, etc. are IN SCOPE if they plausibly
hit the SDE target. The broker and human reviewer decide final fit.

## Hard Rules — Do Not Violate
- **Synchronous only.** No asyncio, no aiohttp. Use `requests` in sync mode.
- **No database.** State lives in Pandas DataFrames. Checkpoints are CSV files in `data/`.
- **No ORM, no models layer.** DataFrames only.
- **No YAML/JSON config loading.** Constants go in `config.py` as plain variables.
- **No complex class hierarchies.** Gates are simple functions: `def filter_by_X(df) -> df`
- **No tenacity retry decorators on everything.** Retries exist ONLY in `05_enrich_owner.py`.
- **Cache is file-based JSON only.** No SQLite for caching. Files in `data/cache/`.

## Pipeline Order
```
python 00_acquire_leads.py   -> data/raw_candidates.csv
python 01_ingest.py          -> data/raw_candidates.csv (normalize/merge)
python 02_filter.py          -> data/filtered_candidates.csv  (5 gates)
python 03_enrich_google.py   -> data/google_enriched.csv
python 04_deduplicate.py     -> data/deduped_candidates.csv
python 05_enrich_owner.py    -> data/owner_enriched.csv  (LinkedIn/D&B/OBR alternatives)
python 06_score.py           -> data/scored_candidates.csv (8-factor scoring)
python 07_export.py          -> data/top_100_for_review.csv (Hamilton standard 17-field CSV)
python 08_export_excel.py    -> data/Oakville_Acquisition_Leads.xlsx (formatted workbook)
python 09_review_queue.py    -> human review CLI
```

## Output Format (Hamilton Standard)
17 fields in this exact order:

1.  business_name
2.  address
3.  city
4.  postal_code
5.  website
6.  phone
7.  owner_name
8.  owner_confidence    (high/medium/none)
9.  owner_source        (LinkedIn, OBR, D&B, or manual research note)
10. industry
11. category_standardized
12. employee_range_estimate
13. revenue_range_estimate
14. sde_range_estimate
15. age_range_estimate
16. acquisition_fit_score (0-100)
17. important_notes         (category tag, SDE fit, estimate confidence HIGH/MODERATE/LOW, flags)

## Key Technical Decisions
- **No REQ equivalent.** Ontario does not have a publicly scrapable enterprise
  registry like Quebec's REQ. Owner enrichment uses alternative sources:
  OpenCorporates API, LinkedIn (manual or API), D&B, Canada Business Registries.
  Step 05 is designed as a pluggable enrichment step.
- **SDE-first filtering.** Previous projects filtered on revenue. This project
  filters on estimated SDE range ($250K-$500K). Revenue thresholds are
  back-calculated from industry margins. A manufacturing company needs ~$2M+
  revenue; a services firm needs ~$1.25M+.
- **Minimal exclusions.** Only 5 hard-excluded categories (law, immigration,
  convenience stores, retail, restaurant) plus standard non-business types. Everything else passes
  through to scoring and human review.
- **Scoring uses 8 factors:** years, reviews, sector signal, employees,
  data quality, website, location, SDE-fit signal. Weights sum to 1.0.
- **Cost-optimized acquisition strategy.** Instead of a full 400+ cell grid
  sweep ($13-$40), uses keyword search as primary acquisition (~$1.30) plus
  a targeted mini-grid covering only industrial/commercial zones (~$1-$2).
  Full grid is available as fallback (disabled by default). Total acquisition
  cost: $3-$7 vs. $26-$70 for the naive approach.
- **Pre-scored Place Details.** Step 03 pre-scores candidates using free data
  (name, types, reviews) and only pays for Place Details ($0.017/call) on
  the top 200 candidates. Saves ~60% on enrichment costs.
- **Export matches Hamilton MVP Burlington STANDARDIZED format** exactly.
  17 fields, identical column names and order. SDE uses industry-specific margins.
- **B2B keyword boost in pre-scoring.** Step 03 pre-scores candidates to decide
  which get expensive Place Details enrichment. Manufacturing, wholesale,
  logistics, and trades companies often have zero consumer reviews, so the
  pre-score includes a keyword boost (15-25 points) for B2B/industrial terms
  in the company name. This prevents high-value targets from being deprioritized
  behind dentists and hair salons.
- **Estimate confidence tagging.** Each exported lead carries a confidence tag
  (HIGH/MODERATE/LOW) in the important_notes field, so the broker can immediately
  see which SDE estimates are backed by multiple data signals versus rough proxies.
  HIGH = employee count + reviews + age data. LOW = name-only estimate.

## Dependencies
- Python 3.8+
- pandas, requests, python-dotenv
- openpyxl (for Excel export only)
- thefuzz (for fuzzy name matching in deduplication)

## Utility Modules
- `utils/chain_filter.py` — chains/franchises (Ontario-calibrated, all sectors)
- `utils/subsidiary_detector.py` — multinational subsidiary detection
- `utils/cache.py` — file-based JSON API response cache
- `utils/website_validator.py` — synchronous HTTP website validation
- `utils/fuzzy_match.py` — fuzzy name matching for deduplication
- `utils/owner_enrichment.py` — pluggable owner discovery (OpenCorporates, etc.)

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your GOOGLE_PLACES_API_KEY
```
