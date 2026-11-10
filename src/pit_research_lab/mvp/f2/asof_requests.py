"""Bounded G03 source assembly; explicit caller observation is the only I/O surface.

Exact accepted corpus pins authorize this synthetic engineering mapping only.
They authenticate neither issuers nor search completeness. Native owns all
qualification, including the deliberately incomplete/hostile source profiles.
"""

import base64
import binascii
import json
import re
import stat
import subprocess
import zlib
from dataclasses import dataclass, field, fields
from datetime import date
from functools import lru_cache
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast

from pit_research_lab.domain import asof_slice
from pit_research_lab.domain import contracts as c
from pit_research_lab.domain import selection as s
from pit_research_lab.domain.pit_slice import CODE_PATHS, CodeObservation
from pit_research_lab.mvp.f2.synthetic_contracts import InputError, decode_input_bytes
from pit_research_lab.mvp.f2.synthetic_temporal import (
    SyntheticInputPack,
    build_weekly_requests,
    verify_input_pack,
)

CORPUS_SHA256 = "37e7c10b74d1eab7ff45cc42f571f933a1be769f812d6872402f952704c37524"
S1S2_SHA256 = "a876570e6bcc92ffe6977aea3d2ca06b4d19f3262f33abe95ff7607db8d46fa8"
PACK_SHA256 = "c0c8d440f1127f0ede57863cfb544eaaac184e1a3436670c1bf8d46f1385195c"
NATIVE_CODE_PINS = tuple(
    zip(
        CODE_PATHS + s.S3_CODE_PATHS,
        (
            "8121e022e7de092b4c79651137a4ccd89cd450ba910d65bb507b15781a52a5ff",
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "d0a15387c919cdeafa7fc166952f9878487ae0337ec4ff92327b4c9ceb0a3bac",
            "fc1ed60a5fb3066553a18322f69df195429f7e83bd6dba774cb201d0f5c216d7",
            "09dfd6108c5ba2e117fb61ab4b9ce9254d342d1bf26fcfbf16d221b1d3f25dc7",
            "ab7ba2843035811e35e66f1a22eca51bc6d1b20d07248bb4f6097a76e898cc53",
            "15ab6df10542df799a54a41e716c19fd13f52e3c738fba6e689b649c171f0202",
            "5500f53b0526b2e629ec844cef99b9445479900fc3e73ba98c9e48e2d30b2a31",
        ),
        (79, 0, 24933, 42942, 18274, 4029, 63295, 3055),
        strict=True,
    )
)
G03_PATHS = (
    "src/pit_research_lab/mvp/f2/asof_requests.py",
    "src/pit_research_lab/mvp/f2/asof_qualification.py",
    "tests/unit/mvp_f2/test_bounded_asof.py",
    "tests/unit/mvp_f2/data/bounded_asof_evidence_v0.1.json",
)
_STATUS_PATHS = frozenset((*G03_PATHS, "src/pit_research_lab/mvp/f2/native_requests.py"))
_OBSERVED = object()
_PREPARED = object()


@dataclass(frozen=True, slots=True)
class G03SourceInput:
    corpus_bytes: bytes
    s1s2_fixture_bytes: bytes
    profile_id: str


