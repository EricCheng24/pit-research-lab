"""Production structural checks, invented refs never promoted to real identities."""

import copy
import json
from dataclasses import FrozenInstanceError, asdict
from hashlib import sha256
from pathlib import Path

import pytest

from pit_research_lab.mvp.if03 import canonical_codec as codec
from pit_research_lab.mvp.if03 import typed_references as refs
from pit_research_lab.mvp.if03.domain_registry import DOMAIN_REGISTRY

ROOT = Path(__file__).resolve().parents[3]
CASES = json.loads((ROOT / "tests/fixtures/mvp_if03/wu05_oracle01_v0_1/cases.json").read_bytes())[
    "cases"
]
FROZEN_IDS = {
    "N-ASSOCIATION-INSTANCE",
    "N-FOREIGN-PARENT",
    "N-UNREVIEWED-RESOURCE",
    "N-DECISION-FUTURE-PRICE",
    "N-DECISION-OUTCOME",
    "N-DECISION-LABEL",
}


def uint(value):
    return {"type": "uint64", "value": str(value)}


def parent(domain="F2-OBSERVATION", digest="a" * 64):
    # Independent handwritten, explicitly invented claim. No encoder generates it.
    return {
        "domain_tag": f"PITLAB/ACADEMIC/{domain}/candidate-v0.1",
        "object_schema_version": domain.lower() + "-candidate-v0.1",
        "canonical_profile_version": "typed-json-candidate-v0.1",
        "digest_algorithm": "SHA-256",
        "canonical_payload_byte_length": uint(187),
        "digest_hex": digest,
    }


def resource(role="PROTOCOL"):
    return {
        "resource_kind": role,
        "resource_version": "NON_ISSUED",
        "resource_schema": "UNREVIEWED_SHAPE_ONLY",
        "content_ref": parent("SOURCE-BYTES"),
    }


def shallow_payload(domain):
    # Opaque uninspected fields are explicit placeholders, never complete positives.
    payload = dict.fromkeys(DOMAIN_REGISTRY[domain].semantic_fields, "UNINSPECTED")
    payload["canonical_profile_version"] = codec.PROFILE
    return payload


def refusal(code, action, category="STRUCTURALLY_INVALID"):
    with pytest.raises(codec.CodecRefusal) as caught:
        action()
    assert (caught.value.category, caught.value.code) == (category, code)


def execute_frozen_case(case):
    """Use exact ledger input at the API's actual scope, without fake typed parents.

    parent_match compares domain declarations only: revisions are unexamined.
    decision_fields checks the supplied extra name as a subset, no fake full record.
    resource_schema gates the exact role/schema request, without fabricating bytes.
    ExperimentInput passes its exact object and rejects fields before its symbols.
    """
    inp = case["input"]
    if case["operation"] == "experiment_input":
        return refs.validate_experiment_input_shape(inp)
    if case["operation"] == "parent_match":
        return refs.validate_declared_parent_domain(inp["expected_domain"], inp["supplied_domain"])
    if case["operation"] == "resource_schema":
        return refs.require_resource_semantics(inp["role"], inp["schema"])
    if case["operation"] == "decision_fields":
        return refs.inspect_declared_field_names("F5-DECISION", [inp["extra"]])
    raise AssertionError("unsupported frozen operation")


@pytest.mark.parametrize(
    "case", [c for c in CASES if c["case_id"] in FROZEN_IDS], ids=lambda c: c["case_id"]
)
def test_exact_frozen_scoped_refusals(case):
    refusal(
        case["expected"]["code"], lambda: execute_frozen_case(case), case["expected"]["category"]
    )


