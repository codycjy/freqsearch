.PHONY: all install dev test lint fmt clean proto run help

# Python parameters
PYTHON=python3
PIP=$(PYTHON) -m pip
PYTEST=$(PYTHON) -m pytest

all: install

## install: Install package in production mode
install:
	$(PIP) install -e .

## dev: Install package with development dependencies
dev:
	$(PIP) install -e ".[dev,ollama]"

## test: Run tests
test:
	$(PYTEST) tests/ -v

## test-cov: Run tests with coverage
test-cov:
	$(PYTEST) tests/ -v --cov=src/freqsearch --cov-report=html --cov-report=term

## lint: Run linter
lint:
	$(PYTHON) -m ruff check src/ tests/
	$(PYTHON) -m mypy src/

## fmt: Format code
fmt:
	$(PYTHON) -m ruff format src/ tests/
	$(PYTHON) -m ruff check --fix src/ tests/

## clean: Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

## proto: Generate protobuf code
proto:
	@../scripts/generate_proto.sh

## run: Run the agent
run:
	$(PYTHON) -m freqsearch.main

## shell: Start Python shell with package loaded
shell:
	$(PYTHON) -c "from freqsearch import *; import code; code.interact(local=locals())"

## help: Show this help message
help:
	@echo "FreqSearch Python Agent - Available commands:"
	@echo ""
	@sed -n 's/^##//p' $(MAKEFILE_LIST) | column -t -s ':' | sed -e 's/^/ /'

.DEFAULT_GOAL := help
