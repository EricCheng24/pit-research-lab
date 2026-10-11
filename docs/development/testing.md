# Testing conventions

Run tests in the installed Python 3.12 environment:

```bash
uv sync --locked --python 3.12
uv run --locked pytest -q -m "not integration"  # make test; make smoke
uv run --locked pytest -q                       # make test-all
uv run --locked pytest --collect-only -q
```

`make check` combines lock validation, Ruff lint/format checks, strict source
mypy, and the fast suite. It propagates failures and does not start services or
rewrite source or the lockfile. Use `make format` separately when intentionally
changing formatting. A zero-test selection is not a passing test run.

## Unit and integration boundaries

Keep pure or self-contained tests in `tests/unit/`, including deterministic CLI
and future contract tests. The current suite checks package import and installed
metadata, CLI help/version, and unknown-option rejection. All four tests are
unit tests; there are no integration tests or integration placeholders.

The registered `integration` marker means a test requires PostgreSQL/containers,
external resources, or cross-component persistence. Add `tests/integration/`
and `@pytest.mark.integration` only when a real implementation needs that
boundary tested. Self-contained tests must not receive the marker arbitrarily.
The fast suite excludes it; the full suite collects everything and will need
the relevant prerequisites once those tests exist. Strict marker enforcement
rejects misspellings and unregistered markers. No database or hosted CI evidence
is supplied by this milestone; F1-3 and F1-4 own those foundations.

## Assertions and isolation

Test observable outcomes: returned values, output, state changes, and explicit
failure behavior. Pair positive cases with meaningful negative inputs. For
example, an unknown CLI option must return a nonzero parser error, name the
rejected option in stderr, and produce no success output. Do not swallow
exceptions, broadly skip/xfail failures, or merely assert that code ran.

Use function-scoped built-ins only where needed. Current CLI tests use
`tmp_path` as their working directory to prove the installed command works
outside the checkout and leaves that directory empty. Subprocesses use a
discovered installed executable, argument arrays, `shell=False`, captured
streams, and a ten-second timeout. Version output is compared with installed
metadata; package metadata is checked against the declared project version.

Use `monkeypatch` for future environment/state changes so pytest restores them
after each test. Add a shared fixture in `tests/conftest.py` only when real reuse
justifies it. Never write test resources into the repository, home, production
directories, Git internals, or provider accounts. Avoid global autouse fixtures,
hidden service startup, network access, secrets, real datasets, background
processes, and dependence on local files or environment values.

## Future research tests

CAP-F2 should test actual domain interfaces using tiny deterministic synthetic
data: delayed disclosure, revisions, and historical snapshots, including
rejection of future information and preservation of earlier snapshots. Keep
event time, availability time, revision identity, and experiment cutoff explicit
so isolation does not erase the experimental semantics. These are future
adversarial cases, not implemented PIT guarantees in F1-2.

CAP-F3 should exercise real hypothesis, protocol, and evidence execution paths.
Choose statistical or numerical tolerances based on the methods being tested.
Do not add speculative business fixtures, arbitrary thresholds, or test plugins
before their owning implementation needs them. Native macOS ARM64 execution and
teammate onboarding evidence remain deferred to F1-5.
