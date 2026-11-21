"""Authored detached inputs only: no F3 execution, verifier, backend or browser."""

import ast
import copy
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from pit_research_lab.mvp.f6 import contracts as c
from pit_research_lab.mvp.f6 import projection as p

ROOT = Path(__file__).absolute().parents[3]


def native_fact(state="KNOWN"):
    return dict(
        month="2024-01",
        state=state,
        amount=100 if state == "KNOWN" else None,
        source_ref="SYN-L1-1-REV-2024-01",
        publication="2024-02-10T12:00:00+08:00",
        available_at="2024-02-10T12:01:00+08:00",
        unit="NTD_thousands",
        basis="consolidated-v1",
        native_state="SELECTED",
        reason="NONE" if state == "KNOWN" else state,
        qualification_ref="a" * 64,
        version_ref="SYN-L1-1-REV-2024-01-VERSION",
    )


def native_metrics():
    return dict(
        n=80,
        exact={name: dict(numerator="0", denominator="1") for name in c.METRIC_NAMES},
        display={
            **{name: "0.000000000000" for name in c.METRIC_NAMES},
            "rmse": "0.000000000000",
            "oos_improvement": None,
        },
        oos_improvement=dict(state="NOT_COMPUTABLE", reason="ZERO_BASELINE_SSE"),
        units=c.UNITS,
        iid_inference="NOT_PERFORMED",
        adjacent_residual_pairs=0,
        diagnostic_interpretation=c.DIAGNOSTIC,
    )


def native_receipt():
    return dict(
        schema="F2_L1_QUALIFICATION_RECEIPT_V1",
        non_if03=True,
        dataset_digest=c.DATASET_SHA256,
        cutoff="2024-03-08T18:00:00+08:00",
        subject="AUTHORED-RECEIPT",
        state="SELECTED",
        reason="NONE",
        native_invocation="RUN",
        selected_sources=[
            dict(assertion="AUTHORED-ASSERTION", source_sha256="a" * 64, s1="BOUND", s2="SUPPORTED")
        ],
        code_pins=[dict(path="src/pit_research_lab/domain/pit_slice.py", sha256="b" * 64)],
        revenue_value=dict(
            source_sha256="c" * 64, s1="BOUND", s2="SUPPORTED", native_invocation="RUN", value=100
        ),
    )


def native_fold():
    training_ids = [
        f"{issuer}:t{tick:02}"
        for tick in range(40)
        for issuer in c.ISSUERS[: 5 if tick < 20 else 4]
    ]
    scored_ids = [f"{issuer}:t{tick:02}" for tick in range(48, 68) for issuer in c.ISSUERS[:4]]
    state = dict(
        training_ref="a" * 64,
        fold="F1",
        fit_cutoff="2025-02-07T17:00:00+08:00",
        dataset_digest=c.DATASET_SHA256,
        protocol_ref=c.PROTOCOL_SHA256,
        training_ids=training_ids,
        **{k: dict(numerator="0", denominator="1") for k in ("alpha", "beta", "gbar", "rbar")},
    )
    state["state_id"] = hashlib.sha256(c.canonical_json(state)).hexdigest()
    fold = dict(
        fold="F1",
        history_candidates=[0, 47],
        test_ticks=[48, 71],
        fit_cutoff=state["fit_cutoff"],
        training_ids=training_ids,
        training_count=180,
        training_cutoffs=40,
        training_issuers=5,
        distinct_issuer_month_releases=10,
        distinct_source_versions=20,
        latest_training_label_availability="2025-01-01T18:00:00+08:00",
        scored_cutoffs=20,
        excluded_training=[],
        exclusion_counts={},
        state_id=state["state_id"],
        scoring_cutoff="2026-02-28T23:59:59+08:00",
        prediction_id="d" * 64,
        scored_ids=scored_ids,
        excluded=[],
        metrics=native_metrics(),
    )
    return fold, state


@pytest.mark.parametrize(
    "states",
    [
        ["SUPPORTED"],
        ["SELECTED"],
        ["KNOWN"],
        ["NO_QUALIFIED_CLAIM"],
        ["NOT_ADMISSIBLE"],
        ["SUCCEEDED"],
        ["FAILED"],
        [],
    ],
)
def test_axes_never_promote_native_claims(states):
    axes = p.project_axes(states)
    assert isinstance(axes, p.ConservativeAxes)
    wire = axes.to_wire()
    assert wire == dict(
        pit_status="UNRESOLVED",
        execution_status="NOT_RUN",
        execution_provenance="NOT_EXECUTED",
        evidence_class="UNVERIFIED",
        data_mode="SYNTHETIC_GOLDEN",
        verification_state="NOT_CHECKED",
        release_state="UNAVAILABLE",
    )


