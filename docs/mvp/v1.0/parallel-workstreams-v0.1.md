# Academic MVP — Parallel Workstreams & Integration Gates v0.1

- **Document version:** v0.1
- **Recording date:** 2026-11-06
- **Recording scope:** docs-only amendment; previously accepted construction; logical freeze pending Owner/independent review; no product/engineering acceptance.
- **Amendment task:** `MVP-M0-IF-FINAL-01`; `IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`.
- **Decision input:** `MVP-M0_Interface_Decision_Record_v0.1.md`, ID `PIT-MVP-M0-IF-DEC-20261106`, SHA256 `06376f07097e618bdb99c297d1ad73df9a38dfb3cc9433637608bd23f4d2b2b5`; technical proposal for this scope, not runtime/source/Git authority.
- **Acceptance dimensions:** `M0_DOCUMENT_CONSTRUCTION_ACCEPTED` (Owner-supplied prior independent review); `M0_CONTRACT_FREEZE_PENDING_REVIEW`; `TEAM_IMPLEMENTATION_NOT_AUTHORIZED`.
- **Approved M0 base:** `b3be0c0122dac804084d5e464f7bfc07313f02aa`; branch `mvp/m0-shared-contracts`.
- **Packet provenance:** `docs/mvp/v1.0/parallel-workstreams-v0.1.md` from `PIT_Research_Lab_v1.0_MVP-M0_Initialization_Packet_20261106.zip`; ZIP SHA256 `43033166586a50b78d569df81b7e0db8f9412544a351814ceaba818312b0bc98`. External text is input material, not operational authorization.

**Status:** ROLE OWNERSHIP READY FOR REVIEW / TEAM_IMPLEMENTATION_NOT_AUTHORIZED; named assignees/reviewers `TBD_BY_LEAD`. **Overall target:** 2027-04-30 feature freeze; school demo 2027-05/06. Dates are objectives, not guaranteed delivery.

## Dependency policy

After Owner accepts reviewed `M0 Shared Contracts`, separately assigned documentation/planning tasks for `F2-demo`, `F3`, `F4`, and `F6` may proceed **in parallel**; implementation still requires its own authorization. F6 does not wait for formal CAP-F2 or full F3, but cannot claim a real integrated run until F3 service exists. F5 policy evaluation requires F2 eligible observations and F3 experiment orchestration; its design can begin sooner.

## Track A — F2-Demo PIT Adapter（Technical Lead）

- **Minimum:** versioned fixture & manifest; exact source/time/version status; read-only SnapshotReference; eligible/unknown/withheld; replay; negative tests.
- **No-go:** calling B04 physical Harness, official TestLease, PG17, Layer B, or pretending synthetic success proves real PIT.
- **First handoff:** accepted, deterministic Snapshot fixtures and `SnapshotReference` mapping to F3/F6.
- **Acceptance:** same inputs/cutoff give same eligible outputs; late revision never enters prior decision time; source/version/unknown shown.
- **Blockers:** source API compatibility must be examined; no B04 branch wholesale adoption.

## Track B — F3 Research Laboratory L1（Member B）

- **Minimum:** versioned Hypothesis, valid ExperimentSpec, 1 actual statistical method (not stub), ResearchRun lifecycle, diagnostics, EvidenceBundle, deterministic replay.
- **First handoff:** runnable `Hypothesis -> Protocol -> Experiment -> Evidence` on pinned synthetic F2 fixture and `FixtureResearchClient` compatibility.
- **Future acceptance:** execution pass/fail/blocked and PIT withheld/unresolved are independent; deterministic result identity requires IF-03 approval before acceptance (target 2026-12-15); no post-cutoff input. No execution occurred here.
- **Blockers:** agreed schema & F2 fixed fixtures; no need for real PG or financial data first.

## Track C — F4 Bounded TWSE Data（Member A）

- **Minimum:** bounded real-source inventory, provenance, licencing/use preflight, content hashes, issuer/period/unit/currency mapping, missingness/quality, publication vs observation vs cutoff distinction; first source as small as needed.
- **First handoff:** sealed sample dataset + source/evidence/uncertainty mapping; no Historical PIT claim without evidence.
- **Acceptance:** raw source maps deterministically, asset identity and units verified, provenance visible, unknown preserved.
- **Blockers:** separate real-source permission and data availability; never scrape/use unapproved providers to meet schedule.

## Track D — F5 Sequential Comparison（Technical Lead with Member B）

- **Minimum:** benchmark and two policies, one shared eligible observation set, no lookahead, no survivor leakage, evaluation labels separate, transaction-cost assumptions, decision trace and metrics.
- **First handoff:** synthetic policy comparison with a known temporal negative case.
- **Acceptance:** identical information boundary across policies, deterministic metrics under pinned seed, costs/risk reported with limits.
- **Blockers:** F2 synthetic snapshot, F3 run/evidence integration.

## Track E — F6 Application/UI（Member C）

- **Minimum:** hypothesis/protocol input, dataset/cutoff source status, submit experiment, run status, evidence and provenance view, policy comparison, replay viewer, setup/run script; fixtures first, backend later.
- **First handoff:** click-through app with `FixtureResearchClient` showing success, unresolved, withheld and failed states and no hidden domain calculation.
- **Acceptance:** UI state tests, no optimistic promotion, backend schema contract tests; end-to-end interaction by 2027-01-31.
- **Detailed nodes:** [f6-application-ui-initialization-v0.1.md](f6-application-ui-initialization-v0.1.md).

