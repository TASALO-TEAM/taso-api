"""El scheduler de la API no debe duplicar el despachador de /y del bot.

El bot envia los avisos de /y a las :00 UTC (year_alert_scheduler.py). El job
por minuto que habia en la API solo construia el mensaje y lo escribia en el
log: 1440 consultas a BD al dia sin ningun efecto. Se retira; el saludo de
Año Nuevo (una vez al dia) se conserva.
"""

import pytest
from unittest.mock import MagicMock

from src.services.scheduler import create_scheduler, init_year_scheduler


@pytest.mark.asyncio
async def test_api_no_registra_cron_por_minuto_de_year():
    scheduler = create_scheduler(MagicMock())
    await init_year_scheduler(scheduler, MagicMock())

    ids = {job.id for job in scheduler.get_jobs()}

    assert "year_daily_alert" not in ids


@pytest.mark.asyncio
async def test_api_conserva_saludo_de_ano_nuevo_y_refresh():
    scheduler = create_scheduler(MagicMock())
    await init_year_scheduler(scheduler, MagicMock())

    ids = {job.id for job in scheduler.get_jobs()}

    assert "year_new_year_greeting" in ids
    assert "refresh_all" in ids
