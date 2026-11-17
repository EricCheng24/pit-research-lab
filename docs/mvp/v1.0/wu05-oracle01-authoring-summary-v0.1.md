# WU05 ORACLE-01 independent authoring v0.1

`MVP-F2-WU05-ORACLE-01` disposition:
`WU05_ORACLE01_AUTHORED_READY_FOR_INDEPENDENT_REVIEW`.
Eight existing SOURCE-BYTES positives are independently reconstructed; the other
nine domains have explicit blocked full positives. No new complete positive was
authored, no reference/resource was issued, and no full-domain freeze is claimed.

**Baseline and change boundary.** Work began on clean `main` at exactly
`c2d66cf880d2e34d9f95f9351cbb616e3d5a7783`, with the expected
`https://github.com/EricCheng24/pit-research-lab.git` origin. The local branch is
`mvp/f2-wu05-oracle01`. Before Git commands, the allowed clone's `.git` was checked
as a real local directory without symlink/gitdir pointer, commondir or object
alternates. Redirecting Git environment/config was absent; `GIT_PAGER=cat` is
nonredirecting. Effective Git config was also inspected. No fetch, remote change,
stage, commit, push, PR, merge, reset, cleanup, Native evaluator invocation or service activation
was performed.

Audit deviation: one early `rg --files -g AGENTS.md` filename search mistakenly
used `/home/rooki/projects` as its root. It returned no excluded-checkout paths,
but may have traversed excluded directories; absolute filesystem non-traversal
cannot be certified for that search. No Git command, file-content read or write
targeted the protected Formal checkout, old linked Academic worktree or previous
temporary RS checkout. All subsequent repository inspection and implementation
used the authorized standalone clone. The local Git isolation and exact baseline
were established independently of that search.

Eight additive paths only:

- `tests/fixtures/mvp_if03/wu05_oracle01_v0_1/README.md`
- `tests/fixtures/mvp_if03/wu05_oracle01_v0_1/cases.json`
- `tests/fixtures/mvp_if03/wu05_oracle01_v0_1/domain_coverage.json`
- `tests/fixtures/mvp_if03/wu05_oracle01_v0_1/source_pins.json`
- `tests/fixtures/mvp_if03/wu05_oracle01_v0_1/schedule_declaration.json`
- `tests/unit/mvp_f2/test_wu05_oracle01.py`
- `tests/unit/mvp_f2/wu05_oracle_reference.py`
- `docs/mvp/v1.0/wu05-oracle01-authoring-summary-v0.1.md`

Existing Golden/archive/contracts/RS production files, earlier tests, dependency
files and CI are unchanged. The final tracked and staged diffs are empty; these
eight additions remain untracked for Owner integration. No provenance guard was
changed or bypassed.

**Source authority.** The [source pins](../../../tests/fixtures/mvp_if03/wu05_oracle01_v0_1/source_pins.json)
record 53 actual baseline Git Blob IDs with separate raw-file SHA-256 and length,
including the 24 old binaries, archive/manifest, contracts, RS sources, WU01–WU04
fixtures/tests and toolchain configuration. The focused tests verify these pins
without Git status assumptions. Principal exact contract blobs are:

| Source | Actual Git Blob ID |
| --- | --- |
| Shared Interface CAN-01..10 / AD01-08/09/11 / RT01-01..05 | `d028005f6ac854fc3cde965b562dba4e449159cf` |
| UX ADR, bounded Weekly illustration and later ratification | `96d463c40a49d94e0b206be3851e26063fc6c581` |
| Existing limited Golden freeze note | `447f3619b1eb0e14f1db88766d2aac97421ab491` |

Shared/UX raw SHA-256 respectively:
`66bef5b0bb8240214ec8ea14c3c94c8748e2944270883c56de3ae7f27355428b` /
`abb04bba20ce8640c38b2406aa662ae86ff3d6df892343b2e6d780c3073c01db`.
D01–D06 design authority comes from the current Owner execution prompt; it does
not issue bodies or prove attempts. The four optional WU05 SPEC/Planning/PREP/REM1
review ZIPs were not present in the authorized checkout. No outside-root search
for those packets or redundant transfer was needed.

**Actual coverage.** Counts below are derived from the authored records. One case
can apply to multiple domains, so rows cannot be summed as unique totals.
`Rel. tested` means an author's structural/declaration predicate, never domain
issuance, replay or production conformance.

| Domain | Complete positive | Executable refusal | Rel. tested | Documentary relation | Blocked full/time positive |
| --- | ---: | ---: | ---: | ---: | ---: |
| SOURCE-BYTES | 8 | 42 | 2 | 2 | 0 |
| F2-QUALIFICATION | 0 | 9 | 1 | 1 | 2 |
| F2-OBSERVATION | 0 | 11 | 1 | 1 | 1 |
| TEMPORAL-SEQUENCE | 0 | 12 | 3 | 0 | 1 |
| F3-EXPERIMENT | 0 | 1 | 0 | 0 | 1 |
| F3-RUN-ATTEMPT | 0 | 1 | 0 | 1 | 1 |
| RESULT | 0 | 2 | 0 | 1 | 1 |
| EVIDENCE | 0 | 6 | 1 | 0 | 1 |
| F5-DECISION | 0 | 3 | 0 | 1 | 1 |
| F5-EVALUATION | 0 | 1 | 0 | 1 | 1 |

