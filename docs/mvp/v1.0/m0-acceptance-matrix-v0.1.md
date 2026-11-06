# MVP-M0 Shared Contract & Parallel Workstream — Acceptance Matrix v0.1

- **Document version:** v0.1
- **Recording date:** 2026-11-06
- **Recording scope:** docs-only amendment; previously accepted construction; logical freeze pending Owner/independent review; no product/engineering acceptance.
- **Amendment task:** `MVP-M0-IF-FINAL-01`; `IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`.
- **Decision input:** `MVP-M0_Interface_Decision_Record_v0.1.md`, ID `PIT-MVP-M0-IF-DEC-20261106`, SHA256 `06376f07097e618bdb99c297d1ad73df9a38dfb3cc9433637608bd23f4d2b2b5`; technical proposal for this scope, not runtime/source/Git authority.
- **Acceptance dimensions:** `M0_DOCUMENT_CONSTRUCTION_ACCEPTED` (Owner-supplied prior independent review); `M0_CONTRACT_FREEZE_PENDING_REVIEW`; `TEAM_IMPLEMENTATION_NOT_AUTHORIZED`.
- **Approved M0 base:** `b3be0c0122dac804084d5e464f7bfc07313f02aa`; branch `mvp/m0-shared-contracts`.
- **Packet provenance:** `docs/mvp/v1.0/m0-acceptance-matrix-v0.1.md` from `PIT_Research_Lab_v1.0_MVP-M0_Initialization_Packet_20261106.zip`; ZIP SHA256 `43033166586a50b78d569df81b7e0db8f9412544a351814ceaba818312b0bc98`. External text is input material, not operational authorization.

**Owner-approved Academic MVP strategy ≠ M0 contract acceptance.** This matrix is the acceptance gate for *document and team initialization only*, not runnable product acceptance.

| Gate | Requirement | Evidence | Pass rule |
|---|---|---|---|
| M0-G01 | Dirty B04 preserved | read-only Git status before/after, staged/index, original HEAD/branch | No B04 change, no stash/reset/clean |
| M0-G02 | Separate M0 worktree with exact approved document preimages | Approved base SHA, branch/ref, eight untracked preimages, no unrelated edits or staged paths; Codex 02 clean startup is historical | No unreviewed B04 content imported; no current preimage drift |
| M0-G03 | Rebaseline accurately recorded | RBL-01..12, dates, AC-01..08, owner approval stated without forging Git approval | All present and consistent |
| M0-G04 | Shared contract boundaries defined | DTO table, ownership, status and evidence classification, null/unresolved rules | No promoted synthetic/real claims |
| M0-G05 | **DOC DESIGN READY FOR REVIEW** | Historical Codex 02 static mapping + current IF dispositions, fail-closed policy and deferred gates | Independent review may later accept design only; no runtime/source acceptance or invented API |
| M0-G06 | **ROLE OWNERSHIP READY FOR REVIEW** | Technical Lead, Member A/B/C role workstreams and gates; named assignees/reviewers `TBD_BY_LEAD` | Role/planning review only; exact names, paths and tests required before any implementation task |
| M0-G07 | F6 initialized | F6-00..09, screens, state matrix, fixture & backend integration gates | Detailed handoff for Member C |
| M0-G08 | 中文 SOP actionable | 6-step workflow, error triage, AI query template, escalation, reviewer checks | Team can use without tacit knowledge |
| M0-G09 | Only approved docs changed | `git status`, `git diff --check`, path allowlist, no binaries/secrets | No source/package/CI mutation |
| M0-G10 | Provenance & conditional handoff | Eight exact pre/post hashes, reversible documentary diffs, textual scenarios, current IF gates and independent review | `IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`; no self-freeze or team implementation permission |

## STOP / failure ledger

M0 must refuse success if: no trustworthy stable base, branch/worktree conflicts, preexisting target docs differ without review, repository instruction conflicts, any new physical action/secret exposure, unauthorized code edits, source-history reinterpretation, or unresolved status promotion rules. IF dispositions must use `POLICY_DECIDED_IMPLEMENTATION_PENDING`, `DEFERRED_WITH_BLOCKING_GATE` or `UNKNOWN_REQUIRES_AUTHORITY` with role, deadline and no-go default. Baseline/UI safety ambiguity blocks M0 freeze; deferred IF-03/04 implementation and IF-07 approval do not block logical freeze when their blocking gates are explicit and independently accepted.

## Required documentary review outputs

