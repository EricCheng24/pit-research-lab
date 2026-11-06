# CAP-F6 — Application / UI + Integrated Demo — Initialization Charter v0.1

- **Document version:** v0.1
- **Recording date:** 2026-11-06
- **Recording scope:** docs-only amendment; previously accepted construction; logical freeze pending Owner/independent review; no product/engineering acceptance.
- **Amendment task:** `MVP-M0-IF-FINAL-01`; `IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`.
- **Decision input:** `MVP-M0_Interface_Decision_Record_v0.1.md`, ID `PIT-MVP-M0-IF-DEC-20261106`, SHA256 `06376f07097e618bdb99c297d1ad73df9a38dfb3cc9433637608bd23f4d2b2b5`; technical proposal for this scope, not runtime/source/Git authority.
- **Acceptance dimensions:** `M0_DOCUMENT_CONSTRUCTION_ACCEPTED` (Owner-supplied prior independent review); `M0_CONTRACT_FREEZE_PENDING_REVIEW`; `TEAM_IMPLEMENTATION_NOT_AUTHORIZED`.
- **Approved M0 base:** `b3be0c0122dac804084d5e464f7bfc07313f02aa`; branch `mvp/m0-shared-contracts`.
- **Packet provenance:** `docs/mvp/v1.0/f6-application-ui-initialization-v0.1.md` from `PIT_Research_Lab_v1.0_MVP-M0_Initialization_Packet_20261106.zip`; ZIP SHA256 `43033166586a50b78d569df81b7e0db8f9412544a351814ceaba818312b0bc98`. External text is input material, not operational authorization.

**Status:** SCOPE_PROPOSED / M0_SHARED_CONTRACT_REVIEW_PENDING. **Owner role:** UI Member C; named assignee/reviewer `TBD_BY_LEAD` (project lead reviews interfaces, security and acceptance). **Target:** First actual UI-backend integration by 2027-01-31; feature freeze by 2027-04-30.

## A. Purpose / non-goals

使用者在同一個介面中建立／選擇 Hypothesis、設定 Experiment、查看 Data Snapshot/Temporal Status、送出研究、檢視 Evidence、觀察決策策略與比較結果、完成可重播展示。F6 是 Presentation / Application Orchestration，不是 Authority Provider 或研究計算核心。

**不做：** 自行判定 PIT 真偽、直接 SQL、重新計算 authoritative financial/portfolio metrics、改寫 Evidence、任意解除 `WITHHELD/UNRESOLVED`、接入 B04 Physical Harness、複雜多租戶/登入/雲端部署、AI Agent 自動研究平台。

## B. User journey & screens

最小展示路徑（先 Fixture Mode、後 Backend Mode）：

1. **Dataset/Snapshot chooser**：Mode S vs Mode R，Source refs、manifest digest、decision cutoff、eligibility/conflict/unknown 明確顯示。
2. **Research Setup**：Hypothesis、Method、Protocol inputs、seed、evaluation policy；由契約檢查必填欄位。
3. **Run detail**：執行 `NOT_RUN/PENDING/RUNNING/SUCCEEDED/FAILED/BLOCKED`、Run ID、error code、retry policy（不自動重試不可重複操作）。
4. **Evidence & Provenance**：Metrics、Diagnostics、Lineage、Source IDs、content/version hash、limitations、資料取得與歷史可得性區別。
5. **Decision Comparison**：Benchmark/A/B 的績效、成本、風險和 Action Trace；只有後端提供的合格結果能稱權威。
6. **Replay/Export viewer**：固定 Manifest / Spec / Code Ref / Seed，決定性結果核對；匯出受約束、不得外洩 protected raw data。

## C. Engineering nodes and bounded Done criteria

