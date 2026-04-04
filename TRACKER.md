# Oakville Acquisition MVP — Project Tracker

**Goal:** Generate 100 scored acquisition leads (SDE $250K–$500K, Oakville ON)
**Last updated:** 2026-04-03 (session 2)

---

## LEGEND
- ✅ Done
- 🔄 In Progress
- ⬜ To Do
- 🐛 Bug fix
- ⚠️ Needs API key / external dependency

---

## PHASE 0 — SCAFFOLDING & SETUP

| # | Task | Status | Notes |
|---|------|--------|-------|
| 0.1 | Write all 10 pipeline scripts (00–09) | ✅ Done | |
| 0.2 | Write all 6 utility modules | ✅ Done | cache, chain_filter, subsidiary_detector, website_validator, fuzzy_match, owner_enrichment |
| 0.3 | Write config.py (all constants) | ✅ Done | 322 lines, SDE-calibrated |
| 0.4 | Write requirements.txt | ✅ Done | 6 dependencies |
| 0.5 | Create virtual environment | ✅ Done | `.venv/` — run scripts with `.venv/bin/python` |
| 0.6 | Install dependencies | ✅ Done | pandas, requests, openpyxl, thefuzz, python-Levenshtein, python-dotenv |
| 0.7 | Create data/ directory structure | ✅ Done | `data/`, `data/cache/`, `data/cache/details/`, `data/cache/owner/`, `data/raw/` created |
| 0.8 | Create .env file | ✅ Done | `.env` created — `GOOGLE_PLACES_API_KEY` set and validated (status OK) |
| 0.9 | README.md | ✅ Done | |

---

## PHASE 1 — BUG FIXES

| # | File | Issue | Status |
|---|------|-------|--------|
| 1.1 | `utils/chain_filter.py` | Substring match without word boundaries — "ge" matches "agency", "management", "general" (false positives) | ✅ Fixed |
| 1.2 | `utils/subsidiary_detector.py` | Substring match without word boundaries — "ey" matches "money", "they", "survey", "storey" | ✅ Fixed |
| 1.3 | `utils/cache.py` | `os.path.getmtime()` called before try/except — raises OSError on permission errors | ✅ Fixed |
| 1.4 | `03_enrich_google.py` | `google_types` overwritten with empty string when Place Details returns no types (loses original data) | ✅ Fixed |
| 1.5 | `07_export.py` | `owner_source` NaN becomes string "nan" in output when owner IS found | ✅ Fixed |
| 1.6 | `08_export_excel.py` | Owner count uses `!= 'Not found'` — NaN rows incorrectly counted as "owners identified" | ✅ Fixed |
| 1.7 | `08_export_excel.py` | No empty-DataFrame guard before `.min()` / `.max()` / `.mean()` on scores | ✅ Fixed |
| 1.8 | `06_score.py` | No runtime assertion that scoring weights sum to 1.0 | ✅ Fixed |

---

## PHASE 1B — API COST GATEKEEPERS

| # | Protection | Where | Status |
|---|-----------|--------|--------|
| G.1 | **Pre-flight estimate** — shows worst-case cost before any call is made | `00`, `03` | ✅ Done |
| G.2 | **Y/N confirmation prompt** — must type `y` to proceed (controlled by `REQUIRE_CONFIRMATION` in config.py) | `00`, `03` | ✅ Done |
| G.3 | **Hard dollar cap** — script aborts mid-run if live cost exceeds `MAX_COST_USD_00` ($10) / `MAX_COST_USD_03` ($5) | `00`, `03` | ✅ Done |
| G.4 | **Accurate live-call tracking** — pagination pages now counted individually; cached responses cost $0 and are excluded from the cap | `00`, `03` | ✅ Done |
| G.5 | **STOP file abort** — create a file named `STOP` in project root at any time to halt the current run safely | `00`, `03` | ✅ Done |
| G.6 | **Periodic checkpoint saves** — partial CSV saved every `CHECKPOINT_EVERY_N_CALLS` (25) live calls; data is safe if run is killed | `00`, `03` | ✅ Done |

**To change limits:** edit `config.py` constants `MAX_COST_USD_00`, `MAX_COST_USD_03`, `REQUIRE_CONFIRMATION`, `CHECKPOINT_EVERY_N_CALLS`.

---

## PHASE 2 — PIPELINE EXECUTION

