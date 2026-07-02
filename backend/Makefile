# DevBoard Backend - Development Commands

.PHONY: help install dev lint typecheck validate test start migrate migrate-auto migrate-heads migrate-merge clean

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

lint:		## Fix formatting/lint issues with ruff (auto-fixes)
	uv run --frozen --active ruff format .
	uv run --frozen --active ruff check . --fix

typecheck:	## Type-check code with ty
	uv run --frozen --active ty check devboard

test:		## Run tests
	uv run --frozen --active pytest

start:		## Start development server (use BACKEND_PORT=XXXX to override default 8000)
	@lsof -ti :$${BACKEND_PORT:-8000} | xargs kill -9 2>/dev/null || true
	uv run --frozen uvicorn devboard.api.main:app --host 0.0.0.0 --port $${BACKEND_PORT:-8000} --reload --log-level debug

migrate:	## Run database migrations
	uv run --frozen alembic upgrade head

migrate-auto:	## Generate new migration (always run `make migrate` first, see README)
	uv run --frozen alembic revision --autogenerate

migrate-heads:	## Show current migration head(s) - more than one means a merge migration is needed
	uv run --frozen alembic heads

migrate-merge:	## Merge multiple migration heads into one (run after migrate-heads shows >1 head)
	uv run --frozen alembic merge heads -m "merge heads"

clean:		## Clean up generated files
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

validate:	## Run lint and typecheck together
	make lint typecheck
