"""
Fuzzy name matching for deduplication.
Uses thefuzz library for string similarity scoring.
"""

import re
from thefuzz import fuzz


def normalize_name(name):
    """Normalize a business name for comparison."""
    if not name:
        return ""
    name = str(name).lower().strip()

    # Remove common suffixes
    suffixes = [
        r"\b(inc|corp|ltd|llc|co|company|limited|incorporated)\b",
        r"\b(ontario|on|canada)\b",
        r"\b(oakville)\b",
    ]
    for pattern in suffixes:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)

    # Remove punctuation and extra whitespace
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def are_duplicates(name1, name2, threshold=85):
    """Check if two business names are likely duplicates.

    Uses token_sort_ratio which handles word reordering well.
    Returns (is_duplicate: bool, similarity_score: int).
    """
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)

    if not n1 or not n2:
        return False, 0

    # Exact match after normalization
    if n1 == n2:
        return True, 100

    # Token sort ratio handles word order differences
    score = fuzz.token_sort_ratio(n1, n2)
    return score >= threshold, score


def find_duplicates_in_dataframe(df, name_column="company_name", threshold=85):
    """Find duplicate groups in a DataFrame based on fuzzy name matching.

    Returns a list of (index_to_keep, indices_to_remove) tuples.
    """
    names = df[name_column].tolist()
    n = len(names)
    visited = set()
    duplicate_groups = []

    for i in range(n):
        if i in visited:
            continue

        group = [i]
        for j in range(i + 1, n):
            if j in visited:
                continue
            is_dup, score = are_duplicates(names[i], names[j], threshold)
            if is_dup:
                group.append(j)
                visited.add(j)

        if len(group) > 1:
            duplicate_groups.append(group)
        visited.add(i)

    return duplicate_groups
