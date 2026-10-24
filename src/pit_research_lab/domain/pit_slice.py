"""Bounded S1/S2 composition. Engineering observations never grant PIT trust."""

import subprocess
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pit_research_lab.domain.contracts import (
    BlockingFailure,
    CodePin,
    ContentInventoryRequest,
    EvidenceOutcome,
    IssuerBindingRequest,
    ProviderCaptureRequest,
    Record,
    SemanticContext,
    require,
)
from pit_research_lab.domain.information import assess_evidence, inventory_content
from pit_research_lab.domain.temporal import (
    EVALUATOR_REF,
    EvidenceRequest,
    TemporalOutcome,
    qualify_temporal,
)

CODE_PATHS = (
    "src/pit_research_lab/__init__.py",
    "src/pit_research_lab/domain/__init__.py",
    "src/pit_research_lab/domain/contracts.py",
    "src/pit_research_lab/domain/information.py",
    "src/pit_research_lab/domain/temporal.py",
    "src/pit_research_lab/domain/pit_slice.py",
)


@dataclass(frozen=True)
class CodeObservation(Record):
    head: str
    head_tree: str
    observed_working_files: tuple[CodePin, ...]
    byte_lengths: tuple[int, ...]
    worktree_status: str
    interpretation: str = "OBSERVED_DISK_BYTES; HEAD_IS_NOT_COMPLETE_CODE_VERSION"


def observe_code(repository: Path) -> CodeObservation:
    """Explicit read-only diagnostic I/O boundary, outside pure composition.

    Hash only fixed implementation paths. These are observed disk bytes, not
    source authentication, independent review, or a runtime attestation. Call
    before and after a replay to check that the observed files stayed fixed.
    """

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "--no-optional-locks", "-C", str(repository), *args], text=True
        ).strip()

    require(
        Path(git("rev-parse", "--show-toplevel")).resolve() == repository.resolve(),
        "REPOSITORY_ROOT_MISMATCH",
    )
    data = tuple((repository / path).read_bytes() for path in CODE_PATHS)
    return CodeObservation(
        git("rev-parse", "HEAD"),
        git("rev-parse", "HEAD^{tree}"),
        tuple(
            CodePin(path, sha256(body).hexdigest())
            for path, body in zip(CODE_PATHS, data, strict=True)
        ),
        tuple(len(body) for body in data),
        git("status", "--short", "--untracked-files=all"),
    )


@dataclass(frozen=True)
class SliceResult(Record):
    request: EvidenceRequest
    context: SemanticContext
    s1: EvidenceOutcome | BlockingFailure
    s2: TemporalOutcome | BlockingFailure
    code_observation: CodeObservation
    declared_s1_pins: tuple[CodePin, ...]
    declared_s2_evaluator_ref: str = EVALUATOR_REF

    disposition: Literal["INTEGRATED_PROVISIONAL"] = field(
        default="INTEGRATED_PROVISIONAL", init=False
    )
    trust: Literal["NOT_TRUSTED_PIT_EVIDENCE"] = field(
        default="NOT_TRUSTED_PIT_EVIDENCE", init=False
    )
    admission_eligible: Literal[False] = field(default=False, init=False)
    diagnostic_only: Literal[True] = field(default=True, init=False)
    source_authentication: Literal["NOT_ESTABLISHED"] = field(default="NOT_ESTABLISHED", init=False)


def evaluate_slice(
    context: SemanticContext,
    request: EvidenceRequest,
    code: CodeObservation,
    /,
) -> SliceResult:
    """Run S1 then S2 with the same immutable request/context; no raw parsing/I/O.

    CodeObservation is supplied observation metadata, distinct from declared
    CandidateProfile pins. Neither constitutes authority to admit any source.
    """
    require(
        isinstance(
            request, (IssuerBindingRequest, ProviderCaptureRequest, ContentInventoryRequest)
        ),
        "UNSUPPORTED_SLICE_REQUEST",
    )
    s1 = (
        inventory_content(context, request)
        if isinstance(request, ContentInventoryRequest)
        else assess_evidence(context, request)
    )
    s2 = qualify_temporal(context, request, s1)
    return SliceResult(request, context, s1, s2, code, context.profile.code_pins)
