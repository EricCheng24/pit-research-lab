"""RS3F exact-use controller. Human-reviewed policy, never machine authentication.

There is no discovery, caller permission receipt, generalized real-source gate,
or Business Wire path. The two original RS2 modules are left byte-identical.
"""

import os
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Final

from pit_research_lab.domain.contracts import CodePin, ContractError, NotEvaluated, Record, require
from pit_research_lab.domain.issuer_html_extraction import HtmlEvidenceObservation, extract_html
from pit_research_lab.domain.issuer_html_slice import _identity, _read_html_relative
from pit_research_lab.domain.sec_financial_diagnostic import (
    GOV_PIN,
    MANIFEST_PIN,
    SEC_PIN,
    SEC_SPEC,
    SNAPSHOT,
    VIEW_SHA,
    FinancialDiagnostic,
    build_diagnostic,
)
from pit_research_lab.domain.source_intake import FilePin, _open_root, json_object

DOWNLOADS: Final = "/mnt/c/Users/rooki/Downloads/"
SOURCE_ROOT: Final = DOWNLOADS + "CAP-F2-V1-A06-IC3_support_inputs"
GOVERNMENT_ROOT: Final = DOWNLOADS + "CAP-F2-V1-A06_source_inputs"
ABSENT = NotEvaluated("RS3F", "NOT_EVALUATED")
APPROVAL_STATUS: Final = "OWNER_APPROVED_HUMAN_REVIEWED_NOT_MACHINE_AUTHENTICATED"


@dataclass(frozen=True)
class ApprovedDocument(Record):
    root: str
    pin: FilePin


# Fixed by RS3F requirements and the reviewed RS3A/B1 identities, not caller JSON.
DOCUMENTS: Final = (
    ApprovedDocument(
        DOWNLOADS + "CAP-F2-V1-A06-IC3-RS3_rights_inputs",
        FilePin(
            "sec_webmaster_faq.html",
            48752,
            "8e5fbf019a0690ce242d980dc5261cd38491da8b8229959939d7afb895dd1ba6",
        ),
    ),
    ApprovedDocument(
        DOWNLOADS + "CAP-F2-V1-A06-IC3-RS3_rights_inputs",
        FilePin(
            "sec_website_dissemination.html",
            96634,
            "4dc3f502afd649fc915ea9a8dd647398ed2e790ee87f5ceeb07aa55d6d62f2ad",
        ),
    ),
    ApprovedDocument(
        DOWNLOADS + "CAP-F2-V1-A06-IC3-RS3_rights_inputs",
        FilePin(
            "rights_source_notes.txt",
            440,
            "0fd0cd7244426cafbd4940b8b02be9f180c24ee029bfe3e5851acc5f25b5bd65",
        ),
    ),
    ApprovedDocument(
        DOWNLOADS + "CAP-F2-V1-A06-IC3-RS3B1_inputs",
        FilePin(
            "CAP-F2-V1-A06-IC3-RS3B1_Owner_Approval_Verbatim_Transcription.txt",
            1241,
            "e58333112a9b494511ae9658e273fa96dca1277ebe5d5cae4f80f2e0b727121b",
        ),
    ),
    ApprovedDocument(
        DOWNLOADS + "CAP-F2-V1-A06-IC3-RS3B1_inputs",
        FilePin(
            "CAP-F2-V1-A06-IC3-RS3B1_Owner_Decision_Record_PROPOSED.json",
            5938,
            "76440ee7298c2592bf7b0e18bf293d02fc7db807fdaa3e124ee07dc4c0329dc3",
        ),
    ),
    ApprovedDocument(
        DOWNLOADS + "CAP-F2-V1-A06-IC3-RS3A_outputs_v0.1",
        FilePin(
            "CAP-F2-V1-A06-IC3-RS3A_Documentary_Freeze_Result_v0.1.md",
            22476,
            "887b33c44060d8912b46bbb5291281dcede251052fe9cd1b94ea5cc8a5faf629",
        ),
    ),
    ApprovedDocument(
        DOWNLOADS + "CAP-F2-V1-A06-IC3-RS3A_outputs_v0.1",
        FilePin(
            "CAP-F2-V1-A06-IC3-RS3A_Rights_Evidence_Inventory_PROPOSED.json",
            56407,
            "6a98e6e7bdf8c1252b801c277637d0e54d1ae6360718519b3bacd0113d51c9b6",
        ),
    ),
    ApprovedDocument(
        DOWNLOADS + "CAP-F2-V1-A06-IC3-RS3B1_outputs_v0.1",
        FilePin(
            "CAP-F2-V1-A06-IC3-RS3B1_Capture_Result_v0.1.md",
            23870,
            "167403d2ead1d55e17a23866fb63acdbe52d7e87102a47b34f3ed7ed5d121b40",
        ),
    ),
    ApprovedDocument(
        DOWNLOADS + "CAP-F2-V1-A06-IC3-RS3B1_outputs_v0.1",
        FilePin(
            "CAP-F2-V1-A06-IC3-RS3B1_Decision_Evidence_Inventory_PROPOSED.json",
            48712,
            "0e615cd99cf15d4ec50c1ea92611061252201b20716dd6db6d70440be6a5b236",
        ),
    ),
)
_DOMAIN = "src/pit_research_lab/domain/"
PINNED_CODE: Final = tuple(
    CodePin(_DOMAIN + name, digest)
    for name, digest in (
        (
            "issuer_html_extraction.py",
            "f6cdc70564b4836543f732dfaed630e1f0a563986e88145f748a7e8d7d0e9cd3",
        ),
        (
            "issuer_html_slice.py",
            "4930e8635729b5d7d92cf4202595575f1e2edd2b19d3512996beb3386411b425",
        ),
        ("contracts.py", "ea4b630f6482badb0ba69b697f1903bd7f778d32cac1269e194fa50563b7c82f"),
        ("source_intake.py", "c59235802a73f3285e98fbff72d5faa97e8797324bcbcf3f5e3b8cf60e48a240"),
        ("source_adapter.py", "afaec82a33bded42b567f0d1bd2305d5a823f5b965e87ca6494747fb1108c4df"),
        (
            "market_row_selection.py",
            "2167b7649fd5b6051c924af146839eecdaee6e31bf8948d7d28b1d82b57440af",
        ),
        ("offline_replay.py", "d6c84c3a647bacd06e6dc06cc57f3139219b07742e766c67f6910be5fe273e7b"),
        (
            "financial_semantics.py",
            "df447297f91404f9bd1431de1d709d14b36f60e3c473993cd6f3b16050a4a960",
        ),
    )
)
BRIDGE_PATHS: Final = (_DOMAIN + "sec_real_closure.py", _DOMAIN + "sec_financial_diagnostic.py")
EXCLUSIONS: Final = (
    "SEC seals and logos",
    "images",
    "scripts",
    "sidecars",
    "Business Wire content",
    "commercial redistribution",
    "generalized SEC crawling",
)
NO_GRANTS: Final = (
    "source authentication",
    "historical PIT availability",
    "IC3 canonical mapping",
    "S1 admission",
    "Golden acceptance",
)


