"""U05–U07: closed records and supplied waits are never OS credentials."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from pit_research_lab.mvp.f6 import contracts as c
from pit_research_lab.mvp.f6.backend import os_runtime_catalog as r
from pit_research_lab.mvp.f6.backend import runtime_catalog as core
from pit_research_lab.mvp.f6.backend import supervisor as s
from pit_research_lab.mvp.f6.backend.child_launcher import (
    SuppliedWait,
    hold_unregistered_observation,
)
from pit_research_lab.mvp.f6.backend.launch_policy import ModelError, digest
from pit_research_lab.mvp.f6.backend.os_ownership import (
    PhysicalNotAuthorized,
    require_physical_session,
)

IDS = tuple(f"72000000-0000-4000-8000-{n:012d}" for n in range(1, 9))
TIME = "2026-11-22T00:00:00+00:00"
SHA = "a" * 64


def launcher():
    return {
        "version": 1,
        "installation_id": IDS[0],
        "app_run_id": IDS[1],
        "launcher_id": IDS[2],
        "generation": IDS[3],
        "boot_id": IDS[4],
        "pid": 4001,
        "start_ticks": "101",
        "pgid": 4001,
        "sid": 4001,
        "installation_lock_dev": "8",
        "installation_lock_ino": "9",
        "job_lock_dev": "8",
        "job_lock_ino": "10",
        "channel_nonce_sha256": SHA,
        "executable_sha256": SHA,
    }


def event(kind, phase, actor, facts, revision=2, sequence=2):
    return s.ModeledEvent(
        revision,
        IDS[1],
        sequence,
        revision - 1,
        kind,
        phase,
        actor,
        IDS[3],
        TIME,
        IDS[4],
        "100",
        c.canonical_json(facts),
        SHA,
    )


def test_record_event_bijection_and_original_generation():
    raw = c.canonical_json(launcher())
    accepted = event(
        "LAUNCHER_REGISTERED",
        s.Phase.OWNER_READY,
        "SUPERVISOR",
        {"launcher_id": IDS[2], "launcher_record_sha256": digest("LAUNCHER", raw)},
    )
    assert r.record_matches_event("LAUNCHER", raw, accepted)
    for changed in (
        replace(accepted, generation=IDS[7]),
        replace(accepted, app_run_id=IDS[7]),
        replace(
            accepted,
            facts=c.canonical_json({"launcher_id": IDS[2], "launcher_record_sha256": "b" * 64}),
        ),
    ):
        assert not r.record_matches_event("LAUNCHER", raw, changed)
    for key, bad in (
        ("version", True),
        ("pid", True),
        ("generation", IDS[1]),
        ("start_ticks", "01"),
        ("extra", "unapproved"),
    ):
        with pytest.raises((ModelError, c.ContractError)):
            r.record("LAUNCHER", c.canonical_json({**launcher(), key: bad}))
    assert r.STATEMENTS is core.STATEMENTS and r.SCHEMA_IDENTITY == core.SCHEMA_IDENTITY
    assert not issubclass(r.OsHelperCatalog, core.SyntheticCatalog)


def test_wait_and_first_failure_consistency():
    outcomes = [(0, ("EXIT", 0, None)), (7, ("EXIT", 7, None)), (-15, ("SIGNAL", None, 15))]
    for code, result in outcomes:
        claim = SuppliedWait(IDS[2], True, code, True, True)
        assert claim.classification() == result
        for change in (
            {"child_registered": False},
            {"original_parent_retained": False},
            {"reaped": False},
            {"returncode": None},
        ):
            assert replace(claim, **change).classification() == ("UNKNOWN_HELD", None, None)
        wait = event(
            "EXIT_OBSERVED",
            s.Phase.EXIT_HELD,
            "LAUNCHER",
            {
                "wait_record_sha256": SHA,
                "result_kind": result[0],
                "exit_code": result[1],
                "signal_number": result[2],
            },
            revision=5,
            sequence=5,
        )
        outcome = s.WaitOutcome(wait)
        model = s.RunModel(
            IDS[0],
            IDS[1],
            IDS[3],
            sequence=5,
            phase=s.Phase.EXIT_HELD,
            armed=True,
            child_known=True,
            wait_observed=True,
            launcher_id=IDS[2],
            permission_id=IDS[5],
            child_id=IDS[6],
            wait_outcome=outcome,
        )
        failure = event(
            "FIRST_FAILURE",
            s.Phase.EXIT_HELD,
            "LAUNCHER",
            {
                "reason": "CHILD_NONZERO_EXIT",
                "first_observed_at": TIME,
                "source_sha256": SHA,
            },
            revision=6,
            sequence=6,
        )
        failure = replace(failure, previous_sha256=wait.event_sha256)
        if code == 7:
            failed = s.reduce_model(
                model,
                failure,
                previous_revision=5,
                previous_sha256=wait.event_sha256,
                registered_generations=(IDS[3],),
            )
            assert (
                failed.wait_outcome is outcome
                and failed.first_failure.reason == "CHILD_NONZERO_EXIT"
            )
            with pytest.raises(FrozenInstanceError):
                failed.first_failure.reason = "STORAGE_BLOCKED"
        else:
            with pytest.raises(ModelError):
                s.reduce_model(
                    model,
                    failure,
                    previous_revision=5,
                    previous_sha256=wait.event_sha256,
                    registered_generations=(IDS[3],),
                )
    for code in (True, -65, 256, "7"):
        with pytest.raises(ModelError):
            SuppliedWait(IDS[2], True, code, True, True).classification()
    limited = hold_unregistered_observation(b"bounded supplied original-wait observation")
    assert limited.disposition == "REGISTRATION_GAP_UNKNOWN_HELD"
    assert not hasattr(limited, "child_record_sha256") and not hasattr(
        limited, "wait_record_sha256"
    )
    with pytest.raises(ModelError):
        hold_unregistered_observation(b"x" * 16385)


def test_synthetic_records_and_readback_grant_no_authority(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("constructor/authority check performed I/O")

    monkeypatch.setattr(r.sqlite3, "connect", forbidden)
    monkeypatch.setattr(Path, "lstat", forbidden)
    location = r.RecordedLocation(
        Path("/tmp/pit-p103b-os-source.1.inert/recorded"), "catalog.sqlite3"
    )
    catalog = r.OsHelperCatalog(location)
    synthetic = core.SyntheticOwnerAck(IDS[3], SHA, object())
    recorded = r.RecordedOwnerAck(IDS[3], SHA, object())
    history = r.RecordedHistory(IDS[0], 0, None, ())
    assert history.evidence_class == recorded.live_refusal() == "RECORDED_ONLY"
    for supplied in (synthetic, recorded, history, SHA, launcher(), object()):
        with pytest.raises(PhysicalNotAuthorized):
            require_physical_session(supplied, "catalog")
        with pytest.raises(PhysicalNotAuthorized):
            catalog.activate_physical(supplied)
    with pytest.raises(ModelError):
        r.RecordedLocation(Path("/tmp/pit-p103b-os-helper.1.inert"), "catalog.sqlite3")
    physical = r.OsHelperCatalog(r.PhysicalLocation(Path("/tmp/pit-p103b-os-helper.1.inert")))
    with pytest.raises(r.CatalogRefusal, match="RECORDED_ROOT_REQUIRED"):
        physical.initialize_recorded(IDS[0], SHA, TIME)
    for operation in (
        lambda: physical.activate_physical(history),
        lambda: physical.open_physical_readback(history),
        lambda: physical.attach_original_launcher(history),
        lambda: physical.register_owner_owned(history, b"{}"),
        lambda: physical.admit_owned(
            history, None, None, expected_revision=0, expected_capability_revision=SHA
        ),
        lambda: physical.append_owned(
            history, "WAIT", b"{}", expected_revision=0, observed_at=TIME, monotonic_ns="1"
        ),
        lambda: physical.quarantine_owned(
            history, IDS[1], SHA, expected_revision=0, observed_at=TIME, monotonic_ns="1"
        ),
    ):
        with pytest.raises(PhysicalNotAuthorized):
            operation()
