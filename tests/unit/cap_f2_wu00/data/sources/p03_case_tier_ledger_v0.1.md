# CAP-F2 — P-03 Golden Case–Tier Traceability Ledger v0.1

**Document ID:** `CAP-F2-P03-GOLDEN-LEDGER-v0.1`  
**Date:** 2026-10-19 · Asia/Taipei  
**Status:** `PROPOSED / NOT_EXECUTED / USER_ADJUDICATION_PENDING`  
**Purpose:** Documentary, exact source-derived mapping of all frozen acceptance obligations; **not a test runner, verified runtime result, or newly authoritative oracle.**

**Normative source:** Gate 4 Golden v1.0 (`02716d2bd4d0983ed0b8d8e22f51dc7d7e2d0c0ed1d3debc6a6e50c9e9f3f3fb`). The Golden file, not this copied ledger, prevails on any discrepancy. Each source row is referenced by physical line number and every complete Expected / Reason / Lineage / Forbidden value is preserved in the A-case entries.

**Authority:** P-01 v0.2 accepted by user, P-02 v0.2 accepted by user through later approval (its as-issued header predates that approval), Gate 5 accepted for scoped planning only. No code/DB/test execution authorized.

## A. Accounting invariant

| Group | Logical IDs | Required case–tier obligations |
|---|---:|---:|
| A01…A12 | 64 | 93 |
| RP01…RP06 | 46 | 61 |
| **Total** | **110** | **154** |

| Required tier | Count |
|---|---:|
| `S` | 56 |
| `X` | 29 |
| `M` | 16 |
| `P` | 53 |

**Tier semantics:** `S` = pure semantic; `X` = integrated cross-layer; `M` = specified metamorphic/property comparison; `P` = actual guarded Test PostgreSQL. Combined requirements are conjunctive. The entries below are proposed planning mappings; not PASS claims.

**Future case status:** every `(case_id, tier)` starts at `NOT_EXECUTED`. P-tier cannot be satisfied by mocked DB, static parsing or inherited CAP-F1 CI status. Source references preserve exact Golden wording; test functions can be shared without collapsing any case.

## B. A01…A12 — exact frozen case rows

**Table fields:** `case`, `base`, `unique delta`, `required tiers`, `owner`, `suggested Work Unit` are identity/plan; Expected, Reason, Lineage, Forbidden are verbatim from Golden §5 rows (except Markdown cell wrapping). Deltas are case-specific mutations and are **not** additional acceptance IDs.


### A01 — Identity Integrity (4 cases)

Planned owner/workstream: `S1` / `WU-01`; final integrated P-tier evidence, where required, is owned by WU-07.

| Case & source line | Base / delta ID | Required tier(s) | Delta operation (Golden) | Expected outcome | Expected reason | Required lineage / exclusions | Forbidden assertion |
|---|---|---|---|---|---|---|---|
| `A01-C01` · G:157 | `B0` / `D-A01-C01` | `S` | Change April representation to 100,000 NTD with exact ×1/1000 conversion and same entity/period/basis | SameSubject=SAME; canonical amount=100 NTD thousands | `NONE` | SUB-A-APR; mapping BASIS-CONSOLIDATED-V1 | Treat unit label as a different economic subject |
| `A01-C02` · G:158 | `B0` / `D-A01-C02` | `S` | Add H1 duration 2025-01-01..06-30 claim with numeric value 600 and Q2 reported value 600 | SameSubject(Q2,H1)=DIFFERENT | `SUBJECT_MISMATCH` | Q2 period and H1 period | Merge identical numeric values into one subject |
| `A01-C03` · G:159 | `B0` / `D-A01-C03` | `S` | Add independently published same-subject June claim value 300, new assertion A-JUN-PEER, issuer context/identity distinct | SameSubject=SAME; assertion IDs remain distinct | `NONE` | A-JUN-01 and A-JUN-PEER | Merge issuer assertions by equal value |
| `A01-C04` · G:160 | `B0` / `D-A01-C04` | `S` | Remove reporting_scope from second June candidate; no mapping evidence for consolidated vs individual | SameSubject=UNRESOLVED | `BASIS_UNRESOLVED` | second candidate; unresolved mapping | Default unknown scope to consolidated |

### A02 — Claim-Specific Evidence (4 cases)

Planned owner/workstream: `S1` / `WU-01`; final integrated P-tier evidence, where required, is owned by WU-07.

