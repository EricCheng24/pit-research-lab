# PIT Research Lab v1.0 — Academic MVP Rebaseline v0.1

- **Document version:** v0.1
- **Recording date:** 2026-11-06
- **Recording scope:** docs-only amendment; previously accepted construction; logical freeze pending Owner/independent review; no product/engineering acceptance.
- **Amendment task:** `MVP-M0-IF-FINAL-01`; `IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`.
- **Decision input:** `MVP-M0_Interface_Decision_Record_v0.1.md`, ID `PIT-MVP-M0-IF-DEC-20261106`, SHA256 `06376f07097e618bdb99c297d1ad73df9a38dfb3cc9433637608bd23f4d2b2b5`; technical proposal for this scope, not runtime/source/Git authority.
- **Acceptance dimensions:** `M0_DOCUMENT_CONSTRUCTION_ACCEPTED` (Owner-supplied prior independent review); `M0_CONTRACT_FREEZE_PENDING_REVIEW`; `TEAM_IMPLEMENTATION_NOT_AUTHORIZED`.
- **Approved M0 base:** `b3be0c0122dac804084d5e464f7bfc07313f02aa`; branch `mvp/m0-shared-contracts`.
- **Packet provenance:** `docs/mvp/v1.0/academic-mvp-rebaseline-v0.1.md` from `PIT_Research_Lab_v1.0_MVP-M0_Initialization_Packet_20261106.zip`; ZIP SHA256 `43033166586a50b78d569df81b7e0db8f9412544a351814ceaba818312b0bc98`. External text is input material, not operational authorization.

- **Document ID:** PIT-RBL-2026-11-06
- **Status:** OWNER-APPROVED STRATEGY / CONSTRUCTION PREVIOUSLY ACCEPTED / LOGICAL CONTRACT FREEZE PENDING REVIEW
- **Owner approval:** 2026-11-06（對話中的明確核准；非 Git 簽章或 Formal Engineering Acceptance）
- **M0 Gate:** 2026-11-20（目標，非已通過）
- **MVP Feature Freeze:** 2027-04-30
- **School Demo:** 2027-05～06
- **Policy:** Capstone-first / Vertical-Slice-Driven / Source-and-PIT integrity must remain true

## 1. Scope and two release identities（RBL-01）

PIT Research Lab v1.0 的學術目標：在 Historical Decision Time 下，只使用符合資格的 Point-in-Time 資訊，提出 Hypothesis、執行可重現實驗，公平比較 Sequential Decision Policies，並展示決策、評估、來源、限制和 Replay。

**Academic MVP Release** 是可啟動、可操作、真正執行至少一條完整研究路徑的學術原型。**CAP-F2 Formal Engineering Release** 保留原訂 WU-00～08、PostgreSQL、Snapshot/Finalization/Recovery、Golden 110/154 和各項獨立驗收。兩種 Release 的 PASS 與 Evidence 不得相互冒用。

## 2. Non-negotiable v1.0 functions（RBL-02）

| Domain | 必備能力 | 非必備／遞延 |
|---|---|---|
| F2 PIT | Deterministic Dataset/Snapshot、Source/Version/Time Qualification、As-of Selection、Unknown/Withheld、Replay | 完整 B04 Physical Matrix 與進階 PostgreSQL Recovery |
| F3 Research | Hypothesis、Experiment Protocol、至少一項真實執行的 Statistical Method、ResearchRun、EvidenceBundle | 自動生成假說、多方法推薦 |
| F4 TWSE | 有限 Historical Monthly Revenue + Price/Return、品質檢查與來源資料 | 全市場 Data Warehouse、完整財務因子庫 |
| F5 Sequential | Benchmark + 兩種可比較 Policy、相同合格資訊、Action Trace、Costs/Risk/Performance | 完整四類 Agents、RL、Portfolio Optimization |
| F6 UI | Research Input → Execute → Result → Evidence/Replay → Decision Comparison | Multi-user、Production Auth、複雜 Cloud Deployment |

每個必備功能都應有 runnable path；UI mock 僅限初期開發，不構成 MVP Acceptance。

## 3. Primary research case（RBL-03）

主題：**歷史決策時點上，僅用當時已取得資格的 TWSE 月營收資訊建立特徵，比較不同決策規則的行為及結果。**

候選資料尺寸：5～10 家公司、24～36 個月月營收、對應歷史價格；具體範圍依來源和合法使用/時間證據縮減。Benchmark + Rule-based A + Feature-based B；Benchmark 是參照組，A/B 為最低兩個 Policy。未來價格與 Labels 僅供事後評估，不得流入當期觀測或訓練。

## 4. Dual modes and evidence discipline（RBL-04）

