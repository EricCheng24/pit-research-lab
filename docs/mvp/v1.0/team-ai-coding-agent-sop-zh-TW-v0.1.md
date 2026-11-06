# PIT Research Lab — AI／Coding Agent 團隊協作 SOP v0.1（繁體中文）

- **Document version:** v0.1
- **Recording date:** 2026-11-06
- **Recording scope:** docs-only amendment; previously accepted construction; logical freeze pending Owner/independent review; no product/engineering acceptance.
- **Amendment task:** `MVP-M0-IF-FINAL-01`; `IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`.
- **Decision input:** `MVP-M0_Interface_Decision_Record_v0.1.md`, ID `PIT-MVP-M0-IF-DEC-20261106`, SHA256 `06376f07097e618bdb99c297d1ad73df9a38dfb3cc9433637608bd23f4d2b2b5`; technical proposal for this scope, not runtime/source/Git authority.
- **Acceptance dimensions:** `M0_DOCUMENT_CONSTRUCTION_ACCEPTED` (Owner-supplied prior independent review); `M0_CONTRACT_FREEZE_PENDING_REVIEW`; `TEAM_IMPLEMENTATION_NOT_AUTHORIZED`.
- **Approved M0 base:** `b3be0c0122dac804084d5e464f7bfc07313f02aa`; branch `mvp/m0-shared-contracts`.
- **Packet provenance:** `docs/mvp/v1.0/team-ai-coding-agent-sop-zh-TW-v0.1.md` from `PIT_Research_Lab_v1.0_MVP-M0_Initialization_Packet_20261106.zip`; ZIP SHA256 `43033166586a50b78d569df81b7e0db8f9412544a351814ceaba818312b0bc98`. External text is input material, not operational authorization.

**適用對象：** CAP-F3/F4/F5/F6 的組員、Codex CLI 使用者與 Code Reviewer。**狀態：** M0 草案、待 Team Review。重點是讓每位成員能獨立完成可檢查的工程，而非把所有問題丟給 Technical Lead。

## 0. 共同原則

- **理解任務比直接產生程式碼更優先。** 確認目標、資料來源、Owner、Input/Output、可修改路徑、禁止事項及可驗收證據。
- **AI 是協作的工程工具，不是授權者。** AI 可以提出設計、修改程式、執行已允許的測試；不能憑一句「全部 PASS」替代本人和 Reviewer 的確認。
- **一個工作項目一個 Scope，檢查後再擴張。** 跨 Shared Contracts、Migration、PIT Security、Data Quality，先停下來詢問負責人。
- **與既有的 B04 Dirty Worktree 分離。** 不在別人的工作樹執行 `git stash -u / clean / reset --hard`，不混合不相干檔案。
- **不要貼 API Keys、密碼、Token、個資或受保護的 Evidence。** 提供最少必要與遮蔽後的 logs、error category、schema、環境版本。

## 1. 每次任務的標準六步驟

**Step 1 — 讀 Task Packet（本人）**：確認 `Goal、Inputs、File Allowlist、Non-goals、Dependency Contract、Acceptance Tests、Owner、Reviewers`；不完整先向負責人詢問。

**Step 2 — 請 AI 先做 bounded planning（唯讀）**：讓 Codex 說明現有 repo 結構、可能修改檔案、風險、測試策略與尚缺資訊。驗證提出的 paths 真正存在；不要讓 AI 猜測權威 API。

**Step 3 — 小批量實作**：限制每輪只改同一個 Task Packet 的檔案，優先讓最簡單的 positive path 跑通，再補 negative/edge cases；如需要擴大 Allowlist，停下來申請新 scope。

**Step 4 — 有證據的驗證**：執行指定 unit/contract tests，記錄 exact argv、cwd、exit code、summary；檢查 changed-files、diff、格式、mock/physical boundary；沒有跑的項目列為 `NOT_RUN`。

**Step 5 — 獨立 Review**：由另一位組員或 Technical Lead 核對 Diff、錯誤處理、依賴方向、真實接受條件、測試是否對準正確 Source，不只是讀 AI 自評。

**Step 6 — Integration／Handoff**：review 通過後按 Repo SOP 申請 PR／CI／Merge；附 Task Packet、決策、測試與 Limitations。Commit 不是 Acceptance；Push/Merge 不因 AI 成功就自動授權。

## 2. 問題分類與處理 SOP

