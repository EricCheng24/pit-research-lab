# Five-schema S1 semantic candidates v0.1

Task `MVP-F2-WU05-RSF02-S1`. Baseline Academic `main` `919236a3ee6d0c83a41251a363ff736b7c50d5f7` (PR #29). **S1_CANDIDATE / NON_OPERATIVE / NOT_RATIFIED.** Five Owner-selected directions, zero S1 approvals, zero approved bodies, zero issued resources, zero rights, zero Native replay or consumer acceptances. Authoring authority is the supplied `MVP-F2-WU05-RSF02-S1_Requirements_v0.1.md` (pin below) and execution prompt, not an adoption receipt.

The requirements' S1-R01..R12 and Gates A..G govern this packet. Evidence files are external, with raw source lines, helper snippets, AST inventories and static checks; no semantic tests, production imports or Native calls are executed. Candidate test inputs are requirements, not approved Resource Body bytes/Golden/ReferenceEnvelopes.

## Evidence classes, authority and historical overlay

| Class | Meaning |
|---|---|
| CURRENT_IMPLEMENTATION | Observed source only; no operational authority. |
| RATIFIED_INTERFACE_RULE | ACCEPTED_CONTRACT in requirements terminology: Owner-ratified interface rule under RT01; independent engineering/operational proof is separate. |
| PROJECT_OWNER_DIRECTION | OWNER_SELECTED_DIRECTION: RSF02-D project scope/direction, never S1 adoption. |
| S1_CANDIDATE | PROPOSED_FOR_S1: author proposal awaiting attributable Owner and independent review. |
| MISSING_OWNER_PROOF | REQUIRES_OWNER_PROOF: accountable role/evidence absent; names are responsibilities, not appointments. |
| BLOCKED | OPEN_BLOCKER: affected promotion must refuse. |


Precedence: explicitly ratified cross-team interface/UX rules → accepted project-level RSF02-D direction within delegated authority → separately evidenced domain-owner semantics → observed Draft implementation → author proposal. Shared RT01 L666–762 and UX L129–143 distinguish actual Owner-ratified interface rules from missing independent/domain/runtime proof. Earlier candidate/PENDING wording is preserved history. PR #29 integration at `919236a3ee6d0c83a41251a363ff736b7c50d5f7` is a separate provenance overlay of the decision documents, whose embedded baseline remains `ce3393df09d1b9126c9b78e854a7f8f44bd37da6`; no historical file is rewritten or retroactively signed.

RSF02-D contains exactly 17 schema decisions: 5 SELECT_BOUNDED_SCHEMA_DIRECTION / 9 REQUIRE_INVARIANTS / 3 DEFER_SCHEMA_SEMANTICS, plus four cross-owner requests. Its adoption/body/issuance flags remain false. The other twelve Draft roles and B01–B04 are dependencies only. Source registry below and external source-pins report provide actual raw SHA-256, blob SHA-1, exact line content and byte length for each cited range. Classification does not upgrade an implementation observation to a ratified body schema.

## Shared exact Draft helper contracts

### Draft wrapper / record / parse_body — CURRENT_IMPLEMENTATION

Both mandatory, exact role-specific rs-spec-<role-kebab>-body-proposal-v0.1 and 0.1-DRAFT-NON_ISSUED. No canonical_profile_version added to a Draft body. record() compares exact key sets; field listing order is not wire key order. parse_body/parse_reference_body/validate_body_key compare role/schema/version structurally, not content authenticity. DraftBody retains supplied raw bytes and fields() returns a fresh parse.

Sources: `src/pit_research_lab/mvp/f2/resource_bodies.py:L43–L57` (pin in source register); `src/pit_research_lab/mvp/f2/resource_bodies.py:L502–L592` (pin in source register).

### strict_json / closed / literal / items / text — CURRENT_IMPLEMENTATION

Raw bytes 1..16777216; UTF-8 JSON object; duplicate keys at any object level rejected before map construction; NaN/Infinity refused. Exact field sets, no extension bag, no omitted or null replacements for these required fields. literal checks exact Python type and value (true != 1). items accepts list length 1..4096; it does not sort or de-duplicate. text is exact str, 1..65536 UTF-8 bytes by default, preserves Unicode, no trimming/coercion; invalid surrogate rejected on text validation. Draft transport parsing is not CAN canonical-byte acceptance or normative depth conformance.

Sources: `src/pit_research_lab/mvp/f2/resource_contracts.py:L89–L138` (pin in source register); `src/pit_research_lab/mvp/f2/resource_contracts.py:L345–L368` (pin in source register); `src/pit_research_lab/mvp/f2/resource_bodies.py:L51–L64` (pin in source register); `src/pit_research_lab/mvp/if03/canonical_codec.py:L61–L99` (pin in source register).

### ParentRef<SOURCE-BYTES> / parent — CURRENT_IMPLEMENTATION

Exact six fields: domain_tag=PITLAB/ACADEMIC/SOURCE-BYTES/candidate-v0.1; object_schema_version=source-bytes-candidate-v0.1; canonical_profile_version=typed-json-candidate-v0.1; digest_algorithm=SHA-256; canonical_payload_byte_length=UInt64 with 1..16777216; digest_hex exactly 64 lowercase hexadecimal characters. Length is canonical payload length, not raw resource-body length. Raw bytes must later independently match SOURCE-BYTES body_byte_length/body_sha256, canonical payload/frame/envelope and approved semantics. No locator/capability/own envelope in the parent. A plausible six-field claim is unissued/unverified and does not prove bytes, origin, rights or freshness.

Sources: `src/pit_research_lab/mvp/f2/resource_contracts.py:L128–L170` (pin in source register); `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L461–L465` (pin in source register); `src/pit_research_lab/mvp/if03/typed_references.py:L97–L137` (pin in source register).

### ResourceRef<R> / resource / ref — CURRENT_IMPLEMENTATION

resource_kind one of closed 40 role names and constrained to expected role; version/schema Text 1..128 UTF-8 bytes, not a registry approval; content_ref is ParentRef<SOURCE-BYTES>. Exact key set and no implicit current/latest alias. Body-key check compares kind/schema/version only. Unknown/unreviewed operational schema or unresolved bytes remains blocked.

Sources: `src/pit_research_lab/mvp/f2/resource_contracts.py:L19–L29` (pin in source register); `src/pit_research_lab/mvp/f2/resource_contracts.py:L181–L194` (pin in source register); `src/pit_research_lab/mvp/f2/resource_bodies.py:L568–L580` (pin in source register); `src/pit_research_lab/mvp/if03/typed_references.py:L127–L157` (pin in source register).

### UInt64 / tagged_integer / _uint_equal — CURRENT_IMPLEMENTATION

Exact {type:uint64,value:decimal string}; grammar 0|[1-9][0-9]*, range 0..2^64-1, spelling bound 21 bytes. No sign, leading zeros, -0, numeric token, bool or coercion. _uint_equal compares to the specified constant; 6 means tagged UInt64(6), not bare JSON 6. Int64 counterpart uses type=int64, signed grammar and [-2^63,2^63-1].

Sources: `src/pit_research_lab/mvp/f2/resource_contracts.py:L128–L138` (pin in source register); `src/pit_research_lab/mvp/f2/resource_bodies.py:L472–L473` (pin in source register); `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L457–L457` (pin in source register).

### TimeRecord / declared_taipei / tick (dependency, not added body fields) — CURRENT_IMPLEMENTATION

TimeRecord preserves original source_text/timezone_name=Asia/Taipei/offset=+08:00/precision=SECOND, ResourceRef<ORIGIN>, derived exact UTC Z seconds and ResourceRef<TIMEZONE_RULES>. declared_taipei checks exact 25-character original declaration and Gregorian validity; this is offset arithmetic, not authentic named-zone rules. TickContext exact tick_id/Text<=128, tick_order/UInt64, decision_cutoff/TimeRecord, context_ref/Text<=128. No rewrite of original origins on equal UTC or equal numeric values.

Sources: `src/pit_research_lab/mvp/f2/resource_contracts.py:L273–L311` (pin in source register); `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L459–L459` (pin in source register).

Required field shape is distinct from proof availability. A missing required scalar/ref is INVALID structure, whereas structurally valid input lacking accepted source/rights/Owner proof remains NOT_SUPPLIED/BLOCKED for semantic acceptance. Original Unknown, NotEvaluated, NotApplicable, Withheld and unavailable Native outcomes are not interchangeable. None of these five policy bodies gains new unknown or proof fields. General CAN Text can be empty; this Draft's scoped nonempty policy remains unchanged. Record key ordering is a canonical serialization rule (CAN-01), not a requirement on ordinary Draft JSON transport; arrays always preserve input order.

Each role below incorporates these exact helper definitions, not an open extension bag. Parent/ResourceRef/UInt64 fields listed here are the nested schemas used by that role. They are claims to be verified later; no full resource bytes, expected hash/digest/envelope or live grant is supplied.

## RSF02-A06 — TIMEZONE_RULES

**Status:** S1_CANDIDATE_PENDING_INDEPENDENT_REVIEW; MISSING_OWNER_PROOF; NOT_ADOPTED.

**CURRENT_IMPLEMENTATION:** `body_schema_label=rs-spec-timezone-rules-body-proposal-v0.1`; `body_version=0.1-DRAFT-NON_ISSUED`. Both exact required wrapper fields, no optional or extra field. Candidate semantic revision `v0.1-CANDIDATE-NON_OPERATIVE` is documentary only; operational `resource_schema/resource_version` NOT_SUPPLIED / NOT_REGISTERED. SOURCE-BYTES parent/profile as in helper contract; policy version (where present) is distinct from wrapper/operational version.

**PROJECT_OWNER_DIRECTION:** Restrict to Asia/Taipei, +08:00, SECOND precision and exact covered original SYN-A publication/cutoff interval; versioned externally reviewed rules_source_ref required; host tzdb or inferred DST rules are not authority. Source: `docs/mvp/v1.0/wu05-rsf02d-owner-decision-matrix-v0.1.json:L151–L168` (pin in source register).

### Exact field and nested helper inventory

| Required field | CURRENT_IMPLEMENTATION validator / exact nested shape | S1_CANDIDATE semantic interpretation |
|---|---|---|
| `timezone_name` | `literal("Asia/Taipei")` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L350–L350` (pin in source register)) | The named zone whose versioned rules interpret original SYN-A declarations; exact Asia/Taipei. It is an evidence identity component, not a host setting. |
| `rules_source_ref` | `parent` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L351–L351` (pin in source register)) | ParentRef<SOURCE-BYTES> of immutable externally reviewed original rule material. A syntactically valid core neither resolves nor authenticates it. Source authority, exact version, rights and independent origin/coverage proof must be supplied. |
| `rules_version` | `text` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L352–L352` (pin in source register)) | Nonempty Text naming the exact reviewed rule edition; no host/current/latest fallback. Text validation proves no version approval. |
| `supported_precision` | `literal("SECOND")` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L353–L353` (pin in source register)) | Literal SECOND; no DAY/MINUTE/fractional/leap-second widening. It states precision of original declarations, not permission to round them. |
| `coverage` | `record(first_local=text, last_local=text)` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L354–L354` (pin in source register)) | Closed {first_local:Text,last_local:Text}; both exact YYYY-MM-DDTHH:MM:SS+08:00 in current parser; inclusive first<=last. Candidate: the declared interval covers every original publication and cutoff in the selected input closure, not just displayed ticks. |
| `offset_rules` | `items(record(start=text, end=text, offset=literal("+08:00")))` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L355–L355` (pin in source register)) | Ordered 1..4096 closed {start:Text,end:Text,offset:+08:00} intervals. Inclusive endpoints; first start=coverage.first_local, each next start=previous end+1second, start<=end<=last, final end=last. Gaps, overlaps, duplicates or reordering refuse; no sort/repair. Arithmetic continuity is not a named-zone authenticity proof. |

Closed nested records are fully enumerated in the expressions above. ParentRef and ResourceRef recurse only through the exact shared helpers; UInt64 uses closed type/value. Each field and literal is mandatory, no null or Unknown replacement. Order and duplicates follow the shared helper rules plus the explicit role-specific proposals above. Empty literal strings reject by LITERAL; empty list rejects ARRAY_BOUND, except the fixed singleton issuer_cohort rejects by LITERAL. No trimming or sort.

### Observed behavior and proposed invariants

- **CURRENT_IMPLEMENTATION** — The parser enforces contiguous second-resolution +08 intervals and literal zone/precision, but checks no source rule authority or rights. Sources: `src/pit_research_lab/mvp/f2/resource_bodies.py:L349–L356` (pin in source register); `src/pit_research_lab/mvp/f2/resource_bodies.py:L555–L564` (pin in source register); `src/pit_research_lab/mvp/f2/resource_binding.py:L136–L143` (pin in source register).
- **CURRENT_IMPLEMENTATION** — Existing test-only rule example spans 2027-01-07T18:00:00+08:00 through 2027-02-05T18:00:00+08:00, not the earlier publication span; it is explicitly unreviewed. Sources: `tests/unit/mvp_f2/test_resource_bodies.py:L434–L442` (pin in source register); `tests/unit/mvp_f2/test_resource_bodies.py:L634–L642` (pin in source register); `tests/unit/mvp_f2/test_resource_bodies.py:L757–L769` (pin in source register).
- **S1_CANDIDATE** — Require approved original versioned rule bytes, independently verified unique zone/offset interpretation and rights; prohibit host tzdb as authority, even though current synthetic generator uses ZoneInfo. Sources: `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L459–L459` (pin in source register); `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L712–L722` (pin in source register); `src/pit_research_lab/mvp/f2/synthetic_temporal.py:L63–L71` (pin in source register).
- **S1_CANDIDATE** — For the seven original source declarations, original SYN-A roster/revenue publications in the separately pinned temporal foundation, and four cutoffs, coverage must include at least 2026-11-05T12:00:00+08:00 through 2027-02-05T18:00:00+08:00, including D1 one second before t1, D2 AT t1 and D3 one second after t3. Further selected timestamps/calendar coverage extend the coverage obligation; no authenticity is asserted. Do not merge distinct original sources merely because publication times match; SYN-B and future evaluation timestamps are not new authorized decision inputs. Sources: `src/pit_research_lab/mvp/f2/resource_binding.py:L45–L116` (pin in source register); `tests/unit/mvp_f2/data/derived_observations_v0.1.json:L1–L1` (pin in source register); `tests/unit/mvp_f2/data/temporal_foundation_v0.1.json:L1–L2152` (pin in source register); `tests/unit/mvp_f2/test_resource_bodies.py:L757–L769` (pin in source register).

**S1_CANDIDATE refusals:** Uncovered publication/cutoff, gap/overlap/reversed coverage, offset other than +08:00, unapproved zone/version/precision, missing authority/rights, untrusted host tzdb substitution, changed rules bytes under old parent.

**Unknown/absence:** All selected policy fields are mandatory exact values/records; null, absent key, unknown union or empty string are not substitutes. Missing source/Owner evidence is NOT_SUPPLIED; no absence-to-zero/default/approval. Original Native Unknown/NotEvaluated/Withheld/first failure/invocation in dependent data remain exact and private as required.

