"""Tests for ad_service.py."""

import pytest

from src.services import ad_service


@pytest.mark.asyncio
async def test_create_ad_defaults(db_session):
    """create_ad crea un anuncio activo, no patrocinado, peso 1 por defecto."""
    ad = await ad_service.create_ad(db_session, text="Visita nuestro canal")
    assert ad is not None
    assert ad.text == "Visita nuestro canal"
    assert ad.is_active is True
    assert ad.is_sponsored is False
    assert ad.weight == 1


@pytest.mark.asyncio
async def test_create_ad_sponsored_with_weight(db_session):
    """create_ad respeta is_sponsored y weight explícitos."""
    ad = await ad_service.create_ad(
        db_session, text="Promo externa", is_sponsored=True, weight=5, created_by=123
    )
    assert ad.is_sponsored is True
    assert ad.weight == 5
    assert ad.created_by == 123


@pytest.mark.asyncio
async def test_list_ads_active_only(db_session):
    """list_ads(active_only=True) excluye los inactivos."""
    a1 = await ad_service.create_ad(db_session, text="Activo")
    a2 = await ad_service.create_ad(db_session, text="Inactivo")
    await ad_service.update_ad(db_session, a2.id, is_active=False)

    all_ads = await ad_service.list_ads(db_session, active_only=False)
    active_ads = await ad_service.list_ads(db_session, active_only=True)

    assert len(all_ads) == 2
    assert len(active_ads) == 1
    assert active_ads[0].id == a1.id


@pytest.mark.asyncio
async def test_get_random_active_ad_returns_none_when_empty(db_session):
    """Sin anuncios activos, get_random_active_ad devuelve None."""
    result = await ad_service.get_random_active_ad(db_session)
    assert result is None


@pytest.mark.asyncio
async def test_get_random_active_ad_only_picks_active(db_session):
    """get_random_active_ad nunca elige un anuncio inactivo."""
    active = await ad_service.create_ad(db_session, text="Solo yo estoy activo")
    inactive = await ad_service.create_ad(db_session, text="Inactivo")
    await ad_service.update_ad(db_session, inactive.id, is_active=False)

    for _ in range(10):
        chosen = await ad_service.get_random_active_ad(db_session)
        assert chosen is not None
        assert chosen.id == active.id


@pytest.mark.asyncio
async def test_update_ad_partial_fields(db_session):
    """update_ad solo cambia los campos provistos, deja el resto intacto."""
    ad = await ad_service.create_ad(db_session, text="Original", weight=1)

    updated = await ad_service.update_ad(db_session, ad.id, is_sponsored=True)

    assert updated.text == "Original"
    assert updated.is_sponsored is True
    assert updated.weight == 1


@pytest.mark.asyncio
async def test_update_ad_not_found_returns_none(db_session):
    """update_ad sobre un id inexistente devuelve None sin lanzar excepción."""
    result = await ad_service.update_ad(db_session, 9999, text="x")
    assert result is None


@pytest.mark.asyncio
async def test_delete_ad_success_and_idempotent(db_session):
    """delete_ad borra el anuncio; una segunda llamada devuelve False."""
    ad = await ad_service.create_ad(db_session, text="Para borrar")

    first = await ad_service.delete_ad(db_session, ad.id)
    second = await ad_service.delete_ad(db_session, ad.id)

    assert first is True
    assert second is False


@pytest.mark.asyncio
async def test_count_active(db_session):
    """count_active refleja solo los anuncios activos."""
    a1 = await ad_service.create_ad(db_session, text="A")
    a2 = await ad_service.create_ad(db_session, text="B")
    await ad_service.update_ad(db_session, a2.id, is_active=False)

    count = await ad_service.count_active(db_session)
    assert count == 1
