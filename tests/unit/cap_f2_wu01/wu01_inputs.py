"""Input-only, bounded adapter. The sole fixture capability is fixed materialize()."""

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from types import ModuleType

from pit_research_lab.domain.contracts import (
    SCHEMA,
    AssertionFacts,
    AwareInstant,
    BlockingFailure,
    CandidateProfile,
    CaptureEdge,
    CaptureFacts,
    ContentFacts,
    ContentInventoryRequest,
    ContentPin,
    ContractError,
    ExactUnitMapping,
    FieldOrigin,
    IssuerBindingRequest,
    Known,
    NotApplicable,
    NumericContract,
    OriginKnownValue,
    OriginUnknownValue,
    ProviderCaptureRequest,
    PublicationEventFacts,
    Record,
    RequestBindingAttempt,
    RequestedTuple,
    RoleRef,
    S1Request,
    S1Scope,
    SemanticContext,
    SourceRecords,
    SubjectComparisonRequest,
    SubjectFacts,
    SubjectOperand,
    SupportBinding,
    TemporalPolicy,
    TimeProof,
    Unknown,
    UnknownCause,
    Visibility,
    int64,
    require,
)

NA = NotApplicable("S1", "NO_SOURCE_REFERENCE")
NODE_FIELDS = (
    "content_versions",
    "assertions",
    "subjects",
    "publication_events",
    "evidence",
    "supports",
    "time_proofs",
    "observations",
    "relations",
    "reports",
)
OUTER = {
    "case_id",
    "delta_id",
    "request",
    "active_discovery_membership",
    "auxiliary_comparison_inputs",
    "dependency_only_or_fault_schedule_inputs",
    "audit_annotations",
    "feature_specs",
    "calendar",
    "universe",
    "grid",
    "numeric_contract",
    "decision_wall_times",
    "contract_metadata",
    "provenance",
}
# Physical input pins from accepted INV2/P0, not expected domain answers or approval hashes.
RAW_PINS = (
    ("CV-APR-01", 396, "9debdebac6c31095cdcc1717506db150d58b74f05891ed05b1e5277f81a53849"),
    ("CV-MAY-01", 396, "f116159a328451978276d08f8f5e0b1c52d309d725caab4b64acb6b9b45d7776"),
    ("CV-JUN-01", 542, "b2b9e4ab15b1af3bacb475a0786469368c82e40a50779026b8dbd7f6c1a8cacc"),
    ("CV-JUN-02", 542, "8aa94499ab2c75362b4d4b279e426888c7326dab340eee0516944b8aa50f845c"),
    ("CV-A01-C01-APR-NTD", 410, "69b03e5477af4fb8164885251de933a106d8ed534d9cb9fa687d5cc9b9141b81"),
    ("CV-A01-C02-H1-Q2", 682, "759a7ada41bedbb6424effbbe9256ee6e88e2eca7b0186c070c5b7a1151d4fe2"),
    ("CV-JUN-PEER", 406, "50056e7bbce8546b9163e31dc4245efdfe381bb694e659377ced36ac1bcfd3fb"),
    (
        "CV-A01-C04-SCOPE-UNKNOWN",
        412,
        "8881bec36cc5758412bb3c2ddbfcef0fc951d5c9672cf2b2d2227830fc3e924d",
    ),
    (
        "CV-A02-C04-PX-CAPTURE",
        237,
        "2adcf78f2a9e3d8b141adda02d0fa6e6d80799a15d6fd8c36fa83063de7212a8",
    ),
)


def origin(visibility, pointer, object_id=None, schema=None, raw_digest=None):
    def leaf(value):
        if value is not None:
            return OriginKnownValue(value)
        return OriginUnknownValue(UnknownCause.ABSENT_SOURCE_FIELD)

    return FieldOrigin(visibility, pointer, leaf(object_id), leaf(schema), leaf(raw_digest))


CALLER = origin(Visibility.CALLER, "/invocation")