There are **110 unique authored records**: 8 existing complete positives,
80 executable refusals, 11 relations (6 tested / 5 documentary), 10 blocked and
1 deferred cross-owner gate (`DEFER-GATES`, applicable to the nine semantic
domains). The ledger preserves all ten exact schema/tag/profile tuples, exact
top-level semantic keys, source field specifications, helper/typed parent order,
conditional resource roles, prerequisites and next owners. No eleventh Domain is
introduced for a resource role.

**B01–B08 reconstruction.** All eight passed independent raw-body → payload →
LP64BE frame → SHA-256/envelope comparison. All 24 direct `.bin` files match their
archive members byte for byte. The archive remains 383476 bytes, SHA-256
`b3b74b713dbd43b6ef70f32c6c666c0caf8e5ac08c27d96a2d025cda038bdd34`.
Its 409 member paths/counts/sizes/CRC and all 408 manifest entries passed before
selected data was read in memory. No archived script was imported or executed.

Worked B01: the raw body is empty, with raw-body SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Its exact three-field payload is:

```json
{"body_byte_length":{"type":"uint64","value":"0"},"body_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","canonical_profile_version":"typed-json-candidate-v0.1"}
```

Field order is body_byte_length, body_sha256, canonical_profile_version; the nested
UInt64 order is type, value. Payload = 187 UTF-8 bytes. Domain
`PITLAB/ACADEMIC/SOURCE-BYTES/candidate-v0.1` = 43 bytes; schema
`source-bytes-candidate-v0.1` = 27 bytes. Three eight-byte big-endian prefixes are
`000000000000002b`, `000000000000001b`, `00000000000000bb`, at offsets 0, 51 and
86. Payload starts at 94; total frame length = 24 + 43 + 27 + 187 = **281**.
SHA-256(frame) =
`687ddd2e1d12816f5e20e505af0bb9d6f149ddf218e7f37a6eb6dc13df3ea686`.
The original expected six-field envelope agrees on domain/schema/profile,
`digest_algorithm: SHA-256`, the digest, and UInt64 payload length **187**, not
281. Every vector is also checked against its original expected JSON record's
literal payload/frame hex and original frozen manifest pins. B06 remains opaque
raw `ff`; B04/B05 retain composed/decomposed scalar distinctions.

No positive expectation is rewritten or generated from RS/production serializers.
The original archive's historical 64-case composition remains 8 complete,
14 scalar fragments, 4 framing components, 21 documentary refusals,
11 documentary relations, 5 blocked and 1 deferred. The other **56 historical
records are not 56 passed runtime tests**. New refusal checks are separately
authored records with their own IDs and bounded claims.

**Executed versus unexecuted.** The focused test passed B01–B08, every `N-*` case
in [cases.json](../../../tests/fixtures/mvp_if03/wu05_oracle01_v0_1/cases.json)
(80), and R-UNICODE, R-RAW-MUTATION, R-FOUR-CUTOFFS, R-D06-CONSISTENT,
R-D06-POLICY-CHANGE and R-EVIDENCE-DIRECTION. These are 94 executed case records;
three additional pytest checks validate metadata/pins/coverage/archive composition.

R-REDACTION, R-ATTEMPT-SEPARATION, R-DECISION-EVALUATION, P2-DEPTH-64 and
P2-DEPTH-65 remain documentary. BLO-01..BLO-09, BLO-TIME and DEFER-GATES are
unexecuted. Checking their register entries does not count as running a refusal,
Native event, issuance, original witness verification or policy operation.

The temporal check reads all seven original raw-body and publication declarations
from pinned `derived_observations_v0.1.json`; explicit JSON pointers are recorded
in R-FOUR-CUTOFFS. It independently checks strict publication-before-cutoff,
D1/D2/D2/D3, the four exact local 18:00 cutoffs, A04 sums and A05 HALF_EVEN
six-place arithmetic. D2 AT t1 and D3 t3+1 second are excluded. Reused contexts,
swapped/dropped/duplicate/foreign ticks, W03 as fifth tick and B03 midnight reject.
This does not run Native qualification or attest named-zone rules. Full
TimeRecord evidence retains source_text/zone/offset/precision/origin/UTC/rules
separation; host timezone data is never adopted.

D04 transitive symbolic attempt ancestry and graph cycles reject; mandatory
NativeSummary receipt/state omissions reject without inventing no-outcome state.
D05 SAFE extra surfaces and missing/revoked grants reject under separate
categories. D06 compares complete hypothetical refs: original inputs, PF038,
AF009 policy and sequence schedule mismatches reject before ordinary
`NOT_SUPPLIED`; consistent declarations remain `NOT_SUPPLIED`. A changed full
policy ref changes the dependency preimage expression without claiming a new
issued digest. F3 association-instance/result-attempt edges and F5 future fields
or immature evaluation inputs have narrow structural refusals. Symbolic graph
names and hypothetical six-field wrappers supply no authenticated resources.

