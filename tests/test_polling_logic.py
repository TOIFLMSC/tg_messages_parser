import pytest

from app.polling import fetch_messages


class FakeClient:
    def __init__(self, messages):
        self._messages = messages

    async def iter_messages(self, entity, **kwargs):
        for msg in self._messages:
            yield msg


@pytest.mark.asyncio
async def test_fetch_messages_returns_oldest_first(monkeypatch):
    class DummyMessage:
        def __init__(self, msg_id):
            self.id = msg_id

    monkeypatch.setattr("app.polling.Message", DummyMessage)

    msgs = [DummyMessage(3), DummyMessage(2), DummyMessage(1)]
    client = FakeClient(msgs)
    result = await fetch_messages(client, entity=object(), min_id=None, limit=50)
    assert [m.id for m in result] == [1, 2, 3]