@pytest.mark.parametrize("domain", tuple(DOMAIN_REGISTRY))
def test_invented_parent_is_only_shape_and_cannot_be_resolved(domain):
    result = refs.validate_parent_ref_shape(parent(domain), domain)
    assert result.structure == "STRUCTURAL_ONLY" and result.resolution == "NOT_SUPPLIED"
    assert result.diagnostic_only is True and result.admission_eligible is False
    assert result.trust == "NOT_TRUSTED_PIT_EVIDENCE"
    assert result.source_authentication == "NOT_ESTABLISHED"
    assert result.disposition == "INTEGRATED_PROVISIONAL"
    assert "digest_hex" not in asdict(result)
    with pytest.raises(FrozenInstanceError):
        result.resolution = "RESOLVED_AND_RECOMPUTED"
    refusal(
        "PARENT_EXISTENCE_FRESHNESS_RIGHTS_NOT_SUPPLIED",
        lambda: refs.require_resolved_parent(parent(domain), domain),
        "NOT_SUPPLIED",
    )


@pytest.mark.parametrize("key", tuple(refs.PARENT_FIELDS))
@pytest.mark.parametrize("mode", ("missing", "extra"))
def test_parent_exact_fields(key, mode):
    value = parent()
    if mode == "missing":
        del value[key]
    else:
        value[key + "_alias"] = value[key]
    refusal("CLOSED_FIELDS", lambda: refs.validate_parent_ref_shape(value, "F2-OBSERVATION"))


@pytest.mark.parametrize("key", ("locator", "resolver", "capability", "reference", "issuer"))
def test_parent_disallows_authority_metadata(key):
    value = parent()
    value[key] = "NOT_AUTHORITY"
    refusal("CLOSED_FIELDS", lambda: refs.validate_parent_ref_shape(value, "F2-OBSERVATION"))


@pytest.mark.parametrize(
    "field,value,code,category",
    [
        (
            "domain_tag",
            "PITLAB/ACADEMIC/SOURCE-BYTES/candidate-v0.1",
            "FOREIGN_PARENT",
            "STRUCTURALLY_INVALID",
        ),
        ("object_schema_version", "other", "REFERENCE_NEGOTIATION", "UNSUPPORTED_SCHEMA"),
        ("canonical_profile_version", "other", "REFERENCE_NEGOTIATION", "UNSUPPORTED_SCHEMA"),
        ("digest_algorithm", "sha256", "REFERENCE_NEGOTIATION", "UNSUPPORTED_SCHEMA"),
        ("digest_hex", "A" * 64, "HEX64", "STRUCTURALLY_INVALID"),
        ("digest_hex", "a" * 63, "HEX64", "STRUCTURALLY_INVALID"),
        ("digest_hex", "g" * 64, "HEX64", "STRUCTURALLY_INVALID"),
        ("digest_hex", "é" * 64, "HEX64", "STRUCTURALLY_INVALID"),
        ("canonical_payload_byte_length", uint(0), "PAYLOAD_LENGTH", "STRUCTURALLY_INVALID"),
        ("canonical_payload_byte_length", uint(16777217), "PAYLOAD_LENGTH", "STRUCTURALLY_INVALID"),
        (
            "canonical_payload_byte_length",
            uint("18446744073709551616"),
            "INTEGER_RANGE",
            "STRUCTURALLY_INVALID",
        ),
        ("canonical_payload_byte_length", uint("01"), "INTEGER_SPELLING", "STRUCTURALLY_INVALID"),
        ("canonical_payload_byte_length", uint("-1"), "INTEGER_SPELLING", "STRUCTURALLY_INVALID"),
        (
            "canonical_payload_byte_length",
            {"type": "uint64", "value": True},
            "INTEGER_TEXT",
            "STRUCTURALLY_INVALID",
        ),
        (
            "canonical_payload_byte_length",
            {"type": "int64", "value": "1"},
            "INTEGER_TAG",
            "STRUCTURALLY_INVALID",
        ),
    ],
)
def test_parent_negotiation_and_scalar_bounds(field, value, code, category):
    p = parent()
    p[field] = value
    refusal(code, lambda: refs.validate_parent_ref_shape(p, "F2-OBSERVATION"), category)


def test_parent_unknown_expected_domain_and_extreme_integer():
    refusal(
        "DOMAIN_SCHEMA",
        lambda: refs.validate_parent_ref_shape(parent(), "OTHER"),
        "UNSUPPORTED_SCHEMA",
    )
    p = parent()
    p["canonical_payload_byte_length"] = uint("9" * 10000)
    refusal("INTEGER_RANGE", lambda: refs.validate_parent_ref_shape(p, "F2-OBSERVATION"))


