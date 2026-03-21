# TASALO-API — Progreso de Implementación

> **Última actualización:** 2026-03-21
> **Estado:** En progreso

---

## 📋 Visión General del Proyecto

**Objetivo:** Implementar `taso-api` — el backend central del ecosistema TASALO que agrega tasas de cambio de ElToque, CADECA, BCC y Binance, y las expone como API REST.

**Repositorio:** `tasalo/taso-api`
**Stack:** Python 3.12 · FastAPI · PostgreSQL/SQLite · SQLAlchemy async · Alembic · APScheduler

---

## 🗓️ Fases de Implementación

### ✅ Fase 1 — Scaffold y Base de Datos
**Estado:** **EN PROGRESO**
**Iniciado:** 2026-03-21
**Completado:** —

**Objetivo:** Repositorio funcional con conexión a base de datos y endpoint de health check.

#### Tareas

- [ ] **Task 1:** Estructura de directorios y archivos base
  - [ ] `.gitignore`
  - [ ] `.env.example`
  - [ ] `requirements.txt`
  - [ ] `src/__init__.py`
  - [ ] `docs/plans/.gitkeep`

- [ ] **Task 2:** Configuración con Pydantic Settings
  - [ ] `src/config.py` con validación
  - [ ] `tests/test_config.py`

- [ ] **Task 3:** Modelos de Base de Datos
  - [ ] `src/database.py`
  - [ ] `src/models/rate_snapshot.py`
  - [ ] `src/models/scheduler_status.py`
  - [ ] `tests/test_models.py`

- [ ] **Task 4:** Configurar Alembic para Migraciones
  - [ ] `alembic.ini`
  - [ ] `alembic/env.py` (async)
  - [ ] Migración inicial
  - [ ] Verificar tablas creadas

- [ ] **Task 5:** Aplicación FastAPI y Endpoint Health
  - [ ] `src/main.py`
  - [ ] `tests/test_main.py`
  - [ ] CORS middleware
  - [ ] Lifespan events

- [ ] **Task 6:** README y Documentación
  - [ ] `README.md` completo

- [ ] **Task 7:** Verificación Final
  - [ ] Servidor levanta
  - [ ] Health endpoint responde
  - [ ] Swagger UI disponible
  - [ ] Tests pasan
  - [ ] Tag v1.0.0-fase1

---

### ⏳ Fase 2 — Scrapers
**Estado:** Pendiente

**Objetivo:** Los 4 scrapers/clientes funcionando como funciones independientes testeables.

- [ ] `scrapers/eltoque.py` — Cliente API ElToque
- [ ] `scrapers/binance.py` — Cliente API Binance
- [ ] `scrapers/cadeca.py` — Scraper CADECA (httpx + BS4)
- [ ] `scrapers/bcc.py` — Scraper BCC (httpx + BS4)
- [ ] Tests manuales para cada scraper

---

### ⏳ Fase 3 — Servicio de Tasas y Scheduler
**Estado:** Pendiente

**Objetivo:** El backend recoge datos automáticamente y los persiste en PostgreSQL.

- [ ] `services/rates_service.py`
- [ ] `services/scheduler.py` con APScheduler
- [ ] Job `refresh_all` cada 5 minutos
- [ ] Actualizar `SchedulerStatus` en cada ejecución

---

### ⏳ Fase 4 — Endpoints Públicos
**Estado:** Pendiente

**Objetivo:** API consumible por los servicios clientes.

- [ ] `routers/rates.py`
- [ ] `GET /api/v1/tasas/latest`
- [ ] `GET /api/v1/tasas/eltoque`
- [ ] `GET /api/v1/tasas/cadeca`
- [ ] `GET /api/v1/tasas/bcc`
- [ ] `GET /api/v1/tasas/history`
- [ ] Pydantic schemas de respuesta
- [ ] CORS configurado

---

### ⏳ Fase 5 — Endpoints Admin y Auth
**Estado:** Pendiente

**Objetivo:** Endpoints protegidos para operaciones privilegiadas.

- [ ] `middleware/auth.py`
- [ ] `routers/admin.py`
- [ ] `POST /api/v1/admin/refresh`
- [ ] `GET /api/v1/admin/status`

---

### ⏳ Fase 6 — Hardening y README
**Estado:** Pendiente

**Objetivo:** El servicio está listo para producción básica.

- [ ] Exception handlers globales
- [ ] Logging estructurado
- [ ] Documentación `.env.example`
- [ ] README final

---

## 📊 Métricas

| Métrica | Valor |
|---------|-------|
| Total fases | 6 |
| Fases completadas | 0 |
| Progreso total | 0% |
| Tests escritos | 0 |
| Endpoints implementados | 0/7 |
| Scrapers implementados | 0/4 |

---

## 🐛 Issues y Bloqueos

| Fecha | Issue | Estado | Resolución |
|-------|-------|--------|------------|
| — | — | — | — |

---

## 📝 Notas de Desarrollo

### 2026-03-21
- Diseño de implementación aprobado
- Plan de Fase 1 creado en `docs/plans/2026-03-21-taso-api-fase1.md`
- Archivos de seguimiento creados: `PROGRESS.md`, `CONTINUITY.md`
- **Próximo paso:** Comenzar Task 1 del plan

---

## 🔗 Enlaces Relacionados

- **Plan de Implementación:** `docs/plans/2026-03-21-taso-api-fase1.md`
- **Diseño Original:** `docs/plans/2026-03-21-tasalo-api-design.md`
- **Continuidad del Agente:** `docs/CONTINUITY.md`
- **Repositorio GitHub:** https://github.com/tasalo/taso-api
