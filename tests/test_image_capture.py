"""Tests for image capture service."""

import pytest
import os
import json
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.image_capture import capture_and_store_image, get_latest_image
from src.models.image_snapshot import ImageSnapshot


class TestImageCaptureService:
    """Tests for image capture service (modelo de descarga bajo demanda)."""

    @pytest.mark.asyncio
    async def test_get_latest_image_empty(self, db_session: AsyncSession):
        """Test getting latest image when DB is empty."""
        latest = await get_latest_image(db_session, source="eltoque")
        assert latest is None

    @pytest.mark.asyncio
    async def test_get_latest_image_with_data(self, db_session: AsyncSession):
        """Test getting latest image when DB has data."""
        snapshot = ImageSnapshot(
            source="eltoque",
            image_path="/tmp/test_image.png",
            file_size=1024,
            extra_data=json.dumps({"url": "https://iframe.cubanomic.com/"})
        )
        db_session.add(snapshot)
        await db_session.commit()

        latest = await get_latest_image(db_session, source="eltoque")

        assert latest is not None
        assert latest.source == "eltoque"
        assert latest.image_path == "/tmp/test_image.png"
        assert latest.file_size == 1024

    @pytest.mark.asyncio
    async def test_capture_and_store_image_success(self, db_session: AsyncSession, tmp_path):
        """Descarga exitosa: sobrescribe el archivo canónico y hace upsert en DB."""
        fake_image = tmp_path / "fake.png"
        fake_image.write_bytes(b"fake image data")

        from src.services import image_capture
        original_download = image_capture.download_eltoque_post_image

        async def mock_download(output_path, timeout=30000):
            import shutil
            shutil.copy(fake_image, output_path)
            return {"success": True, "file_size": 1024}

        image_capture.download_eltoque_post_image = mock_download
        image_capture.IMAGE_STORAGE_PATH = str(tmp_path)

        try:
            result = await capture_and_store_image(db_session, source="eltoque")

            assert result["success"] is True
            assert result["stale"] is False
            assert result["image"] is not None
            assert result["image"].source == "eltoque"
            assert result["image"].file_size == 1024

            # Segunda descarga exitosa debe hacer UPSERT (una sola fila), no insertar otra
            second = await capture_and_store_image(db_session, source="eltoque")
            assert second["image"].id == result["image"].id
        finally:
            image_capture.download_eltoque_post_image = original_download
            image_capture.IMAGE_STORAGE_PATH = "/home/ersus/tasalo/taso-api/static/images/eltoque"

    @pytest.mark.asyncio
    async def test_capture_and_store_image_fallback_to_stale(self, db_session: AsyncSession, tmp_path):
        """Si la descarga falla pero hay imagen local previa, se sirve marcada 'stale'."""
        from src.services import image_capture

        canonical_path = tmp_path / image_capture.CANONICAL_FILENAME
        canonical_path.write_bytes(b"previous image data")

        existing = ImageSnapshot(
            source="eltoque",
            image_path=str(canonical_path),
            file_size=999,
            extra_data=json.dumps({"url": "https://iframe.cubanomic.com/"})
        )
        db_session.add(existing)
        await db_session.commit()

        original_download = image_capture.download_eltoque_post_image

        async def mock_failing_download(output_path, timeout=30000):
            return {"success": False, "error": "Botón no visible"}

        image_capture.download_eltoque_post_image = mock_failing_download
        image_capture.IMAGE_STORAGE_PATH = str(tmp_path)

        try:
            result = await capture_and_store_image(db_session, source="eltoque")

            assert result["success"] is True
            assert result["stale"] is True
            assert result["image"].image_path == str(canonical_path)
        finally:
            image_capture.download_eltoque_post_image = original_download
            image_capture.IMAGE_STORAGE_PATH = "/home/ersus/tasalo/taso-api/static/images/eltoque"

    @pytest.mark.asyncio
    async def test_capture_and_store_image_total_failure(self, db_session: AsyncSession, tmp_path):
        """Si falla la descarga y no hay imagen local previa, devuelve error real."""
        from src.services import image_capture

        original_download = image_capture.download_eltoque_post_image

        async def mock_failing_download(output_path, timeout=30000):
            return {"success": False, "error": "Timeout de red"}

        image_capture.download_eltoque_post_image = mock_failing_download
        image_capture.IMAGE_STORAGE_PATH = str(tmp_path)

        try:
            result = await capture_and_store_image(db_session, source="eltoque")

            assert result["success"] is False
            assert "error" in result
        finally:
            image_capture.download_eltoque_post_image = original_download
            image_capture.IMAGE_STORAGE_PATH = "/home/ersus/tasalo/taso-api/static/images/eltoque"


