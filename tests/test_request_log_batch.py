"""Registro de peticiones en lotes: encola sin I/O y vuelca con un solo commit."""

import pytest

from src import database, main


class _FakeSession:
    def __init__(self):
        self.added, self.commits = [], 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def add_all(self, items):
        self.added.extend(items)

    async def commit(self):
        self.commits += 1


@pytest.fixture(autouse=True)
def _clean_buffer():
    main._log_buffer.clear()
    yield
    main._log_buffer.clear()


@pytest.mark.asyncio
async def test_flush_writes_batch_in_one_commit(monkeypatch):
    session = _FakeSession()
    monkeypatch.setattr(database, "async_session_factory", lambda: session)
    for i in range(5):
        main._enqueue_request("GET", f"/api/v1/x{i}", 200, 10, "bot")

    await main._flush_request_log()

    assert len(session.added) == 5
    assert session.commits == 1
    assert main._log_buffer == []


@pytest.mark.asyncio
async def test_flush_empty_buffer_does_not_touch_db(monkeypatch):
    def boom():
        raise AssertionError("no debe abrir sesion con buffer vacio")

    monkeypatch.setattr(database, "async_session_factory", boom)
    await main._flush_request_log()


def test_buffer_is_bounded():
    for _ in range(main._LOG_BUFFER_MAX + 50):
        main._enqueue_request("GET", "/a", 200, 1, "bot")
    assert len(main._log_buffer) == main._LOG_BUFFER_MAX


@pytest.mark.asyncio
async def test_flush_failure_drops_batch_without_raising(monkeypatch):
    def broken():
        raise RuntimeError("db caida")

    monkeypatch.setattr(database, "async_session_factory", broken)
    main._enqueue_request("GET", "/a", 200, 1, "bot")
    await main._flush_request_log()
    assert main._log_buffer == []
