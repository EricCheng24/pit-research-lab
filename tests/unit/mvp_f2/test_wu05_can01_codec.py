"""Production core versus fixed independent bytes, never generated Golden.

Only CORE_IDS execute frozen negative inputs. The remaining ledger accounting is
scope bookkeeping, not production semantic conformance. No author helper imports.
"""

import ast
import copy
import json
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest

from pit_research_lab.mvp.if03 import canonical_codec as codec

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / "tests/fixtures/mvp_if03/oracle01_v0_1"
AUTHOR = ROOT / "tests/fixtures/mvp_if03/wu05_oracle01_v0_1"
FROZEN = json.loads((OLD / "FREEZE_MANIFEST.json").read_bytes())
CASES = json.loads((AUTHOR / "cases.json").read_bytes())["cases"]
BY_ID = {c["case_id"]: c for c in CASES}
# This explicit ID set is the scope claim, independent of author dispatch logic.
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
RESOURCE_IDS = {"N-UNREVIEWED-RESOURCE"}
LATER_IDS = set(
    """
N-AT-T1 N-T3-PLUS-ONE N-NAIVE N-FRACTIONAL N-LEAP-SECOND N-TICK-SWAPPED
N-TICK-DROPPED N-TICK-DUPLICATE N-TICK-FOREIGN N-W03-TICK N-B03-MIDNIGHT
N-REUSED-CONTEXT N-CYCLE N-HIDDEN-ATTEMPT N-DANGLING N-RESULT-ATTEMPT
N-ASSOCIATION-INSTANCE N-MISSING-RECEIPT N-NO-OUTCOME-STATE N-SAFE-AUDIT
N-SAFE-CALLBACK N-SAFE-GRANT N-SAFE-ATTEMPT N-SAFE-PRICE N-GRANT-MISSING
N-GRANT-REVOKED N-FOREIGN-PARENT N-STALE-PARENT N-DECISION-FUTURE-PRICE
N-DECISION-OUTCOME N-DECISION-LABEL N-IMMATURE-OUTCOME N-D06-ORIGINALS
N-D06-PF038 N-D06-AF009 N-D06-SCHEDULE
""".split()
)
A = codec.RecordSchema((("a", codec.TEXT),))
AB = codec.RecordSchema((("a", codec.TEXT), ("b", codec.TEXT)))


def stored(cid="B01"):
    folder = OLD / "positives" / cid
    with ZipFile(OLD / FROZEN["original_evidence"]["path"]) as archive:
        expected = json.loads(archive.read(f"vectors/{cid}/expected.json"))
    return (
        (folder / "raw_body.bin").read_bytes(),
        (folder / "canonical_payload.bin").read_bytes(),
        (folder / "frame.bin").read_bytes(),
        expected["expected_envelope_fields"],
    )


def uint(value):
    return {"type": "uint64", "value": str(value)}


def policy_shape():
    # Untrusted shape placeholder: no policy bytes/schema/issuance supplied.
    return {
        "resource_kind": "NUMERIC_POLICY",
        "resource_version": "NON_ISSUED",
        "resource_schema": "UNREVIEWED_SHAPE_ONLY",
        "content_ref": stored()[3],
    }


def decimal_fragment(scale="6"):
    return {
        "type": "decimal",
        "coefficient": {"type": "int64", "value": "-10"},
        "scale": uint(scale),
        "unit": "",
        "numeric_policy_ref": policy_shape(),
    }


def ratio_fragment(units="733333", text="0.733333", scale="6", unit="FRACTION"):
    return {
        "type": "fixed_ratio6",
        "scaled_units": uint(units),
        "decimal_text": text,
        "scale": uint(scale),
        "unit": unit,
        "numeric_policy_ref": policy_shape(),
    }


def refused(code, action, category="STRUCTURALLY_INVALID"):
    with pytest.raises(codec.CodecRefusal) as caught:
        action()
    assert (caught.value.category, caught.value.code) == (category, code)