| Case & source line | Base / delta ID | Required tier(s) | Delta operation (Golden) | Expected outcome | Expected reason | Required lineage / exclusions | Forbidden assertion |
|---|---|---|---|---|---|---|---|
| `A02-C01` · G:167 | `B0` / `D-A02-C01` | `S/X` | Use CV-JUN-01 and SUP-JUN1-PUB with body 300 and exact 07/03 issuance support | June v1 content and issuance attributable | `NONE` | CV-JUN-01 → SUP-JUN1-PUB → A-JUN-01 | Use unrelated support as publication proof |
| `A02-C02` · G:168 | `B0` / `D-A02-C02` | `S` | At same source_locator substitute CV-JUN-02 value 310 while attaching only SUP-JUN1-PUB (300/07-03) | 310 lacks inherited 07/03 content-time support | `CONTENT_BINDING_INSUFFICIENT` | Exclude SUP-JUN1-PUB as support for CV-JUN-02 | Carry URL timestamp to changed body |
| `A02-C03` · G:169 | `B0` / `D-A02-C03` | `S` | Add second capture OBS-JUN1-REPEAT 2025-07-16 12:00+08 of identical CV-JUN-01 bytes | Two captures; exactly one issuer publication event | `NONE` | CV-JUN-01; OBS-JUN1-LATE; OBS-JUN1-REPEAT | Invent another publication from reobservation |
| `A02-C04` · G:170 | `B0` / `D-A02-C04` | `S` | Add downstream provider P-X capture showing 300 on 07/16, no independent issuer notice evidence | Provider observation only; not second issuer assertion | `ATTRIBUTION_UNRESOLVED` | P-X capture; issuer attribution unresolved | Fabricate issuer event for forwarded value |

### A03 — Temporal Boundary (7 cases)

Planned owner/workstream: `S2` / `WU-01`; final integrated P-tier evidence, where required, is owned by WU-07.

| Case & source line | Base / delta ID | Required tier(s) | Delta operation (Golden) | Expected outcome | Expected reason | Required lineage / exclusions | Forbidden assertion |
|---|---|---|---|---|---|---|---|
| `A03-C01` · G:177 | `B0` / `D-A03-C01` | `S/M` | Replace June pub proof by content-bound upper bound 2025-07-06T23:59:59+08:00 CLOSED | SUPPORTED at t0 | `NONE` | bound; CV-JUN-01 | Reject a strictly pre-cutoff bound |
| `A03-C02` · G:178 | `B0` / `D-A03-C02` | `S/M` | Set supported upper bound u=t0 with OPEN semantics | SUPPORTED at t0 | `NONE` | (t0,OPEN); CV-JUN-01 | Treat OPEN equality as late |
| `A03-C03` · G:179 | `B0` / `D-A03-C03` | `S/M` | Set sole supported upper bound u=t0 with CLOSED semantics | UNRESOLVED at t0 | `TEMPORAL_BOUND_INSUFFICIENT` | (t0,CLOSED); no independent earlier proof | Declare known late or early without evidence |
| `A03-C04` · G:180 | `B0` / `D-A03-C04` | `S/M` | Prove precise June publication timestamp equals exactly t0 | NOT_ADMISSIBLE for this publication path | `PUBLICATION_NOT_PRE_CUTOFF` | exact timestamp; publication path | Treat equality as strictly-before |
| `A03-C05` · G:181 | `B0` / `D-A03-C05` | `S/M` | Use independently authenticated date-only publication 2025-07-06 Asia/Taipei; OPEN upper bound next local midnight | SUPPORTED at t0 | `NONE` | (2025-07-07T00:00:00+08:00,OPEN) | Default date-only to 00:00 on release day |
| `A03-C06` · G:182 | `B0` / `D-A03-C06` | `S` | Remove time zone for ambiguous 2025-07-07 00:30 publication with plausibly crossing-zone interpretation | UNRESOLVED | `TIMEZONE_UNRESOLVED` | ambiguous timestamp; no default zone | Assume Asia/Taipei or UTC by convenience |
| `A03-C07` · G:183 | `B0` / `D-A03-C07` | `S/X` | Substitute notice body 310 at same locator, retaining 300 version timestamp only | New body lacks qualifying prior timestamp | `CONTENT_BINDING_INSUFFICIENT` | CV-JUN-02 cannot use SUP-JUN1-PUB | Inherit timing by URL |

### A04 — Reconstruction Mode Isolation (4 cases)

Planned owner/workstream: `S2` / `WU-01`; final integrated P-tier evidence, where required, is owned by WU-07.

| Case & source line | Base / delta ID | Required tier(s) | Delta operation (Golden) | Expected outcome | Expected reason | Required lineage / exclusions | Forbidden assertion |
|---|---|---|---|---|---|---|---|
| `A04-C01` · G:190 | `B0` / `D-A04-C01` | `X` | Place issuer 07/03 content and valid publication support in later research observation 2026-01-01, public mode | Public mode temporal SUPPORT may hold; no historic lab capture | `NONE` | CV-JUN-01; issuer release proof; 2026 observation | Claim lab observed 2025 from later verification |
| `A04-C02` · G:191 | `B0/OBS` / `D-A04-C02` | `S/X` | Use only OBS-JUN1-LATE completion 07/15, ask for observed reconstruction t0 | Not observed-eligible at t0 | `OBSERVATION_AFTER_CUTOFF` | OBS-JUN1-LATE; exclude earlier capture | Substitute issuer time for lab completion |
| `A04-C03` · G:192 | `B0` / `D-A04-C03` | `X` | Add new report first published 2025-07-07 07:00, decision at 08:00, info cutoff t0=00:00 | Report NOT_ADMISSIBLE at t0 | `PUBLICATION_NOT_PRE_CUTOFF` | 07:00 release; t0 | Use 08:00 wall-clock as info cutoff |
| `A04-C04` · G:193 | `B0` / `D-A04-C04` | `X` | Execute frozen qualified Q2 computation at 2025-07-07 07:30, no new input | VALUE_AVAILABLE(600); operational availability by 08:00 not presumed | `NONE` | A-APR-01,A-MAY-01,A-JUN-01 | Invalidate qualified info solely for late compute |

