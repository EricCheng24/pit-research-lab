"""A-only synthetic forms/refusals; never a launch permission or child test."""

import ast
import builtins
import importlib
import socket
import sqlite3
import subprocess
import threading
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from pit_research_lab.mvp.f6 import backend
from pit_research_lab.mvp.f6 import contracts as c
from pit_research_lab.mvp.f6.backend import catalog, config, security

UUID = "00000000-0000-4000-8000-000000000001"


def populated():
    return config.Configuration(
        policy=config.PolicyForm(tuple((key, 1) for key in config.Limit), "1" * 64),
        provenance=config.ProvenanceForm(
            "/synthetic/python",
            "3.12.13",
            "/synthetic/checkout",
            "/synthetic/checkout/src",
            "a" * 40,
            "b" * 64,
            "c" * 64,
            c.SOURCE_SHA256,
            c.MANIFEST_SHA256,
            c.PROTOCOL_SHA256,
            c.DATASET_SHA256,
            "2" * 64,
        ),
        private_root="/synthetic/private",
        port=12345,
        installation_id=UUID,
        storage_approval_ref="3" * 64,
    )


def test_unconfigured_and_populated_forms_always_refuse():
    assert config.launch_refusal(config.Configuration()) == config.Unavailability.NOT_CONFIGURED
    assert config.launch_refusal(populated()) == config.Unavailability.B_PHASE_AUTHORITY_ABSENT
    assert not hasattr(config, "launch") and not hasattr(config, "ready")


@pytest.mark.parametrize(
    "field", ["policy", "provenance", "private_root", "port", "installation_id"]
)
def test_each_missing_prerequisite_refuses(field):
    assert config.launch_refusal(replace(populated(), **{field: None})) == (
        config.Unavailability.NOT_CONFIGURED
    )


@pytest.mark.parametrize("field", ["policy", "provenance", "storage_approval_ref"])
def test_each_missing_approval_refuses(field):
    form = populated()
    changed = (
        None
        if field == "storage_approval_ref"
        else replace(getattr(form, field), approval_ref=None)
    )
    assert config.launch_refusal(replace(form, **{field: changed})) == (
        config.Unavailability.UNAPPROVED_FORM
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", "unknown"),
        ("capability_id", "other"),
        ("port", True),
        ("port", 0),
        ("port", 65536),
        ("port", 1.5),
        ("private_root", "/"),
        ("private_root", "relative"),
        ("private_root", "/tmp/../private"),
        ("private_root", "/tmp//private"),
        ("private_root", "/tmp/private/"),
        ("private_root", "/tmp/%2E"),
        ("installation_id", "not-an-app-id"),
        ("storage_approval_ref", "secret"),
    ],
)
def test_closed_configuration_form(field, value):
    with pytest.raises(config.ConfigurationError, match="^INVALID_CONFIGURATION$"):
        replace(populated(), **{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("python_version", "3.14.4"),
        ("python_version", "3.12.01"),
        ("git_head", "a" * 39),
        ("code_sha256", "X" * 64),
        ("lock_sha256", "short"),
        ("import_path", "/unrelated/src"),
        ("python_path", "python3"),
        ("source_sha256", "d" * 64),
        ("manifest_sha256", "d" * 64),
        ("protocol_sha256", "d" * 64),
        ("dataset_sha256", "d" * 64),
    ],
)
def test_runtime_and_fixed_identity_drift_refuses(field, value):
    with pytest.raises(config.ConfigurationError, match="^INVALID_CONFIGURATION$"):
        replace(populated().provenance, **{field: value})


@pytest.mark.parametrize("value", [True, 0, -1, 2**53, 1.5, "1", None])
def test_policy_numeric_abuse(value):
    limits = tuple((key, value if key == config.Limit.BODY_BYTES else 1) for key in config.Limit)
    with pytest.raises(config.ConfigurationError, match="^INVALID_CONFIGURATION$"):
        config.PolicyForm(limits)


def test_forms_reject_mutable_duplicate_and_unknown_configuration():
    limits = tuple((key, 1) for key in config.Limit)
    for bad in (
        list(limits),
        limits[:-1],
        (limits[0],) * len(limits),
        tuple(list(v) for v in limits),
    ):
        with pytest.raises(config.ConfigurationError):
            config.PolicyForm(bad)
    with pytest.raises(TypeError):
        config.Configuration(ready=True)
    form = populated()
    with pytest.raises(FrozenInstanceError):
        form.port = 23456
    with pytest.raises(FrozenInstanceError):
        form.policy.approval_ref = "4" * 64
    # Even deliberate frozen-dataclass bypass is revalidated; no authority follows.
    object.__setattr__(form.policy, "limits", ((config.Limit.BODY_BYTES, 1),))
    with pytest.raises(config.ConfigurationError):
        config.launch_refusal(form)


def test_imports_and_constructors_inert_under_restricted_in_process_seam(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("inert operation attempted I/O or background activity")

    before = tuple(tmp_path.iterdir())
    with monkeypatch.context() as patch:
        patch.setattr(socket, "socket", forbidden)
        patch.setattr(subprocess, "Popen", forbidden)
        patch.setattr(sqlite3, "connect", forbidden)
        patch.setattr(threading.Thread, "start", forbidden)
        patch.setattr(Path, "mkdir", forbidden)
        patch.setattr(Path, "open", forbidden)
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(catalog.os, "getenv", forbidden)
        patch.setattr(catalog.os, "open", forbidden)
        for module in (backend, config, security, catalog):
            importlib.reload(module)
        assert config.launch_refusal(config.Configuration()) == config.Unavailability.NOT_CONFIGURED
        catalog.TestCatalog(catalog.TestLocation(tmp_path, "inert.sqlite3"))
    assert tuple(tmp_path.iterdir()) == before


def test_source_boundary_has_no_native_http_or_execution_imports():
    for module in (backend, config, security, catalog):
        tree = ast.parse(Path(module.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [v.name for v in node.names] if isinstance(node, ast.Import) else [node.module]
                )
                assert all(
                    not any(
                        x in (name or "")
                        for x in (
                            "f3_l1",
                            "f2.",
                            "fixtures",
                            "subprocess",
                            "socket",
                            "asyncio",
                            "starlette",
                            "uvicorn",
                            "threading",
                            "http.server",
                        )
                    )
                    for name in names
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"exec", "eval", "__import__"}
