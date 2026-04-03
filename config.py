# =============================================================================
# Oakville Acquisition MVP — Pipeline Configuration (v1)
# =============================================================================
# Target: Businesses with SDE $250K-$500K CAD in Oakville, Ontario.
# Minimal exclusions: law firms, immigration consultants, retail, restaurants.
# Architecture: Hybrid (Vaudreuil sequential structure + Hamilton enrichment).
#
# Key difference from prior projects:
#   - SDE-first targeting (not revenue-first)
#   - No REQ scraper (Ontario has no public enterprise registry like Quebec)
#   - English-only keywords (no French)
#   - Wider funnel: most business types are in scope
# =============================================================================

import os
from dotenv import load_dotenv

load_dotenv()

# === API KEYS ===
GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "YOUR_KEY_HERE")
OPENCORPORATES_API_TOKEN = os.environ.get("OPENCORPORATES_API_TOKEN", "")

# === TARGET GEOGRAPHY ===
TARGET_CITY = "Oakville"
TARGET_PROVINCE = "ON"
TARGET_POSTAL_PREFIXES = ["L6H", "L6J", "L6K", "L6L", "L6M"]

# Geographic bounds for Oakville proper (municipal boundaries)
#   South: Lake Ontario shoreline
#   North: Dundas Street / Highway 407 corridor
#   West: Bronte Creek / Burlington border
#   East: Sixteen Mile Creek / Mississauga border
GEO_BOUNDS = {
    "south": 43.385,
    "north": 43.505,
    "west": -79.785,
    "east": -79.580,
}

# === SDE TARGET RANGE ===
# This is the primary acquisition filter. All revenue thresholds are
# back-calculated from this using industry-specific margins.
TARGET_SDE_LOW = 250_000    # CAD
TARGET_SDE_HIGH = 500_000   # CAD

# === SECTOR SCOPE (MINIMAL EXCLUSIONS) ===
# Only 4 hard-excluded categories per mandate, plus standard non-business types.
# Everything else passes through to scoring and human review.

EXCLUDED_SECTOR_KEYWORDS = [
    # --- Hard exclusions (per mandate) ---
    # Law firms
    "law firm", "legal services", "barrister", "solicitor",
    "litigation", "paralegal", "law office", "attorney",
    "avocats",  # catch bilingual listings

    # Immigration consultants
    "immigration", "visa service", "citizenship",
    "immigration consultant", "rcic",

    # Convenience stores
    "convenience store", "convenience", "corner store",
    "variety store", "mini mart", "minimart",
    "milk store", "depanneur",  # bilingual listings

    # Retail stores
    "retail", "store", "shop ", " shop", "boutique", "outlet",
    "mall", "shopping centre", "shopping center",
    "grocery", "supermarket",
    "dollar store", "thrift", "consignment",
    "liquor store", "beer store", "lcbo",
    "pet store", "pet shop",
    "flower shop", "florist",
    "gift shop", "card shop",
    "bookstore", "book store",
    "jewellery", "jewelry",
    "shoe store", "clothing store",
    "furniture store", "mattress",
    "electronics store",
    "pharmacy", "drugstore",
    "vape shop", "smoke shop", "cannabis",

    # Restaurants, bars, food service
    "restaurant", "bistro", "cafe", "café", "coffee shop",
    "bar ", " bar", "pub ", " pub", "tavern", "lounge",
    "pizza", "sushi", "burger", "grill", "diner",
    "bakery", "pastry", "patisserie",
    "catering", "caterer",
    "food truck", "fast food",
    "ice cream", "frozen yogurt",
    "brewery", "brewpub", "taproom",
    "winery", "wine bar",

    # --- Standard non-business types ---
    "church", "mosque", "synagogue", "temple",
    "school", "college", "university",
    "daycare", "child care", "montessori",
    "hospital", "emergency room",
    "government", "municipal", "town of",
    "non-profit", "nonprofit", "charity",
    "community centre", "community center",
    "library", "museum",
    "fire station", "police",
]