def test_resource_success_carries_gate_and_any_schema_is_unapproved():
    result = refs.validate_resource_ref_shape(resource(), ("PROTOCOL",))
    assert result.structure == "STRUCTURAL_ONLY"
    assert "RESOURCE_SEMANTICS_NOT_SUPPLIED" in result.blockers
    for schema in ("UNREVIEWED_SHAPE_ONLY", "temporal-configuration-candidate-v0.1"):
        refusal(
            "REF_UNAPPROVED_RESOURCE_SCHEMA",
            lambda schema=schema: refs.require_resource_semantics("PROTOCOL", schema),
            "UNSUPPORTED_SCHEMA",
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("resource_kind", "NEW_ROLE"),
        ("resource_kind", "OUTCOME"),
        ("resource_version", ""),
        ("resource_schema", ""),
        ("resource_schema", "x" * 129),
        ("resource_version", "é" * 65),
        ("resource_version", "\ud800"),
        ("content_ref", "a" * 64),
        ("content_ref", parent()),
        ("content_ref", "https://example.invalid/body"),
        ("content_ref", {}),
    ],
)
def test_resource_wrong_shapes(field, value):
    r = resource()
    r[field] = value
    with pytest.raises(codec.CodecRefusal):
        refs.validate_resource_ref_shape(r, ("PROTOCOL",))


@pytest.mark.parametrize("key", tuple(refs.RESOURCE_FIELDS))
def test_resource_missing_extra_and_unknown_expected_role(key):
    r = resource()
    del r[key]
    refusal("CLOSED_FIELDS", lambda: refs.validate_resource_ref_shape(r, ("PROTOCOL",)))
    r = resource()
    r["alias"] = "a"
    refusal("CLOSED_FIELDS", lambda: refs.validate_resource_ref_shape(r, ("PROTOCOL",)))
    refusal(
        "REF_UNAPPROVED_RESOURCE_SCHEMA",
        lambda: refs.validate_resource_ref_shape(resource(), ("UNKNOWN",)),
        "UNSUPPORTED_SCHEMA",
    )


def test_experiment_input_unions_and_contract_vs_instance():
    sequence = {
        "kind": "SEQUENCE",
        "temporal_binding_set_ref": parent("TEMPORAL-SEQUENCE"),
        "association_contract_version": "experiment-sequence-binding-candidate-v0.1",
    }
    assert refs.validate_experiment_input_shape(sequence).structure == "STRUCTURAL_ONLY"
    wrong = dict(sequence, association_instance_ref=resource("EXPERIMENT_ASSOCIATION"))
    refusal("EXPERIMENT_INPUT_FIELDS", lambda: refs.validate_experiment_input_shape(wrong))
    sequence["association_contract_version"] = "v2"
    refusal(
        "ASSOCIATION_CONTRACT_VERSION",
        lambda: refs.validate_experiment_input_shape(sequence),
        "UNSUPPORTED_SCHEMA",
    )
    single = {
        "kind": "SINGLE_CUTOFF",
        "observation_ref": parent(),
        "single_cutoff_contract_ref": resource(),
    }
    assert refs.validate_experiment_input_shape(single).structure == "STRUCTURAL_ONLY"
    single["single_cutoff_contract_ref"] = resource("OUTCOME")
    with pytest.raises(codec.CodecRefusal):
        refs.validate_experiment_input_shape(single)
    single["kind"] = "single_cutoff"
    refusal("EXPERIMENT_INPUT_FIELDS", lambda: refs.validate_experiment_input_shape(single))


def scope():
    return {
        "data_mode": "SYNTHETIC_GOLDEN",
        "pit_status": "UNRESOLVED",
        "evidence_class": "UNVERIFIED",
        "scope_flags": asdict(refs.DiagnosticScope()),
    }


