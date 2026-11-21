# F6 Fixed Synthetic F3-L1 Research Projection v0.1

Task: MVP-P1-01 / F6-08. Owner-authorized scope: eight additive contract/projection/test/fixture/document files. Base: `785d57d6d3f81236355b22c1089e2b829a3f3fcb`. Implementation remains pending separate Independent Review and Owner adjudication. This document reports no actual experiment, native artifact verification, replay execution, server or browser result.

## 1. Scope and trust boundary

The family literal is `F6_FIXED_SYNTHETIC_F3_L1_RESEARCH_V0.1`; the fixed capability is `fixed-synthetic-f3-l1-v0.1`. It represents the authored synthetic weekly F3-L1 research experiment independently of the seven M0 DTOs. It is not M0 ResearchClient compatibility, IF-03 issuance, a single-snapshot representation or F5 policy/evaluation output.

`contracts.py` defines named immutable wire representations and explicit recursive validators. `projection.py` contains only deterministic projections of supplied detached values. Both use standard library only and import no native runtime, backend or test fixture. Neither module reads files, starts processes, accesses a network/catalog, observes runtime readiness, verifies artifacts or releases results.

**Every `WireDocument`, including `VerifiedResultView`, is a schema-checked, unauthenticated CLAIM.** Its constructor/parser validates syntax and local consistency, including the shape of a PASSED/AVAILABLE claim. It does not authenticate that claim. The stored canonical bytes detach input containers; `to_wire()` returns a new copy. There is no authenticated flag/token, success-producing verifier stub or convenience result-release constructor. P1-03 must independently establish execution, native directory verification, app/attempt binding, safe bytes and durable publication before serving any result. Passing `isinstance(value, VerifiedResultView)` is not a release gate.

The only capability projection constructor is `project_unavailable_capability`. It remains UNAVAILABLE even when a caller supplies a policy hash. Missing required build/provenance identifiers refuses rather than inventing them. `validate_submission_selection` is pure comparison/refusal, not submission acceptance, idempotency persistence or runtime authority.

## 2. JSON, scalar and union rules

All seven shapes and every nested object are closed: missing and extra keys, incorrect kinds, unknown versions and incompatible union branches refuse with `ContractError`, whose `Reason` code never echoes supplied data. JSON decoding rejects duplicate keys at every nesting depth, floats/exponents, NaN/Infinity, invalid UTF-8 and invalid JSON. Serialization refuses non-JSON objects, tuples, non-string keys and invalid Unicode surrogates; there is no generic trusted dictionary passthrough.

The implementation uses explicit per-shape validators rather than a dynamic schema/plugin engine. Validated wire types store immutable canonical bytes; nested `MetricsValue`, `FactTraceValue`, `SourceSummaryValue`, `ObservationTraceValue`, `SafeReceiptValue`, `FoldResultValue` provide the same detachment/closure rule. Input dictionaries are parsing boundaries, not trusted production contracts. These types deliberately carry no authentication capability.

| Type | Rules |
|---|---|
| UUID | Canonical lowercase hyphenated UUIDv4; App Run and Native Attempt are different named fields/entities |
| SHA256 | Exactly 64 lowercase ASCII hexadecimal characters |
| UInt | Exact Python/JSON integer excluding Boolean, from 0 through 2^53−1 |
| UIntText | Canonical unsigned decimal string; no leading zeros, sign, float conversion or artificial numeric truncation |
| App timestamp | Calendar-valid ISO8601 `YYYY-MM-DDTHH:MM:SS[.1..6 digits]+00:00` |
| Native semantic timestamp | Calendar-valid original `YYYY-MM-DDTHH:MM:SS+08:00`; no inferred wall/fit/decision equivalence |
| Slot<T> | Exactly `{state:"PRESENT",value:T}` or `{state:"UNAVAILABLE",reason:Reason}`; never value+reason or bare null |
| NativeDigestRef | Exactly `{kind:<closed ReferenceKind>,sha256:<SHA256>}`; expected kind checked at each field |
| Failure | Exactly `code`, `native_code:Slot<safe uppercase native code>`, `first_observed_at`, `stage:Slot<NativeStage>` |

`Reason`, `Kind`, `ReferenceKind`, `Execution`, `Pit`, `Provenance`, `VerificationState`, `ReleaseState` and `FactState` are explicit closed enums. Native selection/fact/exclusion reasons have fixed supported registries; unreviewed variants refuse. Closed refusal records preserve an explicitly supplied safe native state/reason where available. The code does not invent unknown-cause information absent from the native safe record.

