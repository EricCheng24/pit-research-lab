"""Verify that the package imports and its installed metadata is available."""

import importlib
import tomllib
from importlib.metadata import distribution
from pathlib import Path


def test_installed_package() -> None:
    package = importlib.import_module("pit_research_lab")
    installed = distribution("pit-research-lab")
    with (Path(__file__).resolve().parents[2] / "pyproject.toml").open("rb") as config_file:
        project = tomllib.load(config_file)["project"]

    assert package.__name__ == "pit_research_lab"
    assert installed.metadata["Name"] == "pit-research-lab"
    assert installed.version == project["version"]
