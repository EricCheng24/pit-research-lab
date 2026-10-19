# CAP-F2 Gate 4 — Golden Acceptance Specification v1.0

**Project:** PIT Research Lab · CAP-F2  
**Document class:** Normative synthetic golden acceptance specification  
**Version:** `1.0` · **Prepared:** `2026-10-18` (Asia/Taipei)  
**Review status at issue:** `FINAL_CONTRACT_FREEZE_REVIEW_PENDING`  
**Gate 4 architecture decisions:** `G4-D01…G4-D20 USER_APPROVED`  
**Integrated adjudications:** `G4-AJ01…G4-AJ06 USER_APPROVED`  
**Runtime implementation, SQL migrations, test execution:** `NOT AUTHORIZED / NOT EXECUTED`  
**Gate 3 true-source freeze:** `BLOCKED`; no real issuer evidence is admitted by this document.

> **Controlling distinction:** A signed-off specification is an *oracle for future tests*, not evidence that the future PIT kernel already passes them. This document becomes **FROZEN** only after the user's separate final review/approval; issue of v1.0 alone does not effect freeze.

## 1. Governance, scope, and precedence

### 1.1 Purpose and authority

This document consolidates the user-approved G4-1 Golden Corpus Contract (GC-01…GC-06; G4-D01…D06), G4-2 Cross-Layer Acceptance Matrix (A01…A12; G4-D07…D12), G4-3 Replay & Persistence Acceptance Design (RP-01…RP-06; G4-D13…D20), and G4-4 adjudication/remediation (G4-AJ01…AJ06; G4-R01…R07). It provides a self-contained, reviewable baseline for future implementation and independent testing, not a new semantic model.

Normative requirements use **MUST**, **MUST NOT**, and **SHOULD**. If a suggested implementation technique differs from a semantic invariant, the semantic invariant prevails. Changes to a reviewed oracle require a separate numbered contract amendment, impact analysis, independent review and user approval; a failing implementation MUST NOT edit the expected result to make CI pass.

### 1.2 Prior accepted gates retained

- **Gate 1:** one S1 identity/evidence owner, one S2 time owner, one S3 historical selector, one S4 dependency evaluation and single observation projector; independent relation qualification; shared historical Universe; typed failures; immutable context-bound replay.
- **Gate 2 (G2-D01…D06):** reuse CAP-F1 Python + PostgreSQL modular monolith; immutable input set/manifest; consistent reads and atomic publication; layered typed results; shared Universe and single projector; safe migrations and least-privilege access. No existing CAP-F2 PIT domain schema or verified runtime is assumed.
- **Gate 3:** synthetic-first acceptance design is permitted while real historical publication, rights, original-version history and complete source coverage remain limited. G3-R1 (`2236`, September 2025) closed with explicit limitations and is **not** part of the synthetic corpus.
- **Test/evidence terminology:** `SPECIFICATION_ACCEPTED`, `TEST_PASS`, `ENGINEERING_ACCEPTED`, `REAL_SOURCE_ADMITTED` and `PRODUCTION_READY` denote separate, non-implicating statuses.

### 1.3 Freeze exclusions

No branch creation, Codex execution, code edits, data ingestion, migrations, provider API access, bulk downloads, GitHub CI changes, real-source archival grants, general ML/RL training, live deployment or real trading are authorized by this document. Future PostgreSQL examples refer exclusively to an explicitly approved, isolated **Test** target with the existing CAP-F1 guards intact.

## 2. Semantic ownership and typed boundaries

| Owner | Normative question | Consumed / emitted contract | Forbidden shortcut |
|---|---|---|---|
| **S1** | What precise subject, assertion, evidence content and attribution? | Subject mapping; `SAME / DIFFERENT / UNRESOLVED`; content-bound support and attribution | Conflate subject, value, assertion, provider, URL, capture, publication |
| **S2** | Was this content/event available strictly **before** the decision information cutoff under the declared mode? | `SUPPORTED / UNRESOLVED / NOT_ADMISSIBLE` with evidence path | Use capture date as publication date; inherit time across new body; assume unknown timezone |
| **S3** | Which evidenced version applied, given target, relations, materiality and adequate bounded coverage? | `SELECTED(x) / UNRESOLVED / NO_QUALIFIED_CLAIM` plus audit | MAX(timestamp), majority vote, later revision backfill, invented rollback, no-search ⇒ no-claim |
| **S4-A/B/C** | What can be computed from selected values, valid dependencies and fitted state? | `VALUE_AVAILABLE / NOT_COMPUTABLE / UNRESOLVED` with lineage | latest fetch, unauthorized fill, post-cutoff fit, immature label, dependency cycle |
| **S4-D** | What may the agent consume? | approved schema/serializer; allowed value/missing or withholding | expose audit IDs/reasons/future labels; drop universe member due to missing value |
| **Shared reconstruction/persistence** | What exact context and immutable content was used, and was it atomically finalized? | Manifest/Run/Result identities; freeze, replay and commit boundary | use latest sources during replay; partial publication; failure-to-missing conversion |

Normal research non-values are distinct from **blocking** `CONTRACT_VIOLATION` and `OPERATIONAL_ERROR` (including pinned-input integrity faults). A `FAILED` run is not a fourth S3 selection result. `WITHHELD` is a projection/publication disposition, not a source fact.

**Cutoff rule:** valid historical-publication upper-bound evidence `(u,OPEN)` supports strict pre-cutoff at `u=t`; `(u,CLOSED)` at equality alone does not. A **known exact** publication at `t` fails the strict-before requirement. A qualified source's time evidence does not confer historical laboratory capture. Prospective Observed PIT requires an actual completed, identifiable pre-cutoff observation.

## 3. Canonical Golden Corpus — GC-01…GC-06

### 3.1 The complete primary synthetic world (`BASE-0`)

All names, IDs, notices, providers, receipts, prices/amounts and rights in this section are **invented**. They are not claims about TWSE, MOPS, FinMind or a real issuer.

| Fixture | Immutable synthetic semantics |
|---|---|
| `ENT-A` | Fictional issuer `SYN-A`, manufacturing; listed/decision-eligible on both synthetic cutoff days |
| `ENT-B` | Fictional issuer `SYN-B`, likewise eligible, used for Universe, cross-section and bounded no-claim |
| `SUB-A-APR` | `SYN-A`; consolidated net monthly operating revenue; `Duration(2025-04-01,2025-04-30)`; NTD thousands; compatible basis `BASIS-CONSOLIDATED-V1` |
| `SUB-A-MAY` | Same subject dimensions, May 2025 period |
| `SUB-A-JUN` | Same subject dimensions, June 2025 period |
| `SUB-A-Q2` | Derived subject: consolidated quarter flow, `Duration(2025-04-01,2025-06-30)`; *not* an issuer-published Q2 assertion |
| `SUB-A-JUN-ORDERS` | Separate non-revenue subject; June 2025 count of orders, integer `7`, not eligible as a revenue input |
| `SUB-B-APR` | `SYN-B` monthly consolidated revenue April 2025; intentionally no qualified candidate in a fully searched synthetic scope |
| `CAL-1` | Calendar version declares both 2025-07-07 and 2025-07-14 as first qualifying trading days of their week; 00:00+08:00 cutoff; 08:00 decision wall-clock |
| `UNI-1` | `U(t0)=U(t1)={SYN-A,SYN-B}`; predeclared full grid `G={(t0,A),(t0,B),(t1,A),(t1,B)}` |
| `FS-Q2-1` | `STRICT_Q2_SUM_V1`: exactly April+May+June, each once, same entity/metric/consolidation/basis/currency, signed integer exact sum; no implicit zero/forward fill; θ=∅ |
| `P-SEL-1` | Target `ATTRIBUTED_ASSERTION`, issuer notice scope, time-qualified explicit corrections, material conflicts block, fully bounded completed source discovery required |
| `P-OBS-1` | Single allowlisted safe projection; publish qualified values and expressly permitted neutral no-claim missing; withhold core-feature `UNRESOLVED`; block operation/contract failure |
| `P-FIT-1` | Explicit feature/fit/decision as-of and label maturity; never allows training-row own-label target leakage without approved isolation |
| `NUM-1` | Signed 64-bit integer values, exact addition, no rounding/floating tolerance, NTD thousands; error on invalid domain or overflow |

All reference periods, entity identifiers, measurement basis, policies, targets and source identities are separate fields, even if their values happen to match.

### 3.2 Claims, release events and immutable synthetic evidence

