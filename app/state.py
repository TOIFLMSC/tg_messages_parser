from __future__ import annotations

"""Async-safe JSON state storage for dedup and runtime metadata."""

import asyncio
import json
import os
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from app.models import DedupState, RuntimeState


class StateManager:
    def __init__(self, state_dir: str, ttl_hours: int, cleanup_interval_minutes: int) -> None:
        self._state_dir = state_dir
        self._hash_file = os.path.join(state_dir, "processed_hashes.json")
        self._runtime_file = os.path.join(state_dir, "runtime.json")
        self._ttl = timedelta(hours=ttl_hours)
        self._cleanup_interval = timedelta(minutes=cleanup_interval_minutes)
        # Shared async lock prevents concurrent JSON writes across workers.
        self._lock = asyncio.Lock()
        self._hashes = DedupState()
        self._runtime = RuntimeState()

    async def load(self) -> None:
        os.makedirs(self._state_dir, exist_ok=True)
        self._hashes = DedupState(items=self._read_json(self._hash_file).get("items", {}))
        self._runtime = RuntimeState(
            last_cleanup_iso=self._read_json(self._runtime_file).get("last_cleanup_iso")
        )

    async def is_duplicate(self, hash_value: str) -> bool:
        return hash_value in self._hashes.items

    async def add_hash(self, hash_value: str) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        self._hashes.items[hash_value] = now_iso
        await self._write_hashes()

    async def cleanup_if_due(self) -> int:
        now = datetime.now(timezone.utc)
        last_cleanup = self._parse_iso(self._runtime.last_cleanup_iso)
        if last_cleanup and now - last_cleanup < self._cleanup_interval:
            return 0
        return await self.cleanup(now)

    async def cleanup(self, now: Optional[datetime] = None) -> int:
        now = now or datetime.now(timezone.utc)
        expired_before = now - self._ttl
        to_delete = [
            key
            for key, value in self._hashes.items.items()
            if self._parse_iso(value) < expired_before
        ]
        for key in to_delete:
            self._hashes.items.pop(key, None)
        self._runtime.last_cleanup_iso = now.isoformat()
        await self._write_hashes()
        await self._write_runtime()
        return len(to_delete)

    def _parse_iso(self, value: Optional[str]) -> datetime:
        if not value:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _read_json(self, path: str) -> Dict[str, object]:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}

    async def _write_hashes(self) -> None:
        await self._write_json(self._hash_file, {"items": self._hashes.items})

    async def _write_runtime(self) -> None:
        await self._write_json(self._runtime_file, asdict(self._runtime))

    async def _write_json(self, path: str, payload: Dict[str, object]) -> None:
        async with self._lock:
            tmp_path = f"{path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)