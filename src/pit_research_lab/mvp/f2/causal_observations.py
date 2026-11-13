"""Closed R1 midnight input adoption and observed public Native B03 diagnostic.

This synthetic engineering adoption authenticates no publisher. Native alone
selects, derives, qualifies the universe and projects the audited candidate.
"""

import base64
import json
import re
import stat
import subprocess
import sys
import time
import zlib
from dataclasses import dataclass, field, fields, is_dataclass, replace
from datetime import date
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pit_research_lab.domain import causal_derivation as b03
from pit_research_lab.domain import causal_slice
from pit_research_lab.domain import contracts as c
from pit_research_lab.domain import diagnostic_projection as dp
from pit_research_lab.domain import selection as s
from pit_research_lab.domain.asof_slice import AsOfRequest
from pit_research_lab.domain.derivation import DependencySlot, FeatureSpec
from pit_research_lab.domain.ratio import RatioFeatureSpec
from pit_research_lab.mvp.f2 import asof_requests, native_requests
from pit_research_lab.mvp.f2 import derived_observations as a04
from pit_research_lab.mvp.f2 import ratio_observations as a05

ADAPTER_PATH = "src/pit_research_lab/mvp/f2/causal_observations.py"
FIXTURE_PATH = "tests/unit/mvp_f2/data/causal_observations_v0.1.json"
OLD_SOURCE_PATH = "tests/unit/mvp_f2/data/derived_observations_v0.1.json"
NEW_PATHS = (ADAPTER_PATH, "tests/unit/mvp_f2/test_causal_observations.py", FIXTURE_PATH)
LOCAL_PATHS = (
    ADAPTER_PATH,
    "src/pit_research_lab/mvp/f2/native_requests.py",
    "src/pit_research_lab/mvp/f2/asof_requests.py",
    "src/pit_research_lab/mvp/f2/derived_observations.py",
    "src/pit_research_lab/mvp/f2/ratio_observations.py",
    "tests/unit/mvp_f2/test_ratio_observations.py",
    "tests/unit/mvp_f2/test_causal_observations.py",
)
STATUS_PATHS = frozenset(
    (
        *LOCAL_PATHS,
        FIXTURE_PATH,
        "src/pit_research_lab/mvp/f2/weekly_sequence.py",
        "tests/unit/mvp_f2/test_weekly_sequence.py",
    )
)
EXTENSION_PINS = (
    (
        "src/pit_research_lab/domain/causal_derivation.py",
        "c1bcb2a3f09ec653859f03c2f254895fe91f6471fb298d85e397c97d842f1905",
        30_497,
    ),
    (
        "src/pit_research_lab/domain/causal_slice.py",
        "5970614c8b7d79a1e77ba30d2627bd3ac62645f92494cd73f80b849225140e21",
        13_752,
    ),
    (
        "src/pit_research_lab/domain/diagnostic_projection.py",
        "19ef5b9e1e5cc350c5767468c5ef203bcde7b94e999c6c24060be1b412ddb27b",
        5_877,
    ),
)
NATIVE_PINS = (*a05.NATIVE_PINS, *EXTENSION_PINS)
PACKET_PIN = (1_955_116, "9a07ee74486fdad6534768a1484dc314c621cfb810802b9bcfae3b424085cdf7")
ORACLE_PIN = (1_974, "efd9470925997f5f0595f023fb1bb8efa6a1820ca296fd3bd7b9cd72251199e3")
FIXTURE_PIN = (138008, "3823c5a2e20740a93573c3553ef3613958e3ea4b39a928f01f4f01ccf114cff7")
MD1_CUTOFF = "2027-01-08T00:00:00+08:00"
MD1_CALENDAR = "CONT01-MIDNIGHT-DIAGNOSTIC-CALENDAR-v1"
FEATURE_KEYS = ("derived_quarter_revenue", "third_month_share")
PRIMARY_VIEWS = (
    "MD1-A-M1",
    "MD1-A-M2",
    "MD1-A-M3",
    "MD1-B-M1",
    "MD1-B-M2",
    "MD1-B-M3",
    "MD1-MEM-A",
    "MD1-MEM-B",
)
SOURCE_TAGS = (
    "O",
    "N",
    "D1",
    "D2",
    "D3",
    "N12",
    "N23",
    "B-O",
    "B-N",
    "B-D",
    "MEM-A",
    "MEM-B",
    "Z-O",
    "Z-N",
    "Z-D",
)
VIEW_IDS = (
    *PRIMARY_VIEWS,
    *(v.replace("MD1", "W18") for v in PRIMARY_VIEWS),
    "MD1-Z-M1",
    "MD1-Z-M2",
    "MD1-Z-M3",
    "MD1-B-UNRESOLVED-M3",
)
type NativeUniverse = b03.QualifiedSyntheticUniverse | b03.B03Refusal | c.BlockingFailure
type NativeResult = b03.B03Result | b03.B03Refusal | c.BlockingFailure
type Projection = dp.DiagnosticProjectionCandidate | dp.ProjectionWithheld | dp.ProjectionBlocked