**Earliest missing prerequisites.** The matching ledger cases retain details:

| Case / domain | Earliest upstream dependency / next owner |
| --- | --- |
| BLO-01 / F2-QUALIFICATION | F2 must supply reviewed original source/Origin, distinct Manifest/Version/History/Coverage, Calendar/rule bodies, relevant code closure, mandatory semantic NATIVE_RECEIPT and separate original Attempt/correspondence witness/rights. |
| BLO-TIME | Actual reviewed pinned TIMEZONE_RULES bytes/schema/coverage/rights; declaration arithmetic alone is insufficient. |
| BLO-02 / F2-OBSERVATION | Complete qualification and tick context, typed value/origin/numeric policy and reviewed Projection/Release Policies; actual authorization remains a separate operation. |
| BLO-03 / TEMPORAL-SEQUENCE | Actual versioned ScheduleInput SOURCE-BYTES containing exact original refs/full invariant policy, AF009 agreement and PF038 → DECISION_SCHEDULE → schedule_ref; then reviewed config/schedule/trace and four distinct bindings plus F3/F5 temporal declarations. |
| BLO-04 / F3-EXPERIMENT | F3-owned hypothesis/method/protocol/horizon/evaluation plan/seed and sequence parent; association CONTRACT VERSION only. |
| BLO-05 / F3-RUN-ATTEMPT | Genuine fresh actual attempt, issuer ID and immutable revision receipt, experiment parent and original receipt semantics/witness. |
| BLO-06 / RESULT | F3-owned method/metric schemas, experiment, mature realized inputs and actual computation/code/protocol/limitations. |
| BLO-07 / EVIDENCE | Issued subject and reviewed semantic evidence/provenance/limitations; private original attempt details remain separately authorized and never SAFE. |
| BLO-08 / F5-DECISION | F5-owned predeclared policy/action/execution rules and issued time-available observations/sequence position, with release rights. |
| BLO-09 / F5-EVALUATION | F5 evaluation declarations and actually mature prices/outcomes/decisions/metrics/cost/window evidence; no invented trade or return. |

IF04 transport/current principal-grant-resource-operation verification and immutable
receipts, IF05 separate positive/negative eligibility predicates, and IF07 real
source rights/history remain unavailable for release. Channel A genuine Native
reissue is not run or authorized here. Channel B has only author test-only
reconstruction of the bounded existing positives, not a production Codec or
whole-path replay. F3/F5/F6 consumers and TypeScript parity remain separate gates.
All five diagnostic scope flags remain unchanged; no count/value/hash/RUN or
VALUE_AVAILABLE implies ELIGIBLE or INELIGIBLE.

**Limited depth P2.** Ratified text bounds record depth at 64 but does not resolve
whether the root is depth 1 or 0. Recommended convention: root record = 1,
immediate nested record = 2, arrays add no record level themselves. Alternative:
root = 0, immediate nested record = 1. For a chain of 64 records, both readings
are within the depth bound; for 65 records, root=1 rejects while root=0 is within
the bound. These are conditional outcomes for P2-DEPTH-64/65, not valid complete
payloads or frozen conformance. Reviewer/Owner resolution is still required;
the author's implementation recursion budget supplies no normative answer.

**Final verification commands/results.** All commands used the existing locked
toolchain; no dependency/framework/config change was made:

| Command | Final result |
| --- | --- |
| `uv run --locked ruff check tests/unit/mvp_f2/test_wu05_oracle01.py tests/unit/mvp_f2/wu05_oracle_reference.py` | PASS |
| `uv run --locked ruff format --check tests/unit/mvp_f2/test_wu05_oracle01.py tests/unit/mvp_f2/wu05_oracle_reference.py` | PASS; two files formatted |
| `uv run --locked pytest -q tests/unit/mvp_f2/test_wu05_oracle01.py` | PASS; 97 tests |
| `uv run --locked pytest -q tests/unit/mvp_f2/test_resource_bodies.py` | PASS; 75 tests, 39 subtests; existing public Native entrypoints trapped |
| `uv run --locked mypy src/pit_research_lab` | PASS; 47 source files |
| `git diff --check` plus additive-path/empty-index inspection | PASS; no tracked modification or staged content |

The helper is intentionally test-only and was not separately mypy-checked. Full
`make check`, WU04 runtime tests, integration/database/service checks and Native
replay were not run. Legitimate uncommitted additions make the checkout dirty;
existing provenance guards must remain intact for the Owner's later clean-commit
CI. Initial authoring mistakes were corrected before these final results.

**ORACLE-02 handoff.** Reconstruct B01, B06 and Unicode/mutation/boundary samples
with a separate implementation and contract reading; compare stored bytes exactly,
then review all refusal/category claims, dependency closure, the depth P2 and the
scope-audit deviation above. Treat this author's helper and tests as one authoring
implementation. Freeze only the independently proven, precisely named subset.
Obtain missing owner evidence for blocked positives before authoring their
expected bytes. Production WU05-CAN, Native reissue and Git integration require
their own authorized stages; this author does not perform the reviewer's freeze.
