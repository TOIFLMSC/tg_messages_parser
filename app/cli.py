from __future__ import annotations

"""CLI entrypoints, interactive task management, and target resolver flow."""

import argparse
import asyncio
from typing import List, Optional, Union

from app.config import ConfigError, load_config, save_config
from app.logging_setup import get_logger, set_debug_mode, setup_logging
from app.models import FilterConfig, TaskConfig, TaskOutputConfig, TargetCandidate
from app.runner import run_tasks
from app.target_resolver import fetch_target_candidates
from app.telegram_client import create_client


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="Telegram Filter Worker")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run tasks")
    run_parser.add_argument("task_name", nargs="?", help="Task name")
    run_parser.add_argument("--all", action="store_true", help="Run all enabled tasks")

    subparsers.add_parser("list-tasks", help="List tasks")
    subparsers.add_parser("add-task", help="Add a new task")

    edit_parser = subparsers.add_parser("edit-task", help="Edit a task")
    edit_parser.add_argument("task_name", help="Task name")

    delete_parser = subparsers.add_parser("delete-task", help="Delete a task")
    delete_parser.add_argument("task_name", help="Task name")

    subparsers.add_parser("resolve-target", help="Discover a target and optionally assign")

    args = parser.parse_args()
    config_path = "config.yaml"

    if not args.command:
        interactive_menu(config_path)
        return

    if args.command == "list-tasks":
        config = load_config_safe(config_path)
        apply_runtime_logging(config)
        list_tasks(config)
        return

    if args.command == "add-task":
        config = load_config_safe(config_path)
        apply_runtime_logging(config)
        add_task_interactive(config)
        save_config(config_path, config)
        return

    if args.command == "edit-task":
        config = load_config_safe(config_path)
        apply_runtime_logging(config)
        edit_task_interactive(config, args.task_name)
        save_config(config_path, config)
        return

    if args.command == "delete-task":
        config = load_config_safe(config_path)
        apply_runtime_logging(config)
        delete_task_interactive(config, args.task_name)
        save_config(config_path, config)
        return

    if args.command == "resolve-target":
        config = load_config_safe(config_path)
        apply_runtime_logging(config)
        resolve_target_interactive(config)
        save_config(config_path, config)
        return

    if args.command == "run":
        config = load_config_safe(config_path)
        apply_runtime_logging(config)
        tasks = select_run_tasks(config, args.task_name, args.all)
        try:
            asyncio.run(run_tasks(config, tasks))
        except KeyboardInterrupt:
            logger = get_logger("cli")
            logger.info("Shutdown requested")
        return


def load_config_safe(path: str):
    try:
        return load_config(path)
    except ConfigError as exc:
        raise SystemExit(f"Config error: {exc}")


def apply_runtime_logging(config) -> None:
    set_debug_mode(config.runtime.debug)


def list_tasks(config) -> None:
    if not config.tasks:
        print("No tasks configured")
        return
    for task in config.tasks:
        status = "enabled" if task.enabled else "disabled"
        target = task.output.target
        print(
            f"- {task.name} ({status}) interval={task.interval_seconds}s sources={len(task.sources)} target={target}"
        )


def select_run_tasks(config, task_name: Optional[str], run_all: bool):
    if run_all:
        return [task for task in config.tasks if task.enabled]
    if task_name:
        for task in config.tasks:
            if task.name == task_name:
                return [task]
        raise SystemExit(f"Task not found: {task_name}")
    raise SystemExit("Specify a task name or --all")


def interactive_menu(config_path: str) -> None:
    config = load_config_safe(config_path)
    apply_runtime_logging(config)
    print("Existing tasks:")
    list_tasks(config)
    print("\nChoose an action:")
    print("1. Run one task")
    print("2. Run all enabled tasks")
    print("3. Add a new task")
    print("4. Edit a task")
    print("5. Delete a task")
    print("6. Resolve target ID")
    print("7. Exit")
    choice = input("Enter choice: ").strip()

    if choice == "1":
        name = input("Task name: ").strip()
        tasks = select_run_tasks(config, name, False)
        try:
            asyncio.run(run_tasks(config, tasks))
        except KeyboardInterrupt:
            logger = get_logger("cli")
            logger.info("Shutdown requested")
        return
    if choice == "2":
        tasks = select_run_tasks(config, None, True)
        try:
            asyncio.run(run_tasks(config, tasks))
        except KeyboardInterrupt:
            logger = get_logger("cli")
            logger.info("Shutdown requested")
        return
    if choice == "3":
        add_task_interactive(config)
        save_config(config_path, config)
        return
    if choice == "4":
        name = input("Task name: ").strip()
        edit_task_interactive(config, name)
        save_config(config_path, config)
        return
    if choice == "5":
        name = input("Task name: ").strip()
        delete_task_interactive(config, name)
        save_config(config_path, config)
        return
    if choice == "6":
        resolve_target_interactive(config)
        save_config(config_path, config)
        return


