"""Pure authored wire claims; no native execution or artifact verification occurs."""

import ast
import copy
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from pit_research_lab.mvp.f6 import contracts as c

ROOT = Path(__file__).absolute().parents[3]
FIXTURES = ROOT / "tests/fixtures/mvp_f6"
APP_ID = "00000000-0000-4000-8000-000000000001"
ATTEMPT_ID = "00000000-0000-4000-8000-000000000002"
REPLAY_ID = "00000000-0000-4000-8000-000000000003"
NOW = "2026-11-20T00:00:00+00:00"


def ref(kind, digest="1" * 64):
    return {"kind": kind.value, "sha256": digest}


def refs(complete=True, attempt=ATTEMPT_ID):
    if not complete:
        return {
            k: c.unavailable(c.Reason.NOT_STARTED) for k in ("native_attempt_id", *c.REF_FIELDS)
        }
    return {
        "native_attempt_id": c.present(attempt),
        **{
            field: c.present(
                ref(
                    kind,
                    c.PROTOCOL_SHA256
                    if field == "protocol_ref"
                    else c.DATASET_SHA256
                    if field == "dataset_digest"
                    else "2" * 64
                    if field == "result_ref"
                    else "3" * 64
                    if field == "evidence_ref"
                    else "1" * 64,
                )
            )
            for field, kind in c.REF_FIELDS.items()
        },
    }


def verification(passed=False):
    return {
        "state": "PASSED_NATIVE_DIRECTORY_AND_APP_LINKS" if passed else "NOT_CHECKED",
        "scope": "NATIVE_F3_ARTIFACTS_AND_APP_LAUNCH_BINDING",
        "checked_at": c.present(NOW) if passed else c.unavailable(c.Reason.NOT_YET_AVAILABLE),
        "manifest_sha256": c.present("f" * 64)
        if passed
        else c.unavailable(c.Reason.NOT_YET_AVAILABLE),
        "failure": c.unavailable(c.Reason.NO_FAILURE),
    }


def metric():
    names = (
        "absolute_error_sum",
        "sse",
        "signed_error_sum",
        "baseline_sse",
        "mae",
        "mse",
        "mean_prediction_error",
        "residual_variance_population",
        "minimum_residual",
        "maximum_residual",
    )
    return {
        "n": 2,
        "exact": {
            **{k: {"numerator": "0", "denominator": "1"} for k in names},
            c.ADJACENT_METRIC: c.unavailable(c.Reason.NO_ADJACENT_PAIRS),
        },
        "display": {
            **{k: "0.000000000000" for k in names},
            c.ADJACENT_METRIC: c.unavailable(c.Reason.NO_ADJACENT_PAIRS),
            "rmse": "0.000000000000",
            "oos_improvement": c.unavailable(c.Reason.ZERO_BASELINE_SSE),
        },
        "oos_improvement": {"state": "NOT_COMPUTABLE", "reason": "ZERO_BASELINE_SSE"},
        "units": c.UNITS,
        "iid_inference": "NOT_PERFORMED",
        "adjacent_residual_pairs": 0,
        "diagnostic_interpretation": c.DIAGNOSTIC,
    }


def fold(name):
    return {
        "fold": name,
        "state_id": ref(c.ReferenceKind.STATE),
        "fit_cutoff": "2025-01-01T17:00:00+08:00",
        "history_candidates": [0, 47] if name == "F1" else [0, 71],
        "test_ticks": [48, 71] if name == "F1" else [72, 95],
        "training_count": 180,
        "training_cutoffs": 40,
        "training_issuers": 3,
        "scored_count": 80,
        "scored_cutoffs": 20,
        "excluded_training_count": 0,
        "exclusion_counts": [],
        "latest_training_label_availability": "2024-12-31T18:00:00+08:00",
        "distinct_issuer_month_releases": 20,
        "distinct_source_versions": 20,
        **{k: {"numerator": "0", "denominator": "1"} for k in ("alpha", "beta", "gbar", "rbar")},
        "metrics": {**metric(), "n": 80},
    }


def fact():
    return {
        "month": "2024-01",
        "state": "ABSENT",
        "native_state": "NO_QUALIFIED_CLAIM",
        "reason": "MISSING_PREDECESSOR",
        "unit": "NTD_thousands",
        "basis": "consolidated-v1",
        **{
            k: c.unavailable(c.Reason.MISSING_PREDECESSOR)
            for k in (
                "source_ref",
                "version_ref",
                "qualification_ref",
                "publication",
                "available_at",
            )
        },
    }