@dataclass(frozen=True, slots=True)
class G03ObservedCodeInput:
    """Only observe_g03_code issues a local caller witness; not an attestation.

    An externally constructed receipt has no witness and fails preparation.
    This protects the API boundary, not a process against hostile Python code.
    """

    code: CodeObservation
    checkout_root: str
    _witness: object | None = field(default=None, init=False, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class G03ObservationUnavailable:
    reason: str


@dataclass(frozen=True, slots=True)
class G03MappingRefusal:
    stage: str
    reason: str
    exact_exception_type: str | None = None
    upstream_code: str | None = None
    native_invocation: Literal["NOT_RUN"] = field(default="NOT_RUN", init=False)
    diagnostic_only: Literal[True] = field(default=True, init=False)
    admission_eligible: Literal[False] = field(default=False, init=False)


@dataclass(frozen=True, slots=True)
class G03RequestAssembly:
    request: asof_slice.AsOfRequest
    before_observation: G03ObservedCodeInput
    source_identity: tuple[tuple[str, str], ...]
    request_digest: str
    _witness: object | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def before_code(self) -> CodeObservation:
        return self.before_observation.code


def _checkout_root() -> Path:
    """Lexical authority comes from loaded source, never caller data or env."""
    module = PurePosixPath(__file__)
    if (
        not module.is_absolute()
        or ".." in module.parts
        or module.parts[-5:] != ("src", "pit_research_lab", "mvp", "f2", "asof_requests.py")
    ):
        raise ValueError("G03_CHECKOUT_LAYOUT_INVALID")
    return Path(module.parents[4])


def _regular_bytes(path: Path) -> bytes:
    for part in (*reversed(path.parents), path):
        if part.is_symlink():
            raise ValueError("G03_SYMLINK_REFUSED")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("G03_NONREGULAR_OR_LINKED_FILE")
    return path.read_bytes()


def _status_valid(status: str) -> bool:
    for line in status.splitlines():
        # Native observe_code strips its subprocess output, including the first
        # porcelain line's leading space. Parse that actual representation.
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2 or parts[0] not in {"??", "M"} or parts[1] not in _STATUS_PATHS:
            return False
    return True


def observation_reason(value: G03ObservedCodeInput | G03ObservationUnavailable) -> str | None:
    """Pure check of an actual boundary-issued receipt and fixed Native pins."""
    if isinstance(value, G03ObservationUnavailable):
        return value.reason
    if not isinstance(value, G03ObservedCodeInput) or value._witness is not _OBSERVED:
        return "G03_OBSERVATION_NOT_ISSUED"
    code = value.code
    if value.checkout_root != str(_checkout_root()) or not _status_valid(code.worktree_status):
        return "G03_OBSERVATION_SCOPE_INVALID"
    if tuple((p.path, p.sha256) for p in code.observed_working_files) != tuple(
        (p, h) for p, h, _ in NATIVE_CODE_PINS
    ) or code.byte_lengths != tuple(n for _, _, n in NATIVE_CODE_PINS):
        return "G03_OBSERVATION_PIN_MISMATCH"
    if (
        re.fullmatch("[0-9a-f]{40}", code.head) is None
        or re.fullmatch("[0-9a-f]{40}", code.head_tree) is None
        or code.interpretation != "OBSERVED_DISK_BYTES; HEAD_IS_NOT_COMPLETE_CODE_VERSION"
    ):
        return "G03_OBSERVATION_SCOPE_INVALID"
    return None


def observe_g03_code() -> G03ObservedCodeInput | G03ObservationUnavailable:
    """Explicit trusted caller I/O. No root parameter, source parsing or selection."""
    try:
        root = _checkout_root()
        module = root / "src/pit_research_lab/mvp/f2/asof_requests.py"
        _regular_bytes(module)
        if Path(asof_slice.__file__) != root / "src/pit_research_lab/domain/asof_slice.py":
            raise ValueError("G03_LOADED_OWNER_ROOT_MISMATCH")
        top = subprocess.check_output(
            ["git", "--no-optional-locks", "-C", str(root), "rev-parse", "--show-toplevel"],
            text=True,
        ).strip()
        if top != str(root) or root.resolve() != root:
            raise ValueError("G03_GIT_ROOT_MISMATCH")
        for path, digest, length in NATIVE_CODE_PINS:
            body = _regular_bytes(root / path)
            if len(body) != length or sha256(body).hexdigest() != digest:
                raise ValueError("G03_OBSERVATION_PIN_MISMATCH")
        code = asof_slice.observe_asof_code(root)
        value = G03ObservedCodeInput(code, str(root))
        object.__setattr__(value, "_witness", _OBSERVED)
        if reason := observation_reason(value):
            return G03ObservationUnavailable(reason)
        return value
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return G03ObservationUnavailable(str(error))


# Closed source-input constructors only. No completed owner/result types and no
# dynamic import, Native private decoder, scratch code or test dependency.
_CONSTRUCTORS: dict[str, type[c.Record]] = {
    cls.__name__: cls
    for cls in (
        c.AssertionFacts,
        c.AwareInstant,
        c.CandidateProfile,
        c.CodePin,
        c.ContentFacts,
        c.ContentPin,
        c.FieldOrigin,
        c.IssuerBindingRequest,
        c.Known,
        c.NotApplicable,
        c.NotEvaluated,
        c.OriginKnownValue,
        c.OriginUnknownValue,
        c.PublicationEventFacts,
        c.RequestBindingAttempt,
        c.RequestedTuple,
        c.RoleRef,
        c.S1Scope,
        c.SemanticContext,
        c.SourceRecords,
        c.SubjectFacts,
        c.SupportBinding,
        c.TemporalPolicy,
        c.TimeProof,
        c.Unknown,
        s.CandidateSource,
        s.CoverageCheck,
        s.DirectRelation,
        s.DiscoveryEvidence,
        s.DiscoveryExclusion,
        s.HistoricalLead,
        s.LeadEvidence,
        s.RelationSource,
        s.RevisionScope,
        s.SelectionPolicy,
    )
}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("G03_DUPLICATE_SOURCE_KEY")
        value[key] = item
    return value


def _json(body: bytes) -> Any:
    return json.loads(body, object_pairs_hook=_pairs)


def _unblob(value: dict[str, Any]) -> bytes:
    if value["encoding"] != "zlib+base64" or not 0 <= value["decoded_length"] <= 32_000_000:
        raise ValueError("G03_BLOB_ENCODING_INVALID")
    stream = zlib.decompressobj()
    body = stream.decompress(base64.b64decode(value["data"], validate=True), 32_000_001)
    if (
        not stream.eof
        or stream.unused_data
        or stream.unconsumed_tail
        or len(body) != value["decoded_length"]
        or sha256(body).hexdigest() != value["decoded_sha256"]
    ):
        raise ValueError("G03_SOURCE_BLOB_PIN_MISMATCH")
    return body


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_decode(v) for v in value)
    if not isinstance(value, dict):
        return value
    if "enum" in value:
        return {"Visibility": c.Visibility, "UnknownCause": c.UnknownCause}[value["enum"]](
            value["value"]
        )
    if "bytes_hex" in value:
        return bytes.fromhex(value["bytes_hex"])
    if "date" in value:
        return date.fromisoformat(value["date"])
    if value.get("wire_type") == "date":
        return date.fromisoformat(value["iso8601"])
    if value.get("wire_type") == "bytes":
        body = base64.b64decode(value["base64"], validate=True)
        if len(body) != value["byte_len"] or sha256(body).hexdigest() != value["sha256"]:
            raise ValueError("G03_SOURCE_RAW_PIN_MISMATCH")
        return body
    name = value.get("type", value.get("native_type"))
    if not isinstance(name, str):
        raise ValueError("G03_SOURCE_TYPE_MISMATCH")
    cls = _CONSTRUCTORS[name]
    source = (
        value["fields"]
        if "native_type" in value
        else {k: v for k, v in value.items() if k != "type"}
    )
    descriptions = {f.name: f for f in fields(cls)}
    if set(source) - set(descriptions):
        raise ValueError("G03_SOURCE_FIELD_UNSUPPORTED")
    kwargs = {k: _decode(v) for k, v in source.items() if descriptions[k].init}
    if cls in (c.FieldOrigin, c.RoleRef):
        kwargs["visibility"] = c.Visibility(kwargs["visibility"])
    if cls in (c.Unknown, c.OriginUnknownValue):
        kwargs["cause"] = c.UnknownCause(kwargs["cause"])
    result = cls(**kwargs)
    for key, desc in descriptions.items():
        if not desc.init and key in source and getattr(result, key) != _decode(source[key]):
            raise ValueError("G03_SOURCE_DERIVED_FIELD_MISMATCH")
    return result


