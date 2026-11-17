"""Pure CAN-01 candidate codec, complete only for opaque SOURCE-BYTES.

Explicit schemas describe byte/fragment grammar, never semantic domain approval.
Digest equality is content integrity only. No resource resolution, Native replay,
source authentication, publication provenance, access grant or PIT admission.
Diagnostics are local to the tested subset, without global multi-fault precedence.
"""

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from hashlib import sha256
from types import MappingProxyType
from typing import Literal, NoReturn, cast

MAX_PAYLOAD = 16_777_216
MAX_TEXT = 65_536
MAX_ARRAY = 4096
# Conservative container safety ceiling, NOT a normative record-depth convention.
# Arrays count toward this local budget; disputed record depth 64/65 is unsupported.
_CONTAINER_CEILING = 64
_NODE_BUDGET = 100_000
PROFILE = "typed-json-candidate-v0.1"
DOMAINS = MappingProxyType(
    {
        name: name.lower() + "-candidate-v0.1"
        for name in (
            "SOURCE-BYTES",
            "F2-QUALIFICATION",
            "F2-OBSERVATION",
            "TEMPORAL-SEQUENCE",
            "F3-EXPERIMENT",
            "F3-RUN-ATTEMPT",
            "RESULT",
            "EVIDENCE",
            "F5-DECISION",
            "F5-EVALUATION",
        )
    }
)
SOURCE_DOMAIN = "PITLAB/ACADEMIC/SOURCE-BYTES/candidate-v0.1"
SOURCE_SCHEMA_VERSION = DOMAINS["SOURCE-BYTES"]
_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*", re.ASCII)
_HEX = re.compile(r"[0-9a-f]{64}", re.ASCII)


class CodecRefusal(ValueError):
    """Bounded codec diagnostic, not an F2/F3/F5 or authorization error API."""

    def __init__(self, code: str, category: str = "STRUCTURALLY_INVALID") -> None:
        self.category = category
        self.code = code
        super().__init__(f"{category} / {code}")


def _refuse(code: str, category: str = "STRUCTURALLY_INVALID") -> NoReturn:
    raise CodecRefusal(code, category)


@dataclass(frozen=True, slots=True)
class TextSchema:
    """Unicode scalar Text; empty is allowed unless the field says otherwise."""

    literal: str | None = None
    max_bytes: int = MAX_TEXT
    min_bytes: int = 0
    hex64: bool = False


@dataclass(frozen=True, slots=True)
class BooleanSchema:
    """Actual Boolean, with no integer coercion."""


@dataclass(frozen=True, slots=True)
class IntegerSchema:
    """Tagged Int64/UInt64 fragment; no semantic field sign policy implied."""

    signed: bool = False


@dataclass(frozen=True, slots=True)
class RecordSchema:
    """Closed ordered schema declaration; emitter sorts keys, never arrays.

    This is a fragment grammar descriptor, not a registered-domain validator.
    """

    fields: tuple[tuple[str, "Schema"], ...]


@dataclass(frozen=True, slots=True)
class ArraySchema:
    """Explicit authorized cardinality within the global array budget."""

    item: "Schema"
    minimum: int
    maximum: int