**Rights and release — BLOCKED:** No policy grants access; immutable source evidence/right-to-use/operation receipt/IF04 capability/IF05 predicate separately required. Default DENIED and local WITHHELD unchanged.

The independently extracted original publication inventory (authored synthetic evidence, not authenticated zone rules) is:

| Original tag | Exact source_text | Original pointer in pinned packet |
|---|---|---|
| O | 2026-11-05T12:00:00+08:00 | `/sources/0/source/request/attempts/0/supplied/proof_candidate/timestamp` |
| N | 2026-12-05T12:00:00+08:00 | `/sources/1/source/request/attempts/0/supplied/proof_candidate/timestamp` |
| D1 | 2027-01-07T17:59:59+08:00 | `/sources/2/source/request/attempts/0/supplied/proof_candidate/timestamp` |
| D2 | 2027-01-07T18:00:00+08:00 | `/sources/3/source/request/attempts/0/supplied/proof_candidate/timestamp` |
| D3 | 2027-01-29T18:00:01+08:00 | `/sources/4/source/request/attempts/0/supplied/proof_candidate/timestamp` |
| N12 | 2027-01-07T18:00:00+08:00 | `/sources/5/source/request/attempts/0/supplied/proof_candidate/timestamp` |
| N23 | 2027-01-29T18:00:01+08:00 | `/sources/6/source/request/attempts/0/supplied/proof_candidate/timestamp` |

All seven retain original Asia/Taipei/+08:00/SECOND and origin records in the external source report. Packet source is `tests/unit/mvp_f2/data/derived_observations_v0.1.json` (full-file pin below); `resource_binding.original_source_facts` L85–116 corroborates the extraction. Four cutoffs at binding L45–50 extend the covered range through February 5. This is a minimum coverage obligation for this selected closure, not approved rule bytes or broader all-history completeness. The existing cutoff-only test example is insufficient as a semantic positive.

The separately pinned temporal foundation also has the following original SYN-A publication declarations. They stay distinct from the seven-source packet; matching clocks do not merge origins. SYN-B is outside the selected SYN-A direction. Full-calendar/session timestamps or any later selected source closure require additional coverage review; future price/label timestamps never become decision observations.

| Original source | Exact source_text | JSON pointer |
|---|---|---|
| tests/unit/mvp_f2/data/temporal_foundation_v0.1.json | 2027-01-04T08:00:00+08:00 | `/input_spec/roster/0/publication` |
| tests/unit/mvp_f2/data/temporal_foundation_v0.1.json | 2027-01-07T17:59:59+08:00 | `/input_spec/revenue_events/0/publication` |
| tests/unit/mvp_f2/data/temporal_foundation_v0.1.json | 2027-01-07T18:00:00+08:00 | `/input_spec/revenue_events/1/publication` |
| tests/unit/mvp_f2/data/temporal_foundation_v0.1.json | 2027-01-29T18:00:01+08:00 | `/input_spec/revenue_events/3/publication` |

### Parser and inspected tests (NOT_RUN)

- parse_body: `src/pit_research_lab/mvp/f2/resource_bodies.py:L514–L565` (pin in source register)
- parse_reference_body: `src/pit_research_lab/mvp/f2/resource_bodies.py:L577–L580` (pin in source register)
- validate_body_key: `src/pit_research_lab/mvp/f2/resource_bodies.py:L568–L574` (pin in source register)
- issuance_readiness: `src/pit_research_lab/mvp/f2/resource_bodies.py:L583–L592` (pin in source register)

- test_rule_table_draft_does_not_supply_reviewed_rule_evidence: `tests/unit/mvp_f2/test_resource_bodies.py:L634–L642` (pin in source register) — definition inspected only, NOT_RUN
- test_strict_before_edges_and_declared_utc: `tests/unit/mvp_f2/test_resource_bodies.py:L812–L816` (pin in source register) — definition inspected only, NOT_RUN
- test_time_zone_precision_naive_rules_and_origin: `tests/unit/mvp_f2/test_resource_bodies.py:L818–L833` (pin in source register) — definition inspected only, NOT_RUN
- test_rule_table_rejects_gap_overlap_and_reversed_bounds: `tests/unit/mvp_f2/test_resource_bodies.py:L1308–L1317` (pin in source register) — definition inspected only, NOT_RUN

### F02 per-field empty-string compatibility verdicts

| Field / empty-string mutation | Current scoped verdict | Compatibility |
|---|---|---|
| rules_version | REJECT; scoped Draft TEXT_BOUND (required nonempty Text), never empty-to-Unknown | RETAIN_EXISTING_DRAFT_REFUSAL; accepting empty would require VERSIONED_AMENDMENT_REQUIRED; general CAN Text unchanged |
| coverage.first_local | REJECT; scoped Draft TEXT_BOUND (required nonempty Text), never empty-to-Unknown | RETAIN_EXISTING_DRAFT_REFUSAL; accepting empty would require VERSIONED_AMENDMENT_REQUIRED; general CAN Text unchanged |
| coverage.last_local | REJECT; scoped Draft TEXT_BOUND (required nonempty Text), never empty-to-Unknown | RETAIN_EXISTING_DRAFT_REFUSAL; accepting empty would require VERSIONED_AMENDMENT_REQUIRED; general CAN Text unchanged |
| offset_rules[].start | REJECT; scoped Draft TEXT_BOUND (required nonempty Text), never empty-to-Unknown | RETAIN_EXISTING_DRAFT_REFUSAL; accepting empty would require VERSIONED_AMENDMENT_REQUIRED; general CAN Text unchanged |
| offset_rules[].end | REJECT; scoped Draft TEXT_BOUND (required nonempty Text), never empty-to-Unknown | RETAIN_EXISTING_DRAFT_REFUSAL; accepting empty would require VERSIONED_AMENDMENT_REQUIRED; general CAN Text unchanged |
| rules_source_ref.domain_tag | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| rules_source_ref.object_schema_version | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| rules_source_ref.canonical_profile_version | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| rules_source_ref.digest_algorithm | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| rules_source_ref.canonical_payload_byte_length.type | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| rules_source_ref.canonical_payload_byte_length.value | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| rules_source_ref.digest_hex | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |

All remaining literal string leaves (including wrapper label/version, enum members and fixed cohort) reject empty by exact literal/role checks. Required boolean/object/list leaves reject empty string by literal/object/array checks. This independently stated verdict covers every selected leaf; it does not change general CAN Text. Parent and value dependencies are not silently inserted into the policy body.

### Positive / negative / mutation requirements — NOT_RUN

**RSF02-A06-POSITIVE**: `PRECONDITION_NOT_SUPPLIED` / `CANDIDATE_ONLY`; execution `NOT_RUN`. Source prerequisites: Versioned rules_source_ref bytes/source rights and independent named-zone provenance/coverage are NOT_SUPPLIED. Owner must approve exact selected publication/cutoff closure and bounded zone/precision semantics; independent reviewer must verify interval endpoints against original declarations and rule edition.

| Case | Independently specified input / change | Expected type/state | Reason |
|---|---|---|---|
| RSF02-A06-POSITIVE-01 | Approved original rule edition, Asia/Taipei +08 SECOND and contiguous inclusive intervals covering all seven original publications and four cutoffs | CANDIDATE_ONLY; structural DraftBody plus independently proven coverage if preconditions later supplied; current readiness remains NOT_SUPPLIED | Rule authority and original coverage are independent of arithmetic. |
| RSF02-A06-POSITIVE-02 | Original D1 2027-01-07T17:59:59+08:00, D2 exactly t1 and D3 2027-01-29T18:00:01+08:00; exact source/origin preserved | CANDIDATE_ONLY; strict publication comparison D1 BEFORE t1, D2 AT t1 not BEFORE, D3 AFTER t3 | Boundary comparison is not authentic rule proof. |
| RSF02-A06-POSITIVE-03 | Every original timestamp TimeRecord has approved immutable rule ref plus unchanged zone/offset/SECOND/origin | CANDIDATE_ONLY; retain declarations, derived UTC only for comparison; no grant or admission | Equal UTC does not erase evidence identity. |

**RSF02-A06-NEGATIVE**: `CANDIDATE_ONLY` / `CANDIDATE_ONLY`; execution `NOT_RUN`. Source prerequisites: Versioned rules_source_ref bytes/source rights and independent named-zone provenance/coverage are NOT_SUPPLIED. Owner must approve exact selected publication/cutoff closure and bounded zone/precision semantics; independent reviewer must verify interval endpoints against original declarations and rule edition.

| Case | Independently specified input / change | Expected type/state | Reason |
|---|---|---|---|
| RSF02-A06-NEGATIVE-01 | Cutoff-only test interval starting t1, omitting O/N/D1 publications | BLOCKED semantic coverage even if Draft interval parser succeeds | All original publication coverage required. |
| RSF02-A06-NEGATIVE-02 | Offset +09:00; precision DAY/fraction; zone UTC; naive or malformed Gregorian time | INVALID structural literal/time representation (no fallback) | Current bounded zone/offset/SECOND only. |
| RSF02-A06-NEGATIVE-03 | Gap, overlap, duplicate/reversed interval, uncovered first/last original endpoint | INVALID RULE_COVERAGE_ORDER or RULE_INTERVAL_COVERAGE as applicable; semantic uncovered endpoint BLOCKED | Inclusive one-second contiguous partition required. |
| RSF02-A06-NEGATIVE-04 | Missing/unapproved rules_source_ref or rules_version; host tzdb/current alias instead of reviewed bytes; absent source rights | NOT_SUPPLIED/BLOCKED; no authenticity or issuance | Syntactic source core and arithmetic cannot supply authority. |
| RSF02-A06-NEGATIVE-05 | Each empty rules_version/coverage.first_local/coverage.last_local/offset_rules[].start/end independently; null/unknown substitution; missing/extra/duplicate key | INVALID scoped Draft TEXT_BOUND/time/closed/duplicate rules; canonical general Text remains unchanged | F02 per-field retain-refusal; unknown evidence is not a valid required scalar. |

**RSF02-A06-MUTATION**: `CANDIDATE_ONLY` / `CANDIDATE_ONLY`; execution `NOT_RUN`. Source prerequisites: Versioned rules_source_ref bytes/source rights and independent named-zone provenance/coverage are NOT_SUPPLIED. Owner must approve exact selected publication/cutoff closure and bounded zone/precision semantics; independent reviewer must verify interval endpoints against original declarations and rule edition.

| Case | Independently specified input / change | Expected type/state | Reason |
|---|---|---|---|
| RSF02-A06-MUTATION-01 | One original rule-source byte or rules_version changes while old rule/time refs are retained | BLOCKED stale/unverified parent; require independently verified new identities, no expected digest supplied | Changed immutable rules cannot use old source pin. |
| RSF02-A06-MUTATION-02 | Reorder intervals or move any endpoint by one second; change original zone/offset/precision/origin while claiming same UTC | INVALID interval or BLOCKED stale evidence; original declaration retained | No array sorting, timestamp rewrite or identity equivalence. |
| RSF02-A06-MUTATION-03 | Remove earliest publication from declared closure to make cutoff-only example appear sufficient | BLOCKED incomplete original closure | Selected closure needs attributable Owner adjudication, not author filtering. |

**Downstream identity/invalidation for every case:** Changed rule bytes/version/coverage/original declaration/origin require newly verified rule/time parents and affected calendar/config/qualification/observation/schedule/sequence references; same UTC alone cannot preserve evidence identity. No computed body/frame/digest equivalence. No full Resource Body/Frame/Digest/Parent resolution/grant/Native witness supplied; no expected full SHA fabricated. Positive cases cannot advance until source preconditions are independently fulfilled.

### Compatibility, accountable decision and deferred work

**S1_CANDIDATE compatibility:** Existing Draft interval arithmetic is retained. Requiring actual source authority/complete original-time coverage is an additional semantic acceptance gate, requiring an explicitly reviewed operational schema/version or registered mapping before use. Wider zone/precision/offset, altered endpoint meaning, new proof fields, accepting empty version or changing array treatment requires VERSIONED_AMENDMENT_REQUIRED. No new fields are added here.

**MISSING_OWNER_PROOF / BLOCKED obligations:**

- Versioned rules_source_ref bytes/source rights and independent named-zone provenance/coverage are NOT_SUPPLIED.
- Owner must approve exact selected publication/cutoff closure and bounded zone/precision semantics; independent reviewer must verify interval endpoints against original declarations and rule edition.

**Accountable semantic Owner role:** Technical Lead/F2; F4/Data source custodian for original rule provenance and rights. Actual role-holder decision/signature NOT_SUPPLIED. Prior project direction is not that missing proof.

**Independent reviewer role:** Independent temporal/rules and source-provenance reviewer, distinct from author/issuer. Identity, appointment, completed review/verdict and signature NOT_SUPPLIED. This author cannot approve itself.

**Exact next Owner decision:** Accept/revise/defer the exact inclusive interval and original timestamp coverage contract, designate attributable rule custodian and independent temporal reviewer, and supply immutable reviewed rule edition/rights. Do not mark rule authenticity or S2 complete from this document.

**Alternatives:**

- Retain candidate pending exact rule evidence (proposed).
- Revise to a broader zone/version/precision only via separately authorized versioned schema and independent vectors.
- Defer S1 if provenance or interval scope cannot be adjudicated.

| Future decision | Consequence |
|---|---|
| ACCEPT | Attributable Owner acceptance of exact semantics remains separate from independent review; only both completed for exact adopted version with conditions fulfilled can yield S1 adoption; no S2–S5 promotion. |
| REVISE | Keep current Draft and immutable evidence; authorize separately versioned changed acceptance/fields, independent compatibility vectors and renewed review. |
| DEFER | Keep S1_NOT_YET_ACCEPTED and blocked downstream operations; no implicit approval. |

S1 requires exact adopted semantic version, attributable Owner acceptance and a separately completed independent semantic review with these conditions resolved. SCHEDULE_INVARIANT_POLICY additionally cannot be unconditionally ratified before adopted B01 semantics. A future reviewer may return ACCEPTED_CANDIDATE_PENDING_OWNER, REVISION_REQUIRED or BLOCKED_BY_EXTERNAL_OWNER; none is an author-supplied verdict. **S2:** exact original resource body/version/parents and rights; **S3:** independent full-domain Golden/freeze; **S4:** issuer/current rights/receipt/actual Native replay; **S5:** exact consumer/IF04/IF05/F3/F5 acceptance all remain separately unauthorized and unproved.

## RSF02-A09 — NUMERIC_POLICY

**Status:** S1_CANDIDATE_PENDING_INDEPENDENT_REVIEW; MISSING_OWNER_PROOF; NOT_ADOPTED.

**CURRENT_IMPLEMENTATION:** `body_schema_label=rs-spec-numeric-policy-body-proposal-v0.1`; `body_version=0.1-DRAFT-NON_ISSUED`. Both exact required wrapper fields, no optional or extra field. Candidate semantic revision `v0.1-CANDIDATE-NON_OPERATIVE` is documentary only; operational `resource_schema/resource_version` NOT_SUPPLIED / NOT_REGISTERED. SOURCE-BYTES parent/profile as in helper contract; policy version (where present) is distinct from wrapper/operational version.