@pytest.mark.parametrize("row", FROZEN["golden_positives"], ids=lambda r: r["vector_id"])
def test_frozen_golden_actual_raw_bytes(row):
    cid = row["vector_id"]
    raw, payload, frame, envelope = stored(cid)
    result = codec.encode_source_bytes_candidate(raw)
    assert result.payload == payload
    assert result.frame == frame
    assert result.frame_digest == row["expected_frame_digest_sha256"] == envelope["digest_hex"]
    assert result.candidate_envelope == envelope
    assert len(payload) == 187 and len(frame) == 281
    assert codec.verify_source_bytes_candidate(raw, payload, frame, envelope) == result
    with ZipFile(OLD / FROZEN["original_evidence"]["path"]) as archive:
        for artifact in row["artifacts"].values():
            direct = (OLD / artifact["fixture_path"]).read_bytes()
            assert direct == archive.read(artifact["source_zip_member"])
            assert sha256(direct).hexdigest() == artifact["file_sha256"]
            assert len(direct) == artifact["byte_length"]
    assert result.diagnostic_only is True and result.admission_eligible is False
    assert result.trust == "NOT_TRUSTED_PIT_EVIDENCE"
    assert result.source_authentication == "NOT_ESTABLISHED"
    assert result.disposition == "INTEGRATED_PROVISIONAL"


def test_anchors_unicode_and_opaque_raw():
    assert stored()[3]["digest_hex"] == (
        "687ddd2e1d12816f5e20e505af0bb9d6f149ddf218e7f37a6eb6dc13df3ea686"
    )
    assert stored("B04")[0] != stored("B05")[0]
    assert stored("B04")[2] != stored("B05")[2]
    assert stored("B06")[0] == b"\xff"
    assert codec.encode_canonical_record({"a": "é"}, A) == b'{"a":"\xc3\xa9"}'
    assert codec.encode_canonical_record({"a": "e\u0301"}, A) == b'{"a":"e\xcc\x81"}'
    assert codec.encode_canonical_record({"a": ""}, A) == b'{"a":""}'
    assert codec.encode_source_bytes_candidate(b"\x00").payload != stored()[1]


def frozen_mutation(case):
    """Apply ledger inputs to actual bytes; no author expected-value algorithm."""
    inp, op = case["input"], case["operation"]
    if op == "fragment":
        raw = bytes.fromhex(inp["hex"])
        codec.parse_canonical_record(raw, AB if case["case_id"] == "N-ORDER" else A)
    elif op == "integer":
        codec.validate_integer(inp["value"], signed=inp["signed"])
    elif op == "boolean":
        codec.validate_boolean(inp["value"])
    elif op == "decimal_scale":
        v = decimal_fragment()
        v["scale"] = inp["value"]
        codec.validate_numeric_fragment(v)
    elif op == "ratio":
        codec.validate_numeric_fragment(
            ratio_fragment(inp["scaled_units"], inp["decimal_text"], inp["scale"], inp["unit"])
        )
    elif op == "payload":
        raw = stored()[1]
        mutation = inp["mutation"]
        if mutation == "missing":
            raw = raw.replace(b'"body_byte_length":{"type":"uint64","value":"0"},', b"")
        elif mutation == "unknown":
            raw = raw[:-1] + b',"extra":"x"}'
        elif mutation == "own_envelope":
            raw = raw[:-1] + b',"digest_hex":"' + inp["own_digest_claim"].encode() + b'"}'
        else:
            pytest.fail(mutation)
        codec.parse_canonical_record(raw, codec.SOURCE_PAYLOAD_SCHEMA)
    elif op == "frame":
        _, _, frame, envelope = stored(inp["base"])
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
        elif mutation == "zero":
            frame = frame[:86] + bytes(8)
        elif mutation == "over_limit":
            frame = frame[:86] + (16_777_217).to_bytes(8, "big")
        elif mutation == "envelope_length":
            envelope["canonical_payload_byte_length"] = uint(281)
        elif mutation == "unframed_hash":
            envelope["digest_hex"] = sha256(stored()[1]).hexdigest()
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
        codec.verify_source_frame(frame, envelope)
    else:
        pytest.fail(f"No production core test for {case['case_id']}")


