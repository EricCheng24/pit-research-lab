"""A06 bounded, read-only offline intake. Supplied records are not attestations."""

import json
import os
import stat
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Literal, Never, cast

from pit_research_lab.domain.contracts import (
    ContractError,
    NotEvaluated,
    Record,
    digest,
    identifier,
    require,
)

MAX_RAW_BYTES = 1_048_576
MAX_METADATA_BYTES = 65_536
MANIFEST_VERSION = "a06-offline-csv-v0.1"
type IntakeDisposition = Literal[
    "SOURCE_INPUT_PENDING",
    "SOURCE_RESTRICTED_OR_RIGHTS_UNRESOLVED",
    "SOURCE_INTEGRITY_FAILURE",
    "SOURCE_SNAPSHOT_ACCEPTED_FOR_OFFLINE_PARSE",
]


def safe_relative(path: str) -> None:
    require(
        type(path) is str
        and bool(path)
        and "\\" not in path
        and ":" not in path
        and all(ord(c) >= 32 for c in path),
        "UNSAFE_RELATIVE_PATH",
    )
    parts = path.split("/")
    require(
        not PurePosixPath(path).is_absolute()
        and all(part and not part.startswith(".") for part in parts),
        "UNSAFE_RELATIVE_PATH",
    )


@dataclass(frozen=True)
class FilePin(Record):
    relative_path: str
    byte_length: int
    sha256: str

    def __post_init__(self) -> None:
        super().__post_init__()
        safe_relative(self.relative_path)
        digest(self.sha256)
        require(
            type(self.byte_length) is int and 0 <= self.byte_length <= MAX_RAW_BYTES,
            "INVALID_FILE_LENGTH",
        )


@dataclass(frozen=True)
class RightsRecord(Record):
    status: str
    allowed_uses: tuple[str, ...]
    covered_paths: tuple[str, ...]
    terms_ref: str | None
    attribution: str | None
    evidence_text: str | None
    origin_ref: str | None


@dataclass(frozen=True)
class OfflineSourceManifest(Record):
    bundle_ref: str
    snapshot_ref: str
    data_classification: str
    source_class: str
    source_title: str
    publisher: str | None
    retriever: str | None
    dataset_page_url: str | None
    resource_url: str | None
    raw: FilePin
    mapping_file: FilePin | None
    rights: RightsRecord
    custody_ref: str | None
    acquisition_text: str | None
    acquisition_origin: str | None
    acquisition_reliability: str
    csv_profile: str
    encoding: str
    headers: tuple[str, ...]
    period_policy: str
    integer_policy: str
    company_code: str
    year: int
    quarter: int
    source_metadata_claims: tuple[tuple[str, str], ...]
    manifest_version: str = MANIFEST_VERSION


@dataclass(frozen=True)
class RawSourceIdentity(Record):
    relative_path: str
    byte_length: int
    sha256: str
    representation_kind: Literal["ORIGINAL"] = field(default="ORIGINAL", init=False)


@dataclass(frozen=True)
class IntakeResult(Record):
    disposition: IntakeDisposition
    reason: str
    manifest: OfflineSourceManifest | NotEvaluated
    raw_bytes: bytes | NotEvaluated
    mapping_bytes: bytes | NotEvaluated
    observed_raw: RawSourceIdentity | NotEvaluated
    disposition_scope: str = field(
        default="SUPPLIED_RIGHTS_RECORD_COMPLETENESS; NOT_SOURCE_OR_LICENSE_AUTHENTICATION",
        init=False,
    )
    disposition_label: Literal["INTEGRATED_PROVISIONAL"] = field(
        default="INTEGRATED_PROVISIONAL", init=False
    )
    trust: Literal["NOT_TRUSTED_PIT_EVIDENCE"] = field(
        default="NOT_TRUSTED_PIT_EVIDENCE", init=False
    )
    source_authentication: Literal["NOT_ESTABLISHED"] = field(default="NOT_ESTABLISHED", init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)
    diagnostic_only: Literal[True] = field(default=True, init=False)


