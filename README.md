# Oakville Acquisition Lead Generation MVP

Business acquisition lead generation pipeline targeting companies with **SDE (Seller's Discretionary Earnings) of CAD $250K to $500K** in Oakville, Ontario.

## Current Status

| Phase | Status |
|---|---|
| Phase 0 — Scaffolding & Setup | ✅ Complete |
| Phase 1 — Bug Fixes | ✅ Complete (8 bugs fixed) |
| Phase 1B — API Cost Gatekeepers | ✅ Complete (6 protections) |
| Phase 2 — Pipeline Execution | ✅ Complete (steps 00–08 done; step 09 optional) |
| Phase 4 — Quality Fixes | ✅ Complete (9 fixes) |
| Phase 5 — Revenue Model Fixes | ✅ Complete (9 fixes) |
| Phase 3 — Validation | ⬜ To Do |

**Pipeline run results:** 3,387 raw → 2,049 filtered → 1,994 deduped → 278 qualified → **100 exported leads** (scores 50–62). Total API cost: ~$42.

## Target Profile

| Parameter | Value |
|---|---|
| SDE Range | CAD $250,000 to $500,000 per year |
| Implied Revenue | ~$1.25M to $8.3M (varies by industry margin) |
| Location | Oakville, ON (postal: L6H, L6J, L6K, L6L, L6M) |
| Employees | Typically 10 to 75 |
| Business Age | 10+ years preferred |
| End Use | Broker-ready leads for cold outreach |

## Excluded Sectors

Only five hard exclusions: **law firms**, **immigration consultants**, **convenience stores**, **retail stores**, and **restaurants/food service**. Plus standard non-business types (churches, schools, hospitals, government, non-profits).

All other business types are in scope, including healthcare practices, accounting firms, IT services, and professional services that plausibly hit the SDE target. The broker and human reviewer decide final fit.

## Scripts

### Main Pipeline (run in order)

```
python 00_acquire_leads.py   -> data/raw_candidates.csv       (keyword search + industrial zone mini-grid)
python 01_ingest.py          -> data/raw_candidates.csv       (normalize/merge/clean names)
python 02_filter.py          -> data/filtered_candidates.csv  (5 gates: geography, sector, chain, subsidiary, employee)
python 03_enrich_google.py   -> data/google_enriched.csv      (Place Details for all filtered candidates)
python 04_deduplicate.py     -> data/deduped_candidates.csv   (fuzzy name matching)
python 05_enrich_owner.py    -> data/owner_enriched.csv       (BBB + NER + DuckDuckGo 3-source chain) [optional]
python 06_score.py           -> data/scored_candidates.csv    (8-factor SDE-calibrated scoring)
python 07_export.py          -> data/top_100_for_review.csv   (Hamilton standard 17-field CSV)
python 08_export_excel.py    -> data/Oakville_Acquisition_Leads.xlsx
python 09_review_queue.py    -> human review CLI              [optional]
```

### Standalone Tools

| Script | Purpose |
|---|---|
| `generate_leads.py` | Self-contained lead generator CLI — fetch, score, and export leads without running the full pipeline. Supports `--count`, `--industries`, and interactive industry selection. Output: `data/Generated_Leads_{timestamp}.xlsx` |
| `10_new_batch_nontrades.py` | One-off batch for 10 fresh leads from underrepresented non-trades sectors (IT, accounting, manufacturing, veterinary, physiotherapy, financial planning, etc.). Deduplicates against existing `raw_candidates.csv`. Output: `data/Oakville_NewBatch_NonTrades_10.xlsx` |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your GOOGLE_PLACES_API_KEY
```

To run with the project venv:

```bash
.venv/bin/python 00_acquire_leads.py
```

## Output Format

17-field Hamilton Standard format:

| # | Field | Description |
|---|---|---|
| 1 | business_name | Cleaned company name |
| 2 | address | Full street address |
| 3 | city | City (default: Oakville) |
| 4 | postal_code | Canadian postal code (A1A 1A1) |
| 5 | website | Clean URL (UTM params stripped) |
| 6 | phone | Normalized (905) 555-1234 format |
| 7 | owner_name | Owner/operator name if found |
| 8 | owner_confidence | high / medium / none |
| 9 | owner_source | BBB, NER, DuckDuckGo, or manual note |
| 10 | industry | Internal label (trades, manufacturing, etc.) |
| 11 | category_standardized | Display category (Plumbing Contractor, etc.) |
| 12 | employee_range_estimate | e.g. "10-20" |
| 13 | revenue_range_estimate | e.g. "$1.6M-$2.8M" |
| 14 | sde_range_estimate | e.g. "$320K-$560K" |
| 15 | age_range_estimate | e.g. "15+ years (est.)" |
| 16 | acquisition_fit_score | 0–100 composite score |
| 17 | important_notes | Flags, confidence tag, category, fit assessment |

## Scoring Model (8 Factors)

| Factor | Weight | Signal |
|---|---|---|
| Years in business | 20% | Registration date or review-count proxy |
| Employee count | 17% | 4-rule heuristic chain (direct → Google type → review proxy → B2B name signal) |
| SDE fit signal | 15% | Estimated SDE vs $250K–$500K target |
| Sector signal | 15% | High-value keyword match |
| Data quality | 12% | Field completeness |
| Review count | 8% | Google reviews (low weight: B2C bias) |
| Website presence | 8% | Validated working website |
| Location bonus | 5% | Core Oakville postal prefixes |

## Revenue Estimation Model

Revenue is estimated from employee count and review count signals combined with an industry-specific age factor. Range width is controlled by a **confidence-tiered margin**:

| Confidence | Signals present | Margin |
|---|---|---|
| High (≥ 60) | Employee + review + age | ±8% |
| Moderate (≥ 40) | Employee + review | ±15% |
| Low (< 40) | Review only or none | ±30% |

Per-employee revenue uses **industry-specific multipliers** (not a global flat rate):

| Industry | Low | Mid | High |
|---|---|---|---|
| Wholesale / distribution | $150K | $200K | $260K |
| IT services | $140K | $175K | $210K |
| Engineering / professional services | $130K | $165K | $200K |
| Accounting / financial services | $125K | $160K | $195K |
| Manufacturing | $130K | $150K | $175K |
| Healthcare / medical | $120K | $150K | $180K |
| Trades (plumbing, electrical, HVAC) | $110K | $140K | $165K |
| Automotive | $110K | $135K | $160K |
| Logistics / moving | $100K | $125K | $150K |
| Printing / signage | $100K | $120K | $145K |
| Cleaning services | $80K | $100K | $125K |
| Landscaping | $70K | $90K | $115K |
| Default | $120K | $150K | $185K |

SDE is calculated as `revenue × industry margin` (e.g. trades 20%, IT 30%, wholesale 8%).

## Owner Enrichment

Three-source chain with file-based caching:
1. **BBB Canada** — scrapes Better Business Bureau for named owner/officer
2. **HuggingFace NER** — `dslim/bert-base-NER` extracts person names from business website content
3. **DuckDuckGo SERP** — searches `"<company>" owner OR founder OR president` and parses results

Hit rate: ~36–38% in practice. `owner_confidence` reflects source quality (BBB = high, NER = medium, SERP = low).

> **Note:** Step 05 was skipped in the current run (no OpenCorporates token). `06_score.py` falls back to `deduped_candidates.csv` automatically.

## API Cost Gatekeepers (Steps 00 and 03)

| Protection | Description |
|---|---|
| Pre-flight estimate | Shows worst-case cost before any call is made |
| Y/N confirmation | Must type `y` to proceed (controlled by `REQUIRE_CONFIRMATION` in config.py) |
| Hard dollar cap | Script aborts if live cost exceeds `MAX_COST_USD_00` ($10) / `MAX_COST_USD_03` ($40) |
| Live-call tracking | Pagination pages counted individually; cached responses cost $0 |
| STOP file abort | Create a file named `STOP` in project root to halt the current run safely |
| Checkpoint saves | Partial CSV saved every 25 live calls; data is safe if run is killed |

## Estimated API Costs

| Step | API | Estimated Cost |
|---|---|---|
| 00 (Acquire) | Google Text/Nearby Search | $3–$7 |
| 03 (Enrich) | Google Place Details (all ~2,049 candidates) | ~$35 |
| 05 (Owner) | BBB scraping + NER (free) | $0 |
| **Total** | | **~$38–$42 per full run** |

Subsequent runs are cheaper — all API responses are file-cached in `data/cache/`.

## Architecture

**Hard rules (do not violate):**
- Synchronous only — no asyncio, no aiohttp
- No database — state in Pandas DataFrames, checkpoints in CSV files
- No YAML/JSON config loading — constants in `config.py` as plain variables
- No ORM or class hierarchies — gates are simple functions
- File-based JSON cache only — no SQLite

**Key decisions:**
- **SDE-first filtering** — unlike prior projects that filtered on revenue, this pipeline filters on estimated SDE range. Revenue thresholds are back-calculated from industry margins.
- **Minimal exclusions** — only 5 hard-excluded categories. Broker and human reviewer decide final fit.
- **Cost-optimized acquisition** — keyword search + targeted industrial zone mini-grid (~$4–$7) instead of full geographic sweep (~$26–$70).
- **Full enrichment** — all 2,049 filtered candidates get Place Details (~$35 at $0.017/call) rather than a pre-scored subset.
- **Estimate confidence tagging** — each lead carries HIGH/MODERATE/LOW in `important_notes` so brokers know which SDE estimates are backed by multiple signals.
- **B2B keyword boost** — manufacturing, wholesale, and logistics companies often have zero consumer reviews. Pre-scoring applies a +15–25 point boost for B2B/industrial name terms.

## Utility Modules

| Module | Purpose |
|---|---|
| `utils/cache.py` | File-based JSON API response cache |
| `utils/chain_filter.py` | Chain/franchise detection (Ontario-calibrated, all sectors) |
| `utils/subsidiary_detector.py` | Multinational subsidiary detection |
| `utils/employee_estimator.py` | 4-rule employee count heuristic + business age proxy |
| `utils/website_validator.py` | Synchronous HTTP website validation |
| `utils/fuzzy_match.py` | Fuzzy name matching for deduplication |
| `utils/owner_enrichment.py` | Pluggable owner discovery (BBB, NER, DuckDuckGo) |

## Known Limitations

- **Employee estimates are heuristic proxies** — derived from review count thresholds and Google place types, not verified data (LinkedIn, D&B, CFIB). Order-of-magnitude only.
- **Business age estimates are weak proxies** — `estimated_years` back-calculated from review count accumulation. B2B firms with few reviews will be underestimated.
- **Revenue/SDE confidence is MODERATE at best** — no external financial data sources (D&B Hoovers, Industry Canada NAICS benchmarks). All estimates carry "(est.)" label in output.
- **Owner enrichment ~36–38% hit rate** — Ontario has no public enterprise registry equivalent to Quebec's REQ. Named owner data is sparse for smaller B2B operators.
- **Name cleaning handles common patterns** — pipe-delimited marketing text stripped at ingestion; unusual formatting may still need manual review.
- **Google Places data is B2C-biased** — B2B companies (manufacturing, wholesale) often have zero reviews. B2B keyword boost compensates in pre-scoring.

## License

MIT
