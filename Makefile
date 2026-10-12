.POSIX:

sync:
	uv sync --locked --python 3.12

lock-check:
	uv lock --check

lint:
	uv run --locked ruff check src tests scripts migrations

format-check:
	uv run --locked ruff format --check src tests scripts migrations

format:
	uv run --locked ruff format src tests scripts migrations

typecheck:
	uv run --locked mypy src/pit_research_lab

test:
	uv run --locked pytest -q -m "not integration"

test-all: test
	uv run --locked pytest -q -m integration

smoke: test

build:
	uv build

check: lock-check lint format-check typecheck test

db-preflight:
	uv run --locked python scripts/database.py preflight dev

db-test-preflight:
	uv run --locked python scripts/database.py preflight test

db-up:
	uv run --locked python scripts/database.py up dev

db-test-up:
	uv run --locked python scripts/database.py up test

db-down:
	uv run --locked python scripts/database.py down dev

db-test-down:
	uv run --locked python scripts/database.py down test

db-probe:
	uv run --locked python scripts/database.py probe dev

db-test-probe:
	uv run --locked python scripts/database.py probe test

db-test-destroy:
	uv run --locked python scripts/database.py destroy-test

db-migrate:
	uv run --locked alembic -c alembic.ini -x target=dev upgrade head
