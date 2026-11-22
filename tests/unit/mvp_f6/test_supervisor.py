"""Supplied-event models only; no OS facts or execution evidence."""

from dataclasses import FrozenInstanceError, asdict, replace

import pytest

from pit_research_lab.mvp.f6 import contracts as c
from pit_research_lab.mvp.f6.backend import supervisor as s
from pit_research_lab.mvp.f6.backend.launch_policy import ModelError, Refusal

INSTALL = "10000000-0000-4000-8000-000000000001"
APP = "10000000-0000-4000-8000-000000000002"
GEN = "10000000-0000-4000-8000-000000000003"
OTHER = "10000000-0000-4000-8000-000000000004"
PERMISSION = "10000000-0000-4000-8000-000000000006"
CHILD = "10000000-0000-4000-8000-000000000007"
BOOT = "10000000-0000-4000-8000-000000000005"
TIME = "2026-11-21T00:00:00+00:00"
SHA = "a" * 64


def event(model, kind, state, actor, facts, previous=None, generation=GEN):
    return s.ModeledEvent(
        (previous.revision if previous else 0) + 1,
        APP,
        model.sequence + 1,
        previous.revision if previous else 0,
        kind,
        state,
        actor,
        generation,
        TIME,
        BOOT,
        "100",
        c.canonical_json(facts),
        previous.event_sha256 if previous else s.ZERO_HASH,
    )


def apply(model, item, previous=None):
    return s.reduce_model(
        model,
        item,
        previous_revision=previous.revision if previous else 0,
        previous_sha256=previous.event_sha256 if previous else s.ZERO_HASH,
        registered_generations=(GEN, OTHER),
    )


def intent():
    model = s.RunModel(INSTALL, APP, GEN)
    item = event(
        model,
        "INTENT_COMMITTED",
        s.Phase.INTENT_HELD,
        "ADMISSION",
        {
            "admission_sha256": SHA,
            "expectation_sha256": SHA,
            "fingerprint": SHA,
            "allocation_id": OTHER,
        },
    )
    return apply(model, item), item


def test_closed_transitions_cas_hash_actor_and_generation():
    model, previous = intent()
    item = event(
        model,
        "LAUNCHER_REGISTERED",
        s.Phase.OWNER_READY,
        "SUPERVISOR",
        {
            "launcher_id": OTHER,
            "launcher_record_sha256": SHA,
        },
        previous,
    )
    for bad in (
        replace(item, revision=3),
        replace(item, run_sequence=3),
        replace(item, previous_sha256="b" * 64),
        replace(item, actor="ADMISSION"),
        replace(item, generation=PERMISSION),
    ):
        with pytest.raises(ModelError):
            apply(model, bad, previous)
    assert apply(model, item, previous).phase is s.Phase.OWNER_READY
    assert model.phase is s.Phase.INTENT_HELD
    with pytest.raises(ModelError):
        replace(item, facts=c.canonical_json({"unknown": SHA}))


def test_one_use_arm_model_and_no_positive_authority():
    model, previous = intent()
    for kind, phase, actor, facts in (
        (
            "LAUNCHER_REGISTERED",
            s.Phase.OWNER_READY,
            "SUPERVISOR",
            {"launcher_id": OTHER, "launcher_record_sha256": SHA},
        ),
        (
            "SPAWN_ARMED",
            s.Phase.ARM_CONSUMED,
            "LAUNCHER",
            {
                "permission_id": PERMISSION,
                "launcher_id": OTHER,
                "command_sha256": SHA,
                "deadline_monotonic_ns": "200",
            },
        ),
        (
            "CHILD_REGISTERED",
            s.Phase.CHILD_KNOWN,
            "LAUNCHER",
            {"child_id": CHILD, "child_record_sha256": SHA},
        ),
        (
            "EXIT_OBSERVED",
            s.Phase.EXIT_HELD,
            "LAUNCHER",
            {
                "wait_record_sha256": SHA,
                "result_kind": "EXIT",
                "exit_code": 0,
                "signal_number": None,
            },
        ),
    ):
        item = event(model, kind, phase, actor, facts, previous)
        model = apply(model, item, previous)
        previous = item
        assert model.live_refusal() is Refusal.B_CORE_AUTHORITY_ABSENT
    rearm = event(
        model,
        "SPAWN_ARMED",
        s.Phase.ARM_CONSUMED,
        "LAUNCHER",
        {
            "permission_id": PERMISSION,
            "launcher_id": OTHER,
            "command_sha256": SHA,
            "deadline_monotonic_ns": "200",
        },
        previous,
    )
    with pytest.raises(ModelError):
        apply(model, rearm, previous)
    assert not {p.value for p in s.Phase} & {
        "RUNNING",
        "SUCCEEDED",
        "COMPLETE",
        "AVAILABLE",
        "ACTUAL_F3_CLI",
    }


