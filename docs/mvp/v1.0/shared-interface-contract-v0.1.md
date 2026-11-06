# Academic MVP — Shared Interface Contract v0.1

- **Document version:** v0.1
- **Recording date:** 2026-11-06
- **Recording scope:** docs-only amendment; previously accepted construction; logical freeze pending Owner/independent review; no product/engineering acceptance.
- **Amendment task:** `MVP-M0-IF-FINAL-01`; `IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`.
- **Decision input:** `MVP-M0_Interface_Decision_Record_v0.1.md`, ID `PIT-MVP-M0-IF-DEC-20261106`, SHA256 `06376f07097e618bdb99c297d1ad73df9a38dfb3cc9433637608bd23f4d2b2b5`; technical proposal for this scope, not runtime/source/Git authority.
- **Acceptance dimensions:** `M0_DOCUMENT_CONSTRUCTION_ACCEPTED` (Owner-supplied prior independent review); `M0_CONTRACT_FREEZE_PENDING_REVIEW`; `TEAM_IMPLEMENTATION_NOT_AUTHORIZED`.
- **Approved M0 base:** `b3be0c0122dac804084d5e464f7bfc07313f02aa`; branch `mvp/m0-shared-contracts`.
- **Packet provenance:** `docs/mvp/v1.0/shared-interface-contract-v0.1.md` from `PIT_Research_Lab_v1.0_MVP-M0_Initialization_Packet_20261106.zip`; ZIP SHA256 `43033166586a50b78d569df81b7e0db8f9412544a351814ceaba818312b0bc98`. External text is input material, not operational authorization.

- **Status:** REVIEWED_DRAFT / M0_CONTRACT_FREEZE_PENDING_REVIEW / TEAM_IMPLEMENTATION_NOT_AUTHORIZED
- **Consumer:** F6 UI, F5 Evaluation; **Producer:** F2 Data, F3 Research
- **Meaning:** Application-facing logical DTOs; NOT new formal PIT or B04 authorization APIs.

## Principles

1. Source-of-truth semantics are owned by F2/F3/F5. UI renders but never certifies, reclassifies, or computes authoritative domain values.
2. The logical App proposal requires every result/envelope to carry `schema_version`, `data_mode`, `evidence_class`, `source_refs`, `limitations`, and the applicable independent `pit_status` / `execution_status` axes; placement in each concrete DTO remains an implementation design task. No unlabeled `is_verified` Boolean.
3. Time values must be timezone-aware ISO 8601, with UTC normalization for comparison and original timezone retained for display where appropriate. Distinguish decision time, release/publication evidence, observation time, and outcome availability.
4. `UNRESOLVED` means evidence insufficient, not false; `WITHHELD` means not released to this consumer; `NOT_RUN` is not PASS. Missing data must not silently be filled from post-cutoff sources.
5. All hashes and IDs carry explicit canonicalization rules. No `hash(PythonObject)` or noncanonical JSON. IF-03 blocks first M1 identity/replay acceptance until canonical bytes, digest domain separation, timestamp/number precision and replay oracle are approved; decision target 2026-12-15. M0 does not require implementation now or assert current App encoding behavior.
6. No secrets, raw protected resource handles, DB credentials, or raw traceback in response DTOs/fixtures/logs.
7. Existing Domain contracts and accepted Frozen Golden remain authoritative; use a translator adapter where semantics differ.

## Suggested type registry

| Logical DTO | Minimum fields (proposed) | Owner | UI invariant |
|---|---|---|---|
| `DatasetManifest` | `manifest_id`, `schema_version`, `data_mode`, `content_digest`, `source_refs[]`, `transform_version`, `period_coverage`, `evidence_class`, `limitations[]` | F2/F4 | Source facts display-only |
| `SnapshotReference` | `snapshot_id`, `manifest_id`, `decision_cutoff`, `pit_status`, `selection_version`, `eligible_items_ref`, `exclusions_ref`, `lineage_ref`, **PROPOSED** `qualification_trace_ref` (or equivalent evidence access) | F2 | No UI PIT recomputation |
| `ExperimentSpec` | `spec_id`, `hypothesis_id`, `hypothesis_version`, `snapshot_id`, `method_id`, `method_version`, `seed`, `evaluation_plan`, `temporal_policy` | F3 | Validate required inputs, do not invent method eligibility |
| `ResearchRun` | `run_id`, `spec_id`, `snapshot_id`, `execution_status`, `evidence_ref`, `started_at`, `finished_at`, `failure_code`, `limitations[]` | F3 | Status and evidence independently shown |
| `EvidenceBundle` | `bundle_id`, `run_id`, `input_manifest_digest`, `code_version`, `protocol_version`, `result_digest`, `metrics[]`, `diagnostics[]`, `artifacts[]`, `lineage_refs[]`, `limitations[]`, `evidence_class` | F3 | No automatic `PIT_VERIFIED` inference |
| `DecisionTrace` | `run_id`, `policy_id`, `decision_time`, `observation_ref`, `eligibility_status`, `action`, `cost`, `outcome_ref`, `limitations[]` | F5 | Evaluation labels shown separately from decision inputs |
| `EvaluationResult` | `run_id`, `benchmark_policy_id`, `policy_metrics[]`, `risk_metrics[]`, `cost_assumptions`, `comparison_method`, `evidence_ref`, `limitations[]` | F5 | Do not calculate authoritative P&L in UI |