| # | Step | Script | Output | Status | Notes |
|---|------|--------|--------|--------|-------|
| 2.1 | Acquire leads | `00_acquire_leads.py` | `data/raw_candidates.csv` | ✅ Done | 3,387 raw candidates; 138 live calls; $4.42 total cost |
| 2.2 | Ingest & normalize | `01_ingest.py` | `data/raw_candidates.csv` (updated) | ✅ Done | 3,387 records normalized |
| 2.3 | Filter (5 gates) | `02_filter.py` | `data/filtered_candidates.csv` | ✅ Done | 3,387 → 2,049 (removed 1,338) |
| 2.4 | Google enrichment | `03_enrich_google.py` | `data/google_enriched.csv` | ✅ Done | 200 Place Details enriched; $3.38; 2 dtype bugs fixed |
| 2.5 | Deduplicate | `04_deduplicate.py` | `data/deduped_candidates.csv` | ✅ Done | 2,049 → 1,994 (55 fuzzy dupes removed) |
| 2.6 | Owner enrichment | `05_enrich_owner.py` | `data/owner_enriched.csv` | ⏭️ Skipped | No OpenCorporates token; 06_score.py uses deduped fallback |
| 2.7 | Score & rank | `06_score.py` | `data/scored_candidates.csv` | ✅ Done | 1,994 scored; 278 qualified (≥40); score range 22–62 |
| 2.8 | Export CSV | `07_export.py` | `data/top_100_for_review.csv` | ✅ Done | 100 leads; scores 50–62; 17 Hamilton fields verified |
| 2.9 | Export Excel | `08_export_excel.py` | `data/Oakville_Acquisition_Leads.xlsx` | ✅ Done | 2 sheets: Acquisition Leads + Summary |
| 2.10 | Human review | `09_review_queue.py` | `data/top_100_for_review.csv` (updated) | ⬜ To Do | CLI: approve / reject / flag / skip |

---

## PHASE 4 — QUALITY FIXES (Session 1)

| # | Task | File(s) | Status | Notes |
|---|------|---------|--------|-------|
| 4.1 | Fix category classifier substring bug | `07_export.py` | ✅ Done | Left-anchored `\b` word boundary prevents "charnwood"→Wood/Millwork, "engineer"→Engineering false positives |
| 4.2 | Fix company name cleaning | `01_ingest.py` | ✅ Done | Strips pipe-delimited marketing junk, location tags (` - Oakville`), promo parentheses, comma-list collapse (3+ names → first) |
| 4.3 | Add residential address detection flag | `02_filter.py`, `07_export.py` | ✅ Done | Non-blocking flag; street type abbreviations (Dr, Cres, Crt, etc.) added; `residential_flag` column + `FLAG:` note in export |
| 4.4 | Tighten chain/franchise filter | `utils/chain_filter.py` | ✅ Done | +30 entries: plumbing franchises, hotel chains, waste/facilities corps, major construction/engineering (PCL, EllisDon, Aecon, Stantec, WSP, SNC-Lavalin, AECOM, Jacobs) |
| 4.5 | Add employee count estimation heuristic | `utils/employee_estimator.py`, `06_score.py` | ✅ Done | 4-rule chain: direct → Google type baseline → review count proxy → B2B name signal; used in scoring before hardcoded default |
| 4.6 | Hard-filter SDE out-of-range leads in export | `07_export.py` | ✅ Done | Removes leads with SDE below $250K or above $500K after top-N selection; backfills from remaining pool |
| 4.7 | Tighten geographic filter — adjacent municipality spill | `02_filter.py` | ✅ Done | Stage B hard-excludes Burlington (L7L–L7T) and Mississauga (L5A–L5L) postal prefixes even if lat/lng overlaps |
| 4.8 | Add business age estimation from Google data | `utils/employee_estimator.py`, `03_enrich_google.py`, `06_score.py` | ✅ Done | `estimate_business_age()` uses review count proxy; stored as `estimated_years`; used as fallback in `score_years_in_business()` |
| 4.9 | Raise enrichment cap to cover all filtered candidates | `config.py`, `03_enrich_google.py` | ✅ Done | `MAX_COST_USD_03` $5→$40; `MAX_DETAILS_CANDIDATES` 200→2100; enriches all 2,049 candidates (~$35 at $0.017/call) |

---

## PHASE 5 — REVENUE MODEL FIXES (Session 2)