def synthetic_scope(scope, *, supports=None, captures=None, events=None, capture_edges=None):
    """Construct a NEW synthetic reference before a test's challenged invocation.

    Explicit fixture-construction only: adversarial mutations must keep this
    reference fixed. No domain code calls this helper or derives its own witness.
    """
    source = scope.source_records
    return replace(
        scope,
        source_records=SourceRecords(
            scope.input_members,
            scope.raw_pins,
            source.supports if supports is None else tuple(supports),
            source.captures if captures is None else tuple(captures),
            source.events if events is None else tuple(events),
            source.capture_edges if capture_edges is None else tuple(capture_edges),
        ),
    )


def synthetic_proof(request, proof):
    """A deliberate new source-time fixture, distinct from a forged binding."""
    attempt = request.attempts[0]
    binding = replace(attempt.supplied, proof_candidate=proof)
    supports = tuple(
        binding if s.support_ref == binding.support_ref else s
        for s in request.scope.source_records.supports
    )
    return replace(
        request,
        attempts=(replace(attempt, supplied=binding),),
        scope=synthetic_scope(request.scope, supports=supports),
    )


@dataclass(frozen=True)
class InvocationSelector(Record):
    operation: str
    concrete_targets: tuple[str, ...]
    supplied_support_ref: str | NotApplicable
    allowed_visibility: tuple[Visibility, ...]

    def __post_init__(self):
        super().__post_init__()
        require(
            self.operation in {"COMPARE_SUBJECTS", "CHECK_BINDING", "INVENTORY_CONTENT"},
            "UNSUPPORTED_OPERATION",
        )
        require(bool(self.concrete_targets), "MISSING_TARGET")
        require(
            set(self.allowed_visibility) <= {Visibility.ACTIVE, Visibility.AUXILIARY},
            "FORBIDDEN_VISIBILITY",
        )


@dataclass(frozen=True)
class AdaptedS1Input(Record):
    context: SemanticContext
    request: S1Request
    selector: InvocationSelector
    source_members: tuple[RoleRef, ...]
    source_captures: tuple[CaptureFacts, ...]
    source_events: tuple[PublicationEventFacts, ...]
    source_assertion_refs: tuple[str, ...]
    source_attempt_refs: tuple[str, ...]


def materialize(case_id):
    """Expose only the reviewed materialized envelope, never the helper module."""
    path = Path(__file__).parent.parent / "cap_f2_wu00" / "wu00_inputs.py"
    require(not any(p.is_symlink() for p in (path, *path.parents)), "UNSAFE_HELPER_PATH")
    source = path.read_bytes()
    require(
        len(source) == 19372
        and hashlib.sha256(source).hexdigest()
        == "9663de3fe9cbce3c81b2e4222006c2ae97c5056bc82134a65417894fa54065b6",
        "HELPER_PIN_MISMATCH",
    )
    module = ModuleType("_wu01_fixed_materializer")
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module.materialize(case_id)


def materialize_input(case_id, selector, profile):
    """Bookkeeping ID reaches only the fixed input seam, never semantic decisions."""
    try:
        return adapt(materialize(case_id), selector, profile)
    except OSError:
        return BlockingFailure(
            "OPERATIONAL_ERROR",
            "REQUIRED_INPUT_UNAVAILABLE",
            (),
            "REQUIRED_INPUT_UNAVAILABLE",
            CALLER,
            selector.operation,
        )
    except (ContractError, KeyError, TypeError, ValueError) as error:
        code = str(error) if isinstance(error, ContractError) else "MATERIALIZED_CONTRACT_INVALID"
        return BlockingFailure("CONTRACT_VIOLATION", code, (), code, CALLER, selector.operation)


def _decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_SOURCE_KEY")
            result[key] = value
        return result

    def invalid(_):
        raise ContractError("INVALID_NUMERIC_TYPE")

    return json.loads(raw, object_pairs_hook=pairs, parse_float=invalid, parse_constant=invalid)


