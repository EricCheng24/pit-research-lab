"""Adversarial synthetic controls at the private historical archive boundary."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import stat
import struct
import warnings
import zipfile
from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from pit_research_lab.mvp.f6.historical_f5 import archive as a
from pit_research_lab.mvp.f6.historical_f5 import contract as c

ZIP_LABEL = "SYNTHETIC-BOUNDARY-CONTROL"
LEFT, RIGHT = "f5-run-a/", "f5-run-b/"
STAMP = "2026-05-10T03:00:00.123456+00:00"
A = "bf855e75-11fa-4d0a-a2f9-7ada6d45e027"
B = "aa855e75-11fa-4d0a-b2f9-7ada6d45e027"
REF = "a" * 64
ROOT = "/synthetic-only/producer"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def wire(source: object) -> bytes:
    return json.dumps(source, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def files() -> list[tuple[str, bytes]]:
    peers = [
        (root + stem + ".json", (ZIP_LABEL + stem).encode())
        for root in (LEFT, RIGHT)
        for stem in ("spec", "decisions", "ledger", "metrics", "evidence", "attempt")
    ]
    return peers + [(f"notes/n{n:03d}.txt", f"{ZIP_LABEL} {n}".encode()) for n in range(187)]


def make_archive(
    rows: list[tuple[str, bytes]], *, manifest: bytes | None = None, aliases: tuple[str, ...] = ()
) -> tuple[bytes, a.Release]:
    if manifest is None:
        manifest = "".join(f"{digest(body)}  {name}\n" for name, body in rows).encode()
    out = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
            for name, data in [*rows, ("handoff/SHA256SUMS", manifest)]:
                info = zipfile.ZipInfo(name)
                mode = stat.S_IFLNK if name in aliases else stat.S_IFREG
                info.external_attr = (mode | 0o600) << 16
                zipped.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
    raw = out.getvalue()
    return raw, replace(
        a._RELEASE,
        size=len(raw),
        archive_sha256=digest(raw),
        manifest_sha256=digest(manifest),
        acceptance_ref=ZIP_LABEL,
    )


def test_H01_external_pin_precedes_any_zip_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    raw, synthetic = make_archive(files())
    seen = Mock(side_effect=AssertionError("raw pin must short-circuit"))
    monkeypatch.setattr(a, "_zip_layout", seen)
    with pytest.raises(c.Refusal, match="^ARCHIVE_PIN$"), a._packet(raw, a._RELEASE, a.Budget()):
        pytest.fail("historical authority was inferred from a synthetic packet")
    with (
        pytest.raises(c.Refusal, match="^ARCHIVE_PIN$"),
        a._packet(raw[:-1] + b"z", synthetic, a.Budget()),
    ):
        pytest.fail("changed bytes passed the fixed raw pin")
    seen.assert_not_called()


def test_H01_exact_inventory_crc_sha_and_identical_members() -> None:
    rows = files()
    raw, synthetic = make_archive(rows)
    with a._packet(raw, synthetic, a.Budget()) as packet:
        assert set(packet.pins) == {n for n, _ in rows}
        assert len(packet.pins) == 199
        for name, data in rows:
            assert packet.pins[name] == a.Pin(len(data), digest(data))
        packet.exact_match(LEFT + "ledger.json", RIGHT + "ledger.json")
    with pytest.raises(c.Refusal, match="PROVENANCE_MISMATCH"):
        a._gate(synthetic, c.EDITION)


@pytest.mark.parametrize(
    "name",
    [
        "../bad",
        "/absolute",
        "a/b/c",
        r"a\b",
        "a/./b",
        "NUL.txt",
        "a.",
        "notes/N004.TXT",
        "notes/n004.txt",
        "a" * 97,
    ],
)
def test_H06_unsafe_zip_leaf_or_alias(name: str) -> None:
    original = files()
    raw, release = make_archive([*original[:-1], (name, b"non-evidence")])
    with pytest.raises(c.Refusal, match="^ARCHIVE_STRUCTURE$"), a._packet(raw, release, a.Budget()):
        pytest.fail("unsafe ZIP profile was accepted")


def test_H06_symlink_crc_and_deflate_expansion_controls() -> None:
    rows = files()
    raw, release = make_archive(rows, aliases=(rows[-1][0],))
    with pytest.raises(c.Refusal, match="ARCHIVE_STRUCTURE"), a._packet(raw, release, a.Budget()):
        pytest.fail("symlink entry accepted")
    raw, release = make_archive([*rows[:-1], (rows[-1][0], b"z" * 50_000)])
    with pytest.raises(c.Refusal, match="BOUNDS_EXCEEDED"), a._packet(raw, release, a.Budget()):
        pytest.fail("inflation ratio accepted")
    raw, release = make_archive(rows)
    mutable = bytearray(raw)
    crc = struct.unpack_from("<I", raw, 14)[0]
    # Same incorrect CRC in the first local and central headers.
    start_dir = struct.unpack_from("<I", raw, len(raw) - 6)[0]
    struct.pack_into("<I", mutable, 14, crc ^ 1)
    struct.pack_into("<I", mutable, start_dir + 16, crc ^ 1)
    damaged = bytes(mutable)
    with (
        pytest.raises(c.Refusal, match="MEMBER_MISMATCH"),
        a._packet(damaged, replace(release, archive_sha256=digest(damaged)), a.Budget()),
    ):
        pytest.fail("incorrect CRC accepted")


def test_H06_actual_inflate_size_refuses_beyond_header() -> None:
    raw, release = make_archive(files())
    mutable = bytearray(raw)
    size = struct.unpack_from("<I", raw, 22)[0]
    assert size > 1
    start_dir = struct.unpack_from("<I", raw, len(raw) - 6)[0]
    struct.pack_into("<I", mutable, 22, size - 1)
    struct.pack_into("<I", mutable, start_dir + 24, size - 1)
    false_length = bytes(mutable)
    with (
        pytest.raises(c.Refusal, match="MEMBER_MISMATCH"),
        a._packet(false_length, replace(release, archive_sha256=digest(false_length)), a.Budget()),
    ):
        pytest.fail("quiet truncation")


def test_H05_missing_peer_and_rehashed_member_at_deep_gate() -> None:
    rows = files()
    gone = [row if row[0] != RIGHT + "attempt.json" else ("unexpected", row[1]) for row in rows]
    raw, release = make_archive(gone)
    with pytest.raises(c.Refusal, match="PEER_MISSING"), a._packet(raw, release, a.Budget()):
        pytest.fail("absent peer read as successful")
    damaged = [
        (name, data + b"changed" if name == RIGHT + "spec.json" else data) for name, data in rows
    ]
    raw, release = make_archive(damaged)
    with a._packet(raw, release, a.Budget()) as packet:
        with pytest.raises(c.Refusal, match="MEMBER_MISMATCH"):
            packet.exact_match(LEFT + "spec.json", RIGHT + "spec.json")


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        (b'{"a":1,"a":2}', "MALFORMED_JSON"),
        (b'{"a":{"t":1,"t":2}}', "MALFORMED_JSON"),
        (b'{"a":NaN}', "MALFORMED_JSON"),
        (b'{"a":123e2}', "MALFORMED_JSON"),
        (b'{"a":1.23}', "MALFORMED_JSON"),
        (b'{"a":"\xff"}', "MALFORMED_JSON"),
        (b'{"x":' + (b"[" * 16) + b"0" + (b"]" * 16) + b"}", "BOUNDS_EXCEEDED"),
        (b'{"x":' + b"2" * 25 + b"}", "BOUNDS_EXCEEDED"),
        (b'{"x":[' + b"0," * 300_000 + b"0]}", "BOUNDS_EXCEEDED"),
    ],
    ids=[
        "duplicate",
        "nested-duplicate",
        "nan",
        "exponent",
        "float",
        "utf8",
        "depth",
        "integer",
        "tokens",
    ],
)
def test_H06_bounded_json_parser(raw: bytes, reason: str) -> None:
    with pytest.raises(c.Refusal, match=f"^{reason}$"):
        a._decode(raw, a.Budget())


def test_H06_document_and_private_decimal_boundaries() -> None:
    assert a._decode(b'{"x":' + b"7" * 24 + b"}", a.Budget()) == {"x": int("7" * 24)}
    allowed = b'{"launch":{"invocation":{"wall_seconds":1.2345}}}'
    parsed = a._decode(allowed, a.Budget(), producer_post=True)
    assert str(parsed["launch"]["invocation"]["wall_seconds"]) == "1.2345"
    for path in (b'{"wall_seconds":1.2345}', b'{"launch":{"invocation":{"wall_seconds":-1.2345}}}'):
        with pytest.raises(c.Refusal, match="MALFORMED_JSON"):
            a._decode(path, a.Budget(), producer_post=True)
    expired = a.Budget()
    expired.until = -1
    with pytest.raises(c.Refusal, match="BOUNDS_EXCEEDED"):
        a._decode(b"{}", expired)


def attempts() -> tuple[dict[str, Any], dict[str, Any]]:
    body = {
        "started_at": STAMP,
        "finished_at": "2026-05-10T04:00:00.000000+00:00",
        "elapsed_seconds": "55.3",
        "execution_status": "SUCCEEDED",
        "comparison_status": "COMPLETE_COMPARABLE_SYNTHETIC",
        "replay_status": "VERIFIED",
        "completed_stages": [
            "F3_ORIGIN_AND_SOURCE_SEMANTICS_VERIFIED",
            "TYPED_SLOT_CENSUS_SEALED",
            "PORTFOLIOS_EVALUATED",
            "DETERMINISTIC_EVIDENCE_WRITTEN",
        ],
        "first_failure": None,
        "evidence_sha256": REF,
        "peer_evidence_sha256": REF,
        "producer_root": ROOT,
        "origin_handoff_status": "ORIGIN_ARTIFACT_AND_SEMANTICS_VERIFIED",
    }
    return (
        body | {"attempt_id": A, "process_id": 41, "peer_attempt_id": B, "peer_process_id": 43},
        body | {"attempt_id": B, "process_id": 43, "peer_attempt_id": A, "peer_process_id": 41},
    )


def pending(value: dict[str, Any]) -> dict[str, Any]:
    return value | {
        "execution_status": "EVALUATED_REPLAY_PENDING",
        "comparison_status": "INCOMPLETE_OR_BLOCKED",
        "replay_status": "NOT_RUN",
        "peer_attempt_id": None,
        "peer_evidence_sha256": None,
        "peer_process_id": None,
    }


@pytest.mark.parametrize(
    ("field", "new"),
    [
        ("attempt_id", A),
        ("process_id", 41),
        ("peer_attempt_id", B),
        ("peer_process_id", 31),
        ("peer_evidence_sha256", "b" * 64),
        ("producer_root", "/synthetic-only/incorrect"),
        ("evidence_sha256", "b" * 64),
        ("origin_handoff_status", "NOT_VERIFIED"),
        ("started_at", "not-rfc3339"),
    ],
)
def test_H05_reciprocal_attempt_identity_refusal(field: str, new: object) -> None:
    left, right = attempts()
    assert a._check_pair((left, right), ROOT, REF) == "COMPLETE_COMPARABLE_SYNTHETIC"
    right[field] = new
    with pytest.raises(c.Refusal, match="RECEIPT_MISMATCH"):
        a._check_pair((left, right), ROOT, REF)


@pytest.mark.parametrize("terminal", ["EVALUATED_REPLAY_PENDING", "FAILED", "BLOCKED_INPUT"])
def test_H05_mixed_or_failed_pair_never_completes(terminal: str) -> None:
    left, right = attempts()
    changed = pending(right) | {"execution_status": terminal}
    outcome = "PAIR_INCOMPLETE" if terminal == "EVALUATED_REPLAY_PENDING" else "PAIR_FAILED"
    with pytest.raises(c.Refusal, match=f"^{outcome}$"):
        a._check_pair((left, changed), ROOT, REF)


def test_H05_pair_post_checks_recorded_root_and_attempt_order() -> None:
    left, right = pair = attempts()
    old = [pending(left), pending(right)]
    view = []
    pre = []
    packet = Mock(spec=a.Packet)
    packet.pins = {}
    for index, prefix in enumerate((LEFT, RIGHT)):
        witness_root = "/synthetic-only/" + prefix[:-1]
        rows = {}
        for leaf in ("spec", "decisions", "ledger", "metrics", "evidence", "attempt"):
            content = f"simulated {prefix}/{leaf}".encode()
            rows[leaf + ".json"] = {"bytes": len(content), "sha256": digest(content)}
            packet.pins[prefix + leaf + ".json"] = a.Pin(len(content), digest(content))
        view.append({"root": witness_root, "root_identity": [1, 50 + index, 3], "files": rows})
        pending_wire = wire(
            {"schema": "F5_WEEKLY_SYNTHETIC_ATTEMPT_V1", "non_if03": True, "payload": old[index]}
        )
        pre.append(
            view[-1]
            | {
                "files": rows
                | {"attempt.json": {"bytes": len(pending_wire), "sha256": digest(pending_wire)}}
            }
        )
    candidate = {
        "completed_attempts": list(pair),
        "effective_class": "COMPLETE_COMPARABLE_SYNTHETIC",
        "finished_utc": STAMP,
        "idempotence": "PASS",
        "pending_attempts": old,
        "pid": 88,
        "post": view,
        "pre": pre,
        "single_root": "NOT_COMPUTABLE",
    }
    reference = replace(a._RELEASE, pair_post_sha256=digest(wire(candidate)))
    packet.pins["witness/pair-post.json"] = a.Pin(len(wire(candidate)), reference.pair_post_sha256)
    packet.json.return_value = candidate
    a._pair_record(packet, reference, pair, "COMPLETE_COMPARABLE_SYNTHETIC")
    for key in ("completed_attempts", "post", "pre"):
        twisted = copy.deepcopy(candidate)
        twisted[key].reverse()
        packet.json.return_value = twisted
        with pytest.raises(c.Refusal, match="RECEIPT_MISMATCH"):
            a._pair_record(packet, reference, pair, "COMPLETE_COMPARABLE_SYNTHETIC")


def test_H05_degraded_effective_is_not_publishable() -> None:
    left, right = attempts()
    reports = [row | {"comparison_status": "DEGRADED_DIAGNOSTIC_ONLY"} for row in (left, right)]
    kind = a._check_pair((reports[0], reports[1]), ROOT, REF)
    assert kind == "DEGRADED_DIAGNOSTIC_ONLY"
    packet = Mock(spec=a.Packet)
    packet.pins = {root + "evidence.json": a.Pin(1, REF) for root in (LEFT, RIGHT)}
    artifacts = []
    for stem in ("spec", "decisions", "ledger", "metrics"):
        fingerprint = digest(stem.encode())
        artifacts.append({"file": stem + ".json", "sha256": fingerprint, "byte_length": 1})
        for root in (LEFT, RIGHT):
            packet.pins[root + stem + ".json"] = a.Pin(1, fingerprint)
    for leaf in ("witness/effective-post-a-b.json", "witness/effective-post-b-a.json"):
        packet.pins[leaf] = a.Pin(1, "b" * 64)
    display = {"books": {}, "coverage": {}, "comparison_status": kind}
    packet.json.return_value = display
    packet.payload.side_effect = lambda prefix, key, fields: (
        {
            "artifacts": artifacts,
            "candidate_class": kind,
            "scope": "AUTHORED_SYNTHETIC_ONLY",
            "test_execution_attestation": "NOT_ATTESTED_BY_RUNTIME",
        }
        if key == "evidence"
        else {
            "books": {},
            "coverage": {},
            "candidate_class": kind,
            "common_failure": None,
            "limitations": [],
        }
    )
    with pytest.raises(c.Refusal, match="^PAIR_DEGRADED$"):
        a._effective(packet, replace(a._RELEASE, f5_sha256=REF, effective_sha256="b" * 64), kind)


def test_H05_H06_edition_authority_and_provenance_are_closed() -> None:
    for release, edition, reason in (
        (a._RELEASE, "other", "UNKNOWN_EDITION"),
        (None, c.EDITION, "EDITION_WITHHELD"),
        (replace(a._RELEASE, acceptance_ref="STALE"), c.EDITION, "PROVENANCE_MISMATCH"),
        (replace(a._RELEASE, receipt_id="b" * 64), c.EDITION, "PROVENANCE_MISMATCH"),
    ):
        with pytest.raises(c.Refusal, match=reason):
            a._gate(release, edition)
    base = {
        "base_head": "e" * 40,
        "code_claim": "ACTUAL_UNCOMMITTED_WORKTREE_BYTES_NOT_HEAD_CONTENT",
        "files": [{"byte_length": 9, "sha256": REF, "path": "src/example.py"}],
        "runtime": {"implementation": "CPython", "python": "3.12.13"},
    }
    assert a._provenance(base, "base_head", "e" * 40, 1)[1] == [["src/example.py", REF, 9]]
    for alternation in (
        {"base_head": "a" * 40},
        {"runtime": {"implementation": "CPython", "python": "3.11.1"}},
        {"files": [{"byte_length": 9, "sha256": REF, "path": "../file.py"}]},
    ):
        with pytest.raises(c.Refusal, match="PROVENANCE_MISMATCH"):
            a._provenance(base | alternation, "base_head", "e" * 40, 1)


def test_H05_cutoff_common_information_and_canonical_slot_identity() -> None:
    info = "c" * 64
    policy = "QUALIFIED_EW_CAP50_V1"
    cutoff = "2025-03-05T18:00:00+08:00"
    aliases = [f"SYN-L1-{n}" for n in range(1, 6)]
    fraction = {"numerator": "1", "denominator": "5"}
    action = {
        "cash_weight": {"numerator": "0", "denominator": "1"},
        "cutoff": cutoff,
        "disposition": "ALLOCATE",
        "information_digest": info,
        "issuer_reasons": [[name, "QUALIFIED_UNIVERSE_MEMBER"] for name in aliases],
        "policy_id": policy,
        "policy_version": "F5_WEEKLY_SYNTHETIC_V1",
        "reason": "NONE",
        "schema": "F5_TARGET_ACTION_V1",
        "tick": 48,
        "weights": [[name, fraction] for name in aliases],
    }
    slot = {
        "attempted": True,
        "cutoff": cutoff,
        "engine_disposition": None,
        "failure_cause": None,
        "information_digest": info,
        "outcome": "VALID",
        "policy_action": action,
        "policy_decision_digest": digest(wire(action)),
        "policy_id": policy,
        "schema": "F5_DECISION_SLOT_V1",
        "tick": 48,
    }
    assert (
        a._slot(
            slot | {"slot_digest": digest(wire(slot))},
            policy,
            48,
            {"cutoff": cutoff, "information_digest": info},
        )["policy_action"]
        == action
    )
    wrong = slot | {"information_digest": "1" * 64}
    with pytest.raises(c.Refusal, match="PROVENANCE_MISMATCH"):
        a._slot(
            wrong | {"slot_digest": digest(wire(wrong))},
            policy,
            48,
            {"cutoff": cutoff, "information_digest": info},
        )


def test_H05_protocol_drift_cannot_hide_behind_a_new_digest() -> None:
    protocol = {
        "exclusion_policy": "TYPED_UNAVAILABLE_NO_IMPUTATION_NO_OLDER_PAIR_FALLBACK",
        "feature": "LATEST_AVAILABLE_MONTH_OVER_IMMEDIATE_PREDECESSOR_MINUS_ONE",
        "folds": [
            {"name": "F1", "history_end": 48, "test_start": 48, "test_end": 72},
            {"name": "F2", "history_end": 72, "test_start": 72, "test_end": 96},
        ],
        "h0": "beta = 0",
        "h1": "beta != 0",
        "horizon_sessions": 20,
        "limitations": [f"SYNTHETIC_CONTROL_{k}" for k in range(8)],
        "method": "OLS_INTERCEPT_ONE_REGRESSOR_V1",
        "min_issuers": 3,
        "min_test_cutoffs": 20,
        "min_test_rows": 80,
        "min_train_cutoffs": 40,
        "min_train_rows": 180,
        "non_if03": True,
        "numeric_policy": "FRACTION_REDUCED_4096_DECIMAL50_FIXED12_HALF_EVEN_V1",
        "question": "Does PIT monthly revenue growth predict subsequent synthetic returns?",
        "schema": "F3_L1_RESEARCH_V0.1",
        "seed": 17,
        "temporal_policy": {
            "feature": "public_delivery < decision",
            "fit": "17:00_FIRST_TEST_SESSION",
            "prediction": "18:00_LAST_SESSION_OF_WEEK",
            "purge": "outcome_end < first_test_start_mark",
            "score": "sealed_prediction_then_mature_outcome",
            "target": "20_SUBSEQUENT_SESSION_CLOSES",
            "training_label": "available_at <= fit",
            "validation": "NOT_APPLICABLE_NO_TUNING",
        },
    }
    a._bound_protocol(
        {"protocol": protocol, "protocol_ref": digest(wire(protocol)), "dataset_digest": REF}
    )
    changed = protocol | {"horizon_sessions": 21}
    with pytest.raises(c.Refusal, match="^PROVENANCE_MISMATCH$"):
        a._bound_protocol(
            {"protocol": changed, "protocol_ref": digest(wire(changed)), "dataset_digest": REF}
        )


def test_H06_string_lexeme_bound_counts_quotes() -> None:
    good = b'{"x":"' + b"a" * 8190 + b'"}'
    assert len(a._decode(good, a.Budget())["x"]) == 8190
    with pytest.raises(c.Refusal, match="^BOUNDS_EXCEEDED$"):
        a._decode(b'{"x":"' + b"a" * 8191 + b'"}', a.Budget())