| Assertion | Subject | Value | Fictional issuer publication `Asia/Taipei` | Artifact content-version | Support |
|---|---|---:|---|---|---|
| `A-APR-01` | `SUB-A-APR` | 100 | `2025-05-08 11:00:00` | `CV-APR-01` | `SUP-APR-PUB` |
| `A-MAY-01` | `SUB-A-MAY` | 200 | `2025-06-09 11:00:00` | `CV-MAY-01` | `SUP-MAY-PUB` |
| `A-JUN-01` | `SUB-A-JUN` | 300 | `2025-07-03 14:00:00` | `CV-JUN-01` | `SUP-JUN1-PUB` |
| `A-JUN-02` | `SUB-A-JUN` | 310 | `2025-07-10 18:30:00` | `CV-JUN-02` | `SUP-JUN2-PUB` |
| `A-ORD-01` | `SUB-A-JUN-ORDERS` | 7 | `2025-07-03 14:00:00` | `CV-JUN-01` | `SUP-ORD1-PUB` |
| `A-ORD-02` | `SUB-A-JUN-ORDERS` | 7 | `2025-07-10 18:30:00` | `CV-JUN-02` | `SUP-ORD2-PUB` |

`CV-JUN-02` is a **new synthetic notice version**, not an in-place overwrite. `REL-JUN-01` is separately supported by `SUP-JUN-REV`: it states a field-scoped issuer correction `A-JUN-01 → A-JUN-02` **only for June consolidated monthly revenue** and was itself published/qualified at `2025-07-10 18:30:00+08:00`. Order count `7` was restated in the second notice but has **no correction edge**: unchanged numerical value does not fuse issuer assertions or establish another revision. A synthetic recorded relation does not reverse-prove the older version's first-publication time.

`EVID-{APR,MAY,JUN1,JUN2}-TIME` are content-version-bound issuer publication receipts supporting the exact respective claim and time. `EVID-JUN-REL` is an independent document-and-event support for the correction. `OBS-{APR,MAY,JUN1,JUN2}-LATE` are separate synthetic **lab captures** with completion times *after* their issuance (the canonical retrospective baseline completes captures on `2025-07-15 12:00:00+08:00`). Thus none of these late captures establishes a prospective observed claim at `t0` or `t1`. Evidence artifacts, observations, support edges and assertions are different logical objects even when one synthetic JSON notice contains several fields.

### 3.3 Contexts, bounded discovery and version sets (GC-03/04)

| Context | Cutoff | Frozen scope | Expected June issuer assertion | Expected Q2 derived |
|---|---|---|---|---:|
| `CTX-EARLY` (`B0`) | `t0=2025-07-07T00:00:00+08:00` | `E0` with original April/May/June v1 and completed `RCPT-E0` | `A-JUN-01` | **600** |
| `CTX-LATE` (`B1`) | `t1=2025-07-14T00:00:00+08:00` | `E1=E0 + CV-JUN-02 + REL-JUN-01 + RCPT-E1` | `A-JUN-02` | **610** |
| `CTX-EARLY-REPLAY` (`B2`) | `t0` | **original sealed manifest `M0`, E0 only**, even after E1 insertions | `A-JUN-01` | **600** |
| `CTX-EARLY-NEW-EVIDENCE` (`B3`) | `t0` | **new manifest M2/E1**, same cutoff and policy | `A-JUN-01` | **600** |

`RCPT-E0` and `RCPT-E1` are invented immutable receipt snapshots for issuer notice discovery from `2025-05-01T00:00:00+08:00` up to the relevant cutoff, covering named revenue, revision and order notices. Their fixed page/result membership and explicit end-of-results marker establish synthetic `COMPLETED / SUFFICIENT` **only within the predeclared source and subject scope**. E0 has three revenue claims and order v1; E1 additionally has notice v2 and the scoped correction; no material unresolved candidates. For `SUB-B-APR`, the synthetic receipt declares an adequately completed empty source result (`NO_QUALIFIED_CLAIM`), not a globally proven nonexistence. No synthetic receipt proves anything about real public sites.

`M0`, `M1`, `M2` are **logical manifest designations**, not preexisting stored artifact IDs; their canonical bytes/digests are established at implementation from pinned complete input membership. `M0` and `M2` must be distinct even when both return 600. `B3` is valid only because the 7/10 event is *known to have occurred after t0*, and the expanded E1 adds no previously available competing pre-t0 issuer value; a different later-discovered historical pre-t0 source may legitimately alter a new reconstruction.

**Corpus reuse:** Base selection and reported value expectations depend on `S1→S2→S3` qualifying the synthetic content, scope, publication support and receipt completeness. The value 600/610 is **not** evidence that the issuer published an official Q2 number or that the Lab really computed it in 2025.

### 3.4 Case isolation and explicit deltas (G4-R01)

Each normative case uses `I_case = ApplyDelta(BASE-0, Delta_case)` under the named context. `Delta_case` is the **unique** change described in its registry row, including changes to linked receipts where stated. Other records, versions, policies and membership remain unchanged. A deliberately invalid delta may specify a malformed contract or corrupted bytes; it MUST NOT mutate BASE-0 or another case. Scenario-specific isolated subjects/providers and source scopes use the same predefined S1–S4 policies unless the row explicitly selects another approved target. Test oracles must be authored and frozen separately from evaluator inputs.

## 4. Canonical identity, bytes, and manifest binding (G4-R02)

### 4.1 `golden-json-c14n-v1` restricted synthetic profile

- Input is an object or array of **schema-allowed** JSON values. Keys match `[a-z][a-z0-9_]*`, are ASCII and **unique**; reject unrecognized or missing required keys. Canonical object keys sorted ascending by ASCII byte value.
- Strings are restricted to **printable ASCII code points U+0020…U+007E**. JSON encodes ASCII double quote as `\"`, backslash as `\\`, and does not emit unnecessary escapes. Control chars, non-ASCII strings and Unicode normalizations are **rejected** in this restricted profile, not silently rewritten. Non-ASCII original publisher documents require a separate future profile.
- Numeric values are integers in `[-2^63, 2^63-1]`; no floats, NaN, infinities, exponent notation, leading zeros or negative zero. Boolean is a distinct JSON type, not an integer. No implicit coercion from strings to numbers.
- Canonical output uses compact JSON, separators `,`/`:`, no extra whitespace, UTF-8 **without BOM**, no trailing newline in hashed payload. `null` differs from omitted keys; key presence validated by schema.
- Arrays tagged by schema as **ordered** preserve order; arrays tagged as **sets** are sorted by specified unique member identity and reject duplicates or ambiguous member keys rather than losing evidence. Object key sorting MUST NOT reorder meaningful sequence arrays.
- Timestamps are schema-validated `YYYY-MM-DDTHH:MM:SS+08:00` for this synthetic timeline; retain `Asia/Taipei` as named timezone, evidence precision and bound openness/closedness in separate required fields when applicable. Reject unknown timezone and implicit defaults. The `+08:00` profile is synthetic-specific; S2 supports other properly proven offsets under its policy.
- Schema version and `golden-json-c14n-v1` are pinned in enclosing contracts. SHA-256 is calculated on **exact canonical UTF-8 bytes**; a digest is a content-integrity claim, never proof of issuer publication or licensing.

### 4.2 Verified Golden Byte Vectors

**Vector V1:** raw canonical UTF-8 bytes, no final newline:

```json
{"content_version_id":"CV-JUN-01","publication_time":"2025-07-03T14:00:00+08:00","subject_id":"SUB-A-JUN","value":300}
```

- Byte count: `118`.
- SHA-256: `0675f2ae3d0c95e9efd9ffdac697945e141b6d53570beac2273fae6f0c087886`.
- Different input order of JSON object keys MUST serialize to exactly those bytes.

**Vector V2 (invalid same-version-content mutation):** replace final `"value":300` with `"value":310`, but **do not** change `CV-JUN-01`.

- Byte count: `118`.
- SHA-256: `ef3b3f21d450635765b6367393d95cf1ca58bde42e380b437e8c4c4f94edb1aa`.
- If a stored `CV-JUN-01` bound to V1 resolves to V2, **PINNED_INPUT_INVALID / INTEGRITY FAILURE**. Legal v2 publication uses new `CV-JUN-02`, claim `A-JUN-02`, support and relation.

Vector bytes are an intentionally tiny **normalized payload test**, not a claim to represent the entirety of the multi-field `CV-JUN-01` evidence artifact. The complete future fixture must bind every referenced assertion, support and original version. Raw stored bytes and a normalized derived payload have distinct hashes when they differ.

### 4.3 Immutable identities

`source_locator` can resolve to more than one historical content version. `subject_id` is semantic identity, not a value. `assertion_id`, `content_version_id`, evidence support ID, receipt ID and finalized `manifest_id` cannot be rebound to different canonical content. A `manifest_id` binds complete pinned transitive membership; a `run_id` denotes an execution attempt; a `result_id` denotes a complete research result; a **publication key** identifies a unique authorized externally consumable payload. IDs never substitute for checking bytes/digests.

## 5. Full Golden Acceptance Registry — 64 normative cases

### 5.1 Column interpretation

