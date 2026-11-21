"""Detached A-only admission predicates. No parser, session issuer or server.

Bounds below are authorized synthetic-test ceilings, NOT production quotas.
HTTP framing, raw header preservation and parser normalization remain unproven.
"""

import hmac
import re
from dataclasses import dataclass

from pit_research_lab.mvp.f6 import contracts as c

BODY_CEILING = 256 * 1024
DEPTH_CEILING = 32
MEMBER_CEILING = 1000
TEXT_CEILING = 16 * 1024
PREFIX = "/api/f6/fixed-research/v0.1"
type Headers = tuple[tuple[str, str], ...]


def _require(condition: bool, reason: c.Reason = c.Reason.INVALID_REQUEST) -> None:
    if not condition:
        raise c.ContractError(reason)


def _headers(headers: Headers) -> dict[str, tuple[str, ...]]:
    _require(type(headers) is tuple and len(headers) <= 64)
    result: dict[str, tuple[str, ...]] = {}
    total = 0
    for entry in headers:
        _require(type(entry) is tuple and len(entry) == 2)
        name, value = entry
        _require(type(name) is str and type(value) is str)
        total += len(name) + len(value)
        _require(total <= TEXT_CEILING)
        _require(re.fullmatch(r"[A-Za-z0-9-]{1,64}", name) is not None)
        _require(all(32 <= ord(ch) < 127 for ch in value) and value == value.strip())
        key = name.lower()
        result[key] = (*result.get(key, ()), value)
    return result


def _one(headers: dict[str, tuple[str, ...]], key: str, reason: c.Reason) -> str:
    values = headers.get(key, ())
    _require(len(values) == 1, reason)
    return values[0]


def literal_authority(expected: str) -> str:
    _require(type(expected) is str, c.Reason.HOST_REJECTED)
    match = re.fullmatch(r"127\.0\.0\.1:([1-9][0-9]{0,4})", expected)
    _require(match is not None, c.Reason.HOST_REJECTED)
    assert match is not None
    _require(int(match[1]) <= 65535, c.Reason.HOST_REJECTED)
    return expected


def canonical_path(target: str) -> str:
    """Recognize fixed route *syntax*, with no route implementation or file mapping."""
    _require(type(target) is str and len(target) <= 256)
    fixed = {PREFIX + suffix for suffix in ("/bootstrap", "/capability", "/submissions")}
    if target in fixed:
        return target
    match = re.fullmatch(re.escape(PREFIX) + r"/runs/([^/]+)(?:/(result|evidence))?", target)
    _require(match is not None)
    assert match is not None
    c.uuid4_text(match[1])
    return target


def check_authority(headers: Headers, target: str, expected_authority: str) -> None:
    expected = literal_authority(expected_authority)
    parsed = _headers(headers)
    _require(
        not any(
            key == "forwarded"
            or key.startswith(("x-forwarded-", "x-original-", "x-rewrite-"))
            or key in ("via", "host-override", "x-host", "x-http-host-override")
            for key in parsed
        ),
        c.Reason.HOST_REJECTED,
    )
    _require(_one(parsed, "host", c.Reason.HOST_REJECTED) == expected, c.Reason.HOST_REJECTED)
    canonical_path(target)


@dataclass(frozen=True, slots=True)
class SyntheticSession:
    """Comparison operands only; constructing these bytes authenticates nobody."""

    session: bytes
    csrf: bytes
    generation: str
    expires_at: int

    def __post_init__(self) -> None:
        for token in (self.session, self.csrf):
            _require(type(token) is bytes and re.fullmatch(rb"[0-9a-f]{64}", token) is not None)
        c.uuid4_text(self.generation)
        _require(type(self.expires_at) is int and 0 < self.expires_at <= 2**53 - 1)


