"""Pure projections of supplied native claims; no verifier or release constructor.

Native fields are explicitly selected after closed-shape validation. Local
payload hashes below check transcription consistency only, never qualification,
execution, artifact verification, source authenticity or IF-03 equivalence.
"""

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import cast

from . import contracts as c


@dataclass(frozen=True, slots=True)
class ProjectionRefusal:
    code: c.Reason
    pit_status: c.Pit = c.Pit.UNRESOLVED
    native_state: str | None = None
    native_reason: str | None = None

    def __post_init__(self) -> None:
        c.require(type(self.code) is c.Reason and type(self.pit_status) is c.Pit)
        for value in (self.native_state, self.native_reason):
            if value is not None:
                c.require(
                    type(value) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,159}", value) is not None
                )

    def to_wire(self) -> c.WireObject:
        return {
            "state": "REFUSED",
            "code": self.code.value,
            "pit_status": self.pit_status.value,
            "native_state": c.present(self.native_state)
            if self.native_state is not None
            else c.unavailable(c.Reason.NOT_YET_AVAILABLE),
            "native_reason": c.present(self.native_reason)
            if self.native_reason is not None
            else c.unavailable(c.Reason.NOT_YET_AVAILABLE),
        }


@dataclass(frozen=True, slots=True)
class ConservativeAxes:
    """Presentation summary only; this type never asserts real execution."""

    pit_status: c.Pit
    execution_status: c.Execution
    execution_provenance: c.Provenance

    def __post_init__(self) -> None:
        c.require(type(self.pit_status) is c.Pit)
        c.require(type(self.execution_provenance) is c.Provenance)
        c.require(self.execution_status is c.Execution.NOT_RUN)
        c.require(
            self.execution_provenance in (c.Provenance.NOT_EXECUTED, c.Provenance.FIXTURE_ONLY)
        )

    def to_wire(self) -> c.WireObject:
        return {
            "pit_status": self.pit_status.value,
            "execution_status": self.execution_status.value,
            "execution_provenance": self.execution_provenance.value,
            "evidence_class": "UNVERIFIED",
            "data_mode": "SYNTHETIC_GOLDEN",
            "verification_state": "NOT_CHECKED",
            "release_state": "UNAVAILABLE",
        }


def project_axes(
    native_states: object, *, fixture: bool = False
) -> ConservativeAxes | ProjectionRefusal:
    c.require(type(fixture) is bool)
    c.require(type(native_states) is list)
    states = cast(list[object], native_states)
    c.require(all(type(state) is str for state in states))
    if "WITHHELD" in states:
        return ConservativeAxes(
            c.Pit.WITHHELD,
            c.Execution.NOT_RUN,
            c.Provenance.FIXTURE_ONLY if fixture else c.Provenance.NOT_EXECUTED,
        )
    known = {
        *tuple(c.FactState),
        *c.SELECTION_STATES,
        "SUPPORTED",
        "NOT_ADMISSIBLE",
        "SUCCEEDED",
        "FAILED",
        "RUNNING",
        "NOT_TRUSTED_PIT_EVIDENCE",
    }
    for state in states:
        if state not in known:
            name = c.text(state)
            if re.fullmatch(r"[A-Z][A-Z0-9_]{0,159}", name) is None:
                return ProjectionRefusal(c.Reason.NATIVE_CONTRACT_INVALID)
            return ProjectionRefusal(c.Reason.NATIVE_UNKNOWN_STATE, native_state=name)
    return ConservativeAxes(
        c.Pit.UNRESOLVED,
        c.Execution.NOT_RUN,
        c.Provenance.FIXTURE_ONLY if fixture else c.Provenance.NOT_EXECUTED,
    )


