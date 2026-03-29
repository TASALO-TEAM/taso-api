"""Tests for image capture service."""

import pytest
import os
import json
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.image_capture import capture_and_store_image, get_latest_image, get_image_by_date
from src.models.image_snapshot import ImageSnapshot


class TestImageCaptureService:
    """Tests for image capture service."""
    
    @pytest.mark.asyncio
    async def test_get_latest_image_empty(self, db_session: AsyncSession):
        """Test getting latest image when DB is empty."""
        latest = await get_latest_image(db_session, source="eltoque")
        assert latest is None
    
    @pytest.mark.asyncio
    async def test_get_latest_image_with_data(self, db_session: AsyncSession):
        """Test getting latest image when DB has data."""
        # Create a test image snapshot
        snapshot = ImageSnapshot(
            source="eltoque",
            image_path="/tmp/test_image.jpg",
            file_size=1024,
            extra_data=json.dumps({"width": 800, "height": 600})
        )
        db_session.add(snapshot)
        await db_session.commit()
        
        # Get latest
        latest = await get_latest_image(db_session, source="eltoque")
        
        assert latest is not None
        assert latest.source == "eltoque"
        assert latest.image_path == "/tmp/test_image.jpg"
        assert latest.file_size == 1024
    
    @pytest.mark.asyncio
    async def test_capture_and_store_image_mock(self, db_session: AsyncSession, tmp_path):
        """Test capture and store with mocked image data."""
        # Create a fake image file
        fake_image = tmp_path / "fake.jpg"
        fake_image.write_bytes(b"fake image data")
        
        # Mock the capture function to use our fake image
        from src.services import image_capture
        original_capture = image_capture.capture_eltoque_image
        
        async def mock_capture(output_path, timeout=30000):
            # Copy fake image to output path
            import shutil
            shutil.copy(fake_image, output_path)
            return {
                "success": True,
                "width": 800,
                "height": 600,
                "file_size": 1024
            }
        
        image_capture.capture_eltoque_image = mock_capture
        image_capture.IMAGE_STORAGE_PATH = str(tmp_path)
        
        try:
            result = await capture_and_store_image(db_session, source="eltoque")
            
            assert result["success"] is True
            assert result["image"] is not None
            assert result["image"].source == "eltoque"
            assert result["image"].file_size == 1024
        finally:
            # Restore original function
            image_capture.capture_eltoque_image = original_capture
            image_capture.IMAGE_STORAGE_PATH = "/home/ersus/tasalo/taso-api/static/images/eltoque"
