# Academic MVP — System UI & Research-First User Flow Specification v0.1

- **Status:** PROPOSED / OWNER REVIEW REQUIRED / NOT IMPLEMENTATION AUTHORIZATION
- **Date:** 2026-11-07
- **Intent:** A cross-module product/UX anchor for F2–F6. M0 accepted contracts and safety gates remain authoritative.
- **Source basis:** User-provided draft “研究動機與目的 — 初稿”, §§1.1–1.5 (conversation attachment, not copied here). It defines a Financial Research Workbench: research question first, historically qualified information, appropriate methods, verifiable evidence, reproducibility, and no automatic stock recommendation.
- **Related M0 contracts:** [Rebaseline](academic-mvp-rebaseline-v0.1.md) · [Shared Interface](shared-interface-contract-v0.1.md) · [F6 Charter](f6-application-ui-initialization-v0.1.md) · [Workstreams](parallel-workstreams-v0.1.md).
- **Companion proposal:** [F3/F5 Reverse Design](f3-f5-research-methods-decision-spec-v0.1.md).
- **UX-D01 product direction (Owner):** Decision frequency is configurable in the product architecture. **Weekly is the sole executable Academic MVP requirement**; Monthly is optional next, Daily later. Showing future options does not imply execution support, and accepted M0 AC-05 is unchanged.
- **Temporal ADR:** [UX-ADR-01 — Weekly-first Temporal Execution Contract](ux-adr-01-temporal-execution-contract-v0.1.md) is the companion proposal for P1 remediation, per-cutoff binding, synthetic data and acceptance; status pending Owner/independent design review.

## 1. Product thesis and limits

**Question → Point-in-Time Boundary → Appropriate Method → Genuine Execution → Results & Decision Comparison → Evidence & Replay.**

The system is a research workbench, not a trading recommendation service, live order system, universal DL/RL toolkit, or source-of-truth assertion engine in the UI. Users must distinguish statistical association from causation, predictive quality from investable performance, observed source bytes from historical availability, and mock scenarios from actual runs.

This is an additive design proposal, not an amendment to M0 RBL-01..12 or AC-01..08. No new executable API, backend, DB schema, team task, model or F6 scaffold is approved by this file.

## 2. Canonical user journey

The seven actions below **reuse the six existing M0 screen surfaces**; they do not add seven separate pages:

1. **Research question first** — enter a falsifiable question, hypothesis, task family (association / prediction / decision), outcome definition, horizon and scope in the Research Setup screen.
2. **Choose historical information** — visit Dataset/Snapshot Chooser; select data mode, manifest, universe, version and decision cutoff; examine eligibility and evidence gaps.
3. **Design the experiment** — return to Research Setup; choose a supported F3 statistical method and optional F5 model/policy; choose decision cadence (**Weekly executable MVP; Monthly/Daily visibly planned or unavailable until independently accepted and actually supported**), and separately specify prediction horizon, rebalance schedule, temporal train/validation/test plan, seed, baseline, metrics and cost assumptions.
4. **Run** — submit a versioned experiment via a separately reviewed client; show actual run lifecycle, blocking reasons and errors.
5. **Interpret evidence** — explain results against the original question, including metric units, diagnostics, lineage, uncertainty, failures and limits.
6. **Compare decisions when applicable** — Benchmark + A + B, identical eligible decision-time observation set, cost/risk/performance and action trace. Model prediction is not a trading decision.
7. **Replay/export** — display manifest/spec/method/code/seed IDs, reproducibility conditions, digest mismatch or blocked checks, export constraints.

The entry can begin in Research Setup even though the historical M0 screen inventory lists Dataset Chooser first. F6-00 chooses the final navigation mechanism without rewriting that inventory.

## 3. Six-screen information architecture

