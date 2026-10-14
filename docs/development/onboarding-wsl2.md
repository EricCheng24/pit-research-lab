# Windows 11 with WSL2 Ubuntu

Target: Windows 11 x86_64 with WSL2 Ubuntu and Linux-side CPython 3.12/uv.
The **complete new clean-checkout workflow is NOT VERIFIED**. Earlier WSL2 Core
and guarded-DB operations are bounded historical subsets, not a fresh run of this
guide. See the [capability evidence matrix](platform-support.md).

## Choose the correct terminal and get access

**Windows PowerShell** is the Windows shell. **Ubuntu/WSL POSIX shell** is the Linux
terminal where this project's Git, Python, Doctor, uv and Make commands belong.
Windows-installed Python/uv do not prove Ubuntu-side prerequisites. A WSL2 kernel
signal does not establish Windows edition, hardware or resource sufficiency.

If Windows 11/WSL2 Ubuntu or Linux tools are not installed, arrange workstation
setup through your team's approved procedure first. Enabling WSL, installing a
distro/tools and changing settings are separate actions, not Doctor repairs.
No Windows settings or PowerShell commands are required for the Docker-free path.

Confirm account access to the private
[official repository](https://github.com/EricCheng24/pit-research-lab) and permission
to use the standard Core workflow. In **Ubuntu/WSL**, choose a Linux-side parent
folder for the checkout. After the maintainer approves HTTPS or SSH, copy that
method's URL from the repository's **Code** menu and use Git's clone action there.
Clone accesses the network and writes files; do not clone over an existing folder.
For an existing checkout, confirm its identity with the maintainer.
Follow the [hub's access and root instructions](onboarding.md); enter the directory
containing `pyproject.toml`, `Makefile` and `uv.lock`. Its observational Git root
query helps locate the folder. Authentication/root failures mean stop and ask an
authorized maintainer, without credentials in chat or SSH/permission repair.

## Docker-free Core order

Use **Ubuntu/WSL POSIX shell, repository root** for every following step. Run one
command at a time and stop on nonzero; no commands here were executed as evidence.

1. Arrange Linux CPython 3.12 on PATH, uv and Git. Make is optional. Use the hub's
   reviewed installation reference; tool installation writes state and is separate
   from diagnosis. A uv-managed interpreter outside PATH is not found by Doctor.
2. Diagnose observationally: `sh scripts/doctor.sh --profile core`. Optional MAKE
   WARN permits the direct route; required FAIL/indeterminate evidence stops setup.
3. With Lead-granted routine Core workflow permission, intentionally run
   `uv sync --locked --python 3.12`. It writes `.venv`/caches and may need network.
   Doctor PASS does not prove sync success; no fresh per-command approval is needed
   for routine Core after the baseline permission.
4. After successful sync, run serial `make check`, or the **complete five direct
   uv commands in the [hub](onboarding.md)** in order. Both may write environment,
   cache or temporary files; neither starts Docker nor selects real DB tests.
5. CLI smoke/build are optional; use the hub's preconditions and write labels.

## Optional Test PostgreSQL

Core needs no Docker Desktop. Optional Test needs approved Docker Desktop WSL
integration, Compose v2 and the existing local Unix Docker context. Starting or
configuring Desktop is an operational action; never do it as automatic diagnosis.
In **Ubuntu/WSL POSIX shell at the root**, `sh scripts/doctor.sh --profile test`
observes prerequisites only. It never proves DB identity, ports, ownership, SQL or
health; missing private config can fail Test while Core remains satisfied.

Before setup or operation, obtain separate action-scoped Lead permission for this
checkout's unique namespace and non-overlapping **Dev/Test port pair**. The
[guarded operator manual](database.md) governs setup, lifecycle, probe, integration,
shutdown and destruction. Setup creates both private files once; Test-only work
does not require Dev to run. Its examples/default ports are not your allocation.

The helper may need Linux listener evidence and invoke `powershell.exe` for
Windows listener/reservation proof. The manual's **Windows PowerShell** inspection
examples belong on the Windows side and still require the assigned ports and
operator scope. Ambiguous/missing Windows proof cannot be replaced with a manual
PASS. Preserve the existing bounded bootstrap-bind content proof; no mount or
resource guard workaround is authorized by this guide.

## Stop and retain state

Wrong Linux interpreter/root, failed sync/lock/check or uncertain architecture:
stop and follow the [hub recovery table](onboarding.md). Missing Docker, daemon
denial, remote context, unsafe `.env.test.local` metadata, routing overrides,
ambiguous ports or bind proof: stop Test for Lead review. Do not switch context,
guess ports, copy identities, chmod files/sockets, prune or stop unrelated services.
If mounted-filesystem ownership/mode behavior is unexpected, retain files and ask
for scoped help rather than automatically relocating or changing permissions.

Start with Docker-free work on constrained devices; optional Test-only use depends
on actual resources. Physical 8 GB memory/storage/OOM behavior is NOT VERIFIED.
No swap, VM or Docker Desktop tuning is prescribed. Feedback and native experiments
remain optional Layers B/C, with no onboarding completion quorum.
