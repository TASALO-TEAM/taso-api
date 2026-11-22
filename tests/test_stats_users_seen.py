"""Tests de POST /admin/stats/users/seen (taso-bot#72, Fase 1: registro automatico).

El servicio hace un upsert idempotente en bot_users. No cuenta como comando:
total_commands no sube y no se escribe nada en bot_command_stats.
"""

import pytest
from sqlalchemy import func, select
from starlette.testclient import TestClient

from src.main import app
from src.models.bot_stats import BotCommandStat, BotUser
from src.services import stats_service


async def _count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar()


class TestMarkUserSeen:
    async def test_creates_new_user_without_counting_a_command(self, db_session):
        await stats_service.mark_user_seen(db_session, 111, username="ana", first_name="Ana")

        user = await db_session.get(BotUser, 111)
        assert user.username == "ana"
        assert user.first_name == "Ana"
        assert user.total_commands == 0
        assert await _count(db_session, BotCommandStat) == 0

    async def test_is_idempotent_one_row_per_user(self, db_session):
        for _ in range(3):
            await stats_service.mark_user_seen(db_session, 222, username="beto")

        assert await _count(db_session, BotUser) == 1
        assert (await db_session.get(BotUser, 222)).total_commands == 0

    async def test_updates_last_seen_on_repeat(self, db_session):
        await stats_service.mark_user_seen(db_session, 333)
        first = (await db_session.get(BotUser, 333)).last_seen

        await stats_service.mark_user_seen(db_session, 333)
        await db_session.refresh(await db_session.get(BotUser, 333))

        assert (await db_session.get(BotUser, 333)).last_seen >= first

    async def test_none_does_not_erase_known_username_or_first_name(self, db_session):
        await stats_service.mark_user_seen(db_session, 444, username="carla", first_name="Carla")
        await stats_service.mark_user_seen(db_session, 444, username=None, first_name=None)

        user = await db_session.get(BotUser, 444)
        assert user.username == "carla"
        assert user.first_name == "Carla"

    async def test_new_values_replace_old_ones(self, db_session):
        await stats_service.mark_user_seen(db_session, 555, username="viejo", first_name="Dani")
        await stats_service.mark_user_seen(db_session, 555, username="nuevo", first_name="Daniel")

        user = await db_session.get(BotUser, 555)
        assert user.username == "nuevo"
        assert user.first_name == "Daniel"

    async def test_does_not_reset_command_counter_of_existing_user(self, db_session):
        await stats_service.track_command(db_session, "/ta", 666, username="eva")
        await stats_service.mark_user_seen(db_session, 666, username="eva", first_name="Eva")

        user = await db_session.get(BotUser, 666)
        assert user.total_commands == 1
        assert user.first_name == "Eva"


class TestSeenEndpointAuth:
    """Admin-only: sin X-API-Key valida no debe registrar a nadie."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as client:
            yield client

    def test_without_auth_returns_401(self, client):
        response = client.post("/api/v1/admin/stats/users/seen", json={"user_id": 1})
        assert response.status_code == 401

    def test_with_invalid_auth_returns_401(self, client):
        response = client.post(
            "/api/v1/admin/stats/users/seen",
            json={"user_id": 1},
            headers={"X-API-Key": "invalid_key"},
        )
        assert response.status_code == 401
