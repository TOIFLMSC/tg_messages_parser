from __future__ import annotations

"""Formatting for outgoing messages (plain text MVP layout)."""

from typing import List

from app.models import MessagePayload


def format_message(payload: MessagePayload) -> str:
    """Compose the outgoing message with metadata lines appended."""
    lines: List[str] = []
    if payload.text:
        lines.append(payload.text)
    lines.append("")
    matched_keywords = ", ".join(payload.matched_keywords) if payload.matched_keywords else "none"
    matched_links = ", ".join(payload.matched_links) if payload.matched_links else "none"
    lines.append(f"Matched keywords: {matched_keywords}")
    lines.append(f"Matched links: {matched_links}")
    lines.append(f"Source: {payload.source_title}")
    original = payload.original_link if payload.original_link else "unavailable"
    lines.append(f"Original: {original}")
    return "\n".join(lines)