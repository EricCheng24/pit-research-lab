"""RS2 explicit synthetic-only file reads; real rights/approval remain unverified.

No approval-verification contract is installed. Submitted metadata, including
apparently complete pins or nonempty approval strings, can never enable a real
body read here. A future real admission path requires separate authorization.
"""

import os
import stat
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import cast

from pit_research_lab.domain.contracts import CodePin, ContractError, NotEvaluated, Record, require
from pit_research_lab.domain.issuer_html_extraction import (
    ABSENT,
    CODE_PATHS,
    MAX_BODY,
    SEC_SHA,
    ExtractionRefusal,
    HtmlEvidenceObservation,
    HtmlProfileSpec,
    extract_html,
    real_bw_disabled,
    validate_spec,
)
from pit_research_lab.domain.source_intake import (
    MAX_METADATA_BYTES,
    FilePin,
    _open_root,
    _read_relative,
    json_object,
    safe_relative,
    text_value,
)


@dataclass(frozen=True)
class HtmlIntakeResult(Record):
    source_pin: FilePin
    specification: HtmlProfileSpec
    status: str
    reason: str
    observation: HtmlEvidenceObservation | ExtractionRefusal | NotEvaluated = ABSENT
    body_read_attempts: tuple[str, ...] = ()
    description_sha256: str | NotEvaluated = ABSENT
    source_body: NotEvaluated = field(default=ABSENT, init=False)
    admission_eligible: bool = field(default=False, init=False)
    trust: str = field(default="NOT_TRUSTED_PIT_EVIDENCE", init=False)


def _object(value: object, keys: set[str]) -> dict[str, object]:
    require(type(value) is dict, "INVALID_RIGHTS_DESCRIPTION")
    result = cast(dict[str, object], value)
    require(set(result) == keys, "INVALID_RIGHTS_DESCRIPTION_FIELDS")
    return result


def _pin(value: object) -> FilePin:
    data = _object(value, {"relative_path", "byte_length", "sha256"})
    require(type(data["byte_length"]) is int, "INVALID_RIGHTS_PIN_LENGTH")
    return FilePin(
        text_value(data["relative_path"]),
        cast(int, data["byte_length"]),
        text_value(data["sha256"]),
    )


def _description(
    body: bytes, pin: FilePin, spec: HtmlProfileSpec, code: tuple[CodePin, ...]
) -> bool:
    """Validate submitted cross-links only; True means terms PIN PRESENT, not approved."""
    data = _object(
        json_object(body),
        {
            "description_schema",
            "source_pin",
            "profile_id",
            "profile_version",
            "source_role",
            "reference_month",
            "issuer_name",
            "code_pins",
            "terms_pin",
            "decision_pin",
            "approval_ref",
            "declared_status",
        },
    )
    require(
        data["description_schema"] == "RS2-RIGHTS-DESCRIPTION-PROPOSED-v0.1",
        "UNSUPPORTED_RIGHTS_DESCRIPTION",
    )
    require(_pin(data["source_pin"]) == pin, "SOURCE_PIN_MISMATCH")
    require(
        (
            data["profile_id"],
            data["profile_version"],
            data["source_role"],
            data["reference_month"],
            data["issuer_name"],
        )
        == (
            spec.profile_id,
            spec.profile_version,
            spec.source_role,
            spec.reference_month,
            spec.issuer_name,
        ),
        "RIGHTS_PROFILE_SCOPE_LINK_MISMATCH",
    )
    values = data["code_pins"]
    require(type(values) is list, "INVALID_CODE_LINKS")
    pins = []
    for value in cast(list[object], values):
        item = _object(value, {"path", "sha256"})
        pins.append(CodePin(text_value(item["path"]), text_value(item["sha256"])))
    require(tuple(pins) == code, "RIGHTS_CODE_LINK_MISMATCH")
    for name in ("terms_pin", "decision_pin"):
        if data[name] is not None:
            _pin(data[name])
    if data["approval_ref"] is not None:
        text_value(data["approval_ref"])
    text_value(data["declared_status"])
    return data["terms_pin"] is not None


def _identity(value: os.stat_result) -> tuple[int, int, int, int]:
    # mtime is a concurrent-read guard only, never a publication/capture witness.
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