Finite transport/body/storage/process limits are not assigned here. Native count/digit grammar is enforced; resource quotas, bounded native file reads, request depth/size admission and operational limits belong to P1-03 and require separately approved values.

## 3. Response envelope and seven objects

All response kinds except ERROR have exactly:

`schema_version`, `kind`, `non_if03:true`, `data_mode:SYNTHETIC_GOLDEN`, `pit_status:UNRESOLVED|WITHHELD`, `execution_status:Execution`, `evidence_class:UNVERIFIED`, `execution_provenance:NOT_EXECUTED|ACTUAL_F3_CLI|FIXTURE_ONLY`, `source_refs:SourceRef[]`, `limitations`, `payload`.

SourceRef is exactly `kind:AUTHORED_SYNTHETIC_DECLARATION`, `source_ref:Slot<string>`, `version_ref:Slot<string>`, `qualification_ref:Slot<SHA256>`. There are no raw audit handles, filesystem output paths or source-data bodies. The eight native limitations, followed by the four application limitations in the code, are mandatory in exact order. FIXTURE_ONLY additionally requires `DISPLAY_SCENARIO_NOT_EXECUTED_RESEARCH` and actual execution NOT_RUN.

The field-level P1-00 Bridge Contract and Test Matrix remains the governing design. This section records the implemented closed shapes. Names separated by commas below are individual required fields, not arbitrary dictionaries.

### CapabilityDescriptor / CAPABILITY

Payload keys: `capability_id`, `capability_revision`, `readiness`, `unavailable_reasons`, `submission_gate`, `question`, `h0`, `h1`, `method_id`, `native_protocol_schema`, `protocol_ref`, `source_bytes_sha256`, `manifest_bytes_sha256`, `dataset_digest`, `decision_frequency`, `cutoff_count`, `issuer_count`, `horizon_sessions`, `seed`, `folds`, `numeric_policy`, `application_build_ref`, `native_provenance_basis`, `resource_policy_ref`, `replay_modes`.

Fixed facts: authored synthetic, WEEKLY, 96 decision cutoffs, five issuers, 480 issuer/tick observations, OLS_INTERCEPT_ONE_REGRESSOR_V1, seed 17, horizon 20 subsequent sessions. F1 is history [0,48), test [48,72); F2 is history [0,72), test [72,96). The native numeric policy is FRACTION_REDUCED_4096_DECIMAL50_FIXED12_HALF_EVEN_V1. Fixed question/H0/H1 and native version must match the transcription. Extra configuration knobs refuse.

Readiness is EXECUTABLE or UNAVAILABLE with consistent reason-list cardinality; unavailable policy cannot have EXECUTABLE or OPEN submission. Shape-valid executable claims are unauthenticated wire records only. `project_unavailable_capability` never creates one. Native provenance/app build hashes are explicitly supplied rather than observed by this module.

### SubmissionRequest / SUBMISSION_REQUEST

No response envelope. Exact keys: `schema_version`, `kind`, `capability_id`, `capability_revision`, `data_mode`, `idempotency_key:UUIDv4`.

Method/seed/cutoff/path/argv/environment/script override fields refuse, even if set to fixed defaults. Current-revision/readiness/gate checking is a separate pure `validate_submission_selection` operation. No HTTP handling, durable idempotency or job launch exists here.

### ApplicationRunReceipt / RUN_RECEIPT

Payload keys: `app_run_id`, `run_kind:EXPERIMENT|FRESH_REPLAY`, `replay_of_app_run_id`, `accepted_at`, `idempotency_key`, `request_fingerprint`, `capability_id`, `capability_revision`, `native_refs`, `status_path`.

Original runs require unavailable NOT_A_REPLAY relation. Fresh replay requires a different PRESENT original App ID. Paths must equal the fixed relative route constructed from the exact UUID. This is path grammar validation, not an implemented route. Missing native identities remain tagged slots, not dummy UUIDs.

### RunStatusResponse / RUN_STATUS

Payload keys: `app_run_id`, `run_kind`, `replay_of_app_run_id`, `catalog_revision:UIntText`, `phase`, `accepted_at`, `updated_at`, `started_at`, `finished_at`, `native_refs`, `native_execution_status`, `completed_stages`, `first_failure`, `release`, `result_path`, `evidence_path`.

