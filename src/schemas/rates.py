"""Pydantic schemas for rates API responses."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class CurrencyRate(BaseModel):
    """Tasa individual con indicador de cambio."""

    rate: float = Field(..., description="Tasa de cambio actual")
    buy: float | None = Field(None, description="Tasa de compra (solo CADECA)")
    sell: float | None = Field(None, description="Tasa de venta (solo CADECA)")
    change: Literal["up", "down", "neutral"] = Field(..., description="Dirección del cambio")
    prev_rate: float | None = Field(None, description="Tasa anterior")


class SourceRatesResponse(BaseModel):
    """Respuesta para tasas de una fuente específica."""

    source: str = Field(..., description="Nombre de la fuente (eltoque, cadeca, bcc, binance)")
    rates: dict[str, CurrencyRate] = Field(..., description="Tasas por moneda")
    updated_at: datetime = Field(..., description="Cuándo se actualizaron los datos")


class LatestRatesData(BaseModel):
    """Datos combinados de todas las fuentes."""

    eltoque: dict[str, CurrencyRate] = Field(default_factory=dict, description="Tasas de ElToque")
    cadeca: dict[str, CurrencyRate] = Field(default_factory=dict, description="Tasas de CADECA")
    bcc: dict[str, CurrencyRate] = Field(default_factory=dict, description="Tasas de BCC")
    binance: dict[str, CurrencyRate] = Field(default_factory=dict, description="Tasas de Binance")


class LatestRatesResponse(BaseModel):
    """Respuesta combinada de todas las fuentes."""

    ok: bool = Field(True, description="Estado de la respuesta")
    data: LatestRatesData = Field(..., description="Tasas de todas las fuentes")
    updated_at: datetime = Field(..., description="Cuándo se actualizaron los datos")


class HistoryQueryParams(BaseModel):
    """Parámetros de consulta para histórico."""

    source: Literal["eltoque", "cadeca", "bcc", "binance"] = Field(
        default="eltoque",
        description="Fuente de datos"
    )
    currency: str = Field(
        default="USD",
        description="Moneda a consultar"
    )
    days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Días de histórico (1-365)"
    )


class HistorySnapshot(BaseModel):
    """Snapshot individual para histórico."""

    source: str = Field(..., description="Fuente de datos")
    currency: str = Field(..., description="Moneda")
    buy_rate: float | None = Field(None, description="Tasa de compra")
    sell_rate: float | None = Field(None, description="Tasa de venta")
    fetched_at: datetime = Field(..., description="Cuándo se obtuvo el dato")


class CubanomicHistorySnapshot(BaseModel):
    """Snapshot para histórico de Cubanomic con rates explícitos.
    
    Este schema extiende HistorySnapshot para incluir campos específicos
    que el frontend espera para los gráficos de Cubanomic.
    """
    
    source: str = Field("cubanomic", description="Fuente de datos")
    currency: str = Field("MULTI", description="Moneda (MULTI para múltiple)")
    buy_rate: float | None = Field(None, description="Tasa de compra (USD)")
    sell_rate: float | None = Field(None, description="Tasa de venta (EUR)")
    fetched_at: datetime | str = Field(..., description="Cuándo se obtuvo el dato")
    
    # Campos explícitos para el frontend de Cubanomic
    usd_rate: float | None = Field(None, description="Tasa del USD")
    eur_rate: float | None = Field(None, description="Tasa del EUR")
    mlc_rate: float | None = Field(None, description="Tasa del MLC")


class HistoryResponse(BaseModel):
    """Respuesta para consulta histórica."""

    ok: bool = Field(True, description="Estado de la respuesta")
    data: list[HistorySnapshot] = Field(..., description="Lista de snapshots históricos")
    count: int = Field(..., description="Cantidad de registros")


class CubanomicHistoryResponse(BaseModel):
    """Respuesta para histórico de Cubanomic con rates explícitos."""
    
    ok: bool = Field(True, description="Estado de la respuesta")
    data: list[CubanomicHistorySnapshot] = Field(..., description="Lista de snapshots con USD/EUR/MLC")
    count: int = Field(..., description="Cantidad de registros")
