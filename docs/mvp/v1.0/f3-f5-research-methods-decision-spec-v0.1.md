# Academic MVP — F3/F5 Research Methods & Decision Evaluation Reverse Design v0.1

- **Status:** PROPOSED / OWNER AND INDEPENDENT REVIEW REQUIRED / NOT IMPLEMENTATION AUTHORIZATION
- **Recorded:** 2026-11-07
- **Purpose:** Backward-design F3 and F5 from the [System UI/User Flow](system-ui-user-flow-spec-v0.1.md) without silently widening the accepted M0 MVP commitments.
- **UX-D01 Owner product direction (2026-11-07):** user-selectable Daily / Weekly / Monthly decision frequency. The three-cadence executable Synthetic MVP requirement is **proposed scope expansion pending Owner/independent change review**; frozen M0 AC-05 remains authoritative until then.
- **Normative references:** [Academic MVP Rebaseline](academic-mvp-rebaseline-v0.1.md), [Shared Interface Contract](shared-interface-contract-v0.1.md), [F6 Initialization](f6-application-ui-initialization-v0.1.md), [Workstreams](parallel-workstreams-v0.1.md). M0 RBL-01..12, AC-01..08, IF-01..07 remain unchanged.
- **Source basis:** Owner-supplied October 2026 draft “研究動機與目的 — 初稿”, §§1.1–1.5. Source positions the project as a research-first Financial Research Workbench with historical information evidence, hypothesis/method selection, experiment reproducibility and optional sequential decisions. This document is an engineering proposal, not a verbatim source transcription.

## 1. Stable mission and module ownership

**F3 — Research Design & Experimentation.** Own a falsifiable research question, hypothesis identity/version, target/feature and horizon definitions, experimental protocol, **decision-frequency configuration and its consistency with label maturity**, temporal validation design, statistical inference/diagnostics for the actual supported method, run orchestration and reproducible EvidenceBundle. F3 records limitations and unsupported conclusions.

**F5 — Research Methods, Model & Decision Evaluation.** Long-term expandable computational/evaluation family for statistical/ML/DL/RL methods and decision policies. Own method implementation and capability descriptors (where delegated), **method × decision-frequency support**, model fit/predict/evaluate, baseline comparisons, policy construction over the accepted decision schedule, action traces, trading-cost assumptions, portfolio/performance/risk metrics and method-specific evidence. F5 must not change F3's hypothesis or F2's PIT authority.

**MVP first instantiation:** Financial decision comparison in a small PIT-qualified TWSE-like synthetic research case. The existing Benchmark + two Policies, identical eligible information, action traces, costs/risk/performance remain mandatory under M0 AC-05. A simple supervised ML method is preferred if feasible, but **DL/RL are not mandatory**. F3's genuine statistical method is mandatory under AC-02; mock-only experiments do not qualify.

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

The attached research-draft §1.5 suggests daily data with weekly decisions; accepted M0 RBL-03 specifies monthly revenue and subsequent-month returns. They refer to **different temporal dimensions**, not two mutually exclusive product boundaries. Under the Owner-directed UX-D01, the interface offers Daily / Weekly / Monthly **decision frequency** independent of actual data observation frequency, target horizon, rebalance frequency and evaluation aggregation. Exact calendar and method implementation rules remain open. No PolicySpec or validated runtime schedule is implied.

## 3. Proposed M1 and M4 vertical slices

| Milestone | Scope | Acceptance evidence | Not accepted as substitute |
|---|---|---|---|
| **M1 by 2026-12-31** | F2 pinned synthetic observation + F3 versioned Hypothesis/Protocol + one genuine runnable statistical method + ResearchRun/EvidenceBundle | deterministic positive/negative synthetic examples, actual runner result, errors, reproducible identity after IF-03 review | descriptive UI metrics, hand-entered success, simulated statistical results |
| **M2 by 2027-01-31** | F6 actual backend submission/status/evidence rendering via separately approved IF-04 bridge | same protocol consumed end-to-end; no optimistic state promotion; browser/contract tests | FixtureResearchClient-only success |
| **M3 by 2027-02-28** | bounded real TWSE source and quality/availability viewer where independently authorized | source/time/version/rights limitations truthfully shown | current source bytes as Historical PIT proof |
| **M4 by 2027-03-31** | benchmark + two policies on identical qualified information; **proposed added UX-D01 scope:** executable Daily / Weekly / Monthly synthetic decision schedules | reproducible cost/risk/action evidence and negative cases; for added scope, test all three genuine schedules after acceptance | UI-only cadence selector, future-label leakage or unqualified information |
| **M5 by 2027-04-30** | stable demo and evidence/replay, negative paths, handoff | clean setup, real actual execution, replay proof as applicable | optional DL/RL or unreviewed extra UI features |

