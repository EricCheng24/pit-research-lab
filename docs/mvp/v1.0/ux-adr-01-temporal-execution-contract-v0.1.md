# UX-ADR-01 — Weekly-first Temporal Execution & Frequency Scope v0.1

- **Recorded:** 2026-11-07
- **Status:** OWNER-DIRECTED PROPOSAL / INDEPENDENT REVIEW PENDING / DOCS ONLY
- **Purpose:** Address PR #13 Design Review P1-01, P1-02, P1-03 with a generic temporal contract but a single required executable MVP cadence.
- **Related:** [System UI / User Flow](system-ui-user-flow-spec-v0.1.md); [F3/F5 Reverse Design](f3-f5-research-methods-decision-spec-v0.1.md); [M0 Rebaseline](academic-mvp-rebaseline-v0.1.md); [M0 Shared Interface](shared-interface-contract-v0.1.md).
- **Compatibility:** M0 RBL-01..12, AC-01..08 and IF-01..07 remain frozen. This is additive design guidance, NOT a new accepted schema, physical authority, implemented runtime, or F2/B04 release.

## 1. P1-01 — Scope adjudication

**Product architecture:** Decision Frequency is configurable; the general engine may eventually support Weekly, Monthly and Daily schedules independently of data/source frequency, prediction horizon, rebalancing cadence and evaluation aggregation.

**Academic MVP minimum:** **WEEKLY** is the **only required executable decision frequency** in Synthetic Mode. Existing M0 AC-05 stays mandatory: Benchmark + two Policies, identical PIT-qualified information, action traces, transaction costs, risk/performance and reproducible evidence. Monthly revenue features and subsequent-period return remain the primary example; weekly decisions do not redefine target horizon.

**Extension order:** (1) Weekly required, implementation and acceptance still pending; (2) Monthly optional when capacity allows and Weekly has passed acceptance, separately reviewed; (3) Daily optional only after Monthly readiness and separate review. **The MVP frequency selector needs only Weekly as an enabled choice**; Monthly/Daily may appear as non-interactive roadmap information but must NOT be labeled EXECUTABLE or offered as runnable choices unless the exact method+mode+frequency is confirmed by an accepted backend. No three-cadence execution claim is required for M4 or M5.

**Milestones unchanged:** M1 (2026-12-31) genuine F2 synthetic → F3 statistical experiment → evidence; M2 (2027-01-31) genuine UI→backend run; M4 (2027-03-31) **Weekly** Benchmark/A/B comparison; M5 (2027-04-30) feature freeze. Optional frequencies must not displace PIT correctness, actual F3 run, AC-05 or M0 safety gates.

**Scope fallback:** defer Monthly, then Daily, then optional ML/DL/RL and UI polish if time is insufficient. Do not cut eligibility rules, same-information-set invariants, source identity, or evidence. This is a product scope choice to be confirmed in the final PR design adjudication, not a silent M0 rewrite.

## 2. Five orthogonal temporal concepts

1. **Data/source frequency:** actual observation and release cadence (e.g., daily price, monthly revenue), with publication, version and observation timestamps.
2. **Decision frequency:** candidate schedule of decision timestamps; Weekly first.
3. **Prediction horizon:** target interval and its later observation/maturity time; never a decision-time feature before availability.
4. **Rebalance frequency:** when trading/holdings may change; may differ from decision frequency.
5. **Evaluation frequency:** aggregation and annualization policy for metrics and common comparison window.

The calendar version, time zone, cutoff convention, price/execution convention, source freshness, validation windows and method capability must be explicit and versioned rather than inferred by UI.

## 3. P1-02 — Multi-cutoff logical binding

**Gap:** Existing proposed M0 ExperimentSpec has one snapshot_id, while a SnapshotReference covers one decision_cutoff. Weekly decision comparison has multiple cutoffs and therefore cannot claim full PIT evidence from one snapshot ID.

**Conceptual, not an approved DTO/API:**
- TemporalConfiguration: source-cadence references, Weekly/Monthly/Daily decision cadence, prediction horizon, rebalance/evaluation rules, calendar/version, time zone, cutoff, anchor, holiday-roll, execution/cost conventions.
- DecisionSchedule: ordered trading-session cutoffs t0 < t1 < ... < tn, schedule identity and calendar/protocol reference.
- PerDecisionBinding: each tick links its cutoff to an F2-qualified SnapshotReference / qualification trace, manifest/source/version identity, observed feature reference, exact decision reasons, including missing/UNRESOLVED/WITHHELD.
- TemporalEvaluationContext: versioned reference relating ExperimentSpec, pinned manifest, temporal config, ordered cutoffs, per-tick bindings, Method/Policy IDs, target maturity and F3/F5 evidence.

~~~text
F3 Hypothesis/ExperimentSpec + F2/F4 manifest
    -> reviewed TemporalConfiguration + DecisionSchedule
    -> for each t_k: F2 independently qualifies source/version at t_k
    -> I(t_k) shared by F5 Benchmark + A + B or explicit blocked/abstain
    -> F3 ResearchRun/EvidenceBundle with F5 DecisionTrace/EvaluationResult
    -> F6 read-only evidence/status/replay presentation
~~~

**IF-02 hard gate:** The representation could be a compatible temporal_policy reference, a composite snapshot reference or a separate versioned sidecar; choose only after review of existing M0 DTOs and adapter semantics. Do not create a new accepted field/DTO by writing this ADR. One manifest ID or a single PIT-positive source cannot prove all cutoffs. Every comparison must have identical admissible information at each tick; native F2 refusal/withholding/unknown reasons remain intact.

