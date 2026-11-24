"""Unit accounting/barrier controls and fresh-process REFUSAL, not genuine F3 replay."""

import json
import os
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction as Q

import pytest

from pit_research_lab.mvp.f2 import research_panel as f2
from pit_research_lab.mvp.f5 import experiment as e
from pit_research_lab.mvp.f5 import prices, replay
from pit_research_lab.mvp.f5.contracts import (
    CALENDAR_SHA,
    COMPLETE,
    DEGRADED,
    INCOMPLETE,
    ISSUERS,
    POLICIES,
    DecisionFact,
    DecisionForecast,
    DecisionObservation,
    F5Error,
    IssuerInput,
    Protocol,
    digest,
    verify_barrier,
)
from pit_research_lab.mvp.f5.policies import choose


@pytest.fixture(scope="module")
def unit_inputs():
    """Manual five-name DTO seam, NOT F2-qualified/genuine F3 producer evidence."""
    body = prices.pinned_body()
    observations = []
    for tick in range(48, 96):
        cells = []
        for name in ISSUERS:
            fact = DecisionFact(
                "2025-01",
                "KNOWN",
                110,
                "NTD_thousands",
                "consolidated-v1",
                name,
                name + "-VERSION",
                "2025-02-10T12:00:00+08:00",
                "2025-02-10T12:01:00+08:00",
                "SELECTED",
                "NONE",
                "1" * 64,
            )
            prev = replace(fact, month="2024-12", amount=100)
            row = DecisionForecast(
                f"{name}:t{tick:02}",
                name,
                tick,
                body["cutoffs"][tick],
                "3" * 64,
                CALENDAR_SHA,
                "4" * 64,
                "F1" if tick < 72 else "F2",
                "2025-02-14T17:00:00+08:00" if tick < 72 else "2025-08-01T17:00:00+08:00",
                "5" * 64,
                "6" * 64,
                "OLS_INTERCEPT_ONE_REGRESSOR_V1",
                20,
                "PREDICTED",
                Q(3, 100),
                "NONE",
            )
            cells.append(
                IssuerInput(
                    name,
                    row.sample_id,
                    "4" * 64,
                    fact,
                    prev,
                    Q(1, 10),
                    "KNOWN",
                    "NONE",
                    row,
                    True,
                    "NONE",
                )
            )
        observations.append(
            DecisionObservation(tick, body["cutoffs"][tick], CALENDAR_SHA, "3" * 64, tuple(cells))
        )
    calendar = tuple((x["date"], x["close"]) for x in body["calendar"] if x["status"] == "SESSION")
    return tuple(observations), tuple(body["cutoffs"]), calendar


class UnitPriceClaims:
    """Instrumented kernel claims only; real qualification tested in test_prices."""

    constructions = 0
    reads = 0
    fail_day = None

    def __init__(self, barrier):
        verify_barrier(barrier)
        type(self).constructions += 1

    def read_mark(self, issuer, session, asof):
        type(self).reads += 1
        if session == self.fail_day:
            raise F5Error("UNIT_MISSING_MARK")
        return prices.QualifiedMark(
            issuer,
            session,
            asof.replace(":01+", ":00+"),
            asof,
            100000,
            "NTD_price_ticks_1e4",
            "unadjusted-synthetic-v1",
            issuer + "-CLOSE-" + session,
            issuer + "-CLOSE-" + session + "-VERSION",
            "7" * 64,
            "BOUND",
            "SUPPORTED",
            "NONE",
            asof,
            witness_time=asof,
        )


def test_144_valid_and_one_failed_separate_engine_fallback_barrier(unit_inputs):
    observations, cutoffs, calendar = unit_inputs
    trace, copies = [], []

    def policy(obs, p):
        assert UnitPriceClaims.constructions == 0
        trace.append((obs.tick, p, obs.information_digest, obs.availability_mask))
        copies.append(obs)
        return choose(obs, p)

    UnitPriceClaims.constructions = UnitPriceClaims.reads = 0
    sealed = e.prepare(observations, cutoffs, policy)
    assert e.census(sealed)["valid"] == 144 and len(trace) == 144
    for offset in range(0, 144, 3):
        assert trace[offset][2:] == trace[offset + 1][2:] == trace[offset + 2][2:]
        assert copies[offset] is not copies[offset + 1] and copies[offset] == copies[offset + 1]
    assert [t for t, _, _, _ in trace] == [t for t in range(48, 96) for _ in POLICIES]
    result = e.evaluate(sealed, calendar, cutoffs, UnitPriceClaims)
    assert (
        result["candidate_class"] == COMPLETE
    )  # CANDIDATE from a unit seam, not effective report.
    assert result["coverage"]["qualified_common_mark_cells"] == 1205
    assert all(
        b["weekly_returns_evaluated"] == b["processed_opportunities"] == 48
        for b in result["books"].values()
    )
    assert len([x for x in result["events"] if x["tick"] == 95]) == 6
    assert all(
        x["reference_time"].startswith("2026-01-12") for x in result["events"] if x["tick"] == 95
    )
    UnitPriceClaims.constructions = UnitPriceClaims.reads = 0

    def broken(obs, p):
        assert UnitPriceClaims.constructions == 0
        if obs.tick == 60 and p == POLICIES[1]:
            raise F5Error("UNIT_POLICY_FAILURE")
        return choose(obs, p)

    failed = e.prepare(observations, cutoffs, broken)
    counts = e.census(failed)
    assert (counts["valid"], counts["failed_policy"], counts["committed_engine_fallback"]) == (
        143,
        1,
        1,
    )
    slot = next(s for s in failed.slots if s.outcome == "FAILED_POLICY")
    assert slot.policy_action is None and slot.engine_disposition.origin == "ENGINE"
    assert UnitPriceClaims.constructions == 0
    degraded = e.evaluate(failed, calendar, cutoffs, UnitPriceClaims)
    assert degraded["candidate_class"] == DEGRADED
    assert degraded["books"][POLICIES[1]]["applied_fallback"] == 1


