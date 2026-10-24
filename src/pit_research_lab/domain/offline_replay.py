"""A06 conservative CSV boundary, not another S1/S2/S3/S4 owner.

No supported native external-CSV contract exists in the preserved owners.
Consequently this slice NEVER fabricates or dispatches issuer/provider requests.
"""

import json
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from pit_research_lab.domain.contracts import (
    CodePin,
    ContractError,
    NotEvaluated,
    Record,
    SemanticContext,
    require,
)
from pit_research_lab.domain.derivation import S4_CODE_PATHS
from pit_research_lab.domain.pit_slice import CODE_PATHS
from pit_research_lab.domain.ratio import RATIO_CODE_PATHS, RatioCodeObservation
from pit_research_lab.domain.ratio_slice import observe_ratio_code
from pit_research_lab.domain.selection import S3_CODE_PATHS
from pit_research_lab.domain.source_adapter import (
    ExtractionResult,
    MappingAssessment,
    assess_mapping,
    extract_monthly_rows,
)
from pit_research_lab.domain.source_intake import (
    IntakeResult,
    OfflineSourceManifest,
    RawSourceIdentity,
    validate_source_manifest,
)

EVALUATOR_REF = "a06-offline-boundary-v0.1-CANDIDATE"
A06_CODE_PATHS = (
    "src/pit_research_lab/domain/source_intake.py",
    "src/pit_research_lab/domain/source_adapter.py",
    "src/pit_research_lab/domain/offline_replay.py",
)
OWNERS = ("S1", "S2", "S3", "A04", "A05")


@dataclass(frozen=True)
class OfflineCodeObservation(Record):
    upstream_a05: RatioCodeObservation
    extension_pins: tuple[CodePin, ...]
    extension_byte_lengths: tuple[int, ...]
    interpretation: str = (
        "OBSERVED_DISK_BYTES; HEAD_IS_NOT_COMPLETE_CODE_VERSION; NOT_RUNTIME_ATTESTED"
    )


@dataclass(frozen=True)
class RowProjection(Record):
    original: RawSourceIdentity
    row_ordinal: int
    projection_bytes: bytes
    projection_sha256: str
    representation_kind: str = field(default="ADAPTER_GENERATED_PROJECTION", init=False)
    scope: str = field(default="EXTRACTED_ROW_DIAGNOSTIC_ONLY; NOT_NATIVE_S1_CONTENT", init=False)


@dataclass(frozen=True)
class StageFinding(Record):
    stage: str
    state: str
    reason: str


@dataclass(frozen=True)
class OfflineReplayResult(Record):
    disposition: str
    reason: str
    context: SemanticContext
    intake: IntakeResult
    extraction: ExtractionResult | NotEvaluated
    mapping: MappingAssessment | NotEvaluated
    projections: tuple[RowProjection, ...]
    stages: tuple[StageFinding, ...]
    owner_results: tuple[tuple[str, NotEvaluated], ...]
    research_ref: str
    code: OfflineCodeObservation
    diagnostic_preview_bytes: bytes
    evidence_gaps: tuple[str, ...]
    overall_disposition: str = field(default="INTEGRATED_PROVISIONAL", init=False)
    trust: str = field(default="NOT_TRUSTED_PIT_EVIDENCE", init=False)
    source_authentication: str = field(default="NOT_ESTABLISHED", init=False)
    admission_eligible: bool = field(default=False, init=False)
    diagnostic_only: bool = field(default=True, init=False)
    agent_observation: NotEvaluated = field(
        default=NotEvaluated("A06", "AGENT_OBSERVATION_NOT_PRODUCED"), init=False
    )