### A05 — Revision Non-Retroactivity (5 cases)

Planned owner/workstream: `S3` / `WU-02`; final integrated P-tier evidence, where required, is owned by WU-07.

| Case & source line | Base / delta ID | Required tier(s) | Delta operation (Golden) | Expected outcome | Expected reason | Required lineage / exclusions | Forbidden assertion |
|---|---|---|---|---|---|---|---|
| `A05-C01` · G:200 | `B0` / `D-A05-C01` | `X` | No eligible 07/10 correction in E0 | SELECTED(A-JUN-01,300) | `NONE` | A-JUN-01; SUP-JUN1-PUB; RCPT-E0 | Select future 310 |
| `A05-C02` · G:201 | `B1` / `D-A05-C02` | `X` | Use qualified REL-JUN-01 and CV-JUN-02 in E1 | SELECTED(A-JUN-02,310) | `NONE` | A-JUN-02; SUP-JUN2-PUB; SUP-JUN-REV; RCPT-E1 | Keep obsolete version without policy cause |
| `A05-C03` · G:202 | `B3` / `D-A05-C03` | `X` | Use E1 at earlier t0; 07/10 publication after t0 | SELECTED(A-JUN-01,300) | `NONE` | A-JUN-01; exclude A-JUN-02 at t0 | Backdate correction to t0 |
| `A05-C04` · G:203 | `B0` / `D-A05-C04` | `S/X` | Replace E0 with isolated E1 view containing independently supported 07/10 REL-JUN-01; remove SUP-JUN1-PUB prior publication proof of old 300 | Old early target UNRESOLVED; relation independently supported at its actual time | `TEMPORAL_BOUND_INSUFFICIENT` | REL-JUN-01 independently; A-JUN-01 early unsupported | Infer old first publication from later correction |
| `A05-C05` · G:204 | `B0` / `D-A05-C05` | `X/P` | Create separate E2 research snapshot: newly discovered issuer correction A-JUN-EARLY-CORR=305 published 07/05 12:00+08, with own content-time proof and explicit relation A-JUN-01→A-JUN-EARLY-CORR; complete bounded receipt; evaluate new M3 at t0 | New M3 SELECTED(305), derived Q2=605; original M0 stays 600 | `NONE` | M3 includes A-JUN-EARLY-CORR and qualified relation; M0 pinned to A-JUN-01 | Mutate original M0 or treat late discovery as late publication |

### A06 — Coverage / Conflict (6 cases)

Planned owner/workstream: `S3` / `WU-02`; final integrated P-tier evidence, where required, is owned by WU-07.

| Case & source line | Base / delta ID | Required tier(s) | Delta operation (Golden) | Expected outcome | Expected reason | Required lineage / exclusions | Forbidden assertion |
|---|---|---|---|---|---|---|---|
| `A06-C01` · G:211 | `B0` / `D-A06-C01` | `S` | Change required RCPT-E0 search state COMPLETED to NOT_PERFORMED | UNRESOLVED | `COVERAGE_INSUFFICIENT` | RCPT-E0 incomplete | Treat absent search as empty universe |
| `A06-C02` · G:212 | `B0` / `D-A06-C02` | `S` | Select SUB-B-APR target; certified complete empty source scope and no material leads | NO_QUALIFIED_CLAIM | `NO_QUALIFIED_WITHIN_SCOPE` | RCPT-B-APR-COMPLETE-EMPTY | Generalize bounded absence to whole world |
| `A06-C03` · G:213 | `B0` / `D-A06-C03` | `S` | Add candidate lead L-ALT for same June subject plausibly public before t0 with missing content/time; receipt records material lead | UNRESOLVED | `MATERIAL_CANDIDATE_UNRESOLVED` | L-ALT; materiality rule and receipt | Ignore concrete material unknown |
| `A06-C04` · G:214 | `B0` / `D-A06-C04` | `S/M` | Add A-JUN-CONFLICT value 315 at 07/03 15:00, independent issuer pub proof; update complete receipt to include it; no revision relation and peer authority | UNRESOLVED | `MATERIAL_CANDIDATE_UNRESOLVED` | A-JUN-01,A-JUN-CONFLICT; no qualifying precedence | Break tie by latest timestamp/ID |
| `A06-C05` · G:215 | `B0/VAL` / `D-A06-C05` | `S` | Add independently published issuer A-JUN-PEER value 300 and update completed receipt; select CONTENT_VALUE target; also evaluate same fixture ATTRIBUTED_ASSERTION target | CONTENT_VALUE SELECTED(300) with both origins; ATTRIBUTED_ASSERTION UNRESOLVED if nonunique | `ATTRIBUTION_UNRESOLVED for attributed target` | A-JUN-01,A-JUN-PEER both retained | Merge assertion identities when values coincide |
| `A06-C06` · G:216 | `B0` / `D-A06-C06` | `S/P` | Required receipt/provider query raises injected read error before completing discovery | OPERATIONAL_ERROR; no normal S3 outcome | `REQUIRED_OPERATION_FAILED` | failed operation receipt and affected scope | Classify failed search as no claim |