M0 AC-01..08 and formal CAP-F2 engineering gates retain their independent scope.

## 4. F3 MVP functional contract

1. **HypothesisSpec (conceptual, not new Shared DTO):** ID/version, user-facing question, measurable claims, universe/time/horizon, source qualification requirements and limits.
2. **ExperimentSpec (existing proposed M0 DTO):** link hypothesis/version to snapshot, method/version, evaluation plan, seed, temporal policy. The conceptual temporal configuration distinguishes data frequency, decision frequency, prediction horizon, rebalance frequency and evaluation aggregation; exact fields are **not approved without IF-02 review**. Reject incoherent schedules, post-cutoff features and outcomes used before maturity.
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

### A1. UX-D01 — Temporal Configuration & Cadence Capability

Frequency is a **user-selectable product feature**, while PIT eligibility at every scheduled decision time is an invariant. The configuration must not collapse these distinct dimensions:

1. **Data/source frequency:** actual observations, publication/version history and freshness; daily market prices do not imply daily fundamental-data releases.
2. **Decision frequency:** Daily / Weekly / Monthly trading-session decision schedules generated under one versioned market calendar and cutoff convention.
3. **Prediction horizon:** target interval and when its realized label becomes available; unavailable labels cannot be used as current features/training data.
4. **Rebalancing frequency:** when trades are allowed, which may differ from how often forecasts/decisions are produced.
5. **Evaluation frequency:** return/risk aggregation, comparison period and annualization conventions.

**F4** supplies authorized source coverage, true cadence, version/time information and calendar inputs. **F2** qualifies source/version at *each generated cutoff* and provides reasons, unknowns and withholding; a previously released monthly fundamental signal may be reused at a later daily cutoff, but a future release or revision cannot enter earlier decisions. **F3** fixes temporal protocol, generated schedule definition, valid train/test/label maturation rules and method suitability. **F5** implements method capability checks, policy actions and costs/risk/returns on the accepted schedule, with common eligible observations for benchmark/A/B. **F6** only displays selection, support/rejection reasons, evidence and results.

**Before implementation decide:** exchange calendar/version, holiday handling, weekly/monthly anchor and non-trading day roll, time zone and cutoff hour, source release effective-time, revision precedence, feature/label alignment, forecast horizon, execution-price convention, rebalance restrictions, cost assumptions and cross-frequency comparability. Unsupported method × frequency × mode combinations must explicitly be unavailable or blocked, not executed by fallback without user knowledge. Repeated unchanged monthly data used across daily decisions are correlated observations, not additional independent observations.

**Proposed Academic MVP added acceptance:** In synthetic mode, genuinely generate deterministic Daily, Weekly and Monthly decision schedules; for each cadence execute Benchmark + Policy A + Policy B over the same qualified information at each tick and produce reproducible action, risk, cost and performance evidence; test late publications, revisions, missing/withheld data, label immaturity, calendar edges and stale identities. Real-TWSE available frequencies depend on actual F4 coverage and F2 approved evidence; unavailable combinations are visibly blocked. Comparisons *between* cadences require explicit common universe, evaluation window, price/return units, costs, annualization and horizon rules.

**Governance:** This is a **scope-extension proposal beyond accepted M0 AC-05**, not implemented code, a proven runtime, an accepted DTO field, or immediate permission to broaden M4. Obtain Owner/independent acceptance of an ADR or scope amendment before committing three-cadence deliverables. Preserve original M0 AC-05 until then.

### B. Benchmark and two-policy case

