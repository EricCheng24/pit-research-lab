# WU05 ORACLE-01 authoring candidates v0.1

Disposition: `WU05_ORACLE01_AUTHORED_READY_FOR_INDEPENDENT_REVIEW`.
This is synthetic, test-only authoring. ORACLE-02 review/freeze and WU05-CAN
production Codec conformance are separate work. No new complete positive is
authored: B01–B08 remain the eight accepted SOURCE-BYTES positives in the adjacent
immutable `oracle01_v0_1` directory. Their bytes and archive are referenced directly.

Run from the repository root:

```sh
uv run --locked pytest -q tests/unit/mvp_f2/test_wu05_oracle01.py
```

The author's reference helper uses explicit SOURCE-BYTES field concatenation and
three unsigned big-endian length prefixes. It imports no production code. The
canonical fragment predicate and symbolic graph checks establish necessary
structural conditions only. They do not implement a general domain Codec,
semantic Resource validator, reference issuer, resolver or authorization service.
**The ORACLE-02 reviewer must independently reconstruct expectations without
reusing this helper as a second implementation.** Never copy/import it into
production. Fixed expected positive bytes/digests come from the existing frozen
artifacts, not a runtime expectation generator.

The small metadata schema is ordinary repository JSON, not CanonicalPayload:

| File | Schema |
| --- | --- |
| `cases.json` | `{format, baseline, cases[]}`; each case has unique `case_id`, nonempty registered `domains[]`, `status`, `execution`, `operation`, `input`, literal `expected`, `source_clause[]`, and `note`. |
| `domain_coverage.json` | `{format, baseline, parent_order_rule, resource_role_rule, helper_contracts, helper_clause_specs, domains[]}`; exactly one entry for each of the ten AD01-09 domains, in table order. Each entry contains exact schema/tag/profile, semantic key list and verbatim field specification, resource roles, typed parent traversal, case-ID lists, evidence preconditions, status, source clauses and next owner. `helper_clause_specs` preserves the exact numeric/time/reference/fact clauses for nested types outside the helper table. |
| `source_pins.json` | `{format, baseline, files[], optional_packets}`; each file has repository `path`, actual baseline `git_blob_sha1`, raw file `sha256`, and `byte_length`. No self-hash or signature. |
| `schedule_declaration.json` | A deliberately hypothetical D06 comparison fixture: exact original-input/core expectations, PF038, full invariant policy ResourceRef/AF009, and sequence/schedule reference expectations. No resource body is issued or authenticated by these wrappers. |

Each `source_clause` is `{path, clause}` and resolves through `source_pins.json`.
CAN references abbreviate AD01-07.CAN clauses; RT01 is the later ratification
overlay. D04-A/D05/D06-A refer to the directly authorized task prompt; their design
acceptance supplies no missing issued bytes, original attempt or witness. Fixed
contracts/accepted Golden take precedence, then authorized D01–D06 scope, fixed
source facts, supporting proposals, and author inference. The four optional
review ZIPs are absent from this checkout; no contents or receipts are invented.

Case status is exactly one of:

- `VALID_COMPLETE_DOMAIN_POSITIVE`: existing fixed B01–B08, reconstructed and
  compared against stored payload/frame/digest/envelope expectations.
- `EXECUTABLE_REFUSAL`: fixed malformed input or precisely named mutation of a
  pinned base, tested by an author's necessary-condition predicate. `expected`
  has `category` and local diagnostic `code`. Categories distinguish
  `STRUCTURALLY_INVALID`, `UNSUPPORTED_SCHEMA`, `MISSING_REQUIRED_EVIDENCE` and
  `DENIED_AUTHORIZATION`; these codes are not a new production error API.
- `CONTRACT_RELATIONAL_ASSERTION`: `execution` explicitly distinguishes
  `TEST_ONLY` from `NOT_EXECUTED`. A tested symbolic graph is not an issued graph.
- `BLOCKED_NOT_CONSTRUCTIBLE`: `NOT_EXECUTED`, missing prerequisites, category
  `NOT_CONSTRUCTIBLE`, and `expected_digest: null`. No positive bytes may exist.
- `DEFERRED_SEPARATE_OWNER`: unexecuted cross-owner/replay/release gates.

`TEST_ONLY` means the case is dispatched by the focused test, not a historical
execution receipt. The summary records actual command results. Documentary cases
have `operation: null`; their metadata validation is not execution of the claimed
operation. Negative canonical bytes are stored as literal hex in `input`, avoiding
separate nearly empty files. Other negatives use named single mutations of B01 or
explicit tiny graph/declaration inputs. A case's domain list states applicability;
domain table counts therefore overlap and must not be summed as unique cases.

The ledger retains all exact top-level contract keys. Canonical key order is
ASCII order; arrays preserve order recursively. Helper definitions expand nested
typed parents, and every ResourceRef's content parent is SOURCE-BYTES. Listed
resource roles include union alternatives and conditional roles; the transitive
semantic body closure and rights remain blocked. No resource role adds an
eleventh primary domain. Draft RS descriptor schemas remain input/status facts.

Archive verification checks the external ZIP pin, member count, safe paths,
bounded sizes, CRC, and all 408 manifest entries before selecting data in memory.
It never extracts or executes archived scripts. The 24 direct binary fixtures
are byte-compared against archive members. Historical 64-case composition stays
8 complete positives / 14 scalar fragments / 4 framing components / 21 documentary
refusals / 11 documentary relations / 5 blocked / 1 deferred. The other 56 are not
promoted to runtime passes by the new tests.

The root-depth limit retains a limited P2: `P2-DEPTH-64` and `P2-DEPTH-65` are
documentary, conditional examples, not frozen boundary conformance. The fragment
predicate's internal recursion budget is not a resolution of that ambiguity.

Only explicit +08:00 declaration arithmetic is tested. Actual named-zone/rule
identity remains blocked. The seven original raw source records and publication
pointers are retained in the pinned WU03 input packet; the test reads those
declarations without calling Native. Four diagnostic positions, equal numeric
values, a policy match or hash equality confer no admission or authorization.
Scope stays `diagnostic_only=True`, `admission_eligible=False`,
`NOT_TRUSTED_PIT_EVIDENCE`, `source_authentication=NOT_ESTABLISHED`,
`INTEGRATED_PROVISIONAL`. IF04/05/07, actual grants/revocations/receipts, Native
Channel A, production Codec/Channel B, F3/F5/F6 and TypeScript remain separately
gated. Full dirty-checkout CI is intentionally left to later clean integration.

See [authoring summary](../../../../docs/mvp/v1.0/wu05-oracle01-authoring-summary-v0.1.md)
for the coverage counts, exact commands and independent review handoff.