### A07 — Field-Scoped Revision (4 cases)

Planned owner/workstream: `S3` / `WU-02`; final integrated P-tier evidence, where required, is owned by WU-07.

| Case & source line | Base / delta ID | Required tier(s) | Delta operation (Golden) | Expected outcome | Expected reason | Required lineage / exclusions | Forbidden assertion |
|---|---|---|---|---|---|---|---|
| `A07-C01` · G:223 | `B1` / `D-A07-C01` | `S/X` | REL-JUN-01 scope exactly SUB-A-JUN; order-count independent subject | Only monthly revenue v1→v2 applicability changed | `NONE` | REL-JUN-01→SUB-A-JUN | Extend relation to all fields in notice |
| `A07-C02` · G:224 | `B1` / `D-A07-C02` | `S` | With unchanged orders 7 in CV-JUN-01 and CV-JUN-02, no order-correction evidence | No revision edge for SUB-A-JUN-ORDERS | `RELATION_SCOPE_MISMATCH if asserted` | A-ORD-01,A-ORD-02; exclude order revision edge | Fabricate order revision by document version |
| `A07-C03` · G:225 | `B1` / `D-A07-C03` | `S` | Use new independently attributable A-ORD-02=7 from 07/10 alongside A-ORD-01=7 | Distinct assertion/publication identities | `NONE` | A-ORD-01 and A-ORD-02 | Collapse equal content into same publication |
| `A07-C04` · G:226 | `B1` / `D-A07-C04` | `S` | Add supported withdrawal of A-JUN-02 at 07/11, without restoration of A-JUN-01, no alternative qualified claim | UNRESOLVED under withdrawal applicability policy | `RELATION_UNQUALIFIED for presumed rollback` | withdrawal event; A-JUN-01 not restored | Automatically restore old 300 |

### A08 — Derived Computability (6 cases)

Planned owner/workstream: `S4-A/B` / `WU-03`; final integrated P-tier evidence, where required, is owned by WU-07.

| Case & source line | Base / delta ID | Required tier(s) | Delta operation (Golden) | Expected outcome | Expected reason | Required lineage / exclusions | Forbidden assertion |
|---|---|---|---|---|---|---|---|
| `A08-C01` · G:233 | `B0` / `D-A08-C01` | `S/X` | Use three selected compatible months 100,200,300, exact integer rule FS-Q2-1 | VALUE_AVAILABLE(600) | `NONE` | A-APR-01,A-MAY-01,A-JUN-01 | Pass solely by coincidental sum using latest input |
| `A08-C02` · G:234 | `B1` / `D-A08-C02` | `S/X` | Use qualified correction, months 100,200,310 | VALUE_AVAILABLE(610) | `NONE` | A-APR-01,A-MAY-01,A-JUN-02 | Keep old June assertion in late derived lineage |
| `A08-C03` · G:235 | `B0` / `D-A08-C03` | `S` | Delete May claim and change complete May search receipt to empty, no material unknown | NOT_COMPUTABLE; no numeric Q2 | `DEPENDENCY_NOT_COMPUTABLE` | May NO_QUALIFIED_CLAIM; Apr/June selected | Implicitly insert zero or skip month |
| `A08-C04` · G:236 | `B0` / `D-A08-C04` | `S/X` | Add material unresolved June competitor with bounded lead as A06-C03 | UNRESOLVED; no numeric Q2 | `DEPENDENCY_UNRESOLVED` | June UNRESOLVED lead; no selected substitute | Use 300 just to finish sum |
| `A08-C05` · G:237 | `B0` / `D-A08-C05` | `S` | Change May selected claim reporting_scope to individual, not consolidated; mapping verifies DIFFERENT | NOT_COMPUTABLE under FS-Q2-1 | `ACCOUNTING_BASIS_INCOMPATIBLE` | May incompatible; Apr/June compatible | Mix consolidation bases for Q2 |
| `A08-C06` · G:238 | `B0` / `D-A08-C06` | `S` | Replace FS-Q2-1 month list [APR,MAY,JUN] by [APR,MAY,JUN,JUN] with unique-month contract unchanged | CONTRACT_VIOLATION | `INVALID_FEATURE_SPEC` | duplicate June in spec | Double-count June and call it quarter |

### A09 — Fitted-State & Label Causality (5 cases)

