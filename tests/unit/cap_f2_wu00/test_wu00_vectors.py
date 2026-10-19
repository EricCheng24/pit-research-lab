"""Acceptance-owned restricted reference verifier; this is not the runtime Agent serializer."""

import hashlib
import json
import re
from datetime import datetime

import pytest
from wu00_oracle import load_vectors, source_texts

CONTENT_KEYS = {"content_version_id", "publication_time", "subject_id", "value"}
AGENT_KEYS = {"decision_cutoff", "derived_q2_revenue", "entity_id", "observation_schema_version"}


def _reject(value):
    raise ValueError(f"invalid number: {value}")


def _int(text):
    number = int(text)
    if text == "-0" or not -(2**63) <= number < 2**63:
        raise ValueError("invalid int64")
    return number


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate object key")
        result[key] = value
    return result


def _allowed(value):
    if isinstance(value, dict):
        for key, member in value.items():
            if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", key):
                raise ValueError("invalid ASCII key")
            _allowed(member)
    elif isinstance(value, list):
        for member in value:
            _allowed(member)
    elif isinstance(value, str):
        if any(not 0x20 <= ord(c) <= 0x7E for c in value):
            raise ValueError("nonprintable/non-ASCII string")
    elif type(value) is int:
        if not -(2**63) <= value < 2**63:
            raise ValueError("int64 overflow")
    elif value is not None and type(value) is not bool:
        raise ValueError("invalid value type")


def _time(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+08:00", value
    ):
        raise ValueError("timestamp requires explicit synthetic offset")
    datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")


def canonical(payload, schema, timezone):
    """Schema-known arrays only: events ordered, member IDs set-valued after duplicate rejection."""
    if timezone != "Asia/Taipei":
        raise ValueError("missing/unknown named timezone")
    if isinstance(payload, bytes):
        if payload.startswith(b"\xef\xbb\xbf") or payload.endswith(b"\n"):
            raise ValueError("BOM/trailing newline")
        payload = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_object,
            parse_int=_int,
            parse_float=_reject,
            parse_constant=_reject,
        )
    _allowed(payload)
    if not isinstance(payload, dict):
        raise ValueError("schema requires object")
    if schema == "normalized-revenue-content-v1":
        if set(payload) != CONTENT_KEYS or type(payload["value"]) is not int:
            raise ValueError("content schema keys/value type")
        if any(
            not isinstance(payload[k], str) or not payload[k]
            for k in ["content_version_id", "subject_id"]
        ):
            raise ValueError("content identity type")
        _time(payload["publication_time"])
    elif schema == "agent-obs-v1":
        if set(payload) != AGENT_KEYS or payload["observation_schema_version"] != "agent-obs-v1":
            raise ValueError("agent schema keys/version")
        value = payload["derived_q2_revenue"]
        if (value is not None and type(value) is not int) or payload["entity_id"] not in [
            "SYN-A",
            "SYN-B",
        ]:
            raise ValueError("agent field type")
        _time(payload["decision_cutoff"])
    elif schema == "reference-sequence-v1":
        if set(payload) != {"events", "members"}:
            raise ValueError("sequence schema keys")
        if not isinstance(payload["events"], list) or not isinstance(payload["members"], list):
            raise ValueError("array type")
        for event in payload["events"]:
            if not isinstance(event, dict) or set(event) != {"event_id", "value"}:
                raise ValueError("event schema")
            if not isinstance(event["event_id"], str) or type(event["value"]) is not int:
                raise ValueError("event type")
        identities = [e["event_id"] for e in payload["events"]]
        members = payload["members"]
        if any(not isinstance(m, str) for m in members):
            raise ValueError("set member type")
        if len(set(identities)) != len(identities) or len(set(members)) != len(members):
            raise ValueError("duplicate array identity")
        payload = {"events": payload["events"], "members": sorted(members)}
    else:
        raise ValueError("unknown schema")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def test_five_exact_vectors_against_frozen_source():
    golden, _ = source_texts()
    vectors = load_vectors()
    assert [v["byte_length"] for v in vectors] == [118, 118, 136, 136, 137]
    for vector in vectors:
        data = bytes.fromhex(vector["payload_hex"])
        assert canonical(data, vector["schema_version"], "Asia/Taipei") == data
        assert hashlib.sha256(data).hexdigest() == vector["sha256"]
        if vector["vector_id"] == "invalid_content_v2":
            original = bytes.fromhex(vectors[0]["payload_hex"])
            assert data == original.replace(b'"value":300', b'"value":310')
            assert "invalid same-version-content mutation" in "\n".join(golden[129:137])
        else:
            assert data.decode() in "\n".join(golden)
        value = json.loads(data)
        reordered = dict(reversed(list(value.items())))
        assert canonical(reordered, vector["schema_version"], "Asia/Taipei") == data


def test_ordered_events_change_identity_but_sets_and_object_keys_do_not():
    example = {
        "events": [{"event_id": "E1", "value": 1}, {"event_id": "E2", "value": 2}],
        "members": ["B", "A"],
    }
    first = canonical(example, "reference-sequence-v1", "Asia/Taipei")
    example["members"].reverse()
    assert canonical(example, "reference-sequence-v1", "Asia/Taipei") == first
    example["events"].reverse()
    assert canonical(example, "reference-sequence-v1", "Asia/Taipei") != first
    example["members"].append("A")
    with pytest.raises(ValueError, match="duplicate"):
        canonical(example, "reference-sequence-v1", "Asia/Taipei")


@pytest.mark.parametrize(
    "payload",
    [
        b'{"value":1,"value":2}',
        b'{"value":-0}',
        b'{"value":1.0}',
        b'{"value":1e2}',
        b'{"value":9223372036854775808}',
        b"\xef\xbb\xbf{}",
        b"{}\n",
        b"{bad",
        b'{"Bad":1}',
        rb'{"value":"\u00e9"}',
    ],
)
def test_invalid_json_profile_is_not_repaired(payload):
    with pytest.raises((ValueError, UnicodeError)):
        canonical(payload, "normalized-revenue-content-v1", "Asia/Taipei")


def test_missing_keys_unknown_zone_and_bool_are_rejected():
    good = json.loads(bytes.fromhex(load_vectors()[0]["payload_hex"]))
    for timezone in [None, "UTC", "Unknown"]:
        with pytest.raises(ValueError, match="timezone"):
            canonical(good, "normalized-revenue-content-v1", timezone)
    for key in CONTENT_KEYS:
        with pytest.raises(ValueError):
            canonical(
                {k: v for k, v in good.items() if k != key},
                "normalized-revenue-content-v1",
                "Asia/Taipei",
            )
    with pytest.raises(ValueError):
        canonical({**good, "value": True}, "normalized-revenue-content-v1", "Asia/Taipei")
    with pytest.raises(ValueError):
        canonical(
            {**good, "publication_time": "2025-07-03T14:00:00"},
            "normalized-revenue-content-v1",
            "Asia/Taipei",
        )
