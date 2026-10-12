# PostgreSQL persistence foundation

Python stays native; Docker runs only PostgreSQL. Ordinary CLI commands, imports,
`make check` and `make test` need no DB or Docker. Real integration tests require
an explicitly started Test DB. Nothing automatically migrates, starts a service,
resets storage, rotates credentials or repairs an identity mismatch.

## One-time local setup

From this checkout's root, with Python 3.12 and uv installed:

```bash
uv sync --locked --python 3.12
uv run --locked python scripts/database.py setup --namespace capf13
git check-ignore .env.dev.local .env.test.local
```

Choose a unique 1–20 character lowercase alphanumeric namespace beginning with
a letter. `capf13` is an example allocation for this checkout. Another checkout
requires its own explicitly allocated namespace AND port pair. Use setup's
`--dev-port NUMBER --test-port NUMBER` only after the Technical Lead assigns the
pair; never guess free ports. Defaults are dev 55432 and test 55433.

Setup exclusively creates `.env.dev.local` and `.env.test.local` with mode 0600,
different UUID4s and six independent random passwords. It refuses existing files
and prints no secrets. Keep both files private and preserve them with retained
volumes. They are ignored by existing Git rules; `.env.example` is documentation
with unusable placeholders. No setup step runs Docker or initializes a DB.
Interrupted setup may leave one file; retain it and diagnose privately rather
than overwrite it. Setup runs once; **zero configuration exports/copies/edits are
needed in subsequent shells**.

The reader supports UTF-8, unquoted `KEY=VALUE`, blank lines and whole-line `#`
comments only. There is no shell expansion, escaping, `export`, quoting or inline
comment syntax. Missing, duplicated, unknown or malformed keys fail. Selected
files must be operator-owned regular files with exactly mode 0600; symlinks fail.
All ten keys in `.env.example` are required. Passwords use 64 lowercase hex
characters; URLs must exactly match their target, role, password and numeric
loopback endpoint and have no query options.

Every helper and DB Alembic invocation explicitly selects one target and reads
only that file. Ambient `PG*`, `COMPOSE_*` and `PITLAB_*` variables are refused,
including empty values; remove stale exports in your shell. Docker lifecycle
also refuses `DOCKER_*` overrides and remote contexts. There is no fallback or
environment-over-file precedence. The ordinary package/CLI does not read local
files. Native applications can deliberately supply a validated `DatabaseConfig`
object without reading a file. Factory calls also reject ambient routing settings.

## Ports and prerequisites

The pinned multi-platform image in both files is:

```text
postgres:17.11-bookworm@sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826
```

No platform emulation is forced. Published manifest availability is separate from
successful Linux execution and native macOS ARM64 hardware tests (F1-5). Updates
to the patch tag/index digest and uv dependencies require deliberate review and
targeted integration verification. PostgreSQL 17 uses the image's default PGDATA
and a named volume at `/var/lib/postgresql/data`.

Read-only WSL checks:

```bash
docker --version
docker compose version
docker context show
docker info --format '{{.ServerVersion}}'
docker ps --format '{{.Names}} {{.Ports}}'
ss -ltn
```

Windows PowerShell checks (do not change settings):

```powershell
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 55432,55433 }
netsh interface ipv4 show excludedportrange protocol=tcp
netsh interface ipv6 show excludedportrange protocol=tcp
```

On native macOS, the helper uses `netstat -an -p tcp` for listener inspection;
actual macOS execution remains deferred to F1-5.

The WSL helper also invokes `powershell.exe` read-only to check Windows listeners
and reserved ranges. Missing tools, listener-query warnings, unknown range output
or occupied/reserved ports fail closed. Human Windows inspection alone does not
turn an ambiguous helper result into permission to bypass it; report a parser/tool
problem for a targeted fix. A matching running PITLab container with its verified
loopback publication supports idempotent startup; a stopped container does not
authorize reuse of an occupied port. Bind races remain possible and startup errors
are failures. Never change a context, firewall, socket permission or conflicting
service to make these commands pass.

