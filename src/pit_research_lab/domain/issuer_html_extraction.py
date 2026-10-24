"""RS2 inert, source-specific HTML observations; never source or rights admission.

No filesystem, clock or network I/O. Mutable parser nodes are private temporary
state; every returned record and generated representation is immutable. The BW
profile is deliberately synthetic-only and cannot admit a captured real release.
"""

import html
import json
import re
from array import array
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from html.entities import html5
from html.parser import HTMLParser

from pit_research_lab.domain.contracts import CodePin, ContractError, NotEvaluated, Record, require
from pit_research_lab.domain.source_adapter import _amount
from pit_research_lab.domain.source_intake import FilePin

SEC_PROFILE = "SEC-EX99_2-SAVEDHTML"
BW_PROFILE = "BW-PRIMARY-STORY-SYNTHETIC-ONLY"
VERSION = "v0.1"
CODE_PATHS = (
    "src/pit_research_lab/domain/issuer_html_extraction.py",
    "src/pit_research_lab/domain/issuer_html_slice.py",
)
MAX_BODY = 1_048_576
MAX_NODES = 5000
MAX_DEPTH = 256
MAX_ROWS = 256
MAX_COLUMNS = 16
BW_SHA = "67bd462b2035729e279905615f03e0918fa81146e13307c8d2c325dcbc148607"
SEC_SHA = "058a7553584e93b80291e059e007a3a4a1a15ef909b9e81affd27796a442abf4"
VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
EXCLUDED = frozenset("script style template noscript iframe object svg embed".split())
ABSENT = NotEvaluated("RS2", "NOT_EVALUATED")
SEC_HEADER = ("Period", "Items", "2026", "2025", "Changes", "%")
MONTHS = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def normalize(value: str) -> str:
    return re.sub(r"[ \t\r\n\f\v\xa0]+", " ", value).strip()


@dataclass(frozen=True)
class HtmlProfileSpec(Record):
    profile_id: str
    declared_encoding: str
    source_role: str
    classification: str
    issuer_name: str
    reference_month: str
    document_date_label: str
    expected_amount_text: str
    profile_version: str = VERSION


@dataclass(frozen=True)
class StructuralLocator(Record):
    purpose: str
    element_path: str
    original_element_start_tag_byte_offset: int
    predicates: tuple[tuple[str, str], ...] = ()
    exact_byte_span: str = field(default="BYTE_SPAN_NOT_ESTABLISHED", init=False)


@dataclass(frozen=True)
class ExcludedCell(Record):
    reason: str
    original_lexeme: str
    parsed_text: str
    locator: StructuralLocator


@dataclass(frozen=True)
class ExtractionView(Record):
    canonical_view_bytes: bytes
    generated_view_sha256: str
    representation_kind: str = field(default="ADAPTER_GENERATED_HTML_EXTRACTION_VIEW", init=False)


@dataclass(frozen=True)
class ExtractionRefusal(Record):
    source_pin: FilePin
    specification: HtmlProfileSpec
    reason: str
    status: str = "STRUCTURAL_REFUSAL"
    generated_view: NotEvaluated = field(default=ABSENT, init=False)
    source_body: NotEvaluated = field(default=ABSENT, init=False)
    admission_eligible: bool = field(default=False, init=False)


@dataclass(frozen=True)
class HtmlEvidenceObservation(Record):
    source_pin: FilePin
    specification: HtmlProfileSpec
    code_pins: tuple[CodePin, ...]
    section_locator: StructuralLocator
    table_locator: StructuralLocator
    claim_locators: tuple[StructuralLocator, ...]
    original_amount_lexeme: str
    parsed_amount_text: str
    unit_heading: str
    exclusions: tuple[ExcludedCell, ...]
    unobserved_claims: tuple[str, ...]
    view: ExtractionView
    source_evidence_class: str = field(default="DOCUMENT_CONTENT_OBSERVED_UNADMITTED", init=False)
    source_authentication: str = field(default="NOT_ESTABLISHED", init=False)
    admission_eligible: bool = field(default=False, init=False)
    trust: str = field(default="NOT_TRUSTED_PIT_EVIDENCE", init=False)
    native_transport: str = field(default="UNSUPPORTED_EXTERNAL_SOURCE_SCHEMA", init=False)
    owner_results: tuple[tuple[str, NotEvaluated], ...] = field(
        default=tuple(
            (o, NotEvaluated(o, "NOT_EVALUATED")) for o in ("S1", "S2", "S3", "A04", "A05")
        ),
        init=False,
    )
    agent_observation: str = field(default="NOT_PRODUCED", init=False)
    mapping: str = field(default="MAPPING_UNRESOLVED", init=False)
    historical_publication_proof: NotEvaluated = field(default=ABSENT, init=False)


