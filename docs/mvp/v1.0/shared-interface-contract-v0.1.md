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

## MVP-IF-02-IF-03-ADOPT-01 — proposed normative addendum v0.1

### AD01-01. Authority, provenance and adoption state

**PROPOSED_FOR_OWNER_ADOPTION / INDEPENDENT_REVIEW_PENDING.** This appendix is `OWNER_DIRECTED_CANDIDATE`; all eleven decisions are `CANDIDATE_FOR_OWNER_RATIFICATION`, approval receipts `NOT_SUPPLIED`. Task initiation authorizes drafting, not eleven affirmative votes, reviewer appointment, oracle freeze or implementation. MUST/SHALL below describe the candidate contract if ratified; they do not alter existing runtime behavior. `ADOPTION_DRAFT_READY_FOR_REVIEW` is document construction only. No decision receives `OWNER_ADOPTED_PENDING_INDEPENDENT_REVIEW` without an exact external Owner receipt. Contract freeze is NOT_AUTHORIZED_THIS_TASK.

Fixed source is `d693b11ce649802df9fc13248c343203a09ff397`, tree `4b51b56dc2cb7b300ef56f598fcd1ff1109c3971`. Verified predecessor packet is `IF02_IF03_REVIEW01_Review_Evidence.zip`, SHA-256 `90d2212c92a31bc2cf0b26ffb8d95132c78db91de355d830a5c1cac8a039d508`; embedded report 127,700 bytes, SHA-256 `769b62d6bd80aa2e2e2f7b51cb28e309f6ea51e08adc6cdfac2602b41858e873`. User-supplied predecessor review disposition is `CONTRACT_REVIEW_ACCEPTED — OWNER_ADOPTION_PENDING`; this is not a signed adoption receipt. The packet's earlier empty AGENTS filename enumeration remains a disclosed, non-blocking procedural exception; it was not repeated. This appendix preserves the original 2026-11-06/07 status lines, seven proposed DTOs, ResearchClient methods, enum spellings, historical source tables and gate history verbatim.

Three claims stay distinct: exact source content integrity; per-cutoff source/time/version Native qualification; permission to release a particular projection to a particular consumer. Source pins, execution RUN and SELECTED do not imply ELIGIBLE. WU04 remains diagnostic_only=True, admission_eligible=False, NOT_TRUSTED_PIT_EVIDENCE, source_authentication=NOT_ESTABLISHED, INTEGRATED_PROVISIONAL. No App SnapshotReference, temporal DTO instance, client endpoint, translator, codec, golden vector or runner is created here.

| Authority dimension | Observed source / evidence | Current meaning |
| --- | --- | --- |
| M0 seven DTOs/client | docs/mvp/v1.0/shared-interface-contract-v0.1.md:L28–L38, L64–L77 | REVIEWED_SOURCE_POLICY_PROPOSAL; schemas/translation/transport pending |
| IF-02/03/05 | docs/mvp/v1.0/shared-interface-contract-v0.1.md:L130–L165, L185–L199 | Existing policy proposal/deferred gates; no predicate implementation or canonical replay acceptance |
| Temporal model | docs/mvp/v1.0/ux-adr-01-temporal-execution-contract-v0.1.md:L21–L50 | Five independent dimensions and singular snapshot conflict are documentary facts |
| WU04 implementation | src/pit_research_lab/mvp/f2/weekly_sequence.py:L114–L141, L339–L380, L514–L525 | IMPLEMENTED_AND_INSPECTED; bytes or DiagnosticReadWithheld, private audit, no resolver |
| Four diagnostic facts | tests/unit/mvp_f2/test_weekly_sequence.py:L38–L42, L295–L382 | Static committed support and supplied accepted scope; no new execution |
| Native semantics | src/pit_research_lab/domain/temporal.py:L157–L187; src/pit_research_lab/domain/causal_derivation.py:L622–L631 | Exact publication TimeProof strict BEFORE; B03 local-midnight constraint preserved |
| This appendix | ADOPT-01 user task + verified predecessor decision register | OWNER_DIRECTED_CANDIDATE; independent review/Owner ratification pending |
| Runtime/oracle/source authority | No new execution/independent vector/real-source receipt | NOT_RUN / NOT_AUTHORIZED / NOT_PROVEN as applicable |

### AD01-02. Sidecar-first selection and alternatives

Draft selection IF02-OD01 is Option A: separately versioned Temporal Binding Sidecar. F2 owns and issues per-cutoff evidence/qualification and permitted observation; F3 owns experiment/hypothesis/method/protocol association; F5 owns policy/action/execution/cost/outcome interpretation; F6 renders authorized safe views. The seven logical DTO proposals are not changed by this appendix.

```text
F2 immutable source/version/time evidence
 -> genuine public Native qualifications independently per cutoff
 -> private audit receipt / original lineage / typed first failure
 -> detached strict permitted observation reference (no audit resolver)
 -> ordered TemporalBindingSet / PerCutoffBinding refs
 -> explicit F3 ExperimentSequenceBinding (kind/version/discovery)
 -> future F3 protocol/run and F5 same-info policies only after separate gates
 -> F6 display-only safe view under IF-04/06
Private audit resolution: separate authorized F2/reviewer principal only.
Future prices / labels / returns: F3/F5 EVALUATION-ONLY, never policy input.
```

This graph is conceptual; no identifier is minted. Option B remains viable fallback: a new explicitly tagged composite resource with per-member qualification and coordinated migration; never store an aggregate alias in old singular snapshot_id. Option C is a deliberate versioned DTO/temporal-input extension; it requires F3/F6 migration and exact temporal_policy shape review. Sidecar reduces immediate singular-schema reinterpretation but adds association/discovery surface; it is not a way to avoid IF-02 consumer contracts. B/C are preserved options, not rejected existing implementations.

### AD01-03. Explicit F3 association and legacy reader refusal

Candidate `ExperimentSequenceBinding` contract version is `experiment-sequence-binding-candidate-v0.1`, kind `EXPERIMENT_SEQUENCE_BINDING`, issuer_role `F3`, temporal_input_kind `SEQUENCE`. F3 is authoritative for the association truth and protocol approval, not for source qualification. The exact field registry below includes author_ref, status/approval receipt, typed experiment_spec_ref and temporal_binding_set_ref, schedule_protocol_ref, method_horizon_maturity_ref, optional tagged policy_evaluation_ref and reader_contract_ref. Its detached identity is `ResourceRef<EXPERIMENT_ASSOCIATION>` over its body; own envelope is outside that body. No F3 API/DTO implementation exists by this proposal: **CONTRACT_ONLY / NO_PORT**.

Logical discovery is concrete while transport stays deferred: an F3-owned registry keyed by `(exact experiment_spec_ref, association_kind, object_schema_version)` must resolve exactly one current, authorized, immutable association. Zero/multiple entries -> REF_ASSOCIATION_AMBIGUOUS. A reader first supplies exact `association_contract_version`, `temporal_input_kinds`, `sequence_schema_versions`, `canonical_profile_versions`, `observation_rights_policy_ref`, `legacy_fallback=false`. It must explicitly support SEQUENCE and the exact registered association/set/profile versions. Missing capability, legacy single-cutoff-only support, unknown version or implicit fallback -> REF_LEGACY_SINGLE_CUTOFF or REF_UNSUPPORTED_VERSION. This is a logical compatibility contract, not an added ResearchClient method or endpoint; IF-04 separately chooses HTTP/CLI/DB/in-process transport and issuer/capability enforcement.

The association must match exact experiment, sequence, schedule/calendar/config/data-mode/protocol versions and F3 approval receipt; duplicated/missing/stale/foreign/wrong-order/mismatched refs refuse. F3 protocol approval never grants F2 eligibility or F5 evaluation approval. Changed hypothesis/method/horizon/seed/allowed input or sequence invalidates the association; retain old immutable history, do not repoint aliases silently. Revocation of a grant blocks future resolution without rewriting content identity.

**No snapshot_id fallback:** snapshot_id retains its single-cutoff meaning. Never populate it with t1, a dummy aggregate, composite alias or hidden sidecar. Never infer SEQUENCE by parsing untyped temporal_policy. Seven proposed DTOs/client methods remain unchanged; actual sequence submission stays blocked until a separately reviewed versioned F3/F6 mapping exists. A legacy reader must refuse, not degrade to one cutoff.

**Association cycle refusal:** first seal F3-EXPERIMENT with exact sequence ref and association CONTRACT VERSION; only then may an association point to that experiment and sequence. The experiment MUST NOT hash an association INSTANCE that points back to it. Parent graph cycle -> REF_CYCLE. This resolves IF02-OD05-S1 and IF03-OD03-S2 as pending drafting choices, not approved twelfth decisions.

### AD01-04. Proposed field registry, temporal case and positional accounting

All fields below are logical candidates. `R` means required; a required container may have zero members only where cardinality explicitly permits 0..n. No null/omission for unknown facts; use declared tagged unions. All issuers are role-level, not assigned people. `SAFE` is a reviewed safe/control view, never a raw resolver; `AUDIT` is a separate F2-scoped capability; `EVAL` is retrospective only. Every field failure is a named REF_* refusal or original typed Native cause, never a zero/blank successful default. The referenced original 70 rights records are all accounted as PF001..PF070; AF records are explicit additions. Source policy anchors are shared contract L19–L38/L155–L165 and UX-ADR L33–L50 at the fixed SHA.

Common parent rule: typed parent core/ResourceRef is identity-bearing; own `reference` moves to ReferenceEnvelope outside CanonicalPayload (CAN-05). `schema_version` becomes an explicit candidate object_schema_version, not a modification of any existing DTO schema. Private `audit_evidence_ref` and `provenance_ref` exist only in the private F2 binding view. They are absent from policy-consumable payload. Source/config/protocol refs identify immutable content and permitted role; unresolved resource schema is IF03-OD01-S1, never untyped decode.

Logical resource schema literals are `temporal-configuration-candidate-v0.1`, `decision-schedule-candidate-v0.1`, `per-cutoff-binding-candidate-v0.1`, `temporal-binding-set-candidate-v0.1`, and `experiment-sequence-binding-candidate-v0.1`. These are source-backed ResourceRef body schemas; the ten domain CanonicalPayload schemas in AD01-09 are distinct semantic identity projections, not aliases of these bodies. The domain payload is exactly its listed fields, never automatic serialization of the field registry or own reference. A separately reviewed owner mapping must establish consistency of source body and projection before issuance; unknown resource schema or unmapped field is REF_UNAPPROVED_RESOURCE_SCHEMA, not implicit omission. This resource-mapping prerequisite is IF03-OD01-S1. No logical DTO or projection implementation is created.

