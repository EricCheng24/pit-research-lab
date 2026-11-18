# WU05 research vertical slice runtime contract v0.1

This is an executable **synthetic Stage V demonstration**, pending independent
technical review. Its authority is baseline
`4d3e56291dc5831be3dd85c00106a91055d3d3d1` and the two merged
`wu05-rebaseline01-*` owner/matrix documents. No Stage V acceptance is assigned here.
All eight Stage M cases remain `NOT_RUN / NOT_VERIFIED`. Original Full Functional
Scheme B remains `NOT_COMPLETED`; the earlier five S1 approvals remain `0/5`.

## Original extraction and trust boundary

`sources.load_pinned_synthetic_events()` checks actual original file bytes before
JSON decoding. `SOURCE_PINS` records the fixed paths, SHA-256 and byte lengths:

| Original fixture under `tests/unit/mvp_f2/data/` | Bytes | SHA-256 |
|---|---:|---|
| `temporal_foundation_v0.1.json` | 72800 | `3b81aae8e3242468c3076911861a13b6f1646f42d068be67b316af9caef1c373` |
| `derived_observations_v0.1.json` | 5440756 | `b9e1babbcc86b0e70ed5589972259fcbe6b666a38d2e7eff77d108f448e4dc0e` |

The loader reads no generated pack, Native result, fixture oracle, external store,
credential, grant resolver or protected project. Neither a digest nor a SYN-A name
proves real-world provenance. Trust here means the explicitly pinned authored
synthetic declarations, within this demonstration only.

Foundation original pointers are `/input_spec/revenue_events/{i}/amount`,
`.../publication/instant/source_text`, `.../source_ref`, `.../version_ref`,
`.../issuer_ref`, `.../reference_month` and `.../supersedes_ref` for indices 0–3.
Rows 0/1/3 form the original SYN-A December revision chain (100/110/90);
row 2 is a separate SYN-B record (200), published one second after t1.
The event content digest for these rows hashes the **research JSON encoding of the
original row**, not an invented original raw fragment encoding. The full original
fixture byte digest above remains authoritative for the source bytes.

For the seven original notices, `/sources/{i}/raw/utf8` is parsed as a separate
original JSON fragment. Its `/statements/0/value`, `/subject_id`, `/assertion_id`
and `/content_version_id` are linked to the exact original timestamp at
`/sources/{i}/source/request/attempts/0/supplied/proof_candidate/timestamp/source_text`.
The loader checks raw SHA/length, timestamp format/offset/precision, raw descriptor,
fragment selector, publication event and assertion/version links. The combined
pointer notation `.../raw/utf8#/statements/0/value` means fixture JSON pointer,
then pointer within its decoded UTF-8 JSON fragment. It is not a ResourceRef.

| i / tag | Original publication (+08:00) | Original amount/declaration |
|---|---|---:|
| 0 / O | 2026-11-05T12:00:00 | 17 |
| 1 / N | 2026-12-05T12:00:00 | 23 |
| 2 / D1 | 2027-01-07T17:59:59 | 100 |
| 3 / D2 | 2027-01-07T18:00:00 | 110 |
| 4 / D3 | 2027-01-29T18:00:01 | 90 |
| 5 / N12 | 2027-01-07T18:00:00 | 1 (correction declaration) |
| 6 / N23 | 2027-01-29T18:00:01 | 1 (correction declaration) |

The original relation arrays encoded in N12/N23's `metric` fields link the D1→D2→D3
revision chain. Their endpoints and publication times are checked; only their
eligible integer declaration and sanitized provenance are public. This is a local
research reconstruction, with no Native B02 equivalence claim. Tag names or old
tests alone do not establish the source linkage. The explicit `Unknown` at
`/sources/0/source/request/content/provider_ref/type` becomes a public `UNKNOWN`
status with no provider value or private reason.

Publication declarations determine available decision inputs only under the
bounded policy `original_publication < cutoff`. They are neither real delivery
timestamps nor Native temporal qualification. `/manual_oracle`, `/oracle`,
`/views`, `/native_controls`, prices/templates, endpoints and all original
diagnostic/audit material are excluded. No labels, rewards or price cells are
ever adapter inputs, including after the last cutoff.

## Observation and episode

`InputEvent`, provenance, ledger and observations use frozen slotted value types;
public snapshots are detached. The ledger keeps original subject/field identities
and publication text. Selection order is validated revision-chain depth,
publication text, source, version, record. Fixed +08:00 SECOND representations
make lexical timestamp order chronological here. Duplicate identities, same-key
same-clock priorities, missing parents, branches, cycles and contradictory
revision ordering refuse. Equal-clock distinct logical origins stay separate.