Planned owner/workstream: `S4-C` / `WU-03`; final integrated P-tier evidence, where required, is owned by WU-07.

| Case & source line | Base / delta ID | Required tier(s) | Delta operation (Golden) | Expected outcome | Expected reason | Required lineage / exclusions | Forbidden assertion |
|---|---|---|---|---|---|---|---|
| `A09-C01` · G:245 | `B0` / `D-A09-C01` | `S` | Compute FS-Q2-1 with θ=∅, no fit dependencies | VALUE_AVAILABLE(600); fitting NOT_APPLICABLE | `NONE` | three source months; no synthetic model state | Invent artificial fitted-state proof |
| `A09-C02` · G:246 | `B0` / `D-A09-C02` | `S/X` | Set FIT-0 cutoff t0, training view PRE-T0, dependency on A-JUN-02 first public 07/10 18:30 | Fitted state inadmissible; block affected derived feature | `FUTURE_DEPENDENCY` | FIT-0→A-JUN-02; after fit cutoff | Admit fitted state from future claim |
| `A09-C03` · G:247 | `B0` / `D-A09-C03` | `S` | Set FIT-0 cutoff t0, dependent label L-0 with explicitly declared maturity 07/12 00:00 | Fitted state inadmissible | `IMMATURE_LABEL` | FIT-0→L-0 maturity after t0 | Use immature target in fit |
| `A09-C04` · G:248 | `B0` / `D-A09-C04` | `S` | Specify feature F-CYCLE requires state THETA-CYCLE and THETA-CYCLE requires F-CYCLE | CONTRACT_VIOLATION | `DEPENDENCY_CYCLE` | F-CYCLE↔THETA-CYCLE | Evaluate cyclic information dependency |
| `A09-C05` · G:249 | `B0` / `D-A09-C05` | `S` | Target encoder TE-OWN for training-row R1 with own mature binary label=1 returns encoded feature=1 directly from R1 label; no out-of-fold/leave-one-out isolation contract | Cannot certify leakage-safe training feature; deny approval | `WITHIN_SAMPLE_TARGET_LEAKAGE` | TE-OWN→row-own-label | Treat maturity alone as sample isolation |

### A10 — Audit Non-Interference (5 cases)

Planned owner/workstream: `S4-D` / `WU-03`; final integrated P-tier evidence, where required, is owned by WU-07.

| Case & source line | Base / delta ID | Required tier(s) | Delta operation (Golden) | Expected outcome | Expected reason | Required lineage / exclusions | Forbidden assertion |
|---|---|---|---|---|---|---|---|
| `A10-C01` · G:256 | `B0` / `D-A10-C01` | `M/X` | Append audit-only FUTURE_RESTATEMENT_NOTE="revised July10"; keep Q,context,policy fixed | Agent serialized bytes unchanged | `NONE` | same projection from Q and U; future note audit only | Leak future note into payload |
| `A10-C02` · G:257 | `B0` / `D-A10-C02` | `M` | Edit ONLY explanatory audit coverage-confidence/reason wording without changing normative coverage decision | Allowed missing mask unchanged | `NONE` | same S3 qualified result/branch; audit text excluded | Use retrospective confidence as missingness flag |
| `A10-C03` · G:258 | `B0` / `D-A10-C03` | `M` | Toggle audit-only future revision flag with no eligible S3 input change; FS-Q2-1 baseline specifies NO_FALLBACK | Fallback branch remains NO_FALLBACK | `NONE` | same permitted branch predicate | Choose proxy using future flag |
| `A10-C04` · G:259 | `B0` / `D-A10-C04` | `M/X` | Attach later reward/return label to Audit for SYN-B; U0 and grid unchanged | G and sample policy decision unchanged | `NONE` | U0={A,B}; all four grid rows | Delete losing firm or adjust sample |
| `A10-C05` · G:260 | `B0` / `D-A10-C05` | `S/X` | Attempt to replace U0 with current survivor subset {SYN-A} in rank/projector while declared Universe pin still UNI-1 | CONTRACT_VIOLATION; reject unpinned Universe substitution | `INVALID_UNIVERSE_POLICY` | UNI-1; excluded survivor list | Silently omit SYN-B |

### A11 — Missingness & Failure Integrity (6 cases)

Planned owner/workstream: `S4-D / Shared` / `WU-03 / WU-06`; final integrated P-tier evidence, where required, is owned by WU-07.

