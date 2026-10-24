"""IC3 isolated synthetic fixtures; no owner source or external support discovery."""

from pathlib import Path

import pytest

from pit_research_lab.domain.financial_semantics_slice import observe_ic3_code


@pytest.fixture(scope="module")
def ic3_code():
    return observe_ic3_code(Path(__file__).resolve().parents[3])
