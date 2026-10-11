.POSIX:

sync:
	uv sync --locked --python 3.12

lock-check:
	uv lock --check

lint:
	uv run --locked ruff check src tests

format-check:
	uv run --locked ruff format --check src tests

format:
	uv run --locked ruff format src tests

typecheck:
	uv run --locked mypy src/pit_research_lab

test:
	uv run --locked pytest -q -m "not integration"

test-all:
	uv run --locked pytest -q

smoke: test

build:
	uv build

check: lock-check lint format-check typecheck test
