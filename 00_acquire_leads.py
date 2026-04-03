"""
STEP 0: ACQUIRE LEADS (Oakville: Cost-Optimized)

Three-phase acquisition strategy, designed to minimize API cost:

  Phase 1 (PRIMARY): Keyword search — targeted textSearch queries for
           business types likely to hit $250K-$500K SDE. This is the
           main acquisition engine. ~40 keywords at $0.032/call = ~$1.30.

  Phase 2 (SUPPLEMENT): Mini-grid sweep of known industrial/commercial
           zones only (QEW corridor, Speers Rd, Winston Park). NOT all
           of Oakville. ~30-50 cells vs. 400+ for a full sweep. ~$1-$2.

  Phase 3 (OPTIONAL): Full grid sweep. Disabled by default. Enable via
           FULL_GRID_ENABLED=True in config.py if keyword+mini-grid
           yield fewer than TARGET_FINAL_LEADS candidates after filtering.

Deduplication is by Google place_id throughout.

Output: data/raw_candidates.csv

Requires: GOOGLE_PLACES_API_KEY in .env

Cost estimate (optimized):
  Keywords: ~40 keywords x 1-3 pages = $1.30-$3.84
  Mini-grid: ~40 cells x 1-3 pages = $1.28-$3.84
  Total: $2.58-$7.68 (vs. $26-$70 for full grid approach)
"""

import requests
import pandas as pd
import time
import json
import math
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from config import (
    GOOGLE_PLACES_API_KEY,
    GEO_BOUNDS,
    GOOGLE_DELAY_SECONDS,
    TARGET_CITY,
    TARGET_PROVINCE,
    TARGET_POSTAL_PREFIXES,
    CHECKPOINT_RAW,
    ACQUISITION_KEYWORDS,
    CACHE_ENABLED,
    MAX_COST_USD_00,
    REQUIRE_CONFIRMATION,
    CHECKPOINT_EVERY_N_CALLS,
)

NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
TEXT_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
CACHE_DIR = "data/cache/acquisition"

# Mini-grid config: only industrial/commercial zones, not all of Oakville.
MINI_GRID_CELL_SIZE_M = 1000   # Coarser than full grid
MINI_GRID_RADIUS_M = 800

# Full grid (disabled by default, enable via config)
FULL_GRID_ENABLED = False
FULL_GRID_CELL_SIZE_M = 1500   # Very coarse if enabled
FULL_GRID_RADIUS_M = 1200

# Oakville industrial/commercial zones for targeted mini-grid.
# Each zone is a small bounding box covering a known business corridor.
INDUSTRIAL_ZONES = [
    {
        "name": "QEW South Service Road Corridor",
        "south": 43.420, "north": 43.440,
        "west": -79.740, "east": -79.620,
    },
    {
        "name": "Speers Road Industrial Area",
        "south": 43.440, "north": 43.460,
        "west": -79.720, "east": -79.640,
    },
    {
        "name": "Winston Park / Burloak Employment Lands",
        "south": 43.385, "north": 43.415,
        "west": -79.785, "east": -79.740,
    },
    {
        "name": "Upper Middle / Eighth Line Business Parks",
        "south": 43.460, "north": 43.490,
        "west": -79.720, "east": -79.640,
    },
    {
        "name": "Cornwall Road / Cross Ave Commercial",
        "south": 43.435, "north": 43.450,
        "west": -79.690, "east": -79.640,
    },
]


def meters_to_degrees_lat(meters):
    """Convert meters to approximate latitude degrees."""
    return meters / 111_320


def meters_to_degrees_lng(meters, lat):
    """Convert meters to approximate longitude degrees at a given latitude."""
    return meters / (111_320 * math.cos(math.radians(lat)))


def generate_zone_grid_centers(zone, cell_size_m):
    """Generate grid cell center points for a single industrial zone."""
    centers = []
    mid_lat = (zone["south"] + zone["north"]) / 2
    lat_step = meters_to_degrees_lat(cell_size_m)
    lng_step = meters_to_degrees_lng(cell_size_m, mid_lat)

    lat = zone["south"]
    while lat <= zone["north"]:
        lng = zone["west"]
        while lng <= zone["east"]:
            centers.append((lat, lng))
            lng += lng_step
        lat += lat_step
    return centers