Every table row is normative. `Base` names the inherited snapshot and cutoff (`B0=E0/t0`, `B1=E1/t1`, `B2=M0 replay`, `B3=E1/t0`; `B0/OBS` is prospective observed variant; `B0/VAL` uses `CONTENT_VALUE` target). Each `Delta` column begins with its **unique delta identifier** `D-{case-id}`. `Expected` names typed result, concrete value or precise refusal. `Reason` is the expected auditable category, `NONE` for normal success; `Lineage` states required references or explicit exclusions. `Forbidden` is an independent assertion. `Tier` codes: `S` semantic/unit, `X` cross-layer, `P` real Test-PostgreSQL integration, `M` metamorphic/property; combined levels require both. Owner is uniquely assigned per family even for shared integration. These acceptance reason labels are **contract vocabulary**, not mandated Runtime Enum spellings (G4-R05).

For a negative fixture referring to an absent claim, its completed receipt is changed **in the same delta** to record an adequately searched empty result. For a material unknown, the synthetic lead is inserted with a documented plausible pre-cutoff effect and matching scoped receipt; otherwise absence could incorrectly be reported as a complete empty scope. `E0`/`E1` represent frozen memberships, not a rule allowing current sources to be reread.

### A01 — Identity Integrity  
**Primary semantic owner:** `S1`  

| Case / delta | Base | Exact isolated delta | Required expected oracle | Expected reason | Required lineage / exclusion | Forbidden behavior | Tier | Owner |
|---|---|---|---|---|---|---|---|---|
| `A01-C01` / `D-A01-C01` | `B0` | Change April representation to 100,000 NTD with exact ×1/1000 conversion and same entity/period/basis | SameSubject=SAME; canonical amount=100 NTD thousands | `NONE` | SUB-A-APR; mapping BASIS-CONSOLIDATED-V1 | Treat unit label as a different economic subject | `S` | `S1` |
| `A01-C02` / `D-A01-C02` | `B0` | Add H1 duration 2025-01-01..06-30 claim with numeric value 600 and Q2 reported value 600 | SameSubject(Q2,H1)=DIFFERENT | `SUBJECT_MISMATCH` | Q2 period and H1 period | Merge identical numeric values into one subject | `S` | `S1` |
| `A01-C03` / `D-A01-C03` | `B0` | Add independently published same-subject June claim value 300, new assertion A-JUN-PEER, issuer context/identity distinct | SameSubject=SAME; assertion IDs remain distinct | `NONE` | A-JUN-01 and A-JUN-PEER | Merge issuer assertions by equal value | `S` | `S1` |
| `A01-C04` / `D-A01-C04` | `B0` | Remove reporting_scope from second June candidate; no mapping evidence for consolidated vs individual | SameSubject=UNRESOLVED | `BASIS_UNRESOLVED` | second candidate; unresolved mapping | Default unknown scope to consolidated | `S` | `S1` |

### A02 — Claim-Specific Evidence  
**Primary semantic owner:** `S1`  

| Case / delta | Base | Exact isolated delta | Required expected oracle | Expected reason | Required lineage / exclusion | Forbidden behavior | Tier | Owner |
|---|---|---|---|---|---|---|---|---|
| `A02-C01` / `D-A02-C01` | `B0` | Use CV-JUN-01 and SUP-JUN1-PUB with body 300 and exact 07/03 issuance support | June v1 content and issuance attributable | `NONE` | CV-JUN-01 → SUP-JUN1-PUB → A-JUN-01 | Use unrelated support as publication proof | `S/X` | `S1` |
| `A02-C02` / `D-A02-C02` | `B0` | At same source_locator substitute CV-JUN-02 value 310 while attaching only SUP-JUN1-PUB (300/07-03) | 310 lacks inherited 07/03 content-time support | `CONTENT_BINDING_INSUFFICIENT` | Exclude SUP-JUN1-PUB as support for CV-JUN-02 | Carry URL timestamp to changed body | `S` | `S1` |
| `A02-C03` / `D-A02-C03` | `B0` | Add second capture OBS-JUN1-REPEAT 2025-07-16 12:00+08 of identical CV-JUN-01 bytes | Two captures; exactly one issuer publication event | `NONE` | CV-JUN-01; OBS-JUN1-LATE; OBS-JUN1-REPEAT | Invent another publication from reobservation | `S` | `S1` |
| `A02-C04` / `D-A02-C04` | `B0` | Add downstream provider P-X capture showing 300 on 07/16, no independent issuer notice evidence | Provider observation only; not second issuer assertion | `ATTRIBUTION_UNRESOLVED` | P-X capture; issuer attribution unresolved | Fabricate issuer event for forwarded value | `S` | `S1` |

### A03 — Temporal Boundary  
**Primary semantic owner:** `S2`  

| Case / delta | Base | Exact isolated delta | Required expected oracle | Expected reason | Required lineage / exclusion | Forbidden behavior | Tier | Owner |
|---|---|---|---|---|---|---|---|---|
| `A03-C01` / `D-A03-C01` | `B0` | Replace June pub proof by content-bound upper bound 2025-07-06T23:59:59+08:00 CLOSED | SUPPORTED at t0 | `NONE` | bound; CV-JUN-01 | Reject a strictly pre-cutoff bound | `S/M` | `S2` |
| `A03-C02` / `D-A03-C02` | `B0` | Set supported upper bound u=t0 with OPEN semantics | SUPPORTED at t0 | `NONE` | (t0,OPEN); CV-JUN-01 | Treat OPEN equality as late | `S/M` | `S2` |
| `A03-C03` / `D-A03-C03` | `B0` | Set sole supported upper bound u=t0 with CLOSED semantics | UNRESOLVED at t0 | `TEMPORAL_BOUND_INSUFFICIENT` | (t0,CLOSED); no independent earlier proof | Declare known late or early without evidence | `S/M` | `S2` |
| `A03-C04` / `D-A03-C04` | `B0` | Prove precise June publication timestamp equals exactly t0 | NOT_ADMISSIBLE for this publication path | `PUBLICATION_NOT_PRE_CUTOFF` | exact timestamp; publication path | Treat equality as strictly-before | `S/M` | `S2` |
| `A03-C05` / `D-A03-C05` | `B0` | Use independently authenticated date-only publication 2025-07-06 Asia/Taipei; OPEN upper bound next local midnight | SUPPORTED at t0 | `NONE` | (2025-07-07T00:00:00+08:00,OPEN) | Default date-only to 00:00 on release day | `S/M` | `S2` |
| `A03-C06` / `D-A03-C06` | `B0` | Remove time zone for ambiguous 2025-07-07 00:30 publication with plausibly crossing-zone interpretation | UNRESOLVED | `TIMEZONE_UNRESOLVED` | ambiguous timestamp; no default zone | Assume Asia/Taipei or UTC by convenience | `S` | `S2` |
| `A03-C07` / `D-A03-C07` | `B0` | Substitute notice body 310 at same locator, retaining 300 version timestamp only | New body lacks qualifying prior timestamp | `CONTENT_BINDING_INSUFFICIENT` | CV-JUN-02 cannot use SUP-JUN1-PUB | Inherit timing by URL | `S/X` | `S2` |

### A04 — Reconstruction Mode Isolation  
**Primary semantic owner:** `S2`  

| Case / delta | Base | Exact isolated delta | Required expected oracle | Expected reason | Required lineage / exclusion | Forbidden behavior | Tier | Owner |
|---|---|---|---|---|---|---|---|---|
| `A04-C01` / `D-A04-C01` | `B0` | Place issuer 07/03 content and valid publication support in later research observation 2026-01-01, public mode | Public mode temporal SUPPORT may hold; no historic lab capture | `NONE` | CV-JUN-01; issuer release proof; 2026 observation | Claim lab observed 2025 from later verification | `X` | `S2` |
| `A04-C02` / `D-A04-C02` | `B0/OBS` | Use only OBS-JUN1-LATE completion 07/15, ask for observed reconstruction t0 | Not observed-eligible at t0 | `OBSERVATION_AFTER_CUTOFF` | OBS-JUN1-LATE; exclude earlier capture | Substitute issuer time for lab completion | `S/X` | `S2` |
| `A04-C03` / `D-A04-C03` | `B0` | Add new report first published 2025-07-07 07:00, decision at 08:00, info cutoff t0=00:00 | Report NOT_ADMISSIBLE at t0 | `PUBLICATION_NOT_PRE_CUTOFF` | 07:00 release; t0 | Use 08:00 wall-clock as info cutoff | `X` | `S2` |
| `A04-C04` / `D-A04-C04` | `B0` | Execute frozen qualified Q2 computation at 2025-07-07 07:30, no new input | VALUE_AVAILABLE(600); operational availability by 08:00 not presumed | `NONE` | A-APR-01,A-MAY-01,A-JUN-01 | Invalidate qualified info solely for late compute | `X` | `S2` |

