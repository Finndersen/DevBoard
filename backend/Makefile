# DevBoard Backend - Development Commands

.PHONY: help install dev format lint typecheck test start migrate clean

help:		## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

lock:
	env -u PIP_INDEX_URL -u UV_DEFAULT_INDEX -u UV_INDEX -u UV_EXCLUDE_NEWER uv lock --no-config --index-url https://pypi.org/simple/

install:	## Install development dependencies & setup dev environment
	env -u PIP_INDEX_URL -u UV_DEFAULT_INDEX uv sync --extra dev --frozen
	@if [ -f "$$(git rev-parse --show-toplevel)/.git" ]; then \
		echo "Skipping pre-commit install (git worktree detected)"; \
	else \
		uv run --frozen pre-commit install; \
	fi

format:		## Format code with ruff
	uv run --frozen ruff format .
	uv run --frozen ruff check . --fix

lint:		## Lint code with ruff
	uv run --frozen ruff format . --check
	uv run --frozen ruff check .
	uv run --frozen pyright

typecheck:	## Type-check code with pyright
	uv run --frozen pyright

test:		## Run tests
	uv run --frozen pytest

start:		## Start development server (use BACKEND_PORT=XXXX to override default 8000)
	uv run --frozen uvicorn devboard.api.main:app --host 0.0.0.0 --port $${BACKEND_PORT:-8000} --reload --log-level debug

migrate:	## Run database migrations
	mkdir -p ~/.devboard/data && uv run --frozen alembic upgrade head

migrate-auto:	## Generate new migration
	uv run --frozen alembic revision --autogenerate

clean:		## Clean up generated files
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

all-checks:	## Run all checks (format, lint, type-check, test)
	make format lint typecheck test
