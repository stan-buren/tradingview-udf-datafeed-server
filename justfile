# ─── TradingView UDF Server · Task Runner ───

_default:
    @just --list

# Start development server with hot reload
dev:
    uv run uvicorn src.udf_server.main:app --reload --host 0.0.0.0 --port 8088

# Start production server
serve:
    uv run uvicorn src.udf_server.main:app --host 0.0.0.0 --port 8088 --workers 4

# Sync Binance symbols to local SQLite cache
sync-symbols:
    uv run python -m src.udf_server.cache.symbol_store --sync

# Run test suite with coverage
test:
    uv run pytest --cov=src/udf_server --cov-report=term-missing

# Run a single test file
test-file FILE:
    uv run pytest tests/{{FILE}} -v

# Format code
fmt:
    uv run ruff format src/ tests/

# Lint code
lint:
    uv run ruff check src/ tests/

# Format + lint
check:
    uv run ruff format src/ tests/ && uv run ruff check src/ tests/

# Clean build artifacts
clean:
    rm -rf __pycache__ src/__pycache__ src/**/__pycache__ tests/__pycache__
    rm -rf .ruff_cache .pytest_cache .coverage htmlcov
    rm -rf dist build *.egg-info

# Install systemd service for bare-metal deployment
install-service:
    sudo cp docker/udf-server.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable udf-server
    @echo "Service installed. Start with: sudo systemctl start udf-server"
