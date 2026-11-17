"""Synthetic bounded adversaries, not authority or complete domain verification.

Seeds: 305031 (maps/bodies), 305032 (graphs). At most 48 maps/bodies,
24 nodes per seeded graph, 4097 nodes/20480 edges in explicit budget controls.
Exact frozen single-fault diagnostics live in conformance; multi-fault controls
require CodecRefusal without inventing a global failure ordering.
"""

import copy
import itertools
import json
import random
from collections import deque
from dataclasses import asdict
from hashlib import sha256

import pytest
from test_wu05_can03_conformance import decimal, ratio, uint
from wu05_can03_expected import PROFILE, literal_source, stored

from pit_research_lab.mvp.if03 import canonical_codec as codec
from pit_research_lab.mvp.if03 import typed_references as refs
from pit_research_lab.mvp.if03.dependency_graph import (
    SymbolicEdge as Edge,
)
from pit_research_lab.mvp.if03.dependency_graph import (
    SymbolicNode as Node,
)
from pit_research_lab.mvp.if03.dependency_graph import (
    check_dependency_graph_symbolic as check,
)

MAP_SEED = 305031
GRAPH_SEED = 305032
A = codec.RecordSchema((("a", codec.TEXT),))
FLAGS = {
    "diagnostic_only": True,
    "admission_eligible": False,
    "trust": "NOT_TRUSTED_PIT_EVIDENCE",
    "source_authentication": "NOT_ESTABLISHED",
    "disposition": "INTEGRATED_PROVISIONAL",
}


def bounded(result):
    for name, expected in FLAGS.items():
        assert getattr(result, name) == expected
        assert type(getattr(result, name)) is type(expected)
    if hasattr(result, "semantics"):
        assert result.semantics == "BLOCKED_NOT_SUPPLIED" and result.blockers


def refusal(action, code=None, category=None):
    with pytest.raises(codec.CodecRefusal) as caught:
        action()
    if code is not None:
        assert caught.value.code == code
    if category is not None:
        assert caught.value.category == category
    return caught.value


def parent(domain="RESULT", digest="b" * 64):
    # Explicit fake claim; no bytes, parent existence, revision or rights supplied.
    return {
        "domain_tag": f"PITLAB/ACADEMIC/{domain}/candidate-v0.1",
        "object_schema_version": domain.lower() + "-candidate-v0.1",
        "canonical_profile_version": PROFILE,
        "digest_algorithm": "SHA-256",
        "canonical_payload_byte_length": uint(187),
        "digest_hex": digest,
    }


def resource(role="PROTOCOL"):
    return {
        "resource_kind": role,
        "resource_version": "NON_ISSUED",
        "resource_schema": "UNREVIEWED_SHAPE_ONLY",
        "content_ref": stored()[3],
    }


@pytest.mark.parametrize("index", range(48))
def test_seeded_map_and_source_metamorphisms(index):
    rng = random.Random(MAP_SEED + index)
    pairs = [(f"key_{i}", "".join(rng.choices("abc/é中", k=12))) for i in range(8)]
    schema = codec.RecordSchema(tuple((k, codec.TEXT) for k, _ in pairs))
    expected = json.dumps(
        dict(pairs), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    rng.shuffle(pairs)
    assert codec.encode_canonical_record(dict(pairs), schema) == expected
    assert codec.parse_canonical_record(expected, schema) == dict(pairs)
    # Duplicate declarations/JSON pairs are refused, never silently deduplicated.
    duplicate = codec.RecordSchema(tuple((k, codec.TEXT) for k, _ in pairs + pairs[:1]))
    refusal(lambda: codec.encode_canonical_record(dict(pairs), duplicate), "SCHEMA_FIELDS")
    body = rng.randbytes(rng.randrange(1, 129))
    changed = body[:-1] + bytes([body[-1] ^ 1])
    old, new = literal_source(body), literal_source(changed)
    assert all(a != b for a, b in zip(old, new, strict=True))  # SHA-256 assumption
    for raw, expected_source in ((body, old), (changed, new)):
        actual = codec.encode_source_bytes_candidate(raw)
        assert (actual.payload, actual.frame, bytes.fromhex(actual.frame_digest)) == expected_source
        assert codec.encode_source_bytes_candidate(raw) == actual
        bounded(actual)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":"x","a":"y"}',
        b"{}",
        b'{"a":"x","extra":"y"}',
        b'\xef\xbb\xbf{"a":"x"}',
        b'{ "a":"x"}',
        b'{"a":"x"}\n',
        b'{"a":"\\n"}',
        b'{"a":"\\u000A"}',
        b'{"a":"\\/"}',
        b'{"a":"\\u00e9"}',
        b'{"a":"\xff"}',
        b'{"a":"\xc0\xaf"}',
        b'{"a":"\xed\xa0\x80"}',
        b'{"a":"\\udfff"}',
        b'{"a":null}',
        b'{"a":0}',
        b'{"a":1.2}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b'{"a":-Infinity}',
    ],
)
def test_canonical_grammar_refuses(raw):
    refusal(lambda: codec.parse_canonical_record(raw, A))


