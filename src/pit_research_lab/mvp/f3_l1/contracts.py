"""Closed, separately versioned research protocol and exact numerical transport."""

import re
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from fractions import Fraction
from typing import Any

from pit_research_lab.mvp.f2.research_panel import PanelError, closed, digest, require
from pit_research_lab.mvp.research_vslice.contracts import research_bytes

VERSION = "F3_L1_RESEARCH_V0.1"
NUMERIC = "FRACTION_REDUCED_4096_DECIMAL50_FIXED12_HALF_EVEN_V1"
LIMITATIONS = (
    "AUTHORED_SYNTHETIC_INFRASTRUCTURE_ONLY",
    "NOT_REAL_TWSE_OR_HISTORICAL_PIT_CERTIFICATION",
    "NO_IF03_ISSUANCE_OR_IF05_ADMISSION",
    "NO_IID_PVALUES_CI_OR_H0_REJECTION",
    "REPEATED_MONTHLY_SIGNALS_AND_DEPENDENT_ENTITIES",
    "OVERLAPPING_20_SESSION_OUTCOMES",
    "DESCRIPTIVE_ASSOCIATION_AND_OOS_ASSESSMENT_ONLY",
    "NO_CAUSAL_OR_PROFITABILITY_CLAIM",
)


def fraction_wire(value: Fraction) -> dict[str, str]:
    require(type(value) is Fraction, "EXACT_FRACTION_REQUIRED")
    try:
        n, den = str(value.numerator), str(value.denominator)
    except ValueError:
        raise PanelError("NUMERIC_DIGIT_LIMIT") from None
    require(len(n.lstrip("-")) <= 4096 and len(den) <= 4096, "NUMERIC_DIGIT_LIMIT")
    return {"numerator": n, "denominator": den}


def fraction_read(value: object) -> Fraction:
    closed(value, "numerator denominator")
    assert isinstance(value, dict)
    for key, pattern in (("numerator", r"0|-?[1-9][0-9]*"), ("denominator", r"[1-9][0-9]*")):
        text = value[key]
        require(
            type(text) is str
            and len(text.lstrip("-")) <= 4096
            and re.fullmatch(pattern, text) is not None,
            "INVALID_FRACTION",
        )
    number = Fraction(int(value["numerator"]), int(value["denominator"]))
    require(fraction_wire(number) == value, "NONREDUCED_FRACTION")
    return number


def decimal_text(value: Fraction, *, sqrt: bool = False) -> str:
    fraction_wire(value)
    with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN)):
        number = Decimal(value.numerator) / Decimal(value.denominator)
        if sqrt:
            require(number >= 0, "NEGATIVE_SQRT")
            number = number.sqrt()
        rounded = number.quantize(Decimal("0.000000000001"))
        if rounded == 0:
            rounded = abs(rounded)
        return format(rounded, ".12f")


@dataclass(frozen=True, slots=True)
class Fold:
    name: str
    history_end: int
    test_start: int
    test_end: int


FOLDS = (Fold("F1", 48, 48, 72), Fold("F2", 72, 72, 96))


@dataclass(frozen=True, slots=True)
class Protocol:
    schema: str = VERSION
    seed: int = 17
    horizon_sessions: int = 20
    numeric_policy: str = NUMERIC
    folds: tuple[Fold, ...] = FOLDS
    min_train_cutoffs: int = 40
    min_train_rows: int = 180
    min_issuers: int = 3
    min_test_cutoffs: int = 20
    min_test_rows: int = 80

    def payload(self) -> dict[str, Any]:
        value = asdict(self)
        value["folds"] = [asdict(fold) for fold in self.folds]
        value.update(
            non_if03=True,
            question="Does PIT monthly revenue growth predict subsequent synthetic returns?",
            h0="beta = 0",
            h1="beta != 0",
            method="OLS_INTERCEPT_ONE_REGRESSOR_V1",
            feature="LATEST_AVAILABLE_MONTH_OVER_IMMEDIATE_PREDECESSOR_MINUS_ONE",
            temporal_policy={
                "feature": "public_delivery < decision",
                "training_label": "available_at <= fit",
                "fit": "17:00_FIRST_TEST_SESSION",
                "prediction": "18:00_LAST_SESSION_OF_WEEK",
                "target": "20_SUBSEQUENT_SESSION_CLOSES",
                "purge": "outcome_end < first_test_start_mark",
                "score": "sealed_prediction_then_mature_outcome",
                "validation": "NOT_APPLICABLE_NO_TUNING",
            },
            exclusion_policy="TYPED_UNAVAILABLE_NO_IMPUTATION_NO_OLDER_PAIR_FALLBACK",
            limitations=list(LIMITATIONS),
        )
        return value

    def validate(self) -> None:
        require(
            type(self) is Protocol
            and self == Protocol()
            and all(
                type(getattr(self, name)) is int
                for name in (
                    "seed",
                    "horizon_sessions",
                    "min_train_cutoffs",
                    "min_train_rows",
                    "min_issuers",
                    "min_test_cutoffs",
                    "min_test_rows",
                )
            )
            and type(self.folds) is tuple
            and all(
                type(f) is Fold
                and all(
                    type(getattr(f, name)) is int
                    for name in ("history_end", "test_start", "test_end")
                )
                for f in self.folds
            ),
            "UNSUPPORTED_PROTOCOL",
        )

    @property
    def identity(self) -> str:
        self.validate()
        return digest(self.payload())


def wire_bytes(kind: str, payload: dict[str, Any]) -> bytes:
    require(
        kind
        in {
            "SPEC",
            "BINDINGS",
            "FOLDS",
            "RESULT",
            "EVIDENCE",
            "PREDICTIONS",
            "ATTEMPT",
            "TARGETS",
            "STATES",
            "HANDOFF",
        },
        "UNSUPPORTED_SCHEMA",
    )
    return research_bytes(
        {"schema": "F3_L1_RESEARCH_" + kind + "_V0.1", "non_if03": True, "payload": payload}
    )
