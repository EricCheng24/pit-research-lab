"""A suite that omits/skips any required Stage V case cannot report success."""

import re

import pytest

REQUIRED = frozenset(
    {
        "RC01-T01",
        "RC01-T02",
        "RC01-T03",
        "RC02-T01",
        "RC02-T02",
        "RC02-T03",
        "RC03-T01",
        "RC03-T02",
        "RC03-T03",
        "RC04-T01",
        "RC04-T03",
        "RC05-T01",
    }
)
EXECUTED = {}
INVOLVED = False


def pytest_collection_finish(session):
    global INVOLVED
    INVOLVED = any("/mvp_research_vslice/" in str(item.path) for item in session.items)


def pytest_runtest_logreport(report):
    match = re.search(r"::test_(RC\d{2})_(T\d{2})_", report.nodeid)
    if match and "/mvp_research_vslice/" in report.nodeid:
        cid = "-".join(match.groups())
        if report.when == "call":
            EXECUTED[cid] = report.outcome


def pytest_sessionfinish(session, exitstatus):
    if INVOLVED and not session.config.option.collectonly:
        if set(EXECUTED) != REQUIRED or any(result != "passed" for result in EXECUTED.values()):
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
            reporter = session.config.pluginmanager.get_plugin("terminalreporter")
            if reporter:
                reporter.write_line("STAGE_V_EXECUTION_INCOMPLETE_OR_FAILED", red=True)
