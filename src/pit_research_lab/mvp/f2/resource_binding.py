"""D04/D06 draft dependency checks, never Native execution or App issuance."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from pit_research_lab.mvp.f2.resource_bodies import (
    VERSION,
    DraftBody,
    accounting,
    annotation,
    native_summary,
    observation_ref,
    original_ref,
    parse_body,
    record,
    validate_body_key,
)
from pit_research_lab.mvp.f2.resource_contracts import (
    Check,
    ParentCore,
    ResourceError,
    ResourceKey,
    State,
    absent,
    array,
    closed,
    code_pin,
    items,
    literal,
    parent,
    ref,
    require,
    resource,
    safe_reason,
    scope,
    strict_json,
    tagged_integer,
    text,
    tick,
    time_record,
)

CUTOFFS = (
    "2027-01-07T18:00:00+08:00",
    "2027-01-15T18:00:00+08:00",
    "2027-01-29T18:00:00+08:00",
    "2027-02-05T18:00:00+08:00",
)
SELECTED_VERSIONS = ("D1", "D2", "D2", "D3")
SOURCE_TAGS = ("O", "N", "D1", "D2", "D3", "N12", "N23")
PACKET_SHA256 = "b9e1babbcc86b0e70ed5589972259fcbe6b666a38d2e7eff77d108f448e4dc0e"
PACKET_LENGTH = 5440756
SCHEDULE_INPUT_SCHEMA = "rs-spec-schedule-input-proposal-v0.1"
EXTERNAL_DECLARATIONS = frozenset(
    ("PROTOCOL", "HORIZON_MATURITY", "EXECUTION_RULES", "EVALUATION_PROTOCOL")
)
SEQ_FIELDS = frozenset(
    (
        "canonical_profile_version",
        "configuration_ref",
        "schedule_ref",
        "bindings",
        "annotations",
        "release_state",
        "provenance_ref",
        "scope",
    )
)


@dataclass(frozen=True, slots=True)
class SourceFact:
    tag: str
    raw: bytes
    raw_sha256: str
    packet_pointer: str
    publication_text: str
    publication_pointer: str
    # Original authored assertion, never an actual Native invocation receipt.
    content_version: str


def original_source_facts(packet: bytes) -> tuple[SourceFact, ...]:
    """Extract only pinned original facts; no schema adoption or history expansion."""
    require(
        len(packet) == PACKET_LENGTH and sha256(packet).hexdigest() == PACKET_SHA256,
        "ORIGINAL_PACKET_PIN_MISMATCH",
    )
    payload = strict_json(packet)
    sources = payload["sources"]
    require(tuple(s["tag"] for s in sources) == SOURCE_TAGS, "ORIGINAL_SEVEN_SOURCES")
    result = []
    for i, source in enumerate(sources):
        raw = source["raw"]["utf8"].encode("utf-8")
        require(
            len(raw) == source["raw"]["byte_length"]
            and sha256(raw).hexdigest() == source["raw"]["sha256"],
            "RAW_SOURCE_PIN",
        )
        notice = strict_json(raw)
        proof = source["source"]["request"]["attempts"][0]["supplied"]["proof_candidate"]
        pointer = f"/sources/{i}/source/request/attempts/0/supplied/proof_candidate/timestamp"
        result.append(
            SourceFact(
                source["tag"],
                raw,
                source["raw"]["sha256"],
                f"/sources/{i}/raw",
                proof["timestamp"]["source_text"],
                pointer,
                notice["content_version_id"],
            )
        )
    return tuple(result)


def source_body_prerequisites(packet: bytes) -> Check:
    original_source_facts(packet)
    return Check(
        State.NOT_SUPPLIED,
        (
            "ORIGIN_RESOURCE_AND_RIGHTS_NOT_SUPPLIED",
            "RULES_NOT_SUPPLIED",
            "SOURCE_BYTES_CODEC_NOT_SUPPLIED",
        ),
    )


def declared_before(publication: object, cutoff: object) -> bool:
    """Strict comparison of original declarations; not proof of named-zone validity."""
    return time_record(publication) < time_record(cutoff)


def time_rules_readiness(value: object, rules: DraftBody | None = None) -> Check:
    time_record(value)
    if rules is None:
        return Check(State.NOT_SUPPLIED, ("RULES_NOT_SUPPLIED",))
    require(rules.kind == "TIMEZONE_RULES", "RESOURCE_KIND")
    parse_body(rules.kind, rules.raw)
    # No reviewed rule source or canonical byte verification exists in this task.
    return Check(State.NOT_SUPPLIED, ("REVIEWED_RULE_SOURCE_AND_RIGHTS_NOT_SUPPLIED",))


def validate_four_ticks(value: object, annotations: object) -> None:
    ticks = array(value, 4, 4)
    ids, contexts = [], []
    for index, t in enumerate(ticks):
        tick(t)
        require(tagged_integer(t["tick_order"]) == index, "TICK_ORDER")
        require(t["decision_cutoff"]["source_text"] == CUTOFFS[index], "TICK_CUTOFF")
        ids.append(t["tick_id"])
        contexts.append(t["context_ref"])
    require(len(set(ids)) == len(set(contexts)) == 4, "DISTINCT_TICK_CONTEXTS")
    notes = array(annotations, 1, 1)
    annotation(notes[0])


@dataclass(frozen=True, slots=True)
class ScheduleInput:
    raw: bytes
    invariant_policy: ResourceKey
    original_inputs: tuple[ParentCore, ...]


def parse_schedule_input(raw: bytes) -> ScheduleInput:
    d = strict_json(raw)
    record(
        body_schema_label=literal(SCHEDULE_INPUT_SCHEMA),
        body_version=literal(VERSION),
        original_input_refs=items(parent),
        invariant_policy_ref=ref("SCHEDULE_INVARIANT_POLICY"),
        selected_profile=literal("FIXED_FOUR_WEEKLY_SYN_A"),
    )(d)
    refs = tuple(parent(v) for v in d["original_input_refs"])
    require(len(set(refs)) == len(refs), "DUPLICATE_INPUT")
    return ScheduleInput(
        raw, resource(d["invariant_policy_ref"], "SCHEDULE_INVARIANT_POLICY"), refs
    )


def schedule_path_check(
    source_input: ScheduleInput,
    schedule: DraftBody,
    *,
    supplied_input_core: ParentCore,
    invariant_policy_ref: object,
    sequence_schedule_ref: object,
    schedule_resource_ref: object,
    policy_body: DraftBody | None = None,
) -> Check:
    """A3/A4/A5/A6 structural comparisons. No canonical equality is asserted."""
    source_input = parse_schedule_input(source_input.raw)
    require(schedule.kind == "DECISION_SCHEDULE", "RESOURCE_KIND")
    schedule = parse_body(schedule.kind, schedule.raw)
    s = schedule.fields()
    validate_four_ticks([v["tick"] for v in s["ticks"]], s["annotations"])
    require(parent(s["source_input_ref"]) == supplied_input_core, "STALE_SCHEDULE_INPUT")
    require(
        source_input.invariant_policy
        == resource(invariant_policy_ref, "SCHEDULE_INVARIANT_POLICY"),
        "AF009_POLICY_MISMATCH",
    )
    sr = resource(schedule_resource_ref, "DECISION_SCHEDULE")
    require(sr == resource(sequence_schedule_ref, "DECISION_SCHEDULE"), "STALE_SEQUENCE_SCHEDULE")
    validate_body_key(sr, schedule)
    if policy_body is None:
        return Check(State.NOT_SUPPLIED, ("INVARIANT_POLICY_BODY_NOT_SUPPLIED",))
    require(policy_body.kind == "SCHEDULE_INVARIANT_POLICY", "RESOURCE_KIND")
    parse_body(policy_body.kind, policy_body.raw)
    validate_body_key(source_input.invariant_policy, policy_body)
    return Check(
        State.NOT_SUPPLIED,
        (
            "IMMUTABLE_SOURCE_BYTES_VERIFICATION_NOT_SUPPLIED",
            "POLICY_PROVENANCE_AND_RIGHTS_NOT_SUPPLIED",
        ),
    )


@dataclass(frozen=True, slots=True)
class ScheduleInfluence:
    """An inert dependency expression, NOT canonical bytes, hash or issued ref.

    Equality compares complete draft inputs including the policy ref. An actual
    schedule/SEQ ref can change only after independent Codec/Oracle gates.
    """

    input_body: bytes
    schedule_body: bytes
    edge: str = "SEQ.schedule_ref -> DECISION_SCHEDULE -> PF038 ScheduleInput"


def schedule_influence(source_input: ScheduleInput, schedule: DraftBody) -> ScheduleInfluence:
    parse_schedule_input(source_input.raw)
    require(schedule.kind == "DECISION_SCHEDULE", "RESOURCE_KIND")
    parse_body(schedule.kind, schedule.raw)
    return ScheduleInfluence(source_input.raw, schedule.raw)


def configuration_readiness(configuration: DraftBody) -> Check:
    require(configuration.kind == "TEMPORAL_CONFIGURATION", "RESOURCE_KIND")
    parse_body(configuration.kind, configuration.raw)
    return Check(
        State.NOT_SUPPLIED,
        tuple("OWNED_DECLARATION_NOT_SUPPLIED:" + role for role in sorted(EXTERNAL_DECLARATIONS)),
    )


type DependencyKey = ParentCore | ResourceKey


def typed_dependencies(value: object) -> Iterator[DependencyKey]:
    """Traverse declared typed parents only, preserving their source array order."""
    if type(value) is dict:
        if "resource_kind" in value:
            yield resource(value)
        elif "domain_tag" in value:
            for domain in (
                "SOURCE-BYTES",
                "F2-QUALIFICATION",
                "F2-OBSERVATION",
                "TEMPORAL-SEQUENCE",
            ):
                if value["domain_tag"] == f"PITLAB/ACADEMIC/{domain}/candidate-v0.1":
                    yield parent(value, domain)
                    break
            else:
                raise ResourceError("FORBIDDEN_PARENT_DOMAIN")
        else:
            for child in value.values():
                yield from typed_dependencies(child)
    elif type(value) is list:
        for child in value:
            yield from typed_dependencies(child)


@dataclass(frozen=True, slots=True)
class DraftNode:
    key: DependencyKey
    body: DraftBody | None
    classification: str  # SEMANTIC, OPAQUE_INPUT, ACTUAL_ATTEMPT, CORRESPONDENCE, FINAL_EVIDENCE


def semantic_ancestry(
    root: DependencyKey, nodes: Mapping[DependencyKey, DraftNode], trace_subtype: str = "QUAL_INPUT"
) -> Check:
    """Reject direct AND hidden attempt parents. Opaque bytes never prove safety."""
    require(
        trace_subtype in ("QUAL_INPUT", "PER_CUTOFF_BINDING", "SET_INPUT_MANIFEST"), "TRACE_SUBTYPE"
    )
    visiting: set[DependencyKey] = set()
    visited: set[DependencyKey] = set()
    blockers: list[str] = []

    def visit(key: DependencyKey, depth: int) -> None:
        # Implementation traversal budget only; CAN max-depth root ambiguity remains open.
        require(depth <= 64 and len(visited) < 16384, "DRAFT_GRAPH_BUDGET")
        require(key not in visiting, "REF_CYCLE")
        if isinstance(key, ParentCore):
            require(key.domain != "TEMPORAL-SEQUENCE", "FINAL_SEQUENCE_BACKEDGE")
            if trace_subtype == "QUAL_INPUT":
                require(key.domain == "SOURCE-BYTES", "QUAL_INPUT_BACKEDGE")
        if key in visited:
            return
        node = nodes.get(key)
        if node is None:
            blockers.append("DANGLING_PARENT_NOT_SUPPLIED")
            return
        require(node.key == key, "FOREIGN_NODE")
        require(
            node.classification not in ("ACTUAL_ATTEMPT", "CORRESPONDENCE", "FINAL_EVIDENCE"),
            "ATTEMPT_OR_FINAL_EVIDENCE_ANCESTRY",
        )
        require(node.classification in ("SEMANTIC", "OPAQUE_INPUT"), "NODE_CLASSIFICATION")
        if node.classification == "OPAQUE_INPUT" or node.body is None:
            blockers.append("SEMANTIC_INPUT_DECODER_NOT_SUPPLIED")
            return
        body = parse_body(node.body.kind, node.body.raw)
        if isinstance(key, ResourceKey):
            validate_body_key(key, body)
        visiting.add(key)
        for dependency in typed_dependencies(body.fields()):
            visit(dependency, depth + 1)
        visiting.remove(key)
        visited.add(key)

    visit(root, 0)
    return Check(
        State.NOT_SUPPLIED,
        tuple(
            dict.fromkeys(
                blockers + ["TRANSITIVE_BYTES_RIGHTS_AND_INDEPENDENT_REVIEW_NOT_SUPPLIED"]
            )
        ),
    )


def correspondence_record(raw: bytes) -> dict[str, Any]:
    d = strict_json(raw)
    record(
        schema_label=literal("rs-spec-audit-correspondence-proposal-v0.1"),
        record_revision=text,
        issuing_owner=text,
        declared_capture_scope=text,
        semantic_receipt_ref=ref("NATIVE_RECEIPT"),
        original_attempt_input_ref=parent,
        operation=text,
        original_attempt_key=text,
        tick_context=tick,
        semantic_projection_schema=text,
        relevant_code_refs=items(code_pin),
        correspondence=record(
            state=literal("MATCH", "MISMATCH", "NOT_EVALUATED"),
            reason=safe_reason,
            verifier_role=text,
        ),
        actual_invocation=literal("RUN", "ATTEMPTED", "NOT_RUN"),
        original_failure_pointer=lambda v: text(v) if type(v) is str else absent(v),
        original_observation_pointers=items(
            record(phase=literal("BEFORE", "PREINVOKE", "AFTER"), pointer=text), 0
        ),
        access_policy_ref=ref("AUDIT_ACCESS_POLICY"),
        resolution_receipt_link=lambda v: text(v) if type(v) is str else absent(v, "not_evaluated"),
    )(d)
    return d


def check_correspondence(raw: bytes | None, original_attempt: bytes | None = None) -> Check:
    if raw is None:
        return Check(State.NOT_EVALUATED, ("CORRESPONDENCE_NOT_SUPPLIED",))
    d = correspondence_record(raw)
    if original_attempt is None:
        return Check(State.NOT_EVALUATED, ("CORRESPONDENCE_NOT_SUPPLIED",))
    # Input MATCH is merely a claim. There is no original portable attempt format,
    # approved projection witness or reviewer grant at this baseline.
    if d["correspondence"]["state"] == "MATCH":
        return Check(
            State.NOT_EVALUATED, ("UNVERIFIED_MATCH_CLAIM", "ATTEMPT_WITNESS_NOT_SUPPLIED")
        )
    return Check(State.NOT_EVALUATED, ("ORIGINAL_ATTEMPT_SCHEMA_AND_REVIEW_NOT_SUPPLIED",))


def sealed_summary_readiness(value: object) -> Check:
    try:
        native_summary(value)
    except ResourceError as exc:
        if type(value) is dict and ("state" not in value or type(value["state"]) is not str):
            return Check(State.NOT_SUPPLIED, ("NATIVE_SUMMARY_NO_OUTCOME_AM_D04_3",))
        raise exc
    return Check(State.NOT_SUPPLIED, ("GENUINE_NATIVE_CORRESPONDENCE_NOT_SUPPLIED",))


def sequence_structure(
    value: object,
    binding_bodies: tuple[DraftBody, ...],
    schedule: DraftBody,
    set_input: DraftBody,
    *,
    expected_schedule_ref: object | None = None,
    expected_provenance_ref: object | None = None,
    expected_schedule_input_core: object | None = None,
    expected_manifest_ref: object | None = None,
    expected_original_source_refs: object | None = None,
    source_input: ScheduleInput | None = None,
    invariant_policy_ref: object | None = None,
) -> Check:
    """Validate the exact proposed SEQ field map without encoding/hashing it.

    Four complete test-only field structures can exercise ordering/consistency;
    this routine never returns an issued or eligible sequence, even if they match.
    Keyword expectations are independently supplied serialized typed refs, decoded
    below with resource/parent. They are never inferred from the SEQ under review.
    Matching declarations do not cryptographically bind any DraftBody to a core.
    """
    d = closed(value, " ".join(sorted(SEQ_FIELDS)))
    literal("typed-json-candidate-v0.1")(d["canonical_profile_version"])
    resource(d["configuration_ref"], "TEMPORAL_CONFIGURATION")
    schedule_key = resource(d["schedule_ref"], "DECISION_SCHEDULE")
    provenance_key = resource(d["provenance_ref"], "SEMANTIC_TRACE")
    scope(d["scope"])
    accounting(d["release_state"])
    members = array(d["bindings"], 4, 4)
    require(
        len(binding_bodies) == 4 and schedule.kind == "DECISION_SCHEDULE", "FOUR_BINDINGS_REQUIRED"
    )
    schedule = parse_body(schedule.kind, schedule.raw)
    s = schedule.fields()
    require(set_input.kind == "SEMANTIC_TRACE", "RESOURCE_KIND")
    set_input = parse_body(set_input.kind, set_input.raw)
    si = set_input.fields()["trace"]
    require(si["subtype"] == "SET_INPUT_MANIFEST", "SET_INPUT_SUBTYPE")
    blockers: list[str] = []
    if expected_schedule_ref is None:
        blockers.append("EXPECTED_SCHEDULE_REF_NOT_SUPPLIED")
    else:
        expected_schedule = resource(expected_schedule_ref, "DECISION_SCHEDULE")
        require(schedule_key == expected_schedule, "STALE_SEQUENCE_SCHEDULE")
        validate_body_key(expected_schedule, schedule)
    if expected_provenance_ref is None:
        blockers.append("EXPECTED_PROVENANCE_REF_NOT_SUPPLIED")
    else:
        expected_provenance = resource(expected_provenance_ref, "SEMANTIC_TRACE")
        require(provenance_key == expected_provenance, "STALE_SEQUENCE_PROVENANCE")
        validate_body_key(expected_provenance, set_input)
    if expected_schedule_input_core is None:
        blockers.append("EXPECTED_SCHEDULE_INPUT_CORE_NOT_SUPPLIED")
    else:
        expected_input = parent(expected_schedule_input_core)
        require(parent(s["source_input_ref"]) == expected_input, "STALE_SCHEDULE_INPUT")
    if expected_manifest_ref is None:
        blockers.append("EXPECTED_MANIFEST_REF_NOT_SUPPLIED")
    else:
        require(
            resource(si["manifest_ref"], "MANIFEST") == resource(expected_manifest_ref, "MANIFEST"),
            "SET_INPUT_MANIFEST_MISMATCH",
        )
    if expected_original_source_refs is None:
        blockers.append("EXPECTED_ORIGINAL_SOURCE_REFS_NOT_SUPPLIED")
    else:
        expected_sources = array(expected_original_source_refs)
        for source in expected_sources:
            original_ref(source)
        require(
            tuple(typed_dependencies(si["original_source_refs"]))
            == tuple(typed_dependencies(expected_sources)),
            "SET_INPUT_SOURCE_REFS_MISMATCH",
        )
    if invariant_policy_ref is None:
        blockers.append("INVARIANT_POLICY_REF_NOT_SUPPLIED")
    else:
        resource(invariant_policy_ref, "SCHEDULE_INVARIANT_POLICY")
    if source_input is None:
        blockers.append("SCHEDULE_INPUT_BODY_NOT_SUPPLIED")
    else:
        source_input = parse_schedule_input(source_input.raw)
        if invariant_policy_ref is not None:
            if expected_schedule_ref is not None and expected_schedule_input_core is not None:
                path = schedule_path_check(
                    source_input,
                    schedule,
                    supplied_input_core=parent(expected_schedule_input_core),
                    invariant_policy_ref=invariant_policy_ref,
                    sequence_schedule_ref=d["schedule_ref"],
                    schedule_resource_ref=expected_schedule_ref,
                )
                blockers.extend(path.reasons)
            else:
                # Missing unrelated expectations must not hide a known AF009 contradiction.
                require(
                    source_input.invariant_policy
                    == resource(invariant_policy_ref, "SCHEDULE_INVARIANT_POLICY"),
                    "AF009_POLICY_MISMATCH",
                )
    require(
        d["configuration_ref"] == s["configuration_ref"] and d["annotations"] == s["annotations"],
        "SCHEDULE_CONFIGURATION_MISMATCH",
    )
    validate_four_ticks([v["tick"] for v in members], d["annotations"])
    qualifications = []
    observations = []
    binding_refs = []
    for i, (member, body) in enumerate(zip(members, binding_bodies, strict=True)):
        m = closed(member, "tick binding_ref qualification_ref observation_ref scope")
        tick(m["tick"])
        binding_key = resource(m["binding_ref"], "SEMANTIC_TRACE")
        binding_refs.append(binding_key)
        qualifications.append(parent(m["qualification_ref"], "F2-QUALIFICATION"))
        observation_ref(m["observation_ref"])
        if m["observation_ref"]["type"] == "available":
            observations.append(parent(m["observation_ref"]["ref"], "F2-OBSERVATION"))
        scope(m["scope"])
        require(body.kind == "SEMANTIC_TRACE", "RESOURCE_KIND")
        validate_body_key(binding_key, body)
        b = parse_body(body.kind, body.raw).fields()["trace"]
        require(b["subtype"] == "PER_CUTOFF_BINDING", "BINDING_SUBTYPE")
        require(m["tick"] == b["tick"] == s["ticks"][i]["tick"], "BINDING_TICK_MISMATCH")
        require(m["binding_ref"] == si["binding_refs"][i], "SET_INPUT_BINDING_ORDER")
        require(
            m["qualification_ref"] == b["qualification_ref"]
            and m["observation_ref"] == b["observation_ref"],
            "BINDING_PARENT_MISMATCH",
        )
        require(m["scope"]["scope_flags"] == b["scope_flags"], "BINDING_SCOPE_MISMATCH")
    require(len(set(qualifications)) == 4, "DISTINCT_QUALIFICATION_CONTEXTS")
    require(len(set(binding_refs)) == 4, "DISTINCT_BINDING_CONTEXTS")
    require(len(set(observations)) == len(observations), "DISTINCT_OBSERVATION_CONTEXTS")
    # Declared graph equality only: no raw-byte/Codec/Oracle/rights verification.
    return Check(
        State.NOT_SUPPLIED,
        tuple(
            dict.fromkeys(
                blockers
                + [
                    "QUAL_OBS_AND_SOURCE_BYTES_VERIFICATION_NOT_SUPPLIED",
                    "IMMUTABLE_SOURCE_BYTES_VERIFICATION_NOT_SUPPLIED",
                    "INDEPENDENT_ORACLE_AND_CODEC_NOT_SUPPLIED",
                    "OWNED_DECLARATIONS_AND_RIGHTS_NOT_SUPPLIED",
                    "GENUINE_NATIVE_CORRESPONDENCE_NOT_SUPPLIED",
                ]
            )
        ),
    )
