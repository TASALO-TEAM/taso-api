"""Colector de liquidaciones de futuros (taso-bot M3b).

Tres websockets publicos (Binance, Bybit, OKX) -> eventos en USD -> buffer en memoria ->
volcado en lote cada FLUSH_SECONDS a liquidation_buckets (ver services/liquidations.py).
Verificado desde el VPS (EE. UU.) el 2026-11-25:
- Binance: fstream.binance.com esta bloqueado por geografia; dstream.binance.com SI entrega
  el stream global !forceOrder@arr (simbolos USDT/USDC). Endpoint no documentado para esto: es
  fragil, y si se cae el colector sigue con Bybit y OKX.
- Bybit: REST bloqueado, websocket OK; topic allLiquidation.<SIMBOLO> (sin comodin).
- OKX: liquidation-orders SWAP (todos) por el puerto 443; sz en contratos (ctVal por REST).
"""

import asyncio
import json
import logging
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Callable

import httpx
from websockets.asyncio.client import connect as ws_connect

from src.services.liquidations import LiqEvent, purge_old, record_events

logger = logging.getLogger(__name__)

MAX_AGE_SECONDS = 120  # descarta datos viejos (p. ej. el snapshot inicial de OKX)
FLUSH_SECONDS = 15
DEDUPE_MINUTES = 10

BINANCE_URL = "wss://dstream.binance.com/ws/!forceOrder@arr"
BYBIT_URL = "wss://stream.bybit.com/v5/public/linear"
OKX_URL = "wss://ws.okx.com:443/ws/v5/public"
OKX_INSTRUMENTS_URL = "https://www.okx.com/api/v5/public/instruments?instType=SWAP"

# Bybit no tiene comodin y su REST esta bloqueado desde el VPS: lista fija de los perpetuos USDT mas liquidados.
BYBIT_SYMBOLS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "AVAX", "LINK", "SUI", "HYPE", "TON", "LTC", "BCH", "DOT",
    "TRX", "NEAR", "APT", "ARB", "OP", "INJ", "TIA", "SEI", "WLD", "PEPE", "WIF", "BONK", "FIL", "ATOM", "UNI",
    "AAVE", "ENA", "TAO", "ZEC", "FARTCOIN", "PENGU", "ONDO", "JUP", "TRUMP", "ASTER",
]

_QUOTES = ("USDT", "USDC", "BUSD", "PERP")


def next_delay(attempt: int) -> int:
    """Espera entre reconexiones: 1, 2, 4, ... con tope de 60 s."""
    return min(60, 2 ** max(0, attempt))


def _utc_from_ms(value) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


def _fresh(ts: datetime, now: datetime) -> bool:
    return (now - ts).total_seconds() <= MAX_AGE_SECONDS


def _base(symbol: str) -> str:
    for q in _QUOTES:
        if symbol.endswith(q) and len(symbol) > len(q):
            return symbol[: -len(q)]
    return symbol


def _load(raw: str):
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def parse_binance(raw: str, now: datetime) -> LiqEvent | None:
    """forceOrder: S=SELL cierra un long (long liquidado); S=BUY cierra un short."""
    msg = _load(raw)
    if not isinstance(msg, dict) or msg.get("e") != "forceOrder":
        return None
    try:
        o = msg["o"]
        sym = str(o["s"])
        if "_" in sym:  # COIN-M (BTCUSD_PERP): el tamano es en contratos, no se convierte
            return None
        ts = _utc_from_ms(o["T"])
        usd = float(o["z"]) * float(o["ap"])
        side = "long" if o["S"] == "SELL" else "short"
    except (KeyError, TypeError, ValueError):
        return None
    if not _fresh(ts, now) or usd <= 0:
        return None
    return LiqEvent(ts=ts, exchange="binance", symbol=_base(sym), side=side, notional_usd=usd)


def parse_bybit(raw: str, now: datetime) -> list[LiqEvent]:
    """allLiquidation: segun la documentacion de Bybit, S=Buy es un long liquidado."""
    msg = _load(raw)
    if not isinstance(msg, dict) or not str(msg.get("topic", "")).startswith("allLiquidation."):
        return []
    out = []
    for d in msg.get("data") or []:
        try:
            ts = _utc_from_ms(d["T"])
            usd = float(d["v"]) * float(d["p"])
            side = "long" if d["S"] == "Buy" else "short"
            sym = _base(str(d["s"]))
        except (KeyError, TypeError, ValueError):
            continue
        if _fresh(ts, now) and usd > 0:
            out.append(LiqEvent(ts=ts, exchange="bybit", symbol=sym, side=side, notional_usd=usd))
    return out


