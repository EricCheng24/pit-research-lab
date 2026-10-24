"""IC1 exact single-month source selection; no historical version selection or I/O."""

import json
import re
from dataclasses import dataclass, field
from datetime import date
from hashlib import sha256
from typing import Literal

from pit_research_lab.domain.contracts import (
    ContractError,
    NotEvaluated,
    Record,
    identifier,
    require,
)
from pit_research_lab.domain.offline_replay import RowProjection
from pit_research_lab.domain.source_adapter import (
    CSV_PROFILE,
    ExtractedMonthlyRow,
    _amount,
    _csv_records,
    _period,
)
from pit_research_lab.domain.source_intake import (
    MANIFEST_VERSION,
    IntakeResult,
    OfflineSourceManifest,
    RawSourceIdentity,
    intake_result,
    safe_relative,
    snapshot_ref_for,
    validate_source_manifest,
)

POLICY = "A06-IC1-EXACT_COMPANY_MONTH-v0.1"
HEADERS = (
    "出表日期",
    "資料年月",
    "公司代號",
    "公司名稱",
    "產業別",
    "營業收入-當月營收",
    "營業收入-上月營收",
    "營業收入-去年當月營收",
    "營業收入-上月比較增減(%)",
    "營業收入-去年同月增減(%)",
    "累計營業收入-當月累計營收",
    "累計營業收入-去年累計營收",
    "累計營業收入-前期比較增減(%)",
    "備註",
)
ABSENT = NotEvaluated("IC1", "BYTES_NOT_EVALUATED")


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


@dataclass(frozen=True)
class FullMarketSelectionSpec(Record):
    company_code: str = "2303"
    reference_month: str = "2026-09"
    policy: Literal["A06-IC1-EXACT_COMPANY_MONTH-v0.1"] = "A06-IC1-EXACT_COMPANY_MONTH-v0.1"
    period_policy: Literal["ROC_YYYMM_PLUS_1911-v0.1"] = "ROC_YYYMM_PLUS_1911-v0.1"
    amount_column: Literal["營業收入-當月營收"] = "營業收入-當月營收"
    expected_record_count: int | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        require(self.policy == POLICY, "UNSUPPORTED_SELECTION_POLICY")
        require(re.fullmatch(r"[0-9]{1,10}", self.company_code) is not None, "INVALID_COMPANY_CODE")
        require(
            re.fullmatch(r"[0-9]{4}-[0-9]{2}", self.reference_month) is not None,
            "INVALID_REFERENCE_MONTH",
        )
        try:
            date.fromisoformat(self.reference_month + "-01")
        except ValueError as exc:
            raise ContractError("INVALID_REFERENCE_MONTH") from exc
        require(self.period_policy == "ROC_YYYMM_PLUS_1911-v0.1", "UNSUPPORTED_PERIOD_POLICY")
        require(self.amount_column == HEADERS[5], "UNSUPPORTED_SOURCE_AMOUNT_COLUMN")
        require(
            self.expected_record_count is None
            or (
                type(self.expected_record_count) is int and 0 <= self.expected_record_count <= 10000
            ),
            "INVALID_EXPECTED_RECORD_COUNT",
        )


@dataclass(frozen=True)
class SelectionView(RowProjection):
    representation_kind: str = field(default="ADAPTER_GENERATED_SELECTION_VIEW", init=False)


@dataclass(frozen=True)
class SelectedSourceRow(Record):
    original: RawSourceIdentity
    extracted: ExtractedMonthlyRow
    view: SelectionView
    amount_column_index: int = field(default=5, init=False)  # zero based
    amount_column_name: str = field(default=HEADERS[5], init=False)
    amount_semantics: str = field(default="SOURCE_REPORTED_INTEGER_ONLY", init=False)


@dataclass(frozen=True)
class FullMarketSelectionOutcome(Record):
    state: Literal[
        "ROW_SELECTED",
        "TARGET_ROW_NOT_FOUND",
        "DUPLICATE_TARGET_ROW",
        "EXTRACTION_REJECTED",
        "NOT_EVALUATED",
    ]
    reason: str
    original: RawSourceIdentity | NotEvaluated
    selected: SelectedSourceRow | NotEvaluated
    record_count: int | NotEvaluated
    match_count: int | NotEvaluated


