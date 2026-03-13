import types
import pytest

from app.models import FilterConfig, TaskConfig, TaskOutputConfig
from app.polling import process_message


class FakeState:
    def __init__(self):
        self._seen = set()

    async def is_duplicate(self, value):
        return value in self._seen

    async def add_hash(self, value):
        self._seen.add(value)


class FakeLogger:
    def __init__(self):
        self.records = []

    def debug(self, msg, *args):
        self.records.append(("debug", msg % args if args else msg))

    def info(self, msg, *args):
        self.records.append(("info", msg % args if args else msg))

    def error(self, msg, *args):
        self.records.append(("error", msg % args if args else msg))


@pytest.mark.asyncio
async def test_user_mode_routes_to_user_sender(monkeypatch):
    called = {"user": 0, "bot": 0}

    async def fake_user_send(client, target, text):
        called["user"] += 1

    async def fake_bot_send(token, target, text, logger):
        called["bot"] += 1

    monkeypatch.setattr("app.polling.send_user_message", fake_user_send)
    monkeypatch.setattr("app.polling.send_bot_message", fake_bot_send)

    task = TaskConfig(
        name="t1",
        enabled=True,
        interval_seconds=5,
        sources=["@src"],
        output=TaskOutputConfig(mode="user", target="@dst"),
        filters=FilterConfig(mode="or", keywords=["hit"], link_patterns=[]),
    )

    message = types.SimpleNamespace(
        message="hit",
        text="hit",
        media=None,
        entities=[],
        id=1,
    )

    state = FakeState()
    logger = FakeLogger()

    matched = await process_message(
        client=None,
        task=task,
        entity=types.SimpleNamespace(username="src", id=1),
        message=message,
        state=state,
        target=task.output.target,
        logger=logger,
    )

    assert matched is True
    assert called["user"] == 1
    assert called["bot"] == 0


@pytest.mark.asyncio
async def test_bot_mode_routes_to_bot_sender(monkeypatch):
    called = {"user": 0, "bot": 0}

    async def fake_user_send(client, target, text):
        called["user"] += 1

    async def fake_bot_send(token, target, text, logger):
        called["bot"] += 1

    monkeypatch.setattr("app.polling.send_user_message", fake_user_send)
    monkeypatch.setattr("app.polling.send_bot_message", fake_bot_send)

    task = TaskConfig(
        name="t1",
        enabled=True,
        interval_seconds=5,
        sources=["@src"],
        output=TaskOutputConfig(mode="bot", target="-100123", bot_token="123:ABC"),
        filters=FilterConfig(mode="or", keywords=["hit"], link_patterns=[]),
    )

    message = types.SimpleNamespace(
        message="hit",
        text="hit",
        media=None,
        entities=[],
        id=2,
    )

    state = FakeState()
    logger = FakeLogger()

    matched = await process_message(
        client=None,
        task=task,
        entity=types.SimpleNamespace(username=None, id=1),
        message=message,
        state=state,
        target=task.output.target,
        logger=logger,
    )

    assert matched is True
    assert called["bot"] == 1
    assert called["user"] == 0


@pytest.mark.asyncio
async def test_bot_mode_requires_token(monkeypatch):
    async def fake_user_send(client, target, text):
        raise AssertionError("should not be called")

    async def fake_bot_send(token, target, text, logger):
        raise AssertionError("should not be called")

    monkeypatch.setattr("app.polling.send_user_message", fake_user_send)
    monkeypatch.setattr("app.polling.send_bot_message", fake_bot_send)

    task = TaskConfig(
        name="t1",
        enabled=True,
        interval_seconds=5,
        sources=["@src"],
        output=TaskOutputConfig(mode="bot", target="-100123", bot_token=None),
        filters=FilterConfig(mode="or", keywords=["hit"], link_patterns=[]),
    )

    message = types.SimpleNamespace(
        message="hit",
        text="hit",
        media=None,
        entities=[],
        id=3,
    )

    state = FakeState()
    logger = FakeLogger()

    with pytest.raises(ValueError):
        await process_message(
            client=None,
            task=task,
            entity=types.SimpleNamespace(username=None, id=1),
            message=message,
            state=state,
            target=task.output.target,
            logger=logger,
        )
