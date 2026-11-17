"""Closed AD01-09 navigation metadata, never a positive domain parser or issuer."""

from dataclasses import dataclass
from types import MappingProxyType

from .canonical_codec import DOMAINS, PROFILE, CodecRefusal

REGISTRY_VERSION = "can02-structural-v0.1"
RESOURCE_ROLES = frozenset(
    """CALENDAR TEMPORAL_CONFIGURATION DECISION_SCHEDULE MANIFEST SOURCE_VERSION_HISTORY
    SOURCE_VERSION COVERAGE SEMANTIC_TRACE NATIVE_RECEIPT SEMANTIC_EVIDENCE
    OBSERVATION_RELEASE_POLICY OBSERVATION_RELEASE_RECEIPT AUDIT_ACCESS_POLICY
    READER_CAPABILITY_POLICY ASSOCIATION_PROTOCOL EXPERIMENT_ASSOCIATION AUTHOR_RECORD
    OWNER_DECISION METHOD HYPOTHESIS PROTOCOL HORIZON_MATURITY EVALUATION_PLAN POLICY
    EXECUTION_RULES EVALUATION_PROTOCOL POLICY_EVALUATION_PROTOCOL OUTCOME PRICE
    NUMERIC_POLICY TIMEZONE_RULES PROJECTION_POLICY SOURCE_TEXT ORIGIN RESULT_METRIC
    LIMITATION ACTION SCHEDULE_INVARIANT_POLICY SOURCE_CADENCE STATE""".split()
)
SUBJECT_DOMAINS = tuple(n for n in DOMAINS if n not in ("EVIDENCE", "F3-RUN-ATTEMPT"))
PROVENANCE_DOMAINS = tuple(n for n in DOMAINS if n != "EVIDENCE")
REALIZED_DOMAINS = ("SOURCE-BYTES", "F2-QUALIFICATION", "F2-OBSERVATION", "TEMPORAL-SEQUENCE")


@dataclass(frozen=True, slots=True)
class ReferenceRole:
    """Declared field path; [] preserves order, alternatives are conditional unions."""

    path: str
    parent_domains: tuple[str, ...] = ()
    resource_roles: tuple[str, ...] = ()
    condition: str = "required"


@dataclass(frozen=True, slots=True)
class DomainDescriptor:
    name: str
    domain_tag: str
    object_schema_version: str
    canonical_profile_version: str
    semantic_fields: tuple[str, ...]
    references: tuple[ReferenceRole, ...]
    resource_navigation: tuple[str, ...]
    scoped_complete_positive: bool
    issuable: bool = False
    resource_semantics: str = "RESOURCE_SEMANTICS_NOT_SUPPLIED"


def _parent(path: str, *domains: str, condition: str = "required") -> ReferenceRole:
    return ReferenceRole(path, domains, condition=condition)


def _resource(path: str, *roles: str, condition: str = "required") -> ReferenceRole:
    return ReferenceRole(path, resource_roles=roles, condition=condition)


