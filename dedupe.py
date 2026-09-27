"""Fuzzy de-duplication so the same posting reposted on two boards, or with a
slightly different title, is only shown once."""

from __future__ import annotations

from rapidfuzz import fuzz

DEFAULT_THRESHOLD = 90  # 0..100, higher means stricter (closer to identical)


def _key(posting) -> str:
    return f"{posting.title} {posting.organization}".strip().lower()


def dedupe_within(postings: list, threshold: int = DEFAULT_THRESHOLD) -> list:
    """Remove near-duplicates inside a single batch, keeping the first seen."""
    kept = []
    kept_keys = []
    for p in postings:
        k = _key(p)
        if any(fuzz.token_sort_ratio(k, kk) >= threshold for kk in kept_keys):
            continue
        kept.append(p)
        kept_keys.append(k)
    return kept


def is_duplicate_of_seen(posting, seen_keys: list, threshold: int = DEFAULT_THRESHOLD) -> bool:
    """True if this posting closely matches something we already stored."""
    k = _key(posting)
    return any(fuzz.token_sort_ratio(k, sk) >= threshold for sk in seen_keys)
