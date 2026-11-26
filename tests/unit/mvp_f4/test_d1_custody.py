import os

import pytest

from pit_research_lab.mvp.f4.d1_backup import OwnerClient
from pit_research_lab.mvp.f4.d1_custody import (
    blob_path,
    custody_lock,
    put_blob,
    read_blob,
)
from pit_research_lab.mvp.f4.d1_profile import Refusal, Target, private_read


def test_exact_blob_reuse_and_no_overwrite(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    payload = b"fictional\r\npayload\n"
    seen = put_blob(root, payload)
    assert put_blob(root, payload) == seen
    assert read_blob(root, *seen) == payload
    path = blob_path(root, seen[0])
    corrupt = b"x" * seen[1]
    path.write_bytes(corrupt)
    with pytest.raises(Refusal, match="ARTIFACT_INTEGRITY_FAILURE"):
        put_blob(root, payload)
    assert path.read_bytes() == corrupt
    path.unlink()
    with pytest.raises(Refusal, match="MISSING_OR_UNSAFE_ARTIFACT"):
        read_blob(root, *seen)
    with pytest.raises(Refusal, match="INVALID_ARTIFACT_DIGEST"):
        blob_path(root, "../outside")


def test_private_paths_and_hardlinks(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    file = root / "fixture.csv"
    file.write_bytes(b"fictional")
    file.chmod(0o600)
    linked = root / "linked.csv"
    linked.symlink_to(file)
    with pytest.raises(OSError):
        private_read(linked, 100)
    linked.unlink()
    os.link(file, linked)
    with pytest.raises(Refusal, match="UNSAFE_PRIVATE_FILE"):
        private_read(file, 100)
    linked.unlink()
    with pytest.raises(Refusal, match="UNSAFE_PRIVATE_FILE"):
        private_read(file, 1)


def test_custody_lock_is_bounded(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    with (
        custody_lock(root),
        pytest.raises(Refusal, match="CUSTODY_LOCK_TIMEOUT"),
        custody_lock(root, budget=0),
    ):
        pytest.fail("concurrent lock allowed")


def test_container_adapter_refuses_ordinary_roles_and_selectors(tmp_path):
    target = Target("test", "f4d1test0001", "fixture", 56321, "reader", "a" * 64, tmp_path, {}, {})
    with pytest.raises(Refusal, match="MAINTENANCE_ROLE_REQUIRED"):
        OwnerClient(target, "a" * 64)
    maintainer = Target(
        "test", "f4d1test0001", "fixture", 56321, "migrator", "a" * 64, tmp_path, {}, {}
    )
    with pytest.raises(Refusal, match="EXACT_CONTAINER_ID_REQUIRED"):
        OwnerClient(maintainer, "another-container")
