"""TEST_ONLY / NON_ISSUED draft inputs, never Native attempts or Golden vectors.

Repeated hexadecimal markers below are deliberately unverified test placeholders.
No expected canonical digest is derived. Every public Native evaluator is trapped
while these tests run; only pure numeric constructors/arithmetic are exercised.
Run without third-party dependencies: python3.12 -B -m unittest discover ...
"""

import ast
import copy
import json
import re
import unittest
import zipfile
from collections import Counter
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from pit_research_lab.domain.ratio import _fixed_ratio
from pit_research_lab.mvp.f2.resource_access import (
    AccessRequest,
    GrantDeclaration,
    authorization_check,
    detached_release,
    safe_observation_structure,
)
from pit_research_lab.mvp.f2.resource_binding import (
    CUTOFFS,
    EXTERNAL_DECLARATIONS,
    SCHEDULE_INPUT_SCHEMA,
    SEQ_FIELDS,
    DraftNode,
    check_correspondence,
    configuration_readiness,
    correspondence_record,
    declared_before,
    original_source_facts,
    parse_schedule_input,
    schedule_influence,
    schedule_path_check,
    sealed_summary_readiness,
    semantic_ancestry,
    sequence_structure,
    source_body_prerequisites,
    time_rules_readiness,
    validate_four_ticks,
)
from pit_research_lab.mvp.f2.resource_bodies import (
    SCHEMAS,
    VERSION,
    accounting,
    issuance_readiness,
    native_summary,
    parse_body,
    parse_reference_body,
    schema_label,
)
from pit_research_lab.mvp.f2.resource_contracts import (
    DOMAINS,
    FLAGS,
    PROFILE,
    ROLES,
    ResourceError,
    State,
    closure_class,
    fixed_ratio,
    parent,
    resource,
    revenue,
    strict_json,
    tagged_integer,
    time_record,
)

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tests/unit/mvp_f2/data/derived_observations_v0.1.json"


def raw(value):
    # Ordinary test transport only, NOT an App canonical serializer.
    return json.dumps(value).encode()


def uint(n):
    return {"type": "uint64", "value": str(n)}


def core(domain="SOURCE-BYTES", marker="0"):
    return {
        "domain_tag": f"PITLAB/ACADEMIC/{domain}/candidate-v0.1",
        "object_schema_version": DOMAINS[domain],
        "canonical_profile_version": PROFILE,
        "digest_algorithm": "SHA-256",
        "canonical_payload_byte_length": uint(1),
        "digest_hex": marker * 64,
    }


def rr(kind, marker="0"):
    return {
        "resource_kind": kind,
        "resource_version": VERSION,
        "resource_schema": schema_label(kind),
        "content_ref": core(marker=marker),
    }


def na():
    return {"type": "not_applicable", "owner": "TEST_ONLY", "reason": "NON_ISSUED"}


def ne():
    return {"type": "not_evaluated", "owner": "TEST_ONLY", "reason": "NOT_SUPPLIED"}


def unknown():
    return {
        "type": "unknown",
        "cause": "ABSENT_SOURCE_FIELD",
        "origin_ref": rr("ORIGIN"),
        "source_text_ref": na(),
    }


def scope():
    return {
        "data_mode": "SYNTHETIC_GOLDEN",
        "pit_status": "UNRESOLVED",
        "evidence_class": "UNVERIFIED",
        "scope_flags": dict(FLAGS),
    }


def tm(source=CUTOFFS[0]):
    instant = datetime.fromisoformat(source).astimezone(UTC)
    return {
        "source_text": source,
        "timezone_name": "Asia/Taipei",
        "offset": "+08:00",
        "precision": "SECOND",
        "origin_ref": rr("ORIGIN"),
        "utc_comparison": instant.isoformat().replace("+00:00", "Z"),
        "timezone_rules_ref": rr("TIMEZONE_RULES"),
    }


def tick(i=0):
    return {
        "tick_id": f"TEST_ONLY_t{i + 1}",
        "tick_order": uint(i),
        "decision_cutoff": tm(CUTOFFS[i]),
        "context_ref": f"NON_ISSUED_CONTEXT_{i}",
    }


def notes():
    return [{"iso_week": "2027-W03", "kind": "NO_SESSION_WEEK", "calendar_ref": rr("CALENDAR")}]


def code():
    return {
        "role": "TEST_ONLY",
        "path": "src/test_only.py",
        "byte_length": uint(1),
        "sha256": "0" * 64,
        "semantic_version": "NON_ISSUED",
    }


def summary(invocation="RUN"):
    return {
        "owner": "TEST_ONLY",
        "type": "TEST_ONLY_FACT",
        "state": "VALUE_AVAILABLE",
        "reason_code": "NONE",
        "unknown": na(),
        "first_failure": na(),
        "invocation": invocation,
        "invocation_receipt_ref": rr("NATIVE_RECEIPT"),
    }


def body(kind, **fields):
    key = "semantic_version" if kind == "NATIVE_RECEIPT" else "body_version"
    return {"body_schema_label": schema_label(kind), key: VERSION, **fields}


def origin_body(input_ref=None):
    return body(
        "ORIGIN",
        source_input_ref=input_ref or core(),
        input_pointer="/TEST_ONLY",
        fact_owner="TEST_ONLY",
        source_schema={"kind": "KNOWN", "value": "NON_ISSUED"},
        object_id={"kind": "UNKNOWN", "cause": "ABSENT_SOURCE_FIELD", "source_text": na()},
        origin_kind="AUTHORED_SYNTHETIC",
    )


def native_body(i=0):
    return body(
        "NATIVE_RECEIPT",
        owner="TEST_ONLY",
        operation="TEST_ONLY_OPERATION",
        record_type="TEST_ONLY_FACT",
        tick_context=tick(i),
        semantic_input_refs=[core()],
        rules_code_refs=[code()],
        invocation="RUN",
        original_state_fact="VALUE_AVAILABLE",
        reason_code="NONE",
        unknown=na(),
        first_failure=na(),
        scope=scope(),
    )


def schedule_input(policy=None):
    return {
        "body_schema_label": SCHEDULE_INPUT_SCHEMA,
        "body_version": VERSION,
        "original_input_refs": [core()],
        "invariant_policy_ref": policy or rr("SCHEDULE_INVARIANT_POLICY"),
        "selected_profile": "FIXED_FOUR_WEEKLY_SYN_A",
    }


def schedule():
    return body(
        "DECISION_SCHEDULE",
        object_schema_version="decision-schedule-candidate-v0.1",
        limitations=["TEST_ONLY_NON_ISSUED"],
        data_mode="SYNTHETIC_GOLDEN",
        source_refs=[core()],
        evidence_class="UNVERIFIED",
        configuration_ref=rr("TEMPORAL_CONFIGURATION"),
        source_input_ref=core(),
        ticks=[{"tick": tick(i), "session_id": f"TEST_SESSION_{i}"} for i in range(4)],
        annotations=notes(),
    )


def configuration():
    return body(
        "TEMPORAL_CONFIGURATION",
        object_schema_version="temporal-configuration-candidate-v0.1",
        limitations=["TEST_ONLY_NON_ISSUED"],
        data_mode="SYNTHETIC_GOLDEN",
        source_refs=[core()],
        evidence_class="UNVERIFIED",
        calendar=rr("CALENDAR"),
        source_cadence_refs=[rr("SOURCE_CADENCE")],
        decision_cadence="WEEKLY",
        cutoff_convention={
            "timezone_name": "Asia/Taipei",
            "offset": "+08:00",
            "precision": "SECOND",
            "local_clock": "18:00:00",
            "anchor_ref": rr("PROTOCOL"),
            "holiday_roll_ref": rr("PROTOCOL", "1"),
        },
        horizon_ref=rr("HORIZON_MATURITY"),
        rebalance_execution_ref=rr("EXECUTION_RULES"),
        evaluation_ref=rr("EVALUATION_PROTOCOL"),
    )