| ID / logical field | Exact candidate type / cardinality | Semantic owner / issuer | Rights / disposition |
| --- | --- | --- | --- |
| PF001 TemporalConfiguration.object_schema_version | exact candidate object schema literal; schema discriminator, not adopted DTO version; 1 | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF002 TemporalConfiguration.ReferenceEnvelope (outside CanonicalPayload) | ReferenceEnvelope or ResourceRef content envelope; own digest never in own payload; 1 | respective issuing owner | SAFE; MOVED_TO_REFERENCE_ENVELOPE |
| PF003 TemporalConfiguration.limitations | ordered bounded string[]; 0..n | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF004 TemporalConfiguration.data_mode | SYNTHETIC_GOLDEN / REAL_TWSE_PILOT enum; 1 | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF005 TemporalConfiguration.source_refs | bounded typed immutable reference[]; 1..n | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF006 TemporalConfiguration.evidence_class | proposed App enum; 1 | respective evidence owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF007 DecisionSchedule.object_schema_version | exact candidate object schema literal; schema discriminator, not adopted DTO version; 1 | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF008 DecisionSchedule.ReferenceEnvelope (outside CanonicalPayload) | ReferenceEnvelope or ResourceRef content envelope; own digest never in own payload; 1 | respective issuing owner | SAFE; MOVED_TO_REFERENCE_ENVELOPE |
| PF009 DecisionSchedule.limitations | ordered bounded string[]; 0..n | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF010 DecisionSchedule.data_mode | SYNTHETIC_GOLDEN / REAL_TWSE_PILOT enum; 1 | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF011 DecisionSchedule.source_refs | bounded typed immutable reference[]; 1..n | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF012 DecisionSchedule.evidence_class | proposed App enum; 1 | respective evidence owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF013 PerCutoffBinding.object_schema_version | exact candidate object schema literal; schema discriminator, not adopted DTO version; 1 | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF014 PerCutoffBinding.ReferenceEnvelope (outside CanonicalPayload) | ReferenceEnvelope or ResourceRef content envelope; own digest never in own payload; 1 | respective issuing owner | SAFE; MOVED_TO_REFERENCE_ENVELOPE |
| PF015 PerCutoffBinding.limitations | ordered bounded string[]; 0..n | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF016 PerCutoffBinding.data_mode | SYNTHETIC_GOLDEN / REAL_TWSE_PILOT enum; 1 | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF017 PerCutoffBinding.source_refs | bounded typed immutable reference[]; 1..n | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF018 TemporalBindingSet.object_schema_version | exact candidate object schema literal; schema discriminator, not adopted DTO version; 1 | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF019 TemporalBindingSet.ReferenceEnvelope (outside CanonicalPayload) | ReferenceEnvelope or ResourceRef content envelope; own digest never in own payload; 1 | respective issuing owner | SAFE; MOVED_TO_REFERENCE_ENVELOPE |
| PF020 TemporalBindingSet.limitations | ordered bounded string[]; 0..n | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF021 TemporalBindingSet.data_mode | SYNTHETIC_GOLDEN / REAL_TWSE_PILOT enum; 1 | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF022 TemporalBindingSet.source_refs | bounded typed immutable reference[]; 1..n | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF023 TemporalBindingSet.evidence_class | proposed App enum; 1 | respective evidence owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF024 ExperimentSequenceBinding.object_schema_version | exact candidate object schema literal; schema discriminator, not adopted DTO version; 1 | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF025 ExperimentSequenceBinding.ReferenceEnvelope (outside CanonicalPayload) | ReferenceEnvelope or ResourceRef content envelope; own digest never in own payload; 1 | respective issuing owner | SAFE; MOVED_TO_REFERENCE_ENVELOPE |
| PF026 ExperimentSequenceBinding.limitations | ordered bounded string[]; 0..n | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF027 ExperimentSequenceBinding.data_mode | SYNTHETIC_GOLDEN / REAL_TWSE_PILOT enum; 1 | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF028 ExperimentSequenceBinding.source_refs | bounded typed immutable reference[]; 1..n | respective issuing owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF029 ExperimentSequenceBinding.evidence_class | proposed App enum; 1 | respective evidence owner | SAFE; PRESERVED_AS_CANDIDATE |
| PF030 TemporalConfiguration.calendar | ResourceRef<CALENDAR>; 1 | F2 calendar facts; F3 approves schedule use | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF031 TemporalConfiguration.source_cadence_refs | ordered ResourceRef<SOURCE_CADENCE>[] 1..4096; 1..n | F2/F4 | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF032 TemporalConfiguration.decision_cadence | literal WEEKLY for candidate executable scope; no Monthly/Daily fallback; 1 | F3 with F2 calendar review | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF033 TemporalConfiguration.cutoff_convention | exact {timezone_name:Text,offset:Text,precision:SECOND,local_clock:Text,anchor_ref:ResourceRef<PROTOCOL>,holiday_roll_ref:ResourceRef<PROTOCOL>}; 1 | F2/F3 | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF034 TemporalConfiguration.horizon_ref | ResourceRef<HORIZON_MATURITY>; 1 | Member B/F3 | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF035 TemporalConfiguration.rebalance_execution_ref | ResourceRef<EXECUTION_RULES>; 1 | F5 owner | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF036 TemporalConfiguration.evaluation_ref | ResourceRef<EVALUATION_PROTOCOL>; 1 | F3/F5 | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF037 DecisionSchedule.configuration_ref | ResourceRef<TEMPORAL_CONFIGURATION>; 1 | F3 schedule planner with F2 verification | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF038 DecisionSchedule.source_input_ref | ParentRef<SOURCE-BYTES> of fixed schedule input; 1 | F2 | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF039 DecisionSchedule.ticks | ordered {tick:TickContext,session_id:Text}[] 1..4096; session must exist in pinned calendar; generic bound 1..4096 candidate, exact 4 only WU04 profile; 1..n; bounded case 4 | F2 generation; F3 schedule approval | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF040 DecisionSchedule.annotations | ordered NoSessionAnnotation[] 0..4096; 0..n; current 1 | F2 calendar/F3 schedule | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF041 PerCutoffBinding.tick | TickContext; 1 | Technical Lead/F2 | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF042 PerCutoffBinding.manifest_source_versions | exact {manifest_ref:ResourceRef<MANIFEST>,source_version_refs:ordered SourceVersionRef[],coverage_ref:ResourceRef<COVERAGE>}; 1 | Technical Lead/F2 | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF043 PerCutoffBinding.qualification_ref | ParentRef<F2-QUALIFICATION>; 1 | Technical Lead/F2 | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF044 PerCutoffBinding.audit_evidence_ref | Private ResourceRef<NATIVE_RECEIPT / SEMANTIC_EVIDENCE> + capability-bound audit locator outside parent core; 1 | Technical Lead/F2 | AUDIT; REFINED_PRIVATE_VIEW_ONLY |
| PF045 PerCutoffBinding.observation_ref | Available{ref:ParentRef<F2-OBSERVATION>}  /  Withheld{reason:SafeReason}; no audit resolver; 1 | Technical Lead/F2 | SAFE; PRESERVED_AS_CANDIDATE |
| PF046 PerCutoffBinding.native_summary | NativeSummary{owner,type,state,reason_code,unknown,first_failure,invocation,invocation_receipt_ref}; tagged unions, exact private record kept; 1 | Technical Lead/F2 | SAFE; PRESERVED_AS_CANDIDATE |
| PF047 PerCutoffBinding.app_axes | AppAxes{pit_status,execution_status,evidence_class,execution_scope_ref:ResourceRef<PROTOCOL>}; execution scope mandatory to distinguish Native operation from F3 lifecycle; 1 | F2 qualification; F3 operation owner | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF048 PerCutoffBinding.scope_flags | ScopeFlags{diagnostic_only:true,admission_eligible:false,trust:NOT_TRUSTED_PIT_EVIDENCE,source_authentication:NOT_ESTABLISHED,disposition:INTEGRATED_PROVISIONAL}; 1 | Technical Lead/F2 | SAFE; PRESERVED_AS_CANDIDATE |
| PF049 TemporalBindingSet.configuration_ref | ResourceRef<TEMPORAL_CONFIGURATION>; 1 | F2 issuer; F3 association owner | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF050 TemporalBindingSet.schedule_ref | ResourceRef<DECISION_SCHEDULE>; 1 | F2 issuer | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF051 TemporalBindingSet.bindings | ordered ResourceRef<SEMANTIC_TRACE> of per-cutoff binding bodies; exactly schedule count; generic bound 1..4096 candidate, exact 4 only WU04 profile; exactly schedule tick count | Technical Lead/F2 | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF052 TemporalBindingSet.completion | SequenceAccounting; 1 | Technical Lead/F2 | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF053 TemporalBindingSet.provenance_ref | Private ResourceRef<SEMANTIC_TRACE> input evidence manifest, never own final EVIDENCE; 1 | Technical Lead/F2 | AUDIT; REFINED_EXACT_CANDIDATE_TYPE |
| PF054 ExperimentSequenceBinding.experiment_spec_ref | ParentRef<F3-EXPERIMENT> of sealed logical spec; no association-instance backedge; 1 | Member B/F3 with F5 owner for evaluation | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF055 ExperimentSequenceBinding.temporal_binding_set_ref | ParentRef<TEMPORAL-SEQUENCE>; 1 | Member B/F3 with F5 owner for evaluation | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF056 ExperimentSequenceBinding.method_horizon_maturity_ref | ResourceRef<HORIZON_MATURITY>; ties exact method/protocol refs through schedule_protocol_ref; 1 | Member B/F3 with F5 owner for evaluation | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF057 ExperimentSequenceBinding.policy_evaluation_ref | ResourceRef<POLICY_EVALUATION_PROTOCOL>  /  NotApplicable{owner,reason}; F3-only experiment does not require invented F5 protocol; 1 | Member B/F3 with F5 owner for evaluation | SAFE; PRESERVED_AS_CANDIDATE |
| PF058 ExperimentSequenceBinding.temporal_input_kind | literal SEQUENCE for this association; SINGLE_CUTOFF uses original separate contract; 1 | F3/Technical Lead | SAFE; REFINED_EXPLICIT_DISCRIMINATOR |
| PF059 SafeObservation.issuer_ref | string; 1 | Technical Lead/F2 | SAFE; PRESERVED_AS_CANDIDATE |
| PF060 SafeObservation.feature_ref | string + projection-policy version; 1 | Technical Lead/F2 | SAFE; PRESERVED_AS_CANDIDATE |
| PF061 SafeObservation.cutoff | TimeRecord; 1 | Technical Lead/F2 | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF062 SafeObservation.value | Known{typed int64 or FixedRatio6} / Unknown / NotEvaluated / Withheld; 1 | Technical Lead/F2 | SAFE; PRESERVED_AS_CANDIDATE |
| PF063 SafeObservation.unit | closed string enum; 1 | Technical Lead/F2 | SAFE; PRESERVED_AS_CANDIDATE |
| PF064 SafeObservation.qualification_ref | ParentRef<F2-QUALIFICATION>; 1 | Technical Lead/F2 | SAFE; REFINED_EXACT_CANDIDATE_TYPE |
| PF065 SafeObservation.scope_flags | ScopeFlags{diagnostic_only:true,admission_eligible:false,trust:NOT_TRUSTED_PIT_EVIDENCE,source_authentication:NOT_ESTABLISHED,disposition:INTEGRATED_PROVISIONAL}; 1 | Technical Lead/F2 | SAFE; PRESERVED_AS_CANDIDATE |
| PF066 RetrospectiveEvaluation.future_price_observation | typed immutable evaluation reference or tagged unavailable; 0..n | F3 label maturity / F5 execution evaluation | EVAL; PRESERVED_AS_CANDIDATE |
| PF067 RetrospectiveEvaluation.future_label | typed immutable evaluation reference or tagged unavailable; 0..n | F3 label maturity / F5 execution evaluation | EVAL; PRESERVED_AS_CANDIDATE |
| PF068 RetrospectiveEvaluation.realized_return | typed immutable evaluation reference or tagged unavailable; 0..n | F3 label maturity / F5 execution evaluation | EVAL; PRESERVED_AS_CANDIDATE |
| PF069 RetrospectiveEvaluation.outcome_maturity | typed immutable evaluation reference or tagged unavailable; 0..n | F3 label maturity / F5 execution evaluation | EVAL; PRESERVED_AS_CANDIDATE |
| PF070 RetrospectiveEvaluation.execution_cost_outcome | typed immutable evaluation reference or tagged unavailable; 0..n | F3 label maturity / F5 execution evaluation | EVAL; PRESERVED_AS_CANDIDATE |
| AF001 ExperimentSequenceBinding.association_kind | literal EXPERIMENT_SEQUENCE_BINDING; 1 | Member B/F3 | SAFE; ADDED_CANDIDATE |
| AF002 ExperimentSequenceBinding.author_ref | ResourceRef<AUTHOR_RECORD>  /  Unknown; 1 | Member B/F3 | SAFE; ADDED_CANDIDATE |
| AF003 ExperimentSequenceBinding.issuer_role | literal F3; 1 | Member B/F3 | SAFE; ADDED_CANDIDATE |
| AF004 ExperimentSequenceBinding.association_status | Available{ref:ResourceRef<OWNER_DECISION>}  /  NotEvaluated; F3 protocol approval only, never F2 eligibility; 1 | Member B/F3 | SAFE; ADDED_CANDIDATE |
| AF005 ExperimentSequenceBinding.schedule_protocol_ref | ResourceRef<ASSOCIATION_PROTOCOL> binding schedule/calendar/config/data-frequency/horizon/execution refs; 1 | Member B/F3 | SAFE; ADDED_CANDIDATE |
| AF006 ExperimentSequenceBinding.reader_contract_ref | ResourceRef<READER_CAPABILITY_POLICY>; 1 | Member B/F3 with F6 | SAFE; ADDED_CANDIDATE |
| AF007 TemporalBindingSet.kind | literal TEMPORAL_BINDING_SET; 1 | Technical Lead/F2 | SAFE; ADDED_CANDIDATE |
| AF008 TemporalBindingSet.release_policy_ref | ResourceRef<OBSERVATION_RELEASE_POLICY>; 1 | Technical Lead/F2 | SAFE; ADDED_CANDIDATE |
| AF009 TemporalBindingSet.invariant_policy_ref | ResourceRef<SCHEDULE_INVARIANT_POLICY>; 1 | F2/F3 | SAFE; ADDED_CANDIDATE |
| AF010 PerCutoffBinding.selected_cohort | ordered CohortEntry[] 1..4096; current SYN-A only; 1 | Technical Lead/F2 | SAFE; ADDED_CANDIDATE |
| AF011 PerCutoffBinding.mismatch_reason | SafeReason  /  NotApplicable; 1 | Technical Lead/F2 | SAFE; ADDED_CANDIDATE |
| AF012 QualificationTraceRef.parent_core | ParentRef<F2-QUALIFICATION>; 1 | Technical Lead/F2 | SAFE; ADDED_CANDIDATE |
| AF013 QualificationTraceRef.audit_resolution_policy_ref | ResourceRef<AUDIT_ACCESS_POLICY>; no bearer authority in public parent core; 1 | Technical Lead/F2 | AUDIT; ADDED_CANDIDATE |
| AF014 ObservationRef.parent_core | ParentRef<F2-OBSERVATION>; 1 | Technical Lead/F2 | SAFE; ADDED_CANDIDATE |
| AF015 ObservationRef.release_receipt_ref | ResourceRef<OBSERVATION_RELEASE_RECEIPT>  /  NotEvaluated; 1 | Technical Lead/F2 | SAFE; ADDED_CANDIDATE |

TemporalConfiguration preserves five independent dimensions: source cadence refs (F2/F4), Weekly decision cadence and schedule/protocol (F3 with F2 calendar facts), horizon/training/label maturity (F3), rebalance/execution/cost rules (F5), evaluation/aggregation rules (F3/F5). Config is a typed immutable source-backed semantic resource, not F2 ownership of F5 price policy. DecisionSchedule has unique ordered actual session/tick IDs, zero-based contiguous order, strictly increasing UTC cutoffs, calendar/config/source pins and annotation policy. General candidate cardinality is 1..4096; exactly four is the WU04 fixed profile only. Unsupported calendar/zone/precision/cadence refuses; Monthly/Daily do not silently become runnable.

Each PerCutoffBinding preserves original exact tick/cutoff (source text, zone, offset, SECOND precision and origin), selected issuer/feature cohort, manifest/source version/history/coverage refs, independent qualification and observation parents, exact original typed unknown/first failure and Native invocation label/receipt provenance. The private Native evidence/lineage graph is never a decision observation. `QualificationTraceRef` commits to F2-owned audit evidence; `ObservationRef` resolves only an approved strict detached projection plus release receipt under a separate capability, never a WU04 _SequenceAudit pointer. No Python reference, callback, full pack, audit graph, arbitrary metadata or future grid enters policy input.

