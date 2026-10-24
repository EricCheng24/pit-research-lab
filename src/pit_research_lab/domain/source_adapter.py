"""A06 strict bounded CSV extraction, separate from supplied semantic mapping."""

import calendar
import re
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from typing import Literal

from pit_research_lab.domain.contracts import ContractError, NotEvaluated, Record, int64, require
from pit_research_lab.domain.source_intake import (
    IntakeResult,
    OfflineSourceManifest,
    json_object,
    text_value,
    validate_source_manifest,
)

CSV_PROFILE = "A06_MONTHLY_REVENUE_CSV-v0.1"
REQUIRED_HEADERS = ("出表日期", "資料年月", "公司代號", "營業收入-當月營收")
MAX_FIELD_CHARS = 4096


@dataclass(frozen=True)
class ExtractedMonthlyRow(Record):
    raw_sha256: str
    row_ordinal: int
    headers: tuple[str, ...]
    source_fields: tuple[str, ...]
    source_tokens: tuple[str, ...]
    company_code: str
    reference_period: tuple[date, date]
    source_amount_text: str
    amount: int | NotEvaluated
    exact_byte_span: NotEvaluated


@dataclass(frozen=True)
class ExtractionResult(Record):
    state: Literal["EXTRACTED", "UNRESOLVED", "REJECTED", "NOT_EVALUATED"]
    reason: str
    rows: tuple[ExtractedMonthlyRow, ...]


@dataclass(frozen=True)
class MappingAssessment(Record):
    state: Literal["MAPPED", "UNRESOLVED", "REJECTED"]
    reason: str
    source_column_facts: tuple[tuple[str, str], ...]
    semantic_facts: tuple[tuple[str, str], ...]
    support_sha256: str | NotEvaluated
    scope: str = "CONDITIONAL_ON_SEPARATELY_PINNED_SUPPLIED_METADATA; NOT_ISSUER_AUTHENTICATION"


def _csv_records(text: str) -> tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]:
    """Strict quote-aware logical records; retain decoded fields AND raw lexemes.

    No byte-span assertion: multibyte UTF-8 and quoted multiline fields use the
    whole-file digest + logical data-record ordinal as the exact source locator.
    """
    require("\x00" not in text, "CSV_NUL_UNSUPPORTED")
    records: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    fields: list[str] = []
    tokens: list[str] = []
    value: list[str] = []
    state = "START"
    start = i = 0

    def end_field(end: int) -> None:
        require(len(value) <= MAX_FIELD_CHARS and len(fields) < 32, "CSV_FIELD_LIMIT")
        fields.append("".join(value))
        tokens.append(text[start:end])
        value.clear()

    while i < len(text):
        ch = text[i]
        require(len(value) <= MAX_FIELD_CHARS, "CSV_FIELD_LIMIT")
        if state == "QUOTED":
            if ch == '"':
                state = "CLOSED"
            else:
                value.append(ch)
            i += 1
            continue
        if state == "CLOSED" and ch == '"':
            value.append('"')
            state = "QUOTED"
            i += 1
            continue
        if ch in {",", "\n", "\r"}:
            end_field(i)
            if ch == ",":
                i += 1
            else:
                if ch == "\r":
                    require(text[i : i + 2] == "\r\n", "BARE_CR_RECORD_SEPARATOR")
                    i += 1
                records.append((tuple(fields), tuple(tokens)))
                require(len(records) <= 10_001, "CSV_RECORD_LIMIT")
                fields.clear()
                tokens.clear()
                i += 1
            state = "START"
            start = i
            continue
        require(state != "CLOSED", "CHARACTERS_AFTER_QUOTED_FIELD")
        if ch == '"':
            require(state == "START", "QUOTE_IN_UNQUOTED_FIELD")
            state = "QUOTED"
        else:
            value.append(ch)
            state = "UNQUOTED"
        i += 1
    require(state != "QUOTED", "UNCLOSED_QUOTED_FIELD")
    if fields or value or state == "CLOSED" or (text and text[-1] == ","):
        end_field(len(text))
        records.append((tuple(fields), tuple(tokens)))
    require(len(records) <= 10_001, "CSV_RECORD_LIMIT")
    return tuple(records)