def project_unavailable_capability(basis: object) -> c.CapabilityDescriptor | ProjectionRefusal:
    """Only unavailable discovery can be constructed without runtime authority.

    Missing build/provenance identities refuse; resource policy may explicitly be
    unavailable. Caller-supplied policy text never establishes runtime readiness.
    """
    try:
        obj = c.record(
            c.decode_json(c.canonical_json(basis)),
            "application_build_ref native_provenance_basis resource_policy_ref",
        )
        build = c.sha256_text(obj["application_build_ref"])
        provenance = c.sha256_text(obj["native_provenance_basis"])
        payload: c.WireObject = {
            "capability_id": c.CAPABILITY_ID,
            "capability_revision": "0" * 64,
            "readiness": "UNAVAILABLE",
            "unavailable_reasons": [c.Reason.SERVICE_NOT_READY.value],
            "submission_gate": "RECOVERY_BLOCKED",
            "question": c.QUESTION,
            "h0": "beta = 0",
            "h1": "beta != 0",
            "method_id": c.METHOD,
            "native_protocol_schema": c.NATIVE_VERSION,
            "protocol_ref": c.NativeDigestRef(
                c.ReferenceKind.PROTOCOL, c.PROTOCOL_SHA256
            ).to_wire(),
            "source_bytes_sha256": c.SOURCE_SHA256,
            "manifest_bytes_sha256": c.MANIFEST_SHA256,
            "dataset_digest": c.NativeDigestRef(
                c.ReferenceKind.DATASET, c.DATASET_SHA256
            ).to_wire(),
            "decision_frequency": "WEEKLY",
            "cutoff_count": 96,
            "issuer_count": 5,
            "horizon_sessions": 20,
            "seed": 17,
            "folds": c.fixed_folds(),
            "numeric_policy": c.NUMERIC_POLICY,
            "application_build_ref": build,
            "native_provenance_basis": provenance,
            "resource_policy_ref": obj["resource_policy_ref"],
            "replay_modes": [
                "NATIVE_DIRECTORY_VERIFICATION",
                "FRESH_PROCESS_NATIVE_RESEARCH_REPLAY",
            ],
        }
        payload["capability_revision"] = c.capability_revision(payload)
        return c.CapabilityDescriptor.from_wire(
            {
                "schema_version": c.VERSION,
                "kind": c.Kind.CAPABILITY.value,
                "non_if03": True,
                "data_mode": "SYNTHETIC_GOLDEN",
                "pit_status": "UNRESOLVED",
                "execution_status": "NOT_RUN",
                "evidence_class": "UNVERIFIED",
                "execution_provenance": "NOT_EXECUTED",
                "source_refs": [],
                "limitations": [*c.NATIVE_LIMITATIONS, *c.APP_LIMITATIONS],
                "payload": payload,
            }
        )
    except c.ContractError as error:
        return ProjectionRefusal(error.code)


def project_metrics(native: object) -> c.MetricsValue | ProjectionRefusal:
    try:
        obj = c.record(
            c.decode_json(c.canonical_json(native)),
            "n exact display oos_improvement units iid_inference adjacent_residual_pairs "
            "diagnostic_interpretation",
        )
        c.require(type(obj["exact"]) is dict and type(obj["display"]) is dict)
        exact = cast(c.WireObject, obj["exact"])
        display = cast(c.WireObject, obj["display"])
        has_adjacent = c.uint(obj["adjacent_residual_pairs"]) > 0
        metric_names = (*c.METRIC_NAMES, c.ADJACENT_METRIC) if has_adjacent else c.METRIC_NAMES
        c.record(exact, " ".join(metric_names))
        c.record(display, " ".join((*metric_names, "rmse", "oos_improvement")))
        projected_exact: c.WireObject = {name: exact[name] for name in c.METRIC_NAMES}
        projected_display: c.WireObject = {name: display[name] for name in c.METRIC_NAMES}
        for source, target in ((exact, projected_exact), (display, projected_display)):
            target[c.ADJACENT_METRIC] = (
                c.present(source[c.ADJACENT_METRIC])
                if has_adjacent
                else c.unavailable(c.Reason.NO_ADJACENT_PAIRS)
            )
        projected_display["rmse"] = display["rmse"]
        projected_display["oos_improvement"] = (
            c.unavailable(c.Reason.ZERO_BASELINE_SSE)
            if display["oos_improvement"] is None
            else c.present(display["oos_improvement"])
        )
        return c.MetricsValue.from_wire(
            {
                "n": obj["n"],
                "exact": projected_exact,
                "display": projected_display,
                "oos_improvement": obj["oos_improvement"],
                "units": obj["units"],
                "iid_inference": obj["iid_inference"],
                "adjacent_residual_pairs": obj["adjacent_residual_pairs"],
                "diagnostic_interpretation": obj["diagnostic_interpretation"],
            }
        )
    except c.ContractError as error:
        return ProjectionRefusal(error.code)


FACT_FIELDS = (
    "month state amount source_ref publication available_at unit basis native_state reason "
    "qualification_ref version_ref"
)