All scheduled positions must be retained, including failure/not-run positions. scheduled_count==accounted_count means positional accounting, not four admitted ticks. Any missing/unresolved/withheld/stale member blocks all-qualified release (REF_SEQUENCE_RELEASE_BLOCKED); do not drop, refill, sort or reindex; no all_eligible=True default. Existing successful A04/A05 retains VALUE_AVAILABLE, while access release may remain blocked. A complete diagnostic sequence can still be not admitted.

| Case | Original cutoff Asia/Taipei / SECOND | December / A04 / A05 | 672-byte request SHA-256 |
| --- | --- | --- | --- |
| t1 | 2027-01-07T18:00:00+08:00 | D1 / 140 / 0.714286 | 909050c0cc90f0e16361891e9fa2b2233a363aa35de5278a38b838d97baea046 |
| t2 | 2027-01-15T18:00:00+08:00 | D2 / 150 / 0.733333 | be50dadac52fee5a266b56dbd4448275cf331078af554050713bcdf4471fe1fa |
| t3 | 2027-01-29T18:00:00+08:00 | D2 / 150 / 0.733333 | 56c8ca0ff123301adc894e65738209c7987e91d31a9c9b35597e3ae44c0abed8 |
| t4 | 2027-02-05T18:00:00+08:00 | D3 / 130 / 0.692308 | beaf6dff59c87f22f9384a5d1ce3017a1192dbf2167e51b0c9b54d389eb107e8 |

These are source-backed accepted-scope diagnostic facts, not tests rerun here or admitted App objects. W03 (`2027-W03`) is NO_SESSION_WEEK, not a phantom tick. D2 exactly at t1 18:00 is not prior; D3 t3+1s cannot enter t3. t2/t3 share D2 bytes/values but must have distinct cutoff/context/qualification/observation identities. Comparing two changed candidate sequence member payloads changes sequence identity; looking up two members of the same sealed four-tick container does not mutate that container. B03 MD1 `2027-01-08T00:00:00+08:00` is a different diagnostic context; local midnight cannot substitute for Weekly 18:00. SYN-B requested roster is not independent Weekly qualification; MD1's two-issuer universe must not be borrowed. The prior approximately 1,813-byte read is a supplied historical reference only, not a new measurement; its actual whitelist deliberately contains none of these new evidence refs (weekly_sequence L339–L380/L514–L525).

### AD01-05. Capability-bound resolver contract

Issuer and verifier are distinct roles: F2 issues source/qualification/projection evidence; independent authorized F2/reviewer verifies original bytes/time/Native receipts; F3 verifies association/protocol, not source authenticity. A bare digest, alias or opaque locator grants no access. ResolutionMetadata and capabilities are outside canonical parent cores. Every resolution must bind principal, issuer grant, exact typed resource/domain/version, operation, cutoff/cohort, approved disclosure policy and validity/revocation receipt. Current enforcement is **NOT_IMPLEMENTED / IF-04_OR_CAPABILITY_GATE**.

| Principal | May resolve | Must not resolve | Grant / issuer |
| --- | --- | --- | --- |
| F2 authorized audit/reviewer | Scoped approved immutable source/version/time/Native receipt resolution | Unreviewed real data, secrets, arbitrary filesystem/path traversal | Technical Lead/F2 grants separate approved audit policy; reviewer appointment by Owner |
| F2 approved decision observation issuer | Read own required qualification evidence under separate audit grant, issue strict approved projection | Release full packet, future price/label or raw audit to decision principal | Technical Lead/F2 under separate projection/release policy |
| F3 research executor | Explicitly authorized observation, protocol and safe sequence/association refs after IF-02/05 | Raw/audit resolution, implied privileges from digest/opaque ID | F3 access subject to F2 observation-release authority |
| F5 policy evaluator | Identical admitted per-tick observation refs for Benchmark/A/B | Source reconstruction, future evaluation outcome at decision time | F5 policy capability never includes audit grant |
| F6 display | Authorized sanitized status/evidence/limitations summary | Native audit/root resources, PIT recomputation, eligibility promotion, authoritative P&L | IF-04/06 reviewed display view only |

Private audit locators and original source/Native/future graphs MUST NOT appear in policy payloads when the same consumer capability could resolve them. Same-capability opaque audit resolution is an explicit REF_AUDIT_CAPABILITY_LEAK, even if identifiers are unguessable. Authorized humans review via separate capability; F3/F5 receive only safe refs/release receipts after IF-02/05, and F6 only summaries. Missing/stale/dangling/wrong-domain/unknown-version/foreign-principal refs fail closed; no raw-object/current-version fallback. Grant revocation denies future operations while preserving immutable content/attempt history; semantic privacy/release-policy changes issue new dependent observation refs. A content match never defeats revocation.

Resolution audit receipt must preserve principal/grant/policy ref, requested typed target/action/context, checked source/code/version/length/digest, allow/deny reason, original operation/attempt provenance and receipt version. Keep secret grants/raw content out of safe logs. No actual resolver receipt exists now. Logical refusal codes below are proposed protocol diagnostics, **not new App enums**, and do not replace the original first Native failure.

| Named refusal | Required behavior |
| --- | --- |
| REF_MISSING | No resolver content/receipt available; block release/replay, preserve original typed cause |
| REF_STALE | Referenced immutable content differs from active source/code/policy/version requirements; old object retained historically, no reuse |
| REF_FOREIGN_PRINCIPAL | Capability/principal/object/action/scope mismatch; deny without disclosing raw existence/content |
| REF_AUDIT_CAPABILITY_LEAK | Decision/policy principal can resolve raw audit under same capability; deny release even if locator opaque |
| REF_DOMAIN_MISMATCH | Typed expected parent domain does not match actual envelope domain |
| REF_SCHEMA_OR_TYPE_MISMATCH | Object schema/profile/exact field/type mismatch, including wrong length/digest grammar |
| REF_UNSUPPORTED_VERSION | Unsupported contract/schema/profile/numeric/time resource version; no downgrade |
| REF_CYCLE | Self/ancestor identity or semantic dependency cycle; no recursive envelope hashing |
| REF_SEQUENCE_MISMATCH | Duplicate/missing/foreign/nonmonotonic/wrong-order binding or schedule/context mismatch |
| REF_LEGACY_SINGLE_CUTOFF | Reader lacks exact SEQUENCE association support; snapshot_id/temporal_policy fallback forbidden |
| REF_ASSOCIATION_AMBIGUOUS | Zero/multiple live F3 associations for exact spec/kind/contract version or untrusted F3 issuer |
| REF_PROFILE_MISMATCH | canonical_profile_version literal in payload/envelope not identical/registered, even if digest claim equal |
| REF_PIN_MISMATCH | Exact source/canonical payload/frame length or digest mismatch |
| REF_UNAPPROVED_RESOURCE_SCHEMA | Referenced F2/F3/F5 resource schema/content rules not approved; no generic untyped decode |
| REF_REVOKED | Authorization revoked/expired/superseded; deny operation, immutable content identity itself does not mutate |
| REF_SEQUENCE_RELEASE_BLOCKED | All positions accounted but at least one missing/unresolved/withheld/mismatch; no all-qualified release |

### AD01-06. IF-05 axes, typed provenance and no promotion

`pit_status`, `execution_status`, `evidence_class` stay independent and retain exact original enum spellings. Default App PIT is UNRESOLVED absent a separately reviewed/tested mode-specific positive predicate; preserve stronger applicable native/access WITHHELD. Explicit INELIGIBLE needs its own reviewed/tested negative predicate. BOUND/SUPPORTED/SELECTED/VALUE_AVAILABLE/four RUNs/hash equality or successful resolution never supply those predicates. `evidence_class` defaults conservatively to UNVERIFIED here; stronger classes require actual approved scope-specific evidence, not a mock or synthetic mode name. Synthetic does not mean real historical PIT or Formal Golden.

Original UnknownCause/FieldOrigin, NotEvaluated, NotApplicable, BlockingFailure category/code/owner/first failure, source/version/lineage/cutoff and actual invocation receipt remain exact in audit. Safe public subset follows reviewed disclosure policy; sanitization does not pretend to preserve full reason text. NOT_RUN differs from entered ATTEMPTED and returned RUN; later observation failure cannot overwrite entered operation evidence. Successful A04/A05 does not acquire an invented Native WITHHELD state. F3 lifecycle uses its actual own runner receipt; no F3 run happened here. Fixture simulated success retains FIXTURE_ONLY and actual runner NOT_RUN; execution success does not grant PIT status or positive hypothesis support. Real historical rights/time/version/source authentication remains IF-07.

| Predecessor status record | Original Native state / reason basis | Candidate App PIT / execution distinction |
| --- | --- | --- |
| S1-BOUND | BOUND; reason and CompleteScopedProvenance unchanged | UNRESOLVED; Per-operation receipt only; F3 runner NOT_RUN |
| S1-UNKNOWN | UNRESOLVED  /  original failure; UnknownCause + FieldOrigin; CONTENT_BINDING_INSUFFICIENT if S1 blocked at S2 | UNRESOLVED; Independent from PIT |
| S2-SUPPORTED | SUPPORTED; NONE / conditional unverified facts | UNRESOLVED; No F3 success inferred |
| S2-NOT_ADMISSIBLE | NOT_ADMISSIBLE; PUBLICATION_NOT_PRE_CUTOFF or actual reason | UNRESOLVED; No F3 success inferred |
| S2-UNRESOLVED | UNRESOLVED; Actual temporal reason, unknown tags, provenance and diagnostic | UNRESOLVED; No F3 success inferred |
| S3-SELECTED | SELECTED; Original reason/selected version/coverage/reachability; no fabricated absence cohort | UNRESOLVED; Independent; F3 remains NOT_RUN here |
| S3-NO_QUALIFIED_CLAIM | NO_QUALIFIED_CLAIM; Original reason/selected version/coverage/reachability; no fabricated absence cohort | UNRESOLVED; Independent; F3 remains NOT_RUN here |
| S3-UNRESOLVED | UNRESOLVED; Original reason/selected version/coverage/reachability; no fabricated absence cohort | UNRESOLVED; Independent; F3 remains NOT_RUN here |
| A04-VALUE | VALUE_AVAILABLE; NONE + original lineage; A05 FixedRatio6 under native policy | UNRESOLVED; Native RUN is not F3 SUCCEEDED |
| A04-MISSING | UNRESOLVED  /  NOT_COMPUTABLE  /  CONTRACT_VIOLATION  /  OPERATIONAL_ERROR; DEPENDENCY_UNRESOLVED / DEPENDENCY_NOT_COMPUTABLE / ZERO_QUARTER_REVENUE_DENOMINATOR / NEGATIVE_INPUT_OUTSIDE_SHARE_DOMAIN / exact failure | UNRESOLVED; FAILED/BLOCKED only from corresponding actual operation receipt ZERO_QUARTER_REVENUE_DENOMINATOR/NEGATIVE_INPUT_OUTSIDE_SHARE_DOMAIN belong to A05, not A04. A04 preserves its actual dependency/contract/operational reason; predecessor grouped examples are not new A04 states. |
| A05-VALUE | VALUE_AVAILABLE; NONE + original lineage; A05 FixedRatio6 under native policy | UNRESOLVED; Native RUN is not F3 SUCCEEDED |
| A05-MISSING | UNRESOLVED  /  NOT_COMPUTABLE  /  CONTRACT_VIOLATION  /  OPERATIONAL_ERROR; DEPENDENCY_UNRESOLVED / DEPENDENCY_NOT_COMPUTABLE / ZERO_QUARTER_REVENUE_DENOMINATOR / NEGATIVE_INPUT_OUTSIDE_SHARE_DOMAIN / exact failure | UNRESOLVED; FAILED/BLOCKED only from corresponding actual operation receipt |
| B03 | WITHHELD; NOT_TRUSTED_PIT_EVIDENCE; source_authentication NOT_ESTABLISHED | WITHHELD; Operation-specific only; Weekly is blocked |
| WU04-BYTES | wu04-weekly-diagnostic-read-v0.1; Copied Native VALUE_AVAILABLE/reason; diagnostic scope flags | UNRESOLVED; F3 runner NOT_RUN |
| WU04-WITHHELD | No separate Weekly WITHHELD enum; Closed safe reason; native_invocations tuple; full private typed audit survives | WITHHELD (proposed access summary); Whole release BLOCKED; original operation labels retained WITHHELD here is proposed consumer access summary only; do not pretend Native A04/A05 has that outcome. Original private typed cause and invocation tuple remain. |
| FIRST-FAILURE | original typed state; category/code/affected_scope/origin/attempted_operation; observation drift must not overwrite entered attempt | UNRESOLVED or stronger WITHHELD; Operation-specific FAILED/BLOCKED; unstarted F3 NOT_RUN |
| F3-ACTUAL | No actual F3 run established in inspected scope; Actual receipts required; hypothetical run success leaves PIT unchanged | UNRESOLVED; NOT_RUN here; future lifecycle separately owned |
| F3-FIXTURE | Simulated SUCCEEDED only as scenario; FIXTURE_ONLY presentation provenance persists | UNRESOLVED absent accepted predicate; NOT_RUN actual runner |
| PARTIAL | Some RUN, some blocked/not-run; Preserve each original position, outcome and first failure | UNRESOLVED / WITHHELD per member; Release BLOCKED; completion means accounted positions only |

### AD01-07. Candidate typed JSON grammar and CAN-01..CAN-10

Profile `typed-json-candidate-v0.1` is a deterministic **specification candidate**, not a codec or approved vector set. Every prospective bound/format below is OWNER_DECISION_REQUIRED unless its narrower existing Native behavior is explicitly cited. Unsupported external resource schema/time rules block corresponding oracle authoring; these parts are not ADOPTION_READY. Common candidate limits: payload <=16MiB, record depth <=64, array <=4096, Text <=65536 UTF-8 bytes, IDs/versions <=128, no bare number tokens. Reject bounds/length overflow before allocation; no permissive truncation. ResourceRef<R> has exactly resource_kind, resource_version, resource_schema, content_ref:ParentRef<SOURCE-BYTES>; roles below are closed, but each referenced body/schema needs its semantic owner's separate review. Pinned bytes alone do not establish the referenced protocol.

