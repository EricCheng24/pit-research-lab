"""Four issued Weekly diagnostics; detached read bytes confer no admission.

Raw inputs and actual Native receipts stay in private audit records. The sole
read entrypoint returns bytes or a closed withholding reason, never that graph.
This is interface isolation and local disk consistency, not process attestation.
"""

import json
import re
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path, PurePosixPath
from time import perf_counter
from typing import Literal

from pit_research_lab.domain.contracts import NotEvaluated
from pit_research_lab.domain.derivation import DerivedResult, FeatureSpec
from pit_research_lab.domain.ratio import FixedRatio, RatioFeatureSpec, RatioResult
from pit_research_lab.mvp.f2 import derived_observations as a04
from pit_research_lab.mvp.f2 import ratio_observations as a05
from pit_research_lab.mvp.f2.synthetic_contracts import decode_input_bytes
from pit_research_lab.mvp.f2.synthetic_temporal import (
    WeekAnnotation,
    build_pack,
    build_weekly_requests,
    verify_input_pack,
)

__all__ = ["DiagnosticReadWithheld", "run_weekly_sequence"]
MODULE_PATH = "src/pit_research_lab/mvp/f2/weekly_sequence.py"
TEST_PATH = "tests/unit/mvp_f2/test_weekly_sequence.py"
SOURCE_PINS = (
    (
        "tests/unit/mvp_f2/data/temporal_foundation_v0.1.json",
        "3b81aae8e3242468c3076911861a13b6f1646f42d068be67b316af9caef1c373",
        72_800,
    ),
    (
        "tests/unit/mvp_f2/data/derived_observations_v0.1.json",
        "b9e1babbcc86b0e70ed5589972259fcbe6b666a38d2e7eff77d108f448e4dc0e",
        5_440_756,
    ),
)
CODE_PATHS = (
    MODULE_PATH,
    "src/pit_research_lab/mvp/f2/synthetic_temporal.py",
    "src/pit_research_lab/mvp/f2/synthetic_contracts.py",
    *a05.LOCAL_PATHS,
)
STATUS_PATHS = frozenset(
    (
        MODULE_PATH,
        TEST_PATH,
        *a05.LOCAL_PATHS,
        "src/pit_research_lab/mvp/f2/causal_observations.py",
        "tests/unit/mvp_f2/test_ratio_observations.py",
        "tests/unit/mvp_f2/test_causal_observations.py",
    )
)
TICK_SHA256S = (
    "909050c0cc90f0e16361891e9fa2b2233a363aa35de5278a38b838d97baea046",
    "be50dadac52fee5a266b56dbd4448275cf331078af554050713bcdf4471fe1fa",
    "56c8ca0ff123301adc894e65738209c7987e91d31a9c9b35597e3ae44c0abed8",
    "beaf6dff59c87f22f9384a5d1ce3017a1192dbf2167e51b0c9b54d389eb107e8",
)
_SCOPE = {
    "diagnostic_only": True,
    "admission_eligible": False,
    "trust": "NOT_TRUSTED_PIT_EVIDENCE",
    "source_authentication": "NOT_ESTABLISHED",
    "disposition": "INTEGRATED_PROVISIONAL",
}
type _NativeOutcome = (
    a05.RatioDiagnostic | a05.InvocationFailure | a05.ObservationFailure | a05.MappingRefusal
)
type _NativeAttempt = a05.NativeRatioAttempt | a05.InvocationFailure | a05.MappingRefusal


@dataclass(frozen=True, slots=True)
class DiagnosticReadWithheld:
    """No audit reference, callback, source body or success-by-default value."""

    reason: str
    native_invocations: tuple[str, ...]
    diagnostic_only: Literal[True] = field(default=True, init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)


@dataclass(frozen=True, slots=True)
class _Unavailable:
    reason: str