**PROJECT_OWNER_DIRECTION:** Retain original signed Int64 revenue in NTD_thousands and Native six-decimal FixedRatio6 fractional units/scaled bounds/half-even rounding; text/display is not replacement evidence; no float or unreviewed coercion. Source: `docs/mvp/v1.0/wu05-rsf02d-owner-decision-matrix-v0.1.json:L208–L225` (pin in source register).

### Exact field and nested helper inventory

| Required field | CURRENT_IMPLEMENTATION validator / exact nested shape | S1_CANDIDATE semantic interpretation |
|---|---|---|
| `input_integer_type` | `literal("int64")` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L372–L372` (pin in source register)) | Literal int64 designates signed original revenue Int64, [-2^63,2^63-1], exact integer type and canonical signed decimal tag at the value boundary; no float/bool/string/Decimal coercion. |
| `revenue_unit` | `literal("NTD_thousands")` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L373–L373` (pin in source register)) | Literal NTD_thousands on original revenue. No multiplication into NTD or rescaling by display formatter; signed negative input remains original Int64 evidence, not automatically an invalid source. |
| `ratio_policy_name` | `literal(NUMERICAL_POLICY)` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L374–L374` (pin in source register)) | Literal FIXED_SIX_DECIMAL_FRACTION_HALF_EVEN-v0.1; names bounded Native FixedRatio6 policy, not a general Decimal or exact-fraction interchange schema. |
| `ratio_scale` | `lambda v: _uint_equal(v, 6)` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L375–L375` (pin in source register)) | Exact tagged UInt64(6). Ratio scale belongs to the numeric representation; bare 6/6.0/true is rejected by tagged_integer. |
| `ratio_unit` | `literal("FRACTION")` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L376–L376` (pin in source register)) | Literal FRACTION, never PERCENT. |
| `ratio_scaled_bounds` | `record(<br>            min=lambda v: _uint_equal(v, 0), max=lambda v: _uint_equal(v, 1000000)<br>        )` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L377–L379` (pin in source register)) | Closed {min:UInt64(0),max:UInt64(1000000)} inclusive. FixedRatio6 exact scaled_units/decimal_text relation is required at value boundary; policy body itself holds no revenue or ratio result. |
| `rounding` | `literal("HALF_EVEN")` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L380–L380` (pin in source register)) | Literal HALF_EVEN; exact quotient/remainder rounding at six places with ties to even. No decimal-text reparsing or alternate rounding policy. |
| `policy_source_ref` | `parent` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L381–L381` (pin in source register)) | ParentRef<SOURCE-BYTES> for exact reviewed Native policy source bytes and provenance. Matching labels/policy constants are insufficient; rights, equivalence and loaded-rule provenance remain unverified. |

Closed nested records are fully enumerated in the expressions above. ParentRef and ResourceRef recurse only through the exact shared helpers; UInt64 uses closed type/value. Each field and literal is mandatory, no null or Unknown replacement. Order and duplicates follow the shared helper rules plus the explicit role-specific proposals above. Empty literal strings reject by LITERAL; empty list rejects ARRAY_BOUND, except the fixed singleton issuer_cohort rejects by LITERAL. No trimming or sort.

### Observed behavior and proposed invariants

- **CURRENT_IMPLEMENTATION** — Draft pins policy literals/bounds but does not resolve policy_source_ref or run numeric/Native calculations. Sources: `src/pit_research_lab/mvp/f2/resource_bodies.py:L371–L382` (pin in source register); `src/pit_research_lab/mvp/f2/resource_bodies.py:L472–L473` (pin in source register).
- **CURRENT_IMPLEMENTATION** — Value helper revenue is signed tagged Int64 with exact unit; fixed_ratio validates closed type/scaled_units/decimal_text/scale/unit/numeric_policy_ref through Native FixedRatio. Native uses integer divmod half-even, without float. Sources: `src/pit_research_lab/mvp/f2/resource_contracts.py:L322–L342` (pin in source register); `src/pit_research_lab/domain/ratio.py:L72–L94` (pin in source register); `src/pit_research_lab/domain/ratio.py:L138–L154` (pin in source register).
- **S1_CANDIDATE** — FixedRatio6 must have type=fixed_ratio6, scaled_units UInt64 0..1000000, exact six decimal places (0.000000 through 1.000000), scale UInt64(6), unit FRACTION and exact approved NUMERIC_POLICY ref. Native relation is text=(scaled//1000000).(scaled%1000000 as six digits). Sources: `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L457–L457` (pin in source register); `src/pit_research_lab/mvp/f2/resource_contracts.py:L329–L342` (pin in source register).
- **S1_CANDIDATE** — Preserve original signed Int64 values. Negative months or zero actual A04 denominator are domain-specific NOT_COMPUTABLE, not coercion to zero or fabricated available ratio. Pure arithmetic examples are not a Native replay or approved policy resource. Sources: `src/pit_research_lab/domain/ratio.py:L344–L371` (pin in source register); `tests/unit/mvp_f2/test_resource_bodies.py:L848–L893` (pin in source register).

**S1_CANDIDATE refusals:** Float, NaN/Infinity, +1/01/-0/exponent spelling, signed overflow, negative UInt64 ratio units, scaled >1000000, inconsistent ratio text, wrong unit/scale/rounding, missing or unapproved policy_source_ref authority.

**Unknown/absence:** All selected policy fields are mandatory exact values/records; null, absent key, unknown union or empty string are not substitutes. Missing source/Owner evidence is NOT_SUPPLIED; no absence-to-zero/default/approval. Original Native Unknown/NotEvaluated/Withheld/first failure/invocation in dependent data remain exact and private as required.

**Rights and release — BLOCKED:** No policy grants access; immutable source evidence/right-to-use/operation receipt/IF04 capability/IF05 predicate separately required. Default DENIED and local WITHHELD unchanged.

### Parser and inspected tests (NOT_RUN)

- parse_body: `src/pit_research_lab/mvp/f2/resource_bodies.py:L514–L565` (pin in source register)
- parse_reference_body: `src/pit_research_lab/mvp/f2/resource_bodies.py:L577–L580` (pin in source register)
- validate_body_key: `src/pit_research_lab/mvp/f2/resource_bodies.py:L568–L574` (pin in source register)
- issuance_readiness: `src/pit_research_lab/mvp/f2/resource_bodies.py:L583–L592` (pin in source register)

- test_numeric_policy_cannot_widen_scale_or_claim_general_decimal: `tests/unit/mvp_f2/test_resource_bodies.py:L655–L661` (pin in source register) — definition inspected only, NOT_RUN
- test_exact_int64_signed_unit_and_encoding: `tests/unit/mvp_f2/test_resource_bodies.py:L848–L854` (pin in source register) — definition inspected only, NOT_RUN
- test_fixed_ratio_original_values_half_even_and_bounds: `tests/unit/mvp_f2/test_resource_bodies.py:L856–L868` (pin in source register) — definition inspected only, NOT_RUN
- test_ratio_float_exponent_scale_percent_and_mismatch: `tests/unit/mvp_f2/test_resource_bodies.py:L881–L893` (pin in source register) — definition inspected only, NOT_RUN

### F02 per-field empty-string compatibility verdicts

| Field / empty-string mutation | Current scoped verdict | Compatibility |
|---|---|---|
| policy_source_ref.domain_tag | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| policy_source_ref.object_schema_version | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| policy_source_ref.canonical_profile_version | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| policy_source_ref.digest_algorithm | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| policy_source_ref.canonical_payload_byte_length.type | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| policy_source_ref.canonical_payload_byte_length.value | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| policy_source_ref.digest_hex | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| ratio_scale.type | REJECT; tagged UInt64 TEXT_BOUND for value, LITERAL for type; ratio decimal_text TEXT_BOUND | RETAIN_EXISTING_DRAFT_REFUSAL; exact numeric grammar is distinct from general Text |
| ratio_scale.value | REJECT; tagged UInt64 TEXT_BOUND for value, LITERAL for type; ratio decimal_text TEXT_BOUND | RETAIN_EXISTING_DRAFT_REFUSAL; exact numeric grammar is distinct from general Text |
| ratio_scaled_bounds.min.type | REJECT; tagged UInt64 TEXT_BOUND for value, LITERAL for type; ratio decimal_text TEXT_BOUND | RETAIN_EXISTING_DRAFT_REFUSAL; exact numeric grammar is distinct from general Text |
| ratio_scaled_bounds.min.value | REJECT; tagged UInt64 TEXT_BOUND for value, LITERAL for type; ratio decimal_text TEXT_BOUND | RETAIN_EXISTING_DRAFT_REFUSAL; exact numeric grammar is distinct from general Text |
| ratio_scaled_bounds.max.type | REJECT; tagged UInt64 TEXT_BOUND for value, LITERAL for type; ratio decimal_text TEXT_BOUND | RETAIN_EXISTING_DRAFT_REFUSAL; exact numeric grammar is distinct from general Text |
| ratio_scaled_bounds.max.value | REJECT; tagged UInt64 TEXT_BOUND for value, LITERAL for type; ratio decimal_text TEXT_BOUND | RETAIN_EXISTING_DRAFT_REFUSAL; exact numeric grammar is distinct from general Text |
| dependency.FixedRatio6.decimal_text | REJECT; tagged UInt64 TEXT_BOUND for value, LITERAL for type; ratio decimal_text TEXT_BOUND | RETAIN_EXISTING_DRAFT_REFUSAL; exact numeric grammar is distinct from general Text |
| dependency.FixedRatio6.numeric_policy_ref.resource_schema | REJECT; tagged UInt64 TEXT_BOUND for value, LITERAL for type; ratio decimal_text TEXT_BOUND | RETAIN_EXISTING_DRAFT_REFUSAL; exact numeric grammar is distinct from general Text |
| dependency.FixedRatio6.numeric_policy_ref.resource_version | REJECT; tagged UInt64 TEXT_BOUND for value, LITERAL for type; ratio decimal_text TEXT_BOUND | RETAIN_EXISTING_DRAFT_REFUSAL; exact numeric grammar is distinct from general Text |

All remaining literal string leaves (including wrapper label/version, enum members and fixed cohort) reject empty by exact literal/role checks. Required boolean/object/list leaves reject empty string by literal/object/array checks. This independently stated verdict covers every selected leaf; it does not change general CAN Text. Parent and value dependencies are not silently inserted into the policy body.

### Positive / negative / mutation requirements — NOT_RUN

**RSF02-A09-POSITIVE**: `PRECONDITION_NOT_SUPPLIED` / `CANDIDATE_ONLY`; execution `NOT_RUN`. Source prerequisites: Exact approved policy_source_ref original bytes/rights and independent Native source-to-policy equivalence NOT_SUPPLIED. Accountable numeric Owner must confirm signed revenue vs restricted ratio operand domain and bind exact policy version.

| Case | Independently specified input / change | Expected type/state | Reason |
|---|---|---|---|
| RSF02-A09-POSITIVE-01 | Reviewed original policy bytes; exact signed Int64 revenue -9223372036854775808, 0, 140, 9223372036854775807 with NTD_thousands | CANDIDATE_ONLY; exact Int64 values retained; no automatic ratio availability for negative input | Source signed integers are distinct from share operand domain. |
| RSF02-A09-POSITIVE-02 | FixedRatio6 scaled 0/714286/733333/692308/1000000, text 0.000000/0.714286/0.733333/0.692308/1.000000, tagged scale6 and FRACTION | CANDIDATE_ONLY; exact text/scaled consistency, no policy-source authenticity from label | Six places and bounded integer scaled units required. |
| RSF02-A09-POSITIVE-03 | Independently specified rational tie cases 1/128 and 3/128 under six-place half-even | CANDIDATE_ONLY; mathematical scaled units 7812 and 23438 respectively, never executed Native replay | Half-even tie rounds the odd retained quotient up and even quotient down; expectations specified from arithmetic, not encoder output. |

**RSF02-A09-NEGATIVE**: `CANDIDATE_ONLY` / `CANDIDATE_ONLY`; execution `NOT_RUN`. Source prerequisites: Exact approved policy_source_ref original bytes/rights and independent Native source-to-policy equivalence NOT_SUPPLIED. Accountable numeric Owner must confirm signed revenue vs restricted ratio operand domain and bind exact policy version.

| Case | Independently specified input / change | Expected type/state | Reason |
|---|---|---|---|
| RSF02-A09-NEGATIVE-01 | Float/NaN/Infinity/bool/Decimal or string coercion as original value, +1/01/-0/1e2 spelling, Int64 overflow on either side | INVALID exact typed integer grammar/range; no truncation | Signed Int64 and spelling must be exact. |
| RSF02-A09-NEGATIVE-02 | Ratio scaled -1 or1000001, scale5/18/bare6, FRACTION changed to PERCENT, wrong six-place text or exponent | INVALID tagged integer/NUMERIC_POLICY_BOUND/RATIO_SCALE/INVALID_FIXED_RATIO as applicable | Scale/unit/text are evidence, not display normalization. |
| RSF02-A09-NEGATIVE-03 | Rounding HALF_UP, input type float, revenue_unit NTD, missing/unapproved policy_source_ref bytes/rights | INVALID literal or NOT_SUPPLIED source proof, no policy adoption | Matching Native name is insufficient. |
| RSF02-A09-NEGATIVE-04 | Empty policy-source parent field/value/digest, fixed_ratio.decimal_text or numeric_policy_ref version/schema; null, extension decimal_rules, duplicate keys | INVALID specific literal/TEXT_BOUND/HEX64/CLOSED_FIELDS/DUPLICATE_KEY; no global Text amendment | F02 exact field verdicts and no extension bag. |
| RSF02-A09-NEGATIVE-05 | Actual ratio operand lineage has a negative month or zero quarter denominator | CANDIDATE_ONLY; Native policy requires NOT_COMPUTABLE with original reason, no available ratio or zero fill | Input valid Int64 does not imply share-domain computability. |

**RSF02-A09-MUTATION**: `CANDIDATE_ONLY` / `CANDIDATE_ONLY`; execution `NOT_RUN`. Source prerequisites: Exact approved policy_source_ref original bytes/rights and independent Native source-to-policy equivalence NOT_SUPPLIED. Accountable numeric Owner must confirm signed revenue vs restricted ratio operand domain and bind exact policy version.

| Case | Independently specified input / change | Expected type/state | Reason |
|---|---|---|---|
| RSF02-A09-MUTATION-01 | Change policy-source bytes/version, unit/scale/rounding or ratio text without changed scaled units | BLOCKED stale semantic parents or INVALID inconsistent ratio; require reviewed new policy and dependent refs | No stale qualification/projection/replay reuse. |
| RSF02-A09-MUTATION-02 | Change display text by dropping a trailing zero or infer from float while retaining original ref | INVALID exact six-place consistency; old evidence must remain immutable | Presentation cannot replace original scaled evidence. |
| RSF02-A09-MUTATION-03 | Change source-policy ref to another well-shaped core with same policy label | NOT_SUPPLIED independent equivalence/rights; no digest equivalence | Typed shape cannot authenticate source policy. |

**Downstream identity/invalidation for every case:** Changed policy bytes/version or units/scale/rounding invalidate affected qualification, projection, observation and dependent sequence/experiment identities and replay; source-policy equality by label or Python hash cannot preserve them. Revocation changes current permission, not immutable numeric history. No full Resource Body/Frame/Digest/Parent resolution/grant/Native witness supplied; no expected full SHA fabricated. Positive cases cannot advance until source preconditions are independently fulfilled.

### Compatibility, accountable decision and deferred work

**S1_CANDIDATE compatibility:** Clarifies existing policy literals and Native value helpers. Semantic source authority is a separate acceptance gate. Any new value domain/rounding/scale/unit/required field or changed rejection requires VERSIONED_AMENDMENT_REQUIRED and fresh operational version/registered mapping plus independent vectors. Generic CAN Decimal remains separate; existing Draft version unchanged.

**MISSING_OWNER_PROOF / BLOCKED obligations:**

- Exact approved policy_source_ref original bytes/rights and independent Native source-to-policy equivalence NOT_SUPPLIED.
- Accountable numeric Owner must confirm signed revenue vs restricted ratio operand domain and bind exact policy version.

**Accountable semantic Owner role:** Technical Lead/F2 with attributable Native numeric-policy owner and F4 original input custodian. Actual role-holder decision/signature NOT_SUPPLIED. Prior project direction is not that missing proof.

**Independent reviewer role:** Independent Native numeric equivalence/source-policy reviewer, distinct from issuer/author. Identity, appointment, completed review/verdict and signature NOT_SUPPLIED. This author cannot approve itself.

**Exact next Owner decision:** Accept/revise/defer the bounded signed Int64/FixedRatio6 policy and exact six-place HALF_EVEN meaning, identify attributable Native policy authority and require independent source/code/policy equivalence before S2 or use.

**Alternatives:**

- Keep the exact bounded policy candidate with missing source proof (proposed).
- General Decimal, percent, other rounding or ratio domains need a new separately reviewed schema/version and independent Golden.
- Defer if source policy provenance cannot be approved.

| Future decision | Consequence |
|---|---|
| ACCEPT | Attributable Owner acceptance of exact semantics remains separate from independent review; only both completed for exact adopted version with conditions fulfilled can yield S1 adoption; no S2–S5 promotion. |
| REVISE | Keep current Draft and immutable evidence; authorize separately versioned changed acceptance/fields, independent compatibility vectors and renewed review. |
| DEFER | Keep S1_NOT_YET_ACCEPTED and blocked downstream operations; no implicit approval. |

S1 requires exact adopted semantic version, attributable Owner acceptance and a separately completed independent semantic review with these conditions resolved. SCHEDULE_INVARIANT_POLICY additionally cannot be unconditionally ratified before adopted B01 semantics. A future reviewer may return ACCEPTED_CANDIDATE_PENDING_OWNER, REVISION_REQUIRED or BLOCKED_BY_EXTERNAL_OWNER; none is an author-supplied verdict. **S2:** exact original resource body/version/parents and rights; **S3:** independent full-domain Golden/freeze; **S4:** issuer/current rights/receipt/actual Native replay; **S5:** exact consumer/IF04/IF05/F3/F5 acceptance all remain separately unauthorized and unproved.

## RSF02-A11 — OBSERVATION_RELEASE_POLICY

**Status:** S1_CANDIDATE_PENDING_INDEPENDENT_REVIEW; MISSING_OWNER_PROOF; NOT_ADOPTED.

**CURRENT_IMPLEMENTATION:** `body_schema_label=rs-spec-observation-release-policy-body-proposal-v0.1`; `body_version=0.1-DRAFT-NON_ISSUED`. Both exact required wrapper fields, no optional or extra field. Candidate semantic revision `v0.1-CANDIDATE-NON_OPERATIVE` is documentary only; operational `resource_schema/resource_version` NOT_SUPPLIED / NOT_REGISTERED. SOURCE-BYTES parent/profile as in helper contract; policy version (where present) is distinct from wrapper/operational version.

**PROJECT_OWNER_DIRECTION:** Retain policy axes exact_target, context_match, current_grant, IF05_predicate and audit_separation; deny by default; policy-version changes must invalidate dependent observation eligibility; repeated principal class semantics require explicit duplicate rejection without unreviewed array normalization. Source: `docs/mvp/v1.0/wu05-rsf02d-owner-decision-matrix-v0.1.json:L246–L263` (pin in source register).

### Exact field and nested helper inventory

| Required field | CURRENT_IMPLEMENTATION validator / exact nested shape | S1_CANDIDATE semantic interpretation |
|---|---|---|
| `policy_purpose` | `literal("SEMANTIC_DISCLOSURE_RULES")` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L385–L385` (pin in source register)) | Literal SEMANTIC_DISCLOSURE_RULES; identifies disclosure policy purpose, not an access capability or a PIT eligibility predicate. |
| `projection_policy_ref` | `ref("PROJECTION_POLICY")` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L386–L386` (pin in source register)) | ResourceRef<PROJECTION_POLICY> whose exact approved strict detached whitelist/version must be reviewed separately (A10 remains invariant-required). It must not expose original Native/audit/source/future graphs. |
| `principal_classes` | `items(<br>            literal("F2_ISSUER", "F2_REVIEWER", "F3_RESEARCH", "F5_POLICY", "F6_DISPLAY")<br>        )` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L387–L389` (pin in source register)) | Ordered 1..4096 list drawn from F2_ISSUER, F2_REVIEWER, F3_RESEARCH, F5_POLICY, F6_DISPLAY. These are five permitted class literals, not a requirement that every policy contain all five and not appointed identities. Current items() allows repetitions. Candidate rejects duplicate classes without sorting; changing this acceptance behavior requires a separate versioned amendment. |
| `required_checks` | `record(<br>            exact_target=literal(True),<br>            context_match=literal(True),<br>            current_grant=literal(True),<br>            IF05_predicate=literal(True),<br>            audit_separation=literal(True),<br>        )` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L390–L396` (pin in source register)) | Closed five mandatory true booleans: exact_target means exact typed target/version and operation/exposure; context_match means exact cutoff/context/issuer-feature cohort; current_grant means appointed principal/current issuer grant/validity/revocation at operation; IF05_predicate means separately approved and proven mode-specific eligibility/release predicate; audit_separation means policy principal cannot resolve private audit under the same capability. true is a requirement, not proof that the check ran. |
| `denial_rule` | `literal("FAIL_CLOSED_RETAIN_NATIVE_STATE")` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L397–L397` (pin in source register)) | Literal FAIL_CLOSED_RETAIN_NATIVE_STATE. Refuse unauthorized release; preserve original Native state, unknown, typed first failure and RUN/ATTEMPTED/NOT_RUN privately. Native VALUE_AVAILABLE is never relabeled WITHHELD; separate access state can be WITHHELD/DENIED. |
| `policy_version` | `text` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L398–L398` (pin in source register)) | Nonempty Text for exact disclosure semantics. Not body_version and not the future ResourceRef operational version. Unknown/stale/mismatched policy versions cannot fall back to a latest alias. |

