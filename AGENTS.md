# Repository Guidelines

## Project Overview

**TradingView UDF Datafeed Server** — a Python/FastAPI bridge between Binance public market data and TradingView-compatible charts. Implements the TradingView **UDF (Universal Datafeed) protocol**: 6 HTTP REST endpoints that return OHLCV data in columnar JSON format. The frontend demo uses **Lightweight Charts** (Apache 2.0, open-source) — no TradingView license needed.

**Goal**: demonstrate understanding of the UDF protocol spec, real-time WebSocket streaming, and clean protocol-adapter architecture.

## Architecture & Data Flow

```
Binance REST API ──→ Data Adapter ──→ UDF Protocol Router ──→ Lightweight Charts
Binance WebSocket ──→ WS Bridge   ──→ UDF Protocol Router ──→ Static HTML/JS
                      Symbol Cache (SQLite)
```

**Three-layer design:**

| Layer | Location | Responsibility |
|-------|----------|----------------|
| External sources | `adapter/` | Fetch from Binance REST + WebSocket, map to UDF format |
| UDF server | `router/` + `main.py` | Expose 6 UDF endpoints, FastAPI lifespan |
| Frontend demo | `frontend/` | Lightweight Charts widget + JS UDF adapter |

**Request flow (loading a chart):**
1. `GET /config` — chart capabilities
2. `GET /search?query=...` — user searches symbol
3. `GET /symbols?symbol=BTCUSDT` — resolve symbol metadata
4. `GET /history?symbol=BTCUSDT&resolution=60&from=...&to=...` — OHLCV bars
5. WebSocket bridge pushes real-time updates to cached bars

**Backing data source:** Binance public REST API (`api.binance.com/api/v3/klines`) and WebSocket streams (`stream.binance.com/ws/<symbol>@kline_<interval>`). No API key required.

## Key Directories

```
tradingview/
├── src/udf_server/        ← Python package: all server logic
│   ├── main.py            ← FastAPI app entry point + lifespan
│   ├── config.py          ← SSOT config: resolutions, exchanges, limits, timeouts
│   ├── models/            ← Pydantic models (UDF types, LibrarySymbolInfo, Bar)
│   ├── router/            ← 6 UDF endpoint handlers (config, search, symbols, history, time, marks)
│   ├── adapter/           ← Binance → UDF data translation layer
│   │   ├── binance_rest.py   ← REST klines → UDF columnar bars
│   │   ├── binance_ws.py     ← WebSocket stream → in-memory bar cache
│   │   └── resolution.py     ← Resolution mapping (1m→"1", 1h→"60", 1d→"1D")
│   └── cache/
│       ├── symbol_store.py   ← SQLite symbol cache (~2,800 USDT pairs)
│       └── bar_cache.py      ← In-memory rolling bar cache for real-time updates
├── frontend/              ← Static demo served by FastAPI
│   ├── index.html         ← Chart page with symbol search + real-time chart
│   ├── datafeed.js        ← JS UDF adapter: calls our endpoints, feeds Lightweight Charts
│   └── style.css          ← Dark theme
├── data/                  ← SQLite databases (gitignored)
├── docker/                ← Dockerfile + docker-compose.yml + .dockerignore
├── tests/                 ← pytest suite with mock Binance fixtures
├── docs/                  ← Implementation decisions, architecture notes
├── pyproject.toml         ← uv project config + dependencies
├── justfile               ← Task runner: dev, test, sync-symbols, install-service
└── .python-version        ← 3.14
```

## Development Commands

```bash
# Install dependencies
uv sync

# Sync Binance symbols to local SQLite cache (first run ~12s)
just sync-symbols

# Start dev server (UDF: :8080, frontend: :8080/demo)
just dev

# Run test suite with coverage
just test

# Format + lint
just fmt
just lint

# Install as systemd service (for bare-metal continuous operation)
just install-service
```

## Code Conventions & Common Patterns

### Language & Runtime
- **Python 3.14** (target); currently dev on 3.12.3
- **Package manager:** `uv` (pyproject.toml)
- **Task runner:** `just` (justfile)
- **Formatter:** Ruff
- **Linter:** Ruff

### Async Patterns
- All I/O is `async/await` — FastAPI handlers, Binance REST calls (`httpx.AsyncClient`), WebSocket connections (`websockets`)
- `FastAPI.lifespan` context manager handles startup (symbol sync, WS connect) and shutdown (WS disconnect, DB close)
- `asyncio.create_task()` for background WebSocket stream processing

