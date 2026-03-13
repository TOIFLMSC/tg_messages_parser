import pytest

from app.sender import send_bot_message


class FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self._status_code = status_code
        self._json = json_data or {"ok": True}

    def raise_for_status(self):
        if self._status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._json


class FakeAsyncClient:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json):
        return self._response


class FakeLogger:
    def __init__(self):
        self.messages = []

    def error(self, msg, *args):
        self.messages.append(msg % args if args else msg)


@pytest.mark.asyncio
async def test_bot_send_success(monkeypatch):
    response = FakeResponse(status_code=200, json_data={"ok": True})
    monkeypatch.setattr("app.sender.httpx.AsyncClient", lambda timeout: FakeAsyncClient(response))
    logger = FakeLogger()
    await send_bot_message("123:ABCDEF", "-100123", "hello", logger)
    assert logger.messages == []


@pytest.mark.asyncio
async def test_bot_send_failure_masks_token(monkeypatch):
    response = FakeResponse(status_code=200, json_data={"ok": False, "description": "Bad Request"})
    monkeypatch.setattr("app.sender.httpx.AsyncClient", lambda timeout: FakeAsyncClient(response))
    logger = FakeLogger()
    token = "123456:ABCDEFSECRET"
    with pytest.raises(RuntimeError):
        await send_bot_message(token, "-100123", "hello", logger)
    assert logger.messages
    logged = logger.messages[0]
    assert token not in logged
    assert "1234...CRET" in logged
