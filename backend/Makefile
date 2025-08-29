# DevBoard Backend - Development Commands

.PHONY: help install dev format lint type-check test start migrate clean

help:		## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:	## Install dependencies
	uv sync

dev:		## Install development dependencies
	uv sync --dev

format:		## Format code with ruff
	uv run ruff format .

lint:		## Lint code with ruff
	uv run ruff check .

type-check:	## Type check with pyright
	uv run pyright

test:		## Run tests
	uv run pytest

start:		## Start development server
	uv run uvicorn devboard.main:app --host 0.0.0.0 --port 8000 --reload

migrate:	## Run database migrations
	mkdir -p data && PYTHONPATH=. uv run alembic upgrade head

migrate-auto:	## Generate new migration
	PYTHONPATH=. uv run alembic revision --autogenerate

clean:		## Clean up generated files
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

all-checks:	## Run all checks (format, lint, type-check, test)
	make format lint type-check test