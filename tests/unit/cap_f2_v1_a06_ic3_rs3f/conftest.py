"""Explicit accepted synthetic fixture import; no financial-folder discovery."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def rs2_fixture():
    path = Path(__file__).absolute().parents[1] / "cap_f2_v1_a06_ic3_rs2/rs2_inputs.py"
    spec = importlib.util.spec_from_file_location("rs3f_accepted_synthetic", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
