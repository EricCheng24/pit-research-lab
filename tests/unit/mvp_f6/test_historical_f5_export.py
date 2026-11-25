"""Hermetic synthetic publication and refusal tests."""

from __future__ import annotations

import ast
import hashlib
import os
import stat
from dataclasses import replace
from pathlib import Path

import pytest
from test_historical_f5_projection import synthetic_history

from pit_research_lab.mvp.f6.historical_f5 import __main__ as entry
from pit_research_lab.mvp.f6.historical_f5 import archive

SYNTHETIC_BYTES = b"synthetic-only sealed test input, not a research archive"


def _write(path: Path, contents: bytes) -> None:
    path.write_bytes(contents)
    path.chmod(0o600)


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    application = tmp_path / ".local/share/pit-research-lab/f6-u1"
    source = application / "custody"
    snapshots = application / "snapshots"
    source.mkdir(mode=0o700, parents=True)
    snapshots.mkdir(mode=0o700)
    application.chmod(0o700)
    release = replace(
        archive._RELEASE,
        acceptance_ref="SYNTHETIC-TEST-ONLY",
        archive_sha256=hashlib.sha256(SYNTHETIC_BYTES).hexdigest(),
        size=len(SYNTHETIC_BYTES),
    )
    monkeypatch.setattr(archive, "_RELEASE", release)
    archive_file = source / release.basename
    _write(archive_file, SYNTHETIC_BYTES)

    def only_synthetic(
        contents: bytes, selected: archive.Release, budget: archive.Budget
    ) -> archive.Historical:
        assert contents == SYNTHETIC_BYTES and selected == release
        budget.check()
        return replace(synthetic_history(), release=release)

    monkeypatch.setattr(archive, "_inspect", only_synthetic)
    return tmp_path, archive_file, snapshots


def _locate(snapshot_root: Path, delivery: entry.Delivery) -> Path:
    relative = delivery.line.split()[-1]
    path = snapshot_root / relative
    assert path.is_file() and path.name == "index.html" and path.parent.parent == snapshot_root
    return path


@pytest.mark.parametrize(
    ("condition", "reason", "code"),
    [
        ("missing", "ARCHIVE_MISSING", 2),
        ("mutated", "ARCHIVE_PIN", 3),
        ("withheld", "EDITION_WITHHELD", 2),
        ("bad-marker", "UNSAFE_INPUT", 3),
    ],
)
def test_H07_new_refusal_leaves_valid_snapshot_dated_and_unchanged(
    isolated: tuple[Path, Path, Path], condition: str, reason: str, code: int
) -> None:
    home, archive_path, output = isolated
    original = entry._export(home)
    assert original.code == 0 and original.line.startswith("AVAILABLE_HISTORICAL snapshot-")
    ready = _locate(output, original)
    initial = ready.read_bytes()
    assert "dated file" in initial.decode()
    assert stat.S_IMODE(ready.stat().st_mode) == 0o600
    assert stat.S_IMODE(ready.parent.stat().st_mode) == 0o700
    if condition == "missing":
        archive_path.unlink()
    elif condition == "mutated":
        _write(archive_path, b"!" + SYNTHETIC_BYTES[1:])
    else:
        _write(
            archive_path.with_name("WITHHOLD"),
            b"WITHHELD\n" if condition == "withheld" else b"ALLOWED\n",
        )
    refusal = entry._export(home)
    assert refusal.code == code and reason in refusal.line and " REFUSAL_PAGE " in refusal.line
    page = _locate(output, refusal)
    assert page != ready and ready.read_bytes() == initial
    html = page.read_text()
    assert reason in html and 'id="comparison"' not in html
    assert str(archive_path) not in html
    assert not (output / "latest").exists()


@pytest.mark.parametrize("mechanism", ["write", "rename"])
def test_H06_H07_publish_fault_produces_no_locator(
    isolated: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, mechanism: str
) -> None:
    home, _, output = isolated
    prior = _locate(output, entry._export(home))
    before = prior.read_bytes()

    def failure(*args: object, **kwargs: object) -> int:
        raise OSError("private file path hidden")

    monkeypatch.setattr(os, mechanism, failure)
    result = entry._export(home)
    assert result == entry.Delivery(4, "FAILED OUTPUT_IO")
    assert prior.read_bytes() == before
    assert list(output.glob("*/index.html")) == [prior]
    assert not list(output.glob("*/page.part"))