All seven DTOs and logical `ResearchClient` remain **NEW_M0_PROPOSAL**. `mvp-app-v0.1` is a proposed new application schema family, not an implemented schema or a change to Domain `Record` / DB. Codex 02 static mapping below is historical; this task adds no new source audit. Never rename existing source symbols or invent `ApprovedDataSnapshot` to fit this registry. The logical port can be frozen in design only after independent review; concrete payload layout, translators and transport remain separately gated.

## Enumerations and states

`data_mode`: `SYNTHETIC_GOLDEN` | `REAL_TWSE_PILOT`.

`pit_status`: `ELIGIBLE` | `INELIGIBLE` | `UNRESOLVED` | `WITHHELD`.

`execution_status`: `NOT_RUN` | `PENDING` | `RUNNING` | `SUCCEEDED` | `FAILED` | `BLOCKED`.

`evidence_class`: `SYNTHETIC_VERIFIED_IN_SCOPE` | `REAL_SOURCE_OBSERVED` | `HISTORICAL_PIT_SUPPORTED_IN_SCOPE` | `PROVISIONAL` | `UNVERIFIED`.

These are **Application proposal labels** (not aliases for accepted formal Harness states). M0 must map old statuses carefully; do not implement state promotion rules before F2 Owner review. `SYNTHETIC_VERIFIED_IN_SCOPE` is only allowed after the corresponding synthetic oracle tests, not from mock UI fixtures.

## Data ownership and flow

```text
Read-only pinned dataset (F2/F4)
    -> F2 SnapshotReference / PIT qualification
    -> F3 ExperimentSpec -> ResearchRun -> EvidenceBundle
    -> F5 optional EvaluationResult + DecisionTrace
    -> F6 view-only presentation (source/evidence badges, statuses, controls)
```

No F6 direct access to PostgreSQL tables, migrations, Layer B runtime, p4m/p4s consumer, collection/testlease, filesystem secrets, or mutable original source snapshots.

## Logical client interface (not committed HTTP endpoints)

```ts
interface ResearchClient {
  listDatasets(): Promise<DatasetManifest[]>;
  getSnapshot(referenceId: string): Promise<SnapshotReference>;
  submitExperiment(spec: ExperimentSpec): Promise<ResearchRun>;
  getRun(runId: string): Promise<ResearchRun>;
  getEvidence(evidenceRef: string): Promise<EvidenceBundle>;
  getEvaluation?(runId: string): Promise<EvaluationResult>;
}
```

The proposed first F6 implementation would use a deterministic in-memory `FixtureResearchClient` after separate task approval. F3 would supply the proposed `BackendResearchClient` only when an owner-reviewed endpoint/DTO mapping is available. No framework, HTTP route, database, UI library, or persistent run engine is selected by this document.

## Contract-fixture pairs required for F6

- `M0-SUCCESS-SYNTH`: specification of a simulated synthetic eligibility/success scenario with persistent `FIXTURE_ONLY`; actual runner remains `NOT_RUN`. Only separately approved executed synthetic oracle evidence could later support real bounded synthetic claims.
- `M0-LATE-REVISION`: after-cutoff revision withheld/unresolved, no future data in observation.
- `M0-MISSING-EVIDENCE`: `UNRESOLVED`, missing publication/version binding.
- `M0-FORCED-WITHHELD`: evidence intentionally withheld, not converted to empty successful values.
- `M0-RUN-FAILURE`: protocol/runner failure shown as `FAILED`, no fabricated metric.
- `M0-POLICY-COMPARISON`: benchmark + A/B outputs from one exact snapshot; any dummy results labelled demo-only.

