"""Independent IC1 synthetic fixtures; no Golden inputs or prior test factories."""

from pathlib import Path

import pytest

from pit_research_lab.domain.market_source_slice import observe_ic1_code


@pytest.fixture(scope="module")
def code():
    return observe_ic1_code(Path(__file__).resolve().parents[3])
