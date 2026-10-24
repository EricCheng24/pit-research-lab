"""IC1 explicit guarded reader, outer code observation and stopped external boundary."""

import os
from dataclasses import asdict, dataclass, field
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
from pit_research_lab.domain.market_row_selection import (
    ABSENT,
    FullMarketSelectionOutcome,
    FullMarketSelectionSpec,
    canonical,
    preflight_manifest,
    select_market_row,
    validate_ic1_intake,
)
from pit_research_lab.domain.offline_replay import (
    OWNERS,
    OfflineCodeObservation,
    StageFinding,
    _check_code,
    observe_offline_code,
)
from pit_research_lab.domain.source_intake import (
    MAX_METADATA_BYTES,
    MAX_RAW_BYTES,
    FilePin,
    IntakeResult,
    OfflineSourceManifest,
    _open_root,
    _read_relative,
    decode_manifest,
    intake_result,
    json_object,
    safe_relative,
    text_value,
    validate_source_manifest,
)

IC1_CODE_PATHS = (
    "src/pit_research_lab/domain/market_row_selection.py",
    "src/pit_research_lab/domain/market_source_slice.py",
)


@dataclass(frozen=True)
class IC1SourceInput(Record):
    intake: IntakeResult
    notes_pin: FilePin
    notes_bytes: bytes | NotEvaluated
    read_stages: tuple[StageFinding, ...] = ()


@dataclass(frozen=True)
class IC1CodeObservation(Record):
    upstream_a06: OfflineCodeObservation
    extension_pins: tuple[CodePin, ...]
    extension_byte_lengths: tuple[int, ...]
    interpretation: str = "OBSERVED_DISK_BYTES; NOT_RUNTIME_ATTESTED"


@dataclass(frozen=True)
class IC1BoundaryResult(Record):
    source: IC1SourceInput
    selection: FullMarketSelectionOutcome
    stages: tuple[StageFinding, ...]
    owner_results: tuple[tuple[str, NotEvaluated], ...]
    research_ref: str
    code: IC1CodeObservation
    diagnostic_preview_bytes: bytes
    overall_disposition: str = field(default="INTEGRATED_PROVISIONAL", init=False)
    trust: str = field(default="NOT_TRUSTED_PIT_EVIDENCE", init=False)
    source_authentication: str = field(default="NOT_ESTABLISHED", init=False)
    admission_eligible: bool = field(default=False, init=False)
    diagnostic_only: bool = field(default=True, init=False)
    agent_observation: NotEvaluated = field(
        default=NotEvaluated("IC1", "AGENT_OBSERVATION_NOT_PRODUCED"), init=False
    )


def inspect_market_source(
    root: Path, notes_pin: FilePin, manifest_path: str = "manifest.json"
) -> IC1SourceInput:
    """Explicit I/O: bounded metadata/permission first, original source only after success.

    Notes are separately pinned IC1 audit metadata, outside A06 raw/mapping identity.
    No file creation, path discovery, permission inference or source-text logging.
    """
    manifest: OfflineSourceManifest | NotEvaluated = ABSENT
    root_fd: int | None = None
    read_stages: list[StageFinding] = []
    try:
        safe_relative(manifest_path)
        require(manifest_path.endswith(".json"), "MANIFEST_MUST_BE_JSON")
        require(notes_pin.byte_length <= MAX_METADATA_BYTES, "NOTES_SIZE_LIMIT")
        root_fd = _open_root(root)
        read_stages.append(StageFinding("MANIFEST_READ", "ATTEMPTED", "EXPLICIT_GUARDED_IO"))
        manifest = decode_manifest(_read_relative(root_fd, manifest_path, MAX_METADATA_BYTES))
        paths = (manifest_path, notes_pin.relative_path, manifest.raw.relative_path) + (
            (manifest.mapping_file.relative_path,) if manifest.mapping_file else ()
        )
        require(len(paths) == len(set(paths)), "INPUT_ROLE_PATH_COLLISION")
        preflight = preflight_manifest(manifest)
        read_stages[-1] = StageFinding("MANIFEST_READ", "READ", "BOUNDED_METADATA_ONLY")
        read_stages.append(
            StageFinding("RIGHTS_PREFLIGHT", preflight.disposition, preflight.reason)
        )
        if preflight.reason != "RIGHTS_PREFLIGHT_PASSED":
            return IC1SourceInput(preflight, notes_pin, ABSENT, tuple(read_stages))
        read_stages.append(StageFinding("NOTES_READ", "ATTEMPTED", "EXPLICIT_GUARDED_IO"))
        notes = _read_relative(root_fd, notes_pin.relative_path, MAX_METADATA_BYTES)
        require(
            len(notes) == notes_pin.byte_length and sha256(notes).hexdigest() == notes_pin.sha256,
            "NOTES_PIN_MISMATCH",
        )
        read_stages[-1] = StageFinding("NOTES_READ", "READ_AND_PINNED", "NOTES_PIN_MATCH")
        read_stages.append(StageFinding("RAW_READ", "ATTEMPTED", "RIGHTS_PREFLIGHT_PASSED"))
        raw = _read_relative(root_fd, manifest.raw.relative_path, MAX_RAW_BYTES)
        read_stages[-1] = StageFinding("RAW_READ", "READ", "INTEGRITY_CHECK_FOLLOWS")
        if manifest.mapping_file:
            read_stages.append(StageFinding("MAPPING_READ", "ATTEMPTED", "EXPLICIT_GUARDED_IO"))
        mapping = (
            _read_relative(root_fd, manifest.mapping_file.relative_path, MAX_METADATA_BYTES)
            if manifest.mapping_file
            else None
        )
        if manifest.mapping_file:
            read_stages[-1] = StageFinding("MAPPING_READ", "READ", "INTEGRITY_CHECK_FOLLOWS")
        checked = validate_source_manifest(manifest, raw, mapping)
        checked = validate_ic1_intake(checked)
        if checked.disposition != "SOURCE_SNAPSHOT_ACCEPTED_FOR_OFFLINE_PARSE":
            return IC1SourceInput(checked, notes_pin, ABSENT, tuple(read_stages))
        return IC1SourceInput(checked, notes_pin, notes, tuple(read_stages))
    except FileNotFoundError:
        result = intake_result(
            "SOURCE_INPUT_PENDING", "ROOT_MANIFEST_OR_PINNED_FILE_MISSING", manifest, ABSENT, ABSENT
        )
    except (OSError, ContractError) as exc:
        reason = (
            str(exc) if isinstance(exc, ContractError) else "UNSAFE_PATH_OR_READ_OPERATION_FAILED"
        )
        result = intake_result("SOURCE_INTEGRITY_FAILURE", reason, manifest, ABSENT, ABSENT)
    finally:
        if root_fd is not None:
            os.close(root_fd)
    if read_stages and read_stages[-1].state == "ATTEMPTED":
        last = read_stages[-1]
        read_stages[-1] = StageFinding(last.stage, "FAILED", result.reason)
    return IC1SourceInput(result, notes_pin, ABSENT, tuple(read_stages))