def snapshot_ref_for(raw_digest: str, mapping_digest: str | None) -> str:
    digest(raw_digest)
    if mapping_digest is not None:
        digest(mapping_digest)
    return "A06-SNAPSHOT-" + sha256(json.dumps([raw_digest, mapping_digest]).encode()).hexdigest()


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _no_number(value: str) -> Never:
    raise ContractError("NONINTEGER_JSON_NUMBER")


def json_object(body: bytes) -> dict[str, object]:
    require(type(body) is bytes and len(body) <= MAX_METADATA_BYTES, "METADATA_SIZE_LIMIT")
    try:
        value: object = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_float=_no_number,
            parse_constant=_no_number,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError("INVALID_METADATA_JSON") from exc
    require(type(value) is dict, "INVALID_METADATA_OBJECT")
    return cast(dict[str, object], value)


def text_value(value: object) -> str:
    require(type(value) is str and bool(value), "INVALID_TEXT_FIELD")
    return cast(str, value)


def _optional_text(value: object) -> str | None:
    return None if value is None else text_value(value)


def _texts(value: object) -> tuple[str, ...]:
    require(type(value) is list, "INVALID_TEXT_ARRAY")
    return tuple(text_value(v) for v in cast(list[object], value))


def _integer(value: object) -> int:
    require(type(value) is int, "INVALID_INTEGER_FIELD")
    return cast(int, value)


def _pin(value: object) -> FilePin:
    require(type(value) is dict, "INVALID_FILE_PIN")
    p = cast(dict[str, object], value)
    require(set(p) == {"relative_path", "byte_length", "sha256"}, "INVALID_FILE_PIN")
    return FilePin(
        text_value(p["relative_path"]), _integer(p["byte_length"]), text_value(p["sha256"])
    )


def decode_manifest(body: bytes) -> OfflineSourceManifest:
    """Strict proposed JSON schema; no inferred defaults or temporal proof channel."""
    data = json_object(body)
    required = {
        "bundle_ref",
        "snapshot_ref",
        "data_classification",
        "source_class",
        "source_title",
        "publisher",
        "retriever",
        "dataset_page_url",
        "resource_url",
        "raw",
        "mapping_file",
        "rights",
        "custody_ref",
        "acquisition_text",
        "acquisition_origin",
        "acquisition_reliability",
        "csv_profile",
        "encoding",
        "headers",
        "period_policy",
        "integer_policy",
        "company_code",
        "year",
        "quarter",
        "source_metadata_claims",
        "manifest_version",
    }
    require(set(data) == required, "MANIFEST_FIELDS_INVALID")
    require(type(data["rights"]) is dict, "INVALID_RIGHTS_RECORD")
    rights = cast(dict[str, object], data["rights"])
    require(
        set(rights)
        == {
            "status",
            "allowed_uses",
            "covered_paths",
            "terms_ref",
            "attribution",
            "evidence_text",
            "origin_ref",
        },
        "INVALID_RIGHTS_RECORD",
    )
    require(type(data["source_metadata_claims"]) is dict, "INVALID_SOURCE_CLAIMS")
    claims = cast(dict[str, object], data["source_metadata_claims"])
    return OfflineSourceManifest(
        text_value(data["bundle_ref"]),
        text_value(data["snapshot_ref"]),
        text_value(data["data_classification"]),
        text_value(data["source_class"]),
        text_value(data["source_title"]),
        _optional_text(data["publisher"]),
        _optional_text(data["retriever"]),
        _optional_text(data["dataset_page_url"]),
        _optional_text(data["resource_url"]),
        _pin(data["raw"]),
        None if data["mapping_file"] is None else _pin(data["mapping_file"]),
        RightsRecord(
            text_value(rights["status"]),
            _texts(rights["allowed_uses"]),
            _texts(rights["covered_paths"]),
            *(
                _optional_text(rights[k])
                for k in ("terms_ref", "attribution", "evidence_text", "origin_ref")
            ),
        ),
        _optional_text(data["custody_ref"]),
        _optional_text(data["acquisition_text"]),
        _optional_text(data["acquisition_origin"]),
        text_value(data["acquisition_reliability"]),
        text_value(data["csv_profile"]),
        text_value(data["encoding"]),
        _texts(data["headers"]),
        text_value(data["period_policy"]),
        text_value(data["integer_policy"]),
        text_value(data["company_code"]),
        _integer(data["year"]),
        _integer(data["quarter"]),
        tuple(sorted((k, text_value(v)) for k, v in claims.items())),
        text_value(data["manifest_version"]),
    )