def binding(i):
    return body(
        "SEMANTIC_TRACE",
        trace={
            "subtype": "PER_CUTOFF_BINDING",
            "object_schema_version": "per-cutoff-binding-candidate-v0.1",
            "limitations": ["TEST_ONLY_NON_ISSUED"],
            "data_mode": "SYNTHETIC_GOLDEN",
            "source_refs": [core()],
            "tick": tick(i),
            "manifest_source_versions": {
                "manifest_ref": rr("MANIFEST"),
                "source_version_refs": [
                    {
                        "body_ref": core(),
                        "version_ref": rr("SOURCE_VERSION"),
                        "representation_ref": "TEST_ONLY",
                        "revision_history_ref": rr("SOURCE_VERSION_HISTORY"),
                    }
                ],
                "coverage_ref": rr("COVERAGE"),
            },
            "qualification_ref": core("F2-QUALIFICATION", str(i)),
            "audit_evidence_ref": rr("NATIVE_RECEIPT"),
            "observation_ref": {"type": "available", "ref": core("F2-OBSERVATION", str(i))},
            "native_summary": summary(),
            "app_axes": {
                "pit_status": "UNRESOLVED",
                "execution_status": "NOT_RUN",
                "evidence_class": "UNVERIFIED",
                "execution_scope_ref": rr("PROTOCOL"),
            },
            "scope_flags": dict(FLAGS),
            "selected_cohort": [{"issuer_ref": "SYN-A", "feature_ref": "TEST_ONLY"}],
            "mismatch_reason": na(),
        },
    )


def sequence():
    bindings = [binding(i) for i in range(4)]
    members = [
        {
            "tick": tick(i),
            "binding_ref": rr("SEMANTIC_TRACE", str(i)),
            "qualification_ref": b["trace"]["qualification_ref"],
            "observation_ref": b["trace"]["observation_ref"],
            "scope": scope(),
        }
        for i, b in enumerate(bindings)
    ]
    si = body(
        "SEMANTIC_TRACE",
        trace={
            "subtype": "SET_INPUT_MANIFEST",
            "manifest_ref": rr("MANIFEST"),
            "binding_refs": [m["binding_ref"] for m in members],
            "semantic_limitations": ["TEST_ONLY"],
            "original_source_refs": [core()],
        },
    )
    return (
        {
            "canonical_profile_version": PROFILE,
            "configuration_ref": rr("TEMPORAL_CONFIGURATION"),
            "schedule_ref": rr("DECISION_SCHEDULE"),
            "bindings": members,
            "annotations": notes(),
            "release_state": {
                "scheduled_count": uint(4),
                "accounted_count": uint(4),
                "position_outcomes": [{"owner": "F2", "code": "NOT_EVALUATED"}] * 4,
                "release_policy_ref": rr("OBSERVATION_RELEASE_POLICY"),
            },
            "provenance_ref": rr("SEMANTIC_TRACE", "9"),
            "scope": scope(),
        },
        bindings,
        si,
    )


def rem1_sequence_inputs():
    value, bindings, set_input = sequence()
    return (
        value,
        tuple(parse_body("SEMANTIC_TRACE", raw(b)) for b in bindings),
        parse_body("DECISION_SCHEDULE", raw(schedule())),
        parse_body("SEMANTIC_TRACE", raw(set_input)),
    )


def rem1_expected_refs():
    # Independently declared TEST_ONLY / NON_ISSUED equality inputs, not copied
    # from the SEQ being checked and not cryptographically verified identities.
    return dict(
        expected_schedule_ref=rr("DECISION_SCHEDULE"),
        expected_provenance_ref=rr("SEMANTIC_TRACE", "9"),
        expected_schedule_input_core=core(),
        expected_manifest_ref=rr("MANIFEST"),
        expected_original_source_refs=[core()],
        source_input=parse_schedule_input(raw(schedule_input())),
        invariant_policy_ref=rr("SCHEDULE_INVARIANT_POLICY"),
    )


def draft_examples():
    """Every implemented schema gets a NON_ISSUED closed-field exercise."""
    version_ref = {
        "body_ref": core(),
        "version_ref": rr("SOURCE_VERSION"),
        "representation_ref": "TEST_ONLY",
        "revision_history_ref": rr("SOURCE_VERSION_HISTORY"),
    }
    period = {"start_date": "2027-01-07", "end_date": "2027-01-07"}
    return {
        "ORIGIN": origin_body(),
        "SOURCE_VERSION": body(
            "SOURCE_VERSION",
            issuer_ref="SYN-A",
            content_version_label="D1",
            representation_ref="TEST_ONLY",
            assertion_ref="TEST_ONLY",
            raw_body_ref=core(),
            subject_period=period,
            publication=unknown(),
            origin_ref=rr("ORIGIN"),
            original_packet_ref=core(),
        ),
        "SOURCE_VERSION_HISTORY": body(
            "SOURCE_VERSION_HISTORY",
            issuer_ref="SYN-A",
            ordered_versions=[rr("SOURCE_VERSION")],
            corrections=[],
            history_scope="TEST_ONLY_PARTIAL",
            evidence_input_ref=core(),
        ),
        "MANIFEST": body(
            "MANIFEST",
            source_versions=[version_ref],
            issuer_cohort=["SYN-A"],
            calendar_ref=rr("CALENDAR"),
            original_input_refs=[core()],
            membership_state=unknown(),
            origin_ref=rr("ORIGIN"),
        ),
        "COVERAGE": body(
            "COVERAGE",
            manifest_ref=rr("MANIFEST"),
            context_ref="TEST_ONLY",
            query_scope="TEST_ONLY_PARTIAL",
            candidate_refs=[rr("SOURCE_VERSION")],
            history_ref=rr("SOURCE_VERSION_HISTORY"),
            checks=[
                {
                    "operation": "TEST_ONLY",
                    "status": "NOT_PERFORMED",
                    "evidence_ref": core(),
                    "origin_ref": rr("ORIGIN"),
                }
            ],
            termination=unknown(),
        ),
        "TIMEZONE_RULES": body(
            "TIMEZONE_RULES",
            timezone_name="Asia/Taipei",
            rules_source_ref=core(),
            rules_version="TEST_ONLY_UNREVIEWED",
            supported_precision="SECOND",
            coverage={"first_local": CUTOFFS[0], "last_local": CUTOFFS[-1]},
            offset_rules=[{"start": CUTOFFS[0], "end": CUTOFFS[-1], "offset": "+08:00"}],
        ),
        "CALENDAR": body(
            "CALENDAR",
            calendar_label="TEST_ONLY",
            timezone_rules_ref=rr("TIMEZONE_RULES"),
            coverage=period,
            days=[
                {
                    "date": "2027-01-07",
                    "status": "SESSION",
                    "session": {
                        "type": "available",
                        "value": {
                            "session_id": "TEST_ONLY",
                            "open": tm("2027-01-07T09:00:00+08:00"),
                            "close": tm("2027-01-07T13:30:00+08:00"),
                        },
                    },
                    "origin_ref": rr("ORIGIN"),
                }
            ],
            source_input_ref=core(),
        ),
        "SOURCE_CADENCE": body(
            "SOURCE_CADENCE",
            source_kinds=["TEST_ONLY_REVENUE"],
            source_version_refs=[rr("SOURCE_VERSION")],
            period_basis="MONTHLY",
            availability_basis="TEST_ONLY_ORIGINAL_PUBLICATION",
            origin_ref=rr("ORIGIN"),
        ),
        "NUMERIC_POLICY": body(
            "NUMERIC_POLICY",
            input_integer_type="int64",
            revenue_unit="NTD_thousands",
            ratio_policy_name="FIXED_SIX_DECIMAL_FRACTION_HALF_EVEN-v0.1",
            ratio_scale=uint(6),
            ratio_unit="FRACTION",
            ratio_scaled_bounds={"min": uint(0), "max": uint(1000000)},
            rounding="HALF_EVEN",
            policy_source_ref=core(),
        ),
        "PROJECTION_POLICY": body(
            "PROJECTION_POLICY",
            projection={
                "feature_rules": [
                    {
                        "feature_ref": "TEST_ONLY_A04",
                        "value_type": "INT64",
                        "unit": "NTD_thousands",
                        "numeric_policy_ref": rr("NUMERIC_POLICY"),
                    },
                    {
                        "feature_ref": "TEST_ONLY_A05",
                        "value_type": "FIXED_RATIO6",
                        "unit": "FRACTION",
                        "numeric_policy_ref": rr("NUMERIC_POLICY"),
                    },
                ],
                "allowed_tags": ["Known", "Unknown", "NotEvaluated", "Withheld"],
                "safe_reason_rules": [],
                "scope_flags": dict(FLAGS),
                "forbidden_surfaces": [
                    "RAW_SOURCE",
                    "NATIVE_AUDIT",
                    "ATTEMPT",
                    "TIMING",
                    "TOKEN",
                    "CALLBACK",
                    "FUTURE_EVAL",
                ],
            },
        ),
        "OBSERVATION_RELEASE_POLICY": body(
            "OBSERVATION_RELEASE_POLICY",
            policy_purpose="SEMANTIC_DISCLOSURE_RULES",
            projection_policy_ref=rr("PROJECTION_POLICY"),
            principal_classes=["F5_POLICY"],
            required_checks={
                "exact_target": True,
                "context_match": True,
                "current_grant": True,
                "IF05_predicate": True,
                "audit_separation": True,
            },
            denial_rule="FAIL_CLOSED_RETAIN_NATIVE_STATE",
            policy_version="TEST_ONLY_NON_ISSUED",
        ),
        "AUDIT_ACCESS_POLICY": body(
            "AUDIT_ACCESS_POLICY",
            principal_classes=["INDEPENDENT_F2_REVIEWER"],
            operations=["VERIFY_PROVENANCE"],
            target_rules=[
                {
                    "resource_kind": "NATIVE_RECEIPT",
                    "schema": schema_label("NATIVE_RECEIPT"),
                    "version": VERSION,
                }
            ],
            context_scope={"cutoff_rule": "TEST_ONLY_EXACT", "issuer_cohort": ["SYN-A"]},
            receipt_requirements="SC:L390_EXACT_OPERATION_RECEIPT",
            revocation_rule="DENY_CURRENT_OPERATION_RETAIN_HISTORY",
        ),
        "SCHEDULE_INVARIANT_POLICY": body(
            "SCHEDULE_INVARIANT_POLICY",
            protocol_ref=rr("PROTOCOL"),
            profile="FIXED_FOUR_WEEKLY_SYN_A",
            preserve_order=True,
            preserve_unknown=True,
            no_session_annotation_only=True,
            accounting_implies_admission=False,
        ),
        "TEMPORAL_CONFIGURATION": configuration(),
        "DECISION_SCHEDULE": schedule(),
        "NATIVE_RECEIPT": native_body(),
        "SEMANTIC_TRACE": body(
            "SEMANTIC_TRACE",
            trace={
                "subtype": "QUAL_INPUT",
                "semantic_input_refs": [core()],
                "rules_code_refs": [code()],
                "native_summary": summary(),
                "scope": scope(),
            },
        ),
    }