Phases: INTENT_RECORDED/STARTING map to PENDING; NATIVE_RUNNING/VERIFYING to RUNNING; COMPLETE to SUCCEEDED; FAILED/BLOCKED remain independent failure/refusal; RECONCILING permits PENDING/RUNNING. Fixture actual NOT_RUN never permits an active/completed native phase in the production payload; simulated execution belongs outside that payload. Native SUCCEEDED during VERIFYING is allowed without app success or result release. COMPLETE needs all native references, native SUCCEEDED, complete ordered stages and start/finish times. A historically completed run may have BLOCKED/INVALIDATED release without rewriting execution history.

Completed-stage records are exactly `stage`, `finished_at`, `elapsed_ns:UIntText`, in the native stage-prefix order. Unknown/reordered stages refuse. Native execution is a slot over RUNNING/SUCCEEDED/FAILED. Release is exactly `state`, `reason`, `verification`. Verification is exactly `state`, `scope`, `checked_at`, `manifest_sha256`, `failure`. PASSED requires time/manifest and no failure; AVAILABLE requires PASSED, NO_FAILURE reason, COMPLETE actual execution, no withholding and exact result/evidence relative paths. These are consistency rules for claims, not independent verification.

### REM01 — Normative RUN_STATUS lifecycle closure

This P1-01 contract remediation resolves independent review findings P2-01 and
P2-02. `_status` validates payload shape and native fields; `_status_lifecycle`
**must** then validate the entire response envelope. All named RUN_STATUS decode
and construction paths call both. Neither function observes/authenticates a
process or authorizes release.

| Phase | Actual execution / provenance | Native identity/progress and app timestamps | Release and first failure |
|---|---|---|---|
| INTENT_RECORDED | PENDING / NOT_EXECUTED | Start/finish unavailable; all six native refs, native status and stages unavailable/empty | No AVAILABLE; verification NOT_CHECKED; known app cause may be retained |
| STARTING | PENDING / NOT_EXECUTED until launch proof | Same no-launch rule; mere launcher startup is not an observed F3 attempt | No AVAILABLE; verification NOT_CHECKED |
| NATIVE_RUNNING | RUNNING / ACTUAL_F3_CLI, observed start required | Any already-known valid subset of refs/stages/status may be retained; partial/missing attempt is permitted; finish unavailable | No AVAILABLE; app verification NOT_CHECKED; early native SUCCEEDED does not promote app success |
| VERIFYING | RUNNING / ACTUAL_F3_CLI, observed start required | Preserve the native SUCCEEDED claim, or still-unavailable/partial polling metadata while checks are in progress; finish unavailable | No AVAILABLE; complete native refs, SUCCEEDED and all stages required before claiming PASSED verification |
| RECONCILING before launch proof | PENDING / NOT_EXECUTED | No start/finish, attempt/status/stages or experiment/result/evidence artifacts; already-known fixed protocol/dataset **input pins** may remain PRESENT | No AVAILABLE; verification NOT_CHECKED; retain a known first cause |
| RECONCILING after launch proof | RUNNING / ACTUAL_F3_CLI, original observed start retained | Preserve known partial refs/progress/native status; do not require a complete attempt. A previously recorded finish time may remain as evidence, without implying success | No AVAILABLE; unknown outcome does not grant success; known failure remains PRESENT |
| COMPLETE | SUCCEEDED / ACTUAL_F3_CLI | Complete native refs, native SUCCEEDED, all eleven stages, start/finish required | AVAILABLE + PASSED, or historical BLOCKED + INVALIDATED; run first_failure remains UNAVAILABLE(NO_FAILURE) in both |
| FAILED | FAILED / ACTUAL_F3_CLI, observed start/finish | Native metadata may be partial or unavailable if no usable receipt was written; preserve already-known values | No AVAILABLE; first_failure must be PRESENT(Failure), never any UNAVAILABLE branch or PRESENT(NO_FAILURE) |
| BLOCKED before launch proof | BLOCKED / NOT_EXECUTED | No native execution artifacts/start/progress; optional app finish describes finalization of the nonexecution gate | BLOCKED release; pure policy/input refusal may have NO_FAILURE; known launch/recovery/application failure must be PRESENT |
| BLOCKED after launch proof | BLOCKED / ACTUAL_F3_CLI, original start required | Preserve known refs/status/progress; orphan/outcome uncertainty need not have a finish or a readable attempt | BLOCKED release; first_failure must be PRESENT, using the known app cause without inventing native errors |
| FIXTURE_ONLY | Unconditional actual NOT_RUN / FIXTURE_ONLY | Only prelaunch INTENT_RECORDED/STARTING or a nonexecution BLOCKED gate; no start, native refs/status/stages or performed verification | No AVAILABLE; existing WITHHELD gate remains valid. Simulated COMPLETE, VERIFYING or native success belongs in an external test wrapper |