def tick():
    return {
        "tick_id": "t1",
        "tick_order": uint(1),
        "context_ref": "declared-only",
        "decision_cutoff": {
            "source_text": "2027-01-07T18:00:00+08:00",
            "timezone_name": "Asia/Taipei",
            "offset": "+08:00",
            "precision": "SECOND",
            "origin_ref": resource("ORIGIN"),
            "utc_comparison": "2027-01-07T10:00:00Z",
            "timezone_rules_ref": resource("TIMEZONE_RULES"),
        },
    }


def sequence_member():
    return {
        "tick": tick(),
        "binding_ref": resource("SEMANTIC_TRACE"),
        "qualification_ref": parent("F2-QUALIFICATION"),
        "observation_ref": {"type": "available", "ref": parent()},
        "scope": scope(),
    }


def decision():
    d = shallow_payload("F5-DECISION")
    d.update(
        sequence_tick_ref={
            "sequence_ref": parent("TEMPORAL-SEQUENCE"),
            "tick_order": uint(1),
            "tick_id": "t1",
        },
        policy_ref=resource("POLICY"),
        observation_refs=[parent(digest="b" * 64), parent(digest="a" * 64)],
        action={"type": "not_evaluated", "owner": "F5", "reason": "NOT_SUPPLIED"},
        decision_execution_rules_ref=resource("EXECUTION_RULES"),
    )
    return d


def test_observation_foreign_qualification_and_no_complete_positive():
    d = shallow_payload("F2-OBSERVATION")
    d.update(
        qualification_ref=parent("F2-QUALIFICATION"),
        tick_context=tick(),
        projection_policy_ref=resource("PROJECTION_POLICY"),
        release_policy_ref=resource("OBSERVATION_RELEASE_POLICY"),
    )
    result = refs.inspect_domain_structure("F2-OBSERVATION", d)
    assert "feature_values" in result.uninspected_fields
    assert "DOMAIN_SEMANTICS_NOT_SUPPLIED" in result.blockers
    d["qualification_ref"] = parent("SOURCE-BYTES")
    refusal("FOREIGN_PARENT", lambda: refs.inspect_domain_structure("F2-OBSERVATION", d))


def test_sequence_available_withheld_and_conditional_parent():
    d = shallow_payload("TEMPORAL-SEQUENCE")
    d.update(
        bindings=[sequence_member()],
        configuration_ref=resource("TEMPORAL_CONFIGURATION"),
        schedule_ref=resource("DECISION_SCHEDULE"),
        provenance_ref=resource("SEMANTIC_TRACE"),
    )
    original = copy.deepcopy(d)
    assert refs.inspect_domain_structure("TEMPORAL-SEQUENCE", d).structure == "STRUCTURAL_ONLY"
    assert d == original
    member = d["bindings"][0]
    member["observation_ref"] = {
        "type": "withheld",
        "owner": "F2",
        "reason": "PRIVATE",
        "policy_ref": resource("OBSERVATION_RELEASE_POLICY"),
    }
    refs.inspect_domain_structure("TEMPORAL-SEQUENCE", d)
    member["observation_ref"]["ref"] = parent()
    refusal("CLOSED_FIELDS", lambda: refs.inspect_domain_structure("TEMPORAL-SEQUENCE", d))
    member["observation_ref"] = {"type": "available", "ref": parent("RESULT")}
    refusal("FOREIGN_PARENT", lambda: refs.inspect_domain_structure("TEMPORAL-SEQUENCE", d))
    member["observation_ref"] = original["bindings"][0]["observation_ref"]
    member["qualification_ref"] = parent()
    refusal("FOREIGN_PARENT", lambda: refs.inspect_domain_structure("TEMPORAL-SEQUENCE", d))


