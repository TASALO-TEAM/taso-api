"""Pydantic schemas for rates API."""

from src.schemas.rates import (
    CurrencyRate,
    SourceRatesResponse,
    LatestRatesData,
    LatestRatesResponse,
    HistoryQueryParams,
    HistorySnapshot,
    HistoryResponse,
)

from src.schemas.admin import (
    SchedulerStatusResponse,
    AdminStatusResponse,
    RefreshResult,
    RefreshData,
    RefreshResponse,
)

__all__ = [
    "CurrencyRate",
    "SourceRatesResponse",
    "LatestRatesData",
    "LatestRatesResponse",
    "HistoryQueryParams",
    "HistorySnapshot",
    "HistoryResponse",
    "SchedulerStatusResponse",
    "AdminStatusResponse",
    "RefreshResult",
    "RefreshData",
    "RefreshResponse",
]
