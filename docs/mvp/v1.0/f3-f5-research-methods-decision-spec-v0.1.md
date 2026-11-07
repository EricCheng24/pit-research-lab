# Academic MVP — F3/F5 Research Methods & Decision Evaluation Reverse Design v0.1

- **Status:** PROPOSED / OWNER AND INDEPENDENT REVIEW REQUIRED / NOT IMPLEMENTATION AUTHORIZATION
- **Recorded:** 2026-11-07
- **Purpose:** Backward-design F3 and F5 from the [System UI/User Flow](system-ui-user-flow-spec-v0.1.md) without silently widening the accepted M0 MVP commitments.
- **UX-D01 Owner scope decision (2026-11-07):** General configurable decision frequency, but **Weekly is the only mandatory executable Academic MVP cadence**; Monthly and then Daily are optional extensions. Frozen M0 AC-05 remains authoritative; no extra three-cadence MVP requirement.
- **Temporal ADR / P1 remediation proposal:** [UX-ADR-01 Weekly-first Temporal Execution Contract](ux-adr-01-temporal-execution-contract-v0.1.md). No accepted App schema or runtime is implied.
- **Normative references:** [Academic MVP Rebaseline](academic-mvp-rebaseline-v0.1.md), [Shared Interface Contract](shared-interface-contract-v0.1.md), [F6 Initialization](f6-application-ui-initialization-v0.1.md), [Workstreams](parallel-workstreams-v0.1.md). M0 RBL-01..12, AC-01..08, IF-01..07 remain unchanged.
- **Source basis:** Owner-supplied October 2026 draft “研究動機與目的 — 初稿”, §§1.1–1.5. Source positions the project as a research-first Financial Research Workbench with historical information evidence, hypothesis/method selection, experiment reproducibility and optional sequential decisions. This document is an engineering proposal, not a verbatim source transcription.

## 1. Stable mission and module ownership

**F3 — Research Design & Experimentation.** Own a falsifiable research question, hypothesis identity/version, target/feature and horizon definitions, experimental protocol, **decision-frequency configuration and its consistency with label maturity**, temporal validation design, statistical inference/diagnostics for the actual supported method, run orchestration and reproducible EvidenceBundle. F3 records limitations and unsupported conclusions.

**F5 — Research Methods, Model & Decision Evaluation.** Long-term expandable computational/evaluation family for statistical/ML/DL/RL methods and decision policies. Own method implementation and capability descriptors (where delegated), **method × decision-frequency support**, model fit/predict/evaluate, baseline comparisons, policy construction over the accepted decision schedule, action traces, trading-cost assumptions, portfolio/performance/risk metrics and method-specific evidence. F5 must not change F3's hypothesis or F2's PIT authority.

**MVP first instantiation:** Financial decision comparison in a small PIT-qualified TWSE-like synthetic research case using a **Weekly** decision schedule. The existing Benchmark + two Policies, identical **per-tick eligible information**, action traces, costs/risk/performance remain mandatory under M0 AC-05. Monthly then Daily are optional after Weekly acceptance, not required now. A simple supervised ML method is preferred if feasible, but **DL/RL are not mandatory**. F3's genuine statistical method is mandatory under AC-02; mock-only experiments do not qualify.

**F2/F4** own temporal/source authority and source facts; **F6** owns orchestration/presentation, not authoritative computations.

## 2. Research problem to evaluation contract

An MVP hypothesis should contain: research question, H0/H1 or explicitly testable claim, universe, target definition and measurement time, candidate features, information cutoff, horizon, anticipated direction, exclusion rules, validation plan, baseline, predeclared metrics and interpretable limitations. The statistical/predictive task and any trading policy must be separately specified.

**Suggested user question:** “Does PIT-qualified monthly-revenue growth carry out-of-sample predictive information for subsequent stock returns for a bounded TWSE sample?” This is association/prediction; no causal inference claim.