| Case & source line | Base / delta ID | Required tier(s) | Delta operation (Golden) | Expected outcome | Expected reason | Required lineage / exclusions | Forbidden assertion |
|---|---|---|---|---|---|---|---|
| `A11-C01` · G:267 | `B0` / `D-A11-C01` | `S/X` | Replace April claim by valid pre-t0 0 with own content/support and maintain complete receipt | VALUE_AVAILABLE(0) at source; Q2=500, not missing | `NONE` | qualified zero April; May200; June300 | Interpret numerical 0 as unknown |
| `A11-C02` · G:268 | `B0` / `D-A11-C02` | `S/X` | Delete May claim, update fully completed May receipt to empty; P-OBS-1 expressly allows neutral missing for this case | NOT_COMPUTABLE; publication PUBLISHED_WITH_ALLOWED_MISSING | `DEPENDENCY_NOT_COMPUTABLE` | missing token only; May NO_QUALIFIED_CLAIM in audit | Auto-zero or leak detailed reason in agent payload |
| `A11-C03` · G:269 | `B0` / `D-A11-C03` | `S/X` | Add evidence-grounded material June unknown as A06-C03; strict core feature policy | UNRESOLVED; research COMPLETED; agent WITHHELD | `DEPENDENCY_UNRESOLVED` | June lead and unresolved reason in audit only; grid row kept | Emit ordinary neutral missing or delete grid row |
| `A11-C04` · G:270 | `B0` / `D-A11-C04` | `S/P` | Select nonexistent required feature spec FS-UNKNOWN with no registered definition | CONTRACT_VIOLATION; run FAILED | `INVALID_FEATURE_SPEC` | invalid spec ref in engineering/audit | Publish None as normal missing |
| `A11-C05` · G:271 | `B0` / `D-A11-C05` | `P` | Inject read failure for a required persisted input after freeze begins | OPERATIONAL_ERROR; run FAILED | `REQUIRED_OPERATION_FAILED` | failed input read and safe diagnostic ref | Return zero/missing/NO_QUALIFIED_CLAIM |
| `A11-C06` · G:272 | `B0` / `D-A11-C06` | `P` | Inject failure before finalization COMMIT after manifest/result and before completion/observation authorized | No COMPLETED and no visible agent payload | `REQUIRED_OPERATION_FAILED` | transaction rollback; incomplete attempt recorded safely | Expose partial success |

### A12 — Deterministic Replay (8 cases)

Planned owner/workstream: `Shared Manifest` / `WU-05 / WU-06 / WU-07`; final integrated P-tier evidence, where required, is owned by WU-07.

| Case & source line | Base / delta ID | Required tier(s) | Delta operation (Golden) | Expected outcome | Expected reason | Required lineage / exclusions | Forbidden assertion |
|---|---|---|---|---|---|---|---|
| `A12-C01` · G:279 | `B2` / `D-A12-C01` | `X/P` | Replay same sealed M0 without source rediscovery; identical versions, numeric and serializer | 600; exact canonical value/lineage/payload equivalence | `NONE` | M0; A-APR-01,A-MAY-01,A-JUN-01 | Use a fresh latest-source query |
| `A12-C02` · G:280 | `B2` / `D-A12-C02` | `P` | Append CV-JUN-02 and REL-JUN-01 to database after original M0 committed, then replay M0 | 600 and original M0 lineage unchanged | `NONE` | E0 pinned; exclude new E1 artifacts | Substitute 310 during replay |
| `A12-C03` · G:281 | `B1` / `D-A12-C03` | `X/P` | Evaluate new M1 based on E1 with late cutoff t1 | 610 with new manifest identity | `NONE` | A-JUN-02 and qualified REL-JUN-01 | Write 610 into M0 record |
| `A12-C04` · G:282 | `B3` / `D-A12-C04` | `X/P` | Evaluate t0 anew with E1, supported 07/10 event strictly after t0 | 600 under different M2 identity | `NONE` | M2 != M0; June old at t0 | Equate new context with old manifest |
| `A12-C05` · G:283 | `B2` / `D-A12-C05` | `S/P` | Replace stored CV-JUN-01 V1 300 bytes with V2 310 bytes while keeping CV-JUN-01 ID/digest reference | Replay BLOCKED: PINNED_INPUT_INVALID | `PINNED_INPUT_INVALID` | M0→CV-JUN-01 V1 fingerprint | Recalculate and accept corrupted bytes |
| `A12-C06` · G:284 | `B2` / `D-A12-C06` | `P` | Use two PostgreSQL connections: reader freezes first membership; writer commits new version/edge between necessary reads | Coherent E0 snapshot; no hybrid input set | `NONE` | one pinned committed read view | Mix pre/post writer state |
| `A12-C07` · G:285 | `B0` / `D-A12-C07` | `P` | Inject failure in atomic finalization before commit after one dependent write | No externally COMPLETED manifest/result/agent publication | `REQUIRED_OPERATION_FAILED` | rolled-back transaction / hidden provisional write | Show partial canonical result |
| `A12-C08` · G:286 | `B2` / `D-A12-C08` | `M/P` | Change DB row enumeration and append unrelated receipt for non-target issuer with M0 fixed | Same status, value, pinned lineage and canonical agent bytes | `NONE` | M0 ordering policy; unrelated append excluded | Use arrival order as winner/tie-break |

## C. RP01…RP06 — exact frozen physical acceptance registry

For RP tests the two Golden columns are `Fixed fault/interleaving` and `Required oracle / forbidden shortcut`; the latter must be judged in full, not merely substring-matched. All RP entries remain distinct required logical IDs.


### RP01 — Canonical Fixture & Immutable Content (6 tests)