def preflight_manifest(manifest: OfflineSourceManifest) -> IntakeResult:
    """IC1 metadata-only equivalent of the current A06 permission requirements.

    This is supplied-record completeness, never independent legal authentication.
    Legacy A06 reader/validator remain unchanged and their retention risk stays open.
    """
    try:
        require(manifest.manifest_version == MANIFEST_VERSION, "UNSUPPORTED_MANIFEST_VERSION")
        identifier(manifest.bundle_ref)
        safe_relative(manifest.raw.relative_path)
        require(manifest.raw.relative_path.endswith(".csv"), "RAW_FILE_MUST_BE_CSV")
        mapping = manifest.mapping_file
        if mapping is not None:
            safe_relative(mapping.relative_path)
            require(
                mapping.relative_path.endswith(".json")
                and mapping.relative_path != manifest.raw.relative_path,
                "INVALID_MAPPING_PATH",
            )
        require(
            manifest.snapshot_ref
            == snapshot_ref_for(manifest.raw.sha256, mapping.sha256 if mapping else None),
            "SNAPSHOT_PIN_MISMATCH",
        )
        require(
            manifest.data_classification in {"OWNER_SUPPLIED_EXTERNAL", "SYNTHETIC_TEST_ONLY"}
            and manifest.source_class
            in {
                "ISSUER_ORIGINAL",
                "EXCHANGE_AGGREGATE",
                "GOVERNMENT_AGGREGATE",
                "THIRD_PARTY",
                "UNKNOWN",
            },
            "INVALID_SOURCE_CLASSIFICATION",
        )
        require(
            bool(manifest.custody_ref)
            and bool(manifest.acquisition_origin)
            and manifest.acquisition_reliability
            in {"OWNER_DECLARED", "DOCUMENTED_NOT_AUTHENTICATED"},
            "CUSTODY_RECORD_MISSING_OR_UNSUPPORTED",
        )
        rights = manifest.rights
        paths = (manifest.raw.relative_path,) + ((mapping.relative_path,) if mapping else ())
        if not (
            rights.status == "PERMITTED"
            and rights.allowed_uses == ("OFFLINE_RESEARCH",)
            and tuple(sorted(rights.covered_paths)) == tuple(sorted(paths))
            and all((rights.terms_ref, rights.attribution, rights.evidence_text, rights.origin_ref))
            and isinstance(rights.evidence_text, str)
            and not rights.evidence_text.startswith(("http://", "https://"))
        ):
            return intake_result(
                "SOURCE_RESTRICTED_OR_RIGHTS_UNRESOLVED",
                "RIGHTS_RECORD_INCOMPLETE_RESTRICTED_OR_NOT_APPLICABLE",
                manifest,
                ABSENT,
                ABSENT,
            )
        return intake_result(
            "SOURCE_INPUT_PENDING", "RIGHTS_PREFLIGHT_PASSED", manifest, ABSENT, ABSENT
        )
    except ContractError as exc:
        return intake_result("SOURCE_INTEGRITY_FAILURE", str(exc), manifest, ABSENT, ABSENT)


def validate_ic1_intake(intake: IntakeResult) -> IntakeResult:
    """Recheck permission and original bytes; strip every refused payload."""
    if not isinstance(intake.manifest, OfflineSourceManifest):
        if intake.disposition == "SOURCE_SNAPSHOT_ACCEPTED_FOR_OFFLINE_PARSE":
            return intake_result(
                "SOURCE_INTEGRITY_FAILURE",
                "READY_WITHOUT_MANIFEST",
                intake.manifest,
                ABSENT,
                ABSENT,
            )
        return intake_result(intake.disposition, intake.reason, intake.manifest, ABSENT, ABSENT)
    preflight = preflight_manifest(intake.manifest)
    if preflight.reason != "RIGHTS_PREFLIGHT_PASSED":
        return preflight
    checked = validate_source_manifest(
        intake.manifest,
        intake.raw_bytes if isinstance(intake.raw_bytes, bytes) else None,
        intake.mapping_bytes if isinstance(intake.mapping_bytes, bytes) else None,
    )
    if checked.disposition != "SOURCE_SNAPSHOT_ACCEPTED_FOR_OFFLINE_PARSE":
        return intake_result(checked.disposition, checked.reason, checked.manifest, ABSENT, ABSENT)
    if checked != intake:
        return intake_result(
            "SOURCE_INTEGRITY_FAILURE",
            "INTAKE_RESULT_TRANSPORT_MISMATCH",
            intake.manifest,
            ABSENT,
            ABSENT,
        )
    return checked


