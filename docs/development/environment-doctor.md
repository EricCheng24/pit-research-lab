# Environment Doctor

Doctor diagnoses prerequisites before project dependency synchronization. It uses
Python **3.12** and only the standard library; no installed application, Make,
Docker or database is needed for the **core** profile. From the repository root
in a POSIX shell (WSL-side Linux or macOS `/bin/sh`), run:

```sh
sh scripts/doctor.sh --profile core
sh scripts/doctor.sh --profile test
sh scripts/doctor.sh --help
```

No arguments defaults to `core`. Only those argument forms are accepted; help
does no probes. The launcher prefers `python3.12`, then `python3` only when the
former is absent. An incompatible or broken preferred interpreter fails without
retrying another one. If Python is missing, install/select Python 3.12 separately
before rerunning. A uv-managed interpreter that is absent from PATH is not
automatically discovered or installed. Explicit invocation is also available:

```sh
python3.12 -I -S -B scripts/environment_doctor.py --profile core
```

The launcher always supplies `-I -S -B`: isolated imports, no site initialization,
and no bytecode files. Direct invocation should retain all three flags. No
dependency synchronization, installation, repair, report file or service startup
is performed by Doctor. Missing uv needs separate installation; optional Make
absence gives a warning. After diagnosis, follow the existing
[locked setup and Make-free quality commands](../../README.md#local-setup-and-verification)
separately. Those development commands can write environments/caches and are not
Doctor probes. The installed `pitlab --help` / `--version` interface is unchanged.

## Profiles and observed properties

| Check | Core | Test | Observation and limitation |
| --- | --- | --- | --- |
| PLATFORM / PYTHON | Required | Required | Supported 64-bit process platform and Python 3.12 minor; no physical-device or dependency certification |
| WSL2_SIGNAL | Optional on Linux | Optional on Linux | Explicit kernel signature only; ambiguous WSL generation never invalidates otherwise valid generic Linux Core |
| UV / GIT / CHECKOUT | Required | Required | Bounded recognized versions and expected Git worktree root; no lock/dependency/test validation |
| MANIFESTS | Required | Required | Exact pyproject.toml, uv.lock and .python-version regular-file metadata only |
| MAKE / SHELL_GUIDANCE | Optional | Optional | Shortcut discovery and invocation guidance; no Make command is executed |
| ROUTING | Excluded | Required | Presence of PG*, COMPOSE_*, PITLAB_* and all DOCKER_* names, even empty exports; values and arbitrary names are never printed |
| DOCKER_CLI / COMPOSE_V2 | Excluded | Required | Recognizable Docker client version and Compose v2 |
| DOCKER_CONTEXT / DOCKER_DAEMON | Excluded | Required | Validated current-context name, narrow Unix endpoint signal and server-version response; no resource/ownership/port proof |
| TEST_CONFIG | Excluded | Required | Exact .env.test.local lstat: regular non-symlink, current Unix UID, mode exactly 0600; contents never opened |
| TEST_PATHS | Excluded | Required | Exact scripts directory, compose.test.yaml, scripts/database.py and scripts/init-postgres.sh metadata; no execution or content validation |
| DB_RUNTIME | Always excluded | Always excluded | NOT CHECKED: identity, SQL, ownership, ports and health are never queried |

Linux x86_64 can satisfy Core independently of WSL2 identification. A canonical
Microsoft WSL2 kernel signature is only a bounded signal; an ambient WSL variable
alone is insufficient. Darwin ARM64 can satisfy its process check; Darwin x86_64
cannot establish the targeted native ARM64 process path. Doctor does not identify
hardware, prove Rosetta translation or certify native workflow compatibility.
Unknown/malformed required observations remain indeterminate; known unsupported
process architecture fails.

Docker's [official context inspect reference](https://docs.docker.com/reference/cli/docker/context/inspect/)
documents an explicit context argument and output formatting. Doctor obtains the
current name with `docker context show`, validates a bounded alphanumeric name
with dots/underscores/hyphens, then supplies that single name as an argv argument:
`docker context inspect --format '{{.Endpoints.docker.Host}}' <validated-current-name>`.
It does not rely on omitted-name semantics, enumerate contexts or accept a user
context option. Ambiguous names/endpoints return NOT CHECKED; non-Unix contexts
fail. No context switch occurs. Daemon query is only
`docker info --format '{{.ServerVersion}}'` after a local-context signal. These
snapshots assume a stable operator context and do not prove enduring local identity.
Live Docker/version-specific behavior has not been established by mock tests.

## States, exits and safe recovery

| State | Meaning |
| --- | --- |
| PASS | The narrowly named property was observed satisfied |
| WARN | Optional issue or bounded limitation; does not replace required proof |
| FAIL | A required property was observed unsatisfied |
| NOT CHECKED | Excluded by profile or evidence unavailable/unsafe; reason shown |

| Exit | Meaning |
| --- | --- |
| 0 | All selected-profile required checks PASS; optional warnings allowed, or help |
| 1 | At least one required FAIL, including when NOT CHECKED is also present |
| 2 | Required evidence indeterminate without an observed required FAIL |
| 64 | Invalid invocation; no probes and no rejected argument echo |

Core and Test summaries remain independent. Test failure can leave Core
prerequisites satisfied; a separate core invocation may return 0. The Test summary
describes the additional Test checks; its overall profile exit also includes every
required Core check. Both summaries must be considered. Required WARN cannot
stand in for PASS. Missing/blocked dependencies produce NOT CHECKED for
dependent probes. Missing Docker or config affects Test only. Exit 0 establishes
prerequisites for the selected profile, never PostgreSQL readiness or passing tests.

Probes use a closed argument allowlist, `shell=False`, no stdin, three-second
deadlines (five seconds for daemon response), and concurrent stdout/stderr capture
limited to 4 KiB per stream. Timeout/overflow kills and reaps only the launched
child, without retries. Only validated numeric versions and controlled reasons
are displayed; raw outputs, exception details, context endpoints, user paths and
secret values are suppressed. Unrecognized release suffixes/diagnostic output
remain NOT CHECKED. uv is not locally pinned to CI's 0.11.29; a different recognized
version produces an optional reference warning.

Child environments contain PATH and fixed C locale; Docker additionally receives
HOME for its existing context and WSL_INTEROP when present. Git uses disabled
optional locks/fsmonitor and disabled global/system configuration. Ambient secrets
and routing overrides are not inherited. Doctor reads no private home or Docker
configuration itself. Trusted third-party CLIs may internally load plugins/config,
contact a local daemon and record incidental state; controlled tests do not prove
host-wide absence of vendor writes, logs or telemetry. Stop and seek Lead review
if actual use exposes behavior violating the observational contract.

For unavailable tools, review installation/selecting the intended tools separately.
For ambiguous evidence, daemon denial, remote context, unsafe config metadata or
missing setup, retain existing files/resources and ask the Technical Lead. Never
paste secrets, change socket/file permissions, switch context, guess ports, prune
resources or bypass guards to make Doctor pass. Config metadata is a momentary
observation; it cannot establish credentials, namespace, ACL correctness or safety
against concurrent substitution.

Doctor **never imports, invokes or calls scripts/database.py**, including guarded
`preflight` or any other helper action. The
[database operator workflow](database.md) needs separate authorization and performs
the full ownership/identity/ports/SQL checks; it is not a Doctor subroutine.

## Illustrative output and evidence

The excerpts below are illustrative, **not observed executions**; other checks are
omitted for brevity.

```text
PIT Research Lab Environment Doctor — profile core
PASS          PLATFORM         Linux x86_64 process signal; workflows not verified.
NOT CHECKED   WSL2_SIGNAL      WSL2 not established; generic Linux Core remains independent.
WARN          MAKE             Optional shortcut; direct uv quality commands are in README.md.
NOT CHECKED   DB_RUNTIME       PostgreSQL identity, SQL, ownership, ports and health not queried.
Core prerequisites: satisfied
Test prerequisites: excluded
Exit: 0
```

```text
PIT Research Lab Environment Doctor — profile test
FAIL          DOCKER_DAEMON    Daemon access/response unavailable; seek Lead review, no socket repair.
FAIL          TEST_CONFIG      Expected file missing; review setup/source separately.
NOT CHECKED   DB_RUNTIME       PostgreSQL identity, SQL, ownership, ports and health not queried.
Core prerequisites: satisfied
Test prerequisites: incomplete (failure)
Exit: 1
```

Deterministic unit/fixture tests provide **SIMULATED_TEST** logic/safety evidence;
they establish no native macOS, WSL2 or 8 GB compatibility. Those physical workflows
remain **NOT VERIFIED** without separately recorded direct evidence. Optional
Layer C validation and Layer B contributor adoption are non-blocking; mandatory
Layer A Doctor safety/tests/review remain gates. Full platform onboarding/low-RAM
guides and integrated acceptance belong to later F1-5B/C work. Neither Doctor
output nor a green test run grants acceptance or DB operation authorization.