`asof_view(ledger, cutoff)` accepts only the four fixed SYN-A cutoffs at 18:00:00
+08:00 on 2027-01-07, 01-15, 01-29 and 02-05. It excludes AT and AFTER, does not
interpolate, and reconstructs old views without updating old facts. The foundation
calendar is checked for these four last-session dates and the no-session week of
January 18. W03 is a configuration annotation only, never a step or action.
The code uses the original fixed offset, with **no host tzdb authority claim**.

Public slots are declared in `contracts.SOURCE_KEYS`; the availability mask is
derived from the same immutable features. Unpublished slots contain only `ABSENT`,
`None`, unit `NONE` and no provenance. They disclose the fixed requested feature
schema, not future values, future publication dates or future version IDs.
`restricted_fields=WITHHELD` is a local research API exclusion status;
`evaluation=NOT_EVALUATED` records no evaluation; `unprovided_feature=ABSENT`
records no supplied feature. These are explicitly **policy states**, not invented
original source facts or CAN-07 values. None is zero-filled or promoted to KNOWN.

`ResearchEnvironment.reset(seed, agent_id)` starts at t1 with empty transitions;
`observe()` returns only the current detached public snapshot. `step(action)`
returns a `StepResult` containing the next observation (or terminal `None`) and
the current transition. Valid actions are HOLD, FLAG_REVIEW and ABSTAIN. Invalid
actions record `REFUSED_INVALID_ACTION` with no attacker-controlled action text
and no advancement. The fourth valid step terminates; subsequent step/observe
calls raise `EPISODE_NOT_ACTIVE`. Resets and independent environments share no
mutable episode state. Constructor ledger injection is a **trusted kernel/test
seam**, not an adapter input or an alternative pin authority.

The baseline ignores feature values and chooses HOLD for odd seeds, ABSTAIN for
even seeds. The comparator flags eligible December amounts ≥ the declared
threshold (default 105), holds below it, abstains when unavailable. Both receive
identical observations and masks. These are research choices, with no orders,
fills, returns, trained model, cost model or benchmark/evaluation claim.

The protection is **public API non-disclosure for cooperative/instrumented
adapters**, not a sandbox for malicious Python with filesystem/process privileges.
Private-name reflection, import monkeypatching and host filesystem access require
separate isolation. Tests exercise public fields/repr/properties, mutation,
next-cutoff requests, invalid actions and episode isolation. No legacy release,
Default DENIED/WITHHELD, IF03 identity or issuance path is invoked or weakened.

## Replay and reproduction

`RESEARCH_TRACE_V0.1` is a separately named non-IF03 research JSON format. Its
closed producer contains format/non-IF03 marker, execution identity and two
episodes. Each episode contains agent ID, four ordered ticks and terminal. Each
tick has cutoff/order, public observation and digest, availability mask, and
action/transition/disposition/next-order/terminal. No hidden source or reward
payload is hashed into the trace. Serialization uses `json.dumps(sort_keys=True,
ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")`,
without a trailing newline. All floats, sets and other objects are refused.
SHA-256 hashes **exactly these trace bytes**.

The execution identity hashes the stable manifest specification, including actual
source byte pins, research code and test file digests, package/format, configuration,
seed, agent IDs and Python version/implementation. The final manifest additionally
records trace SHA/size. Code-file digests supply implementation identity; the
authority baseline is not claimed as the new implementation commit. No wall time,
PID, hostname or output path enters the identity. Runtime test inventory is labeled
`NOT_ATTESTED_BY_RUNTIME`; only executed pytest evidence reports results.

From a source checkout with the locked environment already installed:

```sh
UV_OFFLINE=1 UV_NO_SYNC=1 uv run --locked python -m pit_research_lab.mvp.research_vslice.cli --seed 17 --output-dir /tmp/wu05-research-vslice01-UNIQUE/run-a
UV_OFFLINE=1 UV_NO_SYNC=1 uv run --locked python -m pit_research_lab.mvp.research_vslice.cli --seed 17 --output-dir /tmp/wu05-research-vslice01-UNIQUE/run-b
cmp /tmp/wu05-research-vslice01-UNIQUE/run-a/trace.json /tmp/wu05-research-vslice01-UNIQUE/run-b/trace.json
UV_OFFLINE=1 UV_NO_SYNC=1 uv run --locked pytest -q tests/unit/mvp_research_vslice
```

Use a new absolute output directory outside the checkout. Existing output paths,
symlink components and parent traversal refuse. The CLI writes `trace.json` and
`manifest.json`, and prints trace SHA. Both fresh processes independently load
the originals. Seed 18 and `--rule-threshold 95` are executed sensitivity controls;
future-D3 in-memory poisoning tests leave pre-t4 observations unchanged and alter
t4. Original fixture bytes are never rewritten. The focused suite fails if any
required Stage V case is missing, skipped or unexecuted. Separate external evidence
records exact commands, executed results, both replay outputs and file integrity.

This format has no IF03 registration, live right, Resource Issuance, Native
equivalence, empirical TWSE validation, S1 ratification or global RC acceptance.