| Node | Phase / Dependency | Work item | Deliverable / Definition of Done |
|---|---|---|---|
| **F6-00** | After Owner accepts M0 logical contracts; separate planning assignment | Scope and Contract mapping | UI information architecture、screen inventory、state matrix、API client types、open decisions；Lead review。**No app code yet** |
| **F6-01** | M0/M1 | UI project scaffold proposal | Read existing repo/build tooling; submit smallest UI stack choice, dependency/licence/offline build plan; scaffold only after separate scoped approval |
| **F6-02** | M1; F6-00 IF-06 path approval + separate fixture-code authorization | FixtureResearchClient & states | Deterministic synthetic fixtures for success, unresolved, withheld, late revision, blocked, fail; explicit MOCK/FIXTURE labeling; contract and rendering tests |
| **F6-03** | M1 | Research Setup screen | Dataset/cutoff, hypothesis, method, seed, protocol; invalid input refused locally, backend remains final authority |
| **F6-04** | M1/M2 | Research Run workflow | Submit, loading, success/failure, blocked/missing evidence views; no false success on timeout, client receives mock vs real provenance |
| **F6-05** | M2 | Evidence/Provenance viewer | Source/version/availability/limitations + metrics/diagnostics, unknown not collapsed to false, underlying refs visible |
| **F6-06** | M3/M4 | Evaluation and Decision Trace | Benchmark+A+B comparison; common snapshot identity; backend metrics only, assumptions/period/missing values labeled |
| **F6-07** | M3/M4 | Replay and integrity viewer | Manifest/protocol/code ref/seed; result digest comparison, mismatch visible, reproducibility is server-validated not frontend-inferred |
| **F6-08** | M2 onwards; IF-04 transport decision target 2026-12-20 before actual integration | BackendResearchClient integration | Replace same interface implementation; schema and error mapping tests; no F2 security bypass, real API only after F3 signoff |
| **F6-09** | M5 | Academic demo hardening | One-command local startup where feasible, no-network fallback, golden synthetic demo, e2e smoke, UI errors/accessibility, README / demo script |

**Only after Owner accepts M0 logical contracts may F6-00 be separately assigned for documentation/planning and fixture/spec proposals**. F6-01 scaffold/package installation and F6-02 fixture code each require separate task-level authorization with exact named assignee/reviewer, path ownership, dependency/tool approval and checks; none is granted here. Avoid preemptively creating a frontend app under unknown directories.

## D. Acceptance matrix (per UI state)

| State | Correct behavior | Forbidden behavior |
|---|---|---|
| `ELIGIBLE` | only display a separately reviewed/tested mode-specific rule with source/time/version/rights/manifest evidence and qualification trace | infer eligibility from SUPPORTED/SELECTED, run success, hash or UI |
| `INELIGIBLE` | show explicit approved negative predicate and exact native reason; keep separate from execution errors | blanket conversion from NOT_ADMISSIBLE / NO_QUALIFIED_CLAIM / failure |
| `UNRESOLVED` | show evidence gap and no trusted conclusion | auto-fill from later data |
| `WITHHELD` | clearly mark output withheld and reason/category | convert to empty metric or successful result |
| `NOT_RUN` | no metrics/result, can show protocol | display fixture metrics as actual experiment |
| `RUNNING` | progress indicator; no final claim | show `SUCCEEDED` before backend response |
| `FAILED/BLOCKED` | sanitized error, source reference and limits | raw secrets/traceback in UI |
| `SUCCEEDED` | show actual execution evidence independently of PIT; UNRESOLVED snapshot stays unresolved | infer eligibility or Historical PIT acceptance from success |
| `FIXTURE_ONLY` | persistent simulated-scenario label; actual runner remains NOT_RUN until executed | claim actual SUCCEEDED or SYNTHETIC_VERIFIED_IN_SCOPE from mock payload |
| `REAL_SOURCE_OBSERVED` | verified observation evidence and separate historical time/version/rights limits | promote observed bytes into historical eligibility/support |
| `REAL_TWSE_PILOT` | observed vs historical availability distinguished | claim true PIT without supporting evidence |
| `SYNTHETIC_GOLDEN` | explicit simulated/synthetic label | present sample securities or returns as empirical result |

## E. Test strategy

M0: all contract fixtures described, UI state/negative acceptance scenarios enumerated. M1: unit component tests + mock client contract, snapshots/test data deterministic. M2: real F3 BackendResearchClient contract test, Browser E2E for user journey, failure and blocked. M4: no-leak and no-reclassification tests for F5 decision output. M5: from-clean-checkout install/start/playback script, network-offline path, fixed dataset and UI capture, 2nd-machine run if possible.

Future UI code must stay outside original B04 package/Harness and use separately implemented/reviewed shared DTOs and application API; current DTOs/ResearchClient are NEW_M0_PROPOSAL, not executable interfaces. No tests may require real PostgreSQL or unapproved data access. Do not increase scope to auth, orchestration, production CI or cloud prematurely.

