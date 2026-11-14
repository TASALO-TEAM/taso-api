"""Captura diaria de El Toque: hora fija 8:15 Cuba y reintentos si la imagen no es nueva."""

import pytest

from src.services import image_capture
from src.services import scheduler as sch


class _FakeSched:
    def __init__(self):
        self.jobs = []

    def add_job(self, func, **kw):
        self.jobs.append((func, kw))


class _FakeDB:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


async def _montar(monkeypatch, resultado):
    async def fake_capture(db, source="eltoque"):
        return resultado

    monkeypatch.setattr(image_capture, "capture_and_store_image", fake_capture)
    s = _FakeSched()
    await sch.init_image_capture_scheduler(s, lambda: _FakeDB())
    return s


@pytest.mark.asyncio
async def test_cron_a_las_815_cuba(monkeypatch):
    s = await _montar(monkeypatch, {"success": True, "stale": False})
    _, kw = s.jobs[0]
    assert (kw["hour"], kw["minute"], kw["timezone"]) == (8, 15, "America/Havana")


@pytest.mark.asyncio
async def test_imagen_vieja_programa_reintento_en_5_min(monkeypatch):
    s = await _montar(monkeypatch, {"success": True, "stale": True})
    await s.jobs[0][0]()
    _, kw = s.jobs[1]
    assert kw["trigger"] == "date" and kw["kwargs"] == {"intento": 1}
    assert kw["misfire_grace_time"] >= 60  # con el default (1 s) un loop ocupado descartaria el reintento


@pytest.mark.asyncio
async def test_imagen_nueva_no_reintenta(monkeypatch):
    s = await _montar(monkeypatch, {"success": True, "stale": False})
    await s.jobs[0][0]()
    assert len(s.jobs) == 1


@pytest.mark.asyncio
async def test_reintentos_tienen_tope(monkeypatch):
    s = await _montar(monkeypatch, {"success": False, "error": "x"})
    await s.jobs[0][0](intento=7)
    assert len(s.jobs) == 1
