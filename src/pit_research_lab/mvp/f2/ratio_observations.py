"""Bounded WU03-B1 observation of the accepted weekly SYN-A Native A05 path.

Only WU03-A's public preparation issues source inputs. Native owns all source,
sum, ratio and missingness decisions. Disk observations are not attestations.
"""

import json
import re
import stat
import subprocess
import sys
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Literal

from pit_research_lab.domain import contracts as c
from pit_research_lab.domain import ratio_slice
from pit_research_lab.domain.ratio import RatioCodeObservation, RatioFeatureSpec, RatioResult
from pit_research_lab.mvp.f2 import derived_observations as upstream
from pit_research_lab.mvp.f2.derived_observations import WU03RequestAssembly
from pit_research_lab.mvp.f2.synthetic_temporal import SyntheticInputPack

ADAPTER_PATH = "src/pit_research_lab/mvp/f2/ratio_observations.py"
FEATURE_REF = "WU03-B1-THIRD-MONTH-SHARE-Q4-2026"
EXTENSION_PINS = (
    (
        "src/pit_research_lab/domain/ratio.py",
        "018953c2631bb197ff505ec1cb14ab4191b46ebfbcca4670017080e7cafd6996",
        13_897,
    ),
    (
        "src/pit_research_lab/domain/ratio_slice.py",
        "499ba15fcbb772aac3cbb9a9b88b883a7c3b9ee506aeb15f5957d9d47e67673a",
        1_805,
    ),
)
NATIVE_PINS = (*upstream.NATIVE_PINS, *EXTENSION_PINS)
LOCAL_PATHS = (
    ADAPTER_PATH,
    "src/pit_research_lab/mvp/f2/native_requests.py",
    "src/pit_research_lab/mvp/f2/asof_requests.py",
    "src/pit_research_lab/mvp/f2/derived_observations.py",
)
STATUS_PATHS = frozenset(
    (
        *LOCAL_PATHS,
        "tests/unit/mvp_f2/test_ratio_observations.py",
        "tests/unit/mvp_f2/data/ratio_observations_v0.1.json",
    )
)
_OBSERVED = object()
_PREPARED = object()
_INVOKED = object()


@dataclass(frozen=True, slots=True)
class _DiagnosticScope:
    """Closed engineering labels; they never imply execution or admission."""

    diagnostic_only: Literal[True] = field(default=True, init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)
    disposition: Literal["INTEGRATED_PROVISIONAL"] = field(
        default="INTEGRATED_PROVISIONAL", init=False
    )
    trust: Literal["NOT_TRUSTED_PIT_EVIDENCE"] = field(
        default="NOT_TRUSTED_PIT_EVIDENCE", init=False
    )
    source_authentication: Literal["NOT_ESTABLISHED"] = field(default="NOT_ESTABLISHED", init=False)


@dataclass(frozen=True, slots=True)
class ObservationUnavailable(_DiagnosticScope):
    reason: str


@dataclass(frozen=True, slots=True)
class ObservedRatioCode(_DiagnosticScope):
    code: RatioCodeObservation
    checkout_root: str
    local_pins: tuple[tuple[str, str, int], ...]
    raw_status: str
    _witness: object | None = field(default=None, init=False, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class MappingRefusal(_DiagnosticScope):
    stage: str
    reason: str
    exact_exception_type: str | None = None
    native_invocation: Literal["NOT_RUN"] = field(default="NOT_RUN", init=False)


@dataclass(frozen=True, slots=True)
class RatioRequestAssembly(_DiagnosticScope):
    upstream: WU03RequestAssembly
    specification: RatioFeatureSpec
    before_observation: ObservedRatioCode
    input_digest: str
    pack: SyntheticInputPack
    _witness: object | None = field(default=None, init=False, repr=False, compare=False)
    _issued_upstream: WU03RequestAssembly | None = field(
        default=None, init=False, repr=False, compare=False
    )


@dataclass(frozen=True, slots=True)
class NativeRatioAttempt(_DiagnosticScope):
    assembly: RatioRequestAssembly
    native_result: RatioResult
    native_invocation: Literal["RUN"] = field(default="RUN", init=False)
    _witness: object | None = field(default=None, init=False, repr=False, compare=False)
    _result_digest: str = field(default="", init=False, repr=False, compare=False)
    _issued_assembly: RatioRequestAssembly | None = field(
        default=None, init=False, repr=False, compare=False
    )


@dataclass(frozen=True, slots=True)
class InvocationFailure(_DiagnosticScope):
    assembly: RatioRequestAssembly
    exact_native_exception_type: str
    code: str
    native_invocation: Literal["ATTEMPTED"] = field(default="ATTEMPTED", init=False)
    _witness: object | None = field(default=None, init=False, repr=False, compare=False)
    _issued_assembly: RatioRequestAssembly | None = field(
        default=None, init=False, repr=False, compare=False
    )


@dataclass(frozen=True, slots=True)
class RatioDiagnostic(_DiagnosticScope):
    source_identity: tuple[tuple[str, str], ...]
    identity: str
    native_result: RatioResult
    observations: tuple[ObservedRatioCode, ObservedRatioCode]
    upstream_observations: tuple[upstream.WU03ObservedCodeInput, upstream.WU03ObservedCodeInput]
    native_invocation: Literal["RUN"] = field(default="RUN", init=False)


@dataclass(frozen=True, slots=True)
class ObservationFailure(_DiagnosticScope):
    reason: str
    preserved: NativeRatioAttempt | InvocationFailure
    after_observation: ObservedRatioCode | ObservationUnavailable
    after_upstream_observation: upstream.WU03ObservedCodeInput | upstream.WU03ObservationUnavailable
    native_invocation: Literal["RUN", "ATTEMPTED"] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "native_invocation", self.preserved.native_invocation)


