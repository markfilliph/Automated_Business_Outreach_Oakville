"""
STEP 1: INGEST & NORMALIZE

Reads raw_candidates.csv from Step 0 and normalizes fields:
  - Standardize phone numbers
  - Extract postal codes from addresses
  - Extract city names
  - Clean company names (trim whitespace, fix encoding)
  - Add placeholder columns for downstream enrichment

This step also merges any additional raw data sources (e.g., manual CSV
imports from Chamber of Commerce, Yellow Pages scrapes, etc.) if present
in data/raw/.

Input:  data/raw_candidates.csv (+ optional data/raw/*.csv)
Output: data/raw_candidates.csv (overwritten with normalized version)
"""

import pandas as pd
import re
import os
import sys
import glob

sys.path.insert(0, os.path.dirname(__file__))
from config import CHECKPOINT_RAW, TARGET_POSTAL_PREFIXES


def normalize_phone(phone):
    """Normalize phone number to (905) 555-1234 format."""
    if pd.isna(phone) or not phone:
        return ""
    phone = str(phone).strip()
    digits = re.sub(r"[^\d]", "", phone)

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return phone  # Return as-is if we can't normalize


def extract_postal_code(address):
    """Extract Canadian postal code from address string."""
    if pd.isna(address):
        return ""
    # Canadian postal code pattern: A1A 1A1 or A1A1A1
    match = re.search(r"[A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d", str(address))
    if match:
        code = match.group().upper().replace(" ", "")
        return f"{code[:3]} {code[3:]}"  # Standardize to A1A 1A1
    return ""


def extract_city(address):
    """Extract city from address string. Default to Oakville."""
    if pd.isna(address):
        return "Oakville"

    address = str(address)
    # Common Oakville-area city names
    cities = ["Oakville", "Bronte", "Glen Abbey", "Clearview"]
    for city in cities:
        if city.lower() in address.lower():
            return city

    # Check for ON or Ontario in address (confirms it's in the right province)
    if re.search(r"\bON\b|\bOntario\b", address, re.IGNORECASE):
        # Try to extract city before ON/Ontario
        match = re.search(r",\s*([A-Za-z\s]+?),?\s*(?:ON|Ontario)", address, re.IGNORECASE)
        if match:
            city = match.group(1).strip()
            if city and len(city) > 2:
                return city

    return "Oakville"


_LOCATION_TAGS = [
    "oakville", "burlington", "mississauga", "toronto",
    "hamilton", "brampton", "milton", "gta",
]

_PROMO_PARENS = re.compile(
    r'\s*\([^)]*(?:works at|located in|serving|your #1|best in)[^)]*\)',
    re.IGNORECASE,
)

_CORPORATE_PARENS = re.compile(
    r'\([^)]*(?:canada|ontario|inc\.|ltd\.|corp\.|llc)[^)]*\)',
    re.IGNORECASE,
)


def clean_company_name(name):
    """Clean and normalize company name.

    Cleaning steps (applied in order after encoding fixes):
      1. Strip pipe-delimited marketing suffixes.
      2. Strip trailing location tags after ' - '.
      3. Strip promotional parenthetical phrases.
      4. Collapse comma-separated service lists (3+ segments → keep first).
      5. Re-trim and remove trailing punctuation.
    """
    if pd.isna(name):
        return ""
    name = str(name).strip()

    # Encoding fixes
    name = name.replace("\u2019", "'").replace("\u2013", " ").replace("\u2014", " ")
    name = name.replace("&amp;", "&")
    name = re.sub(r"\s+", " ", name)

    # 1. Strip everything after the first pipe
    if "|" in name:
        name = name.split("|")[0].strip()

    # 2. Strip trailing location tag after ' - '
    #    Only strip the LAST dash-segment if it is a known city/region.
    parts = name.split(" - ")
    if len(parts) > 1:
        last = parts[-1].strip().lower()
        if any(loc in last for loc in _LOCATION_TAGS):
            name = " - ".join(parts[:-1]).strip()

    # 3. Strip promotional parentheses; preserve corporate ones
    if _PROMO_PARENS.search(name) and not _CORPORATE_PARENS.search(name):
        name = _PROMO_PARENS.sub("", name).strip()

    # 4. Collapse comma-separated service lists (3+ segments → keep first)
    comma_parts = [p.strip() for p in name.split(",")]
    if len(comma_parts) >= 3:
        name = comma_parts[0]

    # 5. Final trim and remove trailing punctuation
    name = name.strip().rstrip(".,- ")

    return name


def merge_additional_sources(df):
    """Merge any additional CSV files from data/raw/ directory."""
    raw_dir = "data/raw"
    if not os.path.exists(raw_dir):
        return df

    additional_files = glob.glob(os.path.join(raw_dir, "*.csv"))
    if not additional_files:
        return df

    print(f"\n  Merging additional sources from {raw_dir}:")
    for filepath in additional_files:
        try:
            extra_df = pd.read_csv(filepath)
            # Map common column name variations
            col_map = {
                "name": "company_name",
                "business_name": "company_name",
                "business name": "company_name",
                "address": "address_raw",
                "full_address": "address_raw",
                "telephone": "phone",
                "phone_number": "phone",
                "url": "website",
                "web": "website",
            }
            extra_df.rename(columns={k: v for k, v in col_map.items()
                                     if k in extra_df.columns}, inplace=True)

            before = len(df)
            df = pd.concat([df, extra_df], ignore_index=True)
            added = len(df) - before
            print(f"    {os.path.basename(filepath)}: +{added} rows")
        except Exception as e:
            print(f"    {os.path.basename(filepath)}: SKIP ({e})")

    return df


def main():
    print("=" * 60)
    print(" STEP 1: INGEST & NORMALIZE")
    print("=" * 60)

    df = pd.read_csv(CHECKPOINT_RAW)
    print(f"  [INPUT] {len(df)} raw candidates from {CHECKPOINT_RAW}")

    # Merge additional sources
    df = merge_additional_sources(df)

    # Normalize fields
    print(f"\n  Normalizing {len(df)} records...")

    df["company_name"] = df["company_name"].apply(clean_company_name)
    df["phone"] = df.get("phone", pd.Series([""] * len(df))).apply(normalize_phone)
    df["postal_code"] = df["address_raw"].apply(extract_postal_code)
    df["city"] = df["address_raw"].apply(extract_city)

    # Add placeholder columns for downstream enrichment
    for col in ["website", "num_employees", "industry_description",
                "owner_name", "owner_confidence", "owner_source",
                "registration_date", "established_date",
                "website_valid"]:
        if col not in df.columns:
            df[col] = ""

    # Remove rows with empty names
    before = len(df)
    df = df[df["company_name"].str.strip().str.len() > 0].copy()
    if len(df) < before:
        print(f"  Removed {before - len(df)} rows with empty names")

    # Summary
    postal_found = len(df[df["postal_code"].str.len() > 0])
    print(f"\n  Normalization complete:")
    print(f"    Records:       {len(df)}")
    print(f"    Postal codes:  {postal_found}/{len(df)} extracted")
    print(f"    Phones:        {len(df[df['phone'].str.len() > 0])}/{len(df)} present")

    # City distribution
    print(f"\n  City distribution:")
    for city, count in df["city"].value_counts().head(5).items():
        print(f"    {city:20s} {count:>5}")

    # Save (overwrite)
    df.to_csv(CHECKPOINT_RAW, index=False, encoding="utf-8")
    print(f"\n  [OUTPUT] {len(df)} normalized candidates -> {CHECKPOINT_RAW}")


if __name__ == "__main__":
    main()