def _fact(record, key, field_origin):
    field_origin = replace(field_origin, envelope_pointer=field_origin.envelope_pointer + "/" + key)
    if key not in record:
        return Unknown(UnknownCause.ABSENT_SOURCE_FIELD, None, field_origin)
    if record[key] is None:
        return Unknown(UnknownCause.EXPLICIT_SOURCE_UNKNOWN, None, field_origin)
    require(type(record[key]) is str, "INVALID_SOURCE_FIELD_TYPE")
    return Known(record[key], field_origin)


def _raw(asset, visibility, pointer, metadata=None):
    require(asset["encoding"] == "utf8-literal", "UNSUPPORTED_RAW_ENCODING")
    require(type(asset["payload"]) is str and type(asset["byte_length"]) is int, "INVALID_RAW_TYPE")
    raw = asset["payload"].encode("utf-8")
    require(
        len(raw) == asset["byte_length"] and hashlib.sha256(raw).hexdigest() == asset["sha256"],
        "PINNED_INPUT_INVALID",
    )
    matching = [p for p in RAW_PINS if p[0] == asset["id"]]
    require(len(matching) == 1, "UNSUPPORTED_RAW_PROFILE")
    require(matching[0][1:] == (len(raw), asset["sha256"]), "IMMUTABLE_ID_CONFLICT")
    body = _decode(raw)
    require(body["content_version_id"] == asset["id"], "CONTENT_ID_MISMATCH")
    require(
        body["schema"] in {"synthetic-notice-v1", "synthetic-provider-capture-v1"},
        "UNSUPPORTED_SOURCE_SCHEMA",
    )
    o = origin(visibility, pointer, asset["id"], body["schema"], asset["sha256"])
    if body["schema"] == "synthetic-notice-v1":
        require(
            set(body)
            == {"schema", "content_version_id", "issuer_id", "source_locator", "statements"},
            "UNSUPPORTED_SOURCE_SCHEMA",
        )
        statements = tuple(s["assertion_id"] for s in body["statements"])
        for statement in body["statements"]:
            int64(statement["value"])
    else:
        require(
            set(body)
            == {
                "schema",
                "content_version_id",
                "provider_id",
                "source_locator",
                "subject_reference",
                "displayed_value",
                "unit",
            },
            "UNSUPPORTED_SOURCE_SCHEMA",
        )
        int64(body["displayed_value"])
        statements = ()
    metadata = {} if metadata is None else metadata
    for key in ("content_version_id", "issuer_id", "source_locator"):
        if key in metadata:
            require(metadata[key] == body.get(key), "SOURCE_METADATA_CONFLICT")
    representation = "REP-RAW-" + asset["id"]
    if metadata:
        require(metadata["raw_representation_id"] == representation, "RAW_REFERENCE_MISMATCH")
        require(tuple(metadata["statement_member_ids"]) == statements, "STATEMENT_MEMBERSHIP")
    facts = ContentFacts(
        asset["id"],
        representation,
        raw,
        len(raw),
        asset["sha256"],
        body["schema"],
        _fact(metadata, "source_id", o),
        _fact(body, "issuer_id", o),
        _fact(metadata if "provider_id" in metadata else body, "provider_id", o),
        _fact(body, "source_locator", o),
        statements,
        tuple(metadata.get("report_member_ids", ())),
        o,
    )
    return facts, body


def _instant(text, zone, precision, o):
    require(type(text) is str, "INVALID_INSTANT")
    return AwareInstant(text, zone, text[-6:], precision, o)


def _capture(row, o, kind="LAB_CAPTURE"):
    completed = (
        Known(_instant(row["completed_at"], row["timezone"], row["precision"], o), o)
        if row.get("completed_at") is not None
        else Unknown(UnknownCause.ABSENT_SOURCE_FIELD, None, o)
    )
    return CaptureFacts(
        row["observation_id"],
        row["raw_representation_id"],
        row["captured_sha256"],
        completed,
        _fact(row, "precision", o),
        kind,
        o,
    )


