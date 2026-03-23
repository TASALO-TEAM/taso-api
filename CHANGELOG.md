# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/),
y este proyecto se adhiere a [Versionado Semántico](https://semver.org/lang/es/).

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