@dataclass(frozen=True)
class SecUseRequest(Record):
    issuer: str = "United Microelectronics Corporation"
    cik: str = "0001033767"
    accession: str = "0001193125-26-414888"
    exhibit: str = "Exhibit 99.2"
    purpose: str = "OFFLINE_RESEARCH"
    reference_month: str = "2026-09"
    source_root: str = SOURCE_ROOT
    source_pin: FilePin = SEC_PIN
    profile_id: str = "SEC-EX99_2-SAVEDHTML"
    classification: str = "OWNER_SUPPLIED_EXTERNAL"


APPROVED_REQUEST: Final = SecUseRequest()


@dataclass(frozen=True)
class ReadEvent(Record):
    sequence: int
    stage: str
    path: str
    state: str


@dataclass(frozen=True)
class SecClosureResult(Record):
    status: str
    reason: str
    source_use: str
    events: tuple[ReadEvent, ...]
    body_read_attempts: tuple[str, ...]
    observation: HtmlEvidenceObservation | NotEvaluated = ABSENT
    diagnostic: FinancialDiagnostic | NotEvaluated = ABSENT
    code_context: tuple[CodePin, ...] = ()
    audit_label_non_pit: str = ""
    source_body: NotEvaluated = field(default=ABSENT, init=False)
    admission_eligible: bool = field(default=False, init=False)
    source_authentication: str = field(default="NOT_ESTABLISHED", init=False)
    trust: str = field(default="NOT_TRUSTED_PIT_EVIDENCE", init=False)


def _read_pinned(root: Path, pin: FilePin) -> bytes:
    """Shared RS2 bounded descriptor read, with stable root re-resolution.

    No directory enumeration and no follow of symlink components or special files.
    Identity/mtime are race guards only, never historical event evidence.
    """
    fd = _open_root(root)
    try:
        original_root = _identity(os.fstat(fd))
        body = _read_html_relative(fd, pin)
        current = _open_root(root)
        try:
            require(
                original_root == _identity(os.fstat(current)), "SOURCE_ROOT_CHANGED_DURING_READ"
            )
        finally:
            os.close(current)
        return body
    finally:
        os.close(fd)