@pytest.mark.parametrize("cid", sorted(CORE_IDS))
def test_frozen_core_refusals(cid):
    case = BY_ID[cid]
    refused(case["expected"]["code"], lambda: frozen_mutation(case), case["expected"]["category"])


def test_coverage_accounting_does_not_promote_semantics():
    negatives = {c["case_id"] for c in CASES if c["case_id"].startswith("N-")}
    assert CORE_IDS.isdisjoint(LATER_IDS | RESOURCE_IDS)
    assert LATER_IDS.isdisjoint(RESOURCE_IDS)
    assert CORE_IDS | LATER_IDS | RESOURCE_IDS == negatives
    assert (len(CORE_IDS), len(LATER_IDS), len(RESOURCE_IDS), len(negatives)) == (43, 36, 1, 80)
    # 43 actual core refusals; 36 OUT_OF_SCOPE_CAN02/CAN03; one BLOCKED_RESOURCE_SCHEMA.
    assert {c["case_id"] for c in CASES if c["case_id"].startswith("P2-")} == {
        "P2-DEPTH-64",
        "P2-DEPTH-65",
    }  # DEFERRED_DEPTH_OWNER_DECISION, never positive.
    manifest = (
        ROOT / "tests/fixtures/mvp_if03/wu05_oracle02_scoped_freeze_v0_1/FREEZE_MANIFEST.json"
    )
    assert sha256(manifest.read_bytes()).hexdigest() == (
        "9099a4faede3c893ec57dc936d33741b1c6a1ac5b8b6f612d56219808d4a73b1"
    )
    m = json.loads(manifest.read_bytes())
    assert len(CASES) == 110
    assert m["counts"]["included_total"] == 94 and m["counts"]["excluded_total"] == 16


@pytest.mark.parametrize(
    "value",
    [
        "unknown",
        "",
        {},
        {"digest_hex": "unrelated"},
        {"domain_tag": "other", "digest_hex": "0" * 64},
    ],
)
def test_unrelated_reference_is_not_cycle(value):
    d = json.loads(stored()[1])
    d["reference"] = value
    raw = json.dumps(d, sort_keys=True, separators=(",", ":")).encode()
    refused("CLOSED_FIELDS", lambda: codec.parse_canonical_record(raw, codec.SOURCE_PAYLOAD_SCHEMA))


def test_recognizable_own_envelope():
    d = json.loads(stored()[1])
    d["reference"] = stored()[3]
    raw = json.dumps(d, sort_keys=True, separators=(",", ":")).encode()
    refused("REF_CYCLE", lambda: codec.parse_canonical_record(raw, codec.SOURCE_PAYLOAD_SCHEMA))


def test_canonical_controls_quotes_and_backslash():
    text = "".join(chr(i) for i in range(32)) + '"\\/é\u2028'
    expected = (
        b'{"a":"'
        + b"".join(f"\\u{i:04x}".encode() for i in range(32))
        + b'\\"\\\\/\xc3\xa9\xe2\x80\xa8"}'
    )
    assert codec.encode_canonical_record({"a": text}, A) == expected
    assert codec.parse_canonical_record(expected, A) == {"a": text}


@pytest.mark.parametrize(
    "raw",
    [b' {"a":""}', b'{"a":""}\n', b'{"a":"x"} ', b'{"a":"\\u0061"}', b'{"a":"\\uD83D\\uDE00"}'],
)
def test_additional_noncanonical_json(raw):
    refused("NONCANONICAL_BYTES", lambda: codec.parse_canonical_record(raw, A))


