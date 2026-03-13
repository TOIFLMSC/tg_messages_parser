from __future__ import annotations

"""Polling and per-message processing for each worker cycle."""

import asyncio
from typing import Dict, List, Optional, Tuple

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import Message

from app.filtering import match_keywords, normalize_text
from app.formatter import format_message
from app.links import extract_entity_links, extract_links_from_text, match_link_patterns
from app.models import MessagePayload, TaskConfig
from app.sender import send_bot_message, send_user_message
from app.state import StateManager
from app.telegram_client import get_entity_title


def _collect_text(message: Message) -> str:
    """Return the canonical body text, with caption only when it is separate."""
    text = message.message or ""
    if message.text and message.text != text:
        text = message.text
    caption = getattr(getattr(message, "media", None), "caption", None)
    if isinstance(caption, str) and caption and caption != text:
        if text:
            text = f"{text}\n{caption}"
        else:
            text = caption
    return text


def _build_original_link(entity: object, message: Message) -> Optional[str]:
    username = getattr(entity, "username", None)
    if username and message.id:
        return f"https://t.me/{username}/{message.id}"
    chat_id = getattr(entity, "id", None)
    if chat_id and message.id:
        return f"https://t.me/c/{str(chat_id).lstrip('-')}/{message.id}"
    return None


def _normalize_source(source: str) -> Tuple[object, str]:
    """Return a normalized source and a label describing how it is treated."""
    if source.lstrip("-").isdigit():
        return int(source), "numeric_id"
    return source, "raw"


def _normalize_target_value(target: str | int) -> Tuple[object, str]:
    if isinstance(target, int):
        return target, "numeric_id"
    if isinstance(target, str) and target.lstrip("-").isdigit():
        return int(target), "numeric_id"
    return target, "raw"


async def process_message(
    client: TelegramClient,
    task: TaskConfig,
    entity: object,
    message: Message,
    state: StateManager,
    target: str | int,
    logger,
) -> bool:
    text = _collect_text(message)
    if not text:
        return False

    matched_keywords = match_keywords(text, task.filters.keywords)
    # Extract links from both entities and plain text.
    entity_links = extract_entity_links(text, message.entities)
    plain_links = extract_links_from_text(text)
    all_links = [link for link in entity_links + plain_links if link]
    matched_links = match_link_patterns(all_links, task.filters.link_patterns)

    if not matched_keywords and not matched_links:
        return False

    normalized = normalize_text(text)
    dedup_hash = _hash_text(normalized)
    if await state.is_duplicate(dedup_hash):
        return False

    payload = MessagePayload(
        text=text,
        source_title=get_entity_title(entity),
        original_link=_build_original_link(entity, message),
        matched_keywords=matched_keywords,
        matched_links=matched_links,
    )
    outgoing = format_message(payload)
    if task.output.mode == "user":
        normalized_target, target_kind = _normalize_target_value(target)
        logger.debug(
            "Sending to target mode=user raw=%s type=%s normalized=%s kind=%s method=send_user_message",
            target,
            type(target).__name__,
            normalized_target,
            target_kind,
        )
        try:
            await send_user_message(client, normalized_target, outgoing)
        except Exception as exc:
            logger.error("Send failed for target %s: %s", normalized_target, exc)
            if target_kind == "numeric_id":
                logger.debug("Retrying send after dialog preload")
                await client.get_dialogs()
                await send_user_message(client, normalized_target, outgoing)
            else:
                raise
        logger.info("Sent matched message to target %s", normalized_target)
    elif task.output.mode == "bot":
        logger.debug("Sending to target mode=bot target=%s method=send_bot_message", target)
        if not task.output.bot_token:
            raise ValueError("Bot token is required for bot output mode")
        await send_bot_message(task.output.bot_token, target, outgoing, logger)
        logger.info("Sent matched message to bot target %s", target)
    else:
        raise ValueError(f"Unsupported output mode: {task.output.mode}")
    await state.add_hash(dedup_hash)
    return True


def _hash_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def fetch_messages(
    client: TelegramClient,
    entity: object,
    min_id: Optional[int] = None,
    limit: int = 50,
) -> List[Message]:
    messages: List[Message] = []
    kwargs = {"limit": limit}
    if min_id is not None:
        kwargs["min_id"] = min_id
    async for msg in client.iter_messages(entity, **kwargs):
        if isinstance(msg, Message):
            messages.append(msg)
    return list(reversed(messages))


async def poll_task_sources(
    client: TelegramClient,
    task: TaskConfig,
    state: StateManager,
    target: str | int,
    logger,
    last_ids: Dict[str, int],
) -> None:
    # One worker processes its sources sequentially for MVP simplicity.
    for source in task.sources:
        normalized_source, source_kind = _normalize_source(source)
        logger.debug(
            "Resolving source raw=%s type=%s normalized=%s kind=%s method=get_entity",
            source,
            type(source).__name__,
            normalized_source,
            source_kind,
        )
        try:
            entity = await client.get_entity(normalized_source)
        except Exception as exc:
            logger.error("Failed to resolve source %s: %s", source, exc)
            if source_kind == "numeric_id":
                logger.debug("Retrying source resolution after dialog preload")
                try:
                    await client.get_dialogs()
                    entity = await client.get_entity(normalized_source)
                except Exception as retry_exc:
                    logger.error("Retry failed for source %s: %s", source, retry_exc)
                    continue
            else:
                continue
        last_id = last_ids.get(source)
        try:
            logger.debug("Fetching messages for %s with min_id=%s limit=50", source, last_id)
            messages = await fetch_messages(client, entity, min_id=last_id)
        except FloodWaitError as exc:
            logger.warning("Flood wait for %s seconds", exc.seconds)
            await asyncio.sleep(exc.seconds)
            continue
        except Exception as exc:
            logger.error("Failed to fetch messages for %s: %s", source, exc)
            continue

        for message in messages:
            if last_id is None or message.id > last_id:
                last_id = message.id
            try:
                matched = await process_message(
                    client, task, entity, message, state, target, logger
                )
                if matched:
                    logger.info("Matched message %s", message.id)
            except FloodWaitError as exc:
                logger.warning("Flood wait during send %s seconds", exc.seconds)
                await asyncio.sleep(exc.seconds)
            except Exception as exc:
                logger.error("Failed to process message %s: %s", message.id, exc)
        if last_id is not None:
            last_ids[source] = last_id
