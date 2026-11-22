"""Tests de segmentos de difusion (taso-bot#72, Fase 4).

/users/ids acepta un segmento: todos, activos (visto en 7 dias), alertas
(alerta de precio ACTIVE), tspl y year (suscripciones). Siempre sobre alcanzables.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.models.bot_stats import BotUser
from src.models.price_alert import PriceAlert
from src.models.tspl_subscription import TsplSubscription
from src.models.year_subscription import YearSubscription
from src.services import stats_service


def _ago(days: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


async def _seed(db_session):
    """1 activo reciente, 2 inactivo, 3 inalcanzable reciente con alerta, 4 con las tres cosas."""
    db_session.add_all([
        BotUser(user_id=1, last_seen=_ago(1)),
        BotUser(user_id=2, last_seen=_ago(30)),
        BotUser(user_id=3, last_seen=_ago(1), is_reachable=False),
        BotUser(user_id=4, last_seen=_ago(40)),
    ])
    db_session.add_all([
        PriceAlert(user_id=3, coin="BTC", target_price=1.0, condition="ABOVE", status="ACTIVE"),
        PriceAlert(user_id=4, coin="BTC", target_price=1.0, condition="ABOVE", status="ACTIVE"),
        PriceAlert(user_id=2, coin="ETH", target_price=1.0, condition="BELOW", status="TRIGGERED"),
        TsplSubscription(user_id=4, hour=12),
        TsplSubscription(user_id=4, hour=18),  # hasta 2 filas por usuario: no debe duplicar
        YearSubscription(user_id=4, hour=13),
        YearSubscription(user_id=1, hour=13),
    ])
    await db_session.commit()


class TestSegments:
    async def test_todos_es_el_comportamiento_de_siempre(self, db_session):
        await _seed(db_session)
        ids = await stats_service.get_all_user_ids(db_session)
        assert sorted(ids) == [1, 2, 4]  # sin el inalcanzable

    async def test_activos_son_los_vistos_en_7_dias(self, db_session):
        await _seed(db_session)
        ids = await stats_service.get_all_user_ids(db_session, segment="activos")
        assert sorted(ids) == [1]

    async def test_alertas_solo_cuenta_alertas_activas_de_alcanzables(self, db_session):
        await _seed(db_session)
        ids = await stats_service.get_all_user_ids(db_session, segment="alertas")
        # 3 tiene alerta pero esta inalcanzable; 2 solo tiene una ya disparada
        assert sorted(ids) == [4]

    async def test_tspl_no_duplica_usuarios_con_dos_suscripciones(self, db_session):
        await _seed(db_session)
        ids = await stats_service.get_all_user_ids(db_session, segment="tspl")
        assert ids == [4]

    async def test_year(self, db_session):
        await _seed(db_session)
        ids = await stats_service.get_all_user_ids(db_session, segment="year")
        assert sorted(ids) == [1, 4]

    async def test_incluir_inalcanzables_tambien_aplica_al_segmento(self, db_session):
        await _seed(db_session)
        ids = await stats_service.get_all_user_ids(
            db_session, only_reachable=False, segment="alertas"
        )
        assert sorted(ids) == [3, 4]

    async def test_segmento_desconocido_falla_en_vez_de_difundir_a_todos(self, db_session):
        with pytest.raises(ValueError):
            await stats_service.get_all_user_ids(db_session, segment="vip")

    async def test_el_conteo_coincide_con_una_consulta_directa(self, db_session):
        """Criterio de 'hecho' del issue: el conteo de la vista previa = consulta directa."""
        from sqlalchemy import func, select

        await _seed(db_session)
        directo = (
            await db_session.execute(
                select(func.count(func.distinct(YearSubscription.user_id)))
                .join(BotUser, BotUser.user_id == YearSubscription.user_id)
                .where(BotUser.is_reachable.is_(True))
            )
        ).scalar_one()
        ids = await stats_service.get_all_user_ids(db_session, segment="year")
        assert len(ids) == directo