## M0 logical freeze scope and deferred implementation

本輪將 IF-01..07 處置列於下方 register；政策規則與延後閘門供獨立 review，不再把所有事項籠統稱為 OPEN。M0 design review 可審 DTO responsibility、三軸、no-promotion、fixture/role/dependency gates；不要求此刻實作 IF-03 hash、選定 IF-04 transport 或完成 IF-07 real-source certification。Runtime/source admission 一律另行授權。

## Change control

- Versioned additive changes to application contracts require owner approval and new fixtures/tests.
- No unreviewed breaking schema changes between F3 and F6.
- `v0.1` contract approval is **not** implementation acceptance.

## Repository compatibility record — 2026-11-06 (static only)

**Historical Codex 02 static audit, retained unchanged in its source table; no new source/runtime audit in MVP-M0-IF-FINAL-01.** The table records that audit-time finding (including then-open IF wording), not this round’s disposition. Current documentary policy is the IF register below. Audit base: `b3be0c0122dac804084d5e464f7bfc07313f02aa`, Owner-approved in the earlier implementation session. `VERIFIED_EXISTING` below verifies a source definition and inspected boundary, not runtime behavior, formal acceptance, or approval to call it now. `NEW_M0_PROPOSAL` means an application contract to be reviewed. `UNKNOWN/REQUIRES_OWNER_DECISION` means no accepted mapping or authority was established. These DTO proposals are not DB schemas, migrations, or revisions to existing domain/PIT semantics.

The eight candidate evaluator entry points have a statically inspected transitive closure of 13 domain modules, with standard-library and domain imports only; no runtime/database/test-fixture imports were found. Package initializers were also read. No project module was imported or executed. Evaluators take retained request/context/code-observation inputs; constructors, input integrity, timezone data availability and runtime compatibility remain untested. This is a source-level reuse candidate list for IF-01 review, not a runtime sandbox or an instruction to activate an adapter.