- **Mode S — Deterministic Synthetic Demo:** pinned inputs、明確 Temporal Oracle、完整 end-to-end/negative/replay 測試；主展示保底路徑。
- **Mode R — Bounded Real-TWSE Pilot:** 小範圍真實 Source Bytes、語意與可得時間證據；其研究 Claim 必須逐項對應證據。缺乏 Historical Publication/Content-Version Binding 的資料標為 `UNRESOLVED` 或 `WITHHELD`，不可推定已知。

Mode S PASS 不代表歷史金融資料的 PIT 認證；Mode R 取得現代資料，也不代表已於歷史 Cutoff 可得。

## 5. F2-Demo runtime separation（RBL-05）

以受控唯讀、Manifest-pinned local dataset 做 MVP Data Adapter：

`Versioned Data → Hash/Manifest Verify → PIT Eligibility → Feature Projection → ResearchRun → Evidence`。

優先重用可安全獨立執行的既有 Pure Domain Functions。**禁止** import/activate/bypass B04 Physical Consumers、CTRL03、Layer B、未核准的 PostgreSQL/TestLease；不改寫 Core24、Observation30、P4M33、Source36 historical seals、Frozen Golden、舊版驗收資料。任何新正式 API 行為與先前 Source 身分不相符時，另列版本與審核，不回頭竄改 baseline。

## 6. Shared application contract（RBL-06）

`DatasetManifest`、`SnapshotReference`、`ExperimentSpec`、`ResearchRun`、`EvidenceBundle`、`DecisionTrace`、`EvaluationResult` 是**建議的 Application-level DTO / logical contracts**；不預設與既有 `ApprovedDataSnapshot` 等 Domain 名稱直接一對一。精確欄位、狀態與 Owner 在 [shared-interface-contract-v0.1.md](shared-interface-contract-v0.1.md) 中列出，於 M0 review 後才可 freeze。

F2 擁有 PIT 與資料權威；F3 擁有 Research lifecycle；F5 擁有 Decision/Evaluation；F6 只做 input/UI/rendering。Frontend 不得代為認證 PIT、回填未知資料或憑空計算權威報酬。

## 7. CAP-F2 preservation（RBL-07）

已知截至 2026-11-06：CTRL06 SR01 source review 已接受；Controller2 partial source/offline 部分可供限定延續；CTRL03 Official Late-binding ABI P1 OPEN；真實 Project Collection／Physical TestLease／PG17 未通過；E0-G5=NO_GO；P4-M Layer B=PERMANENT_DENY；B04 與 WU-04～06、Golden110/154 仍非正式完成。受影響操作依原 safety gate 管制。MVP 不可把 Blocked Gate 改成 PASS。

## 8. Four workstreams（RBL-08）

| Team role | Primary responsibilities | First verifiable artifact |
|---|---|---|
| Technical Lead | F2-Demo、Interfaces、PIT correctness、F5 design、integration adjudication | pinned Synthetic PIT projection |
| Member A | F4 bounded TWSE Data/Quality | dataset manifest + quality evidence |
| Member B | F3 Research L1 | actual synthetic Hypothesis → Experiment → Evidence |
| Member C | F6 Application/UI | navigable UI + contract-based mock client |

模組的個別 feature branch 以 **M0 reviewed common base** 分支。Shared DTO/migration/security 文件由 Tech Lead review。每個人不能在同一個 Dirty B04 Worktree 上執行自己的 Codex。

## 9. Milestone dates（RBL-09）

| Milestone | Target | Required proof |
|---|---|---|
| M0 | 2026-11-20 | Scope、Shared DTO、worktrees/owners、review protocol 已固定 |
| M1 | 2026-12-31 | Synthetic F2 → F3 → Evidence runnable |
| M2 | 2027-01-31 | 真正 UI → Backend → ResearchRun → Evidence |
| M3 | 2027-02-28 | Bounded TWSE source/semantics/uncertainty demonstrated |
| M4 | 2027-03-31 | Benchmark + 2 Policies，same eligible info，cost/risk/trace |
| M5-RC | 2027-04-15 | Demo candidate；無新功能進入 |
| M5-F | 2027-04-30 | Feature freeze；只允許 blocking fixes |
| M6 | 2027-05～06 | School demo、evidence、handoff |

## 10. Academic MVP Acceptance Criteria（RBL-10）

- **AC-01 Runnable:** clean-machine setup / backend / UI startup reproducible，無未授權 physical dependency。
- **AC-02 Real experiment:** 至少一項真正執行的統計方法，含 protocol、metric、diagnostic。
- **AC-03 Synthetic PIT correctness:** late/publication/version conflict 欠資格資料不可進入 decisions，Unknown 仍 Unknown。
- **AC-04 Bounded real source:** 至少一組真實 TWSE 資料可顯示來源、證據、限制；未經證明的 Historical PIT 不可認證。
- **AC-05 Sequential:** Benchmark + 兩個 Policies、同一 eligible info、decision traces、cost/risk/performance。
- **AC-06 Reproducibility:** 同 manifest/protocol/code/seed 重跑決定性內容 hash 一致；不同 Run ID 不得污染 deterministic hash。
- **AC-07 Negative paths:** late revision、missing/conflict、unqualified、illegal cutoff、runtime failure 均拒絕誤升格。
- **AC-08 Handoff:** fixtures、version/commands、CI、demo script、limitations 和 owner notes 完成。

