"""IC3 bounded, pure issuer-excerpt adjudication; no publisher authentication.

The supported profile is an explicitly located UTF-8 minimal excerpt, not an
HTML/PDF scraper. Quotes must occur uniquely in the pinned body and match the
documented finite grammar below. Unsupported real layouts fail closed. Neither
supplied role/rights declarations nor content matching attest who authored bytes.
"""

import re
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Literal, cast

from pit_research_lab.domain.contracts import (
    ContractError,
    FieldOrigin,
    Known,
    NotEvaluated,
    OriginKnownValue,
    Record,
    Visibility,
    int64,
    require,
)
from pit_research_lab.domain.market_row_selection import (
    HEADERS,
    FullMarketSelectionSpec,
    SelectedSourceRow,
    canonical,
    select_market_row,
)
from pit_research_lab.domain.source_adapter import _amount
from pit_research_lab.domain.source_intake import (
    MAX_METADATA_BYTES,
    FilePin,
    IntakeResult,
    OfflineSourceManifest,
    json_object,
    text_value,
)

VERSION = "IC3-FINANCIAL-SEMANTICS-v0.1"
BUNDLE_VERSION = "IC3-SUPPORT-BUNDLE-v0.1"
EXCERPT_PROFILE = "IC3-LOCATED-MONTHLY-EXCERPT-v0.1"
CROSSWALK_PROFILE = "IC3-OWNER-SEMANTIC-CROSSWALK-v0.1"
ABSENT = NotEvaluated("IC3", "NOT_EVALUATED")
CLAIMS = tuple(f"IC3-C{n:02d}" for n in range(1, 9))
ROLES = (
    "ISSUER_OFFICIAL",
    "ISSUER_AUTHORED_DISTRIBUTOR",
    "RETRANSMISSION",
    "GOVERNMENT_REFERENCE",
    "THIRD_PARTY",
    "LOCAL_SEMANTIC_POLICY",
)
CANONICAL = (
    ("metric", "net_operating_revenue"),
    ("period_kind", "DURATION"),
    ("reporting_scope", "consolidated"),
    ("basis_ref", "BASIS-CONSOLIDATED-V1"),
    ("currency", "NTD"),
    ("canonical_unit", "NTD_thousands"),
)
SOURCE_COLUMNS = (
    ("company_code", HEADERS[2]),
    ("reference_period", HEADERS[1]),
    ("source_amount", HEADERS[5]),
)


def object_fields(value: object, keys: set[str]) -> dict[str, object]:
    require(type(value) is dict, "INVALID_OBJECT")
    result = cast(dict[str, object], value)
    require(set(result) == keys, "INVALID_FIELDS")
    return result


def integer(value: object) -> int:
    require(type(value) is int, "INVALID_INTEGER")
    result = cast(int, value)
    int64(result)
    return result


def file_pin(value: object) -> FilePin:
    data = object_fields(value, {"relative_path", "byte_length", "sha256"})
    pin = FilePin(
        text_value(data["relative_path"]),
        integer(data["byte_length"]),
        text_value(data["sha256"]),
    )
    require(0 < pin.byte_length <= MAX_METADATA_BYTES, "SUPPORT_SIZE_LIMIT")
    return pin


@dataclass(frozen=True)
class SourceBinding(Record):
    raw: FilePin
    row_ordinal: int
    company_code: str
    reference_month: str
    column_index: int
    column_name: str
    amount_lexeme: str
    amount: int
    view_sha256: str


def binding_for(row: SelectedSourceRow) -> SourceBinding:
    extracted = row.extracted
    require(type(extracted.amount) is int, "SOURCE_AMOUNT_UNRESOLVED")
    return SourceBinding(
        FilePin(row.original.relative_path, row.original.byte_length, row.original.sha256),
        extracted.row_ordinal,
        extracted.company_code,
        extracted.reference_period[0].isoformat()[:7],
        row.amount_column_index,
        row.amount_column_name,
        extracted.source_tokens[5],
        cast(int, extracted.amount),
        row.view.projection_sha256,
    )


def binding_json(binding: SourceBinding) -> dict[str, object]:
    data = asdict(binding)
    data.pop("schema_version")
    data["raw"].pop("schema_version")
    return data