```text
CanonicalPayload<D> = Record({canonical_profile_version: "typed-json-candidate-v0.1"} + ExactFields[D])
Record = '{' ASCII-keys-sorted-by-unsigned-UTF8 ':' typed-values, separated by ',' '}'
Array = '[' ordered typed-values separated by ',' ']'
Value = scalar-string | Boolean-for-Boolean-field | Record | Array
No bare JSON number, null, unknown key, duplicate key or arbitrary extension.
Int64 = {"type":"int64","value":SINT}; UInt64 = {"type":"uint64","value":UINT}
UINT = "0" | [1-9][0-9]*; SINT = "0" | "-"?[1-9][0-9]*; ranges checked.
```

The grammar is documentary pseudocode: it defines bytes/types, not executable code in this task. Exact key order is a serialization rule, independent of the order fields are listed for reviewers.

**AD01-07.CAN-01 — Encoding/form.** A CanonicalPayload is an exact versioned record; UTF-8 without BOM, no whitespace outside strings. Record keys are defined ASCII [A-Za-z_][A-Za-z0-9_]*, sorted by unsigned UTF-8 bytes. Reject duplicate keys before map construction, unknown/missing keys, invalid UTF-8 and unpaired surrogates. Preserve Unicode scalar sequence, no NFC/NFD rewrite. Canonical string escaping: quote -> \"; backslash -> \\; every U+0000..U+001F -> lowercase \u00xx (including newline, no short escapes); other scalars emitted literally as UTF-8, no slash/non-ASCII escaping. Arrays retain order. No arbitrary extension bag. This candidate declares no nullable fact fields: missing, explicit null, Unknown, NotEvaluated, NotApplicable and Withheld differ; null is rejected for every current declared field. A future nullable field requires a new reviewed schema. Parsed noncanonical JSON may be decoded for inspection, but a canonical byte claim must match the single re-encoding exactly. Do not reuse WU01 ensure_ascii=True bytes.

**AD01-07.CAN-02 — Numbers.** No bare JSON numeric token is allowed in canonical records. Int64={"type":"int64","value":SINT}; SINT is "0" or "-"?[1-9][0-9]* and value in [-2^63,2^63-1]. UInt64={"type":"uint64","value":UINT}; UINT is "0" or [1-9][0-9]* and value in [0,2^64-1]. Boolean schema fields use true/false only, never int/bool coercion. Decimal={type:"decimal",coefficient:Int64,scale:UInt64,unit:Text,numeric_policy_ref:ResourceRef}; scale 0..18 candidate, coefficient*10^(-scale), preserve declared scale; exponent spelling is not accepted. No positive sign/leading zeros/-0; zero coefficient is exactly "0", while its declared decimal scale remains data. Negative integers/Decimal allowed only in fields with an appropriate semantic domain; overflow/precision loss refused. FixedRatio6={type:"fixed_ratio6",scaled_units:UInt64,decimal_text:Text,scale:UInt64,unit:"FRACTION",numeric_policy_ref:ResourceRef}; scale exactly 6, scaled_units 0..1000000; decimal_text exactly integer part + dot + six digits, checked against scaled units and Native policy FIXED_SIX_DECIMAL_FRACTION_HALF_EVEN-v0.1. Ratio body includes both text and exact scaled representation consistently; no recomputation from arbitrary display text. Float, NaN/Inf, implicit string/boolean/Decimal coercion and exact fractions are unsupported; new fraction schema requires separate decision. Seed is Int64 0..2^63-1. All bounds are candidate defaults under IF03-OD01-S2, not an existing general Native Decimal contract.

**AD01-07.CAN-03 — Time.** TimeRecord has exactly source_text, timezone_name, offset, precision, origin_ref, utc_comparison, timezone_rules_ref. Current profile: precision="SECOND", source_text=YYYY-MM-DDTHH:MM:SS(+|-)HH:MM, valid proleptic Gregorian year 0001..9999, no leap second, no fractional seconds; explicit offset numeric hours 00..23/minutes 00..59 and actual named zone must agree. utc_comparison uses YYYY-MM-DDTHH:MM:SSZ and must equal the instant derived from original declaration, never independent replacement evidence. Require pinned timezone-rules ResourceRef; reject naive/malformed/unsupported precision, gap, unavailable rules, contradictory offset-zone or nonunique interpretation. An explicit offset may resolve a repeated local wall time only if pinned zone rules give exactly one consistent instant. Origin is identity-bearing, not rewritten from UI. For current WU01 boundary only Asia/Taipei +08:00 original SECOND declarations are supported. A broader valid timezone case needs approved schema/rules; same UTC can compare SAME_INSTANT while original zone/text/origin differs as evidence identity. The actual exact Native TimeProof path uses published_at < cutoff; AT is not BEFORE. Do not generalize that one path to every publication/observation proof variant. IF03-OD02-S1 blocks unpinned/broader-zone oracle claims.

**AD01-07.CAN-04 — Domain separation/framing.** Supported candidate digest_algorithm literal "SHA-256". Exact domain_tag="PITLAB/ACADEMIC/"+registered DOMAIN+"/candidate-v0.1"; object_schema_version is the exact domain table literal. Each must be ASCII encoded as UTF-8, length 1..128 bytes. canonical payload length 1..16777216 bytes (16 MiB); reject overflow, excessive bounds, trailing frame bytes. LP(x)=uint64 big-endian byte length || exact bytes. frame=LP(UTF8(domain_tag)) || LP(UTF8(object_schema_version)) || LP(canonical_payload). Payload MUST contain canonical_profile_version literal "typed-json-candidate-v0.1"; it participates in the hashed third part. A new profile needs a new registered schema/domain version or explicit new reviewed pair; never strip/change profile while reusing old frame. Compare full decoded 32 digest bytes with exact envelope domain/schema/profile/algorithm/length. Unsupported domain/schema/profile/algorithm or mismatch refuses before any equality/admission claim. SHA-256 collision resistance is an integrity assumption, not proof of publisher, code execution or admission.

**AD01-07.CAN-05 — Reference semantics.** CanonicalPayload and ReferenceEnvelope are disjoint. Payload contains only the exact domain semantic fields plus canonical_profile_version, and already-defined typed parent cores. The object's OWN digest/envelope, locator, capability or issuance timestamp MUST NOT be in its own payload. ReferenceEnvelope exact hashed-identity core fields: domain_tag, object_schema_version, canonical_profile_version, digest_algorithm, canonical_payload_byte_length:UInt64, digest_hex:64 lowercase ASCII hex. The length is canonical PAYLOAD bytes, excluding frame/header/envelope. Optional issuer/display locator metadata is in a separate ResolutionMetadata record, outside parent cores and digest; it confers no capability. ParentRef<T> is the six-field core with expected registered domain T; no resolver callback or arbitrary URI. ResourceRef<R>={resource_kind,resource_version,resource_schema,content_ref:ParentRef<SOURCE-BYTES>}; owner must approve exact referenced resource bytes/schema; generic opaque bytes prove no semantics. Reject unsupported schema/domain, dangling/stale/foreign/reordered parent, own-envelope inclusion and graph cycles. Verify raw resource bytes via SOURCE-BYTES body length/raw hash, then semantic schema; verify canonical resource by exact payload/frame/envelope recomputation. Display aliases and Git/source/provider names are hints/provenance only. F3 experiment uses sequence parent plus association CONTRACT VERSION, never its association INSTANCE: seal experiment before association binds to it. Evidence points to subject, never subject to its own final evidence; use original semantic-input trace resource to avoid cycles.

**AD01-07.CAN-06 — Code/policy provenance.** F2 qualification pins relevant evaluator, adapter, source schema, qualification/time/numeric rules and Native trace; observation additionally pins projection/disclosure/release policy; F3/F5 own their method/protocol/policy pins. CodePin has exact relative owner path, byte length, raw SHA-256 and semantic version/owner reference. Observed loaded-path/code consistency, before/after receipts, Git commit/tree and checkout status are provenance, not portable deterministic App identity unless a named approved domain field requires them. Candidate excludes host checkout path/status from deterministic payloads; attempt receipts retain them privately. New clean commit with unchanged relevant bytes can preserve a deterministic subject only if reviewed relevant closure proves it; otherwise block replay. Never weaken historical byte guards or claim Git commit authenticates source or executed code.

**AD01-07.CAN-07 — Unknown/error/operation state.** Closed fact tags: Available{type:"available",ref:<exact expected typed ref>}; Known{type:"known",value:<schema type>,origin_ref:ResourceRef<ORIGIN>}; Unknown{type:"unknown",cause:<exact original UnknownCause>,origin_ref:ResourceRef<ORIGIN>,source_text_ref:ResourceRef<SOURCE_TEXT>|NotApplicable}; NotEvaluated{type:"not_evaluated",owner:Text,reason:Text}; NotApplicable{type:"not_applicable",owner:Text,reason:Text}; Withheld{type:"withheld",owner:Text,reason:Text,policy_ref:ResourceRef<OBSERVATION_RELEASE_POLICY>}. Preserve exact Native UnknownCause names (ABSENT_SOURCE_FIELD, EXPLICIT_SOURCE_UNKNOWN, AMBIGUOUS_SOURCE, UNMAPPED), no cause inference. NativeFailure={type:"native_failure",owner:Text,category:Text,code:Text,affected_scope_refs:ordered ResourceRef[],safe_diagnostic:Text,origin_ref:ResourceRef<ORIGIN>,attempted_operation:Text}; original detailed failure record retained audit-only when public text would leak. NativeSummary={owner:Text,type:Text,state:Text,reason_code:Text,unknown:Unknown|NotApplicable,first_failure:NativeFailure|NotApplicable,invocation:RUN|ATTEMPTED|NOT_RUN,invocation_receipt_ref:ResourceRef<NATIVE_RECEIPT>}. No missing -> zero/null or generic empty success. Exact first failing owner/reason/order survives wrappers; safe public code is not claimed lossless original text. RUN means actual returned operation per original receipt, ATTEMPTED entered exception, NOT_RUN no owner entered. These are operation labels, not new App lifecycle enums. Successful A04/A05 remains VALUE_AVAILABLE, no invented Native WITHHELD.

**AD01-07.CAN-08 — Attempt versus deterministic content.** Deterministic experiment/sequence/result payload excludes incidental attempt ID, execution wall clock, host, log path, perf counters, allocation and local object token. Historical publication/availability/label maturity times remain semantic evidence. F3-RUN-ATTEMPT has a fresh issuer-scoped attempt_id and immutable revision receipt per lifecycle change, not deterministic across reruns. It may include actual started/finished/observed code receipts and first failure. A new actual execution reissues work and gets a new attempt ID; reading stored JSON or constructing a result is not replay. RESULT never hashes its attempt envelope. An attempt may reference RESULT, which references EXPERIMENT but never that attempt, preserving DAG. Failed or not-started run uses tagged unavailable result, never fabricated deterministic metrics.

**AD01-07.CAN-09 — Object graph order.** All candidate arrays are ordered, including ticks, per-cutoff refs, lineage/correction paths, notices, failure priority and no-session annotations; no implicit array sorting or reindexing. Unique tick_id/order, strictly increasing UTC cutoffs and exact schedule membership are mandatory. No-session annotation changes schedule identity but never creates a tick. Native S3 owner-declared sets retain only their exact existing source policies (selection.py:canonical_bundle/reconstruction_ref); B03's named set-field sorting is scoped B03 behavior, never a universal codec rule. No new candidate field is declared a mathematical set; future set field requires exact owner/key/duplicate policy and version review. Duplicate/swapped/dropped/foreign tick refuses for fixed WU04 four-member profile. Generic schedule is 1..4096 candidate, with a separately pinned calendar/protocol; do not make all schedules exactly four.

**AD01-07.CAN-10 — Serialization stability/migration.** Exact schema/profile/domain negotiation and strict field refusal; unsupported version never downgrades, strips extension or falls back to single snapshot. Preserve historical bytes/identities under old rules. Migration produces new typed resource plus owner-reviewed relation receipt, not digest equivalence. No bridge to WU01/A04/A05/B03 raw/local identities without independently verified contracted preimages. Future independent Python/TypeScript full-byte/frame/digest parity required only after an approved TypeScript consumer/runtime exists. None exists by assertion of this draft. No canonical reference issued until normative ratification, independent oracle preparation/review and separately authorized codec/runtime validations.

### AD01-08. Non-self-referential reference envelope and byte framing

```text
CanonicalPayload = exact semantic record including canonical_profile_version;
                   typed already-defined parent cores allowed; OWN envelope forbidden.
ReferenceEnvelope = {domain_tag, object_schema_version, canonical_profile_version,
                    digest_algorithm, canonical_payload_byte_length:UInt64, digest_hex}
ResolutionMetadata = separate issuer/display locator/grant hints OUTSIDE payload/core;
                     no capability is implied and metadata is not hashed as a parent.
LP(x) = len64be(bytes(x)) || bytes(x)
frame = LP(UTF8(domain_tag)) || LP(UTF8(object_schema_version)) || LP(canonical_payload)
candidate_digest = SHA256(frame)    # NOT evaluated here
```

canonical_payload_byte_length counts **payload bytes only**, never frame or envelope. Profile version is a required literal IN payload, hence hashed in frame part 3; envelope profile must agree. New profile/schema/domain pairs require explicit registration; wrong profile refuses even when a caller claims equal digest. Digest format is 64 lowercase hex; algorithm literal SHA-256; domain/schema UTF-8 of exact ASCII strings 1..128 bytes; prefix u64 big endian; exact frame total 24+domain bytes+schema bytes+payload bytes, no trailing data. Validate parent expected-domain/type/schema/length and DAG before equality claims. Unknown/foreign/reordered parent refuses. Own digest/envelope inclusion or cycle is REF_CYCLE. No Python hash(), repr(), untyped JSON or current WU04 serialization is an oracle.