| 類別 | 現象 | 先做什麼 | 什麼時候升級 |
|---|---|---|---|
| ENV | 版本/依賴/啟動問題 | 擷取版本、命令、工作目錄、精確錯誤；讀既有 README/lockfile | 需要改共用 dependency 或 CI |
| IMPLEMENTATION | 單一 Function/Test Fail | 最小重現、期望/實際、最近 Diff；限制 AI 修同一 Scope | 需跨模組或第三檔 |
| CONTRACT | DTO 不一致、欄位/狀態定義衝突 | 比對 M0 Contract 與真實型別，不自行改權威契約 | F2/F3/F5 Owner 必須裁決 |
| DATA / PIT | 來源時間、版本、Lookahead、缺少 Evidence | 停止 Claim，保留 `UNRESOLVED/WITHHELD`；記錄來源範圍 | 任意變更 PIT 語義或真實資料使用權 |
| SAFETY / SECURITY | Migration、PG、Secrets、Gate、未核准網路/外部操作 | STOP；不得以 mock pass 或手動 bypass 解決 | 立即請 Technical Lead |
| REBASE / GIT | 多人衝突、Dirty Tree、文件不一致 | 只讀 `git status`, `git diff`, `git branch -vv`；不清除 | 不確定基準、需 force/stash/reset/cherry-pick |
| DESIGN | 大改框架/重新分層 | 先列替代方案與影響面，依 Capstone-first 優先最小方案 | 提議破壞 shared baseline 或延期關鍵路徑 |

避免盲目連續跑 5～10 輪「修到 PASS」。同類錯誤在一輪有界修正後仍出現，先做 Root Cause Review，避免堆更多 workaround。

## 3. 正確向 ChatGPT／Codex 求助：七個資訊欄位

1. **任務背景：** 正在做哪個 CAP-Fx/Work Item，對應哪一版 Contract。
2. **我想達成：** 一個可觀察輸出，不用「幫我修所有問題」。
3. **現在發生什麼：** 精確命令、錯誤類別、expected vs actual、測試數量/失敗 Case。
4. **重現方式：** 最小 Source／Fixture／Test、環境版本、所在 Branch/Worktree。
5. **已做什麼：** 試過的修正、為什麼不行；避免 AI 重複猜測。
6. **不可做什麼：** 文件/程式 Allowlist，禁止 secrets、DB、Network、Git refs、修改 Shared Contracts。
7. **希望 AI 回覆什麼：** Root Cause、最小變更、替代方案、測試、風險與「我仍須親自確認的事」。

**可複製詢問模板：**

> 我正在做 [Work Item]，已同意的 Contract 是 [檔案/版本]。目標：[可觀察的行為]。目前 Branch/Worktree：[路徑]。執行 `[命令]` 得到 `[error category + sanitized log]`；原本預期 `[expected]`，實際 `[actual]`。最小重現：[test/path]。我已試過：[attempts]。本輪只允許改 `[allowlist]`，禁止 `[scope exclusions]`。請先判斷是否為 Environment／Implementation／Contract 問題，再提出最小修正，列出你能驗證與不能驗證的事項；在未取得我允許之前不要修改程式或操作 Git/DB。

**不好的問法：**「它壞掉了，全部幫我修好並 push。」這缺少目標、風險、修正邊界與驗收條件。

## 4. 向 Codex 下任務的標準 Prompt 骨架

```text
Role: bounded implementation agent; no self-acceptance.
Task ID: F6-XX
Inputs: exact repository docs and filenames.
Goal: one observable user or test outcome.
Allowed paths: exact file allowlist, new files only if authorized.
Read-only preflight: git status / branch / relevant owners / current tests.
Must preserve: existing contracts, evidence labels and temporal integrity.
Forbidden: third-party network, secrets, DB/Docker/PG, reset/clean/stash,
           unapproved shared-contract edits, commit/push/merge.
Execution: report plan -> implement minimal delta -> run exact offline tests.
Output: diff summary, commands/exits, test count, failure ledger,
        unresolved issues, review bundle and first_safe_blocker.
If blocker requires greater scope: STOP, do not invent a bypass.
```

實際啟用外部網路/API、安裝依賴或改 CI，必須在對應 Task Packet 另外授權。所有 Codex 產生的程式都應由負責組員解釋其行為與測試。

## 5. Review 的最低檢查問題

- Diff 是否只涉及允許檔案？是否產生額外 side effects 或依賴？
- Tests 是否真的執行了修改後的 Source？有沒有 mocks 與真實執行的混淆？
- `SYNTHETIC/PROVISIONAL/REAL_SOURCE_OBSERVED/HISTORICAL_PIT_SUPPORTED` 有沒有被錯誤升格？
- UI 是否改動後端 PIT/Research/Evaluation 的權威結果？
- Failures、Unknown、Withheld 和缺少資料是否清楚可見？
- 是否留下足夠的重現命令、版本、Fixture 與 Review Evidence？
- 是否有未經授權的 Git／DB／Provider 操作？