def test_attempt_result_realized_input_direction_and_union():
    a = shallow_payload("F3-RUN-ATTEMPT")
    a.update(
        attempt_id="invented-unresolved",
        experiment_ref=parent("F3-EXPERIMENT"),
        operation_receipt_ref=resource("NATIVE_RECEIPT"),
        result_ref={"type": "available", "ref": parent("RESULT")},
    )
    refs.inspect_domain_structure("F3-RUN-ATTEMPT", a)
    a["result_ref"] = {"type": "not_evaluated", "owner": "F3", "reason": "NOT_RUN"}
    refs.inspect_domain_structure("F3-RUN-ATTEMPT", a)
    a["result_ref"]["ref"] = parent("RESULT")
    refusal("CLOSED_FIELDS", lambda: refs.inspect_domain_structure("F3-RUN-ATTEMPT", a))
    r = shallow_payload("RESULT")
    r.update(
        experiment_ref=parent("F3-EXPERIMENT"),
        realized_input_refs=[parent("SOURCE-BYTES"), resource("OUTCOME"), resource("PRICE")],
        limitations=[],
    )
    refs.inspect_domain_structure("RESULT", r)
    for invalid in (parent("F3-RUN-ATTEMPT"), parent("F5-DECISION"), resource("PROTOCOL")):
        r["realized_input_refs"] = [invalid]
        with pytest.raises(codec.CodecRefusal):
            refs.inspect_domain_structure("RESULT", r)
    r["attempt_ref"] = parent("F3-RUN-ATTEMPT")
    refusal("CLOSED_FIELDS", lambda: refs.inspect_domain_structure("RESULT", r))


def test_evidence_subject_and_full_provenance_union():
    e = shallow_payload("EVIDENCE")
    e.update(
        subject_ref=parent("RESULT"),
        semantic_audit_ref=resource("SEMANTIC_EVIDENCE"),
        source_code_protocol_refs=[
            parent("F3-RUN-ATTEMPT"),
            resource("TIMEZONE_RULES"),
            resource("AUTHOR_RECORD"),
        ],
        limitations=[],
    )
    result = refs.inspect_domain_structure("EVIDENCE", e)
    assert "evidence_claim" in result.uninspected_fields
    for invalid in ("EVIDENCE", "F3-RUN-ATTEMPT"):
        e["subject_ref"] = parent(invalid)
        refusal("FOREIGN_PARENT", lambda: refs.inspect_domain_structure("EVIDENCE", e))
    e["subject_ref"] = parent("RESULT")
    e["source_code_protocol_refs"] = [parent("EVIDENCE")]
    refusal("FOREIGN_PARENT", lambda: refs.inspect_domain_structure("EVIDENCE", e))


def test_decision_exclusions_evaluation_roles_and_preserved_order():
    d = decision()
    original = copy.deepcopy(d)
    refs.inspect_domain_structure("F5-DECISION", d)
    assert d == original and d["observation_refs"][0]["digest_hex"] == "b" * 64
    d["observation_refs"].reverse()
    refs.inspect_domain_structure("F5-DECISION", d)
    assert d["observation_refs"] == original["observation_refs"][::-1]
    for name in ("future_price", "outcome_ref", "label_maturity"):
        bad = dict(d, **{name: resource("OUTCOME")})
        refusal("CLOSED_FIELDS", lambda bad=bad: refs.inspect_domain_structure("F5-DECISION", bad))
    for invalid in (parent("F5-EVALUATION"), resource("OUTCOME")):
        d["observation_refs"] = [invalid]
        with pytest.raises(codec.CodecRefusal):
            refs.inspect_domain_structure("F5-DECISION", d)
    e = shallow_payload("F5-EVALUATION")
    e.update(
        decision_refs=[parent("F5-DECISION")],
        outcome_refs=[resource("OUTCOME"), resource("PRICE")],
        evaluation_policy_ref=resource("EVALUATION_PROTOCOL"),
        limitations=[],
    )
    refs.inspect_domain_structure("F5-EVALUATION", e)
    e["decision_refs"] = [parent()]
    refusal("FOREIGN_PARENT", lambda: refs.inspect_domain_structure("F5-EVALUATION", e))
    e["decision_refs"] = [parent("F5-DECISION")]
    e["outcome_refs"] = [resource("POLICY")]
    refusal(
        "REF_UNAPPROVED_RESOURCE_SCHEMA",
        lambda: refs.inspect_domain_structure("F5-EVALUATION", e),
        "UNSUPPORTED_SCHEMA",
    )


