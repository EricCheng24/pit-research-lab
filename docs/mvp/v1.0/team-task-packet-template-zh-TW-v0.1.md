# PIT Research Lab — Team Task Packet Template（中文）

- **Document version:** v0.1
- **Recording date:** 2026-11-06
- **Recording scope:** docs-only amendment; previously accepted construction; logical freeze pending Owner/independent review; no product/engineering acceptance.
- **Amendment task:** `MVP-M0-IF-FINAL-01`; `IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`.
- **Decision input:** `MVP-M0_Interface_Decision_Record_v0.1.md`, ID `PIT-MVP-M0-IF-DEC-20261106`, SHA256 `06376f07097e618bdb99c297d1ad73df9a38dfb3cc9433637608bd23f4d2b2b5`; technical proposal for this scope, not runtime/source/Git authority.
- **Acceptance dimensions:** `M0_DOCUMENT_CONSTRUCTION_ACCEPTED` (Owner-supplied prior independent review); `M0_CONTRACT_FREEZE_PENDING_REVIEW`; `TEAM_IMPLEMENTATION_NOT_AUTHORIZED`.
- **Approved M0 base:** `b3be0c0122dac804084d5e464f7bfc07313f02aa`; branch `mvp/m0-shared-contracts`.
- **Packet provenance:** `docs/mvp/v1.0/team-task-packet-template-zh-TW-v0.1.md` from `PIT_Research_Lab_v1.0_MVP-M0_Initialization_Packet_20261106.zip`; ZIP SHA256 `43033166586a50b78d569df81b7e0db8f9412544a351814ceaba818312b0bc98`. External text is input material, not operational authorization.

> 每個工程項目請複製本模板形成獨立文件；不要把整個 CAP-F6 一次交給 Codex 實作。

## Task Identity

- Task ID：`F6-XX`（或 F2/F3/F4/F5）
- Responsible role：`TBD_BY_LEAD`
- Named assignee / named reviewer：`TBD_BY_LEAD` / `TBD_BY_LEAD`（code task 前必填真實姓名，不可用角色代替）
- Branch / Base SHA / Worktree：
- Dependency Contract Version：
- 預期交付日期／Checkpoint：
- Status：`PROPOSED`（可用值：`PROPOSED / APPROVED_FOR_IMPLEMENTATION / IN_REVIEW / ACCEPTED / BLOCKED`；本模板不授權升格）
- M0 construction：`M0_DOCUMENT_CONSTRUCTION_ACCEPTED`（Owner 提供的先前獨立審查結果）
- M0 contract：`M0_CONTRACT_FREEZE_PENDING_REVIEW`；team code：`TEAM_IMPLEMENTATION_NOT_AUTHORIZED`

## 1. Goal（可觀察且有邊界的成果）

一句話描述使用者或測試可以看到的行為。

## 2. Inputs & References

精確 repo paths、DTO/schema/fixtures、上游 Approved/Provisional 標記、來源 SHA／版本。不能把未確認名稱當作實際存在 API。

## 3. Exact Allowlist / Forbidden Scope

- Allowed files：
- New files allowed：
- Forbidden：Protected contracts、B04 security/physical path、DB/Docker、外部 API、Secrets、unapproved Git 操作（依項目調整）。

## 4. Acceptance Tests / Negative Tests

- Positive Case：
- Negative / Unknown / Withheld / Failure Case：
- Replay / consistency requirement：
- Actual test commands and expected output：
- Note what is `NOT_RUN` or only `SIMULATED`：

## 5. Implementation Plan

限定改動、依賴、里程碑和回退方案；若需跨 Scope 停止申請 Amendment。

## 6. Review and Handoff

- Diff summary / actual modified paths：
- Exact commands / exit codes / test counts：
- Security／PIT／semantic check：
- Known risks and blocker category：
- Reviewer adjudication / next task：

## 7. AI Collaboration Prompt

使用 [team-ai-coding-agent-sop-zh-TW-v0.1.md](team-ai-coding-agent-sop-zh-TW-v0.1.md) 的七欄位提問模板，並附本 Task Packet；Prompt 要明確要求「不能自行宣告驗收／不能擅自改跨模組契約」。

## 8. M0 Contract / Permission Record（每項任務必填）

