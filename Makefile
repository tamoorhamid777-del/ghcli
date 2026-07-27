# ─────────────────────────────────────────────────────────────────────────────
# ghcli Makefile
# Usage: make <target>
# ─────────────────────────────────────────────────────────────────────────────

PYTHON   ?= python3
PIP      ?= $(PYTHON) -m pip
PACKAGE  := ghcli
SRC_DIR  := ghcli
TEST_DIR := tests

.PHONY: help install install-dev uninstall test test-cov lint format \
        type-check security-check clean build publish

# ── Default target ────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  ghcli — Makefile targets"
	@echo ""
	@echo "  install        Install ghcli in editable mode (pip install -e .)"
	@echo "  install-dev    Install with all dev/test dependencies"
	@echo "  uninstall      Uninstall ghcli"
	@echo "  test           Run the test suite"
	@echo "  test-cov       Run tests with coverage report"
	@echo "  lint           Run flake8 linter"
	@echo "  format         Auto-format with black + isort"
	@echo "  type-check     Run mypy type checker"
	@echo "  security-check Run bandit security scanner"
	@echo "  clean          Remove build artifacts and caches"
	@echo "  build          Build distribution packages (sdist + wheel)"
	@echo "  publish        Upload to PyPI via twine (requires credentials)"
	@echo ""

# ── Installation ──────────────────────────────────────────────────────────────
install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"

uninstall:
	$(PIP) uninstall -y $(PACKAGE)

# ── Testing ───────────────────────────────────────────────────────────────────
test:
	$(PYTHON) -m pytest $(TEST_DIR) -v --tb=short

test-cov:
	$(PYTHON) -m pytest $(TEST_DIR) -v --tb=short \
		--cov=$(SRC_DIR) --cov-report=term-missing --cov-report=html
	@echo "Coverage HTML report: htmlcov/index.html"

# ── Code quality ──────────────────────────────────────────────────────────────
lint:
	$(PYTHON) -m flake8 $(SRC_DIR) $(TEST_DIR) --max-line-length=100 \
		--extend-ignore=E203,W503

format:
	$(PYTHON) -m black $(SRC_DIR) $(TEST_DIR) --line-length=100
	$(PYTHON) -m isort $(SRC_DIR) $(TEST_DIR) --profile=black

type-check:
	$(PYTHON) -m mypy $(SRC_DIR) --ignore-missing-imports

security-check:
	$(PYTHON) -m bandit -r $(SRC_DIR) -ll

# ── Build & publish ───────────────────────────────────────────────────────────
clean:
	rm -rf build dist *.egg-info .eggs htmlcov .coverage .mypy_cache .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

build: clean
	$(PYTHON) -m build

publish: build
	$(PYTHON) -m twine check dist/*
	$(PYTHON) -m twine upload dist/*
