"""Synthetic text only: no procfs, PID lookup or process control."""

from dataclasses import replace

import pytest

from pit_research_lab.mvp.f6.backend import process_identity as p
from pit_research_lab.mvp.f6.backend.launch_policy import ModelError, Refusal


def identity():
    return p.SyntheticIdentity(
        "20000000-0000-4000-8000-000000000001",
        "20000000-0000-4000-8000-000000000002",
        "20000000-0000-4000-8000-000000000003",
        8123,
        "123456",
        8123,
        8123,
        "20000000-0000-4000-8000-000000000004",
        "a" * 64,
        "9",
        "17",
        "b" * 64,
    )


def stat_bytes():
    return b"8123 (synthetic name) S 8000 8123 8123 " + b"0 " * 15 + b"123456"


def test_supplied_stat_has_exact_fields_but_no_live_authority():
    parsed = p.parse_supplied_stat(stat_bytes())
    assert (
        parsed.pid,
        parsed.parent_pid,
        parsed.pgid,
        parsed.sid,
        parsed.start_ticks,
        parsed.state,
    ) == (8123, 8000, 8123, 8123, "123456", "S")
    assert p.compare_supplied(identity(), identity()) is p.Comparison.MODEL_MATCH
    assert identity().live_refusal() is Refusal.B_CORE_AUTHORITY_ABSENT


def test_truncated_ambiguous_and_pathological_supplied_text_refuses():
    for raw in (
        b"",
        stat_bytes()[:-10],
        stat_bytes() + b"\n",
        b"x" * 4097,
        stat_bytes().replace(b"synthetic name", b"a)b("),
        stat_bytes().replace(b"8123 (", b"1 ("),
        stat_bytes().replace(b"123456", b"01"),
        b"\xff",
    ):
        with pytest.raises(ModelError):
            p.parse_supplied_stat(raw)


def test_reused_pid_boot_generation_nonce_and_lease_all_fence():
    original = identity()
    changes = {
        "start_ticks": "123457",
        "boot_id": "20000000-0000-4000-8000-000000000005",
        "generation": "20000000-0000-4000-8000-000000000006",
        "pid": 8124,
        "pgid": 8124,
        "sid": 8124,
        "nonce_sha256": "c" * 64,
        "lease_dev": "10",
        "lease_ino": "18",
        "executable_sha256": "c" * 64,
        "installation_id": "20000000-0000-4000-8000-000000000007",
        "launcher_id": "20000000-0000-4000-8000-000000000008",
    }
    for field, value in changes.items():
        supplied = replace(original, **{field: value})
        assert p.compare_supplied(original, supplied) is p.Comparison.MODEL_MISMATCH
        assert supplied.live_refusal() is Refusal.B_CORE_AUTHORITY_ABSENT


def test_unknown_forged_or_invalid_supplied_values_refuse():
    original = identity()
    for field, value in (
        ("pid", True),
        ("pid", 0),
        ("start_ticks", "0"),
        ("lease_ino", "-1"),
        ("boot_id", "unknown"),
        ("nonce_sha256", "A" * 64),
        ("generation", original.installation_id),
    ):
        with pytest.raises(ModelError):
            replace(original, **{field: value})
    with pytest.raises(ModelError):
        p.compare_supplied(original, None)
