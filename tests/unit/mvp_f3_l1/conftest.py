import pytest

from pit_research_lab.mvp.f2.research_panel import load_panel
from pit_research_lab.mvp.f3_l1.contracts import FOLDS, Protocol
from pit_research_lab.mvp.f3_l1.experiment import fit, training_set


@pytest.fixture(scope="session")
def panel():
    return load_panel()


@pytest.fixture(scope="session")
def protocol():
    return Protocol()


@pytest.fixture(scope="session")
def training(panel, protocol):
    return training_set(panel, FOLDS[0], protocol)


@pytest.fixture(scope="session")
def state(training, protocol):
    return fit(training, protocol)