- IF-01..07 對本任務的 disposition、responsible role、blocking milestone/deadline、no-go default 與 Owner／independent review receipt：
- Disposition 僅用 `POLICY_DECIDED_IMPLEMENTATION_PENDING / DEFERRED_WITH_BLOCKING_GATE / UNKNOWN_REQUIRES_AUTHORITY`，不等於 runtime verified 或 source accepted：
- Interface classification：`VERIFIED_EXISTING / NEW_M0_PROPOSAL / UNKNOWN/REQUIRES_OWNER_DECISION`；來源 path、symbol、SHA、靜態／實際執行證據：
- Fixture provenance：ID／version／作者／生成方式／digest 規則／`FIXTURE_ONLY`；實際研究未執行時保留 `NOT_RUN`：
- 對 `SYNTHETIC_GOLDEN / REAL_TWSE_PILOT / UNRESOLVED / WITHHELD / NOT_RUN` 的展示／權威界線：
- 本次明確允許的 code／dependency install／network／Git／physical actions（無則寫 NONE；不以範本授權）：
- 首個超出範圍的 blocker 與升級對象：

依 [Shared Contract](shared-interface-contract-v0.1.md) 與 [M0 initial tasks](m0-acceptance-matrix-v0.1.md#initial-team-task-register-proposed-not-executed) 填寫。本範本尚未核准任何任務；M0 不等於最終工程驗收。

## 9. Before planning / code / identity / source gates

- Planning task（F2-DEMO-PLAN / F3-L1-PLAN / F4-PILOT-PLAN / F6-00 / F5-PLAN）：Owner 接受 M0 logical contracts 後另行指派；本次沒有派工。
- Code task：真實 named assignee/reviewer（目前 `TBD_BY_LEAD`）、精確 path allowlist、approved base/ref/worktree、獨立 task authorization、dependency/network/Git/physical 權限與預定 test commands 缺一即不得開始。
- IF-01/02：八個 evaluator 僅為 Codex 02 靜態候選，runtime/input review 另案；七個 App DTO + logical ResearchClient 與 `mvp-app-v0.1` schema family 仍為 NEW_M0_PROPOSAL，不修改 Domain/DB。
- IF-03：canonical bytes/digest domain/precision/replay oracle target 2026-12-15，before M1 identity/replay acceptance；不得拿 B03 hash 當 App hash。
- IF-04：transport planning target 2026-12-20，before F6-08/actual integration；本模板不選 framework。
- IF-05：分開 pit_status / execution_status / evidence_class；未映射 UNRESOLVED、較強原生 WITHHELD 保留；positive/negative predicates 均需另審與後續 tests，typed errors 不等於 INELIGIBLE。
- IF-06：F6-00 路徑提案、F6-02 fixture task 另審；FIXTURE_ONLY 不能證明 actual SUCCEEDED／synthetic verified，runner 未執行為 NOT_RUN。
- IF-07：real intake / positive historical claim 前，rights/time/version evidence 經 independent reviewer 與 Lead/Data roles 核准；target checkpoint 2027-02-28。Producer 不得自我認證；獨立 reviewer 姓名目前 TBD_BY_LEAD。
- Test evidence：對照 [十項 IF-05 textual cases](shared-interface-contract-v0.1.md#if-05-adversarial-textual-contract-cases) 填入將來的正負案例與 exact commands。文件覆蓋只能稱 TEXT_SPEC_PASS；runtime/source/CI/pytest/UI/E2E/PostgreSQL/physical tests、Source36/CTRL03 authorization、real-source intake、migration/recovery、PR/hosted CI 本輪全部 NOT_RUN。

填寫 proposed qualification_trace_ref 或等價 reference 的資料保留策略：native state/type、reason/unknown cause、typed first failure、cutoff/source/version/manifest/lineage/flags/evidence basis。identity 改變時禁止沿用舊 digest/lineage；Evaluation labels 不流入 decision-time observations。以上均為審查欄位，不是可執行 schema 或授權。

Related M0 records: [Rebaseline](academic-mvp-rebaseline-v0.1.md), [Shared contract](shared-interface-contract-v0.1.md), [Acceptance matrix](m0-acceptance-matrix-v0.1.md).