Candidate Work Unit trace: `WU-00 / WU-04 / WU-07`; unit-local evidence is partial until all required tiers and WU-07 integration are independently accepted.

| Test & Golden line | Required tier(s) | Fixed fault / interleaving (Golden) | Required oracle / forbidden shortcut (Golden) |
|---|---|---|---|
| `RP01-T01` · G:358 | `S/P` | Bind CV-JUN-01 to V1 then attempt to rebind to V2 | Reject same-content-version identity collision; no published content mutation |
| `RP01-T02` · G:359 | `S/P` | Tamper V1 value bytes while retaining original V1 digest | PINNED_INPUT_INVALID/integrity failure |
| `RP01-T03` · G:360 | `S` | Shuffle only object key input ordering | Canonically identical 118 bytes and V1 digest |
| `RP01-T04` · G:361 | `S` | Reorder a schema-tagged ordered events array | New canonical meaning/identity, not silently identical |
| `RP01-T05` · G:362 | `S` | Omit required named timezone or content_version_id | CONTRACT_VIOLATION; do not default |
| `RP01-T06` · G:363 | `S` | Attempt evaluator read of Expected Oracle fixture | Boundary violation; fail harness inspection |

### RP02 — Frozen Manifest Completeness (7 tests)

Candidate Work Unit trace: `WU-05 / WU-07`; unit-local evidence is partial until all required tiers and WU-07 integration are independently accepted.

| Test & Golden line | Required tier(s) | Fixed fault / interleaving (Golden) | Required oracle / forbidden shortcut (Golden) |
|---|---|---|---|
| `RP02-T01` · G:369 | `S/P` | Load same complete sealed M0 twice | Same manifest identity/membership and approved oracle |
| `RP02-T02` · G:370 | `P` | Append June v2 after M0 finalization | M0 membership/digest immutable |
| `RP02-T03` · G:371 | `S/P` | Create M2 at t0 from E1 | M2 differs from M0 even if value both 600 |
| `RP02-T04` · G:372 | `S` | Omit evaluator_version or π revision from manifest | Reject incomplete replay manifest |
| `RP02-T05` · G:373 | `S` | Change feature spec or projector version in new manifest | Different identity; original untouched |
| `RP02-T06` · G:374 | `P` | Delete required immutable artifact reference | PINNED_INPUT_INVALID; no latest fallback |
| `RP02-T07` · G:375 | `S/P` | Retain SUP-JUN-REV ID but discard its referenced content version | Manifest transitive-completeness failure |

### RP03 — Consistent Freeze & Concurrent Append (6 tests)

Candidate Work Unit trace: `WU-05 / WU-07`; unit-local evidence is partial until all required tiers and WU-07 integration are independently accepted.

| Test & Golden line | Required tier(s) | Fixed fault / interleaving (Golden) | Required oracle / forbidden shortcut (Golden) |
|---|---|---|---|
| `RP03-T01` · G:381 | `P` | Reader first SELECT starts RR snapshot; writer commits June v2 before reader second SELECT | Reader consistent E0 membership; no hybrid |
| `RP03-T02` · G:382 | `P` | Writer commits June v2 before reader establishes snapshot | Reader may see complete E1 but time selector still controls t0/t1 |
| `RP03-T03` · G:383 | `P` | Add evidence after freeze completion | Previously pinned membership immutable |
| `RP03-T04` · G:384 | `P` | Writer appends independent unrelated artifact | No change to M0 result or pinned lineage |
| `RP03-T05` · G:385 | `P` | Inject DB query failure between necessary reads | No complete frozen manifest published |
| `RP03-T06` · G:386 | `P` | Writer inserts uncommitted relation when reader queries | Reader never treats uncommitted relation as admitted |

### RP04 — Atomic Finalization & Recovery (8 tests)

Candidate Work Unit trace: `WU-06 / WU-07`; unit-local evidence is partial until all required tiers and WU-07 integration are independently accepted.

| Test & Golden line | Required tier(s) | Fixed fault / interleaving (Golden) | Required oracle / forbidden shortcut (Golden) |
|---|---|---|---|
| `RP04-T01` · G:392 | `P` | Manifest insert fails inside finish transaction | No completed result/observation |
| `RP04-T02` · G:393 | `P` | Result insert fails after provisional manifest insert | No completed result/observation |
| `RP04-T03` · G:394 | `P` | Single allowlisted serializer fails before commit | No invalid/partial agent payload publication |
| `RP04-T04` · G:395 | `P` | Audit association insert fails before commit | No completed result |
| `RP04-T05` · G:396 | `P` | Completion marker insert/update fails | No visible completed publication |
| `RP04-T06` · G:397 | `P` | Force transaction abort before commit | All provisional formal writes roll back |
| `RP04-T07` · G:398 | `P` | Commit succeeds but client acknowledgment lost | Query publication key; exactly one matching completed publication |
| `RP04-T08` · G:399 | `P` | Two workers concurrently finalize same stable publication key | Unique coherent outcome; no conflicting completed duplicate |