def payload(kind):
    if kind == c.Kind.SUBMISSION_REQUEST:
        return dict(
            schema_version=c.VERSION,
            kind=kind.value,
            capability_id=c.CAPABILITY_ID,
            capability_revision="0" * 64,
            data_mode="SYNTHETIC_GOLDEN",
            idempotency_key=APP_ID,
        )
    if kind == c.Kind.ERROR:
        return dict(
            schema_version=c.VERSION,
            kind=kind.value,
            code="INVALID_REQUEST",
            request_id=APP_ID,
            app_run_id=c.unavailable(c.Reason.NOT_STARTED),
        )
    if kind == c.Kind.CAPABILITY:
        fixture = json.loads((FIXTURES / "projection_v0_1.json").read_bytes())
        return fixture["scenarios"][0]["wire"]["payload"]
    if kind == c.Kind.RUN_RECEIPT:
        return dict(
            app_run_id=APP_ID,
            run_kind="EXPERIMENT",
            replay_of_app_run_id=c.unavailable(c.Reason.NOT_A_REPLAY),
            accepted_at=NOW,
            idempotency_key=APP_ID,
            request_fingerprint="4" * 64,
            capability_id=c.CAPABILITY_ID,
            capability_revision="0" * 64,
            native_refs=refs(False),
            status_path=c.BASE_PATH + APP_ID,
        )
    if kind == c.Kind.RUN_STATUS:
        return dict(
            app_run_id=APP_ID,
            run_kind="EXPERIMENT",
            replay_of_app_run_id=c.unavailable(c.Reason.NOT_A_REPLAY),
            catalog_revision="0",
            phase="VERIFYING",
            accepted_at=NOW,
            updated_at=NOW,
            started_at=c.present(NOW),
            finished_at=c.unavailable(c.Reason.NOT_YET_AVAILABLE),
            native_refs=refs(),
            native_execution_status=c.present("SUCCEEDED"),
            completed_stages=[],
            first_failure=c.unavailable(c.Reason.NO_FAILURE),
            release=dict(
                state="UNAVAILABLE", reason="RESULT_NOT_RELEASED", verification=verification()
            ),
            result_path=c.unavailable(c.Reason.RESULT_NOT_RELEASED),
            evidence_path=c.unavailable(c.Reason.RESULT_NOT_RELEASED),
        )
    if kind == c.Kind.VERIFIED_RESULT:
        return dict(
            app_run_id=APP_ID,
            native_refs=refs(),
            verification=verification(True),
            question=c.QUESTION,
            h0="beta = 0",
            h1="beta != 0",
            method_id=c.METHOD,
            decision_frequency="WEEKLY",
            horizon_sessions=20,
            seed=17,
            interpretation=c.INTERPRETATION,
            aggregate={**metric(), "n": 160},
            folds=[fold("F1"), fold("F2")],
            dependence=dict(
                weekly_rows_are_independent=False,
                target_overlap=True,
                overlapping_within_issuer_scored_window_pairs=1,
                common_price_shocks=True,
                effective_sample_size="NOT_ESTIMATED",
                interpretation="NO_H0_REJECTION_OR_POPULATION_INFERENCE",
            ),
        )
    if kind == c.Kind.EVIDENCE_PROVENANCE:
        cutoffs = [
            (date(2024, 3, 8) + timedelta(weeks=i)).isoformat() + "T18:00:00+08:00"
            for i in range(96)
        ]
        return dict(
            app_run_id=APP_ID,
            native_refs=refs(),
            verification=verification(True),
            evidence_scope="EXECUTED_AUTHORED_SYNTHETIC_RESEARCH_ONLY",
            test_execution_attestation="NOT_ATTESTED_BY_EXPERIMENT_RUNTIME",
            application_build_ref="a" * 64,
            resource_policy_ref="b" * 64,
            native_code_claim="ACTUAL_UNCOMMITTED_WORKTREE_BYTES_NOT_HEAD_CONTENT",
            native_base_head="0" * 40,
            runtime=dict(python="3.12.13 AUTHORED", implementation="CPython"),
            source_file_pins=[],
            source_bytes_sha256=c.SOURCE_SHA256,
            manifest_bytes_sha256=c.MANIFEST_SHA256,
            artifacts=[
                dict(
                    name=n,
                    byte_length="1",
                    sha256="2" * 64
                    if n == "result.json"
                    else "3" * 64
                    if n == "evidence.json"
                    else "1" * 64,
                    role="ATTEMPT_METADATA" if n == "attempt.json" else "DETERMINISTIC_CONTENT",
                )
                for n in c.ARTIFACTS
            ],
            source_summary=dict(
                dataset_digest=ref(c.ReferenceKind.DATASET, c.DATASET_SHA256),
                calendar_id="SYN-L1-CALENDAR-V1",
                issuer_roster=list(c.ISSUERS),
                cutoffs=cutoffs,
                calendar_coverage=["2024-01-01", "2026-02-28"],
                revenue_declarations=131,
                price_marks=1,
                scope="AUTHORED_SYNTHETIC_PUBLIC_ONLY",
                non_if03=True,
                admission_eligible=False,
                source_authentication="NOT_ESTABLISHED",
                native_invocations=0,
                invocation_count_scope="TOP_LEVEL_ASOF_AND_EXPLICIT_S1_S2_CALLS_EXCLUDES_TRANSITIVE_REPLAY",
            ),
            observation_trace=[
                dict(
                    sample_id=f"{issuer}:t{tick:02}",
                    issuer=issuer,
                    tick=tick,
                    cutoff=cutoff,
                    binding_id=ref(c.ReferenceKind.BINDING),
                    current=fact(),
                    previous=fact(),
                )
                for tick, cutoff in enumerate(cutoffs)
                for issuer in c.ISSUERS
            ],
            native_receipts=[],
        )
    assert kind == c.Kind.BASIC_REPLAY_RESULT
    return dict(
        original_app_run_id=APP_ID,
        replay_app_run_id=REPLAY_ID,
        mode="FRESH_PROCESS_NATIVE_RESEARCH_REPLAY",
        state="MATCH",
        original_native_refs=refs(),
        replay_native_refs=refs(attempt=REPLAY_ID),
        original_verification=verification(True),
        replay_verification=verification(True),
        basis_check=dict(state="SAME", reasons=[]),
        comparisons=[
            dict(
                artifact=n,
                original_sha256="2" * 64
                if n == "result.json"
                else "3" * 64
                if n == "evidence.json"
                else "1" * 64,
                replay_sha256="2" * 64
                if n == "result.json"
                else "3" * 64
                if n == "evidence.json"
                else "1" * 64,
                byte_equal=True,
            )
            for n in c.DETERMINISTIC_ARTIFACTS
        ],
        compared_at=c.present(NOW),
        first_failure=c.unavailable(c.Reason.NO_FAILURE),
        scope="NATIVE_DETERMINISTIC_RESEARCH_BYTES_ONLY",
        attempt_metadata_policy="EXPECT_DISTINCT_ATTEMPT_UUID_EXCLUDE_WALL_TIME_AND_DURATION_FROM_CONTENT_EQUALITY",
    )


def example(kind):
    value = payload(kind)
    if kind in (c.Kind.SUBMISSION_REQUEST, c.Kind.ERROR):
        return value
    execution = (
        "NOT_RUN"
        if kind == c.Kind.CAPABILITY
        else "PENDING"
        if kind == c.Kind.RUN_RECEIPT
        else "RUNNING"
        if kind == c.Kind.RUN_STATUS
        else "SUCCEEDED"
    )
    provenance = (
        "NOT_EXECUTED" if kind in (c.Kind.CAPABILITY, c.Kind.RUN_RECEIPT) else "ACTUAL_F3_CLI"
    )
    return dict(
        schema_version=c.VERSION,
        kind=kind.value,
        non_if03=True,
        data_mode="SYNTHETIC_GOLDEN",
        pit_status="UNRESOLVED",
        execution_status=execution,
        evidence_class="UNVERIFIED",
        execution_provenance=provenance,
        source_refs=[],
        limitations=[*c.NATIVE_LIMITATIONS, *c.APP_LIMITATIONS],
        payload=value,
    )


@pytest.mark.parametrize("kind", list(c.Kind))
def test_all_closed_claim_shapes_and_detached_serialization(kind):
    source = example(kind)
    model = c.DOCUMENT_TYPES[kind].from_wire(source)
    encoded = model.serialize()
    assert c.parse_document(encoded).to_wire() == source
    assert encoded == c.canonical_json(source)
    source["extra"] = "mutation"
    assert "extra" not in model.to_wire()
    detached = model.to_wire()
    detached.clear()
    assert model.serialize() == encoded
    with pytest.raises((AttributeError, TypeError)):
        model.authenticated = True