| Interface / symbol | Classification | Inspected source path and symbol | Compatibility limit |
|---|---|---|---|
| S1/S2 composition | `VERIFIED_EXISTING` | [pit_slice.py](../../../src/pit_research_lab/domain/pit_slice.py): `evaluate_slice(context, request, code, /)`, `SliceResult`; [information.py](../../../src/pit_research_lab/domain/information.py): `assess_evidence`, `inventory_content`; [temporal.py](../../../src/pit_research_lab/domain/temporal.py): `qualify_temporal`, `TemporalOutcome` | Supplied immutable inputs; provisional, diagnostic, not source authentication or admission. Temporal `SUPPORTED` is conditional. |
| As-of composition | `VERIFIED_EXISTING` | [asof_slice.py](../../../src/pit_research_lab/domain/asof_slice.py): `AsOfRequest`, `evaluate_asof(request, code, /)`; [selection.py](../../../src/pit_research_lab/domain/selection.py): `AsOfSelectionResult`, `SelectionOutcome` | Recomputes owners and selects; `SELECTED`, `UNRESOLVED`, `NO_QUALIFIED_CLAIM` are domain states, not app enum aliases. |
| Derived feature composition | `VERIFIED_EXISTING` | [derived_slice.py](../../../src/pit_research_lab/domain/derived_slice.py): `evaluate_derived(specification, slots, code, /)`; [derivation.py](../../../src/pit_research_lab/domain/derivation.py): `FeatureSpec`, `DependencySlot`, `DerivedResult` | Calls request-based upstream composition; retains failures and scoped lineage; no app snapshot authority. |
| Ratio composition | `VERIFIED_EXISTING` | [ratio_slice.py](../../../src/pit_research_lab/domain/ratio_slice.py): `evaluate_ratio(specification, sum_specification, slots, code, /)`; [ratio.py](../../../src/pit_research_lab/domain/ratio.py): `RatioCodeObservation`, `RatioResult` | Retains actual upstream result; finite numerical/domain restrictions still apply. |
| Synthetic universe qualification | `VERIFIED_EXISTING` | [causal_slice.py](../../../src/pit_research_lab/domain/causal_slice.py): `qualify_universe(request, code, context, /)`; [causal_derivation.py](../../../src/pit_research_lab/domain/causal_derivation.py): `UniverseRequest`, `QualifiedSyntheticUniverse`, `B03Refusal` | Bounded synthetic profile; refusals/failures preserved, no real-universe qualification inference. |
| Standardizer fit | `VERIFIED_EXISTING` | [causal_slice.py](../../../src/pit_research_lab/domain/causal_slice.py): `fit_standardizer(request, code, decision, /)`; [causal_derivation.py](../../../src/pit_research_lab/domain/causal_derivation.py): `StandardizerRequest`, `FitEvaluation`, `FrozenStandardizer` | Validates fit cutoffs and limited training rows; not a generic F3 statistical runner. |
| Causal composition | `VERIFIED_EXISTING` | [causal_slice.py](../../../src/pit_research_lab/domain/causal_slice.py): `evaluate_causal(request, code, /)`; [causal_derivation.py](../../../src/pit_research_lab/domain/causal_derivation.py): `B03Request`, `B03Result`, `B03CodeObservation` | Bounded public/synthetic/window/feature profiles; unsupported inputs may refuse; no general policy engine. |
| Diagnostic projection | `VERIFIED_EXISTING` | [diagnostic_projection.py](../../../src/pit_research_lab/domain/diagnostic_projection.py): `project_candidate(fixed_context, fixed_feature_specs, completed, universe, policy, code, /)`, `ProjectionPolicy`, `DiagnosticProjectionCandidate`, `ProjectionWithheld`, `ProjectionBlocked` | Replays causal evaluation; only SYN-A/SYN-B universe supported. Candidate is `WITHHELD`, `admission_eligible=False`, `diagnostic_only=True`, `NOT_TRUSTED_PIT_EVIDENCE`, `source_authentication=NOT_ESTABLISHED`. Never promote this candidate to an admitted snapshot. |
| Code observation helpers | `VERIFIED_EXISTING` | `pit_slice.py: observe_code`; `asof_slice.py: observe_asof_code`; `derived_slice.py: observe_derived_code`; `ratio_slice.py: observe_ratio_code`; `causal_slice.py: observe_causal_code` (linked above) | Explicit Git/disk I/O, separate from evaluators. Observed bytes are not attestation. Not executed here and not included as pure application operations. |
| Existing domain fact vocabulary | `VERIFIED_EXISTING` | [contracts.py](../../../src/pit_research_lab/domain/contracts.py): `Record`, `Known`, `Unknown`, `UnknownCause`, `NotApplicable`, `NotEvaluated`, `BlockingFailure`, `SemanticContext`, `AwareInstant`, `CodePin`, `ContentPin` | Tagged facts and origins cannot be collapsed to nullable values, false, empty metrics, or app success. `Record` validates its existing candidate schema; do not change it for app DTOs. |
| Existing offline manifest | `VERIFIED_EXISTING` | [source_intake.py](../../../src/pit_research_lab/domain/source_intake.py): `OfflineSourceManifest`, `FilePin`, `RightsRecord`, `IntakeResult`, `decode_manifest`, `inspect_offline_source` | Existing `a06-offline-csv-v0.1` schema is not `DatasetManifest`; intake has explicit filesystem/rights boundaries. No intake invocation or source authentication was performed. |
| Existing deterministic encoding | `VERIFIED_EXISTING` | [causal_derivation.py](../../../src/pit_research_lab/domain/causal_derivation.py): `semantic_bytes`, `identity`; [diagnostic_projection.py](../../../src/pit_research_lab/domain/diagnostic_projection.py): `SCHEMA = b03-diagnostic-candidate-v0.1` | B03-scoped serialization/identity only; diagnostic schema is not an application EvidenceBundle schema. |
| `DatasetManifest` | `NEW_M0_PROPOSAL` | No matching definition in inspected `src/`, `tests/`, `migrations/`; possible input reference: `source_intake.py: OfflineSourceManifest` | F2/F4 producer; F2/F3/F6 consumers. Translation/rights semantics pending IF-02/03/07. |
| `SnapshotReference` | `NEW_M0_PROPOSAL` | No matching definition; related diagnostic types: `asof_slice.py: AsOfRequest`, `selection.py: AsOfSelectionResult` | F2 producer; F3/F5/F6 consumers. No one-to-one domain or DB mapping; IF-02/05 pending. |
| `ExperimentSpec` | `NEW_M0_PROPOSAL` | No matching definition in inspected application source tree | F3 producer/owner; F3 runner and F6 consumers; no implemented protocol endpoint established. |
| `ResearchRun` | `NEW_M0_PROPOSAL` | No matching definition in inspected application source tree | F3 producer; F5/F6 consumers; lifecycle/transport pending IF-04/05. |
| `EvidenceBundle` | `NEW_M0_PROPOSAL` | No matching definition; `diagnostic_projection.py: ResearchAudit` is a different existing diagnostic wrapper | F3 producer; F5/F6 consumers; no existing authoritative bundle API established. |
| `DecisionTrace` | `NEW_M0_PROPOSAL` | No matching definition; `causal_derivation.py: DecisionRow` is a different domain input type | F5 producer; F3/F6 consumers; not a synonym for `DecisionRow`. |
| `EvaluationResult` | `NEW_M0_PROPOSAL` | No matching definition; `ratio.py: RatioResult` and `causal_derivation.py: B03Result` have different bounded purposes | F5 producer; F3/F6 consumers; no existing return/risk/policy comparison API established. |
| `ResearchClient` and methods `listDatasets`, `getSnapshot`, `submitExperiment`, `getRun`, `getEvidence`, optional `getEvaluation` | `NEW_M0_PROPOSAL` | No matching declarations in inspected source; TypeScript example in this document only | Logical UI port; neither HTTP routes nor a backend bridge currently established. |
| `FixtureResearchClient`, `BackendResearchClient` | `NEW_M0_PROPOSAL` | No matching definitions in inspected source | Future F6 fixture implementation / F3-owned backend mapping; no framework/dependencies selected. |
| Concrete DTO translators, status promotion, universal canonical hash, service transport and real-source admissibility | `UNKNOWN/REQUIRES_OWNER_DECISION` | No accepted app mapping found between the proposed registry and the inspected symbols above | IF-01..07 remain open; existence of a domain function does not settle mapping or authority. |
| `ApprovedDataSnapshot` | `UNKNOWN/REQUIRES_OWNER_DECISION` | Name searched in `src/`, `tests/`, `migrations/`: no match | Package comparison example only, not an implemented repository type. |