| M0 Screen | Essential user-facing content | Domain authority | Forbidden |
|---|---|---|---|
| **S1 Dataset/Snapshot Chooser** | mode, issuer/period, publication vs observation vs cutoff, source/version/manifest, qualified/excluded/unknown reasons, trace link | F2/F4 | Reclassify PIT, assume source rights, replace missing history with later versions |
| **S2 Research Setup** | question, hypothesis, target/horizon, configurable frequency (Weekly supported MVP; Monthly then Daily planned), supported method×frequency combinations, rebalance/evaluation settings, seed, temporal splits, predeclared evaluation plan | F3 temporal protocol; F5 method/frequency capability | Show planned cadence/method as executable; permit leaky split or invalid inputs |
| **S3 Run Detail** | run ID, true/fixture provenance, NOT_RUN/PENDING/RUNNING/SUCCEEDED/FAILED/BLOCKED, sanitized error, non-optimistic retries | F3 ResearchRun | Label fixture success as actual execution |
| **S4 Evidence & Provenance** | question and claim, evidence class, metrics/diagnostics, source/version/lineage, uncertainty and limitations | F3 EvidenceBundle with F2/F5 references | Zero-fill unknown, claim causation or historical verification by a hash |
| **S5 Decision Comparison** | selected decision cadence and generated timestamps, Benchmark/A/B, common eligible information boundary, action traces, rebalance/cost assumptions, gross/net return, turnover, drawdown/risk, metric horizon | F5 EvaluationResult / DecisionTrace | Compute P&L in UI, conflate decision vs rebalance cadence, or present cross-frequency results as directly comparable without normalization |
| **S6 Replay/Export Viewer** | identities, replay basis and status, mismatch, scope-limited export | F2/F3/F5 evidence owners | Invent deterministic equivalence or disclose protected raw data |

Research question and method selection may be progressive sections inside S2. Results and decision comparison must retain separate research-vs-action interpretation even when shown on neighboring screens.

## 4. Demonstration case

**Question:** Does historically qualified monthly-revenue growth supply out-of-sample predictive information for subsequent stock returns in a bounded TWSE sample? This is predictive/associational, not causal or investment advice.

- **Synthetic (Mode S):** pinned trading-session calendar, **daily synthetic price observations plus monthly revenue release/version events**, intentional late revisions/unknown/withheld cases, actual executed F3 statistical analysis, and a **Weekly** benchmark + two-policy comparison on per-tick qualified information. Every execution follows the reviewed calendar, price timing and label-maturity convention. Synthetic scope is explicit; fixture UI scenarios are not executed research. SYNTHETIC_GOLDEN is not formal Frozen Golden 110/154.
- **Bounded Real TWSE (Mode R):** show authorized source provenance, units, quality and availability uncertainty. Modern source observation does not establish historical publication/version availability; show UNRESOLVED or existing WITHHELD where needed. A real-source viewer may be limited without a positive historical PIT claim.
- **Preferred F5 decision comparison:** common universe, **per-tick cutoff and qualified observation binding**, benchmark, pre-specified rule policy A and feature/model-based policy B on a **single reviewed Weekly schedule**, same evaluation horizon and documented transaction costs. Monthly can follow Weekly acceptance, and Daily only later. Additional cadences are optional, separately tested extensions; no three-frequency MVP runtime obligation. Small supervised ML is preferred if feasible; DL/RL remain future capabilities, not implied current implementation.
- **Freshness is not decision frequency:** a daily decision may reuse the last already-qualified monthly revenue version until a newly released version becomes admissible; it must never invent daily updates of monthly revenue. Daily price observations do not establish daily historical availability of the fundamental signal.

## 5. Status, method suitability and negative-path UX

Preserve the existing independent dimensions:
- PIT: ELIGIBLE / INELIGIBLE / UNRESOLVED / WITHHELD.
- Execution: NOT_RUN / PENDING / RUNNING / SUCCEEDED / FAILED / BLOCKED.
- Evidence: SYNTHETIC_VERIFIED_IN_SCOPE / REAL_SOURCE_OBSERVED / HISTORICAL_PIT_SUPPORTED_IN_SCOPE / PROVISIONAL / UNVERIFIED.
- Data mode and separate FIXTURE_ONLY provenance remain visible.

Do not infer ELIGIBLE from native SUPPORTED/SELECTED, a successful run, a source digest or the frontend. Positive/negative predicates, typed failures, qualification reasons, admission flags and source/version/cutoff references require reviewed backend authority under M0 IF-05.

