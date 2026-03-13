from __future__ import annotations

"""Run selected tasks concurrently within a single asyncio event loop."""

import asyncio
from typing import Iterable, List

from telethon import TelegramClient

from app.logging_setup import get_logger
from app.models import AppConfig, TaskConfig
from app.state import StateManager
from app.telegram_client import create_client
from app.worker import run_worker


async def run_tasks(config: AppConfig, tasks: Iterable[TaskConfig]) -> None:
    logger = get_logger("runner")
    selected = list(tasks)
    if not selected:
        logger.info("No tasks to run")
        return

    # Shared client and shared state live inside the same event loop.
    client = create_client(config.telegram)
    await client.start()
    logger.info("Telegram client started")

    state = StateManager(
        config.storage.state_dir,
        config.storage.hash_ttl_hours,
        config.storage.cleanup_interval_minutes,
    )
    await state.load()

    worker_tasks: List[asyncio.Task] = []
    for task in selected:
        worker_tasks.append(
            asyncio.create_task(
                run_worker(client, task, state),
                name=f"worker:{task.name}",
            )
        )

    try:
        await asyncio.gather(*worker_tasks)
    except asyncio.CancelledError:
        logger.info("Cancellation requested")
        for task in worker_tasks:
            task.cancel()
        await asyncio.gather(*worker_tasks, return_exceptions=True)
        raise
    finally:
        await client.disconnect()
        logger.info("Telegram client disconnected")