Closed nested records are fully enumerated in the expressions above. ParentRef and ResourceRef recurse only through the exact shared helpers; UInt64 uses closed type/value. Each field and literal is mandatory, no null or Unknown replacement. Order and duplicates follow the shared helper rules plus the explicit role-specific proposals above. Empty literal strings reject by LITERAL; empty list rejects ARRAY_BOUND, except the fixed singleton issuer_cohort rejects by LITERAL. No trimming or sort.

### Observed behavior and proposed invariants

- **CURRENT_IMPLEMENTATION** — Parser enforces five all-true checks but not duplicate principal rejection or actual grant/predicate verification. Existing example uses only F5_POLICY. Sources: `src/pit_research_lab/mvp/f2/resource_bodies.py:L384–L399` (pin in source register); `src/pit_research_lab/mvp/f2/resource_contracts.py:L113–L125` (pin in source register); `tests/unit/mvp_f2/test_resource_bodies.py:L515–L529` (pin in source register).
- **CURRENT_IMPLEMENTATION** — authorization_check always returns DENIED, even with matching declarations/receipt bytes; detached_release always returns local WITHHELD after structural checks, preserving Native input. This does not establish F01 stronger-status architecture. Sources: `src/pit_research_lab/mvp/f2/resource_access.py:L51–L75` (pin in source register); `src/pit_research_lab/mvp/f2/resource_access.py:L97–L118` (pin in source register); `tests/unit/mvp_f2/test_resource_bodies.py:L1168–L1217` (pin in source register).
- **S1_CANDIDATE** — Reject repeated principal classes as explicitly selected by A11; preserve supplied order and exact cardinality of the selected subset. No deduplication or implicit sort. This narrows current Draft acceptance and requires VERSIONED_AMENDMENT_REQUIRED before enforcement. Sources: `docs/mvp/v1.0/wu05-rsf02d-owner-decision-record-v0.1.md:L117–L122` (pin in source register); `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L471–L473` (pin in source register); `src/pit_research_lab/mvp/f2/resource_bodies.py:L384–L399` (pin in source register).
- **S1_CANDIDATE** — Require an operation-bound conjunction of all five real checks. Missing IF05 predicate/grant/receipt, expired or revoked grant, target/context/version mismatch or same-capability audit resolution denies release. Separately verified immutable stronger-WITHHELD status must reach all consumers; retain deferred SEMANTIC_TRACE/AppAxes narrower UNRESOLVED. Sources: `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L378–L390` (pin in source register); `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L752–L753` (pin in source register); `docs/mvp/v1.0/wu05-rsf02d-owner-decision-record-v0.1.md:L208–L214` (pin in source register).

**S1_CANDIDATE refusals:** Policy text/true booleans or safe projection treated as grant; duplicate-principal normalization; missing IF05 proof; expired/revoked grant; wrong target/operation/cutoff/cohort/exposure/version; audit co-grant; leaking private reasons; inventing Native WITHHELD or claiming F01 solved.

**Unknown/absence:** All selected policy fields are mandatory exact values/records; null, absent key, unknown union or empty string are not substitutes. Missing source/Owner evidence is NOT_SUPPLIED; no absence-to-zero/default/approval. Original Native Unknown/NotEvaluated/Withheld/first failure/invocation in dependent data remain exact and private as required.

**Rights and release — BLOCKED:** No policy grants access; immutable source evidence/right-to-use/operation receipt/IF04 capability/IF05 predicate separately required. Default DENIED and local WITHHELD unchanged.

### Parser and inspected tests (NOT_RUN)

- parse_body: `src/pit_research_lab/mvp/f2/resource_bodies.py:L514–L565` (pin in source register)
- parse_reference_body: `src/pit_research_lab/mvp/f2/resource_bodies.py:L577–L580` (pin in source register)
- validate_body_key: `src/pit_research_lab/mvp/f2/resource_bodies.py:L568–L574` (pin in source register)
- issuance_readiness: `src/pit_research_lab/mvp/f2/resource_bodies.py:L583–L592` (pin in source register)

- test_immutable_release_policy_cannot_switch_off_current_grant_or_if05: `tests/unit/mvp_f2/test_resource_bodies.py:L663–L670` (pin in source register) — definition inspected only, NOT_RUN
- test_current_grants_absent_revoked_wrong_context_and_fake_receipt_deny: `tests/unit/mvp_f2/test_resource_bodies.py:L1168–L1204` (pin in source register) — definition inspected only, NOT_RUN
- test_withheld_release_never_rewrites_native_invocation_or_first_failure: `tests/unit/mvp_f2/test_resource_bodies.py:L1206–L1217` (pin in source register) — definition inspected only, NOT_RUN
- test_safe_whitelist_unknown_withheld_and_no_recursive_private_details: `tests/unit/mvp_f2/test_resource_bodies.py:L1219–L1260` (pin in source register) — definition inspected only, NOT_RUN

### F02 per-field empty-string compatibility verdicts

| Field / empty-string mutation | Current scoped verdict | Compatibility |
|---|---|---|
| policy_version | REJECT; scoped Draft TEXT_BOUND (required nonempty Text), never empty-to-Unknown | RETAIN_EXISTING_DRAFT_REFUSAL; accepting empty would require VERSIONED_AMENDMENT_REQUIRED; general CAN Text unchanged |
| projection_policy_ref.resource_schema | REJECT; scoped Draft TEXT_BOUND (required nonempty Text), never empty-to-Unknown | RETAIN_EXISTING_DRAFT_REFUSAL; accepting empty would require VERSIONED_AMENDMENT_REQUIRED; general CAN Text unchanged |
| projection_policy_ref.resource_version | REJECT; scoped Draft TEXT_BOUND (required nonempty Text), never empty-to-Unknown | RETAIN_EXISTING_DRAFT_REFUSAL; accepting empty would require VERSIONED_AMENDMENT_REQUIRED; general CAN Text unchanged |
| projection_policy_ref.content_ref.domain_tag | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| projection_policy_ref.content_ref.object_schema_version | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| projection_policy_ref.content_ref.canonical_profile_version | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| projection_policy_ref.content_ref.digest_algorithm | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| projection_policy_ref.content_ref.canonical_payload_byte_length.type | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| projection_policy_ref.content_ref.canonical_payload_byte_length.value | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| projection_policy_ref.content_ref.digest_hex | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |

All remaining literal string leaves (including wrapper label/version, enum members and fixed cohort) reject empty by exact literal/role checks. Required boolean/object/list leaves reject empty string by literal/object/array checks. This independently stated verdict covers every selected leaf; it does not change general CAN Text. Parent and value dependencies are not silently inserted into the policy body.

### Positive / negative / mutation requirements — NOT_RUN

**RSF02-A11-POSITIVE**: `PRECONDITION_NOT_SUPPLIED` / `CANDIDATE_ONLY`; execution `NOT_RUN`. Source prerequisites: Independent IF04 principal/grant/expiry/revocation/receipt and IF05 positive/explicit-negative predicate proof NOT_SUPPLIED. A10 projection invariants remain separately unadopted; stronger F01 no-release status view NOT_SUPPLIED/NOT_EVALUATED. Owner must choose duplicate rejection under a new operational version or explicit registered amendment; do not silently tighten current Draft.

| Case | Independently specified input / change | Expected type/state | Reason |
|---|---|---|---|
| RSF02-A11-POSITIVE-01 | Explicit approved subset of five permitted principal classes, exact projection ref/version and all five required true booleans | CANDIDATE_ONLY; DraftBody structure only; current authorization DENIED and release WITHHELD | Policy parsing grants nothing. |
| RSF02-A11-POSITIVE-02 | All approved exact-target/context/current-grant/IF05/audit-separation evidence later supplied under separately authorized runtime | CANDIDATE_ONLY; evaluate only in future S4/S5; this baseline still DENIED | No author-supplied strings/receipt can pass current gate. |
| RSF02-A11-POSITIVE-03 | Separately authorized immutable F01 status view carries stronger WITHHELD alongside narrower AppAxes UNRESOLVED with unchanged Native VALUE_AVAILABLE/unknown/failure/invocation | CANDIDATE_ONLY; no-release stronger state visible consistently to all readers if independently proven | F01 view proof is missing, not satisfied by local refusal. |

