"""Acceptance-side denial and synthetic calibration; positive admission is deferred."""

from dataclasses import dataclass, fields, is_dataclass


@dataclass(frozen=True)
class ExternalAuthority:
    """Untrusted externally supplied claims, not an authenticated root or receipt."""

    receipt_pin: str
    binding_pin: str
    actual_source_pin: str
    reviewer: str
    claimed_decision: str
    revoked: bool


@dataclass(frozen=True)
class RuntimeGrant:
    reference: str
    case_id: str
    tier: str


@dataclass(frozen=True)
class CertificationOutcome:
    verdict: str
    issues: tuple[str, ...]
    runtime_evidence: tuple[()] = ()


def certify(actual, binding, authority=None, runtime_grant=None):
    """Never elevate author-supplied strings or candidate hashes into trusted admission."""
    issues = []
    if authority is None:
        issues.append("MISSING_INDEPENDENT_AUTHORITY")
    elif not isinstance(authority, ExternalAuthority):
        issues.append("UNAUTHENTICATED_AUTHORITY_SHAPE")
    else:
        if authority.revoked:
            issues.append("REVOKED_AUTHORITY")
        if (
            not authority.receipt_pin
            or not authority.binding_pin
            or not authority.actual_source_pin
        ):
            issues.append("MISSING_EXTERNAL_PINS")
        issues.append("EXTERNAL_AUTHENTICATION_NOT_IMPLEMENTED_DEFERRED_WU01D")
    if runtime_grant is None:
        issues.append("MISSING_SEPARATE_RUNTIME_GRANT")
    elif not isinstance(runtime_grant, RuntimeGrant) or runtime_grant.tier != "S":
        issues.append("UNAUTHORIZED_RUNTIME_SCOPE")
    if getattr(binding, "status", None) != "PROPOSED / NOT_APPROVED":
        issues.append("UNTRUSTED_BINDING_ADMISSION")
    else:
        issues.append("CANDIDATE_BINDING_NOT_INDEPENDENTLY_APPROVED")
    if actual is None:
        issues.append("MISSING_ACTUAL")
    return CertificationOutcome("BLOCKED", tuple(issues))


def _typed_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_typed_equal(left[k], right[k]) for k in left)
    if isinstance(left, (tuple, list)):
        return len(left) == len(right) and all(
            _typed_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    if is_dataclass(left):
        return all(
            _typed_equal(getattr(left, f.name), getattr(right, f.name)) for f in fields(left)
        )
    return left == right


@dataclass(frozen=True)
class CalibrationOutcome:
    stimulus_id: str
    result: str
    classification: str = "SYNTHETIC_COMPARATOR_CALIBRATION_ONLY"


def calibrate(actual, expected, *, stimulus_id):
    """Typed equality on explicit artificial stimuli; never emits a Golden receipt."""
    if not isinstance(stimulus_id, str) or not stimulus_id.startswith("CAL-"):
        raise ValueError("synthetic calibration ID required")
    return CalibrationOutcome(stimulus_id, "PASS" if _typed_equal(actual, expected) else "FAIL")