def test_common_prep_failure_cursor_and_seal_refuse_before_evaluator(unit_inputs):
    observations, cutoffs, calendar = unit_inputs
    cursor = e.DecisionCursor(observations)
    with pytest.raises(F5Error, match="SEMANTIC_CURSOR"):
        cursor.release(49)
    assert cursor.release(48).tick == 48
    corrupted = (replace(observations[0], issuers=observations[0].issuers[:-1]), *observations[1:])
    blocked = e.prepare(corrupted, cutoffs)
    assert e.census(blocked)["blocked_not_attempted"] == 144

    def forbidden(*args):
        pytest.fail("price factory entered before barrier")

    with pytest.raises(F5Error, match="BARRIER_NOT_OPEN"):
        e.evaluate(blocked, calendar, cutoffs, forbidden)
    sealed = e.prepare(observations, cutoffs)
    with pytest.raises(F5Error, match="BARRIER_SEAL"):
        verify_barrier(replace(sealed, slot_set_digest="0" * 64))


def test_terminal_failure_no_survivor_metrics_and_atomic_event(unit_inputs):
    observations, cutoffs, calendar = unit_inputs
    sealed = e.prepare(observations, cutoffs)

    class Missing(UnitPriceClaims):
        fail_day = "2026-01-16"

    result = e.evaluate(sealed, calendar, cutoffs, Missing)
    assert result["candidate_class"] == INCOMPLETE
    assert result["coverage"]["qualified_common_mark_cells"] == 1200
    assert all(
        x["full_period_candidate"]["state"] == "NOT_COMPUTABLE"
        and x["weekly_returns_evaluated"] == 47
        for x in result["books"].values()
    )

    class FillMissing(UnitPriceClaims):
        fail_day = "2025-02-17"

    result = e.evaluate(sealed, calendar, cutoffs, FillMissing)
    assert result["events"] == []
    assert all(
        x["terminal_book"]["cash"] == {"numerator": "1000", "denominator": "1"}
        for x in result["books"].values()
    )


def test_future_unit_price_poison_never_changes_sealed_prior_actions(unit_inputs):
    observations, cutoffs, calendar = unit_inputs
    sealed = e.prepare(observations, cutoffs)
    before = sealed.payload()

    class Poison(UnitPriceClaims):
        def read_mark(self, issuer, session, asof):
            mark = super().read_mark(issuer, session, asof)
            return replace(mark, value_ticks=9000000) if session >= "2025-09-01" else mark

    result = e.evaluate(sealed, calendar, cutoffs, Poison)
    assert sealed.payload() == before
    assert result["books"][POLICIES[0]]["candidate_metrics"]["net_return"] != 0
    # Fold2 carries capital; it is not reset to 1000 on t72.
    fold = next(
        x
        for x in result["events"]
        if x["tick"] == 73 and x["policy"] == POLICIES[0] and not x["mirror"]
    )
    assert fold["fill"]["pre_equity"] != {"numerator": "1000", "denominator": "1"}