def _disk_code() -> tuple[CodePin, ...]:
    repository = Path(__file__).absolute().parents[3]
    fd = _open_root(repository)
    try:
        result = []
        # Existing accepted implementation must match pins, before any financial body open.
        from pit_research_lab.domain.source_intake import _read_relative

        for pin in PINNED_CODE:
            body = _read_relative(fd, pin.path, 65536)
            require(sha256(body).hexdigest() == pin.sha256, "CODE_PROFILE_PIN_MISMATCH")
            result.append(pin)
        for name in BRIDGE_PATHS:
            body = _read_relative(fd, name, 65536)
            result.append(CodePin(name, sha256(body).hexdigest()))
        return tuple(result)
    finally:
        os.close(fd)


def _validate_decision(body: bytes) -> None:
    """Exact record scope plus whole-file pin; authority is the fixed reviewed policy.

    Its original PENDING preparer-only fields are retained honestly: independent
    human acceptance comes from the governing execution context, not those fields.
    """
    data = json_object(body)
    expected = {
        "accession": "0001193125-26-414888",
        "cik": "0001033767",
        "conditional_permitted_operation": "AFTER_RIGHTS_EVIDENCE_AND_INDEPENDENT_VERIFICATION: offline read-only inert HTML locating and original-preserving extraction to a separately hashed view with SEC EDGAR attribution",
        "content": "Exhibit 99.2 text and financial table content only",
        "exclusions": list(EXCLUSIONS),
        "exhibit": "Exhibit 99.2",
        "express_no_grants": list(NO_GRANTS),
        "filing": "SEC EDGAR Form 6-K",
        "issuer": "United Microelectronics Corporation",
        "purpose": "OFFLINE_RESEARCH",
        "source_capture": {
            "bytes": SEC_PIN.byte_length,
            "capture_class": "BROWSER_SAVED_CAPTURE",
            "relative_path": SEC_PIN.relative_path,
            "sha256": SEC_PIN.sha256,
        },
        "system": "PIT Research Lab",
        "temporal_class": "NON_PIT",
    }
    require(data.get("actual_approved_scope") == expected, "OWNER_DECISION_SCOPE_MISMATCH")
    require(
        data.get("record_schema") == "CAP-F2-V1-A06-IC3-RS3B1-OWNER-DECISION-PROPOSED-v0.1"
        and data.get("decision_status") == "APPROVED_IN_CONVERSATION"
        and data.get("authorizer_identity") == "NOT_INDEPENDENTLY_AUTHENTICATED"
        and data.get("decision_time_basis") == "NON_PIT_NO_TRUSTED_MESSAGE_TIME_OBSERVED"
        and data.get("decision_message_native_id") is None
        and data.get("decision_message_server_timestamp") is None
        and data.get("decision_message_raw_transport_bytes_available") is False,
        "OWNER_DECISION_ASSURANCE_MISMATCH",
    )
    require(
        data.get("chat_transcription")
        == {
            "bom": False,
            "bytes": 1241,
            "filename": DOCUMENTS[3].pin.relative_path,
            "raw_chat_message_hash_is_this": False,
            "sha256": DOCUMENTS[3].pin.sha256,
            "source": "assistant_transcription_of_user_message",
            "trailing_newline": False,
            "unicode_normalization": "NONE",
        },
        "TRANSCRIPTION_LINK_MISMATCH",
    )
    documentary = data.get("documentary_basis")
    require(isinstance(documentary, dict), "DOCUMENTARY_LINK_MISMATCH")
    assert isinstance(documentary, dict)
    require(
        documentary.get("policy_capture_pins")
        == [
            {
                "bytes": doc.pin.byte_length,
                "classification": "BROWSER_SAVED_POLICY_CAPTURES",
                "relative_path": doc.pin.relative_path,
                "sha256": doc.pin.sha256,
            }
            for doc in DOCUMENTS[:2]
        ]
        and documentary.get("rights_source_notes_pin")
        == {
            "bytes": DOCUMENTS[2].pin.byte_length,
            "relative_path": DOCUMENTS[2].pin.relative_path,
            "sha256": DOCUMENTS[2].pin.sha256,
        },
        "DOCUMENTARY_LINK_MISMATCH",
    )
    for key, doc in (("rs3a_report", DOCUMENTS[5]), ("rs3a_inventory", DOCUMENTS[6])):
        require(
            documentary.get(key)
            == {
                "bytes": doc.pin.byte_length,
                "filename": doc.pin.relative_path,
                "sha256": doc.pin.sha256,
            },
            "RS3A_LINK_MISMATCH",
        )
    baseline = data.get("engineering_baseline")
    require(isinstance(baseline, dict), "BASELINE_LINK_MISMATCH")
    assert isinstance(baseline, dict)
    require(
        baseline.get("ic2_manifest_sha256") == MANIFEST_PIN.sha256
        and baseline.get("ic2_snapshot") == SNAPSHOT,
        "BASELINE_LINK_MISMATCH",
    )