@pytest.mark.parametrize("key", ["é", "1a", "a-b", "", "a b"])
def test_ascii_keys_only(key):
    refused("ASCII_KEY", lambda: codec.encode_canonical_record({key: "x"}, A))


@pytest.mark.parametrize(
    "signed,text",
    [
        (True, "-9223372036854775808"),
        (True, "9223372036854775807"),
        (True, "0"),
        (False, "0"),
        (False, "18446744073709551615"),
    ],
)
def test_integer_bounds(signed, text):
    tagged = {"type": "int64" if signed else "uint64", "value": text}
    assert codec.validate_integer(tagged, signed=signed) == int(text)
    s = codec.RecordSchema((("a", codec.IntegerSchema(signed=signed)),))
    assert codec.parse_canonical_record(codec.encode_canonical_record({"a": tagged}, s), s) == {
        "a": tagged
    }


@pytest.mark.parametrize("text", ["", " 1", "1 ", "١", "00", "-01", "+0", "1.0", "1E2"])
def test_more_integer_spellings(text):
    refused(
        "INTEGER_SPELLING",
        lambda: codec.validate_integer({"type": "int64", "value": text}, signed=True),
    )


def test_wrong_integer_tag_overflow_and_boolean():
    refused("INTEGER_TAG", lambda: codec.validate_integer({"type": "int64", "value": "0"}))
    refused(
        "INTEGER_RANGE",
        lambda: codec.validate_integer(
            {"type": "int64", "value": "-9223372036854775809"}, signed=True
        ),
    )
    refused("INTEGER_RANGE", lambda: codec.validate_integer(uint("9" * 5000)))
    s = codec.RecordSchema((("a", codec.BooleanSchema()),))
    assert codec.encode_canonical_record({"a": True}, s) == b'{"a":true}'
    assert codec.encode_canonical_record({"a": False}, s) == b'{"a":false}'
    for value in (0, 1, "true", None):
        refused("BOOLEAN_TYPE", lambda value=value: codec.validate_boolean(value))
    for value in (True, 1, 1.0):
        refused(
            "INTEGER_TEXT",
            lambda value=value: codec.validate_integer({"type": "uint64", "value": value}),
        )
    for value in (1, 0.1, float("inf"), float("nan"), None):
        with pytest.raises(codec.CodecRefusal):
            codec.encode_canonical_record({"a": value}, A)


@pytest.mark.parametrize(
    "value",
    [
        decimal_fragment("0"),
        decimal_fragment("18"),
        ratio_fragment("0", "0.000000"),
        ratio_fragment("1000000", "1.000000"),
        ratio_fragment(),
    ],
)
def test_numeric_fragments_are_structural_and_policy_blocked(value):
    check = codec.validate_numeric_fragment(value)
    assert check.structure == "STRUCTURE_VALID_FRAGMENT_ONLY"
    assert check.semantics == "BLOCKED_NOT_SUPPLIED"


@pytest.mark.parametrize(
    "changes",
    [
        {"scaled_units": uint(1000001)},
        {"scale": uint(5)},
        {"decimal_text": "0.7333330"},
        {"decimal_text": "00.733333"},
        {"decimal_text": "7.33333e-1"},
        {"decimal_text": "+0.733333"},
        {"decimal_text": "0.733334"},
    ],
)
def test_ratio_structural_mismatch(changes):
    value = ratio_fragment()
    value.update(changes)
    refused("RATIO_MISMATCH", lambda: codec.validate_numeric_fragment(value))