**RSF02-A11-NEGATIVE**: `CANDIDATE_ONLY` / `CANDIDATE_ONLY`; execution `NOT_RUN`. Source prerequisites: Independent IF04 principal/grant/expiry/revocation/receipt and IF05 positive/explicit-negative predicate proof NOT_SUPPLIED. A10 projection invariants remain separately unadopted; stronger F01 no-release status view NOT_SUPPLIED/NOT_EVALUATED. Owner must choose duplicate rejection under a new operational version or explicit registered amendment; do not silently tighten current Draft.

| Case | Independently specified input / change | Expected type/state | Reason |
|---|---|---|---|
| RSF02-A11-NEGATIVE-01 | Any of five check flags false, missing, bool replaced by1, extra key; policy purpose or denial literal wrong | INVALID LITERAL/CLOSED_FIELDS as applicable | Every required check remains mandatory. |
| RSF02-A11-NEGATIVE-02 | Duplicate F5_POLICY or another class | Current Draft permits repeated list entries; candidate rejects only after separately reviewed VERSIONED_AMENDMENT_REQUIRED | No implicit sort/dedup or false claim of existing rejection. |
| RSF02-A11-NEGATIVE-03 | Absent/expired/revoked grant; target/schema/version/content/operation/exposure/cutoff/cohort mismatch; missing IF05 predicate/receipt or shared audit capability | DENIED ACCESS_DENIED and no release; original Native input retained | Five real checks must be proven; policy booleans are not grants. |
| RSF02-A11-NEGATIVE-04 | Empty policy_version or projection ref version/schema; unknown/null in a required policy scalar; private audit detail in safe denial | INVALID scoped Text/closed/type or DENIED without private existence/failure details | F02 per-field compatibility; data unknown is preserved separately. |
| RSF02-A11-NEGATIVE-05 | Consumer uses UNRESOLVED to erase stronger WITHHELD or treats Native RUN as ELIGIBLE | BLOCKED no release; F01 unresolved and IF05 predicates absent | Keep App axes independent and Native state exact. |

**RSF02-A11-MUTATION**: `CANDIDATE_ONLY` / `CANDIDATE_ONLY`; execution `NOT_RUN`. Source prerequisites: Independent IF04 principal/grant/expiry/revocation/receipt and IF05 positive/explicit-negative predicate proof NOT_SUPPLIED. A10 projection invariants remain separately unadopted; stronger F01 no-release status view NOT_SUPPLIED/NOT_EVALUATED. Owner must choose duplicate rejection under a new operational version or explicit registered amendment; do not silently tighten current Draft.

| Case | Independently specified input / change | Expected type/state | Reason |
|---|---|---|---|
| RSF02-A11-MUTATION-01 | Change disclosure/projection policy_version, projection target or principal list/order while retaining observation refs | BLOCKED stale eligibility/observation dependencies; require reviewed new policy/observation identities | Array order remains identity-bearing, no automatic sort. |
| RSF02-A11-MUTATION-02 | Revoke/expire previously matching grant after immutable content/old receipt is retained | DENIED current operation; immutable content/Native/old receipt preserved | Revocation affects access, not past content. |
| RSF02-A11-MUTATION-03 | Try to relabel Native VALUE_AVAILABLE to WITHHELD or remove first failure/actual invocation when access refuses | BLOCKED unlawful source-state rewrite; retain Native and separate no-release status | F01 stronger access state cannot invent a Native outcome. |

**Downstream identity/invalidation for every case:** Semantic projection/disclosure/release-policy version or principal-array/order changes require new verified policy and affected observation refs, then dependent bindings/sequence/consumer replay. Grant revocation immediately denies future operations while immutable policy/content/Native history remains. Status-view correspondence has no digest supplied. No full Resource Body/Frame/Digest/Parent resolution/grant/Native witness supplied; no expected full SHA fabricated. Positive cases cannot advance until source preconditions are independently fulfilled.

### Compatibility, accountable decision and deferred work

**S1_CANDIDATE compatibility:** Duplicate rejection changes current acceptance and requires VERSIONED_AMENDMENT_REQUIRED. Do not sort, deduplicate or require all five classes. A new operation field, altered policy semantics, empty policy_version, accepted check=false or a stronger-status body field also needs separately reviewed version/schema/Golden; no Draft field is added here.

**MISSING_OWNER_PROOF / BLOCKED obligations:**

- Independent IF04 principal/grant/expiry/revocation/receipt and IF05 positive/explicit-negative predicate proof NOT_SUPPLIED.
- A10 projection invariants remain separately unadopted; stronger F01 no-release status view NOT_SUPPLIED/NOT_EVALUATED.
- Owner must choose duplicate rejection under a new operational version or explicit registered amendment; do not silently tighten current Draft.

**Accountable semantic Owner role:** Technical Lead/F2 release semantic Owner; separate IF04 capability and IF05 predicate owners; F3/F5/F6 consumer consultation. Actual role-holder decision/signature NOT_SUPPLIED. Prior project direction is not that missing proof.

**Independent reviewer role:** Independent disclosure/security and IF05 reviewer; independently verified F01 status-view review still required. Identity, appointment, completed review/verdict and signature NOT_SUPPLIED. This author cannot approve itself.

**Exact next Owner decision:** Accept/revise/defer exact five-check conjunction and candidate duplicate rejection with versioned compatibility treatment; require separate IF04/IF05 decisions and an independently tested F01 no-release view before any consumer release.

**Alternatives:**

- Reject duplicate classes under a separately reviewed operational version/amendment (proposed).
- Retain current duplicate-permitting Draft as historical parser; it remains non-issued and cannot satisfy the selected duplicate-refusal policy.
- If separate F01 status view is insufficient, authorize a separate AppAxes/body/contract amendment; otherwise defer release.

| Future decision | Consequence |
|---|---|
| ACCEPT | Attributable Owner acceptance of exact semantics remains separate from independent review; only both completed for exact adopted version with conditions fulfilled can yield S1 adoption; no S2–S5 promotion. |
| REVISE | Keep current Draft and immutable evidence; authorize separately versioned changed acceptance/fields, independent compatibility vectors and renewed review. |
| DEFER | Keep S1_NOT_YET_ACCEPTED and blocked downstream operations; no implicit approval. |

S1 requires exact adopted semantic version, attributable Owner acceptance and a separately completed independent semantic review with these conditions resolved. SCHEDULE_INVARIANT_POLICY additionally cannot be unconditionally ratified before adopted B01 semantics. A future reviewer may return ACCEPTED_CANDIDATE_PENDING_OWNER, REVISION_REQUIRED or BLOCKED_BY_EXTERNAL_OWNER; none is an author-supplied verdict. **S2:** exact original resource body/version/parents and rights; **S3:** independent full-domain Golden/freeze; **S4:** issuer/current rights/receipt/actual Native replay; **S5:** exact consumer/IF04/IF05/F3/F5 acceptance all remain separately unauthorized and unproved.

## RSF02-A12 — AUDIT_ACCESS_POLICY

**Status:** S1_CANDIDATE_PENDING_INDEPENDENT_REVIEW; MISSING_OWNER_PROOF; NOT_ADOPTED.

**CURRENT_IMPLEMENTATION:** `body_schema_label=rs-spec-audit-access-policy-body-proposal-v0.1`; `body_version=0.1-DRAFT-NON_ISSUED`. Both exact required wrapper fields, no optional or extra field. Candidate semantic revision `v0.1-CANDIDATE-NON_OPERATIVE` is documentary only; operational `resource_schema/resource_version` NOT_SUPPLIED / NOT_REGISTERED. SOURCE-BYTES parent/profile as in helper contract; policy version (where present) is distinct from wrapper/operational version.

**PROJECT_OWNER_DIRECTION:** Separate F2 issuer/reviewer audit principals and exact target, operation, cutoff/context and immutable receipt; revocation must deny current access while retaining historical fact; no SAFE/audit co-grant or privilege escalation. Source: `docs/mvp/v1.0/wu05-rsf02d-owner-decision-matrix-v0.1.json:L265–L282` (pin in source register).

### Exact field and nested helper inventory

| Required field | CURRENT_IMPLEMENTATION validator / exact nested shape | S1_CANDIDATE semantic interpretation |
|---|---|---|
| `principal_classes` | `items(literal("F2_ISSUER", "INDEPENDENT_F2_REVIEWER"))` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L401–L401` (pin in source register)) | Ordered 1..4096 entries from F2_ISSUER and INDEPENDENT_F2_REVIEWER. Their identity/appointment and independence must be proven externally; a class literal appoints nobody. F2_REVIEWER in release policy is not automatically this appointed independent audit reviewer. |
| `operations` | `items(literal("INSPECT_SOURCE", "INSPECT_NATIVE", "VERIFY_PROVENANCE"))` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L402–L402` (pin in source register)) | Ordered 1..4096 entries from INSPECT_SOURCE, INSPECT_NATIVE, VERIFY_PROVENANCE, each scoped to exact current operation. No execute/release/issue right is implied. Draft items() does not reject duplicates; candidate duplicate exact operations/principals/targets refusal is proposed explicitly as a versioned narrowing. |
| `target_rules` | `items(record(resource_kind=lambda v: _role(v), schema=text, version=text))` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L403–L403` (pin in source register)) | Ordered 1..4096 closed {resource_kind,schema,version}. resource_kind uses the existing closed 40-role vocabulary; schema/version are nonempty Text<=65536 here, not the 128-byte ResourceRef helper limit. Exact tuple identifies permitted policy scope only; a later operation must also bind exact ResourceRef/content/target, not grant every body sharing a tuple. |
| `context_scope` | `record(cutoff_rule=text, issuer_cohort=literal(["SYN-A"]))` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L404–L404` (pin in source register)) | Closed {cutoff_rule:Text,issuer_cohort:[SYN-A]}. cutoff_rule is nonempty but uninterpreted by Draft; candidate requires exact approved cutoff/context/issuer-feature cohort mapping in external operation proof. Literal singleton SYN-A does not appoint a source or authorize another cohort. |
| `receipt_requirements` | `literal("SC:L390_EXACT_OPERATION_RECEIPT")` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L405–L405` (pin in source register)) | Literal SC:L390_EXACT_OPERATION_RECEIPT denotes the contract clause. Immutable operation receipt must preserve principal/grant/policy, exact typed target/action/context, source/code/version/length/digest, decision and original operation/attempt provenance plus receipt version. This string is not a receipt. |
| `revocation_rule` | `literal("DENY_CURRENT_OPERATION_RETAIN_HISTORY")` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L406–L406` (pin in source register)) | Literal DENY_CURRENT_OPERATION_RETAIN_HISTORY. Check current validity/expiry/revocation for each operation, deny expired/revoked grants while preserving immutable historical content/receipt; no ongoing right from a past allow. |

Closed nested records are fully enumerated in the expressions above. ParentRef and ResourceRef recurse only through the exact shared helpers; UInt64 uses closed type/value. Each field and literal is mandatory, no null or Unknown replacement. Order and duplicates follow the shared helper rules plus the explicit role-specific proposals above. Empty literal strings reject by LITERAL; empty list rejects ARRAY_BOUND, except the fixed singleton issuer_cohort rejects by LITERAL. No trimming or sort.

### Observed behavior and proposed invariants

- **CURRENT_IMPLEMENTATION** — Draft validates class/operation/target tuple shape and literal receipt/revocation rules; no actual appointment, rights, receipt or current verifier is supplied. Sources: `src/pit_research_lab/mvp/f2/resource_bodies.py:L400–L407` (pin in source register); `src/pit_research_lab/mvp/f2/resource_access.py:L30–L75` (pin in source register); `tests/unit/mvp_f2/test_resource_bodies.py:L530–L544` (pin in source register).
- **S1_CANDIDATE** — F2 issuer and separately appointed independent reviewer are distinct audit principals. Scope each named operation to exact target/content/schema/version, original cutoff/context/cohort and actual source rights; current validity [valid_from,valid_until), revocation and immutable receipt verified per operation. No private audit grant or reviewer appointment is invented. Sources: `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L378–L390` (pin in source register); `src/pit_research_lab/mvp/f2/resource_access.py:L30–L75` (pin in source register).
- **S1_CANDIDATE** — Propose reject exact duplicate principals/operations/target tuples as a reviewed operational narrowing; preserve order rather than normalize. cutoff_rule must have attributable exact interpretation; wildcard/latest matching not authorized. Public denial remains constant ACCESS_DENIED without private existence/failure detail. Sources: `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L471–L473` (pin in source register); `src/pit_research_lab/mvp/f2/resource_access.py:L1–L5` (pin in source register); `src/pit_research_lab/mvp/f2/resource_contracts.py:L113–L125` (pin in source register).

**S1_CANDIDATE refusals:** Unappointed reviewer or self-review; SAFE capability reused for audit; arbitrary/unknown operation, target tuple/content mismatch, wrong cutoff/cohort, missing source rights/immutable receipt, expiry/revocation, source/private failure existence leaked in public denial.

**Unknown/absence:** All selected policy fields are mandatory exact values/records; null, absent key, unknown union or empty string are not substitutes. Missing source/Owner evidence is NOT_SUPPLIED; no absence-to-zero/default/approval. Original Native Unknown/NotEvaluated/Withheld/first failure/invocation in dependent data remain exact and private as required.

**Rights and release — BLOCKED:** No policy grants access; immutable source evidence/right-to-use/operation receipt/IF04 capability/IF05 predicate separately required. Default DENIED and local WITHHELD unchanged.

### Parser and inspected tests (NOT_RUN)

- parse_body: `src/pit_research_lab/mvp/f2/resource_bodies.py:L514–L565` (pin in source register)
- parse_reference_body: `src/pit_research_lab/mvp/f2/resource_bodies.py:L577–L580` (pin in source register)
- validate_body_key: `src/pit_research_lab/mvp/f2/resource_bodies.py:L568–L574` (pin in source register)
- issuance_readiness: `src/pit_research_lab/mvp/f2/resource_bodies.py:L583–L592` (pin in source register)

- test_every_implemented_body_descriptor_closed_and_non_issued: `tests/unit/mvp_f2/test_resource_bodies.py:L609–L621` (pin in source register) — definition inspected only, NOT_RUN
- test_current_grants_absent_revoked_wrong_context_and_fake_receipt_deny: `tests/unit/mvp_f2/test_resource_bodies.py:L1168–L1204` (pin in source register) — definition inspected only, NOT_RUN
- test_frozen_golden_and_original_wu04_static_regression: `tests/unit/mvp_f2/test_resource_bodies.py:L1262–L1292` (pin in source register) — definition inspected only, NOT_RUN

### F02 per-field empty-string compatibility verdicts

