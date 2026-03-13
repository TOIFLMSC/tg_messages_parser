from __future__ import annotations

"""URL extraction and link pattern matching for MVP link filters."""

import re
from typing import Iterable, List, Optional, Sequence

from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl

URL_REGEX = re.compile(r"https?://[^\s<>\]\[\)\(]+", re.IGNORECASE)


def extract_links_from_text(text: str) -> List[str]:
    """Extract plain-text URLs from message content."""
    if not text:
        return []
    return URL_REGEX.findall(text)


def extract_entity_links(text: str, entities: Optional[Sequence[object]]) -> List[str]:
    """Extract URLs from Telegram entities (inline URLs and URL text entities)."""
    links: List[str] = []
    if not entities:
        return links
    for entity in entities:
        if isinstance(entity, MessageEntityTextUrl) and entity.url:
            links.append(entity.url)
        elif isinstance(entity, MessageEntityUrl):
            offset = getattr(entity, "offset", 0)
            length = getattr(entity, "length", 0)
            if offset is None or length is None:
                continue
            if 0 <= offset < len(text):
                links.append(text[offset : offset + length])
    return links


def match_link_patterns(links: Iterable[str], patterns: Iterable[str]) -> List[str]:
    """Match configured patterns as case-insensitive substrings of URLs."""
    matched: List[str] = []
    patterns_normalized = [p.lower() for p in patterns if p]
    for link in links:
        link_lower = link.lower()
        for pattern in patterns_normalized:
            if pattern in link_lower:
                matched.append(link)
                break
    return matched