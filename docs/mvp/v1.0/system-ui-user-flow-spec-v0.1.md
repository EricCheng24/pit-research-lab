# Academic MVP — System UI & Research-First User Flow Specification v0.1

- **Status:** PROPOSED / OWNER REVIEW REQUIRED / NOT IMPLEMENTATION AUTHORIZATION
- **Date:** 2026-11-07
- **Intent:** A cross-module product/UX anchor for F2–F6. M0 accepted contracts and safety gates remain authoritative.
- **Source basis:** User-provided draft “研究動機與目的 — 初稿”, §§1.1–1.5 (conversation attachment, not copied here). It defines a Financial Research Workbench: research question first, historically qualified information, appropriate methods, verifiable evidence, reproducibility, and no automatic stock recommendation.
- **Related M0 contracts:** [Rebaseline](academic-mvp-rebaseline-v0.1.md) · [Shared Interface](shared-interface-contract-v0.1.md) · [F6 Charter](f6-application-ui-initialization-v0.1.md) · [Workstreams](parallel-workstreams-v0.1.md).
- **Companion proposal:** [F3/F5 Reverse Design](f3-f5-research-methods-decision-spec-v0.1.md).

## 1. Product thesis and limits

**Question → Point-in-Time Boundary → Appropriate Method → Genuine Execution → Results & Decision Comparison → Evidence & Replay.**

The system is a research workbench, not a trading recommendation service, live order system, universal DL/RL toolkit, or source-of-truth assertion engine in the UI. Users must distinguish statistical association from causation, predictive quality from investable performance, observed source bytes from historical availability, and mock scenarios from actual runs.

This is an additive design proposal, not an amendment to M0 RBL-01..12 or AC-01..08. No new executable API, backend, DB schema, team task, model or F6 scaffold is approved by this file.

## 2. Canonical user journey

The seven actions below **reuse the six existing M0 screen surfaces**; they do not add seven separate pages:

1. **Research question first** — enter a falsifiable question, hypothesis, task family (association / prediction / decision), outcome definition, horizon and scope in the Research Setup screen.
2. **Choose historical information** — visit Dataset/Snapshot Chooser; select data mode, manifest, universe, version and decision cutoff; examine eligibility and evidence gaps.
3. **Design the experiment** — return to Research Setup; choose a supported F3 statistical method and optional F5 model/policy, temporal train/validation/test plan, seed, baseline, metrics and cost assumptions.
4. **Run** — submit a versioned experiment via a separately reviewed client; show actual run lifecycle, blocking reasons and errors.
5. **Interpret evidence** — explain results against the original question, including metric units, diagnostics, lineage, uncertainty, failures and limits.
6. **Compare decisions when applicable** — Benchmark + A + B, identical eligible decision-time observation set, cost/risk/performance and action trace. Model prediction is not a trading decision.
7. **Replay/export** — display manifest/spec/method/code/seed IDs, reproducibility conditions, digest mismatch or blocked checks, export constraints.

The entry can begin in Research Setup even though the historical M0 screen inventory lists Dataset Chooser first. F6-00 chooses the final navigation mechanism without rewriting that inventory.

## 3. Six-screen information architecture

| M0 Screen | Essential user-facing content | Domain authority | Forbidden |
|---|---|---|---|
| **S1 Dataset/Snapshot Chooser** | mode, issuer/period, publication vs observation vs cutoff, source/version/manifest, qualified/excluded/unknown reasons, trace link | F2/F4 | Reclassify PIT, assume source rights, replace missing history with later versions |
| **S2 Research Setup** | question, hypothesis, target/horizon, methods and suitability, seed, temporal splits, predeclared evaluation plan | F3 protocol; F5 method capability | Show unsupported algorithms as executable; permit leaky split or invalid inputs |
| **S3 Run Detail** | run ID, true/fixture provenance, NOT_RUN/PENDING/RUNNING/SUCCEEDED/FAILED/BLOCKED, sanitized error, non-optimistic retries | F3 ResearchRun | Label fixture success as actual execution |
| **S4 Evidence & Provenance** | question and claim, evidence class, metrics/diagnostics, source/version/lineage, uncertainty and limitations | F3 EvidenceBundle with F2/F5 references | Zero-fill unknown, claim causation or historical verification by a hash |
| **S5 Decision Comparison** | Benchmark/A/B, shared information boundary, action traces, rebalance/cost assumptions, gross/net return, turnover, drawdown/risk | F5 EvaluationResult / DecisionTrace | Compute authoritative P&L in UI or silently compare unequal information sets |
| **S6 Replay/Export Viewer** | identities, replay basis and status, mismatch, scope-limited export | F2/F3/F5 evidence owners | Invent deterministic equivalence or disclose protected raw data |

