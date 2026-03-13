from __future__ import annotations

"""Config loading and validation for config.yaml."""

import logging
import os
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Union

import yaml

from app.models import (
    AppConfig,
    FilterConfig,
    RuntimeConfig,
    StorageConfig,
    TaskConfig,
    TaskOutputConfig,
    TelegramConfig,
)


class ConfigError(ValueError):
    pass


LOGGER = logging.getLogger("config")
REQUIRED_TOP_LEVEL = {"telegram", "storage", "runtime", "tasks"}


def load_config(path: str) -> AppConfig:
    """Load and validate config.yaml into typed dataclasses."""
    if not os.path.exists(path):
        raise ConfigError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as handle:
        try:
            raw = yaml.safe_load(handle) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"Invalid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("Config root must be a mapping")

    # Validate top-level keys early to give clear errors.
    missing = REQUIRED_TOP_LEVEL - set(raw.keys())
    if missing:
        raise ConfigError(f"Missing top-level keys: {', '.join(sorted(missing))}")

    telegram = _parse_telegram(raw.get("telegram"))
    storage = _parse_storage(raw.get("storage"))
    runtime = _parse_runtime(raw.get("runtime"))
    legacy_output = _parse_legacy_output(raw.get("output"))
    tasks = _parse_tasks(raw.get("tasks"), legacy_output)

    if legacy_output:
        LOGGER.warning("Global output is deprecated; use task-level output instead")

    return AppConfig(
        telegram=telegram,
        storage=storage,
        runtime=runtime,
        tasks=tasks,
        legacy_output=legacy_output,
    )


def save_config(path: str, config: AppConfig) -> None:
    """Serialize config back to YAML with task-level output only."""
    payload = {
        "telegram": asdict(config.telegram),
        "storage": asdict(config.storage),
        "runtime": asdict(config.runtime),
        "tasks": [
            {
                "name": task.name,
                "enabled": task.enabled,
                "interval_seconds": task.interval_seconds,
                "sources": list(task.sources),
                "output": _serialize_task_output(task.output),
                "filters": {
                    "mode": task.filters.mode,
                    "keywords": list(task.filters.keywords),
                    "link_patterns": list(task.filters.link_patterns),
                },
            }
            for task in config.tasks
        ],
    }
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)
    LOGGER.info("Config saved to %s", path)


def _parse_telegram(raw: Any) -> TelegramConfig:
    if not isinstance(raw, dict):
        raise ConfigError("telegram must be a mapping")
    api_id = _require_int(raw.get("api_id"), "telegram.api_id")
    api_hash = _require_str(raw.get("api_hash"), "telegram.api_hash")
    session_name = _require_str(raw.get("session_name"), "telegram.session_name")
    return TelegramConfig(api_id=api_id, api_hash=api_hash, session_name=session_name)


def _parse_legacy_output(raw: Any) -> Optional[TaskOutputConfig]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError("output must be a mapping when present")
    if "mode" not in raw:
        LOGGER.warning(
            "Ignoring legacy top-level output; tasks[].output.mode is required"
        )
        return None
    return _parse_task_output(raw, "output")


def _parse_task_output(raw: Any, path: str) -> TaskOutputConfig:
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must be a mapping")
    mode = raw.get("mode")
    if not isinstance(mode, str) or not mode.strip():
        raise ConfigError(f"{path}.mode is required and must be a string")
    mode = mode.strip().lower()
    if mode not in {"user", "bot"}:
        raise ConfigError(f"{path}.mode must be 'user' or 'bot'")
    target = _require_target(raw.get("target"), f"{path}.target")
    bot_token = raw.get("bot_token")
    if mode == "bot":
        bot_token = _require_str(bot_token, f"{path}.bot_token")
    elif bot_token is not None:
        if not isinstance(bot_token, str) or not bot_token.strip():
            raise ConfigError(f"{path}.bot_token must be a non-empty string if set")
        bot_token = bot_token.strip()
    target_title = raw.get("target_title")
    if target_title is not None:
        if not isinstance(target_title, str) or not target_title.strip():
            raise ConfigError(f"{path}.target_title must be a non-empty string if set")
        target_title = target_title.strip()
    return TaskOutputConfig(
        mode=mode,
        target=target,
        target_title=target_title,
        bot_token=bot_token,
    )


