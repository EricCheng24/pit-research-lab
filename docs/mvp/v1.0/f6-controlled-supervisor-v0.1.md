# F6 B-CORE controlled supervisor data model v0.1

This slice provides an independent, synthetic SQLite catalog, closed supplied-value
policy and process identity records, and a pure private reducer. It does not run a
supervisor, authenticate an operating-system owner, issue a launch permission or
produce a public F6 response. Independent review and Owner acceptance remain open.

## Authority and isolation

Owner record `MVP-P1-03B-OAA-01` selects E1 plus A1 and nine CREATE-only paths.
`B-CORE-TOOLCHAIN-EXCEPTION-01` permits the existing Mainline virtual environment's
Python interpreter with F6 source first in `PYTHONPATH`; it authorizes no shared
environment mutation. All existing A files, P1-01 contracts, dependencies, tests,
pins and workflows remain unchanged. The A TestCatalog v1 is neither imported nor
adopted as a runtime catalog. No A submission, timestamp or held slot is promoted.

The new `SyntheticCatalog` constructor is inert. Explicit `*_for_test` operations
require a private owner-controlled directory below the approved unpredictable
`/tmp/pit-p103b-bcore.<uid>.<random>` test root. Existing directories must be 0700;
database files must be regular, singly linked, owner-controlled and 0600. Paths
with symlinked components or existing journals/sidecars refuse. This is a limited
test location policy, not a production storage root or hostile-filesystem defense.

## Schema and transaction contract

`runtime_catalog.py` installs a fixed ordered E1 STRICT schema, application ID
`0x46364231`, schema version 1 and purpose `TEST_HELPER_ONLY`. The schema identity
is SHA-256 of canonical JSON containing the fixed statement sequence. Expected
schema is never learned from database bytes. Eleven append-only tables, two views,
ordering/arm constraints and immutable triggers include future negative constraints;
B-CORE refuses nonempty launcher, arm, child, wait or quiescence tables on audit.

Every connection sets and verifies foreign keys ON, defer_foreign_keys OFF,
recursive_triggers ON, busy_timeout 250 ms, DELETE journaling and EXTRA synchronous.
There is no power-loss, unsupported-filesystem or operational crash recovery claim.
Open/reopen audit checks application/version, exact SQL objects, SQLite integrity
and foreign keys, canonical row/record agreement, owner predecessor chain, global
event revision and hash chain, local sequence, first cause and retained reservation.
Unknown or inconsistent storage refuses without repair or migration.

A1 orders the two explicit synthetic transactions:

1. Tx0 registers only an immutable synthetic Owner row. Generation number and
   predecessor digest are checked separately from the global event revision.
   A definitely acknowledged commit creates an in-memory test-session witness.
   Reopen/readback does not recreate that witness. Registration is not OS authority.
2. Tx1 requires that original test-session witness and current matching registration.
   A single BEGIN IMMEDIATE transaction writes Run, INTENT_COMMITTED and RESERVE.
   The immediate event-to-owner FK is satisfied by Tx0; the deferred run-to-first-event
   FK is satisfied before Tx1 COMMIT. Audit and foreign_key_check run before commit.
   The slot remains held; B-CORE has no disposal or rearm method.

Same-key/same-fingerprint requests return the original private allocation and bytes
without writes before checking current readiness, generation, capability revision,
busy slot or revision CAS. Different valid fingerprints conflict. Rejected unknown
keys are not allocated. A commit exception makes the session uncertain, blocks
future writes and never retries the transaction. Identity readback after lost ACK
never authorizes continuation, Tx2, GO or spawn.

Tx2 remains a future B-OS registration obligation. A pure modeled launcher event
must reference the first intent's original generation, but no B-CORE method registers
a real launcher, opens a lease, consumes an executable arm or sends GO.

## Pure modules

`launch_policy.py` validates bounded canonical expectation and resource forms and
declares a fixed future argv/environment from supplied lexical paths. Every live
request returns `B_CORE_AUTHORITY_ABSENT`, including complete hash-shaped approvals.

`process_identity.py` parses only bounded supplied stat-like bytes and compares
synthetic boot/PID/start/PGID/SID/generation/nonce/lease/executable identities.
Equality is `MODEL_MATCH`; it never proves a process or FD exists. No procfs,
process inspection, signaling or operating-system lease operation is present.

`supervisor.py` reduces closed private events with explicit revision, sequence,
hash and generation fencing. First failure cannot be replaced; unknown outcomes
quarantine without rearm. W00–W14 are separately identifiable supplied-fact models.
Modeled arm, exit or quiescence labels are not execution or result evidence.
Neither modeled EXIT 0 nor any catalog hash creates ACTUAL_F3_CLI, verified results,
RUNNING, SUCCEEDED, COMPLETE or AVAILABLE public claims.

REM01 retains the accepted supplied `EXIT_OBSERVED` event in a frozen `WaitOutcome`
on `RunModel`. Its canonical facts retain `EXIT` versus `SIGNAL` and the corresponding
code or signal. `wait_observed` must agree with a coherent outcome bound to the run,
original generation, sequence and post-wait phase; a Boolean alone is insufficient.
`FIRST_FAILURE(CHILD_NONZERO_EXIT)` additionally requires a known child and an earlier
modeled `EXIT` with an integer code in `1..255`. EXIT 0, SIGNAL and absent/uncertain
wait evidence cannot satisfy that claim. Repeated wait events and first-cause
replacement remain refused; secondary/recovery events preserve the stored outcome.
These are private accepted-history consistency checks, not authentic wait/reap proof.
A directly constructed snapshot remains a supplied claim, not a substitute for
replaying the event chain. `FIRST_FAILURE.source_sha256` keeps its existing digest
syntax; no equality to a wait-record/event digest or new hash domain is asserted.

## Validation and deferred gates

The original four-module target was 29 pure items and five SQLite-only integration
items. REM01 adds necessary outcome/first-failure regressions without removing the
W00–W14 cases. Actual counts/results, source identities, schema digest, negative traces,
timings, resource observations and selected unchanged-A regressions are recorded
in the external B-CORE evidence packet; this document makes no CI-pass claim.
The integration marker excludes the five SQLite items from the non-integration
phase and includes them in the existing full test collection. No collection,
Makefile, dependency, marker or workflow changes are part of this slice.

All tests require the externally isolated temporary/cache root and an independently
validated outer watchdog. Test code caps catalog counts, owner/run/event counts,
SQLite size and connection counts. Fault injection is an in-process exception
seam, not power loss or an OS crash. Test cleanup removes only inspected test-owned
regular leaves; no unrelated process or storage is touched.

B-OS/B-REC still need separate approval for original S/L ownership, private channels,
flock/FD inheritance, Linux identity and signaling, original-parent wait/reap,
quiescence and crash recovery. Production storage, quotas, runtime authorization,
CI delta and physical durability remain open. HTTP/dependencies/protected-current
pin transitions, C release G01–G10, real F3 execution/verifier and D real Native
acceptance remain deferred. No Git integration is authorized by this slice.