def _directory(root_fd: int, parts: list[str]) -> int:
    fd = os.dup(root_fd)
    try:
        for component in parts:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read_html_relative(root_fd: int, pin: FilePin) -> bytes:
    safe_relative(pin.relative_path)
    parts = pin.relative_path.split("/")
    parent = _directory(root_fd, parts[:-1])
    try:
        named_before = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        require(stat.S_ISREG(named_before.st_mode), "UNSAFE_SOURCE_PATH")
        leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            before = os.fstat(leaf)
            require(
                stat.S_ISREG(before.st_mode) and _identity(before) == _identity(named_before),
                "UNSAFE_SOURCE_PATH",
            )
            require(0 < before.st_size <= MAX_BODY, "HTML_BODY_SIZE_LIMIT")
            require(before.st_size == pin.byte_length, "SOURCE_PIN_MISMATCH")
            data = bytearray()
            while len(data) <= MAX_BODY:
                chunk = os.read(leaf, min(65536, MAX_BODY + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            after = os.fstat(leaf)
            # Re-resolve from the still-open root to catch path/directory replacement,
            # including a replacement with identical bytes and a different inode.
            current_parent = _directory(root_fd, parts[:-1])
            try:
                named_after = os.stat(parts[-1], dir_fd=current_parent, follow_symlinks=False)
                require(
                    _identity(before) == _identity(after) == _identity(named_after)
                    and stat.S_ISREG(named_after.st_mode),
                    "SOURCE_CHANGED_DURING_READ",
                )
            finally:
                os.close(current_parent)
            require(
                len(data) == before.st_size and len(data) <= MAX_BODY,
                "PARTIAL_OR_OVERSIZED_SOURCE_READ",
            )
            body = bytes(data)
            require(sha256(body).hexdigest() == pin.sha256, "SOURCE_PIN_MISMATCH")
            return body
        finally:
            os.close(leaf)
    finally:
        os.close(parent)


def observe_html_code(repository: Path) -> tuple[CodePin, ...]:
    """Explicit two-module observation, without widening any prior observer."""
    fd = _open_root(repository)
    try:
        return tuple(
            CodePin(path, sha256(_read_relative(fd, path, MAX_BODY)).hexdigest())
            for path in CODE_PATHS
        )
    finally:
        os.close(fd)


def inspect_issuer_html(
    root: Path,
    pin: FilePin,
    spec: HtmlProfileSpec,
    code: tuple[CodePin, ...],
    rights_description: bytes | None = None,
) -> HtmlIntakeResult:
    """Rights-first formal path. Only synthetic inputs can reach file I/O in RS2."""
    if real_bw_disabled(pin, spec):
        return HtmlIntakeResult(
            pin, spec, "BUSINESS_WIRE_REAL_BODY_DISABLED", "BUSINESS_WIRE_REAL_BODY_DISABLED"
        )
    attempts: tuple[str, ...] = ()
    description_hash: str | NotEvaluated = ABSENT
    root_fd: int | None = None
    try:
        validate_spec(spec, code)
        require(
            root.is_absolute() and ".." not in root.parts and len(root.parts) > 2,
            "UNSAFE_SOURCE_PATH",
        )
        has_terms_pin = False
        if rights_description is not None:
            require(type(rights_description) is bytes, "INVALID_RIGHTS_DESCRIPTION")
            require(len(rights_description) <= MAX_METADATA_BYTES, "RIGHTS_DESCRIPTION_SIZE_LIMIT")
            description_hash = sha256(rights_description).hexdigest()
            has_terms_pin = _description(rights_description, pin, spec, code)
        if spec.classification != "SYNTHETIC_TEST_ONLY":
            # No callable verifier/override is accepted: there is no independently
            # approved approval-verification contract in the current repository.
            reason = "OWNER_APPROVAL_UNVERIFIED" if has_terms_pin else "RIGHTS_DOCUMENTARY_GAP"
            return HtmlIntakeResult(
                pin, spec, "RIGHTS_PENDING", reason, description_sha256=description_hash
            )
        require(
            root.parts[:2] == ("/", "tmp") and len(root.parts) > 2,
            "SYNTHETIC_INPUT_REQUIRES_ISOLATED_TMP_ROOT",
        )
        require(pin.sha256 != SEC_SHA, "REAL_SOURCE_CANNOT_BE_RELABELLED_SYNTHETIC")
        root_fd = _open_root(root)
        original_root = os.fstat(root_fd)
        attempts = (pin.relative_path,)
        body = _read_html_relative(root_fd, pin)
        current_root = _open_root(root)
        try:
            require(
                _identity(original_root) == _identity(os.fstat(current_root)),
                "SOURCE_ROOT_CHANGED_DURING_READ",
            )
        finally:
            os.close(current_root)
        observation = extract_html(body, pin, spec, code)
        status = (
            "DOCUMENT_CONTENT_OBSERVED_UNADMITTED"
            if isinstance(observation, HtmlEvidenceObservation)
            else observation.status
        )
        reason = (
            "SYNTHETIC_ONLY_NO_REAL_RIGHTS_ADMISSION"
            if isinstance(observation, HtmlEvidenceObservation)
            else observation.reason
        )
        return HtmlIntakeResult(pin, spec, status, reason, observation, attempts, description_hash)
    except ContractError as exc:
        return HtmlIntakeResult(
            pin,
            spec,
            "STRUCTURAL_REFUSAL",
            str(exc),
            body_read_attempts=attempts,
            description_sha256=description_hash,
        )
    except OSError:
        return HtmlIntakeResult(
            pin,
            spec,
            "STRUCTURAL_REFUSAL",
            "UNSAFE_SOURCE_PATH_OR_READ",
            body_read_attempts=attempts,
            description_sha256=description_hash,
        )
    finally:
        if root_fd is not None:
            os.close(root_fd)
