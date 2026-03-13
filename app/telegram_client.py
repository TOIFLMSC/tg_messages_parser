from __future__ import annotations

"""Telethon client helpers for session-based auth and basic entity info."""

from telethon import TelegramClient

from app.models import TelegramConfig


def create_client(config: TelegramConfig) -> TelegramClient:
    """Create a Telethon client using the configured session name and credentials."""
    return TelegramClient(config.session_name, config.api_id, config.api_hash)


def get_entity_title(entity: object) -> str:
    """Best-effort title/identifier for logging and output metadata."""
    title = getattr(entity, "title", None)
    if isinstance(title, str) and title:
        return title
    username = getattr(entity, "username", None)
    if isinstance(username, str) and username:
        return f"@{username}"
    return str(getattr(entity, "id", "unknown"))