def test_first_failure_permanent_and_quarantine_has_no_revival():
    model, previous = intent()
    facts = {"reason": "RECOVERY_BLOCKED", "first_observed_at": TIME, "source_sha256": SHA}
    first = event(model, "FIRST_FAILURE", model.phase, "RECOVERY", facts, previous)
    model = apply(model, first, previous)
    frozen = model.first_failure
    duplicate = event(model, "FIRST_FAILURE", model.phase, "RECOVERY", facts, first)
    with pytest.raises(ModelError):
        apply(model, duplicate, first)
    secondary = event(
        model,
        "SECONDARY_FAILURE",
        model.phase,
        "RECOVERY",
        {
            "reason": "STORAGE_BLOCKED",
            "source_sha256": "b" * 64,
        },
        first,
    )
    model = apply(model, secondary, first)
    quarantine = event(
        model,
        "QUARANTINED",
        s.Phase.QUARANTINED,
        "RECOVERY",
        {
            "prior_revision": secondary.revision,
            "reason": "RECOVERY_BLOCKED",
            "evidence_sha256": SHA,
        },
        secondary,
    )
    model = apply(model, quarantine, secondary)
    assert model.first_failure == frozen
    revive = event(
        model,
        "RECONCILING",
        s.Phase.RECONCILING,
        "RECOVERY",
        {
            "prior_revision": quarantine.revision,
            "reason": "RECOVERY_BLOCKED",
            "evidence_sha256": SHA,
        },
        quarantine,
    )
    with pytest.raises(ModelError):
        apply(model, revive, quarantine)


def test_rev01_owner_only_unknown_ack_and_inconsistent_supplied_facts():
    owner = s.reconcile_model(s.RecoveryFacts(s.Window.W00, owner_committed=True))
    assert owner.classification == "OWNER_ONLY" and owner.first_failure is None
    uncertain = s.reconcile_model(
        s.RecoveryFacts(
            s.Window.W01,
            owner_committed=True,
            intent_committed=True,
            database_ack_ambiguous=True,
            lease_attributed=True,
        )
    )
    assert uncertain.classification == "QUARANTINED" and uncertain.first_failure is None
    with pytest.raises(ModelError):
        s.RecoveryFacts(s.Window.W04, arm_consumed=True)
    with pytest.raises(ModelError):
        s.RunModel(INSTALL, APP, GEN, child_known=True)
    assert owner.live_refusal() == uncertain.live_refusal() == Refusal.B_CORE_AUTHORITY_ABSENT
    lost = s.RecoveryFacts(
        s.Window.W07,
        owner_committed=True,
        intent_committed=True,
        launcher_registered=True,
        arm_consumed=True,
        child_known=True,
        lease_attributed=True,
        supervisor_loss_observed=True,
    )
    assert s.reconcile_model(lost).reason == "SUPERVISOR_LOST"
    assert (
        s.reconcile_model(replace(lost, wait_owner_lost=True)).reason == "EXECUTION_OUTCOME_UNKNOWN"
    )


@pytest.mark.parametrize(
    "window,changes,expected",
    [
        (s.Window.W00, {"owner_committed": False, "intent_committed": False}, "NO_INTENT"),
        (s.Window.W01, {}, "IDENTITY_ONLY"),
        (s.Window.W02, {}, "QUARANTINED"),
        (
            s.Window.W03,
            {"launcher_registered": True, "original_owner_survives": True},
            "HOLD_ORIGINAL",
        ),
        (s.Window.W04, {"launcher_registered": True, "arm_consumed": True}, "QUARANTINED"),
        (s.Window.W05, {"launcher_registered": True, "arm_consumed": True}, "QUARANTINED"),
        (
            s.Window.W06,
            {
                "launcher_registered": True,
                "arm_consumed": True,
                "child_known": True,
                "original_owner_survives": True,
            },
            "HOLD_ORIGINAL",
        ),
        (
            s.Window.W07,
            {"launcher_registered": True, "arm_consumed": True, "child_known": True},
            "QUARANTINED",
        ),
        (s.Window.W08, {"launcher_registered": True, "arm_consumed": True}, "QUARANTINED"),
        (
            s.Window.W09,
            {
                "launcher_registered": True,
                "arm_consumed": True,
                "child_known": True,
                "wait_observed": True,
            },
            "EXIT_HELD",
        ),
        (
            s.Window.W10,
            {
                "launcher_registered": True,
                "arm_consumed": True,
                "child_known": True,
                "wait_observed": True,
            },
            "EXIT_HELD",
        ),
        (s.Window.W11, {"boot_matches": False}, "QUARANTINED"),
        (s.Window.W12, {"storage_readable": False}, "STORAGE_BLOCKED"),
        (s.Window.W13, {"lease_attributed": False}, "QUARANTINED"),
        (s.Window.W14, {"boot_matches": False, "database_ack_ambiguous": True}, "IDENTITY_ONLY"),
    ],
    ids=[w.value for w in s.Window],
)
def test_crash_window(window, changes, expected):
    base = s.RecoveryFacts(
        window, owner_committed=True, intent_committed=True, lease_attributed=True
    )
    facts = replace(base, **changes)
    result = s.reconcile_model(facts)
    assert result.classification == expected
    for _ in range(3):
        assert s.reconcile_model(facts) == result
    assert result.first_failure is None  # Classification is not a newly observed cause.
    assert result.live_refusal() is Refusal.B_CORE_AUTHORITY_ABSENT
    if facts.intent_committed:
        first = s.Failure("STORAGE_BLOCKED", TIME, SHA)
        again = s.reconcile_model(replace(facts, first_failure=first))
        assert again.first_failure is first and again.reason == first.reason


