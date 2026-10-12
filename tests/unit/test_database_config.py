"""Offline target, file and secret policy negatives."""

import os
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy.engine import URL

from pit_research_lab.infrastructure.database.config import (
    PersistenceError,
    load_config,
    parse_config,
    reject_ambient,
)


def config_values(target="test"):
    passwords = [character * 64 for character in "abc"]
    port, peer = (55433, 55432) if target == "test" else (55432, 55433)
    values = {
        "TARGET": target,
        "NAMESPACE": "unit",
        "INSTANCE_ID": str(uuid4()),
        "PORT": str(port),
        "PEER_PORT": str(peer),
        "ADMIN_PASSWORD": passwords[0],
        "MIGRATOR_PASSWORD": passwords[1],
        "APP_PASSWORD": passwords[2],
    }
    for key, role, password in (
        ("DATABASE_URL", "app", passwords[2]),
        ("MIGRATION_DATABASE_URL", "migrator", passwords[1]),
    ):
        values[key] = URL.create(
            "postgresql+psycopg",
            username=f"pitlab_{target}_{role}",
            password=password,
            host="127.0.0.1",
            port=port,
            database=f"pitlab_{target}",
        ).render_as_string(hide_password=False)
    return values


def test_config_repr_and_explicit_target_file(tmp_path):
    values = config_values()
    path = tmp_path / ".env.test.local"
    path.write_text("\n".join(f"{k}={v}" for k, v in values.items()))
    path.chmod(0o600)
    config = load_config("test", tmp_path, environ={})
    assert config.database == "pitlab_test"
    assert config.marker.startswith("pitlab:test:unit:")
    for value in (values["APP_PASSWORD"], values["DATABASE_URL"], values["MIGRATOR_PASSWORD"]):
        assert value not in repr(config)
    with pytest.raises(PersistenceError, match="unavailable"):
        load_config("dev", tmp_path, environ={})


@pytest.mark.parametrize(
    "key,value",
    [
        ("TARGET", "dev"),
        ("NAMESPACE", "../foreign"),
        ("INSTANCE_ID", "not-a-uuid"),
        ("PORT", "55432"),
        ("PORT", "invalid"),
        ("PEER_PORT", "55433"),
        ("APP_PASSWORD", "a" * 64),
        ("DATABASE_URL", "malformed-secret"),
        ("DATABASE_URL", config_values("dev")["DATABASE_URL"]),
    ],
)
def test_config_negatives_are_redacted(key, value):
    values = config_values()
    values[key] = value
    with pytest.raises(PersistenceError) as caught:
        parse_config(values, "test")
    assert values["ADMIN_PASSWORD"] not in str(caught.value)
    assert values["DATABASE_URL"] not in str(caught.value)


@pytest.mark.parametrize(
    "change",
    [
        {"host": "localhost"},
        {"database": "pitlab_dev"},
        {"username": "pitlab_test_admin"},
        {"query": {"host": "127.0.0.1"}},
        {"drivername": "postgresql"},
        {"password": "wrong"},
    ],
)
def test_typed_config_rejects_route_and_role_changes(change):
    config = parse_config(config_values(), "test")
    with pytest.raises(PersistenceError):
        replace(config, runtime_url=config.runtime_url.set(**change))


@pytest.mark.parametrize("name", ["PGHOST", "PGSERVICE", "COMPOSE_FILE", "PITLAB_DATABASE_URL"])
def test_ambient_routing_rejected(name):
    with pytest.raises(PersistenceError, match="ambient"):
        reject_ambient({name: "secret"})


def test_strict_reader_and_permissions(tmp_path):
    path = tmp_path / ".env.test.local"
    values = config_values()
    text = "\n".join(f"{k}={v}" for k, v in values.items())
    for addition in ("\nTARGET=test", "\nUNKNOWN=secret", "\nexport PGHOST=foreign"):
        path.write_text(text + addition)
        path.chmod(0o600)
        with pytest.raises(PersistenceError, match="Malformed"):
            load_config("test", tmp_path, environ={})
    path.write_text(text)
    path.chmod(0o644)
    with pytest.raises(PersistenceError, match="0600"):
        load_config("test", tmp_path, environ={})
    path.unlink()
    other = tmp_path / "other"
    other.write_text(text)
    other.chmod(0o600)
    path.symlink_to(other)
    with pytest.raises(PersistenceError, match="regular file"):
        load_config("test", tmp_path, environ={})
    assert os.stat(other).st_mode & 0o777 == 0o600