def add_task_interactive(config) -> None:
    name = prompt_non_empty("Task name")
    if any(task.name == name for task in config.tasks):
        print("Task name already exists")
        return
    enabled = prompt_bool("Enabled", default=True)
    interval_seconds = prompt_int("Interval seconds", default=10)
    sources = prompt_list("Sources (comma-separated)")
    output_mode = prompt_output_mode(default="user")
    validate_numeric = output_mode == "user"
    output_target = prompt_output_target(
        config, label="Output target", validate_numeric=validate_numeric
    )
    bot_token = prompt_bot_token() if output_mode == "bot" else None
    output_title = prompt_optional("Output target title", default=None)
    keywords = prompt_list("Keywords (comma-separated)")
    link_patterns = prompt_list("Link patterns (comma-separated)")

    task = TaskConfig(
        name=name,
        enabled=enabled,
        interval_seconds=interval_seconds,
        sources=sources,
        output=TaskOutputConfig(
            mode=output_mode,
            target=output_target,
            target_title=output_title,
            bot_token=bot_token,
        ),
        filters=FilterConfig(mode="or", keywords=keywords, link_patterns=link_patterns),
    )
    config.tasks.append(task)


def edit_task_interactive(config, task_name: str) -> None:
    task = next((t for t in config.tasks if t.name == task_name), None)
    if task is None:
        raise SystemExit(f"Task not found: {task_name}")
    task.enabled = prompt_bool("Enabled", default=task.enabled)
    task.interval_seconds = prompt_int("Interval seconds", default=task.interval_seconds)
    task.sources = prompt_list("Sources (comma-separated)", default=task.sources)
    output_mode = prompt_output_mode(default=task.output.mode)
    validate_numeric = output_mode == "user"
    task.output.mode = output_mode
    task.output.target = prompt_output_target(
        config,
        label="Output target",
        default=task.output.target,
        validate_numeric=validate_numeric,
    )
    if output_mode == "bot":
        task.output.bot_token = prompt_bot_token(default=task.output.bot_token)
    else:
        task.output.bot_token = None
    task.output.target_title = prompt_optional(
        "Output target title", default=task.output.target_title
    )
    task.filters.keywords = prompt_list("Keywords (comma-separated)", default=task.filters.keywords)
    task.filters.link_patterns = prompt_list(
        "Link patterns (comma-separated)", default=task.filters.link_patterns
    )


def delete_task_interactive(config, task_name: str) -> None:
    task = next((t for t in config.tasks if t.name == task_name), None)
    if task is None:
        raise SystemExit(f"Task not found: {task_name}")
    confirm = prompt_bool(f"Delete task '{task_name}'", default=False)
    if confirm:
        config.tasks = [t for t in config.tasks if t.name != task_name]


def resolve_target_interactive(config) -> None:
    """Discover a target from dialogs and optionally assign it to a task."""
    logger = get_logger("cli")
    logger.info("Resolve-target started")
    try:
        candidates = asyncio.run(_load_target_candidates(config))
    except KeyboardInterrupt:
        logger.info("Target resolution cancelled")
        return

    if not candidates:
        print("No channel or group dialogs found for this account")
        return

    print("\nAvailable target candidates:")
    _print_candidates(candidates)

    selection = prompt_int("Select target number", default=0)
    if selection <= 0 or selection > len(candidates):
        print("Invalid selection")
        return
    candidate = candidates[selection - 1]

    print(
        f"\nSelected target: {candidate.title}\n"
        f"Type: {candidate.type_label}\n"
        f"ID: {candidate.peer_id}\n"
        f"Username: {('@' + candidate.username) if candidate.username else '-'}"
    )

    assign = prompt_bool("Assign this target to a task", default=False)
    if not assign:
        print("No changes made to config")
        return

    if not config.tasks:
        print("No tasks configured; cannot assign target")
        return

    task_name = prompt_task_name(config)
    task = next((t for t in config.tasks if t.name == task_name), None)
    if task is None:
        raise SystemExit(f"Task not found: {task_name}")

    task.output.target = candidate.peer_id
    task.output.target_title = candidate.title
    logger.info("Target assigned to task %s", task.name)
    print(f"Saved target ID for task '{task.name}': {candidate.peer_id}")