@pytest.mark.parametrize("kind", list(c.Kind))
def test_missing_extra_version_kind_and_wrong_model_refuse(kind):
    source = example(kind)
    for field in source:
        changed = copy.deepcopy(source)
        del changed[field]
        with pytest.raises(c.ContractError):
            c.DOCUMENT_TYPES[kind].from_wire(changed)
    for field, value in (("unexpected", True), ("schema_version", "V999"), ("kind", "FUTURE")):
        changed = copy.deepcopy(source)
        changed[field] = value
        with pytest.raises(c.ContractError):
            c.DOCUMENT_TYPES[kind].from_wire(changed)
    with pytest.raises(c.ContractError):
        c.SubmissionRequest.from_wire(example(c.Kind.CAPABILITY))


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}',
        b'{"a":{"b":1,"b":2}}',
        b'{"a":0.1}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b'{"a":-Infinity}',
        b'{"a":1e2}',
        b"{} trailing",
        b"\xff",
    ],
)
def test_duplicate_and_invalid_json_numbers_refuse(raw):
    with pytest.raises(c.ContractError):
        c.decode_json(raw)


@pytest.mark.parametrize("value", [0.0, float("nan"), float("inf"), (1, 2), {1: "a"}, "\ud800"])
def test_serialization_rejects_non_json_values(value):
    with pytest.raises(c.ContractError):
        c.canonical_json(value)


def test_json_utf8_key_order_and_no_unicode_normalization():
    assert c.canonical_json({"é": "e\u0301", "a": "中"}) == '{"a":"中","é":"é"}'.encode()
    assert c.canonical_json({"a": "é"}) != c.canonical_json({"a": "e\u0301"})


@pytest.mark.parametrize("bad", [True, False, -1, 2**53, "1", 1.0])
def test_safe_integer_refusal(bad):
    with pytest.raises(c.ContractError):
        c.uint(bad)


@pytest.mark.parametrize("bad", ["", "00", "01", "-1", "+1", "1.0", 1, True])
def test_uint_text_refusal(bad):
    with pytest.raises(c.ContractError):
        c.uint_text(bad)


@pytest.mark.parametrize(
    "bad",
    [
        APP_ID.upper().replace("4000", "4A00"),
        APP_ID.replace("4000", "1000"),
        APP_ID.replace("-", ""),
        "{" + APP_ID + "}",
        True,
    ],
)
def test_uuid_canonical_v4_refusal(bad):
    with pytest.raises(c.ContractError):
        c.uuid4_text(bad)


@pytest.mark.parametrize("bad", ["A" * 64, "f" * 63, "g" * 64, "sha256:" + "a" * 64, True])
def test_sha_grammar_refusal(bad):
    with pytest.raises(c.ContractError):
        c.sha256_text(bad)


@pytest.mark.parametrize(
    "bad",
    [
        "2026-11-20",
        "2026-11-20T00:00:00Z",
        "2026-11-20T00:00:00",
        "2026-02-30T00:00:00+00:00",
        "2026-11-20T00:00:00+08:00",
    ],
)
def test_app_timestamp_refusal(bad):
    with pytest.raises(c.ContractError):
        c.timestamp(bad)


@pytest.mark.parametrize(
    "wire",
    [
        {"numerator": "-0", "denominator": "1"},
        {"numerator": "0", "denominator": "2"},
        {"numerator": "+1", "denominator": "1"},
        {"numerator": "01", "denominator": "1"},
        {"numerator": "1", "denominator": "0"},
        {"numerator": "1", "denominator": "-2"},
        {"numerator": "2", "denominator": "4"},
        {"numerator": "1", "denominator": "02"},
        {"numerator": True, "denominator": "1"},
        {"numerator": 1.0, "denominator": "1"},
        {"numerator": "1e3", "denominator": "1"},
        {"numerator": "9" * 4097, "denominator": "1"},
        {"numerator": "1", "denominator": "9" * 4097},
        {"numerator": "1", "denominator": "1", "display": "1.0"},
    ],
)
def test_fraction_native_grammar_reduction_and_limits(wire):
    with pytest.raises(c.ContractError):
        c.ExactFraction.from_wire(wire)


def test_fraction_precision_zero_and_4096_digit_boundaries():
    for n, d in (
        ("0", "1"),
        ("9007199254740993", "9007199254740992"),
        ("-" + "9" * 4096, "1"),
        ("1", "9" * 4096),
    ):
        wire = {"numerator": n, "denominator": d}
        assert c.ExactFraction.from_wire(wire).to_wire() == wire
    assert c.uint(2**53 - 1) == 2**53 - 1
    assert c.uint_text("9" * 100) == "9" * 100


@pytest.mark.parametrize(
    "slot",
    [
        {"state": "PRESENT"},
        {"state": "PRESENT", "value": ATTEMPT_ID, "reason": "NO_FAILURE"},
        {"state": "UNAVAILABLE", "reason": "INVENTED"},
        {"state": "UNAVAILABLE", "reason": "NOT_STARTED", "value": ATTEMPT_ID},
        {"state": "UNKNOWN", "reason": "NOT_STARTED"},
        None,
    ],
)
def test_reference_slots_are_closed(slot):
    source = example(c.Kind.RUN_RECEIPT)
    source["payload"]["native_refs"]["native_attempt_id"] = slot
    with pytest.raises(c.ContractError):
        c.ApplicationRunReceipt.from_wire(source)


def test_native_reference_domains_and_required_release_refs():
    source = example(c.Kind.VERIFIED_RESULT)
    for field in c.REF_FIELDS:
        changed = copy.deepcopy(source)
        changed["payload"]["native_refs"][field] = c.present(ref(c.ReferenceKind.BINDING))
        with pytest.raises(c.ContractError):
            c.VerifiedResultView.from_wire(changed)
        changed["payload"]["native_refs"][field] = c.unavailable(c.Reason.NOT_YET_AVAILABLE)
        with pytest.raises(c.ContractError, match="SOURCE_REFERENCE_MISSING"):
            c.VerifiedResultView.from_wire(changed)
    changed = copy.deepcopy(source)
    changed["payload"]["native_refs"]["protocol_ref"]["value"]["sha256"] = "0" * 64
    with pytest.raises(c.ContractError):
        c.VerifiedResultView.from_wire(changed)


