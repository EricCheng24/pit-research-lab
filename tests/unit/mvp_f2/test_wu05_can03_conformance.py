"""Frozen literal expectations versus separately invoked public CAN-01/02 APIs.

Adapters supply only declared fragment grammar or vocabulary translations. None
construct parent bytes, resource approval, rights, schedules or Native receipts.
"""

import copy
import json
from hashlib import sha256

import pytest
from wu05_can03_expected import AUTHOR, PROFILE, ledger, literal_source, stored

from pit_research_lab.mvp.if03 import canonical_codec as codec
from pit_research_lab.mvp.if03 import typed_references as refs
from pit_research_lab.mvp.if03.dependency_graph import (
    SymbolicEdge,
    SymbolicNode,
    check_dependency_graph_symbolic,
)

CASES = ledger()
# Independently explicit scope; coverage tests extract and compare the historical definitions.
CORE_IDS = set(
    """
N-DUPLICATE N-BOM N-UTF8 N-SURROGATE N-ORDER N-WHITESPACE N-SHORT-ESCAPE
N-UPPER-ESCAPE N-ASCII-ESCAPE N-SLASH-ESCAPE N-NULL N-BARE-INT N-FLOAT N-NAN
N-INFINITY N-MISSING N-UNKNOWN N-OWN-ENVELOPE N-PLUS N-ZERO-PREFIX
N-NEGATIVE-ZERO N-EXPONENT N-UINT-NEGATIVE N-INT-OVERFLOW N-UINT-OVERFLOW
N-BOOL-COERCION N-BOOL-INT N-DECIMAL-SCALE N-RATIO-MISMATCH N-PROFILE
N-FRAME-LENGTH N-ENDIAN N-SECTION-ORDER N-TRAILING N-PAYLOAD-LENGTH
N-UNFRAMED-HASH N-DIGEST N-DOMAIN N-SCHEMA N-ALGORITHM N-ENVELOPE-PROFILE
N-ZERO-LENGTH N-OVER-LIMIT
""".split()
)
REF_IDS = {
    "N-ASSOCIATION-INSTANCE",
    "N-FOREIGN-PARENT",
    "N-UNREVIEWED-RESOURCE",
    "N-DECISION-FUTURE-PRICE",
    "N-DECISION-OUTCOME",
    "N-DECISION-LABEL",
}
GRAPH_IDS = {"N-CYCLE", "N-HIDDEN-ATTEMPT", "N-DANGLING", "N-RESULT-ATTEMPT"}
RELATION_IDS = {
    "R-UNICODE",
    "R-RAW-MUTATION",
    "R-EVIDENCE-DIRECTION",
    "R-FOUR-CUTOFFS",
    "R-D06-CONSISTENT",
    "R-D06-POLICY-CHANGE",
}


def uint(n):
    return {"type": "uint64", "value": str(n)}


def numeric_policy():
    # Frozen B01 envelope is content integrity only. No semantic policy bytes exist.
    return {
        "resource_kind": "NUMERIC_POLICY",
        "resource_version": "NON_ISSUED",
        "resource_schema": "UNREVIEWED_SHAPE_ONLY",
        "content_ref": stored()[3],
    }


def decimal(scale="6"):
    return {
        "type": "decimal",
        "coefficient": {"type": "int64", "value": "-10"},
        "scale": uint(scale),
        "unit": "",
        "numeric_policy_ref": numeric_policy(),
    }


def ratio(units="733333", text="0.733333", scale="6", unit="FRACTION"):
    return {
        "type": "fixed_ratio6",
        "scaled_units": uint(units),
        "decimal_text": text,
        "scale": uint(scale),
        "unit": unit,
        "numeric_policy_ref": numeric_policy(),
    }


def graph_adapter(inp):
    """Preserve all supplied adjacency, even disconnected nodes and dangling targets.

    SEMANTIC is opaque; fields on ATTEMPT are descriptive, not authenticated data.
    Generic dependency edges claim no typed field path or real graph completeness.
    """
    assert set(inp) == {"nodes", "root"} and inp["root"] in inp["nodes"]
    kinds = {
        "SOURCE": "SOURCE-BYTES",
        "SEQUENCE": "TEMPORAL-SEQUENCE",
        "QUALIFICATION": "F2-QUALIFICATION",
        "SEMANTIC": "SEMANTIC_RESOURCE",
        "ATTEMPT": "F3-RUN-ATTEMPT",
        "RESULT": "RESULT",
        "EVIDENCE": "EVIDENCE",
    }
    nodes = []
    for name, data in inp["nodes"].items():
        assert set(data) in ({"kind", "parents"}, {"kind", "parents", "fields"})
        if "fields" in data:
            assert data["kind"] == "ATTEMPT" and data["fields"] == ["host", "clock", "token"]
        nodes.append(
            SymbolicNode(name, kinds[data["kind"]], tuple(SymbolicEdge(p) for p in data["parents"]))
        )
    return tuple(nodes)


