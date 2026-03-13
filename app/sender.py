from __future__ import annotations

"""Async sender wrapper to keep Telegram I/O in one place."""

from typing import Union

import httpx
from telethon import TelegramClient

from app.models import TaskOutputConfig


def _normalize_target(target: Union[str, int]) -> tuple[Union[str, int], str]:
    if isinstance(target, int):
        return target, "numeric_id"
    if isinstance(target, str) and target.lstrip("-").isdigit():
        return int(target), "numeric_id"
    return target, "raw"


def _mask_token(token: str) -> str:
    token = token.strip()
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


def _normalize_bot_target(target: Union[str, int]) -> Union[str, int]:
    if isinstance(target, int):
        return target
    if isinstance(target, str) and target.lstrip("-").isdigit():
        return int(target)
    return target


async def send_user_message(client: TelegramClient, target: Union[str, int], text: str) -> None:
    """Send a text message via the authenticated user account."""
    normalized_target, _ = _normalize_target(target)
    await client.send_message(normalized_target, text)


async def send_bot_message(
    token: str, target: Union[str, int], text: str, logger
) -> None:
    """Send a text message through the Telegram Bot API."""
    normalized_target = _normalize_bot_target(target)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": normalized_target, "text": text}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok", False):
            raise RuntimeError(data.get("description", "Bot API error"))
    except Exception as exc:
        masked = _mask_token(token)
        logger.error(
            "Bot send failed for target %s (token=%s): %s",
            normalized_target,
            masked,
            exc,
        )
        raise RuntimeError("Bot send failed") from None


async def send_output_message(
    client: TelegramClient, output: TaskOutputConfig, text: str, logger
) -> None:
    """Route the outgoing message to the task's configured output backend."""
    if output.mode == "user":
        await send_user_message(client, output.target, text)
        return
    if output.mode == "bot":
        if not output.bot_token:
            raise ValueError("Bot token is required for bot output mode")
        await send_bot_message(output.bot_token, output.target, text, logger)
        return
    raise ValueError(f"Unsupported output mode: {output.mode}")

