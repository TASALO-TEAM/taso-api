# TASALO API — Documentación para desarrolladores

API REST pública que agrega tasas de cambio de Cuba en tiempo (casi) real: **ElToque** (mercado informal), **CADECA** y **BCC** (oficiales), **Binance** (cripto P2P) y **Cubanomic** (multi-fuente). Se actualiza automáticamente cada 5 minutos.

Esta guía es para cualquiera que quiera **consumir los datos ya desplegados**, sin necesidad de instalar ni mantener su propia instancia de la API: widgets de escritorio, extensiones de navegador, bots de Telegram, apps de finanzas personales, dashboards, etc.

---

## URL base

```
http://tasalo.duckdns.org:8040
```

Todos los endpoints de este documento son relativos a esa dirección. Ejemplo completo:

```
http://tasalo.duckdns.org:8040/api/v1/tasas/latest
```

## Principios generales

- **No hace falta API key** para leer datos. Los endpoints de tasas, histórico, anuncios e imágenes son de lectura pública.
- **CORS abierto**: se puede llamar directamente desde JavaScript en el navegador, no solo desde un backend.
- **Diseño resiliente**: si no hay datos frescos en el momento de la consulta, la API devuelve automáticamente el último dato histórico disponible en vez de fallar. En la práctica esto significa que casi nunca vas a recibir un error solo porque una fuente externa (ElToque, CADECA, etc.) esté caída momentáneamente.
- **Formato de respuesta consistente** en toda la API:

```json
{
  "ok": true,
  "data": { "...": "..." },
  "updated_at": "2026-07-07T14:00:00Z"
}
```

Los errores siguen el mismo criterio:

```json
{
  "ok": false,
  "error": { "code": 422, "message": "Error de validación", "path": "/api/v1/tasas/history" }
}
```

---

## Endpoints de tasas

| Método | Endpoint | Parámetros | Descripción |
|---|---|---|---|
| GET | `/api/v1/health` | — | Estado de la API y de la base de datos |
| GET | `/api/v1/tasas/latest` | `max_age_minutes` (5–1440, default 120) | Todas las fuentes combinadas: ElToque, CADECA, BCC, Binance |
| GET | `/api/v1/tasas/eltoque` | `max_age_minutes` (5–1440, default 120) | Solo ElToque (mercado informal) |
| GET | `/api/v1/tasas/cadeca` | `max_age_minutes` (5–1440, default 120) | Solo CADECA (oficial, compra/venta) |
| GET | `/api/v1/tasas/bcc` | `max_age_minutes` (5–1440, default 120) | Solo Banco Central de Cuba (oficial) |
| GET | `/api/v1/tasas/fuel` | `max_age_minutes` (1–1440, default 60) | Precios de combustible (mercado informal) |
| GET | `/api/v1/tasas/cubanomic` | `max_age_minutes` (60–2880, default 1440) | USD / EUR / MLC de Cubanomic |
| GET | `/api/v1/tasas/history` | `source`, `currency`, `days` (1–365) | Histórico crudo por fuente y moneda |
| GET | `/api/v1/tasas/history/cubanomic` | `days` (7–730) | Histórico de Cubanomic agrupado por día (USD+EUR+MLC juntos) |
| GET | `/api/v1/tasas/history/local` | `days` (1–730) | Histórico local: promedio diario combinando todas las fuentes |

### `GET /api/v1/tasas/latest`

El endpoint más usado — todas las fuentes en una sola llamada.

```bash
curl "http://tasalo.duckdns.org:8040/api/v1/tasas/latest"
```

```json
{
  "ok": true,
  "data": {
    "eltoque": {
      "USD": { "rate": 365.0, "buy": null, "sell": null, "change": "up", "prev_rate": 360.0 },
      "EUR": { "rate": 398.0, "buy": null, "sell": null, "change": "neutral", "prev_rate": null }
    },
    "cadeca": {
      "USD": { "rate": 120.0, "buy": 115.0, "sell": 120.0, "change": "neutral", "prev_rate": null }
    },
    "bcc": {
      "USD": { "rate": 120.0, "buy": null, "sell": null, "change": "neutral", "prev_rate": null }
    },
    "binance": {}
  },
  "updated_at": "2026-07-07T14:00:00Z"
}
```

**Campos de cada tasa (`CurrencyRate`):**

| Campo | Tipo | Descripción |
|---|---|---|
| `rate` | número | Valor principal a usar en la mayoría de los casos |
| `buy` | número o `null` | Tasa de compra — solo poblada en CADECA y combustible |
| `sell` | número o `null` | Tasa de venta — solo poblada en CADECA y combustible. En CADECA, `rate` == `sell` |
| `change` | `"up"` / `"down"` / `"neutral"` | Dirección respecto al snapshot anterior — listo para pintar flechas 🔺🔻 sin calcularlo vos mismo |
| `prev_rate` | número o `null` | Valor anterior, `null` si aún no hay snapshot previo |

### `GET /api/v1/tasas/eltoque`

Igual formato, sin el wrapper de las 4 fuentes:

```json
{
  "source": "eltoque",
  "rates": {
    "USD": { "rate": 365.0, "buy": null, "sell": null, "change": "up", "prev_rate": 360.0 },
    "EUR": { "rate": 398.0, "buy": null, "sell": null, "change": "neutral", "prev_rate": null }
  },
  "updated_at": "2026-07-07T14:00:00Z"
}
```

### `GET /api/v1/tasas/history?source=eltoque&currency=USD&days=7`