def intake_result(
    state: IntakeDisposition,
    reason: str,
    manifest: OfflineSourceManifest | NotEvaluated,
    raw: bytes | NotEvaluated,
    mapping: bytes | NotEvaluated,
) -> IntakeResult:
    identity: RawSourceIdentity | NotEvaluated = NotEvaluated("A06", "RAW_BYTES_NOT_OBSERVED")
    if isinstance(raw, bytes) and isinstance(manifest, OfflineSourceManifest):
        identity = RawSourceIdentity(manifest.raw.relative_path, len(raw), sha256(raw).hexdigest())
    return IntakeResult(state, reason, manifest, raw, mapping, identity)


def validate_source_manifest(
    manifest: OfflineSourceManifest,
    supplied_bytes: bytes | None,
    mapping_bytes: bytes | None = None,
) -> IntakeResult:
    """Pure supplied-record/integrity gate; no historical availability inference."""
    absent = NotEvaluated("A06", "BYTES_NOT_SUPPLIED")
    raw: bytes | NotEvaluated = absent if supplied_bytes is None else supplied_bytes
    mapping: bytes | NotEvaluated = absent if mapping_bytes is None else mapping_bytes
    try:
        require(manifest.manifest_version == MANIFEST_VERSION, "UNSUPPORTED_MANIFEST_VERSION")
        identifier(manifest.bundle_ref)
        safe_relative(manifest.raw.relative_path)
        require(manifest.raw.relative_path.endswith(".csv"), "RAW_FILE_MUST_BE_CSV")
        if manifest.mapping_file is not None:
            safe_relative(manifest.mapping_file.relative_path)
            require(
                manifest.mapping_file.relative_path.endswith(".json")
                and manifest.mapping_file.relative_path != manifest.raw.relative_path,
                "INVALID_MAPPING_PATH",
            )
        if supplied_bytes is None or (manifest.mapping_file is not None and mapping_bytes is None):
            return intake_result(
                "SOURCE_INPUT_PENDING", "PINNED_BYTES_MISSING", manifest, raw, mapping
            )
        require(
            type(supplied_bytes) is bytes and len(supplied_bytes) <= MAX_RAW_BYTES, "RAW_SIZE_LIMIT"
        )
        require(
            len(supplied_bytes) == manifest.raw.byte_length
            and sha256(supplied_bytes).hexdigest() == manifest.raw.sha256,
            "RAW_PIN_MISMATCH",
        )
        if manifest.mapping_file is not None:
            assert mapping_bytes is not None
            p = manifest.mapping_file
            require(
                type(mapping_bytes) is bytes
                and len(mapping_bytes) <= MAX_METADATA_BYTES
                and len(mapping_bytes) == p.byte_length
                and sha256(mapping_bytes).hexdigest() == p.sha256,
                "MAPPING_PIN_MISMATCH",
            )
        else:
            require(mapping_bytes is None, "UNDECLARED_MAPPING_BYTES")
        require(
            manifest.snapshot_ref
            == snapshot_ref_for(
                manifest.raw.sha256, manifest.mapping_file.sha256 if manifest.mapping_file else None
            ),
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
        paths = (manifest.raw.relative_path,) + (
            (manifest.mapping_file.relative_path,) if manifest.mapping_file else ()
        )
        if not (
            rights.status == "PERMITTED"
            and rights.allowed_uses == ("OFFLINE_RESEARCH",)
            and tuple(sorted(rights.covered_paths)) == tuple(sorted(paths))
            and all((rights.terms_ref, rights.attribution, rights.evidence_text, rights.origin_ref))
            and not cast(str, rights.evidence_text).startswith(("http://", "https://"))
        ):
            return intake_result(
                "SOURCE_RESTRICTED_OR_RIGHTS_UNRESOLVED",
                "RIGHTS_RECORD_INCOMPLETE_RESTRICTED_OR_NOT_APPLICABLE",
                manifest,
                raw,
                mapping,
            )
        return intake_result(
            "SOURCE_SNAPSHOT_ACCEPTED_FOR_OFFLINE_PARSE",
            "SUPPLIED_RECORDS_AND_BYTES_MATCH",
            manifest,
            raw,
            mapping,
        )
    except ContractError as exc:
        return intake_result("SOURCE_INTEGRITY_FAILURE", str(exc), manifest, raw, mapping)


def _open_root(root: Path) -> int:
    require(
        root.is_absolute() and ".." not in root.parts and len(root.parts) > 2, "UNSAFE_INPUT_ROOT"
    )
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in root.parts[1:]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read_relative(root_fd: int, name: str, limit: int) -> bytes:
    safe_relative(name)
    fd = os.dup(root_fd)
    try:
        parts = name.split("/")
        for component in parts[:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            before = os.fstat(leaf)
            require(stat.S_ISREG(before.st_mode), "NOT_REGULAR_INPUT_FILE")
            require(before.st_size <= limit, "INPUT_SIZE_LIMIT")
            data = bytearray()
            while len(data) <= limit:
                block = os.read(leaf, min(65_536, limit + 1 - len(data)))
                if not block:
                    break
                data.extend(block)
            after = os.fstat(leaf)
            require(
                len(data) <= limit and len(data) == before.st_size, "INPUT_SIZE_OR_READ_CHANGED"
            )
            # mtime is only a concurrent-read stability guard, NEVER historical evidence.
            require(
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
                "INPUT_CHANGED_DURING_READ",
            )
            return bytes(data)
        finally:
            os.close(leaf)
    finally:
        os.close(fd)


def inspect_offline_source(root: Path, manifest_path: str = "manifest.json") -> IntakeResult:
    """Explicit read-only I/O; caller supplies an authorized root, never discovered."""
    absent = NotEvaluated("A06", "NOT_OBSERVED")
    manifest: OfflineSourceManifest | NotEvaluated = absent
    raw: bytes | NotEvaluated = absent
    mapping: bytes | NotEvaluated = absent
    root_fd: int | None = None
    try:
        safe_relative(manifest_path)
        require(manifest_path.endswith(".json"), "MANIFEST_MUST_BE_JSON")
        root_fd = _open_root(root)
        manifest = decode_manifest(_read_relative(root_fd, manifest_path, MAX_METADATA_BYTES))
        require(
            manifest.raw.relative_path != manifest_path
            and (
                manifest.mapping_file is None
                or manifest.mapping_file.relative_path != manifest_path
            ),
            "INPUT_ROLE_PATH_COLLISION",
        )
        raw = _read_relative(root_fd, manifest.raw.relative_path, MAX_RAW_BYTES)
        if manifest.mapping_file is not None:
            mapping = _read_relative(
                root_fd, manifest.mapping_file.relative_path, MAX_METADATA_BYTES
            )
        return validate_source_manifest(
            manifest, raw, mapping if isinstance(mapping, bytes) else None
        )
    except FileNotFoundError:
        return intake_result(
            "SOURCE_INPUT_PENDING", "ROOT_MANIFEST_OR_PINNED_FILE_MISSING", manifest, raw, mapping
        )
    except (OSError, ContractError) as exc:
        reason = (
            str(exc) if isinstance(exc, ContractError) else "UNSAFE_PATH_OR_READ_OPERATION_FAILED"
        )
        return intake_result("SOURCE_INTEGRITY_FAILURE", reason, manifest, raw, mapping)
    finally:
        if root_fd is not None:
            os.close(root_fd)
