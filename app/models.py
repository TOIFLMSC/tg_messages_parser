from __future__ import annotations

"""Shared dataclasses used across modules."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union


@dataclass
class TelegramConfig:
    api_id: int
    api_hash: str
    session_name: str


@dataclass
class TaskOutputConfig:
    mode: str
    target: Union[str, int]
    target_title: Optional[str] = None
    bot_token: Optional[str] = None


@dataclass
class StorageConfig:
    state_dir: str
    hash_ttl_hours: int
    cleanup_interval_minutes: int


@dataclass
class RuntimeConfig:
    default_interactive_task_selection: bool = True
    debug: bool = False


@dataclass
class FilterConfig:
    mode: str
    keywords: List[str] = field(default_factory=list)
    link_patterns: List[str] = field(default_factory=list)


@dataclass
class TaskConfig:
    name: str
    enabled: bool
    interval_seconds: int
    sources: List[str]
    output: TaskOutputConfig
    filters: FilterConfig


@dataclass
class AppConfig:
    telegram: TelegramConfig
    storage: StorageConfig
    runtime: RuntimeConfig
    tasks: List[TaskConfig]
    legacy_output: Optional[TaskOutputConfig] = None


@dataclass
class MatchResult:
    matched_keywords: List[str] = field(default_factory=list)
    matched_links: List[str] = field(default_factory=list)


@dataclass
class MessagePayload:
    text: str
    source_title: str
    original_link: Optional[str]
    matched_keywords: List[str]
    matched_links: List[str]


@dataclass
class DedupState:
    items: Dict[str, str] = field(default_factory=dict)


@dataclass
class RuntimeState:
    last_cleanup_iso: Optional[str] = None


@dataclass
class TargetCandidate:
    title: str
    type_label: str
    peer_id: int
    username: Optional[str] = None