# Positive sector keywords: used for SCORING (not filtering).
# Businesses matching these get a boost because they represent sectors
# with stronger acquisition characteristics at the $250K-$500K SDE level.
HIGH_VALUE_SECTOR_KEYWORDS = [
    # Manufacturing and fabrication
    "manufactur", "fabricat", "production", "assembly",
    "machining", "cnc", "precision", "tool and die",
    "plastics", "injection mold", "metal", "steel",
    "wood", "millwork", "cabinet", "carpentry",
    "printing", "packaging", "label",
    "food processing", "food manufacturing",

    # Construction and trades (high SDE potential)
    "construction", "general contractor", "renovation",
    "plumbing", "plumber", "hvac", "heating", "cooling",
    "air conditioning", "ventilation", "refrigeration",
    "electrical", "electrician", "wiring",
    "roofing", "roofer", "siding",
    "excavation", "grading", "concrete", "paving", "asphalt",
    "masonry", "bricklaying", "stone",
    "welding", "structural steel",
    "insulation", "drywall", "framing",
    "demolition", "abatement",
    "fire protection", "sprinkler",
    "elevator", "escalator",

    # Transportation and logistics
    "transport", "trucking", "freight", "shipping",
    "warehouse", "warehousing", "distribution",
    "logistics", "supply chain", "3pl",
    "courier", "delivery", "moving",

    # Professional and technical services (larger firms hit SDE target)
    "engineering", "engineer", "consulting engineer",
    "architecture", "architect",
    "it services", "managed services", "msp",
    "software", "technology", "systems integrator",
    "environmental", "remediation",
    "surveying", "geotechnical",
    "testing", "laboratory", "inspection",
    "staffing", "recruitment", "placement",

    # Wholesale and distribution
    "wholesale", "distributor", "distribution",
    "supply", "supplier", "industrial supply",

    # Specialized services
    "equipment", "rental", "leasing",
    "maintenance", "facility", "facilities",
    "cleaning", "janitorial", "commercial cleaning",
    "landscaping", "lawn care", "property maintenance",
    "security", "guard", "alarm", "surveillance",
    "pest control", "extermination",
    "waste", "recycling", "disposal",
    "towing", "auto body", "collision",
    "signage", "sign company", "graphics",
    "printing", "print shop", "digital printing",

    # Healthcare services (larger clinics can hit SDE target)
    "dental", "dentist", "dental group",
    "physiotherapy", "physio", "rehabilitation",
    "veterinary", "vet clinic", "animal hospital",
    "optometry", "optometrist", "optical",
    "chiropractic", "chiropractor",
    "medical clinic", "walk-in clinic",
    "home care", "home health",
    "pharmacy group",  # Multi-location pharmacies

    # Financial and professional services (larger firms)
    "accounting", "accountant", "cpa", "bookkeeping",
    "financial planning", "wealth management",
    "insurance", "insurance broker",
    "real estate", "property management", "brokerage",
]

# === SCORING WEIGHTS (must sum to 1.0) ===
WEIGHT_YEARS_IN_BUSINESS = 0.20
WEIGHT_REVIEW_COUNT = 0.08       # Low: reviews biased toward B2C
WEIGHT_SECTOR_SIGNAL = 0.15      # High-value sector keyword match
WEIGHT_EMPLOYEE_COUNT = 0.17     # Strong SDE proxy at this range
WEIGHT_DATA_QUALITY = 0.12
WEIGHT_WEBSITE_PRESENCE = 0.08
WEIGHT_LOCATION_BONUS = 0.05
WEIGHT_SDE_FIT_SIGNAL = 0.15     # NEW: replaces ownership_signal; penalizes
                                  # businesses clearly outside SDE range

# === FILTERING THRESHOLDS ===
MIN_EMPLOYEES = 5                 # Below 5 employees, SDE $250K+ is rare
MAX_EMPLOYEES = 200               # Above 200, likely too large / corporate
QUALIFICATION_THRESHOLD = 40      # Score threshold for export
UNVERIFIED_PENALTY = 10           # Points deducted for unverified leads
FUZZY_NAME_THRESHOLD = 85         # Minimum similarity for dedup matching
TARGET_FINAL_LEADS = 100          # Number of leads to export

# === REVENUE ESTIMATION PARAMETERS ===
# Revenue is estimated from employee count, reviews, industry, and age.
# SDE is then calculated from revenue using industry-specific margins.
REVENUE_ESTIMATION = {
    "per_employee_low": 120_000,   # Conservative: $120K revenue per employee
    "per_employee_mid": 150_000,   # Moderate estimate
    "per_employee_high": 185_000,  # Aggressive estimate
    "base_range": (800_000, 5_000_000),  # Wider base for this SDE range
    "confidence_margin_low": 0.30,      # +/- 30% when only base confidence (no signals)
    "confidence_margin_moderate": 0.15, # +/- 15% when one signal (employee or review count)
    "confidence_margin_high": 0.08,     # +/- 8%  when multiple signals
    "review_adjustment": 0.12,     # Review count adjusts estimate by up to 12%
    "years_adjustment": 0.12,      # Years in business adjusts by up to 12%
    "website_adjustment": 0.08,    # Website presence adjusts by up to 8%
}

# Industry margins for SDE calculation from revenue.
# SDE = Revenue * Margin (approximately, for owner-operated businesses)
# These reflect typical SDE margins for businesses in this size range.
INDUSTRY_MARGINS = {
    "manufacturing": 0.12,
    "printing": 0.15,
    "wholesale": 0.08,
    "professional_services": 0.25,
    "construction": 0.12,
    "trades": 0.20,
    "transportation": 0.10,
    "equipment_rental": 0.22,
    "food_processing": 0.10,
    "cleaning_services": 0.18,
    "landscaping": 0.20,
    "it_services": 0.30,
    "healthcare_services": 0.25,
    "financial_services": 0.30,
    "staffing": 0.15,
    "default": 0.15,
}

