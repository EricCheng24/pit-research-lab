"""Independent author checks; NOT production Codec conformance or Native replay."""

import copy
import json
import re
from collections import Counter
from decimal import ROUND_HALF_EVEN, Decimal
from hashlib import sha1, sha256
from pathlib import Path

import pytest
import wu05_oracle_reference as ref

ROOT = Path(__file__).resolve().parents[3]
FIX = ROOT / "tests/fixtures/mvp_if03/wu05_oracle01_v0_1"
OLD = ROOT / "tests/fixtures/mvp_if03/oracle01_v0_1"
BASELINE = "c2d66cf880d2e34d9f95f9351cbb616e3d5a7783"
DOMAINS = (
    "SOURCE-BYTES",
    "F2-QUALIFICATION",
    "F2-OBSERVATION",
    "TEMPORAL-SEQUENCE",
    "F3-EXPERIMENT",
    "F3-RUN-ATTEMPT",
    "RESULT",
    "EVIDENCE",
    "F5-DECISION",
    "F5-EVALUATION",
)


def read(path):
    return json.loads(path.read_bytes())


REGISTER = read(FIX / "cases.json")
CASES = REGISTER["cases"]
FROZEN = read(OLD / "FREEZE_MANIFEST.json")
EXECUTABLE = [c for c in CASES if c["execution"] == "TEST_ONLY"]


@pytest.fixture(scope="module")
def archived():
    return ref.checked_archive(
        OLD / FROZEN["original_evidence"]["path"], FROZEN["original_evidence"]
    )


def test_source_pins_and_register_schema():
    pins = read(FIX / "source_pins.json")
    assert pins["format"] == "wu05-oracle01-source-pins-v0.1"
    assert pins["baseline"] == REGISTER["baseline"] == BASELINE
    paths = [p["path"] for p in pins["files"]]
    assert len(paths) == len(set(paths))
    for pin in pins["files"]:
        path = Path(pin["path"])
        assert not path.is_absolute() and ".." not in path.parts
        raw = (ROOT / path).read_bytes()
        assert len(raw) == pin["byte_length"]
        assert sha256(raw).hexdigest() == pin["sha256"]
        assert sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() == pin["git_blob_sha1"]
    assert REGISTER["format"] == "wu05-oracle01-cases-v0.1"
    assert len({c["case_id"] for c in CASES}) == len(CASES)
    assert not (FIX / "positives").exists()  # No newly authored complete positives.
    allowed = {
        "VALID_COMPLETE_DOMAIN_POSITIVE",
        "EXECUTABLE_REFUSAL",
        "CONTRACT_RELATIONAL_ASSERTION",
        "BLOCKED_NOT_CONSTRUCTIBLE",
        "DEFERRED_SEPARATE_OWNER",
    }
    for c in CASES:
        assert set(c) == {
            "case_id",
            "domains",
            "status",
            "execution",
            "operation",
            "input",
            "expected",
            "source_clause",
            "note",
        }
        assert c["status"] in allowed
        assert c["domains"] and set(c["domains"]) <= set(DOMAINS)
        assert len(c["domains"]) == len(set(c["domains"]))
        assert bool(c["operation"]) == (c["execution"] == "TEST_ONLY")
        for source in c["source_clause"]:
            assert source["path"] in paths and source["clause"]
        if c["status"] in {"BLOCKED_NOT_CONSTRUCTIBLE", "DEFERRED_SEPARATE_OWNER"}:
            assert c["execution"] == "NOT_EXECUTED"
            assert c["expected"] == {"category": "NOT_CONSTRUCTIBLE", "expected_digest": None}
            assert c["input"]["missing_preconditions"]
            assert not (FIX / "positives" / c["case_id"]).exists()
        if c["status"] == "VALID_COMPLETE_DOMAIN_POSITIVE":
            assert c["case_id"] in FROZEN["scope"]["positive_ids"]
            assert c["domains"] == ["SOURCE-BYTES"]
            assert c["operation"] == "frozen"
        if c["status"] == "EXECUTABLE_REFUSAL":
            assert c["expected"]["category"] in {
                "STRUCTURALLY_INVALID",
                "UNSUPPORTED_SCHEMA",
                "MISSING_REQUIRED_EVIDENCE",
                "DENIED_AUTHORIZATION",
            }
            assert c["expected"]["code"] and c["execution"] == "TEST_ONLY"
    declarations = read(FIX / "schedule_declaration.json")
    assert set(declarations) == {
        "original_input_refs",
        "expected_original_input_refs",
        "PF038",
        "expected_input_ref",
        "invariant_policy_ref",
        "AF009",
        "sequence_schedule_ref",
        "expected_schedule_ref",
    }
    b01 = FROZEN["golden_positives"][0]
    expected_content = {
        "domain_tag": b01["domain_tag"],
        "object_schema_version": b01["object_schema_version"],
        "canonical_profile_version": ref.PROFILE,
        "digest_algorithm": "SHA-256",
        "canonical_payload_byte_length": {"type": "uint64", "value": "187"},
        "digest_hex": b01["expected_frame_digest_sha256"],
    }
    assert (
        declarations["original_input_refs"]
        == declarations["expected_original_input_refs"]
        == [expected_content]
    )
    assert declarations["PF038"] == declarations["expected_input_ref"] == expected_content
    for key, role in (
        ("invariant_policy_ref", "SCHEDULE_INVARIANT_POLICY"),
        ("AF009", "SCHEDULE_INVARIANT_POLICY"),
        ("sequence_schedule_ref", "DECISION_SCHEDULE"),
        ("expected_schedule_ref", "DECISION_SCHEDULE"),
    ):
        wrapper = declarations[key]
        assert set(wrapper) == {
            "resource_kind",
            "resource_version",
            "resource_schema",
            "content_ref",
        }
        assert wrapper["resource_kind"] == role and wrapper["content_ref"] == expected_content
        assert wrapper["resource_version"] == "HYPOTHETICAL_NON_ISSUED"
        assert wrapper["resource_schema"] == "HYPOTHETICAL_UNREVIEWED"