| Field / empty-string mutation | Current scoped verdict | Compatibility |
|---|---|---|
| target_rules[].schema | REJECT; scoped Draft TEXT_BOUND (required nonempty Text), never empty-to-Unknown | RETAIN_EXISTING_DRAFT_REFUSAL; accepting empty would require VERSIONED_AMENDMENT_REQUIRED; general CAN Text unchanged |
| target_rules[].version | REJECT; scoped Draft TEXT_BOUND (required nonempty Text), never empty-to-Unknown | RETAIN_EXISTING_DRAFT_REFUSAL; accepting empty would require VERSIONED_AMENDMENT_REQUIRED; general CAN Text unchanged |
| context_scope.cutoff_rule | REJECT; scoped Draft TEXT_BOUND (required nonempty Text), never empty-to-Unknown | RETAIN_EXISTING_DRAFT_REFUSAL; accepting empty would require VERSIONED_AMENDMENT_REQUIRED; general CAN Text unchanged |

All remaining literal string leaves (including wrapper label/version, enum members and fixed cohort) reject empty by exact literal/role checks. Required boolean/object/list leaves reject empty string by literal/object/array checks. This independently stated verdict covers every selected leaf; it does not change general CAN Text. Parent and value dependencies are not silently inserted into the policy body.

### Positive / negative / mutation requirements — NOT_RUN

**RSF02-A12-POSITIVE**: `PRECONDITION_NOT_SUPPLIED` / `CANDIDATE_ONLY`; execution `NOT_RUN`. Source prerequisites: Actual independent reviewer appointment/identity, source rights, exact cutoff_rule interpretation, current grant/expiry/revocation proof and immutable current operation receipt NOT_SUPPLIED. Independent security/provenance review must verify exact target matching and nonleaking denial. Optional duplicate narrowing needs explicit versioned Owner decision.

| Case | Independently specified input / change | Expected type/state | Reason |
|---|---|---|---|
| RSF02-A12-POSITIVE-01 | Separate appointed F2 issuer and independent F2 reviewer; exact selected INSPECT_SOURCE/INSPECT_NATIVE/VERIFY_PROVENANCE target tuple and context | CANDIDATE_ONLY; Draft structure plus later external appointment/rights checks; current DENIED | Class literals do not appoint people. |
| RSF02-A12-POSITIVE-02 | Immutable exact-operation receipt later records principal/grant/policy,target/action/context,source/code/version/length/digest,reason,original provenance,receipt version | CANDIDATE_ONLY; independent receipt verification in later authorized S4; baseline DENIED | Receipt string literal is not current operation proof. |
| RSF02-A12-POSITIVE-03 | Historical immutable audit record exists and a current grant later becomes revoked/expired | CANDIDATE_ONLY; retain history and DENIED current access | Past evidence never overrides current rights. |

**RSF02-A12-NEGATIVE**: `CANDIDATE_ONLY` / `CANDIDATE_ONLY`; execution `NOT_RUN`. Source prerequisites: Actual independent reviewer appointment/identity, source rights, exact cutoff_rule interpretation, current grant/expiry/revocation proof and immutable current operation receipt NOT_SUPPLIED. Independent security/provenance review must verify exact target matching and nonleaking denial. Optional duplicate narrowing needs explicit versioned Owner decision.

| Case | Independently specified input / change | Expected type/state | Reason |
|---|---|---|---|
| RSF02-A12-NEGATIVE-01 | Unappointed principal or issuer acting as own independent reviewer; SAFE principal/capability reused for audit | DENIED constant ACCESS_DENIED; no existence or private reason leak | Appointment, independence and audit rights separate. |
| RSF02-A12-NEGATIVE-02 | Wrong operation, target resource_kind/schema/version/content, cutoff/cohort/context; missing exact source rights/receipt; expiry at valid_until or revoked grant | DENIED; literals/role shape may also be INVALID as applicable | Exact operation and current proof required. |
| RSF02-A12-NEGATIVE-03 | Duplicate principal/operation/exact target tuple | Current Draft permits duplicates; proposed semantic rejection VERSIONED_AMENDMENT_REQUIRED | No unreviewed normalization of ordered arrays. |
| RSF02-A12-NEGATIVE-04 | Empty target_rules schema/version or context_scope.cutoff_rule; absent/null required field; extra grant/appointment field | INVALID TEXT_BOUND/CLOSED_FIELDS; empty literal/parent leaves likewise refuse | F02 separate retain-refusal; no new fields silently added. |
| RSF02-A12-NEGATIVE-05 | Target schema/version length129..65536 presented as if ResourceRef-compatible; wildcard cutoff text without approved meaning | Draft target Text may parse; semantic compatibility BLOCKED pending explicit operational mapping/version | Do not silently assert 128 bound or grant from arbitrary Text. |

**RSF02-A12-MUTATION**: `CANDIDATE_ONLY` / `CANDIDATE_ONLY`; execution `NOT_RUN`. Source prerequisites: Actual independent reviewer appointment/identity, source rights, exact cutoff_rule interpretation, current grant/expiry/revocation proof and immutable current operation receipt NOT_SUPPLIED. Independent security/provenance review must verify exact target matching and nonleaking denial. Optional duplicate narrowing needs explicit versioned Owner decision.

| Case | Independently specified input / change | Expected type/state | Reason |
|---|---|---|---|
| RSF02-A12-MUTATION-01 | Change operation/target tuple/cutoff/cohort/policy version or a receipt byte while reusing old operation approval | DENIED/BLOCKED stale receipt/policy proof; require immutable new operation evidence | Exact action and target binding prevent privilege widening. |
| RSF02-A12-MUTATION-02 | Revoke grant or reach expiry after past allow receipt | DENIED current operation, preserve old historical content/receipt | Revocation is current, not retroactive content rewrite. |
| RSF02-A12-MUTATION-03 | Alter public denial according to private resource existence or original Native failure | BLOCKED nonleaking-denial requirement; retain constant ACCESS_DENIED | Private audit existence is not a public status surface. |

**Downstream identity/invalidation for every case:** Changed audit policy/principal classes/operations/target tuple/context rule requires new verified policy/version and dependent private correspondence/receipt review. Revocation/expiry changes permission for a current operation without rewriting immutable old content or receipt. No audit/SAFE co-grant or Native identity asserted. No full Resource Body/Frame/Digest/Parent resolution/grant/Native witness supplied; no expected full SHA fabricated. Positive cases cannot advance until source preconditions are independently fulfilled.

### Compatibility, accountable decision and deferred work

**S1_CANDIDATE compatibility:** Exact target/context/current receipt semantics clarify contract obligations but are not implemented authorization. Duplicate-refusal is a proposed VERSIONED_AMENDMENT_REQUIRED narrowing. Any explicit appointment/expiry/receipt fields would be a new schema, not a silent addition. target schema/version currently text<=65536 versus ResourceRef<=128 must be reconciled by explicit versioned operational constraint, not falsely reported as current Draft behavior.

**MISSING_OWNER_PROOF / BLOCKED obligations:**

- Actual independent reviewer appointment/identity, source rights, exact cutoff_rule interpretation, current grant/expiry/revocation proof and immutable current operation receipt NOT_SUPPLIED.
- Independent security/provenance review must verify exact target matching and nonleaking denial. Optional duplicate narrowing needs explicit versioned Owner decision.

**Accountable semantic Owner role:** Technical Lead/F2 audit semantic issuer; Academic Owner appoints independent reviewer; IF04/IF07 rights custodians separately accountable. Actual role-holder decision/signature NOT_SUPPLIED. Prior project direction is not that missing proof.

**Independent reviewer role:** Independent F2 security/provenance reviewer, distinct from F2 issuer and candidate author; actual appointment NOT_SUPPLIED. Identity, appointment, completed review/verdict and signature NOT_SUPPLIED. This author cannot approve itself.

**Exact next Owner decision:** Accept/revise/defer exact separate audit-principal/operation/target/context/receipt/revocation semantics, explicitly adjudicate duplicates and cutoff_rule interpretation, and commission external appointment/rights evidence; do not grant access or change default denial.

**Alternatives:**

- Adopt the semantic candidate with external proof conditions, and separately review the proposed duplicate-refusal amendment.
- Retain Draft duplicate acceptance only as historical structure; no operational rights follow.
- Defer operational semantics if exact cutoff interpretation or appointment cannot be supplied.

| Future decision | Consequence |
|---|---|
| ACCEPT | Attributable Owner acceptance of exact semantics remains separate from independent review; only both completed for exact adopted version with conditions fulfilled can yield S1 adoption; no S2–S5 promotion. |
| REVISE | Keep current Draft and immutable evidence; authorize separately versioned changed acceptance/fields, independent compatibility vectors and renewed review. |
| DEFER | Keep S1_NOT_YET_ACCEPTED and blocked downstream operations; no implicit approval. |

S1 requires exact adopted semantic version, attributable Owner acceptance and a separately completed independent semantic review with these conditions resolved. SCHEDULE_INVARIANT_POLICY additionally cannot be unconditionally ratified before adopted B01 semantics. A future reviewer may return ACCEPTED_CANDIDATE_PENDING_OWNER, REVISION_REQUIRED or BLOCKED_BY_EXTERNAL_OWNER; none is an author-supplied verdict. **S2:** exact original resource body/version/parents and rights; **S3:** independent full-domain Golden/freeze; **S4:** issuer/current rights/receipt/actual Native replay; **S5:** exact consumer/IF04/IF05/F3/F5 acceptance all remain separately unauthorized and unproved.

## RSF02-A13 — SCHEDULE_INVARIANT_POLICY

**Status:** S1_CANDIDATE_PENDING_INDEPENDENT_REVIEW; MISSING_OWNER_PROOF; NOT_ADOPTED; BLOCKED_BY_RSF02_B01.

**CURRENT_IMPLEMENTATION:** `body_schema_label=rs-spec-schedule-invariant-policy-body-proposal-v0.1`; `body_version=0.1-DRAFT-NON_ISSUED`. Both exact required wrapper fields, no optional or extra field. Candidate semantic revision `v0.1-CANDIDATE-NON_OPERATIVE` is documentary only; operational `resource_schema/resource_version` NOT_SUPPLIED / NOT_REGISTERED. SOURCE-BYTES parent/profile as in helper contract; policy version (where present) is distinct from wrapper/operational version.

**PROJECT_OWNER_DIRECTION:** Select FIXED_FOUR_WEEKLY_SYN_A only: preserve order/unknowns, W03 annotation-only, accounting_implies_admission=false; require separately adopted PROTOCOL and immutable AF009/PF038 source-input equality; no generic schedule approval. Source: `docs/mvp/v1.0/wu05-rsf02d-owner-decision-matrix-v0.1.json:L284–L301` (pin in source register).

### Exact field and nested helper inventory

