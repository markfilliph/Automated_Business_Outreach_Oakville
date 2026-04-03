"""
Employee count estimation heuristic.

Estimates employee range when num_employees is not available from
Google Places data. Uses four signal layers in priority order:

  1. Existing num_employees field (direct, authoritative)
  2. Google Places type signals (type-specific baselines)
  3. Review count proxy (size correlates with review volume)
  4. B2B name signals + corporate suffix (manufacturing, wholesale, etc.)

Returns a dict or None (if no estimate possible).
"""

import re
import pandas as pd


# Google Places types → (range_string, midpoint)
_TYPE_BASELINES = {
    "general_contractor":   ("15-50",  32),
    "electrician":          ("5-20",   12),
    "plumber":              ("5-20",   12),
    "roofing_contractor":   ("5-20",   12),
    "moving_company":       ("10-30",  20),
    "car_repair":           ("5-15",   10),
    "car_dealer":           ("5-15",   10),
    "accounting":           ("5-20",   12),
    "dentist":              ("5-15",   10),
    "veterinary_care":      ("5-15",   10),
    "physiotherapist":      ("3-10",    6),
    "real_estate_agency":   ("3-10",    6),
}

_B2B_SIGNALS = [
    "manufacturing", "industrial", "wholesale", "distribution",
    "logistics", "warehouse", "construction", "contractor",
]

_CORPORATE_SUFFIXES = re.compile(
    r'\b(inc|ltd|corp|group)\b', re.IGNORECASE
)


def estimate_employee_range(row):
    """Estimate employee count range from available signals.

    Returns dict with keys:
      employee_range    — string e.g. "10-30"
      employee_midpoint — int e.g. 20
      employee_source   — string describing which rule fired

    Returns None if no estimate is possible.
    """
    # Rule 1: existing num_employees field
    emp = row.get("num_employees")
    if pd.notna(emp) and emp not in ("", "nan", "None"):
        try:
            val = float(emp)
            if val > 0:
                return {
                    "employee_range": _midpoint_to_range(int(val)),
                    "employee_midpoint": int(val),
                    "employee_source": "google_places_direct",
                }
        except (ValueError, TypeError):
            pass

    google_types = str(row.get("google_types", "") or "").lower()
    company_name = str(row.get("company_name", "") or "").lower()

    # Rule 2: Google Places type signals
    for type_key, (range_str, midpoint) in _TYPE_BASELINES.items():
        if type_key in google_types:
            return {
                "employee_range": range_str,
                "employee_midpoint": midpoint,
                "employee_source": f"google_type:{type_key}",
            }

    # Rule 3: review count proxy
    reviews = row.get("review_count", 0)
    try:
        reviews = int(float(reviews)) if pd.notna(reviews) else 0
    except (ValueError, TypeError):
        reviews = 0

    if reviews >= 100:
        return {"employee_range": "20-75",  "employee_midpoint": 47, "employee_source": "review_count_proxy"}
    elif reviews >= 50:
        return {"employee_range": "15-50",  "employee_midpoint": 32, "employee_source": "review_count_proxy"}
    elif reviews >= 15:
        return {"employee_range": "10-30",  "employee_midpoint": 20, "employee_source": "review_count_proxy"}
    elif reviews >= 5:
        return {"employee_range": "5-15",   "employee_midpoint": 10, "employee_source": "review_count_proxy"}
    elif reviews >= 1:
        return {"employee_range": "2-10",   "employee_midpoint":  6, "employee_source": "review_count_proxy"}

    # Rule 4: B2B name signals + corporate suffix
    has_b2b = any(signal in company_name for signal in _B2B_SIGNALS)
    has_suffix = bool(_CORPORATE_SUFFIXES.search(company_name))
    if has_b2b and has_suffix:
        return {
            "employee_range": "10-50",
            "employee_midpoint": 30,
            "employee_source": "b2b_name_signal",
        }

    return None


def estimate_business_age(review_count):
    """Estimate business age in years from Google review count.

    Review volume is a weak but non-zero proxy for longevity — businesses
    accumulate reviews over time. Returns a (years_midpoint, label) tuple,
    or None if no reviews are available.

    Thresholds (conservative — biased toward underestimating age):
      100+ reviews  → likely 15+ years  (midpoint: 18)
       50-99        → likely 10-15 years (midpoint: 12)
       20-49        → likely 5-10 years  (midpoint: 7)
        5-19        → likely 3-5 years   (midpoint: 4)
        1-4         → likely 1-3 years   (midpoint: 2)
        0           → unknown            (None)
    """
    try:
        reviews = int(float(review_count)) if review_count is not None else 0
    except (ValueError, TypeError):
        reviews = 0

    if reviews >= 100:
        return {"estimated_years": 18, "age_label": "15+ years (review proxy)"}
    elif reviews >= 50:
        return {"estimated_years": 12, "age_label": "10-15 years (review proxy)"}
    elif reviews >= 20:
        return {"estimated_years": 7,  "age_label": "5-10 years (review proxy)"}
    elif reviews >= 5:
        return {"estimated_years": 4,  "age_label": "3-5 years (review proxy)"}
    elif reviews >= 1:
        return {"estimated_years": 2,  "age_label": "1-3 years (review proxy)"}
    return None


def _midpoint_to_range(emp):
    """Convert a known employee count to a display range string."""
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