For method/frequency selection, proposed presentation descriptors are EXECUTABLE (backend-confirmed for the exact method, protocol, selected frequency and data mode), SPEC_ONLY, UNAVAILABLE and BLOCKED_BY_INPUT. These are **presentation-only**, not new DTO enums. **Weekly is the sole required runnable cadence**; Monthly and Daily can be visible as planned/unsupported until the actual backend capability is independently accepted. Unsupported combinations show exact reasons and are not submitted. Never show planned DL/RL as runnable.

| Negative path | UI expected behavior |
|---|---|
| Missing or conflicting release/version time | UNRESOLVED, visible source reason, no invented qualified record |
| Diagnostic WITHHELD or not admission eligible | WITHHELD and diagnostic warning, never success/empty metric |
| Mock success fixture | FIXTURE_ONLY and simulated; actual execution NOT_RUN |
| SUCCEEDED run with UNRESOLVED PIT | Independent success and uncertainty; no historical claim |
| Insufficient sample, unsupported method, invalid temporal split | Explicit limitation or BLOCKED, no fabricated result |
| Label unavailable by decision cutoff | Exclude from decision observations; it may be used only in post-decision evaluation when mature |
| Typed run error, timeout | Sanitized first failure and correct status; metrics absent |
| Manifest, cutoff or version changed | Invalidate stale qualification/result identity; replay not silently accepted |
| Policies use different eligible information | Comparison invalid/blocked or explicitly non-comparable; no winning claim |
| Data available monthly while decision cadence is Daily | Reuse only the latest version qualified by each daily cutoff; repeat observation references transparently, never fabricate fresh monthly data |
| Method unsupported at selected cadence / insufficient eligible observations | Mark combination UNAVAILABLE or BLOCKED_BY_INPUT with reason; no fake success |
| Non-trading-day weekly/monthly anchor or ambiguous time zone | Use one reviewed calendar/roll convention or refuse protocol until configured |
| Cross-frequency performance comparison | Only available after an extra cadence is actually implemented and reviewed; align periods/universe/outcome horizon/cost/annualization or mark non-comparable |
| Method shown but unimplemented (including Monthly/Daily) | Show SPEC_ONLY/UNAVAILABLE/BLOCKED_BY_INPUT and why; disable submission, do not fabricate a completed run |
| Actual F3 experiment returns SUCCEEDED but hypothesis not supported | Preserve genuine SUCCEEDED, PIT/evidence class unchanged, and present F3-supported negative/inconclusive research conclusion with diagnostics; never convert it to FAILED or a positive research claim |

## 6. Logical port / data ownership

Existing proposed ResearchClient operations only: listDatasets, getSnapshot, submitExperiment, getRun, getEvidence, optional getEvaluation. None is a verified route, runtime service or transport choice. Existing seven application DTOs remain NEW_M0_PROPOSAL. F6 never reads database directly, runs PIT/financial authority logic, or guesses missing backend metrics.

A future method-capability descriptor may include method ID/version, task family, supported modes, input requirements, validation constraints and readiness; it is a **candidate design**, not a new schema field or API without IF-02 change review.

## 7. User-acceptance stories (future tests, NOT_RUN)

- **UAT-01:** Question → qualified synthetic snapshot → genuine supported statistical method → Run → Evidence → Replay.
- **UAT-02:** Benchmark + policies A/B use identical eligible observations; costs, net/gross performance and traces displayed.
- **UAT-03:** Late revision, missing release time, stale manifest and withheld result are never promoted.
- **UAT-04:** Fixture-only mock success remains distinct from real execution and verified evidence.
- **UAT-05:** Real source observed without historical time/version proof remains unresolved.
- **UAT-06:** Unsupported methods, too-small samples and leaky temporal splits refuse or warn truthfully.
- **UAT-07:** Run failure and replay mismatch never become successful results.
- **UAT-08 (Weekly MVP):** A pinned Synthetic market calendar produces one deterministic Weekly decision schedule; the genuine Benchmark/A/B comparison uses identical per-tick qualified information, with cost/risk/action evidence. Monthly/Daily are not required to run.
- **UAT-09 (Weekly PIT):** Monthly revenue is unavailable at earlier Weekly cutoffs; revised versions appear only after qualification; repeated fundamental values do not become independent samples. Daily synthetic prices are available only under their valid observation/execution time rules.
- **UAT-10 (Capability + result interpretation):** Monthly/Daily or method×mode combinations lacking actual backend support are marked unavailable; an actual SUCCEEDED experiment with unsupported/inconclusive hypothesis stays SUCCEEDED and shows its F3 evidence; a mock stays FIXTURE_ONLY / actual NOT_RUN.

