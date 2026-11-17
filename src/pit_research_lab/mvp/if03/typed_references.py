"""Bounded inspections of declared IF-03 fragments, without identity resolution.

No successful result establishes existence, freshness, rights, source provenance,
resource approval or issuance. Diagnostics have no global multi-fault precedence.
Opaque domain fields are reported explicitly; this is not a full-domain parser.
"""

from dataclasses import dataclass, field
from typing import Literal, cast

from .canonical_codec import (
    MAX_ARRAY,
    MAX_PAYLOAD,
    PROFILE,
    CodecRefusal,
    TextSchema,
    _closed,
    _guard_value,
    _text,
    validate_integer,
)
from .domain_registry import (
    PROVENANCE_DOMAINS,
    REALIZED_DOMAINS,
    RESOURCE_ROLES,
    SUBJECT_DOMAINS,
    lookup_domain,
)

PARENT_FIELDS = frozenset(
    (
        "domain_tag",
        "object_schema_version",
        "canonical_profile_version",
        "digest_algorithm",
        "canonical_payload_byte_length",
        "digest_hex",
    )
)
RESOURCE_FIELDS = frozenset(("resource_kind", "resource_version", "resource_schema", "content_ref"))


@dataclass(frozen=True, slots=True)
class DiagnosticScope:
    diagnostic_only: Literal[True] = field(default=True, init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)
    trust: Literal["NOT_TRUSTED_PIT_EVIDENCE"] = field(
        default="NOT_TRUSTED_PIT_EVIDENCE", init=False
    )
    source_authentication: Literal["NOT_ESTABLISHED"] = field(default="NOT_ESTABLISHED", init=False)
    disposition: Literal["INTEGRATED_PROVISIONAL"] = field(
        default="INTEGRATED_PROVISIONAL", init=False
    )


@dataclass(frozen=True, slots=True)
class ShapeInspection(DiagnosticScope):
    """Detached immutable diagnostics, containing no promoted identity or input dict."""

    checked_positions: tuple[str, ...] = ()
    uninspected_fields: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ("PARENT_EXISTENCE_FRESHNESS_RIGHTS_NOT_SUPPLIED",)
    structure: Literal["STRUCTURAL_ONLY"] = field(default="STRUCTURAL_ONLY", init=False)
    resolution: Literal["NOT_SUPPLIED"] = field(default="NOT_SUPPLIED", init=False)
    semantics: Literal["BLOCKED_NOT_SUPPLIED"] = field(default="BLOCKED_NOT_SUPPLIED", init=False)


def _record(value: object, keys: str, code: str = "CLOSED_FIELDS") -> dict[str, object]:
    expected = set(keys.split())
    if type(value) is not dict or len(value) != len(expected) or set(value) != expected:
        raise CodecRefusal(code)
    return cast(dict[str, object], value)


def _list(value: object, minimum: int = 1) -> list[object]:
    if type(value) is not list:
        raise CodecRefusal("ARRAY_TYPE")
    entries = cast(list[object], value)
    if not minimum <= len(entries) <= MAX_ARRAY:
        raise CodecRefusal("ARRAY_BOUND")
    return entries


def _label(value: object) -> str:
    return _text(value, TextSchema(min_bytes=1, max_bytes=128))


def validate_declared_parent_domain(expected_domain: str, supplied_domain: str) -> ShapeInspection:
    """Compare registered type declarations only; no revision/history comparison."""
    lookup_domain(expected_domain)
    lookup_domain(supplied_domain)
    if expected_domain != supplied_domain:
        raise CodecRefusal("FOREIGN_PARENT")
    return ShapeInspection(checked_positions=("declared_parent_domain",))


def validate_parent_ref_shape(value: object, expected_domain: str) -> ShapeInspection:
    """Six-field supplied claim only, even with an invented but well-shaped digest."""
    descriptor = lookup_domain(expected_domain)
    d = _record(value, " ".join(PARENT_FIELDS))
    _text(d["domain_tag"], TextSchema(min_bytes=1, max_bytes=128))
    if d["domain_tag"] != descriptor.domain_tag:
        raise CodecRefusal("FOREIGN_PARENT")
    for key, expected in (
        ("object_schema_version", descriptor.object_schema_version),
        ("canonical_profile_version", descriptor.canonical_profile_version),
        ("digest_algorithm", "SHA-256"),
    ):
        if type(d[key]) is not str or d[key] != expected:
            raise CodecRefusal("REFERENCE_NEGOTIATION", "UNSUPPORTED_SCHEMA")
    length = validate_integer(d["canonical_payload_byte_length"])
    if not 1 <= length <= MAX_PAYLOAD:
        raise CodecRefusal("PAYLOAD_LENGTH")
    _text(d["digest_hex"], TextSchema(hex64=True))
    return ShapeInspection(checked_positions=("ParentRef<" + expected_domain + ">",))