The fixed protocol/dataset pins allowed in pending RECONCILING are input
identities, not issued execution artifacts; INTENT_RECORDED/STARTING and
prelaunch BLOCKED do not populate their native refs. No attempt/result/evidence
identity is invented. A PRESENT partial native reference does not require every
other reference to be PRESENT after actual launch.

P1-00's full-attempt requirement remains a prerequisite for claiming successful
native-directory/app-link verification and for COMPLETE/release (G04–G09), not a
reason to suppress a truthful RUNNING status while inspecting missing/malformed
candidate bytes. VERIFYING polling metadata is not proof that verification has
passed. No G01–G11 gate is implemented or waived here.

App accepted_at <= observed started_at <= observed finished_at <= updated_at
applies to whichever app timestamps are PRESENT; equality is valid. Missing
start is permitted only for truthful nonexecution states; a prelaunch BLOCKED
gate may have its own app finalization time. RECONCILING after observed launch
may retain a known finish time without inferring a final process/research
outcome. First-observed failure time must fall within accepted_at..updated_at;
it need not equal a native stage or semantic fit/decision cutoff. Native stage
ordering and typed native timestamps remain unchanged.

For BLOCKED, absence of a first failure is permitted only for a prelaunch
policy/input gate whose release reason is one of the existing NATIVE_WITHHELD,
SERVICE_NOT_READY, STORAGE_BLOCKED, RESOURCE_LIMIT, SOURCE_REFERENCE_MISSING or
NATIVE_UNKNOWN_STATE codes. These describe refusal, not failed native execution.
LAUNCH_INTERRUPTED, recovery/orphan, timeout, nonzero exit, verification/integrity
and internal-operation problems preserve a PRESENT typed first cause. No
native_code or native stage is fabricated when the cause is application-side.
A child nonzero-exit/timeout cause requires actual-launch provenance; a
prelaunch launcher/recovery problem uses its truthful application-side code.
Native FAILED, failed verification or a recorded operation-failure release
reason cannot coexist with NO_FAILURE in a non-COMPLETE snapshot.

Release INVALIDATED is historical COMPLETE only. Its failure remains in the
verification record and does not rewrite run first_failure, execution status,
original native refs, progress, or start/finish times.

`validate_status_continuity(previous, current)` compares two already-closed,
unauthenticated RunStatusResponse values. It preserves an existing first failure
verbatim; preserves observed launch provenance/start; prevents historical
COMPLETE becoming FAILED/BLOCKED due solely to release corruption; and, on
RECONCILING, preserves known refs, a known native-status slot, the previous progress prefix and any recorded
finish. This is a pure consistency check, not a catalog or general transition
engine. A future P1-03 catalog must retain the prior record and call the check:
a standalone snapshot cannot discover whether a caller erased earlier facts.

Fixture simulation example (test-only enclosing record, not a new DTO):

```text
{scenario_execution_status:"SUCCEEDED", wire:<FIXTURE_ONLY, actual NOT_RUN, no native progress>}
```

The existing authored WITHHELD/BLOCKED/FIXTURE_ONLY fixture and its exact
manifest bytes remain unchanged. The former permissive unit-test acceptance of
FIXTURE_ONLY + VERIFYING/native SUCCEEDED is replaced by an explicit refusal.

### VerifiedResultView / VERIFIED_RESULT

Payload keys: `app_run_id`, `native_refs` (complete), `verification` (PASSED claim), `question`, `h0`, `h1`, `method_id`, `decision_frequency`, `horizon_sessions`, `seed`, `interpretation`, `aggregate`, `folds`, `dependence`. Envelope must claim actual SUCCEEDED, PIT UNRESOLVED, evidence UNVERIFIED. WITHHELD/fixture claims cannot disclose a result.