def test_numeric_missing_policy_and_closed_shape():
    for base in (decimal_fragment(), ratio_fragment()):
        v = copy.deepcopy(base)
        del v["numeric_policy_ref"]
        refused("CLOSED_FIELDS", lambda v=v: codec.validate_numeric_fragment(v))
        v = copy.deepcopy(base)
        v["numeric_policy_ref"]["resource_kind"] = "TIMEZONE_RULES"
        refused("LITERAL", lambda v=v: codec.validate_numeric_fragment(v), "UNSUPPORTED_SCHEMA")
    v = decimal_fragment()
    v["coefficient"] = {"type": "int64", "value": "-0"}
    refused("INTEGER_SPELLING", lambda v=v: codec.validate_numeric_fragment(v))


def test_order_cardinality_and_utf8_byte_bounds():
    s = codec.RecordSchema((("a", codec.ArraySchema(codec.TEXT, 1, 2)),))
    assert codec.encode_canonical_record({"a": ["b", "a"]}, s) == b'{"a":["b","a"]}'
    for entries in ([], ["a", "b", "c"]):
        refused(
            "ARRAY_BOUND", lambda entries=entries: codec.encode_canonical_record({"a": entries}, s)
        )
    codec.encode_canonical_record({"a": "é" * 32768}, A)
    refused("TEXT_BOUND", lambda: codec.encode_canonical_record({"a": "é" * 32769}, A))
    refused("SURROGATE", lambda: codec.encode_canonical_record({"a": "\ud800"}, A))
    s = codec.RecordSchema((("a", codec.ArraySchema(codec.TEXT, 0, 4096)),))
    codec.encode_canonical_record({"a": [""] * 4096}, s)
    refused("ARRAY_BOUND", lambda: codec.encode_canonical_record({"a": [""] * 4097}, s))
    refused(
        "ARRAY_BOUND", lambda: codec.parse_canonical_record(b'{"a":[' + b'"",' * 4096 + b'""]}', s)
    )


@pytest.mark.parametrize("offset", [0, 51, 86])
@pytest.mark.parametrize("size", [0, 2**64 - 1, 2**63])
def test_each_untrusted_length_prefix_before_slice(offset, size):
    _, _, frame, env = stored()
    damaged = frame[:offset] + size.to_bytes(8, "big") + frame[offset + 8 :]
    refused("FRAME_LENGTH", lambda: codec.verify_source_frame(damaged, env))


@pytest.mark.parametrize("length", [0, 1, 7, 8, 50, 51, 58, 85, 86, 93, 94, 280])
def test_truncated_frame(length):
    _, _, frame, env = stored()
    refused("FRAME_TRUNCATED", lambda: codec.verify_source_frame(frame[:length], env))


@pytest.mark.parametrize("digest", ["A" * 64, "g" * 64, "a" * 63, "a" * 65, "", "é" * 64])
def test_hex64_envelope(digest):
    _, _, frame, env = stored()
    env["digest_hex"] = digest
    refused("HEX64", lambda: codec.verify_source_frame(frame, env))


def test_independent_body_payload_frame_and_envelope_mutations():
    raw, payload, frame, env = stored()
    refused(
        "SOURCE_BODY_MISMATCH",
        lambda: codec.verify_source_bytes_candidate(raw + b"x", payload, frame, env),
    )
    refused(
        "PAYLOAD_MISMATCH",
        lambda: codec.verify_source_bytes_candidate(raw, payload + b"x", frame, env),
    )
    altered = frame[:-1] + b"]"
    with pytest.raises(codec.CodecRefusal):
        codec.verify_source_bytes_candidate(raw, payload, altered, env)
    for field in ("locator", "unknown"):
        changed = dict(env, **{field: "x"})
        refused("CLOSED_FIELDS", lambda changed=changed: codec.verify_source_frame(frame, changed))
    for field in env:
        changed = env.copy()
        del changed[field]
        refused("CLOSED_FIELDS", lambda changed=changed: codec.verify_source_frame(frame, changed))
    env["digest_hex"] = sha256(raw).hexdigest()
    refused("DIGEST_MISMATCH", lambda: codec.verify_source_frame(frame, env))
    env = stored()[3]
    env["canonical_payload_byte_length"] = uint(0)
    refused("PAYLOAD_LENGTH", lambda: codec.verify_source_frame(frame, env))