### Error Handling
- UDF protocol mandates `{"s": "error", "errmsg": "..."}` for all errors — never HTTP 500 with tracebacks
- `{"s": "no_data", "nextTime": <unix>}` for gaps (market closed, no data)
- All adapter calls wrapped in try/except → UDF error responses
- Binance HTTP 429/5xx → exponential backoff + retry (3 attempts)

### Models (Pydantic)
- `DatafeedConfiguration` — `/config` response schema
- `LibrarySymbolInfo` — full symbol metadata (pricescale, minmov, session, timezone, etc.)
- `Bar` — single OHLCV candle
- `HistoryResponse` — columnar format: `{s, t[], c[], o[], h[], l[], v[]}`, with `nextTime`
- `SearchResultItem` — symbol search result

### Config (SSOT)
- `config.py` is the single source of truth: supported resolutions, exchange definitions, rate limits, timeouts
- Resolution map: `{"1": "1m", "5": "5m", "15": "15m", "60": "1h", "240": "4h", "1D": "1d", "1W": "1w", "1M": "1M"}`
- Environment variables via `.env` for: `UDF_PORT`, `BINANCE_REST_URL`, `BINANCE_WS_URL`, `SYMBOLS_DB_PATH`

### Adapter Pattern
- Each exchange adapter implements the same interface — currently only Binance, but Bybit/Kraken can be added
- `binance_rest.py`: `async def fetch_klines(symbol, interval, limit) → list[Bar]`
- `resolution.py`: bidirectional mapping between UDF resolution strings and Binance interval strings
- Columnar conversion: Binance `[[t,o,h,l,c,v],...]` → UDF `{t:[], o:[], h:[], l:[], c:[], v:[]}`

### Timestamp Conventions
- Binance returns **milliseconds** (int)
- UDF protocol expects **seconds** (int)
- All internal models store seconds; adapter divides by 1000 on ingest

### Naming Conventions
- Files: `snake_case.py`
- Routes: `{resource}_route.py` (e.g., `history_route.py`)
- Classes: PascalCase (`LibrarySymbolInfo`, `BinanceRestAdapter`)
- Functions: `snake_case` (`fetch_klines`, `resolve_symbol`)
- Model fields match UDF spec exactly: `pricescale`, `minmov`, `has_intraday`, `intraday_multipliers`

### Cache Strategy
- **Symbol cache (SQLite):** populated on startup via `GET /api/v3/exchangeInfo`, read-only at runtime. Indexed on `symbol` column. Refreshed on server restart.
- **Bar cache (in-memory dict):** `{symbol: {resolution: deque[Bar]}}`. WebSocket pushes append to deque; history endpoint reads from it if fresh, else fetches from Binance REST.

## Important Files

| File | Role |
|------|------|
| `src/udf_server/main.py` | FastAPI app, lifespan, static file mount, CORS |
| `src/udf_server/config.py` | All constants: resolutions, exchanges, limits, timeouts |
| `src/udf_server/adapter/resolution.py` | Resolution mapping — critical for correctness |
| `src/udf_server/router/history_route.py` | Most complex endpoint: countback, nextTime, no-data |
| `src/udf_server/cache/symbol_store.py` | SQLite init, upsert, query — server won't work without it |
| `frontend/datafeed.js` | JS UDF adapter — mirrors protocol spec in browser |
| `pyproject.toml` | Dependencies: fastapi, uvicorn, httpx, websockets, aiosqlite, pydantic |
| `justfile` | All runnable commands — the developer entry point |

## Runtime/Tooling Preferences

- **Server:** `uvicorn` with `--reload` in dev; production via `uvicorn` workers or systemd
- **Package install:** `uv sync` — always; never `pip install`
- **Python version:** 3.14 pinned in `.python-version`; uv enforces it
- **Frontend deps:** None — Lightweight Charts loaded from CDN (`unpkg.com/lightweight-charts`)
- **Database:** SQLite via `aiosqlite` (async wrapper); no ORM — raw SQL for speed
- **Container:** Multi-stage Dockerfile (python:3.14-slim), docker-compose for orchestrating server + optional Redis

## Testing & QA

- **Framework:** pytest + pytest-asyncio + pytest-cov
- **Fixtures:** `conftest.py` provides `AsyncClient` (httpx test client), mock Binance responses
- **Test categories:**
  - Route tests: each endpoint with happy path + edge cases (missing params, bad resolution, unknown symbol)
  - Adapter tests: Binance→UDF conversion correctness, resolution mapping
  - Cache tests: SQLite CRUD, bar cache eviction
- **Coverage target:** >80% on `src/udf_server/`
- **Mock strategy:** `unittest.mock.patch` on `httpx.AsyncClient.get` for Binance calls; in-memory SQLite for cache tests
- **Run:** `just test` → `pytest -v --cov=src/udf_server --cov-report=term-missing`