## 4. P1-03 — Weekly Synthetic Temporal Data & Execution

A dataset consisting only of monthly revenue rows is **insufficient** for reproducible Weekly costs/return/risk computation. The bounded synthetic test pack must define:

- **Market calendar:** fixed coverage and version; working/non-trading sessions, holidays/closures, local time zone (candidate Asia/Taipei); weekly anchor and holiday roll.
- **Daily synthetic prices / execution basis:** issuer and session-indexed prices with sufficient coverage for action execution, outcome calculation and risk/performance metrics. Explicit choice of open/close/reference price and its availability time.
- **Monthly synthetic revenue event log:** accounting period, original public release time, post-release revisions and effective time, observation/ingestion basis if modeled, issuer/version/manifest/source IDs, withheld/missing/conflict/late examples.
- **Targets and labels:** subsequent-period return horizon, maturity and time when values can enter training/evaluation; overlapping labels may not enter decision-time features.
- **Policy evaluation:** same qualified universe/decision tick/feature projection for Benchmark/A/B, explicit abstain handling, execution timing, cost/risk/return conventions, deterministic inputs/seed and limitations.

**Candidate first Weekly default (requires F2/F3/F5 review before code):** decisions occur after the last trading session of each calendar week under one stated local cutoff time; possible trades use a separately defined next-session executable price. A week with holidays must follow a stable calendar/roll rule. The monthly fundamental signal remains the most recent **qualified** version at each cutoff, not a fabricated weekly update. The exact clock, price type, first/last session and missing-input rule remain planning decisions.

**Weekly future acceptance cases — specified, NOT_RUN:**
- W01: pinned calendar generates a deterministic Weekly schedule with closure handling.
- W02: after-cutoff revenue and later revisions never appear in earlier qualified observations.
- W03: execution/outcome price information cannot leak into the earlier decision input.
- W04: immature targets are excluded from model training and indicated in evidence.
- W05: Benchmark/A/B share identical information references at every decision tick; action/cost/risk/return metrics are reproducible.
- W06: calendar/cutoff/frequency/manifest/horizon/method/seed changes invalidate stale identity/evidence and replay until reviewed.
- W07: Monthly/Daily unavailable or unsupported mode/method selections are explicitly blocked; no fake Weekly fallback.
- W08: native WITHHELD/UNRESOLVED reasons and mock FIXTURE_ONLY actual NOT_RUN are preserved.

Monthly and Daily require their own tests only when subsequently approved. Real TWSE availability is separately gated by source coverage, historical time/version evidence and IF-07 authority.

## 5. P2-02 — Minimal run/config identity follow-on

**Minimal implementation is planned for a separate approved coding task; no source changes in this docs-only PR.**

- Bind each experimental run to an immutable or versioned config/schedule reference plus source/qualification refs, while distinguishing run_id (execution attempt) from deterministic experiment identity.
- On a change to cadence, calendar/version, cutoff, manifest/source/version, per-decision qualification, horizon, rebalance, method/version, policy or seed, invalidate previously attached results/replay and preserve structured mismatch reason.
- Add tests for same-reference consistency and modified-critical-field invalidation. Do not claim content digest equivalence or cryptographic replay proof until **IF-03** canonicalization/domain-separated hashes/replay oracle are approved.
- Use an IF-02-approved adapter/reference mapping; never silently modify frozen seven DTOs.

## 6. P2-03 — Statistical dependence limitation, deferred deeper analysis

Weekly decisions may repeatedly reuse monthly revenue signals; subsequent-month targets may overlap across weekly decisions. These are **not independent sample enlargements**. Record limitations and minimum anti-leakage checks now; detailed HAC/cluster estimators, overlap-aware cross-validation and effective sample size research are **DEFERRED to F3 methodology planning**.

Deferral never permits post-cutoff labels, preprocessing leakage or false IID significance claims. If the experiment completes but inference is weak/inconclusive, show that as a research conclusion separately from execution status.

## 7. Two required F6 presentation states

1. **Selectable method/frequency but not executable:** Show mode/method/cadence, supported status and reason; SPEC_ONLY, UNAVAILABLE and BLOCKED_BY_INPUT are descriptive **UI presentation labels**, NOT new M0 enums. Disable submission or refuse gracefully. In Weekly MVP, Monthly and Daily are visibly planned/unavailable until genuine backend support.
2. **Actual ResearchRun SUCCEEDED but hypothesis unsupported:** Show genuine execution status SUCCEEDED, unchanged PIT/evidence status and the F3-provided metrics/diagnostics/limitations showing lack of support or inconclusive findings. Do not turn negative research evidence into FAILED, PIT INELIGIBLE, causal proof or an investment recommendation. Mock success scenarios remain FIXTURE_ONLY and actual NOT_RUN.

No UI-side authoritative interpretation or reclassification; preserve evidence references and source uncertainty.

## 8. Adoption and review

- **P1-01:** Weekly-only executable MVP; Monthly then Daily as separately accepted extensions.
- **P1-02:** general sequence/cutoff model and explicit IF-02 representation decision.
- **P1-03:** minimum synthetic calendar, daily prices, monthly revenue releases/versions and Weekly acceptance matrix.
- **P2-02:** minimal change-detection/identity requirements recorded for a later approved task, IF-03 still mandatory for hashes.
- **P2-03:** methodological dependence caveat documented; advanced inference deferred.
- **F6:** unsupported capability and successfully executed but not-supported hypothesis are explicitly different.

This ADR is an **implementation design anchor proposal only**. No claim of actual executed research, accepted canonical hash, live API, real-source rights, B04 physical release, or team coding authorization. The PR requires Owner/independent review before final freeze or merge.
