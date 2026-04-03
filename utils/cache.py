"""
File-based JSON cache for API responses.
Avoids re-querying APIs on re-runs.
"""

import json
import os
import hashlib
import time

DEFAULT_CACHE_DIR = "data/cache"
DEFAULT_TTL_HOURS = 168  # 7 days


def get_cache_path(prefix, key_data, cache_dir=DEFAULT_CACHE_DIR):
    """Generate a filesystem-safe cache path from prefix and key data."""
    key_str = json.dumps(key_data, sort_keys=True) if isinstance(key_data, dict) else str(key_data)
    h = hashlib.md5(key_str.encode()).hexdigest()[:12]
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{prefix}_{h}.json")


def cache_get(prefix, key_data, cache_dir=DEFAULT_CACHE_DIR, ttl_hours=DEFAULT_TTL_HOURS):
    """Retrieve cached data. Returns None if not found or expired."""
    path = get_cache_path(prefix, key_data, cache_dir)

    if not os.path.exists(path):
        return None

    try:
        # Check TTL (getmtime can raise OSError on permission issues)
        age_hours = (time.time() - os.path.getmtime(path)) / 3600
        if age_hours > ttl_hours:
            return None

        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        return None


def cache_set(prefix, key_data, value, cache_dir=DEFAULT_CACHE_DIR):
    """Store data in cache."""
    path = get_cache_path(prefix, key_data, cache_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    try:
        with open(path, "w") as f:
            json.dump(value, f)
        return True
    except (TypeError, IOError) as e:
        print(f"  [CACHE] Write failed: {e}")
        return False