```json
{
  "ok": true,
  "data": [
    { "source": "eltoque", "currency": "USD", "buy_rate": null, "sell_rate": 365.0, "fetched_at": "2026-07-07T12:00:00Z" },
    { "source": "eltoque", "currency": "USD", "buy_rate": null, "sell_rate": 360.0, "fetched_at": "2026-07-06T12:00:00Z" }
  ],
  "count": 2
}
```

Útil para graficar tendencias (7d, 30d...) sin necesidad de mantener tu propio historial.

---

## Endpoints adicionales

| Endpoint | Descripción |
|---|---|
| `GET /api/v1/ads/active` | Lista de anuncios activos del ecosistema TASALO (`id`, `text`, `is_sponsored`, `weight`) |
| `GET /api/v1/ads/random` | Un anuncio activo elegido al azar, ponderado por `weight`. `data` es `null` si no hay ninguno activo (no es un error) |
| `GET /api/v1/year/state` | Progreso del año en curso + frase motivacional del día (feature de comunidad, no relacionada con tasas) |
| `POST /api/v1/images/eltoque/capture` | Fuerza una captura fresca de la imagen del post diario de ElToque. Dispara una acción real cada vez que se llama — evita integrarlo si solo necesitás los números |
| `GET /api/v1/images/eltoque/latest` | Metadata de la última imagen capturada |
| `GET /api/v1/images/eltoque/file/latest` | Descarga el archivo de imagen (binario, `image/png`) |

---

## Ejemplos de código

### Python

```python
import httpx

API_BASE = "http://tasalo.duckdns.org:8040"

def get_latest_rates():
    r = httpx.get(f"{API_BASE}/api/v1/tasas/latest", timeout=10)
    r.raise_for_status()
    return r.json()["data"]

data = get_latest_rates()
print("USD (ElToque):", data["eltoque"]["USD"]["rate"])
```

### JavaScript / Node.js

```javascript
const API_BASE = "http://tasalo.duckdns.org:8040";

async function getLatestRates() {
  const res = await fetch(`${API_BASE}/api/v1/tasas/latest`);
  const json = await res.json();
  return json.data;
}

getLatestRates().then((data) => {
  console.log("USD (ElToque):", data.eltoque.USD.rate);
});
```

### cURL

```bash
# Todas las fuentes
curl "http://tasalo.duckdns.org:8040/api/v1/tasas/latest"

# Solo ElToque, con tolerancia de 30 min de antigüedad
curl "http://tasalo.duckdns.org:8040/api/v1/tasas/eltoque?max_age_minutes=30"

# Histórico de 30 días, ElToque, USD
curl "http://tasalo.duckdns.org:8040/api/v1/tasas/history?source=eltoque&currency=USD&days=30"
```

### PHP

```php
<?php
$response = file_get_contents('http://tasalo.duckdns.org:8040/api/v1/tasas/latest');
$data = json_decode($response, true);
echo "USD (ElToque): " . $data['data']['eltoque']['USD']['rate'];
```

---

## Buenas prácticas de consumo

- **No hace falta consultar más seguido que cada 5 minutos** — es el intervalo de actualización real de la API. Pedir más seguido no trae datos más frescos y solo agrega carga innecesaria.
- **Ajustá `max_age_minutes` según qué tan crítica sea la frescura del dato** para tu caso. El valor por defecto (120 min) es generoso; si tu aplicación calcula montos de dinero, considerá bajarlo (ej. 30 min).
- **Revisá siempre el campo `ok`** antes de asumir que `data` es válido.
- **Aprovechá el campo `change`** en vez de calcular vos mismo si la tasa subió o bajó respecto a la consulta anterior.
- Si tu aplicación necesita reaccionar a cambios de tasa en tiempo real (no solo consultar bajo demanda), lo más simple es un poller cada 5 minutos que compare `change` o el valor de `rate` contra tu última lectura cacheada localmente.

## Manejo de errores

| Código | Cuándo ocurre |
|---|---|
| `422` | Parámetro fuera de rango (ej. `days=1000` cuando el máximo permitido es 365 o 730 según el endpoint) |
| `404` | Recurso no encontrado (ej. pedir una imagen cuando todavía no se capturó ninguna) |
| `500` | Error interno — poco frecuente en los endpoints de tasas gracias al diseño resiliente, pero siempre válido revisar `ok` |

## Limitaciones actuales

- No hay límite de peticiones (*rate limiting*) implementado todavía — se pide usar la API de forma razonable (ver recomendación de polling cada 5 min).
- No existe un esquema formal de versionado más allá del prefijo `/api/v1`. Si el formato de algún campo cambia de forma incompatible en el futuro, se comunicará por los canales del proyecto.

## Lo que no es de acceso público

Estos endpoints existen mas requieren una API key privada (`X-API-Key`) que no se distribuye a terceros — no forman parte de esta guía porque no vas a poder usarlos sin ser parte del equipo de TASALO:

- Endpoints de administración (`/api/v1/admin/*`)
- Alertas de precio de criptomonedas (`/api/v1/alerts/*`)
- Estadísticas internas del bot (`/api/v1/admin/stats/*`)
- Escritura de anuncios y gestión del año (`POST`/`PATCH`/`DELETE` de `/api/v1/ads/*` y `/api/v1/year/*` administrativos)

---

## Contacto

¿Preguntas, ideas o casos de uso que no están cubiertos acá? Abrí un issue en el repositorio de [TASALO-TEAM/taso-api](https://github.com/TASALO-TEAM/taso-api) en GitHub.