# Revenue per employee by industry (low, mid, high) in CAD
# Used in estimate_revenue() to produce industry-calibrated estimates.
# "default" is used for "general" or any unrecognized label.
INDUSTRY_REVENUE_PER_EMPLOYEE = {
    "manufacturing":         (130_000, 150_000, 175_000),
    "trades":                (110_000, 140_000, 165_000),
    "construction":          (120_000, 155_000, 190_000),
    "transportation":        (100_000, 130_000, 160_000),
    "wholesale":             (150_000, 200_000, 260_000),
    "cleaning_services":     ( 80_000, 100_000, 125_000),
    "landscaping":           ( 70_000,  90_000, 115_000),
    "it_services":           (140_000, 175_000, 210_000),
    "professional_services": (130_000, 165_000, 200_000),
    "equipment_rental":      (120_000, 150_000, 185_000),
    "healthcare_services":   (120_000, 150_000, 185_000),
    "financial_services":    (140_000, 180_000, 220_000),
    "staffing":              (100_000, 140_000, 180_000),
    "default":               (120_000, 150_000, 185_000),
}

# Implied revenue ranges for SDE $250K-$500K by industry
# (auto-calculated, used for filtering and scoring)
def get_revenue_range_for_sde(industry):
    """Calculate required revenue range to hit SDE target for an industry."""
    margin = INDUSTRY_MARGINS.get(industry, INDUSTRY_MARGINS["default"])
    rev_low = TARGET_SDE_LOW / margin    # Minimum revenue for $250K SDE
    rev_high = TARGET_SDE_HIGH / margin  # Revenue that gives $500K SDE
    return (rev_low, rev_high)

REVIEW_THRESHOLDS = {
    "very_low": 2,
    "low": 5,
    "moderate": 15,
    "good": 30,
    "excellent": 50,
}

# === CHAIN/FRANCHISE FILTERING ===
CHAIN_FILTER_ENABLED = True

# === SUBSIDIARY DETECTION ===
SUBSIDIARY_FILTER_ENABLED = True

# === API COST CONTROLS ===
# Scripts abort immediately when live-call cost for that step exceeds the cap.
# Cached responses cost $0 and do not count toward the cap.
# To raise a cap, edit here — never remove the cap entirely.
MAX_COST_USD_00 = 10.00        # Hard cap for step 00 (acquisition).  $0.032/call.
MAX_COST_USD_03 = 40.00        # Hard cap for step 03 (enrichment).   $0.017/call.
REQUIRE_CONFIRMATION = True    # Show estimate and ask Y/N before any live calls.
CHECKPOINT_EVERY_N_CALLS = 25  # Save partial results every N live calls (safety net).

# === API CACHING ===
CACHE_ENABLED = True
CACHE_TTL_HOURS = 168  # 7 days

# === WEBSITE VALIDATION ===
WEBSITE_VALIDATION_ENABLED = True
WEBSITE_TIMEOUT_SECONDS = 10
MAX_WEBSITE_CHECKS_PER_RUN = 500

# === GOOGLE PLACES CONFIG ===
GOOGLE_DELAY_SECONDS = 0.5

# === GRID SEARCH CONFIG ===
# Cost-optimized: keyword-first approach with targeted mini-grid.
# Full grid is disabled by default (enable FULL_GRID_ENABLED=True if needed).
# The mini-grid only covers known industrial/commercial zones in Oakville,
# not the full 221 sq km municipal area. This cuts grid cost by ~85%.
GRID_CELL_SIZE_M = 1000       # Only used by mini-grid zones
GRID_SEARCH_RADIUS_M = 800
GRID_MAX_RESULTS_PER_CELL = 60

# === ACQUISITION SEARCH KEYWORDS (English-only for Ontario) ===
# Phase 2 keyword supplement: targeted queries for sectors that may not
# appear in the type=establishment grid sweep.
ACQUISITION_KEYWORDS = [
    "company", "industrial", "manufacturing", "factory",
    "contractor", "construction", "renovation",
    "trucking", "freight", "warehouse", "logistics",
    "wholesale", "distributor", "supply",
    "equipment rental", "equipment service",
    "maintenance", "facility services",
    "engineering firm", "consulting firm",
    "it services", "managed services",
    "cleaning service", "janitorial",
    "landscaping", "property maintenance",
    "plumbing company", "hvac company",
    "electrical contractor", "roofing company",
    "printing company", "packaging",
    "staffing agency", "recruitment",
    "accounting firm", "financial services",
    "dental group", "veterinary clinic",
    "auto body", "collision repair",
    "security company", "pest control",
    "waste management", "recycling",
    "sign company", "signage",
    "moving company", "courier",
    "property management",
    "home care", "home health",
]

# === FILE PATHS ===
CHECKPOINT_RAW = "data/raw_candidates.csv"
CHECKPOINT_FILTERED = "data/filtered_candidates.csv"
CHECKPOINT_GOOGLE = "data/google_enriched.csv"
CHECKPOINT_DEDUPED = "data/deduped_candidates.csv"
CHECKPOINT_OWNER = "data/owner_enriched.csv"
CHECKPOINT_SCORED = "data/scored_candidates.csv"
OUTPUT_FINAL = "data/top_100_for_review.csv"
OUTPUT_EXCEL = "data/Oakville_Acquisition_Leads.xlsx"

# === TOGGLES ===
OWNER_ENRICHMENT_ENABLED = True   # Can disable if API keys unavailable