## IF-05 policy — three independent axes and fail-closed mapping

**Review status:** `POLICY_DOCUMENTED / TRANSLATOR_NOT_IMPLEMENTED`。這是依 Owner 提供的 Decision Record 納入本輪的政策提案，尚待 Owner／獨立 review 採納；不是自行關閉工程 P1 或宣告 M0 freeze。

| Axis | Current proposed values | Meaning / authority |
|---|---|---|
| `pit_status` | `ELIGIBLE`, `INELIGIBLE`, `UNRESOLVED`, `WITHHELD` | 特定 snapshot/observation 在具名規則、cutoff、source/version 範圍內的資格摘要；不是 run lifecycle 或全面 Historical PIT 認證。 |
| `execution_status` | `NOT_RUN`, `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `BLOCKED` | 實際 operation/runner lifecycle；成功不推論資料資格或證據充分性。 |
| `evidence_class` | `SYNTHETIC_VERIFIED_IN_SCOPE`, `REAL_SOURCE_OBSERVED`, `HISTORICAL_PIT_SUPPORTED_IN_SCOPE`, `PROVISIONAL`, `UNVERIFIED` | 可支持的 claim 與 scope；不由 UI、run success 或 hash match 授予。 |

`data_mode` 仍是本輪 **NEW_M0_PROPOSAL**：`SYNTHETIC_GOLDEN` 或 `REAL_TWSE_PILOT`，不改欄位或 enum spelling。**`SYNTHETIC_GOLDEN` 不等於 CAP-F2 formal Frozen Golden 110/154 已執行或驗收。** `FIXTURE_ONLY` 是額外的可見 presentation provenance，不是第四種資格軸、不是真實 `SUCCEEDED` 或 `SYNTHETIC_VERIFIED_IN_SCOPE` 的證明。

### Mandatory status decision table

| Native state / evidence | App projection before a separately approved rule | Forbidden inference |
|---|---|---|
| `TemporalOutcome.SUPPORTED` | 原生 state/reason/lineage 保留；沒有完整已核准資格規則時 `pit_status=UNRESOLVED` | 無條件轉成 `ELIGIBLE` 或 historical evidence |
| `SelectionOutcome.SELECTED` | 保留 selected item/version；App qualification 預設 `UNRESOLVED` | selection success 等於 trusted/admitted snapshot |
| `TemporalOutcome.UNRESOLVED` / `SelectionOutcome.UNRESOLVED` | `UNRESOLVED` + 原始 reason、unknown cause、provenance | false、zero、empty success 或 `INELIGIBLE` by omission |
| `TemporalOutcome.NOT_ADMISSIBLE` / `SelectionOutcome.NO_QUALIFIED_CLAIM` | 原樣保留負向 state/reason；只有 explicit approved negative predicate 可產生 `INELIGIBLE`，否則 `UNRESOLVED`，或保留較強的原生 `WITHHELD` | 未經規則就推斷確定不合格，或轉成正向資格 |
| B03 diagnostic `WITHHELD` / `NOT_TRUSTED_PIT_EVIDENCE` | 必須保持 `WITHHELD`、`diagnostic_only=true`、`admission_eligible=false`、source-authentication/limitations flags | 發佈候選、`ELIGIBLE`、absent payload 視為 successful empty data |
| Typed domain failure / exception | 保留 typed first failure；只有實際 attempted/refused operation 才設定獨立 `execution_status=FAILED/BLOCKED`，未啟動 runner 仍 `NOT_RUN` | 把執行失敗等同 PIT `INELIGIBLE`、刪除錯誤或假造 metrics |
| Synthetic fixture simulated success | 顯示 simulated scenario + 持續可見 `FIXTURE_ONLY`；actual runner remains `NOT_RUN` until executed | fixture 推成 actual `SUCCEEDED` 或 `SYNTHETIC_VERIFIED_IN_SCOPE` |
| Real bytes observed | 觀測證據確認後至多為 `REAL_SOURCE_OBSERVED`；缺獨立歷史 time/version/rights evidence 則 PIT `UNRESOLVED`，原生 withholding 仍保留 | CSV/hash/current API/Source36 直接證明歷史可得或資格 |

### Positive and negative qualification gates

App `ELIGIBLE` 只能來自另行 **reviewed and tested mode-specific eligibility predicate**：完整 input manifest、cutoff、source/time/version/rights evidence、eligible source scope、missing/conflict checks、failure checks、reason 與 lineage。Synthetic 可在執行且有 oracle/test evidence 的受限 synthetic experiment 內主張資格；Real-TWSE 更需獨立審查 historical time/version/rights/admissibility basis。**本任務不實作、不測試、不核准任何正向規則，也不允許直接升格 B03 diagnostic candidate。** Explicit `INELIGIBLE` 另需已核准的負向 predicate 與 exact reason，typed error 本身不是負向資格規則。

不得從 `ResearchRun.SUCCEEDED`、`SUPPORTED`、`SELECTED`、hash match、CSV observation、current provider API、mock UI、historical Source36 或 Controller2 review 推論正向資格或 Historical PIT support。Data Lead 與 F2 Lead 不得自動為自身 ingestion 簽發獨立 historical certification；IF-07 的獨立 reviewer 與證據審核仍是阻擋閘門。

### Proposed qualification trace and identity preservation

`SnapshotReference.qualification_trace_ref` 為 **PROPOSED / NEW_M0_PROPOSAL** logical reference，或提供等價的受控 app-visible evidence/debug access；不是既有 source field、DB column 或已實作 API。未來 translator 必須可追到 native domain type/state、exact reasons、unknown causes、typed first failure、source/version/cutoff/input manifest identifiers、provenance/lineage、evaluator/rule/evidence basis、diagnostic/withholding/admission/source-authentication flags。`pit_status` 僅 summary，不能取代或隱藏這些資訊。未映射狀態一律 `UNRESOLVED`，或保留較強的原生 `WITHHELD`；錯誤維度獨立保存。

cutoff、version 或 manifest 改變時，禁止沿用舊 qualification、digest 或 lineage 作為有效證據；保留 mismatch 並 fail closed，待重新資格判定及 IF-03 的 canonical/replay oracle。這裡不定義實際 encoding，也不宣稱 App hash 與 B03 hash 等價。

### IF-05 adversarial textual contract cases

以下十項是文件條文覆蓋判定 `TEXT_SPEC_PASS`，不是執行測試或 reviewer acceptance；對應 Decision Record §1.2 的順序，未來實作必須另有 negative tests。

| Case | Adversarial input | 必須明載的契約行為 | Documentary result |
|---|---|---|---|
| `IF05-N01` | `TemporalOutcome.SUPPORTED` 單獨出現 | 保留原生 state/reason；無已核准完整規則時 `pit_status=UNRESOLVED`；禁止自動 `ELIGIBLE`。 | `TEXT_SPEC_PASS` only; runtime `NOT_RUN` |
| `IF05-N02` | `SelectionOutcome.SELECTED` 單獨出現 | 保留 item/version/lineage；App 預設 `UNRESOLVED`；禁止自動 `ELIGIBLE`。 | `TEXT_SPEC_PASS` only; runtime `NOT_RUN` |
| `IF05-N03` | B03 `WITHHELD` / `NOT_TRUSTED_PIT_EVIDENCE` | 保持 `WITHHELD`、not-admission-eligible 與 diagnostic flags；不可發佈或視為空的成功資料。 | `TEXT_SPEC_PASS` only; runtime `NOT_RUN` |
| `IF05-N04` | 缺 publication timestamp 或 time/version conflict | 保留 unknown cause 與原始 reason，`UNRESOLVED`；不可假造 false/zero/blank。 | `TEXT_SPEC_PASS` only; runtime `NOT_RUN` |
| `IF05-N05` | `NOT_ADMISSIBLE` / `NO_QUALIFIED_CLAIM` | 保留負向原因；只有 explicit approved negative predicate 可給 `INELIGIBLE`，否則 `UNRESOLVED` 或原生 `WITHHELD`；不可轉正。 | `TEXT_SPEC_PASS` only; runtime `NOT_RUN` |
| `IF05-N06` | Mock success payload | 持續顯示 `FIXTURE_ONLY`；simulated status 與 actual status 分開，實際 runner `NOT_RUN`；不能聲稱 `SYNTHETIC_VERIFIED_IN_SCOPE`。 | `TEXT_SPEC_PASS` only; runtime `NOT_RUN` |
| `IF05-N07` | `ResearchRun.SUCCEEDED` + `SnapshotReference.UNRESOLVED` | 結果與 snapshot 保留不確定性；execution success 不證明 `ELIGIBLE` 或 historical certification。 | `TEXT_SPEC_PASS` only; runtime `NOT_RUN` |
| `IF05-N08` | `REAL_SOURCE_OBSERVED` 或現代 source bytes | 觀測證據確認才可用該 evidence class；無獨立 time/version/rights basis 時 PIT `UNRESOLVED`；不得 historical promotion。 | `TEXT_SPEC_PASS` only; runtime `NOT_RUN` |
| `IF05-N09` | Typed failure / `FAILED` / `BLOCKED` | 保留 typed first failure、PIT state、reason/lineage；只有實際 attempted/refused operation 可設定 execution failed/blocked；不假造 metrics。 | `TEXT_SPEC_PASS` only; runtime `NOT_RUN` |
| `IF05-N10` | cutoff/version/manifest 改變卻沿用舊 digest/lineage | 禁止 silently reuse；舊 qualification/identity 視為不適用，保留 mismatch 原因並 fail closed，待 IF-03 encoding/oracle 與重新資格判定。 | `TEXT_SPEC_PASS` only; runtime `NOT_RUN` |


### IF disposition register — proposed for independent review

三種 disposition 是本次文件處置：`POLICY_DECIDED_IMPLEMENTATION_PENDING` 表示政策已明載為待採納提案、程式未實作；`DEFERRED_WITH_BLOCKING_GATE` 表示具名閘門前禁止使用；`UNKNOWN_REQUIRES_AUTHORITY` 表示證據／獨立授權未建立。它們不是 runtime verified、實作完成、source accepted 或最終 Owner adoption。

| IF | Disposition | 政策／未實作事項 | Responsible role | Blocking milestone / target | No-go default |
|---|---|---|---|---|---|
| `IF-01` | `POLICY_DECIDED_IMPLEMENTATION_PENDING` | 八個 evaluator 是 Codex 02 靜態規劃候選；實際 runtime 與 input/code-observation 建構另審，不能把 Git/disk helper 稱為 pure call。 | Technical Lead (F2) | F2-DEMO-ADAPTER 實作前；M0 規劃目標 2026-11-20 | 不啟動 adapter，不 import B04 Harness / Physical Consumer。 |
| `IF-02` | `POLICY_DECIDED_IMPLEMENTATION_PENDING` | 七個 App DTO 與 logical ResearchClient 為 NEW_M0_PROPOSAL；mvp-app-v0.1 僅提議的 application schema family，與 Domain/DB 分開；translator 必須另版別、另測。 | Technical Lead + Member B (F3 contract owner) | 首次 shared DTO 實作或依賴具體 DTO 的 F3/F6 code 前 | 只做 spec/fixture 規劃；不虛構 ApprovedDataSnapshot、既有欄位或 schema。 |
| `IF-03` | `DEFERRED_WITH_BLOCKING_GATE` | Canonical bytes、digest domain separation、timestamp/number precision、replay equivalence oracle 尚未決定。 | Technical Lead (F2) + Member B (F3) | 首次 M1 identity/replay acceptance 前；target ≤ 2026-12-15；M1 2026-12-31 | 禁止 cross-schema digest 等價宣稱；B03 diagnostic hash 不是 App hash。 |
| `IF-04` | `DEFERRED_WITH_BLOCKING_GATE` | Logical ResearchClient port 作為設計提案固定；實際 local/CLI/HTTP transport 未選，無 framework 決定。 | Member B (F3) + Member C (F6); Lead sign-off | F6-08 / actual backend integration 前；planning decision target ≤ 2026-12-20；M2 2027-01-31 | 僅 FixtureResearchClient spec/mock 規劃；不宣稱真實 endpoint 或 backend 呼叫。 |
| `IF-05` | `POLICY_DECIDED_IMPLEMENTATION_PENDING` | 本文件 IF-05 三軸與 fail-closed 規則已列為待獨立審查的政策提案；translator 未實作、未核准正向資格規則。 | Technical Lead (F2) | M0 logical freeze 前須獨立審查政策；F2-DEMO-ADAPTER 實作前另審 translator 與測試 | 未映射為 UNRESOLVED，原生 WITHHELD 保留；禁止正向自動升格。 |
| `IF-06` | `POLICY_DECIDED_IMPLEMENTATION_PENDING` | M0-* IDs、FIXTURE_ONLY、origin/version/digest/limitations 與禁止 production import test helpers 為政策提案；實際目錄延後。 | Member C (F6) + Member B (F3) | F6-00 提出路徑；F6-02 fixture code 前核准路徑、IF-03 digest 規則與獨立 task | 只有規格，沒有 fixture bytes、執行成功宣稱或 protected data copies。 |
| `IF-07` | `UNKNOWN_REQUIRES_AUTHORITY` | 政策要求 producer 不得自我認證；實際 source rights/time/version admissibility 與獨立 reviewer 任命未建立。 | Technical Lead (F2) + Member A (F4/Data) + independent reviewer | real-data intake 或 positive historical claim 前；target checkpoint ≤ 2027-02-28 | 不 retrieval / intake / admission；僅有證據時可顯示 REAL_SOURCE_OBSERVED，PIT 保留 UNRESOLVED 或原生 WITHHELD。 |

Named implementation assignee 與 reviewer 均為 `TBD_BY_LEAD`。IF-01/02/05/06 的政策與 IF-07 的 authority model 供本輪 review；IF-03/04 細節與 IF-07 實際來源許可不需在 M0 實作完成，但必須保留上述阻擋閘門。M0 logical freeze 只能在 Owner／獨立 review 採納本輪文件後成立；不存在本 agent 的自動 freeze。

### Fixture provenance and F6 display-only authority

All six named M0 fixture cases in this document are specifications only; no fixture bytes, dataset hashes, experiment results, or test passes were created. Future fixture records must identify fixture ID/version, author/owner, source spec/version, synthetic generator or hand-authored origin, content digest and canonicalization, expected scenario status, limitations and `FIXTURE_ONLY` provenance. No protected dataset or formal Golden bytes are implied. F6 must visibly distinguish a simulated success scenario from an actual experiment, which remains `NOT_RUN` until an executed backend result exists. Dummy comparison values are display examples only. F6 cannot certify, recompute, unlock, or relabel authoritative PIT/evidence/financial results.

### Repository layout and verification conventions

According to the retained Codex 02 static record at this base, `src/pit_research_lab/` contains `cli.py`, `domain/`, and `infrastructure/database/`; no F3/F5/F6 application directories or frontend/package manifest were found in the tracked layout. The committed migration inventory contains only `migrations/versions/f13_empty_baseline.py`, not application DTO schemas. F3/F6 paths must be proposed in their own task packets before coding.

[Testing conventions](../../development/testing.md), [contributor policy](../../development/contributing.md), `pyproject.toml`, `Makefile`, and `.github/workflows/ci.yml` were inspected read-only by Codex 02, not re-audited as source/runtime in this task. Python is constrained to 3.12; pytest uses native assertions, strict markers and `tests/unit/` versus `tests/integration/database/`; CI defines `Quality` and `PostgreSQL Integration`. No check, pytest collection, project import, dependency installation or hosted CI was executed in M0. Older README/architecture wording that domain layers are future work is historical and lags the inspected definitions; this task does not edit those files or infer fresh acceptance from them.

Related M0 records: [Rebaseline](academic-mvp-rebaseline-v0.1.md), [Shared contract](shared-interface-contract-v0.1.md), [Acceptance matrix](m0-acceptance-matrix-v0.1.md).
