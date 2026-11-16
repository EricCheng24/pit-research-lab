# WU05 ORACLE-02 scoped freeze materialization v0.1

Task `MVP-F2-WU05-ORACLE02-SF-01`. This is a **materialized candidate pending
independent integration review and Owner Git integration**. No Mainline freeze,
production Codec conformance, Native replay or PIT acceptance is declared.

The [manifest](../../../tests/fixtures/mvp_if03/wu05_oracle02_scoped_freeze_v0_1/FREEZE_MANIFEST.json)
includes exactly **94 distinct reviewed records**: B01–B08, all 80 corrected N-*
refusal requirements, and these six relations:

- `R-UNICODE`, `R-RAW-MUTATION`, `R-FOUR-CUTOFFS`
- `R-D06-CONSISTENT`, `R-D06-POLICY-CHANGE`, `R-EVIDENCE-DIRECTION`

All remaining **16 records are explicitly excluded**: R-REDACTION,
R-ATTEMPT-SEPARATION, R-DECISION-EVALUATION, P2-DEPTH-64/65, the ten BLO-* cases,
and DEFER-GATES. Exclusion reasons, original statuses and metadata-record hashes
are machine-readable. The author ledger remains 110 records; domain applicability
overlaps never enlarge the unique count. Excluded metadata hashes are ordinary
file/record integrity pins, never canonical Domain identities or successful bytes.

This overlay preserves the [previous limited Golden](if03-oracle01-limited-golden-freeze-v0.1.md).
The original archive, manifest and 24 binaries remain in their existing locations;
no replacement binaries or ReferenceEnvelopes are issued. Expected six-field
envelopes and raw/payload/frame/archive-member pins identify the original eight
complete SOURCE-BYTES positives. The other nine primary domains remain without
complete positive identities.

Controlling authority is Shared Interface CAN-01..10, AD01-08/09/11 and
RT01-01..05, plus UX's ratified bounded Weekly illustration. Actual baseline is
`c2d66cf880d2e34d9f95f9351cbb616e3d5a7783`; Shared/UX Git blobs are
`d028005f6ac854fc3cde965b562dba4e449159cf` /
`96d463c40a49d94e0b206be3851e26063fc6c581`. The manifest preserves all 53 baseline
pins and eight corrected author-file pins, including exact input/expected record
snapshots. Record hashing uses explicitly specified sorted compact UTF-8 JSON
with array order preserved and no Unicode normalization. **That metadata encoding
is not the IF-03 App Canonical Codec.** A literal manifest hash lives externally
in the regression test; the manifest does not hash itself.

Independent ORACLE-02 evidence is pinned by file hash and role, including fresh
eight-vector verification, the case matrix and six relation calculations. Its
historical N-OWN-ENVELOPE finding is retained. The current Owner SF-01 instruction
supplies the accepted independent REM1 delta outcome; no separate exported delta
review report, reviewer signature/identity or approval clock was provided or
invented. The REM1 author report is separately labeled revision evidence. External
`/tmp` evidence paths are provenance locators, not CI runtime dependencies.

REM1-P1-01 is preserved as accepted: the explicit own-digest claim expects
`STRUCTURALLY_INVALID / REF_CYCLE` under CAN-05/AD01-08; unrelated unknown fields
retain `CLOSED_FIELDS`. The author's broad top-level `reference` detection is a
known bounded-helper limitation, **not a frozen production rule**. A future Codec
must distinguish a recognizable forbidden own-envelope claim from an unrelated
unknown field. This materialization changes none of the 80 case records.

REM1-P2-03 is preserved: TEMPORAL-SEQUENCE's TimeRecord prerequisites include
ORIGIN/TIMEZONE_RULES; EVIDENCE retains the conditional ProvenanceParent union
beyond its explicit role index. No resource body/schema approval follows.

Record depth root/array counting remains `PENDING_OWNER_BOUNDARY_DECISION`;
P2-DEPTH-64/65 stay conditional and unfrozen. The previously disclosed ancestor
filename-search deviation remains an operational P2. It was not repeated or
investigated through protected-root access.

Refusals are exact narrow expected requirements, not production conformance.
Relations retain their accepted bounds: four-cutoff declaration/arithmetic is
diagnostic only; D06 hypothetical consistency still yields NOT_SUPPLIED; symbolic
Evidence direction does not authenticate a graph. Scope stays diagnostic_only=True,
admission_eligible=False, NOT_TRUSTED_PIT_EVIDENCE,
source_authentication=NOT_ESTABLISHED, INTEGRATED_PROVISIONAL.

The [freeze regression suite](../../../tests/unit/mvp_f2/test_wu05_oracle02_freeze.py)
checks all 110 records, exact 94/16 partition, fixed expectations and source pins,
original archive/binary/envelope integrity, and in-memory tampering controls. It
imports neither the author's reference helper nor production identity code.

WU05-CAN may subsequently be measured against the precisely accepted immutable
subset after independent integration review, Owner-authorized clean-commit
integration and normal Hosted CI. New semantic expectations require a new reviewed
version retaining prior bytes. Actual reviewed timezone/source resources, original
Native Attempt/semantic receipt/correspondence witness, issued ScheduleInput,
F3/F5 declarations and rights remain blockers. Channel A/B acceptance, IF04/05/07,
issuance, F3/F5 execution, TypeScript, services and Formal access remain separate
gates. Full dirty-worktree `make check` is not claimed; provenance guards remain
unchanged. These three new files and the eight prior author additions remain
uncommitted; no staging, commit, push, PR, merge or remote mutation is performed.
