"""Pure synthetic comparisons, not authentication or HTTP parser acceptance."""

from dataclasses import replace

import pytest

from pit_research_lab.mvp.f6 import contracts as c
from pit_research_lab.mvp.f6.backend import security as s

UUID = "00000000-0000-4000-8000-000000000001"
AUTHORITY = "127.0.0.1:12345"
REVISION = "a" * 64
TARGET = s.PREFIX + "/submissions"


def body(**changes):
    return c.canonical_json(
        dict(
            schema_version=c.VERSION,
            kind="SUBMISSION_REQUEST",
            capability_id=c.CAPABILITY_ID,
            capability_revision=REVISION,
            data_mode="SYNTHETIC_GOLDEN",
            idempotency_key=UUID,
        )
        | changes
    )


def session():
    return s.SyntheticSession(b"1" * 64, b"2" * 64, UUID, 100)


def headers():
    return (
        ("Host", AUTHORITY),
        ("Origin", "http://" + AUTHORITY),
        ("Sec-Fetch-Site", "same-origin"),
        ("Sec-Fetch-Mode", "same-origin"),
        ("Sec-Fetch-Dest", "empty"),
        ("Content-Type", "application/json"),
        ("X-F6-Session", "1" * 64),
        ("X-F6-Csrf", "2" * 64),
    )


def changed_headers(name, value):
    retained = tuple((k, v) for k, v in headers() if k.lower() != name.lower())
    return retained if value is None else (*retained, (name, value))


def check(h=None, raw=None, target=TARGET, method="POST", state=None, generation=UUID, now=1):
    return s.check_submission(
        method,
        headers() if h is None else h,
        target,
        body() if raw is None else raw,
        AUTHORITY,
        REVISION,
        session() if state is None else state,
        generation=generation,
        now=now,
    )


def test_synthetic_comparison_only_and_detached_request():
    request = check(h=(*headers(), ("Content-Length", str(len(body())))))
    wire = request.to_wire()
    wire["capability_revision"] = "b" * 64
    assert request.to_wire()["capability_revision"] == REVISION
    assert not hasattr(s, "authenticate") and not hasattr(s, "serve")
    assert s.canonical_path(s.PREFIX + "/runs/" + UUID + "/result")


@pytest.mark.parametrize(
    "value",
    [
        None,
        "127.0.0.1",
        "127.0.0.1:12346",
        "localhost:12345",
        "[::1]:12345",
        "127.0.0.1:012345",
        "127.0.0.1:12345.evil",
        "evil@127.0.0.1:12345",
        "127.0.0.1:12345,127.0.0.1:12345",
        "127.0.0.1:12345 ",
        "127.0.0.1:12345\r\nX-Evil: secret",
    ],
)
def test_host_refusals(value):
    with pytest.raises(c.ContractError):
        check(h=changed_headers("host", value))


@pytest.mark.parametrize(
    "name,value",
    [
        ("hOsT", AUTHORITY),
        ("Forwarded", "host=secret"),
        ("X-Forwarded-Host", AUTHORITY),
        ("X-Forwarded-Port", "12345"),
        ("X-Original-URL", TARGET),
        ("X-Host", AUTHORITY),
        ("Via", "secret"),
        ("X-Rewrite-URL", TARGET),
    ],
)
def test_duplicate_or_proxy_override_refuses(name, value):
    with pytest.raises(c.ContractError):
        check(h=(*headers(), (name, value)))


@pytest.mark.parametrize(
    "expected", ["localhost:1", "127.0.0.1:0", "127.0.0.1:65536", "//127.0.0.1:1"]
)
def test_invalid_expected_authority_refuses(expected):
    with pytest.raises(c.ContractError, match="^HOST_REJECTED$"):
        s.check_authority(headers(), TARGET, expected)


@pytest.mark.parametrize(
    "name,value",
    [
        ("Origin", None),
        ("Origin", "null"),
        ("Origin", "http://foreign.invalid"),
        ("Origin", "http://" + AUTHORITY + "/"),
        ("Origin", "https://" + AUTHORITY),
        ("Sec-Fetch-Site", None),
        ("Sec-Fetch-Site", "cross-site"),
        ("Sec-Fetch-Site", "same-site"),
        ("Sec-Fetch-Site", "none"),
        ("Sec-Fetch-Mode", "cors"),
        ("Sec-Fetch-Mode", "navigate"),
        ("Sec-Fetch-Dest", "document"),
        ("Sec-Fetch-User", "?1"),
        ("Content-Type", "text/plain"),
        ("Content-Type", "application/json;charset=utf-8"),
        ("X-F6-Session", None),
        ("X-F6-Session", "3" * 64),
        ("X-F6-Csrf", None),
        ("X-F6-Csrf", "3" * 64),
        ("X-F6-Csrf", "secret"),
        ("Content-Length", "0001"),
        ("Content-Length", "999"),
        ("Transfer-Encoding", "chunked"),
        ("Content-Encoding", "gzip"),
    ],
)
def test_origin_fetch_session_csrf_content_type_and_framing_refusals(name, value):
    with pytest.raises(c.ContractError):
        check(h=changed_headers(name, value))