def project_fact(native: object) -> c.FactTraceValue | ProjectionRefusal:
    try:
        obj = c.record(c.decode_json(c.canonical_json(native)), FACT_FIELDS)
        axes = project_axes([obj["state"], obj["native_state"]])
        if isinstance(axes, ProjectionRefusal):
            return axes
        if axes.pit_status is c.Pit.WITHHELD:
            return ProjectionRefusal(
                c.Reason.NATIVE_WITHHELD,
                c.Pit.WITHHELD,
                c.text(obj["state"]),
                c.text(obj["reason"]),
            )
        c.require(obj["state"] in tuple(c.FactState), c.Reason.NATIVE_UNKNOWN_STATE)
        if obj["state"] == "KNOWN":
            c.require(type(obj["amount"]) is int and 0 < obj["amount"] < 2**63)
        else:
            c.require(obj["amount"] is None)
        reason = (
            c.Reason.MISSING_PREDECESSOR
            if obj["reason"] == "MISSING_PREDECESSOR"
            else c.Reason.NOT_YET_AVAILABLE
        )
        result: c.WireObject = {
            field: obj[field]
            for field in (
                "month",
                "state",
                "native_state",
                "reason",
                "unit",
                "basis",
            )
        }
        for field in (
            "source_ref",
            "version_ref",
            "qualification_ref",
            "publication",
            "available_at",
        ):
            result[field] = c.unavailable(reason) if obj[field] is None else c.present(obj[field])
        return c.FactTraceValue.from_wire(result)
    except c.ContractError as error:
        return ProjectionRefusal(error.code)


def project_observation(native: object) -> c.ObservationTraceValue | ProjectionRefusal:
    try:
        obj = c.record(
            c.decode_json(c.canonical_json(native)),
            "sample_id issuer tick cutoff dataset_digest calendar_id current previous binding_id",
        )
        c.require(obj["dataset_digest"] == c.DATASET_SHA256)
        c.require(obj["calendar_id"] == "SYN-L1-CALENDAR-V1")
        identity = {k: v for k, v in obj.items() if k != "binding_id"}
        c.require(
            c.sha256_text(obj["binding_id"]) == sha256(c.canonical_json(identity)).hexdigest(),
            c.Reason.ARTIFACT_INTEGRITY_FAILED,
        )
        facts: dict[str, c.FactTraceValue] = {}
        for field in ("current", "previous"):
            projected = project_fact(obj[field])
            if isinstance(projected, ProjectionRefusal):
                return projected
            facts[field] = projected
        return c.ObservationTraceValue.from_wire(
            {
                "sample_id": obj["sample_id"],
                "issuer": obj["issuer"],
                "tick": obj["tick"],
                "cutoff": obj["cutoff"],
                "binding_id": c.NativeDigestRef(
                    c.ReferenceKind.BINDING, c.text(obj["binding_id"])
                ).to_wire(),
                "current": facts["current"].to_wire(),
                "previous": facts["previous"].to_wire(),
            }
        )
    except c.ContractError as error:
        return ProjectionRefusal(error.code)


def project_source_summary(native: object) -> c.SourceSummaryValue | ProjectionRefusal:
    try:
        # The target has the identical closed keys; only the digest is domain-tagged.
        obj = c.record(
            c.decode_json(c.canonical_json(native)),
            "dataset_digest calendar_id issuer_roster cutoffs calendar_coverage "
            "revenue_declarations price_marks scope non_if03 admission_eligible "
            "source_authentication native_invocations invocation_count_scope",
        )
        result = {k: v for k, v in obj.items() if k != "dataset_digest"}
        result["dataset_digest"] = c.NativeDigestRef(
            c.ReferenceKind.DATASET, c.sha256_text(obj["dataset_digest"])
        ).to_wire()
        return c.SourceSummaryValue.from_wire(result)
    except c.ContractError as error:
        return ProjectionRefusal(error.code)