def test_submission_cannot_override_fixed_configuration():
    source = example(c.Kind.SUBMISSION_REQUEST)
    for key in (
        "seed",
        "method",
        "protocol",
        "cutoff",
        "dataset_path",
        "output_dir",
        "args",
        "shell",
        "env",
    ):
        with pytest.raises(c.ContractError):
            c.SubmissionRequest.from_wire({**source, key: 17})
    for field in ("capability_id", "data_mode"):
        with pytest.raises(c.ContractError):
            c.SubmissionRequest.from_wire({**source, field: "UNSUPPORTED"})
    descriptor = c.CapabilityDescriptor.from_wire(example(c.Kind.CAPABILITY))
    source["capability_revision"] = descriptor.to_wire()["payload"]["capability_revision"]
    with pytest.raises(c.ContractError, match="SERVICE_NOT_READY"):
        c.validate_submission_selection(c.SubmissionRequest.from_wire(source), descriptor)
    source["capability_revision"] = "0" * 64
    with pytest.raises(c.ContractError, match="CAPABILITY_CHANGED"):
        c.validate_submission_selection(c.SubmissionRequest.from_wire(source), descriptor)


@pytest.mark.parametrize(
    "field,value",
    [
        ("seed", 18),
        ("seed", True),
        ("cutoff_count", 95),
        ("issuer_count", 6),
        ("horizon_sessions", 21),
        ("decision_frequency", "DAILY"),
        ("native_protocol_schema", "V999"),
        ("numeric_policy", "FLOAT"),
        ("method_id", "OTHER"),
    ],
)
def test_capability_fixed_parameters(field, value):
    source = example(c.Kind.CAPABILITY)
    source["payload"][field] = value
    with pytest.raises(c.ContractError):
        c.CapabilityDescriptor.from_wire(source)


def test_capability_readiness_needs_policy_and_consistent_reasons():
    source = example(c.Kind.CAPABILITY)
    source["payload"].update(readiness="EXECUTABLE", unavailable_reasons=[], submission_gate="OPEN")
    with pytest.raises(c.ContractError):
        c.CapabilityDescriptor.from_wire(source)


@pytest.mark.parametrize(
    "field,value",
    [
        ("pit_status", "ELIGIBLE"),
        ("pit_status", "INELIGIBLE"),
        ("pit_status", "UNKNOWN"),
        ("evidence_class", "SYNTHETIC_VERIFIED_IN_SCOPE"),
        ("evidence_class", "HISTORICAL_PIT_SUPPORTED_IN_SCOPE"),
        ("data_mode", "REAL_TWSE_PILOT"),
    ],
)
def test_no_status_or_evidence_promotion(field, value):
    source = example(c.Kind.VERIFIED_RESULT)
    source[field] = value
    with pytest.raises(c.ContractError):
        c.VerifiedResultView.from_wire(source)


def test_early_native_success_is_independent_of_release_and_execution():
    source = example(c.Kind.RUN_STATUS)
    assert c.RunStatusResponse.from_wire(source).to_wire()["execution_status"] == "RUNNING"
    source["execution_status"] = "SUCCEEDED"
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)
    source["execution_status"] = "RUNNING"
    source["payload"]["release"]["state"] = "AVAILABLE"
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)


def test_fixture_cannot_claim_actual_success_or_release():
    source = example(c.Kind.RUN_STATUS)
    source.update(execution_provenance="FIXTURE_ONLY", execution_status="NOT_RUN")
    source["limitations"].append(c.FIXTURE_LIMITATION)
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)
    source["execution_status"] = "SUCCEEDED"
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)
    result = example(c.Kind.VERIFIED_RESULT)
    result.update(execution_provenance="FIXTURE_ONLY", execution_status="NOT_RUN")
    result["limitations"].append(c.FIXTURE_LIMITATION)
    with pytest.raises(c.ContractError):
        c.VerifiedResultView.from_wire(result)


def test_withheld_cannot_disclose_result_and_limitations_are_exact():
    source = example(c.Kind.VERIFIED_RESULT)
    source["pit_status"] = "WITHHELD"
    with pytest.raises(c.ContractError, match="NATIVE_WITHHELD"):
        c.VerifiedResultView.from_wire(source)
    source["pit_status"] = "UNRESOLVED"
    for index in range(8):
        changed = copy.deepcopy(source)
        del changed["limitations"][index]
        with pytest.raises(c.ContractError):
            c.VerifiedResultView.from_wire(changed)


def test_nested_shapes_and_display_unavailability_are_not_passthrough():
    source = example(c.Kind.VERIFIED_RESULT)
    for path in (("aggregate",), ("aggregate", "exact"), ("aggregate", "display"), ("dependence",)):
        changed = copy.deepcopy(source)
        obj = changed["payload"]
        for key in path:
            obj = obj[key]
        obj["unreviewed"] = 1
        with pytest.raises(c.ContractError):
            c.VerifiedResultView.from_wire(changed)
    for display in ("-0.000000000000", "1.0", 0.0, "NaN"):
        changed = copy.deepcopy(source)
        changed["payload"]["aggregate"]["display"]["rmse"] = display
        with pytest.raises(c.ContractError):
            c.VerifiedResultView.from_wire(changed)
    changed = copy.deepcopy(source)
    changed["payload"]["aggregate"]["display"]["oos_improvement"] = c.present("0.000000000000")
    with pytest.raises(c.ContractError):
        c.VerifiedResultView.from_wire(changed)


def test_replay_comparison_claims_require_consistent_distinct_identities():
    source = example(c.Kind.BASIC_REPLAY_RESULT)
    for mutate in (
        lambda p: p.update(replay_app_run_id=APP_ID),
        lambda p: p["replay_native_refs"].update(native_attempt_id=c.present(ATTEMPT_ID)),
        lambda p: p["replay_verification"].update(state="NOT_CHECKED"),
        lambda p: p["basis_check"].update(state="DIFFERENT", reasons=["REPLAY_BASIS_CHANGED"]),
        lambda p: p["comparisons"].pop(),
        lambda p: p["comparisons"][0].update(byte_equal=False),
        lambda p: p.update(state="MISMATCH"),
    ):
        changed = copy.deepcopy(source)
        mutate(changed["payload"])
        with pytest.raises(c.ContractError):
            c.BasicReplayResult.from_wire(changed)


def test_evidence_fixed_grid_nested_data_and_artifact_inventory():
    source = example(c.Kind.EVIDENCE_PROVENANCE)
    for mutate in (
        lambda p: p["observation_trace"].pop(),
        lambda p: p["observation_trace"][0].update(tick=1),
        lambda p: p["observation_trace"][0].update(snapshot_id="alias"),
        lambda p: p["source_summary"].update(admission_eligible=True),
        lambda p: p["source_summary"]["cutoffs"].reverse(),
        lambda p: p["artifacts"][0].update(name="../../secret"),
        lambda p: p["source_file_pins"].append(
            dict(path=".aws/credentials", byte_length="1", sha256="1" * 64)
        ),
        lambda p: p["observation_trace"][0]["current"].update(state="FUTURE_STATE"),
        lambda p: p["observation_trace"][0]["current"].update(state="WITHHELD"),
    ):
        changed = copy.deepcopy(source)
        mutate(changed["payload"])
        with pytest.raises(c.ContractError):
            c.EvidenceProvenanceView.from_wire(changed)