def test_exact_ten_domain_coverage():
    coverage = read(FIX / "domain_coverage.json")
    assert coverage["format"] == "wu05-oracle01-domain-coverage-v0.1"
    assert coverage["baseline"] == BASELINE
    assert set(coverage) == {
        "format",
        "baseline",
        "parent_order_rule",
        "resource_role_rule",
        "helper_contracts",
        "helper_clause_specs",
        "domains",
    }
    assert tuple(d["domain"] for d in coverage["domains"]) == DOMAINS
    contract = (ROOT / "docs/mvp/v1.0/shared-interface-contract-v0.1.md").read_text()
    for name, rule in coverage["helper_contracts"].items():
        assert f"| {name} | {rule} |" in contract
    for name, spec in coverage["helper_clause_specs"].items():
        assert spec.startswith(f"**AD01-07.{name} ") and spec in contract
    role_line = next(
        s for s in contract.splitlines() if s.startswith("Registered ResourceRef role literals:")
    )
    registered_roles = set(re.findall(r"`([A-Z_]+)`", role_line))
    categories = {
        "positive_cases": "VALID_COMPLETE_DOMAIN_POSITIVE",
        "refusal_case_ids": "EXECUTABLE_REFUSAL",
        "blocked_case_ids": "BLOCKED_NOT_CONSTRUCTIBLE",
        "relational_case_ids": "CONTRACT_RELATIONAL_ASSERTION",
        "deferred_case_ids": "DEFERRED_SEPARATE_OWNER",
    }
    for d in coverage["domains"]:
        assert set(d) == {
            "domain",
            "exact_schema_tag_profile",
            "semantic_fields",
            "contract_field_spec",
            "required_resource_roles",
            "typed_parent_order",
            *categories,
            "evidence_preconditions",
            "status",
            "source_clause",
            "next_owner_or_work_unit",
        }
        domain = d["domain"]
        assert d["exact_schema_tag_profile"] == {
            "domain_tag": f"PITLAB/ACADEMIC/{domain}/candidate-v0.1",
            "object_schema_version": domain.lower() + "-candidate-v0.1",
            "canonical_profile_version": ref.PROFILE,
        }
        line = next(s for s in contract.splitlines() if s.startswith(f"| {domain};"))
        assert d["contract_field_spec"] == line.split(" | ")[1]
        # Extract field names before ':'; explanatory semicolon phrases add no keys.
        actual = re.findall(r"(?:^|; )([a-z_][a-z0-9_]*):", d["contract_field_spec"])
        assert d["semantic_fields"] == ["canonical_profile_version", *actual]
        assert len(set(d["semantic_fields"])) == len(d["semantic_fields"])
        assert d["typed_parent_order"] or domain == "SOURCE-BYTES"
        assert set(d["required_resource_roles"]) <= registered_roles
        assert all(
            s["path"] == "docs/mvp/v1.0/shared-interface-contract-v0.1.md" and s["clause"]
            for s in d["source_clause"]
        )
        assert d["evidence_preconditions"] and d["next_owner_or_work_unit"]
        for key, status in categories.items():
            assert d[key] == [
                c["case_id"] for c in CASES if domain in c["domains"] and c["status"] == status
            ]
        assert d["status"] == (
            "VALID_COMPLETE_DOMAIN_POSITIVE" if d["positive_cases"] else "BLOCKED_NOT_CONSTRUCTIBLE"
        )


