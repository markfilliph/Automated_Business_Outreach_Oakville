"""
Owner enrichment for Ontario businesses.

Three complementary free sources, tried in priority order:

  1. BBB Canada (bbb.org)
     Structured business profiles often list the "Principal" by name.
     Highest confidence — data is explicitly labelled.

  2. Website NER (HuggingFace dslim/bert-base-NER)
     Scrapes About/Team/Contact pages from the business website and
     extracts person names near owner-signal words via NER.
     Medium confidence — works for ~60% of businesses with real websites.

  3. DuckDuckGo SERP
     Searches for "[Company Name] [City] owner OR founder" and runs NER
     on the result snippets. Catches businesses with LinkedIn/news mentions.
     Low-medium confidence — broad coverage but unstructured.

All sources: synchronous requests only, file-based JSON cache, no asyncio.
"""

import re
import time
import requests
from bs4 import BeautifulSoup

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.cache import cache_get, cache_set

CACHE_DIR = "data/cache/owner"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT = 12

# Pages to try when scraping a business website for owner info
WEBSITE_PATHS = ["/about", "/about-us", "/our-team", "/team", "/contact", "/contact-us", ""]


# ── Source 1: BBB Canada ──────────────────────────────────────────────────────

def search_bbb(company_name, city="Oakville", province="ON"):
    """Search BBB Canada for a business and extract the Principal name.

    Returns (name, confidence, source) or ("", "none", reason).
    """
    cache_key = {"source": "bbb", "name": company_name, "city": city}
    cached = cache_get("bbb", cache_key, CACHE_DIR)
    if cached is not None:
        return cached.get("name", ""), cached.get("confidence", "none"), cached.get("source", "")

    try:
        search_url = "https://www.bbb.org/search"
        params = {
            "find_text": company_name,
            "find_loc": f"{city}, {province}",
        }
        resp = requests.get(search_url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return "", "none", f"BBB search HTTP {resp.status_code}"

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find first business result link
        result_link = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/profile/" in href or "/business/" in href:
                if not href.startswith("http"):
                    href = "https://www.bbb.org" + href
                result_link = href
                break

        if not result_link:
            _cache_miss(cache_key, "BBB: no results")
            return "", "none", "BBB: no results"

        time.sleep(1)
        detail_resp = requests.get(result_link, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if detail_resp.status_code != 200:
            _cache_miss(cache_key, f"BBB detail HTTP {detail_resp.status_code}")
            return "", "none", f"BBB detail HTTP {detail_resp.status_code}"

        detail_soup = BeautifulSoup(detail_resp.text, "html.parser")

        # BBB profiles label owner/officer as "Principal" in a definition list or table
        name = _extract_bbb_principal(detail_soup)
        if name:
            result = {"name": name, "confidence": "high", "source": "BBB (Principal)"}
            cache_set("bbb", cache_key, result, CACHE_DIR)
            return name, "high", "BBB (Principal)"

        _cache_miss(cache_key, "BBB: principal not listed")
        return "", "none", "BBB: principal not listed"

    except requests.RequestException as e:
        return "", "none", f"BBB error: {e}"


def _extract_bbb_principal(soup):
    """Extract Principal/Owner name from a BBB business detail page."""
    # Strategy 1: look for a label containing "Principal" near a value
    for tag in soup.find_all(string=re.compile(r"Principal", re.I)):
        parent = tag.parent
        # Sibling or parent's next sibling often has the name
        for candidate in [parent.find_next_sibling(), parent.parent.find_next_sibling()]:
            if candidate:
                text = candidate.get_text(strip=True)
                if text and len(text.split()) >= 2 and len(text) < 60:
                    return text

    # Strategy 2: look for structured data with "name" near "owner" or "principal"
    page_text = soup.get_text(" ", strip=True)
    match = re.search(
        r"Principal[:\s]+([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)?)",
        page_text
    )
    if match:
        return match.group(1).strip()

    return ""


def _cache_miss(cache_key, reason):
    cache_set("bbb", cache_key, {"name": "", "confidence": "none", "source": reason}, CACHE_DIR)


# ── Source 2: Website NER ─────────────────────────────────────────────────────

def enrich_from_website(website_url):
    """Scrape About/Team/Contact pages from the business website and run NER.

    Returns (name, confidence, source) or ("", "none", reason).
    """
    if not website_url or str(website_url).strip() in ("", "nan", "None"):
        return "", "none", "No website URL"

    cache_key = {"source": "website_ner", "url": website_url}
    cached = cache_get("website_ner", cache_key, CACHE_DIR)
    if cached is not None:
        return cached.get("name", ""), cached.get("confidence", "none"), cached.get("source", "")

    # Lazy import — only load transformers if this source is actually called
    from utils.ner_extractor import extract_owner_name

    base = website_url.rstrip("/")

    for path in WEBSITE_PATHS:
        url = base + path
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # Remove nav, footer, scripts — keep body content
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            text = soup.get_text(" ", strip=True)
            # Collapse whitespace
            text = re.sub(r"\s+", " ", text)

            name, confidence = extract_owner_name(text)
            if name:
                source_label = f"Website NER ({path or '/'})"
                result = {"name": name, "confidence": confidence, "source": source_label}
                cache_set("website_ner", cache_key, result, CACHE_DIR)
                return name, confidence, source_label

            time.sleep(0.5)

        except requests.RequestException:
            continue

    result = {"name": "", "confidence": "none", "source": "Website NER: no name found"}
    cache_set("website_ner", cache_key, result, CACHE_DIR)
    return "", "none", "Website NER: no name found"


# ── Source 3: DuckDuckGo SERP ─────────────────────────────────────────────────

def enrich_from_duckduckgo(company_name, city="Oakville"):
    """Search DuckDuckGo for owner info in result snippets.

    Uses the plain-HTML DDG endpoint (no JS, no API key needed).
    Returns (name, confidence, source) or ("", "none", reason).
    """
    cache_key = {"source": "ddg", "name": company_name, "city": city}
    cached = cache_get("ddg", cache_key, CACHE_DIR)
    if cached is not None:
        return cached.get("name", ""), cached.get("confidence", "none"), cached.get("source", "")

    from utils.ner_extractor import extract_owner_name

    query = f'"{company_name}" {city} owner OR founder OR president OR principal'

    try:
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "b": "", "kl": "ca-en"},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            _ddg_cache_miss(cache_key, f"DDG HTTP {resp.status_code}")
            return "", "none", f"DDG HTTP {resp.status_code}"

        soup = BeautifulSoup(resp.text, "html.parser")

        # Collect snippet text from result divs
        snippets = []
        for div in soup.find_all("div", class_=re.compile(r"result__snippet|result__body")):
            snippets.append(div.get_text(" ", strip=True))

        # Also grab result titles — sometimes "[Name], Owner at [Company]"
        for a in soup.find_all("a", class_=re.compile(r"result__a")):
            snippets.append(a.get_text(" ", strip=True))

        combined = " ".join(snippets[:10])  # top 10 results
        if not combined.strip():
            _ddg_cache_miss(cache_key, "DDG: no snippets")
            return "", "none", "DDG: no snippets"

        name, confidence = extract_owner_name(combined)
        if name:
            # DDG snippets are unstructured — cap confidence at "low"
            if confidence == "medium":
                confidence = "low"
            result = {"name": name, "confidence": confidence, "source": "DuckDuckGo SERP"}
            cache_set("ddg", cache_key, result, CACHE_DIR)
            return name, confidence, "DuckDuckGo SERP"

        _ddg_cache_miss(cache_key, "DDG: no name in snippets")
        return "", "none", "DDG: no name in snippets"

    except requests.RequestException as e:
        return "", "none", f"DDG error: {e}"


def _ddg_cache_miss(cache_key, reason):
    cache_set("ddg", cache_key, {"name": "", "confidence": "none", "source": reason}, CACHE_DIR)


# ── Main entry point ──────────────────────────────────────────────────────────

def enrich_owner(company_name, city="Oakville", province="ON", website=None, api_token=None):
    """Discover business owner name using three complementary free sources.

    Priority order (stops at first confident hit):
      1. BBB Canada          → high confidence if found
      2. Website NER         → medium confidence if found
      3. DuckDuckGo SERP     → low confidence (catchall)

    api_token param kept for backward compatibility but no longer used.
    Returns dict with owner_name, owner_confidence, owner_source.
    """
    # Source 1: BBB Canada
    name, confidence, source = search_bbb(company_name, city=city, province=province)
    if name:
        return {"owner_name": name, "owner_confidence": confidence, "owner_source": source}

    time.sleep(1.5)

    # Source 2: Website NER
    name, confidence, source = enrich_from_website(website)
    if name:
        return {"owner_name": name, "owner_confidence": confidence, "owner_source": source}

    time.sleep(2)

    # Source 3: DuckDuckGo SERP
    name, confidence, source = enrich_from_duckduckgo(company_name, city=city)
    if name:
        return {"owner_name": name, "owner_confidence": confidence, "owner_source": source}

    return {
        "owner_name": "Not found",
        "owner_confidence": "none",
        "owner_source": "BBB, Website NER, DDG — no owner identified",
    }