def test_authored_fixture_manifest_and_actual_not_run():
    raw = (FIXTURES / "projection_v0_1.json").read_bytes()
    manifest = json.loads((FIXTURES / "manifest_v0_1.json").read_bytes())
    assert manifest["sha256"] == hashlib.sha256(raw).hexdigest()
    assert manifest["byte_length"] == len(raw)
    assert manifest["execution_provenance"] == "FIXTURE_ONLY"
    assert manifest["actual_execution_status"] == "NOT_RUN"
    assert manifest["if03_issuance"] is False and manifest["formal_golden_acceptance"] is False
    for scenario in json.loads(raw)["scenarios"]:
        if "wire" in scenario:
            wire = c.parse_document(c.canonical_json(scenario["wire"])).to_wire()
            assert (
                wire["execution_status"] == "NOT_RUN"
                and wire["execution_provenance"] == "FIXTURE_ONLY"
            )
            assert wire["evidence_class"] == "UNVERIFIED"


def test_f6_import_root_and_static_isolation():
    assert Path(c.__file__).absolute() == ROOT / "src/pit_research_lab/mvp/f6/contracts.py"
    allowed = {
        "json",
        "re",
        "collections.abc",
        "dataclasses",
        "datetime",
        "enum",
        "hashlib",
        "math",
        "typing",
        "uuid",
    }
    for path in (ROOT / "src/pit_research_lab/mvp/f6").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name in allowed for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert (
                    node.level == 1
                    and node.module is None
                    and [a.name for a in node.names] == ["contracts"]
                ) or node.module in allowed
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"open", "exec", "eval", "__import__"}


# Independent literal vectors authored from the documented byte specification.
EXPECTED_CAPABILITY_BYTES = b'F6_FIXED_RESEARCH_CAPABILITY_V0.1\x00{"application_build_ref":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","capability_id":"fixed-synthetic-f3-l1-v0.1","cutoff_count":96,"dataset_digest":{"kind":"F2_PANEL_RESEARCH_BYTES","sha256":"8c2b03e3875e2029a3d9e0534588b76a5e470e944cea746fdd1fb7aba917927d"},"decision_frequency":"WEEKLY","folds":[{"history_end":48,"name":"F1","test_end":72,"test_start":48},{"history_end":72,"name":"F2","test_end":96,"test_start":72}],"h0":"beta = 0","h1":"beta != 0","horizon_sessions":20,"issuer_count":5,"manifest_bytes_sha256":"7b0cb1bec7b4d42ea55670eeb9d8ee4b744e7c39368cadd7e0eb1298deeb3219","method_id":"OLS_INTERCEPT_ONE_REGRESSOR_V1","native_protocol_schema":"F3_L1_RESEARCH_V0.1","native_provenance_basis":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","numeric_policy":"FRACTION_REDUCED_4096_DECIMAL50_FIXED12_HALF_EVEN_V1","protocol_ref":{"kind":"F3_PROTOCOL_PAYLOAD","sha256":"b5e30ec4033541cb9ec9ad542053430d495532b56298a99c418f6b945c95af66"},"question":"Does PIT monthly revenue growth predict subsequent synthetic returns?","replay_modes":["NATIVE_DIRECTORY_VERIFICATION","FRESH_PROCESS_NATIVE_RESEARCH_REPLAY"],"resource_policy_ref":{"reason":"NOT_YET_AVAILABLE","state":"UNAVAILABLE"},"schema_version":"F6_FIXED_SYNTHETIC_F3_L1_RESEARCH_V0.1","seed":17,"source_bytes_sha256":"8c2b03e3875e2029a3d9e0534588b76a5e470e944cea746fdd1fb7aba917927d"}'
EXPECTED_SUBMISSION_BYTES = b'F6_FIXED_RESEARCH_SUBMISSION_V0.1\x00{"capability_id":"fixed-synthetic-f3-l1-v0.1","capability_revision":"0000000000000000000000000000000000000000000000000000000000000000","data_mode":"SYNTHETIC_GOLDEN","kind":"SUBMISSION_REQUEST","schema_version":"F6_FIXED_SYNTHETIC_F3_L1_RESEARCH_V0.1"}'
EXPECTED_PROTOCOL_BYTES = b'{"exclusion_policy":"TYPED_UNAVAILABLE_NO_IMPUTATION_NO_OLDER_PAIR_FALLBACK","feature":"LATEST_AVAILABLE_MONTH_OVER_IMMEDIATE_PREDECESSOR_MINUS_ONE","folds":[{"history_end":48,"name":"F1","test_end":72,"test_start":48},{"history_end":72,"name":"F2","test_end":96,"test_start":72}],"h0":"beta = 0","h1":"beta != 0","horizon_sessions":20,"limitations":["AUTHORED_SYNTHETIC_INFRASTRUCTURE_ONLY","NOT_REAL_TWSE_OR_HISTORICAL_PIT_CERTIFICATION","NO_IF03_ISSUANCE_OR_IF05_ADMISSION","NO_IID_PVALUES_CI_OR_H0_REJECTION","REPEATED_MONTHLY_SIGNALS_AND_DEPENDENT_ENTITIES","OVERLAPPING_20_SESSION_OUTCOMES","DESCRIPTIVE_ASSOCIATION_AND_OOS_ASSESSMENT_ONLY","NO_CAUSAL_OR_PROFITABILITY_CLAIM"],"method":"OLS_INTERCEPT_ONE_REGRESSOR_V1","min_issuers":3,"min_test_cutoffs":20,"min_test_rows":80,"min_train_cutoffs":40,"min_train_rows":180,"non_if03":true,"numeric_policy":"FRACTION_REDUCED_4096_DECIMAL50_FIXED12_HALF_EVEN_V1","question":"Does PIT monthly revenue growth predict subsequent synthetic returns?","schema":"F3_L1_RESEARCH_V0.1","seed":17,"temporal_policy":{"feature":"public_delivery < decision","fit":"17:00_FIRST_TEST_SESSION","prediction":"18:00_LAST_SESSION_OF_WEEK","purge":"outcome_end < first_test_start_mark","score":"sealed_prediction_then_mature_outcome","target":"20_SUBSEQUENT_SESSION_CLOSES","training_label":"available_at <= fit","validation":"NOT_APPLICABLE_NO_TUNING"}}'