def dispatch_negative(case):
    """Faithful, narrow mappings; expected outputs are never derived here."""
    cid, op, inp = case["case_id"], case["operation"], case["input"]
    assert cid in CORE_IDS | REF_IDS | GRAPH_IDS
    if op == "fragment":
        names = ("a", "b") if cid == "N-ORDER" else ("a",)
        schema = codec.RecordSchema(tuple((k, codec.TEXT) for k in names))
        return codec.parse_canonical_record(bytes.fromhex(inp["hex"]), schema)
    if op == "integer":
        return codec.validate_integer(inp["value"], signed=inp["signed"])
    if op == "boolean":
        return codec.validate_boolean(inp["value"])
    if op == "decimal_scale":
        value = decimal()
        value["scale"] = inp["value"]
        return codec.validate_numeric_fragment(value)
    if op == "ratio":
        return codec.validate_numeric_fragment(
            ratio(inp["scaled_units"], inp["decimal_text"], inp["scale"], inp["unit"])
        )
    if op == "payload":
        payload = stored()[1]
        match inp["mutation"]:
            case "missing":
                payload = payload.replace(b'"body_byte_length":{"type":"uint64","value":"0"},', b"")
            case "unknown":
                payload = payload[:-1] + b',"extra":"x"}'
            case "own_envelope":
                payload = (
                    payload[:-1] + b',"digest_hex":"' + inp["own_digest_claim"].encode() + b'"}'
                )
            case _:
                raise AssertionError(inp)
        return codec.parse_canonical_record(payload, codec.SOURCE_PAYLOAD_SCHEMA)
    if op == "frame":
        _, payload, frame, envelope = stored(inp["base"])
        # Exact LP64BE boundaries independently known from literal frozen parts.
        match inp["mutation"]:
            case "profile":
                frame = frame.replace(PROFILE.encode(), b"typed-json-candidate-v9.9")
            case "length":
                frame = frame[:86] + (len(payload) + 1).to_bytes(8, "big") + frame[94:]
            case "endian":
                frame = frame[:8][::-1] + frame[8:]
            case "order":
                frame = frame[51:86] + frame[:51] + frame[86:]
            case "trailing":
                frame += b"x"
            case "zero":
                frame = frame[:86] + bytes(8)
            case "over_limit":
                frame = frame[:86] + (16_777_217).to_bytes(8, "big")
            case "envelope_length":
                envelope["canonical_payload_byte_length"] = uint(len(frame))
            case "unframed_hash":
                envelope["digest_hex"] = sha256(payload).hexdigest()
            case "digest":
                envelope["digest_hex"] = "0" * 64
            case field:
                key = {
                    "domain": "domain_tag",
                    "schema": "object_schema_version",
                    "algorithm": "digest_algorithm",
                    "envelope_profile": "canonical_profile_version",
                }[field]
                envelope[key] = "UNSUPPORTED_NO_DOWNGRADE"
        return codec.verify_source_frame(frame, envelope)
    if op == "graph":
        return check_dependency_graph_symbolic(graph_adapter(inp))
    if op == "experiment_input":
        return refs.validate_experiment_input_shape(inp)
    if op == "parent_match":
        # Foreign declaration only. Revisions are equal in this single-fault case;
        # stale revision comparison is deliberately not dispatched.
        assert inp["expected_revision"] == inp["supplied_revision"]
        return refs.validate_declared_parent_domain(inp["expected_domain"], inp["supplied_domain"])
    if op == "resource_schema":
        return refs.require_resource_semantics(inp["role"], inp["schema"])
    if op == "decision_fields":
        # Supplied-name subset only, no synthetic complete F5 decision.
        return refs.inspect_declared_field_names("F5-DECISION", [inp["extra"]])
    raise AssertionError(op)


def observe_negative(case):
    try:
        dispatch_negative(copy.deepcopy(case))
    except codec.CodecRefusal as error:
        return {"category": error.category, "code": error.code}
    raise AssertionError(f"Unexpected acceptance: {case['case_id']}")


def compare_golden(cid, expected=None):
    raw, payload, frame, envelope = stored(cid) if expected is None else expected
    actual = codec.encode_source_bytes_candidate(raw)
    assert actual.payload == payload, "payload mismatch"
    assert actual.frame == frame, "frame mismatch"
    assert bytes.fromhex(actual.frame_digest) == bytes.fromhex(envelope["digest_hex"]), (
        "digest mismatch"
    )
    assert actual.candidate_envelope == envelope, "envelope mismatch"
    for field in envelope:
        assert actual.candidate_envelope[field] == envelope[field]
    assert codec.verify_source_frame(frame, envelope) == payload
    assert codec.verify_source_bytes_candidate(raw, payload, frame, envelope) == actual
    assert actual.diagnostic_only is True and actual.admission_eligible is False
    assert actual.trust == "NOT_TRUSTED_PIT_EVIDENCE"
    assert actual.source_authentication == "NOT_ESTABLISHED"
    assert actual.disposition == "INTEGRATED_PROVISIONAL"
    return actual


