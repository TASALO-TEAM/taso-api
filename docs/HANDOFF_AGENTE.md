
# HANDOFF — taso-api / taso-bot (código muerto + recursos del VPS)

Actualizado: 2026-11-11. Plan completo: `tasalo/docs/plans/2026-11-10-codigo-muerto-y-resiliencia-api.md`.

## Decisiones del dueño (Ersus)
- Cubanomic: se quitó scraper de tasas, rutas y job. **NO tocar la captura de imagen** (`image_capture.py`, `/images/eltoque*`, `/toqueimg`): usa `iframe.cubanomic.com` y sigue viva (`scrapers/cubanomic.py` se conserva por eso).
- Prueba de carga al VPS: autorizada, de madrugada, con límite de tasa.
- Rate limit por IP: no.
- Hora de Cuba: mantiene hora de verano (UTC-4) todo el año. Captura de imagen a las **8:30 Cuba** (`timezone="America/Havana"`). El VPS ya corre en hora de Cuba (`date` = CDT).

## Hecho (todo en `main` y desplegado salvo lo marcado)
- API: N+1 de `/latest` y `/eltoque` fuera, caché en memoria (TTL 45 s), ETag + Cache-Control, captura 8:30 Cuba (PR #5).
- API: `logger` definido en `binance.py`/`eltoque.py` (PR #6), `print()` → `logger` (PR #7), pool de conexiones + registro de peticiones por lotes con filtro de escáneres (PR #8), código muerto + Cubanomic de tasas (PR #9, commit 1334fb3). VPS reiniciado con todo esto.
- BD: `VACUUM (ANALYZE) rate_snapshots` hecho (193 mil filas muertas → 0). La poda de `api_request_log` ya existía (30 días en `refresh_all`).
- Bot: imports perezosos (PR #5) y código muerto (PR #6, 85af45f; cadena de imágenes heredada, `file_manager.py`, `check_feature_access`). En el VPS el código ya está en disco.
- VPS: unidades huérfanas `bbchat`, `bia`, `main`, `rss` eliminadas (copias en `/home/ersus/backup-units-bbalert/`).
- Medición (VPS, puerto 8040): `/latest` 1.45 s → 0.55 s frío / 3 ms con caché; `/eltoque` 0.345 s → 0.37 s / 2 ms; `history/daily` 180 días 6.7 s en frío (cuello: ~38 mil filas por red + Python, no la consulta).

## Pendiente (en orden)
1. `taso-bot`: falta `sudo systemctl restart taso-bot` en el VPS (corre código anterior). Luego confirmar que arranca sin el aviso `Template base not found`.
2. Verificar en `logs/taso-api.log` que el job "Captura diaria imagen ElToque (8:30 Cuba)" se ejecuta (registrado al arrancar; primera ejecución real: 8:30 Cuba del 2026-11-11).
3. Prueba de carga de madrugada (hora Cuba) con límite de tasa, midiendo RAM y latencia.
4. Opcional: `history/daily` resuelto en SQL ("lectura más cercana a las 7:00 por día") para pasar de 6.7 s a milisegundos; rama aparte con test de equivalencia.
5. Opcional: `eltoque.py` traga en silencio 401/timeout/red; valorar `logger.warning`.
6. Descartado a propósito (ponytail): `httpx.AsyncClient` compartido en `ai_logic.py` (las llamadas a Groq son poco frecuentes; el ahorro es un handshake TLS).
7. README de taso-bot aún menciona `image_generator.py` (3 líneas); tabla `cubanomic_rates` queda huérfana en la BD (sin migración).

## Ojo
- Alertas de imagen del bot configuradas antes de las 8:30 Cuba reciben la imagen del día anterior (el bot reintenta 3 veces y sigue con la última). Pendiente decidir si se avisa o se valida hora mínima.
- Tests locales: el `.env` apunta a servicios reales y `TestClient(app)` se cuelga; usar `uv run --frozen --with pytest --with pytest-asyncio --with pytest-timeout python -m pytest --timeout=40 <archivo>`. Fallos preexistentes en `main`: `test_rates_service` ×3, `test_bcc` ×2, `test_redis_settings_default_values` (`.env` local). En el bot, 13 fallos preexistentes y `test_p_handler.py` no se recolecta (`p_more_callback` no existe).
- Windows + PowerShell: para ssh enviar scripts por stdin quitando `\r`; las comillas dobles anidadas se rompen.
- `ssh pan` entra sin clave; `sudo` pide contraseña (pedírsela al dueño, no guardarla).
- Un hook de pre-commit sube la versión en cada commit (`pyproject.toml`).