def test_H07_terminal_delivery_fault_cannot_reuse_prior_page(
    isolated: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    home, _, output = isolated
    prior = _locate(output, entry._export(home))
    before = prior.read_bytes()
    current = entry._export(home)
    assert _locate(output, current) != prior

    def fail_write(fd: int, data: bytes) -> int:
        raise BrokenPipeError("internal")

    monkeypatch.setattr(os, "write", fail_write)
    assert entry._deliver(current) == 4
    assert prior.read_bytes() == before


def test_H06_audit_detects_input_replacement_before_rename(
    isolated: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    home, archive_path, output = isolated
    real_render = entry.render.static_html

    def replace_archived_file(view: object) -> bytes:
        body = real_render(view)
        if isinstance(view, dict) and view["status"] == "AVAILABLE_HISTORICAL":
            temporary = archive_path.with_name("synthetic.replacement")
            _write(temporary, SYNTHETIC_BYTES)
            temporary.replace(archive_path)
        return body

    monkeypatch.setattr(entry.render, "static_html", replace_archived_file)
    result = entry._export(home)
    assert result.code == 3 and result.line.startswith("FAILED INPUT_CHANGED REFUSAL_PAGE")
    assert "PASSED_NO_DISCLOSURE" in _locate(output, result).read_text()
    assert len(list(output.glob("*/index.html"))) == 1
    assert not list(output.glob("*/page.part"))


@pytest.mark.parametrize(
    "path_kind", ["link", "hardlink", "fifo", "writable-archive", "marker-link"]
)
def test_H06_unsafe_input_never_returns_a_book(
    isolated: tuple[Path, Path, Path],
    path_kind: str,
) -> None:
    home, source, output = isolated
    target = source.with_name("not-an-input")
    if path_kind in ("hardlink", "link"):
        source.rename(target)
        if path_kind == "hardlink":
            source.hardlink_to(target)
        else:
            source.symlink_to(target)
    elif path_kind == "fifo":
        source.unlink()
        os.mkfifo(source, mode=0o600)
    elif path_kind == "marker-link":
        _write(target, b"WITHHELD\n")
        source.with_name("WITHHOLD").symlink_to(target)
    else:
        source.chmod(0o644)
    result = entry._export(home)
    assert result.line.startswith("FAILED UNSAFE_INPUT REFUSAL_PAGE") and result.code == 3
    assert "Three costed policies" not in _locate(output, result).read_text()


def test_H06_output_alias_and_nonprivate_root_refuse(
    isolated: tuple[Path, Path, Path],
) -> None:
    home, source, output = isolated
    output.chmod(0o755)
    assert entry._export(home) == entry.Delivery(4, "FAILED UNSAFE_OUTPUT")
    output.rmdir()
    output.symlink_to(source.parent, target_is_directory=True)
    assert entry._export(home) == entry.Delivery(4, "FAILED UNSAFE_OUTPUT")


@pytest.mark.parametrize("option", ["--archive", "--edition", "--upload", "--status", "--hash"])
def test_H06_no_operator_path_input_or_success_injection(
    capfd: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    option: str,
) -> None:
    def never_called() -> Path:
        pytest.fail("invalid arguments touched custody")

    monkeypatch.setattr(entry.archive, "account_home", never_called)
    assert entry.main([option, "/private/forbidden"]) == 2
    out, err = capfd.readouterr()
    assert not out and err == "UNAVAILABLE INVALID_INVOCATION\n"


def test_H08_runtime_imports_and_privileged_io_not_in_source() -> None:
    folder = Path(archive.__file__).parent
    allowed = {
        "__future__",
        "typing",
        "collections",
        "collections.abc",
        "contextlib",
        "dataclasses",
        "datetime",
        "decimal",
        "hashlib",
        "html",
        "json",
        "math",
        "os",
        "pathlib",
        "pwd",
        "re",
        "stat",
        "struct",
        "sys",
        "time",
        "unicodedata",
        "uuid",
        "zipfile",
        "zlib",
    }
    launch = {"system", "fork", "spawn", "popen", "execv", "execve", "connect", "listen", "bind"}
    for name in archive.BUILD_FILES:
        parsed = ast.parse((folder / name).read_text())
        for node in ast.walk(parsed):
            if isinstance(node, ast.Import):
                assert {item.name for item in node.names} <= allowed
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 1 or node.module in allowed
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in launch