Temporal protocol must distinguish:
- financial period end;
- original release/publication time and any revision;
- source observation/acquisition time;
- cutoff/decision time;
- prediction target/outcome horizon and when the outcome becomes observable;
- train/validation/test split maturity;
- action timestamp and execution-cost assumptions if converting forecast to decision.

The research draft §1.5 suggests daily data with Weekly decisions; accepted M0 RBL-03 specifies monthly-revenue inputs and subsequent-month return questions. These are **distinct temporal dimensions**, not competing fixed choices. The initial Academic MVP combines monthly revenue releases, daily synthetic price observations and **Weekly** decision opportunities. The general model separates data cadence, decision cadence, target horizon, rebalance and evaluation; Monthly and Daily **decision schedules are optional extensions**. Exact calendar/label/cost conventions require separate protocol review.

## 3. Proposed M1 and M4 vertical slices

| Milestone | Scope | Acceptance evidence | Not accepted as substitute |
|---|---|---|---|
| **M1 by 2026-12-31** | F2 pinned synthetic observation + F3 versioned Hypothesis/Protocol + one genuine runnable statistical method + ResearchRun/EvidenceBundle | deterministic positive/negative synthetic examples, actual runner result, errors, reproducible identity after IF-03 review | descriptive UI metrics, hand-entered success, simulated statistical results |
| **M2 by 2027-01-31** | F6 actual backend submission/status/evidence rendering via separately approved IF-04 bridge | same protocol consumed end-to-end; no optimistic state promotion; browser/contract tests | FixtureResearchClient-only success |
| **M3 by 2027-02-28** | bounded real TWSE source and quality/availability viewer where independently authorized | source/time/version/rights limitations truthfully shown | current source bytes as Historical PIT proof |
| **M4 by 2027-03-31** | **Weekly** deterministic Synthetic decision schedule with Benchmark + A + B on identical qualified per-tick information | actual action traces, cost/risk/performance, source/label/time negative cases, reproducible evidence | three-frequency UI mock, future-label leakage or unequal information sets |
| **M5 by 2027-04-30** | stable demo and evidence/replay, negative paths, handoff | clean setup, real actual execution, replay proof as applicable | optional DL/RL or unreviewed extra UI features |

M0 AC-01..08 and formal CAP-F2 engineering gates retain their independent scope.

## 4. F3 MVP functional contract

1. **HypothesisSpec (conceptual, not new Shared DTO):** ID/version, user-facing question, measurable claims, universe/time/horizon, source qualification requirements and limits.
2. **ExperimentSpec (existing proposed M0 DTO):** link hypothesis/version to snapshot, method/version, evaluation plan, seed, temporal policy. Its single snapshot_id does **not itself identify a sequence of Weekly per-cutoff snapshots**. UX-ADR-01 proposes a versioned DecisionSchedule and per-decision Snapshot/qualification bindings; encoding or sidecar selection requires IF-02 review, not unilateral DTO changes. Separate data frequency, decision cadence, prediction horizon, rebalance and evaluation aggregation. Reject incoherent schedules, post-cutoff features and immature target outcomes.
3. **Real statistical method:** propose one defensible simple analysis with stated assumptions, diagnostics and temporal dependence limitations (e.g. an association/linear-regression baseline on a pinned synthetic panel). The exact method and validity checks are **UX-D02 open**, not pre-approved here. Must actually execute; no stub metrics.
4. **ResearchRun:** NOT_RUN/PENDING/RUNNING/SUCCEEDED/FAILED/BLOCKED are execution lifecycle, independent from PIT and evidence quality. Preserve typed first failure and no fabricated metrics on error.
5. **EvidenceBundle:** protocol/method/source/code/seed identifiers, diagnostics/metrics with denominator/units, lineage, evidence class, limitations and replay identity. A negative or unsupported hypothesis must be displayable as honestly as a favorable outcome.

**F3 completion:** a falsifiable question can be submitted with a genuinely qualified synthetic snapshot to one real method; it yields a real EvidenceBundle and predictable failure modes, not UI-simulated success.