@dataclass(frozen=True, slots=True)
class _Observation:
    head: str
    tree: str
    status: str
    code_pins: tuple[tuple[str, str, int], ...]
    source_pins: tuple[tuple[str, str, int], ...]
    wu03: a04.WU03ObservedCodeInput
    ratio: a05.ObservedRatioCode


@dataclass(frozen=True, slots=True)
class _Refusal:
    reason: str
    native_invocation: Literal["NOT_RUN"] = field(default="NOT_RUN", init=False)


@dataclass(frozen=True, slots=True)
class _TickAudit:
    index: int
    tick_bytes: bytes
    before: _Observation | _Unavailable
    preinvoke: _Observation | _Unavailable | None
    after: _Observation | _Unavailable | None
    assembly: a05.RatioRequestAssembly | a05.MappingRefusal | None
    attempt: _NativeAttempt | None
    outcome: _NativeOutcome | _Refusal
    outer_reason: str | None
    timings: tuple[tuple[str, float], ...]

    @property
    def native_invocation(self) -> str:
        # Observation drift never overwrites the actual entered operation.
        return self.attempt.native_invocation if self.attempt is not None else "NOT_RUN"


@dataclass(frozen=True, slots=True)
class _SequenceAudit:
    initial: _Observation
    final: _Observation | _Unavailable
    annotations: tuple[WeekAnnotation, ...]
    entries: tuple[_TickAudit, ...]
    read: bytes | DiagnosticReadWithheld
    timings: tuple[tuple[str, float], ...]
    attempt_token: object = field(default_factory=object, compare=False, repr=False)


def _safe_reason(reason: str) -> str:
    return reason if re.fullmatch(r"[A-Z][A-Z0-9_]{0,159}", reason) else "WU04_UNAVAILABLE"


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _root() -> Path:
    module = PurePosixPath(__file__)
    _require(
        module.is_absolute()
        and str(module) == __file__
        and ".." not in module.parts
        and "\\" not in __file__
        and module.parts[-5:] == ("src", "pit_research_lab", "mvp", "f2", "weekly_sequence.py"),
        "WU04_CHECKOUT_LAYOUT_INVALID",
    )
    root = Path(module.parents[4])
    _require(__spec__ is not None and __spec__.origin == __file__, "WU04_OWNER_ORIGIN_MISMATCH")
    for path in CODE_PATHS:
        name = path.removeprefix("src/").removesuffix(".py").replace("/", ".")
        loaded = sys.modules.get(name)
        _require(
            loaded is not None and getattr(loaded, "__file__", None) == str(root / path),
            "WU04_LOADED_OWNER_ROOT_MISMATCH",
        )
    return root


def _regular_bytes(path: Path) -> bytes:
    for part in (*reversed(path.parents), path):
        _require(not part.is_symlink(), "WU04_SYMLINK_REFUSED")
    info = path.stat()
    _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "WU04_NONREGULAR_OR_LINKED")
    return path.read_bytes()


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(root), *args], text=True
    )


def _status_valid(raw: str) -> bool:
    lines = raw.splitlines()
    return (
        raw == "".join(line + "\n" for line in lines)
        and len(lines) == len({line[3:] for line in lines})
        and all(
            len(line) > 3 and line[:3] in {" M ", "?? "} and line[3:] in STATUS_PATHS
            for line in lines
        )
    )


def _pins(paths: tuple[str, ...], bodies: tuple[bytes, ...]) -> tuple[tuple[str, str, int], ...]:
    return tuple((p, sha256(b).hexdigest(), len(b)) for p, b in zip(paths, bodies, strict=True))


