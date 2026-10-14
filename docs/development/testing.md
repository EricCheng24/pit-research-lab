# Testing conventions

Run tests in the installed Python 3.12 environment:

```bash
uv sync --locked --python 3.12
uv run --locked pytest -q -m "not integration"  # make test; make smoke
uv run --locked pytest -q -m integration         # second make test-all pass; Test DB required
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
unit tests, and retain all four original assertions. Additional offline tests
cover configuration, automatic physical-connection verification, lifecycle
ownership, explicit migration routing and mandatory integration selection.
Accepted CAP-F1-5A Doctor tests add deterministic prerequisite/safety coverage;
mocked platform classifiers are **SIMULATED_TEST**, not native-device evidence.

The registered `integration` marker means a test requires PostgreSQL/containers,
external resources, or cross-component persistence. Every real DB module in
`tests/integration/database/` has `pytestmark = pytest.mark.integration`.
Fixtures connect only when a test executes, never during imports/collection.
Self-contained tests must not receive the marker arbitrarily. Strict marker
enforcement rejects misspellings and unregistered markers. Pure collection tests
check the DB taxonomy, empty integration exit 5 and mandatory Make failure propagation.
Accepted historical Ubuntu-hosted **Quality** and real guarded **PostgreSQL
Integration** passed at `9e31d8fe9989a0c13478f50082ca2dfc87d430d4`,
[run 38401011335](https://github.com/EricCheng24/pit-research-lab/actions/runs/38401011335).
This is **HOSTED_LINUX — HISTORICAL** evidence, not a fresh documentation-task
test run or native WSL2/macOS/hardware certification.

`make test-all` runs the fast suite, then a separate mandatory `-m integration`
pass. Either failure propagates; empty integration selection is a failure.
See the [database guide](database.md) for one-time target configuration and
explicit `make db-test-up`. Dev need not run. Missing config, stopped DB, wrong
credentials/identity or failed SQL is a test error, never skip/xfail. Tests do not
start containers or repair storage. To prove recovery, explicitly stop Test DB,
require `make test-all` to fail, restart it, then run the suite twice successfully.

Real DB tests prove effective role rights, wrong marker/role refusals, reconnect,
two-connection commit visibility, fresh-snapshot uncommitted invisibility and
caller-owned Session rollback/commit. UUID-named tiny tables have exact registered
cleanup and explicit DML grants. Cleanup failures fail the run. Integration use is
serialized with a nonblocking lock on the private test config file; parallel
workers and concurrent lifecycle changes against that target are unsupported.
Migration tests accept only base or the independent empty head and restore the
starting revision; unexpected states are retained and reported, never reset.

SQLite/fake connection probes in unit tests test factory/pool behavior only; they
are not evidence of PostgreSQL AC-01/02/03/06/08/09. Real DB acceptance remains
NOT RUN when Docker is inaccessible to Codex. Collection success or a healthy
container alone does not meet that acceptance.

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
contributor adoption remain optional, non-blocking Layer C/B evidence, including
F1-5C/F1-6; no native PASS or contributor completion quorum is required.