def decode_binding(value: object) -> SourceBinding:
    data = object_fields(
        value,
        {
            "raw",
            "row_ordinal",
            "company_code",
            "reference_month",
            "column_index",
            "column_name",
            "amount_lexeme",
            "amount",
            "view_sha256",
        },
    )
    raw = object_fields(data["raw"], {"relative_path", "byte_length", "sha256"})
    return SourceBinding(
        FilePin(
            text_value(raw["relative_path"]), integer(raw["byte_length"]), text_value(raw["sha256"])
        ),
        integer(data["row_ordinal"]),
        text_value(data["company_code"]),
        text_value(data["reference_month"]),
        integer(data["column_index"]),
        text_value(data["column_name"]),
        text_value(data["amount_lexeme"]),
        integer(data["amount"]),
        text_value(data["view_sha256"]),
    )


@dataclass(frozen=True)
class EvidenceRights(Record):
    status: str
    allowed_uses: tuple[str, ...]
    covered_sha256: str
    source_ref: str
    terms_ref: str
    attribution: str
    evidence_text: str
    approval_ref: str


@dataclass(frozen=True)
class FinancialEvidencePin(Record):
    file: FilePin
    role: str
    issuer_origin_ref: str
    statement_ref: str
    acquisition_origin: str
    acquisition_text: str
    rights: EvidenceRights
    profile: str
    locators: tuple[tuple[str, str], ...]
    declarations: str = field(default="SUPPLIED_NOT_AUTHENTICATED; ACQUISITION_NON_PIT", init=False)


def decode_evidence(value: object, policy: bool = False) -> FinancialEvidencePin:
    data = object_fields(
        value,
        {
            "file",
            "role",
            "issuer_origin_ref",
            "statement_ref",
            "acquisition_origin",
            "acquisition_text",
            "rights",
            "profile",
            "locators",
        },
    )
    rights = object_fields(
        data["rights"],
        {
            "status",
            "allowed_uses",
            "covered_sha256",
            "source_ref",
            "terms_ref",
            "attribution",
            "evidence_text",
            "approval_ref",
        },
    )
    uses = rights["allowed_uses"]
    require(type(uses) is list, "INVALID_ALLOWED_USES")
    permission = EvidenceRights(
        text_value(rights["status"]),
        tuple(text_value(v) for v in cast(list[object], uses)),
        *(
            text_value(rights[k])
            for k in (
                "covered_sha256",
                "source_ref",
                "terms_ref",
                "attribution",
                "evidence_text",
                "approval_ref",
            )
        ),
    )
    locators = object_fields(
        data["locators"], set() if policy else {"identity", "sales", "unit", "scope"}
    )
    pin = FinancialEvidencePin(
        file_pin(data["file"]),
        text_value(data["role"]),
        text_value(data["issuer_origin_ref"]),
        text_value(data["statement_ref"]),
        text_value(data["acquisition_origin"]),
        text_value(data["acquisition_text"]),
        permission,
        text_value(data["profile"]),
        tuple(sorted((key, text_value(val)) for key, val in locators.items())),
    )
    require(pin.role in ROLES, "UNSUPPORTED_EVIDENCE_ROLE")
    require((pin.role == "LOCAL_SEMANTIC_POLICY") == policy, "EVIDENCE_ROLE_COLLISION")
    require(
        pin.profile == (CROSSWALK_PROFILE if policy else EXCERPT_PROFILE),
        "UNSUPPORTED_EVIDENCE_PROFILE",
    )
    return pin


def preflight_evidence(pin: FinancialEvidencePin) -> None:
    """Supplied permission completeness only, performed before external-body reads."""
    rights = pin.rights
    require(
        rights.status == "PERMITTED"
        and rights.allowed_uses == ("OFFLINE_RESEARCH",)
        and rights.covered_sha256 == pin.file.sha256
        and rights.source_ref == pin.acquisition_origin
        and not rights.evidence_text.startswith(("https://", "http://"))
        and len(rights.evidence_text) >= 20,
        "EVIDENCE_RIGHTS_INCOMPLETE_OR_INAPPLICABLE",
    )
    require(
        pin.role == "GOVERNMENT_REFERENCE" or "data.gov.tw/license" not in rights.terms_ref,
        "GOVERNMENT_TERMS_DO_NOT_COVER_ISSUER_BODY",
    )


@dataclass(frozen=True)
class SupportManifest(Record):
    classification: str
    source_binding: SourceBinding
    issuer_name: str
    evidence: tuple[FinancialEvidencePin, ...]
    crosswalk: FinancialEvidencePin | None