def _print_candidates(candidates: List[TargetCandidate]) -> None:
    for idx, candidate in enumerate(candidates, start=1):
        username = f"@{candidate.username}" if candidate.username else "-"
        print(
            f"{idx}. {candidate.title} | type={candidate.type_label} | id={candidate.peer_id} | username={username}"
        )


async def _load_target_candidates(config) -> List[TargetCandidate]:
    """Open an authenticated client, fetch dialogs, and return candidates."""
    client = create_client(config.telegram)
    await client.start()
    try:
        candidates = await fetch_target_candidates(client)
        logger = get_logger("cli")
        logger.info("Loaded %s target candidates", len(candidates))
        return candidates
    finally:
        await client.disconnect()


def prompt_task_name(config) -> str:
    if not config.tasks:
        raise SystemExit("No tasks configured")
    print("Available tasks:")
    for task in config.tasks:
        print(f"- {task.name}")
    return prompt_non_empty("Task name")



def prompt_output_mode(default: str = "user") -> str:
    """Prompt for output delivery mode."""
    while True:
        value = input(f"Output mode [user/bot] [{default}]: ").strip().lower()
        if not value:
            return default
        if value in {"user", "bot"}:
            return value
        print("Invalid mode; use 'user' or 'bot'")


def prompt_bot_token(default: Optional[str] = None) -> str:
    """Prompt for a bot token; required for bot mode."""
    prompt_default = default or ""
    while True:
        value = input(f"Bot token [{prompt_default}]: ").strip()
        if not value:
            if default:
                return default
            print("Bot token is required for bot mode")
            continue
        return value
def prompt_output_target(
    config,
    label: str,
    default: Optional[Union[str, int]] = None,
    validate_numeric: bool = True,
) -> Union[str, int]:
    """Prompt for output target and optionally validate numeric IDs via Telethon."""
    prompt_default = str(default) if default is not None else ""
    while True:
        value = input(f"{label} [{prompt_default}]: ").strip()
        if not value:
            if default is None:
                print("Output target is required")
                continue
            return default
        if _looks_numeric(value):
            if validate_numeric:
                resolved = asyncio.run(_validate_numeric_target(config, int(value)))
                if not resolved:
                    print("Numeric ID not resolved by Telegram; use resolve-target instead")
                    continue
            return int(value)
        return value


def prompt_non_empty(label: str) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if value:
            return value
        print("Value cannot be empty")


def prompt_optional(label: str, default: Optional[str]) -> Optional[str]:
    prompt_default = default or ""
    value = input(f"{label} [{prompt_default}]: ").strip()
    if not value:
        return default
    return value


def prompt_int(label: str, default: int) -> int:
    value = input(f"{label} [{default}]: ").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        print("Invalid number, using default")
        return default


def prompt_bool(label: str, default: bool) -> bool:
    default_label = "y" if default else "n"
    value = input(f"{label} [y/n] (default {default_label}): ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes", "1", "true"}


def prompt_list(label: str, default: Optional[List[str]] = None) -> List[str]:
    default = default or []
    prompt_default = ", ".join(default) if default else ""
    value = input(f"{label} [{prompt_default}]: ").strip()
    if not value:
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]


def _looks_numeric(value: str) -> bool:
    if value.startswith("-"):
        return value[1:].isdigit()
    return value.isdigit()


async def _validate_numeric_target(config, target_id: int) -> bool:
    """Only accept numeric IDs that Telethon can resolve for this account."""
    client = create_client(config.telegram)
    await client.start()
    try:
        await client.get_entity(target_id)
        return True
    except Exception:
        return False
    finally:
        await client.disconnect()



