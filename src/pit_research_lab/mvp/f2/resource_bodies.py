"""Closed, local NON_ISSUED body schemas for the accepted bounded RS design.

These descriptors validate input, not authority or canonical identity. Missing
external declarations, rules and actual attempts are handled by resource_binding.
SC PF/AF fields remain logical mappings, never automatic canonical serialization.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from pit_research_lab.mvp.f2.resource_contracts import (
    NUMERICAL_POLICY,
    Check,
    ResourceError,
    ResourceKey,
    State,
    absent,
    array,
    closed,
    code_pin,
    declared_taipei,
    fact,
    flags,
    items,
    literal,
    parent,
    ref,
    require,
    resource,
    safe_reason,
    scope,
    source_version_ref,
    strict_json,
    tagged_integer,
    text,
    tick,
    time_record,
    unknown,
)

VERSION = "0.1-DRAFT-NON_ISSUED"
type Validator = Callable[[object], object]


def schema_label(kind: str) -> str:
    return "rs-spec-" + kind.lower().replace("_", "-") + "-body-proposal-v0.1"


def record(**validators: Validator) -> Validator:
    def validate(value: object) -> None:
        d = closed(value, " ".join(validators))
        for key, validator in validators.items():
            validator(d[key])

    return validate


def unique(value: object, validator: Validator) -> None:
    entries = array(value)
    for index, entry in enumerate(entries):
        validator(entry)
        require(entry not in entries[:index], "DUPLICATE_ENTRY")


def local_date(value: object) -> str:
    raw = text(value, 10)
    try:
        require(date.fromisoformat(raw).isoformat() == raw, "DATE_FORMAT")
    except ValueError as exc:
        raise ResourceError("DATE_FORMAT") from exc
    return raw


def period(value: object) -> None:
    d = closed(value, "start_date end_date")
    require(local_date(d["start_date"]) <= local_date(d["end_date"]), "DATE_ORDER")


def native_failure(value: object) -> None:
    if type(value) is dict and value.get("type") == "not_applicable":
        absent(value)
        return
    record(type=literal("native_failure"), owner=text, category=text, code=text,
           affected_scope_refs=items(resource, 0), safe_diagnostic=text,
           origin_ref=ref("ORIGIN"), attempted_operation=text)(value)


def unknown_or_na(value: object) -> None:
    if type(value) is dict and value.get("type") == "unknown":
        unknown(value)
    else:
        absent(value)


def native_summary(value: object) -> None:
    # CAN-07: all eight fields mandatory; no-outcome must refuse, not invent state.
    record(owner=text, type=text, state=text, reason_code=text, unknown=unknown_or_na,
           first_failure=native_failure, invocation=literal("RUN", "ATTEMPTED", "NOT_RUN"),
           invocation_receipt_ref=ref("NATIVE_RECEIPT"))(value)


def retained_origin(value: object) -> None:
    require(type(value) is dict, "ORIGIN_FACT")
    if value.get("kind") == "KNOWN":
        record(kind=literal("KNOWN"), value=text)(value)
    else:
        from pit_research_lab.mvp.f2.resource_contracts import UNKNOWN_CAUSES

        def source_text(v: object) -> None:
            if type(v) is str:
                text(v)
            else:
                absent(v)

        record(kind=literal("UNKNOWN"), cause=literal(*sorted(UNKNOWN_CAUSES)),
               source_text=source_text)(value)


def original_ref(value: object) -> None:
    if type(value) is dict and "resource_kind" in value:
        resource(value, "MANIFEST", "SOURCE_VERSION", "SOURCE_VERSION_HISTORY", "COVERAGE", "CALENDAR")
    else:
        parent(value)


def known_or_unknown(value: object, known: Validator) -> None:
    require(type(value) is dict and value.get("type") in ("known", "unknown"), "FACT_TAG")
    fact(value, known)


def semantic_input(value: object) -> None:
    if type(value) is dict and "version_ref" in value:
        source_version_ref(value)
    elif type(value) is dict and "resource_kind" in value:
        resource(value, "MANIFEST", "COVERAGE", "CALENDAR", "NUMERIC_POLICY", "TIMEZONE_RULES")
    else:
        parent(value)


def annotation(value: object) -> None:
    record(iso_week=literal("2027-W03"), kind=literal("NO_SESSION_WEEK"),
           calendar_ref=ref("CALENDAR"))(value)


def accounting(value: object) -> None:
    d = closed(value, "scheduled_count accounted_count position_outcomes release_policy_ref")
    n = tagged_integer(d["scheduled_count"])
    m = tagged_integer(d["accounted_count"])
    require(n == m == 4, "POSITION_ACCOUNTING")
    outcomes = array(d["position_outcomes"], 4, 4)
    for reason in outcomes:
        safe_reason(reason)
    resource(d["release_policy_ref"], "OBSERVATION_RELEASE_POLICY")


def observation_ref(value: object) -> None:
    require(type(value) is dict, "OBSERVATION_TAG")
    if value.get("type") == "available":
        d = closed(value, "type ref")
        parent(d["ref"], "F2-OBSERVATION")
    else:
        fact(value, lambda _: require(False, "OBSERVATION_TAG"))
        require(value.get("type") == "withheld", "OBSERVATION_TAG")


def cohort(value: object) -> None:
    unique(value, record(issuer_ref=literal("SYN-A"), feature_ref=text))


def _native_state(value: object) -> None:
    if type(value) is str:
        text(value)
    else:
        absent(value, "not_evaluated")


def trace(value: object) -> None:
    require(type(value) is dict, "TRACE_REQUIRED")
    tag = value.get("subtype")
    common: dict[str, Validator] = {"subtype": literal(tag)}
    if tag == "QUAL_INPUT":
        common.update(semantic_input_refs=items(semantic_input), rules_code_refs=items(code_pin),
                      native_summary=native_summary, scope=scope)
    elif tag == "PER_CUTOFF_BINDING":
        common.update(
            object_schema_version=literal("per-cutoff-binding-candidate-v0.1"),
            limitations=items(text, 0), data_mode=literal("SYNTHETIC_GOLDEN"),
            source_refs=items(original_ref), tick=tick,
            manifest_source_versions=record(manifest_ref=ref("MANIFEST"),
                                            source_version_refs=items(source_version_ref),
                                            coverage_ref=ref("COVERAGE")),
            qualification_ref=lambda v: parent(v, "F2-QUALIFICATION"),
            audit_evidence_ref=ref("NATIVE_RECEIPT", "SEMANTIC_EVIDENCE"),
            observation_ref=observation_ref, native_summary=native_summary,
            app_axes=record(pit_status=literal("UNRESOLVED"),
                            execution_status=literal("NOT_RUN", "PENDING", "RUNNING", "SUCCEEDED", "FAILED", "BLOCKED"), evidence_class=literal("UNVERIFIED"),
                            execution_scope_ref=ref("PROTOCOL")),
            scope_flags=flags, selected_cohort=cohort,
            mismatch_reason=lambda v: absent(v) if type(v) is dict
            and v.get("type") == "not_applicable" else safe_reason(v),
        )
    elif tag == "SET_INPUT_MANIFEST":
        common.update(manifest_ref=ref("MANIFEST"),
                      binding_refs=items(ref("SEMANTIC_TRACE")),
                      semantic_limitations=items(text, 0), original_source_refs=items(original_ref))
        require(len(value.get("binding_refs", [])) == 4, "FOUR_BINDINGS_REQUIRED")
    else:
        raise ResourceError("TRACE_SUBTYPE")
    record(**common)(value)


_PUBLIC_FORBIDDEN = (
    "RAW_SOURCE", "NATIVE_AUDIT", "ATTEMPT", "TIMING", "TOKEN", "CALLBACK", "FUTURE_EVAL",
)


def projection(value: object) -> None:
    d = closed(value, "feature_rules allowed_tags safe_reason_rules scope_flags forbidden_surfaces")
    rules = array(d["feature_rules"], 2, 2)
    for rule, typ, unit in zip(rules, ("INT64", "FIXED_RATIO6"), ("NTD_thousands", "FRACTION"),
                               strict=True):
        record(feature_ref=text, value_type=literal(typ), unit=literal(unit),
               numeric_policy_ref=ref("NUMERIC_POLICY"))(rule)
    require(rules[0]["feature_ref"] != rules[1]["feature_ref"], "DUPLICATE_FEATURE")
    literal(["Known", "Unknown", "NotEvaluated", "Withheld"])(d["allowed_tags"])
    items(record(owner=text, native_code=text, safe_code=text), 0)(d["safe_reason_rules"])
    flags(d["scope_flags"])
    literal(list(_PUBLIC_FORBIDDEN))(d["forbidden_surfaces"])


SCHEMAS: dict[str, dict[str, Validator]] = {
    "ORIGIN": dict(source_input_ref=parent, input_pointer=text, fact_owner=text,
                   source_schema=retained_origin, object_id=retained_origin,
                   origin_kind=literal("AUTHORED_SYNTHETIC", "RETAINED_NATIVE_FIELD")),
    "SOURCE_VERSION": dict(
        issuer_ref=literal("SYN-A"), content_version_label=text, representation_ref=text,
        assertion_ref=text, raw_body_ref=parent, subject_period=period,
        publication=lambda v: known_or_unknown(v, record(declared_time=time_record, proof_kind=literal("exact"),
                                            proof_input_ref=parent)),
        origin_ref=ref("ORIGIN"), original_packet_ref=parent,
    ),
    "SOURCE_VERSION_HISTORY": dict(
        issuer_ref=literal("SYN-A"), ordered_versions=items(ref("SOURCE_VERSION")),
        corrections=items(record(prior_ref=ref("SOURCE_VERSION"), next_ref=ref("SOURCE_VERSION"),
                                 notice_ref=ref("SOURCE_VERSION"),
                                 declared_time=lambda v: known_or_unknown(v, time_record),
                                 origin_ref=ref("ORIGIN")), 0),
        history_scope=text, evidence_input_ref=parent,
    ),
    "MANIFEST": dict(source_versions=items(source_version_ref),
                     issuer_cohort=literal(["SYN-A"]), calendar_ref=ref("CALENDAR"),
                     original_input_refs=items(parent), membership_state=lambda v: known_or_unknown(v, text),
                     origin_ref=ref("ORIGIN")),
    "COVERAGE": dict(manifest_ref=ref("MANIFEST"), context_ref=text, query_scope=text,
                     candidate_refs=items(ref("SOURCE_VERSION")), history_ref=ref("SOURCE_VERSION_HISTORY"),
                     checks=items(record(operation=text, status=literal("COMPLETED", "FAILED", "NOT_PERFORMED"),
                                         evidence_ref=parent, origin_ref=ref("ORIGIN"))),
                     termination=lambda v: known_or_unknown(v, literal(True, False))),
    "TIMEZONE_RULES": dict(timezone_name=literal("Asia/Taipei"), rules_source_ref=parent,
                           rules_version=text, supported_precision=literal("SECOND"),
                           coverage=record(first_local=text, last_local=text),
                           offset_rules=items(record(start=text, end=text, offset=literal("+08:00")))),
    "CALENDAR": dict(calendar_label=text, timezone_rules_ref=ref("TIMEZONE_RULES"), coverage=period,
                     days=items(lambda v: _calendar_day(v)), source_input_ref=parent),
    "SOURCE_CADENCE": dict(source_kinds=items(text), source_version_refs=items(ref("SOURCE_VERSION")),
                           period_basis=text, availability_basis=text, origin_ref=ref("ORIGIN")),
    "NUMERIC_POLICY": dict(
        input_integer_type=literal("int64"), revenue_unit=literal("NTD_thousands"),
        ratio_policy_name=literal(NUMERICAL_POLICY), ratio_scale=lambda v: _uint_equal(v, 6),
        ratio_unit=literal("FRACTION"),
        ratio_scaled_bounds=record(min=lambda v: _uint_equal(v, 0),
                                   max=lambda v: _uint_equal(v, 1000000)),
        rounding=literal("HALF_EVEN"), policy_source_ref=parent,
    ),
    "PROJECTION_POLICY": dict(projection=projection),
    "OBSERVATION_RELEASE_POLICY": dict(
        policy_purpose=literal("SEMANTIC_DISCLOSURE_RULES"), projection_policy_ref=ref("PROJECTION_POLICY"),
        principal_classes=items(literal("F2_ISSUER", "F2_REVIEWER", "F3_RESEARCH", "F5_POLICY", "F6_DISPLAY")),
        required_checks=record(exact_target=literal(True), context_match=literal(True),
                               current_grant=literal(True), IF05_predicate=literal(True),
                               audit_separation=literal(True)),
        denial_rule=literal("FAIL_CLOSED_RETAIN_NATIVE_STATE"), policy_version=text,
    ),
    "AUDIT_ACCESS_POLICY": dict(
        principal_classes=items(literal("F2_ISSUER", "INDEPENDENT_F2_REVIEWER")),
        operations=items(literal("INSPECT_SOURCE", "INSPECT_NATIVE", "VERIFY_PROVENANCE")),
        target_rules=items(record(resource_kind=lambda v: _role(v), schema=text, version=text)),
        context_scope=record(cutoff_rule=text, issuer_cohort=literal(["SYN-A"])),
        receipt_requirements=literal("SC:L390_EXACT_OPERATION_RECEIPT"),
        revocation_rule=literal("DENY_CURRENT_OPERATION_RETAIN_HISTORY"),
    ),
    "SCHEDULE_INVARIANT_POLICY": dict(
        protocol_ref=ref("PROTOCOL"), profile=literal("FIXED_FOUR_WEEKLY_SYN_A"),
        preserve_order=literal(True), preserve_unknown=literal(True),
        no_session_annotation_only=literal(True), accounting_implies_admission=literal(False),
    ),
    "TEMPORAL_CONFIGURATION": dict(
        object_schema_version=literal("temporal-configuration-candidate-v0.1"),
        limitations=items(text, 0), data_mode=literal("SYNTHETIC_GOLDEN"),
        source_refs=items(lambda v: _config_source(v)), evidence_class=literal("UNVERIFIED"),
        calendar=ref("CALENDAR"), source_cadence_refs=items(ref("SOURCE_CADENCE")),
        decision_cadence=literal("WEEKLY"),
        cutoff_convention=record(timezone_name=literal("Asia/Taipei"), offset=literal("+08:00"),
                                 precision=literal("SECOND"), local_clock=literal("18:00:00"),
                                 anchor_ref=ref("PROTOCOL"), holiday_roll_ref=ref("PROTOCOL")),
        horizon_ref=ref("HORIZON_MATURITY"), rebalance_execution_ref=ref("EXECUTION_RULES"),
        evaluation_ref=ref("EVALUATION_PROTOCOL"),
    ),
    "DECISION_SCHEDULE": dict(
        object_schema_version=literal("decision-schedule-candidate-v0.1"),
        limitations=items(text, 0), data_mode=literal("SYNTHETIC_GOLDEN"),
        source_refs=items(original_ref), evidence_class=literal("UNVERIFIED"),
        configuration_ref=ref("TEMPORAL_CONFIGURATION"), source_input_ref=parent,
        ticks=items(record(tick=tick, session_id=text)), annotations=items(annotation),
    ),
    "NATIVE_RECEIPT": dict(
        owner=text, operation=text, record_type=text, tick_context=tick,
        semantic_input_refs=items(semantic_input), rules_code_refs=items(code_pin),
        invocation=literal("RUN", "ATTEMPTED", "NOT_RUN"), original_state_fact=_native_state,
        reason_code=text, unknown=unknown_or_na, first_failure=native_failure, scope=scope,
    ),
    "SEMANTIC_TRACE": dict(trace=trace),
}


def _role(value: object) -> None:
    from pit_research_lab.mvp.f2.resource_contracts import ROLES

    literal(*ROLES)(value)


def _uint_equal(value: object, expected: int) -> None:
    require(tagged_integer(value) == expected, "NUMERIC_POLICY_BOUND")


def _config_source(value: object) -> None:
    if type(value) is dict and "resource_kind" in value:
        resource(value, "MANIFEST", "CALENDAR", "SOURCE_CADENCE")
    else:
        parent(value)


def _calendar_day(value: object) -> None:
    d = closed(value, "date status session origin_ref")
    local_date(d["date"])
    resource(d["origin_ref"], "ORIGIN")
    if d["status"] == "CLOSED":
        absent(d["session"])
    else:
        literal("SESSION")(d["status"])
        s = closed(d["session"], "type value")
        literal("available")(s["type"])
        v = closed(s["value"], "session_id open close")
        text(v["session_id"])
        require(time_record(v["open"]) < time_record(v["close"]), "SESSION_ORDER")
        require(v["open"]["source_text"][:10] == d["date"]
                == v["close"]["source_text"][:10], "SESSION_DAY")


@dataclass(frozen=True, slots=True)
class DraftBody:
    kind: str
    schema: str
    version: str
    raw: bytes

    def fields(self) -> dict[str, Any]:
        # Fresh parse: caller mutation cannot alter retained draft bytes.
        return strict_json(self.raw)


def parse_body(kind: str, raw: bytes) -> DraftBody:
    if kind not in SCHEMAS:
        raise ResourceError("BODY_SCHEMA_NOT_SUPPLIED", State.NOT_SUPPLIED)
    d = strict_json(raw)
    version_key = "semantic_version" if kind == "NATIVE_RECEIPT" else "body_version"
    validators: dict[str, Validator] = {
        "body_schema_label": literal(schema_label(kind)), version_key: literal(VERSION),
        **SCHEMAS[kind],
    }
    record(**validators)(d)
    if kind == "SOURCE_VERSION_HISTORY":
        unique(d["ordered_versions"], ref("SOURCE_VERSION"))
        ordered = d["ordered_versions"]
        last = -1
        for correction in d["corrections"]:
            require(correction["prior_ref"] in ordered and correction["next_ref"] in ordered,
                    "FOREIGN_CORRECTION")
            a, b = ordered.index(correction["prior_ref"]), ordered.index(correction["next_ref"])
            require(a < b and a >= last and correction["notice_ref"] in ordered,
                    "CORRECTION_ORDER")
            last = b
    if kind == "CALENDAR":
        days = d["days"]
        require([v["date"] for v in days] == sorted({v["date"] for v in days}), "CALENDAR_ORDER")
        require(days[0]["date"] == d["coverage"]["start_date"]
                and days[-1]["date"] == d["coverage"]["end_date"], "CALENDAR_COVERAGE")
        for a, b in zip(days, days[1:]):
            require((date.fromisoformat(b["date"]) - date.fromisoformat(a["date"])).days == 1,
                    "CALENDAR_GAP")
    if kind == "SEMANTIC_TRACE" and d["trace"]["subtype"] == "SET_INPUT_MANIFEST":
        unique(d["trace"]["binding_refs"], ref("SEMANTIC_TRACE"))
    if kind == "TIMEZONE_RULES":
        first = declared_taipei(d["coverage"]["first_local"])
        last = declared_taipei(d["coverage"]["last_local"])
        require(first <= last, "RULE_COVERAGE_ORDER")
        expected_start = first
        for interval in d["offset_rules"]:
            start, end = declared_taipei(interval["start"]), declared_taipei(interval["end"])
            require(start == expected_start and start <= end <= last, "RULE_INTERVAL_COVERAGE")
            expected_start = end + timedelta(seconds=1)
        require(expected_start == last + timedelta(seconds=1), "RULE_INTERVAL_COVERAGE")
    return DraftBody(kind, schema_label(kind), VERSION, raw)


def validate_body_key(key: ResourceKey, body: DraftBody) -> DraftBody:
    parsed = parse_body(body.kind, body.raw)
    require((key.kind, key.schema, key.version) == (parsed.kind, parsed.schema, parsed.version),
            "REF_BODY_SCHEMA_VERSION")
    return parsed


def parse_reference_body(value: object, raw: bytes) -> DraftBody:
    """Exact draft kind/schema/version binding, still no content-core verification."""
    key = resource(value)
    return validate_body_key(key, parse_body(key.kind, raw))


def issuance_readiness(body: DraftBody) -> Check:
    """No canonical resource or rights issuer exists in this work unit."""
    parse_body(body.kind, body.raw)
    return Check(State.NOT_SUPPLIED, ("BODY_RIGHTS_AND_INDEPENDENT_REVIEW_NOT_SUPPLIED",
                                     "INDEPENDENT_ORACLE_AND_CODEC_NOT_SUPPLIED"))
