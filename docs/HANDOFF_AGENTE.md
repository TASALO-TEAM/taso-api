# HANDOFF — taso-api / taso-bot (código muerto + recursos del VPS)

Actualizado: 2026-11-10. Plan completo: `docs/plans/2026-11-10-codigo-muerto-y-resiliencia-api.md` (en la raíz `tasalo/docs`).

## Decisiones del dueño (Ersus)
- Cubanomic: quitar scraper de tasas, rutas y job del scheduler. **NO tocar la captura de imagen** (`image_capture.py`, `/images/eltoque*`, `/toqueimg` del bot): esa usa `iframe.cubanomic.com` y sigue viva.
- Prueba de carga contra el VPS: autorizada, de madrugada, con límite de tasa.
- Orden: primero bloque rápido (N+1, caché, ETag, VACUUM), medir, luego el resto.
- Rate limit por IP: no.
- Hora de Cuba: Cuba mantiene la hora de verano (UTC-4) aunque otros países ya cambiaron. La captura de imagen va a las **8:30 Cuba** (= 7:30 Miami hoy). Se usa `timezone="America/Havana"` y el tzdata del VPS (2026f) da -04:00 hoy; verificado.

## Hecho
- API PR #5 fusionado a `main` (8881eb0): N+1 fuera, caché en memoria (TTL 45 s, invalidada en `refresh_all`), ETag + `Cache-Control: public, max-age=30`, captura de imagen 8:30 Cuba, textos corregidos. 8 tests nuevos pasan (`tests/test_services/test_rates_batch_cache.py`).
- VPS: `git pull` hecho en `/home/ersus/tasalo/taso-api` (8881eb0) y el servicio ya fue reiniciado (17:33 CDT). DESPUÉS: `/latest` en frío ≈ 0.52 s (antes 1.45 s), con caché ≈ 4 ms; `/eltoque` en frío ≈ 0.50 s, con caché ≈ 3 ms; 304 con `If-None-Match` ≈ 2.5 ms; RSS ≈ 121 MB.
- Bot: PR #5 (imports perezosos) ya estaba fusionado.

## Medición ANTES (main desplegado, curl local en el VPS)
- `/api/v1/tasas/latest` ≈ 1.45 s; `/api/v1/tasas/eltoque` ≈ 0.345 s; RSS uvicorn ≈ 126 MB (RAM total 1966 MB, swap ~870/1023 usado).
- Repetir los mismos curl tras el reinicio y comparar.

## Pendiente (en orden)
0. (Hecho en local, SIN commit ni despliegue) `src/scrapers/binance.py` y `eltoque.py` usaban `logger` sin definirlo (NameError latente): se añadió `import logging` + `logger = logging.getLogger(__name__)`. En Binance la línea "Símbolos faltantes" pasó de info a debug (el aviso con el conteo sigue en warning). Falta: commit en rama `fix/scrapers-logger`, push, PR, `git pull` + `sudo systemctl restart taso-api` en el VPS, y correr tests dirigidos. Opcional: `eltoque.py` traga en silencio 401/timeout/red (devuelve None); valorar `logger.warning`. `bcc.py` no tiene logger pero tampoco lo usa.
1. (Hecho) Reinicio + medición DESPUÉS. Nota: `/eltoque` en frío subió de 0.345 s a ~0.50 s (ahora se serializa con el candado de caché); revisar si vale la pena.
2. API: pool de conexiones, registro de peticiones por lotes (filtrar escáneres), `print()` → `logger`, `EXPLAIN ANALYZE` de `history/daily`, `VACUUM (ANALYZE) rate_snapshots`, retención de `api_request_log`, prueba de carga.
3. API: código muerto + Cubanomic (rates), ramas `refactor:` separadas.
4. Bot: código muerto (cadena de imágenes heredada, stubs BBAlert, logger sin uso) + `httpx.AsyncClient` compartido en `ai_logic.py`. Actualizar el comentario "7:05" en `src/services/daily_image_sender.py` (~línea 140) a 8:30.
5. Borrar ramas fusionadas.

## Ojo
- Alertas de imagen del bot configuradas antes de las 8:30 Cuba verán la imagen del día anterior (el bot reintenta 3 veces y sigue con la última disponible). Valorar si se avisa o se valida la hora mínima.
- VPS: `bbchat`, `bia`, `main`, `rss` (units de otros bots, `/home/ersus/{bbchat,bot/bia,bot/main,rss}`) están en bucle de reinicio (~77 mil reinicios, exit 203/EXEC = el ejecutable no existe). Consumen CPU/log para nada; pedir OK al dueño antes de `systemctl disable --now`.
- Tests locales: el `.env` apunta a servicios reales y `TestClient(app)` se cuelga al arrancar el lifespan; ejecutar tests dirigidos: `uv run --frozen --with pytest --with pytest-asyncio --with pytest-timeout python -m pytest --timeout=40 <archivo>`. `test_redis_settings_default_values` falla por el `.env` local (preexistente).
- Windows + PowerShell: para ssh, enviar scripts por stdin quitando `\r` (`($sh -replace "`r","") | ssh pan 'bash -s'`); las comillas dobles anidadas se rompen.
- `ssh pan` entra sin clave; `sudo` pide contraseña (pedírsela al dueño).
- Un hook de pre-commit sube la versión en cada commit (`pyproject.toml`).