Metrics has exactly `n`, `exact`, `display`, `oos_improvement`, `units`, `iid_inference`, `adjacent_residual_pairs`, `diagnostic_interpretation`. Exact/display metric names are explicitly enumerated in METRIC_NAMES. Adjacent residual product has an explicit availability slot matching pair count. Display additionally has native `rmse` and slotted `oos_improvement`. Zero baseline remains `{state:NOT_COMPUTABLE,reason:ZERO_BASELINE_SSE}` with unavailable display. No statistical recomputation is performed.

FoldResult has exactly `fold`, `state_id`, `fit_cutoff`, `history_candidates`, `test_ticks`, `training_count`, `training_cutoffs`, `training_issuers`, `scored_count`, `scored_cutoffs`, `excluded_training_count`, `exclusion_counts`, `latest_training_label_availability`, `distinct_issuer_month_releases`, `distinct_source_versions`, `alpha`, `beta`, `gbar`, `rbar`, `metrics`. Fold order/ranges and native sample floors are validated. The native coefficient fractions are copied. Aggregate count equals the sum of fold scored counts; no averages/financial metrics are invented.

Dependence has exactly `weekly_rows_are_independent:false`, `target_overlap:true`, `overlapping_within_issuer_scored_window_pairs`, `common_price_shocks:true`, `effective_sample_size:NOT_ESTIMATED`, `interpretation:NO_H0_REJECTION_OR_POPULATION_INFERENCE`.

### EvidenceProvenanceView / EVIDENCE_PROVENANCE

Payload keys: `app_run_id`, `native_refs`, `verification`, `evidence_scope`, `test_execution_attestation`, `application_build_ref`, `resource_policy_ref`, `native_code_claim`, `native_base_head`, `runtime`, `source_file_pins`, `source_bytes_sha256`, `manifest_bytes_sha256`, `artifacts`, `source_summary`, `observation_trace`, `native_receipts`.

Source file/code pin shapes and relative provenance path families are closed. No filesystem path is resolved/read. The ten artifact descriptors have exact names/roles, UIntText lengths and SHA256. Native experiment/result/evidence reference claims must agree with corresponding descriptor hashes. The app supplies attempt/evidence outer pins; neither is appended to the native evidence artifact inventory.

SourceSummary is the exact closed native source-summary key set, with a domain-tagged dataset digest. Preserve admission_eligible=false, source_authentication=NOT_ESTABLISHED, authored scope and invocation-count-scope text. Validate 96 ordered distinct cutoff strings and the five fixed issuers. ObservationTrace is `sample_id`, `issuer`, `tick`, `cutoff`, `binding_id`, `current`, `previous`; validate the 480-member tick/issuer grid and cutoff membership. Relevant withholding prohibits result/evidence disclosure.

FactTrace is `month`, `state`, `native_state`, `reason`, `source_ref`, `version_ref`, `qualification_ref`, `publication`, `available_at`, `unit`, `basis`. Optional facts use tagged slots; amount is deliberately omitted. KNOWN requires source/version/qualification/time refs. SafeReceipt is `qualification_ref`, `schema`, `non_if03`, `dataset_digest`, `cutoff`, `subject`, `state`, `reason`, `native_invocation`, `selected_sources`, `code_pins`, `revenue_value_qualification`. Native receipt hashes are checked before projection; revenue amount/private graphs are omitted. Required qualifier links cannot dangle.

### BasicReplayResult / BASIC_REPLAY_RESULT

Payload keys: `original_app_run_id`, `replay_app_run_id`, `mode`, `state`, `original_native_refs`, `replay_native_refs`, `original_verification`, `replay_verification`, `basis_check`, `comparisons`, `compared_at`, `first_failure`, `scope`, `attempt_metadata_policy`.

Mode is FRESH_PROCESS_NATIVE_RESEARCH_REPLAY. States are NOT_RUN/PENDING/RUNNING/MATCH/MISMATCH/NOT_COMPARABLE/FAILED/BLOCKED. MATCH/MISMATCH claims require complete refs, distinct App/Attempt IDs, PASSED verification claims, SAME basis, comparison time and all nine deterministic file descriptors. Equal/different byte-claim flags and hashes must be locally consistent; MATCH requires all equal and matching native content refs. NOT_COMPARABLE is separate from scientific mismatch. Attempt wall-time/duration bytes are excluded. This contract does not execute replay or prove byte equality/process independence.

ERROR is a supporting closed shape: `schema_version`, `kind:ERROR`, `code:Reason`, `request_id:UUIDv4`, `app_run_id:Slot<UUIDv4>`. Transport-only endpoints, session/CSRF and fresh-replay submission handling are not implemented by this slice.