def generate_full_grid_centers(cell_size_m):
    """Generate grid for entire Oakville bounds (used only if FULL_GRID_ENABLED)."""
    centers = []
    mid_lat = (GEO_BOUNDS["south"] + GEO_BOUNDS["north"]) / 2
    lat_step = meters_to_degrees_lat(cell_size_m)
    lng_step = meters_to_degrees_lng(cell_size_m, mid_lat)

    lat = GEO_BOUNDS["south"]
    while lat <= GEO_BOUNDS["north"]:
        lng = GEO_BOUNDS["west"]
        while lng <= GEO_BOUNDS["east"]:
            centers.append((lat, lng))
            lng += lng_step
        lat += lat_step
    return centers


def cache_key(prefix, params_str):
    """Generate a safe filesystem cache key."""
    import hashlib
    h = hashlib.md5(params_str.encode()).hexdigest()[:12]
    return os.path.join(CACHE_DIR, f"{prefix}_{h}.json")


def cached_request(url, params, prefix="api"):
    """Make a cached API request.

    Returns (data, was_cached):
      - data:       JSON response dict, or None on failure.
      - was_cached: True if served from cache (costs $0), False if a live call.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    key_str = json.dumps(params, sort_keys=True)
    c_path = cache_key(prefix, key_str)

    if CACHE_ENABLED and os.path.exists(c_path):
        with open(c_path, "r") as f:
            return json.load(f), True

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if CACHE_ENABLED and data.get("status") in ("OK", "ZERO_RESULTS"):
            with open(c_path, "w") as f:
                json.dump(data, f)

        return data, False
    except requests.RequestException as e:
        print(f"    [ERROR] API request failed: {e}")
        return None, False


def extract_place_data(result):
    """Extract standardized fields from a Google Places result."""
    location = result.get("geometry", {}).get("location", {})
    return {
        "google_place_id": result.get("place_id", ""),
        "company_name": result.get("name", ""),
        "address_raw": result.get("vicinity", result.get("formatted_address", "")),
        "lat": location.get("lat"),
        "lng": location.get("lng"),
        "google_types": ",".join(result.get("types", [])),
        "google_rating": result.get("rating"),
        "review_count": result.get("user_ratings_total", 0),
        "business_status": result.get("business_status", ""),
        "price_level": result.get("price_level"),
    }


def fetch_all_pages(url, params, prefix, max_results=60):
    """Fetch up to 3 pages of Google Places results (20 per page, max 60).

    Returns (results, live_call_count) — live_call_count is the number of
    actual billed API calls made (cached pages count as 0).
    """
    all_results = []
    live_calls = 0

    data, was_cached = cached_request(url, params, prefix=prefix)
    if not was_cached:
        live_calls += 1
    if not data or data.get("status") not in ("OK", "ZERO_RESULTS"):
        return all_results, live_calls

    all_results.extend(data.get("results", []))

    page = 1
    while "next_page_token" in data and len(all_results) < max_results and page < 3:
        page += 1
        time.sleep(2.0)
        next_params = {
            "pagetoken": data["next_page_token"],
            "key": params["key"],
        }
        data, was_cached = cached_request(url, next_params, prefix=f"{prefix}_p{page}")
        if not was_cached:
            live_calls += 1
        if data and data.get("status") == "OK":
            all_results.extend(data.get("results", []))
        else:
            break

    return all_results, live_calls


COST_PER_CALL_00 = 0.032  # Google Text Search / Nearby Search rate


def is_stop_requested():
    """Return True if a STOP file exists in the project root (emergency abort)."""
    return os.path.exists("STOP")


def save_partial_checkpoint(places_dict, label="partial"):
    """Save whatever has been collected so far — protects against mid-run kills."""
    if not places_dict:
        return
    partial_path = CHECKPOINT_RAW.replace(".csv", f"_{label}.csv")
    os.makedirs(os.path.dirname(partial_path), exist_ok=True)
    pd.DataFrame(list(places_dict.values())).to_csv(partial_path, index=False)
    print(f"    [CHECKPOINT] {len(places_dict)} places saved -> {partial_path}")


def phase1_keyword_search(live_calls_so_far=0):
    """Phase 1 (PRIMARY): Keyword-based textSearch. Cheapest, highest signal.

    Returns (places_dict, live_calls_in_phase).
    Stops early if MAX_COST_USD_00 would be exceeded or STOP file detected.
    """
    print("\n  PHASE 1: Keyword Search (Primary Acquisition)")
    print("  " + "-" * 50)
    print(f"  Keywords: {len(ACQUISITION_KEYWORDS)}")

    all_places = {}
    phase_live_calls = 0
    total_live_calls = live_calls_so_far

    for i, keyword in enumerate(ACQUISITION_KEYWORDS):
        # --- STOP file check ---
        if is_stop_requested():
            print(f"\n  [STOP] STOP file detected after {phase_live_calls} live calls. Halting phase 1.")
            break

        # --- Hard cost cap check ---
        if total_live_calls * COST_PER_CALL_00 >= MAX_COST_USD_00:
            print(f"\n  [COST CAP] Reached ${MAX_COST_USD_00:.2f} limit "
                  f"({total_live_calls} live calls). Stopping phase 1.")
            break

        query = f"{keyword} {TARGET_CITY} {TARGET_PROVINCE}"
        params = {
            "query": query,
            "key": GOOGLE_PLACES_API_KEY,
        }

        results, call_count = fetch_all_pages(TEXT_URL, params, prefix=f"kw_{i}")
        phase_live_calls += call_count
        total_live_calls += call_count

        added = 0
        for r in results:
            pid = r.get("place_id")
            if pid and pid not in all_places:
                all_places[pid] = extract_place_data(r)
                added += 1

        if added > 0:
            cost_so_far = total_live_calls * COST_PER_CALL_00
            print(f"    [{keyword:35s}] +{added:>3} new  "
                  f"(total: {len(all_places)}, live calls: {total_live_calls}, "
                  f"est. cost: ${cost_so_far:.2f})")

        # --- Periodic checkpoint ---
        if phase_live_calls > 0 and phase_live_calls % CHECKPOINT_EVERY_N_CALLS == 0:
            save_partial_checkpoint(all_places, label="phase1_partial")

        time.sleep(GOOGLE_DELAY_SECONDS)

    print(f"  Phase 1 complete: {len(all_places)} unique places, "
          f"{phase_live_calls} live calls (${phase_live_calls * COST_PER_CALL_00:.2f})")
    return all_places, phase_live_calls


def phase2_mini_grid(existing_places, live_calls_so_far=0):
    """Phase 2 (SUPPLEMENT): Mini-grid sweep of industrial/commercial zones only.

    Returns (places_dict, live_calls_in_phase).
    """
    print("\n  PHASE 2: Mini-Grid (Industrial/Commercial Zones)")
    print("  " + "-" * 50)

    total_cells = 0
    new_places = 0
    phase_live_calls = 0
    total_live_calls = live_calls_so_far

    for zone in INDUSTRIAL_ZONES:
        centers = generate_zone_grid_centers(zone, MINI_GRID_CELL_SIZE_M)
        total_cells += len(centers)
        zone_new = 0

        for i, (lat, lng) in enumerate(centers):
            # --- STOP file check ---
            if is_stop_requested():
                print(f"\n  [STOP] STOP file detected. Halting phase 2.")
                save_partial_checkpoint(existing_places, label="phase2_partial")
                return existing_places, phase_live_calls

            # --- Hard cost cap check ---
            if total_live_calls * COST_PER_CALL_00 >= MAX_COST_USD_00:
                print(f"\n  [COST CAP] Reached ${MAX_COST_USD_00:.2f} limit. Stopping phase 2.")
                save_partial_checkpoint(existing_places, label="phase2_partial")
                return existing_places, phase_live_calls

            params = {
                "location": f"{lat},{lng}",
                "radius": MINI_GRID_RADIUS_M,
                "type": "establishment",
                "key": GOOGLE_PLACES_API_KEY,
            }

            results, call_count = fetch_all_pages(NEARBY_URL, params,
                                                  prefix=f"zone_{zone['name'][:10]}_{i}")
            phase_live_calls += call_count
            total_live_calls += call_count

            for r in results:
                pid = r.get("place_id")
                if pid and pid not in existing_places:
                    existing_places[pid] = extract_place_data(r)
                    new_places += 1
                    zone_new += 1

            # --- Periodic checkpoint ---
            if phase_live_calls > 0 and phase_live_calls % CHECKPOINT_EVERY_N_CALLS == 0:
                save_partial_checkpoint(existing_places, label="phase2_partial")

            time.sleep(GOOGLE_DELAY_SECONDS)

        print(f"    {zone['name']:45s} {len(centers):>3} cells  +{zone_new:>3} new")

    print(f"  Phase 2 complete: {new_places} new places from {total_cells} cells, "
          f"{phase_live_calls} live calls (${phase_live_calls * COST_PER_CALL_00:.2f})")
    return existing_places, phase_live_calls


def phase3_full_grid(existing_places, live_calls_so_far=0):
    """Phase 3 (OPTIONAL): Full grid sweep. Only runs if FULL_GRID_ENABLED=True."""
    if not FULL_GRID_ENABLED:
        print("\n  PHASE 3: Full Grid Sweep — DISABLED (set FULL_GRID_ENABLED=True to enable)")
        return existing_places, 0

    print("\n  PHASE 3: Full Grid Sweep (Fallback)")
    print("  " + "-" * 50)

    centers = generate_full_grid_centers(FULL_GRID_CELL_SIZE_M)
    print(f"  Grid cells: {len(centers)} ({FULL_GRID_CELL_SIZE_M}m spacing)")

    new_places = 0
    phase_live_calls = 0
    total_live_calls = live_calls_so_far

    for i, (lat, lng) in enumerate(centers):
        # --- STOP file check ---
        if is_stop_requested():
            print(f"\n  [STOP] STOP file detected at cell {i+1}. Halting phase 3.")
            save_partial_checkpoint(existing_places, label="phase3_partial")
            return existing_places, phase_live_calls

        # --- Hard cost cap check ---
        if total_live_calls * COST_PER_CALL_00 >= MAX_COST_USD_00:
            print(f"\n  [COST CAP] Reached ${MAX_COST_USD_00:.2f} limit at cell {i+1}. Stopping.")
            save_partial_checkpoint(existing_places, label="phase3_partial")
            return existing_places, phase_live_calls

        params = {
            "location": f"{lat},{lng}",
            "radius": FULL_GRID_RADIUS_M,
            "type": "establishment",
            "key": GOOGLE_PLACES_API_KEY,
        }

        results, call_count = fetch_all_pages(NEARBY_URL, params, prefix=f"fullgrid_{i}")
        phase_live_calls += call_count
        total_live_calls += call_count

        for r in results:
            pid = r.get("place_id")
            if pid and pid not in existing_places:
                existing_places[pid] = extract_place_data(r)
                new_places += 1

        if (i + 1) % CHECKPOINT_EVERY_N_CALLS == 0 or i == len(centers) - 1:
            print(f"    Cell {i+1}/{len(centers)}: +{new_places} new, "
                  f"{phase_live_calls} live calls (${phase_live_calls * COST_PER_CALL_00:.2f})")
            save_partial_checkpoint(existing_places, label="phase3_partial")

        time.sleep(GOOGLE_DELAY_SECONDS)

    print(f"  Phase 3 complete: {new_places} new places, "
          f"{phase_live_calls} live calls (${phase_live_calls * COST_PER_CALL_00:.2f})")
    return existing_places, phase_live_calls


def add_metadata(places_dict):
    """Add pipeline metadata columns to each place."""
    for pid, place in places_dict.items():
        place["data_source"] = "google_places"
        place["acquired_at"] = datetime.now().isoformat()
        place["pipeline_version"] = "oakville_v1"
    return places_dict


def basic_quality_filter(df):
    """Remove obviously non-business results before saving."""
    before = len(df)

    df = df[df["company_name"].str.strip().str.len() > 0].copy()
    df = df[df["business_status"] != "CLOSED_PERMANENTLY"].copy()

    non_business_types = [
        "locality", "political", "natural_feature",
        "park", "cemetery", "campground",
        "bus_station", "train_station", "transit_station",
        "parking", "gas_station", "atm",
    ]
    for nbt in non_business_types:
        df = df[~df["google_types"].str.contains(nbt, case=False, na=False)].copy()

    after = len(df)
    removed = before - after
    if removed > 0:
        print(f"  [QUALITY] Removed {removed} non-business entries")
    return df


def main():
    print("=" * 60)
    print(" STEP 0: ACQUIRE LEADS (Oakville Cost-Optimized)")
    print("=" * 60)

    if GOOGLE_PLACES_API_KEY == "YOUR_KEY_HERE":
        print("\n  [ERROR] GOOGLE_PLACES_API_KEY not set in .env file.")
        print("  Copy .env.example to .env and add your key. Exiting.")
        sys.exit(1)

    if os.path.exists("STOP"):
        print("\n  [STOP] STOP file found in project root. Remove it first, then re-run.")
        sys.exit(1)

    # ── Pre-flight cost estimate ───────────────────────────────────────────────
    kw_max_calls = len(ACQUISITION_KEYWORDS) * 3          # up to 3 pages each
    zone_cells = sum(len(generate_zone_grid_centers(z, MINI_GRID_CELL_SIZE_M))
                     for z in INDUSTRIAL_ZONES)
    grid_max_calls = zone_cells * 3                        # up to 3 pages each
    worst_case = (kw_max_calls + grid_max_calls) * COST_PER_CALL_00

    print(f"\n  ── Pre-flight Cost Estimate ──────────────────────────────")
    print(f"  Phase 1 (Keywords):  {len(ACQUISITION_KEYWORDS)} keywords × up to 3 pages "
          f"= up to {kw_max_calls} calls  (${kw_max_calls * COST_PER_CALL_00:.2f})")
    print(f"  Phase 2 (Mini-grid): {zone_cells} cells × up to 3 pages "
          f"= up to {grid_max_calls} calls  (${grid_max_calls * COST_PER_CALL_00:.2f})")
    print(f"  Worst case total:    ${worst_case:.2f}  "
          f"(cached pages cost $0 — likely much less)")
    print(f"  Hard cap:            ${MAX_COST_USD_00:.2f}  "
          f"(script aborts if live calls exceed this)")
    print(f"\n  To abort mid-run: create a file named STOP in the project root.")
    print(f"  Checkpoints saved every {CHECKPOINT_EVERY_N_CALLS} live calls -> "
          f"{CHECKPOINT_RAW.replace('.csv', '_*_partial.csv')}")

    if REQUIRE_CONFIRMATION:
        print(f"\n  Proceed with live API calls? [y/N]: ", end="", flush=True)
        answer = input().strip().lower()
        if answer not in ("y", "yes"):
            print("  Aborted by user.")
            sys.exit(0)

    # ── Run phases ─────────────────────────────────────────────────────────────
    places, calls_1 = phase1_keyword_search(live_calls_so_far=0)
    places, calls_2 = phase2_mini_grid(places, live_calls_so_far=calls_1)
    places, calls_3 = phase3_full_grid(places, live_calls_so_far=calls_1 + calls_2)

    # Add metadata
    places = add_metadata(places)

    # Convert to DataFrame
    df = pd.DataFrame(list(places.values()))
    total_live_calls = calls_1 + calls_2 + calls_3
    print(f"\n  Total unique places acquired: {len(df)}")
    print(f"  Total live API calls: {total_live_calls}")

    # Basic quality filter
    df = basic_quality_filter(df)

    # Save final output
    os.makedirs(os.path.dirname(CHECKPOINT_RAW), exist_ok=True)
    df.to_csv(CHECKPOINT_RAW, index=False, encoding="utf-8")
    print(f"\n  [OUTPUT] {len(df)} raw candidates saved -> {CHECKPOINT_RAW}")

    # Summary stats
    print(f"\n  Place type summary (top 15):")
    type_counts = {}
    for types_str in df["google_types"]:
        if pd.notna(types_str):
            for t in str(types_str).split(","):
                t = t.strip()
                if t:
                    type_counts[t] = type_counts.get(t, 0) + 1
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"    {t:35s} {c:>4}")

    # Cost breakdown (live calls only — cached calls cost $0)
    cost_kw = calls_1 * COST_PER_CALL_00
    cost_mini = calls_2 * COST_PER_CALL_00
    cost_full = calls_3 * COST_PER_CALL_00
    cost_total = cost_kw + cost_mini + cost_full

    print(f"\n  Cost breakdown (live calls only):")
    print(f"    Phase 1 (Keywords):   ${cost_kw:.2f}  ({calls_1} live calls)")
    print(f"    Phase 2 (Mini-grid):  ${cost_mini:.2f}  ({calls_2} live calls)")
    if calls_3 > 0:
        print(f"    Phase 3 (Full grid):  ${cost_full:.2f}  ({calls_3} live calls)")
    print(f"    TOTAL:                ${cost_total:.2f}  "
          f"(hard cap was ${MAX_COST_USD_00:.2f})")


if __name__ == "__main__":
    main()
