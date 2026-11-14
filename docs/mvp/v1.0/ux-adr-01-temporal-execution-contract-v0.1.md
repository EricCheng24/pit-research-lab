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

**Scope fallback:** defer Daily first, then Monthly; preserve Weekly, then optional ML/DL/RL and UI polish if time is insufficient. Do not cut eligibility rules, same-information-set invariants, source identity, or evidence. This is a product scope choice to be confirmed in the final PR design adjudication, not a silent M0 rewrite.

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

## MVP-IF-02-IF-03-ADOPT-01 — P1-02/P1-03 proposed follow-on v0.1

**PROPOSED_FOR_OWNER_ADOPTION / INDEPENDENT_REVIEW_PENDING / DOCS ONLY.** This is OWNER_DIRECTED_CANDIDATE, not signed adoption. All eleven decisions and linked subdecisions remain CANDIDATE_FOR_OWNER_RATIFICATION, receipts NOT_SUPPLIED. Original P1-01/02/03, P2 history, status lines and references above remain verbatim. Historical references to frozen M0 requirements preserve earlier constraints; they do not prove IF-02/03 adoption. See the [shared contract ADOPT-01 addendum](shared-interface-contract-v0.1.md#mvp-if-02-if-03-adopt-01--proposed-normative-addendum-v01), AD01-01..12, for the self-contained candidate field/status/byte/refusal register and Owner decisions.

Weekly remains the only required executable Synthetic MVP priority; Monthly/Daily are optional, unavailable until separate genuine backend acceptance. This statement does not claim that WU04 itself is a runnable F3/F5 research/policy path. Source/data cadence, decision cadence, prediction horizon, rebalance and evaluation aggregation remain five independent dimensions. F2 owns source/calendar/qualification evidence, F3 owns horizon/training/label maturity and experiment association, F5 owns action/execution-price/cost/outcome conventions, F6 displays authorized views. A cadence selection cannot certify data freshness or method support.

P1-02 draft representation is Sidecar-first (IF02-OD01), preserving explicit composite/DTO-extension alternatives. F2 independently issues each cutoff's source/version/qualification and detached strict observation refs, plus ordered TemporalBindingSet/PerCutoffBinding. F3 issues ExperimentSequenceBinding with explicit kind EXPERIMENT_SEQUENCE_BINDING, contract version, typed experiment/sequence/protocol refs, temporal_input_kind=SEQUENCE, approval/author provenance and reader capability contract. Association truth belongs to F3; it grants no source qualification. CONTRACT_ONLY / NO_PORT: logical discovery is an F3-owned exact-key registry requiring one current authorized association. Reader must negotiate exact SEQUENCE/schema/profile/rights support and legacy_fallback=false. Missing/legacy/unknown-version reader refuses REF_LEGACY_SINGLE_CUTOFF / REF_UNSUPPORTED_VERSION; transport stays IF-04 DEFERRED. Existing ResearchClient methods and seven proposed DTO schemas remain unchanged.

snapshot_id remains single-cutoff. Never use t1 as sequence, dummy aggregate/composite alias or implicit temporal_policy escape hatch. F3 experiment hashes sequence + association CONTRACT VERSION, then association points to sealed experiment; no experiment-to-association INSTANCE backedge. Missing/duplicate/stale/foreign/wrong-order/context mismatches fail closed. Private audit resolver access requires a distinct authorized audit principal; policy-consumable views omit private locator/Native graph/full pack/future grid/callbacks. Same-capability opaque audit resolution explicitly fails REF_AUDIT_CAPABILITY_LEAK. Current resolver/capability enforcement is NOT_IMPLEMENTED / IF-04_OR_CAPABILITY_GATE.

P1-03 bounded WU04 illustration at fixed source d693b11ce649802df9fc13248c343203a09ff397: four 672-byte SECOND requests at 2027-01-07, 01-15, 01-29, 02-05 18:00:00+08:00; December D1/D2/D2/D3; Native A04 140/150/150/130 and A05 0.714286/0.733333/0.733333/0.692308. These are accepted-scope diagnostic facts/committed assertions, NOT_RUN here, not admitted per-tick App eligibility. W03 2027-W03 is NO_SESSION_WEEK annotation, never fifth tick. D2 equal to t1 cutoff is not before it; D3 published t3+1 second cannot enter t3. t2/t3 equal feature values/source revision retain distinct context/qualification/observation identities. WU01 SYN-A/SYN-B request roster is not independently qualified two-issuer Weekly universe. B03 MD1 2027-01-08T00:00:00+08:00 is distinct local midnight and cannot substitute for Weekly 18:00 evidence. Sources: weekly_sequence.py L63–L75/L339–L380/L405–L423/L514–L525; test_weekly_sequence.py L38–L42/L295–L382; causal_derivation.py L622–L631, all paths under the exact fixed source inventory.

All scheduled positions remain accounted, including original unknown/withheld/first typed failure and actual RUN/ATTEMPTED/NOT_RUN receipts. A partial failed sequence cannot drop/refill/reorder positions or release an all-qualified claim; count completion is not admission. Generic candidate schedules can have 1..4096 ticks; exactly four is this case only. Corrected source/calendar/manifest/context/code/projection/privacy policy invalidates affected refs; no stale replay reuse or source alias fallback. App PIT defaults UNRESOLVED absent independent tested positive predicate; applicable stronger WITHHELD persists, successful A04/A05 never gets a fabricated Native WITHHELD state. Explicit INELIGIBLE needs a separate negative predicate. Execution/evidence/PIT axes stay independent, and fixtures retain FIXTURE_ONLY / actual NOT_RUN.

Same-information Benchmark/A/B remains future F5 acceptance: identical independently admitted per-cutoff observation refs, separately approved IF-05 predicates, F3 label/training maturity and F5 price/action/cost/evaluation protocol. Mere sequence existence, equal values or four Native RUNs supply none of those. Future prices/labels/returns are EVALUATION-ONLY; no preprocessing or immature-label leakage. Repeated monthly signals/overlapping Weekly targets do not create independent statistical samples; F3 methodology owns limitations.

IF-03 remains blocking before canonical/replay acceptance. Proposed typed-json-candidate-v0.1 preserves original timestamp declaration/zone/precision/origin separately from UTC comparison, strict typed numbers and ordered ticks. CanonicalPayload excludes its own ReferenceEnvelope; canonical_profile_version participates inside payload, with u64be length-prefixed domain/schema/payload frame. Typed parents are acyclic; unknown domain/schema/profile or dangling/unauthorized evidence refuses. No current WU01/A04/A05/B03 hash is silently reused. No new canonical digest/codec/vector is created. Independent author/reviewer, complete independently checked payload/frame/digest vectors and separately authorized oracle freeze precede implementation and genuine two-channel replay.

Owner and independent review/closure remain required before any normative freeze; current outcome can only be document draft ready for review. IF-04/06 transport/fixtures/F6, IF-05 predicates, IF-07 source authority, F3 research lifecycle and F5 policy/evaluation are separate gates. RBL-01/05/07 Formal CAP-F2/B04/Layer B/PG17/TestLease no-go boundaries unchanged. No source code, fixture, test, runtime, schema implementation, new endpoint, commit, push or PR is authorized by this appendix.

## MVP-IF-02-IF-03-RATIFY-01 — Owner ratification follow-on v0.1

**OWNER_RATIFIED_DOCS_ONLY_REVIEW_PENDING.** The current user, expressly acting as PIT Research Lab Academic MVP Owner, directly approved all eleven parent decisions and seven linked subdecisions as EXACT against shared draft SHA-256 `32ae716c234549c636d4c9a2479835b9caa9f39a721a4f055dc9268a2b99060d` (123536 bytes) and this UX draft SHA-256 `5919314a94b9962d7c23ebb4308d72b2e6ce51b9645bf97f05eab8196ea41ce3` (18779 bytes). Receipt catalog `OWNER-RATIFY01-20261114-01` identifies that actual direct message, not an external signature service. Full scope/individual rows/approval excerpt and message integrity pin are in shared contract RT01-01..05. Message-date context is 2026-11-14 / Asia/Taipei, DAY precision; exact approval clock was not supplied or invented. The Owner explicitly requires no repeat form/signoff.

All eleven parents IF02-OD01..05, IF03-OD01..05, IF23-OD01 and all seven children IF02-OD03-S1, IF02-OD05-S1, IF03-OD01-S1/S2, IF03-OD02-S1, IF03-OD03-S1/S2 are individually Owner RATIFIED_EXACT. Parent approval does not imply child; this receipt explicitly covers each. No F2/F3/F5/F6 or independent reviewer signature/appointment is implied. Entire historical 107-line prefix and approved ADOPT-01 appendix remain byte-preserved; their candidate/pending statements are historical stages, not retroactively rewritten.

Owner adopts IF-02 Sidecar-first logical architecture with individually evidenced F2 per-cutoff qualification/observation, explicit F3-owned ExperimentSequenceBinding/discovery and exact reader compatibility refusal, no snapshot_id/t1/aggregate/temporal_policy fallback, and distinct audit/policy capabilities. These are design contracts, CONTRACT_ONLY / NO_PORT, not an implemented resolver, endpoint, DTO, admitted SnapshotReference or runner. Same-capability audit resolution is a failure even for an opaque locator. F3 owns protocol/horizon/training/label maturity; F5 owns policy/action/price/cost/outcome; F6 displays safe authorized records only. Five temporal dimensions remain independent. Weekly priority is unchanged; Monthly/Daily are not silently enabled.

Owner adopts the exact declared IF-03 scalar/framing rules and bounds in CAN-01..10 and linked numeric/time/reference children; profile literal typed-json-candidate-v0.1 and all approved domain/schema literals remain unchanged. Original time declaration/zone/offset/precision/origin are evidence distinct from derived UTC comparison; pinned zone rules required. LP64BE frames domain/schema/canonical-payload bytes; profile is inside payload, own envelope/digest outside; typed parents are acyclic; experiment binds sequence plus association CONTRACT VERSION before association points to sealed experiment. Approval of these rules is not adoption of missing Resource body schemas or expected digest vectors. Full scope map is shared RT01-03..04.

Four WU04 SYN-A ticks/D1-D2-D2-D3/140-150-150-130/six-decimal ratios and W03 annotation remain diagnostic-only, not per-tick App eligibility; t2/t3 equal values retain distinct contexts. D2 AT t1 and D3 t3+1s remain excluded by the existing exact Native publication path. B03 midnight cannot replace Weekly 18:00. Unknown/withheld/first failure/actual invocation and positional accounting survive; partial failure blocks all-qualified release. Source content integrity, qualification and observation release are separate; PIT/execution/evidence axes and no-promotion rules are unchanged. WU04 flags remain diagnostic_only=True, admission_eligible=False, NOT_TRUSTED_PIT_EVIDENCE, source_authentication=NOT_ESTABLISHED, INTEGRATED_PROVISIONAL.

Independent post-ratification review and applicable other-role signoffs remain PENDING. Domain Resource schemas/identity issuance, Independent Golden Oracle/vectors/freeze, genuine Channel A/B replay/Codec, IF-05 translator/positive and explicit negative predicates, IF-04 transport/capability enforcement, actual F3/F5 methods/label maturity/same-info policy execution/returns/F6 UI, IF-07 source rights/history and Formal CAP-F2 physical authority remain blocked or out of scope as recorded in shared RT01-04. No Oracle author/reviewer is appointed by this message. Future evaluation prices/labels remain outside decision input. No global boundary freeze or tested runtime acceptance is self-declared.

Next deliver actual RATIFY-01 deltas plus direct Owner evidence to Independent Review. Only after applicable review/closure and separate authorization may Independent Golden Oracle Authoring planning/execution begin. No codec, binder, policy/agent/F3/F5/F6 implementation or Git integration is authorized. No source/tests/fixtures/CI/dependency/runtime change occurs in this docs-only step.