def _root() -> Path:
    module = PurePosixPath(__file__)
    c.require(
        module.is_absolute()
        and ".." not in module.parts
        and "\\" not in str(module)
        and module.parts[-5:] == ("src", "pit_research_lab", "mvp", "f2", "ratio_observations.py"),
        "B1_CHECKOUT_LAYOUT_INVALID",
    )
    root = Path(module.parents[4])
    # Lexical loaded-owner checks precede all I/O through a claimed root.
    c.require(
        __spec__ is not None
        and __spec__.origin == __file__
        and upstream.__file__ == str(root / LOCAL_PATHS[-1]),
        "B1_LOADED_OWNER_ROOT_MISMATCH",
    )
    for path, _, _ in NATIVE_PINS:
        name = path.removeprefix("src/").removesuffix(".py").replace("/", ".")
        loaded = sys.modules.get(name.removesuffix(".__init__"))
        c.require(
            loaded is not None and getattr(loaded, "__file__", None) == str(root / path),
            "B1_LOADED_OWNER_ROOT_MISMATCH",
        )
    return root


def _regular_bytes(path: Path) -> bytes:
    for component in (*reversed(path.parents), path):
        c.require(not component.is_symlink(), "B1_SYMLINK_REFUSED")
    info = path.stat()
    c.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "B1_NONREGULAR_OR_LINKED")
    return path.read_bytes()


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(root), *args], text=True
    )


def _status_valid(raw: str) -> bool:
    return all(
        len(line) > 3 and line[:3] in {" M ", "?? "} and line[3:] in STATUS_PATHS
        for line in raw.splitlines()
    )


def _observation_reason(value: ObservedRatioCode | ObservationUnavailable) -> str | None:
    if isinstance(value, ObservationUnavailable):
        return value.reason
    if not isinstance(value, ObservedRatioCode) or value._witness is not _OBSERVED:
        return "B1_OBSERVATION_NOT_ISSUED"
    code = value.code
    base = code.upstream_a04
    pins = (*base.observed_working_files, *code.extension_pins)
    lengths = (*base.byte_lengths, *code.extension_byte_lengths)
    if (
        value.checkout_root != str(_root())
        or not _status_valid(value.raw_status)
        or base.worktree_status != value.raw_status.strip()
        or len(pins) != len(lengths)
        or any(type(n) is not int for n in lengths)
        or tuple((p.path, p.sha256, n) for p, n in zip(pins, lengths, strict=True)) != NATIVE_PINS
        or tuple(p for p, _, _ in value.local_pins) != LOCAL_PATHS
        or any(
            re.fullmatch("[0-9a-f]{64}", h) is None or type(n) is not int or n <= 0
            for _, h, n in value.local_pins
        )
        or re.fullmatch("[0-9a-f]{40}", base.head) is None
        or re.fullmatch("[0-9a-f]{40}", base.head_tree) is None
        or base.interpretation != code.interpretation
        or code.interpretation != "OBSERVED_DISK_BYTES; HEAD_IS_NOT_COMPLETE_CODE_VERSION"
    ):
        return "B1_OBSERVATION_PIN_OR_SCOPE_MISMATCH"
    return None