## 4. Native mapping ledger

Paths below refer to the unchanged native files at the declared base.

| Implemented projection/type | Source / meaning | Preserved or excluded |
|---|---|---|
| fixed_protocol / capability | `f3_l1/contracts.py:12–23,73–145` | Exact protocol question/method/seed/folds/horizon/policies/limitations; no parameter overrides |
| source/manifest/dataset pins | `f2/research_panel.py:34–42,690,886–909` | Raw source and research-JSON dataset remain separate domains even if their current digest strings agree |
| project_metrics / MetricsValue | `f3_l1/experiment.py:393–447` | Fraction and native display copied; native optional adjacent/null improvement become explicit slots |
| project_fact / FactTraceValue | `f2/research_panel.py:94–107,545–574` | State/reason/source/version/times retained; amount omitted; missing KNOWN refs refuse; withheld refuses disclosure |
| project_observation / ObservationTraceValue | `f2/research_panel.py:110–159,751–774` | Check local native binding payload hash and retain native binding kind; no snapshot alias |
| project_receipt / SafeReceiptValue | `f2/research_panel.py:482–542` | Check complete supplied native receipt hash; omit revenue value and any raw/private graph |
| project_source_summary / SourceSummaryValue | `f2/research_panel.py:861–879` | Explicit same-key safe mapping plus typed dataset ref; no app admission/source authentication |
| project_fold / FoldResultValue | `f3_l1/experiment.py:225–237,553–579` | Join exact state/fold/training IDs, check local state hash, count verified-shape list members, copy coefficients/metrics |
| NativeRefs / result/evidence shape | `f3_l1/replay.py:129–207,285–381` | Native spec/result/evidence/protocol/dataset identities distinct from App Run and native attempt |
| lifecycle / verification claim types | `f3_l1/replay.py:98–227` | Native saved SUCCEEDED precedes native final verify; never independently grants app success |
| selected native states/reasons | `domain/selection.py:356–358,1441–1492` static dependency read | Supported S3 safe state/reason registry only; unknown variants refuse |
| local research byte hashing | `research_vslice/contracts.py:56–76` | Same integer/string native payload preimage rules for transcription checks; explicitly not IF-03 |

No native module is imported by production F6 or these tests. Static tests read AST/literal declarations and fixed fixture bytes without executing any native code. Copies of native invocation strings such as RUN are claims from supplied records, not an attestation generated by projection.

## 5. Application-control fingerprint bytes

Local control JSON is recursively exact JSON (no floats/nonfinite/custom objects), object keys sorted lexicographically, separators `,` and `:`, ensure_ascii=false, UTF-8, no Unicode normalization and **no trailing newline**. Invalid scalar strings refuse. Fractions are decimal-string pairs, never JSON numbers. Native content and IF-03 framing are separate domains.

Capability preimage:

```text
UTF8("F6_FIXED_RESEARCH_CAPABILITY_V0.1") || 0x00 || control_json(basis)
basis = {"schema_version": FAMILY, **immutable_capability_payload_fields}
```

Immutable capability fields are every required capability payload key except capability_revision, readiness, unavailable_reasons and submission_gate. The injected schema_version explicitly resolves P1-00's “include schema/version; exclude common envelope” wording: only this version literal is included, not common status/source/provenance fields. Exact immutable field key sets are validated before fingerprinting; unknown fields are not silently stripped. Build/provenance/policy hashes are identity-bearing. Runtime availability/busy status is not. Full descriptor validation also checks its declared revision against these bytes.

Submission preimage:

```text
UTF8("F6_FIXED_RESEARCH_SUBMISSION_V0.1") || 0x00 || control_json(request_without_idempotency_key)
```

Validate the exact six-key fixed request before removing only idempotency_key. schema_version/kind/capability ID/revision/data mode remain. SHA256 of the full preimage produces the control fingerprint. The same accepted shape with a different idempotency key has the same request fingerprint; durable key handling is deferred.

The literal exact byte vectors and SHA256 expectations are embedded independently in `test_contracts.py` as EXPECTED_CAPABILITY_BYTES, EXPECTED_SUBMISSION_BYTES and EXPECTED_PROTOCOL_BYTES. The external handoff packet repeats their complete bytes/hex and hashes. Vectors use authored build hash `a` repeated 64, provenance hash `b` repeated 64 and an unavailable NOT_YET_AVAILABLE policy. These are test values, never observed build/runtime evidence.