def test_all_controls_and_scalar_sequences_and_arrays():
    text = "".join(map(chr, range(32))) + '/\\"é中😀'
    expected = b'{"a":"' + b"".join(f"\\u{i:04x}".encode() for i in range(32))
    expected += b'/\\\\\\"' + "é中😀".encode() + b'"}'
    assert codec.encode_canonical_record({"a": text}, A) == expected
    assert codec.parse_canonical_record(expected, A) == {"a": text}
    composed = codec.encode_canonical_record({"a": "é"}, A)
    decomposed = codec.encode_canonical_record({"a": "e\u0301"}, A)
    assert composed == b'{"a":"\xc3\xa9"}' != decomposed == b'{"a":"e\xcc\x81"}'
    schema = codec.RecordSchema((("a", codec.ArraySchema(codec.TEXT, 0, 16)),))
    assert codec.encode_canonical_record({"a": ["b", "a"]}, schema) == b'{"a":["b","a"]}'
    assert codec.encode_canonical_record({"a": ["a", "b"]}, schema) != b'{"a":["b","a"]}'
    for value in ("\ud800", "x" * 65537):
        refusal(lambda value=value: codec.encode_canonical_record({"a": value}, A))
    for bad in ("a-b", "é", "1a"):
        refusal(lambda bad=bad: codec.encode_canonical_record({bad: "x"}, A), "ASCII_KEY")


@pytest.mark.parametrize(
    "signed,valid",
    [
        (True, "-9223372036854775808"),
        (True, "9223372036854775807"),
        (False, "18446744073709551615"),
        (False, "0"),
    ],
)
def test_integer_limits(signed, valid):
    value = {"type": "int64" if signed else "uint64", "value": valid}
    assert codec.validate_integer(value, signed=signed) == int(valid)


@pytest.mark.parametrize("text", ["+1", "01", "-0", "1e2", "1.0", " 1", "١", ""])
@pytest.mark.parametrize("signed", [False, True])
def test_integer_spelling(text, signed):
    refusal(
        lambda: codec.validate_integer(
            {"type": "int64" if signed else "uint64", "value": text}, signed=signed
        )
    )


def test_numeric_boundaries_no_coercion_or_policy_approval():
    for text, signed in (
        ("9223372036854775808", True),
        ("-9223372036854775809", True),
        ("18446744073709551616", False),
        ("-1", False),
    ):
        refusal(
            lambda text=text, signed=signed: codec.validate_integer(
                {"type": "int64" if signed else "uint64", "value": text}, signed=signed
            )
        )
    for value in (True, 1, 1.0, None, float("nan"), float("inf")):
        refusal(lambda value=value: codec.validate_integer({"type": "uint64", "value": value}))
    for value in (0, 1, "true", None):
        refusal(lambda value=value: codec.validate_boolean(value))
    assert codec.validate_boolean(True) is True and codec.validate_boolean(False) is False
    for scale in (0, 1, 18):
        value = decimal(scale)
        before = copy.deepcopy(value)
        result = codec.validate_numeric_fragment(value)
        assert result.semantics == "BLOCKED_NOT_SUPPLIED" and value == before
    refusal(lambda: codec.validate_numeric_fragment(decimal(19)), "DECIMAL_SCALE")
    for units in (0, 1, 733333, 1000000):
        text = f"{units // 1000000}.{units % 1000000:06d}"
        assert (
            codec.validate_numeric_fragment(ratio(units, text)).semantics == "BLOCKED_NOT_SUPPLIED"
        )
        refusal(
            lambda units=units: codec.validate_numeric_fragment(ratio(units, "0.123456")),
            "RATIO_MISMATCH",
        )
    refusal(lambda: codec.validate_numeric_fragment(ratio(scale=5)), "RATIO_MISMATCH")
    refusal(lambda: codec.validate_numeric_fragment(ratio(units=1000001)), "RATIO_MISMATCH")