F6-00 must describe fields, controls, screen transitions, empty/loading/blocked views, accessibility, method readiness, provenance presentation and negative cases. Implementation/test execution is a separate authorized workstream.

## 8. UX-D01 — Weekly-first configurable temporal capability

**Decision:** The user-facing product supports a frequency configuration concept. The **Academic MVP executes Weekly only**. Monthly is a non-mandatory second extension; Daily is a later third extension. A method/cadence/mode must be confirmed EXECUTABLE by an actual reviewed backend, not by a frontend selector or sample fixture. The accepted M0 AC-05 remains the minimum and is demonstrated on one Weekly Synthetic schedule.

**Generic Temporal Execution Contract:** Consult [UX-ADR-01](ux-adr-01-temporal-execution-contract-v0.1.md), which distinguishes source/data cadence, decision frequency, prediction horizon, rebalance cadence and evaluation aggregation; defines a conceptual schedule and **per-decision-cutoff Snapshot/qualification binding**; and specifies calendar, synthetic prices, monthly release/version events, label maturity, costs and negative tests. This is not a new M0 DTO/API. Implementation layout/translator placement requires IF-02 review and replay hash acceptance still requires IF-03.

**Minimum Weekly demo:** choose a Weekly protocol, load pinned Synthetic calendar + daily prices + monthly revenue publication/revision events, qualify available versions separately for each Weekly decision cutoff, execute F3's genuine method, then run Benchmark/A/B with the **same eligible information per tick**. Show run status, negative research conclusions, evidence provenance, action/cost/risk results and replay limitations. No real historical availability claim is inferred.

**MVP flexibility:** Show Monthly/Daily as planned/unavailable, with a reason and no execution button. After separate approval and real implementation, a Monthly capability may be enabled; Daily follows later. UI never silently falls back to Weekly or treats resampled monthly data as daily freshness.

**P2 follow-ons:** Minimal versioned run/config identity and stale-result invalidation are planned for a separately authorized implementation task subject to IF-02/IF-03. Overlapping targets, repeated monthly signals and other non-IID inference limits are recorded now; advanced dependence-aware inference is deferred to F3 planning without waiving basic anti-leakage checks.

## 9. Open decisions / non-silent reconciliation

| ID | Issue | Owner and hard gate |
|---|---|---|
| UX-D01 | Product direction: configurable frequency; **Weekly-only executable MVP**, optional Monthly followed by Daily. Per-tick snapshot binding and synthetic temporal dataset are documented in UX-ADR-01; exact calendar/roll/cutoff/outcome/cost conventions remain engineering gates. | Owner/independent design acceptance of UX-ADR-01; IF-02 representation review before code; IF-03 before replay identity acceptance. M0 AC-05 unchanged. |
| UX-D02 | F3 genuine statistical method, assumptions and meaningful diagnostics | Member B proposal / Lead review before F3-L1 implementation |
| UX-D03 | Exact benchmark, policy A/B and predictive-to-action conversion | F5 planning before implementing AC-05 |
| UX-D04 | Method-capability metadata versus existing DTO/ResearchClient | F3/F5/F6 design review; IF-02 before schema/code changes |
| UX-D05 | Framework, physical frontend paths, fixtures | F6-00 proposal; F6-01/02 separately authorized |
| UX-D06 | Canonicalization, transport and real-source rights | Existing M0 IF-03 / IF-04 / IF-07 gates remain binding |

## 10. Coding-agent stop conditions and governance

A task packet must state approved M0 base/version, this proposal and UX-ADR-01 review status, **Weekly** executable MVP scope, exact file allowlist, expected behavior and negative tests, named owner/reviewer, and permitted data/dependencies. If a design conflicts with M0, **STOP and request an ADR**, never reinterpret M0 silently. No direct changes to main, B04 dirty worktree, physical Harness/CTRL03/PG17, migrations, protected sources or formal Golden. No feature implementation is authorized by this document.

**Current status: PROPOSED.** No acceptance, runtime pass, code, API, backend, frontend or team assignment is claimed.
