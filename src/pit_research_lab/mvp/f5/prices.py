"""Pinned F5-only evaluation compatibility wrapper, not a supported F2 public API."""

import inspect
from dataclasses import dataclass
from datetime import date, timedelta
from hashlib import sha256
from typing import Any

from pit_research_lab.domain import contracts as d
from pit_research_lab.domain.asof_slice import observe_asof_code
from pit_research_lab.domain.pit_slice import evaluate_slice
from pit_research_lab.mvp.f2 import research_panel as f2

from .contracts import CALENDAR_SHA, CUTOFFS_SHA, ISSUERS, F5Error, digest, require
from .inputs import regular_bytes

COMPATIBILITY = {
    "__init__.py": "8121e022e7de092b4c79651137a4ccd89cd450ba910d65bb507b15781a52a5ff",
    "mvp/__init__.py": "ab478403cb3934afe997f7075d68cc62ffdfc0fe104d93975f80b6e62e93fb4b",
    "mvp/f2/__init__.py": "64166ad223f59222470849d4d7db6ee45e588d0525d6260df929d9696438caee",
    "mvp/f2/research_panel.py": "f32ef127801c704137d7272d340e5d79b5d2ca7f3157ce89553d0f870736314d",
    "mvp/research_vslice/__init__.py": "5d0550fa3297e0f5bb47829bbd9eb4a281939b0f37f3d2e4a25edf4bf12551ad",
    "mvp/research_vslice/contracts.py": "7aea50b6f2d9c658c228b42d15832d2fe9fa294b8aa0786304a2a4dc24dba1d7",
    "domain/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "domain/contracts.py": "d0a15387c919cdeafa7fc166952f9878487ae0337ec4ff92327b4c9ceb0a3bac",
    "domain/information.py": "fc1ed60a5fb3066553a18322f69df195429f7e83bd6dba774cb201d0f5c216d7",
    "domain/temporal.py": "09dfd6108c5ba2e117fb61ab4b9ce9254d342d1bf26fcfbf16d221b1d3f25dc7",
    "domain/pit_slice.py": "ab7ba2843035811e35e66f1a22eca51bc6d1b20d07248bb4f6097a76e898cc53",
    "domain/selection.py": "15ab6df10542df799a54a41e716c19fd13f52e3c738fba6e689b649c171f0202",
    "domain/asof_slice.py": "5500f53b0526b2e629ec844cef99b9445479900fc3e73ba98c9e48e2d30b2a31",
}


def check_compatibility() -> None:
    for name, expected in COMPATIBILITY.items():
        raw = regular_bytes(f2.ROOT / "src/pit_research_lab" / name)
        require(sha256(raw).hexdigest() == expected, "F2_COMPATIBILITY_PIN")
    require(
        tuple(inspect.signature(f2._notice).parameters)
        == ("row", "metric", "period", "subject_id", "amount", "unit")
        and tuple(inspect.signature(f2._context).parameters)
        == ("cutoff", "subject", "dataset", "code"),
        "F2_COMPATIBILITY_SIGNATURE",
    )


def pinned_body() -> dict[str, Any]:
    check_compatibility()
    raw, manifest = regular_bytes(f2.ROOT / f2.FIXTURE), regular_bytes(f2.ROOT / f2.MANIFEST)
    require(
        sha256(raw).hexdigest() == f2.SOURCE_SHA256
        and sha256(manifest).hexdigest() == f2.MANIFEST_SHA256,
        "SOURCE_PIN_MISMATCH",
    )
    body: dict[str, Any] = f2.decode(raw)
    require(
        digest(body["calendar"]) == CALENDAR_SHA
        and digest(body["cutoffs"]) == CUTOFFS_SHA
        and tuple(body["issuers"]) == ISSUERS,
        "CALENDAR_PIN",
    )
    return body


@dataclass(frozen=True, slots=True)
class QualifiedMark:
    issuer: str
    session: str
    close_time: str
    available_at: str
    value_ticks: int
    unit: str
    basis: str
    source_id: str
    version_id: str
    source_digest: str
    native_s1_state: str
    native_s2_state: str
    native_reason: str
    evaluation_asof: str
    invocation: str = "RUN"
    witness_kind: str = "PINNED_AUTHORED_DELIVERY"
    original_publication_state: str = "NOT_PROVIDED_IN_PRICE_ROW"
    diagnostic_only: bool = True
    trust: str = "NOT_TRUSTED_PIT_EVIDENCE"
    disposition: str = "INTEGRATED_PROVISIONAL"
    admission_eligible: bool = False
    source_authentication: str = "NOT_ESTABLISHED"
    non_if03: bool = True
    witness_time: str = ""
    native_s1_reason: str = "NONE"


