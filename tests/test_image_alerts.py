"""Tests for image alert service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.image_alert_service import (
    get_user_alert,
    create_update_alert,
    delete_alert,
    get_all_enabled_alerts,
    disable_alert
)
from src.models.image_alert import UserImageAlert


class TestImageAlertService:
    """Tests for image alert service."""
    
    @pytest.mark.asyncio
    async def test_create_new_alert(self, db_session: AsyncSession):
        """Test creating a new alert."""
        alert = await create_update_alert(
            db_session,
            user_id=123456,
            alert_time="07:15",
            format_type="photo",
            enabled=True
        )
        
        assert alert.user_id == 123456
        assert alert.alert_time == "07:15"
        assert alert.format_type == "photo"
        assert alert.enabled is True
    
    @pytest.mark.asyncio
    async def test_update_existing_alert(self, db_session: AsyncSession):
        """Test updating an existing alert."""
        # Create first alert
        await create_update_alert(
            db_session,
            user_id=789012,
            alert_time="07:15",
            format_type="photo"
        )
        
        # Update it
        updated = await create_update_alert(
            db_session,
            user_id=789012,
            alert_time="08:30",
            format_type="document"
        )
        
        assert updated.alert_time == "08:30"
        assert updated.format_type == "document"
        assert updated.enabled is True  # Default
    
    @pytest.mark.asyncio
    async def test_get_user_alert_exists(self, db_session: AsyncSession):
        """Test getting user alert that exists."""
        await create_update_alert(
            db_session,
            user_id=111111,
            alert_time="07:15"
        )
        
        alert = await get_user_alert(db_session, user_id=111111)
        
        assert alert is not None
        assert alert.user_id == 111111
        assert alert.alert_time == "07:15"
    
    @pytest.mark.asyncio
    async def test_get_user_alert_not_exists(self, db_session: AsyncSession):
        """Test getting user alert that doesn't exist."""
        alert = await get_user_alert(db_session, user_id=999999)
        assert alert is None
    
    @pytest.mark.asyncio
    async def test_delete_alert(self, db_session: AsyncSession):
        """Test deleting an alert."""
        # Create alert
        await create_update_alert(
            db_session,
            user_id=222222,
            alert_time="07:15"
        )
        
        # Delete it
        deleted = await delete_alert(db_session, user_id=222222)
        assert deleted is True
        
        # Verify it's gone
        alert = await get_user_alert(db_session, user_id=222222)
        assert alert is None
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_alert(self, db_session: AsyncSession):
        """Test deleting an alert that doesn't exist."""
        deleted = await delete_alert(db_session, user_id=888888)
        assert deleted is False
    
    @pytest.mark.asyncio
    async def test_get_all_enabled_alerts(self, db_session: AsyncSession):
        """Test getting all enabled alerts."""
        # Create multiple alerts
        await create_update_alert(db_session, user_id=1, enabled=True)
        await create_update_alert(db_session, user_id=2, enabled=True)
        await create_update_alert(db_session, user_id=3, enabled=False)
        
        alerts = await get_all_enabled_alerts(db_session)
        
        assert len(alerts) == 2
        assert all(a.enabled for a in alerts)
        user_ids = [a.user_id for a in alerts]
        assert 1 in user_ids
        assert 2 in user_ids
        assert 3 not in user_ids
    
    @pytest.mark.asyncio
    async def test_disable_alert(self, db_session: AsyncSession):
        """Test disabling an alert."""
        # Create enabled alert
        await create_update_alert(
            db_session,
            user_id=333333,
            alert_time="07:15",
            enabled=True
        )
        
        # Disable it
        disabled = await disable_alert(db_session, user_id=333333)
        
        assert disabled is not None
        assert disabled.enabled is False
        
        # Verify it's disabled
        alert = await get_user_alert(db_session, user_id=333333)
        assert alert.enabled is False
    
    @pytest.mark.asyncio
    async def test_disable_nonexistent_alert(self, db_session: AsyncSession):
        """Test disabling an alert that doesn't exist."""
        disabled = await disable_alert(db_session, user_id=777777)
        assert disabled is None
