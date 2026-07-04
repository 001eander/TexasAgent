# TexasAgent — LLM-powered Texas Hold'em poker AI agent
# https://github.com/001eander/TexasAgent

default:
  @just --list

# ── Development ──────────────────────────────────────────────

[group('dev')]
# Install all dependencies
install:
  uv sync
  uv sync --group dev
  uv sync --group poker

[group('dev')]
# Run the FastAPI server in development mode
dev:
  uv run uvicorn app.main:app --reload --port 8000

[group('dev')]
# Run the poker engine in headless simulation mode (no UI, no LLM)
simulate count='100':
  uv run python -m app.simulate --hands {{count}}

# ── Testing ──────────────────────────────────────────────────

[group('test')]
# Run all tests
test *args='':
  uv run pytest {{args}}

[group('test')]
# Run tests with coverage report
test-cov *args='':
  uv run pytest --cov=app --cov-report=term-missing {{args}}

[group('test')]
# Run only poker engine tests
test-engine *args='':
  uv run pytest tests/test_engine/ {{args}}

[group('test')]
# Run tests in watch mode (re-run on changes)
test-watch *args='':
  uv run pytest-watch {{args}}

# ── Code Quality ─────────────────────────────────────────────

[group('lint')]
# Format code with ruff
fmt:
  uv run ruff format app/ tests/

[group('lint')]
# Lint code with ruff
lint:
  uv run ruff check app/ tests/

[group('lint')]
# Fix auto-fixable lint issues
lint-fix:
  uv run ruff check --fix app/ tests/

[group('lint')]
# Type-check with mypy
typecheck:
  uv run mypy app/

[group('lint')]
# Run all quality checks
check: fmt lint typecheck
  @echo "All checks passed ✓"

# ── pi Package ────────────────────────────────────────────────

[group('pi')]
# Install the texas-agent pi package locally for development
pi-install:
  pi install ./pi-package

[group('pi')]
# Test the pi package with an interactive session
pi-dev model='anthropic/claude-sonnet-4-20250514':
  pi -e pi-package/extensions/poker-tools.ts --model {{model}}

[group('pi')]
# Run pi in RPC mode with poker tools loaded
pi-rpc model='anthropic/claude-sonnet-4-20250514':
  pi --mode rpc --no-session -e pi-package/extensions/poker-tools.ts --model {{model}}

# ── Database ──────────────────────────────────────────────────

[group('db')]
# Initialize/recreate the SQLite database
db-init:
  uv run python -c "from app.db.models import init_db; init_db()"

[group('db')]
# Show database statistics
db-stats:
  uv run python -c "from app.db.queries import print_stats; print_stats()"

# ── Cleanup ───────────────────────────────────────────────────

# Remove all generated files
clean:
  rm -rf .venv __pycache__ .pytest_cache .ruff_cache .mypy_cache
  find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
  find . -type f -name '*.pyc' -delete 2>/dev/null || true
  rm -f data/poker.db
  @echo "Cleaned ✓"
