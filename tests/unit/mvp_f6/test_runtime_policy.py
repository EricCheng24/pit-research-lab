"""Closed forms and safe in-process import/constructor inertia checks."""

import ast
import importlib
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest

from pit_research_lab.mvp.f6 import contracts as c
from pit_research_lab.mvp.f6.backend import launch_policy as p


def expectation():
    return p.Expectations(
        c.canonical_json(
            {
                "version": 1,
                "installation_id": "30000000-0000-4000-8000-000000000001",
                "allocation_id": "30000000-0000-4000-8000-000000000002",
                **{key: "a" * 64 for key in p.EXPECTATION_FIELDS.split()[3:]},
            }
        )
    )


def test_missing_and_complete_expectations_always_refuse():
    assert p.launch_refusal() is p.Refusal.B_CORE_AUTHORITY_ABSENT
    assert p.launch_refusal(expectation()) is p.Refusal.B_CORE_AUTHORITY_ABSENT
    for key in p.EXPECTATION_FIELDS.split():
        obj = expectation().values()
        del obj[key]
        with pytest.raises(p.ModelError):
            p.Expectations(c.canonical_json(obj))


def test_hash_shaped_approval_cannot_enable_live_execution():
    policy = p.FinitePolicy(60, 30, 2**28, 2**20, 2**20, 64, 1, 2**16, "a" * 64)
    assert policy.live_refusal() is p.Refusal.B_CORE_AUTHORITY_ABSENT
    assert replace(policy, approval_ref=None).live_refusal() == policy.live_refusal()
    for field, bad in (
        ("processes", True),
        ("wall_seconds", 0),
        ("memory_bytes", 2**60),
        ("approval_ref", "approved"),
    ):
        with pytest.raises(p.ModelError):
            replace(policy, **{field: bad})


def test_future_command_is_fixed_lexical_declaration_only():
    command = p.FixedCommandDeclaration(
        "/synthetic/bin/python", "/synthetic/source", "/synthetic/output/job"
    )
    assert command.argv() == (
        "/synthetic/bin/python",
        "-B",
        "-m",
        "pit_research_lab.mvp.f3_l1.cli",
        "--output-dir",
        "/synthetic/output/job",
    )
    for bad in ("relative", "/a/../b", "/a//b", "/a%20", "/a\n"):
        with pytest.raises(p.ModelError):
            replace(command, python=bad)
    with pytest.raises(p.ModelError):
        replace(command, output_leaf="/synthetic/source/output")


def test_environment_is_supplied_whitelist_without_inheritance(monkeypatch):
    monkeypatch.setenv("P103B_UNTRUSTED", "must-not-inherit")
    env = dict(
        p.environment_declaration("/source", "/private/home", "/private/tmp", "/bin:/usr/bin")
    )
    assert set(env) == {
        "PATH",
        "PYTHONPATH",
        "HOME",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONNOUSERSITE",
    }
    assert env["PYTHONPATH"] == "/source/src" and "P103B_UNTRUSTED" not in env
    with pytest.raises(p.ModelError):
        p.environment_declaration("/source", "/home", "/tmp", "/bin:")


def test_canonical_bounds_duplicates_nested_and_domain_separation():
    for raw in (
        b'{"x":1,"x":1}',
        b'{ "x":1}',
        b'{"x":1.0}',
        b'{"x":' + b"[" * 17 + b"0" + b"]" * 17 + b"}",
        b'{"x":' + b"9" * 100 + b"}",
        b'{"x":true,"extra":1}',
    ):
        with pytest.raises(p.ModelError):
            p.bounded_record(raw, "x")
    raw = c.canonical_json({"x": "synthetic"})
    assert p.digest("OWNER", raw) != p.digest("EVENT", raw)
    with pytest.raises(p.ModelError):
        p.digest("APPROVAL", raw)


def test_import_and_construction_are_inert_and_f6_origins(monkeypatch, tmp_path):
    import os
    import sqlite3

    names = ("launch_policy", "process_identity", "supervisor", "runtime_catalog")
    prefix = "pit_research_lab.mvp.f6.backend."
    modules = [importlib.import_module(prefix + name) for name in names]
    source_root = Path(__file__).resolve().parents[3] / "src" / "pit_research_lab"
    sources = [Path(module.__file__).read_text() for module in modules]
    trees = [ast.parse(source) for source in sources]
    for module, tree in zip(modules, trees, strict=True):
        assert Path(module.__file__).is_relative_to(source_root)
        assert not any(
            isinstance(node, (ast.Import, ast.ImportFrom))
            and any(
                alias.name.split(".")[0]
                in {"subprocess", "socket", "threading", "multiprocessing", "fcntl", "signal"}
                for alias in node.names
            )
            for node in ast.walk(tree)
        )
        assert not any(
            isinstance(node, ast.Attribute)
            and node.attr
            in {
                "Popen",
                "fork",
                "kill",
                "getenv",
                "environ",
                "pidfd_open",
                "flock",
                "Thread",
            }
            for node in ast.walk(tree)
        )

    def forbidden(*args, **kwargs):
        raise AssertionError("import or constructor attempted I/O")

    before = tuple(tmp_path.iterdir())
    with monkeypatch.context() as spies:
        spies.setattr(sqlite3, "connect", forbidden)
        spies.setattr(os, "open", forbidden)
        spies.setattr(Path, "mkdir", forbidden)
        spies.setattr(Path, "lstat", forbidden)
        probes = []
        for name, source in zip(names, sources, strict=True):
            probe = ModuleType(prefix + name + "_inertia_probe")
            probe.__package__ = prefix.removesuffix(".")
            spies.setitem(sys.modules, probe.__name__, probe)
            exec(compile(source, "<inert B module body>", "exec"), probe.__dict__)
            probes.append(probe)
        catalog = probes[-1]
        inert_root = tmp_path / "pit-p103b-bcore.1.inert"
        catalog.SyntheticCatalog(catalog.TestLocation(inert_root, "inert.sqlite3"))
        assert p.launch_refusal(expectation()) is p.Refusal.B_CORE_AUTHORITY_ABSENT
    assert tuple(tmp_path.iterdir()) == before
