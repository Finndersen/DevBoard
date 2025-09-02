# DevBoard Backend - Development Commands

.PHONY: help install dev format lint typecheck test start migrate clean

help:		## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:	## Install development dependencies
	uv sync --extra dev

format:		## Format code with ruff
	ruff format .
	ruff check . --fix

lint:		## Lint code with ruff
	ruff format . --check
	ruff check .
	pyright

typecheck:	## Type-check code with mypy
	pyright

test:		## Run tests
	pytest

start:		## Start development server
	uvicorn devboard.api.main:app --host 0.0.0.0 --port 8000 --reload

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