class TestImagenAunNoPublicada:
    """El Toque corta a las 8:00 (Cuba): si el archivo es identico al de un dia anterior, no es de hoy."""

    @staticmethod
    async def _preparar(db_session, tmp_path, captured_at, contenido_actual):
        from src.services import image_capture

        canonical = tmp_path / image_capture.CANONICAL_FILENAME
        canonical.write_bytes(b"imagen de ayer")
        snap = ImageSnapshot(
            source="eltoque",
            image_path=str(canonical),
            file_size=14,
            captured_at=captured_at,
            extra_data=json.dumps({}),
        )
        db_session.add(snap)
        await db_session.commit()

        async def mock_download(output_path, timeout=30000):
            with open(output_path, "wb") as f:
                f.write(contenido_actual)
            return {"success": True, "file_size": len(contenido_actual)}

        return image_capture, snap, mock_download

    @pytest.mark.asyncio
    async def test_imagen_identica_a_ayer_es_stale_y_no_toca_captured_at(self, db_session, tmp_path, monkeypatch):
        from datetime import datetime, timedelta, timezone

        ayer = datetime.now(timezone.utc) - timedelta(days=1)
        image_capture, snap, mock_download = await self._preparar(db_session, tmp_path, ayer, b"imagen de ayer")
        monkeypatch.setattr(image_capture, "download_eltoque_post_image", mock_download)
        monkeypatch.setattr(image_capture, "IMAGE_STORAGE_PATH", str(tmp_path))

        result = await capture_and_store_image(db_session, source="eltoque")

        assert result["success"] is True
        assert result["stale"] is True
        await db_session.refresh(snap)
        assert abs((snap.captured_at.replace(tzinfo=timezone.utc) - ayer).total_seconds()) < 1

    @pytest.mark.asyncio
    async def test_imagen_distinta_se_guarda_como_de_hoy(self, db_session, tmp_path, monkeypatch):
        from datetime import datetime, timedelta, timezone

        ayer = datetime.now(timezone.utc) - timedelta(days=1)
        image_capture, snap, mock_download = await self._preparar(db_session, tmp_path, ayer, b"imagen nueva")
        monkeypatch.setattr(image_capture, "download_eltoque_post_image", mock_download)
        monkeypatch.setattr(image_capture, "IMAGE_STORAGE_PATH", str(tmp_path))

        result = await capture_and_store_image(db_session, source="eltoque")

        assert result["stale"] is False
        await db_session.refresh(snap)
        assert (datetime.now(timezone.utc) - snap.captured_at.replace(tzinfo=timezone.utc)).total_seconds() < 60

    @pytest.mark.asyncio
    async def test_misma_imagen_capturada_hoy_no_es_stale(self, db_session, tmp_path, monkeypatch):
        from datetime import datetime, timezone

        image_capture, snap, mock_download = await self._preparar(
            db_session, tmp_path, datetime.now(timezone.utc), b"imagen de ayer"
        )
        monkeypatch.setattr(image_capture, "download_eltoque_post_image", mock_download)
        monkeypatch.setattr(image_capture, "IMAGE_STORAGE_PATH", str(tmp_path))

        result = await capture_and_store_image(db_session, source="eltoque")

        assert result["stale"] is False
