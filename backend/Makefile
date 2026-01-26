# DevBoard Backend - Development Commands

.PHONY: help install dev format lint typecheck test start migrate clean

help:		## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:	## Install development dependencies & setup dev environment
	env -u PIP_INDEX_URL -u UV_DEFAULT_INDEX uv sync --extra dev --frozen
	pre-commit install

format:		## Format code with ruff
	ruff format .
	ruff check . --fix

lint:		## Lint code with ruff
	ruff format . --check
	ruff check .
	pyright

typecheck:	## Type-check code with pyright
	pyright

test:		## Run tests
	pytest

start:		## Start development server (use BACKEND_PORT=XXXX to override default 8000)
	uvicorn devboard.api.main:app --host 0.0.0.0 --port $${BACKEND_PORT:-8000} --reload --log-level debug

migrate:	## Run database migrations
	mkdir -p data && PYTHONPATH=. alembic upgrade head

migrate-auto:	## Generate new migration
	PYTHONPATH=. alembic revision --autogenerate

clean:		## Clean up generated files
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

all-checks:	## Run all checks (format, lint, type-check, test)
	make format lint type-check test