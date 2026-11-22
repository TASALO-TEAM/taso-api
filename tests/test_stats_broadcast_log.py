"""Tests del historial de difusiones (taso-bot#72, Fase 3).

broadcast_log guarda solo los contadores de cada difusion de /ms; nunca el texto.
"""

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from src.main import app
from src.models.bot_stats import BroadcastLog
from src.schemas.stats import BroadcastLogItem, BroadcastLogRequest
from src.services import stats_service


def _log(**over):
    base = dict(
        admin_id=1, kind="text", segment="todos",
        recipients=10, ok=8, blocked=1, errors=1, duration_s=2.5,
    )
    base.update(over)
    return base


class TestLogBroadcast:
    async def test_guarda_los_contadores(self, db_session):
        await stats_service.log_broadcast(db_session, **_log())

        rows = await stats_service.get_recent_broadcasts(db_session)

        assert len(rows) == 1
        row = rows[0]
        assert (row.admin_id, row.kind, row.segment) == (1, "text", "todos")
        assert (row.recipients, row.ok, row.blocked, row.errors) == (10, 8, 1, 1)
        assert row.duration_s == 2.5
        assert row.created_at is not None

    def test_el_modelo_no_guarda_el_texto_del_mensaje(self):
        columnas = set(BroadcastLog.__table__.columns.keys())
        assert not columnas & {"text", "caption", "message", "body", "content"}


class TestRecentBroadcasts:
    async def test_devuelve_las_mas_recientes_primero(self, db_session):
        for admin in (1, 2, 3):
            await stats_service.log_broadcast(db_session, **_log(admin_id=admin))

        rows = await stats_service.get_recent_broadcasts(db_session)

        assert [r.admin_id for r in rows] == [3, 2, 1]

    async def test_respeta_el_limite(self, db_session):
        for admin in (1, 2, 3, 4, 5):
            await stats_service.log_broadcast(db_session, **_log(admin_id=admin))

        rows = await stats_service.get_recent_broadcasts(db_session, limit=2)

        assert [r.admin_id for r in rows] == [5, 4]

    async def test_sin_difusiones_devuelve_lista_vacia(self, db_session):
        assert await stats_service.get_recent_broadcasts(db_session) == []

    async def test_el_esquema_de_salida_valida_contra_el_modelo(self, db_session):
        await stats_service.log_broadcast(db_session, **_log(kind="photo"))
        row = (await stats_service.get_recent_broadcasts(db_session))[0]

        item = BroadcastLogItem.model_validate(row)

        assert (item.kind, item.recipients, item.ok) == ("photo", 10, 8)


class TestBroadcastLogRequest:
    def test_acepta_un_registro_valido(self):
        BroadcastLogRequest(**_log())

    def test_el_segmento_por_defecto_es_todos(self):
        data = _log()
        data.pop("segment")
        assert BroadcastLogRequest(**data).segment == "todos"

    @pytest.mark.parametrize(
        "campo,valor",
        [
            ("recipients", -1), ("ok", -1), ("blocked", -1), ("errors", -1),
            ("duration_s", -0.1), ("kind", "video"),
        ],
    )
    def test_rechaza_valores_invalidos(self, campo, valor):
        with pytest.raises(ValidationError):
            BroadcastLogRequest(**_log(**{campo: valor}))


class TestBroadcastRouter:
    async def test_registrar_y_listar(self, db_session):
        from src.routers import stats as router

        resp = await router.log_broadcast(BroadcastLogRequest(**_log()), db=db_session, api_key="k")
        assert resp.ok is True

        listing = await router.list_broadcasts(limit=5, db=db_session, api_key="k")

        assert listing.ok is True
        assert [(i.admin_id, i.recipients, i.blocked) for i in listing.data] == [(1, 10, 1)]


class TestBroadcastEndpointsAuth:
    @pytest.fixture
    def client(self):
        with TestClient(app) as client:
            yield client

    def test_registrar_sin_auth_devuelve_401(self, client):
        response = client.post("/api/v1/admin/stats/broadcasts", json=_log())
        assert response.status_code == 401

    def test_listar_sin_auth_devuelve_401(self, client):
        assert client.get("/api/v1/admin/stats/broadcasts").status_code == 401