| Vector | Expected SHA-256 |
|---|---|
| Native fixed Protocol payload, separate native domain | `b5e30ec4033541cb9ec9ad542053430d495532b56298a99c418f6b945c95af66` |
| Capability control bytes with the authored basis above | `92463e70be9a0a66762c7481ca3ffb70a1e39abe810df8dcc5c6417858e4caf9` |
| Submission control bytes with capability_revision = 64 zero characters | `997de81ef50bc5e0f9eed4058ac170b856d5bc467fb4131180b4f4c6896f6be0` |

### Literal application-control vectors

These Python byte-literal spellings denote the exact complete preimages. The
`\x00` escape denotes one NUL byte, not four printed characters. No newline is
part of either preimage. They match the independently embedded test literals.

```python
CAPABILITY_BYTES = b'F6_FIXED_RESEARCH_CAPABILITY_V0.1\x00{"application_build_ref":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","capability_id":"fixed-synthetic-f3-l1-v0.1","cutoff_count":96,"dataset_digest":{"kind":"F2_PANEL_RESEARCH_BYTES","sha256":"8c2b03e3875e2029a3d9e0534588b76a5e470e944cea746fdd1fb7aba917927d"},"decision_frequency":"WEEKLY","folds":[{"history_end":48,"name":"F1","test_end":72,"test_start":48},{"history_end":72,"name":"F2","test_end":96,"test_start":72}],"h0":"beta = 0","h1":"beta != 0","horizon_sessions":20,"issuer_count":5,"manifest_bytes_sha256":"7b0cb1bec7b4d42ea55670eeb9d8ee4b744e7c39368cadd7e0eb1298deeb3219","method_id":"OLS_INTERCEPT_ONE_REGRESSOR_V1","native_protocol_schema":"F3_L1_RESEARCH_V0.1","native_provenance_basis":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","numeric_policy":"FRACTION_REDUCED_4096_DECIMAL50_FIXED12_HALF_EVEN_V1","protocol_ref":{"kind":"F3_PROTOCOL_PAYLOAD","sha256":"b5e30ec4033541cb9ec9ad542053430d495532b56298a99c418f6b945c95af66"},"question":"Does PIT monthly revenue growth predict subsequent synthetic returns?","replay_modes":["NATIVE_DIRECTORY_VERIFICATION","FRESH_PROCESS_NATIVE_RESEARCH_REPLAY"],"resource_policy_ref":{"reason":"NOT_YET_AVAILABLE","state":"UNAVAILABLE"},"schema_version":"F6_FIXED_SYNTHETIC_F3_L1_RESEARCH_V0.1","seed":17,"source_bytes_sha256":"8c2b03e3875e2029a3d9e0534588b76a5e470e944cea746fdd1fb7aba917927d"}'
SUBMISSION_BYTES = b'F6_FIXED_RESEARCH_SUBMISSION_V0.1\x00{"capability_id":"fixed-synthetic-f3-l1-v0.1","capability_revision":"0000000000000000000000000000000000000000000000000000000000000000","data_mode":"SYNTHETIC_GOLDEN","kind":"SUBMISSION_REQUEST","schema_version":"F6_FIXED_SYNTHETIC_F3_L1_RESEARCH_V0.1"}'
```

## 6. Exact numbers and identity domains

ExactFraction validates signed canonical numerator strings and positive canonical denominator strings, gcd=1, canonical zero 0/1, at most 4096 digits excluding a numerator minus. No plus, leading zeros, negative zero, zero/negative denominator, floats or rounding. Validation uses integer gcd, not floating point. Native display strings are preserved at 12 places with normalized zero; no authoritative display or RMSE is recomputed. NOT_COMPUTABLE remains tagged with ZERO_BASELINE_SSE. UInt is reserved for bounded counts/indexes; durations and byte lengths use UIntText.

App Run UUID is not the native Attempt UUID; native experiment/protocol/result/evidence/dataset/binding/state/prediction/training refs have different ReferenceKind tags. The source raw-byte SHA, manifest SHA and native semantic dataset digest are distinct fields. Capability revision and submission fingerprint use separate application domains. No binding ID is a SnapshotReference or snapshot_id. No App ID is inserted into native deterministic bytes. Reading/hash-checking a supplied native payload is not canonical cross-schema equivalence or evidence of source authenticity.

