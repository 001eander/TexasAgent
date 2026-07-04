# TexasAgent — LLM-powered Texas Hold'em poker AI agent
# https://github.com/001eander/TexasAgent

default:
  @just --list

# ── Development ──────────────────────────────────────────────

# Install all dependencies
install:
  uv sync
  uv sync --group dev

# Run the FastAPI server in development mode
dev:
  uv run uvicorn app.main:app --reload --port 8000

# Run the poker engine in headless simulation mode (no UI, no LLM)
simulate count='100':
  uv run python -m app.simulate --hands {{count}}

# ── Testing ──────────────────────────────────────────────────

# Run all tests
test *args='':
  uv run pytest {{args}}

# Run tests with coverage report
test-cov *args='':
  uv run pytest --cov=app --cov-report=term-missing {{args}}

# Run only poker engine tests
test-engine *args='':
  uv run pytest tests/test_engine/ {{args}}

# ── Code Quality ─────────────────────────────────────────────

# Format code with ruff
fmt:
  uv run ruff format app/ tests/

# Lint code with ruff
lint:
  uv run ruff check app/ tests/

# Fix auto-fixable lint issues
lint-fix:
  uv run ruff check --fix app/ tests/

# Type-check with mypy
typecheck:
  uv run mypy app/

# Run all quality checks
check: fmt lint typecheck
  @echo "All checks passed ✓"

# ── pi Package ────────────────────────────────────────────────

# Install the texas-agent pi package locally for development
pi-install:
  pi install ./pi-package

# Test the pi package with an interactive session
pi-dev model='anthropic/claude-sonnet-4-20250514':
  pi -e pi-package/extensions/poker-tools.ts --model {{model}}

# Run pi in RPC mode with poker tools loaded
pi-rpc model='anthropic/claude-sonnet-4-20250514':
  pi --mode rpc --no-session -e pi-package/extensions/poker-tools.ts --model {{model}}

# ── Cleanup ───────────────────────────────────────────────────

# Remove all generated files
clean:
  rm -rf .venv __pycache__ .pytest_cache .ruff_cache .mypy_cache
  find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
  find . -type f -name '*.pyc' -delete 2>/dev/null || true
  rm -f data/poker.db
  @echo "Cleaned ✓"