| Required field | CURRENT_IMPLEMENTATION validator / exact nested shape | S1_CANDIDATE semantic interpretation |
|---|---|---|
| `protocol_ref` | `ref("PROTOCOL")` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L409–L409` (pin in source register)) | ResourceRef<PROTOCOL>. Direct RSF02-B01 blocking dependency; a registered role vocabulary entry is not an adopted protocol body/schema. One role supports separately scoped schedule anchor/holiday roll, F2 operation scope and F3 research protocol instances; no universal opaque/default protocol. |
| `profile` | `literal("FIXED_FOUR_WEEKLY_SYN_A")` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L410–L410` (pin in source register)) | Literal FIXED_FOUR_WEEKLY_SYN_A only. Exact four original Weekly cutoffs and calendar/session closure, not arbitrary schedules or Monthly/Daily authorization. |
| `preserve_order` | `literal(True)` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L411–L411` (pin in source register)) | Literal true: retain original four positions, distinct tick IDs/orders/contexts and strictly ordered cutoffs. No sorting/reindexing/dropping/refilling failed positions; equal t2/t3 numeric/source values retain distinct context identities. |
| `preserve_unknown` | `literal(True)` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L412–L412` (pin in source register)) | Literal true: preserve original UnknownCause, NotEvaluated, Withheld, original first failure and actual invocation labels; do not fill missing values or replace them with success. This policy body has no unknown union of its own. |
| `no_session_annotation_only` | `literal(True)` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L413–L413` (pin in source register)) | Literal true: W03 2027-W03 is NO_SESSION_WEEK calendar annotation only, never a fifth tick or invented observation. |
| `accounting_implies_admission` | `literal(False)` (`src/pit_research_lab/mvp/f2/resource_bodies.py:L414–L414` (pin in source register)) | Literal false: four positions accounted does not imply eligibility, release, source authenticity, Native replay or F3/F5 acceptance. |

Closed nested records are fully enumerated in the expressions above. ParentRef and ResourceRef recurse only through the exact shared helpers; UInt64 uses closed type/value. Each field and literal is mandatory, no null or Unknown replacement. Order and duplicates follow the shared helper rules plus the explicit role-specific proposals above. Empty literal strings reject by LITERAL; empty list rejects ARRAY_BOUND, except the fixed singleton issuer_cohort rejects by LITERAL. No trimming or sort.

### Observed behavior and proposed invariants

- **CURRENT_IMPLEMENTATION** — Policy parser enforces literal booleans/profile and PROTOCOL ref shape; no B01 semantics. ScheduleInput has wrapper, original_input_refs, invariant_policy_ref, selected_profile. schedule_path_check compares source_input core/PF038, policy ref/AF009, schedule ref/sequence ref and kind/schema/version but still returns NOT_SUPPLIED. Sources: `src/pit_research_lab/mvp/f2/resource_bodies.py:L408–L415` (pin in source register); `src/pit_research_lab/mvp/f2/resource_binding.py:L146–L219` (pin in source register).
- **CURRENT_IMPLEMENTATION** — ScheduleInfluence is only an inert dependency expression; no canonical equality/digest. Fixed source/calendar generator validates actual session rows; it is not a new protocol approval. Sources: `src/pit_research_lab/mvp/f2/resource_binding.py:L222–L239` (pin in source register); `src/pit_research_lab/mvp/f2/synthetic_temporal.py:L303–L349` (pin in source register).
- **S1_CANDIDATE** — Require separately adopted B01 protocol semantics/version/parent mapping and independent proof of equivalent source-input/calendar/policy closure. Immutable chain is ScheduleInput -> DECISION_SCHEDULE.source_input_ref (PF038) -> TEMPORAL-SEQUENCE.schedule_ref, with invariant_policy_ref equal to AF009. Merely matching supplied placeholder cores cannot prove equality. Sources: `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L312–L313` (pin in source register); `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L353–L365` (pin in source register); `src/pit_research_lab/mvp/f2/resource_binding.py:L167–L219` (pin in source register); `docs/mvp/v1.0/wu05-rsf02d-owner-decision-matrix-v0.1.json:L381–L391` (pin in source register).
- **S1_CANDIDATE** — Fixed-four acceptance additionally requires validate_four_ticks, source/calendar/session agreement, W03 annotation, subtype-specific traces and original unknown/failure preservation. Conditional candidate review is possible; no unconditional S1 ratification or operational permission while B01 is missing. Sources: `src/pit_research_lab/mvp/f2/resource_binding.py:L146–L219` (pin in source register); `docs/mvp/v1.0/wu05-rsf02d-owner-decision-record-v0.1.md:L131–L150` (pin in source register); `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L471–L473` (pin in source register).

**S1_CANDIDATE refusals:** Opaque/default/unapproved PROTOCOL; generic 1..4096 parser success as approval; missing/duplicate/swapped/dropped/foreign tick, W03 fifth tick, source/calendar/session mismatch, AF009 policy mismatch, stale PF038 or sequence schedule ref, unknown filling, accounting to admission.

**Unknown/absence:** All selected policy fields are mandatory exact values/records; null, absent key, unknown union or empty string are not substitutes. Missing source/Owner evidence is NOT_SUPPLIED; no absence-to-zero/default/approval. Original Native Unknown/NotEvaluated/Withheld/first failure/invocation in dependent data remain exact and private as required.

**Rights and release — BLOCKED:** No policy grants access; immutable source evidence/right-to-use/operation receipt/IF04 capability/IF05 predicate separately required. Default DENIED and local WITHHELD unchanged.

### Parser and inspected tests (NOT_RUN)

- parse_body: `src/pit_research_lab/mvp/f2/resource_bodies.py:L514–L565` (pin in source register)
- parse_reference_body: `src/pit_research_lab/mvp/f2/resource_bodies.py:L577–L580` (pin in source register)
- validate_body_key: `src/pit_research_lab/mvp/f2/resource_bodies.py:L568–L574` (pin in source register)
- issuance_readiness: `src/pit_research_lab/mvp/f2/resource_bodies.py:L583–L592` (pin in source register)

- test_policy_body_does_not_authenticate_scheduleinput_or_issue_sequence: `tests/unit/mvp_f2/test_resource_bodies.py:L672–L685` (pin in source register) — definition inspected only, NOT_RUN
- test_four_ticks_w03_annotation_and_equal_values_distinct_context: `tests/unit/mvp_f2/test_resource_bodies.py:L835–L846` (pin in source register) — definition inspected only, NOT_RUN
- test_scheduleinput_af009_stale_policy_schedule_and_input: `tests/unit/mvp_f2/test_resource_bodies.py:L1045–L1063` (pin in source register) — definition inspected only, NOT_RUN
- test_policy_mutation_propagates_dependency_expression_not_digest: `tests/unit/mvp_f2/test_resource_bodies.py:L1065–L1073` (pin in source register) — definition inspected only, NOT_RUN
- test_policy_change_requires_new_pf038_dependency_and_sequence_schedule_target: `tests/unit/mvp_f2/test_resource_bodies.py:L1076–L1102` (pin in source register) — definition inspected only, NOT_RUN

### F02 per-field empty-string compatibility verdicts

| Field / empty-string mutation | Current scoped verdict | Compatibility |
|---|---|---|
| protocol_ref.resource_schema | REJECT; scoped Draft TEXT_BOUND (required nonempty Text), never empty-to-Unknown | RETAIN_EXISTING_DRAFT_REFUSAL; accepting empty would require VERSIONED_AMENDMENT_REQUIRED; general CAN Text unchanged |
| protocol_ref.resource_version | REJECT; scoped Draft TEXT_BOUND (required nonempty Text), never empty-to-Unknown | RETAIN_EXISTING_DRAFT_REFUSAL; accepting empty would require VERSIONED_AMENDMENT_REQUIRED; general CAN Text unchanged |
| protocol_ref.content_ref.domain_tag | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| protocol_ref.content_ref.object_schema_version | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| protocol_ref.content_ref.canonical_profile_version | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| protocol_ref.content_ref.digest_algorithm | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| protocol_ref.content_ref.canonical_payload_byte_length.type | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| protocol_ref.content_ref.canonical_payload_byte_length.value | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |
| protocol_ref.content_ref.digest_hex | REJECT; LITERAL for fixed type/domain/schema/profile/algorithm, TEXT_BOUND for integer value/hex text before spelling | RETAIN_EXISTING_DRAFT_REFUSAL; any empty acceptance requires versioned review; no global Text rewrite |

All remaining literal string leaves (including wrapper label/version, enum members and fixed cohort) reject empty by exact literal/role checks. Required boolean/object/list leaves reject empty string by literal/object/array checks. This independently stated verdict covers every selected leaf; it does not change general CAN Text. Parent and value dependencies are not silently inserted into the policy body.

### Positive / negative / mutation requirements — NOT_RUN

**RSF02-A13-POSITIVE**: `PRECONDITION_NOT_SUPPLIED` / `CANDIDATE_ONLY`; execution `NOT_RUN`. Source prerequisites: RSF02-B01 owner-authored adopted PROTOCOL schema/version/semantics and separately attributable F3 review NOT_SUPPLIED; unconditional S1 adoption BLOCKED. Exact original immutable ScheduleInput/source/calendar and policy equivalence NOT_SUPPLIED; A07/A15 and deferred A14/A17 are dependencies, not adopted here. Four cutoffs are 2027-01-07, 01-15, 01-29, 02-05 at 18:00:00+08:00; B03 midnight is not a substitute.

| Case | Independently specified input / change | Expected type/state | Reason |
|---|---|---|---|
| RSF02-A13-POSITIVE-01 | Four original cutoffs at 2027-01-07/15/29 and02-05 18:00+08, exact order/contexts, W03 annotation only, all original unknowns preserved | CANDIDATE_ONLY; structural checks plus later source/calendar/policy equivalence, no admission | Exactly four is this profile only. |
| RSF02-A13-POSITIVE-02 | Separately adopted B01 protocol and immutable ScheduleInput -> PF038 DECISION_SCHEDULE -> TEMPORAL-SEQUENCE.schedule_ref plus identical AF009 policy ref | CANDIDATE_ONLY; B01 and immutable proof preconditions not supplied; current schedule_path_check NOT_SUPPLIED | Conditional review cannot operationally authorize schedule. |
| RSF02-A13-POSITIVE-03 | All four positions accounted, including withheld/unknown/first failing operation, with unchanged invocation provenance | CANDIDATE_ONLY; accounting completed is not eligibility/all-qualified release | Partial failures remain present; no fabricated Native receipt. |

**RSF02-A13-NEGATIVE**: `CANDIDATE_ONLY` / `CANDIDATE_ONLY`; execution `NOT_RUN`. Source prerequisites: RSF02-B01 owner-authored adopted PROTOCOL schema/version/semantics and separately attributable F3 review NOT_SUPPLIED; unconditional S1 adoption BLOCKED. Exact original immutable ScheduleInput/source/calendar and policy equivalence NOT_SUPPLIED; A07/A15 and deferred A14/A17 are dependencies, not adopted here. Four cutoffs are 2027-01-07, 01-15, 01-29, 02-05 at 18:00:00+08:00; B03 midnight is not a substitute.

| Case | Independently specified input / change | Expected type/state | Reason |
|---|---|---|---|
| RSF02-A13-NEGATIVE-01 | Unapproved/missing PROTOCOL or opaque current/latest protocol default; generic1..4096 schedule parser succeeds | BLOCKED B01 and no generic schedule acceptance | Role vocabulary is not adopted schema. |
| RSF02-A13-NEGATIVE-02 | Duplicate/swapped/dropped/foreign fifth tick, W03 converted to tick, equal t2/t3 merged, source/calendar/session disagreement | INVALID fixed-four layered requirements or BLOCKED source proof; no sort/refill | Preserve original order/membership and calendar closure. |
| RSF02-A13-NEGATIVE-03 | AF009 differs from ScheduleInput invariant policy; stale PF038 input core or TEMPORAL-SEQUENCE.schedule_ref target | INVALID AF009_POLICY_MISMATCH/STALE_SCHEDULE_INPUT/STALE_SEQUENCE_SCHEDULE structural checks; immutable verification still required | All chain links are exact and immutable. |
| RSF02-A13-NEGATIVE-04 | Any policy boolean inverted; accounting treated as admission; unknown filled; B03 midnight replaces Weekly18:00 | INVALID literal or BLOCKED semantic profile/no-promotion | Fixed profile and no-admission constraints mandatory. |
| RSF02-A13-NEGATIVE-05 | Empty protocol_ref resource_schema/version; null/unknown scalar, extra protocol fields; missing/duplicate keys | INVALID scoped Text/CLOSED_FIELDS/DUPLICATE_KEY; CAN Text unchanged | F02 field compatibility, no unbounded extension. |

**RSF02-A13-MUTATION**: `CANDIDATE_ONLY` / `CANDIDATE_ONLY`; execution `NOT_RUN`. Source prerequisites: RSF02-B01 owner-authored adopted PROTOCOL schema/version/semantics and separately attributable F3 review NOT_SUPPLIED; unconditional S1 adoption BLOCKED. Exact original immutable ScheduleInput/source/calendar and policy equivalence NOT_SUPPLIED; A07/A15 and deferred A14/A17 are dependencies, not adopted here. Four cutoffs are 2027-01-07, 01-15, 01-29, 02-05 at 18:00:00+08:00; B03 midnight is not a substitute.

| Case | Independently specified input / change | Expected type/state | Reason |
|---|---|---|---|
| RSF02-A13-MUTATION-01 | Policy/protocol/original input/calendar/annotation/order changes while old PF038/AF009/schedule/sequence refs retained | BLOCKED stale dependency chain; independently verify new input core -> new schedule -> sequence target plus AF009 | No computed digest expected; immutable dependency propagation only. |
| RSF02-A13-MUTATION-02 | Replace failed/unknown position with another passing one or reorder without new approved schedule | INVALID fixed-four membership/unknown/order; no all-qualified release | Accounting cannot repair unavailable facts. |
| RSF02-A13-MUTATION-03 | Change B01 semantics to another protocol instance sharing role label | BLOCKED exact protocol version/parent/owner equivalence; no generic approval | One role supports scoped instances, no universal protocol semantics. |

**Downstream identity/invalidation for every case:** Changed policy/protocol/original input/order/calendar/annotation requires verified new ScheduleInput SOURCE-BYTES parent, new PF038 in DECISION_SCHEDULE, new schedule target in TEMPORAL-SEQUENCE and AF009 consistency, then dependent bindings/experiment refs. Stale old cores refuse, never claim recomputed digest or equality. No full Resource Body/Frame/Digest/Parent resolution/grant/Native witness supplied; no expected full SHA fabricated. Positive cases cannot advance until source preconditions are independently fulfilled.

### Compatibility, accountable decision and deferred work

**S1_CANDIDATE compatibility:** Literal fields retained; source/calendar/PF038/AF009 layered obligations are acceptance prerequisites, not new Draft fields. Different tick counts/profile, unknown/order handling, W03 interpretation, protocol target or equality mapping needs a new approved operational version/registered amendment and independent Golden. The other 12 Draft roles remain unadopted; no generic schedule authorization.

**MISSING_OWNER_PROOF / BLOCKED obligations:**

- RSF02-B01 owner-authored adopted PROTOCOL schema/version/semantics and separately attributable F3 review NOT_SUPPLIED; unconditional S1 adoption BLOCKED.
- Exact original immutable ScheduleInput/source/calendar and policy equivalence NOT_SUPPLIED; A07/A15 and deferred A14/A17 are dependencies, not adopted here.
- Four cutoffs are 2027-01-07, 01-15, 01-29, 02-05 at 18:00:00+08:00; B03 midnight is not a substitute.

**Accountable semantic Owner role:** F2 calendar/source/evidence Owner and Member B/F3 schedule/PROTOCOL Owner; neither substitutes for the other. Actual role-holder decision/signature NOT_SUPPLIED. Prior project direction is not that missing proof.

**Independent reviewer role:** Independent F2 temporal/provenance reviewer and independent F3 protocol reviewer; actual identities NOT_SUPPLIED. Identity, appointment, completed review/verdict and signature NOT_SUPPLIED. This author cannot approve itself.

**Exact next Owner decision:** Accept candidate for independent conditional review, revise, or defer. Unconditional S1 adoption requires separately attributable B01 semantics plus independent F2/F3 immutable PF038/AF009 path and source/calendar equivalence proof. Review acceptance never authorizes operations.

**Alternatives:**

- Review candidate conditionally with B01 and immutable equality explicitly blocking adoption/use (proposed).
- Defer until F3 supplies adopted B01 semantics.
- Generic schedules or another temporal profile require separate scope, schema/version and independent vectors; no default expansion.

| Future decision | Consequence |
|---|---|
| ACCEPT | Attributable Owner acceptance of exact semantics remains separate from independent review; only both completed for exact adopted version with conditions fulfilled can yield S1 adoption; no S2–S5 promotion. |
| REVISE | Keep current Draft and immutable evidence; authorize separately versioned changed acceptance/fields, independent compatibility vectors and renewed review. |
| DEFER | Keep S1_NOT_YET_ACCEPTED and blocked downstream operations; no implicit approval. |

S1 requires exact adopted semantic version, attributable Owner acceptance and a separately completed independent semantic review with these conditions resolved. SCHEDULE_INVARIANT_POLICY additionally cannot be unconditionally ratified before adopted B01 semantics. A future reviewer may return ACCEPTED_CANDIDATE_PENDING_OWNER, REVISION_REQUIRED or BLOCKED_BY_EXTERNAL_OWNER; none is an author-supplied verdict. **S2:** exact original resource body/version/parents and rights; **S3:** independent full-domain Golden/freeze; **S4:** issuer/current rights/receipt/actual Native replay; **S5:** exact consumer/IF04/IF05/F3/F5 acceptance all remain separately unauthorized and unproved.

## Cross-cutting findings and dependency boundary

| Issue | State | Required preservation / unresolved proof |
|---|---|---|
| F01 | BLOCKED | PER_CUTOFF_BINDING.app_axes.pit_status is currently only UNRESOLVED. Stronger WITHHELD must survive in a separately authorized immutable no-release status view visible to every consumer, with independent consistency/nonleakage proof. detached_release returns a local refusal, not proof that this separate view exists or a CAN Withheld with a supplied policy. SEMANTIC_TRACE remains deferred; if separate view is insufficient, a versioned AppAxes/body/contract amendment is required. |
| F02 | DRAFT_ONLY_NONEMPTY_RETAINED | Draft text() requires >0 bytes; general CAN Text/TextSchema min_bytes=0 is unchanged. Each empty-string case below has its own retain-rejection/versioned-review verdict. No global Text tightening or silent empty-to-Unknown substitution. |
| F04 | FIXED_FOUR_LAYERED_ONLY | validate_four_ticks plus schedule_path_check plus original source/calendar/session and AF009/PF038 checks are all required for fixed-four. Generic Draft parser success on 1..4096 rows is never generic accepted schedule. Equal declarations alone do not verify immutable bytes. |
| G04 | NOT_SUPPLIED_NOT_EVALUATED | Actual Native Attempt format/witness/correspondence and no-outcome remain unproved. Missing state cannot become a successful NativeSummary; no invented NATIVE_RECEIPT, first failure or successful invocation. Any tagged no-outcome representation requires separately reviewed CAN07 amendment and vectors. |
| G09 | SELECTED_PENDING_CONTRACT_RATIFICATION | Owner selected root container=1, nested dict/list +1, scalar +0, maximum64; independent exact64/65 vectors and formal contract clarification/amendment remain missing. P2-DEPTH-64/65 stay excluded; _CONTAINER_CEILING unchanged. |
| G10 | BOUNDED_WORDING_RECONCILIATION_ONLY | SOURCE_BYTES_CODEC_NOT_SUPPLIED is stale only for accepted bounded SOURCE-BYTES codec/eight complete positives. Resource Body/semantic owner/rights/original Native/full-domain replay blockers remain. No code or historical wording changed. |
| ORACLE_CAN03 | SCOPED_HISTORY_ONLY | ORACLE-02 includes94 (8 complete SOURCE-BYTES positives,80 narrow refusals,6 relations), excludes16. CAN03 overlay:61 scoped matches+6 test-only relation diagnostics;27 negative operations outside scoped production coverage; not all-domain Golden acceptance. No historical EXECUTED or PENDING label is an execution or approval in this authoring run. |

Sources per finding are repeated in the JSON boundary_findings with full pins. No SOURCE_BYTES wording reconciliation is applied to existing code. B01–B04 remain unapproved/unregistered/unissued, as shown below; a request direction is not its body schema.

| Request | Role / accountable roles | Status / dependency |
|---|---|---|
| RSF02-B01 | PROTOCOL — Member B/F3 protocol owner with F2 calendar/Native consultation; independent F3 reviewer. | OWNER_REQUEST_SCOPE_SELECTED / MISSING_OWNER_PROOF / BLOCKED / SCHEMA_NOT_REGISTERED / RESOURCE_NOT_ISSUED; direct A13 prerequisite |
| RSF02-B02 | HORIZON_MATURITY — Member B/F3 research-method owner, consulted F5; independent methods reviewer. | OWNER_REQUEST_SCOPE_SELECTED / MISSING_OWNER_PROOF / BLOCKED / SCHEMA_NOT_REGISTERED / RESOURCE_NOT_ISSUED; later temporal/consumer prerequisite only |
| RSF02-B03 | EXECUTION_RULES — F5 execution-policy owner with F3/F2 interface consultation; independent F5 reviewer. | OWNER_REQUEST_SCOPE_SELECTED / MISSING_OWNER_PROOF / BLOCKED / SCHEMA_NOT_REGISTERED / RESOURCE_NOT_ISSUED; later temporal/consumer prerequisite only |
| RSF02-B04 | EVALUATION_PROTOCOL — Joint F3 methodology and F5 evaluation owners; separately attributable reviews. | OWNER_REQUEST_SCOPE_SELECTED / MISSING_OWNER_PROOF / BLOCKED / SCHEMA_NOT_REGISTERED / RESOURCE_NOT_ISSUED; later temporal/consumer prerequisite only |

## Exact source-byte and Git-blob register

Every citation range refers to this pinned raw source; external RSF02S1_SOURCE_PINS.json includes actual line content, helper snippet hashes, test definitions and original JSON pointers. Full-file hashing is provenance, not an invented resource identity or reviewer signature.

| Exact source path | Bytes / lines | SHA-256 of complete raw bytes | Git blob SHA-1 |
|---|---|---|---|
| `docs/mvp/v1.0/shared-interface-contract-v0.1.md` | 140871 / 1–764 | `66bef5b0bb8240214ec8ea14c3c94c8748e2944270883c56de3ae7f27355428b` | `d028005f6ac854fc3cde965b562dba4e449159cf` |
| `docs/mvp/v1.0/ux-adr-01-temporal-execution-contract-v0.1.md` | 23544 / 1–143 | `abb04bba20ce8640c38b2406aa662ae86ff3d6df892343b2e6d780c3073c01db` | `96d463c40a49d94e0b206be3851e26063fc6c581` |
| `docs/mvp/v1.0/wu05-rsf02d-owner-decision-record-v0.1.md` | 37193 / 1–290 | `c894a5d19a157724d66661a1ea67b989d7014a0658073d549ec59070f797ba67` | `812017db15e5363e9309f98bfed149fc914860a5` |
| `docs/mvp/v1.0/wu05-rsf02d-owner-decision-matrix-v0.1.json` | 47386 / 1–568 | `17ac673755fe26957c1a7441bac08ef0108e195ceab6fe2576b5920f7311fae6` | `b436aa90156b73deca2c0d85743968b6473b9531` |
| `docs/mvp/v1.0/f3-f5-research-methods-decision-spec-v0.1.md` | 21396 / 1–164 | `8d41eb8beba803855a07d187e81b15d57750a579400d83867dece92f8dd3f546` | `17c184db9966e7268131738e44bbc4de1f1b5a8a` |
| `src/pit_research_lab/mvp/f2/resource_contracts.py` | 13024 / 1–379 | `580f9afd0be0719aa63bfc70af309fe7b04e5619c07816dd9716d47510b724d9` | `b201aae33c28ce432a34c3450858da1122309014` |
| `src/pit_research_lab/mvp/f2/resource_bodies.py` | 20470 / 1–592 | `d53f8021b826864906f4acfba69327e4fdcb12712ec2f1c87c22b0704e0f40ea` | `190329d898bfc20cf655d76c5c25f1bb829b9b1e` |
| `src/pit_research_lab/mvp/f2/resource_binding.py` | 21098 / 1–544 | `e7efe7054e87e736ae988111903fabbd4bd17344cf006fb5c504b8e426b78110` | `9e6e75d01236e25721b3183713fbffb871f14508` |
| `src/pit_research_lab/mvp/f2/resource_access.py` | 4108 / 1–118 | `994260e95afb03c519461f0249ad8b530850e7df9614fa852b1e9f3be531e49e` | `b4be5a3b2aaa3c30a01b9bae3cc11b6e5ea8c222` |
| `src/pit_research_lab/mvp/if03/canonical_codec.py` | 21719 / 1–619 | `1a44faf8e6f243f4e9e22c68f61277dad1836aee6d69e7560dd4241aef3aa2e2` | `8ae2d98073337a3dbb57dd1fc283148ec914215a` |
| `src/pit_research_lab/mvp/if03/domain_registry.py` | 8915 / 1–201 | `3a29e4402584c3c653e61e8fa9d7fe8d9c2b0fdd2b03877eb5d48b482a130b18` | `0d87d0e2ba86873a8beed17d55b0da33f3a0962d` |
| `src/pit_research_lab/mvp/if03/typed_references.py` | 17124 / 1–407 | `9e07f4a9d01b59e69df3102d101cdf2ed79aaf03e03cb1e2d4a9cb479b51b828` | `fb50886716ef0faafe99b1454712a8ac827f394e` |
| `src/pit_research_lab/domain/ratio.py` | 13897 / 1–373 | `018953c2631bb197ff505ec1cb14ab4191b46ebfbcca4670017080e7cafd6996` | `69f6537642e0a86986f3ca07d1f5e83abc3d39ed` |
| `src/pit_research_lab/domain/contracts.py` | 24933 / 1–822 | `d0a15387c919cdeafa7fc166952f9878487ae0337ec4ff92327b4c9ceb0a3bac` | `b62db1a971c72b8130032be5d10da339c0e14e81` |
| `src/pit_research_lab/mvp/f2/weekly_sequence.py` | 20140 / 1–525 | `367153643a98b29161d5b07502db0bbd3cce823a8867af3165177593f3a18fc2` | `03a4fdcbcc7a653bcb06c3b3d38128cdd8bf3091` |
| `tests/unit/mvp_f2/test_resource_bodies.py` | 65099 / 1–1625 | `f17bfe48be9b0936606c63628f877c581fef303e5f14a142a904c8adad138343` | `93e71f6fe6f3f0cae37d364ea22c6d7112c1a4e0` |
| `tests/unit/mvp_f2/data/derived_observations_v0.1.json` | 5440756 / 1–1 | `b9e1babbcc86b0e70ed5589972259fcbe6b666a38d2e7eff77d108f448e4dc0e` | `d5db7d9e68b44a990d438db217b0cd7602cca8c3` |
| `tests/fixtures/mvp_if03/wu05_oracle02_scoped_freeze_v0_1/FREEZE_MANIFEST.json` | 139339 / 1–3943 | `9099a4faede3c893ec57dc936d33741b1c6a1ac5b8b6f612d56219808d4a73b1` | `d96c5924e26c9320ccad90aa88384d583e6be1ee` |
| `tests/fixtures/mvp_if03/wu05_can03_v0_1/coverage_matrix.json` | 160207 / 1–3607 | `ae61c798261753d4533fe610238d83da26ee7ebc44c69c019b5d6b6a27c9861f` | `0ccfe6a46febc8d11a8e2d9989f69d546290a888` |
| `src/pit_research_lab/mvp/f2/synthetic_temporal.py` | 13041 / 1–352 | `129b01a261fa17d94e2c1338ebb462d9b6679512335cb79c82fe685ad71317b0` | `056331490189343e2542ee12f7550bbb6e65bb48` |
| `src/pit_research_lab/mvp/f2/synthetic_contracts.py` | 20802 / 1–583 | `599b6005bd323aad64b3b541f0a0b84c7dd1982b31ade6f432645b1964f6ba56` | `e7663d159c5bbd58a47ac2653daf5d2fbd2d42d9` |
| `tests/unit/mvp_f2/data/temporal_foundation_v0.1.json` | 72800 / 1–2152 | `3b81aae8e3242468c3076911861a13b6f1646f42d068be67b316af9caef1c373` | `058123905a746d50e8148ee49b1f9e155250b862` |
| `tests/unit/mvp_f2/test_synthetic_temporal.py` | 28470 / 1–730 | `b952bcb631dd61758e46508d188c28f8c9f7f0ffb793c0b2a13f862f947c7e8a` | `fcaff853844d4f8873176b696c0322d956ef2b16` |
| `tests/unit/mvp_f2/test_weekly_sequence.py` | 35485 / 1–1010 | `8baac7d655a29d6698957b1339a4d1af66b373c6e86dfa025ef19dfce2518369` | `7e24dd09bbf21709cff8d9f8a82c2391735e4d3f` |
| `tests/unit/mvp_f2/test_wu05_can01_codec.py` | 24577 / 1–616 | `e4eff83bd57d91a54f2726349606d9f40d914bde7238f5dd14218322fb2b9ec6` | `eb0e29ccccf22fb83d4496a840db0a98ac87b05f` |
| `tests/unit/mvp_f2/test_wu05_can02_graph.py` | 9121 / 1–259 | `b6caade087c8a4283913060e23320d0d1280591ef54b73599d86a97693b1e138` | `1cb4ca0e83221997b79be174cf67bb6cbc40e5e6` |
| `tests/unit/mvp_f2/test_wu05_can02_references.py` | 24293 / 1–605 | `e8098cc275c5f733457b89033ee76715eb5725f812c02c9861ce96b69195aacc` | `e03af9c215d3463ffef7cc6d85c878ae78e6c38d` |
| `tests/unit/mvp_f2/test_wu05_can02_registry.py` | 3679 / 1–89 | `71223e5be69fc9401692dccc77101e6bcad5dc1d9c18513e9eecf631bdbe9fa8` | `005ceabe562056c93ad38986f97439e7a248c76d` |
| `tests/unit/mvp_f2/test_wu05_can03_adversarial.py` | 25381 / 1–644 | `3ef0b24f28b7288b34bfab87b4732c9e5b5d368550b9043c07c430152f04157d` | `802e23d9db50667a5f86947d2d9b0d5132a90495` |
| `tests/unit/mvp_f2/test_wu05_can03_conformance.py` | 13458 / 1–325 | `783f92a788e087f8a2716390eddba7ecc126c7b0346e3fb3963b1db7233a1529` | `b4a6138b145bcb96d54018797764b72d5eb2f84c` |
| `tests/unit/mvp_f2/test_wu05_can03_coverage.py` | 7360 / 1–178 | `1d160651d147a53b27237d610c12f2404cdc4a935beda6988d584ffdfa379a1e` | `87beb1ce688d539c3a19d66ee2cfe1442c9d78a0` |
| `tests/unit/mvp_f2/test_wu05_oracle01.py` | 23273 / 1–564 | `93f5e950b7f5be85e2c10579921a5fdf290870e8598f6a97d39e9dc75a6fc778` | `fba390b7240d19390dc89ee2b68df3afa5c8f43d` |
| `tests/unit/mvp_f2/test_wu05_oracle02_freeze.py` | 22724 / 1–552 | `f9f20cf918499568fc2940b21f81374465532c59c78745b2fe0b5147c954f730` | `948a637e0648965637ec5331f281e3af5ec6bae8` |
| `tests/unit/mvp_f2/wu05_can03_expected.py` | 5842 / 1–137 | `df84c57dd9bfbc2b1b7fe8e6c887cd027469cedaee911b678d0c868b6b2259b7` | `7ca5d9cd3d8e82ac66d47fa245a57efa4427b07a` |
| `tests/unit/mvp_f2/wu05_oracle_reference.py` | 11242 / 1–306 | `e1c7b81d4ba435bfce29514e92c374c9e6cf0dda3b86243c957fd32520117a35` | `56eb7103344992551a0c46dab3a4b2706a80c075` |
| `tests/fixtures/mvp_if03/wu05_oracle01_v0_1/cases.json` | 73456 / 1–2783 | `c437c9f30cb7588f8d2e8703c6d37a5a81443077a3336abf24a9c87b4a634b1d` | `5d38c0b5e6a29ebdaf1c311694bd3f51744e5d09` |
| `tests/fixtures/mvp_if03/wu05_oracle01_v0_1/source_pins.json` | 14440 / 1–330 | `bcc65ad5bd2c8b2a70174e91ffaaaf7e8cf8a6eaf3be5b08484a7140778569b4` | `2e87d93dfddb79a58c3cddd54ead84c5f3885e38` |
| `tests/fixtures/mvp_if03/wu05_oracle01_v0_1/domain_coverage.json` | 36178 / 1–661 | `0b782d09485de122ed711a93ac1830105284e15d4b90b1da66217c8730a6f534` | `df6fb9fd4e52810280407bb9fa4ba1dbb979711e` |
| `tests/fixtures/mvp_if03/wu05_oracle01_v0_1/schedule_declaration.json` | 4256 / 1–114 | `9d02ef0202830e40b1c3fbaf9c9de299d388dac35774fb0b64addc636c1b355c` | `2e71d9dbe891d930221c8da988b3e0c74c86613d` |
| `tests/fixtures/mvp_if03/wu05_oracle01_v0_1/README.md` | 6827 / 1–96 | `34611859bbcabfc532f74bb95019a3ed69c3debe75d9d5fbf55040b845e00a0b` | `b801e1fc4128f2fd6a63666fe87e9b092d599e8f` |

External authorizing document `/mnt/c/Users/rooki/Downloads/MVP-F2-WU05-RSF02-S1_Requirements_v0.1.md`: 20216 bytes; SHA-256 `84d91741c371c05624d9bd382bd7ccb0cbdf7b871345abfdabc5480bf685d5f8`; 142 lines. Git blob NOT_APPLICABLE (external supplied requirements).

No production registration, ratified contract edit, source/test/fixture edit, resource issuance, Git stage/commit/push/PR/merge or independent-review self-approval is authorized. S1_RATIFIED=false. Stop at independent content review.
