# F6 local backend infrastructure v0.1 — P1-03A

Implementation candidate under `MVP-P1-03-OAA-01` and `MVP-P1-03A-IMP-01`.
Independent Review and Owner acceptance are separate. This is an A-only boundary,
not a running backend or completion of P1-03 A01–A17 / G01–G10.

## Authority and interfaces

The merged P1-01 `contracts.py` and `projection.py` remain unchanged. Their
`VERSION`, fixed capability/protocol/dataset identities, strict request semantics,
and submission fingerprint define the syntactic selection. The fingerprint
excludes the idempotency key. Wire validation never proves actual execution.

`backend/__init__.py` is inert. `config.py` contains frozen, closed forms for
policy and independently supplied provenance expectations. It does no discovery
or I/O. Bounds on integers are representation constraints, not chosen production
limits. Missing fields yield `NOT_CONFIGURED`; missing approval references yield
`UNAPPROVED_FORM`; even a completely populated synthetic form yields
`B_PHASE_AUTHORITY_ABSENT`. References are claims, not approval credentials.
There is no launch, readiness-success, production root, port, runtime or expiry
default. No environment switch enables research.

`security.py` operates on explicitly supplied immutable header tuples, targets,
body bytes and synthetic session-comparison operands. Only POST submission
composition is provided. `X-F6-Session` and `X-F6-Csrf` are detached test inputs,
not an issued cookie/session protocol. Exact literal `127.0.0.1:port`, exact
Origin and restrictive same-origin Fetch Metadata are required. Proxy overrides,
duplicate authority/context values, encoding declarations and unsafe paths refuse.
Optional Content-Length is checked against supplied complete bytes. These checks
do not prove socket framing, raw-header fidelity, cookie parsing, proxy behavior,
browser support, parser admission or authentication. No CORS or file serving exists.

The linear JSON pre-scan precedes the existing strict F6 decoder and closed
`SubmissionRequest`. Synthetic-test ceilings are 256 KiB body, 32 nesting levels,
1,000 conservatively counted structural/string/comma tokens, 16 KiB encoded
string content and 32 numeric-token characters. Conservative counting may refuse
some JSON below the container-member ceiling; the fixed six-field request fits.
Duplicate keys, floats/exponents/nonfinite values and extra fields are rejected.
All outward failures contain closed reason codes, never supplied content.
Syntactic selection does not call `validate_submission_selection` with an invented
executable capability. Future controllers must establish independent readiness.

## Test catalog schema 1

`TestCatalog` construction is inert. Explicit `initialize` creates a nonexistent
leaf; `open_existing` accepts only the exact known schema. Both require a
caller-supplied private 0700 test directory below Linux `/tmp`, with no symlink
components, and a simple filename. Files must be owned, regular, single-link,
0600 and at most 32 MiB. Existing empty/invalid databases and sidecars are refused,
not repaired. This is a test-only storage boundary, not a production installation.
Same-uid malicious filesystem replacement and power-loss recovery are unproven.

Schema identity is SHA-256 of canonical ordered DDL, checked together with exact
`sqlite_master` SQL, `user_version=1`, application ID, metadata identity,
quick/foreign-key checks and the tiny A ledger shape. Unknown versions/objects,
missing triggers and changed identity fail without migration. Opening an unknown
database performs read-only validation before any writable connection.

| Table | Invariant |
|---|---|
| metadata | One immutable test installation UUID and schema identity |
| intents | Immutable App UUID, allocation UUID, canonical request bytes, fingerprint, expected revision/build and caller-supplied synthetic accepted-at; unique operation/key |
| active_slot | Singleton reservation referencing intent; no A API releases it |
| events | Immutable per-run sequence, unique global revision, preparatory phase and first failure |

Unique constraints create the lookup indexes. All four tables reject UPDATE and
DELETE through triggers. Insert guards also refuse `INSERT OR REPLACE`, which
must not bypass immutability through SQLite's implicit replacement deletion.
An insertion trigger requires next sequence/revision
and the reserved slot. A deferred intent-to-first-event foreign key prevents
committing an intent without its first event. A allows one held intent and at
most two events: `INTENT_RECORDED` → `BLOCKED`. Block records one closed
preparatory reason and retains the slot indefinitely. No child or release claims
have a column or transition. Later safe slot disposition needs explicit B scope.

`reserve_synthetic` revalidates canonical bytes, independently supplied expected
revision and fingerprint before looking up the key. `BEGIN IMMEDIATE` serializes
intent + reservation + event. The catalog identity returns only after commit.
Same operation/key/fingerprint reconstructs the same private identity on reopen;
different valid fingerprint conflicts; another key receives BUSY without queueing.
Accepted build/time/allocation stay immutable on retries. This record is not
`ApplicationRunReceipt`, HTTP acknowledgement or a process-launch permission.

The journal strategy is DELETE with `synchronous=FULL`, `foreign_keys=ON`,
1,000 ms busy timeout and explicit transactions. No WAL is used. Failed
transactions roll back; closed handles leave no expected journal sidecar.
This proves SQLite-level atomicity, not directory fsync, power-loss durability,
OS single-job lease, at-most-once child start or immutable result publication.

## Bounded verification and pending gates

Three targeted new test modules cover synthetic config/admission, import inertia,
schema refusal, rollback, idempotency, two-connection contention and SQL tampering.
All catalog tests carry the existing `integration` marker. Quality excludes them;
PostgreSQL Integration's existing `make test-all` includes them. They use SQLite
only and do not need PostgreSQL, Docker or network. Actual collection counts,
elapsed times, tools, commands and outcomes belong in the external implementation
evidence packet, not an asserted whole-CI success here.

Harness ceilings: ≤32 MiB per SQLite file, ≤128 MiB aggregate external owned
files, ≤4 test workers, ≤2 s lock wait, ≤1,000 events/test. A structurally permits
at most two events/catalog, with no slot reuse. Integration fixtures measure owned
bytes including sidecars and remove their owned files. Caches/logs live outside
the checkout; the verified outer watchdog bounds all targeted commands.

D-P103-01 HTTP stack is deferred; no dependency delta. D02 runtime/import/Git,
D03 root/port, D04 production resource/retention policy, D05 supervision and D06
release have no live authorization. D07 selects future T1 physical Real Native
acceptance separation; it creates no acceptance tests in A. D08 grants only the
eight creates; D09 requires independent review, Owner acceptance and separate
Git integration permission. Protected historical/current pins remain untouched.

P1-03B requires authenticated one-use launch/lease, process identity, exit and
crash reconciliation. P1-03C requires parser/security transport proof, exact safe
frozen ten-file reads, actual Native verifier and G01–G10 publication/invalidation.
P1-03D requires separately authorized bounded Real Native acceptance outside
`tests/`, clean-source provenance and complete headless/recovery evidence. None
is implemented or executed here. No successful release, replay, PIT eligibility,
scientific validity, evidence promotion or Owner acceptance follows from A.