def _parent_union(value: object, domains: tuple[str, ...]) -> None:
    d = _record(value, " ".join(PARENT_FIELDS))
    for name in domains:
        if d["domain_tag"] == lookup_domain(name).domain_tag:
            validate_parent_ref_shape(d, name)
            return
    raise CodecRefusal("FOREIGN_PARENT")


def require_resource_semantics(role: object, schema: object) -> None:
    """No resource body/schema/rights approval is supplied in CAN-02, for any label."""
    _label(role)
    _label(schema)
    raise CodecRefusal("REF_UNAPPROVED_RESOURCE_SCHEMA", "UNSUPPORTED_SCHEMA")


def require_resolved_parent(value: object, expected_domain: str) -> None:
    """Fail closed if actual immutable parent, freshness, rights or issuance is required."""
    validate_parent_ref_shape(value, expected_domain)
    raise CodecRefusal("PARENT_EXISTENCE_FRESHNESS_RIGHTS_NOT_SUPPLIED", "NOT_SUPPLIED")


def validate_resource_ref_shape(value: object, expected_roles: tuple[str, ...]) -> ShapeInspection:
    """Registered role and source-parent shape; resource body semantics stay blocked."""
    if type(expected_roles) is not tuple or not 1 <= len(expected_roles) <= len(RESOURCE_ROLES):
        raise CodecRefusal("REF_UNAPPROVED_RESOURCE_SCHEMA", "UNSUPPORTED_SCHEMA")
    for role in expected_roles:
        if type(role) is not str or role not in RESOURCE_ROLES:
            raise CodecRefusal("REF_UNAPPROVED_RESOURCE_SCHEMA", "UNSUPPORTED_SCHEMA")
    d = _record(value, " ".join(RESOURCE_FIELDS))
    role = _label(d["resource_kind"])
    if role not in RESOURCE_ROLES or role not in expected_roles:
        raise CodecRefusal("REF_UNAPPROVED_RESOURCE_SCHEMA", "UNSUPPORTED_SCHEMA")
    _label(d["resource_version"])
    _label(d["resource_schema"])
    validate_parent_ref_shape(d["content_ref"], "SOURCE-BYTES")
    return ShapeInspection(
        checked_positions=("ResourceRef<" + role + ">",),
        blockers=("RESOURCE_SEMANTICS_NOT_SUPPLIED", "RESOURCE_BYTES_SCHEMA_RIGHTS_NOT_SUPPLIED"),
    )


def _ref_union(value: object, domains: tuple[str, ...], roles: tuple[str, ...]) -> None:
    # Only invoked at a declared union position, never arbitrary dict discovery.
    if type(value) is dict and "resource_kind" in value:
        validate_resource_ref_shape(value, roles)
    else:
        _parent_union(value, domains)


def validate_experiment_input_shape(value: object) -> ShapeInspection:
    """AD01-09 ExperimentInput closed union; no association INSTANCE may be hashed."""
    if type(value) is not dict or type(value.get("kind")) is not str:
        raise CodecRefusal("EXPERIMENT_INPUT_FIELDS")
    if value.get("kind") == "SEQUENCE":
        d = _record(
            value,
            "kind temporal_binding_set_ref association_contract_version",
            "EXPERIMENT_INPUT_FIELDS",
        )
        if (
            type(d["association_contract_version"]) is not str
            or d["association_contract_version"] != "experiment-sequence-binding-candidate-v0.1"
        ):
            raise CodecRefusal("ASSOCIATION_CONTRACT_VERSION", "UNSUPPORTED_SCHEMA")
        validate_parent_ref_shape(d["temporal_binding_set_ref"], "TEMPORAL-SEQUENCE")
    elif value.get("kind") == "SINGLE_CUTOFF":
        d = _record(
            value, "kind observation_ref single_cutoff_contract_ref", "EXPERIMENT_INPUT_FIELDS"
        )
        validate_parent_ref_shape(d["observation_ref"], "F2-OBSERVATION")
        validate_resource_ref_shape(d["single_cutoff_contract_ref"], ("PROTOCOL",))
    else:
        raise CodecRefusal("EXPERIMENT_INPUT_FIELDS")
    return ShapeInspection(
        checked_positions=("ExperimentInput",),
        blockers=(
            "RESOURCE_SEMANTICS_NOT_SUPPLIED",
            "PARENT_EXISTENCE_FRESHNESS_RIGHTS_NOT_SUPPLIED",
        ),
    )