### A05 — Revision Non-Retroactivity  
**Primary semantic owner:** `S3`  

| Case / delta | Base | Exact isolated delta | Required expected oracle | Expected reason | Required lineage / exclusion | Forbidden behavior | Tier | Owner |
|---|---|---|---|---|---|---|---|---|
| `A05-C01` / `D-A05-C01` | `B0` | No eligible 07/10 correction in E0 | SELECTED(A-JUN-01,300) | `NONE` | A-JUN-01; SUP-JUN1-PUB; RCPT-E0 | Select future 310 | `X` | `S3` |
| `A05-C02` / `D-A05-C02` | `B1` | Use qualified REL-JUN-01 and CV-JUN-02 in E1 | SELECTED(A-JUN-02,310) | `NONE` | A-JUN-02; SUP-JUN2-PUB; SUP-JUN-REV; RCPT-E1 | Keep obsolete version without policy cause | `X` | `S3` |
| `A05-C03` / `D-A05-C03` | `B3` | Use E1 at earlier t0; 07/10 publication after t0 | SELECTED(A-JUN-01,300) | `NONE` | A-JUN-01; exclude A-JUN-02 at t0 | Backdate correction to t0 | `X` | `S3` |
| `A05-C04` / `D-A05-C04` | `B0` | Replace E0 with isolated E1 view containing independently supported 07/10 REL-JUN-01; remove SUP-JUN1-PUB prior publication proof of old 300 | Old early target UNRESOLVED; relation independently supported at its actual time | `TEMPORAL_BOUND_INSUFFICIENT` | REL-JUN-01 independently; A-JUN-01 early unsupported | Infer old first publication from later correction | `S/X` | `S3` |
| `A05-C05` / `D-A05-C05` | `B0` | Create separate E2 research snapshot: newly discovered issuer correction A-JUN-EARLY-CORR=305 published 07/05 12:00+08, with own content-time proof and explicit relation A-JUN-01→A-JUN-EARLY-CORR; complete bounded receipt; evaluate new M3 at t0 | New M3 SELECTED(305), derived Q2=605; original M0 stays 600 | `NONE` | M3 includes A-JUN-EARLY-CORR and qualified relation; M0 pinned to A-JUN-01 | Mutate original M0 or treat late discovery as late publication | `X/P` | `S3` |

### A06 — Coverage / Conflict  
**Primary semantic owner:** `S3`  

| Case / delta | Base | Exact isolated delta | Required expected oracle | Expected reason | Required lineage / exclusion | Forbidden behavior | Tier | Owner |
|---|---|---|---|---|---|---|---|---|
| `A06-C01` / `D-A06-C01` | `B0` | Change required RCPT-E0 search state COMPLETED to NOT_PERFORMED | UNRESOLVED | `COVERAGE_INSUFFICIENT` | RCPT-E0 incomplete | Treat absent search as empty universe | `S` | `S3` |
| `A06-C02` / `D-A06-C02` | `B0` | Select SUB-B-APR target; certified complete empty source scope and no material leads | NO_QUALIFIED_CLAIM | `NO_QUALIFIED_WITHIN_SCOPE` | RCPT-B-APR-COMPLETE-EMPTY | Generalize bounded absence to whole world | `S` | `S3` |
| `A06-C03` / `D-A06-C03` | `B0` | Add candidate lead L-ALT for same June subject plausibly public before t0 with missing content/time; receipt records material lead | UNRESOLVED | `MATERIAL_CANDIDATE_UNRESOLVED` | L-ALT; materiality rule and receipt | Ignore concrete material unknown | `S` | `S3` |
| `A06-C04` / `D-A06-C04` | `B0` | Add A-JUN-CONFLICT value 315 at 07/03 15:00, independent issuer pub proof; update complete receipt to include it; no revision relation and peer authority | UNRESOLVED | `MATERIAL_CANDIDATE_UNRESOLVED` | A-JUN-01,A-JUN-CONFLICT; no qualifying precedence | Break tie by latest timestamp/ID | `S/M` | `S3` |
| `A06-C05` / `D-A06-C05` | `B0/VAL` | Add independently published issuer A-JUN-PEER value 300 and update completed receipt; select CONTENT_VALUE target; also evaluate same fixture ATTRIBUTED_ASSERTION target | CONTENT_VALUE SELECTED(300) with both origins; ATTRIBUTED_ASSERTION UNRESOLVED if nonunique | `ATTRIBUTION_UNRESOLVED for attributed target` | A-JUN-01,A-JUN-PEER both retained | Merge assertion identities when values coincide | `S` | `S3` |
| `A06-C06` / `D-A06-C06` | `B0` | Required receipt/provider query raises injected read error before completing discovery | OPERATIONAL_ERROR; no normal S3 outcome | `REQUIRED_OPERATION_FAILED` | failed operation receipt and affected scope | Classify failed search as no claim | `S/P` | `S3` |

### A07 — Field-Scoped Revision  
**Primary semantic owner:** `S3`  

| Case / delta | Base | Exact isolated delta | Required expected oracle | Expected reason | Required lineage / exclusion | Forbidden behavior | Tier | Owner |
|---|---|---|---|---|---|---|---|---|
| `A07-C01` / `D-A07-C01` | `B1` | REL-JUN-01 scope exactly SUB-A-JUN; order-count independent subject | Only monthly revenue v1→v2 applicability changed | `NONE` | REL-JUN-01→SUB-A-JUN | Extend relation to all fields in notice | `S/X` | `S3` |
| `A07-C02` / `D-A07-C02` | `B1` | With unchanged orders 7 in CV-JUN-01 and CV-JUN-02, no order-correction evidence | No revision edge for SUB-A-JUN-ORDERS | `RELATION_SCOPE_MISMATCH if asserted` | A-ORD-01,A-ORD-02; exclude order revision edge | Fabricate order revision by document version | `S` | `S3` |
| `A07-C03` / `D-A07-C03` | `B1` | Use new independently attributable A-ORD-02=7 from 07/10 alongside A-ORD-01=7 | Distinct assertion/publication identities | `NONE` | A-ORD-01 and A-ORD-02 | Collapse equal content into same publication | `S` | `S3` |
| `A07-C04` / `D-A07-C04` | `B1` | Add supported withdrawal of A-JUN-02 at 07/11, without restoration of A-JUN-01, no alternative qualified claim | UNRESOLVED under withdrawal applicability policy | `RELATION_UNQUALIFIED for presumed rollback` | withdrawal event; A-JUN-01 not restored | Automatically restore old 300 | `S` | `S3` |

### A08 — Derived Computability  
**Primary semantic owner:** `S4-A/B`  

| Case / delta | Base | Exact isolated delta | Required expected oracle | Expected reason | Required lineage / exclusion | Forbidden behavior | Tier | Owner |
|---|---|---|---|---|---|---|---|---|
| `A08-C01` / `D-A08-C01` | `B0` | Use three selected compatible months 100,200,300, exact integer rule FS-Q2-1 | VALUE_AVAILABLE(600) | `NONE` | A-APR-01,A-MAY-01,A-JUN-01 | Pass solely by coincidental sum using latest input | `S/X` | `S4-A/B` |
| `A08-C02` / `D-A08-C02` | `B1` | Use qualified correction, months 100,200,310 | VALUE_AVAILABLE(610) | `NONE` | A-APR-01,A-MAY-01,A-JUN-02 | Keep old June assertion in late derived lineage | `S/X` | `S4-A/B` |
| `A08-C03` / `D-A08-C03` | `B0` | Delete May claim and change complete May search receipt to empty, no material unknown | NOT_COMPUTABLE; no numeric Q2 | `DEPENDENCY_NOT_COMPUTABLE` | May NO_QUALIFIED_CLAIM; Apr/June selected | Implicitly insert zero or skip month | `S` | `S4-A/B` |
| `A08-C04` / `D-A08-C04` | `B0` | Add material unresolved June competitor with bounded lead as A06-C03 | UNRESOLVED; no numeric Q2 | `DEPENDENCY_UNRESOLVED` | June UNRESOLVED lead; no selected substitute | Use 300 just to finish sum | `S/X` | `S4-A/B` |
| `A08-C05` / `D-A08-C05` | `B0` | Change May selected claim reporting_scope to individual, not consolidated; mapping verifies DIFFERENT | NOT_COMPUTABLE under FS-Q2-1 | `ACCOUNTING_BASIS_INCOMPATIBLE` | May incompatible; Apr/June compatible | Mix consolidation bases for Q2 | `S` | `S4-A/B` |
| `A08-C06` / `D-A08-C06` | `B0` | Replace FS-Q2-1 month list [APR,MAY,JUN] by [APR,MAY,JUN,JUN] with unique-month contract unchanged | CONTRACT_VIOLATION | `INVALID_FEATURE_SPEC` | duplicate June in spec | Double-count June and call it quarter | `S` | `S4-A/B` |