def rem01_child():
    """Four accepted supplied events; no real child or wait is involved."""
    model, previous = intent()
    for kind, phase, actor, facts in (
        (
            "LAUNCHER_REGISTERED",
            s.Phase.OWNER_READY,
            "SUPERVISOR",
            {"launcher_id": OTHER, "launcher_record_sha256": SHA},
        ),
        (
            "SPAWN_ARMED",
            s.Phase.ARM_CONSUMED,
            "LAUNCHER",
            {
                "permission_id": PERMISSION,
                "launcher_id": OTHER,
                "command_sha256": SHA,
                "deadline_monotonic_ns": "200",
            },
        ),
        (
            "CHILD_REGISTERED",
            s.Phase.CHILD_KNOWN,
            "LAUNCHER",
            {"child_id": CHILD, "child_record_sha256": SHA},
        ),
    ):
        item = event(model, kind, phase, actor, facts, previous)
        model, previous = apply(model, item, previous), item
    return model, previous


def rem01_wait(model, previous, kind="EXIT", code=0, signal=None):
    return event(
        model,
        "EXIT_OBSERVED",
        s.Phase.EXIT_HELD,
        "LAUNCHER",
        {
            "wait_record_sha256": SHA,
            "result_kind": kind,
            "exit_code": code,
            "signal_number": signal,
        },
        previous,
    )


def rem01_waited(kind="EXIT", code=0, signal=None):
    model, previous = rem01_child()
    item = rem01_wait(model, previous, kind, code, signal)
    return apply(model, item, previous), item


def rem01_failure(model, previous, reason="CHILD_NONZERO_EXIT"):
    # source_sha256 has no approved equality relation to the wait-record digest.
    return event(
        model,
        "FIRST_FAILURE",
        model.phase,
        "LAUNCHER",
        {
            "reason": reason,
            "first_observed_at": TIME,
            "source_sha256": "b" * 64,
        },
        previous,
    )


def test_rem01_m01_exit_zero_refuses_nonzero_failure(record_property):
    model, previous = rem01_waited()
    item = rem01_failure(model, previous)
    assert model.child_known and model.wait_observed and model.sequence == 5
    assert previous.run_sequence == 5 and item.run_sequence == item.revision == 6
    assert c.decode_json(previous.facts)["exit_code"] == 0
    record_property("M01_prior_exit", "EXIT 0; SIGNAL null; five accepted events")
    with pytest.raises(ModelError):
        accepted = apply(model, item, previous)
        # Recorded only by the original defective reducer during the red run.
        record_property("M01_unexpected_acceptance", accepted.first_failure.reason)


@pytest.mark.parametrize("code", [1, 7, 255], ids=["EXIT1", "EXIT7", "EXIT255"])
def test_rem01_m02_nonzero_is_private_consistency_only(code):
    model, previous = rem01_waited(code=code)
    before = asdict(model)
    result = apply(model, rem01_failure(model, previous), previous)
    assert result.first_failure == s.Failure("CHILD_NONZERO_EXIT", TIME, "b" * 64)
    assert model.first_failure is None and asdict(model) == before
    assert result.wait_outcome is model.wait_outcome
    assert (
        result.wait_outcome.result_kind,
        result.wait_outcome.exit_code,
        result.wait_outcome.signal_number,
    ) == ("EXIT", code, None)
    assert result.wait_outcome.event is previous
    assert result.live_refusal() is Refusal.B_CORE_AUTHORITY_ABSENT
    with pytest.raises(FrozenInstanceError):
        result.first_failure.reason = "CHILD_TIMEOUT"
    with pytest.raises(FrozenInstanceError):
        result.wait_outcome.event = previous