def observe_ic1_code(repository: Path) -> IC1CodeObservation:
    """Explicit read-only outer observation; preserves the existing 10 + 2 + 3 structure."""
    previous = observe_offline_code(repository)
    bodies = tuple((repository / path).read_bytes() for path in IC1_CODE_PATHS)
    return IC1CodeObservation(
        previous,
        tuple(
            CodePin(path, sha256(body).hexdigest())
            for path, body in zip(IC1_CODE_PATHS, bodies, strict=True)
        ),
        tuple(len(body) for body in bodies),
    )


def _mapping(source: IC1SourceInput, selected: bool) -> StageFinding:
    if not selected:
        return StageFinding("MAPPING", "NOT_EVALUATED", "SELECTION_NOT_COMPLETE")
    intake = source.intake
    manifest = intake.manifest
    assert isinstance(manifest, OfflineSourceManifest)
    if manifest.mapping_file is None or not isinstance(intake.mapping_bytes, bytes):
        return StageFinding("MAPPING", "MAPPING_UNRESOLVED", "INDEPENDENT_METADATA_MISSING")
    try:
        support = json_object(intake.mapping_bytes)
        expected = {
            "issuer_code": manifest.company_code,
            "metric": "net_operating_revenue",
            "period_kind": "DURATION",
            "reporting_scope": "consolidated",
            "basis_ref": "BASIS-CONSOLIDATED-V1",
            "currency": "NTD",
            "canonical_unit": "NTD_thousands",
        }
        require(
            set(support)
            == set(expected)
            | {
                "issuer_ref",
                "mapping_schema",
                "source_columns",
                "applies_to_raw_sha256",
                "support_class",
                "evidence_origin",
                "evidence_text",
            },
            "INVALID_MAPPING_METADATA_SCHEMA",
        )
        require(
            support["mapping_schema"] == "a06-field-mapping-v0.1"
            and support["applies_to_raw_sha256"] == manifest.raw.sha256,
            "MAPPING_RAW_MISMATCH",
        )
        require(
            support["source_columns"]
            == {
                "company_code": "公司代號",
                "reference_period": "資料年月",
                "source_amount": "營業收入-當月營收",
            },
            "MAPPING_METADATA_COLUMN_MISMATCH",
        )
        require(
            all(support[k] == v for k, v in expected.items()),
            "UNSUPPORTED_OR_INCOMPATIBLE_FIELD_MAPPING",
        )
        require(
            support["support_class"] == "INDEPENDENT_SOURCE_METADATA"
            or (
                support["support_class"] == "SYNTHETIC_TEST_ONLY"
                and manifest.data_classification == "SYNTHETIC_TEST_ONLY"
            ),
            "MAPPING_INDEPENDENCE_NOT_ESTABLISHED",
        )
        text_value(support["issuer_ref"])
        text_value(support["evidence_origin"])
        explanation = text_value(support["evidence_text"])
        require(not explanation.startswith(("http://", "https://")), "MAPPING_EXPLANATION_MISSING")
        return StageFinding(
            "MAPPING", "MAPPED_CONDITIONALLY", "SUPPLIED_METADATA_NOT_AUTHENTICATED"
        )
    except ContractError as exc:
        return StageFinding("MAPPING", "MAPPING_REJECTED", str(exc))