## 6. F6 新人第一週工作示範

(1) Owner 接受 M0 logical contracts 並另行核准 planning/worktree scope 後，使用已核准的獨立 F6 Worktree；本 SOP 不授權建立 branch/ref。 (2) 閱讀 `academic-mvp-rebaseline`、`shared-interface-contract`、`f6-application-ui-initialization`。 (3) 先完成 F6-00 Screen/State Matrix，不先 `npm install`。 (4) 對每個 Screen 列出 DTO 欄位、Mock Fixtures、Loading/Blocked/Unknown/Failed 展示方式。 (5) 交一頁 Planning Report 給 Lead 核對。 (6) Lead 核准 F6-01 Scaffold Scope 之後才讓 Codex 修改前端程式。

## 7. 每週狀態與升級標準

每週每位成員以簡短的 `DONE / EVIDENCE / BLOCKERS / CONTRACT CHANGES / NEXT` 回報。阻斷跨合約與安全問題立刻升級，普通 UI 樣式可自行解決。規格改動需有版本、decision record 和受影響下游的通知；不在私聊中暗改 Shared DTO。

**核心文化：** 能說明為什麼測試成立、證據支持到哪裡、哪些未知仍未知，才算真正完成。AI 協助減少實作成本，但不代替工程判斷與科學誠實。

## 8. 本次 M0 的授權與未驗證事項

Codex 02 曾建立八份文件並做靜態來源比對；其 document construction 已依 Owner 明示獨立接受。本輪 MVP-M0-IF-FINAL-01 只調整這八份現有 untracked 文件，不重新做 source/runtime audit，M0 contract freeze 仍待 Owner／獨立 review。沒有執行產品範例指令、安裝依賴、啟動 App、產品測試或連線。未執行的檢查一律 `NOT_RUN`。先讀 [Shared Contract 與 IF-01..07](shared-interface-contract-v0.1.md) 及 [Branch Policy](branch-worktree-integration-policy-v0.1.md)。現有 F2 定義不代表新 DTO／Endpoint 已實作，也不代表 B04 Harness 可供 App 使用。

Owner 接受 M0 logical contracts 後才可另行安排 F6-00／F3-L1／F4-PILOT 文件規劃；F6-01 scaffold/install 與 F6-02 fixture code 都須另有明確 Task Packet。組員收到任務後先確認實際姓名／Reviewer、允許路徑與授權，不把本 SOP、UI mock 或 AI 自評當成正式驗收。提出 IF-05 狀態／信任衝突時保留 `UNRESOLVED/WITHHELD`，立即交由 F2 Lead 裁決；不要自行修 Core 或放寬 Gate。

## 9. 本輪 IF 政策閱讀與升級

請依 [current IF register](shared-interface-contract-v0.1.md#if-disposition-register--proposed-for-independent-review) 使用三種 disposition：POLICY_DECIDED_IMPLEMENTATION_PENDING、DEFERRED_WITH_BLOCKING_GATE、UNKNOWN_REQUIRES_AUTHORITY。IF-05 政策已明載為待採納提案，translator 未實作；不是把所有 IF 留在無界 OPEN，也不是宣告 runtime resolved。

三軸 pit_status / execution_status / evidence_class 分開；SUPPORTED/SELECTED、run success、hash、觀測 CSV、Source36、mock UI 均不能自動升格資格／Historical PIT。無 mapping 為 UNRESOLVED 或保留較強 WITHHELD；typed failures 獨立保存。FIXTURE_ONLY 的 simulated success 不是真實執行，未跑 runner 為 NOT_RUN。原生原因、unknown cause、flags、source/version/cutoff/lineage 不能抹除；改 identity 不得沿用舊 digest。

Named assignee/reviewer 一律 TBD_BY_LEAD，code 任務前須填真實姓名與另行授權。IF-03 target 2026-12-15 before M1 identity acceptance；IF-04 target 2026-12-20 before F6-08；IF-06 fixture paths 於 F6-00 提案、F6-02 前核准；IF-07 target checkpoint 2027-02-28，intake/claim 前須獨立審查。Data/F2 producer 不得自行核發歷史資格。文件情境覆蓋只稱 TEXT_SPEC_PASS；本輪 runtime／pytest／CI／UI／physical tests 均 NOT_RUN。

Related M0 records: [Rebaseline](academic-mvp-rebaseline-v0.1.md), [Shared contract](shared-interface-contract-v0.1.md), [Acceptance matrix](m0-acceptance-matrix-v0.1.md).