## 7. Conservative axes and disclosure

`project_axes` always yields actual NOT_RUN with NOT_EXECUTED or FIXTURE_ONLY. It never asserts observed child execution. KNOWN/SUPPORTED/SELECTED/SUCCEEDED/hash equality cannot promote PIT. Unknown safe native variants return NATIVE_UNKNOWN_STATE with safe supplied state text. Relevant WITHHELD takes precedence, including mixed unknown/withheld input, and suppresses disclosure. Actual app lifecycle projection from observed execution belongs to P1-03.

PIT in this family is UNRESOLVED or WITHHELD only. Evidence Class is always UNVERIFIED. Data Mode remains SYNTHETIC_GOLDEN, explicitly not formal Golden acceptance. Verification and release are separate states. Native early success does not change app status to SUCCEEDED or unlock metrics. A negative/unfavorable OOS result does not become FAILED or imply scientific success. The native interpretation remains EXECUTION_COMPLETE_NO_CLAIM_OF_PREDICTIVE_EDGE.

Native limitations are retained verbatim:

1. AUTHORED_SYNTHETIC_INFRASTRUCTURE_ONLY
2. NOT_REAL_TWSE_OR_HISTORICAL_PIT_CERTIFICATION
3. NO_IF03_ISSUANCE_OR_IF05_ADMISSION
4. NO_IID_PVALUES_CI_OR_H0_REJECTION
5. REPEATED_MONTHLY_SIGNALS_AND_DEPENDENT_ENTITIES
6. OVERLAPPING_20_SESSION_OUTCOMES
7. DESCRIPTIVE_ASSOCIATION_AND_OOS_ASSESSMENT_ONLY
8. NO_CAUSAL_OR_PROFITABILITY_CLAIM

## 8. Authored fixtures

`tests/fixtures/mvp_f6/projection_v0_1.json` contains compact authored unavailable/WITHHELD/unknown cases, not generated F3 artifacts. `manifest_v0_1.json` records family/version, author/origin/purpose, exact UTF-8 byte length/SHA256 including final newline, synthetic display scope, FIXTURE_ONLY/actual NOT_RUN, no research execution attestation, no IF-03 issuance and no formal Golden acceptance. Production has no fixture import or file dependency.

Full result/evidence/replay representation examples are constructed only in pure tests. Their actual-looking statuses, fake identifiers/pins and invocation labels are deliberately unauthenticated shape-test inputs; no native process, verification or successful replay is asserted. Large 480-row test structures exist only in memory, not as a pseudo-experiment committed to fixtures.

## 9. Pure coverage and remaining work

| Planned test requirement | Pure implementation/test responsibility |
|---|---|
| T01 | Fixed capability identity/protocol/readiness refusal and revision vectors |
| T02/T03 | All seven shapes, missing/extra/version/kind/duplicate keys, JSON number/type refusal |
| T14 | Native reference tags, required slots, fixed protocol/dataset refs, nested hash/reference consistency |
| T18/T19/T20 | Unknown/WITHHELD precedence, no eligibility/evidence promotion, independent axes, no result disclosure |
| T21 | Fraction grammar/gcd/zero/4096-digit boundary/JS precision preservation, native display/units/NOT_COMPUTABLE |
| T27 | Authored fixture manifest/digest/provenance and actual NOT_RUN; no production fixture imports |
| T28 static only | Worktree import-root assertions, native AST/byte-pin transcription checks, stdlib-only import isolation |

The permitted command targets are exactly the two new test files and the new F6 package/test directory for Ruff/mypy. Actual command outcomes/tool versions belong in the external handoff report. This document does not count static examples as research execution or independent review.

P1-03 still owns safe filesystem reads, complete artifact/native-directory checks, source/code/runtime anchoring, App/Attempt process binding, durable catalog, idempotency, one-job enforcement, timeout/restart/orphan reconciliation and authenticated release. No transport limit/default quota/readiness is invented here. Browser, HTTP/session/CSRF, SQL/SQLite, subprocess/supervision, replay execution, F5 metrics, real data, production auth/cloud and RDE/Home/Guide/Hub remain excluded.

No existing F3/F2/M0/IF-03/dependency/configuration file is changed. Independent Review remains separate from executor self-tests. Stop after P1-01 implementation, scoped checks and evidence reporting; no subsequent slice or Git integration is authorized.