def real_bw_disabled(pin: FilePin, spec: HtmlProfileSpec) -> bool:
    return (
        pin.sha256 == BW_SHA
        or pin.relative_path.split("/")[-1] == "UMC Reports Sales for September 2026.html"
        or spec.source_role == "BUSINESS_WIRE"
        or (
            spec.profile_id == BW_PROFILE
            and (
                spec.classification != "SYNTHETIC_TEST_ONLY"
                or spec.source_role != "SYNTHETIC_ISSUER"
            )
        )
    )


def validate_spec(spec: HtmlProfileSpec, code: tuple[CodePin, ...]) -> None:
    require(
        spec.profile_id in (SEC_PROFILE, BW_PROFILE) and spec.profile_version == VERSION,
        "UNSUPPORTED_HTML_PROFILE",
    )
    require(tuple(p.path for p in code) == CODE_PATHS, "EXTRACTOR_CODE_LINK_MISMATCH")
    require(
        spec.classification in ("SYNTHETIC_TEST_ONLY", "OWNER_SUPPLIED_EXTERNAL"),
        "UNSUPPORTED_CLASSIFICATION",
    )
    require(
        spec.source_role
        == (
            "SYNTHETIC_ISSUER"
            if spec.classification == "SYNTHETIC_TEST_ONLY"
            else "SEC_PUBLIC_FILING"
        ),
        "UNSUPPORTED_SOURCE_ROLE",
    )
    require(
        spec.declared_encoding == ("windows-1252" if spec.profile_id == SEC_PROFILE else "UTF-8"),
        "UNSUPPORTED_ENCODING",
    )
    for text in (
        spec.issuer_name,
        spec.reference_month,
        spec.document_date_label,
        spec.expected_amount_text,
    ):
        require(
            type(text) is str and 0 < len(text) <= 256 and not any(ord(c) < 32 for c in text),
            "INVALID_PROFILE_SCOPE",
        )
    require(
        re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", spec.reference_month) is not None,
        "INVALID_REFERENCE_MONTH",
    )
    if spec.profile_id == SEC_PROFILE:
        require(
            spec.reference_month == "2026-09" and spec.document_date_label == "October 6, 2026",
            "UNSUPPORTED_SEC_PERIOD",
        )
    if spec.classification == "SYNTHETIC_TEST_ONLY":
        require(spec.issuer_name.startswith("SYNTHETIC_TEST_ONLY"), "SYNTHETIC_ISSUER_REQUIRED")
    else:
        require(spec.issuer_name == "United Microelectronics Corporation", "UNSUPPORTED_SEC_ISSUER")
    require(
        type(_amount(spec.expected_amount_text, "SIGNED_GROUPED_INT64-v0.1")) is int,
        "INVALID_EXPECTED_AMOUNT",
    )


@dataclass
class _Text:
    raw: str
    decoded: str


@dataclass(eq=False)
class _Node:
    tag: str
    attrs: tuple[tuple[str, str | None], ...]
    parent: "_Node | None"
    offset: int
    children: list["_Node | _Text"] = field(default_factory=list)


def _nodes(node: _Node) -> list[_Node]:
    result = []
    for child in node.children:
        if isinstance(child, _Node):
            result.append(child)
            result.extend(_nodes(child))
    return result


def _text(node: _Node) -> str:
    if node.tag in EXCLUDED:
        return ""
    return normalize(
        " ".join(c.decoded if isinstance(c, _Text) else _text(c) for c in node.children)
    )