class ResourceTests(unittest.TestCase):
    def setUp(self):
        for module, name in (
            ("ratio_slice", "evaluate_ratio"),
            ("derived_slice", "evaluate_derived"),
            ("pit_slice", "evaluate_slice"),
        ):
            trap = patch(
                f"pit_research_lab.domain.{module}.{name}",
                side_effect=AssertionError("NATIVE_OPERATION_FORBIDDEN"),
            )
            trap.start()
            self.addCleanup(trap.stop)

    def invalid(self, function, code=None):
        with self.assertRaises(ResourceError) as caught:
            function()
        if code:
            self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_registered_roles_and_closure_match_contract(self):
        sc = (ROOT / "docs/mvp/v1.0/shared-interface-contract-v0.1.md").read_text()
        line = next(
            s for s in sc.splitlines() if s.startswith("Registered ResourceRef role literals:")
        )
        self.assertEqual(tuple(re.findall(r"`([A-Z_]+)`", line)), ROLES)
        self.assertEqual(len(set(ROLES)), 40)
        self.assertEqual(
            Counter(closure_class(r) for r in ROLES),
            {
                "REQUIRED_FOR_SLICE": 21,
                "CONDITIONAL": 3,
                "INTERFACE_ONLY": 2,
                "DEFERRED_WITH_GATE": 13,
                "NOT_APPLICABLE_IN_SLICE": 1,
            },
        )

    def test_every_implemented_body_descriptor_closed_and_non_issued(self):
        examples = draft_examples()
        self.assertEqual(set(examples), set(SCHEMAS))
        for kind, example in examples.items():
            with self.subTest(role=kind):
                parsed = parse_body(kind, raw(example))
                self.assertEqual(issuance_readiness(parsed).state, State.NOT_SUPPLIED)
                self.invalid(
                    lambda kind=kind, example=example: parse_body(
                        kind, raw({**example, "attempt_id": "PRIVATE"})
                    ),
                    "CLOSED_FIELDS",
                )

    def test_calendar_gap_order_and_contradictory_session(self):
        d = draft_examples()["CALENDAR"]
        d["days"][0]["session"]["value"]["close"] = tm("2027-01-07T08:59:59+08:00")
        self.invalid(lambda: parse_body("CALENDAR", raw(d)), "SESSION_ORDER")
        d = draft_examples()["CALENDAR"]
        d["days"].append(
            {"date": "2027-01-09", "status": "CLOSED", "session": na(), "origin_ref": rr("ORIGIN")}
        )
        d["coverage"]["end_date"] = "2027-01-09"
        self.invalid(lambda: parse_body("CALENDAR", raw(d)), "CALENDAR_GAP")

    def test_rule_table_draft_does_not_supply_reviewed_rule_evidence(self):
        d = draft_examples()["TIMEZONE_RULES"]
        rules = parse_body("TIMEZONE_RULES", raw(d))
        self.assertEqual(
            time_rules_readiness(tm(), rules).reasons,
            ("REVIEWED_RULE_SOURCE_AND_RIGHTS_NOT_SUPPLIED",),
        )
        d["offset_rules"][0]["offset"] = "+09:00"
        self.invalid(lambda: parse_body("TIMEZONE_RULES", raw(d)))

    def test_unknown_coverage_and_no_failed_operation_promotion(self):
        d = draft_examples()["COVERAGE"]
        parsed = parse_body("COVERAGE", raw(d))
        self.assertEqual(parsed.fields()["termination"]["type"], "unknown")
        d["checks"][0]["status"] = "FAILED"
        self.assertEqual(
            issuance_readiness(parse_body("COVERAGE", raw(d))).state, State.NOT_SUPPLIED
        )
        d["termination"] = True
        self.invalid(lambda: parse_body("COVERAGE", raw(d)))

    def test_numeric_policy_cannot_widen_scale_or_claim_general_decimal(self):
        d = draft_examples()["NUMERIC_POLICY"]
        d["ratio_scale"] = uint(18)
        self.invalid(lambda: parse_body("NUMERIC_POLICY", raw(d)), "NUMERIC_POLICY_BOUND")
        d = draft_examples()["NUMERIC_POLICY"]
        d["decimal_rules"] = {"arbitrary": True}
        self.invalid(lambda: parse_body("NUMERIC_POLICY", raw(d)), "CLOSED_FIELDS")

    def test_immutable_release_policy_cannot_switch_off_current_grant_or_if05(self):
        for key in ("current_grant", "IF05_predicate", "audit_separation"):
            d = draft_examples()["OBSERVATION_RELEASE_POLICY"]
            d["required_checks"][key] = False
            self.invalid(lambda d=d: parse_body("OBSERVATION_RELEASE_POLICY", raw(d)), "LITERAL")
        d = draft_examples()["PROJECTION_POLICY"]
        d["projection"]["allowed_tags"].append("VALUE_AVAILABLE_IS_ELIGIBLE")
        self.invalid(lambda: parse_body("PROJECTION_POLICY", raw(d)), "LITERAL")

    def test_policy_body_does_not_authenticate_scheduleinput_or_issue_sequence(self):
        policy = parse_body(
            "SCHEDULE_INVARIANT_POLICY", raw(draft_examples()["SCHEDULE_INVARIANT_POLICY"])
        )
        result = schedule_path_check(
            parse_schedule_input(raw(schedule_input())),
            parse_body("DECISION_SCHEDULE", raw(schedule())),
            supplied_input_core=parent(core()),
            invariant_policy_ref=rr("SCHEDULE_INVARIANT_POLICY"),
            sequence_schedule_ref=rr("DECISION_SCHEDULE"),
            schedule_resource_ref=rr("DECISION_SCHEDULE"),
            policy_body=policy,
        )
        self.assertIn("IMMUTABLE_SOURCE_BYTES_VERIFICATION_NOT_SUPPLIED", result.reasons)

    def test_draft_graph_semantic_code_change_and_final_evidence_separation(self):
        original = native_body()
        changed = copy.deepcopy(original)
        changed["rules_code_refs"][0]["sha256"] = "1" * 64
        self.assertNotEqual(
            parse_body("NATIVE_RECEIPT", raw(original)).raw,
            parse_body("NATIVE_RECEIPT", raw(changed)).raw,
        )
        evidence_only = {"subject": "TEST_ONLY", "limitation": "NEW_EVIDENCE_ONLY_LIMITATION"}
        self.assertTrue(evidence_only)
        self.assertEqual(parse_body("NATIVE_RECEIPT", raw(original)).raw, raw(original))
        k = resource(rr("NATIVE_RECEIPT"))
        self.invalid(
            lambda: semantic_ancestry(k, {k: DraftNode(k, None, "FINAL_EVIDENCE")}),
            "ATTEMPT_OR_FINAL_EVIDENCE_ANCESTRY",
        )

    def test_closed_body_and_immutable_snapshot(self):
        d = origin_body()
        parsed = parse_body("ORIGIN", raw(d))
        parsed.fields()["fact_owner"] = "MUTATED"
        self.assertEqual(parsed.fields()["fact_owner"], "TEST_ONLY")
        d["extra"] = "FORBIDDEN"
        self.invalid(lambda: parse_body("ORIGIN", raw(d)), "CLOSED_FIELDS")

    def test_missing_field_and_null_refuse(self):
        for mutation in (lambda d: d.pop("fact_owner"), lambda d: d.update(fact_owner=None)):
            d = origin_body()
            mutation(d)
            self.invalid(lambda d=d: parse_body("ORIGIN", raw(d)))

    def test_wrong_body_version_and_schema_refuse(self):
        for key in ("body_version", "body_schema_label"):
            d = origin_body()
            d[key] = "UNREVIEWED"
            self.invalid(lambda d=d: parse_body("ORIGIN", raw(d)), "LITERAL")

    def test_duplicate_json_and_invalid_unicode_refuse(self):
        for b in (b'{"a":1,"a":2}', b"\xef\xbb\xbf{}", b'{"a":NaN}', b"\xff"):
            self.invalid(lambda b=b: strict_json(b))
        d = origin_body()
        d["fact_owner"] = "\ud800"
        self.invalid(lambda: parse_body("ORIGIN", raw(d)), "INVALID_UNICODE")

    def test_unreviewed_external_schema_stays_blocked(self):
        for role in EXTERNAL_DECLARATIONS:
            e = self.invalid(lambda role=role: parse_body(role, b"{}"), "BODY_SCHEMA_NOT_SUPPLIED")
            self.assertEqual(e.state, State.NOT_SUPPLIED)

    def test_structure_never_issues_body_or_rights(self):
        result = issuance_readiness(parse_body("ORIGIN", raw(origin_body())))
        self.assertEqual(result.state, State.NOT_SUPPLIED)
        self.assertTrue(result.diagnostic_only)
        self.assertFalse(result.admission_eligible)

    def test_typed_refs_domains_payload_length_and_profile(self):
        self.assertEqual(resource(rr("ORIGIN")).kind, "ORIGIN")
        self.invalid(lambda: resource(rr("ORIGIN"), "CALENDAR"), "RESOURCE_KIND")
        for key, val in (
            ("object_schema_version", "git-blob"),
            ("canonical_profile_version", "wrong"),
            ("digest_hex", "A" * 64),
            ("canonical_payload_byte_length", uint(0)),
        ):
            c = core()
            c[key] = val
            self.invalid(lambda c=c: parent(c))
        self.invalid(lambda: parent(core("F2-QUALIFICATION")))
        self.invalid(lambda: resource({**rr("ORIGIN"), "capability": "BEARER"}), "CLOSED_FIELDS")

    def test_original_seven_packet_pins_and_correction_order(self):
        facts = original_source_facts(DATA.read_bytes())
        self.assertEqual(tuple(f.tag for f in facts), ("O", "N", "D1", "D2", "D3", "N12", "N23"))
        self.assertEqual(
            [json.loads(f.raw)["statements"][0]["value"] for f in facts[:5]], [17, 23, 100, 110, 90]
        )
        self.assertEqual(facts[3].publication_text, CUTOFFS[0])
        self.assertEqual(facts[4].publication_text, "2027-01-29T18:00:01+08:00")
        self.assertTrue(all(f.publication_pointer.startswith("/sources/") for f in facts))
        self.assertEqual(source_body_prerequisites(DATA.read_bytes()).state, State.NOT_SUPPLIED)
        self.invalid(
            lambda: original_source_facts(DATA.read_bytes() + b" "), "ORIGINAL_PACKET_PIN_MISMATCH"
        )

    def test_history_order_and_missing_publication(self):
        versions = [rr("SOURCE_VERSION", str(i)) for i in range(3)]
        d = body(
            "SOURCE_VERSION_HISTORY",
            issuer_ref="SYN-A",
            ordered_versions=versions,
            corrections=[
                {
                    "prior_ref": versions[0],
                    "next_ref": versions[1],
                    "notice_ref": versions[2],
                    "declared_time": unknown(),
                    "origin_ref": rr("ORIGIN"),
                }
            ],
            history_scope="TEST_ONLY_PARTIAL",
            evidence_input_ref=core(),
        )
        parse_body("SOURCE_VERSION_HISTORY", raw(d))
        d["corrections"][0]["prior_ref"], d["corrections"][0]["next_ref"] = versions[1], versions[0]
        self.invalid(lambda: parse_body("SOURCE_VERSION_HISTORY", raw(d)), "CORRECTION_ORDER")

    def test_unknown_publication_is_not_filled_or_qualified(self):
        d = body(
            "SOURCE_VERSION",
            issuer_ref="SYN-A",
            content_version_label="D1",
            representation_ref="TEST_ONLY",
            assertion_ref="TEST_ONLY",
            raw_body_ref=core(),
            subject_period={"start_date": "2026-12-01", "end_date": "2026-12-31"},
            publication=unknown(),
            origin_ref=rr("ORIGIN"),
            original_packet_ref=core(),
        )
        b = parse_body("SOURCE_VERSION", raw(d))
        self.assertEqual(b.fields()["publication"]["type"], "unknown")
        self.assertEqual(issuance_readiness(b).state, State.NOT_SUPPLIED)
        d["publication"] = ne()
        self.invalid(lambda: parse_body("SOURCE_VERSION", raw(d)), "FACT_TAG")

    def test_strict_before_edges_and_declared_utc(self):
        self.assertFalse(declared_before(tm(CUTOFFS[0]), tm(CUTOFFS[0])))
        self.assertFalse(declared_before(tm("2027-01-29T18:00:01+08:00"), tm(CUTOFFS[2])))
        self.assertTrue(declared_before(tm("2027-01-07T17:59:59+08:00"), tm(CUTOFFS[0])))
        self.assertEqual(time_record(tm()).isoformat(), "2027-01-07T10:00:00+00:00")

    def test_time_zone_precision_naive_rules_and_origin(self):
        for field, value in (
            ("timezone_name", "UTC"),
            ("offset", "+00:00"),
            ("precision", "DAY"),
            ("source_text", "2027-01-07T18:00:00"),
            ("utc_comparison", "2027-01-07T18:00:00Z"),
        ):
            d = tm()
            d[field] = value
            self.invalid(lambda d=d: time_record(d))
        self.assertEqual(time_rules_readiness(tm()).reasons, ("RULES_NOT_SUPPLIED",))
        changed = tm()
        changed["origin_ref"] = rr("ORIGIN", "1")
        self.assertEqual(time_record(changed), time_record(tm()))
        self.assertNotEqual(changed, tm())

    def test_four_ticks_w03_annotation_and_equal_values_distinct_context(self):
        ticks = [tick(i) for i in range(4)]
        validate_four_ticks(ticks, notes())
        self.assertNotEqual(ticks[1], ticks[2])
        for mutation in (
            ticks + [tick(3)],
            ticks[::-1],
            ticks[:3],
            [ticks[0], ticks[1], ticks[1], ticks[3]],
        ):
            self.invalid(lambda mutation=mutation: validate_four_ticks(mutation, notes()))
        self.invalid(lambda: validate_four_ticks(ticks, []))

    def test_exact_int64_signed_unit_and_encoding(self):
        for n in (-(2**63), 0, 140, 2**63 - 1):
            self.assertEqual(revenue({"type": "int64", "value": str(n)}, "NTD_thousands"), n)
        for v in ("+1", "01", "-0", "1e2", "1.0", str(2**63), str(-(2**63) - 1), 140, True, 140.0):
            self.invalid(lambda v=v: revenue({"type": "int64", "value": v}, "NTD_thousands"))
        self.invalid(lambda: revenue({"type": "int64", "value": "140"}, "NTD"))
        self.invalid(lambda: tagged_integer({"type": "uint64", "value": "-1"}))

    def test_fixed_ratio_original_values_half_even_and_bounds(self):
        for scaled, decimal in (
            (714286, "0.714286"),
            (733333, "0.733333"),
            (692308, "0.692308"),
            (0, "0.000000"),
            (1000000, "1.000000"),
        ):
            r = self.ratio(scaled, decimal)
            self.assertEqual(fixed_ratio(r).decimal_text, decimal)
        # Existing pure integer arithmetic only; NOT an evaluate_ratio operation.
        self.assertEqual(_fixed_ratio(1, 128).scaled_units, 7812)  # 7812.5 -> even
        self.assertEqual(_fixed_ratio(3, 128).scaled_units, 23438)  # 23437.5 -> even

    @staticmethod
    def ratio(scaled=714286, decimal="0.714286"):
        return {
            "type": "fixed_ratio6",
            "scaled_units": uint(scaled),
            "decimal_text": decimal,
            "scale": uint(6),
            "unit": "FRACTION",
            "numeric_policy_ref": rr("NUMERIC_POLICY"),
        }

    def test_ratio_float_exponent_scale_percent_and_mismatch(self):
        for k, v in (
            ("decimal_text", "7.14286e-1"),
            ("decimal_text", "0.733333"),
            ("decimal_text", 0.714286),
            ("scaled_units", uint(1000001)),
            ("scaled_units", uint(-1)),
            ("scale", uint(5)),
            ("unit", "PERCENT"),
        ):
            r = self.ratio()
            r[k] = v
            self.invalid(lambda r=r: fixed_ratio(r))

    def test_mandatory_native_receipt_and_all_invocations(self):
        for invocation in ("RUN", "ATTEMPTED", "NOT_RUN"):
            s = summary(invocation)
            native_summary(s)
            s.pop("invocation_receipt_ref")
            self.invalid(lambda s=s: native_summary(s), "CLOSED_FIELDS")

    def test_no_outcome_cannot_invent_native_summary_state(self):
        s = summary("NOT_RUN")
        del s["state"]
        self.assertEqual(
            sealed_summary_readiness(s).reasons, ("NATIVE_SUMMARY_NO_OUTCOME_AM_D04_3",)
        )
        s["state"] = ne()
        self.assertEqual(sealed_summary_readiness(s).state, State.NOT_SUPPLIED)

    def test_native_semantic_body_closed_scope_and_first_failure(self):
        d = native_body()
        d["invocation"] = "ATTEMPTED"
        d["original_state_fact"] = ne()
        failure = {
            "type": "native_failure",
            "owner": "TEST_ONLY",
            "category": "TEST_EXCEPTION",
            "code": "TEST_FIRST_FAILURE",
            "affected_scope_refs": [],
            "safe_diagnostic": "TEST_ONLY",
            "origin_ref": rr("ORIGIN"),
            "attempted_operation": "TEST_OPERATION",
        }
        d["first_failure"] = failure
        b = parse_body("NATIVE_RECEIPT", raw(d))
        self.assertEqual(b.fields()["first_failure"], failure)
        d["attempt_id"] = "PRIVATE"
        self.invalid(lambda: parse_body("NATIVE_RECEIPT", raw(d)), "CLOSED_FIELDS")

    def test_audit_only_metadata_does_not_enter_stable_body(self):
        semantic = native_body()
        before = raw(semantic)
        audit1 = {
            "attempt_id": "TEST_ATTEMPT_A",
            "host": "TEST_HOST_A",
            "wall_clock": "TEST_TIME_A",
        }
        audit2 = {
            "attempt_id": "TEST_ATTEMPT_B",
            "host": "TEST_HOST_B",
            "wall_clock": "TEST_TIME_B",
        }
        self.assertNotEqual(audit1, audit2)
        self.assertEqual(raw(semantic), before)
        for key in audit1:
            self.invalid(
                lambda key=key: parse_body("NATIVE_RECEIPT", raw({**semantic, key: audit1[key]})),
                "CLOSED_FIELDS",
            )
        changed = native_body(1)
        self.assertNotEqual(raw(changed), before)  # context is semantic

    def test_hidden_attempt_ancestor_and_opaque_input_refuse(self):
        root_ref = rr("NATIVE_RECEIPT")
        root_key = resource(root_ref)
        source_key = parent(core())
        nodes = {
            root_key: DraftNode(
                root_key, parse_body("NATIVE_RECEIPT", raw(native_body())), "SEMANTIC"
            ),
            source_key: DraftNode(source_key, None, "ACTUAL_ATTEMPT"),
        }
        self.invalid(
            lambda: semantic_ancestry(root_key, nodes), "ATTEMPT_OR_FINAL_EVIDENCE_ANCESTRY"
        )
        nodes[source_key] = DraftNode(source_key, None, "OPAQUE_INPUT")
        self.assertEqual(semantic_ancestry(root_key, nodes).state, State.NOT_SUPPLIED)

    def test_cycle_self_parent_and_qual_input_backedge_refuse(self):
        root_key = parent(core())
        nodes = {
            root_key: DraftNode(root_key, parse_body("ORIGIN", raw(origin_body())), "SEMANTIC")
        }
        self.invalid(lambda: semantic_ancestry(root_key, nodes), "REF_CYCLE")
        self.invalid(
            lambda: semantic_ancestry(parent(core("F2-QUALIFICATION"), "F2-QUALIFICATION"), {}),
            "QUAL_INPUT_BACKEDGE",
        )

    def test_deep_attempt_under_origin_refuses(self):
        root_key = resource(rr("NATIVE_RECEIPT"))
        origin_key = resource(rr("ORIGIN"))
        attempt_key = parent(core(marker="8"))
        d = native_body()
        d["tick_context"]["decision_cutoff"]["origin_ref"] = rr("ORIGIN")
        nodes = {
            root_key: DraftNode(root_key, parse_body("NATIVE_RECEIPT", raw(d)), "SEMANTIC"),
            origin_key: DraftNode(
                origin_key, parse_body("ORIGIN", raw(origin_body(core(marker="8")))), "SEMANTIC"
            ),
            attempt_key: DraftNode(attempt_key, None, "CORRESPONDENCE"),
        }
        self.invalid(
            lambda: semantic_ancestry(root_key, nodes), "ATTEMPT_OR_FINAL_EVIDENCE_ANCESTRY"
        )

    def test_correspondence_missing_not_evaluated_and_unverified_match(self):
        self.assertEqual(check_correspondence(None).state, State.NOT_EVALUATED)
        d = {
            "schema_label": "rs-spec-audit-correspondence-proposal-v0.1",
            "record_revision": "TEST_ONLY",
            "issuing_owner": "TEST_ONLY",
            "declared_capture_scope": "NO_REAL_ATTEMPTS",
            "semantic_receipt_ref": rr("NATIVE_RECEIPT"),
            "original_attempt_input_ref": core(),
            "operation": "TEST_ONLY",
            "original_attempt_key": "TEST_ONLY",
            "tick_context": tick(),
            "semantic_projection_schema": "TEST_ONLY",
            "relevant_code_refs": [code()],
            "correspondence": {
                "state": "MATCH",
                "reason": {"owner": "TEST_ONLY", "code": "UNVERIFIED"},
                "verifier_role": "TEST_ONLY",
            },
            "actual_invocation": "RUN",
            "original_failure_pointer": na(),
            "original_observation_pointers": [],
            "access_policy_ref": rr("AUDIT_ACCESS_POLICY"),
            "resolution_receipt_link": ne(),
        }
        correspondence_record(raw(d))
        self.assertIn(
            "UNVERIFIED_MATCH_CLAIM", check_correspondence(raw(d), b"TEST_ONLY_NOT_ACTUAL").reasons
        )
        self.assertEqual(check_correspondence(raw(d)).reasons, ("CORRESPONDENCE_NOT_SUPPLIED",))

    def test_scheduleinput_full_typed_policy_version_and_unknown_fields(self):
        parsed = parse_schedule_input(raw(schedule_input()))
        self.assertEqual(parsed.invariant_policy.kind, "SCHEDULE_INVARIANT_POLICY")
        for k, v in (
            ("invariant_policy_ref", "MUTABLE_ALIAS"),
            ("body_version", "WU01_OLD"),
            ("selected_profile", "SINGLE_CUTOFF"),
        ):
            d = schedule_input()
            d[k] = v
            self.invalid(lambda d=d: parse_schedule_input(raw(d)))
        self.invalid(
            lambda: parse_schedule_input(raw({**schedule_input(), "snapshot_id": "t1"})),
            "CLOSED_FIELDS",
        )

    def test_scheduleinput_af009_stale_policy_schedule_and_input(self):
        inp = parse_schedule_input(raw(schedule_input()))
        sch = parse_body("DECISION_SCHEDULE", raw(schedule()))
        kwargs = dict(
            supplied_input_core=parent(core()),
            invariant_policy_ref=rr("SCHEDULE_INVARIANT_POLICY"),
            sequence_schedule_ref=rr("DECISION_SCHEDULE"),
            schedule_resource_ref=rr("DECISION_SCHEDULE"),
        )
        self.assertEqual(
            schedule_path_check(inp, sch, **kwargs).reasons, ("INVARIANT_POLICY_BODY_NOT_SUPPLIED",)
        )
        for key, value, reason in (
            ("supplied_input_core", parent(core(marker="1")), "STALE_SCHEDULE_INPUT"),
            ("invariant_policy_ref", rr("SCHEDULE_INVARIANT_POLICY", "1"), "AF009_POLICY_MISMATCH"),
            ("sequence_schedule_ref", rr("DECISION_SCHEDULE", "1"), "STALE_SEQUENCE_SCHEDULE"),
        ):
            args = {**kwargs, key: value}
            self.invalid(lambda args=args: schedule_path_check(inp, sch, **args), reason)

    def test_policy_mutation_propagates_dependency_expression_not_digest(self):
        sch = parse_body("DECISION_SCHEDULE", raw(schedule()))
        a = parse_schedule_input(raw(schedule_input()))
        b = parse_schedule_input(raw(schedule_input(rr("SCHEDULE_INVARIANT_POLICY", "1"))))
        self.assertEqual(
            schedule_influence(a, sch), schedule_influence(parse_schedule_input(a.raw), sch)
        )
        self.assertNotEqual(schedule_influence(a, sch), schedule_influence(b, sch))
        self.assertNotEqual(a.raw, b.raw)
        # No claim that unchanged supplied DS/SEQ refs are valid under that mutation.

    def test_policy_change_requires_new_pf038_dependency_and_sequence_schedule_target(self):
        new_input = parse_schedule_input(raw(schedule_input(rr("SCHEDULE_INVARIANT_POLICY", "1"))))
        old_schedule = parse_body("DECISION_SCHEDULE", raw(schedule()))
        kwargs = dict(
            supplied_input_core=parent(core(marker="1")),
            invariant_policy_ref=rr("SCHEDULE_INVARIANT_POLICY", "1"),
            sequence_schedule_ref=rr("DECISION_SCHEDULE"),
            schedule_resource_ref=rr("DECISION_SCHEDULE", "2"),
        )
        self.invalid(
            lambda: schedule_path_check(new_input, old_schedule, **kwargs), "STALE_SCHEDULE_INPUT"
        )
        changed = schedule()
        changed["source_input_ref"] = core(marker="1")
        new_schedule = parse_body("DECISION_SCHEDULE", raw(changed))
        self.invalid(
            lambda: schedule_path_check(new_input, new_schedule, **kwargs),
            "STALE_SEQUENCE_SCHEDULE",
        )
        kwargs["sequence_schedule_ref"] = rr("DECISION_SCHEDULE", "2")
        self.assertEqual(
            schedule_path_check(new_input, new_schedule, **kwargs).state, State.NOT_SUPPLIED
        )
        self.assertNotEqual(
            schedule_influence(parse_schedule_input(raw(schedule_input())), old_schedule),
            schedule_influence(new_input, new_schedule),
        )

    def test_all_five_axes_mandatory_and_external_owners_stay_blocked(self):
        config = configuration()
        self.assertEqual(
            configuration_readiness(parse_body("TEMPORAL_CONFIGURATION", raw(config))).state,
            State.NOT_SUPPLIED,
        )
        for field in (
            "calendar",
            "source_cadence_refs",
            "cutoff_convention",
            "horizon_ref",
            "rebalance_execution_ref",
            "evaluation_ref",
        ):
            d = copy.deepcopy(config)
            del d[field]
            self.invalid(lambda d=d: parse_body("TEMPORAL_CONFIGURATION", raw(d)), "CLOSED_FIELDS")

    def test_sequence_four_member_consistency_and_no_admission(self):
        d, b, si = sequence()
        result = sequence_structure(
            d,
            tuple(parse_body("SEMANTIC_TRACE", raw(v)) for v in b),
            parse_body("DECISION_SCHEDULE", raw(schedule())),
            parse_body("SEMANTIC_TRACE", raw(si)),
        )
        self.assertEqual(result.state, State.NOT_SUPPLIED)
        self.assertFalse(result.admission_eligible)
        self.assertEqual(set(d), SEQ_FIELDS)

    def test_sequence_no_extra_canonical_key_drop_reorder_or_alias(self):
        d, b, si = sequence()
        bindings = tuple(parse_body("SEMANTIC_TRACE", raw(v)) for v in b)
        sch = parse_body("DECISION_SCHEDULE", raw(schedule()))
        set_input = parse_body("SEMANTIC_TRACE", raw(si))
        for mutation in (
            lambda v: v.update(invariant_policy_ref=rr("SCHEDULE_INVARIANT_POLICY")),
            lambda v: v["bindings"].pop(),
            lambda v: v["bindings"].reverse(),
            lambda v: v["bindings"][2].update(qualification_ref=core("F2-QUALIFICATION", "1")),
        ):
            changed = copy.deepcopy(d)
            mutation(changed)
            self.invalid(
                lambda changed=changed: sequence_structure(changed, bindings, sch, set_input)
            )

    def test_accounting_equality_does_not_grant_all_eligible(self):
        d = sequence()[0]["release_state"]
        accounting(d)
        self.invalid(lambda: accounting({**d, "all_eligible": True}), "CLOSED_FIELDS")
        d["accounted_count"] = uint(3)
        self.invalid(lambda: accounting(d), "POSITION_ACCOUNTING")

    def test_set_manifest_preserves_prior_sources_and_limitations_no_backedge(self):
        _, _, si = sequence()
        parsed = parse_body("SEMANTIC_TRACE", raw(si))
        self.assertEqual(parsed.fields()["trace"]["semantic_limitations"], ["TEST_ONLY"])
        changed = copy.deepcopy(si)
        changed["trace"]["semantic_limitations"] = ["CHANGED_SEMANTIC_INPUT"]
        self.assertNotEqual(parsed.raw, parse_body("SEMANTIC_TRACE", raw(changed)).raw)
        si["trace"]["original_source_refs"] = [core("TEMPORAL-SEQUENCE")]
        self.invalid(lambda: parse_body("SEMANTIC_TRACE", raw(si)))

    def test_current_grants_absent_revoked_wrong_context_and_fake_receipt_deny(self):
        request = AccessRequest(
            "TEST_ONLY_F5",
            "READ",
            parent(core("F2-OBSERVATION"), "F2-OBSERVATION"),
            CUTOFFS[0],
            (("SYN-A", "TEST_ONLY"),),
            "SAFE_REFERENCE",
        )
        now = datetime(2027, 1, 7, tzinfo=UTC)
        grant = GrantDeclaration(
            request,
            now - timedelta(days=1),
            now + timedelta(days=1),
            False,
            b"TEST_ONLY_NON_ISSUED",
        )
        self.assertEqual(authorization_check(request, None, now).state, State.DENIED)
        for g in (
            grant,
            replace(grant, revoked=True),
            replace(grant, valid_until=now),
            replace(grant, request=replace(request, principal="OTHER")),
            replace(grant, request=replace(request, operation="AUDIT_READ")),
            replace(grant, request=replace(request, exposure="AUDIT_BODY")),
            replace(grant, request=replace(request, cutoff=CUTOFFS[1])),
            replace(grant, request=replace(request, cohort=(("SYN-B", "TEST_ONLY"),))),
            replace(
                grant,
                request=replace(
                    request, target=parent(core("F2-OBSERVATION", "1"), "F2-OBSERVATION")
                ),
            ),
        ):
            self.assertEqual(
                authorization_check(request, g, now, b"FAKE_RECEIPT").reasons, ("ACCESS_DENIED",)
            )

    def test_withheld_release_never_rewrites_native_invocation_or_first_failure(self):
        for invocation in ("RUN", "ATTEMPTED", "NOT_RUN"):
            s = summary(invocation)
            before = copy.deepcopy(s)
            denied = detached_release(s)
            self.assertEqual(s, before)
            self.assertEqual(
                set(asdict(denied)),
                {"release_state", "owner", "reason", "diagnostic_only", "admission_eligible"},
            )
            self.assertEqual(denied.release_state, "WITHHELD")
            self.assertFalse(denied.admission_eligible)

    def test_safe_whitelist_unknown_withheld_and_no_recursive_private_details(self):
        d = {
            "issuer_ref": "SYN-A",
            "feature_ref": "TEST_ONLY_A04",
            "cutoff": tm(),
            "value": {
                "type": "known",
                "value": {"type": "int64", "value": "140"},
                "origin_ref": rr("ORIGIN"),
            },
            "unit": "NTD_thousands",
            "qualification_ref": core("F2-QUALIFICATION"),
            "scope_flags": dict(FLAGS),
        }
        for value in (
            d["value"],
            unknown(),
            ne(),
            {
                "type": "withheld",
                "owner": "F2",
                "reason": "TEST_ONLY",
                "policy_ref": rr("OBSERVATION_RELEASE_POLICY"),
            },
        ):
            safe_observation_structure({**d, "value": value})
        for extra in (
            "attempt_id",
            "token",
            "native_error",
            "timing",
            "future_price",
            "callback",
            "audit_ref",
        ):
            self.invalid(
                lambda extra=extra: safe_observation_structure({**d, extra: "PRIVATE"}),
                "CLOSED_FIELDS",
            )
        leak = copy.deepcopy(d)
        leak["value"]["origin_ref"]["locator"] = "PRIVATE"
        self.invalid(lambda: safe_observation_structure(leak), "CLOSED_FIELDS")

    def test_frozen_golden_and_original_wu04_static_regression(self):
        fixtures = ROOT / "tests/fixtures/mvp_if03/oracle01_v0_1"
        archived = fixtures / "IF03_ORACLE01_Review_Evidence.zip"
        self.assertEqual(
            sha256(archived.read_bytes()).hexdigest(),
            "b3b74b713dbd43b6ef70f32c6c666c0caf8e5ac08c27d96a2d025cda038bdd34",
        )
        with zipfile.ZipFile(archived) as z:
            self.assertEqual(len(z.infolist()), 409)
            self.assertIsNone(z.testzip())
        wu04 = ROOT / "src/pit_research_lab/mvp/f2/weekly_sequence.py"
        self.assertEqual(
            sha256(wu04.read_bytes()).hexdigest(),
            "367153643a98b29161d5b07502db0bbd3cce823a8867af3165177593f3a18fc2",
        )
        # Inspect accepted source constants, not actual Native execution.
        tree = ast.parse(wu04.read_text())
        pins = next(
            ast.literal_eval(n.value)
            for n in tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "TICK_SHA256S" for t in n.targets)
        )
        self.assertEqual(len(pins), 4)
        flags = next(
            ast.literal_eval(n.value)
            for n in tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "_SCOPE" for t in n.targets)
        )
        self.assertEqual(flags, FLAGS)

    def test_reference_body_exact_kind_schema_version_and_no_pin_authentication(self):
        parsed = parse_reference_body(rr("ORIGIN"), raw(origin_body()))
        self.assertEqual(issuance_readiness(parsed).state, State.NOT_SUPPLIED)
        for key, value in (
            ("resource_schema", "UNREVIEWED_SCHEMA"),
            ("resource_version", "STALE_VERSION"),
        ):
            r = rr("ORIGIN")
            r[key] = value
            self.invalid(
                lambda r=r: parse_reference_body(r, raw(origin_body())), "REF_BODY_SCHEMA_VERSION"
            )
        self.invalid(lambda: parse_reference_body(rr("CALENDAR"), raw(origin_body())))

    def test_rule_table_rejects_gap_overlap_and_reversed_bounds(self):
        for mutate in (
            lambda d: d["coverage"].update(first_local=CUTOFFS[-1], last_local=CUTOFFS[0]),
            lambda d: d["offset_rules"][0].update(start=CUTOFFS[1]),
            lambda d: d["offset_rules"].append(d["offset_rules"][0]),
            lambda d: d["offset_rules"][0].update(end=CUTOFFS[2]),
        ):
            d = draft_examples()["TIMEZONE_RULES"]
            mutate(d)
            self.invalid(lambda d=d: parse_body("TIMEZONE_RULES", raw(d)))

    def test_set_input_duplicate_binding_and_foreign_schema_refuse(self):
        d, bindings, si = sequence()
        si["trace"]["binding_refs"][2] = si["trace"]["binding_refs"][1]
        self.invalid(lambda: parse_body("SEMANTIC_TRACE", raw(si)), "DUPLICATE_ENTRY")
        d, bindings, si = sequence()
        d["bindings"][1]["binding_ref"]["resource_schema"] = "FOREIGN_SCHEMA"
        si["trace"]["binding_refs"][1] = d["bindings"][1]["binding_ref"]
        self.invalid(
            lambda: sequence_structure(
                d,
                tuple(parse_body("SEMANTIC_TRACE", raw(b)) for b in bindings),
                parse_body("DECISION_SCHEDULE", raw(schedule())),
                parse_body("SEMANTIC_TRACE", raw(si)),
            ),
            "REF_BODY_SCHEMA_VERSION",
        )

    def test_rem1_pf042_correct_key_and_order_preserved(self):
        b = binding(0)
        entries = b["trace"]["manifest_source_versions"]["source_version_refs"]
        second = copy.deepcopy(entries[0])
        second["version_ref"] = rr("SOURCE_VERSION", "1")
        entries.insert(0, second)
        parsed = parse_body("SEMANTIC_TRACE", raw(b)).fields()
        self.assertEqual(
            parsed["trace"]["manifest_source_versions"]["source_version_refs"], entries
        )
        self.assertEqual(
            set(parsed["trace"]["manifest_source_versions"]),
            {"manifest_ref", "source_version_refs", "coverage_ref"},
        )

    def test_rem1_pf042_obsolete_key_rejected(self):
        b = binding(0)
        nested = b["trace"]["manifest_source_versions"]
        nested["source_versions"] = nested.pop("source_version_refs")
        self.invalid(lambda: parse_body("SEMANTIC_TRACE", raw(b)), "CLOSED_FIELDS")

    def test_rem1_pf042_both_keys_missing_key_and_extra_key_rejected(self):
        for mutation in ("both", "missing", "extra"):
            with self.subTest(mutation=mutation):
                b = binding(0)
                nested = b["trace"]["manifest_source_versions"]
                if mutation == "both":
                    nested["source_versions"] = copy.deepcopy(nested["source_version_refs"])
                elif mutation == "missing":
                    del nested["source_version_refs"]
                else:
                    nested["unexpected"] = "TEST_ONLY"
                self.invalid(lambda b=b: parse_body("SEMANTIC_TRACE", raw(b)), "CLOSED_FIELDS")

    def test_rem1_pf042_null_nonarray_empty_and_malformed_entries_rejected(self):
        bad_values = (None, {}, [], [{}], [rr("SOURCE_VERSION")])
        for index, bad in enumerate(bad_values):
            with self.subTest(case=index):
                b = binding(0)
                b["trace"]["manifest_source_versions"]["source_version_refs"] = bad
                self.invalid(lambda b=b: parse_body("SEMANTIC_TRACE", raw(b)))

    def test_rem1_pf042_wrong_source_version_ref_type_rejected(self):
        b = binding(0)
        entry = b["trace"]["manifest_source_versions"]["source_version_refs"][0]
        entry["body_ref"] = core("F2-QUALIFICATION")
        self.invalid(lambda: parse_body("SEMANTIC_TRACE", raw(b)))

    def test_rem1_manifest_retains_its_own_source_versions_key(self):
        example = draft_examples()["MANIFEST"]
        self.assertIn("source_versions", parse_body("MANIFEST", raw(example)).fields())
        example["source_version_refs"] = example.pop("source_versions")
        self.invalid(lambda: parse_body("MANIFEST", raw(example)), "CLOSED_FIELDS")

    def test_rem1_explicit_matching_references_remain_non_issued(self):
        result = sequence_structure(*rem1_sequence_inputs(), **rem1_expected_refs())
        self.assertEqual(result.state, State.NOT_SUPPLIED)
        self.assertIn("IMMUTABLE_SOURCE_BYTES_VERIFICATION_NOT_SUPPLIED", result.reasons)
        self.assertFalse(result.admission_eligible)
        self.assertTrue(result.diagnostic_only)

    def test_rem1_foreign_seq_schedule_rejected(self):
        value, *rest = rem1_sequence_inputs()
        value["schedule_ref"] = rr("DECISION_SCHEDULE", "1")
        self.invalid(
            lambda: sequence_structure(value, *rest, **rem1_expected_refs()),
            "STALE_SEQUENCE_SCHEDULE",
        )

    def test_rem1_foreign_seq_provenance_rejected(self):
        value, *rest = rem1_sequence_inputs()
        value["provenance_ref"] = rr("SEMANTIC_TRACE", "8")
        self.invalid(
            lambda: sequence_structure(value, *rest, **rem1_expected_refs()),
            "STALE_SEQUENCE_PROVENANCE",
        )

    def test_rem1_foreign_schedule_source_input_rejected(self):
        value, bindings, sch, si = rem1_sequence_inputs()
        changed = sch.fields()
        changed["source_input_ref"] = core(marker="1")
        self.invalid(
            lambda: sequence_structure(
                value,
                bindings,
                parse_body("DECISION_SCHEDULE", raw(changed)),
                si,
                **rem1_expected_refs(),
            ),
            "STALE_SCHEDULE_INPUT",
        )

    def test_rem1_foreign_expected_schedule_rejected(self):
        context = rem1_expected_refs()
        context["expected_schedule_ref"] = rr("DECISION_SCHEDULE", "1")
        self.invalid(
            lambda: sequence_structure(*rem1_sequence_inputs(), **context),
            "STALE_SEQUENCE_SCHEDULE",
        )

    def test_rem1_foreign_expected_provenance_rejected(self):
        context = rem1_expected_refs()
        context["expected_provenance_ref"] = rr("SEMANTIC_TRACE", "8")
        self.invalid(
            lambda: sequence_structure(*rem1_sequence_inputs(), **context),
            "STALE_SEQUENCE_PROVENANCE",
        )

    def test_rem1_foreign_expected_source_input_rejected(self):
        context = rem1_expected_refs()
        context["expected_schedule_input_core"] = core(marker="1")
        self.invalid(
            lambda: sequence_structure(*rem1_sequence_inputs(), **context), "STALE_SCHEDULE_INPUT"
        )

    def test_rem1_expected_reference_kinds_domains_and_versions_checked(self):
        for key, bad in (
            ("expected_schedule_ref", rr("CALENDAR")),
            ("expected_provenance_ref", rr("NATIVE_RECEIPT")),
            ("expected_schedule_input_core", core("F2-QUALIFICATION")),
        ):
            with self.subTest(key=key):
                context = rem1_expected_refs()
                context[key] = bad
                self.invalid(
                    lambda context=context: sequence_structure(*rem1_sequence_inputs(), **context)
                )
        context = rem1_expected_refs()
        context["expected_schedule_ref"]["resource_version"] = "TEST_ONLY_STALE_VERSION"
        self.invalid(
            lambda: sequence_structure(*rem1_sequence_inputs(), **context),
            "STALE_SEQUENCE_SCHEDULE",
        )

    def test_rem1_set_input_subtype_substitution_rejected(self):
        value, bindings, sch, _ = rem1_sequence_inputs()
        foreign = parse_body("SEMANTIC_TRACE", raw(draft_examples()["SEMANTIC_TRACE"]))
        self.invalid(
            lambda: sequence_structure(value, bindings, sch, foreign, **rem1_expected_refs()),
            "SET_INPUT_SUBTYPE",
        )

    def test_rem1_set_input_ordered_binding_refs_substitution_rejected(self):
        value, bindings, sch, si = rem1_sequence_inputs()
        changed = si.fields()
        changed["trace"]["binding_refs"].reverse()
        self.invalid(
            lambda: sequence_structure(
                value,
                bindings,
                sch,
                parse_body("SEMANTIC_TRACE", raw(changed)),
                **rem1_expected_refs(),
            ),
            "SET_INPUT_BINDING_ORDER",
        )

    def test_rem1_expected_original_manifest_mismatch_rejected(self):
        context = rem1_expected_refs()
        context["expected_manifest_ref"] = rr("MANIFEST", "1")
        self.invalid(
            lambda: sequence_structure(*rem1_sequence_inputs(), **context),
            "SET_INPUT_MANIFEST_MISMATCH",
        )

    def test_rem1_set_input_original_manifest_mutation_rejected(self):
        value, bindings, sch, si = rem1_sequence_inputs()
        changed = si.fields()
        changed["trace"]["manifest_ref"] = rr("MANIFEST", "1")
        self.invalid(
            lambda: sequence_structure(
                value,
                bindings,
                sch,
                parse_body("SEMANTIC_TRACE", raw(changed)),
                **rem1_expected_refs(),
            ),
            "SET_INPUT_MANIFEST_MISMATCH",
        )

    def test_rem1_expected_original_sources_mismatch_rejected(self):
        context = rem1_expected_refs()
        context["expected_original_source_refs"] = [core(marker="1")]
        self.invalid(
            lambda: sequence_structure(*rem1_sequence_inputs(), **context),
            "SET_INPUT_SOURCE_REFS_MISMATCH",
        )

    def test_rem1_set_input_original_sources_mutation_rejected(self):
        value, bindings, sch, si = rem1_sequence_inputs()
        changed = si.fields()
        changed["trace"]["original_source_refs"] = [core(marker="1")]
        self.invalid(
            lambda: sequence_structure(
                value,
                bindings,
                sch,
                parse_body("SEMANTIC_TRACE", raw(changed)),
                **rem1_expected_refs(),
            ),
            "SET_INPUT_SOURCE_REFS_MISMATCH",
        )

    def test_rem1_expected_original_sources_order_preserved(self):
        value, bindings, sch, si = rem1_sequence_inputs()
        changed = si.fields()
        changed["trace"]["original_source_refs"].append(rr("SOURCE_VERSION", "1"))
        si = parse_body("SEMANTIC_TRACE", raw(changed))
        context = rem1_expected_refs()
        context["expected_original_source_refs"] = [core(), rr("SOURCE_VERSION", "1")]
        self.assertEqual(
            sequence_structure(value, bindings, sch, si, **context).state, State.NOT_SUPPLIED
        )
        context["expected_original_source_refs"].reverse()
        self.invalid(
            lambda: sequence_structure(value, bindings, sch, si, **context),
            "SET_INPUT_SOURCE_REFS_MISMATCH",
        )

    def test_rem1_missing_reference_context_explicitly_blocked(self):
        result = sequence_structure(*rem1_sequence_inputs())
        self.assertEqual(result.state, State.NOT_SUPPLIED)
        for reason in (
            "EXPECTED_SCHEDULE_REF_NOT_SUPPLIED",
            "EXPECTED_PROVENANCE_REF_NOT_SUPPLIED",
            "EXPECTED_SCHEDULE_INPUT_CORE_NOT_SUPPLIED",
            "EXPECTED_MANIFEST_REF_NOT_SUPPLIED",
            "EXPECTED_ORIGINAL_SOURCE_REFS_NOT_SUPPLIED",
        ):
            self.assertIn(reason, result.reasons)

    def test_rem1_each_missing_expectation_remains_blocked(self):
        for key, reason in (
            ("expected_schedule_ref", "EXPECTED_SCHEDULE_REF_NOT_SUPPLIED"),
            ("expected_provenance_ref", "EXPECTED_PROVENANCE_REF_NOT_SUPPLIED"),
            ("expected_schedule_input_core", "EXPECTED_SCHEDULE_INPUT_CORE_NOT_SUPPLIED"),
            ("expected_manifest_ref", "EXPECTED_MANIFEST_REF_NOT_SUPPLIED"),
            ("expected_original_source_refs", "EXPECTED_ORIGINAL_SOURCE_REFS_NOT_SUPPLIED"),
            ("source_input", "SCHEDULE_INPUT_BODY_NOT_SUPPLIED"),
            ("invariant_policy_ref", "INVARIANT_POLICY_REF_NOT_SUPPLIED"),
        ):
            with self.subTest(key=key):
                context = rem1_expected_refs()
                del context[key]
                self.assertIn(
                    reason, sequence_structure(*rem1_sequence_inputs(), **context).reasons
                )

    def test_rem1_missing_context_does_not_hide_known_contradiction(self):
        value, *rest = rem1_sequence_inputs()
        value["schedule_ref"] = rr("DECISION_SCHEDULE", "1")
        context = rem1_expected_refs()
        del context["expected_provenance_ref"]
        self.invalid(lambda: sequence_structure(value, *rest, **context), "STALE_SEQUENCE_SCHEDULE")

    def test_rem1_changed_scheduleinput_policy_retaining_old_route_rejected(self):
        context = rem1_expected_refs()
        context["source_input"] = parse_schedule_input(
            raw(schedule_input(rr("SCHEDULE_INVARIANT_POLICY", "1")))
        )
        self.invalid(
            lambda: sequence_structure(*rem1_sequence_inputs(), **context), "AF009_POLICY_MISMATCH"
        )

    def test_rem1_explicit_context_preserves_four_position_rejections(self):
        for mutation in ("swap", "repeat", "drop", "fifth_W03"):
            with self.subTest(mutation=mutation):
                value, *rest = rem1_sequence_inputs()
                if mutation == "swap":
                    value["bindings"][1], value["bindings"][2] = (
                        value["bindings"][2],
                        value["bindings"][1],
                    )
                elif mutation == "repeat":
                    value["bindings"][2] = copy.deepcopy(value["bindings"][1])
                elif mutation == "drop":
                    value["bindings"].pop()
                else:
                    extra = copy.deepcopy(value["bindings"][0])
                    extra["tick"]["tick_id"] = "TEST_ONLY_PHANTOM_W03"
                    value["bindings"].append(extra)
                self.invalid(
                    lambda value=value, rest=rest: sequence_structure(
                        value, *rest, **rem1_expected_refs()
                    )
                )


if __name__ == "__main__":
    unittest.main()
