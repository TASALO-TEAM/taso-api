# TASALO-API — Prompt de Continuidad para Agente

> **Generado:** 2026-03-21
> **Versión del proyecto:** 1.0.0 (Fase 1 en progreso)

---

## 🎯 Contexto del Proyecto

**TASALO** es una plataforma distribuida para consultar tasas de cambio del dólar en Cuba en tiempo real. El ecosistema tiene 4 repositorios:

1. **taso-api** (este repo) — Backend FastAPI, única pieza que habla con fuentes externas
2. **taso-bot** — Bot de Telegram (python-telegram-bot)
3. **taso-miniapp** — Mini App web dentro de Telegram (Flask + Tailwind)
4. **taso-extension** — Extensión de navegador (Manifest V3)

**Arquitectura:**
```
ElToque API ──┐
CADECA ───────┤
BCC ──────────├──> taso-api (FastAPI + PostgreSQL) ──> Bot, MiniApp, Extension
Binance ──────┘
```

---

## 📁 Estado Actual del Repositorio

**Directorio:** `/home/ersus/tasalo/taso-api`

**Estado:** Fase 1 en progreso — Scaffold y Base de Datos

**Archivos existentes:**
```
taso-api/
├── .git/                    # Repositorio Git inicializado (vacío)
├── docs/
│   ├── plans/
│   │   ├── 2026-03-21-tasalo-api-design.md  # Diseño original
│   │   └── 2026-03-21-taso-api-fase1.md     # Plan de implementación Fase 1
│   ├── PROGRESS.md          # Tracking de progreso
│   └── CONTINUITY.md        # Este archivo
└── [RESTO POR IMPLEMENTAR]
```

**Lo que NO existe aún:**
- `src/` — Código fuente
- `tests/` — Tests
- `alembic/` — Migraciones
- `requirements.txt` — Dependencias
- `.env` — Configuración local

---

## 🎯 Próxima Acción Requerida

**Implementar Fase 1 — Scaffold y Base de Datos**

El plan completo está en: `docs/plans/2026-03-21-taso-api-fase1.md`

### Tareas Pendientes (en orden):

1. **Task 1:** Estructura de directorios y archivos base
   - Crear `.gitignore`, `.env.example`, `requirements.txt`
   - Crear `src/__init__.py`, `docs/plans/.gitkeep`

2. **Task 2:** Configuración con Pydantic Settings
   - Crear `src/config.py`
   - Crear `tests/test_config.py`

3. **Task 3:** Modelos de Base de Datos
   - Crear `src/database.py`
   - Crear `src/models/rate_snapshot.py`
   - Crear `src/models/scheduler_status.py`
   - Crear `tests/test_models.py`

4. **Task 4:** Configurar Alembic
   - Inicializar Alembic
   - Configurar `alembic/env.py` para async
   - Generar y aplicar migración inicial

5. **Task 5:** Aplicación FastAPI
   - Crear `src/main.py` con endpoint `/api/v1/health`
   - Crear `tests/test_main.py`

6. **Task 6:** README
   - Crear `README.md` completo

7. **Task 7:** Verificación Final
   - Levantar servidor y verificar health endpoint
   - Correr tests
   - Crear tag v1.0.0-fase1

---

## 🛠️ Stack Tecnológico

| Componente | Tecnología | Versión |
|------------|-----------|---------|
| Language | Python | 3.12+ |
| Framework | FastAPI | 0.115.0 |
| ORM | SQLAlchemy (async) | 2.0.30 |
| Migrations | Alembic | 1.13.0 |
| Settings | pydantic-settings | 2.2.0 |
| DB (dev) | SQLite + aiosqlite | 0.20.0 |
| DB (prod) | PostgreSQL + asyncpg | 0.29.0 |
| Server | uvicorn | 0.30.0 |
| Testing | pytest + pytest-asyncio | latest |
| HTTP Client | httpx | 0.27.0 |

---

## ⚙️ Configuración Requerida

### Variables de Entorno (.env.example)

```bash
# Database - SQLite para desarrollo local
DATABASE_URL=sqlite+aiosqlite:///./tasalo.db

# ElToque API
ELTOQUE_API_KEY=<tu_api_key_aqui>
ELTOQUE_API_URL=https://tasas.eltoque.com/v1/trmi

# Security
ADMIN_API_KEY=<tu_secret_admin_key_aqui>

# Scheduler
REFRESH_INTERVAL_MINUTES=5

# CORS
ALLOWED_ORIGINS=*
```