def decode_support(body: bytes) -> SupportManifest:
    data = object_fields(
        json_object(body),
        {
            "support_schema",
            "classification",
            "source_binding",
            "issuer_name",
            "evidence",
            "crosswalk",
        },
    )
    require(data["support_schema"] == BUNDLE_VERSION, "UNSUPPORTED_SUPPORT_SCHEMA")
    require(
        data["classification"] in ("OWNER_SUPPLIED_EXTERNAL", "SYNTHETIC_TEST_ONLY"),
        "INVALID_SUPPORT_CLASSIFICATION",
    )
    entries = data["evidence"]
    require(
        type(entries) is list and 1 <= len(cast(list[object], entries)) <= 4, "EVIDENCE_COUNT_LIMIT"
    )
    evidence = tuple(decode_evidence(v) for v in cast(list[object], entries))
    crosswalk = None if data["crosswalk"] is None else decode_evidence(data["crosswalk"], True)
    all_pins = evidence + ((crosswalk,) if crosswalk else ())
    paths = tuple(p.file.relative_path for p in all_pins)
    require(
        len(set(paths)) == len(paths) and "support.json" not in paths,
        "EVIDENCE_ROLE_PATH_COLLISION",
    )
    for pin in all_pins:
        preflight_evidence(pin)
    return SupportManifest(
        text_value(data["classification"]),
        decode_binding(data["source_binding"]),
        text_value(data["issuer_name"]),
        evidence,
        crosswalk,
    )


@dataclass(frozen=True)
class SupportInput(Record):
    manifest_bytes: bytes | NotEvaluated = ABSENT
    bodies: tuple[tuple[str, bytes], ...] = ()
    reason: str = "SUPPORT_INPUT_PENDING"
    read_attempts: tuple[str, ...] = ()


@dataclass(frozen=True)
class IssuerSemanticSupport(Record):
    evidence_pin: FinancialEvidencePin
    issuer_name: Known[str]
    issuer_code: Known[str]
    reporting_month: Known[str]
    monthly_amount: Known[int]
    metric_wording: Known[str]
    currency: Known[str]
    magnitude: Known[str]
    scope: Known[str]
    measurement: Known[str]
    assurance: Known[str]
    evidence_group_key: str
    interpretation: str = field(
        default="CONTENT_MATCHED_SUPPLIED_ISSUER_CLAIM; NOT_AUTHENTICATED", init=False
    )


def checked_body(pin: FinancialEvidencePin, bodies: tuple[tuple[str, bytes], ...]) -> bytes:
    preflight_evidence(pin)
    matches = tuple(body for path, body in bodies if path == pin.file.relative_path)
    require(len(matches) == 1, "MISSING_OR_DUPLICATE_SUPPORT_BYTES")
    body = matches[0]
    require(
        len(body) == pin.file.byte_length and sha256(body).hexdigest() == pin.file.sha256,
        "EVIDENCE_PIN_MISMATCH",
    )
    return body


def parse_support(pin: FinancialEvidencePin, body: bytes, synthetic: bool) -> IssuerSemanticSupport:
    require(pin.role in ROLES[:3], "ISSUER_AUTHORSHIP_NOT_SUPPORTED")
    require(synthetic == (b"SYNTHETIC_TEST_ONLY" in body), "SYNTHETIC_CLASSIFICATION_MISMATCH")
    try:
        text = body.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ContractError("INVALID_SUPPORT_UTF8") from exc
    require(not any(ord(c) < 32 and c not in "\r\n\t" for c in text), "INVALID_SUPPORT_TEXT")
    quotes = dict(pin.locators)
    for quote in quotes.values():
        require(0 < len(quote) <= 1024 and text.count(quote) == 1, "QUOTE_NOT_UNIQUELY_ANCHORED")
    require(
        all(
            line in quotes.values() or line == "SYNTHETIC_TEST_ONLY"
            for line in text.splitlines()
            if line
        ),
        "UNSUPPORTED_OR_ADDITIONAL_STATEMENT",
    )
    patterns = {
        "identity": r"([^\r\n()]+) \(TWSE: ([0-9]{1,10})\)",
        "sales": r"([0-9]{4}-[0-9]{2}) (unaudited|audited) (monthly|year-to-date|point-in-time) (net sales|gross sales|assets): ([+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+))",
        "unit": r"All figures are in (thousands|millions|units) of (New Taiwan Dollars|US Dollars)\.",
        "scope": r"All figures are (consolidated|standalone|separate)\.",
    }
    parsed: dict[str, tuple[str, ...]] = {}
    for name, pattern in patterns.items():
        match = re.fullmatch(pattern, quotes[name])
        require(match is not None, "UNSUPPORTED_ANCHORED_STATEMENT")
        assert match is not None
        parsed[name] = match.groups()
    identity, sales, unit, scope = (parsed[k] for k in ("identity", "sales", "unit", "scope"))
    value = _amount(
        sales[4], "SIGNED_GROUPED_INT64-v0.1" if "," in sales[4] else "SIGNED_DECIMAL_INT64-v0.1"
    )
    require(type(value) is int, "SUPPORT_AMOUNT_UNRESOLVED")
    amount = cast(int, value)
    origin = FieldOrigin(
        Visibility.AUDIT,
        "/ic3/located_excerpt",
        OriginKnownValue(pin.statement_ref),
        OriginKnownValue(EXCERPT_PROFILE),
        OriginKnownValue(pin.file.sha256),
    )
    # Grouping describes supplied common origin, never independent publisher attestation.
    group = sha256(canonical([pin.issuer_origin_ref, pin.statement_ref])).hexdigest()
    return IssuerSemanticSupport(
        pin,
        Known(identity[0], origin),
        Known(identity[1], origin),
        Known(sales[0], origin),
        Known(amount, origin),
        Known(sales[3], origin),
        Known("NTD" if unit[1] == "New Taiwan Dollars" else "USD", origin),
        Known(unit[0], origin),
        Known(scope[0], origin),
        Known(sales[2], origin),
        Known(sales[1], origin),
        group,
    )