def test_rem01_m03_signal_is_not_numeric_nonzero_exit():
    model, previous = rem01_waited("SIGNAL", None, 15)
    assert model.wait_outcome.result_kind == "SIGNAL"
    assert model.wait_outcome.exit_code is None and model.wait_outcome.signal_number == 15
    before = asdict(model)
    with pytest.raises(ModelError):
        apply(model, rem01_failure(model, previous), previous)
    assert asdict(model) == before and model.first_failure is None


def test_rem01_m04_absent_wait_and_uncertainty_cannot_prove_nonzero():
    model, previous = rem01_child()
    assert not model.wait_observed and model.wait_outcome is None
    for phase, kind in ((s.Phase.RECONCILING, "RECONCILING"), (s.Phase.QUARANTINED, "QUARANTINED")):
        transition = event(
            model,
            kind,
            phase,
            "RECOVERY",
            {
                "prior_revision": previous.revision,
                "reason": "EXECUTION_OUTCOME_UNKNOWN",
                "evidence_sha256": SHA,
            },
            previous,
        )
        uncertain = apply(model, transition, previous)
        assert uncertain.wait_outcome is None
        with pytest.raises(ModelError):
            apply(uncertain, rem01_failure(uncertain, transition), transition)
    with pytest.raises(ModelError):
        apply(model, rem01_failure(model, previous), previous)


def test_rem01_m05_boolean_or_incoherent_snapshot_is_not_wait_history():
    child, _ = rem01_child()
    waited, wait = rem01_waited(code=7)
    for changes in (
        {"wait_observed": True},
        {"wait_outcome": "EXIT 7"},
        {"first_failure": s.Failure("CHILD_NONZERO_EXIT", TIME, SHA)},
    ):
        with pytest.raises(ModelError):
            replace(child, **changes)
    for changes in (
        {"wait_observed": False},
        {"wait_outcome": None},
        {"phase": s.Phase.CHILD_KNOWN},
        {"sequence": wait.run_sequence - 1},
    ):
        with pytest.raises(ModelError):
            replace(waited, **changes)
    with pytest.raises(ModelError):
        replace(child, phase=s.Phase.EXIT_HELD)
    for changes in (
        {"app_run_id": OTHER},
        {"generation": OTHER},
        {"actor": "SUPERVISOR"},
        {"revision": wait.revision + 1},
        {"state": s.Phase.CHILD_KNOWN},
    ):
        with pytest.raises(ModelError):
            outcome = s.WaitOutcome(replace(wait, **changes))
            replace(waited, wait_outcome=outcome)


@pytest.mark.parametrize(
    "kind,code,signal",
    [
        ("EXIT", True, None),
        ("EXIT", False, None),
        ("EXIT", -1, None),
        ("EXIT", 256, None),
        ("EXIT", "7", None),
        ("EXIT", 7.0, None),
        ("EXIT", None, None),
        ("EXIT", 7, 15),
        ("SIGNAL", 7, 15),
        ("SIGNAL", None, True),
        ("SIGNAL", None, 0),
        ("SIGNAL", None, 65),
        ("SIGNAL", None, "15"),
        ("SIGNAL", None, None),
        ("UNKNOWN", 7, None),
    ],
)
def test_rem01_m06_malformed_wait_facts_refuse(kind, code, signal):
    model, previous = rem01_child()
    before = asdict(model)
    if type(code) is float:
        # P1-01 canonical_json already rejects floats. Supply malformed raw
        # facts to the event validator rather than weakening that contract.
        template = rem01_wait(model, previous, code=7)
        with pytest.raises(ModelError):
            replace(template, facts=template.facts.replace(b'"exit_code":7', b'"exit_code":7.0'))
        assert asdict(model) == before
        return
    with pytest.raises(ModelError):
        rem01_wait(model, previous, kind, code, signal)
    assert asdict(model) == before