class _Parser(HTMLParser):
    def __init__(self, source: str, encoding: str) -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        self.encoding = encoding
        self.lines = [0] + [m.end() for m in re.finditer("\n", source)]
        self.byte_positions = array("I", [0])
        total = 0
        for ch in source:
            total += len(ch.encode(encoding))
            self.byte_positions.append(total)
        self.root = _Node("#document", (), None, 0)
        self.stack = [self.root]
        self.elements: list[_Node] = []

    def _position(self) -> int:
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        require(len(self.elements) < MAX_NODES, "HTML_NODE_LIMIT")
        require(len(self.stack) <= MAX_DEPTH, "HTML_DEPTH_LIMIT")
        require(
            len(attrs) <= 128 and len(attrs) == len({key for key, _ in attrs}),
            "AMBIGUOUS_ATTRIBUTES",
        )
        start = self._position()
        raw = self.get_starttag_text()
        require(raw is not None, "START_OFFSET_NOT_VERIFIED")
        assert raw is not None
        require(self.source[start : start + len(raw)] == raw, "START_OFFSET_NOT_VERIFIED")
        node = _Node(tag, tuple(attrs), self.stack[-1], self.byte_positions[start])
        self.stack[-1].children.append(node)
        self.elements.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        require(
            tag not in VOID and len(self.stack) > 1 and self.stack[-1].tag == tag,
            "MALFORMED_HTML_NESTING",
        )
        self.stack.pop()

    def handle_data(self, data: str) -> None:
        require(not any(ord(c) < 32 and c not in "\t\r\n\f" for c in data), "INVALID_HTML_TEXT")
        self._append_text(data, data)

    def _append_text(self, raw: str, decoded: str) -> None:
        children = self.stack[-1].children
        if children and isinstance(children[-1], _Text):
            children[-1].raw += raw
            children[-1].decoded += decoded
        else:
            children.append(_Text(raw, decoded))

    def handle_entityref(self, name: str) -> None:
        require(name + ";" in html5, "UNSUPPORTED_HTML_ENTITY")
        self._reference("&" + name + ";")

    def handle_charref(self, name: str) -> None:
        try:
            number = int(name[1:], 16) if name[:1].lower() == "x" else int(name, 10)
        except ValueError as exc:
            raise ContractError("INVALID_HTML_ENTITY") from exc
        require(
            0 < number <= 0x10FFFF
            and not 0xD800 <= number <= 0xDFFF
            and (number >= 32 or number in (9, 10, 13)),
            "INVALID_HTML_ENTITY",
        )
        self._reference("&#" + name + ";")

    def _reference(self, raw: str) -> None:
        require(self.source.startswith(raw, self._position()), "MALFORMED_HTML_ENTITY")
        self._append_text(raw, html.unescape(raw))

    def handle_comment(self, data: str) -> None:
        self.stack[-1].children.append(
            _Node("#comment", (), self.stack[-1], self.byte_positions[self._position()])
        )

    def handle_decl(self, decl: str) -> None:
        require(decl.lower() == "doctype html", "UNSUPPORTED_HTML_DECLARATION")

    def unknown_decl(self, data: str) -> None:
        raise ContractError("UNSUPPORTED_HTML_DECLARATION")

    def handle_pi(self, data: str) -> None:
        raise ContractError("UNSUPPORTED_HTML_PROCESSING_INSTRUCTION")


def _one(nodes: list[_Node], reason: str) -> _Node:
    require(len(nodes) == 1, reason)
    return nodes[0]


def _path(node: _Node) -> str:
    parts = []
    while node.parent:
        siblings = [n for n in node.parent.children if isinstance(n, _Node) and n.tag == node.tag]
        parts.append(f"{node.tag}[{siblings.index(node) + 1}]")
        node = node.parent
    return "/" + "/".join(reversed(parts))


def _locator(node: _Node, purpose: str, **predicates: str) -> StructuralLocator:
    return StructuralLocator(purpose, _path(node), node.offset, tuple(sorted(predicates.items())))