def _subject(row, content, pointer):
    o = replace(
        content.origin, envelope_pointer=pointer, object_id=OriginKnownValue(row["subject_id"])
    )
    period = tuple(date.fromisoformat(v) for v in row["period"])
    require(len(period) == 2, "INVALID_PERIOD")
    basis = _fact(row, "basis_id", o)
    require(isinstance(basis, Known), "UNSUPPORTED_BASIS_PROFILE")
    require(
        basis.value in {"BASIS-CONSOLIDATED-V1", "BASIS-UNMAPPED-A01-C04"},
        "UNSUPPORTED_BASIS_PROFILE",
    )
    return SubjectFacts(
        row["subject_id"],
        _fact(row, "issuer_id", o) if "issuer_id" in row else content.issuer_ref,
        _fact(row, "metric", o),
        Known("DURATION", o),
        Known(period[0], o),
        Known(period[1], o),
        _fact(row, "reporting_scope", o),
        basis,
        "KNOWN" if basis.value == "BASIS-CONSOLIDATED-V1" else "UNMAPPED",
        _fact(row, "currency", o),
        _fact(row, "unit", o),
        o,
    )


def _assertion(row, content, body, pointer):
    matches = [
        (i, r) for i, r in enumerate(body["statements"]) if r["assertion_id"] == row["assertion_id"]
    ]
    require(len(matches) == 1, "ASSERTION_RAW_BINDING")
    index, raw_statement = matches[0]
    require(
        {k: v for k, v in row.items() if k != "content_version_id"} == raw_statement,
        "ASSERTION_RAW_CONFLICT",
    )
    require(row["content_version_id"] == content.content_version_ref, "ASSERTION_CONTENT_MISMATCH")
    o = replace(
        content.origin, envelope_pointer=pointer, object_id=OriginKnownValue(row["assertion_id"])
    )
    result = AssertionFacts(
        row["assertion_id"],
        row["subject_id"],
        Known(row["value"], o),
        Known(row["unit"], o),
        tuple(date.fromisoformat(x) for x in row["period"]),
        row["content_version_id"],
        o,
    )
    target = RequestedTuple(
        "ASSERTION",
        result.assertion_ref,
        (result.subject_ref,),
        content.content_version_ref,
        content.representation_ref,
        "/statements/" + str(index),
        o,
    )
    return result, target


def _event(row, o):
    return PublicationEventFacts(
        row["event_id"],
        row["event_kind"],
        row["source_id"],
        row["issuer_id"],
        row["content_version_id"],
        o,
    )


def _support(row, view, visibility, pointer):
    evidence = view["evidence"][row["evidence_id"]]
    bindings = [b for b in evidence["bindings"] if b["target_id"] == row["target_id"]]
    require(len(bindings) == 1, "SUPPORT_EVIDENCE_BINDING")
    b = bindings[0]
    for key in (
        "target_kind",
        "target_id",
        "subject_scope_ids",
        "content_version_id",
        "fragment_selector",
    ):
        require(row[key] == b[key], "SUPPORT_EVIDENCE_CONFLICT")
    o = origin(visibility, pointer, row["support_id"])
    view_pointer = pointer.rsplit("/supports/", 1)[0]
    binding_index = evidence["bindings"].index(b)
    binding_origin = origin(
        visibility,
        view_pointer + "/evidence/" + evidence["evidence_id"] + "/bindings/" + str(binding_index),
        evidence["evidence_id"],
    )
    target = RequestedTuple(
        row["target_kind"].upper(),
        row["target_id"],
        tuple(row["subject_scope_ids"]),
        row["content_version_id"],
        b["raw_representation_id"],
        row["fragment_selector"],
        binding_origin,
    )
    event = NA
    if b["event_ref"]:
        event_origin = origin(
            visibility, view_pointer + "/publication_events/" + b["event_ref"], b["event_ref"]
        )
        event = _event(view["publication_events"][b["event_ref"]], event_origin)
    proof = NA
    if b["time_proof_ref"]:
        p = view["time_proofs"][b["time_proof_ref"]]
        require(p["proof_kind"] == "exact", "UNSUPPORTED_S1_PROOF_PROFILE")
        proof_origin = origin(
            visibility, view_pointer + "/time_proofs/" + p["proof_id"], p["proof_id"]
        )
        proof = TimeProof(
            p["proof_id"],
            p["target_kind"].upper(),
            p["target_id"],
            p["content_version_id"],
            p["fragment_selector"],
            _instant(p["timestamp"], p["timezone"], p["precision"], proof_origin),
            tuple(sorted(p.items())),
            proof_origin,
        )
    return SupportBinding(
        row["support_id"], evidence["evidence_id"], target, b["attestation_scope"], event, proof, o
    )


