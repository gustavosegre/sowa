# Forja — comandos do monorepo (CLAUDE.md §7). Recipes are plain `cd x && cmd`
# so they run both under sh and under cmd.exe (Windows).
API_PORT ?= 8000
WEB_PORT ?= 5173
API := apps/api
WEB := apps/web

.PHONY: setup dev test e2e lint format types db-migrate build

setup:
	cd $(API) && uv sync
	pnpm install
	cd $(WEB) && pnpm exec playwright install chromium

dev:
	cd $(API) && uv run python ../../scripts/dev.py --api-port $(API_PORT) --web-port $(WEB_PORT)

test:
	cd $(API) && uv run pytest
	cd $(WEB) && pnpm exec vitest run

e2e:
	cd $(WEB) && pnpm exec playwright test

lint:
	cd $(API) && uv run ruff check src tests migrations scripts
	cd $(API) && uv run ruff format --check src tests migrations scripts
	cd $(API) && uv run mypy
	cd $(WEB) && pnpm exec eslint .
	cd $(WEB) && pnpm exec prettier --check "src/**/*.{ts,tsx,css}" "e2e/**/*.ts"
	cd $(WEB) && pnpm exec tsc --noEmit

format:
	cd $(API) && uv run ruff format src tests migrations scripts
	cd $(API) && uv run ruff check --fix src tests migrations scripts
	cd $(WEB) && pnpm exec prettier --write "src/**/*.{ts,tsx,css}" "e2e/**/*.ts"

# Regenerate TS types from the OpenAPI schema (run after changing Pydantic models).
types:
	cd $(API) && uv run python scripts/dump_openapi.py ../web/src/api/generated/openapi.json
	cd $(WEB) && pnpm exec openapi-typescript src/api/generated/openapi.json -o src/api/generated/schema.d.ts

db-migrate:
	cd $(API) && uv run alembic upgrade head

build:
	cd $(WEB) && pnpm exec vite build