def _critical(root: _Node) -> None:
    for node in [root, *_nodes(root)]:
        attrs = dict(node.attrs)
        require(
            node.tag not in EXCLUDED and node.tag != "#comment",
            "EXECUTABLE_OR_EXCLUDED_CRITICAL_NODE",
        )
        require(
            "hidden" not in attrs
            and (attrs.get("aria-hidden") or "").strip().lower() != "true"
            and re.search(
                r"display\s*:\s*none|visibility\s*:\s*hidden", attrs.get("style") or "", re.I
            )
            is None,
            "HIDDEN_CRITICAL_NODE",
        )
        style = (attrs.get("style") or "").lower()
        require(
            not any(token in style for token in ("\\", "/*", "expression(", "url(")),
            "UNSUPPORTED_CRITICAL_STYLE",
        )
        require(
            not any(key.startswith("on") or key == "srcdoc" for key, _ in node.attrs),
            "ACTIVE_CRITICAL_ATTRIBUTE",
        )
        for key, value in node.attrs:
            if key in ("href", "src", "action", "xlink:href") and value:
                compact = re.sub(r"\s+", "", value).lower()
                require(
                    not compact.startswith(("javascript:", "vbscript:", "data:", "file:")),
                    "UNSAFE_CRITICAL_LINK",
                )
        require(
            not (node.tag == "p" and any(n.tag in ("p", "table", "div") for n in _nodes(node))),
            "MIXED_CRITICAL_MARKUP",
        )


def _rows(table: _Node) -> list[list[_Node]]:
    require(not any(n.tag == "table" for n in _nodes(table)), "NESTED_SALES_TABLE")
    for node in _nodes(table):
        parent_tag = node.parent.tag if node.parent else ""
        if node.tag in ("td", "th"):
            require(parent_tag == "tr", "CELL_OUTSIDE_ROW")
        if node.tag == "tr":
            require(parent_tag in ("table", "thead", "tbody", "tfoot"), "ROW_OUTSIDE_TABLE_GROUP")
        if parent_tag in ("table", "thead", "tbody", "tfoot"):
            require(node.tag in ("tr", "thead", "tbody", "tfoot"), "UNSUPPORTED_TABLE_CHILD")
    rows = [n for n in _nodes(table) if n.tag == "tr"]
    require(0 < len(rows) <= MAX_ROWS, "TABLE_ROW_LIMIT")
    result = []
    for row in rows:
        cells = [n for n in row.children if isinstance(n, _Node) and n.tag in ("td", "th")]
        require(0 < len(cells) <= MAX_COLUMNS, "TABLE_COLUMN_LIMIT")
        require(
            not any(isinstance(n, _Node) and n.tag not in ("td", "th") for n in row.children),
            "MIXED_TABLE_ROW",
        )
        result.append(cells)
    return result


def _tokens(row: list[_Node]) -> tuple[str, ...]:
    return tuple(_text(c) for c in row)


def _spans(rows: list[list[_Node]], width: int, allow_notes: bool) -> None:
    for row in rows:
        for cell in row:
            attrs = dict(cell.attrs)
            require(attrs.get("rowspan", "1") == "1", "UNSUPPORTED_TABLE_SPAN")
            expected = str(width) if allow_notes and len(row) == 1 else "1"
            require(attrs.get("colspan", "1") == expected, "UNSUPPORTED_TABLE_SPAN")


def _lexeme(cell: _Node) -> str:
    fragments: list[_Text] = []

    def visit(n: _Node) -> None:
        for c in n.children:
            if isinstance(c, _Node):
                visit(c)
            elif normalize(c.decoded):
                fragments.append(c)

    visit(cell)
    require(bool(fragments), "MISSING_AMOUNT_LEXEME")
    raw = "".join(c.raw for c in fragments)
    require(normalize("".join(c.decoded for c in fragments)) == _text(cell), "SPLIT_AMOUNT_LEXEME")
    require(len(raw) <= 256, "AMOUNT_LEXEME_LIMIT")
    return raw


def _previous(node: _Node) -> _Node:
    assert node.parent is not None
    children = [n for n in node.parent.children if isinstance(n, _Node)]
    index = children.index(node)
    require(index > 0, "MISSING_ADJACENT_UNIT_HEADING")
    return children[index - 1]