@dataclass(frozen=True, slots=True)
class _Scope:
    diagnostic_only: Literal[True] = field(default=True, init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)
    disposition: str = field(default="INTEGRATED_PROVISIONAL", init=False)
    trust: str = field(default="NOT_TRUSTED_PIT_EVIDENCE", init=False)
    source_authentication: str = field(default="NOT_ESTABLISHED", init=False)


@dataclass(frozen=True, slots=True)
class Refusal(_Scope):
    stage: str
    reason: str
    exact_exception_type: str | None = None
    native_invocation: Literal["NOT_RUN"] = field(default="NOT_RUN", init=False)


@dataclass(frozen=True, slots=True)
class ObservationUnavailable(_Scope):
    reason: str


@dataclass(frozen=True, slots=True)
class _Ticket:
    owner: object
    digest: str


@dataclass(frozen=True, slots=True)
class ObservedCausalCode(_Scope):
    code: b03.B03CodeObservation
    checkout_root: str
    raw_status: str
    local_pins: tuple[tuple[str, str, int], ...]
    source_pins: tuple[tuple[str, str, int], ...]
    _ticket: _Ticket | None = field(default=None, init=False, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class AdoptedInput(_Scope):
    bundle_bytes: bytes
    packet_bytes: bytes
    oracle_bytes: bytes
    sources: tuple[tuple[str, s.CandidateSource], ...]
    views: tuple[tuple[str, AsOfRequest], ...]
    classification: str = field(default="SYNTHETIC_ENGINEERING_DIAGNOSTIC", init=False)
    historical_source_classification: str = field(default="CANDIDATE_NOT_ADOPTED", init=False)


@dataclass(frozen=True, slots=True)
class CausalRequestAssembly(_Scope):
    inputs: AdoptedInput
    request: b03.B03Request
    policy: dp.ProjectionPolicy
    before_observation: ObservedCausalCode
    verification_seconds: float
    _ticket: _Ticket | None = field(default=None, init=False, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class NativeCausalAttempt(_Scope):
    assembly: CausalRequestAssembly
    universe: NativeUniverse | None
    native_result: NativeResult | None
    projection: Projection | None
    native_invocation: Literal["RUN", "ATTEMPTED"]
    stage: str
    exact_exception_type: str | None
    reason: str | None
    timings: tuple[tuple[str, float], ...]
    _ticket: _Ticket | None = field(default=None, init=False, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class CausalDiagnostic(_Scope):
    attempt: NativeCausalAttempt
    observations: tuple[ObservedCausalCode, ObservedCausalCode]
    native_invocation: Literal["RUN", "ATTEMPTED"]


@dataclass(frozen=True, slots=True)
class InvocationFailure(_Scope):
    preserved: NativeCausalAttempt
    observations: tuple[ObservedCausalCode, ObservedCausalCode]
    native_invocation: Literal["ATTEMPTED"] = field(default="ATTEMPTED", init=False)


@dataclass(frozen=True, slots=True)
class ObservationFailure(_Scope):
    reason: str
    preserved: NativeCausalAttempt
    after_observation: ObservedCausalCode | ObservationUnavailable
    native_invocation: Literal["RUN", "ATTEMPTED"] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "native_invocation", self.preserved.native_invocation)


def _identity_value(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "type": type(value).__name__,
            **{f.name: getattr(value, f.name) for f in fields(value) if not f.name.startswith("_")},
        }
    if isinstance(value, bytes):
        return {"sha256": sha256(value).hexdigest(), "byte_length": len(value)}
    if isinstance(value, date):
        return {"date": value.isoformat()}
    raise TypeError("B2_UNSUPPORTED_IDENTITY_VALUE")


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value, default=_identity_value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _stamp(value: ObservedCausalCode | CausalRequestAssembly | NativeCausalAttempt) -> None:
    object.__setattr__(value, "_ticket", _Ticket(value, _digest(value)))


def _issued(value: ObservedCausalCode | CausalRequestAssembly | NativeCausalAttempt) -> bool:
    ticket = value._ticket
    return isinstance(ticket, _Ticket) and ticket.owner is value and ticket.digest == _digest(value)


def _root() -> Path:
    module = PurePosixPath(__file__)
    c.require(
        module.is_absolute()
        and module.as_posix() == __file__
        and ".." not in module.parts
        and "\\" not in __file__
        and module.parts[-5:] == ("src", "pit_research_lab", "mvp", "f2", "causal_observations.py"),
        "B2_CHECKOUT_LAYOUT_INVALID",
    )
    root = Path(module.parents[4])
    c.require(
        asof_requests.__file__ == str(root / LOCAL_PATHS[2])
        and native_requests.__file__ == str(root / LOCAL_PATHS[1]),
        "B2_LOADED_OWNER_ROOT_MISMATCH",
    )
    for path in (ADAPTER_PATH, *LOCAL_PATHS[1:5], *(p for p, _, _ in NATIVE_PINS)):
        name = path.removeprefix("src/").removesuffix(".py").replace("/", ".")
        loaded = sys.modules.get(name.removesuffix(".__init__"))
        spec = getattr(loaded, "__spec__", None)
        c.require(
            loaded is not None
            and getattr(loaded, "__file__", None) == str(root / path)
            and spec is not None
            and spec.origin == str(root / path),
            "B2_LOADED_OWNER_ROOT_MISMATCH",
        )
    return root


def _regular_bytes(path: Path) -> bytes:
    for component in (*reversed(path.parents), path):
        c.require(not component.is_symlink(), "B2_SYMLINK_REFUSED")
    info = path.stat()
    c.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "B2_NONREGULAR_OR_LINKED")
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


def observe_causal_diagnostic_code() -> ObservedCausalCode | ObservationUnavailable:
    """Issue a root-bound before/after witness from actual fixed disk paths."""
    try:
        root = _root()
        native_paths = tuple(p for p, _, _ in NATIVE_PINS)
        source_paths = (FIXTURE_PATH, OLD_SOURCE_PATH)
        paths = (*native_paths, *LOCAL_PATHS, *source_paths)
        bodies = tuple(_regular_bytes(root / p) for p in paths)
        c.require(
            _git(root, "rev-parse", "--show-toplevel").strip() == str(root), "B2_GIT_ROOT_MISMATCH"
        )
        raw = _git(root, "status", "--short", "--untracked-files=all")
        c.require(_status_valid(raw), "B2_DIRTY_STATUS_REFUSED")
        head, tree = (_git(root, "rev-parse", r).strip() for r in ("HEAD", "HEAD^{tree}"))
        c.require(
            all(re.fullmatch("[0-9a-f]{40}", v) is not None for v in (head, tree)),
            "B2_INVALID_GIT_IDENTITY",
        )
        c.require(_pins(native_paths, bodies[:15]) == NATIVE_PINS, "B2_NATIVE_DISK_PIN_MISMATCH")
        source_pins = _pins(source_paths, bodies[-2:])
        c.require(
            source_pins
            == (
                (FIXTURE_PATH, FIXTURE_PIN[1], FIXTURE_PIN[0]),
                (OLD_SOURCE_PATH, a04.FIXTURE_SHA256, a04.FIXTURE_LENGTH),
            ),
            "B2_SOURCE_DISK_PIN_MISMATCH",
        )
        code = causal_slice.observe_causal_code(root)
        base, ratio = code.upstream_ratio.upstream_a04, code.upstream_ratio
        observed_pins = (*base.observed_working_files, *ratio.extension_pins, *code.extension_pins)
        observed_lengths = (
            *base.byte_lengths,
            *ratio.extension_byte_lengths,
            *code.extension_byte_lengths,
        )
        c.require(
            all(type(n) is int for n in observed_lengths)
            and tuple(
                (p.path, p.sha256, n) for p, n in zip(observed_pins, observed_lengths, strict=True)
            )
            == NATIVE_PINS
            and code.profile_ref == b03.PROFILE,
            "B2_NATIVE_OBSERVATION_MISMATCH",
        )
        c.require(
            base.head == head
            and base.head_tree == tree
            and base.worktree_status == raw.strip()
            and bodies == tuple(_regular_bytes(root / p) for p in paths)
            and raw == _git(root, "status", "--short", "--untracked-files=all")
            and head == _git(root, "rev-parse", "HEAD").strip()
            and tree == _git(root, "rev-parse", "HEAD^{tree}").strip(),
            "B2_OBSERVATION_CHANGED_DURING_READ",
        )
        _root()
        result = ObservedCausalCode(
            code, str(root), raw, _pins(LOCAL_PATHS, bodies[15:-2]), source_pins
        )
        _stamp(result)
        return result
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
        return ObservationUnavailable(str(exc))


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        c.require(key not in result, "B2_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _noninteger(_: str) -> Any:
    raise c.ContractError("B2_NONINTEGER_JSON")


def _json(body: bytes, limit: int) -> Any:
    c.require(type(body) is bytes and len(body) <= limit, "B2_JSON_BYTE_LIMIT")
    result = json.loads(
        body.decode("utf-8"),
        object_pairs_hook=_pairs,
        parse_float=_noninteger,
        parse_constant=_noninteger,
    )
    pending = [(result, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        c.require(depth <= 40 and count <= 200_000, "B2_JSON_STRUCTURE_LIMIT")
        if isinstance(item, dict):
            pending.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            pending.extend((v, depth + 1) for v in item)
        else:
            c.require(item is None or type(item) in (str, int, bool), "B2_JSON_VALUE_INVALID")
    return result


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def _pinned(body: bytes, pin: tuple[int, str], reason: str) -> None:
    c.require(
        type(body) is bytes and len(body) == pin[0] and sha256(body).hexdigest() == pin[1], reason
    )


def _blob(value: Any) -> bytes:
    c.require(
        type(value) is dict
        and set(value) == {"utf8", "byte_length", "sha256"}
        and type(value["utf8"]) is str
        and type(value["byte_length"]) is int
        and 0 <= value["byte_length"] <= 1_048_576,
        "B2_BLOB_SCHEMA_INVALID",
    )
    source_text: str = value["utf8"]
    body = source_text.encode("utf-8")
    _pinned(body, (value["byte_length"], value["sha256"]), "B2_BLOB_PIN_MISMATCH")
    return body


def _transport(value: Any, pin: tuple[int, str]) -> bytes:
    c.require(
        type(value) is dict
        and set(value) == {"encoding", "data", "byte_length", "sha256"}
        and value["encoding"] == "zlib+base64"
        and type(value["data"]) is str
        and type(value["byte_length"]) is int
        and (value["byte_length"], value["sha256"]) == pin
        and len(value["data"]) <= 200_000,
        "B2_TRANSPORT_SCHEMA_INVALID",
    )
    compressed = base64.b64decode(value["data"], validate=True)
    stream = zlib.decompressobj()
    body = stream.decompress(compressed, pin[0] + 1)
    c.require(
        stream.eof and not stream.unused_data and not stream.unconsumed_tail,
        "B2_TRANSPORT_NOT_EXACT",
    )
    _pinned(body, pin, "B2_R1_PIN_MISMATCH")
    return body


# Closed grammar for this frozen packet and its seven unchanged old inputs.
# Completed Native objects, feature algorithms and arbitrary constructors are absent.
_INPUTS: dict[str, type[c.Record]] = {
    cls.__name__: cls
    for cls in (
        c.Known,
        c.Unknown,
        c.NotApplicable,
        c.NotEvaluated,
        c.OriginKnownValue,
        c.OriginUnknownValue,
        c.FieldOrigin,
        c.SubjectFacts,
        c.AssertionFacts,
        c.ContentFacts,
        c.RequestedTuple,
        c.PublicationEventFacts,
        c.AwareInstant,
        c.TimeProof,
        c.SupportBinding,
        c.RequestBindingAttempt,
        c.RoleRef,
        c.ContentPin,
        c.SourceRecords,
        c.S1Scope,
        c.IssuerBindingRequest,
        c.CandidateProfile,
        c.CodePin,
        c.TemporalPolicy,
        c.SemanticContext,
        s.CandidateSource,
        s.DirectRelation,
        s.RevisionScope,
        s.SelectionPolicy,
        s.CoverageCheck,
        s.BoundedCoverage,
        s.DiscoveryEvidence,
        s.RelationSource,
        AsOfRequest,
    )
}


def _input(
    value: Any, sources: dict[str, s.CandidateSource], blobs: dict[str, bytes], depth: int = 0
) -> Any:
    c.require(depth <= 40, "B2_INPUT_DEPTH_LIMIT")
    if isinstance(value, list):
        return tuple(_input(v, sources, blobs, depth + 1) for v in value)
    if not isinstance(value, dict):
        c.require(value is None or type(value) in (str, int, bool), "B2_INPUT_VALUE_INVALID")
        return value
    if set(value) == {"source_ref"}:
        c.require(value["source_ref"] in sources, "B2_SOURCE_REFERENCE_INVALID")
        return sources[value["source_ref"]]
    if set(value) == {"blob_ref"}:
        c.require(value["blob_ref"] in blobs, "B2_BLOB_REFERENCE_INVALID")
        return blobs[value["blob_ref"]]
    if set(value) == {"bytes_hex"}:
        c.require(
            type(value["bytes_hex"]) is str and len(value["bytes_hex"]) <= 131_072,
            "B2_RAW_BYTE_LIMIT",
        )
        return bytes.fromhex(value["bytes_hex"])
    if set(value) == {"date"}:
        c.require(type(value["date"]) is str, "B2_DATE_INVALID")
        return date.fromisoformat(value["date"])
    cls = _INPUTS.get(value.get("type", ""))
    c.require(cls is not None, "B2_INPUT_TYPE_REFUSED")
    assert cls is not None
    descriptions = {f.name: f for f in fields(cls)}
    c.require(set(value) == {"type", *descriptions}, "B2_INPUT_FIELDS_INVALID")
    kwargs = {k: _input(v, sources, blobs, depth + 1) for k, v in value.items() if k != "type"}
    if cls in (c.FieldOrigin, c.RoleRef):
        kwargs["visibility"] = c.Visibility(kwargs["visibility"])
    if cls in (c.Unknown, c.OriginUnknownValue):
        kwargs["cause"] = c.UnknownCause(kwargs["cause"])
    result = cls(**{k: v for k, v in kwargs.items() if descriptions[k].init})
    c.require(all(getattr(result, k) == v for k, v in kwargs.items()), "B2_INPUT_DEFAULT_MISMATCH")
    return result


def _verify_view(
    view: Any, request: AsOfRequest, sources: dict[str, s.CandidateSource], blobs: dict[str, bytes]
) -> None:
    c.require(
        set(view)
        == {
            "discovery_blob",
            "notice_inventory",
            "operations",
            "page_blob",
            "profile",
            "request",
            "source_inventory",
            "view_id",
        },
        "B2_VIEW_SCHEMA_INVALID",
    )
    evidence = request.discovery
    c.require(isinstance(evidence, s.DiscoveryEvidence), "B2_DISCOVERY_ABSENT")
    assert isinstance(evidence, s.DiscoveryEvidence)
    vid = view["view_id"]
    c.require(
        evidence.raw_bytes == blobs[view["discovery_blob"]] == s.discovery_proposition(evidence)
        and evidence.discovery_ref == view["discovery_blob"]
        and request.candidates
        == evidence.candidates
        == tuple(sources[t] for t in view["source_inventory"])
        and request.relations == evidence.relations
        and tuple(r.notice for r in request.relations)
        == tuple(sources[t] for t in view["notice_inventory"]),
        "B2_DISCOVERY_MEMBERSHIP_MISMATCH",
    )
    page = _json(blobs[view["page_blob"]], 65_536)
    c.require(
        set(page) == {"members", "next_page", "page_ref", "query", "terminal", "window"}
        and page["page_ref"] == view["page_blob"]
        and page["query"] == evidence.query_key
        and tuple(page["window"]) == evidence.window
        and (tuple(page["members"]),) == evidence.pages
        and page["terminal"] is (vid != "MD1-B-UNRESOLVED-M3")
        and page["next_page"]
        == ("CONT01-R1-PAGE-PENDING" if vid == "MD1-B-UNRESOLVED-M3" else None),
        "B2_PAGE_EVIDENCE_MISMATCH",
    )
    c.require(
        evidence.terminated is (vid != "MD1-B-UNRESOLVED-M3"), "B2_DISCOVERY_TERMINATION_MISMATCH"
    )
    c.require(
        len(view["operations"]) == 3
        and request.coverage.checks == evidence.checks
        and tuple(ch.check_ref for ch in evidence.checks) == s.REQUIRED_CHECKS,
        "B2_OPERATION_INCOMPLETE",
    )
    for operation, check in zip(view["operations"], evidence.checks, strict=True):
        c.require(
            set(operation) == {"facts", "operation_ref", "raw_blob", "review_ledger_view"},
            "B2_OPERATION_SCHEMA_INVALID",
        )
        raw = blobs[operation["raw_blob"]]
        facts = _json(raw, 65_536)
        expected_status = (
            "NOT_PERFORMED"
            if vid == "MD1-B-UNRESOLVED-M3" and check.check_ref == "CANDIDATE_DISCOVERY"
            else "COMPLETED"
        )
        c.require(
            operation["operation_ref"] == operation["raw_blob"]
            and operation["operation_ref"] in check.evidence_refs
            and operation["review_ledger_view"] == vid
            and operation["facts"]["operation"] == check.check_ref
            and operation["facts"]["status"] == check.status == expected_status
            and raw == check.evidence_bytes
            and facts
            == {
                "candidate_refs": list(request.coverage.evaluated_candidate_refs),
                "check": check.check_ref,
                "context_ref": request.context.context_ref,
                "evidence_set_ref": request.context.evidence_set_ref,
                "policy_ref": request.policy.policy_ref,
                "policy_version": request.policy.version,
                "relation_refs": list(request.coverage.evaluated_relation_refs),
                "scope": request.policy.discovery_scope_ref,
                "source_refs": list(request.policy.source_refs),
                "status": check.status,
            },
            "B2_OPERATION_EVIDENCE_MISMATCH",
        )
    profile = view["profile"]
    expected_cutoff = MD1_CUTOFF if profile == "MD1" else "2027-01-07T18:00:00+08:00"
    context = request.context
    cutoff = context.information_cutoff
    c.require(
        profile in ("MD1", "W18")
        and vid.startswith(profile + "-")
        and cutoff.source_text == expected_cutoff
        and cutoff.timezone_name == "Asia/Taipei"
        and cutoff.offset == "+08:00"
        and cutoff.precision == "SECOND"
        and context.mode == "public"
        and context.calendar_ref == (MD1_CALENDAR if profile == "MD1" else "SYN-CAL-v1")
        and context.evidence_set_ref == "CONT01-R1-EVIDENCE-" + profile
        and context.profile.code_pins == tuple(c.CodePin(p, h) for p, h, _ in a04.NATIVE_PINS)
        and request.policy.evaluator_ref == s.B02_EVALUATOR_REF
        and evidence.cutoff_text == cutoff.source_text
        and evidence.context_ref == context.context_ref
        and evidence.evidence_set_ref == context.evidence_set_ref
        and evidence.policy == request.policy
        and evidence.subject == request.subject,
        "B2_VIEW_CONTEXT_MISMATCH",
    )


def _verify_facts(
    packet: Any, old: Any
) -> tuple[tuple[tuple[str, s.CandidateSource], ...], tuple[tuple[str, AsOfRequest], ...]]:
    c.require(
        type(packet) is dict
        and set(packet)
        == {
            "allowed_missing",
            "authoring",
            "blobs",
            "classification",
            "evidence_class",
            "feature_keys",
            "fit",
            "profiles",
            "revision",
            "schema",
            "source_records",
            "universe_validity",
            "views",
        }
        and packet["schema"] == "cont01-input-only-synthetic-source-v0.1"
        and packet["revision"] == "R1"
        and packet["classification"] == "CANDIDATE_NOT_ADOPTED"
        and packet["evidence_class"] == "SYNTHETIC_ENGINEERING_DIAGNOSTIC"
        and packet["feature_keys"] == list(FEATURE_KEYS)
        and packet["allowed_missing"] == []
        and packet["fit"] == "NO_STATE"
        and packet["universe_validity"] == ["2027-01-01", "2027-01-31"]
        and tuple(v["view_id"] for v in packet["views"]) == VIEW_IDS
        and tuple(r["tag"] for r in packet["source_records"]) == SOURCE_TAGS
        and len(packet["blobs"]) == 100,
        "B2_PACKET_SCHEMA_INVALID",
    )
    blobs = {name: _blob(record) for name, record in packet["blobs"].items()}
    sources: dict[str, s.CandidateSource] = {}
    old_sources = {r["tag"]: r for r in old["sources"]}
    for index, record in enumerate(packet["source_records"]):
        tag = record["tag"]
        if index < 7:
            original = old_sources[tag]
            c.require(
                set(record)
                == {
                    "fixture_byte_length",
                    "fixture_path",
                    "fixture_sha256",
                    "kind",
                    "raw_byte_length",
                    "raw_sha256",
                    "record_canonical_sha256",
                    "record_id",
                    "tag",
                }
                and record["kind"] == "REFERENCE_UNCHANGED_ACCEPTED_SOURCE"
                and record["fixture_path"] == OLD_SOURCE_PATH
                and record["fixture_byte_length"] == a04.FIXTURE_LENGTH
                and record["fixture_sha256"] == a04.FIXTURE_SHA256
                and record["record_canonical_sha256"]
                == sha256(_canonical(original["source"])).hexdigest(),
                "B2_OLD_SOURCE_IDENTITY_MISMATCH",
            )
            source = _input(original["source"], {}, {})
            raw = _blob(original["raw"])
            c.require(
                record["record_id"] == source.request.requested.target_ref
                and record["raw_byte_length"] == len(raw)
                and record["raw_sha256"] == sha256(raw).hexdigest(),
                "B2_OLD_RAW_IDENTITY_MISMATCH",
            )
        else:
            c.require(
                set(record)
                == {"S1_source_records_raw", "kind", "publication_record", "raw", "source", "tag"}
                and record["kind"] == "NEW_SOURCE_AUTHORED_SYNTHETIC",
                "B2_NEW_SOURCE_SCHEMA_INVALID",
            )
            source = _input(record["source"], {}, {})
            raw = _blob(record["raw"])
            c.require(
                isinstance(source, s.CandidateSource)
                and isinstance(source.request, c.IssuerBindingRequest),
                "B2_SOURCE_TYPE_INVALID",
            )
            c.require(
                source.request.scope.source_records
                == _input(_json(_blob(record["S1_source_records_raw"]), 65_536), {}, {}),
                "B2_S1_RECORD_BYTES_MISMATCH",
            )
            publication = _blob(record["publication_record"])
            c.require(
                all(
                    event.origin.input_digest == c.OriginKnownValue(sha256(publication).hexdigest())
                    for event in source.request.events
                ),
                "B2_PUBLICATION_BYTES_MISMATCH",
            )
        c.require(
            isinstance(source, s.CandidateSource)
            and isinstance(source.request, c.IssuerBindingRequest)
            and source.request.content.raw_bytes == raw
            and source.request.content.raw_length == len(raw) <= 65_536
            and source.request.content.raw_sha256 == sha256(raw).hexdigest(),
            "B2_RAW_SOURCE_MISMATCH",
        )
        sources[tag] = source
    requests = []
    for view in packet["views"]:
        request = _input(view["request"], sources, blobs)
        c.require(isinstance(request, AsOfRequest), "B2_REQUEST_TYPE_INVALID")
        _verify_view(view, request, sources, blobs)
        requests.append((view["view_id"], request))
    return tuple(sources.items()), tuple(requests)


def verify_causal_bundle(body: bytes, /) -> AdoptedInput | Refusal:
    """Recover exact R1 bytes; fixed old-source path and hash are the only dependency."""
    try:
        _pinned(body, FIXTURE_PIN, "B2_BUNDLE_NOT_ADOPTED")
        wrapper = _json(body, 250_000)
        c.require(
            set(wrapper) == {"schema", "classification", "provenance", "packet", "oracle"}
            and wrapper["schema"] == "wu03b2-r1-lossless-input-v0.1"
            and wrapper["classification"] == "SYNTHETIC_ENGINEERING_DIAGNOSTIC",
            "B2_BUNDLE_SCHEMA_INVALID",
        )
        packet_bytes = _transport(wrapper["packet"], PACKET_PIN)
        oracle_bytes = _transport(wrapper["oracle"], ORACLE_PIN)
        packet, oracle = _json(packet_bytes, PACKET_PIN[0]), _json(oracle_bytes, ORACLE_PIN[0])
        c.require(
            oracle["classification"] == "HAND_AUTHORED_EXPECTED_ONLY_BEFORE_NATIVE",
            "B2_ORACLE_SCHEMA_INVALID",
        )
        old_bytes = _regular_bytes(_root() / OLD_SOURCE_PATH)
        _pinned(old_bytes, (a04.FIXTURE_LENGTH, a04.FIXTURE_SHA256), "B2_OLD_FIXTURE_PIN_MISMATCH")
        sources, views = _verify_facts(packet, _json(old_bytes, a04.FIXTURE_LENGTH))
        return AdoptedInput(body, packet_bytes, oracle_bytes, sources, views)
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        zlib.error,
    ) as exc:
        return Refusal("SOURCE_VERIFICATION", str(exc), type(exc).__name__)


def _md1_request(inputs: AdoptedInput, code: b03.B03CodeObservation) -> b03.B03Request:
    views = dict(inputs.views)
    rows = []
    for entity, short in (("SYN-A", "A"), ("SYN-B", "B")):
        spec = FeatureSpec("WU03-B2-SUM-" + entity + "-Q4-2026", 2026, 4, entity)
        slots = tuple(
            DependencySlot(
                "M" + str(i), views[f"MD1-{short}-M{i}"].subject, views[f"MD1-{short}-M{i}"]
            )
            for i in (1, 2, 3)
        )
        ratio = RatioFeatureSpec(
            "WU03-B2-SHARE-" + entity + "-Q4-2026", spec.feature_ref, entity, 2026, 4
        )
        rows.append(b03.DecisionRow(entity, b03.SumRequest(spec, slots), ratio))
    core = code.upstream_ratio.upstream_a04
    spec_u = b03.UniverseSpec(date(2027, 1, 1), date(2027, 1, 31))
    members = (views["MD1-MEM-A"], views["MD1-MEM-B"])
    universe = b03.UniverseRequest(spec_u, members, b03.UniverseReference(spec_u, members, core))
    context = rows[0].sum_request.slots[0].request.context
    features = tuple(b03.B03FeatureSpec(k) for k in FEATURE_KEYS)
    bindings = (("SYN-A", 2026, 4), ("SYN-B", 2026, 4))
    reference = b03.CausalReference(
        context, features, tuple(rows), b03.NO_STATE, universe, code, bindings, ()
    )
    skeleton = b03.B03Request(
        context,
        features,
        tuple(rows),
        b03.NO_STATE,
        universe,
        b03.CausalPlan((), ()),
        reference,
        bindings,
        allowed_missing=(),
    )
    return replace(skeleton, plan=b03.required_plan(skeleton))


def prepare_causal_request(
    before: ObservedCausalCode | ObservationUnavailable, bundle_bytes: bytes | None = None, /
) -> CausalRequestAssembly | Refusal:
    """Issue only the fixed MD1 request; callers cannot supply context or results."""
    started = time.perf_counter()
    try:
        c.require(
            isinstance(before, ObservedCausalCode) and _issued(before), "B2_OBSERVATION_NOT_ISSUED"
        )
        assert isinstance(before, ObservedCausalCode)
        c.require(observe_causal_diagnostic_code() == before, "B2_BEFORE_OBSERVATION_STALE")
        raw = _regular_bytes(_root() / FIXTURE_PATH) if bundle_bytes is None else bundle_bytes
        inputs = verify_causal_bundle(raw)
        if isinstance(inputs, Refusal):
            return inputs
        request = _md1_request(inputs, before.code)
        result = CausalRequestAssembly(
            inputs,
            request,
            dp.ProjectionPolicy(FEATURE_KEYS, ()),
            before,
            time.perf_counter() - started,
        )
        _stamp(result)
        return result
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return Refusal("PREPARATION", str(exc), type(exc).__name__)


def _assembly_reason(assembly: CausalRequestAssembly) -> str | None:
    if not isinstance(assembly, CausalRequestAssembly) or not _issued(assembly):
        return "B2_ASSEMBLY_NOT_ISSUED_OR_CHANGED"
    if not _issued(assembly.before_observation):
        return "B2_OBSERVATION_NOT_ISSUED"
    if observe_causal_diagnostic_code() != assembly.before_observation:
        return "B2_BEFORE_OBSERVATION_STALE"
    return None


def invoke_causal(assembly: CausalRequestAssembly, /) -> NativeCausalAttempt | Refusal:
    """Preserve actual public Native returns, including exceptions after entry."""
    try:
        if reason := _assembly_reason(assembly):
            return Refusal("BEFORE_INVOCATION", reason)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        return Refusal("BEFORE_INVOCATION", str(exc), type(exc).__name__)
    request, code = assembly.request, assembly.before_observation.code
    universe: NativeUniverse | None = None
    completed: NativeResult | None = None
    projected: Projection | None = None
    timings: list[tuple[str, float]] = []
    stage = "UNIVERSE"
    started = time.perf_counter()
    try:
        universe = causal_slice.qualify_universe(
            request.universe, code.upstream_ratio.upstream_a04, request.context
        )
        timings.append((stage, time.perf_counter() - started))
        stage, started = "B03", time.perf_counter()
        completed = causal_slice.evaluate_causal(request, code)
        timings.append((stage, time.perf_counter() - started))
        stage, started = "PROJECTION", time.perf_counter()
        projected = dp.project_candidate(
            request.context, request.specifications, completed, universe, assembly.policy, code
        )
        timings.append((stage, time.perf_counter() - started))
        result = NativeCausalAttempt(
            assembly, universe, completed, projected, "RUN", stage, None, None, tuple(timings)
        )
    except Exception as exc:
        timings.append((stage, time.perf_counter() - started))
        result = NativeCausalAttempt(
            assembly,
            universe,
            completed,
            projected,
            "ATTEMPTED",
            stage,
            type(exc).__name__,
            str(exc),
            tuple(timings),
        )
    _stamp(result)
    return result


def finalize_causal_diagnostic(
    attempt: NativeCausalAttempt, /
) -> CausalDiagnostic | InvocationFailure | ObservationFailure | Refusal:
    """An after-observation failure preserves the true RUN/ATTEMPTED execution."""
    if (
        not isinstance(attempt, NativeCausalAttempt)
        or not isinstance(attempt._ticket, _Ticket)
        or attempt._ticket.owner is not attempt
    ):
        return Refusal("FINALIZATION", "B2_ATTEMPT_NOT_ISSUED")
    after = observe_causal_diagnostic_code()
    try:
        if (
            not _issued(attempt)
            or not _issued(attempt.assembly)
            or not _issued(attempt.assembly.before_observation)
        ):
            reason = "B2_ATTEMPT_OR_INPUT_CHANGED"
        elif isinstance(after, ObservationUnavailable):
            reason = after.reason
        elif after != attempt.assembly.before_observation:
            reason = "B2_OBSERVATION_CHANGED"
        else:
            if attempt.native_invocation == "ATTEMPTED":
                return InvocationFailure(attempt, (attempt.assembly.before_observation, after))
            return CausalDiagnostic(
                attempt, (attempt.assembly.before_observation, after), attempt.native_invocation
            )
    except (ValueError, TypeError, AttributeError) as exc:
        reason = str(exc)
    return ObservationFailure(reason, attempt, after)