## 5. F5 MVP functional contract

### A. Method-capability layer

Long-term method families:
- **Statistics:** simple association, regression and uncertainty diagnostics, with protocol and assumptions;
- **ML (preferred MVP addition):** simple regularized regression or comparably explainable supervised estimator, temporal out-of-sample validation, feature transformation fit only on training data;
- **DL (stretch):** representation/sequence models only after sufficient sample and separate review;
- **RL/sequential optimization (future):** state/action/reward, transition assumptions, policy evaluation; no off-policy causal claims without adequate support.

Method selection must be constrained by task type, target maturity, sample sufficiency, input data, **selected decision frequency**, compute/resource policy and implementation readiness. A listed future model or unsupported method–frequency combination must not be presented as executable.

### A1. UX-D01 — General temporal execution, Weekly-first delivery

**Product model:** Decision frequency remains user-configurable, not a universal fixed boundary. The **only required executable Academic MVP frequency is Weekly**. Monthly follows as an optional extension after Weekly tests, Daily only after Monthly. A UI option does not constitute implementation.

The [UX-ADR-01 Temporal Contract](ux-adr-01-temporal-execution-contract-v0.1.md) specifies five separate temporal concepts, conceptual TemporalConfiguration/DecisionSchedule/PerDecisionBinding, responsibilities and negative acceptance examples. In particular, **each Weekly decision cutoff must bind its own F2-qualified snapshot/trace**, not inherit a one-time eligible status from the whole DatasetManifest or a single snapshot_id. A versioned sequence-level context remains conceptual pending IF-02 adapter/schema review; IF-03 is needed before cryptographic identity/replay acceptance.

**F4** supplies authorized source cadence and source-time/coverage facts. **F2** independently qualifies historical availability at each Weekly tick; late monthly release/revision cannot enter earlier decisions. **F3** fixes research horizon, calendar/time cutoffs, training/label maturity, genuine statistical method and ResearchRun/Evidence. **F5** executes Benchmark/A/B on the same allowed per-tick observations and computes actions/costs/risks/returns. **F6** displays cadence choice and limitations without adjudicating source, execution or evidence.

**Synthetic MVP dataset contract:** a pinned trading-session calendar, daily synthetic price/execution basis, monthly revenue publication/version event log (including late/revised/missing/withheld cases), explicit future target maturity and cost/risk definitions. Monthly revenue rows alone are insufficient for Weekly policy return and risk computation. The exact Weekly decision timestamp, market calendar/timezone, holiday roll, next tradable price, price availability, rebalance and label rules are **F2/F3/F5 planning gates before code**, not silent UI defaults.

**Acceptance:** one genuine Weekly synthetic schedule, F3 actual supported method, Benchmark + two policies on identical cutoff-qualified information, deterministic action traces and performance/cost/risk, plus temporal negative tests (late publication, revision, immature target, calendar closure, missing/withheld, stale replay). Monthly/Daily are **not** M4 gates. Any new cadence needs separate scope/engineering acceptance.

### B. Benchmark and two-policy case

- **Benchmark:** fixed stated default (e.g. an explicitly defined no-signal or eligible-universe reference); exact policy open as UX-D03.
- **Policy A:** pre-specified rule based only on cutoff-qualified observations.
- **Policy B:** feature/model-based rule on the same available observation set and trained without future leakage.
- **Same-information contract:** for the required Weekly comparison, benchmark/A/B share issuer universe, **each decision tick and its independently qualified Snapshot/trace**, eligible observation version, withholding rules, action/rebalance convention and evaluation horizon; if not met, comparison is blocked/non-comparable. Future cross-frequency comparisons need their own harmonized metric/calendar/transaction-cost review.
- **DecisionTrace:** source observation ref, eligibility status, action, decision time, cost, outcome ref and limitation. Future realized return is evaluation-only; never a contemporaneous observation.
- **EvaluationResult:** documented gross vs net return and cost rules, turnover, volatility/drawdown, metric horizon/units and missingness, benchmark and uncertainty limitations. Small sample metrics must not be framed as robust financial superiority.
- **Prediction→Action transformation:** explicit separately versioned mapping, thresholds/selection/rebalance, trade execution convention and friction assumptions. A lower MAE does not imply higher Sharpe or profitability.

