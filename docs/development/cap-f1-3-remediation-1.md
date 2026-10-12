# CAP-F1-3 — Targeted Remediation 1 review

Status: source correction and offline verification; live acceptance pending.
Branch: `feat/cap-f1-3-postgres-persistence`. No commit, push or PR.

The original `verify_resources()` required
`binds[0].get("Source") == str(root / "scripts/init-postgres.sh")`.
Docker Desktop can translate that client path into the observed daemon-side
`/run/desktop/mnt/host/wsl/docker-desktop-bind-mounts/Ubuntu/<opaque-id>`.
The comparison rejects it despite all other supplied inspection fields agreeing.
An empty preflight has no container mount to compare, explaining the observed
success before startup and failure at the post-start inventory.

`inventory()` shares this check across preflight, pre/post-start `up`, and preflight
plus immediate pre-mutation inventory for `down`/`destroy-test`. Both targets are
affected when their source is translated. The SQL-only `probe` path is unaffected.
This confirms the source-level cause against the supplied inspection evidence;
live inspection could not be repeated in Codex.

## Changes and identity boundary

- `scripts/database.py`: keep the exact direct-path check; alternatively require a
  full Desktop path shape (one distribution component and one 64-character lowercase
  hex component) plus fresh bootstrap content proof. Check all existing ownership
  metadata and consumers before attempting this read. `inventory()` supplies the
  verifier; a translated source without a verifier refuses lifecycle operations.
- `docker cp <full-container-id>:/docker-entrypoint-initdb.d/10-pitlab.sh -` reads
  the one mounted script into memory without extraction. A selector bounds the
  transfer to 64 KiB and 15 seconds, killing/reaping the CLI child on failure.
  Stdin/stderr are discarded; errors are redacted. The local reference must be a
  nonempty regular file of at most 16 KiB. The uncompressed archive must contain
  exactly one nonsparse regular `10-pitlab.sh`, with the expected length and SHA-256.
- Preserve project/service/purpose/namespace/instance labels, exact resource names,
  pinned multi-platform image, named data volume, data directory, mount types,
  network identity/consumers, loopback publication and guarded SQL identity checks.
  Require explicit boolean `RW=False` for the bootstrap and `RW=True` for data.
  No source cache, identity receipts, new configuration, credentials or Compose changes.
- `tests/unit/test_database_safety.py`: generalize the existing owned-resource
  fixture to Development and Test without changing the destruction safeguards.
- `tests/unit/test_database_bind_mounts.py`: add deterministic regressions for direct
  and translated paths, running/stopped containers, foreign/unverified sources,
  metadata refusal before content reads, equal-length content substitution,
  malformed/compressed/oversized/link/multiple-member archives, reference-file
  bounds, timeout/access failures and child cleanup. Exercise real inventory and
  lifecycle routing with a simulated CLI: empty preflight followed by translated
  startup, recreation with new IDs, changed source on the same container, and
  fresh proof immediately before Test deletion. Existing Dev deletion refusal
  and running SQL-mismatch deletion refusal remain covered.
- `docs/development/database.md`: document this compatibility and its limits.

