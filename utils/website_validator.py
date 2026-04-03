"""
Synchronous HTTP website validation.
Tests if a business website is reachable and returns a 200-class response.
"""

import requests
from urllib.parse import urlparse


def validate_website(url, timeout=10):
    """Validate a website URL. Returns (is_valid, final_url, status_code)."""
    if not url or str(url).strip() in ("", "nan", "None", "N/A"):
        return False, "", 0

    url = str(url).strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0 (compatible; LeadGen/1.0)"})
        if resp.status_code < 400:
            return True, resp.url, resp.status_code

        # HEAD failed, try GET (some servers block HEAD)
        resp = requests.get(url, timeout=timeout, allow_redirects=True,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; LeadGen/1.0)"},
                            stream=True)
        resp.close()
        return resp.status_code < 400, resp.url, resp.status_code

    except requests.RequestException:
        return False, url, 0


def normalize_url(url):
    """Normalize a URL for comparison (strip trailing slash, lowercase domain)."""
    if not url:
        return ""
    url = str(url).strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    domain = parsed.netloc.lower().lstrip("www.")
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{domain}{path}"