def select_market_row(
    intake: IntakeResult, spec: FullMarketSelectionSpec
) -> FullMarketSelectionOutcome:
    """Validate all records, count exact matches, then interpret only the unique amount."""
    checked = validate_ic1_intake(intake)
    original = checked.observed_raw
    if checked.disposition != "SOURCE_SNAPSHOT_ACCEPTED_FOR_OFFLINE_PARSE":
        return FullMarketSelectionOutcome(
            "NOT_EVALUATED", checked.reason, original, ABSENT, ABSENT, ABSENT
        )
    assert isinstance(checked.manifest, OfflineSourceManifest)
    assert isinstance(checked.raw_bytes, bytes) and isinstance(original, RawSourceIdentity)
    manifest, raw = checked.manifest, checked.raw_bytes
    try:
        require(manifest.csv_profile == CSV_PROFILE, "UNSUPPORTED_CSV_PROFILE")
        require(
            manifest.encoding == "UTF8_BOM" and raw.startswith(b"\xef\xbb\xbf"),
            "ENCODING_PROFILE_MISMATCH",
        )
        require(manifest.headers == HEADERS, "INVALID_OR_DUPLICATE_CSV_HEADERS")
        require(manifest.period_policy == spec.period_policy, "UNSUPPORTED_PERIOD_POLICY")
        require(
            manifest.company_code == spec.company_code
            and manifest.year == int(spec.reference_month[:4])
            and manifest.quarter == (int(spec.reference_month[5:]) - 1) // 3 + 1,
            "MANIFEST_SELECTION_SCOPE_MISMATCH",
        )
        _amount("0", manifest.integer_policy)
        records = _csv_records(raw[3:].decode("utf-8", errors="strict"))
        require(bool(records) and records[0][0] == HEADERS, "INVALID_OR_DUPLICATE_CSV_HEADERS")
        count = len(records) - 1
        require(
            spec.expected_record_count is None or count == spec.expected_record_count,
            "FILE_RECORD_COUNT_MISMATCH",
        )
        matches = []
        for ordinal, (values, tokens) in enumerate(records[1:], 1):
            require(len(values) == len(HEADERS), "CSV_FIELD_COUNT_MISMATCH")
            period = _period(values[1], spec.period_policy)
            require(
                period[0].isoformat()[:7] == spec.reference_month, "FILE_MONTH_PROFILE_MISMATCH"
            )
            if values[2] == spec.company_code:
                matches.append((ordinal, values, tokens, period))
        if len(matches) != 1:
            state: Literal["TARGET_ROW_NOT_FOUND", "DUPLICATE_TARGET_ROW"] = (
                "TARGET_ROW_NOT_FOUND" if not matches else "DUPLICATE_TARGET_ROW"
            )
            return FullMarketSelectionOutcome(state, state, original, ABSENT, count, len(matches))
        ordinal, values, tokens, period = matches[0]
        amount = _amount(values[5], manifest.integer_policy)
        require(not isinstance(amount, NotEvaluated), "SOURCE_AMOUNT_UNKNOWN")
        extracted = ExtractedMonthlyRow(
            original.sha256,
            ordinal,
            HEADERS,
            values,
            tokens,
            values[2],
            period,
            values[5],
            amount,
            NotEvaluated("IC1", "EXACT_BYTE_SPAN_NOT_ESTABLISHED"),
        )
        body = canonical(
            {
                "selection_schema": POLICY,
                "original_sha256": original.sha256,
                "row_ordinal": ordinal,
                "company_code": spec.company_code,
                "reference_month": spec.reference_month,
                "headers": HEADERS,
                "source_fields": values,
                "source_tokens": tokens,
            }
        )
        selected = SelectedSourceRow(
            original, extracted, SelectionView(original, ordinal, body, sha256(body).hexdigest())
        )
        return FullMarketSelectionOutcome(
            "ROW_SELECTED", "EXACT_UNIQUE_SOURCE_ROW_ONLY", original, selected, count, 1
        )
    except (ContractError, UnicodeError) as exc:
        reason = str(exc) if isinstance(exc, ContractError) else "INVALID_UTF8_BYTES"
        return FullMarketSelectionOutcome(
            "EXTRACTION_REJECTED", reason, original, ABSENT, ABSENT, ABSENT
        )