@dataclass(frozen=True)
class ClaimAssessment(Record):
    claim: str
    state: Literal["SUPPORTED", "UNRESOLVED", "CONTRADICTED", "NOT_EVALUATED"]
    reason: str
    source_refs: tuple[str, ...] = ()
    evidence_groups: tuple[str, ...] = ()
    contradicted_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class MappingCandidate(Record):
    body: bytes
    sha256: str
    status: str = field(default="PROPOSED_NOT_INSTALLED_RESEARCH_ONLY", init=False)


@dataclass(frozen=True)
class FinancialSemanticAssessment(Record):
    selected: SelectedSourceRow | NotEvaluated
    claims: tuple[ClaimAssessment, ...]
    support_input: str
    semantics: str
    mapping: str
    reason: str
    supports: tuple[IssuerSemanticSupport, ...] = ()
    candidate: MappingCandidate | NotEvaluated = ABSENT
    policy_sha256: str | NotEvaluated = ABSENT


def withheld(
    selected: SelectedSourceRow | NotEvaluated, status: str, reason: str
) -> FinancialSemanticAssessment:
    return FinancialSemanticAssessment(
        selected,
        tuple(ClaimAssessment(c, "UNRESOLVED", reason) for c in CLAIMS),
        status,
        "SEMANTICS_PARTIALLY_SUPPORTED",
        "MAPPING_UNRESOLVED",
        reason,
    )


def _crosswalk(
    body: bytes, manifest: SupportManifest, supports: tuple[IssuerSemanticSupport, ...]
) -> None:
    data = object_fields(
        json_object(body),
        {
            "policy_schema",
            "policy_ref",
            "owner_approval_ref",
            "rationale",
            "classification",
            "source_binding",
            "issuer_name",
            "issuer_ref",
            "support_sha256s",
            "source_metric",
            "source_assurance",
            "target",
            "basis_interpretation",
        },
    )
    require(data["policy_schema"] == CROSSWALK_PROFILE, "UNSUPPORTED_CROSSWALK_SCHEMA")
    for key in ("policy_ref", "owner_approval_ref", "issuer_ref"):
        text_value(data[key])
    rationale = text_value(data["rationale"])
    require(
        len(rationale) >= 40 and not rationale.startswith(("http://", "https://")),
        "CROSSWALK_JUSTIFICATION_MISSING",
    )
    require(
        data["classification"] == manifest.classification
        and decode_binding(data["source_binding"]) == manifest.source_binding
        and data["issuer_name"] == manifest.issuer_name,
        "CROSSWALK_SCOPE_MISMATCH",
    )
    require(
        data["support_sha256s"] == sorted({s.evidence_pin.file.sha256 for s in supports}),
        "CROSSWALK_SUPPORT_MISMATCH",
    )
    require(
        data["source_metric"] == "unaudited monthly net sales"
        and data["source_assurance"] == "unaudited"
        and data["target"] == dict(CANONICAL)
        and data["basis_interpretation"]
        == "OWNER_GOVERNED_RESEARCH_EQUIVALENCE_NOT_AUDIT_OR_GAAP_PROOF",
        "CROSSWALK_SEMANTICS_INCOMPATIBLE",
    )


