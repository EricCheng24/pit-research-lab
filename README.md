# PIT Research Lab

PIT Research Lab is an independent foundation for point-in-time (PIT) research
and experimentation. The distribution is `pit-research-lab`; the Python import
package is `pit_research_lab`.

CAP-F1-0 provides packaging, repository hygiene, documentation, and one
standard-library smoke test. There are no research contracts, domain features,
production trading functions, provider credentials, research outcomes, or real
PIT guarantees at this stage. It has no execution dependency on Survivor OS.

## Local setup and verification

Use Python **3.12** and `uv`. From the repository root:

```bash
uv --version
# Only if Python 3.12 is missing:
uv python install 3.12

uv sync --python 3.12
uv run python -c 'import pit_research_lab; print(pit_research_lab.__file__)'
uv run python -m unittest discover -s tests -p 'test_*.py'
uv build
git status --short
git diff --check
```

Python installation and the first build may need internet access to download
Python or the build backend. `uv sync` creates `.venv` and installs the project
in editable mode using the `src/` layout. The smoke test checks the import and
installed distribution metadata. `uv build` produces a source archive and wheel
under `dist/`. Keep `uv.lock` in Git; environments, caches, and build outputs are
ignored. No runtime or test dependencies are needed.

The initial environment targets Windows 11 with WSL2 Ubuntu and native macOS
ARM64, including 8 GB RAM laptops. Use the same Python minor version and uv
workflow on both platforms. This bootstrap needs no database, Docker, Node,
frontend, datasets, or global Python packages beyond uv and Python. Teammate
platform verification and a full onboarding guide are deferred.

## Architecture and milestones

The [architecture overview](docs/architecture/overview.md) describes the future
boundary between generic research infrastructure, finance/quantamental logic,
and TWSE adapters. None of those layers is implemented yet.

The CAP-F1-0 requirements are maintained separately by the
Technical Lead. The following milestones define the planned work:

| Stage | Deferred work |
| --- | --- |
| F1-1 | Ruff, mypy, dependency policy, convenience CLI/Makefile |
| F1-2 | pytest, fixtures, test structure, quality conventions |
| F1-3 | PostgreSQL, Docker Compose, SQLAlchemy, Alembic |
| F1-4 | GitHub Actions, PR policies, branch rules |
| F1-5 / F1-6 | Onboarding/doctor, teammate proof, integrated acceptance |
| F2 / F3 | PIT research foundation / hypothesis laboratory |
| F4+ / F5 / F6 | Finance and TWSE / sequential policies / frontend |

No GitHub CI has been configured or verified. The Technical Lead owns review,
commits, remote configuration, GitHub visibility, and publication.