def inspect_declared_field_names(domain: str, names: object) -> ShapeInspection:
    """Reject undeclared field names in a supplied subset; does not assert completeness."""
    desc = lookup_domain(domain)
    if type(names) not in (list, tuple):
        raise CodecRefusal("FIELD_NAMES")
    field_names = cast(list[object] | tuple[object, ...], names)
    if len(field_names) > MAX_ARRAY:
        raise CodecRefusal("FIELD_NAMES")
    for name in field_names:
        _label(name)
        if name not in desc.semantic_fields:
            raise CodecRefusal("DECISION_FIELDS" if domain == "F5-DECISION" else "CLOSED_FIELDS")
    return ShapeInspection(
        checked_positions=("declared_field_names_subset",),
        blockers=("COMPLETE_PAYLOAD_NOT_INSPECTED",),
    )


def _unavailable(value: object, tags: tuple[str, ...]) -> None:
    d = _record(value, "type owner reason")
    if d["type"] not in tags:
        raise CodecRefusal("UNION_TAG")
    _text(d["owner"])
    _text(d["reason"])


def _available(value: object, domain: str, fallback: str) -> None:
    if type(value) is dict and value.get("type") == "available":
        d = _record(value, "type ref")
        validate_parent_ref_shape(d["ref"], domain)
    elif fallback == "withheld":
        d = _record(value, "type owner reason policy_ref")
        if d["type"] != "withheld":
            raise CodecRefusal("UNION_TAG")
        _text(d["owner"])
        _text(d["reason"])
        validate_resource_ref_shape(d["policy_ref"], ("OBSERVATION_RELEASE_POLICY",))
    else:
        _unavailable(value, (fallback,))


def _time_shape(value: object) -> None:
    # Text/role grammar only: no host timezone rules or clock are consulted.
    d = _record(
        value,
        "source_text timezone_name offset precision origin_ref utc_comparison timezone_rules_ref",
    )
    for key in ("source_text", "timezone_name", "offset", "utc_comparison"):
        _text(d[key])
    if d["precision"] != "SECOND":
        raise CodecRefusal("TIME_PRECISION", "UNSUPPORTED_SCHEMA")
    validate_resource_ref_shape(d["origin_ref"], ("ORIGIN",))
    validate_resource_ref_shape(d["timezone_rules_ref"], ("TIMEZONE_RULES",))


def _scope_shape(value: object) -> None:
    d = _record(value, "data_mode pit_status evidence_class scope_flags")
    # This inspector supports only the explicitly bounded diagnostic profile.
    for key, literal in (
        ("data_mode", "SYNTHETIC_GOLDEN"),
        ("pit_status", "UNRESOLVED"),
        ("evidence_class", "UNVERIFIED"),
    ):
        if d[key] != literal:
            raise CodecRefusal("UNSUPPORTED_SCOPE_PROFILE", "NOT_SUPPLIED")
    flags = _record(
        d["scope_flags"],
        "diagnostic_only admission_eligible trust source_authentication disposition",
    )
    expected = DiagnosticScope()
    for key in flags:
        literal = getattr(expected, key)
        if type(flags[key]) is not type(literal) or flags[key] != literal:
            raise CodecRefusal("SCOPE_FLAGS")


def _tick_shape(value: object) -> None:
    d = _record(value, "tick_id tick_order decision_cutoff context_ref")
    _text(d["tick_id"])
    validate_integer(d["tick_order"])
    _time_shape(d["decision_cutoff"])
    _text(d["context_ref"])


def _sequence_member(value: object) -> None:
    d = _record(value, "tick binding_ref qualification_ref observation_ref scope")
    validate_parent_ref_shape(d["qualification_ref"], "F2-QUALIFICATION")
    _available(d["observation_ref"], "F2-OBSERVATION", "withheld")
    validate_resource_ref_shape(d["binding_ref"], ("SEMANTIC_TRACE",))
    _tick_shape(d["tick"])
    _scope_shape(d["scope"])


