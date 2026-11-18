# Five-schema Owner adjudication candidate v0.1

**Decision preparation only — NON_OPERATIVE / NOT_RATIFIED.** Task `MVP-F2-WU05-RSF02-S1-RATIFY`; pinned Academic `main` `aea25f1a3462666b27c213a508c8dc846eab04ab` (PR #30). This author proposes two pending-proof decisions, two required revisions and one external-dependency deferral. No new attributable specialist approvals or independent S1 verdicts were supplied. **All five `S1_RATIFIED=false`; every S2–S5 flag is false.**

The companion `wu05-rsf02s1-ratify-decision-gate-matrix-v0.1.json` contains exactly five decision rows, the full unchanged 55-case/15-group carryover and explicit cross-owner/stage blockers. Both new documents stay untracked and unstaged. External RATIFY01 reports supply source pins, approval gaps, compatibility, handoff and integrity records. Self-authored file hashes are not third-party consent.

## Authority and version boundaries

Evidence categories: `RATIFIED_INTERFACE_RULE` means the exact scoped Shared RT01/UX interface rule; `PROJECT_OWNER_DIRECTION` is RSF02-D scope/direction; `CURRENT_IMPLEMENTATION` is observed bounded Draft code; `S1_CANDIDATE` is a proposal; `MISSING_OWNER_PROOF` records absence; `BLOCKED` bars affected promotion. Shared RT01 approval does not ratify these Resource schemas, appoint specialist Owners/reviewers or grant rights. Source: `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L666–L762`; `docs/mvp/v1.0/ux-adr-01-temporal-execution-contract-v0.1.md:L129–L143`.

The prior S1 documentary revision remains `v0.1-CANDIDATE-NON_OPERATIVE`, originally pinned to `919236a3ee6d0c83a41251a363ff736b7c50d5f7`. RSF02-D retains `ce3393df09d1b9126c9b78e854a7f8f44bd37da6`. PR #30 is a separate provenance overlay. This decision-record revision is documentary only. Draft `body_schema_label`, Draft `body_version`, semantic rules/policy edition, operational `resource_schema/resource_version`, IF03 domain/profile and SOURCE-BYTES content identity are different axes. No `APPROVED` label replacement or SHA equivalence across versions is asserted.

Current transport helpers require exact closed keys, real literal types, UTF-8 object JSON with duplicate object keys refused, nonempty Draft Text1..65536 bytes (ResourceRef labels1..128), arrays1..4096 and preserved order. `items()` does not de-duplicate. General CAN Text may be empty. Typed Parent/ResourceRef shape does not authenticate content/source/right; IF03 `require_resource_semantics` still refuses unapproved schemas. Sources: `src/pit_research_lab/mvp/f2/resource_contracts.py:L89–L194`; `src/pit_research_lab/mvp/f2/resource_contracts.py:L345–L368`; `src/pit_research_lab/mvp/if03/typed_references.py:L127–L157`.

| Decision | Role | Proposed Owner outcome | S1 |
|---|---|---|---|
| RSF02-A06 | TIMEZONE_RULES | SELECTED_PENDING_PROOF | false |
| RSF02-A09 | NUMERIC_POLICY | SELECTED_PENDING_PROOF | false |
| RSF02-A11 | OBSERVATION_RELEASE_POLICY | REVISION_REQUIRED | false |
| RSF02-A12 | AUDIT_ACCESS_POLICY | REVISION_REQUIRED | false |
| RSF02-A13 | SCHEDULE_INVARIANT_POLICY | DEFERRED_EXTERNAL_DEPENDENCY | false |

## RSF02-A06 — TIMEZONE_RULES

**Proposed Owner outcome: `SELECTED_PENDING_PROOF`.** Evidence: `S1_CANDIDATE / MISSING_OWNER_PROOF / BLOCKED`; this is a source-backed author decision candidate, not an attributable Owner signature.

Candidate source: `docs/mvp/v1.0/wu05-rsf02s1-five-schema-semantics-candidate-v0.1.md:L65–L211`; Git blob `3ab659e8f53239e0f4aaf8eedfc3139020502224`; complete source-byte SHA-256 `0f03bcb3a51a8a21e78f9a92c7f7ef1818471d83e38d4715c3a451bce839ec79` (123544 bytes). Candidate matrix: `docs/mvp/v1.0/wu05-rsf02s1-five-schema-adoption-matrix-v0.1.json`, blob `f146386f07af077dfa8cf03cc40dc3c37ad36527`, raw SHA-256 `08ae7b586c400d2730c256a0dee5bb7ee0f5736b5b244a2f0a358040dd7c828e`. All are read at `aea25f1a3462666b27c213a508c8dc846eab04ab`.

Exact candidate label `v0.1-CANDIDATE-NON_OPERATIVE`; Draft `body_schema_label=rs-spec-timezone-rules-body-proposal-v0.1` and `body_version=0.1-DRAFT-NON_ISSUED`. Proposed operational `resource_schema=NOT_REGISTERED`, `resource_version=NOT_REGISTERED`; semantic edition/version `NOT_SUPPLIED`. Original candidate operational wording is preserved in the JSON and was not rewritten in history.

**CURRENT_IMPLEMENTATION:** Draft requires Asia/Taipei, SECOND, +08:00 offset intervals and inclusive uninterrupted coverage. It checks declared offset arithmetic and interval adjacency, not authentic named-zone edition, original timestamp closure or rights. The existing test interval begins at t1 and omits earlier original publications.

**PROJECT_OWNER_DIRECTION:** Restrict to Asia/Taipei, +08:00, SECOND precision and exact covered original SYN-A publication/cutoff interval; versioned externally reviewed rules_source_ref required; host tzdb or inferred DST rules are not authority. Source: `docs/mvp/v1.0/wu05-rsf02d-owner-decision-matrix-v0.1.json:L151–L168`.

**Selected decision candidate:** Retain Asia/Taipei/+08:00/SECOND; require a reviewed immutable rules_source_ref, exact rules_version and inclusive uninterrupted coverage of the entire selected original publication/calendar/cutoff closure. Minimum 2026-11-05T12:00:00+08:00 through 2027-02-05T18:00:00+08:00; extend for any additional selected source or calendar timestamp. Do not use host tzdb as unreviewed authority.

**Explicit version-strategy candidate:** `PROPOSE_RETAIN_BOUNDED_SEMANTICS_PENDING_EDITION_PROOF`. Actual Project Owner acceptance of this new strategy is `NOT_SUPPLIED`; recording the proposal does not sign for the Owner. No parser edit selected. Original-closure/source authenticity is a semantic acceptance obligation beyond structural parsing. Any new fields, helper domain, precision, zone, offset, interval acceptance/refusal or operational validation change requires an explicitly reviewed registered operational version/amendment; the current Draft is not that version.

Source crosswalk: `src/pit_research_lab/mvp/f2/resource_bodies.py:L349–L356`; `src/pit_research_lab/mvp/f2/resource_bodies.py:L555–L564`; `src/pit_research_lab/mvp/f2/resource_binding.py:L45–L116`; `src/pit_research_lab/mvp/f2/resource_binding.py:L136–L143`; `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L459`; `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L712–L722`.

**Required semantic Owner roles:** Technical Lead/F2; F4/Data source custodian for original rule provenance and rights. Actual individual, appointment, exact-version approval, approval file ID/bytes/hash/provenance: `NOT_SUPPLIED`.

**Independent reviewer conditions:** Independent temporal/rules and source-provenance reviewer, distinct from author/issuer. Identity, appointment, independence evidence and exact-version verdict: `NOT_SUPPLIED`. The author cannot fill this role or self-certify review. Reviewer must reconcile the cited fields/helpers, old/new acceptance/refusals, source authority and exact immutable version before a genuine S1 verdict.

**Decisive blockers / required proof:**

- Attributable timezone/rule custodian appointment and exact-version semantic Owner decision
- Reviewed original rule edition/source bytes, immutable source reference, authority and right to use
- Independent temporal/source reviewer appointment and exact candidate/version verdict
- Independent inclusive uninterrupted full-original-publication/four-cutoff/calendar closure verification

The exact selected cutoffs are t1=2027-01-07T18:00:00+08:00, t2=2027-01-15T18:00:00+08:00, t3=2027-01-29T18:00:00+08:00, t4=2027-02-05T18:00:00+08:00. Every comparison below uses the original declared +08:00/SECOND timestamp; no host tzdb is queried. Matching clocks do not merge source origins.

| Original source | Original source_text | t1 | t2 | t3 | t4 |
|---|---|---|---|---|---|
| O | 2026-11-05T12:00:00+08:00 | BEFORE | BEFORE | BEFORE | BEFORE |
| N | 2026-12-05T12:00:00+08:00 | BEFORE | BEFORE | BEFORE | BEFORE |
| D1 | 2027-01-07T17:59:59+08:00 | BEFORE | BEFORE | BEFORE | BEFORE |
| D2 | 2027-01-07T18:00:00+08:00 | AT | BEFORE | BEFORE | BEFORE |
| D3 | 2027-01-29T18:00:01+08:00 | AFTER | AFTER | AFTER | BEFORE |
| N12 | 2027-01-07T18:00:00+08:00 | AT | BEFORE | BEFORE | BEFORE |
| N23 | 2027-01-29T18:00:01+08:00 | AFTER | AFTER | AFTER | BEFORE |

Exact original pointers are `/sources/{0..6}/source/request/attempts/0/supplied/proof_candidate/timestamp` in `tests/unit/mvp_f2/data/derived_observations_v0.1.json:L1`, in O/N/D1/D2/D3/N12/N23 order. The JSON records every exact pointer and byte pin. D1 is one second BEFORE t1; D2 and N12 are AT t1 and fail strict-before at t1; D3 and N23 are one second AFTER t3. t2/t3 remain distinct contexts. The existing test example at `tests/unit/mvp_f2/test_resource_bodies.py:L434–L442` covers t1..t4 only and excludes O, N and D1; it is insufficient as a semantic positive.

The original SYN-A temporal foundation additionally includes roster publication `2027-01-04T08:00:00+08:00` and revenue declarations `2027-01-07T17:59:59+08:00`, `2027-01-07T18:00:00+08:00`, `2027-01-29T18:00:01+08:00` at `/input_spec/roster/0/publication`, `/input_spec/revenue_events/{0,1,3}/publication`. They remain distinct origins; the minimum inclusive interval covers them. Calendar/session and later-selected original timestamps must be inventoried and extend coverage if needed; SYN-B/future prices/labels do not become decision inputs. No rule edition/right is supplied.

Uninterrupted interval semantics: first start=coverage.first_local; every start<=end<=last; next start=previous end+1 second; final end=coverage.last_local. Reject gaps, overlap, reversal, duplicates or reordering. Full-original closure and reviewed named-zone source evidence remain independent of this arithmetic.

**Inspected current test definitions — all NOT_RUN:**

- `test_rule_table_draft_does_not_supply_reviewed_rule_evidence` — `tests/unit/mvp_f2/test_resource_bodies.py:L634–L642`.
- `test_strict_before_edges_and_declared_utc` — `tests/unit/mvp_f2/test_resource_bodies.py:L812–L816`.
- `test_time_zone_precision_naive_rules_and_origin` — `tests/unit/mvp_f2/test_resource_bodies.py:L818–L833`.
- `test_rule_table_rejects_gap_overlap_and_reversed_bounds` — `tests/unit/mvp_f2/test_resource_bodies.py:L1308–L1317`.

**Later versioned-amendment review requirements — NOT_RUN; no executable tests added:**

- Original minimum first/last inclusive endpoints and all 28 source-to-cutoff comparisons; cutoff-only rule interval must remain semantically blocked.
- Rule edition/source/ref/endpoint mutations, gap/overlap/reordering, additional calendar closure and host-tzdb substitution refusal.

**Separate S2–S5 restrictions:** S2 exact original Body/version/typed-parent/rights proof; S3 independent full-domain Golden and freeze; S4 actual issuer/current grant/revocation/receipt and genuine Native two-channel replay; S5 reader/IF04/IF05/F3/F5/F6 acceptance all remain false, unproved and unauthorized. No stage advances from this card.

**Next Action / Owner:** Academic Owner identifies accountable rules custodian and independent temporal reviewer; F2/F4 supply the exact edition/provenance/right and full timestamp closure for their separate review.

## RSF02-A09 — NUMERIC_POLICY

**Proposed Owner outcome: `SELECTED_PENDING_PROOF`.** Evidence: `S1_CANDIDATE / MISSING_OWNER_PROOF / BLOCKED`; this is a source-backed author decision candidate, not an attributable Owner signature.

Candidate source: `docs/mvp/v1.0/wu05-rsf02s1-five-schema-semantics-candidate-v0.1.md:L212–L341`; Git blob `3ab659e8f53239e0f4aaf8eedfc3139020502224`; complete source-byte SHA-256 `0f03bcb3a51a8a21e78f9a92c7f7ef1818471d83e38d4715c3a451bce839ec79` (123544 bytes). Candidate matrix: `docs/mvp/v1.0/wu05-rsf02s1-five-schema-adoption-matrix-v0.1.json`, blob `f146386f07af077dfa8cf03cc40dc3c37ad36527`, raw SHA-256 `08ae7b586c400d2730c256a0dee5bb7ee0f5736b5b244a2f0a358040dd7c828e`. All are read at `aea25f1a3462666b27c213a508c8dc846eab04ab`.

Exact candidate label `v0.1-CANDIDATE-NON_OPERATIVE`; Draft `body_schema_label=rs-spec-numeric-policy-body-proposal-v0.1` and `body_version=0.1-DRAFT-NON_ISSUED`. Proposed operational `resource_schema=NOT_REGISTERED`, `resource_version=NOT_REGISTERED`; semantic edition/version `NOT_SUPPLIED`. Original candidate operational wording is preserved in the JSON and was not rewritten in history.

**CURRENT_IMPLEMENTATION:** Draft pins int64/NTD_thousands, Native policy label, tagged UInt64 scale6, FRACTION, scaled bounds0..1000000 and HALF_EVEN. revenue accepts signed Int64. FixedRatio validates scaled/text correspondence. The internal ratio constructor restricts operands to exact integers 0<=numerator<=denominator<2^63 and denominator>0; the A04 lineage path preserves negative months or zero denominator as NOT_COMPUTABLE. Draft parsing neither resolves policy_source_ref nor proves Native equivalence.

**PROJECT_OWNER_DIRECTION:** Retain original signed Int64 revenue in NTD_thousands and Native six-decimal FixedRatio6 fractional units/scaled bounds/half-even rounding; text/display is not replacement evidence; no float or unreviewed coercion. Source: `docs/mvp/v1.0/wu05-rsf02d-owner-decision-matrix-v0.1.json:L208–L225`.

**Selected decision candidate:** Retain signed Int64 source revenue [-2^63,2^63-1] in NTD_thousands independently of the restricted ratio operand domain. FixedRatio6 uses scaled units [0,1000000], tagged scale6, FRACTION, exact six-place decimal text and HALF_EVEN. Preserve NEGATIVE_INPUT_OUTSIDE_SHARE_DOMAIN / ZERO_QUARTER_REVENUE_DENOMINATOR and original unknown/first failure; no coercion or zero fill.

**Explicit version-strategy candidate:** `PROPOSE_RETAIN_BOUNDED_NUMERIC_POLICY_PENDING_NATIVE_AUTHORITY`. Actual Project Owner acceptance of this new strategy is `NOT_SUPPLIED`; recording the proposal does not sign for the Owner. No changed numeric domain/rounding/unit/scale/parser is approved. Any such change, new coercion or changed refusal requires a separately reviewed operational version/registered mapping or amendment plus independent vectors; generic CAN Decimal is separate. Native source authority/equivalence remains missing despite matching labels.

Source crosswalk: `src/pit_research_lab/mvp/f2/resource_bodies.py:L371–L382`; `src/pit_research_lab/mvp/f2/resource_contracts.py:L322–L342`; `src/pit_research_lab/domain/ratio.py:L72–L94`; `src/pit_research_lab/domain/ratio.py:L138–L154`; `src/pit_research_lab/domain/ratio.py:L344–L371`; `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L457`.

**Required semantic Owner roles:** Technical Lead/F2 with attributable Native numeric-policy owner and F4 original input custodian. Actual individual, appointment, exact-version approval, approval file ID/bytes/hash/provenance: `NOT_SUPPLIED`.

**Independent reviewer conditions:** Independent Native numeric equivalence/source-policy reviewer, distinct from issuer/author. Identity, appointment, independence evidence and exact-version verdict: `NOT_SUPPLIED`. The author cannot fill this role or self-certify review. Reviewer must reconcile the cited fields/helpers, old/new acceptance/refusals, source authority and exact immutable version before a genuine S1 verdict.

**Decisive blockers / required proof:**

- Attributable Native numeric-policy Owner appointment and exact-version semantic decision
- Exact policy_source_ref original bytes, version, source authority and use rights
- Independent Native source-to-policy equivalence review with exact operand domains and uncomputable behavior
- Independent numeric reviewer appointment and candidate/version verdict, including tie and boundary expectations

Independent mathematical derivation from rational arithmetic, without invoking the Production/Native helper: `1000000 = 128*7812 + 64`, so 1/128 gives scaled7812.5, tie to even7812 (`0.007812`). `3000000 = 128*23437 + 64`, so 3/128 gives scaled23437.5, odd quotient rounds up to even23438 (`0.023438`). These are author-computed mathematical expectations, not independent specialist approval, Native execution or Golden outputs.

Signed revenue accepts negative Int64 values as original data; it does not make them valid ratio operands. The exact helper precondition is `type(numerator) is int`, `type(denominator) is int`, `0<=numerator<=denominator<2**63`, `denominator>0`; bool/float/coercion are excluded. The lineage path verifies three signed monthly inputs, exact sum and actual denominator before negative-month/zero-denominator outcomes. Policy source bytes, authority, rights and source-to-policy equivalence remain absent.

**Inspected current test definitions — all NOT_RUN:**

- `test_numeric_policy_cannot_widen_scale_or_claim_general_decimal` — `tests/unit/mvp_f2/test_resource_bodies.py:L655–L661`.
- `test_exact_int64_signed_unit_and_encoding` — `tests/unit/mvp_f2/test_resource_bodies.py:L848–L854`.
- `test_fixed_ratio_original_values_half_even_and_bounds` — `tests/unit/mvp_f2/test_resource_bodies.py:L856–L868`.
- `test_ratio_float_exponent_scale_percent_and_mismatch` — `tests/unit/mvp_f2/test_resource_bodies.py:L881–L893`.

**Later versioned-amendment review requirements — NOT_RUN; no executable tests added:**

- Independent signed Int64 lower/upper endpoints versus ratio operand-domain controls; negative months, zero denominator and exact lineage preservation.
- Independent HALF_EVEN ties 1/128=>7812 and3/128=>23438, scaled bounds/text correspondence, unit/scale/ref/source mutations.

**Separate S2–S5 restrictions:** S2 exact original Body/version/typed-parent/rights proof; S3 independent full-domain Golden and freeze; S4 actual issuer/current grant/revocation/receipt and genuine Native two-channel replay; S5 reader/IF04/IF05/F3/F5/F6 acceptance all remain false, unproved and unauthorized. No stage advances from this card.

**Next Action / Owner:** F2 obtains attributable Native numeric-policy authority and F4 input custody; an independent numeric/source-policy reviewer verifies original policy edition, operand restrictions and exact equivalence constraints.

## RSF02-A11 — OBSERVATION_RELEASE_POLICY

**Proposed Owner outcome: `REVISION_REQUIRED`.** Evidence: `S1_CANDIDATE / MISSING_OWNER_PROOF / BLOCKED`; this is a source-backed author decision candidate, not an attributable Owner signature.

Candidate source: `docs/mvp/v1.0/wu05-rsf02s1-five-schema-semantics-candidate-v0.1.md:L342–L464`; Git blob `3ab659e8f53239e0f4aaf8eedfc3139020502224`; complete source-byte SHA-256 `0f03bcb3a51a8a21e78f9a92c7f7ef1818471d83e38d4715c3a451bce839ec79` (123544 bytes). Candidate matrix: `docs/mvp/v1.0/wu05-rsf02s1-five-schema-adoption-matrix-v0.1.json`, blob `f146386f07af077dfa8cf03cc40dc3c37ad36527`, raw SHA-256 `08ae7b586c400d2730c256a0dee5bb7ee0f5736b5b244a2f0a358040dd7c828e`. All are read at `aea25f1a3462666b27c213a508c8dc846eab04ab`.

Exact candidate label `v0.1-CANDIDATE-NON_OPERATIVE`; Draft `body_schema_label=rs-spec-observation-release-policy-body-proposal-v0.1` and `body_version=0.1-DRAFT-NON_ISSUED`. Proposed operational `resource_schema=NOT_REGISTERED`, `resource_version=NOT_REGISTERED`; semantic edition/version `NOT_SUPPLIED`. Original candidate operational wording is preserved in the JSON and was not rewritten in history.

**CURRENT_IMPLEMENTATION:** Draft principal_classes uses items(): ordered1..4096 selected entries from F2_ISSUER,F2_REVIEWER,F3_RESEARCH,F5_POLICY,F6_DISPLAY; duplicates are accepted. required_checks is the exact five literal true booleans. authorization_check always DENIED; detached_release returns local WITHHELD without rewriting Native facts. No live IF04 grant, IF05 predicate or verified F01 status view exists.

**PROJECT_OWNER_DIRECTION:** Retain policy axes exact_target, context_match, current_grant, IF05_predicate and audit_separation; deny by default; policy-version changes must invalidate dependent observation eligibility; repeated principal class semantics require explicit duplicate rejection without unreviewed array normalization. Source: `docs/mvp/v1.0/wu05-rsf02d-owner-decision-matrix-v0.1.json:L246–L263`.

**Selected decision candidate:** Propose the new-operational-version option: reject repeated principal class entries while preserving order and allowing an approved subset, not requiring all five classes. Keep exact_target AND context_match AND current_grant AND IF05_predicate AND audit_separation simultaneously true; exact projection/version and FAIL_CLOSED_RETAIN_NATIVE_STATE remain mandatory. No reader release while independent IF04/IF05/F01 proof is absent.

**Explicit version-strategy candidate:** `PROPOSE_OPTION_II_NEW_REGISTERED_OPERATIONAL_VERSION_WITH_DUPLICATE_REJECTION`. Actual Project Owner acceptance of this new strategy is `NOT_SUPPLIED`; recording the proposal does not sign for the Owner. Behavior-changing adoption requires revision. Retain current 0.1-DRAFT-NON_ISSUED byte-for-byte; prepare a separate operational schema/version only after explicit project version-strategy acceptance, specialist semantic Owner approval and independent compatibility/negative/mutation review. Version identifier NOT_REGISTERED. Do not mutate the Draft or sort/deduplicate inputs. Adding a stronger-status field would require its own body/AppAxes/contract amendment.

Source crosswalk: `src/pit_research_lab/mvp/f2/resource_bodies.py:L384–L399`; `src/pit_research_lab/mvp/f2/resource_contracts.py:L113–L125`; `src/pit_research_lab/mvp/f2/resource_access.py:L30–L75`; `src/pit_research_lab/mvp/f2/resource_access.py:L97–L118`; `src/pit_research_lab/mvp/f2/resource_bodies.py:L227–L238`; `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L378–L390`; `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L758`.

**Required semantic Owner roles:** Technical Lead/F2 release semantic Owner; separate IF04 capability and IF05 predicate owners; F3/F5/F6 consumer consultation. Actual individual, appointment, exact-version approval, approval file ID/bytes/hash/provenance: `NOT_SUPPLIED`.

**Independent reviewer conditions:** Independent disclosure/security and IF05 reviewer; independently verified F01 status-view review still required. Identity, appointment, independence evidence and exact-version verdict: `NOT_SUPPLIED`. The author cannot fill this role or self-certify review. Reviewer must reconcile the cited fields/helpers, old/new acceptance/refusals, source authority and exact immutable version before a genuine S1 verdict.

**Decisive blockers / required proof:**

- Explicit attributable Project Owner acceptance of proposed option II version strategy (not supplied by author selection)
- F2 release semantic Owner exact-version adoption and independent disclosure/security reviewer appointment/verdict
- Reviewed duplicate acceptance/refusal compatibility amendment and independent old/new version vectors
- Separate IF04/IF05 semantic constraints and independently verified F01 stronger-WITHHELD no-release status-view design; runtime grants/predicates remain separate S4/S5 gates
- Separately adopted A10 projection whitelist semantics and all-reader nonleakage/Native-preservation requirements

The explicit project-level proposal selects option (ii), a separately registered new operational version after review, rather than asserting duplicate rejection in the current Draft. Option (i), keeping duplicate acceptance operationally, is not selected by this packet; the unchanged Draft remains historical and non-issued. This proposed strategy still needs attributable Project Owner acceptance. A semantic five-check contract is separate from actual current grant/IF05 evaluation. F01 stronger WITHHELD must survive consistently in a separately verified immutable no-release view; local ReleaseWithheld is neither that view nor a supplied CAN Withheld policy. If the separate view cannot meet the requirement, a separately authorized AppAxes/body/contract amendment is necessary.

**Inspected current test definitions — all NOT_RUN:**

- `test_immutable_release_policy_cannot_switch_off_current_grant_or_if05` — `tests/unit/mvp_f2/test_resource_bodies.py:L663–L670`.
- `test_current_grants_absent_revoked_wrong_context_and_fake_receipt_deny` — `tests/unit/mvp_f2/test_resource_bodies.py:L1168–L1204`.
- `test_withheld_release_never_rewrites_native_invocation_or_first_failure` — `tests/unit/mvp_f2/test_resource_bodies.py:L1206–L1217`.
- `test_safe_whitelist_unknown_withheld_and_no_recursive_private_details` — `tests/unit/mvp_f2/test_resource_bodies.py:L1219–L1260`.

**Later versioned-amendment review requirements — NOT_RUN; no executable tests added:**

- Old Draft duplicate accepted versus new version duplicate rejected; selected subsets and order remain unchanged, no automatic normalization.
- Each of five checks false/missing/1, target/context/exposure mismatch, revoked/expired grant, fake receipt, audit co-capability and IF05 positive/explicit-negative controls.
- Every reader preserves stronger WITHHELD while Native state/invocation/first failure stays exact; independently verify separate no-release view before use.

**Separate S2–S5 restrictions:** S2 exact original Body/version/typed-parent/rights proof; S3 independent full-domain Golden and freeze; S4 actual issuer/current grant/revocation/receipt and genuine Native two-channel replay; S5 reader/IF04/IF05/F3/F5/F6 acceptance all remain false, unproved and unauthorized. No stage advances from this card.

**Next Action / Owner:** Project Owner adjudicates the proposed option II strategy; F2 release Owner authors a separately versioned amendment; independent security/IF05 reviewer checks duplicate refusal, exact five-check conjunction and F01 status-view constraints. IF04/IF05 owners supply their own proof later under separate authorization.

## RSF02-A12 — AUDIT_ACCESS_POLICY

**Proposed Owner outcome: `REVISION_REQUIRED`.** Evidence: `S1_CANDIDATE / MISSING_OWNER_PROOF / BLOCKED`; this is a source-backed author decision candidate, not an attributable Owner signature.

Candidate source: `docs/mvp/v1.0/wu05-rsf02s1-five-schema-semantics-candidate-v0.1.md:L465–L577`; Git blob `3ab659e8f53239e0f4aaf8eedfc3139020502224`; complete source-byte SHA-256 `0f03bcb3a51a8a21e78f9a92c7f7ef1818471d83e38d4715c3a451bce839ec79` (123544 bytes). Candidate matrix: `docs/mvp/v1.0/wu05-rsf02s1-five-schema-adoption-matrix-v0.1.json`, blob `f146386f07af077dfa8cf03cc40dc3c37ad36527`, raw SHA-256 `08ae7b586c400d2730c256a0dee5bb7ee0f5736b5b244a2f0a358040dd7c828e`. All are read at `aea25f1a3462666b27c213a508c8dc846eab04ab`.

Exact candidate label `v0.1-CANDIDATE-NON_OPERATIVE`; Draft `body_schema_label=rs-spec-audit-access-policy-body-proposal-v0.1` and `body_version=0.1-DRAFT-NON_ISSUED`. Proposed operational `resource_schema=NOT_REGISTERED`, `resource_version=NOT_REGISTERED`; semantic edition/version `NOT_SUPPLIED`. Original candidate operational wording is preserved in the JSON and was not rewritten in history.

**CURRENT_IMPLEMENTATION:** Draft accepts ordered1..4096 principal classes F2_ISSUER/INDEPENDENT_F2_REVIEWER and operations INSPECT_SOURCE/INSPECT_NATIVE/VERIFY_PROVENANCE; duplicates in principals, operations and exact target tuples are permitted. target schema/version each use Text1..65536 UTF-8 bytes while ResourceRef uses1..128. cutoff_rule is nonempty uninterpreted Text. Receipt/revocation literals do not appoint reviewers or supply receipts/current rights.

**PROJECT_OWNER_DIRECTION:** Separate F2 issuer/reviewer audit principals and exact target, operation, cutoff/context and immutable receipt; revocation must deny current access while retaining historical fact; no SAFE/audit co-grant or privilege escalation. Source: `docs/mvp/v1.0/wu05-rsf02d-owner-decision-matrix-v0.1.json:L265–L282`.

**Selected decision candidate:** Propose reject exact duplicate principals, operations and (resource_kind,schema,version) tuples, retaining array order. Propose target schema/version1..128 UTF-8 bytes for exact ResourceRef compatibility under a new operational version. Propose cutoff_rule semantics as exact equality to the original authorized decision cutoff, original context and issuer/feature cohort per operation, no wildcard/current/latest/default or cutoff substitution. Concrete approved cutoff_rule encoding/mapping is NOT_SUPPLIED, so adoption remains REVISION_REQUIRED.

**Explicit version-strategy candidate:** `PROPOSE_NEW_VERSION_DUPLICATE_REFUSAL_TEXT128_AND_EXACT_CUTOFF_MAPPING`. Actual Project Owner acceptance of this new strategy is `NOT_SUPPLIED`; recording the proposal does not sign for the Owner. All three narrowings need an explicit reviewed version/amendment and independent vectors. No new operational identifier or cutoff_rule literal is invented; both remain NOT_REGISTERED/NOT_SUPPLIED. The historical Draft continues to parse repeated entries,129..65536-byte target labels and uninterpreted nonempty cutoff text. No implicit repair, truncation, wildcard mapping or new grant fields.

Source crosswalk: `src/pit_research_lab/mvp/f2/resource_bodies.py:L400–L407`; `src/pit_research_lab/mvp/f2/resource_contracts.py:L96–L125`; `src/pit_research_lab/mvp/f2/resource_contracts.py:L181–L194`; `src/pit_research_lab/mvp/f2/resource_access.py:L30–L75`; `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L378–L390`.

**Required semantic Owner roles:** Technical Lead/F2 audit semantic issuer; Academic Owner appoints independent reviewer; IF04/IF07 rights custodians separately accountable. Actual individual, appointment, exact-version approval, approval file ID/bytes/hash/provenance: `NOT_SUPPLIED`.

**Independent reviewer conditions:** Independent F2 security/provenance reviewer, distinct from F2 issuer and candidate author; actual appointment NOT_SUPPLIED. Identity, appointment, independence evidence and exact-version verdict: `NOT_SUPPLIED`. The author cannot fill this role or self-certify review. Reviewer must reconcile the cited fields/helpers, old/new acceptance/refusals, source authority and exact immutable version before a genuine S1 verdict.

**Decisive blockers / required proof:**

- Attributable F2 audit semantic Owner version/cutoff/duplicate/length decision
- Academic Owner appointment of an independent reviewer, identity and independence from issuer/author
- Independent security/provenance exact-version review and old/new compatibility/negative/mutation vectors
- Exact approved cutoff_rule encoding and mapping to operation target/content/context/cohort
- Separately evidenced IF04/IF07 authority and source-rights requirements; actual current grants/expiry/revocation/immutable receipts remain S4 proof, not a semantic signature

Exact principals are `F2_ISSUER` and `INDEPENDENT_F2_REVIEWER`; release-policy `F2_REVIEWER` is not automatically that appointed audit reviewer. Allowed operations are exactly `INSPECT_SOURCE`, `INSPECT_NATIVE`, `VERIFY_PROVENANCE`. Each authorized operation later binds typed content/target/schema/version/action/cutoff/context/cohort, original source rights and current grant. `SC:L390_EXACT_OPERATION_RECEIPT` is a rule label, not an issued receipt. The immutable receipt must preserve principal/grant/policy, typed target/action/context, checked source/code/version/length/digest, allow/deny reason, original operation/attempt provenance and receipt version.

Current grant validity is `[valid_from,valid_until)`. Expiry/revocation denies the current operation while retaining historical content/receipts/Native facts. The proposed cutoff equality rule has no approved encoding/implementation or issuer appointment; no wildcard/default alias or live grant follows. The 128-byte proposal is a UTF-8 byte bound, not character truncation. Until duplicate/length/cutoff/version decisions receive real approval and review, behavior-changing adoption remains REVISION_REQUIRED.

**Inspected current test definitions — all NOT_RUN:**

- `test_every_implemented_body_descriptor_closed_and_non_issued` — `tests/unit/mvp_f2/test_resource_bodies.py:L609–L621`.
- `test_current_grants_absent_revoked_wrong_context_and_fake_receipt_deny` — `tests/unit/mvp_f2/test_resource_bodies.py:L1168–L1204`.
- `test_frozen_golden_and_original_wu04_static_regression` — `tests/unit/mvp_f2/test_resource_bodies.py:L1262–L1292`.

**Later versioned-amendment review requirements — NOT_RUN; no executable tests added:**

- Old/new duplicate principal/operation/target-tuple acceptance, array-order mutation, UTF-8 byte lengths0/1/128/129/65536/65537, and matching ResourceRef bounds.
- Exact cutoff/context/cohort positive and mismatch/alias/wildcard/absent mapping refusals; reviewer independence; valid_from inclusive/valid_until exclusive; historical retention after revocation.
- Receipt byte/target/policy/action/context mutation and constant ACCESS_DENIED independent of private existence or Native failure.

**Separate S2–S5 restrictions:** S2 exact original Body/version/typed-parent/rights proof; S3 independent full-domain Golden and freeze; S4 actual issuer/current grant/revocation/receipt and genuine Native two-channel replay; S5 reader/IF04/IF05/F3/F5/F6 acceptance all remain false, unproved and unauthorized. No stage advances from this card.

**Next Action / Owner:** F2 audit Owner proposes exact version and cutoff mapping; Academic Owner supplies independent reviewer appointment. That reviewer adjudicates duplicate/UTF-8 width compatibility and constant-denial separation. IF04/IF07 custodians separately verify actual rights and receipts before any later operation.

## RSF02-A13 — SCHEDULE_INVARIANT_POLICY

**Proposed Owner outcome: `DEFERRED_EXTERNAL_DEPENDENCY`.** Evidence: `S1_CANDIDATE / MISSING_OWNER_PROOF / BLOCKED`; this is a source-backed author decision candidate, not an attributable Owner signature.

Candidate source: `docs/mvp/v1.0/wu05-rsf02s1-five-schema-semantics-candidate-v0.1.md:L578–L700`; Git blob `3ab659e8f53239e0f4aaf8eedfc3139020502224`; complete source-byte SHA-256 `0f03bcb3a51a8a21e78f9a92c7f7ef1818471d83e38d4715c3a451bce839ec79` (123544 bytes). Candidate matrix: `docs/mvp/v1.0/wu05-rsf02s1-five-schema-adoption-matrix-v0.1.json`, blob `f146386f07af077dfa8cf03cc40dc3c37ad36527`, raw SHA-256 `08ae7b586c400d2730c256a0dee5bb7ee0f5736b5b244a2f0a358040dd7c828e`. All are read at `aea25f1a3462666b27c213a508c8dc846eab04ab`.

Exact candidate label `v0.1-CANDIDATE-NON_OPERATIVE`; Draft `body_schema_label=rs-spec-schedule-invariant-policy-body-proposal-v0.1` and `body_version=0.1-DRAFT-NON_ISSUED`. Proposed operational `resource_schema=NOT_REGISTERED`, `resource_version=NOT_REGISTERED`; semantic edition/version `NOT_SUPPLIED`. Original candidate operational wording is preserved in the JSON and was not rewritten in history.

**CURRENT_IMPLEMENTATION:** Draft enforces PROTOCOL reference shape, FIXED_FOUR_WEEKLY_SYN_A and exact preserve/order/unknown/no-session/accounting booleans. validate_four_ticks constrains four distinct tick/context positions and cutoffs; schedule_path_check compares PF038/AF009/schedule-to-sequence claims but returns NOT_SUPPLIED. The generic DECISION_SCHEDULE body allows1..4096 rows and is not generic schedule acceptance.

**PROJECT_OWNER_DIRECTION:** Select FIXED_FOUR_WEEKLY_SYN_A only: preserve order/unknowns, W03 annotation-only, accounting_implies_admission=false; require separately adopted PROTOCOL and immutable AF009/PF038 source-input equality; no generic schedule approval. Source: `docs/mvp/v1.0/wu05-rsf02d-owner-decision-matrix-v0.1.json:L284–L301`.

**Selected decision candidate:** Keep unconditional S1 adoption deferred until B01 PROTOCOL has exact attributable F3 Owner semantics/version/parent mapping and independent F3 review. Conditional review candidate only: four original SYN-A Weekly cutoffs, preserve order/unknown/first failure/invocation, W03 2027-W03 annotation-only, accounting_implies_admission=false; immutable ScheduleInput -> DECISION_SCHEDULE.source_input_ref/PF038 -> TEMPORAL-SEQUENCE.schedule_ref with invariant_policy_ref equal AF009, verified source/calendar/session closure.

**Explicit version-strategy candidate:** `DEFER_OPERATIONAL_VERSION_UNTIL_B01_ADOPTION_AND_F2_F3_REVIEW`. Actual Project Owner acceptance of this new strategy is `NOT_SUPPLIED`; recording the proposal does not sign for the Owner. No conditional candidate counts as operational or ratified. Any changed protocol instance/semantics/parents, schedule profile/order/cardinality/refusal or identifier semantics requires explicit versioned review and fresh dependent identity verification. Source equality is unproved by matching placeholder cores; no digest equivalence across versions. No Daily/Monthly or generic schedule extension.

Source crosswalk: `src/pit_research_lab/mvp/f2/resource_bodies.py:L408–L415`; `src/pit_research_lab/mvp/f2/resource_bodies.py:L437–L449`; `src/pit_research_lab/mvp/f2/resource_binding.py:L146–L219`; `src/pit_research_lab/mvp/f2/resource_binding.py:L222–L239`; `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L312–L313`; `docs/mvp/v1.0/shared-interface-contract-v0.1.md:L353–L365`; `docs/mvp/v1.0/f3-f5-research-methods-decision-spec-v0.1.md:L12–L16`.

**Required semantic Owner roles:** F2 calendar/source/evidence Owner and Member B/F3 schedule/PROTOCOL Owner; neither substitutes for the other. Actual individual, appointment, exact-version approval, approval file ID/bytes/hash/provenance: `NOT_SUPPLIED`.

**Independent reviewer conditions:** Independent F2 temporal/provenance reviewer and independent F3 protocol reviewer; actual identities NOT_SUPPLIED. Identity, appointment, independence evidence and exact-version verdict: `NOT_SUPPLIED`. The author cannot fill this role or self-certify review. Reviewer must reconcile the cited fields/helpers, old/new acceptance/refusals, source authority and exact immutable version before a genuine S1 verdict.

**Decisive blockers / required proof:**

- Separately attributable F3 B01 PROTOCOL adoption with exact schema/version/scoped instances/parent mapping
- Independent F3 protocol reviewer appointment/verdict distinct from author; F2 temporal/source Owner adoption and independent F2 review
- Independent semantic source/calendar/session/PF038/AF009 invariant review; actual immutable Body/parent resolution remains S2
- Separate A07 calendar, A15 schedule and deferred A14/A17 gates; B02-B04 broader configuration/research dependencies remain unadopted

B01 directly blocks unconditional A13 adoption. F3 must approve scoped PROTOCOL instances (schedule anchor/holiday roll, F2 operation scope, F3 experiment protocol) with exact semantics/version/parents; one role name does not adopt all instances. F2 source/calendar review cannot substitute for F3 protocol Owner and independent F3 review. Conditional candidate review does not count toward S1 or authorize a schedule. Four fixed cutoffs are the t1..t4 listed in A06; W03 is an annotation and B03 midnight is not a Weekly18:00 substitute.

**Inspected current test definitions — all NOT_RUN:**

- `test_policy_body_does_not_authenticate_scheduleinput_or_issue_sequence` — `tests/unit/mvp_f2/test_resource_bodies.py:L672–L685`.
- `test_four_ticks_w03_annotation_and_equal_values_distinct_context` — `tests/unit/mvp_f2/test_resource_bodies.py:L835–L846`.
- `test_scheduleinput_af009_stale_policy_schedule_and_input` — `tests/unit/mvp_f2/test_resource_bodies.py:L1045–L1063`.
- `test_policy_mutation_propagates_dependency_expression_not_digest` — `tests/unit/mvp_f2/test_resource_bodies.py:L1065–L1073`.
- `test_policy_change_requires_new_pf038_dependency_and_sequence_schedule_target` — `tests/unit/mvp_f2/test_resource_bodies.py:L1076–L1102`.

**Later versioned-amendment review requirements — NOT_RUN; no executable tests added:**

- B01 absent/wrong-instance/version/parent refusal; four tick membership/order/context and W03 fifth-tick controls; equal t2/t3 never merged.
- PF038 input, AF009 policy, schedule/sequence target and source/calendar/session mutation; unknown/withheld/first-failure/invocation preservation and no accounting-to-admission.

**Separate S2–S5 restrictions:** S2 exact original Body/version/typed-parent/rights proof; S3 independent full-domain Golden and freeze; S4 actual issuer/current grant/revocation/receipt and genuine Native two-channel replay; S5 reader/IF04/IF05/F3/F5/F6 acceptance all remain false, unproved and unauthorized. No stage advances from this card.

**Next Action / Owner:** Member B/F3 protocol Owner and independent F3 reviewer supply B01 exact adopted semantics; F2 temporal/source Owner and independent temporal reviewer then reconcile fixed-four PF038/AF009 constraints. Continue conditional documentary review only until these proofs exist.

## Cross-owner and open boundaries

| External decision | Roles and missing authority | Blocking effect |
|---|---|---|
| RSF02-B01 PROTOCOL | Member B/F3 protocol owner with F2 calendar/Native consultation; independent F3 reviewer. Actual individuals/approval/review NOT_SUPPLIED. | Direct A13 prerequisite; no unconditional S1. |
| RSF02-B02 HORIZON_MATURITY | Member B/F3 research-method owner, consulted F5; independent methods reviewer. Actual individuals/approval/review NOT_SUPPLIED. | Separate broader configuration/research/evaluation prerequisite; no adoption here. |
| RSF02-B03 EXECUTION_RULES | F5 execution-policy owner with F3/F2 interface consultation; independent F5 reviewer. Actual individuals/approval/review NOT_SUPPLIED. | Separate broader configuration/research/evaluation prerequisite; no adoption here. |
| RSF02-B04 EVALUATION_PROTOCOL | Joint F3 methodology and F5 evaluation owners; separately attributable reviews. Actual individuals/approval/review NOT_SUPPLIED. | Separate broader configuration/research/evaluation prerequisite; no adoption here. |

B01–B04 remain non-adopted external role-specific contracts: schema not registered, Body not issued. Source: `docs/mvp/v1.0/wu05-rsf02d-owner-decision-record-v0.1.md:L170–L200`; `docs/mvp/v1.0/f3-f5-research-methods-decision-spec-v0.1.md:L12–L16` and `docs/mvp/v1.0/f3-f5-research-methods-decision-spec-v0.1.md:L82–L120`. B02 preserves horizon/maturity/split proof; B03 preserves execution price/cost/cutoff rules; B04 needs separately attributable F3 methodology and F5 evaluation review, without rewriting sealed decisions.

| Boundary | Preserved finding |
|---|---|
| F01 | PER_CUTOFF_BINDING.app_axes.pit_status is currently only UNRESOLVED. Stronger WITHHELD must survive in a separately authorized immutable no-release status view visible to every consumer, with independent consistency/nonleakage proof. detached_release returns a local refusal, not proof that this separate view exists or a CAN Withheld with a supplied policy. SEMANTIC_TRACE remains deferred; if separate view is insufficient, a versioned AppAxes/body/contract amendment is required. |
| F02 | Draft text() requires >0 bytes; general CAN Text/TextSchema min_bytes=0 is unchanged. Each empty-string case below has its own retain-rejection/versioned-review verdict. No global Text tightening or silent empty-to-Unknown substitution. |
| F04 | validate_four_ticks plus schedule_path_check plus original source/calendar/session and AF009/PF038 checks are all required for fixed-four. Generic Draft parser success on 1..4096 rows is never generic accepted schedule. Equal declarations alone do not verify immutable bytes. |
| G04 | Actual Native Attempt format/witness/correspondence and no-outcome remain unproved. Missing state cannot become a successful NativeSummary; no invented NATIVE_RECEIPT, first failure or successful invocation. Any tagged no-outcome representation requires separately reviewed CAN07 amendment and vectors. |
| G09 | Owner selected root container=1, nested dict/list +1, scalar +0, maximum64; independent exact64/65 vectors and formal contract clarification/amendment remain missing. P2-DEPTH-64/65 stay excluded; _CONTAINER_CEILING unchanged. |
| G10 | SOURCE_BYTES_CODEC_NOT_SUPPLIED is stale only for accepted bounded SOURCE-BYTES codec/eight complete positives. Resource Body/semantic owner/rights/original Native/full-domain replay blockers remain. No code or historical wording changed. |

Boundary evidence: `src/pit_research_lab/mvp/f2/resource_bodies.py:L104–L115`; `src/pit_research_lab/mvp/f2/resource_bodies.py:L227–L238`; `src/pit_research_lab/mvp/f2/resource_access.py:L97–L118`; `src/pit_research_lab/mvp/f2/resource_contracts.py:L96–L103`; `src/pit_research_lab/mvp/f2/resource_binding.py:L146–L219`; `src/pit_research_lab/mvp/f2/resource_binding.py:L340–L392`; `src/pit_research_lab/mvp/if03/canonical_codec.py:L17–L23` and L61–68; `docs/mvp/v1.0/wu05-rsf02d-owner-decision-matrix-v0.1.json:L528–L542`; `src/pit_research_lab/mvp/f2/resource_binding.py:L119–L128`. Depth root1/max64 is selected but not ratified; exact64/65 vectors and amendment remain missing. Native no-outcome remains unproved/refused; project discussion cannot close either.

The 17 Draft roles are A01..A17, with five bounded directions, nine invariant-required and three deferred project directions; zero semantic adoptions. The remaining12 remain dependency-only. The 21 required roles comprise these17 plus B01..B04; the closed40-role IF03 vocabulary is navigation metadata, not schema approval. Exact role inventories are in the JSON, sourced to `src/pit_research_lab/mvp/f2/resource_contracts.py:L19–L38` and `src/pit_research_lab/mvp/f2/resource_bodies.py:L286–L463`. A07/A10/A15 remain invariant-required; A14/A16/A17 remain deferred. Conditional A13 review cannot close the other roles.

ORACLE-02 historical scope remains94 included (8 complete SOURCE-BYTES positives,80 narrow refusals,6 relations),16 excluded. CAN03 scope remains61 scoped matches+6 test-only diagnostics,27 outside scoped production coverage; no all-domain Golden acceptance or new replay. Existing frozen identities, bytes and historical statuses remain immutable.

## Test carryover and handoff

All15 original positive/negative/mutation groups and55 unique case objects are preserved verbatim in the companion JSON and external `RATIFY01_TEST_CARRYOVER.json`. Each role has3 positive+5 negative+3 mutation cases; all55 remain `NOT_RUN` with original expected states, source preconditions, future Owner and independent-proof roles. The original source/Owner preconditions remain missing. Existing test definitions were statically inspected, never executed. Additional amendment requirements are separately identified and do not inflate or replace the55. No executable tests, Resource bytes or Golden outputs are authored.

Independent reviewer must verify exact baseline/blobs/source hashes, both new candidate hashes, original55 equality and all flags; reconcile old/new duplicate/UTF-8 width/cutoff/refusal semantics; inspect role-specific authority and actual appointments/version-bound approvals when supplied; and return an attributable verdict distinct from the author. Current identities, signatures, appointments, reviewed edition rights and role approvals are NOT_SUPPLIED. Full exact steps and no-go boundaries are in external `RATIFY01_INDEPENDENT_REVIEW_HANDOFF.md`.

Author static JSON/cardinality/source/format/archive checks are file-integrity evidence only. Full regressions/Native/IF04/F3/F5/CI are NOT_RUN under this scope. A later baseline/status guard may reject the two intended untracked files; do not change guards. No branch switch, staging, commit, push, PR, merge, source issuance or operational permission is authorized.