### A09 — Fitted-State & Label Causality  
**Primary semantic owner:** `S4-C`  

| Case / delta | Base | Exact isolated delta | Required expected oracle | Expected reason | Required lineage / exclusion | Forbidden behavior | Tier | Owner |
|---|---|---|---|---|---|---|---|---|
| `A09-C01` / `D-A09-C01` | `B0` | Compute FS-Q2-1 with θ=∅, no fit dependencies | VALUE_AVAILABLE(600); fitting NOT_APPLICABLE | `NONE` | three source months; no synthetic model state | Invent artificial fitted-state proof | `S` | `S4-C` |
| `A09-C02` / `D-A09-C02` | `B0` | Set FIT-0 cutoff t0, training view PRE-T0, dependency on A-JUN-02 first public 07/10 18:30 | Fitted state inadmissible; block affected derived feature | `FUTURE_DEPENDENCY` | FIT-0→A-JUN-02; after fit cutoff | Admit fitted state from future claim | `S/X` | `S4-C` |
| `A09-C03` / `D-A09-C03` | `B0` | Set FIT-0 cutoff t0, dependent label L-0 with explicitly declared maturity 07/12 00:00 | Fitted state inadmissible | `IMMATURE_LABEL` | FIT-0→L-0 maturity after t0 | Use immature target in fit | `S` | `S4-C` |
| `A09-C04` / `D-A09-C04` | `B0` | Specify feature F-CYCLE requires state THETA-CYCLE and THETA-CYCLE requires F-CYCLE | CONTRACT_VIOLATION | `DEPENDENCY_CYCLE` | F-CYCLE↔THETA-CYCLE | Evaluate cyclic information dependency | `S` | `S4-C` |
| `A09-C05` / `D-A09-C05` | `B0` | Target encoder TE-OWN for training-row R1 with own mature binary label=1 returns encoded feature=1 directly from R1 label; no out-of-fold/leave-one-out isolation contract | Cannot certify leakage-safe training feature; deny approval | `WITHIN_SAMPLE_TARGET_LEAKAGE` | TE-OWN→row-own-label | Treat maturity alone as sample isolation | `S` | `S4-C` |

### A10 — Audit Non-Interference  
**Primary semantic owner:** `S4-D`  

| Case / delta | Base | Exact isolated delta | Required expected oracle | Expected reason | Required lineage / exclusion | Forbidden behavior | Tier | Owner |
|---|---|---|---|---|---|---|---|---|
| `A10-C01` / `D-A10-C01` | `B0` | Append audit-only FUTURE_RESTATEMENT_NOTE="revised July10"; keep Q,context,policy fixed | Agent serialized bytes unchanged | `NONE` | same projection from Q and U; future note audit only | Leak future note into payload | `M/X` | `S4-D` |
| `A10-C02` / `D-A10-C02` | `B0` | Edit ONLY explanatory audit coverage-confidence/reason wording without changing normative coverage decision | Allowed missing mask unchanged | `NONE` | same S3 qualified result/branch; audit text excluded | Use retrospective confidence as missingness flag | `M` | `S4-D` |
| `A10-C03` / `D-A10-C03` | `B0` | Toggle audit-only future revision flag with no eligible S3 input change; FS-Q2-1 baseline specifies NO_FALLBACK | Fallback branch remains NO_FALLBACK | `NONE` | same permitted branch predicate | Choose proxy using future flag | `M` | `S4-D` |
| `A10-C04` / `D-A10-C04` | `B0` | Attach later reward/return label to Audit for SYN-B; U0 and grid unchanged | G and sample policy decision unchanged | `NONE` | U0={A,B}; all four grid rows | Delete losing firm or adjust sample | `M/X` | `S4-D` |
| `A10-C05` / `D-A10-C05` | `B0` | Attempt to replace U0 with current survivor subset {SYN-A} in rank/projector while declared Universe pin still UNI-1 | CONTRACT_VIOLATION; reject unpinned Universe substitution | `INVALID_UNIVERSE_POLICY` | UNI-1; excluded survivor list | Silently omit SYN-B | `S/X` | `S4-D` |

### A11 — Missingness & Failure Integrity  
**Primary semantic owner:** `S4-D / Shared`  

| Case / delta | Base | Exact isolated delta | Required expected oracle | Expected reason | Required lineage / exclusion | Forbidden behavior | Tier | Owner |
|---|---|---|---|---|---|---|---|---|
| `A11-C01` / `D-A11-C01` | `B0` | Replace April claim by valid pre-t0 0 with own content/support and maintain complete receipt | VALUE_AVAILABLE(0) at source; Q2=500, not missing | `NONE` | qualified zero April; May200; June300 | Interpret numerical 0 as unknown | `S/X` | `S4-D / Shared` |
| `A11-C02` / `D-A11-C02` | `B0` | Delete May claim, update fully completed May receipt to empty; P-OBS-1 expressly allows neutral missing for this case | NOT_COMPUTABLE; publication PUBLISHED_WITH_ALLOWED_MISSING | `DEPENDENCY_NOT_COMPUTABLE` | missing token only; May NO_QUALIFIED_CLAIM in audit | Auto-zero or leak detailed reason in agent payload | `S/X` | `S4-D / Shared` |
| `A11-C03` / `D-A11-C03` | `B0` | Add evidence-grounded material June unknown as A06-C03; strict core feature policy | UNRESOLVED; research COMPLETED; agent WITHHELD | `DEPENDENCY_UNRESOLVED` | June lead and unresolved reason in audit only; grid row kept | Emit ordinary neutral missing or delete grid row | `S/X` | `S4-D / Shared` |
| `A11-C04` / `D-A11-C04` | `B0` | Select nonexistent required feature spec FS-UNKNOWN with no registered definition | CONTRACT_VIOLATION; run FAILED | `INVALID_FEATURE_SPEC` | invalid spec ref in engineering/audit | Publish None as normal missing | `S/P` | `S4-D / Shared` |
| `A11-C05` / `D-A11-C05` | `B0` | Inject read failure for a required persisted input after freeze begins | OPERATIONAL_ERROR; run FAILED | `REQUIRED_OPERATION_FAILED` | failed input read and safe diagnostic ref | Return zero/missing/NO_QUALIFIED_CLAIM | `P` | `S4-D / Shared` |
| `A11-C06` / `D-A11-C06` | `B0` | Inject failure before finalization COMMIT after manifest/result and before completion/observation authorized | No COMPLETED and no visible agent payload | `REQUIRED_OPERATION_FAILED` | transaction rollback; incomplete attempt recorded safely | Expose partial success | `P` | `S4-D / Shared` |

### A12 — Deterministic Replay  
**Primary semantic owner:** `Shared Manifest`  

| Case / delta | Base | Exact isolated delta | Required expected oracle | Expected reason | Required lineage / exclusion | Forbidden behavior | Tier | Owner |
|---|---|---|---|---|---|---|---|---|
| `A12-C01` / `D-A12-C01` | `B2` | Replay same sealed M0 without source rediscovery; identical versions, numeric and serializer | 600; exact canonical value/lineage/payload equivalence | `NONE` | M0; A-APR-01,A-MAY-01,A-JUN-01 | Use a fresh latest-source query | `X/P` | `Shared Manifest` |
| `A12-C02` / `D-A12-C02` | `B2` | Append CV-JUN-02 and REL-JUN-01 to database after original M0 committed, then replay M0 | 600 and original M0 lineage unchanged | `NONE` | E0 pinned; exclude new E1 artifacts | Substitute 310 during replay | `P` | `Shared Manifest` |
| `A12-C03` / `D-A12-C03` | `B1` | Evaluate new M1 based on E1 with late cutoff t1 | 610 with new manifest identity | `NONE` | A-JUN-02 and qualified REL-JUN-01 | Write 610 into M0 record | `X/P` | `Shared Manifest` |
| `A12-C04` / `D-A12-C04` | `B3` | Evaluate t0 anew with E1, supported 07/10 event strictly after t0 | 600 under different M2 identity | `NONE` | M2 != M0; June old at t0 | Equate new context with old manifest | `X/P` | `Shared Manifest` |
| `A12-C05` / `D-A12-C05` | `B2` | Replace stored CV-JUN-01 V1 300 bytes with V2 310 bytes while keeping CV-JUN-01 ID/digest reference | Replay BLOCKED: PINNED_INPUT_INVALID | `PINNED_INPUT_INVALID` | M0→CV-JUN-01 V1 fingerprint | Recalculate and accept corrupted bytes | `S/P` | `Shared Manifest` |
| `A12-C06` / `D-A12-C06` | `B2` | Use two PostgreSQL connections: reader freezes first membership; writer commits new version/edge between necessary reads | Coherent E0 snapshot; no hybrid input set | `NONE` | one pinned committed read view | Mix pre/post writer state | `P` | `Shared Manifest` |
| `A12-C07` / `D-A12-C07` | `B0` | Inject failure in atomic finalization before commit after one dependent write | No externally COMPLETED manifest/result/agent publication | `REQUIRED_OPERATION_FAILED` | rolled-back transaction / hidden provisional write | Show partial canonical result | `P` | `Shared Manifest` |
| `A12-C08` / `D-A12-C08` | `B2` | Change DB row enumeration and append unrelated receipt for non-target issuer with M0 fixed | Same status, value, pinned lineage and canonical agent bytes | `NONE` | M0 ordering policy; unrelated append excluded | Use arrival order as winner/tie-break | `M/P` | `Shared Manifest` |