def run_sec_diagnostic(
    request: SecUseRequest = APPROVED_REQUEST,
    *,
    cutoff: str | None = None,
    audit_label_non_pit: str = "",
) -> SecClosureResult:
    """One fixed approved use. Refusal never returns partially read/extracted content."""
    events: list[ReadEvent] = []
    attempts: tuple[str, ...] = ()
    authority = "NOT_CHECKED"
    code: tuple[CodePin, ...] = ()

    def event(stage: str, path: str, state: str) -> None:
        events.append(ReadEvent(len(events) + 1, stage, path, state))

    def read(root: str, pin: FilePin, stage: str) -> bytes:
        event(stage, root + "/" + pin.relative_path, "ATTEMPTED")
        body = _read_pinned(Path(root), pin)
        event(stage, root + "/" + pin.relative_path, "READ_STABLE_PIN_MATCH")
        return body

    try:
        require(
            type(request) is SecUseRequest and request == SecUseRequest(),
            "OUTSIDE_IMMUTABLE_APPROVED_SCOPE_NO_CALLER_AUTHORITY",
        )
        require(
            type(audit_label_non_pit) is str and len(audit_label_non_pit) <= 256,
            "INVALID_AUDIT_LABEL",
        )
        code = _disk_code()
        event("PRE_SOURCE_BODY_OPEN", "CODE_PROFILE", "ACCEPTED_RS2_CODE_PIN_MATCH")
        decision = b""
        for doc in DOCUMENTS:
            body = read(doc.root, doc.pin, "PRE_SOURCE_BODY_OPEN")
            if doc == DOCUMENTS[4]:
                decision = body
        _validate_decision(decision)
        authority = APPROVAL_STATUS
        event("PRE_SOURCE_BODY_OPEN", "EXACT_SCOPE_AND_EXCLUSIONS", authority)
        # Government manifest is also exact and permission-checked before its CSV body read.
        manifest_body = read(GOVERNMENT_ROOT, MANIFEST_PIN, "GOVERNMENT_MANIFEST")
        from pit_research_lab.domain.market_row_selection import preflight_manifest
        from pit_research_lab.domain.source_intake import decode_manifest

        manifest = decode_manifest(manifest_body)
        require(
            manifest.raw == GOV_PIN
            and manifest.mapping_file is None
            and manifest.snapshot_ref == SNAPSHOT
            and preflight_manifest(manifest).reason == "RIGHTS_PREFLIGHT_PASSED",
            "GOVERNMENT_PREFLIGHT_FAILED",
        )
        attempts = (SOURCE_ROOT + "/" + SEC_PIN.relative_path,)
        body = read(SOURCE_ROOT, SEC_PIN, "SEC_SOURCE_BODY_READ")
        observation = extract_html(body, SEC_PIN, SEC_SPEC, code[:2])
        require(
            isinstance(observation, HtmlEvidenceObservation),
            "SEC_EXTRACTION_REFUSED:" + getattr(observation, "reason", "INVALID_RESULT"),
        )
        assert isinstance(observation, HtmlEvidenceObservation)
        require(observation.view.generated_view_sha256 == VIEW_SHA, "RS2_VIEW_REFERENCE_MISMATCH")
        event("EXTRACTION", SEC_PIN.relative_path, "DOCUMENT_CONTENT_OBSERVED_UNADMITTED")
        government_body = read(GOVERNMENT_ROOT, GOV_PIN, "GOVERNMENT_ORIGINAL_READ")
        diagnostic = build_diagnostic(
            observation, manifest_body, government_body, code, cutoff=cutoff
        )
        event("DIAGNOSTIC", diagnostic.research_ref, "GENERATED_NOT_CANONICAL_MAPPING")
        return SecClosureResult(
            "IMPLEMENTED_PROVISIONAL",
            "PENDING_INDEPENDENT_REVIEW",
            authority,
            tuple(events),
            attempts,
            observation,
            diagnostic,
            code,
            audit_label_non_pit,
        )
    except (ContractError, OSError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, (ContractError, ValueError)) else "UNSAFE_PATH_OR_READ"
        event("REFUSAL", "NO_OBSERVATION_OR_DIAGNOSTIC_EMITTED", reason)
        return SecClosureResult(
            "REFUSED",
            reason,
            authority,
            tuple(events),
            attempts,
            code_context=code,
            audit_label_non_pit=audit_label_non_pit,
        )