def test_domain_structure_is_not_arbitrary_nested_reference_walker():
    d = shallow_payload("F2-QUALIFICATION")
    # No nested dict is silently reinterpreted as an approved typed identity.
    d["feature_cohort"] = {"uninspected": parent("EVIDENCE")}
    result = refs.inspect_domain_structure("F2-QUALIFICATION", d)
    assert "feature_cohort" in result.uninspected_fields
    assert "DOMAIN_SEMANTICS_NOT_SUPPLIED" in result.blockers
    assert result.checked_positions == ("canonical_profile_version",)
    del d["scope"]
    refusal("CLOSED_FIELDS", lambda: refs.inspect_domain_structure("F2-QUALIFICATION", d))


def test_depth_boundary_cycle_and_array_safety():
    d = shallow_payload("F2-QUALIFICATION")
    deep = "x"
    for _ in range(65):
        deep = [deep]
    d["feature_cohort"] = deep
    refusal(
        "PENDING_OWNER_BOUNDARY_DECISION",
        lambda: refs.inspect_domain_structure("F2-QUALIFICATION", d),
        "CONTRACT_BOUNDARY_UNRESOLVED",
    )
    d["feature_cohort"] = ["x"] * 4097
    refusal("ARRAY_BOUND", lambda: refs.inspect_domain_structure("F2-QUALIFICATION", d))
    d["feature_cohort"] = d
    refusal("REF_CYCLE", lambda: refs.inspect_domain_structure("F2-QUALIFICATION", d))


def test_direct_constructor_invalid_and_source_provenance_boundary():
    folder = ROOT / "tests/fixtures/mvp_if03/oracle01_v0_1/positives/B01"
    payload = (folder / "canonical_payload.bin").read_bytes()
    frame = (folder / "frame.bin").read_bytes()
    valid = codec.SourceBytesCandidate(payload, frame, sha256(frame).hexdigest())
    assert valid == codec.encode_source_bytes_candidate(b"")
    for p, f, digest in (
        (b"{}", frame, sha256(frame).hexdigest()),
        (payload, frame, "0" * 64),
        (payload, frame + b"x", sha256(frame + b"x").hexdigest()),
        (payload, frame, "A" * 64),
        (bytearray(payload), frame, sha256(frame).hexdigest()),
    ):
        with pytest.raises(codec.CodecRefusal):
            codec.SourceBytesCandidate(p, f, digest)
    # A consistent claim can still lie about raw-body hash: constructor has no raw bytes.
    forged_payload = payload.replace(b'"body_sha256":"e3b0', b'"body_sha256":"a3b0')
    forged_frame = frame[: -len(payload)] + forged_payload
    forged = codec.SourceBytesCandidate(
        forged_payload, forged_frame, sha256(forged_frame).hexdigest()
    )
    refusal(
        "SOURCE_BODY_MISMATCH",
        lambda: codec.verify_source_bytes_candidate(
            b"", forged_payload, forged_frame, forged.candidate_envelope
        ),
    )


def test_experiment_domain_selects_declared_helper_and_preserves_seed_bound():
    d = shallow_payload("F3-EXPERIMENT")
    d.update(
        hypothesis=resource("HYPOTHESIS"),
        input_binding={
            "kind": "SEQUENCE",
            "temporal_binding_set_ref": parent("TEMPORAL-SEQUENCE"),
            "association_contract_version": "experiment-sequence-binding-candidate-v0.1",
        },
        method=resource("METHOD"),
        protocol_ref=resource("PROTOCOL"),
        horizon_maturity_ref=resource("HORIZON_MATURITY"),
        seed={"type": "int64", "value": "9223372036854775807"},
        evaluation_plan_ref=resource("EVALUATION_PLAN"),
    )
    result = refs.inspect_domain_structure("F3-EXPERIMENT", d)
    assert result.uninspected_fields == ()
    assert result.semantics == "BLOCKED_NOT_SUPPLIED"
    d["seed"] = {"type": "int64", "value": "-1"}
    refusal("SEED_RANGE", lambda: refs.inspect_domain_structure("F3-EXPERIMENT", d))
    d["input_binding"]["temporal_binding_set_ref"] = parent()
    refusal("FOREIGN_PARENT", lambda: refs.inspect_domain_structure("F3-EXPERIMENT", d))


