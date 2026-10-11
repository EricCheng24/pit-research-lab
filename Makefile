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

smoke:
	uv run --locked python -m unittest discover -s tests -p 'test_*.py'

build:
	uv build

check: lock-check lint format-check typecheck smoke
