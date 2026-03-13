from __future__ import annotations

"""Text normalization and keyword matching for the MVP OR filter."""

import re
from typing import Iterable, List


def normalize_text(text: str) -> str:
    """Lowercase, trim, and collapse whitespace for dedup and matching."""
    normalized = text.lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def match_keywords(text: str, keywords: Iterable[str]) -> List[str]:
    """Return keywords that appear in the text (case-insensitive)."""
    if not text:
        return []
    normalized = normalize_text(text)
    matched: List[str] = []
    for keyword in keywords:
        if keyword.lower() in normalized:
            matched.append(keyword)
    return matched