### RP05 — Agent/Audit Boundary & Privileges (5 tests)

Candidate Work Unit trace: `WU-03 / WU-04 / WU-07`; unit-local evidence is partial until all required tiers and WU-07 integration are independently accepted.

| Test & Golden line | Required tier(s) | Fixed fault / interleaving (Golden) | Required oracle / forbidden shortcut (Golden) |
|---|---|---|---|
| `RP05-T01` · G:405 | `M/P` | Insert future-revision explanatory audit note only | No changes in canonical agent bytes/mask/branch |
| `RP05-T02` · G:406 | `M/P` | Toggle post-hoc reward for SYN-B only | No change in U0/grid/sample decision |
| `RP05-T03` · G:407 | `P` | Attempt agent request to raw issuer/support/audit/engine error fields | Access refused; only allowlisted payload exposed |
| `RP05-T04` · G:408 | `P` | Attempt ordinary runtime UPDATE/DELETE of finalized version/manifest | Refused by protected DB privileges/constraints |
| `RP05-T05` · G:409 | `X/P` | Attempt publish WITHHELD unresolved core feature as neutral missing | Fail projection policy; grid row remains recorded |

### RP06 — Replay, Ordering & Injected Failures (14 tests)

Candidate Work Unit trace: `WU-05 / WU-06 / WU-07`; unit-local evidence is partial until all required tiers and WU-07 integration are independently accepted.

| Test & Golden line | Required tier(s) | Fixed fault / interleaving (Golden) | Required oracle / forbidden shortcut (Golden) |
|---|---|---|---|
| `RP06-T01` · G:415 | `X/P` | Replay M0 from pinned content | 600, exact approved lineage and canonical payload |
| `RP06-T02` · G:416 | `P` | Append correction then replay unchanged M0 | 600, no new-version substitution |
| `RP06-T03` · G:417 | `X/P` | Evaluate new M1 at t1/E1 | 610 and distinct M1 identity |
| `RP06-T04` · G:418 | `X/P` | Evaluate new M2 at t0/E1 | 600 under this controlled corpus, M2≠M0 |
| `RP06-T05` · G:419 | `P` | Substitute V2 altered bytes for CV-JUN-01 pinned by M0 | BLOCK PINNED_INPUT_INVALID |
| `RP06-T06` · G:420 | `P` | Remove required support referenced by M0 | BLOCK PINNED_INPUT_INVALID |
| `RP06-T07` · G:421 | `S/P` | Replace pinned selector policy by currently latest version | Block version mismatch, no silent upgrade |
| `RP06-T08` · G:422 | `M/P` | Append unrelated receipt | Same M0 output |
| `RP06-T09` · G:423 | `M/P` | Permute DB row enumeration while respecting pinned set | Identical canonical selection/lineage/output |
| `RP06-T10` · G:424 | `M/P` | Change only future audit note and retrospective confidence wording | Agent bytes/masks/fallback/population unchanged |
| `RP06-T11` · G:425 | `P` | Interleave writer commit between reader reads | One consistent frozen membership |
| `RP06-T12` · G:426 | `P` | Abort before atomic completion | No partial completed data/agent payload |
| `RP06-T13` · G:427 | `P` | Lose commit acknowledgment and recover under same publication key | No duplicate or contradiction |
| `RP06-T14` · G:428 | `P` | Required pinned content loader throws | Blocking operational error; no latest fallback |

## D. Mandatory evidence-join rules

1. **No family-level substitution:** a family name is not a case; require all 110 unique `case_id` rows from the Golden source, and exactly the 154 normalized `(case_id,tier)` obligations.
2. **No owner self-certification:** the under-test evaluator cannot read or generate its own expected oracle. Acceptance comparison, lineage and forbidden checks belong to a separately reviewed harness.
3. **Negative evidence is positive evidence:** for every A case, independently assert the `Forbidden` column is not observed; for every RP test, cover all required oracle and forbidden shortcuts. Matching value alone cannot pass.
4. **Golden controls discrepancies:** if this copy is inconsistent with hash-verified v1.0, record `LEDGER_SOURCE_MISMATCH` and stop. Do not silently repair the Frozen source. A genuine source semantic conflict becomes `ACCEPTANCE_SPECIFICATION_ISSUE`, requiring user-governed amendment.
5. **Execution status separation:** `PASS / FAIL / NOT_EXECUTED / BLOCKED / SPECIFICATION_ISSUE` applies per obligation. No run, DB, CI, source capture or role check was performed in this planning artifact.
6. **Future per-tier receipts:** expected and actual typed result/reason/value/lineage plus bytes/serialization when applicable, input/fixture/version identity, real Test DB evidence for P, interleaving/fault receipt, negative assertion receipt, cleanup and reviewer disposition.
7. **Workspace/safety boundary:** this ledger is an outside-repo proposed document, not a fixture to import into runtime. Any future incorporation in tests requires a separately authorized and hash-verified fixture/oracle isolation scheme.

**STOP: documentary planning only.**