def _typed[T: c.Record](value: Any, cls: type[T]) -> T:
    decoded = _decode(value)
    if not isinstance(decoded, cls):
        raise ValueError("G03_SOURCE_TYPE_MISMATCH")
    return decoded


@lru_cache(maxsize=1)
def _source_json(corpus: bytes, base: bytes) -> tuple[Any, Any]:
    return _json(corpus), _json(base)


@lru_cache(maxsize=40)
def _source_request(source: G03SourceInput) -> asof_slice.AsOfRequest:
    corpus, base = _source_json(source.corpus_bytes, source.s1s2_fixture_bytes)
    profile = corpus["discovery_source"]["profiles"][source.profile_id]
    descriptor = _unblob(profile["descriptor_bytes"])

    def hydrate(value: Any) -> Any:
        if isinstance(value, list):
            return [hydrate(v) for v in value]
        if not isinstance(value, dict):
            return value
        if "adopted_fixture_record" in value:
            record = base["records"][value["adopted_fixture_record"]]
            return s.CandidateSource(
                _typed(record["subject"], c.SubjectFacts),
                _typed(record["request"], c.IssuerBindingRequest),
                c.NotApplicable("S3", "NO_HISTORICAL_CLUE"),
            )
        if "notice_record" in value:
            notice = corpus["source_notices"][value["notice_record"]]
            result = _typed(_json(_unblob(notice["native_notice"])), s.CandidateSource)
            raw = base64.b64decode(notice["raw_base64"], validate=True)
            if (
                raw != result.request.content.raw_bytes
                or len(raw) != notice["byte_length"]
                or sha256(raw).hexdigest() != notice["sha256"]
            ):
                raise ValueError("G03_NOTICE_SOURCE_MISMATCH")
            return result
        if "descriptor_bytes_ref" in value:
            if value["descriptor_bytes_ref"] != source.profile_id:
                raise ValueError("G03_DESCRIPTOR_REFERENCE_MISMATCH")
            return descriptor
        return {k: hydrate(v) for k, v in value.items()}

    # Hydrated values already constructed above are immutable Native Records.
    evidence = _typed(
        hydrate(_json(_unblob(profile["retained_native_source"]))), s.DiscoveryEvidence
    )
    context = _typed(_json(_unblob(profile["native_context"])), c.SemanticContext)
    if descriptor != evidence.raw_bytes or descriptor != s.discovery_proposition(evidence):
        raise ValueError("G03_DISCOVERY_SOURCE_MISMATCH")
    policy = evidence.policy
    if (
        policy.version != s.B02_POLICY_VERSION
        or policy.evaluator_ref != s.B02_EVALUATOR_REF
        or policy.required_checks != s.REQUIRED_CHECKS
        or evidence.context_ref != context.context_ref
        or evidence.evidence_set_ref != context.evidence_set_ref
        or evidence.cutoff_text != context.information_cutoff.source_text
        or policy.subject_ref != evidence.subject.subject_ref
        or context.target_ref != policy.target
        or policy.policy_ref not in context.policy_refs
        or tuple((p.path, p.sha256) for p in context.profile.code_pins)
        != tuple((p, h) for p, h, _ in NATIVE_CODE_PINS[:6])
    ):
        raise ValueError("G03_POLICY_CONTEXT_OR_DECLARED_PIN_MISMATCH")
    operations = corpus["coverage_source"][source.profile_id]["checks"]
    if len(operations) != len(evidence.checks):
        raise ValueError("G03_OPERATION_SOURCE_MISMATCH")
    for operation, check in zip(operations, evidence.checks, strict=True):
        raw = base64.b64decode(operation["operation_raw_base64"], validate=True)
        if (
            raw != check.evidence_bytes
            or len(raw) != operation["byte_length"]
            or sha256(raw).hexdigest() != operation["sha256"]
            or operation["check_ref"] != check.check_ref
            or tuple(operation["evidence_refs"]) != check.evidence_refs
        ):
            raise ValueError("G03_OPERATION_SOURCE_MISMATCH")
    coverage = s.BoundedCoverage(
        "G03-COVERAGE-" + source.profile_id,
        context.context_ref,
        context.evidence_set_ref,
        policy.policy_ref,
        policy.version,
        policy.discovery_scope_ref,
        policy.source_refs,
        tuple(x.request.requested.target_ref for x in evidence.candidates),
        tuple(x.relation.relation_ref for x in evidence.relations),
        evidence.checks,
    )
    return asof_slice.AsOfRequest(
        context,
        evidence.subject,
        policy,
        coverage,
        evidence.candidates,
        evidence.relations,
        evidence,
    )


