"""Pydantic schemas for image endpoints."""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class ImageSnapshotSchema(BaseModel):
    """Schema for ImageSnapshot."""
    
    id: int
    source: str
    image_path: str
    thumbnail_path: Optional[str] = None
    file_size: Optional[int] = None
    captured_at: datetime
    extra_data: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class UserImageAlertSchema(BaseModel):
    """Schema for UserImageAlert."""
    
    user_id: int
    alert_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    format_type: str = Field(..., pattern=r"^(photo|document)$")
    enabled: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    @field_validator("alert_time")
    @classmethod
    def validate_time(cls, v: str) -> str:
        """Validate time format HH:MM."""
        try:
            hour, minute = map(int, v.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("Invalid time")
        except (ValueError, AttributeError):
            raise ValueError("Time must be in HH:MM format (24h)")
        return v


class AlertCreateSchema(BaseModel):
    """Schema for creating/updating alert."""
    
    user_id: int
    alert_time: str = Field(default="07:15", pattern=r"^\d{2}:\d{2}$")
    format_type: str = Field(default="photo", pattern=r"^(photo|document)$")
    enabled: bool = True
    
    @field_validator("alert_time")
    @classmethod
    def validate_time(cls, v: str) -> str:
        """Validate time format HH:MM."""
        try:
            hour, minute = map(int, v.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("Invalid time")
        except (ValueError, AttributeError):
            raise ValueError("Time must be in HH:MM format (24h)")
        return v


class APIResponse(BaseModel):
    """Generic API response wrapper."""
    
    ok: bool
    data: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    count: Optional[int] = None