Outside both repositories: `MVP-M0_IF_Finalization_Implementation_Report.md`, `MVP-M0_Final_Contract_Reconciliation_Matrix.md`, `MVP-M0_Final_Document_Comparison.json`, `MVP-M0_Final_IF_Test_and_Negative_Matrix.md`, `MVP-M0_Final_Review_Evidence.zip`. Include exact pre/post registers, accurate relative diffs reconstructed forward/reverse with zero fuzz in external scratch, ten IF-05 textual cases, and Git preservation evidence. None is a product test or Git PR patch.

## Separate acceptance dimensions

- `M0_DOCUMENT_CONSTRUCTION_ACCEPTED`: Codex 02 construction was independently accepted, per Owner’s supplied review statement; this task does not reissue that acceptance.
- `M0_CONTRACT_FREEZE_PENDING_REVIEW`: the logical policy amendment is `IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`; Owner／獨立 reviewer must accept before design freeze.
- `TEAM_IMPLEMENTATION_NOT_AUTHORIZED`: no blanket readiness for team code, installs, source retrieval, Git or physical work. M0-G06 role readiness is not named-team implementation readiness.

M0-G05 may be accepted later at design level once the IF register, IF-05 and safe deferred gates are independently reviewed. IF-03 canonical implementation, IF-04 transport choice and IF-07 real-source certification are later hard gates, not prerequisites to implement in this task. M0-G06 may be accepted later at role/planning level while all named people remain `TBD_BY_LEAD`. No M0 gate is self-accepted here.

## IF disposition register — proposed for independent review