def test_unknown_refuses_and_withheld_has_precedence():
    refused = p.project_axes(["FUTURE_VARIANT"])
    assert isinstance(refused, p.ProjectionRefusal)
    assert refused.code is c.Reason.NATIVE_UNKNOWN_STATE
    assert refused.to_wire()["native_state"] == c.present("FUTURE_VARIANT")
    for states in (["WITHHELD"], ["FUTURE_VARIANT", "WITHHELD"], ["WITHHELD", "SUCCEEDED"]):
        axes = p.project_axes(states, fixture=True)
        assert isinstance(axes, p.ConservativeAxes)
        assert axes.to_wire()["pit_status"] == "WITHHELD"
        assert axes.to_wire()["execution_status"] == "NOT_RUN"
        assert axes.to_wire()["execution_provenance"] == "FIXTURE_ONLY"
    assert isinstance(p.project_axes(["<script>"]), p.ProjectionRefusal)
    with pytest.raises(c.ContractError):
        p.ConservativeAxes(c.Pit.UNRESOLVED, c.Execution.SUCCEEDED, c.Provenance.ACTUAL_F3_CLI)


def test_static_capability_never_declares_runtime_readiness():
    basis = dict(
        application_build_ref="a" * 64,
        native_provenance_basis="b" * 64,
        resource_policy_ref=c.unavailable(c.Reason.NOT_YET_AVAILABLE),
    )
    for policy in (c.unavailable(c.Reason.NOT_YET_AVAILABLE), c.present("c" * 64)):
        basis["resource_policy_ref"] = policy
        projected = p.project_unavailable_capability(basis)
        assert isinstance(projected, c.CapabilityDescriptor)
        wire = projected.to_wire()
        assert wire["execution_status"] == "NOT_RUN"
        assert wire["payload"]["readiness"] == "UNAVAILABLE"
        assert wire["payload"]["submission_gate"] != "OPEN"
        assert wire["payload"]["capability_revision"] == c.capability_revision(wire["payload"])
        assert wire["payload"]["folds"] == c.fixed_folds()
        assert wire["limitations"][:8] == list(c.NATIVE_LIMITATIONS)
    assert isinstance(p.project_unavailable_capability({}), p.ProjectionRefusal)
    basis["runtime_verified"] = True
    assert isinstance(p.project_unavailable_capability(basis), p.ProjectionRefusal)


def test_metrics_preserve_exact_fraction_and_native_display_without_recomputation():
    source = native_metrics()
    source["exact"]["sse"] = dict(numerator="9007199254740993", denominator="9007199254740992")
    # A native display is copied, not recalculated from authoritative fractions.
    source["display"]["sse"] = "1.000000000000"
    source["oos_improvement"] = dict(numerator="-2", denominator="3")
    source["display"]["oos_improvement"] = "-0.666666666667"
    original = copy.deepcopy(source)
    projected = p.project_metrics(source)
    assert isinstance(projected, c.MetricsValue)
    result = projected.to_wire()
    assert result["exact"]["sse"] == source["exact"]["sse"]
    assert result["display"]["sse"] == source["display"]["sse"]
    assert result["display"]["oos_improvement"] == c.present("-0.666666666667")
    assert result["units"] == c.UNITS
    assert source == original
    source["exact"]["sse"]["numerator"] = "1"
    assert projected.to_wire() == result