### C. Fairness / negative case obligations

- Same decision-time eligible information, outcome maturity, decision schedule and evaluation window across policies within each selected frequency;
- no post-cutoff labels in training/features/state;
- temporal train/test isolation; prevent preprocessing fit on test rows;
- bounded universe and no hidden survival filtering or selectively dropped failed runs;
- explicit cost assumptions rather than free turnover;
- consistent identity, version, method seed and reproducible traces;
- preserve ineligible/unresolved/withheld distinctions, and fail closed on unsupported positive claims.

**F5 MVP acceptance:** Benchmark + A + B genuinely run on **Weekly** Synthetic decision ticks, with identical per-tick PIT-qualified information, reproducible decision/action/cost/risk/performance traces, temporal negative tests and F3 evidence. **Monthly and Daily are explicitly non-mandatory** and may be shown as planned/unavailable until independent extension review. UI frequency selector or method extensibility alone is insufficient.

## 6. Proposed responsibilities of the existing seven M0 application DTOs

| Existing proposed DTO | Producer | F3/F5 extension or interpretation — NOT a schema amendment |
|---|---|---|
| DatasetManifest | F2/F4 | source and provenance, versioned content reference |
| SnapshotReference | F2 | cutoff, qualification/ref, exclusions; F3/F5 must not change status |
| ExperimentSpec | F3 | hypothesis/protocol/method/evaluation selection; proposed method/policy metadata subject to IF-02 review |
| ResearchRun | F3 | genuine execution state and typed failure |
| EvidenceBundle | F3 | recorded diagnostics/results, including referenced F5 method artifacts |
| DecisionTrace | F5 | cutoff-qualified observation/action vs later outcome |
| EvaluationResult | F5 | comparable benchmark/policy metrics, costs/risk and evidence references |

Candidate future types such as MethodSpec, MethodCapability, ValidationProtocol, ModelArtifact and PolicySpec are **conceptual only**. They are not approved fields, source modules, JSON schemas, HTTP routes or extra M0 DTOs. Changes require Lead/owner compatibility decision and a task-specific tested translator.

## 7. UX-driven acceptance trace

| UX acceptance need | Backend responsibility | Required future test |
|---|---|---|
| Research question and proper task family | F3 | hypothesis→protocol identity / unsupported-method refusal |
| PIT qualified snapshot and source reasons | F2/F4, F3 consumer | revision-too-late, missing/conflicting release, withheld preservation |
| Method / decision cadence suitability | F3/F5, F2 data boundary | unsupported Monthly/Daily until real implementation; small sample, invalid Weekly calendar/closure, immature label, invalid split |
| Actual run vs mock | F3/F5 and F6 client | mock scenario NOT_RUN vs genuine SUCCEEDED, typed failure |
| Evidence interprets question | F3 | diagnostics, uncertainty, unknown/negative result, no causal promotion |
| Benchmark / 2 policies / cost/risk | F5 | **Weekly** calendar, same eligible per-cutoff observations for each policy, post-decision labels only, deterministic costs/risk/action traces |
| Replay / source identity | F2/F3/F5 | seed/version/cutoff/manifest mismatch, IF-03 canonical identity oracle |
| UI display-only authority | F6 | no UI PIT or P&L calculations; all source refs and limitations retained |

These are **design acceptance cases, NOT_RUN**, and must be transformed into executable tests by separately authorized implementation tasks.

## 8. Open decisions and responsible gates

