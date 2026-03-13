from __future__ import annotations

"""Worker loop that repeatedly polls sources for one task."""

import asyncio
from typing import Dict

from telethon import TelegramClient

from app.logging_setup import get_task_logger
from app.models import TaskConfig
from app.polling import poll_task_sources
from app.state import StateManager


async def run_worker(
    client: TelegramClient,
    task: TaskConfig,
    state: StateManager,
) -> None:
    logger = get_task_logger("worker", task.name)
    last_ids: Dict[str, int] = {}
    target_label = task.output.target_title or task.output.target
    logger.info("Worker started (target=%s)", target_label)
    try:
        while True:
            logger.info("Polling cycle start")
            try:
                await poll_task_sources(
                    client, task, state, task.output.target, logger, last_ids
                )
                cleaned = await state.cleanup_if_due()
                if cleaned:
                    logger.info("Cleanup removed %s hashes", cleaned)
            except Exception as exc:
                logger.error("Worker cycle error: %s", exc)
            logger.info("Polling cycle end")
            await asyncio.sleep(task.interval_seconds)
    except asyncio.CancelledError:
        logger.info("Worker cancelled")
        raise
    finally:
        logger.info("Worker stopped")