"""RS2 independent invented fixtures, no real source reads or prior test factories."""

from pathlib import Path

import pytest

from pit_research_lab.domain.issuer_html_slice import observe_html_code


@pytest.fixture(scope="module")
def html_code():
    return observe_html_code(Path(__file__).resolve().parents[3])