type Schema = TextSchema | BooleanSchema | IntegerSchema | RecordSchema | ArraySchema
TEXT = TextSchema()
UINT64 = IntegerSchema()
INT64 = IntegerSchema(signed=True)
SOURCE_PAYLOAD_SCHEMA = RecordSchema(
    (
        ("body_byte_length", UINT64),
        ("body_sha256", TextSchema(hex64=True)),
        ("canonical_profile_version", TextSchema(literal=PROFILE)),
    )
)
_ENVELOPE_SCHEMA = RecordSchema(
    (
        ("domain_tag", TextSchema(literal=SOURCE_DOMAIN)),
        ("object_schema_version", TextSchema(literal=SOURCE_SCHEMA_VERSION)),
        ("canonical_profile_version", TextSchema(literal=PROFILE)),
        ("digest_algorithm", TextSchema(literal="SHA-256")),
        ("canonical_payload_byte_length", UINT64),
        ("digest_hex", TextSchema(hex64=True)),
    )
)
_POLICY_SHAPE = RecordSchema(
    (
        ("resource_kind", TextSchema(literal="NUMERIC_POLICY")),
        ("resource_version", TextSchema(min_bytes=1, max_bytes=128)),
        ("resource_schema", TextSchema(min_bytes=1, max_bytes=128)),
        ("content_ref", _ENVELOPE_SCHEMA),
    )
)
_DECIMAL_SHAPE = RecordSchema(
    (
        ("type", TextSchema(literal="decimal")),
        ("coefficient", INT64),
        ("scale", UINT64),
        ("unit", TEXT),
        ("numeric_policy_ref", _POLICY_SHAPE),
    )
)
_RATIO_SHAPE = RecordSchema(
    (
        ("type", TextSchema(literal="fixed_ratio6")),
        ("scaled_units", UINT64),
        ("decimal_text", TEXT),
        ("scale", UINT64),
        ("unit", TextSchema(literal="FRACTION")),
        ("numeric_policy_ref", _POLICY_SHAPE),
    )
)


def _text(value: object, schema: TextSchema = TEXT) -> str:
    if type(value) is not str:
        _refuse("TEXT_TYPE")
    s = value
    if not 0 <= schema.min_bytes <= schema.max_bytes <= MAX_TEXT:
        _refuse("SCHEMA_BOUND", "UNSUPPORTED_SCHEMA")
    if len(s) > schema.max_bytes:
        _refuse("TEXT_BOUND")
    try:
        length = len(s.encode("utf-8"))
    except UnicodeEncodeError:
        _refuse("SURROGATE")
    if not schema.min_bytes <= length <= schema.max_bytes:
        _refuse("TEXT_BOUND")
    if schema.literal is not None and s != schema.literal:
        _refuse("LITERAL", "UNSUPPORTED_SCHEMA")
    if schema.hex64 and _HEX.fullmatch(s) is None:
        _refuse("HEX64")
    return s


