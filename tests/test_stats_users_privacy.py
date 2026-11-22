"""Tests de privacidad y silencio de usuarios (taso-bot#72, Fase 5).

erase_user_data: /privacidad borra los datos del usuario y anonimiza sus tickets.
set_user_muted: /silencio lo excluye de las difusiones masivas (/users/ids).
"""

import pytest
from sqlalchemy import select
from starlette.testclient import TestClient

from src.main import app
from src.models.bot_stats import BotCommandStat, BotUser
from src.models.image_alert import UserImageAlert
from src.models.price_alert import PriceAlert
from src.models.ticket import Ticket
from src.models.tspl_subscription import TsplSubscription
from src.models.year_subscription import YearSubscription
from src.services import stats_service


async def _seed(db_session, uid):
    """Una fila por cada tabla con datos del usuario `uid`."""
    await stats_service.mark_user_seen(db_session, uid, username=f"u{uid}", first_name="N")
    db_session.add_all([
        BotCommandStat(user_id=uid, username=f"u{uid}", command="/t"),
        UserImageAlert(user_id=uid),
        PriceAlert(user_id=uid, coin="BTC", target_price=1.0, condition="ABOVE", status="ACTIVE"),
        TsplSubscription(user_id=uid, hour=12),
        YearSubscription(user_id=uid, hour=12),
        Ticket(user_id=uid, username=f"u{uid}", kind="bug", message="secreto", status="open"),
    ])
    await db_session.commit()


async def _count(db_session, model, uid):
    rows = await db_session.execute(select(model).where(model.user_id == uid))
    return len(rows.scalars().all())


class TestEraseUserData:
    async def test_deletes_user_rows_from_every_table(self, db_session):
        await _seed(db_session, 10)

        await stats_service.erase_user_data(db_session, 10)

        assert await db_session.get(BotUser, 10) is None
        for model in (BotCommandStat, UserImageAlert, PriceAlert, TsplSubscription, YearSubscription):
            assert await _count(db_session, model, 10) == 0

    async def test_anonymizes_tickets_including_open_ones(self, db_session):
        await _seed(db_session, 11)

        result = await stats_service.erase_user_data(db_session, 11)

        assert result["tickets_anonymized"] == 1
        assert await _count(db_session, Ticket, 11) == 0
        ticket = (await db_session.execute(select(Ticket).where(Ticket.user_id == 0))).scalars().one()
        assert ticket.username is None
        assert "secreto" not in ticket.message
        assert ticket.status == "open"
        assert ticket.kind == "bug"

    async def test_does_not_touch_other_users(self, db_session):
        await _seed(db_session, 12)
        await _seed(db_session, 13)

        await stats_service.erase_user_data(db_session, 12)

        assert await db_session.get(BotUser, 13) is not None
        for model in (BotCommandStat, UserImageAlert, PriceAlert, TsplSubscription, YearSubscription, Ticket):
            assert await _count(db_session, model, 13) == 1

    async def test_unknown_user_returns_zeros_without_error(self, db_session):
        result = await stats_service.erase_user_data(db_session, 999)

        assert result == {"deleted_rows": 0, "tickets_anonymized": 0}

    async def test_counts_deleted_rows(self, db_session):
        await _seed(db_session, 14)

        result = await stats_service.erase_user_data(db_session, 14)

        assert result["deleted_rows"] == 6  # bot_users + 5 tablas (los tickets van aparte)


class TestSetUserMuted:
    async def test_mute_and_unmute(self, db_session):
        await stats_service.mark_user_seen(db_session, 20)

        assert await stats_service.set_user_muted(db_session, 20, True) is True
        assert (await db_session.get(BotUser, 20)).is_muted is True

        await stats_service.set_user_muted(db_session, 20, False)
        assert (await db_session.get(BotUser, 20)).is_muted is False

    async def test_unknown_user_returns_false_and_is_not_created(self, db_session):
        assert await stats_service.set_user_muted(db_session, 21, True) is False
        assert await db_session.get(BotUser, 21) is None

    async def test_new_users_are_not_muted_by_default(self, db_session):
        await stats_service.mark_user_seen(db_session, 22)

        assert (await db_session.get(BotUser, 22)).is_muted is False

    async def test_seen_does_not_unmute(self, db_session):
        await stats_service.mark_user_seen(db_session, 23)
        await stats_service.set_user_muted(db_session, 23, True)

        await stats_service.mark_user_seen(db_session, 23)

        assert (await db_session.get(BotUser, 23)).is_muted is True


class TestMutedExcludedFromBroadcast:
    async def test_muted_user_not_in_ids(self, db_session):
        await stats_service.mark_user_seen(db_session, 30)
        await stats_service.mark_user_seen(db_session, 31)
        await stats_service.set_user_muted(db_session, 31, True)

        ids = await stats_service.get_all_user_ids(db_session)

        assert ids == [30]

    async def test_muted_user_not_in_any_segment(self, db_session):
        await stats_service.mark_user_seen(db_session, 32)
        await stats_service.set_user_muted(db_session, 32, True)

        assert await stats_service.get_all_user_ids(db_session, segment="activos") == []

    async def test_skip_muted_false_includes_them(self, db_session):
        await stats_service.mark_user_seen(db_session, 33)
        await stats_service.set_user_muted(db_session, 33, True)

        assert await stats_service.get_all_user_ids(db_session, skip_muted=False) == [33]


class TestPrivacyEndpointsAuth:
    @pytest.fixture
    def client(self):
        with TestClient(app) as client:
            yield client

    def test_privacy_without_auth_returns_401(self, client):
        response = client.post("/api/v1/admin/stats/users/privacy", json={"user_id": 1})
        assert response.status_code == 401

    def test_mute_without_auth_returns_401(self, client):
        response = client.post("/api/v1/admin/stats/users/mute", json={"user_id": 1, "muted": True})
        assert response.status_code == 401