| # | Task | File(s) | Status | Notes |
|---|------|---------|--------|-------|
| 5.1 | Fix revenue estimates — employee midpoint not feeding into estimate_revenue() | `06_score.py` | ✅ Done | `scored_candidates.csv` was pre-Task-5; re-run after fixes confirmed 100/100 `num_employees` populated |
| 5.2 | Fix business age — `estimated_years` not in export | `07_export.py` | ✅ Done | `format_age_range()` now uses `estimated_years` fallback with "(est.)" label; age "Unknown" dropped from 100% to 0% |
| 5.3 | Fix postal code — enriched address not re-parsed | `03_enrich_google.py`, `06_score.py` | ✅ Done | `enrich_row()` re-extracts postal from `formatted_address`; `06_score.py` backfills remaining gaps before scoring |
| 5.4 | Strip UTM tracking params from website URLs | `03_enrich_google.py`, `07_export.py` | ✅ Done | Stripped at enrichment time and at export time; existing cached data cleaned without re-running step 03 |
| 5.5 | Fix `08_export_excel.py` crash on missing `review_status` | `08_export_excel.py` | ✅ Done | Guard added: column created as empty string if not present (only exists after `09_review_queue.py` runs) |
| 5.6 | Narrow per-employee revenue multipliers | `config.py` | ✅ Done | `per_employee_low` $100K→$120K, `per_employee_high` $220K→$185K; tighter range defensible now that employee heuristics are populated |
| 5.7 | Add confidence-based margin tiers | `config.py` | ✅ Done | Single `confidence_margin` 0.30 replaced with `confidence_margin_low/moderate/high` (0.30/0.15/0.08) |
| 5.8 | Apply tiered margins to final combined midpoint | `06_score.py` | ✅ Done | Margin selected on **final** confidence (after all signals); applied once to `avg_mid` — range width purely a confidence function |
| 5.9 | Industry-specific per-employee revenue multipliers | `config.py`, `06_score.py` | ✅ Done | `INDUSTRY_REVENUE_PER_EMPLOYEE` dict with 13 industry tuples; `estimate_revenue(row, industry)` uses industry mid instead of global flat rate |

---

## PHASE 3 — VALIDATION

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | Verify raw_candidates.csv has ≥150 rows | ⬜ To Do | Need enough to survive filtering |
| 3.2 | Verify filtered_candidates.csv drops hard exclusions | ⬜ To Do | Check no restaurants, law firms, retail |
| 3.3 | Verify deduplication removes obvious duplicates | ⬜ To Do | |
| 3.4 | Verify scored output has score range 0–100 | ⬜ To Do | |
| 3.5 | Verify top_100_for_review.csv has exactly 17 fields in Hamilton order | ⬜ To Do | |
| 3.6 | Verify Excel workbook opens and formatting renders | ⬜ To Do | |
| 3.7 | Spot-check 10 leads manually for SDE estimate plausibility | ⬜ To Do | |

---

## KNOWN LIMITATIONS / DECISIONS

- **No REQ equivalent:** Ontario has no public enterprise registry. Owner enrichment uses BBB Canada scraping + HuggingFace NER (dslim/bert-base-NER) + DuckDuckGo SERP as a 3-source chain. ~36% hit rate in practice.
- **Employee estimates are heuristic-based:** Derived from review count thresholds and Google place types — not from a verified source (LinkedIn, D&B, or CFIB). Treat as order-of-magnitude proxies only.
- **Business age estimates are weak proxies:** `estimated_years` is back-calculated from Google review count accumulation. Businesses that discourage reviews or operate B2B will be systematically underestimated.
- **Revenue/SDE estimates remain LOW confidence** without external data sources (LinkedIn Sales Navigator, D&B Hoovers, Industry Canada NAICS benchmarks). Current estimates use employee midpoint × revenue-per-employee × industry margin heuristics.
- **Name cleaning covers common patterns but not all edge cases:** Pipe-delimited marketing text (e.g. "Acme Plumbing | Oakville's #1 Choice") is stripped at ingestion. Unusual formatting or multi-language names may still require manual review.
- **SDE estimates are rough proxies:** Employee count × revenue per employee × industry margin. Confidence tagged HIGH/MODERATE/LOW in output.
- **Google Places data is B2C-biased:** B2B companies (manufacturing, wholesale) often have zero reviews. B2B keyword boost (+15–25 pre-score points) compensates.
- **Cost estimate:** Full pipeline run ≈ $40–$45 USD in Google API calls if run fresh (no cache) with full enrichment of all 2,049 candidates.
- **Step 05 is optional:** Can skip if no enrichment sources available; pipeline reads `deduped_candidates.csv` as fallback.

---

## HOW TO RUN

```bash
# 1. Add your Google Places API key
cp .env.example .env
# Edit .env: GOOGLE_PLACES_API_KEY=your_key_here

# 2. Run pipeline in order
.venv/bin/python 00_acquire_leads.py
.venv/bin/python 01_ingest.py
.venv/bin/python 02_filter.py
.venv/bin/python 03_enrich_google.py
.venv/bin/python 04_deduplicate.py
.venv/bin/python 05_enrich_owner.py   # optional
.venv/bin/python 06_score.py
.venv/bin/python 07_export.py
.venv/bin/python 08_export_excel.py
.venv/bin/python 09_review_queue.py   # optional human review
```
