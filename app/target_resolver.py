from __future__ import annotations

"""Resolve target candidates from dialogs visible to the authenticated account."""

from typing import List

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat
from telethon.utils import get_peer_id

from app.models import TargetCandidate


def _label_entity(entity: object) -> str:
    if isinstance(entity, Channel):
        if getattr(entity, "megagroup", False):
            return "megagroup"
        return "channel"
    if isinstance(entity, Chat):
        return "group"
    return "other"


async def fetch_target_candidates(client: TelegramClient) -> List[TargetCandidate]:
    """Load dialogs and return only channels/groups as discovery candidates."""
    candidates: List[TargetCandidate] = []
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if not isinstance(entity, (Channel, Chat)):
            continue
        type_label = _label_entity(entity)
        if type_label == "other":
            continue
        title = dialog.name or getattr(entity, "title", None) or str(getattr(entity, "id", ""))
        peer_id = get_peer_id(entity)
        username = getattr(entity, "username", None)
        candidates.append(
            TargetCandidate(
                title=str(title),
                type_label=type_label,
                peer_id=int(peer_id),
                username=str(username) if username else None,
            )
        )
    return candidates