def assess_financial_semantics(
    intake: IntakeResult,
    spec: FullMarketSelectionSpec,
    selected: SelectedSourceRow,
    supplied: SupportInput,
) -> FinancialSemanticAssessment:
    """Recompute IC1 selection and every support claim. Never accept a READY/claim DTO."""
    actual = select_market_row(intake, spec)
    if (
        actual.state != "ROW_SELECTED"
        or actual.selected != selected
        or not isinstance(selected, SelectedSourceRow)
        or any(
            type(n) is not int
            for n in (
                selected.extracted.row_ordinal,
                selected.extracted.amount,
                selected.original.byte_length,
                selected.view.row_ordinal,
            )
        )
    ):
        return withheld(
            ABSENT, "EVIDENCE_RESTRICTED_OR_UNVERIFIED", "SOURCE_SELECTION_BINDING_REJECTED"
        )
    assert isinstance(intake.manifest, OfflineSourceManifest)
    synthetic = intake.manifest.data_classification == "SYNTHETIC_TEST_ONLY"
    binding = binding_for(selected)
    if (
        synthetic
        and binding.raw.sha256 == "754761b82a8a7ec9f6146cdaaaa415e1a8d609fec3222da0002ab93eea44ccfd"
    ):
        return withheld(
            ABSENT, "EVIDENCE_RESTRICTED_OR_UNVERIFIED", "REAL_BYTES_CANNOT_BE_SYNTHETIC"
        )
    if not synthetic and (
        binding.raw.sha256 != "754761b82a8a7ec9f6146cdaaaa415e1a8d609fec3222da0002ab93eea44ccfd"
        or binding.company_code != "2303"
        or binding.reference_month != "2026-09"
        or binding.row_ordinal != 267
        or binding.amount != 25350431
        or binding.amount_lexeme != '"25350431"'
        or binding.column_index != 5
        or binding.column_name != HEADERS[5]
    ):
        return withheld(
            ABSENT, "EVIDENCE_RESTRICTED_OR_UNVERIFIED", "OUTSIDE_IC3_REAL_SOURCE_SCOPE"
        )
    if not isinstance(supplied.manifest_bytes, bytes):
        status = (
            "SUPPORT_INPUT_PENDING"
            if supplied.reason == "SUPPORT_INPUT_PENDING"
            else "EVIDENCE_RESTRICTED_OR_UNVERIFIED"
        )
        return withheld(selected, status, supplied.reason)
    try:
        manifest = decode_support(supplied.manifest_bytes)
        require(manifest.source_binding == binding, "SUPPORT_SOURCE_BINDING_MISMATCH")
        require(
            (manifest.classification == "SYNTHETIC_TEST_ONLY") == synthetic,
            "SOURCE_SUPPORT_CLASSIFICATION_MISMATCH",
        )
        require(
            synthetic or manifest.issuer_name in ("United Microelectronics Corporation", "聯電"),
            "OUTSIDE_IC3_ISSUER_SCOPE",
        )
        pins = manifest.evidence + ((manifest.crosswalk,) if manifest.crosswalk else ())
        require(
            sorted(p.file.relative_path for p in pins) == sorted(p for p, _ in supplied.bodies),
            "SUPPORT_BODY_SET_MISMATCH",
        )
        supports = tuple(
            parse_support(p, checked_body(p, supplied.bodies), synthetic) for p in manifest.evidence
        )
        # Identical text with conflicting claimed upstream identities cannot manufacture independence.
        for left in supports:
            for right in supports:
                require(
                    (
                        left.evidence_pin.file.sha256 != right.evidence_pin.file.sha256
                        and left.evidence_pin.locators != right.evidence_pin.locators
                    )
                    or left.evidence_group_key == right.evidence_group_key,
                    "CONTRADICTORY_COMMON_ORIGIN_DECLARATIONS",
                )
    except ContractError as exc:
        return withheld(selected, "EVIDENCE_RESTRICTED_OR_UNVERIFIED", str(exc))
    refs = tuple(sorted({s.evidence_pin.file.sha256 for s in supports}))
    groups = tuple(sorted({s.evidence_group_key for s in supports}))
    claims: list[ClaimAssessment] = []
    for number in range(7):
        bad: set[str] = set()
        for s in supports:
            matches = (
                {
                    "issuer_code": s.issuer_code.value == binding.company_code,
                    "issuer_name": s.issuer_name.value == manifest.issuer_name,
                    "month": s.reporting_month.value == binding.reference_month,
                },
                {
                    "metric": s.metric_wording.value == "net sales",
                    "assurance": s.assurance.value == "unaudited",
                    "measurement": s.measurement.value == "monthly",
                    "month": s.reporting_month.value == binding.reference_month,
                    "issuer_code": s.issuer_code.value == binding.company_code,
                    "amount": s.monthly_amount.value == binding.amount,
                },
                {
                    "amount": s.monthly_amount.value == binding.amount,
                    "month": s.reporting_month.value == binding.reference_month,
                },
                {"currency": s.currency.value == "NTD"},
                {
                    "magnitude": s.magnitude.value == "thousands",
                    "currency": s.currency.value == "NTD",
                },
                {
                    "scope": s.scope.value == "consolidated",
                    "assurance": s.assurance.value == "unaudited",
                },
                {
                    "measurement": s.measurement.value == "monthly",
                    "metric": s.metric_wording.value == "net sales",
                    "month": s.reporting_month.value == binding.reference_month,
                },
            )[number]
            # Every claim concerns this issuer-month, including unit and scope.
            # A correct NTD statement about another issuer cannot support this row.
            matches.update(
                issuer_code=s.issuer_code.value == binding.company_code,
                issuer_name=s.issuer_name.value == manifest.issuer_name,
                month=s.reporting_month.value == binding.reference_month,
            )
            bad.update(key for key, matched in matches.items() if not matched)
        claims.append(
            ClaimAssessment(
                CLAIMS[number],
                "CONTRADICTED" if bad else "SUPPORTED",
                "CONTENT_CONTRADICTION" if bad else "CONDITIONAL_PUBLISHED_ISSUER_CLAIM",
                refs,
                groups,
                tuple(sorted(bad)),
            )
        )
    candidate: MappingCandidate | NotEvaluated = ABSENT
    policy_hash: str | NotEvaluated = ABSENT
    crosswalk = ClaimAssessment(CLAIMS[7], "UNRESOLVED", "OWNER_CANONICAL_CROSSWALK_MISSING")
    if manifest.crosswalk:
        policy_hash = manifest.crosswalk.file.sha256
        try:
            _crosswalk(checked_body(manifest.crosswalk, supplied.bodies), manifest, supports)
            crosswalk = ClaimAssessment(
                CLAIMS[7],
                "SUPPORTED",
                "SUPPLIED_OWNER_RESEARCH_POLICY_NOT_ACCOUNTING_PROOF",
                (policy_hash,),
            )
        except ContractError as exc:
            crosswalk = ClaimAssessment(CLAIMS[7], "UNRESOLVED", str(exc), (policy_hash,))
    claims.append(crosswalk)
    contradictory = any(c.state == "CONTRADICTED" for c in claims)
    complete = all(c.state == "SUPPORTED" for c in claims)
    if complete:
        data: dict[str, object] = dict(CANONICAL)
        data.update(
            mapping_schema="a06-field-mapping-v0.1",
            applies_to_raw_sha256=binding.raw.sha256,
            source_columns=dict(SOURCE_COLUMNS),
            issuer_code=binding.company_code,
            issuer_ref="IC3-RESEARCH-" + binding.company_code + "-" + binding.reference_month,
            support_class="SYNTHETIC_TEST_ONLY" if synthetic else "INDEPENDENT_SOURCE_METADATA",
            evidence_origin="IC3-CONTENT-PINS:" + ",".join(refs),
            evidence_text="Proposed owner-governed research equivalence; content pins "
            + ",".join(refs)
            + "; policy "
            + str(policy_hash)
            + "; not publisher authentication or audited GAAP proof.",
        )
        body = canonical(data)
        candidate = MappingCandidate(body, sha256(body).hexdigest())
    return FinancialSemanticAssessment(
        selected,
        tuple(claims),
        "CONTENT_PINS_VERIFIED_SUPPLIED_ORIGIN",
        "SEMANTICS_CONTRADICTED" if contradictory else "SEMANTICS_SUPPORTED_FOR_RESEARCH",
        "MAPPING_CANDIDATE_PREPARED" if complete else "MAPPING_UNRESOLVED",
        "CONDITIONAL_RESEARCH_ONLY",
        supports,
        candidate,
        policy_hash,
    )