### 5.2 Independent oracle, determinism and reason mapping rules

1. Oracle input is only the approved BASE fixture, named Delta, Context and S1–S4 policy versions. The under-test selector/feature evaluator cannot read expected-result files. Any `PASS` requires both the Expected outcome **and** all listed prohibitions, including source lineage; a coincidentally equal value is insufficient.
2. Every `D-Axx-Cyy` has a unique identity and inherited base context. If a case changes a claim's evidence or a receipt, its specific delta must pin the change to the new case membership rather than mutate BASE-0. Fault injections are part of expected test orchestration and do not become source assertions.
3. The reason vocabulary is versioned, layer-relative. `NONE` represents successful ordinary cases. Normative temporal statuses are not booleans. Example categories `SUBJECT_MISMATCH`, `BASIS_UNRESOLVED`, `CONTENT_BINDING_INSUFFICIENT`, `TIMEZONE_UNRESOLVED`, `COVERAGE_INSUFFICIENT`, `MATERIAL_CANDIDATE_UNRESOLVED`, `DEPENDENCY_UNRESOLVED`, `FUTURE_DEPENDENCY`, `DEPENDENCY_CYCLE`, `INVALID_FEATURE_SPEC`, `REQUIRED_OPERATION_FAILED`, `PINNED_INPUT_INVALID` are *acceptance labels*; runtime naming may differ provided a reviewed one-to-one or explicit many-to-one semantic mapping retains auditable distinctions.
4. A materially incomplete/unknown candidate can cause `UNRESOLVED` only if a source- and target-scoped, evidenced credible as-of possibility could affect selection. Modern-only discrepancies do not veto by default. S3's `NO_QUALIFIED_CLAIM` needs an adequate, bounded completed search, not just a zero-length database table.
5. Direct same-cutoff replay of M0 and fresh t0 reconstruction under E1 are different tests. New historical-publication evidence may legitimately change a **new** t0 reconstruction and manifest without changing M0. `S4` consumes typed S3 selection; it cannot query latest source or independently qualify revisions.

## 6. Reconstruction manifest and numerical contract (RP-02)

Logical reconstruction context `C=(R,E,M,π,t,μ)` includes source/capture set, evidence/support/relation set, subject mapping, versioned policies, strict info cutoff, and public/observed mode. A complete **manifest** transitively pins:

1. artifact bytes/digests and immutable content-version IDs; all source observations, claims, supports and scoped relations; actual candidate Q/U/X sets;
2. search scope, result membership, completion and materiality/coverage policy and receipt IDs;
3. issuer/metric/time mapping, historical event precision, timezone, upper-bound openness and mode;
4. target `CONTENT_VALUE` or `ATTRIBUTED_ASSERTION`, selection/conflict/revision rules, evaluator identity;
5. synthetic calendar version, shared Universe/decision grid, feature calculation population and rule versions;
6. feature spec DAG, fitted-state inputs and training view when applicable (θ=∅ if no fit), label maturity;
7. numeric type, units, rounding, order, missingness, projection allowlist, serializer and schema versions;
8. completed output association, canonical-result definition, execution provenance stored separately.

`manifest_id` is the content-based identity of the **whole canonical manifest payload** (its own digest excluded from its hashed body); `reconstruction_id`/`run_id` denotes an attempt; `result_id` refers to an associated semantic research result; `publication_key` identifies a unique formally consumable payload. Independent versions and dependencies must be content- or immutable-ID-bound. A Git commit hash or source URL alone is not sufficient replay provenance.

**Canonical result comparison:** signed integers (in NTD thousands) must match exactly; expected values `600`/`610` are not floating approximations. In-scope serialized agent payload must match canonical bytes under pinned schema/ordering and allowlist; run-specific diagnostics/time/IDs are excluded from the canonical payload and kept in separately protected audit/execution metadata. Floating tolerances, distributed event semantics and larger numerical libraries require future contract amendments, not implicit adoption.

## 7. Persistence, freeze, atomic publication and recovery — RP-01…RP-06

### 7.1 First physical acceptance design

**Synthetic-only** small content/artifacts and their versions are stored within the guarded **Test PostgreSQL** domain; no external object store or cross-store transaction is assumed. This is a requirement for future implementation acceptance, not a claim that the current CAP-F1 repository contains these tables.

**Freeze → Evaluate → Finalize → Publish/Replay**:

- **Freeze:** a bounded `REPEATABLE READ READ ONLY` PostgreSQL transaction enumerates *all* necessary committed records in a single consistent MVCC snapshot. Before transaction exit, freeze complete required bytes or verified immutable references and complete membership. Pin receipt results and dependencies; fail if incomplete. MVCC isolation alone neither authenticates sources nor makes external content immutable.
- **Evaluate:** close the read transaction; evaluate solely from complete pinned membership, bytes and versioned rules. No late source lookup, no silent source addition or current-policy substitution; absence/corruption results in a blocking failure.
- **Finalize:** one PostgreSQL write transaction validates pinned integrity and atomically stores the complete manifest/result, necessary Audit association, authorized agent projection (if any), and completed marker. All consumers must filter to an atomically committed, authorized state; partial writes are never visible as completed success.
- **Replay:** load M0's exact members and versions, revalidate bytes and execute without source discovery. Newly appended E1 cannot change M0. A new historical reconstruction uses a newly identified manifest even with the same t0 cutoff.

**Immutable storage privileges:** Migration is authorized only by a separately approved gate; runtime roles MUST NOT be able to update/delete finalized content versions, receipts, claims, manifests or completion results through their ordinary access paths. Necessary immutable objects may be enforced through schema constraints, reviewed privileges and narrowly scoped application operations. Admin/migrator compromise is outside the accepted trusted-team threat model; protection against hostile code with arbitrary Python/DB access is not implied.

### 7.2 Publication, idempotence and commit-unknown recovery

`ResearchCompleted(r)` and `AgentPublished(r)` are distinct. A research result may complete with S3 `UNRESOLVED`, with audit intact and Agent projection withheld; an operation or contract failure cannot complete normally. The published payload MUST be tied to completed research and an allowlisted, serializable projection.

Define the stable logical **publication key** as the canonical hash of `(manifest identity, grid/target publication scope, projection policy+schema versions)`; protect uniqueness at persistence boundary. Same publication key and different canonical result **is an integrity conflict**, never an overwrite. Different `run_id` values may replay a manifest, but must not create contradictory canonical publications.

When the client loses commit acknowledgment: query the stable publication key on an authorized fresh connection; if the completed committed record exists, verify manifest, status, digest and associations; if absent and database state is verifiably settled, retry under idempotent uniqueness; if still indeterminate, keep `UNCONFIRMED` and fail closed. Do **not** assume rollback or create an uncontrolled second publication. This is single-DB idempotent commit recovery, not distributed exactly-once delivery.

### 7.3 Publication, audit and sample-boundary semantics (G4-R04)

Synthetic `U_t = {SYN-A,SYN-B}` is the **Benchmark Universe** for each cutoff. The fixed decision grid has four rows `(t0,A),(t0,B),(t1,A),(t1,B)`. A feature population `P_t^φ` is separately derived by predeclared legitimate availability rules; it MUST NOT redefine U or silently drop a grid row. Withholding an Agent observation also MUST NOT erase an entity/week from audit or the benchmark grid.

| Valid research or failure status | Completion | Agent-facing publication | Grid/Universe |
|---|---|---|---|
| `VALUE_AVAILABLE(x)` (including legitimate `0`) | completed | `PUBLISHED` with allowlisted value | retained |
| `NOT_COMPUTABLE` with explicitly approved neutral missing | completed | `PUBLISHED_WITH_ALLOWED_MISSING`, no reason leakage | retained |
| `UNRESOLVED`, strict core feature | completed research with audit | `WITHHELD` (no ordinary market-missing proxy) | retained |
| `CONTRACT_VIOLATION` / `OPERATIONAL_ERROR` | failed / not ordinary completed | no agent payload | retained, with safe failure evidence |
| finalization failure | no complete publication | no agent payload | retained, with separate attempt outcome |