| ID | Needed decision | Gate |
|---|---|---|
| UX-D01 | Configurable frequency is the long-term product direction; **Weekly-only executable MVP**, Monthly optional next, Daily future. Multi-cutoff binding and Synthetic Temporal Environment detailed in UX-ADR-01; exact calendar/label/return rules need engineering decisions. | Owner/independent UX-ADR-01 design acceptance, IF-02 representation, IF-03 replay oracle before claims |
| UX-D02 | Specific genuine F3 statistical method and assumptions/diagnostics | F3-L1 planning and independent review |
| UX-D03 | Benchmark / Policy A / Policy B algorithms and prediction→action rule | F5-PLAN before M4 code |
| UX-D04 | Method capability metadata and whether/how to extend current ExperimentSpec / EvidenceBundle | IF-02 design and translator review before DTO code |
| UX-D05 | UI navigation/layout/fixture implementation and method availability display | F6-00 and separate F6-01/02 approval |
| Existing IF-03 | Canonical bytes, digest separation and replay oracle | before M1 identity/replay acceptance (target 2026-12-15) |
| Existing IF-04 | Actual ResearchClient transport | before F6-08 backend integration (target 2026-12-20 decision) |
| Existing IF-07 | Source access/use authority and time/version evidence | before real-source retrieval/intake and Historical PIT claims |

## 8A. P2 dispositions and F6 result presentation

**P2-02 — Minimal implementation permitted in a subsequent specifically authorized task:** bind experiment/run to versioned Weekly temporal settings and schedule/per-tick references, separate execution-instance run_id from deterministic experiment identity, invalidate stale result refs on frequency/calendar/cutoff/manifest/source/method/version/horizon/rebalance/seed change, preserve mismatch reasons and test negative cases. Do not invent hash equivalence prior to IF-03; do not mutate existing DTO fields prior to IF-02. **This PR implements no code.**

**P2-03 — Research-methodology analysis deferred:** repeated Monthly revenue features across Weekly decisions, overlapping subsequent-month targets, serial dependence and sample-size limitations must be shown now. Advanced dependence-aware estimators, effective-sample-size and overlapping-label inference are deferred to F3 research planning. The deferral does NOT waive future-label and preprocessing leakage protections or permit unsupported IID significance claims.

**F6 states:** (a) selectable but not currently executable method/cadence is shown SPEC_ONLY, UNAVAILABLE or BLOCKED_BY_INPUT (presentation-only labels), with reasons and disabled submission; (b) a genuinely SUCCEEDED ResearchRun whose hypothesis is unsupported/inconclusive remains SUCCEEDED on the execution axis with a **negative/inconclusive F3 evidence interpretation**, not FAILED nor PIT INELIGIBLE. Do not fabricate an authoritative verdict from UI metrics. Fixture simulation remains FIXTURE_ONLY / actual NOT_RUN.

## 9. Coding-agent task partition and stop conditions

**Recommended planning order:** (1) accept Weekly-first UX-ADR-01; (2) F3-L1 method/protocol planning and F5-PLAN Weekly-method/policy planning in parallel with F6-00; (3) review synthetic calendar, daily synthetic prices, monthly release event data and per-tick F2 qualification design; (4) approve named owners/reviewers and exact paths; (5) implement F2 synthetic→F3 genuine statistical slice and Weekly F5 Benchmark/A/B; (6) integrate F6. Monthly/Daily only after Weekly acceptance and separate scope authorization.

Required in each task packet: link to accepted M0 and this design revision **plus UX-ADR-01**, explicit Weekly MVP only, owner, reviewer, base SHA/branch, exact path allowlist, data mode, calendar/label/price/cost convention and IF-02/03 dependencies, interface version, negative-test matrix, statuses, limitations and STOP conditions. If F3/F5/F6 requirements conflict with M0, request an ADR, never silently rewrite the existing contract.

**Never activate/import** B04 dirty working-tree code, CTRL03, Layer B, PG17/TestLease/physical Harness, unauthorized real sources, or protected formal Golden files to complete an academic task. This document is not code, source/runtime review, repository merge, framework selection, real-source authorization or acceptance evidence.

**Status:** PROPOSED — final owner/independent review and merge required before this becomes a team implementation design anchor.