Documentary byte examples, **not approved golden vectors and no digest**:

```text
{"type":"int64","value":"140"}
7b 22 74 79 70 65 22 3a 22 69 6e 74 36 34 22 2c 22 76 61 6c 75 65 22 3a 22 31 34 30 22 7d
"é" = 22 c3 a9 22; decomposed scalar string = 22 65 cc 81 22 (distinct bytes)
newline string = 22 5c 75 30 30 30 61 22 (canonical \u000a, not short escape)
LP toy frame (D/S intentionally unsupported tags, {} not a valid domain payload):
00 00 00 00 00 00 00 01 44 | 00 00 00 00 00 00 00 01 53 |
00 00 00 00 00 00 00 02 7b 7d
```

Verification later: obtain authorized exact payload bytes; validate schema/profile/parents/rights; independently canonicalize per adopted rules; verify payload length, exact framed bytes and digest against envelope and independently frozen vector; verify semantic resource contents separately. No content availability means no reproducibility proof. A hash match is content-integrity evidence only, never authentication/admission.

### AD01-09. Ten identity domains, complete candidate fields and parent ordering

For each domain the only top-level canonical keys are canonical_profile_version plus the ExactFields below; own envelope is excluded. Versioned tag is `PITLAB/ACADEMIC/<DOMAIN>/candidate-v0.1`; schema is `<lowercase-domain>-candidate-v0.1`. Every array is ordered unless a future separate reviewed version explicitly declares a set. Required facts never default to null/zero; only exact declared tagged unavailable unions. ResourceRef content is source-byte-backed; its unresolved owner schema blocks semantic issuance. No new primary domain beyond these ten is silently invented for associations/config: they are typed ResourceRef roles over detached immutable source-backed bodies.

| Domain / owner | ExactFields (all required) | Permitted claim / invalidation / gate |
| --- | --- | --- |
| SOURCE-BYTES; F2/F4 content custodian | body_byte_length: UInt64: exact raw body bytes; body_sha256: Hex64: SHA-256 of exact raw body, existing integrity algorithm only | Equality supports exact body integrity under SHA-256 assumption; never publisher identity, publication time, admissibility or history authenticity; Any exact raw-body byte change changes this object; source timestamp/rights outside body do not change body identity but can invalidate qualification; IF02/03 Owner + independent review; exact resource-schema/oracle gates; IF-05 release/predicates and F3/F5 methods separately; real source IF-07 |
| F2-QUALIFICATION; Technical Lead/F2 | source_body_refs: ordered SourceVersionRef[] 1..4096; manifest_ref: ResourceRef<MANIFEST>; calendar_ref: ResourceRef<CALENDAR>; cutoff: TimeRecord; context_ref: Text; exact issuer-bound Native context ID; feature_cohort: ordered CohortEntry[] 1..4096; coverage_ref: ResourceRef<COVERAGE>; native_semantic_trace_ref: ResourceRef<SEMANTIC_TRACE>; no attempt-specific allocation/clock fields; rules_code_refs: ordered CodePin[] 1..4096; evaluator/adapter/schema/policy roles explicit; qualification_state: NativeSummary; exact typed original state/failure; scope: ScopeRecord | Same contracted per-cutoff qualification evidence; does not imply App ELIGIBLE or verified historical PIT; Source/version/history/cutoff/coverage/context/evaluator/adapter/schema/reason/trace/flags drift; unavailable immutable evidence blocks replay; IF02/03 Owner + independent review; exact resource-schema/oracle gates; IF-05 release/predicates and F3/F5 methods separately; real source IF-07 |
| F2-OBSERVATION; Technical Lead/F2 | qualification_ref: ParentRef<F2-QUALIFICATION>; tick_context: TickContext; issuer_ref: Text; feature_values: ordered FeatureValue[] 1..4096; projection_policy_ref: ResourceRef<PROJECTION_POLICY>; release_policy_ref: ResourceRef<OBSERVATION_RELEASE_POLICY>; scope: ScopeRecord | Same authorized typed decision information under same qualification and projection; numerical display equality is weaker; Cutoff/context/feature/unit/value/scale/projection/qualification change; equal values do not permit reused qualification; IF02/03 Owner + independent review; exact resource-schema/oracle gates; IF-05 release/predicates and F3/F5 methods separately; real source IF-07 |
| TEMPORAL-SEQUENCE; F2 binding issuer; F3 schedule association owner | configuration_ref: ResourceRef<TEMPORAL_CONFIGURATION>; schedule_ref: ResourceRef<DECISION_SCHEDULE>; bindings: ordered SequenceMember[] 1..4096; exact membership/schedule length; annotations: ordered NoSessionAnnotation[] 0..4096; release_state: SequenceAccounting; provenance_ref: ResourceRef<SEMANTIC_TRACE> input manifest, never own completed EVIDENCE; scope: ScopeRecord | Same ordered binding/configuration record; position completion never asserts all admitted; Order/membership/duplicates/calendar/zone/cutoffs/config/bindings/evidence/schema/flags/annotations change; missing member blocks full release; IF02/03 Owner + independent review; exact resource-schema/oracle gates; IF-05 release/predicates and F3/F5 methods separately; real source IF-07 |
| F3-EXPERIMENT; Member B/F3 | hypothesis: ResourceRef<HYPOTHESIS>; input_binding: ExperimentInput; method: ResourceRef<METHOD>; protocol_ref: ResourceRef<PROTOCOL>; horizon_maturity_ref: ResourceRef<HORIZON_MATURITY>; seed: Int64 0..2^63-1; evaluation_plan_ref: ResourceRef<EVALUATION_PLAN> | Same deterministic experiment definition, not same execution attempt, valid inference or hypothesis support; Material hypothesis/protocol/data/time/method/version/seed/horizon/allowed-information change; outcome values themselves do not rewrite predeclared experiment; IF02/03 Owner + independent review; exact resource-schema/oracle gates; IF-05 release/predicates and F3/F5 methods separately; real source IF-07 |
| F3-RUN-ATTEMPT; Member B/F3 operation owner | attempt_id: Text: fresh issuer-scoped execution identifier; experiment_ref: ParentRef<F3-EXPERIMENT>; operation_receipt_ref: ResourceRef<NATIVE_RECEIPT>; immutable actual attempt/lifecycle revision, clocks/provenance/failure as specified by F3 owner; result_ref: Available{ref:ParentRef<RESULT>}  /  NotEvaluated | Identity of particular execution attempt/receipt revision; no deterministic equivalence or PIT authority; Fresh execution must use distinct attempt_id; immutable receipts record transition snapshots rather than overwriting sealed receipt; IF02/03 Owner + independent review; exact resource-schema/oracle gates; IF-05 release/predicates and F3/F5 methods separately; real source IF-07 |
| RESULT; Member B/F3 with owning method/F5 computation owners | experiment_ref: ParentRef<F3-EXPERIMENT>; realized_input_refs: ordered RealizedInputRef[] 0..4096; code_protocol_refs: ordered CodePinOrProtocol[] 1..4096; typed_results: ordered MetricResult[] 0..4096; empty cannot claim missing metrics are successful; limitations: ordered ResourceRef<LIMITATION>[] 0..4096 | Same contracted deterministic result content where method promises determinism; runner success and PIT axes separate; Actual metric/result/semantic diagnostic/protocol/code/input/mature outcome evidence changes; failed operation does not manufacture a successful result; IF02/03 Owner + independent review; exact resource-schema/oracle gates; IF-05 release/predicates and F3/F5 methods separately; real source IF-07 |
| EVIDENCE; F2/F3/F5 evidence owners by record kind | subject_ref: ParentRef<SOURCE-BYTES / F2-QUALIFICATION / F2-OBSERVATION / TEMPORAL-SEQUENCE / F3-EXPERIMENT / RESULT / F5-DECISION / F5-EVALUATION>; semantic_audit_ref: ResourceRef<SEMANTIC_EVIDENCE>; original exact attempt receipts separately retained; source_code_protocol_refs: ordered ProvenanceParent[] 1..4096; limitations: ordered ResourceRef<LIMITATION>[] 0..4096; evidence_claim: exact existing App evidence_class literal; default UNVERIFIED, no predicate grant | Same contracted semantic evidence record; no source authenticity or eligibility beyond separately established claim; Semantic evidence/lineage/limitation/claim/content/code/protocol drift; full exact attempt receipts kept separately and may differ; IF02/03 Owner + independent review; exact resource-schema/oracle gates; IF-05 release/predicates and F3/F5 methods separately; real source IF-07 |
| F5-DECISION; F5 owner | sequence_tick_ref: SequenceTickRef; policy_ref: ResourceRef<POLICY>; observation_refs: ordered ParentRef<F2-OBSERVATION>[] 1..4096; action: ResourceRef<ACTION>  /  NotEvaluated  /  NotApplicable; decision_execution_rules_ref: ResourceRef<EXECUTION_RULES> | Same deterministic policy decision inputs/action, not equivalent retrospective performance; Policy/seed/schedule/observation/action/execution convention drift; future evaluation outcome must not retroactively alter decision identity; IF02/03 Owner + independent review; exact resource-schema/oracle gates; IF-05 release/predicates and F3/F5 methods separately; real source IF-07 |
| F5-EVALUATION; F5 owner; F3 outcome maturity owner | decision_refs: ordered ParentRef<F5-DECISION>[] 1..4096; outcome_refs: ordered ResourceRef<OUTCOME / PRICE>[] 1..4096; evaluation_policy_ref: ResourceRef<EVALUATION_PROTOCOL>; metrics: ordered MetricResult[] 0..4096; limitations: ordered ResourceRef<LIMITATION>[] 0..4096 | Same contracted retrospective evaluation on common information and mature outcomes; never historical PIT certification; Outcome price/maturity/cost/execution/evaluation policy/metric/window/decision cohort drift; immature label blocks evaluation; IF02/03 Owner + independent review; exact resource-schema/oracle gates; IF-05 release/predicates and F3/F5 methods separately; real source IF-07 |

Nonidentity fields retain their predecessor exclusions: UI labels/display locators, mutable aliases and uncontracted presentation formatting never alter source/qualification identity; deterministic experiment/result excludes incidental attempt ID/clock/host/log/perf metadata. Actual source publication/outcome maturity are data, not incidental clocks. SOURCE-BYTES is a particular raw body; raw body hash/length excludes publisher/time claim. F3 attempt has fresh ID and immutable receipt revisions. RESULT excludes attempt; attempt may point to RESULT. EVIDENCE points toward subject/original input evidence; no subject hashes its own final EVIDENCE record. F5-DECISION contains authorized observations/action plan, excludes future outcome; F5-EVALUATION contains mature retrospective outcomes/cost/risk only. Changing authorization grant alone denies access without changing underlying content; changing semantic disclosure policy invalidates observation/release parents.

Closed helper record types (no implicit extra fields):

| Type | Exact fields / rule |
| --- | --- |
| Text | Unicode scalar string <=65536 UTF-8 bytes; role IDs/versions <=128; no normalization. All exact keys ASCII. |
| Hex64 | 64 lowercase hex ASCII characters; cannot substitute for a typed ParentRef. |
| SafeReason | exact {owner:Text,code:Text}; approved bounded non-secret codes only, raw reason audit-only; unknown public mapping retains immutable private original record, never blank success. |
| CodePin | exact {role:Text,path:Text,byte_length:UInt64,sha256:Hex64,semantic_version:Text}; relative approved owner path, no absolute/dot-dot/backslash traversal, raw hash integrity only. |
| ScopeFlags | exact {diagnostic_only:true,admission_eligible:false,trust:"NOT_TRUSTED_PIT_EVIDENCE",source_authentication:"NOT_ESTABLISHED",disposition:"INTEGRATED_PROVISIONAL"}; current diagnostic profile only, not new App enums. |
| ScopeRecord | exact {data_mode:<existing App data_mode>,pit_status:<existing App enum>,evidence_class:<existing App enum>,scope_flags:ScopeFlags}; current bounded case SYNTHETIC_GOLDEN/UNRESOLVED/UNVERIFIED; preserve applicable stronger access withholding independently. No execution success inferred. |
| AppAxes | exact {pit_status:<existing App enum>,execution_status:<existing App enum>,evidence_class:<existing App enum>,execution_scope_ref:ResourceRef<PROTOCOL>}; scope identifies actual operation owner/lifecycle, mandatory. Do not map Native invocation to F3 SUCCEEDED. |
| SourceVersionRef | exact {body_ref:ParentRef<SOURCE-BYTES>,version_ref:ResourceRef<SOURCE_VERSION>,representation_ref:Text,revision_history_ref:ResourceRef<SOURCE_VERSION_HISTORY>}; exact source history order inside independently approved resource. |
| CohortEntry | exact {issuer_ref:Text,feature_ref:Text}; array order declared by issuer; requested roster != qualified cohort. |
| TickContext | exact {tick_id:Text,tick_order:UInt64,decision_cutoff:TimeRecord,context_ref:Text}; no own envelope. |
| FeatureValue | exact {feature_ref:Text,value:Known<Int64 / FixedRatio6> / Unknown / NotEvaluated / Withheld,unit:Text,numeric_policy_ref:ResourceRef<NUMERIC_POLICY>}; no raw audit/future data; scale inside FixedRatio6. |
| SequenceMember | exact {tick:TickContext,binding_ref:ResourceRef<SEMANTIC_TRACE>,qualification_ref:ParentRef<F2-QUALIFICATION>,observation_ref:Available{ref:ParentRef<F2-OBSERVATION>} / Withheld,scope:ScopeRecord}; binding_ref resolves F2 private PerCutoffBinding view only under audit policy; policy view omits private audit locator. |
| NoSessionAnnotation | exact {iso_week:Text,kind:"NO_SESSION_WEEK",calendar_ref:ResourceRef<CALENDAR>}; ISO week valid under pinned calendar; annotation never becomes decision. |
| SequenceAccounting | exact {scheduled_count:UInt64,accounted_count:UInt64,position_outcomes:ordered SafeReason[],release_policy_ref:ResourceRef<OBSERVATION_RELEASE_POLICY>}; count equality proves accounting only; any required failure blocks all-qualified release. Do not encode all_eligible default. |
| ExperimentInput | exact tagged union {kind:"SEQUENCE",temporal_binding_set_ref:ParentRef<TEMPORAL-SEQUENCE>,association_contract_version:"experiment-sequence-binding-candidate-v0.1"} OR {kind:"SINGLE_CUTOFF",observation_ref:ParentRef<F2-OBSERVATION>,single_cutoff_contract_ref:ResourceRef<PROTOCOL>}; no association instance parent in EXPERIMENT; original seven DTOs not modified by this conceptual union. |
| SequenceTickRef | exact {sequence_ref:ParentRef<TEMPORAL-SEQUENCE>,tick_order:UInt64,tick_id:Text}; position must resolve uniquely and agree with cutoff/observation context. |
| RealizedInputRef | ParentRef<SOURCE-BYTES / F2-QUALIFICATION / F2-OBSERVATION / TEMPORAL-SEQUENCE> OR ResourceRef<OUTCOME / PRICE>; declared ordered union, not arbitrary reference; evaluation-only refs denied at decision boundary. |
| CodePinOrProtocol | exact tagged union {kind:"CODE",pin:CodePin}  /  {kind:"PROTOCOL",ref:ResourceRef<PROTOCOL / NUMERIC_POLICY / EVALUATION_PROTOCOL>}. |
| MetricResult | exact {metric_ref:ResourceRef<RESULT_METRIC>,value:Known<Int64 / Decimal / FixedRatio6> / Unknown / NotEvaluated,unit:Text,denominator:Known<UInt64> / NotApplicable,diagnostic_ref:ResourceRef<STATE> / NotApplicable}; actual metric/diagnostic schema remains blocked by IF03-OD01-S1 until owning protocol review. |
| ProvenanceParent | ParentRef<registered ten-domain resource except EVIDENCE itself> OR ResourceRef<registered semantic resource>; full transitive graph must remain acyclic, no subject->own EVIDENCE edge. |