@pytest.mark.parametrize("offset", [0, 51, 86])
@pytest.mark.parametrize("size", [0, 2**64 - 1, 2**63])
def test_lp64be_bounds(offset, size):
    _, _, frame, envelope = stored()
    broken = frame[:offset] + size.to_bytes(8, "big") + frame[offset + 8 :]
    refusal(lambda: codec.verify_source_frame(broken, envelope), "FRAME_LENGTH")


@pytest.mark.parametrize("offset", [0, 51, 86])
def test_each_lp_section_endian_and_missing_bytes(offset):
    _, _, frame, envelope = stored()
    broken = frame[:offset] + frame[offset : offset + 8][::-1] + frame[offset + 8 :]
    refusal(lambda: codec.verify_source_frame(broken, envelope), "FRAME_LENGTH")
    for end in (offset, offset + 7, offset + 8, len(frame) - 1):
        refusal(lambda end=end: codec.verify_source_frame(frame[:end], envelope))


@pytest.mark.parametrize("order", list(itertools.permutations(range(3)))[1:])
def test_frame_section_order(order):
    _, _, frame, envelope = stored()
    sections = (frame[:51], frame[51:86], frame[86:])
    refusal(lambda: codec.verify_source_frame(b"".join(sections[i] for i in order), envelope))


@pytest.mark.parametrize(
    "field",
    [
        "domain_tag",
        "object_schema_version",
        "canonical_profile_version",
        "digest_algorithm",
        "digest_hex",
        "canonical_payload_byte_length",
    ],
)
def test_envelope_and_direct_constructor_hardening(field):
    _, payload, frame, envelope = stored()
    envelope[field] = uint(281) if field == "canonical_payload_byte_length" else "x" * 64
    refusal(lambda: codec.verify_source_frame(frame, envelope))
    refusal(lambda: codec.SourceBytesCandidate(payload, frame, "0" * 64))
    refusal(
        lambda: codec.SourceBytesCandidate(payload, frame + b"x", sha256(frame + b"x").hexdigest())
    )
    refusal(lambda: codec.SourceBytesCandidate(b"{}", frame, sha256(frame).hexdigest()))


def test_frame_body_profile_and_unknown_vs_self_envelope():
    raw, payload, frame, envelope = stored()
    refusal(lambda: codec.verify_source_frame(frame + b"x", envelope), "FRAME_TRAILING")
    refusal(
        lambda: codec.verify_source_bytes_candidate(raw + b"x", payload, frame, envelope),
        "SOURCE_BODY_MISMATCH",
    )
    refusal(
        lambda: codec.verify_source_bytes_candidate(raw, payload + b"x", frame, envelope),
        "PAYLOAD_MISMATCH",
    )
    for old, new in (
        (b"SOURCE-BYTES", b"F5-DECISION"),
        (b"source-bytes-candidate-v0.1", b"source-bytes-candidate-v0.2"),
        (PROFILE.encode(), b"typed-json-candidate-v0.2"),
    ):
        changed = frame.replace(old, new)
        refusal(
            lambda changed=changed, old=old, new=new: codec.SourceBytesCandidate(
                payload.replace(old, new), changed, sha256(changed).hexdigest()
            )
        )
    for value, code in (
        ("unrelated", "CLOSED_FIELDS"),
        ({"digest_hex": "x"}, "CLOSED_FIELDS"),
        (envelope, "REF_CYCLE"),
    ):
        changed = dict(json.loads(payload), reference=value)
        encoded = json.dumps(changed, sort_keys=True, separators=(",", ":")).encode()
        refusal(
            lambda encoded=encoded: codec.parse_canonical_record(
                encoded, codec.SOURCE_PAYLOAD_SCHEMA
            ),
            code,
        )