def observe_ratio_diagnostic_code() -> ObservedRatioCode | ObservationUnavailable:
    """Observe fixed Native/local bytes twice; no caller-selected root or source."""
    try:
        root = _root()
        paths = (*LOCAL_PATHS, *(p for p, _, _ in NATIVE_PINS))
        before = tuple(_regular_bytes(root / p) for p in paths)
        c.require(
            _git(root, "rev-parse", "--show-toplevel").strip() == str(root),
            "B1_GIT_ROOT_MISMATCH",
        )
        status = _git(root, "status", "--short", "--untracked-files=all")
        c.require(_status_valid(status), "B1_DIRTY_STATUS_REFUSED")
        head = _git(root, "rev-parse", "HEAD").strip()
        tree = _git(root, "rev-parse", "HEAD^{tree}").strip()
        c.require(
            tuple(
                (p, sha256(b).hexdigest(), len(b))
                for (p, _, _), b in zip(NATIVE_PINS, before[len(LOCAL_PATHS) :], strict=True)
            )
            == NATIVE_PINS,
            "B1_NATIVE_DISK_PIN_MISMATCH",
        )
        code = ratio_slice.observe_ratio_code(root)
        c.require(
            before == tuple(_regular_bytes(root / p) for p in paths)
            and status == _git(root, "status", "--short", "--untracked-files=all")
            and head == code.upstream_a04.head == _git(root, "rev-parse", "HEAD").strip()
            and tree
            == code.upstream_a04.head_tree
            == _git(root, "rev-parse", "HEAD^{tree}").strip(),
            "B1_OBSERVATION_CHANGED_DURING_READ",
        )
        local = tuple(
            (p, sha256(b).hexdigest(), len(b))
            for p, b in zip(LOCAL_PATHS, before[: len(LOCAL_PATHS)], strict=True)
        )
        value = ObservedRatioCode(code, str(root), local, status)
        object.__setattr__(value, "_witness", _OBSERVED)
        if reason := _observation_reason(value):
            return ObservationUnavailable(reason)
        return value
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return ObservationUnavailable(str(error))


def _identity_value(value: object) -> object:
    """Internal identity encoding only; not an input decoder or output protocol."""
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "type": type(value).__name__,
            **{f.name: getattr(value, f.name) for f in fields(value)},
        }
    if isinstance(value, bytes):
        return {"sha256": sha256(value).hexdigest(), "byte_length": len(value)}
    if isinstance(value, date):
        return {"date": value.isoformat()}
    raise TypeError("B1_UNSUPPORTED_IDENTITY_VALUE")


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value, default=_identity_value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _input_digest(
    issued: WU03RequestAssembly,
    spec: RatioFeatureSpec,
    before: ObservedRatioCode,
    pack: SyntheticInputPack,
) -> str:
    return _digest(
        (
            "WU03-B1-INPUT-v0.1",
            pack,
            issued.specification,
            issued.slots,
            issued.source_packet_bytes,
            issued.exact_tick_bytes,
            issued.source_identity,
            issued.request_digest,
            issued.before_observation.code,
            issued.before_observation.checkout_root,
            issued.before_observation.adapter_sha256,
            issued.before_observation.raw_status,
            spec,
            before.code,
            before.checkout_root,
            before.local_pins,
            before.raw_status,
        )
    )


def _spec(issued: upstream.WU03RequestAssembly) -> RatioFeatureSpec:
    spec = issued.specification
    return RatioFeatureSpec(FEATURE_REF, spec.feature_ref, spec.issuer_ref, spec.year, spec.quarter)


def prepare_ratio_request(
    pack: SyntheticInputPack,
    exact_tick_bytes: bytes,
    source_packet_bytes: bytes,
    wu03_observation: upstream.WU03ObservedCodeInput | upstream.WU03ObservationUnavailable,
    ratio_observation: ObservedRatioCode | ObservationUnavailable,
    /,
) -> RatioRequestAssembly | MappingRefusal:
    try:
        if reason := _observation_reason(ratio_observation):
            return MappingRefusal("S01_OBSERVATION", reason)
        assert isinstance(ratio_observation, ObservedRatioCode)
        issued = upstream.prepare_derived_request(
            pack, exact_tick_bytes, source_packet_bytes, wu03_observation
        )
        if isinstance(issued, upstream.WU03MappingRefusal):
            return MappingRefusal(issued.stage, issued.reason, issued.exact_exception_type)
        if (
            issued.before_observation.code != ratio_observation.code.upstream_a04
            or issued.before_observation.adapter_sha256 != ratio_observation.local_pins[-1][1]
        ):
            return MappingRefusal("S02_UPSTREAM", "B1_UPSTREAM_OBSERVATION_MISMATCH")
        spec = _spec(issued)
        result = RatioRequestAssembly(
            issued,
            spec,
            ratio_observation,
            _input_digest(issued, spec, ratio_observation, pack),
            pack,
        )
        object.__setattr__(result, "_witness", _PREPARED)
        object.__setattr__(result, "_issued_upstream", issued)
        return result
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        return MappingRefusal("S03_ASSEMBLY", str(error), type(error).__name__)