@pytest.mark.parametrize(
    "name", ["Origin", "Sec-Fetch-Site", "X-F6-Session", "X-F6-Csrf", "Content-Type"]
)
def test_ambiguous_context_refuses_even_identical_duplicates(name):
    value = dict(headers())[name]
    with pytest.raises(c.ContractError):
        check(h=(*headers(), (name, value)))


def test_stale_and_malformed_session_refusals_and_constant_time_comparison(monkeypatch):
    with pytest.raises(c.ContractError, match="^CSRF_REJECTED$"):
        check(now=100)
    with pytest.raises(c.ContractError, match="^CSRF_REJECTED$"):
        check(generation="00000000-0000-4000-8000-000000000002")
    with pytest.raises(c.ContractError):
        replace(session(), session=bytearray(b"1" * 64))
    calls = []
    original = s.hmac.compare_digest

    def compare(left, right):
        calls.append((type(left), type(right)))
        return original(left, right)

    monkeypatch.setattr(s.hmac, "compare_digest", compare)
    check()
    assert calls == [(bytes, bytes), (bytes, bytes)]


@pytest.mark.parametrize(
    "path",
    [
        TARGET + "/",
        TARGET + "?x=1",
        TARGET + "#secret",
        "http://" + AUTHORITY + TARGET,
        "http://foreign.invalid" + TARGET,
        "//" + AUTHORITY + TARGET,
        "/etc/passwd",
        s.PREFIX + "//submissions",
        s.PREFIX + "/../submissions",
        s.PREFIX + "\\submissions",
        s.PREFIX + "/%2E%2E/submissions",
        s.PREFIX + "/%2Fsubmissions",
        s.PREFIX + "/%252E/submissions",
        s.PREFIX + "/runs/" + UUID.upper(),
        s.PREFIX + "/runs/00000000000040008000000000000001",
        s.PREFIX + "/runs/" + UUID + "/file",
    ],
)
def test_unsafe_or_noncanonical_path_refuses(path):
    # UUID uses digits: uppercase alone is unchanged, use a hex letter explicitly.
    if path == s.PREFIX + "/runs/" + UUID:
        path = s.PREFIX + "/runs/AAAAAAAA-0000-4000-8000-000000000001"
    with pytest.raises(c.ContractError):
        s.canonical_path(path)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":-Infinity}',
        b'{"x":1.0}',
        b'{"x":1e0}',
        b'{"x":' + b"1" * 4096 + b"}",
        b"\xff",
        b'{"x":"\\ud800"}',
        b"[" * 33 + b"0" + b"]" * 33,
        b'{"x":"' + b"a" * (s.TEXT_CEILING + 1) + b'"}',
        b"[" + b"0," * 1001 + b"0]",
        b" " * (s.BODY_CEILING + 1),
        body(kind="UNKNOWN"),
        body(schema_version="UNKNOWN"),
        body(extra="secret"),
        body(data_mode="ACTUAL"),
        body(capability_revision="b" * 64),
        body(idempotency_key="secret"),
    ],
)
def test_strict_bounded_json_refuses(raw):
    with pytest.raises(c.ContractError):
        check(raw=raw)


def test_oversized_depth_and_tokens_refuse_before_recursive_schema_decoder(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("bounded guard must precede schema decoding")

    monkeypatch.setattr(c.SubmissionRequest, "parse", unexpected)
    for raw in (b" " * (s.BODY_CEILING + 1), b"[" * 33, b"1" * 40):
        with pytest.raises(c.ContractError):
            s.parse_submission(raw, REVISION)


def test_refusals_are_safe_deterministic_and_cannot_consume_a_key():
    writes = []

    def synthetic_caller(h, raw):
        request = check(h=h, raw=raw)
        writes.append(request.serialize())  # Pure recording spy, never a catalog.

    for h, raw in (
        (changed_headers("Origin", "secret"), body()),
        (headers(), body(extra="/private/secret")),
        ((*headers(), ("X-F6-Csrf", "secret")), body()),
    ):
        messages = []
        for _ in range(2):
            with pytest.raises(c.ContractError) as caught:
                synthetic_caller(h, raw)
            messages.append(str(caught.value))
            assert str(caught.value) == caught.value.code.value
            assert "secret" not in str(caught.value)
        assert messages[0] == messages[1]
    assert writes == []


@pytest.mark.parametrize("method", ["GET", "PUT", "post", "DELETE"])
def test_non_submission_methods_refuse(method):
    with pytest.raises(c.ContractError):
        check(method=method)