@pytest.mark.parametrize("domain", ["RESULT", "F2-QUALIFICATION", "F3-EXPERIMENT", "F5-DECISION"])
def test_fake_parent_and_real_source_cannot_promote(domain):
    source = codec.encode_source_bytes_candidate(stored("B06")[0])
    fake = parent(domain, source.frame_digest)
    shape = refs.validate_parent_ref_shape(fake, domain)
    bounded(source)
    bounded(shape)
    assert shape.structure == "STRUCTURAL_ONLY" and shape.resolution == "NOT_SUPPLIED"
    assert "PARENT_EXISTENCE_FRESHNESS_RIGHTS_NOT_SUPPLIED" in shape.blockers
    refusal(
        lambda: refs.require_resolved_parent(fake, domain),
        "PARENT_EXISTENCE_FRESHNESS_RIGHTS_NOT_SUPPLIED",
        "NOT_SUPPLIED",
    )
    refusal(
        lambda: codec.require_candidate_domain(fake["domain_tag"], fake["object_schema_version"]),
        "UNSUPPORTED_SEMANTIC_SCHEMA",
        "NOT_SUPPLIED",
    )
    wrapped = resource()
    wrapped["content_ref"] = source.candidate_envelope
    bounded(refs.validate_resource_ref_shape(wrapped, ("PROTOCOL",)))
    refusal(
        lambda: refs.require_resource_semantics("PROTOCOL", wrapped["resource_schema"]),
        "REF_UNAPPROVED_RESOURCE_SCHEMA",
        "UNSUPPORTED_SCHEMA",
    )
    wrapped["content_ref"] = fake
    refusal(lambda: refs.validate_resource_ref_shape(wrapped, ("PROTOCOL",)), "FOREIGN_PARENT")
    graph = check((Node("body", "SOURCE-BYTES"),))
    bounded(graph)
    assert "REAL_GRAPH_CLOSURE_NOT_SUPPLIED" in graph.blockers


@pytest.mark.parametrize("field", tuple(parent()))
def test_parent_closed_six_fields(field):
    fake = parent()
    del fake[field]
    refusal(lambda: refs.validate_parent_ref_shape(fake, "RESULT"), "CLOSED_FIELDS")
    fake = parent()
    fake["extra"] = "NO_AUTHORITY"
    refusal(lambda: refs.validate_parent_ref_shape(fake, "RESULT"), "CLOSED_FIELDS")


def test_reference_negotiation_resource_role_and_union_mutations():
    for key in (
        "domain_tag",
        "object_schema_version",
        "canonical_profile_version",
        "digest_algorithm",
    ):
        fake = parent()
        fake[key] = "UNSUPPORTED"
        refusal(lambda fake=fake: refs.validate_parent_ref_shape(fake, "RESULT"))
    fake = parent(digest="0" * 64)
    bounded(refs.validate_parent_ref_shape(fake, "RESULT"))  # well-shaped is still untrusted
    wrong = resource("PRICE")
    refusal(lambda: refs.validate_resource_ref_shape(wrong, ("PROTOCOL",)))
    sequence = {
        "kind": "SEQUENCE",
        "temporal_binding_set_ref": parent("TEMPORAL-SEQUENCE"),
        "association_contract_version": "experiment-sequence-binding-candidate-v0.1",
    }
    bounded(refs.validate_experiment_input_shape(sequence))
    for mutation in (
        {"association_instance_ref": resource("EXPERIMENT_ASSOCIATION")},
        {"observation_ref": parent("F2-OBSERVATION")},
        {"kind": "SINGLE_CUTOFF"},
        {"association_contract_version": "v2"},
    ):
        changed = dict(sequence, **mutation)
        refusal(lambda changed=changed: refs.validate_experiment_input_shape(changed))
    for name in ("future_price", "outcome_ref", "label_maturity"):
        refusal(
            lambda name=name: refs.inspect_declared_field_names("F5-DECISION", [name]),
            "DECISION_FIELDS",
        )