class EvaluationPrices:
    """Only the evaluator owns this object. Constructor requires a sealed barrier."""

    def __init__(self, barrier: Any) -> None:
        # Local import prevents an evaluator capability in decision DTO modules.
        from .contracts import verify_barrier

        verify_barrier(barrier)
        self.__barrier = barrier
        self.__body = pinned_body()
        self.__dataset = digest(self.__body)
        self.__calendar = {r["date"]: r for r in self.__body["calendar"]}
        self.__rows = {(r["issuer"], r["session"]): r for r in self.__body["prices"]}
        require(len(self.__rows) == len(self.__body["prices"]) == 2790, "PRICE_GRID")
        self.__code = observe_asof_code(f2.ROOT)
        self.reads = 0
        self.native_invocations = 0
        self.qualified_reads = 0
        self.last_qualification: dict[str, Any] = {"invocation": "NOT_RUN"}

    def read_mark(self, issuer: str, session: str, evaluation_asof: str) -> QualifiedMark:
        from .contracts import verify_barrier

        verify_barrier(self.__barrier)
        require(self.reads < 5000, "MARK_BUDGET")
        self.reads += 1
        self.last_qualification = {"invocation": "NOT_RUN"}
        calendar = self.__calendar.get(session)
        require(
            issuer in ISSUERS and calendar is not None and calendar["status"] == "SESSION",
            "PRICE_IDENTITY",
        )
        assert calendar is not None
        row = self.__rows.get((issuer, session))
        require(row is not None, "MISSING_MARK")
        assert row is not None
        f2.closed(row, "id issuer session value available_at unit basis")
        close = calendar["close"]
        require(
            row["id"] == f"{issuer}-CLOSE-{session}"
            and row["issuer"] == issuer
            and row["session"] == session,
            "PRICE_VERSION_IDENTITY",
        )
        require(
            type(row["value"]) is int
            and 0 < row["value"] < 2**63
            and row["unit"] == "NTD_price_ticks_1e4"
            and row["basis"] == "unadjusted-synthetic-v1",
            "PRICE_VALUE",
        )
        require(
            f2.instant(row["available_at"]) == f2.instant(close) + timedelta(seconds=1)
            and f2.instant(row["available_at"]) <= f2.instant(evaluation_asof),
            "PRICE_AVAILABILITY",
        )
        require(evaluation_asof == row["available_at"], "PRICE_ASOF")
        day = date.fromisoformat(session)
        source = f2._notice(
            row, "synthetic_close_price", (day, day), row["id"], row["value"], row["unit"]
        )
        context = f2._context(
            (f2.instant(evaluation_asof) + timedelta(seconds=1)).isoformat(),
            row["id"],
            self.__dataset,
            self.__code,
        )
        self.native_invocations += 1
        actual = evaluate_slice(context, source.request, self.__code)
        self.last_qualification = {
            "invocation": "RUN",
            "s1_state": getattr(actual.s1, "state", "FAILURE"),
            "s1_reason": getattr(actual.s1, "reason", getattr(actual.s1, "code", "NONE")),
            "s2_state": getattr(actual.s2, "state", "FAILURE"),
            "s2_reason": getattr(actual.s2, "reason", getattr(actual.s2, "code", "NONE")),
        }
        for result in (actual.s1, actual.s2):
            if isinstance(result, d.BlockingFailure):
                raise F5Error("PRICE_QUALIFICATION_" + result.code)
        assert not isinstance(actual.s1, d.BlockingFailure)
        assert not isinstance(actual.s2, d.BlockingFailure)
        require(
            actual.s1.state == "BOUND"
            and actual.s2.state == "SUPPORTED"
            and isinstance(actual.s1.source_amount, d.Known),
            "PRICE_UNAVAILABLE",
        )
        assert isinstance(actual.s1.source_amount, d.Known)
        require(actual.s1.source_amount.value == row["value"], "PRICE_VALUE_MISMATCH")
        require(
            actual.diagnostic_only
            and not actual.admission_eligible
            and actual.source_authentication == "NOT_ESTABLISHED"
            and actual.trust == "NOT_TRUSTED_PIT_EVIDENCE",
            "PRICE_TRUST_FLAGS",
        )
        self.qualified_reads += 1
        return QualifiedMark(
            issuer,
            session,
            close,
            row["available_at"],
            row["value"],
            row["unit"],
            row["basis"],
            row["id"],
            row["id"] + "-VERSION",
            sha256(source.request.content.raw_bytes).hexdigest(),
            actual.s1.state,
            actual.s2.state,
            actual.s2.reason,
            evaluation_asof,
            witness_time=row["available_at"],
            native_s1_reason=str(getattr(actual.s1, "reason", "NONE")),
        )