Registered ResourceRef role literals: `CALENDAR`, `TEMPORAL_CONFIGURATION`, `DECISION_SCHEDULE`, `MANIFEST`, `SOURCE_VERSION_HISTORY`, `SOURCE_VERSION`, `COVERAGE`, `SEMANTIC_TRACE`, `NATIVE_RECEIPT`, `SEMANTIC_EVIDENCE`, `OBSERVATION_RELEASE_POLICY`, `OBSERVATION_RELEASE_RECEIPT`, `AUDIT_ACCESS_POLICY`, `READER_CAPABILITY_POLICY`, `ASSOCIATION_PROTOCOL`, `EXPERIMENT_ASSOCIATION`, `AUTHOR_RECORD`, `OWNER_DECISION`, `METHOD`, `HYPOTHESIS`, `PROTOCOL`, `HORIZON_MATURITY`, `EVALUATION_PLAN`, `POLICY`, `EXECUTION_RULES`, `EVALUATION_PROTOCOL`, `POLICY_EVALUATION_PROTOCOL`, `OUTCOME`, `PRICE`, `NUMERIC_POLICY`, `TIMEZONE_RULES`, `PROJECTION_POLICY`, `SOURCE_TEXT`, `ORIGIN`, `RESULT_METRIC`, `LIMITATION`, `ACTION`, `SCHEDULE_INVARIANT_POLICY`, `SOURCE_CADENCE`, `STATE`. Unknown roles or unreviewed resource_schema refuse REF_UNAPPROVED_RESOURCE_SCHEMA. References require owner/verifier rights; content pin does not approve the schema, protocol or source. External F3/F5 method/metric/trace schemas and bytes remain NOT_SUPPLIED under IF03-OD01-S1. Canonical grammar can be specified now; full-domain golden oracle cannot be invented from these missing bodies.

Local identities remain separate: WU01 input_bytes/payload_pin is authored input integrity (synthetic_contracts L209–L236); A04 request digest is local wire(spec,slots,source identity) (derived_observations L531–L534); S3 reconstruction, A04 realization and A05 realization have owner-specific context/lineage/numeric/code preimages (selection L1094–L1118; derivation L416–L440; ratio L266–L290). A05 diagnostic input includes local checkout/status and result digest (ratio_observations L282–L330/L477–L486). B03 semantic_bytes excludes selected audit/clock fields and sorts a scoped set list; identity has B03- presentation prefix (causal_derivation L419–L477). None equal this new frame by assertion. Native replay consistency is not independent App canonical acceptance.

### AD01-10. All 350 sensitivity dispositions and explicit MAY adjudication

The predecessor's 35×10 dispositions are carried forward with original_disposition, candidate_disposition, source pointers and scope refinements in the external evidence matrix. These are 350 **specification cells**, not executable tests. C=MUST_CHANGE; N=MUST_NOT_CHANGE; B=BLOCKS_REPLAY. All original MAY_CHANGE cells have explicit candidate choices below; none are silently resolved as adopted policy. Changes compare the specified subject and declared parents, not arbitrary unrelated fields. Old sealed objects remain historical. For fixed WU04 profile, invalid replacement/order/duplicate refuses instead of minting a valid new sequence. A new attempt is required for changed experiment/result; an old sealed attempt cannot be relinked.

| Mutation | SRC | QUAL | OBS | SEQ | EXP | ATT | RES | EVID | DEC | EVAL |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M01 t2 -> t3: same feature/selected D2 bytes, different cutoff/context/reconstruction/realization | N | C | C | C | C | B | C | C | C | C |
| M02 Publication evidence declaration changes 17:59:59 -> 18:00:00 at t1, raw body held constant | N | C | C | C | C | B | C | C | C | C |
| M03 Attempt to insert D3 published t3+1 second into t3 decision, source bytes unchanged | N | B | B | B | B | B | B | B | B | B |
| M04 reorder tick relative to fixed four-member contract | N | N | N | B | B | B | B | B | B | B |
| M05 drop tick relative to fixed four-member contract | N | N | N | B | B | B | B | B | B | B |
| M06 duplicate tick relative to fixed four-member contract | N | N | N | B | B | B | B | B | B | B |
| M07 add tick relative to fixed four-member contract | N | N | N | B | B | B | B | B | B | B |
| M08 Change W03 no-session calendar annotation but retain exact valid decision tick values | N | C | C | C | C | B | C | C | C | C |
| M09 Change qualification manifest reference, same individual raw source bodies | N | C | C | C | C | B | C | C | C | C |
| M10 Change calendar version/rule used by all ticks, valid replacement | N | C | C | C | C | B | C | C | C | C |
| M11 Change only F3 horizon/rebalance temporal configuration, retaining F2 source qualification | N | N | N | C | C | B | C | C | C | C |
| M12 Change experiment seed only, holding F2 data binding fixed | N | N | N | N | C | B | C | C | C | C |
| M13 Change WU01 pack seed and therefore manifest/pack pin, same individual revenue source raw bytes | N | C | C | C | C | B | C | C | C | C |
| M14 Change future evaluation price/label value outside pinned decision manifest | N | N | N | N | N | B | C | C | N | C |
| M15 Change future price bytes inside full WU01 pack/manifest pin while individual revenue body unchanged | N | C | C | C | C | B | C | C | C | C |
| M16 Change issuer in qualified Native request without matching evidence | N | B | B | B | B | B | B | B | B | B |
| M17 Change approved feature name/definition only, new valid projection | N | C | C | C | C | B | C | C | C | C |
| M18 Change feature unit or FixedRatio scale without approved new numeric contract | N | B | B | B | B | B | B | B | B | B |
| M19 Change missing typed reason/UnknownCause in original Native qualification evidence | N | C | C | C | C | B | C | C | C | C |
| M20 Mutate original source body bytes with unchanged alias | C | C | C | C | C | B | C | C | C | C |
| M21 Change original source/version/revision/notice chain metadata, exact source body held fixed | N | C | C | C | C | B | C | C | C | C |
| M22 Qualified Native state transitions to unresolved/refusal with same bodies | N | C | C | C | C | B | C | C | C | C |
| M23 Source history/coverage becomes inaccessible, bodies pinned but unavailable for independent replay | N | B | B | B | B | B | B | B | B | B |
| M24 Relevant Native evaluator/adapter bytes drift with source bodies fixed | N | C | C | C | C | B | C | C | C | C |
| M25 Different valid original zone/text/origin for same UTC instant under future broadened profile | N | C | C | C | C | B | C | C | C | C |
| M26 Only cosmetic UI label changes outside semantic limitation/feature registry | N | N | N | N | N | N | N | N | N | N |
| M27 New actual run attempt ID, deterministic inputs/result unchanged | N | N | N | N | N | C | N | N | N | N |
| M28 Only execution wall-clock measurement/performance receipt changes | N | N | N | N | N | C | N | N | N | N |
| M29 Change predeclared metric/protocol/horizon/method version with F2 binding unchanged | N | N | N | N | C | B | C | C | C | C |
| M30 Change F5 policy version/cost assumption after a fixed F3-only statistical experiment | N | N | N | N | N | N | N | N | C | C |
| M31 Actual outcome maturity not met at required evaluation/fit time | N | N | N | N | N | B | B | C | N | B |
| M32 Change actual execution-price/evaluation rule only, leaving decision action plan fixed | N | N | N | N | N | B | C | C | N | C |
| M33 Immutable canonical schema/domain/profile version changes | B | B | B | B | B | B | B | B | B | B |
| M34 New repository commit changes only unrelated uninspected code; relevant owner code pins unchanged | N | N | N | N | N | C | N | N | N | N |
| M35 Change immutable semantic limitation/provenance evidence while values equal | N | N | N | N | N | N | N | C | N | N |

Column domains, in order: SOURCE-BYTES, F2-QUALIFICATION, F2-OBSERVATION, TEMPORAL-SEQUENCE, F3-EXPERIMENT, F3-RUN-ATTEMPT, RESULT, EVIDENCE, F5-DECISION, F5-EVALUATION.

| Original MAY cell | Candidate disposition | Exact scope / rationale |
| --- | --- | --- |
| M08 / F2-QUALIFICATION | MUST_CHANGE | Candidate qualification explicitly pins whole calendar and feature cohort; dependent observation inherits qualification. |
| M08 / F2-OBSERVATION | MUST_CHANGE | Candidate qualification explicitly pins whole calendar and feature cohort; dependent observation inherits qualification. |
| M17 / F2-QUALIFICATION | MUST_CHANGE | Candidate qualification explicitly pins whole calendar and feature cohort; dependent observation inherits qualification. |
| M18 / F2-QUALIFICATION | BLOCKS_REPLAY | Current Native unit/scale contract unsupported; no valid replacement qualification until new numeric/source schema adopted. |
| M30 / F3-EXPERIMENT | MUST_NOT_CHANGE | Narrow scenario explicitly fixed F3-only experiment/RESULT/EVIDENCE; later independent F5 policy is not in these preimages. Embedded F5 artifacts are another declared scenario requiring dependent refs to change. |
| M30 / RESULT | MUST_NOT_CHANGE | Narrow scenario explicitly fixed F3-only experiment/RESULT/EVIDENCE; later independent F5 policy is not in these preimages. Embedded F5 artifacts are another declared scenario requiring dependent refs to change. |
| M30 / EVIDENCE | MUST_NOT_CHANGE | Narrow scenario explicitly fixed F3-only experiment/RESULT/EVIDENCE; later independent F5 policy is not in these preimages. Embedded F5 artifacts are another declared scenario requiring dependent refs to change. |
| M31 / EVIDENCE | MUST_CHANGE | New actually observed evidence receipt records maturity withholding; old sealed evidence retained. No completed result is fabricated. |
| M34 / EVIDENCE | MUST_NOT_CHANGE | Assume independently reviewed relevant code closure unchanged; deterministic EVIDENCE excludes checkout commit. If closure proof absent, REF_STALE/BLOCKS_REPLAY instead, never assume unrelated. |
| M35 / F2-QUALIFICATION | MUST_NOT_CHANGE | Narrow to EVIDENCE-owned limitation/provenance record only; no upstream field/parent changed. Qualification reason changes are M19; method/metric changes M29. |
| M35 / F2-OBSERVATION | MUST_NOT_CHANGE | Narrow to EVIDENCE-owned limitation/provenance record only; no upstream field/parent changed. Qualification reason changes are M19; method/metric changes M29. |
| M35 / TEMPORAL-SEQUENCE | MUST_NOT_CHANGE | Narrow to EVIDENCE-owned limitation/provenance record only; no upstream field/parent changed. Qualification reason changes are M19; method/metric changes M29. |
| M35 / F3-EXPERIMENT | MUST_NOT_CHANGE | Narrow to EVIDENCE-owned limitation/provenance record only; no upstream field/parent changed. Qualification reason changes are M19; method/metric changes M29. |
| M35 / RESULT | MUST_NOT_CHANGE | Narrow to EVIDENCE-owned limitation/provenance record only; no upstream field/parent changed. Qualification reason changes are M19; method/metric changes M29. |
| M35 / F5-DECISION | MUST_NOT_CHANGE | Narrow to EVIDENCE-owned limitation/provenance record only; no upstream field/parent changed. Qualification reason changes are M19; method/metric changes M29. |
| M35 / F5-EVALUATION | MUST_NOT_CHANGE | Narrow to EVIDENCE-owned limitation/provenance record only; no upstream field/parent changed. Qualification reason changes are M19; method/metric changes M29. |