def _assembly_reason(assembly: RatioRequestAssembly) -> str | None:
    try:
        if (
            not isinstance(assembly, RatioRequestAssembly)
            or assembly._witness is not _PREPARED
            or assembly.upstream is not assembly._issued_upstream
        ):
            return "B1_ASSEMBLY_NOT_ISSUED"
        issued = assembly.upstream
        if reason := _observation_reason(assembly.before_observation):
            return reason
        if (
            len(issued.source_packet_bytes) != upstream.FIXTURE_LENGTH
            or sha256(issued.source_packet_bytes).hexdigest() != upstream.FIXTURE_SHA256
            or assembly.specification != _spec(issued)
            or issued.before_observation.code != assembly.before_observation.code.upstream_a04
            or assembly.input_digest
            != _input_digest(
                issued, assembly.specification, assembly.before_observation, assembly.pack
            )
        ):
            return "B1_ASSEMBLY_CHANGED"
        return None
    except (ValueError, TypeError, AttributeError):
        return "B1_ASSEMBLY_CHANGED"


def invoke_ratio(
    assembly: RatioRequestAssembly, /
) -> NativeRatioAttempt | InvocationFailure | MappingRefusal:
    """Only the public Native A05 owner computes; unissued inputs never invoke it."""
    if reason := _assembly_reason(assembly):
        return MappingRefusal("S04_INVOCATION", reason)
    try:
        issued = assembly.upstream
        result = ratio_slice.evaluate_ratio(
            assembly.specification,
            issued.specification,
            issued.slots,
            assembly.before_observation.code,
        )
    except Exception as error:
        safe_code = str(error)
        if re.fullmatch("[A-Z][A-Z0-9_]{0,159}", safe_code) is None:
            safe_code = "B1_NATIVE_EXCEPTION"
        attempt: NativeRatioAttempt | InvocationFailure = InvocationFailure(
            assembly, type(error).__name__, safe_code
        )
    else:
        attempt = NativeRatioAttempt(assembly, result)
        object.__setattr__(attempt, "_result_digest", _digest(result))
    object.__setattr__(attempt, "_witness", _INVOKED)
    object.__setattr__(attempt, "_issued_assembly", assembly)
    return attempt


def finalize_ratio_diagnostic(
    attempt: NativeRatioAttempt | InvocationFailure,
    after_ratio_observation: ObservedRatioCode | ObservationUnavailable,
    after_wu03_observation: upstream.WU03ObservedCodeInput | upstream.WU03ObservationUnavailable,
    /,
) -> RatioDiagnostic | InvocationFailure | ObservationFailure:
    """Retain actual RUN/ATTEMPTED evidence on drift; no new numerical/display policy."""
    if attempt._witness is not _INVOKED:
        raise ValueError("B1_ISSUED_ATTEMPT_REQUIRED")
    assembly = attempt.assembly
    reason = (
        "B1_ATTEMPT_ASSEMBLY_CHANGED"
        if assembly is not attempt._issued_assembly
        else _assembly_reason(assembly)
    )
    if reason is None:
        reason = _observation_reason(after_ratio_observation)
    if reason is None and assembly.before_observation != after_ratio_observation:
        reason = "B1_OBSERVATION_CHANGED"
    if reason is None and assembly.upstream.before_observation != after_wu03_observation:
        reason = "B1_UPSTREAM_OBSERVATION_CHANGED"
    if reason is None:
        # Validate the supplied WU03 after witness through its PUBLIC preparation
        # boundary; never call a private upstream validator or forge an attempt.
        refreshed = upstream.prepare_derived_request(
            assembly.pack,
            assembly.upstream.exact_tick_bytes,
            assembly.upstream.source_packet_bytes,
            after_wu03_observation,
        )
        if isinstance(refreshed, upstream.WU03MappingRefusal):
            reason = "B1_UPSTREAM_AFTER_REFUSED:" + refreshed.reason
        elif refreshed != assembly.upstream:
            reason = "B1_UPSTREAM_ASSEMBLY_CHANGED"
    if (
        reason is None
        and isinstance(attempt, NativeRatioAttempt)
        and _digest(attempt.native_result) != attempt._result_digest
    ):
        reason = "B1_NATIVE_RESULT_CHANGED"
    if reason is not None:
        return ObservationFailure(reason, attempt, after_ratio_observation, after_wu03_observation)
    if isinstance(attempt, InvocationFailure):
        return attempt
    assert isinstance(after_ratio_observation, ObservedRatioCode)
    assert isinstance(after_wu03_observation, upstream.WU03ObservedCodeInput)
    identity = "WU03-B1-DIAGNOSTIC-" + _digest(
        (assembly.input_digest, attempt.native_result.realization_ref, attempt._result_digest)
    )
    return RatioDiagnostic(
        assembly.upstream.source_identity,
        identity,
        attempt.native_result,
        (assembly.before_observation, after_ratio_observation),
        (assembly.upstream.before_observation, after_wu03_observation),
    )