def observe_offline_code(repository: Path) -> OfflineCodeObservation:
    """Explicit read-only code observer, outside source reading and pure replay."""
    previous = observe_ratio_code(repository)
    bodies = tuple((repository / path).read_bytes() for path in A06_CODE_PATHS)
    return OfflineCodeObservation(
        previous,
        tuple(
            CodePin(path, sha256(body).hexdigest())
            for path, body in zip(A06_CODE_PATHS, bodies, strict=True)
        ),
        tuple(len(body) for body in bodies),
    )


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _check_code(context: SemanticContext, code: OfflineCodeObservation) -> None:
    previous = code.upstream_a05
    original = previous.upstream_a04
    require(
        tuple(p.path for p in original.observed_working_files)
        == (*CODE_PATHS, *S3_CODE_PATHS, *S4_CODE_PATHS)
        and tuple(p.path for p in previous.extension_pins) == RATIO_CODE_PATHS
        and tuple(p.path for p in code.extension_pins) == A06_CODE_PATHS,
        "INCOMPLETE_OR_MIXED_CODE_OBSERVATION",
    )
    for pins, lengths in (
        (original.observed_working_files, original.byte_lengths),
        (previous.extension_pins, previous.extension_byte_lengths),
        (code.extension_pins, code.extension_byte_lengths),
    ):
        require(
            len(pins) == len(lengths) and all(type(n) is int and n >= 0 for n in lengths),
            "INVALID_CODE_LENGTHS",
        )
    require(
        context.profile.code_pins == original.observed_working_files,
        "CONTEXT_CODE_OBSERVATION_MISMATCH",
    )


def _projections(intake: IntakeResult, extraction: ExtractionResult) -> tuple[RowProjection, ...]:
    assert isinstance(intake.observed_raw, RawSourceIdentity)
    result = []
    for row in extraction.rows:
        # Explicitly a new diagnostic schema, never synthetic-notice-v1/provider.
        body = _canonical(
            {
                "projection_schema": "a06-extracted-row-v0.1",
                "row_ordinal": row.row_ordinal,
                "original_sha256": row.raw_sha256,
                "headers": row.headers,
                "source_fields": row.source_fields,
                "source_tokens": row.source_tokens,
            }
        )
        result.append(
            RowProjection(intake.observed_raw, row.row_ordinal, body, sha256(body).hexdigest())
        )
    return tuple(result)