Research question and method selection may be progressive sections inside S2. Results and decision comparison must retain separate research-vs-action interpretation even when shown on neighboring screens.

## 4. Demonstration case

**Question:** Does historically qualified monthly-revenue growth supply out-of-sample predictive information for subsequent stock returns in a bounded TWSE sample? This is predictive/associational, not causal or investment advice.

- **Synthetic (Mode S):** pinned deterministic issuer-month records, intentional late revisions/unknown/withheld cases, actual executed statistical analysis, and a benchmark + two-policy comparison on qualified information. Clearly show synthetic scope and distinguish fixture scenarios from executed research. SYNTHETIC_GOLDEN is not formal Frozen Golden 110/154.
- **Bounded Real TWSE (Mode R):** show authorized source provenance, units, quality and availability uncertainty. Modern source observation does not establish historical publication/version availability; show UNRESOLVED or existing WITHHELD where needed. A real-source viewer may be limited without a positive historical PIT claim.
- **Preferred F5 decision comparison:** common universe and cutoff; benchmark, pre-specified rule policy A and feature/model-based policy B; same evaluation horizon and documented transaction costs. Small supervised ML is preferred if feasible; DL/RL remain future capabilities, not implied current implementation.

## 5. Status, method suitability and negative-path UX

Preserve the existing independent dimensions:
- PIT: ELIGIBLE / INELIGIBLE / UNRESOLVED / WITHHELD.
- Execution: NOT_RUN / PENDING / RUNNING / SUCCEEDED / FAILED / BLOCKED.
- Evidence: SYNTHETIC_VERIFIED_IN_SCOPE / REAL_SOURCE_OBSERVED / HISTORICAL_PIT_SUPPORTED_IN_SCOPE / PROVISIONAL / UNVERIFIED.
- Data mode and separate FIXTURE_ONLY provenance remain visible.

Do not infer ELIGIBLE from native SUPPORTED/SELECTED, a successful run, a source digest or the frontend. Positive/negative predicates, typed failures, qualification reasons, admission flags and source/version/cutoff references require reviewed backend authority under M0 IF-05.

For the method selector, proposed presentation descriptors are EXECUTABLE (backend-confirmed for this specific protocol), SPEC_ONLY, UNAVAILABLE and BLOCKED_BY_INPUT. These are **not new DTO enums**. Never display planned DL/RL as if runnable.

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

F6-00 must describe fields, controls, screen transitions, empty/loading/blocked views, accessibility, method readiness, provenance presentation and negative cases. Implementation/test execution is a separate authorized workstream.

## 8. Open decisions / non-silent reconciliation

| ID | Issue | Owner and hard gate |
|---|---|---|
| UX-D01 | Attached research draft §1.5 proposes daily prices/weekly decisions; M0 first example uses monthly revenue/subsequent-month return. These are **not equivalent sampling/evaluation contracts**. | F3/F5 Lead with F2 determines rebalance grid, label horizon, maturity and temporal split **before policy code**. Preserve M0 research case meanwhile. |
| UX-D02 | F3 genuine statistical method, assumptions and meaningful diagnostics | Member B proposal / Lead review before F3-L1 implementation |
| UX-D03 | Exact benchmark, policy A/B and predictive-to-action conversion | F5 planning before implementing AC-05 |
| UX-D04 | Method-capability metadata versus existing DTO/ResearchClient | F3/F5/F6 design review; IF-02 before schema/code changes |
| UX-D05 | Framework, physical frontend paths, fixtures | F6-00 proposal; F6-01/02 separately authorized |
| UX-D06 | Canonicalization, transport and real-source rights | Existing M0 IF-03 / IF-04 / IF-07 gates remain binding |

## 9. Coding-agent stop conditions and governance

A task packet must state approved M0 base/version, this proposal's review status, exact file allowlist, expected behavior and negative tests, named owner/reviewer, and permitted data/dependencies. If a design conflicts with M0, **STOP and request an ADR**, never reinterpret M0 silently. No direct changes to main, B04 dirty worktree, physical Harness/CTRL03/PG17, migrations, protected sources or formal Golden. No feature implementation is authorized by this document.

**Current status: PROPOSED.** No acceptance, runtime pass, code, API, backend, frontend or team assignment is claimed.