def test_provenance_parent_union_and_available_withheld_are_shape_only():
    evidence = {
        "canonical_profile_version": PROFILE,
        "subject_ref": parent("RESULT"),
        "semantic_audit_ref": resource("SEMANTIC_EVIDENCE"),
        "source_code_protocol_refs": [parent("F3-RUN-ATTEMPT"), resource("AUTHOR_RECORD")],
        "limitations": [],
        "evidence_claim": "UNVERIFIED",
    }
    bounded(refs.inspect_domain_structure("EVIDENCE", evidence))
    evidence["source_code_protocol_refs"] = [parent("EVIDENCE")]
    refusal(lambda: refs.inspect_domain_structure("EVIDENCE", evidence), "FOREIGN_PARENT")
    attempt = {
        "canonical_profile_version": PROFILE,
        "attempt_id": "NON_ISSUED",
        "experiment_ref": parent("F3-EXPERIMENT"),
        "operation_receipt_ref": resource("NATIVE_RECEIPT"),
        "result_ref": {"type": "available", "ref": parent("RESULT")},
    }
    bounded(refs.inspect_domain_structure("F3-RUN-ATTEMPT", attempt))
    attempt["result_ref"]["type"] = "withheld"
    refusal(lambda: refs.inspect_domain_structure("F3-RUN-ATTEMPT", attempt))
    # Full sequence grammar for a single diagnostic member, never an issued schedule.
    member = {
        "tick": {
            "tick_id": "declared",
            "tick_order": uint(1),
            "context_ref": "NON_ISSUED",
            "decision_cutoff": {
                "source_text": "2027-01-07T18:00:00+08:00",
                "timezone_name": "Asia/Taipei",
                "offset": "+08:00",
                "precision": "SECOND",
                "origin_ref": resource("ORIGIN"),
                "utc_comparison": "2027-01-07T10:00:00Z",
                "timezone_rules_ref": resource("TIMEZONE_RULES"),
            },
        },
        "binding_ref": resource("SEMANTIC_TRACE"),
        "qualification_ref": parent("F2-QUALIFICATION"),
        "observation_ref": {
            "type": "withheld",
            "owner": "F2",
            "reason": "NOT_SUPPLIED",
            "policy_ref": resource("OBSERVATION_RELEASE_POLICY"),
        },
        "scope": {
            "data_mode": "SYNTHETIC_GOLDEN",
            "pit_status": "UNRESOLVED",
            "evidence_class": "UNVERIFIED",
            "scope_flags": FLAGS.copy(),
        },
    }
    sequence = {
        "canonical_profile_version": PROFILE,
        "configuration_ref": resource("TEMPORAL_CONFIGURATION"),
        "schedule_ref": resource("DECISION_SCHEDULE"),
        "bindings": [member],
        "annotations": [],
        "release_state": "UNINSPECTED",
        "provenance_ref": resource("SEMANTIC_TRACE"),
        "scope": "UNINSPECTED",
    }
    bounded(refs.inspect_domain_structure("TEMPORAL-SEQUENCE", sequence))
    member["observation_ref"]["ref"] = parent("F2-OBSERVATION")
    refusal(lambda: refs.inspect_domain_structure("TEMPORAL-SEQUENCE", sequence), "CLOSED_FIELDS")


