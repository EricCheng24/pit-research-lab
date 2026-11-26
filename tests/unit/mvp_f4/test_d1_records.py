from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pit_research_lab.mvp.f4 import d1_records as records
from pit_research_lab.mvp.f4 import d1_store
from pit_research_lab.mvp.f4.d1_profile import ISSUER, REVENUE, Refusal, digest, json_bytes

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "mvp_f4_d1"


def test_attempt_lock_is_first_and_uses_the_same_scoped_execution_grant():
    db = Mock()
    target = Mock(role="migrator", marker="fictional-test-instance")
    target.account.side_effect = lambda role: f"test_{role}"
    lock = "SELECT public.f4_d1_lock_attempt()"
    payload = {"attempt": "fixture-attempt"}
    row = {
        "id": payload["attempt"],
        "receipt": json_bytes(payload),
        "receipt_sha": digest("receipt", payload),
        "request_sha": digest("receipt", {"profile": "p", "input": "n", "sha": "s"}),
        "deployment": target.marker,
        "started_at": datetime.now(UTC),
    }
    with (
        patch.object(d1_store, "is_active", return_value=True),
        patch.object(d1_store, "started", return_value=row),
    ):
        assert d1_store.begin(db, payload["attempt"], REVENUE, "p", "n", "s", target.marker) == (
            row,
            False,
        )
        db.execute.assert_called_once_with(lock)
        db.reset_mock()
        assert d1_store.finish(db, target, row, result="INTERRUPTED") == payload
        db.execute.assert_called_once_with(lock)

    for available, clause in ((True, "GRANT"), (False, "REVOKE")):
        db.reset_mock()
        d1_store.grants(db, target, available=available)
        statements = [args[0].as_string() for args, _ in db.execute.call_args_list]
        direction = "TO" if available else "FROM"
        assert [s for s in statements if "FUNCTION" in s] == [
            f'{clause} EXECUTE ON FUNCTION public.f4_d1_lock_attempt() {direction} "test_publisher"'
        ]
        publisher = [s for s in statements if s.endswith('"test_publisher"')]
        assert {s.split()[1] for s in publisher} == {"SELECT", "USAGE", "INSERT", "EXECUTE"}
        inserts = next(s for s in publisher if s.split()[1] == "INSERT")
        assert "f4_d1_attempt" in inserts and "f4_d1_profile" not in inserts


def test_declared_fixture_amounts_and_row_locators():
    issuer = records.classified(ISSUER, (FIXTURES / "issuer_fixture.csv").read_bytes())
    assert records.counts(issuer) == {
        "total": 3,
        "accepted": 2,
        "rejected": 0,
        "excluded": 1,
    }
    bindings = [
        tuple(i[k] for k in ("code", "key", "name"))
        for i in (r["issuer"] for r in issuer if "issuer" in r)
    ]
    assert bindings[0][0] == "0001"
    source = (FIXTURES / "revenue_fixture.csv").read_bytes()
    results = records.classified(REVENUE, source, bindings)
    assert records.counts(results) == {
        "total": 4,
        "accepted": 3,
        "rejected": 0,
        "excluded": 1,
    }
    assert [r["row_no"] for r in results] == [1, 2, 3, 4]
    assert [r["assertion"]["body"]["value"] for r in results[:3]] == [
        "0",
        "-12.5",
        None,
    ]
    assert results[2]["assertion"]["body"]["reason"] == "DECLARED_MISSING"
    off = records.classified(REVENUE, source.replace(b"2025-01", b"2025-13"), bindings)
    assert off[0]["reason"] == "INVALID_PERIOD"
    conflicting = bindings + [("0001", "FIC-OTHER", "Fictional Other")]
    assert records.classified(REVENUE, source, conflicting)[0]["reason"] == "UNRESOLVED_ISSUER"


@pytest.mark.parametrize("token", ["", "+1", "01", "1,000", "1e2", "NaN", "0.000000001", "1" * 31])
def test_reject_unsupported_numeric_grammar(token):
    with pytest.raises(Refusal, match="INVALID_AMOUNT"):
        records.amount(token)