def _serialize_task_output(output: TaskOutputConfig) -> Dict[str, object]:
    payload: Dict[str, object] = {"mode": output.mode, "target": output.target}
    if output.target_title:
        payload["target_title"] = output.target_title
    if output.bot_token:
        payload["bot_token"] = output.bot_token
    return payload


def _parse_storage(raw: Any) -> StorageConfig:
    if not isinstance(raw, dict):
        raise ConfigError("storage must be a mapping")
    state_dir = _require_str(raw.get("state_dir"), "storage.state_dir")
    hash_ttl_hours = _require_int(raw.get("hash_ttl_hours"), "storage.hash_ttl_hours")
    cleanup_interval_minutes = _require_int(
        raw.get("cleanup_interval_minutes"), "storage.cleanup_interval_minutes"
    )
    return StorageConfig(
        state_dir=state_dir,
        hash_ttl_hours=hash_ttl_hours,
        cleanup_interval_minutes=cleanup_interval_minutes,
    )


def _parse_runtime(raw: Any) -> RuntimeConfig:
    if not isinstance(raw, dict):
        raise ConfigError("runtime must be a mapping")
    default_selection = raw.get("default_interactive_task_selection", True)
    if not isinstance(default_selection, bool):
        raise ConfigError("runtime.default_interactive_task_selection must be boolean")
    debug = raw.get("debug", False)
    if not isinstance(debug, bool):
        raise ConfigError("runtime.debug must be boolean")
    return RuntimeConfig(default_interactive_task_selection=default_selection, debug=debug)


def _parse_tasks(raw: Any, legacy_output: Optional[TaskOutputConfig]) -> List[TaskConfig]:
    if not isinstance(raw, list):
        raise ConfigError("tasks must be a list")
    tasks: List[TaskConfig] = []
    seen_names = set()
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ConfigError(f"tasks[{idx}] must be a mapping")
        name = _require_str(item.get("name"), f"tasks[{idx}].name")
        if name in seen_names:
            raise ConfigError(f"Duplicate task name: {name}")
        seen_names.add(name)
        enabled = _require_bool(item.get("enabled"), f"tasks[{idx}].enabled")
        interval_seconds = _require_positive_int(
            item.get("interval_seconds"), f"tasks[{idx}].interval_seconds"
        )
        sources = _require_str_list(item.get("sources"), f"tasks[{idx}].sources")
        output_raw = item.get("output")
        if output_raw is None:
            raise ConfigError(f"tasks[{idx}].output is required and must include mode")
        output = _parse_task_output(output_raw, f"tasks[{idx}].output")
        filters = _parse_filters(item.get("filters"), f"tasks[{idx}].filters")
        tasks.append(
            TaskConfig(
                name=name,
                enabled=enabled,
                interval_seconds=interval_seconds,
                sources=sources,
                output=output,
                filters=filters,
            )
        )
    return tasks


def _parse_filters(raw: Any, path: str) -> FilterConfig:
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must be a mapping")
    mode = _require_str(raw.get("mode", "or"), f"{path}.mode")
    if mode.lower() != "or":
        raise ConfigError(f"{path}.mode must be 'or' in MVP")
    keywords = _require_str_list(raw.get("keywords", []), f"{path}.keywords")
    link_patterns = _require_str_list(raw.get("link_patterns", []), f"{path}.link_patterns")
    return FilterConfig(mode=mode.lower(), keywords=keywords, link_patterns=link_patterns)


def _require_str(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{path} must be a non-empty string")
    return value.strip()


def _require_int(value: Any, path: str) -> int:
    if not isinstance(value, int):
        raise ConfigError(f"{path} must be an integer")
    return value


def _require_positive_int(value: Any, path: str) -> int:
    value = _require_int(value, path)
    if value <= 0:
        raise ConfigError(f"{path} must be a positive integer (> 0)")
    return value


def _require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{path} must be a boolean")
    return value


def _require_str_list(value: Any, path: str) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError(f"{path} must be a list of strings")
    items: List[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ConfigError(f"{path}[{idx}] must be a non-empty string")
        items.append(item.strip())
    return items


def _require_target(value: Any, path: str) -> Union[str, int]:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ConfigError(f"{path} must be a non-empty string or integer ID")