`survivor-postgres` at 127.0.0.1:5432 and all non-PITLab resources are untouchable.
List names/ports only; never inspect their environment, data or credentials, stop
them, or prune Docker. Docker socket permission denied in Codex is a sandbox
limitation, not proof of a failed user WSL2 installation. Do not escalate daemon
access or use `sudo docker`.

## Normal commands and recovery

After initial setup, normal use is:

```bash
make check
make db-up                # optional persistent development DB
make db-test-up           # independent Test DB; dev need not run
make test-all             # fast pass, then mandatory real integration pass
make db-test-destroy      # only explicit guarded test-volume deletion
```

For 8 GB machines, start only the environment needed. Each engine has two pooled
connections, no overflow, a five-second pool/connect timeout, ten-second statement
timeout and five-second lock timeout. Containers use 64 MB shared_buffers,
max_connections=20, 128 MB shm and bounded log rotation. These are initial settings,
not measured memory guarantees. No restart policy makes Test DB always on.

Normal stop/restart recovery retains config, UUID, credentials and volume:

```bash
make db-test-down
make test-all             # MUST fail nonzero; no skip/xfail or automatic startup
make db-test-up
make test-all             # real DB tests must now pass, including repeatable migrations
make test-all             # repeat proves no migration-state reset is required
```

New command processes create fresh engines. A long-lived application that loses
a physical connection receives an error and must roll back. Invalidation or
disposal followed by deliberate reuse creates a newly verified connection. There
is no automatic retry or per-statement/per-checkout identity query.

| Problem / redacted example | Bounded recovery |
| --- | --- |
| `Local target config unavailable` | Perform setup once; retain existing files if storage already exists. |
| `Remove ambient PG*, COMPOSE_* and PITLAB_* settings` | Remove stale exports; rerun with the explicitly selected file. |
| `database authentication rejected` | Check the selected private credentials; changing image env does not rotate an existing volume. |
| `database connection/verification unavailable` | Run preflight; explicitly start/restart only the selected owned DB, then probe. A refused TCP connection alone does not prove a stopped container. |
| `database identity/role/privilege mismatch` | Stop; privately compare namespace/UUID/roles with retained installation config. Never rewrite the comment or reset storage to repair it. |
| `Selected port occupied` / reservation proof ambiguous | Retain every conflicting service; have the Technical Lead resolve the allocation/tool problem. |
| `Resource ownership labels disagree` | Retain resources; inspect only the exact project's labels/mounts, never broaden deletion. |
| unexpected migration revision | Inspect guarded `target=test current`; retain storage and report the exact state. |

No helper dumps DSNs, passwords, SQL parameters, raw driver errors, Docker
environments or rendered secret-bearing Compose JSON. Debug logging, `--showlocals`
and directly printing private config dictionaries are outside the supported safe
diagnostic path. Do not run `docker compose config` with real credentials to stdout.

## Direct equivalents and lifecycle boundary

All helper paths resolve from the script location. Run uv/Make from the checkout
root. These are the safe alternatives when `make` is absent:

| Make | Direct command |
| --- | --- |
| `db-preflight` / `db-test-preflight` | `uv run --locked python scripts/database.py preflight dev` / `preflight test` |
| `db-up` / `db-test-up` | `uv run --locked python scripts/database.py up dev` / `up test` |
| `db-down` / `db-test-down` | `uv run --locked python scripts/database.py down dev` / `down test` |
| `db-probe` / `db-test-probe` | `uv run --locked python scripts/database.py probe dev` / `probe test` |
| `db-test-destroy` | `uv run --locked python scripts/database.py destroy-test` |
| `db-migrate` | `uv run --locked alembic -c alembic.ini -x target=dev upgrade head` |
| `test-all` | `uv run --locked pytest -q -m 'not integration'` then `uv run --locked pytest -q -m integration`; stop on either failure |

The helper constructs a minimal child environment, suppresses captured Docker
output and fixes `docker compose --env-file /dev/null -f <absolute target file>
-p pitlab-<namespace>-<target>`. It validates the **entire resolved model**, including
the exact pinned image/bootstrap mount. Compose version changes that alter the
JSON model fail closed pending a small compatibility fix. Raw Compose with shell
exports is not a supported lifecycle shortcut.

