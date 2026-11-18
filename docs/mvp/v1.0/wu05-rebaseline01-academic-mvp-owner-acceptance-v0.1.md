# MVP-F2-WU05-REBASELINE-01 — Academic MVP Research-Critical Scope Acceptance v0.1

**Project:** Academic PIT Research Lab — Sequential Decision and Agent Evaluation Environment  
**Task:** `MVP-F2-WU05-REBASELINE-01`  
**Decision date:** 2026-11-18 (Asia/Taipei)  
**Baseline:** `EricCheng24/pit-research-lab` `main` commit `5f2d5711af48de61862d4ea97da8b8b17f78a3e3` (RATIFY01 PR #31)  
**Authority:** Explicit Academic Project Owner authorization in this conversation to record the revised Academic MVP scope and its acceptance requirements. This records the **scope decision**, not specialist sign-offs, CI results, production fitness, or implementation acceptance.  
**Owner scope decision:** `ACADEMIC_MVP_REBASELINE_SCOPE_OWNER_ACCEPTED`  
**Repository integration state on issuance:** `PENDING_MAINLINE_INTEGRATION`  
**Research-system functional acceptance:** `NOT_YET_ACCEPTED`

## 1. Binding scope decision

The Academic MVP shall optimize for **research correctness and executable evidence**, not full resource issuance governance. The target research question is: *Can a sequential decision environment ensure that each agent acts only on information demonstrably available at that decision time, and can the resulting behavior and evaluation be reproducibly compared?*

The former Scheme B **Full Functional WU05 Closure** is **removed from the Academic MVP critical path**, but **not completed, waived as a historical claim, or retroactively accepted**. It remains an archived, optionally resumable enhanced-governance track. A scope change affects **future MVP acceptance criteria only**; it does not rewrite immutable evidence, previous Owner/Independent Review verdicts, originally ratified interface contracts, or existing system assertions.

**Operative status register:**

| Status key | Decision value | Interpretation |
|---|---|---|
| `ORIGINAL_SCHEME_B_FULL_CLOSURE` | `NOT_COMPLETED` | Original WU05 full resource governance obligations remain historically unsatisfied. |
| `ACADEMIC_MVP_REBASELINE_SCOPE` | `OWNER_ACCEPTED` | The revised academic acceptance scope is authorized by Project Owner. |
| `ACADEMIC_MVP_REBASELINE_REPO_INTEGRATION` | `PENDING` | Until reviewed/merged on GitHub, the acceptance record is not a Mainline fact. |
| `S1_RATIFIED_FIVE_SCHEMAS` | `0_OF_5` | No retroactive S1 schema semantic ratification. |
| `ACADEMIC_MVP_RESEARCH_CAPABILITIES` | `NOT_YET_VERIFIED` | No claim that six research capabilities are implemented/accepted. |
| `RSF02_S1_EVIDENCE01` | `REMOVED_FROM_MVP_CRITICAL_PATH` | Prior full-governance evidence acquisition is not required to start the research runtime. |
| `S2_S5_RESOURCE_ISSUANCE` | `DEFERRED_FOR_ACADEMIC_MVP` | Full body issuance, grants and cross-owner sign-off are not MVP gates; old modules remain fail-closed. |
| `FORMAL_CAP_F2` / `SURVIVOR_OS` | `UNCHANGED_OUT_OF_SCOPE` | No promotion, modification, or authority transfer. |

**Acceptance of this rebaseline is not acceptance of the system.** No `SCHEMA_SEMANTICS_ADOPTED`, `RESOURCE_ISSUED`, `RIGHTS_GRANTED`, `PIT_ADMITTED`, `NATIVE_REPLAY_ACCEPTED`, or `WU05_FULL_CLOSURE` flag is created or set.

## 2. Six research-critical acceptance capabilities

| ID | Capability | Minimum engineering outcome | Falsifiable acceptance evidence |
|---|---|---|---|
| `RC-01` | **PIT Data Foundation** | An immutable, source/version-attributed *as-of* dataset view reconstructs data known strictly before a cutoff; original publication/availability and revisions are preserved. | Unit/integration tests on original publication, version correction, equal-to-cutoff exclusion, missing source and independently checked source hashes; no latest-version overwrite. |
| `RC-02` | **Temporal Leakage Control** | Observations, training features and train-time labels never include post-cutoff or immature information; withheld/unknown data cannot silently become known. | Executed before/at/after, label-maturity, future-revision, feature fitting, delayed-outcome and mutation/poison tests. Negative cases MUST fail closed and be observable without disclosing private source data. |
| `RC-03` | **Sequential Decision Environment** | A callable episode API supports `reset → observe → action → transition → log`, fixed clock progression, action validation, and state separation between agents/episodes. | Executable step/episode tests, invalid-action refusal, fixed-four SYN-A trace and inspection proving action cannot request future observations or rewrite historical facts. |
| `RC-04` | **Deterministic Replay** | A pinned deterministic reference episode reproduces ordered observation/action/event traces under identical input bytes, code, configuration and seed, including from a fresh independent process. | Two clean-process replays with identical canonical *research trace* hashes; explicit seed/environment/version/data manifests and mutation sensitivity. For inherently nondeterministic accelerator/model runs, report limits and prespecified metric tolerances, not a false byte-identity claim. |
| `RC-05` | **Agent Benchmark Fairness** | Agents share the same decision clock, observation-availability policy, action semantics, cost assumptions and sealed evaluation windows. Initial vertical slice may use two agents; final research benchmark includes four defined classes. | Contract tests comparing information masks and cutoff traces, baseline vs learned agent in vertical slice, and four-class reproducible benchmark at final acceptance; training methods may differ but access to unavailable data may not. |
| `RC-06` | **Evaluation & Diagnostics** | Walk-forward/out-of-sample assessment uses only mature labels and declared execution/price/cost rules; logs errors, abstentions, leakage events and robustness. | Reproducible metrics/report with splits, horizon/maturity, costs, seeds, baseline, failures and regime/window slices; assertions against hindsight, overlapping misuse and selective result omission. |

### Staged acceptance — no premature full-MVP claim

**Stage V — Test-first research vertical slice (the next engineering target):** fixed-four SYN-A cutoffs (2027-01-07, 01-15, 01-29 and 02-05 at 18:00:00+08:00); original D1 at `2027-01-07T17:59:59+08:00`, D2 at the first cutoff exactly, and D3 at `2027-01-29T18:00:01+08:00`; W03 no-session is annotation-only, not a fifth tick. Require strict `publication_time < decision_cutoff` for this bounded fixture, revision isolation, no lookahead, fail-closed unknown/withheld, minimal `reset/step`, at least one deterministic baseline and one learned/rule-based comparator, and two process-separated deterministic trace replays. Stage V acceptance is **not** final six-capability MVP acceptance.

**Stage M — Final research MVP:** pass all six `RC-*` executable gates, run the four-class benchmark under the same observation contract, record leakage-negative controls and reproducible evaluation. Any claim of real TWSE empirical validation requires actual TWSE dataset provenance, legally permitted use, original publication/availability and revision semantics, and independently examined dataset splits. SYN-A success alone must be labeled **synthetic demonstration**.

### Required controls, not optional bureaucracy

- Unknown, NotEvaluated, Withheld, absent, and later-arriving facts remain distinct. Never convert a later outcome into a contemporaneous observation.
- Strict publication-before-cutoff semantics govern the current SYN-A fixtures. Changes to clock/availability policy must be explicit, versioned, and accompanied by failing-edge tests.
- Versioned input data, code commit, config, feature definitions, splits, agent artifacts, seeds, evaluation costs and outputs are recorded. No proof-by-label.
- CI and a separate technical review assess **executed** tests and research behavior. An authored test plan or a docs-only PR cannot pass the research runtime gate.
- A new lightweight research-runtime API/record can be added if it is named distinctly from legacy unissued ResourceRefs. It may not impersonate an IF03-registered resource or issue/access-resolve protected data.
- If a chosen test actually consumes a Native-derived result or claims Native equivalence, corresponding original attempt/equivalence evidence is mandatory *for that claim*; otherwise use documented synthetic fixtures and do not claim real Native provenance.
- Genuine external TWSE rights, dataset authenticity and timestamp proof are mandatory when applicable to the actual dataset used; not every synthetic fixture needs an external issuer.

## 3. Historic Resource Governance disposition

This rebaseline changes **critical-path dependency**, not the existence of any original contract:

| Legacy item | Revised Academic MVP treatment |
|---|---|
| IF03 Canonical Profile / Typed References | Preserve frozen assertions and tests. If the research path uses IF03, comply exactly; otherwise use a **separately named** minimal research format, with no issuance/registration claims. |
| WU04 fixed-four SYN-A | Required controlled clock/leakage/replay fixture in Stage V. |
| WU05-RS 17 Draft Schema Bodies | Retain byte-for-byte as `0.1-DRAFT-NON_ISSUED`; no requirement to ratify all before research implementation. |
| Original 40 Resource Roles / 21 `REQUIRED` roles | Preserve old taxonomy and its original meaning **inside the old Full Functional WU05 contract**; new acceptance maps role *concepts* to six research capabilities without requiring 40 issued Resource Bodies. Companion matrix maps all 40 exactly. |
| ORACLE-02 / CAN01–03 | Frozen scoped positives, negatives and diagnostic relations remain as previously accepted. No new all-domain or Native success claim. |
| RSF02-D / RSF02-S1 / RATIFY01 | Retain as source-backed semantic design/risks; pending owner or expert proof does not block a distinct minimal research-runtime implementation. |
| S0–S5 Owner/Reviewer/Rights/Issuer resource governance | Deferred for the old Scheme B track; do **not** mark any old gate accepted or turn off fail-closed guards. |
| IF04/IF05 access/disclosure service | Full live authorization infrastructure deferred; ensure academic research API cannot leak private/audit fields or bypass existing default DENIED/WITHHELD behavior. |
| G04 Native, F01 WITHHELD view, F02 Draft Text, F04 fixed-four, G09 depth64/65, G10 readiness wording | Preserve historical open/selected/deferred states. Address an issue only if it demonstrably blocks a required new research behavior, with bounded compatible change and tests. |
| RSF03/Full-domain Oracle/Resource Binding/Issuance work | Off Academic MVP critical path; may resume as a separately authorized enhanced-governance initiative. |

The 40-role mapping is a **planning crosswalk**, not 40 new mandatory validation rules, and may not silently mutate an existing role definition. No action on other protected repositories, environments, systems or datasets is authorized.

## 4. Explicit acceptance and conflict rules

1. **Project Owner scope acceptance is completed by this decision record**. No further five-schema Owner approval is required as a prerequisite to *starting* Stage V research implementation. This does **not** claim those five legacy Schemas are now ratified.
2. **Mainline integration** requires source review, a docs-only diff, successful applicable CI, and a clean PR merge. It shall be reported separately from Owner acceptance and separately from functional acceptance.
3. **Research functional acceptance** requires code and executed test evidence satisfying the relevant Stage V/M criteria. It may not be automatically granted by this document or by CI of a docs-only branch.
4. Where a minimal research contract conflicts with a currently ratified interface or frozen test, preserve the old contract and give the research runtime a separate boundary. Do not relax existing validators, source/trust controls, status guards, fixture locks, or Golden bytes to make the research API pass.
5. Preserve historical statuses: the old Scheme B is **NOT_COMPLETED**; earlier S1 Ratification still **0/5**; PR #24–31 prior independently reviewed/merged documents remain historically accepted *for their original scope only*.
6. Limit future documentation to the minimum needed for reproducible tests and results. No new serial ratification packets or per-resource approval rounds are on the MVP critical path.

## 5. Immediate executable successor, acceptance and stop conditions

**Next work unit after this record is integrated:** `MVP-F2-WU05-RESEARCH-VSLICE-01 — Temporal Leakage & Deterministic Replay Vertical Slice`.

Minimum first PR should include executable code + positive/negative/mutation tests that demonstrate: selected SYN-A four-cutoff clock, as-of data reconstruction with strict-before edges, no future/immature observation, safe handling of withheld/unknown, two simple agent adapters, deterministic trace manifest + fresh-process repeat. If scope requires multiple commits, split by vertical behavior rather than another authorization-document chain.

**Stop on:** unexpected changes to previously tracked source under a docs-only rebaseline, changes to protected Formal/Survivor roots, a new claim that Draft 0.1 is issued/approved, an access-control bypass, a frozen-fixture rewrite, fake external source/Native proof, or a claim of full MVP acceptance without executed evidence. Do not automatically rewrite/rebaseline old guards.

**Final Owner disposition for this task:** `WU05_REBASELINE01_RESEARCH_SCOPE_OWNER_ACCEPTED`  
**Remaining acceptance work:** Git integration of this amendment; then executable Stage V and Stage M technical verification.  
**Original Full Functional Scheme B:** `NOT_COMPLETED` and deferred, never renamed ACCEPTED.