Audit-only annotations (future revisions, post-hoc performance, coverage confidence wording) may not affect *serialized agent bytes, masks, fallbacks, approved population, universe, sample inclusion/exclusion*. The non-interference relation is conditional on identical qualified S1–S4 inputs and policy. Genuine newly eligible evidence creates a **new reconstruction context**, not an audit-only mutation. A fixed retrospective missingness policy does **not** prove actual historical market missingness, nor unbiased downstream evaluation.

### 7.4 Persistence acceptance case registry — RP-01…RP-06

Each listed test has a predeclared fault/interleaving and independently reviewed oracle. `P` requires actual guarded **Test PostgreSQL**; mocks alone cannot pass it. Several tests intentionally reuse the A01…A12 corpus/deltas and may share one integration setup; no separate service or ingestion framework is required.

#### RP01 — Canonical Fixture & Immutable Content

| Test | Fixed fault or interleaving | Required oracle / forbidden shortcut | Tier |
|---|---|---|---|
| `RP01-T01` | Bind CV-JUN-01 to V1 then attempt to rebind to V2 | Reject same-content-version identity collision; no published content mutation | `S/P` |
| `RP01-T02` | Tamper V1 value bytes while retaining original V1 digest | PINNED_INPUT_INVALID/integrity failure | `S/P` |
| `RP01-T03` | Shuffle only object key input ordering | Canonically identical 118 bytes and V1 digest | `S` |
| `RP01-T04` | Reorder a schema-tagged ordered events array | New canonical meaning/identity, not silently identical | `S` |
| `RP01-T05` | Omit required named timezone or content_version_id | CONTRACT_VIOLATION; do not default | `S` |
| `RP01-T06` | Attempt evaluator read of Expected Oracle fixture | Boundary violation; fail harness inspection | `S` |

#### RP02 — Frozen Manifest Completeness

| Test | Fixed fault or interleaving | Required oracle / forbidden shortcut | Tier |
|---|---|---|---|
| `RP02-T01` | Load same complete sealed M0 twice | Same manifest identity/membership and approved oracle | `S/P` |
| `RP02-T02` | Append June v2 after M0 finalization | M0 membership/digest immutable | `P` |
| `RP02-T03` | Create M2 at t0 from E1 | M2 differs from M0 even if value both 600 | `S/P` |
| `RP02-T04` | Omit evaluator_version or π revision from manifest | Reject incomplete replay manifest | `S` |
| `RP02-T05` | Change feature spec or projector version in new manifest | Different identity; original untouched | `S` |
| `RP02-T06` | Delete required immutable artifact reference | PINNED_INPUT_INVALID; no latest fallback | `P` |
| `RP02-T07` | Retain SUP-JUN-REV ID but discard its referenced content version | Manifest transitive-completeness failure | `S/P` |

#### RP03 — Consistent Freeze & Concurrent Append

| Test | Fixed fault or interleaving | Required oracle / forbidden shortcut | Tier |
|---|---|---|---|
| `RP03-T01` | Reader first SELECT starts RR snapshot; writer commits June v2 before reader second SELECT | Reader consistent E0 membership; no hybrid | `P` |
| `RP03-T02` | Writer commits June v2 before reader establishes snapshot | Reader may see complete E1 but time selector still controls t0/t1 | `P` |
| `RP03-T03` | Add evidence after freeze completion | Previously pinned membership immutable | `P` |
| `RP03-T04` | Writer appends independent unrelated artifact | No change to M0 result or pinned lineage | `P` |
| `RP03-T05` | Inject DB query failure between necessary reads | No complete frozen manifest published | `P` |
| `RP03-T06` | Writer inserts uncommitted relation when reader queries | Reader never treats uncommitted relation as admitted | `P` |

#### RP04 — Atomic Finalization & Recovery

| Test | Fixed fault or interleaving | Required oracle / forbidden shortcut | Tier |
|---|---|---|---|
| `RP04-T01` | Manifest insert fails inside finish transaction | No completed result/observation | `P` |
| `RP04-T02` | Result insert fails after provisional manifest insert | No completed result/observation | `P` |
| `RP04-T03` | Single allowlisted serializer fails before commit | No invalid/partial agent payload publication | `P` |
| `RP04-T04` | Audit association insert fails before commit | No completed result | `P` |
| `RP04-T05` | Completion marker insert/update fails | No visible completed publication | `P` |
| `RP04-T06` | Force transaction abort before commit | All provisional formal writes roll back | `P` |
| `RP04-T07` | Commit succeeds but client acknowledgment lost | Query publication key; exactly one matching completed publication | `P` |
| `RP04-T08` | Two workers concurrently finalize same stable publication key | Unique coherent outcome; no conflicting completed duplicate | `P` |

#### RP05 — Agent/Audit Boundary & Privileges

| Test | Fixed fault or interleaving | Required oracle / forbidden shortcut | Tier |
|---|---|---|---|
| `RP05-T01` | Insert future-revision explanatory audit note only | No changes in canonical agent bytes/mask/branch | `M/P` |
| `RP05-T02` | Toggle post-hoc reward for SYN-B only | No change in U0/grid/sample decision | `M/P` |
| `RP05-T03` | Attempt agent request to raw issuer/support/audit/engine error fields | Access refused; only allowlisted payload exposed | `P` |
| `RP05-T04` | Attempt ordinary runtime UPDATE/DELETE of finalized version/manifest | Refused by protected DB privileges/constraints | `P` |
| `RP05-T05` | Attempt publish WITHHELD unresolved core feature as neutral missing | Fail projection policy; grid row remains recorded | `X/P` |

#### RP06 — Replay, Ordering & Injected Failures

| Test | Fixed fault or interleaving | Required oracle / forbidden shortcut | Tier |
|---|---|---|---|
| `RP06-T01` | Replay M0 from pinned content | 600, exact approved lineage and canonical payload | `X/P` |
| `RP06-T02` | Append correction then replay unchanged M0 | 600, no new-version substitution | `P` |
| `RP06-T03` | Evaluate new M1 at t1/E1 | 610 and distinct M1 identity | `X/P` |
| `RP06-T04` | Evaluate new M2 at t0/E1 | 600 under this controlled corpus, M2≠M0 | `X/P` |
| `RP06-T05` | Substitute V2 altered bytes for CV-JUN-01 pinned by M0 | BLOCK PINNED_INPUT_INVALID | `P` |
| `RP06-T06` | Remove required support referenced by M0 | BLOCK PINNED_INPUT_INVALID | `P` |
| `RP06-T07` | Replace pinned selector policy by currently latest version | Block version mismatch, no silent upgrade | `S/P` |
| `RP06-T08` | Append unrelated receipt | Same M0 output | `M/P` |
| `RP06-T09` | Permute DB row enumeration while respecting pinned set | Identical canonical selection/lineage/output | `M/P` |
| `RP06-T10` | Change only future audit note and retrospective confidence wording | Agent bytes/masks/fallback/population unchanged | `M/P` |
| `RP06-T11` | Interleave writer commit between reader reads | One consistent frozen membership | `P` |
| `RP06-T12` | Abort before atomic completion | No partial completed data/agent payload | `P` |
| `RP06-T13` | Lose commit acknowledgment and recover under same publication key | No duplicate or contradiction | `P` |
| `RP06-T14` | Required pinned content loader throws | Blocking operational error; no latest fallback | `P` |

### 7.5 Real PostgreSQL / CAP-F1 guard conditions

The actual future integration evidence MUST demonstrate bounded in-process multi-connection barriers, real MVCC snapshots, row/constraint/grant enforcement, controlled injected rollback, unique publication completion and replay after insertions. Pure mock/transaction stubs are not a substitute. Future tests use the reviewed disposable **Test** database, not Dev reset; no weakened existing environment-identity guards, arbitrary migration heads, privilege escalation, uncontrolled `xdist` or cross-process parallel writes. If the existing pool/timeouts block a test, first document the concrete bound/observation and review a narrowly scoped mitigation; do not silently relax platform security. Domain migrations, data model, indexes and actual transaction adapters are **future authorized implementation decisions** subject to the frozen behavioral oracles.

## 8. Agent-safe serialization and evaluation limits

Only the authorized projector may construct the serialized Agent Observation; it consumes qualified S3/S4 results, a single versioned Universe and allowlisted schema. The v1 allowlisted schema contains **exactly** (`decision_cutoff`, `derived_q2_revenue`, `entity_id`, `observation_schema_version`) as canonical sorted keys; the version string is `agent-obs-v1`, the approved neutral missing is JSON `null` **only for `NOT_COMPUTABLE` with allowed neutral-missing policy**, and values otherwise are signed integers in NTD thousands. `WITHHELD` means no ordinary serialized payload at all. Source assertion IDs, coverage-confidence reasons, content digests, future restatement flags, labels, rewards, SQL traces and runtime faults stay in Audit/engineering envelopes. The schema pin fixes field order, row order, missing token and numeric encoding before byte-equivalence claims.