def parse_okx(raw: str, ct_val: dict[str, float], now: datetime) -> list[LiqEvent]:
    """liquidation-orders: sz en contratos x ctVal x precio de quiebra; posSide es el lado liquidado."""
    msg = _load(raw)
    if not isinstance(msg, dict) or (msg.get("arg") or {}).get("channel") != "liquidation-orders":
        return []
    out = []
    for item in msg.get("data") or []:
        inst = item.get("instId", "")
        val = ct_val.get(inst)
        if not val:
            continue
        for d in item.get("details") or []:
            try:
                ts = _utc_from_ms(d["ts"])
                usd = float(d["sz"]) * val * float(d["bkPx"])
                side = d["posSide"]
            except (KeyError, TypeError, ValueError):
                continue
            if side in ("long", "short") and _fresh(ts, now) and usd > 0:
                out.append(LiqEvent(ts=ts, exchange="okx", symbol=inst.split("-")[0], side=side, notional_usd=usd))
    return out


class LiqCollector:
    """Mantiene los tres websockets y vuelca el buffer a la BD. Un solo proceso: no duplicar."""

    def __init__(self, session_factory: Callable, connect=ws_connect):
        self._session_factory = session_factory
        self._connect = connect
        self._buffer: list[LiqEvent] = []
        self._seen: OrderedDict = OrderedDict()
        self._ct_val: dict[str, float] = {}
        self._tasks: list[asyncio.Task] = []

    def ingest(self, events: list[LiqEvent]) -> None:
        for e in events:
            key = (e.exchange, e.symbol, e.side, int(e.ts.timestamp() * 1000), round(e.notional_usd, 2))
            if key in self._seen:
                continue
            self._seen[key] = e.ts
            self._buffer.append(e)

    def _prune_seen(self, now: datetime) -> None:
        limit = now - timedelta(minutes=DEDUPE_MINUTES)
        while self._seen and next(iter(self._seen.values())) < limit:
            self._seen.popitem(last=False)

    async def flush(self) -> int:
        """Vuelca el buffer. Si la BD falla, el lote se conserva para el siguiente intento."""
        self._prune_seen(datetime.now(timezone.utc))
        if not self._buffer:
            return 0
        batch, self._buffer = self._buffer, []
        try:
            async with self._session_factory() as db:
                await record_events(db, batch)
        except Exception as exc:  # noqa: BLE001 - el colector no debe morir por la BD
            logger.warning("Liquidaciones: fallo al volcar %d eventos: %s", len(batch), exc)
            self._buffer = batch + self._buffer
            return 0
        return len(batch)

    async def _load_okx_contracts(self) -> None:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(OKX_INSTRUMENTS_URL)
            r.raise_for_status()
        self._ct_val = {
            i["instId"]: float(i["ctVal"])
            for i in r.json().get("data", [])
            if i.get("ctType") == "linear" and i.get("ctVal") and i["instId"].endswith(("-USDT-SWAP", "-USDC-SWAP"))
        }
        logger.info("Liquidaciones: %d contratos OKX cargados", len(self._ct_val))

    async def _stream(self, name: str, url: str, subs: list, handle: Callable[[str], None], before=None) -> None:
        attempt = 0
        while True:
            try:
                if before is not None:
                    await before()
                async with self._connect(url, open_timeout=15, ping_interval=20) as ws:
                    for s in subs:
                        await ws.send(json.dumps(s))
                    logger.info("Liquidaciones: %s conectado", name)
                    attempt = 0
                    async for raw in ws:
                        handle(raw if isinstance(raw, str) else raw.decode())
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("Liquidaciones: %s desconectado: %s", name, exc)
            await asyncio.sleep(next_delay(attempt))
            attempt += 1

    async def _flush_loop(self) -> None:
        purge_every, ticks = 3600 // FLUSH_SECONDS, 0
        while True:
            await asyncio.sleep(FLUSH_SECONDS)
            await self.flush()
            ticks += 1
            if ticks % purge_every == 0:
                try:
                    async with self._session_factory() as db:
                        await purge_old(db)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Liquidaciones: fallo en la purga: %s", exc)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _on_binance(self, raw: str) -> None:
        ev = parse_binance(raw, self._now())
        if ev:
            self.ingest([ev])

    def _on_bybit(self, raw: str) -> None:
        self.ingest(parse_bybit(raw, self._now()))

    def _on_okx(self, raw: str) -> None:
        self.ingest(parse_okx(raw, self._ct_val, self._now()))

    async def start(self) -> None:
        bybit_args = [f"allLiquidation.{s}USDT" for s in BYBIT_SYMBOLS]
        bybit_subs = [{"op": "subscribe", "args": bybit_args[i:i + 10]} for i in range(0, len(bybit_args), 10)]
        okx_subs = [{"op": "subscribe", "args": [{"channel": "liquidation-orders", "instType": "SWAP"}]}]
        self._tasks = [
            asyncio.create_task(self._stream("binance", BINANCE_URL, [], self._on_binance)),
            asyncio.create_task(self._stream("bybit", BYBIT_URL, bybit_subs, self._on_bybit)),
            asyncio.create_task(self._stream("okx", OKX_URL, okx_subs, self._on_okx, before=self._load_okx_contracts)),
            asyncio.create_task(self._flush_loop()),
        ]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.flush()
        self._tasks = []