def inspect_domain_structure(domain: str, value: object) -> ShapeInspection:
    """Top-level closedness and selected declared positions, not complete semantics.

    Remaining fields are opaque, bounded values listed in uninspected_fields.
    TimeRecord inspection is grammar only, not date/zone/instant validation.
    Arrays are inspected in supplied order, never sorted or copied into identity.
    SOURCE-BYTES complete checks remain exclusively in CAN-01.
    """
    desc = lookup_domain(domain)
    if domain == "SOURCE-BYTES":
        raise CodecRefusal("USE_CAN01_SOURCE_BYTES_API", "NOT_SUPPLIED")
    _guard_value(value)  # conservative CAN-01 depth refusal, no normative convention
    d = _closed(value, set(desc.semantic_fields))
    if d["canonical_profile_version"] != PROFILE:
        raise CodecRefusal("PROFILE", "UNSUPPORTED_SCHEMA")
    checked = ["canonical_profile_version"]

    def parent(key: str, expected: str) -> None:
        validate_parent_ref_shape(d[key], expected)
        checked.append(key)

    def resource(key: str, *roles: str) -> None:
        validate_resource_ref_shape(d[key], roles)
        checked.append(key)

    def parents(key: str, expected: str) -> None:
        for ref in _list(d[key]):
            validate_parent_ref_shape(ref, expected)
        checked.append(key)

    def resources(key: str, roles: tuple[str, ...], minimum: int = 1) -> None:
        for ref in _list(d[key], minimum):
            validate_resource_ref_shape(ref, roles)
        checked.append(key)

    if domain == "F2-OBSERVATION":
        parent("qualification_ref", "F2-QUALIFICATION")
        _tick_shape(d["tick_context"])
        checked.append("tick_context")
        resource("projection_policy_ref", "PROJECTION_POLICY")
        resource("release_policy_ref", "OBSERVATION_RELEASE_POLICY")
    elif domain == "TEMPORAL-SEQUENCE":
        for member in _list(d["bindings"]):
            _sequence_member(member)
        checked.append("bindings")
        resource("configuration_ref", "TEMPORAL_CONFIGURATION")
        resource("schedule_ref", "DECISION_SCHEDULE")
        resource("provenance_ref", "SEMANTIC_TRACE")
    elif domain == "F3-EXPERIMENT":
        validate_experiment_input_shape(d["input_binding"])
        checked.append("input_binding")
        for key, role in (
            ("hypothesis", "HYPOTHESIS"),
            ("method", "METHOD"),
            ("protocol_ref", "PROTOCOL"),
            ("horizon_maturity_ref", "HORIZON_MATURITY"),
            ("evaluation_plan_ref", "EVALUATION_PLAN"),
        ):
            resource(key, role)
        if validate_integer(d["seed"], signed=True) < 0:
            raise CodecRefusal("SEED_RANGE")
        checked.append("seed")
    elif domain == "F3-RUN-ATTEMPT":
        parent("experiment_ref", "F3-EXPERIMENT")
        _available(d["result_ref"], "RESULT", "not_evaluated")
        checked.append("result_ref")
        resource("operation_receipt_ref", "NATIVE_RECEIPT")
        _text(d["attempt_id"])
        checked.append("attempt_id")
    elif domain == "RESULT":
        parent("experiment_ref", "F3-EXPERIMENT")
        for ref in _list(d["realized_input_refs"], 0):
            _ref_union(ref, REALIZED_DOMAINS, ("OUTCOME", "PRICE"))
        checked.append("realized_input_refs")
        resources("limitations", ("LIMITATION",), 0)
    elif domain == "EVIDENCE":
        _parent_union(d["subject_ref"], SUBJECT_DOMAINS)
        checked.append("subject_ref")
        for ref in _list(d["source_code_protocol_refs"]):
            _ref_union(ref, PROVENANCE_DOMAINS, tuple(sorted(RESOURCE_ROLES)))
        checked.append("source_code_protocol_refs")
        resource("semantic_audit_ref", "SEMANTIC_EVIDENCE")
        resources("limitations", ("LIMITATION",), 0)
    elif domain == "F5-DECISION":
        parents("observation_refs", "F2-OBSERVATION")
        tick = _record(d["sequence_tick_ref"], "sequence_ref tick_order tick_id")
        validate_parent_ref_shape(tick["sequence_ref"], "TEMPORAL-SEQUENCE")
        validate_integer(tick["tick_order"])
        _text(tick["tick_id"])
        checked.append("sequence_tick_ref")
        resource("policy_ref", "POLICY")
        resource("decision_execution_rules_ref", "EXECUTION_RULES")
        if type(d["action"]) is dict and "resource_kind" in d["action"]:
            resource("action", "ACTION")
        else:
            _unavailable(d["action"], ("not_evaluated", "not_applicable"))
            checked.append("action")
    elif domain == "F5-EVALUATION":
        parents("decision_refs", "F5-DECISION")
        resources("outcome_refs", ("OUTCOME", "PRICE"))
        resource("evaluation_policy_ref", "EVALUATION_PROTOCOL")
        resources("limitations", ("LIMITATION",), 0)
    # F2 qualification and remaining complex value/metric/code fields deliberately
    # stay opaque: unavailable owner semantics must not become full-domain success.
    return ShapeInspection(
        checked_positions=tuple(checked),
        uninspected_fields=tuple(k for k in desc.semantic_fields if k not in checked),
        blockers=(
            "RESOURCE_SEMANTICS_NOT_SUPPLIED",
            "DOMAIN_SEMANTICS_NOT_SUPPLIED",
            "PARENT_EXISTENCE_FRESHNESS_RIGHTS_NOT_SUPPLIED",
            "TIME_AND_SCHEDULE_SEMANTICS_NOT_SUPPLIED",
        ),
    )