def _period(token: str, policy: str) -> tuple[date, date]:
    if policy == "CE_YYYYMM-v0.1":
        require(re.fullmatch(r"[0-9]{6}", token) is not None, "INVALID_CE_PERIOD")
        year, month = int(token[:4]), int(token[4:])
    elif policy == "ROC_YYYMM_PLUS_1911-v0.1":
        require(
            re.fullmatch(r"[0-9]{5}", token) is not None and int(token[:3]) > 0,
            "INVALID_ROC_PERIOD",
        )
        year, month = int(token[:3]) + 1911, int(token[3:])
    else:
        raise ContractError("UNSUPPORTED_PERIOD_POLICY")
    require(1 <= year <= 9999 and 1 <= month <= 12, "INVALID_REFERENCE_MONTH")
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def _amount(token: str, policy: str) -> int | NotEvaluated:
    require(
        policy in {"SIGNED_DECIMAL_INT64-v0.1", "SIGNED_GROUPED_INT64-v0.1"},
        "UNSUPPORTED_INTEGER_POLICY",
    )
    if token in {"", "NA", "N/A", "null", "-"}:
        return NotEvaluated("A06", "SOURCE_AMOUNT_UNKNOWN")
    pattern = (
        r"-?(0|[1-9][0-9]*)"
        if policy == "SIGNED_DECIMAL_INT64-v0.1"
        else r"-?(0|[1-9][0-9]{0,2}(,[0-9]{3})*)"
    )
    require(len(token) <= 27 and re.fullmatch(pattern, token) is not None, "INVALID_INTEGER_TOKEN")
    value = int(token.replace(",", ""))
    int64(value)
    return value


def extract_monthly_rows(intake: IntakeResult) -> ExtractionResult:
    rows: list[ExtractedMonthlyRow] = []
    try:
        if not isinstance(intake.manifest, OfflineSourceManifest) or not isinstance(
            intake.raw_bytes, bytes
        ):
            return ExtractionResult("NOT_EVALUATED", "INTAKE_NOT_READY", ())
        manifest, raw = intake.manifest, intake.raw_bytes
        checked = validate_source_manifest(
            manifest, raw, intake.mapping_bytes if isinstance(intake.mapping_bytes, bytes) else None
        )
        if checked != intake or checked.disposition != "SOURCE_SNAPSHOT_ACCEPTED_FOR_OFFLINE_PARSE":
            return ExtractionResult("NOT_EVALUATED", "INTAKE_GATE_NOT_PASSED", ())
        require(manifest.csv_profile == CSV_PROFILE, "UNSUPPORTED_CSV_PROFILE")
        require(manifest.encoding in {"UTF8", "UTF8_BOM"}, "UNSUPPORTED_ENCODING")
        bom = raw.startswith(b"\xef\xbb\xbf")
        require(bom == (manifest.encoding == "UTF8_BOM"), "ENCODING_PROFILE_MISMATCH")
        text = (raw[3:] if bom else raw).decode("utf-8", errors="strict")
        records = _csv_records(text)
        require(bool(records), "CSV_HEADER_MISSING")
        headers = records[0][0]
        require(
            headers == manifest.headers
            and len(headers) == len(set(headers))
            and all(headers)
            and set(REQUIRED_HEADERS) <= set(headers),
            "INVALID_OR_DUPLICATE_CSV_HEADERS",
        )
        require(
            re.fullmatch(r"[0-9]{1,10}", manifest.company_code) is not None
            and type(manifest.year) is int
            and 1 <= manifest.year <= 9999
            and type(manifest.quarter) is int
            and 1 <= manifest.quarter <= 4,
            "INVALID_SELECTED_SCOPE",
        )
        # Validate policies even for an empty file or unknown source amount.
        require(
            manifest.period_policy in {"CE_YYYYMM-v0.1", "ROC_YYYMM_PLUS_1911-v0.1"},
            "UNSUPPORTED_PERIOD_POLICY",
        )
        _amount("0", manifest.integer_policy)
        for ordinal, (values, tokens) in enumerate(records[1:], 1):
            require(len(values) == len(headers), "CSV_FIELD_COUNT_MISMATCH")
            fields = dict(zip(headers, values, strict=True))
            require(fields["公司代號"] == manifest.company_code, "OUT_OF_SCOPE_COMPANY")
            period = _period(fields["資料年月"], manifest.period_policy)
            require(
                period[0].year == manifest.year
                and (period[0].month - 1) // 3 + 1 == manifest.quarter,
                "OUT_OF_SCOPE_REFERENCE_MONTH",
            )
            amount = _amount(fields["營業收入-當月營收"], manifest.integer_policy)
            rows.append(
                ExtractedMonthlyRow(
                    sha256(raw).hexdigest(),
                    ordinal,
                    headers,
                    values,
                    tokens,
                    fields["公司代號"],
                    period,
                    fields["營業收入-當月營收"],
                    amount,
                    NotEvaluated("A06", "EXACT_BYTE_SPAN_NOT_ESTABLISHED"),
                )
            )
        months = tuple(row.reference_period[0] for row in rows)
        require(len(months) == len(set(months)), "DUPLICATE_COMPANY_MONTH_ROW")
        if len(rows) != 3 or any(isinstance(row.amount, NotEvaluated) for row in rows):
            return ExtractionResult(
                "UNRESOLVED", "REQUIRED_MONTH_OR_SOURCE_AMOUNT_MISSING", tuple(rows)
            )
        return ExtractionResult("EXTRACTED", "RAW_FIELDS_EXTRACTED_NOT_AUTHENTICATED", tuple(rows))
    except (ContractError, UnicodeError) as exc:
        reason = str(exc) if isinstance(exc, ContractError) else "INVALID_UTF8_BYTES"
        return ExtractionResult("REJECTED", reason, tuple(rows))