def relation_observation(cid):
    """Test-only controls. Metadata relations never invoke a runtime schedule issuer."""
    case = CASES[cid]
    if cid == "R-UNICODE":
        a, b = (bytes.fromhex(case["input"][k]) for k in ("nfc_hex", "nfd_hex"))
        assert a == b'"\xc3\xa9"' and b == b'"e\xcc\x81"' and a != b
        assert stored("B04")[0] == a[1:-1] and stored("B05")[0] == b[1:-1]
        return "DISTINCT_SCALAR_BYTES"
    if cid == "R-RAW-MUTATION":
        raw = stored(case["input"]["base"])[0]
        replacement = bytes.fromhex(case["input"]["replacement_hex"])
        old, new = literal_source(raw), literal_source(replacement)
        assert all(a != b for a, b in zip(old, new, strict=True))
        for body, expected in ((raw, old), (replacement, new)):
            actual = codec.encode_source_bytes_candidate(body)
            assert (actual.payload, actual.frame, bytes.fromhex(actual.frame_digest)) == expected
        return "DIFFERENT_PREIMAGE_AND_FRAME"
    if cid == "R-EVIDENCE-DIRECTION":
        actual = check_dependency_graph_symbolic(graph_adapter(case["input"]))
        assert actual.structure == "STRUCTURE_VALID_SYMBOLIC_ONLY"
        assert "REAL_GRAPH_CLOSURE_NOT_SUPPLIED" in actual.blockers
        return "ACYCLIC_SYMBOLIC_ONLY"
    declaration = json.loads((AUTHOR / "schedule_declaration.json").read_bytes())
    if cid == "R-FOUR-CUTOFFS":
        inp = case["input"]
        assert inp["cutoffs"] == [
            f"{d}T18:00:00+08:00" for d in ("2027-01-07", "2027-01-15", "2027-01-29", "2027-02-05")
        ]
        assert inp["selected"] == ["D1", "D2", "D2", "D3"]
        assert inp["a04"] == [140, 150, 150, 130]
        assert inp["a05"] == ["0.714286", "0.733333", "0.733333", "0.692308"]
        assert inp["no_session_week"] == "2027-W03"
        return "DIAGNOSTIC_DECLARATIONS_ONLY"
    if cid == "R-D06-CONSISTENT":
        for left, right in (
            ("original_input_refs", "expected_original_input_refs"),
            ("PF038", "expected_input_ref"),
            ("AF009", "invariant_policy_ref"),
            ("sequence_schedule_ref", "expected_schedule_ref"),
        ):
            assert declaration[left] == declaration[right]
        assert declaration["AF009"]["resource_schema"] == "HYPOTHETICAL_UNREVIEWED"
        return "NOT_SUPPLIED"
    assert cid == "R-D06-POLICY-CHANGE"
    changed = copy.deepcopy(declaration)
    changed["invariant_policy_ref"]["resource_version"] += "_CHANGED"
    assert changed["invariant_policy_ref"] != declaration["invariant_policy_ref"]
    assert changed != declaration  # dependency declaration, not issued ScheduleInput bytes
    return "DEPENDENCY_PREIMAGE_DIFFERS"


@pytest.mark.parametrize("cid", [f"B{i:02}" for i in range(1, 9)])
def test_golden(cid):
    compare_golden(cid)


@pytest.mark.parametrize("cid", sorted(CORE_IDS | REF_IDS | GRAPH_IDS))
def test_frozen_negative(cid):
    assert observe_negative(CASES[cid]) == CASES[cid]["expected"]


@pytest.mark.parametrize("cid", sorted(RELATION_IDS))
def test_relation_diagnostic(cid):
    assert relation_observation(cid) == CASES[cid]["expected"]


def test_harness_negative_control():
    raw, payload, frame, envelope = stored()
    original_digest = envelope["digest_hex"]
    envelope["digest_hex"] = "0" * 64
    with pytest.raises(AssertionError, match="digest mismatch"):
        compare_golden("B01", (raw, payload, frame, envelope))
    assert stored()[3]["digest_hex"] == original_digest
    with pytest.raises(AssertionError, match="frame mismatch"):
        compare_golden("B01", (raw, payload, frame[:-1] + b"x", stored()[3]))


@pytest.mark.parametrize("cid", [f"B{i:02}" for i in range(1, 9)])
def test_frozen_body_mutation(cid):
    raw, payload, frame, envelope = stored(cid)
    mutated = (bytes([raw[0] ^ 1]) + raw[1:]) if raw else b"\x00"
    with pytest.raises(codec.CodecRefusal) as caught:
        codec.verify_source_bytes_candidate(mutated, payload, frame, envelope)
    assert (caught.value.category, caught.value.code) == (
        "STRUCTURALLY_INVALID",
        "SOURCE_BODY_MISMATCH",
    )
    expected = literal_source(mutated)
    actual = codec.encode_source_bytes_candidate(mutated)
    assert (actual.payload, actual.frame, bytes.fromhex(actual.frame_digest)) == expected
    assert actual.payload != payload and actual.frame != frame


def test_unicode_opaque_and_newline_controls():
    assert stored("B04")[0] == "é".encode() != stored("B05")[0] == "e\u0301".encode()
    assert stored("B06")[0] == b"\xff"
    assert stored("B07")[0] == b"A\n"
