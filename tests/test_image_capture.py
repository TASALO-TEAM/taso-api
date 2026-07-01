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