def project_receipt(
    native: object, qualification_ref: str
) -> c.SafeReceiptValue | ProjectionRefusal:
    try:
        detached = c.decode_json(c.canonical_json(native))
        c.require(type(detached) is dict)
        obj = cast(c.WireObject, detached)
        fields = (
            "schema non_if03 dataset_digest cutoff subject state reason native_invocation "
            "selected_sources code_pins"
        )
        has_value = "revenue_value" in obj
        c.record(obj, fields + (" revenue_value" if has_value else ""))
        c.require(
            c.sha256_text(qualification_ref) == sha256(c.canonical_json(obj)).hexdigest(),
            c.Reason.ARTIFACT_INTEGRITY_FAILED,
        )
        result: c.WireObject = {
            field: obj[field] for field in fields.split() if field != "dataset_digest"
        }
        result["dataset_digest"] = c.NativeDigestRef(
            c.ReferenceKind.DATASET, c.sha256_text(obj["dataset_digest"])
        ).to_wire()
        result["qualification_ref"] = qualification_ref
        if has_value:
            value = c.record(obj["revenue_value"], "source_sha256 s1 s2 native_invocation value")
            c.require(type(value["value"]) is int and 0 < value["value"] < 2**63)
            result["revenue_value_qualification"] = c.present(
                {k: v for k, v in value.items() if k != "value"}
            )
        else:
            result["revenue_value_qualification"] = c.unavailable(c.Reason.NOT_YET_AVAILABLE)
        return c.SafeReceiptValue.from_wire(result)
    except c.ContractError as error:
        return ProjectionRefusal(error.code)


def project_fold(
    native_fold: object, native_state: object
) -> c.FoldResultValue | ProjectionRefusal:
    try:
        fold = c.record(
            c.decode_json(c.canonical_json(native_fold)),
            "fold history_candidates test_ticks fit_cutoff training_ids training_count "
            "training_cutoffs training_issuers distinct_issuer_month_releases "
            "distinct_source_versions latest_training_label_availability scored_cutoffs "
            "excluded_training exclusion_counts state_id scoring_cutoff prediction_id "
            "scored_ids excluded metrics",
        )
        state = c.record(
            c.decode_json(c.canonical_json(native_state)),
            "state_id training_ref fold fit_cutoff dataset_digest protocol_ref "
            "training_ids gbar rbar alpha beta",
        )
        for field in ("state_id", "fold", "fit_cutoff", "training_ids"):
            c.require(fold[field] == state[field])
        c.require(
            state["dataset_digest"] == c.DATASET_SHA256
            and state["protocol_ref"] == c.PROTOCOL_SHA256
        )
        c.sha256_text(state["training_ref"])
        c.require(
            c.sha256_text(state["state_id"])
            == sha256(
                c.canonical_json({k: v for k, v in state.items() if k != "state_id"})
            ).hexdigest(),
            c.Reason.ARTIFACT_INTEGRITY_FAILED,
        )
        for field in ("training_ids", "scored_ids"):
            c.require(type(fold[field]) is list)
            ids = cast(list[c.JSONValue], fold[field])
            c.require(
                all(type(v) is str for v in ids) and len(ids) == len(set(cast(list[str], ids)))
            )
        c.require(
            c.uint(fold["training_count"]) == len(cast(list[c.JSONValue], fold["training_ids"]))
        )
        c.native_time(fold["scoring_cutoff"])
        c.sha256_text(fold["prediction_id"])
        for field in ("excluded_training", "excluded"):
            c.require(type(fold[field]) is list)
            for row in cast(list[c.JSONValue], fold[field]):
                c.require(type(row) is list and len(row) == 2)
                pair = cast(list[c.JSONValue], row)
                c.text(pair[0])
                c.require(pair[1] in c.EXCLUSION_REASONS)
        counts = fold["exclusion_counts"]
        c.require(type(counts) is dict)
        counter = cast(c.WireObject, counts)
        c.require(all(k in c.EXCLUSION_REASONS for k in counter))
        for value in counter.values():
            c.uint(value)
        metrics = project_metrics(fold["metrics"])
        if isinstance(metrics, ProjectionRefusal):
            return metrics
        result: c.WireObject = {
            field: fold[field]
            for field in (
                "fold",
                "history_candidates",
                "test_ticks",
                "fit_cutoff",
                "training_count",
                "training_cutoffs",
                "training_issuers",
                "distinct_issuer_month_releases",
                "distinct_source_versions",
                "latest_training_label_availability",
                "scored_cutoffs",
            )
        }
        result.update(
            {
                "state_id": c.NativeDigestRef(
                    c.ReferenceKind.STATE, c.text(state["state_id"])
                ).to_wire(),
                "scored_count": len(cast(list[c.JSONValue], fold["scored_ids"])),
                "excluded_training_count": len(cast(list[c.JSONValue], fold["excluded_training"])),
                "exclusion_counts": [
                    {"native_reason": k, "count": counter[k]} for k in sorted(counter)
                ],
                "metrics": metrics.to_wire(),
                **{field: state[field] for field in ("alpha", "beta", "gbar", "rbar")},
            }
        )
        return c.FoldResultValue.from_wire(result)
    except c.ContractError as error:
        return ProjectionRefusal(error.code)
