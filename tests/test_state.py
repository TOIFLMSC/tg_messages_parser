import asyncio

import pytest

from app.state import StateManager


@pytest.mark.asyncio
async def test_state_persist_roundtrip(tmp_path):
    state_dir = tmp_path / "state"
    manager = StateManager(str(state_dir), ttl_hours=24, cleanup_interval_minutes=10)
    await manager.load()
    assert await manager.is_duplicate("abc") is False
    await manager.add_hash("abc")
    assert await manager.is_duplicate("abc") is True

    other = StateManager(str(state_dir), ttl_hours=24, cleanup_interval_minutes=10)
    await other.load()
    assert await other.is_duplicate("abc") is True


@pytest.mark.asyncio
async def test_global_dedup_across_tasks(tmp_path):
    state_dir = tmp_path / "state"
    task_a = StateManager(str(state_dir), ttl_hours=24, cleanup_interval_minutes=10)
    task_b = StateManager(str(state_dir), ttl_hours=24, cleanup_interval_minutes=10)
    await task_a.load()
    await task_b.load()
    await task_a.add_hash("same")
    await task_b.load()
    assert await task_b.is_duplicate("same") is True