Read-only preflight prints exact owned resource names/IDs before any mutation.
Down retains named storage. Destroy accepts only test and checks project/service,
purpose/namespace/UUID labels, names, exact data/init mounts, loopback publication,
image, networks, all project resources and all volume/network consumers (including
stopped containers). A reachable running DB must also pass its guarded SQL probe.
Unavailable proof refuses all lifecycle operations. Only then may the helper run
the exact test `down --volumes`, without orphan removal. No dev volume deletion
exists. Partial failure prints remaining exact resources when inspectable and
stops without retries. Pre-existing ambiguous resources are never adopted.

Docker Desktop WSL2 may report the bootstrap bind source as
`/run/desktop/mnt/host/wsl/docker-desktop-bind-mounts/<distro>/<64-hex-id>`.
That path shape alone is insufficient ownership proof. After every other resource
and consumer check passes, the helper reads only the exact container's bootstrap
destination with `docker cp ... -` and requires the single regular file's SHA-256
to match the checkout script. The read accepts at most 64 KiB of uncompressed tar,
limits the script to 16 KiB and times out after 15 seconds. It never extracts the
archive, starts a stopped container or persists a receipt. Each inventory requires
fresh proof, including immediately before shutdown/Test deletion; changing opaque
IDs on recreation needs no configuration change. Unavailable mounts, unsupported
path shapes, content changes or ambiguous archives refuse lifecycle operations.
Direct source paths retain their exact-path check. Content identity cannot prove
the host inode of a byte-identical copy; this retains the existing accidental-swap,
rather than malicious-admin, threat boundary.

These checks guard accidental swaps/stale targets, not malicious Docker/admin
operators, copied identity markers/credentials, tampered labels or inspection races.
Do not run lifecycle and integration commands concurrently on one target. Integration
processes take a nonblocking local lock on the selected config file, serializing
migration lifecycle with every other DB test. Parallel test workers are unsupported.

## Persistence API and migrations

```python
from pathlib import Path
from pit_research_lab.infrastructure.database.config import load_config
from pit_research_lab.infrastructure.database.engine import (
    create_database_engine, create_session_factory,
)

config = load_config("dev", Path.cwd())  # deliberate file loading
engine = create_database_engine(config)  # lazy, non-owner runtime role
try:
    sessions = create_session_factory(engine)
    with sessions.begin() as session:
        # Caller owns commit/rollback. Future adapters receive this session
        # and never commit independently.
        pass
finally:
    engine.dispose()  # after all sessions/connections have closed
```

Every new physical connection is checked before SQLAlchemy/application SQL can
use it: database, current/session role, PostgreSQL major 17, protected database
comment `pitlab:<purpose>:<namespace>:<UUID>`, database/schema ownership, negative
role attributes/memberships and effective CONNECT/CREATE/TEMP/USAGE rights. Runtime
also must own no objects. Routine reuse needs no second probe; replacements verify
again. The bootstrap superuser owns DB/comment; migrator owns only `public`, has
no DB CREATE/TEMP or admin membership; app has CONNECT/USAGE, no CREATE/ownership.
PUBLIC DB/schema rights are revoked. Only explicit per-fixture DML is granted.

Alembic has one empty revision `f13_empty_baseline`, with no domain tables. Direct
entry points require exactly one `-x target=dev|test`, the migration role and the
same guarded connection used by Alembic. URL overrides, offline SQL, stamp and dev
downgrade/reset are rejected. `heads` is history-only and needs no target or DB.
No migrations run from startup, bootstrap, healthchecks, probes or fast checks.

```bash
uv run --locked alembic -c alembic.ini -x target=test upgrade head
uv run --locked alembic -c alembic.ini -x target=test current
uv run --locked alembic -c alembic.ini heads
uv run --locked alembic -c alembic.ini -x target=test downgrade base
```

Migration integration tests accept only base or this head, run the full lifecycle,
and restore that starting state. Base may retain the empty Alembic version table.
Failure attempts bounded recovery only from known revisions; if that fails, inspect
`target=test current` and report it. PostgreSQL transaction behavior does not make
every future DDL/failure scenario universally recoverable. Tests allocate only tiny
UUID-named tables, register exact cleanup before allocation, grant only necessary
runtime DML and drop exact names without CASCADE. Process termination can leave
identified test tables; guarded test destruction is the eventual recovery boundary.