def test_raw_relation_r_raw_mutation():
    case = BY_ID["R-RAW-MUTATION"]["input"]
    old = codec.encode_source_bytes_candidate(stored(case["base"])[0])
    new = codec.encode_source_bytes_candidate(bytes.fromhex(case["replacement_hex"]))
    assert (
        old.payload != new.payload
        and old.frame != new.frame
        and old.frame_digest != new.frame_digest
    )


@pytest.mark.parametrize("name,version", list(codec.DOMAINS.items())[1:])
def test_nine_registered_domains_remain_blocked(name, version):
    refused(
        "UNSUPPORTED_SEMANTIC_SCHEMA",
        lambda: codec.require_candidate_domain(f"PITLAB/ACADEMIC/{name}/candidate-v0.1", version),
        "NOT_SUPPLIED",
    )
    _, payload, _, env = stored()
    domain = f"PITLAB/ACADEMIC/{name}/candidate-v0.1".encode()
    frame = b"".join(len(p).to_bytes(8, "big") + p for p in (domain, version.encode(), payload))
    refused(
        "UNSUPPORTED_SEMANTIC_SCHEMA", lambda: codec.verify_source_frame(frame, env), "NOT_SUPPLIED"
    )


@pytest.mark.parametrize(
    "domain,version",
    [
        (codec.SOURCE_DOMAIN, "source-bytes-candidate-v9.9"),
        (codec.SOURCE_DOMAIN.replace("v0.1", "v0.2"), codec.SOURCE_SCHEMA_VERSION),
        ("D", "S"),
        ("PITLAB/ACADEMIC/UNKNOWN/candidate-v0.1", "unknown-candidate-v0.1"),
    ],
)
def test_no_version_fallback(domain, version):
    refused(
        "DOMAIN_SCHEMA",
        lambda: codec.require_candidate_domain(domain, version),
        "UNSUPPORTED_SCHEMA",
    )


@pytest.mark.parametrize("depth", [64, 65, 2000])
def test_depth_boundary_explicitly_unresolved_and_safe(depth):
    raw = b'{"a":' * depth + b'"x"' + b"}" * depth
    refused(
        "PENDING_OWNER_BOUNDARY_DECISION",
        lambda: codec.parse_canonical_record(raw, A),
        "CONTRACT_BOUNDARY_UNRESOLVED",
    )
    value = "x"
    for _ in range(depth):
        value = {"a": value}
    refused(
        "PENDING_OWNER_BOUNDARY_DECISION",
        lambda: codec.encode_canonical_record(value, A),
        "CONTRACT_BOUNDARY_UNRESOLVED",
    )


def test_payload_and_resource_budgets():
    refused(
        "PAYLOAD_BOUND", lambda: codec.parse_canonical_record(b" " * (codec.MAX_PAYLOAD + 1), A)
    )
    value = {"a": ["x" * 65536] * 257}
    s = codec.RecordSchema((("a", codec.ArraySchema(codec.TEXT, 0, 4096)),))
    refused("PAYLOAD_BOUND", lambda: codec.encode_canonical_record(value, s))
    # Many small arrays would amplify JSON decoding: pre-scan refuses first.
    raw = b'{"a":[' + b"[" + b'"",' * 4095 + b'""]' + (b",[]" * 4000) + b"]}"
    with pytest.raises(codec.CodecRefusal):
        codec.parse_canonical_record(raw, A)
    v = {}
    v["a"] = v
    refused("REF_CYCLE", lambda: codec.encode_canonical_record(v, A))


