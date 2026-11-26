from datetime import datetime
from unittest.mock import Mock

import pytest

from pit_research_lab.mvp.f4 import d1, d1_profile


def test_acquire_refuses_before_configuration_or_transport(monkeypatch, capsys):
    forbidden = Mock(side_effect=AssertionError("I/O reached"))
    monkeypatch.setattr(d1, "load_target", forbidden)
    monkeypatch.setattr(d1, "connect", forbidden)
    monkeypatch.setattr("socket.getaddrinfo", forbidden)
    assert d1.main(["acquire"]) == 2
    forbidden.assert_not_called()
    assert capsys.readouterr().err == '{"refused": "REAL_ACQUISITION_NOT_GRANTED"}\n'


def test_profile_and_config_are_closed(tmp_path):
    private = tmp_path / "target"
    private.mkdir(mode=0o700)
    path = private / "config.json"
    body = {
        "mode": "SYNTHETIC_ONLY",
        "target": "test",
        "namespace": "f4d1test00001",
        "instance": "073debac-57a7-42fe-b7df-ab0cfdfde6c0",
        "port": 56321,
        "role": "custodian",
        "password": "a" * 64,
        "root": str(private),
        "profiles": {},
        "inputs": {},
    }

    def write(item):
        path.write_bytes(d1_profile.json_bytes(item))
        path.chmod(0o600)

    write(body)
    target = d1_profile.load_target(path)
    assert target.user == "pitlab_test_f4_custodian"
    for changes in (
        {"mode": "REAL"},
        {"scope": "ALL"},
        {"namespace": "existingf1"},
        {"port": 5432},
        {"role": "app"},
        {"profiles": {"OD-01": "a" * 64}},
        {"profiles": {d1_profile.ISSUER: "a" * 64}},
    ):
        write(body | changes)
        with pytest.raises(d1_profile.Refusal):
            d1_profile.load_target(path)
    with pytest.raises(d1_profile.Refusal, match="UNKNOWN_FIXTURE_PROFILE"):
        target.pin("OD-01", "fixture.csv")
    with pytest.raises(d1_profile.Refusal, match="EXPORT_AUDIENCE_NOT_GRANTED"):
        d1.export(target, "PUBLIC", "nothing")


def test_canonical_codec_preserves_declared_fields():
    assert d1_profile.json_bytes({"z": None, "a": "測試"}) == '{"a":"測試","z":null}'.encode()
    assert d1_profile.digest("subject", {}) != d1_profile.digest("assertion", {})
    with pytest.raises(d1_profile.Refusal, match="INVALID_JSON"):
        d1_profile.decode(b'{"a":1,"a":2}')
    with pytest.raises(d1_profile.Refusal, match="CLOCK_ZONE_REQUIRED"):
        d1_profile.timestamp(datetime(2026, 11, 25))
