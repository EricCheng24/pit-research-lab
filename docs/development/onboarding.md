# First checkout: Docker-free onboarding

This guide is for a new contributor getting from a permitted checkout to local
quality checks. The distribution is `pit-research-lab`; Python imports use
`pit_research_lab`. This is a standalone engineering foundation with no Survivor OS
runtime dependency and no implemented PIT research guarantees.

Choose the [WSL2 Ubuntu path](onboarding-wsl2.md) or
[native macOS ARM64 path](onboarding-macos-arm64.md) for shell and interpreter
guidance. Both are targeted workflows; see the
[platform evidence and lightweight guidance](platform-support.md) for what has
actually been verified. Commands below are reference workflows, not execution
evidence. Run **one command at a time and stop on any nonzero exit**.

## 1. Get access and find your checkout

The official repository is the private
[EricCheng24/pit-research-lab repository](https://github.com/EricCheng24/pit-research-lab).
Confirm with the Technical Lead that your account has repository access and that
you may use the standard Core onboarding workflow. Sign in through your team's
approved GitHub procedure; inability to view the repository is a reason to stop,
not evidence that it is public or missing.

For a new checkout, agree on **HTTPS or SSH** with an authorized maintainer first.
On the repository page, use **Code** to obtain the clone URL for that approved
method. In the platform's terminal, choose a parent directory for your work.
Once the URL and method are approved, run `git clone` followed by that URL as its
single argument. Cloning accesses the network
and writes a new checkout to disk; it is separate from Doctor. No transport is
selected by this guide, so there is no unconditional clone command to paste.
Do not clone over an existing directory. If you already have a checkout, have the
maintainer confirm it belongs to this repository rather than creating another.
Authentication failures require maintainer help; never paste credentials, repair
SSH permissions, use elevated privileges or rewrite Git history to get access.

Open the resulting checkout folder in your platform's terminal. **Repository root**
means the directory containing `pyproject.toml`, `Makefile` and `uv.lock`.
From inside the checkout, this source-backed Git query is observational:

**Ubuntu/WSL or native macOS POSIX shell; inside the approved checkout:**

```sh
git --no-optional-locks -c core.fsmonitor=false rev-parse --show-toplevel
```

It prints a local root path. Enter that directory before the following steps;
keep the path private. This proves Git's local root, not remote ownership or an
approved revision. If Git is missing, the query fails, the folder is unexpected,
or the checkout has unexplained changes, retain it and ask the maintainer. Do not
reset, clean, pull or switch branches as an automatic repair.

## 2. Confirm tools on the correct platform

You need a POSIX shell, **CPython 3.12 on PATH**, uv and Git. Make is optional.
On WSL2, these tools belong inside Ubuntu; Windows-installed Python/uv do not
establish Linux prerequisites. On Apple Silicon use the native ARM64 process path.
No Docker, Node, frontend, CUDA/PyTorch, datasets or provider credentials are needed
for Core.

If a tool is absent, arrange its installation or selection through the team's
approved setup procedure. The existing
[uv installation reference](https://docs.astral.sh/uv/getting-started/installation/)
describes platform choices; installation is an intentional write/network action,
not diagnosis. External links were not visited during this package's static review.
No project minimum uv/Git release is asserted. CI's uv version is a reference,
not a local minimum.

Doctor prefers `python3.12`, then `python3` only if the former is absent. A broken
or incompatible preferred interpreter fails without fallback. A uv-managed Python
outside PATH is not automatically discovered; installation alone does not prove
Doctor can find it. Ask for reviewed interpreter selection rather than editing
PATH or shell profiles automatically.

## 3. Diagnose before synchronization

**Ubuntu/WSL or native macOS POSIX shell; repository root; observational:**

```sh
sh scripts/doctor.sh --profile core
```

Doctor uses Python's standard library without application dependencies. It does
not install, synchronize, build, repair, start services, read private config
contents or invoke **any** DB helper action, including `preflight`.

| Exit / output | Meaning and safe next action |
| --- | --- |
| `0`, Core prerequisites satisfied | Required prerequisites passed; optional warnings are allowed. Proceed to intentional Core setup. |
| `WARN MAKE` | Make is optional; use all five direct uv commands below. |
| `1` | A required check failed, even if another is `NOT CHECKED`. Stop and resolve the named prerequisite. |
| `2` | Required evidence is indeterminate without a required FAIL. Stop for Lead review. |
| `64` | Invalid invocation; review the command spelling. No probes run. |
| `NOT CHECKED DB_RUNTIME` | Always excluded: no PostgreSQL identity, SQL, ownership, port or health proof. |

Checks omitted by Core do not invalidate Core. Required unknown evidence cannot
stand in for PASS. Read the [Doctor reference](environment-doctor.md) for full
profiles, redaction and limitations. A Doctor PASS proves prerequisites only;
it proves neither locked synchronization nor successful tests.

## 4. Intentionally install the local Core environment

Once the Lead grants your contributor/repository access **and use of the standard
Core workflow**, normal Docker-free sync and quality checks are routine permitted
onboarding. You do not need a new approval for each Core command. This permission
does not include DB work, dependency upgrades or workstation repair.

**Ubuntu/WSL or native macOS POSIX shell; repository root; intentional local writes:**

```sh
uv sync --locked --python 3.12
```

Successful sync creates/updates `.venv`, installs the project in editable mode and
includes the default dev tools. It may access the network and write caches. It
preserves the locked dependency contract; no manual `.venv` activation is needed.
If offline access, interpreter selection, storage or lock agreement fails, stop.
Keep `pyproject.toml` and `uv.lock` unchanged; do not use an unlocked sync or upgrade
dependencies to make setup pass.

## 5. Run Docker-free quality checks

After successful sync, choose **one** route. All commands use the same platform's
POSIX shell and repository root. uv may synchronize environments or write caches;
pytest also uses temporary fixtures/caches. These are intentional local effects,
even when checking code. They do not intentionally rewrite tracked source.

With Make available, run serially, without parallel or failure-ignoring options:

```sh
make check
```

Without Make, run these **five commands in order**, individually, stopping on the
first nonzero exit. This is the complete equivalent of serial `make check`:

```sh
uv lock --check
uv run --locked ruff check src tests scripts migrations
uv run --locked ruff format --check src tests scripts migrations
uv run --locked mypy src/pit_research_lab
uv run --locked pytest -q -m "not integration"
```

| Step | What success establishes |
| --- | --- |
| Lock check | Project metadata agrees with the lockfile; no lock update is requested. |
| Ruff check | Lint passes for `src`, `tests`, `scripts` and `migrations`. |
| Ruff format check | Formatting matches; formatting is not applied. |
| mypy | Strict types pass for `src/pit_research_lab` only. |
| Fast pytest | The non-integration suite passes and is nonempty. |

Core setup/checks are successful only after sync and every quality step actually
passes. No Docker or live DB is needed, and a fast pass proves no DB readiness.
`make check` includes neither build nor integration tests. The
[Makefile](../../Makefile) and [testing conventions](testing.md) define this gate.

## 6. Optional CLI and build checks

After successful sync, in the same POSIX shell/root, run any selected step
individually and stop on failure:

```sh
uv run --locked pitlab --help
uv run --locked pitlab --version
uv build
```

The installed CLI needs project distribution metadata; help/version themselves
perform no DB/network/file work. The uv wrapper can write environments/caches.
Build needs its backend and artifacts, may need network/cache access, and writes
the source archive and wheel to `dist/`. These are optional smoke/build steps,
not extra criteria for finishing the Core onboarding route. Doctor PASS is not
their execution evidence.

## 7. Optional Test PostgreSQL: a separate operator track

You can finish initial Core onboarding without Docker or Test configuration.
In the same POSIX shell/root, `sh scripts/doctor.sh --profile test` diagnoses
**prerequisites only**: Docker/Compose v2/local-context/daemon signals, routing-name
presence and `.env.test.local` metadata. It never opens config contents or proves
DB identity, ownership, port availability, SQL or health. Missing config on a fresh
checkout can fail Test while Core passes. Test PASS never grants operator approval.

Before provisioning or operating Test, obtain **separate action-scoped Lead
permission** for this checkout, its unique namespace and non-overlapping approved
**Dev/Test port pair**. Follow the [guarded DB manual](database.md) and
[contribution DB boundary](contributing.md). Their sample namespace/default ports
are not allocations for your checkout. Setup creates **both** private config files
once, even for Test-only work, and refuses overwrite. Retain existing or partial
files; never copy another checkout's identity or share config contents.

The following are helper action names, not a newcomer command block. Each needs
its own approved scope, synchronized environment and selected checkout identity:

| Helper action / test selection | Effect, success and stop boundary |
| --- | --- |
| `setup` | Writes two exclusive private files; no DB starts. Requires assigned namespace and both ports. Existing/partial files: retain and stop. |
| `preflight test` | Observational **but private** operator validation of model/resources/ports; reads selected config and prints identities. Not Doctor or complete SQL readiness. Refusal: retain resources. |
| `up test` | Starts guarded Test resources, waits and probes SQL. Explicit lifecycle approval; any guard/start failure stops. |
| `probe test` | Guarded SQL observation using private config; separate permission. Identity/SQL error stops. |
| `make test-all` | Fast tests, then mandatory nonempty real PostgreSQL integration; writes test DB state/caches. Separately authorized Test must already be started. No skip or automatic startup. |
| `down test` | Guarded shutdown retaining storage/config; separate shutdown permission. Ownership uncertainty stops. |
| `destroy-test` | Destructive guarded Test-only volume removal; separate explicit destruction permission. Never routine onboarding cleanup. |

uv operator wrappers can also write environments/caches. Run lifecycle and tests
serially; Dev need not run. Never bypass guards with bare Compose, guessed ports,
copied credentials, forced deletion or a context change. Link the DB manual for
exact signatures and recovery rather than treating its lifecycle examples as
permission to execute them.

## 8. Recover safely

| Problem | Safe next action |
| --- | --- |
| Python missing/wrong minor/not on PATH, or uv/Git missing | Stop before sync; arrange reviewed tool installation/selection. |
| Make absent | Use all five direct uv steps; no Make installation required. |
| Wrong checkout or unexplained changes | Retain work and ask the maintainer; do not reset/clean. |
| Unsupported/unknown process architecture | Stop for native interpreter selection review; no emulation or automatic profile edits. |
| Offline sync, lock mismatch, lint/type/test/CLI/build error | Stop at the first failed command; share a redacted command/exit/error category. Preserve manifests; no automatic repair. |
| Docker/Compose/daemon missing or denied, remote/ambiguous context | Core remains independent; stop Test and ask the Lead. No socket repair or context switching. |
| Test config missing, symlink, wrong UID/mode/type or inaccessible metadata | Retain files/resources; ask for separately approved setup or private diagnosis. No chmod/overwrite. |
| PG*, COMPOSE_*, PITLAB_* or DOCKER_* routing overrides | Stop Test and have the Lead review shell state separately; even empty exports matter. Share families, never values or an environment dump. |
| Port/ownership/SQL refusal | Retain every conflicting resource and stop; Doctor cannot override a guard. |
| Low RAM/storage, memory pressure or terminated command | Pause new work and report the mode/safe symptom; no pruning, swap/VM tuning or guessed resource guarantee. |

Do not request or paste passwords, tokens, DSNs, private user paths, raw Compose
JSON, Docker environments or whole logs. Do not use sudo/chmod, forced cleanup,
automatic SSH fixes or unrelated-resource operations as recovery instructions.

## 9. Contribute and record only what happened

For a separately authorized change, follow the [contributor guide](contributing.md):
scoped feature branch → PR → latest **Quality** and **PostgreSQL Integration**
completed/success → human review and separately permitted merge. The template is
guidance, not protection; historical settings observations are not continuous
certification. Initial setup grants no Git transport or merge authority.

Use the optional [adoption and platform record templates](platform-support.md).
Record actual commands, exits and nonsecret issues; source inspection and mocked
Doctor tests are not native platform success. Layers B/C remain non-blocking for
F1-5C/F1-6, with no contributor completion quorum, unless a real mandatory safety
or Core defect is discovered. F1-5B implementation requires independent review
and a later Lead acceptance decision; it does not close F1-5C or F1-6.