def evaluate_offline_replay(
    intake: IntakeResult, context: SemanticContext, code: OfflineCodeObservation, /
) -> OfflineReplayResult:
    """Pure negative/conditional replay. No timestamp parsing or owner fabrication."""
    not_run = NotEvaluated("A06", "SOURCE_BOUNDARY_NOT_PASSED")
    extraction: ExtractionResult | NotEvaluated = not_run
    mapping: MappingAssessment | NotEvaluated = not_run
    projections: tuple[RowProjection, ...] = ()
    findings = [StageFinding("INTAKE", intake.disposition, intake.reason)]
    disposition: str = intake.disposition
    reason = intake.reason
    gaps = (
        "ORIGINAL_SOURCE_AUTHENTICATION_NOT_ESTABLISHED",
        "UNSUPPORTED_EXTERNAL_SOURCE_SCHEMA",
        "GENUINE_COVERAGE_NOT_SUPPLIED",
        "MISSING_CONTENT_BOUND_PUBLICATION_PROOF"
        if context.mode == "public"
        else "HISTORICAL_CONTENT_BOUND_LAB_CAPTURE_NOT_SUPPLIED",
    )
    try:
        _check_code(context, code)
        manifest = intake.manifest
        if isinstance(manifest, OfflineSourceManifest):
            require(
                context.evidence_set_ref == manifest.snapshot_ref,
                "CONTEXT_SOURCE_SNAPSHOT_MISMATCH",
            )
            if isinstance(intake.raw_bytes, bytes):
                checked = validate_source_manifest(
                    manifest,
                    intake.raw_bytes,
                    intake.mapping_bytes if isinstance(intake.mapping_bytes, bytes) else None,
                )
                require(checked == intake, "INTAKE_RESULT_TRANSPORT_MISMATCH")
        if intake.disposition == "SOURCE_SNAPSHOT_ACCEPTED_FOR_OFFLINE_PARSE":
            require(
                isinstance(manifest, OfflineSourceManifest) and isinstance(intake.raw_bytes, bytes),
                "READY_WITHOUT_ORIGINAL_BYTES",
            )
            extraction = extract_monthly_rows(intake)
            findings.append(StageFinding("EXTRACTION", extraction.state, extraction.reason))
            if extraction.state != "EXTRACTED":
                disposition, reason = "SOURCE_EXTRACTION_" + extraction.state, extraction.reason
            else:
                projections = _projections(intake, extraction)
                mapping = assess_mapping(intake, extraction)
                findings.append(StageFinding("MAPPING", mapping.state, mapping.reason))
                if mapping.state != "MAPPED":
                    disposition, reason = "MAPPING_" + mapping.state, mapping.reason
                else:
                    disposition, reason = (
                        "UNSUPPORTED_EXTERNAL_SOURCE_SCHEMA",
                        "NO_TRUTHFUL_NATIVE_S1_CSV_TRANSPORT",
                    )
                    findings.append(StageFinding("TYPED_TRANSPORT", "NOT_SUPPORTED", reason))
    except ContractError as exc:
        disposition, reason = "CONTRACT_VIOLATION", str(exc)
    reached = {finding.stage for finding in findings}
    for stage in ("EXTRACTION", "MAPPING", "TYPED_TRANSPORT", *OWNERS):
        if stage not in reached:
            findings.append(StageFinding(stage, "NOT_EVALUATED", "SOURCE_BOUNDARY_NOT_PASSED"))
    owners = tuple(
        (owner, NotEvaluated(owner, "A06_EXTERNAL_SOURCE_BOUNDARY_NOT_PASSED")) for owner in OWNERS
    )
    preview = _canonical(
        {
            "preview_kind": "RESEARCH_DIAGNOSTIC_ONLY",
            "cutoff": context.information_cutoff.source_text,
            "mode": context.mode,
            "availability": "WITHHELD",
            "disposition": "INTEGRATED_PROVISIONAL",
            "trust": "NOT_TRUSTED_PIT_EVIDENCE",
            "source_authentication": "NOT_ESTABLISHED",
            "admission_eligible": False,
            "diagnostic_only": True,
        }
    )
    previous = code.upstream_a05
    pins = (
        *previous.upstream_a04.observed_working_files,
        *previous.extension_pins,
        *code.extension_pins,
    )
    source_identity = (
        intake.observed_raw.sha256 if isinstance(intake.observed_raw, RawSourceIdentity) else None,
        intake.manifest.snapshot_ref
        if isinstance(intake.manifest, OfflineSourceManifest)
        else None,
    )
    manifest_semantics = (
        (
            intake.manifest.bundle_ref,
            intake.manifest.csv_profile,
            intake.manifest.encoding,
            intake.manifest.headers,
            intake.manifest.period_policy,
            intake.manifest.integer_policy,
            intake.manifest.source_class,
            intake.manifest.data_classification,
            intake.manifest.company_code,
            intake.manifest.year,
            intake.manifest.quarter,
        )
        if isinstance(intake.manifest, OfflineSourceManifest)
        else None
    )
    cutoff = context.information_cutoff
    identity = (
        EVALUATOR_REF,
        source_identity,
        manifest_semantics,
        (cutoff.timezone_name, cutoff.offset, cutoff.precision),
        context.context_ref,
        context.evidence_set_ref,
        context.calendar_ref,
        context.policy_refs,
        context.numeric_ref,
        preview.decode(),
        disposition,
        reason,
        tuple((p.path, p.sha256) for p in pins),
    )
    return OfflineReplayResult(
        disposition,
        reason,
        context,
        intake,
        extraction,
        mapping,
        projections,
        tuple(findings),
        owners,
        "A06-RESEARCH-" + sha256(_canonical(identity)).hexdigest(),
        code,
        preview,
        gaps,
    )
