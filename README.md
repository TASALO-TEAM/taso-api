# TASALO API

[![Version](https://img.shields.io/badge/version-0.2.1-blue.svg)](https://github.com/tasalo/taso-api/releases)
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Cuba](https://img.shields.io/badge/made_for-Cuba-0078D4.svg)](https://www.cuba.gob.cu)

---

## 🏗️ Executive Summary

**TASALO API** is a production-ready REST API that aggregates exchange rates from multiple Cuban sources: ElToque (informal market), CADECA, BCC (official rates), and Binance (crypto). Built with **FastAPI** and **PostgreSQL**, it provides real-time currency data with automatic updates every 5 minutes, historical tracking, and change indicators.

**Key Metrics:**
- 📊 **4 data sources** aggregated
- ⏱️ **5-minute** refresh interval
- 📈 **Historical data** tracking
- 🔒 **Admin API** with authentication
- 📝 **Full OpenAPI** documentation

---

## 📋 Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [API Reference](#-api-reference)
- [Code Examples](#-code-examples)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Systemd Service](#-systemd-service-linux)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [Roadmap](#-roadmap)
- [License](#-license)

---

## ✨ Features

### Data Aggregation
| Source | Type | Currencies | Update Frequency |
|--------|------|------------|------------------|
| **ElToque** | Informal market | USD, EUR, MLC | Every 5 min |
| **CADECA** | Official exchange | USD, EUR | Every 5 min |
| **BCC** | Central Bank | USD, EUR | Every 5 min |
| **Binance** | Crypto P2P | USDT, BTC, ETH | Every 5 min |
| **Cubanomic** | Multi-source | USD, EUR, MLC | Daily (00:01 UTC) |

### API Capabilities
- **RESTful Design:** Standard HTTP methods and status codes
- **Change Indicators:** 🔺🔻📊 arrows showing rate movements vs previous snapshot
- **Historical Data:** Query rates from the past 1-365 days
- **Filtering:** Filter by source, currency, and date range
- **Health Checks:** Built-in `/health` endpoint for monitoring

### Production Ready
- **Authentication:** API key protection for admin endpoints
- **CORS:** Configurable cross-origin resource sharing
- **Logging:** Structured JSON logs with configurable levels
- **Error Handling:** Consistent error responses across all endpoints
- **Async/Await:** High-performance non-blocking operations

### Scheduler
- **Automatic Refresh:** Tasas actualizadas automáticamente cada 5 minutos
- **Cubanomic Daily:** Fetch diario a las 00:01 UTC
- **Manual Trigger:** Endpoint admin para refresh manual

---

## 🚀 Quick Start

Get TASALO API running in under 5 minutes:

```bash
# 1. Clone and setup
git clone https://github.com/tasalo/taso-api.git
cd taso-api

# 2. Create virtual environment
uv venv && source .venv/bin/activate

# 3. Install dependencies
uv pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your ElToque API key

# 5. Initialize database
alembic upgrade head

# 6. Start server
uvicorn src.main:app --reload

# 7. Test it!
curl http://localhost:8040/api/v1/health
```

📚 **Interactive API docs:** http://localhost:8040/docs

---

## 📡 API Reference

### Endpoints Overview

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/v1/health` | ❌ | Health check & DB status |
| `GET` | `/api/v1/tasas/latest` | ❌ | Tasas combinadas (ElToque, CADECA, BCC, Binance) |
| `GET` | `/api/v1/tasas/eltoque` | ❌ | Tasas de ElToque |
| `GET` | `/api/v1/tasas/cadeca` | ❌ | Tasas de CADECA (compra/venta) |
| `GET` | `/api/v1/tasas/bcc` | ❌ | Tasas de BCC (oficial) |
| `GET` | `/api/v1/tasas/cubanomic` | ❌ | Tasas de Cubanomic (USD/EUR/MLC) **NUEVO** |
| `GET` | `/api/v1/tasas/history` | ❌ | Histórico (source, currency, days) |
| `GET` | `/api/v1/tasas/history/cubanomic` | ❌ | Histórico Cubanomic (7d-2y) **NUEVO** |
| `GET` | `/api/v1/tasas/history/local` | ❌ | Histórico local (1d-2y) **NUEVO** |
| `POST` | `/api/v1/images/eltoque/capture` | ❌ | Capturar imagen ElToque **NUEVO** |
| `GET` | `/api/v1/images/eltoque/latest` | ❌ | Última imagen capturada **NUEVO** |
| `GET` | `/api/v1/images/eltoque/{date}` | ❌ | Imagen por fecha (YYYY-MM-DD) **NUEVO** |
| `GET` | `/api/v1/images/eltoque/file/latest` | ❌ | Descargar archivo de imagen **NUEVO** |
| `GET` | `/api/v1/images/alerts/{user_id}` | ❌ | Obtener alerta de usuario **NUEVO** |
| `POST` | `/api/v1/images/alerts` | ❌ | Crear/actualizar alerta **NUEVO** |
| `DELETE` | `/api/v1/images/alerts/{user_id}` | ❌ | Eliminar alerta **NUEVO** |
| `POST` | `/api/v1/images/alerts/{user_id}/disable` | ❌ | Desactivar alerta **NUEVO** |
| `GET` | `/api/v1/images/alerts` | ❌ | Obtener alertas activas **NUEVO** |
| `GET` | `/api/v1/admin/status` | ✅ | Scheduler status |
| `POST` | `/api/v1/admin/refresh` | ✅ | Trigger manual refresh | |

### Authentication

Admin endpoints require the `X-API-Key` header:

```bash
curl http://localhost:8040/api/v1/admin/status \
  -H "X-API-Key: your_secret_admin_key"
```

### Response Format

All responses follow a consistent structure:

```json
{
  "ok": true,
  "data": {
    "eltoque": {
      "USD": {
        "rate": 365.50,
        "change": "up",
        "prev_rate": 364.00
      }
    }
  },
  "updated_at": "2026-03-23T04:15:00Z"
}
```

---

## 💻 Code Examples

### Python

```python
import httpx

async def get_latest_rates():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8040/api/v1/tasas/latest"
        )
        data = response.json()
        usd_rate = data["data"]["eltoque"]["USD"]["rate"]
        print(f"USD Rate: {usd_rate}")
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

async function getLatestRates() {
    const response = await axios.get(
        'http://localhost:8040/api/v1/tasas/latest'
    );
    console.log('USD Rate:', response.data.data.eltoque.USD.rate);
}

// Using Fetch API
async function getRates() {
    const res = await fetch('http://localhost:8040/api/v1/tasas/latest');
    const data = await res.json();
    return data;
}
```

### cURL

```bash
# Get latest rates
curl http://localhost:8040/api/v1/tasas/latest

# Get historical data (last 7 days, USD from ElToque)
curl "http://localhost:8040/api/v1/tasas/history?source=eltoque&currency=USD&days=7"

# Admin: Trigger manual refresh
curl -X POST http://localhost:8040/api/v1/admin/refresh \
  -H "X-API-Key: your_admin_key"
```

### PHP

```php
<?php
$response = file_get_contents('http://localhost:8040/api/v1/tasas/latest');
$data = json_decode($response, true);
echo "USD Rate: " . $data['data']['eltoque']['USD']['rate'];
?>
```

### Go

```go
package main

import (
    "encoding/json"
    "fmt"
    "net/http"
)

type RateResponse struct {
    Data struct {
        Eltoque struct {
            USD struct {
                Rate float64 `json:"rate"`
            } `json:"USD"`
        } `json:"eltoque"`
    } `json:"data"`
}

func main() {
    resp, _ := http.Get("http://localhost:8040/api/v1/tasas/latest")
    var data RateResponse
    json.NewDecoder(resp.Body).Decode(&data)
    fmt.Printf("USD Rate: %f\n", data.Data.Eltoque.USD.Rate)
}
```

---

## 📦 Installation

### Prerequisites

- **Python:** 3.13 or higher
- **uv:** Recommended package manager
- **PostgreSQL:** 14+ (for production)

### Step-by-Step

```bash
# 1. Clone repository
git clone https://github.com/tasalo/taso-api.git
cd taso-api

# 2. Create virtual environment
uv venv
source .venv/bin/activate  # Linux/Mac

# 3. Install dependencies
uv pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your settings

# 5. Initialize database
alembic upgrade head

# 6. Run tests (optional)
pytest -v

# 7. Start server
uvicorn src.main:app --reload
```

---

## ⚙️ Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./tasalo.db` | ✅ |
| `ELTOQUE_API_KEY` | ElToque API key | - | ✅ |
| `ELTOQUE_API_URL` | ElToque API endpoint | `https://tasas.eltoque.com/v1/trmi` | ✅ |
| `ADMIN_API_KEY` | Admin API authentication key | - | ✅ |
| `REFRESH_INTERVAL_MINUTES` | Scheduler refresh interval | `5` | ✅ |
| `ALLOWED_ORIGINS` | CORS allowed origins | `*` | ✅ |
| `PORT` | Server port | `8040` | ❌ |

### Generate Secure API Keys

```bash
# Generate secure admin API key
openssl rand -hex 32
```

---

## 🗄️ Redis Configuration

Redis se usa para cachear datos de Cubanomic y reducir la carga en la API externa.

### Configuración

```ini
REDIS_URL=redis://localhost:6379/0
REDIS_TTL_CUBANOMIC=86400  # 24 horas (cache latest)
```

### Instalación

```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl enable redis
sudo systemctl start redis

# Verify
redis-cli ping  # Should return: PONG
```

### Cachés

| Endpoint | TTL | Descripción |
|----------|-----|-------------|
| `/api/v1/tasas/cubanomic` | 24h | Tasas actuales |
| `/api/v1/tasas/history/cubanomic?days=X` | 1h | Histórico por rango de días |
| `/api/v1/tasas/history/local?days=X` | — | Histórico local (sin cache) |

---

## 📊 Local History System

The local history endpoint provides historical rate data collected automatically from the 5-minute refresh cycles.

**Endpoint:** `GET /api/v1/tasas/history/local`

**Query Parameters:**
- `days` (optional): Number of days of history (1-730). Default: 1.

**Response Format:**
```json
{
  "ok": true,
  "data": [
    {
      "fetched_at": "2026-03-29T00:00:00Z",
      "usd_rate": 517.26,
      "eur_rate": 582.36,
      "mlc_rate": 394.82
    }
  ],
  "count": 1,
  "source": "local"
}
```

**Notes:**
- Data is automatically collected every 5 minutes from the existing refresh job
- Rates are daily averages from all available sources (ElToque, CADECA, BCC)
- Starts with 1 day of data, expands as data accumulates
- No caching - always returns fresh data from database

---

## ⏰ Scheduler

### Jobs Programados

| Job | Frecuencia | Hora | Descripción |
|-----|------------|------|-------------|
| `refresh_all` | Cada 5 min | — | Refresca tasas de ElToque, CADECA, BCC, Binance |
| `cubanomic_daily` | Diario | 00:01 UTC | Fetch de Cubanomic (USD/EUR/MLC) |

### Ver Status

```bash
# Ver status del scheduler
curl http://localhost:8040/api/v1/admin/status \
  -H "X-API-Key: your_admin_key"

# Trigger refresh manual
curl -X POST http://localhost:8040/api/v1/admin/refresh \
  -H "X-API-Key: your_admin_key"
```

---

## 🔧 Systemd Service (Linux)

Run TASALO API as a background service with automatic restart:

### Installation

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
ExecStart=/opt/taso-api/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8040
Restart=always

[Install]
WantedBy=multi-user.target
```

### Enable and Start

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable taso-api
sudo systemctl start taso-api

# Check status
sudo systemctl status taso-api

# View logs
sudo journalctl -u taso-api -f
```

---

## 🔧 Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `aiosqlite` install fails | Python < 3.13 | Upgrade to Python 3.13+ |
| CORS errors | Wrong `ALLOWED_ORIGINS` | Set to your frontend domain |
| ElToque timeout | Invalid API key | Regenerate key at eltoque.com |
| SQLite lock | Multiple processes | Close other connections |

### Debug Mode

Enable detailed logging in `.env`:

```bash
LOG_LEVEL=DEBUG
```

### Health Diagnostics

```bash
# Check API health
curl http://localhost:8040/api/v1/health

# Test individual scrapers
python scripts/test_scrapers_manual.py
```

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Quick Start for Contributors

```bash
# 1. Fork the repository
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/taso-api.git

# 3. Create a branch
git checkout -b feature/your-feature-name

# 4. Make changes and test
pytest -v --cov=src

# 5. Submit a pull request
```

### Development Requirements

- **Python:** 3.13+
- **Testing:** `pytest`, `pytest-asyncio`, `pytest-cov`
- **Linting:** `ruff`, `black`, `mypy`

---

## 🗺️ Roadmap

### Q2 2026
- [ ] Email alerts for rate thresholds
- [ ] WebSocket support for real-time updates
- [ ] GraphQL API endpoint
- [ ] Rate comparison charts endpoint

### Q3 2026
- [ ] Mobile SDK (React Native, Flutter)
- [ ] Webhook notifications
- [ ] Multi-language API responses
- [ ] Advanced analytics endpoint

**Have ideas?** [Submit a feature request](https://github.com/tasalo/taso-api/issues/new)

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

### What This Means

✅ **You can:**
- Use commercially
- Modify and distribute
- Use privately

⚠️ **You must:**
- Include copyright notice
- Include license text

---

## 🌟 Community

### Connect with Us

- **GitHub:** [tasalo/taso-api](https://github.com/tasalo/taso-api)
- **Discussions:** [GitHub Discussions](https://github.com/tasalo/taso-api/discussions)
- **Issues:** [Bug Reports](https://github.com/tasalo/taso-api/issues)
- **Email:** hello@tasalo.app

### Related Projects

| Project | Description |
|---------|-------------|
| [taso-bot](https://github.com/tasalo/taso-bot) | Telegram bot for rate alerts |
| [taso-miniapp](https://github.com/tasalo/taso-miniapp) | Telegram Mini App UI |
| [taso-extension](https://github.com/tasalo/taso-extension) | Browser extension |

---

**Made with ❤️ for Cuba** 🇨🇺