def test_exact_control_fingerprint_vectors_and_excluded_fields():
    capability = payload(c.Kind.CAPABILITY)
    assert c.capability_control_bytes(capability) == EXPECTED_CAPABILITY_BYTES
    assert (
        c.capability_revision(capability)
        == "92463e70be9a0a66762c7481ca3ffb70a1e39abe810df8dcc5c6417858e4caf9"
    )
    assert c.canonical_json(c.fixed_protocol()) == EXPECTED_PROTOCOL_BYTES
    assert c.PROTOCOL_SHA256 == "b5e30ec4033541cb9ec9ad542053430d495532b56298a99c418f6b945c95af66"
    request = payload(c.Kind.SUBMISSION_REQUEST)
    assert c.submission_control_bytes(request) == EXPECTED_SUBMISSION_BYTES
    assert (
        c.submission_fingerprint(request)
        == "997de81ef50bc5e0f9eed4058ac170b856d5bc467fb4131180b4f4c6896f6be0"
    )
    request["idempotency_key"] = REPLAY_ID
    assert c.submission_control_bytes(request) == EXPECTED_SUBMISSION_BYTES
    capability.update(
        capability_revision="f" * 64,
        submission_gate="JOB_BUSY",
        unavailable_reasons=["RESOURCE_LIMIT"],
    )
    assert c.capability_control_bytes(capability) == EXPECTED_CAPABILITY_BYTES
    capability["application_build_ref"] = "c" * 64
    assert (
        c.capability_revision(capability)
        != "92463e70be9a0a66762c7481ca3ffb70a1e39abe810df8dcc5c6417858e4caf9"
    )
    capability["invented"] = "extension"
    with pytest.raises(c.ContractError):
        c.capability_control_bytes(capability)


# REM01 examples are unauthenticated wire claims, never observed process evidence.
def rem01_failure(code="CHILD_NONZERO_EXIT"):
    return dict(
        code=code,
        native_code=c.unavailable(c.Reason.NOT_YET_AVAILABLE),
        first_observed_at=NOW,
        stage=c.unavailable(c.Reason.NOT_YET_AVAILABLE),
    )


def rem01_stages(count=11):
    return [
        dict(stage=stage, finished_at=NOW, elapsed_ns=str(i))
        for i, stage in enumerate(c.STAGES[:count])
    ]


def rem01_status(case):
    source = example(c.Kind.RUN_STATUS)
    data = source["payload"]
    if case in (
        "intent",
        "starting",
        "reconcile_pending",
        "blocked_policy",
        "fixture_intent",
        "fixture_withheld",
    ):
        source.update(execution_status="PENDING", execution_provenance="NOT_EXECUTED")
        data.update(
            phase="INTENT_RECORDED",
            started_at=c.unavailable(c.Reason.NOT_STARTED),
            finished_at=c.unavailable(c.Reason.NOT_YET_AVAILABLE),
            native_refs=refs(False),
            native_execution_status=c.unavailable(c.Reason.NOT_STARTED),
            completed_stages=[],
        )
    if case == "starting":
        data["phase"] = "STARTING"
    if case == "running":
        data.update(
            phase="NATIVE_RUNNING",
            native_refs=refs(False),
            native_execution_status=c.unavailable(c.Reason.NOT_YET_AVAILABLE),
            completed_stages=[],
        )
    if case == "running_partial":
        data.update(
            phase="NATIVE_RUNNING",
            native_refs=refs(False),
            native_execution_status=c.present("RUNNING"),
            completed_stages=rem01_stages(2),
        )
        data["native_refs"]["native_attempt_id"] = c.present(ATTEMPT_ID)
        data["native_refs"]["experiment_ref"] = refs()["experiment_ref"]
    if case in ("verifying", "reconcile_running"):
        data["completed_stages"] = rem01_stages()
    if case in ("reconcile_pending", "reconcile_running"):
        data["phase"] = "RECONCILING"
    if case == "failed":
        source["execution_status"] = "FAILED"
        data.update(
            phase="FAILED",
            finished_at=c.present(NOW),
            native_execution_status=c.present("FAILED"),
            first_failure=c.present(rem01_failure()),
        )
        data["release"].update(state="BLOCKED", reason="CHILD_NONZERO_EXIT")
    if case in ("blocked_policy", "fixture_withheld"):
        source.update(execution_status="BLOCKED", pit_status="WITHHELD")
        data["phase"] = "BLOCKED"
        data["release"].update(state="BLOCKED", reason="NATIVE_WITHHELD")
    if case == "blocked_recovery":
        source["execution_status"] = "BLOCKED"
        data.update(
            phase="BLOCKED",
            native_refs=refs(False),
            native_execution_status=c.unavailable(c.Reason.NOT_YET_AVAILABLE),
            first_failure=c.present(rem01_failure("EXECUTION_OUTCOME_UNKNOWN")),
        )
        data["release"].update(state="BLOCKED", reason="EXECUTION_OUTCOME_UNKNOWN")
    if case in ("complete", "invalidated"):
        source["execution_status"] = "SUCCEEDED"
        data.update(phase="COMPLETE", finished_at=c.present(NOW), completed_stages=rem01_stages())
        data["release"] = dict(
            state="AVAILABLE", reason="NO_FAILURE", verification=verification(True)
        )
        data.update(
            result_path=c.present(c.BASE_PATH + APP_ID + "/result"),
            evidence_path=c.present(c.BASE_PATH + APP_ID + "/evidence"),
        )
    if case == "invalidated":
        data["release"].update(state="BLOCKED", reason="ARTIFACT_INTEGRITY_FAILED")
        data["release"]["verification"].update(
            state="INVALIDATED", failure=c.present(rem01_failure("ARTIFACT_INTEGRITY_FAILED"))
        )
        data.update(
            result_path=c.unavailable(c.Reason.RESULT_NOT_RELEASED),
            evidence_path=c.unavailable(c.Reason.RESULT_NOT_RELEASED),
        )
    if case.startswith("fixture_"):
        source.update(execution_status="NOT_RUN", execution_provenance="FIXTURE_ONLY")
        source["limitations"].append(c.FIXTURE_LIMITATION)
    return source


def test_REM01_P201_A_intent_cannot_contain_native_success_refs_or_progress():
    value = rem01_status("intent")
    value["payload"].update(
        native_refs=refs(),
        native_execution_status=c.present("SUCCEEDED"),
        completed_stages=rem01_stages(),
    )
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(value)