def test_stable_exact_identity_and_numeric_bounds():
    assert records.amount("9" * 30 + ".12345678") == "9" * 30 + ".12345678"
    assert records.amount("-0.00000000") == "0"
    assert records.month("2025-12") == ("2025-12-01", "2026-01-01")
    row = records.rows(REVENUE, (FIXTURES / "revenue_fixture.csv").read_bytes())[0]
    original = records.assertion(row)
    assert original == records.assertion(row | {"amount": "-0.00"})
    for change in ({"basis": "standalone"}, {"unit": "TWD"}, {"key": "FIC-OTHER"}):
        new = records.assertion(row | change)
        assert new["subject_sha"] != original["subject_sha"]
        assert new["version_sha"] != original["version_sha"]
    new = records.assertion(row | {"amount": "42.0"})
    assert new["subject_sha"] == original["subject_sha"]
    assert new["version_sha"] != original["version_sha"]


def test_reject_invalid_envelopes():
    raw = (FIXTURES / "revenue_fixture.csv").read_bytes()
    for payload in (
        b"\xff",
        b"\xef\xbb\xbf" + raw,
        raw.replace(b"amount,report_date", b"amount,amount"),
        raw.replace(b"SYNTHETIC_F4_D1", b"OD-02"),
        raw + b"too,short\n",
    ):
        with pytest.raises(Refusal):
            records.classified(REVENUE, payload)


def test_fixture_artifact_reconciliation_rejects_plausible_substitutions():
    from decimal import Decimal

    from pit_research_lab.mvp.f4.d1_backup import exact_children
    from pit_research_lab.mvp.f4.d1_profile import json_bytes

    declared = (FIXTURES / "revenue_fixture.csv").read_bytes()
    issuer_bytes = (FIXTURES / "issuer_fixture.csv").read_bytes()
    issuers = records.classified(ISSUER, issuer_bytes)
    history = [(i["code"], i["key"], i["name"]) for item in issuers if (i := item.get("issuer"))]
    expected = records.classified(REVENUE, declared, history)
    rows = [{k: r[k] for k in ("row_no", "status", "reason")} for r in expected]

    def canonical_rows(source):
        result = []
        for item in records.classified(REVENUE, source, history):
            if item["status"] != "ACCEPTED":
                continue
            a = item["assertion"]
            body = a["body"]
            subject = body["subject"]
            result.append(
                {
                    "row_no": item["row_no"],
                    **{
                        k: a[k]
                        for k in (
                            "issuer_key",
                            "field",
                            "version_sha",
                            "subject_sha",
                            "report_date",
                        )
                    },
                    **{
                        k: subject[k]
                        for k in (
                            "period_start",
                            "period_end_exclusive",
                            "basis",
                            "currency",
                            "unit",
                        )
                    },
                    "body": json_bytes(body),
                    "subject_body": json_bytes(subject),
                    "amount": Decimal(body["value"]) if body["value"] is not None else None,
                    "state": body["state"],
                }
            )
        return result

    actual = canonical_rows(declared)
    exact_children(expected, rows, [], actual)
    wrong_body = canonical_rows(declared.replace(b",0,2025-02-09", b",42,2025-02-09"))
    assert (
        len(wrong_body) == len(actual) and wrong_body[0]["version_sha"] != actual[0]["version_sha"]
    )
    for corrupt in (
        wrong_body,
        [actual[0] | {"amount": Decimal("42")}, *actual[1:]],
        [actual[1] | {"row_no": 1}, actual[0] | {"row_no": 2}, actual[2]],
        actual[:-1],
        [*actual, actual[-1] | {"row_no": 4}],
    ):
        with pytest.raises(Refusal, match="ARTIFACT_ASSERTION_OCCURRENCE_MISMATCH"):
            exact_children(expected, rows, [], corrupt)
    with pytest.raises(Refusal, match="ARTIFACT_ISSUER_OCCURRENCE_MISMATCH"):
        exact_children(expected, rows, [issuers[0]["issuer"]], actual)
    with pytest.raises(Refusal, match="ARTIFACT_ROW_CLASSIFICATION_MISMATCH"):
        exact_children(expected, rows[:-1], [], actual)
