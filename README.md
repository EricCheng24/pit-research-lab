# PIT Research Lab

PIT Research Lab is an independent foundation for point-in-time (PIT) research
and experimentation. The distribution is `pit-research-lab`; the Python import
package is `pit_research_lab`.

CAP-F1-1 adds development tooling, strict source type checking, and a tiny CLI
to the CAP-F1-0 packaging foundation. CAP-F1-2 adds native pytest smoke tests,
an unknown-argument negative test, and fast/full test commands.
There are no research contracts, domain features,
production trading functions, provider credentials, research outcomes, or real
PIT guarantees at this stage. It has no execution dependency on Survivor OS.

## Local setup and verification

Use Python **3.12** and `uv` on Windows 11 with WSL2 Ubuntu or native macOS
ARM64. If uv is missing, follow its [installation instructions](https://docs.astral.sh/uv/getting-started/installation/)
for your platform. Run these commands in a Unix shell from the repository root;
no manual `.venv` activation is needed:

```bash
uv --version
# Only if Python 3.12 is missing:
uv python install 3.12

uv sync --locked --python 3.12
uv lock --check
uv run --locked ruff check src tests
uv run --locked ruff format --check src tests
uv run --locked mypy src/pit_research_lab
uv run --locked pytest -q -m "not integration"
uv run --locked pytest -q
uv run --locked pytest --collect-only -q
uv run --locked pitlab --help
uv run --locked pitlab --version
uv build
git status --short
git diff --check
```

Python installation, dependency sync, and the first build may need internet
access. `uv sync --locked --python 3.12` creates `.venv`, installs the project in
editable mode using the `src/` layout, and includes the default `dev` dependency
group. Ruff, mypy, and pytest belong only to that group; the package has no runtime
dependencies. Tests use native pytest functions and assertions.

Keep `uv.lock` in Git: uv records exact dependency versions, artifacts, and
hashes there. `--locked` refuses to update a stale lockfile; `uv lock --check`
checks that it agrees with `pyproject.toml`. For intentional tool updates, use
`uv add --dev ruff mypy` or `uv lock --upgrade-package ruff --upgrade-package mypy`
and review both files. Never edit the lockfile by hand. Environments, caches,
and build outputs are ignored. `uv build` produces a source archive and wheel
under `dist/`.

Ruff targets Python 3.12 with a 100-column formatter and checks `src/` and
`tests/`. Rules `E4`, `E7`, `E9`, and `F` catch common syntax and correctness
issues; `I` orders imports, `B` catches likely bugs, and `UP` selects modern
Python idioms. Strict mypy targets Python 3.12 and checks only
`src/pit_research_lab`; tests are linted and executed but are outside the strict
mypy gate. There are no global lint/type suppressions.

The installed `pitlab` console script supports `--help` and `--version`, with
the version read from distribution metadata. It performs no network access,
database work, file mutation, telemetry, or research/domain operations. Smoke
tests check package metadata and invoke the installed CLI, including rejection
of an unknown option. Each CLI test runs in a fresh temporary directory and
asserts that the command creates no files.

The portable POSIX Makefile provides these shortcuts. If `make` is missing on
macOS, use the corresponding direct commands:

| Make target | Direct uv alternative |
| --- | --- |
| `make sync` | `uv sync --locked --python 3.12` |
| `make lock-check` | `uv lock --check` |
| `make lint` | `uv run --locked ruff check src tests` |
| `make format-check` | `uv run --locked ruff format --check src tests` |
| `make format` | `uv run --locked ruff format src tests` |
| `make typecheck` | `uv run --locked mypy src/pit_research_lab` |
| `make test` | `uv run --locked pytest -q -m "not integration"` |
| `make test-all` | `uv run --locked pytest -q` |
| `make smoke` | Compatibility alias to `make test` |
| `make build` | `uv build` |
| `make check` | Run the five lock/lint/format-check/typecheck/fast-test commands below |

The direct equivalent of `make check` is:

```bash
uv lock --check
uv run --locked ruff check src tests
uv run --locked ruff format --check src tests
uv run --locked mypy src/pit_research_lab
uv run --locked pytest -q -m "not integration"
```

`make test` and `make check` exclude the registered `integration` marker and need
no database or Docker. Mark tests as `integration` only when they require
PostgreSQL/containers, external resources, or cross-component persistence;
self-contained CLI tests belong in `tests/unit/`. Unregistered markers fail
collection because `--strict-markers` is enabled. Pytest also reports failure
and collection errors with nonzero exit codes; no collected tests is not success.

`make test-all` runs every currently collected test. CAP-F1-2 has four unit tests
and zero integration tests, so fast and full runs currently execute the same
suite. Future integration tests will require their documented prerequisites
before running the full suite. See the [testing guide](docs/development/testing.md)
for fixture isolation, negative paths, and future synthetic PIT tests.

`make format` intentionally rewrites source/test formatting. `make check` never
calls it; all other quality checks leave tracked code unchanged. Sync installs
the local environment, build writes ignored artifacts, and tools may write
ignored caches.

The environment targets 8 GB RAM laptops. Use the same Python minor version
and uv workflow on both platforms. This foundation needs no database, Docker, Node,
frontend, datasets, or global Python packages beyond uv and Python. Teammate
platform verification and a full onboarding guide are deferred to CAP-F1-5.
The locked tools provide Python 3.12-compatible Linux x86_64 and macOS ARM64
artifacts; native macOS ARM64 execution has not been tested.

## Architecture and milestones

The [architecture overview](docs/architecture/overview.md) describes the future
boundary between generic research infrastructure, finance/quantamental logic,
and TWSE adapters. None of those layers is implemented yet.

The CAP-F1-0, CAP-F1-1, and CAP-F1-2 requirements are maintained separately by the
Technical Lead. The following milestones define the planned work:

| Stage | Deferred work |
| --- | --- |
| F1-3 | PostgreSQL, Docker Compose, SQLAlchemy, Alembic |
| F1-4 | GitHub Actions, PR policies, branch rules |
| F1-5 / F1-6 | Onboarding/doctor, teammate proof, integrated acceptance |
| F2 / F3 | PIT research foundation / hypothesis laboratory |
| F4+ / F5 / F6 | Finance and TWSE / sequential policies / frontend |

No GitHub CI has been configured or verified. The Technical Lead owns review,
commits, remote configuration, GitHub visibility, and publication.
