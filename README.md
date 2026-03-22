# TASALO API

[![Version](https://img.shields.io/badge/version-1.5.0-blue.svg)](https://github.com/tasalo/taso-api/releases)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Backend FastAPI para el ecosistema TASALO. Agrega tasas de cambio del mercado informal cubano (ElToque), CADECA, BCC y Binance, y las expone como API REST con actualización automática cada 5 minutos.

## 📋 Tabla de Contenidos

- [Características](#-características)
- [Stack Tecnológico](#-stack-tecnológico)
- [Requisitos del Sistema](#-requisitos-del-sistema)
- [Instalación Paso a Paso](#-instalación-paso-a-paso)
- [Configuración](#-configuración)
- [Endpoints de la API](#-endpoints-de-la-api)
- [Migraciones de Base de Datos](#-migraciones-de-base-de-datos)
- [Testing](#-testing)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Despliegue en Producción](#-despliegue-en-producción)
- [Solución de Problemas](#-solución-de-problemas)
- [License](#-license)

---

## ✨ Características

- **4 Fuentes de tasas:** ElToque (mercado informal), CADECA, BCC (oficiales) y Binance (cripto)
- **Actualización automática:** Scheduler ejecuta scrapers cada 5 minutos
- **Histórico de tasas:** Almacena snapshots para análisis de tendencias
- **Indicadores de cambio:** Calcula 🔺/🔻/neutral comparando con el snapshot anterior
- **API REST documentada:** Swagger UI y ReDoc automáticos
- **Endpoints protegidos:** Admin API con autenticación por API key
- **Logging estructurado:** Logs en stdout con timestamps y niveles
- **Manejo de errores:** Respuestas JSON consistentes para todos los errores

---

## 🛠️ Stack Tecnológico

| Componente | Tecnología | Versión |
|------------|-----------|---------|
| **Lenguaje** | Python | 3.12+ |
| **Framework Web** | FastAPI | 0.115+ |
| **ORM** | SQLAlchemy (async) | 2.0.30+ |
| **Migraciones** | Alembic | 1.13.0+ |
| **Settings** | pydantic-settings | 2.2.0+ |
| **DB (dev)** | SQLite + aiosqlite | 0.20.0+ |
| **DB (prod)** | PostgreSQL + asyncpg | 0.29.0+ |
| **Server** | uvicorn | 0.30.0+ |
| **HTTP Client** | httpx | 0.27.0+ |
| **Scraping** | BeautifulSoup4 + lxml | 4.12.0+ |
| **Scheduler** | APScheduler | 3.10.4+ |
| **Testing** | pytest + pytest-asyncio | 9.0.2+ |

---

## 💻 Requisitos del Sistema

### Mínimos
- **Python:** 3.12 o superior
- **RAM:** 512 MB
- **Disco:** 100 MB
- **SO:** Linux, macOS o Windows

### Recomendados (Producción)
- **Python:** 3.13+
- **RAM:** 1 GB+
- **Disco:** 500 MB+ (para histórico de tasas)
- **PostgreSQL:** 14+

### Verificar Python

```bash
python --version  # Debe mostrar Python 3.12.x o superior
```

Si tienes una versión inferior, descarga la última desde [python.org](https://www.python.org/downloads/).

---

## 🚀 Instalación Paso a Paso

### 1. Clonar el repositorio

```bash
git clone https://github.com/tasalo/taso-api.git
cd taso-api
```

### 2. Crear entorno virtual con uv (recomendado)

```bash
# Instalar uv si no lo tienes
curl -LsSf https://astral.sh/uv/install.sh | sh

# Crear entorno virtual
uv venv

# Activar entorno (Linux/Mac)
source .venv/bin/activate

# Activar entorno (Windows)
.venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
uv pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
# Copiar template
cp .env.example .env

# Editar con tus valores (usar nano, vim, o editor preferido)
nano .env
```

**Variables mínimas requeridas:**
```bash
DATABASE_URL=sqlite+aiosqlite:///./tasalo.db
ADMIN_API_KEY=cambia_esto_por_un_valor_seguro
```

**Para usar ElToque (opcional):**
```bash
ELTOQUE_API_KEY=tu_api_key_aqui
```

### 5. Inicializar base de datos

```bash
# Aplicar migraciones
alembic upgrade head

# Verificar migraciones aplicadas
alembic current
```

### 6. Correr el servidor

```bash
# Desarrollo (auto-reload)
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Producción (sin reload, múltiples workers)
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 7. Verificar funcionamiento

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Expected response:
# {"ok":true,"version":"1.5.0","db":"connected","database_url":"sqlite"}
```

---

## ⚙️ Configuración

### Variables de Entorno

Todas las variables están documentadas en `.env.example`:

| Variable | Descripción | Default | Requerido |
|----------|-------------|---------|-----------|
| `DATABASE_URL` | URL de conexión a la base de datos | `sqlite+aiosqlite:///./tasalo.db` | ✅ |
| `ELTOQUE_API_KEY` | API key para ElToque | — | ❌ (solo scrapers) |
| `ELTOQUE_API_URL` | URL de la API de ElToque | `https://tasas.eltoque.com/v1/trmi` | ❌ |
| `ADMIN_API_KEY` | Clave para endpoints admin | — | ✅ (producción) |
| `REFRESH_INTERVAL_MINUTES` | Intervalo del scheduler | `5` | ❌ |
| `ALLOWED_ORIGINS` | Orígenes CORS (separados por coma) | `*` | ❌ |

### Ejemplo .env para Desarrollo

```bash
DATABASE_URL=sqlite+aiosqlite:///./tasalo.db
ELTOQUE_API_KEY=tu_api_key_aqui
ADMIN_API_KEY=dev_secret_123
REFRESH_INTERVAL_MINUTES=5
ALLOWED_ORIGINS=*
```

### Ejemplo .env para Producción

```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/tasalo
ELTOQUE_API_KEY=tu_api_key_secreta
ADMIN_API_KEY=produccion_secret_456_xyz
REFRESH_INTERVAL_MINUTES=5
ALLOWED_ORIGINS=https://tasalo.app,https://bot.tasalo.app
```

---

## 📡 Endpoints de la API

### Endpoints Públicos (sin autenticación)

#### `GET /api/v1/health`
Verificar estado de la aplicación.

```bash
curl http://localhost:8000/api/v1/health
```

**Respuesta:**
```json
{
  "ok": true,
  "version": "1.5.0",
  "db": "connected",
  "database_url": "sqlite"
}
```

---

#### `GET /api/v1/tasas/latest`
Obtener tasas combinadas de todas las fuentes con indicadores de cambio.

```bash
curl http://localhost:8000/api/v1/tasas/latest
```

**Respuesta:**
```json
{
  "ok": true,
  "data": {
    "eltoque": {
      "USD": { "rate": 365.00, "change": "up", "prev_rate": 360.00 },
      "EUR": { "rate": 398.00, "change": "neutral", "prev_rate": 398.00 }
    },
    "cadeca": { ... },
    "bcc": { ... },
    "binance": { ... }
  },
  "updated_at": "2026-03-22T14:30:00Z"
}
```

---

#### `GET /api/v1/tasas/eltoque`
Obtener solo tasas de ElToque (mercado informal).

```bash
curl http://localhost:8000/api/v1/tasas/eltoque
```

---

#### `GET /api/v1/tasas/cadeca`
Obtener solo tasas de CADECA (compra/venta).

```bash
curl http://localhost:8000/api/v1/tasas/cadeca
```

---

#### `GET /api/v1/tasas/bcc`
Obtener solo tasas de BCC (oficiales).

```bash
curl http://localhost:8000/api/v1/tasas/bcc
```

---

#### `GET /api/v1/tasas/history`
Obtener histórico de tasas para gráficas.

**Query Params:**
- `source` (opcional): Filtrar por fuente (`eltoque`, `cadeca`, `bcc`, `binance`)
- `currency` (opcional): Filtrar por moneda (`USD`, `EUR`, `MLC`, `BTC`)
- `days` (opcional): Días de histórico (1-365, default: 7)

```bash
curl "http://localhost:8000/api/v1/tasas/history?source=eltoque&currency=USD&days=7"
```

**Respuesta:**
```json
{
  "ok": true,
  "data": [
    {
      "source": "eltoque",
      "currency": "USD",
      "rate": 365.00,
      "fetched_at": "2026-03-22T14:30:00Z"
    },
    {
      "source": "eltoque",
      "currency": "USD",
      "rate": 360.00,
      "fetched_at": "2026-03-22T14:25:00Z"
    }
  ]
}
```

---

### Endpoints Admin (requieren autenticación)

Todos los endpoints admin requieren el header `X-API-Key` con el valor configurado en `ADMIN_API_KEY`.

#### `GET /api/v1/admin/status`
Obtener estado del scheduler (última ejecución, errores).

```bash
curl http://localhost:8000/api/v1/admin/status \
  -H "X-API-Key: tu_admin_api_key"
```

**Respuesta:**
```json
{
  "ok": true,
  "data": {
    "last_run_at": "2026-03-22T14:30:00Z",
    "last_success_at": "2026-03-22T14:30:00Z",
    "error_count": 0,
    "last_error": null
  }
}
```

---

#### `POST /api/v1/admin/refresh`
Disparar refresh manual inmediato de todas las fuentes.

```bash
curl -X POST http://localhost:8000/api/v1/admin/refresh \
  -H "X-API-Key: tu_admin_api_key"
```

**Respuesta:**
```json
{
  "ok": true,
  "data": {
    "message": "Refresh completado",
    "sources_updated": 4,
    "snapshots_created": 12
  }
}
```

---

### Documentación Interactiva

Con el servidor corriendo, acceder a:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

---

## 🗄️ Migraciones de Base de Datos

### Crear nueva migración

```bash
# Generar migración automática basada en cambios de modelos
alembic revision --autogenerate -m "Descripción del cambio"
```

### Aplicar migraciones

```bash
# Aplicar todas las migraciones pendientes
alembic upgrade head
```

### Revertir migración

```bash
# Revertir última migración
alembic downgrade -1

# Revertir a migración específica
alembic downgrade <revision_id>
```

### Ver estado actual

```bash
# Ver migración actual
alembic current

# Ver historial de migraciones
alembic history
```

---

## 🧪 Testing

### Correr todos los tests

```bash
pytest
```

### Con verbose y coverage

```bash
pytest -v --cov=src --cov-report=term-missing
```

### Correr tests específicos

```bash
# Tests de un módulo
pytest tests/test_main.py -v

# Tests con patrón de nombre
pytest -k "test_health" -v

# Tests de scrapers
pytest tests/test_scrapers/ -v
```

### Ejecutar tests manuales de integración

```bash
# Test manual de scrapers (requiere .env configurado)
python scripts/test_scrapers_manual.py
```

---

## 📁 Estructura del Proyecto

```
taso-api/
├── alembic/
│   ├── env.py                    # Configuración de Alembic
│   ├── script.py.mako            # Template de migraciones
│   └── versions/                 # Migraciones generadas
├── docs/
│   └── plans/                    # Documentos de diseño
├── scripts/
│   └── test_scrapers_manual.py   # Test manual de integración
├── src/
│   ├── __init__.py
│   ├── main.py                   # FastAPI app + exception handlers
│   ├── config.py                 # Pydantic settings
│   ├── database.py               # SQLAlchemy engine + sessions
│   ├── models/
│   │   ├── __init__.py
│   │   ├── rate_snapshot.py      # Tabla rate_snapshots
│   │   └── scheduler_status.py   # Tabla scheduler_status
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── rates.py              # Schemas de tasas
│   │   └── admin.py              # Schemas de admin
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── rates.py              # Endpoints públicos
│   │   └── admin.py              # Endpoints protegidos
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── eltoque.py            # API ElToque
│   │   ├── binance.py            # API Binance
│   │   ├── cadeca.py             # Scraper CADECA
│   │   └── bcc.py                # Scraper BCC
│   ├── services/
│   │   ├── __init__.py
│   │   ├── rates_service.py      # Lógica de negocio
│   │   └── scheduler.py          # APScheduler
│   └── middleware/
│       ├── __init__.py
│       └── auth.py               # Validación X-API-Key
├── tests/
│   ├── conftest.py               # Fixtures compartidos
│   ├── test_config.py
│   ├── test_main.py
│   ├── test_models.py
│   ├── test_scrapers/
│   ├── test_services/
│   ├── test_routers/
│   └── test_middleware/
├── .env.example                  # Template de variables
├── .gitignore
├── alembic.ini                   # Configuración Alembic
├── pytest.ini                    # Configuración pytest
├── requirements.txt              # Dependencias
└── README.md                     # Este archivo
```

---

## 🌐 Despliegue en Producción

### 1. Base de Datos PostgreSQL

```bash
# Crear database y usuario
createdb tasalo
createuser tasalo_user
psql -c "ALTER USER tasalo_user WITH PASSWORD 'secure_password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE tasalo TO tasalo_user;"
```

### 2. Variables de Entorno

```bash
# En el servidor, crear .env con valores de producción
DATABASE_URL=postgresql+asyncpg://tasalo_user:secure_password@localhost:5432/tasalo
ADMIN_API_KEY=<generar_con_openssl_rand>
ALLOWED_ORIGINS=https://tu-dominio.com
```

### 3. Systemd Service (Linux)

```ini
# /etc/systemd/system/taso-api.service
[Unit]
Description=TASALO API
After=network.target

[Service]
Type=simple
User=tasalo
WorkingDirectory=/opt/taso-api
Environment="PATH=/opt/taso-api/.venv/bin"
ExecStart=/opt/taso-api/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Habilitar y iniciar servicio
sudo systemctl daemon-reload
sudo systemctl enable taso-api
sudo systemctl start taso-api
sudo systemctl status taso-api
```

### 4. Nginx Reverse Proxy (opcional)

```nginx
server {
    listen 80;
    server_name api.tasalo.app;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

---

## 🔧 Solución de Problemas

### Error: `aiosqlite` no instala

```bash
# Verificar Python 3.12+
python --version

# Reinstalar uv y dependencias
curl -LsSf https://astral.sh/uv/install.sh | sh
uv pip install --upgrade -r requirements.txt
```

### Alembic no detecta modelos

```bash
# Verificar que los modelos están importados en alembic/env.py
# Regenerar migración
alembic revision --autogenerate -m "fix"
```

### Tests async fallan

```bash
# Verificar pytest-asyncio instalado
pip list | grep pytest-asyncio

# Reinstalar dependencias de testing
uv pip install pytest pytest-asyncio
```

### CORS errors en el navegador

```bash
# Verificar ALLOWED_ORIGINS en .env
# Para desarrollo: ALLOWED_ORIGINS=*
# Para producción: ALLOWED_ORIGINS=https://tu-dominio.com
```

### SQLite lock errors

```bash
# Cerrar cualquier proceso usando la DB
# Eliminar archivo de lock
rm tasalo.db-journal
```

### ElToque API timeout

```bash
# Verificar API key en .env
# Aumentar timeout en el scraper si es necesario
```

---

## 📊 Estado del Proyecto

| Fase | Estado | Tag |
|------|--------|-----|
| Fase 1: Scaffold | ✅ Completada | `v1.0.0-fase1` |
| Fase 2: Scrapers | ✅ Completada | `v1.1.0-fase2` |
| Fase 3: Servicio + Scheduler | ✅ Completada | `v1.2.0-fase3` |
| Fase 4: Endpoints Públicos | ✅ Completada | `v1.3.0-fase4` |
| Fase 5: Endpoints Admin | ✅ Completada | `v1.4.0-fase5` |
| Fase 6: Hardening | ✅ Completada | `v1.5.0-fase6` |

**Progreso Total:** 6/6 fases (100%)

---

## 📝 License

MIT License - ver [LICENSE](LICENSE) para más detalles.

---

## 👥 Contacto

**Organización:** TASALO-TEAM

**Repositorios:**
- [taso-api](https://github.com/tasalo/taso-api)
- [taso-bot](https://github.com/tasalo/taso-bot)
- [taso-miniapp](https://github.com/tasalo/taso-miniapp)
- [taso-extension](https://github.com/tasalo/taso-extension)

**Documentación:**
- [Diseño del Ecosistema](/home/ersus/tasalo/plans/2026-03-21-tasalo-ecosystem-design.md)
- [Diseño taso-api](/home/ersus/tasalo/plans/2026-03-21-tasalo-api-design.md)