def assembly_valid(assembly: G03RequestAssembly) -> bool:
    return (
        assembly._witness is _PREPARED
        and observation_reason(assembly.before_observation) is None
        and assembly.request_digest == sha256(repr(assembly.request).encode()).hexdigest()
    )


def prepare_asof_request(
    pack: SyntheticInputPack,
    tick_bytes: bytes,
    source: G03SourceInput,
    observed: G03ObservedCodeInput | G03ObservationUnavailable,
    /,
) -> G03RequestAssembly | G03MappingRefusal:
    """Pure mapping; neither evaluates owners nor reads results/oracle fields.

    Refusal order: exact source pins, pack, tick, source constructors, observation.
    Native retains semantic authority for the approved negative source profiles;
    FAILED/NOT_PERFORMED operations are preserved, never upgraded to completed.
    """
    if (
        not isinstance(source, G03SourceInput)
        or type(source.corpus_bytes) is not bytes
        or type(source.s1s2_fixture_bytes) is not bytes
        or type(source.profile_id) is not str
    ):
        return G03MappingRefusal("S01_SOURCE", "G03_SOURCE_INPUT_INVALID")
    if (
        len(source.corpus_bytes) != 1_064_666
        or sha256(source.corpus_bytes).hexdigest() != CORPUS_SHA256
        or len(source.s1s2_fixture_bytes) != 8_803_308
        or sha256(source.s1s2_fixture_bytes).hexdigest() != S1S2_SHA256
    ):
        return G03MappingRefusal("S01_SOURCE", "G03_SOURCE_NOT_ACCEPTED")
    if not isinstance(pack, SyntheticInputPack):
        return G03MappingRefusal("S02_PACK", "G03_PACK_INVALID")
    try:
        verify_input_pack(pack)
    except InputError as error:
        return G03MappingRefusal("S02_PACK", "G03_PACK_INVALID", type(error).__name__, error.code)
    if pack.payload_sha256 != PACK_SHA256:
        return G03MappingRefusal("S02_PACK", "G03_PACK_IDENTITY_MISMATCH")
    if type(tick_bytes) is not bytes or tick_bytes not in build_weekly_requests(pack).requests:
        return G03MappingRefusal("S03_TICK", "G03_TICK_NOT_MEMBER")
    try:
        tick = decode_input_bytes(tick_bytes)
        request = _source_request(source)
        if tick["cutoff"]["source_text"] != request.context.information_cutoff.source_text:
            return G03MappingRefusal("S03_TICK", "G03_CUTOFF_IDENTITY_MISMATCH")
    except c.ContractError as error:
        return G03MappingRefusal(
            "S04_SOURCE_CONSTRUCTION",
            "G03_NATIVE_CONSTRUCTOR_REJECTED",
            type(error).__name__,
            str(error),
        )
    except (InputError, KeyError, ValueError, TypeError, binascii.Error, zlib.error) as error:
        return G03MappingRefusal(
            "S04_SOURCE_CONSTRUCTION",
            "G03_SOURCE_CONSTRUCTION_REJECTED",
            type(error).__name__,
            str(error),
        )
    if reason := observation_reason(observed):
        return G03MappingRefusal("S05_OBSERVATION", reason)
    assert isinstance(observed, G03ObservedCodeInput)
    identity = (
        ("corpus_sha256", CORPUS_SHA256),
        ("s1s2_fixture_sha256", S1S2_SHA256),
        ("pack_sha256", pack.payload_sha256),
        ("tick_sha256", sha256(tick_bytes).hexdigest()),
        ("profile_id", source.profile_id),
        ("cutoff", request.context.information_cutoff.source_text),
        ("original_context_ref", cast(str, tick["context_ref"])),
        ("manifest_ref", cast(str, tick["manifest_ref"])),
        ("config_ref", cast(str, tick["config_ref"])),
        ("calendar_ref", cast(str, tick["calendar_ref"])),
    )
    assembly = G03RequestAssembly(
        request, observed, identity, sha256(repr(request).encode()).hexdigest()
    )
    object.__setattr__(assembly, "_witness", _PREPARED)
    return assembly
