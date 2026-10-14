# Native Apple Silicon macOS ARM64

Target: a native ARM64 process on Apple Silicon with CPython 3.12 and uv.
**Native Doctor, sync, quality checks and Test PostgreSQL execution are NOT VERIFIED.**
Source branches and ARM64 package artifacts do not prove an end-to-end hardware
run. See the [capability evidence matrix](platform-support.md).

## Access, root and interpreter selection

Confirm permission to access the private
[official repository](https://github.com/EricCheng24/pit-research-lab) and use the
standard Core workflow. In a **native macOS POSIX terminal**, choose a parent
folder. Have the maintainer approve HTTPS or SSH, copy that method's URL from the
repository's **Code** menu and use Git's clone action with that URL. This writes a
checkout and accesses the network; never clone over another folder. Confirm an
existing checkout's identity rather than overwriting it. Follow the
[hub access/root steps](onboarding.md), including the observational Git root query,
and enter the directory containing `pyproject.toml`, `Makefile` and `uv.lock`.
Authentication/root errors require maintainer help, not credential pasting or SSH
configuration/permission repair.

Use native CPython 3.12 on PATH, native uv and Git. Make is optional; GNU Make is
not a prerequisite. Arrange missing tools through the approved platform setup
procedure and the hub's uv installation reference; this is intentional setup, not
Doctor. No package-manager, shell-profile, PATH or Rosetta auto-fix is prescribed.

`doctor.sh` chooses `python3.12`, or `python3` only when `python3.12` is absent.
A broken/wrong-minor preferred interpreter fails without trying another. A
uv-managed Python that is not on PATH is not automatically detected. Installing
Python through uv alone does not establish launcher visibility; stop for reviewed
selection if uncertain.

Doctor's Darwin ARM64 result is a **process signal**, not hardware certification.
Darwin x86_64 does not prove the targeted native ARM64 route; it also does not prove
that every such process is Rosetta. Unsupported/unknown architecture requires
Lead review, not forced emulation, architecture flags or source changes.

## Diagnose, then intentionally synchronize

**Native macOS POSIX shell, repository root.** Run each command separately and
stop on any nonzero exit. First, observational prerequisite diagnosis:

```sh
sh scripts/doctor.sh --profile core
```

Exit 0 permits proceeding to setup, not a claim that tests ran. Optional MAKE WARN
is harmless for the direct route; required FAIL or indeterminate evidence stops.
See the [Doctor reference](environment-doctor.md) for exits 1/2/64 and limitations.

Once the Lead has granted standard Core workflow permission, routine local sync
and checks need no fresh per-command approval. The following **writes `.venv` and
caches and may need network**; it is separate from Doctor and from DB permission:

```sh
uv sync --locked --python 3.12
```

If sync fails, retain manifests and stop; no unlocked retry or dependency upgrade.
No manual environment activation is needed.

## Full Make-free quality route

**Native macOS POSIX shell, repository root, after successful sync.** Run all five
commands **one at a time in order; stop on failure**. This is the complete direct
equivalent of serial `make check`, with no hidden Make step:

```sh
uv lock --check
uv run --locked ruff check src tests scripts migrations
uv run --locked ruff format --check src tests scripts migrations
uv run --locked mypy src/pit_research_lab
uv run --locked pytest -q -m "not integration"
```

uv/tool wrappers can write environment/cache state; pytest uses caches/temporary
fixtures. Lock/lint/format checks do not intentionally rewrite tracked inputs.
mypy covers source only; fast tests exclude real integration and must be nonempty.
No Docker or PostgreSQL is required. Success must be observed per step; the guide
and Doctor PASS are not execution evidence. Use the [hub](onboarding.md) for each
step's expected result, optional installed CLI help/version and `uv build` (writes
`dist/`, may use network/cache).

## Optional Test and safe recovery

In the same shell/root, `sh scripts/doctor.sh --profile test` is passive
**prerequisite-only** diagnosis. A pass proves no DB identity, port ownership,
SQL readiness or guarded runtime. Optional Docker/Compose/local-context setup and
Test use require separate Lead scope; no automatic Desktop setup is implied.
Before DB setup, the Lead assigns a unique checkout namespace and approved,
non-overlapping **Dev/Test port pair**. Follow the [DB manual](database.md) for
the guarded helper and retain both once-created private configs. Dev need not run.
SQL probe, integration, shutdown and destruction remain separately governed.
Do not change the pinned image/Compose policy or introduce emulation flags.

Darwin listener-inspection source exists; its native runtime is NOT VERIFIED.
Missing Python/uv, unsupported architecture, absent Make, lock/sync errors and
command failures use the [hub recovery table](onboarding.md). Missing Docker,
remote/ambiguous context, insecure config metadata or ownership/port/SQL refusal
stop Test; retain files/resources and ask the Lead. No chmod, context switching,
credential copy/paste, pruning or guard bypass. For low RAM/storage, pause work;
8 GB performance is unmeasured, and no swap/VM tuning is prescribed. Native-device
observations and individual adoption remain optional, non-blocking Layers B/C.