def adapt(envelope, selector, profile):
    """Copy/freeze only the materialized envelope; source uncertainty remains uncertainty."""
    try:
        require(isinstance(profile, CandidateProfile), "UNSUPPORTED_PROFILE")
        require(isinstance(selector, InvocationSelector), "UNSUPPORTED_SELECTOR")
        require(set(envelope) == OUTER, "MATERIALIZED_OUTER_SCHEMA")
        require(profile.contract_ref == SCHEMA, "UNSUPPORTED_PROFILE")
        active = envelope["active_discovery_membership"]
        require(set(active) == {"facts", "receipts", "pages"}, "ACTIVE_OUTER_SCHEMA")
        views = [(Visibility.ACTIVE, "/active_discovery_membership/facts", active["facts"])]
        auxiliary = []
        for index, item in enumerate(envelope["auxiliary_comparison_inputs"]):
            pointer = "/auxiliary_comparison_inputs/" + str(index)
            if set(item) == {*NODE_FIELDS, "raw_assets", "graph_edges"}:
                views.append((Visibility.AUXILIARY, pointer, item))
            elif set(item) in (
                {"request", "raw_asset", "assertion"},
                {"raw_asset", "observation", "graph_edges"},
            ):
                auxiliary.append((pointer, item))
            else:
                raise ContractError("UNSUPPORTED_AUXILIARY_VARIANT")
        members = []
        contents, bodies, assertions, subjects, targets, supports = {}, {}, {}, {}, {}, {}
        captures, events = [], []
        pins = {}
        for visibility, pointer, view in views:
            require(set(view) == {*NODE_FIELDS, "raw_assets", "graph_edges"}, "FACTS_SCHEMA")
            for field in NODE_FIELDS:
                for identity in sorted(view[field]):
                    identity_key = {
                        "content_versions": "content_version_id",
                        "assertions": "assertion_id",
                        "subjects": "subject_id",
                        "publication_events": "event_id",
                        "evidence": "evidence_id",
                        "supports": "support_id",
                        "time_proofs": "proof_id",
                        "observations": "observation_id",
                        "relations": "relation_id",
                        "reports": "report_id",
                    }[field]
                    require(
                        view[field][identity][identity_key] == identity, "SOURCE_IDENTITY_CONFLICT"
                    )
                    members.append(RoleRef(visibility, field, identity, pointer + "/" + field))
            for representation, asset in view["raw_assets"].items():
                content, body = _raw(
                    asset,
                    visibility,
                    pointer + "/raw_assets/" + representation,
                    view["content_versions"].get(asset["id"]),
                )
                contents[(visibility, content.content_version_ref)] = content
                bodies[(visibility, content.content_version_ref)] = body
                pin = ContentPin(
                    content.content_version_ref,
                    representation,
                    content.raw_length,
                    content.raw_sha256,
                )
                if representation in pins:
                    require(pins[representation] == pin, "IMMUTABLE_ID_CONFLICT")
                pins[representation] = pin
                members.append(RoleRef(visibility, "raw_assets", representation, pointer))
            for identity, row in view["assertions"].items():
                # Unrequested Orders facts remain visible membership, not revenue operands.
                if "basis_id" not in row:
                    continue
                content = contents[(visibility, row["content_version_id"])]
                assertion, target = _assertion(
                    row,
                    content,
                    bodies[(visibility, content.content_version_ref)],
                    pointer + "/assertions/" + identity,
                )
                assertions[(visibility, identity)] = assertion
                targets[(visibility, identity)] = target
                subject = _subject(
                    view["subjects"][row["subject_id"]],
                    content,
                    pointer + "/subjects/" + row["subject_id"],
                )
                for field in ("period", "metric", "reporting_scope", "basis_id", "currency"):
                    require(
                        row.get(field) == view["subjects"][row["subject_id"]].get(field),
                        "ASSERTION_SUBJECT_CONFLICT",
                    )
                subjects[(visibility, row["subject_id"])] = subject
            for identity, row in view["supports"].items():
                supports[(visibility, identity)] = _support(
                    row, view, visibility, pointer + "/supports/" + identity
                )
            for identity, row in view["observations"].items():
                captures.append(
                    _capture(
                        row, origin(visibility, pointer + "/observations/" + identity, identity)
                    )
                )
            for identity, row in view["publication_events"].items():
                events.append(
                    _event(
                        row,
                        origin(visibility, pointer + "/publication_events/" + identity, identity),
                    )
                )
            edges = view["graph_edges"]
            require(len({e["id"] for e in edges}) == len(edges), "DUPLICATE_GRAPH_EDGE")
            members.extend(RoleRef(visibility, "graph_edges", e["id"], pointer) for e in edges)
        for role in ("receipts", "pages"):
            ids = [a["id"] for a in active[role]]
            require(len(set(ids)) == len(ids), "DUPLICATE_MEMBERSHIP")
            members.extend(
                RoleRef(Visibility.ACTIVE, role, x, "/active_discovery_membership/" + role)
                for x in ids
            )
        provider = None
        auxiliary_requests = []
        for pointer, item in auxiliary:
            content, body = _raw(item["raw_asset"], Visibility.AUXILIARY, pointer + "/raw_asset")
            key = (Visibility.AUXILIARY, content.content_version_ref)
            contents[key], bodies[key] = content, body
            pins[content.representation_ref] = ContentPin(
                content.content_version_ref,
                content.representation_ref,
                content.raw_length,
                content.raw_sha256,
            )
            members.append(
                RoleRef(
                    Visibility.AUXILIARY,
                    "raw_assets",
                    content.representation_ref,
                    pointer + "/raw_asset",
                )
            )
            if "assertion" in item:
                row = item["assertion"]
                assertion, target = _assertion(row, content, body, pointer + "/assertion")
                assertions[(Visibility.AUXILIARY, assertion.assertion_ref)] = assertion
                targets[(Visibility.AUXILIARY, assertion.assertion_ref)] = target
                members.append(
                    RoleRef(
                        Visibility.AUXILIARY,
                        "assertions",
                        assertion.assertion_ref,
                        pointer + "/assertion",
                    )
                )
                auxiliary_requests.append(item["request"])
            else:
                require(provider is None, "DUPLICATE_PROVIDER_REQUEST")
                capture = _capture(
                    item["observation"],
                    origin(
                        Visibility.AUXILIARY,
                        pointer + "/observation",
                        item["observation"]["observation_id"],
                    ),
                    "PROVIDER_CAPTURE",
                )
                captures.append(capture)
                edges = tuple(
                    CaptureEdge(
                        e["id"],
                        e["from"],
                        e["to"],
                        e["type"],
                        origin(Visibility.AUXILIARY, pointer + "/graph_edges/" + str(i), e["id"]),
                    )
                    for i, e in enumerate(item["graph_edges"])
                )
                provider = (content, body, capture, edges)
                members.append(
                    RoleRef(
                        Visibility.AUXILIARY,
                        "observations",
                        capture.observation_ref,
                        pointer + "/observation",
                    )
                )
                members.extend(
                    RoleRef(Visibility.AUXILIARY, "graph_edges", e.edge_ref, pointer) for e in edges
                )
        for field, visibility in (
            ("dependency_only_or_fault_schedule_inputs", Visibility.DEPENDENCY),
            ("audit_annotations", Visibility.AUDIT),
        ):
            for index, item in enumerate(envelope[field]):
                identity = hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()
                members.append(
                    RoleRef(visibility, "opaque", identity, "/" + field + "/" + str(index))
                )
        scope = S1Scope(
            tuple(sorted(members, key=lambda m: m.key)), tuple(pins[k] for k in sorted(pins))
        )
        # Resolve source-side records before selecting/challenging request bindings.
        scope = replace(
            scope,
            source_records=SourceRecords(
                scope.input_members,
                scope.raw_pins,
                tuple(supports.values()),
                tuple(captures),
                tuple(events),
                provider[3] if provider is not None else (),
            ),
        )
        request = envelope["request"]
        o = origin(Visibility.ACTIVE, "/request", request["context_id"])
        require(
            envelope["numeric_contract"]["type"] == "signed_int64", "UNSUPPORTED_NUMERIC_CONTRACT"
        )
        numeric = NumericContract(
            **{
                "numeric_ref": envelope["numeric_contract"]["id"],
                **{
                    k: envelope["numeric_contract"][k]
                    for k in ("minimum", "maximum", "unit", "allow_float", "allow_bool")
                },
            }
        )
        context = SemanticContext(
            request["context_id"],
            _instant(
                request["decision_cutoff"],
                envelope["contract_metadata"]["timezone"],
                envelope["contract_metadata"]["precision"],
                o,
            ),
            request["mode"],
            request["target_ref"],
            request["evidence_set_ref"],
            envelope["calendar"]["calendar_id"],
            tuple(request["policy_refs"]),
            numeric.numeric_ref,
            profile,
            tuple(envelope["decision_wall_times"]),
            _fact(request, "computation_attempt_time", o),
            request["spec_ref"],
            tuple(request["fit_state_refs"]),
            TemporalPolicy(),
            o,
        )

        def resolve(table, identity):
            matches = [
                value
                for (visibility, ref), value in table.items()
                if ref == identity and visibility in selector.allowed_visibility
            ]
            require(len(matches) == 1, "AMBIGUOUS_OR_MISSING_OPERAND")
            return matches[0]

        def operand(identity):
            found = [
                (key, value)
                for key, value in assertions.items()
                if key[1] == identity and key[0] in selector.allowed_visibility
            ]
            if not found:
                subject = resolve(subjects, identity)
                return SubjectOperand(subject, NA, (), (), (), ())
            require(len(found) == 1, "AMBIGUOUS_OPERAND")
            (visibility, _), assertion = found[0]
            content = contents[(visibility, assertion.content_version_ref)]
            subject = subjects[(visibility, assertion.subject_ref)]
            own = tuple(
                s
                for (v, _), s in supports.items()
                if v == visibility and s.target.target_ref == identity
            )
            own_events = tuple(
                e
                for e in events
                if e.origin.visibility == visibility
                and e.content_version_ref == content.content_version_ref
            )
            own_captures = tuple(
                c
                for c in captures
                if c.origin.visibility == visibility
                and c.representation_ref == content.representation_ref
            )
            return SubjectOperand(subject, assertion, (content,), own, own_events, own_captures)

        attempt_refs = ()
        if selector.operation == "COMPARE_SUBJECTS":
            require(len(selector.concrete_targets) == 2, "INVALID_OPERANDS")
            if "comparison_pair" in request:
                require(
                    tuple(request["comparison_pair"]) == selector.concrete_targets,
                    "SELECTOR_REQUEST_MISMATCH",
                )
            left, right = (operand(x) for x in selector.concrete_targets)
            mapping = NA
            if "unit_mapping" in request:
                m = request["unit_mapping"]
                subject = left.subject
                mapping = ExactUnitMapping(
                    m["mapping_id"],
                    profile.mapping_ref,
                    m["from_unit"],
                    m["to_unit"],
                    m["numerator"],
                    m["denominator"],
                    subject.subject_ref,
                    tuple(
                        (key, str(fact.value))
                        for key, fact in (
                            ("entity", subject.economic_entity_ref),
                            ("period_start", subject.period_start),
                            ("period_end", subject.period_end),
                            ("basis", subject.basis_ref),
                        )
                        if isinstance(fact, Known)
                    ),
                    origin(Visibility.CALLER, "/request/unit_mapping", m["mapping_id"]),
                )
            result = SubjectComparisonRequest(left, right, mapping, numeric, scope)
        elif provider is not None:
            content, body, capture, edges = provider
            require(
                selector.operation == "CHECK_BINDING"
                and selector.concrete_targets == (capture.observation_ref,)
                and Visibility.AUXILIARY in selector.allowed_visibility,
                "SELECTOR_REQUEST_MISMATCH",
            )
            target = RequestedTuple(
                "PROVIDER_CAPTURE",
                capture.observation_ref,
                (body["subject_reference"],),
                content.content_version_ref,
                content.representation_ref,
                NA,
                content.origin,
            )
            result = ProviderCaptureRequest(
                target,
                content,
                capture,
                edges,
                _fact(body, "subject_reference", content.origin),
                Known(body["displayed_value"], content.origin),
                Known(body["unit"], content.origin),
                scope,
            )
        else:
            identity = selector.concrete_targets[0]
            assertion = resolve(assertions, identity)
            target = resolve(targets, identity)
            content = contents[(assertion.origin.visibility, assertion.content_version_ref)]
            if selector.operation == "INVENTORY_CONTENT":
                require(
                    selector.concrete_targets == (identity, content.content_version_ref),
                    "SELECTOR_REQUEST_MISMATCH",
                )
                result = ContentInventoryRequest(
                    target, content, tuple(captures), tuple(events), tuple(supports.values()), scope
                )
                attempt_refs = tuple(
                    s.support_ref for s in supports.values() if s.target.target_ref == identity
                )
            else:
                source_requests = auxiliary_requests or [request]
                require(len(source_requests) == 1, "AMBIGUOUS_REQUEST")
                supplied = source_requests[0]
                require(
                    supplied["target_assertion_ref"] == identity
                    and supplied["supplied_support_ref"] == selector.supplied_support_ref,
                    "SELECTOR_REQUEST_MISMATCH",
                )
                support = resolve(supports, selector.supplied_support_ref)
                result = IssuerBindingRequest(
                    target,
                    content,
                    assertion,
                    (RequestBindingAttempt(target, support),),
                    tuple(captures),
                    tuple(events),
                    scope,
                )
                attempt_refs = (support.support_ref,)
        return AdaptedS1Input(
            context,
            result,
            selector,
            scope.input_members,
            tuple(captures),
            tuple(events),
            tuple(sorted({m.object_ref for m in members if m.role == "assertions"})),
            attempt_refs,
        )
    except (ContractError, KeyError, TypeError, ValueError, IndexError) as error:
        code = str(error) if isinstance(error, ContractError) else "MATERIALIZED_CONTRACT_INVALID"
        operation = (
            selector.operation if isinstance(selector, InvocationSelector) else "ADAPT_INPUT"
        )
        return BlockingFailure("CONTRACT_VIOLATION", code, (), code, CALLER, operation)