def check_mutation(
    headers: Headers,
    target: str,
    expected_authority: str,
    state: SyntheticSession,
    *,
    generation: str,
    now: int,
) -> None:
    """POST syntactic context check only; cookie parsing/issuance is deferred."""
    check_authority(headers, target, expected_authority)
    _require(target == PREFIX + "/submissions")
    parsed = _headers(headers)
    _require(
        _one(parsed, "origin", c.Reason.ORIGIN_REJECTED) == "http://" + expected_authority,
        c.Reason.ORIGIN_REJECTED,
    )
    for key, expected in (
        ("sec-fetch-site", "same-origin"),
        ("sec-fetch-mode", "same-origin"),
        ("sec-fetch-dest", "empty"),
    ):
        _require(_one(parsed, key, c.Reason.ORIGIN_REJECTED) == expected, c.Reason.ORIGIN_REJECTED)
    _require("sec-fetch-user" not in parsed, c.Reason.ORIGIN_REJECTED)
    _require(_one(parsed, "content-type", c.Reason.INVALID_REQUEST) == "application/json")
    # A has no body-framing parser: all framing/encoding declarations are refused.
    _require(not any(k in parsed for k in ("transfer-encoding", "content-encoding")))
    _require(type(state) is SyntheticSession, c.Reason.CSRF_REJECTED)
    state.__post_init__()
    _require(type(now) is int and 0 <= now < state.expires_at, c.Reason.CSRF_REJECTED)
    _require(generation == state.generation, c.Reason.CSRF_REJECTED)
    for key, expected_token in (("x-f6-session", state.session), ("x-f6-csrf", state.csrf)):
        token = _one(parsed, key, c.Reason.CSRF_REJECTED)
        _require(re.fullmatch(r"[0-9a-f]{64}", token) is not None, c.Reason.CSRF_REJECTED)
        _require(hmac.compare_digest(token.encode("ascii"), expected_token), c.Reason.CSRF_REJECTED)


def _bounded_json(raw: bytes) -> None:
    _require(type(raw) is bytes)
    _require(len(raw) <= BODY_CEILING, c.Reason.BODY_TOO_LARGE)
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        raise c.ContractError() from None
    # One linear scan BEFORE the recursive stdlib/F6 decoder. Escapes cannot
    # conceal structural depth. Counting all string tokens/commas is conservative.
    depth = members = string_size = number_size = 0
    in_string = escaped = False
    for ch in text:
        if in_string:
            string_size += len(ch.encode("utf-8"))
            _require(string_size <= TEXT_CEILING)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string, string_size = True, 0
            members += 1
        elif ch in "[{":
            depth += 1
            members += 1
            _require(depth <= DEPTH_CEILING)
        elif ch in "]}":
            depth -= 1
            _require(depth >= 0)
        elif ch == ",":
            members += 1
        if not in_string and ch in "0123456789-+.eE":
            number_size += 1
            _require(number_size <= 32)
        else:
            number_size = 0
        _require(members <= MEMBER_CEILING)
    _require(depth == 0 and not in_string)


def parse_submission(raw: bytes, expected_revision: str) -> c.SubmissionRequest:
    """Closed syntactic selection, no readiness, intent, or session authority."""
    c.sha256_text(expected_revision)
    _bounded_json(raw)
    request = c.SubmissionRequest.parse(raw)
    _require(
        request.to_wire()["capability_revision"] == expected_revision, c.Reason.CAPABILITY_CHANGED
    )
    return request


def check_submission(
    method: str,
    headers: Headers,
    target: str,
    raw: bytes,
    expected_authority: str,
    expected_revision: str,
    state: SyntheticSession,
    *,
    generation: str,
    now: int,
) -> c.SubmissionRequest:
    """Composition with zero I/O. A passing predicate is NOT accepted execution."""
    _require(method == "POST")
    check_mutation(headers, target, expected_authority, state, generation=generation, now=now)
    parsed = _headers(headers)
    if "content-length" in parsed:
        length = _one(parsed, "content-length", c.Reason.INVALID_REQUEST)
        _require(re.fullmatch(r"0|[1-9][0-9]{0,6}", length) is not None)
        _require(type(raw) is bytes and int(length) == len(raw))
    return parse_submission(raw, expected_revision)