def test_REM01_P201_B_fixture_cannot_embed_completed_actual_progress():
    value = rem01_status("invalidated")
    value.update(execution_status="NOT_RUN", execution_provenance="FIXTURE_ONLY")
    value["limitations"].append(c.FIXTURE_LIMITATION)
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(value)


def test_REM01_P202_failed_cannot_omit_first_failure():
    value = rem01_status("failed")
    value["payload"]["first_failure"] = c.unavailable(c.Reason.NO_FAILURE)
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(value)


@pytest.mark.parametrize(
    "case",
    [
        "intent",
        "starting",
        "running",
        "running_partial",
        "verifying",
        "failed",
        "reconcile_pending",
        "reconcile_running",
        "blocked_policy",
        "blocked_recovery",
        "complete",
        "invalidated",
        "fixture_intent",
        "fixture_withheld",
    ],
)
def test_REM01_truthful_lifecycle_claims_accept(case):
    source = rem01_status(case)
    assert c.RunStatusResponse.from_wire(source).to_wire() == source


@pytest.mark.parametrize("case", ["intent", "starting"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("started_at", c.present(NOW)),
        ("finished_at", c.present(NOW)),
        ("native_execution_status", c.present("SUCCEEDED")),
        ("completed_stages", rem01_stages(1)),
        ("native_refs", refs()),
    ],
)
def test_REM01_prelaunch_fabricated_native_state_refuses(case, field, value):
    source = rem01_status(case)
    source["payload"][field] = value
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)


@pytest.mark.parametrize("case", ["intent", "starting", "blocked_policy", "fixture_withheld"])
@pytest.mark.parametrize("field", ["native_attempt_id", *c.REF_FIELDS])
def test_REM01_prelaunch_each_native_reference_refuses(case, field):
    source = rem01_status(case)
    source["payload"]["native_refs"][field] = refs()[field]
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)


@pytest.mark.parametrize(
    "case", ["running", "verifying", "failed", "complete", "invalidated", "blocked_recovery"]
)
def test_REM01_observed_launch_is_required(case):
    for provenance in ("NOT_EXECUTED", "FIXTURE_ONLY"):
        source = rem01_status(case)
        source["execution_provenance"] = provenance
        if provenance == "FIXTURE_ONLY":
            source["execution_status"] = "NOT_RUN"
            source["limitations"].append(c.FIXTURE_LIMITATION)
        with pytest.raises(c.ContractError):
            c.RunStatusResponse.from_wire(source)
    source = rem01_status(case)
    source["payload"]["started_at"] = c.unavailable(c.Reason.NOT_STARTED)
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)


@pytest.mark.parametrize(
    "case",
    [
        "running",
        "verifying",
        "reconcile_pending",
        "reconcile_running",
        "failed",
        "blocked_recovery",
    ],
)
def test_REM01_noncomplete_cannot_release_even_with_structural_verification(case):
    source = rem01_status(case)
    source["payload"].update(
        release=copy.deepcopy(rem01_status("complete")["payload"]["release"]),
        result_path=c.present(c.BASE_PATH + APP_ID + "/result"),
        evidence_path=c.present(c.BASE_PATH + APP_ID + "/evidence"),
    )
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)


@pytest.mark.parametrize("case", ["running", "verifying"])
def test_REM01_unfinalized_active_phase_cannot_invent_finish(case):
    source = rem01_status(case)
    source["payload"]["finished_at"] = c.present(NOW)
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)


def test_REM01_early_native_success_does_not_promote_or_require_complete_polling_data():
    for case in ("running", "verifying"):
        source = rem01_status(case)
        source["payload"].update(
            native_refs=refs(False),
            completed_stages=[],
            native_execution_status=c.present("SUCCEEDED"),
        )
        assert c.RunStatusResponse.from_wire(source).to_wire()["execution_status"] == "RUNNING"


def test_REM01_pending_reconciliation_may_retain_input_pins_but_not_native_execution_artifacts():
    source = rem01_status("reconcile_pending")
    for field in ("protocol_ref", "dataset_digest"):
        source["payload"]["native_refs"][field] = refs()[field]
    c.RunStatusResponse.from_wire(source)
    for field in ("native_attempt_id", "experiment_ref", "result_ref", "evidence_ref"):
        changed = copy.deepcopy(source)
        changed["payload"]["native_refs"][field] = refs()[field]
        with pytest.raises(c.ContractError):
            c.RunStatusResponse.from_wire(changed)
    source["execution_status"] = "RUNNING"
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)


def test_REM01_launched_reconciliation_preserves_partial_unknown_native_state():
    source = rem01_status("reconcile_running")
    source["payload"].update(
        native_refs=refs(False),
        native_execution_status=c.unavailable(c.Reason.NOT_YET_AVAILABLE),
        completed_stages=rem01_stages(2),
    )
    source["payload"]["native_refs"]["experiment_ref"] = refs()["experiment_ref"]
    source["payload"]["first_failure"] = c.present(rem01_failure("SUPERVISOR_LOST"))
    original = copy.deepcopy(source)
    assert c.RunStatusResponse.from_wire(source).to_wire() == original
    source["payload"]["finished_at"] = c.present(NOW)
    c.RunStatusResponse.from_wire(source)
    source["execution_status"] = "PENDING"
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)


@pytest.mark.parametrize("reason", list(c.Reason))
def test_REM01_any_unavailable_first_failure_refuses_for_failed(reason):
    source = rem01_status("failed")
    source["payload"]["first_failure"] = c.unavailable(reason)
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)


def test_REM01_present_no_failure_is_not_a_failure_and_terminal_finish_is_required():
    source = rem01_status("failed")
    source["payload"]["first_failure"] = c.present(rem01_failure("NO_FAILURE"))
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)
    source = rem01_status("failed")
    source["payload"]["finished_at"] = c.unavailable(c.Reason.NOT_YET_AVAILABLE)
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)


@pytest.mark.parametrize("case", ["reconcile_running", "blocked_recovery", "verifying"])
def test_REM01_known_failure_cannot_be_disguised_as_no_failure(case):
    source = rem01_status(case)
    source["payload"]["native_execution_status"] = c.present("FAILED")
    source["payload"]["first_failure"] = c.unavailable(c.Reason.NO_FAILURE)
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)
    source["payload"]["first_failure"] = c.present(rem01_failure())
    c.RunStatusResponse.from_wire(source)


def test_REM01_blocked_prelaunch_gate_vs_known_app_failure_and_unknown_orphan():
    source = rem01_status("blocked_policy")
    c.RunStatusResponse.from_wire(source)
    source["payload"]["release"]["reason"] = "LAUNCH_INTERRUPTED"
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)
    source["payload"]["first_failure"] = c.present(rem01_failure("LAUNCH_INTERRUPTED"))
    c.RunStatusResponse.from_wire(source)
    orphan = rem01_status("blocked_recovery")
    orphan["payload"]["first_failure"] = c.unavailable(c.Reason.NO_FAILURE)
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(orphan)


