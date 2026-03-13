from __future__ import annotations

"""Logging setup with task-aware adapters."""

import logging


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def set_debug_mode(enabled: bool) -> None:
    level = logging.DEBUG if enabled else logging.INFO
    logging.getLogger().setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class TaskLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        task_name = self.extra.get("task_name", "unknown")
        return f"[{task_name}] {msg}", kwargs


def get_task_logger(name: str, task_name: str) -> TaskLoggerAdapter:
    logger = logging.getLogger(name)
    return TaskLoggerAdapter(logger, {"task_name": task_name})