## Manual acceptance when Codex cannot access Docker

Run the preflight/normal/recovery/migration sequences above in the Technical Lead's
WSL2 terminal. Collect exit codes and real results. No mock/healthcheck substitutes
for transactions, live privilege checks, marker/role negatives or reconnect tests.
Inspect the approved image's index, then actual selected container/server versions:

```bash
docker buildx imagetools inspect postgres:17.11-bookworm@sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826
make db-test-preflight
make db-test-up
make db-test-probe
make test-all
```

After test stop/restart acceptance, run this controlled **dev** durability probe.
It creates one unique tiny dev table, closes/disposes connections before lifecycle
changes, verifies data across down/up, and deletes only that exact probe. It also
checks test destruction with dev running. Inspect the printed exact resources
before the destroy call; stop on any uncertainty. No real data is read.

```bash
make db-up
make db-test-preflight
uv run --locked python - <<'PY'
from pathlib import Path
from uuid import uuid4
import subprocess
from sqlalchemy import Column, Integer, MetaData, Table, insert, select
from pit_research_lab.infrastructure.database.config import load_config
from pit_research_lab.infrastructure.database.engine import create_database_engine

cfg = load_config("dev", Path.cwd())
table = Table("f13_durability_" + uuid4().hex, MetaData(), Column("id", Integer), schema="public")
def helper(action, target=None):
    args = ["uv", "run", "--locked", "python", "scripts/database.py", action]
    subprocess.run(args + ([target] if target else []), check=True)
def sql(operation):
    engine = create_database_engine(cfg, "migration")
    try:
        with engine.begin() as connection:
            return operation(connection)
    finally:
        engine.dispose()
try:
    def create(connection):
        table.create(connection)
        connection.execute(insert(table).values(id=137))
    sql(create)
    helper("preflight", "dev")  # record dev resource IDs/volume before
    helper("down", "dev")       # retains persistent dev volume
    helper("up", "dev")
    assert sql(lambda c: c.execute(select(table.c.id)).scalar_one()) == 137
    helper("preflight", "dev")  # same volume, recreated dev container expected
    helper("preflight", "test") # inspect exact test resources BEFORE destruction
    helper("destroy-test")       # guarded test-only deletion; never dev
    helper("preflight", "dev")  # dev container/volume IDs unchanged by test deletion
    assert sql(lambda c: c.execute(select(table.c.id)).scalar_one()) == 137
    print("Controlled dev record survived dev down/up and test destruction.")
finally:
    sql(lambda c: table.drop(c, checkfirst=True))  # exact guarded cleanup, no CASCADE
PY
```

Prove cross-environment runtime authentication rejection without sending any SQL.
Explicitly start Test DB again if the durability snippet destroyed it:

```bash
make db-test-up
uv run --locked python - <<'PY'
from pathlib import Path
import psycopg
from pit_research_lab.infrastructure.database.config import load_config
dev, test = (load_config(t, Path.cwd()) for t in ("dev", "test"))
for target, credential in ((dev, test), (test, dev)):
    try:
        connection = psycopg.connect(host="127.0.0.1", port=target.port,
            dbname=target.database, user=credential.role("runtime"),
            password=credential.app_password, connect_timeout=5)
    except psycopg.Error as error:
        assert error.sqlstate in ("28P01", "28000"), "No authentication rejection proof; details redacted"
        print(target.target, "rejects other environment's runtime credential")
    else:
        connection.close()
        raise SystemExit("FAIL: cross-environment credential authenticated; no SQL was sent")
PY
```

Before deletion, also collect only selected PITLab containers' image IDs/architecture,
ports/mounts, server version (`SELECT version()` through guarded engines), and
`docker stats --no-stream` for their exact IDs. For named-volume disk footprint,
`docker exec <verified-PITLab-id> du -sk /var/lib/postgresql/data` is a read-only
size check, never a data dump. Record actual image size with `docker image inspect`
using a size-only format. Do not guess memory/disk usage or inspect unrelated services.
Report native macOS ARM64 as deferred and missing Linux DB evidence as NOT RUN.