@pytest.mark.parametrize("case", ["intent", "starting", "fixture_intent", "fixture_withheld"])
def test_REM01_prelaunch_cannot_claim_artifact_verification(case):
    source = rem01_status(case)
    source["payload"]["release"]["verification"] = verification(True)
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)


@pytest.mark.parametrize("case", ["running", "verifying", "reconcile_running"])
def test_REM01_passed_directory_claim_needs_complete_native_metadata(case):
    source = rem01_status(case)
    source["payload"].update(native_refs=refs(False), completed_stages=[])
    source["payload"]["release"]["verification"] = verification(True)
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)


def test_REM01_status_timestamps_are_chronological_without_conflating_native_cutoffs():
    for field, value in (
        ("started_at", "2026-11-19T23:59:59+00:00"),
        ("finished_at", "2026-11-19T23:59:59+00:00"),
        ("finished_at", "2026-11-21T00:00:00+00:00"),
    ):
        source = rem01_status("failed")
        source["payload"][field] = c.present(value)
        with pytest.raises(c.ContractError):
            c.RunStatusResponse.from_wire(source)
    source = rem01_status("intent")
    source["payload"]["updated_at"] = "2026-11-19T23:59:59+00:00"
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)
    source = rem01_status("reconcile_running")
    source["payload"].update(
        started_at=c.present("2026-11-20T00:00:00.1+00:00"), updated_at="2026-11-20T00:00:01+00:00"
    )
    c.RunStatusResponse.from_wire(source)


def test_REM01_complete_retains_no_first_failure_after_release_invalidation():
    source = rem01_status("invalidated")
    result = c.RunStatusResponse.from_wire(source).to_wire()
    assert result["execution_status"] == "SUCCEEDED"
    assert result["payload"]["first_failure"] == c.unavailable(c.Reason.NO_FAILURE)
    assert result["payload"]["release"]["verification"]["failure"]["state"] == "PRESENT"
    source["payload"]["first_failure"] = c.present(rem01_failure("ARTIFACT_INTEGRITY_FAILED"))
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(source)


def test_REM01_fixture_simulation_belongs_in_external_wrapper():
    fixture = rem01_status("fixture_withheld")
    wrapper = dict(scenario_execution_status="SUCCEEDED", wire=fixture)
    assert c.RunStatusResponse.from_wire(wrapper["wire"]).to_wire()["execution_status"] == "NOT_RUN"
    fixture["scenario_execution_status"] = "SUCCEEDED"
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(fixture)


def test_REM01_continuity_preserves_first_failure_and_known_reconciliation_facts():
    previous = rem01_status("running_partial")
    previous["payload"]["first_failure"] = c.present(rem01_failure("SUPERVISOR_LOST"))
    current = copy.deepcopy(previous)
    current["payload"]["phase"] = "RECONCILING"
    before = c.RunStatusResponse.from_wire(previous)
    c.validate_status_continuity(before, c.RunStatusResponse.from_wire(current))
    mutations = [
        lambda v: v["payload"].update(
            native_execution_status=c.unavailable(c.Reason.NOT_YET_AVAILABLE)
        ),
        lambda v: v["payload"].update(first_failure=c.unavailable(c.Reason.NO_FAILURE)),
        lambda v: v["payload"].update(first_failure=c.present(rem01_failure("INTERNAL_ERROR"))),
        lambda v: v["payload"]["native_refs"].update(
            experiment_ref=c.unavailable(c.Reason.NOT_YET_AVAILABLE)
        ),
        lambda v: v["payload"].update(completed_stages=[]),
    ]
    for mutate in mutations:
        changed = copy.deepcopy(current)
        mutate(changed)
        with pytest.raises(c.ContractError):
            c.validate_status_continuity(before, c.RunStatusResponse.from_wire(changed))


def test_REM01_continuity_preserves_historical_complete_and_its_times_and_refs():
    before = c.RunStatusResponse.from_wire(rem01_status("complete"))
    after = c.RunStatusResponse.from_wire(rem01_status("invalidated"))
    c.validate_status_continuity(before, after)
    changed = rem01_status("failed")
    with pytest.raises(c.ContractError):
        c.validate_status_continuity(before, c.RunStatusResponse.from_wire(changed))


@pytest.mark.parametrize("code", ["CHILD_NONZERO_EXIT", "CHILD_TIMEOUT"])
def test_REM01_unlaunched_block_cannot_claim_child_execution_failure(code):
    value = rem01_status("blocked_policy")
    value["payload"]["first_failure"] = c.present(rem01_failure(code))
    with pytest.raises(c.ContractError):
        c.RunStatusResponse.from_wire(value)


@pytest.mark.parametrize(
    "case,allowed",
    [
        ("intent", [("PENDING", "NOT_EXECUTED"), ("NOT_RUN", "FIXTURE_ONLY")]),
        ("starting", [("PENDING", "NOT_EXECUTED"), ("NOT_RUN", "FIXTURE_ONLY")]),
        ("running", [("RUNNING", "ACTUAL_F3_CLI")]),
        ("verifying", [("RUNNING", "ACTUAL_F3_CLI")]),
        ("reconcile_pending", [("PENDING", "NOT_EXECUTED")]),
        ("reconcile_running", [("RUNNING", "ACTUAL_F3_CLI")]),
        ("failed", [("FAILED", "ACTUAL_F3_CLI")]),
        ("blocked_policy", [("BLOCKED", "NOT_EXECUTED"), ("NOT_RUN", "FIXTURE_ONLY")]),
        ("blocked_recovery", [("BLOCKED", "ACTUAL_F3_CLI")]),
        ("complete", [("SUCCEEDED", "ACTUAL_F3_CLI")]),
        ("invalidated", [("SUCCEEDED", "ACTUAL_F3_CLI")]),
    ],
)
@pytest.mark.parametrize("execution", list(c.Execution))
@pytest.mark.parametrize("provenance", list(c.Provenance))
def test_REM01_closed_phase_execution_provenance_product(case, allowed, execution, provenance):
    value = rem01_status(case)
    value.update(execution_status=execution.value, execution_provenance=provenance.value)
    if provenance == c.Provenance.FIXTURE_ONLY:
        value["limitations"].append(c.FIXTURE_LIMITATION)
    if (execution.value, provenance.value) in allowed:
        c.RunStatusResponse.from_wire(value)
    else:
        with pytest.raises(c.ContractError):
            c.RunStatusResponse.from_wire(value)