def assess_mapping(intake: IntakeResult, extraction: ExtractionResult) -> MappingAssessment:
    missing = NotEvaluated("A06", "NO_MAPPING_SUPPORT")
    columns = (
        ("公司代號", "SOURCE_REPORTED_COMPANY_CODE"),
        ("資料年月", "REFERENCE_PERIOD_ONLY"),
        ("營業收入-當月營收", "SOURCE_REPORTED_SIGNED_INTEGER"),
        ("出表日期", "SOURCE_TABLE_DATE_TEXT_ONLY"),
    )
    if extraction != extract_monthly_rows(intake) or extraction.state != "EXTRACTED":
        return MappingAssessment(
            "UNRESOLVED", "EXTRACTION_NOT_COMPLETE_OR_TRANSPORT_MISMATCH", columns, (), missing
        )
    manifest = intake.manifest
    assert isinstance(manifest, OfflineSourceManifest)
    if manifest.mapping_file is None or not isinstance(intake.mapping_bytes, bytes):
        return MappingAssessment(
            "UNRESOLVED", "INDEPENDENT_FIELD_MAPPING_METADATA_MISSING", columns, (), missing
        )
    support_digest = sha256(intake.mapping_bytes).hexdigest()
    try:
        support = json_object(intake.mapping_bytes)
        names = {
            "issuer_code",
            "issuer_ref",
            "metric",
            "period_kind",
            "reporting_scope",
            "basis_ref",
            "currency",
            "canonical_unit",
        }
        require(
            set(support)
            == names
            | {
                "mapping_schema",
                "applies_to_raw_sha256",
                "evidence_origin",
                "evidence_text",
                "support_class",
                "source_columns",
            },
            "INVALID_MAPPING_METADATA_SCHEMA",
        )
        require(
            support["mapping_schema"] == "a06-field-mapping-v0.1"
            and support["applies_to_raw_sha256"] == manifest.raw.sha256,
            "MAPPING_METADATA_RAW_MISMATCH",
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
            support["support_class"] == "INDEPENDENT_SOURCE_METADATA"
            or (
                support["support_class"] == "SYNTHETIC_TEST_ONLY"
                and manifest.data_classification == "SYNTHETIC_TEST_ONLY"
            ),
            "MAPPING_INDEPENDENCE_NOT_ESTABLISHED",
        )
        text_value(support["evidence_origin"])
        explanation = text_value(support["evidence_text"])
        require(not explanation.startswith(("http://", "https://")), "MAPPING_EXPLANATION_MISSING")
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
            all(support[k] == v for k, v in expected.items()),
            "UNSUPPORTED_OR_INCOMPATIBLE_FIELD_MAPPING",
        )
        require(bool(text_value(support["issuer_ref"])), "ISSUER_MAPPING_UNKNOWN")
        facts = tuple(sorted((k, text_value(support[k])) for k in names))
        return MappingAssessment(
            "MAPPED", "CONDITIONAL_SUPPLIED_METADATA_MAPPING", columns, facts, support_digest
        )
    except ContractError as exc:
        return MappingAssessment("REJECTED", str(exc), columns, (), support_digest)
