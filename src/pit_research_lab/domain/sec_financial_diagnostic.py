"""RS3F pure, original-linked research diagnostic. No canonical or PIT admission."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from hashlib import sha256

from pit_research_lab.domain.contracts import CodePin, Record, require
from pit_research_lab.domain.financial_semantics import (
    CLAIMS,
    ClaimAssessment,
    SourceBinding,
    binding_for,
)
from pit_research_lab.domain.issuer_html_extraction import (
    SEC_PROFILE,
    SEC_SHA,
    HtmlEvidenceObservation,
    HtmlProfileSpec,
    StructuralLocator,
    canonical,
)
from pit_research_lab.domain.market_row_selection import (
    FullMarketSelectionSpec,
    SelectedSourceRow,
    preflight_manifest,
    select_market_row,
)
from pit_research_lab.domain.source_intake import FilePin, decode_manifest, validate_source_manifest

SEC_PIN = FilePin("umc-ex99.htm", 58214, SEC_SHA)
SEC_SPEC = HtmlProfileSpec(
    SEC_PROFILE,
    "windows-1252",
    "SEC_PUBLIC_FILING",
    "OWNER_SUPPLIED_EXTERNAL",
    "United Microelectronics Corporation",
    "2026-09",
    "October 6, 2026",
    "25,350,431",
)
VIEW_SHA = "32b1a1bb9a4855167f2c1d1a07e5eef9f347ecd78875496fc87d17c1bf7c4520"
GOV_PIN = FilePin(
    "t187ap05_L.csv",
    205416,
    "754761b82a8a7ec9f6146cdaaaa415e1a8d609fec3222da0002ab93eea44ccfd",
)
MANIFEST_PIN = FilePin(
    "manifest.json",
    3984,
    "0481150d9015ce9937715ff139e471a7a8f4ca22cd79c995ed319c24040241ab",
)
SNAPSHOT = "A06-SNAPSHOT-9febd14574d935da4bfdaf7d3e9abf1f9988b0fa6ba07dfa4672c301d077944d"


def check_pin(body: bytes, pin: FilePin) -> None:
    require(
        type(body) is bytes
        and len(body) == pin.byte_length
        and sha256(body).hexdigest() == pin.sha256,
        "SOURCE_PIN_MISMATCH",
    )


@dataclass(frozen=True)
class CsvLocator(Record):
    row_ordinal: int
    column_index: int
    column_name: str
    exact_byte_span: str = field(default="BYTE_SPAN_NOT_ESTABLISHED", init=False)


@dataclass(frozen=True)
class FieldEvidence(Record):
    source_role: str
    source_sha256: str
    field_name: str
    status: str
    value: str | int | None
    locators: tuple[StructuralLocator | CsvLocator, ...]
    reason: str


@dataclass(frozen=True)
class NumericComparison(Record):
    sec_amount: int
    government_amount: int
    state: str
    unit_operation: str = field(default="NO_UNIT_OR_CURRENCY_CONVERSION", init=False)
    interpretation: str = field(
        default="NUMERIC_DIAGNOSTIC_ONLY; COMMON_ISSUER_ORIGIN; NOT_INDEPENDENT_AUTHENTICATION",
        init=False,
    )


def compare_amounts(sec: int, government: int) -> NumericComparison:
    require(type(sec) is int and type(government) is int, "AMOUNT_TYPE_MISMATCH")
    return NumericComparison(sec, government, "EQUAL" if sec == government else "CONTRADICTED")


@dataclass(frozen=True)
class FinancialDiagnostic(Record):
    source_pin: FilePin
    extraction_view_sha256: str
    government: SourceBinding
    manifest_pin: FilePin
    snapshot_ref: str
    fields: tuple[FieldEvidence, ...]
    comparison: NumericComparison
    claims: tuple[ClaimAssessment, ...]
    code_context: tuple[CodePin, ...]
    requested_cutoff: str | None
    diagnostic_only: bool = field(default=True, init=False)
    mapping: str = field(default="MAPPING_UNRESOLVED", init=False)
    ic3_r01: str = field(default="P2_OPEN", init=False)
    source_authentication: str = field(default="NOT_ESTABLISHED", init=False)
    historic_PIT: str = field(default="NOT_ESTABLISHED", init=False)
    cutoff_availability: str = field(default="UNRESOLVED", init=False)
    evidence_time_semantics: str = field(
        default="DOCUMENT_ACQUISITION_APPROVAL_ALL_NON_PIT", init=False
    )
    trusted_pit: bool = field(default=False, init=False)
    admission_eligible: bool = field(default=False, init=False)
    agent_observation: str = field(default="NOT_PRODUCED", init=False)
    golden: str = field(default="NOT_GRANTED", init=False)
    owner_results: tuple[tuple[str, str], ...] = field(
        default=tuple(
            (o, "NOT_EVALUATED / UNSUPPORTED_EXTERNAL_SOURCE_SCHEMA")
            for o in ("S1", "S2", "S3", "A04", "A05")
        ),
        init=False,
    )
    interpretation: str = field(
        default="RS3F_FINANCIAL_SEMANTICS_RESEARCH_DIAGNOSTIC-v0.1", init=False
    )

    def serialize(self) -> bytes:
        return canonical(asdict(self))

    @property
    def sha256(self) -> str:
        return sha256(self.serialize()).hexdigest()

    @property
    def research_ref(self) -> str:
        return "RS3F-RESEARCH-" + self.sha256


def _check_observation(observation: HtmlEvidenceObservation) -> None:
    """Bind every used DTO field to the fixed independently reproduced RS2 view.

    This is content consistency, not authentication of a caller or live process.
    The outer controller obtains the observation directly from extract_html.
    """
    require(type(observation) is HtmlEvidenceObservation, "INVALID_SEC_OBSERVATION")
    require(
        observation.source_pin == SEC_PIN and observation.specification == SEC_SPEC,
        "SEC_OBSERVATION_SCOPE_MISMATCH",
    )
    view = observation.view
    require(
        sha256(view.canonical_view_bytes).hexdigest() == view.generated_view_sha256 == VIEW_SHA,
        "EXTRACTION_VIEW_MISMATCH",
    )
    data = json.loads(view.canonical_view_bytes)
    pairs = (
        ("original_amount_lexeme", observation.original_amount_lexeme),
        ("generated_parsed_amount_text", observation.parsed_amount_text),
        ("unit_heading", observation.unit_heading),
        ("section_locator", asdict(observation.section_locator)),
        ("table_locator", asdict(observation.table_locator)),
        ("claim_locators", [asdict(v) for v in observation.claim_locators]),
        ("code_pins", [asdict(v) for v in observation.code_pins]),
        ("unobserved_claims", observation.unobserved_claims),
        (
            "excluded_comparison",
            asdict(observation.exclusions[0]) if len(observation.exclusions) == 2 else None,
        ),
        (
            "excluded_ytd",
            asdict(observation.exclusions[1]) if len(observation.exclusions) == 2 else None,
        ),
    )
    require(
        all(canonical(data[k]) == canonical(v) for k, v in pairs),
        "SEC_OBSERVATION_VIEW_BINDING_MISMATCH",
    )


def build_diagnostic(
    observation: HtmlEvidenceObservation,
    manifest_body: bytes,
    government_body: bytes,
    code_context: tuple[CodePin, ...],
    *,
    claimed_selection: SelectedSourceRow | None = None,
    cutoff: str | None = None,
) -> FinancialDiagnostic:
    """Recompute IC1 from exact originals; no caller READY/selected DTO promotion."""
    _check_observation(observation)
    check_pin(manifest_body, MANIFEST_PIN)
    check_pin(government_body, GOV_PIN)
    if cutoff is not None:
        require(type(cutoff) is str, "INVALID_CUTOFF")
        try:
            parsed_cutoff = datetime.fromisoformat(cutoff)
        except ValueError as exc:
            raise ValueError("INVALID_CUTOFF") from exc
        require(parsed_cutoff.tzinfo is not None, "CUTOFF_REQUIRES_TIMEZONE")
    manifest = decode_manifest(manifest_body)
    require(
        manifest.raw == GOV_PIN
        and manifest.mapping_file is None
        and manifest.snapshot_ref == SNAPSHOT,
        "GOVERNMENT_SCOPE_MISMATCH",
    )
    require(
        preflight_manifest(manifest).reason == "RIGHTS_PREFLIGHT_PASSED",
        "GOVERNMENT_RIGHTS_PREFLIGHT_FAILED",
    )
    intake = validate_source_manifest(manifest, government_body, None)
    selection = select_market_row(intake, FullMarketSelectionSpec())
    require(
        selection.state == "ROW_SELECTED" and isinstance(selection.selected, SelectedSourceRow),
        "GOVERNMENT_SELECTION_FAILED",
    )
    selected = selection.selected
    assert isinstance(selected, SelectedSourceRow)
    binding = binding_for(selected)
    require(
        type(binding.amount) is int
        and type(binding.row_ordinal) is int
        and binding.raw == GOV_PIN
        and binding.row_ordinal == 267
        and binding.company_code == "2303"
        and binding.reference_month == "2026-09"
        and binding.amount == 25350431
        and binding.amount_lexeme == '"25350431"',
        "GOVERNMENT_SELECTION_BINDING_MISMATCH",
    )
    require(
        claimed_selection is None
        or (
            type(claimed_selection) is SelectedSourceRow
            and claimed_selection == selected
            and type(claimed_selection.extracted.amount) is int
            and type(claimed_selection.extracted.row_ordinal) is int
        ),
        "FORGED_OR_STALE_SELECTION",
    )
    locators = {v.purpose: v for v in observation.claim_locators}
    fields = []
    for name, value, purpose, status in (
        ("issuer_name", SEC_SPEC.issuer_name, "ISSUER_NAME", "OBSERVED_IN_SEC"),
        ("reference_month", "2026-09", "REPORTING_PERIOD", "OBSERVED_IN_SEC"),
        ("metric_wording", "Net sales", "TARGET_AMOUNT", "OBSERVED_IN_SEC"),
        ("amount", 25350431, "TARGET_AMOUNT", "OBSERVED_IN_SEC"),
        ("unit_heading", "NT$ Thousand", "UNIT_HEADING", "OBSERVED_IN_SEC"),
        (
            "document_stated_date",
            SEC_SPEC.document_date_label,
            "DOCUMENT_DATE_NON_PIT",
            "OBSERVED_NON_PIT",
        ),
    ):
        fields.append(
            FieldEvidence(
                "SEC_PUBLIC_FILING",
                SEC_PIN.sha256,
                name,
                status,
                value,
                (locators[purpose],),
                "EXHIBIT_99_2_STATIC_SOURCE_OBSERVATION",
            )
        )
    for name in (
        "TWSE_code",
        "unaudited",
        "consolidated",
        "canonical_basis_equivalence",
        "historical_publication_availability",
    ):
        fields.append(
            FieldEvidence(
                "SEC_PUBLIC_FILING",
                SEC_PIN.sha256,
                name,
                "NOT_ESTABLISHED_BY_SEC",
                None,
                (observation.section_locator,),
                "NO_SUPPORT_IN_EXHIBIT_99_2",
            )
        )
    for name, value, column in (
        ("TWSE_code", binding.company_code, 2),
        ("issuer_name", selected.extracted.source_fields[3], 3),
        ("reference_month", binding.reference_month, 1),
        ("amount", binding.amount, 5),
    ):
        fields.append(
            FieldEvidence(
                "GOVERNMENT_AGGREGATE",
                GOV_PIN.sha256,
                name,
                "OBSERVED_IN_GOVERNMENT_ROW",
                value,
                (CsvLocator(267, column, selected.extracted.headers[column]),),
                "SOURCE_SPECIFIC_ONLY_NO_SEC_SCOPE_LEAKAGE",
            )
        )
    fields.append(
        FieldEvidence(
            "GOVERNMENT_AGGREGATE",
            GOV_PIN.sha256,
            "declared_amount_scale",
            "SOURCE_SPECIFIC_DECLARATION_NOT_AUTHENTICATED",
            "NTD thousands",
            (CsvLocator(267, 5, binding.column_name),),
            "APPROVED_SOURCE_CONTEXT; NO_CANONICAL_CROSSWALK",
        )
    )
    missing = (
        "SEC_TWSE_CODE_NOT_OBSERVED; ISSUER_CODE_EQUIVALENCE_UNRESOLVED",
        "SEC_TWSE_CODE_AND_UNAUDITED_NOT_OBSERVED; METRIC_EQUIVALENCE_UNRESOLVED",
        "NUMERIC_EQUALITY_ONLY; SEC_TWSE_CODE_NOT_OBSERVED",
        "LITERAL_NT$_ONLY; ISSUER_CODE_AND_CANONICAL_CURRENCY_UNRESOLVED",
        "LITERAL_THOUSAND_ONLY; ISSUER_CODE_AND_CANONICAL_UNIT_UNRESOLVED",
        "SEC_CONSOLIDATED_AND_UNAUDITED_NOT_OBSERVED; BASIS_UNRESOLVED",
        "MONTHLY_NET_SALES_OBSERVED; ISSUER_CODE_NOT_OBSERVED",
        "OWNER_SEMANTIC_CROSSWALK_MISSING; IC3_R01_P2_OPEN; SOURCE_USE_IS_NOT_SEMANTIC_POLICY",
    )
    claims = tuple(
        ClaimAssessment(c, "UNRESOLVED", reason, (SEC_PIN.sha256, GOV_PIN.sha256))
        for c, reason in zip(CLAIMS, missing, strict=True)
    )
    return FinancialDiagnostic(
        SEC_PIN,
        VIEW_SHA,
        binding,
        MANIFEST_PIN,
        SNAPSHOT,
        tuple(fields),
        compare_amounts(int(observation.parsed_amount_text.replace(",", "")), binding.amount),
        claims,
        code_context,
        cutoff,
    )