def extract_html(
    body: bytes, pin: FilePin, spec: HtmlProfileSpec, code: tuple[CodePin, ...]
) -> HtmlEvidenceObservation | ExtractionRefusal:
    """Pure bytes supplied by an authorized caller, always unadmitted observations.

    This function confers no permission to acquire/read a file. The separate
    formal reader has no available real-approval verifier and cannot admit it.
    """
    if real_bw_disabled(pin, spec) or (
        type(body) is bytes and len(body) <= MAX_BODY and sha256(body).hexdigest() == BW_SHA
    ):
        return ExtractionRefusal(
            pin, spec, "BUSINESS_WIRE_REAL_BODY_DISABLED", "BUSINESS_WIRE_REAL_BODY_DISABLED"
        )
    try:
        validate_spec(spec, code)
        require(type(body) is bytes and 0 < len(body) <= MAX_BODY, "HTML_BODY_SIZE_LIMIT")
        require(
            len(body) == pin.byte_length and sha256(body).hexdigest() == pin.sha256,
            "SOURCE_PIN_MISMATCH",
        )
        require(
            not body.startswith((b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff")), "UNSUPPORTED_HTML_BOM"
        )
        synthetic = spec.classification == "SYNTHETIC_TEST_ONLY"
        require(
            (b"SYNTHETIC_TEST_ONLY" in body) == synthetic
            and not (synthetic and pin.sha256 == SEC_SHA),
            "SOURCE_CLASSIFICATION_MISMATCH",
        )
        encoding = "cp1252" if spec.declared_encoding == "windows-1252" else "utf-8"
        text = body.decode(encoding, errors="strict")
        require(
            text.encode(encoding) == body and not re.search(r"[\u0080-\u009f\ufffd]", text),
            "ENCODING_ROUNDTRIP_OR_CONTROL_FAILURE",
        )
        if encoding == "cp1252":
            # Refuse UTF-8 mojibake rather than silently interpreting it as Windows-1252.
            require(
                not re.search(r"[\u00c2\u00c3\u00e2][\u0080-\u00bf\u20ac\u2122]", text),
                "MIXED_HTML_ENCODING",
            )
        parser = _Parser(text, encoding)
        parser.feed(text)
        parser.close()
        require(len(parser.stack) == 1, "UNCLOSED_HTML_STRUCTURE")
        for node in parser.elements:
            if node.tag == "table":
                require(sum(n.tag == "tr" for n in _nodes(node)) <= MAX_ROWS, "TABLE_ROW_LIMIT")
            elif node.tag == "tr":
                require(
                    sum(isinstance(n, _Node) and n.tag in ("td", "th") for n in node.children)
                    <= MAX_COLUMNS,
                    "TABLE_COLUMN_LIMIT",
                )
        declarations = []
        for node in parser.elements:
            attrs = dict(node.attrs)
            if node.tag != "meta":
                continue
            if "charset" in attrs:
                declarations.append((attrs["charset"] or "").strip().lower())
            elif "charset" in (attrs.get("content") or "").lower():
                match = re.search(
                    r"(?:^|;)\s*charset\s*=\s*([A-Za-z0-9_-]+)\s*(?:;|$)",
                    attrs.get("content") or "",
                    re.I,
                )
                require(match is not None, "CHARSET_DECLARATION_MISMATCH")
                assert match is not None
                declarations.append(match.group(1).lower())
        require(declarations == [spec.declared_encoding.lower()], "CHARSET_DECLARATION_MISMATCH")
        if spec.profile_id == SEC_PROFILE:
            return _sec(parser, pin, spec, code)
        return _bw(parser, pin, spec, code)
    except UnicodeError:
        return ExtractionRefusal(pin, spec, "INVALID_DECLARED_ENCODING")
    except (ContractError, AssertionError, ValueError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, ContractError) else "MALFORMED_HTML_STRUCTURE"
        return ExtractionRefusal(pin, spec, reason)


def _finish(
    pin: FilePin,
    spec: HtmlProfileSpec,
    code: tuple[CodePin, ...],
    section: _Node,
    table: _Node,
    claims: list[StructuralLocator],
    target: _Node,
    comparison: _Node,
    ytd: _Node,
    unit: str,
    missing: tuple[str, ...],
    row_key: tuple[str, ...],
) -> HtmlEvidenceObservation:
    token = _text(target)
    require(type(_amount(token, "SIGNED_GROUPED_INT64-v0.1")) is int, "INVALID_SELECTED_AMOUNT")
    require(token == spec.expected_amount_text, "TARGET_AMOUNT_CONFLICT")
    exclusions = tuple(
        ExcludedCell(reason, _lexeme(cell), _text(cell), _locator(cell, reason))
        for reason, cell in (
            ("EXCLUDED_YEAR_2025_OR_PRIOR_YEAR", comparison),
            ("EXCLUDED_YEAR_TO_DATE", ytd),
        )
    )
    section_locator = _locator(section, "SECTION", profile=spec.profile_id)
    table_locator = _locator(table, "SALES_TABLE", year=spec.reference_month[:4])
    claims.append(
        _locator(target, "TARGET_AMOUNT", row="/".join(row_key), year=spec.reference_month[:4])
    )
    amount_lexeme = _lexeme(target)
    payload = {
        "view_schema": "RS2-HTML-EXTRACTION-VIEW-v0.1",
        "profile_id": spec.profile_id,
        "profile_version": spec.profile_version,
        "source_role": spec.source_role,
        "raw_filename": pin.relative_path,
        "raw_sha256": pin.sha256,
        "raw_byte_length": pin.byte_length,
        "declared_encoding": spec.declared_encoding,
        "issuer_name_observed": spec.issuer_name,
        "reference_month_observed": spec.reference_month,
        "document_date_label_observed_non_pit": spec.document_date_label,
        "issuer_code": "NOT_EVALUATED",
        "canonical_unit": "NOT_EVALUATED",
        "capture_classification": "SYNTHETIC_TEST_ONLY"
        if spec.classification == "SYNTHETIC_TEST_ONLY"
        else "BROWSER_SAVED_CAPTURE",
        "representation_kind": "ADAPTER_GENERATED_HTML_EXTRACTION_VIEW",
        "source_authentication": "NOT_ESTABLISHED",
        "source_evidence_class": "DOCUMENT_CONTENT_OBSERVED_UNADMITTED",
        "admission_eligible": False,
        "trust": "NOT_TRUSTED_PIT_EVIDENCE",
        "native_transport": "UNSUPPORTED_EXTERNAL_SOURCE_SCHEMA",
        "section_locator": asdict(section_locator),
        "table_locator": asdict(table_locator),
        "claim_locators": [asdict(c) for c in claims],
        "selected_row_key": row_key,
        "year_column": spec.reference_month[:4],
        "original_amount_lexeme": amount_lexeme,
        "generated_parsed_amount_text": token,
        "unit_heading": unit,
        "excluded_comparison": asdict(exclusions[0]),
        "excluded_ytd": asdict(exclusions[1]),
        "unobserved_claims": missing,
        "normalization": "ENTITY_DECODE_CHILD_ASCII_SPACE_ASCII_WHITESPACE_NBSP_FOLD_NO_CONVERSION-v0.1",
        "visibility": "STATIC_SOURCE_TEXT_NOT_BROWSER_COMPUTED_VISIBILITY",
        "exact_byte_span": "BYTE_SPAN_NOT_ESTABLISHED",
        "code_pins": [asdict(p) for p in code],
        "code_interpretation": "SUPPLIED_CONTENT_PINS_NOT_RUNTIME_ATTESTATION",
        "mapping": "MAPPING_UNRESOLVED",
        "IC3_C01_C08": "UNRESOLVED_LIVE",
    }
    generated = canonical(payload)
    return HtmlEvidenceObservation(
        pin,
        spec,
        code,
        section_locator,
        table_locator,
        tuple(claims),
        amount_lexeme,
        token,
        unit,
        exclusions,
        missing,
        ExtractionView(generated, sha256(generated).hexdigest()),
    )


def _sec(
    parser: _Parser, pin: FilePin, spec: HtmlProfileSpec, code: tuple[CodePin, ...]
) -> HtmlEvidenceObservation:
    marker = _one(
        [n for n in parser.elements if n.tag == "p" and _text(n) == "Exhibit 99.2"],
        "EXHIBIT_99_2_NOT_UNIQUE",
    )
    section = marker.parent
    require(section is not None and section.tag == "div", "INVALID_EXHIBIT_SECTION")
    assert section is not None
    _critical(section)
    paragraphs = [n for n in section.children if isinstance(n, _Node) and n.tag == "p"]
    issuer = _one(
        [n for n in paragraphs if _text(n) == spec.issuer_name], "ISSUER_NOT_UNIQUE_OR_CONFLICTING"
    )
    date = _one(
        [n for n in paragraphs if _text(n) == spec.document_date_label],
        "DOCUMENT_DATE_NOT_UNIQUE_OR_CONFLICTING",
    )
    month = _one(
        [n for n in paragraphs if _text(n).endswith("for the period of September 2026.")],
        "REPORTING_MONTH_NOT_UNIQUE_OR_CONFLICTING",
    )
    require(
        not re.search(r"\b2303\b|\bunaudited\b|\bconsolidated\b", _text(section), re.I),
        "UNEXPECTED_SEC_SEMANTIC_CLAIM",
    )
    tables = [n for n in _nodes(section) if n.tag == "table"]
    require(len(tables) == 2, "EXHIBIT_TABLE_SET_MISMATCH")
    candidates = [t for t in tables if any(_tokens(r) == SEC_HEADER for r in _rows(t))]
    table = _one(candidates, "SALES_TABLE_NOT_UNIQUE")
    other = next(t for t in tables if t is not table)
    require("Financial instruments" in _text(other), "DERIVATIVES_TABLE_NOT_IDENTIFIED")
    heading = _previous(table)
    require(_text(heading) == "1) Sales volume (NT$ Thousand)", "UNIT_HEADING_MISMATCH")
    unit_heads = [
        n
        for n in section.children
        if isinstance(n, _Node) and re.match(r"[0-9]+\) Sales volume", _text(n))
    ]
    require(len(unit_heads) == 1, "DUPLICATE_UNIT_HEADING")
    header_elements = []
    for node in section.children:
        if node is heading:
            break
        if isinstance(node, _Node) and _text(node):
            header_elements.append(node)
    require(header_elements == [marker, issuer, date, month], "CONFLICTING_EXHIBIT_HEADER")
    period_mentions = [
        n for n in paragraphs if re.search(r"for the period of [A-Za-z]+ [0-9]{4}\.", _text(n))
    ]
    date_mentions = [
        n for n in paragraphs if re.fullmatch(r"[A-Za-z]+ [0-9]{1,2}, [0-9]{4}", _text(n))
    ]
    require(
        period_mentions == [month] and date_mentions == [date],
        "CONFLICTING_DOCUMENT_PERIOD_OR_DATE",
    )
    rows = _rows(table)
    _spans(rows, 6, False)
    require(all(len(r) == 6 for r in rows), "SALES_ROW_WIDTH_MISMATCH")
    require(sum(_tokens(r) == SEC_HEADER for r in rows) == 1, "DUPLICATE_SALES_HEADER")
    empty = [r for r in rows if not any(_tokens(r))]
    require(len(empty) <= 1, "DUPLICATE_LAYOUT_ROW")
    data = [r for r in rows if any(_tokens(r)) and _tokens(r) != SEC_HEADER]
    require(len(data) == 2, "UNEXPECTED_SALES_ROW_SET")
    target = _one(
        [r[2] for r in data if _tokens(r)[:2] == ("September", "Net sales")],
        "TARGET_ROW_NOT_UNIQUE",
    )
    selected = next(r for r in data if r[2] is target)
    ytd = _one(
        [r[2] for r in data if _tokens(r)[:2] == ("Year-to-Date", "Net sales")],
        "YTD_ROW_NOT_UNIQUE",
    )
    locators = [
        _locator(n, label)
        for n, label in (
            (marker, "EXHIBIT_MARKER"),
            (issuer, "ISSUER_NAME"),
            (date, "DOCUMENT_DATE_NON_PIT"),
            (month, "REPORTING_PERIOD"),
            (heading, "UNIT_HEADING"),
        )
    ]
    locators.append(
        _locator(
            table,
            "LAYOUT_ROW_RULE",
            ignored_rows=str(len(empty)),
            reason="ALL_EMPTY_SIX_CELL_LAYOUT_ONLY",
        )
    )
    return _finish(
        pin,
        spec,
        code,
        section,
        table,
        locators,
        target,
        selected[3],
        ytd,
        "NT$ Thousand",
        (
            "TWSE_CODE_NOT_OBSERVED_IN_SEC",
            "UNAUDITED_NOT_OBSERVED_IN_SEC",
            "CONSOLIDATED_NOT_OBSERVED_IN_SEC",
        ),
        ("September", "Net sales"),
    )


def _bw(
    parser: _Parser, pin: FilePin, spec: HtmlProfileSpec, code: tuple[CodePin, ...]
) -> HtmlEvidenceObservation:
    root = _one(
        [n for n in parser.elements if dict(n.attrs).get("id") == "bw-release-story"],
        "PRIMARY_ROOT_NOT_UNIQUE",
    )
    ancestors = []
    parent = root.parent
    while parent:
        ancestors.append(parent.tag)
        parent = parent.parent
    require(ancestors.count("main") == 1, "PRIMARY_ROOT_OUTSIDE_MAIN")
    _critical(root)
    year, month = (int(part) for part in spec.reference_month.split("-"))
    period = MONTHS[month] + " " + str(year)
    lead_text = spec.issuer_name + " | " + period + " | unaudited monthly sales"
    paragraphs = [n for n in _nodes(root) if n.tag == "p"]
    lead = _one([n for n in paragraphs if _text(n) == lead_text], "SYNTHETIC_LEAD_NOT_UNIQUE")
    date = _one(
        [n for n in paragraphs if _text(n) == spec.document_date_label], "SYNTHETIC_DATE_NOT_UNIQUE"
    )
    table = _one([n for n in _nodes(root) if n.tag == "table"], "SALES_TABLE_NOT_UNIQUE")
    rows = _rows(table)
    _spans(rows, 5, True)
    require(len(rows) == 6, "SYNTHETIC_TABLE_ROW_SET_MISMATCH")
    title = "Monthly revenue: " + period
    unit = "Synthetic scale: NTD thousands."
    scope = "Synthetic scope: consolidated."
    for text, reason in (
        (title, "TITLE_NOT_UNIQUE"),
        (unit, "UNIT_NOTE_NOT_UNIQUE"),
        (scope, "SCOPE_NOTE_NOT_UNIQUE"),
    ):
        require(sum(_tokens(r) == (text,) for r in rows) == 1, reason)
    header = ("Period", str(year), str(year - 1), "Y/Y Change", "Y/Y (%)")
    require(sum(_tokens(r) == header for r in rows) == 1, "SYNTHETIC_HEADER_NOT_UNIQUE")
    full = [r for r in rows if len(r) == 5 and _tokens(r) != header]
    require(len(full) == 2, "SYNTHETIC_DATA_ROW_SET_MISMATCH")
    selected = [r for r in full if _text(r[0]) == MONTHS[month]]
    require(len(selected) == 1, "TARGET_ROW_NOT_UNIQUE")
    ytd = _one([r[1] for r in full if _text(r[0]) == "Year-to-Date"], "YTD_ROW_NOT_UNIQUE")
    notes = [_locator(r[0], "SYNTHETIC_NOTE", note=_text(r[0])) for r in rows if len(r) == 1]
    return _finish(
        pin,
        spec,
        code,
        root,
        table,
        [_locator(lead, "SYNTHETIC_LEAD"), _locator(date, "SYNTHETIC_DATE_NON_PIT"), *notes],
        selected[0][1],
        selected[0][2],
        ytd,
        unit,
        (),
        (MONTHS[month],),
    )
