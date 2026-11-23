# F6 OS helper lifecycle — OAA-02 source-only v0.1

Authorization: `MVP-P1-03B-OS-OAA-02-SOURCE-IMPLEMENTATION-v1.0`.
Base: `ba4190fe36cc9876cac205459879cef6b6975972`.
Status: SOURCE_ONLY_IMPLEMENTED; independent review and Owner acceptance pending.
MODEL/SQL_VERIFIED applies only to the actual results in external implementation
evidence. PHYSICAL_NOT_EXECUTED; SIGNAL_NOT_AUTHORIZED; B_REC_DEFERRED;
NATIVE_NOT_AUTHORIZED. No kernel, platform, physical wait or cleanup PASS.

## Boundaries and source modules

All twelve additions are isolated from the nine accepted B-CORE files and A's
TestCatalog. `os_ownership.py` contains supplied identity/frame/FD codecs and
session-gated Linux adapter source. `os_runtime_catalog.py` reuses E1's exact
ordered DDL/app ID/version, with a separate full lifecycle audit and a deliberately
RECORDED_ONLY fixture writer. `os_supervisor.py` supplies the fixed helper spec,
unapproved budget values and pure S registration/arm/report/GO state. The original
L source is `child_launcher.py`: local once latches, supplied-effect simulation,
gated Popen/sole original wait, and bounded held evidence for OS-F02.

There is no physical-session issuer in this authorization. PhysicalSession cannot
be constructed; every physical adapter entry refuses before its first I/O. Models,
synthetic owner ACKs, readback, nonces, JSON, approval hashes, config and environment
cannot issue that session. This intentionally withholds physical admission; it is
not a claim of an operational S/L/W installation. A future independently reviewed,
case-scoped Owner/platform/target/cleanup issuer and its integration remain required
before dormant role entrypoints can run. No generic live-enable seam is provided.

Imports/constructors are inert. The physical driver, harness and eight physical
node declarations are outside testpaths=[tests], are never imported by ordinary
tests or runtime source, and have no current positive entrypoint. Dormant S/L and W
entry adapters refuse rather than manufacture observations or simulate a physical
run. S/L source algorithms use the closed OriginalSupervisorIO/OriginalLauncherIO
ports, and W source enforces finite topology/evidence/close ordering. Binding those
ports to a genuine original physical session is intentionally unavailable; no
fixture or generic callable may substitute for that issuer. The fixed no-fork child
and resource/target adapters are also dormant. None of this physical orchestration
or issuer/port integration is asserted tested or independently accepted here.

## Lease, identity and message design

Installation I is one stable exclusive nonblocking flock OFD inherited S→L through
the exact pass_fds allowlist. Copies close normally; no shared LOCK_UN. Active job
J is L-only, never H. I acquisition precedes J. A released/acquirable J does not
prove H absence. The root/lock contract is private owner-controlled Linux-local
storage, directories0700, regular single-link locks0600, no symlink components,
stable before/after device/inode. Trusted cooperative UID/code, not hostile-code
sandboxing or protection against malicious same-UID rewrites.

Bind boot/PID/PPID/start/PGID/SID, original generation, launcher/run/installation,
nonce and I/J identities with approved source/runtime/helper identity. Supplied
equality or PID alone is not ownership. pidfd denotes an individual process; it
does not prove group containment or original wait rights. Private credentialed
SOCK_SEQPACKET frames use SO_PASSCRED/SCM_CREDENTIALS, not prespawn SO_PEERCRED as
spawned-L attribution. Reject ancillary FD transfer, truncation, missing/extra
credentials, closed-field mismatch, replay and cross-session frames; ≤16KiB/frame,
≤32 accepted frames/window. Raw nonce plaintext never belongs in public evidence.

FD extras: W/S/contender one private context endpoint; L I+S/L endpoint; H one L/H
endpoint, with redirected stdio. close_fds=True; exact pass_fds; restored CLOEXEC.
No root/database/credential/lease/pidfd reaches H. Kernel/CPython/OFD behavior is
UNVERIFIED physically in this task.

## E1/A1, one attempt, original wait and OS-F02

Tx0 Owner precedes Tx1 Run+INTENT_COMMITTED+RESERVE. Tx2 launcher+event is atomic.
Tx3 inserts arms(consumed=1) BEFORE SPAWN_ARMED so arm_owner sees OWNER_READY.
TX3 definite synchronous ACK → ARM_COMMITTED report → exact matching GO → local
once latch → GO_ACK → at most one spawn attempt. ARM_ALLOWED is prearm only.
Transaction uncertainty poisons the writer; readback returns historical identity,
never a continuation. No automatic retry/rearm/replacement L or recovered wait.
Global event revision and run sequence are independent counters; Tx0 has neither.