def test_archive_historical_composition(archived):
    scope = json.loads(archived["oracle_scope_register.json"])
    assert scope["cases_total"] == FROZEN["scope"]["total_cases"] == 64
    assert (
        scope["class_counts"]
        == FROZEN["scope"]["class_counts"]
        == {
            "VALID_COMPLETE_DOMAIN": 8,
            "SCALAR_FRAGMENT_EXACT_BYTES": 14,
            "FRAMING_COMPONENT_EXACT_BYTES": 4,
            "CONTRACT_REFUSAL_ONLY": 21,
            "RELATIONAL_ASSERTION_ONLY": 11,
            "BLOCKED_BY_RESOURCE_SCHEMA": 5,
            "DEFERRED_TO_FUTURE_DOMAIN_ORACLE": 1,
        }
    )
    assert Counter(v["class"] for v in scope["vectors"]) == scope["class_counts"]
    assert len(FROZEN["non_promoted"]) == 56  # Historical records, NOT 56 runtime passes.


def frozen_parts(cid, archived):
    expected = json.loads(archived[f"vectors/{cid}/expected.json"])
    return (
        (OLD / "positives" / cid / "frame.bin").read_bytes(),
        copy.deepcopy(expected["expected_envelope_fields"]),
    )


def check_frozen(cid, archived):
    row = next(r for r in FROZEN["golden_positives"] if r["vector_id"] == cid)
    expected = json.loads(archived[row["source_expected_record"]])
    parts = {}
    for name, pin in row["artifacts"].items():
        raw = (OLD / pin["fixture_path"]).read_bytes()
        assert raw == archived[pin["source_zip_member"]]
        assert len(raw) == pin["byte_length"] and sha256(raw).hexdigest() == pin["file_sha256"]
        parts[name] = raw
    raw = parts["raw_body.bin"]
    payload, frame = ref.source_bytes(raw)
    assert payload == parts["canonical_payload.bin"]
    assert frame == parts["frame.bin"]
    assert len(payload) == row["expected_payload_only_envelope_byte_length"] == 187
    assert len(frame) == 281
    assert sha256(raw).hexdigest() == row["raw_body_sha256"] == expected["expected_raw_sha256"]
    assert sha256(frame).hexdigest() == row["expected_frame_digest_sha256"]
    assert sha256(frame).hexdigest() == expected["expected_frame_sha256"]
    assert payload.hex() == expected["exact_scalar_or_payload_bytes_hex"]["canonical_payload"]
    assert frame.hex() == expected["exact_frame_bytes_hex"]
    envelope = {
        "domain_tag": ref.DOMAIN.decode(),
        "object_schema_version": ref.SCHEMA.decode(),
        "canonical_profile_version": ref.PROFILE,
        "digest_algorithm": "SHA-256",
        "canonical_payload_byte_length": {"type": "uint64", "value": "187"},
        "digest_hex": row["expected_frame_digest_sha256"],
    }
    assert envelope == expected["expected_envelope_fields"]
    ref.source_frame(frame, envelope)