M01 C for sequence refers to a separately constructed valid sequence whose member/context differs, not lookup inside the unchanged four-tick container. M14/M32 concern an outcome/rule actually used by the compared RESULT/EVALUATION; unused unreferenced future values cannot alter an earlier observation. M15 separately covers changing future bytes inside the full WU01 manifest pin, which stales dependent binding integrity even when features equal. M30 fixes F3-only experiment/result/evidence; adding embedded F5 results is a different explicit dependency case. M34 requires independently established unchanged relevant code closure; absent closure proof blocks replay. M35 narrows to EVIDENCE-owned limitation/provenance only; upstream state changes are M19/M29. Wrong domain/schema/profile, wrong principal, unavailable raw audit, dangling refs or partial sequence always deny the affected release/replay through AD01-05 refusal codes; no false all-eligible result.

### AD01-11. Independent golden oracle and two-channel replay gate

No golden data, expected canonical digest, codec or runtime is produced. Future oracle must be independently authored/reviewed **before** codec implementation. Owner later appoints an Independent Author separate from implementer, and Independent Reviewer separate from derivation/implementation where possible; assignments/signoffs are NOT_SUPPLIED here. Only a later authorized, evidence-backed freeze may label the completed vector set frozen; this draft does not.

Channel A — Source/Qualification Replay: under distinct audit capability, resolve exact approved source/version/manifest/calendar/time/coverage and correction evidence; observe genuine relevant code; reissue public Native S1/S2/S3/A04/A05 requests at every actual cutoff. Preserve original first typed failure/cause/lineage/output and actual invocation receipts; derive strict permitted read without future data. Stored completed result or B03 midnight is not Weekly execution. Detached JSON equality is insufficient.

Channel B — Typed Identity/Result Replay: validate exact domain/schema/profile/type/parent rights and acyclic graph; reconstruct adopted CanonicalPayload/full frame against independently frozen expected bytes/digests; verify parent pins and invalidation. Genuine F3/F5 reruns require their own accepted method/protocol/admission scope. Distinguish deterministic experiment/result identity from new Run Attempt ID; hash/value equality alone proves neither execution nor admission.

Each independent vector requires: ID/version; immutable source commit/blob/pins and exact line/pointer; field schema/domain/profile; **complete payload bytes**, **complete frame bytes**, independently checked expected digest (never generated by codec under test), expected relation or exact refusal; parent/rights context; author/reviewer provenance/signoff; limitations/version and frozen manifest SHA. Cover four original WU04 ticks/t2-t3 contexts, Int64/UInt64/bool/Decimal/FixedRatio6/overflow, Unicode/escaping, duplicate/unknown keys/null vs missing/tags, zone/origin/offset/precision/rules, domain/schema/profile substitution, self-reference/cycles/foreign/stale refs, source/code/time drift, order/partial sequence and same experiment fresh attempt. Do not use WU04 read serialization or implementation hash routine to manufacture expected new canonical bytes/digests.

Current absence control remains NOT_CONSTRUCTIBLE for accepted whole-path Weekly NO_QUALIFIED_CLAIM source cohort; full Weekly withheld source is DEFERRED; real TWSE historical claims remain IF-07-gated. Actual App/F3/F5 vectors and source authentication are unavailable, not fake metrics. Python/TypeScript parity is later only if an approved TypeScript consumer/runtime exists; none is asserted by this text. Scalar/frame grammar exact candidates can be reviewed, but unratified bounds/time/resource schemas block full oracle authoring. Runtime checks all NOT_RUN.

### AD01-12. Eleven Owner decisions, dependencies and next closure

Each row is CANDIDATE_FOR_OWNER_RATIFICATION; approval proof NOT_SUPPLIED; independent reviewers/author names TBD_BY_LEAD, not appointed here. Selection is drafting recommendation, not approval. Exact alternatives/tradeoffs/conflicts and original source citations are preserved in the external Owner Decision Sheet and decision_register.json.

| Parent ID | Draft selection | Approving / independent reviewing role | Affected clauses |
| --- | --- | --- | --- |
| IF02-OD01 | A with explicit F3 association/discovery and capability conditions; B fallback if resource discoverability outweighs migration burden | Owner + Technical Lead/F2 + Member B/F3 / Member B/F3, F5 owner, Member C/F6, independent reviewer | AD01-02 |
| IF02-OD02 | F2 issues immutable per-cutoff evidence/observation refs and accounted set; F3 approves schedule/protocol association; F5 references execution/evaluation rules | Technical Lead/F2 + Member B/F3 + F5 owner / independent reviewer + Member C/F6 | AD01-03, AD01-04 |
| IF02-OD03 | Separate audit capability; omit private locator from policy view; same-capability resolver fails required separation | Technical Lead/F2 + Owner / independent reviewer + Member B/F3 + F5 owner + Member C/F6 | AD01-05 |
| IF02-OD04 | Fail closed, original Native state/reason/unknown/first failure and invocation preserved; no positive/explicit negative predicate granted | Technical Lead/F2 + Owner / independent reviewer + Member B/F3 | AD01-06 |
| IF02-OD05 | Preserve original single-cutoff snapshot_id meaning; explicit SEQUENCE association and reader refusal; no first-tick substitution | Member B/F3 + Technical Lead/F2; Member C/F6 consumer agreement / F5 owner + independent reviewer | AD01-03 |
| IF03-OD01 | Typed JSON candidate with int/decimal/FixedRatio tags; strict fields, duplicate refusal, Unicode/time/number policies from CAN ledger | Technical Lead/F2 + Member B/F3 + Owner / Member C/F6 + independent oracle author/reviewer | AD01-07 |
| IF03-OD02 | Retain original declaration and origin in qualification identity; time relation uses UTC; current WU01 strict SECOND/Taipei profile preserved | Technical Lead/F2 + Member B/F3 / independent reviewer + F5 owner | AD01-07.CAN-03 |
| IF03-OD03 | Length-framed domain/schema/payload with required canonical_profile_version in payload; own envelope outside; typed acyclic parents, payload-only length; CAN-04/05 candidate. | Technical Lead/F2 + Member B/F3 + Owner / independent reviewer + Member C/F6 | AD01-08, AD01-09 |
| IF03-OD04 | Separate F3-EXPERIMENT, RESULT/EVIDENCE semantic identities from F3-RUN-ATTEMPT receipt; retain actual availability times as data | Member B/F3 + Technical Lead/F2 + F5 owner / independent reviewer | AD01-07.CAN-08, AD01-09 |
| IF03-OD05 | Independent author/reviewer and fixed oracle manifest before implementation; two-channel genuine Native replay and identity checks; unconstructible controls explicit | Owner/Technical Lead appoint independent oracle author + reviewer; Member B/F3 / F2/F3/F5 owners + separate independent reviewer | AD01-11 |
| IF23-OD01 | Two-doc additive draft only now; independent review and explicit ratification before later oracle authoring/freeze, codec/private binding, IF-05/F3/F5, and separate Git integration. | Owner + Technical Lead/F2 / Member B/F3 + independent reviewer; F5/F6 review interfaces | AD01-12 |

| Subdecision linked to existing parent | Pending exact choice | Blocking use |
| --- | --- | --- |
| IF02-OD05-S1 → IF02-OD05 | F3-owned exact-key immutable association registry, explicit reader capability descriptor, no snapshot_id fallback; CONTRACT_ONLY / NO_PORT | Before F3 sequence submission or IF-04 transport implementation |
| IF03-OD03-S1 → IF03-OD03 | Own ReferenceEnvelope outside payload; required canonical_profile_version literal INSIDE every CanonicalPayload; typed parent cores only; payload length excludes frame | Before any byte/digest oracle or codec |
| IF02-OD03-S1 → IF02-OD03 | Policy principal never gets audit capability/locator; access checks and immutable resolution receipt required; enforcement NOT_IMPLEMENTED / IF-04_OR_CAPABILITY_GATE | Before any observation release/resolver deployment |
| IF03-OD02-S1 → IF03-OD02 | Pinned timezone-rules resource and unique offset/zone interpretation; no host-default tzdb. Current WU01 restricted to Taipei SECOND +08:00 | Before broader-zone independent time oracle |
| IF03-OD01-S1 → IF03-OD01 | Closed typed ResourceRef roles; reject unknown/unreviewed resource schema. Owner must freeze actual resource bytes/schema under F2/F3/F5 gates | Blocks full F3/F5-domain oracle authoring, not drafting scalar/frame grammar |
| IF03-OD03-S2 → IF03-OD03 | Seal F3 experiment using sequence ref and association CONTRACT VERSION, then association refers to sealed experiment; experiment never hashes association instance. Evidence receipt points toward subject; subject never hashes its own evidence receipt | Before association/evidence identity issuance |
| IF03-OD01-S2 → IF03-OD01 | Int64/UInt64 decimal tags; decimal coefficient Int64 and scale 0..18; 16MiB payload, 64 depth, 4096 items, 65536-byte text. Proposed choices, not Native generalization | Owner must ratify numeric/bounds grammar before oracle bytes authored |

Boundary gates: IF-02 logical design is not translator/consumer acceptance. IF-03 byte/oracle design is not tested replay. IF-05 separately reviews/tests positive and explicit negative mode-specific predicates; IF-07 separately reviews real-source rights/time/version/authentication. IF-04 transport/capability enforcement and IF-06 fixtures/F6 display remain separate. F3 method/horizon/train-label maturity/run and F5 same-information policy/action/price/cost/outcome acceptance remain separate. Formal CAP-F2 B04, Layer B, PG17/TestLease and physical consumers retain existing no-go boundaries. No source/test/fixture/CI/dependency changes or runtime work are authorized here.

Milestones remain planning targets: IF-03 decision 2026-12-15 before first M1 identity/replay acceptance; M1 genuine experiment 2026-12-31; M2 genuine UI/backend 2027-01-31. No target is automatic acceptance and no teammate progress is inferred. Next path: independent contract adoption review of these exact two additive diffs; explicit Owner decisions/subdecisions and evidence-backed closure; later separately authorized independent oracle authoring/review/freeze; then separately authorized codec/private binding/IF-05/F3/F5/F6 work. Git integration is separate: no commit, push, PR or merge in ADOPT-01.

Acceptance dimensions remain separately reported: source definitions IMPLEMENTED_AND_INSPECTED; earlier documents REVIEWED_SOURCE_POLICY_PROPOSAL; this appendix OWNER_DIRECTED_CANDIDATE; signed adoption NOT_SUPPLIED; independent adoption review PENDING; oracle/runtime NOT_RUN; admission/implementation/contract freeze NOT_AUTHORIZED. The earlier historical frozen wording is not evidence that this draft was ratified.

## MVP-IF-02-IF-03-RATIFY-01 — Owner ratification and boundary record v0.1

### RT01-01. Actual Owner evidence and temporal scope

**OWNER_RATIFIED_DOCS_ONLY_REVIEW_PENDING.** The Owner's direct ratification message explicitly approves the eleven parents and seven linked children below as EXACT against both pinned ADOPT-01 document versions. It authorizes this two-document documentary adoption and delivery to Independent Review. No further Ready-to-Sign form or repeated Owner signoff is required. This record is an additive status/provenance overlay: the entire approved ADOPT-01 text, historical 211-line prefix, original alternatives, original proposal statuses and audit history remain unchanged. Earlier candidate/pending statements record their historical stage; they are not retroactively rewritten.

Owner evidence catalog ID: `OWNER-RATIFY01-20261114-01` (agent-assigned evidence reference for the actual direct message, not an external signing service). Actor: current user expressly acting as PIT Research Lab Academic MVP Owner; no separate legal name, hidden account ID, cryptographic signature or other-role identity is inferred. Message-date context is 2026-11-14 / Asia/Taipei, DAY precision from the supplied conversation environment. Exact approval wall-clock was not supplied; audit recording time in the external receipt is not a fabricated signing time. The Owner expressly makes this direct message the ratification evidence.

Attributable approval excerpt:

> 我以 PIT Research Lab Academic MVP Owner 身分，正式核准本輪已審查的 **11 項 Parent Decisions 與 7 項 Linked Subdecisions**，採用 RATIFY-01 Decision Ledger 中的 `EXACT` 候選方案。

The message also states:

> **本訊息即為 Owner Ratification Evidence。** 不需要額外的 Ready-to-Sign Form 或重複簽核程序。

> 其他角色的獨立審查或必要工程驗收，不因本次 Owner Ratification 而自動視為通過。

Recorded UTF-8 message-transcription integrity SHA-256: `90d0b6acf24829bc9bc46de6a35f1830cb47db3b9fc142248aed16dc17d2565d` (`owner_ratification_evidence.json` and `Owner_Ratification_Message.md` in the RATIFY-01 Owner evidence packet). This is a source-transcription/package pin, not an IF-03 identity or cryptographic signature. The operative evidence is the actual direct user message with the exact ID set and approved hashes, not the agent-assigned catalog label.

| Owner-approved preimage | Bytes | SHA-256 |
| --- | --- | --- |
| docs/mvp/v1.0/shared-interface-contract-v0.1.md | 123536 | 32ae716c234549c636d4c9a2479835b9caa9f39a721a4f055dc9268a2b99060d |
| docs/mvp/v1.0/ux-adr-01-temporal-execution-contract-v0.1.md | 18779 | 5919314a94b9962d7c23ebb4308d72b2e6ce51b9645bf97f05eab8196ea41ce3 |

The new RATIFY appendices change document bytes solely by adding this authorized receipt/status/boundary record. The two pins above remain the immutable Owner-approved contract preimages; final documentary hashes and incremental ratification patches are recorded externally for Independent Review. No self-hash or new canonical digest is inserted into a contract payload.

