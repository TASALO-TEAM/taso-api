"""Pydantic schemas for rates API responses."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class CurrencyRate(BaseModel):
    """Tasa individual con indicador de cambio."""

    rate: float = Field(..., description="Tasa de cambio actual")
    buy: float | None = Field(None, description="Tasa de compra (QvaPay)")
    sell: float | None = Field(None, description="Tasa de venta (QvaPay)")
    change: Literal["up", "down", "neutral"] = Field(..., description="Dirección del cambio")
    prev_rate: float | None = Field(None, description="Tasa anterior")


class QvaPayRate(CurrencyRate):
    """Tasa de un método de pago de QvaPay, con datos descriptivos para que el cliente no tenga que conocer cada moneda."""

    name: str | None = Field(None, description="Nombre legible del método según QvaPay (p. ej. 'CUP Cash')")
    kind: Literal["bank", "cash", "wallet"] | None = Field(
        None, description="Tipo de método: bank (banco), cash (efectivo) o wallet (billetera)"
    )
    count: int | None = Field(
        None, description="Operaciones recientes que respaldan el promedio (pocas = promedio poco fiable)"
    )


class ElToqueRate(CurrencyRate):
    """Tasa de ElToque con datos para que los clientes la agrupen sin conocer cada moneda."""

    name: str | None = Field(None, description="Nombre legible (None si la moneda no esta en el catalogo)")
    group: Literal["main", "crypto", "other"] = Field(
        "other", description="Grupo de pantalla: main (principales), crypto u other"
    )
    tier: Literal["market", "reference"] = Field(
        "market",
        description="market = tasa de mercado; reference = valor fijo sin ofertas reales (mostrar en 'Mostrar mas')",
    )
    offers: int | None = Field(
        None, description="Ofertas reales detras de la tasa (None si viene de la API oficial de ElToque)"
    )
    order: int = Field(999, description="Posicion dentro del grupo (ascendente)")


class SourceRatesResponse(BaseModel):
    """Respuesta para tasas de una fuente específica."""

    source: str = Field(..., description="Nombre de la fuente (eltoque, bcc, binance, qvapay)")
    rates: dict[str, CurrencyRate] = Field(..., description="Tasas por moneda")
    updated_at: datetime = Field(..., description="Cuándo se actualizaron los datos")


class QvaPayRatesResponse(SourceRatesResponse):
    """Respuesta de /tasas/qvapay: igual que SourceRatesResponse pero con name/kind/count por método."""

    rates: dict[str, QvaPayRate] = Field(..., description="Tasas por método de pago")


class ElToqueRatesResponse(SourceRatesResponse):
    """Respuesta de /tasas/eltoque: igual que SourceRatesResponse pero con name/group/tier/offers/order."""

    rates: dict[str, ElToqueRate] = Field(..., description="Tasas por moneda, ya ordenadas por grupo")


class LatestRatesData(BaseModel):
    """Datos combinados de todas las fuentes."""

    eltoque: dict[str, ElToqueRate] = Field(
        default_factory=dict, description="Tasas de ElToque, agrupadas (name/group/tier/offers/order)"
    )
    bcc: dict[str, CurrencyRate] = Field(default_factory=dict, description="Tasas de BCC")
    binance: dict[str, CurrencyRate] = Field(default_factory=dict, description="Tasas de Binance")
    qvapay: dict[str, QvaPayRate] = Field(
        default_factory=dict,
        description="Tasas P2P de QvaPay por método de pago (rate = promedio compra/venta, más buy y sell)",
    )


class LatestRatesResponse(BaseModel):
    """Respuesta combinada de todas las fuentes."""

    ok: bool = Field(True, description="Estado de la respuesta")
    data: LatestRatesData = Field(..., description="Tasas de todas las fuentes")
    updated_at: datetime = Field(..., description="Cuándo se actualizaron los datos")
    sources_updated_at: dict[str, datetime] = Field(
        default_factory=dict,
        description=(
            "Hora real (fetched_at) del último dato de cada fuente. A diferencia de updated_at "
            "(hora de la respuesta), esta no avanza si el scraper de una fuente lleva tiempo sin actualizar."
        ),
    )


class HistoryQueryParams(BaseModel):
    """Parámetros de consulta para histórico."""

    source: Literal["eltoque", "bcc", "binance", "qvapay"] = Field(
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


class HistoryResponse(BaseModel):
    """Respuesta para consulta histórica."""

    ok: bool = Field(True, description="Estado de la respuesta")
    data: list[HistorySnapshot] = Field(..., description="Lista de snapshots históricos")
    count: int = Field(..., description="Cantidad de registros")