def test_rem01_m07_first_cause_cannot_be_overwritten_or_reclassified():
    model, previous = rem01_waited(code=7)
    item = rem01_failure(model, previous)
    failed = apply(model, item, previous)
    before = asdict(failed)
    for reason in ("CHILD_NONZERO_EXIT", "CHILD_TIMEOUT", "STORAGE_BLOCKED"):
        with pytest.raises(ModelError):
            apply(failed, rem01_failure(failed, item, reason), item)
    assert asdict(failed) == before
    # Existing timeout semantics require a child, not a nonzero wait.
    child, child_event = rem01_child()
    timeout_event = rem01_failure(child, child_event, "CHILD_TIMEOUT")
    timeout = apply(child, timeout_event, child_event)
    zero_event = rem01_wait(timeout, timeout_event)
    after_zero = apply(timeout, zero_event, timeout_event)
    assert after_zero.first_failure is timeout.first_failure
    assert after_zero.first_failure.reason == "CHILD_TIMEOUT"
    assert after_zero.wait_outcome.exit_code == 0


def test_rem01_m08_secondary_and_recovery_preserve_cause_and_wait():
    model, previous = rem01_waited(code=7)
    first = rem01_failure(model, previous)
    model = apply(model, first, previous)
    original_wait, original_failure = model.wait_outcome, model.first_failure
    for kind, phase, facts in (
        (
            "SECONDARY_FAILURE",
            s.Phase.EXIT_HELD,
            {"reason": "STORAGE_BLOCKED", "source_sha256": SHA},
        ),
        (
            "RECONCILING",
            s.Phase.RECONCILING,
            {"prior_revision": 7, "reason": "RECOVERY_BLOCKED", "evidence_sha256": SHA},
        ),
        (
            "QUARANTINED",
            s.Phase.QUARANTINED,
            {"prior_revision": 8, "reason": "RECOVERY_BLOCKED", "evidence_sha256": SHA},
        ),
    ):
        previous = first
        item = event(model, kind, phase, "RECOVERY", facts, previous)
        model, first = apply(model, item, previous), item
        assert model.wait_outcome is original_wait and model.first_failure is original_failure
        assert model.live_refusal() is Refusal.B_CORE_AUTHORITY_ABSENT


def test_rem01_m09_rejected_failure_does_not_mutate_model_or_event_bytes():
    model, previous = rem01_waited()
    item = rem01_failure(model, previous)
    before = (
        asdict(model),
        previous.facts,
        previous.preimage(),
        previous.event_sha256,
        item.facts,
        item.preimage(),
        item.event_sha256,
    )
    with pytest.raises(ModelError):
        apply(model, item, previous)
    assert before == (
        asdict(model),
        previous.facts,
        previous.preimage(),
        previous.event_sha256,
        item.facts,
        item.preimage(),
        item.event_sha256,
    )
    assert model.sequence == 5 and model.first_failure is None


@pytest.mark.parametrize(
    "kind,code,signal", [("EXIT", 0, None), ("EXIT", 7, None), ("SIGNAL", None, 15)]
)
def test_rem01_m10_outcomes_and_quarantine_never_grant_authority(kind, code, signal):
    model, previous = rem01_waited(kind, code, signal)
    assert model.live_refusal() is Refusal.B_CORE_AUTHORITY_ABSENT
    item = event(
        model,
        "QUARANTINED",
        s.Phase.QUARANTINED,
        "RECOVERY",
        {
            "prior_revision": previous.revision,
            "reason": "RECOVERY_BLOCKED",
            "evidence_sha256": SHA,
        },
        previous,
    )
    quarantined = apply(model, item, previous)
    assert quarantined.wait_outcome is model.wait_outcome
    assert quarantined.live_refusal() is Refusal.B_CORE_AUTHORITY_ABSENT
    assert not {phase.value for phase in s.Phase} & {
        "RUNNING",
        "SUCCEEDED",
        "COMPLETE",
        "AVAILABLE",
        "ACTUAL_F3_CLI",
    }
    assert not {"VerifiedResultView", "EvidenceProvenanceView", "Popen", "GO"} & vars(s).keys()


def test_rem01_m12_rejected_or_repeated_exit_cannot_manufacture_wait():
    model, previous = rem01_child()
    item = rem01_wait(model, previous, code=7)
    before = asdict(model)
    for changes in (
        {"actor": "SUPERVISOR"},
        {"generation": OTHER},
        {"previous_sha256": "b" * 64},
        {"revision": item.revision + 1},
        {"run_sequence": item.run_sequence + 1},
    ):
        with pytest.raises(ModelError):
            apply(model, replace(item, **changes), previous)
        assert asdict(model) == before and model.wait_outcome is None
    with pytest.raises(ModelError):
        apply(model, rem01_failure(model, previous), previous)
    waited = apply(model, item, previous)
    before = asdict(waited)
    repeated = rem01_wait(waited, item, code=7)
    with pytest.raises(ModelError):
        apply(waited, repeated, item)
    assert asdict(waited) == before and waited.wait_outcome.event is item
