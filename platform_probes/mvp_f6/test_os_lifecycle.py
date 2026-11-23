"""Future physical contracts only. NOT_RUN / NOT_AUTHORIZED under OAA-02.

Outside default testpaths. Do not import/collect/run this file in this task.
No environment or supplied hash can activate a case. Failure is never a skip.
"""

import pytest

pytestmark = pytest.mark.integration

CONTRACTS = {
    "P01": {"starts": 4, "spawn_attempts": 0, "oracle": "CONTENDED_UNTIL_LAST_CLOSE"},
    "P02": {"starts": 4, "spawn_attempts": 1, "oracle": "ORIGINAL_EXIT0_HELD"},
    "P03": {"starts": 4, "spawn_attempts": 1, "oracle": "ORIGINAL_EXIT7_IMMUTABLE_CAUSE"},
    "P04": {"starts": 3, "spawn_attempts": 0, "oracle": "COMMIT_UNKNOWN_NO_GO"},
    "P05": {"starts": 4, "spawn_attempts": 1, "oracle": "NO_CHILD_NO_WAIT_NO_Q_HELD"},
    "P06": {"starts": 3, "spawn_attempts": 0, "oracle": "PREARM_AUTHORITY_REFUSED"},
    "F00": {"starts": 2, "spawn_attempts": 1, "oracle": "WATCHDOG_DIRECT_SIGNAL_WAIT"},
    "F01": {"starts": 4, "spawn_attempts": 1, "oracle": "ORIGINAL_L_SIGNAL_WAIT"},
}


def _future_case(case):
    # No issuer/provider is implemented or executed in this source-only scope.
    # Never replace this with an environment flag or JSON/hash-shaped approval.
    raise PermissionError("PHYSICAL_OS_EXECUTION_NOT_AUTHORIZED:" + case)


def _assert_actual_evidence(case, evidence):
    """Future positive oracle, never called on modeled/SQL fixture results."""
    contract = CONTRACTS[case]
    assert evidence["case"] == case and evidence["evidence_class"] == "PHYSICAL_HELPER"
    assert evidence["original_kernel_custody_verified"] is True
    assert evidence["role_starts"] <= contract["starts"]
    assert evidence["spawn_attempts"] == contract["spawn_attempts"]
    assert evidence["oracle"] == contract["oracle"]
    assert evidence["cleanup_verified"] is True and evidence["slot_disposed"] is False
    assert evidence["native_started"] is False and evidence["public_success"] is False
    if case == "P02":
        assert evidence["wait_kind"] == "EXIT" and evidence["exit_code"] == 0
        assert evidence["arm_count"] == 1 and evidence["child_fd_isolation_verified"] is True
    if case == "P03":
        assert evidence["wait_kind"] == "EXIT" and evidence["exit_code"] == 7
        assert evidence["first_failure"] == "CHILD_NONZERO_EXIT"
    if case == "P05":
        assert evidence["child_rows"] == evidence["wait_rows"] == evidence["quiescence_rows"] == 0
    if case in ("F00", "F01"):
        assert evidence["separate_signal_permit_verified"] is True
        assert evidence["wait_kind"] == "SIGNAL" and evidence["signal_number"] == 15


def test_installation_and_job_lease_contention():
    _future_case("P01")


def test_registered_exit_zero_fd_isolation_and_one_use():
    _future_case("P02")


def test_registered_exit_seven_preserves_first_failure():
    _future_case("P03")


def test_arm_commit_lost_ack_forbids_spawn():
    _future_case("P04")


def test_spawn_without_registration_stays_held():
    _future_case("P05")


def test_private_channel_and_prearm_authority_failure_refuse():
    _future_case("P06")


def test_watchdog_direct_child_signal_safety():
    _future_case("F00")


def test_original_launcher_signal_wait():
    _future_case("F01")
