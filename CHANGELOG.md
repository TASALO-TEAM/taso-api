# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/),
y este proyecto se adhiere a [Versionado Semántico](https://semver.org/lang/es/).

## [Unreleased]

### Added
- **`POST /api/v1/admin/stats/users/seen`** (admin, `X-API-Key`): upsert idempotente de `user_id`, `username` y `first_name` en `bot_users` sin contarlo como comando (`total_commands` no sube y no escribe en `bot_command_stats`). Un `username`/`first_name` nulo no borra el valor ya conocido. Base de taso-bot#72 (Fase 1, registro automatico de usuarios).
- **ElToque agrupado para los clientes**: `/tasas/eltoque` y `data.eltoque` de `/tasas/latest` ahora traen `name`, `group` (main/crypto/other), `tier` (market/reference), `offers` y `order` por moneda, ya ordenadas (EUR, USD, ZELLE, MLC, CLA / cripto / otras). Campos aditivos: los clientes viejos los ignoran. Catalogo en `src/services/eltoque_catalog.py`.
- **Columna `rate_snapshots.offers`** (migracion `4k_add_rate_snapshot_offers`, aditiva y nullable): ofertas reales detras de una tasa de Cubanomic; `NULL` = API oficial.
- **QvaPay como fuente de tasas**: nuevo scraper `src/scrapers/qvapay.py` (10 métodos de pago, compra y venta), `GET /api/v1/tasas/qvapay`, clave `qvapay` en `/tasas/latest` y `source=qvapay` en `/tasas/history`. `rate` es el promedio compra/venta.
- **QvaPay: nuevo método `CUPCASH`** (CUP en efectivo, categoría Cash de QvaPay).

### Changed
- **Ciclo de refresco de 5 a 15 minutos** (`REFRESH_INTERVAL_MINUTES`) para todas las fuentes; el indicador `change` compara contra 15 min atrás.
- **Retención de tasas de 1 año a 6 meses** (`RATES_RETENTION_DAYS` default 180).

## [0.3.0] - 2026-03-23

### Fixed
- **ElToque Scraper**: Corregido error crítico que impedía la obtención de tasas de ElToque
  - El scraper ahora carga automáticamente la API key desde la configuración
  - Los parámetros `api_key` y `api_url` son opcionales en `fetch_eltoque()`
  - Todas las 4 fuentes de datos funcionan correctamente (ElToque, CADECA, BCC, Binance)

### Changed
- Actualización de versión a 0.3.0

## [0.2.1] - 2026-03-23

### Added
- **Systemd Service**: Configuración de servicio systemd para ejecutar la API como daemon en Linux
  - Archivo de servicio documentado en README.md
  - Soporte para inicio automático al boot
  - Restart automático en caso de fallos
  - Logging integrado con systemd journal

### Changed
- Actualización de versión a 0.2.1 (release estable)

## [0.2.0] - 2026-03-22

### Added
- Endpoints REST para tasas de cambio:
  - `GET /api/v1/tasas/latest` - Últimas tasas de todas las fuentes
  - `GET /api/v1/tasas/eltoque` - Tasas del mercado informal (ElToque)
  - `GET /api/v1/tasas/cadeca` - Tasas oficiales (CADECA)
  - `GET /api/v1/tasas/bcc` - Tasas del Banco Central de Cuba
  - `GET /api/v1/tasas/history` - Histórico de tasas
- Scheduler automático para actualización periódica de tasas
- Integración con múltiples fuentes de datos
- Base de datos PostgreSQL/SQLite para persistencia
- Documentación completa en README.md

### Changed
- Migración de estructura de proyecto a uv/pip
- Mejoras en logging estructurado
- Actualización de dependencias

### Fixed
- Manejo de errores en scrapers
- Validación de schemas Pydantic
- Conexión asíncrona a base de datos

## [0.1.0] - 2026-03-20

### Added
- Estructura inicial del proyecto
- Configuración básica de FastAPI
- Primeros scrapers para fuentes de tasas