**原 Golden 110/154 仍屬 CAP-F2 Formal Engineering Acceptance，Academic MVP 不以其他 test count 取代。**

## 11. Stop-building / scope reduction（RBL-11）

落後時先減 UI polish，後減研究 universe/optional features，再減多餘 ML/Policies，最後遞延非必備 infrastructure；不可減除 PIT、source identity、same information set、evidence label、安全 gate。2027-02-28 如實際資料仍難整合，Synthetic 是主線而 Real Viewer 誠實顯示限制；2027-03-31 若 sequential 未完成，全面停止 stretch。

## 12. Authorization（RBL-12）

Owner 已核准 Academic MVP 策略，**尚未自動授權**：原安全 baseline 變更、Docker/PG、TestLease、real source retrieval、DB migration/reset、Protected branch 操作、commit/push/merge、正式 release acceptance。這些操作依另行授權、受限 scope 與獨立審查。

**M0 Current State:** `OWNER_APPROVED_STRATEGY / M0_DOCUMENT_CONSTRUCTION_ACCEPTED / M0_CONTRACT_FREEZE_PENDING_REVIEW / TEAM_IMPLEMENTATION_NOT_AUTHORIZED`。Construction acceptance 依 Owner 本次提供的獨立審查結果；本輪政策 amendment 仍待獨立 review，不宣稱 MVP 或 final contract freeze 已完成。

## 13. Repository recording and evidence limits — 2026-11-06

RBL-01..12 and AC-01..08 above preserve the supplied Owner-approved strategy. Prior strategy approval and CAP-F2 gate/Source36/Controller statuses are supplied historical context, not independently reaccepted by this task. The current Owner explicitly approved base `b3be0c0122dac804084d5e464f7bfc07313f02aa` for the isolated M0 worktree; that base approval does not accept any dirty B04 content or close formal engineering gates.

The [source compatibility record](shared-interface-contract-v0.1.md#repository-compatibility-record--2026-11-06-static-only) identifies existing bounded domain definitions and all unimplemented application DTOs. No material redefinition of existing domain/PIT semantics is proposed; translators remain pending. Priority is M0 contract review, then separately scoped F2/F3 synthetic work and F6 planning, followed by a real backend bridge, bounded real-source work and sequential comparison at the dates above. This recording grants no team code, install, network, physical or release authority.

## 14. Two release tracks and current review boundary

RBL-01..12、AC-01..08 與原 milestone dates 均保留。Academic MVP logical contract 的後續 Owner acceptance 不等於 Formal CAP-F2 Engineering Acceptance，也不能取代 Frozen Golden 110/154。IF-05 的三軸 fail-closed 政策在 [Shared Contract](shared-interface-contract-v0.1.md#if-05-policy--three-independent-axes-and-fail-closed-mapping) 明載供獨立 review；七個 App DTO、logical ResearchClient 與 proposed schema family 仍為 NEW_M0_PROPOSAL，八個 F2 evaluator 只是 Codex 02 靜態候選，runtime/input review 未執行。

M0 logical freeze 不要求現在實作 canonical hashes、選 transport 或取得 real-source certification；[IF register](shared-interface-contract-v0.1.md#if-disposition-register--proposed-for-independent-review) 明定後續硬閘門：IF-03 target 2026-12-15 before M1 identity/replay acceptance、IF-04 target 2026-12-20 before F6-08、IF-07 target checkpoint 2027-02-28 且 intake/claim 前需獨立 authority。M0 target 2026-11-20 與 academic feature freeze 2027-04-30 不變。

Owner 接受 M0 logical contracts 後僅可另行派發 planning，named assignee/reviewer 仍為 TBD_BY_LEAD；本任務不授權 code、dependency、real sources 或 Git。B04/Source36/Controller2 與 formal gates 不變：CTRL03 P1_OPEN / NO_PHYSICAL_ADMISSION；PostgreSQL NO_GO；PG17 僅為 supplied report 的 REPORTED_STOPPED / CONTENT_UNKNOWN / RETAIN，未查詢實體資源。B04 untracked source 不在 common base，不能被納入 App。Runtime/physical/source-admission 驗證一律 NOT_RUN。

Related M0 records: [Rebaseline](academic-mvp-rebaseline-v0.1.md), [Shared contract](shared-interface-contract-v0.1.md), [Acceptance matrix](m0-acceptance-matrix-v0.1.md).