The following register matches the [Shared Contract](shared-interface-contract-v0.1.md#if-disposition-register--proposed-for-independent-review) verbatim. Disposition means documentary policy/deferment, never runtime completion or independently granted authority.

| IF | Disposition | 政策／未實作事項 | Responsible role | Blocking milestone / target | No-go default |
|---|---|---|---|---|---|
| `IF-01` | `POLICY_DECIDED_IMPLEMENTATION_PENDING` | 八個 evaluator 是 Codex 02 靜態規劃候選；實際 runtime 與 input/code-observation 建構另審，不能把 Git/disk helper 稱為 pure call。 | Technical Lead (F2) | F2-DEMO-ADAPTER 實作前；M0 規劃目標 2026-11-20 | 不啟動 adapter，不 import B04 Harness / Physical Consumer。 |
| `IF-02` | `POLICY_DECIDED_IMPLEMENTATION_PENDING` | 七個 App DTO 與 logical ResearchClient 為 NEW_M0_PROPOSAL；mvp-app-v0.1 僅提議的 application schema family，與 Domain/DB 分開；translator 必須另版別、另測。 | Technical Lead + Member B (F3 contract owner) | 首次 shared DTO 實作或依賴具體 DTO 的 F3/F6 code 前 | 只做 spec/fixture 規劃；不虛構 ApprovedDataSnapshot、既有欄位或 schema。 |
| `IF-03` | `DEFERRED_WITH_BLOCKING_GATE` | Canonical bytes、digest domain separation、timestamp/number precision、replay equivalence oracle 尚未決定。 | Technical Lead (F2) + Member B (F3) | 首次 M1 identity/replay acceptance 前；target ≤ 2026-12-15；M1 2026-12-31 | 禁止 cross-schema digest 等價宣稱；B03 diagnostic hash 不是 App hash。 |
| `IF-04` | `DEFERRED_WITH_BLOCKING_GATE` | Logical ResearchClient port 作為設計提案固定；實際 local/CLI/HTTP transport 未選，無 framework 決定。 | Member B (F3) + Member C (F6); Lead sign-off | F6-08 / actual backend integration 前；planning decision target ≤ 2026-12-20；M2 2027-01-31 | 僅 FixtureResearchClient spec/mock 規劃；不宣稱真實 endpoint 或 backend 呼叫。 |
| `IF-05` | `POLICY_DECIDED_IMPLEMENTATION_PENDING` | 本文件 IF-05 三軸與 fail-closed 規則已列為待獨立審查的政策提案；translator 未實作、未核准正向資格規則。 | Technical Lead (F2) | M0 logical freeze 前須獨立審查政策；F2-DEMO-ADAPTER 實作前另審 translator 與測試 | 未映射為 UNRESOLVED，原生 WITHHELD 保留；禁止正向自動升格。 |
| `IF-06` | `POLICY_DECIDED_IMPLEMENTATION_PENDING` | M0-* IDs、FIXTURE_ONLY、origin/version/digest/limitations 與禁止 production import test helpers 為政策提案；實際目錄延後。 | Member C (F6) + Member B (F3) | F6-00 提出路徑；F6-02 fixture code 前核准路徑、IF-03 digest 規則與獨立 task | 只有規格，沒有 fixture bytes、執行成功宣稱或 protected data copies。 |
| `IF-07` | `UNKNOWN_REQUIRES_AUTHORITY` | 政策要求 producer 不得自我認證；實際 source rights/time/version admissibility 與獨立 reviewer 任命未建立。 | Technical Lead (F2) + Member A (F4/Data) + independent reviewer | real-data intake 或 positive historical claim 前；target checkpoint ≤ 2027-02-28 | 不 retrieval / intake / admission；僅有證據時可顯示 REAL_SOURCE_OBSERVED，PIT 保留 UNRESOLVED 或原生 WITHHELD。 |

## IF-05 review obligations

Review the [three independent axes and decision table](shared-interface-contract-v0.1.md#if-05-policy--three-independent-axes-and-fail-closed-mapping) and all ten [textual cases](shared-interface-contract-v0.1.md#if-05-adversarial-textual-contract-cases). `SUPPORTED`/`SELECTED` never auto-promote; B03 withholding stays withheld; errors preserve typed failure independently of PIT; fixtures remain `FIXTURE_ONLY` with actual `NOT_RUN`; real observation never implies Historical PIT support. Positive and negative predicates require separate approval and later tests. The **PROPOSED** `qualification_trace_ref` or equivalent preserves all native evidence and identity. `TEXT_SPEC_PASS` only describes specification coverage.

Runtime/source/code/CI/pytest/UI/E2E/PostgreSQL/physical tests, Source36/CTRL03 authorization, real-source intake, migration/recovery and PR/hosted CI remain `NOT_RUN`. Source36/Controller2 history grants no app or physical permission. Current document evidence is distinct from formal CAP-F2/Golden 110/154 acceptance.

## Initial team task register (PROPOSED, not executed)

| Proposed task | Responsible role | Dependencies | First planning output | No-go gate | Named assignee / reviewer |
|---|---|---|---|---|---|
| `F2-DEMO-PLAN` | Technical Lead (F2) | M0 logical contract Owner acceptance；IF-01/02/05 policy；IF-03 identity gate | 八個 evaluator 的 reuse/input/observation plan、synthetic qualification/error map、replay spec | 不啟動 adapter；runtime/input review、positive/negative predicates 與程式任務另審。 | `TBD_BY_LEAD` / `TBD_BY_LEAD` |
| `F3-L1-PLAN` | Member B (F3); Lead reviewer role | M0 review 後另行指派；contract v0.1、F2 synthetic fixture spec | Hypothesis → Protocol → actual statistical-method proposal → Evidence slice；module paths 與 checks 計畫 | 不建立 runner/DTO code；identity acceptance 先過 IF-03，真實 bridge 先過 IF-04。 | `TBD_BY_LEAD` / `TBD_BY_LEAD` |
| `F4-PILOT-PLAN` | Member A (F4/Data); Lead reviewer role | M0 review 後另行指派；IF-07 authority model | 僅 supplied metadata 的 bounded TWSE inventory、rights、release/observation-time evidence 計畫 | 不得 retrieval/intake；獨立 reviewer 與 rights/time/version evidence 未核准前不 admission 或 historical claim。 | `TBD_BY_LEAD` / `TBD_BY_LEAD` |
| `F6-00` | Member C (F6); Lead reviewer role | Owner 接受 M0 logical contracts 後另行指派；IF-02/04/05/06 | 六個 screen、三軸 state matrix、fixture client scenarios、framework/path/options recommendation | 僅 documentation/planning；不選定 framework、不 scaffold/install；F6-01/02 各需獨立 task authorization。 | `TBD_BY_LEAD` / `TBD_BY_LEAD` |
| `F5-PLAN` | Technical Lead + Member B | M0 review 後另行指派；F2/F3 contract 與 IF-05 boundaries | Benchmark+A/B、same information set、decision/evaluation labels、cost/trace spec | 沒有 F2/F3 implemented contracts 與另行任務，不執行 policies 或產生績效結論。 | `TBD_BY_LEAD` / `TBD_BY_LEAD` |

Use the [task template](team-task-packet-template-zh-TW-v0.1.md). Planning may be separately assigned after Owner accepts the M0 logical contracts; this task assigns nobody. Before code, Lead must fill named assignee/reviewer, exact allowlist, approved base/worktree, commands and authority. M0 target remains 2026-11-20. No runtime/source fetching or framework choice is authorized.


Related M0 records: [Rebaseline](academic-mvp-rebaseline-v0.1.md), [Shared contract](shared-interface-contract-v0.1.md), [Acceptance matrix](m0-acceptance-matrix-v0.1.md).