def test_zero_baseline_and_optional_adjacent_metric_are_typed():
    projected = p.project_metrics(native_metrics())
    assert isinstance(projected, c.MetricsValue)
    wire = projected.to_wire()
    assert wire["oos_improvement"] == dict(state="NOT_COMPUTABLE", reason="ZERO_BASELINE_SSE")
    assert wire["display"]["oos_improvement"] == c.unavailable(c.Reason.ZERO_BASELINE_SSE)
    assert wire["exact"][c.ADJACENT_METRIC] == c.unavailable(c.Reason.NO_ADJACENT_PAIRS)
    source = native_metrics()
    source["adjacent_residual_pairs"] = 2
    source["exact"][c.ADJACENT_METRIC] = dict(numerator="-1", denominator="3")
    source["display"][c.ADJACENT_METRIC] = "-0.333333333333"
    result = p.project_metrics(source)
    assert isinstance(result, c.MetricsValue)
    assert result.to_wire()["exact"][c.ADJACENT_METRIC] == c.present(
        dict(numerator="-1", denominator="3")
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda obj: obj.update(unreviewed_metric=0),
        lambda obj: obj["exact"].update(unsupported=dict(numerator="1", denominator="1")),
        lambda obj: obj["display"].update(pvalue="0.000000000001"),
        lambda obj: obj.update(n=True),
        lambda obj: obj.update(oos_improvement=dict(state="UNKNOWN", reason="UNSUPPORTED")),
        lambda obj: obj["display"].update(oos_improvement="0.000000000000"),
    ],
)
def test_unknown_metric_variants_refuse_without_partial_payload(change):
    source = native_metrics()
    change(source)
    result = p.project_metrics(source)
    assert isinstance(result, p.ProjectionRefusal)
    assert "metrics" not in result.to_wire() and "value" not in result.to_wire()


def test_fact_mapping_preserves_typed_native_provenance_and_omits_amount():
    source = native_fact()
    result = p.project_fact(source)
    assert isinstance(result, c.FactTraceValue)
    wire = result.to_wire()
    assert wire["state"] == "KNOWN" and wire["native_state"] == "SELECTED"
    assert wire["source_ref"] == c.present(source["source_ref"])
    assert wire["qualification_ref"] == c.present("a" * 64)
    assert wire["publication"] == c.present(source["publication"])
    assert "amount" not in wire
    source["source_ref"] = None
    result = p.project_fact(source)
    assert isinstance(result, p.ProjectionRefusal)
    assert result.code is c.Reason.SOURCE_REFERENCE_MISSING


def test_withheld_unknown_and_missing_fact_do_not_disclose_or_fill_values():
    result = p.project_fact(native_fact("WITHHELD"))
    assert isinstance(result, p.ProjectionRefusal)
    assert result.pit_status is c.Pit.WITHHELD
    assert result.native_reason == "WITHHELD"
    assert not {"amount", "source_ref", "value"}.intersection(result.to_wire())
    assert isinstance(p.project_fact(native_fact("FUTURE_VARIANT")), p.ProjectionRefusal)
    source = native_fact("ABSENT")
    source.update(native_state="NO_QUALIFIED_CLAIM", reason="MISSING_PREDECESSOR")
    for name in ("source_ref", "version_ref", "qualification_ref", "publication", "available_at"):
        source[name] = None
    result = p.project_fact(source)
    assert isinstance(result, c.FactTraceValue)
    assert result.to_wire()["source_ref"] == c.unavailable(c.Reason.MISSING_PREDECESSOR)
    source["future_raw_graph"] = {}
    assert isinstance(p.project_fact(source), p.ProjectionRefusal)


def test_observation_binding_is_distinct_and_payload_pin_mismatch_refuses():
    source = dict(
        sample_id="SYN-L1-1:t00",
        issuer="SYN-L1-1",
        tick=0,
        cutoff="2024-03-08T18:00:00+08:00",
        dataset_digest=c.DATASET_SHA256,
        calendar_id="SYN-L1-CALENDAR-V1",
        current=native_fact(),
        previous=native_fact(),
    )
    source["binding_id"] = hashlib.sha256(c.canonical_json(source)).hexdigest()
    result = p.project_observation(source)
    assert isinstance(result, c.ObservationTraceValue)
    assert result.to_wire()["binding_id"] == dict(
        kind="F3_BINDING_PAYLOAD", sha256=source["binding_id"]
    )
    assert "snapshot_id" not in result.to_wire()
    source["binding_id"] = "0" * 64
    assert isinstance(p.project_observation(source), p.ProjectionRefusal)
    source["snapshot_id"] = "alias"
    assert isinstance(p.project_observation(source), p.ProjectionRefusal)


