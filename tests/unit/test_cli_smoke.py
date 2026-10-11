"""Verify the installed console entry point without external services."""

import shutil
import subprocess
from importlib.metadata import version
from pathlib import Path


def _run_cli(option: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("pitlab")
    assert executable is not None, "pitlab must be installed in the uv-managed environment"
    return subprocess.run(
        [executable, option],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=10,
        shell=False,
        check=False,
    )


def test_help(tmp_path: Path) -> None:
    result = _run_cli("--help", tmp_path)

    assert result.returncode == 0, result.stderr
    assert "usage: pitlab" in result.stdout
    assert "--help" in result.stdout
    assert "--version" in result.stdout
    assert result.stderr == ""
    assert list(tmp_path.iterdir()) == []


def test_version(tmp_path: Path) -> None:
    result = _run_cli("--version", tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == version("pit-research-lab")
    assert result.stderr == ""
    assert list(tmp_path.iterdir()) == []


def test_unknown_argument(tmp_path: Path) -> None:
    result = _run_cli("--unknown-option", tmp_path)

    assert result.returncode == 2, result.stderr
    assert result.stdout == ""
    assert "usage: pitlab" in result.stderr
    assert "error: unrecognized arguments: --unknown-option" in result.stderr
    assert list(tmp_path.iterdir()) == []
