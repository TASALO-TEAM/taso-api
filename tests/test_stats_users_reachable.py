"""Tests de alcanzabilidad de usuarios (taso-bot#72, Fase 2).

bot_users.is_reachable / unreachable_since marcan a quien bloqueo el bot.
/users/ids excluye por defecto a los inalcanzables (los usa /ms) y la purga
diaria borra a los que llevan mas de N dias inalcanzables.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from starlette.testclient import TestClient

from src.main import app
from src.models.bot_stats import BotCommandStat, BotUser
from src.services import stats_service


class TestSetUserReachability:
    async def test_blocked_user_is_marked_unreachable_with_date(self, db_session):
        await stats_service.mark_user_seen(db_session, 1)

        assert await stats_service.set_user_reachability(db_session, 1, False) is True

        user = await db_session.get(BotUser, 1)
        assert user.is_reachable is False
        assert user.unreachable_since is not None

    async def test_unblocked_user_is_restored_and_date_cleared(self, db_session):
        await stats_service.mark_user_seen(db_session, 2)
        await stats_service.set_user_reachability(db_session, 2, False)

        await stats_service.set_user_reachability(db_session, 2, True)

        user = await db_session.get(BotUser, 2)
        assert user.is_reachable is True
        assert user.unreachable_since is None

    async def test_repeated_block_keeps_the_first_date(self, db_session):
        await stats_service.mark_user_seen(db_session, 3)
        await stats_service.set_user_reachability(db_session, 3, False)
        first = (await db_session.get(BotUser, 3)).unreachable_since

        await stats_service.set_user_reachability(db_session, 3, False)

        assert (await db_session.get(BotUser, 3)).unreachable_since == first

    async def test_unknown_user_returns_false_and_creates_nothing(self, db_session):
        assert await stats_service.set_user_reachability(db_session, 999, False) is False
        assert await db_session.get(BotUser, 999) is None

    async def test_new_users_are_reachable_by_default(self, db_session):
        await stats_service.mark_user_seen(db_session, 4)
        assert (await db_session.get(BotUser, 4)).is_reachable is True

    async def test_user_who_writes_again_is_reachable_again(self, db_session):
        await stats_service.mark_user_seen(db_session, 5)
        await stats_service.set_user_reachability(db_session, 5, False)

        await stats_service.mark_user_seen(db_session, 5)

        user = await db_session.get(BotUser, 5)
        assert user.is_reachable is True
        assert user.unreachable_since is None


class TestUserIdsReachability:
    async def test_unreachable_users_are_excluded_by_default(self, db_session):
        for uid in (10, 11):
            await stats_service.mark_user_seen(db_session, uid)
        await stats_service.set_user_reachability(db_session, 11, False)

        assert await stats_service.get_all_user_ids(db_session) == [10]

    async def test_can_include_unreachable_users(self, db_session):
        for uid in (10, 11):
            await stats_service.mark_user_seen(db_session, uid)
        await stats_service.set_user_reachability(db_session, 11, False)

        ids = await stats_service.get_all_user_ids(db_session, only_reachable=False)
        assert sorted(ids) == [10, 11]


class TestPurgeUnreachable:
    async def _unreachable_since(self, db_session, uid, days_ago):
        await stats_service.mark_user_seen(db_session, uid)
        await stats_service.track_command(db_session, "/ta", uid)
        await stats_service.set_user_reachability(db_session, uid, False)
        user = await db_session.get(BotUser, uid)
        user.unreachable_since = datetime.now(timezone.utc) - timedelta(days=days_ago)
        await db_session.commit()

    async def test_deletes_only_users_unreachable_for_more_than_n_days(self, db_session):
        await self._unreachable_since(db_session, 20, days_ago=8)  # se borra
        await self._unreachable_since(db_session, 21, days_ago=3)  # reciente: se queda
        await stats_service.mark_user_seen(db_session, 22)  # alcanzable: se queda

        deleted = await stats_service.purge_unreachable_users(db_session, days=7)

        assert deleted == 1
        remaining = (await db_session.execute(select(BotUser.user_id))).scalars().all()
        assert sorted(remaining) == [21, 22]

    async def test_also_deletes_command_stats_of_purged_users_only(self, db_session):
        await self._unreachable_since(db_session, 30, days_ago=10)
        await self._unreachable_since(db_session, 31, days_ago=1)

        await stats_service.purge_unreachable_users(db_session, days=7)

        stat_users = (await db_session.execute(select(BotCommandStat.user_id))).scalars().all()
        assert stat_users == [31]

    async def test_returns_zero_when_nothing_to_purge(self, db_session):
        await stats_service.mark_user_seen(db_session, 40)
        assert await stats_service.purge_unreachable_users(db_session, days=7) == 0


class TestReachabilityEndpointAuth:
    @pytest.fixture
    def client(self):
        with TestClient(app) as client:
            yield client

    def test_without_auth_returns_401(self, client):
        response = client.post(
            "/api/v1/admin/stats/users/reachability",
            json={"user_id": 1, "reachable": False},
        )
        assert response.status_code == 401

    def test_ids_without_auth_returns_401(self, client):
        assert client.get("/api/v1/admin/stats/users/ids").status_code == 401