def weekly(inp):
    assert tuple(inp["cutoffs"]) == ref.CUTOFFS
    packet = read(ROOT / inp["source_packet"]["path"])
    assert [s["tag"] for s in packet["sources"]] == inp["source_packet"]["tag_order"]
    assert inp["source_packet"]["tag_order"] == ["O", "N", "D1", "D2", "D3", "N12", "N23"]
    originals = {}
    for index, source in enumerate(packet["sources"]):
        raw = source["raw"]["utf8"].encode()
        assert len(raw) == source["raw"]["byte_length"]
        assert sha256(raw).hexdigest() == source["raw"]["sha256"]
        pub = source["source"]["request"]["attempts"][0]["supplied"]["proof_candidate"]
        assert pub["timestamp"]["timezone_name"] == "Asia/Taipei"
        assert pub["timestamp"]["offset"] == "+08:00"
        assert pub["timestamp"]["precision"] == "SECOND"
        assert pub["timestamp"]["origin"]  # Retain original, never mint an Origin ResourceRef.
        originals[source["tag"]] = (pub["timestamp"]["source_text"], json.loads(raw))
        assert index < 7  # No synthesized source/history/coverage records.
    selected = []
    for cutoff in ref.CUTOFFS:
        selected.append(
            next(
                tag
                for tag in ("D3", "D2", "D1")
                if ref.declared_time(originals[tag][0]) < ref.declared_time(cutoff)
            )
        )
    assert selected == inp["selected"] == ["D1", "D2", "D2", "D3"]
    assert originals["D2"][0] == ref.CUTOFFS[0]
    assert originals["D3"][0] == "2027-01-29T18:00:01+08:00"
    # Exact diagnostic arithmetic, not a rerun of A04/A05 or qualification.
    prior = sum(originals[tag][1]["statements"][0]["value"] for tag in ("O", "N"))
    numerators = [originals[tag][1]["statements"][0]["value"] for tag in selected]
    assert [n + prior for n in numerators] == inp["a04"] == [140, 150, 150, 130]
    computed = [
        str(
            (Decimal(n) / Decimal(n + prior)).quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_EVEN
            )
        )
        for n in numerators
    ]
    assert computed == inp["a05"]
    assert inp["no_session_week"] == "2027-W03"
    assert [ref.declared_time(t).strftime("%H:%M:%SZ") for t in ref.CUTOFFS] == ["10:00:00Z"] * 4
    assert len(set(ref.CUTOFFS)) == 4
    assert ref.CUTOFFS[1] != ref.CUTOFFS[2] and selected[1] == selected[2]
    return "DIAGNOSTIC_DECLARATIONS_ONLY"