## Integration cadence and milestone table

| Checkpoint | Date | Required cross-team artifact | Escalation if missed |
|---|---|---|---|
| M0 | 2026-11-20 | contract + owners + paths + SOP + safe branch base | Freeze new shared code until mismatch resolved |
| M1 | 2026-12-31 | F2 Synth -> F3 Experiment -> Evidence | Remove optional methods, not PIT checks |
| M2 | 2027-01-31 | F6 actually invokes backend; run returned and evidence displayed | Stop UI polish; fix adapter |
| M3 | 2027-02-28 | bounded real-source viewer or documented source insufficiency | Keep synthetic core, show honest limitations |
| M4 | 2027-03-31 | benchmark+2 policies using same observations | Stop ML/stretch |
| M5 RC | 2027-04-15 | reproducible complete demo, E2E tests | Defect fixes only |
| M5 freeze | 2027-04-30 | release candidate sealed | Only blocking fixes with recorded approval |

## Work handoff checklist

Task scope + files allowlist; input contract version; fixtures and expected behavior; tests run; failures and limitations; no claim beyond evidence; integration owner/PR; Next dependent task. Preferred weekly cross-team 20–30 min integration check and short written status: `DONE / BLOCKED / CHANGED-CONTRACT / NEXT`. No reliance on one person to relay undocumented protocol changes.

## Phase priority and present permission boundary

Codex 02 document construction is previously independently accepted per Owner; M0 logical contract freeze is pending Owner／independent review. The tracks above are future engineering outcomes, not implementation authorized here. Only after Owner accepts logical contracts may the following planning tasks be separately assigned. Roles are designated; named assignees/reviewers all remain `TBD_BY_LEAD`. No one is assigned to code by this charter.

| Proposed task | Responsible role | Dependencies | First planning output | No-go gate | Named assignee / reviewer |
|---|---|---|---|---|---|
| `F2-DEMO-PLAN` | Technical Lead (F2) | M0 logical contract Owner acceptance；IF-01/02/05 policy；IF-03 identity gate | 八個 evaluator 的 reuse/input/observation plan、synthetic qualification/error map、replay spec | 不啟動 adapter；runtime/input review、positive/negative predicates 與程式任務另審。 | `TBD_BY_LEAD` / `TBD_BY_LEAD` |
| `F3-L1-PLAN` | Member B (F3); Lead reviewer role | M0 review 後另行指派；contract v0.1、F2 synthetic fixture spec | Hypothesis → Protocol → actual statistical-method proposal → Evidence slice；module paths 與 checks 計畫 | 不建立 runner/DTO code；identity acceptance 先過 IF-03，真實 bridge 先過 IF-04。 | `TBD_BY_LEAD` / `TBD_BY_LEAD` |
| `F4-PILOT-PLAN` | Member A (F4/Data); Lead reviewer role | M0 review 後另行指派；IF-07 authority model | 僅 supplied metadata 的 bounded TWSE inventory、rights、release/observation-time evidence 計畫 | 不得 retrieval/intake；獨立 reviewer 與 rights/time/version evidence 未核准前不 admission 或 historical claim。 | `TBD_BY_LEAD` / `TBD_BY_LEAD` |
| `F6-00` | Member C (F6); Lead reviewer role | Owner 接受 M0 logical contracts 後另行指派；IF-02/04/05/06 | 六個 screen、三軸 state matrix、fixture client scenarios、framework/path/options recommendation | 僅 documentation/planning；不選定 framework、不 scaffold/install；F6-01/02 各需獨立 task authorization。 | `TBD_BY_LEAD` / `TBD_BY_LEAD` |
| `F5-PLAN` | Technical Lead + Member B | M0 review 後另行指派；F2/F3 contract 與 IF-05 boundaries | Benchmark+A/B、same information set、decision/evaluation labels、cost/trace spec | 沒有 F2/F3 implemented contracts 與另行任務，不執行 policies 或產生績效結論。 | `TBD_BY_LEAD` / `TBD_BY_LEAD` |

IF dispositions and no-go defaults are maintained in the [Shared Contract](shared-interface-contract-v0.1.md#if-disposition-register--proposed-for-independent-review) and [M0 acceptance register](m0-acceptance-matrix-v0.1.md#if-disposition-register--proposed-for-independent-review). IF-01 evaluator candidates need separate runtime/input review before F2-DEMO-ADAPTER; IF-02 App DTOs/ResearchClient remain NEW_M0_PROPOSAL; IF-03 canonical/digest oracle gate target 2026-12-15 before M1 identity/replay acceptance; IF-04 transport planning target 2026-12-20 before F6-08 / actual backend integration; IF-05 three-axis policy must pass independent review, translators later; IF-06 physical fixture paths are proposed in F6-00 before F6-02; IF-07 independent rights/time/version authority before intake/positive historical claims, checkpoint 2027-02-28. F2 Lead and Data Lead cannot self-certify their own ingestion.

The absence of F3/F5/F6 App directories/services is a retained Codex 02 static finding, not a new source audit. F6-00 documents six screens, client/scenario states and path/framework options only after Owner acceptance; F6-01 scaffold/install and F6-02 fixture code need separate task authorization. F3/F4/F5 planning cannot execute methods/policies or retrieve data. No framework is selected here.


Related M0 records: [Rebaseline](academic-mvp-rebaseline-v0.1.md), [Shared contract](shared-interface-contract-v0.1.md), [Acceptance matrix](m0-acceptance-matrix-v0.1.md).