**Golden Agent Payload Vectors** (canonical UTF-8 JSON, no trailing newline):

Early SYN-A / t0: `{"decision_cutoff":"2025-07-07T00:00:00+08:00","derived_q2_revenue":600,"entity_id":"SYN-A","observation_schema_version":"agent-obs-v1"}` (136 bytes; SHA-256 `35eae53179a9912740635da733a41e0ddb31d62759b60e06adfe1f98441dbafa`).

Late SYN-A / t1: `{"decision_cutoff":"2025-07-14T00:00:00+08:00","derived_q2_revenue":610,"entity_id":"SYN-A","observation_schema_version":"agent-obs-v1"}` (136 bytes; SHA-256 `bf25ac7667200b840d5d35c86c22617079ac9cb14f917e512b1cf15952cdbdd9`).

Allowed-missing SYN-B / t0: `{"decision_cutoff":"2025-07-07T00:00:00+08:00","derived_q2_revenue":null,"entity_id":"SYN-B","observation_schema_version":"agent-obs-v1"}` (137 bytes; SHA-256 `af668b4116853c4512a53bf2f299eea4d69f3ab2dc749f36cfbea1f491db3b3b`). Here `null` is a policy-allowed neutral missing after the synthetic adequate empty `SUB-B-APR` search, **not** a representation of unresolved or infrastructure failure. If the complete derived dependency plan cannot certify the corresponding `NOT_COMPUTABLE`, the payload is withheld instead.

For a fixed qualified input `Q`, fixed universe and policy, changes to unapproved audit-only annotation `A` MUST NOT change **bytes, masks, fallback branches, calculation/benchmark population or sample inclusion**: `Project(Q,A1)=Project(Q,A2)`. The predicate does not prohibit legitimately new historical evidence from producing a separately identified research context and outcome. Sample inclusion/exclusion decisions are governed by independently approved downstream evaluation policy; a withheld observation never silently rewrites the benchmark grid. Fixed retrospective evidence policies can still create coverage-selection bias compared with the information actual traders saw; the Golden Suite does not certify unbiased ML evaluation.

## 9. Execution, CI, evidence, and independent review obligations

| Tier | Minimum proof | Allowed claim after real PASS |
|---|---|---|
| Semantic (`S`) | independent oracle vs typed S1–S4 rules; negative statuses; precise time/identity/field cases | listed semantic cases only |
| Metamorphic (`M`) | controlled audit-only changes; ordering invariance; equality/boundary properties | specified transformations only |
| Cross-layer (`X`) | one shared pipeline with 600→610, independent correction relation, missingness and projector | tested synthetic cross-layer behavior |
| Persistence (`P`) | real Test PostgreSQL: frozen membership, append interleaving, rollback, privileges, idempotence, persisted replay | tested storage/transaction behavior |

Each run evidence includes tested repository commit and migration revision, run identity, exact spec and corpus versions/digests, case IDs, expected and actual typed status/reason/value/lineage/payload digest, fault/interleaving trace, relevant DB consistency/rollback/permissions evidence, terminal status `PASS/FAIL/NOT_EXECUTED/BLOCKED`, cleanup outcome and independent review disposition. Results MUST show true nonempty test selection; unauthorized live provider access and implicit skips are not evidence. A missing Test DB or absent domain schema is `BLOCKED/NOT_EXECUTED`, not a program PASS or an observed repository regression. Security-sensitive connection strings and secrets MUST NOT be included in reported evidence.

Pass accounting MUST distinguish every one of the **64** A-cases and **46** RP tests by identifier, while physical test functions and reused setups can be fewer. A case only passes after every required verification tier and forbidden-behavior assertion pass. Integration tests may be staged after authorization, but none may be called `PASS` now. A future code implementation with passing unit tests but unexecuted real PostgreSQL freeze/finalization tests has **not** met the full engineering acceptance contract.

## 10. Known limits and deferred work

- **Real source admission:** G3-R1 P0-002 only conditionally supports historical content-time and intentionally retains metadata-first source-use boundaries. Authentic issuer publication/version custody, real source rights, archive replay, historic Universe coverage and source freeze remain independent blockers; synthetic bytes/hashes cannot cure them.
- **No performance certification:** PIT-causal features do not establish leakage-free model selection, robust out-of-sample evaluation, predictive value, fair comparison of RL/ML families, real financial returns or production trading correctness.
- **No operational certification:** 08:00 runtime availability, live ingestion latency, monitoring, recovery from infrastructure failure, deployment security and throughput are not proven by these offline fixtures. The historical 00:00 feature cutoff is not the 08:00 execution timestamp.
- **Security threat limit:** first design assumes trusted application/operators and guarded Test/PostgreSQL roles; it does not isolate deliberately hostile arbitrary agent code with filesystem or DB access.
- **Numeric/format limits:** restricted ASCII JSON and exact signed-integer features cover only this initial artificial corpus; real company names, decimals, scientific or financial currencies, IFRS taxonomies and complex fitted transforms need separate versioned semantic contracts and tests.
- **Coverage policy limit:** synthetic `COMPLETED/SUFFICIENT` receipts are exhaustive *inside their fictional declared scope*, not globally complete financial archives. “No qualified claim” does not prove nonexistence to all past market participants.

## 11. Freeze-control and formal sign-off protocol

### 11.1 Traceability of approved decisions and remediation

| Decision group | Accepted invariant now expressed by |
|---|---|
| `G4-D01…D06` | one corpus, two fictional issuers, independent evidence IDs, independent oracle, 600→610 + replay, real-source separation (§3–5) |
| `G4-D07…D12` | 12 families/64 case IDs, explicit per-case oracle/forbidden/tier, four context identities, reason vs blocking, full audit non-interference (§5, §8) |
| `G4-D13…D20` | versioned JSON/digests, full pinned manifest, bounded consistent freeze, atomic publication, replay integrity, single projector, real DB tests and design-only boundary (§4, §6–9) |
| `G4-AJ01…AJ06` | integrated consistency acceptance, P1 remediation, P2 clarification, no premature freeze, single final spec, no unauthorized code/source freeze (§1–11) |
| `G4-R01` (P1) | 64-case Base/Delta/Context/Outcome/Reason/Lineage/Forbidden/Tier registry (§5) |
| `G4-R02` (P1) | restricted canonical profile, verified byte/digest vectors and clear version identity (§4) |
| `G4-R03` (P1) | PostgreSQL-contained test evidence, consistent read, finalization and commit-unknown recovery (§7) |
| `G4-R04` (P1) | Universe ≠ Grid ≠ feature population ≠ publication, audit-only non-interference (§7–8) |
| `G4-R05…R07` (P2) | reason labels distinct from statuses; exact numeric/time domain; bounded ability claims (§2, §4, §9–10) |

### 11.2 Final Specification Freeze Checklist

- [ ] Verify all **64** A-case rows have fixed base, unique explicit delta, owner, context, expected typed value/reason/lineage, forbidden behavior and tier.
- [ ] Verify all **46** RP test IDs map to the stated immutable, consistency, publication, security or replay requirements.
- [ ] Independently verify canonical V1/V2 bytes, byte count and SHA-256; check that fixture/expected oracle access remains isolated.
- [ ] Verify the four context oracles: `(t0,E0)=600`, `(t1,E1)=610`, `Replay(M0)=600`, `(t0,E1)=600` (this artificial bounded world only).
- [ ] Verify `UNRESOLVED / NO_QUALIFIED_CLAIM / NOT_COMPUTABLE / WITHHELD / CONTRACT_VIOLATION / OPERATIONAL_ERROR` retain separate meanings and correct information visibility.
- [ ] Verify G4-R01…R07 cross-references are resolved without new semantic owner, source-admission claim or modified Gate 1/2 approvals.
- [ ] Complete independent Final Contract Freeze Review and record the user's explicit sign-off, exact v1.0 filename/digest and date.

### 11.3 Amendment/approval record

**As issued:** `SPECIFICATION_PREPARED_FOR_FINAL_FREEZE_REVIEW`; no `GATE_4_FROZEN` signature is implied. Upon separate user approval after checklist review, record `CAP-F2 GATE_4 = GOLDEN_ACCEPTANCE_SPECIFICATION_FROZEN`, exact content digest, approver, effective date and frozen reference. Subsequent changes require a documented amendment with changed case IDs, old/new oracle, source semantic owner, regression impact, version increment, independent review and explicit approval. An implementation agent may not unilaterally change the frozen oracle, selected data boundary or required negative tests.

**Engineering implementation authority:** `NOT_GRANTED`. Separate Gate 5 planning, user authorization, branch/migration/test security review and independent engineering acceptance are required. Gate 3 real-source freeze remains independently blocked.

---

**End of CAP-F2 Gate 4 — Golden Acceptance Specification v1.0 (prepared for final review).**