def kahn_acyclic(adjacency):
    """Separate indegree/queue algorithm; no production DFS, ancestry or path rules."""
    indegree = dict.fromkeys(adjacency, 0)
    for targets in adjacency.values():
        for target in targets:
            assert target in indegree
            indegree[target] += 1
    queue = deque(name for name, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        name = queue.popleft()
        visited += 1
        for target in adjacency[name]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    return visited == len(adjacency)


@pytest.mark.parametrize("index", range(48))
def test_seeded_graph_against_independent_kahn(index):
    rng = random.Random(GRAPH_SEED + index)
    count = rng.randrange(2, 25)
    adjacency = {
        str(i): [str(j) for j in range(i + 1, count) if rng.random() < 0.18] for i in range(count)
    }
    if index % 2:
        adjacency["0"].append(str(count - 1))
        adjacency[str(count - 1)].append("0")
    expected = kahn_acyclic(adjacency)
    nodes = [Node(k, "SEMANTIC_RESOURCE", tuple(Edge(p) for p in v)) for k, v in adjacency.items()]
    for _ in range(2):
        rng.shuffle(nodes)
        if expected:
            result = check(tuple(nodes))
            bounded(result)
            assert result.node_count == count and result.edge_count == sum(
                map(len, adjacency.values())
            )
        else:
            refusal(lambda: check(tuple(nodes)), "REF_CYCLE")


@pytest.mark.parametrize(
    "nodes,code",
    [
        ((Node("x", "SEMANTIC_RESOURCE", (Edge("x"),)),), "REF_CYCLE"),
        (
            (
                Node("r", "RESULT"),
                Node("x", "SEMANTIC_RESOURCE", (Edge("y"),)),
                Node("y", "SEMANTIC_RESOURCE", (Edge("x"),)),
            ),
            "REF_CYCLE",
        ),
        ((Node("x", "RESULT", (Edge("absent"),)),), "DANGLING_PARENT"),
        ((Node("x", "RESULT"), Node("x", "RESULT")), "DUPLICATE_NODE"),
        (
            (
                Node("r", "RESULT", (Edge("trace"),)),
                Node("trace", "SEMANTIC_RESOURCE", (Edge("a"),)),
                Node("a", "F3-RUN-ATTEMPT"),
            ),
            "ATTEMPT_ANCESTRY",
        ),
        ((Node("r", "RESULT", (Edge("e"),)), Node("e", "EVIDENCE")), "EVIDENCE_DIRECTION"),
        (
            (
                Node("o", "F2-OBSERVATION", (Edge("q", "wrong_path"),)),
                Node("q", "F2-QUALIFICATION"),
            ),
            "GRAPH_EDGE_ROLE",
        ),
        (
            (
                Node("o", "F2-OBSERVATION", (Edge("q", "qualification_ref"),)),
                Node("q", "SOURCE-BYTES"),
            ),
            "FOREIGN_PARENT",
        ),
        (
            (
                Node(
                    "x",
                    "F3-EXPERIMENT",
                    (
                        Edge("s", "input_binding.temporal_binding_set_ref"),
                        Edge("o", "input_binding.observation_ref"),
                    ),
                ),
                Node("s", "TEMPORAL-SEQUENCE"),
                Node("o", "F2-OBSERVATION"),
            ),
            "GRAPH_UNION_BRANCH",
        ),
        (
            (
                Node("e", "F5-EVALUATION", (Edge("p", "outcome_refs[]"),)),
                Node("p", "RESOURCE:POLICY"),
            ),
            "FOREIGN_PARENT",
        ),
    ],
)
def test_graph_isolated_adversaries(nodes, code):
    refusal(lambda: check(nodes), code)


def test_graph_reversal_swapping_and_missing_edge_control():
    valid = (Node("e", "EVIDENCE", (Edge("s", "subject_ref"),)), Node("s", "SOURCE-BYTES"))
    bounded(check(valid))
    refusal(
        lambda: check((Node("e", "EVIDENCE"), Node("s", "SOURCE-BYTES", (Edge("e"),)))),
        "EVIDENCE_DIRECTION",
    )
    valid = (
        Node("o", "F2-OBSERVATION", (Edge("q", "qualification_ref"),)),
        Node("q", "F2-QUALIFICATION"),
        Node("s", "SOURCE-BYTES"),
    )
    bounded(check(valid))
    refusal(
        lambda: check(
            (Node("o", "F2-OBSERVATION", (Edge("s", "qualification_ref"),)), valid[1], valid[2])
        ),
        "FOREIGN_PARENT",
    )
    # Omit a required real edge: topology alone cannot detect this incompleteness.
    omitted = check((Node("o", "F2-OBSERVATION"),))
    bounded(omitted)
    assert omitted.structure == "STRUCTURE_VALID_SYMBOLIC_ONLY"
    assert "REAL_GRAPH_CLOSURE_NOT_SUPPLIED" in omitted.blockers


def test_graph_and_fragment_resource_safety_budgets():
    refusal(
        lambda: check(tuple(Node(str(i), "SEMANTIC_RESOURCE") for i in range(4097))),
        "GRAPH_NODE_BOUND",
    )
    refusal(lambda: check((Node("x", "RESULT", (Edge("x"),) * 4097),)), "GRAPH_DEGREE_BOUND")
    nodes = tuple(Node(str(i), "SEMANTIC_RESOURCE", (Edge("0"),) * 4096) for i in range(5))
    refusal(lambda: check(nodes), "GRAPH_EDGE_BOUND")
    chain = tuple(
        Node(str(i), "SEMANTIC_RESOURCE", (Edge(str(i + 1)),) if i < 128 else ())
        for i in range(129)
    )
    for ordered in (chain, chain[::-1]):
        refusal(lambda ordered=ordered: check(ordered), "GRAPH_DEPTH_BOUND")
    assert check(tuple(Node(str(i), "SEMANTIC_RESOURCE") for i in range(4096))).node_count == 4096
    schema = codec.RecordSchema((("a", codec.ArraySchema(codec.TEXT, 0, 4096)),))
    refusal(lambda: codec.encode_canonical_record({"a": [""] * 4097}, schema), "ARRAY_BOUND")
    refusal(lambda: codec.parse_canonical_record(b" " * 16_777_217, A), "PAYLOAD_BOUND")
    cyclic = {}
    cyclic["a"] = cyclic
    refusal(lambda: codec.encode_canonical_record(cyclic, A), "REF_CYCLE")
    # Safety refusal only; P2-DEPTH frozen 64/65 remains excluded, no depth convention chosen.
    deep = b'{"a":' * 100 + b'"x"' + b"}" * 100
    refusal(
        lambda: codec.parse_canonical_record(deep, A),
        "PENDING_OWNER_BOUNDARY_DECISION",
        "CONTRACT_BOUNDARY_UNRESOLVED",
    )


def test_multifault_fail_closed_and_diagnostic_noninterference():
    marker = "SYNTHETIC_PRIVATE_SENTINEL"
    fake = parent()
    fake.update(digest_hex="BAD", locator=marker, digest_algorithm="BAD")
    error = refusal(lambda: refs.validate_parent_ref_shape(fake, "RESULT"))
    assert marker not in str(error) and marker not in repr(error)
    _, payload, frame, envelope = stored()
    envelope.update(digest_hex="BAD", locator=marker, domain_tag="BAD")
    error = refusal(lambda: codec.verify_source_frame(frame + b"x", envelope))
    assert marker not in str(error)
    refusal(
        lambda: check(
            (Node("r", "RESULT", (Edge("a"), Edge("absent"))), Node("a", "F3-RUN-ATTEMPT"))
        )
    )
    # Display/host/clock lives outside the contracted raw body and never enters the API.
    wrappers = [
        {"raw": b"synthetic", "display": marker, "host": "one", "clock": "one"},
        {"raw": b"synthetic", "display": "changed", "host": "two", "clock": "two"},
    ]
    candidates = [codec.encode_source_bytes_candidate(w["raw"]) for w in wrappers]
    assert candidates[0] == candidates[1]
    assert marker.encode() not in candidates[0].payload
    diagnostics = [
        refs.validate_parent_ref_shape(parent(digest="a" * 64), "RESULT"),
        refs.validate_parent_ref_shape(parent(digest="b" * 64), "RESULT"),
        check((Node(marker, "SOURCE-BYTES"),)),
    ]
    assert diagnostics[0] == diagnostics[1]
    for diagnostic in diagnostics:
        bounded(diagnostic)
        assert marker not in json.dumps(asdict(diagnostic))
    changed = dict(json.loads(payload), host=marker)
    error = refusal(lambda: codec.encode_canonical_record(changed, codec.SOURCE_PAYLOAD_SCHEMA))
    assert marker not in str(error)