**Nota:** El usuario YA TIENE la API key de ElToque.

---

## 📋 Convenciones del Proyecto

### Estructura de Directorios
```
src/
├── main.py           # FastAPI app
├── config.py         # Pydantic settings
├── database.py       # SQLAlchemy engine
├── models/           # ORM models
├── schemas/          # Pydantic schemas
├── routers/          # API routers
├── scrapers/         # Scrapers de fuentes
├── services/         # Business logic
└── middleware/       # Auth, logging, etc.
```

### Tests
- Directorio: `tests/`
- Framework: pytest + pytest-asyncio
- Convención: `test_<module>.py`
- Coverage objetivo: >80%

### Git
- Commits frecuentes y atómicos
- Mensajes en formato: `type: description`
- Tags para versiones: `v1.0.0-fase1`

---

## 🎨 Design Patterns y Principios

1. **DRY** — No repetir código
2. **YAGNI** — No agregar funcionalidad hasta que sea necesaria
3. **TDD** — Tests primero, implementación después
4. **Async First** — Todo asíncrono con asyncio
5. **Config Externalizada** — Nada hardcodeado, todo por env

---

## 🔗 Recursos y Enlaces

### Documentos del Proyecto
- **Diseño del Ecosistema:** `/home/ersus/tasalo/plans/2026-03-21-tasalo-ecosystem-design.md`
- **Diseño taso-api:** `/home/ersus/tasalo/plans/2026-03-21-tasalo-api-design.md`
- **Plan de Fase 1:** `docs/plans/2026-03-21-taso-api-fase1.md`
- **Progreso:** `docs/PROGRESS.md`

### Organización GitHub
- **URL:** https://github.com/tasalo
- **Repositorios:** taso-api, taso-bot, taso-miniapp, taso-extension

### Fuentes Externas
- **ElToque API:** https://tasas.eltoque.com/v1/trmi
- **Binance API:** https://api.binance.com/api/v3/ticker/price
- **CADECA:** https://www.cadeca.cu (scraper)
- **BCC:** https://www.bc.gob.cu (scraper)

---

## 🚀 Comandos Útiles

### Setup Inicial
```bash
cd /home/ersus/tasalo/taso-api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Base de Datos
```bash
alembic upgrade head          # Aplicar migraciones
alembic revision --autogenerate -m "msg"  # Nueva migración
alembic current               # Ver versión actual
```

### Servidor
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Tests
```bash
pytest                        # Todos los tests
pytest -v                     # Verbose
pytest --cov=src             # Con coverage
```

### Verificación
```bash
curl http://localhost:8000/api/v1/health
```

---

## ✅ Criterios de Éxito de Fase 1

Un desarrollador debe poder:

1. Clonar el repositorio
2. Copiar `.env.example` a `.env`
3. Correr `pip install -r requirements.txt`
4. Correr `alembic upgrade head`
5. Correr `uvicorn src.main:app --reload`
6. Verificar `curl http://localhost:8000/api/v1/health` devuelve `{"ok": true, "db": "connected"}`
7. Ver `http://localhost:8000/docs` muestra Swagger UI

---

## 📝 Instrucciones para el Agente

**Para continuar la implementación:**

1. **Leer el plan completo:** `docs/plans/2026-03-21-taso-api-fase1.md`

2. **Seguir el proceso TDD:**
   - Escribir test primero
   - Verificar que falla
   - Implementar mínimo para pasar
   - Verificar que pasa
   - Commit

3. **Usar la skill `executing-plans`** para ejecutar el plan task por task

4. **Actualizar `docs/PROGRESS.md`** después de cada task completado

5. **Commits frecuentes** con mensajes descriptivos

6. **Al finalizar Fase 1:** Crear tag `v1.0.0-fase1`

---

## 🆘 Posibles Problemas y Soluciones

| Problema | Solución |
|----------|----------|
| `aiosqlite` no instala | Verificar Python 3.12+ |
| Alembic no detecta modelos | Importar modelos en `env.py` |
| Tests async fallan | Verificar `pytest-asyncio` instalado |
| CORS errors | Verificar `ALLOWED_ORIGINS` en `.env` |
| SQLite lock errors | Agregar `connect_args={"check_same_thread": False}` |

---

**Fin del documento de continuidad.**

Para comenzar, ejecutar:
```bash
skill: executing-plans
```

Y seguir el plan en `docs/plans/2026-03-21-taso-api-fase1.md`