def test_immutable_candidate_and_no_runtime_imports():
    candidate = codec.encode_source_bytes_candidate(b"")
    with pytest.raises(FrozenInstanceError):
        candidate.frame = b"x"
    detached = candidate.candidate_envelope
    detached["canonical_payload_byte_length"]["value"] = "281"
    assert candidate.candidate_envelope == stored()[3]
    module = Path(codec.__file__).read_text()
    tree = ast.parse(module)
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(n.name.split(".")[0] for n in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or "").split(".")[0])
    assert roots <= {"json", "re", "collections", "dataclasses", "hashlib", "types", "typing"}
    assert set(codec.DOMAINS) == {
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
    }


@pytest.mark.parametrize("offset", [0, 51, 86])
def test_each_prefix_wrong_endian_and_in_bound_truncation(offset):
    _, _, frame, env = stored()
    swapped = frame[:offset] + frame[offset : offset + 8][::-1] + frame[offset + 8 :]
    refused("FRAME_LENGTH", lambda: codec.verify_source_frame(swapped, env))
    # Prefix stays in bounds, but its section extends past the supplied bytes.
    prefix = (128 if offset < 86 else 188).to_bytes(8, "big")
    damaged = frame[:offset] + prefix + frame[offset + 8 : offset + 9]
    refused("FRAME_TRUNCATED", lambda: codec.verify_source_frame(damaged, env))


def test_before_decode_and_traversal_resource_budgets():
    # All individual arrays are within bounds; their combined tokens exceed the
    # local defensive budget before json.loads can amplify the representation.
    member = b"[" + b'"",' * 4095 + b'""]'
    raw = b'{"a":[' + b",".join([member] * 100) + b"]}"
    refused("RESOURCE_BUDGET", lambda: codec.parse_canonical_record(raw, A))
    value = {"a": [[""] * 4096] * 100}
    refused("RESOURCE_BUDGET", lambda: codec.encode_canonical_record(value, A))


def test_closed_fragment_and_explicit_schema_required():
    refused("CLOSED_FIELDS", lambda: codec.encode_canonical_record({}, A))
    refused("CLOSED_FIELDS", lambda: codec.encode_canonical_record({"a": "", "b": ""}, A))
    refused(
        "EXPLICIT_SCHEMA_REQUIRED",
        lambda: codec.encode_canonical_record({"a": ""}, None),
        "UNSUPPORTED_SCHEMA",
    )
    invalid = codec.RecordSchema((("a", codec.TEXT), ("a", codec.TEXT)))
    refused(
        "SCHEMA_FIELDS",
        lambda: codec.encode_canonical_record({"a": ""}, invalid),
        "UNSUPPORTED_SCHEMA",
    )
    invalid = codec.RecordSchema((("a", codec.ArraySchema(codec.TEXT, 0, 4097)),))
    refused(
        "SCHEMA_BOUND",
        lambda: codec.encode_canonical_record({"a": []}, invalid),
        "UNSUPPORTED_SCHEMA",
    )


@pytest.mark.parametrize("value", ["raw text", bytearray(b"raw"), memoryview(b"raw"), None])
def test_raw_body_requires_actual_bytes_without_coercion(value):
    refused("BYTES_REQUIRED", lambda: codec.encode_source_bytes_candidate(value))


def test_decimal_scale_preserved_without_floats():
    a, b = decimal_fragment("0"), decimal_fragment("1")
    a["coefficient"] = {"type": "int64", "value": "0"}
    b["coefficient"] = {"type": "int64", "value": "0"}
    assert codec.validate_numeric_fragment(a).semantics == "BLOCKED_NOT_SUPPLIED"
    assert codec.validate_numeric_fragment(b).semantics == "BLOCKED_NOT_SUPPLIED"
    # Validation neither normalizes scale nor recomputes the supplied coefficient.
    assert a["scale"] == uint(0) and b["scale"] == uint(1)
    b["scale"] = uint(19)
    refused("DECIMAL_SCALE", lambda: codec.validate_numeric_fragment(b))
    b["scale"] = {"type": "uint64", "value": 6.0}
    refused("BARE_NUMBER", lambda: codec.validate_numeric_fragment(b))