def test_reference_bounds_edges_and_required_arrays():
    p = parent()
    for length in (1, 16_777_216):
        p["canonical_payload_byte_length"] = uint(length)
        assert refs.validate_parent_ref_shape(p, "F2-OBSERVATION").structure == "STRUCTURAL_ONLY"
    r = resource()
    r["resource_version"] = "x" * 128
    r["resource_schema"] = "é" * 64
    refs.validate_resource_ref_shape(r, ("PROTOCOL",))
    r["content_ref"] = resource()
    refusal("CLOSED_FIELDS", lambda: refs.validate_resource_ref_shape(r, ("PROTOCOL",)))
    for entries in ([], [parent()] * 4097):
        d = decision()
        d["observation_refs"] = entries
        refusal("ARRAY_BOUND", lambda d=d: refs.inspect_domain_structure("F5-DECISION", d))
    d = decision()
    d["sequence_tick_ref"]["sequence_ref"] = parent("RESULT")
    refusal("FOREIGN_PARENT", lambda: refs.inspect_domain_structure("F5-DECISION", d))


def test_scope_and_time_are_explicitly_bounded_without_timezone_approval():
    d = shallow_payload("TEMPORAL-SEQUENCE")
    d.update(
        bindings=[sequence_member()],
        configuration_ref=resource("TEMPORAL_CONFIGURATION"),
        schedule_ref=resource("DECISION_SCHEDULE"),
        provenance_ref=resource("SEMANTIC_TRACE"),
    )
    d["bindings"][0]["scope"]["scope_flags"]["diagnostic_only"] = 1
    # Pre-guard denies bare int before any Boolean coercion.
    refusal("BARE_NUMBER", lambda: refs.inspect_domain_structure("TEMPORAL-SEQUENCE", d))
    d["bindings"][0]["scope"]["scope_flags"]["diagnostic_only"] = False
    refusal("SCOPE_FLAGS", lambda: refs.inspect_domain_structure("TEMPORAL-SEQUENCE", d))
    d["bindings"][0]["scope"] = scope()
    d["bindings"][0]["tick"]["decision_cutoff"]["timezone_rules_ref"] = resource("PROTOCOL")
    refusal(
        "REF_UNAPPROVED_RESOURCE_SCHEMA",
        lambda: refs.inspect_domain_structure("TEMPORAL-SEQUENCE", d),
        "UNSUPPORTED_SCHEMA",
    )


@pytest.mark.parametrize(
    "old,new",
    [
        (
            b"PITLAB/ACADEMIC/SOURCE-BYTES/candidate-v0.1",
            b"PITLAB/ACADEMIC/SOURCE-BYTES/candidate-v0.2",
        ),
        (b"source-bytes-candidate-v0.1", b"source-bytes-candidate-v0.2"),
        (b"typed-json-candidate-v0.1", b"typed-json-candidate-v0.2"),
    ],
)
def test_constructor_rejects_consistent_hash_for_unregistered_negotiation(old, new):
    folder = ROOT / "tests/fixtures/mvp_if03/oracle01_v0_1/positives/B01"
    payload = (folder / "canonical_payload.bin").read_bytes().replace(old, new)
    frame = (folder / "frame.bin").read_bytes().replace(old, new)
    with pytest.raises(codec.CodecRefusal):
        codec.SourceBytesCandidate(payload, frame, sha256(frame).hexdigest())


def test_direct_experiment_helper_rejects_coercible_literal_objects():
    class EqualToAnything:
        def __eq__(self, other):
            return True

    value = {
        "kind": "SEQUENCE",
        "temporal_binding_set_ref": parent("TEMPORAL-SEQUENCE"),
        "association_contract_version": EqualToAnything(),
    }
    refusal(
        "ASSOCIATION_CONTRACT_VERSION",
        lambda: refs.validate_experiment_input_shape(value),
        "UNSUPPORTED_SCHEMA",
    )
    value["kind"] = EqualToAnything()
    refusal("EXPERIMENT_INPUT_FIELDS", lambda: refs.validate_experiment_input_shape(value))
