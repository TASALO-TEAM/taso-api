"""Tests de /api/v1/tspl/digest/latest (digest diario: taso-bot lo empuja, taso-gcg lo lee)."""

import asyncio

import pytest
from starlette.testclient import TestClient

from src.main import app
from src.services import tspl_service

ADMIN_API_KEY = "your_secret_admin_key_here"
URL = "/api/v1/tspl/digest/latest"


@pytest.fixture
def client(tmp_path):
    """TestClient con su propia base SQLite (archivo temporal) inyectada en get_db.

    Un archivo y no ':memory:' porque cada conexion a ':memory:' es otra base. Las tablas se
    crean con el driver sincrono para no mezclar bucles de eventos con el del TestClient.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from src.database import Base, get_db

    ruta = tmp_path / "digest.db"
    sync_engine = create_engine(f"sqlite:///{ruta}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()

    engine = create_async_engine(f"sqlite+aiosqlite:///{ruta}")
    sesion = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_db():
        async with sesion() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())


@pytest.fixture
def headers():
    return {"X-API-Key": ADMIN_API_KEY}


def _body(**extra):
    return {"telegram_text": "Resumen TSPL de hoy", "generated_at": "2026-11-27T11:00:05+00:00", **extra}


class TestAuth:
    def test_get_sin_clave_da_401(self, client):
        assert client.get(URL).status_code == 401

    def test_put_sin_clave_da_401(self, client):
        assert client.put(URL, json=_body()).status_code == 401


class TestRoundTrip:
    def test_get_sin_digest_guardado_da_404(self, client, headers):
        assert client.get(URL, headers=headers).status_code == 404

    def test_guarda_y_devuelve(self, client, headers):
        r = client.put(URL, json=_body(blog_markdown="# Blog"), headers=headers)
        assert r.status_code == 200
        d = client.get(URL, headers=headers).json()
        assert d["ok"] is True
        assert d["telegram_text"] == "Resumen TSPL de hoy"
        assert d["blog_markdown"] == "# Blog"
        assert d["generated_at"].startswith("2026-11-27T11:00:05")
        assert d["updated_at"]

    def test_el_blog_es_opcional(self, client, headers):
        client.put(URL, json=_body(), headers=headers)
        assert client.get(URL, headers=headers).json()["blog_markdown"] is None

    def test_un_segundo_put_reemplaza_al_primero(self, client, headers):
        client.put(URL, json=_body(telegram_text="ayer"), headers=headers)
        client.put(URL, json=_body(telegram_text="hoy", blog_markdown="nuevo"), headers=headers)
        d = client.get(URL, headers=headers).json()
        assert d["telegram_text"] == "hoy" and d["blog_markdown"] == "nuevo"

    def test_tildes_y_emojis_sobreviven(self, client, headers):
        texto = "📊 Mercado: sube el dólar, ñandú"
        client.put(URL, json=_body(telegram_text=texto), headers=headers)
        assert client.get(URL, headers=headers).json()["telegram_text"] == texto


class TestValidacion:
    @pytest.mark.parametrize("texto", ["", "x" * 4097])
    def test_texto_fuera_de_limites(self, client, headers, texto):
        assert client.put(URL, json=_body(telegram_text=texto), headers=headers).status_code == 422

    def test_falta_generated_at(self, client, headers):
        assert client.put(URL, json={"telegram_text": "x"}, headers=headers).status_code == 422

    def test_generated_at_invalido(self, client, headers):
        assert client.put(URL, json=_body(generated_at="ayer"), headers=headers).status_code == 422


async def test_sin_digest_el_servicio_devuelve_none(db_session):
    assert await tspl_service.get_digest(db_session) is None


async def test_save_digest_deja_una_sola_fila(db_session):
    from datetime import datetime, timezone

    from sqlalchemy import func, select

    from src.models.tspl_digest import TsplDigest

    ahora = datetime(2026, 11, 27, 11, 0, tzinfo=timezone.utc)
    await tspl_service.save_digest(db_session, "uno", None, ahora)
    await tspl_service.save_digest(db_session, "dos", "md", ahora)
    total = (await db_session.execute(select(func.count()).select_from(TsplDigest))).scalar_one()
    assert total == 1
    assert (await tspl_service.get_digest(db_session)).telegram_text == "dos"