def _observe() -> _Observation | _Unavailable:
    """Fixed lexical root, real public witnesses and two reads; no source trust."""
    try:
        root = _root()
        source_paths = tuple(p for p, _, _ in SOURCE_PINS)
        paths = (*CODE_PATHS, *source_paths)
        bodies = tuple(_regular_bytes(root / p) for p in paths)
        _require(_git(root, "rev-parse", "--show-toplevel").strip() == str(root), "WU04_GIT_ROOT")
        status = _git(root, "status", "--short", "--untracked-files=all")
        _require(_status_valid(status), "WU04_DIRTY_STATUS_REFUSED")
        head = _git(root, "rev-parse", "HEAD").strip()
        tree = _git(root, "rev-parse", "HEAD^{tree}").strip()
        _require(_pins(source_paths, bodies[-2:]) == SOURCE_PINS, "WU04_SOURCE_PIN_MISMATCH")
        wu03, ratio = a04.observe_wu03_code(), a05.observe_ratio_diagnostic_code()
        if isinstance(wu03, a04.WU03ObservationUnavailable):
            return _Unavailable(wu03.reason)
        if isinstance(ratio, a05.ObservationUnavailable):
            return _Unavailable(ratio.reason)
        _require(
            wu03.code == ratio.code.upstream_a04
            and wu03.code.head == head
            and wu03.code.head_tree == tree
            and wu03.raw_status == ratio.raw_status == status,
            "WU04_UPSTREAM_OBSERVATION_MISMATCH",
        )
        _require(
            bodies == tuple(_regular_bytes(root / p) for p in paths)
            and status == _git(root, "status", "--short", "--untracked-files=all")
            and head == _git(root, "rev-parse", "HEAD").strip()
            and tree == _git(root, "rev-parse", "HEAD^{tree}").strip(),
            "WU04_OBSERVATION_CHANGED_DURING_READ",
        )
        return _Observation(
            head, tree, status, _pins(CODE_PATHS, bodies[:-2]), SOURCE_PINS, wu03, ratio
        )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return _Unavailable(_safe_reason(str(error)))


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        _require(key not in result, "WU04_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _no_number(_value: str) -> object:
    raise ValueError("WU04_NONEXACT_JSON_NUMBER")


def _preview(body: bytes | NotEvaluated, expected: dict[str, object]) -> None:
    _require(type(body) is bytes, "WU04_NATIVE_PREVIEW_WITHHELD")
    assert isinstance(body, bytes)
    actual: object = json.loads(
        body, object_pairs_hook=_pairs, parse_float=_no_number, parse_constant=_no_number
    )
    _require(
        actual == expected
        and body
        == json.dumps(expected, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(),
        "WU04_NATIVE_PREVIEW_MISMATCH",
    )


def _features(result: RatioResult, cutoff: str) -> dict[str, object] | DiagnosticReadWithheld:
    """Copy approved exact Native values only; never recompute a sum or ratio."""
    try:
        upstream = result.upstream_a04
        _require(isinstance(upstream, DerivedResult), "WU04_A04_NOT_RUN")
        assert isinstance(upstream, DerivedResult)
        spec = FeatureSpec("WU03-A-DERIVED-Q4-2026", 2026, 4, "SYN-A")
        _require(
            upstream.specification == spec
            and result.specification
            == RatioFeatureSpec(a05.FEATURE_REF, spec.feature_ref, "SYN-A", 2026, 4),
            "WU04_FEATURE_COHORT_MISMATCH",
        )
        for native in (result, upstream):
            _require(
                all(getattr(native, key) == value for key, value in _SCOPE.items()),
                "WU04_NATIVE_SCOPE_MISMATCH",
            )
        for native in (upstream, result):
            if native.outcome.state != "VALUE_AVAILABLE":
                return DiagnosticReadWithheld(_safe_reason(native.outcome.reason), ("RUN",))
        total, share = upstream.outcome.value, result.outcome.value
        _require(type(total) is int and isinstance(share, FixedRatio), "WU04_NATIVE_VALUE_MISSING")
        assert isinstance(share, FixedRatio)
        _preview(
            upstream.diagnostic_preview_bytes,
            {
                "preview_kind": "RESEARCH_DIAGNOSTIC_ONLY",
                "feature_ref": spec.feature_ref,
                "cutoff": cutoff,
                "mode": "public",
                "value": total,
                "missingness": None,
                **_SCOPE,
            },
        )
        _preview(
            result.diagnostic_preview_bytes,
            {
                "preview_kind": "RESEARCH_DIAGNOSTIC_ONLY",
                "feature_ref": a05.FEATURE_REF,
                "cutoff": cutoff,
                "mode": "public",
                "value": share.decimal_text,
                "unit": share.unit,
                "scale": share.scale,
                "absence": None,
                **_SCOPE,
            },
        )
        return {
            "derived_quarter_revenue": {
                "state": upstream.outcome.state,
                "reason": upstream.outcome.reason,
                "value": total,
                "unit": "NTD_thousands",
            },
            "third_month_share": {
                "state": result.outcome.state,
                "reason": result.outcome.reason,
                "value": share.decimal_text,
                "unit": share.unit,
                "scale": share.scale,
            },
        }
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError) as error:
        return DiagnosticReadWithheld(_safe_reason(str(error)), ("RUN",))


def _read(entries: tuple[_TickAudit, ...]) -> bytes | DiagnosticReadWithheld:
    invocations = tuple(entry.native_invocation for entry in entries)
    if (
        len(entries) != 4
        or tuple(e.index for e in entries) != (0, 1, 2, 3)
        or tuple(sha256(e.tick_bytes).hexdigest() for e in entries) != TICK_SHA256S
    ):
        return DiagnosticReadWithheld("WU04_READ_MEMBERSHIP_MISMATCH", invocations)
    rows = []
    for entry in entries:
        outcome = entry.outcome
        if entry.outer_reason is not None or not isinstance(outcome, a05.RatioDiagnostic):
            reason = entry.outer_reason or getattr(
                outcome, "reason", getattr(outcome, "code", "WU04_NATIVE_FAILED")
            )
            return DiagnosticReadWithheld(
                _safe_reason(reason) if isinstance(reason, str) else "WU04_NATIVE_FAILED",
                invocations,
            )
        tick = decode_input_bytes(entry.tick_bytes)
        cutoff = tick["cutoff"]["source_text"]
        features = _features(outcome.native_result, cutoff)
        if isinstance(features, DiagnosticReadWithheld):
            return DiagnosticReadWithheld(features.reason, invocations)
        rows.append(
            {
                "tick_id": tick["tick_id"],
                "tick_order": entry.index,
                "decision_cutoff": cutoff,
                "timezone_name": "Asia/Taipei",
                "precision": "SECOND",
                "issuer_ref": "SYN-A",
                "features": features,
            }
        )
    return json.dumps(
        {"schema_version": "wu04-weekly-diagnostic-read-v0.1", **_SCOPE, "ticks": rows},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()


def _execute(exact_ticks: tuple[bytes, ...] | None) -> _SequenceAudit | _Refusal:
    """Private audit seam; only run_weekly_sequence releases detached read data."""
    started = perf_counter()
    initial = _observe()
    if isinstance(initial, _Unavailable):
        return _Refusal(initial.reason)
    try:
        root = _root()
        foundation_bytes, packet = tuple(_regular_bytes(root / p) for p, _, _ in SOURCE_PINS)
        _require(
            _pins(tuple(p for p, _, _ in SOURCE_PINS), (foundation_bytes, packet)) == SOURCE_PINS,
            "WU04_SOURCE_CHANGED",
        )
        foundation = decode_input_bytes(foundation_bytes)
        _require(
            type(foundation["default_seed"]) is int and foundation["default_seed"] == 17,
            "WU04_SEED",
        )
        built = perf_counter()
        pack = build_pack(foundation["input_spec"], foundation["default_seed"])
        verify_input_pack(pack)
        _require(pack.payload_sha256 == a04.PACK_SHA256, "WU04_PACK_PIN_MISMATCH")
        schedule = build_weekly_requests(pack)
        ticks = schedule.requests
        _require(
            type(ticks) is tuple
            and len(ticks) == 4
            and all(type(t) is bytes and len(t) == 672 for t in ticks)
            and tuple(sha256(t).hexdigest() for t in ticks) == TICK_SHA256S
            and schedule.annotations == (WeekAnnotation("2027-W03"),),
            "WU04_SCHEDULE_MISMATCH",
        )
        _require(
            exact_ticks is None
            or (
                type(exact_ticks) is tuple
                and all(type(t) is bytes for t in exact_ticks)
                and exact_ticks == ticks
            ),
            "WU04_TICK_TUPLE_MISMATCH",
        )
        built_seconds = perf_counter() - built
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        return _Refusal(_safe_reason(str(error)))
    entries = []
    for index, tick in enumerate(ticks):
        before = _observe()
        preinvoke: _Observation | _Unavailable | None = None
        after: _Observation | _Unavailable | None = None
        assembly: a05.RatioRequestAssembly | a05.MappingRefusal | None = None
        attempt: _NativeAttempt | None = None
        outcome: _NativeOutcome | _Refusal
        outer_reason = None
        phases = []
        if isinstance(before, _Unavailable) or before != initial:
            outcome = _Refusal(
                before.reason if isinstance(before, _Unavailable) else "WU04_BEFORE_CHANGED"
            )
        else:
            phase = perf_counter()
            assembly = a05.prepare_ratio_request(pack, tick, packet, before.wu03, before.ratio)
            phases.append(("prepare", perf_counter() - phase))
            if isinstance(assembly, a05.MappingRefusal):
                outcome = assembly
            else:
                preinvoke = _observe()
                if preinvoke != before:
                    outcome = _Refusal(
                        preinvoke.reason
                        if isinstance(preinvoke, _Unavailable)
                        else "WU04_PREINVOKE_CHANGED"
                    )
                else:
                    phase = perf_counter()
                    attempt = a05.invoke_ratio(assembly)
                    phases.append(("invoke", perf_counter() - phase))
                    phase = perf_counter()
                    after = _observe()
                    if isinstance(attempt, a05.MappingRefusal):
                        outcome = attempt
                    else:
                        # Even local source/owner drift retains a real public finalization.
                        after_ratio = (
                            after.ratio
                            if isinstance(after, _Observation)
                            else a05.observe_ratio_diagnostic_code()
                        )
                        after_wu03 = (
                            after.wu03
                            if isinstance(after, _Observation)
                            else a04.observe_wu03_code()
                        )
                        outcome = a05.finalize_ratio_diagnostic(attempt, after_ratio, after_wu03)
                    if after != before:
                        outer_reason = (
                            after.reason
                            if isinstance(after, _Unavailable)
                            else "WU04_AFTER_CHANGED"
                        )
                    phases.append(("finalize_and_observe", perf_counter() - phase))
        entries.append(
            _TickAudit(
                index,
                tick,
                before,
                preinvoke,
                after,
                assembly,
                attempt,
                outcome,
                outer_reason,
                tuple(phases),
            )
        )
    frozen = tuple(entries)
    phase = perf_counter()
    read = _read(frozen)
    final = _observe()
    if final != initial:
        read = DiagnosticReadWithheld(
            final.reason if isinstance(final, _Unavailable) else "WU04_RELEASE_CHANGED",
            tuple(entry.native_invocation for entry in frozen),
        )
    timings = (
        ("build_pack_schedule", built_seconds),
        ("read", perf_counter() - phase),
        ("total", perf_counter() - started),
    )
    return _SequenceAudit(initial, final, schedule.annotations, frozen, read, timings)


def run_weekly_sequence(
    exact_ticks: tuple[bytes, ...] | None = None, /
) -> bytes | DiagnosticReadWithheld:
    """Execute only the fixed source cohort; return no reachable audit/Native graph.

    Optional exact ticks are an equality assertion, not a custom schedule. Inputs
    are read from the two literal accepted source paths under the loaded root.
    """
    audit = _execute(exact_ticks)
    if isinstance(audit, _Refusal):
        return DiagnosticReadWithheld(_safe_reason(audit.reason), ())
    return audit.read
