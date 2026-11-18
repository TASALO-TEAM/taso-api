
# HANDOFF — taso-api / taso-bot (código muerto + recursos del VPS)

Actualizado: 2026-11-11. Plan completo: `tasalo/docs/plans/2026-11-10-codigo-muerto-y-resiliencia-api.md`.

## Decisiones del dueño (Ersus)
- Cubanomic: se quitó scraper de tasas, rutas y job. **NO tocar la captura de imagen** (`image_capture.py`, `/images/eltoque*`, `/toqueimg`): usa `iframe.cubanomic.com` y sigue viva (`scrapers/cubanomic.py` se conserva por eso).
- Prueba de carga al VPS: autorizada, de madrugada, con límite de tasa.
- Rate limit por IP: no.
- Hora de Cuba: mantiene hora de verano (UTC-4) todo el año. Captura de imagen a las **8:15 Cuba** (antes 8:30; ver sesion 2026-11-14 al final) (`timezone="America/Havana"`). El VPS ya corre en hora de Cuba (`date` = CDT).

## Hecho (todo en `main` y desplegado salvo lo marcado)
- API: N+1 de `/latest` y `/eltoque` fuera, caché en memoria (TTL 45 s), ETag + Cache-Control, captura 8:30 Cuba (PR #5).
- API: `logger` definido en `binance.py`/`eltoque.py` (PR #6), `print()` → `logger` (PR #7), pool de conexiones + registro de peticiones por lotes con filtro de escáneres (PR #8), código muerto + Cubanomic de tasas (PR #9, commit 1334fb3). VPS reiniciado con todo esto.
- BD: `VACUUM (ANALYZE) rate_snapshots` hecho (193 mil filas muertas → 0). La poda de `api_request_log` ya existía (30 días en `refresh_all`).
- Bot: imports perezosos (PR #5) y código muerto (PR #6, 85af45f; cadena de imágenes heredada, `file_manager.py`, `check_feature_access`). En el VPS el código ya está en disco.
- VPS: unidades huérfanas `bbchat`, `bia`, `main`, `rss` eliminadas (copias en `/home/ersus/backup-units-bbalert/`).
- Medición (VPS, puerto 8040): `/latest` 1.45 s → 0.55 s frío / 3 ms con caché; `/eltoque` 0.345 s → 0.37 s / 2 ms; `history/daily` 180 días 6.7 s en frío (cuello: ~38 mil filas por red + Python, no la consulta).

## Pendiente (en orden)
1. (Hecho) `taso-bot` reiniciado en el VPS el 2026-11-11 08:35 con 85af45f: activo, ~68 MB RAM, sin Traceback ni aviso `Template base not found`; jobs (alertas de imagen/precio, digest /tspl) arrancaron.
2. (Hecho) Job "Captura diaria imagen ElToque (8:30 Cuba)" verificado el 2026-11-11: corrió 08:30:00, imagen nueva (618 KB), `stale=False`.
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


## Sesion 2026-11-14 — captura a las 8:15 con hash y reintentos (decidido por Ersus: "dale")
- **Por que:** hasta el 9/11 el servidor estaba en CST y el cron de "7:05" corria a las 8:05 reales (despues del corte de El Toque, 8:00 Cuba). Al corregir la zona horaria paso a las 7:05 reales (imagen vieja) y se tapo moviendolo a 8:30. Hay 3 capturas hechas entre 8:05 y 8:13 y las tres eran nuevas, por eso 8:15.
- **taso-api (PR #10, `3c6a651`, v0.13.2.0):** cron 8:15 `America/Havana`. `capture_and_store_image` compara el sha256 del archivo con el de antes de descargar: si es identico y el ultimo snapshot es de un dia anterior (fecha Cuba), devuelve `stale=True` **sin refrescar `captured_at`** (el bot usa ese campo para saber si la imagen es de hoy). El job reintenta cada 5 min hasta 7 veces (~8:50) si `stale` o falla (ids `eltoque_image_capture_retry_N`). `misfire_grace_time` 300 s en el cron y 120 s en los reintentos: con el default de APScheduler (1 s) un loop ocupado descartaria el reintento en silencio.
- **taso-bot (PR #12, `5640222`, v0.18.4.0):** `IMAGE_CAPTURE_TIME = "08:15"`. Los avisos cuya hora es anterior a la captura (p. ej. 7:30, que se ajustan a 8:16) se aceptan hasta `CAPTURE_GRACE_MIN = 40` min despues (hasta ~8:56), para cubrir los reintentos de la API. Antes solo valia ±5 min (ticks de 8:15 y 8:20), asi que una imagen que llegara a las 8:30 dejaba a esos usuarios sin envio ese dia. Los avisos a hora fija posterior (9:00) conservan su ventana de 5 min.
- **Verificacion:** 21 tests de captura en verde en taso-api (`uv run ...`, ver "Ojo"); bot: rojo/verde en worktree del VPS (la prueba de captura tardia falla con el codigo anterior), suite 422 pasan + 1 falla conocida (`test_imports_perezosos`, H-031, igual en `main`).
- **Desplegado a medias:** `git pull` hecho en el VPS en ambos repos (api `3c6a651`, bot `5640222`). **FALTA reiniciar `taso-api` y luego `taso-bot`** (pide sudo): hasta entonces corren con el cron de 8:30 y sin reintentos. Reiniciar fuera de 8:10-9:00 Cuba. Tras reiniciar: `journalctl -u taso-api` debe mostrar "ElToque image capture job added (08:15 Cuba)".
- **Sin verificar en vivo:** el primer ciclo real (manana 8:15 Cuba). Mirar el log de taso-api: `Captura diaria de ElToque OK (stale=..., intento=N)`.
- **Limite conocido:** `_sent_today` del bot vive en memoria; si el bot se reinicia entre 8:16 y 8:56 un usuario con aviso temprano podria recibir la imagen dos veces.
- **Descartado (medido):** liberar memoria del bot "descargando" modulos pesados tras usarlos no sirve, Python no devuelve la memoria (177,2 MB antes y despues). El recorte real seria reemplazar `pandas_ta` (H-032, ~70 MB), pendiente de aprobacion.

## Sesion 2026-11-17 - ElToque hibrido y monedas agrupadas
- Plan y tareas: `tasalo/docs/plans/2026-11-17-eltoque-hibrido-y-agrupado-monedas.md` y `taso-bot/task/registro` (BOARD API-T1..T8, D-026, `handoffs/eltoque-hibrido-2026-11-17.md`).
- **Por que:** el token de la API de ElToque vencio el 2026-11-14. Cubanomic (`api.cubanomic.com/api/v1/x-rates`, con `Referer`) se usa como respaldo y como complemento: da ~20 monedas.
- **Hecho en main/VPS (Grok, b347d7f):** 3 intentos a ElToque y Cubanomic solo si fallan.
- **Hecho y desplegado 2026-11-17 (v0.15.0.0):** mezcla API + Cubanomic y alertas al grupo soporte (PR #13, 26 tests); `UDS` de Cubanomic se expone como `ZELLE` (PR #14). El bot (taso-bot PR #53, v0.38.0.0) muestra lista fija EUR, USD, ZELLE, MLC, CLA + BTC, TRX, USDT, BNB.
- **Decidido por Ersus:** monedas de referencia visibles dentro de "Mostrar más", debajo de los grupos Principales, Cripto y Otras; `UDS` = Zelle, `CLA` = tarjeta Clásica; Zelle siempre tras USD en apps, miniapp y extensiones. FALTA: `offers`/`group`/`tier`/`name` en la API y los clientes (ver plan, tareas API-T2..T8).
- Token de ElToque vencido (2026-11-14): la API opera en modo `cubanomic` hasta poner el nuevo en `ELTOQUE_API_KEY` del `.env` del VPS.
