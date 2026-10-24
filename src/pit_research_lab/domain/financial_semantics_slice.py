"""IC3 explicit offline reads and pure research boundary; no source bundle writes."""

import os
from dataclasses import dataclass, field, fields
from hashlib import sha256
from pathlib import Path

from pit_research_lab.domain.contracts import CodePin, ContractError, NotEvaluated, Record, require
from pit_research_lab.domain.derivation import S4_CODE_PATHS
from pit_research_lab.domain.financial_semantics import (
    ABSENT,
    VERSION,
    FinancialSemanticAssessment,
    SupportInput,
    assess_financial_semantics,
    checked_body,
    decode_support,
)
from pit_research_lab.domain.market_row_selection import (
    FullMarketSelectionSpec,
    SelectedSourceRow,
    canonical,
)
from pit_research_lab.domain.market_source_slice import (
    IC1_CODE_PATHS,
    IC1CodeObservation,
    observe_ic1_code,
)
from pit_research_lab.domain.offline_replay import A06_CODE_PATHS
from pit_research_lab.domain.pit_slice import CODE_PATHS
from pit_research_lab.domain.ratio import RATIO_CODE_PATHS
from pit_research_lab.domain.selection import S3_CODE_PATHS
from pit_research_lab.domain.source_intake import (
    MAX_METADATA_BYTES,
    IntakeResult,
    _open_root,
    _read_relative,
)

IC3_CODE_PATHS = (
    "src/pit_research_lab/domain/financial_semantics.py",
    "src/pit_research_lab/domain/financial_semantics_slice.py",
)
OWNERS = ("S1", "S2", "S3", "A04", "A05")


def inspect_financial_support(root: Path | None) -> SupportInput:
    """Only an explicit root is traversed. All rights precede every body read.

    No external root means no I/O. Metadata failure/refusal retains no body.
    This checks supplied records, not legal validity or publisher signatures.
    """
    if root is None:
        return SupportInput()
    fd: int | None = None
    attempts: list[str] = []
    try:
        fd = _open_root(root)
        attempts.append("support.json")
        metadata = _read_relative(fd, "support.json", MAX_METADATA_BYTES)
        manifest = decode_support(metadata)
        pins = manifest.evidence + ((manifest.crosswalk,) if manifest.crosswalk else ())
        bodies: list[tuple[str, bytes]] = []
        for pin in pins:
            attempts.append(pin.file.relative_path)
            body = _read_relative(fd, pin.file.relative_path, MAX_METADATA_BYTES)
            checked_body(pin, ((pin.file.relative_path, body),))
            bodies.append((pin.file.relative_path, body))
        return SupportInput(
            metadata, tuple(bodies), "SUPPORT_BYTES_READ_NOT_ADJUDICATED", tuple(attempts)
        )
    except FileNotFoundError:
        reason = "SUPPORT_INPUT_PENDING" if len(attempts) <= 1 else "PINNED_SUPPORT_FILE_MISSING"
    except (OSError, ContractError) as exc:
        reason = str(exc) if isinstance(exc, ContractError) else "UNSAFE_SUPPORT_PATH_OR_READ"
    finally:
        if fd is not None:
            os.close(fd)
    return SupportInput(reason=reason, read_attempts=tuple(attempts))


@dataclass(frozen=True)
class IC3CodeObservation(Record):
    upstream_ic1: IC1CodeObservation
    extension_pins: tuple[CodePin, ...]
    extension_byte_lengths: tuple[int, ...]
    interpretation: str = "OBSERVED_DISK_BYTES; NOT_RUNTIME_ATTESTED"


def observe_ic3_code(repository: Path) -> IC3CodeObservation:
    """Explicit outer observation; old 10+2+3+2 shapes remain untouched."""
    upstream = observe_ic1_code(repository)
    fd = _open_root(repository)
    try:
        bodies = tuple(_read_relative(fd, path, MAX_METADATA_BYTES) for path in IC3_CODE_PATHS)
    finally:
        os.close(fd)
    return IC3CodeObservation(
        upstream,
        tuple(
            CodePin(path, sha256(body).hexdigest())
            for path, body in zip(IC3_CODE_PATHS, bodies, strict=True)
        ),
        tuple(len(body) for body in bodies),
    )


