"""U08–U10: model sequencing, no retry and source import inertia only."""

import importlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from pit_research_lab.mvp.f6 import contracts as c
from pit_research_lab.mvp.f6.backend import child_launcher as l
from pit_research_lab.mvp.f6.backend import os_ownership as o
from pit_research_lab.mvp.f6.backend import os_supervisor as s
from pit_research_lab.mvp.f6.backend.launch_policy import ModelError

IDS = tuple(f"73000000-0000-4000-8000-{n:012d}" for n in range(1, 9))
SHA = "a" * 64


def protocol():
    binding = o.Binding(IDS[0], IDS[1], IDS[2], IDS[3], SHA)
    instance = s.SupervisorProtocol(binding, SHA, s.SuppliedCommit("TX1", 7, SHA, True))
    raw = c.canonical_json(
        {
            "version": 1,
            "installation_id": IDS[0],
            "app_run_id": IDS[1],
            "launcher_id": IDS[3],
            "generation": IDS[2],
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
    )
    instance.register_model(raw, s.SuppliedCommit("TX2", 8, SHA, True))
    request = {
        "permission_id": IDS[5],
        "expected_revision": 8,
        "expected_run_sequence": 2,
        "command_sha256": SHA,
        "deadline_monotonic_ns": "2000",
    }
    return instance, request


def test_definite_arm_then_go_and_single_attempt():
    instance, request = protocol()
    assert instance.run_sequence == 2 and instance.revision == 8
    assert "request_sha256" in c.decode_json(instance.allow_arm_model(request))
    report = {"permission_id": IDS[5], "revision": 9, "event_sha256": SHA}
    instance.observe_arm_model(report, s.SuppliedCommit("TX3", 9, SHA, True))
    assert c.decode_json(instance.go_model())["payload"] == report
    with pytest.raises(ModelError):
        instance.go_model()
    effects = l.ModelEffects()
    launcher = l.OriginalLauncher()
    result = launcher.attempt_model(effects)
    assert effects.calls == list(l.STEPS)
    assert (
        effects.calls.index("ARM_COMMIT") < effects.calls.index("GO") < effects.calls.index("SPAWN")
    )
    assert effects.calls.index("GO_ACK_SEND") < effects.calls.index("SPAWN")
    assert result.spawn_calls == 1 and result.arm_may_be_consumed
    assert result.evidence_class == "MODEL_ONLY"
    with pytest.raises(ModelError):
        launcher.attempt_model(l.ModelEffects())


def test_all_uncertainty_points_refuse_retry():
    for step in l.STEPS:
        for ambiguous in (False, True):
            launcher = l.OriginalLauncher()
            effects = l.ModelEffects(step, ambiguous)
            result = launcher.attempt_model(effects)
            assert effects.calls[-1] == step
            assert result.spawn_calls == (1 if l.STEPS.index(step) >= l.STEPS.index("SPAWN") else 0)
            assert result.phase in ("REFUSED_HELD", "UNKNOWN_HELD")
            assert launcher.attempt_entered
            with pytest.raises(ModelError):
                launcher.attempt_model(l.ModelEffects())
    instance, request = protocol()
    instance.allow_arm_model(request)
    with pytest.raises(ModelError):
        instance.observe_arm_model(
            {"permission_id": IDS[5], "revision": 9, "event_sha256": SHA},
            s.SuppliedCommit("TX3", 9, SHA, False),
        )
    with pytest.raises(ModelError):
        instance.go_model()
    for change in (
        {"expected_run_sequence": 8},
        {"command_sha256": "b" * 64},
        {"expected_revision": 7},
    ):
        instance, request = protocol()
        with pytest.raises(ModelError):
            instance.allow_arm_model({**request, **change})
        assert instance.refused
    instance, _ = protocol()
    instance.disconnect()
    with pytest.raises(ModelError):
        instance.go_model()


def test_imports_constructors_and_helper_facts_cannot_activate_native(monkeypatch):
    prefix = "pit_research_lab.mvp.f6.backend."
    names = ("os_ownership", "os_runtime_catalog", "os_supervisor", "child_launcher")
    modules = [importlib.import_module(prefix + n) for n in names]
    sources = [Path(m.__file__).read_text() for m in modules]
    calls = []

    def forbidden(*args, **kwargs):
        calls.append("FORBIDDEN")
        raise AssertionError("physical or catalog I/O reached")

    with monkeypatch.context() as patch:
        for module, name in (
            (os, "open"),
            (os, "pidfd_open"),
            (os, "kill"),
            (os, "killpg"),
            (subprocess, "Popen"),
            (subprocess, "run"),
            (sqlite3, "connect"),
            (o.socket, "socketpair"),
            (o.socket, "socket"),
            (o.fcntl, "flock"),
            (o.fcntl, "fcntl"),
            (o.signal, "pidfd_send_signal"),
            (Path, "lstat"),
            (Path, "mkdir"),
            (Path, "open"),
        ):
            patch.setattr(module, name, forbidden, raising=False)
        for name, source in zip(names, sources, strict=True):
            probe = ModuleType(prefix + name + "_inertia")
            probe.__package__ = prefix.removesuffix(".")
            patch.setitem(sys.modules, probe.__name__, probe)
            exec(compile(source, "<OAA-02 inert source>", "exec"), probe.__dict__)
        spec = s.HelperSpec("/tmp/pit-p103b-os-helper.1.model", "P02", 0)
        assert set(spec.environment()) == {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL"}
        assert spec.argv(o.FDPlan("child", (5,)))[1:4] == ("-I", "-S", "-B")
        assert "f3_l1" not in " ".join(spec.argv(o.FDPlan("child", (5,))))
        assert s.CandidateBudget().live_refusal() == "UNAPPROVED_PHYSICAL_BUDGET"
        instance, _ = protocol()
        launcher = l.OriginalLauncher()
        for operation in (
            lambda: instance.run_owned(SHA),
            lambda: launcher.spawn_owned(SHA, spec, o.FDPlan("child", (5,))),
            lambda: launcher.original_wait(SHA, 1),
        ):
            with pytest.raises(o.PhysicalNotAuthorized):
                operation()
    assert calls == []
