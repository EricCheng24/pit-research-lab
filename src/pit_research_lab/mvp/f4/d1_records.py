"""Exact canonical values and strict, visibly fictional CSV mapping."""

import csv
import io
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from .d1_profile import (
    COLUMNS,
    ISSUER,
    MAX_ROWS,
    NAMESPACE,
    REVENUE,
    Refusal,
    digest,
    require,
)

MAX_FIELD = 256
VALUE = re.compile(r"-?(?:0|[1-9][0-9]{0,29})(?:\.[0-9]{1,8})?")


def amount(token: str) -> str:
    require(VALUE.fullmatch(token), "INVALID_AMOUNT")
    value = Decimal(token)
    if value == 0:
        return "0"
    plain = format(value, "f")
    return plain.rstrip("0").rstrip(".") if "." in plain else plain


def iso_date(token: str) -> date:
    try:
        result = date.fromisoformat(token)
    except ValueError:
        raise Refusal("INVALID_DATE") from None
    require(result.isoformat() == token and 2000 <= result.year <= 2099, "INVALID_DATE")
    return result


def month(token: str) -> tuple[str, str]:
    require(re.fullmatch(r"20[0-9]{2}-(?:0[1-9]|1[0-2])", token), "INVALID_PERIOD")
    start = iso_date(token + "-01")
    end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return start.isoformat(), end.isoformat()


def rows(profile: str, raw: bytes) -> list[dict[str, str]]:
    require(profile in COLUMNS, "UNKNOWN_FIXTURE_PROFILE")
    try:
        reader = csv.reader(io.StringIO(raw.decode("utf-8"), newline=""), strict=True)
        columns = COLUMNS[profile]
        require(tuple(next(reader, [])) == columns, "WRONG_CSV_HEADER")
        result: list[dict[str, str]] = []
        for row in reader:
            require(len(result) < MAX_ROWS and len(row) == len(columns), "INVALID_CSV_SHAPE")
            require(
                all(len(v) <= MAX_FIELD and v.isprintable() or v == "" for v in row),
                "INVALID_CSV_FIELD",
            )
            value = dict(zip(columns, row, strict=True))
            require(value["namespace"] == NAMESPACE, "NON_FIXTURE_FILE")
            result.append(value)
        require(bool(result), "EMPTY_FIXTURE")
        return result
    except (UnicodeError, csv.Error):
        raise Refusal("INVALID_CSV") from None


def identity(row: dict[str, str]) -> tuple[str, str, str]:
    require(re.fullmatch(r"00[0-9]{2}", row["code"]), "INVALID_INSTRUMENT_CODE")
    require(re.fullmatch(r"FIC-[A-Z]{2,12}", row["key"]), "INVALID_FIXTURE_ISSUER_KEY")
    require(re.fullmatch(r"Fictional [A-Za-z ]{2,48}", row["name"]), "INVALID_FIXTURE_NAME")
    return row["code"], row["key"], row["name"]


def assertion(row: dict[str, str]) -> dict[str, Any]:
    _, key, _ = identity(row)
    start, end = month(row["period"])
    require(row["basis"] in {"consolidated", "standalone"}, "INVALID_BASIS")
    require(
        row["currency"] == "TWD" and row["unit"] in {"TWD", "TWD_THOUSANDS"},
        "INVALID_CURRENCY_UNIT",
    )
    subject = {
        "issuer": f"{NAMESPACE}/{key}",
        "market": "FICTIONAL_TWSE_STYLE",
        "identity_namespace": NAMESPACE,
        "metric": "MONTHLY_OPERATING_REVENUE",
        "period_start": start,
        "period_end_exclusive": end,
        "basis": row["basis"],
        "currency": row["currency"],
        "unit": row["unit"],
    }
    missing = row["amount"] == "MISSING"
    body = {
        "subject": subject,
        "value": None if missing else amount(row["amount"]),
        "state": "MISSING" if missing else "PRESENT",
        "reason": "DECLARED_MISSING" if missing else None,
        "semantic_version": "f4-d1-canon-v1",
    }
    return {
        "subject_sha": digest("subject", subject),
        "version_sha": digest("assertion", body),
        "body": body,
    }


def classified(
    profile: str, raw: bytes, bindings: Iterable[tuple[str, str, str]] = ()
) -> list[dict[str, Any]]:
    values = rows(profile, raw)
    identities: dict[str, set[tuple[str, str]]] = defaultdict(set)
    key_codes: dict[str, set[str]] = defaultdict(set)
    for code, key, name in bindings:
        identities[code].add((key, name))
        key_codes[key].add(code)
    if profile == ISSUER:
        for row in values:
            try:
                code, key, name = identity(row)
                iso_date(row["listed_date"])
                if row["sector"] not in {"technology", "services"}:
                    continue
            except Refusal:
                continue
            if code in {"0001", "0002"}:
                identities[code].add((key, name))
                key_codes[key].add(code)

    results = []
    for ordinal, row in enumerate(values, start=1):
        result: dict[str, Any] = {"row_no": ordinal}
        try:
            code, key, name = identity(row)
            if code not in {"0001", "0002"}:
                results.append(result | {"status": "OUT_OF_SCOPE", "reason": "FIXTURE_SUBSET"})
                continue
            require(
                identities.get(code) == {(key, name)} and key_codes.get(key) == {code},
                "UNRESOLVED_ISSUER",
            )
            if profile == ISSUER:
                require(row["sector"] in {"technology", "services"}, "INVALID_SECTOR")
                result["issuer"] = {
                    "key": key,
                    "code": code,
                    "name": name,
                    "sector": row["sector"],
                    "listed_date": iso_date(row["listed_date"]).isoformat(),
                }
            elif profile == REVENUE:
                result["assertion"] = assertion(row) | {
                    "issuer_key": key,
                    "field": "amount",
                    "report_date": iso_date(row["report_date"]).isoformat(),
                }
            result["status"], result["reason"] = "ACCEPTED", None
        except Refusal as error:
            result["status"], result["reason"] = "REJECTED", str(error)
        results.append(result)
    return results


def counts(results: list[dict[str, Any]]) -> dict[str, int]:
    states = Counter(row["status"] for row in results)
    return {
        "total": len(results),
        "accepted": states["ACCEPTED"],
        "rejected": states["REJECTED"],
        "excluded": states["OUT_OF_SCOPE"],
    }