Docker documents `docker cp` for running/stopped containers and tar streaming.
Moby's Linux filesystem view sets up the container's declared mounts for archive
reads. These support the selected stopped-container strategy; the installed Docker
Desktop implementation still requires live verification.
Sources: [Docker cp](https://docs.docker.com/reference/cli/docker/container/cp/),
[Moby archive reads](https://github.com/moby/moby/blob/master/daemon/archive_unix.go),
[Moby filesystem view](https://github.com/moby/moby/blob/master/daemon/containerfs_linux.go).

## Verification

Final offline commands (the temporary cache avoids a read-only default uv cache;
offline mode prevents dependency downloads):

```bash
UV_CACHE_DIR=/tmp/cap-f1-3-remediation-1-uv-cache UV_OFFLINE=1 uv run --locked pytest -q tests/unit/test_database_bind_mounts.py tests/unit/test_database_safety.py
UV_CACHE_DIR=/tmp/cap-f1-3-remediation-1-uv-cache UV_OFFLINE=1 make check
git diff --check
```

Focused regressions: **100 passed**. `make check`: lock validation, Ruff lint/format
and mypy passed; **148 passed, 7 integration tests deselected**. `git diff --check`
passed. Both Python blocks below were parsed offline successfully; they were not
executed against Docker.

Docker `info` failed with permission denied at `/var/run/docker.sock`. No escalation,
socket change or live mutation was attempted. Existing Development resources were
preserved. Integration tests and live Desktop mount reads remain unexecuted.

## Human-operated WSL2 verification

Run from the existing WSL2 checkout, without sourcing or printing credentials:

```bash
cd /home/rooki/projects/pit-research-lab
make db-preflight
make db-probe
make db-test-preflight
make db-test-probe
```

Stop on any refusal. Development preflight must now accept the existing translated
source, and the probes must retain the installed database identities.

To verify Development `up` while enforcing preservation of the existing container,
use the actual helper with an invocation-only `--no-recreate` addition. This changes
no source/config file and retains all helper proofs:

```bash
uv run --locked python - <<'PY'
import importlib.util
from pathlib import Path

root = Path.cwd()
spec = importlib.util.spec_from_file_location("database_operator", root / "scripts/database.py")
db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db)
config = db.load_config("dev", root)
env, before = db.preflight(config, root, ports=True)
if len(before[0]) != 1 or len(before[1]) != 1:
    raise SystemExit("Expected existing Development container and volume; stop.")
container_id = before[0][0]["Id"]
volume = before[1][0]
original_run = db.run

def preserve_container(args, *a, **kw):
    if args[:2] == ["docker", "compose"] and "up" in args:
        args = [*args, "--no-recreate"]
    return original_run(args, *a, **kw)

db.run = preserve_container
db.lifecycle("up", config, root)
after = db.inventory(config, root, env)
if after[0][0]["Id"] != container_id or after[1][0] != volume:
    raise SystemExit("Development resource preservation check failed; stop.")
print("Development up verified; existing container and volume preserved.")
PY
```

For an existing running Test container, the following separate WSL2 invocation
checks stopped-container reads and restart without removing either container or
volume. It stops only the positively verified Test container. If stopped preflight
refuses, retain it and report; there is no automatic restart/repair fallback.

```bash
uv run --locked python - <<'PY'
import importlib.util
from pathlib import Path

root = Path.cwd()
spec = importlib.util.spec_from_file_location("database_operator", root / "scripts/database.py")
db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db)
config = db.load_config("test", root)
env, before = db.preflight(config, root, ports=False)
if len(before[0]) != 1 or len(before[1]) != 1:
    raise SystemExit("Expected existing Test container and volume; stop.")
container_id = before[0][0]["Id"]
volume = before[1][0]
db.probe_database(config)
db.run(["docker", "stop", container_id], env, timeout=60)
db.lifecycle("preflight", config, root)
original_run = db.run

def preserve_container(args, *a, **kw):
    if args[:2] == ["docker", "compose"] and "up" in args:
        args = [*args, "--no-recreate"]
    return original_run(args, *a, **kw)

db.run = preserve_container
db.lifecycle("up", config, root)
after = db.inventory(config, root, env)
if after[0][0]["Id"] != container_id or after[1][0] != volume:
    raise SystemExit("Test resource preservation check failed; stop.")
print("Test stopped read/restart verified; existing container and volume preserved.")
PY
```

If the existing Test source is direct, this does not prove a stopped *translated*
read on the installed Desktop daemon. That case, unmodified `make db-up`, actual
recreation with a changing opaque ID, and live Test destruction remain pending
Technical Lead verification on an explicitly disposable Test installation. Offline
regressions cover these branches. No live Development down or volume deletion is
part of this remediation.

## Residual safety limits

Content proof establishes script identity, not the original host inode. A byte-identical
copy at a valid translated source with every ownership field duplicated cannot be
distinguished; the existing boundary excludes malicious Docker/admin actors and
concurrent inspection/mutation races. Modified content, unsupported path layouts,
unreadable/stale translated sources and failed stopped archive reads fail closed.
Desktop versions that cannot archive the stopped mount remain blocked safely.
No claim of CAP-F1-3 completion is made.
