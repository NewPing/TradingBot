.PHONY: help install check lint fmt format-check typecheck test test-fast cov up down logs dev web-build web-dev migrate migration

PYTHON ?= uv run python
UV ?= uv

help:
	@echo "ATLAS Makefile Commands:"
	@echo "  make install       - Install dependencies with uv"
	@echo "  make check         - Run full verification (lint + fmt-check + typecheck + test + web-build)"
	@echo "  make lint          - Run Ruff linter"
	@echo "  make fmt           - Format code with Ruff"
	@echo "  make format-check  - Check formatting with Ruff"
	@echo "  make typecheck     - Run Mypy strict type checking"
	@echo "  make test          - Run full pytest test suite"
	@echo "  make test-fast     - Run fast tests"
	@echo "  make cov           - Run tests with coverage"
	@echo "  make web-build     - Build Next.js web application"
	@echo "  make web-dev       - Start Next.js development server (:3000)"
	@echo "  make up            - Start Docker infrastructure"
	@echo "  make down          - Stop Docker infrastructure"
	@echo "  make logs          - Tail Docker logs"
	@echo "  make dev           - Run local API development server (:8001)"

install:
	$(UV) sync --all-extras

check: lint format-check typecheck test web-build

lint:
	$(UV) run ruff check atlas tests

fmt:
	$(UV) run ruff format atlas tests

format-check:
	$(UV) run ruff format --check atlas tests

typecheck:
	$(UV) run mypy atlas tests

test:
	$(UV) run pytest

test-fast:
	$(UV) run pytest -q

cov:
	$(UV) run pytest --cov=atlas --cov-report=term-missing --cov-report=html

web-build:
	npm run --prefix web build

web-dev:
	npm run --prefix web dev

up:
	docker compose -f compose.yml up -d

down:
	docker compose -f compose.yml down

logs:
	docker compose -f compose.yml logs -f

dev:
	$(UV) run uvicorn atlas.api.main:app --reload --host 0.0.0.0 --port 8001

migrate:
	$(UV) run alembic upgrade head