def evaluate_market_source(
    source: IC1SourceInput,
    spec: FullMarketSelectionSpec,
    context: SemanticContext,
    code: IC1CodeObservation,
) -> IC1BoundaryResult:
    """Pure revalidation and research identity; no native owner dispatch or proof creation."""
    intake = validate_ic1_intake(source.intake)
    try:
        _check_code(context, code.upstream_a06)
        require(
            tuple(p.path for p in code.extension_pins) == IC1_CODE_PATHS
            and len(code.extension_byte_lengths) == len(IC1_CODE_PATHS)
            and all(type(n) is int and n > 0 for n in code.extension_byte_lengths),
            "INVALID_IC1_CODE_OBSERVATION",
        )
        if isinstance(intake.manifest, OfflineSourceManifest):
            require(
                context.evidence_set_ref == intake.manifest.snapshot_ref,
                "CONTEXT_SOURCE_SNAPSHOT_MISMATCH",
            )
        if intake.disposition == "SOURCE_SNAPSHOT_ACCEPTED_FOR_OFFLINE_PARSE":
            manifest = intake.manifest
            assert isinstance(manifest, OfflineSourceManifest)
            roles = (source.notes_pin.relative_path, manifest.raw.relative_path) + (
                (manifest.mapping_file.relative_path,) if manifest.mapping_file else ()
            )
            require(len(roles) == len(set(roles)), "INPUT_ROLE_PATH_COLLISION")
            require(
                isinstance(source.notes_bytes, bytes)
                and len(source.notes_bytes) <= MAX_METADATA_BYTES
                and len(source.notes_bytes) == source.notes_pin.byte_length
                and sha256(source.notes_bytes).hexdigest() == source.notes_pin.sha256,
                "NOTES_PIN_MISMATCH",
            )
    except ContractError as exc:
        intake = intake_result(
            "SOURCE_INTEGRITY_FAILURE", str(exc), intake.manifest, ABSENT, ABSENT
        )
    notes = (
        source.notes_bytes
        if intake.disposition == "SOURCE_SNAPSHOT_ACCEPTED_FOR_OFFLINE_PARSE"
        else ABSENT
    )
    safe_source = IC1SourceInput(intake, source.notes_pin, notes, source.read_stages)
    selection = select_market_row(intake, spec)
    ready = intake.disposition == "SOURCE_SNAPSHOT_ACCEPTED_FOR_OFFLINE_PARSE"
    mapping = _mapping(safe_source, selection.state == "ROW_SELECTED")
    stages = (
        StageFinding(
            "SOURCE_BYTES",
            "PINNED_BYTES_REVALIDATED" if ready else "UNAVAILABLE_OR_REFUSED",
            intake.reason,
        ),
        StageFinding(
            "RIGHTS", "SUPPLIED_RECORD_COMPLETE" if ready else intake.disposition, intake.reason
        ),
        StageFinding("INTAKE", intake.disposition, intake.reason),
        StageFinding("EXTRACTION", selection.state, selection.reason),
        mapping,
        StageFinding(
            "TYPED_TRANSPORT",
            "UNSUPPORTED_EXTERNAL_SOURCE_SCHEMA",
            "NO_NATIVE_EXTERNAL_CSV_TRANSPORT",
        ),
        *(StageFinding(owner, "NOT_EVALUATED", "EXTERNAL_SOURCE_BOUNDARY") for owner in OWNERS),
    )
    owners = tuple((owner, NotEvaluated(owner, "IC1_EXTERNAL_SOURCE_BOUNDARY")) for owner in OWNERS)
    preview = canonical(
        {
            "preview_kind": "RESEARCH_DIAGNOSTIC_ONLY",
            "mode": context.mode,
            "availability": "WITHHELD",
            "disposition": "INTEGRATED_PROVISIONAL",
            "trust": "NOT_TRUSTED_PIT_EVIDENCE",
            "source_authentication": "NOT_ESTABLISHED",
            "admission_eligible": False,
            "diagnostic_only": True,
        }
    )
    # Audit narrative can change provenance identity but never selects/ranks a financial row.
    identity = (
        asdict(spec),
        asdict(context),
        asdict(code),
        asdict(intake.manifest),
        asdict(source.notes_pin),
        sha256(notes).hexdigest() if isinstance(notes, bytes) else None,
        selection.state,
        selection.reason,
        selection.selected.view.projection_sha256
        if selection.state == "ROW_SELECTED" and not isinstance(selection.selected, NotEvaluated)
        else None,
    )
    return IC1BoundaryResult(
        safe_source,
        selection,
        stages,
        owners,
        "IC1-RESEARCH-" + sha256(canonical(identity)).hexdigest(),
        code,
        preview,
    )
