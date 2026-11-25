"""Liquidaciones agregadas por minuto (taso-bot M3a).

Aqui solo vive el almacenamiento y la consulta. El colector websocket y los
parsers de cada exchange se anaden aparte, tras verificar muestras reales.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.liquidation import LiquidationBucket

WINDOWS = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "24h": 1440}  # minutos
RETENTION_HOURS = 25
SIDES = ("long", "short")


@dataclass(frozen=True)
class LiqEvent:
    ts: datetime
    exchange: str
    symbol: str
    side: str  # lado de la posicion liquidada: long | short
    notional_usd: float


@dataclass
class LiqRow:
    key: str
    long_usd: float = 0.0
    short_usd: float = 0.0

    @property
    def total_usd(self) -> float:
        return self.long_usd + self.short_usd


@dataclass
class LiqResult:
    data: list[LiqRow] = field(default_factory=list)
    since: datetime | None = None
    coverage_from: datetime | None = None


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _minute(dt: datetime) -> datetime:
    return _utc(dt).replace(second=0, microsecond=0)


async def record_events(db: AsyncSession, events: list[LiqEvent]) -> None:
    """Suma los eventos sobre sus cubos de 1 minuto (crea el cubo si no existe)."""
    if not events:
        return
    agg: dict[tuple, list] = {}
    for e in events:
        if e.side not in SIDES:
            raise ValueError(f"side invalido: {e.side!r}")
        k = (_minute(e.ts), e.exchange, e.symbol, e.side)
        acc = agg.setdefault(k, [0.0, 0])
        acc[0] += e.notional_usd
        acc[1] += 1

    for (bucket, exchange, symbol, side), (usd, n) in agg.items():
        row = (await db.execute(
            select(LiquidationBucket).where(
                LiquidationBucket.bucket == bucket,
                LiquidationBucket.exchange == exchange,
                LiquidationBucket.symbol == symbol,
                LiquidationBucket.side == side,
            )
        )).scalar_one_or_none()
        if row is None:
            db.add(LiquidationBucket(
                bucket=bucket, exchange=exchange, symbol=symbol, side=side, notional_usd=usd, n=n,
            ))
        else:
            row.notional_usd += usd
            row.n += n
    await db.commit()


async def get_liquidations(db: AsyncSession, window: str, by: str, now: datetime | None = None) -> LiqResult:
    """Totales long/short por simbolo o exchange dentro de la ventana, el mayor primero."""
    if window not in WINDOWS:
        raise ValueError(f"window invalida: {window!r}")
    if by not in ("symbol", "exchange"):
        raise ValueError(f"by invalido: {by!r}")
    since = _minute(now or datetime.now(timezone.utc)) - timedelta(minutes=WINDOWS[window])
    col = LiquidationBucket.symbol if by == "symbol" else LiquidationBucket.exchange

    rows = (await db.execute(
        select(col, LiquidationBucket.side, func.sum(LiquidationBucket.notional_usd))
        .where(LiquidationBucket.bucket >= since)
        .group_by(col, LiquidationBucket.side)
    )).all()

    por_clave: dict[str, LiqRow] = {}
    for key, side, usd in rows:
        item = por_clave.setdefault(key, LiqRow(key=key))
        if side == "long":
            item.long_usd += float(usd)
        else:
            item.short_usd += float(usd)

    first = (await db.execute(select(func.min(LiquidationBucket.bucket)))).scalar()
    return LiqResult(
        data=sorted(por_clave.values(), key=lambda r: r.total_usd, reverse=True),
        since=since,
        coverage_from=_utc(first) if first is not None else None,
    )


async def purge_old(db: AsyncSession, now: datetime | None = None) -> int:
    """Borra cubos con mas de RETENTION_HOURS. Devuelve cuantos."""
    limit = _minute(now or datetime.now(timezone.utc)) - timedelta(hours=RETENTION_HOURS)
    result = await db.execute(delete(LiquidationBucket).where(LiquidationBucket.bucket < limit))
    await db.commit()
    return result.rowcount or 0