The recorded fixture writer is restricted to a private source-evidence root
`/tmp/pit-p103b-os-source.<uid>.<random>/...`, ≤2MiB/catalog, ≤250ms busy timeout,
foreign_keys ON, defer_foreign_keys OFF, recursive_triggers ON, DELETE/EXTRA.
No physical-helper root/profile file is created. Physical future layout remains
`/tmp/pit-p103b-os-helper.<uid>.<random>/` with authority.json/catalog.sqlite3,
stable installation/job locks, private home/tmp/evidence. TEST_HELPER_ONLY and
PHYSICAL_HELPER_V1 metadata are not authorization tokens. RUNTIME_DORMANT unused.

The dormant owned write path has a distinct PhysicalLocation and explicit
activate_physical/register_owner_owned/admit_owned/append_owned/failure_owned/
quarantine_owned/terminal_owned methods. Each requires the unavailable genuine
session before I/O and binds observed records to that session; recorded methods
refuse the physical root type. Owned Tx0 ACKs are catalog/session-bound and issued
only after definite commit. Original L may attach its own connection only with
the original live I/J/nonce/Tx2 channel witness, never by discovering a row.
open_physical_readback remains read-only and does not set that session or ACKs.
No positive owned activation/attachment/write was exercised by SQL fixtures.

Whole-ledger audit checks exact schema/objects/PRAGMAs, owner chain/columns, request
and expectation bytes, accepted identity, full event hash/revision/run sequence,
all row↔event↔closed-record links and original generation/actor, immutable first
failure, one-use arm and retained reservation. Existing SyntheticCatalog remains
unchanged and rejects populated future tables. Unknown schema/data refuse without
repair/migration. Reopening this new catalog is read-only and cannot restore ACKs.

Tx4 child registration must definitely precede H work release. Tx5 retains only
an attributed original L wait. EXIT0, EXIT7 and SIGNAL are distinct; known nonzero
failure requires a registered child and accepted nonzero EXIT, preserving REM01.
L is the sole reaper with bounded Popen.wait; timeout/ECHILD/lost L is unknown,
not exit. No implicit run(timeout) kill or second reaper.

**OS-F02 conservative selection:** no committed registered child means no Wait/Q
catalog row or forced EXIT_OBSERVED. Keep only bounded external observation bytes
and their integrity digest; retain Held/Unknown. Never fabricate a child row,
child-observation hash or original wait witness to satisfy E1's required FK/hash.
The planning packet's optional limited in-schema wait path is not selected.

Tx6 no-fork Q requires registered child, durable original wait and matching
launcher/helper inventory/lease disposition. These stored records are supplied
claims in SQL fixtures, not kernel evidence. Tx7 TERMINAL_HELD retains the slot.
No DISPOSE/SLOT_DISPOSED, cold recovery, orphan adoption result, or general
descendant proof. No helper result becomes ACTUAL_F3_CLI or public success.

## Tests and future physical gates

Ten U functions and five C functions use only supplied facts/SQLite. Their actual
commands/results/hashes and tool origins belong to the external evidence packet;
code/test existence is not PASS. Tests trap subprocess/socket/flock/pidfd/signal
paths. Existing A/B-CORE/P1-01 expected behavior and protected bytes are unchanged.

P01–P06/F00/F01 are authored declarations, NOT_RUN/NOT_AUTHORIZED, never skipped
as success. P01 uses the Owner prompt's exact function name
test_installation_and_job_lease_contention. F00/F01 require a separate signal
permit; F02/F03 crash/orphan/recovery remain B-REC and are not authored here.
Proposed22 normal role starts/23 with runner, max4 concurrent roles, 8s/node,
60s/command and64MiB total are unapproved planning candidates, not live quotas.
Current code does not activate a watchdog to validate them.

OS-F03/04: future independent review must inspect exact source, syscall/FD/target
and pidfd custody, bounded W cleanup and subreaper/platform assumptions before
physical execution. No broad group signal or fallback guessed PID kill. Explicit
static lint/format/syntax checks cover platform_probes because Makefile roots do
not; default collection must not discover/import those physical files.

Quality/PostgreSQL Integration check names/selections, Makefile, dependencies and
strict marker configuration remain unchanged. Hosted checks and genuine independent
review/Owner acceptance/Git integration are later gates. Source-only validation
does not authorize Native F3, verifier/research release, HTTP or production service.