### RT01-02. Eleven parents and seven children — individual EXACT disposition

Every row is **RATIFIED_EXACT at the Owner dimension** under the same explicit direct-message receipt, not inferred from its parent. The selected choice is the existing RATIFY-01 Decision Ledger EXACT candidate at the two approved hashes. No schema field, Resource body, identity value, profile literal or numeric/time parameter is amended. Required F2/F3/F5/F6 consultations and independent acceptance remain separately pending; an Owner row does not impersonate those roles.

| Decision / parent | Exact adopted candidate | Approved controlling clauses | Owner disposition |
| --- | --- | --- | --- |
| IF02-OD01 | A with explicit F3 association/discovery and capability conditions; B fallback if resource discoverability outweighs migration burden | AD01-02 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF02-OD02 | F2 issues immutable per-cutoff evidence/observation refs and accounted set; F3 approves schedule/protocol association; F5 references execution/evaluation rules | AD01-03, AD01-04 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF02-OD03 | Separate audit capability; omit private locator from policy view; same-capability resolver fails required separation | AD01-05 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF02-OD04 | Fail closed, original Native state/reason/unknown/first failure and invocation preserved; no positive/explicit negative predicate granted | AD01-06 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF02-OD05 | Preserve original single-cutoff snapshot_id meaning; explicit SEQUENCE association and reader refusal; no first-tick substitution | AD01-03 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF03-OD01 | Typed JSON candidate with int/decimal/FixedRatio tags; strict fields, duplicate refusal, Unicode/time/number policies from CAN ledger | AD01-07 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF03-OD02 | Retain original declaration and origin in qualification identity; time relation uses UTC; current WU01 strict SECOND/Taipei profile preserved | AD01-07.CAN-03 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF03-OD03 | Length-framed domain/schema/payload with required canonical_profile_version in payload; own envelope outside; typed acyclic parents, payload-only length; CAN-04/05 candidate. | AD01-08, AD01-09 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF03-OD04 | Separate F3-EXPERIMENT, RESULT/EVIDENCE semantic identities from F3-RUN-ATTEMPT receipt; retain actual availability times as data | AD01-07.CAN-08, AD01-09 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF03-OD05 | Independent author/reviewer and fixed oracle manifest before implementation; two-channel genuine Native replay and identity checks; unconstructible controls explicit | AD01-11 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF23-OD01 | Two-doc additive draft only now; independent review and explicit ratification before later oracle authoring/freeze, codec/private binding, IF-05/F3/F5, and separate Git integration. | AD01-12 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF02-OD03-S1 → IF02-OD03 | Policy principal never gets audit capability/locator; access checks and immutable resolution receipt required; enforcement NOT_IMPLEMENTED / IF-04_OR_CAPABILITY_GATE | AD01-05 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF02-OD05-S1 → IF02-OD05 | F3-owned exact-key immutable association registry, explicit reader capability descriptor, no snapshot_id fallback; CONTRACT_ONLY / NO_PORT | AD01-03 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF03-OD01-S1 → IF03-OD01 | Closed typed ResourceRef roles; reject unknown/unreviewed resource schema. Owner must freeze actual resource bytes/schema under F2/F3/F5 gates | AD01-09 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF03-OD01-S2 → IF03-OD01 | Int64/UInt64 decimal tags; decimal coefficient Int64 and scale 0..18; 16MiB payload, 64 depth, 4096 items, 65536-byte text. Proposed choices, not Native generalization | AD01-07, AD01-07.CAN-02 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF03-OD02-S1 → IF03-OD02 | Pinned timezone-rules resource and unique offset/zone interpretation; no host-default tzdb. Current WU01 restricted to Taipei SECOND +08:00 | AD01-07.CAN-03 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF03-OD03-S1 → IF03-OD03 | Own ReferenceEnvelope outside payload; required canonical_profile_version literal INSIDE every CanonicalPayload; typed parent cores only; payload length excludes frame | AD01-07.CAN-04, AD01-07.CAN-05, AD01-08 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |
| IF03-OD03-S2 → IF03-OD03 | Seal F3 experiment using sequence ref and association CONTRACT VERSION, then association refers to sealed experiment; experiment never hashes association instance. Evidence receipt points toward subject; subject never hashes its own evidence receipt | AD01-03, AD01-07.CAN-05, AD01-09 | RATIFIED_EXACT; OWNER-RATIFY01-20261114-01 |

### RT01-03. Limited architecture and scalar/framing normative scope

**IF02_LOGICAL_ARCHITECTURE: OWNER_RATIFIED_DESIGN / INDEPENDENT_REVIEW_PENDING.** Adopt the existing Sidecar-first TemporalBindingSet/ordered PerCutoffBinding design, explicit F3-owned ExperimentSequenceBinding/exact-key discovery and reader capability refusal, singular snapshot_id preservation, source/observation/audit/evaluation ownership and no-promotion constraints. A legacy reader cannot silently receive t1, an aggregate alias or untyped temporal_policy fallback. Audit locator/capability never enters the policy principal's safe view; operation/principal/grant/resource-bound resolution and immutable receipt are required but NOT_IMPLEMENTED. A bare opaque locator is not an access barrier. The seven proposed App DTOs/ResearchClient are not implemented or changed by this status record.

**IF03_SCALAR_FRAMING_PROFILE: OWNER_RATIFIED_PROFILE_SPEC / INDEPENDENT_REVIEW_PENDING.** `IF03_SCALAR_FRAMING_NORMATIVE_SCOPE` means only the exact existing scalar/JSON/time/framing/reference-separation rules and general invariants in the approved CAN clauses below. The literal `typed-json-candidate-v0.1` and the existing domain/schema/version literals remain exactly as approved; a name containing "candidate" is not silently renamed. This is not complete domain Resource schema adoption or concrete reference issuance. The Owner ratified the explicit blocking rule for missing/unreviewed Resource schemas, not fictional missing bodies.

Approved bounds remain Int64 [-2^63,2^63-1], UInt64 [0,2^64-1], decimal coefficient Int64 and scale 0..18, 16 MiB canonical payload, depth 64, collection limit 4096 and Text limit 65536 UTF-8 bytes, as defined by the pinned text. These are scoped contract choices, not Native-wide changes. Original time/zone/offset/precision/origin remain evidence, derived UTC remains comparison, and pinned timezone rules are required; current WU01 remains Asia/Taipei / SECOND / +08:00. Concrete timezone-resource bytes/schema and full domain oracles remain separate prerequisites.

Frame remains LP64BE(domain UTF-8 bytes) || LP64BE(object-schema UTF-8 bytes) || LP64BE(canonical payload bytes), each prefix counting the immediately following segment in bytes. Required canonical_profile_version is inside the hashed payload and must agree with the outside envelope; own digest/locator is outside its preimage; envelope length is payload-only. Typed parents remain acyclic. Seal experiment using sequence plus association CONTRACT VERSION before the association references the experiment; never hash its own association INSTANCE. Evidence points toward subject, not subject toward its own final receipt. No code or digest is evaluated/issued here.

| Approved CAN clause | Unchanged approved text location | Explicit Owner decision basis |
| --- | --- | --- |
| CAN-01 | AD01-07.CAN-01 L455–L456 | IF03-OD01, IF03-OD01-S2 |
| CAN-02 | AD01-07.CAN-02 L457–L458 | IF03-OD01, IF03-OD01-S2 |
| CAN-03 | AD01-07.CAN-03 L459–L460 | IF03-OD02, IF03-OD02-S1 |
| CAN-04 | AD01-07.CAN-04 L461–L462 | IF03-OD03, IF03-OD03-S1 |
| CAN-05 | AD01-07.CAN-05 L463–L464 | IF03-OD03, IF03-OD03-S1, IF03-OD03-S2 |
| CAN-06 | AD01-07.CAN-06 L465–L466 | IF03-OD01, IF03-OD03, IF23-OD01 |
| CAN-07 | AD01-07.CAN-07 L467–L468 | IF02-OD04, IF03-OD01 |
| CAN-08 | AD01-07.CAN-08 L469–L470 | IF03-OD04 |
| CAN-09 | AD01-07.CAN-09 L471–L472 | IF02-OD02, IF03-OD03 |
| CAN-10 | AD01-07.CAN-10 L473–L474 | IF03-OD03, IF03-OD05, IF23-OD01 |

CAN-01..10 approval is scoped to the exact declared grammar/framing/provenance/ordering/migration rules. External Resource-body schemas, actual method/metric/model semantics, independent golden bytes/digests, cross-language parity, observed code/Native execution and replay acceptance are not acquired by ratifying their prerequisite rules. Local WU01 input pins, S3 reconstruction, A04/A05 realizations and B03 semantic identities retain distinct preimages; no universal App equivalence is granted.

### RT01-04. Scope-of-Freeze Register — independent dimensions retained

Owner approval is now recorded; **independent boundary/design closure and any applicable other-role signoffs remain pending**. No blanket IF-02/03 freeze or runtime acceptance is declared by this agent. The following register is normative as an Owner-approved boundary statement; its blocked rows remain blocked.

| Scope | Current disposition | Remaining blocking gate | Limitations |
| --- | --- | --- | --- |
| IF02_LOGICAL_ARCHITECTURE | OWNER_RATIFIED_DESIGN / INDEPENDENT_REVIEW_PENDING | Applicable other-role signoffs and independent review of actual RATIFY-01 deltas before design closure/implementation | Owner EXACT adoption of existing Sidecar/association/capability/no-promotion design only; WU04 diagnostic flags unchanged. No translator/API/resolver/runtime/admitted snapshot. |
| IF03_SCALAR_FRAMING_PROFILE | OWNER_RATIFIED_PROFILE_SPEC / INDEPENDENT_REVIEW_PENDING | Independent review of approved exact CAN-01..10 scalar/framing text; concrete Resource schemas/vectors/codec/parity/replay remain separately blocked | Owner approved exact existing bounds/time/framing choices, not a Native-wide rule, full domain adoption, canonical reference or executed replay. |
| IF03_DOMAIN_IDENTITY | DEFERRED_WITH_BLOCKING_GATE | Reviewed concrete Resource body schemas/bytes, typed parent graphs and references, independently authored vectors | No concrete canonical reference issuance or universal hash equality; independent of scalar design |
| IF03_GOLDEN_ORACLE | NOT_RUN / NOT_FROZEN | Separately authorized independent author/reviewer, full expected payload/frame/digest/refusal vectors and immutable oracle manifest | Owner adopted independent-author-before-codec procedure only. No author/reviewer appointed, vectors/digests created, freeze or execution authorized. |
| IF03_REPLAY_ACCEPTANCE | NOT_RUN | Genuine Native Channel A and Identity/Result Channel B under their own approved contracts with independent expected results | No stored completed result, diagnostic read or old local hash substitutes for execution |
| IF05_ELIGIBILITY_TRANSLATOR | NOT_IMPLEMENTED / NOT_AUTHORIZED | Separately reviewed/tested mode-specific positive and explicit negative predicates and actual translation | PIT/execution/evidence remain independent; Native RUN/SUPPORTED/SELECTED/VALUE_AVAILABLE/hash never grants ELIGIBLE |
| IF04_CAPABILITY_TRANSPORT | DEFERRED_WITH_BLOCKING_GATE | Actual principal/grant/resource/action authorization, immutable resolution receipts, transport/runtime review | Opaque locator alone is no access barrier; no existing endpoint/store/service claimed |
| F3/F5/F6 | NOT_AUTHORIZED / NOT_RUN | Own method/protocol/horizon/label-maturity/run/policy/same-info/execution-price/cost/outcome/UI contracts and tasks | No experiment, training, labels, policies, metrics, returns, decision feed or backend/UI execution accepted here |
| IF07_REAL_SOURCE | DEFERRED_WITH_BLOCKING_GATE | Actual rights, publisher/time/version/availability/source admissibility and independent review | Real TWSE historical support blocked; modern bytes, synthetic pins and review history do not certify it |
| CAP_F2_FORMAL | OUT_OF_SCOPE / UNCHANGED | No new permission from this task | Formal physical/B04/Layer B/TestLease/PG17/Golden claims unchanged; protected roots never accessed |

WU04 stays diagnostic_only=True, admission_eligible=False, NOT_TRUSTED_PIT_EVIDENCE, source_authentication=NOT_ESTABLISHED, INTEGRATED_PROVISIONAL. The four SYN-A Weekly diagnostics are not an admitted App universe or F3/F5 feed; B03 midnight is not Weekly 18:00. Source content integrity, cutoff qualification and consumer release permission remain independent. RUN/SUPPORTED/SELECTED/VALUE_AVAILABLE/SYNTHETIC_GOLDEN/fixture/hash parity or ResearchRun success cannot grant ELIGIBLE. Positive and explicit negative IF-05 predicates are separate and unapproved; PIT/execution/evidence axes and exact first failure/unknown/withholding/invocation provenance remain intact.

### RT01-05. Independent review and next authorization boundary

Deliver the actual incremental RATIFY-01 deltas, approved preimage hashes, direct Owner receipt, eighteen-item ledger and final two-root preservation audit to Independent Review. Other-role consultations/appointments and independent engineering acceptance are NOT_SUPPLIED; none is fabricated or implied by Owner approval. This task does not appoint Oracle author/reviewer, freeze oracle bytes, accept canonical Codec/Replay/Eligibility Translator/F3/F5 integration, retrieve real sources, or grant Formal CAP-F2/B04/Layer B/PG17/TestLease authority.

Only after required independent review/closure and explicit separate authorization may Independent Golden Oracle Authoring planning/execution proceed, with concrete schema/parameter/source and role prerequisites checked. Codec/private binder/agent/F3/F5/F6 work and Git integration remain separate tasks. No staging, commit, push, PR, merge, CI/dependency/test/fixture/runtime change is authorized here. No new contract amendment or identity value was introduced; any such need requires a separate Contract Amendment Review.