def test_safe_receipt_hash_check_and_value_omission():
    source = native_receipt()
    pin = hashlib.sha256(c.canonical_json(source)).hexdigest()
    result = p.project_receipt(source, pin)
    assert isinstance(result, c.SafeReceiptValue)
    wire = result.to_wire()
    assert wire["qualification_ref"] == pin
    assert wire["revenue_value_qualification"]["state"] == "PRESENT"
    assert "value" not in wire["revenue_value_qualification"]["value"]
    assert "revenue_value" not in wire
    source["revenue_value"]["value"] = 999
    refused = p.project_receipt(source, pin)
    assert isinstance(refused, p.ProjectionRefusal)
    assert refused.code is c.Reason.ARTIFACT_INTEGRITY_FAILED
    source["private_audit"] = "forbidden"
    assert isinstance(
        p.project_receipt(source, hashlib.sha256(c.canonical_json(source)).hexdigest()),
        p.ProjectionRefusal,
    )


def test_source_summary_preserves_sequence_and_native_scope():
    source = dict(
        dataset_digest=c.DATASET_SHA256,
        calendar_id="SYN-L1-CALENDAR-V1",
        issuer_roster=list(c.ISSUERS),
        cutoffs=[
            (date(2024, 3, 8) + timedelta(weeks=i)).isoformat() + "T18:00:00+08:00"
            for i in range(96)
        ],
        calendar_coverage=["2024-01-01", "2026-02-28"],
        revenue_declarations=131,
        price_marks=10,
        scope="AUTHORED_SYNTHETIC_PUBLIC_ONLY",
        non_if03=True,
        admission_eligible=False,
        source_authentication="NOT_ESTABLISHED",
        native_invocations=0,
        invocation_count_scope="TOP_LEVEL_ASOF_AND_EXPLICIT_S1_S2_CALLS_EXCLUDES_TRANSITIVE_REPLAY",
    )
    result = p.project_source_summary(source)
    assert isinstance(result, c.SourceSummaryValue)
    assert len(result.to_wire()["cutoffs"]) == 96
    assert result.to_wire()["admission_eligible"] is False
    source["admission_eligible"] = True
    assert isinstance(p.project_source_summary(source), p.ProjectionRefusal)


def test_fold_projection_joins_native_ids_and_preserves_coefficients():
    fold, state = native_fold()
    original = copy.deepcopy((fold, state))
    result = p.project_fold(fold, state)
    assert isinstance(result, c.FoldResultValue)
    wire = result.to_wire()
    assert wire["state_id"] == dict(kind="F3_STATE_PAYLOAD", sha256=state["state_id"])
    assert wire["alpha"] == state["alpha"]
    assert wire["scored_count"] == len(fold["scored_ids"]) == 80
    assert wire["metrics"]["n"] == 80
    assert (fold, state) == original
    state["state_id"] = "0" * 64
    assert isinstance(p.project_fold(fold, state), p.ProjectionRefusal)
    fold, state = native_fold()
    state["undeclared_outcome"] = 1
    assert isinstance(p.project_fold(fold, state), p.ProjectionRefusal)


def test_source_transcription_matches_static_native_definitions_without_import():
    source = ROOT / "src/pit_research_lab/mvp/f3_l1/contracts.py"
    tree = ast.parse(source.read_text())
    constants = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"VERSION", "NUMERIC", "LIMITATIONS"}
    }
    assert constants["VERSION"] == c.NATIVE_VERSION
    assert constants["NUMERIC"] == c.NUMERIC_POLICY
    assert constants["LIMITATIONS"] == c.NATIVE_LIMITATIONS
    protocol = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Protocol"
    )
    fields = {
        node.target.id: ast.literal_eval(node.value)
        for node in protocol.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id
        in {
            "seed",
            "horizon_sessions",
            "min_train_cutoffs",
            "min_train_rows",
            "min_issuers",
            "min_test_cutoffs",
            "min_test_rows",
        }
    }
    assert all(c.fixed_protocol()[key] == value for key, value in fields.items())
    panel = ROOT / "tests/fixtures/mvp_f3_l1/revenue_growth_panel_v0_1.json"
    assert hashlib.sha256(panel.read_bytes()).hexdigest() == c.SOURCE_SHA256
    data = json.loads(panel.read_bytes())
    assert hashlib.sha256(c.canonical_json(data)).hexdigest() == c.DATASET_SHA256


def test_projection_module_selected_from_f6_worktree_and_has_no_success_factory():
    assert Path(p.__file__).absolute() == ROOT / "src/pit_research_lab/mvp/f6/projection.py"
    tree = ast.parse(Path(p.__file__).read_text())
    exports = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    assert not exports.intersection(
        {"verify_directory", "run_to_directory", "release", "make_available", "assume_verified"}
    )