## F. Suggested per-task handoff packet

Every F6-XX ticket: goal, dependency version, file allowlist, examples/fixtures, exact acceptance tests, demo screen, no-go scope, reviewer, review deadline, PR status. Use [team-task-packet-template-zh-TW-v0.1.md](team-task-packet-template-zh-TW-v0.1.md) and [team-ai-coding-agent-sop-zh-TW-v0.1.md](team-ai-coding-agent-sop-zh-TW-v0.1.md).

## G. Proposed first planning task for Member C (M0/F6-00)

**Conditional task, named assignee/reviewer `TBD_BY_LEAD`:** After Owner accepts M0 logical contracts and separately assigns planning, investigate the reviewed Shared Interface and existing repo frontend/layout; propose screen inventory and state matrix; prepare `FixtureResearchClient` contract cases and proposed tech stack *without implementing it*. Request owner review before any scaffold or dependency installation. Deliver `F6-00 Planning Report`, six-screen wireframe descriptions, blocked/unknown states matrix, project path proposal and F6-01 requirements. No B04 source edits, no package manager install, no Git write except separately authorized documentation scope.

## H. Source-aware planning boundaries and provenance

The retained Codex 02 [historical static compatibility record](shared-interface-contract-v0.1.md#repository-compatibility-record--2026-11-06-static-only) reported no matching DTO/client definitions; no new source/runtime audit is performed here. No existing frontend directory, package manager choice or backend transport was established. F6-00 proposes paths and state/spec matrices only, after Owner accepts M0 logical contracts and assigns that planning task; F6-01 requires its own approval before app creation or `npm install`. This document authorizes no code or installation.

Fixture cases are authored specifications, not executed research or formal Golden fixtures. Record origin, version, digest rules and `FIXTURE_ONLY` as required by the shared contract. A fixture may illustrate `SUCCEEDED`, but actual research remains `NOT_RUN` without backend execution. Add explicit `INELIGIBLE`, loading, empty dataset, unavailable evidence and transport timeout/error scenarios to F6-00; do not substitute empty values for withheld or unresolved evidence. Display raw domain reasons and trust limitations through an approved translator. IF-05 fail-closed policy is now documented for independent review; translator implementation and exact rules/tests remain separately blocked. B03 diagnostic `WITHHELD` cannot become an eligible application snapshot. All UI/contract/E2E tests in this charter are planned and `NOT_RUN` here.

## I. Three-axis rendering, trace and future client gates

Follow the [IF-05 policy and ten textual cases](shared-interface-contract-v0.1.md#if-05-policy--three-independent-axes-and-fail-closed-mapping). Render `pit_status`, `execution_status`, and `evidence_class` independently, alongside `data_mode` and visible fixture provenance. `run_status` is UI wording for the existing proposed `execution_status`, not a new DTO field. Do not rename native F2 statuses or any data_mode enum. `SYNTHETIC_GOLDEN` never means formal Golden 110/154 acceptance.

Distinguish fixture demo vs actual research; PIT UNRESOLVED vs WITHHELD vs explicitly justified INELIGIBLE; run failure vs qualification failure; REAL_SOURCE_OBSERVED vs independently supported historical evidence; evaluation labels/outcome availability vs decision-time observations. Typed failures preserve first error, native reason/unknown cause/flags; never collapse them into PIT ineligibility or zero metrics. A proposed qualification_trace_ref (or equivalent evidence access) exposes cutoff/source/version/lineage and evidence basis without treating the summary status as authority. Changed cutoff/version/manifest must show mismatch and refuse stale digest/lineage reuse.

Logical ResearchClient remains NEW_M0_PROPOSAL. IF-04 concrete transport is undecided (planning target 2026-12-20, hard gate before F6-08/backend integration); IF-06 fixture directories are decided in F6-00 before separately authorized F6-02 code; IF-03 canonical/digest rules target 2026-12-15 before M1 identity/replay acceptance. Real-source intake/claims require IF-07 independent approval, not frontend inference. No fixture bytes, client implementation, code framework, dependency or UI test execution is authorized in this amendment.

Related M0 records: [Rebaseline](academic-mvp-rebaseline-v0.1.md), [Shared contract](shared-interface-contract-v0.1.md), [Acceptance matrix](m0-acceptance-matrix-v0.1.md).