def run_case(c, archived):
    op, inp = c["operation"], c["input"]
    if op == "frozen":
        check_frozen(inp["vector_id"], archived)
        return "EXACT_STORED_BYTES"
    if op == "fragment":
        return ref.canonical_fragment(bytes.fromhex(inp["hex"]))
    if op == "integer":
        return ref.integer(inp["value"], inp["signed"])
    if op == "boolean":
        ref.need(type(inp["value"]) is bool, "BOOLEAN_TYPE")
    elif op == "decimal_scale":
        ref.need(ref.integer(inp["value"]) <= 18, "DECIMAL_SCALE")
    elif op == "ratio":
        units = ref.integer({"type": "uint64", "value": inp["scaled_units"]})
        ref.need(
            inp["scale"] == "6"
            and inp["unit"] == "FRACTION"
            and units <= 1000000
            and inp["decimal_text"] == f"{units // 1000000}.{units % 1000000:06}",
            "RATIO_MISMATCH",
        )
    elif op == "payload":
        raw = (OLD / "positives/B01/canonical_payload.bin").read_bytes()
        mutation = inp["mutation"]
        if mutation == "unknown":
            raw = raw[:-1] + b',"extra":"x"}'
        elif mutation == "missing":
            raw = raw.replace(b'"body_byte_length":{"type":"uint64","value":"0"},', b"")
        elif mutation == "own_envelope":
            raw = raw[:-1] + b',"digest_hex":"' + inp["own_digest_claim"].encode("ascii") + b'"}'
        else:
            raise AssertionError(f"Unhandled payload mutation: {mutation}")
        ref.source_payload(raw)
    elif op == "frame":
        frame, envelope = frozen_parts(inp["base"], archived)
        mutation = inp["mutation"]
        if mutation == "profile":
            frame = frame.replace(b"typed-json-candidate-v0.1", b"typed-json-candidate-v9.9")
        elif mutation == "length":
            frame = frame[:86] + (188).to_bytes(8, "big") + frame[94:]
        elif mutation == "endian":
            frame = frame[:8][::-1] + frame[8:]
        elif mutation == "order":
            frame = frame[51:86] + frame[:51] + frame[86:]
        elif mutation == "trailing":
            frame += b"x"
        elif mutation in {"zero", "over_limit"}:
            frame = frame[:86] + (0 if mutation == "zero" else 16777217).to_bytes(8, "big")
        elif mutation == "envelope_length":
            envelope["canonical_payload_byte_length"]["value"] = "281"
        elif mutation == "unframed_hash":
            envelope["digest_hex"] = sha256(frame[94:]).hexdigest()
        elif mutation == "digest":
            envelope["digest_hex"] = "0" * 64
        else:
            field = {
                "domain": "domain_tag",
                "schema": "object_schema_version",
                "algorithm": "digest_algorithm",
                "envelope_profile": "canonical_profile_version",
            }[mutation]
            envelope[field] = "UNSUPPORTED_NO_DOWNGRADE"
        ref.source_frame(frame, envelope)
    elif op == "unicode":
        a, b = (bytes.fromhex(inp[k]) for k in ("nfc_hex", "nfd_hex"))
        assert ref.canonical_fragment(a) == "é"
        assert ref.canonical_fragment(b) == "e\u0301"
        assert a != b
        return "DISTINCT_SCALAR_BYTES"
    elif op == "raw_mutation":
        raw = (OLD / "positives" / inp["base"] / "raw_body.bin").read_bytes()
        changed = bytes.fromhex(inp["replacement_hex"])
        assert raw != changed and ref.source_bytes(raw) != ref.source_bytes(changed)
        return "DIFFERENT_PREIMAGE_AND_FRAME"
    elif op == "weekly":
        return weekly(inp)
    elif op == "before":
        ref.need(
            ref.declared_time(inp["published_at"])
            < ref.declared_time(ref.CUTOFFS[inp["cutoff_index"]]),
            "NOT_BEFORE",
        )
    elif op == "time":
        ref.declared_time(inp["source_text"])
    elif op == "ticks":
        ticks = list(ref.CUTOFFS)
        mutation = inp["mutation"]
        if mutation == "swapped":
            ticks[1], ticks[2] = ticks[2], ticks[1]
        elif mutation == "dropped":
            ticks.pop()
        elif mutation == "duplicate":
            ticks[2] = ticks[1]
        elif mutation == "foreign":
            ticks[3] = "FOREIGN_TICK"
        elif mutation == "annotation_as_tick":
            ticks.append("2027-W03")
        else:
            ticks[0] = "2027-01-08T00:00:00+08:00"
        ref.need(tuple(ticks) == ref.CUTOFFS, "FIXED_SCHEDULE")
    elif op == "contexts":
        ref.need(len(set(inp["contexts"])) == 4, "REUSED_CONTEXT")
    elif op == "graph":
        ref.graph_condition(inp["nodes"], inp["root"])
        return "ACYCLIC_SYMBOLIC_ONLY"
    elif op == "experiment_input":
        ref.need(
            set(inp) == {"kind", "temporal_binding_set_ref", "association_contract_version"},
            "EXPERIMENT_INPUT_FIELDS",
        )
    elif op == "native_summary":
        fields = {
            "owner",
            "type",
            "state",
            "reason_code",
            "unknown",
            "first_failure",
            "invocation",
            "invocation_receipt_ref",
        }
        ref.need(set(inp["summary"]) == fields, "NATIVE_SUMMARY_FIELDS")
    elif op in {"safe_fields", "decision_fields"}:
        fields = (
            {
                "issuer_ref",
                "feature_ref",
                "cutoff",
                "value",
                "unit",
                "qualification_ref",
                "scope_flags",
            }
            if op == "safe_fields"
            else {
                "canonical_profile_version",
                "sequence_tick_ref",
                "policy_ref",
                "observation_refs",
                "action",
                "decision_execution_rules_ref",
            }
        )
        ref.need(
            fields | {inp["extra"]} == fields,
            "SAFE_FIELDS" if op == "safe_fields" else "DECISION_FIELDS",
        )
    elif op == "authorization":
        grant = inp["grant"]
        ref.need(
            grant is not None and grant.get("revoked") is False,
            "ACCESS_DENIED",
            "DENIED_AUTHORIZATION",
        )
    elif op == "parent_match":
        ref.need(inp["expected_domain"] == inp["supplied_domain"], "FOREIGN_PARENT")
        ref.need(inp["expected_revision"] == inp["supplied_revision"], "STALE_PARENT")
    elif op == "resource_schema":
        # No approved concrete timezone resource schema is supplied by the contract.
        reviewed_pairs = set()
        ref.need(
            (inp["role"], inp["schema"]) in reviewed_pairs,
            "REF_UNAPPROVED_RESOURCE_SCHEMA",
            "UNSUPPORTED_SCHEMA",
        )
    elif op == "maturity":
        ref.need(
            ref.declared_time(inp["available_at"]) <= ref.declared_time(inp["evaluation_at"]),
            "IMMATURE_OUTCOME",
        )
    elif op in {"schedule", "policy_change"}:
        value = read(FIX / "schedule_declaration.json")
        if op == "policy_change":
            changed = copy.deepcopy(value)
            changed["invariant_policy_ref"]["resource_version"] = "HYPOTHETICAL_CHANGE"
            assert changed["invariant_policy_ref"] != value["invariant_policy_ref"]
            assert {k: changed[k] for k in ("original_input_refs", "invariant_policy_ref")} != {
                k: value[k] for k in ("original_input_refs", "invariant_policy_ref")
            }
            return "DEPENDENCY_PREIMAGE_DIFFERS"
        mutation = inp["mutation"]
        if mutation == "originals":
            value["original_input_refs"] = []
        elif mutation == "PF038":
            value["PF038"]["digest_hex"] = "0" * 64
        elif mutation == "AF009":
            value["AF009"]["resource_version"] = "HYPOTHETICAL_CHANGE"
        elif mutation == "schedule":
            value["sequence_schedule_ref"]["resource_version"] = "HYPOTHETICAL_CHANGE"
        return ref.schedule_path(value)
    else:
        raise AssertionError(f"Unhandled case operation: {op}")