# AD01-09 exact top-level fields, with the profile included explicitly below.
_FIELDS = (
    "body_byte_length body_sha256",
    "source_body_refs manifest_ref calendar_ref cutoff context_ref feature_cohort coverage_ref "
    "native_semantic_trace_ref rules_code_refs qualification_state scope",
    "qualification_ref tick_context issuer_ref feature_values projection_policy_ref release_policy_ref scope",
    "configuration_ref schedule_ref bindings annotations release_state provenance_ref scope",
    "hypothesis input_binding method protocol_ref horizon_maturity_ref seed evaluation_plan_ref",
    "attempt_id experiment_ref operation_receipt_ref result_ref",
    "experiment_ref realized_input_refs code_protocol_refs typed_results limitations",
    "subject_ref semantic_audit_ref source_code_protocol_refs limitations evidence_claim",
    "sequence_tick_ref policy_ref observation_refs action decision_execution_rules_ref",
    "decision_refs outcome_refs evaluation_policy_ref metrics limitations",
)
_REFERENCES = (
    (),
    (
        _parent("source_body_refs[].body_ref", "SOURCE-BYTES"),
        _resource("source_body_refs[].version_ref", "SOURCE_VERSION"),
        _resource("source_body_refs[].revision_history_ref", "SOURCE_VERSION_HISTORY"),
        _resource("manifest_ref", "MANIFEST"),
        _resource("calendar_ref", "CALENDAR"),
        _resource("coverage_ref", "COVERAGE"),
        _resource("native_semantic_trace_ref", "SEMANTIC_TRACE"),
    ),
    (
        _parent("qualification_ref", "F2-QUALIFICATION"),
        _resource("projection_policy_ref", "PROJECTION_POLICY"),
        _resource("release_policy_ref", "OBSERVATION_RELEASE_POLICY"),
    ),
    (
        _resource("configuration_ref", "TEMPORAL_CONFIGURATION"),
        _resource("schedule_ref", "DECISION_SCHEDULE"),
        _resource("bindings[].binding_ref", "SEMANTIC_TRACE"),
        _parent("bindings[].qualification_ref", "F2-QUALIFICATION"),
        _parent("bindings[].observation_ref.ref", "F2-OBSERVATION", condition="available"),
        _resource(
            "bindings[].observation_ref.policy_ref",
            "OBSERVATION_RELEASE_POLICY",
            condition="withheld",
        ),
        _resource("annotations[].calendar_ref", "CALENDAR"),
        _resource("release_state.release_policy_ref", "OBSERVATION_RELEASE_POLICY"),
        _resource("provenance_ref", "SEMANTIC_TRACE"),
    ),
    (
        _resource("hypothesis", "HYPOTHESIS"),
        _parent(
            "input_binding.temporal_binding_set_ref",
            "TEMPORAL-SEQUENCE",
            condition="SEQUENCE; contract version only",
        ),
        _parent("input_binding.observation_ref", "F2-OBSERVATION", condition="SINGLE_CUTOFF"),
        _resource(
            "input_binding.single_cutoff_contract_ref", "PROTOCOL", condition="SINGLE_CUTOFF"
        ),
        _resource("method", "METHOD"),
        _resource("protocol_ref", "PROTOCOL"),
        _resource("horizon_maturity_ref", "HORIZON_MATURITY"),
        _resource("evaluation_plan_ref", "EVALUATION_PLAN"),
    ),
    (
        _parent("experiment_ref", "F3-EXPERIMENT"),
        _resource("operation_receipt_ref", "NATIVE_RECEIPT"),
        _parent("result_ref.ref", "RESULT", condition="available; otherwise not_evaluated"),
    ),
    (
        _parent("experiment_ref", "F3-EXPERIMENT"),
        ReferenceRole(
            "realized_input_refs[]", REALIZED_DOMAINS, ("OUTCOME", "PRICE"), "selected union branch"
        ),
        _resource(
            "code_protocol_refs[].ref",
            "PROTOCOL",
            "NUMERIC_POLICY",
            "EVALUATION_PROTOCOL",
            condition="PROTOCOL; CODE uses CodePin",
        ),
        _resource("typed_results[].metric_ref", "RESULT_METRIC"),
        _resource("limitations[]", "LIMITATION", condition="0..4096"),
    ),
    (
        _parent("subject_ref", *SUBJECT_DOMAINS),
        _resource("semantic_audit_ref", "SEMANTIC_EVIDENCE"),
        ReferenceRole(
            "source_code_protocol_refs[]",
            PROVENANCE_DOMAINS,
            tuple(sorted(RESOURCE_ROLES)),
            "full conditional ProvenanceParent union",
        ),
        _resource("limitations[]", "LIMITATION", condition="0..4096"),
    ),
    (
        _parent("sequence_tick_ref.sequence_ref", "TEMPORAL-SEQUENCE"),
        _resource("policy_ref", "POLICY"),
        _parent("observation_refs[]", "F2-OBSERVATION"),
        _resource("action", "ACTION", condition="resource; otherwise not_evaluated/not_applicable"),
        _resource("decision_execution_rules_ref", "EXECUTION_RULES"),
    ),
    (
        _parent("decision_refs[]", "F5-DECISION"),
        _resource("outcome_refs[]", "OUTCOME", "PRICE"),
        _resource("evaluation_policy_ref", "EVALUATION_PROTOCOL"),
        _resource("metrics[].metric_ref", "RESULT_METRIC"),
        _resource("limitations[]", "LIMITATION", condition="0..4096"),
    ),
)
# Direct/helper navigation includes conditional branches; never transitive approval.
# TEMPORAL-SEQUENCE TimeRecord requires ORIGIN/TIMEZONE_RULES. EVIDENCE's
# explicit two roles do not narrow the full ProvenanceParent union above.
_NAVIGATION = (
    "",
    "CALENDAR COVERAGE MANIFEST NATIVE_RECEIPT ORIGIN SEMANTIC_TRACE SOURCE_VERSION SOURCE_VERSION_HISTORY SOURCE_TEXT TIMEZONE_RULES",
    "NUMERIC_POLICY OBSERVATION_RELEASE_POLICY ORIGIN PROJECTION_POLICY SOURCE_TEXT TIMEZONE_RULES",
    "CALENDAR DECISION_SCHEDULE OBSERVATION_RELEASE_POLICY SEMANTIC_TRACE TEMPORAL_CONFIGURATION SCHEDULE_INVARIANT_POLICY ORIGIN TIMEZONE_RULES",
    "EVALUATION_PLAN HORIZON_MATURITY HYPOTHESIS METHOD PROTOCOL",
    "NATIVE_RECEIPT",
    "EVALUATION_PROTOCOL LIMITATION NUMERIC_POLICY OUTCOME PRICE PROTOCOL RESULT_METRIC ORIGIN SOURCE_TEXT STATE",
    "LIMITATION SEMANTIC_EVIDENCE",
    "ACTION EXECUTION_RULES POLICY",
    "EVALUATION_PROTOCOL LIMITATION OUTCOME PRICE RESULT_METRIC ORIGIN NUMERIC_POLICY STATE SOURCE_TEXT",
)
DOMAIN_REGISTRY = MappingProxyType(
    {
        name: DomainDescriptor(
            name,
            f"PITLAB/ACADEMIC/{name}/candidate-v0.1",
            schema,
            PROFILE,
            ("canonical_profile_version", *fields.split()),
            refs,
            tuple(nav.split()),
            name == "SOURCE-BYTES",
        )
        for (name, schema), fields, refs, nav in zip(
            DOMAINS.items(), _FIELDS, _REFERENCES, _NAVIGATION, strict=True
        )
    }
)


def lookup_domain(name: str) -> DomainDescriptor:
    """Metadata lookup only: no parsing, resolution, issuance or rights."""
    if type(name) is not str or name not in DOMAIN_REGISTRY:
        raise CodecRefusal("DOMAIN_SCHEMA", "UNSUPPORTED_SCHEMA")
    return DOMAIN_REGISTRY[name]