- **Benchmark:** fixed stated default (e.g. an explicitly defined no-signal or eligible-universe reference); exact policy open as UX-D03.
- **Policy A:** pre-specified rule based only on cutoff-qualified observations.
- **Policy B:** feature/model-based rule on the same available observation set and trained without future leakage.
- **Same-information contract:** for each selected cadence, benchmark/A/B share universe, eligibility/withholding rules, **decision schedule and cutoff at each decision tick**, feature availability, rebalance calendar and evaluation horizon; if not met, comparison is blocked/non-comparable. Cross-frequency comparison separately states metric normalization, calendar and friction assumptions.
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

**F5 frozen M0 MVP acceptance:** Benchmark + A + B genuinely run using identical PIT-qualified synthetic information; action traces and costs/risk/performance are reproducible. **Proposed extra UX-D01 acceptance:** repeat genuine synthetic Benchmark + A + B execution at Daily / Weekly / Monthly configured schedules, with deterministic negative tests and truthful unsupported real-mode options. This is pending explicit scope review; UI selector or method extensibility alone is insufficient.

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
| Method / decision cadence suitability | F3/F5, F2 data boundary | small sample, wrong target, unsupported DL/RL or cadence pairing, invalid trading calendar, immature label, invalid split |
| Actual run vs mock | F3/F5 and F6 client | mock scenario NOT_RUN vs genuine SUCCEEDED, typed failure |
| Evidence interprets question | F3 | diagnostics, uncertainty, unknown/negative result, no causal promotion |
| Benchmark / 2 policies / cost/risk | F5 | same eligible observations at each decision tick, no future label, deterministic action/metrics; additional Daily/Weekly/Monthly synthetic cases require scope adoption |
| Replay / source identity | F2/F3/F5 | seed/version/cutoff/manifest mismatch, IF-03 canonical identity oracle |
| UI display-only authority | F6 | no UI PIT or P&L calculations; all source refs and limitations retained |

These are **design acceptance cases, NOT_RUN**, and must be transformed into executable tests by separately authorized implementation tasks.

## 8. Open decisions and responsible gates

| ID | Needed decision | Gate |
|---|---|---|
| UX-D01 | **Product direction accepted for proposal:** selectable Daily / Weekly / Monthly decision cadence; exact calendar, cutoff, source freshness, label maturity, rebalance schedule, metrics normalization and frequency support remain engineering decisions. Three-cadence runnable MVP requirement is a scope extension, not yet an accepted M0 amendment. | Owner/Lead scope ADR and F2/F3/F5 review before code |
| UX-D02 | Specific genuine F3 statistical method and assumptions/diagnostics | F3-L1 planning and independent review |
| UX-D03 | Benchmark / Policy A / Policy B algorithms and prediction→action rule | F5-PLAN before M4 code |
| UX-D04 | Method capability metadata and whether/how to extend current ExperimentSpec / EvidenceBundle | IF-02 design and translator review before DTO code |
| UX-D05 | UI navigation/layout/fixture implementation and method availability display | F6-00 and separate F6-01/02 approval |
| Existing IF-03 | Canonical bytes, digest separation and replay oracle | before M1 identity/replay acceptance (target 2026-12-15) |
| Existing IF-04 | Actual ResearchClient transport | before F6-08 backend integration (target 2026-12-20 decision) |
| Existing IF-07 | Source access/use authority and time/version evidence | before real-source retrieval/intake and Historical PIT claims |

## 9. Coding-agent task partition and stop conditions

**Recommended planning order:** (1) cross-module UX review/adjudication; (2) F3-L1 method/protocol planning and F5-PLAN method/policy planning in parallel with F6-00; (3) approve named owners/reviewers and explicit contract/paths; (4) implement small F2 synthetic→F3 statistical slice; (5) add F5 benchmark/A/B and F6 integration under separate approvals.

Required in each task packet: link to accepted M0 and this *reviewed* design revision, owner, reviewer, base SHA/branch, exact path allowlist, accepted data mode, interface version, negative-test matrix, statuses, limitations and STOP conditions. If F3/F5/F6 requirements conflict with M0, request an ADR, never silently rewrite the existing contract.

**Never activate/import** B04 dirty working-tree code, CTRL03, Layer B, PG17/TestLease/physical Harness, unauthorized real sources, or protected formal Golden files to complete an academic task. This document is not code, source/runtime review, repository merge, framework selection, real-source authorization or acceptance evidence.

**Status:** PROPOSED — final owner/independent review and merge required before this becomes a team implementation design anchor.
