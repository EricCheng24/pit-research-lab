"""Bounded WU03-A source transport and observation-gated Native A04 diagnostics.

Discovery/coverage bytes are authored inputs, never completed by this adapter.
Observation is local disk consistency, not runtime attestation or source trust.
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
from typing import Any, Literal

from pit_research_lab.domain import contracts as c
from pit_research_lab.domain import derived_slice
from pit_research_lab.domain import selection as s
from pit_research_lab.domain.asof_slice import AsOfRequest
from pit_research_lab.domain.derivation import (
    S4_CODE_PATHS,
    DependencySlot,
    DerivedResult,
    FeatureSpec,
)
from pit_research_lab.domain.pit_slice import CODE_PATHS, CodeObservation
from pit_research_lab.mvp.f2.synthetic_contracts import InputError, decode_input_bytes
from pit_research_lab.mvp.f2.synthetic_temporal import (
    SyntheticInputPack,
    build_weekly_requests,
    verify_input_pack,
)

SCHEMA = "wu03a-source-evidence-v0.1"
FIXTURE_SHA256 = "b9e1babbcc86b0e70ed5589972259fcbe6b666a38d2e7eff77d108f448e4dc0e"
FIXTURE_LENGTH = 5_440_756
ORACLE_SHA256 = "6686616cbab395c93aa00e6e6b25c8043b940e43fbfeceb96a106cd37644f4d6"
PACK_SHA256 = "c0c8d440f1127f0ede57863cfb544eaaac184e1a3436670c1bf8d46f1385195c"
NATIVE_PATHS = (*CODE_PATHS, *s.S3_CODE_PATHS, *S4_CODE_PATHS)
NATIVE_PINS = tuple(
    zip(
        NATIVE_PATHS,
        (
            "8121e022e7de092b4c79651137a4ccd89cd450ba910d65bb507b15781a52a5ff",
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "d0a15387c919cdeafa7fc166952f9878487ae0337ec4ff92327b4c9ceb0a3bac",
            "fc1ed60a5fb3066553a18322f69df195429f7e83bd6dba774cb201d0f5c216d7",
            "09dfd6108c5ba2e117fb61ab4b9ce9254d342d1bf26fcfbf16d221b1d3f25dc7",
            "ab7ba2843035811e35e66f1a22eca51bc6d1b20d07248bb4f6097a76e898cc53",
            "15ab6df10542df799a54a41e716c19fd13f52e3c738fba6e689b649c171f0202",
            "5500f53b0526b2e629ec844cef99b9445479900fc3e73ba98c9e48e2d30b2a31",
            "bd52a33d8f971adbd11f12ad7ec7c905fd2c6404ac40d1674c303a16e97534e9",
            "26976c30bfb45cd70d012f4242bd5cad44811b63786ce2f403dd9d1c825873bb",
        ),
        (79, 0, 24933, 42942, 18274, 4029, 63295, 3055, 17339, 1681),
        strict=True,
    )
)
ADAPTER_PATH = "src/pit_research_lab/mvp/f2/derived_observations.py"
STATUS_PATHS = frozenset(
    (
        "src/pit_research_lab/mvp/f2/ratio_observations.py",
        "tests/unit/mvp_f2/test_ratio_observations.py",
        "tests/unit/mvp_f2/data/ratio_observations_v0.1.json",
        ADAPTER_PATH,
        "tests/unit/mvp_f2/data/derived_observations_v0.1.json",
        "tests/unit/mvp_f2/test_derived_observations.py",
        "src/pit_research_lab/mvp/f2/native_requests.py",
        "src/pit_research_lab/mvp/f2/asof_requests.py",
    )
)
_OBSERVED = object()
_PREPARED = object()
_INVOKED = object()


@dataclass(frozen=True, slots=True)
class WU03ObservationUnavailable:
    reason: str


@dataclass(frozen=True, slots=True)
class WU03ObservedCodeInput:
    code: CodeObservation
    checkout_root: str
    adapter_sha256: str
    raw_status: str
    _witness: object | None = field(default=None, init=False, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class WU03MappingRefusal:
    stage: str
    reason: str
    exact_exception_type: str | None = None
    native_invocation: Literal["NOT_RUN"] = field(default="NOT_RUN", init=False)
    diagnostic_only: Literal[True] = field(default=True, init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)


@dataclass(frozen=True, slots=True)
class WU03RequestAssembly:
    specification: FeatureSpec
    slots: tuple[DependencySlot, ...]
    before_observation: WU03ObservedCodeInput
    source_packet_bytes: bytes
    exact_tick_bytes: bytes
    source_identity: tuple[tuple[str, str], ...]
    request_digest: str
    _witness: object | None = field(default=None, init=False, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class WU03NativeAttempt:
    assembly: WU03RequestAssembly
    native_result: DerivedResult
    native_invocation: Literal["RUN"] = field(default="RUN", init=False)
    _witness: object | None = field(default=None, init=False, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class WU03InvocationFailure:
    assembly: WU03RequestAssembly
    exact_native_exception_type: str
    code: str
    native_invocation: Literal["ATTEMPTED"] = field(default="ATTEMPTED", init=False)
    _witness: object | None = field(default=None, init=False, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class WU03Diagnostic:
    source_identity: tuple[tuple[str, str], ...]
    native_result: DerivedResult
    observations: tuple[WU03ObservedCodeInput, WU03ObservedCodeInput]
    source_packet_sha256: str
    oracle_sha256: str
    native_invocation: Literal["RUN"] = field(default="RUN", init=False)
    diagnostic_only: Literal[True] = field(default=True, init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)
    trust: Literal["NOT_TRUSTED_PIT_EVIDENCE"] = field(
        default="NOT_TRUSTED_PIT_EVIDENCE", init=False
    )
    source_authentication: Literal["NOT_ESTABLISHED"] = field(default="NOT_ESTABLISHED", init=False)
    disposition: Literal["INTEGRATED_PROVISIONAL"] = field(
        default="INTEGRATED_PROVISIONAL", init=False
    )


@dataclass(frozen=True, slots=True)
class WU03ObservationFailure:
    reason: str
    preserved: WU03NativeAttempt | WU03InvocationFailure
    after_observation: WU03ObservedCodeInput | WU03ObservationUnavailable
    native_invocation: Literal["RUN", "ATTEMPTED"] = field(init=False)
    diagnostic_only: Literal[True] = field(default=True, init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "native_invocation", self.preserved.native_invocation)


def _root() -> Path:
    module = PurePosixPath(__file__)
    c.require(
        module.is_absolute()
        and ".." not in module.parts
        and module.parts[-5:]
        == ("src", "pit_research_lab", "mvp", "f2", "derived_observations.py"),
        "WU03_CHECKOUT_LAYOUT_INVALID",
    )
    root = Path(module.parents[4])
    # Check loaded owner lexically BEFORE any I/O through a potentially forged root.
    c.require(
        Path(derived_slice.__file__) == root / "src/pit_research_lab/domain/derived_slice.py"
        and __spec__ is not None
        and __spec__.origin == __file__,
        "WU03_LOADED_OWNER_ROOT_MISMATCH",
    )
    for path in NATIVE_PATHS:
        name = path.removeprefix("src/").removesuffix(".py").replace("/", ".")
        name = name.removesuffix(".__init__")
        loaded = sys.modules.get(name)
        c.require(
            loaded is not None and getattr(loaded, "__file__", None) == str(root / path),
            "WU03_LOADED_OWNER_ROOT_MISMATCH",
        )
    return root


def _regular_bytes(path: Path) -> bytes:
    for part in (*reversed(path.parents), path):
        c.require(not part.is_symlink(), "WU03_SYMLINK_REFUSED")
    info = path.stat()
    c.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "WU03_NONREGULAR_OR_LINKED")
    return path.read_bytes()


def _status_valid(raw: str) -> bool:
    # Read unstripped porcelain ourselves: 'M ' (staged) must not become ' M'.
    return all(
        len(line) > 3 and line[:3] in {" M ", "?? "} and line[3:] in STATUS_PATHS
        for line in raw.splitlines()
    )


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(root), *args], text=True
    )


def _observation_reason(value: WU03ObservedCodeInput | WU03ObservationUnavailable) -> str | None:
    if isinstance(value, WU03ObservationUnavailable):
        return value.reason
    if not isinstance(value, WU03ObservedCodeInput) or value._witness is not _OBSERVED:
        return "WU03_OBSERVATION_NOT_ISSUED"
    if value.checkout_root != str(_root()) or not _status_valid(value.raw_status):
        return "WU03_OBSERVATION_SCOPE_INVALID"
    code = value.code
    if (
        tuple(
            (p.path, p.sha256, n)
            for p, n in zip(code.observed_working_files, code.byte_lengths, strict=True)
        )
        != NATIVE_PINS
        or code.worktree_status != value.raw_status.strip()
        or re.fullmatch("[0-9a-f]{40}", code.head) is None
        or re.fullmatch("[0-9a-f]{40}", code.head_tree) is None
        or re.fullmatch("[0-9a-f]{64}", value.adapter_sha256) is None
        or code.interpretation != "OBSERVED_DISK_BYTES; HEAD_IS_NOT_COMPLETE_CODE_VERSION"
    ):
        return "WU03_OBSERVATION_PIN_OR_CONTEXT_MISMATCH"
    return None


def observe_wu03_code() -> WU03ObservedCodeInput | WU03ObservationUnavailable:
    """Only this boundary issues witnesses; there is no caller-selected root.

    Source packet bytes are explicit immutable caller inputs, hashed in prepare
    and again in finalize. This observer never resolves a test fixture path.
    """
    try:
        root = _root()
        adapter = _regular_bytes(root / ADAPTER_PATH)
        c.require(
            _git(root, "rev-parse", "--show-toplevel").strip() == str(root),
            "WU03_GIT_ROOT_MISMATCH",
        )
        raw_status = _git(root, "status", "--short", "--untracked-files=all")
        c.require(_status_valid(raw_status), "WU03_DIRTY_STATUS_REFUSED")
        before = tuple(_regular_bytes(root / p) for p in NATIVE_PATHS)
        c.require(
            tuple(
                (p, sha256(b).hexdigest(), len(b))
                for p, b in zip(NATIVE_PATHS, before, strict=True)
            )
            == NATIVE_PINS,
            "WU03_NATIVE_DISK_PIN_MISMATCH",
        )
        code = derived_slice.observe_derived_code(root)
        c.require(
            before == tuple(_regular_bytes(root / p) for p in NATIVE_PATHS)
            and adapter == _regular_bytes(root / ADAPTER_PATH)
            and raw_status == _git(root, "status", "--short", "--untracked-files=all")
            and code.head == _git(root, "rev-parse", "HEAD").strip()
            and code.head_tree == _git(root, "rev-parse", "HEAD^{tree}").strip(),
            "WU03_OBSERVATION_CHANGED_DURING_READ",
        )
        value = WU03ObservedCodeInput(code, str(root), sha256(adapter).hexdigest(), raw_status)
        object.__setattr__(value, "_witness", _OBSERVED)
        if reason := _observation_reason(value):
            return WU03ObservationUnavailable(reason)
        return value
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return WU03ObservationUnavailable(str(error))


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        c.require(key not in result, "WU03_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _noninteger(_: str) -> Any:
    raise c.ContractError("WU03_NONINTEGER_JSON")


def _json(body: bytes) -> Any:
    return json.loads(
        body, object_pairs_hook=_pairs, parse_float=_noninteger, parse_constant=_noninteger
    )


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _blob(value: Any) -> bytes:
    c.require(
        type(value) is dict and set(value) == {"utf8", "byte_length", "sha256"},
        "WU03_BLOB_SCHEMA_INVALID",
    )
    c.require(type(value["utf8"]) is str, "WU03_BLOB_SCHEMA_INVALID")
    source_text: str = value["utf8"]
    body = source_text.encode("utf-8")
    c.require(
        type(value["byte_length"]) is int
        and len(body) == value["byte_length"]
        and sha256(body).hexdigest() == value["sha256"],
        "WU03_EVIDENCE_PIN_MISMATCH",
    )
    return body


# Input records only. No outcome/completed-result/feature grammar constructor.
_CONSTRUCTORS: dict[str, type[c.Record]] = {
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


def _decode(value: Any, sources: dict[str, s.CandidateSource]) -> Any:
    if isinstance(value, list):
        return tuple(_decode(v, sources) for v in value)
    if not isinstance(value, dict):
        c.require(value is None or type(value) in (str, int, bool), "WU03_WIRE_VALUE_INVALID")
        return value
    if set(value) == {"source_ref"}:
        return sources[value["source_ref"]]
    if set(value) == {"bytes_hex"}:
        return bytes.fromhex(value["bytes_hex"])
    if set(value) == {"date"}:
        return date.fromisoformat(value["date"])
    cls = _CONSTRUCTORS.get(value.get("type", ""))
    c.require(cls is not None, "WU03_INPUT_TYPE_REFUSED")
    assert cls is not None
    descriptions = {f.name: f for f in fields(cls)}
    c.require(set(value) == {"type", *descriptions}, "WU03_INPUT_FIELDS_INVALID")
    kwargs = {k: _decode(v, sources) for k, v in value.items() if k != "type"}
    if cls in (c.FieldOrigin, c.RoleRef):
        kwargs["visibility"] = c.Visibility(kwargs["visibility"])
    if cls in (c.Unknown, c.OriginUnknownValue):
        kwargs["cause"] = c.UnknownCause(kwargs["cause"])
    result = cls(**{k: v for k, v in kwargs.items() if descriptions[k].init})
    c.require(
        all(getattr(result, k) == v for k, v in kwargs.items()), "WU03_INPUT_DEFAULT_MISMATCH"
    )
    return result


def _wire(value: Any) -> Any:
    if is_dataclass(value):
        return {
            "type": type(value).__name__,
            **{f.name: _wire(getattr(value, f.name)) for f in fields(value)},
        }
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, date):
        return {"date": value.isoformat()}
    if isinstance(value, tuple):
        return [_wire(v) for v in value]
    return value


def _verify_packet(body: bytes) -> tuple[Any, tuple[AsOfRequest, ...]]:
    """Decode only after the external whole-file pin; validate ALL 12 views."""
    c.require(
        type(body) is bytes
        and len(body) == FIXTURE_LENGTH
        and sha256(body).hexdigest() == FIXTURE_SHA256,
        "WU03_SOURCE_NOT_ACCEPTED",
    )
    obj = _json(body)
    c.require(
        set(obj)
        == {
            "schema",
            "classification",
            "authoring",
            "binding",
            "oracle",
            "sources",
            "views",
            "native_controls",
        }
        and obj["schema"] == SCHEMA
        and obj["classification"] == "SYNTHETIC_ENGINEERING_DIAGNOSTIC",
        "WU03_SOURCE_SCHEMA_INVALID",
    )
    c.require(
        sha256(_canonical(obj["oracle"])).hexdigest() == ORACLE_SHA256, "WU03_ORACLE_PIN_MISMATCH"
    )
    c.require(
        len(obj["sources"]) == 7 and len(obj["views"]) == 12, "WU03_SOURCE_CARDINALITY_INVALID"
    )
    # Verify persisted byte pins before constructing any Native input DTO.
    for source in obj["sources"]:
        _blob(source["raw"])
    for control in obj["native_controls"]:
        _blob(control["raw"])
        _blob(control["discovery_descriptor"])
        for operation in control["operations"]:
            _blob(operation)
    for view in obj["views"]:
        _blob(view["discovery_descriptor"])
        c.require(
            len(view["operations"]) == 3 and len(view["pages"]) == 1,
            "WU03_VIEW_EVIDENCE_INCOMPLETE",
        )
        for operation in view["operations"]:
            _blob(operation["evidence"])
        for page in view["pages"]:
            _blob(page["evidence"])
    sources: dict[str, s.CandidateSource] = {}
    for source in obj["sources"]:
        tag = source["tag"]
        c.require(tag not in sources, "WU03_DUPLICATE_SOURCE")
        candidate = _decode(source["source"], {})
        c.require(isinstance(candidate, s.CandidateSource), "WU03_SOURCE_TYPE_INVALID")
        assert isinstance(candidate, s.CandidateSource)
        c.require(
            candidate.request.content.raw_bytes == _blob(source["raw"]), "WU03_RAW_SOURCE_MISMATCH"
        )
        sources[tag] = candidate
    requests = []
    for i, view in enumerate(obj["views"]):
        c.require(
            view["view_id"] == f"t{i // 3 + 1}-M{i % 3 + 1}" and view["slot"] == f"M{i % 3 + 1}",
            "WU03_VIEW_IDENTITY_MISMATCH",
        )
        request = _decode(view["request"], sources)
        c.require(isinstance(request, AsOfRequest), "WU03_REQUEST_TYPE_INVALID")
        assert isinstance(request, AsOfRequest)
        evidence = request.discovery
        c.require(isinstance(evidence, s.DiscoveryEvidence), "WU03_DISCOVERY_ABSENT")
        assert isinstance(evidence, s.DiscoveryEvidence)
        c.require(
            _blob(view["discovery_descriptor"])
            == evidence.raw_bytes
            == s.discovery_proposition(evidence),
            "WU03_DISCOVERY_SOURCE_MISMATCH",
        )
        c.require(
            request.candidates
            == evidence.candidates
            == tuple(sources[t] for t in view["source_tags"])
            and request.relations == evidence.relations
            and tuple(r.notice for r in request.relations)
            == tuple(sources[t] for t in view["notice_tags"]),
            "WU03_VIEW_MEMBERSHIP_MISMATCH",
        )
        page = _json(_blob(view["pages"][0]["evidence"]))
        c.require(
            page["query"] == evidence.query_key
            and tuple(page["window"]) == evidence.window
            and (tuple(page["members"]),) == evidence.pages
            and page["terminal"] is True
            and page["next_page"] is None
            and evidence.terminated is True,
            "WU03_PAGE_EVIDENCE_MISMATCH",
        )
        checks = tuple(_decode(op["check"], {}) for op in view["operations"])
        c.require(
            checks == request.coverage.checks == evidence.checks
            and tuple(check.check_ref for check in checks) == s.REQUIRED_CHECKS,
            "WU03_OPERATION_SOURCE_MISMATCH",
        )
        for operation, check in zip(view["operations"], checks, strict=True):
            c.require(
                operation["operation_ref"] in check.evidence_refs
                and _blob(operation["evidence"]) == check.evidence_bytes
                and tuple(operation["source_refs"]) == request.policy.source_refs
                and operation["facts"]["view"] == view["view_id"]
                and operation["facts"]["operation"] == check.check_ref
                and check.status == "COMPLETED",
                "WU03_OPERATION_EVIDENCE_MISMATCH",
            )
        c.require(
            request.context.profile.code_pins == tuple(c.CodePin(p, h) for p, h, _ in NATIVE_PINS),
            "WU03_DECLARED_CODE_MISMATCH",
        )
        requests.append(request)
    return obj, tuple(requests)


def _request_digest(
    spec: FeatureSpec, slots: tuple[DependencySlot, ...], identity: tuple[tuple[str, str], ...]
) -> str:
    return sha256(_canonical(_wire((spec, slots, identity)))).hexdigest()


def prepare_derived_request(
    pack: SyntheticInputPack,
    exact_tick_bytes: bytes,
    source_packet_bytes: bytes,
    observation: WU03ObservedCodeInput | WU03ObservationUnavailable,
    /,
) -> WU03RequestAssembly | WU03MappingRefusal:
    stage = "S01_OBSERVATION"
    try:
        if reason := _observation_reason(observation):
            return WU03MappingRefusal(stage, reason)
        assert isinstance(observation, WU03ObservedCodeInput)
        stage = "S02_PACK_TICK"
        verify_input_pack(pack)
        c.require(pack.payload_sha256 == PACK_SHA256, "WU03_PACK_NOT_ACCEPTED")
        ticks = build_weekly_requests(pack).requests
        c.require(
            type(exact_tick_bytes) is bytes and exact_tick_bytes in ticks, "WU03_TICK_NOT_MEMBER"
        )
        tick = decode_input_bytes(exact_tick_bytes)
        index = ticks.index(exact_tick_bytes)
        stage = "S03_SOURCE"
        obj, requests = _verify_packet(source_packet_bytes)
        binding = obj["binding"]
        c.require(
            binding["pack_sha256"] == pack.payload_sha256
            and binding["ticks"][index] == tick
            and all(binding[k] == tick[k] for k in ("manifest_ref", "calendar_ref", "config_ref")),
            "WU03_MANIFEST_BINDING_MISMATCH",
        )
        selected = requests[3 * index : 3 * index + 3]
        for j, request in enumerate(selected):
            c.require(
                request.context.information_cutoff.source_text == tick["cutoff"]["source_text"]
                and request.context.calendar_ref == tick["calendar_ref"]
                and request.context.mode == "public"
                and request.policy.target == "ATTRIBUTED_ASSERTION"
                and request.policy.issuer_ref == "SYN-A"
                and request.policy.version == s.B02_POLICY_VERSION
                and request.context.profile.code_pins == observation.code.observed_working_files
                and obj["views"][3 * index + j]["tick_id"] == tick["tick_id"],
                "WU03_TICK_VIEW_CONTEXT_MISMATCH",
            )
        spec = FeatureSpec("WU03-A-DERIVED-Q4-2026", 2026, 4, "SYN-A")
        slots = tuple(DependencySlot(f"M{i + 1}", r.subject, r) for i, r in enumerate(selected))
        identity = (
            ("packet_sha256", FIXTURE_SHA256),
            ("oracle_sha256", ORACLE_SHA256),
            ("pack_sha256", pack.payload_sha256),
            ("tick_sha256", sha256(exact_tick_bytes).hexdigest()),
            *(
                (key, tick[key])
                for key in ("tick_id", "context_ref", "manifest_ref", "calendar_ref", "config_ref")
            ),
        )
        result = WU03RequestAssembly(
            spec,
            slots,
            observation,
            source_packet_bytes,
            exact_tick_bytes,
            identity,
            _request_digest(spec, slots, identity),
        )
        object.__setattr__(result, "_witness", _PREPARED)
        return result
    except (InputError, ValueError, TypeError, KeyError, AttributeError) as error:
        return WU03MappingRefusal(stage, str(error), type(error).__name__)


def _assembly_valid_unchecked(assembly: WU03RequestAssembly) -> bool:
    return (
        isinstance(assembly, WU03RequestAssembly)
        and assembly._witness is _PREPARED
        and _observation_reason(assembly.before_observation) is None
        and sha256(assembly.source_packet_bytes).hexdigest() == FIXTURE_SHA256
        and len(assembly.source_packet_bytes) == FIXTURE_LENGTH
        and ("tick_sha256", sha256(assembly.exact_tick_bytes).hexdigest())
        in assembly.source_identity
        and assembly.request_digest
        == _request_digest(assembly.specification, assembly.slots, assembly.source_identity)
    )


def _assembly_valid(assembly: WU03RequestAssembly) -> bool:
    try:
        return _assembly_valid_unchecked(assembly)
    except (ValueError, TypeError, AttributeError):
        return False


def invoke_derived(assembly: WU03RequestAssembly, /) -> WU03NativeAttempt | WU03InvocationFailure:
    """The only numerical invocation is public Native A04; inputs must be issued."""
    if not _assembly_valid(assembly):
        raise ValueError("WU03_UNCHANGED_PREPARED_ASSEMBLY_REQUIRED; NOT_RUN")
    try:
        result = derived_slice.evaluate_derived(
            assembly.specification, assembly.slots, assembly.before_observation.code
        )
        attempt: WU03NativeAttempt | WU03InvocationFailure = WU03NativeAttempt(assembly, result)
    except Exception as error:
        attempt = WU03InvocationFailure(assembly, type(error).__name__, str(error))
    object.__setattr__(attempt, "_witness", _INVOKED)
    return attempt


def finalize_derived_diagnostic(
    attempt: WU03NativeAttempt | WU03InvocationFailure,
    after_observation: WU03ObservedCodeInput | WU03ObservationUnavailable,
    /,
) -> WU03Diagnostic | WU03InvocationFailure | WU03ObservationFailure:
    """No new preview: retain Native bytes, reasons and actual execution state.

    Rehash retained source bytes here: their identity is an input observation,
    not a claim that the caller's source file on disk was observed by this API.
    """
    if attempt._witness is not _INVOKED:
        # An unissued object cannot supply an authoritative execution label.
        # Reject it without emitting either RUN or an invented NOT_RUN status.
        raise ValueError("WU03_ISSUED_ATTEMPT_REQUIRED")
    reason: str | None = None
    if reason is None and not _assembly_valid(attempt.assembly):
        reason = "WU03_ASSEMBLY_CHANGED"
    if reason is None:
        reason = _observation_reason(after_observation)
    if reason is None and attempt.assembly.before_observation != after_observation:
        reason = "WU03_OBSERVATION_CHANGED"
    if reason is not None:
        return WU03ObservationFailure(reason, attempt, after_observation)
    if isinstance(attempt, WU03InvocationFailure):
        return attempt
    assert isinstance(after_observation, WU03ObservedCodeInput)
    return WU03Diagnostic(
        attempt.assembly.source_identity,
        attempt.native_result,
        (attempt.assembly.before_observation, after_observation),
        FIXTURE_SHA256,
        ORACLE_SHA256,
    )
