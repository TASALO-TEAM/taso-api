# TASALO API

Backend FastAPI para el ecosistema TASALO. Agrega tasas de cambio del mercado informal cubano (ElToque), CADECA, BCC y Binance, y las expone como API REST.

## Stack Tecnológico

- **Python 3.12+**
- **FastAPI** - Web framework
- **SQLAlchemy (async)** - ORM
- **Alembic** - Migraciones de base de datos
- **pydantic-settings** - Configuración
- **Base de datos:** SQLite (desarrollo) / PostgreSQL (producción)

## Desarrollo Rápido

### 1. Clonar y configurar entorno

```bash
cd taso-api

# Crear entorno virtual con uv
uv venv
source .venv/bin/activate  # Linux/Mac
# o: .venv\Scripts\activate  # Windows

# Instalar dependencias
uv pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus valores
```

### 3. Inicializar base de datos

```bash
# Aplicar migraciones
alembic upgrade head
```

### 4. Correr el servidor

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

La API estará disponible en `http://localhost:8000`

### 5. Verificar funcionamiento

```bash
curl http://localhost:8000/api/v1/health
# Expected: {"ok":true,"version":"1.0.0","db":"connected","database_url":"sqlite"}
```

## Documentación API

Con el servidor corriendo, acceder a:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

## Configuración

Todas las variables de entorno están en `.env.example`:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `DATABASE_URL` | URL de conexión a la base de datos | `sqlite+aiosqlite:///./tasalo.db` |
| `ELTOQUE_API_KEY` | API key para ElToque | (requerido para scrapers) |
| `ELTOQUE_API_URL` | URL de la API de ElToque | `https://tasas.eltoque.com/v1/trmi` |
| `ADMIN_API_KEY` | Clave para endpoints admin | `changeme` |
| `REFRESH_INTERVAL_MINUTES` | Intervalo del scheduler | `5` |
| `ALLOWED_ORIGINS` | Orígenes CORS (separados por coma) | `*` |

### Ejemplo .env para desarrollo

```bash
DATABASE_URL=sqlite+aiosqlite:///./tasalo.db
ELTOQUE_API_KEY=tu_api_key_aqui
ADMIN_API_KEY=dev_secret_123
REFRESH_INTERVAL_MINUTES=5
ALLOWED_ORIGINS=*
```

### Ejemplo .env para producción (PostgreSQL)

```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/tasalo
ELTOQUE_API_KEY=tu_api_key_secreta
ADMIN_API_KEY=produccion_secret_456_xyz
REFRESH_INTERVAL_MINUTES=5
ALLOWED_ORIGINS=https://tasalo.app,https://bot.tasalo.app
```

## Migraciones de Base de Datos

### Crear nueva migración

```bash
alembic revision --autogenerate -m "Descripción del cambio"
```

### Aplicar migraciones

```bash
alembic upgrade head
```

### Revertir migración

```bash
alembic downgrade -1
```

### Ver estado actual

```bash
alembic current
```

## Testing

```bash
# Correr todos los tests
pytest

# Con verbose y coverage
pytest -v --cov=src --cov-report=term-missing
```

## Estructura del Proyecto

```
taso-api/
├── alembic/                 # Migraciones de Alembic
├── docs/
│   └── plans/              # Documentos de diseño y planificación
├── src/
│   ├── main.py             # Punto de entrada FastAPI
│   ├── config.py           # Configuración con pydantic-settings
│   ├── database.py         # Engine y sesiones de SQLAlchemy
│   └── models/             # Modelos ORM
│       ├── rate_snapshot.py
│       └── scheduler_status.py
├── tests/                  # Tests unitarios y de integración
├── .env.example            # Template de variables de entorno
├── requirements.txt        # Dependencias de Python
└── README.md               # Este archivo
```

## Endpoints Disponibles

### Health Check

```
GET /api/v1/health
```

Respuesta:
```json
{
  "ok": true,
  "version": "1.0.0",
  "db": "connected",
  "database_url": "sqlite"
}
```

## Próximas Fases

- **Fase 2:** Implementar scrapers (ElToque, CADECA, BCC, Binance)
- **Fase 3:** Servicio de tasas y scheduler con APScheduler
- **Fase 4:** Endpoints públicos de tasas
- **Fase 5:** Endpoints admin protegidos
- **Fase 6:** Hardening y documentación final

## License

MIT License - ver LICENSE para más detalles.

## Contacto

Organización: TASALO-TEAM
GitHub: https://github.com/tasalo