def _audit_key(value: object) -> object:
    """Hash bodies instead of copying source/evidence text into a research identity."""
    if isinstance(value, bytes):
        return {"sha256": sha256(value).hexdigest(), "bytes": len(value)}
    if isinstance(value, Record):
        return {f.name: _audit_key(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, tuple):
        return [_audit_key(v) for v in value]
    if value is None or type(value) in (str, int, bool):
        return value
    # Selected source intervals are immutable dates, not publication times.
    return str(value)


@dataclass(frozen=True)
class IC3ResearchResult(Record):
    assessment: FinancialSemanticAssessment
    research_ref: str
    code: IC3CodeObservation
    owner_results: tuple[tuple[str, NotEvaluated], ...] = field(
        default=tuple(
            (owner, NotEvaluated(owner, "UNSUPPORTED_EXTERNAL_SOURCE_SCHEMA")) for owner in OWNERS
        ),
        init=False,
    )
    disposition: str = field(default="INTEGRATED_PROVISIONAL", init=False)
    trust: str = field(default="NOT_TRUSTED_PIT_EVIDENCE", init=False)
    source_authentication: str = field(default="NOT_ESTABLISHED", init=False)
    admission_eligible: bool = field(default=False, init=False)
    diagnostic_only: bool = field(default=True, init=False)
    agent_observation: str = field(default="NOT_PRODUCED", init=False)
    typed_transport: str = field(default="UNSUPPORTED_EXTERNAL_SOURCE_SCHEMA", init=False)
    historical_publication_proof: NotEvaluated = field(default=ABSENT, init=False)
    diagnostic_preview_bytes: bytes = field(
        default=canonical(
            {
                "availability": "WITHHELD",
                "disposition": "INTEGRATED_PROVISIONAL",
                "trust": "NOT_TRUSTED_PIT_EVIDENCE",
                "admission_eligible": False,
                "diagnostic_only": True,
                "agent_observation": "NOT_PRODUCED",
            }
        ),
        init=False,
    )


def evaluate_financial_semantics(
    intake: IntakeResult,
    spec: FullMarketSelectionSpec,
    selected: SelectedSourceRow,
    support: SupportInput,
    code: IC3CodeObservation,
    context: str = "public",
) -> IC3ResearchResult:
    """Pure consistency checks, never a claim that supplied code pins attest runtime."""
    require(context in ("public", "prospective_observed"), "UNSUPPORTED_RESEARCH_CONTEXT")
    ic1 = code.upstream_ic1
    a06 = ic1.upstream_a06
    a05 = a06.upstream_a05
    a04 = a05.upstream_a04
    for pins, lengths, paths in (
        (code.extension_pins, code.extension_byte_lengths, IC3_CODE_PATHS),
        (ic1.extension_pins, ic1.extension_byte_lengths, IC1_CODE_PATHS),
        (a06.extension_pins, a06.extension_byte_lengths, A06_CODE_PATHS),
        (a05.extension_pins, a05.extension_byte_lengths, RATIO_CODE_PATHS),
        (
            a04.observed_working_files,
            a04.byte_lengths,
            (*CODE_PATHS, *S3_CODE_PATHS, *S4_CODE_PATHS),
        ),
    ):
        require(
            tuple(p.path for p in pins) == paths
            and len(pins) == len(lengths)
            and all(type(n) is int and n >= 0 for n in lengths)
            and (paths != IC3_CODE_PATHS or all(n > 0 for n in lengths)),
            "INVALID_OUTER_CODE_OBSERVATION",
        )
    assessment = assess_financial_semantics(intake, spec, selected, support)
    research = sha256(
        canonical(_audit_key((VERSION, intake, spec, selected, support, code, context, assessment)))
    ).hexdigest()
    return IC3ResearchResult(assessment, "IC3-RESEARCH-" + research, code)