def test_two_fresh_processes_are_refusals_not_genuine_research_replay(tmp_path):
    outputs, attempts = [], []
    for name, flags in (
        ("a", []),
        ("b", ["--f3-dir", str(tmp_path / "untrusted"), "--f3-evidence-sha256", "0" * 64]),
    ):
        out = tmp_path / name
        res = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "pit_research_lab.mvp.f5.cli",
                "--output-dir",
                str(out),
                *flags,
            ],
            cwd=f2.ROOT,
            env={**os.environ, "PYTHONPATH": str(f2.ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert res.returncode == 2 and res.stderr.strip() == "BLOCKED_INPUT"
        assert {p.name for p in out.iterdir()} == {"attempt.json", "metrics.json", "decisions.json"}
        attempt = json.loads((out / "attempt.json").read_bytes())["payload"]
        assert attempt["execution_status"] == "BLOCKED_INPUT" and attempt["completed_stages"] == []
        assert replay.effective_report(out)["full_period_comparison"]["state"] == "NOT_COMPUTABLE"
        outputs.append(out)
        attempts.append(attempt)
    assert attempts[0]["attempt_id"] != attempts[1]["attempt_id"]
    assert attempts[0]["process_id"] != attempts[1]["process_id"]
    assert (outputs[0] / "decisions.json").read_bytes() == (
        outputs[1] / "decisions.json"
    ).read_bytes()
    with pytest.raises(F5Error, match="ARTIFACT_INVENTORY"):
        replay.verify_pair(*outputs)


def test_output_refusals_and_failed_attempt_retention(tmp_path):
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(F5Error, match="OUTPUT_ALREADY_EXISTS"):
        replay.run_to_directory(existing)
    link = tmp_path / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(F5Error, match="OUTPUT_SYMLINK"):
        replay.run_to_directory(link / "out")
    with pytest.raises(F5Error, match="OUTPUT_IN_CHECKOUT"):
        replay.run_to_directory(f2.ROOT / "unauthorized-test-output")
    with pytest.raises(F5Error, match="UNSAFE_OUTPUT"):
        replay.run_to_directory(tmp_path / ".." / "outside")
    result = replay.run_to_directory(tmp_path / "failure")
    assert result["first_failure"] == "BLOCKED_INPUT"
    assert (tmp_path / "failure" / "attempt.json").stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "failure").stat().st_mode & 0o777 == 0o700


def test_source_calendar_cost_seed_and_numeric_identity_invalidates(monkeypatch):
    first = replay.provenance()
    regular = replay.regular_bytes

    def changed(p):
        raw = regular(p)
        return raw + b"\n" if p.name == "policies.py" else raw

    monkeypatch.setattr(replay, "regular_bytes", changed)
    assert digest(replay.provenance()) != digest(first)
    for changed_protocol in (
        replace(Protocol(), seed=18),
        replace(Protocol(), fee=Q()),
        replace(Protocol(), terminal="2026-02-01T18:00:00+08:00"),
    ):
        with pytest.raises(F5Error, match="UNSUPPORTED_PROTOCOL"):
            changed_protocol.validate()
    decode = f2.decode

    def bad_calendar(raw):
        body = decode(raw)
        if "calendar" in body:
            body["calendar"][0]["status"] = "CLOSED"
        return body

    monkeypatch.setattr(f2, "decode", bad_calendar)
    with pytest.raises(F5Error, match="CALENDAR_PIN"):
        prices.pinned_body()


def test_fold_boundary_keeps_previously_earned_capital(unit_inputs):
    observations, cutoffs, calendar = unit_inputs
    sealed = e.prepare(observations, cutoffs)

    class PriorGain(UnitPriceClaims):
        def read_mark(self, issuer, session, asof):
            mark = super().read_mark(issuer, session, asof)
            return replace(mark, value_ticks=200000) if session >= "2025-07-21" else mark

    result = e.evaluate(sealed, calendar, cutoffs, PriorGain)
    events = [x for x in result["events"] if x["policy"] == POLICIES[0] and not x["mirror"]]
    prior = next(x for x in events if x["tick"] == 71)
    boundary = next(x for x in events if x["tick"] == 72)
    expected = {"numerator": "2000000", "denominator": "1001"}
    assert prior["fill"]["post_equity"] == boundary["fill"]["pre_equity"] == expected
    assert prior["fill"]["after"] == boundary["fill"]["before"]


def test_absent_origin_retains_typed_blocked_slots_without_calls(tmp_path):
    result = replay.run_to_directory(tmp_path / "blocked")
    payload = json.loads((tmp_path / "blocked" / "decisions.json").read_bytes())["payload"]
    assert result["first_failure"] == "BLOCKED_INPUT"
    assert payload["census_state"] == "SEALED_BLOCKED"
    assert payload["coverage"]["attempted"] == payload["verified_oos_cells"] == 0
    assert len(payload["slots"]) == 144
    assert payload["slots"][0]["cutoff"] == "2025-02-14T18:00:00+08:00"
    assert all(
        s["schema"] == "F5_DECISION_SLOT_V1"
        and s["outcome"] == "BLOCKED_NOT_ATTEMPTED"
        and s["engine_disposition"] is None
        and s["policy_action"] is None
        for s in payload["slots"]
    )


def test_partial_mark_reads_do_not_post_partial_book_event(unit_inputs):
    observations, cutoffs, calendar = unit_inputs
    sealed = e.prepare(observations, cutoffs)

    class LastIssuerMissing(UnitPriceClaims):
        def read_mark(self, issuer, session, asof):
            if session == "2025-02-17" and issuer == ISSUERS[-1]:
                raise F5Error("UNIT_MISSING_LAST_ISSUER")
            return super().read_mark(issuer, session, asof)

    result = e.evaluate(sealed, calendar, cutoffs, LastIssuerMissing)
    assert result["candidate_class"] == INCOMPLETE and result["events"] == []
    assert result["coverage"]["committed_common_mark_cells"] == 5
    assert result["coverage"]["mark_requests"] == 10
    assert result["coverage"]["returned_mark_records"] == 9


@pytest.mark.parametrize("mode", ["unit_trusted", "absent", "mismatched", "fake_grant"])
def test_cli_trusted_embedding_wiring_stops_at_artifact_gate(tmp_path, monkeypatch, mode):
    """UNIT-ONLY origin callback control; deliberately NEVER a genuine producer PASS."""
    from pit_research_lab.mvp.f5 import cli, inputs

    producer = tmp_path / "unit_record_only"
    producer.mkdir(mode=0o700)
    out = tmp_path / "attempt"
    trace = []

    def forbidden(*args, **kwargs):
        pytest.fail("policy/evaluator must not run before genuine import")

    def unit_witness(directory, expected):
        trace.append("unit_witness")
        return inputs.ProducerOrigin(
            directory,
            "f" * 64 if mode == "mismatched" else expected,
            "1" * 40,
            "3.12.13",
            "CPython",
            (),
            "UNIT_ONLY_NOT_EXTERNAL_EVIDENCE",
            _grant=b"FAKE" if mode == "fake_grant" else b"",
        )

    def unit_artifact_stop(directory, expected, origin):
        if origin is None:
            inputs.require_origin(directory, expected, None)
        trace.append("artifact_gate")
        assert origin._grant
        # Real artifact gate still rejects this empty unit root after local binding.
        with pytest.raises(F5Error, match="ARTIFACT_INVENTORY"):
            inputs.require_origin(directory, expected, origin)
        raise F5Error("UNIT_ARTIFACT_GATE_STOP")

    monkeypatch.setattr(replay, "import_f3", unit_artifact_stop)
    monkeypatch.setattr(replay, "prepare", forbidden)
    monkeypatch.setattr(replay, "evaluate", forbidden)
    with pytest.raises(SystemExit) as stopped:
        cli.main(
            [
                "--output-dir",
                str(out),
                "--f3-dir",
                str(producer),
                "--f3-evidence-sha256",
                "0" * 64,
            ],
            origin_witness=None if mode == "absent" else unit_witness,
        )
    assert stopped.value.code == 2
    attempt = json.loads((out / "attempt.json").read_bytes())["payload"]
    reasons = {
        "unit_trusted": "UNIT_ARTIFACT_GATE_STOP",
        "absent": "BLOCKED_INPUT",
        "mismatched": "ORIGIN_WITNESS_BINDING",
        "fake_grant": "ORIGIN_WITNESS_REUSED_GRANT",
    }
    assert attempt["first_failure"] == reasons[mode]
    assert attempt["completed_stages"] == [] and attempt["comparison_status"] == INCOMPLETE
    assert trace == (
        []
        if mode == "absent"
        else ["unit_witness", "artifact_gate"]
        if mode == "unit_trusted"
        else ["unit_witness"]
    )
    assert attempt["origin_handoff_status"] == (
        "RECORD_BOUND_ARTIFACT_AND_SEMANTICS_PENDING"
        if mode == "unit_trusted"
        else "NOT_ESTABLISHED"
    )


def test_inert_marker_is_part_of_f5_code_identity(monkeypatch):
    before = replay.provenance()
    marker = "tests/unit/mvp_f5/__init__.py"
    assert marker in {x["path"] for x in before["files"]}
    read = replay.regular_bytes
    monkeypatch.setattr(
        replay,
        "regular_bytes",
        lambda p: read(p) + b"\n" if p.as_posix().endswith(marker) else read(p),
    )
    assert digest(replay.provenance()) != digest(before)


@pytest.fixture
def candidate_factory(tmp_path):
    """Authored verification-mechanism candidates, NOT F3 origin or research runs.

    Uses the real canonical reader/single-directory verifier with actual current
    source provenance. Slots/marks/books are explicitly UNIT-ONLY structural
    records satisfying that verifier, not qualified actions/prices or a ledger.
    UUIDs/PIDs are authored cooperative metadata, not fresh-process evidence.
    """
    import uuid
    from hashlib import sha256

    count = 0

    def make(kind=COMPLETE):
        nonlocal count
        count += 1
        out = tmp_path / f"unit_candidate_{count}"
        out.mkdir(mode=0o700)
        bodies = {
            "spec": {
                "protocol": replay.wire(Protocol()),
                "provenance": replay.provenance(),
                "producer_origin": {"receipt_id": "UNIT_ONLY_NO_EXTERNAL_ORIGIN"},
                "unit_only": True,
            },
            "decisions": {"slots": [{"unit_slot": i} for i in range(144)]},
            "ledger": {"marks": [{"unit_mark": i} for i in range(1205)]},
            "metrics": {
                "candidate_class": kind,
                "coverage": {"complete_calendar": True},
                "books": {"UNIT_ONLY_NOT_EMPIRICAL": {}},
            },
        }
        for name, body in bodies.items():
            replay._write(out, name, body)
        replay._write(
            out,
            "evidence",
            {
                "artifacts": [
                    {
                        "file": n + ".json",
                        "sha256": sha256((out / (n + ".json")).read_bytes()).hexdigest(),
                        "byte_length": (out / (n + ".json")).stat().st_size,
                    }
                    for n in replay.ARTIFACTS
                    if n != "evidence"
                ],
                "candidate_class": kind,
                "test_execution_attestation": "UNIT_ONLY_NOT_ATTESTED",
                "scope": "UNIT_ONLY_NOT_GENUINE_RESEARCH",
            },
        )
        replay._write(
            out,
            "attempt",
            {
                "attempt_id": str(uuid.uuid4()),
                "process_id": 10000 + count,
                "started_at": "2026-01-01T00:00:00+00:00",
                "finished_at": "2026-01-01T00:00:01+00:00",
                "elapsed_seconds": "1",
                "execution_status": "EVALUATED_REPLAY_PENDING",
                "comparison_status": INCOMPLETE,
                "replay_status": "NOT_RUN",
                "completed_stages": [
                    "F3_ORIGIN_AND_SOURCE_SEMANTICS_VERIFIED",
                    "TYPED_SLOT_CENSUS_SEALED",
                    "PORTFOLIOS_EVALUATED",
                    "DETERMINISTIC_EVIDENCE_WRITTEN",
                ],
                "first_failure": None,
                "evidence_sha256": sha256((out / "evidence.json").read_bytes()).hexdigest(),
                "peer_evidence_sha256": None,
                "peer_attempt_id": None,
                "peer_process_id": None,
                "producer_root": str(tmp_path / "UNIT_ONLY_NOT_A_PRODUCER"),
                "origin_handoff_status": "ORIGIN_ARTIFACT_AND_SEMANTICS_VERIFIED",
            },
        )
        assert replay.verify_directory(out)["candidate_class"] == kind
        return out

    return make


def test_R01_status_only_cannot_promote_real_single_directory(candidate_factory):
    """Pre-fix reproduction: original verifier passes; original reader releases books."""
    out = candidate_factory()
    attempt = replay._read(out, "attempt")
    attempt.update(
        execution_status="SUCCEEDED",
        replay_status="VERIFIED",
        comparison_status=COMPLETE,
        peer_evidence_sha256=attempt["evidence_sha256"],
    )
    replay._write(out, "attempt", attempt, update=True)
    assert replay.verify_directory(out)["candidate_class"] == COMPLETE
    report = replay.effective_report(out)
    assert report["comparison_status"] == INCOMPLETE
    assert report["full_period_comparison"]["state"] == "NOT_COMPUTABLE" and "books" not in report


def _unit_files(out):
    return {p.name: p.read_bytes() for p in out.iterdir()}


def _unit_edit(out, **fields):
    a = replay._read(out, "attempt")
    a.update(fields)
    replay._write(out, "attempt", a, update=True)


def _assert_blocked(out, peer=None):
    result = replay.effective_report(out, peer)
    assert result["comparison_status"] == INCOMPLETE and "books" not in result
    assert result["full_period_comparison"]["state"] == "NOT_COMPUTABLE"
    assert len(result["full_period_comparison"]["reason"]) <= 160
    return result


def test_R02_pending_pair_reports_read_only(candidate_factory):
    a, b = candidate_factory(), candidate_factory()
    before = (_unit_files(a), _unit_files(b))
    _assert_blocked(a)
    _assert_blocked(a, b)
    _assert_blocked(b, a)
    assert before == (_unit_files(a), _unit_files(b))


@pytest.mark.parametrize("kind", [COMPLETE, DEGRADED])
def test_R03_R04_R12_actual_pair_gate_and_deterministic_separation(candidate_factory, kind):
    a, b = candidate_factory(kind), candidate_factory(kind)
    before = [
        {n + ".json": (out / (n + ".json")).read_bytes() for n in replay.ARTIFACTS}
        for out in (a, b)
    ]
    replay.verify_pair(a, b)  # Real verifiers; authored IDs/PIDs, NOT real research processes.
    aa, bb = replay._read(a, "attempt"), replay._read(b, "attempt")
    for out, peer, own, other in ((a, b, aa, bb), (b, a, bb, aa)):
        report = replay.effective_report(out, peer)
        assert report["comparison_status"] == kind and "books" in report
        assert (own["peer_attempt_id"], own["peer_process_id"], own["peer_evidence_sha256"]) == (
            other["attempt_id"],
            other["process_id"],
            other["evidence_sha256"],
        )
        assert own["attempt_id"] != other["attempt_id"] and own["process_id"] != other["process_id"]
    for i, out in enumerate((a, b)):
        assert before[i] == {
            n + ".json": (out / (n + ".json")).read_bytes() for n in replay.ARTIFACTS
        }
        assert not any(
            k in repr(before[i])
            for k in ("peer_attempt_id", "peer_process_id", aa["attempt_id"], bb["attempt_id"])
        )
    stable = (_unit_files(a), _unit_files(b))
    replay.verify_pair(a, b)  # Explicitly supported exact-pair idempotence, no resealing.
    assert stable == (_unit_files(a), _unit_files(b))


@pytest.mark.parametrize("mode", ["root", "file", "mode"])
def test_R05_completed_pair_missing_or_unreadable_peer(candidate_factory, mode):
    a, b = candidate_factory(), candidate_factory()
    replay.verify_pair(a, b)
    if mode == "root":
        moved = b.with_name("unit_peer_moved")
        b.rename(moved)
    elif mode == "file":
        (b / "metrics.json").unlink()  # pytest-owned unit fixture only.
    else:
        (b / "attempt.json").chmod(0o000)
    _assert_blocked(a, b)
    with pytest.raises((ValueError, OSError)):
        replay.verify_pair(a, b)


def _unit_repin(out):
    from hashlib import sha256

    ev = replay._read(out, "evidence")
    for pin in ev["artifacts"]:
        raw = (out / pin["file"]).read_bytes()
        pin.update(sha256=sha256(raw).hexdigest(), byte_length=len(raw))
    replay._write(out, "evidence", ev, update=True)
    _unit_edit(out, evidence_sha256=sha256((out / "evidence.json").read_bytes()).hexdigest())


@pytest.mark.parametrize("name", replay.ARTIFACTS)
@pytest.mark.parametrize("rehashed", [False, True])
def test_R06_each_peer_artifact_mutation_and_self_rehash(candidate_factory, name, rehashed):
    a, b = candidate_factory(), candidate_factory()
    replay.verify_pair(a, b)
    changed = replay._read(b, name)
    if name == "evidence":
        changed["scope"] = "UNIT_ONLY_CHANGED"
    else:
        changed["unit_mutation"] = True
    replay._write(b, name, changed, update=True)
    if rehashed:
        _unit_repin(b)
        _unit_edit(a, peer_evidence_sha256=replay._read(b, "attempt")["evidence_sha256"])
        assert replay.verify_directory(b)["candidate_class"] == COMPLETE
        assert _assert_blocked(a, b)["full_period_comparison"]["reason"] == "REPLAY_MISMATCH"
    else:
        _assert_blocked(a, b)
    before = (_unit_files(a), _unit_files(b))
    with pytest.raises((ValueError, OSError)):
        replay.verify_pair(a, b)
    assert before == (_unit_files(a), _unit_files(b))
    _assert_blocked(b, a)


@pytest.mark.parametrize(
    "mode", ["same_root", "uuid", "pid", "symlink", "overlap", "wrong_peer", "hardlink"]
)
def test_R07_distinct_actual_roots_and_attempts(candidate_factory, tmp_path, mode):
    a, b = candidate_factory(), candidate_factory()
    if mode == "same_root":
        b = a
    elif mode == "hardlink":
        (b / "attempt.json").unlink()
        os.link(a / "attempt.json", b / "attempt.json")
    elif mode == "uuid":
        _unit_edit(b, attempt_id=replay._read(a, "attempt")["attempt_id"])
    elif mode == "pid":
        _unit_edit(b, process_id=replay._read(a, "attempt")["process_id"])
    elif mode == "symlink":
        link = tmp_path / "unit_alias"
        link.symlink_to(b, target_is_directory=True)
        b = link
    elif mode == "overlap":
        child = a / "unit_nested"
        child.mkdir(mode=0o700)
        b = child
    else:
        replay.verify_pair(a, b)
        b = candidate_factory()
    _assert_blocked(a, b)
    with pytest.raises((ValueError, OSError)):
        replay.verify_pair(a, b)


@pytest.mark.parametrize("failed_write", [1, 2])
@pytest.mark.parametrize("truncate", [False, True])
def test_R08_first_second_write_failure_never_releases(
    candidate_factory, monkeypatch, failed_write, truncate
):
    a, b = candidate_factory(), candidate_factory()
    write = replay._write
    calls = 0

    def fail(out, name, payload, **kw):
        nonlocal calls
        calls += 1
        if calls == failed_write:
            if truncate:
                (out / "attempt.json").write_bytes(b'{"schema":')
            raise OSError("UNIT_ONLY_WRITE_FAILURE")
        write(out, name, payload, **kw)

    with monkeypatch.context() as patch:
        patch.setattr(replay, "_write", fail)
        with pytest.raises(OSError):
            replay.verify_pair(a, b)
    _assert_blocked(a, b)
    _assert_blocked(b, a)
    if failed_write == 2:
        before = (_unit_files(a), _unit_files(b))
        with pytest.raises(ValueError):
            replay.verify_pair(a, b)  # no automatic mixed-state recovery
        assert before == (_unit_files(a), _unit_files(b))


@pytest.mark.parametrize("mode", ["pending", "failed", "truncated", "malformed", "missing"])
def test_R08_partial_receipt_read_failures(candidate_factory, mode):
    a, b = candidate_factory(), candidate_factory()
    replay.verify_pair(a, b)
    if mode == "pending":
        _unit_edit(
            b,
            execution_status="EVALUATED_REPLAY_PENDING",
            replay_status="NOT_RUN",
            comparison_status=INCOMPLETE,
            peer_attempt_id=None,
            peer_process_id=None,
            peer_evidence_sha256=None,
        )
    elif mode == "failed":
        _unit_edit(b, first_failure="UNIT_STOP", execution_status="FAILED")
    elif mode == "truncated":
        (b / "attempt.json").write_bytes(b'{"schema":')
    elif mode == "malformed":
        (b / "attempt.json").write_bytes(b"[]")
    else:
        (b / "attempt.json").unlink()
    before = (_unit_files(a), _unit_files(b))
    _assert_blocked(a, b)
    _assert_blocked(b, a)
    with pytest.raises((ValueError, OSError, KeyError, TypeError)):
        replay.verify_pair(a, b)
    assert before == (_unit_files(a), _unit_files(b))


@pytest.mark.parametrize(
    "field,value",
    [
        ("process_id", True),
        ("process_id", 0),
        ("attempt_id", "bad"),
        ("attempt_id", False),
        ("peer_attempt_id", None),
        ("peer_process_id", True),
        ("peer_evidence_sha256", "bad"),
        ("evidence_sha256", True),
        ("comparison_status", DEGRADED),
        ("execution_status", "FAILED"),
        ("replay_status", "NOT_RUN"),
        ("first_failure", "UNIT_FAILURE"),
        ("completed_stages", []),
        ("origin_handoff_status", "NOT_ESTABLISHED"),
        ("elapsed_seconds", "NaN"),
        ("finished_at", None),
        ("started_at", "no-time"),
        ("producer_root", None),
    ],
)
def test_R09_malformed_or_contradictory_attempts(candidate_factory, field, value):
    a, b = candidate_factory(), candidate_factory()
    replay.verify_pair(a, b)
    _unit_edit(b, **{field: value})
    before = (_unit_files(a), _unit_files(b))
    _assert_blocked(a, b)
    _assert_blocked(b, a)
    with pytest.raises((ValueError, OSError)):
        replay.verify_pair(a, b)
    assert before == (_unit_files(a), _unit_files(b))


@pytest.mark.parametrize("mode", ["unknown", "missing", "legacy"])
def test_R09_closed_receipt_schema_and_legacy_success(candidate_factory, mode):
    a, b = candidate_factory(), candidate_factory()
    replay.verify_pair(a, b)
    record = replay._read(b, "attempt")
    if mode == "unknown":
        record["unreviewed_authority"] = True
    elif mode == "missing":
        record.pop("peer_attempt_id")
    else:
        for key in ("peer_attempt_id", "peer_process_id"):
            record.pop(key)
    replay._write(b, "attempt", record, update=True)
    _assert_blocked(a, b)
    with pytest.raises(ValueError):
        replay.verify_pair(a, b)


def test_R10_failure_precedence_and_blocked_origin_cannot_pair(candidate_factory, tmp_path):
    a = candidate_factory()
    b = tmp_path / "actual_blocked_attempt"
    replay.run_to_directory(b)
    assert _assert_blocked(b, a)["full_period_comparison"]["reason"] == "BLOCKED_INPUT"
    _unit_edit(b, execution_status="SUCCEEDED", replay_status="VERIFIED")
    before = (_unit_files(a), _unit_files(b))
    _assert_blocked(a, b)
    assert _assert_blocked(b, a)["full_period_comparison"]["reason"] == "BLOCKED_INPUT"
    with pytest.raises(ValueError):
        replay.verify_pair(a, b)
    assert before == (_unit_files(a), _unit_files(b))


@pytest.mark.parametrize("mode", ["rebind", "stale_uuid", "stale_pid", "stale_hash"])
def test_R11_completed_pair_cannot_be_rebound(candidate_factory, mode):
    a, b = candidate_factory(), candidate_factory()
    replay.verify_pair(a, b)
    if mode == "rebind":
        b = candidate_factory()
    elif mode == "stale_uuid":
        _unit_edit(b, peer_attempt_id=replay._read(b, "attempt")["attempt_id"])
    elif mode == "stale_pid":
        _unit_edit(b, peer_process_id=replay._read(b, "attempt")["process_id"])
    else:
        _unit_edit(b, peer_evidence_sha256="f" * 64)
    before = (_unit_files(a), _unit_files(b))
    _assert_blocked(a, b)
    with pytest.raises(ValueError):
        replay.verify_pair(a, b)
    assert before == (_unit_files(a), _unit_files(b))


def test_R11_snapshot_drift_is_detected_and_no_unrelated_bug_success(
    candidate_factory, monkeypatch
):
    a, b = candidate_factory(), candidate_factory()
    replay.verify_pair(a, b)
    original = replay.verify_directory
    calls = 0

    def drift(out):
        nonlocal calls
        result = original(out)
        calls += 1
        if calls == 2:
            _unit_edit(a, elapsed_seconds="2")  # still semantically valid, snapshot changed
        return result

    with monkeypatch.context() as patch:
        patch.setattr(replay, "verify_directory", drift)
        assert _assert_blocked(a, b)["full_period_comparison"]["reason"] == "REPLAY_DRIFT"

    def unrelated(*args, **kwargs):
        raise RuntimeError("UNIT_IMPLEMENTATION_BUG")

    monkeypatch.setattr(replay, "_validate_pair", unrelated)
    with pytest.raises(RuntimeError):
        replay.effective_report(a, b)


def test_R10_incomplete_candidate_status_edits_cannot_promote(candidate_factory):
    a, b = candidate_factory(), candidate_factory()
    data = replay._read(a, "metrics")
    data["candidate_class"] = INCOMPLETE
    replay._write(a, "metrics", data, update=True)
    ev = replay._read(a, "evidence")
    ev["candidate_class"] = INCOMPLETE
    replay._write(a, "evidence", ev, update=True)
    _unit_repin(a)
    peer = replay._read(b, "attempt")
    _unit_edit(
        a,
        execution_status="SUCCEEDED",
        replay_status="VERIFIED",
        comparison_status=COMPLETE,
        peer_attempt_id=peer["attempt_id"],
        peer_process_id=peer["process_id"],
        peer_evidence_sha256=peer["evidence_sha256"],
    )
    assert _assert_blocked(a, b)["full_period_comparison"]["reason"] == "REPLAY_CLASS"
    before = (_unit_files(a), _unit_files(b))
    with pytest.raises(ValueError):
        replay.verify_pair(a, b)
    assert before == (_unit_files(a), _unit_files(b))


def test_R11_deterministic_file_identity_drift_during_completion(candidate_factory, monkeypatch):
    a, b = candidate_factory(), candidate_factory()
    original = replay._write

    def drifting(out, name, payload, **kwargs):
        original(out, name, payload, **kwargs)
        if out == a and name == "attempt":
            path = a / "spec.json"
            body = path.read_bytes()
            path.unlink()
            path.write_bytes(body)
            path.chmod(0o600)

    monkeypatch.setattr(replay, "_write", drifting)
    with pytest.raises(F5Error, match="REPLAY_DRIFT"):
        replay.verify_pair(a, b)
    _assert_blocked(a, b)
    _assert_blocked(b, a)
    assert replay._read(b, "attempt")["execution_status"] == "EVALUATED_REPLAY_PENDING"


@pytest.mark.parametrize("failed_write", [1, 2])
def test_R08_write_error_after_complete_bytes_retires_only_own_receipt(
    candidate_factory, monkeypatch, failed_write
):
    a, b = candidate_factory(), candidate_factory()
    original = replay._write
    calls = 0

    def fail_after(out, name, payload, **kwargs):
        nonlocal calls
        calls += 1
        original(out, name, payload, **kwargs)
        if calls == failed_write:
            raise OSError("UNIT_ONLY_POST_WRITE_ERROR")

    with monkeypatch.context() as patch:
        patch.setattr(replay, "_write", fail_after)
        with pytest.raises(OSError):
            replay.verify_pair(a, b)
    _assert_blocked(a, b)
    _assert_blocked(b, a)
    assert replay._read(a, "attempt")["first_failure"] == "REPLAY_COMPLETION_WRITE_FAILED"
    assert replay._read(b, "attempt")["first_failure"] is None
    before = (_unit_files(a), _unit_files(b))
    with pytest.raises(ValueError):
        replay.verify_pair(a, b)
    assert before == (_unit_files(a), _unit_files(b))