@pytest.mark.parametrize(
    ("suffix", "expected_code"),
    [
        (b',"extra":"unrelated"}', "CLOSED_FIELDS"),
        (
            b',"digest_hex":"687ddd2e1d12816f5e20e505af0bb9d6f149ddf218e7f37a6eb6dc13df3ea686"}',
            "REF_CYCLE",
        ),
        (
            b',"reference":{"canonical_payload_byte_length":{"type":"uint64","value":"187"},'
            b'"canonical_profile_version":"typed-json-candidate-v0.1",'
            b'"digest_algorithm":"SHA-256",'
            b'"digest_hex":"687ddd2e1d12816f5e20e505af0bb9d6f149ddf218e7f37a6eb6dc13df3ea686",'
            b'"domain_tag":"PITLAB/ACADEMIC/SOURCE-BYTES/candidate-v0.1",'
            b'"object_schema_version":"source-bytes-candidate-v0.1"}}',
            "REF_CYCLE",
        ),
    ],
    ids=("ordinary-unknown", "own-digest", "own-envelope"),
)
def test_own_reference_refusal_is_distinct_from_unknown_fields(suffix, expected_code):
    # Literal malformed claims: no self-consistent digest or reference is issued.
    payload = (OLD / "positives/B01/canonical_payload.bin").read_bytes()
    with pytest.raises(ref.Refusal) as caught:
        ref.source_payload(payload[:-1] + suffix)
    assert caught.value.category == "STRUCTURALLY_INVALID"
    assert caught.value.code == expected_code


@pytest.mark.parametrize("case", EXECUTABLE, ids=lambda c: c["case_id"])
def test_authored_case(case, archived):
    if case["status"] == "EXECUTABLE_REFUSAL":
        with pytest.raises(ref.Refusal) as caught:
            run_case(case, archived)
        assert caught.value.category == case["expected"]["category"]
        assert caught.value.code == case["expected"]["code"]
    else:
        assert run_case(case, archived) == case["expected"]