def _closed(value: object, keys: set[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != keys:
        _refuse("CLOSED_FIELDS")
    return cast(dict[str, object], value)


def validate_integer(value: object, *, signed: bool = False) -> int:
    """Validate a tagged integer exactly; returned int is internal arithmetic only."""
    d = _closed(value, {"type", "value"})
    if d["type"] != ("int64" if signed else "uint64"):
        _refuse("INTEGER_TAG")
    if type(d["value"]) is not str:
        _refuse("INTEGER_TEXT")
    s = d["value"]
    pattern = r"0|-?[1-9][0-9]*" if signed else r"0|[1-9][0-9]*"
    if re.fullmatch(pattern, s, re.ASCII) is None:
        _refuse("INTEGER_SPELLING")
    # Bound before int conversion (including Python's large decimal conversion limit).
    if len(s) > 20:
        _refuse("INTEGER_RANGE")
    n = int(s)
    low, high = (-(1 << 63), (1 << 63) - 1) if signed else (0, (1 << 64) - 1)
    if not low <= n <= high:
        _refuse("INTEGER_RANGE")
    return n


def validate_boolean(value: object) -> bool:
    """Validate a Boolean fragment without Python's bool/int coercion."""
    if type(value) is not bool:
        _refuse("BOOLEAN_TYPE")
    return value


def _guard_value(value: object) -> None:
    """Iterative traversal before recursive validation/encoding; reject cycles."""
    active: set[int] = set()
    stack = [(value, 0, False)]
    budget = _NODE_BUDGET
    while stack:
        v, depth, leaving = stack.pop()
        if leaving:
            active.remove(id(v))
            continue
        budget -= 1
        if budget < 0:
            _refuse("RESOURCE_BUDGET")
        if v is None:
            _refuse("NULL_OR_UNTAGGED")
        if type(v) in (int, float):
            _refuse("BARE_NUMBER")
        if type(v) is str:
            _text(v)
        elif type(v) is bool:
            pass
        elif type(v) in (dict, list):
            if id(v) in active:
                _refuse("REF_CYCLE")
            if depth + 1 >= _CONTAINER_CEILING:
                _refuse("PENDING_OWNER_BOUNDARY_DECISION", "CONTRACT_BOUNDARY_UNRESOLVED")
            active.add(id(v))
            stack.append((v, depth, True))
            children: Iterable[object]
            if isinstance(v, dict):
                if len(v) > _NODE_BUDGET:
                    _refuse("RESOURCE_BUDGET")
                for key in v:
                    if type(key) is not str or _KEY.fullmatch(key) is None:
                        _refuse("ASCII_KEY")
                    _text(key)
                children = v.values()
            else:
                entries = cast(list[object], v)
                if len(entries) > MAX_ARRAY:
                    _refuse("ARRAY_BOUND")
                children = entries
            stack.extend((child, depth + 1, False) for child in children)
        else:
            _refuse("VALUE_TYPE")


def _validate(value: object, schema: Schema) -> None:
    if isinstance(schema, TextSchema):
        _text(value, schema)
    elif isinstance(schema, BooleanSchema):
        validate_boolean(value)
    elif isinstance(schema, IntegerSchema):
        validate_integer(value, signed=schema.signed)
    elif isinstance(schema, ArraySchema):
        if not 0 <= schema.minimum <= schema.maximum <= MAX_ARRAY:
            _refuse("SCHEMA_BOUND", "UNSUPPORTED_SCHEMA")
        if type(value) is not list:
            _refuse("ARRAY_TYPE")
        entries = cast(list[object], value)
        if not schema.minimum <= len(entries) <= schema.maximum:
            _refuse("ARRAY_BOUND")
        for entry in entries:
            _validate(entry, schema.item)
    elif isinstance(schema, RecordSchema):
        names = [k for k, _ in schema.fields]
        if len(set(names)) != len(names) or any(_KEY.fullmatch(k) is None for k in names):
            _refuse("SCHEMA_FIELDS", "UNSUPPORTED_SCHEMA")
        d = _closed(value, set(names))
        for key, child_schema in schema.fields:
            _validate(d[key], child_schema)
    else:
        _refuse("EXPLICIT_SCHEMA_REQUIRED", "UNSUPPORTED_SCHEMA")


def _emit(value: object) -> bytes:
    result = bytearray()

    def append(raw: bytes) -> None:
        if len(result) + len(raw) > MAX_PAYLOAD:
            _refuse("PAYLOAD_BOUND")
        result.extend(raw)

    def string(s: str) -> None:
        append(b'"')
        for c in s:
            if c == '"':
                append(b'\\"')
            elif c == "\\":
                append(b"\\\\")
            elif ord(c) < 32:
                append(f"\\u{ord(c):04x}".encode("ascii"))
            else:
                append(c.encode("utf-8"))
        append(b'"')

    def visit(v: object) -> None:
        if isinstance(v, str):
            string(v)
        elif type(v) is bool:
            append(b"true" if v else b"false")
        elif isinstance(v, dict):
            append(b"{")
            for i, key in enumerate(sorted(v, key=lambda k: k.encode("utf-8"))):
                if i:
                    append(b",")
                string(key)
                append(b":")
                visit(v[key])
            append(b"}")
        elif isinstance(v, list):
            append(b"[")
            for i, entry in enumerate(v):
                if i:
                    append(b",")
                visit(entry)
            append(b"]")
        else:
            _refuse("VALUE_TYPE")

    visit(value)
    return bytes(result)


def encode_canonical_record(value: object, schema: RecordSchema) -> bytes:
    """Encode a closed explicitly described fragment, without domain approval."""
    if not isinstance(schema, RecordSchema):
        _refuse("EXPLICIT_SCHEMA_REQUIRED", "UNSUPPORTED_SCHEMA")
    _guard_value(value)
    if schema == SOURCE_PAYLOAD_SCHEMA:
        _source_claim_check(value)
    _validate(value, schema)
    return _emit(value)


def _prescan(raw: bytes) -> None:
    """Bound nesting/array cardinality/token amplification before json.loads."""
    stack: list[list[int]] = []
    quoted = escaped = False
    punctuation = 0
    for c in raw:
        if quoted:
            if escaped:
                escaped = False
            elif c == 92:
                escaped = True
            elif c == 34:
                quoted = False
        elif c == 34:
            quoted = True
        elif c in (123, 91):
            stack.append([c, 1])
            punctuation += 1
            if len(stack) >= _CONTAINER_CEILING:
                _refuse("PENDING_OWNER_BOUNDARY_DECISION", "CONTRACT_BOUNDARY_UNRESOLVED")
        elif c in (125, 93):
            if not stack or stack[-1][0] != (123 if c == 125 else 91):
                _refuse("INVALID_JSON_UTF8")
            stack.pop()
        elif c in (44, 58):
            punctuation += 1
            if c == 44 and stack and stack[-1][0] == 91:
                stack[-1][1] += 1
                if stack[-1][1] > MAX_ARRAY:
                    _refuse("ARRAY_BOUND")
        if punctuation > _NODE_BUDGET:
            _refuse("RESOURCE_BUDGET")


def _decode(raw: bytes) -> object:
    if type(raw) is not bytes:
        _refuse("BYTES_REQUIRED")
    if not 1 <= len(raw) <= MAX_PAYLOAD:
        _refuse("PAYLOAD_BOUND")
    if raw.startswith(b"\xef\xbb\xbf"):
        _refuse("BOM")
    _prescan(raw)

    def pairs(entries: list[tuple[str, object]]) -> dict[str, object]:
        seen: set[str] = set()
        for key, _ in entries:
            if key in seen:
                _refuse("DUPLICATE_KEY")
            seen.add(key)
        return dict(entries)

    def number(_: str) -> NoReturn:
        _refuse("BARE_NUMBER")

    try:
        value: object = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_int=number,
            parse_float=number,
            parse_constant=number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise CodecRefusal("INVALID_JSON_UTF8") from exc
    _guard_value(value)
    return value


def _source_claim_check(value: object) -> None:
    if type(value) is not dict:
        return
    d = cast(dict[str, object], value)
    # SOURCE-BYTES has no legitimate digest_hex or reference field. Recognize
    # explicit digest claims/full own-type envelopes, never a field name alone.
    if type(d.get("digest_hex")) is str and _HEX.fullmatch(cast(str, d["digest_hex"])):
        _refuse("REF_CYCLE")
    ref = d.get("reference")
    if type(ref) is dict and set(ref) == {k for k, _ in _ENVELOPE_SCHEMA.fields}:
        if (
            ref.get("domain_tag") == SOURCE_DOMAIN
            and ref.get("object_schema_version") == SOURCE_SCHEMA_VERSION
        ):
            digest = ref.get("digest_hex")
            if type(digest) is str and _HEX.fullmatch(digest):
                _refuse("REF_CYCLE")


def parse_canonical_record(raw: bytes, schema: RecordSchema) -> dict[str, object]:
    """Parse strict original bytes; no defaulting, normalization or coercion."""
    value = _decode(raw)
    if schema == SOURCE_PAYLOAD_SCHEMA:
        _source_claim_check(value)
        if isinstance(value, dict) and "canonical_profile_version" in value:
            if value["canonical_profile_version"] != PROFILE:
                _refuse("PROFILE", "UNSUPPORTED_SCHEMA")
    expected = encode_canonical_record(value, schema)
    if raw != expected:
        _refuse("NONCANONICAL_BYTES")
    return cast(dict[str, object], value)


@dataclass(frozen=True, slots=True)
class NumericFragmentCheck:
    """Only structural grammar passed; policy semantics remain unavailable."""

    structure: Literal["STRUCTURE_VALID_FRAGMENT_ONLY"] = "STRUCTURE_VALID_FRAGMENT_ONLY"
    semantics: Literal["BLOCKED_NOT_SUPPLIED"] = "BLOCKED_NOT_SUPPLIED"


def validate_numeric_fragment(value: object) -> NumericFragmentCheck:
    """Decimal/FixedRatio6 grammar, including untrusted policy reference shape.

    No NUMERIC_POLICY resource body is resolved, reviewed or approved here.
    """
    _guard_value(value)
    if not isinstance(value, dict):
        _refuse("CLOSED_FIELDS")
    if value.get("type") == "decimal":
        _validate(value, _DECIMAL_SHAPE)
        if validate_integer(value["scale"]) > 18:
            _refuse("DECIMAL_SCALE")
    elif value.get("type") == "fixed_ratio6":
        _validate(value, _RATIO_SHAPE)
        units = validate_integer(value["scaled_units"])
        if (
            validate_integer(value["scale"]) != 6
            or units > 1_000_000
            or value["decimal_text"] != f"{units // 1_000_000}.{units % 1_000_000:06d}"
        ):
            _refuse("RATIO_MISMATCH")
    else:
        _refuse("NUMERIC_TAG")
    return NumericFragmentCheck()


def require_candidate_domain(domain_tag: str, schema_version: str) -> None:
    """Exact negotiation; nine known names do not supply semantic bodies/oracles."""
    _text(domain_tag, TextSchema(min_bytes=1, max_bytes=128))
    _text(schema_version, TextSchema(min_bytes=1, max_bytes=128))
    if not domain_tag.isascii() or not schema_version.isascii():
        _refuse("DOMAIN_SCHEMA", "UNSUPPORTED_SCHEMA")
    for name, version in DOMAINS.items():
        if domain_tag == f"PITLAB/ACADEMIC/{name}/candidate-v0.1" and schema_version == version:
            if name != "SOURCE-BYTES":
                _refuse("UNSUPPORTED_SEMANTIC_SCHEMA", "NOT_SUPPLIED")
            return
    _refuse("DOMAIN_SCHEMA", "UNSUPPORTED_SCHEMA")


def _uint(n: int) -> dict[str, object]:
    return {"type": "uint64", "value": str(n)}


def _envelope(payload: bytes, digest: str) -> dict[str, object]:
    return {
        "domain_tag": SOURCE_DOMAIN,
        "object_schema_version": SOURCE_SCHEMA_VERSION,
        "canonical_profile_version": PROFILE,
        "digest_algorithm": "SHA-256",
        "canonical_payload_byte_length": _uint(len(payload)),
        "digest_hex": digest,
    }


@dataclass(frozen=True, slots=True)
class SourceBytesCandidate:
    """Internally consistent candidate; original raw-body provenance is not established.

    Construction reconciles payload/frame/digest only. Raw-body reconciliation
    still requires verify_source_bytes_candidate with the actual original bytes.
    """

    payload: bytes
    frame: bytes
    frame_digest: str
    diagnostic_only: Literal[True] = field(default=True, init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)
    trust: Literal["NOT_TRUSTED_PIT_EVIDENCE"] = field(
        default="NOT_TRUSTED_PIT_EVIDENCE", init=False
    )
    source_authentication: Literal["NOT_ESTABLISHED"] = field(default="NOT_ESTABLISHED", init=False)
    disposition: Literal["INTEGRATED_PROVISIONAL"] = field(
        default="INTEGRATED_PROVISIONAL", init=False
    )

    def __post_init__(self) -> None:
        if type(self.payload) is not bytes:
            _refuse("BYTES_REQUIRED")
        actual = verify_source_frame(self.frame, _envelope(self.payload, self.frame_digest))
        if actual != self.payload:
            _refuse("PAYLOAD_MISMATCH")

    @property
    def candidate_envelope(self) -> dict[str, object]:
        """Six-field reference-shaped candidate, never an issued ParentRef."""
        return _envelope(self.payload, self.frame_digest)


def encode_source_bytes_candidate(raw_body: bytes) -> SourceBytesCandidate:
    """Hash actual opaque bytes without decoding; build the sole complete candidate."""
    if type(raw_body) is not bytes:
        _refuse("BYTES_REQUIRED")
    payload = encode_canonical_record(
        {
            "body_byte_length": _uint(len(raw_body)),
            "body_sha256": sha256(raw_body).hexdigest(),
            "canonical_profile_version": PROFILE,
        },
        SOURCE_PAYLOAD_SCHEMA,
    )
    frame = b"".join(
        len(part).to_bytes(8, "big") + part
        for part in (SOURCE_DOMAIN.encode("ascii"), SOURCE_SCHEMA_VERSION.encode("ascii"), payload)
    )
    return SourceBytesCandidate(payload, frame, sha256(frame).hexdigest())


def verify_source_frame(frame: bytes, envelope: object) -> bytes:
    """Bounded exact SOURCE-BYTES transport/payload verification, without raw body.

    This cannot establish raw-body reconciliation; use the complementary verifier.
    Untrusted lengths are checked before slicing; no allocation follows a prefix.
    """
    if type(frame) is not bytes:
        _refuse("BYTES_REQUIRED")
    if len(frame) > MAX_PAYLOAD + 280:
        _refuse("FRAME_LENGTH")
    offset = 0
    parts: list[bytes] = []
    for bound in (128, 128, MAX_PAYLOAD):
        if len(frame) - offset < 8:
            _refuse("FRAME_TRUNCATED")
        size = int.from_bytes(frame[offset : offset + 8], "big")
        offset += 8
        if not 1 <= size <= bound:
            _refuse("FRAME_LENGTH")
        if size > len(frame) - offset:
            _refuse("FRAME_TRUNCATED")
        parts.append(frame[offset : offset + size])
        offset += size
    if offset != len(frame):
        _refuse("FRAME_TRAILING")
    try:
        domain, version = (part.decode("ascii") for part in parts[:2])
    except UnicodeDecodeError:
        _refuse("DOMAIN_SCHEMA", "UNSUPPORTED_SCHEMA")
    require_candidate_domain(domain, version)
    payload = parts[2]
    parse_canonical_record(payload, SOURCE_PAYLOAD_SCHEMA)
    _guard_value(envelope)
    d = _closed(envelope, {k for k, _ in _ENVELOPE_SCHEMA.fields})
    for key, expected in (
        ("domain_tag", domain),
        ("object_schema_version", version),
        ("canonical_profile_version", PROFILE),
        ("digest_algorithm", "SHA-256"),
    ):
        if d[key] != expected:
            _refuse("ENVELOPE_NEGOTIATION", "UNSUPPORTED_SCHEMA")
    _validate(d, _ENVELOPE_SCHEMA)
    if validate_integer(d["canonical_payload_byte_length"]) != len(payload):
        _refuse("PAYLOAD_LENGTH")
    if bytes.fromhex(cast(str, d["digest_hex"])) != sha256(frame).digest():
        _refuse("DIGEST_MISMATCH")
    return payload


def verify_source_bytes_candidate(
    raw_body: bytes, payload: bytes, frame: bytes, envelope: object
) -> SourceBytesCandidate:
    """Reconcile supplied raw body, payload, full frame and six-field candidate."""
    actual_payload = verify_source_frame(frame, envelope)
    if type(payload) is not bytes or payload != actual_payload:
        _refuse("PAYLOAD_MISMATCH")
    candidate = encode_source_bytes_candidate(raw_body)
    if payload != candidate.payload or frame != candidate.frame:
        _refuse("SOURCE_BODY_MISMATCH")
    return candidate
